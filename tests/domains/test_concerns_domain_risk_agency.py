"""Phase 10.25 — Concerns risk/agency rule-class tests.

The remaining four canonical rules are @dataclass(frozen=True, slots=True)
definitions exposing ``definition`` and ``evaluate(context)``.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from cmm.cognitive.enums import (
    ReasoningRiskLevel,
    ReasoningRuleCategory,
    ReasoningRuleResultStatus,
    ReasoningRuleScope,
    ReasoningRuleStatus,
    ReasoningSeverity,
)
from cmm.cognitive.reasoning_rule_contracts import ReasoningRuleContext
from cmm.domains.concerns.rules import (
    AgencyWithoutPressureRule,
    DirectnessWithoutHarshnessRule,
    ImmediateRiskEscalationRule,
    RepetitionWithoutPathologizingRule,
    build_concerns_rules,
)
from cmm.domains.rule_contracts import DomainReasoningRuleDefinition

NOW = datetime(2026, 8, 21, 14, 0, tzinfo=timezone.utc)


def _definition(rule_id: str, name: str, *, priority: int = 800):
    return DomainReasoningRuleDefinition(
        id=rule_id,
        name=name,
        version="1.0.0",
        scope=ReasoningRuleScope.DOMAIN,
        domain_id="domain:concerns",
        category=ReasoningRuleCategory.SAFETY.value,
        status=ReasoningRuleStatus.ENABLED,
        priority=priority,
        risk_level=ReasoningRiskLevel.MEDIUM,
        deterministic=True,
        description=f"{name} under test.",
        metadata={"phase": "10.25"},
    )


def test_build_concerns_rules_returns_exactly_14_in_catalog_order():
    rules = build_concerns_rules()
    assert len(rules) == 14
    ids = [rule.definition.id for rule in rules]
    assert ids == [
        "concerns.understand_before_intervene",
        "concerns.emotional_validation",
        "concerns.experience_reality_separation",
        "concerns.support_need_calibration",
        "concerns.contextual_question",
        "concerns.uncertainty_preservation",
        "concerns.evidence_calibrated_reassurance",
        "concerns.proportional_risk",
        "concerns.no_catastrophic_escalation",
        "concerns.no_false_reassurance",
        "concerns.repetition_without_pathologizing",
        "concerns.agency_without_pressure",
        "concerns.directness_without_harshness",
        "concerns.immediate_risk_escalation",
    ]
    names = [rule.definition.name for rule in rules]
    assert names == [
        "UnderstandBeforeInterveneRule",
        "EmotionalValidationRule",
        "ExperienceRealitySeparationRule",
        "SupportNeedCalibrationRule",
        "ContextualQuestionRule",
        "UncertaintyPreservationRule",
        "EvidenceCalibratedReassuranceRule",
        "ProportionalRiskRule",
        "NoCatastrophicEscalationRule",
        "NoFalseReassuranceRule",
        "RepetitionWithoutPathologizingRule",
        "AgencyWithoutPressureRule",
        "DirectnessWithoutHarshnessRule",
        "ImmediateRiskEscalationRule",
    ]


def test_all_rules_deterministic_and_domain_scoped():
    for rule in build_concerns_rules():
        assert str(rule.definition.domain_id) == "domain:concerns"
        assert rule.definition.deterministic is True


def test_repetition_rule_preserves_non_pathology():
    context = ReasoningRuleContext(
        reasoning_id="rr-c-rwp-1",
        timestamp=NOW,
        active_domains=("domain:concerns",),
        primary_domain="domain:concerns",
        metadata={
            "recurrence": {
                "current": {"topic": "t", "question": "q"},
                "previous": ({"topic": "t", "question": "q"},),
                "turns": tuple({"turn": i, "same_question": True} for i in range(6)),
            }
        },
    )
    rule = RepetitionWithoutPathologizingRule(
        definition=_definition(
            "concerns.repetition_without_pathologizing",
            "RepetitionWithoutPathologizingRule",
        )
    )
    result = rule.evaluate(context)
    finding = result.findings[0]
    metadata = finding.metadata
    assert metadata["pathology_inferred"] is False
    assert metadata["reassurance_allowed"] is True
    json.dumps(result.to_dict(), allow_nan=False)


def test_agency_rule_blocks_forced_action():
    context = ReasoningRuleContext(
        reasoning_id="rr-c-awp-1",
        timestamp=NOW,
        active_domains=("domain:concerns",),
        primary_domain="domain:concerns",
        metadata={
            "action": {
                "options": ("A", "B"),
                "user_request": "I just need to talk.",
            }
        },
    )
    rule = AgencyWithoutPressureRule(
        definition=_definition("concerns.agency_without_pressure", "AgencyWithoutPressureRule")
    )
    result = rule.evaluate(context)
    finding = result.findings[0]
    assert finding.metadata["record"]["decision_adopted"] is False
    assert finding.metadata["record"]["action_forced"] is False


def test_directness_rule_reports_grounded_opinion():
    context = ReasoningRuleContext(
        reasoning_id="rr-c-dwh-1",
        timestamp=NOW,
        active_domains=("domain:concerns",),
        primary_domain="domain:concerns",
        metadata={
            "directness": {
                "assessment": "user_interpretation_unlikely",
                "evidence": (
                    {"identity": "c1", "against": "feared reading", "grounding": "a"},
                    {"identity": "c2", "against": "feared reading", "grounding": "b"},
                ),
            }
        },
    )
    rule = DirectnessWithoutHarshnessRule(
        definition=_definition(
            "concerns.directness_without_harshness", "DirectnessWithoutHarshnessRule"
        )
    )
    result = rule.evaluate(context)
    finding = result.findings[0]
    assert finding.severity is not ReasoningSeverity.ERROR
    assert finding.metadata["harsh"] is False
    assert finding.metadata["disagreement_explicit"] is True


def test_immediate_risk_rule_not_applicable_without_inputs():
    context = ReasoningRuleContext(
        reasoning_id="rr-c-ire-1",
        timestamp=NOW,
        active_domains=("domain:concerns",),
        primary_domain="domain:concerns",
        metadata={},
    )
    rule = ImmediateRiskEscalationRule(
        definition=_definition(
            "concerns.immediate_risk_escalation", "ImmediateRiskEscalationRule"
        )
    )
    result = rule.evaluate(context)
    assert result.status is ReasoningRuleResultStatus.NOT_APPLICABLE


def test_immediate_risk_rule_escalates_only_credibly():
    context = ReasoningRuleContext(
        reasoning_id="rr-c-ire-2",
        timestamp=NOW,
        active_domains=("domain:concerns",),
        primary_domain="domain:concerns",
        metadata={
            "escalation": {
                "risk_state": {"described_signal": "ordinary sadness"},
            }
        },
    )
    rule = ImmediateRiskEscalationRule(
        definition=_definition(
            "concerns.immediate_risk_escalation", "ImmediateRiskEscalationRule"
        ),
    )
    result = rule.evaluate(context)
    finding = result.findings[0]
    assert finding.metadata["escalate"] is False
    json.dumps(result.to_dict(), allow_nan=False)
