"""Security and isolation tests for Validation CLI (Phase 7.12)."""

from __future__ import annotations

import argparse
from pathlib import Path

from cmm.validation import ValidationExitCode
from cmm.validation.cli import handle_validation_cli, register_validation_cli


def _build_test_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="cmm")
    subparsers = parser.add_subparsers(dest="command", required=True)
    register_validation_cli(subparsers)
    return parser


def test_cli_path_traversal_blocked(tmp_path: Path, capsys) -> None:
    parser = _build_test_parser()
    bad_path = "../../etc/passwd"
    args = parser.parse_args(
        [
            "validation",
            "run",
            "--files",
            bad_path,
            "--output",
            "json",
            "--project",
            str(tmp_path),
        ]
    )

    exit_code = handle_validation_cli(args)
    captured = capsys.readouterr()

    import json

    parsed = json.loads(captured.out)
    assert parsed["success"] is False
    assert parsed["exit_code"] == ValidationExitCode.INVALID_USAGE
    assert "traversal" in parsed["error"]["message"].lower()
    assert exit_code == ValidationExitCode.INVALID_USAGE


def test_cli_invalid_step_name_blocked(tmp_path: Path, capsys) -> None:
    parser = _build_test_parser()
    malicious_step = "lint; rm -rf /"
    args = parser.parse_args(
        [
            "validation",
            "run",
            "--step",
            malicious_step,
            "--output",
            "json",
            "--project",
            str(tmp_path),
        ]
    )

    exit_code = handle_validation_cli(args)
    captured = capsys.readouterr()

    import json

    parsed = json.loads(captured.out)
    assert parsed["success"] is False
    assert parsed["exit_code"] == ValidationExitCode.CONFIGURATION_ERROR
    assert parsed["error"]["code"] == "validation_step_not_found"
    assert exit_code == ValidationExitCode.CONFIGURATION_ERROR


def test_cli_inspect_path_traversal_id_blocked(tmp_path: Path, capsys) -> None:
    parser = _build_test_parser()
    bad_id = "../../../etc/passwd"
    args = parser.parse_args(
        [
            "validation",
            "inspect",
            bad_id,
            "--output",
            "json",
            "--project",
            str(tmp_path),
        ]
    )

    exit_code = handle_validation_cli(args)
    assert exit_code in (
        ValidationExitCode.NOT_FOUND,
        ValidationExitCode.INTERNAL_ERROR,
        ValidationExitCode.INVALID_USAGE,
    )
