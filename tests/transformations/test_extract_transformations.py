from __future__ import annotations

import pytest

from cmm.transformations import (
    ExtractMethodOperation,
    ExtractMethodTransformation,
    ExtractModuleOperation,
    ExtractModuleTransformation,
)


def test_extract_method_plan_has_deterministic_dag_and_parameters() -> None:
    plan = ExtractMethodTransformation("app", "Service", "run", "helper", 1, 3).create_plan("x")
    assert [step.id for step in plan.steps] == ["extract-method-1", "extract-method-2"]
    assert isinstance(plan.steps[0].operation, ExtractMethodOperation)
    assert plan.steps[0].operation.metadata() == {
        "module": "app",
        "class_name": "Service",
        "method_name": "run",
        "new_method_name": "helper",
        "start_index": 1,
        "end_index": 3,
    }
    assert plan.steps[1].dependencies == ("extract-method-1",)


def test_extract_module_plan_supports_existing_and_new_destinations() -> None:
    existing = ExtractModuleTransformation("source", "target", ("foo", "Service"))
    new = ExtractModuleTransformation("source", "target", ("foo",), create_target=True)
    assert isinstance(existing.create_plan("x").steps[0].operation, ExtractModuleOperation)
    assert [step.id for step in existing.create_plan("x").steps] == [
        "extract-module-1",
        "extract-module-2",
    ]
    assert new.create_plan("x").steps[0].operation.name == "create_module"


@pytest.mark.parametrize(
    "start,end",
    [(0, 0), (-1, 1), (3, 4)],
)
def test_extract_method_plan_preserves_selector_for_precondition(start: int, end: int) -> None:
    plan = ExtractMethodTransformation("app", "Service", "run", "helper", start, end).create_plan("x")
    precondition = plan.preconditions[-1]
    assert precondition.start_index == start
    assert precondition.end_index == end
