"""Phase 9.20 – Runtime Event Repository.

Event persistence with append-only semantics and in-memory implementation.
"""

from __future__ import annotations

import builtins
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from cmm.agent_runtime.runtime_event_contracts import AgentRuntimeEvent


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

    def save(self, event: AgentRuntimeEvent) -> None:
        event_id = event.header.event_id
        if event_id in self._events:
            raise ValueError(f"event '{event_id}' already exists; append-only")
        self._events[event_id] = event

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
        events = sorted(events, key=lambda e: e.header.occurred_at)
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
        result = events
        if filters.get("event_type"):
            result = [e for e in result if e.header.event_type == filters["event_type"]]
        if filters.get("agent_run_id"):
            result = [
                e for e in result if e.header.agent_run_id == filters["agent_run_id"]
            ]
        if filters.get("goal_id"):
            result = [e for e in result if e.header.goal_id == filters["goal_id"]]
        if filters.get("correlation_id"):
            result = [
                e
                for e in result
                if e.header.correlation_id == filters["correlation_id"]
            ]
        if filters.get("agent_id"):
            result = [e for e in result if e.header.agent_id == filters["agent_id"]]
        if filters.get("start_time"):
            result = [
                e for e in result if e.header.occurred_at >= filters["start_time"]
            ]
        if filters.get("end_time"):
            result = [e for e in result if e.header.occurred_at <= filters["end_time"]]
        if filters.get("limit"):
            result = result[: filters["limit"]]
        return result
