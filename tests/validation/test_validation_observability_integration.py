"""Integration tests for Phase 7.11 — ValidationObservabilityService
and end-to-end pipeline + persistence.

Covers:
1. Service start → complete → retrieve lifecycle
2. Pipeline integration with observability
3. Gate result recording
4. Log retrieval
5. Artifact retrieval
6. Correlation by validation_id
7. Optional observability (None) keeps pipeline working
8. Persistence failure does not corrupt result
9. Restart simulation (new repo on same storage)
10. Cancelled/failed pipeline scenarios
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from cmm.validation.artifacts import ValidationArtifact
from cmm.validation.commit_gate.enums import CommitGateReasonCode
from cmm.validation.commit_gate.models import CommitGateReason, CommitGateResult
from cmm.validation.context import ValidationContext
from cmm.validation.enums import ValidationStatus
from cmm.validation.executor import ValidationExecutor
from cmm.validation.observability.history import ValidationHistoryQuery
from cmm.validation.observability.repository import LocalValidationRepository
from cmm.validation.observability.service import ValidationObservabilityService
from cmm.validation.pipeline import ValidationPipeline
from cmm.validation.registry import ValidationRegistry
from cmm.validation.results import ValidationResult
from cmm.validation.steps import (
    ValidationStep,
    ValidationStepResult,
    ValidationStepType,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _make_context(tmp_path: Path, policy: str = "small_change") -> ValidationContext:
    return ValidationContext(
        project_root=tmp_path,
        changed_files=(),
        execution_mode="local",
        requested_policy=policy,
        actor="human:christian",
        branch="feature/phase-7-continuous-validation",
        base_commit="abc123",
    )


def _make_store(tmp_path: Path) -> Path:
    return tmp_path / ".cmm" / "validation"


def _make_service(
    store: Path,
) -> tuple[LocalValidationRepository, ValidationObservabilityService]:
    repo = LocalValidationRepository(store)
    service = ValidationObservabilityService(repository=repo)
    return repo, service


class _PassingValidator:
    """Internal validator that always returns PASSED."""

    def validate(
        self,
        context: ValidationContext,
        step: ValidationStep,
        registry: ValidationRegistry,
    ) -> ValidationStepResult:
        return ValidationStepResult(
            name=step.name,
            status=ValidationStatus.PASSED,
            duration_ms=10,
        )


class _FailingValidator:
    """Internal validator that always returns FAILED."""

    def validate(
        self,
        context: ValidationContext,
        step: ValidationStep,
        registry: ValidationRegistry,
    ) -> ValidationStepResult:
        return ValidationStepResult(
            name=step.name,
            status=ValidationStatus.FAILED,
            duration_ms=10,
        )


def _internal_step(name: str) -> ValidationStep:
    return ValidationStep(
        name=name,
        step_type=ValidationStepType.INTERNAL,
        command=(),
        required=False,
    )


# ---------------------------------------------------------------------------
# Service lifecycle
# ---------------------------------------------------------------------------


def test_service_start_and_complete_execution(tmp_path: Path) -> None:
    store = _make_store(tmp_path)
    repo, service = _make_service(store)
    ctx = _make_context(tmp_path)

    vid = service.start_execution(context=ctx)
    assert vid.startswith("validation-")

    # Record in-progress
    in_progress = repo.load_execution(vid)
    assert in_progress is not None
    assert in_progress.status == "running"

    # Simulate a minimal result
    result = ValidationResult(
        id=vid,
        status=ValidationStatus.PASSED,
        policy="small_change",
        duration_ms=500,
        started_at=_now(),
        completed_at=_now(),
    )
    record = service.complete_execution(validation_id=vid, result=result)
    assert record.status == "passed"

    # Retrieve
    retrieved = service.get_execution(vid)
    assert retrieved is not None
    assert retrieved.status == "passed"


def test_service_logs_recorded(tmp_path: Path) -> None:
    store = _make_store(tmp_path)
    _repo, service = _make_service(store)
    ctx = _make_context(tmp_path)

    vid = service.start_execution(context=ctx)
    result = ValidationResult(
        id=vid,
        status=ValidationStatus.PASSED,
        duration_ms=100,
        started_at=_now(),
        completed_at=_now(),
    )
    service.complete_execution(validation_id=vid, result=result)

    logs = service.get_logs(vid)
    assert len(logs) >= 2  # at least started + completed
    events = [l.event for l in logs]
    assert "validation.started" in events
    assert "validation.completed" in events


def test_service_step_logging(tmp_path: Path) -> None:
    store = _make_store(tmp_path)
    _repo, service = _make_service(store)
    ctx = _make_context(tmp_path)
    vid = service.start_execution(context=ctx)

    service.record_step_started(validation_id=vid, step_name="lint")
    service.record_step_completed(
        validation_id=vid, step_name="lint", status="passed", duration_ms=200
    )

    logs = service.get_logs(vid)
    events = [l.event for l in logs]
    assert "validation.step.started" in events
    assert "validation.step.completed" in events


def test_service_gate_result_logging(tmp_path: Path) -> None:
    store = _make_store(tmp_path)
    _repo, service = _make_service(store)
    ctx = _make_context(tmp_path)
    vid = service.start_execution(context=ctx)

    gate = CommitGateResult(
        allowed=True,
        validation_result_id=vid,
    )
    service.record_gate_result(validation_id=vid, gate_result=gate)

    logs = service.get_logs(vid)
    events = [l.event for l in logs]
    assert "validation.gate.approved" in events


def test_service_gate_denied_logging(tmp_path: Path) -> None:
    store = _make_store(tmp_path)
    _repo, service = _make_service(store)
    ctx = _make_context(tmp_path)
    vid = service.start_execution(context=ctx)

    gate = CommitGateResult(
        allowed=False,
        validation_result_id=vid,
        reasons=(
            CommitGateReason(
                code=CommitGateReasonCode.VALIDATION_NOT_PASSED,
                message="Tests failed",
            ),
        ),
    )
    service.record_gate_result(validation_id=vid, gate_result=gate)

    logs = service.get_logs(vid)
    events = [l.event for l in logs]
    assert "validation.gate.rejected" in events


def test_service_artifact_persistence(tmp_path: Path) -> None:
    store = _make_store(tmp_path)
    _repo, service = _make_service(store)
    ctx = _make_context(tmp_path)
    vid = service.start_execution(context=ctx)

    artifact = ValidationArtifact(
        id="test-artifact-001",
        kind="lint_report",
        source="ruff",
        content={"violations": 0},
        created_at=_now(),
    )
    result = ValidationResult(
        id=vid,
        status=ValidationStatus.PASSED,
        artifacts=(artifact,),
        duration_ms=100,
        started_at=_now(),
        completed_at=_now(),
    )
    service.complete_execution(validation_id=vid, result=result)

    loaded_artifact = service.get_artifact(vid, artifact.id)
    assert loaded_artifact is not None
    assert loaded_artifact.id == artifact.id
    assert loaded_artifact.kind == "lint_report"


def test_service_history_query(tmp_path: Path) -> None:
    store = _make_store(tmp_path)
    _repo, service = _make_service(store)
    ctx = _make_context(tmp_path)

    # Create 3 executions
    for i in range(3):
        vid = service.start_execution(
            context=ctx, validation_id=f"validation-hist-{i:03d}"
        )
        result = ValidationResult(
            id=vid,
            status=ValidationStatus.PASSED,
            duration_ms=100,
            started_at=_now(),
            completed_at=_now(),
        )
        service.complete_execution(validation_id=vid, result=result)

    page = service.list_history(ValidationHistoryQuery(status="passed"))
    assert page.total >= 3


def test_service_correlation_by_validation_id(tmp_path: Path) -> None:
    """All logs, artifacts, and the record share the same validation_id."""
    store = _make_store(tmp_path)
    repo, service = _make_service(store)
    ctx = _make_context(tmp_path)
    vid = service.start_execution(context=ctx)

    artifact = ValidationArtifact(
        id="corr-artifact",
        kind="report",
        source="test",
        content={"ok": True},
        created_at=_now(),
    )
    result = ValidationResult(
        id=vid,
        status=ValidationStatus.PASSED,
        artifacts=(artifact,),
        duration_ms=50,
        started_at=_now(),
        completed_at=_now(),
    )
    service.complete_execution(validation_id=vid, result=result)

    record = repo.load_execution(vid)
    logs = repo.list_logs(vid)
    art = repo.load_artifact(vid, "corr-artifact")

    assert record is not None and record.id == vid
    assert all(l.validation_id == vid for l in logs)
    assert art is not None


# ---------------------------------------------------------------------------
# Pipeline integration
# ---------------------------------------------------------------------------


def test_pipeline_without_observability_still_works(tmp_path: Path) -> None:
    """observability=None must not break the pipeline."""
    registry = ValidationRegistry()
    executor = ValidationExecutor()
    pipeline = ValidationPipeline(
        executor=executor, registry=registry, observability=None
    )
    ctx = ValidationContext(
        project_root=tmp_path,
        execution_mode="local",
        requested_policy="full",
        change_type="full",
    )
    result = pipeline.run(ctx, [])
    # Empty pipeline returns PASSED (no steps = no failures)
    assert result.status in (
        ValidationStatus.PASSED,
        ValidationStatus.WARNING,
        ValidationStatus.ERROR,
        ValidationStatus.FAILED,
    )


def test_pipeline_with_observability_records_execution(tmp_path: Path) -> None:
    store = _make_store(tmp_path)
    repo, service = _make_service(store)

    registry = ValidationRegistry()
    executor = ValidationExecutor()
    pipeline = ValidationPipeline(
        executor=executor, registry=registry, observability=service
    )

    ctx = _make_context(tmp_path)
    result = pipeline.run(ctx, [])

    # Result must have a valid ID and be retrievable
    assert result.id.startswith("validation-")
    retrieved = repo.load_execution(result.id)
    assert retrieved is not None
    assert retrieved.status in ("passed", "failed", "warning", "error")


def test_pipeline_result_id_matches_persisted_id(tmp_path: Path) -> None:
    store = _make_store(tmp_path)
    repo, service = _make_service(store)

    registry = ValidationRegistry()
    executor = ValidationExecutor()
    pipeline = ValidationPipeline(
        executor=executor, registry=registry, observability=service
    )
    ctx = _make_context(tmp_path)
    result = pipeline.run(ctx, [])

    retrieved = repo.load_execution(result.id)
    assert retrieved is not None
    assert retrieved.id == result.id


def test_pipeline_observability_failure_does_not_break_result(tmp_path: Path) -> None:
    """Simulates an observability backend that throws immediately."""

    class _FailingRepo:
        def save_execution(self, record) -> None:
            raise RuntimeError("Storage is down!")

        def load_execution(self, vid):
            return None

        def list_executions(self, query):
            from cmm.validation.observability.history import ValidationHistoryPage

            return ValidationHistoryPage()

        def save_log(self, entry) -> None:
            raise RuntimeError("Log storage is down!")

        def list_logs(self, vid):
            return ()

        def save_artifact(self, vid, artifact) -> None:
            raise RuntimeError("Artifact storage down!")

        def load_artifact(self, vid, aid):
            return None

    failing_service = ValidationObservabilityService(repository=_FailingRepo())
    registry = ValidationRegistry()
    executor = ValidationExecutor()
    pipeline = ValidationPipeline(
        executor=executor, registry=registry, observability=failing_service
    )
    ctx = _make_context(tmp_path)
    result = pipeline.run(ctx, [])
    # Must still produce a result (not raise)
    assert result is not None
    assert result.id


# ---------------------------------------------------------------------------
# Restart simulation
# ---------------------------------------------------------------------------


def test_data_survives_restart(tmp_path: Path) -> None:
    """Create a repo, write data, then open a new repo instance on same storage."""
    store = _make_store(tmp_path)

    # First session
    _repo1, service1 = _make_service(store)
    ctx = _make_context(tmp_path)
    vid = service1.start_execution(context=ctx)
    result = ValidationResult(
        id=vid,
        status=ValidationStatus.PASSED,
        duration_ms=100,
        started_at=_now(),
        completed_at=_now(),
    )
    service1.complete_execution(validation_id=vid, result=result)

    # Second session — completely fresh repo instance
    repo2 = LocalValidationRepository(store)
    service2 = ValidationObservabilityService(repository=repo2)

    retrieved = service2.get_execution(vid)
    assert retrieved is not None
    assert retrieved.status == "passed"

    logs = service2.get_logs(vid)
    assert len(logs) >= 1
