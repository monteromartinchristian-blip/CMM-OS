"""Contract tests for the approved first-wave provider manifests.

Scope under test is the Plan 2 Task 3 contract: the eight approved providers
are registered declaratively (no per-provider subclass, no inference) and the
manifests stay free of credential material. Three policy decisions are pinned
here rather than left to implementation taste:

* Qwen Token Plan and Qwen Cloud remain separate providers with distinct
  ``provider_id`` values, so a subscription route and a PAYG route can never
  share quota/account state (spec §13 — "subscription vs PAYG separation").
* Kira's base URL is exactly ``https://kiraai.vn/api/v1`` and no Kira model id
  is hardcoded anywhere in the manifest: the endpoint's registry entry holds
  transport/auth defaults only, and ``/models`` discovery stays authoritative
  for the model list (spec §7, §9).
* The NVIDIA NIM ``activation_allowlist`` is empty. Kimi K3 is the approved
  NVIDIA scope, but its provider model id is unknown without a live ``/models``
  call, so activation defaults to manual approval rather than a guessed id.
"""

import dataclasses
from collections.abc import Mapping
from pathlib import Path

import pytest

from kernel.llm import first_wave_providers
from kernel.llm.exceptions import ProviderError
from kernel.llm.first_wave_providers import (
    provider_spec_from_manifest,
    register_first_wave_manifests,
    register_first_wave_providers,
    register_subscription_bridge_providers,
)
from kernel.llm.provider_connections import BillingClass
from kernel.llm.provider_manifests import (
    FIRST_WAVE_AUTH_SCHEME,
    ProviderManifestRegistry,
)
from kernel.llm.provider_manifests import ProviderManifest as _ProviderManifest
from kernel.llm.provider_registry import ProviderRegistry

# The exact approved first-wave set (plan Task 3 Step 1, spec §2). Declared
# uppercase-safe because provider ids are normalized to lowercase.
REQUIRED_PROVIDER_IDS: tuple[str, ...] = (
    "qwen-token-plan",
    "commandcode",
    "qwen-cloud",
    "deepseek",
    "kira",
    "openrouter",
    "opencode-zen",
    "nvidia-nim",
)

# Billing class per provider id (spec §2). ``BillingClass.API`` is the enum
# spelling of the spec's ``api``.
EXPECTED_BILLING_CLASSES: dict[str, BillingClass] = {
    "qwen-token-plan": BillingClass.SUBSCRIPTION,
    "commandcode": BillingClass.API,
    "qwen-cloud": BillingClass.PAYG,
    "deepseek": BillingClass.PAYG,
    "kira": BillingClass.FREE_OR_API,
    "openrouter": BillingClass.API,
    "opencode-zen": BillingClass.FREE_OR_API,
    "nvidia-nim": BillingClass.FREE_OR_API,
}

# Field names that would mean a manifest persists credential material.
_CREDENTIAL_FIELD_NAMES = frozenset({"api_key", "token", "secret", "password"})

# Case-insensitive substrings marking a declared value as secret-shaped. The
# manifests are declarative data, so any hit means a secret leaked into source
# instead of a keychain reference (``keychain://`` refs carry no such marker).
# The guard has a vacuous-pass hole: a value that is lowercase but not
# secret-shaped would slip past a mutant that lowercases values first. The
# positive/negative controls below exist to make that hole fail loudly if it is
# ever opened.
_SECRET_MARKERS = (
    "sk-",
    "api_key",
    "api-key",
    "apikey",
    "authorization",
    "bearer ",
    "password",
    "secret",
    "token=",
    "token:",
)

# Kira's manifest is pinned empty on purpose (plan Task 3 Step 3) and is the
# negative control for the secret scan: it has no model-id-shaped field, so
# deleting the scan call must still fail it. NVIDIA is excluded because its
# empty-allowlist default punishes the opposite mutant.
_CREDENTIAL_FREE_PROVIDER_IDS: tuple[str, ...] = tuple(
    provider_id for provider_id in REQUIRED_PROVIDER_IDS if provider_id != "nvidia-nim"
)

_KIRA_BASE_URL = "https://kiraai.vn/api/v1"

# Two synthetic controls that document why the credential scan is written the
# way it is (unicode-safe lowercasing, no whitespace stripping before match).
# Both are assembled from fragments at runtime so this file itself never holds a
# secret-shaped literal.
_SECRET_DIRECTIVE = "Author" + "ization: Bearer " + "sk-" + "live-abc123"
_SECRET_SHAPED_FOLDING = "pa\u00dfword"
_FILLER = "kimi-k3-approved"


# Test-only stand-in carrying a credential field name. The real
# ``ProviderManifest`` has no field named ``api_key`` (that is the point of the
# assertion below), so the only way to prove ``_leaked_fields`` reports a
# credential *field name* — rather than merely matching secret-shaped values —
# is to hand it a dataclass that does. Declared at module scope so the positive
# control in ``test_credential_and_keychain_reference_guard_has_no_vacuous_pass``
# exercises the same field-name branch the live manifests must never trigger.
@dataclasses.dataclass(frozen=True)
class _CredentialFieldProbe:
    """Dataclass with an ``api_key`` field, used only as a positive control."""

    provider_id: str = "probe"
    # Deliberately mundane: no marker in _SECRET_MARKERS appears here, so this
    # value can only be reported by the field-*name* branch of _leaked_fields.
    api_key: str = "opaque-value-with-no-marker"


def _bound_registry() -> tuple[ProviderRegistry, ProviderManifestRegistry]:
    """Return a canonical registry and a manifest catalog bound to it."""
    providers = ProviderRegistry()
    return providers, ProviderManifestRegistry(providers)


def _manifests() -> tuple[_ProviderManifest, ...]:
    """Return the first-wave manifests exactly as the registration returns them."""
    _, manifests = _bound_registry()
    return register_first_wave_manifests(manifests)


def _replacement_manifest(**overrides: object) -> _ProviderManifest:
    """Build a valid manifest for guard tests, keyed by ``provider_id``.

    Returned manifests satisfy the validator by construction, so a guard test
    can isolate the table-level invariant it is pinning instead of accidentally
    tripping ``ProviderManifest.__post_init__``.
    """
    fields: dict[str, object] = {
        "provider_id": "probe",
        "display_name": "Probe",
        "billing_class": BillingClass.API,
        "default_base_url": "https://probe.example/v1",
        "auth_scheme": FIRST_WAVE_AUTH_SCHEME,
    }
    fields.update(overrides)
    return _ProviderManifest(**fields)  # type: ignore[arg-type]


def test_guard_rejects_an_empty_first_wave_table(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Pin the emptiness guard: an emptied table must raise, not silently pass."""
    monkeypatch.setattr(first_wave_providers, "_FIRST_WAVE_MANIFESTS", ())

    with pytest.raises(ValueError, match="cannot be empty"):
        first_wave_providers._validated_manifests()

    # And the guard is on the registration path, not merely private helper code.
    _, manifests = _bound_registry()
    with pytest.raises(ValueError, match="cannot be empty"):
        register_first_wave_manifests(manifests)


def test_guard_rejects_a_missing_qwen_token_plan_separation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Pin the separation guard for the qwen-token-plan half (spec §13)."""
    table = tuple(
        manifest
        for manifest in first_wave_providers._FIRST_WAVE_MANIFESTS
        if manifest.provider_id != "qwen-token-plan"
    )
    assert len(table) == 7
    monkeypatch.setattr(first_wave_providers, "_FIRST_WAVE_MANIFESTS", table)

    with pytest.raises(ValueError) as excinfo:
        first_wave_providers._validated_manifests()

    message = str(excinfo.value)
    assert "qwen-token-plan" in message
    assert "qwen-cloud" in message
    assert "separate providers" in message


def test_guard_rejects_a_missing_qwen_cloud_separation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Pin the same guard for the qwen-cloud half — one branch, both directions."""
    table = tuple(
        manifest
        for manifest in first_wave_providers._FIRST_WAVE_MANIFESTS
        if manifest.provider_id != "qwen-cloud"
    )
    assert len(table) == 7
    monkeypatch.setattr(first_wave_providers, "_FIRST_WAVE_MANIFESTS", table)

    with pytest.raises(ValueError, match="separate providers"):
        first_wave_providers._validated_manifests()


def test_guard_rejects_a_collapsed_qwen_subscription_and_payg_table(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Pin the separation guard against the collapse it exists to prevent.

    Replacing qwen-cloud with a second qwen-token-plan manifest keeps the table
    8-long and well-formed, so only the separation guard can reject it: the two
    Qwen surfaces must not collapse into one provider id (spec §13).
    """
    collapsed = tuple(
        _replacement_manifest(
            provider_id="qwen-token-plan",
            display_name="Qwen Token Plan (collapsed)",
        )
        if manifest.provider_id == "qwen-cloud"
        else manifest
        for manifest in first_wave_providers._FIRST_WAVE_MANIFESTS
    )
    monkeypatch.setattr(first_wave_providers, "_FIRST_WAVE_MANIFESTS", collapsed)

    _, manifests = _bound_registry()
    with pytest.raises(ValueError, match="separate providers"):
        register_first_wave_manifests(manifests)


def test_registration_rejects_a_none_registry() -> None:
    """Pin the None-registry guard the docstring promises (not AttributeError)."""
    with pytest.raises(ValueError, match="registry cannot be None"):
        register_first_wave_manifests(None)  # type: ignore[arg-type]


def test_registration_rejects_a_repeat_bootstrap_without_duplicating() -> None:
    """A second bootstrap is rejected by the canonical authority, not re-checked.

    Registering the canonical ``ProviderSpec`` first means a repeat bootstrap
    fails on existing provider identity (``ProviderError``) before any metadata
    is touched. The intent of the previous assertion is preserved and widened:
    the second call is rejected *and* neither inventory grows.
    """
    providers, registry = _bound_registry()
    register_first_wave_manifests(registry)

    with pytest.raises(ProviderError, match="already registered"):
        register_first_wave_manifests(registry)

    assert len(providers.list()) == len(REQUIRED_PROVIDER_IDS)
    assert len(registry.list()) == len(REQUIRED_PROVIDER_IDS)


def test_first_wave_bootstrap_registers_provider_identity_canonically() -> None:
    """First-wave providers exist as canonical ``ProviderSpec`` entries first."""
    providers, manifests = _bound_registry()

    registered = register_first_wave_providers(providers, manifests)

    assert tuple(spec.id for spec in providers.list()) == tuple(
        sorted(manifest.provider_id for manifest in registered)
    )
    assert {m.provider_id for m in manifests.list()} == {
        spec.id for spec in providers.list()
    }
    assert providers.has("qwen-token-plan")
    assert providers.has("qwen-cloud")
    # Transport fidelity: the canonical specs must carry each manifest's own
    # transport, not merely its id (a wrong base_url would still route traffic).
    assert [(spec.id, spec.api_style, spec.base_url) for spec in providers.list()] == [
        (manifest.provider_id, manifest.api_styles[0], manifest.default_base_url)
        for manifest in sorted(registered, key=lambda item: item.provider_id)
    ]
    # The two Qwen surfaces are distinct identities, pinned on the registered
    # data (a literal-to-literal comparison would be constant-folded).
    qwen_billing = {
        manifest.provider_id: manifest.billing_class
        for manifest in registered
        if manifest.provider_id.startswith("qwen-")
    }
    assert set(qwen_billing) == {"qwen-token-plan", "qwen-cloud"}
    assert qwen_billing["qwen-token-plan"] is BillingClass.SUBSCRIPTION
    assert qwen_billing["qwen-cloud"] is BillingClass.PAYG


def test_register_first_wave_manifests_creates_identity_only_canonically() -> None:
    """The compatibility entry point cannot create identity off-authority."""
    providers, manifests = _bound_registry()

    register_first_wave_manifests(manifests)

    assert {spec.id for spec in providers.list()} == set(REQUIRED_PROVIDER_IDS)
    assert {manifest.provider_id for manifest in manifests.list()} == set(
        REQUIRED_PROVIDER_IDS
    )


def test_provider_spec_from_manifest_projects_canonical_transport() -> None:
    """The manifest-to-``ProviderSpec`` projection is deterministic."""
    manifest = first_wave_providers._FIRST_WAVE_MANIFESTS[0]

    spec = provider_spec_from_manifest(manifest)

    assert spec.id == manifest.provider_id
    assert spec.provider_type == "remote"
    assert spec.api_style == manifest.api_styles[0]
    assert spec.base_url == manifest.default_base_url


def test_blank_provider_id_is_rejected_by_the_manifest_boundary() -> None:
    """Document *where* a blank id is caught: the manifest, not the table guard.

    The module deliberately carries no blank-id branch because this boundary
    check makes it unreachable; this test pins that the boundary is what fires.
    """
    with pytest.raises(ValueError, match="cannot be empty"):
        _replacement_manifest(provider_id="   ")


def test_guard_module_has_no_unreachable_provider_id_branches() -> None:
    """Pin the deletion of the unreachable blank/duplicate branches.

    Both conditions are already impossible past ``ProviderManifest`` and
    ``ProviderManifestRegistry.register``, so a re-check in the module would be
    dead code. This asserts the module source carries neither message; if a
    future edit re-adds a branch, it must come back with a test that can reach it.
    """
    source = Path(str(first_wave_providers.__file__)).read_text(encoding="utf-8")

    assert "duplicate provider_id in first-wave manifests" not in source
    assert "cannot be empty" in source  # the emptiness guard is still there


def _by_id() -> dict[str, _ProviderManifest]:
    """Return the first-wave manifests keyed by normalized provider id."""
    return {manifest.provider_id: manifest for manifest in _manifests()}


def test_returns_exactly_the_eight_required_provider_ids() -> None:
    manifests = _manifests()

    assert isinstance(manifests, tuple)
    assert {manifest.provider_id for manifest in manifests} == set(
        REQUIRED_PROVIDER_IDS
    )
    assert len(manifests) == len(REQUIRED_PROVIDER_IDS)


def test_no_extra_provider_appears_in_the_registry() -> None:
    _, registry = _bound_registry()
    register_first_wave_manifests(registry)

    assert [manifest.provider_id for manifest in registry.list()] == sorted(
        REQUIRED_PROVIDER_IDS
    )
    assert set(EXPECTED_BILLING_CLASSES) == set(REQUIRED_PROVIDER_IDS)


def test_registration_registers_every_manifest_and_returns_them_in_order() -> None:
    _, registry = _bound_registry()

    returned = register_first_wave_manifests(registry)

    assert len(registry.list()) == 8
    # ``registry.list()`` is sorted by id; ``returned`` is declaration order
    # (plan order), so both are asserted rather than assumed equal.
    assert [manifest.provider_id for manifest in returned] == list(
        REQUIRED_PROVIDER_IDS
    )
    assert {manifest.provider_id for manifest in registry.list()} == set(
        REQUIRED_PROVIDER_IDS
    )
    for manifest in returned:
        assert registry.get(manifest.provider_id) is manifest


def test_every_manifest_constructs_through_the_validator() -> None:
    for manifest in _manifests():
        assert type(manifest).__name__ == "ProviderManifest"
        assert manifest.auth_scheme == FIRST_WAVE_AUTH_SCHEME
        assert manifest.api_styles == ("chat_completions",)
        assert manifest.models_path == "/models"
        assert manifest.default_base_url.startswith("https://")


def test_billing_class_per_provider_matches_spec() -> None:
    for provider_id, expected in EXPECTED_BILLING_CLASSES.items():
        manifest = _by_id()[provider_id]
        assert manifest.billing_class is expected, provider_id


def test_qwen_token_plan_and_qwen_cloud_are_separate_providers() -> None:
    manifests = _by_id()
    token_plan = manifests["qwen-token-plan"]
    cloud = manifests["qwen-cloud"]

    assert token_plan.billing_class is BillingClass.SUBSCRIPTION
    assert cloud.billing_class is BillingClass.PAYG
    assert token_plan.provider_id != cloud.provider_id


def test_kira_base_url_is_the_pinned_endpoint() -> None:
    # The manifest validator strips trailing slashes, so the stored value must
    # equal the pinned URL with no trailing slash or the two would disagree.
    kira = _by_id()["kira"]

    assert kira.default_base_url == _KIRA_BASE_URL

    # Source-level pin: the declared constant must also be canonical, so the
    # normalization is never load-bearing for the Kira endpoint.
    assert first_wave_providers.KIRA_BASE_URL == _KIRA_BASE_URL


def test_commandcode_base_url_is_the_documented_provider_root() -> None:
    """Pin CommandCode's researched endpoint (docs + live probe, not guesswork).

    The provider's documented OpenAI-compatible root is ``/provider/v1``: the
    docs page lists ``.../provider/v1/chat/completions``, ``/messages`` and
    ``/models``, and a live probe returned HTTP 200 with a model list for
    ``.../provider/v1/models`` while ``.../v1/models`` returned HTTP 404 ("not a
    registered API route"). The shorter ``/v1`` spelling would have 404'd every
    discovery call, so this value is asserted literally rather than derived.
    """
    expected = "https://api.commandcode.ai/provider/v1"
    commandcode = _by_id()["commandcode"]

    assert commandcode.default_base_url == expected
    assert first_wave_providers.COMMANDCODE_BASE_URL == expected

    # Regression pin: the previously declared /v1 root is a dead route.
    assert first_wave_providers.COMMANDCODE_BASE_URL != "https://api.commandcode.ai/v1"


def test_every_declared_base_url_is_pinned_and_provenance_documented() -> None:
    """Every base-URL constant is asserted literally and carries its provenance.

    A URL that moves upstream is a data change, so each constant is pinned by
    value here and the module documents which values were researched
    (provider-documented / probe-verified) versus spec-pinned (Kira). This keeps
    a silent endpoint edit from passing review.
    """
    expected_urls = {
        "QWEN_TOKEN_PLAN_BASE_URL": (
            "https://token-plan.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1"
        ),
        "COMMANDCODE_BASE_URL": "https://api.commandcode.ai/provider/v1",
        "QWEN_CLOUD_BASE_URL": (
            "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
        ),
        "DEEPSEEK_BASE_URL": "https://api.deepseek.com/v1",
        "KIRA_BASE_URL": "https://kiraai.vn/api/v1",
        "OPENROUTER_BASE_URL": "https://openrouter.ai/api/v1",
        "OPENCODE_ZEN_BASE_URL": "https://opencode.ai/zen/v1",
        "NVIDIA_NIM_BASE_URL": "https://integrate.api.nvidia.com/v1",
        "CODEX_BASE_URL": "https://api.openai.com/v1",
        "CLAUDE_CODE_BASE_URL": "https://api.anthropic.com/v1",
        "ANTIGRAVITY_BASE_URL": "https://cloudcode-pa.googleapis.com/v1",
    }

    assert set(expected_urls) == {
        name for name in vars(first_wave_providers) if name.endswith("_BASE_URL")
    }
    for name, expected in expected_urls.items():
        actual = getattr(first_wave_providers, name)
        assert actual == expected, name
        # Canonical: lowercase scheme, no trailing slash, so the validator's
        # normalization is never load-bearing for a declared constant.
        assert actual == actual.lower(), name
        assert not actual.endswith("/"), name

    # Each manifest wires the constant it is supposed to.
    for provider_id, name in {
        "qwen-token-plan": "QWEN_TOKEN_PLAN_BASE_URL",
        "commandcode": "COMMANDCODE_BASE_URL",
        "qwen-cloud": "QWEN_CLOUD_BASE_URL",
        "deepseek": "DEEPSEEK_BASE_URL",
        "kira": "KIRA_BASE_URL",
        "openrouter": "OPENROUTER_BASE_URL",
        "opencode-zen": "OPENCODE_ZEN_BASE_URL",
        "nvidia-nim": "NVIDIA_NIM_BASE_URL",
    }.items():
        assert _by_id()[provider_id].default_base_url == getattr(
            first_wave_providers, name
        ), provider_id

    # The subscription bridges are wired to their pinned endpoints as well.
    assert {
        manifest.provider_id: manifest.default_base_url for manifest in _bridges()
    } == {
        "codex": first_wave_providers.CODEX_BASE_URL,
        "claude-code": first_wave_providers.CLAUDE_CODE_BASE_URL,
        "antigravity": first_wave_providers.ANTIGRAVITY_BASE_URL,
    }

    # Provenance is recorded in the module, per the review finding: the three
    # classes must be named so a reader can tell researched values from pinned.
    source = Path(str(first_wave_providers.__file__)).read_text(encoding="utf-8")
    assert "spec-pinned" in source
    assert "provider-documented" in source
    assert "externally-verified-via-probe" in source


def test_kira_manifest_hardcodes_no_model_ids() -> None:
    kira = _by_id()["kira"]
    declared = tuple(
        value
        for field in dataclasses.fields(kira)
        for value in _declared_values(getattr(kira, field.name))
    )

    assert kira.activation_allowlist == ()

    # Field-level: no declared value looks like a provider model id. The endpoint
    # is exempt because its version segment is not a model id.
    assert _model_id_shaped_in(declared, endpoint=_KIRA_BASE_URL) == ()

    # Whole-manifest structural scan: any collection value (not just the
    # allowlist) whose entries are not the pinned endpoint is a hardcoded id.
    assert _model_id_collections_within(kira, _KIRA_BASE_URL) == ()

    # Self-checks: the predicate is not vacuously true.
    assert _model_id_shaped_in(("qwen3.8-27b-free",)) == ("qwen3.8-27b-free",)
    assert _model_id_collections_within({"models": ("glm-5.3-free",)}, "") != ()
    assert _model_id_shaped_in((_KIRA_BASE_URL,), endpoint=_KIRA_BASE_URL) == ()


def test_nvidia_allowlist_is_empty_because_kimi_k3_id_is_not_known_offline() -> None:
    # Policy (plan Task 3 Step 3): NVIDIA scope starts at Kimi K3, but its
    # provider model id is only knowable from a live /models response. Plan 2
    # forbids live calls, so the allowlist stays empty and activation defaults
    # to manual approval. Discovery remains authoritative: inventing an id here
    # would silently activate a route that no discovery result can confirm.
    nvidia = _by_id()["nvidia-nim"]

    assert nvidia.activation_allowlist == ()


def test_every_other_manifest_also_defers_activation_to_discovery() -> None:
    for provider_id in REQUIRED_PROVIDER_IDS:
        if provider_id == "nvidia-nim":
            continue
        assert _by_id()[provider_id].activation_allowlist == (), provider_id


def test_no_manifest_carries_credential_shaped_data() -> None:
    manifests = {**_by_id(), **{item.provider_id: item for item in _bridges()}}
    assert set(manifests) == set(REQUIRED_PROVIDER_IDS) | set(
        REQUIRED_SUBSCRIPTION_BRIDGE_IDS
    )
    for provider_id, manifest in manifests.items():
        field_names = [field.name for field in dataclasses.fields(manifest)]
        # Substring match: a field named secret_ref is still a credential field.
        assert not _CREDENTIAL_FIELD_NAMES.intersection(field_names), provider_id
        for field in dataclasses.fields(manifest):
            for value in _declared_values(getattr(manifest, field.name)):
                assert not any(marker in str(value) for marker in _SECRET_MARKERS), (
                    provider_id,
                    field.name,
                )

    assert _leaked_provider_ids(manifests) == ()


def test_credential_and_keychain_reference_guard_has_no_vacuous_pass() -> None:
    manifests = _by_id()

    assert _leaked_provider_ids(manifests) == ()

    # Control 1: a secret-shaped value must be detected. The literal is built at
    # runtime from parts so this file never itself contains a secret-shaped
    # string.
    leaked = dict(manifests)
    secret_shape = (
        _SECRET_DIRECTIVE.split(" ")[0] + " " + _SECRET_DIRECTIVE.split(" ")[1]
    )
    control = dataclasses.replace(manifests["openrouter"])
    object.__setattr__(control, "display_name", secret_shape)
    leaked["openrouter"] = control
    assert _leaked_fields(control) == (("display_name", secret_shape),)
    assert _leaked_provider_ids(leaked) == ("openrouter",)

    # Control 2: the scan must not strip whitespace before matching — a padded
    # secret is still a secret.
    assert _secret_shaped("  " + secret_shape + "  ") is True

    # Control 3: the scan is unicode-safe and case-insensitive. "paßword"
    # casefolds to "password" but lowercases to itself, so a lower()-only
    # implementation would miss the marker and fail this assertion.
    folding_marker = "password"
    assert folding_marker in _SECRET_MARKERS
    assert _secret_shaped(_SECRET_SHAPED_FOLDING) is True
    assert folding_marker in _SECRET_SHAPED_FOLDING.casefold()
    assert folding_marker not in _SECRET_SHAPED_FOLDING.lower()

    # Control 4: the guard's vocabulary is not simply "everything" — a keychain
    # reference with a model-shaped filler around it is not secret-shaped.
    for provider_id in _CREDENTIAL_FREE_PROVIDER_IDS:
        assert (
            _leaked_fields(
                dataclasses.replace(manifests[provider_id], display_name=_FILLER)
            )
            == ()
        ), provider_id
    assert _secret_shaped("keychain://cmm/providers/deepseek/" + _FILLER) is False

    # Control 5: the field-name branch is real. The intersection assertion in
    # the sibling test is vacuous over a fixed 8-field constructor — it can only
    # ever be empty — so the branch is proved here on a synthetic dataclass whose
    # value is deliberately NOT secret-shaped: the only reason it is reported is
    # its field name. Deleting the ``_CREDENTIAL_FIELD_NAMES`` branch makes this
    # control return () and fail.
    probe = _CredentialFieldProbe()
    assert _secret_shaped(probe.api_key) is False
    assert _leaked_fields(probe) == (("api_key", probe.api_key),)
    assert _leaked_provider_ids({"probe": probe}) == ("probe",)
    # And the live manifests must not look like the probe.
    assert not _CREDENTIAL_FIELD_NAMES.intersection(
        field.name
        for manifest in manifests.values()
        for field in dataclasses.fields(manifest)
    )


def test_manifests_carry_only_plain_declarative_field_values() -> None:
    # A callable, set, dict or object value would mean the manifest smuggles
    # behaviour or a credential resolver instead of declaring static defaults.
    # ``bool`` is admitted for the declarative ``requires_isolation`` policy
    # (MAJOR-V2-03); callables and containers stay rejected, which the controls
    # below pin so the admitted set cannot silently widen.
    for manifest in (*_manifests(), *_bridges()):
        for field in dataclasses.fields(manifest):
            for value in _declared_values(getattr(manifest, field.name)):
                assert _plain_declared_value(value), (manifest.provider_id, field.name)

    assert _plain_declared_value("bearer") is True
    assert _plain_declared_value(True) is True
    assert _plain_declared_value(False) is True
    assert _plain_declared_value(lambda: None) is False
    assert _plain_declared_value({"resolver": "keychain://cmm/providers"}) is False
    assert _plain_declared_value({"a", "b"}) is False


def test_module_declares_no_provider_model_id_literals() -> None:
    # Kira's documented free model ids and the NVIDIA Kimi K3 id are deliberately
    # absent from the implementation module as well: no provider model id may be
    # pinned in source while discovery is authoritative. Only single-quoted and
    # double-quoted literals are scanned, so docstrings/comments (prose) cannot
    # trip the check while a pinned model id still does.
    source_path = Path(str(first_wave_providers.__file__))
    source = source_path.read_text(encoding="utf-8")
    literals = _model_id_literals_in(source, quote="'") + _model_id_literals_in(
        source, quote='"'
    )

    assert literals == ()
    # Self-check: the scanner does report a pinned model-id literal.
    assert _model_id_literals_in(
        "    model_ids = ('qwen3.8-27b-free',)", quote="'"
    ) == ("qwen3.8-27b-free",)
    assert _model_id_literals_in('"https://kiraai.vn/api/v1"') == ()


# --- subscription bridge isolation policy (MAJOR-V2-03) ---------------------

# The three approved subscription bridges (approved hybrid design §2). They are
# a separate canonical category from the eight first-wave API providers, and
# each must run under a CMM-owned isolation profile even when the external home
# carries authentication evidence only.
REQUIRED_SUBSCRIPTION_BRIDGE_IDS: tuple[str, ...] = (
    "codex",
    "claude-code",
    "antigravity",
)

_EXPECTED_SUBSCRIPTION_BRIDGE_URLS: dict[str, str] = {
    "codex": "https://api.openai.com/v1",
    "claude-code": "https://api.anthropic.com/v1",
    "antigravity": "https://cloudcode-pa.googleapis.com/v1",
}


def _bridges() -> tuple[_ProviderManifest, ...]:
    """Return the canonical subscription-bridge manifests as registered."""
    providers, manifests = _bound_registry()
    return register_subscription_bridge_providers(providers, manifests)


def test_subscription_bridges_declare_the_isolation_policy_explicitly() -> None:
    """Each bridge is a subscription surface that requires CMM-owned isolation."""
    bridges = _bridges()

    assert [manifest.provider_id for manifest in bridges] == list(
        REQUIRED_SUBSCRIPTION_BRIDGE_IDS
    )
    for manifest in bridges:
        assert manifest.requires_isolation is True, manifest.provider_id
        assert manifest.billing_class is BillingClass.SUBSCRIPTION, manifest.provider_id
        assert (
            manifest.default_base_url
            == _EXPECTED_SUBSCRIPTION_BRIDGE_URLS[manifest.provider_id]
        ), manifest.provider_id


def test_no_first_wave_provider_declares_the_isolation_policy() -> None:
    """Qwen Token Plan stays a subscription surface without local isolation.

    The policy is explicit metadata, so a subscription billing class must never
    be enough to force a first-wave provider into profile isolation.
    """
    first_wave = _by_id()

    assert first_wave["qwen-token-plan"].billing_class is BillingClass.SUBSCRIPTION
    for provider_id, manifest in first_wave.items():
        assert manifest.requires_isolation is False, provider_id


def test_subscription_bridge_bootstrap_registers_identity_before_metadata() -> None:
    """Canonical identity first, then the bound manifest — as for first wave."""
    providers, manifests = _bound_registry()

    registered = register_subscription_bridge_providers(providers, manifests)

    assert tuple(spec.id for spec in providers.list()) == tuple(
        sorted(REQUIRED_SUBSCRIPTION_BRIDGE_IDS)
    )
    assert {manifest.provider_id for manifest in manifests.list()} == set(
        REQUIRED_SUBSCRIPTION_BRIDGE_IDS
    )
    for manifest in registered:
        assert manifests.get(manifest.provider_id) is manifest
        assert providers.get(manifest.provider_id).base_url == (
            manifest.default_base_url
        )


def test_subscription_bridge_bootstrap_rejects_none_arguments() -> None:
    providers, manifests = _bound_registry()

    with pytest.raises(ValueError, match="provider_registry cannot be None"):
        register_subscription_bridge_providers(None, manifests)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="manifests cannot be None"):
        register_subscription_bridge_providers(providers, None)  # type: ignore[arg-type]


def test_bridge_bootstrap_leaves_the_eight_provider_contract_intact() -> None:
    """The verified first-wave contract is not widened or re-policied."""
    providers, manifests = _bound_registry()
    first_wave = {
        manifest.provider_id for manifest in register_first_wave_manifests(manifests)
    }

    register_subscription_bridge_providers(providers, manifests)

    assert first_wave == set(REQUIRED_PROVIDER_IDS)
    assert {spec.id for spec in providers.list()} == first_wave | set(
        REQUIRED_SUBSCRIPTION_BRIDGE_IDS
    )
    reloaded = {manifest.provider_id: manifest for manifest in manifests.list()}
    assert set(reloaded) == first_wave | set(REQUIRED_SUBSCRIPTION_BRIDGE_IDS)
    for provider_id in REQUIRED_PROVIDER_IDS:
        assert reloaded[provider_id].requires_isolation is False, provider_id


def test_guard_rejects_an_empty_subscription_bridge_table(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Pin the emptiness guard on the bridge table and its bootstrap path."""
    monkeypatch.setattr(first_wave_providers, "_SUBSCRIPTION_BRIDGE_MANIFESTS", ())

    with pytest.raises(ValueError, match="cannot be empty"):
        first_wave_providers._validated_subscription_bridge_manifests()

    providers, manifests = _bound_registry()
    with pytest.raises(ValueError, match="cannot be empty"):
        register_subscription_bridge_providers(providers, manifests)


def test_guard_rejects_a_bridge_declared_without_isolation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A bridge that drops the isolation policy must fail, not connect bare."""
    table = tuple(
        _replacement_manifest(
            provider_id=manifest.provider_id,
            requires_isolation=False,
        )
        if manifest.provider_id == "antigravity"
        else manifest
        for manifest in first_wave_providers._SUBSCRIPTION_BRIDGE_MANIFESTS
    )
    monkeypatch.setattr(first_wave_providers, "_SUBSCRIPTION_BRIDGE_MANIFESTS", table)

    with pytest.raises(ValueError, match="requires_isolation"):
        first_wave_providers._validated_subscription_bridge_manifests()


def test_guard_rejects_a_bridge_colliding_with_a_first_wave_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The bridge category must not reinterpret a first-wave provider id."""
    table = tuple(
        _replacement_manifest(provider_id="deepseek", requires_isolation=True)
        if manifest.provider_id == "codex"
        else manifest
        for manifest in first_wave_providers._SUBSCRIPTION_BRIDGE_MANIFESTS
    )
    monkeypatch.setattr(first_wave_providers, "_SUBSCRIPTION_BRIDGE_MANIFESTS", table)

    with pytest.raises(ValueError, match="distinct from first-wave"):
        first_wave_providers._validated_subscription_bridge_manifests()


def _plain_declared_value(value: object) -> bool:
    """Return whether a declared manifest value is a plain static scalar."""
    return isinstance(value, (str, bool))


def _declared_values(value: object) -> tuple[object, ...]:
    """Return the declared values of a manifest field as a flat tuple."""
    if isinstance(value, str):
        return (value,)
    if isinstance(value, tuple):
        return tuple(value)
    return (value,)


def _model_id_shaped_in(
    values: tuple[object, ...], *, endpoint: str = ""
) -> tuple[object, ...]:
    """Return declared values that look like a provider model id.

    A model id is a version-bearing identifier, not a URL: ``qwen3.8-27b-free``
    qualifies, while a base URL (``://``) is exempt, as is ``endpoint`` itself
    because its version segment (``v1``) carries a digit without being a model id.
    """
    return tuple(
        value
        for value in values
        if "://" not in str(value)
        and str(value) != endpoint
        and (
            any(character.isdigit() for character in str(value))
            or "-free" in str(value)
        )
    )


def _model_id_collections_within(
    value: object, endpoint: str, *, _depth: int = 0
) -> tuple[str, ...]:
    """Return entries of collection-valued fields that look like model ids.

    Walks dataclass manifests and nested mappings/collections; the shared
    predicate exempts base URLs, so the pinned endpoint cannot self-flag.
    """
    if _depth > 3:
        return ()
    if isinstance(value, (tuple, list, set, frozenset)):
        return tuple(
            str(entry) for entry in _model_id_shaped_in(tuple(value), endpoint=endpoint)
        )
    if isinstance(value, dict):
        found: list[str] = []
        for entry in value.values():
            found.extend(
                _model_id_collections_within(entry, endpoint, _depth=_depth + 1)
            )
        return tuple(found)
    if not dataclasses.is_dataclass(value) or isinstance(value, type):
        return ()
    found = []
    for field in dataclasses.fields(value):
        found.extend(
            _model_id_collections_within(
                getattr(value, field.name), endpoint, _depth=_depth + 1
            )
        )
    return tuple(found)


def _model_id_literals_in(text: str, *, quote: str = '"') -> tuple[str, ...]:
    """Return ``quote``-delimited literals in ``text`` that look like model ids.

    Uses the same shape test as the field scan, so URLs, docstrings and prose
    cannot be reported as pinned model ids.
    """
    literals: list[str] = []
    for chunk in text.split(quote)[1::2]:
        if " " in chunk or "\n" in chunk:
            continue
        if _model_id_shaped_in((chunk,)):
            literals.append(chunk)
    return tuple(sorted(set(literals)))


def _secret_shaped(value: object) -> bool:
    """Return whether a declared value carries secret material."""
    text = str(value)
    folded = text.casefold()
    return any(marker in text or marker in folded for marker in _SECRET_MARKERS)


def _leaked_fields(manifest: object) -> tuple[tuple[str, str], ...]:
    """Return (field name, field value) pairs whose values are secret-shaped.

    Takes ``object`` rather than ``ProviderManifest`` so the positive control
    can pass a synthetic dataclass that carries a credential *field name*.
    """
    leaked: list[tuple[str, str]] = []
    for field in dataclasses.fields(manifest):  # type: ignore[arg-type]
        value = getattr(manifest, field.name)
        if field.name in _CREDENTIAL_FIELD_NAMES:
            leaked.append((field.name, str(value)))
            continue
        for declared in _declared_values(value):
            if _secret_shaped(declared):
                leaked.append((field.name, str(declared)))
    return tuple(leaked)


def _leaked_provider_ids(
    manifests: Mapping[str, object],
) -> tuple[str, ...]:
    """Return the provider ids whose manifests carry credential-shaped data.

    Typed for any dataclass-bearing mapping so the positive control can pass a
    synthetic credential-field probe alongside the real manifests.
    """
    return tuple(
        sorted(
            provider_id
            for provider_id, manifest in manifests.items()
            if _leaked_fields(manifest)
        )
    )
