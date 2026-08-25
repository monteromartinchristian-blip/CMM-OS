"""Tests for Phase 10.29 Life Plan Domain Safety Invariants."""

from __future__ import annotations

from cmm.domains.life_plan.rules import (
    evaluate_alternative_route,
    evaluate_cross_domain_impact,
    evaluate_decision_status,
    evaluate_goal_dependencies,
    evaluate_long_term_temporal,
    evaluate_plan_drift,
    evaluate_resource_constraints,
    evaluate_scenario_consistency,
)


def test_safety_no_silent_preference_to_decision() -> None:
    for pref in ("preference", "idea", "hypothesis"):
        res = evaluate_decision_status(
            current_status=pref,
            proposed_status="decision",
            confirmation_evidence=None,
        )
        assert res["allowed"] is False


def test_safety_no_silent_scenario_to_commitment() -> None:
    res = evaluate_decision_status(
        current_status="scenario",
        proposed_status="commitment",
        confirmation_evidence=None,
    )
    assert res["allowed"] is False


def test_safety_closed_decision_immutable_without_new_evidence() -> None:
    res = evaluate_decision_status(
        current_status="decision",
        proposed_status="idea",
        is_closed=True,
        has_new_evidence=False,
    )
    assert res["allowed"] is False


def test_safety_alternative_route_never_marks_goal_abandoned() -> None:
    res = evaluate_alternative_route(
        primary_goal_id="g-100",
        alternative_route_id="alt-100",
        route_type="fallback",
    )
    assert res["primary_goal_abandoned"] is False
    assert res["is_failure"] is False


def test_safety_scenario_is_never_decision() -> None:
    res = evaluate_scenario_consistency(
        scenario_id="s-1",
        assumptions={"a": 1},
    )
    assert res["is_decision"] is False
    assert res["is_commitment"] is False


def test_safety_resource_constraints_missing_values_do_not_become_zero() -> None:
    res = evaluate_resource_constraints(
        time={"available_hours_per_week": None, "required_hours_per_week": 10.0}
    )
    assert res["dimensions"]["time"]["status"] == "unknown"
    assert res["dimensions"]["time"]["available"] is None


def test_safety_plan_drift_never_infers_automatic_abandonment() -> None:
    res = evaluate_plan_drift(
        planned_state={"milestone": "2026-Q1"},
        actual_state={"milestone": "2026-Q4"},
    )
    assert res["goal_abandoned"] is False


def test_safety_cross_domain_raw_payload_rejected() -> None:
    res = evaluate_cross_domain_impact(
        projection={"status": "unverified_external"},
        is_authorized=False,
    )
    assert res["applied"] is False
