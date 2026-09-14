"""Phase 10.33 — Domain Event Factory Tests.

Tests covering:
- Deterministic event construction with injected clock and id_factory
- Default clock and id_factory generation
- Contract validation via factory
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from cmm.domains.errors import DomainContractValidationError
from cmm.domains.event_factory import DomainEventFactory
from cmm.domains.identifiers import DomainId


def test_factory_deterministic_injected_clock_and_id() -> None:
    fixed_time = datetime(2026, 8, 28, 15, 0, 0, tzinfo=timezone.utc)
    id_counter = 0

    def mock_clock() -> datetime:
        return fixed_time

    def mock_id_factory() -> str:
        nonlocal id_counter
        id_counter += 1
        return f"evt-injected-{id_counter}"

    factory = DomainEventFactory(clock=mock_clock, id_factory=mock_id_factory)

    evt1 = factory.create_event(
        event_type="domain.resolution.started",
        domain_id=DomainId(slug="project"),
        actor="system",
        sensitivity="internal",
    )
    assert evt1.event_id == "evt-injected-1"
    assert evt1.occurred_at == fixed_time
    assert evt1.event_type == "domain.resolution.started"
    assert evt1.domain_id == DomainId(slug="project")

    evt2 = factory.create_event(
        event_type="domain.resolution.completed",
        domain_id=DomainId(slug="project"),
        actor="system",
        sensitivity="internal",
    )
    assert evt2.event_id == "evt-injected-2"
    assert evt2.occurred_at == fixed_time


def test_factory_explicit_overrides() -> None:
    custom_time = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    factory = DomainEventFactory()

    evt = factory.create_event(
        event_type="domain.execution.started",
        domain_id="domain:health",
        actor="agent-alpha",
        sensitivity="confidential",
        event_id="explicit-id-999",
        occurred_at=custom_time,
        session_id="sess-xyz",
        permissions=("domain.health.read",),
        payload={"task": "diagnostic"},
    )
    assert evt.event_id == "explicit-id-999"
    assert evt.occurred_at == custom_time
    assert evt.domain_id == DomainId(slug="health")
    assert evt.session_id == "sess-xyz"
    assert evt.permissions == ("domain.health.read",)
    assert evt.payload["task"] == "diagnostic"


def test_factory_validates_and_rejects_unsafe_payload() -> None:
    factory = DomainEventFactory()
    with pytest.raises(DomainContractValidationError):
        factory.create_event(
            event_type="domain.execution.started",
            domain_id=DomainId(slug="project"),
            actor="agent-1",
            payload={"password": "plain_password"},
        )
