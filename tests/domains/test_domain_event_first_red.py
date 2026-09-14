"""Phase 10.33 — First RED cycle for Domain Events.

Tests covering:
1. exact 23-event canonical catalog;
2. construction of one valid DomainEvent;
3. rejection of one invalid/unsafe DomainEvent;
4. conversion of a valid Domain Event into kernel.events.Event without semantic loss.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from cmm.domains.errors import DomainContractValidationError
from cmm.domains.event_catalog import CANONICAL_DOMAIN_EVENTS
from cmm.domains.event_contracts import DomainEvent, DomainEventReference
from cmm.domains.event_publisher import DomainKernelEventPublisher
from cmm.domains.identifiers import DomainId
from kernel.events.event import Event


# 1. Exact 23-event canonical catalog
def test_first_red_canonical_catalog_exact_23() -> None:
    expected_events = {
        "domain.resolution.started",
        "domain.resolution.completed",
        "domain.resolution.ambiguous",
        "domain.composition.created",
        "domain.composition.updated",
        "domain.execution.started",
        "domain.execution.completed",
        "domain.execution.failed",
        "domain.conflict.detected",
        "domain.conflict.resolved",
        "domain.permission.requested",
        "domain.permission.denied",
        "domain.approval.requested",
        "domain.approval.received",
        "domain.memory.proposed",
        "domain.memory.updated",
        "domain.workflow.started",
        "domain.workflow.paused",
        "domain.workflow.resumed",
        "domain.workflow.completed",
        "domain.operation.started",
        "domain.operation.completed",
        "domain.operation.failed",
    }
    assert len(CANONICAL_DOMAIN_EVENTS) == 23
    assert set(CANONICAL_DOMAIN_EVENTS) == expected_events


# 2. Construction of one valid DomainEvent
def test_first_red_construct_valid_domain_event() -> None:
    now = datetime(2026, 8, 28, 12, 0, 0, tzinfo=timezone.utc)
    ref = DomainEventReference(
        kind="resolution",
        reference_id="res-123",
        domain_id=DomainId(slug="project"),
    )
    event = DomainEvent(
        event_id="evt-001",
        event_type="domain.resolution.completed",
        schema_version="1.0.0",
        domain_id=DomainId(slug="project"),
        related_domain_ids=(DomainId(slug="general"),),
        actor="agent-1",
        session_id="sess-abc",
        occurred_at=now,
        provenance=(ref,),
        sensitivity="internal",
        permissions=("domain.project.read",),
        correlation_id="corr-1",
        causation_id="caus-1",
        payload={"status": "resolved", "score": 0.95},
        metadata={"source": "test"},
    )
    assert event.event_id == "evt-001"
    assert event.event_type == "domain.resolution.completed"
    assert event.domain_id == DomainId(slug="project")
    assert event.occurred_at == now
    assert event.payload["status"] == "resolved"


# 3. Rejection of invalid / unsafe DomainEvent
def test_first_red_reject_unsafe_domain_event() -> None:
    now = datetime(2026, 8, 28, 12, 0, 0, tzinfo=timezone.utc)
    # Reject credential key in payload
    with pytest.raises(DomainContractValidationError):
        DomainEvent(
            event_id="evt-unsafe",
            event_type="domain.execution.started",
            schema_version="1.0.0",
            domain_id=DomainId(slug="project"),
            actor="agent-1",
            occurred_at=now,
            sensitivity="internal",
            payload={"api_key": "secret_value_123"},
        )


# 4. Conversion of a valid Domain Event into kernel.events.Event without semantic loss
def test_first_red_kernel_event_conversion_lossless() -> None:
    now = datetime(2026, 8, 28, 12, 0, 0, tzinfo=timezone.utc)
    ref = DomainEventReference(
        kind="resolution",
        reference_id="res-123",
        domain_id=DomainId(slug="project"),
    )
    event = DomainEvent(
        event_id="evt-001",
        event_type="domain.resolution.completed",
        schema_version="1.0.0",
        domain_id=DomainId(slug="project"),
        related_domain_ids=(DomainId(slug="general"),),
        actor="agent-1",
        session_id="sess-abc",
        occurred_at=now,
        provenance=(ref,),
        sensitivity="internal",
        permissions=("domain.project.read",),
        correlation_id="corr-1",
        causation_id="caus-1",
        payload={"status": "resolved", "score": 0.95},
        metadata={"source": "test"},
    )
    publisher = DomainKernelEventPublisher()
    kernel_event = publisher.publish(event)

    assert isinstance(kernel_event, Event)
    assert kernel_event.name == "domain.resolution.completed"
    assert kernel_event.timestamp == now
    assert isinstance(kernel_event.payload, dict)
    assert kernel_event.payload["event_id"] == "evt-001"
    assert kernel_event.payload["event_type"] == "domain.resolution.completed"
    assert kernel_event.payload["domain_id"] == {"slug": "project"}
    assert kernel_event.payload["payload"] == {"status": "resolved", "score": 0.95}
    assert kernel_event.payload["provenance"] == [
        {
            "kind": "resolution",
            "reference_id": "res-123",
            "domain_id": {"slug": "project"},
        }
    ]
