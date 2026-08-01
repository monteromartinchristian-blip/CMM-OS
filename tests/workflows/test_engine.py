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
