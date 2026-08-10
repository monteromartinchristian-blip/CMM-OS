"""Phase 10.22 — B6: Academic Workload (constraint pipeline).

The audit found the previous implementation only compared a raw total against a
full-time reference.  Workload planning must follow a staged pipeline: HARD
CONSTRAINTS -> FEASIBILITY -> PREFERENCES -> TRADE-OFFS -> SCENARIOS ->
PROPOSAL.  An authorized Health functional constraint (e.g. a reduced-load
cap) affects feasibility; clinical details are never consumed by the domain.
"""

from __future__ import annotations

from cmm.domains.university.rules import evaluate_academic_workload


def test_hard_constraint_unsatisfied_blocks_feasibility():
    """An unsatisfied hard constraint stops the pipeline before preferences."""
    result = evaluate_academic_workload(
        hard_constraints=({"id": "hc-1", "satisfied": False},)
    )
    assert result["feasible"] is False
    assert result["stage"] == "feasibility"
    assert result["proposal"] is None


def test_all_hard_constraints_satisfied_is_feasible():
    result = evaluate_academic_workload(
        hard_constraints=({"id": "hc-1", "satisfied": True},)
    )
    assert result["feasible"] is True
    assert result["stage"] == "preferences"


def test_preferences_applied_after_feasibility():
    result = evaluate_academic_workload(
        hard_constraints=({"id": "hc-1", "satisfied": True},),
        preferences=({"id": "pref-1", "rank": 1},),
    )
    assert result["stage"] == "preferences"
    assert result["preferences_applied"] is True


def test_tradeoffs_emitted_when_preferences_conflict():
    """When preferences conflict, trade-offs are surfaced before scenarios."""
    result = evaluate_academic_workload(
        hard_constraints=({"id": "hc-1", "satisfied": True},),
        preferences=(
            {"id": "pref-1", "rank": 1},
            {"id": "pref-2", "rank": 1},
        ),
    )
    assert result["stage"] == "tradeoffs"
    assert result["tradeoffs"]  # non-empty


def test_scenarios_produced_when_preferences_are_compatible():
    result = evaluate_academic_workload(
        hard_constraints=({"id": "hc-1", "satisfied": True},),
        preferences=(
            {"id": "pref-1", "rank": 1},
            {"id": "pref-2", "rank": 2},
        ),
    )
    assert result["stage"] == "scenarios"
    assert result["scenarios"]


def test_proposal_emitted_when_scenario_selected():
    """A proposal is only emitted at the final stage, never adopted."""
    result = evaluate_academic_workload(
        hard_constraints=({"id": "hc-1", "satisfied": True},),
        preferences=({"id": "pref-1", "rank": 1},),
        selected_scenario="sc-1",
    )
    assert result["stage"] == "proposal"
    assert result["proposal"] == "sc-1"
    assert result["adopted_decision"] is False


def test_health_constraint_affects_feasibility():
    """An authorized Health functional constraint (reduced-load cap) is a hard
    constraint that affects feasibility."""
    result = evaluate_academic_workload(
        total_ect=40,
        full_time_ect=30,
        health_constraint={"functional_cap_ect": 20, "authorized": True},
    )
    assert result["feasible"] is False
    assert result["stage"] == "feasibility"


def test_health_constraint_satisfied_is_feasible():
    result = evaluate_academic_workload(
        total_ect=15,
        full_time_ect=30,
        health_constraint={"functional_cap_ect": 20, "authorized": True},
    )
    assert result["feasible"] is True


def test_clinical_details_never_consumed():
    """Clinical details supplied by Health are never consumed by the domain."""
    result = evaluate_academic_workload(
        total_ect=15,
        full_time_ect=30,
        health_constraint={
            "functional_cap_ect": 20,
            "authorized": True,
            "clinical_details": "sensitive-diagnosis",
        },
    )
    assert result["clinical_details_consumed"] is False
    assert "clinical_details" not in result["consumed_factors"]


def test_unauthorized_health_constraint_ignored():
    result = evaluate_academic_workload(
        total_ect=40,
        full_time_ect=30,
        health_constraint={"functional_cap_ect": 20, "authorized": False},
    )
    assert result["feasible"] is True