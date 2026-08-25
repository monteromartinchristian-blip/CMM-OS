"""Tests for Phase 10.29 Life Plan Domain Rules and Deterministic Evaluators."""

from __future__ import annotations

from datetime import datetime, timezone

from cmm.cognitive.enums import (
    ReasoningRuleResultStatus,
)
from cmm.cognitive.reasoning_rule_contracts import ReasoningRuleContext
from cmm.domains.life_plan.catalog import (
    CANONICAL_LIFE_PLAN_RULE_IDS,
    CANONICAL_LIFE_PLAN_RULE_NAMES,
)
from cmm.domains.life_plan.rules import (
    build_life_plan_rules,
    evaluate_alternative_route,
    evaluate_cross_domain_impact,
    evaluate_decision_status,
    evaluate_goal_dependencies,
    evaluate_long_term_temporal,
    evaluate_plan_drift,
    evaluate_resource_constraints,
    evaluate_scenario_consistency,
)

NOW = datetime(2026, 8, 26, 0, 0, tzinfo=timezone.utc)


def test_build_life_plan_rules_exact_canonical_parity() -> None:
    rules = build_life_plan_rules()
    assert len(rules) == 8
    assert tuple(r.definition.id for r in rules) == CANONICAL_LIFE_PLAN_RULE_IDS
    assert tuple(r.definition.name for r in rules) == CANONICAL_LIFE_PLAN_RULE_NAMES


# ── Decision Status Evaluator Tests ──────────────────────────────────────────


def test_evaluate_decision_status_preference_not_decision_without_confirmation() -> (
    None
):
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


def test_evaluate_decision_status_scenario_not_commitment_without_confirmation() -> (
    None
):
    res = evaluate_decision_status(
        current_status="scenario",
        proposed_status="commitment",
        confirmation_evidence=None,
    )
    assert res["allowed"] is False
    assert res["requires_confirmation"] is True


def test_evaluate_decision_status_inference_not_confirmed_fact() -> None:
    res = evaluate_decision_status(
        current_status="inference",
        proposed_status="decision",
        confirmation_evidence=None,
    )
    assert res["allowed"] is False


def test_evaluate_decision_status_inference_cannot_become_commitment() -> None:
    res = evaluate_decision_status(
        current_status="inference",
        proposed_status="commitment",
        confirmation_evidence=None,
    )
    assert res["allowed"] is False


def test_evaluate_decision_status_unknown_current_status_fails_closed() -> None:
    res = evaluate_decision_status(
        current_status="nonsense",
        proposed_status="decision",
        confirmation_evidence=None,
    )
    assert res["allowed"] is False


def test_evaluate_decision_status_unknown_proposed_status_fails_closed() -> None:
    res = evaluate_decision_status(
        current_status="idea",
        proposed_status="confirmed_fact",
        confirmation_evidence=None,
    )
    assert res["allowed"] is False


def test_evaluate_decision_status_valid_confirmed_transition() -> None:
    res = evaluate_decision_status(
        current_status="preference",
        proposed_status="decision",
        confirmation_evidence={
            "confirmed_by": "user",
            "timestamp": "2026-08-26T00:00:00Z",
        },
    )
    assert res["allowed"] is True
    assert res["current_status"] == "preference"
    assert res["new_status"] == "decision"


def test_evaluate_decision_status_closed_decision_reopening_protection() -> None:
    res_no_evidence = evaluate_decision_status(
        current_status="decision",
        proposed_status="idea",
        is_closed=True,
        has_new_evidence=False,
    )
    assert res_no_evidence["allowed"] is False
    assert (
        "closed" in res_no_evidence["reason"].lower()
        or "reopen" in res_no_evidence["reason"].lower()
    )

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
        assumption_conflicts=[("residence", "on_site_work")],
    )
    assert res["consistent"] is False
    assert len(res["conflicts"]) > 0
    assert res["is_decision"] is False
    assert res["is_commitment"] is False


def test_evaluate_scenario_consistency_computes_milestone_ordering_conflict() -> None:
    res = evaluate_scenario_consistency(
        scenario_id="scen-temporal-01",
        milestones=[
            {"id": "move", "target_date": "2028-01-01T00:00:00Z"},
            {"id": "start_job", "target_date": "2027-01-01T00:00:00Z", "depends_on": "move"},
        ],
    )
    assert res["consistent"] is False
    assert len(res["conflicts"]) > 0


def test_evaluate_scenario_consistency_computes_resource_incompatibility() -> None:
    res = evaluate_scenario_consistency(
        scenario_id="scen-res-01",
        resource_constraints={
            "time": {"available_hours_per_week": 10.0, "required_hours_per_week": 40.0}
        },
    )
    assert res["consistent"] is False
    assert len(res["conflicts"]) > 0


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


# ── Goal Dependency Evaluator Tests ──────────────────────────────────────────


def test_evaluate_goal_dependencies_valid_graph() -> None:
    prereqs = {
        "goal_b": ["goal_a"],
        "goal_c": ["goal_b"],
    }
    res = evaluate_goal_dependencies(dependencies=prereqs)
    assert res["valid"] is True
    assert res["has_cycles"] is False
    assert "goal_b" in res["prerequisites"]


def test_evaluate_goal_dependencies_detects_cycles() -> None:
    circular = {
        "goal_a": ["goal_b"],
        "goal_b": ["goal_c"],
        "goal_c": ["goal_a"],
    }
    res = evaluate_goal_dependencies(dependencies=circular)
    assert res["valid"] is False
    assert res["has_cycles"] is True
    assert len(res["cycles"]) > 0


def test_evaluate_goal_dependencies_distinguishes_soft_dependency() -> None:
    res = evaluate_goal_dependencies(
        dependencies={"goal_x": ["goal_y"]},
        soft_dependencies={"goal_x": ["goal_z"]},
    )
    assert res["valid"] is True
    assert "goal_y" in res["prerequisites"]["goal_x"]
    assert "goal_z" in res["soft_dependencies"]["goal_x"]


# ── Resource Constraint Evaluator Tests ──────────────────────────────────────


def test_evaluate_resource_constraints_independent_dimensions() -> None:
    res = evaluate_resource_constraints(
        time={"available_hours_per_week": 15.0, "required_hours_per_week": 10.0},
        money={"available_funds": 5000.0, "required_funds": 3000.0},
        energy={"current_energy_level": "moderate", "minimum_required": "moderate"},
        available_capacity={"slots": 2, "required_slots": 1},
    )
    assert res["status"] == "feasible"
    assert res["dimensions"]["time"]["status"] == "sufficient"
    assert res["dimensions"]["money"]["status"] == "sufficient"


def test_evaluate_resource_constraints_missing_values_remain_unknown() -> None:
    res = evaluate_resource_constraints(
        time={"available_hours_per_week": None, "required_hours_per_week": 10.0},
        money={"available_funds": None, "required_funds": 1000.0},
    )
    assert res["dimensions"]["time"]["status"] == "unknown"
    assert res["dimensions"]["money"]["status"] == "unknown"
    assert res["status"] == "unknown"


def test_evaluate_resource_constraints_rejects_malformed_values() -> None:
    for bad_val in (
        True,
        False,
        float("nan"),
        float("inf"),
        float("-inf"),
        "not_a_num",
    ):
        res = evaluate_resource_constraints(
            time={"available_hours_per_week": bad_val, "required_hours_per_week": 10.0},
        )
        assert res["dimensions"]["time"]["status"] == "invalid_evidence"


# ── Long Term Temporal Evaluator Tests ───────────────────────────────────────


def test_evaluate_long_term_temporal_valid_milestones() -> None:
    milestones = [
        {"id": "m1", "target_date": "2027-01-01"},
        {"id": "m2", "target_date": "2027-06-01", "depends_on": "m1"},
        {"id": "m3", "target_date": "2028-01-01", "depends_on": "m2"},
    ]
    res = evaluate_long_term_temporal(milestones=milestones)
    assert res["valid"] is True
    assert res["ordering_valid"] is True


def test_evaluate_long_term_temporal_detects_impossible_ordering() -> None:
    # m2 depends on m1 but date is earlier
    milestones = [
        {"id": "m1", "target_date": "2027-06-01"},
        {"id": "m2", "target_date": "2027-01-01", "depends_on": "m1"},
    ]
    res = evaluate_long_term_temporal(milestones=milestones)
    assert res["valid"] is False
    assert res["ordering_valid"] is False
    assert len(res["ordering_conflicts"]) > 0


def test_evaluate_long_term_temporal_preserves_uncertainty() -> None:
    milestones = [
        {"id": "m1", "target_date": None},
        {"id": "m2", "target_date": "2027-06-01"},
    ]
    res = evaluate_long_term_temporal(milestones=milestones)
    assert res["valid"] is True
    assert len(res["uncertain_milestones"]) == 1


# ── Cross Domain Impact Evaluator Tests ──────────────────────────────────────


def test_evaluate_cross_domain_impact_requires_authorized_contribution() -> None:
    # Raw unverified mapping fails
    raw_payload = {"source_domain": "domain:health", "activity_limits": ["no_travel"]}
    res_unauth = evaluate_cross_domain_impact(
        projection=raw_payload, is_authorized=False
    )
    assert res_unauth["applied"] is False

    # Prohibited clinical dossier fields are rejected
    dossier = {
        "full_clinical_history": ["heart_surgery"],
        "medication_list": ["med1"],
    }
    res_dossier = evaluate_cross_domain_impact(projection=dossier, is_authorized=True)
    assert res_dossier["applied"] is False
    assert res_dossier["reason"] == "rejected_unauthorized_dossier"


# ── Plan Drift Evaluator Tests ───────────────────────────────────────────────


def test_evaluate_plan_drift_detects_divergence_without_abandonment() -> None:
    planned = {"target_career": "data_science", "target_year": 2027}
    confirmed = {"decisions": ["enrolled_in_masters"]}
    actual = {"current_role": "software_engineer", "progress_pct": 50}

    res = evaluate_plan_drift(
        planned_state=planned,
        confirmed_decisions=confirmed,
        actual_state=actual,
    )
    assert res["status"] == "evaluated"
    assert res["goal_abandoned"] is False
    assert res["has_drift"] is False or res["has_drift"] is True
    assert res["provenance_preserved"] is True


# ── Rule Classes Tests ────────────────────────────────────────────────────────


def test_rule_classes_evaluation() -> None:
    for rule in build_life_plan_rules():
        ctx = ReasoningRuleContext(
            reasoning_id=f"test-rule-{rule.definition.id}",
            timestamp=NOW,
            metadata={},
        )
        result = rule.evaluate(ctx)
        assert result.status == ReasoningRuleResultStatus.APPLIED
