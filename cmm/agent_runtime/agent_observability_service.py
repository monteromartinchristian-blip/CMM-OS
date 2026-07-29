"""Service layer for Phase 9.26 Agent Runtime observability."""

from __future__ import annotations

import hashlib
import json
import math
import uuid
from collections.abc import Callable
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import MappingProxyType
from typing import Any, TypeVar

from cmm.agent_runtime.agent_delegation_enums import DelegationEventType
from cmm.agent_runtime.agent_observability_contracts import (
    AgentAuditRecord,
    AgentHealthReport,
    AgentHealthThresholds,
    AgentMetricPoint,
    AgentModelInvocationRecord,
    AgentObservabilityTraceRecord,
    AgentRunMetrics,
    AgentRuntimeMetrics,
    AgentSpan,
    AgentTelemetryRecord,
    AgentTraceLink,
    AgentTraceMetrics,
    AgentTraceSnapshot,
    _utc,
    sanitize_agent_observability_data,
)
from cmm.agent_runtime.agent_observability_enums import (
    AgentAuditOutcome,
    AgentAuditSeverity,
    AgentHealthStatus,
    AgentTelemetryKind,
)
from cmm.agent_runtime.agent_observability_errors import (
    AgentObservabilityNotFoundError,
    AgentObservabilityTraceFinalizedError,
    InvalidAgentObservabilityContractError,
)
from cmm.agent_runtime.agent_observability_store import (
    AgentObservabilityStore,
    InMemoryAgentObservabilityStore,
)
from cmm.agent_runtime.agent_trace_contracts import AgentTrace
from cmm.agent_runtime.enums import AgentTraceStatus
from cmm.agent_runtime.runtime_event_contracts import AgentRuntimeEvent
from cmm.agent_runtime.runtime_event_types import EVENT_TYPE_CATEGORY_MAP, EventType
from cmm.agent_runtime.runtime_loop_contracts import RuntimeHeartbeat

_EventMapping = tuple[AgentTelemetryKind, AgentAuditOutcome, AgentAuditSeverity]
_RecordT = TypeVar("_RecordT")
_PAGE_SIZE = 1000


def _mapping(
    kind: AgentTelemetryKind,
    outcome: AgentAuditOutcome = AgentAuditOutcome.UNKNOWN,
    severity: AgentAuditSeverity = AgentAuditSeverity.INFO,
) -> _EventMapping:
    return kind, outcome, severity


_EVENT_MAPPING: MappingProxyType[str, _EventMapping] = MappingProxyType(
    {
        **{
            event_type: _mapping(AgentTelemetryKind.CUSTOM)
            for event_type in EVENT_TYPE_CATEGORY_MAP
        },
        **{
            event_type: _mapping(AgentTelemetryKind.CUSTOM, AgentAuditOutcome.SUCCESS)
            for event_type in (
                EventType.AGENT_ITERATION_COMPLETED,
                EventType.OBSERVATION_COMPLETED,
                EventType.KNOWLEDGE_LOADED,
                EventType.COGNITIVE_ANALYSIS_COMPLETED,
                EventType.QUESTION_ANSWERED,
                EventType.WORKFLOW_PLAN_CREATED,
                EventType.WORKFLOW_PLAN_VALIDATED,
                EventType.VALIDATION_COMPLETED,
                EventType.OUTCOME_EVALUATION_COMPLETED,
                EventType.KNOWLEDGE_UPDATE_APPLIED,
                EventType.MEMORY_UPDATE_APPLIED,
                EventType.OPERATIONAL_LESSON_CREATED,
                EventType.AGENT_TRACE_CREATED,
                EventType.AGENT_TRACE_FINALIZED,
            )
        },
        **{
            event_type: _mapping(
                AgentTelemetryKind.CUSTOM,
                AgentAuditOutcome.FAILED,
                AgentAuditSeverity.ERROR,
            )
            for event_type in (
                EventType.AGENT_ITERATION_FAILED,
                EventType.OBSERVATION_FAILED,
                EventType.WORKFLOW_PLAN_REJECTED,
                EventType.VALIDATION_FAILED,
                EventType.RUNTIME_ERROR,
            )
        },
        EventType.RUNTIME_WARNING: _mapping(
            AgentTelemetryKind.CUSTOM,
            AgentAuditOutcome.PARTIAL,
            AgentAuditSeverity.WARNING,
        ),
        EventType.AGENT_RUN_CREATED: _mapping(AgentTelemetryKind.RUN_STARTED),
        EventType.AGENT_RUN_STARTED: _mapping(AgentTelemetryKind.RUN_STARTED),
        EventType.AGENT_RUN_STATUS_CHANGED: _mapping(AgentTelemetryKind.CUSTOM),
        EventType.AGENT_RUN_PAUSED: _mapping(AgentTelemetryKind.RUN_PAUSED),
        EventType.AGENT_RUN_RESUMED: _mapping(AgentTelemetryKind.RUN_RESUMED),
        EventType.AGENT_RUN_CANCELLED: _mapping(
            AgentTelemetryKind.RUN_CANCELLED,
            AgentAuditOutcome.CANCELLED,
            AgentAuditSeverity.NOTICE,
        ),
        EventType.AGENT_RUN_COMPLETED: _mapping(
            AgentTelemetryKind.RUN_COMPLETED, AgentAuditOutcome.SUCCESS
        ),
        EventType.AGENT_RUN_FAILED: _mapping(
            AgentTelemetryKind.RUN_FAILED,
            AgentAuditOutcome.FAILED,
            AgentAuditSeverity.ERROR,
        ),
        EventType.GOAL_CREATED: _mapping(AgentTelemetryKind.GOAL_CREATED),
        EventType.GOAL_UPDATED: _mapping(AgentTelemetryKind.GOAL_UPDATED),
        EventType.GOAL_PRIORITIZED: _mapping(AgentTelemetryKind.GOAL_UPDATED),
        EventType.GOAL_BLOCKED: _mapping(
            AgentTelemetryKind.GOAL_UPDATED,
            AgentAuditOutcome.PARTIAL,
            AgentAuditSeverity.WARNING,
        ),
        EventType.GOAL_PAUSED: _mapping(AgentTelemetryKind.GOAL_UPDATED),
        EventType.GOAL_RESUMED: _mapping(AgentTelemetryKind.GOAL_UPDATED),
        EventType.GOAL_CANCELLED: _mapping(
            AgentTelemetryKind.GOAL_UPDATED, AgentAuditOutcome.CANCELLED
        ),
        EventType.GOAL_COMPLETED: _mapping(
            AgentTelemetryKind.GOAL_COMPLETED, AgentAuditOutcome.SUCCESS
        ),
        EventType.GOAL_FAILED: _mapping(
            AgentTelemetryKind.GOAL_UPDATED,
            AgentAuditOutcome.FAILED,
            AgentAuditSeverity.ERROR,
        ),
        EventType.OPERATION_STARTED: _mapping(AgentTelemetryKind.OPERATION_STARTED),
        EventType.OPERATION_COMPLETED: _mapping(
            AgentTelemetryKind.OPERATION_COMPLETED, AgentAuditOutcome.SUCCESS
        ),
        EventType.OPERATION_FAILED: _mapping(
            AgentTelemetryKind.OPERATION_FAILED,
            AgentAuditOutcome.FAILED,
            AgentAuditSeverity.ERROR,
        ),
        EventType.APPROVAL_REQUESTED: _mapping(
            AgentTelemetryKind.APPROVAL_REQUESTED,
            severity=AgentAuditSeverity.NOTICE,
        ),
        EventType.APPROVAL_APPROVED: _mapping(
            AgentTelemetryKind.APPROVAL_RESOLVED, AgentAuditOutcome.SUCCESS
        ),
        EventType.APPROVAL_REJECTED: _mapping(
            AgentTelemetryKind.APPROVAL_RESOLVED,
            AgentAuditOutcome.DENIED,
            AgentAuditSeverity.WARNING,
        ),
        EventType.APPROVAL_EXPIRED: _mapping(
            AgentTelemetryKind.APPROVAL_RESOLVED,
            AgentAuditOutcome.EXPIRED,
            AgentAuditSeverity.WARNING,
        ),
        EventType.POLICY_EVALUATED: _mapping(AgentTelemetryKind.POLICY_EVALUATED),
        EventType.POLICY_DENIED: _mapping(
            AgentTelemetryKind.POLICY_EVALUATED,
            AgentAuditOutcome.DENIED,
            AgentAuditSeverity.WARNING,
        ),
        EventType.BUDGET_RESERVED: _mapping(
            AgentTelemetryKind.BUDGET_RESERVED, AgentAuditOutcome.SUCCESS
        ),
        EventType.BUDGET_CONSUMED: _mapping(
            AgentTelemetryKind.BUDGET_CONSUMED, AgentAuditOutcome.SUCCESS
        ),
        EventType.BUDGET_RELEASED: _mapping(
            AgentTelemetryKind.BUDGET_CONSUMED, AgentAuditOutcome.PARTIAL
        ),
        EventType.BUDGET_EXCEEDED: _mapping(
            AgentTelemetryKind.BUDGET_CONSUMED,
            AgentAuditOutcome.FAILED,
            AgentAuditSeverity.ERROR,
        ),
        EventType.RECOVERY_STARTED: _mapping(
            AgentTelemetryKind.RECOVERY_STARTED,
            severity=AgentAuditSeverity.WARNING,
        ),
        EventType.RECOVERY_RETRY_REQUESTED: _mapping(
            AgentTelemetryKind.OPERATION_RETRIED,
            AgentAuditOutcome.PARTIAL,
            AgentAuditSeverity.WARNING,
        ),
        EventType.RECOVERY_REOBSERVE_REQUESTED: _mapping(
            AgentTelemetryKind.RECOVERY_STARTED,
            AgentAuditOutcome.PARTIAL,
            AgentAuditSeverity.WARNING,
        ),
        EventType.RECOVERY_REPLAN_REQUESTED: _mapping(
            AgentTelemetryKind.RECOVERY_STARTED,
            AgentAuditOutcome.PARTIAL,
            AgentAuditSeverity.WARNING,
        ),
        EventType.RECOVERY_ROLLBACK_REQUESTED: _mapping(
            AgentTelemetryKind.ROLLBACK_STARTED,
            severity=AgentAuditSeverity.WARNING,
        ),
        EventType.RECOVERY_ROLLBACK_COMPLETED: _mapping(
            AgentTelemetryKind.ROLLBACK_COMPLETED,
            AgentAuditOutcome.SUCCESS,
            AgentAuditSeverity.NOTICE,
        ),
        EventType.RECOVERY_ESCALATED: _mapping(
            AgentTelemetryKind.RECOVERY_STARTED,
            AgentAuditOutcome.PARTIAL,
            AgentAuditSeverity.ERROR,
        ),
        EventType.RECOVERY_FAILED: _mapping(
            AgentTelemetryKind.RECOVERY_COMPLETED,
            AgentAuditOutcome.FAILED,
            AgentAuditSeverity.ERROR,
        ),
        EventType.RUNTIME_KILL_SWITCH_ACTIVATED: _mapping(
            AgentTelemetryKind.SECURITY_FINDING,
            AgentAuditOutcome.DENIED,
            AgentAuditSeverity.CRITICAL,
        ),
        DelegationEventType.PROPOSED.value: _mapping(
            AgentTelemetryKind.DELEGATION_PROPOSED
        ),
        DelegationEventType.ACCEPTED.value: _mapping(
            AgentTelemetryKind.DELEGATION_ACCEPTED
        ),
        DelegationEventType.REJECTED.value: _mapping(
            AgentTelemetryKind.DELEGATION_COMPLETED,
            AgentAuditOutcome.DENIED,
            AgentAuditSeverity.WARNING,
        ),
        DelegationEventType.STARTED.value: _mapping(
            AgentTelemetryKind.DELEGATION_ACCEPTED
        ),
        DelegationEventType.WAITING.value: _mapping(
            AgentTelemetryKind.DELEGATION_ACCEPTED,
            AgentAuditOutcome.PARTIAL,
            AgentAuditSeverity.NOTICE,
        ),
        DelegationEventType.COMPLETED.value: _mapping(
            AgentTelemetryKind.DELEGATION_COMPLETED, AgentAuditOutcome.SUCCESS
        ),
        DelegationEventType.RESULT_RECEIVED.value: _mapping(
            AgentTelemetryKind.DELEGATION_COMPLETED, AgentAuditOutcome.SUCCESS
        ),
        DelegationEventType.FAILED.value: _mapping(
            AgentTelemetryKind.DELEGATION_COMPLETED,
            AgentAuditOutcome.FAILED,
            AgentAuditSeverity.ERROR,
        ),
        DelegationEventType.CANCELLED.value: _mapping(
            AgentTelemetryKind.DELEGATION_COMPLETED,
            AgentAuditOutcome.CANCELLED,
            AgentAuditSeverity.NOTICE,
        ),
        "checkpoint.created": _mapping(
            AgentTelemetryKind.CHECKPOINT_CREATED, AgentAuditOutcome.SUCCESS
        ),
        "checkpoint.restored": _mapping(
            AgentTelemetryKind.ROLLBACK_COMPLETED, AgentAuditOutcome.SUCCESS
        ),
        "transaction.rolled_back": _mapping(
            AgentTelemetryKind.ROLLBACK_COMPLETED, AgentAuditOutcome.SUCCESS
        ),
        "security.prompt_injection.assessed": _mapping(
            AgentTelemetryKind.SECURITY_FINDING,
            severity=AgentAuditSeverity.WARNING,
        ),
        "security.audit.recorded": _mapping(AgentTelemetryKind.PERMISSION_EVALUATED),
        "security.kill_switch.activated": _mapping(
            AgentTelemetryKind.SECURITY_FINDING,
            AgentAuditOutcome.DENIED,
            AgentAuditSeverity.CRITICAL,
        ),
        "security.kill_switch.released": _mapping(
            AgentTelemetryKind.SECURITY_FINDING,
            AgentAuditOutcome.SUCCESS,
            AgentAuditSeverity.NOTICE,
        ),
        "security.kill_switch.recovery_requested": _mapping(
            AgentTelemetryKind.RECOVERY_STARTED,
            severity=AgentAuditSeverity.WARNING,
        ),
        "model.invocation": _mapping(AgentTelemetryKind.MODEL_INVOCATION),
    }
)

_FINAL_TRACE_STATUSES = frozenset(
    {
        AgentTraceStatus.COMPLETE,
        AgentTraceStatus.FAILED,
        AgentTraceStatus.CORRUPTED,
        AgentTraceStatus.REDACTED,
        AgentTraceStatus.ARCHIVED,
    }
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:16]}"


def _stable_id(prefix: str, *parts: object) -> str:
    digest = hashlib.sha256("|".join(map(str, parts)).encode()).hexdigest()[:16]
    return f"{prefix}-{digest}"


def _payload_hash(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, default=str, separators=(",", ":"))
    return f"sha256:{hashlib.sha256(encoded.encode()).hexdigest()}"


def _tuple_field(data: dict[str, Any], name: str) -> tuple[str, ...]:
    value = data.get(name, ())
    if isinstance(value, (list, tuple)):
        return tuple(str(item) for item in value)
    return ()


def _all_records(
    list_records: Callable[..., tuple[_RecordT, ...]], **filters: Any
) -> tuple[_RecordT, ...]:
    """Read every deterministic store page without bypassing public limits."""

    records: list[_RecordT] = []
    offset = 0
    while True:
        page = list_records(offset=offset, limit=_PAGE_SIZE, **filters)
        records.extend(page)
        if len(page) < _PAGE_SIZE:
            return tuple(records)
        offset += len(page)


class AgentObservabilityService:
    """Records, reconstructs, aggregates and audits Agent Runtime activity."""

    def __init__(
        self,
        store: AgentObservabilityStore | None = None,
        *,
        health_thresholds: AgentHealthThresholds | None = None,
    ) -> None:
        self._store: AgentObservabilityStore = (
            store if store is not None else InMemoryAgentObservabilityStore()
        )
        self._health_thresholds = health_thresholds or AgentHealthThresholds()

    @property
    def store(self) -> AgentObservabilityStore:
        return self._store

    @property
    def health_thresholds(self) -> AgentHealthThresholds:
        return self._health_thresholds

    def record_telemetry(
        self,
        record: AgentTelemetryRecord | None = None,
        **values: Any,
    ) -> AgentTelemetryRecord:
        if record is None:
            values.setdefault("id", _new_id("agent-telemetry"))
            values.setdefault("timestamp", _now())
            record = AgentTelemetryRecord(**values)
        elif values:
            raise InvalidAgentObservabilityContractError(
                "record and telemetry fields are mutually exclusive"
            )
        self._store.add_telemetry(record)
        return record

    def record_metric(
        self, point: AgentMetricPoint | None = None, **values: Any
    ) -> AgentMetricPoint:
        if point is None:
            values.setdefault("id", _new_id("agent-metric"))
            values.setdefault("timestamp", _now())
            point = AgentMetricPoint(**values)
        elif values:
            raise InvalidAgentObservabilityContractError(
                "point and metric fields are mutually exclusive"
            )
        self._store.add_metric(point)
        return point

    def record_audit(
        self, record: AgentAuditRecord | None = None, **values: Any
    ) -> AgentAuditRecord:
        if record is None:
            values.setdefault("id", _new_id("agent-audit"))
            values.setdefault("timestamp", _now())
            record = AgentAuditRecord(**values)
        elif values:
            raise InvalidAgentObservabilityContractError(
                "record and audit fields are mutually exclusive"
            )
        self._store.add_audit(record)
        return record

    def record_model_invocation(
        self, record: AgentModelInvocationRecord
    ) -> AgentModelInvocationRecord:
        self._store.add_model_invocation(record)
        telemetry = AgentTelemetryRecord(
            id=_stable_id("agent-telemetry", record.id),
            kind=AgentTelemetryKind.MODEL_INVOCATION,
            timestamp=record.timestamp,
            agent_id=record.agent_id,
            agent_run_id=record.agent_run_id,
            goal_id=record.goal_id,
            operation_id=record.operation_id,
            trace_id=record.trace_id,
            correlation_id=record.correlation_id,
            outcome=record.validation_outcome,
            duration_ms=record.latency_ms,
            retry_count=record.retry_count,
            measurements={
                "input_tokens": record.input_tokens,
                "output_tokens": record.output_tokens,
                "cached_input_tokens": record.cached_input_tokens,
                "estimated_cost": str(record.estimated_cost),
                "actual_cost": str(record.actual_cost),
            },
            metadata={
                "model_invocation_id": record.id,
                "provider": record.provider,
                "model": record.model,
            },
        )
        self._store.add_telemetry(telemetry)
        self._store.add_audit(
            AgentAuditRecord(
                id=_stable_id("agent-audit", record.id),
                timestamp=record.timestamp,
                action="model.invocation",
                outcome=record.validation_outcome,
                severity=(
                    AgentAuditSeverity.ERROR
                    if record.validation_outcome == AgentAuditOutcome.FAILED
                    else AgentAuditSeverity.INFO
                ),
                agent_id=record.agent_id,
                agent_run_id=record.agent_run_id,
                goal_id=record.goal_id,
                operation_id=record.operation_id,
                decision=record.selection_reason,
                reason_codes=("fallback",) if record.fallback else (),
                trace_id=record.trace_id,
                correlation_id=record.correlation_id,
                payload_hash=_payload_hash(
                    {
                        "provider": record.provider,
                        "model": record.model,
                        "configuration_version": record.configuration_version,
                    }
                ),
                payload_reference=f"model:{record.id}",
                metadata={
                    "provider": record.provider,
                    "model": record.model,
                    "privacy_mode": record.privacy_mode,
                    "persisted_result": record.persisted_result,
                },
            )
        )
        return record

    def start_trace(
        self,
        agent_run_id: str,
        goal_id: str,
        *,
        agent_id: str | None = None,
        workflow_id: str = "",
        correlation_id: str | None = None,
        timestamp: datetime | None = None,
        trace_id: str | None = None,
        root_span_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AgentObservabilityTraceRecord:
        started = _utc(timestamp or _now(), "timestamp")
        trace_id = trace_id or _new_id("trace")
        root_span_id = root_span_id or _new_id("span")
        correlation_id = correlation_id or trace_id
        trace = AgentTrace(
            trace_id=trace_id,
            agent_run_id=agent_run_id,
            goal_id=goal_id,
            agent_id=agent_id or "",
            workflow_id=workflow_id,
            status=AgentTraceStatus.OPEN.value,
            started_at=started,
            correlation_id=correlation_id,
            metadata=dict(sanitize_agent_observability_data(metadata or {})),
        )
        self._store.add_trace(trace)
        root = AgentSpan(
            span_id=root_span_id,
            trace_id=trace_id,
            parent_span_id=None,
            agent_run_id=agent_run_id,
            goal_id=goal_id,
            operation_id="operation-agent-run",
            operation_name="agent_run",
            started_at=started,
            status=AgentTraceStatus.OPEN,
        )
        self._store.add_span(root)
        metrics = AgentTraceMetrics(trace_id=trace_id, span_count=1)
        snapshot = AgentTraceSnapshot(
            id=_stable_id("agent-trace-snapshot", trace_id),
            trace_id=trace_id,
            root_span_id=root_span_id,
            agent_id=agent_id,
            agent_run_id=agent_run_id,
            goal_id=goal_id,
            started_at=started,
            status=AgentTraceStatus.OPEN,
            metrics=metrics,
            child_trace_ids=(),
            correlation_id=correlation_id,
            metadata=metadata or {},
        )
        record = AgentObservabilityTraceRecord(
            id=_stable_id("agent-observability-trace", trace_id),
            trace=trace,
            root_span_id=root_span_id,
            snapshot=snapshot,
            links=(),
            created_at=started,
            updated_at=started,
            metadata=metadata or {},
        )
        self._store.add_trace_record(record)
        return record

    def _trace_record(self, trace_id: str) -> AgentObservabilityTraceRecord:
        return self._store.get_trace_record_by_trace(trace_id)

    def _ensure_open_trace(self, record: AgentObservabilityTraceRecord) -> None:
        if AgentTraceStatus(record.trace.status) in _FINAL_TRACE_STATUSES:
            raise AgentObservabilityTraceFinalizedError("trace is finalized")

    def start_span(
        self,
        trace_id: str,
        operation_id: str,
        operation_name: str,
        *,
        span_id: str | None = None,
        parent_span_id: str | None = None,
        timestamp: datetime | None = None,
        attributes: dict[str, Any] | None = None,
        retry_count: int = 0,
        metadata: dict[str, Any] | None = None,
    ) -> AgentSpan:
        record = self._trace_record(trace_id)
        self._ensure_open_trace(record)
        span_id = span_id or _new_id("span")
        if parent_span_id == span_id:
            raise InvalidAgentObservabilityContractError(
                "parent_span_id cannot equal span_id"
            )
        parent_span_id = parent_span_id or record.root_span_id
        parent = self._store.get_span(parent_span_id)
        if parent.trace_id != trace_id:
            raise InvalidAgentObservabilityContractError(
                "parent span belongs to another trace"
            )
        span = AgentSpan(
            span_id=span_id,
            trace_id=trace_id,
            parent_span_id=parent_span_id,
            agent_run_id=record.trace.agent_run_id,
            goal_id=record.trace.goal_id,
            operation_id=operation_id,
            operation_name=operation_name,
            started_at=_utc(timestamp or _now(), "timestamp"),
            status=AgentTraceStatus.OPEN,
            attributes=attributes or {},
            retry_count=retry_count,
            metadata=metadata or {},
        )
        self._store.add_span(span)
        self._refresh_trace_record(trace_id, span.started_at)
        return span

    def _close_span(
        self,
        span_id: str,
        *,
        status: AgentTraceStatus,
        completed_at: datetime | None,
        error_summary: str | None = None,
    ) -> AgentSpan:
        span = self._store.get_span(span_id)
        if span.status != AgentTraceStatus.OPEN:
            raise AgentObservabilityTraceFinalizedError("span is already finalized")
        completed = _utc(completed_at or _now(), "completed_at")
        if completed < span.started_at:
            raise InvalidAgentObservabilityContractError(
                "completed_at cannot be before started_at"
            )
        updated = replace(
            span,
            status=status,
            completed_at=completed,
            duration_ms=(completed - span.started_at).total_seconds() * 1000,
            error_summary=error_summary,
        )
        self._store.update_span(updated)
        self._refresh_trace_record(span.trace_id, completed)
        return updated

    def complete_span(
        self, span_id: str, *, completed_at: datetime | None = None
    ) -> AgentSpan:
        return self._close_span(
            span_id,
            status=AgentTraceStatus.COMPLETE,
            completed_at=completed_at,
        )

    def fail_span(
        self,
        span_id: str,
        *,
        error_summary: str,
        completed_at: datetime | None = None,
    ) -> AgentSpan:
        return self._close_span(
            span_id,
            status=AgentTraceStatus.FAILED,
            completed_at=completed_at,
            error_summary=error_summary,
        )

    def _refresh_trace_record(
        self, trace_id: str, updated_at: datetime
    ) -> AgentObservabilityTraceRecord:
        record = self._trace_record(trace_id)
        spans = _all_records(self._store.list_spans, trace_id=trace_id)
        metrics = AgentTraceMetrics(
            trace_id=trace_id,
            span_count=len(spans),
            error_count=sum(span.status == AgentTraceStatus.FAILED for span in spans),
            retry_count=sum(span.retry_count for span in spans),
            total_duration_ms=sum(span.duration_ms or 0.0 for span in spans),
        )
        snapshot = replace(record.snapshot, metrics=metrics)
        updated = replace(
            record,
            snapshot=snapshot,
            updated_at=max(record.updated_at, _utc(updated_at, "updated_at")),
        )
        self._store.update_trace_record(updated)
        return updated

    def complete_trace(
        self, trace_id: str, *, completed_at: datetime | None = None
    ) -> AgentObservabilityTraceRecord:
        record = self._trace_record(trace_id)
        self._ensure_open_trace(record)
        completed = _utc(completed_at or _now(), "completed_at")
        open_children = tuple(
            span
            for span in _all_records(self._store.list_spans, trace_id=trace_id)
            if span.span_id != record.root_span_id
            and span.status == AgentTraceStatus.OPEN
        )
        if open_children:
            raise AgentObservabilityTraceFinalizedError("trace has open child spans")
        root = self._store.get_span(record.root_span_id)
        if root.status == AgentTraceStatus.OPEN:
            self.complete_span(root.span_id, completed_at=completed)
            record = self._trace_record(trace_id)
        trace = replace(
            record.trace,
            status=AgentTraceStatus.COMPLETE.value,
            completed_at=completed,
            duration_ms=int(
                (completed - record.trace.started_at).total_seconds() * 1000
            ),
        )
        self._store.update_trace(trace)
        snapshot = replace(
            record.snapshot,
            completed_at=completed,
            status=AgentTraceStatus.COMPLETE,
        )
        updated = replace(
            record,
            trace=trace,
            snapshot=snapshot,
            updated_at=max(record.updated_at, completed),
        )
        self._store.update_trace_record(updated)
        return updated

    def link_child_trace(
        self,
        parent_trace_id: str,
        child_trace_id: str,
        *,
        delegation_id: str | None = None,
        timestamp: datetime | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AgentTraceLink:
        parent = self._trace_record(parent_trace_id)
        self._trace_record(child_trace_id)
        self._ensure_open_trace(parent)
        link = AgentTraceLink(
            id=_new_id("agent-trace-link"),
            parent_trace_id=parent_trace_id,
            child_trace_id=child_trace_id,
            relation="delegation",
            delegation_id=delegation_id,
            timestamp=_utc(timestamp or _now(), "timestamp"),
            metadata=metadata or {},
        )
        child_ids = tuple(
            sorted(set(parent.snapshot.child_trace_ids + (child_trace_id,)))
        )
        snapshot = replace(parent.snapshot, child_trace_ids=child_ids)
        updated = replace(
            parent,
            snapshot=snapshot,
            links=parent.links + (link,),
            updated_at=max(parent.updated_at, link.timestamp),
        )
        self._store.update_trace_record(updated)
        return link

    def ingest_event(self, event: AgentRuntimeEvent) -> AgentTelemetryRecord:
        if not isinstance(event, AgentRuntimeEvent):
            raise InvalidAgentObservabilityContractError(
                "event must be AgentRuntimeEvent"
            )
        header = event.header
        data = dict(event.payload.data)
        header_metadata = dict(header.metadata)
        kind, outcome, severity = _EVENT_MAPPING.get(
            header.event_type,
            _mapping(AgentTelemetryKind.CUSTOM),
        )
        if header.event_type in {
            EventType.RUNTIME_KILL_SWITCH_ACTIVATED,
            "security.kill_switch.activated",
        }:
            data.setdefault("reason_codes", ["kill_switch_activated"])
        safe_payload = sanitize_agent_observability_data(data)
        safe_header_metadata = sanitize_agent_observability_data(header_metadata)

        def first(*names: str) -> Any:
            for name in names:
                value = data.get(name)
                if value is None:
                    value = header_metadata.get(name)
                if value is not None:
                    return value
            return None

        duration = first("duration_ms", "latency_ms")
        attempt = first("attempt")
        retry_count = first("retry_count", "retries")
        record = AgentTelemetryRecord(
            id=_stable_id("agent-telemetry", header.event_id),
            kind=kind,
            timestamp=header.occurred_at,
            agent_id=header.agent_id,
            agent_run_id=header.agent_run_id,
            goal_id=header.goal_id,
            operation_id=first("operation_id") or header.task_id,
            workflow_id=header.workflow_id,
            delegation_id=first("delegation_id"),
            checkpoint_id=first("checkpoint_id"),
            approval_id=first("approval_id", "approval_request_id"),
            actor_id=header.actor_id,
            trace_id=first("trace_id"),
            span_id=first("span_id"),
            parent_span_id=first("parent_span_id"),
            correlation_id=header.correlation_id,
            causation_id=header.causation_id or header.event_id,
            severity=severity,
            outcome=outcome,
            duration_ms=float(duration) if duration is not None else None,
            attempt=int(attempt) if attempt is not None else 1,
            retry_count=int(retry_count) if retry_count is not None else 0,
            resource_ids=_tuple_field(data, "resource_ids"),
            reason_codes=_tuple_field(data, "reason_codes"),
            measurements=data.get("measurements", {}),
            metadata={
                "event_type": header.event_type,
                "source": header.source,
                "sensitivity": header.sensitivity.value,
                "payload": safe_payload,
                "event_metadata": safe_header_metadata,
            },
        )
        self._store.add_telemetry(record)
        self.record_audit(
            AgentAuditRecord(
                id=_stable_id("agent-audit", header.event_id),
                timestamp=header.occurred_at,
                action=header.event_type,
                outcome=outcome,
                severity=severity,
                agent_id=header.agent_id,
                agent_run_id=header.agent_run_id,
                goal_id=header.goal_id,
                operation_id=record.operation_id,
                decision=first("decision", "result", "status"),
                policy_id=first("policy_id"),
                permission_decision=first("permission_decision", "decision"),
                sensitivity=header.sensitivity.value,
                resource_ids=record.resource_ids,
                actor_id=header.actor_id,
                reason_codes=record.reason_codes,
                trace_id=record.trace_id,
                span_id=record.span_id,
                correlation_id=header.correlation_id,
                causation_id=header.event_id,
                payload_hash=_payload_hash(safe_payload),
                payload_reference=f"event:{header.event_id}",
                metadata={"event_type": header.event_type},
            )
        )
        return record

    def snapshot_run_metrics(
        self, agent_run_id: str, *, timestamp: datetime | None = None
    ) -> AgentRunMetrics:
        timestamp = _utc(timestamp or _now(), "timestamp")
        telemetry = _all_records(self._store.list_telemetry, agent_run_id=agent_run_id)
        models = _all_records(
            self._store.list_model_invocations, agent_run_id=agent_run_id
        )
        operation_records = tuple(
            record
            for record in telemetry
            if record.kind
            in {
                AgentTelemetryKind.OPERATION_COMPLETED,
                AgentTelemetryKind.OPERATION_FAILED,
            }
        )
        resource_ids = tuple(
            sorted({item for record in telemetry for item in record.resource_ids})
        )
        agent_id = next(
            (record.agent_id for record in telemetry if record.agent_id), None
        )
        goal_id = next((record.goal_id for record in telemetry if record.goal_id), None)
        errors = sum(record.outcome == AgentAuditOutcome.FAILED for record in telemetry)
        health = AgentHealthStatus.DEGRADED if errors else AgentHealthStatus.HEALTHY
        metrics = AgentRunMetrics(
            id=_stable_id("agent-run-metrics", agent_run_id, timestamp.isoformat()),
            agent_run_id=agent_run_id,
            agent_id=agent_id,
            goal_id=goal_id,
            timestamp=timestamp,
            operations_total=len(operation_records),
            operations_succeeded=sum(
                record.kind == AgentTelemetryKind.OPERATION_COMPLETED
                for record in operation_records
            ),
            operations_failed=sum(
                record.kind == AgentTelemetryKind.OPERATION_FAILED
                for record in operation_records
            ),
            retries=sum(record.retry_count for record in telemetry),
            approvals=sum(
                record.kind == AgentTelemetryKind.APPROVAL_REQUESTED
                for record in telemetry
            ),
            delegations=sum(
                record.kind == AgentTelemetryKind.DELEGATION_COMPLETED
                for record in telemetry
            ),
            checkpoints=sum(
                record.kind == AgentTelemetryKind.CHECKPOINT_CREATED
                for record in telemetry
            ),
            rollbacks=sum(
                record.kind == AgentTelemetryKind.ROLLBACK_COMPLETED
                for record in telemetry
            ),
            recoveries=sum(
                record.kind
                in {
                    AgentTelemetryKind.RECOVERY_STARTED,
                    AgentTelemetryKind.RECOVERY_COMPLETED,
                }
                for record in telemetry
            ),
            active_duration_ms=sum(
                record.duration_ms or 0.0 for record in operation_records
            ),
            waiting_duration_ms=sum(
                record.duration_ms or 0.0
                for record in telemetry
                if record.kind == AgentTelemetryKind.RUN_WAITING
            ),
            estimated_cost=sum(
                (record.estimated_cost for record in models), Decimal(0)
            ),
            actual_cost=sum((record.actual_cost for record in models), Decimal(0)),
            input_tokens=sum(record.input_tokens for record in models),
            output_tokens=sum(record.output_tokens for record in models),
            resource_ids=resource_ids,
            error_count=errors,
            health_status=health,
        )
        try:
            existing = self._store.get_run_metrics(metrics.id)
        except AgentObservabilityNotFoundError:
            self._store.add_run_metrics(metrics)
            return metrics
        if existing == metrics:
            return existing
        self._store.update_run_metrics(metrics)
        return metrics

    @staticmethod
    def _percentile(values: tuple[float, ...], percentile: float) -> float:
        if not values:
            return 0.0
        ordered = sorted(values)
        rank = max(1, math.ceil(percentile * len(ordered)))
        return ordered[rank - 1]

    def snapshot_runtime_metrics(
        self,
        *,
        window_start: datetime,
        window_end: datetime,
        timestamp: datetime | None = None,
    ) -> AgentRuntimeMetrics:
        start = _utc(window_start, "window_start")
        end = _utc(window_end, "window_end")
        timestamp = _utc(timestamp or _now(), "timestamp")
        telemetry = _all_records(self._store.list_telemetry, start=start, end=end)
        models = _all_records(self._store.list_model_invocations, start=start, end=end)
        operations = tuple(
            record
            for record in telemetry
            if record.kind
            in {
                AgentTelemetryKind.OPERATION_COMPLETED,
                AgentTelemetryKind.OPERATION_FAILED,
            }
        )
        durations = tuple(
            record.duration_ms
            for record in operations
            if record.duration_ms is not None
        )
        completed = sum(
            record.kind == AgentTelemetryKind.RUN_COMPLETED for record in telemetry
        )
        failed = sum(
            record.kind == AgentTelemetryKind.RUN_FAILED for record in telemetry
        )
        denominator = completed + failed
        success_rate = completed / denominator if denominator else 0.0
        active_agents = {
            record.agent_id
            for record in telemetry
            if record.agent_id
            and record.kind
            not in {
                AgentTelemetryKind.RUN_COMPLETED,
                AgentTelemetryKind.RUN_FAILED,
                AgentTelemetryKind.RUN_CANCELLED,
            }
        }
        metrics = AgentRuntimeMetrics(
            id=_stable_id(
                "agent-runtime-metrics",
                start.isoformat(),
                end.isoformat(),
                timestamp.isoformat(),
            ),
            window_start=start,
            window_end=end,
            timestamp=timestamp,
            runs_started=sum(
                record.kind == AgentTelemetryKind.RUN_STARTED for record in telemetry
            ),
            runs_completed=completed,
            runs_failed=failed,
            success_rate=success_rate,
            average_duration_ms=(sum(durations) / len(durations)) if durations else 0.0,
            p50_duration_ms=self._percentile(durations, 0.50),
            p95_duration_ms=self._percentile(durations, 0.95),
            p99_duration_ms=self._percentile(durations, 0.99),
            operations=len(operations),
            retries=sum(record.retry_count for record in telemetry),
            approvals=sum(
                record.kind == AgentTelemetryKind.APPROVAL_REQUESTED
                for record in telemetry
            ),
            denials=sum(
                record.outcome == AgentAuditOutcome.DENIED for record in telemetry
            ),
            delegations=sum(
                record.kind == AgentTelemetryKind.DELEGATION_COMPLETED
                for record in telemetry
            ),
            rollbacks=sum(
                record.kind == AgentTelemetryKind.ROLLBACK_COMPLETED
                for record in telemetry
            ),
            recoveries=sum(
                record.kind == AgentTelemetryKind.RECOVERY_STARTED
                for record in telemetry
            ),
            kill_switch_activations=sum(
                "kill_switch_activated" in record.reason_codes for record in telemetry
            ),
            estimated_cost=sum(
                (record.estimated_cost for record in models), Decimal(0)
            ),
            actual_cost=sum((record.actual_cost for record in models), Decimal(0)),
            input_tokens=sum(record.input_tokens for record in models),
            output_tokens=sum(record.output_tokens for record in models),
            active_agents=len(active_agents),
            stalled_runs=0,
            health_status=(
                AgentHealthStatus.DEGRADED if failed else AgentHealthStatus.HEALTHY
            )
            if telemetry
            else AgentHealthStatus.UNKNOWN,
        )
        try:
            existing = self._store.get_runtime_metrics(metrics.id)
        except AgentObservabilityNotFoundError:
            self._store.add_runtime_metrics(metrics)
            return metrics
        if existing == metrics:
            return existing
        self._store.update_runtime_metrics(metrics)
        return metrics

    def evaluate_health(
        self,
        *,
        scope: str,
        timestamp: datetime | None = None,
        agent_run_id: str | None = None,
        heartbeat: RuntimeHeartbeat | None = None,
    ) -> AgentHealthReport:
        timestamp = _utc(timestamp or _now(), "timestamp")
        if heartbeat is not None and not isinstance(heartbeat, RuntimeHeartbeat):
            raise InvalidAgentObservabilityContractError(
                "heartbeat must be RuntimeHeartbeat"
            )
        if (
            heartbeat is not None
            and agent_run_id is not None
            and heartbeat.agent_run_id != agent_run_id
        ):
            raise InvalidAgentObservabilityContractError(
                "heartbeat agent_run_id does not match health scope"
            )
        telemetry = _all_records(self._store.list_telemetry, agent_run_id=agent_run_id)
        metrics = _all_records(self._store.list_metrics, agent_run_id=agent_run_id)
        findings: list[str] = []
        operation_records = tuple(
            record
            for record in telemetry
            if record.kind
            in {
                AgentTelemetryKind.OPERATION_COMPLETED,
                AgentTelemetryKind.OPERATION_FAILED,
                AgentTelemetryKind.OPERATION_RETRIED,
            }
        )
        error_count = sum(
            record.kind == AgentTelemetryKind.OPERATION_FAILED
            or record.outcome == AgentAuditOutcome.FAILED
            for record in operation_records
        )
        retry_count = sum(
            max(record.retry_count, 1)
            if record.kind == AgentTelemetryKind.OPERATION_RETRIED
            else record.retry_count
            for record in operation_records
        )
        denominator = len(operation_records)
        error_rate = min(1.0, error_count / denominator) if denominator else 0.0
        retry_rate = min(1.0, retry_count / denominator) if denominator else 0.0
        denials = sum(
            record.outcome == AgentAuditOutcome.DENIED for record in telemetry
        )
        denial_rate = min(1.0, denials / len(telemetry)) if telemetry else 0.0
        if error_rate > self._health_thresholds.max_error_rate:
            findings.append("high_error_rate")
        if retry_rate > self._health_thresholds.max_retry_rate:
            findings.append("retry_storm")
        if denial_rate > self._health_thresholds.max_denial_rate:
            findings.append("excessive_denials")
        recovery_count = sum(
            record.kind == AgentTelemetryKind.RECOVERY_STARTED for record in telemetry
        )
        if recovery_count > self._health_thresholds.max_recoveries:
            findings.append("repeated_recovery")
        checkpoint_failures = sum(
            record.kind == AgentTelemetryKind.CHECKPOINT_CREATED
            and record.outcome == AgentAuditOutcome.FAILED
            for record in telemetry
        )
        if checkpoint_failures > self._health_thresholds.max_checkpoint_failures:
            findings.append("checkpoint_failures")
        recovery_failures = sum(
            record.kind == AgentTelemetryKind.RECOVERY_COMPLETED
            and record.outcome == AgentAuditOutcome.FAILED
            for record in telemetry
        )
        kill_switch = any(
            "kill_switch_activated" in record.reason_codes for record in telemetry
        )
        if kill_switch:
            findings.append("kill_switch_active")
        terminal_runs = {
            record.agent_run_id
            for record in telemetry
            if record.agent_run_id
            and record.kind
            in {
                AgentTelemetryKind.RUN_COMPLETED,
                AgentTelemetryKind.RUN_FAILED,
                AgentTelemetryKind.RUN_CANCELLED,
            }
        }
        last_started: dict[str, datetime] = {}
        failed_runs: set[str] = set()
        for record in telemetry:
            if record.agent_run_id and record.kind == AgentTelemetryKind.RUN_STARTED:
                last_started[record.agent_run_id] = max(
                    record.timestamp,
                    last_started.get(record.agent_run_id, record.timestamp),
                )
            if record.agent_run_id and record.kind == AgentTelemetryKind.RUN_FAILED:
                failed_runs.add(record.agent_run_id)
        stalled_runs = tuple(
            sorted(
                run_id
                for run_id, started_at in last_started.items()
                if run_id not in terminal_runs
                and (timestamp - started_at).total_seconds()
                > self._health_thresholds.stalled_after_seconds
            )
        )
        if stalled_runs:
            findings.append("stalled_run")
        heartbeat_stalled = False
        heartbeat_failed = False
        if heartbeat is not None:
            try:
                heartbeat_expires_at = _utc(
                    datetime.fromisoformat(heartbeat.expires_at),
                    "heartbeat.expires_at",
                )
            except ValueError as exc:
                raise InvalidAgentObservabilityContractError(
                    "invalid heartbeat.expires_at"
                ) from exc
            heartbeat_stalled = timestamp > heartbeat_expires_at + timedelta(
                seconds=self._health_thresholds.heartbeat_grace_seconds
            )
            if heartbeat_stalled:
                findings.append("heartbeat_missing")
            if heartbeat.health == "stalled":
                heartbeat_stalled = True
                findings.append("heartbeat_stalled")
            if heartbeat.health in {"failed", "abandoned"}:
                heartbeat_failed = True
                findings.append("heartbeat_failed")
        backlog_values = [
            int(point.value)
            for point in metrics
            if point.name in {"agent.runtime.backlog", "agent.runtime.queue"}
        ]
        queue_backlog = backlog_values[-1] if backlog_values else None
        if (
            queue_backlog is not None
            and queue_backlog > self._health_thresholds.max_backlog
        ):
            findings.append("backlog_exceeded")
        if not telemetry and not metrics:
            status = AgentHealthStatus.UNKNOWN
        elif kill_switch or heartbeat_failed:
            status = AgentHealthStatus.UNHEALTHY
        elif stalled_runs or heartbeat_stalled:
            status = AgentHealthStatus.STALLED
        elif "high_error_rate" in findings and error_rate >= 0.75:
            status = AgentHealthStatus.UNHEALTHY
        elif findings:
            status = AgentHealthStatus.DEGRADED
        else:
            status = AgentHealthStatus.HEALTHY
        report = AgentHealthReport(
            id=_stable_id(
                "agent-health-report", scope, agent_run_id, timestamp.isoformat()
            ),
            scope=scope,
            status=status,
            findings=tuple(dict.fromkeys(findings)),
            stalled_run_ids=stalled_runs,
            failed_run_ids=tuple(sorted(failed_runs)),
            queue_backlog=queue_backlog,
            error_rate=error_rate,
            retry_rate=retry_rate,
            checkpoint_failures=checkpoint_failures,
            recovery_failures=recovery_failures,
            timestamp=timestamp,
        )
        try:
            self._store.get_health_report(report.id)
        except AgentObservabilityNotFoundError:
            self._store.add_health_report(report)
        else:
            self._store.update_health_report(report)
        return report


__all__ = ["AgentObservabilityService"]
