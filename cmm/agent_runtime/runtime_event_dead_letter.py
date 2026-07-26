"""Phase 9.20 – Runtime Event Dead Letter Queue.

In-memory dead letter queue for failed event deliveries.
"""

from __future__ import annotations

import builtins
import threading

from cmm.agent_runtime.runtime_event_contracts import (
    AgentRuntimeEvent,
    AgentRuntimeEventDeadLetter,
)


class InMemoryAgentRuntimeDeadLetterQueue:
    """Thread-safe in-memory dead letter queue."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._items: list[AgentRuntimeEventDeadLetter] = []

    def add(self, item: AgentRuntimeEventDeadLetter) -> None:
        """Add a dead letter entry."""
        if not isinstance(item, AgentRuntimeEventDeadLetter):
            raise TypeError("item must be an AgentRuntimeEventDeadLetter")
        with self._lock:
            self._items.append(item)

    def get(self, index: int) -> AgentRuntimeEventDeadLetter:
        """Get dead letter by index."""
        with self._lock:
            if index < 0 or index >= len(self._items):
                raise IndexError("dead letter index out of range")
            return self._items[index]

    def list(self) -> builtins.list[AgentRuntimeEventDeadLetter]:
        """List all dead letters."""
        with self._lock:
            return list(self._items)

    def replay(self, index: int) -> AgentRuntimeEvent:
        """Get the event from a dead letter for replay."""
        item = self.get(index)
        return item.event

    def remove(self, index: int) -> AgentRuntimeEventDeadLetter:
        """Remove and return a dead letter."""
        with self._lock:
            if index < 0 or index >= len(self._items):
                raise IndexError("dead letter index out of range")
            return self._items.pop(index)

    def clear(self) -> None:
        """Clear all dead letters."""
        with self._lock:
            self._items.clear()

    def count(self) -> int:
        """Return the number of dead letters."""
        with self._lock:
            return len(self._items)
