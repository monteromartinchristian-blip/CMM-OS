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
from cmm.agent_runtime.cognitive_adapter_contracts import (
    AgentCognitiveRequest,
    AgentCognitiveResult,
)
from cmm.agent_runtime.enums import (
    AgentCognitiveStatus,
    AgentValidationDecision,
    AgentValidationStage,
    BudgetResourceType,
    GoalKind,
    GoalStatus,
    WorkflowPlanChangeReason,
)
from cmm.agent_runtime.errors import (
    AgentOperationNotRegisteredError,
    AgentOperationVersionNotRegisteredError,
    BudgetReservationAlreadyResolvedError,
    InvalidRuntimeContractError,
)
from cmm.agent_runtime.operation_execution_contracts import (
    AgentOperationRequest,
    OperationDescriptor,
)
from cmm.agent_runtime.runtime_event_factory import AgentRuntimeEventFactory
from cmm.agent_runtime.runtime_event_types import EventType
from cmm.agent_runtime.validation_integration_contracts import (
    AgentValidationRequest,
    ValidationExecutionContext,
    ValidationRequirement,
)
from cmm.agent_runtime.workflow_planner_contracts import (
    AgentPlanningRequest,
    AgentReplanningRequest,
    AgentWorkflowOperation,
    AgentWorkflowPlan,
)

_IDEMPOTENT_COMPENSATION_ERRORS: tuple[type[Exception], ...] = (
    InvalidRuntimeContractError,
    BudgetReservationAlreadyResolvedError,
    AgentDelegationInvalidStateTransitionError,
)


def _operation_failure_message(operation: AgentOperationRequest, result: Any) -> str:
    return f"operation {operation.operation_name} failed: {result.reason_codes}"


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
        cognitive_service: Any | None = None,
        planning_service: Any | None = None,
        validation_service: Any | None = None,
        validation_policy_service: Any | None = None,
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
        self._cognitive_service = cognitive_service
        self._planning_service = planning_service
        self._validation_service = validation_service
        self._validation_policy_service = validation_policy_service
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
        self._validate_cognitive_availability(request)

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
        elif record.state is IntegrationExecutionState.WAITING_APPROVAL:
            record = self._store.resume(
                execution_id, IntegrationExecutionState.PLANNING
            )

        operations = request.operations
        validation_results: list[Mapping[str, Any]] = []
        if record.state is IntegrationExecutionState.PLANNING:
            needs_planning = not request.operations and request.workflow is None
            require_cognitive = bool(
                request.policy.metadata.get("require_cognitive", False)
            )
            cognitive_result = None
            if needs_planning or require_cognitive:
                record, cognitive_result = self._run_cognitive_analysis(
                    record, request, obs
                )
                if cognitive_result is not None and self._cognitive_blocks_execution(
                    cognitive_result
                ):
                    obs.complete_trace()
                    return self._save_snapshot(
                        execution_id,
                        IntegrationExecutionState.FAILED,
                        warnings=tuple(obs.warnings),
                        event_ids=tuple(obs.record_ids),
                        errors=self._cognitive_failure_reasons(cognitive_result),
                    )

            try:
                operations, record = self._resolve_operations(
                    record, request, obs, cognitive_result
                )
            except AgentRuntimeIntegrationError as exc:
                compensation_warnings = self._run_compensations(execution_id)
                obs.complete_trace()
                return self._save_snapshot(
                    execution_id,
                    IntegrationExecutionState.FAILED,
                    warnings=tuple(obs.warnings) + compensation_warnings,
                    event_ids=tuple(obs.record_ids),
                    errors=(str(exc),),
                )

            pre_ok, pre_validation = self._run_pre_execution_validation(
                record, request, obs, operations
            )
            if pre_validation:
                validation_results.append(pre_validation)
            if not pre_ok:
                obs.complete_trace()
                return self._save_snapshot(
                    execution_id,
                    IntegrationExecutionState.FAILED,
                    validation_results=tuple(validation_results),
                    warnings=tuple(obs.warnings),
                    event_ids=tuple(obs.record_ids),
                    errors=("pre-execution validation blocked",),
                )

            record = self._store.transition(
                execution_id, IntegrationExecutionState.RUNNING
            )

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
                validation_results=tuple(validation_results),
                warnings=tuple(obs.warnings) + compensation_warnings,
                event_ids=tuple(obs.record_ids),
                errors=checkpoint_errors,
            )

        operation_results: list[Any] = []
        operation_result_ids: list[str] = []
        attempted_operations: list[AgentOperationRequest] = list(operations)
        reservation = self._reserve_budget(
            record, request, operation_count=len(operations)
        )
        if reservation is not None:
            obs.telemetry(
                AgentTelemetryKind.BUDGET_RESERVED,
                agent_id=record.agent_id,
                agent_run_id=record.agent_run_id,
                goal_id=request.goal_id,
            )

        record, failed_operation, failed_result = self._run_operation_batch(
            execution_id,
            record,
            request,
            obs,
            operations,
            operation_results,
            operation_result_ids,
        )
        if failed_operation is not None:
            record, replanned = self._attempt_replan(
                record, request, obs, failed_operation
            )
            if replanned is not None:
                attempted_operations.extend(replanned)
                record, failed_operation, failed_result = self._run_operation_batch(
                    execution_id,
                    record,
                    request,
                    obs,
                    replanned,
                    operation_results,
                    operation_result_ids,
                )

        if failed_operation is not None:
            compensation_warnings = self._run_compensations(execution_id)
            obs.telemetry(
                AgentTelemetryKind.RUN_FAILED,
                agent_id=record.agent_id,
                agent_run_id=record.agent_run_id,
                goal_id=request.goal_id,
                reason_codes=failed_result.reason_codes,
            )
            obs.event(
                EventType.AGENT_RUN_FAILED,
                request=request,
                agent_id=record.agent_id,
                agent_run_id=record.agent_run_id,
                payload={"operation_id": failed_operation.id},
            )
            obs.complete_trace()
            return self._save_snapshot(
                execution_id,
                IntegrationExecutionState.FAILED,
                operation_results=tuple(operation_results),
                operation_request_ids=tuple(item.id for item in attempted_operations),
                checkpoint_ids=record.checkpoint_ids,
                retry_count=retry_count,
                recovery_attempts=recovery_attempts,
                validation_results=tuple(validation_results),
                warnings=tuple(obs.warnings) + compensation_warnings,
                event_ids=tuple(obs.record_ids),
                errors=(_operation_failure_message(failed_operation, failed_result),),
            )

        post_ok, post_validation, commit_validation = (
            self._run_post_execution_validation(record, request, obs, operations)
        )
        if post_validation:
            validation_results.append(post_validation)
        if commit_validation:
            validation_results.append(commit_validation)
        if not post_ok:
            compensation_warnings = self._run_compensations(execution_id)
            obs.telemetry(
                AgentTelemetryKind.RUN_FAILED,
                agent_id=record.agent_id,
                agent_run_id=record.agent_run_id,
                goal_id=request.goal_id,
            )
            obs.event(
                EventType.AGENT_RUN_FAILED,
                request=request,
                agent_id=record.agent_id,
                agent_run_id=record.agent_run_id,
                payload={"reason": "post_execution_validation_blocked"},
            )
            obs.complete_trace()
            return self._save_snapshot(
                execution_id,
                IntegrationExecutionState.FAILED,
                operation_results=tuple(operation_results),
                operation_request_ids=tuple(item.id for item in attempted_operations),
                checkpoint_ids=record.checkpoint_ids,
                retry_count=retry_count,
                recovery_attempts=recovery_attempts,
                validation_results=tuple(validation_results),
                warnings=tuple(obs.warnings) + compensation_warnings,
                event_ids=tuple(obs.record_ids),
                errors=("post-execution validation blocked",),
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
            operation_request_ids=tuple(item.id for item in attempted_operations),
            budget_consumption_ids=(consumption_id,) if consumption_id else (),
            memory_updates=tuple({"id": memory_id} for memory_id in memory_ids),
            checkpoint_ids=record.checkpoint_ids,
            delegations=delegations,
            retry_count=retry_count,
            recovery_attempts=recovery_attempts,
            validation_results=tuple(validation_results),
            warnings=tuple(obs.warnings),
            event_ids=tuple(obs.record_ids),
        )

    def _run_operation_batch(
        self,
        execution_id: str,
        record: IntegrationExecutionRecord,
        request: IntegratedAgentExecutionRequest,
        obs: _ObservabilityContext,
        operations: tuple[AgentOperationRequest, ...],
        operation_results: list[Any],
        operation_result_ids: list[str],
    ) -> tuple[IntegrationExecutionRecord, AgentOperationRequest | None, Any | None]:
        """Execute ``operations`` sequentially, appending to the given lists.

        Returns ``(record, None, None)`` on full success, or
        ``(record, failed_operation, failed_result)`` on the first failure.
        """

        for operation in operations:
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
                return record, prepared, result
        return record, None, None

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
        validation_results: tuple[Mapping[str, Any], ...] = (),
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
            validation_results=validation_results,
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
            metadata=dict(record.metadata),
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
        if (
            not request.operations
            and request.workflow is None
            and self._planning_service is None
        ):
            raise AgentRuntimeIntegrationError(
                "operations or workflow is required when no planning service"
                " is configured",
                failure_mode=IntegrationFailureMode.MANDATORY_FAIL_CLOSED,
            )
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

    def _validate_cognitive_availability(
        self, request: IntegratedAgentExecutionRequest
    ) -> None:
        require_cognitive = bool(
            request.policy.metadata.get("require_cognitive", False)
        )
        if require_cognitive and self._cognitive_service is None:
            raise AgentRuntimeIntegrationError(
                "cognitive service is required by policy but not configured",
                failure_mode=IntegrationFailureMode.MANDATORY_FAIL_CLOSED,
            )

    # ── Cognitive integration (Phase 9.28) ───────────────────────────────────

    def _run_cognitive_analysis(
        self,
        record: IntegrationExecutionRecord,
        request: IntegratedAgentExecutionRequest,
        obs: _ObservabilityContext,
    ) -> tuple[IntegrationExecutionRecord, AgentCognitiveResult | None]:
        """Invoke the Cognitive Layer adapter before planning/execution.

        Persists result id, session/trace references, warnings, gaps,
        questions, contradictions, and confidence into ``record.metadata``
        (which flows into the final result via ``_save_snapshot``). Returns
        ``(record, None)`` when no cognitive service is configured, allowing
        direct execution when the request already carries operations.
        """

        if self._cognitive_service is None:
            return record, None

        cognitive_request = AgentCognitiveRequest(
            agent_run_id=record.agent_run_id or "",
            goal_id=request.goal_id,
            objective=str(request.metadata.get("objective") or request.goal_id),
            actor_id=request.actor_id,
            permissions=(
                request.permission_context.allowed_domains
                if request.permission_context
                else ()
            ),
            metadata={
                "resources": dict(request.resources),
                "cognitive_context": dict(request.cognitive_context),
                "correlation_id": request.correlation_id,
                "causation_id": request.causation_id,
            },
        )
        result = self._cognitive_service.analyze(cognitive_request)

        for warning in result.warnings:
            obs.warnings.append(f"cognitive:{warning.code}: {warning.message}")

        cognitive_summary = {
            "cognitive_result_id": result.id,
            "cognitive_session_id": result.reasoning_session_id,
            "cognitive_trace_id": result.reasoning_trace_id,
            "cognitive_status": result.status.value,
            "cognitive_decision": result.recommended_decision.value,
            "cognitive_confidence": result.confidence,
            "cognitive_gap_count": len(result.information_gaps),
            "cognitive_question_count": len(result.questions),
            "cognitive_contradiction_count": len(result.contradictions),
        }
        record = self._store.update(
            replace(record, metadata={**record.metadata, **cognitive_summary})
        )
        obs.event(
            EventType.COGNITIVE_ANALYSIS_COMPLETED,
            request=request,
            agent_id=record.agent_id,
            agent_run_id=record.agent_run_id,
            payload={"cognitive_result_id": result.id, "status": result.status.value},
        )
        if result.questions:
            obs.event(
                EventType.QUESTION_CREATED,
                request=request,
                agent_id=record.agent_id,
                agent_run_id=record.agent_run_id,
                payload={"count": len(result.questions)},
            )
        if result.information_gaps:
            obs.event(
                EventType.INFORMATION_GAP_DETECTED,
                request=request,
                agent_id=record.agent_id,
                agent_run_id=record.agent_run_id,
                payload={"count": len(result.information_gaps)},
            )
        return record, result

    @staticmethod
    def _cognitive_blocks_execution(result: AgentCognitiveResult) -> bool:
        return result.blocked or result.status in (
            AgentCognitiveStatus.WAITING_FOR_USER,
            AgentCognitiveStatus.WAITING_FOR_RESOURCE,
            AgentCognitiveStatus.INSUFFICIENT_INFORMATION,
            AgentCognitiveStatus.BLOCKED,
            AgentCognitiveStatus.FAILED,
        )

    @staticmethod
    def _cognitive_failure_reasons(result: AgentCognitiveResult) -> tuple[str, ...]:
        if result.errors:
            return tuple(result.errors)
        return (f"cognitive analysis blocked: {result.status.value}",)

    # ── Planner integration (Phase 9.28) ─────────────────────────────────────

    def _build_planning_request(
        self,
        record: IntegrationExecutionRecord,
        request: IntegratedAgentExecutionRequest,
        cognitive_result: AgentCognitiveResult | None,
    ) -> AgentPlanningRequest:
        return AgentPlanningRequest(
            id=f"plan-req-{request.execution_id}",
            goal_id=request.goal_id,
            agent_run_id=record.agent_run_id or "",
            objective=str(request.metadata.get("objective") or request.goal_id),
            cognitive_result_id=cognitive_result.id if cognitive_result else None,
            permissions=(
                list(request.permission_context.allowed_operations)
                if request.permission_context
                else []
            ),
            autonomy_level=request.max_autonomy_level,
            actor_id=request.actor_id,
            metadata={
                "correlation_id": request.correlation_id,
                "causation_id": request.causation_id,
            },
        )

    def _operations_from_workflow_plan(
        self,
        plan: AgentWorkflowPlan,
        record: IntegrationExecutionRecord,
    ) -> tuple[AgentOperationRequest, ...]:
        """Translate a canonical workflow plan into executable operations.

        Task ordering (already a linearization of the plan's dependency
        chain, produced by the Workflow Planner Adapter) is reused as-is;
        no DAG is recomputed here.
        """

        by_id = {operation.id: operation for operation in plan.operations}
        ordered: list[AgentWorkflowOperation] = []
        seen: set[str] = set()
        for task in plan.tasks:
            for operation_id in task.operation_ids:
                operation = by_id.get(operation_id)
                if operation is not None and operation_id not in seen:
                    ordered.append(operation)
                    seen.add(operation_id)
        for operation in plan.operations:
            if operation.id not in seen:
                ordered.append(operation)
                seen.add(operation.id)

        run_id = record.agent_run_id or ""
        now_iso = self._now().isoformat()
        return tuple(
            AgentOperationRequest(
                id=operation.id,
                agent_run_id=run_id,
                workflow_id=plan.workflow_id,
                task_id=operation.task_id,
                operation_name=operation.operation_name,
                idempotency_key=f"{plan.id}:{operation.id}",
                parameters=dict(operation.parameters),
                created_at=now_iso,
            )
            for operation in ordered
        )

    def _resolve_operations(
        self,
        record: IntegrationExecutionRecord,
        request: IntegratedAgentExecutionRequest,
        obs: _ObservabilityContext,
        cognitive_result: AgentCognitiveResult | None,
    ) -> tuple[tuple[AgentOperationRequest, ...], IntegrationExecutionRecord]:
        if request.operations:
            return request.operations, record
        if request.workflow is not None:
            return self._operations_from_workflow_plan(request.workflow, record), record

        if self._planning_service is None:
            raise AgentRuntimeIntegrationError(
                "planning service is required to produce operations for this execution",
                failure_mode=IntegrationFailureMode.MANDATORY_FAIL_CLOSED,
            )

        planning_request = self._build_planning_request(
            record, request, cognitive_result
        )
        plan = self._planning_service.plan(planning_request)
        validation = self._planning_service.validate_plan(
            plan, request=planning_request
        )
        if not validation.is_valid:
            obs.event(
                EventType.WORKFLOW_PLAN_REJECTED,
                request=request,
                agent_id=record.agent_id,
                agent_run_id=record.agent_run_id,
                payload={
                    "plan_id": plan.id,
                    "errors": list(validation.blocking_errors),
                },
            )
            raise AgentRuntimeIntegrationError(
                f"workflow plan is invalid: {list(validation.blocking_errors)}",
                failure_mode=IntegrationFailureMode.MANDATORY_FAIL_CLOSED,
            )

        plan_summary = {
            "plan_id": plan.id,
            "plan_workflow_id": plan.workflow_id,
            "plan_version": plan.version,
            "plan_task_count": len(plan.tasks),
            "plan_dependency_count": len(plan.dependencies),
            "plan_operation_count": len(plan.operations),
            "plan_checkpoint_ids": [checkpoint.id for checkpoint in plan.checkpoints],
            "plan_validation_status": validation.status.value,
        }
        record = self._store.update(
            replace(
                record,
                workflow_id=plan.workflow_id,
                metadata={**record.metadata, **plan_summary},
            )
        )
        obs.event(
            EventType.WORKFLOW_PLAN_CREATED,
            request=request,
            agent_id=record.agent_id,
            agent_run_id=record.agent_run_id,
            payload={"plan_id": plan.id, "workflow_id": plan.workflow_id},
        )
        obs.event(
            EventType.WORKFLOW_PLAN_VALIDATED,
            request=request,
            agent_id=record.agent_id,
            agent_run_id=record.agent_run_id,
            payload={"plan_id": plan.id, "status": validation.status.value},
        )
        return self._operations_from_workflow_plan(plan, record), record

    def _attempt_replan(
        self,
        record: IntegrationExecutionRecord,
        request: IntegratedAgentExecutionRequest,
        obs: _ObservabilityContext,
        failed_operation: AgentOperationRequest,
    ) -> tuple[IntegrationExecutionRecord, tuple[AgentOperationRequest, ...] | None]:
        """Attempt exactly one replan after an operation failure.

        Bounded to a single attempt per execution (via ``replan_count`` in
        ``record.metadata``) to avoid infinite replan loops.
        """

        plan_id = record.metadata.get("plan_id")
        replan_count = int(record.metadata.get("replan_count", 0))
        if (
            plan_id is None
            or self._planning_service is None
            or not request.policy.allow_recovery
            or replan_count >= 1
        ):
            return record, None

        replanning_request = AgentReplanningRequest(
            id=f"replan-{request.execution_id}-{replan_count + 1}",
            plan_id=str(plan_id),
            reason=WorkflowPlanChangeReason.OPERATION_FAILED,
            reason_details=f"operation {failed_operation.operation_name} failed",
            failed_operation_id=failed_operation.id,
        )
        obs.event(
            EventType.RECOVERY_REPLAN_REQUESTED,
            request=request,
            agent_id=record.agent_id,
            agent_run_id=record.agent_run_id,
            payload={
                "plan_id": str(plan_id),
                "failed_operation_id": failed_operation.id,
            },
        )
        try:
            result = self._planning_service.replan(replanning_request)
        except Exception as exc:  # noqa: BLE001
            obs.warnings.append(f"replan failed: {exc}")
            return record, None
        if result.new_plan is None:
            return record, None

        record = self._store.update(
            replace(
                record,
                workflow_id=result.new_plan.workflow_id,
                metadata={
                    **record.metadata,
                    "plan_id": result.new_plan.id,
                    "previous_plan_id": str(plan_id),
                    "plan_version": result.new_plan.version,
                    "replan_count": replan_count + 1,
                },
            )
        )
        obs.event(
            EventType.WORKFLOW_PLAN_REPLANNED,
            request=request,
            agent_id=record.agent_id,
            agent_run_id=record.agent_run_id,
            payload={
                "previous_plan_id": str(plan_id),
                "new_plan_id": result.new_plan.id,
                "version": result.new_plan.version,
            },
        )
        return record, self._operations_from_workflow_plan(result.new_plan, record)

    # ── Validation integration (Phase 9.28) ──────────────────────────────────

    def _primary_operation_descriptor(
        self, operations: tuple[AgentOperationRequest, ...]
    ) -> OperationDescriptor | None:
        if not operations:
            return None
        try:
            return self._execution_adapter.registry.resolve(
                operations[0].operation_name, operations[0].operation_version
            )
        except (
            AgentOperationNotRegisteredError,
            AgentOperationVersionNotRegisteredError,
        ):
            return None

    def _resolve_validation_requirements(
        self,
        request: IntegratedAgentExecutionRequest,
        stage: AgentValidationStage,
        operation_descriptor: OperationDescriptor | None,
        *,
        commit_gate_required: bool = False,
    ) -> tuple[ValidationRequirement, ...]:
        if self._validation_policy_service is None:
            return ()
        selection = self._validation_policy_service.select_policy(
            operation_descriptor=operation_descriptor,
            stage=stage,
            sensitivity=request.sensitivity.value,
            commit_gate_required=commit_gate_required,
        )
        return selection.requirements

    def _run_validation_stage(
        self,
        record: IntegrationExecutionRecord,
        request: IntegratedAgentExecutionRequest,
        obs: _ObservabilityContext,
        operations: tuple[AgentOperationRequest, ...],
        stage: AgentValidationStage,
        *,
        commit_gate_required: bool = False,
    ) -> tuple[bool, dict[str, Any] | None]:
        if self._validation_service is None:
            return True, None
        descriptor = self._primary_operation_descriptor(operations)
        requirements = self._resolve_validation_requirements(
            request, stage, descriptor, commit_gate_required=commit_gate_required
        )
        if not requirements:
            return True, None

        operation = operations[0] if operations else None
        context_data: dict[str, Any] = {}
        policy_name = request.metadata.get("validation_policy_name")
        if policy_name:
            context_data["policy_name"] = policy_name
        project_root = request.metadata.get("validation_project_root")
        if project_root:
            context_data["project_root"] = project_root
        validation_request = AgentValidationRequest(
            id=f"val-{stage.value}-{request.execution_id}",
            run_id=record.agent_run_id or "",
            iteration_id="1",
            operation_request_id=operation.id if operation else request.execution_id,
            stage=stage,
            requirements=requirements,
            idempotency_key=f"{request.execution_id}:{stage.value}",
            context_data=context_data,
        )
        changed_files = tuple(
            str(p) for p in request.resources.get("changed_files", ())
        )
        exec_context = (
            ValidationExecutionContext(
                run_id=record.agent_run_id or "",
                iteration_id="1",
                operation_name=operation.operation_name if operation else "",
                resource_scope=changed_files,
            )
            if changed_files
            else None
        )
        obs.event(
            EventType.VALIDATION_STARTED,
            request=request,
            agent_id=record.agent_id,
            agent_run_id=record.agent_run_id,
            payload={"stage": stage.value},
        )
        result = self._validation_service.validate(
            validation_request, exec_context=exec_context
        )
        obs.event(
            EventType.VALIDATION_COMPLETED
            if result.decision is AgentValidationDecision.CONTINUE
            else EventType.VALIDATION_FAILED,
            request=request,
            agent_id=record.agent_id,
            agent_run_id=record.agent_run_id,
            payload={"stage": stage.value, "decision": result.decision.value},
        )
        return result.decision is AgentValidationDecision.CONTINUE, result.to_dict()

    def _run_pre_execution_validation(
        self,
        record: IntegrationExecutionRecord,
        request: IntegratedAgentExecutionRequest,
        obs: _ObservabilityContext,
        operations: tuple[AgentOperationRequest, ...],
    ) -> tuple[bool, dict[str, Any] | None]:
        return self._run_validation_stage(
            record, request, obs, operations, AgentValidationStage.PRE_EXECUTION
        )

    def _run_post_execution_validation(
        self,
        record: IntegrationExecutionRecord,
        request: IntegratedAgentExecutionRequest,
        obs: _ObservabilityContext,
        operations: tuple[AgentOperationRequest, ...],
    ) -> tuple[bool, dict[str, Any] | None, dict[str, Any] | None]:
        ok, post_dict = self._run_validation_stage(
            record, request, obs, operations, AgentValidationStage.POST_EXECUTION
        )
        if not ok:
            return False, post_dict, None
        if not request.policy.require_terminal_validation:
            return True, post_dict, None
        ok, commit_dict = self._run_validation_stage(
            record, request, obs, operations, AgentValidationStage.PRE_COMMIT
        )
        return ok, post_dict, commit_dict

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
        *,
        operation_count: int | None = None,
    ) -> Any | None:
        if self._budget_service is None or request.budget_id is None:
            return None
        if record.agent_run_id is None:
            raise AgentRuntimeIntegrationError("agent run is not bound")
        count = max(
            operation_count if operation_count is not None else len(request.operations),
            1,
        )
        try:
            self._budget_service.get_budget(request.budget_id)
        except KeyError:
            self._budget_service.create_budget(
                record.agent_run_id,
                {BudgetResourceType.OPERATION: count},
                budget_id=request.budget_id,
                created_at=self._now(),
            )
        reservation = self._budget_service.reserve(
            request.budget_id,
            [BudgetAllocation(BudgetResourceType.OPERATION, count)],
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
