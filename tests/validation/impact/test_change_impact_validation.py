from __future__ import annotations

from pathlib import Path

from cmm.validation.context import ValidationContext
from cmm.validation.executor import ValidationExecutor
from cmm.validation.pipeline import ValidationPipeline
from cmm.validation.registry import ValidationRegistry
from cmm.validation.testing_defaults import default_validation_steps
from cmm.validation.catalog import build_default_validation_registry


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_change_impact_step_is_in_default_validation_steps(tmp_path: Path) -> None:
    from cmm.validation.catalog import change_impact_step

    _write(tmp_path / "pkg" / "module.py", "def func(x):\n    return x\n")
    context = ValidationContext(project_root=tmp_path, changed_files=(Path("pkg/module.py"),))

    step = change_impact_step(context)

    assert step is not None
    assert step.name == "change_impact"
    assert step.step_type.value == "internal"
    assert step.metadata["changed_files"] == ["pkg/module.py"]


def test_change_impact_runs_through_validation_pipeline(tmp_path: Path) -> None:
    _write(tmp_path / "pkg" / "module.py", "def func(x):\n    return x\n")
    _write(tmp_path / "tests" / "test_module.py", "def test_func():\n    assert True\n")
    context = ValidationContext(project_root=tmp_path, changed_files=(Path("pkg/module.py"),))

    pipeline = ValidationPipeline(executor=ValidationExecutor(), registry=build_default_validation_registry())
    result = pipeline.run(context, default_validation_steps(context))

    assert result.status.value in {"passed", "warning"}
    assert any(step.name == "change_impact" for step in result.steps)
    assert result.affected_tests == ("tests/test_module.py",)
