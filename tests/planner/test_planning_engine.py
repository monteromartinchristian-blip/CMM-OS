from __future__ import annotations

from uuid import UUID

import pytest

from kernel.planner.exceptions import PlannerError
from kernel.planner.execution_plan import ExecutionPlan
from kernel.planner.operations import CreateClassOperation, InsertMethodOperation
from kernel.planner.planning_engine import PlanningEngine


def test_planning_engine_returns_linear_order() -> None:
    first = CreateClassOperation(class_name="User")
    second = InsertMethodOperation(
        target_class="User",
        method_name="full_name",
        source_code="def full_name(self):\n    return self.name",
        depends_on=(first.operation_id,),
    )

    plan = ExecutionPlan()
    plan.extend([first, second])

    ordered = PlanningEngine().plan(plan)

    assert ordered == [first, second]


def test_planning_engine_returns_valid_order_for_dependencies() -> None:
    root = CreateClassOperation(class_name="User")
    left = InsertMethodOperation(
        target_class="User",
        method_name="left",
        source_code="def left(self):\n    pass",
        depends_on=(root.operation_id,),
    )
    right = InsertMethodOperation(
        target_class="User",
        method_name="right",
        source_code="def right(self):\n    pass",
        depends_on=(root.operation_id,),
    )

    plan = ExecutionPlan()
    plan.extend([root, left, right])

    ordered = PlanningEngine().plan(plan)

    assert ordered[0] is root
    assert {operation.operation_id for operation in ordered[1:]} == {left.operation_id, right.operation_id}


def test_planning_engine_returns_empty_list_for_empty_plan() -> None:
    assert PlanningEngine().plan(ExecutionPlan()) == []


def test_planning_engine_propagates_validation_errors() -> None:
    missing_dependency_id = UUID("00000000-0000-0000-0000-000000000001")
    operation = InsertMethodOperation(
        target_class="User",
        method_name="full_name",
        source_code="def full_name(self):\n    return self.name",
        depends_on=(missing_dependency_id,),
    )

    plan = ExecutionPlan()
    plan.add(operation)

    with pytest.raises(PlannerError, match="Missing dependency detected"):
        PlanningEngine().plan(plan)
