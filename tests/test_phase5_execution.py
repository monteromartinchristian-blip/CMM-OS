from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from cmm.development.models import DevelopmentPlan
from cmm.development import AutonomousDevelopmentService
from cmm.development.providers import DeterministicPlanningProvider
from cmm.execution import Action, ActionType, ActionPlanner, ExecutorRegistry
from cmm.execution.development import AutonomousExecutionService
from cmm.execution.executors import ExecutionContext, FilesystemExecutor, GitExecutor, PythonExecutor
from cmm.runtime import ActionRuntime, ActionStatus


def _context(action: Action, root: Path) -> ExecutionContext:
    return ExecutionContext(runtime=object(), action=action, working_directory=str(root), environment={})


def _action(number: int, action_type: ActionType, target: str, metadata=None) -> Action:
    return Action(f"action-{number}", number, action_type, target, action_type.value, metadata or {})


def test_filesystem_mutations_are_project_scoped_and_atomic(tmp_path: Path) -> None:
    executor = FilesystemExecutor()
    created = executor.execute(_context(_action(1, ActionType.FILESYSTEM_CREATE_FILE, "new.txt", {"content": "one"}), tmp_path))
    appended = executor.execute(_context(_action(1, ActionType.FILESYSTEM_APPEND_FILE, "new.txt", {"content": " two"}), tmp_path))
    moved = executor.execute(_context(_action(1, ActionType.FILESYSTEM_MOVE_FILE, "new.txt", {"destination": "moved.txt"}), tmp_path))
    deleted = executor.execute(_context(_action(1, ActionType.FILESYSTEM_DELETE_FILE, "moved.txt"), tmp_path))

    assert all(item.success for item in (created, appended, moved, deleted))
    assert not (tmp_path / "moved.txt").exists()
    unsafe = executor.execute(_context(_action(1, ActionType.FILESYSTEM_WRITE_FILE, "../escape.txt", {"content": "x"}), tmp_path))
    assert unsafe.success is False
    directory = executor.execute(_context(_action(1, ActionType.FILESYSTEM_CREATE_DIRECTORY, "nested", {}), tmp_path))
    removed_directory = executor.execute(_context(_action(1, ActionType.FILESYSTEM_DELETE_DIRECTORY, "nested", {}), tmp_path))
    assert directory.success and removed_directory.success
    outside = tmp_path.parent / f"{tmp_path.name}-outside"
    outside.mkdir()
    try:
        link = tmp_path / "link"
        link.symlink_to(outside, target_is_directory=True)
        escaped = executor.execute(_context(_action(1, ActionType.FILESYSTEM_WRITE_FILE, "link/file.txt", {"content": "x"}), tmp_path))
        assert escaped.success is False
    except (NotImplementedError, OSError):
        pass


def test_python_executor_mutations_delegate_to_semantic_runtime(tmp_path: Path) -> None:
    path = tmp_path / "module.py"
    path.write_text("class User:\n    def old(self):\n        return 1\n", encoding="utf-8")
    executor = PythonExecutor()
    operations = [
        (ActionType.PYTHON_ADD_IMPORT, {"module": "pkg", "name": "Thing"}),
        (ActionType.PYTHON_INSERT_METHOD, {"class_name": "User", "position": "end", "code": "def added(self):\n    return 2"}),
        (ActionType.PYTHON_REPLACE_METHOD, {"class_name": "User", "method_name": "old", "code": "def old(self):\n    return 3"}),
        (ActionType.PYTHON_RENAME_METHOD, {"class_name": "User", "old_name": "old", "new_name": "renamed"}),
        (ActionType.PYTHON_REMOVE_IMPORT, {"module": "pkg", "name": "Thing"}),
        (ActionType.PYTHON_CREATE_CLASS, {"class_name": "Other"}),
        (ActionType.PYTHON_RENAME_CLASS, {"class_name": "Other", "new_name": "Renamed"}),
        (ActionType.PYTHON_DELETE_CLASS, {"class_name": "Renamed"}),
        (ActionType.PYTHON_DELETE_METHOD, {"class_name": "User", "method_name": "added"}),
    ]
    results = []
    for number, (action_type, metadata) in enumerate(operations, 1):
        results.append(executor.execute(_context(_action(number, action_type, "module.py", metadata), tmp_path)))

    assert all(result.success for result in results), [result.message for result in results]
    compile(path.read_text(encoding="utf-8"), str(path), "exec")
    assert "renamed" in path.read_text(encoding="utf-8")


def test_action_runtime_stops_and_preserves_history_on_mutation_failure(tmp_path: Path) -> None:
    path = tmp_path / "module.py"
    path.write_text("class User:\n    pass\n", encoding="utf-8")
    actions = [
        _action(1, ActionType.FILESYSTEM_WRITE_FILE, "module.py", {"content": "class User:\n    pass\n", "allow_existing": True}),
        _action(2, ActionType.PYTHON_DELETE_METHOD, "module.py", {"class_name": "User", "method_name": "missing"}),
        _action(3, ActionType.FILESYSTEM_CREATE_FILE, "later.txt", {"content": "later"}),
    ]
    runtime = ActionRuntime(ActionPlanner(object()), working_directory=tmp_path)
    result = runtime.execute(actions)

    assert result.success is False
    assert result.executions[1].status is ActionStatus.FAILED
    assert result.executions[2].status is ActionStatus.SKIPPED


def test_phase5_goal_creates_python_and_refreshes_memory(tmp_path: Path) -> None:
    goal = "create class User in app.py"
    result = AutonomousExecutionService(DeterministicPlanningProvider()).develop(goal, tmp_path, yes=True)

    assert result.success is True
    assert result.memory_refreshed is True
    assert result.review_ready is True
    assert result.diff
    assert any(action["type"] == "python.create_class" for action in result.planned_actions)
    assert "class User" in (tmp_path / "app.py").read_text(encoding="utf-8")


def test_phase5_multi_action_plan_and_rollback(tmp_path: Path) -> None:
    path = tmp_path / "app.py"
    path.write_text("class User:\n    pass\n", encoding="utf-8")
    original = path.read_bytes()
    plan = {
        "goal": "apply change",
        "affected_files": ["app.py"],
        "operations": [
            {"domain": "python", "type": "create_class", "parameters": {"path": "app.py", "class_name": "Added"}},
            {"domain": "python", "type": "delete_method", "parameters": {"path": "app.py", "class_name": "User", "method_name": "missing"}},
        ],
        "rationale": "exercise rollback",
    }
    result = AutonomousExecutionService(DeterministicPlanningProvider(plan=plan)).develop("apply change", tmp_path, yes=True)

    assert result.success is False
    assert result.rollback_applied is True
    assert path.read_bytes() == original
    assert not result.memory_refreshed


def test_phase5_coordinator_executes_multiple_real_actions_in_order(tmp_path: Path) -> None:
    plan = {
        "goal": "build module",
        "affected_files": ["app.py"],
        "operations": [
            {"domain": "filesystem", "type": "write_file", "parameters": {"path": "app.py", "content": "from pkg import Thing\n"}},
            {"domain": "python", "type": "create_class", "parameters": {"path": "app.py", "class_name": "User"}},
            {"domain": "python", "type": "insert_method", "parameters": {"path": "app.py", "class_name": "User", "position": "end", "code": "def run(self):\n    return Thing"}},
        ],
        "rationale": "build a small module",
    }
    result = AutonomousExecutionService(DeterministicPlanningProvider(plan=plan)).develop("build module", tmp_path, yes=True)

    assert result.success is True
    assert [item["status"] for item in result.executed_actions] == ["COMPLETED"] * 3
    assert "class User" in (tmp_path / "app.py").read_text(encoding="utf-8")
    assert len(result.diff.splitlines()) > 2


def test_git_executor_isolation_operations_are_controlled(tmp_path: Path) -> None:
    if shutil.which("git") is None:
        pytest.skip("git unavailable")
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, check=True)
    (tmp_path / "README.md").write_text("initial\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=tmp_path, check=True, capture_output=True)
    executor = GitExecutor(timeout=5)
    branch = executor.execute(_context(_action(1, ActionType.GIT_CREATE_BRANCH, ".", {"branch": "cmm-review"}), tmp_path))
    changed = executor.execute(_context(_action(1, ActionType.GIT_LIST_CHANGED_FILES, "."), tmp_path))
    current = executor.execute(_context(_action(1, ActionType.GIT_CURRENT_BRANCH, "."), tmp_path))

    assert branch.success and changed.success and current.success
    assert current.metadata["branch"] == "cmm-review"
    unsafe = executor.execute(_context(_action(1, ActionType.GIT_CREATE_BRANCH, ".", {"branch": "--delete"}), tmp_path))
    assert unsafe.success is False


def test_phase3_autonomous_cycle_reuses_phase5_mutating_backend(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text("class User:\n    pass\n", encoding="utf-8")
    bad = {
        "goal": "repair",
        "affected_files": ["app.py"],
        "operations": [
            {"domain": "filesystem", "type": "write_file", "parameters": {"path": "app.py", "content": "class User:\n    pass\n", "allow_existing": True}},
            {"domain": "python", "type": "delete_method", "parameters": {"path": "app.py", "class_name": "User", "method_name": "missing"}},
        ],
        "rationale": "force a recoverable execution failure",
    }
    good = {
        "goal": "repair",
        "affected_files": ["app.py"],
        "operations": [{"domain": "python", "type": "create_class", "parameters": {"path": "app.py", "class_name": "Fixed"}}],
        "rationale": "apply the correction",
    }
    provider = DeterministicPlanningProvider(plans=[bad], corrections=[good])
    result = AutonomousDevelopmentService(provider, development=AutonomousExecutionService(provider)).develop("repair", tmp_path, yes=True, max_attempts=2)

    assert result.success is True
    assert result.attempt_count == 2
    assert [attempt.failure.kind.value for attempt in result.attempts] == ["execution", "none"]
    assert "class Fixed" in (tmp_path / "app.py").read_text(encoding="utf-8")
