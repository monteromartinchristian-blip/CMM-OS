"""Tests for General Domain workflows."""

from __future__ import annotations

from cmm.domains.general import (
    GENERAL_WORKFLOW_IDS,
    build_general_workflow_definitions,
)
from cmm.domains.workflow_contracts import DomainWorkflowDefinition
from cmm.workflows.enums import WorkflowNodeType


def test_all_workflows_built():
    workflows = build_general_workflow_definitions()
    assert len(workflows) == 4


def test_workflow_ids_match():
    workflows = build_general_workflow_definitions()
    ids = tuple(w.workflow_id for w in workflows)
    assert ids == GENERAL_WORKFLOW_IDS


def test_workflow_domain_ids():
    workflows = build_general_workflow_definitions()
    for w in workflows:
        assert w.domain_id == "domain:general"


def test_workflow_versions():
    workflows = build_general_workflow_definitions()
    for w in workflows:
        assert w.version == "1.0.0"


def test_workflow_unique_ids():
    workflows = build_general_workflow_definitions()
    ids = [w.workflow_id for w in workflows]
    assert len(set(ids)) == len(ids)


def test_workflow_has_nodes():
    workflows = build_general_workflow_definitions()
    for w in workflows:
        assert len(w.nodes) >= 5


def test_workflow_node_types_supported():
    workflows = build_general_workflow_definitions()
    supported = {node_type.value for node_type in WorkflowNodeType}
    for w in workflows:
        for node in w.nodes:
            assert node.node_type.value in supported


def test_workflow_no_cycles():
    workflows = build_general_workflow_definitions()
    for w in workflows:
        node_ids = {n.node_id for n in w.nodes}
        for node in w.nodes:
            for dep in node.dependencies:
                assert dep in node_ids
                assert dep != node.node_id


def test_workflow_deterministic_order():
    a = build_general_workflow_definitions()
    b = build_general_workflow_definitions()
    assert [w.workflow_id for w in a] == [w.workflow_id for w in b]


def test_workflow_serialization_round_trip():
    workflows = build_general_workflow_definitions()
    for w in workflows:
        restored = DomainWorkflowDefinition.from_dict(w.to_dict())
        assert restored.workflow_id == w.workflow_id
        assert len(restored.nodes) == len(w.nodes)


def test_workflow_can_be_registered():
    from cmm.domains.workflow_registry import InMemoryDomainWorkflowRegistry
    from cmm.workflows.registry import InMemoryWorkflowRegistry

    common = InMemoryWorkflowRegistry()
    registry = InMemoryDomainWorkflowRegistry(common)
    for w in build_general_workflow_definitions():
        registry.register(w)
    assert len(registry.list_for_domain("domain:general")) == 4


def test_information_review_has_complete_flow():
    workflows = build_general_workflow_definitions()
    review = next(w for w in workflows if w.workflow_id == "general.information_review")
    node_types = {n.node_id: n.node_type for n in review.nodes}
    assert node_types["load"] is WorkflowNodeType.LOAD_RESOURCE
    assert node_types["search"] is WorkflowNodeType.SEARCH_KNOWLEDGE
    assert node_types["profile"] is WorkflowNodeType.APPLY_PROFILE
    assert node_types["reason"] is WorkflowNodeType.REASON
    assert node_types["gaps"] is WorkflowNodeType.DETECT_GAPS
    assert node_types["summary"] is WorkflowNodeType.EXECUTE_OPERATION
    assert node_types["questions"] is WorkflowNodeType.EXECUTE_OPERATION
    assert node_types["validate"] is WorkflowNodeType.VALIDATE
    assert node_types["memory"] is WorkflowNodeType.PROPOSE_MEMORY
    assert node_types["complete"] is WorkflowNodeType.COMPLETE


def test_goal_clarification_has_pause():
    workflows = build_general_workflow_definitions()
    clarification = next(
        w for w in workflows if w.workflow_id == "general.goal_clarification"
    )
    node_types = {n.node_id: n.node_type for n in clarification.nodes}
    assert node_types["ask"] is WorkflowNodeType.ASK_QUESTION
    assert node_types["pause"] is WorkflowNodeType.PAUSE


def test_decision_support_has_compare():
    workflows = build_general_workflow_definitions()
    support = next(w for w in workflows if w.workflow_id == "general.decision_support")
    node_types = {n.node_id: n.node_type for n in support.nodes}
    assert node_types["compare"] is WorkflowNodeType.EXECUTE_OPERATION
    assert node_types["report"] is WorkflowNodeType.EXECUTE_OPERATION


def test_periodic_review_has_timeline():
    workflows = build_general_workflow_definitions()
    review = next(w for w in workflows if w.workflow_id == "general.periodic_review")
    node_types = {n.node_id: n.node_type for n in review.nodes}
    assert node_types["timeline"] is WorkflowNodeType.EXECUTE_OPERATION
    assert node_types["memory"] is WorkflowNodeType.PROPOSE_MEMORY


def test_workflow_completion_criteria():
    workflows = build_general_workflow_definitions()
    for w in workflows:
        assert w.completion_criteria.get("all_required_nodes_completed") is True


def test_workflow_no_side_effects():
    workflows = build_general_workflow_definitions()
    for w in workflows:
        assert w.metadata.get("phase") == "10.19"