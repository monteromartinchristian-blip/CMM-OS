"""Phase 9.20 – Runtime Event Factory and Normalizer.

Creates, normalizes, and validates runtime events.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
import secrets
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


def _compute_fingerprint(
    header: AgentRuntimeEventHeader, payload: AgentRuntimeEventPayload
) -> str:
    """Compute a deterministic fingerprint for an event."""
    payload_str = json.dumps(payload.data, sort_keys=True, default=str)
    raw = f"{header.event_id}:{header.event_type}:{header.schema_version}:{header.occurred_at.isoformat()}:{header.emitted_at.isoformat()}:{payload_str}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


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

    def __init__(self) -> None:
        self._generate_id = _generate_event_id

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
    ) -> AgentRuntimeEvent:
        """Create a new runtime event."""
        if not is_registered_event_type(event_type):
            raise ValueError(f"unknown event_type '{event_type}'")

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
        )

        payload_obj = AgentRuntimeEventPayload(data=payload_copy, raw=None)
        return AgentRuntimeEvent(header=header, payload=payload_obj)

    def from_dict(self, data: dict[str, Any]) -> AgentRuntimeEvent:
        """Create event from dictionary."""
        header_data = data.get("header", {})
        payload_data = data.get("payload", {})

        occurred_at = header_data.get("occurred_at")
        if isinstance(occurred_at, str):
            occurred_at = datetime.fromisoformat(occurred_at)

        emitted_at = header_data.get("emitted_at")
        if isinstance(emitted_at, str):
            emitted_at = datetime.fromisoformat(emitted_at)

        sensitivity = header_data.get("sensitivity", EventSensitivity.INTERNAL)
        if isinstance(sensitivity, str):
            sensitivity = EventSensitivity(sensitivity)

        payload_dict = payload_data.get("data", {})
        if not isinstance(payload_dict, dict):
            payload_dict = {}

        return self.create_event(
            event_type=header_data["event_type"],
            payload=payload_dict,
            event_id=header_data.get("event_id"),
            schema_version=header_data.get("schema_version", "1.0.0"),
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
            permissions=header_data.get("permissions", []),
            metadata=header_data.get("metadata", {}),
        )

    def to_dict(self, event: AgentRuntimeEvent) -> dict[str, Any]:
        """Serialize event to dictionary."""
        return {
            "header": {
                "event_id": event.header.event_id,
                "event_type": event.header.event_type,
                "schema_version": event.header.schema_version,
                "occurred_at": event.header.occurred_at.isoformat(),
                "emitted_at": event.header.emitted_at.isoformat(),
                "agent_id": event.header.agent_id,
                "agent_run_id": event.header.agent_run_id,
                "goal_id": event.header.goal_id,
                "workflow_id": event.header.workflow_id,
                "task_id": event.header.task_id,
                "iteration_id": event.header.iteration_id,
                "correlation_id": event.header.correlation_id,
                "causation_id": event.header.causation_id,
                "actor_id": event.header.actor_id,
                "source": event.header.source,
                "sensitivity": event.header.sensitivity.value,
                "permissions": list(event.header.permissions),
                "metadata": dict(event.header.metadata),
            },
            "payload": {
                "data": dict(event.payload.data),
                "raw": event.payload.raw,
            },
        }

    def to_json(self, event: AgentRuntimeEvent) -> str:
        """Serialize event to JSON string."""
        return json.dumps(self.to_dict(event), default=str)


class AgentRuntimeEventNormalizer:
    """Normalizer for runtime events."""

    def __init__(self, factory: AgentRuntimeEventFactory) -> None:
        self.factory = factory

    def normalize(self, event: AgentRuntimeEvent) -> AgentRuntimeEvent:
        """Normalize timestamps and complete correlation."""
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
            metadata=dict(header.metadata),
        )

        return AgentRuntimeEvent(
            header=normalized_header,
            payload=AgentRuntimeEventPayload(
                data=dict(event.payload.data),
                raw=event.payload.raw,
            ),
        )
