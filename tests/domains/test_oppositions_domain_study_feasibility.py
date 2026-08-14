"""Phase 10.23 — StudyFeasibilityRule tests (frozen spec §39)."""

from __future__ import annotations

from cmm.domains.oppositions.rules import evaluate_study_feasibility


def test_feasible_scenario():
    record = evaluate_study_feasibility(
        remaining_hours=20, available_hours=30, target_days=30
    )
    assert record["feasible"] is True
    assert record["adopted_plan"] is False


def test_infeasible_hard_constraint():
    record = evaluate_study_feasibility(
        remaining_hours=100, available_hours=10, target_days=5
    )
    assert record["infeasible"] is True
    assert "capacity_exceeded" in record["unmet_hard_constraints"]


def test_unknown_decision_critical_constraint_unresolved():
    record = evaluate_study_feasibility(
        remaining_hours=None, available_hours=10, target_days=5
    )
    assert record["unresolved"] is True
    assert record["feasible"] is False


def test_preferences_only_after_hard_constraints():
    # a missing usable capacity should never become feasible via preference
    record = evaluate_study_feasibility(
        remaining_hours=10, available_hours=1, target_days=5
    )
    assert record["hard_before_preferences"] is True
    assert record["feasible"] is False


def test_malformed_numeric_does_not_raise():

    record = evaluate_study_feasibility(
        remaining_hours="100", available_hours=10
    )
    # numeric strings are not silently coerced
    assert record["unresolved"] is True


def test_target_date_missing_invalid():
    record = evaluate_study_feasibility(
        remaining_hours=10, available_hours=30, target_days="soon"
    )
    assert record["target_date_invalid"] is True


def test_no_plan_silently_adopted():
    record = evaluate_study_feasibility(
        remaining_hours=20, available_hours=30, target_days=30
    )
    assert record["adopted_plan"] is False
    assert record["proposal_only"] is True
    assert record["target_unchanged"] is True
    assert record["calendar_not_modified"] is True


def test_target_date_valid():
    record = evaluate_study_feasibility(
        remaining_hours=20, available_hours=30, target_days=30
    )
    assert record["target_date_invalid"] is False
    assert record["scenarios"][0]["adopted"] is False