"""Canonical provider manifest declarations for the Provider Registry.

This module is pure declaration: it holds the transport/auth/billing defaults
for the two canonical provider categories — the eight approved first-wave
OpenAI-compatible providers (spec §2, plan Task 3) and the three approved
subscription bridges (approved hybrid design §2) — and registers them into a
:class:`ProviderManifestRegistry`. Nothing here performs network I/O, and no
credential material — not a key, not a token, not a keychain reference — appears
in a manifest: secrets live in native secret storage and are referenced by
accepted connections (see ``kernel.llm.provider_connections``).

The two categories are registered by two separate bootstraps and never share a
provider id: :func:`register_first_wave_providers` registers the eight API
surfaces, and :func:`register_subscription_bridge_providers` registers the three
subscription bridges. Keeping them apart is what preserves the verified
eight-provider contract while giving the bridges their own policy
(``requires_isolation=True``) — a declaration table cannot silently widen the
other one.

Base URLs are the providers' documented public OpenAI-compatible endpoints. A
manifest carries no per-provider subclass and no model catalog: model ids are
only knowable from a live ``/models`` response, so runtime discovery remains the
authoritative catalog (spec §7) and no provider model id is hardcoded here.

``activation_allowlist`` is empty for every first-wave provider. That is a
deliberate policy, not an omission:

* Activation is discovery-driven by default. A non-empty allowlist narrows
  routing to explicitly approved provider model ids, which requires an id that
  has actually been observed.
* NVIDIA NIM's approved scope starts at Kimi K3, but its provider model id is
  only knowable from a live ``/models`` call. This plan performs no live calls,
  so the allowlist stays empty and NVIDIA activation defaults to manual
  approval. Inventing an id would silently activate a route that no discovery
  result could confirm.

Billing classes follow spec §2 exactly, including the mandatory separation of
``qwen-token-plan`` (subscription) from ``qwen-cloud`` (PAYG): identical models
may be exposed by both, but they must remain distinct providers so quota and
account state can never be shared implicitly (spec §13).

Isolation policy (MAJOR-V2-03): ``requires_isolation`` is declared per provider
and never inferred from ``BillingClass``. The three subscription bridges declare
``True`` because each must run under a CMM-owned profile even when the external
home carries authentication evidence only; ``qwen-token-plan`` stays ``False``
even though it is also a subscription surface (spec §6.3 explicitly forbids the
billing-class inference). The bridge table's own guard refuses a bridge that
drops the policy and a bridge id that collides with a first-wave provider.

Error taxonomy: this module raises :class:`ValueError` for every configuration
error it detects directly — an empty manifest table, a missing
Qwen subscription/PAYG pair, a bridge without isolation policy, a bridge id that
collides with a first-wave provider, an absent registry argument — and forwards
whatever the registries raise: the canonical
:class:`~kernel.llm.provider_registry.ProviderRegistry` answers a
repeat bootstrap with :class:`~kernel.llm.exceptions.ProviderError`
(``"Provider is already registered"``) because identity is registered first,
and :class:`ProviderManifest`/``ProviderManifestRegistry`` raise
``ValueError`` for malformed field values and for duplicate manifest
metadata. Blank and duplicate provider ids are *not* re-checked here:
:class:`ProviderManifest` rejects a blank id and
:meth:`ProviderManifestRegistry.register` rejects a duplicate, both at the
boundary, so re-checking them would be unreachable code.
"""

from __future__ import annotations

from kernel.llm.provider_connections import BillingClass
from kernel.llm.provider_manifests import (
    FIRST_WAVE_AUTH_SCHEME,
    ProviderManifest,
    ProviderManifestRegistry,
)
from kernel.llm.provider_registry import ProviderRegistry, ProviderSpec

# Documented public OpenAI-compatible endpoints, keyed by provider id. Values
# are canonical (lowercase scheme, no trailing slash) so the validator's
# trailing-slash normalization is a no-op rather than a silent rewrite.
#
# Provenance per constant, so it stays visible which values were *researched*
# and could drift versus which were handed down by the spec (a URL that moves
# upstream is a data change here, never a silent code change):
#
#   spec-pinned (plan global constraint, spec §2 — not renegotiable here)
#     KIRA_BASE_URL
#   provider-documented (each vendor's published OpenAI-compatible root)
#     QWEN_TOKEN_PLAN_BASE_URL, QWEN_CLOUD_BASE_URL, OPENCODE_ZEN_BASE_URL,
#     DEEPSEEK_BASE_URL, OPENROUTER_BASE_URL, NVIDIA_NIM_BASE_URL
#   externally-verified-via-probe (documented *and* confirmed by a live call)
#     COMMANDCODE_BASE_URL
QWEN_TOKEN_PLAN_BASE_URL: str = (
    "https://token-plan.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1"
)
# Provider-documented **and** externally verified by live probe before pinning.
# The documented OpenAI-compatible root is .../provider/v1, not .../v1:
# https://commandcode.ai/docs/provider lists
# https://api.commandcode.ai/provider/v1/chat/completions, /messages and /models.
# Verified 2026-09-14: GET https://api.commandcode.ai/provider/v1/models -> 200
# with a model list, whereas GET https://api.commandcode.ai/v1/models -> 404
# ("... is not a registered API route"). The /v1 spelling would have failed
# every discovery call, so the probe is the load-bearing evidence here.
COMMANDCODE_BASE_URL: str = "https://api.commandcode.ai/provider/v1"
QWEN_CLOUD_BASE_URL: str = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
DEEPSEEK_BASE_URL: str = "https://api.deepseek.com/v1"
# Spec-pinned by the plan's global constraints and spec §2; bearer auth.
KIRA_BASE_URL: str = "https://kiraai.vn/api/v1"
OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
OPENCODE_ZEN_BASE_URL: str = "https://opencode.ai/zen/v1"
NVIDIA_NIM_BASE_URL: str = "https://integrate.api.nvidia.com/v1"

# Subscription bridge endpoints (approved hybrid design §2). Each is the
# vendor's documented OpenAI-compatible root for the subscription surface the
# bridge fronts; the CMM-owned isolation profile, not the user's external home,
# is what a connection references. All three are provider-documented.
CODEX_BASE_URL: str = "https://api.openai.com/v1"
CLAUDE_CODE_BASE_URL: str = "https://api.anthropic.com/v1"
ANTIGRAVITY_BASE_URL: str = "https://cloudcode-pa.googleapis.com/v1"

# Declared in plan order (plan Task 3, spec §2). Registration is order-free —
# the registry sorts by id — but tests compare the returned tuple against this
# order, so it is part of the contract.
_FIRST_WAVE_MANIFESTS: tuple[ProviderManifest, ...] = (
    ProviderManifest(
        provider_id="qwen-token-plan",
        display_name="Qwen Token Plan",
        billing_class=BillingClass.SUBSCRIPTION,
        default_base_url=QWEN_TOKEN_PLAN_BASE_URL,
        auth_scheme=FIRST_WAVE_AUTH_SCHEME,
    ),
    ProviderManifest(
        provider_id="commandcode",
        display_name="CommandCode API",
        billing_class=BillingClass.API,
        default_base_url=COMMANDCODE_BASE_URL,
        auth_scheme=FIRST_WAVE_AUTH_SCHEME,
    ),
    ProviderManifest(
        provider_id="qwen-cloud",
        display_name="Qwen Cloud PAYG",
        billing_class=BillingClass.PAYG,
        default_base_url=QWEN_CLOUD_BASE_URL,
        auth_scheme=FIRST_WAVE_AUTH_SCHEME,
    ),
    ProviderManifest(
        provider_id="deepseek",
        display_name="DeepSeek API",
        billing_class=BillingClass.PAYG,
        default_base_url=DEEPSEEK_BASE_URL,
        auth_scheme=FIRST_WAVE_AUTH_SCHEME,
    ),
    ProviderManifest(
        provider_id="kira",
        display_name="Kira AI",
        billing_class=BillingClass.FREE_OR_API,
        default_base_url=KIRA_BASE_URL,
        auth_scheme=FIRST_WAVE_AUTH_SCHEME,
    ),
    ProviderManifest(
        provider_id="openrouter",
        display_name="OpenRouter",
        billing_class=BillingClass.API,
        default_base_url=OPENROUTER_BASE_URL,
        auth_scheme=FIRST_WAVE_AUTH_SCHEME,
    ),
    ProviderManifest(
        provider_id="opencode-zen",
        display_name="OpenCode Zen",
        billing_class=BillingClass.FREE_OR_API,
        default_base_url=OPENCODE_ZEN_BASE_URL,
        auth_scheme=FIRST_WAVE_AUTH_SCHEME,
    ),
    ProviderManifest(
        provider_id="nvidia-nim",
        display_name="NVIDIA NIM",
        billing_class=BillingClass.FREE_OR_API,
        default_base_url=NVIDIA_NIM_BASE_URL,
        auth_scheme=FIRST_WAVE_AUTH_SCHEME,
    ),
)

# The three approved subscription bridges, declared in canonical order. They are
# a separate category from the first-wave API providers (approved hybrid design
# §2) and each declares ``requires_isolation=True`` as explicit canonical policy
# (spec §6.3): a bridge may become CONNECTED only through a CMM-owned isolation
# profile, even when the external home carries authentication evidence alone.
# ``billing_class`` is metadata here and is deliberately NOT the source of the
# policy — ``qwen-token-plan`` above is also a subscription surface and stays
# ``requires_isolation=False``.
_SUBSCRIPTION_BRIDGE_MANIFESTS: tuple[ProviderManifest, ...] = (
    ProviderManifest(
        provider_id="codex",
        display_name="Codex (ChatGPT Plus)",
        billing_class=BillingClass.SUBSCRIPTION,
        default_base_url=CODEX_BASE_URL,
        auth_scheme=FIRST_WAVE_AUTH_SCHEME,
        requires_isolation=True,
    ),
    ProviderManifest(
        provider_id="claude-code",
        display_name="Claude Code (Claude Pro)",
        billing_class=BillingClass.SUBSCRIPTION,
        default_base_url=CLAUDE_CODE_BASE_URL,
        auth_scheme=FIRST_WAVE_AUTH_SCHEME,
        requires_isolation=True,
    ),
    ProviderManifest(
        provider_id="antigravity",
        display_name="Antigravity (Google AI Pro)",
        billing_class=BillingClass.SUBSCRIPTION,
        default_base_url=ANTIGRAVITY_BASE_URL,
        auth_scheme=FIRST_WAVE_AUTH_SCHEME,
        requires_isolation=True,
    ),
)


def _validated_manifests() -> tuple[ProviderManifest, ...]:
    """Return the declared manifests after checkable invariants hold.

    Only invariants that this module can actually observe are checked here:

    * the table is non-empty (a mutant that blanks the declaration is caught);
    * the Qwen subscription/PAYG pair is both present — the cross-manifest
      invariant the table itself can violate (spec §13).

    Blank and duplicate ``provider_id`` are deliberately *not* re-checked:
    :class:`ProviderManifest` already rejects a blank id and
    :meth:`ProviderManifestRegistry.register` already rejects a duplicate, so a
    local check could never fire and would be untestable dead code.
    """
    if not _FIRST_WAVE_MANIFESTS:
        raise ValueError("first-wave manifests cannot be empty")

    provider_ids = tuple(manifest.provider_id for manifest in _FIRST_WAVE_MANIFESTS)

    # Subscription and PAYG surfaces of the same vendor must never collapse into
    # one provider: shared quota/account state would follow implicitly (spec §13).
    if "qwen-token-plan" not in provider_ids or "qwen-cloud" not in provider_ids:
        raise ValueError(
            "qwen-token-plan and qwen-cloud must both be registered as "
            "separate providers"
        )

    return _FIRST_WAVE_MANIFESTS


def _validated_subscription_bridge_manifests() -> tuple[ProviderManifest, ...]:
    """Return the declared subscription bridges after their policy holds.

    Only invariants this table can actually violate are checked, and each one is
    reachable:

    * the table is non-empty (a mutant that blanks the declaration is caught);
    * every declared bridge carries ``requires_isolation=True`` — the entire
      point of declaring the bridges separately (spec §6.3): a bridge that lost
      the policy would silently connect without a CMM-owned profile;
    * no bridge reuses a first-wave provider id — the categories are distinct
      surfaces, and a shared id would reinterpret an API provider as an
      isolation-required bridge (spec §13's separation rule, applied across
      categories).

    Blank and duplicate ``provider_id`` inside the table are deliberately *not*
    re-checked: :class:`ProviderManifest` and
    :meth:`ProviderManifestRegistry.register` already reject them.
    """
    if not _SUBSCRIPTION_BRIDGE_MANIFESTS:
        raise ValueError("subscription bridge manifests cannot be empty")

    undeclared = sorted(
        manifest.provider_id
        for manifest in _SUBSCRIPTION_BRIDGE_MANIFESTS
        if not manifest.requires_isolation
    )
    if undeclared:
        raise ValueError(
            "subscription bridges must declare requires_isolation: " + undeclared[0]
        )

    first_wave_ids = {manifest.provider_id for manifest in _FIRST_WAVE_MANIFESTS}
    collisions = sorted(
        manifest.provider_id
        for manifest in _SUBSCRIPTION_BRIDGE_MANIFESTS
        if manifest.provider_id in first_wave_ids
    )
    if collisions:
        raise ValueError(
            "subscription bridges must stay distinct from first-wave providers: "
            + collisions[0]
        )

    return _SUBSCRIPTION_BRIDGE_MANIFESTS


def provider_spec_from_manifest(manifest: ProviderManifest) -> ProviderSpec:
    """Project one declarative manifest into a canonical provider definition.

    The projection is deterministic and lossless for the fields the canonical
    authority owns: identity, provider type, API style and base URL. Manifests
    stay the source of billing/auth defaults; ``ProviderSpec`` is the source of
    provider existence, so the bootstrap below registers this spec *first* and
    only then its bound metadata.
    """
    if not isinstance(manifest, ProviderManifest):
        raise TypeError("manifest must be a ProviderManifest")
    return ProviderSpec(
        id=manifest.provider_id,
        provider_type="remote",
        api_style=manifest.api_styles[0],
        base_url=manifest.default_base_url,
    )


def register_first_wave_providers(
    provider_registry: ProviderRegistry,
    manifests: ProviderManifestRegistry,
) -> tuple[ProviderManifest, ...]:
    """Bootstrap canonical provider identity, then bind its manifest metadata.

    Registration order is the authority order: each declared manifest becomes a
    ``ProviderSpec`` in ``provider_registry`` and only then a manifest in the
    provider-bound ``manifests`` catalog, so a first-wave provider can never
    exist as metadata while being absent from the canonical registry (spec §4.3,
    MAJOR-01).

    Returns the manifests in declaration order (plan Task 3, spec §2), so callers
    can render them deterministically without re-sorting.

    Raises ``ValueError`` for an absent argument (``None``), for an empty
    manifest table, and for a missing Qwen subscription/PAYG pair; raises
    ``ProviderError`` when the canonical registry already holds a provider id.
    """
    if provider_registry is None:
        raise ValueError("provider_registry cannot be None")
    if manifests is None:
        raise ValueError("manifests cannot be None")

    declared = _validated_manifests()
    for manifest in declared:
        provider_registry.register(provider_spec_from_manifest(manifest))
        manifests.register(manifest)
    return declared


def register_first_wave_manifests(
    registry: ProviderManifestRegistry,
) -> tuple[ProviderManifest, ...]:
    """Register the first-wave providers through a bound manifest registry.

    Compatibility wrapper that delegates to :func:`register_first_wave_providers`
    using the canonical registry ``registry`` is bound to, so it cannot create
    provider identity outside that authority. Returns the manifests in
    declaration order.
    """
    if registry is None:
        raise ValueError("registry cannot be None")
    return register_first_wave_providers(registry.provider_registry, registry)


def register_subscription_bridge_providers(
    provider_registry: ProviderRegistry,
    manifests: ProviderManifestRegistry,
) -> tuple[ProviderManifest, ...]:
    """Bootstrap the subscription bridges: identity first, then their metadata.

    Same authority order as :func:`register_first_wave_providers` — each declared
    bridge becomes a ``ProviderSpec`` in ``provider_registry`` and only then a
    manifest in the provider-bound ``manifests`` catalog — so a bridge can never
    exist as metadata while being absent from the canonical registry.

    This is a separate bootstrap from the first-wave one on purpose: the eight
    API providers keep their verified contract, and the three bridges carry their
    own ``requires_isolation=True`` policy (MAJOR-V2-03). Returns the manifests in
    declaration order.

    Raises ``ValueError`` for an absent argument (``None``), for an empty bridge
    table, for a bridge declared without the isolation policy, and for a bridge
    id that collides with a first-wave provider; raises ``ProviderError`` when
    the canonical registry already holds one of the bridge ids.
    """
    if provider_registry is None:
        raise ValueError("provider_registry cannot be None")
    if manifests is None:
        raise ValueError("manifests cannot be None")

    declared = _validated_subscription_bridge_manifests()
    for manifest in declared:
        provider_registry.register(provider_spec_from_manifest(manifest))
        manifests.register(manifest)
    return declared
