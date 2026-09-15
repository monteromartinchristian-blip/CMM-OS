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
        self.calls = 0

    def list_models(self) -> tuple[str, ...]:
        self.calls += 1
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


def test_commit_fails_closed_when_item_level_authority_is_stale(
    tmp_path: Path,
) -> None:
    """MAJOR-V4-01: a stale graph can never publish the next revision.

    The canonical provider is removed while its dependent connection (and its
    committed state) remain. The coordinator does not repair that incoherence —
    capture refuses it, so nothing durable advances.
    """
    repository = _SwitchableStateRepository()
    runtime = _runtime(tmp_path, repository=repository)
    connection = _connection(runtime, status=ConnectionStatus.CONNECTED)
    runtime.coordinator.persist_connection_acceptance(connection, occurred_at=T0)
    committed = repository.load()
    assert committed is not None
    assert runtime.coordinator.revision == 1
    audit_before = runtime.coordinator.audit_log

    runtime.providers.remove("deepseek")

    with pytest.raises(
        ProviderStateCoherenceError, match="stale or missing ProviderSpec"
    ):
        runtime.coordinator.persist_connection_acceptance(connection, occurred_at=T1)

    assert runtime.coordinator.revision == 1
    assert runtime.coordinator.audit_log == audit_before
    assert repository.load() == committed
    # The stale connection is still visible: capture refuses it, nothing drops it.
    assert runtime.connections.get("deepseek:main") is connection


def test_status_transition_fails_closed_before_mutating_a_stale_connection(
    tmp_path: Path,
) -> None:
    """MAJOR-V4-01: a status transition never rewrites a stale authority.

    The canonical provider is removed while the connection survives. The
    operation revalidates that authority before mutating, so it fails with the
    same coherence error capture would raise — and the stored record, the
    revision, the audit log and the durable document are all unchanged (nothing
    is left to compensate through an authority that no longer exists).
    """
    repository = FileProviderRegistryStateRepository(tmp_path / "state.json")
    runtime = _runtime(tmp_path, repository=repository)
    connection = _connection(runtime, status=ConnectionStatus.CONNECTED)
    runtime.coordinator.persist_connection_acceptance(connection, occurred_at=T0)
    committed = repository.load()
    assert committed is not None
    revision_before = runtime.coordinator.revision
    audit_before = runtime.coordinator.audit_log

    runtime.providers.remove("deepseek")

    with pytest.raises(
        ProviderStateCoherenceError,
        match="connection deepseek:main is bound to a stale or missing ProviderSpec",
    ):
        runtime.coordinator.update_connection_status(
            "deepseek:main", ConnectionStatus.WARNING, occurred_at=T1
        )

    stored = runtime.connections.get("deepseek:main")
    assert stored is connection
    assert stored.status is ConnectionStatus.CONNECTED
    assert stored.last_validated_at is None
    assert runtime.coordinator.revision == revision_before
    assert runtime.coordinator.audit_log == audit_before
    assert repository.load() == committed


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
    """Discover → disappear → reappear: one revision per real mutation batch.

    Each pass commits one batch: the lifecycle transitions it produced plus a
    ``route.refreshed`` record for every known available route it re-advertised
    at a newer timestamp. A route with a lifecycle record in the same pass is
    never also reported as refreshed (MAJOR-V3-02, spec §6.6).
    """
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
    assert [record.revision for record in state.audit_log] == [1, 1, 2, 2, 3, 3]
    # Within one batch the envelope's canonical order applies, so the refresh
    # record of a batch sorts before that batch's lifecycle record.
    assert [record.event_type for record in state.audit_log] == [
        "route.discovered",
        "route.discovered",
        "route.refreshed",
        "route.unavailable",
        "route.refreshed",
        "route.restored",
    ]
    assert state.audit_log[2].entity_id == "deepseek:main:deepseek-chat"
    assert state.audit_log[2].entity_kind == "route"
    assert state.audit_log[2].occurred_at == T1
    assert state.audit_log[2].detail == (
        ("connection_id", "deepseek:main"),
        ("available", "true"),
    )
    assert state.audit_log[3].entity_id == "deepseek:main:deepseek-reasoner"
    assert state.audit_log[3].occurred_at == T1
    assert state.audit_log[3].detail == (
        ("connection_id", "deepseek:main"),
        ("available", "false"),
    )
    assert state.audit_log[5].entity_id == "deepseek:main:deepseek-reasoner"
    assert state.audit_log[5].occurred_at == T2
    assert state.audit_log[5].detail == (
        ("connection_id", "deepseek:main"),
        ("available", "true"),
    )
    # Restoring is a lifecycle transition: the restored route is never also
    # reported as refreshed in the same pass.
    assert [
        record.entity_id
        for record in state.audit_log
        if record.event_type == "route.refreshed"
    ] == ["deepseek:main:deepseek-chat", "deepseek:main:deepseek-chat"]
    reasoner = runtime.routes.get("deepseek:main:deepseek-reasoner")
    assert reasoner is not None
    assert reasoner.available is True
    assert reasoner.first_seen_at == T0
    assert reasoner.last_seen_at == T2
    chat = runtime.routes.get("deepseek:main:deepseek-chat")
    assert chat is not None
    assert chat.first_seen_at == T0
    assert chat.last_seen_at == T2


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
    assert [record.revision for record in restored.audit_log] == [1, 1, 2, 2, 3, 3]
    assert [record.event_type for record in restored.audit_log] == [
        "route.discovered",
        "route.discovered",
        "route.refreshed",
        "route.unavailable",
        "route.refreshed",
        "route.restored",
    ]
    restored_reasoner = restored.routes.get("deepseek:main:deepseek-reasoner")
    assert restored_reasoner is not None
    assert restored_reasoner.available is True
    assert restored_reasoner.first_seen_at == T0
    assert restored_reasoner.last_seen_at == T2
    restored_chat = restored.routes.get("deepseek:main:deepseek-chat")
    assert restored_chat is not None
    assert restored_chat.first_seen_at == T0
    assert restored_chat.last_seen_at == T2


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


def test_refresh_only_discovery_is_a_durable_mutation(tmp_path: Path) -> None:
    """A successful rediscovery of a known route is durable state (MAJOR-V3-02).

    Independent Re-audit V3 reproduced the opposite: ``mark_seen`` advanced the
    live ``last_seen_at`` without a lifecycle transition, the coordinator
    persisted nothing, and a restart regressed the route to ``T0``. A newer
    timestamp is real phase-owned state, so it is one mutation batch: sanitized
    ``route.refreshed`` audit plus one revision, saved before publishing.
    """
    repository = FileProviderRegistryStateRepository(tmp_path / "state.json")
    runtime = _runtime(tmp_path, repository=repository)
    connection = _connection(runtime, status=ConnectionStatus.CONNECTED)
    manifest = _active_manifest(runtime)
    route_id = "deepseek:main:deepseek-chat"

    runtime.coordinator.discover_models(
        connection, manifest, _DiscoveryClient(("deepseek-chat",)), seen_at=T0
    )
    assert runtime.coordinator.revision == 1

    result = runtime.coordinator.discover_models(
        connection, manifest, _DiscoveryClient(("deepseek-chat",)), seen_at=T1
    )

    # A refresh-only pass: no new, restored or unavailable route anywhere.
    assert result.new_route_ids == ()
    assert result.restored_route_ids == ()
    assert result.unavailable_route_ids == ()
    assert runtime.coordinator.revision == 2
    live = runtime.routes.get(route_id)
    assert live is not None
    assert live.last_seen_at == T1
    persisted = repository.load()
    assert persisted is not None
    assert persisted.revision == 2
    persisted_route = next(
        route for route in persisted.routes if route.route_id == route_id
    )
    assert persisted_route.last_seen_at == T1
    assert persisted_route.first_seen_at == T0
    # The lifecycle record is absent; the refresh record carries the batch.
    assert [record.event_type for record in persisted.audit_log] == [
        "route.discovered",
        "route.refreshed",
    ]
    refreshed = persisted.audit_log[1]
    assert refreshed.revision == 2
    assert refreshed.entity_kind == "route"
    assert refreshed.entity_id == route_id
    assert refreshed.occurred_at == T1
    assert refreshed.detail == (
        ("connection_id", "deepseek:main"),
        ("available", "true"),
    )

    # Process-equivalent restart: the newest successful discovery survives.
    restored = restore_provider_registry_state(persisted)
    restored_route = restored.routes.get(route_id)
    assert restored_route is not None
    assert restored_route.last_seen_at == T1
    assert restored_route.first_seen_at == T0
    assert restored.revision == 2


def test_same_timestamp_discovery_is_a_true_no_op(tmp_path: Path) -> None:
    """Re-running the identical pass at the same instant mutates nothing.

    The valid no-op: every resulting route field is already equal, so no
    revision, audit record, durable byte or live route changes.
    """
    repository = _SwitchableStateRepository()
    runtime = _runtime(tmp_path, repository=repository)
    connection = _connection(runtime, status=ConnectionStatus.CONNECTED)
    manifest = _active_manifest(runtime)

    runtime.coordinator.discover_models(
        connection, manifest, _DiscoveryClient(("deepseek-chat",)), seen_at=T1
    )
    revision_before = runtime.coordinator.revision
    audit_before = runtime.coordinator.audit_log
    state_before = repository.load()
    saves_before = repository.save_calls
    routes_before = runtime.routes.list()

    runtime.coordinator.discover_models(
        connection, manifest, _DiscoveryClient(("deepseek-chat",)), seen_at=T1
    )

    assert repository.save_calls == saves_before
    assert runtime.coordinator.revision == revision_before
    assert runtime.coordinator.audit_log == audit_before
    assert repository.load() == state_before
    assert runtime.routes.list() == routes_before


def test_failed_refresh_save_restores_the_route_catalog_exactly(
    tmp_path: Path,
) -> None:
    """A refresh-only persistence failure rolls the live route back to T0."""
    repository = _SwitchableStateRepository()
    runtime = _runtime(tmp_path, repository=repository)
    connection = _connection(runtime, status=ConnectionStatus.CONNECTED)
    manifest = _active_manifest(runtime)
    route_id = "deepseek:main:deepseek-chat"

    runtime.coordinator.discover_models(
        connection, manifest, _DiscoveryClient(("deepseek-chat",)), seen_at=T0
    )
    committed = repository.load()
    assert committed is not None
    routes_before = runtime.routes.list()
    audit_before = runtime.coordinator.audit_log

    repository.fail = True
    with pytest.raises(RuntimeError, match="persistence failed"):
        runtime.coordinator.discover_models(
            connection, manifest, _DiscoveryClient(("deepseek-chat",)), seen_at=T1
        )

    rolled_back = runtime.routes.get(route_id)
    assert rolled_back is not None
    assert rolled_back.last_seen_at == T0
    assert runtime.routes.list() == routes_before
    assert runtime.coordinator.revision == 1
    assert runtime.coordinator.audit_log == audit_before
    assert repository.load() == committed
    assert all(
        record.event_type != "route.refreshed"
        for record in runtime.coordinator.audit_log
    )


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
    """An already-inactive route stays inactive without a spurious record.

    The second pass re-advertises the inactive route, but a deferred route is
    neither stamped by ``mark_seen`` nor re-reported: its only durable effect is
    the refresh of the still-active route, so no lifecycle record exists for
    the deferred one (MAJOR-V3-02, spec §6.7).
    """
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

    assert repository.save_calls == 2
    assert runtime.coordinator.revision == 2
    assert [
        (record.event_type, record.entity_id)
        for record in runtime.coordinator.audit_log
        if record.revision == 2
    ] == [("route.refreshed", "deepseek:main:deepseek-chat")]
    deferred = runtime.routes.get("deepseek:main:deepseek-reasoner")
    assert deferred is not None
    assert deferred.available is False
    assert deferred.last_seen_at == T0


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
    assert [record.revision for record in restored.audit_log] == [1, 1, 2, 2, 3, 3, 4]
    assert [record.event_type for record in restored.audit_log] == [
        "route.discovered",
        "route.discovered",
        "route.refreshed",
        "route.unavailable",
        "route.refreshed",
        "route.restored",
        "provider.validation_changed",
    ]
    assert [record.entity_kind for record in restored.audit_log][-1] == "connection"
    restored_connection = restored.connections.get("deepseek:main")
    assert restored_connection is not None
    assert restored_connection.status is ConnectionStatus.CONNECTED


# --- discovery manifest authority (MAJOR-V4-03) ------------------------------


def _foreign_manifest(
    provider_id: str = "deepseek",
    *,
    allowlist: tuple[str, ...] = ("deepseek-chat",),
) -> ProviderManifest:
    """Build a same-id manifest that is deliberately not the canonical one."""
    return ProviderManifest(
        provider_id=provider_id,
        display_name=provider_id,
        billing_class=BillingClass.PAYG,
        default_base_url="https://foreign.example/v1",
        auth_scheme="bearer",
        activation_allowlist=allowlist,
    )


def test_discovery_rejects_a_foreign_same_id_manifest_before_any_effect(
    tmp_path: Path,
) -> None:
    """MAJOR-V4-03: a caller-supplied manifest is a claim, never authority."""
    repository = FileProviderRegistryStateRepository(tmp_path / "state.json")
    runtime = _runtime(tmp_path, repository=repository)
    connection = _connection(runtime, status=ConnectionStatus.CONNECTED)
    assert runtime.manifests.get("deepseek") is not None
    foreign = _foreign_manifest()
    client = _DiscoveryClient(("deepseek-chat", "deepseek-reasoner"))

    with pytest.raises(
        ProviderStateCoherenceError,
        match="discovery manifest is not the active canonical manifest",
    ):
        runtime.coordinator.discover_models(connection, foreign, client, seen_at=T0)

    assert client.calls == 0
    assert runtime.routes.list() == ()
    assert runtime.coordinator.revision == 0
    assert runtime.coordinator.audit_log == ()
    assert repository.load() is None


def test_discovery_rejects_a_stale_formerly_active_manifest(
    tmp_path: Path,
) -> None:
    """A manifest that was once canonical is still not the active one."""
    repository = FileProviderRegistryStateRepository(tmp_path / "state.json")
    runtime = _runtime(tmp_path, repository=repository)
    connection = _connection(runtime, status=ConnectionStatus.CONNECTED)
    previous = _active_manifest(runtime)

    # Replace the provider authority, then register fresh metadata under it.
    runtime.providers.remove("deepseek")
    runtime.providers.register(_spec("deepseek", _DEEPSEEK_URL))
    replacement = runtime.manifests.register(
        _manifest("deepseek", _DEEPSEEK_URL, BillingClass.PAYG)
    )
    assert replacement is not previous
    assert runtime.manifests.get("deepseek") is replacement
    client = _DiscoveryClient(("deepseek-chat",))

    with pytest.raises(
        ProviderStateCoherenceError,
        match="discovery manifest is not the active canonical manifest",
    ):
        runtime.coordinator.discover_models(connection, previous, client, seen_at=T0)

    assert client.calls == 0
    assert runtime.routes.list() == ()
    assert runtime.coordinator.revision == 0
    assert runtime.coordinator.audit_log == ()
    assert repository.load() is None


def test_discovery_rejects_a_manifest_for_another_canonical_provider(
    tmp_path: Path,
) -> None:
    """A manifest of a *different* canonical provider is also not authority."""
    repository = FileProviderRegistryStateRepository(tmp_path / "state.json")
    runtime = _runtime(tmp_path, repository=repository)
    connection = _connection(runtime, status=ConnectionStatus.CONNECTED)
    other = runtime.manifests.get("qwen-token-plan")
    assert other is not None
    client = _DiscoveryClient(("deepseek-chat",))

    with pytest.raises(
        ProviderStateCoherenceError,
        match="discovery manifest is not the active canonical manifest",
    ):
        runtime.coordinator.discover_models(connection, other, client, seen_at=T0)

    assert client.calls == 0
    assert runtime.routes.list() == ()
    assert runtime.coordinator.revision == 0
    assert repository.load() is None


def test_discovery_rejects_a_manifest_whose_provider_has_no_active_metadata(
    tmp_path: Path,
) -> None:
    """With no active canonical manifest for the connection, discovery fails closed."""
    repository = FileProviderRegistryStateRepository(tmp_path / "state.json")
    runtime = _runtime(tmp_path, repository=repository)
    connection = _connection(runtime, status=ConnectionStatus.CONNECTED)
    canonical = _active_manifest(runtime)

    client = _DiscoveryClient(("deepseek-chat",))
    runtime.providers.remove("deepseek")

    with pytest.raises(
        ProviderStateCoherenceError,
        match="discovery manifest is not the active canonical manifest",
    ):
        runtime.coordinator.discover_models(connection, canonical, client, seen_at=T0)

    assert client.calls == 0
    assert runtime.routes.list() == ()
    assert runtime.coordinator.revision == 0
    assert repository.load() is None


def test_discovery_still_runs_with_the_active_canonical_manifest(
    tmp_path: Path,
) -> None:
    """The identity guard rejects divergence only, never the canonical manifest."""
    repository = FileProviderRegistryStateRepository(tmp_path / "state.json")
    runtime = _runtime(tmp_path, repository=repository)
    connection = _connection(runtime, status=ConnectionStatus.CONNECTED)
    client = _DiscoveryClient(("deepseek-chat",))

    result = runtime.coordinator.discover_models(
        connection, _active_manifest(runtime), client, seen_at=T0
    )

    assert client.calls == 1
    assert result.new_route_ids == ("deepseek:main:deepseek-chat",)
    assert runtime.coordinator.revision == 1


# --- monotonic discovery snapshots (MINOR-V4-01) -----------------------------


def test_discovery_rejects_an_older_snapshot_before_the_client_call(
    tmp_path: Path,
) -> None:
    """MINOR-V4-01: an older observation never regresses ``last_seen_at``."""
    repository = FileProviderRegistryStateRepository(tmp_path / "state.json")
    runtime = _runtime(tmp_path, repository=repository)
    connection = _connection(runtime, status=ConnectionStatus.CONNECTED)
    manifest = _active_manifest(runtime)
    runtime.coordinator.discover_models(
        connection, manifest, _DiscoveryClient(("deepseek-chat",)), seen_at=T1
    )
    state_before = repository.load()
    assert state_before is not None
    audit_before = runtime.coordinator.audit_log
    client = _DiscoveryClient(("deepseek-chat",))

    with pytest.raises(
        ProviderStateCoherenceError,
        match="discovery seen_at precedes current route state",
    ):
        runtime.coordinator.discover_models(connection, manifest, client, seen_at=T0)

    assert client.calls == 0
    route = runtime.routes.get("deepseek:main:deepseek-chat")
    assert route is not None
    assert route.last_seen_at == T1
    assert route.available is True
    assert runtime.coordinator.revision == state_before.revision
    assert runtime.coordinator.audit_log == audit_before
    assert repository.load() == state_before


def test_discovery_rejects_an_older_snapshot_without_availability_changes(
    tmp_path: Path,
) -> None:
    """An older snapshot cannot make a route disappear either."""
    repository = FileProviderRegistryStateRepository(tmp_path / "state.json")
    runtime = _runtime(tmp_path, repository=repository)
    connection = _connection(runtime, status=ConnectionStatus.CONNECTED)
    manifest = _active_manifest(runtime)
    runtime.coordinator.discover_models(
        connection,
        manifest,
        _DiscoveryClient(("deepseek-chat", "deepseek-reasoner")),
        seen_at=T1,
    )
    state_before = repository.load()
    assert state_before is not None
    client = _DiscoveryClient(("deepseek-chat",))

    with pytest.raises(
        ProviderStateCoherenceError,
        match="discovery seen_at precedes current route state",
    ):
        runtime.coordinator.discover_models(connection, manifest, client, seen_at=T0)

    assert client.calls == 0
    reasoner = runtime.routes.get("deepseek:main:deepseek-reasoner")
    assert reasoner is not None
    assert reasoner.available is True
    assert reasoner.last_seen_at == T1
    assert runtime.coordinator.revision == state_before.revision
    assert repository.load() == state_before


def test_discovery_accepts_an_equal_snapshot_as_a_v3_noop(tmp_path: Path) -> None:
    """Equality stays valid: the exact same pass is still a true no-op."""
    repository = FileProviderRegistryStateRepository(tmp_path / "state.json")
    runtime = _runtime(tmp_path, repository=repository)
    connection = _connection(runtime, status=ConnectionStatus.CONNECTED)
    manifest = _active_manifest(runtime)
    runtime.coordinator.discover_models(
        connection, manifest, _DiscoveryClient(("deepseek-chat",)), seen_at=T1
    )
    state_before = repository.load()
    assert state_before is not None
    assert runtime.coordinator.revision == 1

    result = runtime.coordinator.discover_models(
        connection, manifest, _DiscoveryClient(("deepseek-chat",)), seen_at=T1
    )

    assert result.new_route_ids == ()
    assert result.restored_route_ids == ()
    assert runtime.coordinator.revision == 1
    assert runtime.coordinator.audit_log == state_before.audit_log
    assert repository.load() == state_before
    route = runtime.routes.get("deepseek:main:deepseek-chat")
    assert route is not None
    assert route.last_seen_at == T1


def test_discovery_allows_a_snapshot_matching_the_latest_route_timestamp(
    tmp_path: Path,
) -> None:
    """The policy is the connection-level maximum, not per-route equality.

    One route is at T1 while another still carries T0; a T1 snapshot is the
    newest observation of that connection and must be accepted.
    """
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
    older = runtime.routes.get("deepseek:main:deepseek-reasoner")
    assert older is not None
    assert older.last_seen_at == T0

    result = runtime.coordinator.discover_models(
        connection,
        manifest,
        _DiscoveryClient(("deepseek-chat", "deepseek-reasoner")),
        seen_at=T1,
    )

    assert result.restored_route_ids == ("deepseek:main:deepseek-reasoner",)
    refreshed = runtime.routes.get("deepseek:main:deepseek-reasoner")
    assert refreshed is not None
    assert refreshed.last_seen_at == T1
    assert refreshed.available is True


def test_discovery_accepts_the_first_snapshot_for_a_connection(
    tmp_path: Path,
) -> None:
    """With no routes yet, any otherwise-valid aware timestamp is allowed."""
    repository = FileProviderRegistryStateRepository(tmp_path / "state.json")
    runtime = _runtime(tmp_path, repository=repository)
    connection = _connection(runtime, status=ConnectionStatus.CONNECTED)

    result = runtime.coordinator.discover_models(
        connection,
        _active_manifest(runtime),
        _DiscoveryClient(("deepseek-chat",)),
        seen_at=T0,
    )

    assert result.new_route_ids == ("deepseek:main:deepseek-chat",)
