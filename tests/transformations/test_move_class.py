from __future__ import annotations

from dataclasses import dataclass, field

from cmm.transformations import (
    BasicTransformationExecutor,
    BasicTransformationPlanner,
    CopySymbolOperation,
    DeleteSymbolOperation,
    MoveClassTransformation,
    TransformationGraph,
    TransformationStep,
    UpdateImportsOperation,
    ValidateProjectOperation,
)


@dataclass
class RecordingDispatcher:
    """Dispatcher double that records operations without executing them."""

    received_operations: list[object] = field(default_factory=list)

    def dispatch(self, operation: object) -> object:
        self.received_operations.append(operation)
        return operation.name


def _transformation() -> MoveClassTransformation:
    return MoveClassTransformation(
        class_name="Service",
        source_module="cmm.source",
        target_module="cmm.target",
    )


def test_move_class_builds_four_primitive_operation_steps() -> None:
    plan = _transformation().build_plan()

    assert len(plan.steps) == 4
    assert [step.operation.name for step in plan.steps] == [
        "copy_symbol",
        "update_imports",
        "delete_symbol",
        "validate_project",
    ]
    assert [
        step.operation for step in plan.steps
    ] == [
        CopySymbolOperation(
            symbol="Service",
            source="cmm.source",
            destination="cmm.target",
            symbol_kind="class",
        ),
        UpdateImportsOperation(
            module="cmm.target",
            old_module="cmm.source",
            new_module="cmm.target",
            symbol_name="Service",
            new_symbol_name="Service",
        ),
        DeleteSymbolOperation(symbol="Service", module="cmm.source", symbol_kind="class"),
        ValidateProjectOperation(scope="project"),
    ]


def test_move_class_plan_builds_valid_linear_graph() -> None:
    plan = _transformation().build_plan()

    graph = BasicTransformationPlanner().build_graph(plan)

    assert isinstance(graph, TransformationGraph)
    assert list(graph.nodes) == [step.id for step in plan.steps]
    assert graph.nodes[plan.steps[0].id].dependencies == ()
    assert graph.nodes[plan.steps[1].id].dependencies == (plan.steps[0].id,)
    assert graph.nodes[plan.steps[2].id].dependencies == (plan.steps[1].id,)
    assert graph.nodes[plan.steps[3].id].dependencies == (plan.steps[2].id,)


def test_move_class_graph_can_be_traversed_with_dispatcher_mock() -> None:
    plan = _transformation().build_plan()
    graph = BasicTransformationPlanner().build_graph(plan)
    dispatcher = RecordingDispatcher()

    result = BasicTransformationExecutor(dispatcher).execute(graph)

    assert [operation.name for operation in dispatcher.received_operations] == [
        step.operation.name for step in plan.steps
    ]
    assert result == [step.operation.name for step in plan.steps]
