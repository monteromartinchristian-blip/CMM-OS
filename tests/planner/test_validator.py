from kernel.planner.execution_plan import ExecutionPlan
from kernel.planner.operations import (
    CreateClassOperation,
    EnsureImportOperation,
    InsertMethodOperation,
    ReplaceMethodOperation,
)
from kernel.planner.validator import PlanValidator


def test_validator_accepts_valid_plan() -> None:
    plan = ExecutionPlan()
    plan.add(CreateClassOperation(class_name="User"))
    plan.add(
        InsertMethodOperation(
            target_class="User",
            method_name="run",
            source_code="def run(self):\n    pass",
        )
    )

    result = PlanValidator().validate(plan)

    assert result.valid is True
    assert result.has_errors() is False


def test_validator_rejects_empty_plan() -> None:
    result = PlanValidator().validate(ExecutionPlan())

    assert result.valid is False
    assert any("at least one operation" in error for error in result.errors)


def test_validator_rejects_duplicate_operation_ids() -> None:
    plan = ExecutionPlan()
    first = CreateClassOperation(class_name="User")
    second = CreateClassOperation(class_name="Admin")
    object.__setattr__(first, "operation_id", second.operation_id)

    plan.add(first)
    plan.add(second)

    result = PlanValidator().validate(plan)

    assert result.valid is False
    assert any("Duplicate operation_id" in error for error in result.errors)


def test_validator_rejects_duplicate_operations() -> None:
    plan = ExecutionPlan()
    plan.add(CreateClassOperation(class_name="User"))
    plan.add(CreateClassOperation(class_name="User"))

    result = PlanValidator().validate(plan)

    assert result.valid is False
    assert any("Duplicate operation detected" in error for error in result.errors)


def test_validator_rejects_empty_class_name() -> None:
    plan = ExecutionPlan()
    plan.add(CreateClassOperation(class_name=""))

    result = PlanValidator().validate(plan)

    assert result.valid is False
    assert any("non-empty class_name" in error for error in result.errors)


def test_validator_rejects_empty_source_code() -> None:
    plan = ExecutionPlan()
    plan.add(InsertMethodOperation(target_class="User", method_name="run", source_code=""))

    result = PlanValidator().validate(plan)

    assert result.valid is False
    assert any("source_code" in error for error in result.errors)


def test_validator_rejects_empty_module() -> None:
    plan = ExecutionPlan()
    plan.add(EnsureImportOperation(module=""))

    result = PlanValidator().validate(plan)

    assert result.valid is False
    assert any("module" in error for error in result.errors)
