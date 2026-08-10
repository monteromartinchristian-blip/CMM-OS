"""Phase 10.22 — B4: ECTS Consistency (credit buckets, no double-counting).

The audit found the previous implementation compared ECTS×hours against a
declared workload as the core consistency check.  That comparison is removed
as the core.  ECTS reasoning must instead reason over distinct credit buckets
(completed / recognized / enrolled / planned / pending-recognition / required),
never double-count a credit, never silently sum contradictory buckets, and
block a completion conclusion when a critical requirement is uncertain.
"""

from __future__ import annotations

from datetime import datetime, timezone

from cmm.cognitive.enums import ReasoningRuleResultStatus
from cmm.cognitive.reasoning_rule_contracts import ReasoningRuleContext
from cmm.domains.university import build_university_rules
from cmm.domains.university.rules import check_ects_consistency

T = datetime(2026, 8, 1, tzinfo=timezone.utc)


def _record(subject_id, ects, state, *, source="record-1", **extra):
    return {
        "subject_id": subject_id,
        "ects": ects,
        "state": state,
        "grounded": True,
        "source_reference": source,
        "temporal": "valid",
        **extra,
    }


def _canonical_result(*, records=(), degree_requirement=None, **legacy):
    rule = {
        r.definition.id: r
        for r in build_university_rules()
    }["university.ects_consistency"]
    context = ReasoningRuleContext(
        reasoning_id="ects-production",
        timestamp=T,
        active_domains=("domain:university",),
        primary_domain="domain:university",
        metadata={
            "ects": {
                **legacy,
                "records": records,
                "degree_requirement": degree_requirement,
            }
        },
    )
    return rule.evaluate(context)


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


def test_canonical_rule_missing_requirement_stays_unknown():
    result = _canonical_result(
        records=tuple(_record(f"subject-{i}", 30, "completed") for i in range(6)),
        degree_requirement=None,
    )
    finding = result.findings[0]
    assert result.status is ReasoningRuleResultStatus.APPLIED
    assert finding.metadata["required"] is None
    assert finding.metadata["satisfied"] is False
    assert finding.metadata["required_known"] is False
    assert result.gaps
    assert result.gaps[0].metadata["verification_need"]["needed"] is True


def test_canonical_rule_legacy_aggregate_cannot_confirm_completion():
    result = _canonical_result(completed=180, required=180)
    finding = result.findings[0]
    assert finding.code == "ECTS_COMPLETION_BLOCKED"
    assert finding.metadata["satisfied"] is False
    assert finding.metadata["required_known"] is False
    assert finding.metadata["credit_state_sufficiently_grounded"] is False
    assert finding.metadata["verification_need"]["needed"] is True


def test_canonical_rule_same_subject_completed_and_recognized_is_not_double_counted():
    result = _canonical_result(
        records=(
            _record("subject-a", 6, "completed", source="record-complete"),
            _record("subject-a", 6, "recognized", source="record-recognized"),
        ),
        degree_requirement={"required_ects": 6, "grounded": True, "source_reference": "degree-1"},
    )
    finding = result.findings[0]
    assert finding.code == "ECTS_COMPLETION_BLOCKED"
    assert finding.metadata["double_counting"] is True
    assert "subject-a" in finding.metadata["double_counted"]
    assert finding.metadata["recognized_total"] == 12


def test_canonical_rule_enrolled_credits_do_not_count_as_completed():
    result = _canonical_result(
        records=(_record("subject-enrolled", 6, "enrolled"),),
        degree_requirement={"required_ects": 6, "grounded": True, "source_reference": "degree-1"},
    )
    finding = result.findings[0]
    assert finding.metadata["completed"] == 0
    assert finding.metadata["enrolled"] == 6
    assert finding.metadata["satisfied"] is False


def test_canonical_rule_pending_recognition_is_only_conditional():
    result = _canonical_result(
        records=(
            _record("subject-complete", 174, "completed"),
            _record("subject-pending", 6, "pending_recognition"),
        ),
        degree_requirement={"required_ects": 180, "grounded": True, "source_reference": "degree-1"},
    )
    finding = result.findings[0]
    assert finding.metadata["recognized_total"] == 174
    assert finding.metadata["pending_recognition"] == 6
    assert finding.metadata["satisfied"] is False
    assert finding.metadata["scenario_if_recognized"] == 180


def test_canonical_rule_contradictory_current_credit_states_block_completion():
    result = _canonical_result(
        records=(
            _record("subject-a", 6, "completed", source="pass"),
            _record("subject-a", 6, "failed", source="fail"),
        ),
        degree_requirement={"required_ects": 6, "grounded": True, "source_reference": "degree-1"},
    )
    finding = result.findings[0]
    assert finding.code == "ECTS_COMPLETION_BLOCKED"
    assert finding.metadata["contradiction"] is True
    assert "subject-a" in finding.metadata["contradictory"]


def test_canonical_rule_grounded_records_can_confirm_completion():
    result = _canonical_result(
        records=tuple(_record(f"subject-{i}", 30, "completed") for i in range(6)),
        degree_requirement={"required_ects": 180, "grounded": True, "source_reference": "degree-1"},
    )
    finding = result.findings[0]
    assert result.status is ReasoningRuleResultStatus.APPLIED
    assert finding.code == "ECTS_REQUIREMENT_SATISFIED"
    assert finding.metadata["recognized_total"] == 180
