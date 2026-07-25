"""Integration tests for Planner Validation Adapter (Subphase 7.13)."""

import pytest

from cmm.validation.integration.contracts import (
    ValidationPhase,
    ValidationPlanNode,
)
from cmm.validation.integration.planning import (
    PlannerValidationAdapter,
    PlannerValidationError,
)


def test_planner_adapter_node_validation_success():
    adapter = PlannerValidationAdapter()
    node1 = ValidationPlanNode(
        id="node-1",
        phase=ValidationPhase.AFTER_EXECUTION,
        policy_name="default",
    )
    node2 = ValidationPlanNode(
        id="node-2",
        phase=ValidationPhase.AFTER_EXECUTION,
        policy_name="fast_static_only",
        depends_on=("node-1",),
    )
    adapter.validate_plan_nodes((node1, node2))


def test_planner_adapter_unknown_policy():
    adapter = PlannerValidationAdapter()
    node = ValidationPlanNode(
        id="node-bad",
        policy_name="non_existent_policy_xyz",
    )
    with pytest.raises(PlannerValidationError, match="Unknown validation policy"):
        adapter.validate_plan_nodes((node,))


def test_planner_adapter_cycle_detection():
    adapter = PlannerValidationAdapter()
    node1 = ValidationPlanNode(id="node-a", depends_on=("node-b",))
    node2 = ValidationPlanNode(id="node-b", depends_on=("node-a",))

    with pytest.raises(PlannerValidationError, match="Cycle detected"):
        adapter.validate_plan_nodes((node1, node2))


def test_planner_adapter_inject_validation_nodes():
    adapter = PlannerValidationAdapter()
    raw_plan = [
        {"id": "step_1", "mutating": True},
        {"id": "step_2", "mutating": False},
    ]

    augmented = adapter.inject_validation_nodes(
        raw_plan, policy_name="fast_static_only"
    )
    assert len(augmented) == 3
    assert augmented[0]["id"] == "step_1"
    assert augmented[1]["id"] == "val_step_1"
    assert augmented[2]["id"] == "step_2"
