"""Base contract for non-runtime action executors."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional

from cmm.execution.action_planner import ActionType


@dataclass(frozen=True)
class ExecutionResult:
    """Immutable result returned by an action executor."""

    success: bool
    message: str
    artifacts: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    execution_time: Optional[float] = None


@dataclass
class ExecutionContext:
    """Container passed to an executor for one action invocation."""

    runtime: object
    action: object
    working_directory: str
    environment: dict[str, str]


class ActionExecutor(ABC):
    """Contract implemented by executors that perform one supported action."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the executor's stable name."""

    @abstractmethod
    def supported_action_types(self) -> set[ActionType]:
        """Return action types this executor can process."""

    def can_execute(self, action: object) -> bool:
        """Return whether the action type is supported by this executor."""
        action_type = getattr(action, "action_type", None)
        return isinstance(action_type, ActionType) and action_type in self.supported_action_types()

    @abstractmethod
    def execute(self, context: ExecutionContext) -> ExecutionResult:
        """Execute one action and return its result without changing runtime state."""


class NoOpExecutor(ActionExecutor):
    """Executor that accepts every action and performs no work."""

    @property
    def name(self) -> str:
        """Return the stable no-operation executor name."""
        return "noop"

    def supported_action_types(self) -> set[ActionType]:
        """Support every currently defined action type."""
        return set(ActionType)

    def execute(self, context: ExecutionContext) -> ExecutionResult:
        """Return a successful no-operation result without inspecting the context."""
        return ExecutionResult(success=True, message="No operation executed.")
