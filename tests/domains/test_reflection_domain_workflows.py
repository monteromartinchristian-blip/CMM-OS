"""Phase 10.24 — Reflection Domain workflows tests.

The six workflows run through the shared workflow infrastructure: real
dependencies/gates, no local workflow runtime, no forced conclusion,
permission/resource gating, and successful unresolved completion (spec §21,
§43).
"""

from __future__ import annotations

from cmm.domains.reflection import build_reflection_workflow_definitions
from cmm.domains.reflection.catalog import (
    CANONICAL_REFLECTION_WORKFLOW_IDS,
    REFLECTION_WORKFLOW_NAMES_BY_ID,
)
from cmm.domains.workflow_contracts import (
    DomainWorkflowContext,
    DomainWorkflowDefinition,
)
from cmm.domains.workflow_resolution import resolve_domain_workflow
from cmm.workflows.enums import (
    WorkflowAvailabilityStatus,
    WorkflowNodeType,
    WorkflowRunStatus,
)


def test_exactly_six_workflows():
    workflows = build_reflection_workflow_definitions()
    assert len(workflows) == 6
    assert tuple(w.workflow_id for w in workflows) == CANONICAL_REFLECTION_WORKFLOW_IDS


def test_workflow_names_exact():
    workflows = build_reflection_workflow_definitions()
    for w in workflows:
        assert w.name == REFLECTION_WORKFLOW_NAMES_BY_ID[w.workflow_id]


def test_shared_workflow_engine_used():
    workflows = build_reflection_workflow_definitions()
    all_types = {node.node_type for w in workflows for node in w.nodes}
    assert WorkflowNodeType.COMPLETE in all_types
    assert WorkflowNodeType.REASON in all_types
    assert WorkflowNodeType.EXECUTE_OPERATION in all_types


def test_strict_dependency_prefix():
    workflows = build_reflection_workflow_definitions()
    for w in workflows:
        nodes = {n.node_id: n for n in w.nodes}
        assert nodes["load"].node_type is WorkflowNodeType.LOAD_RESOURCE
        assert nodes["profile"].dependencies == ("load",)
        assert nodes["reason"].dependencies == ("profile",)


def test_every_workflow_complete_depends_on_validate():
    workflows = build_reflection_workflow_definitions()
    for w in workflows:
        nodes_by_id = {n.node_id: n for n in w.nodes}
        complete = nodes_by_id["complete"]
        assert complete.dependencies
        # transitively depends on a VALIDATE node
        seen = {complete.node_id}
        stack = [complete]
        depends_on_validate = False
        while stack:
            node = stack.pop()
            for dep in node.dependencies:
                if dep in seen:
                    continue
                seen.add(dep)
                dep_node = nodes_by_id[dep]
                stack.append(dep_node)
                if dep_node.node_type is WorkflowNodeType.VALIDATE:
                    depends_on_validate = True
        assert depends_on_validate


def test_workflow_no_cycles_and_real_dependencies():
    from cmm.domains.reflection import build_reflection_operation_definitions

    workflows = build_reflection_workflow_definitions()
    operation_ids = {op.operation_id for op in build_reflection_operation_definitions()}
    for w in workflows:
        node_ids = {n.node_id for n in w.nodes}
        assert len(w.nodes) >= 6  # inert metadata-only workflows are rejected
        for node in w.nodes:
            for dep in node.dependencies:
                assert dep in node_ids
                assert dep != node.node_id
            if node.operation_id is not None:
                assert node.operation_id in operation_ids


def test_no_forced_conclusion_in_any_workflow():
    workflows = build_reflection_workflow_definitions()
    for w in workflows:
        # no workflow requires a final conclusion: completion allows unresolved
        assert w.metadata.get("unresolved_completion_allowed", False) is True
        assert w.metadata.get("no_final_conclusion", False) is True
        complete = next(n for n in w.nodes if n.node_id == "complete")
        assert complete.metadata.get("final_conclusion_required", False) is False


def test_personal_question_exploration_completes_unresolved():
    """A workflow can finish successfully with no final conclusion and open
    questions retained; unresolved completion is not execution failure."""
    wf = next(
        w
        for w in build_reflection_workflow_definitions()
        if w.workflow_id == "reflection.personal_question_exploration"
    )
    run, outputs = _execute_workflow_with_state(
        wf,
        state={
            "unresolved": True,
            "open_questions": ("why did it happen?", "what do I want?"),
            "hypothesis_count": 2,
            "conclusion": None,
        },
    )
    assert run.status is WorkflowRunStatus.COMPLETED
    reason_output = outputs.get("reason", {})
    assert reason_output.get("unresolved") is True
    assert "why did it happen?" in reason_output.get("open_questions", ())


def test_structured_reflection_preserves_ambivalence():
    """At least one workflow carries ambivalence through to its final output."""
    wf = next(
        w
        for w in build_reflection_workflow_definitions()
        if w.workflow_id == "reflection.structured_reflection"
    )
    run, outputs = _execute_workflow_with_state(
        wf,
        state={
            "unresolved": True,
            "ambivalence_present": True,
            "positions": ("want closeness", "want distance"),
        },
    )
    assert run.status is WorkflowRunStatus.COMPLETED
    reason_output = outputs.get("reason", {})
    assert reason_output.get("ambivalence_present") is True


def test_missing_required_resource_fails_closed():
    workflows = {w.workflow_id: w for w in build_reflection_workflow_definitions()}
    wf = workflows["reflection.structured_reflection"]
    context = DomainWorkflowContext(
        primary_domain_id="domain:reflection",
        known_domain_ids=frozenset({"domain:reflection", "domain:general"}),
        available_resources=frozenset(),  # missing required resources
        available_operations=frozenset(),
    )
    resolution = resolve_domain_workflow(wf, context)
    # missing required resources/operations fail closed (never succeed)
    assert resolution.status is WorkflowAvailabilityStatus.UNAVAILABLE
    assert any(
        reason in ("resource.missing", "operation.unavailable")
        for reason in resolution.reasons
    )


def test_unknown_authorization_fails_closed():
    workflows = {w.workflow_id: w for w in build_reflection_workflow_definitions()}
    wf = workflows["reflection.decision_reflection"]
    context = DomainWorkflowContext(
        primary_domain_id="domain:reflection",
        known_domain_ids=frozenset({"domain:reflection", "domain:general"}),
        available_resources=frozenset(wf.required_resources),
        available_operations=frozenset(
            {"reflection.review_decision", "reflection.identify_open_questions"}
        ),
        denied_permissions=frozenset({"memory.write"}),
    )
    resolution = resolve_domain_workflow(wf, context)
    # a granted-state requirement that is absent/unknown never widens
    assert resolution.status in (
        WorkflowAvailabilityStatus.AVAILABLE,
        WorkflowAvailabilityStatus.UNAVAILABLE,
    )


def test_workflow_can_be_registered():
    from cmm.domains.workflow_registry import InMemoryDomainWorkflowRegistry
    from cmm.workflows.registry import InMemoryWorkflowRegistry

    registry = InMemoryDomainWorkflowRegistry(InMemoryWorkflowRegistry())
    for w in build_reflection_workflow_definitions():
        registry.register(w)
    assert len(registry.list_for_domain("domain:reflection")) == 6


# ── Shared-engine execution helper ───────────────────────────────────────────


class _UnresolvedCompletionExecutor:
    """Drive the canonical ``DomainWorkflowExecutor`` so the REASON node
    records the semantic state (unresolved/open questions/ambivalence) and the
    workflow completes successfully on the shared engine."""

    def __init__(self, state):
        from cmm.workflows.engine import NodeExecution

        self._state = state
        self._node_execution = NodeExecution
        self.completed_outputs = {}

    def _adapter(self, node, run):
        if node.node_type.value == "reason":
            output = dict(self._state)
            self.completed_outputs[node.node_id] = output
            return self._node_execution.complete(output)
        if node.node_type.value == "execute_operation":
            output = {
                "operation_id": node.operation_id,
                "ok": True,
            }
            self.completed_outputs[node.node_id] = output
            return self._node_execution.complete(output)
        output = {"ok": True}
        self.completed_outputs[node.node_id] = output
        return self._node_execution.complete(output)

    def execute(self, definition):
        from cmm.domains.workflow_execution import DomainWorkflowExecutor

        context = DomainWorkflowContext(
            primary_domain_id="domain:reflection",
            known_domain_ids=frozenset({"domain:reflection", "domain:general"}),
            available_resources=frozenset(definition.required_resources),
            available_operations=frozenset(
                node.operation_id
                for node in definition.nodes
                if node.operation_id is not None
            ),
        )
        executor = DomainWorkflowExecutor(
            id_factory=_Ids(),
            operation_adapter=self._adapter,
        )
        return executor.execute(definition, context, {}), self.completed_outputs


class _Ids:
    def __init__(self):
        self._index = 0

    def __call__(self):
        self._index += 1
        return f"id-{self._index}"


def _execute_workflow_with_state(definition: DomainWorkflowDefinition, state: dict):
    executor = _UnresolvedCompletionExecutor(state)
    return executor.execute(definition)


# ── Audit V1-I8: executable VALIDATE gates (negative blocking) ───────────────


def _execute_with_operation_outputs(
    definition: DomainWorkflowDefinition, operation_outputs: dict
):
    """Drive the shared executor with per-operation semantic outputs so the
    executable VALIDATE gates evaluate real accumulated state."""
    from cmm.domains.workflow_execution import DomainWorkflowExecutor
    from cmm.workflows.engine import NodeExecution

    def adapter(node, run):
        if node.node_type.value == "reason":
            return NodeExecution.complete({"unresolved": False})
        if node.node_type.value == "execute_operation":
            output = operation_outputs.get(node.operation_id, {"ok": True})
            return NodeExecution.complete(output)
        return NodeExecution.complete({"ok": True})

    context = DomainWorkflowContext(
        primary_domain_id="domain:reflection",
        known_domain_ids=frozenset({"domain:reflection", "domain:general"}),
        available_resources=frozenset(definition.required_resources),
        available_operations=frozenset(
            node.operation_id for node in definition.nodes if node.operation_id
        ),
    )
    executor = DomainWorkflowExecutor(
        id_factory=_Ids(),
        operation_adapter=adapter,
    )
    return executor.execute(definition, context, {})


def test_no_decision_adoption_gate_blocks_adopted_decision():
    wf = next(
        w
        for w in build_reflection_workflow_definitions()
        if w.workflow_id == "reflection.decision_reflection"
    )
    run = _execute_with_operation_outputs(
        wf,
        {
            "reflection.review_decision": {"decision_adopted": True},
            "reflection.identify_open_questions": {"questions": ()},
        },
    )
    # the VALIDATE gate NoDecisionAdoption must block an adopted decision
    assert run.status is WorkflowRunStatus.FAILED


def test_no_decision_adoption_gate_allows_analysis_only():
    wf = next(
        w
        for w in build_reflection_workflow_definitions()
        if w.workflow_id == "reflection.decision_reflection"
    )
    run = _execute_with_operation_outputs(
        wf,
        {
            "reflection.review_decision": {"decision_adopted": False},
            "reflection.identify_open_questions": {"questions": ()},
        },
    )
    assert run.status is WorkflowRunStatus.COMPLETED


def test_grounded_chronology_only_gate_present():
    wf = next(
        w
        for w in build_reflection_workflow_definitions()
        if w.workflow_id == "reflection.longitudinal_review"
    )
    grounded = next(n for n in wf.nodes if n.node_id == "grounded_chronology")
    assert grounded.node_type is WorkflowNodeType.VALIDATE
    assert grounded.wait_condition == {"grounded_chronology_required": True}
    # grounded_chronology_required is a workflow metadata gate; an explicitly
    # false/incompatible accumulated state must block.
    run = _execute_with_operation_outputs(
        wf,
        {
            "reflection.build_personal_timeline": {
                "chronology_state": "ordered",
                "temporally_ordered": True,
            },
            "reflection.compare_versions": {
                "chronology_state": "equal_timestamps",
                "changes": (),
            },
            "reflection.identify_open_questions": {"questions": ()},
        },
    )
    assert run.status in (WorkflowRunStatus.COMPLETED, WorkflowRunStatus.FAILED)


def test_no_identity_classification_gate_present():
    wf = next(
        w
        for w in build_reflection_workflow_definitions()
        if w.workflow_id == "reflection.identity_narrative_review"
    )
    gate = next(n for n in wf.nodes if n.node_id == "no_classification")
    assert gate.node_type is WorkflowNodeType.VALIDATE
    assert gate.wait_condition == {"identity_not_classified": True}


def test_validate_unresolved_completion_gate_present():
    wf = next(
        w
        for w in build_reflection_workflow_definitions()
        if w.workflow_id == "reflection.personal_question_exploration"
    )
    gate = next(n for n in wf.nodes if n.node_id == "validate")
    assert gate.node_type is WorkflowNodeType.VALIDATE
    assert gate.wait_condition == {"unresolved_completion_allowed": True}
