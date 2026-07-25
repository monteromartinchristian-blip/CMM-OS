"""Unit tests for presenters (Phase 7.12)."""

from __future__ import annotations

import json

from cmm.validation import (
    ValidationArtifactResponse,
    ValidationGateResponse,
    ValidationResultResponse,
    ValidationStatusResponse,
    format_human_artifacts,
    format_human_gate,
    format_human_inspect,
    format_human_run,
    format_json_response,
)


def test_format_json_response_success() -> None:
    raw = format_json_response(
        command="validation.run",
        success=True,
        exit_code=0,
        validation_id="val-100",
        result={"status": "passed"},
        error=None,
    )
    parsed = json.loads(raw)
    assert parsed["schema_version"] == 1
    assert parsed["command"] == "validation.run"
    assert parsed["success"] is True
    assert parsed["exit_code"] == 0
    assert parsed["validation_id"] == "val-100"
    assert parsed["result"] == {"status": "passed"}
    assert parsed["error"] is None


def test_format_json_response_error() -> None:
    raw = format_json_response(
        command="validation.inspect",
        success=False,
        exit_code=3,
        validation_id=None,
        result=None,
        error={"code": "validation_not_found", "message": "Not found", "details": {}},
    )
    parsed = json.loads(raw)
    assert parsed["success"] is False
    assert parsed["exit_code"] == 3
    assert parsed["error"]["code"] == "validation_not_found"


def test_format_human_run() -> None:
    resp = ValidationResultResponse(
        validation_id="val-100",
        status="passed",
        policy="small_change",
        duration_ms=120,
        can_commit=True,
    )
    human = format_human_run(resp)
    assert "Validation val-100" in human
    assert "Policy: small_change" in human
    assert "Status: passed" in human
    assert "Gate: allowed" in human


def test_format_human_inspect() -> None:
    rec = ValidationStatusResponse(
        validation_id="val-100",
        status="passed",
        policy="small_change",
        actor="developer",
    )
    human = format_human_inspect(rec)
    assert "Validation val-100" in human
    assert "Actor: developer" in human


def test_format_human_artifacts() -> None:
    art = ValidationArtifactResponse(
        id="art-1",
        kind="lint_report",
        source="ruff",
        size_bytes=100,
    )
    human_list = format_human_artifacts([art])
    assert "Artifacts (1):" in human_list
    assert "art-1" in human_list

    human_single = format_human_artifacts([art], selected_artifact=art)
    assert "Artifact art-1" in human_single
    assert "Kind: lint_report" in human_single


def test_format_human_gate() -> None:
    gate = ValidationGateResponse(
        allowed=True,
        reasons=(),
        blocking_findings=(),
        validation_result_id="val-100",
    )
    human = format_human_gate(gate)
    assert "Validation Gate: allowed" in human
    assert "Validation Result ID: val-100" in human
