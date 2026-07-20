from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from kernel.planner.operations import CreateClassOperation, EnsureImportOperation, InsertMethodOperation, Operation, ReplaceMethodOperation


def test_operation_generates_uuid_automatically() -> None:
    operation = CreateClassOperation(class_name="User")

    assert isinstance(operation.id, UUID)
    assert operation.id is not None


def test_operation_depends_on_empty_by_default() -> None:
    operation = CreateClassOperation(class_name="User")

    assert operation.depends_on == ()


def test_operation_metadata_defaults_to_empty_dict() -> None:
    operation = CreateClassOperation(class_name="User")

    assert operation.metadata == {}


def test_operation_tags_defaults_to_empty_tuple() -> None:
    operation = CreateClassOperation(class_name="User")

    assert operation.tags == ()


def test_operation_serialize_and_from_dict_round_trip() -> None:
    operation = CreateClassOperation(
        class_name="User",
        module="models.py",
        metadata={"source": "demo"},
        tags=("alpha",),
        depends_on=(),
    )

    payload = operation.serialize()
    restored = Operation.from_dict(payload)

    assert restored.class_name == "User"
    assert restored.module == "models.py"
    assert restored.metadata == {"source": "demo"}
    assert restored.tags == ("alpha",)


def test_operation_cannot_depend_on_itself() -> None:
    operation = CreateClassOperation(class_name="User")
    self_dependent = CreateClassOperation(class_name="Admin", id=operation.id, depends_on=(operation.id,))

    with pytest.raises(ValueError, match="depend on itself"):
        self_dependent.validate()


def test_existing_operations_still_work() -> None:
    create = CreateClassOperation(class_name="User")
    insert = InsertMethodOperation(target_class="User", method_name="login", source_code="pass")
    replace = ReplaceMethodOperation(target_class="User", method_name="login", source_code="pass")
    ensure = EnsureImportOperation(module="typing")

    assert create.class_name == "User"
    assert insert.method_name == "login"
    assert replace.target_class == "User"
    assert ensure.module == "typing"

def test_operation_metadata_contract_is_stable() -> None:
    operations = [
        CreateClassOperation(class_name="User"),
        InsertMethodOperation(target_class="User", method_name="login", source_code="pass"),
        ReplaceMethodOperation(target_class="User", method_name="login", source_code="pass"),
        EnsureImportOperation(module="typing"),
    ]

    for operation in operations:
        schema = operation.schema()
        assert set(schema) >= {"name", "description", "category", "parameters"}
