"""Filesystem operation executors backed by ExecutionContext path checks."""

from __future__ import annotations

from cmm.execution.execution_context import ExecutionContext
from cmm.execution.execution_result import ExecutionResult
from cmm.execution.operation_executor import OperationExecutor
from cmm.transformations.execution_request import ExecutionRequest
from cmm.transformations.operation import TransformationOperation
from cmm.transformations.operations import CreateFileOperation, DeleteFileOperation


def _context_from(request: ExecutionRequest) -> ExecutionContext | None:
    context = request.metadata.get("execution_context")
    return context if isinstance(context, ExecutionContext) else None


class CreateFileExecutor(OperationExecutor):
    """Create an empty in-project file without overwriting existing content."""

    @property
    def operation_type(self) -> type[TransformationOperation]:
        return CreateFileOperation

    def execute(self, request: ExecutionRequest) -> ExecutionResult:
        if not isinstance(request.operation, CreateFileOperation):
            return ExecutionResult(False, request.operation, ("Unsupported operation",))
        context = _context_from(request)
        if context is None:
            return ExecutionResult(False, request.operation, ("Missing ExecutionContext",))
        path = context.resolve_project_path(request.operation.path)
        if path.exists():
            return ExecutionResult(False, request.operation, ("File already exists",))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch(exist_ok=False)
        return ExecutionResult(True, request.operation, created_paths=(path,))


class DeleteFileExecutor(OperationExecutor):
    """Delete an in-project file."""

    @property
    def operation_type(self) -> type[TransformationOperation]:
        return DeleteFileOperation

    def execute(self, request: ExecutionRequest) -> ExecutionResult:
        if not isinstance(request.operation, DeleteFileOperation):
            return ExecutionResult(False, request.operation, ("Unsupported operation",))
        context = _context_from(request)
        if context is None:
            return ExecutionResult(False, request.operation, ("Missing ExecutionContext",))
        path = context.resolve_project_path(request.operation.path)
        if not path.is_file():
            return ExecutionResult(False, request.operation, ("File not found",))
        path.unlink()
        return ExecutionResult(True, request.operation, metadata={"deleted_paths": (path,)})
