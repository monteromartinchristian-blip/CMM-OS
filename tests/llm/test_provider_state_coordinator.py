"""Focused tests for the Provider Registry state coordinator (MAJOR-V2-02).

One coordinator owns the Provider Registry revision/audit commit seam: a
canonical mutation is captured into one coherent aggregate, saved through the
canonical repository, and only then published as the new in-memory revision and
audit log. These tests pin that sequence — including the failure path, where a
failed save must leave the coordinator believing nothing committed.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import pytest

from kernel.llm.credential_store import InMemoryCredentialStore
from kernel.llm.model_catalog import ModelCatalog
from kernel.llm.model_routes import ModelRouteCatalog
from kernel.llm.provider_connections import (
    BillingClass,
    ConnectionStatus,
    ProviderConnection,
    ProviderConnectionRegistry,
)
from kernel.llm.provider_manifests import ProviderManifest, ProviderManifestRegistry
from kernel.llm.provider_registry import ProviderRegistry, ProviderSpec
from kernel.llm.provider_state import (
    ProviderRegistryAuditRecord,
    ProviderRegistryState,
    ProviderStateCoherenceError,
)
from kernel.llm.provider_state_coordinator import ProviderRegistryStateCoordinator
from kernel.llm.provider_state_repository import (
    FileProviderRegistryStateRepository,
    InMemoryProviderRegistryStateRepository,
    ProviderRegistryStateRepository,
    restore_provider_registry_state,
)

T0 = datetime(2026, 9, 15, 10, 0, tzinfo=timezone.utc)
T1 = datetime(2026, 9, 15, 12, 0, tzinfo=timezone.utc)
T2 = datetime(2026, 9, 15, 14, 0, tzinfo=timezone.utc)

_DEEPSEEK_URL = "https://api.deepseek.com/v1"
_QWEN_URL = "https://token-plan.example.invalid/v1"
_SECRET = "sk-coordinator-test-secret"


@dataclass(frozen=True, slots=True)
class _Runtime:
    """The canonical component graph plus one coordinator over it."""

    coordinator: ProviderRegistryStateCoordinator
    providers: ProviderRegistry
    manifests: ProviderManifestRegistry
    models: ModelCatalog
    connections: ProviderConnectionRegistry
    routes: ModelRouteCatalog
    repository: ProviderRegistryStateRepository
    credentials: InMemoryCredentialStore


def _spec(provider_id: str, base_url: str) -> ProviderSpec:
    return ProviderSpec(
        id=provider_id,
        provider_type="remote",
        api_style="chat_completions",
        base_url=base_url,
    )


def _manifest(
    provider_id: str,
    base_url: str,
    billing: BillingClass,
    activation_allowlist: tuple[str, ...] = (),
) -> ProviderManifest:
    return ProviderManifest(
        provider_id=provider_id,
        display_name=provider_id,
        billing_class=billing,
        default_base_url=base_url,
        auth_scheme="bearer",
        activation_allowlist=activation_allowlist,
    )


def _runtime(
    tmp_path: Path,
    *,
    repository: ProviderRegistryStateRepository | None = None,
    revision: int = 0,
    allowlist: tuple[str, ...] = (),
) -> _Runtime:
    """Wire the canonical components and one coordinator over them."""
    providers = ProviderRegistry()
    providers.register(_spec("deepseek", _DEEPSEEK_URL))
    providers.register(_spec("qwen-token-plan", _QWEN_URL))
    manifests = ProviderManifestRegistry(providers)
    manifests.register(
        _manifest(
            "deepseek", _DEEPSEEK_URL, BillingClass.PAYG, activation_allowlist=allowlist
        )
    )
    manifests.register(
        _manifest("qwen-token-plan", _QWEN_URL, BillingClass.SUBSCRIPTION)
    )
    connections = ProviderConnectionRegistry(providers)
    models = ModelCatalog(providers)
    routes = ModelRouteCatalog(connections)
    wired_repository = repository or InMemoryProviderRegistryStateRepository()
    credentials = InMemoryCredentialStore()
    coordinator = ProviderRegistryStateCoordinator(
        providers=providers,
        manifests=manifests,
        models=models,
        connections=connections,
        routes=routes,
        repository=wired_repository,
        revision=revision,
    )
    return _Runtime(
        coordinator=coordinator,
        providers=providers,
        manifests=manifests,
        models=models,
        connections=connections,
        routes=routes,
        repository=wired_repository,
        credentials=credentials,
    )


def _connection(
    runtime: _Runtime,
    *,
    status: ConnectionStatus = ConnectionStatus.AUTH_REQUIRED,
    credential_ref: str | None = None,
) -> ProviderConnection:
    """Register one canonical connection and return the stored identity."""
    return runtime.connections.register(
        ProviderConnection(
            connection_id="deepseek:main",
            provider_id="deepseek",
            display_name="DeepSeek",
            billing_class=BillingClass.PAYG,
            credential_ref=credential_ref,
            endpoint=_DEEPSEEK_URL,
            isolation_profile_ref=None,
            status=status,
            created_at=T0,
        )
    )


class _SwitchableStateRepository:
    """Repository whose ``save`` can be toggled to fail (failure-path probe)."""

    def __init__(self) -> None:
        self._state: ProviderRegistryState | None = None
        self.fail = False
        self.save_calls = 0

    def load(self) -> ProviderRegistryState | None:
        return self._state

    def save(self, state: ProviderRegistryState) -> None:
        self.save_calls += 1
        if self.fail:
            raise RuntimeError("persistence failed")
        self._state = state


class _DiscoveryClient:
    """Administrative-only transport: it exposes the advertised model list."""

    def __init__(self, models: tuple[str, ...]) -> None:
        self._models = models

    def list_models(self) -> tuple[str, ...]:
        return self._models


def _active_manifest(
    runtime: _Runtime, provider_id: str = "deepseek"
) -> ProviderManifest:
    """Return the canonical manifest for ``provider_id``, asserting it is active."""
    manifest = runtime.manifests.get(provider_id)
    assert manifest is not None
    return manifest


# --- construction -----------------------------------------------------------


def test_coordinator_exposes_initial_revision_and_audit_log(tmp_path: Path) -> None:
    runtime = _runtime(
        tmp_path,
        repository=FileProviderRegistryStateRepository(tmp_path / "state.json"),
        revision=7,
    )

    assert runtime.coordinator.revision == 7
    assert runtime.coordinator.audit_log == ()


def test_coordinator_defaults_to_revision_zero(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)

    assert runtime.coordinator.revision == 0
    assert runtime.coordinator.audit_log == ()


def test_coordinator_seeds_its_audit_log_from_the_persisted_history(
    tmp_path: Path,
) -> None:
    record = ProviderRegistryAuditRecord(
        revision=1,
        event_type="connection.accepted",
        entity_kind="connection",
        entity_id="deepseek:main",
        occurred_at=T0,
    )

    runtime = _runtime(tmp_path, revision=1)
    seeded = ProviderRegistryStateCoordinator(
        providers=runtime.providers,
        manifests=runtime.manifests,
        models=runtime.models,
        connections=runtime.connections,
        routes=runtime.routes,
        repository=runtime.repository,
        revision=1,
        audit_log=(record,),
    )

    assert seeded.revision == 1
    assert seeded.audit_log == (record,)


def test_coordinator_rejects_a_negative_revision(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)

    with pytest.raises(ValueError, match="revision cannot be negative"):
        ProviderRegistryStateCoordinator(
            providers=runtime.providers,
            manifests=runtime.manifests,
            models=runtime.models,
            connections=runtime.connections,
            routes=runtime.routes,
            repository=runtime.repository,
            revision=-1,
        )


def test_coordinator_rejects_a_non_integer_revision(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)

    with pytest.raises(TypeError, match="revision must be an int"):
        ProviderRegistryStateCoordinator(
            providers=runtime.providers,
            manifests=runtime.manifests,
            models=runtime.models,
            connections=runtime.connections,
            routes=runtime.routes,
            repository=runtime.repository,
            revision=True,
        )


@pytest.mark.parametrize(
    "attribute",
    ["providers", "manifests", "models", "connections", "routes", "repository"],
)
def test_coordinator_requires_canonical_component_types(
    tmp_path: Path, attribute: str
) -> None:
    runtime = _runtime(tmp_path)
    components: dict[str, object] = {
        "providers": runtime.providers,
        "manifests": runtime.manifests,
        "models": runtime.models,
        "connections": runtime.connections,
        "routes": runtime.routes,
        "repository": runtime.repository,
    }
    components[attribute] = object()

    with pytest.raises(TypeError):
        ProviderRegistryStateCoordinator(**components)  # type: ignore[arg-type]


def test_coordinator_rejects_a_non_audit_log_entry(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)

    with pytest.raises(TypeError, match="audit_log"):
        ProviderRegistryStateCoordinator(
            providers=runtime.providers,
            manifests=runtime.manifests,
            models=runtime.models,
            connections=runtime.connections,
            routes=runtime.routes,
            repository=runtime.repository,
            audit_log=(object(),),  # type: ignore[arg-type]
        )


# --- cross-authority construction (MAJOR-V3-01) -----------------------------


def _graph(
    base_url: str,
) -> tuple[
    ProviderRegistry,
    ProviderManifestRegistry,
    ModelCatalog,
    ProviderConnectionRegistry,
    ModelRouteCatalog,
]:
    """One live authority with the same ``deepseek`` id and every bound catalog.

    Two of these hold different ``ProviderSpec`` objects and different base
    URLs under the same normalized provider id, so provider-id equality alone
    can never satisfy the exact-object graph guards (MAJOR-V3-01).
    """
    providers = ProviderRegistry()
    providers.register(_spec("deepseek", base_url))
    manifests = ProviderManifestRegistry(providers)
    manifests.register(_manifest("deepseek", base_url, BillingClass.PAYG))
    connections = ProviderConnectionRegistry(providers)
    return (
        providers,
        manifests,
        ModelCatalog(providers),
        connections,
        ModelRouteCatalog(connections),
    )


def test_coordinator_rejects_a_foreign_manifest_registry(tmp_path: Path) -> None:
    """The audited V3 reproduction: same id in two authorities is not identity."""
    providers, _, models, connections, routes = _graph("https://canonical.example/v1")
    _, foreign_manifests, _, _, _ = _graph("https://foreign.example/v1")
    assert providers.has("deepseek")
    assert foreign_manifests.get("deepseek") is not None

    with pytest.raises(
        ProviderStateCoherenceError,
        match="manifest registry is bound to a different ProviderRegistry",
    ):
        ProviderRegistryStateCoordinator(
            providers=providers,
            manifests=foreign_manifests,
            models=models,
            connections=connections,
            routes=routes,
            repository=InMemoryProviderRegistryStateRepository(),
        )


def test_coordinator_rejects_a_foreign_model_catalog(tmp_path: Path) -> None:
    providers, manifests, _, connections, routes = _graph(
        "https://canonical.example/v1"
    )
    _, _, foreign_models, _, _ = _graph("https://foreign.example/v1")

    with pytest.raises(
        ProviderStateCoherenceError,
        match="model catalog is bound to a different ProviderRegistry",
    ):
        ProviderRegistryStateCoordinator(
            providers=providers,
            manifests=manifests,
            models=foreign_models,
            connections=connections,
            routes=routes,
            repository=InMemoryProviderRegistryStateRepository(),
        )


def test_coordinator_rejects_a_foreign_connection_registry(tmp_path: Path) -> None:
    providers, manifests, models, _, routes = _graph("https://canonical.example/v1")
    _, _, _, foreign_connections, _ = _graph("https://foreign.example/v1")

    with pytest.raises(
        ProviderStateCoherenceError,
        match="connection registry is bound to a different ProviderRegistry",
    ):
        ProviderRegistryStateCoordinator(
            providers=providers,
            manifests=manifests,
            models=models,
            connections=foreign_connections,
            routes=routes,
            repository=InMemoryProviderRegistryStateRepository(),
        )


def test_coordinator_rejects_a_route_catalog_bound_to_another_connection_registry(
    tmp_path: Path,
) -> None:
    providers, manifests, models, connections, _ = _graph(
        "https://canonical.example/v1"
    )
    _, _, _, _, foreign_routes = _graph("https://canonical.example/v1")

    with pytest.raises(
        ProviderStateCoherenceError,
        match="route catalog is bound to a different ProviderConnectionRegistry",
    ):
        ProviderRegistryStateCoordinator(
            providers=providers,
            manifests=manifests,
            models=models,
            connections=connections,
            routes=foreign_routes,
            repository=InMemoryProviderRegistryStateRepository(),
        )


def test_coordinator_exposes_read_only_canonical_component_bindings(
    tmp_path: Path,
) -> None:
    """Onboarding proves exact identity through these, and they never rebind."""
    runtime = _runtime(tmp_path)

    assert runtime.coordinator.providers is runtime.providers
    assert runtime.coordinator.manifests is runtime.manifests
    assert runtime.coordinator.connections is runtime.connections
    with pytest.raises(AttributeError):
        runtime.coordinator.providers = ProviderRegistry()  # type: ignore[misc]
    assert runtime.coordinator.providers is runtime.providers


# --- connection acceptance commit -------------------------------------------


def test_persist_connection_acceptance_saves_one_revision_and_audit_record(
    tmp_path: Path,
) -> None:
    repository = FileProviderRegistryStateRepository(tmp_path / "state.json")
    runtime = _runtime(tmp_path, repository=repository)
    connection = _connection(runtime, status=ConnectionStatus.AUTH_REQUIRED)

    runtime.coordinator.persist_connection_acceptance(connection, occurred_at=T0)

    state = repository.load()
    assert state is not None
    assert state.revision == 1
    assert runtime.coordinator.revision == 1
    assert runtime.coordinator.audit_log == state.audit_log
    record = state.audit_log[-1]
    assert record.revision == 1
    assert record.event_type == "connection.accepted"
    assert record.entity_kind == "connection"
    assert record.entity_id == "deepseek:main"
    assert record.occurred_at == T0
    assert record.detail == (("status", "auth_required"),)
    assert tuple(item.connection_id for item in state.connections) == ("deepseek:main",)


def test_persist_connection_acceptance_uses_the_connected_event_for_connected(
    tmp_path: Path,
) -> None:
    runtime = _runtime(tmp_path)
    connection = _connection(runtime, status=ConnectionStatus.CONNECTED)

    runtime.coordinator.persist_connection_acceptance(connection, occurred_at=T1)

    assert runtime.coordinator.audit_log[-1].event_type == "provider.connected"
    assert runtime.coordinator.audit_log[-1].detail == (("status", "connected"),)


def test_persist_connection_acceptance_defaults_to_the_current_time(
    tmp_path: Path,
) -> None:
    runtime = _runtime(tmp_path)
    connection = _connection(runtime)

    runtime.coordinator.persist_connection_acceptance(connection)

    assert runtime.coordinator.audit_log[-1].occurred_at.tzinfo is not None


def test_persist_connection_acceptance_rejects_an_unregistered_connection(
    tmp_path: Path,
) -> None:
    repository = FileProviderRegistryStateRepository(tmp_path / "state.json")
    runtime = _runtime(tmp_path, repository=repository)
    unregistered = ProviderConnection(
        connection_id="deepseek:main",
        provider_id="deepseek",
        display_name="DeepSeek",
        billing_class=BillingClass.PAYG,
        credential_ref=None,
        endpoint=_DEEPSEEK_URL,
        isolation_profile_ref=None,
        status=ConnectionStatus.CONNECTED,
    )

    with pytest.raises(ValueError, match="not registered"):
        runtime.coordinator.persist_connection_acceptance(unregistered, occurred_at=T0)

    assert runtime.coordinator.revision == 0
    assert runtime.coordinator.audit_log == ()
    assert repository.load() is None


def test_persist_connection_acceptance_rejects_a_non_connection(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)

    with pytest.raises(TypeError, match="ProviderConnection"):
        runtime.coordinator.persist_connection_acceptance("deepseek:main")  # type: ignore[arg-type]


def test_persisted_acceptance_carries_only_the_opaque_credential_ref(
    tmp_path: Path,
) -> None:
    """The commit seam never widens the secret boundary."""
    path = tmp_path / "state.json"
    runtime = _runtime(tmp_path, repository=FileProviderRegistryStateRepository(path))
    ref = runtime.credentials.put("deepseek", "main", _SECRET)
    connection = _connection(
        runtime, status=ConnectionStatus.CONNECTED, credential_ref=ref
    )

    runtime.coordinator.persist_connection_acceptance(connection, occurred_at=T0)

    payload = path.read_text(encoding="utf-8")
    assert ref in payload
    assert _SECRET not in payload
    assert "sk-" not in payload
    detail = json.dumps(
        [list(pair) for pair in runtime.coordinator.audit_log[-1].detail],
        ensure_ascii=False,
    )
    assert _SECRET not in detail


def test_each_acceptance_advances_exactly_one_revision(tmp_path: Path) -> None:
    repository = FileProviderRegistryStateRepository(tmp_path / "state.json")
    runtime = _runtime(tmp_path, repository=repository)
    first = _connection(runtime)
    runtime.coordinator.persist_connection_acceptance(first, occurred_at=T0)
    second = runtime.connections.register(
        ProviderConnection(
            connection_id="qwen-token-plan:main",
            provider_id="qwen-token-plan",
            display_name="Qwen Token Plan",
            billing_class=BillingClass.SUBSCRIPTION,
            credential_ref=None,
            endpoint=_QWEN_URL,
            isolation_profile_ref=None,
            status=ConnectionStatus.CONNECTED,
        )
    )

    runtime.coordinator.persist_connection_acceptance(second, occurred_at=T1)

    state = repository.load()
    assert state is not None
    assert state.revision == 2
    assert [record.revision for record in state.audit_log] == [1, 2]
    assert [record.entity_id for record in state.audit_log] == [
        "deepseek:main",
        "qwen-token-plan:main",
    ]


# --- failure semantics ------------------------------------------------------


def test_failed_repository_save_does_not_advance_coordinator_revision(
    tmp_path: Path,
) -> None:
    repository = _SwitchableStateRepository()
    repository.fail = True
    runtime = _runtime(tmp_path, repository=repository)
    connection = _connection(runtime, status=ConnectionStatus.CONNECTED)

    with pytest.raises(RuntimeError, match="persistence failed"):
        runtime.coordinator.persist_connection_acceptance(connection, occurred_at=T0)

    assert repository.save_calls == 1
    assert runtime.coordinator.revision == 0
    assert runtime.coordinator.audit_log == ()
    assert repository.load() is None


def test_failed_save_keeps_the_previous_durable_revision_and_audit_log(
    tmp_path: Path,
) -> None:
    """A later failure never rewinds or advances an already committed revision."""
    repository = _SwitchableStateRepository()
    runtime = _runtime(tmp_path, repository=repository)
    runtime.coordinator.persist_connection_acceptance(
        _connection(runtime, status=ConnectionStatus.CONNECTED), occurred_at=T0
    )
    committed = repository.load()
    assert committed is not None
    assert runtime.coordinator.revision == 1

    repository.fail = True
    with pytest.raises(RuntimeError, match="persistence failed"):
        runtime.coordinator.persist_connection_acceptance(
            runtime.connections.get("deepseek:main"), occurred_at=T1
        )

    assert runtime.coordinator.revision == 1
    assert runtime.coordinator.audit_log == committed.audit_log
    assert repository.load() == committed
    assert repository.load().revision == 1


# --- route discovery lifecycle commit (MAJOR-V2-02) -------------------------


def test_discovery_commit_persists_one_route_discovered_record_per_new_route(
    tmp_path: Path,
) -> None:
    repository = FileProviderRegistryStateRepository(tmp_path / "state.json")
    runtime = _runtime(tmp_path, repository=repository)
    connection = _connection(runtime, status=ConnectionStatus.CONNECTED)

    result = runtime.coordinator.discover_models(
        connection,
        _active_manifest(runtime),
        _DiscoveryClient(("deepseek-chat", "deepseek-reasoner")),
        seen_at=T0,
    )

    assert result.connection_id == "deepseek:main"
    assert result.new_route_ids == (
        "deepseek:main:deepseek-chat",
        "deepseek:main:deepseek-reasoner",
    )
    assert result.unavailable_route_ids == ()
    assert result.restored_route_ids == ()
    state = repository.load()
    assert state is not None
    assert state.revision == 1
    assert runtime.coordinator.revision == 1
    assert runtime.coordinator.audit_log == state.audit_log
    assert [record.event_type for record in state.audit_log] == [
        "route.discovered",
        "route.discovered",
    ]
    assert [record.revision for record in state.audit_log] == [1, 1]
    assert [record.entity_kind for record in state.audit_log] == ["route", "route"]
    assert [record.entity_id for record in state.audit_log] == [
        "deepseek:main:deepseek-chat",
        "deepseek:main:deepseek-reasoner",
    ]
    assert state.audit_log[0].occurred_at == T0
    assert state.audit_log[0].detail == (
        ("connection_id", "deepseek:main"),
        ("available", "true"),
    )
    assert [route.route_id for route in state.routes] == [
        "deepseek:main:deepseek-chat",
        "deepseek:main:deepseek-reasoner",
    ]


def test_discovery_lifecycle_audit_sequence_is_persisted_in_order(
    tmp_path: Path,
) -> None:
    """Discover → disappear → reappear: one revision per real transition."""
    repository = FileProviderRegistryStateRepository(tmp_path / "state.json")
    runtime = _runtime(tmp_path, repository=repository)
    connection = _connection(runtime, status=ConnectionStatus.CONNECTED)
    manifest = _active_manifest(runtime)

    runtime.coordinator.discover_models(
        connection,
        manifest,
        _DiscoveryClient(("deepseek-chat", "deepseek-reasoner")),
        seen_at=T0,
    )
    runtime.coordinator.discover_models(
        connection, manifest, _DiscoveryClient(("deepseek-chat",)), seen_at=T1
    )
    runtime.coordinator.discover_models(
        connection,
        manifest,
        _DiscoveryClient(("deepseek-chat", "deepseek-reasoner")),
        seen_at=T2,
    )

    state = repository.load()
    assert state is not None
    assert state.revision == 3
    assert runtime.coordinator.revision == 3
    assert [record.revision for record in state.audit_log] == [1, 1, 2, 3]
    assert [record.event_type for record in state.audit_log] == [
        "route.discovered",
        "route.discovered",
        "route.unavailable",
        "route.restored",
    ]
    assert state.audit_log[2].entity_id == "deepseek:main:deepseek-reasoner"
    assert state.audit_log[2].entity_kind == "route"
    assert state.audit_log[2].occurred_at == T1
    assert state.audit_log[2].detail == (
        ("connection_id", "deepseek:main"),
        ("available", "false"),
    )
    assert state.audit_log[3].entity_id == "deepseek:main:deepseek-reasoner"
    assert state.audit_log[3].occurred_at == T2
    assert state.audit_log[3].detail == (
        ("connection_id", "deepseek:main"),
        ("available", "true"),
    )
    reasoner = runtime.routes.get("deepseek:main:deepseek-reasoner")
    assert reasoner is not None
    assert reasoner.available is True
    assert reasoner.first_seen_at == T0
    assert reasoner.last_seen_at == T2


def test_discovery_lifecycle_audit_survives_a_restart(tmp_path: Path) -> None:
    repository = FileProviderRegistryStateRepository(tmp_path / "state.json")
    runtime = _runtime(tmp_path, repository=repository)
    connection = _connection(runtime, status=ConnectionStatus.CONNECTED)
    manifest = _active_manifest(runtime)

    runtime.coordinator.discover_models(
        connection,
        manifest,
        _DiscoveryClient(("deepseek-chat", "deepseek-reasoner")),
        seen_at=T0,
    )
    runtime.coordinator.discover_models(
        connection, manifest, _DiscoveryClient(("deepseek-chat",)), seen_at=T1
    )
    runtime.coordinator.discover_models(
        connection,
        manifest,
        _DiscoveryClient(("deepseek-chat", "deepseek-reasoner")),
        seen_at=T2,
    )

    persisted = repository.load()
    assert persisted is not None
    restored = restore_provider_registry_state(persisted)

    assert restored.revision == 3
    assert [record.revision for record in restored.audit_log] == [1, 1, 2, 3]
    assert [record.event_type for record in restored.audit_log] == [
        "route.discovered",
        "route.discovered",
        "route.unavailable",
        "route.restored",
    ]
    restored_reasoner = restored.routes.get("deepseek:main:deepseek-reasoner")
    assert restored_reasoner is not None
    assert restored_reasoner.available is True
    assert restored_reasoner.first_seen_at == T0
    assert restored_reasoner.last_seen_at == T2


def test_discovery_audit_detail_never_carries_credential_material(
    tmp_path: Path,
) -> None:
    """The commit seam never widens the secret boundary."""
    path = tmp_path / "state.json"
    runtime = _runtime(tmp_path, repository=FileProviderRegistryStateRepository(path))
    ref = runtime.credentials.put("deepseek", "main", _SECRET)
    connection = _connection(
        runtime, status=ConnectionStatus.CONNECTED, credential_ref=ref
    )

    runtime.coordinator.discover_models(
        connection,
        _active_manifest(runtime),
        _DiscoveryClient(("deepseek-chat",)),
        seen_at=T0,
    )

    payload = path.read_text(encoding="utf-8")
    assert ref in payload
    assert _SECRET not in payload
    assert "sk-" not in payload
    for record in runtime.coordinator.audit_log:
        assert tuple(key for key, _ in record.detail) == ("connection_id", "available")


def test_no_op_discovery_scan_does_not_advance_the_revision(tmp_path: Path) -> None:
    """Refreshing routes that are already known and available is not a transition.

    Contract: a discovery pass commits exactly one revision when it produced at
    least one route lifecycle transition (discovered / unavailable / restored).
    A pass that produced none — here, the same models advertised again — marks
    the routes seen and persists nothing, so the durable revision and the audit
    log stay exactly where they were.
    """
    repository = _SwitchableStateRepository()
    runtime = _runtime(tmp_path, repository=repository)
    connection = _connection(runtime, status=ConnectionStatus.CONNECTED)
    manifest = _active_manifest(runtime)

    runtime.coordinator.discover_models(
        connection, manifest, _DiscoveryClient(("deepseek-chat",)), seen_at=T0
    )
    assert repository.save_calls == 1
    first_pass = runtime.routes.get("deepseek:main:deepseek-chat")
    assert first_pass is not None
    assert first_pass.last_seen_at == T0

    runtime.coordinator.discover_models(
        connection, manifest, _DiscoveryClient(("deepseek-chat",)), seen_at=T1
    )

    assert repository.save_calls == 1
    assert runtime.coordinator.revision == 1
    assert [record.revision for record in runtime.coordinator.audit_log] == [1]
    refreshed = runtime.routes.get("deepseek:main:deepseek-chat")
    assert refreshed is not None
    assert refreshed.last_seen_at == T1
    persisted = repository.load()
    assert persisted is not None
    assert persisted.revision == 1
    persisted_route = persisted.routes[0]
    assert persisted_route.route_id == "deepseek:main:deepseek-chat"
    assert persisted_route.last_seen_at == T0


def test_empty_discovery_result_is_a_no_op_scan(tmp_path: Path) -> None:
    """An empty administrative response reconciles nothing and commits nothing."""
    repository = _SwitchableStateRepository()
    runtime = _runtime(tmp_path, repository=repository)
    connection = _connection(runtime, status=ConnectionStatus.CONNECTED)

    result = runtime.coordinator.discover_models(
        connection, _active_manifest(runtime), _DiscoveryClient(()), seen_at=T0
    )

    assert result.discovered_route_ids == ()
    assert result.unavailable_route_ids == ()
    assert repository.save_calls == 0
    assert repository.load() is None
    assert runtime.coordinator.revision == 0
    assert runtime.coordinator.audit_log == ()
    assert runtime.routes.list() == ()


def test_inactive_first_sight_route_is_discovered_and_unavailable(
    tmp_path: Path,
) -> None:
    """Registration and activation are separate facts, so both are audited."""
    repository = FileProviderRegistryStateRepository(tmp_path / "state.json")
    runtime = _runtime(tmp_path, repository=repository, allowlist=("deepseek-chat",))
    connection = _connection(runtime, status=ConnectionStatus.CONNECTED)
    manifest = _active_manifest(runtime)

    runtime.coordinator.discover_models(
        connection,
        manifest,
        _DiscoveryClient(("deepseek-chat", "deepseek-reasoner")),
        seen_at=T0,
    )

    state = repository.load()
    assert state is not None
    assert [(record.event_type, record.entity_id) for record in state.audit_log] == [
        ("route.discovered", "deepseek:main:deepseek-chat"),
        ("route.discovered", "deepseek:main:deepseek-reasoner"),
        ("route.unavailable", "deepseek:main:deepseek-reasoner"),
    ]
    assert state.audit_log[1].detail == (
        ("connection_id", "deepseek:main"),
        ("available", "false"),
    )
    deferred = runtime.routes.get("deepseek:main:deepseek-reasoner")
    assert deferred is not None
    assert deferred.available is False


def test_repeated_inactive_scan_reports_no_further_transition(tmp_path: Path) -> None:
    """An already-inactive route stays inactive without a spurious record."""
    repository = _SwitchableStateRepository()
    runtime = _runtime(tmp_path, repository=repository, allowlist=("deepseek-chat",))
    connection = _connection(runtime, status=ConnectionStatus.CONNECTED)
    manifest = _active_manifest(runtime)

    runtime.coordinator.discover_models(
        connection,
        manifest,
        _DiscoveryClient(("deepseek-chat", "deepseek-reasoner")),
        seen_at=T0,
    )
    runtime.coordinator.discover_models(
        connection,
        manifest,
        _DiscoveryClient(("deepseek-chat", "deepseek-reasoner")),
        seen_at=T1,
    )

    assert repository.save_calls == 1
    assert runtime.coordinator.revision == 1
    deferred = runtime.routes.get("deepseek:main:deepseek-reasoner")
    assert deferred is not None
    assert deferred.available is False


def test_failed_discovery_save_restores_the_route_catalog(tmp_path: Path) -> None:
    repository = _SwitchableStateRepository()
    repository.fail = True
    runtime = _runtime(tmp_path, repository=repository)
    connection = _connection(runtime, status=ConnectionStatus.CONNECTED)
    routes_before = runtime.routes.list()

    with pytest.raises(RuntimeError, match="persistence failed"):
        runtime.coordinator.discover_models(
            connection,
            _active_manifest(runtime),
            _DiscoveryClient(("deepseek-chat",)),
            seen_at=T0,
        )

    assert repository.save_calls == 1
    assert runtime.routes.list() == routes_before
    assert runtime.coordinator.revision == 0
    assert runtime.coordinator.audit_log == ()
    assert repository.load() is None


def test_failed_discovery_save_keeps_the_committed_revision(tmp_path: Path) -> None:
    """A failed pass rolls the catalog back and never rewinds a live revision."""
    repository = _SwitchableStateRepository()
    runtime = _runtime(tmp_path, repository=repository)
    connection = _connection(runtime, status=ConnectionStatus.CONNECTED)
    manifest = _active_manifest(runtime)
    runtime.coordinator.discover_models(
        connection,
        manifest,
        _DiscoveryClient(("deepseek-chat", "deepseek-reasoner")),
        seen_at=T0,
    )
    committed = repository.load()
    assert committed is not None
    routes_before = runtime.routes.list()

    repository.fail = True
    with pytest.raises(RuntimeError, match="persistence failed"):
        runtime.coordinator.discover_models(
            connection, manifest, _DiscoveryClient(("deepseek-chat",)), seen_at=T1
        )

    assert runtime.coordinator.revision == 1
    assert runtime.coordinator.audit_log == committed.audit_log
    assert repository.load() == committed
    assert runtime.routes.list() == routes_before
    still_available = runtime.routes.get("deepseek:main:deepseek-reasoner")
    assert still_available is not None
    assert still_available.available is True
    assert still_available.last_seen_at == T0


def test_discovery_rejects_a_non_connection(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)

    with pytest.raises(TypeError, match="ProviderConnection"):
        runtime.coordinator.discover_models(  # type: ignore[arg-type]
            "deepseek:main",
            _active_manifest(runtime),
            _DiscoveryClient(("deepseek-chat",)),
            seen_at=T0,
        )


def test_discovery_rejects_a_non_manifest(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)
    connection = _connection(runtime)

    with pytest.raises(TypeError, match="ProviderManifest"):
        runtime.coordinator.discover_models(  # type: ignore[arg-type]
            connection,
            "deepseek",
            _DiscoveryClient(("deepseek-chat",)),
            seen_at=T0,
        )


def test_discovery_rejects_an_unregistered_connection(tmp_path: Path) -> None:
    """The audit history never describes a connection the aggregate lacks."""
    repository = FileProviderRegistryStateRepository(tmp_path / "state.json")
    runtime = _runtime(tmp_path, repository=repository)
    unregistered = ProviderConnection(
        connection_id="deepseek:main",
        provider_id="deepseek",
        display_name="DeepSeek",
        billing_class=BillingClass.PAYG,
        credential_ref=None,
        endpoint=_DEEPSEEK_URL,
        isolation_profile_ref=None,
        status=ConnectionStatus.CONNECTED,
    )

    with pytest.raises(ValueError, match="not registered"):
        runtime.coordinator.discover_models(
            unregistered,
            _active_manifest(runtime),
            _DiscoveryClient(("deepseek-chat",)),
            seen_at=T0,
        )

    assert runtime.coordinator.revision == 0
    assert repository.load() is None
    assert runtime.routes.list() == ()


def test_discovery_rejects_a_naive_timestamp(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)
    connection = _connection(runtime)

    with pytest.raises(ValueError, match="timezone-aware"):
        runtime.coordinator.discover_models(
            connection,
            _active_manifest(runtime),
            _DiscoveryClient(("deepseek-chat",)),
            seen_at=datetime(2026, 9, 15, 10, 0),  # noqa: DTZ001
        )

    assert runtime.coordinator.revision == 0
    assert runtime.routes.list() == ()


# --- connection validation transition commit (MAJOR-V2-02) ------------------


def test_update_connection_status_persists_one_validation_changed_record(
    tmp_path: Path,
) -> None:
    repository = FileProviderRegistryStateRepository(tmp_path / "state.json")
    runtime = _runtime(tmp_path, repository=repository)
    _connection(runtime, status=ConnectionStatus.AUTH_REQUIRED)

    updated = runtime.coordinator.update_connection_status(
        "deepseek:main", ConnectionStatus.CONNECTED, occurred_at=T1
    )

    assert updated.status is ConnectionStatus.CONNECTED
    assert runtime.connections.get("deepseek:main") == updated
    state = repository.load()
    assert state is not None
    assert state.revision == 1
    assert runtime.coordinator.revision == 1
    assert runtime.coordinator.audit_log == state.audit_log
    record = state.audit_log[-1]
    assert record.revision == 1
    assert record.event_type == "provider.validation_changed"
    assert record.entity_kind == "connection"
    assert record.entity_id == "deepseek:main"
    assert record.occurred_at == T1
    assert record.detail == (
        ("old_status", "auth_required"),
        ("new_status", "connected"),
    )
    assert tuple(item.status for item in state.connections) == (
        ConnectionStatus.CONNECTED,
    )


def test_validation_transition_records_the_validation_timestamp(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)
    _connection(runtime, status=ConnectionStatus.AUTH_REQUIRED)

    updated = runtime.coordinator.update_connection_status(
        "deepseek:main", ConnectionStatus.WARNING, occurred_at=T1
    )

    assert updated.last_validated_at == T1
    assert runtime.connections.get("deepseek:main").last_validated_at == T1


def test_update_connection_status_rejects_an_unchanged_status(tmp_path: Path) -> None:
    """The operation is a transition seam: a no-op is a caller error."""
    repository = _SwitchableStateRepository()
    runtime = _runtime(tmp_path, repository=repository)
    connection = _connection(runtime, status=ConnectionStatus.AUTH_REQUIRED)

    with pytest.raises(ValueError, match="status unchanged"):
        runtime.coordinator.update_connection_status(
            "deepseek:main", connection.status, occurred_at=T1
        )

    assert repository.save_calls == 0
    assert repository.load() is None
    assert runtime.coordinator.revision == 0
    assert runtime.coordinator.audit_log == ()
    assert runtime.connections.get("deepseek:main").status is (
        ConnectionStatus.AUTH_REQUIRED
    )
    assert runtime.connections.get("deepseek:main").last_validated_at is None


def test_update_connection_status_rejects_an_unknown_connection(tmp_path: Path) -> None:
    repository = _SwitchableStateRepository()
    runtime = _runtime(tmp_path, repository=repository)

    with pytest.raises(ValueError, match="unknown connection_id"):
        runtime.coordinator.update_connection_status(
            "deepseek:main", ConnectionStatus.CONNECTED, occurred_at=T1
        )

    assert repository.save_calls == 0
    assert runtime.coordinator.revision == 0


def test_update_connection_status_rejects_a_non_enum_status(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)
    _connection(runtime, status=ConnectionStatus.AUTH_REQUIRED)

    with pytest.raises(TypeError, match="ConnectionStatus"):
        runtime.coordinator.update_connection_status(
            "deepseek:main",
            "connected",
            occurred_at=T1,  # type: ignore[arg-type]
        )

    assert runtime.coordinator.revision == 0


def test_update_connection_status_rejects_a_naive_timestamp(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)
    _connection(runtime, status=ConnectionStatus.AUTH_REQUIRED)

    with pytest.raises(ValueError, match="timezone-aware"):
        runtime.coordinator.update_connection_status(
            "deepseek:main",
            ConnectionStatus.CONNECTED,
            occurred_at=datetime(2026, 9, 15, 12, 0),  # noqa: DTZ001
        )

    assert runtime.coordinator.revision == 0
    assert runtime.connections.get("deepseek:main").status is (
        ConnectionStatus.AUTH_REQUIRED
    )


def test_failed_status_save_restores_the_previous_connection_record(
    tmp_path: Path,
) -> None:
    repository = _SwitchableStateRepository()
    repository.fail = True
    runtime = _runtime(tmp_path, repository=repository)
    _connection(runtime, status=ConnectionStatus.AUTH_REQUIRED)

    with pytest.raises(RuntimeError, match="persistence failed"):
        runtime.coordinator.update_connection_status(
            "deepseek:main", ConnectionStatus.CONNECTED, occurred_at=T1
        )

    assert repository.save_calls == 1
    restored = runtime.connections.get("deepseek:main")
    assert restored is not None
    assert restored.status is ConnectionStatus.AUTH_REQUIRED
    assert restored.last_validated_at is None
    assert runtime.coordinator.revision == 0
    assert runtime.coordinator.audit_log == ()
    assert repository.load() is None


def test_failed_status_save_keeps_the_committed_revision(tmp_path: Path) -> None:
    repository = _SwitchableStateRepository()
    runtime = _runtime(tmp_path, repository=repository)
    _connection(runtime, status=ConnectionStatus.AUTH_REQUIRED)
    runtime.coordinator.update_connection_status(
        "deepseek:main", ConnectionStatus.CONNECTED, occurred_at=T0
    )
    committed = repository.load()
    assert committed is not None

    repository.fail = True
    with pytest.raises(RuntimeError, match="persistence failed"):
        runtime.coordinator.update_connection_status(
            "deepseek:main", ConnectionStatus.WARNING, occurred_at=T1
        )

    assert runtime.coordinator.revision == 1
    assert runtime.coordinator.audit_log == committed.audit_log
    assert repository.load() == committed
    restored = runtime.connections.get("deepseek:main")
    assert restored is not None
    assert restored.status is ConnectionStatus.CONNECTED
    assert restored.last_validated_at == T0


def test_validation_transition_audit_survives_a_restart(tmp_path: Path) -> None:
    repository = FileProviderRegistryStateRepository(tmp_path / "state.json")
    runtime = _runtime(tmp_path, repository=repository)
    _connection(runtime, status=ConnectionStatus.AUTH_REQUIRED)
    runtime.coordinator.update_connection_status(
        "deepseek:main", ConnectionStatus.CONNECTED, occurred_at=T1
    )

    persisted = repository.load()
    assert persisted is not None
    restored = restore_provider_registry_state(persisted)

    assert restored.revision == 1
    assert [record.event_type for record in restored.audit_log] == [
        "provider.validation_changed"
    ]
    assert restored.audit_log[0].detail == (
        ("old_status", "auth_required"),
        ("new_status", "connected"),
    )
    restored_connection = restored.connections.get("deepseek:main")
    assert restored_connection is not None
    assert restored_connection.status is ConnectionStatus.CONNECTED
    assert restored_connection.last_validated_at == T1


def test_route_and_validation_history_survive_a_restart_together(
    tmp_path: Path,
) -> None:
    """Discover → disappear → restore plus a validation transition, then restart."""
    repository = FileProviderRegistryStateRepository(tmp_path / "state.json")
    runtime = _runtime(tmp_path, repository=repository)
    connection = _connection(runtime, status=ConnectionStatus.AUTH_REQUIRED)
    manifest = _active_manifest(runtime)

    runtime.coordinator.discover_models(
        connection,
        manifest,
        _DiscoveryClient(("deepseek-chat", "deepseek-reasoner")),
        seen_at=T0,
    )
    runtime.coordinator.discover_models(
        connection, manifest, _DiscoveryClient(("deepseek-chat",)), seen_at=T1
    )
    runtime.coordinator.discover_models(
        connection,
        manifest,
        _DiscoveryClient(("deepseek-chat", "deepseek-reasoner")),
        seen_at=T2,
    )
    runtime.coordinator.update_connection_status(
        "deepseek:main", ConnectionStatus.CONNECTED, occurred_at=T2
    )

    persisted = repository.load()
    assert persisted is not None
    restored = restore_provider_registry_state(persisted)

    assert restored.revision == 4
    assert [record.revision for record in restored.audit_log] == [1, 1, 2, 3, 4]
    assert [record.event_type for record in restored.audit_log] == [
        "route.discovered",
        "route.discovered",
        "route.unavailable",
        "route.restored",
        "provider.validation_changed",
    ]
    assert [record.entity_kind for record in restored.audit_log][-1] == "connection"
    restored_connection = restored.connections.get("deepseek:main")
    assert restored_connection is not None
    assert restored_connection.status is ConnectionStatus.CONNECTED
