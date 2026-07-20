from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

import cmm.__main__ as cmm_main
from kernel.planner.execution_plan import ExecutionPlan
from kernel.planner.operations import CreateClassOperation
from kernel.planner.plan_validator import ValidationResult
from kernel.planner.executor import ExecutionResult


@dataclass
class DummyResult:
    goal: str
    execution_plan: ExecutionPlan
    validation_result: ValidationResult
    execution_result: ExecutionResult | None
    modified_files: tuple[Path, ...]

    @property
    def success(self) -> bool:
        return self.validation_result.valid and self.execution_result is not None and self.execution_result.success


class DummyRunner:
    def __init__(self, result: DummyResult) -> None:
        self.result = result
        self.calls: list[tuple[str, Path]] = []

    def run(self, goal: str, project_path: Path) -> DummyResult:
        self.calls.append((goal, project_path))
        return self.result


def test_cli_valid_run(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    plan = ExecutionPlan()
    plan.add(CreateClassOperation(class_name="User"))
    validation_result = ValidationResult(valid=True)
    execution_result = ExecutionResult(
        success=True,
        executed_operations=[CreateClassOperation(class_name="User")],
        failed_operations=[],
        errors=[],
    )
    runner = DummyRunner(
        DummyResult(
            goal="Añade un método hello() a User",
            execution_plan=plan,
            validation_result=validation_result,
            execution_result=execution_result,
            modified_files=(tmp_path / "user.py",),
        )
    )

    monkeypatch.setattr(cmm_main, "EndToEndRunner", lambda: runner)

    project_path = tmp_path / "project"
    project_path.mkdir()

    exit_code = cmm_main.main(["run", "Añade un método hello() a User", "--project", str(project_path)])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "Goal: Añade un método hello() a User" in output
    assert "Operations: 1" in output
    assert "Validation: valid" in output
    assert "- create_class" in output
    assert "-" in output
    assert runner.calls == [("Añade un método hello() a User", project_path)]


def test_cli_requires_command(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(SystemExit) as exc_info:
           cmm_main.main([])

    assert exc_info.value.code == 2


def test_cli_reports_validation_error_and_exits_nonzero(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    plan = ExecutionPlan()
    plan.add(CreateClassOperation(class_name="User"))
    validation_result = ValidationResult(
        valid=False,
        errors=["CreateClassOperation requires a non-empty class_name."],
        warnings=[],
    )
    runner = DummyRunner(
        DummyResult(
            goal="bad goal",
            execution_plan=plan,
            validation_result=validation_result,
            execution_result=None,
            modified_files=(),
        )
    )

    monkeypatch.setattr(cmm_main, "EndToEndRunner", lambda: runner)

    project_path = tmp_path / "project"
    project_path.mkdir()

    exit_code = cmm_main.main(["run", "bad goal", "--project", str(project_path)])
    output = capsys.readouterr().out

    assert exit_code == 2
    assert "Validation: invalid" in output
    assert "Validation errors:" in output
    assert "non-empty class_name" in output


def test_cli_reports_missing_project_path(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = cmm_main.main(["run", "Añade un método hello() a User", "--project", "/nonexistent/project/path"])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "project path does not exist" in captured.err
