"""Tests for Languages Domain Spaced Review, Load, Goals, Progression, Certification, Cultural, and Memory Rules."""

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
from cmm.domains.languages.catalog import CANONICAL_LANGUAGES_RULE_IDS
from cmm.domains.languages.rules import (
    CertificationTemporalRule,
    CulturalContextEvidenceRule,
    GoalAlignmentRule,
    LanguageMemoryConsentRule,
    LearningLoadRule,
    ProgressionEvidenceRule,
    SpacedReviewRule,
    align_activity_to_goals,
    build_languages_rules,
    evaluate_certification_source,
    evaluate_cultural_context,
    evaluate_language_memory_consent,
    evaluate_learning_load,
    evaluate_progression,
    plan_spaced_review,
)
from cmm.domains.rule_contracts import DomainReasoningRuleDefinition

NOW = datetime.now(timezone.utc)


def test_plan_spaced_review_priority() -> None:
    """Spaced review responds to mastery, recall, importance, and active patterns."""
    items = (
        {"id": "v1", "term": "ubiquitous", "mastery": 0.9, "due": False},
        {"id": "v2", "term": "alleviate", "mastery": 0.3, "due": True, "goal_relevant": True},
        {"id": "v3", "term": "meticulous", "mastery": 0.6, "due": True, "active_pattern": True},
    )
    result = plan_spaced_review(items=items, active_goals=("c1_exam",))
    assert result["prioritized_items"][0]["id"] in ("v2", "v3")
    assert result["backlog_count"] >= 2


def test_evaluate_learning_load_constraints() -> None:
    """Hard constraints/time/energy precede preferences and no calendar mutation occurs."""
    result = evaluate_learning_load(
        available_time=20,
        energy="low",
        priorities=("review", "conversation"),
        review_backlog=({"id": "i1"}, {"id": "i2"}),
    )
    assert result["recommended_duration_minutes"] <= 20
    assert result["calendar_modified"] is False


def test_align_activity_to_goals_coexistence() -> None:
    """Multiple concurrent goals can coexist without one erasing the other."""
    goals = (
        {"id": "g_cert", "kind": "certification", "target": "C1 Catalan"},
        {"id": "g_conv", "kind": "conversation", "target": "Daily fluency"},
    )
    res = align_activity_to_goals(
        activity={"type": "roleplay", "topic": "workplace"},
        goals=goals,
    )
    assert len(res["coexisting_goals"]) == 2
    assert "g_cert" in res["coexisting_goals"]
    assert "g_conv" in res["coexisting_goals"]


def test_evaluate_progression_single_sample_vs_stable() -> None:
    """One better sample is short_term_improvement; repeated is stable_improvement."""
    # Single improvement
    prev_ev = ({"provenance_id": "p1", "score": 0.6, "skill": "writing", "comparable": True, "comparison_key": "writing-argumentative"},)
    curr_ev_single = ({"provenance_id": "c1", "score": 0.85, "skill": "writing", "comparable": True, "comparison_key": "writing-argumentative"},)
    res_single = evaluate_progression(previous_evidence=prev_ev, current_evidence=curr_ev_single, skill="writing")
    assert res_single["progression_outcome"] == "short_term_improvement"
    assert res_single["stable_progression"] is False

    # Repeated comparable improvement
    curr_ev_repeated = (
        {"provenance_id": "c1", "score": 0.85, "skill": "writing", "comparable": True, "comparison_key": "writing-argumentative"},
        {"provenance_id": "c2", "score": 0.88, "skill": "writing", "comparable": True, "comparison_key": "writing-argumentative"},
    )
    res_stable = evaluate_progression(previous_evidence=prev_ev, current_evidence=curr_ev_repeated, skill="writing")
    assert res_stable["progression_outcome"] == "stable_improvement"
    assert res_stable["stable_progression"] is True


def test_no_baseline_cannot_create_stable_progression() -> None:
    """Current high scores cannot invent their own historical baseline."""
    current = (
        {"provenance_id": "c1", "score": 0.90, "skill": "writing", "comparable": True, "comparison_key": "writing-argumentative"},
        {"provenance_id": "c2", "score": 0.92, "skill": "writing", "comparable": True, "comparison_key": "writing-argumentative"},
    )

    result = evaluate_progression(previous_evidence=(), current_evidence=current, skill="writing")

    assert result["stable_progression"] is False
    assert result["progression_outcome"] == "insufficient_evidence"


def test_non_comparable_results_cannot_create_stable_progression() -> None:
    """Longitudinal claims require an explicit shared comparison basis."""
    previous = ({"provenance_id": "p1", "score": 0.5, "skill": "writing", "comparable": True, "comparison_key": "essay"},)
    current = (
        {"provenance_id": "c1", "score": 0.9, "skill": "writing", "comparable": False, "comparison_key": "dialogue"},
        {"provenance_id": "c2", "score": 0.92, "skill": "writing", "comparable": False, "comparison_key": "translation"},
    )

    result = evaluate_progression(previous_evidence=previous, current_evidence=current, skill="writing")

    assert result["stable_progression"] is False
    assert result["progression_outcome"] == "insufficient_evidence"


def test_progress_operation_never_inflates_unrelated_skills() -> None:
    from cmm.domains.languages.operations import generate_progress_review_result

    result = generate_progress_review_result(
        language="English",
        period="month",
        previous_evidence=(
            {"provenance_id": "w0", "score": 0.5, "skill": "writing", "comparable": True, "comparison_key": "essay"},
        ),
        evidence=(
            {"provenance_id": "w1", "score": 0.8, "skill": "writing", "comparable": True, "comparison_key": "essay"},
            {"provenance_id": "w2", "score": 0.82, "skill": "writing", "comparable": True, "comparison_key": "essay"},
        ),
        skill="writing",
    )

    assert set(result["skill_progress"]) == {"writing"}
    assert set(result["skill_progress"]) <= {
        item["skill"] for item in (
            {"skill": "writing"},
        )
    }
    assert result["cross_skill_inflation"] is False


def test_evaluate_progression_one_poor_session_no_stable_regression() -> None:
    """One poor session does not produce stable regression."""
    prev_ev = ({"id": "p1", "score": 0.85, "skill": "writing"},)
    curr_ev_bad = ({"id": "c1", "score": 0.40, "skill": "writing"},)
    res = evaluate_progression(previous_evidence=prev_ev, current_evidence=curr_ev_bad, skill="writing")
    assert res["progression_outcome"] != "stable_regression"
    assert res["stable_progression"] is False


def test_evaluate_certification_source_authority() -> None:
    """Current official source outranks stale guide/memory; conflict remains unresolved."""
    sources = (
        {"id": "s_guide", "source_type": "guide", "authority": 1, "date_valid": True, "format": "3_tasks"},
        {"id": "s_official", "source_type": "official", "authority": 3, "date_valid": True, "format": "4_tasks"},
    )
    res = evaluate_certification_source(sources=sources, decision_critical=True)
    assert res["selected_source"]["id"] == "s_official"
    assert res["needs_verification"] is False

    # Conflicting equal authority
    conflicting = (
        {"id": "s_off1", "source_type": "official", "authority": 3, "date_valid": True, "task_count": 3},
        {"id": "s_off2", "source_type": "official", "authority": 3, "date_valid": True, "task_count": 4},
    )
    res_conf = evaluate_certification_source(sources=conflicting, decision_critical=True)
    assert res_conf["unresolved_conflict"] is True
    assert res_conf["needs_verification"] is True


def test_current_official_beats_stale_official_even_when_stale_is_first() -> None:
    """Temporal validity outranks input order within official authority."""
    result = evaluate_certification_source(
        sources=(
            {"id": "stale", "source_type": "official", "date_valid": False, "format": "old-format"},
            {"id": "current", "source_type": "official", "date_valid": True, "format": "current-format"},
        ),
        decision_critical=True,
    )

    assert result["selected_source"]["id"] == "current"
    assert result["needs_verification"] is False


def test_stale_official_only_requires_decision_critical_verification() -> None:
    """Official provenance cannot make stale facts current."""
    result = evaluate_certification_source(
        sources=({"id": "stale", "source_type": "official", "date_valid": False},),
        decision_critical=True,
    )

    assert result["selected_source"]["id"] == "stale"
    assert result["needs_verification"] is True


def test_unknown_official_temporality_requires_verification() -> None:
    """Missing currentness fails closed for decision-critical facts."""
    result = evaluate_certification_source(
        sources=({"id": "unknown", "source_type": "official"},),
        decision_critical=True,
    )

    assert result["needs_verification"] is True


def test_evaluate_cultural_context_stereotypes_rejected() -> None:
    """Universal cultural stereotypes from weak evidence are rejected in favor of qualified tendencies."""
    res = evaluate_cultural_context(
        claim="All native speakers always use formal greetings.",
        universal_claim=True,
    )
    assert res["universal_claim_rejected"] is True
    assert res["qualified_tendency"] is True


def test_evaluate_language_memory_consent() -> None:
    """Session observation does not become durable state without literal boolean True consent."""
    # Session-only is fine without persistence
    res_session = evaluate_language_memory_consent(content_kind="session_note", session_only=True)
    assert res_session["session_only_allowed"] is True
    assert res_session["persistence_required"] is False

    # String "true" or int 1 is rejected
    res_str = evaluate_language_memory_consent(
        content_kind="proficiency_record",
        session_only=False,
        consent="true",
        permission_chain_valid=True,
    )
    assert res_str["persistence_authorized"] is False

    # Valid literal True consent produces proposal
    res_valid = evaluate_language_memory_consent(
        content_kind="proficiency_record",
        session_only=False,
        consent=True,
        permission_chain_valid=True,
    )
    assert res_valid["persistence_authorized"] is True
    assert res_valid["proposal_required"] is True
    assert res_valid["persistence_applied"] is False


def test_remaining_rule_classes_evaluation() -> None:
    """Verify evaluation for SpacedReview, LearningLoad, GoalAlignment, Progression, CertificationTemporal, CulturalContext, LanguageMemoryConsent rules."""
    # 1. SpacedReviewRule
    rule_sr = SpacedReviewRule(definition=DomainReasoningRuleDefinition(
        id="languages.spaced_review", name="SpacedReviewRule", version="1.0.0",
        scope=ReasoningRuleScope.DOMAIN, domain_id="domain:languages",
        category=ReasoningRuleCategory.INFERENCE, status=ReasoningRuleStatus.ENABLED,
        priority=770, risk_level=ReasoningRiskLevel.LOW,
    ))
    res_sr = rule_sr.evaluate(ReasoningRuleContext(reasoning_id="r-sr", timestamp=NOW, metadata={"material": {"items": [{"id": "v1", "due": True}]}}))
    assert res_sr.status == ReasoningRuleResultStatus.APPLIED

    # 2. LearningLoadRule
    rule_ll = LearningLoadRule(definition=DomainReasoningRuleDefinition(
        id="languages.learning_load", name="LearningLoadRule", version="1.0.0",
        scope=ReasoningRuleScope.DOMAIN, domain_id="domain:languages",
        category=ReasoningRuleCategory.INFERENCE, status=ReasoningRuleStatus.ENABLED,
        priority=780, risk_level=ReasoningRiskLevel.LOW,
    ))
    res_ll = rule_ll.evaluate(ReasoningRuleContext(reasoning_id="r-ll", timestamp=NOW, metadata={"material": {"available_time": 25}}))
    assert res_ll.status == ReasoningRuleResultStatus.APPLIED

    # 3. GoalAlignmentRule
    rule_ga = GoalAlignmentRule(definition=DomainReasoningRuleDefinition(
        id="languages.goal_alignment", name="GoalAlignmentRule", version="1.0.0",
        scope=ReasoningRuleScope.DOMAIN, domain_id="domain:languages",
        category=ReasoningRuleCategory.INFERENCE, status=ReasoningRuleStatus.ENABLED,
        priority=790, risk_level=ReasoningRiskLevel.LOW,
    ))
    res_ga = rule_ga.evaluate(ReasoningRuleContext(reasoning_id="r-ga", timestamp=NOW, metadata={"material": {"goals": [{"id": "g1"}]}}))
    assert res_ga.status == ReasoningRuleResultStatus.APPLIED

    # 4. ProgressionEvidenceRule
    rule_pe = ProgressionEvidenceRule(definition=DomainReasoningRuleDefinition(
        id="languages.progression_evidence", name="ProgressionEvidenceRule", version="1.0.0",
        scope=ReasoningRuleScope.DOMAIN, domain_id="domain:languages",
        category=ReasoningRuleCategory.EPISTEMIC, status=ReasoningRuleStatus.ENABLED,
        priority=800, risk_level=ReasoningRiskLevel.LOW,
    ))
    res_pe = rule_pe.evaluate(ReasoningRuleContext(reasoning_id="r-pe", timestamp=NOW, metadata={"material": {"current_evidence": [{"score": 0.8}]}}))
    assert res_pe.status == ReasoningRuleResultStatus.APPLIED

    # 5. CertificationTemporalRule
    rule_ct = CertificationTemporalRule(definition=DomainReasoningRuleDefinition(
        id="languages.certification_temporal", name="CertificationTemporalRule", version="1.0.0",
        scope=ReasoningRuleScope.DOMAIN, domain_id="domain:languages",
        category=ReasoningRuleCategory.TEMPORALITY, status=ReasoningRuleStatus.ENABLED,
        priority=810, risk_level=ReasoningRiskLevel.LOW,
    ))
    res_ct = rule_ct.evaluate(ReasoningRuleContext(reasoning_id="r-ct", timestamp=NOW, metadata={"material": {"sources": [{"source_type": "official"}]}}))
    assert res_ct.status == ReasoningRuleResultStatus.APPLIED

    # 6. CulturalContextEvidenceRule
    rule_cc = CulturalContextEvidenceRule(definition=DomainReasoningRuleDefinition(
        id="languages.cultural_context_evidence", name="CulturalContextEvidenceRule", version="1.0.0",
        scope=ReasoningRuleScope.DOMAIN, domain_id="domain:languages",
        category=ReasoningRuleCategory.EPISTEMIC, status=ReasoningRuleStatus.ENABLED,
        priority=820, risk_level=ReasoningRiskLevel.LOW,
    ))
    res_cc = rule_cc.evaluate(ReasoningRuleContext(reasoning_id="r-cc", timestamp=NOW, metadata={"material": {"claim": "Tendency in region"}}))
    assert res_cc.status == ReasoningRuleResultStatus.APPLIED

    # 7. LanguageMemoryConsentRule
    rule_mc = LanguageMemoryConsentRule(definition=DomainReasoningRuleDefinition(
        id="languages.language_memory_consent", name="LanguageMemoryConsentRule", version="1.0.0",
        scope=ReasoningRuleScope.DOMAIN, domain_id="domain:languages",
        category=ReasoningRuleCategory.SAFETY, status=ReasoningRuleStatus.ENABLED,
        priority=830, risk_level=ReasoningRiskLevel.LOW,
    ))
    res_mc = rule_mc.evaluate(ReasoningRuleContext(reasoning_id="r-mc", timestamp=NOW, metadata={"material": {"session_only": True}}))
    assert res_mc.status == ReasoningRuleResultStatus.APPLIED


def test_build_languages_rules_exact_14() -> None:
    """Verify build_languages_rules returns exactly 14 rules in canonical catalog order."""
    rules = build_languages_rules()
    assert len(rules) == 14
    rule_ids = tuple(r.definition.id for r in rules)
    assert rule_ids == CANONICAL_LANGUAGES_RULE_IDS
