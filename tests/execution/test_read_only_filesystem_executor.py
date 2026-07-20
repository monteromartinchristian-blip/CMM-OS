from __future__ import annotations

import stat

import pytest

from cmm.execution import Action, ActionType, UnsupportedActionError, create_default_executor_registry
from cmm.execution.executors import (
    CompositeExecutor,
    ExecutionContext,
    GitExecutor,
    NoOpExecutor,
    PythonExecutor,
    ReadOnlyFilesystemExecutor,
)


def test_exists_reports_true_and_false(tmp_path) -> None:
    executor = ReadOnlyFilesystemExecutor()
    existing = tmp_path / "existing.txt"
    existing.write_text("hello", encoding="utf-8")

    existing_result = executor.execute(_context(_action(ActionType.FILESYSTEM_EXISTS, str(existing)), tmp_path))
    missing_result = executor.execute(
        _context(_action(ActionType.FILESYSTEM_EXISTS, str(tmp_path / "missing.txt")), tmp_path)
    )

    assert existing_result.success is True
    assert existing_result.metadata == {"exists": True}
    assert missing_result.success is True
    assert missing_result.metadata == {"exists": False}


def test_is_file_and_is_directory(tmp_path) -> None:
    executor = ReadOnlyFilesystemExecutor()
    file_path = tmp_path / "data.txt"
    directory_path = tmp_path / "folder"
    file_path.write_text("x", encoding="utf-8")
    directory_path.mkdir()

    file_result = executor.execute(_context(_action(ActionType.FILESYSTEM_IS_FILE, str(file_path)), tmp_path))
    directory_result = executor.execute(
        _context(_action(ActionType.FILESYSTEM_IS_DIRECTORY, str(directory_path)), tmp_path)
    )

    assert file_result.success is True
    assert file_result.metadata == {"is_file": True}
    assert directory_result.success is True
    assert directory_result.metadata == {"is_directory": True}


def test_read_file_returns_content_and_encoding(tmp_path) -> None:
    executor = ReadOnlyFilesystemExecutor()
    file_path = tmp_path / "notes.txt"
    file_path.write_text("line one\nline two", encoding="utf-8")

    result = executor.execute(_context(_action(ActionType.FILESYSTEM_READ_FILE, str(file_path)), tmp_path))

    assert result.success is True
    assert result.metadata == {
        "path": str(file_path),
        "content": "line one\nline two",
        "encoding": "utf-8",
    }


def test_read_file_handles_missing_file(tmp_path) -> None:
    executor = ReadOnlyFilesystemExecutor()

    result = executor.execute(
        _context(_action(ActionType.FILESYSTEM_READ_FILE, str(tmp_path / "missing.txt")), tmp_path)
    )

    assert result.success is False
    assert result.metadata["error"] == "not_found"


def test_list_directory_returns_entries(tmp_path) -> None:
    executor = ReadOnlyFilesystemExecutor()
    directory_path = tmp_path / "workspace"
    nested_directory = directory_path / "nested"
    nested_file = directory_path / "main.py"
    nested_directory.mkdir(parents=True)
    nested_file.write_text("print('ok')\n", encoding="utf-8")

    result = executor.execute(_context(_action(ActionType.FILESYSTEM_LIST_DIRECTORY, str(directory_path)), tmp_path))

    assert result.success is True
    assert result.metadata["entries"] == [
        {
            "name": "main.py",
            "path": str(nested_file),
            "type": "file",
            "size": len("print('ok')\n"),
        },
        {
            "name": "nested",
            "path": str(nested_directory),
            "type": "directory",
            "size": None,
        },
    ]


def test_list_directory_handles_missing_directory(tmp_path) -> None:
    executor = ReadOnlyFilesystemExecutor()

    result = executor.execute(
        _context(
            _action(ActionType.FILESYSTEM_LIST_DIRECTORY, str(tmp_path / "missing-directory")),
            tmp_path,
        )
    )

    assert result.success is False
    assert result.metadata["error"] == "not_found"


def test_unsupported_action_is_rejected(tmp_path) -> None:
    executor = ReadOnlyFilesystemExecutor()

    with pytest.raises(UnsupportedActionError, match="Unsupported action type: READ_METHOD"):
        executor.execute(_context(_action(ActionType.READ_METHOD, str(tmp_path)), tmp_path))


def test_permission_denied_when_reading_file_if_supported_by_platform(tmp_path) -> None:
    executor = ReadOnlyFilesystemExecutor()
    restricted_file = tmp_path / "restricted.txt"
    restricted_file.write_text("secret", encoding="utf-8")
    restricted_file.chmod(0)

    try:
        result = executor.execute(
            _context(_action(ActionType.FILESYSTEM_READ_FILE, str(restricted_file)), tmp_path)
        )
    finally:
        restricted_file.chmod(stat.S_IRUSR | stat.S_IWUSR)

    if result.success:
        pytest.skip("Current platform permissions allow reading chmod(0) file for this test user.")

    assert result.metadata["error"] == "permission_denied"


def test_binary_file_is_rejected(tmp_path) -> None:
    executor = ReadOnlyFilesystemExecutor()
    binary_file = tmp_path / "payload.bin"
    binary_file.write_bytes(b"\xff\x00\x80")

    result = executor.execute(_context(_action(ActionType.FILESYSTEM_READ_FILE, str(binary_file)), tmp_path))

    assert result.success is False
    assert result.metadata["error"] == "binary_file"


def test_create_default_executor_registry_registers_filesystem_and_noop() -> None:
    registry = create_default_executor_registry()

    assert isinstance(registry.all()[0], CompositeExecutor)
    assert isinstance(registry.all()[1], ReadOnlyFilesystemExecutor)
    assert isinstance(registry.all()[2], PythonExecutor)
    assert isinstance(registry.all()[3], GitExecutor)
    assert isinstance(registry.all()[4], NoOpExecutor)


def _action(action_type: ActionType, target: str) -> Action:
    return Action(
        id="action-1",
        order=1,
        action_type=action_type,
        target=target,
        description="Test action",
    )


def _context(action: Action, working_directory) -> ExecutionContext:
    return ExecutionContext(
        runtime=object(),
        action=action,
        working_directory=str(working_directory),
        environment={},
    )
