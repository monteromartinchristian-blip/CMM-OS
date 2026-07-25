"""Phase 9.4 – Observation Engine Contracts.

Defines the core immutable data models, snapshots, requests, changes, and queries
for system state observation in the Autonomous Agent Runtime.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from cmm.agent_runtime.enums import (
    ObservationKind,
    ObservationSignificance,
    ObservationStatus,
    ObservedChangeKind,
    ObserverStatus,
)
from cmm.agent_runtime.errors import InvalidObservationContractError


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _require_aware_datetime(
    value: datetime | None,
    field_name: str,
) -> None:
    if value is not None and value.tzinfo is None:
        raise InvalidObservationContractError(f"{field_name} must be timezone-aware")


def _parse_datetime(value: str | datetime | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


@dataclass(frozen=True, slots=True)
class ObservationRequest:
    """Request specification for invoking observation across observers."""

    id: str = field(
        default_factory=lambda: f"observation-request:{uuid.uuid4().hex[:12]}"
    )
    goal_id: str | None = None
    agent_run_id: str | None = None
    observer_names: tuple[str, ...] = ()
    scope: tuple[str, ...] = ()
    changed_since: datetime | None = None
    maximum_items: int = 1000
    timeout_seconds: float = 60.0
    permissions: tuple[str, ...] = ()
    sensitivity_levels: tuple[str, ...] = ()
    required_observers: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=_utc_now)

    def __post_init__(self) -> None:
        if not self.id.strip():
            raise InvalidObservationContractError(
                "ObservationRequest id must not be blank"
            )

        if self.maximum_items <= 0:
            raise InvalidObservationContractError(
                "maximum_items must be positive (> 0)"
            )

        if self.timeout_seconds <= 0.0:
            raise InvalidObservationContractError(
                "timeout_seconds must be positive (> 0)"
            )

        _require_aware_datetime(self.changed_since, "ObservationRequest changed_since")
        _require_aware_datetime(self.created_at, "ObservationRequest created_at")

        object.__setattr__(self, "observer_names", tuple(self.observer_names))
        object.__setattr__(self, "scope", tuple(self.scope))
        object.__setattr__(self, "permissions", tuple(self.permissions))
        object.__setattr__(self, "sensitivity_levels", tuple(self.sensitivity_levels))
        object.__setattr__(self, "required_observers", tuple(self.required_observers))
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "goal_id": self.goal_id,
            "agent_run_id": self.agent_run_id,
            "observer_names": list(self.observer_names),
            "scope": list(self.scope),
            "changed_since": self.changed_since.isoformat()
            if self.changed_since
            else None,
            "maximum_items": self.maximum_items,
            "timeout_seconds": self.timeout_seconds,
            "permissions": list(self.permissions),
            "sensitivity_levels": list(self.sensitivity_levels),
            "required_observers": list(self.required_observers),
            "metadata": dict(self.metadata),
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ObservationRequest:
        return cls(
            id=data.get("id") or f"observation-request:{uuid.uuid4().hex[:12]}",
            goal_id=data.get("goal_id"),
            agent_run_id=data.get("agent_run_id"),
            observer_names=tuple(data.get("observer_names", ())),
            scope=tuple(data.get("scope", ())),
            changed_since=_parse_datetime(data.get("changed_since")),
            maximum_items=data.get("maximum_items", 1000),
            timeout_seconds=data.get("timeout_seconds", 60.0),
            permissions=tuple(data.get("permissions", ())),
            sensitivity_levels=tuple(data.get("sensitivity_levels", ())),
            required_observers=tuple(data.get("required_observers", ())),
            metadata=dict(data.get("metadata", {})),
            created_at=_parse_datetime(data.get("created_at")) or _utc_now(),
        )


@dataclass(frozen=True, slots=True)
class Observation:
    """Structured, immutable representation of an observed state fact."""

    id: str = field(default_factory=lambda: f"observation:{uuid.uuid4().hex[:12]}")
    observer: str = ""
    kind: ObservationKind | str = ObservationKind.STATE
    subject_id: str = ""
    statement: str = ""
    value: Any = field(default_factory=dict)
    source_ids: tuple[str, ...] = ()
    observed_at: datetime = field(default_factory=_utc_now)
    valid_at: datetime = field(default_factory=_utc_now)
    confidence: float = 1.0
    sensitivity: str = "internal"
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.id.strip():
            raise InvalidObservationContractError("Observation id must not be blank")
        if not self.observer.strip():
            raise InvalidObservationContractError(
                "Observation observer must not be blank"
            )
        if not self.subject_id.strip():
            raise InvalidObservationContractError(
                "Observation subject_id must not be blank"
            )

        if not (0.0 <= self.confidence <= 1.0):
            raise InvalidObservationContractError(
                f"confidence must be between 0.0 and 1.0, got {self.confidence}"
            )

        _require_aware_datetime(self.observed_at, "Observation observed_at")
        _require_aware_datetime(self.valid_at, "Observation valid_at")

        # Parse kind if string
        if isinstance(self.kind, str):
            try:
                object.__setattr__(self, "kind", ObservationKind(self.kind))
            except ValueError:
                # Keep custom or validated kind string if valid
                pass

        object.__setattr__(self, "source_ids", tuple(self.source_ids))
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "observer": self.observer,
            "kind": self.kind.value
            if isinstance(self.kind, ObservationKind)
            else str(self.kind),
            "subject_id": self.subject_id,
            "statement": self.statement,
            "value": self.value,
            "source_ids": list(self.source_ids),
            "observed_at": self.observed_at.isoformat(),
            "valid_at": self.valid_at.isoformat(),
            "confidence": self.confidence,
            "sensitivity": self.sensitivity,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Observation:
        kind_raw = data.get("kind", ObservationKind.STATE.value)
        try:
            kind_val: ObservationKind | str = ObservationKind(kind_raw)
        except ValueError:
            kind_val = str(kind_raw)

        return cls(
            id=data.get("id") or f"observation:{uuid.uuid4().hex[:12]}",
            observer=data.get("observer", ""),
            kind=kind_val,
            subject_id=data.get("subject_id", ""),
            statement=data.get("statement", ""),
            value=data.get("value", {}),
            source_ids=tuple(data.get("source_ids", ())),
            observed_at=_parse_datetime(data.get("observed_at")) or _utc_now(),
            valid_at=_parse_datetime(data.get("valid_at")) or _utc_now(),
            confidence=float(data.get("confidence", 1.0)),
            sensitivity=data.get("sensitivity", "internal"),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass(frozen=True, slots=True)
class ObservedChange:
    """Structured representation of a detected state change between observations."""

    id: str = field(default_factory=lambda: f"observed-change:{uuid.uuid4().hex[:12]}")
    subject_id: str = ""
    kind: ObservedChangeKind | str = ObservedChangeKind.MODIFIED
    previous_value: Any = None
    current_value: Any = None
    detected_at: datetime = field(default_factory=_utc_now)
    significance: ObservationSignificance | str = ObservationSignificance.MEDIUM
    related_goal_ids: tuple[str, ...] = ()
    source_observer: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.id.strip():
            raise InvalidObservationContractError("ObservedChange id must not be blank")
        if not self.subject_id.strip():
            raise InvalidObservationContractError(
                "ObservedChange subject_id must not be blank"
            )

        _require_aware_datetime(self.detected_at, "ObservedChange detected_at")

        if isinstance(self.kind, str):
            try:
                object.__setattr__(self, "kind", ObservedChangeKind(self.kind))
            except ValueError:
                pass

        if isinstance(self.significance, str):
            try:
                object.__setattr__(
                    self, "significance", ObservationSignificance(self.significance)
                )
            except ValueError:
                pass

        object.__setattr__(self, "related_goal_ids", tuple(self.related_goal_ids))
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "subject_id": self.subject_id,
            "kind": self.kind.value
            if isinstance(self.kind, ObservedChangeKind)
            else str(self.kind),
            "previous_value": self.previous_value,
            "current_value": self.current_value,
            "detected_at": self.detected_at.isoformat(),
            "significance": (
                self.significance.value
                if isinstance(self.significance, ObservationSignificance)
                else str(self.significance)
            ),
            "related_goal_ids": list(self.related_goal_ids),
            "source_observer": self.source_observer,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ObservedChange:
        kind_raw = data.get("kind", ObservedChangeKind.MODIFIED.value)
        try:
            kind_val: ObservedChangeKind | str = ObservedChangeKind(kind_raw)
        except ValueError:
            kind_val = str(kind_raw)

        sig_raw = data.get("significance", ObservationSignificance.MEDIUM.value)
        try:
            sig_val: ObservationSignificance | str = ObservationSignificance(sig_raw)
        except ValueError:
            sig_val = str(sig_raw)

        return cls(
            id=data.get("id") or f"observed-change:{uuid.uuid4().hex[:12]}",
            subject_id=data.get("subject_id", ""),
            kind=kind_val,
            previous_value=data.get("previous_value"),
            current_value=data.get("current_value"),
            detected_at=_parse_datetime(data.get("detected_at")) or _utc_now(),
            significance=sig_val,
            related_goal_ids=tuple(data.get("related_goal_ids", ())),
            source_observer=data.get("source_observer", ""),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass(frozen=True, slots=True)
class ObservationError:
    """Structured error captured during an observation run."""

    id: str = field(
        default_factory=lambda: f"observation-error:{uuid.uuid4().hex[:12]}"
    )
    observer_name: str = ""
    error_type: str = "ObserverExecutionError"
    message: str = ""
    occurred_at: datetime = field(default_factory=_utc_now)
    is_fatal: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_aware_datetime(self.occurred_at, "ObservationError occurred_at")
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "observer_name": self.observer_name,
            "error_type": self.error_type,
            "message": self.message,
            "occurred_at": self.occurred_at.isoformat(),
            "is_fatal": self.is_fatal,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ObservationError:
        return cls(
            id=data.get("id") or f"observation-error:{uuid.uuid4().hex[:12]}",
            observer_name=data.get("observer_name", ""),
            error_type=data.get("error_type", "ObserverExecutionError"),
            message=data.get("message", ""),
            occurred_at=_parse_datetime(data.get("occurred_at")) or _utc_now(),
            is_fatal=bool(data.get("is_fatal", False)),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass(frozen=True, slots=True)
class ObservationSourceVersion:
    """Provenance tracking for data sources queried by an observer."""

    source_name: str
    version_identifier: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.source_name.strip():
            raise InvalidObservationContractError(
                "ObservationSourceVersion source_name must not be blank"
            )
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_name": self.source_name,
            "version_identifier": self.version_identifier,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ObservationSourceVersion:
        return cls(
            source_name=data.get("source_name", ""),
            version_identifier=data.get("version_identifier", ""),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass(frozen=True, slots=True)
class ObservationResult:
    """Individual execution result returned by a single Observer."""

    observer_name: str
    observer_version: str
    status: ObserverStatus | str = ObserverStatus.COMPLETED
    observations: tuple[Observation, ...] = ()
    changes: tuple[ObservedChange, ...] = ()
    warnings: tuple[str, ...] = ()
    errors: tuple[ObservationError, ...] = ()
    source_version: ObservationSourceVersion | None = None
    duration_ms: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.observer_name.strip():
            raise InvalidObservationContractError(
                "ObserverResult observer_name must not be blank"
            )

        if isinstance(self.status, str):
            try:
                object.__setattr__(self, "status", ObserverStatus(self.status))
            except ValueError:
                pass

        object.__setattr__(self, "observations", tuple(self.observations))
        object.__setattr__(self, "changes", tuple(self.changes))
        object.__setattr__(self, "warnings", tuple(self.warnings))
        object.__setattr__(self, "errors", tuple(self.errors))
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "observer_name": self.observer_name,
            "observer_version": self.observer_version,
            "status": self.status.value
            if isinstance(self.status, ObserverStatus)
            else str(self.status),
            "observations": [o.to_dict() for o in self.observations],
            "changes": [c.to_dict() for c in self.changes],
            "warnings": list(self.warnings),
            "errors": [e.to_dict() for e in self.errors],
            "source_version": self.source_version.to_dict()
            if self.source_version
            else None,
            "duration_ms": self.duration_ms,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ObservationResult:
        status_raw = data.get("status", ObserverStatus.COMPLETED.value)
        try:
            status_val: ObserverStatus | str = ObserverStatus(status_raw)
        except ValueError:
            status_val = str(status_raw)

        sv = data.get("source_version")
        source_version = ObservationSourceVersion.from_dict(sv) if sv else None

        return cls(
            observer_name=data.get("observer_name", ""),
            observer_version=data.get("observer_version", "1.0.0"),
            status=status_val,
            observations=tuple(
                Observation.from_dict(o) for o in data.get("observations", [])
            ),
            changes=tuple(ObservedChange.from_dict(c) for c in data.get("changes", [])),
            warnings=tuple(data.get("warnings", [])),
            errors=tuple(ObservationError.from_dict(e) for e in data.get("errors", [])),
            source_version=source_version,
            duration_ms=float(data.get("duration_ms", 0.0)),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass(frozen=True, slots=True)
class ObservationSnapshot:
    """Complete aggregated snapshot of system state observations produced by the ObservationEngine."""

    id: str = field(
        default_factory=lambda: f"observation-snapshot:{uuid.uuid4().hex[:12]}"
    )
    goal_id: str | None = None
    agent_run_id: str | None = None
    observations: tuple[Observation, ...] = ()
    changes: tuple[ObservedChange, ...] = ()
    warnings: tuple[str, ...] = ()
    errors: tuple[ObservationError, ...] = ()
    observer_results: tuple[ObservationResult, ...] = ()
    source_versions: dict[str, ObservationSourceVersion] = field(default_factory=dict)
    started_at: datetime = field(default_factory=_utc_now)
    completed_at: datetime = field(default_factory=_utc_now)
    duration_ms: float = 0.0
    status: ObservationStatus | str = ObservationStatus.COMPLETED
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.id.strip():
            raise InvalidObservationContractError(
                "ObservationSnapshot id must not be blank"
            )

        _require_aware_datetime(self.started_at, "ObservationSnapshot started_at")
        _require_aware_datetime(self.completed_at, "ObservationSnapshot completed_at")

        if self.completed_at < self.started_at:
            raise InvalidObservationContractError(
                "completed_at must not precede started_at"
            )

        if self.duration_ms < 0.0:
            raise InvalidObservationContractError("duration_ms must not be negative")

        if isinstance(self.status, str):
            try:
                object.__setattr__(self, "status", ObservationStatus(self.status))
            except ValueError:
                pass

        object.__setattr__(self, "observations", tuple(self.observations))
        object.__setattr__(self, "changes", tuple(self.changes))
        object.__setattr__(self, "warnings", tuple(self.warnings))
        object.__setattr__(self, "errors", tuple(self.errors))
        object.__setattr__(self, "observer_results", tuple(self.observer_results))
        object.__setattr__(self, "source_versions", dict(self.source_versions))
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "goal_id": self.goal_id,
            "agent_run_id": self.agent_run_id,
            "observations": [o.to_dict() for o in self.observations],
            "changes": [c.to_dict() for c in self.changes],
            "warnings": list(self.warnings),
            "errors": [e.to_dict() for e in self.errors],
            "observer_results": [r.to_dict() for r in self.observer_results],
            "source_versions": {
                k: v.to_dict() for k, v in self.source_versions.items()
            },
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat(),
            "duration_ms": self.duration_ms,
            "status": self.status.value
            if isinstance(self.status, ObservationStatus)
            else str(self.status),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ObservationSnapshot:
        status_raw = data.get("status", ObservationStatus.COMPLETED.value)
        try:
            status_val: ObservationStatus | str = ObservationStatus(status_raw)
        except ValueError:
            status_val = str(status_raw)

        sv_dict = {}
        for k, v in data.get("source_versions", {}).items():
            sv_dict[k] = ObservationSourceVersion.from_dict(v)

        return cls(
            id=data.get("id") or f"observation-snapshot:{uuid.uuid4().hex[:12]}",
            goal_id=data.get("goal_id"),
            agent_run_id=data.get("agent_run_id"),
            observations=tuple(
                Observation.from_dict(o) for o in data.get("observations", [])
            ),
            changes=tuple(ObservedChange.from_dict(c) for c in data.get("changes", [])),
            warnings=tuple(data.get("warnings", [])),
            errors=tuple(ObservationError.from_dict(e) for e in data.get("errors", [])),
            observer_results=tuple(
                ObservationResult.from_dict(r) for r in data.get("observer_results", [])
            ),
            source_versions=sv_dict,
            started_at=_parse_datetime(data.get("started_at")) or _utc_now(),
            completed_at=_parse_datetime(data.get("completed_at")) or _utc_now(),
            duration_ms=float(data.get("duration_ms", 0.0)),
            status=status_val,
            metadata=dict(data.get("metadata", {})),
        )


@dataclass(frozen=True, slots=True)
class ObservationQuery:
    """Query model to filter observations from snapshots."""

    observer_names: tuple[str, ...] = ()
    kinds: tuple[ObservationKind | str, ...] = ()
    subject_ids: tuple[str, ...] = ()
    min_confidence: float = 0.0
    sensitivity_levels: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not (0.0 <= self.min_confidence <= 1.0):
            raise InvalidObservationContractError(
                f"min_confidence must be between 0.0 and 1.0, got {self.min_confidence}"
            )
        object.__setattr__(self, "observer_names", tuple(self.observer_names))
        object.__setattr__(self, "kinds", tuple(self.kinds))
        object.__setattr__(self, "subject_ids", tuple(self.subject_ids))
        object.__setattr__(self, "sensitivity_levels", tuple(self.sensitivity_levels))
        object.__setattr__(self, "metadata", dict(self.metadata))
