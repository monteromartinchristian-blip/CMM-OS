from pathlib import Path

from kernel.planner.bootstrap import create_default_planner
from kernel.planner.context import PlanningContext
from kernel.planner.operations import (
    CreateClassOperation,
    EnsureImportOperation,
    InsertMethodOperation,
    ReplaceMethodOperation,
)
from kernel.planner.planner import PlanningError


def test_planning_context_defaults_and_metadata() -> None:
    context = PlanningContext(intent="crea una clase User")

    assert context.language == "python"
    assert context.has_project is False
    assert context.has_current_file is False

    updated = context.with_metadata(source="demo.py", repository="demo")

    assert updated is not context
    assert updated.metadata["source"] == "demo.py"
    assert context.metadata == {}


def test_planning_context_with_project_and_file() -> None:
    context = PlanningContext(
        intent="crea una clase User",
        project_root=Path("/tmp/project"),
        current_file=Path("/tmp/project/app.py"),
    )

    assert context.has_project is True
    assert context.has_current_file is True


def test_planner_creates_class() -> None:
    planner = create_default_planner()

    plan = planner.plan(PlanningContext(intent="crea una clase User"))

    assert len(plan) == 1
    assert isinstance(plan[0], CreateClassOperation)
    assert plan[0].class_name == "User"


def test_planner_adds_method() -> None:
    planner = create_default_planner()

    plan = planner.plan(PlanningContext(intent="añade un método login a User"))

    assert len(plan) == 1
    assert isinstance(plan[0], InsertMethodOperation)
    assert plan[0].method_name == "login"
    assert plan[0].target_class == "user"


def test_planner_replaces_method() -> None:
    planner = create_default_planner()

    plan = planner.plan(PlanningContext(intent="reemplaza el método login de User"))

    assert len(plan) == 1
    assert isinstance(plan[0], ReplaceMethodOperation)
    assert plan[0].method_name == "login"
    assert plan[0].target_class == "user"


def test_planner_ensures_import() -> None:
    planner = create_default_planner()

    plan = planner.plan(PlanningContext(intent="asegura el import typing"))

    assert len(plan) == 1
    assert isinstance(plan[0], EnsureImportOperation)
    assert plan[0].module == "typing"


def test_planner_builds_composite_plan() -> None:
    planner = create_default_planner()

    plan = planner.plan(PlanningContext(intent="crea una clase User con un método login"))

    assert len(plan) == 2
    assert isinstance(plan[0], CreateClassOperation)
    assert isinstance(plan[1], InsertMethodOperation)
    assert plan[0].class_name == "User"
    assert plan[1].method_name == "login"


def test_planner_rejects_unknown_intent() -> None:
    planner = create_default_planner()

    try:
        planner.plan(PlanningContext(intent="haz algo raro"))
    except PlanningError as exc:
        assert "Unable to interpret intent" in str(exc)
    else:
        raise AssertionError("Expected PlanningError")


def test_plan_contains_operations_in_order() -> None:
    planner = create_default_planner()

    plan = planner.plan(PlanningContext(intent="crea una clase User con un método login"))

    assert [type(operation).__name__ for operation in plan] == ["CreateClassOperation", "InsertMethodOperation"]
