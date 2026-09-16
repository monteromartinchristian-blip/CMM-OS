"""Phase 11.2 — the safe orchestration event sink.

This module defines a narrow **adapter seam**, not an event system.  Phase 11.2
introduces no event bus, no publish/subscribe platform, no replay engine, no
durable event log and no event registry: the injected sink is simply where the
Orchestration Layer hands off safe lifecycle notifications to whatever event
infrastructure an application already owns.

Only the frozen Phase 11.2 lifecycle event names are accepted, and payloads are
structurally restricted to safe identifiers and categorical facts.  Keys naming
secret-bearing or reasoning-bearing content fail closed, opaque runtime values
are rejected, and recorded payloads are recursively frozen and detached from
the caller, so no raw request content, prompt, credential, provider payload or
hidden reasoning can reach an event.
"""

from __future__ import annotations

import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Protocol, runtime_checkable

__all__ = [
    "ALLOWED_EVENT_TYPES",
    "OrchestrationEventSink",
    "RecordedOrchestrationEvent",
    "RecordingOrchestrationEventSink",
    "validate_orchestration_event",
]

#: The frozen Phase 11.2 lifecycle event names, in emission order.
ALLOWED_EVENT_TYPES: tuple[str, ...] = (
    "orchestration.request_received",
    "orchestration.intent_resolved",
    "orchestration.domain_resolved",
    "orchestration.route_selected",
    "orchestration.approval_required",
    "orchestration.blocked",
    "orchestration.escalated",
    "orchestration.routed",
    "orchestration.failed",
)

_ALLOWED_EVENT_TYPE_SET = frozenset(ALLOWED_EVENT_TYPES)

#: Payload keys that name content which must never enter an event.
FORBIDDEN_PAYLOAD_KEYS = frozenset(
    {
        "chain_of_thought",
        "hidden_reasoning",
        "raw_reasoning",
        "reasoning",
        "prompt",
        "prompts",
        "provider_payload",
        "raw_context",
        "raw_payload",
        "raw_request",
        "request_text",
        "secret",
        "secrets",
        "credential",
        "credentials",
        "password",
        "passwd",
        "token",
        "api_key",
        "apikey",
        "authorization",
        "traceback",
    }
)

#: Payload key segments whose presence fails closed.
FORBIDDEN_PAYLOAD_KEY_TOKENS = frozenset(
    {
        "secret",
        "secrets",
        "credential",
        "credentials",
        "password",
        "passwd",
        "token",
        "auth",
        "authorization",
        "cookie",
        "prompt",
        "prompts",
        "reasoning",
        "chainofthought",
        "thought",
        "payload",
        "traceback",
    }
)

_FORBIDDEN_PAYLOAD_KEYS_SQUASHED = frozenset(
    key.replace("_", "") for key in FORBIDDEN_PAYLOAD_KEYS
)


def _normalize_key(key: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", key.strip().lower()).strip("_")


def _is_forbidden_payload_key(key: str) -> bool:
    """Return whether *key* names content that must never enter an event."""

    normalized = _normalize_key(key)
    if not normalized:
        return False
    if normalized in FORBIDDEN_PAYLOAD_KEYS:
        return True
    if normalized.replace("_", "") in _FORBIDDEN_PAYLOAD_KEYS_SQUASHED:
        return True
    segments = normalized.split("_")
    if any(segment in FORBIDDEN_PAYLOAD_KEY_TOKENS for segment in segments):
        return True
    return "".join(segments) in FORBIDDEN_PAYLOAD_KEY_TOKENS


def _freeze_payload_value(value: object, key: str) -> Any:
    """Return a recursively immutable, JSON-safe payload value."""

    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"event payload '{key}' must be a finite float")
        return value
    if isinstance(value, bytes | bytearray):
        raise TypeError(f"event payload '{key}' must not carry binary data")
    if isinstance(value, Mapping):
        frozen: dict[str, Any] = {}
        for nested_key, nested_value in value.items():
            if not isinstance(nested_key, str):
                raise TypeError("event payload keys must be strings")
            if _is_forbidden_payload_key(nested_key):
                raise ValueError(f"event payload key '{nested_key}' is not permitted")
            frozen[nested_key] = _freeze_payload_value(nested_value, nested_key)
        return MappingProxyType(frozen)
    if isinstance(value, Sequence):
        return tuple(_freeze_payload_value(item, key) for item in value)

    raise TypeError(
        f"event payload '{key}' must be a descriptive immutable value, "
        f"not {type(value).__name__}"
    )


def _text(value: object, field_name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string")
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} must be non-empty")
    return normalized


def validate_orchestration_event(
    event_type: str,
    payload: Mapping[str, object],
) -> Mapping[str, object]:
    """Validate and freeze one orchestration event payload.

    Returns a recursively immutable, detached copy so a caller cannot mutate an
    already-recorded event, and fails closed on an unknown event name, a
    forbidden key or an opaque runtime value.
    """

    normalized_type = _text(event_type, "event_type")
    if normalized_type not in _ALLOWED_EVENT_TYPE_SET:
        raise ValueError(
            f"event type '{normalized_type}' is not a Phase 11.2 lifecycle event"
        )
    if not isinstance(payload, Mapping):
        raise TypeError("payload must be a mapping")

    return _freeze_payload_value(payload, "payload")


@runtime_checkable
class OrchestrationEventSink(Protocol):
    """Narrow emission boundary for safe orchestration lifecycle events."""

    def emit(
        self,
        event_type: str,
        *,
        request_id: str,
        payload: Mapping[str, object],
    ) -> str | None: ...


@dataclass(frozen=True, slots=True)
class RecordedOrchestrationEvent:
    """One safely recorded orchestration lifecycle event."""

    event_type: str
    request_id: str
    sequence: int
    payload: Mapping[str, object] = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        object.__setattr__(self, "event_type", _text(self.event_type, "event_type"))
        object.__setattr__(self, "request_id", _text(self.request_id, "request_id"))
        if isinstance(self.sequence, bool) or not isinstance(self.sequence, int):
            raise TypeError("sequence must be an int")
        if self.sequence < 0:
            raise ValueError("sequence must be non-negative")
        object.__setattr__(
            self,
            "payload",
            validate_orchestration_event(self.event_type, self.payload),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_type": self.event_type,
            "request_id": self.request_id,
            "sequence": self.sequence,
            "payload": _thaw(self.payload),
        }


def _thaw(value: object) -> Any:
    if isinstance(value, Mapping):
        return {key: _thaw(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw(item) for item in value]
    return value


class RecordingOrchestrationEventSink:
    """Official in-memory recording adapter for tests and local composition.

    It records safe events in emission order and exposes them as an immutable
    tuple.  It is deliberately **not** an event bus: no subscription, no
    replay, no retry and no persistence.
    """

    __slots__ = ("_events",)

    def __init__(self) -> None:
        self._events: list[RecordedOrchestrationEvent] = []

    def emit(
        self,
        event_type: str,
        *,
        request_id: str,
        payload: Mapping[str, object],
    ) -> str:
        """Validate and record one event, returning a deterministic reference."""

        normalized_type = _text(event_type, "event_type")
        normalized_request = _text(request_id, "request_id")
        safe_payload = validate_orchestration_event(normalized_type, payload)

        sequence = len(self._events)
        self._events.append(
            RecordedOrchestrationEvent(
                event_type=normalized_type,
                request_id=normalized_request,
                sequence=sequence,
                payload=safe_payload,
            )
        )
        return f"{normalized_type}:{normalized_request}:{sequence}"

    def events(self) -> tuple[RecordedOrchestrationEvent, ...]:
        """Return the recorded events in emission order."""

        return tuple(self._events)
