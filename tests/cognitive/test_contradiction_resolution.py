"""Tests for Phase 8.10 Contradiction Resolution Engine."""

from datetime import datetime, timezone

import pytest

from cmm.cognitive.contracts import Confidence
from cmm.cognitive.contradiction_detection_contracts import (
    ContradictionDetection,
    ContradictionKind,
    ContradictionSignal,
)
from cmm.cognitive.contradiction_resolution import (
    ContradictionResolutionEngine,
    KnowledgeContradictionResolver,
    generate_resolution_proposal_id,
)
from cmm.cognitive.enums import (
    ContradictionSeverity,
    EvidenceKind,
    EvidencePolarityKind,
    KnowledgeKind,
    KnowledgeStatus,
    TemporalScopeKind,
)
from cmm.cognitive.errors import (
    InvalidResolutionProposalError,
    KnowledgeStoreNotFoundError,
    ResolutionConflictError,
)
from cmm.cognitive.knowledge import (
    Contradiction,
    Evidence,
    KnowledgeItem,
    TemporalScope,
)
from cmm.cognitive.resolution_contracts import (
    ContradictionResolutionProposal,
    ResolutionDecision,
    ResolutionStatus,
)
from cmm.cognitive.store_memory import InMemoryKnowledgeStore


def create_test_item(
    item_id: str,
    statement: str,
    *,
    kind: KnowledgeKind = KnowledgeKind.FACT,
    confidence_val: float = 0.8,
    status: KnowledgeStatus = KnowledgeStatus.ACTIVE,
    resource_id: str | None = "res-1",
    actor_id: str | None = "actor-1",
    temporal_scope: TemporalScope | None = None,
    evidence: tuple[Evidence, ...] = (),
    updated_at: datetime | None = None,
) -> KnowledgeItem:
    now = datetime.now(timezone.utc)
    return KnowledgeItem(
        id=item_id,
        statement=statement,
        kind=kind,
        confidence=Confidence(value=confidence_val, source="test"),
        status=status,
        resource_id=resource_id,
        actor_id=actor_id,
        temporal_scope=temporal_scope or TemporalScope(kind=TemporalScopeKind.TIMELESS),
        evidence=evidence,
        created_at=now,
        updated_at=updated_at or now,
    )


def create_test_evidence(ev_id: str, resource_id: str = "res-1") -> Evidence:
    return Evidence(
        id=ev_id,
        resource_id=resource_id,
        fragment="Sample evidence text fragment",
        confidence=Confidence(value=0.85, source="test"),
        kind=EvidenceKind.DOCUMENT_REFERENCE,
        polarity=EvidencePolarityKind.SUPPORTING,
        observed_at=datetime.now(timezone.utc),
    )


def test_deterministic_proposal_id_generation():
    prop_id_1 = generate_resolution_proposal_id(
        "cntr-100", ResolutionDecision.REQUEST_HUMAN_REVIEW, "item-a", "item-b"
    )
    prop_id_2 = generate_resolution_proposal_id(
        "cntr-100", ResolutionDecision.REQUEST_HUMAN_REVIEW, "item-a", "item-b"
    )
    # Order of item_a and item_b should be canonicalized in seed
    prop_id_3 = generate_resolution_proposal_id(
        "cntr-100", ResolutionDecision.REQUEST_HUMAN_REVIEW, "item-b", "item-a"
    )

    assert prop_id_1 == prop_id_2
    assert prop_id_1 == prop_id_3
    assert prop_id_1.startswith("resolution-proposal:cognitive:")


def test_basic_proposal_generation():
    resolver = KnowledgeContradictionResolver()
    ev_a = create_test_evidence("ev-a")
    ev_b = create_test_evidence("ev-b")

    item_a = create_test_item(
        "item-a", "El contrato está activo.", confidence_val=0.9, evidence=(ev_a,)
    )
    item_b = create_test_item(
        "item-b", "El contrato está extinguido.", confidence_val=0.5, evidence=(ev_b,)
    )

    cntr = Contradiction(
        id="cntr-1",
        item_a_id="item-a",
        item_b_id="item-b",
        severity=ContradictionSeverity.HIGH,
        explanation="Conflicto directo sobre el estado del contrato.",
    )

    proposals = resolver.propose_resolutions(cntr, item_a, item_b)

    assert isinstance(proposals, tuple)
    assert len(proposals) > 0

    for prop in proposals:
        assert isinstance(prop, ContradictionResolutionProposal)
        assert prop.status == ResolutionStatus.PROPOSED
        assert prop.contradiction_id == "cntr-1"
        assert prop.item_a_id == "item-a"
        assert prop.item_b_id == "item-b"
        assert 0.0 <= prop.confidence <= 1.0
        assert len(prop.rationale) > 0
        assert "ev-a" in prop.evidence_ids
        assert "ev-b" in prop.evidence_ids


def test_propose_dont_decide_non_mutating():
    resolver = KnowledgeContradictionResolver()
    item_a = create_test_item("item-a", "Statement A", confidence_val=0.9)
    item_b = create_test_item("item-b", "Statement B", confidence_val=0.4)
    cntr = Contradiction(id="cntr-nomutate", item_a_id="item-a", item_b_id="item-b")

    item_a_dict_before = item_a.serialize()
    item_b_dict_before = item_b.serialize()

    proposals = resolver.propose_resolutions(cntr, item_a, item_b)
    assert len(proposals) > 0

    # Ensure items were NOT mutated
    assert item_a.serialize() == item_a_dict_before
    assert item_b.serialize() == item_b_dict_before
    assert item_a.status == KnowledgeStatus.ACTIVE
    assert item_b.status == KnowledgeStatus.ACTIVE


def test_strict_determinism():
    resolver = KnowledgeContradictionResolver()
    item_a = create_test_item("item-a", "Servicio operativo.", confidence_val=0.85)
    item_b = create_test_item("item-b", "Servicio suspendido.", confidence_val=0.70)
    cntr = Contradiction(id="cntr-det", item_a_id="item-a", item_b_id="item-b")

    now = datetime.now(timezone.utc)
    proposals_run_1 = resolver.propose_resolutions(cntr, item_a, item_b, created_at=now)
    proposals_run_2 = resolver.propose_resolutions(cntr, item_a, item_b, created_at=now)

    assert len(proposals_run_1) == len(proposals_run_2)
    for p1, p2 in zip(proposals_run_1, proposals_run_2):
        assert p1 == p2
        assert p1.id == p2.id
        assert p1.confidence == p2.confidence
        assert p1.decision == p2.decision
        assert p1.rationale == p2.rationale


def test_decision_scenarios():
    resolver = KnowledgeContradictionResolver()

    # Scenario 1: Direct High Severity -> REQUEST_HUMAN_REVIEW should be top candidate
    item_a = create_test_item("item-1", "Fact A", confidence_val=0.8)
    item_b = create_test_item("item-2", "Fact B", confidence_val=0.8)
    cntr_high = Contradiction(
        id="cntr-high",
        item_a_id="item-1",
        item_b_id="item-2",
        severity=ContradictionSeverity.HIGH,
    )
    props_high = resolver.propose_resolutions(cntr_high, item_a, item_b)
    assert props_high[0].decision == ResolutionDecision.REQUEST_HUMAN_REVIEW

    # Scenario 2: Clear confidence disparity -> PREFER_ITEM_A
    item_high = create_test_item("item-h", "Fact High", confidence_val=0.95)
    item_low = create_test_item("item-l", "Fact Low", confidence_val=0.20)
    cntr_disp = Contradiction(id="cntr-disp", item_a_id="item-h", item_b_id="item-l")
    props_disp = resolver.propose_resolutions(cntr_disp, item_high, item_low)
    decisions = [p.decision for p in props_disp]
    assert ResolutionDecision.PREFER_ITEM_A in decisions

    # Scenario 3: Distinct temporal scopes -> KEEP_BOTH candidate
    t_a = TemporalScope(
        kind=TemporalScopeKind.INTERVAL,
        valid_from=datetime(2025, 1, 1, tzinfo=timezone.utc),
        valid_until=datetime(2025, 6, 30, tzinfo=timezone.utc),
    )
    t_b = TemporalScope(
        kind=TemporalScopeKind.INTERVAL,
        valid_from=datetime(2025, 7, 1, tzinfo=timezone.utc),
        valid_until=datetime(2025, 12, 31, tzinfo=timezone.utc),
    )
    item_t1 = create_test_item("item-t1", "Contrato 2025 H1", temporal_scope=t_a)
    item_t2 = create_test_item("item-t2", "Contrato 2025 H2", temporal_scope=t_b)
    cntr_temp = Contradiction(id="cntr-temp", item_a_id="item-t1", item_b_id="item-t2")
    props_temp = resolver.propose_resolutions(cntr_temp, item_t1, item_t2)
    decisions_temp = [p.decision for p in props_temp]
    assert ResolutionDecision.KEEP_BOTH in decisions_temp

    # Scenario 4: Expired item -> MARK_ONE_INVALID
    t_exp = TemporalScope(
        kind=TemporalScopeKind.INTERVAL,
        valid_from=datetime(2020, 1, 1, tzinfo=timezone.utc),
        valid_until=datetime(2021, 1, 1, tzinfo=timezone.utc),
    )
    item_exp = create_test_item("item-exp", "Fact Expired", temporal_scope=t_exp)
    item_cur = create_test_item("item-cur", "Fact Current")
    cntr_exp = Contradiction(id="cntr-exp", item_a_id="item-exp", item_b_id="item-cur")
    props_exp = resolver.propose_resolutions(cntr_exp, item_exp, item_cur)
    decisions_exp = [p.decision for p in props_exp]
    assert ResolutionDecision.MARK_ONE_INVALID in decisions_exp


def test_propose_for_detection_record():
    resolver = KnowledgeContradictionResolver()
    item_a = create_test_item("item-a", "Precio es 100", confidence_val=0.9)
    item_b = create_test_item("item-b", "Precio es 200", confidence_val=0.9)

    detection = ContradictionDetection(
        item_a_id="item-a",
        item_b_id="item-b",
        is_contradiction=True,
        kind=ContradictionKind.QUANTITATIVE,
        severity=ContradictionSeverity.MEDIUM,
        confidence=0.85,
        signals=(
            ContradictionSignal(
                kind=ContradictionKind.QUANTITATIVE,
                field="statement",
                value_a=100,
                value_b=200,
                strength=0.9,
                reason="Value mismatch for price quantity",
            ),
        ),
    )

    props = resolver.propose_for_detection(detection, item_a, item_b)
    assert len(props) > 0
    decisions = [p.decision for p in props]
    assert (
        ResolutionDecision.MERGE_INFORMATION in decisions
        or ResolutionDecision.REQUEST_HUMAN_REVIEW in decisions
    )


def test_propose_for_contradiction_with_store():
    store = InMemoryKnowledgeStore()
    resolver = KnowledgeContradictionResolver(store=store)

    item_a = create_test_item("item-store-a", "Servidor activo.")
    item_b = create_test_item("item-store-b", "Servidor apagado.")
    store.save_item(item_a)
    store.save_item(item_b)

    cntr = Contradiction(
        id="cntr-store", item_a_id="item-store-a", item_b_id="item-store-b"
    )
    store.save_contradiction(cntr)

    props = resolver.propose_for_contradiction(cntr)
    assert len(props) > 0
    assert props[0].contradiction_id == "cntr-store"


def test_propose_batch():
    store = InMemoryKnowledgeStore()
    resolver = KnowledgeContradictionResolver(store=store)

    item_1 = create_test_item("item-1", "Fact 1")
    item_2 = create_test_item("item-2", "Fact 2")
    item_3 = create_test_item("item-3", "Fact 3")
    item_4 = create_test_item("item-4", "Fact 4")

    store.save_item(item_1)
    store.save_item(item_2)
    store.save_item(item_3)
    store.save_item(item_4)

    cntr_1 = Contradiction(id="cntr-batch-1", item_a_id="item-1", item_b_id="item-2")
    cntr_2 = Contradiction(id="cntr-batch-2", item_a_id="item-3", item_b_id="item-4")

    batch_props = resolver.propose_batch([cntr_1, cntr_2])
    assert len(batch_props) > 0
    cntr_ids = {p.contradiction_id for p in batch_props}
    assert "cntr-batch-1" in cntr_ids
    assert "cntr-batch-2" in cntr_ids


def test_error_validations():
    resolver = KnowledgeContradictionResolver()
    item_a = create_test_item("item-a", "Fact A")
    item_b = create_test_item("item-b", "Fact B")

    # Mismatched item IDs between contradiction and items
    cntr_mismatch = Contradiction(
        id="cntr-mis", item_a_id="item-a", item_b_id="item-other"
    )
    with pytest.raises(ResolutionConflictError):
        resolver.propose_resolutions(cntr_mismatch, item_a, item_b)

    # Same item IDs
    with pytest.raises(InvalidResolutionProposalError):
        resolver.propose_resolutions(None, item_a, item_a)

    # Missing store for propose_for_contradiction
    cntr = Contradiction(id="cntr-nostore", item_a_id="item-a", item_b_id="item-b")
    with pytest.raises(KnowledgeStoreNotFoundError):
        resolver.propose_for_contradiction(cntr)

    # Naive datetime
    naive_now = datetime.now()  # noqa: DTZ005
    with pytest.raises(InvalidResolutionProposalError):
        resolver.propose_resolutions(None, item_a, item_b, created_at=naive_now)


def test_proposal_serialization_and_roundtrip():
    resolver = KnowledgeContradictionResolver()
    item_a = create_test_item("item-a", "Fact A", confidence_val=0.9)
    item_b = create_test_item("item-b", "Fact B", confidence_val=0.4)
    cntr = Contradiction(id="cntr-rt", item_a_id="item-a", item_b_id="item-b")

    proposals = resolver.propose_resolutions(cntr, item_a, item_b)
    for prop in proposals:
        data = prop.serialize()
        restored = ContradictionResolutionProposal.from_dict(data)
        assert prop == restored


def test_architectural_equivalence_alias():
    assert ContradictionResolutionEngine is KnowledgeContradictionResolver
