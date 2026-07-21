"""Deterministic execution-action planning API for CMM OS."""

from cmm.execution.action_planner import Action, ActionPlanner, ActionType
from cmm.execution.backend_action_adapter import BackendActionAdapter
from cmm.execution.execution_context import ExecutionContext, ProjectPathError
from cmm.execution.execution_pipeline import ExecutionPipeline
from cmm.execution.execution_result import (
    ExecutionResult,
    FinalValidationResult,
    OperationResultRecord,
    PipelineExecutionResult,
    RollbackResult,
    StructuredExecutionError,
)
from cmm.execution.file_operation_executors import CreateFileExecutor, DeleteFileExecutor
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
    "CreateFileExecutor",
    "DeleteFileExecutor",
    "ExecutionContext",
    "ExecutionPipeline",
    "ExecutionResult",
    "FinalValidationResult",
    "ExecutorRegistry",
    "OperationResultRecord",
    "OperationExecutor",
    "OperationExecutorRegistry",
    "PipelineExecutionResult",
    "ProjectPathError",
    "RollbackResult",
    "StructuredExecutionError",
    "UnsupportedActionError",
    "UnsupportedOperationExecutorError",
    "create_default_executor_registry",
]
