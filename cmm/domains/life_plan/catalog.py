"""Phase 10.29 — Canonical Life Plan Domain Catalog.

Single source of truth for the structural IDs of the Life Plan Domain.

Counts:
13 entities, 12 resources, 8 rules, 10 operations, 7 workflows.
"""

from __future__ import annotations

CANONICAL_LIFE_PLAN_ENTITY_TYPES: tuple[str, ...] = (
    "life_goal",
    "milestone",
    "scenario",
    "dependency",
    "constraint",
    "risk",
    "decision",
    "financial_resource",
    "career_path",
    "education_path",
    "housing_goal",
    "family_goal",
    "timeline",
)

CANONICAL_LIFE_PLAN_ENTITY_IDS: tuple[str, ...] = (
    "life_plan.entity.life_goal",
    "life_plan.entity.milestone",
    "life_plan.entity.scenario",
    "life_plan.entity.dependency",
    "life_plan.entity.constraint",
    "life_plan.entity.risk",
    "life_plan.entity.decision",
    "life_plan.entity.financial_resource",
    "life_plan.entity.career_path",
    "life_plan.entity.education_path",
    "life_plan.entity.housing_goal",
    "life_plan.entity.family_goal",
    "life_plan.entity.timeline",
)

LIFE_PLAN_ENTITY_IDS: tuple[str, ...] = CANONICAL_LIFE_PLAN_ENTITY_IDS

CANONICAL_LIFE_PLAN_RESOURCE_IDS: tuple[str, ...] = (
    "life_plan.resource.life_plan",
    "life_plan.resource.financial_plan",
    "life_plan.resource.academic_plan",
    "life_plan.resource.opposition_plan",
    "life_plan.resource.health_constraints",
    "life_plan.resource.family_plan",
    "life_plan.resource.housing_plan",
    "life_plan.resource.goal",
    "life_plan.resource.decision",
    "life_plan.resource.calendar_event",
    "life_plan.resource.memory_entry",
    "life_plan.resource.user_message",
)

LIFE_PLAN_RESOURCE_IDS: tuple[str, ...] = CANONICAL_LIFE_PLAN_RESOURCE_IDS

LIFE_PLAN_RESOURCE_KINDS: tuple[str, ...] = tuple(
    resource_id.split(".", 1)[1] for resource_id in CANONICAL_LIFE_PLAN_RESOURCE_IDS
)

CANONICAL_LIFE_PLAN_RULE_IDS: tuple[str, ...] = (
    "life_plan.rule.goal_dependency",
    "life_plan.rule.scenario_consistency",
    "life_plan.rule.resource_constraint",
    "life_plan.rule.decision_status",
    "life_plan.rule.long_term_temporal",
    "life_plan.rule.alternative_route",
    "life_plan.rule.cross_domain_impact",
    "life_plan.rule.plan_drift",
)

LIFE_PLAN_RULE_IDS: tuple[str, ...] = CANONICAL_LIFE_PLAN_RULE_IDS

CANONICAL_LIFE_PLAN_RULE_NAMES: tuple[str, ...] = (
    "GoalDependencyRule",
    "ScenarioConsistencyRule",
    "ResourceConstraintRule",
    "DecisionStatusRule",
    "LongTermTemporalRule",
    "AlternativeRouteRule",
    "CrossDomainImpactRule",
    "PlanDriftRule",
)

CANONICAL_LIFE_PLAN_OPERATION_IDS: tuple[str, ...] = (
    "life_plan.build_timeline",
    "life_plan.compare_scenarios",
    "life_plan.review_goals",
    "life_plan.detect_dependencies",
    "life_plan.identify_risks",
    "life_plan.update_plan",
    "life_plan.create_milestones",
    "life_plan.generate_periodic_review",
    "life_plan.evaluate_feasibility",
    "life_plan.track_decisions",
)

LIFE_PLAN_OPERATION_IDS: tuple[str, ...] = CANONICAL_LIFE_PLAN_OPERATION_IDS

CANONICAL_LIFE_PLAN_WORKFLOW_IDS: tuple[str, ...] = (
    "life_plan.life_plan_setup",
    "life_plan.quarterly_life_review",
    "life_plan.scenario_comparison",
    "life_plan.goal_dependency_review",
    "life_plan.cross_domain_impact_review",
    "life_plan.plan_drift_review",
    "life_plan.annual_life_plan_update",
)

LIFE_PLAN_WORKFLOW_IDS: tuple[str, ...] = CANONICAL_LIFE_PLAN_WORKFLOW_IDS

__all__ = [
    "CANONICAL_LIFE_PLAN_ENTITY_IDS",
    "CANONICAL_LIFE_PLAN_ENTITY_TYPES",
    "CANONICAL_LIFE_PLAN_OPERATION_IDS",
    "CANONICAL_LIFE_PLAN_RESOURCE_IDS",
    "CANONICAL_LIFE_PLAN_RULE_IDS",
    "CANONICAL_LIFE_PLAN_RULE_NAMES",
    "CANONICAL_LIFE_PLAN_WORKFLOW_IDS",
    "LIFE_PLAN_ENTITY_IDS",
    "LIFE_PLAN_OPERATION_IDS",
    "LIFE_PLAN_RESOURCE_IDS",
    "LIFE_PLAN_RESOURCE_KINDS",
    "LIFE_PLAN_RULE_IDS",
    "LIFE_PLAN_WORKFLOW_IDS",
]
