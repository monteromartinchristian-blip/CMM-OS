"""Phase 10.25 — Audit-remediation regression tests for workflow gate integrity.

Remediates B-003: every VALIDATE gate's condition field must be produced by a
real direct dependency's output schema (never satisfied by inert static
metadata), and missing runtime safety evidence must fail closed
(``validate.condition_unknown`` / non-completion).  Statically reconciles all
eight Concerns workflows against their operation output schemas.
"""

from __future__ import annotations

from cmm.domains.concerns.operations import (
    build_concerns_operation_definitions,
)
from cmm.domains.concerns.workflows import build_concerns_workflow_definitions
from cmm.domains.workflow_contracts import DomainWorkflowContext
from cmm.domains.workflow_execution import DomainWorkflowExecutor
from cmm.workflows.engine import NodeExecution
from cmm.workflows.enums import WorkflowNodeType, WorkflowRunStatus


class _Ids:
    def __init__(self):
        self._index = 0

    def __call__(self):
        self._index += 1
        return f"id-{self._index}"


def _run_workflow(workflow, operation_outputs: dict, *, by_node: bool = True):
    def adapter(node, run):
        if node.node_type.value == "execute_operation":
            key_source = node.node_id if by_node else node.operation_id
            return NodeExecution.complete(
                operation_outputs.get(key_source, {"ok": True})
            )
        return NodeExecution.complete({"ok": True})

    context = DomainWorkflowContext(
        primary_domain_id="domain:concerns",
        known_domain_ids=frozenset({"domain:concerns", "domain:general"}),
        available_resources=frozenset(workflow.required_resources),
        available_operations=frozenset(
            node.operation_id for node in workflow.nodes if node.operation_id
        ),
    )
    executor = DomainWorkflowExecutor(id_factory=_Ids(), operation_adapter=adapter)
    return executor.execute(workflow, context, {})


def _workflow_by_id(workflow_id):
    return next(
        w for w in build_concerns_workflow_definitions() if w.workflow_id == workflow_id
    )


# ── R2a: actual false reassurance blocked by the workflow gate ──────────────


def test_reassurance_workflow_blocks_actual_false_reassurance_helper_output():
    """The gate waits on the field the canonical helper actually emits
    (``false_reassurance_detected``).  A real helper output with
    false_reassurance_detected=True must block the gate."""
    wf = _workflow_by_id("concerns.reassurance_review")
    blocked = _run_workflow(
        wf,
        {
            "understand": {"understood": True, "ok": True},
            "reassurance": {
                "assessment": "REASSURANCE_SUPPORTED",
                "false_reassurance_detected": True,
                "corrected_assessment": "CONCERN_SUPPORTED",
                "remaining_uncertainty": (),
                "absolute_certainty": False,
            },
            "escalation": {
                "catastrophic_escalation_present": False,
                "statements": (),
                "promotions_blocked_total": 0,
            },
            "questions": {"questions": (), "ritual_questions_suppressed": 0},
        },
    )
    assert blocked.status is not WorkflowRunStatus.COMPLETED


def test_reassurance_workflow_fails_closed_when_false_reassurance_field_missing():
    """If the reassurance node's output does not contain the safety field, the
    gate must fail closed (missing runtime evidence is never satisfied by a
    static metadata default)."""
    wf = _workflow_by_id("concerns.reassurance_review")
    run = _run_workflow(
        wf,
        {
            "understand": {"understood": True, "ok": True},
            "reassurance": {"assessment": "REASSURANCE_SUPPORTED"},
            "escalation": {
                "catastrophic_escalation_present": False,
                "statements": (),
                "promotions_blocked_total": 0,
            },
            "questions": {"questions": (), "ritual_questions_suppressed": 0},
        },
    )
    # Without the safety field and without a metadata default, the gate cannot
    # pass: fail-closed means no safe completion.
    assert run.status is not WorkflowRunStatus.COMPLETED


# ── R2b: catastrophic escalation gate from a real producer ──────────────────


def test_reassurance_workflow_blocks_catastrophic_escalation_from_actual_producer():
    """The proportionality gate must read catastrophic_escalation_present from
    a direct dependency output (the escalation producer)."""
    wf = _workflow_by_id("concerns.reassurance_review")
    blocked = _run_workflow(
        wf,
        {
            "understand": {"understood": True, "ok": True},
            "reassurance": {
                "assessment": "REASSURANCE_SUPPORTED",
                "false_reassurance_detected": False,
                "corrected_assessment": "REASSURANCE_SUPPORTED",
                "remaining_uncertainty": (),
                "absolute_certainty": False,
            },
            "escalation": {"catastrophic_escalation_present": True},
            "questions": {"questions": (), "ritual_questions_suppressed": 0},
        },
    )
    assert blocked.status is not WorkflowRunStatus.COMPLETED


# ── R2c: material question gate fails closed on missing evidence ────────────


def test_open_concern_workflow_fails_closed_when_question_materiality_evidence_missing():
    """The material-question gate depends on the open-questions node which must
    produce the ritual-question suppression field; a missing field fails
    closed."""
    wf = _workflow_by_id("concerns.open_concern_conversation")
    run = _run_workflow(
        wf,
        {
            "understand": {"understood": True, "ok": True},
            "support_need": {"support_need": "PERSPECTIVE", "ok": True},
            "lived_experience": {"diagnosis": False, "ok": True},
            "gaps": {},  # missing ritual_questions_suppressed
        },
    )
    assert run.status is not WorkflowRunStatus.COMPLETED


# ── R2d: external action from next_step output blocked ──────────────────────


def test_practical_problem_solving_blocks_external_action_from_next_step_output():
    """The no-execution gate must depend on the next_step producer and block
    when its output says an external action was performed."""
    wf = _workflow_by_id("concerns.practical_problem_solving")
    blocked = _run_workflow(
        wf,
        {
            "understand": {"understood": True, "ok": True},
            "options": {"decision_adopted": False, "options": (), "ok": True},
            "next_step": {
                "external_action_executed": True,
                "next_step": None,
                "no_next_step_required": True,
            },
        },
    )
    assert blocked.status is not WorkflowRunStatus.COMPLETED


# ── R2e: static reconciliation of every validate condition ──────────────────


def test_every_validate_condition_has_a_direct_dependency_schema_property():
    """Statically reconcile ALL eight workflows: for every VALIDATE
    wait_condition field, at least one DIRECT dependency must produce that
    exact field in its output schema (or metadata/inputs policy field)."""
    operations = {op.operation_id: op for op in build_concerns_operation_definitions()}
    for wf in build_concerns_workflow_definitions():
        nodes_by_id = {n.node_id: n for n in wf.nodes}
        for node in wf.nodes:
            if node.node_type is not WorkflowNodeType.VALIDATE or not node.wait_condition:
                continue
            for field in node.wait_condition:
                # Immutable workflow policy fields (documented) may come from
                # workflow metadata directly; runtime-derived safety fields
                # must be produced by a declared dependency's output schema.
                produced_by_dependency = any(
                    _dependency_emits_field(nodes_by_id[dep], field, operations)
                    for dep in (node.dependencies or ())
                )
                assert produced_by_dependency or field in (
                    _workflow_immutable_metadata_fields(wf)
                ), (
                    f"{wf.workflow_id}:{node.node_id} waits on {field!r} but no "
                    "direct dependency output schema declares it and it is not "
                    "immutable workflow policy"
                )


def _dependency_emits_field(dep_node, field: str, operations) -> bool:
    """A dependency node emits ``field`` if it is an EXECUTE_OPERATION whose
    operation output schema declares it, or it is a metadata/input producer."""
    if dep_node.operation_id and dep_node.operation_id in operations:
        schema = operations[dep_node.operation_id].output_schema
        return field in schema.get("properties", {})
    if dep_node.node_type.value in ("load_resource", "apply_profile", "reason"):
        # load/profile/reason nodes produce validated workflow state; their
        # declared fields live in workflow metadata/outputs.
        return field in (dep_node.metadata or {})
    return False


def _workflow_immutable_metadata_fields(wf) -> tuple[str, ...]:
    """Immutable policy fields are the workflow-level policy constants that
    never come from runtime evidence (e.g. unresolved_completion_allowed)."""
    immutable = {
        "unresolved_completion_allowed",
        "unresolved_completion_valid",
        "no_final_conclusion",
        "no_action_plan",
        "no_monitoring_plan",
        "adopted_decision_required",
        "final_conclusion_required",
        "action_plan_required",
        "risk_matrix_required",
        "monitoring_plan_required",
    }
    return tuple(key for key in wf.metadata if key in immutable)


# ── Conflict tests: metadata says safe, direct dependency says violation ────


def test_metadata_safe_default_never_masks_runtime_violation_false_reassurance():
    """Even if workflow metadata pre-populates a safe value, a direct
    dependency output carrying the violation must win."""
    wf = _workflow_by_id("concerns.reassurance_review")
    run = _run_workflow(
        wf,
        {
            "understand": {"understood": True, "ok": True},
            "reassurance": {
                "assessment": "REASSURANCE_SUPPORTED",
                "false_reassurance_detected": True,
                "corrected_assessment": "CONCERN_SUPPORTED",
                "remaining_uncertainty": (),
                "absolute_certainty": False,
            },
            "escalation": {
                "catastrophic_escalation_present": False,
                "statements": (),
                "promotions_blocked_total": 0,
            },
            "questions": {"questions": (), "ritual_questions_suppressed": 0},
        },
    )
    assert run.status is not WorkflowRunStatus.COMPLETED


def test_metadata_safe_default_never_masks_runtime_violation_external_action():
    wf = _workflow_by_id("concerns.practical_problem_solving")
    run = _run_workflow(
        wf,
        {
            "understand": {"understood": True, "ok": True},
            "options": {"decision_adopted": False, "options": (), "ok": True},
            "next_step": {
                "external_action_executed": True,
                "next_step": None,
                "no_next_step_required": True,
            },
        },
    )
    assert run.status is not WorkflowRunStatus.COMPLETED


# ── Happy-path sanity: correct outputs complete ─────────────────────────────


def test_reassurance_review_completes_with_clean_producer_fields():
    wf = _workflow_by_id("concerns.reassurance_review")
    run = _run_workflow(
        wf,
        {
            "understand": {"understood": True, "ok": True},
            "reassurance": {
                "assessment": "REASSURANCE_SUPPORTED",
                "false_reassurance_detected": False,
                "corrected_assessment": "REASSURANCE_SUPPORTED",
                "remaining_uncertainty": (),
                "absolute_certainty": False,
            },
            "escalation": {
                "catastrophic_escalation_present": False,
                "statements": (),
                "promotions_blocked_total": 0,
            },
            "questions": {"questions": (), "ritual_questions_suppressed": 0},
        },
    )
    assert run.status is WorkflowRunStatus.COMPLETED


def test_open_concern_completes_with_ritual_suppression_zero():
    wf = _workflow_by_id("concerns.open_concern_conversation")
    run = _run_workflow(
        wf,
        {
            "understand": {"understood": True, "ok": True},
            "support_need": {"support_need": "PERSPECTIVE", "ok": True},
            "lived_experience": {"diagnosis": False, "ok": True},
            "gaps": {"questions": (), "ritual_questions_suppressed": 0},
        },
    )
    assert run.status is WorkflowRunStatus.COMPLETED


def test_practical_problem_solving_completes_with_clean_next_step():
    wf = _workflow_by_id("concerns.practical_problem_solving")
    run = _run_workflow(
        wf,
        {
            "understand": {"understood": True, "ok": True},
            "options": {"decision_adopted": False, "options": (), "ok": True},
            "next_step": {
                "external_action_executed": False,
                "next_step": None,
                "no_next_step_required": True,
            },
            "questions": {"questions": (), "ritual_questions_suppressed": 0},
        },
    )
    assert run.status is WorkflowRunStatus.COMPLETED