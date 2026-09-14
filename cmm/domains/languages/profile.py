"""Phase 10.26 — Languages Domain Profile.

A structured ``DomainProfileDefinition`` for language learning:
high epistemic discipline, skill separation, variety validity, adaptive
difficulty, multi-language/multi-goal awareness, selective correction density,
no automatic certified proficiency inference, no transcript-only pronunciation
assessment, no silent memory persistence, and no direct calendar mutation or
exam registration.

Configures shared cognition through shared profile contracts; does not create
a cognitive engine and never encodes a communication persona.
"""

from __future__ import annotations

from cmm.cognitive.enums import SensitivityLevel
from cmm.domains.enums import DomainReasoningDepth
from cmm.domains.languages.catalog import CANONICAL_LANGUAGES_RULE_IDS
from cmm.domains.languages.resources import LANGUAGES_RESOURCE_KINDS
from cmm.domains.profile_contracts import (
    DomainMemoryPolicy,
    DomainPresentationPolicy,
    DomainProductionPolicy,
    DomainProfileDefinition,
    DomainQuestionPolicy,
    DomainTemporalPolicy,
)

LANGUAGES_PROFILE_ID = "languages.profile"
LANGUAGES_PROFILE_NAME = "LanguageLearningProfile"

LANGUAGES_PEDAGOGICAL_MODES: tuple[str, ...] = (
    "teach",
    "practice",
    "assess",
    "review",
    "certification",
    "immersion",
)

LANGUAGES_PROHIBITED_ACTIONS: tuple[str, ...] = (
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
)


def build_languages_profile() -> DomainProfileDefinition:
    """Build the ``LanguageLearningProfile`` deterministically."""
    return DomainProfileDefinition(
        id=LANGUAGES_PROFILE_ID,
        domain_id="domain:languages",
        profile_name=LANGUAGES_PROFILE_NAME,
        required_rules=CANONICAL_LANGUAGES_RULE_IDS,
        optional_rules=(),
        prohibited_rules=(),
        allowed_resource_kinds=LANGUAGES_RESOURCE_KINDS,
        priority_resource_kinds=("user_message", "conversation", "writing_sample"),
        prohibited_resource_kinds=(),
        minimum_confidence=0.6,
        reasoning_depth=DomainReasoningDepth.STANDARD,
        allowed_inferences=(
            "observed_performance",
            "estimated_proficiency",
            "skill_specific_evidence",
            "valid_language_variety",
            "observed_error",
            "candidate_error_pattern",
            "supported_error_pattern",
            "short_term_improvement",
            "stable_improvement",
            "plateau",
            "possible_regression",
            "insufficient_evidence",
            "certification_readiness",
            "communicative_effectiveness",
            "scaffolding_need",
            "spaced_review_priority",
        ),
        prohibited_inferences=(
            "single_sample_to_certified",
            "single_sample_to_stable_proficiency",
            "cross_skill_inflation",
            "variety_difference_to_error",
            "transcript_to_pronunciation",
            "single_score_to_stable_progression",
            "exam_readiness_to_general_proficiency",
            "silent_framework_identity",
            "silent_memory_persistence",
        ),
        maximum_questions=3,
        escalation_rules=(
            "languages.language_level_evidence",
            "languages.skill_separation",
            "languages.language_variety_validity",
        ),
        prohibited_actions=LANGUAGES_PROHIBITED_ACTIONS,
        question_policy=DomainQuestionPolicy(
            maximum_questions=3,
            allow_follow_up=True,
            require_deduplication=True,
            allow_clarification=True,
            stop_on_blocking_gap=True,
        ),
        presentation_policy=DomainPresentationPolicy(
            detail_level="detailed",
            include_uncertainty=True,
            include_provenance=True,
            include_alternatives=True,
            allow_speculation=False,
            require_disclaimers=True,
            required_sections=(
                "objective",
                "activity",
                "feedback",
                "evidence",
                "uncertainty",
                "next_practice",
            ),
            optional_sections=(
                "strengths",
                "observed_errors",
                "supported_patterns",
                "skill_evidence",
                "proficiency_interpretation",
                "missing_evidence",
                "progress_context",
                "external_action_state",
                "memory_state",
            ),
            suppressible_sections=(),
            preferred_section_order=(
                "objective",
                "activity",
                "feedback",
                "evidence",
                "uncertainty",
                "next_practice",
            ),
            protected_terms=(
                "certified_proficiency",
                "estimated_proficiency",
                "observed_performance",
                "valid_alternative",
                "observed_error",
                "error_pattern",
                "readiness",
                "proposal",
            ),
            term_glosses={
                "certified_proficiency": "formal credential backed by official record",
                "estimated_proficiency": "longitudinal probabilistic assessment across skills",
                "observed_performance": "performance on a specific sample or task",
                "valid_alternative": "valid variety/dialect difference, not an error",
                "observed_error": "isolated performance deviation",
                "error_pattern": "recurrent systematic difficulty across comparable contexts",
                "readiness": "task/format readiness, distinct from global proficiency",
                "proposal": "candidate action or persistence requiring explicit user consent",
            },
            preferred_components=(
                "objective",
                "activity",
                "feedback",
                "evidence",
                "uncertainty",
            ),
            preferred_views=("structured",),
            warning_position="before_content",
            allowed_output_types=("HUMAN_READABLE", "STRUCTURED"),
            preferred_output_types=("STRUCTURED",),
        ),
        memory_policy=DomainMemoryPolicy(
            allow_read=True,
            allow_write=None,
            allow_long_term=True,
            allow_cross_domain=False,
            retention_scope="long_term",
            sensitivity_limit=SensitivityLevel.PERSONAL,
        ),
        temporal_policy=DomainTemporalPolicy(
            require_current_information=False,
            allow_historical_information=True,
            require_temporal_provenance=True,
            allow_future_projection=False,
        ),
        production_policy=DomainProductionPolicy(
            allow_draft=True,
            allow_final=True,
            allow_external_action=False,
            require_review=False,
            require_validation=True,
            maximum_output_items=128,
        ),
        permissions=None,
        metadata={
            "phase": "10.26",
            "pedagogical_modes": list(LANGUAGES_PEDAGOGICAL_MODES),
            "communicative_usefulness_priority": "high",
            "correction_density_default": "selective",
            "evidence_discipline": "high",
            "skill_separation": True,
            "multi_language": True,
            "multiple_goals_per_language": True,
            "adaptive_difficulty": True,
            "cross_domain_awareness": True,
        },
    )


__all__ = [
    "LANGUAGES_PEDAGOGICAL_MODES",
    "LANGUAGES_PROFILE_ID",
    "LANGUAGES_PROFILE_NAME",
    "LANGUAGES_PROHIBITED_ACTIONS",
    "build_languages_profile",
]
