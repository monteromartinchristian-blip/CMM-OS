"""End-to-End Real Integration Scenarios for Phase 7 (Subphase 7.13)."""

import shutil
from pathlib import Path

from cmm.validation.integration.contracts import (
    ValidationAction,
    ValidationPhase,
    ValidationPlanNode,
    ValidationTrigger,
)
from cmm.validation.integration.events import KernelEventPublisher
from cmm.validation.integration.memory import ValidationMemoryAdapter
from cmm.validation.integration.planning import PlannerValidationAdapter
from cmm.validation.integration.service import ValidationIntegrationService
from cmm.validation.interfaces.application import ValidationApplicationService
from kernel.events.event import Event

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


def test_e2e_valid_semantic_transformation(tmp_path: Path):
    setup_test_project_dir(tmp_path)
    code_file = tmp_path / "calculator.py"
    code_file.write_text(
        'class Calculator:\n    def add(self, a: int, b: int) -> int:\n        """Add numbers."""\n        return a + b\n',
        encoding="utf-8",
    )

    app_service = ValidationApplicationService(project_root=tmp_path)
    service = ValidationIntegrationService(application_service=app_service)

    res = service.validate_semantic_change(
        project_root=tmp_path,
        changed_files=(code_file,),
        policy_name="small_change",
    )

    assert res.decision.allowed_to_continue is True
    assert res.decision.recommended_action == ValidationAction.CONTINUE
    assert res.validation_result.status.value == "passed"


def test_e2e_invalid_syntax_triggers_rollback(tmp_path: Path):
    setup_test_project_dir(tmp_path)
    code_file = tmp_path / "calculator.py"
    original_code = 'class Calculator:\n    def add(self, a: int, b: int) -> int:\n        """Add numbers."""\n        return a + b\n'
    code_file.write_text(original_code, encoding="utf-8")

    # Apply broken change
    broken_code = "class Calculator:\n    def add(self, a, b:\n        return a + b\n"
    code_file.write_text(broken_code, encoding="utf-8")

    def rollback() -> bool:
        code_file.write_text(original_code, encoding="utf-8")
        return True

    app_service = ValidationApplicationService(project_root=tmp_path)
    service = ValidationIntegrationService(application_service=app_service)

    res = service.validate_after_execution(
        project_root=tmp_path,
        changed_files=(code_file,),
        policy_name="small_change",
        rollback_handler=rollback,
    )

    assert res.decision.allowed_to_continue is False
    assert res.decision.recommended_action == ValidationAction.ROLLBACK
    assert res.rollback_requested is True
    assert res.rollback_executed is True
    assert res.rollback_success is True
    assert code_file.read_text(encoding="utf-8") == original_code


def test_e2e_plan_node_validation_and_events(tmp_path: Path):
    setup_test_project_dir(tmp_path)
    code_file = tmp_path / "module.py"
    code_file.write_text(
        '"""Module doc."""\n\n\ndef get_answer() -> int:\n    """Return answer."""\n    return 42\n',
        encoding="utf-8",
    )

    emitted: list[Event] = []
    publisher = KernelEventPublisher(event_listener=lambda e: emitted.append(e))
    app_service = ValidationApplicationService(project_root=tmp_path)

    planner_adapter = PlannerValidationAdapter(application_service=app_service)
    node = ValidationPlanNode(
        id="val_node_01",
        phase=ValidationPhase.AFTER_EXECUTION,
        policy_name="small_change",
        on_pass=ValidationAction.CONTINUE,
        on_failure=ValidationAction.STOP,
    )

    planner_adapter.validate_plan_nodes((node,))

    res = planner_adapter.execute_plan_node(
        node=node,
        project_root=tmp_path,
        changed_files=(code_file,),
    )

    assert res.decision.allowed_to_continue is True
    assert res.decision.recommended_action == ValidationAction.CONTINUE
    publisher.publish_validation_events(
        res.validation_result,
        trigger=ValidationTrigger(
            phase=ValidationPhase.AFTER_EXECUTION,
            source="planner",
            actor="planner",
        ),
    )
    assert len(publisher.emitted_events) > 0


def test_e2e_memory_persistence_on_failure(tmp_path: Path):
    setup_test_project_dir(tmp_path)
    code_file = tmp_path / "broken.py"
    code_file.write_text("def error(\n", encoding="utf-8")

    app_service = ValidationApplicationService(project_root=tmp_path)
    memory_adapter = ValidationMemoryAdapter(retention_policy="blocking_only")
    service = ValidationIntegrationService(
        application_service=app_service,
        memory_adapter=memory_adapter,
    )

    res = service.validate_after_execution(
        project_root=tmp_path,
        changed_files=(code_file,),
        policy_name="small_change",
    )

    assert res.decision.allowed_to_continue is False
    assert len(memory_adapter.records) == 1
    rec = memory_adapter.records[0]
    assert rec.status == "failed"
    assert "broken.py" in rec.affected_files[0]


def test_e2e_legacy_opt_in_disabled(tmp_path: Path):
    from cmm.validation.integration.semantic import SemanticValidationAdapter

    adapter = SemanticValidationAdapter(
        application_service=None, validation_enabled=False
    )
    res = adapter.validate_semantic_operation(
        project_root=tmp_path,
        changed_files=(),
    )

    assert res.decision.allowed_to_continue is True
    assert res.decision.recommended_action == ValidationAction.CONTINUE
    assert res.validation_result is None
