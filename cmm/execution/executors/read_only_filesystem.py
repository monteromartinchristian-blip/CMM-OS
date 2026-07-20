"""Read-only filesystem executor for production action handling."""

from __future__ import annotations

from pathlib import Path

from cmm.execution.action_planner import ActionType
from cmm.execution.executor_registry import UnsupportedActionError
from cmm.execution.executors.base import ActionExecutor, ExecutionContext, ExecutionResult


class ReadOnlyFilesystemExecutor(ActionExecutor):
    """Execute filesystem inspection actions without mutating the filesystem."""

    _SUPPORTED_ACTION_TYPES = {
        ActionType.FILESYSTEM_EXISTS,
        ActionType.FILESYSTEM_IS_FILE,
        ActionType.FILESYSTEM_IS_DIRECTORY,
        ActionType.FILESYSTEM_READ_FILE,
        ActionType.FILESYSTEM_LIST_DIRECTORY,
    }

    @property
    def name(self) -> str:
        """Return the stable executor name."""
        return "read-only-filesystem"

    def supported_action_types(self) -> set[ActionType]:
        """Return supported read-only filesystem action types."""
        return set(self._SUPPORTED_ACTION_TYPES)

    def execute(self, context: ExecutionContext) -> ExecutionResult:
        """Dispatch the action to the mapped read-only filesystem operation."""
        action = context.action
        action_type = getattr(action, "action_type", None)
        if not isinstance(action_type, ActionType):
            raise UnsupportedActionError(f"Unsupported action type: {action_type}.")

        operations = {
            ActionType.FILESYSTEM_EXISTS.value: self._exists,
            ActionType.FILESYSTEM_IS_FILE.value: self._is_file,
            ActionType.FILESYSTEM_IS_DIRECTORY.value: self._is_directory,
            ActionType.FILESYSTEM_READ_FILE.value: self._read_file,
            ActionType.FILESYSTEM_LIST_DIRECTORY.value: self._list_directory,
        }
        operation = operations.get(action_type.value)
        if operation is None:
            raise UnsupportedActionError(f"Unsupported action type: {action_type.value}.")

        target = getattr(action, "target", "")
        if not isinstance(target, str) or not target.strip():
            return ExecutionResult(
                success=False,
                message="Invalid path.",
                metadata={"error": "invalid_path"},
            )

        path_result = self._resolve_path(target, context.working_directory)
        if isinstance(path_result, ExecutionResult):
            return path_result

        return operation(path_result)

    def _exists(self, path: Path) -> ExecutionResult:
        return ExecutionResult(
            success=True,
            message="Filesystem existence check completed.",
            metadata={"exists": path.exists()},
        )

    def _is_file(self, path: Path) -> ExecutionResult:
        return ExecutionResult(
            success=True,
            message="Filesystem file check completed.",
            metadata={"is_file": path.is_file()},
        )

    def _is_directory(self, path: Path) -> ExecutionResult:
        return ExecutionResult(
            success=True,
            message="Filesystem directory check completed.",
            metadata={"is_directory": path.is_dir()},
        )

    def _read_file(self, path: Path) -> ExecutionResult:
        try:
            content = path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return self._error_result("File not found.", path, "not_found")
        except PermissionError:
            return self._error_result("Permission denied.", path, "permission_denied")
        except IsADirectoryError:
            return self._error_result("Path is a directory.", path, "is_directory")
        except UnicodeDecodeError:
            return self._error_result("Binary files are not supported.", path, "binary_file")
        except OSError as error:
            return self._error_result(f"Unable to read file: {error}", path, "os_error")

        return ExecutionResult(
            success=True,
            message="Filesystem file read completed.",
            metadata={
                "path": str(path),
                "content": content,
                "encoding": "utf-8",
            },
        )

    def _list_directory(self, path: Path) -> ExecutionResult:
        try:
            if not path.exists():
                return self._error_result("Directory not found.", path, "not_found")
            if not path.is_dir():
                return self._error_result("Path is not a directory.", path, "not_directory")

            entries = []
            for entry in sorted(path.iterdir(), key=lambda item: item.name):
                entry_type = "directory" if entry.is_dir() else "file"
                size = None
                if entry.is_file():
                    try:
                        size = entry.stat().st_size
                    except OSError:
                        size = None

                entries.append(
                    {
                        "name": entry.name,
                        "path": str(entry),
                        "type": entry_type,
                        "size": size,
                    }
                )
        except PermissionError:
            return self._error_result("Permission denied.", path, "permission_denied")
        except OSError as error:
            return self._error_result(f"Unable to list directory: {error}", path, "os_error")

        return ExecutionResult(
            success=True,
            message="Filesystem directory listing completed.",
            metadata={"entries": entries},
        )

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
