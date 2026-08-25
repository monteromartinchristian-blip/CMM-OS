"""Tests for Phase 10.29 Life Plan Domain Workflows."""

from __future__ import annotations

from cmm.domains.life_plan.catalog import (
    CANONICAL_LIFE_PLAN_WORKFLOW_IDS,
)
from cmm.domains.life_plan.workflows import (
    LIFE_PLAN_WORKFLOW_IDS,
    LIFE_PLAN_WORKFLOW_NAMES_BY_ID,
    build_life_plan_workflow_definitions,
    execute_cross_domain_impact_workflow,
)


def test_life_plan_workflow_definitions_exact_canonical_parity() -> None:
    wfs = build_life_plan_workflow_definitions()
    assert len(wfs) == 7
    assert tuple(w.workflow_id for w in wfs) == CANONICAL_LIFE_PLAN_WORKFLOW_IDS
    assert tuple(w.workflow_id for w in wfs) == LIFE_PLAN_WORKFLOW_IDS
    assert all(w.domain_id == "domain:life-plan" for w in wfs)


def test_life_plan_workflow_nodes_safety_order() -> None:
    for wf in build_life_plan_workflow_definitions():
        node_ids = [n.node_id for n in wf.nodes]
        assert node_ids[:3] == ["load", "profile", "reason"]
        assert node_ids[-2:] == ["validate", "complete"]
        # terminal complete depends on validate
        complete_node = wf.nodes[-1]
        assert "validate" in complete_node.dependencies


def test_cross_domain_impact_review_is_major_decision_support() -> None:
    wfs = {w.workflow_id: w for w in build_life_plan_workflow_definitions()}
    cd_wf = wfs["life_plan.cross_domain_impact_review"]
    assert "cross_domain_impact_review" in cd_wf.workflow_id
    assert "Major Decision Support" in cd_wf.metadata.get("purpose", "") or "cross-domain" in cd_wf.description.lower()


def test_execute_cross_domain_impact_workflow_safe_execution() -> None:
    res = execute_cross_domain_impact_workflow(
        primary_goal={"id": "g-001", "title": "Move to Germany"},
        supporting_domain_contributions=[],
    )
    assert res["status"] == "completed"
    assert res["workflow_id"] == "life_plan.cross_domain_impact_review"
    assert res["is_decision"] is False
    assert res["is_commitment"] is False
