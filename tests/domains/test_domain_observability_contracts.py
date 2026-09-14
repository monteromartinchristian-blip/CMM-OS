"""Phase 10.37 — Domain Observability contract tests.

Proves the immutable observed/unavailable metric contracts, health contracts
and report contracts follow the canonical Phase 10 repository conventions.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from cmm.domains.errors import InvalidDomainObservabilityContractError
from cmm.domains.observability_contracts import (
    DomainHealthFinding,
    DomainHealthResult,
    DomainHealthStatus,
    DomainMetricBucket,
    DomainMetricMeasurement,
    DomainMetricsSnapshot,
    DomainMetricStatus,
    DomainObservabilityLogEntry,
    DomainObservabilityReport,
)

NOW = datetime(2026, 8, 31, 12, 0, tzinfo=timezone.utc)


def test_metric_status_has_only_observed_and_unavailable() -> None:
    assert DomainMetricStatus.OBSERVED.value == "observed"
    assert DomainMetricStatus.UNAVAILABLE.value == "unavailable"
    assert {status.value for status in DomainMetricStatus} == {
        "observed",
        "unavailable",
    }


def test_health_status_has_canonical_semantic_states() -> None:
    assert {status.value for status in DomainHealthStatus} == {
        "healthy",
        "degraded",
        "unhealthy",
        "unknown",
    }


def test_unavailable_metric_is_not_observed_zero() -> None:
    measurement = DomainMetricMeasurement(
        name="permissions.rejected",
        status=DomainMetricStatus.UNAVAILABLE,
        unit="count",
        unavailable_reason="NO_PERMISSION_EVIDENCE",
    )

    assert measurement.status is DomainMetricStatus.UNAVAILABLE
    assert measurement.value is None
    assert measurement.buckets == ()
    assert measurement.unavailable_reason == "NO_PERMISSION_EVIDENCE"


def test_observed_zero_is_valid_and_distinct_from_unavailable() -> None:
    measurement = DomainMetricMeasurement(
        name="permissions.rejected",
        status=DomainMetricStatus.OBSERVED,
        unit="count",
        value=0,
        evidence_reference_ids=("permission-evidence:1",),
    )

    assert measurement.value == 0
    assert measurement.unavailable_reason is None


def test_observed_metric_cannot_claim_unavailable_reason() -> None:
    with pytest.raises(InvalidDomainObservabilityContractError):
        DomainMetricMeasurement(
            name="permissions.rejected",
            status=DomainMetricStatus.OBSERVED,
            unit="count",
            value=0,
            evidence_reference_ids=("permission-evidence:1",),
            unavailable_reason="NO_PERMISSION_EVIDENCE",
        )


def test_unavailable_metric_cannot_carry_a_value() -> None:
    with pytest.raises(InvalidDomainObservabilityContractError):
        DomainMetricMeasurement(
            name="permissions.rejected",
            status=DomainMetricStatus.UNAVAILABLE,
            unit="count",
            value=3,
            unavailable_reason="NO_PERMISSION_EVIDENCE",
        )


def test_unavailable_metric_cannot_carry_buckets() -> None:
    with pytest.raises(InvalidDomainObservabilityContractError):
        DomainMetricMeasurement(
            name="operations.by_domain",
            status=DomainMetricStatus.UNAVAILABLE,
            unit="count",
            buckets=(DomainMetricBucket(key="domain:health", value=2),),
            unavailable_reason="NO_OPERATION_EVIDENCE",
        )


def test_unavailable_metric_requires_a_reason() -> None:
    with pytest.raises(InvalidDomainObservabilityContractError):
        DomainMetricMeasurement(
            name="permissions.rejected",
            status=DomainMetricStatus.UNAVAILABLE,
            unit="count",
        )


def test_observed_metric_requires_value_or_buckets() -> None:
    with pytest.raises(InvalidDomainObservabilityContractError):
        DomainMetricMeasurement(
            name="permissions.rejected",
            status=DomainMetricStatus.OBSERVED,
            unit="count",
            evidence_reference_ids=("permission-evidence:1",),
        )


def test_bucket_rejects_blank_key() -> None:
    with pytest.raises(InvalidDomainObservabilityContractError):
        DomainMetricBucket(key="   ", value=1)


def test_bucket_rejects_boolean_value() -> None:
    with pytest.raises(InvalidDomainObservabilityContractError):
        DomainMetricBucket(key="domain:health", value=True)


def test_bucket_rejects_non_finite_value() -> None:
    with pytest.raises(InvalidDomainObservabilityContractError):
        DomainMetricBucket(key="domain:health", value=float("nan"))
    with pytest.raises(InvalidDomainObservabilityContractError):
        DomainMetricBucket(key="domain:health", value=float("inf"))


def test_measurement_buckets_are_canonically_ordered() -> None:
    measurement = DomainMetricMeasurement(
        name="resolution.decisions_by_domain",
        status=DomainMetricStatus.OBSERVED,
        unit="count",
        buckets=(
            DomainMetricBucket(key="domain:health", value=7),
            DomainMetricBucket(key="domain:general", value=3),
        ),
    )

    assert [bucket.key for bucket in measurement.buckets] == [
        "domain:general",
        "domain:health",
    ]


def test_measurement_evidence_ids_are_sorted_and_deduplicated() -> None:
    measurement = DomainMetricMeasurement(
        name="permissions.rejected",
        status=DomainMetricStatus.OBSERVED,
        unit="count",
        value=1,
        evidence_reference_ids=(
            "permission-evidence:2",
            "permission-evidence:1",
            "permission-evidence:2",
        ),
    )

    assert measurement.evidence_reference_ids == (
        "permission-evidence:1",
        "permission-evidence:2",
    )


def test_measurement_metadata_is_deep_frozen_and_caller_alias_safe() -> None:
    metadata = {"sensitivity": "internal"}

    measurement = DomainMetricMeasurement(
        name="permissions.rejected",
        status=DomainMetricStatus.OBSERVED,
        unit="count",
        value=1,
        metadata=metadata,
    )

    metadata["sensitivity"] = "mutated"

    assert measurement.metadata["sensitivity"] == "internal"
    with pytest.raises(TypeError):
        measurement.metadata["sensitivity"] = "write"  # type: ignore[index]


def test_measurement_rejects_boolean_scalar_value() -> None:
    with pytest.raises(InvalidDomainObservabilityContractError):
        DomainMetricMeasurement(
            name="permissions.rejected",
            status=DomainMetricStatus.OBSERVED,
            unit="count",
            value=True,
        )


def test_measurement_rejects_non_finite_scalar_value() -> None:
    with pytest.raises(InvalidDomainObservabilityContractError):
        DomainMetricMeasurement(
            name="resolution.confidence.mean",
            status=DomainMetricStatus.OBSERVED,
            unit="ratio",
            value=float("nan"),
        )


def test_log_entry_timestamps_must_be_timezone_aware() -> None:
    with pytest.raises(InvalidDomainObservabilityContractError):
        DomainObservabilityLogEntry(
            source_kind="domain_event",
            source_id="domain-event-123",
            category="resolution",
            status="completed",
            occurred_at=datetime(2026, 8, 31, 12, 0),  # noqa: DTZ001
        )


def test_log_entry_rejects_negative_duration() -> None:
    with pytest.raises(InvalidDomainObservabilityContractError):
        DomainObservabilityLogEntry(
            source_kind="domain_trace",
            source_id="domain-trace-123",
            category="result",
            status="completed",
            occurred_at=NOW,
            duration_ms=-1,
        )


def test_log_entry_rejects_blank_required_fields() -> None:
    with pytest.raises(InvalidDomainObservabilityContractError):
        DomainObservabilityLogEntry(
            source_kind=" ",
            source_id="domain-event-123",
            category="resolution",
            status="completed",
            occurred_at=NOW,
        )


def _health_result(
    *,
    status: DomainHealthStatus = DomainHealthStatus.HEALTHY,
    **overrides: object,
) -> DomainHealthResult:
    values: dict[str, object] = {
        "manifest": True,
        "registry": True,
        "resources": True,
        "rules": True,
        "operations": True,
        "workflows": True,
        "permissions": True,
        "dependencies": True,
    }
    values.update(overrides)
    return DomainHealthResult(
        domain_id="domain:health",
        status=status,
        last_checked_at=NOW,
        **values,  # type: ignore[arg-type]
    )


def test_health_timestamps_must_be_timezone_aware() -> None:
    with pytest.raises(InvalidDomainObservabilityContractError):
        DomainHealthResult(
            domain_id="domain:health",
            status=DomainHealthStatus.HEALTHY,
            manifest=True,
            registry=True,
            resources=True,
            rules=True,
            operations=True,
            workflows=True,
            permissions=True,
            dependencies=True,
            last_checked_at=datetime(2026, 8, 31, 12, 0),  # noqa: DTZ001
        )


def test_health_result_rejects_blocking_finding_when_healthy() -> None:
    blocking = DomainHealthFinding(
        code="DOMAIN_HEALTH_REQUIRED_DEPENDENCY_MISSING",
        component="dependencies",
        severity="critical",
        message="Required dependency is missing",
        reference_ids=("domain:health",),
        blocking=True,
    )

    with pytest.raises(InvalidDomainObservabilityContractError):
        _health_result(findings=(blocking,))


def test_health_result_rejects_healthy_status_with_unverified_dimension() -> None:
    with pytest.raises(InvalidDomainObservabilityContractError):
        _health_result(resources=False)


def test_health_result_rejects_non_strict_booleans() -> None:
    with pytest.raises(InvalidDomainObservabilityContractError):
        DomainHealthResult(
            domain_id="domain:health",
            status=DomainHealthStatus.DEGRADED,
            manifest=True,
            registry=True,
            resources=1,  # type: ignore[arg-type]
            rules=True,
            operations=True,
            workflows=True,
            permissions=True,
            dependencies=True,
            last_checked_at=NOW,
        )


def test_health_finding_rejects_blank_fields() -> None:
    with pytest.raises(InvalidDomainObservabilityContractError):
        DomainHealthFinding(
            code="",
            component="permissions",
            severity="warning",
            message="Permission policy could not be positively verified",
        )


def _measurement() -> DomainMetricMeasurement:
    return DomainMetricMeasurement(
        name="domains.installed",
        status=DomainMetricStatus.OBSERVED,
        unit="count",
        value=2,
        evidence_reference_ids=("domain:general", "domain:health"),
    )


def _snapshot() -> DomainMetricsSnapshot:
    return DomainMetricsSnapshot(
        generated_at=NOW,
        measurements=(_measurement(),),
        evidence_event_ids=("domain-event-001",),
        evidence_trace_ids=("domain-trace-001",),
        evidence_session_ids=("session-001",),
    )


def _log_entry() -> DomainObservabilityLogEntry:
    return DomainObservabilityLogEntry(
        source_kind="domain_event",
        source_id="domain-event-001",
        category="resolution",
        status="completed",
        occurred_at=NOW,
        primary_domain="domain:health",
        supporting_domains=("domain:general",),
        session_id="session-001",
        duration_ms=12,
        reference_ids=("domain-resolution-123", "domain-trace-123"),
        metadata={"event_type": "domain.resolution.completed"},
    )


def _finding() -> DomainHealthFinding:
    return DomainHealthFinding(
        code="DOMAIN_HEALTH_PERMISSION_POLICY_UNVERIFIED",
        component="permissions",
        severity="warning",
        message="Permission policy could not be positively verified",
        reference_ids=("domain:health",),
        blocking=False,
    )


def _health() -> DomainHealthResult:
    return _health_result(status=DomainHealthStatus.HEALTHY)


def _report() -> DomainObservabilityReport:
    return DomainObservabilityReport(
        generated_at=NOW,
        log_entries=(_log_entry(),),
        metrics=_snapshot(),
        health_results=(_health(),),
        source_event_ids=("domain-event-001",),
        source_trace_ids=("domain-trace-001",),
        source_session_ids=("session-001",),
        findings=(),
    )


def test_snapshot_rejects_inconsistent_supplied_digest() -> None:
    with pytest.raises(InvalidDomainObservabilityContractError):
        DomainMetricsSnapshot(
            generated_at=NOW,
            measurements=(_measurement(),),
            digest="0" * 64,
        )


def test_snapshot_rejects_duplicate_measurement_names() -> None:
    with pytest.raises(InvalidDomainObservabilityContractError):
        DomainMetricsSnapshot(
            generated_at=NOW,
            measurements=(_measurement(), _measurement()),
        )


def test_report_rejects_inconsistent_supplied_digest() -> None:
    with pytest.raises(InvalidDomainObservabilityContractError):
        DomainObservabilityReport(
            generated_at=NOW,
            log_entries=(_log_entry(),),
            metrics=_snapshot(),
            health_results=(_health(),),
            digest="0" * 64,
        )


def test_report_rejects_naive_generated_at() -> None:
    with pytest.raises(InvalidDomainObservabilityContractError):
        DomainObservabilityReport(
            generated_at=datetime(2026, 8, 31, 12, 0),  # noqa: DTZ001
            log_entries=(),
            metrics=_snapshot(),
            health_results=(),
        )


def test_contracts_are_frozen() -> None:
    measurement = _measurement()
    with pytest.raises((AttributeError, TypeError)):
        measurement.value = 5  # type: ignore[misc]

    entry = _log_entry()
    with pytest.raises((AttributeError, TypeError)):
        entry.status = "mutated"  # type: ignore[misc]

    health = _health()
    with pytest.raises((AttributeError, TypeError)):
        health.status = DomainHealthStatus.UNHEALTHY  # type: ignore[misc]
