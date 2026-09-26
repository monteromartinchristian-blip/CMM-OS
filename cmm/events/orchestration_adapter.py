"""Phase 11.22 — production ``OrchestrationEventSink`` adapter.

Phase 11.2 deliberately left ``OrchestrationEventSink`` as a narrow adapter seam,
not an event system, and named the dependency ``orchestration.event_sink``.  This
module is the Phase 11.22 production implementation of that seam.

The adapter is one-way and decision-free:

* it accepts only the frozen Phase 11.2 lifecycle event set, enforced by reusing
  the Phase 11.2 ``validate_orchestration_event`` policy, so the closed-phase
  payload safety rule is not weakened;
* it maps supported lifecycle facts through the explicit Phase 11.22 translation
  table and publishes through the canonical ``EventSystem`` facade, so the durable
  repository and the one Phase 9 event bus stay the transport;
* an orchestration fact with no Phase 11.22 platform event is *observed and
  skipped*, never fabricated into a platform event;
* it preserves request correlation and owner identity;
* it makes no routing decision, mutates no orchestration state and never calls the
  Orchestrator back.

Emission failure propagates to the Orchestrator, which fails closed.  A
lifecycle fact the Orchestrator considers mandatory must never be silently
dropped because the event system could not accept it.

``RecordingOrchestrationEventSink`` remains the official simple in-memory
recorder for its existing tests and use cases; it is neither removed nor
redefined as the platform bus.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from cmm.events.event_payload_safety import (
    ALLOWED_PAYLOAD_KEYS,
    PlatformEventPayloadError,
    freeze_platform_payload,
)
from cmm.events.event_system import EventSystem
from cmm.events.event_translation import (
    ORCHESTRATION_SOURCE_TRANSLATIONS,
    translate_orchestration_event,
)
from cmm.orchestration.events import validate_orchestration_event

__all__ = [
    "ORCHESTRATION_ADAPTER_ID",
    "PlatformOrchestrationEventSink",
    "SkippedOrchestrationEvent",
]

ORCHESTRATION_ADAPTER_ID = "cmm.events.orchestration_adapter"

#: Facts the adapter may read from an orchestration payload.  This is the
#: intersection of what Phase 11.2 can legitimately carry and what the Phase 11.22
#: bounded platform vocabulary permits, so a payload key the platform does not
#: allow fails closed here rather than being silently dropped.
READABLE_PAYLOAD_KEYS: frozenset[str] = frozenset(
    {
        "channel",
        "session_id",
        "intent",
        "needs_clarification",
        "status",
        "primary_domain",
        "supporting_domains",
        "approval_refs",
        "agent_id",
        "workflow_id",
        "decision_id",
        "policy_disposition",
        "reason_codes",
        "route",
    }
)

#: Every readable key must also be inside the canonical platform vocabulary.
assert READABLE_PAYLOAD_KEYS <= ALLOWED_PAYLOAD_KEYS, (
    "adapter facts must stay inside the canonical platform payload vocabulary"
)


@dataclass(frozen=True, slots=True)
class SkippedOrchestrationEvent:
    """One accepted orchestration fact with no Phase 11.22 platform event."""

    event_type: str
    request_id: str
    sequence: int
    reason: str = "no_explicit_platform_translation"


class PlatformOrchestrationEventSink:
    """Publish safe orchestration lifecycle facts into the platform event system.

    The sink implements the frozen Phase 11.2 ``OrchestrationEventSink`` protocol
    structurally, so it can be injected anywhere the protocol is accepted.
    """

    __slots__ = ("_observed", "_published", "_sequence", "_skipped", "_system")

    def __init__(self, system: EventSystem) -> None:
        if system is None:
            raise TypeError("system is required")
        self._system = system
        self._sequence = 0
        self._observed: list[Any] = []
        self._skipped: list[SkippedOrchestrationEvent] = []
        self._published: list[Any] = []

    # ── Frozen Phase 11.2 seam ───────────────────────────────────────────────

    def emit(
        self,
        event_type: str,
        *,
        request_id: str,
        payload: Mapping[str, object],
    ) -> str | None:
        """Validate one orchestration fact and publish it when mapped.

        Returns the canonical platform event ID when a platform event was
        published, and ``None`` when the fact has no Phase 11.22 platform event.
        Raises when the source event is invalid or the platform path refuses it,
        so a mandatory orchestration fact is never lost silently.
        """

        # 1. The closed Phase 11.2 policy decides what may enter an event at all.
        safe_payload = validate_orchestration_event(event_type, payload)

        # 2. Every readable fact must also be inside the platform vocabulary.
        self._assert_readable(safe_payload)

        return self._translate_and_publish(
            event_type=event_type,
            request_id=request_id,
            safe_payload=safe_payload,
        )

    # ── Observation surface ──────────────────────────────────────────────────

    def events(self) -> tuple[Any, ...]:
        """Return the recorded orchestration events in emission order.

        This preserves the observer surface Phase 11.2/11.3/11.4 consumers already
        rely on, while publication goes through the canonical platform path.
        """

        return tuple(self._observed)

    def skipped_events(self) -> tuple[SkippedOrchestrationEvent, ...]:
        """Return the accepted facts that had no explicit platform translation."""

        return tuple(self._skipped)

    def published_events(self) -> tuple[Any, ...]:
        """Return the canonical platform events this adapter published."""

        return tuple(self._published)

    # ── Internals ────────────────────────────────────────────────────────────

    def _assert_readable(self, payload: Mapping[str, object]) -> None:
        unknown = sorted(key for key in payload if key not in READABLE_PAYLOAD_KEYS)
        if unknown:
            raise PlatformEventPayloadError(
                "orchestration fact is outside the bounded platform vocabulary",
                key=unknown[0],
            )

    def _translate_and_publish(
        self,
        *,
        event_type: str,
        request_id: str,
        safe_payload: Mapping[str, object],
    ) -> str | None:
        from cmm.orchestration.events import RecordedOrchestrationEvent

        sequence = self._sequence
        self._sequence += 1

        self._observed.append(
            RecordedOrchestrationEvent(
                event_type=event_type,
                request_id=request_id,
                sequence=sequence,
                payload=safe_payload,
            )
        )

        translation = translate_orchestration_event(event_type)
        if translation is None:
            self._skipped.append(
                SkippedOrchestrationEvent(
                    event_type=event_type,
                    request_id=request_id,
                    sequence=sequence,
                )
            )
            return None

        platform_payload = self._project(translation.fact_keys, safe_payload)
        platform_payload["request_id"] = request_id

        result = self._system.publish(
            translation.platform_event_type,
            platform_payload,
            correlation_id=request_id,
            causation_id=request_id,
            producer="cmm.orchestration",
            aggregate_id=request_id,
        )
        self._published.append(result.event)
        return result.event.header.event_id

    @staticmethod
    def _project(
        fact_keys: tuple[str, ...], safe_payload: Mapping[str, object]
    ) -> dict[str, object]:
        """Copy only the mapped facts that are actually present.

        A missing fact stays missing: the translation never invents a value.
        """

        projected: dict[str, object] = {}
        for key in fact_keys:
            if key in safe_payload:
                value = safe_payload[key]
                if isinstance(value, tuple):
                    value = list(value)
                projected[key] = value
        return projected


def orchestration_adapter_translations() -> tuple[Any, ...]:
    """Return the explicit orchestration translations the adapter uses."""

    return ORCHESTRATION_SOURCE_TRANSLATIONS


def frozen_orchestration_payload(payload: Mapping[str, object]) -> Mapping[str, object]:
    """Freeze a payload through the platform gate (test/inspection helper)."""

    return freeze_platform_payload(payload)
