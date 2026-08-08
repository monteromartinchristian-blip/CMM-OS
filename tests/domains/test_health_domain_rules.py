"""Tests for Phase 10.20 Health Domain reasoning rules."""

from __future__ import annotations

from datetime import datetime, timezone

from cmm.cognitive.enums import ReasoningRuleResultStatus
from cmm.cognitive.reasoning_rule_contracts import ReasoningRuleContext
from cmm.domains.health import build_health_rules

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
    assert any(
        finding.code == "NO_DEFINITIVE_DIAGNOSIS"
        for finding in result.findings
    )


def test_no_definitive_diagnosis_allows_documented():
    rules = _by_id(build_health_rules())
    rule = rules["health.no_definitive_diagnosis"]
    result = rule.evaluate(
        _context(diagnostic_claim={"evidence": True, "documented": True})
    )
    assert result.status is ReasoningRuleResultStatus.APPLIED


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
        classify_clinical_statement(
            is_user_possibility=True, is_system_hypothesis=True
        )
        == "user_possibility"
    )
    assert (
        classify_clinical_statement(is_system_hypothesis=True)
        == "system_hypothesis"
    )
    relation = build_medication_temporal_relation(
        medication="medx", event_kind="start"
    )
    assert relation["temporal_association"] is True
    assert relation["causation"] is False
    assert clinical_source_rank("medical_report") < clinical_source_rank("inference")
    assert evaluate_clinical_temporality(state="expired") == "expired"
    verdict = validate_diagnostic_claim(evidence=True, documented=True)
    assert verdict["is_definitive"] is True
