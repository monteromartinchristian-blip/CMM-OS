"""Unit tests for Validation CLI JSON output formatting and clean stdout (Phase 7.12)."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from cmm.validation import ValidationExitCode
from cmm.validation.cli import handle_validation_cli, register_validation_cli


def _build_test_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="cmm")
    subparsers = parser.add_subparsers(dest="command", required=True)
    register_validation_cli(subparsers)
    return parser


def test_cli_run_json_valid_stdout(tmp_path: Path, capsys) -> None:
    (tmp_path / "cmm").mkdir()
    (tmp_path / "cmm" / "__init__.py").write_text("# init")

    parser = _build_test_parser()
    args = parser.parse_args(
        [
            "validation",
            "run",
            "--policy",
            "small_change",
            "--output",
            "json",
            "--project",
            str(tmp_path),
        ]
    )

    exit_code = handle_validation_cli(args)
    captured = capsys.readouterr()

    # stdout MUST be valid JSON
    parsed = json.loads(captured.out)
    assert parsed["schema_version"] == 1
    assert parsed["command"] == "validation.run"
    assert parsed["validation_id"].startswith("val-")
    assert parsed["result"] is not None
    assert parsed["error"] is None
    assert exit_code in (
        ValidationExitCode.SUCCESS,
        ValidationExitCode.VALIDATION_FAILED,
    )


def test_cli_inspect_json_error(tmp_path: Path, capsys) -> None:
    parser = _build_test_parser()
    args = parser.parse_args(
        [
            "validation",
            "inspect",
            "val-non-existent",
            "--output",
            "json",
            "--project",
            str(tmp_path),
        ]
    )

    exit_code = handle_validation_cli(args)
    captured = capsys.readouterr()

    # stdout MUST be valid JSON even on error
    parsed = json.loads(captured.out)
    assert parsed["schema_version"] == 1
    assert parsed["command"] == "validation.inspect"
    assert parsed["success"] is False
    assert parsed["exit_code"] == ValidationExitCode.NOT_FOUND
    assert parsed["error"]["code"] == "validation_not_found"
    assert exit_code == ValidationExitCode.NOT_FOUND


def test_cli_quiet_and_verbose_mutual_exclusion_json(capsys) -> None:
    parser = _build_test_parser()
    args = parser.parse_args(
        [
            "validation",
            "run",
            "--output",
            "json",
            "--quiet",
            "--verbose",
        ]
    )

    exit_code = handle_validation_cli(args)
    captured = capsys.readouterr()

    parsed = json.loads(captured.out)
    assert parsed["success"] is False
    assert parsed["exit_code"] == ValidationExitCode.INVALID_USAGE
    assert parsed["error"]["code"] == "validation_invalid_request"
    assert exit_code == ValidationExitCode.INVALID_USAGE
