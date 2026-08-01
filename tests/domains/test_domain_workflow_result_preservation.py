from cmm.domains.workflow_contracts import (
    DomainWorkflowContext,
    DomainWorkflowDefinition,
)
from cmm.domains.workflow_execution import DomainWorkflowExecutor
from cmm.workflows.contracts import (
    ApprovalDecision,
    ApprovalRequest,
    WaitRequest,
    WorkflowNode,
)
from cmm.workflows.engine import NodeExecution
from cmm.workflows.enums import WorkflowNodeStatus, WorkflowRunStatus


def test_execute_result_preserves_operation_result_events_and_attempts():
    definition = DomainWorkflowDefinition(
        "x.operation", "domain:x", "1.0.0", "Operation",
        nodes=(
            WorkflowNode("op", "execute_operation", "Operation", operation_id="op.x", operation_version="1.0.0"),
            WorkflowNode("finish", "complete", "Finish", dependencies=("op",)),
        ),
    )
    def adapter(node, run):
        return {"value": 7} if node.operation_id else NodeExecution.complete({"done": True})

    executor = DomainWorkflowExecutor(id_factory=lambda: "id", operation_adapter=adapter)
    result = executor.execute_result(definition, DomainWorkflowContext("domain:x", available_operations=frozenset({"op.x"})), {})
    assert result.status is WorkflowRunStatus.COMPLETED
    assert result.common_result.node_results["op"].status is WorkflowNodeStatus.COMPLETED
    assert result.common_result.node_results["op"].operation_result == {"value": 7}
    assert result.common_result.events
    assert result.common_result.attempts["op"] == 1


def test_resume_rehydrates_results_events_attempts_outputs_and_hierarchy():
    definition = DomainWorkflowDefinition(
        "x.resume", "domain:x", "1.0.0", "Resume",
        nodes=(
            WorkflowNode("a", "execute_operation", "A", operation_id="op.a", operation_version="1.0.0"),
            WorkflowNode("b", "request_approval", "B", dependencies=("a",), approval_gate="gate"),
            WorkflowNode("c", "complete", "C", dependencies=("b",)),
        ),
    )
    calls: list[str] = []

    def adapter(node, run):
        calls.append(node.node_id)
        if node.node_id == "a":
            return NodeExecution.complete({"a": True}, operation_result={"operation": "a"})
        if node.node_id == "b" and calls.count("b") == 1:
            approval = ApprovalRequest("approval", run.workflow_id, run.workflow_version, run.run_id, node.node_id, run.inputs)
            return NodeExecution.wait(WaitRequest("approval", "approval required", node.node_id, approval_request=approval))
        return NodeExecution.complete({node.node_id: True})

    executor = DomainWorkflowExecutor(
        id_factory=lambda: "id",
        operation_adapter=adapter,
        parent_run_id="parent-run",
        root_run_id="root-run",
        depth=2,
    )
    first = executor.execute(definition, DomainWorkflowContext("domain:x", available_operations=frozenset({"op.a"})), {"request": 1})
    approval = first.common_run.wait_request.approval_request.decide(ApprovalDecision("human", True))
    resumed = executor.resume(first, condition_resolved=True, approval=approval)

    execution = resumed.execution_result
    assert resumed.status is WorkflowRunStatus.COMPLETED
    assert resumed.common_run.completed_nodes == ("a", "b", "c")
    assert set(execution.node_results) == {"a", "b", "c"}
    assert execution.attempts == {"a": 1, "b": 2, "c": 1}
    assert len(execution.events) == 6
    assert [event.event_type for event in execution.events] == [
        "workflow.running", "node.completed", "node.waiting", "node.completed", "node.completed", "workflow.completed",
    ]
    assert execution.node_results["a"].output == {"a": True}
    assert execution.node_results["a"].operation_result == {"operation": "a"}
    assert execution.node_results["b"].output == {"b": True}
    assert resumed.common_run.outputs == {"a": {"a": True}, "b": {"b": True}, "c": {"c": True}}
    assert first.common_run.checkpoint_id == "id"
    assert resumed.common_run.checkpoint_id is None
    assert resumed.common_run.parent_run_id == "parent-run"
    assert resumed.common_run.root_run_id == "root-run"
    assert resumed.common_run.depth == 2
