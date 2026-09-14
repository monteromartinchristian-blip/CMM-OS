"""Tests for Languages Domain Language Variety and Framework Semantics."""

from __future__ import annotations

from datetime import datetime, timezone

from cmm.cognitive.enums import (
    ReasoningRiskLevel,
    ReasoningRuleCategory,
    ReasoningRuleResultStatus,
    ReasoningRuleScope,
    ReasoningRuleStatus,
)
from cmm.cognitive.reasoning_rule_contracts import ReasoningRuleContext
from cmm.domains.languages.rules import (
    LanguageVarietyValidityRule,
    ProficiencyFrameworkRule,
    classify_language_variety,
    evaluate_framework_mapping,
)
from cmm.domains.rule_contracts import DomainReasoningRuleDefinition

NOW = datetime.now(timezone.utc)


def test_classify_language_variety_valid_alternative() -> None:
    """Valid alternative variety is not treated as an error."""
    result = classify_language_variety(
        preferred_variety="American English",
        observed_variety="British English",
        assessment_standard="General English",
        form_status="valid",
    )
    assert result["classification"] == "valid_alternative"
    assert result["error"] is False
    assert result["is_valid_alternative"] is True


def test_classify_language_variety_preferred_match() -> None:
    """Observed variety matching preferred variety is preferred."""
    result = classify_language_variety(
        preferred_variety="American English",
        observed_variety="American English",
        assessment_standard="General English",
        form_status="valid",
    )
    assert result["classification"] == "preferred"
    assert result["error"] is False


def test_classify_language_variety_invalid_form() -> None:
    """Invalid linguistic form is classified as incorrect regardless of variety claim."""
    result = classify_language_variety(
        preferred_variety="American English",
        observed_variety="British English",
        assessment_standard="General English",
        form_status="incorrect",
    )
    assert result["classification"] == "incorrect"
    assert result["error"] is True


def test_classify_language_variety_unknown_string() -> None:
    """Unknown strings do not silently become valid."""
    result = classify_language_variety(
        preferred_variety="American English",
        observed_variety="Fictional Variety 99",
        assessment_standard="General English",
        form_status=None,
    )
    assert result["classification"] == "uncertain"
    assert result["error"] is False


def test_evaluate_framework_mapping_identity_forbidden() -> None:
    """Different frameworks (e.g. CEFR and IELTS) are not identical without evidence."""
    result = evaluate_framework_mapping(
        source_framework="CEFR",
        source_value="B2",
        target_framework="IELTS",
        mapping_evidence=(),
    )
    assert result["mapping_status"] in (
        "identity_forbidden",
        "grounded_approximate_mapping",
    )
    assert result["is_exact"] is False
    assert result["approximate"] is True


def test_evaluate_framework_mapping_known_approximate() -> None:
    """Standard concordance provides grounded approximate mapping."""
    result = evaluate_framework_mapping(
        source_framework="CEFR",
        source_value="C1",
        target_framework="IELTS",
        mapping_evidence=(
            {
                "source": "Cambridge English Concordance",
                "source_id": "cambridge-concordance-v1",
                "source_framework": "CEFR",
                "source_value": "C1",
                "target_framework": "IELTS",
                "target_range": "7.0-8.0",
            },
        ),
    )
    assert result["mapping_status"] == "grounded_approximate_mapping"
    assert result["target_estimate_range"] == "7.0-8.0"
    assert result["approximate"] is True
    assert result["is_exact"] is False
    assert result["calibrated"] is True
    assert result["evidence"][0]["source_id"] == "cambridge-concordance-v1"


def test_language_variety_validity_rule_evaluation() -> None:
    """Verify LanguageVarietyValidityRule evaluation."""
    rule_def = DomainReasoningRuleDefinition(
        id="languages.language_variety_validity",
        name="LanguageVarietyValidityRule",
        version="1.0.0",
        scope=ReasoningRuleScope.DOMAIN,
        domain_id="domain:languages",
        category=ReasoningRuleCategory.EPISTEMIC,
        status=ReasoningRuleStatus.ENABLED,
        priority=720,
        risk_level=ReasoningRiskLevel.LOW,
    )
    rule = LanguageVarietyValidityRule(definition=rule_def)
    context = ReasoningRuleContext(
        reasoning_id="r-eval-3",
        timestamp=NOW,
        metadata={
            "material": {
                "preferred_variety": "American English",
                "observed_variety": "British English",
                "form_status": "valid",
            }
        },
    )
    res = rule.evaluate(context)
    assert res.status == ReasoningRuleResultStatus.APPLIED
    assert res.findings[0].metadata["classification"] == "valid_alternative"


def test_proficiency_framework_rule_evaluation() -> None:
    """Verify ProficiencyFrameworkRule evaluation."""
    rule_def = DomainReasoningRuleDefinition(
        id="languages.proficiency_framework",
        name="ProficiencyFrameworkRule",
        version="1.0.0",
        scope=ReasoningRuleScope.DOMAIN,
        domain_id="domain:languages",
        category=ReasoningRuleCategory.EPISTEMIC,
        status=ReasoningRuleStatus.ENABLED,
        priority=730,
        risk_level=ReasoningRiskLevel.LOW,
    )
    rule = ProficiencyFrameworkRule(definition=rule_def)
    context = ReasoningRuleContext(
        reasoning_id="r-eval-4",
        timestamp=NOW,
        metadata={
            "material": {
                "source_framework": "CEFR",
                "source_value": "B2",
                "target_framework": "IELTS",
            }
        },
    )
    res = rule.evaluate(context)
    assert res.status == ReasoningRuleResultStatus.APPLIED
    assert res.findings[0].metadata["mapping_status"] == "identity_forbidden"
