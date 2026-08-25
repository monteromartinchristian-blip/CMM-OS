"""Phase 10.29 — Life Plan Domain Workflows.

Seven declarative Life Plan workflows built on shared DomainWorkflowDefinition:
1. life_plan.life_plan_setup
2. life_plan.quarterly_life_review
3. life_plan.scenario_comparison
4. life_plan.goal_dependency_review
5. life_plan.cross_domain_impact_review  (Major Decision Support)
6. life_plan.plan_drift_review
7. life_plan.annual_life_plan_update

Safety ordering: ``load -> profile -> reason`` is a strict dependency chain.
A terminal ``COMPLETE`` node always transitively depends on a ``VALIDATE`` node.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from cmm.domains.life_plan.catalog import (
    CANONICAL_LIFE_PLAN_WORKFLOW_IDS,
)
from cmm.domains.life_plan.rules import (
    AuthorizedCrossDomainContribution,
    evaluate_cross_domain_impact,
    evaluate_resource_constraints,
)
from cmm.domains.workflow_contracts import DomainWorkflowDefinition
from cmm.workflows.contracts import WorkflowNode
from cmm.workflows.enums import WorkflowNodeType

LIFE_PLAN_WORKFLOW_IDS: tuple[str, ...] = CANONICAL_LIFE_PLAN_WORKFLOW_IDS

LIFE_PLAN_WORKFLOW_NAMES_BY_ID: dict[str, str] = {
    "life_plan.life_plan_setup": "Life Plan Setup",
    "life_plan.quarterly_life_review": "Quarterly Life Review",
    "life_plan.scenario_comparison": "Scenario Comparison",
    "life_plan.goal_dependency_review": "Goal Dependency Review",
    "life_plan.cross_domain_impact_review": "Cross Domain Impact Review",
    "life_plan.plan_drift_review": "Plan Drift Review",
    "life_plan.annual_life_plan_update": "Annual Life Plan Update",
}


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
        _node("load", WorkflowNodeType.LOAD_RESOURCE, "LoadLifePlanSources"),
        _node(
            "profile",
            WorkflowNodeType.APPLY_PROFILE,
            "ApplyLifePlanProfile",
            dependencies=("load",),
        ),
        _node(
            "reason",
            WorkflowNodeType.REASON,
            "ApplyLifePlanRules",
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
        domain_id="domain:life-plan",
        version="1.0.0",
        name=LIFE_PLAN_WORKFLOW_NAMES_BY_ID[workflow_id],
        description=description,
        nodes=(*_ordered_prefix(), *core_nodes),
        completion_criteria={
            "all_required_nodes_completed": True,
            "no_blocking_failures": True,
        },
        metadata={
            "phase": "10.29",
            "purpose": purpose,
            "non_autonomous": True,
            **(extra_metadata or {}),
        },
    )


def build_life_plan_workflow_definitions() -> tuple[DomainWorkflowDefinition, ...]:
    """Build all seven canonical Life Plan Domain workflow definitions deterministically."""
    # 1. life_plan_setup
    life_plan_setup = _workflow(
        "life_plan.life_plan_setup",
        description="Set up a new life plan structure and primary goals.",
        purpose="Define vision, initial life categories and milestones.",
        core_nodes=(
            _node(
                "create_plan",
                WorkflowNodeType.EXECUTE_OPERATION,
                "CreateLifePlan",
                dependencies=("reason",),
                operation_id="life_plan.update_plan",
            ),
            _node(
                "validate",
                WorkflowNodeType.VALIDATE,
                "ValidateLifePlanSetup",
                dependencies=("create_plan",),
            ),
            _node(
                "complete",
                WorkflowNodeType.COMPLETE,
                "CompleteLifePlanSetup",
                dependencies=("validate",),
            ),
        ),
    )

    # 2. quarterly_life_review
    quarterly_life_review = _workflow(
        "life_plan.quarterly_life_review",
        description="Conduct quarterly progress and balance review.",
        purpose="Evaluate quarterly milestone progress, energy and resource alignment.",
        core_nodes=(
            _node(
                "review_goals",
                WorkflowNodeType.EXECUTE_OPERATION,
                "ReviewQuarterlyGoals",
                dependencies=("reason",),
                operation_id="life_plan.review_goals",
            ),
            _node(
                "generate_review",
                WorkflowNodeType.EXECUTE_OPERATION,
                "GenerateQuarterlyReview",
                dependencies=("review_goals",),
                operation_id="life_plan.generate_periodic_review",
            ),
            _node(
                "validate",
                WorkflowNodeType.VALIDATE,
                "ValidateQuarterlyReview",
                dependencies=("generate_review",),
            ),
            _node(
                "complete",
                WorkflowNodeType.COMPLETE,
                "CompleteQuarterlyReview",
                dependencies=("validate",),
            ),
        ),
    )

    # 3. scenario_comparison
    scenario_comparison = _workflow(
        "life_plan.scenario_comparison",
        description="Compare multiple future life scenarios and hypotheses.",
        purpose="Analyze feasibility and consistency without forcing commitment.",
        core_nodes=(
            _node(
                "compare_scenarios",
                WorkflowNodeType.EXECUTE_OPERATION,
                "CompareScenariosOperation",
                dependencies=("reason",),
                operation_id="life_plan.compare_scenarios",
            ),
            _node(
                "evaluate_feasibility",
                WorkflowNodeType.EXECUTE_OPERATION,
                "EvaluateScenarioFeasibility",
                dependencies=("compare_scenarios",),
                operation_id="life_plan.evaluate_feasibility",
            ),
            _node(
                "validate",
                WorkflowNodeType.VALIDATE,
                "ValidateScenarioComparison",
                dependencies=("evaluate_feasibility",),
            ),
            _node(
                "complete",
                WorkflowNodeType.COMPLETE,
                "CompleteScenarioComparison",
                dependencies=("validate",),
            ),
        ),
    )

    # 4. goal_dependency_review
    goal_dependency_review = _workflow(
        "life_plan.goal_dependency_review",
        description="Analyze goal dependency relationships, prerequisites and potential bottlenecks.",
        purpose="Identify critical path and circular dependencies across life goals.",
        core_nodes=(
            _node(
                "detect_dependencies",
                WorkflowNodeType.EXECUTE_OPERATION,
                "DetectGoalDependencies",
                dependencies=("reason",),
                operation_id="life_plan.detect_dependencies",
            ),
            _node(
                "identify_risks",
                WorkflowNodeType.EXECUTE_OPERATION,
                "IdentifyDependencyRisks",
                dependencies=("detect_dependencies",),
                operation_id="life_plan.identify_risks",
            ),
            _node(
                "validate",
                WorkflowNodeType.VALIDATE,
                "ValidateGoalDependencies",
                dependencies=("identify_risks",),
            ),
            _node(
                "complete",
                WorkflowNodeType.COMPLETE,
                "CompleteGoalDependencyReview",
                dependencies=("validate",),
            ),
        ),
    )

    # 5. cross_domain_impact_review (Major Decision Support)
    cross_domain_impact_review = _workflow(
        "life_plan.cross_domain_impact_review",
        description="Review multi-domain impacts of major life decisions.",
        purpose="Major Decision Support: Coordinate authorized supporting domain projections (Health, University, Oppositions, Parenthood, Project).",
        core_nodes=(
            _node(
                "review_cross_domain",
                WorkflowNodeType.EXECUTE_OPERATION,
                "ReviewCrossDomainImpacts",
                dependencies=("reason",),
                operation_id="life_plan.identify_risks",
            ),
            _node(
                "evaluate_feasibility",
                WorkflowNodeType.EXECUTE_OPERATION,
                "EvaluateMultiDomainFeasibility",
                dependencies=("review_cross_domain",),
                operation_id="life_plan.evaluate_feasibility",
            ),
            _node(
                "validate",
                WorkflowNodeType.VALIDATE,
                "ValidateCrossDomainReview",
                dependencies=("evaluate_feasibility",),
            ),
            _node(
                "complete",
                WorkflowNodeType.COMPLETE,
                "CompleteCrossDomainReview",
                dependencies=("validate",),
            ),
        ),
    )

    # 6. plan_drift_review
    plan_drift_review = _workflow(
        "life_plan.plan_drift_review",
        description="Detect and analyze divergence between planned milestones and actual reality.",
        purpose="Evaluate drift without automatically inferring goal abandonment.",
        core_nodes=(
            _node(
                "review_drift",
                WorkflowNodeType.EXECUTE_OPERATION,
                "ReviewPlanDrift",
                dependencies=("reason",),
                operation_id="life_plan.review_goals",
            ),
            _node(
                "evaluate_adjustments",
                WorkflowNodeType.EXECUTE_OPERATION,
                "EvaluatePlanAdjustments",
                dependencies=("review_drift",),
                operation_id="life_plan.update_plan",
            ),
            _node(
                "validate",
                WorkflowNodeType.VALIDATE,
                "ValidatePlanDriftReview",
                dependencies=("evaluate_adjustments",),
            ),
            _node(
                "complete",
                WorkflowNodeType.COMPLETE,
                "CompletePlanDriftReview",
                dependencies=("validate",),
            ),
        ),
    )

    # 7. annual_life_plan_update
    annual_life_plan_update = _workflow(
        "life_plan.annual_life_plan_update",
        description="Comprehensive annual life review and multi-year trajectory calibration.",
        purpose="Update annual goals, milestones and scenario parameters with explicit confirmation.",
        core_nodes=(
            _node(
                "update_plan",
                WorkflowNodeType.EXECUTE_OPERATION,
                "UpdateAnnualPlan",
                dependencies=("reason",),
                operation_id="life_plan.update_plan",
            ),
            _node(
                "create_milestones",
                WorkflowNodeType.EXECUTE_OPERATION,
                "CreateAnnualMilestones",
                dependencies=("update_plan",),
                operation_id="life_plan.create_milestones",
            ),
            _node(
                "validate",
                WorkflowNodeType.VALIDATE,
                "ValidateAnnualPlanUpdate",
                dependencies=("create_milestones",),
            ),
            _node(
                "complete",
                WorkflowNodeType.COMPLETE,
                "CompleteAnnualPlanUpdate",
                dependencies=("validate",),
            ),
        ),
    )

    by_id = {
        "life_plan.life_plan_setup": life_plan_setup,
        "life_plan.quarterly_life_review": quarterly_life_review,
        "life_plan.scenario_comparison": scenario_comparison,
        "life_plan.goal_dependency_review": goal_dependency_review,
        "life_plan.cross_domain_impact_review": cross_domain_impact_review,
        "life_plan.plan_drift_review": plan_drift_review,
        "life_plan.annual_life_plan_update": annual_life_plan_update,
    }

    return tuple(by_id[wf_id] for wf_id in CANONICAL_LIFE_PLAN_WORKFLOW_IDS)


def execute_cross_domain_impact_workflow(
    *,
    primary_goal: dict[str, Any] | None = None,
    supporting_domain_contributions: list[Any] | None = None,
    resource_estimates: dict[str, Any] | None = None,
    alternative_routes: list[Any] | None = None,
) -> dict[str, Any]:
    """Execute cross domain impact review workflow safely (Major Decision Support)."""
    contributions = list(supporting_domain_contributions or [])
    applied_contributions = []

    for contrib in contributions:
        if isinstance(contrib, AuthorizedCrossDomainContribution) and getattr(
            contrib, "_is_verified", False
        ):
            applied_contributions.append(contrib.projection)
        elif isinstance(contrib, dict):
            if "authorized_artifact" in contrib and isinstance(
                contrib["authorized_artifact"], AuthorizedCrossDomainContribution
            ):
                applied_contributions.append(contrib["authorized_artifact"].projection)
            else:
                eval_res = evaluate_cross_domain_impact(projection=contrib)
                if eval_res.get("applied"):
                    applied_contributions.append(eval_res["contribution"])

    res_eval = evaluate_resource_constraints(**(resource_estimates or {}))

    return {
        "status": "completed",
        "workflow_id": "life_plan.cross_domain_impact_review",
        "primary_goal": primary_goal,
        "supporting_contributions_applied": len(applied_contributions),
        "resource_feasibility": res_eval["status"],
        "is_decision_support": True,
        "alternatives_preserved": True,
        "alternative_routes": list(alternative_routes or []),
        "disclaimer_present": True,
        "is_decision": False,
        "is_commitment": False,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


__all__ = [
    "LIFE_PLAN_WORKFLOW_IDS",
    "LIFE_PLAN_WORKFLOW_NAMES_BY_ID",
    "build_life_plan_workflow_definitions",
    "execute_cross_domain_impact_workflow",
]
