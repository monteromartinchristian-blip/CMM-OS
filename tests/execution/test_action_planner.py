from __future__ import annotations

from dataclasses import FrozenInstanceError
from types import SimpleNamespace

import pytest

from cmm.execution import Action, ActionPlanner, ActionType
from cmm.planner import ExecutionPlan, PlanStep


def test_create_actions_transforms_plan_steps_without_executing() -> None:
    action_planner = ActionPlanner(object())

    actions = action_planner.create_actions(_plan())

    assert [action.order for action in actions] == list(range(1, 8))
    assert [action.action_type for action in actions] == [
        ActionType.READ_CLASS,
        ActionType.ANALYZE_DEPENDENCIES,
        ActionType.ANALYZE_CALLERS,
        ActionType.ANALYZE_CALLEES,
        ActionType.ANALYZE_IMPACT,
        ActionType.ANALYZE_IMPACT,
        ActionType.PREPARE_MODIFICATION,
    ]
    assert {action.target for action in actions} == {"AuthenticationService"}
    assert actions[0].metadata == {
        "goal": "Modify AuthenticationService",
        "plan_step_order": 1,
    }


def test_create_actions_selects_read_action_from_symbol_kind() -> None:
    action_planner = ActionPlanner(object())
    plan = ExecutionPlan(
        goal="Read symbols",
        summary="",
        estimated_complexity="LOW",
        entry_points=[
            SimpleNamespace(title="api", kind="Module"),
            SimpleNamespace(title="Service", kind="Class"),
            SimpleNamespace(title="build", kind="Function"),
            SimpleNamespace(title="run", kind="Method"),
        ],
        impacted_components=[],
        steps=[
            PlanStep(1, "Analyze entry points", "", ""),
        ],
    )

    actions = action_planner.create_actions(plan)

    assert [action.action_type for action in actions] == [
        ActionType.READ_MODULE,
        ActionType.READ_CLASS,
        ActionType.READ_FUNCTION,
        ActionType.READ_METHOD,
    ]


def test_optimize_removes_duplicates_and_renumbers_actions() -> None:
    action_planner = ActionPlanner(object())
    actions = [
        Action("old-one", 3, ActionType.READ_CLASS, "Service", "Read"),
        Action("old-two", 4, ActionType.READ_CLASS, "Service", "Read again"),
        Action("old-three", 8, ActionType.ANALYZE_IMPACT, "Service", "Impact"),
    ]

    optimized = action_planner.optimize(actions)

    assert [(action.id, action.order) for action in optimized] == [
        ("action-1", 1),
        ("action-2", 2),
    ]
    assert [action.action_type for action in optimized] == [
        ActionType.READ_CLASS,
        ActionType.ANALYZE_IMPACT,
    ]


def test_validate_reports_invalid_action_queue() -> None:
    action_planner = ActionPlanner(object())
    actions = [
        Action("duplicate", 2, ActionType.READ_CLASS, "", "Read"),
        Action("duplicate", 3, "READ", "Service", "Read"),
    ]

    result = action_planner.validate(actions)

    assert result["valid"] is False
    assert result["errors"] == [
        "Action duplicate has order 2; expected 1.",
        "Action duplicate has an invalid target.",
        "Duplicate action id: duplicate.",
        "Action duplicate has order 3; expected 2.",
        "Action duplicate has an invalid action type.",
    ]


def test_action_and_metadata_are_immutable() -> None:
    action = Action("action-1", 1, ActionType.READ_CLASS, "Service", "Read")

    with pytest.raises(FrozenInstanceError):
        action.target = "Other"
    with pytest.raises(TypeError):
        action.metadata["goal"] = "Other"


def test_validate_accepts_optimized_action_queue() -> None:
    action_planner = ActionPlanner(object())

    result = action_planner.validate(action_planner.optimize(action_planner.create_actions(_plan())))

    assert result == {"valid": True, "errors": []}


def _plan() -> ExecutionPlan:
    return ExecutionPlan(
        goal="Modify AuthenticationService",
        summary="",
        estimated_complexity="MEDIUM",
        entry_points=[
            SimpleNamespace(title="AuthenticationService", kind="Class"),
        ],
        impacted_components=[],
        steps=[
            PlanStep(1, "Analyze entry points", "Read the entry point.", ""),
            PlanStep(2, "Identify dependencies", "Analyze dependencies.", ""),
            PlanStep(3, "Review call graph", "Analyze calls.", ""),
            PlanStep(4, "Evaluate impacted components", "Analyze impact.", ""),
            PlanStep(5, "Estimate risk", "Estimate risk.", ""),
            PlanStep(6, "Prepare modifications", "Prepare changes.", ""),
        ],
    )
