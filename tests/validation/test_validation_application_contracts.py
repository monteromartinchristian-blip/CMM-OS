"""Unit tests for Validation Application Contracts (Phase 7.12)."""

from __future__ import annotations

from pathlib import Path

import pytest

from cmm.validation import (
    StartValidationRequest,
    ValidationGateResponse,
    ValidationInvalidRequestError,
    ValidationStatusResponse,
)


def test_start_validation_request_defaults(tmp_path: Path) -> None:
    req = StartValidationRequest(project_root=tmp_path)
    assert req.project_root == tmp_path.resolve()
    assert req.policy_name is None
    assert req.steps is None
    assert req.files is None
    assert req.use_git_changes is False
    assert req.persist is True


def test_start_validation_request_invalid_root() -> None:
    non_existent = Path("/non/existent/path/for/test/12345")
    with pytest.raises(ValidationInvalidRequestError):
        StartValidationRequest(project_root=non_existent)


def test_start_validation_request_path_traversal(tmp_path: Path) -> None:
    bad_file = Path("../../etc/passwd")
    with pytest.raises(ValidationInvalidRequestError):
        StartValidationRequest(project_root=tmp_path, files=(bad_file,))


def test_start_validation_request_serialization(tmp_path: Path) -> None:
    req = StartValidationRequest(
        project_root=tmp_path,
        policy_name="small_change",
        steps=("lint", "syntax"),
        actor="dev",
    )
    serialized = req.serialize()
    assert serialized["policy_name"] == "small_change"
    assert serialized["steps"] == ["lint", "syntax"]
    assert serialized["actor"] == "dev"

    deserialized = StartValidationRequest.from_mapping(serialized)
    assert deserialized.policy_name == "small_change"
    assert deserialized.steps == ("lint", "syntax")


def test_validation_status_response_serialization() -> None:
    resp = ValidationStatusResponse(
        validation_id="val-123",
        status="passed",
        policy="ci",
    )
    serialized = resp.serialize()
    assert serialized["validation_id"] == "val-123"
    assert serialized["status"] == "passed"


def test_validation_gate_response_serialization() -> None:
    resp = ValidationGateResponse(
        allowed=True,
        reasons=({"code": "all_passed", "message": "OK"},),
        blocking_findings=(),
        validation_result_id="val-123",
    )
    serialized = resp.serialize()
    assert serialized["allowed"] is True
    assert serialized["validation_result_id"] == "val-123"
