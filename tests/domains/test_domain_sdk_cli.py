"""Phase 10.35 — Tests for Domain SDK CLI."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

from cmm.domains.enums import DomainValidationStatus
from cmm.domains.registry import DomainRegistry
from cmm.domains.sdk.cli import validate_domain_path
from cmm.domains.sdk.scaffold import DomainScaffolder


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


def test_validate_domain_path_canonical_success(tmp_path: Path) -> None:
    pack_root = tmp_path / "valid-pack"
    DomainScaffolder().create("valid-pack", destination=pack_root)

    result = validate_domain_path(pack_root)
    assert result.status in (DomainValidationStatus.PASSED, DomainValidationStatus.WARNING)
    assert result.manifest_valid is True
    assert result.compatibility_valid is True
    assert result.security_valid is True
    assert result.fragmentation_valid is True


def test_validate_domain_path_tampered_fails_canonically(tmp_path: Path) -> None:
    pack_root = tmp_path / "tampered-pack"
    DomainScaffolder().create("tampered-pack", destination=pack_root)

    # Corrupt manifest with forbidden path traversal in fixtures
    manifest_path = pack_root / "manifest.json"
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    data["fixtures"] = [{"id": "escape", "path": "../outside.json"}]
    manifest_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    result = validate_domain_path(pack_root)
    assert result.status in (DomainValidationStatus.FAILED, DomainValidationStatus.ERROR)
    assert result.manifest_valid is False or not all(
        (result.security_valid, result.manifest_valid, result.contracts_valid)
    )


def test_cli_domain_validate_success(tmp_path: Path) -> None:
    pack_root = tmp_path / "validate-sample"
    DomainScaffolder().create("validate-sample", destination=pack_root)

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "cmm",
            "domain",
            "validate",
            str(pack_root),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, f"Validation failed:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    assert "domain:validate-sample" in result.stdout or "validate-sample" in result.stdout


def test_cli_domain_validate_failure(tmp_path: Path) -> None:
    pack_root = tmp_path / "broken-pack"
    DomainScaffolder().create("broken-pack", destination=pack_root)

    manifest_path = pack_root / "manifest.json"
    manifest_path.write_text("{invalid json", encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "cmm",
            "domain",
            "validate",
            str(pack_root),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0
    assert "Traceback" not in result.stderr


def test_cli_domain_validate_does_not_mutate_registry(tmp_path: Path) -> None:
    pack_root = tmp_path / "registry-check"
    DomainScaffolder().create("registry-check", destination=pack_root)

    registry = DomainRegistry()
    snapshot_before = registry.snapshot_state()

    result = validate_domain_path(pack_root)
    assert result.status in (DomainValidationStatus.PASSED, DomainValidationStatus.WARNING)

    snapshot_after = registry.snapshot_state()
    assert snapshot_before == snapshot_after


def test_cli_domain_test_success(tmp_path: Path) -> None:
    pack_root = tmp_path / "test-sample"
    DomainScaffolder().create("test-sample", destination=pack_root)

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "cmm",
            "domain",
            "test",
            str(pack_root),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, f"Test command failed:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"


def test_cli_domain_test_validation_failure_blocks_test(tmp_path: Path) -> None:
    pack_root = tmp_path / "blocked-test-pack"
    DomainScaffolder().create("blocked-test-pack", destination=pack_root)

    # Corrupt manifest
    manifest_path = pack_root / "manifest.json"
    manifest_path.write_text("{invalid json", encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "cmm",
            "domain",
            "test",
            str(pack_root),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0
    assert "Traceback" not in result.stderr


def test_cli_domain_test_failing_test_returns_nonzero(tmp_path: Path) -> None:
    pack_root = tmp_path / "failing-test-pack"
    DomainScaffolder().create("failing-test-pack", destination=pack_root)

    # Add a failing test
    test_file = pack_root / "tests" / "test_domain.py"
    test_file.write_text(
        "def test_failure():\n    assert False, 'intentional failure'\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "cmm",
            "domain",
            "test",
            str(pack_root),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0


def test_cli_domain_test_missing_tests_dir_fails(tmp_path: Path) -> None:
    pack_root = tmp_path / "no-tests-pack"
    DomainScaffolder().create("no-tests-pack", destination=pack_root)

    # Remove tests directory
    shutil.rmtree(pack_root / "tests")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "cmm",
            "domain",
            "test",
            str(pack_root),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0
    assert "Traceback" not in result.stderr


def test_cli_domain_test_path_with_spaces(tmp_path: Path) -> None:
    pack_root = tmp_path / "pack with spaces"
    DomainScaffolder().create("spaces-pack", destination=pack_root)

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "cmm",
            "domain",
            "test",
            str(pack_root),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, f"Test with spaces failed:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"


def test_cli_domain_pack_success(tmp_path: Path) -> None:
    pack_root = tmp_path / "pack-target"
    DomainScaffolder().create("pack-target", destination=pack_root)

    out_archive = tmp_path / "pack-target.tar.gz"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "cmm",
            "domain",
            "pack",
            str(pack_root),
            "--output",
            str(out_archive),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, f"Pack command failed:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    assert out_archive.is_file()


def test_cli_domain_pack_failure_on_invalid_pack(tmp_path: Path) -> None:
    pack_root = tmp_path / "broken-target"
    DomainScaffolder().create("broken-target", destination=pack_root)

    # Corrupt manifest
    (pack_root / "manifest.json").write_text("{invalid json", encoding="utf-8")

    out_archive = tmp_path / "broken-target.tar.gz"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "cmm",
            "domain",
            "pack",
            str(pack_root),
            "--output",
            str(out_archive),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0
    assert not out_archive.exists()
    assert "Traceback" not in result.stderr
