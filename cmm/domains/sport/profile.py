"""Phase 10.28 — Sport Domain Profile.

A structured ``DomainProfileDefinition`` for sport:
high athletic discipline, progression analysis, load tracking, recovery review,
injury risk signals without diagnosis, authorized Health constraint integration,
fail-closed permission boundaries, and no autonomous medical or external calendar actions.
"""

from __future__ import annotations

from cmm.cognitive.enums import SensitivityLevel
from cmm.domains.enums import DomainReasoningDepth
from cmm.domains.profile_contracts import (
    DomainMemoryPolicy,
    DomainPresentationPolicy,
    DomainProductionPolicy,
    DomainProfileDefinition,
    DomainQuestionPolicy,
    DomainTemporalPolicy,
)
from cmm.domains.sport.catalog import (
    CANONICAL_SPORT_RULE_IDS,
    SPORT_RESOURCE_KINDS,
)

SPORT_PROFILE_ID = "sport.profile"
SPORT_PROFILE_NAME = "SportProfile"

SPORT_PROHIBITED_ACTIONS: tuple[str, ...] = (
    "direct_memory_write",
    "silent_memory_persistence",
    "clinical_diagnosis",
    "treatment_modification",
    "high_risk_medical_recommendation",
    "direct_calendar_mutation",
    "unauthorized_health_access",
    "external_communication",
    "contracting",
    "payment",
    "permission_modification",
    "shell_execution",
)


def build_sport_profile() -> DomainProfileDefinition:
    """Build the ``SportProfile`` deterministically."""
    return DomainProfileDefinition(
        id=SPORT_PROFILE_ID,
        domain_id="domain:sport",
        profile_name=SPORT_PROFILE_NAME,
        required_rules=CANONICAL_SPORT_RULE_IDS,
        optional_rules=(),
        prohibited_rules=(),
        allowed_resource_kinds=SPORT_RESOURCE_KINDS,
        priority_resource_kinds=(
            "resource.workout_log",
            "resource.training_plan",
            "resource.wearable_data",
            "resource.body_measurement",
        ),
        prohibited_resource_kinds=(),
        minimum_confidence=0.7,
        reasoning_depth=DomainReasoningDepth.STANDARD,
        allowed_inferences=(
            "training_load_calculation",
            "progressive_overload_comparison",
            "readiness_assessment",
            "injury_risk_signal",
            "measurement_trend",
            "health_constraint_incorporation",
            "schedule_proposal",
        ),
        prohibited_inferences=(
            "clinical_injury_diagnosis",
            "medical_treatment_modification",
            "high_risk_medical_recommendation",
            "silent_memory_persistence",
            "direct_calendar_mutation",
        ),
        maximum_questions=5,
        escalation_rules=(
            "sport.rule.injury_signal",
            "sport.rule.health_constraint",
        ),
        prohibited_actions=SPORT_PROHIBITED_ACTIONS,
        question_policy=DomainQuestionPolicy(
            maximum_questions=5,
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
                "training_and_activity_context",
                "evidence_and_observations",
                "load_and_recovery_analysis",
                "health_constraints_and_boundaries",
                "recommended_next_steps",
            ),
            optional_sections=(
                "measurement_trends",
                "schedule_proposal",
                "risk_signals",
                "questions_for_coaches",
            ),
            suppressible_sections=(),
            preferred_section_order=(
                "objective",
                "training_and_activity_context",
                "evidence_and_observations",
                "load_and_recovery_analysis",
                "health_constraints_and_boundaries",
                "recommended_next_steps",
            ),
            protected_terms=(
                "training_load",
                "progressive_overload",
                "readiness_state",
                "injury_signal",
                "health_constraint",
                "schedule_proposal",
            ),
            term_glosses={
                "training_load": "evaluated volume, intensity and frequency of training",
                "progressive_overload": "comparison between baseline and proposed training progression",
                "readiness_state": "mutable, time-bound assessment of physical recovery and fatigue",
                "injury_signal": "athletic risk signal requiring load adjustment or check, not a diagnosis",
                "health_constraint": "authorized functional limitation provided from Health domain",
                "schedule_proposal": "proposed session timing requiring explicit approval for calendar mutation",
            },
            preferred_components=(
                "objective",
                "training_and_activity_context",
                "load_and_recovery_analysis",
                "health_constraints_and_boundaries",
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
            sensitivity_limit=SensitivityLevel.SENSITIVE,
        ),
        temporal_policy=DomainTemporalPolicy(
            require_current_information=True,
            allow_historical_information=True,
            require_temporal_provenance=True,
            allow_future_projection=False,
        ),
        production_policy=DomainProductionPolicy(
            allow_draft=True,
            allow_final=False,
            allow_external_action=False,
            require_review=True,
            require_validation=True,
            maximum_output_items=64,
        ),
    )


__all__ = [
    "SPORT_PROFILE_ID",
    "SPORT_PROFILE_NAME",
    "SPORT_PROHIBITED_ACTIONS",
    "build_sport_profile",
]
