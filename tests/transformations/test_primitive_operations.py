from __future__ import annotations

from dataclasses import FrozenInstanceError, is_dataclass
import json

import pytest

from cmm.transformations import (
    CopySymbolOperation,
    CreateFileOperation,
    CreateModuleOperation,
    DeleteFileOperation,
    DeleteModuleOperation,
    DeleteSymbolOperation,
    MoveSymbolOperation,
    OperationRegistry,
    RenameSymbolOperation,
    TransformationOperation,
    UpdateImportsOperation,
    ValidateProjectOperation,
)


def _operations() -> list[TransformationOperation]:
    return [
        CreateFileOperation(path="src/new_module.py"),
        DeleteFileOperation(path="src/obsolete.py"),
        CreateModuleOperation(module_name="cmm.new_module"),
        DeleteModuleOperation(module="cmm.obsolete"),
        MoveSymbolOperation(
            symbol="Service",
            source="cmm.old",
            destination="cmm.new",
        ),
        CopySymbolOperation(
            symbol="Service",
            source="cmm.old",
            destination="cmm.new",
        ),
        DeleteSymbolOperation(symbol="obsolete_service", module="cmm.obsolete"),
        RenameSymbolOperation(symbol="Service", new_name="NewService"),
        UpdateImportsOperation(module="cmm.api"),
        ValidateProjectOperation(scope="cmm"),
    ]


@pytest.mark.parametrize("operation", _operations())
def test_operations_are_frozen_dataclasses(operation: TransformationOperation) -> None:
    assert is_dataclass(operation)
    assert operation.__dataclass_params__.frozen

    field_name = next(iter(operation.metadata()))
    with pytest.raises(FrozenInstanceError):
        setattr(operation, field_name, "changed")


@pytest.mark.parametrize("operation", _operations())
def test_operation_metadata_is_serializable_and_describable(
    operation: TransformationOperation,
) -> None:
    assert isinstance(operation.describe(), str)
    assert operation.describe()
    assert json.loads(json.dumps(operation.metadata())) == operation.metadata()


@pytest.mark.parametrize("operation", _operations())
def test_operations_support_value_equality_and_hashing(
    operation: TransformationOperation,
) -> None:
    equivalent_operation = type(operation)(**operation.metadata())

    assert operation == equivalent_operation
    assert hash(operation) == hash(equivalent_operation)


def test_operation_registry_stores_and_resolves_operations() -> None:
    create_module = CreateModuleOperation(module_name="cmm.feature")
    delete_module = DeleteModuleOperation(module="cmm.legacy")
    registry = OperationRegistry()

    registry.register(create_module)
    registry.register_many([delete_module])

    assert registry.resolve("create_module") == create_module
    assert registry.all() == [create_module, delete_module]

    registry.clear()

    assert registry.all() == []


@pytest.mark.parametrize("operation_type", [CopySymbolOperation, DeleteSymbolOperation, RenameSymbolOperation])
def test_symbol_operations_reject_unknown_symbol_kind(operation_type) -> None:
    arguments = {
        CopySymbolOperation: {"symbol": "Thing", "source": "source", "destination": "target"},
        DeleteSymbolOperation: {"symbol": "Thing", "module": "source"},
        RenameSymbolOperation: {"symbol": "Thing", "new_name": "Other"},
    }
    with pytest.raises(ValueError, match="Unsupported symbol kind"):
        operation_type(**arguments[operation_type], symbol_kind="module")
