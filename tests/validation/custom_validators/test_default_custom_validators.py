"""Integration and default catalog tests for CMM OS custom validators (Phase 7.9 - Block 2)."""

from __future__ import annotations

from pathlib import Path
import pytest

from cmm.validation.context import ValidationContext
from cmm.validation.custom import (
    CustomValidator,
    CustomValidatorRegistry,
    build_custom_validation_step,
)
from cmm.validation.custom_validators import (
    ProjectManifestValidator,
    ValidationContractValidator,
    PublicApiValidator,
    TestLayoutValidator,
    build_default_custom_validator_registry,
    default_custom_validators,
)
from cmm.validation.enums import ValidationStatus
from cmm.validation.executor import ValidationExecutor
from cmm.validation.pipeline import ValidationPipeline
from cmm.validation.registry import ValidationRegistry
from cmm.validation.steps import ValidationStepResult


def test_default_custom_validators_instantiation() -> None:
    validators = default_custom_validators()
    assert len(validators) == 4

    names = [v.name for v in validators]
    assert names == [
        "project_manifest",
        "validation_contract",
        "public_api",
        "test_layout",
    ]
    assert len(set(names)) == 4

    for v in validators:
        assert isinstance(v, CustomValidator)

    # Independent instances per call
    v2 = default_custom_validators()
    assert len(v2) == 4
    for i in range(4):
        assert validators[i] is not v2[i]
        assert validators[i].name == v2[i].name


def test_build_default_custom_validator_registry() -> None:
    custom_reg = build_default_custom_validator_registry()
    assert isinstance(custom_reg, CustomValidatorRegistry)
    assert len(custom_reg) == 4
    assert set(custom_reg.names()) == {
        "project_manifest",
        "validation_contract",
        "public_api",
        "test_layout",
    }


def test_custom_validators_pipeline_e2e_integration(tmp_path: Path) -> None:
    # Build a minimum valid temporary project structure
    manifest = tmp_path / "pyproject.toml"
    manifest.write_text(
        """[build-system]
requires = ["setuptools"]
[project]
name = "cmm-os"
version = "0.1.0"
requires-python = ">=3.10"
[project.optional-dependencies]
dev = ["pytest>=9", "bandit>=1.7", "pip-audit>=2.7", "mypy>=1.10", "vulture>=2.14"]
validation = ["bandit>=1.7", "pip-audit>=2.7", "mypy>=1.10", "vulture>=2.14"]
[project.scripts]
cmm = "cmm.cli:main"
""",
        encoding="utf-8",
    )

    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_main.py").write_text(
        "def test_ok(): assert True\n", encoding="utf-8"
    )

    cmm_dir = tmp_path / "cmm"
    cmm_dir.mkdir()
    (cmm_dir / "__init__.py").write_text(
        '__all__ = ["__version__"]\n__version__ = "0.1.0"\n', encoding="utf-8"
    )

    val_dir = cmm_dir / "validation"
    val_dir.mkdir()
    for f in (
        "__init__.py",
        "custom.py",
        "pipeline.py",
        "registry.py",
        "steps.py",
        "results.py",
        "context.py",
        "enums.py",
        "findings.py",
        "artifacts.py",
    ):
        (val_dir / f).write_text("class Dummy: pass\n", encoding="utf-8")

    (val_dir / "custom.py").write_text(
        "class CustomValidator: pass\n"
        "class CustomValidatorRegistry: pass\n"
        "def build_custom_validation_step(): pass\n",
        encoding="utf-8",
    )

    init_content = """
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
    "ValidationContext", "ValidationStep", "ValidationStepResult",
    "ValidationPipeline", "ValidationRegistry", "ValidationExecutor",
    "ValidationFinding", "ValidationArtifact", "ValidationStatus",
    "ValidationSeverity", "CustomValidator", "CustomValidatorRegistry",
    "build_custom_validation_step"
]
"""
    (val_dir / "__init__.py").write_text(init_content, encoding="utf-8")

    custom_registry = build_default_custom_validator_registry()
    val_registry = ValidationRegistry()

    steps = custom_registry.build_steps(
        custom_registry.names(),
        validation_registry=val_registry,
    )

    assert len(steps) == 4
    step_names = [s.name for s in steps]
    assert step_names == [
        "custom.project_manifest",
        "custom.validation_contract",
        "custom.public_api",
        "custom.test_layout",
    ]

    pipeline = ValidationPipeline(
        executor=ValidationExecutor(),
        registry=val_registry,
    )
    context = ValidationContext(project_root=tmp_path)
    result = pipeline.run(context, steps)

    assert result.status == ValidationStatus.PASSED
    assert len(result.steps) == 4
    for sr in result.steps:
        assert sr.status == ValidationStatus.PASSED
        assert len(sr.artifacts) == 1

    serialized = result.serialize()
    assert isinstance(serialized, dict)
    assert serialized["status"] == "passed"
    assert len(serialized["steps"]) == 4


def test_exception_in_custom_validator_handled_gracefully(tmp_path: Path) -> None:
    class FailingValidator(CustomValidator):
        name = "failing_val"

        def validate(self, context: ValidationContext) -> ValidationStepResult:
            raise RuntimeError("Unexpected failure")

    custom_reg = CustomValidatorRegistry()
    custom_reg.register(FailingValidator())
    val_reg = ValidationRegistry()

    steps = custom_reg.build_steps(["failing_val"], validation_registry=val_reg)
    pipeline = ValidationPipeline(executor=ValidationExecutor(), registry=val_reg)

    context = ValidationContext(project_root=tmp_path)
    res = pipeline.run(context, steps)

    assert res.status == ValidationStatus.ERROR
    assert len(res.steps) == 1
    sr = res.steps[0]
    assert sr.status == ValidationStatus.ERROR
    assert "failing_val" in sr.stderr
