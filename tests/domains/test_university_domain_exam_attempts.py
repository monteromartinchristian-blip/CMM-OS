"""Phase 10.22 — B5: Exam Attempts (grounded, ordinary≠reassessment).

The audit found the previous implementation counted a raw ``attempt_count`` and
treated ``passed`` as a boolean.  Attempt semantics must be grounded: an
ordinary attempt is distinct from a reassessment attempt; a failed grade does
not by itself consume an attempt; attempt counts must be grounded (never
caller-claimed); canceled or waived attempts do not count against the limit;
and the regulation in force governs the limit.
"""

from __future__ import annotations

from cmm.domains.university.rules import evaluate_exam_attempt


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