from datetime import datetime, timezone

import pytest

from cmm.workflows.contracts import (
    ApprovalDecision,
    ApprovalRequest,
    WaitRequest,
    WorkflowDefinition,
    WorkflowNode,
)
from cmm.workflows.engine import NodeExecution, WorkflowEngine
from cmm.workflows.enums import ApprovalStatus, WorkflowRunStatus
from cmm.workflows.errors import WorkflowStateError


def test_waiting_for_input_requires_checkpoint_and_resumes_without_repeating_completed_nodes():
    calls = []

    def adapter(node, run):
        calls.append(node.node_id)
        if node.node_id == "question" and "answer" not in run.inputs:
            return NodeExecution.wait(WaitRequest("input", "missing answer", node.node_id, {"field": "answer"}))
        return NodeExecution.complete({"ok": True})

    definition = WorkflowDefinition(
        "wait.flow", "1.0.0", "Wait", nodes=(
            WorkflowNode("prepare", "load_resource", "Prepare"),
            WorkflowNode("question", "ask_question", "Question", dependencies=("prepare",), wait_condition={"field": "answer"}),
            WorkflowNode("finish", "complete", "Finish", dependencies=("question",)),
        )
    )
    engine = WorkflowEngine(definition, id_factory=lambda: "run-1", clock=lambda: datetime.now(timezone.utc), node_adapter=adapter)
    paused = engine.start({})
    assert paused.run.status is WorkflowRunStatus.WAITING_FOR_INPUT
    assert paused.run.checkpoint_id
    resumed = engine.resume(paused.run, condition_resolved=True, inputs={"answer": "yes"})
    assert resumed.run.status is WorkflowRunStatus.COMPLETED
    assert calls == ["prepare", "question", "question", "finish"]


def test_approval_fingerprint_cannot_be_reused_for_another_run_or_input():
    request = ApprovalRequest("approval-1", "wf", "1.0.0", "run-1", "node-1", {"amount": 10})
    assert request.status is ApprovalStatus.PENDING
    approved = request.decide(ApprovalDecision("approver", True))
    assert approved.status is ApprovalStatus.APPROVED
    with pytest.raises(WorkflowStateError):
        approved.assert_matches(run_id="run-2", inputs={"amount": 10})
    with pytest.raises(WorkflowStateError):
        approved.assert_matches(run_id="run-1", inputs={"amount": 11})


def test_retry_records_attempts_and_does_not_retry_contract_errors():
    attempts = []

    def adapter(node, run):
        attempts.append(node.node_id)
        if len(attempts) < 2:
            return NodeExecution.failure("temporary", retryable=True)
        return NodeExecution.complete({"ok": True})

    definition = WorkflowDefinition("retry.flow", "1.0.0", "Retry", nodes=(WorkflowNode("work", "complete", "Work"),))
    engine = WorkflowEngine(definition, id_factory=lambda: "run-1", node_adapter=adapter)
    result = engine.start({}, retry_policy={"work": 2})
    assert result.run.status is WorkflowRunStatus.COMPLETED
    assert result.attempts["work"] == 2
