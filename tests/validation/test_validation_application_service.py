"""Unit and integration tests for ValidationApplicationService (Phase 7.12)."""

from __future__ import annotations

from pathlib import Path

import pytest

from cmm.validation import (
    StartValidationRequest,
    ValidationApplicationService,
    ValidationConflictError,
    ValidationNotFoundError,
    ValidationPolicyNotFoundError,
    ValidationStepNotFoundError,
)


def test_service_start_validation_basic(tmp_path: Path) -> None:
    # Create minimal project layout
    (tmp_path / "cmm").mkdir()
    (tmp_path / "cmm" / "__init__.py").write_text("# init")

    service = ValidationApplicationService(project_root=tmp_path)
    req = StartValidationRequest(
        project_root=tmp_path,
        policy_name="small_change",
    )
    result = service.start_validation(req)

    assert result.validation_id.startswith("val-")
    assert result.policy == "small_change"
    assert result.status in ("passed", "failed", "warning")


def test_service_invalid_policy(tmp_path: Path) -> None:
    service = ValidationApplicationService(project_root=tmp_path)
    req = StartValidationRequest(
        project_root=tmp_path,
        policy_name="non_existent_policy_123",
    )
    with pytest.raises(ValidationPolicyNotFoundError):
        service.start_validation(req)


def test_service_invalid_step(tmp_path: Path) -> None:
    service = ValidationApplicationService(project_root=tmp_path)
    req = StartValidationRequest(
        project_root=tmp_path,
        steps=("non_existent_step_123",),
    )
    with pytest.raises(ValidationStepNotFoundError):
        service.start_validation(req)


def test_service_get_validation_not_found(tmp_path: Path) -> None:
    service = ValidationApplicationService(project_root=tmp_path)
    with pytest.raises(ValidationNotFoundError):
        service.get_validation("val-does-not-exist")


def test_service_evaluate_gate(tmp_path: Path) -> None:
    (tmp_path / "cmm").mkdir()
    (tmp_path / "cmm" / "__init__.py").write_text("# init")

    service = ValidationApplicationService(project_root=tmp_path)
    req = StartValidationRequest(project_root=tmp_path, policy_name="small_change")
    res = service.start_validation(req)

    gate_res = service.evaluate_gate(res.validation_id)
    assert gate_res.validation_result_id == res.validation_id
    assert isinstance(gate_res.allowed, bool)


def test_service_idempotency(tmp_path: Path) -> None:
    (tmp_path / "cmm").mkdir()
    (tmp_path / "cmm" / "__init__.py").write_text("# init")

    service = ValidationApplicationService(project_root=tmp_path)
    req1 = StartValidationRequest(
        project_root=tmp_path,
        policy_name="small_change",
        request_id="req-unique-123",
    )
    res1 = service.start_validation(req1)

    # Identical request returns same execution result
    req2 = StartValidationRequest(
        project_root=tmp_path,
        policy_name="small_change",
        request_id="req-unique-123",
    )
    res2 = service.start_validation(req2)
    assert res2.validation_id == res1.validation_id

    # Incompatible policy with same request_id raises conflict error
    req_conflict = StartValidationRequest(
        project_root=tmp_path,
        policy_name="full",
        request_id="req-unique-123",
    )
    with pytest.raises(ValidationConflictError):
        service.start_validation(req_conflict)


def test_service_get_status_and_history(tmp_path: Path) -> None:
    (tmp_path / "cmm").mkdir()
    (tmp_path / "cmm" / "__init__.py").write_text("# init")

    service = ValidationApplicationService(project_root=tmp_path)
    req = StartValidationRequest(project_root=tmp_path, policy_name="small_change")
    res = service.start_validation(req)

    status_resp = service.get_status(res.validation_id)
    assert status_resp.validation_id == res.validation_id
    assert status_resp.status == res.status

    page = service.query_history()
    assert page.total >= 1
    assert any(item.id == res.validation_id for item in page.items)


def test_service_artifacts_retrieval(tmp_path: Path) -> None:
    (tmp_path / "cmm").mkdir()
    (tmp_path / "cmm" / "__init__.py").write_text("# init")

    service = ValidationApplicationService(project_root=tmp_path)
    req = StartValidationRequest(project_root=tmp_path, policy_name="small_change")
    res = service.start_validation(req)

    artifacts = service.list_artifacts(res.validation_id)
    assert isinstance(artifacts, list)

    with pytest.raises(ValidationNotFoundError):
        service.get_artifact(res.validation_id, "non-existent-artifact-999")


def test_persisted_result_reconstruction_preserves_commit_gate_evidence(
    tmp_path: Path,
) -> None:
    from datetime import datetime, timezone

    from cmm.validation.commit_gate.evaluator import CommitGateEvaluator
    from cmm.validation.observability import ValidationExecutionRecord
    from cmm.validation.policy import (
        DEFAULT_VALIDATION_POLICIES,
        expand_validation_step_labels,
    )

    service = ValidationApplicationService(project_root=tmp_path)
    policy = DEFAULT_VALIDATION_POLICIES["small_change"]
    required_steps = expand_validation_step_labels(policy.required_steps)
    timestamp = datetime.now(timezone.utc)

    record = ValidationExecutionRecord(
        id="val-persisted-gate-regression",
        schema_version=1,
        status="passed",
        policy=policy.name,
        changed_files=("cmm/example.py",),
        affected_tests=("tests/test_example.py",),
        step_results=tuple(
            {
                "name": step_name,
                "status": "passed",
                "exit_code": 0,
                "duration_ms": 1,
                "stdout": "",
                "stderr": "",
                "findings": [],
                "artifacts": [],
                "started_at": timestamp.isoformat(),
                "completed_at": timestamp.isoformat(),
                "metadata": {},
            }
            for step_name in required_steps
        ),
        findings=(
            {
                "code": "NON_BLOCKING_INFORMATION",
                "message": "Persisted informational finding",
                "severity": "info",
                "source": "test",
                "file_path": None,
                "line": None,
                "column": None,
                "blocking": False,
                "suggested_fix": None,
                "documentation_url": None,
                "metadata": {},
            },
        ),
        artifacts=(
            {
                "id": "persisted-report",
                "kind": "test_report",
                "source": "pytest",
                "path": None,
                "content": {"tests_passed": 1},
                "findings": [],
                "metrics": {"tests_passed": 1},
                "created_at": timestamp.isoformat(),
                "metadata": {},
            },
        ),
        metrics={"total_duration_ms": 123},
        started_at=timestamp,
        completed_at=timestamp,
    )

    reconstructed = service._record_to_validation_result(record)

    assert tuple(step.name for step in reconstructed.steps) == required_steps
    assert reconstructed.artifacts[0].id == "persisted-report"
    assert reconstructed.warnings[0].code == "NON_BLOCKING_INFORMATION"
    assert reconstructed.changed_files == (Path("cmm/example.py"),)
    assert reconstructed.duration_ms == 123
    assert reconstructed.can_commit is True

    gate_result = CommitGateEvaluator.evaluate(reconstructed, policy)

    assert gate_result.allowed is True
    assert gate_result.reasons == ()
