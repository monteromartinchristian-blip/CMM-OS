from __future__ import annotations

import ast
from pathlib import Path

import pytest

from kernel.actions.filesystem import WriteFileAction
from kernel.executor import Executor
from kernel.runtime import Runtime
from kernel.semantic import (
    SemanticExecutor,
    SemanticExecutorNotFoundError,
    SemanticOperation,
    SemanticResult,
    SemanticRuntime,
    SemanticValidationError,
)
from kernel.semantic_adapters import operation_from_legacy_action, operation_from_transformation
from kernel.semantic_executors import (
    FileSystemSemanticExecutor,
    NoOpSemanticExecutor,
    TransformationSemanticExecutor,
    create_default_semantic_registry,
)
from cmm.transformations import CreateFileOperation


class RecordingExecutor(SemanticExecutor):
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.operations: list[SemanticOperation] = []

    def supports(self, operation: SemanticOperation) -> bool:
        return operation.domain == "test"

    def validate_before(self, operation: SemanticOperation) -> None:
        operation.require("value")

    def execute(self, operation: SemanticOperation) -> SemanticResult:
        self.operations.append(operation)
        if self.fail:
            raise RuntimeError("execution failed")
        return SemanticResult(
            success=True,
            message="ok",
            data={"value": operation.parameters["value"]},
            operation=operation,
        )


class PostValidationExecutor(RecordingExecutor):
    def validate_after(
        self,
        operation: SemanticOperation,
        result: SemanticResult,
    ) -> SemanticResult:
        raise SemanticValidationError("post validation failed")


def test_semantic_operation_contract_serializes_and_validates() -> None:
    operation = SemanticOperation(
        operation_type="write_file",
        domain="filesystem",
        parameters={"path": "hello.txt", "content": "hello"},
        metadata={"source": "test"},
        operation_id="op-1",
    )

    assert operation.type_id == "filesystem.write_file"
    assert operation.serialize() == {
        "id": "op-1",
        "domain": "filesystem",
        "type": "write_file",
        "parameters": {"path": "hello.txt", "content": "hello"},
        "metadata": {"source": "test"},
    }
    assert SemanticOperation.from_mapping(operation.serialize()) == operation

    with pytest.raises(SemanticValidationError):
        SemanticOperation(operation_type="", domain="filesystem", parameters={})


def test_registry_resolves_supported_executor_and_reports_missing() -> None:
    registry = create_default_semantic_registry()
    operation = SemanticOperation("write_file", "filesystem", {"path": "x", "content": "y"})

    assert isinstance(registry.resolve(operation), FileSystemSemanticExecutor)

    with pytest.raises(SemanticExecutorNotFoundError):
        registry.resolve(SemanticOperation("missing", "unknown", {}))


def test_runtime_validates_before_execution_and_returns_structured_error() -> None:
    registry = create_default_semantic_registry()
    runtime = SemanticRuntime(registry)

    result = runtime.execute_operation(
        SemanticOperation("write_file", "filesystem", {"path": "missing-content.txt"})
    )

    assert result.success is False
    assert "Missing required parameter: content" in result.message
    assert result.errors


def test_runtime_reports_executor_errors_and_post_validation_errors() -> None:
    failing = RecordingExecutor(fail=True)
    post_validation = PostValidationExecutor()

    registry = create_default_semantic_registry()
    registry.register(failing)
    runtime = SemanticRuntime(registry)

    failed = runtime.execute_operation(SemanticOperation("boom", "test", {"value": 1}))
    assert failed.success is False
    assert failed.message == "execution failed"

    registry = create_default_semantic_registry()
    registry.register(post_validation)
    failed_post = SemanticRuntime(registry).execute_operation(
        SemanticOperation("post", "test", {"value": 1})
    )
    assert failed_post.success is False
    assert failed_post.message == "post validation failed"


def test_e2e_legacy_parser_runtime_registry_executor_validation_result(tmp_path: Path) -> None:
    target = tmp_path / "sample.py"
    target.write_text("class User:\n    pass\n", encoding="utf-8")
    payload = {
        "version": 1,
        "actions": [
            {
                "tool": "python",
                "action": "insert_method",
                "path": str(target),
                "class_name": "User",
                "position": "end",
                "code": "def hello(self):\n    return 'hi'",
            }
        ],
    }

    result = Runtime().run(payload)

    source = target.read_text(encoding="utf-8")
    assert result.success is True
    assert len(result.results) == 1
    assert result.results[0].success is True
    assert result.results[0].changes == (str(target),)
    assert "def hello" in source
    ast.parse(source)


def test_filesystem_flow_and_legacy_executor_compatibility(tmp_path: Path) -> None:
    target = tmp_path / "hello.txt"
    action = WriteFileAction(tool="filesystem", action="write_file", path=str(target), content="hello")

    operation = operation_from_legacy_action(action)
    assert operation.type_id == "filesystem.write_file"

    legacy_result = Executor().execute(action)

    assert legacy_result == str(target)
    assert target.read_text(encoding="utf-8") == "hello"


def test_git_or_noop_flow_uses_common_runtime() -> None:
    runtime = SemanticRuntime(create_default_semantic_registry())

    result = runtime.execute_operation(SemanticOperation("status", "git", {"path": "."}))

    assert result.success is True
    assert result.message == "No operation executed."
    assert result.data["operation"] == "git.status"


def test_transformation_operation_adapter_is_ready_for_common_runtime() -> None:
    operation = operation_from_transformation(CreateFileOperation(path="cmm/example.py"))
    registry = create_default_semantic_registry()

    executor = registry.resolve(operation)
    result = SemanticRuntime(registry).execute_operation(operation)

    assert isinstance(executor, TransformationSemanticExecutor)
    assert result.success is True
    assert result.data["operation"] == "create_file"
    assert result.data["parameters"] == {"path": "cmm/example.py"}


def test_runtime_stops_plan_on_executor_not_found() -> None:
    runtime = SemanticRuntime(create_default_semantic_registry())
    result = runtime.execute_plan(
        [
            SemanticOperation("noop", "noop", {}),
            SemanticOperation("missing", "unknown", {}),
            SemanticOperation("noop", "noop", {}),
        ]
    )

    assert result.success is False
    assert len(result.results) == 2
    assert "No semantic executor found" in result.errors[0]
