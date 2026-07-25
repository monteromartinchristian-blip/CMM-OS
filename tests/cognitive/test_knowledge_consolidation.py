"""Phase 8.7 – Tests for Knowledge Consolidation.

Covers statement normalization, stable fingerprints, contract validation, candidate comparison,
plan building, preview, atomic execution, conflict handling, and cross-store parity.
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
    ManualReviewRequiredError,
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
    )


# ── Normalization Tests ───────────────────────────────────────────────────────


def test_normalize_statement_basic() -> None:
    raw = "   Madrid   es España  "
    norm = normalize_statement(raw)
    assert norm == "madrid es españa"


def test_normalize_statement_unicode_nfkc() -> None:
    # Full-width characters and accents
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


# ── Atomic Apply & Merge / Supersede / Link Tests ──────────────────────────────


def test_apply_plan_dry_run_does_not_modify(store: KnowledgeStoreProtocol) -> None:
    item_a = _make_item("k-1", "Duplicates")
    item_b = _make_item("k-2", "Duplicates")
    store.save_item(item_a)
    store.save_item(item_b)

    consolidator = KnowledgeConsolidator(store)
    candidates = consolidator.find_candidates()
    plan = consolidator.build_plan(candidates, actor_id="actor-1", dry_run=True)

    res = consolidator.apply_plan(plan)

    assert res.applied is False
    assert store.get_item("k-1").status == KnowledgeStatus.ACTIVE
    assert store.get_item("k-2").status == KnowledgeStatus.ACTIVE


def test_apply_plan_merge(store: KnowledgeStoreProtocol) -> None:
    ev_a = Evidence(
        id="ev-1",
        fragment="Quote A",
        resource_id="res-1",
        confidence=Confidence(value=1.0),
    )
    ev_b = Evidence(
        id="ev-2",
        fragment="Quote B",
        resource_id="res-1",
        confidence=Confidence(value=1.0),
    )
    item_a = _make_item("k-1", "Target statement", confidence_val=0.9, evidence=(ev_a,))
    item_b = _make_item("k-2", "Target statement", confidence_val=0.8, evidence=(ev_b,))
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
    assert "k-1" in res.updated_item_ids
    assert "k-2" in res.superseded_item_ids

    updated_a = store.get_item("k-1")
    superseded_b = store.get_item("k-2")

    assert len(updated_a.evidence) == 2
    assert updated_a.confidence.value == 0.8  # Conservative lower bound
    assert superseded_b.status == KnowledgeStatus.SUPERSEDED
    assert superseded_b.superseded_by_id == "k-1"


def test_apply_plan_supersede(store: KnowledgeStoreProtocol) -> None:
    item_a = _make_item("k-1", "V1 text", version=1)
    item_b = _make_item("k-2", "V2 text", version=2, supersedes_id="k-1")
    store.save_item(item_a)
    store.save_item(item_b)

    consolidator = KnowledgeConsolidator(store)
    candidates = consolidator.find_candidates()
    plan = consolidator.build_plan(candidates, actor_id="actor-1", dry_run=False)

    res = consolidator.apply_plan(plan)

    assert res.applied is True
    assert "k-1" in res.superseded_item_ids
    assert store.get_item("k-1").status == KnowledgeStatus.SUPERSEDED
    assert store.get_item("k-1").superseded_by_id == "k-2"


def test_apply_plan_link(store: KnowledgeStoreProtocol) -> None:
    item_a = _make_item("k-1", "Text A", actor_id="actor-1")
    item_b = _make_item("k-2", "Text B", actor_id="actor-1")
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
    res = consolidator.apply_plan(plan)

    assert res.applied is True
    assert len(res.linked_relation_ids) == 1

    rel = store.get_relation(res.linked_relation_ids[0])
    assert rel.source_id == "k-1"
    assert rel.target_id == "k-2"
    assert rel.kind == KnowledgeRelationKind.EQUIVALENT_TO


def test_apply_plan_stale_fingerprint_raises(store: KnowledgeStoreProtocol) -> None:
    item_a = _make_item("k-1", "Original text")
    item_b = _make_item("k-2", "Original text")
    store.save_item(item_a)
    store.save_item(item_b)

    consolidator = KnowledgeConsolidator(store)
    candidates = consolidator.find_candidates()
    plan = consolidator.build_plan(candidates, actor_id="actor-1", dry_run=False)

    # Mutate item_a after plan creation
    mutated_a = replace(item_a, statement="Mutated text after plan creation")
    store.save_item(mutated_a)

    with pytest.raises(KnowledgeConsolidationConflictError):
        consolidator.apply_plan(plan)


def test_apply_plan_manual_review_raises(store: KnowledgeStoreProtocol) -> None:
    action = ConsolidationAction(
        decision=ConsolidationDecision.MANUAL_REVIEW,
        source_item_ids=("k-1", "k-2"),
        actor_id="actor-1",
    )
    plan = ConsolidationPlan(
        actions=(action,),
        actor_id="actor-1",
        dry_run=False,
    )

    consolidator = KnowledgeConsolidator(store)
    with pytest.raises(ManualReviewRequiredError):
        consolidator.apply_plan(plan)


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
