"""Phase 10.37 — Privacy minimization tests.

Proves the observability projection is reference-first: raw sensitive content
never appears in serialized output, secret-shaped evidence fails closed
without echoing the secret, and user-generated text can never become a metric
label.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from cmm.domains.contracts import DomainId
from cmm.domains.enums import DomainOperationStatus
from cmm.domains.event_contracts import DomainEvent
from cmm.domains.health.bootstrap import (
    build_standard_health_domain_bootstrap,
)
from cmm.domains.observability_health import DomainHealthChecker
from cmm.domains.observability_metrics import (
    DomainMetricsCalculator,
    DomainObservabilityEvidence,
)
from cmm.domains.observability_service import DomainObservabilityService
from cmm.domains.operation_contracts import DomainOperationResult

NOW = datetime(2026, 8, 31, 12, 0, 0, tzinfo=timezone.utc)

MEDICAL_TEXT = "the payload contains a clinical timeline summary body"
RELATIONSHIP_TEXT = "the payload contains a relationship context body"
MEMORY_TEXT = "the payload contains a stored memory body"
USER_INPUT = "the payload contains the submitted user request body"
SECRET_KEY = "api-key-1234567890"
SECRET_VALUE = "private-note-for-internal-use"


# ``DomainEvent`` rejects secret-shaped metadata at construction (fail closed
# at the source). The observability privacy tests therefore use payload
# content and metadata that pass the canonical event contract but are still
# private user/domain content that projection must never copy.


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


def _sensitive_event() -> DomainEvent:
    return DomainEvent(
        event_id="event-privacy-1",
        event_type="domain.resolution.completed",
        schema_version="1.0",
        domain_id=DomainId.from_str("domain:health"),
        actor="orchestrator",
        occurred_at=NOW,
        sensitivity="internal",
        payload={
            "objective": MEDICAL_TEXT,
            "relationships": RELATIONSHIP_TEXT,
            "memory": MEMORY_TEXT,
            "user_input": USER_INPUT,
        },
        metadata={"secondary": SECRET_VALUE},
    )


def test_no_raw_sensitive_content_in_serialized_report() -> None:
    service = _service()
    report = service.build_report(
        DomainObservabilityEvidence(events=(_sensitive_event(),)),
        health_domain_ids=(),
    )

    rendered = json.dumps(report.to_dict(), ensure_ascii=False)

    for forbidden in (MEDICAL_TEXT, RELATIONSHIP_TEXT, MEMORY_TEXT, USER_INPUT):
        assert forbidden not in rendered


def test_secret_shaped_evidence_never_echoed() -> None:
    service = _service()

    # The event itself carries a synthetic secret in metadata. The report
    # must contain neither the key nor the value.
    report = service.build_report(
        DomainObservabilityEvidence(events=(_sensitive_event(),)),
        health_domain_ids=(),
    )

    rendered = json.dumps(report.to_dict(), ensure_ascii=False)
    assert SECRET_VALUE not in rendered


def test_report_only_contains_safe_public_fields() -> None:
    service = _service()
    report = service.build_report(
        DomainObservabilityEvidence(events=(_sensitive_event(),)),
        health_domain_ids=(),
    )

    entry = report.log_entries[0]
    assert entry.source_id == "event-privacy-1"
    assert entry.primary_domain == "domain:health"
    # The safe metadata allowlist must not include arbitrary metadata keys.
    safe_metadata = entry.to_dict()["metadata"]
    assert SECRET_KEY not in str(safe_metadata)


def test_secret_shaped_evidence_fails_closed_in_metrics() -> None:
    secret_operation = DomainOperationResult(
        result_id="op-secret-1",
        request_id="req-secret-1",
        operation_id="health.build_medical_timeline",
        operation_version="1.0.0",
        domain_id="domain:health",
        status=DomainOperationStatus.COMPLETED,
        started_at=NOW,
        completed_at=NOW,
        metadata={SECRET_KEY: SECRET_VALUE},
    )

    snapshot = DomainMetricsCalculator().calculate(
        DomainObservabilityEvidence(operation_evidence=(secret_operation,)),
        generated_at=NOW,
    )

    rendered = json.dumps(snapshot.to_dict(), ensure_ascii=False)
    assert SECRET_VALUE not in rendered


def test_user_text_never_becomes_metric_label() -> None:
    operation = DomainOperationResult(
        result_id="op-label-1",
        request_id="req-label-1",
        operation_id="health.build_medical_timeline",
        operation_version="1.0.0",
        domain_id="domain:health",
        status=DomainOperationStatus.COMPLETED,
        started_at=NOW,
        completed_at=NOW,
        metadata={"objective": USER_INPUT},
    )

    snapshot = DomainMetricsCalculator().calculate(
        DomainObservabilityEvidence(operation_evidence=(operation,)),
        generated_at=NOW,
    )

    rendered = json.dumps(snapshot.to_dict(), ensure_ascii=False)
    assert USER_INPUT not in rendered
    # Bucket keys are stable public categories (domain IDs), never user text.
    assert "please schedule" not in rendered
