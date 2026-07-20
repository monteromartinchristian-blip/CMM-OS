import pytest

from kernel.planner.exceptions import InvalidOperationError
from kernel.planner.operations import (
    CreateClassOperation,
    EnsureImportOperation,
    InsertMethodOperation,
    ReplaceMethodOperation,
)


def test_operations_expose_structured_metadata() -> None:
    operations = [
        CreateClassOperation(class_name="User"),
        InsertMethodOperation(target_class="User", method_name="run", source_code="def run(self):\n    pass"),
        ReplaceMethodOperation(target_class="User", method_name="run", source_code="def run(self):\n    return True"),
        EnsureImportOperation(module="typing", name="Optional"),
    ]

    for operation in operations:
        schema = operation.schema()

        assert schema["name"]
        assert schema["description"]
        assert schema["category"]
        assert isinstance(schema["parameters"], list)
        for parameter in schema["parameters"]:
            assert parameter["name"]
            assert parameter["type"]
            assert "required" in parameter
            assert parameter["description"]


def test_create_class_operation_validates_correctly() -> None:
    operation = CreateClassOperation(class_name="User")

    assert operation.class_name == "User"


def test_create_class_operation_rejects_empty_name() -> None:
    operation = CreateClassOperation(class_name="")

    with pytest.raises(InvalidOperationError):
        operation.validate()


def test_insert_method_operation_validates_correctly() -> None:
    operation = InsertMethodOperation(
        target_class="User",
        method_name="run",
        source_code="def run(self):\n    pass",
    )

    assert operation.method_name == "run"


def test_insert_method_operation_rejects_empty_source() -> None:
    operation = InsertMethodOperation(target_class="User", method_name="run", source_code="")

    with pytest.raises(InvalidOperationError):
        operation.validate()


def test_replace_method_operation_validates_correctly() -> None:
    operation = ReplaceMethodOperation(
        target_class="User",
        method_name="run",
        source_code="def run(self):\n    return True",
    )

    assert operation.source_code.startswith("def run")


def test_ensure_import_operation_validates_correctly() -> None:
    operation = EnsureImportOperation(module="os", name="path")

    assert operation.module == "os"
    assert operation.name == "path"


def test_ensure_import_operation_rejects_empty_module() -> None:
    operation = EnsureImportOperation(module="")

    with pytest.raises(InvalidOperationError):
        operation.validate()
