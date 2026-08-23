"""Phase 10.26 — Canonical Languages Domain Catalog.

Single source of truth for the structural IDs of the Languages Domain.

All other modules (definition, resources, profile, rules, operations,
workflows, bootstrap, integration) must import from this module rather than
re-declaring the same tuples.  This prevents catalog divergence.

The canonical entity types are semantic vocabulary surfaced through shared
Entity / KnowledgeItem bindings and the ``entity_types`` field of Languages
resource definitions.  They are not new persistent classes.

Canonical identity (frozen design §5):

    domain:languages / namespace ``languages.*`` / version ``1.0.0``

Counts are frozen acceptance criteria (frozen design §91):
16 entities, 15 resources, 14 rules, 15 operations, 9 workflows.
"""

from __future__ import annotations

# ── Canonical languages entity semantics ─────────────────────────────────────

CANONICAL_LANGUAGES_ENTITY_TYPES: tuple[str, ...] = (
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

# ── Canonical resource IDs ────────────────────────────────────────────────────
# ``domain:languages`` yields slug ``languages``; the shared resource and
# operation contracts require the domain prefix on the canonical IDs.
# ``domain_result`` is the authorized cross-domain projection boundary; a
# ``memory_entry`` is provenance, not current truth; ``official_certification_source``
# is read-only official source reference, not external-search authorization.

CANONICAL_LANGUAGES_RESOURCE_IDS: tuple[str, ...] = (
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

LANGUAGES_RESOURCE_KINDS: tuple[str, ...] = tuple(
    resource_id.split(".", 1)[1]
    for resource_id in CANONICAL_LANGUAGES_RESOURCE_IDS
)

# ── Canonical rule IDs ────────────────────────────────────────────────────────

CANONICAL_LANGUAGES_RULE_IDS: tuple[str, ...] = (
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

# Canonical rule class names (frozen design §15).  The classes are declared in
# ``rules.py`` under exactly these names.
CANONICAL_LANGUAGES_RULE_NAMES: tuple[str, ...] = (
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

# ── Canonical operation IDs ───────────────────────────────────────────────────
# All fifteen operations are analysis, planning, or preparation operations.

CANONICAL_LANGUAGES_OPERATION_IDS: tuple[str, ...] = (
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

# ── Canonical workflow IDs ────────────────────────────────────────────────────

CANONICAL_LANGUAGES_WORKFLOW_IDS: tuple[str, ...] = (
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

# Canonical workflow display names (implementation plan Task 1), keyed by
# workflow ID.  Names are derived from this mapping, never redeclared.
LANGUAGES_WORKFLOW_NAMES_BY_ID: dict[str, str] = {
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

CANONICAL_LANGUAGES_WORKFLOW_NAMES: tuple[str, ...] = tuple(
    LANGUAGES_WORKFLOW_NAMES_BY_ID[workflow_id]
    for workflow_id in CANONICAL_LANGUAGES_WORKFLOW_IDS
)

__all__ = [
    "CANONICAL_LANGUAGES_ENTITY_TYPES",
    "CANONICAL_LANGUAGES_OPERATION_IDS",
    "CANONICAL_LANGUAGES_RESOURCE_IDS",
    "CANONICAL_LANGUAGES_RULE_IDS",
    "CANONICAL_LANGUAGES_RULE_NAMES",
    "CANONICAL_LANGUAGES_WORKFLOW_IDS",
    "CANONICAL_LANGUAGES_WORKFLOW_NAMES",
    "LANGUAGES_RESOURCE_KINDS",
    "LANGUAGES_WORKFLOW_NAMES_BY_ID",
]
