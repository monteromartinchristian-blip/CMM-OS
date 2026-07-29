"""Phase 9.20 – Agent Trace Event Subscriber.

Subscribes to the runtime event bus and feeds events to the Agent Runtime Trace system.
"""

from __future__ import annotations

from typing import Any

from cmm.agent_runtime.runtime_event_contracts import (
    AgentRuntimeEvent,
    AgentRuntimeEventSubscription,
)
from cmm.agent_runtime.runtime_event_errors import (
    AgentRuntimeEventTraceSubscriberError,
)
from cmm.agent_runtime.runtime_event_types import is_registered_event_type


class AgentTraceEventSubscriber:
    """Subscribes to relevant runtime events and converts them to trace records."""

    def __init__(
        self,
        trace_collector: Any,
        trace_service: Any,
        redactor: Any,
    ) -> None:
        self._trace_collector = trace_collector
        self._trace_service = trace_service
        self._redactor = redactor
        self._trace_event_types: set[str] = {
            "goal.created",
            "goal.updated",
            "goal.completed",
            "goal.failed",
            "agent_run.created",
            "agent_run.started",
            "agent_run.completed",
            "agent_run.failed",
            "agent_iteration.started",
            "agent_iteration.completed",
            "agent_iteration.failed",
            "observation.completed",
            "knowledge.loaded",
            "workflow_plan.created",
            "workflow_plan.validated",
            "operation.started",
            "operation.completed",
            "operation.failed",
            "recovery.started",
            "recovery.retry_requested",
            "outcome_evaluation.started",
            "outcome_evaluation.completed",
            "runtime.error",
            "runtime.warning",
        }
        self._trace_map: dict[str, str] = {}

    def handle_event(self, event: AgentRuntimeEvent) -> None:
        """Process an event for trace recording."""
        event_type = event.header.event_type
        if not is_registered_event_type(event_type):
            return

        if event_type not in self._trace_event_types:
            return

        try:
            redacted = self._redactor.redact_event(event)
            self._trace_collector.add_event(redacted)
        except Exception as exc:
            raise AgentRuntimeEventTraceSubscriberError(
                f"trace subscriber failed for event '{event.header.event_id}': {exc}"
            ) from exc

    def get_subscription(self, bus: Any) -> AgentRuntimeEventSubscription:
        """Create a subscription for the provided event bus."""
        return AgentRuntimeEventSubscription(
            id="trace_subscriber",
            handler_name="AgentTraceEventSubscriber",
            event_types=list(self._trace_event_types),
            filters={"source": "agent_runtime"},
            priority=-100,
        )

    def finalize_trace(self, agent_run_id: str) -> None:
        """Finalize trace for an agent run."""
        try:
            self._trace_service.finalize_trace(agent_run_id)
        except Exception as exc:
            raise AgentRuntimeEventTraceSubscriberError(
                f"finalize trace failed for run '{agent_run_id}': {exc}"
            ) from exc
