from datetime import datetime, timezone

import pytest

from cmm.workflows.contracts import WorkflowDefinition, WorkflowNode, WorkflowRun
from cmm.workflows.engine import NodeExecution, WorkflowEngine
from cmm.workflows.enums import WorkflowRunStatus
from cmm.workflows.errors import WorkflowExecutionError, WorkflowStateError


def test_engine_without_adapter_cannot_execute_or_complete_nodes():
    definition = WorkflowDefinition("x", "1.0.0", "X", nodes=(WorkflowNode("n", "complete", "N"),))
    with pytest.raises(WorkflowExecutionError, match="node_adapter is required"):
        WorkflowEngine(definition, id_factory=lambda: "run-1", clock=lambda: datetime.now(timezone.utc))


def test_engine_with_explicit_adapter_runs_nodes():
    definition = WorkflowDefinition("x", "1.0.0", "X", nodes=(WorkflowNode("n", "complete", "N"),))
    engine = WorkflowEngine(definition, id_factory=lambda: "run-1", clock=lambda: datetime.now(timezone.utc), node_adapter=lambda node, run: NodeExecution.complete())
    result = engine.start({})
    assert result.run.status is WorkflowRunStatus.COMPLETED
    assert result.run.completed_nodes == ("n",)


def test_ready_node_adapter_sees_completed_producer_output_in_run() -> None:
    definition = WorkflowDefinition(
        "output-visibility",
        "1.0.0",
        "Output visibility",
        nodes=(
            WorkflowNode(
                "producer",
                "execute_operation",
                "Producer",
                operation_id="test.produce",
                operation_version="1.0.0",
            ),
            WorkflowNode(
                "consumer",
                "execute_operation",
                "Consumer",
                dependencies=("producer",),
                operation_id="test.consume",
                operation_version="1.0.0",
            ),
        ),
    )

    def adapter(node, run):
        if node.node_id == "producer":
            return NodeExecution.complete({"value": "produced"})
        assert run.outputs["producer"] == {"value": "produced"}
        assert run.completed_nodes == ()
        assert run.failed_nodes == ()
        assert run.waiting_nodes == ()
        assert run.skipped_nodes == ()
        return NodeExecution.complete({"consumed": True})

    result = WorkflowEngine(
        definition,
        id_factory=lambda: "owned-id",
        node_adapter=adapter,
    ).start({})

    assert result.run.outputs["consumer"] == {"consumed": True}


def test_ready_node_adapter_sees_multiple_accumulated_outputs() -> None:
    definition = WorkflowDefinition(
        "multiple-output-visibility",
        "1.0.0",
        "Multiple output visibility",
        nodes=(
            WorkflowNode(
                "producer-a",
                "execute_operation",
                "Producer A",
                operation_id="test.produce_a",
                operation_version="1.0.0",
            ),
            WorkflowNode(
                "producer-b",
                "execute_operation",
                "Producer B",
                operation_id="test.produce_b",
                operation_version="1.0.0",
            ),
            WorkflowNode(
                "consumer",
                "execute_operation",
                "Consumer",
                dependencies=("producer-a", "producer-b"),
                operation_id="test.consume",
                operation_version="1.0.0",
            ),
        ),
    )

    def adapter(node, run):
        if node.node_id.startswith("producer"):
            return NodeExecution.complete({"producer": node.node_id})
        assert run.outputs == {
            "producer-a": {"producer": "producer-a"},
            "producer-b": {"producer": "producer-b"},
        }
        return NodeExecution.complete({"count": len(run.outputs)})

    result = WorkflowEngine(
        definition,
        id_factory=lambda: "owned-id",
        node_adapter=adapter,
    ).start({})

    assert result.run.outputs["consumer"] == {"count": 2}


def test_engine_lifecycle_pause_resume_cancel_and_recovery():
    definition = WorkflowDefinition("x", "1.0.0", "X", nodes=(WorkflowNode("n", "complete", "N"),))
    engine = WorkflowEngine(definition, id_factory=lambda: "run-1", node_adapter=lambda node, run: NodeExecution.complete())
    run = engine.start({}).run
    with pytest.raises(WorkflowStateError):
        engine.cancel(run)
    running = WorkflowRun("r", "x", "1.0.0", status=WorkflowRunStatus.RUNNING)
    paused = engine.pause(running, "checkpoint-1")
    assert engine.resume(paused, condition_resolved=True).status is WorkflowRunStatus.RUNNING
    assert engine.cancel(running).status is WorkflowRunStatus.CANCELLED
