from __future__ import annotations

from dataclasses import dataclass

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
from cmm.agent_runtime.operation_execution_adapter import AgentExecutionAdapter
from cmm.agent_runtime.operation_registry import InMemoryAgentOperationRegistry
from cmm.agent_runtime.permission_restriction_contracts import (
    PostVerificationKind,
    PostVerificationRequirement,
)
from cmm.domains import (
    DefaultDomainOperationOrchestrator,
    DomainOperationDefinition,
    DomainOperationExecutionDelegate,
    DomainOperationRequest,
    DomainOperationStatus,
    DomainOperationType,
    InMemoryDomainOperationRegistry,
)
from cmm.domains.approval_bridge import to_approval_requirement
from cmm.domains.permission_gate import DomainPermissionGate


@dataclass(frozen=True)
class _Resolution:
    effective_permissions: EffectivePermissionResult


class _Resolver:
    def __init__(self, outcomes: dict[PermissionCapability, PermissionOutcome], approval_requirement: PermissionApprovalRequirement | None = None, effective_constraints: dict[str, object] | None = None) -> None:
        self.outcomes = outcomes
        self.approval_requirement = approval_requirement
        self.effective_constraints = effective_constraints or {}
        self.calls: list[PermissionCapability] = []

    def resolve(self, request, **kwargs):
        self.calls.append(request.action)
        outcome = self.outcomes.get(request.action, PermissionOutcome.ALLOW)
        requirements = (
            (self.approval_requirement,)
            if outcome is PermissionOutcome.APPROVAL_REQUIRED
            and self.approval_requirement is not None
            else ()
        )
        layer = PermissionLayerEvaluation(
            PermissionLayer.DOMAIN,
            outcome,
            source_id="policy:current",
            reasons=("current_policy",),
            approval_requirements=requirements,
            constraints=self.effective_constraints,
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
                approval_requirements=requirements,
                effective_constraints=self.effective_constraints,
            )
        )


class _Implementation:
    def __init__(self, definition: DomainOperationDefinition) -> None:
        self.definition = definition
        self.calls = 0

    def execute(self, request):
        self.calls += 1
        return {"success": True, "output": {"ok": True}}


class _TransactionManager:
    class _Boundary:
        id = "transaction:1"

    def start_transaction(self, **kwargs):
        return self._Boundary(), None

    def register_operation(self, *args, **kwargs):
        return None

    def commit(self, *args, **kwargs):
        return None


def _definition(**changes) -> DomainOperationDefinition:
    values = {
        "operation_id": "general.secured",
        "domain_id": "domain:general",
        "version": "1.0.0",
        "name": "Secured",
        "description": "Secured operation",
        "operation_type": DomainOperationType.PREPARATION,
        "reversible": True,
        "required_permissions": (PermissionCapability.MEMORY_READ.value,),
        "input_schema": {"type": "object"},
        "output_schema": {"type": "object"},
    }
    values.update(changes)
    return DomainOperationDefinition(**values)


def _request(**changes) -> DomainOperationRequest:
    values = {
        "request_id": "request:gate",
        "operation_id": "general.secured",
        "operation_version": "1.0.0",
        "inputs": {},
        "agent_run_id": "actor:1",
        "session_id": "session:1",
        "task_id": "task:1",
        "primary_domain_id": "domain:general",
        "idempotency_key": "idem:gate",
        "capabilities": ("execute", "transaction"),
        "granted_permissions": (PermissionCapability.MEMORY_READ.value,),
    }
    values.update(changes)
    return DomainOperationRequest(**values)


def _system(resolver: _Resolver, approval_service: ApprovalService | None = None):
    definition = _definition()
    common = InMemoryAgentOperationRegistry()
    registry = InMemoryDomainOperationRegistry(common)
    implementation = _Implementation(definition)
    registry.register(definition, implementation)
    adapter = AgentExecutionAdapter(
        registry=common,
        execution_delegate=DomainOperationExecutionDelegate(registry),
    )
    orchestrator = DefaultDomainOperationOrchestrator(
        registry,
        adapter,
        permission_gate=DomainPermissionGate(resolver, approval_service),
        approval_service=approval_service,
        transaction_manager=_TransactionManager(),
    )
    return orchestrator, implementation


def test_legacy_granted_permissions_cannot_bypass_current_policy_deny() -> None:
    resolver = _Resolver({PermissionCapability.MEMORY_READ: PermissionOutcome.DENY})
    orchestrator, implementation = _system(resolver)

    result = orchestrator.execute(_request())

    assert result.status is DomainOperationStatus.BLOCKED
    assert implementation.calls == 0
    assert PermissionCapability.MEMORY_READ in resolver.calls


def test_legacy_granted_permissions_fail_closed_when_gate_is_unavailable() -> None:
    definition = _definition()
    common = InMemoryAgentOperationRegistry()
    registry = InMemoryDomainOperationRegistry(common)
    implementation = _Implementation(definition)
    registry.register(definition, implementation)
    adapter = AgentExecutionAdapter(
        registry=common,
        execution_delegate=DomainOperationExecutionDelegate(registry),
    )
    orchestrator = DefaultDomainOperationOrchestrator(
        registry,
        adapter,
        transaction_manager=_TransactionManager(),
    )

    result = orchestrator.execute(_request())

    assert result.status is DomainOperationStatus.BLOCKED
    assert result.trace_entries[0].reason_code == "permission.gate_unavailable"
    assert implementation.calls == 0


def test_allowed_operation_without_approval_still_dispatches() -> None:
    resolver = _Resolver({})
    orchestrator, implementation = _system(resolver)

    result = orchestrator.execute(_request())

    assert result.status is DomainOperationStatus.COMPLETED
    assert implementation.calls == 1


def test_dispatched_mutation_awaiting_post_verification_is_not_completed() -> None:
    requirement = PostVerificationRequirement(
        kinds=(PostVerificationKind.REFETCH, PostVerificationKind.COMPARISON),
        resource_ids=("resource:result",),
    )
    resolver = _Resolver(
        {},
        effective_constraints={"post_verification": requirement.to_dict()},
    )
    orchestrator, implementation = _system(resolver)

    result = orchestrator.execute(_request())

    assert result.status is DomainOperationStatus.RUNNING
    assert result.to_dict()["metadata"]["post_verification"] == requirement.to_dict()
    assert implementation.calls == 1


def _approval_requirement() -> PermissionApprovalRequirement:
    return PermissionApprovalRequirement(
        requirement_id="policy:operation:request:gate",
        action=PermissionCapability.OPERATION_EXECUTE,
        actor_id="actor:1",
        session_id="session:1",
        domain_id="domain:general",
        operation_id="general.secured",
        operation_version="1.0.0",
        fingerprint="request:gate:general.secured:actor:1:session:1",
        scope="operation",
    )


def test_valid_operation_approval_is_consumed_once() -> None:
    requirement = _approval_requirement()
    service = ApprovalService(InMemoryApprovalRepository())
    approval = service.create_request_from_requirement(to_approval_requirement(requirement))
    service.approve(approval.id, "reviewer")
    resolver = _Resolver(
        {PermissionCapability.OPERATION_EXECUTE: PermissionOutcome.APPROVAL_REQUIRED},
        requirement,
    )
    orchestrator, implementation = _system(resolver, service)

    first = orchestrator.execute(_request(approval_request_id=approval.id))
    second = orchestrator.execute(_request(approval_request_id=approval.id))

    assert first.status is DomainOperationStatus.COMPLETED
    assert second.status is DomainOperationStatus.BLOCKED
    assert implementation.calls == 1
    assert service.repository.is_consumed(approval.id) is True


def test_current_deny_blocks_without_consuming_prior_approval() -> None:
    requirement = _approval_requirement()
    service = ApprovalService(InMemoryApprovalRepository())
    approval = service.create_request_from_requirement(to_approval_requirement(requirement))
    service.approve(approval.id, "reviewer")
    resolver = _Resolver({PermissionCapability.OPERATION_EXECUTE: PermissionOutcome.DENY})
    orchestrator, implementation = _system(resolver, service)

    result = orchestrator.execute(_request(approval_request_id=approval.id))

    assert result.status is DomainOperationStatus.BLOCKED
    assert implementation.calls == 0
    assert service.repository.is_consumed(approval.id) is False


def test_operation_preview_validates_but_does_not_consume() -> None:
    requirement = _approval_requirement()
    service = ApprovalService(InMemoryApprovalRepository())
    approval = service.create_request_from_requirement(to_approval_requirement(requirement))
    service.approve(approval.id, "reviewer")
    gate = DomainPermissionGate(
        _Resolver(
            {PermissionCapability.OPERATION_EXECUTE: PermissionOutcome.APPROVAL_REQUIRED},
            requirement,
        ),
        service,
    )

    result = gate.evaluate_operation_definition(
        _definition(),
        request_id="request:gate",
        actor_id="actor:1",
        session_id="session:1",
        approval_request_id=approval.id,
        dry_run=True,
    )

    assert result.allowed
    assert service.repository.is_consumed(approval.id) is False
