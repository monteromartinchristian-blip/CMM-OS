"""Read-only Python semantic executor for production action handling."""

from __future__ import annotations

from pathlib import Path
from typing import Mapping

from kernel.services.python_index import PythonIndex
from kernel.semantic import SemanticOperation, SemanticRuntime
from kernel.semantic_executors import create_default_semantic_registry

from cmm.execution.action_planner import ActionType
from cmm.execution.executor_registry import UnsupportedActionError
from cmm.execution.executors.base import ActionExecutor, ExecutionContext, ExecutionResult


class PythonExecutor(ActionExecutor):
    """Execute read-only and mutating Python operations through the semantic engine."""

    _SUPPORTED_ACTION_TYPES = {
        ActionType.PYTHON_LIST_CLASSES,
        ActionType.PYTHON_LIST_FUNCTIONS,
        ActionType.PYTHON_LIST_METHODS,
        ActionType.PYTHON_LIST_IMPORTS,
        ActionType.PYTHON_DESCRIBE_MODULE,
        ActionType.PYTHON_FIND_SYMBOL,
        ActionType.PYTHON_INSERT_METHOD,
        ActionType.PYTHON_REPLACE_METHOD,
        ActionType.PYTHON_DELETE_METHOD,
        ActionType.PYTHON_RENAME_METHOD,
        ActionType.PYTHON_ADD_IMPORT,
        ActionType.PYTHON_REMOVE_IMPORT,
        ActionType.PYTHON_CREATE_CLASS,
        ActionType.PYTHON_RENAME_CLASS,
        ActionType.PYTHON_DELETE_CLASS,
    }

    def __init__(self) -> None:
        self._engine = PythonIndex()
        self._semantic_runtime = SemanticRuntime(create_default_semantic_registry())

    @property
    def name(self) -> str:
        """Return the stable executor name."""
        return "python"

    def supported_action_types(self) -> set[ActionType]:
        """Return supported read-only Python semantic action types."""
        return set(self._SUPPORTED_ACTION_TYPES)

    def execute(self, context: ExecutionContext) -> ExecutionResult:
        """Dispatch the action to the mapped Python semantic operation."""
        action = context.action
        action_type = getattr(action, "action_type", None)
        if not isinstance(action_type, ActionType):
            raise UnsupportedActionError(f"Unsupported action type: {action_type}.")

        if action_type in self._MUTATING_ACTION_TYPES:
            return self._execute_mutation(context, action_type)

        operations = {
            ActionType.PYTHON_LIST_CLASSES.value: self._list_classes,
            ActionType.PYTHON_LIST_FUNCTIONS.value: self._list_functions,
            ActionType.PYTHON_LIST_METHODS.value: self._list_methods,
            ActionType.PYTHON_LIST_IMPORTS.value: self._list_imports,
            ActionType.PYTHON_DESCRIBE_MODULE.value: self._describe_module,
            ActionType.PYTHON_FIND_SYMBOL.value: self._find_symbol,
        }
        operation = operations.get(action_type.value)
        if operation is None:
            raise UnsupportedActionError(f"Unsupported action type: {action_type.value}.")

        target = getattr(action, "target", "")
        action_metadata = getattr(action, "metadata", {})
        metadata: Mapping[str, object] = (
            action_metadata if isinstance(action_metadata, Mapping) else {}
        )
        if not isinstance(target, str) or not target.strip():
            return ExecutionResult(
                success=False,
                message="Invalid path.",
                metadata={"error": "invalid_path"},
            )

        path_result = self._resolve_path(target, context.working_directory)
        if isinstance(path_result, ExecutionResult):
            return path_result

        module_index = self._index_module(path_result)
        if isinstance(module_index, ExecutionResult):
            return module_index

        return operation(path_result, module_index, metadata)

    _MUTATING_ACTION_TYPES = {
        ActionType.PYTHON_INSERT_METHOD,
        ActionType.PYTHON_REPLACE_METHOD,
        ActionType.PYTHON_DELETE_METHOD,
        ActionType.PYTHON_RENAME_METHOD,
        ActionType.PYTHON_ADD_IMPORT,
        ActionType.PYTHON_REMOVE_IMPORT,
        ActionType.PYTHON_CREATE_CLASS,
        ActionType.PYTHON_RENAME_CLASS,
        ActionType.PYTHON_DELETE_CLASS,
    }

    def _execute_mutation(self, context: ExecutionContext, action_type: ActionType) -> ExecutionResult:
        target = getattr(context.action, "target", "")
        resolved = self._resolve_path(target, context.working_directory)
        if isinstance(resolved, ExecutionResult):
            return resolved
        root = Path(context.working_directory).resolve(strict=True)
        try:
            resolved.relative_to(root)
        except ValueError:
            return self._error_result("Python path escapes the project.", resolved, "unsafe_path")
        metadata = getattr(context.action, "metadata", {})
        parameters = dict(metadata) if isinstance(metadata, Mapping) else {}
        parameters.pop("goal", None)
        parameters.pop("plan_step_order", None)
        parameters["path"] = str(resolved)
        operation = SemanticOperation(
            domain="python",
            operation_type=action_type.value.split(".", 1)[1],
            parameters=parameters,
            metadata={"source": "ActionRuntime", "action_id": str(getattr(context.action, "id", ""))},
        )
        result = self._semantic_runtime.execute_operation(operation)
        return ExecutionResult(
            success=result.success,
            message=result.message,
            artifacts=list(result.changes),
            metadata={**dict(result.data), "semantic_errors": list(result.errors), "operation": result.operation.serialize() if result.operation else None},
        )

    def _list_classes(
        self,
        path: Path,
        module_index: dict[str, object],
        metadata: Mapping[str, object],
    ) -> ExecutionResult:
        classes = [
            {
                "name": class_index.get("name"),
                "docstring": class_index.get("docstring") or "",
                "bases": list(class_index.get("bases", [])),
                "lineno": class_index.get("lineno"),
                "end_lineno": class_index.get("end_lineno"),
            }
            for class_index in module_index.get("classes", [])
        ]
        return ExecutionResult(
            success=True,
            message="Python classes listed.",
            metadata={"path": str(path), "classes": classes},
        )

    def _list_functions(
        self,
        path: Path,
        module_index: dict[str, object],
        metadata: Mapping[str, object],
    ) -> ExecutionResult:
        functions = [
            {
                "name": function_index.get("name"),
                "docstring": function_index.get("docstring") or "",
                "lineno": function_index.get("lineno"),
                "end_lineno": function_index.get("end_lineno"),
            }
            for function_index in module_index.get("functions", [])
        ]
        return ExecutionResult(
            success=True,
            message="Python functions listed.",
            metadata={"path": str(path), "functions": functions},
        )

    def _list_methods(
        self,
        path: Path,
        module_index: dict[str, object],
        metadata: Mapping[str, object],
    ) -> ExecutionResult:
        methods = []
        for class_index in module_index.get("classes", []):
            class_name = class_index.get("name")
            for method_index in class_index.get("methods", []):
                methods.append(
                    {
                        "class": class_name,
                        "name": method_index.get("name"),
                        "docstring": method_index.get("docstring") or "",
                        "lineno": method_index.get("lineno"),
                        "end_lineno": method_index.get("end_lineno"),
                    }
                )

        return ExecutionResult(
            success=True,
            message="Python methods listed.",
            metadata={"path": str(path), "methods": methods},
        )

    def _list_imports(
        self,
        path: Path,
        module_index: dict[str, object],
        metadata: Mapping[str, object],
    ) -> ExecutionResult:
        imports = list(module_index.get("imports", []))
        import_targets = [
            {
                "kind": target.get("kind"),
                "module": target.get("module"),
                "name": target.get("name"),
                "asname": target.get("asname"),
                "level": target.get("level"),
            }
            for target in module_index.get("import_targets", [])
        ]
        return ExecutionResult(
            success=True,
            message="Python imports listed.",
            metadata={
                "path": str(path),
                "imports": imports,
                "import_targets": import_targets,
            },
        )

    def _describe_module(
        self,
        path: Path,
        module_index: dict[str, object],
        metadata: Mapping[str, object],
    ) -> ExecutionResult:
        classes = module_index.get("classes", [])
        functions = module_index.get("functions", [])
        method_count = sum(len(class_index.get("methods", [])) for class_index in classes)

        return ExecutionResult(
            success=True,
            message="Python module described.",
            metadata={
                "path": str(path),
                "docstring": module_index.get("docstring") or "",
                "classes_count": len(classes),
                "functions_count": len(functions),
                "methods_count": method_count,
                "imports_count": len(module_index.get("imports", [])),
            },
        )

    def _find_symbol(
        self,
        path: Path,
        module_index: dict[str, object],
        metadata: Mapping[str, object],
    ) -> ExecutionResult:
        symbol = metadata.get("symbol")
        if not isinstance(symbol, str) or not symbol.strip():
            return ExecutionResult(
                success=False,
                message="Missing symbol query.",
                metadata={"error": "missing_symbol", "path": str(path)},
            )

        matches = []
        for class_index in module_index.get("classes", []):
            class_name = class_index.get("name")
            if class_name == symbol:
                matches.append(
                    {
                        "kind": "Class",
                        "name": class_name,
                        "lineno": class_index.get("lineno"),
                        "end_lineno": class_index.get("end_lineno"),
                    }
                )

            for method_index in class_index.get("methods", []):
                if method_index.get("name") == symbol:
                    matches.append(
                        {
                            "kind": "Method",
                            "class": class_name,
                            "name": method_index.get("name"),
                            "lineno": method_index.get("lineno"),
                            "end_lineno": method_index.get("end_lineno"),
                        }
                    )

        for function_index in module_index.get("functions", []):
            if function_index.get("name") == symbol:
                matches.append(
                    {
                        "kind": "Function",
                        "name": function_index.get("name"),
                        "lineno": function_index.get("lineno"),
                        "end_lineno": function_index.get("end_lineno"),
                    }
                )

        if not matches:
            return ExecutionResult(
                success=False,
                message="Symbol not found.",
                metadata={"error": "symbol_not_found", "path": str(path), "symbol": symbol},
            )

        return ExecutionResult(
            success=True,
            message="Python symbol lookup completed.",
            metadata={"path": str(path), "symbol": symbol, "matches": matches},
        )

    def _index_module(self, path: Path) -> dict[str, object] | ExecutionResult:
        try:
            index = self._engine.index(path)
        except FileNotFoundError:
            return self._error_result("File not found.", path, "not_found")
        except PermissionError:
            return self._error_result("Permission denied.", path, "permission_denied")
        except IsADirectoryError:
            return self._error_result("Path is a directory.", path, "is_directory")
        except UnicodeDecodeError:
            return self._error_result("Binary files are not supported.", path, "binary_file")
        except SyntaxError as error:
            return ExecutionResult(
                success=False,
                message=f"Invalid Python syntax: {error.msg}",
                metadata={
                    "error": "invalid_syntax",
                    "path": str(path),
                    "line": error.lineno,
                    "offset": error.offset,
                },
            )
        except OSError as error:
            return self._error_result(f"Unable to inspect module: {error}", path, "os_error")

        return index

    def _resolve_path(self, target: str, working_directory: str) -> Path | ExecutionResult:
        try:
            path = Path(target).expanduser()
            base_directory = Path(working_directory).expanduser()
            if not path.is_absolute():
                path = base_directory / path
            return path.resolve(strict=False)
        except (OSError, RuntimeError, ValueError) as error:
            return ExecutionResult(
                success=False,
                message=f"Invalid path: {error}",
                metadata={"error": "invalid_path", "path": target},
            )

    def _error_result(self, message: str, path: Path, code: str) -> ExecutionResult:
        return ExecutionResult(
            success=False,
            message=message,
            metadata={"error": code, "path": str(path)},
        )
