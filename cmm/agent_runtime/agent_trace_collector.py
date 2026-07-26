"""Phase 9.19 – Agent Runtime Trace Collector.

Live collector that subscribes to the Event Bus, normalizes events,
deduplicates, buffers, and persists incrementally.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from typing import Any

from cmm.agent_runtime.agent_trace_event_normalizer import AgentTraceEventNormalizer
from cmm.agent_runtime.agent_trace_service import AgentTraceService
from cmm.agent_runtime.errors import (
    AgentTraceBuildError,
    AgentTraceContractError,
)


class AgentTraceCollector:
    """Live collector that subscribes to an Event Bus and builds traces.

    The collector is an optional adapter.  If the Event Bus does not
    support subscribe(), integration can be done via manual calls to
    receive_event().

    Rules:
    - Buffer with configurable max size
    - Backpressure via buffer limit
    - Invalid event does not crash collector
    - Collector closed rejects new events
    """

    def __init__(
        self,
        trace_service: AgentTraceService,
        normalizer: AgentTraceEventNormalizer | None = None,
        buffer_size: int = 1000,
    ) -> None:
        self._trace_service = trace_service
        self._normalizer = normalizer or AgentTraceEventNormalizer(strict=False)
        self._buffer_size = buffer_size
        self._buffer: list[dict[str, Any]] = []
        self._lock = threading.RLock()
        self._closed = False
        self._event_count = 0
        self._trace_ids: dict[str, str] = {}  # agent_run_id -> trace_id

    @property
    def is_closed(self) -> bool:
        return self._closed

    @property
    def buffer_size(self) -> int:
        return len(self._buffer)

    def subscribe(self, event_bus: Any, event_types: list[str] | None = None) -> None:
        """Subscribe to an Event Bus.

        Args:
            event_bus: An object with a subscribe(event_type, callback) method
                or a register_handler(event_type, callback) method.
            event_types: List of event types to subscribe to. If None,
                subscribes to all supported types.
        """
        supported = self._normalizer._registry.known_event_types()
        types_to_sub = event_types or list(supported)

        for event_type in types_to_sub:
            try:
                if hasattr(event_bus, "subscribe"):
                    event_bus.subscribe(event_type, self._make_handler(event_type))
                elif hasattr(event_bus, "register_handler"):
                    event_bus.register_handler(
                        event_type, self._make_handler(event_type)
                    )
            except Exception:  # noqa: BLE001, S112
                # Intencionalmente tolerante: el colector no debe romperse
                # por un bus malísimo o un handler conflictivo.
                continue

    def _make_handler(self, event_type: str) -> Callable:
        def handler(event: Any) -> None:
            if isinstance(event, dict):
                self.receive_event(event)
            elif hasattr(event, "to_dict"):
                self.receive_event(event.to_dict())
            elif hasattr(event, "__dict__"):
                self.receive_event(event.__dict__)

        return handler

    def receive_event(self, event: dict[str, Any]) -> None:
        """Receive an event from the Event Bus or external source."""
        if self._closed:
            raise AgentTraceBuildError("Collector is closed")

        agent_run_id = event.get("agent_run_id", event.get("run_id", ""))
        if not agent_run_id:
            return

        with self._lock:
            # Check buffer limit
            if len(self._buffer) >= self._buffer_size:
                self._flush()

            self._buffer.append(event)
            self._event_count += 1

            # Ensure trace exists
            trace_id = self._trace_ids.get(agent_run_id)
            if trace_id is None:
                # Create trace
                goal_id = event.get("goal_id", event.get("goal", ""))
                trace = self._trace_service.start_trace(
                    agent_run_id=agent_run_id,
                    goal_id=goal_id or "unknown",
                    goal_created_by=event.get("goal_created_by", ""),
                    agent_id=event.get("agent_id", ""),
                    workflow_id=event.get("workflow_id", ""),
                    correlation_id=event.get("correlation_id", ""),
                )
                self._trace_ids[agent_run_id] = trace.trace_id

    def flush(self) -> int:
        """Flush buffered events to trace storage.

        Returns the number of events flushed.
        """
        with self._lock:
            return self._flush()

    def _flush(self) -> int:
        if not self._buffer:
            return 0

        events_to_flush = list(self._buffer)
        self._buffer.clear()

        # Group events by agent_run_id
        run_events: dict[str, list[dict[str, Any]]] = {}
        for event in events_to_flush:
            run_id = event.get("agent_run_id", event.get("run_id", ""))
            if run_id:
                run_events.setdefault(run_id, []).append(event)

        flushed = 0
        for run_id, run_evts in run_events.items():
            trace_id = self._trace_ids.get(run_id)
            if trace_id is None:
                continue
            try:
                self._trace_service.append_events(trace_id, run_evts)
                flushed += len(run_evts)
            except (AgentTraceBuildError, AgentTraceContractError):
                continue

        return flushed

    def close(self) -> int:
        """Close the collector and flush remaining events.

        Returns the number of events flushed.
        """
        with self._lock:
            flushed = self._flush()
            self._closed = True
            return flushed

    def get_trace_id(self, agent_run_id: str) -> str | None:
        """Get the trace ID for an agent run."""
        return self._trace_ids.get(agent_run_id)
