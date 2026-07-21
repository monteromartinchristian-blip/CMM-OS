from __future__ import annotations

import pytest

from cmm.execution import (
    ExecutionResult,
    OperationExecutor,
    OperationExecutorRegistry,
    UnsupportedOperationExecutorError,
)
from cmm.execution.python import (
    PythonCopySymbolExecutor,
    PythonCreateModuleExecutor,
    PythonDeleteSymbolExecutor,
    PythonUpdateImportsExecutor,
    PythonValidateProjectExecutor,
    PythonProjectParser,
    SemanticContextBuilder,
)
from cmm.transformations import (
    CopySymbolOperation,
    CreateModuleOperation,
    DeleteSymbolOperation,
    ExecutionRequest,
    UpdateImportsOperation,
    ValidateProjectOperation,
)


def _executors() -> list[OperationExecutor]:
    return [
        PythonCreateModuleExecutor(),
        PythonCopySymbolExecutor(),
        PythonDeleteSymbolExecutor(),
        PythonUpdateImportsExecutor(),
        PythonValidateProjectExecutor(),
    ]


def _requests(
    project_root: str = ".",
    snapshot: object = None,
) -> list[ExecutionRequest]:
    context = (
        SemanticContextBuilder().build(snapshot)
        if snapshot is not None
        else None
    )
    return [
        ExecutionRequest(
            operation=CreateModuleOperation(
                module_name="cmm.target",
                project_root=project_root,
            )
        ),
        ExecutionRequest(
            operation=CopySymbolOperation(
                symbol="Service",
                source="cmm.source",
                destination="copy_target",
            ),
            metadata={
                "semantic_context": context,
            },
        ),
        ExecutionRequest(
            operation=DeleteSymbolOperation(
                symbol="Service",
                module="cmm.source",
            ),
            metadata={
                "semantic_context": context,
            },
        ),
        ExecutionRequest(
            operation=UpdateImportsOperation(module="cmm.target"),
            metadata={
                "semantic_context": context,
                "old_module": "old_module",
                "new_module": "new_module",
                "symbol_name": "symbol",
            },
        ),
        ExecutionRequest(
            operation=ValidateProjectOperation(scope="project"),
            metadata={"project_root": project_root},
        ),
    ]


def test_registry_registers_resolves_and_reports_supported_operations() -> None:
    registry = OperationExecutorRegistry()
    executors = _executors()

    registry.register_many(executors)

    assert registry.all() == executors
    for request, executor in zip(_requests(), executors, strict=True):
        assert registry.supports(request.operation)
        assert registry.resolve(request.operation) is executor


def test_registry_unregisters_executor_by_concrete_operation_type() -> None:
    registry = OperationExecutorRegistry()
    executor = PythonCreateModuleExecutor()
    registry.register(executor)

    removed = registry.unregister(CreateModuleOperation)

    assert removed is executor
    assert not registry.supports(CreateModuleOperation(module_name="cmm.target"))
    with pytest.raises(UnsupportedOperationExecutorError):
        registry.resolve(CreateModuleOperation(module_name="cmm.target"))


def test_registered_executors_share_interface_and_return_success(tmp_path: object) -> None:
    registry = OperationExecutorRegistry()
    registry.register_many(_executors())
    source_path = tmp_path / "cmm" / "source.py"
    target_path = tmp_path / "copy_target.py"
    source_path.parent.mkdir()
    source_path.write_text("def Service():\n    return None\n", encoding="utf-8")
    target_path.write_text("", encoding="utf-8")
    snapshot = PythonProjectParser().parse(tmp_path)

    for request in _requests(str(tmp_path), snapshot):
        executor = registry.resolve(request.operation)
        result = executor.execute(request)

        assert isinstance(executor, OperationExecutor)
        assert isinstance(result, ExecutionResult)
        assert result.success
        assert result.operation is request.operation
