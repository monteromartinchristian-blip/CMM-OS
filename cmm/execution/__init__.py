"""Deterministic execution-action planning API for CMM OS."""

from cmm.execution.action_planner import Action, ActionPlanner, ActionType
from cmm.execution.backend_action_adapter import BackendActionAdapter
from cmm.execution.execution_result import ExecutionResult
from cmm.execution.operation_executor import OperationExecutor
from cmm.execution.operation_executor_registry import (
    OperationExecutorRegistry,
    UnsupportedOperationExecutorError,
)
from cmm.execution.executor_registry import (
    ExecutorRegistry,
    UnsupportedActionError,
    create_default_executor_registry,
)

__all__ = [
    "Action",
    "ActionPlanner",
    "ActionType",
    "BackendActionAdapter",
    "ExecutionResult",
    "ExecutorRegistry",
    "OperationExecutor",
    "OperationExecutorRegistry",
    "UnsupportedActionError",
    "UnsupportedOperationExecutorError",
    "create_default_executor_registry",
]
