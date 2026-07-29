"""Protocol-backed in-memory store for Phase 9.26 observability."""

from __future__ import annotations

import threading
from datetime import datetime
from typing import Any, Protocol, TypeVar, runtime_checkable

from cmm.agent_runtime.agent_observability_contracts import (
    AgentAuditRecord,
    AgentHealthReport,
    AgentMetricPoint,
    AgentModelInvocationRecord,
    AgentObservabilityTraceRecord,
    AgentRunMetrics,
    AgentRuntimeMetrics,
    AgentSpan,
    AgentTelemetryRecord,
    _utc,
)
from cmm.agent_runtime.agent_observability_enums import (
    AgentAuditOutcome,
    AgentAuditSeverity,
    AgentMetricKind,
    AgentTelemetryKind,
)
from cmm.agent_runtime.agent_observability_errors import (
    AgentObservabilityAppendOnlyError,
    AgentObservabilityDuplicateError,
    AgentObservabilityNotFoundError,
    AgentObservabilityQueryError,
)
from cmm.agent_runtime.agent_trace_repository import (
    AgentTraceRepository,
    InMemoryAgentTraceRepository,
)
from cmm.agent_runtime.errors import AgentTraceNotFoundError

RecordT = TypeVar("RecordT")


@runtime_checkable
class AgentObservabilityStore(Protocol):
    """Storage boundary for Agent Runtime observability adapters."""

    @property
    def trace_repository(self) -> AgentTraceRepository: ...

    def add_telemetry(self, record: AgentTelemetryRecord) -> None: ...

    def get_telemetry(self, record_id: str) -> AgentTelemetryRecord: ...

    def update_telemetry(self, record: AgentTelemetryRecord) -> None: ...

    def delete_telemetry(self, record_id: str) -> None: ...

    def list_telemetry(
        self,
        *,
        agent_id: str | None = None,
        agent_run_id: str | None = None,
        goal_id: str | None = None,
        operation_id: str | None = None,
        kind: AgentTelemetryKind | str | None = None,
        outcome: AgentAuditOutcome | str | None = None,
        severity: AgentAuditSeverity | str | None = None,
        trace_id: str | None = None,
        span_id: str | None = None,
        correlation_id: str | None = None,
        causation_id: str | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> tuple[AgentTelemetryRecord, ...]: ...

    def add_metric(self, point: AgentMetricPoint) -> None: ...

    def get_metric(self, point_id: str) -> AgentMetricPoint: ...

    def update_metric(self, point: AgentMetricPoint) -> None: ...

    def delete_metric(self, point_id: str) -> None: ...

    def list_metrics(
        self,
        *,
        agent_id: str | None = None,
        agent_run_id: str | None = None,
        goal_id: str | None = None,
        operation_id: str | None = None,
        kind: AgentMetricKind | str | None = None,
        trace_id: str | None = None,
        correlation_id: str | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> tuple[AgentMetricPoint, ...]: ...

    def add_span(self, span: AgentSpan) -> None: ...

    def get_span(self, span_id: str) -> AgentSpan: ...

    def update_span(self, span: AgentSpan) -> None: ...

    def delete_span(self, span_id: str) -> None: ...

    def list_spans(
        self,
        *,
        trace_id: str | None = None,
        parent_span_id: str | None = None,
        agent_run_id: str | None = None,
        goal_id: str | None = None,
        operation_id: str | None = None,
        status: str | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> tuple[AgentSpan, ...]: ...

    def add_trace(self, trace: Any) -> Any: ...

    def get_trace(self, trace_id: str) -> Any: ...

    def update_trace(self, trace: Any) -> Any: ...

    def delete_trace(self, trace_id: str) -> None: ...

    def add_trace_record(self, record: AgentObservabilityTraceRecord) -> None: ...

    def get_trace_record(self, record_id: str) -> AgentObservabilityTraceRecord: ...

    def get_trace_record_by_trace(
        self, trace_id: str
    ) -> AgentObservabilityTraceRecord: ...

    def update_trace_record(self, record: AgentObservabilityTraceRecord) -> None: ...

    def delete_trace_record(self, record_id: str) -> None: ...

    def list_trace_records(
        self,
        *,
        trace_id: str | None = None,
        agent_run_id: str | None = None,
        goal_id: str | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> tuple[AgentObservabilityTraceRecord, ...]: ...

    def add_audit(self, record: AgentAuditRecord) -> None: ...

    def get_audit(self, record_id: str) -> AgentAuditRecord: ...

    def update_audit(self, record: AgentAuditRecord) -> None: ...

    def delete_audit(self, record_id: str) -> None: ...

    def list_audits(
        self,
        *,
        agent_id: str | None = None,
        agent_run_id: str | None = None,
        goal_id: str | None = None,
        operation_id: str | None = None,
        outcome: AgentAuditOutcome | str | None = None,
        severity: AgentAuditSeverity | str | None = None,
        actor_id: str | None = None,
        resource_id: str | None = None,
        trace_id: str | None = None,
        span_id: str | None = None,
        correlation_id: str | None = None,
        causation_id: str | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> tuple[AgentAuditRecord, ...]: ...

    def add_model_invocation(self, record: AgentModelInvocationRecord) -> None: ...

    def get_model_invocation(self, record_id: str) -> AgentModelInvocationRecord: ...

    def update_model_invocation(self, record: AgentModelInvocationRecord) -> None: ...

    def delete_model_invocation(self, record_id: str) -> None: ...

    def list_model_invocations(
        self,
        *,
        agent_run_id: str | None = None,
        goal_id: str | None = None,
        operation_id: str | None = None,
        trace_id: str | None = None,
        correlation_id: str | None = None,
        provider: str | None = None,
        model: str | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> tuple[AgentModelInvocationRecord, ...]: ...

    def add_run_metrics(self, record: AgentRunMetrics) -> None: ...

    def get_run_metrics(self, record_id: str) -> AgentRunMetrics: ...

    def update_run_metrics(self, record: AgentRunMetrics) -> None: ...

    def delete_run_metrics(self, record_id: str) -> None: ...

    def list_run_metrics(
        self,
        *,
        agent_run_id: str | None = None,
        agent_id: str | None = None,
        goal_id: str | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> tuple[AgentRunMetrics, ...]: ...

    def add_runtime_metrics(self, record: AgentRuntimeMetrics) -> None: ...

    def get_runtime_metrics(self, record_id: str) -> AgentRuntimeMetrics: ...

    def update_runtime_metrics(self, record: AgentRuntimeMetrics) -> None: ...

    def delete_runtime_metrics(self, record_id: str) -> None: ...

    def list_runtime_metrics(
        self,
        *,
        start: datetime | None = None,
        end: datetime | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> tuple[AgentRuntimeMetrics, ...]: ...

    def add_health_report(self, record: AgentHealthReport) -> None: ...

    def get_health_report(self, record_id: str) -> AgentHealthReport: ...

    def update_health_report(self, record: AgentHealthReport) -> None: ...

    def delete_health_report(self, record_id: str) -> None: ...

    def list_health_reports(
        self,
        *,
        start: datetime | None = None,
        end: datetime | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> tuple[AgentHealthReport, ...]: ...

    def clear(self) -> None: ...


class InMemoryAgentObservabilityStore:
    """Thread-safe per-instance in-memory observability store."""

    _MAX_LIMIT = 1000

    def __init__(self, trace_repository: AgentTraceRepository | None = None) -> None:
        self._lock = threading.RLock()
        self._trace_repository = trace_repository or InMemoryAgentTraceRepository()
        self._telemetry: dict[str, AgentTelemetryRecord] = {}
        self._metrics: dict[str, AgentMetricPoint] = {}
        self._spans: dict[str, AgentSpan] = {}
        self._trace_records: dict[str, AgentObservabilityTraceRecord] = {}
        self._audits: dict[str, AgentAuditRecord] = {}
        self._model_invocations: dict[str, AgentModelInvocationRecord] = {}
        self._run_metrics: dict[str, AgentRunMetrics] = {}
        self._runtime_metrics: dict[str, AgentRuntimeMetrics] = {}
        self._health_reports: dict[str, AgentHealthReport] = {}
        self._indexes: dict[str, dict[str, dict[str, set[str]]]] = {}

    @property
    def trace_repository(self) -> AgentTraceRepository:
        return self._trace_repository

    @staticmethod
    def _record_id(record: Any) -> str:
        return str(getattr(record, "id", getattr(record, "span_id", "")))

    @staticmethod
    def _timestamp(record: Any) -> datetime:
        for name in ("timestamp", "started_at", "created_at", "updated_at"):
            value = getattr(record, name, None)
            if isinstance(value, datetime):
                return value
        raise AgentObservabilityQueryError("record has no deterministic timestamp")

    @classmethod
    def _validate_page(cls, offset: int, limit: int) -> None:
        if isinstance(offset, bool) or not isinstance(offset, int) or offset < 0:
            raise AgentObservabilityQueryError("offset must be >= 0")
        if (
            isinstance(limit, bool)
            or not isinstance(limit, int)
            or limit < 1
            or limit > cls._MAX_LIMIT
        ):
            raise AgentObservabilityQueryError(
                f"limit must be between 1 and {cls._MAX_LIMIT}"
            )

    @staticmethod
    def _index_values(record: Any) -> dict[str, tuple[str, ...]]:
        values: dict[str, tuple[str, ...]] = {}
        for name in (
            "agent_id",
            "agent_run_id",
            "goal_id",
            "operation_id",
            "trace_id",
            "span_id",
            "parent_span_id",
            "correlation_id",
            "causation_id",
            "actor_id",
            "provider",
            "model",
        ):
            value = getattr(record, name, None)
            if value:
                values[name] = (str(value),)
        for name in ("kind", "outcome", "severity", "status"):
            value = getattr(record, name, None)
            if value is not None:
                values[name] = (str(getattr(value, "value", value)),)
        resources = getattr(record, "resource_ids", ())
        if resources:
            values["resource_id"] = tuple(str(item) for item in resources)
        return values

    def _add_indexes(self, family: str, record: Any) -> None:
        record_id = self._record_id(record)
        family_indexes = self._indexes.setdefault(family, {})
        for field_name, values in self._index_values(record).items():
            field_index = family_indexes.setdefault(field_name, {})
            for value in values:
                field_index.setdefault(value, set()).add(record_id)

    def _remove_indexes(self, family: str, record: Any) -> None:
        record_id = self._record_id(record)
        family_indexes = self._indexes.get(family, {})
        for field_name, values in self._index_values(record).items():
            field_index = family_indexes.get(field_name, {})
            for value in values:
                ids = field_index.get(value)
                if ids is None:
                    continue
                ids.discard(record_id)
                if not ids:
                    field_index.pop(value, None)

    def _add(self, family: str, target: dict[str, RecordT], record: RecordT) -> None:
        record_id = self._record_id(record)
        with self._lock:
            if record_id in target:
                raise AgentObservabilityDuplicateError(f"duplicate {family} identifier")
            target[record_id] = record
            self._add_indexes(family, record)

    def _get(self, family: str, target: dict[str, RecordT], record_id: str) -> RecordT:
        with self._lock:
            try:
                return target[record_id]
            except KeyError as exc:
                raise AgentObservabilityNotFoundError(
                    f"{family} record not found"
                ) from exc

    def _update(self, family: str, target: dict[str, RecordT], record: RecordT) -> None:
        record_id = self._record_id(record)
        with self._lock:
            if record_id not in target:
                raise AgentObservabilityNotFoundError(f"{family} record not found")
            previous = target[record_id]
            self._remove_indexes(family, previous)
            target[record_id] = record
            self._add_indexes(family, record)

    def _delete(self, family: str, target: dict[str, RecordT], record_id: str) -> None:
        with self._lock:
            if record_id not in target:
                raise AgentObservabilityNotFoundError(f"{family} record not found")
            previous = target.pop(record_id)
            self._remove_indexes(family, previous)

    def _list(
        self,
        target: dict[str, RecordT],
        *,
        start: datetime | None = None,
        end: datetime | None = None,
        offset: int = 0,
        limit: int = 100,
        filters: dict[str, Any] | None = None,
    ) -> tuple[RecordT, ...]:
        self._validate_page(offset, limit)
        if start is not None:
            start = _utc(start, "start")
        if end is not None:
            end = _utc(end, "end")
        if start is not None and end is not None and end < start:
            raise AgentObservabilityQueryError("end cannot be before start")
        active_filters = {
            name: getattr(value, "value", value)
            for name, value in (filters or {}).items()
            if value is not None
        }
        with self._lock:
            records = tuple(target.values())
        matched: list[RecordT] = []
        for record in records:
            timestamp = self._timestamp(record)
            if start is not None and timestamp < start:
                continue
            if end is not None and timestamp > end:
                continue
            accepted = True
            for name, expected in active_filters.items():
                if name == "resource_id":
                    if expected not in getattr(record, "resource_ids", ()):
                        accepted = False
                        break
                    continue
                actual = getattr(record, name, None)
                actual = getattr(actual, "value", actual)
                if actual != expected:
                    accepted = False
                    break
            if accepted:
                matched.append(record)
        matched.sort(key=lambda item: (self._timestamp(item), self._record_id(item)))
        return tuple(matched[offset : offset + limit])

    # Telemetry
    def add_telemetry(self, record: AgentTelemetryRecord) -> None:
        self._add("telemetry", self._telemetry, record)

    def get_telemetry(self, record_id: str) -> AgentTelemetryRecord:
        return self._get("telemetry", self._telemetry, record_id)

    def update_telemetry(self, record: AgentTelemetryRecord) -> None:
        self._update("telemetry", self._telemetry, record)

    def delete_telemetry(self, record_id: str) -> None:
        self._delete("telemetry", self._telemetry, record_id)

    def list_telemetry(
        self,
        *,
        agent_id: str | None = None,
        agent_run_id: str | None = None,
        goal_id: str | None = None,
        operation_id: str | None = None,
        kind: AgentTelemetryKind | str | None = None,
        outcome: AgentAuditOutcome | str | None = None,
        severity: AgentAuditSeverity | str | None = None,
        trace_id: str | None = None,
        span_id: str | None = None,
        correlation_id: str | None = None,
        causation_id: str | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> tuple[AgentTelemetryRecord, ...]:
        return self._list(
            self._telemetry,
            start=start,
            end=end,
            offset=offset,
            limit=limit,
            filters={
                "agent_id": agent_id,
                "agent_run_id": agent_run_id,
                "goal_id": goal_id,
                "operation_id": operation_id,
                "kind": kind,
                "outcome": outcome,
                "severity": severity,
                "trace_id": trace_id,
                "span_id": span_id,
                "correlation_id": correlation_id,
                "causation_id": causation_id,
            },
        )

    # Metric points
    def add_metric(self, point: AgentMetricPoint) -> None:
        self._add("metric", self._metrics, point)

    def get_metric(self, point_id: str) -> AgentMetricPoint:
        return self._get("metric", self._metrics, point_id)

    def update_metric(self, point: AgentMetricPoint) -> None:
        self._update("metric", self._metrics, point)

    def delete_metric(self, point_id: str) -> None:
        self._delete("metric", self._metrics, point_id)

    def list_metrics(
        self,
        *,
        agent_id: str | None = None,
        agent_run_id: str | None = None,
        goal_id: str | None = None,
        operation_id: str | None = None,
        kind: AgentMetricKind | str | None = None,
        trace_id: str | None = None,
        correlation_id: str | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> tuple[AgentMetricPoint, ...]:
        return self._list(
            self._metrics,
            start=start,
            end=end,
            offset=offset,
            limit=limit,
            filters={
                "agent_id": agent_id,
                "agent_run_id": agent_run_id,
                "goal_id": goal_id,
                "operation_id": operation_id,
                "kind": kind,
                "trace_id": trace_id,
                "correlation_id": correlation_id,
            },
        )

    # Spans
    def add_span(self, span: AgentSpan) -> None:
        self._add("span", self._spans, span)

    def get_span(self, span_id: str) -> AgentSpan:
        return self._get("span", self._spans, span_id)

    def update_span(self, span: AgentSpan) -> None:
        self._update("span", self._spans, span)

    def delete_span(self, span_id: str) -> None:
        self._delete("span", self._spans, span_id)

    def list_spans(
        self,
        *,
        trace_id: str | None = None,
        parent_span_id: str | None = None,
        agent_run_id: str | None = None,
        goal_id: str | None = None,
        operation_id: str | None = None,
        status: str | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> tuple[AgentSpan, ...]:
        return self._list(
            self._spans,
            start=start,
            end=end,
            offset=offset,
            limit=limit,
            filters={
                "trace_id": trace_id,
                "parent_span_id": parent_span_id,
                "agent_run_id": agent_run_id,
                "goal_id": goal_id,
                "operation_id": operation_id,
                "status": status,
            },
        )

    # Canonical traces and composition records
    def add_trace(self, trace: Any) -> Any:
        with self._lock:
            try:
                self._trace_repository.get(trace.trace_id)
            except AgentTraceNotFoundError:
                return self._trace_repository.save(trace)
            raise AgentObservabilityDuplicateError(
                "duplicate canonical trace identifier"
            )

    def get_trace(self, trace_id: str) -> Any:
        try:
            return self._trace_repository.get(trace_id)
        except AgentTraceNotFoundError as exc:
            raise AgentObservabilityNotFoundError("canonical trace not found") from exc

    def update_trace(self, trace: Any) -> Any:
        self.get_trace(trace.trace_id)
        return self._trace_repository.save(trace)

    def delete_trace(self, trace_id: str) -> None:
        self.get_trace(trace_id)
        self._trace_repository.delete(trace_id)

    def add_trace_record(self, record: AgentObservabilityTraceRecord) -> None:
        self._add("trace_record", self._trace_records, record)

    def get_trace_record(self, record_id: str) -> AgentObservabilityTraceRecord:
        return self._get("trace_record", self._trace_records, record_id)

    def get_trace_record_by_trace(self, trace_id: str) -> AgentObservabilityTraceRecord:
        records = self.list_trace_records(trace_id=trace_id)
        if not records:
            raise AgentObservabilityNotFoundError("trace record not found")
        return records[0]

    def update_trace_record(self, record: AgentObservabilityTraceRecord) -> None:
        self._update("trace_record", self._trace_records, record)

    def delete_trace_record(self, record_id: str) -> None:
        self._delete("trace_record", self._trace_records, record_id)

    def list_trace_records(
        self,
        *,
        trace_id: str | None = None,
        agent_run_id: str | None = None,
        goal_id: str | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> tuple[AgentObservabilityTraceRecord, ...]:
        records = self._list(
            self._trace_records,
            start=start,
            end=end,
            offset=0,
            limit=self._MAX_LIMIT,
            filters={"trace_id": trace_id},
        )
        filtered = tuple(
            record
            for record in records
            if (agent_run_id is None or record.trace.agent_run_id == agent_run_id)
            and (goal_id is None or record.trace.goal_id == goal_id)
        )
        self._validate_page(offset, limit)
        return filtered[offset : offset + limit]

    # Append-only audits
    def add_audit(self, record: AgentAuditRecord) -> None:
        self._add("audit", self._audits, record)

    def get_audit(self, record_id: str) -> AgentAuditRecord:
        return self._get("audit", self._audits, record_id)

    def update_audit(self, record: AgentAuditRecord) -> None:
        raise AgentObservabilityAppendOnlyError("audit records are append-only")

    def delete_audit(self, record_id: str) -> None:
        self._delete("audit", self._audits, record_id)

    def list_audits(
        self,
        *,
        agent_id: str | None = None,
        agent_run_id: str | None = None,
        goal_id: str | None = None,
        operation_id: str | None = None,
        outcome: AgentAuditOutcome | str | None = None,
        severity: AgentAuditSeverity | str | None = None,
        actor_id: str | None = None,
        resource_id: str | None = None,
        trace_id: str | None = None,
        span_id: str | None = None,
        correlation_id: str | None = None,
        causation_id: str | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> tuple[AgentAuditRecord, ...]:
        return self._list(
            self._audits,
            start=start,
            end=end,
            offset=offset,
            limit=limit,
            filters={
                "agent_id": agent_id,
                "agent_run_id": agent_run_id,
                "goal_id": goal_id,
                "operation_id": operation_id,
                "outcome": outcome,
                "severity": severity,
                "actor_id": actor_id,
                "resource_id": resource_id,
                "trace_id": trace_id,
                "span_id": span_id,
                "correlation_id": correlation_id,
                "causation_id": causation_id,
            },
        )

    # Model invocation records
    def add_model_invocation(self, record: AgentModelInvocationRecord) -> None:
        self._add("model_invocation", self._model_invocations, record)

    def get_model_invocation(self, record_id: str) -> AgentModelInvocationRecord:
        return self._get("model_invocation", self._model_invocations, record_id)

    def update_model_invocation(self, record: AgentModelInvocationRecord) -> None:
        raise AgentObservabilityAppendOnlyError(
            "model invocation records are append-only"
        )

    def delete_model_invocation(self, record_id: str) -> None:
        self._delete("model_invocation", self._model_invocations, record_id)

    def list_model_invocations(
        self,
        *,
        agent_run_id: str | None = None,
        goal_id: str | None = None,
        operation_id: str | None = None,
        trace_id: str | None = None,
        correlation_id: str | None = None,
        provider: str | None = None,
        model: str | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> tuple[AgentModelInvocationRecord, ...]:
        return self._list(
            self._model_invocations,
            start=start,
            end=end,
            offset=offset,
            limit=limit,
            filters={
                "agent_run_id": agent_run_id,
                "goal_id": goal_id,
                "operation_id": operation_id,
                "trace_id": trace_id,
                "correlation_id": correlation_id,
                "provider": provider,
                "model": model,
            },
        )

    # Snapshot families
    def add_run_metrics(self, record: AgentRunMetrics) -> None:
        self._add("run_metrics", self._run_metrics, record)

    def get_run_metrics(self, record_id: str) -> AgentRunMetrics:
        return self._get("run_metrics", self._run_metrics, record_id)

    def update_run_metrics(self, record: AgentRunMetrics) -> None:
        previous = self.get_run_metrics(record.id)
        if previous.timestamp == record.timestamp:
            monotonic = (
                "operations_total",
                "operations_succeeded",
                "operations_failed",
                "retries",
                "approvals",
                "delegations",
                "checkpoints",
                "rollbacks",
                "recoveries",
                "input_tokens",
                "output_tokens",
                "error_count",
            )
            if any(
                getattr(record, name) < getattr(previous, name) for name in monotonic
            ):
                raise AgentObservabilityQueryError(
                    "run metric counters cannot decrease in one snapshot"
                )
        self._update("run_metrics", self._run_metrics, record)

    def delete_run_metrics(self, record_id: str) -> None:
        self._delete("run_metrics", self._run_metrics, record_id)

    def list_run_metrics(
        self,
        *,
        agent_run_id: str | None = None,
        agent_id: str | None = None,
        goal_id: str | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> tuple[AgentRunMetrics, ...]:
        return self._list(
            self._run_metrics,
            start=start,
            end=end,
            offset=offset,
            limit=limit,
            filters={
                "agent_run_id": agent_run_id,
                "agent_id": agent_id,
                "goal_id": goal_id,
            },
        )

    def add_runtime_metrics(self, record: AgentRuntimeMetrics) -> None:
        self._add("runtime_metrics", self._runtime_metrics, record)

    def get_runtime_metrics(self, record_id: str) -> AgentRuntimeMetrics:
        return self._get("runtime_metrics", self._runtime_metrics, record_id)

    def update_runtime_metrics(self, record: AgentRuntimeMetrics) -> None:
        self._update("runtime_metrics", self._runtime_metrics, record)

    def delete_runtime_metrics(self, record_id: str) -> None:
        self._delete("runtime_metrics", self._runtime_metrics, record_id)

    def list_runtime_metrics(
        self,
        *,
        start: datetime | None = None,
        end: datetime | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> tuple[AgentRuntimeMetrics, ...]:
        return self._list(
            self._runtime_metrics,
            start=start,
            end=end,
            offset=offset,
            limit=limit,
        )

    def add_health_report(self, record: AgentHealthReport) -> None:
        self._add("health_report", self._health_reports, record)

    def get_health_report(self, record_id: str) -> AgentHealthReport:
        return self._get("health_report", self._health_reports, record_id)

    def update_health_report(self, record: AgentHealthReport) -> None:
        self._update("health_report", self._health_reports, record)

    def delete_health_report(self, record_id: str) -> None:
        self._delete("health_report", self._health_reports, record_id)

    def list_health_reports(
        self,
        *,
        start: datetime | None = None,
        end: datetime | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> tuple[AgentHealthReport, ...]:
        return self._list(
            self._health_reports,
            start=start,
            end=end,
            offset=offset,
            limit=limit,
        )

    def clear(self) -> None:
        with self._lock:
            for target in (
                self._telemetry,
                self._metrics,
                self._spans,
                self._trace_records,
                self._audits,
                self._model_invocations,
                self._run_metrics,
                self._runtime_metrics,
                self._health_reports,
            ):
                target.clear()
            self._indexes.clear()
            try:
                traces = self._trace_repository.list(limit=self._MAX_LIMIT).items
            except (AttributeError, TypeError):
                traces = ()
            for trace in traces:
                self._trace_repository.delete(trace.trace_id)


__all__ = ["AgentObservabilityStore", "InMemoryAgentObservabilityStore"]
