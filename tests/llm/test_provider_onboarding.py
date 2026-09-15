"""Hybrid provider onboarding tests (Plan 3 Task 5).

Detect is not connect: ``propose()`` resolves a canonical endpoint
and records what acceptance would do, while only ``accept()`` stores
secrets, builds isolation profiles, and mutates the registry.
"""

from __future__ import annotations

import json
import shutil
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import pytest

from kernel.llm.credential_store import InMemoryCredentialStore, credential_ref
from kernel.llm.exceptions import ProviderError
from kernel.llm.first_wave_providers import (
    DEEPSEEK_BASE_URL,
    register_first_wave_manifests,
    register_subscription_bridge_providers,
)
from kernel.llm.model_catalog import ModelCatalog
from kernel.llm.model_routes import ModelRouteCatalog
from kernel.llm.provider_candidates import CandidateRisk, ProviderCandidate
from kernel.llm.provider_connections import (
    BillingClass,
    ConnectionStatus,
    ProviderConnectionRegistry,
)
from kernel.llm.provider_detectors import (
    AntigravityDetector,
    ClaudeCodeDetector,
    CodexDetector,
)
from kernel.llm.provider_manifests import ProviderManifest, ProviderManifestRegistry
from kernel.llm.provider_onboarding import (
    ConnectionProposal,
    ProviderIsolationError,
    ProviderOnboardingRollbackError,
    ProviderOnboardingService,
)
from kernel.llm.provider_registry import ProviderRegistry, ProviderSpec
from kernel.llm.provider_state import (
    ProviderRegistryState,
    ProviderStateCoherenceError,
)
from kernel.llm.provider_state_coordinator import ProviderRegistryStateCoordinator
from kernel.llm.provider_state_repository import (
    FileProviderRegistryStateRepository,
    ProviderRegistryStateRepository,
)
from kernel.llm.subscription_profiles import SubscriptionProfileManager

_DECOY_URL = "http://127.0.0.1:9999/v1"
_MARKER = "17841"
# Canonical subscription endpoints, pinned here to the values the production
# declaration must carry (MAJOR-V2-03). The connection endpoint always comes
# from the canonical manifest, never from candidate metadata.
_CODEX_MANIFEST_URL = "https://api.openai.com/v1"
_CLAUDE_MANIFEST_URL = "https://api.anthropic.com/v1"
_ANTIGRAVITY_MANIFEST_URL = "https://cloudcode-pa.googleapis.com/v1"
_SECRET = "sk-deepseek-test-secret-value"

_SUBSCRIPTION_MANIFEST_URLS: dict[str, str] = {
    "codex": _CODEX_MANIFEST_URL,
    "claude-code": _CLAUDE_MANIFEST_URL,
    "antigravity": _ANTIGRAVITY_MANIFEST_URL,
}


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
    coordinator: ProviderRegistryStateCoordinator | None


def _wiring(
    tmp_path: Path,
    validator: Callable[[ConnectionProposal], bool] | None = None,
    *,
    repository: ProviderRegistryStateRepository | None = None,
    credentials: InMemoryCredentialStore | None = None,
) -> _Wiring:
    """Build a service wired to fresh registries and an in-memory store.

    Durable wiring goes through one coordinator: the repository is owned by the
    coordinator, never by the service (MAJOR-V2-02). Provider identity and
    manifest metadata come from the canonical bootstraps — the eight first-wave
    providers plus the three subscription bridges — never from test-local
    declarations (MAJOR-V2-03). ``credentials`` is injectable so an adversary
    can pin behaviour of the official in-memory store.
    """
    providers = ProviderRegistry()
    manifests = ProviderManifestRegistry(providers)
    register_first_wave_manifests(manifests)
    register_subscription_bridge_providers(providers, manifests)
    connections = ProviderConnectionRegistry(providers)
    credentials = credentials if credentials is not None else InMemoryCredentialStore()
    models = ModelCatalog(providers)
    routes = ModelRouteCatalog(connections)
    coordinator = (
        None
        if repository is None
        else ProviderRegistryStateCoordinator(
            providers=providers,
            manifests=manifests,
            models=models,
            connections=connections,
            routes=routes,
            repository=repository,
        )
    )
    service = ProviderOnboardingService(
        providers=providers,
        connections=connections,
        manifests=manifests,
        credentials=credentials,
        profiles=SubscriptionProfileManager(),
        profiles_root=tmp_path / "cmm-profiles",
        validator=validator,
        state_coordinator=coordinator,
    )
    return _Wiring(
        service=service,
        providers=providers,
        manifests=manifests,
        connections=connections,
        credentials=credentials,
        models=models,
        routes=routes,
        coordinator=coordinator,
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


# --- auth-only subscription adversaries (MAJOR-V2-03) -----------------------


# The auth marker each approved subscription detector reports as evidence, and
# the config marker it treats as an external configuration file. The
# adversaries below write ONLY the auth marker.
_AUTH_ONLY_MARKERS: dict[str, str] = {
    "codex": "auth.json",
    "claude-code": ".claude.json",
    "antigravity": "credentials.json",
}

_FORBIDDEN_CONFIG_MARKERS: dict[str, str] = {
    "codex": "config.toml",
    "claude-code": "settings.json",
    "antigravity": "config.json",
}


def _write_auth_only_source(provider_id: str, root: Path) -> Path:
    """Write only that provider's auth marker; never a config marker."""
    source = root / f"{provider_id}-auth-only"
    source.mkdir(parents=True, exist_ok=True)
    (source / _AUTH_ONLY_MARKERS[provider_id]).write_text("{}\n", encoding="utf-8")
    assert not (source / _FORBIDDEN_CONFIG_MARKERS[provider_id]).exists()
    return source


def _real_subscription_detector(provider_id: str, source: Path):
    """Return the real approved detector for one subscription provider."""
    if provider_id == "codex":
        return CodexDetector(codex_home=source)
    if provider_id == "claude-code":
        return ClaudeCodeDetector(claude_home=source)
    return AntigravityDetector(config_dir=source)


@pytest.mark.parametrize("provider_id", _ISOLATION_PROVIDER_IDS)
def test_auth_only_subscription_proposal_still_requires_isolation(
    tmp_path: Path, provider_id: str
) -> None:
    """Canonical manifest policy — not observed config — requires isolation.

    The Audit V2 §7.3 reproduction, with the real detectors: authentication
    evidence and no config marker, so the candidate reports
    ``external_config_present=False`` while the canonical policy still demands a
    CMM-owned isolation outcome.
    """
    source = _write_auth_only_source(provider_id, tmp_path)
    candidate = _real_subscription_detector(provider_id, source).detect()

    assert candidate.detected is True
    assert candidate.auth_available is True
    assert candidate.external_config_present is False
    assert candidate.external_endpoint_override_present is False

    proposal = _wiring(tmp_path, validator=lambda proposal: True).service.propose(
        candidate
    )

    assert proposal.source_home == str(source)
    assert proposal.requires_isolation is True
    assert proposal.endpoint == _SUBSCRIPTION_MANIFEST_URLS[provider_id]


@pytest.mark.parametrize("provider_id", _ISOLATION_PROVIDER_IDS)
def test_auth_only_subscription_is_connected_only_with_a_cmm_owned_profile(
    tmp_path: Path, provider_id: str
) -> None:
    """A passing validator still requires the CMM-owned profile first."""
    source = _write_auth_only_source(provider_id, tmp_path)
    wired = _wiring(tmp_path, validator=lambda proposal: True)
    candidate = _real_subscription_detector(provider_id, source).detect()
    profiles_root = tmp_path / "cmm-profiles"

    connection = wired.service.accept(wired.service.propose(candidate))

    assert connection.status == ConnectionStatus.CONNECTED
    assert connection.isolation_profile_ref is not None
    profile_home = Path(connection.isolation_profile_ref)
    assert profile_home.is_dir()
    assert profile_home != source
    assert profile_home.is_relative_to(profiles_root)
    # Evidence is not authority: the external home is never modified.
    assert (source / _AUTH_ONLY_MARKERS[provider_id]).is_file()


@pytest.mark.parametrize("provider_id", _ISOLATION_PROVIDER_IDS)
def test_auth_only_subscription_never_connects_when_isolation_fails(
    tmp_path: Path, provider_id: str
) -> None:
    """Auth evidence alone is not connection authority; a failed build closes."""
    source = _write_auth_only_source(provider_id, tmp_path)
    wired = _wiring(tmp_path, validator=lambda proposal: True)
    candidate = _real_subscription_detector(provider_id, source).detect()
    proposal = wired.service.propose(candidate)
    assert proposal.requires_isolation is True

    # The evidence home disappears between detection and acceptance.
    shutil.rmtree(source)

    with pytest.raises(ProviderIsolationError):
        wired.service.accept(proposal)

    assert wired.connections.list() == ()
    assert not (tmp_path / "cmm-profiles" / provider_id).exists()


def test_propose_requires_canonical_provider_authority(tmp_path: Path) -> None:
    """Stale manifest metadata cannot authorize a de-registered provider."""
    wired = _wiring(tmp_path)
    wired.providers.remove("deepseek")

    with pytest.raises(ProviderError, match="Unknown registered provider"):
        wired.service.propose(_deepseek_candidate())

    # MAJOR-V2-01: metadata cannot outlive canonical identity — the stale
    # manifest is not merely unauthorized, it is no longer active at all.
    assert wired.manifests.get("deepseek") is None
    assert "deepseek" not in {item.provider_id for item in wired.manifests.list()}
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
        self.save_calls = 0

    def load(self) -> ProviderRegistryState | None:
        return self._state

    def save(self, state: ProviderRegistryState) -> None:
        self.save_calls += 1
        raise RuntimeError("persistence failed")


class _RecordingStateRepository:
    """Repository that records every saved state and counts the saves."""

    def __init__(self) -> None:
        self.save_calls = 0
        self.saved: list[ProviderRegistryState] = []

    def load(self) -> ProviderRegistryState | None:
        return self.saved[-1] if self.saved else None

    def save(self, state: ProviderRegistryState) -> None:
        self.save_calls += 1
        self.saved.append(state)


def test_acceptance_commits_through_the_coordinator(tmp_path: Path) -> None:
    """The service delegates its revision/audit commit to the coordinator."""
    repository = FileProviderRegistryStateRepository(tmp_path / "state.json")
    wired = _wiring(tmp_path, repository=repository)
    coordinator = wired.coordinator
    assert coordinator is not None

    connection = wired.service.accept(
        wired.service.propose(_deepseek_candidate()), credential=_SECRET
    )

    assert coordinator.revision == 1
    assert wired.service.revision == coordinator.revision
    assert len(coordinator.audit_log) == 1
    assert coordinator.audit_log[0].revision == 1
    assert coordinator.audit_log[0].entity_id == connection.connection_id
    persisted = repository.load()
    assert persisted is not None
    assert persisted.audit_log == coordinator.audit_log


def test_acceptance_saves_the_aggregate_exactly_once(tmp_path: Path) -> None:
    """One acceptance, one repository save: no parallel persistence path."""
    repository = _RecordingStateRepository()
    wired = _wiring(tmp_path, repository=repository)

    wired.service.accept(
        wired.service.propose(_deepseek_candidate()), credential=_SECRET
    )

    assert repository.save_calls == 1
    assert len(repository.saved) == 1
    assert repository.saved[0].revision == 1
    assert len(repository.saved[0].audit_log) == 1


def test_service_revision_is_zero_without_a_coordinator(tmp_path: Path) -> None:
    """An ephemeral runtime has no durable revision and commits nothing."""
    wired = _wiring(tmp_path)
    assert wired.coordinator is None

    wired.service.accept(
        wired.service.propose(_deepseek_candidate()), credential=_SECRET
    )

    assert wired.service.revision == 0


def test_service_rejects_a_non_coordinator(tmp_path: Path) -> None:
    """Only the canonical coordinator may own the commit path."""
    providers = ProviderRegistry()
    manifests = ProviderManifestRegistry(providers)
    register_first_wave_manifests(manifests)
    connections = ProviderConnectionRegistry(providers)

    with pytest.raises(TypeError, match="ProviderRegistryStateCoordinator"):
        ProviderOnboardingService(
            providers=providers,
            connections=connections,
            manifests=manifests,
            credentials=InMemoryCredentialStore(),
            profiles=SubscriptionProfileManager(),
            profiles_root=tmp_path / "cmm-profiles",
            state_coordinator=_ExplodingStateRepository(),  # type: ignore[arg-type]
        )


# --- cross-authority construction guards (MAJOR-V3-01) ----------------------


_FOREIGN_URL = "https://foreign-manifest.example/v1"


def _foreign_authority() -> tuple[
    ProviderRegistry, ProviderManifestRegistry, ProviderConnectionRegistry
]:
    """A second live authority carrying the same provider id as the canonical one.

    The audited V3 wiring: two simultaneously live ``ProviderRegistry``
    instances hold ``deepseek``, so provider-id equality alone can never
    satisfy the exact-object graph guards.
    """
    providers = ProviderRegistry()
    providers.register(
        ProviderSpec(
            id="deepseek",
            provider_type="remote",
            api_style="chat_completions",
            base_url=_FOREIGN_URL,
        )
    )
    manifests = ProviderManifestRegistry(providers)
    manifests.register(
        ProviderManifest(
            provider_id="deepseek",
            display_name="Foreign DeepSeek",
            billing_class=BillingClass.PAYG,
            default_base_url=_FOREIGN_URL,
            auth_scheme="bearer",
        )
    )
    connections = ProviderConnectionRegistry(providers)
    return providers, manifests, connections


def test_service_rejects_a_foreign_manifest_registry(tmp_path: Path) -> None:
    """Foreign metadata under another authority is refused before any effect."""
    wired = _wiring(tmp_path)
    _, foreign_manifests, _ = _foreign_authority()
    credentials = InMemoryCredentialStore()
    repository = FileProviderRegistryStateRepository(tmp_path / "state.json")
    assert wired.providers.has("deepseek")
    assert foreign_manifests.get("deepseek") is not None

    with pytest.raises(
        ProviderStateCoherenceError,
        match="manifest registry is bound to a different ProviderRegistry",
    ):
        ProviderOnboardingService(
            providers=wired.providers,
            connections=wired.connections,
            manifests=foreign_manifests,
            credentials=credentials,
            profiles=SubscriptionProfileManager(),
            profiles_root=tmp_path / "cmm-profiles",
            state_coordinator=wired.coordinator,
        )

    # Rejected at construction: no service exists, so no proposal could have been
    # produced from foreign metadata and no side effect was performed.
    assert wired.connections.list() == ()
    assert credentials._secrets == {}
    assert not (tmp_path / "cmm-profiles").exists()
    assert repository.load() is None


def test_service_rejects_a_foreign_connection_registry(tmp_path: Path) -> None:
    """A connection registry resolving through another authority is refused."""
    wired = _wiring(tmp_path)
    _, _, foreign_connections = _foreign_authority()

    with pytest.raises(
        ProviderStateCoherenceError,
        match="connection registry is bound to a different ProviderRegistry",
    ):
        ProviderOnboardingService(
            providers=wired.providers,
            connections=foreign_connections,
            manifests=wired.manifests,
            credentials=InMemoryCredentialStore(),
            profiles=SubscriptionProfileManager(),
            profiles_root=tmp_path / "cmm-profiles",
            state_coordinator=wired.coordinator,
        )

    assert wired.connections.list() == ()
    assert foreign_connections.list() == ()


def test_service_rejects_a_coordinator_for_another_graph(tmp_path: Path) -> None:
    """A coordinator over a different authority is not the same commit seam."""
    wired = _wiring(tmp_path)
    foreign_providers, foreign_manifests, foreign_connections = _foreign_authority()
    foreign_coordinator = ProviderRegistryStateCoordinator(
        providers=foreign_providers,
        manifests=foreign_manifests,
        models=ModelCatalog(foreign_providers),
        connections=foreign_connections,
        routes=ModelRouteCatalog(foreign_connections),
        repository=FileProviderRegistryStateRepository(tmp_path / "state.json"),
    )

    with pytest.raises(
        ProviderStateCoherenceError,
        match="state coordinator is bound to a different ProviderRegistry",
    ):
        ProviderOnboardingService(
            providers=wired.providers,
            connections=wired.connections,
            manifests=wired.manifests,
            credentials=InMemoryCredentialStore(),
            profiles=SubscriptionProfileManager(),
            profiles_root=tmp_path / "cmm-profiles",
            state_coordinator=foreign_coordinator,
        )

    assert wired.connections.list() == ()


def test_service_rejects_a_coordinator_over_a_parallel_manifest_catalog(
    tmp_path: Path,
) -> None:
    """Same authority, different component objects is still not one graph."""
    wired = _wiring(tmp_path)
    parallel_manifests = ProviderManifestRegistry(wired.providers)
    parallel_connections = ProviderConnectionRegistry(wired.providers)
    coordinator = ProviderRegistryStateCoordinator(
        providers=wired.providers,
        manifests=parallel_manifests,
        models=ModelCatalog(wired.providers),
        connections=parallel_connections,
        routes=ModelRouteCatalog(parallel_connections),
        repository=FileProviderRegistryStateRepository(tmp_path / "state.json"),
    )

    with pytest.raises(
        ProviderStateCoherenceError,
        match="state coordinator is bound to a different ProviderManifestRegistry",
    ):
        ProviderOnboardingService(
            providers=wired.providers,
            connections=wired.connections,
            manifests=wired.manifests,
            credentials=InMemoryCredentialStore(),
            profiles=SubscriptionProfileManager(),
            profiles_root=tmp_path / "cmm-profiles",
            state_coordinator=coordinator,
        )


def test_service_rejects_a_coordinator_over_a_parallel_connection_registry(
    tmp_path: Path,
) -> None:
    """Same authority again: a parallel connection registry is a foreign seam."""
    wired = _wiring(tmp_path)
    parallel_connections = ProviderConnectionRegistry(wired.providers)
    coordinator = ProviderRegistryStateCoordinator(
        providers=wired.providers,
        manifests=wired.manifests,
        models=ModelCatalog(wired.providers),
        connections=parallel_connections,
        routes=ModelRouteCatalog(parallel_connections),
        repository=FileProviderRegistryStateRepository(tmp_path / "state.json"),
    )

    with pytest.raises(
        ProviderStateCoherenceError,
        match="state coordinator is bound to a different ProviderConnectionRegistry",
    ):
        ProviderOnboardingService(
            providers=wired.providers,
            connections=wired.connections,
            manifests=wired.manifests,
            credentials=InMemoryCredentialStore(),
            profiles=SubscriptionProfileManager(),
            profiles_root=tmp_path / "cmm-profiles",
            state_coordinator=coordinator,
        )


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
    wired = _wiring(tmp_path, repository=repository)

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
    wired = _wiring(tmp_path, repository=repository)
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
    wired = _wiring(tmp_path, repository=_ExplodingStateRepository())

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
    wired = _wiring(tmp_path, repository=_ExplodingStateRepository())
    profile_target = tmp_path / "cmm-profiles" / "codex"

    with pytest.raises(RuntimeError, match="persistence failed"):
        wired.service.accept(
            wired.service.propose(_subscription_candidate("codex", source))
        )

    assert not profile_target.exists()
    assert wired.connections.list() == ()
    assert (source / "auth.json").is_file()


# --- pre-existing resource ownership (MAJOR-V2-04) --------------------------
# Each adversary pre-creates exactly the resource new-connection acceptance
# would write, then proves the write never happens: no overwrite, no adoption,
# no deletion, no connection and no durable revision.


def test_preexisting_credential_rejects_acceptance_before_any_mutation(
    tmp_path: Path,
) -> None:
    """The Audit V2 §8.3 adversary: an unowned credential is never adopted.

    A new connection may not take ownership of a credential that already
    existed, because a later failure would then delete it. Acceptance fails
    before ``put()``, the stored secret and the connection registry stay as they
    were, and the durable revision never advances.
    """
    repository = FileProviderRegistryStateRepository(tmp_path / "state.json")
    wired = _wiring(tmp_path, repository=repository)
    existing_ref = wired.credentials.put("deepseek", "main", "secret-old")
    secrets_before = dict(wired.credentials._secrets)
    # The adversary occupies the canonical credential namespace, so the ref the
    # service derives for this connection is exactly the pre-existing one.
    assert existing_ref == credential_ref("deepseek", "main")

    with pytest.raises(ValueError, match="credential already exists"):
        wired.service.accept(
            wired.service.propose(_deepseek_candidate()), credential="secret-new"
        )

    assert wired.credentials._secrets == secrets_before
    assert wired.credentials.has(existing_ref)
    assert wired.credentials._secrets[existing_ref] == "secret-old"
    assert wired.connections.list() == ()
    assert wired.service.revision == 0
    assert not (tmp_path / "state.json").exists()


def test_preexisting_isolation_target_rejects_acceptance_before_mutation(
    tmp_path: Path,
) -> None:
    """The Audit V2 §8.4 adversary: pre-existing profile bytes stay identical.

    The previous acceptance reused any existing target home and overwrote
    ``auth.json`` inside it. New-connection acceptance now refuses before the
    profile build: nothing is copied, merged, snapshotted or deleted.
    """
    source = _write_subscription_source("codex", tmp_path)
    target = tmp_path / "cmm-profiles" / "codex"
    target.mkdir(parents=True)
    auth = target / "auth.json"
    auth.write_text("OLD-AUTH", encoding="utf-8")
    marker = target / "keep-me.txt"
    marker.write_text("preexisting", encoding="utf-8")
    auth_before = auth.read_bytes()
    repository = FileProviderRegistryStateRepository(tmp_path / "state.json")
    wired = _wiring(tmp_path, repository=repository)

    with pytest.raises(ValueError, match="isolation profile already exists"):
        wired.service.accept(
            wired.service.propose(_subscription_candidate("codex", source))
        )

    assert auth.read_bytes() == auth_before
    assert marker.read_text(encoding="utf-8") == "preexisting"
    assert sorted(item.name for item in target.iterdir()) == [
        "auth.json",
        "keep-me.txt",
    ]
    assert wired.connections.list() == ()
    assert wired.service.revision == 0
    assert not (tmp_path / "state.json").exists()


@pytest.mark.parametrize("provider_id", ["claude-code", "antigravity"])
def test_preexisting_isolation_target_file_also_rejects_before_mutation(
    tmp_path: Path, provider_id: str
) -> None:
    """Any entry at the target path is pre-existing state, not just a home."""
    source = _write_subscription_source(provider_id, tmp_path)
    target = tmp_path / "cmm-profiles" / provider_id
    target.parent.mkdir(parents=True)
    target.write_text("occupied\n", encoding="utf-8")
    wired = _wiring(tmp_path)

    with pytest.raises(ValueError, match="isolation profile already exists"):
        wired.service.accept(
            wired.service.propose(_subscription_candidate(provider_id, source))
        )

    assert target.read_text(encoding="utf-8") == "occupied\n"
    assert wired.connections.list() == ()


def test_an_owned_credential_is_still_deleted_by_compensation(tmp_path: Path) -> None:
    """Ownership preflight keeps compensation working for this call's credential."""
    wired = _wiring(tmp_path, repository=_ExplodingStateRepository())

    with pytest.raises(RuntimeError, match="persistence failed"):
        wired.service.accept(
            wired.service.propose(_deepseek_candidate()), credential=_SECRET
        )

    assert wired.credentials._secrets == {}
    assert not wired.credentials.has("keychain://cmm/providers/deepseek/main")


class _FailingDeleteCredentialStore(InMemoryCredentialStore):
    """Official in-memory store whose cleanup path fails on purpose."""

    def delete(self, ref: str) -> None:
        """Fail the cleanup to prove a partial rollback is made visible."""
        raise OSError("keychain delete unavailable")


def test_rollback_failure_is_visible_without_masking_the_original_error(
    tmp_path: Path,
) -> None:
    """A failed cleanup raises a focused error with the original failure as cause."""
    wired = _wiring(
        tmp_path,
        repository=_ExplodingStateRepository(),
        credentials=_FailingDeleteCredentialStore(),
    )

    with pytest.raises(ProviderOnboardingRollbackError) as excinfo:
        wired.service.accept(
            wired.service.propose(_deepseek_candidate()), credential=_SECRET
        )

    error = excinfo.value
    assert isinstance(error.__cause__, RuntimeError)
    assert "persistence failed" in str(error.__cause__)
    # The failure names what could not be cleaned up...
    assert "credential" in str(error)
    assert "keychain delete unavailable" in str(error)
    # ...and never secret material, only the opaque ref.
    assert _SECRET not in str(error)
    assert _SECRET not in repr(error)
    assert "keychain://cmm/providers/deepseek/main" in str(error)
    # The connection was still compensated, and no durable state was written.
    assert wired.connections.list() == ()


def test_service_has_no_parallel_persistence_configuration(tmp_path: Path) -> None:
    """The pre-coordinator wiring surface is gone, not merely deprecated.

    MAJOR-V2-02: ``state_repository``/``models``/``routes``/``revision``/
    ``audit_log`` are no longer constructor parameters — a caller cannot wire a
    second commit path next to the coordinator (``models`` and ``routes`` are
    always required by the coordinator instead of conditionally by the service).
    """
    providers = ProviderRegistry()
    manifests = ProviderManifestRegistry(providers)
    register_first_wave_manifests(manifests)
    connections = ProviderConnectionRegistry(providers)

    with pytest.raises(TypeError):
        ProviderOnboardingService(
            providers=providers,
            connections=connections,
            manifests=manifests,
            credentials=InMemoryCredentialStore(),
            profiles=SubscriptionProfileManager(),
            profiles_root=tmp_path / "cmm-profiles",
            state_repository=_ExplodingStateRepository(),  # type: ignore[call-arg]
        )
