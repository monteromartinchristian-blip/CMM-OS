"""Tests for Phase 10.27 Parenthood Domain Catalog."""

from __future__ import annotations

from cmm.domains.parenthood.catalog import (
    CANONICAL_PARENTHOOD_CHILD_ENTITY_TYPES,
    CANONICAL_PARENTHOOD_CHILD_OPERATION_IDS,
    CANONICAL_PARENTHOOD_CHILD_RULE_IDS,
    CANONICAL_PARENTHOOD_CHILD_WORKFLOW_IDS,
    CANONICAL_PARENTHOOD_ENTITY_TYPES,
    CANONICAL_PARENTHOOD_JOURNEY_ENTITY_TYPES,
    CANONICAL_PARENTHOOD_JOURNEY_OPERATION_IDS,
    CANONICAL_PARENTHOOD_JOURNEY_RULE_IDS,
    CANONICAL_PARENTHOOD_JOURNEY_WORKFLOW_IDS,
    CANONICAL_PARENTHOOD_OPERATION_IDS,
    CANONICAL_PARENTHOOD_RESOURCE_IDS,
    CANONICAL_PARENTHOOD_RULE_IDS,
    CANONICAL_PARENTHOOD_RULE_NAMES,
    CANONICAL_PARENTHOOD_WORKFLOW_IDS,
    CANONICAL_PARENTHOOD_WORKFLOW_NAMES,
    PARENTHOOD_RESOURCE_KINDS,
    PARENTHOOD_WORKFLOW_NAMES_BY_ID,
)


def test_canonical_catalog_counts() -> None:
    """Verify exact counts of canonical catalog items for Phase 10.27."""
    assert len(CANONICAL_PARENTHOOD_JOURNEY_ENTITY_TYPES) == 15
    assert len(CANONICAL_PARENTHOOD_CHILD_ENTITY_TYPES) == 18
    assert len(CANONICAL_PARENTHOOD_ENTITY_TYPES) == 33

    assert len(CANONICAL_PARENTHOOD_RESOURCE_IDS) == 19
    assert len(PARENTHOOD_RESOURCE_KINDS) == 19

    assert len(CANONICAL_PARENTHOOD_JOURNEY_RULE_IDS) == 7
    assert len(CANONICAL_PARENTHOOD_CHILD_RULE_IDS) == 10
    assert len(CANONICAL_PARENTHOOD_RULE_IDS) == 17
    assert len(CANONICAL_PARENTHOOD_RULE_NAMES) == 17

    assert len(CANONICAL_PARENTHOOD_JOURNEY_OPERATION_IDS) == 9
    assert len(CANONICAL_PARENTHOOD_CHILD_OPERATION_IDS) == 11
    assert len(CANONICAL_PARENTHOOD_OPERATION_IDS) == 20

    assert len(CANONICAL_PARENTHOOD_JOURNEY_WORKFLOW_IDS) == 8
    assert len(CANONICAL_PARENTHOOD_CHILD_WORKFLOW_IDS) == 8
    assert len(CANONICAL_PARENTHOOD_WORKFLOW_IDS) == 16
    assert len(CANONICAL_PARENTHOOD_WORKFLOW_NAMES) == 16


def test_canonical_catalog_uniqueness() -> None:
    """Verify all canonical sets contain no duplicates."""
    for values in (
        CANONICAL_PARENTHOOD_JOURNEY_ENTITY_TYPES,
        CANONICAL_PARENTHOOD_CHILD_ENTITY_TYPES,
        CANONICAL_PARENTHOOD_ENTITY_TYPES,
        CANONICAL_PARENTHOOD_RESOURCE_IDS,
        PARENTHOOD_RESOURCE_KINDS,
        CANONICAL_PARENTHOOD_RULE_IDS,
        CANONICAL_PARENTHOOD_RULE_NAMES,
        CANONICAL_PARENTHOOD_OPERATION_IDS,
        CANONICAL_PARENTHOOD_WORKFLOW_IDS,
        CANONICAL_PARENTHOOD_WORKFLOW_NAMES,
    ):
        assert len(values) == len(set(values))


def test_canonical_catalog_prefixes() -> None:
    """Verify namespaces and prefixes for resources, rules, operations, workflows."""
    assert all(
        v.startswith("parenthood.resource.") for v in CANONICAL_PARENTHOOD_RESOURCE_IDS
    )
    assert all(v.startswith("parenthood.rule.") for v in CANONICAL_PARENTHOOD_RULE_IDS)
    assert all(
        v.startswith("parenthood.journey.")
        for v in CANONICAL_PARENTHOOD_JOURNEY_OPERATION_IDS
    )
    assert all(
        v.startswith("parenthood.child.")
        for v in CANONICAL_PARENTHOOD_CHILD_OPERATION_IDS
    )
    assert all(
        v.startswith("parenthood.workflow.") for v in CANONICAL_PARENTHOOD_WORKFLOW_IDS
    )


def test_canonical_entities_exact() -> None:
    """Verify exact entities in canonical order."""
    expected_journey = (
        "parenthood_goal",
        "parenthood_pathway",
        "jurisdiction",
        "medical_pathway",
        "medical_provider",
        "participant",
        "legal_requirement",
        "administrative_requirement",
        "documentation_requirement",
        "financial_scenario",
        "ethical_constraint",
        "timeline",
        "decision",
        "risk",
        "birth_transition",
    )
    assert CANONICAL_PARENTHOOD_JOURNEY_ENTITY_TYPES == expected_journey

    expected_child = (
        "child",
        "developmental_stage",
        "care_need",
        "routine",
        "milestone",
        "education_plan",
        "school",
        "activity",
        "health_context",
        "wellbeing_signal",
        "family_context",
        "support_network",
        "parental_decision",
        "value",
        "boundary",
        "schedule",
        "residence_plan",
        "long_term_plan",
    )
    assert CANONICAL_PARENTHOOD_CHILD_ENTITY_TYPES == expected_child
    assert CANONICAL_PARENTHOOD_ENTITY_TYPES == expected_journey + expected_child


def test_canonical_resources_and_kinds() -> None:
    """Verify exact 19 resources and derived kinds."""
    expected_resources = (
        "parenthood.resource.life_plan",
        "parenthood.resource.legal_document",
        "parenthood.resource.medical_report",
        "parenthood.resource.financial_plan",
        "parenthood.resource.provider_information",
        "parenthood.resource.jurisdiction_information",
        "parenthood.resource.decision",
        "parenthood.resource.note",
        "parenthood.resource.parenting_note",
        "parenthood.resource.education_document",
        "parenthood.resource.child_development_resource",
        "parenthood.resource.health_summary",
        "parenthood.resource.schedule",
        "parenthood.resource.parental_decision",
        "parenthood.resource.school_information",
        "parenthood.resource.activity_information",
        "parenthood.resource.user_message",
        "parenthood.resource.external_source",
        "parenthood.resource.memory_entry",
    )
    assert CANONICAL_PARENTHOOD_RESOURCE_IDS == expected_resources
    assert PARENTHOOD_RESOURCE_KINDS == tuple(
        r.split(".", 1)[1] for r in expected_resources
    )


def test_canonical_rules_and_class_names() -> None:
    """Verify exact 17 rules and corresponding class names."""
    expected_journey_rules = (
        "parenthood.rule.parenthood_decision_explicit",
        "parenthood.rule.legal_temporal_validity",
        "parenthood.rule.medical_legal_separation",
        "parenthood.rule.ethical_constraint",
        "parenthood.rule.cost_uncertainty",
        "parenthood.rule.journey_dependency",
        "parenthood.rule.journey_to_child_boundary",
    )
    assert CANONICAL_PARENTHOOD_JOURNEY_RULE_IDS == expected_journey_rules

    expected_child_rules = (
        "parenthood.rule.child_interest_and_wellbeing",
        "parenthood.rule.developmental_context",
        "parenthood.rule.age_appropriate_guidance",
        "parenthood.rule.parent_child_boundary",
        "parenthood.rule.health_boundary",
        "parenthood.rule.education_boundary",
        "parenthood.rule.minor_privacy",
        "parenthood.rule.long_term_continuity",
        "parenthood.rule.parental_uncertainty",
        "parenthood.rule.sibling_identity_isolation",
    )
    assert CANONICAL_PARENTHOOD_CHILD_RULE_IDS == expected_child_rules
    assert (
        CANONICAL_PARENTHOOD_RULE_IDS == expected_journey_rules + expected_child_rules
    )

    expected_rule_names = (
        "ParenthoodDecisionExplicitRule",
        "LegalTemporalValidityRule",
        "MedicalLegalSeparationRule",
        "EthicalConstraintRule",
        "CostUncertaintyRule",
        "JourneyDependencyRule",
        "JourneyToChildBoundaryRule",
        "ChildInterestAndWellbeingRule",
        "DevelopmentalContextRule",
        "AgeAppropriateGuidanceRule",
        "ParentChildBoundaryRule",
        "HealthBoundaryRule",
        "EducationBoundaryRule",
        "MinorPrivacyRule",
        "LongTermContinuityRule",
        "ParentalUncertaintyRule",
        "SiblingIdentityIsolationRule",
    )
    assert CANONICAL_PARENTHOOD_RULE_NAMES == expected_rule_names


def test_canonical_workflows_and_names() -> None:
    """Verify exact 16 workflows and display names."""
    expected_journey_workflows = (
        "parenthood.workflow.path_to_parenthood_review",
        "parenthood.workflow.pathway_comparison",
        "parenthood.workflow.provider_review",
        "parenthood.workflow.requirements_review",
        "parenthood.workflow.financial_readiness_review",
        "parenthood.workflow.medical_preparation_review",
        "parenthood.workflow.documentation_review",
        "parenthood.workflow.annual_journey_plan_update",
    )
    assert CANONICAL_PARENTHOOD_JOURNEY_WORKFLOW_IDS == expected_journey_workflows

    expected_child_workflows = (
        "parenthood.workflow.child_needs_review",
        "parenthood.workflow.developmental_stage_review",
        "parenthood.workflow.education_planning_review",
        "parenthood.workflow.routine_review",
        "parenthood.workflow.parental_decision_review",
        "parenthood.workflow.family_context_review",
        "parenthood.workflow.milestone_review",
        "parenthood.workflow.annual_parenting_plan_review",
    )
    assert CANONICAL_PARENTHOOD_CHILD_WORKFLOW_IDS == expected_child_workflows
    assert (
        CANONICAL_PARENTHOOD_WORKFLOW_IDS
        == expected_journey_workflows + expected_child_workflows
    )

    expected_names_by_id = {
        "parenthood.workflow.path_to_parenthood_review": "Path to Parenthood Review",
        "parenthood.workflow.pathway_comparison": "Pathway Comparison",
        "parenthood.workflow.provider_review": "Provider Review",
        "parenthood.workflow.requirements_review": "Requirements Review",
        "parenthood.workflow.financial_readiness_review": "Financial Readiness Review",
        "parenthood.workflow.medical_preparation_review": "Medical Preparation Review",
        "parenthood.workflow.documentation_review": "Documentation Review",
        "parenthood.workflow.annual_journey_plan_update": "Annual Journey Plan Update",
        "parenthood.workflow.child_needs_review": "Child Needs Review",
        "parenthood.workflow.developmental_stage_review": "Developmental Stage Review",
        "parenthood.workflow.education_planning_review": "Education Planning Review",
        "parenthood.workflow.routine_review": "Routine Review",
        "parenthood.workflow.parental_decision_review": "Parental Decision Review",
        "parenthood.workflow.family_context_review": "Family Context Review",
        "parenthood.workflow.milestone_review": "Milestone Review",
        "parenthood.workflow.annual_parenting_plan_review": "Annual Parenting Plan Review",
    }
    assert PARENTHOOD_WORKFLOW_NAMES_BY_ID == expected_names_by_id
    assert CANONICAL_PARENTHOOD_WORKFLOW_NAMES == tuple(
        expected_names_by_id[w] for w in CANONICAL_PARENTHOOD_WORKFLOW_IDS
    )
