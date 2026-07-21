"""LibCST executor for minimal project-wide from-import updates."""

from cmm.execution.execution_result import ExecutionResult
from cmm.execution.operation_executor import OperationExecutor
from cmm.execution.python.import_resolver import ImportResolver
from cmm.execution.python.python_module_editor import PythonModuleEditor
from cmm.execution.python.python_module_writer import PythonModuleWriter
from cmm.execution.python.semantic_context import SemanticContext
from cmm.execution.python.visitors import UpdateImportTransformer
from cmm.transformations.execution_request import ExecutionRequest
from cmm.transformations.operation import TransformationOperation
from cmm.transformations.operations import UpdateImportsOperation


class PythonUpdateImportsExecutor(OperationExecutor):
    """Update simple symbol imports across modules in a semantic context."""

    def __init__(self, writer: PythonModuleWriter | None = None) -> None:
        self._writer = writer or PythonModuleWriter()

    @property
    def operation_type(self) -> type[TransformationOperation]:
        return UpdateImportsOperation

    def execute(self, request: ExecutionRequest) -> ExecutionResult:
        context = request.metadata.get("semantic_context")
        old_module = request.metadata.get("old_module")
        new_module = request.metadata.get("new_module")
        symbol_name = request.metadata.get("symbol_name")
        if (
            not isinstance(context, SemanticContext)
            or not isinstance(old_module, str)
            or not isinstance(new_module, str)
            or not isinstance(symbol_name, str)
        ):
            return ExecutionResult(
                success=False,
                operation=request.operation,
                diagnostics=("Missing import update parameters",),
            )

        resolver = ImportResolver(context)
        written_paths = []
        for module in context.snapshot.modules:
            if module.parsed_module is None:
                continue
            resolver.resolve_symbol(module.module_name, symbol_name)
            transformer = UpdateImportTransformer(
                old_module,
                new_module,
                symbol_name,
            )
            updated_module = PythonModuleEditor(module).apply(transformer)
            if transformer.changed and self._writer.write(updated_module):
                written_paths.append(updated_module.path)

        return ExecutionResult(
            success=True,
            operation=request.operation,
            created_paths=tuple(written_paths),
        )
