from __future__ import annotations

from pathlib import Path
import shutil
import subprocess

import pytest

from cmm.execution import Action, ActionType, UnsupportedActionError
from cmm.execution.executors import ExecutionContext, GitExecutor


def test_git_executor_read_only_operations_succeed(tmp_path) -> None:
    if shutil.which("git") is None:
        pytest.skip("git command is not available")

    repository = _init_repo(tmp_path)
    _run_git(repository, "branch", "feature")
    _run_git(repository, "tag", "v0.1.0")

    file_path = repository / "README.md"
    file_path.write_text("hello\nworld\n", encoding="utf-8")

    executor = GitExecutor()

    status_result = executor.execute(_context(_action(ActionType.GIT_STATUS, str(repository)), tmp_path))
    branch_result = executor.execute(
        _context(_action(ActionType.GIT_CURRENT_BRANCH, str(repository)), tmp_path)
    )
    branches_result = executor.execute(
        _context(_action(ActionType.GIT_LIST_BRANCHES, str(repository)), tmp_path)
    )
    log_result = executor.execute(
        _context(_action(ActionType.GIT_LOG, str(repository), {"limit": 5}), tmp_path)
    )
    diff_result = executor.execute(_context(_action(ActionType.GIT_DIFF, str(repository)), tmp_path))
    show_result = executor.execute(
        _context(_action(ActionType.GIT_SHOW, str(repository), {"object": "HEAD"}), tmp_path)
    )
    tags_result = executor.execute(_context(_action(ActionType.GIT_LIST_TAGS, str(repository)), tmp_path))

    assert status_result.success is True
    assert "porcelain" in status_result.metadata
    assert "short" in status_result.metadata

    assert branch_result.success is True
    assert isinstance(branch_result.metadata["branch"], str)
    assert branch_result.metadata["branch"]

    assert branches_result.success is True
    assert "feature" in branches_result.metadata["branches"]

    assert log_result.success is True
    assert len(log_result.metadata["entries"]) >= 1
    assert "commit" in log_result.metadata["entries"][0]

    assert diff_result.success is True
    assert "diff" in diff_result.metadata

    assert show_result.success is True
    assert "commit" in show_result.metadata["output"].lower()

    assert tags_result.success is True
    assert "v0.1.0" in tags_result.metadata["tags"]


def test_unsupported_action_is_rejected(tmp_path) -> None:
    executor = GitExecutor()

    with pytest.raises(UnsupportedActionError, match="Unsupported action type: READ_METHOD"):
        executor.execute(_context(_action(ActionType.READ_METHOD, str(tmp_path)), tmp_path))


def test_missing_repository_is_handled(tmp_path) -> None:
    executor = GitExecutor()

    result = executor.execute(
        _context(_action(ActionType.GIT_STATUS, str(tmp_path / "does-not-exist")), tmp_path)
    )

    assert result.success is False
    assert result.metadata["error"] == "not_found"


def test_non_git_directory_is_handled(tmp_path) -> None:
    executor = GitExecutor()
    plain_directory = tmp_path / "plain"
    plain_directory.mkdir()

    result = executor.execute(
        _context(_action(ActionType.GIT_CURRENT_BRANCH, str(plain_directory)), tmp_path)
    )

    assert result.success is False
    assert result.metadata["error"] == "not_git_repository"


def test_invalid_inputs_are_handled(tmp_path) -> None:
    if shutil.which("git") is None:
        pytest.skip("git command is not available")

    repository = _init_repo(tmp_path)
    executor = GitExecutor()

    invalid_limit = executor.execute(
        _context(_action(ActionType.GIT_LOG, str(repository), {"limit": 0}), tmp_path)
    )
    invalid_ref = executor.execute(
        _context(_action(ActionType.GIT_DIFF, str(repository), {"ref": ""}), tmp_path)
    )
    missing_object = executor.execute(_context(_action(ActionType.GIT_SHOW, str(repository)), tmp_path))

    assert invalid_limit.success is False
    assert invalid_limit.metadata["error"] == "invalid_input"
    assert invalid_limit.metadata["field"] == "limit"

    assert invalid_ref.success is False
    assert invalid_ref.metadata["error"] == "invalid_input"
    assert invalid_ref.metadata["field"] == "ref"

    assert missing_object.success is False
    assert missing_object.metadata["error"] == "invalid_input"
    assert missing_object.metadata["field"] == "object"


def _init_repo(tmp_path: Path) -> Path:
    repository = tmp_path / "repo"
    repository.mkdir()
    _run_git(repository, "init")
    _run_git(repository, "config", "user.email", "test@example.com")
    _run_git(repository, "config", "user.name", "Test User")

    file_path = repository / "README.md"
    file_path.write_text("hello\n", encoding="utf-8")
    _run_git(repository, "add", "README.md")
    _run_git(repository, "commit", "-m", "Initial commit")

    return repository


def _run_git(cwd: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {completed.stderr}")
    return (completed.stdout or "").strip()


def _action(action_type: ActionType, target: str, metadata: dict[str, object] | None = None) -> Action:
    return Action(
        id="action-1",
        order=1,
        action_type=action_type,
        target=target,
        description="Test action",
        metadata=metadata or {},
    )


def _context(action: Action, working_directory: Path) -> ExecutionContext:
    return ExecutionContext(
        runtime=object(),
        action=action,
        working_directory=str(working_directory),
        environment={},
    )
