"""Default semantic executors used by the generic kernel runtime."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from kernel.semantic import SemanticExecutor, SemanticOperation, SemanticResult
from kernel.services.diff_engine import DiffEngine
from kernel.services.filesystem import FileSystemService
from kernel.services.python_editor import PythonEditor
from kernel.services.python_validator import PythonValidator


class FileSystemSemanticExecutor(SemanticExecutor):
    """Execute filesystem semantic operations."""

    _SUPPORTED = {"write_file", "read_file", "create_directory"}

    def __init__(self, service: FileSystemService | None = None) -> None:
        self._service = service or FileSystemService()

    def supports(self, operation: SemanticOperation) -> bool:
        return operation.domain == "filesystem" and operation.operation_type in self._SUPPORTED

    def validate_before(self, operation: SemanticOperation) -> None:
        super().validate_before(operation)
        if operation.operation_type == "write_file":
            operation.require("path", "content")
        else:
            operation.require("path")

    def execute(self, operation: SemanticOperation) -> SemanticResult:
        path = str(operation.parameters["path"])
        if operation.operation_type == "write_file":
            self._service.write(path, str(operation.parameters["content"]))
            return self._result(operation, "File written.", path, path, changes=(path,))
        if operation.operation_type == "read_file":
            content = self._service.read(path)
            return self._result(operation, "File read.", content, path)
        self._service.mkdir(path)
        return self._result(operation, "Directory created.", path, path, changes=(path,))

    def _result(
        self,
        operation: SemanticOperation,
        message: str,
        legacy_result: Any,
        path: str,
        changes: tuple[str, ...] = (),
    ) -> SemanticResult:
        return SemanticResult(
            success=True,
            message=message,
            data={"legacy_result": legacy_result, "path": path},
            changes=changes,
            operation=operation,
        )


class DiffSemanticExecutor(SemanticExecutor):
    """Execute text diff semantic operations."""

    _SUPPORTED = {"replace_block", "insert_after", "insert_before"}

    def __init__(self, engine: DiffEngine | None = None) -> None:
        self._engine = engine or DiffEngine()

    def supports(self, operation: SemanticOperation) -> bool:
        return operation.domain == "diff" and operation.operation_type in self._SUPPORTED

    def validate_before(self, operation: SemanticOperation) -> None:
        super().validate_before(operation)
        if operation.operation_type == "replace_block":
            operation.require("path", "old", "new")
        else:
            operation.require("path", "anchor", "content")

    def execute(self, operation: SemanticOperation) -> SemanticResult:
        path = str(operation.parameters["path"])
        if operation.operation_type == "replace_block":
            changed_path = self._engine.replace_block(path, operation.parameters["old"], operation.parameters["new"])
        elif operation.operation_type == "insert_after":
            changed_path = self._engine.insert_after(path, operation.parameters["anchor"], operation.parameters["content"])
        else:
            changed_path = self._engine.insert_before(path, operation.parameters["anchor"], operation.parameters["content"])
        return SemanticResult(
            success=True,
            message="Diff operation applied.",
            data={"legacy_result": changed_path, "path": str(changed_path)},
            changes=(str(changed_path),),
            operation=operation,
        )


class PythonSemanticExecutor(SemanticExecutor):
    """Execute Python semantic operations without coupling the runtime to Python."""

    _SUPPORTED = {
        "insert_method",
        "replace_method",
        "delete_method",
        "rename_method",
        "add_import",
        "remove_import",
        "create_class",
        "rename_class",
        "delete_class",
    }

    def __init__(
        self,
        editor: PythonEditor | None = None,
        validator: PythonValidator | None = None,
    ) -> None:
        self._editor = editor or PythonEditor()
        self._validator = validator or PythonValidator()

    def supports(self, operation: SemanticOperation) -> bool:
        return operation.domain == "python" and operation.operation_type in self._SUPPORTED

    def validate_before(self, operation: SemanticOperation) -> None:
        super().validate_before(operation)
        if operation.operation_type == "insert_method":
            operation.require("path", "class_name", "position", "code")
        elif operation.operation_type == "replace_method":
            operation.require("path", "class_name", "method_name", "code")
        elif operation.operation_type == "delete_method":
            operation.require("path", "class_name", "method_name")
        elif operation.operation_type == "rename_method":
            operation.require("path", "class_name", "old_name", "new_name")
        elif operation.operation_type == "add_import":
            operation.require("path", "module")
        elif operation.operation_type == "remove_import":
            operation.require("path", "module")
        elif operation.operation_type == "create_class":
            operation.require("path", "class_name")
        elif operation.operation_type == "rename_class":
            operation.require("path", "class_name", "new_name")
        elif operation.operation_type == "delete_class":
            operation.require("path", "class_name")
        self._validator.validate(Path(str(operation.parameters["path"])).read_text(encoding="utf-8"))

    def execute(self, operation: SemanticOperation) -> SemanticResult:
        path = str(operation.parameters["path"])
        changed = self._execute_python_operation(operation, path)
        warnings = self._warnings(operation, changed)
        if not changed and operation.operation_type in {
            "insert_method",
            "replace_method",
            "delete_method",
            "rename_method",
            "rename_class",
            "delete_class",
        }:
            message = f"Python symbol not found or unchanged: {operation.operation_type}."
            return SemanticResult(
                success=False,
                message=message,
                data={"legacy_result": changed, "changed": changed, "path": path},
                errors=(message,),
                operation=operation,
            )
        return SemanticResult(
            success=True,
            message="Python operation applied." if changed else "Python operation made no changes.",
            data={
                "legacy_result": changed,
                "changed": changed,
                "path": path,
                "warnings": warnings,
            },
            changes=(path,) if changed else (),
            operation=operation,
        )

    def _execute_python_operation(self, operation: SemanticOperation, path: str) -> bool:
        parameters = operation.parameters
        scope = parameters.get("scope")
        if operation.operation_type == "insert_method":
            return self._editor.insert_method(
                path,
                str(parameters["class_name"]),
                str(parameters["position"]),
                str(parameters["code"]),
                scope=scope,
            )
        if operation.operation_type == "replace_method":
            return self._editor.replace_method(
                path,
                str(parameters["class_name"]),
                str(parameters["method_name"]),
                str(parameters["code"]),
                scope=scope,
            )
        if operation.operation_type == "delete_method":
            return self._editor.delete_method(
                path,
                str(parameters["class_name"]),
                str(parameters["method_name"]),
                scope=scope,
            )
        if operation.operation_type == "rename_method":
            return self._editor.rename_method(
                path,
                str(parameters["class_name"]),
                str(parameters["old_name"]),
                str(parameters["new_name"]),
                scope=scope,
            )
        if operation.operation_type == "add_import":
            return self._editor.ensure_import(
                path,
                str(parameters["module"]),
                name=parameters.get("name"),
                alias=parameters.get("alias"),
                level=int(parameters.get("level") or 0),
            )
        if operation.operation_type == "remove_import":
            return self._editor.remove_import(
                path,
                str(parameters["module"]),
                name=parameters.get("name"),
                alias=parameters.get("alias"),
                level=int(parameters.get("level") or 0),
            )
        if operation.operation_type == "create_class":
            return self._editor.create_class(
                path,
                str(parameters["class_name"]),
                base_classes=parameters.get("base_classes"),
                methods=parameters.get("methods"),
                scope=scope,
            )
        if operation.operation_type == "rename_class":
            return self._editor.rename_class(
                path,
                str(parameters["class_name"]),
                str(parameters["new_name"]),
                scope=scope,
            )
        if operation.operation_type == "delete_class":
            return self._editor.delete_class(
                path,
                str(parameters["class_name"]),
                scope=scope,
            )
        raise ValueError(f"Unsupported Python operation: {operation.operation_type}")

    def _warnings(self, operation: SemanticOperation, changed: bool) -> list[str]:
        if not changed:
            return []
        if operation.operation_type in {"rename_method", "rename_class"}:
            return ["References were not updated automatically."]
        return []

    def validate_after(
        self,
        operation: SemanticOperation,
        result: SemanticResult,
    ) -> SemanticResult:
        if result.success:
            self._validator.validate(Path(str(operation.parameters["path"])).read_text(encoding="utf-8"))
        return result


class NoOpSemanticExecutor(SemanticExecutor):
    """Generic no-op executor for safe fallback and Git smoke flows."""

    def supports(self, operation: SemanticOperation) -> bool:
        return operation.domain in {"noop", "git"} and operation.operation_type in {"noop", "status"}

    def execute(self, operation: SemanticOperation) -> SemanticResult:
        return SemanticResult(
            success=True,
            message="No operation executed.",
            data={"legacy_result": None, "operation": operation.type_id},
            operation=operation,
        )


class TransformationSemanticExecutor(SemanticExecutor):
    """Prepared adapter boundary for transformation operations."""

    def supports(self, operation: SemanticOperation) -> bool:
        return operation.domain == "transformation"

    def execute(self, operation: SemanticOperation) -> SemanticResult:
        return SemanticResult(
            success=True,
            message="Transformation operation adapted.",
            data={
                "legacy_result": operation.serialize(),
                "operation": operation.operation_type,
                "parameters": dict(operation.parameters),
            },
            operation=operation,
        )


def create_default_semantic_registry():
    """Create the default semantic executor registry."""

    from kernel.semantic import SemanticExecutorRegistry

    registry = SemanticExecutorRegistry()
    registry.register_many(
        [
            FileSystemSemanticExecutor(),
            DiffSemanticExecutor(),
            PythonSemanticExecutor(),
            NoOpSemanticExecutor(),
            TransformationSemanticExecutor(),
        ]
    )
    return registry
