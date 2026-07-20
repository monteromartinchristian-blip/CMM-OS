from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

from kernel.planner.execution_plan import ExecutionPlan
from kernel.planner.operations import CreateClassOperation, EnsureImportOperation, InsertMethodOperation
from kernel.planner.plan_validator import PlanValidator


def test_plan_validator_accepts_valid_plan() -> None:
    plan = ExecutionPlan()
    plan.add(CreateClassOperation(class_name="User"))
    plan.add(
        InsertMethodOperation(
            target_class="User",
            method_name="hello",
            source_code="def hello(self):\n    pass",
        )
    )

    result = PlanValidator().validate(plan)

    assert result.valid is True
    assert result.errors == []
    assert result.warnings == []


def test_plan_validator_rejects_duplicate_create_class() -> None:
    plan = ExecutionPlan()
    plan.add(CreateClassOperation(class_name="User"))
    plan.add(CreateClassOperation(class_name="User"))

    result = PlanValidator().validate(plan)

    assert result.valid is False
    assert any("Duplicate operation detected" in error for error in result.errors)


def test_plan_validator_rejects_duplicate_imports() -> None:
    plan = ExecutionPlan()
    plan.add(EnsureImportOperation(module="logging"))
    plan.add(EnsureImportOperation(module="logging"))

    result = PlanValidator().validate(plan)

    assert result.valid is False
    assert any("Duplicate operation detected" in error for error in result.errors)


def test_plan_validator_rejects_missing_required_parameters() -> None:
    operation = object.__new__(InsertMethodOperation)
    object.__setattr__(operation, "id", uuid4())
    object.__setattr__(operation, "depends_on", tuple())
    object.__setattr__(operation, "metadata", {})
    object.__setattr__(operation, "tags", tuple())
    object.__setattr__(operation, "target_class", "User")
    object.__setattr__(operation, "method_name", "hello")

    plan = ExecutionPlan()
    plan.add(operation)

    result = PlanValidator().validate(plan)

    assert result.valid is False
    assert any("missing required parameter source_code" in error for error in result.errors)


def test_plan_validator_rejects_empty_source_code() -> None:
    plan = ExecutionPlan()
    plan.add(
        InsertMethodOperation(
            target_class="User",
            method_name="hello",
            source_code="",
        )
    )

    result = PlanValidator().validate(plan)

    assert result.valid is False
    assert any("source_code" in error for error in result.errors)


def test_plan_validator_rejects_empty_names() -> None:
    plan = ExecutionPlan()
    plan.add(CreateClassOperation(class_name=""))

    result = PlanValidator().validate(plan)

    assert result.valid is False
    assert any("non-empty class_name" in error for error in result.errors)
