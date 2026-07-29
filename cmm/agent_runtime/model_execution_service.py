"""Application service for persisted model execution records."""

from __future__ import annotations

import threading
from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Protocol

from .model_execution_contracts import (
    AcceptanceStatus,
    ModelExecutionRecord,
    ModelExecutionStatus,
    is_valid_acceptance_transition,
)
from .model_execution_errors import (
    InvalidModelExecutionRecordError,
    ModelExecutionIdempotencyConflictError,
    ModelExecutionNotFoundError,
)
from .runtime_event_contracts import EventSensitivity
from .runtime_event_errors import (
    AgentRuntimeEventBusClosedError,
    AgentRuntimeEventQueueFullError,
)
from .runtime_event_factory import AgentRuntimeEventFactory
from .runtime_event_types import EventType


class _Repository(Protocol):
    def add(self, record: ModelExecutionRecord) -> ModelExecutionRecord: ...
    def get(self, record_id: str) -> ModelExecutionRecord: ...
    def update(self, record: ModelExecutionRecord) -> ModelExecutionRecord: ...
    def query(self, **filters: object) -> tuple[ModelExecutionRecord, ...]: ...


class _EventBus(Protocol):
    def publish(self, event: object) -> None: ...


class ModelExecutionRecordService:
    def __init__(self, repository: _Repository, *, event_bus: _EventBus | None = None,
                 event_factory: AgentRuntimeEventFactory | None = None) -> None:
        self._repository = repository
        self._event_bus = event_bus
        self._event_factory = event_factory or AgentRuntimeEventFactory()
        self._idempotency: dict[str, tuple[str, str]] = {}
        self._idempotency_lock = threading.RLock()

    def create_record(self, record: ModelExecutionRecord, *, idempotency_key: str | None = None) -> ModelExecutionRecord:
        if idempotency_key:
            fingerprint = record.fingerprint()
            with self._idempotency_lock:
                prior = self._idempotency.get(idempotency_key)
                if prior:
                    if prior[1] != fingerprint:
                        raise ModelExecutionIdempotencyConflictError(idempotency_key)
                    return self._repository.get(prior[0])
                # Hold the lock through persistence.  A key becomes visible only
                # after add() succeeds, so concurrent callers cannot observe an
                # idempotency reference to a record that does not exist.
                created = self._repository.add(record)
                self._idempotency[idempotency_key] = (created.id, fingerprint)
        else:
            created = self._repository.add(record)
        self._emit(EventType.MODEL_EXECUTION_CREATED, created)
        return created

    def complete_record(self, record_id: str, *, actual_cost: Decimal | None = None,
                        latency_ms: int | None = None) -> ModelExecutionRecord:
        current = self._repository.get(record_id)
        if current.execution_status is not ModelExecutionStatus.PENDING:
            return current
        updates: dict[str, Any] = {"execution_status": ModelExecutionStatus.COMPLETED,
                                   "completed_at": datetime.now(timezone.utc)}
        if actual_cost is not None:
            updates["actual_cost"] = actual_cost
        if latency_ms is not None:
            updates["latency_ms"] = latency_ms
        result = self._repository.update(replace(current, **updates))
        self._emit(EventType.MODEL_EXECUTION_COMPLETED, result)
        return result

    def fail_record(self, record_id: str) -> ModelExecutionRecord:
        current = self._repository.get(record_id)
        if current.execution_status is not ModelExecutionStatus.PENDING:
            return current
        result = self._repository.update(replace(current, execution_status=ModelExecutionStatus.FAILED,
                                                  completed_at=datetime.now(timezone.utc)))
        self._emit(EventType.MODEL_EXECUTION_FAILED, result)
        return result

    def cancel_record(self, record_id: str) -> ModelExecutionRecord:
        current = self._repository.get(record_id)
        if current.execution_status is not ModelExecutionStatus.PENDING:
            return current
        result = self._repository.update(replace(current, execution_status=ModelExecutionStatus.CANCELLED,
                                                  completed_at=datetime.now(timezone.utc)))
        self._emit(EventType.MODEL_EXECUTION_CANCELLED, result)
        return result

    def update_acceptance(self, record_id: str, status: AcceptanceStatus | str) -> ModelExecutionRecord:
        current = self._repository.get(record_id)
        try:
            target = status if isinstance(status, AcceptanceStatus) else AcceptanceStatus(status)
        except (TypeError, ValueError) as exc:
            raise InvalidModelExecutionRecordError(f"invalid acceptance status: {status!r}") from exc
        if current.acceptance_status is target:
            return current
        if not is_valid_acceptance_transition(current.acceptance_status, target):
            raise InvalidModelExecutionRecordError(
                f"invalid acceptance transition: {current.acceptance_status} -> {target}"
            )
        result = self._repository.update(replace(current, acceptance_status=target))
        self._emit(EventType.MODEL_EXECUTION_ACCEPTANCE_UPDATED, result)
        return result

    def get_record(self, record_id: str) -> ModelExecutionRecord | None:
        try:
            return self._repository.get(record_id)
        except ModelExecutionNotFoundError:
            return None

    def query_records(self, **filters: object) -> tuple[ModelExecutionRecord, ...]:
        return self._repository.query(**filters)

    def _emit(self, event_type: str, record: ModelExecutionRecord) -> None:
        if self._event_bus is None:
            return
        payload = {"record_id": record.id, "agent_run_id": record.agent_run_id,
                   "operation_id": record.operation_id, "provider_id": record.provider_id,
                   "model_id": record.model_id, "acceptance_status": record.acceptance_status.value,
                   "trace_id": record.trace_id}
        event = self._event_factory.create_event(
            event_type, payload, agent_run_id=record.agent_run_id, goal_id=record.goal_id,
            workflow_id=record.workflow_id, task_id=record.task_id, correlation_id=record.correlation_id,
            causation_id=record.causation_id, sensitivity=EventSensitivity.INTERNAL,
        )
        try:
            self._event_bus.publish(event)
        except (AgentRuntimeEventBusClosedError, AgentRuntimeEventQueueFullError):
            # Event publication is explicitly best-effort; record persistence is authoritative.
            return
