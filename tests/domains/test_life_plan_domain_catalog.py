"""Tests for Phase 10.29 Life Plan Domain Catalog and Definition."""

from __future__ import annotations

from cmm.domains.life_plan.catalog import (
    CANONICAL_LIFE_PLAN_ENTITY_IDS,
    CANONICAL_LIFE_PLAN_ENTITY_TYPES,
    CANONICAL_LIFE_PLAN_OPERATION_IDS,
    CANONICAL_LIFE_PLAN_RESOURCE_IDS,
    CANONICAL_LIFE_PLAN_RULE_IDS,
    CANONICAL_LIFE_PLAN_RULE_NAMES,
    CANONICAL_LIFE_PLAN_WORKFLOW_IDS,
    LIFE_PLAN_ENTITY_IDS,
    LIFE_PLAN_OPERATION_IDS,
    LIFE_PLAN_RESOURCE_IDS,
    LIFE_PLAN_RESOURCE_KINDS,
    LIFE_PLAN_RULE_IDS,
    LIFE_PLAN_WORKFLOW_IDS,
)
from cmm.domains.life_plan.definition import (
    LIFE_PLAN_DOMAIN_ID,
    LIFE_PLAN_DOMAIN_VERSION,
    LIFE_PLAN_MANIFEST_ID,
    LIFE_PLAN_PERMISSION_IDS,
    LIFE_PLAN_PROFILE_NAME,
    build_life_plan_domain_definition,
)


def test_life_plan_catalog_exact_counts() -> None:
    assert len(LIFE_PLAN_ENTITY_IDS) == 13
    assert len(LIFE_PLAN_RESOURCE_IDS) == 12
    assert len(LIFE_PLAN_RULE_IDS) == 8
    assert len(LIFE_PLAN_OPERATION_IDS) == 10
    assert len(LIFE_PLAN_WORKFLOW_IDS) == 7

    assert len(CANONICAL_LIFE_PLAN_ENTITY_TYPES) == 13
    assert len(CANONICAL_LIFE_PLAN_RULE_NAMES) == 8
    assert len(LIFE_PLAN_RESOURCE_KINDS) == 12


def test_life_plan_required_cross_domain_workflow_is_inside_seven() -> None:
    assert "life_plan.cross_domain_impact_review" in LIFE_PLAN_WORKFLOW_IDS
    assert len(LIFE_PLAN_WORKFLOW_IDS) == 7


def test_life_plan_catalog_exact_ids() -> None:
    assert LIFE_PLAN_ENTITY_IDS == (
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
    assert LIFE_PLAN_ENTITY_IDS == CANONICAL_LIFE_PLAN_ENTITY_IDS
    assert CANONICAL_LIFE_PLAN_ENTITY_TYPES == (
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
    assert LIFE_PLAN_RESOURCE_IDS == (
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
    assert LIFE_PLAN_RESOURCE_IDS == CANONICAL_LIFE_PLAN_RESOURCE_IDS
    assert LIFE_PLAN_RULE_IDS == (
        "life_plan.rule.goal_dependency",
        "life_plan.rule.scenario_consistency",
        "life_plan.rule.resource_constraint",
        "life_plan.rule.decision_status",
        "life_plan.rule.long_term_temporal",
        "life_plan.rule.alternative_route",
        "life_plan.rule.cross_domain_impact",
        "life_plan.rule.plan_drift",
    )
    assert LIFE_PLAN_RULE_IDS == CANONICAL_LIFE_PLAN_RULE_IDS
    assert CANONICAL_LIFE_PLAN_RULE_NAMES == (
        "GoalDependencyRule",
        "ScenarioConsistencyRule",
        "ResourceConstraintRule",
        "DecisionStatusRule",
        "LongTermTemporalRule",
        "AlternativeRouteRule",
        "CrossDomainImpactRule",
        "PlanDriftRule",
    )
    assert LIFE_PLAN_OPERATION_IDS == (
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
    assert LIFE_PLAN_OPERATION_IDS == CANONICAL_LIFE_PLAN_OPERATION_IDS
    assert LIFE_PLAN_WORKFLOW_IDS == (
        "life_plan.life_plan_setup",
        "life_plan.quarterly_life_review",
        "life_plan.scenario_comparison",
        "life_plan.goal_dependency_review",
        "life_plan.cross_domain_impact_review",
        "life_plan.plan_drift_review",
        "life_plan.annual_life_plan_update",
    )
    assert LIFE_PLAN_WORKFLOW_IDS == CANONICAL_LIFE_PLAN_WORKFLOW_IDS


def test_life_plan_domain_identity_contract() -> None:
    definition = build_life_plan_domain_definition()
    assert str(definition.id) == LIFE_PLAN_DOMAIN_ID
    assert definition.name == "life-plan"
    assert definition.display_name == "Life Plan"
    assert definition.version == LIFE_PLAN_DOMAIN_VERSION
    assert definition.reasoning_profile == LIFE_PLAN_PROFILE_NAME
    assert definition.manifest_id == LIFE_PLAN_MANIFEST_ID
    assert definition.permissions == LIFE_PLAN_PERMISSION_IDS
    assert definition.metadata.metadata["phase"] == "10.29"
    assert build_life_plan_domain_definition().to_dict() == definition.to_dict()
