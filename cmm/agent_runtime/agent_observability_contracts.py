"""Immutable contracts for Phase 9.26 agent observability.

The Phase 9.19 ``AgentTrace`` and ``AgentTraceStatus`` contracts remain
canonical.  This module composes around them and deliberately defines neither
name.
"""

from __future__ import annotations

import math
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from types import MappingProxyType
from typing import Any

from cmm.agent_runtime.agent_observability_enums import (
    AgentAuditOutcome,
    AgentAuditSeverity,
    AgentHealthStatus,
    AgentMetricKind,
    AgentTelemetryKind,
)
from cmm.agent_runtime.agent_observability_errors import (
    InvalidAgentObservabilityContractError,
)

REDACTED = "[REDACTED]"

_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:\-]{0,127}$")
_NAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_.:\-]{0,127}$")
_SENSITIVE_KEYS = frozenset(
    {
        "password",
        "passwd",
        "secret",
        "token",
        "api_key",
        "apikey",
        "authorization",
        "cookie",
        "credential",
        "private_key",
        "access_key",
        "refresh_token",
        "session",
    }
)
_URL_CREDS_RE = re.compile(
    r"([a-zA-Z][a-zA-Z0-9+.-]*://)([^@\s]+:[^@\s]+@)", re.IGNORECASE
)
_EMBEDDED_SECRET_RE = re.compile(
    r"(?i)\b(password|passwd|secret|token|api_key|apikey|authorization|cookie|"
    r"credential|private_key|access_key|refresh_token|session)\s*([:=])\s*"
    r"(?:Bearer\s+)?[^\s,;]+"
)


def _sensitive_key(key: str) -> bool:
    normalized = key.casefold()
    return any(part in normalized for part in _SENSITIVE_KEYS)


def _sanitize_string(value: str) -> str:
    value = _URL_CREDS_RE.sub(r"\1[REDACTED]@", value)
    return _EMBEDDED_SECRET_RE.sub(
        lambda match: f"{match.group(1)}{match.group(2)}{REDACTED}", value
    )


def sanitize_agent_observability_data(value: Any) -> Any:
    """Return a conservative recursively sanitized copy of ``value``."""

    if isinstance(value, Mapping):
        result: dict[Any, Any] = {}
        for key, item in value.items():
            if isinstance(key, str) and _sensitive_key(key):
                result[key] = REDACTED
            else:
                result[key] = sanitize_agent_observability_data(item)
        return result
    if isinstance(value, tuple):
        return tuple(sanitize_agent_observability_data(item) for item in value)
    if isinstance(value, list):
        return [sanitize_agent_observability_data(item) for item in value]
    if isinstance(value, set | frozenset):
        return tuple(
            sanitize_agent_observability_data(item) for item in sorted(value, key=repr)
        )
    if isinstance(value, str):
        return _sanitize_string(value)
    return value


def _freeze_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType(
            {str(key): _freeze_value(item) for key, item in value.items()}
        )
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_value(item) for item in value)
    if isinstance(value, (set, frozenset)):
        return tuple(_freeze_value(item) for item in sorted(value, key=repr))
    return value


def _thaw(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _thaw(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw(item) for item in value]
    if isinstance(value, Decimal):
        return str(value)
    return value


def _freeze_mapping(
    value: Mapping[str, Any] | None, field_name: str
) -> MappingProxyType[str, Any]:
    if value is not None and not isinstance(value, Mapping):
        raise InvalidAgentObservabilityContractError(f"{field_name} must be a mapping")
    sanitized = sanitize_agent_observability_data(value or {})
    return _freeze_value(sanitized)


def _freeze_str_tuple(value: Iterable[str], field_name: str) -> tuple[str, ...]:
    if isinstance(value, str):
        raise InvalidAgentObservabilityContractError(
            f"{field_name} must be an iterable of strings"
        )
    result = tuple(value)
    if any(not isinstance(item, str) or not item.strip() for item in result):
        raise InvalidAgentObservabilityContractError(
            f"{field_name} must contain non-empty strings"
        )
    return result


def _require_id(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not _ID_RE.fullmatch(value):
        raise InvalidAgentObservabilityContractError(f"invalid {field_name}")
    return value


def _optional_id(value: Any, field_name: str) -> str | None:
    return None if value is None else _require_id(value, field_name)


def _non_empty(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise InvalidAgentObservabilityContractError(
            f"{field_name} must be a non-empty string"
        )
    return value.strip()


def _stable_name(value: Any, field_name: str) -> str:
    value = _non_empty(value, field_name)
    if not _NAME_RE.fullmatch(value):
        raise InvalidAgentObservabilityContractError(f"invalid {field_name}")
    return value


def _utc(value: datetime, field_name: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise InvalidAgentObservabilityContractError(
            f"{field_name} must be timezone-aware"
        )
    return value.astimezone(timezone.utc)


def _parse_datetime(value: Any, field_name: str) -> datetime:
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value)
        except ValueError as exc:
            raise InvalidAgentObservabilityContractError(
                f"invalid {field_name}"
            ) from exc
    return _utc(value, field_name)


def _finite_non_negative(value: Any, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
        raise InvalidAgentObservabilityContractError(f"{field_name} must be numeric")
    result = float(value)
    if not math.isfinite(result) or result < 0:
        raise InvalidAgentObservabilityContractError(f"invalid {field_name}")
    return result


def _non_negative_int(value: Any, field_name: str, *, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise InvalidAgentObservabilityContractError(f"invalid {field_name}")
    return value


def _ratio(value: Any, field_name: str) -> float:
    result = _finite_non_negative(value, field_name)
    if result > 1.0:
        raise InvalidAgentObservabilityContractError(f"invalid {field_name}")
    return result


def _decimal_non_negative(value: Any, field_name: str) -> Decimal:
    if isinstance(value, (bool, float)):
        raise InvalidAgentObservabilityContractError(
            f"{field_name} must use Decimal, int, or string"
        )
    try:
        result = Decimal(value)
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise InvalidAgentObservabilityContractError(f"invalid {field_name}") from exc
    if not result.is_finite() or result < 0:
        raise InvalidAgentObservabilityContractError(f"invalid {field_name}")
    return result


def _enum(value: Any, enum_type: type[Any], field_name: str) -> Any:
    if isinstance(value, enum_type):
        return value
    if isinstance(value, str):
        try:
            return enum_type(value)
        except ValueError as exc:
            raise InvalidAgentObservabilityContractError(
                f"invalid {field_name}"
            ) from exc
    raise InvalidAgentObservabilityContractError(f"invalid {field_name}")


def _enum_value(value: Any) -> str:
    """Serialize a value already normalized by ``_enum``."""

    result = getattr(value, "value", None)
    if not isinstance(result, str):
        raise InvalidAgentObservabilityContractError("invalid enum value")
    return result


def _trace_status(value: Any) -> Any:
    from cmm.agent_runtime.enums import AgentTraceStatus as CanonicalTraceStatus

    return _enum(value, CanonicalTraceStatus, "status")


def _validate_numeric_tree(value: Any, field_name: str) -> None:
    if isinstance(value, Mapping):
        for item in value.values():
            _validate_numeric_tree(item, field_name)
    elif isinstance(value, tuple):
        for item in value:
            _validate_numeric_tree(item, field_name)
    elif isinstance(value, float) and not math.isfinite(value):
        raise InvalidAgentObservabilityContractError(f"invalid {field_name}")


@dataclass(frozen=True, slots=True)
class AgentTelemetryRecord:
    """Normalized immutable Agent Runtime telemetry fact."""

    id: str
    kind: AgentTelemetryKind | str
    timestamp: datetime
    agent_id: str | None = None
    agent_run_id: str | None = None
    goal_id: str | None = None
    operation_id: str | None = None
    workflow_id: str | None = None
    delegation_id: str | None = None
    checkpoint_id: str | None = None
    approval_id: str | None = None
    actor_id: str | None = None
    trace_id: str | None = None
    span_id: str | None = None
    parent_span_id: str | None = None
    correlation_id: str | None = None
    causation_id: str | None = None
    severity: AgentAuditSeverity | str = AgentAuditSeverity.INFO
    outcome: AgentAuditOutcome | str = AgentAuditOutcome.UNKNOWN
    duration_ms: float | None = None
    attempt: int = 1
    retry_count: int = 0
    resource_ids: tuple[str, ...] = ()
    reason_codes: tuple[str, ...] = ()
    measurements: Mapping[str, Any] = field(default_factory=dict)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", _require_id(self.id, "id"))
        object.__setattr__(self, "kind", _enum(self.kind, AgentTelemetryKind, "kind"))
        object.__setattr__(self, "timestamp", _utc(self.timestamp, "timestamp"))
        for name in (
            "agent_id",
            "agent_run_id",
            "goal_id",
            "operation_id",
            "workflow_id",
            "delegation_id",
            "checkpoint_id",
            "approval_id",
            "actor_id",
            "trace_id",
            "span_id",
            "parent_span_id",
            "correlation_id",
            "causation_id",
        ):
            object.__setattr__(self, name, _optional_id(getattr(self, name), name))
        if self.span_id is not None and self.parent_span_id == self.span_id:
            raise InvalidAgentObservabilityContractError(
                "parent_span_id cannot equal span_id"
            )
        object.__setattr__(
            self, "severity", _enum(self.severity, AgentAuditSeverity, "severity")
        )
        object.__setattr__(
            self, "outcome", _enum(self.outcome, AgentAuditOutcome, "outcome")
        )
        if self.duration_ms is not None:
            object.__setattr__(
                self,
                "duration_ms",
                _finite_non_negative(self.duration_ms, "duration_ms"),
            )
        object.__setattr__(
            self, "attempt", _non_negative_int(self.attempt, "attempt", minimum=1)
        )
        object.__setattr__(
            self, "retry_count", _non_negative_int(self.retry_count, "retry_count")
        )
        object.__setattr__(
            self, "resource_ids", _freeze_str_tuple(self.resource_ids, "resource_ids")
        )
        object.__setattr__(
            self, "reason_codes", _freeze_str_tuple(self.reason_codes, "reason_codes")
        )
        measurements = _freeze_mapping(self.measurements, "measurements")
        _validate_numeric_tree(measurements, "measurements")
        object.__setattr__(self, "measurements", measurements)
        object.__setattr__(self, "metadata", _freeze_mapping(self.metadata, "metadata"))

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": _enum_value(self.kind),
            "timestamp": self.timestamp.isoformat(),
            "agent_id": self.agent_id,
            "agent_run_id": self.agent_run_id,
            "goal_id": self.goal_id,
            "operation_id": self.operation_id,
            "workflow_id": self.workflow_id,
            "delegation_id": self.delegation_id,
            "checkpoint_id": self.checkpoint_id,
            "approval_id": self.approval_id,
            "actor_id": self.actor_id,
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "parent_span_id": self.parent_span_id,
            "correlation_id": self.correlation_id,
            "causation_id": self.causation_id,
            "severity": _enum_value(self.severity),
            "outcome": _enum_value(self.outcome),
            "duration_ms": self.duration_ms,
            "attempt": self.attempt,
            "retry_count": self.retry_count,
            "resource_ids": list(self.resource_ids),
            "reason_codes": list(self.reason_codes),
            "measurements": _thaw(self.measurements),
            "metadata": _thaw(self.metadata),
        }

    serialize = to_dict

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> AgentTelemetryRecord:
        data = dict(value)
        data["timestamp"] = _parse_datetime(data.get("timestamp"), "timestamp")
        return cls(**data)

    from_dict = from_mapping


@dataclass(frozen=True, slots=True)
class AgentMetricPoint:
    """One typed, timestamped metric sample."""

    id: str
    name: str
    kind: AgentMetricKind | str
    value: int | float | Decimal | str
    unit: str
    timestamp: datetime
    dimensions: Mapping[str, Any] = field(default_factory=dict)
    agent_id: str | None = None
    agent_run_id: str | None = None
    goal_id: str | None = None
    operation_id: str | None = None
    trace_id: str | None = None
    correlation_id: str | None = None
    sample_count: int = 1
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", _require_id(self.id, "id"))
        object.__setattr__(self, "name", _stable_name(self.name, "name"))
        kind = _enum(self.kind, AgentMetricKind, "kind")
        object.__setattr__(self, "kind", kind)
        if kind == AgentMetricKind.COST:
            normalized: int | float | Decimal = _decimal_non_negative(
                self.value, "value"
            )
        else:
            if isinstance(self.value, str):
                raise InvalidAgentObservabilityContractError("value must be numeric")
            normalized = _finite_non_negative(self.value, "value")
            if kind == AgentMetricKind.RATIO:
                normalized = _ratio(normalized, "value")
            if kind == AgentMetricKind.TOKENS and normalized != int(normalized):
                raise InvalidAgentObservabilityContractError(
                    "token value must be an integer"
                )
            if kind == AgentMetricKind.TOKENS:
                normalized = int(normalized)
        object.__setattr__(self, "value", normalized)
        object.__setattr__(self, "unit", _non_empty(self.unit, "unit"))
        object.__setattr__(self, "timestamp", _utc(self.timestamp, "timestamp"))
        for name in (
            "agent_id",
            "agent_run_id",
            "goal_id",
            "operation_id",
            "trace_id",
            "correlation_id",
        ):
            object.__setattr__(self, name, _optional_id(getattr(self, name), name))
        object.__setattr__(
            self,
            "sample_count",
            _non_negative_int(self.sample_count, "sample_count", minimum=1),
        )
        object.__setattr__(
            self, "dimensions", _freeze_mapping(self.dimensions, "dimensions")
        )
        object.__setattr__(self, "metadata", _freeze_mapping(self.metadata, "metadata"))

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "kind": _enum_value(self.kind),
            "value": str(self.value) if isinstance(self.value, Decimal) else self.value,
            "unit": self.unit,
            "timestamp": self.timestamp.isoformat(),
            "dimensions": _thaw(self.dimensions),
            "agent_id": self.agent_id,
            "agent_run_id": self.agent_run_id,
            "goal_id": self.goal_id,
            "operation_id": self.operation_id,
            "trace_id": self.trace_id,
            "correlation_id": self.correlation_id,
            "sample_count": self.sample_count,
            "metadata": _thaw(self.metadata),
        }

    serialize = to_dict

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> AgentMetricPoint:
        data = dict(value)
        data["timestamp"] = _parse_datetime(data.get("timestamp"), "timestamp")
        return cls(**data)

    from_dict = from_mapping


@dataclass(frozen=True, slots=True)
class AgentSpan:
    """A span in the operational graph around a canonical Phase 9.19 trace."""

    span_id: str
    trace_id: str
    parent_span_id: str | None
    operation_id: str
    operation_name: str
    started_at: datetime
    agent_run_id: str | None = None
    goal_id: str | None = None
    completed_at: datetime | None = None
    status: Any = "open"
    duration_ms: float | None = None
    attributes: Mapping[str, Any] = field(default_factory=dict)
    error_summary: str | None = None
    linked_event_ids: tuple[str, ...] = ()
    retry_count: int = 0
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "span_id", _require_id(self.span_id, "span_id"))
        object.__setattr__(self, "trace_id", _require_id(self.trace_id, "trace_id"))
        object.__setattr__(
            self, "parent_span_id", _optional_id(self.parent_span_id, "parent_span_id")
        )
        if self.parent_span_id == self.span_id:
            raise InvalidAgentObservabilityContractError(
                "parent_span_id cannot equal span_id"
            )
        object.__setattr__(
            self, "operation_id", _require_id(self.operation_id, "operation_id")
        )
        object.__setattr__(
            self, "operation_name", _non_empty(self.operation_name, "operation_name")
        )
        object.__setattr__(self, "started_at", _utc(self.started_at, "started_at"))
        object.__setattr__(
            self, "agent_run_id", _optional_id(self.agent_run_id, "agent_run_id")
        )
        object.__setattr__(self, "goal_id", _optional_id(self.goal_id, "goal_id"))
        status = _trace_status(self.status)
        object.__setattr__(self, "status", status)
        completed = self.completed_at
        if completed is not None:
            completed = _utc(completed, "completed_at")
            if completed < self.started_at:
                raise InvalidAgentObservabilityContractError(
                    "completed_at cannot be before started_at"
                )
            object.__setattr__(self, "completed_at", completed)
        if status.value == "open" and completed is not None:
            raise InvalidAgentObservabilityContractError(
                "open span cannot have completed_at"
            )
        duration = self.duration_ms
        if completed is not None and duration is None:
            duration = (completed - self.started_at).total_seconds() * 1000
        if duration is not None:
            duration = _finite_non_negative(duration, "duration_ms")
        object.__setattr__(self, "duration_ms", duration)
        if self.error_summary is not None:
            object.__setattr__(
                self,
                "error_summary",
                _sanitize_string(_non_empty(self.error_summary, "error_summary")),
            )
        object.__setattr__(
            self, "attributes", _freeze_mapping(self.attributes, "attributes")
        )
        object.__setattr__(
            self,
            "linked_event_ids",
            _freeze_str_tuple(self.linked_event_ids, "linked_event_ids"),
        )
        object.__setattr__(
            self, "retry_count", _non_negative_int(self.retry_count, "retry_count")
        )
        object.__setattr__(self, "metadata", _freeze_mapping(self.metadata, "metadata"))

    def to_dict(self) -> dict[str, Any]:
        return {
            "span_id": self.span_id,
            "trace_id": self.trace_id,
            "parent_span_id": self.parent_span_id,
            "agent_run_id": self.agent_run_id,
            "goal_id": self.goal_id,
            "operation_id": self.operation_id,
            "operation_name": self.operation_name,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat()
            if self.completed_at
            else None,
            "status": _enum_value(self.status),
            "duration_ms": self.duration_ms,
            "attributes": _thaw(self.attributes),
            "error_summary": self.error_summary,
            "linked_event_ids": list(self.linked_event_ids),
            "retry_count": self.retry_count,
            "metadata": _thaw(self.metadata),
        }

    serialize = to_dict

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> AgentSpan:
        data = dict(value)
        data["started_at"] = _parse_datetime(data.get("started_at"), "started_at")
        if data.get("completed_at") is not None:
            data["completed_at"] = _parse_datetime(data["completed_at"], "completed_at")
        return cls(**data)

    from_dict = from_mapping


@dataclass(frozen=True, slots=True)
class AgentTraceMetrics:
    """Span-derived metrics for one canonical trace."""

    trace_id: str
    span_count: int = 0
    error_count: int = 0
    retry_count: int = 0
    total_duration_ms: float = 0.0

    def __post_init__(self) -> None:
        object.__setattr__(self, "trace_id", _require_id(self.trace_id, "trace_id"))
        for name in ("span_count", "error_count", "retry_count"):
            object.__setattr__(self, name, _non_negative_int(getattr(self, name), name))
        object.__setattr__(
            self,
            "total_duration_ms",
            _finite_non_negative(self.total_duration_ms, "total_duration_ms"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "span_count": self.span_count,
            "error_count": self.error_count,
            "retry_count": self.retry_count,
            "total_duration_ms": self.total_duration_ms,
        }

    serialize = to_dict

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> AgentTraceMetrics:
        return cls(**dict(value))

    from_dict = from_mapping


@dataclass(frozen=True, slots=True)
class AgentTraceLink:
    """Typed relation between canonical traces, normally a delegation."""

    id: str
    parent_trace_id: str
    child_trace_id: str
    relation: str
    timestamp: datetime
    delegation_id: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", _require_id(self.id, "id"))
        object.__setattr__(
            self,
            "parent_trace_id",
            _require_id(self.parent_trace_id, "parent_trace_id"),
        )
        object.__setattr__(
            self,
            "child_trace_id",
            _require_id(self.child_trace_id, "child_trace_id"),
        )
        if self.parent_trace_id == self.child_trace_id:
            raise InvalidAgentObservabilityContractError(
                "trace link cannot reference itself"
            )
        object.__setattr__(self, "relation", _stable_name(self.relation, "relation"))
        object.__setattr__(self, "timestamp", _utc(self.timestamp, "timestamp"))
        object.__setattr__(
            self,
            "delegation_id",
            _optional_id(self.delegation_id, "delegation_id"),
        )
        object.__setattr__(self, "metadata", _freeze_mapping(self.metadata, "metadata"))

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "parent_trace_id": self.parent_trace_id,
            "child_trace_id": self.child_trace_id,
            "relation": self.relation,
            "delegation_id": self.delegation_id,
            "timestamp": self.timestamp.isoformat(),
            "metadata": _thaw(self.metadata),
        }

    serialize = to_dict

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> AgentTraceLink:
        data = dict(value)
        data["timestamp"] = _parse_datetime(data.get("timestamp"), "timestamp")
        return cls(**data)

    from_dict = from_mapping


@dataclass(frozen=True, slots=True)
class AgentTraceSnapshot:
    """Operational span snapshot keyed by a canonical trace ID."""

    id: str
    trace_id: str
    root_span_id: str
    agent_run_id: str
    goal_id: str
    started_at: datetime
    status: Any
    metrics: AgentTraceMetrics
    agent_id: str | None = None
    completed_at: datetime | None = None
    child_trace_ids: tuple[str, ...] = ()
    correlation_id: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", _require_id(self.id, "id"))
        object.__setattr__(self, "trace_id", _require_id(self.trace_id, "trace_id"))
        object.__setattr__(
            self, "root_span_id", _require_id(self.root_span_id, "root_span_id")
        )
        object.__setattr__(
            self, "agent_run_id", _require_id(self.agent_run_id, "agent_run_id")
        )
        object.__setattr__(self, "goal_id", _require_id(self.goal_id, "goal_id"))
        object.__setattr__(self, "agent_id", _optional_id(self.agent_id, "agent_id"))
        object.__setattr__(self, "started_at", _utc(self.started_at, "started_at"))
        if self.completed_at is not None:
            completed = _utc(self.completed_at, "completed_at")
            if completed < self.started_at:
                raise InvalidAgentObservabilityContractError(
                    "completed_at cannot be before started_at"
                )
            object.__setattr__(self, "completed_at", completed)
        object.__setattr__(self, "status", _trace_status(self.status))
        if not isinstance(self.metrics, AgentTraceMetrics):
            if isinstance(self.metrics, Mapping):
                object.__setattr__(
                    self, "metrics", AgentTraceMetrics.from_mapping(self.metrics)
                )
            else:
                raise InvalidAgentObservabilityContractError(
                    "metrics must be AgentTraceMetrics"
                )
        if self.metrics.trace_id != self.trace_id:
            raise InvalidAgentObservabilityContractError(
                "metrics trace_id does not match snapshot trace_id"
            )
        child_ids = _freeze_str_tuple(self.child_trace_ids, "child_trace_ids")
        if self.trace_id in child_ids:
            raise InvalidAgentObservabilityContractError(
                "trace cannot be its own child"
            )
        object.__setattr__(self, "child_trace_ids", child_ids)
        object.__setattr__(
            self,
            "correlation_id",
            _optional_id(self.correlation_id, "correlation_id"),
        )
        object.__setattr__(self, "metadata", _freeze_mapping(self.metadata, "metadata"))

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "trace_id": self.trace_id,
            "root_span_id": self.root_span_id,
            "agent_id": self.agent_id,
            "agent_run_id": self.agent_run_id,
            "goal_id": self.goal_id,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat()
            if self.completed_at
            else None,
            "status": _enum_value(self.status),
            "metrics": self.metrics.to_dict(),
            "child_trace_ids": list(self.child_trace_ids),
            "correlation_id": self.correlation_id,
            "metadata": _thaw(self.metadata),
        }

    serialize = to_dict

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> AgentTraceSnapshot:
        data = dict(value)
        data["started_at"] = _parse_datetime(data.get("started_at"), "started_at")
        if data.get("completed_at") is not None:
            data["completed_at"] = _parse_datetime(data["completed_at"], "completed_at")
        data["metrics"] = AgentTraceMetrics.from_mapping(data["metrics"])
        return cls(**data)

    from_dict = from_mapping


@dataclass(frozen=True, slots=True)
class AgentObservabilityTraceRecord:
    """Composition root joining a canonical trace to Phase 9.26 data."""

    id: str
    trace: Any
    root_span_id: str
    snapshot: AgentTraceSnapshot
    links: tuple[AgentTraceLink, ...]
    created_at: datetime
    updated_at: datetime
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        from cmm.agent_runtime.agent_trace_contracts import (
            AgentTrace as CanonicalAgentTrace,
        )

        object.__setattr__(self, "id", _require_id(self.id, "id"))
        if isinstance(self.trace, CanonicalAgentTrace):
            canonical_trace = self.trace
        elif isinstance(self.trace, Mapping):
            canonical_trace = CanonicalAgentTrace.from_dict(dict(self.trace))
            object.__setattr__(self, "trace", canonical_trace)
        else:
            raise InvalidAgentObservabilityContractError(
                "trace must be the canonical AgentTrace"
            )
        object.__setattr__(
            self, "root_span_id", _require_id(self.root_span_id, "root_span_id")
        )
        if isinstance(self.snapshot, AgentTraceSnapshot):
            snapshot = self.snapshot
        elif isinstance(self.snapshot, Mapping):
            snapshot = AgentTraceSnapshot.from_mapping(self.snapshot)
            object.__setattr__(self, "snapshot", snapshot)
        else:
            raise InvalidAgentObservabilityContractError(
                "snapshot must be AgentTraceSnapshot"
            )
        if canonical_trace.trace_id != snapshot.trace_id:
            raise InvalidAgentObservabilityContractError(
                "canonical trace and snapshot IDs do not match"
            )
        if self.root_span_id != snapshot.root_span_id:
            raise InvalidAgentObservabilityContractError("root span IDs do not match")
        links: list[AgentTraceLink] = []
        for link in self.links:
            links.append(
                AgentTraceLink.from_mapping(link) if isinstance(link, Mapping) else link
            )
        if any(not isinstance(link, AgentTraceLink) for link in links):
            raise InvalidAgentObservabilityContractError(
                "links must contain AgentTraceLink values"
            )
        object.__setattr__(self, "links", tuple(links))
        created = _utc(self.created_at, "created_at")
        updated = _utc(self.updated_at, "updated_at")
        if updated < created:
            raise InvalidAgentObservabilityContractError(
                "updated_at cannot be before created_at"
            )
        object.__setattr__(self, "created_at", created)
        object.__setattr__(self, "updated_at", updated)
        object.__setattr__(self, "metadata", _freeze_mapping(self.metadata, "metadata"))

    @property
    def trace_id(self) -> str:
        return self.trace.trace_id

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "trace": self.trace.to_dict(),
            "root_span_id": self.root_span_id,
            "snapshot": self.snapshot.to_dict(),
            "links": [link.to_dict() for link in self.links],
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "metadata": _thaw(self.metadata),
        }

    serialize = to_dict

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> AgentObservabilityTraceRecord:
        data = dict(value)
        data["created_at"] = _parse_datetime(data.get("created_at"), "created_at")
        data["updated_at"] = _parse_datetime(data.get("updated_at"), "updated_at")
        data["snapshot"] = AgentTraceSnapshot.from_mapping(data["snapshot"])
        data["links"] = tuple(
            AgentTraceLink.from_mapping(item) for item in data.get("links", ())
        )
        return cls(**data)

    from_dict = from_mapping


@dataclass(frozen=True, slots=True)
class AgentAuditRecord:
    """Append-only structured audit record without sensitive payload content."""

    id: str
    timestamp: datetime
    action: str
    outcome: AgentAuditOutcome | str = AgentAuditOutcome.UNKNOWN
    severity: AgentAuditSeverity | str = AgentAuditSeverity.INFO
    agent_id: str | None = None
    agent_run_id: str | None = None
    goal_id: str | None = None
    operation_id: str | None = None
    decision: str | None = None
    policy_id: str | None = None
    permission_decision: str | None = None
    sensitivity: str | None = None
    resource_ids: tuple[str, ...] = ()
    actor_id: str | None = None
    reason_codes: tuple[str, ...] = ()
    trace_id: str | None = None
    span_id: str | None = None
    correlation_id: str | None = None
    causation_id: str | None = None
    payload_hash: str | None = None
    payload_reference: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", _require_id(self.id, "id"))
        object.__setattr__(self, "timestamp", _utc(self.timestamp, "timestamp"))
        object.__setattr__(self, "action", _stable_name(self.action, "action"))
        object.__setattr__(
            self, "outcome", _enum(self.outcome, AgentAuditOutcome, "outcome")
        )
        object.__setattr__(
            self, "severity", _enum(self.severity, AgentAuditSeverity, "severity")
        )
        for name in (
            "agent_id",
            "agent_run_id",
            "goal_id",
            "operation_id",
            "actor_id",
            "trace_id",
            "span_id",
            "correlation_id",
            "causation_id",
        ):
            object.__setattr__(self, name, _optional_id(getattr(self, name), name))
        for name in (
            "decision",
            "policy_id",
            "permission_decision",
            "sensitivity",
            "payload_hash",
            "payload_reference",
        ):
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(
                    self, name, _sanitize_string(_non_empty(value, name))
                )
        object.__setattr__(
            self, "resource_ids", _freeze_str_tuple(self.resource_ids, "resource_ids")
        )
        object.__setattr__(
            self, "reason_codes", _freeze_str_tuple(self.reason_codes, "reason_codes")
        )
        object.__setattr__(self, "metadata", _freeze_mapping(self.metadata, "metadata"))

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat(),
            "action": self.action,
            "outcome": _enum_value(self.outcome),
            "severity": _enum_value(self.severity),
            "agent_id": self.agent_id,
            "agent_run_id": self.agent_run_id,
            "goal_id": self.goal_id,
            "operation_id": self.operation_id,
            "decision": self.decision,
            "policy_id": self.policy_id,
            "permission_decision": self.permission_decision,
            "sensitivity": self.sensitivity,
            "resource_ids": list(self.resource_ids),
            "actor_id": self.actor_id,
            "reason_codes": list(self.reason_codes),
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "correlation_id": self.correlation_id,
            "causation_id": self.causation_id,
            "payload_hash": self.payload_hash,
            "payload_reference": self.payload_reference,
            "metadata": _thaw(self.metadata),
        }

    serialize = to_dict

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> AgentAuditRecord:
        data = dict(value)
        data["timestamp"] = _parse_datetime(data.get("timestamp"), "timestamp")
        return cls(**data)

    from_dict = from_mapping


@dataclass(frozen=True, slots=True)
class AgentModelInvocationRecord:
    """Safe metadata for one model invocation; prompts are deliberately absent."""

    id: str
    timestamp: datetime
    provider: str
    model: str
    operation_id: str
    selection_reason: str
    configuration_version: str
    privacy_mode: str
    agent_id: str | None = None
    agent_run_id: str | None = None
    goal_id: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    cached_input_tokens: int = 0
    estimated_cost: Decimal | int | str = Decimal(0)
    actual_cost: Decimal | int | str = Decimal(0)
    latency_ms: float = 0.0
    retry_count: int = 0
    fallback: bool = False
    validation_outcome: AgentAuditOutcome | str = AgentAuditOutcome.UNKNOWN
    persisted_result: bool = False
    memory_change_ids: tuple[str, ...] = ()
    trace_id: str | None = None
    correlation_id: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", _require_id(self.id, "id"))
        object.__setattr__(self, "timestamp", _utc(self.timestamp, "timestamp"))
        for name in (
            "provider",
            "model",
            "selection_reason",
            "configuration_version",
            "privacy_mode",
        ):
            object.__setattr__(self, name, _non_empty(getattr(self, name), name))
        object.__setattr__(
            self, "operation_id", _require_id(self.operation_id, "operation_id")
        )
        for name in (
            "agent_id",
            "agent_run_id",
            "goal_id",
            "trace_id",
            "correlation_id",
        ):
            object.__setattr__(self, name, _optional_id(getattr(self, name), name))
        for name in (
            "input_tokens",
            "output_tokens",
            "cached_input_tokens",
            "retry_count",
        ):
            object.__setattr__(self, name, _non_negative_int(getattr(self, name), name))
        object.__setattr__(
            self,
            "estimated_cost",
            _decimal_non_negative(self.estimated_cost, "estimated_cost"),
        )
        object.__setattr__(
            self,
            "actual_cost",
            _decimal_non_negative(self.actual_cost, "actual_cost"),
        )
        object.__setattr__(
            self, "latency_ms", _finite_non_negative(self.latency_ms, "latency_ms")
        )
        if not isinstance(self.fallback, bool) or not isinstance(
            self.persisted_result, bool
        ):
            raise InvalidAgentObservabilityContractError(
                "fallback and persisted_result must be booleans"
            )
        object.__setattr__(
            self,
            "validation_outcome",
            _enum(
                self.validation_outcome,
                AgentAuditOutcome,
                "validation_outcome",
            ),
        )
        object.__setattr__(
            self,
            "memory_change_ids",
            _freeze_str_tuple(self.memory_change_ids, "memory_change_ids"),
        )
        object.__setattr__(self, "metadata", _freeze_mapping(self.metadata, "metadata"))

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat(),
            "agent_id": self.agent_id,
            "agent_run_id": self.agent_run_id,
            "goal_id": self.goal_id,
            "operation_id": self.operation_id,
            "provider": self.provider,
            "model": self.model,
            "selection_reason": self.selection_reason,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cached_input_tokens": self.cached_input_tokens,
            "estimated_cost": str(self.estimated_cost),
            "actual_cost": str(self.actual_cost),
            "latency_ms": self.latency_ms,
            "retry_count": self.retry_count,
            "fallback": self.fallback,
            "validation_outcome": _enum_value(self.validation_outcome),
            "persisted_result": self.persisted_result,
            "memory_change_ids": list(self.memory_change_ids),
            "configuration_version": self.configuration_version,
            "privacy_mode": self.privacy_mode,
            "trace_id": self.trace_id,
            "correlation_id": self.correlation_id,
            "metadata": _thaw(self.metadata),
        }

    serialize = to_dict

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> AgentModelInvocationRecord:
        data = dict(value)
        data["timestamp"] = _parse_datetime(data.get("timestamp"), "timestamp")
        return cls(**data)

    from_dict = from_mapping


@dataclass(frozen=True, slots=True)
class AgentRunMetrics:
    """Deterministic metrics snapshot for one agent run."""

    id: str
    agent_run_id: str
    timestamp: datetime
    agent_id: str | None = None
    goal_id: str | None = None
    operations_total: int = 0
    operations_succeeded: int = 0
    operations_failed: int = 0
    retries: int = 0
    approvals: int = 0
    delegations: int = 0
    checkpoints: int = 0
    rollbacks: int = 0
    recoveries: int = 0
    active_duration_ms: float = 0.0
    waiting_duration_ms: float = 0.0
    estimated_cost: Decimal | int | str = Decimal(0)
    actual_cost: Decimal | int | str = Decimal(0)
    input_tokens: int = 0
    output_tokens: int = 0
    resource_ids: tuple[str, ...] = ()
    error_count: int = 0
    health_status: AgentHealthStatus | str = AgentHealthStatus.UNKNOWN
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", _require_id(self.id, "id"))
        object.__setattr__(
            self, "agent_run_id", _require_id(self.agent_run_id, "agent_run_id")
        )
        object.__setattr__(self, "timestamp", _utc(self.timestamp, "timestamp"))
        object.__setattr__(self, "agent_id", _optional_id(self.agent_id, "agent_id"))
        object.__setattr__(self, "goal_id", _optional_id(self.goal_id, "goal_id"))
        for name in (
            "operations_total",
            "operations_succeeded",
            "operations_failed",
            "retries",
            "approvals",
            "delegations",
            "checkpoints",
            "rollbacks",
            "recoveries",
            "input_tokens",
            "output_tokens",
            "error_count",
        ):
            object.__setattr__(self, name, _non_negative_int(getattr(self, name), name))
        if self.operations_succeeded + self.operations_failed > self.operations_total:
            raise InvalidAgentObservabilityContractError(
                "operation outcomes exceed operations_total"
            )
        for name in ("active_duration_ms", "waiting_duration_ms"):
            object.__setattr__(
                self, name, _finite_non_negative(getattr(self, name), name)
            )
        for name in ("estimated_cost", "actual_cost"):
            object.__setattr__(
                self, name, _decimal_non_negative(getattr(self, name), name)
            )
        object.__setattr__(
            self, "resource_ids", _freeze_str_tuple(self.resource_ids, "resource_ids")
        )
        object.__setattr__(
            self,
            "health_status",
            _enum(self.health_status, AgentHealthStatus, "health_status"),
        )
        object.__setattr__(self, "metadata", _freeze_mapping(self.metadata, "metadata"))

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "agent_run_id": self.agent_run_id,
            "agent_id": self.agent_id,
            "goal_id": self.goal_id,
            "timestamp": self.timestamp.isoformat(),
            "operations_total": self.operations_total,
            "operations_succeeded": self.operations_succeeded,
            "operations_failed": self.operations_failed,
            "retries": self.retries,
            "approvals": self.approvals,
            "delegations": self.delegations,
            "checkpoints": self.checkpoints,
            "rollbacks": self.rollbacks,
            "recoveries": self.recoveries,
            "active_duration_ms": self.active_duration_ms,
            "waiting_duration_ms": self.waiting_duration_ms,
            "estimated_cost": str(self.estimated_cost),
            "actual_cost": str(self.actual_cost),
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "resource_ids": list(self.resource_ids),
            "error_count": self.error_count,
            "health_status": _enum_value(self.health_status),
            "metadata": _thaw(self.metadata),
        }

    serialize = to_dict

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> AgentRunMetrics:
        data = dict(value)
        data["timestamp"] = _parse_datetime(data.get("timestamp"), "timestamp")
        return cls(**data)

    from_dict = from_mapping


@dataclass(frozen=True, slots=True)
class AgentRuntimeMetrics:
    """Global or inclusive-window Agent Runtime metrics snapshot."""

    id: str
    window_start: datetime
    window_end: datetime
    timestamp: datetime
    runs_started: int = 0
    runs_completed: int = 0
    runs_failed: int = 0
    success_rate: float = 0.0
    average_duration_ms: float = 0.0
    p50_duration_ms: float = 0.0
    p95_duration_ms: float = 0.0
    p99_duration_ms: float = 0.0
    operations: int = 0
    retries: int = 0
    approvals: int = 0
    denials: int = 0
    delegations: int = 0
    rollbacks: int = 0
    recoveries: int = 0
    kill_switch_activations: int = 0
    estimated_cost: Decimal | int | str = Decimal(0)
    actual_cost: Decimal | int | str = Decimal(0)
    input_tokens: int = 0
    output_tokens: int = 0
    active_agents: int = 0
    stalled_runs: int = 0
    health_status: AgentHealthStatus | str = AgentHealthStatus.UNKNOWN
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", _require_id(self.id, "id"))
        start = _utc(self.window_start, "window_start")
        end = _utc(self.window_end, "window_end")
        if end < start:
            raise InvalidAgentObservabilityContractError(
                "window_end cannot be before window_start"
            )
        object.__setattr__(self, "window_start", start)
        object.__setattr__(self, "window_end", end)
        object.__setattr__(self, "timestamp", _utc(self.timestamp, "timestamp"))
        for name in (
            "runs_started",
            "runs_completed",
            "runs_failed",
            "operations",
            "retries",
            "approvals",
            "denials",
            "delegations",
            "rollbacks",
            "recoveries",
            "kill_switch_activations",
            "input_tokens",
            "output_tokens",
            "active_agents",
            "stalled_runs",
        ):
            object.__setattr__(self, name, _non_negative_int(getattr(self, name), name))
        object.__setattr__(
            self, "success_rate", _ratio(self.success_rate, "success_rate")
        )
        for name in (
            "average_duration_ms",
            "p50_duration_ms",
            "p95_duration_ms",
            "p99_duration_ms",
        ):
            object.__setattr__(
                self, name, _finite_non_negative(getattr(self, name), name)
            )
        for name in ("estimated_cost", "actual_cost"):
            object.__setattr__(
                self, name, _decimal_non_negative(getattr(self, name), name)
            )
        object.__setattr__(
            self,
            "health_status",
            _enum(self.health_status, AgentHealthStatus, "health_status"),
        )
        object.__setattr__(self, "metadata", _freeze_mapping(self.metadata, "metadata"))

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "window_start": self.window_start.isoformat(),
            "window_end": self.window_end.isoformat(),
            "timestamp": self.timestamp.isoformat(),
            "runs_started": self.runs_started,
            "runs_completed": self.runs_completed,
            "runs_failed": self.runs_failed,
            "success_rate": self.success_rate,
            "average_duration_ms": self.average_duration_ms,
            "p50_duration_ms": self.p50_duration_ms,
            "p95_duration_ms": self.p95_duration_ms,
            "p99_duration_ms": self.p99_duration_ms,
            "operations": self.operations,
            "retries": self.retries,
            "approvals": self.approvals,
            "denials": self.denials,
            "delegations": self.delegations,
            "rollbacks": self.rollbacks,
            "recoveries": self.recoveries,
            "kill_switch_activations": self.kill_switch_activations,
            "estimated_cost": str(self.estimated_cost),
            "actual_cost": str(self.actual_cost),
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "active_agents": self.active_agents,
            "stalled_runs": self.stalled_runs,
            "health_status": _enum_value(self.health_status),
            "metadata": _thaw(self.metadata),
        }

    serialize = to_dict

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> AgentRuntimeMetrics:
        data = dict(value)
        for name in ("window_start", "window_end", "timestamp"):
            data[name] = _parse_datetime(data.get(name), name)
        return cls(**data)

    from_dict = from_mapping


@dataclass(frozen=True, slots=True)
class AgentHealthThresholds:
    """Configurable deterministic health thresholds."""

    stalled_after_seconds: float = 300.0
    heartbeat_grace_seconds: float = 600.0
    max_error_rate: float = 0.25
    max_retry_rate: float = 0.5
    max_denial_rate: float = 0.5
    max_recoveries: int = 3
    max_checkpoint_failures: int = 1
    max_backlog: int = 100

    def __post_init__(self) -> None:
        for name in ("stalled_after_seconds", "heartbeat_grace_seconds"):
            object.__setattr__(
                self, name, _finite_non_negative(getattr(self, name), name)
            )
        for name in ("max_error_rate", "max_retry_rate", "max_denial_rate"):
            object.__setattr__(self, name, _ratio(getattr(self, name), name))
        for name in ("max_recoveries", "max_checkpoint_failures", "max_backlog"):
            object.__setattr__(self, name, _non_negative_int(getattr(self, name), name))

    def to_dict(self) -> dict[str, Any]:
        return {
            "stalled_after_seconds": self.stalled_after_seconds,
            "heartbeat_grace_seconds": self.heartbeat_grace_seconds,
            "max_error_rate": self.max_error_rate,
            "max_retry_rate": self.max_retry_rate,
            "max_denial_rate": self.max_denial_rate,
            "max_recoveries": self.max_recoveries,
            "max_checkpoint_failures": self.max_checkpoint_failures,
            "max_backlog": self.max_backlog,
        }

    serialize = to_dict

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> AgentHealthThresholds:
        return cls(**dict(value))

    from_dict = from_mapping


@dataclass(frozen=True, slots=True)
class AgentHealthReport:
    """Health evaluation result for a run, agent, or runtime scope."""

    id: str
    scope: str
    status: AgentHealthStatus | str
    findings: tuple[str, ...]
    stalled_run_ids: tuple[str, ...]
    failed_run_ids: tuple[str, ...]
    queue_backlog: int | None
    error_rate: float
    retry_rate: float
    checkpoint_failures: int
    recovery_failures: int
    timestamp: datetime
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", _require_id(self.id, "id"))
        object.__setattr__(self, "scope", _non_empty(self.scope, "scope"))
        object.__setattr__(
            self, "status", _enum(self.status, AgentHealthStatus, "status")
        )
        for name in ("findings", "stalled_run_ids", "failed_run_ids"):
            object.__setattr__(self, name, _freeze_str_tuple(getattr(self, name), name))
        if self.queue_backlog is not None:
            object.__setattr__(
                self,
                "queue_backlog",
                _non_negative_int(self.queue_backlog, "queue_backlog"),
            )
        object.__setattr__(self, "error_rate", _ratio(self.error_rate, "error_rate"))
        object.__setattr__(self, "retry_rate", _ratio(self.retry_rate, "retry_rate"))
        object.__setattr__(
            self,
            "checkpoint_failures",
            _non_negative_int(self.checkpoint_failures, "checkpoint_failures"),
        )
        object.__setattr__(
            self,
            "recovery_failures",
            _non_negative_int(self.recovery_failures, "recovery_failures"),
        )
        object.__setattr__(self, "timestamp", _utc(self.timestamp, "timestamp"))
        object.__setattr__(self, "metadata", _freeze_mapping(self.metadata, "metadata"))

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "scope": self.scope,
            "status": _enum_value(self.status),
            "findings": list(self.findings),
            "stalled_run_ids": list(self.stalled_run_ids),
            "failed_run_ids": list(self.failed_run_ids),
            "queue_backlog": self.queue_backlog,
            "error_rate": self.error_rate,
            "retry_rate": self.retry_rate,
            "checkpoint_failures": self.checkpoint_failures,
            "recovery_failures": self.recovery_failures,
            "timestamp": self.timestamp.isoformat(),
            "metadata": _thaw(self.metadata),
        }

    serialize = to_dict

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> AgentHealthReport:
        data = dict(value)
        data["timestamp"] = _parse_datetime(data.get("timestamp"), "timestamp")
        return cls(**data)

    from_dict = from_mapping


__all__ = [
    "REDACTED",
    "AgentAuditRecord",
    "AgentHealthReport",
    "AgentHealthThresholds",
    "AgentMetricPoint",
    "AgentModelInvocationRecord",
    "AgentObservabilityTraceRecord",
    "AgentRunMetrics",
    "AgentRuntimeMetrics",
    "AgentSpan",
    "AgentTelemetryRecord",
    "AgentTraceLink",
    "AgentTraceMetrics",
    "AgentTraceSnapshot",
    "sanitize_agent_observability_data",
]
