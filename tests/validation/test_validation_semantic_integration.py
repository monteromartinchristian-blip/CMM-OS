"""Integration tests for Semantic Engine Validation Adapter (Subphase 7.13)."""

import shutil
from pathlib import Path

from cmm.validation.integration.contracts import ValidationAction
from cmm.validation.integration.semantic import SemanticValidationAdapter
from cmm.validation.interfaces.application import ValidationApplicationService

VALID_PYPROJECT_TOML = """[build-system]
requires = ["setuptools>=61.0"]
build-backend = "setuptools.build_meta"

[project]
name = "test-project"
version = "0.1.0"
requires-python = ">=3.10"

[project.scripts]
cmm = "cmm.cli:main"

[project.optional-dependencies]
dev = ["ruff", "mypy", "pytest", "bandit", "vulture", "pip-audit"]
validation = ["ruff", "mypy", "pytest", "bandit", "vulture", "pip-audit"]
"""


def setup_test_project_dir(tmp_path: Path) -> Path:
    (tmp_path / "pyproject.toml").write_text(VALID_PYPROJECT_TOML, encoding="utf-8")
    cmm_dir = tmp_path / "cmm"
    cmm_dir.mkdir(parents=True, exist_ok=True)
    shutil.copytree(
        Path.cwd() / "cmm" / "validation",
        cmm_dir / "validation",
        dirs_exist_ok=True,
        ignore=shutil.ignore_patterns("test_*.py"),
    )
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir(parents=True, exist_ok=True)
    (tests_dir / "test_sample.py").write_text(
        "def test_sample():\n    pass\n", encoding="utf-8"
    )
    return tmp_path


def test_semantic_adapter_legacy_opt_in_disabled():
    adapter = SemanticValidationAdapter(
        application_service=None, validation_enabled=False
    )
    res = adapter.validate_semantic_operation(
        project_root="/tmp",
        changed_files=(),
    )
    assert res.decision.allowed_to_continue is True
    assert res.decision.recommended_action == ValidationAction.CONTINUE
    assert res.validation_result is None


def test_semantic_adapter_valid_operation(tmp_path: Path):
    setup_test_project_dir(tmp_path)
    file1 = tmp_path / "sample.py"
    file1.write_text(
        'def hello() -> str:\n    """Return greeting."""\n    return "world"\n',
        encoding="utf-8",
    )

    app_service = ValidationApplicationService(project_root=tmp_path)
    adapter = SemanticValidationAdapter(
        application_service=app_service, validation_enabled=True
    )

    res = adapter.validate_semantic_operation(
        project_root=tmp_path,
        changed_files=(file1,),
        policy_name="small_change",
    )

    assert res.decision.validation_id != ""
    assert res.decision.allowed_to_continue is True
    assert res.validation_result is not None
    assert res.validation_result.status.value == "passed"


def test_semantic_adapter_syntax_error(tmp_path: Path):
    setup_test_project_dir(tmp_path)
    file1 = tmp_path / "broken.py"
    file1.write_text("def broken_syntax(\n", encoding="utf-8")

    app_service = ValidationApplicationService(project_root=tmp_path)
    adapter = SemanticValidationAdapter(
        application_service=app_service, validation_enabled=True
    )

    res = adapter.validate_semantic_operation(
        project_root=tmp_path,
        changed_files=(file1,),
        policy_name="small_change",
    )

    assert res.decision.allowed_to_continue is False
    assert res.decision.recommended_action == ValidationAction.ROLLBACK
    assert res.validation_result.status.value == "failed"
