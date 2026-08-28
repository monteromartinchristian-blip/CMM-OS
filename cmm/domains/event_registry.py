"""Phase 10.33 — Domain Event Registry.

Declares and validates built-in and specialized Domain Intelligence events.
All 23 general events are built-in, immutable, and cannot be overridden.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from cmm.domains.errors import (
    DomainEventRegistryError,
    DomainEventValidationError,
)
from cmm.domains.event_catalog import (
    CANONICAL_DOMAIN_EVENTS,
    is_canonical_general_event,
    validate_event_type_syntax,
    validate_specialized_event_namespace,
)
from cmm.domains.event_contracts import DomainEvent
from cmm.domains.identifiers import DomainId


@dataclass(frozen=True, slots=True)
class DomainEventDeclaration:
    """Declaration of a registered domain event type."""

    event_type: str
    domain_id: DomainId | None
    schema_version: str = "1.0.0"
    is_builtin: bool = False
    validator: Callable[[DomainEvent], None] | None = None
    description: str = ""


class DomainEventRegistry:
    """Registry for Domain Intelligence event types."""

    def __init__(self) -> None:
        self._declarations: dict[str, DomainEventDeclaration] = {}
        self._initialize_builtins()

    def _initialize_builtins(self) -> None:
        """Register the exact 23 canonical general domain events."""
        for event_type in CANONICAL_DOMAIN_EVENTS:
            self._declarations[event_type] = DomainEventDeclaration(
                event_type=event_type,
                domain_id=None,
                schema_version="1.0.0",
                is_builtin=True,
                description=f"Built-in canonical general domain event: {event_type}",
            )

    def is_registered(self, event_type: str) -> bool:
        """Check if an event type is registered."""
        return event_type in self._declarations

    def get_declaration(self, event_type: str) -> DomainEventDeclaration | None:
        """Get declaration for a registered event type."""
        return self._declarations.get(event_type)

    def register_specialized(
        self,
        domain_id: DomainId | str,
        event_type: str,
        schema_version: str = "1.0.0",
        validator: Callable[[DomainEvent], None] | None = None,
        description: str = "",
    ) -> None:
        """Register a specialized domain event owned by a Domain Pack."""
        if isinstance(domain_id, str):
            domain_id = (
                DomainId.from_str(domain_id)
                if domain_id.startswith("domain:")
                else DomainId(slug=domain_id)
            )
        elif not isinstance(domain_id, DomainId):
            raise DomainEventRegistryError(
                f"domain_id must be DomainId or str, got {type(domain_id).__name__}",
                field="domain_id",
            )

        if not validate_event_type_syntax(event_type):
            raise DomainEventRegistryError(
                f"Invalid event_type syntax: {event_type!r}",
                field="event_type",
            )

        if is_canonical_general_event(event_type):
            raise DomainEventRegistryError(
                f"Cannot override built-in general domain event: {event_type!r}",
                field="event_type",
            )

        if not validate_specialized_event_namespace(event_type, domain_id):
            raise DomainEventRegistryError(
                f"Specialized event {event_type!r} does not match owning domain namespace for {domain_id}",
                field="event_type",
            )

        if event_type in self._declarations:
            raise DomainEventRegistryError(
                f"Event type {event_type!r} is already registered",
                field="event_type",
            )

        self._declarations[event_type] = DomainEventDeclaration(
            event_type=event_type,
            domain_id=domain_id,
            schema_version=schema_version,
            is_builtin=False,
            validator=validator,
            description=description,
        )

    def validate_event(self, event: DomainEvent) -> None:
        """Validate an event against the registry. Fails closed on unknown event types."""
        decl = self._declarations.get(event.event_type)
        if decl is None:
            raise DomainEventValidationError(
                f"Unknown event type: {event.event_type!r}",
                field="event_type",
            )

        if (
            not decl.is_builtin
            and decl.domain_id is not None
            and event.domain_id != decl.domain_id
        ):
            raise DomainEventValidationError(
                f"Event domain {event.domain_id} does not match registered domain {decl.domain_id} for {event.event_type}",
                field="domain_id",
            )

        if decl.validator is not None:
            decl.validator(event)

    def list_declarations(self) -> tuple[DomainEventDeclaration, ...]:
        """Return all registered declarations."""
        return tuple(self._declarations.values())

    def list_general_events(self) -> tuple[str, ...]:
        """Return all built-in general event types (exact 23)."""
        return CANONICAL_DOMAIN_EVENTS


# Default global singleton registry
DEFAULT_DOMAIN_EVENT_REGISTRY = DomainEventRegistry()
