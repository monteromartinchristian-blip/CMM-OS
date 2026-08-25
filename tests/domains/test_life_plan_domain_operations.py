"""Tests for Phase 10.29 Life Plan Domain Operations."""

from __future__ import annotations

from cmm.domains.life_plan.catalog import (
    CANONICAL_LIFE_PLAN_OPERATION_IDS,
)
from cmm.domains.life_plan.operations import (
    build_life_plan_operation_definitions,
    build_timeline_result,
    compare_scenarios_result,
    create_milestones_result,
    detect_dependencies_result,
    evaluate_feasibility_result,
    generate_periodic_review_result,
    identify_risks_result,
    review_goals_result,
    track_decisions_result,
    update_plan_result,
)


def test_life_plan_operation_definitions_canonical_parity() -> None:
    ops = build_life_plan_operation_definitions()
    assert len(ops) == 10
    assert tuple(op.operation_id for op in ops) == CANONICAL_LIFE_PLAN_OPERATION_IDS
    assert all(op.domain_id == "domain:life-plan" for op in ops)


def test_build_timeline_result_preserves_uncertainty() -> None:
    milestones = [
        {"id": "m1", "target_date": "2027-01-01"},
        {"id": "m2", "target_date": None},
    ]
    res = build_timeline_result(milestones=milestones)
    assert res["status"] == "completed"
    assert res["is_proposal"] is True
    assert len(res["timeline"]["milestones"]) == 2
    assert "m2" in res["timeline"]["uncertain_milestones"]


def test_compare_scenarios_result_does_not_commit() -> None:
    scenarios = [
        {"id": "scen_a", "assumptions": {"city": "Berlin"}},
        {"id": "scen_b", "assumptions": {"city": "Tokyo"}},
    ]
    res = compare_scenarios_result(scenarios=scenarios)
    assert res["status"] == "completed"
    assert res["is_proposal"] is True
    assert len(res["scenarios_evaluated"]) == 2
    assert res["is_decision"] is False
    assert res["is_commitment"] is False


def test_review_goals_result() -> None:
    goals = [{"id": "g1", "title": "Master German C1"}]
    res = review_goals_result(goals=goals)
    assert res["status"] == "completed"
    assert res["is_proposal"] is True
    assert res["goals_count"] == 1


def test_detect_dependencies_result_valid_and_cyclic() -> None:
    res_valid = detect_dependencies_result(dependencies={"g2": ["g1"]})
    assert res_valid["valid"] is True
    assert res_valid["has_cycles"] is False

    res_cyclic = detect_dependencies_result(dependencies={"g1": ["g2"], "g2": ["g1"]})
    assert res_cyclic["valid"] is False
    assert res_cyclic["has_cycles"] is True


def test_identify_risks_result() -> None:
    res = identify_risks_result(risks=[{"id": "r1", "description": "visa delay"}])
    assert res["status"] == "completed"
    assert res["is_proposal"] is True
    assert len(res["risks"]) == 1


def test_update_plan_result_does_not_silently_persist_decision() -> None:
    # Unconfirmed preference -> decision in updates is rejected
    res_unconfirmed = update_plan_result(
        plan_id="plan-001",
        updates={"current_status": "preference", "proposed_status": "decision"},
        confirmation_evidence=None,
    )
    assert res_unconfirmed["status"] == "update_pending_confirmation"
    assert res_unconfirmed["is_proposal"] is True

    # Confirmed update succeeds as proposal
    res_confirmed = update_plan_result(
        plan_id="plan-001",
        updates={"current_status": "preference", "proposed_status": "decision"},
        confirmation_evidence={"confirmed_by": "user"},
    )
    assert res_confirmed["status"] == "proposed_update"
    assert res_confirmed["is_proposal"] is True


def test_create_milestones_result() -> None:
    milestones = [{"id": "m1", "title": "Finish Degree"}]
    res = create_milestones_result(milestones=milestones)
    assert res["status"] == "created"
    assert res["is_proposal"] is True
    assert len(res["milestones"]) == 1


def test_generate_periodic_review_result() -> None:
    res = generate_periodic_review_result(period="quarterly")
    assert res["status"] == "completed"
    assert res["is_proposal"] is True
    assert res["period"] == "quarterly"


def test_evaluate_feasibility_result() -> None:
    res = evaluate_feasibility_result(
        time={"available_hours_per_week": 20.0, "required_hours_per_week": 15.0},
        money={"available_funds": 10000.0, "required_funds": 5000.0},
    )
    assert res["status"] == "evaluated"
    assert res["is_proposal"] is True
    assert res["feasibility"] == "feasible"


def test_track_decisions_result() -> None:
    res_unauth = track_decisions_result(
        decision_id="dec-001",
        current_status="preference",
        proposed_status="decision",
        confirmation_evidence=None,
    )
    assert res_unauth["status"] == "transition_denied"

    res_auth = track_decisions_result(
        decision_id="dec-001",
        current_status="preference",
        proposed_status="decision",
        confirmation_evidence={"confirmed_by": "user"},
    )
    assert res_auth["status"] == "tracked"
