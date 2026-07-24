"""Integration tests for ValidationIntegrationService facade (Subphase 7.13)."""

import shutil
from pathlib import Path

from cmm.validation.integration.events import KernelEventPublisher
from cmm.validation.integration.memory import ValidationMemoryAdapter
from cmm.validation.integration.service import ValidationIntegrationService
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


def test_integration_service_full_workflow(tmp_path: Path):
    setup_test_project_dir(tmp_path)
    file1 = tmp_path / "app.py"
    file1.write_text(
        'def run() -> bool:\n    """Doc."""\n    return True\n', encoding="utf-8"
    )

    app_service = ValidationApplicationService(project_root=tmp_path)
    event_publisher = KernelEventPublisher(policy="best_effort")
    memory_adapter = ValidationMemoryAdapter(retention_policy="always")

    service = ValidationIntegrationService(
        application_service=app_service,
        event_publisher=event_publisher,
        memory_adapter=memory_adapter,
    )

    # 1. Pre-execution
    pre_res = service.validate_before_execution(
        project_root=tmp_path,
        changed_files=(file1,),
        policy_name="small_change",
    )
    assert pre_res.decision.allowed_to_continue is True

    # 2. Semantic change validation
    sem_res = service.validate_semantic_change(
        project_root=tmp_path,
        changed_files=(file1,),
        policy_name="small_change",
    )
    assert sem_res.decision.allowed_to_continue is True
    assert len(event_publisher.emitted_events) > 0
    assert len(memory_adapter.records) == 1

    # 3. Post-execution validation
    post_res = service.validate_after_execution(
        project_root=tmp_path,
        changed_files=(file1,),
        policy_name="small_change",
    )
    assert post_res.decision.allowed_to_continue is True
