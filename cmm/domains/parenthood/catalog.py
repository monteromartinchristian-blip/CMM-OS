"""Phase 10.27 — Canonical Parenthood Domain Catalog.

Single source of truth for the structural IDs of the Parenthood Domain.

All other modules (definition, resources, profile, rules, operations,
workflows, bootstrap, integration, workspaces, memory, presentation, trace)
must import from this module rather than re-declaring the same tuples.
This prevents catalog divergence.

Canonical identity:
    domain:parenthood / namespace ``parenthood.*`` / version ``1.0.0``

Counts:
33 entities (15 journey + 18 child),
19 resources,
17 rules (7 journey + 10 child),
20 operations (9 journey + 11 child),
16 workflows (8 journey + 8 child).
"""

from __future__ import annotations

# ── Canonical parenthood journey entity semantics ────────────────────────────

CANONICAL_PARENTHOOD_JOURNEY_ENTITY_TYPES: tuple[str, ...] = (
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

# ── Canonical parenthood child entity semantics ──────────────────────────────

CANONICAL_PARENTHOOD_CHILD_ENTITY_TYPES: tuple[str, ...] = (
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

CANONICAL_PARENTHOOD_ENTITY_TYPES: tuple[str, ...] = (
    CANONICAL_PARENTHOOD_JOURNEY_ENTITY_TYPES + CANONICAL_PARENTHOOD_CHILD_ENTITY_TYPES
)

# ── Canonical resource IDs ────────────────────────────────────────────────────

CANONICAL_PARENTHOOD_RESOURCE_IDS: tuple[str, ...] = (
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

PARENTHOOD_RESOURCE_KINDS: tuple[str, ...] = tuple(
    resource_id.split(".", 1)[1] for resource_id in CANONICAL_PARENTHOOD_RESOURCE_IDS
)

# ── Canonical rule IDs ────────────────────────────────────────────────────────

CANONICAL_PARENTHOOD_JOURNEY_RULE_IDS: tuple[str, ...] = (
    "parenthood.rule.parenthood_decision_explicit",
    "parenthood.rule.legal_temporal_validity",
    "parenthood.rule.medical_legal_separation",
    "parenthood.rule.ethical_constraint",
    "parenthood.rule.cost_uncertainty",
    "parenthood.rule.journey_dependency",
    "parenthood.rule.journey_to_child_boundary",
)

CANONICAL_PARENTHOOD_CHILD_RULE_IDS: tuple[str, ...] = (
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

CANONICAL_PARENTHOOD_RULE_IDS: tuple[str, ...] = (
    CANONICAL_PARENTHOOD_JOURNEY_RULE_IDS + CANONICAL_PARENTHOOD_CHILD_RULE_IDS
)

CANONICAL_PARENTHOOD_RULE_NAMES: tuple[str, ...] = (
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

# ── Canonical operation IDs ───────────────────────────────────────────────────

CANONICAL_PARENTHOOD_JOURNEY_OPERATION_IDS: tuple[str, ...] = (
    "parenthood.journey.build_timeline",
    "parenthood.journey.compare_pathways",
    "parenthood.journey.review_requirements",
    "parenthood.journey.review_financial_scenarios",
    "parenthood.journey.prepare_questions",
    "parenthood.journey.track_decisions",
    "parenthood.journey.update_plan",
    "parenthood.journey.generate_documentation_checklist",
    "parenthood.journey.review_risks",
)

CANONICAL_PARENTHOOD_CHILD_OPERATION_IDS: tuple[str, ...] = (
    "parenthood.child.review_needs",
    "parenthood.child.review_developmental_stage",
    "parenthood.child.plan_routines",
    "parenthood.child.prepare_parental_decision",
    "parenthood.child.review_education_plan",
    "parenthood.child.review_family_context",
    "parenthood.child.track_milestones",
    "parenthood.child.prepare_questions",
    "parenthood.child.track_decisions",
    "parenthood.child.update_parenting_plan",
    "parenthood.child.review_risks_and_needs",
)

CANONICAL_PARENTHOOD_OPERATION_IDS: tuple[str, ...] = (
    CANONICAL_PARENTHOOD_JOURNEY_OPERATION_IDS
    + CANONICAL_PARENTHOOD_CHILD_OPERATION_IDS
)

# ── Canonical workflow IDs ────────────────────────────────────────────────────

CANONICAL_PARENTHOOD_JOURNEY_WORKFLOW_IDS: tuple[str, ...] = (
    "parenthood.workflow.path_to_parenthood_review",
    "parenthood.workflow.pathway_comparison",
    "parenthood.workflow.provider_review",
    "parenthood.workflow.requirements_review",
    "parenthood.workflow.financial_readiness_review",
    "parenthood.workflow.medical_preparation_review",
    "parenthood.workflow.documentation_review",
    "parenthood.workflow.annual_journey_plan_update",
)

CANONICAL_PARENTHOOD_CHILD_WORKFLOW_IDS: tuple[str, ...] = (
    "parenthood.workflow.child_needs_review",
    "parenthood.workflow.developmental_stage_review",
    "parenthood.workflow.education_planning_review",
    "parenthood.workflow.routine_review",
    "parenthood.workflow.parental_decision_review",
    "parenthood.workflow.family_context_review",
    "parenthood.workflow.milestone_review",
    "parenthood.workflow.annual_parenting_plan_review",
)

CANONICAL_PARENTHOOD_WORKFLOW_IDS: tuple[str, ...] = (
    CANONICAL_PARENTHOOD_JOURNEY_WORKFLOW_IDS + CANONICAL_PARENTHOOD_CHILD_WORKFLOW_IDS
)

PARENTHOOD_WORKFLOW_NAMES_BY_ID: dict[str, str] = {
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

CANONICAL_PARENTHOOD_WORKFLOW_NAMES: tuple[str, ...] = tuple(
    PARENTHOOD_WORKFLOW_NAMES_BY_ID[workflow_id]
    for workflow_id in CANONICAL_PARENTHOOD_WORKFLOW_IDS
)

__all__ = [
    "CANONICAL_PARENTHOOD_CHILD_ENTITY_TYPES",
    "CANONICAL_PARENTHOOD_CHILD_OPERATION_IDS",
    "CANONICAL_PARENTHOOD_CHILD_RULE_IDS",
    "CANONICAL_PARENTHOOD_CHILD_WORKFLOW_IDS",
    "CANONICAL_PARENTHOOD_ENTITY_TYPES",
    "CANONICAL_PARENTHOOD_JOURNEY_ENTITY_TYPES",
    "CANONICAL_PARENTHOOD_JOURNEY_OPERATION_IDS",
    "CANONICAL_PARENTHOOD_JOURNEY_RULE_IDS",
    "CANONICAL_PARENTHOOD_JOURNEY_WORKFLOW_IDS",
    "CANONICAL_PARENTHOOD_OPERATION_IDS",
    "CANONICAL_PARENTHOOD_RESOURCE_IDS",
    "CANONICAL_PARENTHOOD_RULE_IDS",
    "CANONICAL_PARENTHOOD_RULE_NAMES",
    "CANONICAL_PARENTHOOD_WORKFLOW_IDS",
    "CANONICAL_PARENTHOOD_WORKFLOW_NAMES",
    "PARENTHOOD_RESOURCE_KINDS",
    "PARENTHOOD_WORKFLOW_NAMES_BY_ID",
]
