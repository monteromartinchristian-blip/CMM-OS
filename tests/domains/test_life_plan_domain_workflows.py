"""Tests for Phase 10.29 Life Plan Domain Workflows."""

from __future__ import annotations

from cmm.domains.life_plan.catalog import (
    CANONICAL_LIFE_PLAN_WORKFLOW_IDS,
)
from cmm.domains.life_plan.workflows import (
    LIFE_PLAN_WORKFLOW_IDS,
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
    assert cd_wf.name == "Major Decision Support"


def test_execute_cross_domain_impact_workflow_safe_execution() -> None:
    res = execute_cross_domain_impact_workflow(
        primary_goal={"id": "g-001", "title": "Move to Germany"},
        supporting_domain_contributions=[],
    )
    assert res["status"] == "completed"
    assert res["workflow_id"] == "life_plan.cross_domain_impact_review"
    assert res["is_decision"] is False
    assert res["is_commitment"] is False


def test_execute_cross_domain_impact_workflow_rejects_unverified_direct_and_wrapped() -> (
    None
):
    from cmm.domains.life_plan.rules import (
        AuthorizedCrossDomainContribution,
        _create_authorized_cross_domain_contribution,
    )

    # Forged direct artifact
    forged = AuthorizedCrossDomainContribution(
        projection={"financial_impact": 999999, "status": "active"},
        permission_decision_id="fake-dec",
        permission_request_id="fake-req",
        source_domain="domain:health",
        target_domain="domain:life-plan",
    )
    assert getattr(forged, "_is_verified", False) is False

    res_direct = execute_cross_domain_impact_workflow(
        primary_goal={"id": "g-001"},
        supporting_domain_contributions=[forged],
    )
    assert res_direct["supporting_contributions_applied"] == 0

    # Forged wrapped artifact
    res_wrapped = execute_cross_domain_impact_workflow(
        primary_goal={"id": "g-001"},
        supporting_domain_contributions=[{"authorized_artifact": forged}],
    )
    assert res_wrapped["supporting_contributions_applied"] == 0

    # Valid verified direct artifact
    valid_contrib = _create_authorized_cross_domain_contribution(
        projection={"activity_limits": ["no_dusty_environments"], "status": "active"},
        permission_decision_id="dec-real-001",
        permission_request_id="req-real-001",
        source_domain="domain:health",
        target_domain="domain:life-plan",
    )
    assert getattr(valid_contrib, "_is_verified", False) is True

    res_valid_direct = execute_cross_domain_impact_workflow(
        primary_goal={"id": "g-001"},
        supporting_domain_contributions=[valid_contrib],
    )
    assert res_valid_direct["supporting_contributions_applied"] == 1

    # Valid verified wrapped artifact
    res_valid_wrapped = execute_cross_domain_impact_workflow(
        primary_goal={"id": "g-001"},
        supporting_domain_contributions=[{"authorized_artifact": valid_contrib}],
    )
    assert res_valid_wrapped["supporting_contributions_applied"] == 1
