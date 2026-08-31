"""Phase 10.37 — Domain Observability evidence identity, deduplication and
source precedence tests.

Proves deterministic evidence identity rules: identical authoritative IDs are
counted once, conflicting duplicates fail closed without echoing unsafe
payloads, and event/trace overlap is deduplicated by stable reference identity
instead of string similarity.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from cmm.domains.contracts import DomainId
from cmm.domains.enums import DomainOperationStatus
from cmm.domains.errors import InvalidDomainObservabilityEvidenceError
from cmm.domains.event_contracts import DomainEvent
from cmm.domains.health.bootstrap import (
    build_standard_health_domain_bootstrap,
)
from cmm.domains.observability_contracts import (
    DomainObservabilityReport,
)
from cmm.domains.observability_health import DomainHealthChecker
from cmm.domains.observability_metrics import (
    DomainMetricsCalculator,
    DomainObservabilityEvidence,
)
from cmm.domains.observability_service import DomainObservabilityService
from cmm.domains.operation_contracts import DomainOperationResult
from cmm.domains.resolver_contracts import (
    DomainResolutionResult,
    DomainResolutionStatus,
)

NOW = datetime(2026, 8, 31, 12, 0, 0, tzinfo=timezone.utc)


def _event(
    event_id: str, *, event_type: str = "domain.resolution.completed"
) -> DomainEvent:
    return DomainEvent(
        event_id=event_id,
        event_type=event_type,
        schema_version="1.0",
        domain_id=DomainId.from_str("domain:health"),
        actor="orchestrator",
        occurred_at=NOW,
        sensitivity="internal",
    )


def _resolution(
    result_id: str,
    *,
    status: DomainResolutionStatus = DomainResolutionStatus.RESOLVED,
    confidence: float = 0.9,
) -> DomainResolutionResult:
    return DomainResolutionResult(
        id=result_id,
        context_id=f"ctx-{result_id}",
        status=status,
        primary_domain=DomainId.from_str("domain:health"),
        confidence=confidence,
    )


def test_duplicate_identical_event_is_counted_once() -> None:
    first = _event("event-dedup-1")
    second = _event("event-dedup-1")

    snapshot = DomainMetricsCalculator().calculate(
        DomainObservabilityEvidence(events=(first, second)),
        generated_at=NOW,
    )

    assert snapshot.evidence_event_ids == ("event-dedup-1",)
    # Snapshot digest is deterministic despite duplicate input.
    assert len(snapshot.digest) == 64


def test_duplicate_conflicting_event_fails_closed() -> None:
    first = _event("event-conflict-1", event_type="domain.resolution.completed")
    second = _event("event-conflict-1", event_type="domain.resolution.started")

    with pytest.raises(InvalidDomainObservabilityEvidenceError) as exc_info:
        DomainMetricsCalculator().calculate(
            DomainObservabilityEvidence(events=(first, second)),
            generated_at=NOW,
        )

    details = dict(exc_info.value.details)
    assert details["source_type"] == "DomainEvent"
    assert details["source_id"] == "event-conflict-1"
    # No unsafe payload echo.
    rendered = str(exc_info.value.__dict__)
    assert "event-conflict-1" in rendered
    assert "resolution.completed" not in rendered or "started" not in rendered


def test_duplicate_identical_resolution_is_counted_once() -> None:
    first = _resolution("res-dedup-1")
    second = _resolution("res-dedup-1")

    snapshot = DomainMetricsCalculator().calculate(
        DomainObservabilityEvidence(resolution_results=(first, second)),
        generated_at=NOW,
    )

    measurement = {item.name: item for item in snapshot.measurements}[
        "resolution.decisions_by_domain"
    ]
    assert {bucket.key: bucket.value for bucket in measurement.buckets} == {
        "domain:health": 1
    }
    assert len(snapshot.digest) == 64


def test_duplicate_conflicting_resolution_fails_closed() -> None:
    first = _resolution("res-conflict-1", confidence=0.9)
    second = _resolution("res-conflict-1", confidence=0.4)

    with pytest.raises(InvalidDomainObservabilityEvidenceError) as exc_info:
        DomainMetricsCalculator().calculate(
            DomainObservabilityEvidence(resolution_results=(first, second)),
            generated_at=NOW,
        )

    details = dict(exc_info.value.details)
    assert details["source_type"] == "DomainResolutionResult"
    assert details["source_id"] == "res-conflict-1"


def test_duplicate_is_deterministic_across_runs() -> None:
    first_run = DomainMetricsCalculator().calculate(
        DomainObservabilityEvidence(events=(_event("evt-a"), _event("evt-a"))),
        generated_at=NOW,
    )
    second_run = DomainMetricsCalculator().calculate(
        DomainObservabilityEvidence(events=(_event("evt-a"),)),
        generated_at=NOW,
    )

    assert first_run.to_dict() == second_run.to_dict()
    assert first_run.digest == second_run.digest


def test_event_and_operation_result_with_shared_reference_count_once() -> None:
    """One operation occurrence in both a DomainEvent and an operation result
    is counted once by stable reference identity."""
    event = DomainEvent(
        event_id="event-op-1",
        event_type="domain.operation.completed",
        schema_version="1.0",
        domain_id=DomainId.from_str("domain:health"),
        actor="orchestrator",
        occurred_at=NOW,
        sensitivity="internal",
        payload={},
        metadata={"operation_id": "op-1"},
    )
    operation = DomainOperationResult(
        result_id="op-res-ref-1",
        request_id="req-1",
        operation_id="op-1",
        operation_version="1.0.0",
        domain_id="domain:health",
        status=DomainOperationStatus.COMPLETED,
        started_at=NOW,
        completed_at=NOW,
    )

    snapshot = DomainMetricsCalculator().calculate(
        DomainObservabilityEvidence(
            events=(event,),
            operation_evidence=(operation,),
        ),
        generated_at=NOW,
    )

    metrics = {item.name: item for item in snapshot.measurements}
    operations = metrics["operations.by_domain"]
    assert {bucket.key: bucket.value for bucket in operations.buckets} == {
        "domain:health": 1
    }
    assert "event-op-1" in snapshot.evidence_event_ids


# ── DomainObservabilityService projection ───────────────────────────────────


def _service() -> DomainObservabilityService:
    bootstrap = build_standard_health_domain_bootstrap()
    health_checker = DomainHealthChecker(
        domain_registry=bootstrap.domain_registry,
        resource_registry=bootstrap.resource_registry,
        rule_registry=bootstrap.rule_registry,
        operation_registry=bootstrap.operation_registry,
        workflow_registry=bootstrap.workflow_registry,
        permission_registry=bootstrap.permission_registry,
        manifest_validation_lookup=lambda domain_id: None,
        clock=lambda: NOW,
    )
    return DomainObservabilityService(
        metrics_calculator=DomainMetricsCalculator(),
        health_checker=health_checker,
        clock=lambda: NOW,
    )


def test_service_builds_report_with_event_log_entries() -> None:
    event = DomainEvent(
        event_id="event-log-1",
        event_type="domain.resolution.completed",
        schema_version="1.0",
        domain_id=DomainId.from_str("domain:health"),
        actor="orchestrator",
        occurred_at=NOW,
        sensitivity="internal",
        payload={"objective": "arbitrary upstream payload content blocks"},
        metadata={"cross_reference": "arbitrary upstream metadata value"},
    )

    service = _service()
    report = service.build_report(
        DomainObservabilityEvidence(events=(event,)),
        health_domain_ids=("domain:health",),
    )

    assert isinstance(report, DomainObservabilityReport)
    assert len(report.log_entries) == 1
    entry = report.log_entries[0]
    assert entry.source_kind == "domain_event"
    assert entry.source_id == "event-log-1"
    assert entry.primary_domain == "domain:health"
    # Raw payload/metadata must never be copied wholesale.
    assert "arbitrary upstream payload content blocks" not in str(report.to_dict())
    assert "arbitrary upstream metadata value" not in str(report.to_dict())


def test_service_calculates_metrics_and_health() -> None:
    resolved = _resolution("res-service-1")
    service = _service()

    snapshot = service.calculate_metrics(
        DomainObservabilityEvidence(resolution_results=(resolved,))
    )
    assert len(snapshot.measurements) == 25

    health = service.check_domain_health("domain:health")
    assert health.domain_id == "domain:health"


def test_service_report_includes_health_results() -> None:
    service = _service()
    report = service.build_report(
        DomainObservabilityEvidence(),
        health_domain_ids=("domain:health",),
    )

    assert len(report.health_results) == 1
    assert report.health_results[0].domain_id == "domain:health"


def test_service_report_digest_is_deterministic() -> None:
    service = _service()
    first = service.build_report(
        DomainObservabilityEvidence(),
        health_domain_ids=("domain:health",),
    )
    second = service.build_report(
        DomainObservabilityEvidence(),
        health_domain_ids=("domain:health",),
    )

    assert first.digest == second.digest
    assert first.to_dict() == second.to_dict()
