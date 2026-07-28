"""Composition root for Agent Runtime integration execution."""

from __future__ import annotations

import threading
from collections.abc import Mapping
from dataclasses import replace
from datetime import datetime, timezone
from types import MappingProxyType
from typing import Any, ClassVar

from cmm.agent_runtime.action_budget_contracts import BudgetAllocation
from cmm.agent_runtime.agent_delegation_contracts import DelegationProposal
from cmm.agent_runtime.agent_delegation_errors import (
    AgentDelegationInvalidStateTransitionError,
)
from cmm.agent_runtime.agent_observability_enums import (
    AgentAuditOutcome,
    AgentTelemetryKind,
)
from cmm.agent_runtime.agent_registry_contracts import AgentFactoryContext, AgentVersion
from cmm.agent_runtime.agent_registry_enums import AgentLifecycle
from cmm.agent_runtime.agent_runtime_integration_contracts import (
    IntegratedAgentExecutionRequest,
    IntegratedAgentExecutionResult,
    IntegrationCompensation,
    IntegrationExecutionRecord,
)
from cmm.agent_runtime.agent_runtime_integration_enums import (
    TERMINAL_INTEGRATION_STATES,
    IntegrationExecutionState,
    IntegrationFailureMode,
)
from cmm.agent_runtime.agent_runtime_integration_errors import (
    AgentRuntimeIntegrationError,
    IntegrationIdempotencyConflictError,
)
from cmm.agent_runtime.agent_runtime_integration_store import (
    AgentRuntimeIntegrationStore,
)
from cmm.agent_runtime.agent_security_contracts import (
    AgentPermissionContext,
    PermissionCheckRequest,
)
from cmm.agent_runtime.agent_security_enums import PermissionEffect
from cmm.agent_runtime.agent_security_errors import PromptInjectionBlockedError
from cmm.agent_runtime.checkpoint_contracts import CheckpointCreationRequest
from cmm.agent_runtime.enums import BudgetResourceType, GoalKind, GoalStatus
from cmm.agent_runtime.errors import (
    AgentOperationNotRegisteredError,
    AgentOperationVersionNotRegisteredError,
    BudgetReservationAlreadyResolvedError,
    InvalidRuntimeContractError,
)
from cmm.agent_runtime.operation_execution_contracts import AgentOperationRequest
from cmm.agent_runtime.runtime_event_factory import AgentRuntimeEventFactory
from cmm.agent_runtime.runtime_event_types import EventType

_IDEMPOTENT_COMPENSATION_ERRORS: tuple[type[Exception], ...] = (
    InvalidRuntimeContractError,
    BudgetReservationAlreadyResolvedError,
    AgentDelegationInvalidStateTransitionError,
)


class _ObservabilityContext:
    """Best-effort telemetry/event/span helper for one execution attempt.

    Instantiated fresh per call so it carries no shared mutable state across
    concurrent executions; failures are recorded as visible warnings instead
    of being swallowed.
    """

    def __init__(
        self,
        *,
        observability_service: Any | None,
        event_bus: Any | None,
        event_factory: AgentRuntimeEventFactory,
        trace_id: str,
    ) -> None:
        self._observability_service = observability_service
        self._event_bus = event_bus
        self._event_factory = event_factory
        self.trace_id = trace_id
        self.warnings: list[str] = []
        self.record_ids: list[str] = []

    def start_trace(
        self,
        *,
        agent_run_id: str,
        goal_id: str,
        agent_id: str | None,
        correlation_id: str | None,
    ) -> None:
        if self._observability_service is None:
            return
        try:
            self._observability_service.start_trace(
                agent_run_id,
                goal_id,
                agent_id=agent_id,
                correlation_id=correlation_id,
                trace_id=self.trace_id,
            )
        except Exception as exc:  # noqa: BLE001
            self.warnings.append(f"trace start failed: {exc}")

    def span(self, operation_id: str, operation_name: str) -> str | None:
        if self._observability_service is None:
            return None
        try:
            span = self._observability_service.start_span(
                self.trace_id, operation_id, operation_name
            )
            return span.span_id
        except Exception as exc:  # noqa: BLE001
            self.warnings.append(f"span '{operation_name}' start failed: {exc}")
            return None

    def close_span(
        self, span_id: str | None, *, success: bool, error: str | None = None
    ) -> None:
        if self._observability_service is None or span_id is None:
            return
        try:
            if success:
                self._observability_service.complete_span(span_id)
            else:
                self._observability_service.fail_span(
                    span_id, error_summary=error or "operation failed"
                )
        except Exception as exc:  # noqa: BLE001
            self.warnings.append(f"span close failed: {exc}")

    def complete_trace(self) -> None:
        if self._observability_service is None:
            return
        try:
            self._observability_service.complete_trace(self.trace_id)
        except Exception as exc:  # noqa: BLE001
            self.warnings.append(f"trace complete failed: {exc}")

    def telemetry(self, kind: AgentTelemetryKind, **fields: Any) -> str | None:
        if self._observability_service is None:
            return None
        try:
            record = self._observability_service.record_telemetry(
                kind=kind, trace_id=self.trace_id, **fields
            )
        except Exception as exc:  # noqa: BLE001
            self.warnings.append(f"telemetry '{kind.value}' failed: {exc}")
            return None
        self.record_ids.append(record.id)
        return record.id

    def audit(self, **fields: Any) -> str | None:
        """Record a mandatory security audit entry. Failures are not swallowed."""

        if self._observability_service is None:
            return None
        record = self._observability_service.record_audit(
            trace_id=self.trace_id, **fields
        )
        self.record_ids.append(record.id)
        return record.id

    def event(
        self,
        event_type: str,
        *,
        request: IntegratedAgentExecutionRequest,
        agent_id: str | None,
        agent_run_id: str | None,
        payload: Mapping[str, Any] | None = None,
    ) -> str | None:
        if self._event_bus is None:
            return None
        try:
            event = self._event_factory.create_event(
                event_type=event_type,
                payload=dict(payload or {}),
                agent_id=agent_id,
                agent_run_id=agent_run_id,
                goal_id=request.goal_id,
                correlation_id=request.correlation_id or self.trace_id,
                causation_id=request.causation_id,
                actor_id=request.actor_id,
            )
            self._event_bus.publish(event)
        except Exception as exc:  # noqa: BLE001
            self.warnings.append(f"event '{event_type}' publish failed: {exc}")
            return None
        self.record_ids.append(event.header.event_id)
        return event.header.event_id


class AgentRuntimeIntegrationService:
    """Orchestrate one integrated Agent Runtime execution using canonical services."""

    _TERMINAL_GOAL_STATUSES: ClassVar[set[GoalStatus]] = {
        GoalStatus.COMPLETED,
        GoalStatus.PARTIALLY_COMPLETED,
        GoalStatus.FAILED,
        GoalStatus.ABANDONED,
        GoalStatus.CANCELLED,
        GoalStatus.SUPERSEDED,
    }

    def __init__(
        self,
        *,
        store: AgentRuntimeIntegrationStore,
        goal_manager: Any,
        registry_service: Any,
        runtime_loop: Any,
        security_service: Any,
        budget_service: Any | None = None,
        approval_service: Any | None = None,
        execution_adapter: Any,
        event_bus: Any | None = None,
        observability_service: Any | None = None,
        checkpoint_service: Any | None = None,
        recovery_service: Any | None = None,
        delegation_service: Any | None = None,
        memory_service: Any | None = None,
    ) -> None:
        self._store = store
        self._goal_manager = goal_manager
        self._registry_service = registry_service
        self._runtime_loop = runtime_loop
        self._security_service = security_service
        self._budget_service = budget_service
        self._approval_service = approval_service
        self._execution_adapter = execution_adapter
        self._event_bus = event_bus
        self._observability_service = observability_service
        self._checkpoint_service = checkpoint_service
        self._recovery_service = recovery_service
        self._delegation_service = delegation_service
        self._memory_service = memory_service
        self._event_factory = AgentRuntimeEventFactory()
        self._lock = threading.RLock()

    def _observability(
        self, request: IntegratedAgentExecutionRequest
    ) -> _ObservabilityContext:
        trace_id = request.trace_id or f"trace-{request.execution_id}"
        return _ObservabilityContext(
            observability_service=self._observability_service,
            event_bus=self._event_bus,
            event_factory=self._event_factory,
            trace_id=trace_id,
        )

    def validate(self, request: IntegratedAgentExecutionRequest) -> None:
        """Validate fail-closed dependencies before creating side effects."""

        self._validate_goal(request)
        self._select_agent(request)
        self._validate_deadlines(request)
        self._validate_prompt_injection(request)
        self._validate_operations(request)

    def get_status(self, execution_id: str) -> IntegrationExecutionRecord | None:
        """Return the persisted execution record snapshot."""

        return self._store.get(execution_id)

    def execute(
        self, request: IntegratedAgentExecutionRequest
    ) -> IntegratedAgentExecutionResult:
        """Execute or resume the preparation/execution path idempotently."""

        with self._lock:
            existing = self._store.get_by_request_id(request.request_id)
            if existing is not None:
                self._ensure_same_request(existing, request)
                if existing.result is not None:
                    return existing.result
                if existing.state is IntegrationExecutionState.WAITING_APPROVAL:
                    return self._paused_result(existing)

            self.validate(request)
            descriptor = self._select_agent(request)
            run_id = self._run_id(request.execution_id)
            record = self._store.create(
                IntegrationExecutionRecord(
                    execution_id=request.execution_id,
                    request_id=request.request_id,
                    goal_id=request.goal_id,
                    request=request,
                    agent_id=descriptor.agent_id,
                    agent_version=descriptor.version.canonical(),
                )
            )
            record = self._store.transition(
                record.execution_id,
                IntegrationExecutionState.VALIDATING,
                expected_version=record.version,
            )
            record = self._store.transition(
                record.execution_id,
                IntegrationExecutionState.AUTHORIZED,
                expected_version=record.version,
            )

            run = self._runtime_loop.start(
                run_id,
                agent_id=descriptor.agent_id,
                goal_id=request.goal_id,
                autonomy_level=request.max_autonomy_level,
                idempotency_key=f"{request.execution_id}:runtime-start",
                now=request.created_at.isoformat(),
            )
            record = self._store.bind_run(
                record.execution_id, run.id, expected_version=record.version
            )
            record = self._store.append_compensation(
                record.execution_id,
                IntegrationCompensation(
                    compensation_id=f"comp-{request.execution_id}-runtime-run",
                    execution_id=request.execution_id,
                    action="runtime.cancel_run",
                    target_id=run.id,
                    failure_mode=IntegrationFailureMode.MANDATORY_WITH_COMPENSATION,
                    created_at=self._now(),
                ),
                expected_version=record.version,
            )
            self._registry_service.create_agent(
                descriptor,
                AgentFactoryContext(
                    request_id=request.request_id,
                    run_id=run.id,
                    actor_id=request.actor_id,
                ),
            )

            obs = self._observability(request)
            obs.start_trace(
                agent_run_id=run.id,
                goal_id=request.goal_id,
                agent_id=descriptor.agent_id,
                correlation_id=request.correlation_id,
            )
            obs.telemetry(
                AgentTelemetryKind.RUN_STARTED,
                agent_id=descriptor.agent_id,
                agent_run_id=run.id,
                goal_id=request.goal_id,
                correlation_id=request.correlation_id,
                causation_id=request.causation_id,
            )
            obs.event(
                EventType.AGENT_RUN_STARTED,
                request=request,
                agent_id=descriptor.agent_id,
                agent_run_id=run.id,
            )

            decision = self._check_permissions(request, descriptor.agent_id, run.id)
            obs.telemetry(
                AgentTelemetryKind.PERMISSION_EVALUATED,
                agent_id=descriptor.agent_id,
                agent_run_id=run.id,
                goal_id=request.goal_id,
                outcome=(
                    AgentAuditOutcome.SUCCESS
                    if decision.effect is PermissionEffect.ALLOW
                    else AgentAuditOutcome.DENIED
                ),
                reason_codes=decision.reason_codes,
            )
            obs.audit(
                action="agent_runtime.integration.permission_check",
                outcome=(
                    AgentAuditOutcome.SUCCESS
                    if decision.effect is PermissionEffect.ALLOW
                    else AgentAuditOutcome.DENIED
                ),
                agent_id=descriptor.agent_id,
                agent_run_id=run.id,
                goal_id=request.goal_id,
                decision=decision.effect.value,
                reason_codes=decision.reason_codes,
            )
            if decision.effect is PermissionEffect.KILL_SWITCH_ACTIVE:
                return self._save_snapshot(
                    record.execution_id,
                    IntegrationExecutionState.KILL_SWITCH_BLOCKED,
                    errors=decision.reason_codes,
                    warnings=tuple(obs.warnings),
                    event_ids=tuple(obs.record_ids),
                )
            if decision.is_denied:
                return self._save_snapshot(
                    record.execution_id,
                    IntegrationExecutionState.DENIED,
                    errors=decision.reason_codes,
                    warnings=tuple(obs.warnings),
                    event_ids=tuple(obs.record_ids),
                )

            if self._requires_approval(request):
                obs.telemetry(
                    AgentTelemetryKind.APPROVAL_REQUESTED,
                    agent_id=descriptor.agent_id,
                    agent_run_id=run.id,
                    goal_id=request.goal_id,
                )
                obs.event(
                    EventType.APPROVAL_REQUESTED,
                    request=request,
                    agent_id=descriptor.agent_id,
                    agent_run_id=run.id,
                )
                return self._pause_for_approval(
                    record.execution_id, request, run.id, warnings=tuple(obs.warnings)
                )

            return self._continue_execution(
                record.execution_id, initial_warnings=tuple(obs.warnings)
            )

    def resume(
        self, execution_id: str, *, approval_id: str
    ) -> IntegratedAgentExecutionResult:
        """Resume a paused approval execution after explicit revalidation."""

        with self._lock:
            record = self._require_record(execution_id)
            if record.result is not None and record.result.is_terminal:
                return record.result
            if approval_id not in record.pending_approval_ids:
                raise AgentRuntimeIntegrationError("approval is not pending")
            if self._approval_service is None:
                raise AgentRuntimeIntegrationError("approval service is required")
            request = self._require_request(record)
            obs = self._observability(request)
            resolution = self._approval_service.resolve(approval_id)
            obs.telemetry(
                AgentTelemetryKind.APPROVAL_RESOLVED,
                agent_id=record.agent_id,
                agent_run_id=record.agent_run_id,
                goal_id=request.goal_id,
                approval_id=approval_id,
                outcome=(
                    AgentAuditOutcome.SUCCESS
                    if resolution.may_execute
                    else AgentAuditOutcome.DENIED
                ),
            )
            obs.event(
                EventType.APPROVAL_APPROVED
                if resolution.may_execute
                else EventType.APPROVAL_REJECTED,
                request=request,
                agent_id=record.agent_id,
                agent_run_id=record.agent_run_id,
            )
            if not resolution.may_execute:
                obs.complete_trace()
                return self._save_snapshot(
                    execution_id,
                    IntegrationExecutionState.DENIED,
                    errors=resolution.reason_codes,
                    warnings=tuple(obs.warnings),
                    event_ids=tuple(obs.record_ids),
                )
            descriptor = self._select_agent(request)
            decision = self._check_permissions(
                request, descriptor.agent_id, record.agent_run_id
            )
            obs.audit(
                action="agent_runtime.integration.permission_check",
                outcome=(
                    AgentAuditOutcome.SUCCESS
                    if decision.effect is PermissionEffect.ALLOW
                    else AgentAuditOutcome.DENIED
                ),
                agent_id=descriptor.agent_id,
                agent_run_id=record.agent_run_id,
                goal_id=request.goal_id,
                decision=decision.effect.value,
                reason_codes=decision.reason_codes,
            )
            if decision.effect is PermissionEffect.KILL_SWITCH_ACTIVE:
                obs.complete_trace()
                return self._save_snapshot(
                    execution_id,
                    IntegrationExecutionState.KILL_SWITCH_BLOCKED,
                    errors=decision.reason_codes,
                    warnings=tuple(obs.warnings),
                    event_ids=tuple(obs.record_ids),
                )
            if decision.is_denied:
                obs.complete_trace()
                return self._save_snapshot(
                    execution_id,
                    IntegrationExecutionState.DENIED,
                    errors=decision.reason_codes,
                    warnings=tuple(obs.warnings),
                    event_ids=tuple(obs.record_ids),
                )
            self._store.resolve_pending_approval(approval_id)
            return self._continue_execution(
                execution_id, initial_warnings=tuple(obs.warnings)
            )

    def cancel(
        self, execution_id: str, *, reason: str | None = None
    ) -> IntegratedAgentExecutionResult:
        """Cancel an active or paused execution idempotently, running compensations."""

        with self._lock:
            record = self._require_record(execution_id)
            if record.result is not None and record.result.is_terminal:
                return record.result
            compensation_warnings = self._run_compensations(execution_id)
            cancelled = self._store.cancel(execution_id, reason=reason)
            request = cancelled.request
            warnings = compensation_warnings
            event_ids: tuple[str, ...] = ()
            if request is not None:
                obs = self._observability(request)
                obs.telemetry(
                    AgentTelemetryKind.RUN_CANCELLED,
                    agent_id=cancelled.agent_id,
                    agent_run_id=cancelled.agent_run_id,
                    goal_id=cancelled.goal_id,
                    reason_codes=(reason,) if reason else (),
                )
                obs.event(
                    EventType.AGENT_RUN_CANCELLED,
                    request=request,
                    agent_id=cancelled.agent_id,
                    agent_run_id=cancelled.agent_run_id,
                )
                obs.complete_trace()
                warnings = compensation_warnings + tuple(obs.warnings)
                event_ids = tuple(obs.record_ids)
            return self._save_snapshot(
                cancelled.execution_id,
                IntegrationExecutionState.CANCELLED,
                errors=(reason,) if reason else (),
                warnings=warnings,
                event_ids=event_ids,
            )

    def _continue_execution(
        self, execution_id: str, *, initial_warnings: tuple[str, ...] = ()
    ) -> IntegratedAgentExecutionResult:
        record = self._require_record(execution_id)
        request = self._require_request(record)
        obs = self._observability(request)
        obs.warnings.extend(initial_warnings)
        if record.state is IntegrationExecutionState.AUTHORIZED:
            record = self._store.transition(
                execution_id, IntegrationExecutionState.PLANNING
            )
        if record.state is IntegrationExecutionState.PLANNING:
            record = self._store.transition(
                execution_id, IntegrationExecutionState.RUNNING
            )
        elif record.state is IntegrationExecutionState.WAITING_APPROVAL:
            record = self._store.resume(execution_id, IntegrationExecutionState.RUNNING)

        record, retry_count, recovery_attempts, checkpoint_errors = (
            self._ensure_checkpoint(record, request, obs)
        )
        if checkpoint_errors:
            compensation_warnings = self._run_compensations(execution_id)
            obs.telemetry(
                AgentTelemetryKind.RUN_FAILED,
                agent_id=record.agent_id,
                agent_run_id=record.agent_run_id,
                goal_id=request.goal_id,
                reason_codes=checkpoint_errors,
            )
            obs.event(
                EventType.AGENT_RUN_FAILED,
                request=request,
                agent_id=record.agent_id,
                agent_run_id=record.agent_run_id,
                payload={"reason": "checkpoint_failed"},
            )
            obs.complete_trace()
            return self._save_snapshot(
                execution_id,
                IntegrationExecutionState.FAILED,
                retry_count=retry_count,
                recovery_attempts=recovery_attempts,
                checkpoint_ids=record.checkpoint_ids,
                warnings=tuple(obs.warnings) + compensation_warnings,
                event_ids=tuple(obs.record_ids),
                errors=checkpoint_errors,
            )

        operation_results = []
        operation_result_ids = []
        reservation = self._reserve_budget(record, request)
        if reservation is not None:
            obs.telemetry(
                AgentTelemetryKind.BUDGET_RESERVED,
                agent_id=record.agent_id,
                agent_run_id=record.agent_run_id,
                goal_id=request.goal_id,
            )
        for operation in request.operations:
            prepared = self._operation_for_run(operation, record.agent_run_id)
            span_id = obs.span(prepared.id, f"operation:{prepared.operation_name}")
            obs.telemetry(
                AgentTelemetryKind.OPERATION_STARTED,
                agent_id=record.agent_id,
                agent_run_id=record.agent_run_id,
                goal_id=request.goal_id,
                operation_id=prepared.id,
            )
            obs.event(
                EventType.OPERATION_STARTED,
                request=request,
                agent_id=record.agent_id,
                agent_run_id=record.agent_run_id,
                payload={"operation_id": prepared.id},
            )
            result = self._execution_adapter.execute(prepared)
            operation_results.append(result)
            operation_result_ids.append(result.id)
            obs.close_span(span_id, success=bool(result.success))
            obs.telemetry(
                AgentTelemetryKind.OPERATION_COMPLETED
                if result.success
                else AgentTelemetryKind.OPERATION_FAILED,
                agent_id=record.agent_id,
                agent_run_id=record.agent_run_id,
                goal_id=request.goal_id,
                operation_id=prepared.id,
            )
            obs.event(
                EventType.OPERATION_COMPLETED
                if result.success
                else EventType.OPERATION_FAILED,
                request=request,
                agent_id=record.agent_id,
                agent_run_id=record.agent_run_id,
                payload={"operation_id": prepared.id},
            )
            if not result.success:
                record = self._store.update(
                    replace(
                        self._require_record(execution_id),
                        operation_result_ids=tuple(operation_result_ids),
                    )
                )
                compensation_warnings = self._run_compensations(execution_id)
                obs.telemetry(
                    AgentTelemetryKind.RUN_FAILED,
                    agent_id=record.agent_id,
                    agent_run_id=record.agent_run_id,
                    goal_id=request.goal_id,
                    reason_codes=result.reason_codes,
                )
                obs.event(
                    EventType.AGENT_RUN_FAILED,
                    request=request,
                    agent_id=record.agent_id,
                    agent_run_id=record.agent_run_id,
                    payload={"operation_id": prepared.id},
                )
                obs.complete_trace()
                return self._save_snapshot(
                    execution_id,
                    IntegrationExecutionState.FAILED,
                    operation_results=tuple(operation_results),
                    operation_request_ids=tuple(item.id for item in request.operations),
                    checkpoint_ids=record.checkpoint_ids,
                    retry_count=retry_count,
                    recovery_attempts=recovery_attempts,
                    warnings=tuple(obs.warnings) + compensation_warnings,
                    event_ids=tuple(obs.record_ids),
                    errors=(
                        f"operation {prepared.operation_name} failed: {result.reason_codes}",
                    ),
                )
        consumption_id = self._confirm_budget(reservation)
        if consumption_id:
            obs.telemetry(
                AgentTelemetryKind.BUDGET_CONSUMED,
                agent_id=record.agent_id,
                agent_run_id=record.agent_run_id,
                goal_id=request.goal_id,
            )

        if operation_result_ids:
            record = self._store.update(
                replace(
                    self._require_record(execution_id),
                    operation_result_ids=tuple(operation_result_ids),
                )
            )

        record, delegations = self._attempt_delegation(record, request, obs)

        memory_ids = self._record_memory(request, operation_results)
        obs.telemetry(
            AgentTelemetryKind.RUN_COMPLETED,
            agent_id=record.agent_id,
            agent_run_id=record.agent_run_id,
            goal_id=request.goal_id,
        )
        obs.event(
            EventType.AGENT_RUN_COMPLETED,
            request=request,
            agent_id=record.agent_id,
            agent_run_id=record.agent_run_id,
        )
        obs.complete_trace()
        return self._save_snapshot(
            execution_id,
            IntegrationExecutionState.COMPLETED,
            operation_results=tuple(operation_results),
            operation_request_ids=tuple(item.id for item in request.operations),
            budget_consumption_ids=(consumption_id,) if consumption_id else (),
            memory_updates=tuple({"id": memory_id} for memory_id in memory_ids),
            checkpoint_ids=record.checkpoint_ids,
            delegations=delegations,
            retry_count=retry_count,
            recovery_attempts=recovery_attempts,
            warnings=tuple(obs.warnings),
            event_ids=tuple(obs.record_ids),
        )

    def _pause_for_approval(
        self,
        execution_id: str,
        request: IntegratedAgentExecutionRequest,
        run_id: str,
        *,
        warnings: tuple[str, ...] = (),
    ) -> IntegratedAgentExecutionResult:
        if self._approval_service is None:
            raise AgentRuntimeIntegrationError("approval service is required")
        approval = self._approval_service.create_request(
            title=f"Approve execution {execution_id}",
            description=f"Approve Agent Runtime execution {execution_id}",
            requested_by="agent-runtime-integration",
            agent_run_id=run_id,
            goal_id=request.goal_id,
            workflow_id=request.workflow.workflow_id if request.workflow else None,
            operation_id=request.operations[0].id if request.operations else None,
            reason_codes=("integration.approval_required",),
            required_approvers=(request.actor_id,),
            metadata={"execution_id": execution_id, "request_id": request.request_id},
        )
        self._store.set_pending_approval(execution_id, approval.id)
        return self._save_snapshot(
            execution_id,
            IntegrationExecutionState.WAITING_APPROVAL,
            approval_ids=(approval.id,),
            warnings=warnings,
        )

    def _save_snapshot(
        self,
        execution_id: str,
        state: IntegrationExecutionState,
        *,
        operation_request_ids: tuple[str, ...] = (),
        operation_results: tuple[Any, ...] = (),
        approval_ids: tuple[str, ...] = (),
        budget_consumption_ids: tuple[str, ...] = (),
        memory_updates: tuple[dict[str, str], ...] = (),
        checkpoint_ids: tuple[str, ...] = (),
        delegations: tuple[Mapping[str, Any], ...] = (),
        retry_count: int = 0,
        recovery_attempts: tuple[Mapping[str, Any], ...] = (),
        warnings: tuple[str, ...] = (),
        event_ids: tuple[str, ...] = (),
        errors: tuple[str, ...] = (),
    ) -> IntegratedAgentExecutionResult:
        record = self._require_record(execution_id)
        request = self._require_request(record)
        trace_id = request.trace_id or f"trace-{request.execution_id}"
        merged_event_ids = tuple(dict.fromkeys((*record.event_ids, *event_ids)))
        result = IntegratedAgentExecutionResult(
            execution_id=record.execution_id,
            request_id=record.request_id,
            goal_id=record.goal_id,
            agent_id=record.agent_id,
            agent_version=record.agent_version,
            agent_run_id=record.agent_run_id,
            final_state=state,
            operation_request_ids=operation_request_ids,
            operation_results=operation_results,
            approval_ids=approval_ids,
            budget_consumption_ids=budget_consumption_ids,
            memory_updates=memory_updates,
            checkpoint_ids=checkpoint_ids,
            delegations=delegations,
            retry_count=retry_count,
            recovery_attempts=recovery_attempts,
            warnings=warnings,
            errors=errors,
            trace_id=trace_id,
            event_ids=merged_event_ids,
            created_at=request.created_at,
            completed_at=self._now() if state in TERMINAL_INTEGRATION_STATES else None,
        )
        if state in (
            IntegrationExecutionState.WAITING_APPROVAL,
            IntegrationExecutionState.WAITING,
            IntegrationExecutionState.KILL_SWITCH_BLOCKED,
        ):
            current = self._require_record(execution_id)
            if current.state is not state:
                self._store.transition(execution_id, state)
            current = self._require_record(execution_id)
            self._store.update(replace(current, result=result))
            return result
        self._store.save_terminal_result(execution_id, result)
        return result

    def _validate_goal(self, request: IntegratedAgentExecutionRequest) -> Any:
        goal = self._goal_manager.get_goal(request.goal_id)
        if goal is None:
            raise AgentRuntimeIntegrationError(
                "goal not found",
                failure_mode=IntegrationFailureMode.MANDATORY_FAIL_CLOSED,
            )
        if goal.status in self._TERMINAL_GOAL_STATUSES:
            raise AgentRuntimeIntegrationError(
                "goal is terminal",
                failure_mode=IntegrationFailureMode.MANDATORY_FAIL_CLOSED,
            )
        return goal

    def _select_agent(self, request: IntegratedAgentExecutionRequest) -> Any:
        agent_id = request.requested_agent_id
        if agent_id is None:
            raise AgentRuntimeIntegrationError("requested agent is required")
        descriptor = self._registry_service.get_agent(
            agent_id,
            AgentVersion.parse(request.requested_agent_version)
            if request.requested_agent_version is not None
            else None,
        )
        if descriptor is None:
            raise AgentRuntimeIntegrationError(
                "agent not found",
                failure_mode=IntegrationFailureMode.MANDATORY_FAIL_CLOSED,
            )
        if descriptor.lifecycle is not AgentLifecycle.ACTIVE:
            raise AgentRuntimeIntegrationError(
                "agent must be active",
                failure_mode=IntegrationFailureMode.MANDATORY_FAIL_CLOSED,
            )
        supported = {
            *descriptor.supported_operations,
            *(capability.name for capability in descriptor.capabilities),
            *(
                operation
                for capability in descriptor.capabilities
                for operation in capability.operations
            ),
        }
        missing = set(request.required_capabilities) - supported
        if missing:
            raise AgentRuntimeIntegrationError(
                f"agent capability mismatch: {sorted(missing)}",
                failure_mode=IntegrationFailureMode.MANDATORY_FAIL_CLOSED,
            )
        return descriptor

    def _validate_deadlines(self, request: IntegratedAgentExecutionRequest) -> None:
        now = self._now()
        if request.deadline is not None and request.deadline <= now:
            raise AgentRuntimeIntegrationError("deadline expired")
        if request.permission_context.is_expired:
            raise AgentRuntimeIntegrationError("permission context expired")

    def _validate_prompt_injection(
        self, request: IntegratedAgentExecutionRequest
    ) -> None:
        content = request.metadata.get("untrusted_content")
        if content is None:
            return
        try:
            self._security_service.assess_untrusted_content(
                str(content),
                content_id=f"content-{request.execution_id}",
                context=request.permission_context,
            )
        except PromptInjectionBlockedError as exc:
            raise AgentRuntimeIntegrationError(
                "prompt injection blocked",
                failure_mode=IntegrationFailureMode.MANDATORY_FAIL_CLOSED,
            ) from exc

    def _validate_operations(self, request: IntegratedAgentExecutionRequest) -> None:
        if len(request.operations) > request.policy.max_operations:
            raise AgentRuntimeIntegrationError("policy max_operations exceeded")
        for operation in request.operations:
            try:
                self._execution_adapter.registry.resolve(
                    operation.operation_name,
                    operation.operation_version,
                )
            except (
                AgentOperationNotRegisteredError,
                AgentOperationVersionNotRegisteredError,
            ) as exc:
                raise AgentRuntimeIntegrationError(
                    "operation is not registered",
                    failure_mode=IntegrationFailureMode.MANDATORY_FAIL_CLOSED,
                ) from exc

    def _check_permissions(
        self,
        request: IntegratedAgentExecutionRequest,
        agent_id: str,
        run_id: str | None,
    ) -> Any:
        if run_id is None:
            raise AgentRuntimeIntegrationError("agent run is not bound")
        context = self._permission_context_for_run(
            request.permission_context, agent_id, run_id
        )
        operation = request.operations[0] if request.operations else None
        return self._security_service.check_permission(
            PermissionCheckRequest(
                agent_id=agent_id,
                agent_run_id=run_id,
                goal_id=request.goal_id,
                actor_id=request.actor_id,
                operation=operation.operation_name if operation else None,
                domain=operation.operation_name.split(".", 1)[0] if operation else None,
                resources=tuple(
                    str(resource)
                    for values in request.resources.values()
                    for resource in (values if isinstance(values, tuple) else (values,))
                ),
                sensitivity=request.sensitivity,
                required_autonomy_level=request.max_autonomy_level,
            ),
            context=context,
        )

    @staticmethod
    def _permission_context_for_run(
        context: AgentPermissionContext, agent_id: str, run_id: str
    ) -> AgentPermissionContext:
        return replace(
            context,
            agent_id=agent_id,
            agent_run_id=run_id,
            goal_id=context.goal_id,
        )

    def _operation_for_run(
        self, operation: AgentOperationRequest, run_id: str | None
    ) -> AgentOperationRequest:
        if run_id is None:
            raise AgentRuntimeIntegrationError("agent run is not bound")
        data = self._plain(operation.to_dict())
        data.update(
            {
                "agent_run_id": run_id,
                "idempotency_key": (
                    f"{run_id}:{operation.id}:{operation.calculate_fingerprint()}"
                ),
                "created_at": self._now().isoformat(),
            }
        )
        return AgentOperationRequest.from_dict(data)

    def _ensure_checkpoint(
        self,
        record: IntegrationExecutionRecord,
        request: IntegratedAgentExecutionRequest,
        obs: _ObservabilityContext,
    ) -> tuple[
        IntegrationExecutionRecord, int, tuple[Mapping[str, Any], ...], tuple[str, ...]
    ]:
        """Create a checkpoint before running operations, retrying via recovery.

        Returns ``(record, retry_count, recovery_attempts, errors)``. ``errors``
        is empty on success; a non-empty tuple means recovery was exhausted and
        the caller must fail closed.
        """

        if self._checkpoint_service is None:
            return record, 0, (), ()
        if record.agent_run_id is None:
            raise AgentRuntimeIntegrationError("agent run is not bound")

        creation_request = CheckpointCreationRequest(
            agent_run_id=record.agent_run_id,
            goal_id=request.goal_id,
            workflow_id=request.workflow.workflow_id if request.workflow else "none",
            iteration_id="1",
            name=f"integration-{request.execution_id}",
            transaction_boundary_id=f"txn-{request.execution_id}",
            idempotency_key=f"{request.execution_id}:checkpoint",
        )
        recovery_attempts: list[dict[str, Any]] = []
        attempts = 0
        last_error: Exception | None = None
        span_id = obs.span(request.execution_id, "checkpoint.create")
        while True:
            try:
                outcome = self._checkpoint_service.create_checkpoint(
                    request=creation_request
                )
                checkpoint_id = getattr(outcome, "checkpoint_id", outcome)
                if not isinstance(checkpoint_id, str) or not checkpoint_id:
                    raise AgentRuntimeIntegrationError(
                        "checkpoint service returned no checkpoint_id"
                    )
                record = self._store.update(
                    replace(
                        record, checkpoint_ids=(*record.checkpoint_ids, checkpoint_id)
                    )
                )
                obs.close_span(span_id, success=True)
                obs.telemetry(
                    AgentTelemetryKind.CHECKPOINT_CREATED,
                    agent_id=record.agent_id,
                    agent_run_id=record.agent_run_id,
                    goal_id=request.goal_id,
                    checkpoint_id=checkpoint_id,
                    attempt=attempts + 1,
                )
                return record, attempts, tuple(recovery_attempts), ()
            except Exception as exc:  # noqa: BLE001
                last_error = exc

            recovered = False
            if request.policy.allow_recovery and self._recovery_service is not None:
                obs.telemetry(
                    AgentTelemetryKind.RECOVERY_STARTED,
                    agent_id=record.agent_id,
                    agent_run_id=record.agent_run_id,
                    goal_id=request.goal_id,
                    attempt=attempts + 1,
                )
                obs.event(
                    EventType.RECOVERY_STARTED,
                    request=request,
                    agent_id=record.agent_id,
                    agent_run_id=record.agent_run_id,
                    payload={"attempt": attempts + 1},
                )
                try:
                    recovery_result = self._recovery_service.recover(
                        execution_id=request.execution_id,
                        agent_run_id=record.agent_run_id,
                        goal_id=request.goal_id,
                        error=str(last_error),
                        attempt=attempts + 1,
                    )
                    recovered = self._recovery_succeeded(recovery_result)
                    recovery_attempts.append(
                        {
                            "attempt": attempts + 1,
                            "recovered": recovered,
                            "error": str(last_error),
                        }
                    )
                    obs.telemetry(
                        AgentTelemetryKind.RECOVERY_COMPLETED,
                        agent_id=record.agent_id,
                        agent_run_id=record.agent_run_id,
                        goal_id=request.goal_id,
                        attempt=attempts + 1,
                        outcome=(
                            AgentAuditOutcome.SUCCESS
                            if recovered
                            else AgentAuditOutcome.FAILED
                        ),
                    )
                except Exception as recovery_exc:  # noqa: BLE001
                    recovery_attempts.append(
                        {
                            "attempt": attempts + 1,
                            "recovered": False,
                            "error": str(last_error),
                            "recovery_error": str(recovery_exc),
                        }
                    )
                    obs.event(
                        EventType.RECOVERY_FAILED,
                        request=request,
                        agent_id=record.agent_id,
                        agent_run_id=record.agent_run_id,
                        payload={"attempt": attempts + 1, "error": str(recovery_exc)},
                    )

            attempts += 1
            if not recovered or attempts > request.policy.max_retries:
                obs.close_span(span_id, success=False, error=str(last_error))
                return (
                    record,
                    attempts,
                    tuple(recovery_attempts),
                    (f"checkpoint creation failed: {last_error}",),
                )

    @staticmethod
    def _recovery_succeeded(result: Any) -> bool:
        if isinstance(result, Mapping):
            return bool(result.get("recovered") or result.get("success"))
        return bool(
            getattr(result, "success", False) or getattr(result, "recovered", False)
        )

    def _attempt_delegation(
        self,
        record: IntegrationExecutionRecord,
        request: IntegratedAgentExecutionRequest,
        obs: _ObservabilityContext,
    ) -> tuple[IntegrationExecutionRecord, tuple[Mapping[str, Any], ...]]:
        """Propose a delegation when the request's policy allows it.

        Delegation is a supplementary action: a rejected or failed proposal is
        recorded as a visible warning but does not fail the whole execution.
        """

        policy = request.delegation_policy
        target_agent_id = policy.get("target_agent_id")
        if (
            not policy.get("allowed")
            or not target_agent_id
            or self._delegation_service is None
        ):
            return record, ()

        try:
            proposal = DelegationProposal(
                parent_goal_id=request.goal_id,
                target_agent_id=str(target_agent_id),
                child_goal_kind=GoalKind(
                    policy.get("child_goal_kind", GoalKind.INFORMATION.value)
                ),
                child_goal_title=f"Delegated from {request.execution_id}",
                child_goal_description=(
                    f"Delegation proposed by integration execution {request.execution_id}"
                ),
                expected_result={},
                source_agent_id=record.agent_id,
                source_agent_run_id=record.agent_run_id,
                depth=int(policy.get("depth", 0)),
                correlation_id=request.correlation_id,
            )
            delegated = self._delegation_service.propose(proposal)
        except Exception as exc:  # noqa: BLE001
            obs.warnings.append(f"delegation proposal failed: {exc}")
            return record, ()

        record = self._store.append_compensation(
            record.execution_id,
            IntegrationCompensation(
                compensation_id=f"comp-{request.execution_id}-delegation-{delegated.id}",
                execution_id=request.execution_id,
                action="delegation.cancel",
                target_id=delegated.id,
                failure_mode=IntegrationFailureMode.MANDATORY_WITH_COMPENSATION,
                created_at=self._now(),
            ),
        )
        record = self._store.update(
            replace(record, delegation_ids=(*record.delegation_ids, delegated.id))
        )
        obs.telemetry(
            AgentTelemetryKind.DELEGATION_PROPOSED,
            agent_id=record.agent_id,
            agent_run_id=record.agent_run_id,
            goal_id=request.goal_id,
            delegation_id=delegated.id,
        )
        delegation_payload = {
            "delegation_id": delegated.id,
            "parent_goal_id": delegated.parent_goal_id,
            "child_goal_id": delegated.child_goal_id,
            "source_agent_id": delegated.source_agent_id,
            "target_agent_id": delegated.target_agent_id,
            "status": delegated.status.value,
        }
        return record, (delegation_payload,)

    def _execute_compensation(self, compensation: IntegrationCompensation) -> None:
        if compensation.action == "runtime.cancel_run":
            if compensation.target_id is not None:
                self._runtime_loop.cancel(
                    compensation.target_id,
                    reason_codes=("integration.compensation",),
                )
            return
        if compensation.action == "budget.release":
            if compensation.target_id is not None and self._budget_service is not None:
                self._budget_service.release(
                    compensation.target_id, reason="integration.compensation"
                )
            return
        if compensation.action == "delegation.cancel":
            if (
                compensation.target_id is not None
                and self._delegation_service is not None
            ):
                self._delegation_service.cancel(
                    compensation.target_id, reason="integration.compensation"
                )
            return
        raise AgentRuntimeIntegrationError(
            f"unknown compensation action {compensation.action!r}"
        )

    def _run_compensations(self, execution_id: str) -> tuple[str, ...]:
        """Run pending compensations LIFO, idempotently. Never orphans silently."""

        warnings: list[str] = []
        for compensation in self._store.list_pending_compensations(execution_id):
            resolved = True
            try:
                self._execute_compensation(compensation)
            except _IDEMPOTENT_COMPENSATION_ERRORS:
                resolved = True
            except Exception as exc:  # noqa: BLE001
                resolved = False
                warnings.append(
                    f"compensation {compensation.compensation_id} "
                    f"({compensation.action}) failed: {exc}"
                )
            if resolved:
                self._store.mark_compensation_completed(
                    execution_id, compensation.compensation_id
                )
        return tuple(warnings)

    def _reserve_budget(
        self,
        record: IntegrationExecutionRecord,
        request: IntegratedAgentExecutionRequest,
    ) -> Any | None:
        if self._budget_service is None or request.budget_id is None:
            return None
        if record.agent_run_id is None:
            raise AgentRuntimeIntegrationError("agent run is not bound")
        try:
            self._budget_service.get_budget(request.budget_id)
        except KeyError:
            self._budget_service.create_budget(
                record.agent_run_id,
                {BudgetResourceType.OPERATION: max(len(request.operations), 1)},
                budget_id=request.budget_id,
                created_at=self._now(),
            )
        reservation = self._budget_service.reserve(
            request.budget_id,
            [
                BudgetAllocation(
                    BudgetResourceType.OPERATION, max(len(request.operations), 1)
                )
            ],
            workflow_id=request.workflow.workflow_id if request.workflow else None,
            idempotency_key=f"{request.execution_id}:budget-reserve",
            reservation_id=f"reservation-{request.execution_id}",
        )
        self._store.append_compensation(
            record.execution_id,
            IntegrationCompensation(
                compensation_id=f"comp-{request.execution_id}-budget-release",
                execution_id=request.execution_id,
                action="budget.release",
                target_id=reservation.id,
                failure_mode=IntegrationFailureMode.MANDATORY_WITH_COMPENSATION,
                created_at=self._now(),
            ),
        )
        return reservation

    def _confirm_budget(self, reservation: Any | None) -> str | None:
        if reservation is None or self._budget_service is None:
            return None
        consumption = self._budget_service.confirm(reservation.id)
        return consumption.id

    @classmethod
    def _plain(cls, value: Any) -> Any:
        if isinstance(value, MappingProxyType):
            return {str(key): cls._plain(item) for key, item in value.items()}
        if isinstance(value, Mapping):
            return {str(key): cls._plain(item) for key, item in value.items()}
        if isinstance(value, tuple | list):
            return [cls._plain(item) for item in value]
        return value

    def _record_memory(
        self, request: IntegratedAgentExecutionRequest, operation_results: list[Any]
    ) -> tuple[str, ...]:
        if self._memory_service is None:
            return ()
        memory_ids = []
        for result in operation_results:
            if getattr(result, "success", False):
                memory_ids.append(
                    self._memory_service.record_execution_result(
                        execution_id=request.execution_id,
                        request_id=request.request_id,
                        operation_result_id=result.id,
                    )
                )
        return tuple(memory_ids)

    def _requires_approval(self, request: IntegratedAgentExecutionRequest) -> bool:
        return bool(request.metadata.get("requires_approval"))

    def _paused_result(
        self, record: IntegrationExecutionRecord
    ) -> IntegratedAgentExecutionResult:
        if record.result is not None:
            return record.result
        request = self._require_request(record)
        return IntegratedAgentExecutionResult(
            execution_id=record.execution_id,
            request_id=record.request_id,
            goal_id=record.goal_id,
            agent_id=record.agent_id,
            agent_version=record.agent_version,
            agent_run_id=record.agent_run_id,
            final_state=record.state,
            approval_ids=record.pending_approval_ids,
            created_at=request.created_at,
        )

    def _ensure_same_request(
        self,
        record: IntegrationExecutionRecord,
        request: IntegratedAgentExecutionRequest,
    ) -> None:
        if record.request != request:
            raise IntegrationIdempotencyConflictError(
                "request_id already exists with different payload"
            )

    def _require_record(self, execution_id: str) -> IntegrationExecutionRecord:
        record = self._store.get(execution_id)
        if record is None:
            raise AgentRuntimeIntegrationError(f"execution {execution_id!r} not found")
        return record

    @staticmethod
    def _require_request(
        record: IntegrationExecutionRecord,
    ) -> IntegratedAgentExecutionRequest:
        if record.request is None:
            raise AgentRuntimeIntegrationError("execution record has no request")
        return record.request

    @staticmethod
    def _run_id(execution_id: str) -> str:
        return f"run-{execution_id}"

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)
