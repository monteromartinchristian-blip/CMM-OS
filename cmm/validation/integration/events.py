"""Kernel Event Integration for Continuous Validation (Subphase 7.13).

Publishes structured validation lifecycle events to the Kernel Event System.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone

from kernel.events.event import Event

from ..results import ValidationResult
from .contracts import ValidationEventPayload, ValidationTrigger


class KernelEventPublisher:
    """Publishes structured validation events to kernel event subscribers or listeners."""

    def __init__(
        self,
        event_listener: Callable[[Event], None] | None = None,
        policy: str = "best_effort",
    ) -> None:
        """Initialize publisher.

        Args:
            event_listener: Callback taking a kernel.events.event.Event object.
            policy: Publication policy ('best_effort' or 'strict').
        """
        self._listener = event_listener
        self._policy = policy
        self._emitted_events: list[Event] = []

    @property
    def emitted_events(self) -> tuple[Event, ...]:
        return tuple(self._emitted_events)

    def publish(self, event_type: str, payload: ValidationEventPayload) -> None:
        """Publish a single validation event."""
        event_dict = payload.serialize()
        event_obj = Event(name=event_type, payload=event_dict)

        try:
            self._emitted_events.append(event_obj)
            if self._listener is not None:
                self._listener(event_obj)
        except Exception as exc:
            if self._policy == "strict":
                raise RuntimeError(
                    f"Failed to publish validation event '{event_type}': {exc}"
                ) from exc

    def publish_validation_events(
        self,
        result: ValidationResult,
        trigger: ValidationTrigger | None = None,
        workflow_id: str | None = None,
        plan_node_id: str | None = None,
    ) -> list[str]:
        """Publish the full sequence of lifecycle events for a ValidationResult."""
        published_types: list[str] = []

        now_str = datetime.now(timezone.utc).isoformat()
        actor = trigger.actor if trigger else "system"
        policy_name = result.policy or "default"
        wf_id = workflow_id or (trigger.workflow_id if trigger else None)
        node_id = plan_node_id or (trigger.plan_node_id if trigger else None)

        # 1. validation.started
        start_payload = ValidationEventPayload(
            event_type="validation.started",
            validation_id=result.id,
            timestamp=now_str,
            actor=actor,
            policy=policy_name,
            workflow_id=wf_id,
            plan_node_id=node_id,
            status="started",
        )
        self.publish("validation.started", start_payload)
        published_types.append("validation.started")

        # 2. Step events
        for step in result.steps:
            step_start = ValidationEventPayload(
                event_type="validation.step.started",
                validation_id=result.id,
                timestamp=now_str,
                actor=actor,
                policy=policy_name,
                workflow_id=wf_id,
                plan_node_id=node_id,
                step_name=step.name,
                status="running",
            )
            self.publish("validation.step.started", step_start)
            published_types.append("validation.step.started")

            step_comp = ValidationEventPayload(
                event_type="validation.step.completed",
                validation_id=result.id,
                timestamp=now_str,
                actor=actor,
                policy=policy_name,
                workflow_id=wf_id,
                plan_node_id=node_id,
                step_name=step.name,
                status=step.status.value,
                duration_ms=step.duration_ms,
            )
            self.publish("validation.step.completed", step_comp)
            published_types.append("validation.step.completed")

        # 3. Overall completion / failure
        is_passed = result.status.value == "passed"
        comp_event_type = "validation.completed" if is_passed else "validation.failed"

        end_payload = ValidationEventPayload(
            event_type=comp_event_type,
            validation_id=result.id,
            timestamp=now_str,
            actor=actor,
            policy=policy_name,
            workflow_id=wf_id,
            plan_node_id=node_id,
            status=result.status.value,
            duration_ms=result.duration_ms,
        )
        self.publish(comp_event_type, end_payload)
        published_types.append(comp_event_type)

        # 4. Commit gate event if present in metadata
        gate_res = (
            result.metadata.get("gate_result")
            if isinstance(result.metadata, dict)
            else None
        )
        if gate_res is not None:
            gate_approved = getattr(gate_res, "approved", False)
            gate_event_type = (
                "validation.gate.approved"
                if gate_approved
                else "validation.gate.rejected"
            )
            gate_payload = ValidationEventPayload(
                event_type=gate_event_type,
                validation_id=result.id,
                timestamp=now_str,
                actor=actor,
                policy=policy_name,
                workflow_id=wf_id,
                plan_node_id=node_id,
                status="approved" if gate_approved else "rejected",
            )
            self.publish(gate_event_type, gate_payload)
            published_types.append(gate_event_type)

        return published_types
