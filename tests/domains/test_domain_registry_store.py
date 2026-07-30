"""Phase 10.3 – Tests for InMemoryDomainRegistryStore (record-based)."""

from __future__ import annotations

import threading
from datetime import datetime, timezone

import pytest

from cmm.domains.contracts import DomainCapability, DomainDefinition
from cmm.domains.enums import DomainKind, DomainStatus
from cmm.domains.errors import DomainRegistryConflict, DomainRegistryNotFound
from cmm.domains.registry_contracts import DomainRegistryRecord
from cmm.domains.registry_store import InMemoryDomainRegistryStore


def _make_record(
    slug: str,
    version: str,
    kind: DomainKind = DomainKind.CORE,
    status: DomainStatus = DomainStatus.REGISTERED,
) -> DomainRegistryRecord:
    ts = datetime.now(timezone.utc)
    defn = DomainDefinition(
        id=f"domain:{slug}",
        name=slug,
        display_name=f"Test {slug}",
        version=version,
        kind=kind,
        description="Test domain",
        manifest_id=f"manifest:{slug}:{version}",
    )
    return DomainRegistryRecord(
        definition=defn, status=status, registered_at=ts, updated_at=ts
    )


def _make_record_with_cap(
    slug: str, version: str, cap_name: str
) -> DomainRegistryRecord:
    ts = datetime.now(timezone.utc)
    cap = DomainCapability(
        name=cap_name, kind="test", provided_by=f"domain:{slug}", version=version
    )
    defn = DomainDefinition(
        id=f"domain:{slug}",
        name=slug,
        display_name=f"Test {slug}",
        version=version,
        kind=DomainKind.CORE,
        description="Test domain with capability",
        manifest_id=f"manifest:{slug}:{version}",
        capabilities=(cap,),
    )
    return DomainRegistryRecord(
        definition=defn, status=DomainStatus.REGISTERED, registered_at=ts, updated_at=ts
    )


class TestInMemoryDomainRegistryStore:
    def test_add_and_get(self) -> None:
        store = InMemoryDomainRegistryStore()
        rec = _make_record("test", "1.0.0")
        store.add(rec)
        result = store.get("test", "1.0.0")
        assert result is not None
        assert result.definition.id.slug == "test"
        assert result.status == DomainStatus.REGISTERED

    def test_add_duplicate_identical_idempotent(self) -> None:
        store = InMemoryDomainRegistryStore()
        rec = _make_record("test", "1.0.0")
        store.add(rec)
        store.add(rec)
        assert store.get("test", "1.0.0") is not None

    def test_add_duplicate_different_raises(self) -> None:
        store = InMemoryDomainRegistryStore()
        rec1 = _make_record("test", "1.0.0")
        rec2 = _make_record("test", "1.0.0", status=DomainStatus.DISABLED)
        store.add(rec1)
        with pytest.raises(DomainRegistryConflict):
            store.add(rec2)

    def test_multiple_versions_coexist(self) -> None:
        store = InMemoryDomainRegistryStore()
        store.add(_make_record("test", "1.0.0"))
        store.add(_make_record("test", "2.0.0"))
        assert store.get("test", "1.0.0") is not None
        assert store.get("test", "2.0.0") is not None

    def test_list_returns_all(self) -> None:
        store = InMemoryDomainRegistryStore()
        store.add(_make_record("a", "1.0.0"))
        store.add(_make_record("b", "1.0.0"))
        assert len(store.list()) == 2

    def test_list_deterministic_order(self) -> None:
        store = InMemoryDomainRegistryStore()
        store.add(_make_record("b", "1.0.0"))
        store.add(_make_record("a", "1.0.0"))
        store.add(_make_record("a", "2.0.0"))
        result = store.list()
        assert result[0].definition.id.slug == "a"
        assert result[0].definition.version == "2.0.0"
        assert result[1].definition.id.slug == "a"
        assert result[1].definition.version == "1.0.0"
        assert result[2].definition.id.slug == "b"

    def test_list_no_live_views(self) -> None:
        store = InMemoryDomainRegistryStore()
        store.add(_make_record("test", "1.0.0"))
        r1 = store.list()
        r2 = store.list()
        assert r1 is not r2
        assert r1 == r2

    def test_remove(self) -> None:
        store = InMemoryDomainRegistryStore()
        store.add(_make_record("test", "1.0.0"))
        removed = store.remove("test", "1.0.0")
        assert removed.definition.id.slug == "test"
        assert store.get("test", "1.0.0") is None

    def test_remove_not_found(self) -> None:
        store = InMemoryDomainRegistryStore()
        with pytest.raises(DomainRegistryNotFound):
            store.remove("nonexistent", "1.0.0")

    def test_remove_cleans_indices(self) -> None:
        store = InMemoryDomainRegistryStore()
        store.add(_make_record_with_cap("test", "1.0.0", "my-cap"))
        store.remove("test", "1.0.0")
        assert len(store.find_by_capability("my-cap")) == 0

    def test_replace(self) -> None:
        store = InMemoryDomainRegistryStore()
        store.add(_make_record("test", "1.0.0"))
        new_rec = _make_record_with_cap("test", "1.0.0", "new-cap")
        store.replace(new_rec)
        result = store.get("test", "1.0.0")
        assert result is not None
        assert len(result.definition.capabilities) == 1

    def test_replace_not_found(self) -> None:
        store = InMemoryDomainRegistryStore()
        with pytest.raises(DomainRegistryNotFound):
            store.replace(_make_record("test", "1.0.0"))

    def test_find_by_capability(self) -> None:
        store = InMemoryDomainRegistryStore()
        store.add(_make_record_with_cap("a", "1.0.0", "cap-x"))
        store.add(_make_record_with_cap("b", "1.0.0", "cap-x"))
        store.add(_make_record_with_cap("c", "1.0.0", "cap-y"))
        assert len(store.find_by_capability("cap-x")) == 2
        assert len(store.find_by_capability("cap-y")) == 1
        assert len(store.find_by_capability("cap-z")) == 0

    def test_find_by_capability_deterministic(self) -> None:
        store = InMemoryDomainRegistryStore()
        store.add(_make_record_with_cap("b", "1.0.0", "cap-x"))
        store.add(_make_record_with_cap("a", "1.0.0", "cap-x"))
        result = store.find_by_capability("cap-x")
        assert result[0].definition.id.slug == "a"
        assert result[1].definition.id.slug == "b"

    def test_find_by_kind(self) -> None:
        store = InMemoryDomainRegistryStore()
        store.add(_make_record("a", "1.0.0", DomainKind.CORE))
        store.add(_make_record("b", "1.0.0", DomainKind.EXPERIMENTAL))
        core = store.find_by_kind(DomainKind.CORE)
        assert len(core) == 1
        assert core[0].definition.id.slug == "a"

    def test_find_by_status(self) -> None:
        store = InMemoryDomainRegistryStore()
        store.add(_make_record("test", "1.0.0", status=DomainStatus.ACTIVE))
        active = store.find_by_status(DomainStatus.ACTIVE)
        assert len(active) == 1
        assert active[0].definition.id.slug == "test"

    def test_replace_updates_status_index(self) -> None:
        store = InMemoryDomainRegistryStore()
        store.add(_make_record("test", "1.0.0", status=DomainStatus.ACTIVE))
        store.replace(_make_record("test", "1.0.0", status=DomainStatus.DISABLED))
        assert len(store.find_by_status(DomainStatus.ACTIVE)) == 0
        assert len(store.find_by_status(DomainStatus.DISABLED)) == 1

    def test_contains_via_get(self) -> None:
        store = InMemoryDomainRegistryStore()
        store.add(_make_record("test", "1.0.0"))
        assert store.get("test", "1.0.0") is not None
        assert store.get("test", "2.0.0") is None

    def test_clear(self) -> None:
        store = InMemoryDomainRegistryStore()
        store.add(_make_record("test", "1.0.0"))
        store.clear()
        assert len(store.list()) == 0

    def test_list_returns_keys_ordered(self) -> None:
        store = InMemoryDomainRegistryStore()
        store.add(_make_record("b", "1.0.0"))
        store.add(_make_record("a", "2.0.0"))
        records = store.list()
        assert len(records) == 2
        assert records[0].definition.id.slug == "a"
        assert records[0].definition.version == "2.0.0"
        assert records[1].definition.id.slug == "b"


class TestStoreThreadSafety:
    def test_concurrent_adds(self) -> None:
        store = InMemoryDomainRegistryStore()
        errors: list[Exception] = []

        def add_rec(i: int) -> None:
            try:
                store.add(_make_record(f"test-{i}", "1.0.0"))
            except Exception as exc:  # noqa: BLE001 — thread worker captures failures for assertion
                errors.append(exc)

        threads = [threading.Thread(target=add_rec, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(store.list()) == 10
