"""Tests for Languages Domain Proficiency Semantics and Skill Separation."""

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
    LanguageLevelEvidenceRule,
    SkillSeparationRule,
    classify_proficiency_record,
    evaluate_level_update,
    normalize_json_value,
    separate_skill_evidence,
)
from cmm.domains.rule_contracts import DomainReasoningRuleDefinition


def test_classify_proficiency_record_kinds() -> None:
    """Verify distinct CERTIFIED, ESTIMATED, and OBSERVED_PERFORMANCE classifications."""
    # Official certificate -> CERTIFIED
    cert = classify_proficiency_record(
        kind="CERTIFIED",
        framework="CEFR",
        level_or_score="C1",
        skill_scope="reading",
        evidence=(
            {"id": "cert-1", "source_kind": "official_certificate", "issuer": "Cambridge"},
        ),
    )
    assert cert["kind"] == "CERTIFIED"
    assert cert["level_or_score"] == "C1"
    assert cert["is_certified"] is True

    # Single sample -> OBSERVED_PERFORMANCE
    sample = classify_proficiency_record(
        kind="OBSERVED_PERFORMANCE",
        framework="CEFR",
        level_or_score="B2",
        skill_scope="writing",
        evidence=(
            {"id": "sample-1", "task_type": "essay"},
        ),
    )
    assert sample["kind"] == "OBSERVED_PERFORMANCE"
    assert sample["is_certified"] is False

    # Longitudinal -> ESTIMATED
    est = classify_proficiency_record(
        kind="ESTIMATED",
        framework="CEFR",
        level_or_score="B1+",
        skill_scope="writing",
        evidence=(
            {"id": "sample-1", "task_type": "essay", "observed": "B1+"},
            {"id": "sample-2", "task_type": "summary", "observed": "B1+"},
        ),
    )
    assert est["kind"] == "ESTIMATED"
    assert est["is_certified"] is False


def test_evaluate_level_update_single_sample_not_stable() -> None:
    """A single strong sample cannot update stable proficiency estimate."""
    result = evaluate_level_update(
        existing={
            "kind": "ESTIMATED",
            "skill_scope": "writing",
            "level_or_score": "B1+",
        },
        evidence=(
            {"id": "sample-1", "skill": "writing", "observed": "B2"},
        ),
        target_skill="writing",
    )
    assert result["stable_update_supported"] is False
    assert result["reason"] == "insufficient_comparable_evidence"
    assert result["proposed_level"] is None or result["proposed_level"] == "B1+"


def test_evaluate_level_update_cannot_overwrite_certified() -> None:
    """An estimate or practice sample cannot overwrite a certified record."""
    result = evaluate_level_update(
        existing={
            "kind": "CERTIFIED",
            "skill_scope": "reading",
            "level_or_score": "C1",
            "certificate_id": "cambridge-c1",
        },
        evidence=(
            {"id": "sample-1", "skill": "reading", "observed": "B2"},
            {"id": "sample-2", "skill": "reading", "observed": "B2"},
        ),
        target_skill="reading",
    )
    assert result["stable_update_supported"] is False
    assert result["reason"] == "certified_record_cannot_be_overwritten"


def test_separate_skill_evidence_isolation() -> None:
    """Skill evidence is strictly separated across canonical dimensions."""
    evidence = (
        {"id": "ev-1", "skill": "reading", "observed": "B2"},
        {"id": "ev-2", "skill": "grammar", "observed": "85%"},
        {"id": "ev-3", "skill": "writing", "observed": "B1"},
    )
    separated = separate_skill_evidence(evidence=evidence)

    assert "reading" in separated["by_skill"]
    assert "grammar" in separated["by_skill"]
    assert "writing" in separated["by_skill"]

    # Speaking was not observed -> insufficient evidence
    assert separated["by_skill"]["speaking"]["status"] == "insufficient_evidence"
    assert separated["by_skill"]["speaking"]["evidence_count"] == 0

    # Pronunciation was not observed
    assert separated["by_skill"]["pronunciation"]["status"] == "insufficient_evidence"


def test_transcript_only_is_not_pronunciation() -> None:
    """Audio transcript alone provides reading/lexical/grammar evidence, never pronunciation."""
    evidence = (
        {"id": "trans-1", "source_kind": "audio_transcript", "skill": "speaking", "transcript": "Hello world"},
    )
    separated = separate_skill_evidence(evidence=evidence)
    assert separated["pronunciation_assessed"] is False
    assert separated["by_skill"]["pronunciation"]["status"] == "insufficient_evidence"


def test_normalize_json_value() -> None:
    """Verify recursive normalization of dicts, lists, and primitives."""
    raw = {
        "a": (1, 2),
        "b": {"c": 3.0},
        "d": "text",
        "e": None,
    }
    norm = normalize_json_value(raw)
    assert norm == {
        "a": [1, 2],
        "b": {"c": 3.0},
        "d": "text",
        "e": None,
    }


NOW = datetime.now(timezone.utc)


def test_language_level_evidence_rule_evaluation() -> None:
    """Verify LanguageLevelEvidenceRule evaluation."""
    rule_def = DomainReasoningRuleDefinition(
        id="languages.language_level_evidence",
        name="LanguageLevelEvidenceRule",
        version="1.0.0",
        scope=ReasoningRuleScope.DOMAIN,
        domain_id="domain:languages",
        category=ReasoningRuleCategory.EPISTEMIC,
        status=ReasoningRuleStatus.ENABLED,
        priority=700,
        risk_level=ReasoningRiskLevel.LOW,
    )
    rule = LanguageLevelEvidenceRule(definition=rule_def)
    context = ReasoningRuleContext(
        reasoning_id="r-eval-1",
        timestamp=NOW,
        metadata={
            "material": {
                "kind": "CERTIFIED",
                "framework": "CEFR",
                "level_or_score": "C1",
                "evidence": [{"id": "c1", "source_kind": "official_certificate"}],
            }
        },
    )
    res = rule.evaluate(context)
    assert res.status == ReasoningRuleResultStatus.APPLIED
    assert res.findings[0].metadata["kind"] == "CERTIFIED"


def test_skill_separation_rule_evaluation() -> None:
    """Verify SkillSeparationRule evaluation."""
    rule_def = DomainReasoningRuleDefinition(
        id="languages.skill_separation",
        name="SkillSeparationRule",
        version="1.0.0",
        scope=ReasoningRuleScope.DOMAIN,
        domain_id="domain:languages",
        category=ReasoningRuleCategory.EPISTEMIC,
        status=ReasoningRuleStatus.ENABLED,
        priority=710,
        risk_level=ReasoningRiskLevel.LOW,
    )
    rule = SkillSeparationRule(definition=rule_def)
    context = ReasoningRuleContext(
        reasoning_id="r-eval-2",
        timestamp=NOW,
        metadata={
            "material": {
                "evidence": [{"id": "e1", "skill": "reading", "observed": "B2"}],
            }
        },
    )
    res = rule.evaluate(context)
    assert res.status == ReasoningRuleResultStatus.APPLIED
    assert "reading" in res.findings[0].metadata["by_skill"]
