"""Unit tests for Phase 8.11 Contradiction Resolution Policy Layer."""

import pytest

from cmm.cognitive.errors import (
    InvalidResolutionPolicyEvaluationError,
    KnowledgeResolutionPolicyError,
    ResolutionPolicyConflictError,
)
from cmm.cognitive.resolution_contracts import (
    ContradictionResolutionProposal,
    ResolutionDecision,
    ResolutionStatus,
)
from cmm.cognitive.resolution_policy import ContradictionResolutionPolicyEngine
from cmm.cognitive.resolution_policy_contracts import (
    PolicyDecision,
    PolicySeverity,
    ResolutionPolicyEvaluation,
)


def _make_proposal(
    *,
    proposal_id: str = "prop-101",
    decision: ResolutionDecision = ResolutionDecision.KEEP_BOTH,
    confidence: float = 0.85,
) -> ContradictionResolutionProposal:
    return ContradictionResolutionProposal(
        id=proposal_id,
        contradiction_id="cd-1",
        item_a_id="item-a",
        item_b_id="item-b",
        decision=decision,
        status=ResolutionStatus.PROPOSED,
        confidence=confidence,
        rationale=("Test proposal rationale",),
    )


# ── 1. Conservative Mode Tests ───────────────────────────────────────────────


def test_conservative_mode_default_auto_resolution_disabled() -> None:
    engine = ContradictionResolutionPolicyEngine()
    assert engine.allow_auto_resolution is False


@pytest.mark.parametrize(
    "decision",
    [
        ResolutionDecision.KEEP_BOTH,
        ResolutionDecision.PREFER_ITEM_A,
        ResolutionDecision.PREFER_ITEM_B,
        ResolutionDecision.MERGE_INFORMATION,
        ResolutionDecision.MARK_ONE_INVALID,
        ResolutionDecision.REQUEST_HUMAN_REVIEW,
        ResolutionDecision.DEFER,
    ],
)
def test_conservative_mode_denies_all_auto_approvals(
    decision: ResolutionDecision,
) -> None:
    engine = ContradictionResolutionPolicyEngine(allow_auto_resolution=False)
    proposal = _make_proposal(decision=decision, confidence=0.99)
    eval_result = engine.evaluate(proposal)

    assert eval_result.allowed is False
    assert eval_result.decision != PolicyDecision.AUTO_APPROVED


# ── 2. Auto Resolution Enabled Tests ──────────────────────────────────────────


def test_auto_resolution_enabled_keep_both_approved() -> None:
    engine = ContradictionResolutionPolicyEngine(allow_auto_resolution=True)
    proposal = _make_proposal(decision=ResolutionDecision.KEEP_BOTH, confidence=0.75)
    eval_result = engine.evaluate(proposal)

    assert eval_result.allowed is True
    assert eval_result.decision == PolicyDecision.AUTO_APPROVED
    assert eval_result.severity == PolicySeverity.LOW


# ── 3. Human Review Required Tests ───────────────────────────────────────────


def test_human_review_explicitly_requested() -> None:
    engine = ContradictionResolutionPolicyEngine(allow_auto_resolution=True)
    proposal = _make_proposal(
        decision=ResolutionDecision.REQUEST_HUMAN_REVIEW, confidence=0.99
    )
    eval_result = engine.evaluate(proposal)

    assert eval_result.allowed is False
    assert eval_result.decision == PolicyDecision.HUMAN_REVIEW_REQUIRED
    assert eval_result.severity == PolicySeverity.HIGH
    assert any("explicitly requires human validation" in r for r in eval_result.reasons)


# ── 4. Prefer Decisions Tests ─────────────────────────────────────────────────


def test_prefer_item_a_forbidden_auto_approval() -> None:
    engine = ContradictionResolutionPolicyEngine(allow_auto_resolution=True)
    proposal = _make_proposal(
        decision=ResolutionDecision.PREFER_ITEM_A, confidence=0.99
    )
    eval_result = engine.evaluate(proposal)

    assert eval_result.allowed is False
    assert eval_result.decision == PolicyDecision.HUMAN_REVIEW_REQUIRED
    assert eval_result.severity == PolicySeverity.HIGH
    assert any("forbidden without authority policy" in r for r in eval_result.reasons)


def test_prefer_item_b_forbidden_auto_approval() -> None:
    engine = ContradictionResolutionPolicyEngine(allow_auto_resolution=True)
    proposal = _make_proposal(
        decision=ResolutionDecision.PREFER_ITEM_B, confidence=0.99
    )
    eval_result = engine.evaluate(proposal)

    assert eval_result.allowed is False
    assert eval_result.decision == PolicyDecision.HUMAN_REVIEW_REQUIRED
    assert eval_result.severity == PolicySeverity.HIGH
    assert any("forbidden without authority policy" in r for r in eval_result.reasons)


# ── 5. Invalidating Knowledge Tests ──────────────────────────────────────────


def test_mark_one_invalid_requires_human_authority() -> None:
    engine = ContradictionResolutionPolicyEngine(allow_auto_resolution=True)
    proposal = _make_proposal(
        decision=ResolutionDecision.MARK_ONE_INVALID, confidence=0.99
    )
    eval_result = engine.evaluate(proposal)

    assert eval_result.allowed is False
    assert eval_result.decision == PolicyDecision.HUMAN_REVIEW_REQUIRED
    assert eval_result.severity == PolicySeverity.HIGH
    assert any("epistemological validity" in r for r in eval_result.reasons)


# ── 6. Merge Information Tests ───────────────────────────────────────────────


def test_merge_information_auto_approved_high_confidence() -> None:
    engine = ContradictionResolutionPolicyEngine(allow_auto_resolution=True)
    proposal = _make_proposal(
        decision=ResolutionDecision.MERGE_INFORMATION, confidence=0.95
    )
    eval_result = engine.evaluate(proposal)

    assert eval_result.allowed is True
    assert eval_result.decision == PolicyDecision.AUTO_APPROVED
    assert eval_result.severity == PolicySeverity.LOW


def test_merge_information_human_review_low_confidence() -> None:
    engine = ContradictionResolutionPolicyEngine(allow_auto_resolution=True)
    proposal = _make_proposal(
        decision=ResolutionDecision.MERGE_INFORMATION, confidence=0.50
    )
    eval_result = engine.evaluate(proposal)

    assert eval_result.allowed is False
    assert eval_result.decision == PolicyDecision.HUMAN_REVIEW_REQUIRED
    assert eval_result.severity == PolicySeverity.MEDIUM


def test_merge_information_human_review_when_auto_resolution_disabled() -> None:
    engine = ContradictionResolutionPolicyEngine(allow_auto_resolution=False)
    proposal = _make_proposal(
        decision=ResolutionDecision.MERGE_INFORMATION, confidence=0.95
    )
    eval_result = engine.evaluate(proposal)

    assert eval_result.allowed is False
    assert eval_result.decision == PolicyDecision.HUMAN_REVIEW_REQUIRED
    assert eval_result.severity == PolicySeverity.MEDIUM


# ── 7. Defer Decision Tests ─────────────────────────────────────────────────


def test_defer_decision_returns_deferred() -> None:
    engine = ContradictionResolutionPolicyEngine(allow_auto_resolution=True)
    proposal = _make_proposal(decision=ResolutionDecision.DEFER, confidence=0.50)
    eval_result = engine.evaluate(proposal)

    assert eval_result.allowed is False
    assert eval_result.decision == PolicyDecision.DEFERRED
    assert eval_result.severity == PolicySeverity.MEDIUM


# ── 8. Serialization & Roundtrip Tests ────────────────────────────────────────


def test_evaluation_serialization_and_deserialization() -> None:
    eval_result = ResolutionPolicyEvaluation(
        proposal_id="prop-202",
        decision=PolicyDecision.AUTO_APPROVED,
        severity=PolicySeverity.LOW,
        confidence=0.92,
        allowed=True,
        reasons=("Passed safe checks",),
        warnings=("Minor warning",),
        metadata={"rule": "safe_merge"},
    )

    data = eval_result.serialize()
    assert data["proposal_id"] == "prop-202"
    assert data["decision"] == "auto_approved"
    assert data["severity"] == "low"
    assert data["confidence"] == 0.92
    assert data["allowed"] is True
    assert data["reasons"] == ["Passed safe checks"]
    assert data["warnings"] == ["Minor warning"]
    assert data["metadata"] == {"rule": "safe_merge"}

    deserialized = ResolutionPolicyEvaluation.from_mapping(data)
    assert deserialized == eval_result
    assert ResolutionPolicyEvaluation.from_dict(eval_result.to_dict()) == eval_result


# ── 9. Determinism Tests ────────────────────────────────────────────────────


def test_evaluation_determinism() -> None:
    engine = ContradictionResolutionPolicyEngine(allow_auto_resolution=True)
    proposal = _make_proposal(
        decision=ResolutionDecision.MERGE_INFORMATION, confidence=0.95
    )

    eval_1 = engine.evaluate(proposal)
    eval_2 = engine.evaluate(proposal)

    assert eval_1 == eval_2
    assert eval_1.serialize() == eval_2.serialize()


# ── 10. Contract Immutaibility & Validation Tests ─────────────────────────────


def test_evaluation_metadata_immutability() -> None:
    eval_result = ResolutionPolicyEvaluation(
        proposal_id="prop-303",
        decision=PolicyDecision.HUMAN_REVIEW_REQUIRED,
        severity=PolicySeverity.HIGH,
        confidence=0.8,
        allowed=False,
        metadata={"key": "value"},
    )

    with pytest.raises(TypeError):
        eval_result.metadata["key"] = "new_value"  # type: ignore[index]


def test_evaluation_invalid_proposal_type() -> None:
    engine = ContradictionResolutionPolicyEngine()
    with pytest.raises(ResolutionPolicyConflictError):
        engine.evaluate("not-a-proposal")  # type: ignore[arg-type]


def test_evaluation_validation_errors() -> None:
    with pytest.raises(InvalidResolutionPolicyEvaluationError):
        ResolutionPolicyEvaluation(
            proposal_id="",
            decision=PolicyDecision.AUTO_APPROVED,
            severity=PolicySeverity.LOW,
            confidence=0.5,
            allowed=True,
        )

    with pytest.raises(InvalidResolutionPolicyEvaluationError):
        ResolutionPolicyEvaluation(
            proposal_id="prop-1",
            decision="INVALID_DECISION",  # type: ignore[arg-type]
            severity=PolicySeverity.LOW,
            confidence=0.5,
            allowed=True,
        )

    with pytest.raises(InvalidResolutionPolicyEvaluationError):
        ResolutionPolicyEvaluation(
            proposal_id="prop-1",
            decision=PolicyDecision.AUTO_APPROVED,
            severity=PolicySeverity.LOW,
            confidence=1.5,
            allowed=True,
        )


def test_error_hierarchy() -> None:
    assert issubclass(
        InvalidResolutionPolicyEvaluationError, KnowledgeResolutionPolicyError
    )
    assert issubclass(ResolutionPolicyConflictError, KnowledgeResolutionPolicyError)
    assert issubclass(KnowledgeResolutionPolicyError, Exception)
