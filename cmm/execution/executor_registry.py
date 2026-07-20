"""Registry for resolving action executors without executing actions."""

from __future__ import annotations

from cmm.execution.action_planner import ActionType
from cmm.execution.executors.base import ActionExecutor


class UnsupportedActionError(Exception):
    """Raised when no registered executor supports an action."""


class ExecutorRegistry:
    """Register action executors and resolve the first compatible executor."""

    def __init__(self) -> None:
        """Initialize an empty executor registry."""
        self._executors: list[ActionExecutor] = []

    def register(self, executor: ActionExecutor) -> None:
        """Register an executor if its stable name is not already registered."""
        self.register_many([executor])

    def register_many(self, executors: list[ActionExecutor]) -> None:
        """Register several executors atomically, rejecting duplicate names."""
        names = {executor.name for executor in self._executors}
        new_names = set()

        for executor in executors:
            if not isinstance(executor, ActionExecutor):
                raise TypeError("Executor must implement ActionExecutor.")
            if executor.name in names or executor.name in new_names:
                raise ValueError(f"Executor already registered: {executor.name}.")
            new_names.add(executor.name)

        self._executors.extend(executors)

    def resolve(self, action: object) -> ActionExecutor:
        """Return the first registered executor that can execute ``action``."""
        for executor in self._executors:
            if executor.can_execute(action):
                return executor

        action_type = getattr(action, "action_type", None)
        type_name = action_type.value if isinstance(action_type, ActionType) else str(action_type)
        raise UnsupportedActionError(f"Unsupported action type: {type_name}.")

    def all(self) -> list[ActionExecutor]:
        """Return registered executors in registration order."""
        return list(self._executors)

    def clear(self) -> None:
        """Remove every executor from the registry."""
        self._executors.clear()


def create_default_executor_registry() -> ExecutorRegistry:
    """Create the default registry with production and fallback executors."""
    from cmm.execution.executors import NoOpExecutor, PythonExecutor, ReadOnlyFilesystemExecutor

    registry = ExecutorRegistry()
    registry.register_many([ReadOnlyFilesystemExecutor(), PythonExecutor(), NoOpExecutor()])
    return registry
