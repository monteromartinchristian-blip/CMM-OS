"""Read-only Git executor for production action handling."""

from __future__ import annotations

from pathlib import Path
from typing import Mapping

from cmm.execution.action_planner import ActionType
from cmm.execution.executor_registry import UnsupportedActionError
from cmm.execution.executors.base import ActionExecutor, ExecutionContext, ExecutionResult
from cmm.execution.services import GitService, GitServiceError


class GitExecutor(ActionExecutor):
    """Execute controlled read-only and isolation Git operations."""

    _SUPPORTED_ACTION_TYPES = {
        ActionType.GIT_STATUS,
        ActionType.GIT_CURRENT_BRANCH,
        ActionType.GIT_LIST_BRANCHES,
        ActionType.GIT_LOG,
        ActionType.GIT_DIFF,
        ActionType.GIT_SHOW,
        ActionType.GIT_LIST_TAGS,
        ActionType.GIT_CREATE_BRANCH,
        ActionType.GIT_SWITCH_BRANCH,
        ActionType.GIT_RESTORE_WORKTREE,
        ActionType.GIT_LIST_CHANGED_FILES,
    }

    def __init__(self, timeout: float = 15.0) -> None:
        self._service = GitService(timeout=timeout)

    @property
    def name(self) -> str:
        """Return the stable executor name."""
        return "git"

    def supported_action_types(self) -> set[ActionType]:
        """Return supported read-only Git action types."""
        return set(self._SUPPORTED_ACTION_TYPES)

    def execute(self, context: ExecutionContext) -> ExecutionResult:
        """Dispatch the action to the mapped read-only Git operation."""
        action = context.action
        action_type = getattr(action, "action_type", None)
        if not isinstance(action_type, ActionType):
            raise UnsupportedActionError(f"Unsupported action type: {action_type}.")

        operations = {
            ActionType.GIT_STATUS.value: self._status,
            ActionType.GIT_CURRENT_BRANCH.value: self._current_branch,
            ActionType.GIT_LIST_BRANCHES.value: self._list_branches,
            ActionType.GIT_LOG.value: self._log,
            ActionType.GIT_DIFF.value: self._diff,
            ActionType.GIT_SHOW.value: self._show,
            ActionType.GIT_LIST_TAGS.value: self._list_tags,
            ActionType.GIT_CREATE_BRANCH.value: self._create_branch,
            ActionType.GIT_SWITCH_BRANCH.value: self._switch_branch,
            ActionType.GIT_RESTORE_WORKTREE.value: self._restore_worktree,
            ActionType.GIT_LIST_CHANGED_FILES.value: self._list_changed_files,
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
                message="Invalid repository path.",
                metadata={"error": "invalid_path"},
            )

        path_result = self._resolve_path(target, context.working_directory)
        if isinstance(path_result, ExecutionResult):
            return path_result

        return operation(path_result, metadata)

    def _status(self, path: Path, metadata: Mapping[str, object]) -> ExecutionResult:
        return self._service_result("Git status retrieved.", self._service.status, path)

    def _current_branch(self, path: Path, metadata: Mapping[str, object]) -> ExecutionResult:
        return self._service_result("Git current branch retrieved.", self._service.current_branch, path)

    def _list_branches(self, path: Path, metadata: Mapping[str, object]) -> ExecutionResult:
        return self._service_result("Git branches listed.", self._service.list_branches, path)

    def _log(self, path: Path, metadata: Mapping[str, object]) -> ExecutionResult:
        limit = metadata.get("limit", 10)
        if not isinstance(limit, int) or limit <= 0:
            return ExecutionResult(
                success=False,
                message="Invalid log limit.",
                metadata={"error": "invalid_input", "field": "limit", "value": limit},
            )

        return self._service_result("Git log retrieved.", self._service.log, path, limit)

    def _diff(self, path: Path, metadata: Mapping[str, object]) -> ExecutionResult:
        ref = metadata.get("ref", "HEAD")
        if not isinstance(ref, str) or not ref.strip():
            return ExecutionResult(
                success=False,
                message="Invalid diff reference.",
                metadata={"error": "invalid_input", "field": "ref", "value": ref},
            )

        return self._service_result("Git diff retrieved.", self._service.diff, path, ref)

    def _show(self, path: Path, metadata: Mapping[str, object]) -> ExecutionResult:
        git_object = metadata.get("object")
        if not isinstance(git_object, str) or not git_object.strip():
            return ExecutionResult(
                success=False,
                message="Missing Git object.",
                metadata={"error": "invalid_input", "field": "object", "value": git_object},
            )

        return self._service_result("Git object shown.", self._service.show, path, git_object)

    def _list_tags(self, path: Path, metadata: Mapping[str, object]) -> ExecutionResult:
        return self._service_result("Git tags listed.", self._service.list_tags, path)

    def _create_branch(self, path: Path, metadata: Mapping[str, object]) -> ExecutionResult:
        return self._branch_result("Git branch created.", self._service.create_branch, path, metadata)

    def _switch_branch(self, path: Path, metadata: Mapping[str, object]) -> ExecutionResult:
        return self._branch_result("Git branch switched.", self._service.switch_branch, path, metadata)

    def _restore_worktree(self, path: Path, metadata: Mapping[str, object]) -> ExecutionResult:
        return self._service_result("Git worktree restored.", self._service.restore_worktree, path)

    def _list_changed_files(self, path: Path, metadata: Mapping[str, object]) -> ExecutionResult:
        return self._service_result("Git changed files listed.", self._service.list_changed_files, path)

    def _branch_result(self, message: str, operation, path: Path, metadata: Mapping[str, object]) -> ExecutionResult:
        branch = metadata.get("branch")
        if not isinstance(branch, str) or not branch.strip():
            return ExecutionResult(False, "Missing branch name.", metadata={"error": "invalid_input", "field": "branch"})
        return self._service_result(message, operation, path, branch)

    def _service_result(self, message: str, operation, path: Path, *args: object) -> ExecutionResult:
        try:
            payload = operation(path, *args)
        except GitServiceError as error:
            return ExecutionResult(
                success=False,
                message=error.message,
                metadata={"error": error.code, "path": str(path)},
            )

        return ExecutionResult(success=True, message=message, metadata=payload)

    def _resolve_path(self, target: str, working_directory: str) -> Path | ExecutionResult:
        try:
            path = Path(target).expanduser()
            base_directory = Path(working_directory).expanduser()
            if not path.is_absolute():
                path = base_directory / path
            resolved = path.resolve(strict=False)
            resolved.relative_to(base_directory.resolve(strict=True))
            return resolved
        except ValueError:
            return ExecutionResult(False, "Git path escapes the project.", metadata={"error": "unsafe_path", "path": target})
        except (OSError, RuntimeError, ValueError) as error:
            return ExecutionResult(
                success=False,
                message=f"Invalid path: {error}",
                metadata={"error": "invalid_path", "path": target},
            )
