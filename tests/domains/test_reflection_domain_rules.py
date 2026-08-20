"""Phase 10.24 — Reflection canonical rules tests.

The six canonical rules are @dataclass(frozen=True, slots=True) definitions
exposing ``definition`` and ``evaluate(context)`` through the shared reasoning
contracts.  This module also pins ``NoForcedConclusionRule`` semantics:
successful completion without a conclusion is valid, never a rule failure
(spec §13, §41).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from cmm.cognitive.enums import ReasoningRuleResultStatus
from cmm.cognitive.reasoning_rule_contracts import ReasoningRuleContext
from cmm.domains.reflection.rules import (
    NoForcedConclusionRule,
    build_reflection_rules,
    no_forced_conclusion_policy,
)

NOW = datetime(2026, 8, 1, tzinfo=timezone.utc)


def _rule_definition():
    from cmm.cognitive.enums import (
        ReasoningRiskLevel,
        ReasoningRuleCategory,
        ReasoningRuleScope,
        ReasoningRuleStatus,
    )
    from cmm.domains.rule_contracts import DomainReasoningRuleDefinition

    return DomainReasoningRuleDefinition(
        id="reflection.no_forced_conclusion",
        name="NoForcedConclusionRule",
        version="1.0.0",
        scope=ReasoningRuleScope.DOMAIN,
        domain_id="domain:reflection",
        category=ReasoningRuleCategory.SAFETY.value,
        status=ReasoningRuleStatus.ENABLED,
        priority=780,
        risk_level=ReasoningRiskLevel.MEDIUM,
        deterministic=True,
        description="No forced conclusion rule.",
        metadata={"phase": "10.24"},
    )


def test_build_reflection_rules_exactly_six():
    rules = build_reflection_rules()
    assert len(rules) == 6
    ids = [rule.definition.id for rule in rules]
    assert ids == [
        "reflection.multiple_hypotheses",
        "reflection.preserve_ambivalence",
        "reflection.belief_evidence",
        "reflection.open_question",
        "reflection.temporal_evolution",
        "reflection.no_forced_conclusion",
    ]
    names = [rule.definition.name for rule in rules]
    assert names == [
        "MultipleHypothesesRule",
        "PreserveAmbivalenceRule",
        "BeliefEvidenceRule",
        "OpenQuestionRule",
        "ReflectionTemporalEvolutionRule",
        "NoForcedConclusionRule",
    ]


def test_rules_are_deterministic_and_domain_scoped():
    for rule in build_reflection_rules():
        assert rule.definition.domain_id == "domain:reflection"
        assert rule.definition.deterministic is True
        assert rule.definition.scope.value == "domain"


def test_no_forced_conclusion_valid_unresolved_completion():
    """A structured-but-unresolved result is a valid completion, not failure."""
    result = {
        "unresolved": True,
        "hypothesis_count": 3,
        "open_questions": 2,
        "ambivalence_present": True,
        "conclusion": None,
        "recommendation": None,
    }
    policy = no_forced_conclusion_policy(result)
    assert policy["forced_conclusion"] is False
    assert policy["valid_unresolved_completion"] is True
    assert policy["unsupported_certainty"] == ()


def test_forbidden_certainty_phrases_flagged_when_unresolved():
    result = {
        "unresolved": True,
        "hypothesis_count": 2,
        "open_questions": 1,
        "conclusion_text": "Therefore this proves the real reason is that you are "
        "definitely avoidant.",
    }
    policy = no_forced_conclusion_policy(result)
    assert policy["forced_conclusion"] is True
    assert policy["valid_unresolved_completion"] is False
    assert len(policy["unsupported_certainty"]) > 0


def test_resolved_result_without_forced_language_not_forced():
    result = {
        "unresolved": False,
        "conclusion_text": "The user stated they are changing jobs.",
    }
    policy = no_forced_conclusion_policy(result)
    assert policy["forced_conclusion"] is False


def test_no_forced_conclusion_rule_applies():
    context = ReasoningRuleContext(
        reasoning_id="rr-nfc-1",
        timestamp=NOW,
        active_domains=("domain:reflection",),
        primary_domain="domain:reflection",
        metadata={
            "result": {
                "unresolved": True,
                "hypothesis_count": 2,
                "open_questions": 1,
                "ambivalence_present": True,
            }
        },
    )
    rule = NoForcedConclusionRule(definition=_rule_definition())
    result = rule.evaluate(context)
    assert result.status is ReasoningRuleResultStatus.APPLIED
    finding = result.findings[0]
    assert finding.metadata["forced_conclusion"] is False
    assert finding.metadata["valid_unresolved_completion"] is True
    json.dumps(finding.to_dict(), allow_nan=False)


def test_no_forced_conclusion_rule_detects_forced_conclusion():
    context = ReasoningRuleContext(
        reasoning_id="rr-nfc-2",
        timestamp=NOW,
        active_domains=("domain:reflection",),
        primary_domain="domain:reflection",
        metadata={
            "result": {
                "unresolved": True,
                "conclusion_text": "So the answer is clearly that this is the "
                "real reason.",
            }
        },
    )
    rule = NoForcedConclusionRule(definition=_rule_definition())
    result = rule.evaluate(context)
    assert result.status is ReasoningRuleResultStatus.APPLIED
    assert result.findings[0].metadata["forced_conclusion"] is True
    assert result.findings[0].metadata["unsupported_certainty"] != ()


def test_no_forced_conclusion_rule_not_applicable():
    context = ReasoningRuleContext(
        reasoning_id="rr-nfc-3",
        timestamp=NOW,
        active_domains=("domain:reflection",),
        primary_domain="domain:reflection",
        metadata={},
    )
    rule = NoForcedConclusionRule(definition=_rule_definition())
    result = rule.evaluate(context)
    assert result.status is ReasoningRuleResultStatus.NOT_APPLICABLE