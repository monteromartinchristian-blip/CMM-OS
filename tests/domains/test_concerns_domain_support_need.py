"""Phase 10.25 — Concerns support-need calibration rule tests.

``SupportNeedCalibrationRule`` (and its sibling Task 3 rules) are
@dataclass(frozen=True, slots=True) definitions exposing ``definition`` and
``evaluate(context)`` through the shared reasoning contracts.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from cmm.cognitive.enums import ReasoningRuleResultStatus
from cmm.cognitive.reasoning_rule_contracts import ReasoningRuleContext
from cmm.domains.concerns.rules import (
    EmotionalValidationRule,
    SupportNeedCalibrationRule,
    UnderstandBeforeInterveneRule,
    build_concerns_rules,
)

NOW = datetime(2026, 8, 21, 12, 0, tzinfo=timezone.utc)


def _definition(rule_id: str, name: str):
    from cmm.cognitive.enums import (
        ReasoningRiskLevel,
        ReasoningRuleCategory,
        ReasoningRuleScope,
        ReasoningRuleStatus,
    )
    from cmm.domains.rule_contracts import DomainReasoningRuleDefinition

    return DomainReasoningRuleDefinition(
        id=rule_id,
        name=name,
        version="1.0.0",
        scope=ReasoningRuleScope.DOMAIN,
        domain_id="domain:concerns",
        category=ReasoningRuleCategory.INFERENCE.value,
        status=ReasoningRuleStatus.ENABLED,
        priority=720,
        risk_level=ReasoningRiskLevel.LOW,
        deterministic=True,
        description=f"{name} under test.",
        metadata={"phase": "10.25"},
    )


def test_build_concerns_rules_partial_is_deterministic_and_domain_scoped():
    rules = build_concerns_rules()
    assert len(rules) == 14
    for rule in rules:
        assert str(rule.definition.domain_id) == "domain:concerns"
        assert rule.definition.deterministic is True
    names = [rule.definition.name for rule in rules]
    assert names[0] == "UnderstandBeforeInterveneRule"
    assert names[3] == "SupportNeedCalibrationRule"
    assert names[-1] == "ImmediateRiskEscalationRule"


def test_understand_before_intervene_rule_blocks_premature_advice():
    context = ReasoningRuleContext(
        reasoning_id="rr-c-ubi-1",
        timestamp=NOW,
        active_domains=("domain:concerns",),
        primary_domain="domain:concerns",
        metadata={"material": {"situation": "something at work"}},
    )
    rule = UnderstandBeforeInterveneRule(
        definition=_definition(
            "concerns.understand_before_intervene", "UnderstandBeforeInterveneRule"
        )
    )
    result = rule.evaluate(context)
    assert result.status is ReasoningRuleResultStatus.APPLIED
    finding = result.findings[0]
    # premature advice blocked while understanding is incomplete
    assert finding.metadata["intervention_allowed"] is False
    assert finding.metadata["ask_question"] is True


def test_understand_before_intervene_allows_response_with_context():
    context = ReasoningRuleContext(
        reasoning_id="rr-c-ubi-2",
        timestamp=NOW,
        active_domains=("domain:concerns",),
        primary_domain="domain:concerns",
        metadata={
            "material": {
                "situation": "manager silent for five days after salary email",
                "what_matters": "whether my position is at risk",
                "explicit_request": "Tell me what you think.",
            }
        },
    )
    rule = UnderstandBeforeInterveneRule(
        definition=_definition(
            "concerns.understand_before_intervene", "UnderstandBeforeInterveneRule"
        )
    )
    result = rule.evaluate(context)
    finding = result.findings[0]
    assert finding.metadata["intervention_allowed"] is True
    assert finding.metadata["mandatory_action_plan"] is False


def test_support_need_rule_explicit_wins():
    context = ReasoningRuleContext(
        reasoning_id="rr-c-snc-1",
        timestamp=NOW,
        active_domains=("domain:concerns",),
        primary_domain="domain:concerns",
        metadata={
            "support_need": {
                "explicit_request": "I just need to talk, no advice.",
                "historical_preference": "PROBLEM_SOLVING",
            }
        },
    )
    rule = SupportNeedCalibrationRule(
        definition=_definition(
            "concerns.support_need_calibration", "SupportNeedCalibrationRule"
        )
    )
    result = rule.evaluate(context)
    finding = result.findings[0]
    metadata = finding.metadata
    assert metadata["record"]["basis"] == "explicit_current_request"
    assert metadata["record"]["problem_solving_allowed"] is False


def test_support_need_rule_not_applicable():
    context = ReasoningRuleContext(
        reasoning_id="rr-c-snc-2",
        timestamp=NOW,
        active_domains=("domain:concerns",),
        primary_domain="domain:concerns",
        metadata={},
    )
    rule = SupportNeedCalibrationRule(
        definition=_definition(
            "concerns.support_need_calibration", "SupportNeedCalibrationRule"
        )
    )
    result = rule.evaluate(context)
    assert result.status is ReasoningRuleResultStatus.NOT_APPLICABLE


def test_emotional_validation_preserves_experience_boundary():
    context = ReasoningRuleContext(
        reasoning_id="rr-c-ev-1",
        timestamp=NOW,
        active_domains=("domain:concerns",),
        primary_domain="domain:concerns",
        metadata={
            "lived_experience": {
                "emotion_statements": ("I feel ignored",),
                "interpretation_statements": ("They are rejecting me",),
            }
        },
    )
    rule = EmotionalValidationRule(
        definition=_definition(
            "concerns.emotional_validation", "EmotionalValidationRule"
        )
    )
    result = rule.evaluate(context)
    finding = result.findings[0]
    metadata = finding.metadata
    assert metadata["experience_validated"] is True
    assert metadata["interpretation_promoted_to_fact"] is False


def test_rule_findings_are_strict_json_safe():
    context = ReasoningRuleContext(
        reasoning_id="rr-c-json-1",
        timestamp=NOW,
        active_domains=("domain:concerns",),
        primary_domain="domain:concerns",
        metadata={"lived_experience": {"emotion_statements": ("x",)}},
    )
    rule = EmotionalValidationRule(
        definition=_definition(
            "concerns.emotional_validation", "EmotionalValidationRule"
        )
    )
    result = rule.evaluate(context)
    json.dumps(result.to_dict(), allow_nan=False)
    json.dumps(result.findings[0].to_dict(), allow_nan=False)
