from datetime import datetime, timezone

from cmm.workflows.contracts import (
    WaitRequest,
    WorkflowDefinition,
    WorkflowNode,
    WorkflowRun,
)
from cmm.workflows.engine import NodeExecution, WorkflowEngine
from cmm.workflows.enums import WorkflowRunStatus


def test_subworkflow_adapter_receives_parent_and_root_run_ids():
    seen = []

    def adapter(node, run):
        seen.append((run.run_id, run.root_run_id))
        return NodeExecution.complete({"child": "completed"}, subworkflow_result={"status": "completed"})

    definition = WorkflowDefinition("parent", "1.0.0", "Parent", nodes=(WorkflowNode("child", "invoke_subworkflow", "Child", subworkflow_id="child", subworkflow_version="1.0.0"),))
    engine = WorkflowEngine(definition, id_factory=lambda: "run-1", node_adapter=adapter, root_run_id="root-1")
    result = engine.start({})
    assert result.run.status is WorkflowRunStatus.COMPLETED
    assert seen == [("run-1", "root-1")]


def test_subworkflow_hierarchy_survives_wait_and_resume():
    attempts = 0

    def adapter(node, run):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return NodeExecution.wait(WaitRequest("resource", "child unavailable", node.node_id))
        return NodeExecution.complete({"child": "completed"}, subworkflow_result={"status": "completed"})

    definition = WorkflowDefinition(
        "parent", "1.0.0", "Parent",
        nodes=(WorkflowNode("child", "invoke_subworkflow", "Child", subworkflow_id="child", subworkflow_version="1.0.0"),),
    )
    engine = WorkflowEngine(
        definition,
        id_factory=lambda: "run-1",
        node_adapter=adapter,
        parent_run_id="parent-run",
        root_run_id="root-run",
        depth=3,
    )
    waiting = engine.start({})
    resumed = engine.resume(waiting.run, condition_resolved=True)

    assert resumed.run.status is WorkflowRunStatus.COMPLETED
    assert resumed.run.parent_run_id == "parent-run"
    assert resumed.run.root_run_id == "root-run"
    assert resumed.run.depth == 3
    assert resumed.node_results["child"].subworkflow_result == {"status": "completed"}
    assert resumed.attempts == {"child": 2}


def test_subworkflow_lifecycle_preserves_hierarchy_and_execution_context():
    definition = WorkflowDefinition(
        "parent", "1.0.0", "Parent",
        nodes=(WorkflowNode("child", "invoke_subworkflow", "Child", subworkflow_id="child", subworkflow_version="1.0.0"),),
    )
    engine = WorkflowEngine(definition, id_factory=lambda: "run-1", node_adapter=lambda node, run: NodeExecution.complete())
    started_at = datetime.now(timezone.utc)
    common = {
        "inputs": {"request": "value"},
        "outputs": {"child": {"status": "saved"}},
        "checkpoint_id": "checkpoint-1",
        "started_at": started_at,
        "parent_run_id": "parent-run",
        "root_run_id": "root-run",
        "depth": 3,
    }
    running = WorkflowRun("child-run", "parent", "1.0.0", status=WorkflowRunStatus.RUNNING, **common)
    failed = WorkflowRun("child-run", "parent", "1.0.0", status=WorkflowRunStatus.FAILED, failed_nodes=("child",), error_code="child.failed", **common)

    paused = engine.pause(running, "checkpoint-paused")
    cancelled = engine.cancel(running)
    recovering = engine.recover(failed)

    for run, checkpoint_id in ((paused, "checkpoint-paused"), (cancelled, "checkpoint-1"), (recovering, "checkpoint-1")):
        assert run.parent_run_id == "parent-run"
        assert run.root_run_id == "root-run"
        assert run.depth == 3
        assert run.inputs == {"request": "value"}
        assert run.outputs == {"child": {"status": "saved"}}
        assert run.started_at == started_at
        assert run.checkpoint_id == checkpoint_id
