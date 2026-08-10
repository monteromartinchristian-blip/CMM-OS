"""Phase 10.22 — B6: Academic Dependencies (grounded, caller not authoritative).

The audit found the previous implementation trusted a caller `passed` boolean
as authoritative.  Dependency satisfaction must be grounded: only grounded
evidence of passing satisfies a prerequisite; a caller-claimed `passed` with no
grounding is not authoritative; credit/TFG sequencing still blocks; and an
unknown prerequisite status remains unresolved (never silently treated as
satisfied).
"""

from __future__ import annotations

from datetime import datetime, timezone

from cmm.cognitive.enums import ReasoningRuleResultStatus
from cmm.cognitive.reasoning_rule_contracts import ReasoningRuleContext
from cmm.domains.university import build_university_rules
from cmm.domains.university.rules import evaluate_academic_dependency

T = datetime(2026, 8, 1, tzinfo=timezone.utc)


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


def _academic_record(subject_id, status, *, ects=0, source="record-1", grounded=True):
    return {
        "subject_id": subject_id,
        "status": status,
        "ects": ects,
        "grounded": grounded,
        "source_reference": source,
        "temporal": "valid",
    }


def _canonical_result(dependency):
    rule = {
        r.definition.id: r
        for r in build_university_rules()
    }["university.academic_dependency"]
    context = ReasoningRuleContext(
        reasoning_id="dependency-production",
        timestamp=T,
        active_domains=("domain:university",),
        primary_domain="domain:university",
        metadata={"dependency": dependency},
    )
    return rule.evaluate(context)


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


def test_canonical_rule_caller_fabricated_pass_does_not_establish_prerequisite():
    result = _canonical_result(
        {
            "subject_id": "subj-2",
            "prerequisites": (
                {
                    "id": "subj-1",
                    "passed": True,
                    "grounded_passed": True,
                },
            ),
        }
    )
    finding = result.findings[0]
    assert result.status is ReasoningRuleResultStatus.APPLIED
    assert finding.code == "DEPENDENCY_BLOCKED"
    assert "subj-1" in finding.metadata["unknown_prerequisites"]



def test_canonical_rule_grounded_subject_state_satisfies_prerequisite():
    result = _canonical_result(
        {
            "subject_id": "subj-2",
            "prerequisites": ({"id": "subj-1", "kind": "subject"},),
            "academic_records": (
                _academic_record("subj-1", "passed", source="record-pass"),
            ),
        }
    )
    finding = result.findings[0]
    assert finding.code == "DEPENDENCY_SATISFIED"
    assert finding.metadata["satisfied_prerequisites"] == ("subj-1",)


def test_canonical_rule_credit_threshold_uses_grounded_completed_records():
    result = _canonical_result(
        {
            "subject_id": "tfg",
            "prerequisites": (
                {"id": "degree-credits", "kind": "credit_threshold", "required_credits": 180},
            ),
            "academic_records": tuple(
                _academic_record(f"subject-{i}", "completed", ects=29)
                for i in range(6)
            ),
        }
    )
    finding = result.findings[0]
    assert finding.code == "DEPENDENCY_BLOCKED"
    assert finding.metadata["credit_thresholds"]["degree-credits"]["completed"] == 174


def test_canonical_rule_pending_recognition_is_conditional_not_currently_satisfied():
    result = _canonical_result(
        {
            "subject_id": "tfg",
            "prerequisites": (
                {"id": "degree-credits", "kind": "tfg_eligibility", "required_credits": 180},
            ),
            "academic_records": (
                _academic_record("completed", "completed", ects=174),
                _academic_record("pending", "pending_recognition", ects=6),
            ),
        }
    )
    finding = result.findings[0]
    threshold = finding.metadata["credit_thresholds"]["degree-credits"]
    assert finding.code == "DEPENDENCY_BLOCKED"
    assert threshold["status"] == "conditional"
    assert threshold["scenario_if_recognized"] is True


def test_canonical_rule_conditional_prerequisite_is_in_blocked_ids():
    result = _canonical_result(
        {
            "subject_id": "tfg",
            "prerequisites": (
                {"id": "degree-credits", "kind": "credit_threshold", "required_credits": 180},
            ),
            "academic_records": (
                _academic_record("completed", "completed", ects=174),
                _academic_record("pending", "pending_recognition", ects=6),
            ),
        }
    )
    finding = result.findings[0]
    assert finding.metadata["conditional_prerequisites"] == ("degree-credits",)
    assert "degree-credits" in finding.references


def test_canonical_rule_unknown_dependency_remains_unresolved():
    result = _canonical_result(
        {
            "subject_id": "subj-2",
            "prerequisites": ({"id": "subj-1", "kind": "subject"},),
            "academic_records": (),
        }
    )
    finding = result.findings[0]
    assert finding.code == "DEPENDENCY_BLOCKED"
    assert finding.metadata["unknown_prerequisites"] == ("subj-1",)
