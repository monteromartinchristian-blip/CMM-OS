"""Tests for Phase 10.22 University Domain reasoning rules.

Covers the ten rules, the attribute-specific source authority (never a global
ranking), the fail-closed material contradiction path, the Academic State vs
Personal Memory separation, the performance != capacity boundary, Academic
Integrity Mode C (permissive by default), and decision support that never
adopts a decision.
"""

from __future__ import annotations

from datetime import datetime, timezone

from cmm.cognitive.enums import ReasoningRuleResultStatus
from cmm.cognitive.reasoning_rule_contracts import ReasoningRuleContext
from cmm.domains.university import build_university_rules
from cmm.domains.university.catalog import CANONICAL_UNIVERSITY_RULE_IDS
from cmm.domains.university.rules import (
    check_ects_consistency,
    evaluate_academic_contradiction,
    evaluate_academic_dependency,
    evaluate_academic_workload,
    evaluate_deadline,
    evaluate_exam_attempt,
    evaluate_performance_capacity,
    resolve_source_authority_by_attribute,
)

T = datetime(2026, 8, 1, tzinfo=timezone.utc)


def _context(**metadata) -> ReasoningRuleContext:
    return ReasoningRuleContext(
        reasoning_id="rid",
        timestamp=T,
        active_domains=("domain:university",),
        primary_domain="domain:university",
        metadata=metadata,
    )


def _by_id():
    return {rule.definition.id: rule for rule in build_university_rules()}


def test_ten_rules_and_canonical_order():
    rules = build_university_rules()
    assert len(rules) == 10
    ids = [rule.definition.id for rule in rules]
    assert ids == list(CANONICAL_UNIVERSITY_RULE_IDS)
    assert ids == sorted(ids)


def test_source_authority_preserved_by_attribute():
    """Source authority is resolved per-attribute; a global naive ranking is
    never applied."""
    rules = _by_id()
    rule = rules["university.academic_source_authority"]
    result = rule.evaluate(
        _context(
            academic_claims=[
                {
                    "id": "c1",
                    "attribute": "grade",
                    "source_type": "official",
                    "supplied_attributes": ("grade",),
                },
                {
                    "id": "c2",
                    "attribute": "grade",
                    "source_type": "user_reported",
                    "supplied_attributes": ("grade",),
                },
            ]
        )
    )
    assert result.status is ReasoningRuleResultStatus.APPLIED
    assert any(
        finding.code == "ATTRIBUTE_AUTHORITY"
        and finding.metadata["source_type"] == "official"
        for finding in result.findings
    )


def test_source_authority_does_not_compete_for_unsupplied_attribute():
    """A source that does not supply an attribute never competes for it."""
    resolved = resolve_source_authority_by_attribute(
        attribute="grade",
        sources=(
            {"source_id": "s1", "source_type": "official", "supplied_attributes": ("grade",)},
            {"source_id": "s2", "source_type": "official", "supplied_attributes": ("other",)},
        ),
    )
    assert resolved["authority"] == "official"
    assert len(resolved["matched_sources"]) == 1
    assert resolved["matched_sources"][0]["source_id"] == "s1"


def test_material_contradiction_fails_closed():
    """A decision-critical contradiction that cannot be resolved by authority
    blocks reasoning (fail-closed).  Contradiction is derived from the claims,
    not from caller booleans."""
    rules = _by_id()
    rule = rules["university.academic_contradiction"]
    result = rule.evaluate(
        _context(
            contradiction_statements=[
                {
                    "id": "a",
                    "attribute": "assignment_deadline",
                    "value": "2026-01-18",
                    "source_class": "specific_official_call",
                    "specificity": "specific",
                    "critical": True,
                },
                {
                    "id": "b",
                    "attribute": "assignment_deadline",
                    "value": "2026-01-17",
                    "source_class": "specific_official_call",
                    "specificity": "specific",
                    "critical": True,
                },
            ]
        )
    )
    assert result.status is ReasoningRuleResultStatus.BLOCKED
    assert result.escalation is not None
    assert result.escalation.code == "MATERIAL_CONTRADICTION_BLOCKED"
    assert any(
        finding.code == "MATERIAL_CONTRADICTION_UNRESOLVED"
        for finding in result.findings
    )


def test_resolved_contradiction_allows_proceeding():
    """Compatible claims (no unresolved conflict) proceed."""
    rule = _by_id()["university.academic_contradiction"]
    result = rule.evaluate(
        _context(
            contradiction_statements=[
                {"id": "a", "attribute": "grade", "value": "B"},
                {"id": "b", "attribute": "exam_date", "value": "2026-01-17"},
            ]
        )
    )
    assert result.status is ReasoningRuleResultStatus.APPLIED
    assert any(
        finding.code == "CONTRADICTION_STATE"
        for finding in result.findings
    )


def test_performance_never_capacity():
    """Observed academic performance is a fact about output, never a measure of
    intellectual capacity."""
    rules = _by_id()
    rule = rules["university.observed_performance_capacity"]
    result = rule.evaluate(
        _context(
            performance_observation={
                "ref": "res-1",
                "outcome": "below_average",
            }
        )
    )
    assert result.status is ReasoningRuleResultStatus.APPLIED
    assert result.escalation is not None
    assert result.escalation.code == "CAPACITY_INFERENCE_BLOCKED"
    assert any(
        finding.code == "PERFORMANCE_NOT_CAPACITY" for finding in result.findings
    )
    assert all(
        finding.metadata.get("capacity_inferred") is False
        for finding in result.findings
    )


def test_integrity_mode_c_permissive_by_default():
    """Academic Integrity Mode C is permissive by default; the domain does not
    police academic conduct."""
    rules = _by_id()
    rule = rules["university.academic_integrity"]
    result = rule.evaluate(_context(integrity={"mode": "mode_c"}))
    assert result.status is ReasoningRuleResultStatus.APPLIED
    assert any(
        finding.code == "INTEGRITY_MODE_PRESERVED"
        and finding.metadata["mode"] == "mode_c"
        for finding in result.findings
    )


def test_integrity_mode_defaults_to_c():
    rule = _by_id()["university.academic_integrity"]
    result = rule.evaluate(_context(integrity={}))
    assert result.status is ReasoningRuleResultStatus.APPLIED
    assert any(
        finding.code == "INTEGRITY_MODE_PRESERVED"
        and finding.metadata["mode"] == "mode_c"
        for finding in result.findings
    )


def test_integrity_unknown_mode_blocked():
    rule = _by_id()["university.academic_integrity"]
    result = rule.evaluate(_context(integrity={"mode": "mode_x"}))
    assert result.status is ReasoningRuleResultStatus.BLOCKED
    assert any(
        finding.code == "INTEGRITY_MODE_REJECTED" for finding in result.findings
    )


def test_decision_support_never_adopts():
    """Decision support compares options; no academic decision is adopted,
    persisted, or executed."""
    rules = _by_id()
    rule = rules["university.academic_decision_preservation"]
    result = rule.evaluate(_context(decision_support={"options": (1, 2)}))
    assert result.status is ReasoningRuleResultStatus.APPLIED
    assert any(
        finding.code == "DECISION_NOT_ADOPTED"
        and finding.metadata["adopted_decision"] is False
        and finding.metadata["requires_user_confirmation"] is True
        for finding in result.findings
    )


def test_deadline_never_auto_scheduled():
    rule = _by_id()["university.academic_deadline"]
    result = rule.evaluate(
        _context(
            deadline={
                "value": "2026-09-15",
                "source_class": "official_publication",
                "provenance": "grounded",
                "temporal": "valid",
                "effective_date": "2026-09-15",
            }
        )
    )
    assert result.status is ReasoningRuleResultStatus.APPLIED
    assert any(
        finding.code == "DEADLINE_FACT" for finding in result.findings
    )
    assert all(
        finding.metadata.get("auto_scheduled") is not True
        for finding in result.findings
    )


def test_deadline_undergrounded_triggers_verification_need():
    """A bare date string with no grounding is not a confirmed deadline and
    raises a verification need rather than being treated as authoritative."""
    rule = _by_id()["university.academic_deadline"]
    result = rule.evaluate(_context(deadline={"value": "2026-09-15"}))
    assert result.status is ReasoningRuleResultStatus.APPLIED
    assert any(
        finding.code == "DEADLINE_VERIFICATION_NEEDED"
        for finding in result.findings
    )


def test_ects_double_counting_blocks_completion():
    rule = _by_id()["university.ects_consistency"]
    result = rule.evaluate(
        _context(
            ects={
                "completed": 100,
                "recognized": 100,
                "required": 180,
                "double_counted": ("subj-a",),
            }
        )
    )
    assert result.status is ReasoningRuleResultStatus.APPLIED
    assert any(
        finding.code == "ECTS_COMPLETION_BLOCKED" for finding in result.findings
    )


def test_exam_attempt_limit_reported_not_acted_on():
    rule = _by_id()["university.exam_attempt"]
    result = rule.evaluate(
        _context(
                exam_attempt={
                    "attempts": (
                        {
                            "id": "attempt-1",
                            "exam_id": "exam-1",
                            "date": "2026-07-01",
                            "source_reference": "record-1",
                            "kind": "ordinary",
                            "outcome": "failed",
                            "grounded": True,
                            "status": "consumed",
                        },
                        {
                            "id": "attempt-2",
                            "exam_id": "exam-1",
                            "date": "2026-07-02",
                            "source_reference": "record-2",
                            "kind": "ordinary",
                            "outcome": "failed",
                            "grounded": True,
                            "status": "consumed",
                        },
                        {
                            "id": "attempt-3",
                            "exam_id": "exam-1",
                            "date": "2026-07-03",
                            "source_reference": "record-3",
                            "kind": "ordinary",
                            "outcome": "failed",
                            "grounded": True,
                            "status": "consumed",
                        },
                        {
                            "id": "attempt-4",
                            "exam_id": "exam-1",
                            "date": "2026-07-04",
                            "source_reference": "record-4",
                            "kind": "ordinary",
                            "outcome": "failed",
                            "grounded": True,
                            "status": "consumed",
                        },
                    ),
                    "regulation": {
                        "id": "reg-1",
                        "source_reference": "regulation-1",
                        "source_class": "regulation",
                        "temporal": "valid",
                        "grounded": True,
                        "max_attempts": 3,
                    },
                    "max_attempts": 3,
                }
        )
    )
    assert result.status is ReasoningRuleResultStatus.APPLIED
    assert any(
        finding.code == "EXAM_ATTEMPT_LIMIT_EXCEEDED" for finding in result.findings
    )


def test_workload_infeasibility_blocks_pipeline():
    rule = _by_id()["university.academic_workload"]
    result = rule.evaluate(
        _context(
            workload={
                "total_ect": 60,
                "full_time_ect": 30,
                "health_constraint": {"functional_cap_ect": 20, "authorized": True},
            }
        )
    )
    assert result.status is ReasoningRuleResultStatus.APPLIED
    assert any(
        finding.code == "WORKLOAD_INFEASIBLE" for finding in result.findings
    )
    assert all(
        finding.metadata.get("clinical_details_consumed") is False
        for finding in result.findings
    )


def test_dependency_blocked_no_auto_enrolment():
    rule = _by_id()["university.academic_dependency"]
    result = rule.evaluate(
        _context(
            dependency={
                "subject_id": "subj-2",
                "prerequisites": (
                    {"id": "subj-1", "passed": False},
                ),
            }
        )
    )
    assert result.status is ReasoningRuleResultStatus.APPLIED
    assert any(
        finding.code == "DEPENDENCY_BLOCKED"
        and "subj-1" in finding.references
        for finding in result.findings
    )


def test_not_applicable_when_no_metadata():
    rules = _by_id()
    for rule in rules.values():
        result = rule.evaluate(_context())
        assert result.status is ReasoningRuleResultStatus.NOT_APPLICABLE


def test_deterministic_helpers():
    # resolve_source_authority_by_attribute: per-attribute, official dominates.
    resolved = resolve_source_authority_by_attribute(
        attribute="grade",
        sources=(
            {"source_id": "s1", "source_type": "user_reported", "supplied_attributes": ("grade",)},
            {"source_id": "s2", "source_type": "official", "supplied_attributes": ("grade",)},
        ),
    )
    assert resolved["authority"] == "official"
    assert resolved["authority_resolved"] is True
    # An unsupplied attribute resolves to no authority.
    unresolved = resolve_source_authority_by_attribute(
        attribute="credit",
        sources=(
            {"source_id": "s1", "source_type": "official", "supplied_attributes": ("grade",)},
        ),
    )
    assert unresolved["authority_resolved"] is False

    # evaluate_academic_contradiction: material + unresolved fails closed.
    assert evaluate_academic_contradiction(statements=())["state"] == "unresolved"
    assert evaluate_academic_contradiction(
        statements=({"material": True, "unresolved": True},)
    )["state"] == "material"
    resolved_contradiction = evaluate_academic_contradiction(
        statements=({"material": False, "unresolved": False},)
    )
    assert resolved_contradiction["state"] == "resolved"

    # check_ects_consistency: reasons over credit buckets, never rewrites.
    clean = check_ects_consistency(completed=180, required=180)
    assert clean["satisfied"] is True
    assert clean["completion_determinable"] is True
    blocked = check_ects_consistency(
        completed=100, recognized=100, required=180, double_counted=("s1",)
    )
    assert blocked["completion_blocked"] is True
    assert blocked["satisfied"] is False

    # evaluate_exam_attempt: reports grounded attempts, never authorizes a
    # retake; reassessment and non-consumed attempts do not count.
    within = evaluate_exam_attempt(
        attempts=(
            {"kind": "ordinary", "outcome": "failed", "grounded": True, "status": "consumed"},
            {"kind": "reassessment", "outcome": "failed", "grounded": True, "status": "consumed"},
        ),
        max_attempts=1,
    )
    assert within["within_limits"] is True
    assert within["reassessment_count"] == 1
    exceeded = evaluate_exam_attempt(
        attempts=(
            {"kind": "ordinary", "outcome": "failed", "grounded": True, "status": "consumed"},
            {"kind": "ordinary", "outcome": "failed", "grounded": True, "status": "consumed"},
            {"kind": "ordinary", "outcome": "failed", "grounded": True, "status": "consumed"},
            {"kind": "ordinary", "outcome": "failed", "grounded": True, "status": "consumed"},
        ),
        max_attempts=3,
    )
    assert exceeded["limit_exceeded"] is True

    # evaluate_academic_workload: staged pipeline, clinical details never
    # consumed.
    feasible = evaluate_academic_workload(
        total_ect=30,
        full_time_ect=30,
        hard_constraints=({"id": "hc-1", "satisfied": True},),
    )
    assert feasible["feasible"] is True
    assert feasible["clinical_details_consumed"] is False
    infeasible = evaluate_academic_workload(
        total_ect=40,
        full_time_ect=30,
        health_constraint={"functional_cap_ect": 20, "authorized": True},
    )
    assert infeasible["feasible"] is False
    assert infeasible["stage"] == "feasibility"

    # evaluate_academic_dependency: grounded-only, never auto-enrols.
    dep = evaluate_academic_dependency(
        subject_id="subj-2",
        dependencies=({"id": "subj-1", "grounded_passed": True, "status": "passed"},),
    )
    assert dep["dependency_blocked"] is False
    assert dep["satisfied_prerequisites"] == ("subj-1",)
    # A caller-claimed ``caller_passed`` without grounding is not authoritative.
    ungrounded = evaluate_academic_dependency(
        subject_id="subj-2",
        dependencies=({"id": "subj-1", "caller_passed": True},),
    )
    assert ungrounded["dependency_blocked"] is True
    assert ungrounded["satisfied_prerequisites"] == ()
    assert "subj-1" in ungrounded["caller_passed_ignored"]

    # evaluate_performance_capacity: performance never establishes capacity.
    perf = evaluate_performance_capacity(
        performance_observation={"ref": "res-1", "outcome": "below_average"}
    )
    assert perf["performance_observed"] is True
    assert perf["capacity_inferred"] is False

    # evaluate_deadline: a fact, never auto-scheduled.
    assert evaluate_deadline(deadline="2026-09-15")["deadline_present"] is True
    assert evaluate_deadline(deadline="2026-09-15")["auto_scheduled"] is False
    assert evaluate_deadline(deadline="")["deadline_present"] is False
