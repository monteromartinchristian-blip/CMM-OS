from cmm.domains.workflow_contracts import (
    DomainWorkflowContext,
    DomainWorkflowDefinition,
)
from cmm.domains.workflow_execution import DomainWorkflowExecutor
from cmm.domains.workflow_resolution import resolve_domain_workflow
from cmm.workflows.contracts import ApprovalDecision, WaitRequest, WorkflowNode
from cmm.workflows.engine import NodeExecution
from cmm.workflows.enums import WorkflowAvailabilityStatus, WorkflowRunStatus


def test_required_approval_is_waiting_until_gate_is_approved():
    definition = DomainWorkflowDefinition(
        "x.approval", "domain:x", "1.0.0", "Approval",
        nodes=(WorkflowNode("approve", "request_approval", "Approve", approval_gate="gate-1"),),
    )
    waiting = resolve_domain_workflow(definition, DomainWorkflowContext("domain:x"))
    assert waiting.status is WorkflowAvailabilityStatus.AVAILABLE
    available = resolve_domain_workflow(definition, DomainWorkflowContext("domain:x", approved_gates=frozenset({"gate-1"})))
    assert available.status is WorkflowAvailabilityStatus.AVAILABLE


def test_domain_executor_returns_validated_domain_result_after_wait_resume():
    calls = []
    definition = DomainWorkflowDefinition(
        "x.question", "domain:x", "1.0.0", "Question",
        nodes=(
            WorkflowNode("ask", "ask_question", "Ask", wait_condition={"field": "answer"}),
            WorkflowNode("finish", "complete", "Finish", dependencies=("ask",)),
        ),
    )

    def operation_adapter(node, run):
        calls.append(node.node_id)
        if node.node_id == "ask" and "answer" not in run.inputs:
            return NodeExecution.wait(WaitRequest("input", "answer required", "ask", {"field": "answer"}))
        return NodeExecution.complete({"ok": True})

    executor = DomainWorkflowExecutor(id_factory=lambda: "id", operation_adapter=operation_adapter)
    first = executor.execute(definition, DomainWorkflowContext("domain:x"), {})
    assert first.status is WorkflowRunStatus.WAITING_FOR_INPUT
    second = executor.resume(first, condition_resolved=True, inputs={"answer": "yes"})
    assert second.status is WorkflowRunStatus.COMPLETED
    assert calls == ["ask", "ask", "finish"]


def test_domain_approval_node_resumes_only_with_its_bound_approval():
    definition = DomainWorkflowDefinition(
        "x.approval.run", "domain:x", "1.0.0", "Approval run",
        nodes=(WorkflowNode("approve", "request_approval", "Approve", approval_gate="gate"),),
    )
    executor = DomainWorkflowExecutor(id_factory=lambda: "id")
    waiting = executor.execute(definition, DomainWorkflowContext("domain:x"), {"amount": 3})
    assert waiting.status is WorkflowRunStatus.WAITING_FOR_APPROVAL
    approval = waiting.common_run.wait_request.approval_request.decide(ApprovalDecision("human", True))
    resumed = executor.resume(waiting, condition_resolved=True, approval=approval)
    assert resumed.status is WorkflowRunStatus.COMPLETED
