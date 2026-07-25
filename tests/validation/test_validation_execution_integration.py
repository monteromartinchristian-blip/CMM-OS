"""Integration tests for Execution Engine Coordinator (Subphase 7.13)."""

import shutil
from pathlib import Path

from cmm.validation.integration.contracts import ValidationAction
from cmm.validation.integration.execution import ExecutionValidationCoordinator
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


def test_execution_coordinator_pre_validation_pass(tmp_path: Path):
    setup_test_project_dir(tmp_path)
    file1 = tmp_path / "valid.py"
    file1.write_text(
        'def valid_func() -> int:\n    """Doc."""\n    return 10\n', encoding="utf-8"
    )

    app_service = ValidationApplicationService(project_root=tmp_path)
    coord = ExecutionValidationCoordinator(application_service=app_service)

    res = coord.validate_pre_execution(
        project_root=tmp_path,
        changed_files=(file1,),
        policy_name="small_change",
    )

    assert res.decision.allowed_to_continue is True
    assert res.decision.recommended_action == ValidationAction.CONTINUE
    assert res.rollback_requested is False


def test_execution_coordinator_post_validation_with_rollback(tmp_path: Path):
    setup_test_project_dir(tmp_path)
    file1 = tmp_path / "bad.py"
    original_content = 'def test() -> None:\n    """Doc."""\n    pass\n'
    file1.write_text("def broken_code(: bad\n", encoding="utf-8")

    rollback_called = False

    def handle_rollback() -> bool:
        nonlocal rollback_called
        file1.write_text(original_content, encoding="utf-8")
        rollback_called = True
        return True

    app_service = ValidationApplicationService(project_root=tmp_path)
    coord = ExecutionValidationCoordinator(application_service=app_service)

    res = coord.validate_post_execution(
        project_root=tmp_path,
        changed_files=(file1,),
        policy_name="small_change",
        rollback_handler=handle_rollback,
    )

    assert res.decision.allowed_to_continue is False
    assert res.rollback_requested is True
    assert res.rollback_executed is True
    assert res.rollback_success is True
    assert rollback_called is True
    assert file1.read_text(encoding="utf-8") == original_content
    assert res.validation_result.status.value == "failed"
