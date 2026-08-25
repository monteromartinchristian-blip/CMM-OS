"""Tests for Phase 10.27 Parenthood Domain Workflows."""

from __future__ import annotations

from cmm.domains.parenthood.catalog import (
    CANONICAL_PARENTHOOD_CHILD_WORKFLOW_IDS,
    CANONICAL_PARENTHOOD_JOURNEY_WORKFLOW_IDS,
    CANONICAL_PARENTHOOD_WORKFLOW_IDS,
    PARENTHOOD_WORKFLOW_NAMES_BY_ID,
)
from cmm.domains.parenthood.workflows import build_parenthood_workflow_definitions
from cmm.workflows.enums import WorkflowNodeType


def test_parenthood_workflow_definitions_count_and_ids() -> None:
    """Verify all 16 workflows build deterministically in canonical order."""
    workflows = build_parenthood_workflow_definitions()
    assert len(workflows) == 16
    wf_ids = tuple(wf.workflow_id for wf in workflows)
    assert wf_ids == CANONICAL_PARENTHOOD_WORKFLOW_IDS

    journey_ids = [wf.workflow_id for wf in workflows if "journey" in wf.workflow_id or wf.workflow_id in CANONICAL_PARENTHOOD_JOURNEY_WORKFLOW_IDS]
    child_ids = [wf.workflow_id for wf in workflows if "child" in wf.workflow_id or wf.workflow_id in CANONICAL_PARENTHOOD_CHILD_WORKFLOW_IDS]
    assert tuple(journey_ids) == CANONICAL_PARENTHOOD_JOURNEY_WORKFLOW_IDS
    assert tuple(child_ids) == CANONICAL_PARENTHOOD_CHILD_WORKFLOW_IDS


def test_parenthood_workflow_names_and_metadata() -> None:
    """Verify workflow display names and non-autonomous safety properties."""
    workflows = build_parenthood_workflow_definitions()
    for wf in workflows:
        assert str(wf.domain_id) == "domain:parenthood"
        assert wf.name == PARENTHOOD_WORKFLOW_NAMES_BY_ID[wf.workflow_id]
        assert wf.metadata.get("non_autonomous") is True
        assert wf.metadata.get("phase") == "10.27"


def test_parenthood_workflow_safety_ordering() -> None:
    """Verify strict safety prefix ordering: load -> profile -> reason -> ... -> validate -> complete."""
    workflows = build_parenthood_workflow_definitions()
    for wf in workflows:
        node_types = [n.node_type for n in wf.nodes]
        assert node_types[0] is WorkflowNodeType.LOAD_RESOURCE
        assert node_types[1] is WorkflowNodeType.APPLY_PROFILE
        assert node_types[2] is WorkflowNodeType.REASON
        assert node_types[-1] is WorkflowNodeType.COMPLETE
        assert node_types[-2] is WorkflowNodeType.VALIDATE
