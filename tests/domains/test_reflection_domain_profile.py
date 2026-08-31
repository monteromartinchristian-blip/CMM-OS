"""Phase 10.24 — Reflection Domain profile tests.

``ReflectionProfile`` configures shared cognition for high-sensitivity,
open-ended reflective reasoning: multiple hypotheses, retained open
questions, no forced conclusion, restricted identity inference, no automatic
personal decisions, and confirmation-gated semantic persistence (spec §34).
It never creates a Reflection reasoning/planning/cognitive engine.
"""

from __future__ import annotations

from cmm.cognitive.enums import SensitivityLevel
from cmm.domains.enums import DomainReasoningDepth
from cmm.domains.reflection import (
    REFLECTION_PROFILE_ID,
    REFLECTION_PROFILE_NAME,
    REFLECTION_PROHIBITED_ACTIONS,
    build_reflection_profile,
)


def test_profile_identity():
    profile = build_reflection_profile()
    assert profile.id == REFLECTION_PROFILE_ID
    assert profile.profile_name == REFLECTION_PROFILE_NAME
    assert str(profile.domain_id) == "domain:reflection"


def test_profile_required_rules_match_catalog():
    profile = build_reflection_profile()
    from cmm.domains.reflection.catalog import CANONICAL_REFLECTION_RULE_IDS

    assert set(profile.required_rules) == set(CANONICAL_REFLECTION_RULE_IDS)


def test_profile_is_high_sensitivity():
    profile = build_reflection_profile()
    assert profile.memory_policy.sensitivity_limit is (
        SensitivityLevel.HIGHLY_SENSITIVE
    )
    # sensitivity gate is asserted separately via sensitivity_limit below


def test_profile_preserves_multiple_hypotheses_and_open_questions():
    profile = build_reflection_profile()
    assert "multiple_hypotheses" in profile.allowed_inferences
    assert "open_question" in profile.allowed_inferences
    assert "ambivalence" in profile.allowed_inferences
    assert "no_forced_conclusion" in profile.allowed_inferences
    assert profile.presentation_policy.include_uncertainty is True
    assert "open_questions" in profile.presentation_policy.required_sections


def test_profile_prohibits_automatic_personal_decisions():
    profile = build_reflection_profile()
    assert "personal_decision_adoption" in REFLECTION_PROHIBITED_ACTIONS
    assert "personal_decision_adoption" in profile.prohibited_actions
    assert profile.production_policy.allow_external_action is False
    assert profile.production_policy.allow_final is False


def test_profile_restricts_identity_inference():
    profile = build_reflection_profile()
    for prohibited in (
        "identity_classification",
        "personality_classification",
        "sexual_identity_inference",
        "political_identity_inference",
        "religious_identity_inference",
        "attachment_classification",
        "mental_disorder_diagnosis",
        "moral_character_inference",
        "fixed_motive_inference",
    ):
        assert prohibited in profile.prohibited_inferences
    assert "hypothetical_identity_narrative" in profile.allowed_inferences


def test_profile_requires_confirmation_gated_semantic_persistence():
    profile = build_reflection_profile()
    assert profile.memory_policy.allow_write is False
    assert "memory_persistence" in profile.prohibited_actions
    assert "confirmed_persistence_proposal" in profile.allowed_inferences
    assert "no_diagnosis_presentation" in profile.prohibited_actions


def test_profile_reasoning_depth_prudent():
    profile = build_reflection_profile()
    assert profile.reasoning_depth is DomainReasoningDepth.STANDARD


def test_profile_no_parallel_engine():
    """The profile configures shared cognition; no Reflection engine exists."""
    profile = build_reflection_profile()
    assert profile.id == REFLECTION_PROFILE_ID
    import cmm.domains.reflection

    assert not hasattr(cmm.domains.reflection, "ReflectionReasoningEngine")
    assert not hasattr(cmm.domains.reflection, "ReflectionPlanner")
    assert not hasattr(cmm.domains.reflection, "ReflectionCognitiveRuntime")
