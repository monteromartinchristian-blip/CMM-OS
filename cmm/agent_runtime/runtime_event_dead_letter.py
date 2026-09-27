"""Phase 9.20 – Runtime Event Dead Letter Queue.

In-memory dead letter queue for failed event deliveries.
"""

from __future__ import annotations

import builtins
import threading

from cmm.agent_runtime.runtime_event_contracts import (
    AgentRuntimeEvent,
    AgentRuntimeEventDeadLetter,
    detached_dead_letter_copy,
)


class InMemoryAgentRuntimeDeadLetterQueue:
    """Thread-safe in-memory dead letter queue.

    Every entry handed out is a detached snapshot, so a caller that mutates a
    returned record's nested event containers or metadata can never change the
    queue's retained evidence or what a later inspection observes.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._items: list[AgentRuntimeEventDeadLetter] = []

    def add(self, item: AgentRuntimeEventDeadLetter) -> None:
        """Add a dead letter entry."""
        if not isinstance(item, AgentRuntimeEventDeadLetter):
            raise TypeError("item must be an AgentRuntimeEventDeadLetter")
        with self._lock:
            # Retain a detached snapshot, so the recorder's own object can never
            # mutate the evidence the queue holds.
            self._items.append(detached_dead_letter_copy(item))

    def get(self, index: int) -> AgentRuntimeEventDeadLetter:
        """Get a detached snapshot of the dead letter at *index*."""
        with self._lock:
            if index < 0 or index >= len(self._items):
                raise IndexError("dead letter index out of range")
            return detached_dead_letter_copy(self._items[index])

    def list(self) -> builtins.list[AgentRuntimeEventDeadLetter]:
        """List detached snapshots of all dead letters."""
        with self._lock:
            return [detached_dead_letter_copy(item) for item in self._items]

    def replay(self, index: int) -> AgentRuntimeEvent:
        """Get the event from a dead letter for replay."""
        item = self.get(index)
        return item.event

    def remove(self, index: int) -> AgentRuntimeEventDeadLetter:
        """Remove and return a detached snapshot of a dead letter."""
        with self._lock:
            if index < 0 or index >= len(self._items):
                raise IndexError("dead letter index out of range")
            return detached_dead_letter_copy(self._items.pop(index))

    def clear(self) -> None:
        """Clear all dead letters."""
        with self._lock:
            self._items.clear()

    def count(self) -> int:
        """Return the number of dead letters."""
        with self._lock:
            return len(self._items)
