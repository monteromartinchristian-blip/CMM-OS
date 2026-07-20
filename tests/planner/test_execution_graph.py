from __future__ import annotations

from uuid import UUID

from kernel.planner.execution_graph import ExecutionGraph
from kernel.planner.operations import CreateClassOperation, InsertMethodOperation


def test_execution_graph_adds_and_retrieves_operations() -> None:
    graph = ExecutionGraph()
    operation = CreateClassOperation(class_name="User")

    graph.add_operation(operation)

    assert graph.contains(operation.operation_id) is True
    assert graph.get(operation.operation_id) is operation
    assert graph.operations() == (operation,)


def test_execution_graph_tracks_dependencies_and_dependents() -> None:
    graph = ExecutionGraph()
    root = CreateClassOperation(class_name="User")
    child = InsertMethodOperation(
        target_class="User",
        method_name="full_name",
        source_code="def full_name(self):\n    return self.name",
        depends_on=(root.operation_id,),
    )

    graph.add_operation(root)
    graph.add_operation(child)

    assert graph.dependencies_of(child.operation_id) == (root.operation_id,)
    assert graph.dependents_of(root.operation_id) == (child.operation_id,)


def test_execution_graph_returns_empty_tuples_for_missing_nodes() -> None:
    graph = ExecutionGraph()
    missing_id = UUID("00000000-0000-0000-0000-000000000000")

    assert graph.get(missing_id) is None
    assert graph.contains(missing_id) is False
    assert graph.dependencies_of(missing_id) == ()
    assert graph.dependents_of(missing_id) == ()
    assert graph.operations() == ()


def test_execution_graph_preserves_insertion_order() -> None:
    graph = ExecutionGraph()
    first = CreateClassOperation(class_name="User")
    second = CreateClassOperation(class_name="Admin")

    graph.add_operation(first)
    graph.add_operation(second)

    assert graph.operations() == (first, second)
