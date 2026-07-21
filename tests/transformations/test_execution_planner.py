from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from cmm.execution import BackendActionAdapter
from cmm.transformations import (
    CreateFileOperation,
    ExecutionPlan,
    ExecutionPlanner,
    ExecutionRequest,
    ExecutionStage,
    MoveClassTransformation,
)


def test_execution_stage_is_immutable() -> None:
    stage = ExecutionStage(
        requests=(ExecutionRequest(operation=CreateFileOperation(path="cmm/new.py")),)
    )

    with pytest.raises(FrozenInstanceError):
        stage.parallel = True


def test_execution_plan_is_immutable() -> None:
    plan = ExecutionPlan(stages=(ExecutionStage(requests=()),))

    with pytest.raises(FrozenInstanceError):
        plan.version = "2.0"


def test_execution_planner_builds_one_ordered_sequential_stage() -> None:
    transformation_plan = MoveClassTransformation(
        class_name="Service",
        source_module="cmm.source",
        target_module="cmm.target",
    ).build_plan()

    execution_plan = ExecutionPlanner().build(transformation_plan)

    assert len(execution_plan.stages) == 1
    assert not execution_plan.stages[0].parallel
    assert [request.operation for request in execution_plan.stages[0].requests] == [
        step.operation for step in transformation_plan.steps
    ]
    assert [request.metadata["step_id"] for request in execution_plan.stages[0].requests] == [
        step.id for step in transformation_plan.steps
    ]


def test_execution_plan_exposes_all_requests_metadata_and_description() -> None:
    transformation_plan = MoveClassTransformation(
        class_name="Service",
        source_module="cmm.source",
        target_module="cmm.target",
    ).build_plan()
    execution_plan = ExecutionPlanner().build(transformation_plan)

    assert execution_plan.all_requests() == execution_plan.stages[0].requests
    assert execution_plan.metadata()["version"] == "1.0"
    assert execution_plan.metadata()["stages"][0]["parallel"] is False
    assert isinstance(execution_plan.describe(), str)
    assert isinstance(execution_plan.stages[0].describe(), str)


def test_backend_action_adapter_accepts_execution_plan() -> None:
    transformation_plan = MoveClassTransformation(
        class_name="Service",
        source_module="cmm.source",
        target_module="cmm.target",
    ).build_plan()
    execution_plan = ExecutionPlanner().build(transformation_plan)

    actions = BackendActionAdapter().adapt(execution_plan)

    assert [action.id for action in actions] == [
        step.id for step in transformation_plan.steps
    ]
    assert [action.order for action in actions] == [1, 2, 3, 4]
