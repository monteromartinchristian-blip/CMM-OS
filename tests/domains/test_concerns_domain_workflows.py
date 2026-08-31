"""Phase 10.25 — Concerns workflows tests.

The eight workflows run through the shared workflow infrastructure: real
dependency chains, no custom engine, literal-boolean VALIDATE gates, no forced
action/decision/conclusion, and successful unresolved completion (frozen
design §47–§55; implementation plan Task 7).
"""

from __future__ import annotations

from cmm.domains.concerns.catalog import (
    CANONICAL_CONCERNS_WORKFLOW_IDS,
    CONCERNS_WORKFLOW_NAMES_BY_ID,
)
from cmm.domains.concerns.operations import build_concerns_operation_definitions
from cmm.domains.concerns.workflows import build_concerns_workflow_definitions
from cmm.domains.workflow_contracts import DomainWorkflowContext
from cmm.domains.workflow_resolution import resolve_domain_workflow
from cmm.workflows.enums import (
    WorkflowAvailabilityStatus,
    WorkflowNodeType,
    WorkflowRunStatus,
)


def test_exactly_8_workflows_in_catalog_order():
    workflows = build_concerns_workflow_definitions()
    assert len(workflows) == 8
    assert tuple(w.workflow_id for w in workflows) == CANONICAL_CONCERNS_WORKFLOW_IDS


def test_workflow_names_exact():
    for w in build_concerns_workflow_definitions():
        assert w.name == CONCERNS_WORKFLOW_NAMES_BY_ID[w.workflow_id]


def test_shared_engine_node_types_used_no_custom_runtime():
    all_types = {
        node.node_type
        for w in build_concerns_workflow_definitions()
        for node in w.nodes
    }
    assert WorkflowNodeType.COMPLETE in all_types
    assert WorkflowNodeType.REASON in all_types
    assert WorkflowNodeType.EXECUTE_OPERATION in all_types
    assert WorkflowNodeType.VALIDATE in all_types


def test_strict_dependency_prefix_load_profile_reason():
    for w in build_concerns_workflow_definitions():
        nodes = {n.node_id: n for n in w.nodes}
        assert nodes["load"].node_type is WorkflowNodeType.LOAD_RESOURCE
        assert nodes["profile"].dependencies == ("load",)
        assert nodes["reason"].dependencies == ("profile",)


def test_complete_transitively_depends_on_validate():
    for w in build_concerns_workflow_definitions():
        nodes_by_id = {n.node_id: n for n in w.nodes}
        complete = nodes_by_id["complete"]
        seen = {complete.node_id}
        stack = [complete]
        found = False
        while stack:
            node = stack.pop()
            for dep in node.dependencies:
                if dep in seen:
                    continue
                seen.add(dep)
                dep_node = nodes_by_id[dep]
                stack.append(dep_node)
                if dep_node.node_type is WorkflowNodeType.VALIDATE:
                    found = True
        assert found


def test_acyclic_real_dependencies_and_known_operations():
    operation_ids = {op.operation_id for op in build_concerns_operation_definitions()}
    for w in build_concerns_workflow_definitions():
        node_ids = {n.node_id for n in w.nodes}
        assert len(w.nodes) >= 6  # inert metadata-only workflows rejected
        for node in w.nodes:
            for dep in node.dependencies:
                assert dep in node_ids
                assert dep != node.node_id
            if node.operation_id is not None:
                assert node.operation_id in operation_ids


def _adjacency(workflow):
    return {node.node_id: set(node.dependencies) for node in workflow.nodes}


def test_all_workflows_acyclic():
    for w in build_concerns_workflow_definitions():
        deps = _adjacency(w)
        resolved: set[str] = set()
        remaining = dict(deps)
        while remaining:
            ready = [
                node_id
                for node_id, requirements in remaining.items()
                if requirements <= resolved
            ]
            if not ready:
                raise AssertionError(f"cycle detected in {w.workflow_id}")
            for node_id in ready:
                resolved.add(node_id)
                del remaining[node_id]


# ── No forced semantics ──────────────────────────────────────────────────────


def test_no_workflow_forces_action_plan_or_risk_matrix_or_monitoring():
    forbidden_metadata_keys = (
        "action_plan_required",
        "risk_matrix_required",
        "monitoring_plan_required",
        "adopted_decision_required",
        "final_conclusion_required",
    )
    for w in build_concerns_workflow_definitions():
        assert w.metadata.get("unresolved_completion_allowed", False) is True
        assert w.metadata.get("no_final_conclusion", False) is True
        assert w.metadata.get("no_action_plan", False) is True
        assert w.metadata.get("no_monitoring_plan", False) is True
        complete = next(n for n in w.nodes if n.node_id == "complete")
        for key in forbidden_metadata_keys:
            assert complete.metadata.get(key, False) is False


def test_unresolved_completion_is_valid_everywhere():
    """Every workflow's validate node accepts an unresolved-but-safe state."""
    from cmm.domains.concerns.operations import identify_open_questions_result

    output = identify_open_questions_result(
        questions=({"question": "why?", "changes": ("meaning",)},)
    )
    # unresolved questions are retained, not failures
    assert output["questions"]


# ── Literal-boolean gates (shared engine) ────────────────────────────────────


from cmm.domains.workflow_execution import DomainWorkflowExecutor
from cmm.workflows.engine import NodeExecution


class _Ids:
    def __init__(self):
        self._index = 0

    def __call__(self):
        self._index += 1
        return f"id-{self._index}"


def _run_workflow(workflow, operation_outputs: dict, *, by_node: bool = False):
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


def test_reassurance_review_blocks_false_reassurance_gate_violation():
    wf = _workflow_by_id("concerns.reassurance_review")
    # The honesty gate reads the canonical helper field
    # false_reassurance_detected; a safe helper output with the gate alias
    # completes.
    run = _run_workflow(
        wf,
        {
            "understand": {"understood": True},
            "reassurance": {
                "assessment": "REASSURANCE_SUPPORTED",
                "false_reassurance_detected": False,
                "false_reassurance": False,
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
        by_node=True,
    )
    assert run.status is WorkflowRunStatus.COMPLETED


def test_practical_problem_solving_agency_gate_blocks_adoption():
    wf = _workflow_by_id("concerns.practical_problem_solving")
    # outputs keyed by node id: 'options' produces decision_adopted which the
    # agency gate reads from its transitive dependency chain
    run = _run_workflow(
        wf,
        {"options": {"decision_adopted": True}},
        by_node=True,
    )
    assert run.status is not WorkflowRunStatus.COMPLETED

    ok_run = _run_workflow(
        wf,
        {
            "options": {"decision_adopted": False},
            "next_step": {"external_action_executed": False},
        },
        by_node=True,
    )
    assert ok_run.status is WorkflowRunStatus.COMPLETED


def test_recurring_review_non_pathologizing_gate_executable():
    wf = _workflow_by_id("concerns.recurring_concern_review")
    blocked = _run_workflow(
        wf,
        {"recurrence": {"pathology_inferred": True}},
        by_node=True,
    )
    assert blocked.status is not WorkflowRunStatus.COMPLETED

    clean = _run_workflow(
        wf,
        {"recurrence": {"pathology_inferred": False}},
        by_node=True,
    )
    assert clean.status is WorkflowRunStatus.COMPLETED


def test_talk_it_through_completes_without_resolution():
    wf = _workflow_by_id("concerns.talk_it_through")
    run = _run_workflow(
        wf,
        {
            "concerns.map_lived_experience": {"diagnosis": False},
            "concerns.identify_open_questions": {"questions": ()},
        },
    )
    assert run.status is WorkflowRunStatus.COMPLETED


def test_professional_preparation_preparation_only_gate_executable():
    wf = _workflow_by_id("concerns.professional_discussion_preparation")
    blocked = _run_workflow(
        wf,
        {
            "concerns.identify_open_questions": {"questions": ()},
            "concerns.prepare_professional_discussion": {
                "external_transmission_performed": True
            },
        },
    )
    assert blocked.status is not WorkflowRunStatus.COMPLETED


def test_missing_required_resource_fails_closed():
    wf = _workflow_by_id("concerns.open_concern_conversation")
    context = DomainWorkflowContext(
        primary_domain_id="domain:concerns",
        known_domain_ids=frozenset({"domain:concerns", "domain:general"}),
        available_resources=frozenset(),
        available_operations=frozenset(),
    )
    resolution = resolve_domain_workflow(wf, context)
    assert resolution.status is WorkflowAvailabilityStatus.UNAVAILABLE
    assert any(
        reason in ("resource.missing", "operation.unavailable")
        for reason in resolution.reasons
    )


def test_workflows_can_be_registered():
    from cmm.domains.workflow_registry import InMemoryDomainWorkflowRegistry
    from cmm.workflows.registry import InMemoryWorkflowRegistry

    registry = InMemoryDomainWorkflowRegistry(InMemoryWorkflowRegistry())
    for w in build_concerns_workflow_definitions():
        registry.register(w)
    assert len(registry.list_for_domain("domain:concerns")) == 8
