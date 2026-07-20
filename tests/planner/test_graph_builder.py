from __future__ import annotations

from kernel.planner.execution_graph import ExecutionGraph
from kernel.planner.execution_plan import ExecutionPlan
from kernel.planner.graph_builder import GraphBuilder
from kernel.planner.operations import CreateClassOperation, InsertMethodOperation


def test_graph_builder_copies_all_operations() -> None:
    first = CreateClassOperation(class_name="User")
    second = InsertMethodOperation(
        target_class="User",
        method_name="full_name",
        source_code="def full_name(self):\n    return self.name",
        depends_on=(first.operation_id,),
    )

    plan = ExecutionPlan()
    plan.add(first)
    plan.add(second)

    graph = GraphBuilder().build(plan)

    assert isinstance(graph, ExecutionGraph)
    assert graph.contains(first.operation_id) is True
    assert graph.contains(second.operation_id) is True
    assert graph.get(first.operation_id) is first
    assert graph.get(second.operation_id) is second
    assert graph.operations() == (first, second)


def test_graph_builder_copies_dependencies() -> None:
    root = CreateClassOperation(class_name="User")
    child = InsertMethodOperation(
        target_class="User",
        method_name="full_name",
        source_code="def full_name(self):\n    return self.name",
        depends_on=(root.operation_id,),
    )

    plan = ExecutionPlan()
    plan.extend([root, child])

    graph = GraphBuilder().build(plan)

    assert graph.dependencies_of(child.operation_id) == (root.operation_id,)
    assert graph.dependents_of(root.operation_id) == (child.operation_id,)


def test_graph_builder_handles_empty_plans() -> None:
    graph = GraphBuilder().build(ExecutionPlan())

    assert isinstance(graph, ExecutionGraph)
    assert graph.operations() == ()