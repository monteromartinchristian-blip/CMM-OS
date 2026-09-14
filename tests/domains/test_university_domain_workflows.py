"""Tests for Phase 10.22 University Domain workflows.

Covers the strictly ordered safety path (load -> profile -> reason), the real
REQUEST_APPROVAL planning gates, the read-only memory policy (no workflow
proposes memory), and the terminal-op safety boundaries for the planning and
preparation workflows (nothing enrols, registers, submits, or sends).
"""

from __future__ import annotations

from cmm.domains import university
from cmm.domains.university.catalog import (
    CANONICAL_UNIVERSITY_OPERATION_IDS,
    CANONICAL_UNIVERSITY_WORKFLOW_IDS,
)
from cmm.workflows.enums import WorkflowNodeType


def _by_id():
    return {
        w.workflow_id: w for w in university.build_university_workflow_definitions()
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


def test_seven_workflows_and_canonical_order():
    workflows = university.build_university_workflow_definitions()
    assert len(workflows) == 7
    assert [w.workflow_id for w in workflows] == list(CANONICAL_UNIVERSITY_WORKFLOW_IDS)


def test_ordered_safety_path_load_profile_reason():
    """reasoning must depend on profile, which must depend on load."""
    for wf in university.build_university_workflow_definitions():
        nodes = _node_map(wf)
        reason_deps = _transitive_deps(nodes, "reason")
        assert "profile" in reason_deps
        profile_deps = _transitive_deps(nodes, "profile")
        assert "load" in profile_deps


def test_analytical_operation_cannot_precede_reasoning():
    """Every EXECUTE_OPERATION node must transitively depend on reason."""
    for wf in university.build_university_workflow_definitions():
        nodes = _node_map(wf)
        for node in wf.nodes:
            if node.node_type is WorkflowNodeType.EXECUTE_OPERATION:
                assert "reason" in _transitive_deps(nodes, node.node_id)


def test_terminal_completion_cannot_bypass_validation():
    """The COMPLETE node must transitively depend on a VALIDATE node."""
    for wf in university.build_university_workflow_definitions():
        nodes = _node_map(wf)
        complete_ids = [
            n.node_id for n in wf.nodes if n.node_type is WorkflowNodeType.COMPLETE
        ]
        assert len(complete_ids) == 1
        complete_deps = _transitive_deps(nodes, complete_ids[0])
        assert any(
            nodes[cid].node_type is WorkflowNodeType.VALIDATE for cid in complete_deps
        )


def test_every_operation_node_references_declared_op():
    known_ops = set(CANONICAL_UNIVERSITY_OPERATION_IDS)
    for workflow in university.build_university_workflow_definitions():
        for node in workflow.nodes:
            if node.operation_id is not None:
                assert node.operation_id in known_ops


def test_no_workflow_proposes_memory():
    """The University memory policy is read-only; no workflow proposes memory."""
    for wf in university.build_university_workflow_definitions():
        node_types = {n.node_type for n in wf.nodes}
        assert WorkflowNodeType.PROPOSE_MEMORY not in node_types


def test_every_workflow_has_exactly_one_complete():
    for wf in university.build_university_workflow_definitions():
        completes = [n for n in wf.nodes if n.node_type is WorkflowNodeType.COMPLETE]
        assert len(completes) == 1


def test_no_workflow_enrols_registers_submits_or_sends():
    """No University workflow operation encodes an autonomous send/submit/enrol/
    register/record-write action."""
    forbidden = ("send", "submit", "enrol", "register", "write_record")
    for wf in university.build_university_workflow_definitions():
        op_ids = {node.operation_id for node in wf.nodes if node.operation_id}
        assert all(find not in op for op in op_ids for find in forbidden)


def test_semester_planning_prepares_proposal_with_approval_gate():
    """Semester planning is a proposal: it carries a real REQUEST_APPROVAL gate
    and never enrols or registers."""
    wf = _by_id()["university.semester_planning"]
    node_types = {n.node_type for n in wf.nodes}
    assert WorkflowNodeType.REQUEST_APPROVAL in node_types
    gates = {
        n.approval_gate
        for n in wf.nodes
        if n.node_type is WorkflowNodeType.REQUEST_APPROVAL
    }
    assert gates and all(g for g in gates)
    op_ids = {node.operation_id for node in wf.nodes if node.operation_id}
    assert "university.plan_semester" in op_ids
    assert all(
        word not in op for op in op_ids for word in ("enrol", "register", "submit")
    )
    # The gate is on the transitive path to completion.
    nodes = _node_map(wf)
    complete_id = next(
        n.node_id for n in wf.nodes if n.node_type is WorkflowNodeType.COMPLETE
    )
    complete_deps = _transitive_deps(nodes, complete_id)
    assert any(
        nodes[cid].node_type is WorkflowNodeType.REQUEST_APPROVAL
        for cid in complete_deps
    )


def test_exam_preparation_only_prepares():
    """Exam preparation must never terminate in a send/submit action."""
    wf = _by_id()["university.exam_preparation"]
    op_ids = {node.operation_id for node in wf.nodes if node.operation_id}
    assert "university.prepare_exam" in op_ids
    assert all(
        word not in op
        for op in op_ids
        for word in ("send", "submit", "contact", "message")
    )


def test_assignment_preparation_only_prepares():
    wf = _by_id()["university.assignment_preparation"]
    op_ids = {node.operation_id for node in wf.nodes if node.operation_id}
    assert "university.prepare_assignment" in op_ids
    assert all(word not in op for op in op_ids for word in ("send", "submit"))


def test_academic_review_only_reviews():
    """Academic review must not modify any official state."""
    wf = _by_id()["university.academic_review"]
    op_ids = {node.operation_id for node in wf.nodes if node.operation_id}
    assert "university.review_academic_record" in op_ids
    assert all(
        word not in op for op in op_ids for word in ("modify", "write", "update_record")
    )


def test_degree_completion_review_takes_no_official_action():
    wf = _by_id()["university.degree_completion_review"]
    op_ids = {node.operation_id for node in wf.nodes if node.operation_id}
    assert "university.review_degree_completion" in op_ids
    assert all(
        word not in op
        for op in op_ids
        for word in ("graduate", "award", "submit", "register")
    )


def test_tfg_planning_has_approval_gate():
    """TFG planning is a formal-procedure preparation: approval-gated, never
    submits."""
    wf = _by_id()["university.tfg_planning"]
    node_types = {n.node_type for n in wf.nodes}
    assert WorkflowNodeType.REQUEST_APPROVAL in node_types
    gates = {
        n.approval_gate
        for n in wf.nodes
        if n.node_type is WorkflowNodeType.REQUEST_APPROVAL
    }
    assert gates and all(g for g in gates)
    op_ids = {node.operation_id for node in wf.nodes if node.operation_id}
    assert "university.create_study_plan" in op_ids
    assert all(
        word not in op for op in op_ids for word in ("submit", "register", "file")
    )


def test_reassessment_internal_academic_state_only():
    """Reassessment planning is a proposal and must not mutate academic state:
    ``update_subject_status`` (a MEMORY write) is absent from the workflow."""
    wf = _by_id()["university.reassessment_planning"]
    op_ids = {node.operation_id for node in wf.nodes if node.operation_id}
    assert "university.update_subject_status" not in op_ids
    assert all(
        word not in op for op in op_ids for word in ("official", "register", "submit")
    )


def _executor():
    from cmm.domains.workflow_execution import DomainWorkflowExecutor
    from cmm.workflows.contracts import ApprovalRequest, WaitRequest
    from cmm.workflows.engine import NodeExecution

    # REQUEST_APPROVAL nodes fall out into the real engine approval wait on the
    # first encounter; once the gate is granted and the run is resumed, the same
    # node completes on retry.
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
                        run.workflow_id,
                        "1.0.0",
                        run.run_id,
                        node.node_id,
                        run.inputs,
                    ),
                )
            )
        return NodeExecution.complete({"ok": True})

    return DomainWorkflowExecutor(id_factory=_Ids(), operation_adapter=adapter)


def _context(wf):
    from cmm.domains.workflow_contracts import DomainWorkflowContext

    return DomainWorkflowContext(
        primary_domain_id="domain:university",
        available_permissions=frozenset(),
        available_resources=frozenset(wf.required_resources),
        available_operations=frozenset(
            {n.operation_id for n in wf.nodes if n.operation_id}
        ),
        approved_gates=frozenset(),
    )


def test_planning_workflow_blocks_without_approval():
    """A planning workflow without an approved gate blocks into
    WAITING_FOR_APPROVAL rather than completing as ordinary success."""
    from cmm.workflows.enums import WorkflowRunStatus

    wf = _by_id()["university.semester_planning"]
    run = _executor().execute(wf, _context(wf), {"subject": "s"})
    assert run.status is WorkflowRunStatus.WAITING_FOR_APPROVAL
    approval = run.common_run.wait_request.approval_request
    assert approval is not None
    assert approval.node_id == "approve"


def test_planning_workflow_completes_once_gate_approved():
    """Once the planning gate's approval is granted, the workflow proceeds to
    ordinary completion."""
    from cmm.workflows.contracts import ApprovalDecision as WorkflowApprovalDecision
    from cmm.workflows.enums import WorkflowRunStatus

    wf = _by_id()["university.semester_planning"]
    executor = _executor()
    waiting = executor.execute(wf, _context(wf), {"subject": "s"})
    assert waiting.status is WorkflowRunStatus.WAITING_FOR_APPROVAL
    legacy = waiting.common_run.wait_request.approval_request
    assert legacy is not None
    decided = legacy.decide(WorkflowApprovalDecision("reviewer", True))
    resumed = executor.resume(waiting, condition_resolved=True, approval=decided)
    assert resumed.status is WorkflowRunStatus.COMPLETED


def test_non_planning_workflow_completes_without_approval():
    """A review/preparation workflow has no approval gate and completes
    ordinarily."""
    from cmm.workflows.enums import WorkflowRunStatus

    wf = _by_id()["university.exam_preparation"]
    run = _executor().execute(wf, _context(wf), {"subject": "s"})
    assert run.status is WorkflowRunStatus.COMPLETED
