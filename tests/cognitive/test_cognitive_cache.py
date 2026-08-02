"""Phase 8.24 – Cognitive Cache tests."""

from __future__ import annotations

import ast
from datetime import datetime, timedelta, timezone
from inspect import getsourcefile
from pathlib import Path
from types import MappingProxyType

import pytest

from cmm.cognitive import (
    COGNITIVE_CACHE_SCHEMA_VERSION,
    CognitiveCache,
    CognitiveCacheContext,
    CognitiveCacheEntry,
    CognitiveCacheEntryStatus,
    CognitiveCacheLookupStatus,
    Confidence,
    InMemoryCognitiveCacheStore,
    InvalidCognitiveCacheEntryError,
    KnowledgePackage,
    Resource,
    ResourceKind,
    ResourcePermission,
    ResourcePermissionOperation,
    ResourceProvenance,
    ResourceSourceKind,
    ResourceTemporalScope,
    SensitivityLevel,
    build_cognitive_cache_context_signature,
    cache_entry_from_knowledge_package,
    cognitive_cache_entry_id,
)

NOW = datetime(2020, 1, 1, 12, 0, tzinfo=timezone.utc)


class FakeClock:
    """A fully controllable, injectable clock for deterministic time tests."""

    def __init__(self, start: datetime) -> None:
        self._current = start

    def __call__(self) -> datetime:
        return self._current

    def advance(self, delta: timedelta) -> None:
        self._current += delta

    def set(self, moment: datetime) -> None:
        self._current = moment


def make_entry(**overrides) -> CognitiveCacheEntry:
    defaults = {
        "id": "cognitive-cache:abc123",
        "key": "objective:health-summary",
        "kind": "knowledge_package",
        "value": {"summary": "verified findings"},
        "context_signature": "sha256:deadbeef",
        "profile_version": "profile-1",
        "domain_version": "domain-1",
        "source_ids": ("resource:1",),
        "dependency_ids": ("knowledge:1",),
        "process_metadata": {"produced_by": "cognitive_cycle"},
        "confidence": 0.9,
        "created_at": NOW,
        "last_validated_at": NOW,
        "valid_until": None,
        "invalidation_keys": ("health-summary",),
        "sensitivity": SensitivityLevel.PERSONAL,
        "permissions": (),
        "provenance": ("resource:1", "knowledge:1"),
        "status": CognitiveCacheEntryStatus.VALID,
        "metadata": {},
        "schema_version": COGNITIVE_CACHE_SCHEMA_VERSION,
    }
    defaults.update(overrides)
    return CognitiveCacheEntry(**defaults)


def make_context(**overrides) -> CognitiveCacheContext:
    # Default clearance is the highest tier so tests unrelated to sensitivity
    # policy are not incidentally blocked by permission checks; dedicated
    # sensitivity tests override this explicitly.
    defaults = {
        "context_signature": "sha256:deadbeef",
        "profile_version": "profile-1",
        "domain_version": "domain-1",
        "sensitivity_clearance": SensitivityLevel.RESTRICTED,
        "at": NOW,
    }
    defaults.update(overrides)
    return CognitiveCacheContext(**defaults)


def make_resource(resource_id: str, sensitivity: SensitivityLevel) -> Resource:
    return Resource(
        id=resource_id,
        domain="health",
        kind=ResourceKind.NOTE,
        source=ResourceSourceKind.USER_INPUT,
        content="patient notes",
        provenance=ResourceProvenance(
            source_type=ResourceSourceKind.USER_INPUT,
            source_id="user:1",
            retrieved_at=NOW,
        ),
        reliability=Confidence(value=0.9),
        temporal_scope=ResourceTemporalScope(ingested_at=NOW),
        sensitivity=sensitivity,
        created_at=NOW,
        updated_at=NOW,
    )


# 1. entrada mínima válida
def test_minimal_valid_entry() -> None:
    entry = make_entry()
    assert entry.id == "cognitive-cache:abc123"
    assert entry.status is CognitiveCacheEntryStatus.VALID
    assert entry.sensitivity is SensitivityLevel.PERSONAL
    assert entry.updated_at == NOW
    assert entry.invalidated_at is None


# 2. inmutabilidad
def test_entry_is_immutable() -> None:
    entry = make_entry()
    with pytest.raises(AttributeError):
        entry.status = CognitiveCacheEntryStatus.INVALID  # type: ignore[misc]
    assert isinstance(entry.value, MappingProxyType)
    assert isinstance(entry.metadata, MappingProxyType)


# 3. serialización y round-trip
def test_serialize_round_trip() -> None:
    entry = make_entry()
    payload = entry.serialize()
    assert payload == entry.to_dict()
    restored = CognitiveCacheEntry.from_mapping(payload)
    assert restored.id == entry.id
    assert restored.serialize() == payload
    assert CognitiveCacheEntry.from_dict(payload).id == restored.id


# 4. determinismo
def test_serialization_is_deterministic() -> None:
    entry = make_entry()
    assert entry.serialize() == entry.serialize()


# 5. firma estable para contextos equivalentes
def test_context_signature_stable_for_equivalent_context() -> None:
    sig_a = build_cognitive_cache_context_signature(
        objective="  Summarize   Health   Records ",
        profile_version="p1",
        dependency_ids=["b", "a"],
    )
    sig_b = build_cognitive_cache_context_signature(
        objective="summarize health records",
        profile_version="p1",
        dependency_ids=["a", "b"],
    )
    assert sig_a == sig_b


# 6. firma distinta para contextos distintos
def test_context_signature_differs_for_different_context() -> None:
    sig_a = build_cognitive_cache_context_signature(
        objective="summarize health records", profile_version="p1"
    )
    sig_b = build_cognitive_cache_context_signature(
        objective="summarize health records", profile_version="p2"
    )
    assert sig_a != sig_b


# 7. rechazo de fechas inválidas
def test_rejects_naive_datetime() -> None:
    with pytest.raises(InvalidCognitiveCacheEntryError):
        make_entry(created_at=datetime(2020, 1, 1, 12, 0))  # noqa: DTZ001
    with pytest.raises(InvalidCognitiveCacheEntryError):
        make_entry(last_validated_at=NOW - timedelta(days=1))
    with pytest.raises(InvalidCognitiveCacheEntryError):
        make_entry(valid_until=NOW - timedelta(days=1))


# 8. rechazo de versión inválida
def test_rejects_unsupported_schema_version() -> None:
    with pytest.raises(InvalidCognitiveCacheEntryError):
        make_entry(schema_version=999)


# 9. rechazo de IDs duplicados
def test_rejects_duplicate_ids() -> None:
    with pytest.raises(InvalidCognitiveCacheEntryError):
        make_entry(source_ids=("a", "a"))
    with pytest.raises(InvalidCognitiveCacheEntryError):
        make_entry(dependency_ids=("a", "a"))
    with pytest.raises(InvalidCognitiveCacheEntryError):
        make_entry(invalidation_keys=("a", "a"))


# 10. rechazo de value no serializable
def test_rejects_non_serializable_value() -> None:
    with pytest.raises(InvalidCognitiveCacheEntryError):
        make_entry(value={"bad": object()})


# 11. store protocol
def test_store_implements_protocol() -> None:
    from cmm.cognitive import CognitiveCacheStoreProtocol

    store = InMemoryCognitiveCacheStore()
    assert isinstance(store, CognitiveCacheStoreProtocol)


# 12. put/get
def test_put_and_get() -> None:
    store = InMemoryCognitiveCacheStore()
    entry = make_entry()
    store.put(entry)
    assert store.get(entry.id).id == entry.id


# 13. búsqueda por key + context signature
def test_get_by_key_and_context_signature() -> None:
    store = InMemoryCognitiveCacheStore()
    entry = make_entry()
    store.put(entry)
    found = store.get_by_key(entry.key, entry.context_signature)
    assert found is not None
    assert found.id == entry.id


# 14. detección de miss
def test_cache_miss() -> None:
    cache = CognitiveCache(InMemoryCognitiveCacheStore())
    result = cache.get("unknown-key", make_context())
    assert result.status is CognitiveCacheLookupStatus.MISS
    assert result.hit is False
    assert result.reusable is False


# 15. detección de context mismatch
def test_context_mismatch() -> None:
    store = InMemoryCognitiveCacheStore()
    cache = CognitiveCache(store)
    entry = make_entry()
    store.put(entry)
    result = cache.get(entry.key, make_context(context_signature="sha256:other"))
    assert result.status is CognitiveCacheLookupStatus.CONTEXT_MISMATCH
    assert result.reusable is False
    assert result.requires_revalidation is True


# 16. expiración
def test_expired_entry_not_reusable() -> None:
    store = InMemoryCognitiveCacheStore()
    cache = CognitiveCache(store)
    entry = make_entry(valid_until=NOW + timedelta(hours=1))
    store.put(entry)
    result = cache.get(entry.key, make_context(at=NOW + timedelta(hours=2)))
    assert result.status is CognitiveCacheLookupStatus.HIT_EXPIRED
    assert result.reusable is False


# 17. invalidación explícita
def test_explicit_invalidation() -> None:
    store = InMemoryCognitiveCacheStore()
    cache = CognitiveCache(store)
    entry = make_entry()
    store.put(entry)
    updated = cache.invalidate(entry.id, reason="manual review")
    assert updated.status is CognitiveCacheEntryStatus.INVALID
    result = cache.get(entry.key, make_context())
    assert result.status is CognitiveCacheLookupStatus.HIT_INVALID


# 18. invalidación por source
def test_invalidate_by_source_id() -> None:
    store = InMemoryCognitiveCacheStore()
    cache = CognitiveCache(store)
    entry = make_entry()
    store.put(entry)
    invalidated = cache.invalidate_by_source_id("resource:1")
    assert len(invalidated) == 1
    assert invalidated[0].status is CognitiveCacheEntryStatus.INVALID


# 19. invalidación por dependency
def test_invalidate_by_dependency_id() -> None:
    store = InMemoryCognitiveCacheStore()
    cache = CognitiveCache(store)
    entry = make_entry()
    store.put(entry)
    invalidated = cache.invalidate_by_dependency_id("knowledge:1")
    assert len(invalidated) == 1
    assert invalidated[0].status is CognitiveCacheEntryStatus.INVALID


# 20. invalidación por invalidation key
def test_invalidate_by_invalidation_key() -> None:
    store = InMemoryCognitiveCacheStore()
    cache = CognitiveCache(store)
    entry = make_entry()
    store.put(entry)
    invalidated = cache.invalidate_by_key("health-summary")
    assert len(invalidated) == 1
    assert invalidated[0].status is CognitiveCacheEntryStatus.INVALID


# 21. invalidación por profile version
def test_invalidate_by_profile_version() -> None:
    store = InMemoryCognitiveCacheStore()
    cache = CognitiveCache(store)
    entry = make_entry()
    store.put(entry)
    invalidated = cache.invalidate_by_profile_version("profile-1")
    assert len(invalidated) == 1
    assert invalidated[0].status is CognitiveCacheEntryStatus.INVALID


# 22. invalidación por domain version
def test_invalidate_by_domain_version() -> None:
    store = InMemoryCognitiveCacheStore()
    cache = CognitiveCache(store)
    entry = make_entry()
    store.put(entry)
    invalidated = cache.invalidate_by_domain_version("domain-1")
    assert len(invalidated) == 1
    assert invalidated[0].status is CognitiveCacheEntryStatus.INVALID


# 23. permission denied
def test_permission_denied() -> None:
    store = InMemoryCognitiveCacheStore()
    cache = CognitiveCache(store)
    permission = ResourcePermission(
        allowed_actor_ids=("actor-a",),
        allowed_operations=(ResourcePermissionOperation.READ,),
    )
    entry = make_entry(permissions=(permission,))
    store.put(entry)
    result = cache.get(entry.key, make_context(actor_id="actor-b"))
    assert result.status is CognitiveCacheLookupStatus.PERMISSION_DENIED
    assert result.reusable is False

    allowed_result = cache.get(entry.key, make_context(actor_id="actor-a"))
    assert allowed_result.status is CognitiveCacheLookupStatus.HIT_REUSABLE


# 24. sensitivity preservada
def test_sensitivity_preserved_and_enforced() -> None:
    store = InMemoryCognitiveCacheStore()
    cache = CognitiveCache(store)
    entry = make_entry(sensitivity=SensitivityLevel.HIGHLY_SENSITIVE)
    store.put(entry)
    assert store.get(entry.id).sensitivity is SensitivityLevel.HIGHLY_SENSITIVE

    denied = cache.get(
        entry.key, make_context(sensitivity_clearance=SensitivityLevel.INTERNAL)
    )
    assert denied.status is CognitiveCacheLookupStatus.PERMISSION_DENIED

    allowed = cache.get(
        entry.key, make_context(sensitivity_clearance=SensitivityLevel.RESTRICTED)
    )
    assert allowed.status is CognitiveCacheLookupStatus.HIT_REUSABLE


# 25. stale no reutilizable
def test_stale_entry_not_reusable() -> None:
    store = InMemoryCognitiveCacheStore()
    cache = CognitiveCache(store)
    entry = make_entry(status=CognitiveCacheEntryStatus.STALE)
    store.put(entry)
    result = cache.get(entry.key, make_context())
    assert result.status is CognitiveCacheLookupStatus.HIT_STALE
    assert result.reusable is False
    assert result.requires_revalidation is True


# 26. invalid no reutilizable
def test_invalid_entry_not_reusable() -> None:
    store = InMemoryCognitiveCacheStore()
    cache = CognitiveCache(store)
    entry = make_entry(status=CognitiveCacheEntryStatus.INVALID)
    store.put(entry)
    result = cache.get(entry.key, make_context())
    assert result.status is CognitiveCacheLookupStatus.HIT_INVALID
    assert result.reusable is False


# 27. revalidation required
def test_revalidation_required_on_profile_mismatch() -> None:
    store = InMemoryCognitiveCacheStore()
    cache = CognitiveCache(store)
    entry = make_entry()
    store.put(entry)
    result = cache.get(entry.key, make_context(profile_version="profile-2"))
    assert result.status is CognitiveCacheLookupStatus.REVALIDATION_REQUIRED
    assert result.requires_revalidation is True


# 28. revalidación válida
def test_revalidate_marks_entry_valid() -> None:
    store = InMemoryCognitiveCacheStore()
    cache = CognitiveCache(store)
    entry = make_entry(status=CognitiveCacheEntryStatus.STALE)
    store.put(entry)
    revalidated = cache.revalidate(entry.id, make_context())
    assert revalidated.status is CognitiveCacheEntryStatus.VALID
    result = cache.get(entry.key, make_context())
    assert result.status is CognitiveCacheLookupStatus.HIT_REUSABLE


# 29. auditoría del motivo de invalidación
def test_invalidation_audit_trail() -> None:
    store = InMemoryCognitiveCacheStore()
    cache = CognitiveCache(store)
    entry = make_entry()
    store.put(entry)
    updated = cache.invalidate(entry.id, reason="dependency removed")
    assert len(updated.audit_log) == 1
    record = updated.audit_log[0]
    assert record["reason"] == "dependency removed"
    assert record["to"] == "invalid"
    assert "at" in record


# 30. integración con KnowledgePackage
def test_cache_entry_from_knowledge_package() -> None:
    package = KnowledgePackage(
        id="pkg-1", objective="summarize", profile="profile-1", created_at=NOW
    )
    entry = cache_entry_from_knowledge_package(
        package,
        key="objective:summarize",
        context_signature="sha256:pkg",
        profile_version="profile-1",
        sensitivity=SensitivityLevel.PUBLIC,
    )
    assert entry.kind == "knowledge_package"
    assert entry.value["id"] == "pkg-1"
    assert entry.profile_version == "profile-1"

    store = InMemoryCognitiveCacheStore()
    cache = CognitiveCache(store)
    cache.put(entry)
    result = cache.get(
        "objective:summarize",
        make_context(
            context_signature="sha256:pkg",
            profile_version="profile-1",
            domain_version=None,
            sensitivity_clearance=SensitivityLevel.PUBLIC,
        ),
    )
    assert result.status is CognitiveCacheLookupStatus.HIT_REUSABLE


# 31. KnowledgePackage expirado no reutilizable
def test_expired_knowledge_package_not_reusable() -> None:
    package = KnowledgePackage(
        id="pkg-2",
        objective="summarize",
        profile="profile-1",
        created_at=NOW,
        valid_until=NOW + timedelta(minutes=1),
    )
    entry = cache_entry_from_knowledge_package(
        package,
        key="objective:summarize-2",
        context_signature="sha256:pkg2",
        profile_version="profile-1",
        sensitivity=SensitivityLevel.PUBLIC,
    )
    store = InMemoryCognitiveCacheStore()
    cache = CognitiveCache(store)
    cache.put(entry)
    result = cache.get(
        "objective:summarize-2",
        make_context(
            context_signature="sha256:pkg2",
            profile_version="profile-1",
            domain_version=None,
            sensitivity_clearance=SensitivityLevel.PUBLIC,
            at=NOW + timedelta(hours=1),
        ),
    )
    assert result.status is CognitiveCacheLookupStatus.HIT_EXPIRED
    assert result.reusable is False


# 32. provenance preservada
def test_provenance_preserved() -> None:
    entry = make_entry()
    assert entry.provenance == ("resource:1", "knowledge:1")
    restored = CognitiveCacheEntry.from_mapping(entry.serialize())
    assert restored.provenance == entry.provenance


# 33. exclusión de imports de providers/routing
def test_module_has_no_provider_or_routing_imports() -> None:
    source_path = getsourcefile(CognitiveCacheEntry)
    assert source_path is not None
    tree = ast.parse(Path(source_path).read_text(encoding="utf-8"))
    imported_modules = [
        node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
    ]
    forbidden = ("provider", "routing", "llm", "model_catalog", "prompt_cache")
    for module in imported_modules:
        assert not any(term in module for term in forbidden), module


# 34. API pública
def test_public_api_exports_cognitive_cache_symbols() -> None:
    from cmm import cognitive

    for name in (
        "CognitiveCache",
        "CognitiveCacheEntry",
        "CognitiveCacheEntryStatus",
        "CognitiveCacheLookupResult",
        "CognitiveCacheLookupStatus",
        "CognitiveCacheContext",
        "CognitiveCacheStoreProtocol",
        "InMemoryCognitiveCacheStore",
        "CognitiveCacheValidator",
    ):
        assert hasattr(cognitive, name), name


# 35. compatibilidad con el resto del paquete cognitivo
def test_compatible_with_rest_of_cognitive_package() -> None:
    from cmm.cognitive import (
        InMemoryKnowledgeStore,
        KnowledgePackageBuilder,
        KnowledgePackageRequest,
    )

    knowledge_store = InMemoryKnowledgeStore()
    package = KnowledgePackageBuilder(knowledge_store).build(
        KnowledgePackageRequest(objective="unrelated topic")
    )
    entry = cache_entry_from_knowledge_package(
        package,
        key="objective:unrelated",
        context_signature="sha256:compat",
        sensitivity=SensitivityLevel.PUBLIC,
    )
    store = InMemoryCognitiveCacheStore()
    cache = CognitiveCache(store)
    cache.put(entry)
    assert store.get(entry.id).kind == "knowledge_package"


def test_entry_id_helper_is_deterministic() -> None:
    a = cognitive_cache_entry_id("key", "sha256:x")
    b = cognitive_cache_entry_id("key", "sha256:x")
    assert a == b
    assert a != cognitive_cache_entry_id("key", "sha256:y")


def test_invalid_ids_and_keys_rejected() -> None:
    with pytest.raises(InvalidCognitiveCacheEntryError):
        make_entry(id="")
    with pytest.raises(InvalidCognitiveCacheEntryError):
        make_entry(key="")
    with pytest.raises(InvalidCognitiveCacheEntryError):
        make_entry(context_signature="")


def test_invalid_status_rejected() -> None:
    with pytest.raises(InvalidCognitiveCacheEntryError):
        make_entry(status="not-a-status")


def test_store_conflict_on_incompatible_overwrite() -> None:
    from cmm.cognitive import CognitiveCacheConflictError

    store = InMemoryCognitiveCacheStore()
    entry = make_entry()
    store.put(entry)
    conflicting = make_entry(value={"summary": "different"})
    with pytest.raises(CognitiveCacheConflictError):
        store.put(conflicting)


# ── Additional required coverage: injectable clock ──────────────────────────


# 1. reloj fijo
def test_fixed_clock_drives_invalidation_timestamps() -> None:
    clock = FakeClock(NOW + timedelta(days=1))
    store = InMemoryCognitiveCacheStore(clock=clock)
    cache = CognitiveCache(store, clock=clock)
    entry = make_entry()
    store.put(entry)
    updated = cache.invalidate(entry.id, reason="fixed clock test")
    assert updated.invalidated_at == NOW + timedelta(days=1)
    assert updated.updated_at == NOW + timedelta(days=1)


# 2. clock skew: a clock returning a moment before created_at must be rejected,
# never silently accepted as a valid transition timestamp.
def test_clock_skew_before_created_at_is_rejected() -> None:
    skewed_clock = FakeClock(NOW - timedelta(days=1))
    store = InMemoryCognitiveCacheStore(clock=skewed_clock)
    entry = make_entry()
    store.put(entry)
    with pytest.raises(InvalidCognitiveCacheEntryError):
        store.invalidate(entry.id, reason="skewed clock")


# 3. invalidación no modifica last_validated_at
def test_invalidation_does_not_touch_last_validated_at() -> None:
    clock = FakeClock(NOW + timedelta(hours=2))
    store = InMemoryCognitiveCacheStore(clock=clock)
    entry = make_entry()
    store.put(entry)
    updated = store.invalidate(entry.id, reason="dependency removed")
    assert updated.last_validated_at == NOW
    assert updated.invalidated_at == NOW + timedelta(hours=2)
    assert updated.updated_at == NOW + timedelta(hours=2)


# 4. revalidación sí modifica last_validated_at
def test_revalidation_updates_last_validated_at() -> None:
    store = InMemoryCognitiveCacheStore()
    cache = CognitiveCache(store)
    entry = make_entry(status=CognitiveCacheEntryStatus.STALE)
    store.put(entry)
    context = make_context(at=NOW + timedelta(hours=5))
    revalidated = cache.revalidate(entry.id, context)
    assert revalidated.last_validated_at == NOW + timedelta(hours=5)
    assert revalidated.invalidated_at is None


# 5. invalidated_at (equivalente de metadata temporal explícita) preservado en round-trip
def test_invalidated_at_preserved_in_round_trip() -> None:
    store = InMemoryCognitiveCacheStore()
    entry = make_entry()
    store.put(entry)
    updated = store.invalidate(entry.id, reason="dependency removed")
    restored = CognitiveCacheEntry.from_mapping(updated.serialize())
    assert restored.invalidated_at == updated.invalidated_at
    assert restored.updated_at == updated.updated_at
    assert restored.last_validated_at == updated.last_validated_at


# 6. sensibilidad sin clearance: pública reutilizable, personal/altamente sensible denegadas
def test_public_sensitivity_reusable_without_clearance() -> None:
    store = InMemoryCognitiveCacheStore()
    cache = CognitiveCache(store)
    entry = make_entry(sensitivity=SensitivityLevel.PUBLIC)
    store.put(entry)
    result = cache.get(entry.key, make_context(sensitivity_clearance=None))
    assert result.status is CognitiveCacheLookupStatus.HIT_REUSABLE


def test_personal_sensitivity_denied_without_clearance() -> None:
    store = InMemoryCognitiveCacheStore()
    cache = CognitiveCache(store)
    entry = make_entry(sensitivity=SensitivityLevel.PERSONAL)
    store.put(entry)
    result = cache.get(entry.key, make_context(sensitivity_clearance=None))
    assert result.status is CognitiveCacheLookupStatus.PERMISSION_DENIED


def test_highly_sensitive_denied_without_clearance() -> None:
    store = InMemoryCognitiveCacheStore()
    cache = CognitiveCache(store)
    entry = make_entry(sensitivity=SensitivityLevel.HIGHLY_SENSITIVE)
    store.put(entry)
    result = cache.get(entry.key, make_context(sensitivity_clearance=None))
    assert result.status is CognitiveCacheLookupStatus.PERMISSION_DENIED


def test_insufficient_clearance_denied() -> None:
    store = InMemoryCognitiveCacheStore()
    cache = CognitiveCache(store)
    entry = make_entry(sensitivity=SensitivityLevel.SENSITIVE)
    store.put(entry)
    result = cache.get(
        entry.key, make_context(sensitivity_clearance=SensitivityLevel.PERSONAL)
    )
    assert result.status is CognitiveCacheLookupStatus.PERMISSION_DENIED


def test_sufficient_clearance_allowed() -> None:
    store = InMemoryCognitiveCacheStore()
    cache = CognitiveCache(store)
    entry = make_entry(sensitivity=SensitivityLevel.SENSITIVE)
    store.put(entry)
    result = cache.get(
        entry.key, make_context(sensitivity_clearance=SensitivityLevel.SENSITIVE)
    )
    assert result.status is CognitiveCacheLookupStatus.HIT_REUSABLE


# 7. no downgrade de sensibilidad al construir desde un KnowledgePackage
def test_cache_entry_from_package_never_downgrades_sensitivity() -> None:
    package = KnowledgePackage(
        id="pkg-sensitive",
        objective="summarize",
        resources=(
            make_resource("resource:sensitive", SensitivityLevel.HIGHLY_SENSITIVE),
        ),
        created_at=NOW,
    )
    entry = cache_entry_from_knowledge_package(
        package,
        key="k-sensitive",
        context_signature="sig-sensitive",
        sensitivity=SensitivityLevel.PUBLIC,
    )
    assert entry.sensitivity is SensitivityLevel.HIGHLY_SENSITIVE


def test_cache_entry_from_package_defaults_to_restrictive_without_signal() -> None:
    package = KnowledgePackage(
        id="pkg-no-signal", objective="summarize", created_at=NOW
    )
    entry = cache_entry_from_knowledge_package(
        package, key="k-no-signal", context_signature="sig-no-signal"
    )
    assert entry.sensitivity is SensitivityLevel.RESTRICTED


# 8. profile/domain separados de sus versiones
def test_profile_and_domain_separated_from_versions() -> None:
    package = KnowledgePackage(
        id="pkg-versions",
        objective="summarize",
        profile="clinical-profile",
        domain="health",
        created_at=NOW,
    )
    entry = cache_entry_from_knowledge_package(
        package,
        key="k-versions",
        context_signature="sig-versions",
        profile_version="v3",
        domain_version="v7",
        sensitivity=SensitivityLevel.PUBLIC,
    )
    assert entry.profile_version == "v3"
    assert entry.domain_version == "v7"
    assert entry.value["profile"] == "clinical-profile"
    assert entry.value["domain"] == "health"
    assert entry.profile_version != entry.value["profile"]
    assert entry.domain_version != entry.value["domain"]


# 9. expiración determinista con reloj inyectado
def test_deterministic_expiration_with_fixed_clock() -> None:
    clock = FakeClock(NOW + timedelta(days=2))
    store = InMemoryCognitiveCacheStore(clock=clock)
    cache = CognitiveCache(store, clock=clock)
    entry = make_entry(valid_until=NOW + timedelta(days=1))
    cache.put(entry)
    stored = store.get(entry.id)
    assert stored.status is CognitiveCacheEntryStatus.EXPIRED
    assert stored.invalidated_at == NOW + timedelta(days=2)
    assert stored.last_validated_at == NOW  # not touched: this was not a revalidation


# 10. política elegida para permisos revocados: diferido explícitamente a 8.25
def test_revoked_permission_invalidation_is_deferred_to_phase_8_25() -> None:
    assert not hasattr(CognitiveCache, "invalidate_by_revoked_permission")


# 11. invalidate_by_schema_version
def test_invalidate_by_schema_version() -> None:
    store = InMemoryCognitiveCacheStore()
    cache = CognitiveCache(store)
    entry = make_entry()
    store.put(entry)
    invalidated = cache.invalidate_by_schema_version(COGNITIVE_CACHE_SCHEMA_VERSION)
    assert len(invalidated) == 1
    assert invalidated[0].status is CognitiveCacheEntryStatus.INVALID


# 12. invalidate_expired
def test_invalidate_expired() -> None:
    clock = FakeClock(NOW + timedelta(days=10))
    store = InMemoryCognitiveCacheStore(clock=clock)
    cache = CognitiveCache(store, clock=clock)
    entry = make_entry(valid_until=NOW + timedelta(days=1))
    store.put(entry)  # store.put bypasses CognitiveCache.put's auto-downgrade
    expired = cache.invalidate_expired()
    assert len(expired) == 1
    assert expired[0].status is CognitiveCacheEntryStatus.EXPIRED
    assert expired[0].invalidated_at == NOW + timedelta(days=10)
