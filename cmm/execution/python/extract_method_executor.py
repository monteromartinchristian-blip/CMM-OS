"""Executor for real LibCST extract-method operations."""

from cmm.execution.execution_context import ExecutionContext
from cmm.execution.execution_result import ExecutionResult
from cmm.execution.operation_executor import OperationExecutor
from cmm.execution.python.extract_method_analysis import analyze_method_extraction
from cmm.execution.python.python_module_editor import PythonModuleEditor
from cmm.execution.python.python_module_writer import PythonModuleWriter
from cmm.execution.python.semantic_context import SemanticContext
from cmm.execution.python.visitors import ExtractMethodTransformer
from cmm.transformations.execution_request import ExecutionRequest
from cmm.transformations.operation import TransformationOperation
from cmm.transformations.operations import ExtractMethodOperation


class PythonExtractMethodExecutor(OperationExecutor):
    @property
    def operation_type(self) -> type[TransformationOperation]:
        return ExtractMethodOperation

    def __init__(self, writer: PythonModuleWriter | None = None) -> None:
        self._writer = writer or PythonModuleWriter()

    def execute(self, request: ExecutionRequest) -> ExecutionResult:
        operation = request.operation
        if not isinstance(operation, ExtractMethodOperation):
            return ExecutionResult(False, operation, ("Unsupported operation",))
        context = request.metadata.get("semantic_context")
        execution_context = request.metadata.get("execution_context")
        if not isinstance(context, SemanticContext) or not isinstance(execution_context, ExecutionContext):
            return ExecutionResult(False, operation, ("Missing execution context",))
        module = next((item for item in context.snapshot.modules if item.module_name == operation.module), None)
        if module is None or module.parsed_module is None:
            return ExecutionResult(False, operation, ("Module not found",))
        analysis, message = analyze_method_extraction(
            module.path,
            operation.class_name,
            operation.method_name,
            operation.new_method_name,
            operation.start_index,
            operation.end_index,
        )
        if analysis is None:
            return ExecutionResult(False, operation, (message,))
        updated = PythonModuleEditor(module).apply(
            ExtractMethodTransformer(
                operation.class_name,
                operation.method_name,
                operation.new_method_name,
                analysis,
            )
        )
        if self._writer.write(updated):
            return ExecutionResult(True, operation, created_paths=(updated.path,))
        return ExecutionResult(False, operation, ("Extraction produced no change",))
