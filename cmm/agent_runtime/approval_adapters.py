"""Phase 9.10 – Human Approval System Adapters.

Pure functional adapters translating evaluation outputs from Policy Engine,
Autonomy Levels, and Workflow Planner into canonical ApprovalRequirement contracts.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from types import MappingProxyType
from typing import Any

from .approval_contracts import ApprovalRequirement
from .enums import (
    ApprovalRequirementSource,
    AutonomyDecision,
    PolicyDecision,
    PolicyRiskLevel,
)
from .errors import (
    ApprovalAutonomyIntegrationError,
    ApprovalPolicyIntegrationError,
    InvalidApprovalContractError,
)


def _map_risk(val: Any) -> PolicyRiskLevel:
    """Helper to safely map risk value to PolicyRiskLevel."""
    if isinstance(val, PolicyRiskLevel):
        return val
    if hasattr(val, "value"):
        v_str = str(val.value).lower()
    else:
        v_str = str(val or "medium").lower()

    if v_str in ("critical", "blocking"):
        return PolicyRiskLevel.CRITICAL
    if v_str in ("high", "severe"):
        return PolicyRiskLevel.HIGH
    if v_str in ("medium", "moderate"):
        return PolicyRiskLevel.MEDIUM
    if v_str in ("low", "minor"):
        return PolicyRiskLevel.LOW
    if v_str in ("none", "zero"):
        return PolicyRiskLevel.NONE
    return PolicyRiskLevel.MEDIUM


def create_requirement_from_policy(
    policy_result: Any,
    title: str | None = None,
    description: str | None = None,
    agent_run_id: str | None = None,
    goal_id: str | None = None,
    workflow_id: str | None = None,
    operation_id: str | None = None,
    required_approvers: tuple[str, ...] = (),
    minimum_approvals: int = 1,
    expires_at: datetime | None = None,
    metadata: dict[str, Any] | None = None,
) -> ApprovalRequirement:
    """Translate a PolicyEvaluationResult into an ApprovalRequirement.

    Fail-safe rule: Policy DENY decision CANNOT be converted into an approvable request.
    Raises ApprovalPolicyIntegrationError if policy decision is DENY or denied is True.
    """
    decision = getattr(policy_result, "decision", None)
    is_denied = getattr(policy_result, "denied", False)

    if decision == PolicyDecision.DENY or is_denied:
        raise ApprovalPolicyIntegrationError(
            "Policy evaluation returned DENY. Policy DENY cannot be converted into an executable approval request."
        )

    requires_approval = getattr(policy_result, "requires_approval", False)

    # Check for REQUIRE_APPROVAL obligation if requires_approval is False
    obligations = getattr(policy_result, "obligations", ())
    has_approval_obligation = any(
        getattr(ob, "kind", None) == "require_approval"
        or getattr(ob, "kind", None) == "REQUIRE_APPROVAL"
        for ob in obligations
    )

    if (
        not requires_approval
        and not has_approval_obligation
        and decision != PolicyDecision.REQUIRE_APPROVAL
    ):
        raise InvalidApprovalContractError(
            "PolicyEvaluationResult does not require approval (requires_approval=False, no approval obligation)."
        )

    req_id = f"req-pol-{uuid.uuid4().hex[:12]}"
    res_id = getattr(policy_result, "id", "unknown-policy-result")
    req_title = title or f"Policy Approval Required: {res_id}"
    req_desc = (
        description
        or f"Policy evaluation {res_id} mandated human approval prior to execution."
    )

    reason_codes = getattr(policy_result, "reason_codes", ())
    meta = dict(getattr(policy_result, "metadata", {}) or {})
    if metadata:
        meta.update(metadata)
    meta["policy_result_id"] = res_id
    meta["policy_request_id"] = getattr(policy_result, "request_id", None)

    risk_level = _map_risk(meta.get("risk_level", PolicyRiskLevel.MEDIUM))

    return ApprovalRequirement(
        id=req_id,
        source=ApprovalRequirementSource.POLICY,
        title=req_title,
        description=req_desc,
        reason_codes=tuple(reason_codes),
        required_approvers=required_approvers,
        minimum_approvals=minimum_approvals,
        risk_level=risk_level,
        scope="policy_check",
        agent_run_id=agent_run_id,
        goal_id=goal_id,
        workflow_id=workflow_id,
        operation_id=operation_id,
        expires_at=expires_at,
        metadata=MappingProxyType(dict(meta)),
    )


def create_requirement_from_autonomy(
    autonomy_result: Any,
    title: str | None = None,
    description: str | None = None,
    agent_run_id: str | None = None,
    goal_id: str | None = None,
    workflow_id: str | None = None,
    operation_id: str | None = None,
    required_approvers: tuple[str, ...] = (),
    minimum_approvals: int = 1,
    expires_at: datetime | None = None,
    metadata: dict[str, Any] | None = None,
) -> ApprovalRequirement:
    """Translate an AutonomyEvaluationResult into an ApprovalRequirement.

    Fail-safe rule: Autonomy DENY decision CANNOT be converted into an approvable request.
    Raises ApprovalAutonomyIntegrationError if autonomy decision is DENY or denied is True.
    """
    decision = getattr(autonomy_result, "decision", None)
    is_denied = getattr(autonomy_result, "denied", False)

    if decision == AutonomyDecision.DENY or is_denied:
        raise ApprovalAutonomyIntegrationError(
            "Autonomy evaluation returned DENY. Autonomy DENY cannot be converted into an executable approval request."
        )

    requires_approval = getattr(autonomy_result, "requires_approval", False)
    if not requires_approval and decision != AutonomyDecision.REQUIRE_APPROVAL:
        raise InvalidApprovalContractError(
            "AutonomyEvaluationResult does not require approval (requires_approval=False)."
        )

    req_id = f"req-auto-{uuid.uuid4().hex[:12]}"
    res_id = getattr(autonomy_result, "id", "unknown-autonomy-result")
    level_val = getattr(autonomy_result, "level", "unknown-level")

    req_title = title or f"Autonomy Elevation Approval Required (Level {level_val})"
    req_desc = (
        description
        or f"Autonomy evaluation {res_id} at Level {level_val} requires human confirmation."
    )

    reason_codes = getattr(autonomy_result, "reason_codes", ())
    meta = dict(getattr(autonomy_result, "metadata", {}) or {})
    if metadata:
        meta.update(metadata)
    meta["autonomy_result_id"] = res_id
    meta["autonomy_level"] = str(level_val)

    return ApprovalRequirement(
        id=req_id,
        source=ApprovalRequirementSource.AUTONOMY,
        title=req_title,
        description=req_desc,
        reason_codes=tuple(reason_codes),
        required_approvers=required_approvers,
        minimum_approvals=minimum_approvals,
        risk_level=PolicyRiskLevel.HIGH,
        scope="autonomy_capability",
        agent_run_id=agent_run_id,
        goal_id=goal_id,
        workflow_id=workflow_id,
        operation_id=operation_id,
        expires_at=expires_at,
        metadata=MappingProxyType(dict(meta)),
    )


def create_requirement_from_workflow_plan(
    plan: Any,
    node_id: str | None = None,
    title: str | None = None,
    description: str | None = None,
    agent_run_id: str | None = None,
    required_approvers: tuple[str, ...] = (),
    minimum_approvals: int = 1,
    expires_at: datetime | None = None,
    metadata: dict[str, Any] | None = None,
) -> ApprovalRequirement:
    """Translate a WorkflowPlan approval node into an ApprovalRequirement."""
    plan_id = getattr(plan, "id", "plan-unknown")
    goal_id = getattr(plan, "goal_id", None)
    workflow_id = getattr(plan, "workflow_id", plan_id)

    req_id = f"req-wf-{uuid.uuid4().hex[:12]}"
    req_title = title or f"Workflow Plan Approval Required: {plan_id}"
    req_desc = (
        description
        or f"AgentWorkflowPlan {plan_id} node {node_id or 'all'} mandates human approval."
    )

    meta = {"plan_id": plan_id, "node_id": node_id}
    if metadata:
        meta.update(metadata)

    risk_val = getattr(plan, "risk", PolicyRiskLevel.MEDIUM)
    risk_level = _map_risk(risk_val)

    return ApprovalRequirement(
        id=req_id,
        source=ApprovalRequirementSource.WORKFLOW,
        title=req_title,
        description=req_desc,
        reason_codes=("workflow.approval_node_required",),
        required_approvers=required_approvers,
        minimum_approvals=minimum_approvals,
        risk_level=risk_level,
        scope="workflow_node",
        agent_run_id=agent_run_id,
        goal_id=goal_id,
        workflow_id=workflow_id,
        operation_id=node_id,
        expires_at=expires_at,
        metadata=MappingProxyType(dict(meta)),
    )
