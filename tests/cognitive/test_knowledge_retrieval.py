"""Tests for Phase 8.6 Knowledge Retrieval."""

from __future__ import annotations

from collections.abc import Generator
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from cmm import cognitive
from cmm.cognitive import (
    Confidence,
    Contradiction,
    ContradictionSeverity,
    ContradictionStatus,
    Evidence,
    InMemoryKnowledgeStore,
    InvalidKnowledgeQueryError,
    KnowledgeBundle,
    KnowledgeItem,
    KnowledgeKind,
    KnowledgeOrderField,
    KnowledgeQuery,
    KnowledgeQueryResult,
    KnowledgeRelation,
    KnowledgeRelationKind,
    KnowledgeRetriever,
    KnowledgeStatus,
    KnowledgeStoreNotFoundError,
    KnowledgeStoreProtocol,
    SensitivityLevel,
    SortDirection,
    SQLiteKnowledgeStore,
    TemporalScope,
    TemporalScopeKind,
)

NOW = datetime.now(timezone.utc)
ONE_HOUR = timedelta(hours=1)


@pytest.fixture(params=["in_memory", "sqlite"])
def store(
    request: pytest.FixtureRequest,
) -> Generator[KnowledgeStoreProtocol, None, None]:
    if request.param == "in_memory":
        yield InMemoryKnowledgeStore()
    else:
        with TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "retrieval_test.db"
            yield SQLiteKnowledgeStore(db_path)


# ── 1. KnowledgeQuery Tests ───────────────────────────────────────────────────


def test_knowledge_query_defaults() -> None:
    query = KnowledgeQuery()
    assert query.kinds == ()
    assert query.statuses == ()
    assert query.limit is None
    assert query.offset == 0
    assert query.order_by is KnowledgeOrderField.CREATED_AT
    assert query.order_direction is SortDirection.DESC
    assert query.include_expired is True
    assert query.include_superseded is True
    assert query.include_invalidated is True


def test_knowledge_query_converts_sequences_and_enums() -> None:
    query = KnowledgeQuery(
        kinds=["fact", "hypothesis"],
        statuses=["active"],
        resource_ids=["res-1"],
        actor_ids=["actor-1"],
        sensitivities=["internal"],
        relation_kinds=["supports"],
        order_by="updated_at",
        order_direction="asc",
    )
    assert query.kinds == (KnowledgeKind.FACT, KnowledgeKind.HYPOTHESIS)
    assert query.statuses == (KnowledgeStatus.ACTIVE,)
    assert query.resource_ids == ("res-1",)
    assert query.actor_ids == ("actor-1",)
    assert query.sensitivities == (SensitivityLevel.INTERNAL,)
    assert query.relation_kinds == (KnowledgeRelationKind.SUPPORTS,)
    assert query.order_by is KnowledgeOrderField.UPDATED_AT
    assert query.order_direction is SortDirection.ASC


def test_knowledge_query_validation_errors() -> None:
    with pytest.raises(InvalidKnowledgeQueryError, match="limit"):
        KnowledgeQuery(limit=-1)

    with pytest.raises(InvalidKnowledgeQueryError, match="offset"):
        KnowledgeQuery(offset=-5)

    with pytest.raises(InvalidKnowledgeQueryError, match="created_until"):
        KnowledgeQuery(
            created_from=NOW,
            created_until=NOW - ONE_HOUR,
        )

    with pytest.raises(InvalidKnowledgeQueryError, match="updated_until"):
        KnowledgeQuery(
            updated_from=NOW,
            updated_until=NOW - ONE_HOUR,
        )

    naive_dt = datetime.now(timezone.utc).replace(tzinfo=None)
    with pytest.raises(InvalidKnowledgeQueryError, match="timezone-aware"):
        KnowledgeQuery(created_from=naive_dt)

    with pytest.raises(InvalidKnowledgeQueryError, match="empty or whitespace"):
        KnowledgeQuery(text_contains="   ")

    with pytest.raises(InvalidKnowledgeQueryError, match="resource_ids"):
        KnowledgeQuery(resource_ids=["  "])

    with pytest.raises(InvalidKnowledgeQueryError, match="Invalid KnowledgeKind"):
        KnowledgeQuery(kinds=["non_existent_kind"])


def test_knowledge_query_serialization_roundtrip() -> None:
    query = KnowledgeQuery(
        kinds=[KnowledgeKind.FACT],
        statuses=[KnowledgeStatus.ACTIVE],
        resource_ids=["res-1"],
        actor_ids=["actor-1"],
        created_from=NOW,
        text_contains="search phrase",
        limit=10,
        offset=5,
        order_by=KnowledgeOrderField.CONFIDENCE,
        order_direction=SortDirection.ASC,
        metadata={"tag": "test"},
    )
    serialized = query.serialize()
    assert serialized["kinds"] == ["fact"]
    assert serialized["limit"] == 10
    assert serialized["offset"] == 5
    assert serialized["order_by"] == "confidence"

    reconstructed = KnowledgeQuery.from_mapping(serialized)
    assert reconstructed == query
    assert reconstructed.to_dict() == serialized
    assert KnowledgeQuery.from_dict(serialized) == query


def test_knowledge_query_defensive_copies() -> None:
    meta = {"a": 1}
    kinds_list = [KnowledgeKind.FACT]
    query = KnowledgeQuery(kinds=kinds_list, metadata=meta)

    kinds_list.append(KnowledgeKind.HYPOTHESIS)
    assert query.kinds == (KnowledgeKind.FACT,)

    with pytest.raises(TypeError):
        query.metadata["b"] = 2  # type: ignore[index]


# ── 2. KnowledgeQueryResult Tests ─────────────────────────────────────────────


def test_query_result_serialization_roundtrip() -> None:
    item = KnowledgeItem(
        id="knowledge-item:knowledge:1",
        statement="Earth revolves around the Sun",
        kind=KnowledgeKind.FACT,
        confidence=Confidence(0.99),
        created_at=NOW,
        updated_at=NOW,
    )
    query = KnowledgeQuery(limit=5)
    result = KnowledgeQueryResult(
        query=query,
        items=(item,),
        total_count=1,
        returned_count=1,
        offset=0,
        limit=5,
        has_more=False,
        applied_filters=("limit",),
    )
    serialized = result.serialize()
    reconstructed = KnowledgeQueryResult.from_mapping(serialized)
    assert reconstructed.query == query
    assert reconstructed.items == (item,)
    assert reconstructed.total_count == 1
    assert reconstructed.has_more is False
    assert reconstructed.to_dict() == serialized


# ── 3. Basic Querying & Pagination ────────────────────────────────────────────


def test_query_empty_store(store: KnowledgeStoreProtocol) -> None:
    retriever = KnowledgeRetriever(store)
    res = retriever.query(KnowledgeQuery())
    assert res.items == ()
    assert res.total_count == 0
    assert res.returned_count == 0
    assert res.has_more is False


def test_query_pagination(store: KnowledgeStoreProtocol) -> None:
    for i in range(10):
        store.save_item(
            KnowledgeItem(
                id=f"knowledge-item:knowledge:{i:02d}",
                statement=f"Statement {i}",
                kind=KnowledgeKind.FACT,
                confidence=Confidence(0.8),
                created_at=NOW + timedelta(seconds=i),
                updated_at=NOW + timedelta(seconds=i),
            )
        )

    retriever = KnowledgeRetriever(store)

    # Page 1: limit 4, offset 0, order CREATED_AT DESC
    res1 = retriever.query(
        KnowledgeQuery(
            limit=4,
            offset=0,
            order_by=KnowledgeOrderField.CREATED_AT,
            order_direction=SortDirection.DESC,
        )
    )
    assert res1.total_count == 10
    assert res1.returned_count == 4
    assert res1.has_more is True
    assert [it.id for it in res1.items] == [
        "knowledge-item:knowledge:09",
        "knowledge-item:knowledge:08",
        "knowledge-item:knowledge:07",
        "knowledge-item:knowledge:06",
    ]

    # Page 2: limit 4, offset 4
    res2 = retriever.query(
        KnowledgeQuery(
            limit=4,
            offset=4,
            order_by=KnowledgeOrderField.CREATED_AT,
            order_direction=SortDirection.DESC,
        )
    )
    assert res2.returned_count == 4
    assert res2.has_more is True
    assert [it.id for it in res2.items] == [
        "knowledge-item:knowledge:05",
        "knowledge-item:knowledge:04",
        "knowledge-item:knowledge:03",
        "knowledge-item:knowledge:02",
    ]

    # Page 3: limit 4, offset 8
    res3 = retriever.query(
        KnowledgeQuery(
            limit=4,
            offset=8,
            order_by=KnowledgeOrderField.CREATED_AT,
            order_direction=SortDirection.DESC,
        )
    )
    assert res3.returned_count == 2
    assert res3.has_more is False
    assert [it.id for it in res3.items] == [
        "knowledge-item:knowledge:01",
        "knowledge-item:knowledge:00",
    ]


# ── 4. Filtering Tests ────────────────────────────────────────────────────────


def test_query_filter_kinds_and_statuses(store: KnowledgeStoreProtocol) -> None:
    store.save_item(
        KnowledgeItem(
            id="item-1",
            statement="Fact 1",
            kind=KnowledgeKind.FACT,
            status=KnowledgeStatus.ACTIVE,
            confidence=Confidence(0.9),
        )
    )
    store.save_item(
        KnowledgeItem(
            id="item-2",
            statement="Hypothesis 1",
            kind=KnowledgeKind.HYPOTHESIS,
            status=KnowledgeStatus.UNVERIFIED,
            confidence=Confidence(0.5),
        )
    )
    store.save_item(
        KnowledgeItem(
            id="item-3",
            statement="Observation 1",
            kind=KnowledgeKind.OBSERVATION,
            status=KnowledgeStatus.DISPUTED,
            confidence=Confidence(0.7),
        )
    )

    retriever = KnowledgeRetriever(store)

    # Multi-kind (OR)
    res_kinds = retriever.query(
        KnowledgeQuery(kinds=[KnowledgeKind.FACT, KnowledgeKind.HYPOTHESIS])
    )
    assert res_kinds.total_count == 2
    assert {it.id for it in res_kinds.items} == {"item-1", "item-2"}

    # Status filter
    res_status = retriever.query(KnowledgeQuery(statuses=[KnowledgeStatus.DISPUTED]))
    assert res_status.total_count == 1
    assert res_status.items[0].id == "item-3"


def test_query_filter_resource_actor_sensitivity(
    store: KnowledgeStoreProtocol,
) -> None:
    store.save_item(
        KnowledgeItem(
            id="item-1",
            statement="Statement 1",
            kind=KnowledgeKind.FACT,
            confidence=Confidence(0.9),
            resource_id="res-A",
            actor_id="actor-X",
            sensitivity=SensitivityLevel.PUBLIC,
        )
    )
    store.save_item(
        KnowledgeItem(
            id="item-2",
            statement="Statement 2",
            kind=KnowledgeKind.FACT,
            confidence=Confidence(0.9),
            resource_id="res-B",
            actor_id="actor-Y",
            sensitivity=SensitivityLevel.RESTRICTED,
        )
    )

    retriever = KnowledgeRetriever(store)

    res_res = retriever.query(KnowledgeQuery(resource_ids=["res-A"]))
    assert res_res.total_count == 1 and res_res.items[0].id == "item-1"

    res_actor = retriever.query(KnowledgeQuery(actor_ids=["actor-Y"]))
    assert res_actor.total_count == 1 and res_actor.items[0].id == "item-2"

    res_sens = retriever.query(
        KnowledgeQuery(sensitivities=[SensitivityLevel.RESTRICTED])
    )
    assert res_sens.total_count == 1 and res_sens.items[0].id == "item-2"


def test_query_filter_time_ranges(store: KnowledgeStoreProtocol) -> None:
    t1 = NOW - timedelta(days=5)
    t2 = NOW - timedelta(days=2)
    t3 = NOW

    store.save_item(
        KnowledgeItem(
            id="item-1",
            statement="S1",
            kind=KnowledgeKind.FACT,
            confidence=Confidence(0.9),
            created_at=t1,
            updated_at=t1,
        )
    )
    store.save_item(
        KnowledgeItem(
            id="item-2",
            statement="S2",
            kind=KnowledgeKind.FACT,
            confidence=Confidence(0.9),
            created_at=t2,
            updated_at=t2,
        )
    )
    store.save_item(
        KnowledgeItem(
            id="item-3",
            statement="S3",
            kind=KnowledgeKind.FACT,
            confidence=Confidence(0.9),
            created_at=t3,
            updated_at=t3,
        )
    )

    retriever = KnowledgeRetriever(store)

    res_created = retriever.query(
        KnowledgeQuery(
            created_from=t1 + timedelta(days=1),
            created_until=t2 + timedelta(days=1),
        )
    )
    assert res_created.total_count == 1
    assert res_created.items[0].id == "item-2"


def test_query_filter_text_contains(store: KnowledgeStoreProtocol) -> None:
    store.save_item(
        KnowledgeItem(
            id="item-1",
            statement="El paciente presenta fiebre alta y tos",
            kind=KnowledgeKind.OBSERVATION,
            confidence=Confidence(0.9),
        )
    )
    store.save_item(
        KnowledgeItem(
            id="item-2",
            statement="Diagnóstico de neumonía atípica",
            kind=KnowledgeKind.INFERENCE,
            confidence=Confidence(0.8),
        )
    )

    retriever = KnowledgeRetriever(store)

    res = retriever.query(KnowledgeQuery(text_contains="FIEBRE"))
    assert res.total_count == 1
    assert res.items[0].id == "item-1"


def test_query_filter_valid_at_and_status_flags(
    store: KnowledgeStoreProtocol,
) -> None:
    valid_from = NOW - timedelta(days=10)
    valid_until = NOW - timedelta(days=2)

    # Expired scope
    scope_expired = TemporalScope(
        kind=TemporalScopeKind.INTERVAL,
        valid_from=valid_from,
        valid_until=valid_until,
    )
    item_expired = store.save_item(
        KnowledgeItem(
            id="item-expired",
            statement="Expired facts",
            kind=KnowledgeKind.FACT,
            confidence=Confidence(0.9),
            temporal_scope=scope_expired,
        )
    )

    # Superseded item
    item_sup = store.save_item(
        KnowledgeItem(
            id="item-superseded",
            statement="Old version",
            kind=KnowledgeKind.FACT,
            confidence=Confidence(0.9),
            status=KnowledgeStatus.SUPERSEDED,
            superseded_by_id="item-new",
        )
    )

    # Invalidated item
    item_inv = store.save_item(
        KnowledgeItem(
            id="item-invalidated",
            statement="Wrong statement",
            kind=KnowledgeKind.FACT,
            confidence=Confidence(0.9),
            status=KnowledgeStatus.INVALIDATED,
            invalidated_at=NOW,
            invalidation_reason="debunked",
        )
    )

    retriever = KnowledgeRetriever(store)

    # Exclude expired
    res_no_exp = retriever.query(KnowledgeQuery(include_expired=False))
    assert item_expired.id not in {it.id for it in res_no_exp.items}

    # Exclude superseded
    res_no_sup = retriever.query(KnowledgeQuery(include_superseded=False))
    assert item_sup.id not in {it.id for it in res_no_sup.items}

    # Exclude invalidated
    res_no_inv = retriever.query(KnowledgeQuery(include_invalidated=False))
    assert item_inv.id not in {it.id for it in res_no_inv.items}

    # valid_at check at NOW
    res_valid_at = retriever.query(KnowledgeQuery(valid_at=NOW))
    assert item_expired.id not in {it.id for it in res_valid_at.items}

    # valid_at check at valid_from + 1 day
    res_valid_past = retriever.query(
        KnowledgeQuery(valid_at=valid_from + timedelta(days=1))
    )
    assert item_expired.id in {it.id for it in res_valid_past.items}


def test_query_filter_evidence_and_relations(store: KnowledgeStoreProtocol) -> None:
    ev = Evidence(
        id="ev-1",
        resource_id="res-1",
        fragment="Text quote",
        confidence=Confidence(0.9),
    )
    rel = KnowledgeRelation(
        id="rel-1",
        source_id="item-with-rel",
        target_id="item-target",
        kind=KnowledgeRelationKind.SUPPORTS,
        confidence=Confidence(0.9),
    )

    store.save_item(
        KnowledgeItem(
            id="item-with-ev",
            statement="Item with evidence",
            kind=KnowledgeKind.FACT,
            confidence=Confidence(0.9),
            evidence=(ev,),
        )
    )
    store.save_item(
        KnowledgeItem(
            id="item-with-rel",
            statement="Item with relation",
            kind=KnowledgeKind.FACT,
            confidence=Confidence(0.9),
            relations=(rel,),
        )
    )
    store.save_item(
        KnowledgeItem(
            id="item-plain",
            statement="Plain item",
            kind=KnowledgeKind.FACT,
            confidence=Confidence(0.9),
        )
    )

    retriever = KnowledgeRetriever(store)

    res_has_ev = retriever.query(KnowledgeQuery(has_evidence=True))
    assert {it.id for it in res_has_ev.items} == {"item-with-ev"}

    res_no_ev = retriever.query(KnowledgeQuery(has_evidence=False))
    assert {it.id for it in res_no_ev.items} == {"item-with-rel", "item-plain"}

    res_rel_kind = retriever.query(
        KnowledgeQuery(relation_kinds=[KnowledgeRelationKind.SUPPORTS])
    )
    assert {it.id for it in res_rel_kind.items} == {"item-with-rel"}


def test_query_filter_composition(store: KnowledgeStoreProtocol) -> None:
    # 5+ filters combined
    store.save_item(
        KnowledgeItem(
            id="target-item",
            statement="Specific search target statement",
            kind=KnowledgeKind.FACT,
            status=KnowledgeStatus.ACTIVE,
            confidence=Confidence(0.95),
            resource_id="res-100",
            actor_id="actor-5",
            sensitivity=SensitivityLevel.INTERNAL,
            created_at=NOW,
        )
    )
    store.save_item(
        KnowledgeItem(
            id="other-item",
            statement="Other statement",
            kind=KnowledgeKind.FACT,
            status=KnowledgeStatus.ACTIVE,
            confidence=Confidence(0.80),
            resource_id="res-100",
            actor_id="actor-5",
            sensitivity=SensitivityLevel.PUBLIC,
            created_at=NOW,
        )
    )

    retriever = KnowledgeRetriever(store)

    q = KnowledgeQuery(
        kinds=[KnowledgeKind.FACT],
        statuses=[KnowledgeStatus.ACTIVE],
        resource_ids=["res-100"],
        actor_ids=["actor-5"],
        sensitivities=[SensitivityLevel.INTERNAL],
        text_contains="target",
    )
    res = retriever.query(q)
    assert res.total_count == 1
    assert res.items[0].id == "target-item"


# ── 5. Ordering Tests ─────────────────────────────────────────────────────────


def test_query_ordering(store: KnowledgeStoreProtocol) -> None:
    t1 = NOW + timedelta(seconds=1)
    t2 = NOW + timedelta(seconds=2)
    t3 = NOW + timedelta(seconds=3)
    store.save_item(
        KnowledgeItem(
            id="item-c",
            statement="C",
            kind=KnowledgeKind.FACT,
            confidence=Confidence(0.7),
            created_at=t1,
            updated_at=t1,
        )
    )
    store.save_item(
        KnowledgeItem(
            id="item-a",
            statement="A",
            kind=KnowledgeKind.FACT,
            confidence=Confidence(0.9),
            created_at=t2,
            updated_at=t2,
        )
    )
    store.save_item(
        KnowledgeItem(
            id="item-b",
            statement="B",
            kind=KnowledgeKind.FACT,
            confidence=Confidence(0.9),
            created_at=t3,
            updated_at=t3,
        )
    )

    retriever = KnowledgeRetriever(store)

    # Order by CONFIDENCE DESC, tie-breaker ID ASC
    # Confidence: item-a (0.9), item-b (0.9), item-c (0.7)
    # Tie-breaker between item-a and item-b: "item-a" < "item-b" -> item-a, item-b, item-c
    res_conf = retriever.query(
        KnowledgeQuery(
            order_by=KnowledgeOrderField.CONFIDENCE,
            order_direction=SortDirection.DESC,
        )
    )
    assert [it.id for it in res_conf.items] == ["item-a", "item-b", "item-c"]

    # Order by CREATED_AT ASC
    res_created = retriever.query(
        KnowledgeQuery(
            order_by=KnowledgeOrderField.CREATED_AT,
            order_direction=SortDirection.ASC,
        )
    )
    assert [it.id for it in res_created.items] == ["item-c", "item-a", "item-b"]


# ── 6. Relations, Contradictions, Bundles Auxiliary Methods ───────────────────


def test_relations_for_item(store: KnowledgeStoreProtocol) -> None:
    rel1 = KnowledgeRelation(
        id="rel-1",
        source_id="item-A",
        target_id="item-B",
        kind=KnowledgeRelationKind.SUPPORTS,
        confidence=Confidence(0.9),
        created_at=NOW,
    )
    rel2 = KnowledgeRelation(
        id="rel-2",
        source_id="item-C",
        target_id="item-A",
        kind=KnowledgeRelationKind.CONTRADICTS,
        confidence=Confidence(0.8),
        created_at=NOW + timedelta(seconds=1),
    )
    store.save_relation(rel1)
    store.save_relation(rel2)

    retriever = KnowledgeRetriever(store)

    # All relations for item-A (both source and target)
    rels = retriever.relations_for_item("item-A")
    assert len(rels) == 2
    assert [r.id for r in rels] == ["rel-1", "rel-2"]

    # Filtered by kind SUPPORTS
    rels_sup = retriever.relations_for_item(
        "item-A", kinds=[KnowledgeRelationKind.SUPPORTS]
    )
    assert len(rels_sup) == 1
    assert rels_sup[0].id == "rel-1"

    # Item with no relations
    assert retriever.relations_for_item("item-non-existent") == ()


def test_contradictions_for_item(store: KnowledgeStoreProtocol) -> None:
    c1 = Contradiction(
        id="contra-1",
        item_a_id="item-X",
        item_b_id="item-Y",
        severity=ContradictionSeverity.HIGH,
        status=ContradictionStatus.UNRESOLVED,
        created_at=NOW,
    )
    c2 = Contradiction(
        id="contra-2",
        item_a_id="item-Z",
        item_b_id="item-X",
        severity=ContradictionSeverity.LOW,
        status=ContradictionStatus.RESOLVED,
        created_at=NOW + timedelta(seconds=1),
    )
    store.save_contradiction(c1)
    store.save_contradiction(c2)

    retriever = KnowledgeRetriever(store)

    # All contradictions for item-X
    contras = retriever.contradictions_for_item("item-X")
    assert len(contras) == 2
    assert [c.id for c in contras] == ["contra-1", "contra-2"]

    # Filtered by status UNRESOLVED
    contras_unres = retriever.contradictions_for_item(
        "item-X", statuses=[ContradictionStatus.UNRESOLVED]
    )
    assert len(contras_unres) == 1
    assert contras_unres[0].id == "contra-1"


def test_bundles_for_item(store: KnowledgeStoreProtocol) -> None:
    it1 = KnowledgeItem(
        id="item-1",
        statement="S1",
        kind=KnowledgeKind.FACT,
        confidence=Confidence(0.9),
    )
    it2 = KnowledgeItem(
        id="item-2",
        statement="S2",
        kind=KnowledgeKind.FACT,
        confidence=Confidence(0.9),
    )
    it3 = KnowledgeItem(
        id="item-3",
        statement="S3",
        kind=KnowledgeKind.FACT,
        confidence=Confidence(0.9),
    )

    b1 = KnowledgeBundle(
        id="bundle-1",
        items=(it1, it2),
        created_at=NOW,
    )
    b2 = KnowledgeBundle(
        id="bundle-2",
        items=(it2, it3),
        created_at=NOW + timedelta(seconds=1),
    )
    store.save_bundle(b1)
    store.save_bundle(b2)

    retriever = KnowledgeRetriever(store)

    bundles_2 = retriever.bundles_for_item("item-2")
    assert len(bundles_2) == 2
    assert [b.id for b in bundles_2] == ["bundle-1", "bundle-2"]

    bundles_3 = retriever.bundles_for_item("item-3")
    assert len(bundles_3) == 1
    assert bundles_3[0].id == "bundle-2"

    assert retriever.bundles_for_item("item-absent") == ()


# ── 7. Batch API Tests ────────────────────────────────────────────────────────


def test_get_items_batch(store: KnowledgeStoreProtocol) -> None:
    store.save_item(
        KnowledgeItem(
            id="item-1",
            statement="S1",
            kind=KnowledgeKind.FACT,
            confidence=Confidence(0.9),
        )
    )
    store.save_item(
        KnowledgeItem(
            id="item-2",
            statement="S2",
            kind=KnowledgeKind.FACT,
            confidence=Confidence(0.9),
        )
    )

    retriever = KnowledgeRetriever(store)

    # Order preserved, duplicates collapsed
    items = retriever.get_items(["item-2", "item-1", "item-2"])
    assert len(items) == 2
    assert [it.id for it in items] == ["item-2", "item-1"]

    # Missing item with ignore_missing=False
    with pytest.raises(KnowledgeStoreNotFoundError, match="item-missing"):
        retriever.get_items(["item-1", "item-missing"], ignore_missing=False)

    # Missing item with ignore_missing=True
    items_ignored = retriever.get_items(["item-1", "item-missing"], ignore_missing=True)
    assert len(items_ignored) == 1
    assert items_ignored[0].id == "item-1"


# ── 8. Exports Regression Test ────────────────────────────────────────────────


def test_public_api_exports_regression() -> None:
    expected_exports = [
        "KnowledgeQuery",
        "KnowledgeQueryResult",
        "KnowledgeRetriever",
        "KnowledgeOrderField",
        "SortDirection",
        "KnowledgeRetrievalError",
        "InvalidKnowledgeQueryError",
        "UnsupportedKnowledgeQueryError",
        "KnowledgeItem",
        "KnowledgeKind",
        "KnowledgeStatus",
        "InMemoryKnowledgeStore",
        "SQLiteKnowledgeStore",
        "KnowledgeStoreProtocol",
    ]

    for export_name in expected_exports:
        assert hasattr(cognitive, export_name), f"Missing export: {export_name}"
        assert export_name in cognitive.__all__, f"Missing from __all__: {export_name}"
