"""Tests for Phase 10.26 Languages Domain Profile."""

from __future__ import annotations

from cmm.cognitive.enums import SensitivityLevel
from cmm.domains.languages.catalog import (
    CANONICAL_LANGUAGES_RULE_IDS,
    LANGUAGES_RESOURCE_KINDS,
)
from cmm.domains.languages.profile import (
    LANGUAGES_PEDAGOGICAL_MODES,
    LANGUAGES_PROFILE_ID,
    LANGUAGES_PROFILE_NAME,
    LANGUAGES_PROHIBITED_ACTIONS,
    build_languages_profile,
)
from cmm.domains.profile_contracts import DomainProfileDefinition


def test_build_languages_profile_structure() -> None:
    """Verify standard profile structure and fields."""
    profile = build_languages_profile()
    assert isinstance(profile, DomainProfileDefinition)
    assert profile.id == LANGUAGES_PROFILE_ID == "languages.profile"
    assert profile.domain_id == "domain:languages"
    assert profile.profile_name == LANGUAGES_PROFILE_NAME == "LanguageLearningProfile"
    assert tuple(profile.required_rules) == CANONICAL_LANGUAGES_RULE_IDS
    assert tuple(profile.allowed_resource_kinds) == LANGUAGES_RESOURCE_KINDS
    assert profile.permissions is None


def test_languages_profile_pedagogical_modes() -> None:
    """Verify pedagogical modes configured in profile."""
    expected_modes = (
        "teach",
        "practice",
        "assess",
        "review",
        "certification",
        "immersion",
    )
    assert LANGUAGES_PEDAGOGICAL_MODES == expected_modes
    profile = build_languages_profile()
    assert tuple(profile.metadata["pedagogical_modes"]) == expected_modes


def test_languages_profile_memory_policy() -> None:
    """Verify opt-in longitudinal memory policy."""
    profile = build_languages_profile()
    mp = profile.memory_policy
    assert mp.allow_read is True
    assert mp.allow_write is None
    assert mp.allow_long_term is True
    assert mp.allow_cross_domain is False
    assert mp.retention_scope == "long_term"
    assert mp.sensitivity_limit is SensitivityLevel.PERSONAL


def test_languages_profile_production_policy() -> None:
    """Verify production policy allows tutoring output without external actions."""
    profile = build_languages_profile()
    pp = profile.production_policy
    assert pp.allow_draft is True
    assert pp.allow_final is True
    assert pp.allow_external_action is False
    assert pp.require_review is False
    assert pp.require_validation is True
    assert pp.maximum_output_items == 128


def test_languages_profile_prohibited_actions_and_inferences() -> None:
    """Verify prohibited actions and inferences."""
    profile = build_languages_profile()
    for action in (
        "direct_memory_write",
        "silent_memory_persistence",
        "unconfirmed_progress_persistence",
        "unconfirmed_proficiency_persistence",
        "unconfirmed_error_pattern_persistence",
        "calendar_modification",
        "schedule_modification",
        "task_creation",
        "external_communication",
        "exam_registration",
        "application_submission",
        "payment",
        "purchase",
        "publication",
        "permission_modification",
        "shell_execution",
    ):
        assert action in profile.prohibited_actions
        assert action in LANGUAGES_PROHIBITED_ACTIONS

    for inf in (
        "single_sample_to_certified",
        "single_sample_to_stable_proficiency",
        "cross_skill_inflation",
        "variety_difference_to_error",
        "transcript_to_pronunciation",
        "single_score_to_stable_progression",
        "exam_readiness_to_general_proficiency",
        "silent_framework_identity",
        "silent_memory_persistence",
    ):
        assert inf in profile.prohibited_inferences


def test_languages_profile_composition_non_erasure() -> None:
    """Prove that permissions=None does not erase later scoped permission grants."""
    profile = build_languages_profile()
    assert profile.permissions is None
