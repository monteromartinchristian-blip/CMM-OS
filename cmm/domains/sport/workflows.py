"""Phase 10.28 — Sport Domain Workflows.

Five declarative Sport workflows built on shared DomainWorkflowDefinition:
1. sport.training_plan_setup
2. sport.weekly_training_review
3. sport.recovery_review
4. sport.progress_review
5. sport.return_to_training_with_health_constraints

Safety ordering: ``load -> profile -> reason`` is a strict dependency chain.
A terminal ``COMPLETE`` node always transitively depends on a ``VALIDATE`` node.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from cmm.domains.sport.catalog import (
    CANONICAL_SPORT_WORKFLOW_IDS,
)
from cmm.domains.sport.rules import (
    evaluate_health_constraint,
    evaluate_injury_signal,
    evaluate_recovery,
)
from cmm.domains.workflow_contracts import DomainWorkflowDefinition
from cmm.workflows.contracts import WorkflowNode
from cmm.workflows.enums import WorkflowNodeType

SPORT_WORKFLOW_IDS: tuple[str, ...] = CANONICAL_SPORT_WORKFLOW_IDS

SPORT_WORKFLOW_NAMES_BY_ID: dict[str, str] = {
    "sport.training_plan_setup": "Training Plan Setup",
    "sport.weekly_training_review": "Weekly Training Review",
    "sport.recovery_review": "Recovery Review",
    "sport.progress_review": "Progress Review",
    "sport.return_to_training_with_health_constraints": "Return to Training",
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
        _node("load", WorkflowNodeType.LOAD_RESOURCE, "LoadSportSources"),
        _node(
            "profile",
            WorkflowNodeType.APPLY_PROFILE,
            "ApplySportProfile",
            dependencies=("load",),
        ),
        _node(
            "reason",
            WorkflowNodeType.REASON,
            "ApplySportRules",
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
        domain_id="domain:sport",
        version="1.0.0",
        name=SPORT_WORKFLOW_NAMES_BY_ID[workflow_id],
        description=description,
        nodes=(*_ordered_prefix(), *core_nodes),
        completion_criteria={
            "all_required_nodes_completed": True,
            "no_blocking_failures": True,
        },
        metadata={
            "phase": "10.28",
            "purpose": purpose,
            "non_autonomous": True,
            **(extra_metadata or {}),
        },
    )


def build_sport_workflow_definitions() -> tuple[DomainWorkflowDefinition, ...]:
    """Build all five canonical Sport Domain workflow definitions deterministically."""
    # 1. training_plan_setup
    training_plan_setup = _workflow(
        "sport.training_plan_setup",
        description="Set up a new athletic training plan proposal.",
        purpose="Define goals, initial volume/intensity/frequency and structure.",
        core_nodes=(
            _node(
                "create_plan",
                WorkflowNodeType.EXECUTE_OPERATION,
                "CreateTrainingPlan",
                dependencies=("reason",),
                operation_id="sport.create_training_plan",
            ),
            _node(
                "validate",
                WorkflowNodeType.VALIDATE,
                "ValidateTrainingPlan",
                dependencies=("create_plan",),
            ),
            _node(
                "complete",
                WorkflowNodeType.COMPLETE,
                "CompleteTrainingPlanSetup",
                dependencies=("validate",),
            ),
        ),
    )

    # 2. weekly_training_review
    weekly_training_review = _workflow(
        "sport.weekly_training_review",
        description="Review weekly training load, progress and upcoming workouts.",
        purpose="Evaluate volume, intensity and adjust next week's load.",
        core_nodes=(
            _node(
                "review_progress",
                WorkflowNodeType.EXECUTE_OPERATION,
                "ReviewWeeklyProgress",
                dependencies=("reason",),
                operation_id="sport.review_progress",
            ),
            _node(
                "adjust_load",
                WorkflowNodeType.EXECUTE_OPERATION,
                "AdjustTrainingLoad",
                dependencies=("review_progress",),
                operation_id="sport.adjust_training_load",
            ),
            _node(
                "validate",
                WorkflowNodeType.VALIDATE,
                "ValidateWeeklyReview",
                dependencies=("adjust_load",),
            ),
            _node(
                "complete",
                WorkflowNodeType.COMPLETE,
                "CompleteWeeklyReview",
                dependencies=("validate",),
            ),
        ),
    )

    # 3. recovery_review
    recovery_review = _workflow(
        "sport.recovery_review",
        description="Assess physical recovery, fatigue and readiness.",
        purpose="Evaluate rest, fatigue, pain and update mutable readiness state.",
        core_nodes=(
            _node(
                "review_recovery",
                WorkflowNodeType.EXECUTE_OPERATION,
                "ReviewRecoveryState",
                dependencies=("reason",),
                operation_id="sport.review_recovery",
            ),
            _node(
                "validate",
                WorkflowNodeType.VALIDATE,
                "ValidateRecoveryState",
                dependencies=("review_recovery",),
            ),
            _node(
                "complete",
                WorkflowNodeType.COMPLETE,
                "CompleteRecoveryReview",
                dependencies=("validate",),
            ),
        ),
    )

    # 4. progress_review
    progress_review = _workflow(
        "sport.progress_review",
        description="Longer term progress review across training metrics and measurements.",
        purpose="Evaluate trends from ordered comparable observations.",
        core_nodes=(
            _node(
                "review_progress",
                WorkflowNodeType.EXECUTE_OPERATION,
                "ReviewProgressTrends",
                dependencies=("reason",),
                operation_id="sport.review_progress",
            ),
            _node(
                "validate",
                WorkflowNodeType.VALIDATE,
                "ValidateProgressReview",
                dependencies=("review_progress",),
            ),
            _node(
                "complete",
                WorkflowNodeType.COMPLETE,
                "CompleteProgressReview",
                dependencies=("validate",),
            ),
        ),
    )

    # 5. return_to_training_with_health_constraints
    return_to_training = _workflow(
        "sport.return_to_training_with_health_constraints",
        description="Return to training workflow with authorized Health constraints.",
        purpose="Coordinate return-to-activity under restrictive functional Health constraints.",
        core_nodes=(
            _node(
                "identify_risks",
                WorkflowNodeType.EXECUTE_OPERATION,
                "IdentifyInjuryRisks",
                dependencies=("reason",),
                operation_id="sport.identify_risks",
            ),
            _node(
                "adjust_load",
                WorkflowNodeType.EXECUTE_OPERATION,
                "ApplyConstraintLoadAdjustment",
                dependencies=("identify_risks",),
                operation_id="sport.adjust_training_load",
            ),
            _node(
                "validate",
                WorkflowNodeType.VALIDATE,
                "ValidateReturnToTrainingPlan",
                dependencies=("adjust_load",),
            ),
            _node(
                "complete",
                WorkflowNodeType.COMPLETE,
                "CompleteReturnToTraining",
                dependencies=("validate",),
            ),
        ),
    )

    by_id = {
        "sport.training_plan_setup": training_plan_setup,
        "sport.weekly_training_review": weekly_training_review,
        "sport.recovery_review": recovery_review,
        "sport.progress_review": progress_review,
        "sport.return_to_training_with_health_constraints": return_to_training,
    }

    return tuple(by_id[wf_id] for wf_id in CANONICAL_SPORT_WORKFLOW_IDS)


def execute_return_to_training_workflow(
    *,
    rest_hours: float = 8.0,
    fatigue_score: int = 2,
    pain_score: int = 0,
    health_constraint: dict[str, Any] | None = None,
    is_authorized: bool = False,
    is_current: bool = True,
) -> dict[str, Any]:
    """Execute return to training workflow with Health constraints."""
    rec_res = evaluate_recovery(rest_hours=rest_hours, fatigue_score=fatigue_score, pain_score=pain_score)
    readiness = rec_res["readiness_state"]

    inj_res = evaluate_injury_signal(pain_score=pain_score, fatigue_score=fatigue_score)
    signal_action = inj_res["action"]

    hc_res = evaluate_health_constraint(projection=health_constraint, is_authorized=is_authorized, is_current=is_current)

    rec = "continue"
    if signal_action == "stop_and_check" or readiness == "hold":
        rec = "stop_and_check"
    elif hc_res["applied"]:
        rec = "reduce_load"
    elif signal_action == "reduce_load" or readiness == "limited":
        rec = "reduce_load"

    return {
        "status": "completed",
        "workflow_id": "sport.return_to_training_with_health_constraints",
        "recommendation": rec,
        "readiness_state": readiness,
        "injury_signal_action": signal_action,
        "health_constraint_applied": hc_res["applied"],
        "is_diagnosis": False,
        "treatment_modified": False,
        "clinical_clearance_claimed": False,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


__all__ = [
    "SPORT_WORKFLOW_IDS",
    "SPORT_WORKFLOW_NAMES_BY_ID",
    "build_sport_workflow_definitions",
    "execute_return_to_training_workflow",
]
