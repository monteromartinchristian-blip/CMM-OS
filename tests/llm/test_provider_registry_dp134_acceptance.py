"""Connected acceptance for DP-134 — canonical, persistent, fail-closed registry.

``AT-DP-134`` exercises the real canonical components (or their official
in-memory implementations) end to end — no isolated mocks stand in for the
provider authority, the persistence repository, the isolation machinery or the
discovery path. Scenarios A–M map one-to-one to the Design Point statement in
``docs/superpowers/specs/2026-09-14-phase-11.34-provider-registry-remediation-v1-design.md``
§10.

The final section carries the Remediation V2 adversaries Independent Re-audit V2
required (``docs/audits/phase-11.34-provider-registry-independent-reaudit-v2.md``):
manifest non-divergence, route/validation audit persistence through the
coordinator, auth-only subscription isolation with the real detectors,
pre-existing credential/profile ownership, and the Phase 11 requirements-matrix
traceability checkpoint.

The only fakes allowed are boundary fakes required for a hermetic run: an
injected detector environment, injected filesystem homes under ``tmp_path``,
the official in-memory credential store, and a recording discovery client that
exposes only ``list_models()`` where network access would otherwise occur.
"""

from __future__ import annotations

import dataclasses
import json
import shutil
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import pytest

from kernel.llm.credential_store import InMemoryCredentialStore, credential_ref
from kernel.llm.exceptions import ProviderError
from kernel.llm.first_wave_providers import (
    provider_spec_from_manifest,
    register_first_wave_providers,
    register_subscription_bridge_providers,
)
from kernel.llm.model_catalog import ModelCatalog, ModelSpec
from kernel.llm.model_discovery import DiscoverableModelClient, discover_models
from kernel.llm.model_routes import (
    CapabilityConfidence,
    ModelRoute,
    ModelRouteCatalog,
    RouteCapabilityState,
)
from kernel.llm.provider_candidates import ProviderCandidate
from kernel.llm.provider_connections import (
    BillingClass,
    ConnectionStatus,
    ProviderConnection,
    ProviderConnectionRegistry,
)
from kernel.llm.provider_detectors import (
    AntigravityDetector,
    ClaudeCodeDetector,
    CodexDetector,
    EnvironmentApiCredentialDetector,
)
from kernel.llm.provider_events import (
    ProviderInventorySnapshot,
    build_inventory_snapshot,
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
from kernel.llm.provider_state import (
    ProviderRegistryState,
    ProviderStateCoherenceError,
    ProviderStateSchemaError,
    ProviderStateSerializationError,
)
from kernel.llm.provider_state_coordinator import ProviderRegistryStateCoordinator
from kernel.llm.provider_state_repository import (
    FileProviderRegistryStateRepository,
    ProviderRegistryStateRepository,
    capture_provider_registry_state,
    restore_provider_registry_state,
)
from kernel.llm.subscription_profiles import SubscriptionProfileManager

T0 = datetime(2026, 9, 14, 10, 0, tzinfo=timezone.utc)
T1 = datetime(2026, 9, 14, 12, 0, tzinfo=timezone.utc)
T2 = datetime(2026, 9, 14, 14, 0, tzinfo=timezone.utc)

_SECRET = "sk-deepseek-test-secret-value"

# Canonical subscription bridge endpoints (MAJOR-V2-03). Identity, metadata and
# these endpoints come from the production declaration
# (``register_subscription_bridge_providers``); the mapping below only pins the
# values the acceptance expects that declaration to carry.
_SUBSCRIPTION_BRIDGE_ENDPOINTS: dict[str, str] = {
    "codex": "https://api.openai.com/v1",
    "claude-code": "https://api.anthropic.com/v1",
    "antigravity": "https://cloudcode-pa.googleapis.com/v1",
}

# The auth marker each subscription detector requires (presence-only).
_SUBSCRIPTION_AUTH_MARKERS: dict[str, str] = {
    "codex": "auth.json",
    "claude-code": ".claude.json",
    "antigravity": "credentials.json",
}

# The config marker that makes the detector report external config presence,
# which in turn marks the proposal as isolation-required.
_SUBSCRIPTION_CONFIG_MARKERS: dict[str, str] = {
    "codex": "config.toml",
    "claude-code": "settings.json",
    "antigravity": "config.json",
}


@dataclass(frozen=True, slots=True)
class _Runtime:
    """The canonical component graph one scenario wires together."""

    service: ProviderOnboardingService
    providers: ProviderRegistry
    manifests: ProviderManifestRegistry
    models: ModelCatalog
    connections: ProviderConnectionRegistry
    routes: ModelRouteCatalog
    credentials: InMemoryCredentialStore
    profiles_root: Path
    coordinator: ProviderRegistryStateCoordinator | None


def _runtime(
    tmp_path: Path,
    *,
    repository: ProviderRegistryStateRepository | None = None,
    validator: Callable[[ConnectionProposal], bool] | None = None,
) -> _Runtime:
    """Build the full canonical runtime: one authority, one persistence seam.

    Both provider categories come from their canonical declarations — the eight
    first-wave API providers and the three subscription bridges — so the runtime
    carries no test-local provider or manifest fabrication.
    """
    providers = ProviderRegistry()
    manifests = ProviderManifestRegistry(providers)
    register_first_wave_providers(providers, manifests)
    register_subscription_bridge_providers(providers, manifests)
    connections = ProviderConnectionRegistry(providers)
    models = ModelCatalog(providers)
    routes = ModelRouteCatalog(connections)
    credentials = InMemoryCredentialStore()
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
    return _Runtime(
        service=service,
        providers=providers,
        manifests=manifests,
        models=models,
        connections=connections,
        routes=routes,
        credentials=credentials,
        profiles_root=tmp_path / "cmm-profiles",
        coordinator=coordinator,
    )


def _api_candidate(provider_id: str) -> ProviderCandidate:
    """API credential evidence for one first-wave provider."""
    return ProviderCandidate(
        provider_id=provider_id,
        source="env-credential",
        detected=True,
        auth_available=True,
        external_config_present=False,
        external_endpoint_override_present=False,
        risks=(),
        metadata=(("env_key", f"{provider_id.upper().replace('-', '_')}_API_KEY"),),
    )


def _write_subscription_source(provider_id: str, root: Path) -> Path:
    """A filesystem-safe subscription home with auth plus benign config."""
    source = root / f"{provider_id}-source"
    source.mkdir(parents=True, exist_ok=True)
    (source / _SUBSCRIPTION_AUTH_MARKERS[provider_id]).write_text(
        "{}\n", encoding="utf-8"
    )
    (source / _SUBSCRIPTION_CONFIG_MARKERS[provider_id]).write_text(
        "benign-config\n", encoding="utf-8"
    )
    return source


def _subscription_detector(provider_id: str, source: Path):
    """The real detector for one subscription provider."""
    if provider_id == "codex":
        return CodexDetector(codex_home=source)
    if provider_id == "claude-code":
        return ClaudeCodeDetector(claude_home=source)
    return AntigravityDetector(config_dir=source)


def _connect_deepseek(runtime: _Runtime) -> ProviderConnection:
    """Accept the DeepSeek API candidate and return the connection."""
    return runtime.service.accept(
        runtime.service.propose(_api_candidate("deepseek")),
        credential=_SECRET,
    )


# --- Scenario A: single provider authority --------------------------------


def test_scenario_a_single_provider_authority() -> None:
    """First-wave identities exist canonically; metadata cannot diverge."""
    providers = ProviderRegistry()
    manifests = ProviderManifestRegistry(providers)

    registered = register_first_wave_providers(providers, manifests)

    assert tuple(spec.id for spec in providers.list()) == tuple(
        sorted(manifest.provider_id for manifest in registered)
    )
    assert {m.provider_id for m in manifests.list()} == {
        spec.id for spec in providers.list()
    }
    assert len(providers.list()) == 8

    # No divergent second inventory: manifest metadata cannot create identity.
    rogue = ProviderManifest(
        provider_id="rogue-provider",
        display_name="Rogue",
        billing_class=BillingClass.API,
        default_base_url="https://rogue.example/v1",
        auth_scheme=FIRST_WAVE_AUTH_SCHEME,
    )
    with pytest.raises(ProviderError, match="Unknown registered provider"):
        manifests.register(rogue)
    assert not providers.has("rogue-provider")
    assert manifests.get("rogue-provider") is None

    # ModelCatalog resolves models through the same authority instance.
    models = ModelCatalog(providers)
    models.register(ModelSpec(id="deepseek-chat", provider_id="deepseek"))
    with pytest.raises(ProviderError, match="Unknown registered provider"):
        models.register(ModelSpec(id="rogue-model", provider_id="rogue-provider"))
    assert models.get("deepseek-chat", provider_id="deepseek").id == "deepseek-chat"


# --- Scenario B: Qwen route/account separation -----------------------------


def test_scenario_b_qwen_subscription_and_payg_stay_distinct(
    tmp_path: Path,
) -> None:
    """Same model, two Qwen surfaces: identities and routes never collapse."""
    runtime = _runtime(tmp_path)

    subscription = runtime.service.accept(
        runtime.service.propose(_api_candidate("qwen-token-plan")),
        credential="qwen-subscription-secret",
    )
    payg = runtime.service.accept(
        runtime.service.propose(_api_candidate("qwen-cloud")),
        credential="qwen-payg-secret",
    )

    assert subscription.provider_id != payg.provider_id
    assert subscription.billing_class is BillingClass.SUBSCRIPTION
    assert payg.billing_class is BillingClass.PAYG

    # One canonical model, two provider-specific routes with distinct ids.
    runtime.routes.restore(
        ModelRoute(
            route_id="qwen-token-plan:main:qwen3.8-max",
            connection_id="qwen-token-plan:main",
            provider_model_id="qwen3.8-max",
            canonical_model_id="qwen3.8-max",
        )
    )
    runtime.routes.restore(
        ModelRoute(
            route_id="qwen-cloud:main:qwen/qwen3.8-max",
            connection_id="qwen-cloud:main",
            provider_model_id="qwen/qwen3.8-max",
            canonical_model_id="qwen3.8-max",
        )
    )

    shared = runtime.routes.routes_for_canonical_model("qwen3.8-max")
    assert {route.connection_id for route in shared} == {
        "qwen-token-plan:main",
        "qwen-cloud:main",
    }
    assert {route.provider_model_id for route in shared} == {
        "qwen3.8-max",
        "qwen/qwen3.8-max",
    }

    # The inventory projection keeps both provider surfaces distinct.
    inventory = build_inventory_snapshot(
        runtime.connections.list(), runtime.routes.list()
    )
    assert {item.provider_id for item in inventory.connections} == {
        "qwen-cloud",
        "qwen-token-plan",
    }
    assert [item.provider_id for item in inventory.routes] == [
        "qwen-cloud",
        "qwen-token-plan",
    ]


# --- Scenario C: detect is not connect -------------------------------------


def test_scenario_c_detect_is_not_connect(tmp_path: Path) -> None:
    """A detected candidate stays out of the connection registry until accept."""
    runtime = _runtime(tmp_path)
    detector = EnvironmentApiCredentialDetector(
        provider_id="deepseek",
        env_keys=("DEEPSEEK_API_KEY",),
        env={"DEEPSEEK_API_KEY": _SECRET},
    )

    candidate = detector.detect()

    assert candidate.detected is True
    assert runtime.connections.list() == ()
    runtime.service.propose(candidate)
    assert runtime.connections.list() == ()

    connection = runtime.service.accept(
        runtime.service.propose(candidate), credential=_SECRET
    )

    assert runtime.connections.list() == (connection,)


# --- Scenarios D/E/F: Codex, Claude, Antigravity isolation -----------------


@pytest.mark.parametrize("provider_id", ["codex", "claude-code", "antigravity"])
def test_scenario_def_subscription_isolation_requires_a_cmm_profile(
    tmp_path: Path, provider_id: str
) -> None:
    """Real normalized evidence flows into a CMM-owned profile before CONNECTED."""
    source = _write_subscription_source(provider_id, tmp_path)
    runtime = _runtime(tmp_path, validator=lambda proposal: True)

    candidate = _subscription_detector(provider_id, source).detect()
    assert candidate.detected is True
    metadata = dict(candidate.metadata)
    assert metadata["source_home"] == str(source)
    assert metadata["source_home_kind"].endswith("_home")

    proposal = runtime.service.propose(candidate)
    assert proposal.source_home == str(source)
    assert proposal.requires_isolation is True
    assert proposal.endpoint == _SUBSCRIPTION_BRIDGE_ENDPOINTS[provider_id]

    connection = runtime.service.accept(proposal)

    assert connection.status == ConnectionStatus.CONNECTED
    assert connection.endpoint == _SUBSCRIPTION_BRIDGE_ENDPOINTS[provider_id]
    assert connection.isolation_profile_ref is not None
    profile_home = Path(connection.isolation_profile_ref)
    assert profile_home.is_dir()
    assert runtime.profiles_root in profile_home.parents
    assert profile_home != source
    # Evidence is not authority: the external home is untouched.
    assert (source / _SUBSCRIPTION_AUTH_MARKERS[provider_id]).is_file()
    assert (source / _SUBSCRIPTION_CONFIG_MARKERS[provider_id]).is_file()


# --- Scenario G: fail-closed isolation adversaries -------------------------


def _isolation_candidate(provider_id: str, source: Path | None) -> ProviderCandidate:
    """Direct candidate construction: the Audit V1 reproduction path."""
    metadata = (
        (
            ("source_home", str(source)),
            (
                "source_home_kind",
                {
                    "codex": "codex_home",
                    "claude-code": "claude_home",
                    "antigravity": "antigravity_home",
                }.get(provider_id, f"{provider_id}_home"),
            ),
        )
        if source is not None
        else ()
    )
    return ProviderCandidate(
        provider_id=provider_id,
        source="subscription-home",
        detected=True,
        auth_available=True,
        external_config_present=True,
        external_endpoint_override_present=False,
        risks=(),
        metadata=metadata,
    )


@pytest.mark.parametrize("provider_id", ["codex", "claude-code", "antigravity"])
def test_scenario_g_missing_evidence_never_connects(
    tmp_path: Path, provider_id: str
) -> None:
    """A passing validator cannot override missing isolation evidence."""
    runtime = _runtime(tmp_path, validator=lambda proposal: True)

    with pytest.raises(ProviderIsolationError, match="source"):
        runtime.service.accept(
            runtime.service.propose(_isolation_candidate(provider_id, None))
        )

    assert runtime.connections.list() == ()


@pytest.mark.parametrize("provider_id", ["codex", "claude-code", "antigravity"])
def test_scenario_g_failed_profile_creation_never_connects(
    tmp_path: Path, provider_id: str
) -> None:
    """A source with no usable evidence fails the profile build, not open."""
    runtime = _runtime(tmp_path, validator=lambda proposal: True)
    absent = tmp_path / "absent-source"

    with pytest.raises(ProviderIsolationError):
        runtime.service.accept(
            runtime.service.propose(_isolation_candidate(provider_id, absent))
        )

    assert runtime.connections.list() == ()
    assert not (runtime.profiles_root / provider_id).exists()


def test_scenario_g_unsupported_isolation_never_connects(tmp_path: Path) -> None:
    """A provider the profile manager cannot isolate fails closed."""
    runtime = _runtime(tmp_path, validator=lambda proposal: True)
    runtime.providers.register(
        ProviderSpec(
            id="mystery-subscription",
            provider_type="remote",
            api_style="chat_completions",
            base_url="https://mystery.example/v1",
        )
    )
    runtime.manifests.register(
        ProviderManifest(
            provider_id="mystery-subscription",
            display_name="Mystery",
            billing_class=BillingClass.SUBSCRIPTION,
            default_base_url="https://mystery.example/v1",
            auth_scheme=FIRST_WAVE_AUTH_SCHEME,
        )
    )

    with pytest.raises(ProviderIsolationError, match="unsupported"):
        runtime.service.accept(
            runtime.service.propose(
                _isolation_candidate("mystery-subscription", tmp_path / "home")
            )
        )

    assert runtime.connections.list() == ()


# --- Scenario H: atomic duplicate acceptance -------------------------------


def test_scenario_h_atomic_duplicate_acceptance(tmp_path: Path) -> None:
    """The Audit V1 reproduction: a failed duplicate mutates nothing durable."""
    repository = FileProviderRegistryStateRepository(tmp_path / "state.json")
    runtime = _runtime(tmp_path, repository=repository)

    first = runtime.service.accept(
        runtime.service.propose(_api_candidate("deepseek")),
        credential="secret-one",
    )
    secrets_before = dict(runtime.credentials._secrets)
    bytes_before = (tmp_path / "state.json").read_bytes()

    with pytest.raises(ValueError, match="duplicate connection_id"):
        runtime.service.accept(
            runtime.service.propose(_api_candidate("deepseek")),
            credential="secret-two",
        )

    assert runtime.connections.list() == (first,)
    assert runtime.credentials._secrets == secrets_before
    assert (tmp_path / "state.json").read_bytes() == bytes_before
    assert repository.load().revision == 1
    assert "secret-two" not in (tmp_path / "state.json").read_text(encoding="utf-8")


# --- Scenario I: durable no-secret restart ---------------------------------


class _RecordingClient:
    """Administrative-only transport: lists models, traps inference calls."""

    def __init__(self, models: tuple[str, ...]) -> None:
        self._models = models
        self.inference_calls: list[object] = []
        self.list_calls = 0

    def list_models(self) -> tuple[str, ...]:
        self.list_calls += 1
        return self._models

    def generate(self, **kwargs: object) -> object:
        self.inference_calls.append(kwargs)
        raise AssertionError("inference invoked during administrative discovery")


def test_scenario_i_durable_no_secret_restart(tmp_path: Path) -> None:
    """The aggregate survives a process-equivalent restart without secrets."""
    repository = FileProviderRegistryStateRepository(tmp_path / "state.json")
    runtime = _runtime(tmp_path, repository=repository)
    coordinator = runtime.coordinator
    assert coordinator is not None
    connection = _connect_deepseek(runtime)
    manifest = runtime.manifests.get("deepseek")
    assert manifest is not None

    # Two administrative discovery passes through the coordinator's canonical
    # discovery operation — the one seam that reconciles routes *and* commits
    # the lifecycle audit. Nothing here captures or saves state by hand, so the
    # acceptance proves discovery itself goes through that seam: the second pass
    # omits deepseek-reasoner, so its route stays in the catalog but unavailable
    # with its first-sight history, while the re-advertised deepseek-chat route
    # is durably refreshed (MAJOR-V3-02).
    first_pass = _RecordingClient(("deepseek-chat", "deepseek-reasoner"))
    second_pass = _RecordingClient(("deepseek-chat",))
    coordinator.discover_models(connection, manifest, first_pass, seen_at=T0)
    coordinator.discover_models(connection, manifest, second_pass, seen_at=T1)
    assert first_pass.inference_calls == []
    assert second_pass.inference_calls == []
    vanished = runtime.routes.get("deepseek:main:deepseek-reasoner")
    assert vanished is not None
    assert vanished.available is False
    assert vanished.last_seen_at == T0

    persisted = repository.load()
    assert persisted is not None
    assert persisted.revision == coordinator.revision == 3
    assert [record.event_type for record in persisted.audit_log] == [
        # no validator is wired, so this acceptance is not ``CONNECTED`` and its
        # canonical event is ``connection.accepted`` rather than
        # ``provider.connected``
        "connection.accepted",
        "route.discovered",
        "route.discovered",
        "route.refreshed",
        "route.unavailable",
    ]

    # Discard every runtime component; rebuild from the persisted bytes only.
    restored = restore_provider_registry_state(persisted)

    assert restored.revision == persisted.revision
    recaptured = capture_provider_registry_state(
        restored.providers,
        restored.manifests,
        restored.models,
        restored.connections,
        restored.routes,
        revision=restored.revision,
        audit_log=restored.audit_log,
    )
    assert recaptured == persisted

    rebuilt = restored.routes.get("deepseek:main:deepseek-reasoner")
    assert rebuilt is not None
    assert rebuilt.available is False
    assert rebuilt.first_seen_at == T0
    assert rebuilt.last_seen_at == T0
    assert rebuilt.capabilities == vanished.capabilities
    rebuilt_connection = restored.connections.get("deepseek:main")
    assert rebuilt_connection is not None
    assert rebuilt_connection.last_validated_at == connection.last_validated_at
    assert rebuilt_connection.credential_ref == "keychain://cmm/providers/deepseek/main"

    # Persisted bytes carry only the opaque ref, never the stored secret.
    payload = (tmp_path / "state.json").read_text(encoding="utf-8")
    assert "keychain://cmm/providers/deepseek/main" in payload
    assert _SECRET not in payload
    assert (
        runtime.credentials._secrets["keychain://cmm/providers/deepseek/main"]
        == _SECRET
    )


# --- Scenario J: corruption/version fail closed ----------------------------


def _write_payload(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_scenario_j_corruption_and_version_fail_closed(tmp_path: Path) -> None:
    """Unsupported, malformed, or orphaned state rejects the whole load."""
    state_path = tmp_path / "state.json"
    repository = FileProviderRegistryStateRepository(state_path)
    runtime = _runtime(tmp_path, repository=repository)
    _connect_deepseek(runtime)
    good_bytes = state_path.read_bytes()

    # Unsupported schema version.
    payload = json.loads(good_bytes)
    payload["schema_version"] = "999"
    _write_payload(state_path, payload)
    with pytest.raises(ProviderStateSchemaError):
        repository.load()

    # Malformed payload.
    state_path.write_text("{not json", encoding="utf-8")
    with pytest.raises(ProviderStateSerializationError):
        repository.load()

    # Orphan connection: the provider is missing from the persisted providers.
    payload = json.loads(good_bytes)
    payload["connections"][0]["provider_id"] = "ghost-provider"
    state = ProviderRegistryState.from_dict(payload)
    with pytest.raises(ProviderError, match="Unknown registered provider"):
        restore_provider_registry_state(state)

    # Orphan route: the connection was never accepted.
    payload = json.loads(good_bytes)
    payload["routes"] = [
        {
            "route_id": "ghost:main:model",
            "connection_id": "ghost:main",
            "provider_model_id": "model",
            "canonical_model_id": "model",
            "available": True,
            "first_seen_at": None,
            "last_seen_at": None,
            "capabilities": [],
        }
    ]
    with pytest.raises(ValueError, match="unknown connection_id"):
        restore_provider_registry_state(ProviderRegistryState.from_dict(payload))

    # No partial aggregate is ever exposed: the pristine bytes still restore
    # fully, and the failed attempts left no state behind.
    state_path.write_bytes(good_bytes)
    restored = restore_provider_registry_state(repository.load())
    assert restored.connections.get("deepseek:main") is not None
    assert len(restored.providers.list()) == 11


# --- Scenario K: discovery without inference -------------------------------


def test_scenario_k_discovery_without_inference(tmp_path: Path) -> None:
    """The canonical discovery path updates routes and never infers."""
    runtime = _runtime(tmp_path)
    connection = _connect_deepseek(runtime)
    manifest = runtime.manifests.get("deepseek")
    assert manifest is not None
    client = _RecordingClient(("deepseek-chat", "deepseek-reasoner"))

    result = discover_models(connection, manifest, client, runtime.routes, seen_at=T0)

    assert result.discovered_route_ids == (
        "deepseek:main:deepseek-chat",
        "deepseek:main:deepseek-reasoner",
    )
    assert len(result.new_route_ids) == 2
    assert runtime.routes.get("deepseek:main:deepseek-chat") is not None
    assert client.inference_calls == []
    # The transport contract itself exposes no inference entry point.
    assert not hasattr(DiscoverableModelClient, "generate")


# --- Scenario L: capability filtering --------------------------------------


def test_scenario_l_capability_filtering_is_deterministic(tmp_path: Path) -> None:
    """Only supported, non-UNKNOWN claims satisfy; order is canonical."""
    runtime = _runtime(tmp_path)
    connection = _connect_deepseek(runtime)
    assert connection.connection_id == "deepseek:main"

    def route_with(
        route_id: str,
        capabilities: tuple[RouteCapabilityState, ...],
    ) -> ModelRoute:
        return ModelRoute(
            route_id=route_id,
            connection_id="deepseek:main",
            provider_model_id=route_id.split(":")[-1],
            canonical_model_id=route_id.split(":")[-1],
            capabilities=capabilities,
        )

    runtime.routes.restore(
        route_with(
            "deepseek:main:verified",
            (
                RouteCapabilityState(
                    name="tools",
                    supported=True,
                    confidence=CapabilityConfidence.VERIFIED,
                ),
            ),
        )
    )
    runtime.routes.restore(
        route_with(
            "deepseek:main:unknown-confidence",
            (
                RouteCapabilityState(
                    name="tools",
                    supported=True,
                    confidence=CapabilityConfidence.UNKNOWN,
                ),
            ),
        )
    )
    runtime.routes.restore(
        route_with(
            "deepseek:main:unsupported",
            (
                RouteCapabilityState(
                    name="tools",
                    supported=False,
                    confidence=CapabilityConfidence.DISCOVERED,
                ),
            ),
        )
    )
    runtime.routes.restore(route_with("deepseek:main:missing", ()))

    filtered = runtime.routes.filter_required_capabilities(("tools",))
    assert [route.route_id for route in filtered] == ["deepseek:main:verified"]

    # Determinism: the same catalog yields the same canonical order again.
    assert [
        route.route_id
        for route in runtime.routes.filter_required_capabilities(("tools",))
    ] == ["deepseek:main:verified"]

    # An unknown requirement name can never be satisfied by any route.
    assert runtime.routes.filter_required_capabilities(("not-a-capability",)) == ()


# --- Scenario M: immutable safe projections ---------------------------------


def test_scenario_m_immutable_safe_projections(tmp_path: Path) -> None:
    """Snapshots leak nothing, stay frozen, and round-trip exactly."""
    runtime = _runtime(tmp_path, validator=lambda proposal: True)
    _connect_deepseek(runtime)
    runtime.routes.restore(
        ModelRoute(
            route_id="deepseek:main:deepseek-chat",
            connection_id="deepseek:main",
            provider_model_id="deepseek-chat",
            canonical_model_id="deepseek-chat",
            first_seen_at=T0,
            last_seen_at=T1,
            capabilities=(
                RouteCapabilityState(
                    name="tools",
                    supported=True,
                    confidence=CapabilityConfidence.VERIFIED,
                ),
            ),
        )
    )

    inventory = build_inventory_snapshot(
        runtime.connections.list(), runtime.routes.list()
    )
    dumped = json.dumps(inventory.to_dict())

    # No secret material, no credential refs, no profile paths, no endpoints,
    # no raw detector metadata cross the projection boundary.
    assert _SECRET not in dumped
    assert "keychain://" not in dumped
    assert "cmm-profiles" not in dumped
    lowered = [key.lower() for key in _all_keys(inventory.to_dict())]
    for forbidden in (
        "credential",
        "secret",
        "password",
        "api_key",
        "bearer",
        "isolation",
        "profile",
        "endpoint",
        "metadata",
        "source_home",
    ):
        assert not any(forbidden in key for key in lowered)

    # Frozen via real-field assignment, per snapshot type.
    with pytest.raises(dataclasses.FrozenInstanceError):
        inventory.connections[0].provider_id = "mutated"  # type: ignore[misc]
    with pytest.raises(dataclasses.FrozenInstanceError):
        inventory.routes[0].provider_id = "mutated"  # type: ignore[misc]
    with pytest.raises(dataclasses.FrozenInstanceError):
        inventory.generated_at = "mutated"  # type: ignore[misc]

    # JSON round-trip is exact.
    restored = ProviderInventorySnapshot.from_dict(
        json.loads(json.dumps(inventory.to_dict()))
    )
    assert restored == inventory


def _all_keys(payload: object) -> list[str]:
    """Collect every mapping key recursively (test helper)."""
    keys: list[str] = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            keys.append(str(key))
            keys.extend(_all_keys(value))
    elif isinstance(payload, list):
        for item in payload:
            keys.extend(_all_keys(item))
    return keys


# --- Remediation V2 adversaries (Independent Re-audit V2 findings) ----------
#
# These checkpoints close the acceptance-adequacy gap Independent Re-audit V2
# reported for MAJOR-V2-01 … MAJOR-V2-05. They exercise the same canonical
# components as scenarios A–M — no mock stands in for the provider authority,
# the manifest catalog, the repository, the coordinator, the real detectors or
# the discovery path.

# --- MAJOR-V2-01: manifest metadata cannot outlive canonical identity -------


def test_v2_manifest_non_divergence_after_provider_removal(tmp_path: Path) -> None:
    """A manifest dies with its exact provider and never revives on re-add."""
    repository = FileProviderRegistryStateRepository(tmp_path / "state.json")
    runtime = _runtime(tmp_path, repository=repository)
    manifest = runtime.manifests.get("deepseek")
    assert manifest is not None
    bound = runtime.providers.get("deepseek")

    assert runtime.providers.remove("deepseek") is bound
    assert runtime.manifests.get("deepseek") is None
    assert all(item.provider_id != "deepseek" for item in runtime.manifests.list())
    # The metadata record itself is untouched; only its validity is gone.
    assert manifest.provider_id == "deepseek"

    # Same provider id, new canonical `ProviderSpec` object: identity equality by
    # id alone must not revive the removed provider's metadata.
    runtime.providers.register(provider_spec_from_manifest(manifest))
    assert runtime.providers.has("deepseek")
    assert runtime.manifests.get("deepseek") is None
    assert all(item.provider_id != "deepseek" for item in runtime.manifests.list())

    # Capture stays coherent, and whatever it captures always restores.
    state = capture_provider_registry_state(
        runtime.providers,
        runtime.manifests,
        runtime.models,
        runtime.connections,
        runtime.routes,
        revision=0,
    )
    assert all(item.provider_id != "deepseek" for item in state.manifests)
    assert [spec.id for spec in state.providers] == [
        spec.id for spec in runtime.providers.list()
    ]
    restored = restore_provider_registry_state(state)
    assert restored.providers.has("deepseek")
    assert [item.provider_id for item in restored.manifests.list()] == [
        item.provider_id for item in state.manifests
    ]

    # The lazy purge is not what makes this safe: a runtime that re-registers the
    # same id without any intervening lookup still refuses the old metadata.
    fresh = _runtime(tmp_path / "no-intervening-lookup")
    fresh_manifest = fresh.manifests.get("deepseek")
    assert fresh_manifest is not None
    fresh.providers.remove("deepseek")
    fresh.providers.register(provider_spec_from_manifest(fresh_manifest))
    assert fresh.manifests.get("deepseek") is None
    assert all(item.provider_id != "deepseek" for item in fresh.manifests.list())


def test_v2_capture_refuses_manifest_metadata_without_a_canonical_provider(
    tmp_path: Path,
) -> None:
    """Cross-authority metadata can never reach a persisted, unrestorable aggregate."""
    runtime = _runtime(tmp_path)
    foreign = ProviderRegistry()
    assert foreign.list() == ()
    models = ModelCatalog(foreign)
    connections = ProviderConnectionRegistry(foreign)
    routes = ModelRouteCatalog(connections)

    # The exact-object graph guard (MAJOR-V3-01) refuses the authority mismatch
    # at the composition boundary, before enumeration: a metadata catalog bound
    # to another authority is not merely orphaned, it is cross-wired.
    with pytest.raises(
        ProviderStateCoherenceError,
        match="manifest registry is bound to a different ProviderRegistry",
    ):
        capture_provider_registry_state(
            foreign,
            runtime.manifests,
            models,
            connections,
            routes,
            revision=0,
        )

    # The guard is a refusal, not a silent omission: the same metadata graph
    # captures and restores once it is bound to the authority holding its
    # providers.
    coherent = capture_provider_registry_state(
        runtime.providers,
        runtime.manifests,
        runtime.models,
        runtime.connections,
        runtime.routes,
        revision=0,
    )
    assert [item.provider_id for item in coherent.manifests] == [
        item.provider_id for item in runtime.manifests.list()
    ]
    assert restore_provider_registry_state(coherent).providers.has("deepseek")


# --- MAJOR-V2-02: route and validation lifecycle audit persistence ----------


def test_v2_route_lifecycle_audit_is_persisted_and_survives_restart(
    tmp_path: Path,
) -> None:
    """discover → disappear → restore is durably audited, not just inspected."""
    repository = FileProviderRegistryStateRepository(tmp_path / "state.json")
    runtime = _runtime(tmp_path, repository=repository)
    coordinator = runtime.coordinator
    assert coordinator is not None
    connection = _connect_deepseek(runtime)
    manifest = runtime.manifests.get("deepseek")
    assert manifest is not None
    clients = (
        _RecordingClient(("deepseek-chat", "deepseek-reasoner")),
        _RecordingClient(("deepseek-chat",)),
        _RecordingClient(("deepseek-chat", "deepseek-reasoner")),
    )

    for client, seen_at in zip(clients, (T0, T1, T2), strict=True):
        coordinator.discover_models(connection, manifest, client, seen_at=seen_at)

    assert [client.inference_calls for client in clients] == [[], [], []]
    state = repository.load()
    assert state is not None
    assert state.revision == coordinator.revision == 4
    assert [record.event_type for record in state.audit_log] == [
        "connection.accepted",
        "route.discovered",
        "route.discovered",
        "route.refreshed",
        "route.unavailable",
        "route.refreshed",
        "route.restored",
    ]
    assert [record.revision for record in state.audit_log] == [1, 2, 2, 3, 3, 4, 4]
    assert state.audit_log[2].entity_kind == "route"
    assert state.audit_log[3].entity_id == "deepseek:main:deepseek-chat"
    assert state.audit_log[3].occurred_at == T1
    assert state.audit_log[4].entity_id == "deepseek:main:deepseek-reasoner"
    assert state.audit_log[4].occurred_at == T1
    assert state.audit_log[4].detail == (
        ("connection_id", "deepseek:main"),
        ("available", "false"),
    )
    assert state.audit_log[6].entity_id == "deepseek:main:deepseek-reasoner"
    assert state.audit_log[6].occurred_at == T2
    assert state.audit_log[6].detail == (
        ("connection_id", "deepseek:main"),
        ("available", "true"),
    )

    # Process-equivalent restart: the same subsequence is available again.
    restored = restore_provider_registry_state(state)
    assert restored.revision == state.revision
    assert [record.event_type for record in restored.audit_log] == [
        "connection.accepted",
        "route.discovered",
        "route.discovered",
        "route.refreshed",
        "route.unavailable",
        "route.refreshed",
        "route.restored",
    ]
    assert [record.revision for record in restored.audit_log] == [1, 2, 2, 3, 3, 4, 4]
    route = restored.routes.get("deepseek:main:deepseek-reasoner")
    assert route is not None
    assert route.available is True
    assert route.first_seen_at == T0
    assert route.last_seen_at == T2
    refreshed = restored.routes.get("deepseek:main:deepseek-chat")
    assert refreshed is not None
    assert refreshed.first_seen_at == T0
    assert refreshed.last_seen_at == T2


def test_v2_validation_transition_audit_is_persisted_and_survives_restart(
    tmp_path: Path,
) -> None:
    """A real status transition is durably audited with its old/new status."""
    repository = FileProviderRegistryStateRepository(tmp_path / "state.json")
    runtime = _runtime(tmp_path, repository=repository)
    coordinator = runtime.coordinator
    assert coordinator is not None
    connection = _connect_deepseek(runtime)
    assert connection.status is ConnectionStatus.AUTH_REQUIRED
    assert connection.last_validated_at is None

    updated = coordinator.update_connection_status(
        "deepseek:main", ConnectionStatus.CONNECTED, occurred_at=T1
    )

    assert updated.status is ConnectionStatus.CONNECTED
    assert updated.last_validated_at == T1
    assert runtime.connections.get("deepseek:main") == updated
    state = repository.load()
    assert state is not None
    assert state.revision == coordinator.revision == 2
    assert [record.event_type for record in state.audit_log] == [
        "connection.accepted",
        "provider.validation_changed",
    ]
    record = state.audit_log[1]
    assert record.entity_kind == "connection"
    assert record.entity_id == "deepseek:main"
    assert record.occurred_at == T1
    assert record.detail == (
        ("old_status", "auth_required"),
        ("new_status", "connected"),
    )

    restored = restore_provider_registry_state(state)
    assert [item.event_type for item in restored.audit_log] == [
        "connection.accepted",
        "provider.validation_changed",
    ]
    rebuilt = restored.connections.get("deepseek:main")
    assert rebuilt is not None
    assert rebuilt.status is ConnectionStatus.CONNECTED
    assert rebuilt.last_validated_at == T1


# --- MAJOR-V2-03: auth-only subscription isolation --------------------------


def _write_auth_only_subscription_source(provider_id: str, root: Path) -> Path:
    """A subscription home carrying authentication evidence *only*."""
    source = root / f"{provider_id}-auth-only"
    source.mkdir(parents=True, exist_ok=True)
    (source / _SUBSCRIPTION_AUTH_MARKERS[provider_id]).write_text(
        "{}\n", encoding="utf-8"
    )
    return source


@pytest.mark.parametrize("provider_id", ["codex", "claude-code", "antigravity"])
def test_v2_auth_only_subscription_requires_cmm_owned_isolation(
    tmp_path: Path, provider_id: str
) -> None:
    """Authentication alone still forces a CMM-owned profile before CONNECTED."""
    source = _write_auth_only_subscription_source(provider_id, tmp_path)
    runtime = _runtime(tmp_path, validator=lambda proposal: True)

    candidate = _subscription_detector(provider_id, source).detect()

    assert candidate.auth_available is True
    assert candidate.external_config_present is False
    assert candidate.external_endpoint_override_present is False
    proposal = runtime.service.propose(candidate)
    assert proposal.requires_isolation is True

    connection = runtime.service.accept(proposal)

    assert connection.status is ConnectionStatus.CONNECTED
    assert connection.isolation_profile_ref is not None
    profile_home = Path(connection.isolation_profile_ref)
    assert profile_home.is_dir()
    assert runtime.profiles_root in profile_home.parents
    assert profile_home != source
    # The profile is CMM-owned: the external home is never the profile, the
    # external config marker is never copied, and the acceptance touched
    # nothing outside the CMM-owned root.
    assert not (profile_home / _SUBSCRIPTION_CONFIG_MARKERS[provider_id]).exists()
    assert (source / _SUBSCRIPTION_AUTH_MARKERS[provider_id]).is_file()
    assert not (source / _SUBSCRIPTION_CONFIG_MARKERS[provider_id]).exists()
    if provider_id == "codex":
        copied = profile_home / _SUBSCRIPTION_AUTH_MARKERS[provider_id]
        original = source / _SUBSCRIPTION_AUTH_MARKERS[provider_id]
        assert copied.read_bytes() == original.read_bytes()


@pytest.mark.parametrize("provider_id", ["codex", "claude-code", "antigravity"])
def test_v2_auth_only_subscription_never_connects_without_isolation(
    tmp_path: Path, provider_id: str
) -> None:
    """A passing validator never replaces a required isolation outcome."""
    root = tmp_path / "run"
    repository = FileProviderRegistryStateRepository(root / "state.json")
    source = _write_auth_only_subscription_source(provider_id, root)
    runtime = _runtime(root, repository=repository, validator=lambda proposal: True)
    candidate = _subscription_detector(provider_id, source).detect()
    assert candidate.external_config_present is False
    proposal = runtime.service.propose(candidate)
    assert proposal.requires_isolation is True

    # The isolation evidence disappears after detection: the candidate was real,
    # the profile can no longer be built.
    shutil.rmtree(source)

    with pytest.raises(ProviderIsolationError):
        runtime.service.accept(proposal)

    assert runtime.connections.list() == ()
    assert runtime.service.revision == 0
    assert repository.load() is None
    assert not (runtime.profiles_root / provider_id).exists()


# --- MAJOR-V2-04: ownership-safe acceptance side effects --------------------


def test_v2_preexisting_credential_is_never_overwritten_or_deleted(
    tmp_path: Path,
) -> None:
    """New-connection acceptance rejects an unowned ref before `put()`."""
    state_path = tmp_path / "state.json"
    repository = FileProviderRegistryStateRepository(state_path)
    runtime = _runtime(tmp_path, repository=repository)
    other = runtime.service.accept(
        runtime.service.propose(_api_candidate("qwen-cloud")), credential="qwen-secret"
    )
    existing_ref = runtime.credentials.put("deepseek", "main", "secret-old")
    secrets_before = dict(runtime.credentials._secrets)
    bytes_before = state_path.read_bytes()

    with pytest.raises(ValueError, match="credential already exists"):
        runtime.service.accept(
            runtime.service.propose(_api_candidate("deepseek")),
            credential="secret-new",
        )

    # Rejected before any mutation: the pre-existing secret mapping is unchanged
    # byte for byte, the connection is absent and the durable state is untouched.
    assert runtime.credentials._secrets == secrets_before
    assert runtime.credentials.has(existing_ref)
    assert runtime.credentials._secrets[existing_ref] == "secret-old"
    assert runtime.connections.list() == (other,)
    assert runtime.service.revision == 1
    durable = repository.load()
    assert durable is not None
    assert durable.revision == 1
    assert state_path.read_bytes() == bytes_before
    assert _SECRET not in bytes_before.decode("utf-8")
    assert "secret-new" not in bytes_before.decode("utf-8")


@pytest.mark.parametrize("provider_id", ["codex", "claude-code", "antigravity"])
def test_v2_preexisting_isolation_target_is_never_mutated(
    tmp_path: Path, provider_id: str
) -> None:
    """A pre-existing isolation target is rejected before profile mutation."""
    root = tmp_path / "run"
    repository = FileProviderRegistryStateRepository(root / "state.json")
    source = _write_auth_only_subscription_source(provider_id, root)
    runtime = _runtime(root, repository=repository, validator=lambda proposal: True)
    target = runtime.profiles_root / provider_id
    target.mkdir(parents=True)
    (target / "keep-me.bin").write_bytes(b"PRE-EXISTING-MARKER")
    if provider_id == "codex":
        (target / "auth.json").write_text(
            '{"tokens": "PRE-EXISTING-AUTH"}\n', encoding="utf-8"
        )
    before = {path.name: path.read_bytes() for path in target.iterdir()}

    candidate = _subscription_detector(provider_id, source).detect()
    proposal = runtime.service.propose(candidate)
    assert proposal.requires_isolation is True

    with pytest.raises(ValueError, match="isolation profile already exists"):
        runtime.service.accept(proposal)

    # Byte-for-byte identical target: no file rewritten, no file added, no
    # directory replaced.
    assert {path.name: path.read_bytes() for path in target.iterdir()} == before
    assert runtime.connections.list() == ()
    assert runtime.service.revision == 0
    assert repository.load() is None


_REPO_ROOT = Path(__file__).resolve().parents[2]
_PHASE11_MATRIX_PATH = (
    _REPO_ROOT
    / "docs"
    / "reference"
    / "phase-11-stable-integrated-platform-requirements-matrix.md"
)
_PHASE10_MATRIX_PATH = (
    _REPO_ROOT / "docs" / "reference" / "domain-intelligence-requirements-matrix.md"
)

# The canonical F11-014 statement the Phase 11 matrix must carry (spec §8.3).
_F11_014_STATEMENT = (
    "Maintain one canonical, persistent, auditable and fail-closed Provider "
    "Registry in which provider identity is authoritative through "
    "`ProviderRegistry`, manifests/connections/models/routes are referentially "
    "coherent, subscription isolation policy is explicit, onboarding side "
    "effects are ownership-safe, discovery remains non-inference, and `DP-134` "
    "is verified through `AT-DP-134`."
)

# Claims that would mean Phase 11.34 is closed. Before Independent Re-audit V3
# they may appear only inside a fence explicitly labelled as the future closure
# criteria, never as current state (spec §15).
_FORBIDDEN_CURRENT_CLAIMS = (
    "PHASE11_34=CLOSED",
    "F11-014=VERIFIED_EXISTING",
    "DP-134=VERIFIED_EXISTING",
    "AT-DP-134=PASS",
    "CLOSURE_ELIGIBLE=YES",
)

# Every artifact the F11-014 row must trace to (spec §8.4).
_F11_014_TRACEABILITY = (
    "kernel/llm/provider_registry.py",
    "kernel/llm/provider_manifests.py",
    "kernel/llm/provider_connections.py",
    "kernel/llm/model_routes.py",
    "kernel/llm/model_discovery.py",
    "kernel/llm/provider_onboarding.py",
    "ProviderRegistryStateRepository",
    "ProviderRegistryStateCoordinator",
    "ProviderOnboardingService",
    "docs/audits/phase-11.34-provider-registry-independent-audit-v1.md",
    "docs/audits/phase-11.34-provider-registry-independent-reaudit-v2.md",
    "docs/superpowers/specs/2026-09-14-phase-11.34-provider-registry-remediation-v1-design.md",
    "docs/superpowers/plans/2026-09-14-phase-11.34-provider-registry-remediation-v1-implementation-plan.md",
    "docs/superpowers/specs/2026-09-15-phase-11.34-provider-registry-remediation-v2-design.md",
    "docs/superpowers/plans/2026-09-15-phase-11.34-provider-registry-remediation-v2-implementation-plan.md",
    "tests/llm/test_provider_registry_dp134_acceptance.py",
)

# The inherited/preassigned Phase 11 planning rows that stay owned by the Phase
# 10 matrix. Their normative text must not be restated (duplicated) here.
_INHERITED_PHASE11_IDS = tuple(f"F11-{index:03d}" for index in range(1, 14))


def _marked_lines(text: str):
    """Yield ``(line, fence_label)``; the label is ``None`` outside a fence.

    A fence is labelled with the nearest preceding non-empty line outside any
    fence, so a "future closure criteria" heading before a block is what marks
    the block as such.
    """
    fence_label: str | None = None
    pending_label = ""
    for line in text.splitlines():
        if line.strip().startswith("```"):
            if fence_label is None:
                fence_label = pending_label
            else:
                fence_label = None
                pending_label = ""
            continue
        if fence_label is None and line.strip():
            pending_label = line.strip()
        yield line, fence_label


def _phase11_inherited_rows(text: str) -> dict[str, str]:
    """Return the ``F11-0xx`` planning rows of the Phase 10 matrix by id.

    Only the normative-requirement cell is extracted: that text is what the new
    Phase 11 matrix must point back to instead of copying.
    """
    rows: dict[str, str] = {}
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("| `F11-0"):
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split(" | ")]
        if len(cells) != 7:
            continue
        requirement_id = cells[0].strip("`")
        if requirement_id in _INHERITED_PHASE11_IDS:
            rows[requirement_id] = cells[1]
    return rows


def test_requirements_matrix_traceability_is_canonical_and_pending_reaudit() -> None:
    """The Phase 11 matrix owns `F11-014` → `DP-134` → `AT-DP-134`, unclosed.

    Documentary checkpoint only (spec §9.7): every runtime invariant in this
    file is proven by the scenarios themselves, never by reading a document.
    """
    assert _PHASE11_MATRIX_PATH.is_file(), (
        f"the canonical Phase 11 requirements matrix is missing: {_PHASE11_MATRIX_PATH}"
    )
    text = _PHASE11_MATRIX_PATH.read_text(encoding="utf-8")

    # The row and its full traceable chain exist verbatim.
    for marker in ("F11-014", "DP-134", "AT-DP-134", "11.34"):
        assert marker in text, f"Phase 11 matrix does not carry {marker}"
    assert _F11_014_STATEMENT in text
    for artifact in _F11_014_TRACEABILITY:
        assert artifact in text, f"F11-014 row does not trace to {artifact}"

    # The lifecycle status is the pending-reaudit maximum, never closure.
    assert "IMPLEMENTED_PENDING_INDEPENDENT_REAUDIT" in text
    assert "DP-134=IMPLEMENTED_PENDING_INDEPENDENT_REAUDIT" in text
    assert "AT-DP-134=PASS_REPORTED" in text
    assert "CLOSURE_ELIGIBLE=NO" in text
    for line, fence_label in _marked_lines(text):
        if line.strip() not in _FORBIDDEN_CURRENT_CLAIMS:
            continue
        assert fence_label is not None and "future closure criteria" in (
            fence_label.lower()
        ), f"premature closure claim outside future criteria: {line.strip()!r}"

    # The historical Phase 10 matrix stays canonical for `F11-001`…`F11-013`:
    # the new matrix points back to those rows instead of restating them.
    assert _PHASE10_MATRIX_PATH.name in text
    inherited = _phase11_inherited_rows(_PHASE10_MATRIX_PATH.read_text("utf-8"))
    assert set(_INHERITED_PHASE11_IDS) <= set(inherited)
    for requirement_id in _INHERITED_PHASE11_IDS:
        assert requirement_id in text
        assert inherited[requirement_id] not in text, (
            f"{requirement_id} normative text must stay owned by the Phase 10 "
            "matrix instead of being duplicated"
        )


# --- Remediation V3 adversaries (Independent Re-audit V3 findings) ----------
#
# MAJOR-V3-01: two simultaneously live ``ProviderRegistry`` authorities holding
# the same normalized provider id must never be cross-wirable — capture,
# coordinator construction and onboarding construction each fail closed on the
# exact-object graph.
#
# MAJOR-V3-02: a successful rediscovery of an already-known route is durable
# Provider Registry state; it survives a restart, is audited as
# ``route.refreshed``, stays a true no-op at the same timestamp, and rolls back
# exactly when the save fails.
#
# Every component here is canonical (real ``ProviderRegistry``,
# ``ProviderManifestRegistry``, ``ModelCatalog``, ``ProviderConnectionRegistry``,
# ``ModelRouteCatalog``, repository and coordinator); no mock stands in for the
# provider authority or the persistence seam.

_FOREIGN_PROVIDER_URL = "https://foreign-provider.example/v1"
_FOREIGN_MANIFEST_URL = "https://foreign-manifest.example/v1"
_CANONICAL_PROVIDER_URL = "https://canonical-provider.example/v1"


@dataclass(frozen=True, slots=True)
class _Authority:
    """One live provider authority with every catalog bound to it."""

    providers: ProviderRegistry
    manifests: ProviderManifestRegistry
    models: ModelCatalog
    connections: ProviderConnectionRegistry
    routes: ModelRouteCatalog


def _authority(provider_url: str, manifest_url: str) -> _Authority:
    """Build one live authority carrying the audited ``deepseek`` identity.

    Both authorities built by this helper hold the same normalized provider id
    with different ``ProviderSpec``/``ProviderManifest`` values, exactly as the
    independent V3 reproduction did, so provider-id equality can never satisfy
    an exact-object guard.
    """
    providers = ProviderRegistry()
    providers.register(
        ProviderSpec(
            id="deepseek",
            provider_type="remote",
            api_style="chat_completions",
            base_url=provider_url,
        )
    )
    manifests = ProviderManifestRegistry(providers)
    manifests.register(
        ProviderManifest(
            provider_id="deepseek",
            display_name="DeepSeek",
            billing_class=BillingClass.PAYG,
            default_base_url=manifest_url,
            auth_scheme=FIRST_WAVE_AUTH_SCHEME,
        )
    )
    connections = ProviderConnectionRegistry(providers)
    return _Authority(
        providers=providers,
        manifests=manifests,
        models=ModelCatalog(providers),
        connections=connections,
        routes=ModelRouteCatalog(connections),
    )


def _cross_authority_pair() -> tuple[_Authority, _Authority]:
    """Return ``(canonical, foreign)``: same id, divergent provider/metadata."""
    canonical = _authority(_CANONICAL_PROVIDER_URL, _CANONICAL_PROVIDER_URL)
    foreign = _authority(_FOREIGN_PROVIDER_URL, _FOREIGN_MANIFEST_URL)
    assert canonical.providers.get("deepseek") is not foreign.providers.get("deepseek")
    assert foreign.manifests.get("deepseek").default_base_url == _FOREIGN_MANIFEST_URL
    return canonical, foreign


@pytest.mark.parametrize(
    ("component", "message"),
    [
        ("manifests", "manifest registry is bound to a different ProviderRegistry"),
        ("models", "model catalog is bound to a different ProviderRegistry"),
        ("connections", "connection registry is bound to a different ProviderRegistry"),
        (
            "routes",
            "route catalog is bound to a different ProviderConnectionRegistry",
        ),
    ],
)
def test_v3_capture_rejects_every_cross_wired_component(
    component: str, message: str
) -> None:
    """No state envelope is ever produced from a cross-authority graph."""
    canonical, foreign = _cross_authority_pair()
    graph: dict[str, object] = {
        "manifests": canonical.manifests,
        "models": canonical.models,
        "connections": canonical.connections,
        "routes": canonical.routes,
    }
    graph[component] = getattr(foreign, component)

    with pytest.raises(ProviderStateCoherenceError, match=message):
        capture_provider_registry_state(
            canonical.providers,
            graph["manifests"],  # type: ignore[arg-type]
            graph["models"],  # type: ignore[arg-type]
            graph["connections"],  # type: ignore[arg-type]
            graph["routes"],  # type: ignore[arg-type]
            revision=0,
        )

    # The same graph with the canonical component restores normally, which
    # proves the refusal is about wiring, not about the components themselves.
    coherent = capture_provider_registry_state(
        canonical.providers,
        canonical.manifests,
        canonical.models,
        canonical.connections,
        canonical.routes,
        revision=0,
    )
    assert [item.provider_id for item in coherent.manifests] == ["deepseek"]
    assert restore_provider_registry_state(coherent).providers.has("deepseek")


def test_v3_coordinator_rejects_a_cross_authority_graph(tmp_path: Path) -> None:
    """The coordinator is not constructible over a foreign same-id graph."""
    canonical, foreign = _cross_authority_pair()
    repository = FileProviderRegistryStateRepository(tmp_path / "state.json")

    with pytest.raises(
        ProviderStateCoherenceError,
        match="manifest registry is bound to a different ProviderRegistry",
    ):
        ProviderRegistryStateCoordinator(
            providers=canonical.providers,
            manifests=foreign.manifests,
            models=canonical.models,
            connections=canonical.connections,
            routes=canonical.routes,
            repository=repository,
        )

    # Construction failed before the coordinator existed: no revision was
    # produced and the repository was never written.
    assert repository.load() is None


def test_v3_onboarding_rejects_a_cross_authority_graph(tmp_path: Path) -> None:
    """Foreign metadata can never become an accepted connection endpoint."""
    runtime = _runtime(tmp_path)
    _, foreign = _cross_authority_pair()
    credentials = InMemoryCredentialStore()
    repository = FileProviderRegistryStateRepository(tmp_path / "state.json")
    assert runtime.providers.has("deepseek")
    assert foreign.manifests.get("deepseek").default_base_url == _FOREIGN_MANIFEST_URL

    with pytest.raises(
        ProviderStateCoherenceError,
        match="manifest registry is bound to a different ProviderRegistry",
    ):
        ProviderOnboardingService(
            providers=runtime.providers,
            connections=runtime.connections,
            manifests=foreign.manifests,
            credentials=credentials,
            profiles=SubscriptionProfileManager(),
            profiles_root=tmp_path / "cmm-profiles",
            state_coordinator=runtime.coordinator,
        )

    # No service exists, so no proposal could resolve the foreign endpoint and
    # nothing was mutated, stored or profiled.
    assert runtime.connections.list() == ()
    assert credentials._secrets == {}
    assert not (tmp_path / "cmm-profiles").exists()
    assert repository.load() is None


def test_v3_onboarding_rejects_a_coordinator_for_another_graph(tmp_path: Path) -> None:
    """A coordinator over another authority is not onboarding's commit seam."""
    runtime = _runtime(tmp_path)
    _, foreign = _cross_authority_pair()
    foreign_coordinator = ProviderRegistryStateCoordinator(
        providers=foreign.providers,
        manifests=foreign.manifests,
        models=foreign.models,
        connections=foreign.connections,
        routes=foreign.routes,
        repository=FileProviderRegistryStateRepository(tmp_path / "foreign.json"),
    )

    with pytest.raises(
        ProviderStateCoherenceError,
        match="state coordinator is bound to a different ProviderRegistry",
    ):
        ProviderOnboardingService(
            providers=runtime.providers,
            connections=runtime.connections,
            manifests=runtime.manifests,
            credentials=InMemoryCredentialStore(),
            profiles=SubscriptionProfileManager(),
            profiles_root=tmp_path / "cmm-profiles",
            state_coordinator=foreign_coordinator,
        )

    assert runtime.connections.list() == ()


class _SwitchableRepository:
    """Two-method repository whose ``save`` can be armed to fail on demand."""

    def __init__(self) -> None:
        self.fail = False
        self.save_calls = 0
        self._state: ProviderRegistryState | None = None

    def load(self) -> ProviderRegistryState | None:
        return self._state

    def save(self, state: ProviderRegistryState) -> None:
        self.save_calls += 1
        if self.fail:
            raise RuntimeError("persistence failed")
        self._state = state


def test_v3_route_refresh_is_durable_across_a_restart(tmp_path: Path) -> None:
    """T0 → T1 rediscovery persists T1 and survives a process-equivalent restart."""
    repository = FileProviderRegistryStateRepository(tmp_path / "state.json")
    runtime = _runtime(tmp_path, repository=repository)
    coordinator = runtime.coordinator
    assert coordinator is not None
    connection = _connect_deepseek(runtime)
    manifest = runtime.manifests.get("deepseek")
    assert manifest is not None
    route_id = "deepseek:main:deepseek-chat"

    coordinator.discover_models(
        connection, manifest, _RecordingClient(("deepseek-chat",)), seen_at=T0
    )
    revision_after_t0 = coordinator.revision
    assert revision_after_t0 == 2

    second = _RecordingClient(("deepseek-chat",))
    coordinator.discover_models(connection, manifest, second, seen_at=T1)

    assert second.inference_calls == []
    assert coordinator.revision == revision_after_t0 + 1
    live = runtime.routes.get(route_id)
    assert live is not None
    assert live.last_seen_at == T1
    state = repository.load()
    assert state is not None
    assert state.revision == coordinator.revision
    assert [record.event_type for record in state.audit_log] == [
        "connection.accepted",
        "route.discovered",
        "route.refreshed",
    ]
    refreshed = state.audit_log[2]
    assert refreshed.revision == 3
    assert refreshed.entity_kind == "route"
    assert refreshed.entity_id == route_id
    assert refreshed.occurred_at == T1
    assert refreshed.detail == (
        ("connection_id", "deepseek:main"),
        ("available", "true"),
    )
    persisted_route = next(
        route for route in state.routes if route.route_id == route_id
    )
    assert persisted_route.last_seen_at == T1

    # Process-equivalent restart: the component graph is rebuilt from the
    # persisted aggregate only and keeps the newest successful discovery.
    restored = restore_provider_registry_state(state)
    restored_route = restored.routes.get(route_id)
    assert restored_route is not None
    assert restored_route.last_seen_at == T1
    assert restored_route.first_seen_at == T0
    assert restored.revision == state.revision
    assert [record.event_type for record in restored.audit_log][-1] == "route.refreshed"


def test_v3_same_timestamp_rediscovery_is_a_true_no_op(tmp_path: Path) -> None:
    """An identical pass at the exact same instant changes no durable byte."""
    state_path = tmp_path / "state.json"
    runtime = _runtime(
        tmp_path, repository=FileProviderRegistryStateRepository(state_path)
    )
    coordinator = runtime.coordinator
    assert coordinator is not None
    connection = _connect_deepseek(runtime)
    manifest = runtime.manifests.get("deepseek")
    assert manifest is not None

    coordinator.discover_models(
        connection, manifest, _RecordingClient(("deepseek-chat",)), seen_at=T1
    )
    revision_before = coordinator.revision
    audit_before = coordinator.audit_log
    bytes_before = state_path.read_bytes()

    coordinator.discover_models(
        connection, manifest, _RecordingClient(("deepseek-chat",)), seen_at=T1
    )

    assert coordinator.revision == revision_before
    assert coordinator.audit_log == audit_before
    assert state_path.read_bytes() == bytes_before
    assert runtime.routes.get("deepseek:main:deepseek-chat").last_seen_at == T1


def test_v3_refresh_persistence_failure_rolls_back_exactly(tmp_path: Path) -> None:
    """A refresh-only pass that cannot be saved leaves runtime and disk at T0."""
    repository = _SwitchableRepository()
    runtime = _runtime(tmp_path, repository=repository)
    coordinator = runtime.coordinator
    assert coordinator is not None
    connection = _connect_deepseek(runtime)
    manifest = runtime.manifests.get("deepseek")
    assert manifest is not None
    route_id = "deepseek:main:deepseek-chat"

    coordinator.discover_models(
        connection, manifest, _RecordingClient(("deepseek-chat",)), seen_at=T0
    )
    committed = repository.load()
    assert committed is not None
    assert committed.revision == 2
    revision_before = coordinator.revision
    audit_before = coordinator.audit_log
    routes_before = runtime.routes.list()

    repository.fail = True
    with pytest.raises(RuntimeError, match="persistence failed"):
        coordinator.discover_models(
            connection, manifest, _RecordingClient(("deepseek-chat",)), seen_at=T1
        )

    rolled_back = runtime.routes.get(route_id)
    assert rolled_back is not None
    assert rolled_back.last_seen_at == T0
    assert runtime.routes.list() == routes_before
    assert coordinator.revision == revision_before
    assert coordinator.audit_log == audit_before
    assert repository.load() == committed
    assert all(
        record.event_type != "route.refreshed" for record in coordinator.audit_log
    )


# --- Remediation V4 adversaries (Independent Re-audit V4 findings) -----------
#
# MAJOR-V4-01: a correctly wired component graph is not enough — every active
# model, connection and route must still belong to the exact authority object it
# was registered under, or capture refuses to persist the aggregate.
#
# MAJOR-V4-02: ``ConnectionProposal`` is public evidence. Every authority field
# is revalidated against the current canonical provider/manifest at accept time,
# before the validator or any side effect.
#
# MAJOR-V4-03: the caller's discovery manifest is a claim; only the exact active
# canonical manifest may drive route/audit/durable mutation.
#
# MINOR-V4-01: a discovery pass is a connection-level snapshot, so an older
# observation is refused before the client is consulted and ``last_seen_at``
# never regresses.
#
# Everything below runs on the canonical runtime (real registries, canonical
# first-wave/subscription bootstrap, real repository and coordinator). Recording
# fakes are used only to prove zero validator/client calls and zero side effects.

_V4_FOREIGN_MANIFEST_URL = "https://v4-foreign.example/v1"
_V4_FORGED_ENDPOINT = "https://evil.example/v1"


class _RecordingValidator:
    """Canonical-shape validator that records whether it was consulted."""

    def __init__(self, result: bool = True) -> None:
        self.result = result
        self.calls: list[ConnectionProposal] = []

    def __call__(self, proposal: ConnectionProposal) -> bool:
        self.calls.append(proposal)
        return self.result


def _restored_graph_state(runtime: _Runtime) -> ProviderRegistryState:
    """Capture the runtime's live canonical graph as one aggregate."""
    return capture_provider_registry_state(
        runtime.providers,
        runtime.manifests,
        runtime.models,
        runtime.connections,
        runtime.routes,
        revision=7,
    )


def _connect_deepseek_with_dependents(runtime: _Runtime) -> ProviderConnection:
    """Accept DeepSeek and register one dependent model plus one route."""
    connection = _connect_deepseek(runtime)
    runtime.models.register(ModelSpec(id="deepseek-chat", provider_id="deepseek"))
    runtime.routes.register(
        ModelRoute(
            route_id="deepseek:main:deepseek-chat",
            connection_id="deepseek:main",
            provider_model_id="deepseek-chat",
            canonical_model_id="deepseek-chat",
        )
    )
    return connection


def _replacement_connection(connection: ProviderConnection) -> ProviderConnection:
    """Build a different object carrying ``connection``'s id."""
    return dataclasses.replace(connection, endpoint=_V4_FORGED_ENDPOINT)


def test_v4_01_capture_rejects_dependents_of_a_removed_provider(
    tmp_path: Path,
) -> None:
    """A: provider removal with surviving dependents is not capturable."""
    runtime = _runtime(tmp_path)
    _connect_deepseek_with_dependents(runtime)
    assert len(runtime.models.list()) == 1
    assert len(runtime.connections.list()) == 1
    assert len(runtime.routes.list()) == 1

    runtime.providers.remove("deepseek")

    with pytest.raises(
        ProviderStateCoherenceError,
        match="stale or missing ProviderSpec",
    ):
        _restored_graph_state(runtime)


def test_v4_01_capture_rejects_dependents_after_same_id_provider_replacement(
    tmp_path: Path,
) -> None:
    """B: id equality never revives stale dependent authority."""
    runtime = _runtime(tmp_path)
    _connect_deepseek_with_dependents(runtime)
    original = runtime.providers.get("deepseek")

    runtime.providers.remove("deepseek")
    replacement = runtime.providers.register(
        ProviderSpec(
            id="deepseek",
            provider_type="remote",
            api_style="chat_completions",
            base_url=_V4_FOREIGN_MANIFEST_URL,
        )
    )

    assert original is not replacement
    # Dependents survive by id and stay visible...
    assert runtime.connections.get("deepseek:main") is not None
    assert runtime.models.get("deepseek-chat", provider_id="deepseek") is not None
    # ...and capture still refuses the aggregate.
    with pytest.raises(
        ProviderStateCoherenceError,
        match="stale or missing ProviderSpec",
    ):
        _restored_graph_state(runtime)


def test_v4_01_capture_rejects_a_route_after_same_id_connection_replacement(
    tmp_path: Path,
) -> None:
    """C: a surviving route cannot look current after its connection is replaced."""
    runtime = _runtime(tmp_path)
    connection = _connect_deepseek_with_dependents(runtime)
    runtime.models.remove("deepseek-chat", provider_id="deepseek")

    runtime.connections.remove("deepseek:main")
    replacement = runtime.connections.register(_replacement_connection(connection))

    assert connection is not replacement
    assert runtime.routes.get("deepseek:main:deepseek-chat") is not None
    with pytest.raises(
        ProviderStateCoherenceError,
        match="stale or missing ProviderConnection",
    ):
        _restored_graph_state(runtime)


def test_v4_01_coherent_restore_recaptures_successfully(tmp_path: Path) -> None:
    """D: object identity is local to each coherent runtime generation."""
    runtime = _runtime(tmp_path)
    _connect_deepseek_with_dependents(runtime)
    state = _restored_graph_state(runtime)

    restored = restore_provider_registry_state(state)

    assert (
        capture_provider_registry_state(
            restored.providers,
            restored.manifests,
            restored.models,
            restored.connections,
            restored.routes,
            revision=state.revision,
            audit_log=state.audit_log,
        )
        == state
    )


def test_v4_01_coordinator_commit_cannot_publish_a_stale_graph(
    tmp_path: Path,
) -> None:
    """E: a stale item-level graph can never advance the durable revision."""
    repository = FileProviderRegistryStateRepository(tmp_path / "state.json")
    runtime = _runtime(tmp_path, repository=repository)
    coordinator = runtime.coordinator
    assert coordinator is not None
    connection = _connect_deepseek(runtime)
    committed = repository.load()
    assert committed is not None
    revision_before = coordinator.revision
    audit_before = coordinator.audit_log

    runtime.providers.remove("deepseek")

    with pytest.raises(
        ProviderStateCoherenceError,
        match="stale or missing ProviderSpec",
    ):
        coordinator.persist_connection_acceptance(connection)

    assert coordinator.revision == revision_before
    assert coordinator.audit_log == audit_before
    assert repository.load() == committed


def _canonical_codex_proposal(
    runtime: _Runtime,
    **overrides: object,
) -> ConnectionProposal:
    """Build a Codex proposal from the canonical manifest, with forgeries."""
    manifest = runtime.manifests.get("codex")
    assert manifest is not None
    assert manifest.requires_isolation is True
    fields: dict[str, object] = {
        "provider_id": "codex",
        "display_name": manifest.display_name,
        "billing_class": manifest.billing_class,
        "endpoint": manifest.default_base_url,
        "requires_isolation": True,
        "source_home": str(Path("/tmp/v4-forged-source-home")),
    }
    fields.update(overrides)
    return ConnectionProposal(**fields)  # type: ignore[arg-type]


def _assert_acceptance_untouched(
    runtime: _Runtime,
    validator: _RecordingValidator,
    repository: FileProviderRegistryStateRepository,
    committed: ProviderRegistryState | None,
    *,
    validator_calls_before: int,
    expected_connections: tuple[ProviderConnection, ...] = (),
) -> None:
    """Prove a rejected acceptance consulted and changed nothing.

    ``validator_calls_before`` and ``expected_connections`` describe the state
    that already existed before the rejected call, so "unchanged" is asserted
    against real pre-existing state rather than against an empty runtime.
    """
    coordinator = runtime.coordinator
    assert coordinator is not None
    assert len(validator.calls) == validator_calls_before
    assert runtime.connections.list() == expected_connections
    assert runtime.connections.get("codex:main") is None
    assert not runtime.credentials.has(credential_ref("codex", "main"))
    assert not (runtime.profiles_root / "codex").exists()
    expected_revision = 0 if committed is None else committed.revision
    expected_audit = () if committed is None else committed.audit_log
    assert coordinator.revision == expected_revision
    assert coordinator.audit_log == expected_audit
    assert repository.load() == committed


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("requires_isolation", False, "proposal isolation policy contradicts"),
        ("endpoint", _V4_FORGED_ENDPOINT, "proposal endpoint contradicts"),
        ("billing_class", BillingClass.PAYG, "proposal billing class contradicts"),
        ("display_name", "Forged Codex", "proposal display name contradicts"),
    ],
)
def test_v4_02_forged_codex_proposals_are_rejected_before_side_effects(
    tmp_path: Path,
    field: str,
    value: object,
    message: str,
) -> None:
    """F/G/H/I: no proposal field can override canonical Codex authority.

    A real DeepSeek connection is already committed, so the rejection is proven
    against live durable state: revision, audit log, repository document,
    connection inventory, credential store and profile root all stay untouched.
    """
    repository = FileProviderRegistryStateRepository(tmp_path / "state.json")
    validator = _RecordingValidator()
    runtime = _runtime(tmp_path, repository=repository, validator=validator)
    existing = _connect_deepseek(runtime)
    committed = repository.load()
    assert committed is not None
    assert committed.revision == 1
    validator_calls_before = len(validator.calls)
    proposal = _canonical_codex_proposal(runtime, **{field: value})

    with pytest.raises(ProviderStateCoherenceError, match=message):
        runtime.service.accept(proposal, credential=_SECRET)

    _assert_acceptance_untouched(
        runtime,
        validator,
        repository,
        committed,
        validator_calls_before=validator_calls_before,
        expected_connections=(existing,),
    )


def test_v4_02_stale_proposal_is_rejected_against_current_authority(
    tmp_path: Path,
) -> None:
    """J: a proposal minted under a replaced authority fails closed."""
    repository = FileProviderRegistryStateRepository(tmp_path / "state.json")
    validator = _RecordingValidator()
    runtime = _runtime(tmp_path, repository=repository, validator=validator)
    existing = _connect_deepseek(runtime)
    committed = repository.load()
    assert committed is not None
    assert committed.revision == 1
    validator_calls_before = len(validator.calls)
    proposal = _canonical_codex_proposal(runtime)

    runtime.providers.remove("codex")
    runtime.providers.register(
        ProviderSpec(
            id="codex",
            provider_type="remote",
            api_style="chat_completions",
            base_url="https://api.openai.com/v1",
        )
    )

    with pytest.raises(
        ProviderStateCoherenceError,
        match="proposal provider has no active canonical manifest",
    ):
        runtime.service.accept(proposal, credential=_SECRET)

    _assert_acceptance_untouched(
        runtime,
        validator,
        repository,
        committed,
        validator_calls_before=validator_calls_before,
        expected_connections=(existing,),
    )


def test_v4_02_isolation_strengthening_is_still_permitted(tmp_path: Path) -> None:
    """K: canonical policy is a minimum a proposal may strengthen, never weaken."""
    repository = FileProviderRegistryStateRepository(tmp_path / "state.json")
    validator = _RecordingValidator()
    runtime = _runtime(tmp_path, repository=repository, validator=validator)
    manifest = runtime.manifests.get("deepseek")
    assert manifest is not None
    assert manifest.requires_isolation is False
    source = _write_subscription_source("codex", tmp_path)
    stricter = ConnectionProposal(
        provider_id="deepseek",
        display_name=manifest.display_name,
        billing_class=manifest.billing_class,
        endpoint=manifest.default_base_url,
        source_home=str(source),
        requires_isolation=True,
    )

    with pytest.raises(ProviderIsolationError) as excinfo:
        runtime.service.accept(stricter, credential=_SECRET)

    # The failure is the pre-existing isolation prerequisite, never the new
    # canonical-authority gate, and the validator was still not consulted.
    assert not isinstance(excinfo.value, ProviderStateCoherenceError)
    assert "contradicts canonical" not in str(excinfo.value)
    assert validator.calls == []
    assert runtime.connections.list() == ()


def _foreign_deepseek_manifest(runtime: _Runtime) -> ProviderManifest:
    """Build a same-id DeepSeek manifest that is not the canonical one."""
    canonical = runtime.manifests.get("deepseek")
    assert canonical is not None
    foreign = ProviderManifest(
        provider_id="deepseek",
        display_name=canonical.display_name,
        billing_class=canonical.billing_class,
        default_base_url=_V4_FOREIGN_MANIFEST_URL,
        auth_scheme=FIRST_WAVE_AUTH_SCHEME,
        activation_allowlist=("deepseek-chat",),
    )
    assert foreign is not canonical
    return foreign


def test_v4_03_discovery_rejects_a_foreign_same_id_manifest(
    tmp_path: Path,
) -> None:
    """L: only the exact active canonical manifest may drive discovery."""
    repository = FileProviderRegistryStateRepository(tmp_path / "state.json")
    runtime = _runtime(tmp_path, repository=repository)
    coordinator = runtime.coordinator
    assert coordinator is not None
    connection = _connect_deepseek(runtime)
    committed = repository.load()
    assert committed is not None
    revision_before = coordinator.revision
    audit_before = coordinator.audit_log
    client = _RecordingClient(("deepseek-chat", "deepseek-reasoner"))
    foreign = _foreign_deepseek_manifest(runtime)

    with pytest.raises(
        ProviderStateCoherenceError,
        match="discovery manifest is not the active canonical manifest",
    ):
        coordinator.discover_models(connection, foreign, client, seen_at=T0)

    assert client.list_calls == 0
    assert client.inference_calls == []
    assert runtime.routes.list() == ()
    assert coordinator.revision == revision_before
    assert coordinator.audit_log == audit_before
    assert repository.load() == committed


def test_v4_03_discovery_rejects_a_stale_formerly_active_manifest(
    tmp_path: Path,
) -> None:
    """M: a manifest that was once canonical is no longer authority."""
    repository = FileProviderRegistryStateRepository(tmp_path / "state.json")
    runtime = _runtime(tmp_path, repository=repository)
    coordinator = runtime.coordinator
    assert coordinator is not None
    connection = _connect_deepseek(runtime)
    committed = repository.load()
    assert committed is not None
    revision_before = coordinator.revision
    audit_before = coordinator.audit_log
    previous = runtime.manifests.get("deepseek")
    assert previous is not None

    runtime.providers.remove("deepseek")
    runtime.providers.register(
        ProviderSpec(
            id="deepseek",
            provider_type="remote",
            api_style="chat_completions",
            base_url="https://api.deepseek.com/v1",
        )
    )
    replacement = runtime.manifests.register(
        ProviderManifest(
            provider_id="deepseek",
            display_name=previous.display_name,
            billing_class=previous.billing_class,
            default_base_url=previous.default_base_url,
            auth_scheme=FIRST_WAVE_AUTH_SCHEME,
        )
    )
    assert replacement is not previous
    client = _RecordingClient(("deepseek-chat",))

    with pytest.raises(
        ProviderStateCoherenceError,
        match="discovery manifest is not the active canonical manifest",
    ):
        coordinator.discover_models(connection, previous, client, seen_at=T0)

    assert client.list_calls == 0
    assert runtime.routes.list() == ()
    assert coordinator.revision == revision_before
    assert coordinator.audit_log == audit_before
    assert repository.load() == committed


def test_v4_04_older_discovery_snapshot_is_rejected_before_the_client(
    tmp_path: Path,
) -> None:
    """N: T1 persisted, T0 refused, ``last_seen_at`` never regresses."""
    repository = FileProviderRegistryStateRepository(tmp_path / "state.json")
    runtime = _runtime(tmp_path, repository=repository)
    coordinator = runtime.coordinator
    assert coordinator is not None
    connection = _connect_deepseek(runtime)
    manifest = runtime.manifests.get("deepseek")
    assert manifest is not None
    coordinator.discover_models(
        connection, manifest, _RecordingClient(("deepseek-chat",)), seen_at=T1
    )
    committed = repository.load()
    assert committed is not None
    revision_before = coordinator.revision
    audit_before = coordinator.audit_log
    client = _RecordingClient(("deepseek-chat",))

    with pytest.raises(
        ProviderStateCoherenceError,
        match="discovery seen_at precedes current route state",
    ):
        coordinator.discover_models(connection, manifest, client, seen_at=T0)

    assert client.list_calls == 0
    route = runtime.routes.get("deepseek:main:deepseek-chat")
    assert route is not None
    assert route.last_seen_at == T1
    assert route.available is True
    assert coordinator.revision == revision_before
    assert coordinator.audit_log == audit_before
    assert repository.load() == committed


def test_v4_04_exact_timestamp_repeat_keeps_v3_noop_semantics(
    tmp_path: Path,
) -> None:
    """O: equality stays valid — the same pass remains a true no-op."""
    repository = FileProviderRegistryStateRepository(tmp_path / "state.json")
    runtime = _runtime(tmp_path, repository=repository)
    coordinator = runtime.coordinator
    assert coordinator is not None
    connection = _connect_deepseek(runtime)
    manifest = runtime.manifests.get("deepseek")
    assert manifest is not None
    coordinator.discover_models(
        connection, manifest, _RecordingClient(("deepseek-chat",)), seen_at=T1
    )
    committed = repository.load()
    assert committed is not None
    revision_before = coordinator.revision
    audit_before = coordinator.audit_log
    client = _RecordingClient(("deepseek-chat",))

    result = coordinator.discover_models(connection, manifest, client, seen_at=T1)

    assert client.list_calls == 1
    assert result.new_route_ids == ()
    assert result.restored_route_ids == ()
    assert coordinator.revision == revision_before
    assert coordinator.audit_log == audit_before
    assert repository.load() == committed


def test_v4_04_mixed_route_timestamps_use_the_connection_maximum(
    tmp_path: Path,
) -> None:
    """P: one route at T1 and another at T0 still admit a T1 snapshot."""
    repository = FileProviderRegistryStateRepository(tmp_path / "state.json")
    runtime = _runtime(tmp_path, repository=repository)
    coordinator = runtime.coordinator
    assert coordinator is not None
    connection = _connect_deepseek(runtime)
    manifest = runtime.manifests.get("deepseek")
    assert manifest is not None
    coordinator.discover_models(
        connection,
        manifest,
        _RecordingClient(("deepseek-chat", "deepseek-reasoner")),
        seen_at=T0,
    )
    coordinator.discover_models(
        connection, manifest, _RecordingClient(("deepseek-chat",)), seen_at=T1
    )
    older = runtime.routes.get("deepseek:main:deepseek-reasoner")
    assert older is not None
    assert older.last_seen_at == T0

    result = coordinator.discover_models(
        connection,
        manifest,
        _RecordingClient(("deepseek-chat", "deepseek-reasoner")),
        seen_at=T1,
    )

    assert result.restored_route_ids == ("deepseek:main:deepseek-reasoner",)
    restored = runtime.routes.get("deepseek:main:deepseek-reasoner")
    assert restored is not None
    assert restored.last_seen_at == T1
    assert restored.available is True
