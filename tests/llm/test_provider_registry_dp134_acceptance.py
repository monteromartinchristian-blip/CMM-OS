"""Connected acceptance for DP-134 — canonical, persistent, fail-closed registry.

``AT-DP-134`` exercises the real canonical components (or their official
in-memory implementations) end to end — no isolated mocks stand in for the
provider authority, the persistence repository, the isolation machinery or the
discovery path. Scenarios A–M map one-to-one to the Design Point statement in
``docs/superpowers/specs/2026-09-14-phase-11.34-provider-registry-remediation-v1-design.md``
§10.

The only fakes allowed are boundary fakes required for a hermetic run: an
injected detector environment, injected filesystem homes under ``tmp_path``,
the official in-memory credential store, and a recording discovery client that
exposes only ``list_models()`` where network access would otherwise occur.
"""

from __future__ import annotations

import dataclasses
import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import pytest

from kernel.llm.credential_store import InMemoryCredentialStore
from kernel.llm.exceptions import ProviderError
from kernel.llm.first_wave_providers import (
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
    ProviderStateSchemaError,
    ProviderStateSerializationError,
)
from kernel.llm.provider_state_coordinator import ProviderRegistryStateCoordinator
from kernel.llm.provider_state_repository import (
    FileProviderRegistryStateRepository,
    capture_provider_registry_state,
    restore_provider_registry_state,
)
from kernel.llm.subscription_profiles import SubscriptionProfileManager

T0 = datetime(2026, 9, 14, 10, 0, tzinfo=timezone.utc)
T1 = datetime(2026, 9, 14, 12, 0, tzinfo=timezone.utc)

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


def _runtime(
    tmp_path: Path,
    *,
    repository: FileProviderRegistryStateRepository | None = None,
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

    def list_models(self) -> tuple[str, ...]:
        return self._models

    def generate(self, **kwargs: object) -> object:
        self.inference_calls.append(kwargs)
        raise AssertionError("inference invoked during administrative discovery")


def test_scenario_i_durable_no_secret_restart(tmp_path: Path) -> None:
    """The aggregate survives a process-equivalent restart without secrets."""
    repository = FileProviderRegistryStateRepository(tmp_path / "state.json")
    runtime = _runtime(tmp_path, repository=repository)
    connection = _connect_deepseek(runtime)
    manifest = runtime.manifests.get("deepseek")
    assert manifest is not None

    # Two discovery passes: the second omits deepseek-reasoner, so its route
    # stays in the catalog but unavailable with its first-sight history.
    discover_models(
        connection,
        manifest,
        _RecordingClient(("deepseek-chat", "deepseek-reasoner")),
        runtime.routes,
        seen_at=T0,
    )
    discover_models(
        connection,
        manifest,
        _RecordingClient(("deepseek-chat",)),
        runtime.routes,
        seen_at=T1,
    )
    vanished = runtime.routes.get("deepseek:main:deepseek-reasoner")
    assert vanished is not None
    assert vanished.available is False
    assert vanished.last_seen_at == T0

    # Persist the discovery results through the canonical capture/save path
    # (discovery itself is administrative and never persists implicitly).
    persisted = repository.load()
    assert persisted is not None
    repository.save(
        capture_provider_registry_state(
            runtime.providers,
            runtime.manifests,
            runtime.models,
            runtime.connections,
            runtime.routes,
            revision=persisted.revision + 1,
            audit_log=persisted.audit_log,
        )
    )
    persisted = repository.load()
    assert persisted is not None

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
