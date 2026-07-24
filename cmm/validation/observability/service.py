"""Observability service for Phase 7.11.

:class:`ValidationObservabilityService`
    Coordinates record construction, metrics calculation, sanitisation,
    and persistence.  It delegates storage to an injected
    :class:`ValidationRepositoryProtocol` implementation.

The service does **not**:
- Execute validations.
- Modify pipeline logic.
- Implement a general event system.
- Couple commit-gate approval logic with persistence.

All data is sanitised before being handed to the repository.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..commit_gate.models import CommitGateResult
    from ..results import ValidationResult
    from .protocols import ValidationRepositoryProtocol

from ..artifacts import ValidationArtifact
from ..context import ValidationContext
from .history import ValidationHistoryPage, ValidationHistoryQuery
from .metrics import ValidationMetricsCalculator
from .models import (
    CURRENT_SCHEMA_VERSION,
    ValidationExecutionRecord,
    ValidationLogEntry,
    new_validation_id,
)
from .sanitization import sanitize_validation_data


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


class ValidationObservabilityService:
    """Coordinates observability and persistence for a validation run.

    Parameters
    ----------
    repository:
        A :class:`ValidationRepositoryProtocol` implementation.
        All persistence is delegated here.
    metrics_calculator:
        Optional custom calculator; defaults to
        :class:`ValidationMetricsCalculator`.
    """

    def __init__(
        self,
        repository: ValidationRepositoryProtocol,
        metrics_calculator: ValidationMetricsCalculator | None = None,
    ) -> None:
        self._repo = repository
        self._calc = metrics_calculator or ValidationMetricsCalculator()

    # ------------------------------------------------------------------
    # Execution lifecycle
    # ------------------------------------------------------------------

    def start_execution(
        self,
        *,
        context: ValidationContext,
        validation_id: str | None = None,
        actor: str | None = None,
    ) -> str:
        """Create and persist an in-progress execution record.

        Returns the assigned ``validation_id``.
        """
        vid = validation_id or new_validation_id()
        now = _now_utc()

        record = ValidationExecutionRecord(
            id=vid,
            schema_version=CURRENT_SCHEMA_VERSION,
            status="running",
            policy=context.requested_policy or context.change_type,
            actor=actor or context.actor,
            execution_mode=context.execution_mode,
            project_root=str(context.project_root),
            branch=context.branch,
            base_commit=context.base_commit,
            changed_files=tuple(str(f) for f in (context.changed_files or ())),
            started_at=now,
            created_at=now,
        )
        self._safe_save(record)
        self.record_log(
            validation_id=vid,
            level="info",
            component="validation.observability",
            event="validation.started",
            message="Validation execution started",
            metadata={"execution_mode": context.execution_mode},
        )
        return vid

    def complete_execution(
        self,
        *,
        validation_id: str,
        result: ValidationResult,
        gate_result: CommitGateResult | None = None,
    ) -> ValidationExecutionRecord:
        """Build, sanitise, and persist the completed execution record.

        Also persists all artifacts found in *result*.

        Returns the persisted record.
        """
        # Calculate metrics
        metrics = self._calc.calculate(result, gate_result)
        metrics_dict = sanitize_validation_data(metrics.serialize())

        # Gate
        gate_dict = (
            sanitize_validation_data(gate_result.serialize())
            if gate_result is not None
            else None
        )

        # Step results — sanitise stdout/stderr
        step_results = tuple(
            sanitize_validation_data(s.serialize()) for s in (result.steps or ())
        )

        # Findings
        all_findings = list(result.blocking_findings or ()) + list(
            result.warnings or ()
        )
        findings_serialized = tuple(
            sanitize_validation_data(f.serialize()) for f in all_findings
        )

        # Artifacts (structured data)
        artifacts_serialized = tuple(
            sanitize_validation_data(a.serialize()) for a in (result.artifacts or ())
        )

        now = _now_utc()
        record = ValidationExecutionRecord(
            id=validation_id,
            schema_version=CURRENT_SCHEMA_VERSION,
            status=result.status.value
            if hasattr(result.status, "value")
            else str(result.status),
            policy=result.policy,
            actor=None,  # preserved from existing record if available
            execution_mode="local",
            changed_files=tuple(str(f) for f in (result.changed_files or ())),
            affected_tests=tuple(result.affected_tests or ()),
            step_results=step_results,
            findings=findings_serialized,
            artifacts=artifacts_serialized,
            metrics=metrics_dict,
            gate_result=gate_dict,
            commit_hash=(gate_result.commit_hash if gate_result is not None else None),
            started_at=result.started_at,
            completed_at=result.completed_at or now,
            created_at=now,
            metadata=sanitize_validation_data(dict(result.metadata or {})),
        )

        # Attempt to preserve actor from the existing record
        try:
            existing = self._repo.load_execution(validation_id)
            if existing is not None:
                record = ValidationExecutionRecord(
                    id=record.id,
                    schema_version=record.schema_version,
                    status=record.status,
                    policy=record.policy or existing.policy,
                    actor=existing.actor,
                    execution_mode=existing.execution_mode,
                    project_root=existing.project_root,
                    branch=existing.branch,
                    base_commit=existing.base_commit,
                    changed_files=record.changed_files,
                    affected_tests=record.affected_tests,
                    step_results=record.step_results,
                    findings=record.findings,
                    artifacts=record.artifacts,
                    metrics=record.metrics,
                    gate_result=record.gate_result,
                    commit_hash=record.commit_hash,
                    started_at=existing.started_at or record.started_at,
                    completed_at=record.completed_at,
                    created_at=existing.created_at,
                    metadata=record.metadata,
                )
        except Exception:  # noqa: BLE001, S110
            pass  # best effort; proceed with what we have

        self._safe_save(record)

        # Persist artifacts individually
        for artifact in result.artifacts or ():
            self._safe_save_artifact(validation_id, artifact)

        self.record_log(
            validation_id=validation_id,
            level="info",
            component="validation.observability",
            event="validation.completed",
            message=f"Validation execution completed with status={record.status}",
            status=record.status,
            duration_ms=result.duration_ms,
        )

        return record

    # ------------------------------------------------------------------
    # Step events
    # ------------------------------------------------------------------

    def record_step_started(
        self,
        *,
        validation_id: str,
        step_name: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self.record_log(
            validation_id=validation_id,
            level="info",
            component="validation.pipeline",
            event="validation.step.started",
            message=f"Step '{step_name}' started",
            step_name=step_name,
            metadata=metadata,
        )

    def record_step_completed(
        self,
        *,
        validation_id: str,
        step_name: str,
        status: str,
        duration_ms: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        event = (
            "validation.step.completed"
            if status not in ("failed", "timed_out")
            else f"validation.step.{status}"
        )
        level = "info" if status in ("passed", "skipped", "warning") else "warning"
        self.record_log(
            validation_id=validation_id,
            level=level,
            component="validation.pipeline",
            event=event,
            message=f"Step '{step_name}' completed with status={status}",
            step_name=step_name,
            status=status,
            duration_ms=duration_ms,
            metadata=metadata,
        )

    # ------------------------------------------------------------------
    # Gate
    # ------------------------------------------------------------------

    def record_gate_result(
        self,
        *,
        validation_id: str,
        gate_result: CommitGateResult,
    ) -> None:
        """Log the gate evaluation outcome."""
        event = (
            "validation.gate.approved"
            if gate_result.allowed
            else "validation.gate.rejected"
        )
        level = "info" if gate_result.allowed else "warning"
        self.record_log(
            validation_id=validation_id,
            level=level,
            component="validation.commit_gate",
            event=event,
            message=(
                f"Commit gate {'approved' if gate_result.allowed else 'rejected'} "
                f"for validation {validation_id}"
            ),
            status="allowed" if gate_result.allowed else "denied",
        )
        if gate_result.commit_created:
            self.record_log(
                validation_id=validation_id,
                level="info",
                component="validation.commit_gate",
                event="validation.commit.created",
                message=f"Provisional commit created: {gate_result.commit_hash}",
                metadata={"commit_hash": gate_result.commit_hash},
            )

    # ------------------------------------------------------------------
    # Structured logging
    # ------------------------------------------------------------------

    def record_log(
        self,
        *,
        validation_id: str,
        level: str,
        component: str,
        event: str,
        message: str,
        step_name: str | None = None,
        status: str | None = None,
        duration_ms: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Create and persist a structured log entry."""
        entry = ValidationLogEntry.new(
            validation_id=validation_id,
            level=level,
            component=component,
            event=event,
            message=message,
            step_name=step_name,
            duration_ms=duration_ms,
            status=status,
            metadata=sanitize_validation_data(metadata or {}),
        )
        try:
            self._repo.save_log(entry)
        except (
            Exception
        ) as exc:  # persistence failure must not hide results  # noqa: BLE001
            self._record_persistence_failure(validation_id, exc, "log")

    # ------------------------------------------------------------------
    # Retrieval
    # ------------------------------------------------------------------

    def get_execution(self, validation_id: str) -> ValidationExecutionRecord | None:
        """Return the execution record or ``None``."""
        return self._repo.load_execution(validation_id)

    def list_history(
        self, query: ValidationHistoryQuery | None = None
    ) -> ValidationHistoryPage:
        """Return a paginated history page."""
        q = query or ValidationHistoryQuery()
        return self._repo.list_executions(q)

    def get_logs(self, validation_id: str) -> tuple[ValidationLogEntry, ...]:
        """Return all log entries for *validation_id* in order."""
        return self._repo.list_logs(validation_id)

    def get_artifact(
        self, validation_id: str, artifact_id: str
    ) -> ValidationArtifact | None:
        """Return an artifact or ``None``."""
        return self._repo.load_artifact(validation_id, artifact_id)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _safe_save(self, record: ValidationExecutionRecord) -> None:
        """Save *record*, converting persistence errors to log entries."""
        try:
            self._repo.save_execution(record)
        except Exception as exc:
            self._record_persistence_failure(record.id, exc, "execution")
            raise

    def _safe_save_artifact(
        self, validation_id: str, artifact: ValidationArtifact
    ) -> None:
        try:
            # Sanitise artifact before persisting
            safe_artifact = ValidationArtifact(
                id=artifact.id,
                kind=artifact.kind,
                source=artifact.source,
                path=artifact.path,
                content=sanitize_validation_data(dict(artifact.content or {})),
                findings=artifact.findings,
                metrics=sanitize_validation_data(dict(artifact.metrics or {})),
                created_at=artifact.created_at,
                metadata=sanitize_validation_data(dict(artifact.metadata or {})),
            )
            self._repo.save_artifact(validation_id, safe_artifact)
        except Exception as exc:  # noqa: BLE001
            # Artifact persistence failures are non-fatal
            self._record_persistence_failure(validation_id, exc, "artifact")

    def _record_persistence_failure(
        self,
        validation_id: str,
        exc: Exception,
        target: str,
    ) -> None:
        """Attempt to log a persistence failure — best effort only."""
        try:
            entry = ValidationLogEntry.new(
                validation_id=validation_id,
                level="error",
                component="validation.observability",
                event="validation.persistence.failed",
                message=f"Persistence failure for {target}: {type(exc).__name__}",
                metadata={"error_type": type(exc).__name__},
            )
            self._repo.save_log(entry)
        except Exception:  # noqa: BLE001, S110
            pass  # truly nothing more we can do


__all__ = ["ValidationObservabilityService"]
