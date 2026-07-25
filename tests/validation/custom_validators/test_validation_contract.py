"""Unit tests for ValidationContractValidator (Phase 7.9 - Block 2)."""

from __future__ import annotations

from pathlib import Path
import pytest

from cmm.validation.context import ValidationContext
from cmm.validation.custom_validators.contracts import (
    REQUIRED_EXPORTS,
    REQUIRED_VALIDATION_MODULES,
    ValidationContractValidator,
)
from cmm.validation.enums import ValidationStatus


def _create_mock_validation_structure(root: Path) -> Path:
    val_dir = root / "cmm" / "validation"
    val_dir.mkdir(parents=True, exist_ok=True)

    for mod in REQUIRED_VALIDATION_MODULES:
        if mod != "__init__.py":
            (val_dir / mod).write_text(
                "class Dummy:\n    pass\n\ndef dummy_func():\n    pass\n",
                encoding="utf-8",
            )

    (val_dir / "custom.py").write_text(
        "class CustomValidator:\n    pass\n"
        "class CustomValidatorRegistry:\n    pass\n"
        "def build_custom_validation_step():\n    pass\n",
        encoding="utf-8",
    )

    exports_str = ",\n    ".join(f'"{exp}"' for exp in REQUIRED_EXPORTS)
    init_content = f"""
from .custom import CustomValidator, CustomValidatorRegistry, build_custom_validation_step

class ValidationContext: pass
class ValidationStep: pass
class ValidationStepResult: pass
class ValidationPipeline: pass
class ValidationRegistry: pass
class ValidationExecutor: pass
class ValidationFinding: pass
class ValidationArtifact: pass
class ValidationStatus: pass
class ValidationSeverity: pass

__all__ = [
    {exports_str}
]
"""
    (val_dir / "__init__.py").write_text(init_content, encoding="utf-8")
    return val_dir


def test_validation_contract_valid(tmp_path: Path) -> None:
    _create_mock_validation_structure(tmp_path)
    context = ValidationContext(project_root=tmp_path)
    validator = ValidationContractValidator()

    assert validator.name == "validation_contract"
    result = validator.validate(context)

    assert result.status == ValidationStatus.PASSED
    assert len(result.findings) == 0
    assert len(result.artifacts) == 1
    art = result.artifacts[0]
    assert art.kind == "validation_contract_report"
    assert art.content["valid"] is True
    assert len(art.content["missing_modules"]) == 0
    assert len(art.content["missing_exports"]) == 0


def test_validation_contract_missing_module(tmp_path: Path) -> None:
    _create_mock_validation_structure(tmp_path)
    (tmp_path / "cmm" / "validation" / "custom.py").unlink()

    context = ValidationContext(project_root=tmp_path)
    validator = ValidationContractValidator()
    result = validator.validate(context)

    assert result.status == ValidationStatus.FAILED
    assert any(f.code == "VALIDATION_MODULE_MISSING" for f in result.findings)


def test_validation_contract_syntax_error_sanitized(tmp_path: Path) -> None:
    _create_mock_validation_structure(tmp_path)
    (tmp_path / "cmm" / "validation" / "__init__.py").write_text(
        "invalid python syntax (", encoding="utf-8"
    )

    context = ValidationContext(project_root=tmp_path)
    validator = ValidationContractValidator()
    result = validator.validate(context)

    assert result.status == ValidationStatus.FAILED
    syntax_finding = next(
        f for f in result.findings if f.code == "VALIDATION_INIT_SYNTAX_ERROR"
    )
    assert "line" in syntax_finding.metadata
    assert "column" in syntax_finding.metadata
    assert "invalid python syntax" not in syntax_finding.message
    assert "invalid python syntax" not in str(syntax_finding.metadata)


def test_validation_contract_all_missing(tmp_path: Path) -> None:
    _create_mock_validation_structure(tmp_path)
    (tmp_path / "cmm" / "validation" / "__init__.py").write_text(
        "# No __all__ defined\n", encoding="utf-8"
    )

    context = ValidationContext(project_root=tmp_path)
    validator = ValidationContractValidator()
    result = validator.validate(context)

    assert result.status == ValidationStatus.FAILED
    assert any(f.code == "VALIDATION_ALL_MISSING" for f in result.findings)


def test_validation_contract_all_not_literal(tmp_path: Path) -> None:
    _create_mock_validation_structure(tmp_path)
    (tmp_path / "cmm" / "validation" / "__init__.py").write_text(
        'exports = ["ValidationContext"]\n__all__ = exports\n', encoding="utf-8"
    )

    context = ValidationContext(project_root=tmp_path)
    validator = ValidationContractValidator()
    result = validator.validate(context)

    assert result.status == ValidationStatus.FAILED
    assert any(f.code == "VALIDATION_ALL_NOT_LITERAL" for f in result.findings)


def test_validation_contract_all_invalid_item(tmp_path: Path) -> None:
    _create_mock_validation_structure(tmp_path)
    (tmp_path / "cmm" / "validation" / "__init__.py").write_text(
        '__all__ = ["ValidationContext", 123]\n', encoding="utf-8"
    )

    context = ValidationContext(project_root=tmp_path)
    validator = ValidationContractValidator()
    result = validator.validate(context)

    assert result.status == ValidationStatus.FAILED
    assert any(f.code == "VALIDATION_ALL_INVALID_ITEM" for f in result.findings)


def test_validation_contract_all_multiple_assignments(tmp_path: Path) -> None:
    _create_mock_validation_structure(tmp_path)
    (tmp_path / "cmm" / "validation" / "__init__.py").write_text(
        '__all__ = ["a"]\n__all__ = ["b"]\n', encoding="utf-8"
    )

    context = ValidationContext(project_root=tmp_path)
    validator = ValidationContractValidator()
    result = validator.validate(context)

    assert result.status == ValidationStatus.FAILED
    assert any(f.code == "VALIDATION_ALL_MULTIPLE_ASSIGNMENTS" for f in result.findings)


def test_validation_contract_relative_import_package_and_module(tmp_path: Path) -> None:
    _create_mock_validation_structure(tmp_path)
    val_dir = tmp_path / "cmm" / "validation"

    # Create nested package inside cmm/validation/
    pkg_dir = val_dir / "impact"
    pkg_dir.mkdir(parents=True, exist_ok=True)
    (pkg_dir / "__init__.py").write_text(
        "class ChangeImpactAnalyzer: pass\n", encoding="utf-8"
    )

    exports_str = ",\n    ".join(f'"{exp}"' for exp in REQUIRED_EXPORTS)
    init_content = f"""
from .custom import CustomValidator, CustomValidatorRegistry, build_custom_validation_step
from .impact import ChangeImpactAnalyzer

class ValidationContext: pass
class ValidationStep: pass
class ValidationStepResult: pass
class ValidationPipeline: pass
class ValidationRegistry: pass
class ValidationExecutor: pass
class ValidationFinding: pass
class ValidationArtifact: pass
class ValidationStatus: pass
class ValidationSeverity: pass

__all__ = [
    {exports_str},
    "ChangeImpactAnalyzer"
]
"""
    (val_dir / "__init__.py").write_text(init_content, encoding="utf-8")

    context = ValidationContext(project_root=tmp_path)
    validator = ValidationContractValidator()
    result = validator.validate(context)

    assert result.status == ValidationStatus.PASSED
    assert len(result.findings) == 0


def test_validation_contract_read_error_simulated(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _create_mock_validation_structure(tmp_path)
    init_file = tmp_path / "cmm" / "validation" / "__init__.py"

    def mock_read_text(*args, **kwargs):
        raise PermissionError("Access denied")

    monkeypatch.setattr(Path, "read_text", mock_read_text)

    context = ValidationContext(project_root=tmp_path)
    validator = ValidationContractValidator()
    result = validator.validate(context)

    assert result.status == ValidationStatus.FAILED
    assert any(f.code == "VALIDATION_INIT_READ_ERROR" for f in result.findings)


def test_validation_contract_serialization(tmp_path: Path) -> None:
    _create_mock_validation_structure(tmp_path)
    context = ValidationContext(project_root=tmp_path)
    validator = ValidationContractValidator()
    result = validator.validate(context)

    serialized = result.serialize()
    assert serialized["name"] == "custom.validation_contract"
    assert serialized["artifacts"][0]["kind"] == "validation_contract_report"
