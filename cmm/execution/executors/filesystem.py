"""Safe mutating filesystem actions for project-scoped execution."""

from __future__ import annotations

import os
from pathlib import Path, PurePath
import tempfile

from cmm.execution.action_planner import ActionType
from cmm.execution.executor_registry import UnsupportedActionError
from cmm.execution.executors.base import ActionExecutor, ExecutionContext, ExecutionResult


class FilesystemExecutor(ActionExecutor):
    """Execute project-relative filesystem mutations atomically where possible."""

    _SUPPORTED = {
        ActionType.FILESYSTEM_EXISTS,
        ActionType.FILESYSTEM_IS_FILE,
        ActionType.FILESYSTEM_IS_DIRECTORY,
        ActionType.FILESYSTEM_READ_FILE,
        ActionType.FILESYSTEM_LIST_DIRECTORY,
        ActionType.FILESYSTEM_CREATE_FILE,
        ActionType.FILESYSTEM_WRITE_FILE,
        ActionType.FILESYSTEM_APPEND_FILE,
        ActionType.FILESYSTEM_DELETE_FILE,
        ActionType.FILESYSTEM_MOVE_FILE,
        ActionType.FILESYSTEM_CREATE_DIRECTORY,
        ActionType.FILESYSTEM_DELETE_DIRECTORY,
    }

    @property
    def name(self) -> str:
        return "filesystem"

    def supported_action_types(self) -> set[ActionType]:
        return set(self._SUPPORTED)

    def execute(self, context: ExecutionContext) -> ExecutionResult:
        action_type = getattr(context.action, "action_type", None)
        if action_type not in self._SUPPORTED:
            raise UnsupportedActionError(f"Unsupported action type: {action_type}.")
        if action_type in {
            ActionType.FILESYSTEM_EXISTS,
            ActionType.FILESYSTEM_IS_FILE,
            ActionType.FILESYSTEM_IS_DIRECTORY,
            ActionType.FILESYSTEM_READ_FILE,
            ActionType.FILESYSTEM_LIST_DIRECTORY,
        }:
            safe_path = self._safe_path(getattr(context.action, "target", ""), context.working_directory)
            if isinstance(safe_path, ExecutionResult):
                return safe_path
            from cmm.execution.executors.read_only_filesystem import ReadOnlyFilesystemExecutor

            return ReadOnlyFilesystemExecutor().execute(context)
        metadata = getattr(context.action, "metadata", {})
        if not isinstance(metadata, dict) and not hasattr(metadata, "get"):
            metadata = {}
        target = getattr(context.action, "target", "")
        path = self._safe_path(target, context.working_directory)
        if isinstance(path, ExecutionResult):
            return path

        try:
            overwrite = bool(metadata.get("overwrite", False))
            if action_type == ActionType.FILESYSTEM_CREATE_FILE:
                content = str(metadata.get("content", ""))
                if path.exists() and not overwrite:
                    return self._error("File already exists.", path, "exists")
                self._atomic_write(path, content, overwrite=True)
                return self._success("File created.", path)
            if action_type == ActionType.FILESYSTEM_WRITE_FILE:
                if path.exists() and not overwrite and not bool(metadata.get("allow_existing", False)):
                    return self._error("File already exists; overwrite is required.", path, "exists")
                self._atomic_write(path, str(metadata.get("content", "")), overwrite=True)
                return self._success("File written.", path)
            if action_type == ActionType.FILESYSTEM_APPEND_FILE:
                if not path.exists() or not path.is_file():
                    return self._error("File not found.", path, "not_found")
                current = path.read_text(encoding="utf-8")
                self._atomic_write(path, current + str(metadata.get("content", "")), overwrite=True)
                return self._success("File appended.", path)
            if action_type == ActionType.FILESYSTEM_DELETE_FILE:
                if not path.exists():
                    return self._success("File already absent.", path, changed=False)
                if not path.is_file() or path.is_symlink():
                    return self._error("Target is not a regular file.", path, "invalid_target")
                path.unlink()
                return self._success("File deleted.", path)
            if action_type == ActionType.FILESYSTEM_MOVE_FILE:
                destination = self._safe_path(str(metadata.get("destination", "")), context.working_directory)
                if isinstance(destination, ExecutionResult):
                    return destination
                if not path.is_file() or path.is_symlink():
                    return self._error("Source file not found.", path, "not_found")
                if destination.exists() and not overwrite:
                    return self._error("Destination already exists.", destination, "exists")
                destination.parent.mkdir(parents=True, exist_ok=True)
                os.replace(path, destination)
                return ExecutionResult(True, "File moved.", [str(path), str(destination)], {"path": str(path), "destination": str(destination)})
            if action_type == ActionType.FILESYSTEM_CREATE_DIRECTORY:
                path.mkdir(parents=True, exist_ok=True)
                return self._success("Directory created.", path, changed=True)
            if not path.exists():
                return self._success("Directory already absent.", path, changed=False)
            if not path.is_dir() or path.is_symlink():
                return self._error("Target is not a directory.", path, "invalid_target")
            path.rmdir()
            return self._success("Directory deleted.", path)
        except (OSError, UnicodeDecodeError) as error:
            return self._error(str(error), path, "filesystem_error")

    def _safe_path(self, target: object, working_directory: str) -> Path | ExecutionResult:
        if not isinstance(target, str) or not target.strip():
            return self._error("Invalid path.", Path(working_directory), "invalid_path")
        raw = PurePath(target)
        if raw.is_absolute() or ".." in raw.parts:
            return self._error("Absolute paths and traversal are not allowed.", Path(target), "unsafe_path")
        root = Path(working_directory).resolve(strict=True)
        candidate = root.joinpath(*raw.parts)
        try:
            resolved = candidate.resolve(strict=False)
            resolved.relative_to(root)
            existing = candidate.parent.resolve(strict=False)
            existing.relative_to(root)
        except (OSError, RuntimeError, ValueError) as error:
            return self._error(f"Path escapes project: {target}", candidate, "unsafe_path")
        return resolved

    def _atomic_write(self, path: Path, content: str, *, overwrite: bool) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() and not overwrite:
            raise FileExistsError(path)
        temporary: Path | None = None
        try:
            with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
                temporary = Path(handle.name)
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    def _success(self, message: str, path: Path, *, changed: bool = True) -> ExecutionResult:
        return ExecutionResult(changed or not path.exists(), message, [str(path)] if changed else [], {"path": str(path), "changed": changed})

    def _error(self, message: str, path: Path, code: str) -> ExecutionResult:
        return ExecutionResult(False, message, metadata={"error": code, "path": str(path)})
