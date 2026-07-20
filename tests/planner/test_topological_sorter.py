from __future__ import annotations

from kernel.planner.execution_graph import ExecutionGraph
from kernel.planner.operations import CreateClassOperation, InsertMethodOperation
from kernel.planner.topological_sorter import TopologicalSorter


def test_topological_sorter_handles_linear_graph() -> None:
    graph = ExecutionGraph()
    first = CreateClassOperation(class_name="User")
    second = InsertMethodOperation(
        target_class="User",
        method_name="full_name",
        source_code="def full_name(self):\n    return self.name",
        depends_on=(first.operation_id,),
    )

    graph.add_operation(first)
    graph.add_operation(second)

    ordered = TopologicalSorter().sort(graph)

    assert ordered == [first, second]


def test_topological_sorter_handles_branching_graph() -> None:
    graph = ExecutionGraph()
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

    graph.add_operation(root)
    graph.add_operation(left)
    graph.add_operation(right)

    ordered = TopologicalSorter().sort(graph)

    assert ordered[0] is root
    assert {operation.operation_id for operation in ordered[1:]} == {left.operation_id, right.operation_id}


def test_topological_sorter_handles_multiple_roots() -> None:
    graph = ExecutionGraph()
    first = CreateClassOperation(class_name="User")
    second = CreateClassOperation(class_name="Admin")
    child = InsertMethodOperation(
        target_class="User",
        method_name="full_name",
        source_code="def full_name(self):\n    return self.name",
        depends_on=(first.operation_id,),
    )

    graph.add_operation(first)
    graph.add_operation(second)
    graph.add_operation(child)

    ordered = TopologicalSorter().sort(graph)

    assert ordered[0] is first
    assert ordered[1] is second
    assert ordered[2] is child


def test_topological_sorter_handles_empty_graph() -> None:
    assert TopologicalSorter().sort(ExecutionGraph()) == []


def test_topological_sorter_handles_complex_dependencies() -> None:
    graph = ExecutionGraph()
    root_a = CreateClassOperation(class_name="A")
    root_b = CreateClassOperation(class_name="B")
    middle = InsertMethodOperation(
        target_class="A",
        method_name="mid",
        source_code="def mid(self):\n    pass",
        depends_on=(root_a.operation_id, root_b.operation_id),
    )
    leaf = InsertMethodOperation(
        target_class="A",
        method_name="leaf",
        source_code="def leaf(self):\n    pass",
        depends_on=(middle.operation_id,),
    )

    graph.add_operation(root_a)
    graph.add_operation(root_b)
    graph.add_operation(middle)
    graph.add_operation(leaf)

    ordered = TopologicalSorter().sort(graph)

    assert ordered.index(root_a) < ordered.index(middle)
    assert ordered.index(root_b) < ordered.index(middle)
    assert ordered.index(middle) < ordered.index(leaf)
