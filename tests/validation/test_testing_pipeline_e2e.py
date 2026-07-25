from __future__ import annotations

from pathlib import Path

from cmm.validation.context import ValidationContext
from cmm.validation.enums import ValidationStatus
from cmm.validation.executor import ValidationExecutor
from cmm.validation.pipeline import ValidationPipeline
from cmm.validation.registry import ValidationRegistry
from cmm.validation.testing_catalog import default_testing_steps


def _write_test(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def test_pipeline_includes_affected_tests_in_result(tmp_path: Path) -> None:
    project_root = tmp_path
    _write_test(project_root / "tests" / "test_sample.py", "def test_sample():\n    assert True\n")

    context = ValidationContext(project_root=project_root, changed_files=(Path("tests/test_sample.py"),))
    pipeline = ValidationPipeline(executor=ValidationExecutor(), registry=ValidationRegistry())
    result = pipeline.run(context, default_testing_steps(context))

    assert result.status in {ValidationStatus.PASSED, ValidationStatus.WARNING, ValidationStatus.FAILED, ValidationStatus.ERROR}
    assert result.affected_tests == ("tests/test_sample.py",)
