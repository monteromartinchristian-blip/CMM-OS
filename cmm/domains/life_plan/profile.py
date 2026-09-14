"""Phase 10.29 — Life Plan Domain Profile.

A structured ``DomainProfileDefinition`` for life plan:
medium- and long-term goal coordination, scenario comparisons, dependency tracking,
resource constraints (time, money, energy, capacity), explicit non-collapsible
decision states, alternative routes, plan drift analysis, and fail-closed permissions.
Prohibits autonomous external commitments, payments, silent memory persistence,
and automatic goal abandonment.
"""

from __future__ import annotations

from cmm.cognitive.enums import SensitivityLevel
from cmm.domains.enums import DomainReasoningDepth
from cmm.domains.life_plan.catalog import (
    CANONICAL_LIFE_PLAN_RULE_IDS,
    LIFE_PLAN_RESOURCE_KINDS,
)
from cmm.domains.profile_contracts import (
    DomainMemoryPolicy,
    DomainPresentationPolicy,
    DomainProductionPolicy,
    DomainProfileDefinition,
    DomainQuestionPolicy,
    DomainTemporalPolicy,
)

LIFE_PLAN_PROFILE_ID = "life-plan.profile"
LIFE_PLAN_PROFILE_NAME = "LifePlanProfile"

LIFE_PLAN_PROHIBITED_ACTIONS: tuple[str, ...] = (
    "direct_memory_write",
    "silent_memory_persistence",
    "unconfirmed_decision_promotion",
    "unconfirmed_commitment_promotion",
    "automatic_goal_abandonment",
    "direct_calendar_mutation",
    "unauthorized_cross_domain_access",
    "external_communication",
    "contracting",
    "payment",
    "permission_modification",
    "shell_execution",
)


def build_life_plan_profile() -> DomainProfileDefinition:
    """Build the ``LifePlanProfile`` deterministically."""
    return DomainProfileDefinition(
        id=LIFE_PLAN_PROFILE_ID,
        domain_id="domain:life-plan",
        profile_name=LIFE_PLAN_PROFILE_NAME,
        required_rules=CANONICAL_LIFE_PLAN_RULE_IDS,
        optional_rules=(),
        prohibited_rules=(),
        allowed_resource_kinds=LIFE_PLAN_RESOURCE_KINDS,
        priority_resource_kinds=(
            "resource.life_plan",
            "resource.goal",
            "resource.decision",
            "resource.financial_plan",
        ),
        prohibited_resource_kinds=(),
        minimum_confidence=0.7,
        reasoning_depth=DomainReasoningDepth.STANDARD,
        allowed_inferences=(
            "scenario_comparison",
            "goal_dependency_analysis",
            "resource_constraint_evaluation",
            "temporal_ordering_validation",
            "alternative_route_preservation",
            "cross_domain_impact_assessment",
            "plan_drift_detection",
            "feasibility_evaluation",
        ),
        prohibited_inferences=(
            "silent_memory_persistence",
            "unconfirmed_decision_promotion",
            "unconfirmed_commitment_promotion",
            "automatic_goal_abandonment",
            "direct_calendar_mutation",
        ),
        maximum_questions=5,
        escalation_rules=(
            "life_plan.rule.resource_constraint",
            "life_plan.rule.cross_domain_impact",
            "life_plan.rule.plan_drift",
        ),
        prohibited_actions=LIFE_PLAN_PROHIBITED_ACTIONS,
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
                "life_plan_context",
                "goals_and_dependencies",
                "scenarios_and_alternatives",
                "resource_constraints_and_feasibility",
                "decisions_and_commitments",
                "recommended_next_steps",
            ),
            optional_sections=(
                "cross_domain_impacts",
                "milestones_and_timeline",
                "plan_drift_analysis",
                "risk_summaries",
            ),
            suppressible_sections=(),
            preferred_section_order=(
                "objective",
                "life_plan_context",
                "goals_and_dependencies",
                "scenarios_and_alternatives",
                "resource_constraints_and_feasibility",
                "decisions_and_commitments",
                "recommended_next_steps",
            ),
            protected_terms=(
                "life_goal",
                "milestone",
                "scenario",
                "dependency",
                "resource_constraint",
                "decision",
                "commitment",
                "alternative_route",
                "plan_drift",
            ),
            term_glosses={
                "life_goal": "medium- or long-term objective",
                "milestone": "significant checkpoint on the timeline toward a goal",
                "scenario": "coherent set of assumptions and possibilities under evaluation",
                "dependency": "prerequisite or structural relationship between goals or milestones",
                "resource_constraint": "limitation in time, money, energy, or available capacity",
                "decision": "confirmed choice among options, distinct from preference or scenario",
                "commitment": "binding obligation, distinct from preference or scenario",
                "alternative_route": "viable parallel or contingency path toward an objective",
                "plan_drift": "divergence between planned state, confirmed decisions, and actual state",
            },
            preferred_components=(
                "objective",
                "life_plan_context",
                "goals_and_dependencies",
                "scenarios_and_alternatives",
                "resource_constraints_and_feasibility",
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
            allow_future_projection=True,
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
    "LIFE_PLAN_PROFILE_ID",
    "LIFE_PLAN_PROFILE_NAME",
    "LIFE_PLAN_PROHIBITED_ACTIONS",
    "build_life_plan_profile",
]
