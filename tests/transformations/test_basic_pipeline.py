from __future__ import annotations

from cmm.transformations import (
    BasicTransformationExecutor,
    BasicTransformationPlanner,
    CreateFileOperation,
    CreateModuleOperation,
    DeleteFileOperation,
    TransformationGraph,
    TransformationGraphNode,
    TransformationPlan,
    TransformationOperation,
    TransformationStep,
)


class RecordingDispatcher:
    """Test dispatcher that records received steps in execution order."""

    def __init__(self) -> None:
        self.received_operation_names: list[str] = []

    def dispatch(self, operation: TransformationOperation) -> object:
        self.received_operation_names.append(operation.name)
        return {"operation": operation.name}


def test_basic_planner_builds_linear_dependency_graph() -> None:
    planner = BasicTransformationPlanner()
    plan = TransformationPlan(
        steps=(
            TransformationStep(
                id="step-1",
                operation=CreateFileOperation(path="cmm/first.py"),
            ),
            TransformationStep(
                id="step-2",
                operation=CreateModuleOperation(module_name="cmm.second"),
            ),
            TransformationStep(
                id="step-3",
                operation=DeleteFileOperation(path="cmm/third.py"),
            ),
        ),
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
                step=TransformationStep(
                    id="step-1",
                    operation=CreateFileOperation(path="cmm/first.py"),
                ),
                dependencies=(),
            ),
            "step-2": TransformationGraphNode(
                step=TransformationStep(
                    id="step-2",
                    operation=CreateModuleOperation(module_name="cmm.second"),
                ),
                dependencies=("step-1",),
            ),
            "step-3": TransformationGraphNode(
                step=TransformationStep(
                    id="step-3",
                    operation=DeleteFileOperation(path="cmm/third.py"),
                ),
                dependencies=("step-2",),
            ),
        }
    )

    result = executor.execute(graph)

    assert len(result) == 3
    assert dispatcher.received_operation_names == [
        "create_file",
        "create_module",
        "delete_file",
    ]


def test_basic_executor_respects_dependency_order() -> None:
    dispatcher = RecordingDispatcher()
    executor = BasicTransformationExecutor(dispatcher)
    graph = TransformationGraph(
        nodes={
            "step-3": TransformationGraphNode(
                step=TransformationStep(
                    id="step-3",
                    operation=DeleteFileOperation(path="cmm/third.py"),
                ),
                dependencies=("step-2",),
            ),
            "step-1": TransformationGraphNode(
                step=TransformationStep(
                    id="step-1",
                    operation=CreateFileOperation(path="cmm/first.py"),
                ),
                dependencies=(),
            ),
            "step-2": TransformationGraphNode(
                step=TransformationStep(
                    id="step-2",
                    operation=CreateModuleOperation(module_name="cmm.second"),
                ),
                dependencies=("step-1",),
            ),
        }
    )

    executor.execute(graph)

    assert dispatcher.received_operation_names == [
        "create_file",
        "create_module",
        "delete_file",
    ]


def test_dispatcher_receives_steps_from_planned_graph_in_expected_order() -> None:
    planner = BasicTransformationPlanner()
    dispatcher = RecordingDispatcher()
    executor = BasicTransformationExecutor(dispatcher)
    plan = TransformationPlan(
        steps=(
            TransformationStep(
                id="step-a",
                operation=CreateFileOperation(path="cmm/a.py"),
            ),
            TransformationStep(
                id="step-b",
                operation=CreateModuleOperation(module_name="cmm.b"),
            ),
            TransformationStep(
                id="step-c",
                operation=DeleteFileOperation(path="cmm/c.py"),
            ),
        ),
    )

    graph = planner.build_graph(plan)
    results = executor.execute(graph)

    assert dispatcher.received_operation_names == [
        "create_file",
        "create_module",
        "delete_file",
    ]
    assert [item["operation"] for item in results] == [
        "create_file",
        "create_module",
        "delete_file",
    ]
