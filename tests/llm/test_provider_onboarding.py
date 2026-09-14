"""Hybrid provider onboarding tests (Plan 3 Task 5).

Detect is not connect: ``propose()`` resolves a canonical endpoint
and records what acceptance would do, while only ``accept()`` stores
secrets, builds isolation profiles, and mutates the registry.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import pytest

from kernel.llm.credential_store import InMemoryCredentialStore
from kernel.llm.exceptions import ProviderError
from kernel.llm.first_wave_providers import (
    DEEPSEEK_BASE_URL,
    register_first_wave_manifests,
)
from kernel.llm.model_catalog import ModelCatalog
from kernel.llm.model_routes import ModelRouteCatalog
from kernel.llm.provider_candidates import CandidateRisk, ProviderCandidate
from kernel.llm.provider_connections import (
    BillingClass,
    ConnectionStatus,
    ProviderConnectionRegistry,
)
from kernel.llm.provider_manifests import (
    FIRST_WAVE_AUTH_SCHEME,
    ProviderManifest,
    ProviderManifestRegistry,
)
from kernel.llm.provider_onboarding import (
    ConnectionProposal,
    ProviderIsolationError,
    ProviderOnboardingService,
)
from kernel.llm.provider_registry import ProviderRegistry, ProviderSpec
from kernel.llm.provider_state import ProviderRegistryState
from kernel.llm.provider_state_repository import (
    FileProviderRegistryStateRepository,
    ProviderRegistryStateRepository,
)
from kernel.llm.subscription_profiles import SubscriptionProfileManager

_DECOY_URL = "http://127.0.0.1:9999/v1"
_MARKER = "17841"
_CODEX_MANIFEST_URL = "https://api.openai.com/v1"
_CLAUDE_MANIFEST_URL = "https://api.anthropic.com/v1"
_ANTIGRAVITY_MANIFEST_URL = "https://cloudcode-pa.googleapis.com/v1"
_SECRET = "sk-deepseek-test-secret-value"

# Canonical subscription providers and the documented base URL their manifest
# declares; the connection endpoint always comes from here, never from
# candidate metadata.
_SUBSCRIPTION_MANIFESTS: tuple[tuple[str, str], ...] = (
    ("codex", _CODEX_MANIFEST_URL),
    ("claude-code", _CLAUDE_MANIFEST_URL),
    ("antigravity", _ANTIGRAVITY_MANIFEST_URL),
)


@dataclass(frozen=True, slots=True)
class _Wiring:
    """Test-only bundle of the canonical components one service is wired to."""

    service: ProviderOnboardingService
    providers: ProviderRegistry
    manifests: ProviderManifestRegistry
    connections: ProviderConnectionRegistry
    credentials: InMemoryCredentialStore
    models: ModelCatalog
    routes: ModelRouteCatalog


def _wiring(
    tmp_path: Path,
    validator: Callable[[ConnectionProposal], bool] | None = None,
    *,
    state_repository: ProviderRegistryStateRepository | None = None,
    revision: int = 0,
) -> _Wiring:
    """Build a service wired to fresh registries and an in-memory store."""
    providers = ProviderRegistry()
    manifests = ProviderManifestRegistry(providers)
    register_first_wave_manifests(manifests)
    for provider_id, base_url in _SUBSCRIPTION_MANIFESTS:
        providers.register(
            ProviderSpec(
                id=provider_id,
                provider_type="remote",
                api_style="chat_completions",
                base_url=base_url,
            )
        )
        manifests.register(
            ProviderManifest(
                provider_id=provider_id,
                display_name=provider_id,
                billing_class=BillingClass.SUBSCRIPTION,
                default_base_url=base_url,
                auth_scheme=FIRST_WAVE_AUTH_SCHEME,
            )
        )
    connections = ProviderConnectionRegistry(providers)
    credentials = InMemoryCredentialStore()
    models = ModelCatalog(providers)
    routes = ModelRouteCatalog(connections)
    service = ProviderOnboardingService(
        providers=providers,
        connections=connections,
        manifests=manifests,
        credentials=credentials,
        profiles=SubscriptionProfileManager(),
        profiles_root=tmp_path / "cmm-profiles",
        validator=validator,
        state_repository=state_repository,
        models=models,
        routes=routes,
        revision=revision,
    )
    return _Wiring(
        service=service,
        providers=providers,
        manifests=manifests,
        connections=connections,
        credentials=credentials,
        models=models,
        routes=routes,
    )


def _service(
    tmp_path: Path,
    validator: Callable[[ConnectionProposal], bool] | None = None,
) -> tuple[ProviderOnboardingService, ProviderConnectionRegistry]:
    """Return the service and its connection registry for legacy assertions."""
    wired = _wiring(tmp_path, validator)
    return wired.service, wired.connections


def _deepseek_candidate() -> ProviderCandidate:
    """API candidate carrying a decoy URL that must never become endpoint."""
    return ProviderCandidate(
        provider_id="deepseek",
        source="env-credential",
        detected=True,
        auth_available=True,
        external_config_present=False,
        external_endpoint_override_present=False,
        risks=(),
        metadata=(
            ("env_key", "DEEPSEEK_API_KEY"),
            ("evidence_url", _DECOY_URL),
        ),
    )


def _write_contaminated_source(source: Path) -> None:
    """Mirror a user Codex home with auth plus an override config."""
    source.mkdir(parents=True, exist_ok=True)
    (source / "auth.json").write_text(
        json.dumps({"openai_api_key": "sub-key"}), encoding="utf-8"
    )
    (source / "config.toml").write_text(
        f'model = "gpt-5"\nopenai_base_url = "http://127.0.0.1:{_MARKER}/v1"\n',
        encoding="utf-8",
    )


def _codex_candidate(source: Path) -> ProviderCandidate:
    """Subscription candidate flagged with an external endpoint override."""
    return ProviderCandidate(
        provider_id="codex",
        source="codex-home",
        detected=True,
        auth_available=True,
        external_config_present=True,
        external_endpoint_override_present=True,
        risks=(CandidateRisk.EXTERNAL_ENDPOINT_OVERRIDE,),
        metadata=_source_home_pair("codex", source),
    )


_ISOLATION_PROVIDER_IDS: tuple[str, ...] = ("codex", "claude-code", "antigravity")

# The provider-specific key each detector keeps as origin evidence; the
# normalized ``source_home`` pair is what onboarding reads.
_SOURCE_HOME_KINDS: dict[str, str] = {
    "codex": "codex_home",
    "claude-code": "claude_home",
    "antigravity": "antigravity_home",
}


def _source_home_pair(
    provider_id: str, source: str | Path
) -> tuple[tuple[str, str], ...]:
    """Build the normalized isolation-evidence pair for one provider."""
    return (
        ("source_home", str(source)),
        ("source_home_kind", _SOURCE_HOME_KINDS[provider_id]),
    )


def _subscription_candidate(
    provider_id: str, source: str | Path | None
) -> ProviderCandidate:
    """Isolation-required candidate, with or without source evidence."""
    metadata = _source_home_pair(provider_id, source) if source is not None else ()
    return ProviderCandidate(
        provider_id=provider_id,
        source="subscription-home",
        detected=True,
        auth_available=True,
        external_config_present=True,
        external_endpoint_override_present=False,
        risks=(CandidateRisk.UNTRUSTED_EXTERNAL_CONFIG,),
        metadata=metadata,
    )


def _write_subscription_source(provider_id: str, root: Path) -> Path:
    """Create a filesystem-safe source home carrying that provider's evidence."""
    marker = {
        "codex": "auth.json",
        "claude-code": ".claude.json",
        "antigravity": "credentials.json",
    }[provider_id]
    source = root / f"{provider_id}-source"
    source.mkdir(parents=True, exist_ok=True)
    (source / marker).write_text("{}\n", encoding="utf-8")
    return source


def test_proposal_is_frozen() -> None:
    """ConnectionProposal carries no mutators; it is evidence, not state."""
    proposal = ConnectionProposal(
        provider_id="deepseek",
        display_name="DeepSeek API",
        billing_class=BillingClass.PAYG,
        endpoint=DEEPSEEK_BASE_URL,
    )
    with pytest.raises(AttributeError):
        proposal.endpoint = _DECOY_URL  # type: ignore[misc]


def test_api_onboarding_stores_secret_and_uses_manifest_endpoint(
    tmp_path: Path,
) -> None:
    """DeepSeek secret lands in the store; endpoint is the manifest URL."""
    service, _ = _service(tmp_path)
    proposal = service.propose(_deepseek_candidate())

    assert proposal.endpoint == DEEPSEEK_BASE_URL
    assert proposal.endpoint != _DECOY_URL
    assert _DECOY_URL not in proposal.endpoint

    connection = service.accept(proposal, credential=_SECRET)

    assert connection.endpoint == DEEPSEEK_BASE_URL
    assert connection.credential_ref is not None
    assert connection.credential_ref.startswith("keychain://")
    assert "sk-" not in connection.credential_ref
    assert _SECRET not in connection.credential_ref
    assert _DECOY_URL not in connection.endpoint
    assert not hasattr(connection, "api_key")
    assert _SECRET not in repr(connection)


def test_contaminated_codex_onboarding_uses_isolation_profile(
    tmp_path: Path,
) -> None:
    """Override config stays behind; connection points at a CMM profile."""
    source = tmp_path / "user-codex"
    _write_contaminated_source(source)
    service, _ = _service(tmp_path)

    proposal = service.propose(_codex_candidate(source))
    connection = service.accept(proposal)

    assert connection.isolation_profile_ref is not None
    assert connection.endpoint == _CODEX_MANIFEST_URL
    assert _MARKER not in connection.endpoint
    assert _MARKER not in connection.isolation_profile_ref

    profile_home = Path(connection.isolation_profile_ref)
    assert profile_home != source
    assert (profile_home / "auth.json").is_file()
    assert not (profile_home / "config.toml").exists()
    hits = [
        path
        for path in sorted(profile_home.rglob("*"))
        if path.is_file() and _MARKER in path.read_text(encoding="utf-8")
    ]
    assert hits == []
    # Source home is evidence only: the override file is untouched.
    assert _MARKER in (source / "config.toml").read_text(encoding="utf-8")


def test_propose_registers_nothing_accept_registers_one(
    tmp_path: Path,
) -> None:
    """Explicit acceptance: propose() is pure, accept() registers exactly one."""
    service, registry = _service(tmp_path)
    candidate = _deepseek_candidate()

    assert registry.list() == ()
    assert registry.get("deepseek:main") is None

    proposal = service.propose(candidate)

    assert registry.list() == ()
    assert registry.get("deepseek:main") is None

    connection = service.accept(proposal, credential=_SECRET)

    assert registry.list() == (connection,)
    assert registry.get("deepseek:main") == connection


def test_status_without_validation_is_never_connected(tmp_path: Path) -> None:
    """No validation hook means AUTH_REQUIRED (or WARNING), never CONNECTED."""
    service, _ = _service(tmp_path)
    api_connection = service.accept(
        service.propose(_deepseek_candidate()), credential=_SECRET
    )
    assert api_connection.status == ConnectionStatus.AUTH_REQUIRED

    source = tmp_path / "user-codex"
    _write_contaminated_source(source)
    override_connection = service.accept(service.propose(_codex_candidate(source)))
    assert override_connection.status == ConnectionStatus.WARNING


def test_status_with_successful_validation_is_connected(
    tmp_path: Path,
) -> None:
    """A passing administrative validation promotes the status to CONNECTED."""
    service, _ = _service(tmp_path, validator=lambda proposal: True)
    connection = service.accept(
        service.propose(_deepseek_candidate()), credential=_SECRET
    )
    assert connection.status == ConnectionStatus.CONNECTED


def test_failed_validation_is_never_connected(tmp_path: Path) -> None:
    """A failing validation keeps the connection out of CONNECTED."""
    service, _ = _service(tmp_path, validator=lambda proposal: False)
    connection = service.accept(
        service.propose(_deepseek_candidate()), credential=_SECRET
    )
    assert connection.status != ConnectionStatus.CONNECTED


@pytest.mark.parametrize("provider_id", _ISOLATION_PROVIDER_IDS)
def test_propose_reads_normalized_source_home_for_every_provider(
    tmp_path: Path, provider_id: str
) -> None:
    """One normalized onboarding input serves all three subscription providers."""
    source = _write_subscription_source(provider_id, tmp_path)
    wired = _wiring(tmp_path)

    proposal = wired.service.propose(_subscription_candidate(provider_id, source))

    assert proposal.source_home == str(source)
    assert proposal.requires_isolation is True


@pytest.mark.parametrize("provider_id", _ISOLATION_PROVIDER_IDS)
def test_missing_source_evidence_can_never_reach_connected(
    tmp_path: Path, provider_id: str
) -> None:
    """A passing validator cannot override a missing isolation prerequisite."""
    wired = _wiring(tmp_path, validator=lambda proposal: True)

    with pytest.raises(ProviderIsolationError, match="source"):
        wired.service.accept(
            wired.service.propose(_subscription_candidate(provider_id, None))
        )

    assert wired.connections.list() == ()


@pytest.mark.parametrize("provider_id", _ISOLATION_PROVIDER_IDS)
def test_failed_isolation_creation_can_never_reach_connected(
    tmp_path: Path, provider_id: str
) -> None:
    """A source that carries no usable evidence fails closed, not open."""
    missing = tmp_path / "absent-source"
    wired = _wiring(tmp_path, validator=lambda proposal: True)

    with pytest.raises(ProviderIsolationError):
        wired.service.accept(
            wired.service.propose(_subscription_candidate(provider_id, missing))
        )

    assert wired.connections.list() == ()
    assert not (tmp_path / "cmm-profiles" / provider_id).exists()


@pytest.mark.parametrize("provider_id", _ISOLATION_PROVIDER_IDS)
def test_successful_isolation_is_required_before_connected(
    tmp_path: Path, provider_id: str
) -> None:
    """Real evidence flows through the profile manager into a CMM-owned home."""
    source = _write_subscription_source(provider_id, tmp_path)
    wired = _wiring(tmp_path, validator=lambda proposal: True)

    connection = wired.service.accept(
        wired.service.propose(_subscription_candidate(provider_id, source))
    )

    assert connection.status == ConnectionStatus.CONNECTED
    assert connection.isolation_profile_ref is not None
    profile_home = Path(connection.isolation_profile_ref)
    assert profile_home.is_dir()
    assert profile_home != source
    assert tmp_path in profile_home.parents
    # Evidence is not authority: the external home is never modified.
    assert (source / _source_marker(provider_id)).is_file()


def _source_marker(provider_id: str) -> str:
    """Return the auth marker filename that provider's detector requires."""
    return {
        "codex": "auth.json",
        "claude-code": ".claude.json",
        "antigravity": "credentials.json",
    }[provider_id]


def test_isolated_provider_without_validation_stays_out_of_connected(
    tmp_path: Path,
) -> None:
    """Isolation alone is not connection authority; validation still gates it."""
    source = _write_subscription_source("claude-code", tmp_path)
    wired = _wiring(tmp_path)

    connection = wired.service.accept(
        wired.service.propose(_subscription_candidate("claude-code", source))
    )

    assert connection.status == ConnectionStatus.WARNING
    assert connection.status != ConnectionStatus.CONNECTED
    assert connection.isolation_profile_ref is not None


def test_propose_requires_canonical_provider_authority(tmp_path: Path) -> None:
    """Stale manifest metadata cannot authorize a de-registered provider."""
    wired = _wiring(tmp_path)
    wired.providers.remove("deepseek")

    with pytest.raises(ProviderError, match="Unknown registered provider"):
        wired.service.propose(_deepseek_candidate())

    # The metadata is genuinely still present: only authority was withdrawn.
    assert wired.manifests.get("deepseek") is not None
    assert wired.connections.list() == ()


def test_propose_rejects_a_candidate_without_metadata(tmp_path: Path) -> None:
    """Canonical identity without manifest metadata is not onboardable."""
    wired = _wiring(tmp_path)
    wired.providers.register(
        ProviderSpec(
            id="not-declared",
            provider_type="remote",
            api_style="chat_completions",
            base_url="https://not-declared.example/v1",
        )
    )
    candidate = ProviderCandidate(
        provider_id="not-declared",
        source="env-credential",
        detected=True,
        auth_available=True,
        external_config_present=False,
        external_endpoint_override_present=False,
        risks=(),
        metadata=(("env_key", "NOT_DECLARED_API_KEY"),),
    )

    with pytest.raises(ValueError, match="unknown provider: not-declared"):
        wired.service.propose(candidate)


# --- atomic acceptance (MAJOR-04) -------------------------------------------


class _ExplodingStateRepository:
    """Repository whose save always fails without mutating stored state."""

    def __init__(self, state: ProviderRegistryState | None = None) -> None:
        self._state = state

    def load(self) -> ProviderRegistryState | None:
        return self._state

    def save(self, state: ProviderRegistryState) -> None:
        raise RuntimeError("persistence failed")


def test_duplicate_accept_does_not_overwrite_existing_secret(
    tmp_path: Path,
) -> None:
    """The exact Audit V1 reproduction: a failed duplicate mutates nothing."""
    wired = _wiring(tmp_path)

    first = wired.service.accept(
        wired.service.propose(_deepseek_candidate()),
        credential="secret-one",
    )
    before = dict(wired.credentials._secrets)

    with pytest.raises(ValueError, match="duplicate connection_id"):
        wired.service.accept(
            wired.service.propose(_deepseek_candidate()),
            credential="secret-two",
        )

    assert wired.connections.list() == (first,)
    assert wired.credentials._secrets == before


def test_accept_persists_the_aggregate_and_advances_revision(
    tmp_path: Path,
) -> None:
    """A successful acceptance advances the durable revision by exactly one."""
    repository = FileProviderRegistryStateRepository(tmp_path / "state.json")
    wired = _wiring(tmp_path, state_repository=repository)

    connection = wired.service.accept(
        wired.service.propose(_deepseek_candidate()), credential=_SECRET
    )

    persisted = repository.load()
    assert persisted is not None
    assert persisted.revision == 1
    assert wired.service.revision == 1
    assert tuple(item.connection_id for item in persisted.connections) == (
        connection.connection_id,
    )
    assert persisted.audit_log[-1].entity_id == connection.connection_id
    assert _SECRET not in (tmp_path / "state.json").read_text(encoding="utf-8")


def test_failed_duplicate_accept_does_not_advance_persisted_revision(
    tmp_path: Path,
) -> None:
    """Revision 5 stays revision 5 — bytes included — after a failed accept."""
    repository = FileProviderRegistryStateRepository(tmp_path / "state.json")
    wired = _wiring(tmp_path, state_repository=repository)
    wired.service.accept(
        wired.service.propose(_deepseek_candidate()), credential="secret-one"
    )
    assert wired.service.revision == 1
    before = (tmp_path / "state.json").read_bytes()

    with pytest.raises(ValueError, match="duplicate connection_id"):
        wired.service.accept(
            wired.service.propose(_deepseek_candidate()), credential="secret-two"
        )

    assert wired.service.revision == 1
    assert (tmp_path / "state.json").read_bytes() == before
    assert repository.load().revision == 1


def test_persistence_failure_compensates_credential_and_connection(
    tmp_path: Path,
) -> None:
    """A failed save rolls back this call's credential and connection."""
    wired = _wiring(tmp_path, state_repository=_ExplodingStateRepository())

    with pytest.raises(RuntimeError, match="persistence failed"):
        wired.service.accept(
            wired.service.propose(_deepseek_candidate()), credential=_SECRET
        )

    assert wired.connections.list() == ()
    assert wired.credentials._secrets == {}
    assert wired.service.revision == 0


def test_persistence_failure_compensates_the_new_isolation_profile(
    tmp_path: Path,
) -> None:
    """Only the profile this call created is removed; the source is untouched."""
    source = _write_subscription_source("codex", tmp_path)
    wired = _wiring(tmp_path, state_repository=_ExplodingStateRepository())
    profile_target = tmp_path / "cmm-profiles" / "codex"

    with pytest.raises(RuntimeError, match="persistence failed"):
        wired.service.accept(
            wired.service.propose(_subscription_candidate("codex", source))
        )

    assert not profile_target.exists()
    assert wired.connections.list() == ()
    assert (source / "auth.json").is_file()


def test_persistence_failure_keeps_a_preexisting_profile_directory(
    tmp_path: Path,
) -> None:
    """Compensation must never delete a directory this call did not create."""
    source = _write_subscription_source("codex", tmp_path)
    profile_target = tmp_path / "cmm-profiles" / "codex"
    profile_target.mkdir(parents=True)
    marker = profile_target / "keep-me.txt"
    marker.write_text("preexisting", encoding="utf-8")
    wired = _wiring(tmp_path, state_repository=_ExplodingStateRepository())

    with pytest.raises(RuntimeError, match="persistence failed"):
        wired.service.accept(
            wired.service.propose(_subscription_candidate("codex", source))
        )

    assert marker.read_text(encoding="utf-8") == "preexisting"


def test_state_repository_requires_models_and_routes(tmp_path: Path) -> None:
    """Persistence wiring without catalogs is a construction error."""
    providers = ProviderRegistry()
    manifests = ProviderManifestRegistry(providers)
    register_first_wave_manifests(manifests)
    connections = ProviderConnectionRegistry(providers)
    with pytest.raises(TypeError, match="models and routes"):
        ProviderOnboardingService(
            providers=providers,
            connections=connections,
            manifests=manifests,
            credentials=InMemoryCredentialStore(),
            profiles=SubscriptionProfileManager(),
            profiles_root=tmp_path / "cmm-profiles",
            state_repository=_ExplodingStateRepository(),
        )
