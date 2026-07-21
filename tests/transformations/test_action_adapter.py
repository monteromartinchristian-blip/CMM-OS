from __future__ import annotations

from dataclasses import dataclass, field

from cmm.execution import Action, ActionType, BackendActionAdapter
from cmm.transformations import (
    BasicTransformationExecutor,
    CreateModuleOperation,
    DeleteSymbolOperation,
    ExecutionPlan,
    ExecutionRequest,
    ExecutionStage,
    TransformationActionAdapter,
    TransformationDispatcher,
    TransformationGraph,
    TransformationGraphNode,
    TransformationStep,
    UpdateImportsOperation,
)


@dataclass
class RecordingTransformationAdapter:
    """Adapter double that records operations without using a backend."""

    received: list[object] = field(default_factory=list)

    def adapt(self, operation: object) -> object:
        self.received.append(operation)
        return {"operation": operation}


def test_transformation_action_adapter_creates_execution_request() -> None:
    operation = CreateModuleOperation(module_name="cmm.feature")

    request = TransformationActionAdapter().adapt(operation)

    assert isinstance(request, ExecutionRequest)
    assert request.operation == operation
    assert request.metadata == {
        "module_name": "cmm.feature",
        "project_root": ".",
    }


def test_backend_action_adapter_creates_generic_action() -> None:
    request = ExecutionRequest(
        operation=CreateModuleOperation(module_name="cmm.feature"),
        metadata={"module_name": "cmm.feature", "step_id": "create-feature"},
    )

    actions = BackendActionAdapter().adapt(
        ExecutionPlan(stages=(ExecutionStage(requests=(request,)),))
    )
    action = actions[0]

    assert isinstance(action, Action)
    assert action.id == "create-feature"
    assert action.order == 1
    assert action.action_type == ActionType.PREPARE_MODIFICATION
    assert action.target == "cmm.feature"
    assert action.description == "Create module: cmm.feature."
    assert action.metadata == {
        "module_name": "cmm.feature",
        "step_id": "create-feature",
    }


def test_dispatcher_delegates_domain_operation_to_adapter() -> None:
    adapter = RecordingTransformationAdapter()
    dispatcher = TransformationDispatcher(adapter)

    result = dispatcher.dispatch(
        DeleteSymbolOperation(symbol="legacy_symbol", module="cmm.legacy")
    )

    operation = adapter.received[0]
    assert isinstance(operation, DeleteSymbolOperation)
    assert operation.metadata() == {
        "symbol": "legacy_symbol",
        "module": "cmm.legacy",
    }
    assert result == {"operation": operation}


def test_executor_works_with_substituted_action_adapter() -> None:
    adapter = RecordingTransformationAdapter()
    executor = BasicTransformationExecutor(TransformationDispatcher(adapter))
    graph = TransformationGraph(
        nodes={
            "update-imports": TransformationGraphNode(
                step=TransformationStep(
                    id="update-imports",
                    operation=UpdateImportsOperation(module="cmm.api"),
                ),
            )
        }
    )

    result = executor.execute(graph)

    operation = adapter.received[0]
    assert isinstance(operation, UpdateImportsOperation)
    assert result == [{"operation": operation}]
