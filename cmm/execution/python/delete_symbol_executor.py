"""LibCST executor for deleting top-level Python symbols."""

from cmm.execution.execution_result import ExecutionResult
from cmm.execution.execution_context import ExecutionContext
from cmm.execution.operation_executor import OperationExecutor
from cmm.execution.python.python_module_editor import PythonModuleEditor
from cmm.execution.python.python_module_writer import PythonModuleWriter
from cmm.execution.python.semantic_context import SemanticContext
from cmm.execution.python.visitors import DeleteSymbolTransformer, SymbolLocator
from cmm.transformations.execution_request import ExecutionRequest
from cmm.transformations.operation import TransformationOperation
from cmm.transformations.operations import DeleteSymbolOperation


class PythonDeleteSymbolExecutor(OperationExecutor):
    """Delete one top-level function from a semantic-context module."""

    def __init__(
        self,
        locator: SymbolLocator | None = None,
        writer: PythonModuleWriter | None = None,
    ) -> None:
        self._locator = locator or SymbolLocator()
        self._writer = writer or PythonModuleWriter()

    @property
    def operation_type(self) -> type[TransformationOperation]:
        return DeleteSymbolOperation

    def execute(self, request: ExecutionRequest) -> ExecutionResult:
        if not isinstance(request.operation, DeleteSymbolOperation):
            return ExecutionResult(
                success=False,
                operation=request.operation,
                diagnostics=("Unsupported operation",),
            )

        context = request.metadata.get("semantic_context")
        execution_context = request.metadata.get("execution_context")
        if not isinstance(context, SemanticContext):
            return ExecutionResult(
                success=False,
                operation=request.operation,
                diagnostics=("Missing SemanticContext",),
            )
        module = next(
            (
                item
                for item in context.snapshot.modules
                if item.module_name == request.operation.module
            ),
            None,
        )
        if module is None or module.parsed_module is None:
            return ExecutionResult(
                success=False,
                operation=request.operation,
                diagnostics=(f"{request.operation.symbol_kind.title()} not found",),
            )
        if isinstance(execution_context, ExecutionContext):
            execution_context.resolve_project_path(module.path)
        if self._locator.find(
            module.parsed_module,
            request.operation.symbol,
            request.operation.symbol_kind,
        ) is None:
            return ExecutionResult(
                success=False,
                operation=request.operation,
                diagnostics=(f"{request.operation.symbol_kind.title()} not found",),
            )

        updated_module = PythonModuleEditor(module).apply(
            DeleteSymbolTransformer(
                request.operation.symbol,
                request.operation.symbol_kind,
            )
        )
        wrote = self._writer.write(updated_module)
        return ExecutionResult(
            success=True,
            operation=request.operation,
            created_paths=(updated_module.path,) if wrote else (),
        )
