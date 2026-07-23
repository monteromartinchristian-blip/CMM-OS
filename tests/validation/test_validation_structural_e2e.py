from __future__ import annotations

import sys
from pathlib import Path

from cmm.validation import ValidationExecutor, ValidationPipeline, ValidationRegistry
from cmm.validation.catalog import build_default_validation_registry, default_structural_steps
from cmm.validation.context import ValidationContext
from cmm.validation.steps import ValidationStep, ValidationStepType
from cmm.validation.enums import ValidationStatus


def test_pipeline_e2e_default_structural_steps(tmp_path: Path):
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "good.py").write_text("print('ok')\n", encoding="utf-8")
    ctx = ValidationContext(project_root=tmp_path)
    pipeline = ValidationPipeline(executor=ValidationExecutor(), registry=build_default_validation_registry())
    result = pipeline.run(ctx, default_structural_steps(ctx))
    assert result.status == ValidationStatus.ERROR
    assert any(step.name == "formatter_check" and step.status == ValidationStatus.ERROR for step in result.steps)


def test_pipeline_e2e_syntax_failure(tmp_path: Path):
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "bad.py").write_text("def broken(:\n    pass\n", encoding="utf-8")
    ctx = ValidationContext(project_root=tmp_path, changed_files=(Path("pkg/bad.py"),))
    pipeline = ValidationPipeline(executor=ValidationExecutor(), registry=build_default_validation_registry())
    result = pipeline.run(ctx, default_structural_steps(ctx))
    assert result.status == ValidationStatus.FAILED
    assert any(step.name == "syntax" and step.status == ValidationStatus.FAILED for step in result.steps)
