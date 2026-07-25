"""Abstract repository protocol for Phase 7.11 — Observability and Persistence.

:class:`ValidationRepositoryProtocol`
    ``typing.Protocol`` that defines the storage interface.  Any class
    that implements these methods qualifies, without needing to inherit.
    This allows future implementations (SQLite, remote API, object
    storage) to plug in with zero changes to consumers.

Invariants
----------
- ``save_execution`` must be idempotent for identical records.
- ``load_execution`` must return ``None`` (not raise) when the ID is
  unknown.
- ``list_executions`` must never have side effects.
- ``list_logs`` must preserve insertion order.
- ``save_artifact`` must persist the artifact JSON to durable storage.
- ``load_artifact`` must return ``None`` when not found.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from ..artifacts import ValidationArtifact
    from .history import ValidationHistoryPage, ValidationHistoryQuery
    from .models import ValidationExecutionRecord, ValidationLogEntry


@runtime_checkable
class ValidationRepositoryProtocol(Protocol):
    """Storage interface for validation execution data.

    Implementations may use JSON files, SQLite, a remote API, etc.
    Only the local JSON implementation is provided in 7.11.
    """

    # ------------------------------------------------------------------
    # Execution records
    # ------------------------------------------------------------------

    def save_execution(self, record: ValidationExecutionRecord) -> None:
        """Persist *record* atomically.

        If a record with the same ``id`` already exists, the
        implementation must apply the idempotence / conflict policy
        defined in its class docstring.
        """
        ...

    def load_execution(self, validation_id: str) -> ValidationExecutionRecord | None:
        """Return the record for *validation_id*, or ``None`` if absent."""
        ...

    def list_executions(self, query: ValidationHistoryQuery) -> ValidationHistoryPage:
        """Return a paginated slice of matching records.

        Records must be ordered most-recent-first by ``started_at`` /
        ``created_at``.
        """
        ...

    # ------------------------------------------------------------------
    # Logs
    # ------------------------------------------------------------------

    def save_log(self, entry: ValidationLogEntry) -> None:
        """Append *entry* to the log stream for its validation_id."""
        ...

    def list_logs(self, validation_id: str) -> tuple[ValidationLogEntry, ...]:
        """Return all log entries for *validation_id* in insertion order."""
        ...

    # ------------------------------------------------------------------
    # Artifacts
    # ------------------------------------------------------------------

    def save_artifact(self, validation_id: str, artifact: ValidationArtifact) -> None:
        """Persist the structured representation of *artifact*."""
        ...

    def load_artifact(
        self, validation_id: str, artifact_id: str
    ) -> ValidationArtifact | None:
        """Return the artifact, or ``None`` if not found."""
        ...


__all__ = ["ValidationRepositoryProtocol"]
