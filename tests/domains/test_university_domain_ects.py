"""Phase 10.22 — B4: ECTS Consistency (credit buckets, no double-counting).

The audit found the previous implementation compared ECTS×hours against a
declared workload as the core consistency check.  That comparison is removed
as the core.  ECTS reasoning must instead reason over distinct credit buckets
(completed / recognized / enrolled / planned / pending-recognition / required),
never double-count a credit, never silently sum contradictory buckets, and
block a completion conclusion when a critical requirement is uncertain.
"""

from __future__ import annotations

from cmm.domains.university.rules import check_ects_consistency


def test_recognized_credits_satisfy_requirement():
    """Completed plus officially recognized credits count toward the degree."""
    result = check_ects_consistency(
        completed=150,
        recognized=30,
        required=180,
    )
    assert result["satisfied"] is True
    assert result["completion_determinable"] is True
    assert result["completion_blocked"] is False


def test_planned_credits_do_not_count_yet():
    """Enrolled/planned credits are not yet earned and do not satisfy a
    requirement that is being assessed."""
    result = check_ects_consistency(
        completed=100,
        enrolled=30,
        planned=20,
        required=180,
    )
    assert result["satisfied"] is False
    assert result["recognized_total"] == 100


def test_pending_recognition_is_not_fully_recognized():
    """Credits pending recognition stay in a separate bucket and are not
    silently added to the recognized total."""
    result = check_ects_consistency(
        completed=100,
        pending_recognition=50,
        required=180,
    )
    assert result["recognized_total"] == 100
    assert result["satisfied"] is False


def test_double_counting_is_flagged_not_silently_summed():
    """A credit present in more than one earned bucket is double-counted and
    flagged rather than summed twice."""
    result = check_ects_consistency(
        completed=100,
        recognized=100,
        required=180,
        double_counted=("subj-a",),
    )
    assert result["double_counting"] is True
    assert result["satisfied"] is False
    assert result["completion_determinable"] is False


def test_contradictory_buckets_not_silently_reconciled():
    """When buckets contradict each other the result is flagged; the values are
    never silently summed into a confident total."""
    result = check_ects_consistency(
        completed=120,
        recognized=40,
        required=180,
        contradictory=("subj-b",),
    )
    assert result["contradiction"] is True
    assert result["completion_determinable"] is False


def test_critical_requirement_uncertain_blocks_completion():
    """A completion conclusion is blocked while a critical requirement's status
    is uncertain."""
    result = check_ects_consistency(
        completed=180,
        required=180,
        critical_requirement_uncertain=True,
    )
    assert result["completion_blocked"] is True
    assert result["satisfied"] is False


def test_clean_noncritical_case_is_determinable():
    result = check_ects_consistency(
        completed=180,
        required=180,
    )
    assert result["completion_determinable"] is True
    assert result["completion_blocked"] is False
    assert result["satisfied"] is True
    assert result["double_counting"] is False
    assert result["contradiction"] is False