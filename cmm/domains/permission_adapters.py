"""Pure permission adapters for domain rules, operations and workflows.

The adapters translate existing domain contracts into common permission requests;
they never execute, schedule, or grant permissions.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from datetime import datetime
from typing import Any

from cmm.agent_runtime.agent_security_enums import SensitivityLevel
from cmm.agent_runtime.domain_permission_contracts import (
    PermissionApprovalRequirement,
    PermissionCapability,
    PermissionOutcome,
)
from cmm.domains.enums import DomainOperationType
from cmm.domains.operation_contracts import DomainOperationDefinition
from cmm.domains.permission_contracts import (
    CrossDomainPermissionRequest,
    DomainPermissionRequest,
)
from cmm.domains.permission_resolution import DomainPermissionResolver
from cmm.domains.rule_contracts import DomainReasoningRuleDefinition
from cmm.domains.workflow_contracts import DomainWorkflowDefinition
from cmm.workflows.contracts import WorkflowNode
from cmm.workflows.enums import WorkflowNodeType


@dataclass(frozen=True, slots=True)
class DomainOperationRequirementDecision:
    permission: str
    decision: PermissionOutcome
    reasons: tuple[str, ...] = ()
    provenance: tuple[str, ...] = ()
    approval_requirements: tuple[PermissionApprovalRequirement, ...] = ()
    effective_constraints: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class DomainOperationPermissionDecision:
    operation_id: str
    operation_version: str
    decision: PermissionOutcome
    reasons: tuple[str, ...] = ()
    approval_requirements: tuple[PermissionApprovalRequirement, ...] = ()
    requirement_decisions: tuple[DomainOperationRequirementDecision, ...] = ()
    provenance: tuple[str, ...] = ()
    effective_constraints: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class DomainWorkflowNodePermissionDecision:
    node_id: str
    required: bool
    decision: PermissionOutcome
    reasons: tuple[str, ...] = ()
    provenance: tuple[str, ...] = ()
    approval_requirements: tuple[PermissionApprovalRequirement, ...] = ()
    effective_constraints: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class DomainWorkflowPermissionDecision:
    workflow_id: str
    workflow_version: str
    decision: PermissionOutcome
    blocked_nodes: tuple[str, ...] = ()
    approval_requirements: tuple[PermissionApprovalRequirement, ...] = ()
    provenance: tuple[dict[str, Any], ...] = ()
    allowed_nodes: tuple[str, ...] = ()
    approval_nodes: tuple[str, ...] = ()
    node_decisions: tuple[DomainWorkflowNodePermissionDecision, ...] = ()
    requirement_decisions: tuple[DomainOperationRequirementDecision, ...] = ()
    effective_constraints: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class DomainRulePermissionDecision:
    rule_id: str
    decision: PermissionOutcome
    required: bool
    blocked: bool
    partial_enforcement: bool
    provenance: tuple[str, ...] = ()


def request_for_operation(*, request_id: str, domain_id: str, actor_id: str, session_id: str, operation_id: str, operation_version: str | None = None, purpose: str | None = None, sensitivity: SensitivityLevel | None = None) -> DomainPermissionRequest:
    return DomainPermissionRequest(request_id, PermissionCapability.OPERATION_EXECUTE, domain_id, actor_id, session_id, operation_id=operation_id, operation_version=operation_version, purpose=purpose, sensitivity_level=sensitivity)


def request_for_workflow(*, request_id: str, domain_id: str, actor_id: str, session_id: str, workflow_id: str, workflow_version: str | None = None, purpose: str | None = None, sensitivity: SensitivityLevel | None = None) -> DomainPermissionRequest:
    return DomainPermissionRequest(request_id, PermissionCapability.WORKFLOW_EXECUTE, domain_id, actor_id, session_id, workflow_id=workflow_id, workflow_version=workflow_version, purpose=purpose, sensitivity_level=sensitivity)


def request_for_rule_permission(*, request_id: str, domain_id: str, actor_id: str, session_id: str, permission: str) -> DomainPermissionRequest:
    try:
        action = PermissionCapability(permission)
    except ValueError as exc:
        raise ValueError("rule permission must be a known capability") from exc
    return DomainPermissionRequest(request_id, action, domain_id, actor_id, session_id)


def _approval_for_operation(operation: DomainOperationDefinition, *, request_id: str, actor_id: str, session_id: str, reason_code: str) -> PermissionApprovalRequirement:
    return PermissionApprovalRequirement(
        requirement_id=f"operation:{operation.operation_id}:{operation.version}:{request_id}:{reason_code}",
        action=PermissionCapability.OPERATION_EXECUTE, actor_id=actor_id, session_id=session_id,
        domain_id=operation.domain_id, operation_id=operation.operation_id,
        operation_version=operation.version,
        fingerprint=f"{request_id}:{operation.operation_id}:{operation.version}:{actor_id}:{session_id}:{reason_code}",
        scope="operation", reason_code=reason_code, risk=operation.risk_level.value,
    )


def _dedupe_requirements(requirements: tuple[PermissionApprovalRequirement, ...]) -> tuple[PermissionApprovalRequirement, ...]:
    return tuple({item.requirement_id: item for item in requirements}.values())


def evaluate_domain_operation(
    operation: DomainOperationDefinition,
    resolver: DomainPermissionResolver,
    *, request_id: str, actor_id: str, session_id: str, now: datetime | None = None,
) -> DomainOperationPermissionDecision:
    """Evaluate every declared operation constraint without executing it."""
    sensitivity = (
        SensitivityLevel.CONFIDENTIAL
        if operation.operation_type is DomainOperationType.SENSITIVE
        else SensitivityLevel.INTERNAL
    )
    purpose = f"operation:{operation.operation_id}"
    root = resolver.resolve(request_for_operation(
        request_id=request_id, domain_id=operation.domain_id, actor_id=actor_id,
        session_id=session_id, operation_id=operation.operation_id,
        operation_version=operation.version, purpose=purpose, sensitivity=sensitivity,
    ), now=now)
    requirements: list[DomainOperationRequirementDecision] = []
    extra_capabilities = list(operation.required_permissions)
    if operation.operation_type is DomainOperationType.EXTERNAL:
        extra_capabilities.append(PermissionCapability.SEARCH_EXTERNAL.value)
    if operation.operation_type is DomainOperationType.SENSITIVE:
        extra_capabilities.append(PermissionCapability.SENSITIVE_INFERENCE.value)
    for permission in dict.fromkeys(extra_capabilities):
        try:
            action = PermissionCapability(permission)
        except ValueError:
            requirements.append(DomainOperationRequirementDecision(permission, PermissionOutcome.DENY, ("unknown_required_permission",)))
            continue
        resolution = resolver.resolve(DomainPermissionRequest(
            request_id, action, operation.domain_id, actor_id, session_id,
            operation_id=operation.operation_id, operation_version=operation.version,
            purpose=purpose, sensitivity_level=sensitivity,
        ), now=now)
        effective = resolution.effective_permissions
        requirements.append(DomainOperationRequirementDecision(
            permission, effective.decision, effective.reasons,
            tuple(item.source_id for item in effective.layer_evaluations),
            effective.approval_requirements,
            effective.effective_constraints,
        ))
    for resource_id in operation.required_resources:
        resolution = resolver.resolve(DomainPermissionRequest(
            request_id, PermissionCapability.RESOURCE_READ, operation.domain_id, actor_id,
            session_id, resource_id=resource_id,
            operation_id=operation.operation_id, operation_version=operation.version,
            purpose=purpose, sensitivity_level=sensitivity,
        ), now=now)
        effective = resolution.effective_permissions
        requirements.append(DomainOperationRequirementDecision(
            f"resource:{resource_id}", effective.decision, effective.reasons,
            tuple(item.source_id for item in effective.layer_evaluations),
            effective.approval_requirements,
            effective.effective_constraints,
        ))
    all_decisions = (root.effective_permissions.decision, *(item.decision for item in requirements))
    reasons = (*root.effective_permissions.reasons, *(reason for item in requirements for reason in item.reasons))
    provenance = tuple(item.source_id for item in root.effective_permissions.layer_evaluations)
    if not operation.enabled:
        return DomainOperationPermissionDecision(operation.operation_id, operation.version, PermissionOutcome.DENY, (*reasons, "operation_disabled"), requirement_decisions=tuple(requirements), provenance=provenance, effective_constraints=root.effective_permissions.effective_constraints)
    if PermissionOutcome.DENY in all_decisions:
        return DomainOperationPermissionDecision(operation.operation_id, operation.version, PermissionOutcome.DENY, reasons, requirement_decisions=tuple(requirements), provenance=provenance, effective_constraints=root.effective_permissions.effective_constraints)
    approvals = list(root.effective_permissions.approval_requirements)
    approvals.extend(
        requirement
        for item in requirements
        for requirement in item.approval_requirements
    )
    if operation.requires_approval:
        approvals.append(_approval_for_operation(operation, request_id=request_id, actor_id=actor_id, session_id=session_id, reason_code="operation_requires_approval"))
    if not operation.reversible:
        approvals.append(_approval_for_operation(operation, request_id=request_id, actor_id=actor_id, session_id=session_id, reason_code="irreversible_operation"))
    approvals = list(_dedupe_requirements(tuple(approvals)))
    decision = PermissionOutcome.APPROVAL_REQUIRED if approvals or PermissionOutcome.APPROVAL_REQUIRED in all_decisions else PermissionOutcome.ALLOW
    return DomainOperationPermissionDecision(operation.operation_id, operation.version, decision, reasons, tuple(approvals), tuple(requirements), provenance, root.effective_permissions.effective_constraints)


def _node_decision(
    node: WorkflowNode, workflow: DomainWorkflowDefinition, resolver: DomainPermissionResolver,
    *, request_id: str, actor_id: str, session_id: str,
    operations: Mapping[tuple[str, str | None], DomainOperationDefinition],
    workflows: Mapping[tuple[str, str | None], DomainWorkflowDefinition],
    now: datetime | None = None,
) -> DomainWorkflowNodePermissionDecision:
    if node.operation_id is not None:
        operation = operations.get((node.operation_id, node.operation_version))
        if operation is None and node.operation_version is None:
            operation = next((candidate for (operation_id, _), candidate in operations.items() if operation_id == node.operation_id), None)
        if operation is None:
            return DomainWorkflowNodePermissionDecision(node.node_id, node.required, PermissionOutcome.DENY, ("operation_not_registered",), (node.operation_id,))
        result = evaluate_domain_operation(operation, resolver, request_id=f"{request_id}:{node.node_id}", actor_id=actor_id, session_id=session_id, now=now)
        requirements = tuple(
            replace(
                item,
                requirement_id=f"{item.requirement_id}:node:{node.node_id}",
                workflow_id=item.workflow_id or workflow.workflow_id,
                workflow_version=workflow.version,
                node_id=node.node_id,
                scope="node",
                fingerprint=f"{item.fingerprint}:{workflow.workflow_id}:{workflow.version}:{node.node_id}",
            )
            for item in result.approval_requirements
        )
        return DomainWorkflowNodePermissionDecision(node.node_id, node.required, result.decision, result.reasons, result.provenance, requirements, result.effective_constraints)
    if node.subworkflow_id is not None:
        child = workflows.get((node.subworkflow_id, node.subworkflow_version))
        if child is None and node.subworkflow_version is None:
            child = next((candidate for (workflow_id, _), candidate in workflows.items() if workflow_id == node.subworkflow_id), None)
        if child is None:
            return DomainWorkflowNodePermissionDecision(node.node_id, node.required, PermissionOutcome.DENY, ("subworkflow_not_registered",), (node.subworkflow_id,))
        cross_requirements: tuple[PermissionApprovalRequirement, ...] = ()
        cross_reasons: tuple[str, ...] = ()
        if child.domain_id != workflow.domain_id:
            cross = resolver.resolve_cross_domain(CrossDomainPermissionRequest(
                f"{request_id}:{node.node_id}:cross", workflow.domain_id, child.domain_id,
                requested_workflows=(child.workflow_id,), reason="subworkflow", actor_id=actor_id,
                session_id=session_id,
                sensitivity_level=child.sensitivity,
                capability=PermissionCapability.WORKFLOW_EXECUTE,
            ), now=now)
            if cross.decision is PermissionOutcome.DENY:
                return DomainWorkflowNodePermissionDecision(node.node_id, node.required, PermissionOutcome.DENY, cross.reasons, (workflow.domain_id, child.domain_id))
            cross_reasons = cross.reasons
            cross_requirements = cross.approval_requirements
        result = evaluate_domain_workflow(child, resolver, request_id=f"{request_id}:{node.node_id}", actor_id=actor_id, session_id=session_id, operations=operations, workflows=workflows, now=now)
        requirements = tuple(
            replace(
                item,
                requirement_id=f"{item.requirement_id}:node:{node.node_id}",
                workflow_id=item.workflow_id or workflow.workflow_id,
                workflow_version=workflow.version,
                node_id=node.node_id,
                scope="node",
                fingerprint=f"{item.fingerprint}:{workflow.workflow_id}:{workflow.version}:{node.node_id}",
            )
            for item in (*cross_requirements, *result.approval_requirements)
        )
        decision = (
            PermissionOutcome.APPROVAL_REQUIRED
            if requirements
            else result.decision
        )
        return DomainWorkflowNodePermissionDecision(
            node.node_id,
            node.required,
            decision,
            (*cross_reasons, result.decision.value),
            (child.workflow_id,),
            requirements,
        )
    if node.approval_gate is not None or node.node_type is WorkflowNodeType.REQUEST_APPROVAL:
        requirement = PermissionApprovalRequirement(
            requirement_id=f"workflow:{workflow.workflow_id}:{workflow.version}:{node.node_id}:{request_id}",
            action=PermissionCapability.WORKFLOW_EXECUTE, actor_id=actor_id, session_id=session_id,
            domain_id=workflow.domain_id, workflow_id=workflow.workflow_id, workflow_version=workflow.version,
            node_id=node.node_id,
            purpose=workflow.purpose, sensitivity=workflow.sensitivity,
            fingerprint=f"{request_id}:{workflow.workflow_id}:{workflow.version}:{node.node_id}:{actor_id}:{session_id}",
            scope="node", reason_code="workflow_approval_gate",
        )
        return DomainWorkflowNodePermissionDecision(node.node_id, node.required, PermissionOutcome.APPROVAL_REQUIRED, ("workflow_approval_gate",), (node.approval_gate or node.node_id,), (requirement,))
    return DomainWorkflowNodePermissionDecision(node.node_id, node.required, PermissionOutcome.ALLOW, ("node_has_no_permissioned_action",), (node.node_type.value,))


def evaluate_domain_workflow(
    workflow: DomainWorkflowDefinition, resolver: DomainPermissionResolver, *, request_id: str,
    actor_id: str, session_id: str,
    operations: Mapping[tuple[str, str | None], DomainOperationDefinition] | None = None,
    workflows: Mapping[tuple[str, str | None], DomainWorkflowDefinition] | None = None,
    now: datetime | None = None,
) -> DomainWorkflowPermissionDecision:
    """Evaluate each actual workflow node; no node is scheduled or executed."""
    root = resolver.resolve(request_for_workflow(request_id=request_id, domain_id=workflow.domain_id, actor_id=actor_id, session_id=session_id, workflow_id=workflow.workflow_id, workflow_version=workflow.version, purpose=workflow.purpose, sensitivity=workflow.sensitivity), supporting_domains=workflow.supporting_domain_ids, now=now)
    requirements: list[DomainOperationRequirementDecision] = []
    for permission in workflow.required_permissions:
        try:
            action = PermissionCapability(permission)
        except ValueError:
            requirements.append(DomainOperationRequirementDecision(
                permission, PermissionOutcome.DENY, ("unknown_required_permission",)
            ))
            continue
        effective = resolver.resolve(DomainPermissionRequest(
            f"{request_id}:permission:{permission}", action, workflow.domain_id,
            actor_id, session_id, workflow_id=workflow.workflow_id,
            workflow_version=workflow.version,
            purpose=workflow.purpose, sensitivity_level=workflow.sensitivity,
        ), now=now).effective_permissions
        requirements.append(DomainOperationRequirementDecision(
            permission, effective.decision, effective.reasons,
            tuple(item.source_id for item in effective.layer_evaluations),
            effective.approval_requirements,
            effective.effective_constraints,
        ))
    for resource_id in workflow.required_resources:
        effective = resolver.resolve(DomainPermissionRequest(
            f"{request_id}:resource:{resource_id}", PermissionCapability.RESOURCE_READ,
            workflow.domain_id, actor_id, session_id, resource_id=resource_id,
            workflow_id=workflow.workflow_id, workflow_version=workflow.version,
            purpose=workflow.purpose, sensitivity_level=workflow.sensitivity,
        ), now=now).effective_permissions
        requirements.append(DomainOperationRequirementDecision(
            f"resource:{resource_id}", effective.decision, effective.reasons,
            tuple(item.source_id for item in effective.layer_evaluations),
            effective.approval_requirements,
            effective.effective_constraints,
        ))
    operation_index = operations or {}
    workflow_index = workflows or {}
    nodes = tuple(_node_decision(node, workflow, resolver, request_id=request_id, actor_id=actor_id, session_id=session_id, operations=operation_index, workflows=workflow_index, now=now) for node in workflow.nodes)
    if not workflow.enabled or root.effective_permissions.decision is PermissionOutcome.DENY:
        reason = "workflow_disabled" if not workflow.enabled else "workflow_permission_denied"
        nodes = tuple(DomainWorkflowNodePermissionDecision(node.node_id, node.required, PermissionOutcome.DENY, (*node.reasons, reason), node.provenance, node.approval_requirements) for node in nodes)
    blocked = tuple(node.node_id for node in nodes if node.decision is PermissionOutcome.DENY)
    approval_nodes = tuple(node.node_id for node in nodes if node.decision is PermissionOutcome.APPROVAL_REQUIRED)
    allowed = tuple(node.node_id for node in nodes if node.decision is PermissionOutcome.ALLOW)
    approvals = _dedupe_requirements((
        *root.effective_permissions.approval_requirements,
        *(requirement for item in requirements for requirement in item.approval_requirements),
        *(requirement for node in nodes for requirement in node.approval_requirements),
    ))
    required_blocked = any(node.required and node.decision is PermissionOutcome.DENY for node in nodes)
    requirement_denied = any(item.decision is PermissionOutcome.DENY for item in requirements)
    requirement_approval = any(item.decision is PermissionOutcome.APPROVAL_REQUIRED for item in requirements)
    decision = PermissionOutcome.DENY if required_blocked or requirement_denied else PermissionOutcome.APPROVAL_REQUIRED if approvals or requirement_approval or root.effective_permissions.decision is PermissionOutcome.APPROVAL_REQUIRED or approval_nodes else PermissionOutcome.ALLOW
    return DomainWorkflowPermissionDecision(workflow.workflow_id, workflow.version, decision, blocked, approvals, tuple({"node_id": node.node_id, "decision": node.decision.value, "reasons": node.reasons, "provenance": node.provenance} for node in nodes), allowed, approval_nodes, nodes, tuple(requirements), root.effective_permissions.effective_constraints)


def evaluate_domain_workflow_node(
    node: WorkflowNode,
    workflow: DomainWorkflowDefinition,
    resolver: DomainPermissionResolver,
    *,
    request_id: str,
    actor_id: str,
    session_id: str,
    operations: Mapping[tuple[str, str | None], DomainOperationDefinition] | None = None,
    workflows: Mapping[tuple[str, str | None], DomainWorkflowDefinition] | None = None,
    now: datetime | None = None,
) -> DomainWorkflowNodePermissionDecision:
    """Reevaluate one reached node without evaluating or consuming other nodes."""
    return _node_decision(
        node,
        workflow,
        resolver,
        request_id=request_id,
        actor_id=actor_id,
        session_id=session_id,
        operations=operations or {},
        workflows=workflows or {},
        now=now,
    )


def evaluate_domain_rule(rule: DomainReasoningRuleDefinition, resolver: DomainPermissionResolver, *, request_id: str, actor_id: str, session_id: str, required: bool = True) -> DomainRulePermissionDecision:
    """Evaluate declared rule permissions without selecting or executing the rule."""
    domain_id = rule.domain_id
    assert domain_id is not None
    decisions = []
    for permission in rule.required_permissions:
        try:
            action = PermissionCapability(permission)
        except ValueError:
            decisions.append(PermissionOutcome.DENY)
            continue
        decisions.append(resolver.resolve(DomainPermissionRequest(request_id, action, domain_id, actor_id, session_id)).effective_permissions.decision)
    blocked = PermissionOutcome.DENY in decisions
    decision = PermissionOutcome.DENY if blocked else PermissionOutcome.APPROVAL_REQUIRED if PermissionOutcome.APPROVAL_REQUIRED in decisions else PermissionOutcome.ALLOW
    return DomainRulePermissionDecision(rule.id, decision, required, blocked, blocked and not required, tuple(rule.required_permissions))


__all__ = [
    "DomainOperationPermissionDecision", "DomainOperationRequirementDecision", "DomainRulePermissionDecision",
    "DomainWorkflowNodePermissionDecision", "DomainWorkflowPermissionDecision", "evaluate_domain_operation",
    "evaluate_domain_rule", "evaluate_domain_workflow", "evaluate_domain_workflow_node", "request_for_operation", "request_for_rule_permission",
    "request_for_workflow",
]
