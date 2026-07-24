"""Structured data models for Phase 7.11 — Observability and Persistence.

Contracts
---------
:class:`ValidationLogEntry`
    A single structured log event tied to a validation execution.

:class:`ValidationExecutionRecord`
    An immutable, versionable, serializable snapshot of one complete
    (or in-progress) validation run.  Wraps the existing
    ``ValidationResult``, ``CommitGateResult``, and
    :class:`ValidationMetrics` into a single archivable document.

All models are:

* ``frozen=True`` — immutable after construction.
* Serializable via ``serialize()`` → ``dict``.
* Round-trip safe via ``from_mapping()``.
* ``schema_version = 1`` (7.11 initial version).

Schema version contract
-----------------------
* Only version ``1`` is understood by this code.
* Future versions raise :class:`UnsupportedValidationSchemaError`.
* No silent schema migration happens here; that belongs to a future
  migration layer (out of scope for 7.11).
"""

from __future__ import annotations

import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from ..enums import ValidationStatus
from .exceptions import (
    UnsupportedValidationSchemaError,
    ValidationPersistenceError,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CURRENT_SCHEMA_VERSION: int = 1

_FINAL_STATUSES: frozenset[str] = frozenset(
    {
        ValidationStatus.PASSED.value,
        ValidationStatus.FAILED.value,
        ValidationStatus.WARNING.value,
        ValidationStatus.ERROR.value,
        ValidationStatus.CANCELLED.value,
        ValidationStatus.TIMED_OUT.value,
    }
)

_VALID_LOG_LEVELS: frozenset[str] = frozenset(
    {"debug", "info", "warning", "error", "critical"}
)

# Stable event identifiers — do NOT use free-form text as event IDs.
LOG_EVENTS: frozenset[str] = frozenset(
    {
        "validation.started",
        "validation.policy.resolved",
        "validation.step.started",
        "validation.step.completed",
        "validation.step.failed",
        "validation.step.timed_out",
        "validation.cancelled",
        "validation.completed",
        "validation.failed",
        "validation.persistence.failed",
        "validation.gate.evaluated",
        "validation.gate.approved",
        "validation.gate.rejected",
        "validation.commit.created",
    }
)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def new_validation_id() -> str:
    """Return a new, stable, file-safe validation execution ID."""
    return f"validation-{uuid.uuid4()}"


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# ValidationLogEntry
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ValidationLogEntry:
    """A single structured log line tied to a validation execution.

    Parameters
    ----------
    id:
        Unique log entry ID (``log-<uuid>``).
    validation_id:
        Parent execution ID.
    timestamp:
        UTC timestamp of the event.
    level:
        One of ``debug``, ``info``, ``warning``, ``error``, ``critical``.
    component:
        Module or subsystem that emitted the log (e.g.
        ``validation.pipeline``).
    event:
        Stable event identifier from :data:`LOG_EVENTS`.
    message:
        Human-readable description.
    step_name:
        Optional — name of the step being logged.
    duration_ms:
        Optional — milliseconds the step or operation took.
    status:
        Optional — status string.
    correlation_id:
        ID used for cross-entry correlation (typically the validation_id).
    metadata:
        Arbitrary safe key/value pairs (must not contain secrets).
    """

    id: str
    validation_id: str
    timestamp: datetime
    level: str
    component: str
    event: str
    message: str
    step_name: str | None = None
    duration_ms: int | None = None
    status: str | None = None
    correlation_id: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("ValidationLogEntry.id must not be empty")
        if not self.validation_id:
            raise ValueError("ValidationLogEntry.validation_id must not be empty")
        if not isinstance(self.timestamp, datetime):
            raise TypeError("ValidationLogEntry.timestamp must be a datetime")
        if self.level not in _VALID_LOG_LEVELS:
            raise ValueError(
                f"ValidationLogEntry.level must be one of {sorted(_VALID_LOG_LEVELS)}; "
                f"got {self.level!r}"
            )
        if not self.component:
            raise ValueError("ValidationLogEntry.component must not be empty")
        if not self.event:
            raise ValueError("ValidationLogEntry.event must not be empty")
        if not self.message:
            raise ValueError("ValidationLogEntry.message must not be empty")
        if self.duration_ms is not None and self.duration_ms < 0:
            raise ValueError("ValidationLogEntry.duration_ms must be non-negative")
        # Ensure timezone-aware timestamp
        if self.timestamp.tzinfo is None:
            object.__setattr__(
                self, "timestamp", self.timestamp.replace(tzinfo=timezone.utc)
            )
        # Defensive copy
        object.__setattr__(self, "metadata", dict(self.metadata or {}))

    # ------------------------------------------------------------------

    def serialize(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "validation_id": self.validation_id,
            "timestamp": self.timestamp.isoformat(),
            "level": self.level,
            "component": self.component,
            "event": self.event,
            "message": self.message,
            "step_name": self.step_name,
            "duration_ms": self.duration_ms,
            "status": self.status,
            "correlation_id": self.correlation_id,
            "metadata": dict(self.metadata or {}),
        }

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> ValidationLogEntry:
        ts_raw = payload.get("timestamp")
        if isinstance(ts_raw, str):
            ts = datetime.fromisoformat(ts_raw)
        elif isinstance(ts_raw, datetime):
            ts = ts_raw
        else:
            ts = _now_utc()
        return cls(
            id=str(payload["id"]),
            validation_id=str(payload["validation_id"]),
            timestamp=ts,
            level=str(payload["level"]),
            component=str(payload["component"]),
            event=str(payload["event"]),
            message=str(payload["message"]),
            step_name=payload.get("step_name"),
            duration_ms=payload.get("duration_ms"),
            status=payload.get("status"),
            correlation_id=payload.get("correlation_id"),
            metadata=dict(payload.get("metadata") or {}),
        )

    @classmethod
    def new(
        cls,
        *,
        validation_id: str,
        level: str,
        component: str,
        event: str,
        message: str,
        step_name: str | None = None,
        duration_ms: int | None = None,
        status: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> ValidationLogEntry:
        """Convenience constructor with auto-generated ID and timestamp."""
        return cls(
            id=f"log-{uuid.uuid4()}",
            validation_id=validation_id,
            timestamp=_now_utc(),
            level=level,
            component=component,
            event=event,
            message=message,
            step_name=step_name,
            duration_ms=duration_ms,
            status=status,
            correlation_id=validation_id,
            metadata=dict(metadata or {}),
        )


# ---------------------------------------------------------------------------
# ValidationExecutionRecord
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ValidationExecutionRecord:
    """Immutable, versionable snapshot of one validation execution.

    This is the canonical persistence unit.  It wraps all observable
    data about a validation run so that a reader — human, agent, or CLI
    — can reconstruct the complete picture after the fact.

    Constraints enforced in ``__post_init__``
    -----------------------------------------
    * ``id`` non-empty.
    * ``schema_version`` positive and equal to
      :data:`CURRENT_SCHEMA_VERSION` (1 for 7.11).
    * ``started_at`` ≤ ``completed_at`` when both are present.
    * A final status requires ``completed_at``.
    * ``commit_hash`` coherent with ``gate_result``.
    * All collections are normalised to tuples.
    * ``metadata`` is defensively copied.
    """

    id: str
    schema_version: int
    status: str
    policy: str | None = None
    actor: str | None = None
    execution_mode: str = "local"
    project_root: str | None = None
    branch: str | None = None
    base_commit: str | None = None
    changed_files: tuple[str, ...] = ()
    affected_tests: tuple[str, ...] = ()
    step_results: tuple[dict[str, Any], ...] = ()
    findings: tuple[dict[str, Any], ...] = ()
    artifacts: tuple[dict[str, Any], ...] = ()
    metrics: dict[str, Any] | None = None
    gate_result: dict[str, Any] | None = None
    commit_hash: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime = field(default_factory=_now_utc)
    metadata: dict[str, Any] = field(default_factory=dict)

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def __post_init__(self) -> None:
        # --- ID ---
        if not self.id:
            raise ValueError("ValidationExecutionRecord.id must not be empty")

        # --- schema_version ---
        if not isinstance(self.schema_version, int) or self.schema_version <= 0:
            raise ValueError(
                "ValidationExecutionRecord.schema_version must be a positive integer"
            )
        if self.schema_version > CURRENT_SCHEMA_VERSION:
            raise UnsupportedValidationSchemaError(
                code="unsupported_schema_version",
                message=(
                    f"schema_version={self.schema_version} is not supported by "
                    f"this code (max={CURRENT_SCHEMA_VERSION}). "
                    "Records from future versions cannot be loaded."
                ),
                validation_id=self.id,
            )

        # --- status ---
        if not self.status:
            raise ValueError("ValidationExecutionRecord.status must not be empty")

        # --- timestamps ---
        # Ensure timezone-awareness
        for attr in ("started_at", "completed_at", "created_at"):
            val = getattr(self, attr)
            if isinstance(val, datetime) and val.tzinfo is None:
                object.__setattr__(self, attr, val.replace(tzinfo=timezone.utc))

        if (
            self.started_at
            and self.completed_at
            and self.completed_at < self.started_at
        ):
            raise ValueError(
                "ValidationExecutionRecord.completed_at cannot be before started_at"
            )

        # A truly final status should have completed_at
        if self.status in _FINAL_STATUSES and self.completed_at is None:
            raise ValueError(
                f"ValidationExecutionRecord with final status {self.status!r} "
                "must have completed_at set"
            )

        # --- commit_hash coherence ---
        # A commit_hash without a gate_result that says commit_created=True
        # is suspicious; we allow it but at least enforce the reverse:
        # if gate_result says commit_created, there must be a commit_hash.
        if (
            self.gate_result is not None
            and self.gate_result.get("commit_created")
            and not self.commit_hash
        ):
            raise ValueError(
                "ValidationExecutionRecord.commit_hash must be set when "
                "gate_result.commit_created is True"
            )

        # --- defensive copies ---
        object.__setattr__(
            self, "changed_files", tuple(str(f) for f in (self.changed_files or ()))
        )
        object.__setattr__(
            self,
            "affected_tests",
            tuple(str(t) for t in (self.affected_tests or ())),
        )
        object.__setattr__(
            self, "step_results", tuple(dict(r) for r in (self.step_results or ()))
        )
        object.__setattr__(
            self, "findings", tuple(dict(f) for f in (self.findings or ()))
        )
        object.__setattr__(
            self, "artifacts", tuple(dict(a) for a in (self.artifacts or ()))
        )
        object.__setattr__(
            self,
            "metrics",
            dict(self.metrics) if self.metrics is not None else None,
        )
        object.__setattr__(
            self,
            "gate_result",
            dict(self.gate_result) if self.gate_result is not None else None,
        )
        object.__setattr__(self, "metadata", dict(self.metadata or {}))

    # ------------------------------------------------------------------
    # Derived properties
    # ------------------------------------------------------------------

    @property
    def is_active(self) -> bool:
        """True if the execution is still running (no completed_at)."""
        return self.completed_at is None

    @property
    def is_final(self) -> bool:
        return self.status in _FINAL_STATUSES

    @property
    def gate_allowed(self) -> bool | None:
        if self.gate_result is None:
            return None
        return bool(self.gate_result.get("allowed"))

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def serialize(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "id": self.id,
            "status": self.status,
            "policy": self.policy,
            "actor": self.actor,
            "execution_mode": self.execution_mode,
            "project_root": self.project_root,
            "branch": self.branch,
            "base_commit": self.base_commit,
            "changed_files": list(self.changed_files),
            "affected_tests": list(self.affected_tests),
            "step_results": list(self.step_results),
            "findings": list(self.findings),
            "artifacts": list(self.artifacts),
            "metrics": self.metrics,
            "gate_result": self.gate_result,
            "commit_hash": self.commit_hash,
            "started_at": (
                None if self.started_at is None else self.started_at.isoformat()
            ),
            "completed_at": (
                None if self.completed_at is None else self.completed_at.isoformat()
            ),
            "created_at": self.created_at.isoformat(),
            "metadata": dict(self.metadata or {}),
        }

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> ValidationExecutionRecord:
        """Deserialise from a raw mapping (e.g. loaded JSON dict).

        Raises
        ------
        UnsupportedValidationSchemaError
            If ``schema_version`` is greater than :data:`CURRENT_SCHEMA_VERSION`.
        ValidationPersistenceError
            If required fields are missing or malformed.
        """
        try:
            schema_version = int(payload["schema_version"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValidationPersistenceError(
                code="missing_schema_version",
                message="Record is missing a valid 'schema_version' field",
            ) from exc

        def _parse_dt(raw: Any) -> datetime | None:
            if raw is None:
                return None
            if isinstance(raw, datetime):
                return raw
            if isinstance(raw, str):
                return datetime.fromisoformat(raw)
            raise ValidationPersistenceError(
                code="invalid_timestamp",
                message=f"Cannot parse timestamp value: {raw!r}",
            )

        try:
            return cls(
                id=str(payload["id"]),
                schema_version=schema_version,
                status=str(payload["status"]),
                policy=payload.get("policy"),
                actor=payload.get("actor"),
                execution_mode=str(payload.get("execution_mode", "local")),
                project_root=payload.get("project_root"),
                branch=payload.get("branch"),
                base_commit=payload.get("base_commit"),
                changed_files=tuple(payload.get("changed_files") or ()),
                affected_tests=tuple(payload.get("affected_tests") or ()),
                step_results=tuple(payload.get("step_results") or ()),
                findings=tuple(payload.get("findings") or ()),
                artifacts=tuple(payload.get("artifacts") or ()),
                metrics=dict(payload["metrics"]) if payload.get("metrics") else None,
                gate_result=(
                    dict(payload["gate_result"]) if payload.get("gate_result") else None
                ),
                commit_hash=payload.get("commit_hash"),
                started_at=_parse_dt(payload.get("started_at")),
                completed_at=_parse_dt(payload.get("completed_at")),
                created_at=_parse_dt(payload.get("created_at")) or _now_utc(),
                metadata=dict(payload.get("metadata") or {}),
            )
        except (UnsupportedValidationSchemaError, ValidationPersistenceError):
            raise
        except Exception as exc:
            raise ValidationPersistenceError(
                code="deserialization_error",
                message=f"Cannot deserialize ValidationExecutionRecord: {exc}",
            ) from exc


__all__ = [
    "CURRENT_SCHEMA_VERSION",
    "LOG_EVENTS",
    "ValidationExecutionRecord",
    "ValidationLogEntry",
    "new_validation_id",
]
