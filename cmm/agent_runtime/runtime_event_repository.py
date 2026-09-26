"""Phase 9.20 – Runtime Event Repository.

Event persistence with append-only semantics, an in-memory implementation and the
Phase 11.22 durable local implementation of the same canonical contract.

Phase 11.22 adds durability as an *implementation* of
:class:`AgentRuntimeEventRepository`; it defines no second repository protocol and
no general event-store framework.
"""

from __future__ import annotations

import builtins
import json
import os
import threading
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from cmm.agent_runtime.runtime_event_contracts import AgentRuntimeEvent
from cmm.agent_runtime.runtime_event_errors import (
    AgentRuntimeEventIdentityConflictError,
    AgentRuntimeEventPersistenceCorruptionError,
    AgentRuntimeEventRepositoryError,
)
from cmm.agent_runtime.runtime_event_factory import (
    AgentRuntimeEventFactory,
    event_fingerprint,
)


class AgentRuntimeEventRepository:
    """Abstract repository for runtime event persistence."""

    def save(self, event: AgentRuntimeEvent) -> None:
        """Persist a single event."""
        raise NotImplementedError

    def save_many(self, events: Sequence[AgentRuntimeEvent]) -> None:
        """Persist multiple events."""
        for event in events:
            self.save(event)

    def get(self, event_id: str) -> AgentRuntimeEvent | None:
        """Retrieve an event by id."""
        raise NotImplementedError

    def list(
        self,
        limit: int = 1000,
        offset: int = 0,
        **filters: Any,
    ) -> builtins.list[AgentRuntimeEvent]:
        """List events with optional filters and pagination."""
        raise NotImplementedError

    def query(self, **filters: Any) -> builtins.list[AgentRuntimeEvent]:
        """Query events by arbitrary filters."""
        raise NotImplementedError

    def exists(self, event_id: str) -> bool:
        """Check if an event exists."""
        return self.get(event_id) is not None

    def count(self, **filters: Any) -> int:
        """Count events matching filters."""
        return len(self.query(**filters))

    def delete(self, event_id: str) -> None:
        """Delete an event by id if policy allows."""
        raise NotImplementedError


@dataclass
class InMemoryAgentRuntimeEventRepository(AgentRuntimeEventRepository):
    """In-memory, append-only event repository."""

    _events: dict[str, AgentRuntimeEvent] = field(default_factory=dict, repr=False)
    _order: builtins.list[str] = field(default_factory=list, repr=False)

    def save(self, event: AgentRuntimeEvent) -> None:
        event_id = event.header.event_id
        if event_id in self._events:
            raise ValueError(f"event '{event_id}' already exists; append-only")
        self._events[event_id] = event
        self._order.append(event_id)

    def get(self, event_id: str) -> AgentRuntimeEvent | None:
        return self._events.get(event_id)

    def list(
        self,
        limit: int = 1000,
        offset: int = 0,
        **filters: Any,
    ) -> builtins.list[AgentRuntimeEvent]:
        events = list(self._events.values())
        events = self._apply_filters(events, **filters)
        # Chronological order with a deterministic insertion-order tie-break, so
        # replay of equal-timestamp events is stable rather than arbitrary.
        position = {event_id: index for index, event_id in enumerate(self._order)}
        events = sorted(
            events,
            key=lambda e: (e.header.occurred_at, position.get(e.header.event_id, 0)),
        )
        return events[offset : offset + limit]

    def query(self, **filters: Any) -> builtins.list[AgentRuntimeEvent]:
        events = list(self._events.values())
        return self._apply_filters(events, **filters)

    def delete(self, event_id: str) -> None:
        if event_id not in self._events:
            raise KeyError(f"event '{event_id}' not found")
        raise RuntimeError("Append-only repository does not support deletion")

    def _apply_filters(
        self, events: builtins.list[AgentRuntimeEvent], **filters: Any
    ) -> builtins.list[AgentRuntimeEvent]:
        return _apply_filters(events, **filters)


#: The one canonical on-disk record schema version Phase 11.22 writes.
DURABLE_RECORD_SCHEMA_VERSION = "1.0.0"

#: ``0o600``: owner read/write only, where the platform supports it.
_RESTRICTIVE_FILE_MODE = 0o600


def _apply_filters(
    events: builtins.list[AgentRuntimeEvent], **filters: Any
) -> builtins.list[AgentRuntimeEvent]:
    """Apply the canonical repository filters to *events* in order.

    Shared by the durable repository so filter semantics stay identical to the
    long-standing in-memory implementation instead of drifting into a second
    query dialect.
    """

    result = events
    if filters.get("event_type"):
        result = [e for e in result if e.header.event_type == filters["event_type"]]
    if filters.get("agent_run_id"):
        result = [e for e in result if e.header.agent_run_id == filters["agent_run_id"]]
    if filters.get("goal_id"):
        result = [e for e in result if e.header.goal_id == filters["goal_id"]]
    if filters.get("correlation_id"):
        result = [
            e for e in result if e.header.correlation_id == filters["correlation_id"]
        ]
    if filters.get("agent_id"):
        result = [e for e in result if e.header.agent_id == filters["agent_id"]]
    if filters.get("start_time"):
        result = [e for e in result if e.header.occurred_at >= filters["start_time"]]
    if filters.get("end_time"):
        result = [e for e in result if e.header.occurred_at <= filters["end_time"]]
    if filters.get("limit"):
        result = result[: filters["limit"]]
    return result


class FileAgentRuntimeEventRepository(AgentRuntimeEventRepository):
    """Durable local append-only implementation of the canonical repository.

    One event is one newline-delimited JSON record:

    ``{"header": {...}, "payload": {...}, "fingerprint": "<sha256>"}``

    Properties Phase 11.22 guarantees:

    * canonical factory serialization and deserialization — no ``pickle``, no
      ``eval``, no ``exec``, no unsafe YAML and no arbitrary object decoding;
    * deterministic append order, preserved across reopen/restart;
    * the write is flushed and ``fsync``-ed before ``save`` reports success;
    * a duplicate event ID with identical canonical content is an idempotent
      duplicate and stores no second record;
    * a duplicate event ID with different canonical content raises
      :class:`AgentRuntimeEventIdentityConflictError` and mutates nothing;
    * a corrupt, malformed, truncated or unsupported stored record raises
      :class:`AgentRuntimeEventPersistenceCorruptionError` rather than being
      silently skipped, repaired or guessed at;
    * restrictive file permissions where the platform supports them;
    * the parent directory is created only for the explicitly configured path.
    """

    _LINE_SEPARATOR = "\n"

    def __init__(
        self,
        path: str | os.PathLike[str],
        *,
        create_parents: bool = True,
        factory: AgentRuntimeEventFactory | None = None,
        permissions: int = _RESTRICTIVE_FILE_MODE,
    ) -> None:
        if not isinstance(path, (str, os.PathLike)):
            raise TypeError("path must be a str or os.PathLike")

        resolved = Path(path).expanduser()
        if not str(path).strip() or str(resolved) in {"", "."}:
            raise ValueError("path must be a non-empty file path")

        self._path = resolved
        self._create_parents = create_parents
        self._factory = factory or AgentRuntimeEventFactory()
        self._permissions = permissions
        self._lock = threading.RLock()
        self._order: builtins.list[str] = []
        self._by_id: dict[str, tuple[AgentRuntimeEvent, str]] = {}

        if create_parents:
            self._create_parent_directory()
        else:
            self._validate_storage_directory()

        self._load()

    # ── Introspection ────────────────────────────────────────────────────────

    @property
    def path(self) -> Path:
        """Return the configured storage path."""

        return self._path

    # ── Canonical repository contract ────────────────────────────────────────

    def save(self, event: AgentRuntimeEvent) -> None:
        """Durably append *event*, deduplicating by identity and content."""

        if not isinstance(event, AgentRuntimeEvent):
            raise TypeError("event must be an AgentRuntimeEvent")

        event_id = event.header.event_id
        fingerprint = event_fingerprint(event)
        record = {
            "header": self._factory.to_dict(event)["header"],
            "payload": self._factory.to_dict(event)["payload"],
            "fingerprint": fingerprint,
            "record_schema_version": DURABLE_RECORD_SCHEMA_VERSION,
        }

        with self._lock:
            existing = self._by_id.get(event_id)
            if existing is not None:
                _stored_event, stored_fingerprint = existing
                if stored_fingerprint == fingerprint:
                    # Idempotent duplicate: no second stored record.
                    return
                raise AgentRuntimeEventIdentityConflictError(
                    f"event '{event_id}' already exists with different content"
                )

            line = json.dumps(record, sort_keys=True, default=str, allow_nan=False)
            self._append_line(line)
            self._order.append(event_id)
            self._by_id[event_id] = (event, fingerprint)

    def get(self, event_id: str) -> AgentRuntimeEvent | None:
        with self._lock:
            stored = self._by_id.get(event_id)
            return None if stored is None else stored[0]

    def list(
        self,
        limit: int = 1000,
        offset: int = 0,
        **filters: Any,
    ) -> builtins.list[AgentRuntimeEvent]:
        with self._lock:
            events = [self._by_id[event_id][0] for event_id in self._order]
        return _apply_filters(events, **filters)[offset : offset + limit]

    def query(self, **filters: Any) -> builtins.list[AgentRuntimeEvent]:
        with self._lock:
            events = [self._by_id[event_id][0] for event_id in self._order]
        return _apply_filters(events, **filters)

    def delete(self, event_id: str) -> None:
        raise RuntimeError("Append-only repository does not support deletion")

    # ── Durable storage primitives ───────────────────────────────────────────

    def _create_parent_directory(self) -> None:
        """Create the configured parent directory, and only that directory.

        Parent creation is bounded to the explicitly configured path: no other
        location is ever created, and a missing or unwritable parent fails safely
        instead of being silently substituted.
        """

        parent = self._path.parent
        if not str(parent) or parent == self._path:
            return
        if parent.is_dir():
            return
        try:
            parent.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise AgentRuntimeEventRepositoryError(
                f"event storage directory is not writable: {parent}"
            ) from exc

    def _validate_storage_directory(self) -> None:
        """Fail safely unless the configured storage directory is already usable."""

        parent = self._path.parent
        if not str(parent) or parent == self._path:
            return
        if not parent.is_dir():
            raise AgentRuntimeEventRepositoryError(
                f"event storage directory does not exist: {parent}"
            )
        if not os.access(parent, os.W_OK | os.X_OK):
            raise AgentRuntimeEventRepositoryError(
                f"event storage directory is not writable: {parent}"
            )

    def _append_line(self, line: str) -> None:
        payload = f"{line}{self._LINE_SEPARATOR}".encode()
        flags = os.O_WRONLY | os.O_CREAT | os.O_APPEND
        try:
            descriptor = os.open(self._path, flags, self._permissions)
        except OSError as exc:
            raise AgentRuntimeEventRepositoryError(
                "event storage path is not writable"
            ) from exc

        try:
            with os.fdopen(descriptor, "ab", closefd=True) as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
        except OSError as exc:
            raise AgentRuntimeEventRepositoryError(
                "event storage append failed"
            ) from exc

        self._restrict_permissions()

    def _restrict_permissions(self) -> None:
        """Best-effort restrictive permissions; unsupported platforms are fine."""

        try:
            os.chmod(self._path, self._permissions)
        except OSError:
            return

    def _load(self) -> None:
        """Replay stored evidence through canonical deserialization, fail closed."""

        if not self._path.exists():
            return

        try:
            raw = self._path.read_text(encoding="utf-8")
        except OSError as exc:
            raise AgentRuntimeEventPersistenceCorruptionError(
                "stored event evidence could not be read"
            ) from exc

        for number, line in enumerate(raw.split(self._LINE_SEPARATOR), start=1):
            if not line.strip():
                continue
            self._load_record(line, number)

    def _load_record(self, line: str, number: int) -> None:
        try:
            record = json.loads(line)
        except (json.JSONDecodeError, ValueError) as exc:
            raise AgentRuntimeEventPersistenceCorruptionError(
                f"stored event record {number} is not valid JSON"
            ) from exc

        if not isinstance(record, dict):
            raise AgentRuntimeEventPersistenceCorruptionError(
                f"stored event record {number} is not a record object"
            )

        version = record.get("record_schema_version", DURABLE_RECORD_SCHEMA_VERSION)
        if version != DURABLE_RECORD_SCHEMA_VERSION:
            raise AgentRuntimeEventPersistenceCorruptionError(
                f"stored event record {number} has an unsupported schema version"
            )

        fingerprint = record.get("fingerprint")
        if not isinstance(fingerprint, str) or not fingerprint:
            raise AgentRuntimeEventPersistenceCorruptionError(
                f"stored event record {number} has no content fingerprint"
            )

        try:
            event = self._factory.from_dict(
                {"header": record["header"], "payload": record["payload"]}
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise AgentRuntimeEventPersistenceCorruptionError(
                f"stored event record {number} is not a canonical event"
            ) from exc

        if event_fingerprint(event) != fingerprint:
            raise AgentRuntimeEventPersistenceCorruptionError(
                f"stored event record {number} does not match its fingerprint"
            )

        event_id = event.header.event_id
        if event_id in self._by_id:
            raise AgentRuntimeEventPersistenceCorruptionError(
                f"stored event record {number} repeats event id '{event_id}'"
            )

        self._order.append(event_id)
        self._by_id[event_id] = (event, fingerprint)
