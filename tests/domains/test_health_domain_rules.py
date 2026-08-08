"""Tests for Phase 10.20 Health Domain reasoning rules."""

from __future__ import annotations

from datetime import datetime, timezone

from cmm.cognitive.enums import ReasoningRuleResultStatus
from cmm.cognitive.reasoning_rule_contracts import ReasoningRuleContext
from cmm.domains.health import build_health_rules
from cmm.domains.health.rules import (
    classify_clinical_statement,
    validate_diagnostic_claim,
)

T = datetime(2026, 8, 1, tzinfo=timezone.utc)


def _context(**metadata) -> ReasoningRuleContext:
    return ReasoningRuleContext(
        reasoning_id="rid",
        timestamp=T,
        active_domains=("domain:health",),
        primary_domain="domain:health",
        metadata=metadata,
    )


def _by_id(rules):
    return {rule.definition.id: rule for rule in rules}


def test_eight_rules_and_ids():
    rules = build_health_rules()
    assert len(rules) == 8
    ids = [rule.definition.id for rule in rules]
    assert ids == sorted(ids)


def test_symptom_diagnosis_rule_classifies_documented():
    rules = _by_id(build_health_rules())
    rule = rules["health.symptom_diagnosis_hypothesis"]
    result = rule.evaluate(
        _context(
            clinical_statements=[
                {"id": "s1", "documented": True, "diagnosis": True},
            ]
        )
    )
    assert result.status is ReasoningRuleResultStatus.APPLIED
    assert any(
        finding.code == "EPISTEMIC_CATEGORY"
        and "classified" in finding.message
        and "documented_diagnosis" in finding.message
        for finding in result.findings
    )


def test_symptom_diagnosis_rule_never_promotes_to_documented():
    """A hypothesis is never classified as a documented diagnosis."""
    rules = _by_id(build_health_rules())
    rule = rules["health.symptom_diagnosis_hypothesis"]
    result = rule.evaluate(
        _context(
            clinical_statements=[
                {"id": "s1", "diagnosis": True, "system_hypothesis": True},
            ]
        )
    )
    assert result.status is ReasoningRuleResultStatus.APPLIED
    assert any(
        finding.code == "EPISTEMIC_CATEGORY"
        and "system_hypothesis" in finding.message
        and "documented_diagnosis" not in finding.message
        for finding in result.findings
    )


def test_medication_temporal_relationship_not_causation():
    """A temporal association is recorded without claiming causation."""
    rules = _by_id(build_health_rules())
    rule = rules["health.medication_temporal_relationship"]
    result = rule.evaluate(
        _context(
            medication_relation={"medication": "medx", "symptom": "swell"},
        )
    )
    assert result.status is ReasoningRuleResultStatus.APPLIED
    assert any(
        finding.code == "TEMPORAL_ASSOCIATION_NOT_CAUSATION"
        for finding in result.findings
    )


def test_no_definitive_diagnosis_blocks_without_evidence():
    rules = _by_id(build_health_rules())
    rule = rules["health.no_definitive_diagnosis"]
    result = rule.evaluate(
        _context(diagnostic_claim={"evidence": False, "documented": False})
    )
    assert result.status is ReasoningRuleResultStatus.BLOCKED
    assert any(finding.code == "NO_DEFINITIVE_DIAGNOSIS" for finding in result.findings)


def test_no_definitive_diagnosis_allows_confirmed():
    rules = _by_id(build_health_rules())
    rule = rules["health.no_definitive_diagnosis"]
    result = rule.evaluate(
        _context(
            diagnostic_claim={
                "evidence": True,
                "documented": True,
                "confirmed": True,
            }
        )
    )
    assert result.status is ReasoningRuleResultStatus.APPLIED


def test_no_definitive_diagnosis_blocks_documented_without_confirmation():
    """Documented + evidence alone is NOT definitive; only explicit
    confirmation allows definitive presentation."""
    rules = _by_id(build_health_rules())
    rule = rules["health.no_definitive_diagnosis"]
    result = rule.evaluate(
        _context(diagnostic_claim={"evidence": True, "documented": True})
    )
    assert result.status is ReasoningRuleResultStatus.BLOCKED
    assert any(finding.code == "NO_DEFINITIVE_DIAGNOSIS" for finding in result.findings)


def test_provisional_documented_claim_remains_provisional():
    """A provisional diagnosis stays provisional even when documented+evidenced."""
    verdict = validate_diagnostic_claim(
        evidence=True, documented=True, provisional=True, confirmed=False
    )
    assert verdict["is_definitive"] is False
    assert verdict["may_present_as_definitive"] is False


def test_documented_evidence_without_confirmation_not_definitive():
    verdict = validate_diagnostic_claim(evidence=True, documented=True, confirmed=False)
    assert verdict["is_definitive"] is False
    assert verdict["may_present_as_definitive"] is False


def test_system_hypothesis_with_evidence_not_promoted():
    """A system hypothesis with evidence is not promoted to a definitive,
    documented diagnosis."""
    verdict = validate_diagnostic_claim(
        evidence=True, documented=False, confirmed=False
    )
    assert verdict["is_definitive"] is False
    assert verdict["supported_category"] == "system_hypothesis"


def test_explicit_confirmation_alone_may_allow_definitive():
    """Only an explicit confirmed/established status allows definitive
    presentation."""
    verdict = validate_diagnostic_claim(
        evidence=True, documented=True, confirmed=True, provisional=False
    )
    assert verdict["is_definitive"] is True
    assert verdict["may_present_as_definitive"] is True


def test_provenance_does_not_imply_documentary_diagnosis():
    """source origin != epistemic status: provenance alone (user_statement) must
    never classify a diagnosis as documented_diagnosis."""
    assert (
        classify_clinical_statement(
            provenance="user_statement",
            is_user_reported=True,
            is_diagnosis=True,
        )
        != "documented_diagnosis"
    )


def test_inference_provenance_does_not_promote_hypothesis():
    """Provenance of an inference must not promote a system hypothesis to a
    documented diagnosis."""
    assert (
        classify_clinical_statement(
            provenance="inference",
            is_diagnosis=True,
            is_system_hypothesis=True,
        )
        == "system_hypothesis"
    )


def test_user_possibility_stays_possibility_with_provenance():
    assert (
        classify_clinical_statement(
            provenance="user_statement",
            is_user_possibility=True,
        )
        == "user_possibility"
    )


def test_only_explicit_documentary_status_classifies_documented_diagnosis():
    """A diagnosis becomes documented_diagnosis only from an explicit documented
    flag, never from the presence of provenance alone."""
    assert (
        classify_clinical_statement(
            provenance="medical_record",
            is_diagnosis=True,
            is_documented=True,
        )
        == "documented_diagnosis"
    )
    # Provenance alone, without an explicit documented flag, must not.
    assert (
        classify_clinical_statement(provenance="medical_record", is_diagnosis=True)
        != "documented_diagnosis"
    )


def test_confirmed_flag_alone_cannot_make_claim_definitive():
    """confirmed=True with no documented status and no evidence is NOT
    definitive and MUST NOT be presentable as definitive."""
    verdict = validate_diagnostic_claim(
        evidence=False,
        documented=False,
        confirmed=True,
        provisional=False,
    )
    assert verdict["is_definitive"] is False
    assert verdict["may_present_as_definitive"] is False


def test_no_definitive_result_is_hypothesis_possibility_or_provisional():
    """No result may simultaneously be definitive and carry a hypothesis,
    possibility, or provisional category."""
    for category in ("system_hypothesis", "user_possibility", "provisional_diagnosis"):
        for confirmed in (True, False):
            verdict = validate_diagnostic_claim(
                evidence=True, documented=True, confirmed=confirmed, provisional=False
            )
            assert not (
                verdict["is_definitive"] is True
                and verdict["supported_category"] == category
            )


def test_confirmed_plus_provisional_remains_non_definitive():
    verdict = validate_diagnostic_claim(
        evidence=True, documented=True, confirmed=True, provisional=True
    )
    assert verdict["is_definitive"] is False
    assert verdict["may_present_as_definitive"] is False


def test_confirmed_documented_evidenced_diagnosis_may_be_represented():
    """A confirmed diagnosis grounded in documented clinical evidence may be
    represented as definitive (confirmed AND documented AND evidence AND NOT
    provisional)."""
    verdict = validate_diagnostic_claim(
        evidence=True,
        documented=True,
        confirmed=True,
        provisional=False,
    )
    assert verdict["is_definitive"] is True
    assert verdict["may_present_as_definitive"] is True
    assert verdict["supported_category"] == "documented_diagnosis"


def test_medical_red_flag_escalates():
    rules = _by_id(build_health_rules())
    rule = rules["health.medical_red_flag"]
    result = rule.evaluate(
        _context(red_flag={"id": "f1", "is_red_flag": True, "symptom_severity": 3})
    )
    assert result.status is ReasoningRuleResultStatus.APPLIED
    assert result.escalation is not None
    assert result.escalation.code == "PROFESSIONAL_REVIEW_REQUIRED"


def test_professional_escalation_blocks_on_risk():
    rules = _by_id(build_health_rules())
    rule = rules["health.professional_escalation"]
    result = rule.evaluate(_context(escalation_factors={"risk": True}))
    assert result.status is ReasoningRuleResultStatus.BLOCKED
    assert result.escalation is not None


def test_professional_escalation_noop():
    rules = _by_id(build_health_rules())
    rule = rules["health.professional_escalation"]
    result = rule.evaluate(_context(escalation_factors={}))
    assert result.status is ReasoningRuleResultStatus.APPLIED


def test_deterministic_helpers():
    from cmm.domains.health.rules import (
        build_medication_temporal_relation,
        classify_clinical_statement,
        clinical_source_rank,
        evaluate_clinical_temporality,
        validate_diagnostic_claim,
    )

    assert (
        classify_clinical_statement(is_user_possibility=True, is_system_hypothesis=True)
        == "user_possibility"
    )
    assert classify_clinical_statement(is_system_hypothesis=True) == "system_hypothesis"
    relation = build_medication_temporal_relation(medication="medx", event_kind="start")
    assert relation["temporal_association"] is True
    assert relation["causation"] is False
    assert clinical_source_rank("medical_report") < clinical_source_rank("inference")
    assert evaluate_clinical_temporality(state="expired") == "expired"
    verdict = validate_diagnostic_claim(evidence=True, documented=True, confirmed=True)
    assert verdict["is_definitive"] is True
    # Documented + evidence but NOT confirmed must NOT be definitive.
    verdict = validate_diagnostic_claim(evidence=True, documented=True)
    assert verdict["is_definitive"] is False


def test_medication_date_conflict_start_after_end():
    """A start date after an end date is reported as a date-order conflict
    without discarding records or declaring a winner."""
    from cmm.domains.health.rules import detect_medication_conflicts

    records = [
        {
            "medication_id": "medx",
            "active": True,
            "start_date": "2026-08-10",
            "end_date": "2026-08-01",
        },
        {
            "medication_id": "medx",
            "active": True,
            "start_date": "2026-08-02",
            "end_date": "2026-09-01",
        },
    ]
    conflicts = detect_medication_conflicts(records)
    assert any(
        c.code == "MEDICATION_DATE_ORDER" and c.medication_ids == ("medx",)
        for c in conflicts
    )
    # Both records are preserved; no winner is chosen.
    assert len(records) == 2


def test_medication_date_conflict_no_false_positive():
    from cmm.domains.health.rules import detect_medication_conflicts

    conflicts = detect_medication_conflicts(
        [
            {
                "medication_id": "medx",
                "active": True,
                "start_date": "2026-08-01",
                "end_date": "2026-09-01",
            },
        ]
    )
    assert not any(c.code == "MEDICATION_DATE_ORDER" for c in conflicts)


def test_temporal_states_are_distinguishable():
    """The temporal validity model distinguishes current, historical,
    provisional, pending, stale, superseded, future, and unknown; a provisional
    record stays provisional and is never promoted to current."""
    from cmm.domains.health.rules import evaluate_clinical_temporality

    assert evaluate_clinical_temporality(state="current", active=True) == "current"
    assert (
        evaluate_clinical_temporality(state="historical", active=False) == "historical"
    )
    assert (
        evaluate_clinical_temporality(state="provisional", active=False)
        == "provisional"
    )
    assert evaluate_clinical_temporality(state="pending") == "pending"
    assert evaluate_clinical_temporality(state="stale") == "stale"
    assert (
        evaluate_clinical_temporality(state="superseded", superseded=True)
        == "superseded"
    )
    assert evaluate_clinical_temporality(state="future") == "future"
    assert evaluate_clinical_temporality(state="unknown") == "unknown"
    # Provisional must not be promoted to current even when active-flagged.
    assert (
        evaluate_clinical_temporality(state="provisional", active=True) == "provisional"
    )


def test_red_flag_escalation_depends_on_actual_values():
    """Red-flag escalation must follow the actual severity/flag values: a low
    severity with no red flag never escalates; a true red flag or high severity
    does.  The rule never claims to diagnose the cause."""
    from cmm.domains.health.rules import classify_escalation_level

    assert classify_escalation_level(symptom_severity=1) == "monitoring"
    assert (
        classify_escalation_level(symptom_severity=2, is_red_flag=False) == "monitoring"
    )
    assert classify_escalation_level(is_red_flag=True) == "urgent_attention"
    assert classify_escalation_level(symptom_severity=9) == "urgent_attention"
    assert classify_escalation_level(symptom_severity=7) == "priority_review"
    assert classify_escalation_level(symptom_severity=4) == "professional_review"


def test_medical_red_flag_rule_no_escalation_on_low_value():
    """The medical_red_flag rule must NOT attach an escalation when the actual
    values do not warrant professional review (monitoring level)."""
    from cmm.domains.health.rules import ESCALATION_MONITORING

    rules = _by_id(build_health_rules())
    rule = rules["health.medical_red_flag"]
    result = rule.evaluate(
        _context(red_flag={"id": "f0", "is_red_flag": False, "symptom_severity": 1})
    )
    assert result.escalation is None
    assert result.status is ReasoningRuleResultStatus.APPLIED
    assert any(
        finding.code == "RED_FLAG_ESCALATION_LEVEL"
        and ESCALATION_MONITORING in finding.message
        for finding in result.findings
    )
