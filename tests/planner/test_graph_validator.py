from __future__ import annotations

from kernel.planner.execution_graph import ExecutionGraph
from kernel.planner.graph_validator import GraphValidator
from kernel.planner.operations import CreateClassOperation, InsertMethodOperation


def test_graph_validator_accepts_valid_graph() -> None:
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

    result = GraphValidator().validate(graph)

    assert result.valid is True
    assert result.has_errors() is False


def test_graph_validator_rejects_missing_dependency() -> None:
    graph = ExecutionGraph()
    operation = InsertMethodOperation(
        target_class="User",
        method_name="full_name",
        source_code="def full_name(self):\n    return self.name",
    )
    object.__setattr__(operation, "depends_on", (CreateClassOperation(class_name="Ghost").operation_id,))

    graph.add_operation(operation)

    result = GraphValidator().validate(graph)

    assert result.valid is False
    assert any("Missing dependency" in error for error in result.errors)


def test_graph_validator_rejects_simple_cycle() -> None:
    graph = ExecutionGraph()
    first = CreateClassOperation(class_name="User")
    second = InsertMethodOperation(
        target_class="User",
        method_name="full_name",
        source_code="def full_name(self):\n    return self.name",
        depends_on=(first.operation_id,),
    )
    object.__setattr__(first, "depends_on", (second.operation_id,))

    graph.add_operation(first)
    graph.add_operation(second)

    result = GraphValidator().validate(graph)

    assert result.valid is False
    assert any("Cycle detected" in error for error in result.errors)


def test_graph_validator_rejects_multi_node_cycle() -> None:
    graph = ExecutionGraph()
    first = CreateClassOperation(class_name="A")
    second = CreateClassOperation(class_name="B")
    third = CreateClassOperation(class_name="C")

    object.__setattr__(first, "depends_on", (second.operation_id,))
    object.__setattr__(second, "depends_on", (third.operation_id,))
    object.__setattr__(third, "depends_on", (first.operation_id,))

    graph.add_operation(first)
    graph.add_operation(second)
    graph.add_operation(third)

    result = GraphValidator().validate(graph)

    assert result.valid is False
    assert any("Cycle detected" in error for error in result.errors)


def test_graph_validator_accepts_empty_graph() -> None:
    result = GraphValidator().validate(ExecutionGraph())

    assert result.valid is True
    assert result.has_errors() is False
