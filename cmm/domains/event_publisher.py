"""Phase 10.33 — Domain-to-Kernel Event Publisher.

Publishes validated Domain Intelligence events to the Kernel Event boundary
using the existing kernel.events.Event envelope.
"""

from __future__ import annotations

from collections.abc import Callable

from cmm.domains.errors import DomainEventPublicationError
from cmm.domains.event_contracts import DomainEvent
from cmm.domains.event_registry import (
    DEFAULT_DOMAIN_EVENT_REGISTRY,
    DomainEventRegistry,
)
from kernel.events.event import Event


class DomainKernelEventPublisher:
    """Publishes validated Domain Events to Kernel subscribers or listeners."""

    def __init__(
        self,
        event_listener: Callable[[Event], None] | None = None,
        registry: DomainEventRegistry | None = None,
    ) -> None:
        """Initialize the publisher.

        Args:
            event_listener: Optional callback receiving kernel.events.Event.
            registry: DomainEventRegistry for event validation (defaults to global registry).
        """
        self._listener = event_listener
        self._registry = registry or DEFAULT_DOMAIN_EVENT_REGISTRY
        self._emitted_events: list[Event] = []

    @property
    def emitted_events(self) -> tuple[Event, ...]:
        """Return an immutable snapshot of all published Kernel events."""
        return tuple(self._emitted_events)

    def publish(self, event: DomainEvent) -> Event:
        """Validate and publish a DomainEvent as a kernel.events.Event.

        Args:
            event: The DomainEvent instance to publish.

        Returns:
            The created and published kernel.events.Event object.

        Raises:
            DomainEventValidationError: If event fails registry validation.
            DomainEventPublicationError: If listener callback fails.
        """
        # 1. Validate through registry (fails closed on unknown event types)
        self._registry.validate_event(event)

        # 2. Convert to kernel.events.Event with complete public payload
        kernel_event = Event(
            name=event.event_type,
            payload=event.to_dict(),
            timestamp=event.occurred_at,
        )

        # 3. Deliver to listener and record only upon successful delivery
        try:
            if self._listener is not None:
                self._listener(kernel_event)
            self._emitted_events.append(kernel_event)
        except Exception as exc:
            raise DomainEventPublicationError(
                f"Failed to deliver domain event '{event.event_type}' to kernel listener: {exc}",
                field="event",
                details={"event_type": event.event_type, "event_id": event.event_id},
            ) from exc

        return kernel_event
