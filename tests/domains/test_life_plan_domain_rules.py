"""Tests for Phase 10.29 Life Plan Domain Rules (Decision, Scenario, Alternative Route)."""

from __future__ import annotations

from datetime import datetime, timezone

from cmm.cognitive.enums import (
    ReasoningRuleCategory,
    ReasoningRuleResultStatus,
    ReasoningSeverity,
)
from cmm.cognitive.reasoning_rule_contracts import ReasoningRuleContext
from cmm.domains.life_plan.rules import (
    AlternativeRouteRule,
    DecisionStatusRule,
    ScenarioConsistencyRule,
    evaluate_alternative_route,
    evaluate_decision_status,
    evaluate_scenario_consistency,
)

NOW = datetime(2026, 8, 26, 0, 0, tzinfo=timezone.utc)


# ── Decision Status Evaluator Tests ──────────────────────────────────────────


def test_evaluate_decision_status_preference_not_decision_without_confirmation() -> None:
    res = evaluate_decision_status(
        current_status="preference",
        proposed_status="decision",
        confirmation_evidence=None,
    )
    assert res["allowed"] is False
    assert res["requires_confirmation"] is True
    assert "confirmation" in res["reason"].lower()


def test_evaluate_decision_status_scenario_not_decision_without_confirmation() -> None:
    res = evaluate_decision_status(
        current_status="scenario",
        proposed_status="decision",
        confirmation_evidence=None,
    )
    assert res["allowed"] is False
    assert res["requires_confirmation"] is True


def test_evaluate_decision_status_scenario_not_commitment_without_confirmation() -> None:
    res = evaluate_decision_status(
        current_status="scenario",
        proposed_status="commitment",
        confirmation_evidence=None,
    )
    assert res["allowed"] is False
    assert res["requires_confirmation"] is True


def test_evaluate_decision_status_inference_not_confirmed_fact() -> None:
    res = evaluate_decision_status(
        current_status="idea",
        proposed_status="decision",
        confirmation_evidence=None,
    )
    assert res["allowed"] is False
    assert res["requires_confirmation"] is True


def test_evaluate_decision_status_valid_confirmed_transition() -> None:
    res = evaluate_decision_status(
        current_status="preference",
        proposed_status="decision",
        confirmation_evidence={"confirmed_by": "user", "timestamp": "2026-08-26T00:00:00Z"},
    )
    assert res["allowed"] is True
    assert res["current_status"] == "preference"
    assert res["new_status"] == "decision"


def test_evaluate_decision_status_closed_decision_reopening_protection() -> None:
    # Closed decision cannot reopen without explicit new evidence
    res_no_evidence = evaluate_decision_status(
        current_status="decision",
        proposed_status="idea",
        is_closed=True,
        has_new_evidence=False,
    )
    assert res_no_evidence["allowed"] is False
    assert "reopen" in res_no_evidence["reason"].lower() or "closed" in res_no_evidence["reason"].lower()

    # Closed decision can transition/reopen with explicit new evidence
    res_with_evidence = evaluate_decision_status(
        current_status="decision",
        proposed_status="preference",
        is_closed=True,
        has_new_evidence=True,
        new_evidence={"reason": "Job market change in target country"},
    )
    assert res_with_evidence["allowed"] is True
    assert res_with_evidence["reopened"] is True


# ── Scenario Consistency Evaluator Tests ─────────────────────────────────────


def test_evaluate_scenario_consistency_coherent_scenario() -> None:
    res = evaluate_scenario_consistency(
        scenario_id="scen-001",
        assumptions={"target_city": "Berlin", "work_mode": "remote"},
        milestones=[{"id": "m1", "target_date": "2027-01-01"}],
    )
    assert res["consistent"] is True
    assert res["is_decision"] is False
    assert res["is_commitment"] is False


def test_evaluate_scenario_consistency_detects_contradiction() -> None:
    res = evaluate_scenario_consistency(
        scenario_id="scen-002",
        assumptions={"residence": "Madrid", "on_site_work": "Tokyo"},
        contradictions=["residence Madrid is incompatible with daily on_site_work in Tokyo"],
    )
    assert res["consistent"] is False
    assert len(res["conflicts"]) > 0
    assert res["is_decision"] is False
    assert res["is_commitment"] is False


def test_evaluate_scenario_consistency_preserves_uncertainty() -> None:
    res = evaluate_scenario_consistency(
        scenario_id="scen-003",
        assumptions={"visa_required": None, "budget": "unknown"},
    )
    assert res["consistent"] is True
    assert len(res["uncertainties"]) >= 2


# ── Alternative Route Evaluator Tests ────────────────────────────────────────


def test_evaluate_alternative_route_not_abandonment() -> None:
    res = evaluate_alternative_route(
        primary_goal_id="goal-001",
        alternative_route_id="route-alt-01",
        route_type="fallback",
        rationale="If direct master's entry is delayed, pursue professional certification first",
    )
    assert res["primary_goal_abandoned"] is False
    assert res["is_failure"] is False
    assert res["status"] == "active_alternative"


# ── Rule Classes Tests ────────────────────────────────────────────────────────


def test_decision_status_rule_evaluation() -> None:
    rule = DecisionStatusRule()
    assert rule.definition.id == "life_plan.rule.decision_status"
    assert rule.definition.category == ReasoningRuleCategory.CONSISTENCY.value

    ctx = ReasoningRuleContext(
        reasoning_id="test-reasoning-1",
        timestamp=NOW,
        metadata={
            "current_status": "preference",
            "proposed_status": "decision",
            "confirmation_evidence": None,
        },
    )
    result = rule.evaluate(ctx)
    assert result.status == ReasoningRuleResultStatus.APPLIED
    assert len(result.findings) >= 1
    assert any(f.severity == ReasoningSeverity.WARNING for f in result.findings)


def test_scenario_consistency_rule_evaluation() -> None:
    rule = ScenarioConsistencyRule()
    assert rule.definition.id == "life_plan.rule.scenario_consistency"
    ctx = ReasoningRuleContext(
        reasoning_id="test-reasoning-2",
        timestamp=NOW,
        metadata={
            "scenario_id": "scen-100",
            "assumptions": {"career": "software"},
        },
    )
    result = rule.evaluate(ctx)
    assert result.status == ReasoningRuleResultStatus.APPLIED


def test_alternative_route_rule_evaluation() -> None:
    rule = AlternativeRouteRule()
    assert rule.definition.id == "life_plan.rule.alternative_route"
    ctx = ReasoningRuleContext(
        reasoning_id="test-reasoning-3",
        timestamp=NOW,
        metadata={
            "primary_goal_id": "g-1",
            "alternative_route_id": "alt-1",
        },
    )
    result = rule.evaluate(ctx)
    assert result.status == ReasoningRuleResultStatus.APPLIED
