"""LibCST executor for copying top-level Python functions."""

from cmm.execution.execution_result import ExecutionResult
from cmm.execution.operation_executor import OperationExecutor
from cmm.execution.python.python_module_editor import PythonModuleEditor
from cmm.execution.python.python_module_writer import PythonModuleWriter
from cmm.execution.python.python_project_parser import (
    PythonModuleInfo,
    PythonProjectSnapshot,
)
from cmm.execution.python.semantic_context import SemanticContext
from cmm.execution.python.visitors import (
    AppendFunctionTransformer,
    FunctionLocator,
)
from cmm.transformations.execution_request import ExecutionRequest
from cmm.transformations.operation import TransformationOperation
from cmm.transformations.operations import CopySymbolOperation


class PythonCopySymbolExecutor(OperationExecutor):
    """Copy one top-level function from a snapshot module into another module."""

    def __init__(
        self,
        locator: FunctionLocator | None = None,
        writer: PythonModuleWriter | None = None,
    ) -> None:
        self._locator = locator or FunctionLocator()
        self._writer = writer or PythonModuleWriter()

    @property
    def operation_type(self) -> type[TransformationOperation]:
        return CopySymbolOperation

    def execute(self, request: ExecutionRequest) -> ExecutionResult:
        if not isinstance(request.operation, CopySymbolOperation):
            return ExecutionResult(
                success=False,
                operation=request.operation,
                diagnostics=("Unsupported operation",),
            )

        context = request.metadata.get("semantic_context")
        if not isinstance(context, SemanticContext):
            return ExecutionResult(
                success=False,
                operation=request.operation,
                diagnostics=("Missing SemanticContext",),
            )

        source_module = self._module(context.snapshot, request.operation.source)
        target_module = self._module(context.snapshot, request.operation.destination)
        if source_module is None or source_module.parsed_module is None:
            return ExecutionResult(
                success=False,
                operation=request.operation,
                diagnostics=("Source module not found",),
            )
        if target_module is None or target_module.parsed_module is None:
            return ExecutionResult(
                success=False,
                operation=request.operation,
                diagnostics=("Target module not found",),
            )

        function = self._locator.find(
            source_module.parsed_module,
            request.operation.symbol,
        )
        if function is None:
            return ExecutionResult(
                success=False,
                operation=request.operation,
                diagnostics=("Function not found",),
            )
        if self._locator.find(target_module.parsed_module, function.name.value) is not None:
            return ExecutionResult(
                success=False,
                operation=request.operation,
                diagnostics=("Function already exists",),
            )

        updated_target = PythonModuleEditor(target_module).apply(
            AppendFunctionTransformer(function)
        )
        wrote = self._writer.write(updated_target)
        return ExecutionResult(
            success=True,
            operation=request.operation,
            created_paths=(updated_target.path,) if wrote else (),
        )

    def _module(
        self,
        snapshot: PythonProjectSnapshot,
        module_name: str,
    ) -> PythonModuleInfo | None:
        return next(
            (
                module
                for module in snapshot.modules
                if module.module_name == module_name
            ),
            None,
        )
