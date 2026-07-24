"""End-to-end integration tests for Validation Interfaces (Phase 7.12)."""

from __future__ import annotations

from pathlib import Path

from cmm.validation import (
    StartValidationRequest,
    ValidationApplicationService,
    ValidationExitCode,
)
from cmm.validation.cli import handle_validation_cli, register_validation_cli


def test_full_validation_flow_e2e(tmp_path: Path) -> None:
    # 1. Setup temporary project
    (tmp_path / "cmm").mkdir()
    (tmp_path / "cmm" / "__init__.py").write_text("# sample project module")

    service = ValidationApplicationService(project_root=tmp_path)

    # 2. Run validation via application API
    req = StartValidationRequest(
        project_root=tmp_path,
        policy_name="ci",
        actor="e2e-test",
    )
    result_resp = service.start_validation(req)
    vid = result_resp.validation_id

    assert vid is not None
    assert result_resp.policy == "ci"

    # 3. Query status via service API
    status_resp = service.get_status(vid)
    assert status_resp.validation_id == vid
    assert status_resp.policy == "ci"

    # 4. List artifacts
    artifacts = service.list_artifacts(vid)
    assert isinstance(artifacts, list)

    # 5. Evaluate Commit Gate
    gate_resp = service.evaluate_gate(vid)
    assert gate_resp.validation_result_id == vid
    assert isinstance(gate_resp.allowed, bool)

    # 6. Verify same validation ID can be inspected via CLI
    import argparse

    parser = argparse.ArgumentParser(prog="cmm")
    subparsers = parser.add_subparsers(dest="command", required=True)
    register_validation_cli(subparsers)

    args = parser.parse_args(
        [
            "validation",
            "inspect",
            vid,
            "--output",
            "json",
            "--project",
            str(tmp_path),
        ]
    )

    exit_code = handle_validation_cli(args)
    assert exit_code == ValidationExitCode.SUCCESS
