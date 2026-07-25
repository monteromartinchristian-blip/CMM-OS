"""Tests for Phase 8.9 Contradiction Resolution Contracts."""

from datetime import datetime, timezone

import pytest

from cmm.cognitive.errors import (
    InvalidResolutionProposalError,
    KnowledgeContradictionResolutionError,
    ResolutionConflictError,
)
from cmm.cognitive.resolution_contracts import (
    ContradictionResolutionProposal,
    ContradictionResolutionResult,
    ResolutionDecision,
    ResolutionStatus,
)


def test_basic_creation_and_enum_normalization():
    now = datetime.now(timezone.utc)
    proposal = ContradictionResolutionProposal(
        id="prop-1",
        contradiction_id="cntr-1",
        item_a_id="item-a",
        item_b_id="item-b",
        decision="keep_both",
        status="proposed",
        confidence=0.8,
        rationale=("Context difference",),
        evidence_ids=("ev-1",),
        actor_id="user-1",
        created_at=now,
        metadata={"note": "valid"},
    )

    assert proposal.id == "prop-1"
    assert proposal.contradiction_id == "cntr-1"
    assert proposal.item_a_id == "item-a"
    assert proposal.item_b_id == "item-b"
    assert proposal.decision == ResolutionDecision.KEEP_BOTH
    assert proposal.status == ResolutionStatus.PROPOSED
    assert proposal.confidence == 0.8
    assert proposal.rationale == ("Context difference",)
    assert proposal.evidence_ids == ("ev-1",)
    assert proposal.actor_id == "user-1"
    assert proposal.created_at == now
    assert proposal.metadata == {"note": "valid"}


def test_id_validations():
    now = datetime.now(timezone.utc)

    # Empty id
    with pytest.raises(InvalidResolutionProposalError):
        ContradictionResolutionProposal(
            id="",
            contradiction_id="cntr-1",
            item_a_id="item-a",
            item_b_id="item-b",
            decision=ResolutionDecision.KEEP_BOTH,
            status=ResolutionStatus.PROPOSED,
            confidence=0.5,
            created_at=now,
        )

    # Empty contradiction_id
    with pytest.raises(InvalidResolutionProposalError):
        ContradictionResolutionProposal(
            id="prop-1",
            contradiction_id="   ",
            item_a_id="item-a",
            item_b_id="item-b",
            decision=ResolutionDecision.KEEP_BOTH,
            status=ResolutionStatus.PROPOSED,
            confidence=0.5,
            created_at=now,
        )

    # Empty item_a_id
    with pytest.raises(InvalidResolutionProposalError):
        ContradictionResolutionProposal(
            id="prop-1",
            contradiction_id="cntr-1",
            item_a_id="",
            item_b_id="item-b",
            decision=ResolutionDecision.KEEP_BOTH,
            status=ResolutionStatus.PROPOSED,
            confidence=0.5,
            created_at=now,
        )

    # Empty item_b_id
    with pytest.raises(InvalidResolutionProposalError):
        ContradictionResolutionProposal(
            id="prop-1",
            contradiction_id="cntr-1",
            item_a_id="item-a",
            item_b_id="   ",
            decision=ResolutionDecision.KEEP_BOTH,
            status=ResolutionStatus.PROPOSED,
            confidence=0.5,
            created_at=now,
        )

    # Same item A and B
    with pytest.raises(InvalidResolutionProposalError):
        ContradictionResolutionProposal(
            id="prop-1",
            contradiction_id="cntr-1",
            item_a_id="item-same",
            item_b_id="item-same",
            decision=ResolutionDecision.KEEP_BOTH,
            status=ResolutionStatus.PROPOSED,
            confidence=0.5,
            created_at=now,
        )


def test_confidence_validation():
    now = datetime.now(timezone.utc)

    # Valid confidences
    for conf in (0.0, 0.5, 1.0, 0, 1):
        p = ContradictionResolutionProposal(
            id="prop-1",
            contradiction_id="cntr-1",
            item_a_id="item-a",
            item_b_id="item-b",
            decision=ResolutionDecision.PREFER_ITEM_A,
            status=ResolutionStatus.PROPOSED,
            confidence=conf,
            created_at=now,
        )
        assert p.confidence == float(conf)

    # Invalid confidences
    for conf in (-0.1, 1.1, 2.0, -1.0, True, False, "high"):
        with pytest.raises(InvalidResolutionProposalError):
            ContradictionResolutionProposal(
                id="prop-1",
                contradiction_id="cntr-1",
                item_a_id="item-a",
                item_b_id="item-b",
                decision=ResolutionDecision.PREFER_ITEM_A,
                status=ResolutionStatus.PROPOSED,
                confidence=conf,
                created_at=now,
            )


def test_serialization_and_roundtrip():
    now = datetime.now(timezone.utc)
    proposal = ContradictionResolutionProposal(
        id="prop-rt",
        contradiction_id="cntr-rt",
        item_a_id="item-a",
        item_b_id="item-b",
        decision=ResolutionDecision.MERGE_INFORMATION,
        status=ResolutionStatus.APPROVED,
        confidence=0.9,
        rationale=("Merge details",),
        evidence_ids=("ev-1", "ev-2"),
        actor_id="agent-9",
        created_at=now,
        metadata={"key": "value"},
    )

    serialized = proposal.serialize()
    assert serialized == proposal.to_dict()
    assert serialized["decision"] == "merge_information"
    assert serialized["status"] == "approved"
    assert serialized["rationale"] == ["Merge details"]
    assert serialized["evidence_ids"] == ["ev-1", "ev-2"]
    assert serialized["created_at"] == now.isoformat()

    restored_from_dict = ContradictionResolutionProposal.from_dict(serialized)
    restored_from_mapping = ContradictionResolutionProposal.from_mapping(serialized)

    assert proposal == restored_from_dict
    assert proposal == restored_from_mapping


def test_metadata_immutability():
    now = datetime.now(timezone.utc)
    proposal = ContradictionResolutionProposal(
        id="prop-meta",
        contradiction_id="cntr-meta",
        item_a_id="item-a",
        item_b_id="item-b",
        decision=ResolutionDecision.DEFER,
        status=ResolutionStatus.PROPOSED,
        confidence=0.5,
        created_at=now,
        metadata={"a": 1},
    )

    with pytest.raises(TypeError):
        proposal.metadata["a"] = 2


def test_timestamp_timezone_validation():
    naive_dt = datetime.now()  # noqa: DTZ005
    aware_dt = datetime.now(timezone.utc)

    # Naive should fail
    with pytest.raises(InvalidResolutionProposalError):
        ContradictionResolutionProposal(
            id="prop-ts",
            contradiction_id="cntr-ts",
            item_a_id="item-a",
            item_b_id="item-b",
            decision=ResolutionDecision.REQUEST_HUMAN_REVIEW,
            status=ResolutionStatus.PROPOSED,
            confidence=0.5,
            created_at=naive_dt,
        )

    # Aware should succeed
    proposal = ContradictionResolutionProposal(
        id="prop-ts",
        contradiction_id="cntr-ts",
        item_a_id="item-a",
        item_b_id="item-b",
        decision=ResolutionDecision.REQUEST_HUMAN_REVIEW,
        status=ResolutionStatus.PROPOSED,
        confidence=0.5,
        created_at=aware_dt,
    )
    assert proposal.created_at == aware_dt


def test_resolution_result_contract():
    start = datetime.now(timezone.utc)
    finish = datetime.now(timezone.utc)

    result = ContradictionResolutionResult(
        proposal_id="prop-res-1",
        applied=True,
        status=ResolutionStatus.APPLIED,
        affected_item_ids=("item-a", "item-b"),
        created_records=("rec-1",),
        warnings=("warn-1",),
        started_at=start,
        finished_at=finish,
        metadata={"execution": "success"},
    )

    assert result.proposal_id == "prop-res-1"
    assert result.applied is True
    assert result.status == ResolutionStatus.APPLIED
    assert result.affected_item_ids == ("item-a", "item-b")
    assert result.created_records == ("rec-1",)
    assert result.warnings == ("warn-1",)
    assert result.started_at == start
    assert result.finished_at == finish

    serialized = result.serialize()
    restored = ContradictionResolutionResult.from_dict(serialized)
    assert result == restored


def test_error_hierarchy():
    assert issubclass(KnowledgeContradictionResolutionError, Exception)
    assert issubclass(
        InvalidResolutionProposalError, KnowledgeContradictionResolutionError
    )
    assert issubclass(InvalidResolutionProposalError, ValueError)
    assert issubclass(ResolutionConflictError, KnowledgeContradictionResolutionError)
    assert issubclass(ResolutionConflictError, ValueError)
