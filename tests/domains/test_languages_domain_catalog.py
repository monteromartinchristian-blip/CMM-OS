"""Tests for Phase 10.26 Languages Domain Catalog."""

from __future__ import annotations

from cmm.domains.languages.catalog import (
    CANONICAL_LANGUAGES_ENTITY_TYPES,
    CANONICAL_LANGUAGES_OPERATION_IDS,
    CANONICAL_LANGUAGES_RESOURCE_IDS,
    CANONICAL_LANGUAGES_RULE_IDS,
    CANONICAL_LANGUAGES_RULE_NAMES,
    CANONICAL_LANGUAGES_WORKFLOW_IDS,
    CANONICAL_LANGUAGES_WORKFLOW_NAMES,
    LANGUAGES_RESOURCE_KINDS,
    LANGUAGES_WORKFLOW_NAMES_BY_ID,
)


def test_canonical_catalog_counts() -> None:
    """Verify exact counts of canonical catalog items."""
    assert len(CANONICAL_LANGUAGES_ENTITY_TYPES) == 16
    assert len(CANONICAL_LANGUAGES_RESOURCE_IDS) == 15
    assert len(CANONICAL_LANGUAGES_RULE_IDS) == 14
    assert len(CANONICAL_LANGUAGES_RULE_NAMES) == 14
    assert len(CANONICAL_LANGUAGES_OPERATION_IDS) == 15
    assert len(CANONICAL_LANGUAGES_WORKFLOW_IDS) == 9
    assert len(CANONICAL_LANGUAGES_WORKFLOW_NAMES) == 9


def test_canonical_catalog_uniqueness() -> None:
    """Verify all canonical sets contain no duplicates."""
    for values in (
        CANONICAL_LANGUAGES_ENTITY_TYPES,
        CANONICAL_LANGUAGES_RESOURCE_IDS,
        CANONICAL_LANGUAGES_RULE_IDS,
        CANONICAL_LANGUAGES_RULE_NAMES,
        CANONICAL_LANGUAGES_OPERATION_IDS,
        CANONICAL_LANGUAGES_WORKFLOW_IDS,
        CANONICAL_LANGUAGES_WORKFLOW_NAMES,
    ):
        assert len(values) == len(set(values))


def test_canonical_catalog_prefixes() -> None:
    """Verify namespaces and prefixes for resources, rules, operations, workflows."""
    assert all(v.startswith("languages.") for v in CANONICAL_LANGUAGES_RESOURCE_IDS)
    assert all(v.startswith("languages.") for v in CANONICAL_LANGUAGES_RULE_IDS)
    assert all(v.startswith("languages.") for v in CANONICAL_LANGUAGES_OPERATION_IDS)
    assert all(v.startswith("languages.") for v in CANONICAL_LANGUAGES_WORKFLOW_IDS)
    assert "languages.progress_checkpoint" in CANONICAL_LANGUAGES_WORKFLOW_IDS


def test_canonical_entities_exact() -> None:
    """Verify exact 16 entities in canonical order."""
    expected = (
        "language",
        "language_variety",
        "skill_dimension",
        "language_goal",
        "proficiency_framework",
        "proficiency_record",
        "assessment_evidence",
        "practice_session",
        "exercise",
        "observed_error",
        "error_pattern",
        "vocabulary_item",
        "grammar_topic",
        "certification_target",
        "review_item",
        "learning_plan",
    )
    assert CANONICAL_LANGUAGES_ENTITY_TYPES == expected


def test_canonical_resources_and_kinds() -> None:
    """Verify exact 15 resources and derived kinds."""
    expected_resources = (
        "languages.user_message",
        "languages.conversation",
        "languages.writing_sample",
        "languages.audio_transcript",
        "languages.exercise_result",
        "languages.assessment_result",
        "languages.language_plan",
        "languages.lesson_material",
        "languages.vocabulary_list",
        "languages.language_reference",
        "languages.certification_guide",
        "languages.official_certification_source",
        "languages.calendar_event",
        "languages.memory_entry",
        "languages.domain_result",
    )
    assert CANONICAL_LANGUAGES_RESOURCE_IDS == expected_resources
    assert LANGUAGES_RESOURCE_KINDS == tuple(r.split(".", 1)[1] for r in expected_resources)


def test_canonical_rules_and_class_names() -> None:
    """Verify exact 14 rules and corresponding class names."""
    expected_rules = (
        "languages.language_level_evidence",
        "languages.skill_separation",
        "languages.language_variety_validity",
        "languages.proficiency_framework",
        "languages.error_pattern_evidence",
        "languages.correction_priority",
        "languages.adaptive_difficulty",
        "languages.spaced_review",
        "languages.learning_load",
        "languages.goal_alignment",
        "languages.progression_evidence",
        "languages.certification_temporal",
        "languages.cultural_context_evidence",
        "languages.language_memory_consent",
    )
    expected_names = (
        "LanguageLevelEvidenceRule",
        "SkillSeparationRule",
        "LanguageVarietyValidityRule",
        "ProficiencyFrameworkRule",
        "ErrorPatternEvidenceRule",
        "CorrectionPriorityRule",
        "AdaptiveDifficultyRule",
        "SpacedReviewRule",
        "LearningLoadRule",
        "GoalAlignmentRule",
        "ProgressionEvidenceRule",
        "CertificationTemporalRule",
        "CulturalContextEvidenceRule",
        "LanguageMemoryConsentRule",
    )
    assert CANONICAL_LANGUAGES_RULE_IDS == expected_rules
    assert CANONICAL_LANGUAGES_RULE_NAMES == expected_names


def test_canonical_operations_exact() -> None:
    """Verify exact 15 operations in canonical order."""
    expected_ops = (
        "languages.assess_sample",
        "languages.update_level_evidence",
        "languages.create_learning_plan",
        "languages.generate_lesson",
        "languages.generate_exercises",
        "languages.review_exercise",
        "languages.review_writing",
        "languages.generate_conversation_turn",
        "languages.generate_roleplay_turn",
        "languages.review_speaking",
        "languages.review_errors",
        "languages.track_vocabulary",
        "languages.plan_review_schedule",
        "languages.prepare_certification",
        "languages.generate_progress_review",
    )
    assert CANONICAL_LANGUAGES_OPERATION_IDS == expected_ops


def test_canonical_workflows_and_display_names() -> None:
    """Verify exact 9 workflows and display names."""
    expected_workflows = (
        "languages.language_onboarding",
        "languages.proficiency_assessment",
        "languages.adaptive_language_lesson",
        "languages.conversation_roleplay_practice",
        "languages.writing_review",
        "languages.error_remediation",
        "languages.vocabulary_spaced_review",
        "languages.certification_preparation",
        "languages.progress_checkpoint",
    )
    expected_names_by_id = {
        "languages.language_onboarding": "Language Onboarding",
        "languages.proficiency_assessment": "Proficiency Assessment",
        "languages.adaptive_language_lesson": "Adaptive Language Lesson",
        "languages.conversation_roleplay_practice": "Conversation & Roleplay Practice",
        "languages.writing_review": "Writing Review",
        "languages.error_remediation": "Error Remediation",
        "languages.vocabulary_spaced_review": "Vocabulary & Spaced Review",
        "languages.certification_preparation": "Certification Preparation",
        "languages.progress_checkpoint": "Progress Review",
    }
    assert CANONICAL_LANGUAGES_WORKFLOW_IDS == expected_workflows
    assert LANGUAGES_WORKFLOW_NAMES_BY_ID == expected_names_by_id
    assert CANONICAL_LANGUAGES_WORKFLOW_NAMES == tuple(
        expected_names_by_id[w] for w in expected_workflows
    )
