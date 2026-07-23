from __future__ import annotations

from pathlib import Path

from cmm.validation import ValidationExecutor, ValidationPipeline
from cmm.validation.catalog import build_default_validation_registry
from cmm.validation.context import ValidationContext
from cmm.validation.testing_defaults import default_validation_steps


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_static_analysis_pipeline_e2e_reports_warnings(tmp_path: Path) -> None:
    _write(
        tmp_path / "pkg" / "module.py",
        "def uses_missing(x):\n    return missing(x)\n\n\ndef dead():\n    return 1\n",
    )

    context = ValidationContext(project_root=tmp_path, changed_files=(Path("pkg/module.py"),))
    pipeline = ValidationPipeline(executor=ValidationExecutor(), registry=build_default_validation_registry())

    result = pipeline.run(context, default_validation_steps(context))

    assert result.status.value in {"passed", "warning"}
    assert any(step.name == "change_impact" for step in result.steps)
    assert any(step.name == "type_check" for step in result.steps)
    assert any(step.name == "dead_code" for step in result.steps)
    assert any(step.status.value == "warning" for step in result.steps if step.name in {"type_check", "dead_code"})
    assert any(artifact.kind in {"type_check_report", "dead_code_report"} for artifact in result.artifacts)
