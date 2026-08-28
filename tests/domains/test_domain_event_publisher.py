"""Phase 10.33 — Domain Kernel Event Publisher Tests.

Tests covering:
- Conversion of DomainEvent to kernel.events.Event preserving name, timestamp, complete payload
- Registry validation prior to publication
- Unknown event types fail closed without publication
- Listener dispatch and typed publication errors (DomainEventPublicationError)
- Source event immutability across repeated publication
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from cmm.domains.errors import (
    DomainEventPublicationError,
    DomainEventValidationError,
)
from cmm.domains.event_contracts import DomainEvent, DomainEventReference
from cmm.domains.event_publisher import DomainKernelEventPublisher
from cmm.domains.event_registry import DomainEventRegistry
from cmm.domains.identifiers import DomainId
from kernel.events.event import Event


def _make_event(
    event_type: str = "domain.resolution.completed",
    domain_id: DomainId | None = None,
) -> DomainEvent:
    now = datetime(2026, 8, 28, 16, 0, 0, tzinfo=timezone.utc)
    dom_id = domain_id if domain_id is not None else DomainId(slug="project")
    ref = DomainEventReference(
        kind="resolution", reference_id="res-1", domain_id=dom_id
    )
    return DomainEvent(
        event_id="evt-pub-1",
        event_type=event_type,
        schema_version="1.0.0",
        domain_id=dom_id,
        related_domain_ids=(DomainId(slug="general"),),
        actor="orchestrator",
        session_id="sess-001",
        occurred_at=now,
        provenance=(ref,),
        sensitivity="internal",
        permissions=("domain.project.read",),
        correlation_id="corr-1",
        causation_id="caus-1",
        payload={"result": "success", "score": 0.99},
        metadata={"env": "prod"},
    )


# 1. Conversion fidelity
def test_publisher_kernel_event_conversion_fidelity() -> None:
    event = _make_event()
    publisher = DomainKernelEventPublisher()
    kernel_event = publisher.publish(event)

    assert isinstance(kernel_event, Event)
    assert kernel_event.name == event.event_type
    assert kernel_event.timestamp == event.occurred_at
    assert kernel_event.payload == event.to_dict()
    assert len(publisher.emitted_events) == 1
    assert publisher.emitted_events[0] == kernel_event


# 2. Registry validation before publication
def test_publisher_validation_failure_prevents_publication() -> None:
    event = _make_event(event_type="domain.unregistered.event")
    publisher = DomainKernelEventPublisher()

    with pytest.raises(DomainEventValidationError):
        publisher.publish(event)

    assert len(publisher.emitted_events) == 0


# 3. Custom registry support
def test_publisher_with_custom_registry() -> None:
    custom_reg = DomainEventRegistry()
    custom_reg.register_specialized(
        domain_id=DomainId(slug="health"),
        event_type="health.symptom.updated",
    )
    publisher = DomainKernelEventPublisher(registry=custom_reg)
    event = _make_event(
        event_type="health.symptom.updated",
        domain_id=DomainId(slug="health"),
    )
    k_evt = publisher.publish(event)
    assert k_evt.name == "health.symptom.updated"
    assert len(publisher.emitted_events) == 1


# 4. Listener callback dispatch
def test_publisher_listener_dispatch() -> None:
    dispatched: list[Event] = []

    def listener(evt: Event) -> None:
        dispatched.append(evt)

    publisher = DomainKernelEventPublisher(event_listener=listener)
    event = _make_event()
    publisher.publish(event)

    assert len(dispatched) == 1
    assert dispatched[0].name == "domain.resolution.completed"


# 5. Listener error wraps in DomainEventPublicationError
def test_publisher_listener_error_wrapping() -> None:
    def failing_listener(evt: Event) -> None:
        raise RuntimeError("Kernel bus broken")

    publisher = DomainKernelEventPublisher(event_listener=failing_listener)
    event = _make_event()

    with pytest.raises(DomainEventPublicationError) as exc_info:
        publisher.publish(event)

    assert "Failed to deliver domain event" in str(exc_info.value)
    assert exc_info.value.field == "event"
    assert exc_info.value.details["event_type"] == "domain.resolution.completed"


# 6. Event immutability across repeated publication
def test_publisher_does_not_mutate_event_on_repeated_publish() -> None:
    event = _make_event()
    dump1 = event.to_dict()
    publisher = DomainKernelEventPublisher()

    publisher.publish(event)
    assert event.to_dict() == dump1

    publisher.publish(event)
    assert event.to_dict() == dump1
    assert len(publisher.emitted_events) == 2
