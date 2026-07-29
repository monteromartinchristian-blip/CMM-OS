"""Thread-safe in-memory repository for model execution records."""

from __future__ import annotations

import threading
from collections.abc import Iterable
from enum import Enum
from typing import Protocol, runtime_checkable

from .model_execution_contracts import AcceptanceStatus, ModelExecutionRecord
from .model_execution_errors import (
    InvalidModelExecutionRecordError,
    ModelExecutionDuplicateError,
    ModelExecutionNotFoundError,
)


@runtime_checkable
class ModelExecutionRecordRepository(Protocol):
    def add(self, record: ModelExecutionRecord) -> ModelExecutionRecord: ...
    def get(self, record_id: str) -> ModelExecutionRecord: ...
    def update(self, record: ModelExecutionRecord) -> ModelExecutionRecord: ...
    def query(self, **filters: object) -> tuple[ModelExecutionRecord, ...]: ...


class InMemoryModelExecutionRecordRepository:
    _FILTERS = frozenset(ModelExecutionRecord.__dataclass_fields__)
    _IMMUTABLE_FIELDS = frozenset({
        "id", "agent_run_id", "goal_id", "workflow_id", "task_id", "operation_id",
        "provider_id", "model_id", "model_version", "created_at",
    })

    def __init__(self) -> None:
        self._records: dict[str, ModelExecutionRecord] = {}
        self._lock = threading.RLock()

    def add(self, record: ModelExecutionRecord) -> ModelExecutionRecord:
        with self._lock:
            if record.id in self._records:
                raise ModelExecutionDuplicateError(f"record already exists: {record.id}")
            self._records[record.id] = record
        return record

    add_record = add

    def get(self, record_id: str) -> ModelExecutionRecord:
        with self._lock:
            try:
                return self._records[record_id]
            except KeyError as exc:
                raise ModelExecutionNotFoundError(record_id) from exc

    get_record = get

    def update(self, record: ModelExecutionRecord) -> ModelExecutionRecord:
        with self._lock:
            if record.id not in self._records:
                raise ModelExecutionNotFoundError(record.id)
            current = self._records[record.id]
            if any(getattr(current, name) != getattr(record, name) for name in self._IMMUTABLE_FIELDS):
                raise InvalidModelExecutionRecordError("immutable execution identity cannot change")
            self._records[record.id] = record
        return record

    update_record = update

    def _list(self, values: Iterable[ModelExecutionRecord]) -> tuple[ModelExecutionRecord, ...]:
        return tuple(sorted(values, key=lambda item: (item.created_at, item.id)))

    def query(self, **filters: object) -> tuple[ModelExecutionRecord, ...]:
        unknown = set(filters) - self._FILTERS
        if unknown:
            raise InvalidModelExecutionRecordError(
                f"unknown model execution filters: {', '.join(sorted(unknown))}"
            )
        with self._lock:
            values = tuple(self._records.values())
        normalized = {
            name: self._normalize_filter(name, value)
            for name, value in filters.items() if value is not None
        }
        return self._list(
            record for record in values
            if all(
                (getattr(record, name).value if isinstance(getattr(record, name), Enum) else getattr(record, name)) == value
                for name, value in normalized.items()
            )
        )

    @staticmethod
    def _normalize_filter(name: str, value: object) -> object:
        if isinstance(value, Enum):
            value = value.value
        if name in {"provider_id", "model_id"} and isinstance(value, str):
            return value.strip().lower()
        if name in {"execution_status", "acceptance_status", "content_retention", "privacy_classification"}:
            return value
        return value

    list = query

    def list_by_agent_run(self, agent_run_id: str) -> tuple[ModelExecutionRecord, ...]:
        return self.query(agent_run_id=agent_run_id)

    def list_by_goal(self, goal_id: str) -> tuple[ModelExecutionRecord, ...]:
        return self.query(goal_id=goal_id)

    def list_by_workflow(self, workflow_id: str) -> tuple[ModelExecutionRecord, ...]:
        return self.query(workflow_id=workflow_id)

    def list_by_task(self, task_id: str) -> tuple[ModelExecutionRecord, ...]:
        return self.query(task_id=task_id)

    def list_by_operation(self, operation_id: str) -> tuple[ModelExecutionRecord, ...]:
        return self.query(operation_id=operation_id)

    def list_by_provider(self, provider_id: str) -> tuple[ModelExecutionRecord, ...]:
        return self.query(provider_id=provider_id)

    def list_by_model(self, model_id: str) -> tuple[ModelExecutionRecord, ...]:
        return self.query(model_id=model_id)

    def list_by_acceptance_status(self, status: AcceptanceStatus | str) -> tuple[ModelExecutionRecord, ...]:
        return self.query(acceptance_status=status)

    def list_by_trace(self, trace_id: str) -> tuple[ModelExecutionRecord, ...]:
        return self.query(trace_id=trace_id)

    def list_by_correlation(self, correlation_id: str) -> tuple[ModelExecutionRecord, ...]:
        return self.query(correlation_id=correlation_id)

    def __len__(self) -> int:
        with self._lock:
            return len(self._records)
