from __future__ import annotations

from dataclasses import dataclass, field

from cmm.transformations import (
    BasicTransformationExecutor,
    BasicTransformationPlanner,
    TransformationDispatcher,
    TransformationGraph,
    TransformationGraphNode,
    TransformationPlan,
    TransformationStep,
)


@dataclass
class RecordingDispatcher(TransformationDispatcher):
    """Test dispatcher that records received steps in execution order."""

    received_step_ids: list[str] = field(default_factory=list)

    def dispatch(self, step: TransformationStep) -> object:
        self.received_step_ids.append(step.id)
        return {"step_id": step.id, "operation": step.operation}


def test_basic_planner_builds_linear_dependency_graph() -> None:
    planner = BasicTransformationPlanner()
    plan = TransformationPlan(
        goal="Reorganize project structure",
        steps=[
            TransformationStep(id="step-1", operation="create_module"),
            TransformationStep(id="step-2", operation="move_class"),
            TransformationStep(id="step-3", operation="update_imports"),
        ],
    )

    graph = planner.build_graph(plan)

    assert list(graph.nodes.keys()) == ["step-1", "step-2", "step-3"]
    assert graph.nodes["step-1"].dependencies == ()
    assert graph.nodes["step-2"].dependencies == ("step-1",)
    assert graph.nodes["step-3"].dependencies == ("step-2",)


def test_basic_executor_traverses_all_nodes() -> None:
    dispatcher = RecordingDispatcher()
    executor = BasicTransformationExecutor(dispatcher)
    graph = TransformationGraph(
        nodes={
            "step-1": TransformationGraphNode(
                step=TransformationStep(id="step-1", operation="create_module"),
                dependencies=(),
            ),
            "step-2": TransformationGraphNode(
                step=TransformationStep(id="step-2", operation="move_class"),
                dependencies=("step-1",),
            ),
            "step-3": TransformationGraphNode(
                step=TransformationStep(id="step-3", operation="update_imports"),
                dependencies=("step-2",),
            ),
        }
    )

    result = executor.execute(graph)

    assert len(result) == 3
    assert dispatcher.received_step_ids == ["step-1", "step-2", "step-3"]


def test_basic_executor_respects_dependency_order() -> None:
    dispatcher = RecordingDispatcher()
    executor = BasicTransformationExecutor(dispatcher)
    graph = TransformationGraph(
        nodes={
            "step-3": TransformationGraphNode(
                step=TransformationStep(id="step-3", operation="update_imports"),
                dependencies=("step-2",),
            ),
            "step-1": TransformationGraphNode(
                step=TransformationStep(id="step-1", operation="create_module"),
                dependencies=(),
            ),
            "step-2": TransformationGraphNode(
                step=TransformationStep(id="step-2", operation="move_class"),
                dependencies=("step-1",),
            ),
        }
    )

    executor.execute(graph)

    assert dispatcher.received_step_ids == ["step-1", "step-2", "step-3"]


def test_dispatcher_receives_steps_from_planned_graph_in_expected_order() -> None:
    planner = BasicTransformationPlanner()
    dispatcher = RecordingDispatcher()
    executor = BasicTransformationExecutor(dispatcher)
    plan = TransformationPlan(
        goal="Extract module",
        steps=[
            TransformationStep(id="step-a", operation="create_module"),
            TransformationStep(id="step-b", operation="move_function"),
            TransformationStep(id="step-c", operation="delete_symbol"),
        ],
    )

    graph = planner.build_graph(plan)
    results = executor.execute(graph)

    assert dispatcher.received_step_ids == ["step-a", "step-b", "step-c"]
    assert [item["step_id"] for item in results] == ["step-a", "step-b", "step-c"]
