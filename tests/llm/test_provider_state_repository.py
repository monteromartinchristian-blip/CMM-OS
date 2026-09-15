"""Contract tests for the Provider Registry state repository (MAJOR-02).

Two implementations are pinned here: the official in-memory repository (used by
tests and ephemeral runtimes) and the local JSON repository, whose save must be
atomic — a failed replace may never damage the previous durable state — and
whose bytes must never contain raw secret material, only opaque credential refs.

Capture and restore are the canonical reconstruction path: restoring rebuilds
the aggregate in dependency order (providers → manifests → models → connections
→ routes) and fails closed on any orphan reference or unsupported schema, so a
partial aggregate is never handed back to a caller.
"""

from __future__ import annotations

import json
import os
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

import pytest

from kernel.llm.capabilities import ProviderCapabilities
from kernel.llm.credential_store import InMemoryCredentialStore
from kernel.llm.exceptions import ProviderError
from kernel.llm.model_catalog import ModelCatalog, ModelSpec
from kernel.llm.model_routes import (
    CapabilityConfidence,
    ModelRoute,
    ModelRouteCatalog,
    RouteCapabilityState,
)
from kernel.llm.provider_connections import (
    BillingClass,
    ConnectionStatus,
    ProviderConnection,
    ProviderConnectionRegistry,
)
from kernel.llm.provider_manifests import ProviderManifest, ProviderManifestRegistry
from kernel.llm.provider_registry import ProviderRegistry, ProviderSpec
from kernel.llm.provider_state import (
    SCHEMA_VERSION,
    ProviderRegistryAuditRecord,
    ProviderRegistryState,
    ProviderStateCoherenceError,
    ProviderStateSchemaError,
    ProviderStateSerializationError,
)
from kernel.llm.provider_state_repository import (
    FileProviderRegistryStateRepository,
    InMemoryProviderRegistryStateRepository,
    ProviderRegistryStateRepository,
    RestoredProviderRegistryState,
    capture_provider_registry_state,
    restore_provider_registry_state,
)

T0 = datetime(2026, 9, 14, 10, 0, tzinfo=timezone.utc)
T1 = datetime(2026, 9, 14, 12, 0, tzinfo=timezone.utc)

_DEEPSEEK_URL = "https://api.deepseek.com/v1"
_QWEN_URL = "https://token-plan.example.invalid/v1"
_SAFE_REF = "keychain://cmm/providers/deepseek/main"
_SECRET = "super-secret-value"


def _spec(provider_id: str, base_url: str) -> ProviderSpec:
    return ProviderSpec(
        id=provider_id,
        provider_type="remote",
        api_style="chat_completions",
        base_url=base_url,
        availability="available",
        capabilities=ProviderCapabilities(chat_completions=True),
    )


def _manifest(provider_id: str, base_url: str, *, billing: BillingClass):
    return ProviderManifest(
        provider_id=provider_id,
        display_name=provider_id,
        billing_class=billing,
        default_base_url=base_url,
        auth_scheme="bearer",
    )


def _connection(provider_id: str) -> ProviderConnection:
    return ProviderConnection(
        connection_id=f"{provider_id}:main",
        provider_id=provider_id,
        display_name=provider_id,
        billing_class=BillingClass.PAYG,
        credential_ref=_SAFE_REF if provider_id == "deepseek" else None,
        endpoint=_DEEPSEEK_URL if provider_id == "deepseek" else _QWEN_URL,
        isolation_profile_ref=None,
        status=ConnectionStatus.CONNECTED,
        created_at=T0,
        last_validated_at=T1,
    )


def _route(
    connection_id: str,
    *,
    available: bool,
    last_seen_at: datetime | None = T1,
) -> ModelRoute:
    return ModelRoute(
        route_id=f"{connection_id}:deepseek-chat",
        connection_id=connection_id,
        provider_model_id="deepseek-chat",
        canonical_model_id="deepseek-chat",
        available=available,
        first_seen_at=T0,
        last_seen_at=last_seen_at,
        capabilities=(
            RouteCapabilityState(
                name="tools",
                supported=True,
                confidence=CapabilityConfidence.VERIFIED,
            ),
        ),
    )


def _audit(revision: int = 3) -> ProviderRegistryAuditRecord:
    return ProviderRegistryAuditRecord(
        revision=revision,
        event_type="provider.connected",
        entity_kind="connection",
        entity_id="deepseek:main",
        occurred_at=T1,
        detail=(("status", "connected"),),
    )


def _state(
    *,
    revision: int = 3,
    connections: tuple[ProviderConnection, ...] | None = None,
    routes: tuple[ModelRoute, ...] | None = None,
    models: tuple[ModelSpec, ...] | None = None,
) -> ProviderRegistryState:
    """Build a referentially consistent aggregate for repository tests."""
    return ProviderRegistryState(
        schema_version=SCHEMA_VERSION,
        revision=revision,
        providers=(
            _spec("deepseek", _DEEPSEEK_URL),
            _spec("qwen-token-plan", _QWEN_URL),
        ),
        manifests=(
            _manifest("deepseek", _DEEPSEEK_URL, billing=BillingClass.PAYG),
            _manifest(
                "qwen-token-plan",
                _QWEN_URL,
                billing=BillingClass.SUBSCRIPTION,
            ),
        ),
        models=models
        if models is not None
        else (
            ModelSpec(id="deepseek-chat", provider_id="deepseek"),
            ModelSpec(id="deepseek-chat", provider_id="qwen-token-plan"),
        ),
        connections=connections
        if connections is not None
        else (_connection("deepseek"), _connection("qwen-token-plan")),
        routes=routes
        if routes is not None
        else (
            _route("deepseek:main", available=True),
            _route("qwen-token-plan:main", available=False),
        ),
        audit_log=(_audit(),),
    )


def _runtime() -> tuple[
    ProviderRegistry,
    ProviderManifestRegistry,
    ModelCatalog,
    ProviderConnectionRegistry,
    ModelRouteCatalog,
]:
    """Build the canonical runtime component graph in dependency order."""
    providers = ProviderRegistry()
    for spec in _state().providers:
        providers.register(spec)
    manifests = ProviderManifestRegistry(providers)
    for manifest in _state().manifests:
        manifests.register(manifest)
    models = ModelCatalog(providers)
    for spec in _state().models:
        models.register(spec)
    connections = ProviderConnectionRegistry(providers)
    connections.register(_connection("deepseek"))
    connections.register(_connection("qwen-token-plan"))
    routes = ModelRouteCatalog(connections)
    routes.register(_route("deepseek:main", available=True))
    routes.register(_route("qwen-token-plan:main", available=True))
    routes.mark_unavailable("qwen-token-plan:main:deepseek-chat")
    return providers, manifests, models, connections, routes


# --- in-memory repository ---------------------------------------------------


def test_in_memory_repository_loads_none_before_any_save() -> None:
    repository = InMemoryProviderRegistryStateRepository()

    assert repository.load() is None


def test_in_memory_repository_round_trips_state() -> None:
    repository = InMemoryProviderRegistryStateRepository()
    state = _state()

    repository.save(state)

    assert repository.load() == state
    assert repository.load() is state


def test_in_memory_repository_satisfies_the_protocol() -> None:
    assert isinstance(
        InMemoryProviderRegistryStateRepository(), ProviderRegistryStateRepository
    )


def test_in_memory_repository_rejects_a_non_state() -> None:
    repository = InMemoryProviderRegistryStateRepository()

    with pytest.raises(TypeError, match="ProviderRegistryState"):
        repository.save({"schema_version": SCHEMA_VERSION})  # type: ignore[arg-type]


# --- file repository --------------------------------------------------------


def test_file_repository_loads_none_when_absent(tmp_path: Path) -> None:
    repository = FileProviderRegistryStateRepository(tmp_path / "providers.json")

    assert repository.load() is None


def test_file_repository_round_trips_state(tmp_path: Path) -> None:
    path = tmp_path / "providers.json"
    repository = FileProviderRegistryStateRepository(path)
    state = _state()

    repository.save(state)

    assert path.is_file()
    assert repository.load() == state


def test_file_repository_bytes_are_deterministic(tmp_path: Path) -> None:
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"
    state = _state()

    FileProviderRegistryStateRepository(first).save(state)
    FileProviderRegistryStateRepository(second).save(state)

    assert first.read_bytes() == second.read_bytes()


def test_file_repository_persists_no_raw_secret(tmp_path: Path) -> None:
    """Only the opaque ref crosses the boundary; the stored secret never does."""
    path = tmp_path / "providers.json"
    store = InMemoryCredentialStore()
    credential_ref = store.put("deepseek", "main", _SECRET)
    connection = replace(_connection("deepseek"), credential_ref=credential_ref)

    FileProviderRegistryStateRepository(path).save(
        _state(connections=(connection,), routes=())
    )

    payload = path.read_text(encoding="utf-8")
    assert credential_ref in payload
    assert store._secrets[credential_ref] == _SECRET
    assert _SECRET not in payload
    assert "sk-" not in payload


def test_file_repository_rejects_malformed_json(tmp_path: Path) -> None:
    path = tmp_path / "providers.json"
    path.write_text("{not json", encoding="utf-8")

    with pytest.raises(ProviderStateSerializationError):
        FileProviderRegistryStateRepository(path).load()


def test_file_repository_rejects_unsupported_schema(tmp_path: Path) -> None:
    path = tmp_path / "providers.json"
    payload = _state().to_dict()
    payload["schema_version"] = "999"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ProviderStateSchemaError):
        FileProviderRegistryStateRepository(path).load()


def test_file_save_is_atomic_when_replace_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "providers.json"
    repository = FileProviderRegistryStateRepository(path)
    original = _state(revision=1)
    repository.save(original)
    before = path.read_bytes()

    def _boom(*args: object, **kwargs: object) -> None:
        raise OSError("replace failed")

    monkeypatch.setattr(os, "replace", _boom)

    with pytest.raises(OSError, match="replace failed"):
        repository.save(_state(revision=2))

    assert path.read_bytes() == before
    assert repository.load() == original
    assert sorted(item.name for item in tmp_path.iterdir()) == [path.name]


def test_file_save_creates_missing_parent_directories(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "providers.json"
    repository = FileProviderRegistryStateRepository(path)

    repository.save(_state())

    assert repository.load() == _state()


def test_file_repository_rejects_a_non_state(tmp_path: Path) -> None:
    repository = FileProviderRegistryStateRepository(tmp_path / "providers.json")

    with pytest.raises(TypeError, match="ProviderRegistryState"):
        repository.save(object())  # type: ignore[arg-type]


def test_file_repository_satisfies_the_protocol(tmp_path: Path) -> None:
    repository = FileProviderRegistryStateRepository(tmp_path / "providers.json")

    assert isinstance(repository, ProviderRegistryStateRepository)


def test_file_repository_accepts_a_string_path(tmp_path: Path) -> None:
    repository = FileProviderRegistryStateRepository(str(tmp_path / "providers.json"))

    repository.save(_state())

    assert repository.load() == _state()


# --- capture ----------------------------------------------------------------


def test_capture_reads_every_canonical_component() -> None:
    providers, manifests, models, connections, routes = _runtime()

    state = capture_provider_registry_state(
        providers,
        manifests,
        models,
        connections,
        routes,
        revision=5,
        audit_log=(_audit(5),),
    )

    assert state.revision == 5
    assert tuple(spec.id for spec in state.providers) == (
        "deepseek",
        "qwen-token-plan",
    )
    assert tuple(item.provider_id for item in state.manifests) == (
        "deepseek",
        "qwen-token-plan",
    )
    assert tuple(spec.qualified_id for spec in state.models) == (
        "deepseek:deepseek-chat",
        "qwen-token-plan:deepseek-chat",
    )
    assert tuple(item.connection_id for item in state.connections) == (
        "deepseek:main",
        "qwen-token-plan:main",
    )
    assert tuple(item.route_id for item in state.routes) == (
        "deepseek:main:deepseek-chat",
        "qwen-token-plan:main:deepseek-chat",
    )
    assert state.audit_log == (_audit(5),)


def test_capture_rejects_negative_revision() -> None:
    providers, manifests, models, connections, routes = _runtime()

    with pytest.raises(ValueError, match="revision"):
        capture_provider_registry_state(
            providers,
            manifests,
            models,
            connections,
            routes,
            revision=-1,
        )


@pytest.mark.parametrize("position", range(5))
def test_capture_rejects_a_wrong_component_type(position: int) -> None:
    components: list[object] = list(_runtime())
    components[position] = object()

    with pytest.raises(TypeError):
        capture_provider_registry_state(*components, revision=1)  # type: ignore[arg-type]


def _capturable_authority() -> tuple[
    ProviderRegistry,
    ProviderManifestRegistry,
    ModelCatalog,
    ProviderConnectionRegistry,
    ModelRouteCatalog,
]:
    """A two-provider authority with both manifests and no dependent state.

    Removing one provider strands nothing here, so the captured aggregate is
    still exactly restorable — which is what the coherence tests below assert.
    """
    providers = ProviderRegistry()
    providers.register(_spec("deepseek", _DEEPSEEK_URL))
    providers.register(_spec("qwen-token-plan", _QWEN_URL))
    manifests = ProviderManifestRegistry(providers)
    manifests.register(_manifest("deepseek", _DEEPSEEK_URL, billing=BillingClass.PAYG))
    manifests.register(
        _manifest("qwen-token-plan", _QWEN_URL, billing=BillingClass.SUBSCRIPTION)
    )
    connections = ProviderConnectionRegistry(providers)
    return (
        providers,
        manifests,
        ModelCatalog(providers),
        connections,
        ModelRouteCatalog(connections),
    )


def test_capture_omits_a_manifest_whose_canonical_provider_was_removed() -> None:
    """MAJOR-V2-01: no orphan manifest may enter the persisted aggregate."""
    providers, manifests, models, connections, routes = _capturable_authority()

    providers.remove("deepseek")
    state = capture_provider_registry_state(
        providers, manifests, models, connections, routes, revision=1
    )

    assert tuple(item.provider_id for item in state.manifests) == ("qwen-token-plan",)
    assert all(item.provider_id != "deepseek" for item in state.manifests)
    # What is captured can always be canonically reconstructed.
    restored = restore_provider_registry_state(state)
    assert tuple(item.provider_id for item in restored.manifests.list()) == (
        "qwen-token-plan",
    )


def test_capture_omits_a_manifest_after_same_id_provider_reregistration() -> None:
    """A re-created provider identity does not revive the previous metadata."""
    providers, manifests, models, connections, routes = _capturable_authority()

    providers.remove("deepseek")
    providers.register(_spec("deepseek", _DEEPSEEK_URL))
    state = capture_provider_registry_state(
        providers, manifests, models, connections, routes, revision=1
    )

    assert tuple(spec.id for spec in state.providers) == (
        "deepseek",
        "qwen-token-plan",
    )
    assert all(item.provider_id != "deepseek" for item in state.manifests)
    restored = restore_provider_registry_state(state)
    assert tuple(item.provider_id for item in restored.manifests.list()) == (
        "qwen-token-plan",
    )


def test_capture_rejects_a_manifest_without_a_canonical_provider() -> None:
    """Defense in depth: an incoherent manifest/provider graph is never saved.

    Enumeration already hides stale metadata, so this adversarial wiring — a
    metadata catalog bound to a *different* authority than the captured one —
    is the remaining way an orphan manifest could reach the serializer. Capture
    refuses it with a focused error instead of persisting an unrestorable
    aggregate (the audited failure: capture accepted a manifest graph that
    ``restore_provider_registry_state()`` then rejected).
    """
    providers, _, models, connections, routes = _capturable_authority()
    other_providers = ProviderRegistry()
    other_providers.register(_spec("ghost", "https://ghost.example.invalid/v1"))
    other_manifests = ProviderManifestRegistry(other_providers)
    other_manifests.register(
        _manifest("ghost", "https://ghost.example.invalid/v1", billing=BillingClass.API)
    )

    with pytest.raises(ProviderStateCoherenceError, match="ghost"):
        capture_provider_registry_state(
            providers, other_manifests, models, connections, routes, revision=1
        )


def test_capture_accepts_a_coherent_graph_from_a_matching_authority() -> None:
    """The coherence guard rejects divergence only, never a valid aggregate."""
    providers, manifests, models, connections, routes = _capturable_authority()

    state = capture_provider_registry_state(
        providers, manifests, models, connections, routes, revision=2
    )

    assert tuple(item.provider_id for item in state.manifests) == (
        "deepseek",
        "qwen-token-plan",
    )
    assert restore_provider_registry_state(state).revision == 2


# --- restore ----------------------------------------------------------------


def test_restore_rebuilds_the_canonical_component_graph() -> None:
    state = _state()

    restored = restore_provider_registry_state(state)

    assert isinstance(restored, RestoredProviderRegistryState)
    assert restored.revision == state.revision
    assert restored.audit_log == state.audit_log
    assert tuple(spec.id for spec in restored.providers.list()) == (
        "deepseek",
        "qwen-token-plan",
    )
    # Every subordinate component is bound to the rebuilt authority.
    assert restored.manifests.provider_registry is restored.providers
    assert restored.connections.provider_registry is restored.providers
    assert restored.routes.connections is restored.connections
    with pytest.raises(ProviderError, match="Unknown registered provider"):
        restored.providers.get("not-restored")


def test_restore_preserves_route_history_and_availability() -> None:
    state = _state(
        routes=(
            _route("deepseek:main", available=True),
            _route("qwen-token-plan:main", available=False, last_seen_at=T0),
        )
    )

    restored = restore_provider_registry_state(state)

    stale = restored.routes.get("qwen-token-plan:main:deepseek-chat")
    assert stale is not None
    assert stale.available is False
    assert stale.first_seen_at == T0
    assert stale.last_seen_at == T0
    assert stale.capabilities[0].confidence is CapabilityConfidence.VERIFIED
    assert restored.routes.get("deepseek:main:deepseek-chat").available is True


def test_restore_round_trips_through_capture() -> None:
    runtime = _runtime()
    state = capture_provider_registry_state(
        *runtime, revision=4, audit_log=(_audit(4),)
    )

    restored = restore_provider_registry_state(state)

    assert (
        capture_provider_registry_state(
            restored.providers,
            restored.manifests,
            restored.models,
            restored.connections,
            restored.routes,
            revision=restored.revision,
            audit_log=restored.audit_log,
        )
        == state
    )


def test_restore_rejects_a_non_state() -> None:
    with pytest.raises(TypeError, match="ProviderRegistryState"):
        restore_provider_registry_state({})  # type: ignore[arg-type]


def test_restore_rejects_an_orphan_connection() -> None:
    state = _state(connections=(_connection("not-declared"),), routes=())

    with pytest.raises(ProviderError, match="Unknown registered provider"):
        restore_provider_registry_state(state)


def test_restore_rejects_an_orphan_model() -> None:
    state = _state(
        models=(ModelSpec(id="orphan", provider_id="not-declared"),),
        routes=(),
    )

    with pytest.raises(ProviderError, match="Unknown registered provider"):
        restore_provider_registry_state(state)


def test_restore_rejects_an_orphan_route() -> None:
    state = _state(
        routes=(_route("not-declared:main", available=True),),
    )

    with pytest.raises(ValueError, match="unknown connection_id"):
        restore_provider_registry_state(state)


def test_restore_rejects_an_orphan_manifest() -> None:
    state = ProviderRegistryState(
        schema_version=SCHEMA_VERSION,
        revision=1,
        providers=(_spec("deepseek", _DEEPSEEK_URL),),
        manifests=(
            _manifest(
                "qwen-token-plan",
                _QWEN_URL,
                billing=BillingClass.SUBSCRIPTION,
            ),
        ),
        models=(),
        connections=(),
        routes=(),
    )

    with pytest.raises(ProviderError, match="Unknown registered provider"):
        restore_provider_registry_state(state)


def test_failed_restore_returns_no_partial_aggregate() -> None:
    """A rejected restore yields the exception only — never a partial graph."""
    state = _state(routes=(_route("not-declared:main", available=True),))

    with pytest.raises(ValueError, match="unknown connection_id"):
        restore_provider_registry_state(state)

    # The same payload without the orphan restores cleanly, which proves the
    # rejected attempt left no shared/global state behind.
    clean = restore_provider_registry_state(_state(routes=()))
    assert tuple(item.route_id for item in clean.routes.list()) == ()
