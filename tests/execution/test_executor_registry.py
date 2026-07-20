from __future__ import annotations

import pytest

from cmm.execution import (
    Action,
    ActionType,
    ExecutorRegistry,
    UnsupportedActionError,
)
from cmm.execution.executors import ActionExecutor, ExecutionContext, ExecutionResult, NoOpExecutor


class ReadClassExecutor(ActionExecutor):
    """Test executor that supports only class-read actions."""

    @property
    def name(self) -> str:
        """Return the stable test executor name."""
        return "read-class"

    def supported_action_types(self) -> set[ActionType]:
        """Support class-read actions."""
        return {ActionType.READ_CLASS}

    def execute(self, context: ExecutionContext) -> ExecutionResult:
        """Return a deterministic test result."""
        return ExecutionResult(success=True, message="Read class.")


def test_register_adds_executor_and_clear_removes_it() -> None:
    registry = ExecutorRegistry()
    executor = ReadClassExecutor()

    registry.register(executor)

    assert registry.all() == [executor]
    registry.clear()
    assert registry.all() == []


def test_register_many_preserves_registration_order() -> None:
    registry = ExecutorRegistry()
    class_executor = ReadClassExecutor()
    noop_executor = NoOpExecutor()

    registry.register_many([class_executor, noop_executor])

    assert registry.all() == [class_executor, noop_executor]


def test_register_rejects_duplicate_executor_names() -> None:
    registry = ExecutorRegistry()
    registry.register(ReadClassExecutor())

    with pytest.raises(ValueError, match="Executor already registered: read-class"):
        registry.register(ReadClassExecutor())


def test_resolve_returns_first_compatible_executor() -> None:
    registry = ExecutorRegistry()
    class_executor = ReadClassExecutor()
    noop_executor = NoOpExecutor()
    registry.register_many([class_executor, noop_executor])

    assert registry.resolve(_action(ActionType.READ_CLASS)) is class_executor
    assert registry.resolve(_action(ActionType.READ_FUNCTION)) is noop_executor


def test_resolve_raises_for_unsupported_action_type() -> None:
    registry = ExecutorRegistry()

    with pytest.raises(UnsupportedActionError, match="Unsupported action type: READ_METHOD"):
        registry.resolve(_action(ActionType.READ_METHOD))


def _action(action_type: ActionType) -> Action:
    return Action(
        id="action-1",
        order=1,
        action_type=action_type,
        target="Service",
        description="Test action",
    )
