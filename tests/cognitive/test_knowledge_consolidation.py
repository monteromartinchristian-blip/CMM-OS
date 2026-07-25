"""Phase 8.7 – Tests for Knowledge Consolidation.

Covers statement normalization, stable fingerprints, contract validation, candidate comparison,
plan building, preview, atomic execution, TOCTOU prevention, cycle detection, LINK idempotency,
non-lossy MERGE handling, conflict rollback, and cross-store parity.
"""

from __future__ import annotations

import tempfile
from collections.abc import Generator
from dataclasses import replace
from pathlib import Path

import pytest

from cmm.cognitive.consolidation import KnowledgeConsolidator
from cmm.cognitive.consolidation_contracts import (
    ConsolidationAction,
    ConsolidationCandidate,
    ConsolidationDecision,
    ConsolidationMatchKind,
    ConsolidationPlan,
    ConsolidationResult,
    knowledge_fingerprint,
    normalize_statement,
)
from cmm.cognitive.contracts import Confidence
from cmm.cognitive.enums import (
    KnowledgeKind,
    KnowledgeRelationKind,
    KnowledgeStatus,
)
from cmm.cognitive.errors import (
    InvalidConsolidationCandidateError,
    InvalidConsolidationPlanError,
    KnowledgeConsolidationConflictError,
)
from cmm.cognitive.knowledge import (
    Evidence,
    KnowledgeItem,
    KnowledgeRelation,
)
from cmm.cognitive.query import KnowledgeQuery
from cmm.cognitive.store_contracts import KnowledgeStoreProtocol
from cmm.cognitive.store_memory import InMemoryKnowledgeStore
from cmm.cognitive.store_sqlite import SQLiteKnowledgeStore

# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture(params=["memory", "sqlite"])
def store(
    request: pytest.FixtureRequest,
) -> Generator[KnowledgeStoreProtocol, None, None]:
    if request.param == "memory":
        yield InMemoryKnowledgeStore()
    else:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test_consolidation.db"
            st = SQLiteKnowledgeStore(db_path)
            try:
                yield st
            finally:
                st.close()


def _make_item(
    item_id: str,
    statement: str,
    kind: KnowledgeKind = KnowledgeKind.FACT,
    status: KnowledgeStatus = KnowledgeStatus.ACTIVE,
    confidence_val: float = 1.0,
    resource_id: str | None = None,
    actor_id: str | None = None,
    evidence: tuple[Evidence, ...] = (),
    relations: tuple[KnowledgeRelation, ...] = (),
    version: int = 1,
    supersedes_id: str | None = None,
    superseded_by_id: str | None = None,
    metadata: dict | None = None,
) -> KnowledgeItem:
    return KnowledgeItem(
        id=item_id,
        statement=statement,
        kind=kind,
        status=status,
        confidence=Confidence(value=confidence_val),
        resource_id=resource_id,
        actor_id=actor_id,
        evidence=evidence,
        relations=relations,
        version=version,
        supersedes_id=supersedes_id,
        superseded_by_id=superseded_by_id,
        metadata=metadata or {},
    )


# ── Normalization Tests ───────────────────────────────────────────────────────


def test_normalize_statement_basic() -> None:
    raw = "   Madrid   es España  "
    norm = normalize_statement(raw)
    assert norm == "madrid es españa"


def test_normalize_statement_unicode_nfkc() -> None:
    raw = "  Ｈｅｌｌｏ   Ｗｏｒｌｄ  "
    norm = normalize_statement(raw)
    assert norm == "hello world"


def test_normalize_statement_preserves_punctuation() -> None:
    raw = "  ¿Madrid, es la capital?  "
    norm = normalize_statement(raw)
    assert norm == "¿madrid, es la capital?"


def test_normalize_statement_invalid_type() -> None:
    with pytest.raises(TypeError):
        normalize_statement(123)  # type: ignore[arg-type]


# ── Fingerprint Tests ─────────────────────────────────────────────────────────


def test_knowledge_fingerprint_stability() -> None:
    item1 = _make_item("k-1", "  Earth revolves around the Sun  ", resource_id="res-1")
    item2 = _make_item("k-2", "earth revolves around the sun", resource_id="res-1")

    fp1 = knowledge_fingerprint(item1)
    fp2 = knowledge_fingerprint(item2)

    assert len(fp1) == 64
    assert fp1 == fp2


def test_knowledge_fingerprint_differing_fields() -> None:
    item1 = _make_item("k-1", "Earth revolves around the Sun", resource_id="res-1")
    item2 = _make_item("k-1", "Earth revolves around Mars", resource_id="res-1")
    item3 = _make_item("k-1", "Earth revolves around the Sun", resource_id="res-2")

    assert knowledge_fingerprint(item1) != knowledge_fingerprint(item2)
    assert knowledge_fingerprint(item1) != knowledge_fingerprint(item3)


# ── Candidate & Contract Tests ───────────────────────────────────────────────


def test_consolidation_candidate_validation() -> None:
    cand = ConsolidationCandidate(
        item_a_id="k-1",
        item_b_id="k-2",
        match_kind=ConsolidationMatchKind.EXACT_DUPLICATE,
        recommended_decision=ConsolidationDecision.MERGE,
        confidence=1.0,
        reasons=("Exact match",),
    )
    assert cand.item_a_id == "k-1"
    assert cand.item_b_id == "k-2"
    assert cand.confidence.value == 1.0
    assert cand.match_kind == ConsolidationMatchKind.EXACT_DUPLICATE


def test_consolidation_candidate_same_id_rejected() -> None:
    with pytest.raises(InvalidConsolidationCandidateError):
        ConsolidationCandidate(
            item_a_id="k-1",
            item_b_id="k-1",
            match_kind=ConsolidationMatchKind.EXACT_DUPLICATE,
            recommended_decision=ConsolidationDecision.MERGE,
            confidence=1.0,
        )


def test_consolidation_candidate_serialization_roundtrip() -> None:
    cand = ConsolidationCandidate(
        item_a_id="k-1",
        item_b_id="k-2",
        match_kind=ConsolidationMatchKind.EXACT_DUPLICATE,
        recommended_decision=ConsolidationDecision.MERGE,
        confidence=Confidence(value=0.95),
        matching_fields=("statement", "kind"),
        differing_fields=("confidence",),
        reasons=("High match",),
        metadata={"source": "auto"},
    )
    data = cand.serialize()
    restored = ConsolidationCandidate.from_mapping(data)
    assert restored == cand


# ── Compare Tests ─────────────────────────────────────────────────────────────


def test_compare_exact_duplicate(store: KnowledgeStoreProtocol) -> None:
    consolidator = KnowledgeConsolidator(store)
    item_a = _make_item("k-1", "Madrid is in Spain")
    item_b = _make_item("k-2", "Madrid is in Spain")

    candidate = consolidator.compare(item_a, item_b)

    assert candidate.match_kind == ConsolidationMatchKind.EXACT_DUPLICATE
    assert candidate.recommended_decision == ConsolidationDecision.MERGE
    assert candidate.confidence.value == 1.0


def test_compare_normalized_duplicate(store: KnowledgeStoreProtocol) -> None:
    consolidator = KnowledgeConsolidator(store)
    item_a = _make_item("k-1", "  Madrid is in Spain ", confidence_val=0.8)
    item_b = _make_item("k-2", "madrid IS in spain", confidence_val=1.0)

    candidate = consolidator.compare(item_a, item_b)

    assert candidate.match_kind == ConsolidationMatchKind.NORMALIZED_DUPLICATE
    assert candidate.confidence.value == 0.9


def test_compare_version_successor(store: KnowledgeStoreProtocol) -> None:
    consolidator = KnowledgeConsolidator(store)
    item_a = _make_item("k-1", "Original statement", version=1)
    item_b = _make_item("k-2", "Updated statement", version=2, supersedes_id="k-1")

    candidate = consolidator.compare(item_a, item_b)

    assert candidate.match_kind == ConsolidationMatchKind.VERSION_SUCCESSOR
    assert candidate.recommended_decision == ConsolidationDecision.SUPERSEDE
    assert candidate.item_a_id == "k-1"
    assert candidate.item_b_id == "k-2"


def test_compare_symmetry(store: KnowledgeStoreProtocol) -> None:
    consolidator = KnowledgeConsolidator(store)
    item_a = _make_item("k-10", "Madrid is in Spain")
    item_b = _make_item("k-02", "Madrid is in Spain")

    cand1 = consolidator.compare(item_a, item_b)
    cand2 = consolidator.compare(item_b, item_a)

    assert cand1 == cand2


# ── Find Candidates Tests ─────────────────────────────────────────────────────


def test_find_candidates_store(store: KnowledgeStoreProtocol) -> None:
    item_a = _make_item("k-1", "Spain capital is Madrid", resource_id="res-1")
    item_b = _make_item("k-2", "Spain capital is Madrid", resource_id="res-1")
    item_c = _make_item("k-3", "France capital is Paris", resource_id="res-2")

    store.save_item(item_a)
    store.save_item(item_b)
    store.save_item(item_c)

    consolidator = KnowledgeConsolidator(store)
    candidates = consolidator.find_candidates()

    assert len(candidates) == 1
    cand = candidates[0]
    assert {cand.item_a_id, cand.item_b_id} == {"k-1", "k-2"}


def test_find_candidates_query_filter(store: KnowledgeStoreProtocol) -> None:
    item_a = _make_item("k-1", "Fact A statement", resource_id="res-1")
    item_b = _make_item("k-2", "Fact A statement", resource_id="res-1")
    item_c = _make_item(
        "k-3",
        "Hypothesis C statement",
        kind=KnowledgeKind.HYPOTHESIS,
        resource_id="res-2",
    )

    store.save_item(item_a)
    store.save_item(item_b)
    store.save_item(item_c)

    consolidator = KnowledgeConsolidator(store)

    query = KnowledgeQuery(kinds=(KnowledgeKind.FACT,))
    candidates = consolidator.find_candidates(query=query)

    assert len(candidates) == 1
    assert candidates[0].item_a_id == "k-1"
    assert candidates[0].item_b_id == "k-2"


# ── Plan Construction & Preview Tests ──────────────────────────────────────────


def test_build_plan_valid(store: KnowledgeStoreProtocol) -> None:
    item_a = _make_item("k-1", "Same text")
    item_b = _make_item("k-2", "Same text")
    store.save_item(item_a)
    store.save_item(item_b)

    consolidator = KnowledgeConsolidator(store)
    candidates = consolidator.find_candidates()

    plan = consolidator.build_plan(candidates, actor_id="actor-1", dry_run=True)

    assert plan.actor_id == "actor-1"
    assert plan.dry_run is True
    assert len(plan.actions) == 1
    assert plan.actions[0].decision == ConsolidationDecision.MERGE
    assert "k-1" in plan.expected_fingerprints
    assert "k-2" in plan.expected_fingerprints


def test_build_plan_empty_candidates_raises(store: KnowledgeStoreProtocol) -> None:
    consolidator = KnowledgeConsolidator(store)
    with pytest.raises(InvalidConsolidationPlanError):
        consolidator.build_plan([], actor_id="actor-1")


def test_plan_serialization_roundtrip() -> None:
    action = ConsolidationAction(
        decision=ConsolidationDecision.MERGE,
        source_item_ids=("k-1", "k-2"),
        target_item_id="k-1",
        actor_id="actor-1",
    )
    plan = ConsolidationPlan(
        actions=(action,),
        actor_id="actor-1",
        dry_run=True,
        expected_fingerprints={"k-1": "fp1", "k-2": "fp2"},
    )

    serialized = plan.serialize()
    restored = ConsolidationPlan.from_mapping(serialized)
    assert restored == plan


# ── Defect 1: TOCTOU & Atomicity Tests ────────────────────────────────────────


def test_apply_plan_toctou_stale_fingerprint_rejection(
    store: KnowledgeStoreProtocol,
) -> None:
    item_a = _make_item("k-1", "Original statement A")
    item_b = _make_item("k-2", "Original statement A")
    store.save_item(item_a)
    store.save_item(item_b)

    consolidator = KnowledgeConsolidator(store)
    candidates = consolidator.find_candidates()
    plan = consolidator.build_plan(candidates, actor_id="actor-1", dry_run=False)

    # Mutate item_a in store right before apply_plan execution (simulating TOCTOU race)
    store.save_item(replace(item_a, statement="Altered statement A"))

    with pytest.raises(KnowledgeConsolidationConflictError, match="Stale fingerprint"):
        consolidator.apply_plan(plan)

    # Verify store remains unmutated
    assert store.get_item("k-1").statement == "Altered statement A"
    assert store.get_item("k-2").status == KnowledgeStatus.ACTIVE


def test_apply_plan_action_failure_reverts_all_actions(
    store: KnowledgeStoreProtocol,
) -> None:
    item_a = _make_item("k-1", "Statement 1")
    item_b = _make_item("k-2", "Statement 1")
    item_c = _make_item("k-3", "Statement 2")
    item_d = _make_item("k-4", "Statement 2")

    store.save_item(item_a)
    store.save_item(item_b)
    store.save_item(item_c)
    store.save_item(item_d)

    consolidator = KnowledgeConsolidator(store)

    # Action 1 is a valid MERGE of k-1 & k-2
    act1 = ConsolidationAction(
        decision=ConsolidationDecision.MERGE,
        source_item_ids=("k-1", "k-2"),
        target_item_id="k-1",
        actor_id="actor-1",
    )

    # Action 2 is an invalid SUPERSEDE attempting a circular supersession k-3 <-> k-4
    # (where k-3 already supersedes k-4)
    store.save_item(replace(item_c, supersedes_id="k-4"))
    act2 = ConsolidationAction(
        decision=ConsolidationDecision.SUPERSEDE,
        source_item_ids=("k-3",),
        target_item_id="k-4",
        actor_id="actor-1",
    )

    plan = ConsolidationPlan(
        actions=(act1, act2),
        actor_id="actor-1",
        dry_run=False,
        expected_fingerprints={
            "k-1": knowledge_fingerprint(item_a),
            "k-2": knowledge_fingerprint(item_b),
            "k-3": knowledge_fingerprint(store.get_item("k-3")),
            "k-4": knowledge_fingerprint(item_d),
        },
    )

    with pytest.raises(InvalidConsolidationPlanError, match="Circular supersession"):
        consolidator.apply_plan(plan)

    # Verify action 1 changes were completely rolled back in store
    assert store.get_item("k-1").status == KnowledgeStatus.ACTIVE
    assert store.get_item("k-2").status == KnowledgeStatus.ACTIVE


# ── Defect 2: Cycle Detection Tests ───────────────────────────────────────────


def test_supersession_cycle_detection_self_supersession(
    store: KnowledgeStoreProtocol,
) -> None:
    item_a = _make_item("k-1", "Text A")
    store.save_item(item_a)

    act = ConsolidationAction(
        decision=ConsolidationDecision.SUPERSEDE,
        source_item_ids=("k-1",),
        target_item_id="k-1",
        actor_id="actor-1",
    )
    with pytest.raises(InvalidConsolidationPlanError, match="by itself"):
        ConsolidationPlan(
            actions=(act,),
            actor_id="actor-1",
            dry_run=False,
            expected_fingerprints={"k-1": knowledge_fingerprint(item_a)},
        )


def test_supersession_cycle_detection_direct_and_long_cycle(
    store: KnowledgeStoreProtocol,
) -> None:
    # Set up chain: A -> B -> C
    item_a = _make_item(
        "k-A", "Text A", status=KnowledgeStatus.SUPERSEDED, superseded_by_id="k-B"
    )
    item_b = _make_item(
        "k-B",
        "Text B",
        supersedes_id="k-A",
        status=KnowledgeStatus.SUPERSEDED,
        superseded_by_id="k-C",
    )
    item_c = _make_item("k-C", "Text C", supersedes_id="k-B")

    store.save_item(item_a)
    store.save_item(item_b)
    store.save_item(item_c)

    consolidator = KnowledgeConsolidator(store)

    # Attempting C superseded_by A closes cycle A -> B -> C -> A
    act = ConsolidationAction(
        decision=ConsolidationDecision.SUPERSEDE,
        source_item_ids=("k-C",),
        target_item_id="k-A",
        actor_id="actor-1",
    )
    plan = ConsolidationPlan(
        actions=(act,),
        actor_id="actor-1",
        dry_run=False,
        expected_fingerprints={
            "k-A": knowledge_fingerprint(item_a),
            "k-C": knowledge_fingerprint(item_c),
        },
    )

    with pytest.raises(InvalidConsolidationPlanError, match="Circular supersession"):
        consolidator.apply_plan(plan)


def test_supersession_valid_chain_allowed(store: KnowledgeStoreProtocol) -> None:
    item_a = _make_item("k-A", "Text A")
    item_b = _make_item("k-B", "Text B")
    item_c = _make_item("k-C", "Text C")

    store.save_item(item_a)
    store.save_item(item_b)
    store.save_item(item_c)

    consolidator = KnowledgeConsolidator(store)

    # Step 1: A superseded_by B
    act1 = ConsolidationAction(
        decision=ConsolidationDecision.SUPERSEDE,
        source_item_ids=("k-A",),
        target_item_id="k-B",
        actor_id="actor-1",
    )
    plan1 = ConsolidationPlan(
        actions=(act1,),
        actor_id="actor-1",
        dry_run=False,
        expected_fingerprints={
            "k-A": knowledge_fingerprint(item_a),
            "k-B": knowledge_fingerprint(item_b),
        },
    )
    res1 = consolidator.apply_plan(plan1)
    assert res1.applied is True

    # Step 2: B superseded_by C
    act2 = ConsolidationAction(
        decision=ConsolidationDecision.SUPERSEDE,
        source_item_ids=("k-B",),
        target_item_id="k-C",
        actor_id="actor-1",
    )
    plan2 = ConsolidationPlan(
        actions=(act2,),
        actor_id="actor-1",
        dry_run=False,
        expected_fingerprints={
            "k-B": knowledge_fingerprint(store.get_item("k-B")),
            "k-C": knowledge_fingerprint(item_c),
        },
    )
    res2 = consolidator.apply_plan(plan2)
    assert res2.applied is True

    item_a_updated = store.get_item("k-A")
    item_b_updated = store.get_item("k-B")
    item_c_updated = store.get_item("k-C")

    assert item_a_updated.status == KnowledgeStatus.SUPERSEDED
    assert item_a_updated.superseded_by_id == "k-B"
    assert item_b_updated.status == KnowledgeStatus.SUPERSEDED
    assert item_b_updated.superseded_by_id == "k-C"
    assert item_b_updated.supersedes_id == "k-A"
    assert item_c_updated.supersedes_id == "k-B"


# ── Defect 3: LINK Idempotency Tests ──────────────────────────────────────────


def test_link_idempotency_and_deterministic_id(store: KnowledgeStoreProtocol) -> None:
    item_a = _make_item("k-1", "Text A")
    item_b = _make_item("k-2", "Text B")
    store.save_item(item_a)
    store.save_item(item_b)

    action = ConsolidationAction(
        decision=ConsolidationDecision.LINK,
        source_item_ids=("k-1", "k-2"),
        relation_kind=KnowledgeRelationKind.EQUIVALENT_TO,
        actor_id="actor-1",
    )
    plan = ConsolidationPlan(
        actions=(action,),
        actor_id="actor-1",
        dry_run=False,
        expected_fingerprints={
            "k-1": knowledge_fingerprint(item_a),
            "k-2": knowledge_fingerprint(item_b),
        },
    )

    consolidator = KnowledgeConsolidator(store)
    first = consolidator.apply_plan(plan)
    second = consolidator.apply_plan(plan)

    assert len(store.list_relations()) == 1
    assert first.linked_relation_ids == second.linked_relation_ids


def test_link_different_kind_creates_distinct_relation(
    store: KnowledgeStoreProtocol,
) -> None:
    item_a = _make_item("k-1", "Text A")
    item_b = _make_item("k-2", "Text B")
    store.save_item(item_a)
    store.save_item(item_b)

    consolidator = KnowledgeConsolidator(store)

    action1 = ConsolidationAction(
        decision=ConsolidationDecision.LINK,
        source_item_ids=("k-1", "k-2"),
        relation_kind=KnowledgeRelationKind.EQUIVALENT_TO,
        actor_id="actor-1",
    )
    plan1 = ConsolidationPlan(
        actions=(action1,),
        actor_id="actor-1",
        dry_run=False,
        expected_fingerprints={
            "k-1": knowledge_fingerprint(item_a),
            "k-2": knowledge_fingerprint(item_b),
        },
    )
    res1 = consolidator.apply_plan(plan1)

    action2 = ConsolidationAction(
        decision=ConsolidationDecision.LINK,
        source_item_ids=("k-1", "k-2"),
        relation_kind=KnowledgeRelationKind.SUPPORTS,
        actor_id="actor-1",
    )
    plan2 = ConsolidationPlan(
        actions=(action2,),
        actor_id="actor-1",
        dry_run=False,
        expected_fingerprints={
            "k-1": knowledge_fingerprint(item_a),
            "k-2": knowledge_fingerprint(item_b),
        },
    )
    res2 = consolidator.apply_plan(plan2)

    assert len(store.list_relations()) == 2
    assert res1.linked_relation_ids != res2.linked_relation_ids


# ── Defect 4: Non-Lossy MERGE Tests ──────────────────────────────────────────


def test_merge_preserves_source_metadata(store: KnowledgeStoreProtocol) -> None:
    item_a = _make_item("k-1", "Target statement", metadata={"target_key": "v1"})
    item_b = _make_item("k-2", "Target statement", metadata={"source_key": "v2"})
    store.save_item(item_a)
    store.save_item(item_b)

    consolidator = KnowledgeConsolidator(store)
    action = ConsolidationAction(
        decision=ConsolidationDecision.MERGE,
        source_item_ids=("k-1", "k-2"),
        target_item_id="k-1",
        actor_id="actor-1",
    )
    plan = ConsolidationPlan(
        actions=(action,),
        actor_id="actor-1",
        dry_run=False,
        expected_fingerprints={
            "k-1": knowledge_fingerprint(item_a),
            "k-2": knowledge_fingerprint(item_b),
        },
    )

    res = consolidator.apply_plan(plan)
    assert res.applied is True

    merged_a = store.get_item("k-1")
    assert merged_a.metadata["target_key"] == "v1"
    assert "consolidation" in merged_a.metadata
    consolidation_meta = merged_a.metadata["consolidation"]
    assert consolidation_meta["source_metadata"]["k-2"] == {"source_key": "v2"}

    # Source metadata in store remains unaltered
    source_b = store.get_item("k-2")
    assert source_b.metadata == {"source_key": "v2"}


def test_merge_evidence_deduplication_and_conflict(
    store: KnowledgeStoreProtocol,
) -> None:
    from cmm.cognitive.contracts import utc_now

    now = utc_now()
    ev_a = Evidence(
        id="ev-same",
        fragment="Same text",
        resource_id="res-1",
        confidence=Confidence(value=1.0),
        observed_at=now,
    )
    ev_a_dup = Evidence(
        id="ev-same",
        fragment="Same text",
        resource_id="res-1",
        confidence=Confidence(value=1.0),
        observed_at=now,
    )
    ev_a_diff = Evidence(
        id="ev-same",
        fragment="Differing text",
        resource_id="res-1",
        confidence=Confidence(value=1.0),
        observed_at=now,
    )

    item_a = _make_item("k-1", "Statement A", evidence=(ev_a,))
    item_b = _make_item("k-2", "Statement A", evidence=(ev_a_dup,))
    store.save_item(item_a)
    store.save_item(item_b)

    consolidator = KnowledgeConsolidator(store)

    # 1. Identical evidence with same ID deduplicates cleanly
    action_clean = ConsolidationAction(
        decision=ConsolidationDecision.MERGE,
        source_item_ids=("k-1", "k-2"),
        target_item_id="k-1",
        actor_id="actor-1",
    )
    plan_clean = ConsolidationPlan(
        actions=(action_clean,),
        actor_id="actor-1",
        dry_run=False,
        expected_fingerprints={
            "k-1": knowledge_fingerprint(item_a),
            "k-2": knowledge_fingerprint(item_b),
        },
    )
    res_clean = consolidator.apply_plan(plan_clean)
    assert res_clean.applied is True
    assert len(store.get_item("k-1").evidence) == 1

    # 2. Differing evidence with same ID raises KnowledgeConsolidationConflictError
    item_c = _make_item("k-3", "Statement C", evidence=(ev_a_diff,))
    store.save_item(item_c)
    action_conflict = ConsolidationAction(
        decision=ConsolidationDecision.MERGE,
        source_item_ids=("k-1", "k-3"),
        target_item_id="k-1",
        actor_id="actor-1",
    )
    plan_conflict = ConsolidationPlan(
        actions=(action_conflict,),
        actor_id="actor-1",
        dry_run=False,
        expected_fingerprints={
            "k-1": knowledge_fingerprint(store.get_item("k-1")),
            "k-3": knowledge_fingerprint(item_c),
        },
    )

    with pytest.raises(KnowledgeConsolidationConflictError, match="Evidence conflict"):
        consolidator.apply_plan(plan_conflict)


def test_merge_relation_deduplication_and_conflict(
    store: KnowledgeStoreProtocol,
) -> None:
    from cmm.cognitive.contracts import utc_now

    now = utc_now()
    rel_a = KnowledgeRelation(
        id="rel-same",
        source_id="k-1",
        target_id="k-99",
        kind=KnowledgeRelationKind.SUPPORTS,
        confidence=Confidence(value=1.0),
        created_at=now,
    )
    rel_a_dup = KnowledgeRelation(
        id="rel-same",
        source_id="k-1",
        target_id="k-99",
        kind=KnowledgeRelationKind.SUPPORTS,
        confidence=Confidence(value=1.0),
        created_at=now,
    )
    rel_a_diff = KnowledgeRelation(
        id="rel-same",
        source_id="k-1",
        target_id="k-99",
        kind=KnowledgeRelationKind.CONTRADICTS,
        confidence=Confidence(value=1.0),
        created_at=now,
    )

    item_a = _make_item("k-1", "Statement A", relations=(rel_a,))
    item_b = _make_item("k-2", "Statement A", relations=(rel_a_dup,))
    store.save_item(item_a)
    store.save_item(item_b)

    consolidator = KnowledgeConsolidator(store)

    action_clean = ConsolidationAction(
        decision=ConsolidationDecision.MERGE,
        source_item_ids=("k-1", "k-2"),
        target_item_id="k-1",
        actor_id="actor-1",
    )
    plan_clean = ConsolidationPlan(
        actions=(action_clean,),
        actor_id="actor-1",
        dry_run=False,
        expected_fingerprints={
            "k-1": knowledge_fingerprint(item_a),
            "k-2": knowledge_fingerprint(item_b),
        },
    )
    res_clean = consolidator.apply_plan(plan_clean)
    assert res_clean.applied is True
    assert len(store.get_item("k-1").relations) == 1

    item_c = _make_item("k-3", "Statement C", relations=(rel_a_diff,))
    store.save_item(item_c)
    action_conflict = ConsolidationAction(
        decision=ConsolidationDecision.MERGE,
        source_item_ids=("k-1", "k-3"),
        target_item_id="k-1",
        actor_id="actor-1",
    )
    plan_conflict = ConsolidationPlan(
        actions=(action_conflict,),
        actor_id="actor-1",
        dry_run=False,
        expected_fingerprints={
            "k-1": knowledge_fingerprint(store.get_item("k-1")),
            "k-3": knowledge_fingerprint(item_c),
        },
    )

    with pytest.raises(
        KnowledgeConsolidationConflictError, match="KnowledgeRelation conflict"
    ):
        consolidator.apply_plan(plan_conflict)


def test_result_serialization_roundtrip() -> None:
    res = ConsolidationResult(
        plan_id="plan-1",
        applied=True,
        updated_item_ids=("k-1",),
        superseded_item_ids=("k-2",),
    )
    serialized = res.serialize()
    restored = ConsolidationResult.from_mapping(serialized)
    assert restored == res
