from __future__ import annotations

from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from cmm.transformations import (
    CreateFileOperation,
    ExecutionRequest,
    MoveClassTransformation,
    TransformationStep,
)


def test_transformation_steps_require_typed_operations() -> None:
    operation = CreateFileOperation(path="cmm/new.py")
    step = TransformationStep(id="create-file", operation=operation)

    assert step.operation is operation
    assert not isinstance(step.operation, str)

    with pytest.raises(TypeError):
        TransformationStep(id="legacy", operation="create_file")  # type: ignore[arg-type]


def test_composite_plan_contains_no_string_operations() -> None:
    plan = MoveClassTransformation(
        class_name="Service",
        source_module="cmm.source",
        target_module="cmm.target",
    ).build_plan()

    assert all(not isinstance(step.operation, str) for step in plan.steps)


def test_execution_request_is_immutable() -> None:
    request = ExecutionRequest(
        operation=CreateFileOperation(path="cmm/new.py"),
        metadata={"request_id": "create-file"},
    )

    with pytest.raises(FrozenInstanceError):
        request.operation = CreateFileOperation(path="cmm/other.py")
    with pytest.raises(TypeError):
        request.metadata["request_id"] = "other"


def test_transformation_domain_does_not_import_execution_infrastructure() -> None:
    transformations_directory = Path(__file__).parents[2] / "cmm" / "transformations"

    for module_path in transformations_directory.rglob("*.py"):
        source = module_path.read_text(encoding="utf-8")
        assert "cmm.execution" not in source
        assert "ActionRuntime" not in source
