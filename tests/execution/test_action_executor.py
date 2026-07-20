from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from cmm.execution import Action, ActionType
from cmm.execution.executors import (
    ActionExecutor,
    ExecutionContext,
    ExecutionResult,
    NoOpExecutor,
)


class ReadClassExecutor(ActionExecutor):
    """Test executor supporting a single action type."""

    @property
    def name(self) -> str:
        """Return the executor name."""
        return "read-class"

    def supported_action_types(self) -> set[ActionType]:
        """Support class reads only."""
        return {ActionType.READ_CLASS}

    def execute(self, context: ExecutionContext) -> ExecutionResult:
        """Return a deterministic result for the supplied action."""
        return ExecutionResult(success=True, message="Class read.")


def test_action_executor_is_abstract() -> None:
    with pytest.raises(TypeError):
        ActionExecutor()


def test_can_execute_only_accepts_supported_action_types() -> None:
    executor = ReadClassExecutor()
    class_action = _action(ActionType.READ_CLASS)
    function_action = _action(ActionType.READ_FUNCTION)

    assert executor.name == "read-class"
    assert executor.can_execute(class_action) is True
    assert executor.can_execute(function_action) is False
    assert executor.can_execute(object()) is False


def test_noop_executor_supports_every_action_and_does_not_change_context() -> None:
    executor = NoOpExecutor()
    runtime = object()
    action = _action(ActionType.ANALYZE_IMPACT)
    context = ExecutionContext(
        runtime=runtime,
        action=action,
        working_directory="/project",
        environment={"MODE": "test"},
    )

    result = executor.execute(context)

    assert executor.name == "noop"
    assert executor.supported_action_types() == set(ActionType)
    assert executor.can_execute(action) is True
    assert result == ExecutionResult(success=True, message="No operation executed.")
    assert context.runtime is runtime
    assert context.action is action


def test_execution_result_is_immutable_and_has_independent_defaults() -> None:
    first_result = ExecutionResult(success=True, message="Done")
    second_result = ExecutionResult(success=False, message="Failed")

    with pytest.raises(FrozenInstanceError):
        first_result.success = False

    first_result.artifacts.append("report.txt")
    first_result.metadata["source"] = "test"

    assert second_result.artifacts == []
    assert second_result.metadata == {}
    assert first_result.execution_time is None


def _action(action_type: ActionType) -> Action:
    return Action(
        id="action-1",
        order=1,
        action_type=action_type,
        target="Service",
        description="Test action",
    )
