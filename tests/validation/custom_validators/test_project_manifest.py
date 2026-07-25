"""Unit tests for ProjectManifestValidator (Phase 7.9 - Block 2)."""

from __future__ import annotations

from pathlib import Path
import pytest

from cmm.validation.context import ValidationContext
from cmm.validation.custom_validators.manifest import ProjectManifestValidator
from cmm.validation.enums import ValidationStatus, ValidationSeverity


def test_project_manifest_valid(tmp_path: Path) -> None:
    manifest = tmp_path / "pyproject.toml"
    manifest.write_text(
        """[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "cmm-os"
version = "0.1.0"
requires-python = ">=3.10"

[project.optional-dependencies]
validation = ["bandit>=1.7", "pip-audit>=2.7", "mypy>=1.10", "vulture>=2.14"]
dev = ["pytest>=9", "bandit>=1.7", "pip-audit>=2.7", "mypy>=1.10", "vulture>=2.14"]

[project.scripts]
cmm = "cmm.cli:main"
""",
        encoding="utf-8",
    )

    context = ValidationContext(project_root=tmp_path)
    validator = ProjectManifestValidator()

    assert validator.name == "project_manifest"
    result = validator.validate(context)

    assert result.status == ValidationStatus.PASSED
    assert len(result.findings) == 0
    assert len(result.artifacts) == 1
    art = result.artifacts[0]
    assert art.kind == "project_manifest_report"
    assert art.content["valid"] is True
    assert art.content["project_name"] == "cmm-os"
    assert art.content["version"] == "0.1.0"
    assert art.content["requires_python"] == ">=3.10"
    assert result.metadata["custom_validator"] is True
    assert result.metadata["validator_name"] == "project_manifest"


def test_project_manifest_missing(tmp_path: Path) -> None:
    context = ValidationContext(project_root=tmp_path)
    validator = ProjectManifestValidator()
    result = validator.validate(context)

    assert result.status == ValidationStatus.FAILED
    assert any(f.code == "PROJECT_MANIFEST_MISSING" for f in result.findings)
    assert result.artifacts[0].content["valid"] is False


def test_project_manifest_invalid_toml(tmp_path: Path) -> None:
    manifest = tmp_path / "pyproject.toml"
    manifest.write_text("invalid [toml == content", encoding="utf-8")

    context = ValidationContext(project_root=tmp_path)
    validator = ProjectManifestValidator()
    result = validator.validate(context)

    assert result.status == ValidationStatus.FAILED
    assert any(f.code == "PROJECT_MANIFEST_INVALID_TOML" for f in result.findings)


def test_project_manifest_missing_project_section(tmp_path: Path) -> None:
    manifest = tmp_path / "pyproject.toml"
    manifest.write_text("[build-system]\nrequires = []\n", encoding="utf-8")

    context = ValidationContext(project_root=tmp_path)
    validator = ProjectManifestValidator()
    result = validator.validate(context)

    assert result.status == ValidationStatus.FAILED
    assert any(
        f.code == "PROJECT_MANIFEST_PROJECT_SECTION_MISSING" for f in result.findings
    )


def test_project_manifest_missing_name_version(tmp_path: Path) -> None:
    manifest = tmp_path / "pyproject.toml"
    manifest.write_text(
        """[build-system]
requires = ["setuptools"]

[project]
description = "No name or version"
""",
        encoding="utf-8",
    )

    context = ValidationContext(project_root=tmp_path)
    validator = ProjectManifestValidator()
    result = validator.validate(context)

    assert result.status == ValidationStatus.FAILED
    codes = {f.code for f in result.findings}
    assert "PROJECT_MANIFEST_NAME_MISSING" in codes
    assert "PROJECT_MANIFEST_VERSION_MISSING" in codes


def test_project_manifest_missing_entry_point(tmp_path: Path) -> None:
    manifest = tmp_path / "pyproject.toml"
    manifest.write_text(
        """[build-system]
requires = ["setuptools"]

[project]
name = "cmm-os"
version = "0.1.0"
""",
        encoding="utf-8",
    )

    context = ValidationContext(project_root=tmp_path)
    validator = ProjectManifestValidator()
    result = validator.validate(context)

    assert result.status == ValidationStatus.FAILED
    assert any(
        f.code == "PROJECT_MANIFEST_ENTRY_POINT_MISSING" for f in result.findings
    )


def test_project_manifest_invalid_entry_point(tmp_path: Path) -> None:
    manifest = tmp_path / "pyproject.toml"
    manifest.write_text(
        """[build-system]
requires = ["setuptools"]

[project]
name = "cmm-os"
version = "0.1.0"
requires-python = ">=3.10"

[project.scripts]
cmm = "cmm.cli:wrong_main"
""",
        encoding="utf-8",
    )

    context = ValidationContext(project_root=tmp_path)
    validator = ProjectManifestValidator()
    result = validator.validate(context)

    assert result.status == ValidationStatus.FAILED
    assert any(
        f.code == "PROJECT_MANIFEST_ENTRY_POINT_INVALID" for f in result.findings
    )


def test_project_manifest_missing_dev_and_val_dependencies(tmp_path: Path) -> None:
    manifest = tmp_path / "pyproject.toml"
    manifest.write_text(
        """[build-system]
requires = ["setuptools"]

[project]
name = "cmm-os"
version = "0.1.0"
requires-python = ">=3.10"

[project.scripts]
cmm = "cmm.cli:main"

[project.optional-dependencies]
dev = ["pytest"]
validation = ["bandit"]
""",
        encoding="utf-8",
    )

    context = ValidationContext(project_root=tmp_path)
    validator = ProjectManifestValidator()
    result = validator.validate(context)

    # Missing tools in dev and validation generate WARNING findings
    assert result.status == ValidationStatus.WARNING
    codes = {f.code for f in result.findings}
    assert "PROJECT_MANIFEST_DEV_DEPENDENCY_MISSING" in codes
    assert "PROJECT_MANIFEST_VALIDATION_DEPENDENCY_MISSING" in codes


def test_project_manifest_duplicate_dependency(tmp_path: Path) -> None:
    manifest = tmp_path / "pyproject.toml"
    manifest.write_text(
        """[build-system]
requires = ["setuptools"]

[project]
name = "cmm-os"
version = "0.1.0"
requires-python = ">=3.10"

[project.scripts]
cmm = "cmm.cli:main"

[project.optional-dependencies]
dev = ["pytest>=9", "pytest>=9", "mypy>=1.10", "vulture>=2.14"]
validation = ["bandit>=1.7", "pip-audit>=2.7", "mypy>=1.10", "vulture>=2.14"]
""",
        encoding="utf-8",
    )

    context = ValidationContext(project_root=tmp_path)
    validator = ProjectManifestValidator()
    result = validator.validate(context)

    assert result.status == ValidationStatus.WARNING
    assert any(
        f.code == "PROJECT_MANIFEST_DUPLICATE_DEPENDENCY" for f in result.findings
    )


def test_project_manifest_artifact_serialization(tmp_path: Path) -> None:
    manifest = tmp_path / "pyproject.toml"
    manifest.write_text(
        """[build-system]
requires = ["setuptools"]
[project]
name = "cmm-os"
version = "0.1.0"
[project.scripts]
cmm = "cmm.cli:main"
""",
        encoding="utf-8",
    )

    context = ValidationContext(project_root=tmp_path)
    validator = ProjectManifestValidator()
    result = validator.validate(context)

    serialized = result.serialize()
    assert isinstance(serialized, dict)
    assert serialized["name"] == "custom.project_manifest"
    assert "artifacts" in serialized
    assert len(serialized["artifacts"]) == 1
    assert serialized["artifacts"][0]["kind"] == "project_manifest_report"
