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
from cmm.domains.validation_integration import (
    compose_effective_validation_ids,
    resolve_operation_validation_ids,
)
from cmm.domains.validation_policy_bindings import (
    build_cross_domain_execution_policy,
    build_domain_workflow_policy,
)
from cmm.workflows.engine import NodeExecution


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
        operation_validation_provider: (
            Callable[[Any, tuple[Any, ...]], tuple[Any, ...]]
            | Callable[[Any], tuple[Any, ...]]
            | None
        ) = None,
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
        self._operation_validation_provider = operation_validation_provider

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
                    approval_request_id=request.approval_request_id,
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
                    metadata={
                        "permission_gate": gate_result.to_trace_dict(),
                        "approval_evidence": gate_result.to_trace_dict(),
                    },
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
                requires_checkpoint=True,
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
            validation_requirements=self._resolve_host_validation_requirements(
                definition, request
            ),
            validation_project_root=self._resolve_host_validation_root(request),
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
                gate_result=gate_result,
                validation_result_ids=common_result.validation_result_ids,
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
                gate_result=gate_result,
                validation_result_ids=common_result.validation_result_ids,
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
                gate_result=gate_result,
                validation_result_ids=common_result.validation_result_ids,
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
                gate_result=gate_result,
                validation_result_ids=common_result.validation_result_ids,
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
        result_metadata: dict[str, Any] = {}
        if post_verification is not None:
            result_metadata["post_verification"] = post_verification
        if gate_result is not None:
            result_metadata["permission_authority"] = (
                gate_result.to_authority_reference_dict()
            )
        if common_result.validation_result_ids:
            # Reference-only retention of canonical validation evidence.
            result_metadata["validation_result_ids"] = tuple(
                common_result.validation_result_ids
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
            metadata=result_metadata or None,
        )

    def _resolve_host_validation_requirements(
        self, definition: Any, request: DomainOperationRequest
    ) -> tuple[Any, ...]:
        """Resolve host-derived runtime validation requirements.

        Authority is the canonical operation definition via the injected
        provider (Phase 10.43 thin binding), unioned with host-computed
        composition obligations carried on the typed
        ``effective_validation_ids`` channel (workflow/dependency/
        cross-domain). Caller metadata is never consulted: it cannot add,
        remove, or weaken requirements here. Without a provider the legacy
        metadata-only obligation applies.
        """
        provider = self._operation_validation_provider
        if provider is None:
            return ()
        additional = tuple(request.effective_validation_ids or ())
        try:
            resolved = provider(definition, additional)
        except TypeError:
            # Backward compatibility for single-argument providers.
            resolved = provider(definition)
        return tuple(resolved or ())

    def _resolve_host_validation_root(
        self, request: DomainOperationRequest
    ) -> str | None:
        """Resolve the validation project root deployment setting.

        Only meaningful while a validation provider is configured; the
        requirement set itself always stays host-derived from the operation
        definition.
        """
        if self._operation_validation_provider is None:
            return None
        metadata = request.metadata
        try:
            candidate = metadata.get("validation_project_root")
        except AttributeError:
            return None
        if isinstance(candidate, str) and candidate.strip():
            return candidate
        return None

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
        gate_result: Any | None = None,
        validation_result_ids: tuple[str, ...] = (),
    ) -> DomainOperationResult:
        meta: dict[str, Any] = {}
        if gate_result is not None:
            meta["permission_authority"] = gate_result.to_authority_reference_dict()
        if validation_result_ids:
            # Reference-only retention of canonical validation evidence.
            meta["validation_result_ids"] = tuple(validation_result_ids)
        metadata = meta or None

        if transaction_id is None or self._rollback_executor is None:
            return self._result(
                request,
                domain_id,
                DomainOperationStatus.FAILED,
                started_at,
                transaction_id=transaction_id,
                error=original_error,
                metadata=metadata,
            )
        try:
            self._transaction_manager.mark_rollback_started(transaction_id)
            succeeded = bool(
                self._rollback_executor.rollback(transaction_id, checkpoint_id)
            )
        except (AgentRuntimeError, DomainOperationRollbackError) as exc:
            succeeded = False
            mark_failed_fn = getattr(self._transaction_manager, "mark_failed", None)
            if mark_failed_fn is not None:
                mark_failed_fn(transaction_id)
            rollback_error = DomainOperationRollbackError(
                "Operation rollback failed",
                details={
                    "transaction_id": transaction_id,
                    "error_type": type(exc).__name__,
                },
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
                metadata=metadata,
            )

        rollback_error: Mapping[str, Any] | None = None
        status = DomainOperationStatus.FAILED
        if succeeded:
            self._transaction_manager.mark_rolled_back(transaction_id)
            status = DomainOperationStatus.ROLLED_BACK
        else:
            mark_failed_fn = getattr(self._transaction_manager, "mark_failed", None)
            if mark_failed_fn is not None:
                mark_failed_fn(transaction_id)
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
            metadata=metadata,
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
        gate_result: Any | None = None,
        validation_result_ids: tuple[str, ...] = (),
    ) -> DomainOperationResult:
        meta: dict[str, Any] = {}
        if gate_result is not None:
            meta["permission_authority"] = gate_result.to_authority_reference_dict()
        if validation_result_ids:
            # Reference-only retention of canonical validation evidence.
            meta["validation_result_ids"] = tuple(validation_result_ids)
        metadata = meta or None

        if transaction_id is None:
            return self._result(
                request,
                domain_id,
                DomainOperationStatus.CANCELLED,
                started_at,
                error=original_error,
                metadata=metadata,
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
                metadata=metadata,
            )

        try:
            self._transaction_manager.mark_rollback_started(transaction_id)
            rollback_succeeded = bool(
                self._rollback_executor.rollback(transaction_id, checkpoint_id)
            )
        except (AgentRuntimeError, DomainOperationRollbackError) as exc:
            mark_failed_fn = getattr(self._transaction_manager, "mark_failed", None)
            if mark_failed_fn is not None:
                mark_failed_fn(transaction_id)
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
                metadata=metadata,
            )

        if not rollback_succeeded:
            mark_failed_fn = getattr(self._transaction_manager, "mark_failed", None)
            if mark_failed_fn is not None:
                mark_failed_fn(transaction_id)
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
                metadata=metadata,
            )

        try:
            self._transaction_manager.mark_rolled_back(transaction_id)
        except (AgentRuntimeError, DomainOperationRollbackError) as exc:
            mark_failed_fn = getattr(self._transaction_manager, "mark_failed", None)
            if mark_failed_fn is not None:
                mark_failed_fn(transaction_id)
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
                metadata=metadata,
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
            metadata=metadata,
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


def build_domain_workflow_operation_adapter(
    orchestrator: DefaultDomainOperationOrchestrator,
    *,
    primary_domain_id: str,
    capabilities: tuple[str, ...] = (
        "execute",
        "transaction",
        "rollback",
        "validation",
    ),
    granted_permissions: tuple[str, ...] = (),
    denied_permissions: tuple[str, ...] = (),
    available_resources: tuple[str, ...] = (),
    supporting_domain_ids: tuple[str, ...] = (),
    metadata: Mapping[str, Any] | None = None,
    additional_validation_ids: tuple[str, ...] = (),
    workflow_definitions: Mapping[tuple[str, str], Any] | None = None,
    available_operations: tuple[str, ...] = (),
    id_factory: Callable[[], str] | None = None,
    clock: Callable[[], datetime] | None = None,
    maximum_depth: int = 8,
) -> Callable[[Any, Any], Any]:
    """Route Domain workflow operation nodes through the Domain orchestrator.

    Production bridge for Phase 10.43 workflow validation: operation nodes
    execute through ``DefaultDomainOperationOrchestrator`` (which enforces
    host-derived validation requirements via the Phase 9 bridge), and
    required subworkflow nodes recurse through child executors sharing this
    same adapter so dependency obligations survive execution.

    ``additional_validation_ids`` carries the host-computed workflow/
    subworkflow/dependency obligation union; it is bound into a canonical
    ``DomainWorkflowPolicy`` and enforced on every operation node. Caller
    metadata is never consulted for requirements. Approval/wait nodes keep
    their existing permission-gate ownership and are not handled here.
    """
    workflow_policy = build_domain_workflow_policy(
        required_validation_ids=tuple(additional_validation_ids or ())
    )
    workflow_additional = tuple(workflow_policy.required_steps)
    base_metadata = dict(metadata or {})
    new_ids = id_factory or (lambda: f"wf-node:{uuid.uuid4().hex}")
    definitions = dict(workflow_definitions or {})

    def adapter(node: Any, run: Any) -> Any:
        subworkflow_id = getattr(node, "subworkflow_id", None)
        if subworkflow_id:
            return _execute_subworkflow_node(
                node,
                run,
                child_id=str(subworkflow_id),
                definitions=definitions,
                adapter=adapter,
                id_factory=new_ids,
                clock=clock,
                maximum_depth=maximum_depth,
                available_operations=tuple(available_operations),
            )
        operation_id = getattr(node, "operation_id", None)
        if not operation_id:
            return NodeExecution.not_applicable("workflow.node_not_supported")
        node_metadata = getattr(node, "metadata", None)
        node_metadata = (
            dict(node_metadata) if isinstance(node_metadata, Mapping) else {}
        )
        run_inputs = getattr(run, "inputs", None)
        node_bindings = getattr(node, "input_bindings", None)
        domain_request = DomainOperationRequest(
            request_id=new_ids(),
            operation_id=str(operation_id),
            operation_version=str(getattr(node, "operation_version", None) or "1"),
            inputs={
                **dict(run_inputs or {}),
                **dict(node_bindings or {}),
            },
            agent_run_id=str(getattr(run, "run_id", "workflow-run")),
            workflow_id=str(getattr(run, "workflow_id", "domain-workflow")),
            task_id=str(getattr(node, "node_id", "node")),
            primary_domain_id=str(node_metadata.get("domain_id") or primary_domain_id),
            supporting_domain_ids=tuple(supporting_domain_ids),
            granted_permissions=tuple(granted_permissions),
            denied_permissions=tuple(denied_permissions),
            available_resources=tuple(available_resources),
            capabilities=tuple(capabilities),
            idempotency_key=(
                f"{getattr(run, 'run_id', 'run')}:{getattr(node, 'node_id', 'node')}"
            ),
            metadata={**base_metadata, **node_metadata},
            effective_validation_ids=workflow_additional,
        )
        result = orchestrator.execute(domain_request)
        if result.status is DomainOperationStatus.COMPLETED:
            return NodeExecution.complete(
                dict(result.output),
                operation_result={
                    "domain_result_id": result.result_id,
                    "domain_request_id": result.request_id,
                    "validation_result_ids": list(
                        result.metadata.get("validation_result_ids", ())
                    ),
                    "workflow_validation_policy": "DomainWorkflowPolicy",
                },
            )
        return NodeExecution.failure(f"operation.{result.status.value}")

    return adapter


def _execute_subworkflow_node(
    node: Any,
    run: Any,
    *,
    child_id: str,
    definitions: dict[tuple[str, str], Any],
    adapter: Any,
    id_factory: Any,
    clock: Any,
    maximum_depth: int,
    available_operations: tuple[str, ...] = (),
) -> Any:
    """Execute a required subworkflow node through a child executor."""
    from cmm.domains.workflow_contracts import DomainWorkflowContext
    from cmm.domains.workflow_errors import DomainWorkflowError
    from cmm.domains.workflow_execution import DomainWorkflowExecutor

    version = getattr(node, "subworkflow_version", None)
    child = None
    if version is not None:
        child = definitions.get((child_id, str(version)))
    else:
        matches = [
            definition
            for (identifier, _), definition in definitions.items()
            if identifier == child_id
        ]
        child = matches[0] if len(matches) == 1 else None
    if child is None:
        return NodeExecution.failure("workflow.subworkflow_unknown")
    depth = int(getattr(run, "depth", 0) or 0)
    if depth >= maximum_depth:
        return NodeExecution.failure("workflow.max_depth_exceeded")
    child_executor = DomainWorkflowExecutor(
        id_factory=id_factory,
        clock=clock,
        operation_adapter=adapter,
        depth=depth + 1,
        parent_run_id=getattr(run, "run_id", None),
        root_run_id=getattr(run, "root_run_id", None) or getattr(run, "run_id", None),
        maximum_depth=maximum_depth,
    )
    run_inputs = getattr(run, "inputs", None)
    node_bindings = getattr(node, "input_bindings", None)
    try:
        child_run = child_executor.execute(
            child,
            DomainWorkflowContext(
                child.domain_id,
                available_operations=frozenset(available_operations),
            ),
            {**dict(run_inputs or {}), **dict(node_bindings or {})},
        )
    except DomainWorkflowError as exc:
        return NodeExecution.failure(f"workflow.subworkflow_failed:{exc.code}")
    except Exception:  # noqa: BLE001 - child failure must fail the parent node
        return NodeExecution.failure("workflow.subworkflow_failed")
    status = child_run.common_run.status
    if status.value == "completed":
        return NodeExecution.complete(
            {},
            subworkflow_result={
                "workflow_id": child.workflow_id,
                "run_id": child_run.common_run.run_id,
            },
        )
    return NodeExecution.failure(f"workflow.subworkflow_{status.value}")


class OrchestratedCrossDomainOperationPort:
    """Execute coordinated operations through the Domain orchestrator.

    Production ``CrossDomainOperationPort`` for Phase 10.43: resolves each
    coordinated operation against the canonical operation registry, derives
    the restrictive effective validation union from all coordinated
    operations' canonical definitions plus host global obligations, and
    executes every operation through ``DefaultDomainOperationOrchestrator``
    (which enforces the union via the Phase 9 bridge).

    In this codebase Domain packs declare validation at operation
    granularity, so primary/supporting-domain obligations materialize
    through member operations' canonical definitions; the union is
    commutative and deterministic. Per-operation failures are recorded as
    findings (fail-closed); caller metadata is never consulted.
    """

    def __init__(
        self,
        *,
        orchestrator: Any,
        operation_registry: Any,
        global_required_validation_ids: tuple[str, ...] = (),
        capabilities: tuple[str, ...] = ("execute", "validation"),
        granted_permissions: tuple[str, ...] = (),
        denied_permissions: tuple[str, ...] = (),
        available_resources: tuple[str, ...] = (),
        operation_inputs: Mapping[str, Mapping[str, Any]] | None = None,
        operation_versions: Mapping[str, str] | None = None,
        metadata: Mapping[str, Any] | None = None,
        agent_run_id: str | None = None,
        id_factory: Callable[[], str] | None = None,
    ) -> None:
        self._orchestrator = orchestrator
        self._operation_registry = operation_registry
        self._global_required = compose_effective_validation_ids(
            global_required=tuple(global_required_validation_ids or ())
        )
        self._capabilities = tuple(capabilities)
        self._granted_permissions = tuple(granted_permissions)
        self._denied_permissions = tuple(denied_permissions)
        self._available_resources = tuple(available_resources)
        self._operation_inputs = dict(operation_inputs or {})
        self._operation_versions = dict(operation_versions or {})
        self._metadata = dict(metadata or {})
        self._agent_run_id = agent_run_id or f"cross-domain:{uuid.uuid4().hex}"
        self._id_factory = id_factory or (lambda: f"xop:{uuid.uuid4().hex}")
        self.calls: list[tuple[str, tuple[str, ...]]] = []

    def _resolve_definition(self, operation_id: str) -> Any:
        from cmm.domains.errors import CrossDomainContractError

        pinned = self._operation_versions.get(operation_id)
        if pinned is not None:
            definition = self._operation_registry.get(operation_id, pinned)
            if definition is None:
                raise CrossDomainContractError(
                    f"Unknown cross-domain operation '{operation_id}@{pinned}'",
                    field="operation_id",
                )
            return definition
        candidates = [
            item
            for item in self._operation_registry.list_definitions()
            if item.operation_id == operation_id
        ]
        if len(candidates) != 1:
            raise CrossDomainContractError(
                f"Ambiguous cross-domain operation '{operation_id}': "
                "pin an exact version",
                field="operation_id",
            )
        return candidates[0]

    def coordinate_operations(
        self,
        *,
        operation_ids: tuple[str, ...],
        requesting_domains: Mapping[str, tuple[Any, ...]],
        context: Any,
    ) -> Any:
        definitions: dict[str, Any] = {}
        failures: list[str] = []
        for raw_id in operation_ids:
            operation_id = str(raw_id)
            try:
                definitions[operation_id] = self._resolve_definition(operation_id)
            except Exception as exc:  # noqa: BLE001 - per-op fail-closed capture
                failures.append(f"{operation_id}: {type(exc).__name__}")
        derived: dict[str, tuple[str, ...]] = {}
        for operation_id, definition in definitions.items():
            try:
                derived[operation_id] = resolve_operation_validation_ids(definition)
            except Exception as exc:  # noqa: BLE001 - per-op fail-closed capture
                failures.append(f"{operation_id}: {type(exc).__name__}")
        union_all = compose_effective_validation_ids(
            global_required=self._global_required,
            operation_required=tuple(item for ids in derived.values() for item in ids),
        )
        completed: list[str] = []
        findings: list[Any] = []
        for operation_id in operation_ids:
            operation_id = str(operation_id)
            definition = definitions.get(operation_id)
            if definition is None:
                findings.append(
                    self._finding(
                        operation_id,
                        requesting_domains,
                        {"status": "unresolvable", "reason": "unknown_operation"},
                    )
                )
                continue
            own = derived.get(operation_id, ())
            others = compose_effective_validation_ids(
                supporting_required=tuple(
                    item
                    for other, ids in derived.items()
                    if other != operation_id
                    for item in ids
                )
            )
            build_cross_domain_execution_policy(
                global_required=self._global_required,
                primary_required=own,
                supporting_required=others,
                operation_required=own,
            )
            requesting = requesting_domains.get(operation_id, ()) or ()
            supporting = tuple(
                str(domain.slug if hasattr(domain, "slug") else domain)
                for domain in requesting
            )
            primary_domain = str(definition.domain_id)
            supporting = tuple(
                f"domain:{slug}" if ":" not in slug else slug for slug in supporting
            )
            supporting = tuple(item for item in supporting if item != primary_domain)
            request_inputs = self._operation_inputs.get(operation_id, {})
            domain_request = DomainOperationRequest(
                request_id=self._id_factory(),
                operation_id=operation_id,
                operation_version=str(definition.version),
                inputs=dict(request_inputs),
                agent_run_id=self._agent_run_id,
                workflow_id="cross-domain",
                task_id=operation_id,
                primary_domain_id=primary_domain,
                supporting_domain_ids=supporting,
                granted_permissions=self._granted_permissions,
                denied_permissions=self._denied_permissions,
                available_resources=self._available_resources,
                capabilities=self._capabilities,
                idempotency_key=f"{self._agent_run_id}:{operation_id}",
                metadata=dict(self._metadata),
                effective_validation_ids=union_all,
            )
            self.calls.append((operation_id, union_all))
            try:
                result = self._orchestrator.execute(domain_request)
            except Exception as exc:  # noqa: BLE001 - per-op fail-closed capture
                findings.append(
                    self._finding(
                        operation_id,
                        requesting_domains,
                        {
                            "status": "validation_failed",
                            "reason": type(exc).__name__,
                        },
                    )
                )
                continue
            if result.status.value == "completed":
                completed.append(operation_id)
            else:
                findings.append(
                    self._finding(
                        operation_id,
                        requesting_domains,
                        {
                            "status": str(result.status.value),
                            "reason": "operation_did_not_complete",
                        },
                    )
                )
        for failure in failures:
            findings.append(
                self._unresolvable_finding(failure),
            )
        return self._build_result(
            operation_ids=tuple(str(item) for item in operation_ids),
            completed=tuple(completed),
            findings=tuple(findings),
            union_all=union_all,
        )

    @staticmethod
    def _finding(
        operation_id: str,
        requesting_domains: Mapping[str, tuple[Any, ...]],
        value: dict[str, Any],
    ) -> Any:
        from cmm.domains.cross_domain_contracts import CrossDomainFinding
        from cmm.domains.identifiers import DomainId

        requesting = requesting_domains.get(operation_id, ()) or ()
        domains: list[Any] = []
        for domain in requesting:
            if isinstance(domain, DomainId):
                domains.append(domain)
            else:
                slug = str(getattr(domain, "slug", domain))
                domains.append(DomainId(slug=slug.split(":")[-1]))
        return CrossDomainFinding(
            identifier=f"{operation_id}.validation_blocked",
            value=dict(value),
            source_domains=tuple(domains),
            provenance=("cross-domain.operation-coordination",),
        )

    @staticmethod
    def _unresolvable_finding(failure: str) -> Any:
        from cmm.domains.cross_domain_contracts import CrossDomainFinding

        return CrossDomainFinding(
            identifier="cross-domain.operation.unresolvable",
            value={"error": failure},
            source_domains=(),
            provenance=("cross-domain.operation-coordination",),
        )

    @staticmethod
    def _build_result(
        *,
        operation_ids: tuple[str, ...],
        completed: tuple[str, ...],
        findings: tuple[Any, ...],
        union_all: tuple[str, ...],
    ) -> Any:
        from cmm.domains.cross_domain_contracts import CrossDomainOperationResult
        from cmm.domains.enums import CrossDomainStatus

        if len(completed) == len(operation_ids):
            status = CrossDomainStatus.COMPLETED
        elif completed:
            status = CrossDomainStatus.PARTIAL
        else:
            status = CrossDomainStatus.FAILED
        return CrossDomainOperationResult(
            status=status,
            operation_ids=tuple(operation_ids),
            findings=tuple(findings),
            metadata={
                "cross_domain_validation_policy": "CrossDomainExecutionPolicy",
                "effective_validation_ids": list(union_all),
            },
        )


__all__ = [
    "DefaultDomainOperationOrchestrator",
    "DomainOperationExecutionDelegate",
    "OrchestratedCrossDomainOperationPort",
    "build_domain_workflow_operation_adapter",
]
