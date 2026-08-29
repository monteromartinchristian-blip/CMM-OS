"""Phase 10.33 — Domain Event Factory.

Standardized, deterministic event construction supporting injectable
clock and ID generators.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime, timezone
from typing import Any

from cmm.domains.errors import (
    DomainContractValidationError,
    DomainError,
    DomainEventContractError,
    DomainEventSerializationError,
)
from cmm.domains.event_contracts import (
    DomainEvent,
    DomainEventReference,
    _validate_event_domain_id_privacy,
    _validate_event_string_privacy,
)
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
        if event_id is not None:
            if not isinstance(event_id, str) or not event_id.strip():
                raise DomainEventContractError(
                    f"event_id must be a non-empty string if provided, got {type(event_id).__name__}",
                    field="event_id",
                )
            try:
                _validate_event_string_privacy(event_id.strip(), "event_id")
            except DomainContractValidationError as exc:
                raise DomainEventContractError(
                    exc.message, field="event_id", details=dict(exc.details)
                ) from None
            final_id = event_id.strip()
        else:
            final_id = self._id_factory()

        if occurred_at is not None:
            if not isinstance(occurred_at, datetime):
                raise DomainEventContractError(
                    f"occurred_at must be datetime if provided, got {type(occurred_at).__name__}",
                    field="occurred_at",
                )
            final_occurred_at = occurred_at
        else:
            final_occurred_at = self._clock()

        if not isinstance(actor, str) or not actor.strip():
            raise DomainEventContractError(
                f"actor must be a non-empty string, got {type(actor).__name__}",
                field="actor",
            )
        try:
            _validate_event_string_privacy(actor.strip(), "actor")
        except DomainContractValidationError as exc:
            raise DomainEventContractError(
                exc.message, field="actor", details=dict(exc.details)
            ) from None

        if session_id is not None and (
            not isinstance(session_id, str) or isinstance(session_id, bool)
        ):
            raise DomainEventContractError(
                f"session_id must be a string or None, got {type(session_id).__name__}",
                field="session_id",
            )

        if correlation_id is not None and (
            not isinstance(correlation_id, str) or isinstance(correlation_id, bool)
        ):
            raise DomainEventContractError(
                f"correlation_id must be a string or None, got {type(correlation_id).__name__}",
                field="correlation_id",
            )

        if causation_id is not None and (
            not isinstance(causation_id, str) or isinstance(causation_id, bool)
        ):
            raise DomainEventContractError(
                f"causation_id must be a string or None, got {type(causation_id).__name__}",
                field="causation_id",
            )

        if isinstance(permissions, (str, bytes, set, frozenset)) or not isinstance(
            permissions, (list, tuple, Sequence)
        ):
            raise DomainEventContractError(
                "permissions must be an ordered sequence of strings, not a set or scalar",
                field="permissions",
            )

        if payload is not None and not isinstance(payload, Mapping):
            raise DomainEventContractError(
                f"payload must be a mapping or None, got {type(payload).__name__}",
                field="payload",
            )

        if metadata is not None and not isinstance(metadata, Mapping):
            raise DomainEventContractError(
                f"metadata must be a mapping or None, got {type(metadata).__name__}",
                field="metadata",
            )

        if isinstance(domain_id, str):
            try:
                dom_id = (
                    DomainId.from_str(domain_id)
                    if domain_id.startswith("domain:")
                    else DomainId(slug=domain_id)
                )
            except (DomainError, ValueError, TypeError, KeyError):
                raise DomainEventContractError(
                    "Invalid domain_id in factory",
                    field="domain_id",
                ) from None
        elif isinstance(domain_id, DomainId):
            dom_id = domain_id
        else:
            raise DomainEventContractError(
                f"domain_id must be DomainId or str, got {type(domain_id).__name__}",
                field="domain_id",
            )
        try:
            _validate_event_domain_id_privacy(dom_id, "domain_id")
        except DomainContractValidationError as exc:
            raise DomainEventContractError(
                exc.message, field="domain_id", details=dict(exc.details)
            ) from None

        if isinstance(
            related_domain_ids, (str, bytes, set, frozenset)
        ) or not isinstance(related_domain_ids, (list, tuple, Sequence)):
            raise DomainEventContractError(
                "related_domain_ids must be an ordered sequence, not a set or scalar",
                field="related_domain_ids",
            )

        rel_ids: list[DomainId] = []
        for i, rd in enumerate(related_domain_ids):
            if isinstance(rd, str):
                try:
                    rel_dom = (
                        DomainId.from_str(rd)
                        if rd.startswith("domain:")
                        else DomainId(slug=rd)
                    )
                except (DomainError, ValueError, TypeError, KeyError):
                    raise DomainEventContractError(
                        f"Invalid related_domain_ids[{i}]",
                        field="related_domain_ids",
                        details={"index": i},
                    ) from None
            elif isinstance(rd, DomainId):
                rel_dom = rd
            else:
                raise DomainEventContractError(
                    f"related_domain_ids[{i}] must be DomainId or str, got {type(rd).__name__}",
                    field="related_domain_ids",
                    details={"index": i},
                )
            try:
                _validate_event_domain_id_privacy(rel_dom, f"related_domain_ids[{i}]")
            except DomainContractValidationError as exc:
                raise DomainEventContractError(
                    exc.message,
                    field="related_domain_ids",
                    details={"index": i, **dict(exc.details)},
                ) from None
            rel_ids.append(rel_dom)

        if isinstance(provenance, (str, bytes, set, frozenset)) or not isinstance(
            provenance, (list, tuple, Sequence)
        ):
            raise DomainEventContractError(
                "provenance must be an ordered sequence, not a set or scalar",
                field="provenance",
            )

        prov_refs: list[DomainEventReference] = []
        for i, p in enumerate(provenance):
            if isinstance(p, DomainEventReference):
                prov_refs.append(p)
            elif isinstance(p, Mapping):
                try:
                    prov_refs.append(DomainEventReference.from_dict(dict(p)))
                except (
                    DomainEventSerializationError,
                    DomainContractValidationError,
                ) as exc:
                    raise DomainEventContractError(
                        exc.message,
                        field="provenance",
                        details={"index": i, **dict(getattr(exc, "details", {}))},
                    ) from None
            else:
                raise DomainEventContractError(
                    f"provenance[{i}] must be DomainEventReference or Mapping, got {type(p).__name__}",
                    field="provenance",
                    details={"index": i},
                )

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
            payload=payload if payload is not None else {},
            metadata=metadata if metadata is not None else {},
        )
