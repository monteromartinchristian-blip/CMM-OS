from __future__ import annotations

import json

from cmm.transformations import (
    CopySymbolOperation,
    DeleteSymbolOperation,
    MoveFunctionTransformation,
    MoveFunctionTransformationBuilder,
    RenameSymbolOperation,
    UpdateImportsOperation,
    ValidateProjectOperation,
)


def _transformation(new_name: str | None = None) -> MoveFunctionTransformation:
    return MoveFunctionTransformation(
        source_module="cmm.source",
        target_module="cmm.target",
        function_name="greet",
        new_name=new_name,
    )


def test_builder_creates_operations_in_move_order() -> None:
    plan = MoveFunctionTransformationBuilder().build(_transformation("welcome"))

    assert [type(step.operation) for step in plan.steps] == [
        CopySymbolOperation,
        RenameSymbolOperation,
        UpdateImportsOperation,
        DeleteSymbolOperation,
        ValidateProjectOperation,
    ]
    assert [step.id for step in plan.steps] == [
        "move-function-1",
        "move-function-2",
        "move-function-3",
        "move-function-4",
        "move-function-5",
    ]


def test_builder_propagates_transformation_parameters() -> None:
    plan = MoveFunctionTransformationBuilder().build(_transformation("welcome"))
    (
        copy_operation,
        rename_operation,
        update_imports_operation,
        delete_operation,
        validate_operation,
    ) = (step.operation for step in plan.steps)

    assert copy_operation == CopySymbolOperation(
        symbol="greet",
        source="cmm.source",
        destination="cmm.target",
    )
    assert rename_operation == RenameSymbolOperation(
        symbol="greet",
        new_name="welcome",
    )
    assert update_imports_operation == UpdateImportsOperation(module="cmm.target")
    assert delete_operation == DeleteSymbolOperation(
        symbol="greet",
        module="cmm.source",
    )
    assert validate_operation == ValidateProjectOperation(scope="project")


def test_builder_omits_rename_when_not_requested() -> None:
    plan = MoveFunctionTransformationBuilder().build(_transformation())

    assert [type(step.operation) for step in plan.steps] == [
        CopySymbolOperation,
        UpdateImportsOperation,
        DeleteSymbolOperation,
        ValidateProjectOperation,
    ]


def test_plan_operations_are_serializable() -> None:
    plan = MoveFunctionTransformationBuilder().build(_transformation("welcome"))

    serialized = json.dumps(
        [
            {
                "id": step.id,
                "operation": step.operation.name,
                "metadata": step.operation.metadata(),
            }
            for step in plan.steps
        ]
    )

    assert json.loads(serialized) == [
        {
            "id": "move-function-1",
            "operation": "copy_symbol",
            "metadata": {
                "symbol": "greet",
                "source": "cmm.source",
                "destination": "cmm.target",
            },
        },
        {
            "id": "move-function-2",
            "operation": "rename_symbol",
            "metadata": {"symbol": "greet", "new_name": "welcome"},
        },
        {
            "id": "move-function-3",
            "operation": "update_imports",
            "metadata": {"module": "cmm.target"},
        },
        {
            "id": "move-function-4",
            "operation": "delete_symbol",
            "metadata": {"symbol": "greet", "module": "cmm.source"},
        },
        {
            "id": "move-function-5",
            "operation": "validate_project",
            "metadata": {"scope": "project"},
        },
    ]
