"""Tests for Phase 10.28 Sport Domain Operations."""

from __future__ import annotations

from cmm.domains.sport.catalog import (
    CANONICAL_SPORT_OPERATION_IDS,
)
from cmm.domains.sport.operations import (
    adjust_training_load_result,
    build_sport_operation_definitions,
    create_training_plan_result,
    generate_workout_result,
    identify_risks_result,
    review_progress_result,
    review_recovery_result,
    schedule_sessions_result,
    track_measurements_result,
)


def test_sport_operation_definitions_canonical_parity() -> None:
    ops = build_sport_operation_definitions()
    assert len(ops) == 8
    assert tuple(op.operation_id for op in ops) == CANONICAL_SPORT_OPERATION_IDS
    assert all(op.domain_id == "domain:sport" for op in ops)


def test_create_training_plan_is_proposal_not_prescription() -> None:
    res = create_training_plan_result(goal="marathon", weeks=12)
    assert res["status"] == "completed"
    assert res["is_proposal"] is True
    assert res["is_medical_prescription"] is False
    assert len(res["plan"]["weeks"]) == 12


def test_review_progress_preserves_insufficient_evidence() -> None:
    res = review_progress_result(completed_workouts=[])
    assert res["status"] == "insufficient_data"
    assert res["is_proposal"] is True


def test_adjust_training_load_respects_health_constraint_and_readiness() -> None:
    health_constraint = {"status": "active", "load_limits": {"max_intensity": 0.6}}
    res = adjust_training_load_result(
        current_load=150.0,
        readiness_state="limited",
        health_constraint=health_constraint,
    )
    assert res["status"] == "load_reduced"
    assert res["adjusted_load"] < 150.0
    assert res["constraint_applied"] is True


def test_generate_workout_cannot_bypass_blocking_constraint() -> None:
    blocking_constraint = {"status": "active", "activity_limits": ["no_high_impact"]}
    res = generate_workout_result(
        requested_type="high_intensity_plyometrics",
        health_constraint=blocking_constraint,
    )
    assert res["status"] == "blocked_by_constraint"
    assert res["workout"] is None


def test_track_measurements_preserves_unit_and_provenance() -> None:
    res = track_measurements_result(
        metric="body_weight",
        value=75.5,
        unit="kg",
        timestamp="2026-08-25T10:00:00Z",
        source="smart_scale",
    )
    assert res["status"] == "tracked"
    assert res["measurement"]["unit"] == "kg"
    assert res["measurement"]["source"] == "smart_scale"


def test_review_recovery_uses_current_evidence() -> None:
    res = review_recovery_result(rest_hours=8.0, fatigue_score=2)
    assert res["readiness_state"] == "ready"
    assert res["is_mutable"] is True


def test_identify_risks_emits_non_diagnostic_signals() -> None:
    res = identify_risks_result(pain_score=6, load_spike=True)
    assert res["is_diagnosis"] is False
    assert res["risk_signal"] in (
        "stop_and_check",
        "reduce_load",
        "request_health_review",
    )


def test_schedule_sessions_creates_proposal_denies_direct_calendar_mutation() -> None:
    res_no_approval = schedule_sessions_result(
        sessions=[{"day": "Monday", "time": "08:00"}],
        has_approval=False,
    )
    assert res_no_approval["status"] == "proposal_pending_approval"
    assert res_no_approval["external_calendar_mutated"] is False

    res_with_approval = schedule_sessions_result(
        sessions=[{"day": "Monday", "time": "08:00"}],
        has_approval=True,
    )
    assert res_with_approval["status"] == "ready_for_external_execution"
    assert (
        res_with_approval["external_calendar_mutated"] is False
    )  # actual mutation delegated
