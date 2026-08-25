"""Tests for Phase 10.27 Parenthood Domain Operations."""

from __future__ import annotations

from cmm.agent_runtime.enums import PolicyRiskLevel
from cmm.domains.parenthood.catalog import (
    CANONICAL_PARENTHOOD_CHILD_OPERATION_IDS,
    CANONICAL_PARENTHOOD_JOURNEY_OPERATION_IDS,
    CANONICAL_PARENTHOOD_OPERATION_IDS,
)
from cmm.domains.parenthood.operations import (
    build_parenthood_operation_definitions,
    build_timeline_result,
    compare_pathways_result,
    prepare_parental_decision_result,
    review_developmental_stage_result,
)


def test_parenthood_operation_definitions_count_and_ids() -> None:
    """Verify all 20 operations build deterministically in canonical order."""
    ops = build_parenthood_operation_definitions()
    assert len(ops) == 20
    op_ids = tuple(op.operation_id for op in ops)
    assert op_ids == CANONICAL_PARENTHOOD_OPERATION_IDS

    # Verify 9 journey and 11 child operations
    journey_ids = [
        op.operation_id
        for op in ops
        if op.operation_id.startswith("parenthood.journey.")
    ]
    child_ids = [
        op.operation_id for op in ops if op.operation_id.startswith("parenthood.child.")
    ]
    assert tuple(journey_ids) == CANONICAL_PARENTHOOD_JOURNEY_OPERATION_IDS
    assert tuple(child_ids) == CANONICAL_PARENTHOOD_CHILD_OPERATION_IDS


def test_parenthood_operation_safety_properties() -> None:
    """Verify operations are proposal-only, low risk, and belonging to domain:parenthood."""
    ops = build_parenthood_operation_definitions()
    for op in ops:
        assert str(op.domain_id) == "domain:parenthood"
        assert op.risk_level == PolicyRiskLevel.LOW
        assert op.metadata.get("proposal_only") is True
        assert op.metadata.get("no_external_mutation") is True


def test_journey_compare_pathways_result_preserves_uncertainty() -> None:
    """Verify pathway comparison produces structured proposals and preserves cost ranges."""
    res = compare_pathways_result(
        pathways=["surrogacy_international", "adoption_national"],
        criteria={"jurisdiction": "Spain/USA", "budget_range": (60000, 120000)},
    )
    assert res["status"] == "completed"
    assert res["is_proposal"] is True
    assert len(res["pathways"]) == 2
    assert "cost_uncertainty_preserved" in res
    assert res["has_autonomous_decision"] is False


def test_journey_build_timeline_result() -> None:
    """Verify timeline building generates estimated milestone ranges."""
    res = build_timeline_result(
        pathway="surrogacy_usa",
        start_date="2026-09-01",
    )
    assert res["status"] == "completed"
    assert "milestones" in res
    assert res["is_proposal"] is True


def test_child_review_developmental_stage_result() -> None:
    """Verify developmental stage review enforces non-diagnostic normal variation."""
    res = review_developmental_stage_result(
        child_id="child:001",
        stage="toddler",
        observations=["high energy", "selective eating"],
    )
    assert res["status"] == "completed"
    assert res["child_id"] == "child:001"
    assert res["is_diagnostic"] is False
    assert res["normal_variation_confirmed"] is True


def test_child_prepare_parental_decision_result() -> None:
    """Verify preparing a parental decision outputs a proposal requiring user confirmation."""
    res = prepare_parental_decision_result(
        child_id="child:001",
        topic="nursery_school_choice",
        options=["option_a_montessori", "option_b_bilingual"],
        criteria=["proximity", "language_immersion"],
    )
    assert res["status"] == "completed"
    assert res["child_id"] == "child:001"
    assert res["decision_status"] == "proposed"
    assert res["requires_explicit_user_adoption"] is True
    assert res["adopted_by_system"] is False
