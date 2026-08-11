"""Phase 10.22 — B5: Exam Attempts (grounded, ordinary≠reassessment).

The audit found the previous implementation counted a raw ``attempt_count`` and
treated ``passed`` as a boolean.  Attempt semantics must be grounded: an
ordinary attempt is distinct from a reassessment attempt; a failed grade does
not by itself consume an attempt; attempt counts must be grounded (never
caller-claimed); canceled or waived attempts do not count against the limit;
and the regulation in force governs the limit.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from cmm.cognitive.enums import ReasoningRuleResultStatus
from cmm.cognitive.reasoning_rule_contracts import ReasoningRuleContext
from cmm.domains.university import build_university_rules
from cmm.domains.university.rules import evaluate_exam_attempt

T = datetime(2026, 8, 1, tzinfo=timezone.utc)


def _attempt(
    *,
    kind="ordinary",
    outcome="failed",
    grounded=True,
    status="consumed",
):
    return {
        "kind": kind,
        "outcome": outcome,
        "grounded": grounded,
        "status": status,
    }


def _grounded_attempt(
    *,
    attempt_id="attempt-1",
    kind="ordinary",
    outcome="failed",
    status="consumed",
):
    return {
        "id": attempt_id,
        "exam_id": "exam-1",
        "date": "2026-07-01",
        "kind": kind,
        "outcome": outcome,
        "grounded": True,
        "status": status,
        "source_reference": f"record-{attempt_id}",
    }


def _regulation(*, temporal="valid", max_attempts=3):
    return {
        "id": "reg-1",
        "source_reference": "regulation-1",
        "source_class": "regulation",
        "temporal": temporal,
        "grounded": True,
        "applicable_scope": "subject-1",
        "max_attempts": max_attempts,
    }


def _canonical_result(*, attempts=(), regulation=None):
    rule = {
        r.definition.id: r
        for r in build_university_rules()
    }["university.exam_attempt"]
    context = ReasoningRuleContext(
        reasoning_id="exam-attempt-production",
        timestamp=T,
        active_domains=("domain:university",),
        primary_domain="domain:university",
        metadata={
            "exam_attempt": {
                "attempts": attempts,
                "regulation": regulation,
            }
        },
    )
    return rule.evaluate(context)


def test_ordinary_attempt_within_limits():
    result = evaluate_exam_attempt(
        attempts=(_attempt(), _attempt()),
        max_attempts=3,
    )
    assert result["consumed_attempts"] == 2
    assert result["within_limits"] is True
    assert result["limit_exceeded"] is False


def test_reassessment_is_not_an_ordinary_attempt():
    """A reassessment attempt is distinct from ordinary attempts and does not
    consume the ordinary attempt budget."""
    result = evaluate_exam_attempt(
        attempts=(
            _attempt(),  # one ordinary consumed
            _attempt(kind="reassessment"),  # reassessment, not ordinary
        ),
        max_attempts=1,
    )
    assert result["consumed_attempts"] == 1
    assert result["reassessment_count"] == 1
    assert result["within_limits"] is True


def test_failed_grade_does_not_by_itself_consume_attempt():
    """A failed outcome present in the record does not automatically mean the
    attempt was consumed; only grounded consumed attempts count."""
    result = evaluate_exam_attempt(
        attempts=(_attempt(outcome="failed", status="not_consumed"),),
        max_attempts=1,
    )
    assert result["consumed_attempts"] == 0
    assert result["failed_grade_not_consumed"] is True
    assert result["within_limits"] is True


def test_ungrounded_attempt_is_not_counted():
    """A caller-claimed attempt with no grounding is not authoritative and does
    not consume the budget."""
    result = evaluate_exam_attempt(
        attempts=(_attempt(grounded=False),),
        max_attempts=1,
    )
    assert result["consumed_attempts"] == 0
    assert result["ungrounded_attempts"] == 1
    assert result["within_limits"] is True


def test_canceled_attempt_does_not_count():
    result = evaluate_exam_attempt(
        attempts=(_attempt(status="canceled"),),
        max_attempts=1,
    )
    assert result["consumed_attempts"] == 0
    assert result["canceled"] == 1
    assert result["within_limits"] is True


def test_waived_attempt_does_not_count():
    result = evaluate_exam_attempt(
        attempts=(_attempt(status="waived"),),
        max_attempts=1,
    )
    assert result["consumed_attempts"] == 0
    assert result["waived"] == 1
    assert result["within_limits"] is True


def test_exceeded_limit_reported_not_acted_on():
    result = evaluate_exam_attempt(
        attempts=(
            _attempt(),
            _attempt(),
            _attempt(),
            _attempt(),
        ),
        max_attempts=3,
    )
    assert result["consumed_attempts"] == 4
    assert result["limit_exceeded"] is True
    assert result["within_limits"] is False


def test_inactive_regulation_cannot_evaluate_limits():
    """When the regulation is not in force, attempt limits cannot be evaluated
    as authoritative."""
    result = evaluate_exam_attempt(
        attempts=(_attempt(), _attempt(), _attempt()),
        max_attempts=3,
        regulation_active=False,
    )
    assert result["regulation_inactive"] is True
    assert result["limit_exceeded"] is False
    assert result["within_limits"] is False


def test_canonical_rule_missing_regulation_stays_unknown_and_verifies():
    result = _canonical_result(attempts=(_grounded_attempt(),))
    finding = result.findings[0]
    assert result.status is ReasoningRuleResultStatus.APPLIED
    assert finding.code == "EXAM_ATTEMPT_REGULATION_VERIFICATION_NEEDED"
    assert finding.metadata["regulation_unknown"] is True
    assert finding.metadata["verification_need"]["needed"] is True
    assert finding.metadata["verification_need"]["source_class"] == "official_only"


def test_canonical_rule_stale_regulation_is_not_current():
    result = _canonical_result(
        attempts=(_grounded_attempt(),),
        regulation=_regulation(temporal="expired"),
    )
    finding = result.findings[0]
    assert finding.code == "EXAM_ATTEMPT_REGULATION_VERIFICATION_NEEDED"
    assert finding.metadata["regulation_stale"] is True


def test_canonical_rule_failed_grade_without_consumption_does_not_increment():
    result = _canonical_result(
        attempts=(_grounded_attempt(status="not_consumed"),),
        regulation=_regulation(max_attempts=1),
    )
    finding = result.findings[0]
    assert finding.metadata["consumed_attempts"] == 0
    assert finding.metadata["failed_grade_not_consumed"] is True


def test_canonical_rule_complete_ordinary_evidence_increments_count():
    result = _canonical_result(
        attempts=(_grounded_attempt(outcome="passed"),),
        regulation=_regulation(max_attempts=1),
    )
    finding = result.findings[0]
    assert finding.metadata["consumed_attempts"] == 1
    assert finding.metadata["within_limits"] is True


def test_canonical_rule_reassessment_remains_separate_from_ordinary():
    result = _canonical_result(
        attempts=(
            _grounded_attempt(attempt_id="ordinary", outcome="failed"),
            _grounded_attempt(
                attempt_id="reassessment",
                kind="reassessment",
                outcome="failed",
            ),
        ),
        regulation=_regulation(max_attempts=1),
    )
    finding = result.findings[0]
    assert finding.metadata["consumed_attempts"] == 1
    assert finding.metadata["reassessment_count"] == 1


def test_canonical_rule_missing_attempt_limit_remains_unknown_and_verifies():
    result = _canonical_result(
        attempts=(_grounded_attempt(),),
        regulation=_regulation(max_attempts=None),
    )
    finding = result.findings[0]
    assert finding.code == "EXAM_ATTEMPT_REGULATION_VERIFICATION_NEEDED"
    assert finding.metadata["max_attempts"] is None
    assert finding.metadata["limit_unknown"] is True
    assert finding.metadata["within_limits"] is False
    assert finding.metadata["limit_exceeded"] is False


@pytest.mark.parametrize(
    "max_attempts",
    ("abc", -1, 0, 1.5, True),
)
def test_canonical_rule_malformed_attempt_limit_remains_unknown_without_raising(
    max_attempts,
):
    result = _canonical_result(
        attempts=(_grounded_attempt(),),
        regulation=_regulation(max_attempts=max_attempts),
    )
    finding = result.findings[0]
    assert finding.code == "EXAM_ATTEMPT_REGULATION_VERIFICATION_NEEDED"
    assert finding.metadata["max_attempts"] is None
    assert finding.metadata["limit_unknown"] is True
    assert finding.metadata["within_limits"] is False
    assert finding.metadata["limit_exceeded"] is False


def test_non_finite_decimal_attempt_limit_remains_unknown_without_raising():
    result = evaluate_exam_attempt(
        attempts=(_attempt(),),
        max_attempts=Decimal("Infinity"),
    )
    assert result["max_attempts"] is None
    assert result["limit_unknown"] is True
    assert result["within_limits"] is False
    assert result["limit_exceeded"] is False


@pytest.mark.parametrize("kind", ("mystery", None))
def test_canonical_rule_unknown_attempt_kind_is_not_counted_as_ordinary(kind):
    result = _canonical_result(
        attempts=(_grounded_attempt(kind=kind),),
        regulation=_regulation(max_attempts=1),
    )
    finding = result.findings[0]
    assert finding.code == "EXAM_ATTEMPT_REGULATION_VERIFICATION_NEEDED"
    assert finding.metadata["consumed_attempts"] == 0
    assert finding.metadata["unknown_attempts"] == 1
    assert finding.metadata["attempt_evidence_unknown"] is True
    assert finding.metadata["within_limits"] is False


def test_canonical_rule_non_mapping_attempt_evidence_remains_unknown():
    result = _canonical_result(
        attempts=("opaque-attempt",),
        regulation=_regulation(max_attempts=1),
    )
    finding = result.findings[0]
    assert finding.code == "EXAM_ATTEMPT_REGULATION_VERIFICATION_NEEDED"
    assert finding.metadata["consumed_attempts"] == 0
    assert finding.metadata["unknown_attempts"] == 1
    assert finding.metadata["attempt_evidence_unknown"] is True
    assert finding.metadata["within_limits"] is False


# ── V7-B4: malformed collection-shaped metadata must not leak TypeError; ─────
# ── the rule must degrade to a conservative verification-needed result. ───────


def test_canonical_rule_scalar_attempts_collection_does_not_crash():
    """A scalar ``attempts`` value (not a list/tuple) must not raise TypeError
    and must not fabricate consumed attempts or a limit exceedance."""
    result = _canonical_result(attempts=7, regulation=_regulation(max_attempts=1))
    assert result.status is not None
    finding = result.findings[0]
    assert finding.code != "EXAM_ATTEMPT_EVALUATED"
    assert finding.metadata["attempt_evidence_unknown"] is True
    assert finding.metadata["attempts_malformed"] is True
    assert finding.metadata["within_limits"] is False
    assert finding.metadata["consumed_attempts"] == 0
    assert finding.metadata["limit_exceeded"] is False


@pytest.mark.parametrize(
    "malformed",
    (7, "bad", {"unexpected": "mapping"}),
)
def test_canonical_rule_malformed_attempts_remain_unknown(malformed):
    """Malformed attempts evidence is not authoritative zero-attempt evidence
    and cannot produce a definite evaluated finding."""
    result = _canonical_result(attempts=malformed, regulation=_regulation(max_attempts=1))
    finding = result.findings[0]
    assert result.status is ReasoningRuleResultStatus.APPLIED
    assert finding.code != "EXAM_ATTEMPT_EVALUATED"
    assert finding.metadata["attempt_evidence_unknown"] is True
    assert finding.metadata["attempts_malformed"] is True
    assert finding.metadata["within_limits"] is False


def test_canonical_rule_empty_attempts_remain_valid_zero_attempts():
    """A valid empty attempts collection remains legitimate zero-attempt
    evidence rather than being treated as malformed."""
    result = _canonical_result(attempts=[], regulation=_regulation(max_attempts=1))
    finding = result.findings[0]
    assert finding.code == "EXAM_ATTEMPT_EVALUATED"
    assert finding.metadata["attempts_malformed"] is False
    assert finding.metadata["attempt_evidence_unknown"] is False
    assert finding.metadata["within_limits"] is True
# ── V9-B3.2: strict ExamAttempt grounding.  Truthy != grounded. ──────────────


def _ungrounded_regulation():
    return {
        "id": "reg-1",
        "source_reference": "regulation-1",
        "source_class": "regulation",
        "temporal": "valid",
        "grounded": "false",
        "max_attempts": 1,
    }


def test_canonical_rule_ungrounded_regulation_yields_no_within_limits():
    """A regulation with ``grounded="false"`` is not grounding; the attempt
    limit cannot be evaluated as authoritatively within limits."""
    result = _canonical_result(
        attempts=(_grounded_attempt(),),
        regulation=_ungrounded_regulation(),
    )
    finding = result.findings[0]
    assert finding.code != "EXAM_ATTEMPT_EVALUATED"
    assert finding.code == "EXAM_ATTEMPT_REGULATION_VERIFICATION_NEEDED"
    assert finding.metadata["regulation_unknown"] is True
    assert finding.metadata["within_limits"] is False


def test_canonical_rule_ungrounded_attempt_evidence_is_unknown():
    """An attempt with ``grounded="false"`` is malformed trust evidence and must
    not produce a within-limits strong conclusion from the flag."""
    attempt = _grounded_attempt()
    attempt["grounded"] = "false"
    result = _canonical_result(
        attempts=(attempt,),
        regulation=_regulation(max_attempts=1),
    )
    finding = result.findings[0]
    assert finding.code != "EXAM_ATTEMPT_EVALUATED"
    assert finding.code == "EXAM_ATTEMPT_REGULATION_VERIFICATION_NEEDED"
    assert finding.metadata["attempt_evidence_unknown"] is True
    assert finding.metadata["within_limits"] is False


def test_canonical_rule_strict_grounded_true_attempt_within_limits():
    """The positive regression: literal ``grounded=True`` attempt evidence works."""
    result = _canonical_result(
        attempts=(_grounded_attempt(),),
        regulation=_regulation(max_attempts=1),
    )
    finding = result.findings[0]
    assert finding.code == "EXAM_ATTEMPT_EVALUATED"
    assert finding.metadata["within_limits"] is True
