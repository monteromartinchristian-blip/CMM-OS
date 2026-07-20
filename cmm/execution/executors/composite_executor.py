"""Composite executor routing actions to specialized production executors."""

from __future__ import annotations

from typing import Mapping

from cmm.execution.action_planner import ActionType
from cmm.execution.executor_registry import UnsupportedActionError
from cmm.execution.executors.base import ActionExecutor, ExecutionContext, ExecutionResult


class CompositeExecutor(ActionExecutor):
    """Route actions by prefix to the appropriate specialized executor."""

    _KNOWN_PREFIXES = ("filesystem.", "python.", "git.")

    def __init__(self, executors_by_prefix: Mapping[str, ActionExecutor]) -> None:
        self._executors_by_prefix = dict(executors_by_prefix)

    @property
    def name(self) -> str:
        """Return the stable executor name."""
        return "composite"

    def supported_action_types(self) -> set[ActionType]:
        """Return every action type that matches a configured prefix."""
        return {
            action_type
            for action_type in ActionType
            if action_type.value.startswith(self._KNOWN_PREFIXES)
        }

    def execute(self, context: ExecutionContext) -> ExecutionResult:
        """Dispatch execution to the configured executor for the action prefix."""
        action_type = getattr(context.action, "action_type", None)
        if not isinstance(action_type, ActionType):
            raise UnsupportedActionError(f"Unsupported action type: {action_type}.")

        prefix = self._prefix_for(action_type.value)
        if prefix is None:
            raise UnsupportedActionError(f"Unsupported action type: {action_type.value}.")

        executor = self._executors_by_prefix.get(prefix)
        if executor is None:
            raise UnsupportedActionError(f"No executor configured for action prefix: {prefix}.")

        return executor.execute(context)

    def _prefix_for(self, action_type: str) -> str | None:
        for prefix in self._KNOWN_PREFIXES:
            if action_type.startswith(prefix):
                return prefix

        return None
