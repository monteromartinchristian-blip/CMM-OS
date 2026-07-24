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
