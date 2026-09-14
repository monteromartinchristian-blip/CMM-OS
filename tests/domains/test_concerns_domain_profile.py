"""Phase 10.25 — Concerns Domain profile tests.

``ConcernSupportProfile`` configures shared cognition for high-sensitivity
concern support: all 14 required rules, high uncertainty tolerance, low
default action pressure and alarm, evidence-calibrated reassurance,
material-only questioning, grounded-opinion willingness, cross-domain
awareness, no automatic decisions, and no memory mutation.  It never creates a
concern reasoning/planning/cognitive engine and never encodes a persona.
"""

from __future__ import annotations

from cmm.cognitive.enums import SensitivityLevel
from cmm.domains.concerns.catalog import CANONICAL_CONCERNS_RULE_IDS
from cmm.domains.concerns.profile import (
    CONCERNS_PROFILE_ID,
    CONCERNS_PROFILE_NAME,
    CONCERNS_PROHIBITED_ACTIONS,
    build_concerns_profile,
)


def test_profile_identity():
    profile = build_concerns_profile()
    assert profile.id == CONCERNS_PROFILE_ID
    assert profile.id == "concerns.profile"
    assert profile.profile_name == CONCERNS_PROFILE_NAME
    assert profile.profile_name == "ConcernSupportProfile"
    assert str(profile.domain_id) == "domain:concerns"


def test_profile_required_rules_match_catalog():
    profile = build_concerns_profile()
    assert set(profile.required_rules) == set(CANONICAL_CONCERNS_RULE_IDS)
    assert len(profile.required_rules) == 14


def test_profile_is_high_sensitivity():
    profile = build_concerns_profile()
    assert profile.memory_policy.sensitivity_limit is (
        SensitivityLevel.HIGHLY_SENSITIVE
    )
    assert profile.memory_policy.allow_write is False


def test_profile_metadata_semantics():
    """The frozen profile metadata block (implementation plan Task 2)."""
    profile = build_concerns_profile()
    metadata = profile.metadata
    assert metadata.get("contextual_sensitivity") == "high"
    assert metadata.get("epistemic_discipline") == "high"
    assert metadata.get("uncertainty_tolerance") == "high"
    assert metadata.get("emotional_context_awareness") == "high"
    assert metadata.get("interpretive_openness") == "moderate_high"
    assert metadata.get("default_action_pressure") == "low"
    assert metadata.get("default_alarm") == "low"
    assert metadata.get("reassurance_policy") == "evidence_calibrated"
    assert metadata.get("grounded_opinion_allowed") is True
    assert metadata.get("question_policy") == "material_only"
    assert metadata.get("cross_domain_awareness") is True


def test_profile_uncertainty_allowed_and_action_pressure_low():
    profile = build_concerns_profile()
    assert "uncertainty" in profile.allowed_inferences
    assert "no_forced_action" in profile.allowed_inferences
    assert "no_forced_closure" in profile.allowed_inferences
    assert "evidence_calibrated_reassurance" in profile.allowed_inferences
    assert "grounded_opinion" in profile.allowed_inferences
    # no automatic decisions / no diagnosis / no pathologizing recurrence
    for prohibited in (
        "decision_adoption",
        "personal_decision_inference",
        "mental_disorder_diagnosis",
        "psychological_diagnosis",
        "third_party_diagnosis",
        "repetition_pathology_inference",
        "psychiatric_label_inference",
        "sensitive_inference_persist",
    ):
        assert prohibited in profile.prohibited_inferences


def test_profile_prohibits_automatic_external_action():
    profile = build_concerns_profile()
    assert profile.production_policy.allow_external_action is False
    assert profile.production_policy.allow_final is False
    for prohibited in (
        "external_communication",
        "message_send",
        "appointment_booking",
        "calendar_modification",
        "semantic_memory_write",
        "monitoring_start",
    ):
        assert prohibited in profile.prohibited_actions


def test_profile_questioning_material_only():
    profile = build_concerns_profile()
    question = profile.question_policy
    # material-only: a bounded number of targeted questions, deduplicated,
    # never an open-ended therapeutic interview ritual.
    assert question.maximum_questions <= 3
    assert question.require_deduplication is True
    assert question.allow_follow_up is True


def test_profile_reasoning_depth():
    from cmm.domains.enums import DomainReasoningDepth

    profile = build_concerns_profile()
    assert profile.reasoning_depth is DomainReasoningDepth.STANDARD


def test_profile_no_persona_engine_and_no_parallel_infrastructure():
    profile = build_concerns_profile()
    # No fixed tone/warmth/emoji/rhetorical-style semantics anywhere in the
    # profile contract surface (those belong to shared presentation/Phase 11).
    presentation = profile.presentation_policy
    assert not hasattr(presentation, "warmth")
    assert not hasattr(presentation, "persona")
    assert not hasattr(presentation, "emoji_policy")
    import cmm.domains.concerns

    for forbidden in (
        "ConcernAgent",
        "ConcernPlanner",
        "ConcernWorkflowEngine",
        "ConcernMemoryStore",
        "ConcernKnowledgeStore",
        "ConcernKnowledgeGraph",
        "ConcernQuestionEngine",
        "ConcernConfidenceEngine",
        "ConcernConversationEngine",
    ):
        assert not hasattr(cmm.domains.concerns, forbidden)


def test_prohibited_actions_surface_is_fail_closed():
    expected_core = {
        "personal_decision_adoption",
        "decision_adoption",
        "semantic_memory_write",
        "memory_persistence",
        "unconfirmed_memory_persistence",
        "diagnosis_presentation",
        "psychological_diagnosis",
        "external_communication",
        "message_send",
        "email_send",
        "calendar_modification",
        "task_creation",
        "schedule_modification",
        "content_publication",
        "purchase",
        "form_submission",
        "knowledge_delete",
        "export",
        "shell_execution",
        "sensitive_inference_persist",
    }
    assert expected_core <= set(CONCERNS_PROHIBITED_ACTIONS)
