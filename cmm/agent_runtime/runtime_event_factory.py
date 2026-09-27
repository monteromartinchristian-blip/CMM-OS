"""Phase 9.20 – Runtime Event Factory and Normalizer.

Creates, normalizes, and validates runtime events.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
import secrets
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from typing import Any

from cmm.agent_runtime.runtime_event_contracts import (
    AgentRuntimeEvent,
    AgentRuntimeEventHeader,
    AgentRuntimeEventPayload,
    EventSensitivity,
)
from cmm.agent_runtime.runtime_event_types import is_registered_event_type

# Regex patterns to detect sensitive content in payloads
_CHAIN_OF_THOUGHT_PATTERNS = [
    re.compile(r"(?i)chain[-_\s]of[-_\s]thought"),
    re.compile(r"(?i)cot"),
    re.compile(r"(?i)step[-_\s]by[-_\s]step"),
    re.compile(r"(?i)my[-_\s]reasoning"),
    re.compile(r"(?i)internal[-_\s]reasoning"),
    re.compile(r"(?i)thinking[-_\s]process"),
]

_SECRET_PATTERNS = [
    re.compile(r"(?i)(api[_-]?key|apikey)"),
    re.compile(r"(?i)(secret[_-]?key|secretkey)"),
    re.compile(r"(?i)password"),
    re.compile(r"(?i)passwd"),
    re.compile(r"(?i)credential"),
    re.compile(r"(?i)private[_-]?key"),
    re.compile(r"(?i)auth[_-]?token"),
    re.compile(r"(?i)access[_-]?token"),
    re.compile(r"(?i)bearer"),
    re.compile(r"(?i)-----BEGIN"),
]


def _generate_event_id() -> str:
    """Generate a unique event identifier."""
    return f"evt_{secrets.token_hex(12)}"


def _normalize_timestamp(value: datetime | None) -> datetime:
    """Ensure timestamp is timezone-aware UTC."""
    if value is None:
        return datetime.now(timezone.utc)
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _canonical_event_value(value: Any) -> Any:
    """Return the canonical JSON-compatible form of one nested event value.

    The nested facts of a canonical event (``payload.data``, ``header.metadata``)
    are JSON structures, and the Phase 11.22 boundary already rejects every value
    that is not an approved descriptive scalar, mapping or sequence *before*
    persistence.  This function is therefore a pure shape normalization, not a
    safety mechanism: it converts mappings to plain ``dict``, any non-``str``/bytes
    sequence to a plain ``list``, and canonicalizes a ``datetime`` through the
    same ISO-8601 spelling the durable record uses.

    It exists so that the canonical serialization — and therefore the content
    fingerprint — never depends on ``json.dumps(default=str)`` to stringify a
    value.  Relying on ``default=str`` is exactly what let an opaque runtime object
    stringify a credential into durable evidence, and a value that only survives
    serialization because of ``default=str`` does not round-trip.
    """

    if isinstance(value, Mapping):
        return {key: _canonical_event_value(item) for key, item in value.items()}
    if isinstance(value, str):
        return value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, (bytes, bytearray)):
        # Unreachable through the Phase 11.22 gate, which rejects binary values
        # before an event exists.  Kept explicit so the canonicalizer can never
        # silently coerce a binary value if it is ever reached another way.
        raise TypeError("binary values have no canonical event representation")
    if isinstance(value, Sequence):
        return [_canonical_event_value(item) for item in value]
    return value


def canonical_event_dict(event: AgentRuntimeEvent) -> dict[str, Any]:
    """Return the one canonical serialization of *event*.

    This is the single source of truth for both durable persistence and content
    identity.  The fingerprint is computed from exactly this mapping, so there is
    no second, manually maintained list of "identity-relevant" fields that could
    drift away from what is actually persisted.

    Every nested value is normalized to a JSON-compatible shape, so the emitted
    mapping is exactly what durable JSON reopens as: a mapping reopens as a
    ``dict`` and a sequence reopens as a ``list``.  There is consequently one
    stable canonical shape for live, persisted and replayed events.
    """

    header = event.header
    return {
        "header": {
            "event_id": header.event_id,
            "event_type": header.event_type,
            "schema_version": header.schema_version,
            "occurred_at": header.occurred_at.isoformat(),
            "emitted_at": header.emitted_at.isoformat(),
            "agent_id": header.agent_id,
            "agent_run_id": header.agent_run_id,
            "goal_id": header.goal_id,
            "workflow_id": header.workflow_id,
            "task_id": header.task_id,
            "iteration_id": header.iteration_id,
            "correlation_id": header.correlation_id,
            "causation_id": header.causation_id,
            "actor_id": header.actor_id,
            "source": header.source,
            "sensitivity": header.sensitivity.value,
            "permissions": list(header.permissions),
            "metadata": _canonical_event_value(header.metadata),
            "producer": header.producer,
            "aggregate_id": header.aggregate_id,
        },
        "payload": {
            "data": _canonical_event_value(event.payload.data),
            "raw": event.payload.raw,
        },
    }


def _canonical_serialization(event: AgentRuntimeEvent) -> str:
    """Return the deterministic canonical serialization used for the fingerprint.

    The canonical mapping is already JSON-compatible, so this deliberately does
    **not** pass ``default=str``: a value that is not canonically serializable must
    fail closed rather than be stringified into content identity.
    """

    return json.dumps(canonical_event_dict(event), sort_keys=True, allow_nan=False)


def event_fingerprint(event: AgentRuntimeEvent) -> str:
    """Return the canonical, deterministic content fingerprint of *event*.

    Phase 11.22 uses this identity as its content-bound deduplication key: two
    persisted events with the same event ID and the same fingerprint are an
    idempotent duplicate, while the same event ID with a different fingerprint is
    an identity conflict that fails closed.

    The fingerprint hashes the complete canonical serialization of the event, so
    it necessarily covers every persisted header field (including correlation,
    causation, sensitivity, permissions and metadata) and every persisted payload
    field (including ``payload.raw``).  A materially different event can therefore
    never share a fingerprint with a persisted one, and a stored record mutated in
    any persisted field no longer matches its stored fingerprint.
    """

    if not isinstance(event, AgentRuntimeEvent):
        raise TypeError("event must be an AgentRuntimeEvent")
    serialized = _canonical_serialization(event)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _check_payload_safety(payload: dict[str, Any]) -> None:
    """Ensure payload does not contain chain-of-thought or secrets."""

    def scan_value(value: Any) -> None:
        if isinstance(value, dict):
            for k, v in value.items():
                scan_value(k)
                scan_value(v)
        elif isinstance(value, list):
            for item in value:
                scan_value(item)
        elif isinstance(value, str):
            for pattern in _CHAIN_OF_THOUGHT_PATTERNS:
                if pattern.search(value):
                    raise ValueError("payload contains chain-of-thought content")
            for pattern in _SECRET_PATTERNS:
                if pattern.search(value):
                    raise ValueError("payload contains secret content")

    scan_value(payload)


class AgentRuntimeEventFactory:
    """Factory for creating runtime events."""

    #: The one canonical event schema version this build can deserialize.
    SUPPORTED_SCHEMA_VERSION = "1.0.0"

    def __init__(self) -> None:
        self._generate_id = _generate_event_id

    @classmethod
    def supports_schema_version(cls, schema_version: object) -> bool:
        """Return whether this build can deserialize *schema_version*.

        This is the one canonical supported-schema knowledge.  Persistence and the
        Phase 11.22 publication boundary ask here rather than duplicating a
        version constant, so the two can never drift apart.
        """

        return (
            isinstance(schema_version, str)
            and schema_version == cls.SUPPORTED_SCHEMA_VERSION
        )

    def create_event(
        self,
        event_type: str,
        payload: dict[str, Any],
        *,
        event_id: str | None = None,
        schema_version: str = "1.0.0",
        occurred_at: datetime | None = None,
        emitted_at: datetime | None = None,
        agent_id: str | None = None,
        agent_run_id: str | None = None,
        goal_id: str | None = None,
        workflow_id: str | None = None,
        task_id: str | None = None,
        iteration_id: str | None = None,
        correlation_id: str | None = None,
        causation_id: str | None = None,
        actor_id: str | None = None,
        source: str = "agent_runtime",
        sensitivity: EventSensitivity = EventSensitivity.INTERNAL,
        permissions: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        producer: str | None = None,
        aggregate_id: str | None = None,
        raw: str | None = None,
    ) -> AgentRuntimeEvent:
        """Create a new runtime event."""
        if not is_registered_event_type(event_type):
            raise ValueError(f"unknown event_type '{event_type}'")

        if raw is not None and not isinstance(raw, str):
            raise TypeError("payload raw content must be a string or None")

        event_id = event_id or self._generate_id()
        occurred_at = _normalize_timestamp(occurred_at)
        emitted_at = _normalize_timestamp(emitted_at)

        if emitted_at < occurred_at:
            raise ValueError("emitted_at must be after or equal to occurred_at")

        payload_copy = copy.deepcopy(payload)
        _check_payload_safety(payload_copy)

        metadata_copy = copy.deepcopy(metadata) if metadata else {}
        permissions_copy = list(permissions) if permissions else []

        header = AgentRuntimeEventHeader(
            event_id=event_id,
            event_type=event_type,
            schema_version=schema_version,
            occurred_at=occurred_at,
            emitted_at=emitted_at,
            agent_id=agent_id,
            agent_run_id=agent_run_id,
            goal_id=goal_id,
            workflow_id=workflow_id,
            task_id=task_id,
            iteration_id=iteration_id,
            correlation_id=correlation_id,
            causation_id=causation_id,
            actor_id=actor_id,
            source=source,
            sensitivity=sensitivity,
            permissions=permissions_copy,
            metadata=metadata_copy,
            producer=producer,
            aggregate_id=aggregate_id,
        )

        payload_obj = AgentRuntimeEventPayload(data=payload_copy, raw=raw)
        return AgentRuntimeEvent(header=header, payload=payload_obj)

    def from_dict(self, data: dict[str, Any]) -> AgentRuntimeEvent:
        """Create event from dictionary.

        Every malformed persisted shape fails deterministically with a
        ``TypeError`` or ``ValueError``: the durable repository converts those
        into its canonical corruption error, and no shape may escape as an
        incidental ``AttributeError``.
        """
        if not isinstance(data, dict):
            raise TypeError("serialized event must be a mapping")

        header_data = data.get("header", {})
        payload_data = data.get("payload", {})

        if not isinstance(header_data, dict):
            raise TypeError("serialized event header must be a mapping")
        if "event_type" not in header_data:
            raise ValueError("serialized event header has no event_type")
        if not isinstance(payload_data, dict):
            raise TypeError("serialized event payload must be a mapping")

        schema_version = header_data.get("schema_version", "1.0.0")
        if not isinstance(schema_version, str):
            raise TypeError("serialized event schema_version must be a string")
        if not self.supports_schema_version(schema_version):
            raise ValueError(f"unsupported event schema_version '{schema_version}'")

        occurred_at = header_data.get("occurred_at")
        if isinstance(occurred_at, str):
            occurred_at = datetime.fromisoformat(occurred_at)

        emitted_at = header_data.get("emitted_at")
        if isinstance(emitted_at, str):
            emitted_at = datetime.fromisoformat(emitted_at)

        sensitivity = header_data.get("sensitivity", EventSensitivity.INTERNAL)
        if isinstance(sensitivity, str):
            sensitivity = EventSensitivity(sensitivity)

        permissions = header_data.get("permissions", [])
        if not isinstance(permissions, list):
            raise TypeError("serialized event permissions must be a list")

        metadata = header_data.get("metadata", {})
        if not isinstance(metadata, dict):
            raise TypeError("serialized event metadata must be a mapping")

        payload_dict = payload_data.get("data", {})
        if not isinstance(payload_dict, dict):
            raise TypeError("serialized event payload.data must be a mapping")

        raw = payload_data.get("raw")
        if raw is not None and not isinstance(raw, str):
            raise TypeError("serialized event payload.raw must be a string or None")

        return self.create_event(
            event_type=header_data["event_type"],
            payload=payload_dict,
            event_id=header_data.get("event_id"),
            schema_version=schema_version,
            occurred_at=occurred_at,
            emitted_at=emitted_at,
            agent_id=header_data.get("agent_id"),
            agent_run_id=header_data.get("agent_run_id"),
            goal_id=header_data.get("goal_id"),
            workflow_id=header_data.get("workflow_id"),
            task_id=header_data.get("task_id"),
            iteration_id=header_data.get("iteration_id"),
            correlation_id=header_data.get("correlation_id"),
            causation_id=header_data.get("causation_id"),
            actor_id=header_data.get("actor_id"),
            source=header_data.get("source", "agent_runtime"),
            sensitivity=sensitivity,
            permissions=permissions,
            metadata=metadata,
            producer=header_data.get("producer"),
            aggregate_id=header_data.get("aggregate_id"),
            raw=raw,
        )

    def to_dict(self, event: AgentRuntimeEvent) -> dict[str, Any]:
        """Serialize event to the one canonical dictionary representation."""

        return canonical_event_dict(event)

    def to_json(self, event: AgentRuntimeEvent) -> str:
        """Serialize event to its canonical JSON string.

        The canonical mapping is already JSON-compatible, so no ``default=str``
        fallback is used: a value that is not canonically serializable must fail
        closed rather than be stringified into persisted evidence.
        """

        return json.dumps(self.to_dict(event), allow_nan=False)


class AgentRuntimeEventNormalizer:
    """Normalizer for runtime events."""

    def __init__(self, factory: AgentRuntimeEventFactory) -> None:
        self.factory = factory

    def normalize(self, event: AgentRuntimeEvent) -> AgentRuntimeEvent:
        """Normalize timestamps, correlation and canonical nested container shape.

        The returned event shares **no** nested container with the caller.  A
        shallow ``dict(...)`` copy would leave the nested ``payload.data``,
        ``header.metadata`` and their children aliased to the caller's own objects,
        so a caller could mutate the canonical event it just published through an
        alias it still holds.  Normalization therefore deep-detaches every nested
        fact into the one canonical JSON-compatible shape.
        """
        header = event.header

        occurred_at = _normalize_timestamp(header.occurred_at)
        emitted_at = _normalize_timestamp(header.emitted_at)

        correlation_id: str | None
        if header.causation_id and not header.correlation_id:
            # causation implies correlation if absent
            correlation_id = header.causation_id
        else:
            correlation_id = header.correlation_id

        normalized_header = AgentRuntimeEventHeader(
            event_id=header.event_id,
            event_type=header.event_type,
            schema_version=header.schema_version,
            occurred_at=occurred_at,
            emitted_at=emitted_at,
            agent_id=header.agent_id,
            agent_run_id=header.agent_run_id,
            goal_id=header.goal_id,
            workflow_id=header.workflow_id,
            task_id=header.task_id,
            iteration_id=header.iteration_id,
            correlation_id=correlation_id,
            causation_id=header.causation_id,
            actor_id=header.actor_id,
            source=header.source,
            sensitivity=header.sensitivity,
            permissions=list(header.permissions),
            metadata=_canonical_event_value(header.metadata),
            producer=header.producer,
            aggregate_id=header.aggregate_id,
        )

        return AgentRuntimeEvent(
            header=normalized_header,
            payload=AgentRuntimeEventPayload(
                data=_canonical_event_value(event.payload.data),
                raw=event.payload.raw,
            ),
        )
