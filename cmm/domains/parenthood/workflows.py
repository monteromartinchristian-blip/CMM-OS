"""Phase 10.27 — Parenthood Domain Workflows.

Sixteen declarative Parenthood workflows (8 journey + 8 child).
Every workflow loads its sources, applies the ParenthoodProfile, reasons under
the seventeen Parenthood rules, executes reasoning/planning operations, and
validates results against safety and epistemic gates before completion.

Safety ordering: ``load -> profile -> reason`` is a strict dependency chain.
A terminal ``COMPLETE`` node always transitively depends on a ``VALIDATE`` node.
"""

from __future__ import annotations

from cmm.domains.parenthood.catalog import (
    CANONICAL_PARENTHOOD_CHILD_WORKFLOW_IDS,
    CANONICAL_PARENTHOOD_JOURNEY_WORKFLOW_IDS,
    CANONICAL_PARENTHOOD_WORKFLOW_IDS,
    PARENTHOOD_WORKFLOW_NAMES_BY_ID,
)
from cmm.domains.workflow_contracts import DomainWorkflowDefinition
from cmm.workflows.contracts import WorkflowNode
from cmm.workflows.enums import WorkflowNodeType

PARENTHOOD_WORKFLOW_IDS: tuple[str, ...] = CANONICAL_PARENTHOOD_WORKFLOW_IDS


def _node(
    node_id: str,
    node_type: WorkflowNodeType,
    name: str,
    *,
    dependencies: tuple[str, ...] = (),
    operation_id: str | None = None,
    approval_gate: str | None = None,
    wait_condition: dict | None = None,
    metadata: dict | None = None,
) -> WorkflowNode:
    return WorkflowNode(
        node_id=node_id,
        node_type=node_type,
        name=name,
        dependencies=dependencies,
        operation_id=operation_id,
        operation_version="1.0.0" if operation_id else None,
        approval_gate=approval_gate,
        wait_condition=wait_condition,
        metadata=metadata or {},
    )


def _ordered_prefix() -> tuple[WorkflowNode, ...]:
    """Strict safety prefix: load -> profile -> reason."""
    return (
        _node("load", WorkflowNodeType.LOAD_RESOURCE, "LoadParenthoodSources"),
        _node(
            "profile",
            WorkflowNodeType.APPLY_PROFILE,
            "ApplyParenthoodProfile",
            dependencies=("load",),
        ),
        _node(
            "reason",
            WorkflowNodeType.REASON,
            "ApplyParenthoodRules",
            dependencies=("profile",),
        ),
    )


def _workflow(
    workflow_id: str,
    *,
    description: str,
    purpose: str,
    core_nodes: tuple[WorkflowNode, ...],
    extra_metadata: dict | None = None,
) -> DomainWorkflowDefinition:
    return DomainWorkflowDefinition(
        workflow_id=workflow_id,
        domain_id="domain:parenthood",
        version="1.0.0",
        name=PARENTHOOD_WORKFLOW_NAMES_BY_ID[workflow_id],
        description=description,
        nodes=(*_ordered_prefix(), *core_nodes),
        completion_criteria={
            "all_required_nodes_completed": True,
            "no_blocking_failures": True,
        },
        metadata={
            "phase": "10.27",
            "purpose": purpose,
            "non_autonomous": True,
            **(extra_metadata or {}),
        },
    )


def build_parenthood_workflow_definitions() -> tuple[DomainWorkflowDefinition, ...]:
    """Build all sixteen canonical Parenthood Domain workflow definitions deterministically."""
    # ── Journey Workflows ─────────────────────────────────────────────────────

    # 1. path_to_parenthood_review
    path_to_parenthood = _workflow(
        "parenthood.workflow.path_to_parenthood_review",
        description="Comprehensive review of the path to parenthood project.",
        purpose="Review overall parenthood objectives, timing, and readiness.",
        core_nodes=(
            _node("timeline", WorkflowNodeType.EXECUTE_OPERATION, "BuildTimeline", dependencies=("reason",), operation_id="parenthood.journey.build_timeline"),
            _node("validate", WorkflowNodeType.VALIDATE, "ValidateJourneyPlan", dependencies=("timeline",)),
            _node("complete", WorkflowNodeType.COMPLETE, "CompletePathReview", dependencies=("validate",)),
        ),
    )

    # 2. pathway_comparison
    pathway_comparison = _workflow(
        "parenthood.workflow.pathway_comparison",
        description="Structured comparison between prospective family-building pathways.",
        purpose="Compare pathways with explicit cost, legal, and medical separation.",
        core_nodes=(
            _node("compare", WorkflowNodeType.EXECUTE_OPERATION, "ComparePathways", dependencies=("reason",), operation_id="parenthood.journey.compare_pathways"),
            _node("validate", WorkflowNodeType.VALIDATE, "ValidatePathwayComparison", dependencies=("compare",)),
            _node("complete", WorkflowNodeType.COMPLETE, "CompletePathwayComparison", dependencies=("validate",)),
        ),
    )

    # 3. provider_review
    provider_review = _workflow(
        "parenthood.workflow.provider_review",
        description="Review potential clinics, agencies, and medical/legal providers.",
        purpose="Evaluate provider information and prepare questions.",
        core_nodes=(
            _node("questions", WorkflowNodeType.EXECUTE_OPERATION, "PrepareQuestions", dependencies=("reason",), operation_id="parenthood.journey.prepare_questions"),
            _node("validate", WorkflowNodeType.VALIDATE, "ValidateProviderReview", dependencies=("questions",)),
            _node("complete", WorkflowNodeType.COMPLETE, "CompleteProviderReview", dependencies=("validate",)),
        ),
    )

    # 4. requirements_review
    requirements_review = _workflow(
        "parenthood.workflow.requirements_review",
        description="Review legal, administrative, and clinical requirements.",
        purpose="Track requirement dependencies and verify temporal validity.",
        core_nodes=(
            _node("reqs", WorkflowNodeType.EXECUTE_OPERATION, "ReviewRequirements", dependencies=("reason",), operation_id="parenthood.journey.review_requirements"),
            _node("validate", WorkflowNodeType.VALIDATE, "ValidateRequirements", dependencies=("reqs",)),
            _node("complete", WorkflowNodeType.COMPLETE, "CompleteRequirementsReview", dependencies=("validate",)),
        ),
    )

    # 5. financial_readiness_review
    financial_readiness = _workflow(
        "parenthood.workflow.financial_readiness_review",
        description="Review financial scenarios and cost estimates.",
        purpose="Preserve cost uncertainty, contingency reserves, and scenario planning.",
        core_nodes=(
            _node("finance", WorkflowNodeType.EXECUTE_OPERATION, "ReviewFinancialScenarios", dependencies=("reason",), operation_id="parenthood.journey.review_financial_scenarios"),
            _node("validate", WorkflowNodeType.VALIDATE, "ValidateFinancialReadiness", dependencies=("finance",)),
            _node("complete", WorkflowNodeType.COMPLETE, "CompleteFinancialReview", dependencies=("validate",)),
        ),
    )

    # 6. medical_preparation_review
    medical_preparation = _workflow(
        "parenthood.workflow.medical_preparation_review",
        description="Review medical pathway preparation and testing prerequisites.",
        purpose="Organize clinical testing steps without autonomous medical decision.",
        core_nodes=(
            _node("risks", WorkflowNodeType.EXECUTE_OPERATION, "ReviewRisks", dependencies=("reason",), operation_id="parenthood.journey.review_risks"),
            _node("validate", WorkflowNodeType.VALIDATE, "ValidateMedicalPreparation", dependencies=("risks",)),
            _node("complete", WorkflowNodeType.COMPLETE, "CompleteMedicalPreparation", dependencies=("validate",)),
        ),
    )

    # 7. documentation_review
    documentation_review = _workflow(
        "parenthood.workflow.documentation_review",
        description="Review and prepare civil, legal, and identity documentation checklists.",
        purpose="Generate documentation checklists for legal and administrative milestones.",
        core_nodes=(
            _node("checklist", WorkflowNodeType.EXECUTE_OPERATION, "GenerateChecklist", dependencies=("reason",), operation_id="parenthood.journey.generate_documentation_checklist"),
            _node("validate", WorkflowNodeType.VALIDATE, "ValidateDocumentation", dependencies=("checklist",)),
            _node("complete", WorkflowNodeType.COMPLETE, "CompleteDocumentationReview", dependencies=("validate",)),
        ),
    )

    # 8. annual_journey_plan_update
    annual_journey_plan = _workflow(
        "parenthood.workflow.annual_journey_plan_update",
        description="Annual update and review of the parenthood journey plan.",
        purpose="Refresh timeline, dependencies, and decision state.",
        core_nodes=(
            _node("update", WorkflowNodeType.EXECUTE_OPERATION, "UpdateJourneyPlan", dependencies=("reason",), operation_id="parenthood.journey.update_plan"),
            _node("validate", WorkflowNodeType.VALIDATE, "ValidatePlanUpdate", dependencies=("update",)),
            _node("complete", WorkflowNodeType.COMPLETE, "CompleteAnnualJourneyUpdate", dependencies=("validate",)),
        ),
    )

    # ── Child Workflows ───────────────────────────────────────────────────────

    # 9. child_needs_review
    child_needs = _workflow(
        "parenthood.workflow.child_needs_review",
        description="Comprehensive review of child wellbeing and individual care needs.",
        purpose="Assess developmental needs while separating child needs from parent preferences.",
        core_nodes=(
            _node("needs", WorkflowNodeType.EXECUTE_OPERATION, "ReviewChildNeeds", dependencies=("reason",), operation_id="parenthood.child.review_needs"),
            _node("validate", WorkflowNodeType.VALIDATE, "ValidateChildNeeds", dependencies=("needs",)),
            _node("complete", WorkflowNodeType.COMPLETE, "CompleteNeedsReview", dependencies=("validate",)),
        ),
    )

    # 10. developmental_stage_review
    developmental_stage = _workflow(
        "parenthood.workflow.developmental_stage_review",
        description="Review developmental stage and age-appropriate milestones.",
        purpose="Evaluate developmental progress under the non-pathological variation invariant.",
        core_nodes=(
            _node("stage", WorkflowNodeType.EXECUTE_OPERATION, "ReviewStage", dependencies=("reason",), operation_id="parenthood.child.review_developmental_stage"),
            _node("validate", WorkflowNodeType.VALIDATE, "ValidateDevelopmentalStage", dependencies=("stage",)),
            _node("complete", WorkflowNodeType.COMPLETE, "CompleteDevelopmentalReview", dependencies=("validate",)),
        ),
    )

    # 11. education_planning_review
    education_planning = _workflow(
        "parenthood.workflow.education_planning_review",
        description="Plan schooling, educational support, and extracurricular activities.",
        purpose="Support educational planning without specialized psychometric diagnosis.",
        core_nodes=(
            _node("edu", WorkflowNodeType.EXECUTE_OPERATION, "ReviewEducationPlan", dependencies=("reason",), operation_id="parenthood.child.review_education_plan"),
            _node("validate", WorkflowNodeType.VALIDATE, "ValidateEducationPlan", dependencies=("edu",)),
            _node("complete", WorkflowNodeType.COMPLETE, "CompleteEducationReview", dependencies=("validate",)),
        ),
    )

    # 12. routine_review
    routine_review = _workflow(
        "parenthood.workflow.routine_review",
        description="Review and optimize daily routines, schedules, and sleep/care patterns.",
        purpose="Plan healthy routines attuned to child age and family context.",
        core_nodes=(
            _node("routines", WorkflowNodeType.EXECUTE_OPERATION, "PlanRoutines", dependencies=("reason",), operation_id="parenthood.child.plan_routines"),
            _node("validate", WorkflowNodeType.VALIDATE, "ValidateRoutines", dependencies=("routines",)),
            _node("complete", WorkflowNodeType.COMPLETE, "CompleteRoutineReview", dependencies=("validate",)),
        ),
    )

    # 13. parental_decision_review
    parental_decision = _workflow(
        "parenthood.workflow.parental_decision_review",
        description="Formulate, review, and organize options for significant parental choices.",
        purpose="Prepare decisions as proposals requiring explicit user confirmation.",
        core_nodes=(
            _node("prep_dec", WorkflowNodeType.EXECUTE_OPERATION, "PrepareDecision", dependencies=("reason",), operation_id="parenthood.child.prepare_parental_decision"),
            _node("validate", WorkflowNodeType.VALIDATE, "ValidateDecisionProposal", dependencies=("prep_dec",)),
            _node("complete", WorkflowNodeType.COMPLETE, "CompleteDecisionReview", dependencies=("validate",)),
        ),
    )

    # 14. family_context_review
    family_context = _workflow(
        "parenthood.workflow.family_context_review",
        description="Review family dynamics, support network, and shared family context.",
        purpose="Support family context while preserving sibling workspace isolation.",
        core_nodes=(
            _node("fam", WorkflowNodeType.EXECUTE_OPERATION, "ReviewFamilyContext", dependencies=("reason",), operation_id="parenthood.child.review_family_context"),
            _node("validate", WorkflowNodeType.VALIDATE, "ValidateFamilyContext", dependencies=("fam",)),
            _node("complete", WorkflowNodeType.COMPLETE, "CompleteFamilyReview", dependencies=("validate",)),
        ),
    )

    # 15. milestone_review
    milestone_review = _workflow(
        "parenthood.workflow.milestone_review",
        description="Track growth, developmental milestones, and memorable events.",
        purpose="Track milestones without turning variance into deficits.",
        core_nodes=(
            _node("milestones", WorkflowNodeType.EXECUTE_OPERATION, "TrackMilestones", dependencies=("reason",), operation_id="parenthood.child.track_milestones"),
            _node("validate", WorkflowNodeType.VALIDATE, "ValidateMilestones", dependencies=("milestones",)),
            _node("complete", WorkflowNodeType.COMPLETE, "CompleteMilestoneReview", dependencies=("validate",)),
        ),
    )

    # 16. annual_parenting_plan_review
    annual_parenting_plan = _workflow(
        "parenthood.workflow.annual_parenting_plan_review",
        description="Annual comprehensive parenting plan review and forward outlook.",
        purpose="Review long-term parenting continuity, values, and evolving goals.",
        core_nodes=(
            _node("plan", WorkflowNodeType.EXECUTE_OPERATION, "UpdateParentingPlan", dependencies=("reason",), operation_id="parenthood.child.update_parenting_plan"),
            _node("validate", WorkflowNodeType.VALIDATE, "ValidateParentingPlan", dependencies=("plan",)),
            _node("complete", WorkflowNodeType.COMPLETE, "CompleteAnnualParentingReview", dependencies=("validate",)),
        ),
    )

    by_id = {
        "parenthood.workflow.path_to_parenthood_review": path_to_parenthood,
        "parenthood.workflow.pathway_comparison": pathway_comparison,
        "parenthood.workflow.provider_review": provider_review,
        "parenthood.workflow.requirements_review": requirements_review,
        "parenthood.workflow.financial_readiness_review": financial_readiness,
        "parenthood.workflow.medical_preparation_review": medical_preparation,
        "parenthood.workflow.documentation_review": documentation_review,
        "parenthood.workflow.annual_journey_plan_update": annual_journey_plan,
        "parenthood.workflow.child_needs_review": child_needs,
        "parenthood.workflow.developmental_stage_review": developmental_stage,
        "parenthood.workflow.education_planning_review": education_planning,
        "parenthood.workflow.routine_review": routine_review,
        "parenthood.workflow.parental_decision_review": parental_decision,
        "parenthood.workflow.family_context_review": family_context,
        "parenthood.workflow.milestone_review": milestone_review,
        "parenthood.workflow.annual_parenting_plan_review": annual_parenting_plan,
    }

    return tuple(by_id[wf_id] for wf_id in CANONICAL_PARENTHOOD_WORKFLOW_IDS)


__all__ = [
    "CANONICAL_PARENTHOOD_CHILD_WORKFLOW_IDS",
    "CANONICAL_PARENTHOOD_JOURNEY_WORKFLOW_IDS",
    "CANONICAL_PARENTHOOD_WORKFLOW_IDS",
    "PARENTHOOD_WORKFLOW_IDS",
    "build_parenthood_workflow_definitions",
]
