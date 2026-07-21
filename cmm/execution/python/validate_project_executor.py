"""Read-only LibCST executor for validate-project operations."""

from cmm.execution.execution_result import ExecutionResult
from cmm.execution.operation_executor import OperationExecutor
from cmm.execution.python.python_project_parser import PythonProjectParser
from pathlib import Path
from cmm.execution.python.semantic_context_builder import SemanticContextBuilder
from cmm.transformations.execution_request import ExecutionRequest
from cmm.transformations.operation import TransformationOperation
from cmm.transformations.operations import ValidateProjectOperation


class PythonValidateProjectExecutor(OperationExecutor):
    """Validate every Python module in a project without modifying files."""

    def __init__(
        self,
        parser: PythonProjectParser | None = None,
        context_builder: SemanticContextBuilder | None = None,
    ) -> None:
        self._parser = parser or PythonProjectParser()
        self._context_builder = context_builder or SemanticContextBuilder()

    @property
    def operation_type(self) -> type[TransformationOperation]:
        return ValidateProjectOperation

    def execute(self, request: ExecutionRequest) -> ExecutionResult:
        project_root = request.metadata.get("project_root")
        if not isinstance(project_root, str) or not project_root.strip():
            return ExecutionResult(
                success=False,
                operation=request.operation,
                diagnostics=("Missing project_root",),
            )

        snapshot = self._parser.parse(Path(project_root))
        semantic_context = self._context_builder.build(snapshot)
        return ExecutionResult(
            success=not snapshot.errors,
            operation=request.operation,
            diagnostics=snapshot.errors,
            metadata={
                "snapshot": snapshot,
                "semantic_context": semantic_context,
            },
        )
