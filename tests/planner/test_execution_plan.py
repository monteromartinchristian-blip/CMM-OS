from kernel.planner.execution_plan import ExecutionPlan
from kernel.planner.operations import CreateClassOperation, InsertMethodOperation


def test_execution_plan_add_and_len() -> None:
    plan = ExecutionPlan()
    plan.add(CreateClassOperation(class_name="User"))

    assert len(plan) == 1
    assert plan[0].operation_type == "create_class"


def test_execution_plan_extend_and_remove() -> None:
    plan = ExecutionPlan()
    first = CreateClassOperation(class_name="User")
    second = InsertMethodOperation(
        target_class="User",
        method_name="run",
        source_code="def run(self):\n    pass",
    )

    plan.extend([first, second])
    plan.remove(first)

    assert len(plan) == 1
    assert plan[0] is second


def test_execution_plan_serialize_and_deserialize() -> None:
    plan = ExecutionPlan()
    plan.add(CreateClassOperation(class_name="User"))

    payload = plan.serialize()
    restored = ExecutionPlan.from_dict(payload)

    assert restored.plan_id == plan.plan_id
    assert len(restored) == 1
    assert restored[0].serialize()["operation_type"] == "create_class"
