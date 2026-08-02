"""Coordination-only execution of domain operations through AgentExecutionAdapter."""

from __future__ import annotations

import uuid
from collections.abc import Callable, Mapping
from datetime import datetime, timezone
from typing import Any

from cmm.agent_runtime.enums import (
    AgentOperationExecutionStatus,
    ApprovalRequestStatus,
    OperationRecoveryKind,
)
from cmm.agent_runtime.errors import (
    AgentRuntimeError,
    ControlledOperationExecutionError,
)
from cmm.agent_runtime.operation_execution_contracts import (
    AgentOperationExecutionResult,
    AgentOperationRequest,
)
from cmm.agent_runtime.operation_schema import validate_operation_schema
from cmm.domains.enums import DomainOperationStatus
from cmm.domains.errors import (
    DomainOperationContractError,
    DomainOperationExecutionError,
    DomainOperationRollbackError,
    DomainOperationValidationError,
)
from cmm.domains.operation_availability import (
    DomainOperationAvailabilityContext,
    DomainOperationAvailabilityResolver,
)
from cmm.domains.operation_contracts import (
    DomainOperationRequest,
    DomainOperationResult,
    DomainOperationRollbackResult,
    DomainOperationTraceEntry,
    _thaw,
)
from cmm.domains.operation_registry import InMemoryDomainOperationRegistry
from cmm.domains.permission_gate import (
    DomainPermissionGate,
    PermissionGateOutcome,
    PermissionGateReason,
)


class DomainOperationExecutionDelegate:
    """Common adapter delegate that is solely responsible for invoking implementations."""

    def __init__(self, registry: InMemoryDomainOperationRegistry) -> None:
        self._registry = registry

    def __call__(self, request: AgentOperationRequest) -> Mapping[str, Any]:
        implementation = self._registry.get_implementation(
            request.operation_name, request.operation_version
        )
        try:
            output = implementation.execute(request)
        except DomainOperationExecutionError as exc:
            raise ControlledOperationExecutionError(
                code=exc.code,
                message=exc.message,
                details=exc.details,
            ) from exc
        if not isinstance(output, Mapping):
            raise TypeError("domain operation implementation must return a mapping")
        return output


class DefaultDomainOperationOrchestrator:
    """Resolve and coordinate domain services, delegating execution exactly once."""

    def __init__(
        self,
        registry: Any,
        execution_adapter: Any,
        *,
        availability_resolver: DomainOperationAvailabilityResolver | None = None,
        approval_service: Any | None = None,
        permission_gate: DomainPermissionGate | None = None,
        transaction_manager: Any | None = None,
        rollback_executor: Any | None = None,
        clock: Callable[[], datetime] | None = None,
        id_factory: Callable[[], str] | None = None,
    ) -> None:
        if getattr(execution_adapter, "registry", None) is not registry.common_registry:
            raise DomainOperationContractError(
                "execution adapter and domain registry must share the common registry"
            )
        self._registry = registry
        self._execution_adapter = execution_adapter
        self._availability_resolver = (
            availability_resolver or DomainOperationAvailabilityResolver()
        )
        self._approval_service = approval_service
        self._permission_gate = permission_gate
        self._transaction_manager = transaction_manager
        self._rollback_executor = rollback_executor
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._id_factory = id_factory or (lambda: f"domain-result:{uuid.uuid4().hex}")

    def execute(self, request: DomainOperationRequest) -> DomainOperationResult:
        definition = self._registry.get(request.operation_id, request.operation_version)
        if (
            definition.operation_id != request.operation_id
            or definition.version != request.operation_version
        ):
            raise DomainOperationContractError(
                "registry returned mismatched operation identity"
            )
        input_issues = validate_operation_schema(
            request.inputs, definition.input_schema
        )
        if input_issues:
            first = input_issues[0]
            raise DomainOperationValidationError(
                "Domain operation input is invalid",
                details={"path": first.path, "reason_code": first.code},
            )

        if self._permission_gate is None and (
            request.granted_permissions or request.approval_request_id is not None
        ):
            now = self._clock()
            return DomainOperationResult(
                result_id=self._id_factory(),
                request_id=request.request_id,
                operation_id=request.operation_id,
                operation_version=request.operation_version,
                domain_id=definition.domain_id,
                status=DomainOperationStatus.BLOCKED,
                started_at=now,
                completed_at=now,
                trace_entries=(
                    DomainOperationTraceEntry(
                        code="permission:gate_unavailable",
                        status=DomainOperationStatus.BLOCKED,
                        occurred_at=now,
                        reason_code=PermissionGateReason.GATE_UNAVAILABLE.value,
                    ),
                ),
            )

        approval_status: ApprovalRequestStatus | None = None
        approval_fingerprint: str | None = None
        if request.approval_request_id and self._approval_service is not None:
            get_request = getattr(self._approval_service, "get_request", None)
            if get_request is None:
                get_request = self._approval_service.repository.get_request
            approval = get_request(request.approval_request_id)
            approval_status = ApprovalRequestStatus(
                getattr(approval.status, "value", approval.status)
            )
            approval_fingerprint = getattr(approval, "metadata", {}).get(
                "domain_request_fingerprint",
                getattr(approval, "request_fingerprint", None),
            )

        capabilities = list(request.capabilities)
        if self._transaction_manager is None and "transaction" in capabilities:
            capabilities.remove("transaction")
        if self._rollback_executor is None and "rollback" in capabilities:
            capabilities.remove("rollback")
        validation_ids = (
            (definition.validation_policy_id,)
            if definition.validation_policy_id and "validation" in capabilities
            else ()
        )
        rollback_ids = (
            (definition.rollback_policy_id,)
            if definition.rollback_policy_id and "rollback" in capabilities
            else ()
        )
        availability = self._availability_resolver.resolve(
            definition,
            DomainOperationAvailabilityContext(
                primary_domain_id=request.primary_domain_id,
                supporting_domain_ids=request.supporting_domain_ids,
                granted_permissions=request.granted_permissions,
                denied_permissions=request.denied_permissions,
                available_resources=request.available_resources,
                capabilities=tuple(capabilities),
                available_validation_policy_ids=validation_ids,
                available_rollback_policy_ids=rollback_ids,
                approval_status=approval_status,
                approval_fingerprint=approval_fingerprint,
                request_fingerprint=request.calculate_fingerprint(),
                metadata=request.metadata,
            ),
            now=self._clock(),
        )
        if availability.status is not DomainOperationStatus.AVAILABLE:
            return self._non_executed_result(
                request, definition.domain_id, availability
            )

        # ── Phase 10.15 Permission Gate ──────────────────────────────────
        gate_result = None
        if self._permission_gate is not None:
            approval_request_ids = request.metadata.get("approval_request_ids", {})
            if not isinstance(approval_request_ids, Mapping):
                approval_request_ids = {}
            gate_result = self._permission_gate.evaluate_operation_definition(
                definition,
                request_id=request.request_id,
                actor_id=request.metadata.get("actor_id", request.agent_run_id),
                session_id=request.session_id or request.agent_run_id,
                approval_request_id=request.approval_request_id,
                approval_request_ids=approval_request_ids,
            )
            if gate_result.denied:
                reason_code = (
                    gate_result.reasons[-1]
                    if gate_result.outcome == PermissionGateOutcome.APPROVAL_DENIED
                    else PermissionGateReason.POLICY_DENIED.value
                )
                now = self._clock()
                return DomainOperationResult(
                    result_id=self._id_factory(),
                    request_id=request.request_id,
                    operation_id=request.operation_id,
                    operation_version=request.operation_version,
                    domain_id=definition.domain_id,
                    status=DomainOperationStatus.BLOCKED,
                    started_at=now,
                    completed_at=now,
                    trace_entries=(
                        DomainOperationTraceEntry(
                            code="permission:denied",
                            status=DomainOperationStatus.BLOCKED,
                            occurred_at=now,
                            reason_code=reason_code,
                        ),
                    ),
                    metadata={"permission_gate": gate_result.to_trace_dict()},
                )
            if gate_result.requires_approval:
                now = self._clock()
                return DomainOperationResult(
                    result_id=self._id_factory(),
                    request_id=request.request_id,
                    operation_id=request.operation_id,
                    operation_version=request.operation_version,
                    domain_id=definition.domain_id,
                    status=DomainOperationStatus.WAITING_FOR_APPROVAL,
                    started_at=now,
                    completed_at=now,
                    trace_entries=(
                        DomainOperationTraceEntry(
                            code="permission:approval_required",
                            status=DomainOperationStatus.WAITING_FOR_APPROVAL,
                            occurred_at=now,
                            reason_code=PermissionGateReason.APPROVAL_MISSING.value,
                        ),
                    ),
                    metadata={"permission_gate": gate_result.to_trace_dict()},
                )
        # ── End Permission Gate ──────────────────────────────────────────

        started_at = self._clock()
        transaction_id: str | None = None
        checkpoint_id: str | None = None
        if definition.reversible and self._transaction_manager is not None:
            boundary, checkpoint_id = self._transaction_manager.start_transaction(
                agent_run_id=request.agent_run_id,
                goal_id=str(request.metadata.get("goal_id", "domain-operation")),
                workflow_id=request.workflow_id,
                iteration_id=request.task_id,
                kind="compensable",
                name=f"domain-operation:{definition.operation_id}",
                resource_keys=definition.required_resources,
                has_approval=approval_status is ApprovalRequestStatus.APPROVED,
                requires_checkpoint=False,
            )
            transaction_id = boundary.id

        common_request = AgentOperationRequest(
            id=request.request_id,
            agent_run_id=request.agent_run_id,
            workflow_id=request.workflow_id,
            task_id=request.task_id,
            operation_name=request.operation_id,
            operation_version=request.operation_version,
            parameters=_thaw(request.inputs),
            permissions=request.granted_permissions,
            idempotency_key=request.idempotency_key,
            approval_request_id=request.approval_request_id,
            checkpoint_id=checkpoint_id,
            created_at=request.created_at.isoformat(),
            metadata={
                **_thaw(request.metadata),
                "transaction_boundary_id": transaction_id,
                "domain_id": definition.domain_id,
                "session_id": request.session_id,
                "requires_validation": definition.validation_policy_id is not None,
                "validation_policy_id": definition.validation_policy_id,
            },
        )
        common_result = self._execution_adapter.execute(common_request)
        if not isinstance(common_result, AgentOperationExecutionResult):
            raise TypeError(
                "execution adapter must return AgentOperationExecutionResult"
            )
        if (
            common_result.request_id != request.request_id
            or common_result.operation_name != request.operation_id
            or common_result.operation_version != request.operation_version
        ):
            raise DomainOperationContractError(
                "common execution result identity mismatch"
            )

        status_value = str(common_result.status)
        if status_value == AgentOperationExecutionStatus.CANCELLED.value:
            cancellation_error = common_result.error or {
                "code": "OPERATION_CANCELLED",
                "message": "Operation was cancelled",
                "details": {},
            }
            return self._cancel_with_rollback(
                request,
                definition.domain_id,
                started_at,
                transaction_id,
                checkpoint_id,
                definition.rollback_policy_id,
                cancellation_error,
            )

        if not common_result.success:
            original_error = common_result.error or {
                "code": "OPERATION_EXECUTION_FAILED",
                "message": "Operation execution failed",
                "details": {},
            }
            return self._failure_with_rollback(
                request,
                definition.domain_id,
                started_at,
                transaction_id,
                checkpoint_id,
                definition.rollback_policy_id,
                original_error,
            )

        if "memory_write" in (*common_result.effects, *common_result.side_effects):
            direct_write_error = DomainOperationValidationError(
                "Domain operations may propose memory changes but cannot write memory directly",
                details={"reason_code": "memory.direct_write_forbidden"},
            ).to_dict()
            return self._failure_with_rollback(
                request,
                definition.domain_id,
                started_at,
                transaction_id,
                checkpoint_id,
                definition.rollback_policy_id,
                direct_write_error,
            )

        output_issues = validate_operation_schema(
            common_result.output, definition.output_schema
        )
        if output_issues:
            first = output_issues[0]
            validation_error = DomainOperationValidationError(
                "Domain operation output is invalid",
                details={"path": first.path, "reason_code": first.code},
            ).to_dict()
            return self._failure_with_rollback(
                request,
                definition.domain_id,
                started_at,
                transaction_id,
                checkpoint_id,
                definition.rollback_policy_id,
                validation_error,
            )

        if transaction_id is not None:
            self._transaction_manager.register_operation(
                transaction_boundary_id=transaction_id,
                operation_name=definition.operation_id,
                recovery_kind=OperationRecoveryKind.REVERSIBLE,
                effects=common_result.effects,
            )
            self._transaction_manager.commit(transaction_id)
        post_verification = (
            gate_result.effective_constraints.get("post_verification")
            if gate_result is not None
            else None
        )
        return self._result(
            request,
            definition.domain_id,
            DomainOperationStatus.RUNNING
            if post_verification is not None
            else DomainOperationStatus.COMPLETED,
            started_at,
            output=common_result.output,
            transaction_id=transaction_id,
            approval_request_id=request.approval_request_id,
            metadata={"post_verification": post_verification}
            if post_verification is not None
            else None,
        )

    def _non_executed_result(
        self, request: DomainOperationRequest, domain_id: str, availability: Any
    ) -> DomainOperationResult:
        now = self._clock()
        return DomainOperationResult(
            result_id=self._id_factory(),
            request_id=request.request_id,
            operation_id=request.operation_id,
            operation_version=request.operation_version,
            domain_id=domain_id,
            status=availability.status,
            started_at=now,
            completed_at=now,
            approval_request_id=request.approval_request_id,
            trace_entries=availability.trace_entries,
            metadata={"availability": availability.to_dict()},
        )

    def _failure_with_rollback(
        self,
        request: DomainOperationRequest,
        domain_id: str,
        started_at: datetime,
        transaction_id: str | None,
        checkpoint_id: str | None,
        rollback_policy_id: str | None,
        original_error: Mapping[str, Any],
    ) -> DomainOperationResult:
        if transaction_id is None or self._rollback_executor is None:
            return self._result(
                request,
                domain_id,
                DomainOperationStatus.FAILED,
                started_at,
                transaction_id=transaction_id,
                error=original_error,
            )
        self._transaction_manager.mark_rollback_started(transaction_id)
        succeeded = self._rollback_executor.rollback(transaction_id, checkpoint_id)
        rollback_error: Mapping[str, Any] | None = None
        status = DomainOperationStatus.FAILED
        if succeeded:
            self._transaction_manager.mark_rolled_back(transaction_id)
            status = DomainOperationStatus.ROLLED_BACK
        else:
            rollback_error = DomainOperationRollbackError(
                "Operation rollback failed",
                details={"transaction_id": transaction_id},
            ).to_dict()
        rollback_result = DomainOperationRollbackResult(
            attempted=True,
            succeeded=bool(succeeded),
            policy_id=rollback_policy_id,
            error=rollback_error,
        )
        return self._result(
            request,
            domain_id,
            status,
            started_at,
            transaction_id=transaction_id,
            error=original_error,
            rollback_result=rollback_result,
        )

    def _cancel_with_rollback(
        self,
        request: DomainOperationRequest,
        domain_id: str,
        started_at: datetime,
        transaction_id: str | None,
        checkpoint_id: str | None,
        rollback_policy_id: str | None,
        original_error: Mapping[str, Any],
    ) -> DomainOperationResult:
        if transaction_id is None:
            return self._result(
                request,
                domain_id,
                DomainOperationStatus.CANCELLED,
                started_at,
                error=original_error,
            )

        if self._rollback_executor is None:
            return self._result(
                request,
                domain_id,
                DomainOperationStatus.FAILED,
                started_at,
                transaction_id=transaction_id,
                error=original_error,
                rollback_result=DomainOperationRollbackResult(
                    attempted=False,
                    succeeded=False,
                    policy_id=rollback_policy_id,
                    error=DomainOperationRollbackError(
                        "Cancellation could not close its transaction",
                        details={"reason_code": "rollback_executor_missing"},
                    ).to_dict(),
                ),
            )

        try:
            self._transaction_manager.mark_rollback_started(transaction_id)
            rollback_succeeded = bool(
                self._rollback_executor.rollback(transaction_id, checkpoint_id)
            )
        except (AgentRuntimeError, DomainOperationRollbackError) as exc:
            rollback_error = DomainOperationRollbackError(
                "Cancellation transaction rollback failed",
                details={"error_type": type(exc).__name__},
            ).to_dict()
            return self._result(
                request,
                domain_id,
                DomainOperationStatus.FAILED,
                started_at,
                transaction_id=transaction_id,
                error=original_error,
                rollback_result=DomainOperationRollbackResult(
                    attempted=True,
                    succeeded=False,
                    policy_id=rollback_policy_id,
                    error=rollback_error,
                ),
            )

        if not rollback_succeeded:
            rollback_error = DomainOperationRollbackError(
                "Cancellation transaction rollback failed",
                details={"reason_code": "rollback_executor_rejected"},
            ).to_dict()
            return self._result(
                request,
                domain_id,
                DomainOperationStatus.FAILED,
                started_at,
                transaction_id=transaction_id,
                error=original_error,
                rollback_result=DomainOperationRollbackResult(
                    attempted=True,
                    succeeded=False,
                    policy_id=rollback_policy_id,
                    error=rollback_error,
                ),
            )

        try:
            self._transaction_manager.mark_rolled_back(transaction_id)
        except (AgentRuntimeError, DomainOperationRollbackError) as exc:
            rollback_error = DomainOperationRollbackError(
                "Cancellation transaction close failed",
                details={"error_type": type(exc).__name__},
            ).to_dict()
            return self._result(
                request,
                domain_id,
                DomainOperationStatus.FAILED,
                started_at,
                transaction_id=transaction_id,
                error=original_error,
                rollback_result=DomainOperationRollbackResult(
                    attempted=True,
                    succeeded=False,
                    policy_id=rollback_policy_id,
                    error=rollback_error,
                ),
            )

        return self._result(
            request,
            domain_id,
            DomainOperationStatus.CANCELLED,
            started_at,
            transaction_id=transaction_id,
            error=original_error,
            rollback_result=DomainOperationRollbackResult(
                attempted=True,
                succeeded=True,
                policy_id=rollback_policy_id,
                error=None,
            ),
        )

    def _result(
        self,
        request: DomainOperationRequest,
        domain_id: str,
        status: DomainOperationStatus,
        started_at: datetime,
        *,
        output: Mapping[str, Any] | None = None,
        transaction_id: str | None = None,
        approval_request_id: str | None = None,
        error: Mapping[str, Any] | None = None,
        rollback_result: DomainOperationRollbackResult | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> DomainOperationResult:
        completed_at = self._clock()
        return DomainOperationResult(
            result_id=self._id_factory(),
            request_id=request.request_id,
            operation_id=request.operation_id,
            operation_version=request.operation_version,
            domain_id=domain_id,
            status=status,
            output=output or {},
            transaction_id=transaction_id,
            approval_request_id=approval_request_id,
            rollback_result=rollback_result,
            started_at=started_at,
            completed_at=completed_at,
            error=error,
            metadata=metadata or {},
            trace_entries=(
                DomainOperationTraceEntry(
                    code=f"execution:{status.value}",
                    status=status,
                    occurred_at=completed_at,
                    reason_code=f"execution.{status.value}",
                ),
            ),
        )


__all__ = ["DefaultDomainOperationOrchestrator", "DomainOperationExecutionDelegate"]
