from __future__ import annotations

from kernel.planner.registry import (
    CreateClassHandler,
    EnsureImportHandler,
    InsertMethodHandler,
    OperationHandler,
    ReplaceMethodHandler,
)


def test_all_handlers_inherit_from_operation_handler() -> None:
    assert issubclass(CreateClassHandler, OperationHandler)
    assert issubclass(InsertMethodHandler, OperationHandler)
    assert issubclass(ReplaceMethodHandler, OperationHandler)
    assert issubclass(EnsureImportHandler, OperationHandler)


def test_operation_handler_requires_execute_contract() -> None:
    assert hasattr(OperationHandler, "execute")
    assert callable(OperationHandler.execute)