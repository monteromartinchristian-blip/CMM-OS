from __future__ import annotations

from pathlib import Path

from cmm.execution import Action, ActionPlanner, ActionType, ExecutorRegistry
from cmm.execution.executors import ActionExecutor, ExecutionContext, ExecutionResult, NoOpExecutor
from cmm.memory import TechnicalMemory, TechnicalReasoner
from cmm.planner import TaskPlanner
from cmm.runtime import ActionRuntime, ActionStatus


class FailingExecutor(ActionExecutor):
    @property
    def name(self) -> str:
        return "failure"

    def supported_action_types(self) -> set[ActionType]:
        return {ActionType.READ_CLASS}

    def execute(self, context: ExecutionContext) -> ExecutionResult:
        return ExecutionResult(False, "executor failed")


def test_action_runtime_executes_a_queue_through_noop_registry() -> None:
    action_planner = ActionPlanner(object())
    registry = ExecutorRegistry()
    registry.register(NoOpExecutor())
    runtime = ActionRuntime(action_planner, registry=registry)
    actions = [
        Action("one", 1, ActionType.READ_CLASS, "User", "Read User"),
        Action("two", 2, ActionType.ANALYZE_IMPACT, "User", "Analyze User"),
    ]

    result = runtime.execute(actions)

    assert result.success is True
    assert [item.status for item in result.executions] == [ActionStatus.COMPLETED, ActionStatus.COMPLETED]
    assert result.serialize()["errors"] == []


def test_action_runtime_stops_on_missing_executor_and_records_history() -> None:
    action_planner = ActionPlanner(object())
    runtime = ActionRuntime(action_planner, registry=ExecutorRegistry())
    actions = [
        Action("one", 1, ActionType.READ_CLASS, "User", "Read User"),
        Action("two", 2, ActionType.READ_FUNCTION, "run", "Read run"),
    ]

    result = runtime.execute(actions)

    assert result.success is False
    assert result.stopped is True
    assert result.executions[0].status is ActionStatus.FAILED
    assert result.executions[1].status is ActionStatus.SKIPPED
    assert "Unsupported action type" in result.errors[0]


def test_action_runtime_stops_on_executor_error() -> None:
    action_planner = ActionPlanner(object())
    registry = ExecutorRegistry()
    registry.register(FailingExecutor())
    runtime = ActionRuntime(action_planner, registry=registry)
    actions = [
        Action("one", 1, ActionType.READ_CLASS, "User", "Read User"),
        Action("two", 2, ActionType.READ_FUNCTION, "run", "Read run"),
    ]

    result = runtime.execute(actions)

    assert result.success is False
    assert result.errors == ("executor failed",)
    assert result.executions[0].status is ActionStatus.FAILED
    assert result.executions[1].status is ActionStatus.SKIPPED


def test_persistent_goal_to_noop_flow_is_end_to_end(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text("def target():\n    pass\n", encoding="utf-8")
    memory = TechnicalMemory.for_project(tmp_path)
    assert memory.load().success is True
    reasoner = TechnicalReasoner(memory)
    task_planner = TaskPlanner(reasoner)
    execution_plan = task_planner.create_plan("target")
    action_planner = ActionPlanner(task_planner)
    actions = action_planner.optimize(action_planner.create_actions(execution_plan))
    registry = ExecutorRegistry()
    registry.register(NoOpExecutor())
    runtime = ActionRuntime(action_planner, registry=registry, working_directory=tmp_path)

    result = runtime.execute(actions)

    assert result.success is True
    assert result.executions
    assert all(item.status is ActionStatus.COMPLETED for item in result.executions)
