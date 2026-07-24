"""Persistence and observability exceptions for Phase 7.11.

All exceptions inherit from :class:`ValidationErrorBase` so that
callers using the generic hierarchy continue to work unchanged.
Secrets must never appear in ``message`` or ``metadata``.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..exceptions import ValidationErrorBase

# ---------------------------------------------------------------------------
# Base mixin — adds optional path / validation_id / cause
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class _PersistenceBase(ValidationErrorBase):
    """Base for persistence exceptions with optional extra context."""

    path: Path | None = None
    validation_id: str | None = None
    cause: str | None = None

    def __str__(self) -> str:  # pragma: no cover - trivial
        parts = [f"{self.code}: {self.message}"]
        if self.validation_id:
            parts.append(f"(validation_id={self.validation_id})")
        if self.path:
            parts.append(f"(path={self.path})")
        if self.cause:
            parts.append(f"(cause={self.cause})")
        return " ".join(parts)


# ---------------------------------------------------------------------------
# Concrete exceptions
# ---------------------------------------------------------------------------


class ValidationPersistenceError(_PersistenceBase):
    """General persistence failure (I/O error, serialization problem, …)."""


class ValidationRecordNotFoundError(_PersistenceBase):
    """Requested execution record does not exist in the repository."""


class ValidationRecordConflictError(_PersistenceBase):
    """Attempted state transition that would regress an existing record.

    Examples: completing a record that is already marked as failed,
    overwriting a commit_hash with None, or reusing the same ID for a
    different execution.
    """


class ValidationStorageCorruptionError(_PersistenceBase):
    """Storage data is malformed and cannot be interpreted.

    The corrupted file is left in place for manual diagnosis;
    the caller must not delete it automatically.
    """


class UnsupportedValidationSchemaError(_PersistenceBase):
    """Record declares a ``schema_version`` that this code cannot read.

    This happens when a future version of CMM OS wrote a record and
    the current code tries to load it.  Migration helpers are out of
    scope for 7.11; records with unknown versions are rejected.
    """


class ValidationArtifactStorageError(_PersistenceBase):
    """Failed to persist or retrieve a :class:`ValidationArtifact`."""


__all__ = [
    "UnsupportedValidationSchemaError",
    "ValidationArtifactStorageError",
    "ValidationPersistenceError",
    "ValidationRecordConflictError",
    "ValidationRecordNotFoundError",
    "ValidationStorageCorruptionError",
]
