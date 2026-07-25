from __future__ import annotations

from pathlib import Path

from cmm.validation.catalog import syntax_step
from cmm.validation.context import ValidationContext
from cmm.validation.steps import ValidationStep
from cmm.validation.validators.syntax import PythonSyntaxValidator


def test_syntax_validator_passes_valid_file(tmp_path: Path):
    path = tmp_path / "ok.py"
    path.write_text("print('ok')\n", encoding="utf-8")
    ctx = ValidationContext(project_root=tmp_path, changed_files=(Path("ok.py"),))

    validator = PythonSyntaxValidator()
    step = ValidationStep(name="syntax", step_type=__import__("cmm.validation.steps", fromlist=["ValidationStepType"]).ValidationStepType.INTERNAL)
    result = validator.validate(ctx, step)

    assert result.status.value == "passed"
    assert result.artifacts
    assert result.artifacts[0].kind == "syntax_report"
    assert result.artifacts[0].content["checked_files"] == ["ok.py"]


def test_syntax_validator_reports_syntax_error(tmp_path: Path):
    path = tmp_path / "bad.py"
    path.write_text("def broken(:\n    pass\n", encoding="utf-8")
    ctx = ValidationContext(project_root=tmp_path, changed_files=(Path("bad.py"),))

    validator = PythonSyntaxValidator()
    step = ValidationStep(name="syntax", step_type=__import__("cmm.validation.steps", fromlist=["ValidationStepType"]).ValidationStepType.INTERNAL)
    result = validator.validate(ctx, step)

    assert result.status.value == "failed"
    assert any(f.code == "PYTHON_SYNTAX_ERROR" for f in result.findings)
    assert result.findings[0].line is not None
