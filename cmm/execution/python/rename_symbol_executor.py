"""LibCST executor for renaming one top-level function in one module."""

from __future__ import annotations

import keyword

from cmm.execution.execution_result import ExecutionResult
from cmm.execution.execution_context import ExecutionContext
from cmm.execution.operation_executor import OperationExecutor
from cmm.execution.python.python_module_editor import PythonModuleEditor
from cmm.execution.python.python_module_writer import PythonModuleWriter
from cmm.execution.python.reference_index import ReferenceIndex
from cmm.execution.python.semantic_context import SemanticContext
from cmm.execution.python.visitors import (
    FunctionLocator,
    RenameFunctionTransformer,
)
from cmm.transformations.execution_request import ExecutionRequest
from cmm.transformations.operation import TransformationOperation
from cmm.transformations.operations import RenameSymbolOperation


class PythonRenameSymbolExecutor(OperationExecutor):
    """Rename a top-level function and its simple references in one module."""

    def __init__(
        self,
        locator: FunctionLocator | None = None,
        writer: PythonModuleWriter | None = None,
    ) -> None:
        self._locator = locator or FunctionLocator()
        self._writer = writer or PythonModuleWriter()

    @property
    def operation_type(self) -> type[TransformationOperation]:
        return RenameSymbolOperation

    def execute(self, request: ExecutionRequest) -> ExecutionResult:
        if not isinstance(request.operation, RenameSymbolOperation):
            return ExecutionResult(
                success=False,
                operation=request.operation,
                diagnostics=("Unsupported operation",),
            )

        module_name = request.metadata.get("module")
        context = request.metadata.get("semantic_context")
        execution_context = request.metadata.get("execution_context")
        if not isinstance(module_name, str) or not isinstance(context, SemanticContext):
            return ExecutionResult(
                success=False,
                operation=request.operation,
                diagnostics=("Missing SemanticContext",),
            )
        if not isinstance(context.reference_index, ReferenceIndex):
            return ExecutionResult(
                success=False,
                operation=request.operation,
                diagnostics=("Missing ReferenceIndex",),
            )
        if not self._is_valid_name(request.operation.new_name):
            return ExecutionResult(
                success=False,
                operation=request.operation,
                diagnostics=("Invalid new name",),
            )

        module = next(
            (
                item
                for item in context.snapshot.modules
                if item.module_name == module_name
            ),
            None,
        )
        if module is None or module.parsed_module is None:
            return ExecutionResult(
                success=False,
                operation=request.operation,
                diagnostics=("Function not found",),
            )
        if isinstance(execution_context, ExecutionContext):
            execution_context.resolve_project_path(module.path)
        if self._locator.find(module.parsed_module, request.operation.symbol) is None:
            return ExecutionResult(
                success=False,
                operation=request.operation,
                diagnostics=("Function not found",),
            )
        if self._locator.find(module.parsed_module, request.operation.new_name) is not None:
            return ExecutionResult(
                success=False,
                operation=request.operation,
                diagnostics=("Function already exists",),
            )

        reference_locations = [
            location
            for location in context.reference_index.find(request.operation.symbol)
            if location.module_name == module_name
        ]
        updated_module = PythonModuleEditor(module).apply(
            RenameFunctionTransformer(
                request.operation.symbol,
                request.operation.new_name,
            )
        )
        wrote = self._writer.write(updated_module)
        return ExecutionResult(
            success=True,
            operation=request.operation,
            created_paths=(updated_module.path,) if wrote else (),
            metadata={"renamed_references": len(reference_locations)},
        )

    def _is_valid_name(self, name: str) -> bool:
        return name.isidentifier() and not keyword.iskeyword(name)
