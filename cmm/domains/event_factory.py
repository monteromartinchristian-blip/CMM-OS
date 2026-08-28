"""Phase 10.33 — Domain Event Factory.

Standardized, deterministic event construction supporting injectable
clock and ID generators.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime, timezone
from typing import Any

from cmm.domains.event_contracts import DomainEvent, DomainEventReference
from cmm.domains.identifiers import DomainId


def _default_clock() -> datetime:
    return datetime.now(timezone.utc)


def _default_id_factory() -> str:
    return f"evt-{uuid.uuid4().hex}"


class DomainEventFactory:
    """Factory for standardizing DomainEvent construction."""

    def __init__(
        self,
        clock: Callable[[], datetime] | None = None,
        id_factory: Callable[[], str] | None = None,
    ) -> None:
        """Initialize the factory.

        Args:
            clock: Callable returning the current timezone-aware datetime.
            id_factory: Callable returning unique string event IDs.
        """
        self._clock = clock or _default_clock
        self._id_factory = id_factory or _default_id_factory

    def create_event(
        self,
        event_type: str,
        domain_id: DomainId | str,
        actor: str,
        sensitivity: str = "internal",
        schema_version: str = "1.0.0",
        related_domain_ids: Sequence[DomainId | str] = (),
        session_id: str | None = None,
        occurred_at: datetime | None = None,
        provenance: Sequence[DomainEventReference | Mapping[str, Any]] = (),
        permissions: Sequence[str] = (),
        correlation_id: str | None = None,
        causation_id: str | None = None,
        payload: Mapping[str, Any] | None = None,
        metadata: Mapping[str, Any] | None = None,
        event_id: str | None = None,
    ) -> DomainEvent:
        """Create an immutable DomainEvent using injected clock/ID defaults."""
        final_id = event_id or self._id_factory()
        final_occurred_at = occurred_at or self._clock()

        if isinstance(domain_id, str):
            dom_id = (
                DomainId.from_str(domain_id)
                if domain_id.startswith("domain:")
                else DomainId(slug=domain_id)
            )
        else:
            dom_id = domain_id

        rel_ids: list[DomainId] = []
        for rd in related_domain_ids:
            if isinstance(rd, str):
                rel_ids.append(
                    DomainId.from_str(rd)
                    if rd.startswith("domain:")
                    else DomainId(slug=rd)
                )
            else:
                rel_ids.append(rd)

        prov_refs: list[DomainEventReference] = []
        for p in provenance:
            if isinstance(p, DomainEventReference):
                prov_refs.append(p)
            elif isinstance(p, Mapping):
                prov_refs.append(DomainEventReference.from_dict(dict(p)))

        return DomainEvent(
            event_id=final_id,
            event_type=event_type,
            schema_version=schema_version,
            domain_id=dom_id,
            related_domain_ids=tuple(rel_ids),
            actor=actor,
            session_id=session_id,
            occurred_at=final_occurred_at,
            provenance=tuple(prov_refs),
            sensitivity=sensitivity,
            permissions=tuple(permissions),
            correlation_id=correlation_id,
            causation_id=causation_id,
            payload=payload or {},
            metadata=metadata or {},
        )
