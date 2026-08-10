"""Phase 10.22 — B6: Academic Dependencies (grounded, caller not authoritative).

The audit found the previous implementation trusted a caller `passed` boolean
as authoritative.  Dependency satisfaction must be grounded: only grounded
evidence of passing satisfies a prerequisite; a caller-claimed `passed` with no
grounding is not authoritative; credit/TFG sequencing still blocks; and an
unknown prerequisite status remains unresolved (never silently treated as
satisfied).
"""

from __future__ import annotations

from cmm.domains.university.rules import evaluate_academic_dependency


def _dep(
    dep_id,
    *,
    grounded_passed=False,
    caller_passed=False,
    status="unknown",
    kind="subject",
):
    return {
        "id": dep_id,
        "grounded_passed": grounded_passed,
        "caller_passed": caller_passed,
        "status": status,
        "kind": kind,
    }


def test_grounded_passed_prerequisite_satisfies():
    result = evaluate_academic_dependency(
        subject_id="subj-2",
        dependencies=(_dep("subj-1", grounded_passed=True, status="passed"),),
    )
    assert result["dependency_blocked"] is False
    assert result["satisfied_prerequisites"] == ("subj-1",)


def test_ungrounded_caller_passed_is_not_authoritative():
    """A caller claiming ``passed=True`` without grounding does not satisfy the
    prerequisite."""
    result = evaluate_academic_dependency(
        subject_id="subj-2",
        dependencies=(_dep("subj-1", caller_passed=True),),
    )
    assert result["dependency_blocked"] is True
    assert result["caller_passed_ignored"] == ("subj-1",)
    assert "subj-1" not in result["satisfied_prerequisites"]


def test_failed_prerequisite_blocks():
    result = evaluate_academic_dependency(
        subject_id="subj-2",
        dependencies=(_dep("subj-1", status="failed"),),
    )
    assert result["dependency_blocked"] is True
    assert "subj-1" in result["open_prerequisites"]


def test_unknown_prerequisite_remains_unresolved():
    """An unknown prerequisite status stays unresolved and is never treated as
    satisfied."""
    result = evaluate_academic_dependency(
        subject_id="subj-2",
        dependencies=(_dep("subj-1"),),
    )
    assert result["dependency_blocked"] is True
    assert "subj-1" in result["unknown_prerequisites"]
    assert "subj-1" not in result["satisfied_prerequisites"]


def test_mixed_prerequisites_only_grounded_pass_counts():
    result = evaluate_academic_dependency(
        subject_id="subj-2",
        dependencies=(
            _dep("subj-1", grounded_passed=True, status="passed"),
            _dep("subj-3", caller_passed=True),
        ),
    )
    assert result["satisfied_prerequisites"] == ("subj-1",)
    assert result["dependency_blocked"] is True


def test_tfg_prerequisite_blocks_like_subject():
    """TFG/credit sequencing operates like any prerequisite: an unsatisfied
    TFG blocks."""
    result = evaluate_academic_dependency(
        subject_id="degree",
        dependencies=(_dep("tfg", kind="tfg", status="pending"),),
    )
    assert result["dependency_blocked"] is True
    assert "tfg" in result["open_prerequisites"]


def test_grounded_tfg_passed_satisfies():
    result = evaluate_academic_dependency(
        subject_id="degree",
        dependencies=(_dep("tfg", kind="tfg", grounded_passed=True, status="passed"),),
    )
    assert result["dependency_blocked"] is False
    assert "tfg" in result["satisfied_prerequisites"]


def test_no_dependencies_is_blocked_false():
    result = evaluate_academic_dependency(subject_id="subj-2", dependencies=())
    assert result["dependency_blocked"] is False
    assert result["satisfied_prerequisites"] == ()