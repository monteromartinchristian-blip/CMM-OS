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
)
from kernel.llm.provider_state_coordinator import ProviderRegistryStateCoordinator
from kernel.llm.provider_state_repository import (
    FileProviderRegistryStateRepository,
    InMemoryProviderRegistryStateRepository,
    ProviderRegistryStateRepository,
)

T0 = datetime(2026, 9, 15, 10, 0, tzinfo=timezone.utc)
T1 = datetime(2026, 9, 15, 12, 0, tzinfo=timezone.utc)

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
    provider_id: str, base_url: str, billing: BillingClass
) -> ProviderManifest:
    return ProviderManifest(
        provider_id=provider_id,
        display_name=provider_id,
        billing_class=billing,
        default_base_url=base_url,
        auth_scheme="bearer",
    )


def _runtime(
    tmp_path: Path,
    *,
    repository: ProviderRegistryStateRepository | None = None,
    revision: int = 0,
) -> _Runtime:
    """Wire the canonical components and one coordinator over them."""
    providers = ProviderRegistry()
    providers.register(_spec("deepseek", _DEEPSEEK_URL))
    providers.register(_spec("qwen-token-plan", _QWEN_URL))
    manifests = ProviderManifestRegistry(providers)
    manifests.register(_manifest("deepseek", _DEEPSEEK_URL, BillingClass.PAYG))
    manifests.register(
        _manifest("qwen-token-plan", _QWEN_URL, BillingClass.SUBSCRIPTION)
    )
    connections = ProviderConnectionRegistry(providers)
    wired_repository = repository or InMemoryProviderRegistryStateRepository()
    credentials = InMemoryCredentialStore()
    coordinator = ProviderRegistryStateCoordinator(
        providers=providers,
        manifests=manifests,
        models=ModelCatalog(providers),
        connections=connections,
        routes=ModelRouteCatalog(connections),
        repository=wired_repository,
        revision=revision,
    )
    return _Runtime(
        coordinator=coordinator,
        providers=providers,
        manifests=manifests,
        models=ModelCatalog(providers),
        connections=connections,
        routes=ModelRouteCatalog(connections),
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
