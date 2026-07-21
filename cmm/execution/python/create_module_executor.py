"""Filesystem-backed executor for create-module operations."""

from pathlib import Path

from cmm.execution.execution_result import ExecutionResult
from cmm.execution.operation_executor import OperationExecutor
from cmm.transformations.execution_request import ExecutionRequest
from cmm.transformations.operation import TransformationOperation
from cmm.transformations.operations import CreateModuleOperation


class PythonCreateModuleExecutor(OperationExecutor):
    """Create a Python module and missing package initialization files."""

    @property
    def operation_type(self) -> type[TransformationOperation]:
        return CreateModuleOperation

    def execute(self, request: ExecutionRequest) -> ExecutionResult:
        if not isinstance(request.operation, CreateModuleOperation):
            return ExecutionResult(
                success=False,
                operation=request.operation,
                diagnostics=("Unsupported operation",),
            )

        operation = request.operation
        module_path = self._module_path(operation)
        if module_path.exists():
            return ExecutionResult(
                success=False,
                operation=operation,
                diagnostics=("Module already exists",),
            )

        created_paths = self._create_parent_packages(
            Path(operation.project_root),
            operation.module_name,
        )
        module_path.touch(exist_ok=False)
        created_paths.append(module_path)
        return ExecutionResult(
            success=True,
            operation=operation,
            created_paths=tuple(created_paths),
        )

    def _module_path(self, operation: CreateModuleOperation) -> Path:
        return (
            Path(operation.project_root)
            .joinpath(*operation.module_name.split("."))
            .with_suffix(".py")
        )

    def _create_parent_packages(
        self,
        project_root: Path,
        module_name: str,
    ) -> list[Path]:
        created_paths = []
        package_path = project_root
        for package_name in module_name.split(".")[:-1]:
            package_path /= package_name
            if not package_path.exists():
                package_path.mkdir()
                created_paths.append(package_path)

            init_path = package_path / "__init__.py"
            if not init_path.exists():
                init_path.touch(exist_ok=False)
                created_paths.append(init_path)

        return created_paths
