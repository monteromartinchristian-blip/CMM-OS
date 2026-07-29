from __future__ import annotations

import math
from concurrent.futures import ThreadPoolExecutor
from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import MappingProxyType

import pytest

from cmm.agent_runtime.agent_delegation_enums import DelegationEventType
from cmm.agent_runtime.agent_observability_contracts import (
    REDACTED,
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
    sanitize_agent_observability_data,
)
from cmm.agent_runtime.agent_observability_enums import (
    AgentAuditOutcome,
    AgentAuditSeverity,
    AgentHealthStatus,
    AgentMetricKind,
    AgentTelemetryKind,
)
from cmm.agent_runtime.agent_observability_errors import (
    AgentObservabilityAppendOnlyError,
    AgentObservabilityConflictError,
    AgentObservabilityDuplicateError,
    AgentObservabilityError,
    AgentObservabilityNotFoundError,
    AgentObservabilityQueryError,
    AgentObservabilityTraceFinalizedError,
    InvalidAgentObservabilityContractError,
)
from cmm.agent_runtime.agent_observability_service import (
    _EVENT_MAPPING,
    AgentObservabilityService,
)
from cmm.agent_runtime.agent_observability_store import (
    AgentObservabilityStore,
    InMemoryAgentObservabilityStore,
)
from cmm.agent_runtime.agent_trace_contracts import AgentTrace
from cmm.agent_runtime.enums import (
    AgentRuntimeStatus,
    AgentTraceStatus,
    RuntimeHealthStatus,
)
from cmm.agent_runtime.runtime_event_contracts import (
    AgentRuntimeEvent,
    AgentRuntimeEventHeader,
    AgentRuntimeEventPayload,
)
from cmm.agent_runtime.runtime_event_factory import AgentRuntimeEventFactory
from cmm.agent_runtime.runtime_event_types import EVENT_TYPE_CATEGORY_MAP, EventType
from cmm.agent_runtime.runtime_loop_contracts import RuntimeHeartbeat

NOW = datetime(2026, 7, 28, 12, 0, tzinfo=timezone.utc)


def make_telemetry(**changes: object) -> AgentTelemetryRecord:
    values: dict[str, object] = {
        "id": "agent-telemetry-123",
        "kind": AgentTelemetryKind.OPERATION_COMPLETED,
        "timestamp": NOW,
        "agent_id": "agent-123",
        "agent_run_id": "agent-run-123",
        "goal_id": "goal-123",
        "operation_id": "operation-123",
        "workflow_id": None,
        "delegation_id": None,
        "checkpoint_id": None,
        "approval_id": None,
        "actor_id": None,
        "trace_id": "trace-123",
        "span_id": "span-123",
        "parent_span_id": None,
        "correlation_id": "correlation-123",
        "causation_id": "event-123",
        "severity": AgentAuditSeverity.INFO,
        "outcome": AgentAuditOutcome.SUCCESS,
        "duration_ms": 125.0,
        "attempt": 1,
        "retry_count": 0,
        "resource_ids": ("resource-123",),
        "reason_codes": ("ok",),
        "measurements": {"bytes": 10},
        "metadata": {"safe": {"nested": True}},
    }
    values.update(changes)
    return AgentTelemetryRecord(**values)


def make_metric(**changes: object) -> AgentMetricPoint:
    values: dict[str, object] = {
        "id": "agent-metric-123",
        "name": "agent.operation.duration",
        "kind": AgentMetricKind.DURATION,
        "value": 125.0,
        "unit": "ms",
        "timestamp": NOW,
        "dimensions": {"status": "success"},
        "agent_id": "agent-123",
        "agent_run_id": "agent-run-123",
        "goal_id": "goal-123",
        "operation_id": "operation-123",
        "trace_id": "trace-123",
        "correlation_id": "correlation-123",
        "sample_count": 1,
        "metadata": {},
    }
    values.update(changes)
    return AgentMetricPoint(**values)


def make_audit(**changes: object) -> AgentAuditRecord:
    values: dict[str, object] = {
        "id": "agent-audit-123",
        "timestamp": NOW,
        "action": "operation.completed",
        "agent_id": "agent-123",
        "agent_run_id": "agent-run-123",
        "goal_id": "goal-123",
        "operation_id": "operation-123",
        "decision": "allow",
        "outcome": AgentAuditOutcome.SUCCESS,
        "severity": AgentAuditSeverity.INFO,
        "policy_id": "policy-123",
        "permission_decision": "allow",
        "sensitivity": "internal",
        "resource_ids": ("resource-123",),
        "actor_id": "actor-123",
        "reason_codes": ("approved",),
        "trace_id": "trace-123",
        "span_id": "span-123",
        "correlation_id": "correlation-123",
        "causation_id": "event-123",
        "payload_hash": "sha256:abc123",
        "payload_reference": "event:event-123",
        "metadata": {"safe": True},
    }
    values.update(changes)
    return AgentAuditRecord(**values)


class TestEnumsAndErrors:
    def test_enum_values_are_exact(self) -> None:
        assert {item.value for item in AgentTelemetryKind} == {
            "run_started",
            "run_resumed",
            "run_paused",
            "run_waiting",
            "run_completed",
            "run_failed",
            "run_cancelled",
            "goal_created",
            "goal_updated",
            "goal_completed",
            "operation_started",
            "operation_completed",
            "operation_failed",
            "operation_retried",
            "approval_requested",
            "approval_resolved",
            "policy_evaluated",
            "permission_evaluated",
            "delegation_proposed",
            "delegation_accepted",
            "delegation_completed",
            "checkpoint_created",
            "rollback_started",
            "rollback_completed",
            "recovery_started",
            "recovery_completed",
            "security_finding",
            "budget_reserved",
            "budget_consumed",
            "model_invocation",
            "custom",
        }
        assert {item.value for item in AgentMetricKind} == {
            "counter",
            "gauge",
            "duration",
            "histogram",
            "rate",
            "ratio",
            "cost",
            "tokens",
            "bytes",
        }
        assert {item.value for item in AgentAuditSeverity} == {
            "debug",
            "info",
            "notice",
            "warning",
            "error",
            "critical",
        }
        assert {item.value for item in AgentAuditOutcome} == {
            "success",
            "partial",
            "failed",
            "denied",
            "cancelled",
            "expired",
            "unknown",
        }
        assert {item.value for item in AgentHealthStatus} == {
            "healthy",
            "degraded",
            "unhealthy",
            "stalled",
            "unknown",
        }

    def test_invalid_enum_value_is_rejected(self) -> None:
        with pytest.raises(InvalidAgentObservabilityContractError):
            make_telemetry(kind="not-a-real-kind")

    def test_error_hierarchy_is_typed(self) -> None:
        assert issubclass(
            AgentObservabilityTraceFinalizedError, AgentObservabilityConflictError
        )
        assert issubclass(
            AgentObservabilityAppendOnlyError, AgentObservabilityConflictError
        )
        assert issubclass(AgentObservabilityNotFoundError, KeyError)
        assert issubclass(AgentObservabilityDuplicateError, ValueError)
        assert issubclass(AgentObservabilityQueryError, ValueError)

    def test_error_details_do_not_retain_sensitive_values(self) -> None:
        error = AgentObservabilityError(
            "safe failure", {"password": "never-store", "safe": "ok"}
        )
        assert error.details == {"password": REDACTED, "safe": "ok"}
        assert "never-store" not in repr(error.details)


class TestSanitization:
    @pytest.mark.parametrize(
        "key",
        [
            "password",
            "PASSWD",
            "client_secret",
            "token",
            "api_key",
            "ApiKey",
            "authorization",
            "cookie",
            "credential",
            "private_key",
            "access_key",
            "refresh_token",
            "session",
        ],
    )
    def test_sensitive_keys_are_redacted(self, key: str) -> None:
        result = sanitize_agent_observability_data({key: "do-not-store"})
        assert result[key] == REDACTED
        assert "do-not-store" not in repr(result)

    def test_nested_values_and_url_credentials_are_redacted(self) -> None:
        source = {
            "nested": {"password": "hidden", "safe": "ok"},
            "url": "https://user:pass@example.test/path",
            "text": "authorization=Bearer hidden-value",
        }
        result = sanitize_agent_observability_data(source)
        assert result["nested"]["password"] == REDACTED
        assert result["nested"]["safe"] == "ok"
        assert "user:pass" not in result["url"]
        assert "hidden-value" not in result["text"]
        assert source["nested"]["password"] == "hidden"


class TestContracts:
    def test_telemetry_round_trip_and_immutability(self) -> None:
        record = make_telemetry()
        restored = AgentTelemetryRecord.from_mapping(record.to_dict())
        assert restored == record
        assert isinstance(record.metadata, MappingProxyType)
        assert isinstance(record.metadata["safe"], MappingProxyType)
        with pytest.raises(FrozenInstanceError):
            record.id = "changed"  # type: ignore[misc]
        with pytest.raises(TypeError):
            record.metadata["x"] = 1  # type: ignore[index]

    def test_contract_timestamps_normalize_to_utc(self) -> None:
        plus_two = timezone(timedelta(hours=2))
        record = make_telemetry(timestamp=NOW.astimezone(plus_two))
        assert record.timestamp.tzinfo == timezone.utc
        assert record.timestamp == NOW
        with pytest.raises(InvalidAgentObservabilityContractError):
            make_telemetry(timestamp=NOW.replace(tzinfo=None))

    @pytest.mark.parametrize("field", ["id", "agent_id", "trace_id", "span_id"])
    def test_invalid_ids_are_rejected(self, field: str) -> None:
        with pytest.raises(InvalidAgentObservabilityContractError):
            make_telemetry(**{field: "bad id with spaces"})

    @pytest.mark.parametrize("value", [-1.0, math.nan, math.inf, -math.inf])
    def test_invalid_duration_is_rejected(self, value: float) -> None:
        with pytest.raises(InvalidAgentObservabilityContractError):
            make_telemetry(duration_ms=value)

    def test_metric_point_round_trip_and_finite_values(self) -> None:
        point = make_metric()
        assert AgentMetricPoint.from_mapping(point.to_dict()) == point
        for invalid in (math.nan, math.inf, -math.inf):
            with pytest.raises(InvalidAgentObservabilityContractError):
                make_metric(value=invalid)

    def test_cost_metric_uses_decimal(self) -> None:
        point = make_metric(
            kind=AgentMetricKind.COST,
            value=Decimal("0.0100"),
            unit="EUR",
        )
        assert point.value == Decimal("0.0100")
        assert point.to_dict()["value"] == "0.0100"
        assert AgentMetricPoint.from_mapping(point.to_dict()) == point

    @pytest.mark.parametrize(
        ("kind", "value", "unit"),
        [
            (AgentMetricKind.COUNTER, 3, "items"),
            (AgentMetricKind.GAUGE, 2.5, "items"),
            (AgentMetricKind.DURATION, 15.0, "ms"),
            (AgentMetricKind.HISTOGRAM, 7.0, "ms"),
            (AgentMetricKind.RATE, 4.0, "items/s"),
            (AgentMetricKind.RATIO, 0.75, "ratio"),
            (AgentMetricKind.COST, Decimal("0.01"), "EUR"),
            (AgentMetricKind.TOKENS, 10, "tokens"),
            (AgentMetricKind.BYTES, 1024, "bytes"),
        ],
    )
    def test_every_metric_kind_has_a_stable_round_trip(
        self,
        kind: AgentMetricKind,
        value: float | Decimal,
        unit: str,
    ) -> None:
        point = make_metric(kind=kind, value=value, unit=unit)
        assert AgentMetricPoint.from_mapping(point.to_dict()) == point

    def test_ratio_and_token_metric_semantics_are_validated(self) -> None:
        with pytest.raises(InvalidAgentObservabilityContractError):
            make_metric(kind=AgentMetricKind.RATIO, value=1.01, unit="ratio")
        with pytest.raises(InvalidAgentObservabilityContractError):
            make_metric(kind=AgentMetricKind.TOKENS, value=1.5, unit="tokens")

    def test_model_invocation_round_trip_without_prompt(self) -> None:
        record = AgentModelInvocationRecord(
            id="agent-model-invocation-123",
            timestamp=NOW,
            agent_id="agent-123",
            agent_run_id="agent-run-123",
            goal_id="goal-123",
            operation_id="operation-123",
            provider="openai",
            model="gpt-test",
            selection_reason="privacy-compatible",
            input_tokens=100,
            output_tokens=25,
            cached_input_tokens=10,
            estimated_cost=Decimal("0.0123"),
            actual_cost=Decimal("0.0101"),
            latency_ms=250.0,
            retry_count=1,
            fallback=True,
            validation_outcome=AgentAuditOutcome.SUCCESS,
            persisted_result=True,
            memory_change_ids=("memory-change-1",),
            configuration_version="config-7",
            privacy_mode="strict",
            trace_id="trace-123",
            correlation_id="correlation-123",
            metadata={"password": "hidden", "safe": True},
        )
        payload = record.to_dict()
        assert "prompt" not in payload
        assert payload["estimated_cost"] == "0.0123"
        assert payload["metadata"]["password"] == REDACTED
        assert AgentModelInvocationRecord.from_mapping(payload) == record

    def test_model_tokens_and_costs_cannot_be_negative(self) -> None:
        base = {
            "id": "agent-model-invocation-123",
            "timestamp": NOW,
            "provider": "provider",
            "model": "model",
            "operation_id": "operation-123",
            "selection_reason": "default",
            "configuration_version": "v1",
            "privacy_mode": "strict",
        }
        with pytest.raises(InvalidAgentObservabilityContractError):
            AgentModelInvocationRecord(**base, input_tokens=-1)
        with pytest.raises(InvalidAgentObservabilityContractError):
            AgentModelInvocationRecord(**base, estimated_cost=Decimal("-0.1"))

    def test_audit_round_trip_and_payload_reference_only(self) -> None:
        audit = make_audit(metadata={"api_key": "hidden"})
        payload = audit.to_dict()
        assert payload["metadata"]["api_key"] == REDACTED
        assert "payload" not in payload
        assert AgentAuditRecord.from_mapping(payload) == audit


class TestTraceComposition:
    def test_phase_919_trace_contracts_are_canonical(self) -> None:
        from cmm.agent_runtime import AgentTrace as PublicAgentTrace
        from cmm.agent_runtime import AgentTraceStatus as PublicAgentTraceStatus

        assert PublicAgentTrace is AgentTrace
        assert PublicAgentTraceStatus is AgentTraceStatus
        assert AgentTraceStatus.COMPLETE.value == "complete"
        assert not hasattr(AgentTraceStatus, "COMPLETED")

    def test_legacy_agent_trace_round_trip_is_unchanged(self) -> None:
        trace = AgentTrace(
            trace_id="trace-legacy",
            agent_run_id="agent-run-legacy",
            goal_id="goal-legacy",
            agent_id="agent-legacy",
            status=AgentTraceStatus.OPEN.value,
            started_at=NOW,
            correlation_id="correlation-legacy",
        )
        payload = trace.to_dict()
        assert AgentTrace.from_dict(payload).to_dict() == payload
        assert "root_span_id" not in payload
        assert "spans" not in payload

    def test_span_round_trip_and_timestamp_rules(self) -> None:
        span = AgentSpan(
            span_id="span-123",
            trace_id="trace-123",
            parent_span_id=None,
            agent_run_id="agent-run-123",
            goal_id="goal-123",
            operation_id="operation-123",
            operation_name="execute",
            started_at=NOW,
            completed_at=NOW + timedelta(milliseconds=125),
            status=AgentTraceStatus.COMPLETE,
            duration_ms=125.0,
            attributes={"safe": True},
            linked_event_ids=("event-123",),
        )
        assert AgentSpan.from_mapping(span.to_dict()) == span
        with pytest.raises(InvalidAgentObservabilityContractError):
            replace(span, completed_at=NOW - timedelta(seconds=1))
        with pytest.raises(InvalidAgentObservabilityContractError):
            replace(span, parent_span_id=span.span_id)

    def test_trace_composition_round_trip(self) -> None:
        trace = AgentTrace(
            trace_id="trace-123",
            agent_run_id="agent-run-123",
            goal_id="goal-123",
            agent_id="agent-123",
            started_at=NOW,
        )
        metrics = AgentTraceMetrics(
            trace_id=trace.trace_id,
            span_count=1,
            error_count=0,
            retry_count=0,
            total_duration_ms=0.0,
        )
        snapshot = AgentTraceSnapshot(
            id="agent-trace-snapshot-123",
            trace_id=trace.trace_id,
            root_span_id="span-root",
            agent_id=trace.agent_id,
            agent_run_id=trace.agent_run_id,
            goal_id=trace.goal_id,
            started_at=NOW,
            completed_at=None,
            status=AgentTraceStatus.OPEN,
            metrics=metrics,
            child_trace_ids=(),
            correlation_id="correlation-123",
        )
        link = AgentTraceLink(
            id="agent-trace-link-123",
            parent_trace_id="trace-123",
            child_trace_id="trace-child",
            relation="delegation",
            delegation_id="delegation-123",
            timestamp=NOW,
        )
        record = AgentObservabilityTraceRecord(
            id="agent-observability-trace-123",
            trace=trace,
            root_span_id="span-root",
            snapshot=snapshot,
            links=(link,),
            created_at=NOW,
            updated_at=NOW,
        )
        restored = AgentObservabilityTraceRecord.from_mapping(record.to_dict())
        assert restored.to_dict() == record.to_dict()
        assert restored.trace_id == trace.trace_id

    def test_trace_link_cannot_link_itself(self) -> None:
        with pytest.raises(InvalidAgentObservabilityContractError):
            AgentTraceLink(
                id="agent-trace-link-123",
                parent_trace_id="trace-123",
                child_trace_id="trace-123",
                relation="delegation",
                timestamp=NOW,
            )


class TestMetricAndHealthContracts:
    def test_run_metrics_decimal_round_trip(self) -> None:
        metrics = AgentRunMetrics(
            id="agent-run-metrics-123",
            agent_run_id="agent-run-123",
            agent_id="agent-123",
            goal_id="goal-123",
            timestamp=NOW,
            operations_total=2,
            operations_succeeded=1,
            operations_failed=1,
            retries=1,
            approvals=1,
            delegations=1,
            checkpoints=1,
            rollbacks=1,
            recoveries=1,
            active_duration_ms=100.0,
            waiting_duration_ms=25.0,
            estimated_cost=Decimal("0.1000"),
            actual_cost=Decimal("0.0900"),
            input_tokens=10,
            output_tokens=5,
            resource_ids=("resource-123",),
            error_count=1,
            health_status=AgentHealthStatus.DEGRADED,
        )
        assert metrics.to_dict()["estimated_cost"] == "0.1000"
        assert AgentRunMetrics.from_mapping(metrics.to_dict()) == metrics

    def test_runtime_metrics_round_trip(self) -> None:
        metrics = AgentRuntimeMetrics(
            id="agent-runtime-metrics-123",
            window_start=NOW - timedelta(hours=1),
            window_end=NOW,
            timestamp=NOW,
            runs_started=2,
            runs_completed=1,
            runs_failed=1,
            success_rate=0.5,
            average_duration_ms=100.0,
            p50_duration_ms=100.0,
            p95_duration_ms=200.0,
            p99_duration_ms=200.0,
            operations=3,
            retries=1,
            approvals=1,
            denials=1,
            delegations=1,
            rollbacks=1,
            recoveries=1,
            kill_switch_activations=0,
            estimated_cost=Decimal("0.1"),
            actual_cost=Decimal("0.09"),
            input_tokens=10,
            output_tokens=5,
            active_agents=2,
            stalled_runs=0,
            health_status=AgentHealthStatus.DEGRADED,
        )
        assert AgentRuntimeMetrics.from_mapping(metrics.to_dict()) == metrics

    def test_health_thresholds_are_configurable_and_validated(self) -> None:
        thresholds = AgentHealthThresholds(max_error_rate=0.2, max_backlog=10)
        assert thresholds.max_error_rate == 0.2
        assert thresholds.max_backlog == 10
        with pytest.raises(InvalidAgentObservabilityContractError):
            AgentHealthThresholds(max_retry_rate=1.1)

    def test_health_report_round_trip(self) -> None:
        report = AgentHealthReport(
            id="agent-health-report-123",
            scope="runtime",
            status=AgentHealthStatus.STALLED,
            findings=("stalled_run",),
            stalled_run_ids=("agent-run-123",),
            failed_run_ids=(),
            queue_backlog=3,
            error_rate=0.0,
            retry_rate=0.0,
            checkpoint_failures=0,
            recovery_failures=0,
            timestamp=NOW,
        )
        assert AgentHealthReport.from_mapping(report.to_dict()) == report


class TestStore:
    def test_store_satisfies_protocol_and_has_instance_lock(self) -> None:
        first = InMemoryAgentObservabilityStore()
        second = InMemoryAgentObservabilityStore()
        assert isinstance(first, AgentObservabilityStore)
        assert first._lock is not second._lock

    def test_telemetry_crud_filters_and_stale_indexes(self) -> None:
        store = InMemoryAgentObservabilityStore()
        first = make_telemetry()
        second = make_telemetry(
            id="agent-telemetry-456",
            timestamp=NOW + timedelta(seconds=1),
            kind=AgentTelemetryKind.OPERATION_FAILED,
            outcome=AgentAuditOutcome.FAILED,
            severity=AgentAuditSeverity.ERROR,
            correlation_id="correlation-456",
            causation_id="event-456",
        )
        store.add_telemetry(second)
        store.add_telemetry(first)
        assert store.get_telemetry(first.id) == first
        assert store.list_telemetry(agent_run_id="agent-run-123") == (first, second)
        assert store.list_telemetry(kind=AgentTelemetryKind.OPERATION_FAILED) == (
            second,
        )
        assert store.list_telemetry(outcome=AgentAuditOutcome.FAILED) == (second,)
        assert store.list_telemetry(severity=AgentAuditSeverity.ERROR) == (second,)
        assert store.list_telemetry(agent_id="agent-123") == (first, second)
        assert store.list_telemetry(goal_id="goal-123") == (first, second)
        assert store.list_telemetry(operation_id="operation-123") == (first, second)
        assert store.list_telemetry(trace_id="trace-123") == (first, second)
        assert store.list_telemetry(span_id="span-123") == (first, second)
        assert store.list_telemetry(correlation_id="correlation-456") == (second,)
        assert store.list_telemetry(causation_id="event-456") == (second,)
        moved = replace(second, agent_run_id="agent-run-456")
        store.update_telemetry(moved)
        assert store.list_telemetry(agent_run_id="agent-run-123") == (first,)
        assert store.list_telemetry(agent_run_id="agent-run-456") == (moved,)
        store.delete_telemetry(moved.id)
        assert store.list_telemetry(agent_run_id="agent-run-456") == ()
        with pytest.raises(AgentObservabilityNotFoundError):
            store.get_telemetry(moved.id)

    def test_store_rejects_duplicates_and_bad_pagination(self) -> None:
        store = InMemoryAgentObservabilityStore()
        store.add_telemetry(make_telemetry())
        with pytest.raises(AgentObservabilityDuplicateError):
            store.add_telemetry(make_telemetry())
        with pytest.raises(AgentObservabilityQueryError):
            store.list_telemetry(limit=0)
        with pytest.raises(AgentObservabilityQueryError):
            store.list_telemetry(offset=-1)

    def test_time_filters_are_inclusive_and_pagination_is_deterministic(self) -> None:
        store = InMemoryAgentObservabilityStore()
        records = tuple(
            make_telemetry(
                id=f"agent-telemetry-{index}",
                timestamp=NOW + timedelta(seconds=index),
            )
            for index in range(3)
        )
        for record in reversed(records):
            store.add_telemetry(record)
        assert store.list_telemetry(start=NOW, end=NOW + timedelta(seconds=1)) == (
            records[0],
            records[1],
        )
        assert store.list_telemetry(offset=1, limit=1) == (records[1],)

    def test_metric_span_and_audit_indexes(self) -> None:
        store = InMemoryAgentObservabilityStore()
        metric = make_metric()
        span = AgentSpan(
            span_id="span-123",
            trace_id="trace-123",
            parent_span_id=None,
            agent_run_id="agent-run-123",
            goal_id="goal-123",
            operation_id="operation-123",
            operation_name="execute",
            started_at=NOW,
        )
        audit = make_audit()
        store.add_metric(metric)
        store.add_span(span)
        store.add_audit(audit)
        assert store.list_metrics(trace_id="trace-123") == (metric,)
        moved_metric = replace(metric, trace_id="trace-456")
        store.update_metric(moved_metric)
        assert store.get_metric(metric.id) == moved_metric
        assert store.list_metrics(trace_id="trace-123") == ()
        assert store.list_metrics(trace_id="trace-456") == (moved_metric,)
        assert store.list_spans(trace_id="trace-123") == (span,)
        assert store.list_audits(actor_id="actor-123") == (audit,)
        assert store.list_audits(resource_id="resource-123") == (audit,)
        assert store.list_audits(outcome=AgentAuditOutcome.SUCCESS) == (audit,)
        assert store.list_audits(severity=AgentAuditSeverity.INFO) == (audit,)
        assert store.list_audits(trace_id="trace-123") == (audit,)
        assert store.list_audits(span_id="span-123") == (audit,)
        assert store.list_audits(correlation_id="correlation-123") == (audit,)
        assert store.list_audits(causation_id="event-123") == (audit,)
        with pytest.raises(AgentObservabilityAppendOnlyError):
            store.update_audit(audit)
        assert store.get_audit(audit.id) == audit
        store.delete_audit(audit.id)
        assert store.list_audits(actor_id="actor-123") == ()
        store.delete_metric(metric.id)
        assert store.list_metrics(trace_id="trace-456") == ()

    def test_clear_removes_every_record_family(self) -> None:
        store = InMemoryAgentObservabilityStore()
        service = AgentObservabilityService(store)
        store.add_telemetry(make_telemetry())
        store.add_metric(make_metric())
        store.add_audit(make_audit())
        service.start_trace(
            agent_run_id="agent-run-clear",
            goal_id="goal-clear",
            trace_id="trace-clear",
            root_span_id="span-clear",
            timestamp=NOW,
        )
        store.add_model_invocation(
            AgentModelInvocationRecord(
                id="agent-model-invocation-clear",
                timestamp=NOW,
                operation_id="operation-clear",
                provider="provider",
                model="model",
                selection_reason="default",
                configuration_version="v1",
                privacy_mode="strict",
            )
        )
        store.add_run_metrics(
            AgentRunMetrics(
                id="agent-run-metrics-clear",
                agent_run_id="agent-run-clear",
                timestamp=NOW,
            )
        )
        store.add_runtime_metrics(
            AgentRuntimeMetrics(
                id="agent-runtime-metrics-clear",
                window_start=NOW,
                window_end=NOW,
                timestamp=NOW,
            )
        )
        store.add_health_report(
            AgentHealthReport(
                id="agent-health-report-clear",
                scope="runtime",
                status=AgentHealthStatus.UNKNOWN,
                findings=(),
                stalled_run_ids=(),
                failed_run_ids=(),
                queue_backlog=None,
                error_rate=0,
                retry_rate=0,
                checkpoint_failures=0,
                recovery_failures=0,
                timestamp=NOW,
            )
        )
        store.clear()
        assert store.list_telemetry() == ()
        assert store.list_metrics() == ()
        assert store.list_spans() == ()
        assert store.list_trace_records() == ()
        assert store.list_audits() == ()
        assert store.list_model_invocations() == ()
        assert store.list_run_metrics() == ()
        assert store.list_runtime_metrics() == ()
        assert store.list_health_reports() == ()
        with pytest.raises(AgentObservabilityNotFoundError):
            store.get_trace("trace-clear")

    def test_mutable_snapshot_crud_and_append_only_model_records(self) -> None:
        store = InMemoryAgentObservabilityStore()
        report = AgentHealthReport(
            id="agent-health-report-123",
            scope="runtime",
            status=AgentHealthStatus.HEALTHY,
            findings=(),
            stalled_run_ids=(),
            failed_run_ids=(),
            queue_backlog=None,
            error_rate=0,
            retry_rate=0,
            checkpoint_failures=0,
            recovery_failures=0,
            timestamp=NOW,
        )
        store.add_health_report(report)
        assert store.get_health_report(report.id) == report
        degraded = replace(
            report,
            status=AgentHealthStatus.DEGRADED,
            findings=("backlog_exceeded",),
        )
        store.update_health_report(degraded)
        assert store.list_health_reports() == (degraded,)
        store.delete_health_report(report.id)
        assert store.list_health_reports() == ()

        model = AgentModelInvocationRecord(
            id="agent-model-invocation-123",
            timestamp=NOW,
            operation_id="operation-123",
            provider="provider",
            model="model",
            selection_reason="default",
            configuration_version="v1",
            privacy_mode="strict",
        )
        store.add_model_invocation(model)
        assert store.get_model_invocation(model.id) == model
        assert store.list_model_invocations(provider="provider", model="model") == (
            model,
        )
        with pytest.raises(AgentObservabilityAppendOnlyError):
            store.update_model_invocation(model)
        store.delete_model_invocation(model.id)
        assert store.list_model_invocations() == ()

        run_metrics = AgentRunMetrics(
            id="agent-run-metrics-123",
            agent_run_id="agent-run-123",
            timestamp=NOW,
        )
        store.add_run_metrics(run_metrics)
        assert store.get_run_metrics(run_metrics.id) == run_metrics
        updated_run_metrics = replace(
            run_metrics,
            timestamp=NOW + timedelta(seconds=1),
            operations_total=1,
            operations_succeeded=1,
        )
        store.update_run_metrics(updated_run_metrics)
        assert store.list_run_metrics(agent_run_id="agent-run-123") == (
            updated_run_metrics,
        )
        store.delete_run_metrics(run_metrics.id)
        assert store.list_run_metrics() == ()

        runtime_metrics = AgentRuntimeMetrics(
            id="agent-runtime-metrics-123",
            window_start=NOW,
            window_end=NOW,
            timestamp=NOW,
        )
        store.add_runtime_metrics(runtime_metrics)
        assert store.get_runtime_metrics(runtime_metrics.id) == runtime_metrics
        updated_runtime_metrics = replace(runtime_metrics, runs_started=1)
        store.update_runtime_metrics(updated_runtime_metrics)
        assert store.list_runtime_metrics() == (updated_runtime_metrics,)
        store.delete_runtime_metrics(runtime_metrics.id)
        assert store.list_runtime_metrics() == ()

    def test_concurrent_adds_remain_consistent(self) -> None:
        store = InMemoryAgentObservabilityStore()

        def add(index: int) -> None:
            store.add_telemetry(
                make_telemetry(
                    id=f"agent-telemetry-thread-{index}",
                    correlation_id=f"correlation-thread-{index}",
                )
            )

        with ThreadPoolExecutor(max_workers=8) as executor:
            tuple(executor.map(add, range(50)))
        assert len(store.list_telemetry(limit=100)) == 50
        for index in range(50):
            assert (
                len(
                    store.list_telemetry(
                        correlation_id=f"correlation-thread-{index}", limit=100
                    )
                )
                == 1
            )


class TestServiceTracing:
    def test_trace_root_child_and_completion(self) -> None:
        service = AgentObservabilityService()
        record = service.start_trace(
            agent_run_id="agent-run-123",
            goal_id="goal-123",
            agent_id="agent-123",
            correlation_id="correlation-123",
            timestamp=NOW,
            trace_id="trace-123",
            root_span_id="span-root",
        )
        assert record.trace.trace_id == "trace-123"
        assert record.root_span_id == "span-root"
        child = service.start_span(
            trace_id="trace-123",
            span_id="span-child",
            parent_span_id="span-root",
            operation_id="operation-123",
            operation_name="execute",
            timestamp=NOW + timedelta(seconds=1),
        )
        completed_child = service.complete_span(
            child.span_id, completed_at=NOW + timedelta(seconds=2)
        )
        assert completed_child.status == AgentTraceStatus.COMPLETE
        completed = service.complete_trace(
            "trace-123", completed_at=NOW + timedelta(seconds=3)
        )
        assert completed.trace.status == AgentTraceStatus.COMPLETE.value
        assert completed.snapshot.metrics.span_count == 2
        with pytest.raises(AgentObservabilityTraceFinalizedError):
            service.start_span(
                trace_id="trace-123",
                operation_id="operation-456",
                operation_name="late",
            )

    def test_span_parent_rules_and_double_close(self) -> None:
        service = AgentObservabilityService()
        service.start_trace(
            agent_run_id="agent-run-123",
            goal_id="goal-123",
            trace_id="trace-123",
            root_span_id="span-root",
            timestamp=NOW,
        )
        with pytest.raises(AgentObservabilityNotFoundError):
            service.start_span(
                trace_id="trace-123",
                parent_span_id="span-missing",
                operation_id="operation-123",
                operation_name="execute",
            )
        with pytest.raises(InvalidAgentObservabilityContractError):
            service.start_span(
                trace_id="trace-123",
                span_id="span-self",
                parent_span_id="span-self",
                operation_id="operation-123",
                operation_name="execute",
            )
        span = service.start_span(
            trace_id="trace-123",
            span_id="span-child",
            parent_span_id="span-root",
            operation_id="operation-123",
            operation_name="execute",
            timestamp=NOW,
        )
        service.fail_span(
            span.span_id,
            error_summary="safe failure",
            completed_at=NOW + timedelta(seconds=1),
        )
        with pytest.raises(AgentObservabilityTraceFinalizedError):
            service.complete_span(span.span_id)

    def test_delegation_links_child_trace(self) -> None:
        service = AgentObservabilityService()
        service.start_trace(
            agent_run_id="agent-run-parent",
            goal_id="goal-parent",
            trace_id="trace-parent",
            root_span_id="span-parent",
            timestamp=NOW,
        )
        service.start_trace(
            agent_run_id="agent-run-child",
            goal_id="goal-child",
            trace_id="trace-child",
            root_span_id="span-child",
            timestamp=NOW,
        )
        link = service.link_child_trace(
            parent_trace_id="trace-parent",
            child_trace_id="trace-child",
            delegation_id="delegation-123",
            timestamp=NOW,
        )
        assert link.child_trace_id == "trace-child"
        parent = service.store.get_trace_record_by_trace("trace-parent")
        assert parent.snapshot.child_trace_ids == ("trace-child",)

    def test_trace_completion_rejects_timestamp_before_start_without_mutation(
        self,
    ) -> None:
        service = AgentObservabilityService()
        service.start_trace(
            agent_run_id="agent-run-123",
            goal_id="goal-123",
            trace_id="trace-123",
            root_span_id="span-root",
            timestamp=NOW,
        )
        with pytest.raises(InvalidAgentObservabilityContractError):
            service.complete_trace("trace-123", completed_at=NOW - timedelta(seconds=1))
        stored = service.store.get_trace_record_by_trace("trace-123")
        assert stored.trace.status == AgentTraceStatus.OPEN.value
        assert service.store.get_span("span-root").status == AgentTraceStatus.OPEN


class TestEventIngestion:
    def test_every_registered_runtime_event_has_an_explicit_mapping(self) -> None:
        assert set(EVENT_TYPE_CATEGORY_MAP) <= set(_EVENT_MAPPING)
        assert {event.value for event in DelegationEventType} <= set(_EVENT_MAPPING)

    @pytest.mark.parametrize(
        ("event_type", "kind", "outcome", "severity"),
        [
            (
                EventType.AGENT_RUN_STARTED,
                AgentTelemetryKind.RUN_STARTED,
                AgentAuditOutcome.UNKNOWN,
                AgentAuditSeverity.INFO,
            ),
            (
                EventType.AGENT_RUN_COMPLETED,
                AgentTelemetryKind.RUN_COMPLETED,
                AgentAuditOutcome.SUCCESS,
                AgentAuditSeverity.INFO,
            ),
            (
                EventType.AGENT_RUN_FAILED,
                AgentTelemetryKind.RUN_FAILED,
                AgentAuditOutcome.FAILED,
                AgentAuditSeverity.ERROR,
            ),
            (
                EventType.GOAL_CREATED,
                AgentTelemetryKind.GOAL_CREATED,
                AgentAuditOutcome.UNKNOWN,
                AgentAuditSeverity.INFO,
            ),
            (
                EventType.GOAL_COMPLETED,
                AgentTelemetryKind.GOAL_COMPLETED,
                AgentAuditOutcome.SUCCESS,
                AgentAuditSeverity.INFO,
            ),
            (
                EventType.OPERATION_STARTED,
                AgentTelemetryKind.OPERATION_STARTED,
                AgentAuditOutcome.UNKNOWN,
                AgentAuditSeverity.INFO,
            ),
            (
                EventType.OPERATION_COMPLETED,
                AgentTelemetryKind.OPERATION_COMPLETED,
                AgentAuditOutcome.SUCCESS,
                AgentAuditSeverity.INFO,
            ),
            (
                EventType.OPERATION_FAILED,
                AgentTelemetryKind.OPERATION_FAILED,
                AgentAuditOutcome.FAILED,
                AgentAuditSeverity.ERROR,
            ),
            (
                EventType.APPROVAL_REQUESTED,
                AgentTelemetryKind.APPROVAL_REQUESTED,
                AgentAuditOutcome.UNKNOWN,
                AgentAuditSeverity.NOTICE,
            ),
            (
                EventType.APPROVAL_REJECTED,
                AgentTelemetryKind.APPROVAL_RESOLVED,
                AgentAuditOutcome.DENIED,
                AgentAuditSeverity.WARNING,
            ),
            (
                EventType.POLICY_EVALUATED,
                AgentTelemetryKind.POLICY_EVALUATED,
                AgentAuditOutcome.UNKNOWN,
                AgentAuditSeverity.INFO,
            ),
            (
                EventType.BUDGET_RESERVED,
                AgentTelemetryKind.BUDGET_RESERVED,
                AgentAuditOutcome.SUCCESS,
                AgentAuditSeverity.INFO,
            ),
            (
                EventType.RECOVERY_STARTED,
                AgentTelemetryKind.RECOVERY_STARTED,
                AgentAuditOutcome.UNKNOWN,
                AgentAuditSeverity.WARNING,
            ),
            (
                EventType.RECOVERY_RETRY_REQUESTED,
                AgentTelemetryKind.OPERATION_RETRIED,
                AgentAuditOutcome.PARTIAL,
                AgentAuditSeverity.WARNING,
            ),
            (
                EventType.RECOVERY_ROLLBACK_COMPLETED,
                AgentTelemetryKind.ROLLBACK_COMPLETED,
                AgentAuditOutcome.SUCCESS,
                AgentAuditSeverity.NOTICE,
            ),
            (
                EventType.RUNTIME_KILL_SWITCH_ACTIVATED,
                AgentTelemetryKind.SECURITY_FINDING,
                AgentAuditOutcome.DENIED,
                AgentAuditSeverity.CRITICAL,
            ),
        ],
    )
    def test_registered_event_mapping(
        self,
        event_type: str,
        kind: AgentTelemetryKind,
        outcome: AgentAuditOutcome,
        severity: AgentAuditSeverity,
    ) -> None:
        service = AgentObservabilityService()
        event = AgentRuntimeEventFactory().create_event(
            event_type,
            {
                "operation_id": "operation-123",
                "duration_ms": 25,
                "attempt": 2,
                "retry_count": 1,
                "resource_ids": ["resource-123"],
                "reason_codes": ["reason-123"],
            },
            event_id=f"event-{event_type.replace('.', '-')}",
            occurred_at=NOW,
            emitted_at=NOW,
            agent_id="agent-123",
            agent_run_id="agent-run-123",
            goal_id="goal-123",
            workflow_id="workflow-123",
            correlation_id="correlation-123",
            causation_id="causation-123",
            actor_id="actor-123",
        )
        record = service.ingest_event(event)
        assert record.kind == kind
        assert record.outcome == outcome
        assert record.severity == severity
        assert record.operation_id == "operation-123"
        assert record.correlation_id == "correlation-123"
        assert record.causation_id == "causation-123"
        assert service.store.get_telemetry(record.id) == record

    @pytest.mark.parametrize(
        ("event_type", "kind"),
        [
            ("agent.delegation.proposed", AgentTelemetryKind.DELEGATION_PROPOSED),
            ("agent.delegation.accepted", AgentTelemetryKind.DELEGATION_ACCEPTED),
            ("agent.delegation.completed", AgentTelemetryKind.DELEGATION_COMPLETED),
            ("checkpoint.created", AgentTelemetryKind.CHECKPOINT_CREATED),
            ("security.prompt_injection.assessed", AgentTelemetryKind.SECURITY_FINDING),
            ("security.audit.recorded", AgentTelemetryKind.PERMISSION_EVALUATED),
            ("security.kill_switch.activated", AgentTelemetryKind.SECURITY_FINDING),
            ("model.invocation", AgentTelemetryKind.MODEL_INVOCATION),
        ],
    )
    def test_real_cross_phase_event_mapping(
        self, event_type: str, kind: AgentTelemetryKind
    ) -> None:
        service = AgentObservabilityService()
        event = AgentRuntimeEvent(
            header=AgentRuntimeEventHeader(
                event_id=f"event-{event_type.replace('.', '-')}",
                event_type=event_type,
                occurred_at=NOW,
                emitted_at=NOW,
                agent_id="agent-123",
                agent_run_id="agent-run-123",
                goal_id="goal-123",
                correlation_id="correlation-123",
                metadata={"delegation_id": "delegation-123"},
            ),
            payload=AgentRuntimeEventPayload(data={"checkpoint_id": "checkpoint-123"}),
        )
        assert service.ingest_event(event).kind == kind

    def test_event_payload_is_sanitized_and_hashed_for_audit(self) -> None:
        service = AgentObservabilityService()
        event = AgentRuntimeEvent(
            header=AgentRuntimeEventHeader(
                event_id="event-secret",
                event_type=EventType.OPERATION_COMPLETED,
                occurred_at=NOW,
                emitted_at=NOW,
                agent_run_id="agent-run-123",
            ),
            payload=AgentRuntimeEventPayload(
                data={"operation_id": "operation-123", "password": "hidden"}
            ),
        )
        record = service.ingest_event(event)
        assert record.metadata["payload"]["password"] == REDACTED
        audits = service.store.list_audits(causation_id="event-secret")
        assert len(audits) == 1
        assert audits[0].payload_hash.startswith("sha256:")
        assert "hidden" not in repr(audits[0])


class TestAggregationAndHealth:
    def test_aggregation_reads_every_store_page(self) -> None:
        service = AgentObservabilityService()
        for index in range(1001):
            service.record_telemetry(
                make_telemetry(
                    id=f"agent-telemetry-page-{index}",
                    duration_ms=1,
                )
            )
        metrics = service.snapshot_run_metrics("agent-run-123", timestamp=NOW)
        assert metrics.operations_total == 1001
        assert metrics.active_duration_ms == 1001

    def test_run_snapshot_counts_cost_tokens_and_is_deterministic(self) -> None:
        service = AgentObservabilityService()
        for record in (
            make_telemetry(id="agent-telemetry-1", duration_ms=10),
            make_telemetry(
                id="agent-telemetry-2",
                kind=AgentTelemetryKind.OPERATION_FAILED,
                outcome=AgentAuditOutcome.FAILED,
                duration_ms=20,
                retry_count=1,
            ),
            make_telemetry(
                id="agent-telemetry-3",
                kind=AgentTelemetryKind.APPROVAL_REQUESTED,
                duration_ms=None,
            ),
        ):
            service.record_telemetry(record)
        service.record_model_invocation(
            AgentModelInvocationRecord(
                id="agent-model-invocation-1",
                timestamp=NOW,
                agent_id="agent-123",
                agent_run_id="agent-run-123",
                goal_id="goal-123",
                operation_id="operation-123",
                provider="provider",
                model="model",
                selection_reason="default",
                input_tokens=100,
                output_tokens=25,
                estimated_cost=Decimal("0.10"),
                actual_cost=Decimal("0.08"),
                configuration_version="v1",
                privacy_mode="strict",
            )
        )
        first = service.snapshot_run_metrics("agent-run-123", timestamp=NOW)
        second = service.snapshot_run_metrics("agent-run-123", timestamp=NOW)
        assert second == first
        assert first.operations_total == 2
        assert first.operations_succeeded == 1
        assert first.operations_failed == 1
        assert first.retries == 1
        assert first.approvals == 1
        assert first.estimated_cost == Decimal("0.10")
        assert first.actual_cost == Decimal("0.08")
        assert first.input_tokens == 100
        assert first.output_tokens == 25
        audits = service.store.list_audits(operation_id="operation-123")
        assert len(audits) == 1
        assert audits[0].action == "model.invocation"
        assert audits[0].payload_reference == "model:agent-model-invocation-1"
        assert "prompt" not in repr(audits[0]).casefold()

    def test_runtime_snapshot_percentiles_inclusive_window_and_zero_division(
        self,
    ) -> None:
        service = AgentObservabilityService()
        durations = (10.0, 20.0, 30.0, 40.0, 50.0)
        for index, duration in enumerate(durations):
            service.record_telemetry(
                make_telemetry(
                    id=f"agent-telemetry-operation-{index}",
                    timestamp=NOW + timedelta(seconds=index),
                    duration_ms=duration,
                )
            )
        service.record_telemetry(
            make_telemetry(
                id="agent-telemetry-run-start",
                kind=AgentTelemetryKind.RUN_STARTED,
                timestamp=NOW,
                duration_ms=None,
            )
        )
        service.record_telemetry(
            make_telemetry(
                id="agent-telemetry-run-complete",
                kind=AgentTelemetryKind.RUN_COMPLETED,
                timestamp=NOW + timedelta(seconds=4),
                duration_ms=50,
            )
        )
        snapshot = service.snapshot_runtime_metrics(
            window_start=NOW,
            window_end=NOW + timedelta(seconds=4),
            timestamp=NOW + timedelta(seconds=5),
        )
        assert snapshot.operations == 5
        assert snapshot.success_rate == 1.0
        assert snapshot.p50_duration_ms == 30.0
        assert snapshot.p95_duration_ms == 50.0
        assert snapshot.p99_duration_ms == 50.0
        assert (
            service.snapshot_runtime_metrics(
                window_start=NOW,
                window_end=NOW + timedelta(seconds=4),
                timestamp=NOW + timedelta(seconds=5),
            )
            == snapshot
        )
        empty = AgentObservabilityService().snapshot_runtime_metrics(
            window_start=NOW,
            window_end=NOW,
            timestamp=NOW,
        )
        assert empty.success_rate == 0.0
        assert empty.average_duration_ms == 0.0

    def test_health_detects_unknown_healthy_retry_storm_and_kill_switch(self) -> None:
        service = AgentObservabilityService(
            health_thresholds=AgentHealthThresholds(
                max_error_rate=0.5,
                max_retry_rate=0.25,
                max_denial_rate=0.5,
                max_recoveries=2,
                max_checkpoint_failures=1,
                max_backlog=10,
            )
        )
        assert (
            service.evaluate_health(scope="runtime", timestamp=NOW).status
            == AgentHealthStatus.UNKNOWN
        )
        service.record_telemetry(
            make_telemetry(
                id="agent-telemetry-success",
                kind=AgentTelemetryKind.OPERATION_COMPLETED,
                retry_count=0,
            )
        )
        assert (
            service.evaluate_health(scope="runtime", timestamp=NOW).status
            == AgentHealthStatus.HEALTHY
        )
        service.record_telemetry(
            make_telemetry(
                id="agent-telemetry-retry",
                kind=AgentTelemetryKind.OPERATION_RETRIED,
                retry_count=2,
            )
        )
        retry_report = service.evaluate_health(scope="runtime", timestamp=NOW)
        assert retry_report.status == AgentHealthStatus.DEGRADED
        assert "retry_storm" in retry_report.findings
        service.record_telemetry(
            make_telemetry(
                id="agent-telemetry-kill-switch",
                kind=AgentTelemetryKind.SECURITY_FINDING,
                reason_codes=("kill_switch_activated",),
            )
        )
        report = service.evaluate_health(scope="runtime", timestamp=NOW)
        assert report.status == AgentHealthStatus.UNHEALTHY
        assert "kill_switch_active" in report.findings

    def test_health_detects_stalled_run_and_backlog(self) -> None:
        service = AgentObservabilityService(
            health_thresholds=AgentHealthThresholds(
                stalled_after_seconds=30,
                max_backlog=2,
            )
        )
        service.record_telemetry(
            make_telemetry(
                id="agent-telemetry-run-start",
                kind=AgentTelemetryKind.RUN_STARTED,
                timestamp=NOW - timedelta(minutes=2),
                duration_ms=None,
            )
        )
        service.record_metric(
            make_metric(
                id="agent-metric-backlog",
                name="agent.runtime.backlog",
                kind=AgentMetricKind.GAUGE,
                value=3,
                unit="items",
                timestamp=NOW,
            )
        )
        report = service.evaluate_health(scope="runtime", timestamp=NOW)
        assert report.status == AgentHealthStatus.STALLED
        assert report.stalled_run_ids == ("agent-run-123",)
        assert report.queue_backlog == 3
        assert "backlog_exceeded" in report.findings

    def test_health_uses_canonical_runtime_heartbeat_contract(self) -> None:
        service = AgentObservabilityService(
            health_thresholds=AgentHealthThresholds(
                stalled_after_seconds=600,
                heartbeat_grace_seconds=30,
            )
        )
        service.record_telemetry(
            make_telemetry(
                id="agent-telemetry-run-start",
                kind=AgentTelemetryKind.RUN_STARTED,
                timestamp=NOW - timedelta(minutes=2),
                duration_ms=None,
            )
        )
        heartbeat = RuntimeHeartbeat(
            agent_run_id="agent-run-123",
            status=AgentRuntimeStatus.EXECUTING,
            health=RuntimeHealthStatus.STALLED,
            last_activity_at=(NOW - timedelta(minutes=2)).isoformat(),
            expires_at=(NOW - timedelta(minutes=1)).isoformat(),
        )
        report = service.evaluate_health(
            scope="run",
            agent_run_id="agent-run-123",
            heartbeat=heartbeat,
            timestamp=NOW,
        )
        assert report.status == AgentHealthStatus.STALLED
        assert "heartbeat_missing" in report.findings

    def test_health_detects_denials_recovery_and_checkpoint_failures(self) -> None:
        service = AgentObservabilityService(
            health_thresholds=AgentHealthThresholds(
                max_denial_rate=0.1,
                max_recoveries=1,
                max_checkpoint_failures=0,
            )
        )
        records = (
            make_telemetry(
                id="agent-telemetry-denied",
                kind=AgentTelemetryKind.PERMISSION_EVALUATED,
                outcome=AgentAuditOutcome.DENIED,
                duration_ms=None,
            ),
            make_telemetry(
                id="agent-telemetry-recovery-1",
                kind=AgentTelemetryKind.RECOVERY_STARTED,
                duration_ms=None,
            ),
            make_telemetry(
                id="agent-telemetry-recovery-2",
                kind=AgentTelemetryKind.RECOVERY_STARTED,
                duration_ms=None,
            ),
            make_telemetry(
                id="agent-telemetry-checkpoint-failed",
                kind=AgentTelemetryKind.CHECKPOINT_CREATED,
                outcome=AgentAuditOutcome.FAILED,
                duration_ms=None,
            ),
        )
        for record in records:
            service.record_telemetry(record)
        report = service.evaluate_health(scope="runtime", timestamp=NOW)
        assert report.status == AgentHealthStatus.DEGRADED
        assert {
            "excessive_denials",
            "repeated_recovery",
            "checkpoint_failures",
        } <= set(report.findings)
        assert report.checkpoint_failures == 1
