"""Tests for Phase 10.28 Sport Domain Rules."""

from __future__ import annotations

import math
import pytest

from cmm.cognitive.reasoning_rule_contracts import ReasoningRuleContext
from cmm.domains.sport.catalog import (
    CANONICAL_SPORT_RULE_IDS,
    CANONICAL_SPORT_RULE_NAMES,
)
from cmm.domains.sport.rules import (
    HealthConstraintRule,
    InjurySignalRule,
    MeasurementTrendRule,
    ProgressiveOverloadRule,
    RecoveryRule,
    TrainingLoadRule,
    build_sport_rules,
    evaluate_health_constraint,
    evaluate_injury_signal,
    evaluate_measurement_trend,
    evaluate_progressive_overload,
    evaluate_recovery,
    evaluate_training_load,
)


def test_build_sport_rules_exact_canonical_parity() -> None:
    rules = build_sport_rules()
    assert len(rules) == 6
    assert tuple(r.definition.id for r in rules) == CANONICAL_SPORT_RULE_IDS
    assert tuple(r.definition.name for r in rules) == CANONICAL_SPORT_RULE_NAMES


# ── Training Load Rule Tests ──────────────────────────────────────────────────

def test_training_load_preserves_components() -> None:
    res = evaluate_training_load(volume=120.0, intensity=0.7, frequency=3)
    assert res["status"] == "evaluated"
    assert res["components"]["volume"] == 120.0
    assert res["components"]["intensity"] == 0.7
    assert res["components"]["frequency"] == 3
    assert res["load_value"] == pytest.approx(252.0)


def test_training_load_missing_input_remains_unknown() -> None:
    res = evaluate_training_load(volume=120.0, intensity=None, frequency=3)
    assert res["status"] == "unknown"
    assert res["components"]["intensity"] is None


def test_training_load_rejects_invalid_numeric_evidence() -> None:
    # Boolean as number
    res_bool = evaluate_training_load(volume=True, intensity=0.7, frequency=3)  # type: ignore[arg-type]
    assert res_bool["status"] == "invalid_evidence"

    # NaN / Inf
    res_nan = evaluate_training_load(volume=float("nan"), intensity=0.7, frequency=3)
    assert res_nan["status"] == "invalid_evidence"

    res_inf = evaluate_training_load(volume=100.0, intensity=float("inf"), frequency=3)
    assert res_inf["status"] == "invalid_evidence"

    # Negative volume/frequency
    res_neg = evaluate_training_load(volume=-50.0, intensity=0.7, frequency=3)
    assert res_neg["status"] == "invalid_evidence"


# ── Progressive Overload Rule Tests ───────────────────────────────────────────

def test_progressive_overload_comparison() -> None:
    res = evaluate_progressive_overload(
        baseline_load=100.0,
        proposed_load=108.0,
        threshold_percentage=15.0,
    )
    assert res["status"] == "accepted"
    assert res["baseline_load"] == 100.0
    assert res["proposed_load"] == 108.0
    assert res["increase_percentage"] == pytest.approx(8.0)


def test_progressive_overload_without_threshold_preserves_uncertainty() -> None:
    res = evaluate_progressive_overload(
        baseline_load=100.0,
        proposed_load=112.0,
        threshold_percentage=None,
    )
    assert res["status"] == "proposal"
    assert res["certainty"] is False
    assert "No explicit overload threshold configured" in res["rationale"]


def test_progressive_overload_exceeding_threshold() -> None:
    res = evaluate_progressive_overload(
        baseline_load=100.0,
        proposed_load=125.0,
        threshold_percentage=10.0,
    )
    assert res["status"] == "exceeds_threshold"
    assert res["increase_percentage"] == pytest.approx(25.0)


# ── Recovery Rule Tests ───────────────────────────────────────────────────────

def test_recovery_evaluation_mutable_state() -> None:
    res1 = evaluate_recovery(rest_hours=8.0, fatigue_score=3, pain_score=1, workload_score=5)
    assert res1["readiness_state"] in ("ready", "optimal")

    # Newer evidence updates readiness
    res2 = evaluate_recovery(rest_hours=4.0, fatigue_score=8, pain_score=5, workload_score=9)
    assert res2["readiness_state"] in ("limited", "hold")
    assert res2["is_mutable"] is True


def test_recovery_missing_data_returns_unknown() -> None:
    res = evaluate_recovery(rest_hours=None, fatigue_score=None, pain_score=0, workload_score=5)
    assert res["readiness_state"] == "unknown"


# ── Injury Signal Rule Tests ─────────────────────────────────────────────────

def test_injury_signal_produces_non_diagnostic_signals() -> None:
    res = evaluate_injury_signal(
        pain_score=7,
        performance_drop=0.3,
        wearable_anomaly=True,
        load_spike=True,
    )
    assert res["action"] in ("stop_and_check", "request_health_review", "reduce_load", "hold")
    assert res["is_diagnosis"] is False
    assert "diagnosis" not in res
    assert "clinical_label" not in res


def test_injury_signal_prevents_diagnosis_creation() -> None:
    res = evaluate_injury_signal(pain_score=8, pain_location="knee")
    assert res["is_diagnosis"] is False
    assert "ACL tear" not in str(res)
    assert "tendonitis" not in str(res)


# ── Health Constraint Rule Tests ──────────────────────────────────────────────

def test_health_constraint_accepts_authorized_projection() -> None:
    projection = {
        "constraint_id": "const-123",
        "status": "active",
        "effective_from": "2026-08-01",
        "effective_until": "2026-09-01",
        "activity_limits": ["no_running"],
        "load_limits": {"max_hr": 140},
        "source_reference": "health.ref.001",
        "provenance": {"domain": "health"},
        "authorization_reference": "auth.scope.001",
    }
    res = evaluate_health_constraint(projection, is_authorized=True, is_current=True)
    assert res["applied"] is True
    assert res["constraint"]["constraint_id"] == "const-123"
    assert res["provenance"]["authorization_reference"] == "auth.scope.001"


def test_health_constraint_rejects_expired_or_unauthorized() -> None:
    projection = {
        "constraint_id": "const-123",
        "status": "active",
    }
    res_unauth = evaluate_health_constraint(projection, is_authorized=False, is_current=True)
    assert res_unauth["applied"] is False

    res_expired = evaluate_health_constraint(projection, is_authorized=True, is_current=False)
    assert res_expired["applied"] is False


def test_health_constraint_rejects_raw_medical_report() -> None:
    medical_dossier = {
        "full_clinical_history": ["surgery_2020", "diagnosis_X"],
        "medication_list": ["medA", "medB"],
        "raw_health_memory": True,
    }
    res = evaluate_health_constraint(medical_dossier, is_authorized=True, is_current=True)
    assert res["applied"] is False
    assert res["reason"] == "rejected_unauthorized_dossier"


# ── Measurement Trend Rule Tests ──────────────────────────────────────────────

def test_measurement_trend_requires_sufficient_observations() -> None:
    single_obs = [{"timestamp": "2026-08-01", "value": 70.0, "unit": "kg", "method": "scale"}]
    res_single = evaluate_measurement_trend(single_obs, metric="weight")
    assert res_single["status"] == "insufficient_data"

    multi_obs = [
        {"timestamp": "2026-08-01", "value": 70.0, "unit": "kg", "method": "scale"},
        {"timestamp": "2026-08-08", "value": 69.5, "unit": "kg", "method": "scale"},
        {"timestamp": "2026-08-15", "value": 69.0, "unit": "kg", "method": "scale"},
    ]
    res_multi = evaluate_measurement_trend(multi_obs, metric="weight")
    assert res_multi["status"] == "evaluated"
    assert res_multi["direction"] == "decreasing"


def test_measurement_trend_rejects_incomparable_units_or_methods() -> None:
    mismatched = [
        {"timestamp": "2026-08-01", "value": 70.0, "unit": "kg", "method": "scale"},
        {"timestamp": "2026-08-08", "value": 154.0, "unit": "lbs", "method": "scale"},
    ]
    res = evaluate_measurement_trend(mismatched, metric="weight")
    assert res["status"] == "incomparable_units"


def test_measurement_trend_preserves_punctual_outlier() -> None:
    obs = [
        {"timestamp": "2026-08-01", "value": 70.0, "unit": "kg", "method": "scale"},
        {"timestamp": "2026-08-02", "value": 85.0, "unit": "kg", "method": "scale"},  # outlier
        {"timestamp": "2026-08-08", "value": 70.2, "unit": "kg", "method": "scale"},
    ]
    res = evaluate_measurement_trend(obs, metric="weight")
    assert res["status"] == "evaluated"
    assert len(res["outliers"]) == 1
    assert res["outliers"][0]["value"] == 85.0
