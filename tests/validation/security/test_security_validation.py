from __future__ import annotations

from pathlib import Path

from cmm.validation import ValidationContext, ValidationExecutor, ValidationPipeline
from cmm.validation.catalog import build_default_validation_registry
from cmm.validation.enums import ValidationStatus
from cmm.validation.testing_defaults import default_validation_steps


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_security_validation_detects_secret_and_shell(tmp_path: Path) -> None:
    _write(
        tmp_path / "pkg" / "module.py",
        "import subprocess\nAPI_KEY = 'supersecretvalue'\nsubprocess.run(['echo', 'hi'], shell=True)\n",
    )
    _write(tmp_path / "tests" / "test_module.py", "def test_func():\n    assert True\n")
    context = ValidationContext(project_root=tmp_path, changed_files=(Path("pkg/module.py"),))

    pipeline = ValidationPipeline(executor=ValidationExecutor(), registry=build_default_validation_registry())
    result = pipeline.run(context, default_validation_steps(context))

    assert result.status == ValidationStatus.FAILED
    security = next(step for step in result.steps if step.name == "security")
    codes = {finding.code for finding in security.findings}
    assert "SECURITY_SECRET_LITERAL" in codes
    assert "SECURITY_SHELL_TRUE" in codes
    assert any(artifact.kind == "secret_scan_report" for artifact in security.artifacts)
    assert security.metadata["finding_count"] >= 2
