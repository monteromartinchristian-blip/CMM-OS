"""Phase 10.35 — Tests for Domain SDK CLI."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_cli_domain_create_success(tmp_path: Path) -> None:
    dest = tmp_path / "cli-sample"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "cmm",
            "domain",
            "create",
            "cli-sample",
            "--destination",
            str(dest),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, f"CLI create failed:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    assert (dest / "manifest.json").is_file()
    assert (dest / "README.md").is_file()
    assert (dest / "fixtures" / "sample.json").is_file()
    assert (dest / "tests" / "test_domain.py").is_file()


def test_cli_domain_create_invalid_name_fails(tmp_path: Path) -> None:
    dest = tmp_path / "invalid-dest"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "cmm",
            "domain",
            "create",
            "INVALID_NAME_WITH_CAPS",
            "--destination",
            str(dest),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0
    # Expected developer errors should not print Python tracebacks by default
    assert "Traceback" not in result.stderr


def test_cli_domain_create_existing_destination_fails(tmp_path: Path) -> None:
    dest = tmp_path / "existing-dir"
    dest.mkdir()
    (dest / "file.txt").write_text("hello", encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "cmm",
            "domain",
            "create",
            "valid-slug",
            "--destination",
            str(dest),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0
    assert "Traceback" not in result.stderr
