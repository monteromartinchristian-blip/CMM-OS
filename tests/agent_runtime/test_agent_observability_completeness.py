from __future__ import annotations

import inspect

from cmm import agent_runtime
from cmm.agent_runtime.agent_observability_service import AgentObservabilityService
from cmm.agent_runtime.agent_observability_store import InMemoryAgentObservabilityStore
from cmm.agent_runtime.agent_trace_contracts import AgentTrace
from cmm.agent_runtime.enums import AgentTraceStatus

REQUIREMENT_MATRIX = {
    "contracts.round_trip": "TestContracts",
    "contracts.immutability": "test_telemetry_round_trip_and_immutability",
    "contracts.utc": "test_contract_timestamps_normalize_to_utc",
    "contracts.ids": "test_invalid_ids_are_rejected",
    "contracts.nan_infinity": "test_metric_point_round_trip_and_finite_values",
    "contracts.decimal": "test_cost_metric_uses_decimal",
    "store.indexes": "test_telemetry_crud_filters_and_stale_indexes",
    "store.all_families": "test_clear_removes_every_record_family",
    "store.append_only": "test_mutable_snapshot_crud_and_append_only_model_records",
    "store.thread_safety": "test_concurrent_adds_remain_consistent",
    "store.pagination": "test_time_filters_are_inclusive_and_pagination_is_deterministic",
    "store.atomicity": "test_store_satisfies_protocol_and_has_instance_lock",
    "tracing.root_child": "test_trace_root_child_and_completion",
    "tracing.errors": "test_span_parent_rules_and_double_close",
    "tracing.delegation": "test_delegation_links_child_trace",
    "tracing.timestamps": "test_trace_completion_rejects_timestamp_before_start_without_mutation",
    "tracing.backward_compatibility": "test_legacy_agent_trace_round_trip_is_unchanged",
    "telemetry.real_events": "test_registered_event_mapping",
    "metrics.run": "test_run_snapshot_counts_cost_tokens_and_is_deterministic",
    "metrics.runtime": "test_runtime_snapshot_percentiles_inclusive_window_and_zero_division",
    "audit.sanitization": "test_event_payload_is_sanitized_and_hashed_for_audit",
    "audit.model_invocation": "test_run_snapshot_counts_cost_tokens_and_is_deterministic",
    "health.thresholds": "test_health_detects_unknown_healthy_retry_storm_and_kill_switch",
    "health.heartbeat": "test_health_uses_canonical_runtime_heartbeat_contract",
    "health.denials_recovery_checkpoint": "test_health_detects_denials_recovery_and_checkpoint_failures",
    "model.invocation": "test_model_invocation_round_trip_without_prompt",
}


PUBLIC_EXPORTS = {
    "AgentTelemetryKind",
    "AgentMetricKind",
    "AgentAuditSeverity",
    "AgentAuditOutcome",
    "AgentHealthStatus",
    "AgentTelemetryRecord",
    "AgentMetricPoint",
    "AgentSpan",
    "AgentTraceMetrics",
    "AgentTraceLink",
    "AgentTraceSnapshot",
    "AgentObservabilityTraceRecord",
    "AgentAuditRecord",
    "AgentRunMetrics",
    "AgentRuntimeMetrics",
    "AgentHealthThresholds",
    "AgentHealthReport",
    "AgentModelInvocationRecord",
    "AgentObservabilityStore",
    "InMemoryAgentObservabilityStore",
    "AgentObservabilityService",
    "sanitize_agent_observability_data",
}


def test_requirement_matrix_has_no_empty_entries() -> None:
    assert all(REQUIREMENT_MATRIX.values())
    assert len(REQUIREMENT_MATRIX) >= 19


def test_public_api_exports_new_names_exactly_once() -> None:
    assert PUBLIC_EXPORTS <= set(agent_runtime.__all__)
    for name in PUBLIC_EXPORTS:
        assert agent_runtime.__all__.count(name) == 1
        assert hasattr(agent_runtime, name)


def test_canonical_trace_exports_are_not_duplicated() -> None:
    assert agent_runtime.AgentTrace is AgentTrace
    assert agent_runtime.AgentTraceStatus is AgentTraceStatus
    assert agent_runtime.__all__.count("AgentTrace") == 1
    assert agent_runtime.__all__.count("AgentTraceStatus") == 1


def test_public_store_and_service_methods_are_explicit() -> None:
    store_methods = {
        name
        for name, value in inspect.getmembers(
            InMemoryAgentObservabilityStore, inspect.isfunction
        )
        if not name.startswith("_")
    }
    service_methods = {
        name
        for name, value in inspect.getmembers(
            AgentObservabilityService, inspect.isfunction
        )
        if not name.startswith("_")
    }
    assert store_methods == {
        "add_telemetry",
        "get_telemetry",
        "update_telemetry",
        "list_telemetry",
        "delete_telemetry",
        "add_metric",
        "get_metric",
        "update_metric",
        "list_metrics",
        "delete_metric",
        "add_span",
        "get_span",
        "update_span",
        "list_spans",
        "delete_span",
        "add_trace",
        "get_trace",
        "update_trace",
        "delete_trace",
        "add_trace_record",
        "get_trace_record",
        "get_trace_record_by_trace",
        "update_trace_record",
        "delete_trace_record",
        "list_trace_records",
        "add_audit",
        "get_audit",
        "update_audit",
        "list_audits",
        "delete_audit",
        "add_model_invocation",
        "get_model_invocation",
        "update_model_invocation",
        "delete_model_invocation",
        "list_model_invocations",
        "add_run_metrics",
        "get_run_metrics",
        "update_run_metrics",
        "delete_run_metrics",
        "list_run_metrics",
        "add_runtime_metrics",
        "get_runtime_metrics",
        "update_runtime_metrics",
        "delete_runtime_metrics",
        "list_runtime_metrics",
        "add_health_report",
        "get_health_report",
        "update_health_report",
        "delete_health_report",
        "list_health_reports",
        "clear",
    }
    assert service_methods == {
        "record_telemetry",
        "record_metric",
        "record_model_invocation",
        "start_trace",
        "start_span",
        "complete_span",
        "fail_span",
        "complete_trace",
        "link_child_trace",
        "record_audit",
        "ingest_event",
        "snapshot_run_metrics",
        "snapshot_runtime_metrics",
        "evaluate_health",
    }


def test_no_second_trace_contract_or_status_is_defined() -> None:
    from cmm.agent_runtime import (
        agent_observability_contracts,
        agent_observability_enums,
    )

    assert "AgentTrace" not in agent_observability_contracts.__dict__
    assert "AgentTraceStatus" not in agent_observability_enums.__dict__
