from __future__ import annotations

from types import SimpleNamespace

import pytest

from cmm.execution import Action, ActionType, UnsupportedActionError
from cmm.execution.executors import (
    ActionExecutor,
    CompositeExecutor,
    ExecutionContext,
    ExecutionResult,
)


class StubExecutor(ActionExecutor):
    def __init__(self, name: str) -> None:
        self._name = name
        self.received_context: ExecutionContext | None = None

    @property
    def name(self) -> str:
        return self._name

    def supported_action_types(self) -> set[ActionType]:
        return set(ActionType)

    def execute(self, context: ExecutionContext) -> ExecutionResult:
        self.received_context = context
        return ExecutionResult(success=True, message=f"{self._name} executed")


def test_composite_delegates_filesystem_actions() -> None:
    filesystem = StubExecutor("filesystem")
    composite = CompositeExecutor({"filesystem.": filesystem})
    context = _context(_action(ActionType.FILESYSTEM_EXISTS))

    result = composite.execute(context)

    assert result.success is True
    assert result.message == "filesystem executed"
    assert filesystem.received_context is context


def test_composite_delegates_python_actions() -> None:
    python = StubExecutor("python")
    composite = CompositeExecutor({"python.": python})
    context = _context(_action(ActionType.PYTHON_LIST_CLASSES))

    result = composite.execute(context)

    assert result.success is True
    assert result.message == "python executed"
    assert python.received_context is context


def test_composite_delegates_git_actions() -> None:
    git = StubExecutor("git")
    composite = CompositeExecutor({"git.": git})
    context = _context(_action(ActionType.GIT_STATUS))

    result = composite.execute(context)

    assert result.success is True
    assert result.message == "git executed"
    assert git.received_context is context


def test_composite_rejects_unknown_prefix() -> None:
    composite = CompositeExecutor({"filesystem.": StubExecutor("filesystem")})

    with pytest.raises(UnsupportedActionError, match="Unsupported action type: READ_METHOD"):
        composite.execute(_context(_action(ActionType.READ_METHOD)))


def test_composite_rejects_missing_executor() -> None:
    composite = CompositeExecutor({"filesystem.": StubExecutor("filesystem")})

    with pytest.raises(UnsupportedActionError, match="No executor configured for action prefix: python\\."):
        composite.execute(_context(_action(ActionType.PYTHON_LIST_FUNCTIONS)))


def test_composite_rejects_invalid_action() -> None:
    composite = CompositeExecutor({"filesystem.": StubExecutor("filesystem")})
    invalid_action = SimpleNamespace(action_type="filesystem.exists")

    with pytest.raises(UnsupportedActionError, match="Unsupported action type"):
        composite.execute(_context(invalid_action))


def _action(action_type: ActionType) -> Action:
    return Action(
        id="action-1",
        order=1,
        action_type=action_type,
        target=".",
        description="test",
    )


def _context(action: object) -> ExecutionContext:
    return ExecutionContext(
        runtime=object(),
        action=action,
        working_directory="/tmp",
        environment={},
    )
