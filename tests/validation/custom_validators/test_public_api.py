"""Unit tests for PublicApiValidator (Phase 7.9 - Block 2)."""

from __future__ import annotations

from pathlib import Path
import pytest

from cmm.validation.context import ValidationContext
from cmm.validation.custom_validators.public_api import PublicApiValidator
from cmm.validation.enums import ValidationStatus


def test_public_api_valid(tmp_path: Path) -> None:
    cmm_dir = tmp_path / "cmm"
    cmm_dir.mkdir()
    (cmm_dir / "__init__.py").write_text(
        '__version__ = "0.1.0"\n__all__ = ["__version__"]\n', encoding="utf-8"
    )

    val_dir = cmm_dir / "validation"
    val_dir.mkdir()
    (val_dir / "__init__.py").write_text(
        "from .sub import InternalName as PublicAlias\n"
        "class LocalClass: pass\n"
        '__all__ = ["PublicAlias", "LocalClass"]\n',
        encoding="utf-8",
    )

    context = ValidationContext(project_root=tmp_path)
    validator = PublicApiValidator()

    assert validator.name == "public_api"
    result = validator.validate(context)

    assert result.status == ValidationStatus.PASSED
    assert len(result.findings) == 0
    assert len(result.artifacts) == 1
    art = result.artifacts[0]
    assert art.kind == "public_api_report"
    assert art.content["valid"] is True


def test_public_api_scope_limiting(tmp_path: Path) -> None:
    cmm_dir = tmp_path / "cmm"
    cmm_dir.mkdir()
    (cmm_dir / "__init__.py").write_text(
        '__all__ = ["__version__"]\n__version__ = "0.1.0"\n', encoding="utf-8"
    )

    val_dir = cmm_dir / "validation"
    val_dir.mkdir()
    (val_dir / "__init__.py").write_text(
        '__all__ = ["ValidationContext"]\nclass ValidationContext: pass\n',
        encoding="utf-8",
    )

    # Internal package without __all__
    internal_dir = cmm_dir / "internal_pkg"
    internal_dir.mkdir()
    (internal_dir / "__init__.py").write_text(
        "x = 1\n# No __all__ defined\n", encoding="utf-8"
    )

    # Public package with __all__
    public_pkg_dir = cmm_dir / "public_pkg"
    public_pkg_dir.mkdir()
    (public_pkg_dir / "__init__.py").write_text(
        'class Feature: pass\n__all__ = ["Feature"]\n', encoding="utf-8"
    )

    context = ValidationContext(project_root=tmp_path)
    validator = PublicApiValidator()
    result = validator.validate(context)

    assert result.status == ValidationStatus.PASSED
    scanned = result.artifacts[0].content["scanned_modules"]
    assert "cmm/__init__.py" in scanned
    assert "cmm/validation/__init__.py" in scanned
    assert "cmm/public_pkg/__init__.py" in scanned
    assert "cmm/internal_pkg/__init__.py" not in scanned


def test_public_api_all_not_literal(tmp_path: Path) -> None:
    cmm_dir = tmp_path / "cmm"
    cmm_dir.mkdir()
    (cmm_dir / "__init__.py").write_text(
        'symbols = ["a", "b"]\n__all__ = symbols\n', encoding="utf-8"
    )

    context = ValidationContext(project_root=tmp_path)
    validator = PublicApiValidator()
    result = validator.validate(context)

    assert result.status == ValidationStatus.FAILED
    assert any(f.code == "PUBLIC_API_ALL_NOT_LITERAL" for f in result.findings)


def test_public_api_all_multiple_assignments(tmp_path: Path) -> None:
    cmm_dir = tmp_path / "cmm"
    cmm_dir.mkdir()
    (cmm_dir / "__init__.py").write_text(
        '__all__ = ["a"]\n__all__ = ["b"]\nclass a: pass\nclass b: pass\n',
        encoding="utf-8",
    )

    context = ValidationContext(project_root=tmp_path)
    validator = PublicApiValidator()
    result = validator.validate(context)

    assert result.status == ValidationStatus.FAILED
    assert any(f.code == "PUBLIC_API_ALL_MULTIPLE_ASSIGNMENTS" for f in result.findings)


def test_public_api_duplicate_export(tmp_path: Path) -> None:
    cmm_dir = tmp_path / "cmm"
    cmm_dir.mkdir()
    (cmm_dir / "__init__.py").write_text(
        'class Foo: pass\n__all__ = ["Foo", "Foo"]\n', encoding="utf-8"
    )

    context = ValidationContext(project_root=tmp_path)
    validator = PublicApiValidator()
    result = validator.validate(context)

    assert result.status == ValidationStatus.FAILED
    assert any(f.code == "PUBLIC_API_DUPLICATE_EXPORT" for f in result.findings)


def test_public_api_private_export(tmp_path: Path) -> None:
    cmm_dir = tmp_path / "cmm"
    cmm_dir.mkdir()
    (cmm_dir / "__init__.py").write_text(
        'class _PrivateFoo: pass\n__all__ = ["_PrivateFoo"]\n', encoding="utf-8"
    )

    context = ValidationContext(project_root=tmp_path)
    validator = PublicApiValidator()
    result = validator.validate(context)

    assert result.status == ValidationStatus.FAILED
    assert any(f.code == "PUBLIC_API_PRIVATE_EXPORT" for f in result.findings)


def test_public_api_unresolved_export(tmp_path: Path) -> None:
    cmm_dir = tmp_path / "cmm"
    cmm_dir.mkdir()
    (cmm_dir / "__init__.py").write_text(
        '__all__ = ["NonExistentSymbol"]\n', encoding="utf-8"
    )

    context = ValidationContext(project_root=tmp_path)
    validator = PublicApiValidator()
    result = validator.validate(context)

    assert result.status == ValidationStatus.FAILED
    assert any(f.code == "PUBLIC_API_UNRESOLVED_EXPORT" for f in result.findings)


def test_public_api_syntax_error_sanitized(tmp_path: Path) -> None:
    cmm_dir = tmp_path / "cmm"
    cmm_dir.mkdir()
    (cmm_dir / "__init__.py").write_text("invalid python code !!!", encoding="utf-8")

    context = ValidationContext(project_root=tmp_path)
    validator = PublicApiValidator()
    result = validator.validate(context)

    assert result.status == ValidationStatus.FAILED
    syntax_finding = next(
        f for f in result.findings if f.code == "PUBLIC_API_SYNTAX_ERROR"
    )
    assert "line" in syntax_finding.metadata
    assert "column" in syntax_finding.metadata
    assert "invalid python code" not in syntax_finding.message
    assert "invalid python code" not in str(syntax_finding.metadata)


def test_public_api_serialization(tmp_path: Path) -> None:
    cmm_dir = tmp_path / "cmm"
    cmm_dir.mkdir()
    (cmm_dir / "__init__.py").write_text(
        'class Foo: pass\n__all__ = ["Foo"]\n', encoding="utf-8"
    )

    context = ValidationContext(project_root=tmp_path)
    validator = PublicApiValidator()
    result = validator.validate(context)

    serialized = result.serialize()
    assert serialized["name"] == "custom.public_api"
    assert serialized["artifacts"][0]["kind"] == "public_api_report"
