"""Tests for Phase 10.29 Life Plan Domain Safety Invariants."""

from __future__ import annotations

from cmm.domains.life_plan.rules import (
    evaluate_alternative_route,
    evaluate_decision_status,
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
