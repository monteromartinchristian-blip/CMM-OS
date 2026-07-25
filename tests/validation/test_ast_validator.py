from __future__ import annotations

from pathlib import Path

from cmm.validation.context import ValidationContext
from cmm.validation.steps import ValidationStep, ValidationStepType
from cmm.validation.validators.ast import PythonAstValidator


def test_ast_validator_passes_valid_file(tmp_path: Path):
    path = tmp_path / "ok.py"
    path.write_text("print('ok')\n", encoding="utf-8")
    ctx = ValidationContext(project_root=tmp_path, changed_files=(Path("ok.py"),))

    result = PythonAstValidator().validate(
        ctx, ValidationStep(name="ast", step_type=ValidationStepType.INTERNAL)
    )

    assert result.status.value == "passed"
    assert result.artifacts[0].kind == "ast_report"


def test_ast_validator_reports_parse_error(tmp_path: Path):
    path = tmp_path / "bad.py"
    path.write_text("def broken(:\n    pass\n", encoding="utf-8")
    ctx = ValidationContext(project_root=tmp_path, changed_files=(Path("bad.py"),))

    result = PythonAstValidator().validate(
        ctx, ValidationStep(name="ast", step_type=ValidationStepType.INTERNAL)
    )

    assert result.status.value == "failed"
    assert any(f.code == "PYTHON_AST_PARSE_ERROR" for f in result.findings)
