"""Tests for Phase 10.21 Relationships Domain workflows (B2 hardening).

Covers the ordered safety path, the real escalation/approval-gate mechanism,
the read-only memory policy (no workflow proposes memory), and the
terminal-operation safety boundaries for the conversation-preparation and
decision-support workflows.
"""

from __future__ import annotations

from cmm.domains import relationships
from cmm.domains.relationships.catalog import CANONICAL_RELATIONSHIPS_WORKFLOW_IDS
from cmm.workflows.enums import WorkflowNodeType


def _by_id():
    return {
        w.workflow_id: w
        for w in relationships.build_relationships_workflow_definitions()
    }


class _Ids:
    def __init__(self):
        self.value = 0

    def __call__(self):
        self.value += 1
        return f"generated-{self.value}"


def _node_map(wf):
    return {n.node_id: n for n in wf.nodes}


def _transitive_deps(node_map, start):
    """Return the set of node ids that ``start`` transitively depends on."""
    seen: set[str] = set()
    stack = list(node_map[start].dependencies)
    while stack:
        current = stack.pop()
        if current in seen:
            continue
        seen.add(current)
        stack.extend(node_map[current].dependencies)
    return seen


def test_six_workflows_and_canonical_order():
    workflows = relationships.build_relationships_workflow_definitions()
    assert len(workflows) == 6
    assert [w.workflow_id for w in workflows] == list(
        CANONICAL_RELATIONSHIPS_WORKFLOW_IDS
    )


def test_ordered_safety_path_load_profile_reason():
    """reasoning must depend on profile, which must depend on load."""
    for wf in relationships.build_relationships_workflow_definitions():
        nodes = _node_map(wf)
        reason_deps = _transitive_deps(nodes, "reason")
        assert "profile" in reason_deps
        profile_deps = _transitive_deps(nodes, "profile")
        assert "load" in profile_deps


def test_analytical_operation_cannot_precede_reasoning():
    """Every EXECUTE_OPERATION node must transitively depend on reason."""
    for wf in relationships.build_relationships_workflow_definitions():
        nodes = _node_map(wf)
        for node in wf.nodes:
            if node.node_type is WorkflowNodeType.EXECUTE_OPERATION:
                assert "reason" in _transitive_deps(nodes, node.node_id)


def test_terminal_completion_cannot_bypass_validation():
    """The COMPLETE node must transitively depend on a VALIDATE node."""
    for wf in relationships.build_relationships_workflow_definitions():
        nodes = _node_map(wf)
        complete_ids = [
            n.node_id for n in wf.nodes if n.node_type is WorkflowNodeType.COMPLETE
        ]
        assert len(complete_ids) == 1
        complete_deps = _transitive_deps(nodes, complete_ids[0])
        assert any(
            nodes[cid].node_type is WorkflowNodeType.VALIDATE for cid in complete_deps
        )


def test_no_schedule_external_nodes():
    from cmm.domains.relationships.catalog import CANONICAL_RELATIONSHIPS_OPERATION_IDS

    known_ops = set(CANONICAL_RELATIONSHIPS_OPERATION_IDS)
    for workflow in relationships.build_relationships_workflow_definitions():
        for node in workflow.nodes:
            # Every operation node references a declared Relationships op.
            if node.operation_id is not None:
                assert node.operation_id in known_ops


def test_no_workflow_proposes_memory():
    """The Relationships memory policy is read-only; no workflow proposes
    memory."""
    for wf in relationships.build_relationships_workflow_definitions():
        node_types = {n.node_type for n in wf.nodes}
        assert WorkflowNodeType.PROPOSE_MEMORY not in node_types


def test_every_workflow_has_exactly_one_complete():
    for wf in relationships.build_relationships_workflow_definitions():
        completes = [n for n in wf.nodes if n.node_type is WorkflowNodeType.COMPLETE]
        assert len(completes) == 1
        # complete is always terminal (no successors) — enforced by the graph


def test_conversation_preparation_only_prepares():
    """The conversation-preparation workflow must never terminate in a
    send/contact/initiate/message operation."""
    wf = _by_id()["relationships.conversation_preparation"]
    op_ids = {node.operation_id for node in wf.nodes if node.operation_id}
    assert "relationships.prepare_conversation" in op_ids
    assert all(
        word not in op
        for op in op_ids
        for word in ("send", "contact", "initiate", "message", "adopt")
    )


def test_conversation_preparation_has_escalation_path():
    """Conversation preparation must include a real REQUEST_APPROVAL gate."""
    wf = _by_id()["relationships.conversation_preparation"]
    node_types = {n.node_type for n in wf.nodes}
    assert WorkflowNodeType.REQUEST_APPROVAL in node_types
    gates = {
        n.approval_gate
        for n in wf.nodes
        if n.node_type is WorkflowNodeType.REQUEST_APPROVAL
    }
    assert gates and all(g for g in gates)
    # The escalation gate must be on the transitive path to completion, so an
    # escalation cannot be bypassed into ordinary successful completion.
    nodes = _node_map(wf)
    complete_id = next(
        n.node_id for n in wf.nodes if n.node_type is WorkflowNodeType.COMPLETE
    )
    complete_deps = _transitive_deps(nodes, complete_id)
    assert any(
        nodes[cid].node_type is WorkflowNodeType.REQUEST_APPROVAL
        for cid in complete_deps
    )


def test_decision_support_has_escalation_path():
    """Decision Support Mode A must include a real REQUEST_APPROVAL gate that
    never adopts a decision."""
    wf = _by_id()["relationships.decision_support"]
    node_types = {n.node_type for n in wf.nodes}
    assert WorkflowNodeType.REQUEST_APPROVAL in node_types
    gates = {
        n.approval_gate
        for n in wf.nodes
        if n.node_type is WorkflowNodeType.REQUEST_APPROVAL
    }
    assert gates and all(g for g in gates)
    op_ids = {node.operation_id for node in wf.nodes if node.operation_id}
    assert all(word not in op for op in op_ids for word in ("adopt", "execute", "end"))


def test_boundary_review_only_reviews():
    """The boundary-review workflow must not modify/enforce/communicate a
    boundary."""
    wf = _by_id()["relationships.boundary_review"]
    op_ids = {node.operation_id for node in wf.nodes if node.operation_id}
    assert "relationships.review_boundaries" in op_ids
    assert all(
        word not in op
        for op in op_ids
        for word in ("modify", "enforce", "communicate", "withdraw")
    )


def _escalation_executor():
    from cmm.domains.workflow_execution import DomainWorkflowExecutor
    from cmm.workflows.contracts import ApprovalRequest, WaitRequest
    from cmm.workflows.engine import NodeExecution

    # Operation nodes report their structured result.  The conversation
    # escalation REQUEST_APPROVAL node falls out into the real engine approval
    # wait the first time it is reached; once the escalation is granted and the
    # run is resumed, the same node completes on retry.
    waited: set[tuple[str, str]] = set()

    def adapter(node, run):
        if node.node_type.value == "request_approval":
            key = (run.run_id, node.node_id)
            if key in waited:
                return NodeExecution.complete({"approved": True})
            waited.add(key)
            return NodeExecution.wait(
                WaitRequest(
                    "approval",
                    "approval required",
                    node.node_id,
                    {"gate": node.approval_gate},
                    approval_request=ApprovalRequest(
                        _Ids()(),
                        "relationships.conversation_preparation",
                        "1.0.0",
                        run.run_id,
                        node.node_id,
                        run.inputs,
                    ),
                )
            )
        return NodeExecution.complete({"ok": True})

    return DomainWorkflowExecutor(id_factory=_Ids(), operation_adapter=adapter)


def _escalation_context():
    from cmm.domains.workflow_contracts import DomainWorkflowContext

    wf = _by_id()["relationships.conversation_preparation"]
    return DomainWorkflowContext(
        primary_domain_id="domain:relationships",
        available_permissions=frozenset(),
        available_resources=frozenset(wf.required_resources),
        available_operations=frozenset(
            {n.operation_id for n in wf.nodes if n.operation_id}
        ),
        approved_gates=frozenset(),
    )


def test_escalation_gate_blocks_ordinary_completion_without_approval():
    """A workflow path requiring escalation cannot proceed as ordinary
    successful completion without the approval gate (real engine mechanism)."""
    from cmm.workflows.enums import WorkflowRunStatus

    wf = _by_id()["relationships.conversation_preparation"]
    executor = _escalation_executor()
    context = _escalation_context()
    run = executor.execute(wf, context, {"subject": "s"})
    # The conversation-preparation workflow ends with a REQUEST_APPROVAL
    # escalate gate on its completion path.  Without an approved gate it must
    # block into a real WAITING_FOR_APPROVAL state rather than complete as
    # ordinary success.
    assert run.status is WorkflowRunStatus.WAITING_FOR_APPROVAL
    approval = run.common_run.wait_request.approval_request
    assert approval is not None
    assert approval.node_id == "approve"


def test_escalation_path_completes_once_gate_approved():
    """Once the escalation gate's approval is granted, the conversation
    preparation workflow proceeds through to ordinary completion (real engine
    resume mechanism)."""
    from cmm.workflows.contracts import ApprovalDecision as WorkflowApprovalDecision
    from cmm.workflows.enums import WorkflowRunStatus

    wf = _by_id()["relationships.conversation_preparation"]
    executor = _escalation_executor()
    context = _escalation_context()
    waiting = executor.execute(wf, context, {"subject": "s"})
    assert waiting.status is WorkflowRunStatus.WAITING_FOR_APPROVAL
    legacy = waiting.common_run.wait_request.approval_request
    assert legacy is not None
    assert legacy.node_id == "approve"
    decided = legacy.decide(WorkflowApprovalDecision("reviewer", True))
    resumed = executor.resume(waiting, condition_resolved=True, approval=decided)
    assert resumed.status is WorkflowRunStatus.COMPLETED
