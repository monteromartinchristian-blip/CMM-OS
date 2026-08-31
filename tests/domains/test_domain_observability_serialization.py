"""Phase 10.37 — Domain Observability serialization tests.

Proves deterministic JSON-safe serialization, digest integrity and
round-tripping for the observability read models.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from cmm.domains.errors import (
    DomainSerializationError,
    InvalidDomainObservabilityContractError,
)
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


def _measurement() -> DomainMetricMeasurement:
    return DomainMetricMeasurement(
        name="resolution.decisions_by_domain",
        status=DomainMetricStatus.OBSERVED,
        unit="count",
        buckets=(
            DomainMetricBucket(key="domain:general", value=3),
            DomainMetricBucket(key="domain:health", value=7),
        ),
        evidence_reference_ids=("domain-event-001", "domain-event-002"),
        metadata={"sensitivity": "internal"},
    )


def _unavailable_measurement() -> DomainMetricMeasurement:
    return DomainMetricMeasurement(
        name="knowledge.reused",
        status=DomainMetricStatus.UNAVAILABLE,
        unit="count",
        unavailable_reason="NO_KNOWLEDGE_REUSE_EVIDENCE",
    )


def _snapshot() -> DomainMetricsSnapshot:
    return DomainMetricsSnapshot(
        generated_at=NOW,
        measurements=(_measurement(), _unavailable_measurement()),
        evidence_event_ids=("domain-event-001", "domain-event-002"),
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
        reference_ids=("domain-resolution-123",),
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
    return DomainHealthResult(
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
        last_checked_at=NOW,
        findings=(_finding(),),
    )


def _report() -> DomainObservabilityReport:
    return DomainObservabilityReport(
        generated_at=NOW,
        log_entries=(_log_entry(),),
        metrics=_snapshot(),
        health_results=(_health(),),
        source_event_ids=("domain-event-001",),
        source_trace_ids=("domain-trace-001",),
        source_session_ids=("session-001",),
    )


def test_bucket_serialization_round_trips() -> None:
    bucket = DomainMetricBucket(key="domain:health", value=7)

    payload = bucket.to_dict()

    assert payload == {"key": "domain:health", "value": 7}
    assert DomainMetricBucket.from_dict(payload) == bucket


def test_measurement_serialization_is_json_safe() -> None:
    payload = _measurement().to_dict()

    encoded = json.dumps(payload, ensure_ascii=False)
    assert isinstance(encoded, str)
    assert payload["name"] == "resolution.decisions_by_domain"
    assert payload["status"] == "observed"


def test_measurement_round_trips() -> None:
    measurement = _measurement()

    restored = DomainMetricMeasurement.from_dict(measurement.to_dict())

    assert restored == measurement


def test_unavailable_measurement_round_trips() -> None:
    measurement = _unavailable_measurement()

    restored = DomainMetricMeasurement.from_dict(measurement.to_dict())

    assert restored == measurement
    assert restored.value is None
    assert restored.unavailable_reason == "NO_KNOWLEDGE_REUSE_EVIDENCE"


def test_snapshot_digest_is_deterministic_and_excludes_itself() -> None:
    first = _snapshot()
    second = _snapshot()

    assert first.digest != ""
    assert len(first.digest) == 64
    assert first.digest == second.digest


def test_snapshot_digest_changes_with_content() -> None:
    snapshot = _snapshot()
    changed = DomainMetricsSnapshot(
        generated_at=NOW,
        measurements=(
            DomainMetricMeasurement(
                name="domains.installed",
                status=DomainMetricStatus.OBSERVED,
                unit="count",
                value=9,
            ),
            _unavailable_measurement(),
        ),
        evidence_event_ids=("domain-event-001", "domain-event-002"),
        evidence_trace_ids=("domain-trace-001",),
        evidence_session_ids=("session-001",),
    )

    assert snapshot.digest != changed.digest


def test_snapshot_round_trips() -> None:
    snapshot = _snapshot()

    restored = DomainMetricsSnapshot.from_dict(snapshot.to_dict())

    assert restored == snapshot
    assert restored.digest == snapshot.digest


def test_log_entry_round_trips() -> None:
    entry = _log_entry()

    restored = DomainObservabilityLogEntry.from_dict(entry.to_dict())

    assert restored == entry


def test_health_finding_round_trips() -> None:
    finding = _finding()

    restored = DomainHealthFinding.from_dict(finding.to_dict())

    assert restored == finding


def test_health_result_round_trips() -> None:
    health = _health()

    restored = DomainHealthResult.from_dict(health.to_dict())

    assert restored == health


def test_report_digest_is_deterministic() -> None:
    first = _report()
    second = _report()

    assert first.digest != ""
    assert len(first.digest) == 64
    assert first.digest == second.digest


def test_report_round_trips() -> None:
    report = _report()

    restored = DomainObservabilityReport.from_dict(report.to_dict())

    assert restored == report


def test_report_serialization_is_json_safe() -> None:
    encoded = json.dumps(_report().to_dict(), ensure_ascii=False)

    assert isinstance(encoded, str)


def test_from_dict_rejects_unknown_fields() -> None:
    payload = _measurement().to_dict()
    payload["unexpected"] = "value"

    with pytest.raises(DomainSerializationError):
        DomainMetricMeasurement.from_dict(payload)


def test_from_dict_rejects_non_mapping() -> None:
    with pytest.raises(DomainSerializationError):
        DomainMetricMeasurement.from_dict(["not", "a", "mapping"])  # type: ignore[arg-type]


def test_from_dict_rejects_invalid_timestamp() -> None:
    payload = _log_entry().to_dict()
    payload["occurred_at"] = "not-a-timestamp"

    with pytest.raises(DomainSerializationError):
        DomainObservabilityLogEntry.from_dict(payload)


def test_from_dict_rejects_invalid_digest() -> None:
    payload = _snapshot().to_dict()
    payload["digest"] = "not-a-digest"

    with pytest.raises(DomainSerializationError):
        DomainMetricsSnapshot.from_dict(payload)


def test_from_dict_rejects_invalid_health_status() -> None:
    payload = _health().to_dict()
    payload["status"] = "fantastic"

    with pytest.raises(DomainSerializationError):
        DomainHealthResult.from_dict(payload)


def test_from_dict_rejects_invalid_metric_status() -> None:
    payload = _measurement().to_dict()
    payload["status"] = "estimated"

    with pytest.raises(DomainSerializationError):
        DomainMetricMeasurement.from_dict(payload)


def test_from_dict_rejects_contract_violation() -> None:
    payload = _measurement().to_dict()
    payload["status"] = "unavailable"
    payload["value"] = 5

    with pytest.raises(InvalidDomainObservabilityContractError):
        DomainMetricMeasurement.from_dict(payload)
