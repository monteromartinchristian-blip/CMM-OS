from __future__ import annotations

import ast
import shutil
from pathlib import Path

from kernel.end_to_end_runner import EndToEndRunner
from kernel.planner.execution_plan import ExecutionPlan
from kernel.planner.operations import CreateClassOperation, InsertMethodOperation
from kernel.planner.operation_planner import OperationPlanner
from kernel.planner.planner_strategy import RuleBasedPlannerStrategy
from kernel.planner.planner_strategy import PlannerStrategy
from kernel.planner.operation_catalog import OperationCatalog


class DuplicateCreateClassStrategy(PlannerStrategy):
    def plan(self, goal: str, catalog: OperationCatalog) -> ExecutionPlan:
        plan = ExecutionPlan()
        plan.add(CreateClassOperation(class_name="User"))
        plan.add(CreateClassOperation(class_name="User"))
        return plan


def _copy_sample_project(tmp_path: Path) -> Path:
    source = Path(__file__).parent / "fixtures" / "sample_project"
    destination = tmp_path / "sample_project"
    shutil.copytree(source, destination)
    return destination


def test_end_to_end_runner_modifies_the_project(tmp_path: Path) -> None:
    project_path = _copy_sample_project(tmp_path)
    runner = EndToEndRunner()

    result = runner.run("Añade un método hello() a User", project_path)

    user_file = project_path / "user.py"
    text = user_file.read_text(encoding="utf-8")

    assert result.success is True
    assert result.validation_result.valid is True
    assert len(result.execution_plan) == 1
    assert isinstance(result.execution_plan[0], InsertMethodOperation)
    assert result.execution_plan[0].method_name == "hello"
    assert result.execution_result.success is True
    assert user_file in result.modified_files
    assert "def hello" in text
    assert "return" not in text
    ast.parse(text)


def test_end_to_end_runner_does_not_break_rule_based_path(tmp_path: Path) -> None:
    project_path = _copy_sample_project(tmp_path)
    planner = OperationPlanner(strategy=RuleBasedPlannerStrategy())

    plan = planner.plan("create class AuditLog")

    assert len(plan) == 1
    assert plan[0].operation_type_value == "create_class"
    assert plan[0].class_name == "AuditLog"


def test_end_to_end_runner_skips_execution_for_invalid_plans(tmp_path: Path) -> None:
    project_path = _copy_sample_project(tmp_path)
    runner = EndToEndRunner(planner=OperationPlanner(strategy=DuplicateCreateClassStrategy()))

    result = runner.run("any goal", project_path)

    text = (project_path / "user.py").read_text(encoding="utf-8")

    assert result.success is False
    assert result.validation_result.valid is False
    assert result.execution_result is None
    assert result.modified_files == ()
    assert "Duplicate operation detected" in " ".join(result.errors)
    assert text == "class User:\n    pass\n"
