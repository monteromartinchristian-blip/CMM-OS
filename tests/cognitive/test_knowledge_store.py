"""Phase 8.5 – Knowledge Store tests.

Covers InMemoryKnowledgeStore, SQLiteKnowledgeStore, entity round-trips, atomic transactions,
corruption detection, schema versioning, path escaping, and public API compatibility.
"""

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest

from cmm.cognitive import (
    Confidence,
    Contradiction,
    ContradictionSeverity,
    ContradictionStatus,
    Evidence,
    EvidenceKind,
    EvidencePolarityKind,
    InMemoryKnowledgeStore,
    KnowledgeBundle,
    KnowledgeItem,
    KnowledgeKind,
    KnowledgeRelation,
    KnowledgeRelationKind,
    KnowledgeStatus,
    KnowledgeStoreConflictError,
    KnowledgeStoreCorruptionError,
    KnowledgeStoreError,
    KnowledgeStoreNotFoundError,
    KnowledgeStoreProtocol,
    KnowledgeStoreSchemaError,
    LocalKnowledgeStore,
    SensitivityLevel,
    SQLiteKnowledgeStore,
    TemporalScope,
    TemporalScopeKind,
)

NOW = datetime(2026, 7, 25, 12, 0, 0, tzinfo=timezone.utc)


def _sample_evidence(ev_id: str = "evidence:test:1") -> Evidence:
    return Evidence(
        id=ev_id,
        resource_id="res-123",
        fragment="Supporting text fragment.",
        confidence=Confidence(0.9),
        kind=EvidenceKind.DOCUMENT_REFERENCE,
        polarity=EvidencePolarityKind.SUPPORTING,
        observed_at=NOW,
    )


def _sample_item(item_id: str = "knowledge-item:knowledge:1") -> KnowledgeItem:
    return KnowledgeItem(
        id=item_id,
        statement="Cognitive Layer operates deterministically.",
        kind=KnowledgeKind.FACT,
        status=KnowledgeStatus.ACTIVE,
        confidence=Confidence(0.95),
        evidence=(_sample_evidence("evidence:test:1"),),
        relations=(
            KnowledgeRelation(
                id="knowledge-relation:test:1",
                source_id=item_id,
                target_id="knowledge-item:knowledge:target",
                kind=KnowledgeRelationKind.SUPPORTS,
                confidence=Confidence(0.9),
                created_at=NOW,
            ),
        ),
        temporal_scope=TemporalScope(
            kind=TemporalScopeKind.INTERVAL,
            valid_from=NOW,
            valid_until=NOW + timedelta(days=30),
        ),
        sensitivity=SensitivityLevel.HIGHLY_SENSITIVE,
        actor_id="actor:system:1",
        resource_id="res-123",
        version=1,
        created_at=NOW,
        updated_at=NOW,
        metadata={"domain": "cognitive"},
    )


def _sample_contradiction(con_id: str = "contradiction:test:1") -> Contradiction:
    return Contradiction(
        id=con_id,
        item_a_id="knowledge-item:knowledge:1",
        item_b_id="knowledge-item:knowledge:2",
        severity=ContradictionSeverity.HIGH,
        status=ContradictionStatus.UNRESOLVED,
        supporting_evidence=(
            Evidence(
                id="evidence:test:con",
                resource_id="res-456",
                fragment="Contradicting fragment text.",
                confidence=Confidence(0.85),
                kind=EvidenceKind.PARAPHRASE,
                polarity=EvidencePolarityKind.CONTRADICTING,
                observed_at=NOW,
            ),
        ),
        explanation="Statements disagree on behavior.",
        preferred_id="knowledge-item:knowledge:1",
        preference_reason="Higher source authority.",
        remaining_uncertainty=0.1,
        actor_id="actor:verifier:1",
        created_at=NOW,
        metadata={"priority": "high"},
    )


def _sample_bundle(bundle_id: str = "knowledge-bundle:test:1") -> KnowledgeBundle:
    item1 = _sample_item("knowledge-item:knowledge:b1")
    item2_created = NOW + timedelta(seconds=1)
    item2 = KnowledgeItem(
        id="knowledge-item:knowledge:b2",
        statement="Alternative hypothesis statement.",
        kind=KnowledgeKind.HYPOTHESIS,
        confidence=Confidence(0.8),
        created_at=item2_created,
        updated_at=item2_created,
    )
    evidence1 = _sample_evidence("evidence:test:b1")
    relation1 = KnowledgeRelation(
        id="knowledge-relation:test:b1",
        source_id=item1.id,
        target_id=item2.id,
        kind=KnowledgeRelationKind.CONTRADICTS,
        confidence=Confidence(0.9),
        created_at=NOW,
    )
    contradiction1 = Contradiction(
        id="contradiction:test:b1",
        item_a_id=item1.id,
        item_b_id=item2.id,
        created_at=NOW,
    )
    return KnowledgeBundle(
        id=bundle_id,
        items=(item1, item2),
        evidence=(evidence1,),
        relations=(relation1,),
        contradictions=(contradiction1,),
        open_questions=("How to reconcile differences?",),
        findings=("Found 1 contradiction.",),
        actor_id="actor:agent:1",
        status="complete",
        created_at=NOW,
        metadata={"batch": 1},
    )


# ── Protocol Compliance ───────────────────────────────────────────────────────


def test_stores_implement_protocol() -> None:
    mem_store = InMemoryKnowledgeStore()
    sql_store = SQLiteKnowledgeStore(":memory:")
    assert isinstance(mem_store, KnowledgeStoreProtocol)
    assert isinstance(sql_store, KnowledgeStoreProtocol)
    assert LocalKnowledgeStore is SQLiteKnowledgeStore
    sql_store.close()


# ── InMemoryKnowledgeStore Tests ──────────────────────────────────────────────


def test_in_memory_item_lifecycle() -> None:
    store = InMemoryKnowledgeStore()
    item = _sample_item()

    assert not store.contains_item(item.id)
    saved = store.save_item(item)
    assert saved == item
    assert store.contains_item(item.id)

    retrieved = store.get_item(item.id)
    assert retrieved == item
    assert retrieved is not item  # Defensive copy

    # Overwrite / update
    updated_item = KnowledgeItem(
        id=item.id,
        statement="Updated statement.",
        kind=item.kind,
        confidence=item.confidence,
        version=2,
        created_at=NOW,
        updated_at=NOW + timedelta(minutes=5),
    )
    store.save_item(updated_item)
    assert store.get_item(item.id) == updated_item

    # Delete
    store.delete_item(item.id)
    assert not store.contains_item(item.id)

    with pytest.raises(KnowledgeStoreNotFoundError):
        store.get_item(item.id)

    with pytest.raises(KnowledgeStoreNotFoundError):
        store.delete_item(item.id)


def test_in_memory_defensive_copies() -> None:
    store = InMemoryKnowledgeStore()
    item = _sample_item()
    store.save_item(item)

    retrieved1 = store.get_item(item.id)
    retrieved2 = store.get_item(item.id)

    assert retrieved1 == retrieved2
    assert retrieved1 is not retrieved2


def test_in_memory_item_filters_and_ordering() -> None:
    store = InMemoryKnowledgeStore()

    item1 = KnowledgeItem(
        id="knowledge-item:knowledge:b",
        statement="Statement B",
        kind=KnowledgeKind.FACT,
        status=KnowledgeStatus.ACTIVE,
        confidence=Confidence(0.9),
        resource_id="res-1",
        created_at=NOW,
        updated_at=NOW,
    )
    item2 = KnowledgeItem(
        id="knowledge-item:knowledge:a",
        statement="Statement A",
        kind=KnowledgeKind.FACT,
        status=KnowledgeStatus.ACTIVE,
        confidence=Confidence(0.9),
        resource_id="res-1",
        created_at=NOW,
        updated_at=NOW,
    )
    item3_created = NOW + timedelta(hours=1)
    item3 = KnowledgeItem(
        id="knowledge-item:knowledge:c",
        statement="Statement C",
        kind=KnowledgeKind.HYPOTHESIS,
        status=KnowledgeStatus.UNVERIFIED,
        confidence=Confidence(0.7),
        resource_id="res-2",
        created_at=item3_created,
        updated_at=item3_created,
    )

    store.save_item(item1)
    store.save_item(item2)
    store.save_item(item3)

    # Deterministic order: created_at ASC, id ASC
    all_items = store.list_items()
    assert len(all_items) == 3
    assert [i.id for i in all_items] == [
        "knowledge-item:knowledge:a",
        "knowledge-item:knowledge:b",
        "knowledge-item:knowledge:c",
    ]

    assert store.count_items() == 3

    # Filtering by kind
    facts = store.list_items(kind=KnowledgeKind.FACT)
    assert len(facts) == 2
    assert store.count_items(kind=KnowledgeKind.FACT) == 2

    # Filtering by resource_id
    res1_items = store.list_items(resource_id="res-1")
    assert len(res1_items) == 2

    # Pagination
    paged = store.list_items(limit=1, offset=1)
    assert len(paged) == 1
    assert paged[0].id == "knowledge-item:knowledge:b"


def test_in_memory_type_conflict() -> None:
    store = InMemoryKnowledgeStore()
    item = _sample_item("clashing-id")
    store.save_item(item)

    evidence = _sample_evidence("clashing-id")
    with pytest.raises(KnowledgeStoreConflictError):
        store.save_evidence(evidence)


# ── SQLiteKnowledgeStore Tests ────────────────────────────────────────────────


def test_sqlite_persistence_and_reopen(tmp_path: Path) -> None:
    db_file = tmp_path / "test_knowledge.db"

    # First instance
    with SQLiteKnowledgeStore(db_file) as store1:
        item = _sample_item()
        store1.save_item(item)
        assert store1.contains_item(item.id)

    # Second instance reopening same database file
    with SQLiteKnowledgeStore(db_file) as store2:
        assert store2.contains_item(item.id)
        restored = store2.get_item(item.id)
        assert restored == item


def test_sqlite_schema_version_check(tmp_path: Path) -> None:
    db_file = tmp_path / "schema_test.db"

    # Initialize store
    with SQLiteKnowledgeStore(db_file):
        pass

    # Manually corrupt schema version in database
    conn = sqlite3.connect(db_file)
    conn.execute("UPDATE store_metadata SET value = '999' WHERE key = 'schema_version'")
    conn.commit()
    conn.close()

    with pytest.raises(KnowledgeStoreSchemaError):
        SQLiteKnowledgeStore(db_file)


def test_sqlite_corrupt_json_payload(tmp_path: Path) -> None:
    db_file = tmp_path / "corrupt_test.db"

    with SQLiteKnowledgeStore(db_file) as store:
        item = _sample_item("item-corrupt")
        store.save_item(item)

    # Inject corrupt JSON directly into database
    conn = sqlite3.connect(db_file)
    conn.execute(
        "UPDATE knowledge_records SET payload_json = '{bad json' WHERE record_id = 'item-corrupt'"
    )
    conn.commit()
    conn.close()

    with (
        SQLiteKnowledgeStore(db_file) as store,
        pytest.raises(KnowledgeStoreCorruptionError),
    ):
        store.get_item("item-corrupt")


def test_sqlite_invalid_ids_and_paths() -> None:
    with SQLiteKnowledgeStore(":memory:") as store:
        with pytest.raises(KnowledgeStoreError):
            store.get_item("")

        with pytest.raises(KnowledgeStoreError):
            store.get_item("   ")

        with pytest.raises(KnowledgeStoreError):
            store.get_item(123)  # type: ignore

    # Test relative path escaping project root
    escaping_relative = "../../../outside_project_store.db"
    with pytest.raises(KnowledgeStoreError):
        SQLiteKnowledgeStore(escaping_relative)


# ── Entity Round-Trips ────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "store_factory", [InMemoryKnowledgeStore, lambda: SQLiteKnowledgeStore(":memory:")]
)
def test_knowledge_item_full_round_trip(store_factory: Any) -> None:
    store = store_factory()
    item = _sample_item()

    store.save_item(item)
    restored = store.get_item(item.id)

    assert restored == item
    assert restored.statement == item.statement
    assert restored.kind == item.kind
    assert restored.status == item.status
    assert restored.confidence == item.confidence
    assert restored.evidence == item.evidence
    assert restored.relations == item.relations
    assert restored.temporal_scope == item.temporal_scope
    assert restored.sensitivity == item.sensitivity
    assert restored.actor_id == item.actor_id
    assert restored.resource_id == item.resource_id
    assert restored.version == item.version
    assert restored.metadata == item.metadata

    if hasattr(store, "close"):
        store.close()


@pytest.mark.parametrize(
    "store_factory", [InMemoryKnowledgeStore, lambda: SQLiteKnowledgeStore(":memory:")]
)
def test_contradiction_full_round_trip(store_factory: Any) -> None:
    store = store_factory()
    contradiction = _sample_contradiction()

    store.save_contradiction(contradiction)
    restored = store.get_contradiction(contradiction.id)

    assert restored == contradiction
    assert restored.item_a_id == contradiction.item_a_id
    assert restored.item_b_id == contradiction.item_b_id
    assert restored.severity == contradiction.severity
    assert restored.status == contradiction.status
    assert restored.supporting_evidence == contradiction.supporting_evidence
    assert restored.preferred_id == contradiction.preferred_id
    assert restored.preference_reason == contradiction.preference_reason
    assert restored.remaining_uncertainty == contradiction.remaining_uncertainty
    assert restored.actor_id == contradiction.actor_id
    assert restored.metadata == contradiction.metadata

    # Check contradiction list filter
    matching = store.list_contradictions(item_id="knowledge-item:knowledge:1")
    assert len(matching) == 1
    assert matching[0] == contradiction

    if hasattr(store, "close"):
        store.close()


@pytest.mark.parametrize(
    "store_factory", [InMemoryKnowledgeStore, lambda: SQLiteKnowledgeStore(":memory:")]
)
def test_bundle_full_round_trip(store_factory: Any) -> None:
    store = store_factory()
    bundle = _sample_bundle()

    store.save_bundle(bundle)
    restored = store.get_bundle(bundle.id)

    assert restored == bundle
    assert len(restored.items) == 2
    assert len(restored.evidence) == 1
    assert len(restored.relations) == 1
    assert len(restored.contradictions) == 1

    # Strategy B check: internal entities are also stored and queryable
    for item in bundle.items:
        assert store.contains_item(item.id)
        assert store.get_item(item.id) == item

    for ev in bundle.evidence:
        assert store.contains_evidence(ev.id)
        assert store.get_evidence(ev.id) == ev

    for rel in bundle.relations:
        assert store.contains_relation(rel.id)
        assert store.get_relation(rel.id) == rel

    for con in bundle.contradictions:
        assert store.contains_contradiction(con.id)
        assert store.get_contradiction(con.id) == con

    if hasattr(store, "close"):
        store.close()


# ── Atomicity and Rollback ────────────────────────────────────────────────────


def test_sqlite_bundle_transaction_atomicity(tmp_path: Path) -> None:
    db_file = tmp_path / "atomic_bundle.db"

    # Pre-register an item with ID 'clashing-id' as an evidence record to trigger conflict during bundle save
    with SQLiteKnowledgeStore(db_file) as store:
        pre_existing_ev = _sample_evidence("clashing-id")
        store.save_evidence(pre_existing_ev)

    with SQLiteKnowledgeStore(db_file) as store:
        # Create bundle containing a KnowledgeItem with ID 'clashing-id'
        bad_item = KnowledgeItem(
            id="clashing-id",
            statement="This will conflict with evidence record.",
            kind=KnowledgeKind.FACT,
            confidence=Confidence(0.8),
            created_at=NOW,
            updated_at=NOW,
        )
        bundle = KnowledgeBundle(
            id="knowledge-bundle:atomic:fail",
            items=(bad_item,),
            created_at=NOW,
        )

        with pytest.raises(KnowledgeStoreConflictError):
            store.save_bundle(bundle)

        # Ensure bundle itself was NOT saved
        assert not store.contains_bundle(bundle.id)


# ── Public API Compatibility Regression ───────────────────────────────────────


def test_public_api_backwards_compatibility() -> None:
    import cmm.cognitive as cog

    # Phase 8.1 - 8.4 exports check
    for export_name in [
        "CognitiveActor",
        "CognitiveActorKind",
        "CognitiveError",
        "CognitiveFinding",
        "CognitiveIdentifier",
        "CognitiveResult",
        "CognitiveSeverity",
        "CognitiveStatus",
        "Confidence",
        "Resource",
        "ResourceKind",
        "SensitivityLevel",
        "KnowledgeItem",
        "Evidence",
        "KnowledgeRelation",
        "TemporalScope",
        "Contradiction",
        "KnowledgeBundle",
        "KnowledgeKind",
        "KnowledgeStatus",
        "KnowledgeRelationKind",
        "TemporalValidityStatus",
    ]:
        assert hasattr(cog, export_name), f"Missing public export: {export_name}"

    # Phase 8.5 exports check
    for export_name in [
        "KNOWLEDGE_STORE_SCHEMA_VERSION",
        "InMemoryKnowledgeStore",
        "KnowledgeStoreConflictError",
        "KnowledgeStoreCorruptionError",
        "KnowledgeStoreError",
        "KnowledgeStoreNotFoundError",
        "KnowledgeStoreProtocol",
        "KnowledgeStoreSchemaError",
        "KnowledgeStoreSerializationError",
        "LocalKnowledgeStore",
        "SQLiteKnowledgeStore",
    ]:
        assert hasattr(cog, export_name), f"Missing Phase 8.5 export: {export_name}"
