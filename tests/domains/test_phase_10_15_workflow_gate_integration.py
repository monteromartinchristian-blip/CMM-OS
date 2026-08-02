from __future__ import annotations

from dataclasses import dataclass

import pytest

from cmm.agent_runtime.approval_repository import InMemoryApprovalRepository
from cmm.agent_runtime.approval_service import ApprovalService
from cmm.agent_runtime.domain_permission_contracts import (
    EffectivePermissionResult,
    PermissionApprovalRequirement,
    PermissionCapability,
    PermissionLayer,
    PermissionLayerEvaluation,
    PermissionOutcome,
)
from cmm.domains.approval_bridge import to_approval_requirement
from cmm.domains.permission_gate import DomainPermissionGate
from cmm.domains.workflow_contracts import (
    DomainWorkflowContext,
    DomainWorkflowDefinition,
)
from cmm.domains.workflow_errors import DomainWorkflowUnavailableError
from cmm.domains.workflow_execution import DomainWorkflowExecutor
from cmm.workflows.contracts import ApprovalDecision as WorkflowApprovalDecision
from cmm.workflows.contracts import WorkflowNode
from cmm.workflows.engine import NodeExecution
from cmm.workflows.enums import WorkflowRunStatus


@dataclass(frozen=True)
class _Resolution:
    effective_permissions: EffectivePermissionResult


class _Resolver:
    def __init__(
        self,
        outcomes: dict[PermissionCapability, PermissionOutcome] | None = None,
        requirements: dict[PermissionCapability, PermissionApprovalRequirement] | None = None,
        *,
        cross_domain_outcome: PermissionOutcome = PermissionOutcome.ALLOW,
    ) -> None:
        self.outcomes = outcomes or {}
        self.requirements = requirements or {}
        self.cross_domain_outcome = cross_domain_outcome

    def resolve(self, request, **kwargs):
        outcome = self.outcomes.get(request.action, PermissionOutcome.ALLOW)
        approval_requirements = (
            (self.requirements[request.action],)
            if request.action in self.requirements
            and outcome is PermissionOutcome.APPROVAL_REQUIRED
            else ()
        )
        layer = PermissionLayerEvaluation(
            PermissionLayer.DOMAIN,
            outcome,
            source_id="policy:current",
            reasons=("current_policy",),
            approval_requirements=approval_requirements,
        )
        return _Resolution(
            EffectivePermissionResult(
                request_id=request.request_id,
                action=request.action,
                decision=outcome,
                layer_evaluations=(layer,),
                denied_by=(layer.source_id,) if outcome is PermissionOutcome.DENY else (),
                allowed_by=(layer.source_id,) if outcome is PermissionOutcome.ALLOW else (),
                unresolved_by=(),
                reasons=layer.reasons,
                approval_requirements=approval_requirements,
            )
        )

    def resolve_cross_domain(self, request, **kwargs):
        return type(
            "CrossDecision",
            (),
            {
                "decision": self.cross_domain_outcome,
                "reasons": ("target_policy_denied",)
                if self.cross_domain_outcome is PermissionOutcome.DENY
                else ("cross_domain_allowed",),
            },
        )()


class _Ids:
    def __init__(self) -> None:
        self.value = 0

    def __call__(self) -> str:
        self.value += 1
        return f"generated-{self.value}"


def _workflow(*, nodes: tuple[WorkflowNode, ...] | None = None, **changes) -> DomainWorkflowDefinition:
    values = {
        "workflow_id": "x.flow",
        "domain_id": "domain:x",
        "version": "1.0.0",
        "name": "X",
        "nodes": nodes or (WorkflowNode("complete", "complete", "Complete"),),
    }
    values.update(changes)
    return DomainWorkflowDefinition(**values)


def _context(**metadata) -> DomainWorkflowContext:
    return DomainWorkflowContext(
        "domain:x",
        available_permissions=frozenset({PermissionCapability.MEMORY_READ.value}),
        metadata={"actor_id": "actor:1", "session_id": "session:1", **metadata},
    )


def test_global_required_permission_deny_blocks_before_workflow_start() -> None:
    resolver = _Resolver({PermissionCapability.MEMORY_READ: PermissionOutcome.DENY})
    adapter_calls: list[str] = []
    executor = DomainWorkflowExecutor(
        id_factory=_Ids(),
        permission_gate=DomainPermissionGate(resolver),
        operation_adapter=lambda node, run: adapter_calls.append(node.node_id)
        or NodeExecution.complete({}),
    )

    with pytest.raises(DomainWorkflowUnavailableError) as error:
        executor.execute(
            _workflow(required_permissions=(PermissionCapability.MEMORY_READ.value,)),
            _context(),
            {},
        )

    assert error.value.details["reason_code"] == "permission.policy_denied"
    assert adapter_calls == []


def test_legacy_available_permissions_fail_closed_without_gate() -> None:
    executor = DomainWorkflowExecutor(id_factory=_Ids())

    with pytest.raises(DomainWorkflowUnavailableError) as error:
        executor.execute(
            _workflow(required_permissions=(PermissionCapability.MEMORY_READ.value,)),
            _context(),
            {},
        )

    assert error.value.details["reason_code"] == "permission.gate_unavailable"


def test_node_scoped_approval_is_consumed_only_when_node_is_reached() -> None:
    ids = _Ids()
    service = ApprovalService(InMemoryApprovalRepository())
    requirement = PermissionApprovalRequirement(
        requirement_id="workflow:x.flow:1.0.0:approval:generated-1",
        action=PermissionCapability.WORKFLOW_EXECUTE,
        actor_id="actor:1",
        session_id="session:1",
        domain_id="domain:x",
        workflow_id="x.flow",
        workflow_version="1.0.0",
        node_id="approval",
        fingerprint="generated-1:x.flow:1.0.0:approval:actor:1:session:1",
        scope="node",
        reason_code="workflow_approval_gate",
    )
    approval = service.create_request_from_requirement(to_approval_requirement(requirement))
    service.approve(approval.id, "reviewer")
    definition = _workflow(
        nodes=(
            WorkflowNode("prepare", "validate", "Prepare"),
            WorkflowNode(
                "approval",
                "request_approval",
                "Approve",
                dependencies=("prepare",),
                approval_gate="security",
            ),
        )
    )
    executor = DomainWorkflowExecutor(
        id_factory=ids,
        permission_gate=DomainPermissionGate(_Resolver(), service),
        operation_adapter=lambda node, run: NodeExecution.complete({}),
    )

    run = executor.execute(
        definition,
        _context(approval_request_ids={requirement.requirement_id: approval.id}),
        {},
    )

    assert run.status is WorkflowRunStatus.COMPLETED
    assert service.repository.is_consumed(approval.id) is True


def test_unreached_node_does_not_consume_its_approval() -> None:
    ids = _Ids()
    service = ApprovalService(InMemoryApprovalRepository())
    requirement = PermissionApprovalRequirement(
        requirement_id="workflow:x.flow:1.0.0:approval:generated-1",
        action=PermissionCapability.WORKFLOW_EXECUTE,
        actor_id="actor:1",
        session_id="session:1",
        domain_id="domain:x",
        workflow_id="x.flow",
        workflow_version="1.0.0",
        node_id="approval",
        fingerprint="generated-1:x.flow:1.0.0:approval:actor:1:session:1",
        scope="node",
        reason_code="workflow_approval_gate",
    )
    approval = service.create_request_from_requirement(to_approval_requirement(requirement))
    service.approve(approval.id, "reviewer")
    definition = _workflow(
        nodes=(
            WorkflowNode("fail", "validate", "Fail"),
            WorkflowNode(
                "approval",
                "request_approval",
                "Approve",
                dependencies=("fail",),
                approval_gate="security",
            ),
        )
    )
    executor = DomainWorkflowExecutor(
        id_factory=ids,
        permission_gate=DomainPermissionGate(_Resolver(), service),
        operation_adapter=lambda node, run: NodeExecution.failure("expected")
        if node.node_id == "fail"
        else NodeExecution.complete({}),
    )

    run = executor.execute(
        definition,
        _context(approval_request_ids={requirement.requirement_id: approval.id}),
        {},
    )

    assert run.status is WorkflowRunStatus.FAILED
    assert service.repository.is_consumed(approval.id) is False


def test_pending_node_approval_resumes_and_consumes_immediately_before_node() -> None:
    ids = _Ids()
    service = ApprovalService(InMemoryApprovalRepository())
    requirement = PermissionApprovalRequirement(
        requirement_id="workflow:x.flow:1.0.0:approval:generated-1",
        action=PermissionCapability.WORKFLOW_EXECUTE,
        actor_id="actor:1",
        session_id="session:1",
        domain_id="domain:x",
        workflow_id="x.flow",
        workflow_version="1.0.0",
        node_id="approval",
        fingerprint="generated-1:x.flow:1.0.0:approval:actor:1:session:1",
        scope="node",
        reason_code="workflow_approval_gate",
    )
    security_approval = service.create_request_from_requirement(
        to_approval_requirement(requirement)
    )
    definition = _workflow(
        nodes=(
            WorkflowNode(
                "approval",
                "request_approval",
                "Approve",
                approval_gate="security",
            ),
        )
    )
    executor = DomainWorkflowExecutor(
        id_factory=ids,
        permission_gate=DomainPermissionGate(_Resolver(), service),
        operation_adapter=lambda node, run: NodeExecution.complete({}),
    )

    waiting = executor.execute(
        definition,
        _context(
            approval_request_ids={
                requirement.requirement_id: security_approval.id
            }
        ),
        {},
    )

    assert waiting.status is WorkflowRunStatus.WAITING_FOR_APPROVAL
    legacy = waiting.common_run.wait_request.approval_request
    assert legacy is not None
    service.approve(security_approval.id, "reviewer")
    decided = legacy.decide(WorkflowApprovalDecision("reviewer", True))

    resumed = executor.resume(
        waiting,
        condition_resolved=True,
        approval=decided,
    )

    assert resumed.status is WorkflowRunStatus.COMPLETED
    assert service.repository.is_consumed(security_approval.id) is True


def _workflow_start_requirement() -> PermissionApprovalRequirement:
    return PermissionApprovalRequirement(
        requirement_id="policy:workflow:generated-1",
        action=PermissionCapability.WORKFLOW_EXECUTE,
        actor_id="actor:1",
        session_id="session:1",
        domain_id="domain:x",
        workflow_id="x.flow",
        workflow_version="1.0.0",
        fingerprint="generated-1:x.flow:actor:1:session:1",
        scope="workflow",
    )


def test_workflow_scoped_approval_is_consumed_at_start_once() -> None:
    requirement = _workflow_start_requirement()
    service = ApprovalService(InMemoryApprovalRepository())
    approval = service.create_request_from_requirement(to_approval_requirement(requirement))
    service.approve(approval.id, "reviewer")
    resolver = _Resolver(
        {PermissionCapability.WORKFLOW_EXECUTE: PermissionOutcome.APPROVAL_REQUIRED},
        {PermissionCapability.WORKFLOW_EXECUTE: requirement},
    )
    executor = DomainWorkflowExecutor(
        id_factory=_Ids(),
        permission_gate=DomainPermissionGate(resolver, service),
        operation_adapter=lambda node, run: NodeExecution.complete({}),
    )

    run = executor.execute(
        _workflow(),
        _context(approval_request_id=approval.id),
        {},
    )

    assert run.status is WorkflowRunStatus.COMPLETED
    assert service.repository.is_consumed(approval.id) is True


def test_pending_workflow_start_approval_resumes_and_consumes_before_nodes() -> None:
    requirement = _workflow_start_requirement()
    service = ApprovalService(InMemoryApprovalRepository())
    security_approval = service.create_request_from_requirement(
        to_approval_requirement(requirement)
    )
    executor = DomainWorkflowExecutor(
        id_factory=_Ids(),
        permission_gate=DomainPermissionGate(
            _Resolver(
                {
                    PermissionCapability.WORKFLOW_EXECUTE: PermissionOutcome.APPROVAL_REQUIRED
                },
                {PermissionCapability.WORKFLOW_EXECUTE: requirement},
            ),
            service,
        ),
        operation_adapter=lambda node, run: NodeExecution.complete({}),
    )

    waiting = executor.execute(
        _workflow(),
        _context(approval_request_id=security_approval.id),
        {},
    )

    assert waiting.status is WorkflowRunStatus.WAITING_FOR_APPROVAL
    legacy = waiting.common_run.wait_request.approval_request
    assert legacy is not None
    service.approve(security_approval.id, "reviewer")
    decided = legacy.decide(WorkflowApprovalDecision("reviewer", True))

    resumed = executor.resume(
        waiting,
        condition_resolved=True,
        approval=decided,
    )

    assert resumed.status is WorkflowRunStatus.COMPLETED
    assert service.repository.is_consumed(security_approval.id) is True


def test_workflow_scope_does_not_authorize_extra_required_capability() -> None:
    workflow_requirement = _workflow_start_requirement()
    capability_requirement = PermissionApprovalRequirement(
        requirement_id="policy:memory:generated-1",
        action=PermissionCapability.MEMORY_READ,
        actor_id="actor:1",
        session_id="session:1",
        domain_id="domain:x",
        workflow_id="x.flow",
        workflow_version="1.0.0",
        fingerprint="generated-1:memory.read:actor:1:session:1",
        scope="request",
    )
    service = ApprovalService(InMemoryApprovalRepository())
    approval = service.create_request_from_requirement(
        to_approval_requirement(workflow_requirement)
    )
    service.approve(approval.id, "reviewer")
    resolver = _Resolver(
        {
            PermissionCapability.WORKFLOW_EXECUTE: PermissionOutcome.APPROVAL_REQUIRED,
            PermissionCapability.MEMORY_READ: PermissionOutcome.APPROVAL_REQUIRED,
        },
        {
            PermissionCapability.WORKFLOW_EXECUTE: workflow_requirement,
            PermissionCapability.MEMORY_READ: capability_requirement,
        },
    )
    executor = DomainWorkflowExecutor(
        id_factory=_Ids(),
        permission_gate=DomainPermissionGate(resolver, service),
        operation_adapter=lambda node, run: NodeExecution.complete({}),
    )

    run = executor.execute(
        _workflow(required_permissions=(PermissionCapability.MEMORY_READ.value,)),
        _context(approval_request_id=approval.id),
        {},
    )

    assert run.status is WorkflowRunStatus.WAITING_FOR_APPROVAL
    assert run.common_run.wait_request is not None
    assert run.common_run.wait_request.details["reason_code"] == "approval.missing"
    assert service.repository.is_consumed(approval.id) is False


def test_target_domain_current_deny_blocks_before_start_approval_consumption() -> None:
    requirement = _workflow_start_requirement()
    service = ApprovalService(InMemoryApprovalRepository())
    approval = service.create_request_from_requirement(to_approval_requirement(requirement))
    service.approve(approval.id, "reviewer")
    child = DomainWorkflowDefinition(
        workflow_id="y.child",
        domain_id="domain:y",
        version="1.0.0",
        name="Child",
        nodes=(WorkflowNode("done", "complete", "Done"),),
    )
    parent = _workflow(
        nodes=(
            WorkflowNode(
                "child",
                "invoke_subworkflow",
                "Child",
                subworkflow_id="y.child",
                subworkflow_version="1.0.0",
            ),
        ),
        supporting_domain_ids=("domain:y",),
    )
    resolver = _Resolver(
        {PermissionCapability.WORKFLOW_EXECUTE: PermissionOutcome.APPROVAL_REQUIRED},
        {PermissionCapability.WORKFLOW_EXECUTE: requirement},
        cross_domain_outcome=PermissionOutcome.DENY,
    )
    executor = DomainWorkflowExecutor(
        id_factory=_Ids(),
        permission_gate=DomainPermissionGate(resolver, service),
        workflow_definitions={(child.workflow_id, child.version): child},
        operation_adapter=lambda node, run: NodeExecution.complete({}),
    )
    context = DomainWorkflowContext(
        "domain:x",
        supporting_domain_ids=("domain:y",),
        known_domain_ids=frozenset({"domain:x", "domain:y"}),
        authorized_domain_ids=frozenset({"domain:x", "domain:y"}),
        metadata={
            "actor_id": "actor:1",
            "session_id": "session:1",
            "approval_request_id": approval.id,
        },
    )

    with pytest.raises(DomainWorkflowUnavailableError):
        executor.execute(parent, context, {})

    assert service.repository.is_consumed(approval.id) is False
