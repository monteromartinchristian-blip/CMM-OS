from __future__ import annotations

import stat

import pytest

from cmm.execution import Action, ActionType, UnsupportedActionError
from cmm.execution.executors import ExecutionContext, PythonExecutor


def test_list_classes_functions_methods_imports_and_describe_module(tmp_path) -> None:
    executor = PythonExecutor()
    module = tmp_path / "sample.py"
    module.write_text(
        """
import os
from pathlib import Path


def helper() -> str:
    return "ok"


class Service:
    def run(self):
        return helper()
""",
        encoding="utf-8",
    )

    classes_result = executor.execute(_context(_action(ActionType.PYTHON_LIST_CLASSES, str(module)), tmp_path))
    functions_result = executor.execute(_context(_action(ActionType.PYTHON_LIST_FUNCTIONS, str(module)), tmp_path))
    methods_result = executor.execute(_context(_action(ActionType.PYTHON_LIST_METHODS, str(module)), tmp_path))
    imports_result = executor.execute(_context(_action(ActionType.PYTHON_LIST_IMPORTS, str(module)), tmp_path))
    describe_result = executor.execute(_context(_action(ActionType.PYTHON_DESCRIBE_MODULE, str(module)), tmp_path))

    assert classes_result.success is True
    assert [item["name"] for item in classes_result.metadata["classes"]] == ["Service"]

    assert functions_result.success is True
    assert [item["name"] for item in functions_result.metadata["functions"]] == ["helper"]

    assert methods_result.success is True
    assert len(methods_result.metadata["methods"]) == 1
    method = methods_result.metadata["methods"][0]
    assert method["class"] == "Service"
    assert method["name"] == "run"
    assert method["docstring"] == ""
    assert isinstance(method["lineno"], int) and method["lineno"] >= 1
    assert isinstance(method["end_lineno"], int) and method["end_lineno"] >= method["lineno"]

    assert imports_result.success is True
    assert imports_result.metadata["imports"] == ["import os", "from pathlib import Path"]

    assert describe_result.success is True
    assert describe_result.metadata["classes_count"] == 1
    assert describe_result.metadata["functions_count"] == 1
    assert describe_result.metadata["methods_count"] == 1
    assert describe_result.metadata["imports_count"] == 2


def test_find_symbol_success_and_symbol_not_found(tmp_path) -> None:
    executor = PythonExecutor()
    module = tmp_path / "module.py"
    module.write_text(
        """
def alpha():
    return 1


class Beta:
    def alpha(self):
        return 2
""",
        encoding="utf-8",
    )

    success_result = executor.execute(
        _context(_action(ActionType.PYTHON_FIND_SYMBOL, str(module), {"symbol": "alpha"}), tmp_path)
    )
    missing_result = executor.execute(
        _context(_action(ActionType.PYTHON_FIND_SYMBOL, str(module), {"symbol": "missing"}), tmp_path)
    )

    assert success_result.success is True
    assert success_result.metadata["symbol"] == "alpha"
    assert {match["kind"] for match in success_result.metadata["matches"]} == {"Function", "Method"}

    assert missing_result.success is False
    assert missing_result.metadata["error"] == "symbol_not_found"


def test_unsupported_action_is_rejected(tmp_path) -> None:
    executor = PythonExecutor()
    module = tmp_path / "module.py"
    module.write_text("def fn():\n    return 1\n", encoding="utf-8")

    with pytest.raises(UnsupportedActionError, match="Unsupported action type: READ_METHOD"):
        executor.execute(_context(_action(ActionType.READ_METHOD, str(module)), tmp_path))


def test_missing_file_is_handled(tmp_path) -> None:
    executor = PythonExecutor()

    result = executor.execute(
        _context(_action(ActionType.PYTHON_LIST_FUNCTIONS, str(tmp_path / "missing.py")), tmp_path)
    )

    assert result.success is False
    assert result.metadata["error"] == "not_found"


def test_invalid_python_syntax_is_handled(tmp_path) -> None:
    executor = PythonExecutor()
    module = tmp_path / "broken.py"
    module.write_text("def broken(:\n    pass\n", encoding="utf-8")

    result = executor.execute(_context(_action(ActionType.PYTHON_LIST_CLASSES, str(module)), tmp_path))

    assert result.success is False
    assert result.metadata["error"] == "invalid_syntax"
    assert result.metadata["line"] == 1


def test_permission_denied_if_supported_by_platform(tmp_path) -> None:
    executor = PythonExecutor()
    module = tmp_path / "private.py"
    module.write_text("def secret():\n    return 1\n", encoding="utf-8")
    module.chmod(0)

    try:
        result = executor.execute(_context(_action(ActionType.PYTHON_DESCRIBE_MODULE, str(module)), tmp_path))
    finally:
        module.chmod(stat.S_IRUSR | stat.S_IWUSR)

    if result.success:
        pytest.skip("Current platform permissions allow reading chmod(0) file for this test user.")

    assert result.metadata["error"] == "permission_denied"


def _action(action_type: ActionType, target: str, metadata: dict[str, object] | None = None) -> Action:
    return Action(
        id="action-1",
        order=1,
        action_type=action_type,
        target=target,
        description="Test action",
        metadata=metadata or {},
    )


def _context(action: Action, working_directory) -> ExecutionContext:
    return ExecutionContext(
        runtime=object(),
        action=action,
        working_directory=str(working_directory),
        environment={},
    )
