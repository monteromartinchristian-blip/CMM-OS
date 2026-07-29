"""Phase 9.8 – Policy Engine Adapters.

Translates domain contracts from Phase 9.5 (Cognitive), 9.6 (Acquisition), and 9.7 (Planner)
into canonical PolicyEvaluationRequest structures without modifying the underlying domain contracts.
"""

from __future__ import annotations

from typing import Any

from .enums import PolicyResourceKind, PolicyRiskLevel, PolicySubjectKind
from .policy_contracts import (
    PolicyAction,
    PolicyEnvironment,
    PolicyEvaluationRequest,
    PolicyResource,
    PolicySubject,
)


def _map_risk_level(risk_val: Any) -> PolicyRiskLevel:
    """Safely map any risk representation to PolicyRiskLevel."""
    if isinstance(risk_val, PolicyRiskLevel):
        return risk_val
    if hasattr(risk_val, "value"):
        risk_str = str(risk_val.value).lower()
    else:
        risk_str = str(risk_val or "low").lower()

    if risk_str in ("critical", "blocking"):
        return PolicyRiskLevel.CRITICAL
    if risk_str in ("high", "severe"):
        return PolicyRiskLevel.HIGH
    if risk_str in ("medium", "moderate"):
        return PolicyRiskLevel.MEDIUM
    if risk_str in ("low", "minor"):
        return PolicyRiskLevel.LOW
    if risk_str in ("none", "zero"):
        return PolicyRiskLevel.NONE
    return PolicyRiskLevel.LOW


def create_request_from_workflow_plan(
    plan: Any,
    actor_id: str | None = None,
    permissions: tuple[str, ...] = (),
    environment_name: str = "development",
) -> PolicyEvaluationRequest:
    """Translate an AgentWorkflowPlan into a PolicyEvaluationRequest."""
    plan_id = getattr(plan, "id", "plan-unknown")
    goal_id = getattr(plan, "goal_id", None)
    workflow_id = getattr(plan, "workflow_id", plan_id)

    status_val = getattr(plan, "status", "draft")
    if hasattr(status_val, "value"):
        status_val = status_val.value

    validation = getattr(plan, "validation", None)
    v_status_val = getattr(validation, "status", "pending")
    if hasattr(v_status_val, "value"):
        v_status_val = v_status_val.value

    is_validated = bool(getattr(validation, "is_valid", False))

    tasks = getattr(plan, "tasks", ())
    operations = getattr(plan, "operations", ())
    approval_nodes = getattr(plan, "approval_nodes", ())
    rollback_strat = getattr(plan, "rollback_strategy", None)
    risk_val = getattr(plan, "risk", PolicyRiskLevel.LOW)

    subject = PolicySubject(
        id=actor_id or goal_id or "agent-workflow-planner",
        kind=PolicySubjectKind.AGENT,
        permissions=permissions,
    )
    resource = PolicyResource(
        id=workflow_id,
        kind=PolicyResourceKind.WORKFLOW,
        sensitivity="internal",
    )
    action = PolicyAction(
        name="execute_workflow_plan",
        operation_name="workflow_plan",
        parameters={
            "plan_id": plan_id,
            "plan_status": str(status_val),
            "plan_validation_status": str(v_status_val),
            "is_validated": is_validated,
            "has_pending_approvals": len(approval_nodes) > 0,
            "task_count": len(tasks),
            "operation_count": len(operations),
            "has_rollback": rollback_strat is not None,
        },
        is_mutation=True,
        is_reversible=rollback_strat is not None,
    )

    return PolicyEvaluationRequest(
        id=f"req-plan-{plan_id}",
        subject=subject,
        resource=resource,
        action=action,
        environment=PolicyEnvironment(name=environment_name),
        permissions=permissions,
        risk=_map_risk_level(risk_val),
        goal_id=goal_id,
        workflow_plan_id=plan_id,
        actor_id=actor_id,
    )


def create_request_from_workflow_operation(
    operation: Any,
    actor_id: str | None = None,
    permissions: tuple[str, ...] = (),
    environment_name: str = "development",
) -> PolicyEvaluationRequest:
    """Translate an AgentWorkflowOperation into a PolicyEvaluationRequest."""
    op_id = getattr(operation, "id", "op-unknown")
    op_name = getattr(operation, "operation_name", "unknown_operation")
    op_params = getattr(operation, "parameters", {})
    is_mut = True
    is_rev = bool(getattr(operation, "reversible", False))
    risk_val = getattr(operation, "risk", PolicyRiskLevel.LOW)

    subject = PolicySubject(
        id=actor_id or "agent-executor",
        kind=PolicySubjectKind.AGENT,
        permissions=permissions,
    )
    resource = PolicyResource(
        id=op_id,
        kind=PolicyResourceKind.OPERATION,
        sensitivity="internal",
    )
    action = PolicyAction(
        name=op_name,
        operation_name=op_name,
        parameters=dict(op_params or {}),
        is_mutation=is_mut,
        is_reversible=is_rev,
    )

    return PolicyEvaluationRequest(
        id=f"req-op-{op_id}",
        subject=subject,
        resource=resource,
        action=action,
        environment=PolicyEnvironment(name=environment_name),
        permissions=permissions,
        risk=_map_risk_level(risk_val),
        operation_id=op_id,
        actor_id=actor_id,
    )


def create_request_from_acquisition_decision(
    decision: Any,
    actor_id: str | None = None,
    permissions: tuple[str, ...] = (),
    environment_name: str = "development",
) -> PolicyEvaluationRequest:
    """Translate an InformationAcquisitionDecision into a PolicyEvaluationRequest."""
    dec_id = getattr(decision, "id", "acq-unknown")
    gap_id = getattr(decision, "gap_id", "gap-unknown")
    strat_val = getattr(decision, "strategy", "ask_user")
    if hasattr(strat_val, "value"):
        strat_val = strat_val.value

    sens_val = getattr(decision, "sensitivity", "internal")
    if hasattr(sens_val, "value"):
        sens_val = sens_val.value

    risk_val = getattr(decision, "risk", PolicyRiskLevel.LOW)
    params = getattr(decision, "parameters", {})
    is_blocking = getattr(decision, "is_blocking", params.get("is_blocking", False))
    requests_secret = getattr(
        decision, "requests_secret", params.get("requests_secret", False)
    )

    subject = PolicySubject(
        id=actor_id or "agent-info-acquirer",
        kind=PolicySubjectKind.AGENT,
        permissions=permissions,
    )
    resource = PolicyResource(
        id=gap_id,
        kind=PolicyResourceKind.ACQUISITION_STRATEGY,
        sensitivity=str(sens_val),
    )
    action = PolicyAction(
        name=str(strat_val),
        operation_name="acquire_information",
        parameters={
            "gap_id": gap_id,
            "is_blocking": is_blocking,
            "requests_secret": requests_secret,
            **dict(params or {}),
        },
        is_mutation=False,
        is_reversible=True,
    )

    return PolicyEvaluationRequest(
        id=f"req-acq-{dec_id}",
        subject=subject,
        resource=resource,
        action=action,
        environment=PolicyEnvironment(name=environment_name),
        permissions=permissions,
        sensitivity=str(sens_val),
        risk=_map_risk_level(risk_val),
        actor_id=actor_id,
    )


def create_request_from_cognitive_result(
    result: Any,
    actor_id: str | None = None,
    permissions: tuple[str, ...] = (),
    environment_name: str = "development",
) -> PolicyEvaluationRequest:
    """Translate an AgentCognitiveResult into a PolicyEvaluationRequest."""
    res_id = getattr(result, "id", "cog-unknown")
    rec_dec = getattr(result, "recommended_decision", "plan")
    if hasattr(rec_dec, "value"):
        rec_dec = rec_dec.value

    blocked = getattr(result, "blocked", False)
    req_user = getattr(result, "requires_user_input", False)
    req_res = getattr(result, "requires_resource", False)
    confidence = getattr(result, "confidence", 1.0)

    subject = PolicySubject(
        id=actor_id or "agent-cognitive-adapter",
        kind=PolicySubjectKind.AGENT,
        permissions=permissions,
    )
    resource = PolicyResource(
        id=res_id,
        kind=PolicyResourceKind.KNOWLEDGE,
        sensitivity="internal",
    )
    action = PolicyAction(
        name=str(rec_dec),
        operation_name="cognitive_recommendation",
        parameters={
            "blocked": blocked,
            "requires_user_input": req_user,
            "requires_resource": req_res,
            "confidence": confidence,
        },
        is_mutation=False,
        is_reversible=True,
    )

    return PolicyEvaluationRequest(
        id=f"req-cog-{res_id}",
        subject=subject,
        resource=resource,
        action=action,
        environment=PolicyEnvironment(name=environment_name),
        permissions=permissions,
        risk=PolicyRiskLevel.LOW,
        actor_id=actor_id,
    )
