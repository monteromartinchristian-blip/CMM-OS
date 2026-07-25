"""Unit tests for Validation CLI handlers and commands (Phase 7.12)."""

from __future__ import annotations

import argparse
from pathlib import Path

import pytest

from cmm.validation import ValidationExitCode
from cmm.validation.cli import handle_validation_cli, register_validation_cli


def _build_test_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="cmm")
    subparsers = parser.add_subparsers(dest="command", required=True)
    register_validation_cli(subparsers)
    return parser


def test_cli_help() -> None:
    parser = _build_test_parser()
    with pytest.raises(SystemExit) as exc_info:
        parser.parse_args(["validation", "run", "--help"])
    assert exc_info.value.code == 0


def test_cli_run_human(tmp_path: Path, capsys) -> None:
    (tmp_path / "cmm").mkdir()
    (tmp_path / "cmm" / "__init__.py").write_text("# init")

    parser = _build_test_parser()
    args = parser.parse_args(
        ["validation", "run", "--policy", "small_change", "--project", str(tmp_path)]
    )

    exit_code = handle_validation_cli(args)
    assert exit_code in (
        ValidationExitCode.SUCCESS,
        ValidationExitCode.VALIDATION_FAILED,
    )

    captured = capsys.readouterr()
    assert "Validation val-" in captured.out
    assert "Policy: small_change" in captured.out


def test_cli_inspect(tmp_path: Path, capsys) -> None:
    (tmp_path / "cmm").mkdir()
    (tmp_path / "cmm" / "__init__.py").write_text("# init")

    parser = _build_test_parser()

    # 1. Run first
    run_args = parser.parse_args(
        ["validation", "run", "--policy", "small_change", "--project", str(tmp_path)]
    )
    handle_validation_cli(run_args)
    out1 = capsys.readouterr().out
    vid = out1.splitlines()[0].split()[1]

    # 2. Inspect
    inspect_args = parser.parse_args(
        ["validation", "inspect", vid, "--project", str(tmp_path)]
    )
    exit_code = handle_validation_cli(inspect_args)
    assert exit_code == ValidationExitCode.SUCCESS

    captured = capsys.readouterr()
    assert f"Validation {vid}" in captured.out


def test_cli_artifacts(tmp_path: Path, capsys) -> None:
    (tmp_path / "cmm").mkdir()
    (tmp_path / "cmm" / "__init__.py").write_text("# init")

    parser = _build_test_parser()
    run_args = parser.parse_args(["validation", "run", "--project", str(tmp_path)])
    handle_validation_cli(run_args)
    out1 = capsys.readouterr().out
    vid = out1.splitlines()[0].split()[1]

    art_args = parser.parse_args(
        ["validation", "artifacts", vid, "--project", str(tmp_path)]
    )
    exit_code = handle_validation_cli(art_args)
    assert exit_code == ValidationExitCode.SUCCESS

    captured = capsys.readouterr()
    assert "Artifacts" in captured.out


def test_cli_gate(tmp_path: Path, capsys) -> None:
    (tmp_path / "cmm").mkdir()
    (tmp_path / "cmm" / "__init__.py").write_text("# init")

    parser = _build_test_parser()
    run_args = parser.parse_args(
        ["validation", "run", "--policy", "small_change", "--project", str(tmp_path)]
    )
    handle_validation_cli(run_args)
    out1 = capsys.readouterr().out
    vid = out1.splitlines()[0].split()[1]

    gate_args = parser.parse_args(
        ["validation", "gate", vid, "--project", str(tmp_path)]
    )
    exit_code = handle_validation_cli(gate_args)
    assert exit_code in (
        ValidationExitCode.SUCCESS,
        ValidationExitCode.VALIDATION_FAILED,
    )

    captured = capsys.readouterr()
    assert "Validation Gate:" in captured.out


def test_cli_inspect_not_found(tmp_path: Path, capsys) -> None:
    parser = _build_test_parser()
    args = parser.parse_args(
        ["validation", "inspect", "val-non-existent-999", "--project", str(tmp_path)]
    )

    exit_code = handle_validation_cli(args)
    assert exit_code == ValidationExitCode.NOT_FOUND

    captured = capsys.readouterr()
    assert "Error: [validation_not_found]" in captured.err
