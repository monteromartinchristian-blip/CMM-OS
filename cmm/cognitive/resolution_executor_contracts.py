"""Phase 8.12 – Contradiction Resolution Executor Contracts & Enums.

Defines immutable, typed contracts for contradiction resolution execution results and audit records.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from types import MappingProxyType
from typing import Any

from cmm.cognitive.contracts import utc_now
from cmm.cognitive.errors import InvalidResolutionExecutionError


def _require_aware(value: datetime | None, field_name: str) -> None:
    if value is not None and value.tzinfo is None:
        raise InvalidResolutionExecutionError(
            f"{field_name} must be timezone-aware when provided"
        )


class ExecutionStatus(str, Enum):
    """Enumeration of resolution execution statuses."""

    PENDING = "pending"
    VALIDATING = "validating"
    APPLYING = "applying"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


@dataclass(frozen=True, slots=True)
class ResolutionExecutionResult:
    """Immutable result of executing a contradiction resolution proposal."""

    execution_id: str
    proposal_id: str
    status: ExecutionStatus
    applied: bool
    created_item_ids: tuple[str, ...] = ()
    updated_item_ids: tuple[str, ...] = ()
    superseded_item_ids: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()
    started_at: datetime = field(default_factory=utc_now)
    finished_at: datetime | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.execution_id, str) or not self.execution_id.strip():
            raise InvalidResolutionExecutionError(
                "execution_id must be a non-empty string"
            )
        object.__setattr__(self, "execution_id", self.execution_id.strip())

        if not isinstance(self.proposal_id, str) or not self.proposal_id.strip():
            raise InvalidResolutionExecutionError(
                "proposal_id must be a non-empty string"
            )
        object.__setattr__(self, "proposal_id", self.proposal_id.strip())

        stat_val = self.status
        if isinstance(stat_val, str):
            try:
                stat_val = ExecutionStatus(stat_val.lower())
            except ValueError:
                try:
                    stat_val = ExecutionStatus[stat_val.upper()]
                except KeyError as exc:
                    raise InvalidResolutionExecutionError(
                        f"Unknown ExecutionStatus: {stat_val}"
                    ) from exc
        elif not isinstance(stat_val, ExecutionStatus):
            raise InvalidResolutionExecutionError(f"Invalid status: {stat_val}")
        object.__setattr__(self, "status", stat_val)

        if not isinstance(self.applied, bool):
            raise InvalidResolutionExecutionError("applied must be a boolean")

        object.__setattr__(
            self, "created_item_ids", tuple(str(x) for x in self.created_item_ids or ())
        )
        object.__setattr__(
            self, "updated_item_ids", tuple(str(x) for x in self.updated_item_ids or ())
        )
        object.__setattr__(
            self,
            "superseded_item_ids",
            tuple(str(x) for x in self.superseded_item_ids or ()),
        )
        object.__setattr__(self, "warnings", tuple(str(w) for w in self.warnings or ()))
        object.__setattr__(self, "errors", tuple(str(e) for e in self.errors or ()))

        if not isinstance(self.started_at, datetime):
            raise InvalidResolutionExecutionError("started_at must be a datetime")
        _require_aware(self.started_at, "started_at")

        if self.finished_at is not None:
            if not isinstance(self.finished_at, datetime):
                raise InvalidResolutionExecutionError("finished_at must be a datetime")
            _require_aware(self.finished_at, "finished_at")

        object.__setattr__(
            self, "metadata", MappingProxyType(dict(self.metadata or {}))
        )

    def serialize(self) -> dict[str, Any]:
        """Canonical JSON-safe serialization."""
        return {
            "execution_id": self.execution_id,
            "proposal_id": self.proposal_id,
            "status": self.status.value,
            "applied": self.applied,
            "created_item_ids": list(self.created_item_ids),
            "updated_item_ids": list(self.updated_item_ids),
            "superseded_item_ids": list(self.superseded_item_ids),
            "warnings": list(self.warnings),
            "errors": list(self.errors),
            "started_at": self.started_at.isoformat(),
            "finished_at": (
                self.finished_at.isoformat() if self.finished_at is not None else None
            ),
            "metadata": dict(self.metadata),
        }

    def to_dict(self) -> dict[str, Any]:
        """Compatibility alias for :meth:`serialize`."""
        return self.serialize()

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> ResolutionExecutionResult:
        """Canonical deserialization from mapping."""
        if not isinstance(payload, Mapping):
            raise InvalidResolutionExecutionError("payload must be a mapping")

        exec_id = payload.get("execution_id")
        if not isinstance(exec_id, str):
            raise InvalidResolutionExecutionError("execution_id must be a string")

        prop_id = payload.get("proposal_id")
        if not isinstance(prop_id, str):
            raise InvalidResolutionExecutionError("proposal_id must be a string")

        stat_raw = payload.get("status")
        if stat_raw is None:
            raise InvalidResolutionExecutionError("status is required")

        applied_raw = payload.get("applied")
        if applied_raw is None:
            raise InvalidResolutionExecutionError("applied is required")

        started_at_raw = payload.get("started_at")
        if isinstance(started_at_raw, datetime):
            started_at = started_at_raw
        elif isinstance(started_at_raw, str):
            try:
                started_at = datetime.fromisoformat(started_at_raw)
            except ValueError as exc:
                raise InvalidResolutionExecutionError(
                    f"Invalid ISO format for started_at: {started_at_raw}"
                ) from exc
        else:
            raise InvalidResolutionExecutionError("started_at is required")

        finished_at_raw = payload.get("finished_at")
        if isinstance(finished_at_raw, datetime):
            finished_at = finished_at_raw
        elif isinstance(finished_at_raw, str):
            try:
                finished_at = datetime.fromisoformat(finished_at_raw)
            except ValueError as exc:
                raise InvalidResolutionExecutionError(
                    f"Invalid ISO format for finished_at: {finished_at_raw}"
                ) from exc
        else:
            finished_at = None

        return cls(
            execution_id=exec_id,
            proposal_id=prop_id,
            status=stat_raw,
            applied=bool(applied_raw),
            created_item_ids=tuple(payload.get("created_item_ids") or ()),
            updated_item_ids=tuple(payload.get("updated_item_ids") or ()),
            superseded_item_ids=tuple(payload.get("superseded_item_ids") or ()),
            warnings=tuple(payload.get("warnings") or ()),
            errors=tuple(payload.get("errors") or ()),
            started_at=started_at,
            finished_at=finished_at,
            metadata=dict(payload.get("metadata") or {}),
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ResolutionExecutionResult:
        """Compatibility alias for :meth:`from_mapping`."""
        return cls.from_mapping(data)


@dataclass(frozen=True, slots=True)
class ResolutionAuditRecord:
    """Immutable audit record for contradiction resolution execution."""

    audit_id: str
    execution_id: str
    proposal_id: str
    actor_id: str | None
    action: str
    timestamp: datetime = field(default_factory=utc_now)
    details: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.audit_id, str) or not self.audit_id.strip():
            raise InvalidResolutionExecutionError("audit_id must be a non-empty string")
        object.__setattr__(self, "audit_id", self.audit_id.strip())

        if not isinstance(self.execution_id, str) or not self.execution_id.strip():
            raise InvalidResolutionExecutionError(
                "execution_id must be a non-empty string"
            )
        object.__setattr__(self, "execution_id", self.execution_id.strip())

        if not isinstance(self.proposal_id, str) or not self.proposal_id.strip():
            raise InvalidResolutionExecutionError(
                "proposal_id must be a non-empty string"
            )
        object.__setattr__(self, "proposal_id", self.proposal_id.strip())

        if self.actor_id is not None:
            if not isinstance(self.actor_id, str):
                raise InvalidResolutionExecutionError(
                    "actor_id must be a string or None"
                )
            actor_str = self.actor_id.strip()
            object.__setattr__(self, "actor_id", actor_str if actor_str else None)

        if not isinstance(self.action, str) or not self.action.strip():
            raise InvalidResolutionExecutionError("action must be a non-empty string")
        object.__setattr__(self, "action", self.action.strip())

        if not isinstance(self.timestamp, datetime):
            raise InvalidResolutionExecutionError("timestamp must be a datetime")
        _require_aware(self.timestamp, "timestamp")

        object.__setattr__(self, "details", MappingProxyType(dict(self.details or {})))

    def serialize(self) -> dict[str, Any]:
        """Canonical JSON-safe serialization."""
        return {
            "audit_id": self.audit_id,
            "execution_id": self.execution_id,
            "proposal_id": self.proposal_id,
            "actor_id": self.actor_id,
            "action": self.action,
            "timestamp": self.timestamp.isoformat(),
            "details": dict(self.details),
        }

    def to_dict(self) -> dict[str, Any]:
        """Compatibility alias for :meth:`serialize`."""
        return self.serialize()

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> ResolutionAuditRecord:
        """Canonical deserialization from mapping."""
        if not isinstance(payload, Mapping):
            raise InvalidResolutionExecutionError("payload must be a mapping")

        audit_id = payload.get("audit_id")
        if not isinstance(audit_id, str):
            raise InvalidResolutionExecutionError("audit_id must be a string")

        exec_id = payload.get("execution_id")
        if not isinstance(exec_id, str):
            raise InvalidResolutionExecutionError("execution_id must be a string")

        prop_id = payload.get("proposal_id")
        if not isinstance(prop_id, str):
            raise InvalidResolutionExecutionError("proposal_id must be a string")

        action = payload.get("action")
        if not isinstance(action, str):
            raise InvalidResolutionExecutionError("action must be a string")

        ts_raw = payload.get("timestamp")
        if isinstance(ts_raw, datetime):
            ts = ts_raw
        elif isinstance(ts_raw, str):
            try:
                ts = datetime.fromisoformat(ts_raw)
            except ValueError as exc:
                raise InvalidResolutionExecutionError(
                    f"Invalid ISO format for timestamp: {ts_raw}"
                ) from exc
        else:
            raise InvalidResolutionExecutionError("timestamp is required")

        return cls(
            audit_id=audit_id,
            execution_id=exec_id,
            proposal_id=prop_id,
            actor_id=payload.get("actor_id"),
            action=action,
            timestamp=ts,
            details=dict(payload.get("details") or {}),
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ResolutionAuditRecord:
        """Compatibility alias for :meth:`from_mapping`."""
        return cls.from_mapping(data)
