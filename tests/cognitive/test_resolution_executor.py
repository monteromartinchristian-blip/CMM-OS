"""Unit tests for Phase 8.12 Contradiction Resolution Executor."""

from datetime import datetime, timezone

import pytest

from cmm.cognitive.contracts import Confidence
from cmm.cognitive.enums import EvidenceKind, KnowledgeKind, KnowledgeStatus
from cmm.cognitive.errors import InvalidResolutionExecutionError
from cmm.cognitive.knowledge import Evidence, KnowledgeItem
from cmm.cognitive.resolution_contracts import (
    ContradictionResolutionProposal,
    ResolutionDecision,
    ResolutionStatus,
)
from cmm.cognitive.resolution_executor import ContradictionResolutionExecutor
from cmm.cognitive.resolution_executor_contracts import (
    ExecutionStatus,
    ResolutionAuditRecord,
    ResolutionExecutionResult,
)
from cmm.cognitive.resolution_policy_contracts import (
    PolicyDecision,
    PolicySeverity,
    ResolutionPolicyEvaluation,
)
from cmm.cognitive.store_memory import InMemoryKnowledgeStore


def _utc(
    year: int = 2026,
    month: int = 1,
    day: int = 1,
    hour: int = 0,
    minute: int = 0,
    second: int = 0,
) -> datetime:
    return datetime(year, month, day, hour, minute, second, tzinfo=timezone.utc)


def _make_item(
    item_id: str,
    statement: str = "Test statement",
    kind: KnowledgeKind = KnowledgeKind.FACT,
    confidence_val: float = 0.9,
) -> KnowledgeItem:
    return KnowledgeItem(
        id=item_id,
        statement=statement,
        kind=kind,
        confidence=Confidence(value=confidence_val, source="test"),
        created_at=_utc(),
        updated_at=_utc(),
    )


def _make_proposal(
    *,
    proposal_id: str = "prop-101",
    item_a_id: str = "item-a",
    item_b_id: str = "item-b",
    decision: ResolutionDecision = ResolutionDecision.KEEP_BOTH,
    confidence: float = 0.9,
    metadata: dict | None = None,
) -> ContradictionResolutionProposal:
    return ContradictionResolutionProposal(
        id=proposal_id,
        contradiction_id="cd-100",
        item_a_id=item_a_id,
        item_b_id=item_b_id,
        decision=decision,
        status=ResolutionStatus.APPROVED,
        confidence=confidence,
        rationale=("Automated resolution proposal",),
        created_at=_utc(),
        metadata=metadata or {},
    )


def _make_evaluation(
    proposal_id: str = "prop-101",
    decision: PolicyDecision = PolicyDecision.AUTO_APPROVED,
    allowed: bool = True,
) -> ResolutionPolicyEvaluation:
    return ResolutionPolicyEvaluation(
        proposal_id=proposal_id,
        decision=decision,
        severity=PolicySeverity.LOW,
        confidence=0.9,
        allowed=allowed,
        reasons=("Policy auto-approval granted",),
    )


# ── 1. Validation Tests ───────────────────────────────────────────────────────


def test_invalid_proposal_instance_raises_error() -> None:
    store = InMemoryKnowledgeStore()
    executor = ContradictionResolutionExecutor(store)
    evaluation = _make_evaluation()

    with pytest.raises(InvalidResolutionExecutionError, match="proposal must be"):
        executor.execute("not-a-proposal", evaluation)  # type: ignore[arg-type]


def test_invalid_evaluation_instance_raises_error() -> None:
    store = InMemoryKnowledgeStore()
    executor = ContradictionResolutionExecutor(store)
    proposal = _make_proposal()

    with pytest.raises(InvalidResolutionExecutionError, match="evaluation must be"):
        executor.execute(proposal, "not-an-evaluation")  # type: ignore[arg-type]


def test_mismatched_proposal_and_evaluation_id_raises_error() -> None:
    store = InMemoryKnowledgeStore()
    executor = ContradictionResolutionExecutor(store)
    proposal = _make_proposal(proposal_id="prop-1")
    evaluation = _make_evaluation(proposal_id="prop-2")

    with pytest.raises(InvalidResolutionExecutionError, match="does not match"):
        executor.execute(proposal, evaluation)


def test_unapproved_policy_decision_raises_error() -> None:
    store = InMemoryKnowledgeStore()
    executor = ContradictionResolutionExecutor(store)
    proposal = _make_proposal()
    evaluation = _make_evaluation(
        decision=PolicyDecision.HUMAN_REVIEW_REQUIRED, allowed=False
    )

    with pytest.raises(InvalidResolutionExecutionError, match="not approved"):
        executor.execute(proposal, evaluation)


def test_request_human_review_proposal_raises_error() -> None:
    store = InMemoryKnowledgeStore()
    executor = ContradictionResolutionExecutor(store)
    proposal = _make_proposal(decision=ResolutionDecision.REQUEST_HUMAN_REVIEW)
    evaluation = _make_evaluation(decision=PolicyDecision.AUTO_APPROVED, allowed=True)

    with pytest.raises(InvalidResolutionExecutionError, match="cannot be executed"):
        executor.execute(proposal, evaluation)


# ── 2. KEEP_BOTH & DEFER Execution Tests ─────────────────────────────────────


def test_execute_keep_both_does_not_modify_store() -> None:
    store = InMemoryKnowledgeStore()
    item_a = _make_item("item-a", "Statement A")
    item_b = _make_item("item-b", "Statement B")
    store.save_item(item_a)
    store.save_item(item_b)

    executor = ContradictionResolutionExecutor(store)
    proposal = _make_proposal(decision=ResolutionDecision.KEEP_BOTH)
    evaluation = _make_evaluation()

    result = executor.execute(proposal, evaluation)

    assert result.status == ExecutionStatus.COMPLETED
    assert result.applied is False
    assert result.updated_item_ids == ()
    assert result.superseded_item_ids == ()
    assert store.get_item("item-a").status == KnowledgeStatus.ACTIVE
    assert store.get_item("item-b").status == KnowledgeStatus.ACTIVE


def test_execute_defer_does_not_modify_store() -> None:
    store = InMemoryKnowledgeStore()
    item_a = _make_item("item-a")
    item_b = _make_item("item-b")
    store.save_item(item_a)
    store.save_item(item_b)

    executor = ContradictionResolutionExecutor(store)
    proposal = _make_proposal(decision=ResolutionDecision.DEFER)
    evaluation = _make_evaluation()

    result = executor.execute(proposal, evaluation)

    assert result.status == ExecutionStatus.COMPLETED
    assert result.applied is False
    assert result.updated_item_ids == ()


# ── 3. PREFER_ITEM_A & PREFER_ITEM_B Tests ───────────────────────────────────


def test_execute_prefer_item_a_supersedes_b_bidirectionally() -> None:
    store = InMemoryKnowledgeStore()
    item_a = _make_item("item-a", "Version A")
    item_b = _make_item("item-b", "Version B")
    store.save_item(item_a)
    store.save_item(item_b)

    executor = ContradictionResolutionExecutor(store)
    proposal = _make_proposal(decision=ResolutionDecision.PREFER_ITEM_A)
    evaluation = _make_evaluation()

    result = executor.execute(proposal, evaluation)

    assert result.status == ExecutionStatus.COMPLETED
    assert result.applied is True
    assert result.updated_item_ids == ("item-a",)
    assert result.superseded_item_ids == ("item-b",)

    fetched_a = store.get_item("item-a")
    fetched_b = store.get_item("item-b")

    assert fetched_b.status == KnowledgeStatus.SUPERSEDED
    assert fetched_b.superseded_by_id == "item-a"
    assert fetched_a.status == KnowledgeStatus.ACTIVE
    assert fetched_a.supersedes_id == "item-b"


def test_execute_prefer_item_b_supersedes_a_bidirectionally() -> None:
    store = InMemoryKnowledgeStore()
    item_a = _make_item("item-a", "Version A")
    item_b = _make_item("item-b", "Version B")
    store.save_item(item_a)
    store.save_item(item_b)

    executor = ContradictionResolutionExecutor(store)
    proposal = _make_proposal(decision=ResolutionDecision.PREFER_ITEM_B)
    evaluation = _make_evaluation()

    result = executor.execute(proposal, evaluation)

    assert result.status == ExecutionStatus.COMPLETED
    assert result.applied is True
    assert result.updated_item_ids == ("item-b",)
    assert result.superseded_item_ids == ("item-a",)

    fetched_a = store.get_item("item-a")
    fetched_b = store.get_item("item-b")

    assert fetched_a.status == KnowledgeStatus.SUPERSEDED
    assert fetched_a.superseded_by_id == "item-b"
    assert fetched_b.status == KnowledgeStatus.ACTIVE
    assert fetched_b.supersedes_id == "item-a"


# ── 4. MARK_ONE_INVALID Tests ───────────────────────────────────────────────


def test_execute_mark_one_invalid_invalidates_without_deletion() -> None:
    store = InMemoryKnowledgeStore()
    item_a = _make_item("item-a", "Valid statement")
    item_b = _make_item("item-b", "Invalid statement")
    store.save_item(item_a)
    store.save_item(item_b)

    executor = ContradictionResolutionExecutor(store)
    proposal = _make_proposal(decision=ResolutionDecision.MARK_ONE_INVALID)
    evaluation = _make_evaluation()

    result = executor.execute(proposal, evaluation)

    assert result.status == ExecutionStatus.COMPLETED
    assert result.applied is True
    assert result.updated_item_ids == ("item-b",)

    fetched_b = store.get_item("item-b")
    assert fetched_b.status == KnowledgeStatus.INVALIDATED
    assert fetched_b.invalidated_at is not None
    assert fetched_b.invalidation_reason is not None
    assert "Invalidated by contradiction resolution" in fetched_b.invalidation_reason

    # Item A is untouched
    assert store.get_item("item-a").status == KnowledgeStatus.ACTIVE


# ── 5. MERGE_INFORMATION Tests ──────────────────────────────────────────────


def test_execute_merge_information_combines_evidence_metadata_and_supersedes() -> None:
    store = InMemoryKnowledgeStore()

    ev_a = Evidence(
        id="ev-a",
        resource_id="res-1",
        fragment="Fragment A",
        confidence=Confidence(value=0.9, source="src"),
        kind=EvidenceKind.DIRECT_QUOTE,
        observed_at=_utc(),
    )
    ev_b = Evidence(
        id="ev-b",
        resource_id="res-2",
        fragment="Fragment B",
        confidence=Confidence(value=0.8, source="src"),
        kind=EvidenceKind.PARAPHRASE,
        observed_at=_utc(),
    )

    item_a = KnowledgeItem(
        id="item-a",
        statement="Item A statement",
        kind=KnowledgeKind.FACT,
        confidence=Confidence(value=0.9, source="a"),
        evidence=(ev_a,),
        metadata={"key_a": "val_a"},
        created_at=_utc(),
        updated_at=_utc(),
    )
    item_b = KnowledgeItem(
        id="item-b",
        statement="Item B statement",
        kind=KnowledgeKind.FACT,
        confidence=Confidence(value=0.7, source="b"),
        evidence=(ev_b,),
        metadata={"key_b": "val_b"},
        created_at=_utc(),
        updated_at=_utc(),
    )
    store.save_item(item_a)
    store.save_item(item_b)

    executor = ContradictionResolutionExecutor(store)
    proposal = _make_proposal(decision=ResolutionDecision.MERGE_INFORMATION)
    evaluation = _make_evaluation()

    result = executor.execute(proposal, evaluation)

    assert result.status == ExecutionStatus.COMPLETED
    assert result.applied is True
    assert result.updated_item_ids == ("item-a",)
    assert result.superseded_item_ids == ("item-b",)

    fetched_a = store.get_item("item-a")
    fetched_b = store.get_item("item-b")

    # Evidence combined
    assert len(fetched_a.evidence) == 2
    ev_ids = {e.id for e in fetched_a.evidence}
    assert ev_ids == {"ev-a", "ev-b"}

    # Metadata preserved and lineage tracked
    assert fetched_a.metadata["key_a"] == "val_a"
    assert "resolution_merge" in fetched_a.metadata

    # Source superseded
    assert fetched_b.status == KnowledgeStatus.SUPERSEDED
    assert fetched_b.superseded_by_id == "item-a"


# ── 6. Transaction Rollback Tests ───────────────────────────────────────────


def test_execute_transaction_rollback_on_missing_item_restores_store() -> None:
    store = InMemoryKnowledgeStore()
    item_a = _make_item("item-a")
    store.save_item(item_a)
    # item-b is missing in store!

    executor = ContradictionResolutionExecutor(store)
    proposal = _make_proposal(decision=ResolutionDecision.PREFER_ITEM_A)
    evaluation = _make_evaluation()

    result = executor.execute(proposal, evaluation)

    assert result.status == ExecutionStatus.ROLLED_BACK
    assert result.applied is False
    assert len(result.errors) > 0

    # Store state is unchanged
    assert store.contains_item("item-a")
    assert store.get_item("item-a").status == KnowledgeStatus.ACTIVE


# ── 7. Audit & Determinism Tests ─────────────────────────────────────────────


def test_execute_generates_audit_record() -> None:
    store = InMemoryKnowledgeStore()
    item_a = _make_item("item-a")
    item_b = _make_item("item-b")
    store.save_item(item_a)
    store.save_item(item_b)

    executor = ContradictionResolutionExecutor(store)
    proposal = _make_proposal(decision=ResolutionDecision.KEEP_BOTH)
    evaluation = _make_evaluation()

    result = executor.execute(proposal, evaluation, actor_id="actor-99")

    assert "audit_record" in result.metadata
    audit_data = result.metadata["audit_record"]
    audit = ResolutionAuditRecord.from_dict(audit_data)

    assert audit.audit_id.startswith("audit:resolution:")
    assert audit.proposal_id == proposal.id
    assert audit.actor_id == "actor-99"
    assert audit.details["decision"] == ResolutionDecision.KEEP_BOTH.value


def test_execution_determinism() -> None:
    store1 = InMemoryKnowledgeStore()
    store1.save_item(_make_item("item-a"))
    store1.save_item(_make_item("item-b"))

    store2 = InMemoryKnowledgeStore()
    store2.save_item(_make_item("item-a"))
    store2.save_item(_make_item("item-b"))

    executor1 = ContradictionResolutionExecutor(store1)
    executor2 = ContradictionResolutionExecutor(store2)

    proposal = _make_proposal(decision=ResolutionDecision.PREFER_ITEM_A)
    evaluation = _make_evaluation()

    res1 = executor1.execute(proposal, evaluation)
    res2 = executor2.execute(proposal, evaluation)

    assert res1.applied == res2.applied == True
    assert res1.updated_item_ids == res2.updated_item_ids == ("item-a",)
    assert res1.superseded_item_ids == res2.superseded_item_ids == ("item-b",)


# ── 8. Serialization Roundtrip Tests ──────────────────────────────────────────


def test_resolution_execution_result_serialization_roundtrip() -> None:
    result = ResolutionExecutionResult(
        execution_id="exec-001",
        proposal_id="prop-101",
        status=ExecutionStatus.COMPLETED,
        applied=True,
        updated_item_ids=("item-a",),
        superseded_item_ids=("item-b",),
        started_at=_utc(),
        finished_at=_utc(),
        metadata={"foo": "bar"},
    )

    serialized = result.serialize()
    deserialized = ResolutionExecutionResult.from_dict(serialized)

    assert deserialized == result
    assert deserialized.metadata["foo"] == "bar"


def test_resolution_audit_record_serialization_roundtrip() -> None:
    audit = ResolutionAuditRecord(
        audit_id="audit:resolution:12345",
        execution_id="exec-001",
        proposal_id="prop-101",
        actor_id="actor-1",
        action="execute:keep_both",
        timestamp=_utc(),
        details={"applied": False},
    )

    serialized = audit.serialize()
    deserialized = ResolutionAuditRecord.from_dict(serialized)

    assert deserialized == audit
    assert deserialized.details["applied"] is False
