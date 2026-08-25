"""Tests for Phase 10.28 Sport Domain Rules."""

from __future__ import annotations

import pytest

from cmm.domains.sport.catalog import (
    CANONICAL_SPORT_RULE_IDS,
    CANONICAL_SPORT_RULE_NAMES,
)
from cmm.domains.sport.rules import (
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
    res1 = evaluate_recovery(
        rest_hours=8.0, fatigue_score=3, pain_score=1, workload_score=5
    )
    assert res1["readiness_state"] in ("ready", "optimal")

    # Newer evidence updates readiness
    res2 = evaluate_recovery(
        rest_hours=4.0, fatigue_score=8, pain_score=5, workload_score=9
    )
    assert res2["readiness_state"] in ("limited", "hold")
    assert res2["is_mutable"] is True


def test_recovery_missing_data_returns_unknown() -> None:
    res = evaluate_recovery(
        rest_hours=None, fatigue_score=None, pain_score=0, workload_score=5
    )
    assert res["readiness_state"] == "unknown"


# ── Injury Signal Rule Tests ─────────────────────────────────────────────────


def test_injury_signal_produces_non_diagnostic_signals() -> None:
    res = evaluate_injury_signal(
        pain_score=7,
        performance_drop=0.3,
        wearable_anomaly=True,
        load_spike=True,
    )
    assert res["action"] in (
        "stop_and_check",
        "request_health_review",
        "reduce_load",
        "hold",
    )
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
    import dataclasses
    from datetime import datetime, timezone

    from cmm.agent_runtime.approval_repository import InMemoryApprovalRepository
    from cmm.agent_runtime.approval_service import ApprovalService
    from cmm.agent_runtime.domain_permission_contracts import (
        PermissionApprovalRequirement,
        PermissionCapability,
    )
    from cmm.domains.approval_bridge import to_approval_requirement
    from cmm.domains.general.permissions import build_general_permission_policy
    from cmm.domains.health.permissions import build_health_permission_policy
    from cmm.domains.permission_contracts import CrossDomainPermissionRequest
    from cmm.domains.permission_gate import (
        DomainPermissionGate,
        PermissionGateOutcome,
    )
    from cmm.domains.permission_registry import DomainPermissionRegistry
    from cmm.domains.permission_resolution import DomainPermissionResolver
    from cmm.domains.sport import SPORT_DOMAIN_ID, build_sport_permission_policy

    now = datetime(2026, 8, 25, 12, 0, tzinfo=timezone.utc)
    perm_registry = DomainPermissionRegistry()
    perm_registry.register(build_sport_permission_policy())
    perm_registry.register(build_general_permission_policy())
    health_policy = dataclasses.replace(
        build_health_permission_policy(),
        allow_cross_domain_access=True,
        allowed_target_domains=("domain:sport",),
        allowed_capabilities=(
            PermissionCapability.DOMAIN_CROSS_ACCESS,
            PermissionCapability.RESOURCE_READ,
        ),
        allowed_resource_kinds=("resource.health_resource",),
        allowed_sensitivity_levels=("restricted",),
    )
    perm_registry.register(health_policy)
    approval_service = ApprovalService(InMemoryApprovalRepository())
    resolver = DomainPermissionResolver(perm_registry)
    gate = DomainPermissionGate(resolver, approval_service, clock=lambda: now)

    cross_request = CrossDomainPermissionRequest(
        request_id="auth.scope.001",
        source_domain="domain:health",
        target_domain=SPORT_DOMAIN_ID,
        capability=PermissionCapability.RESOURCE_READ,
        reason="return-to-training functional constraint",
        actor_id="actor-test",
        session_id="sess-test",
        sensitivity_level="restricted",
        resource_ids=("sport.resource.health_resource:rtt-001",),
        resource_kinds=("resource.health_resource",),
    )
    pending = gate.evaluate_cross_domain(cross_request)
    req_item = PermissionApprovalRequirement.from_dict(pending.approval_requirements[0])
    app_req = approval_service.create_request_from_requirement(
        to_approval_requirement(req_item, agent_run_id="run-1"),
        requested_by="sports-physician",
    )
    approval_service.approve(app_req.id, "sports-physician")
    consumed = gate.evaluate_cross_domain(cross_request, approval_request_id=app_req.id)
    assert consumed.outcome is PermissionGateOutcome.APPROVAL_CONSUMED

    projection = {
        "constraint_id": "const-123",
        "status": "active",
        "effective_from": "2026-08-01",
        "effective_until": "2026-09-01",
        "activity_limits": ["no_running"],
        "load_limits": {"max_hr": 140},
        "source_reference": "health.ref.001",
        "provenance": {"domain": "health"},
        "authorization_reference": consumed.decision_id,
    }
    res = evaluate_health_constraint(
        projection,
        permission_request=cross_request,
        permission_decision=consumed,
        permission_gate=gate,
        now=now,
    )
    assert res["applied"] is True
    assert res["constraint"]["constraint_id"] == "const-123"
    assert res["provenance"]["authorization_reference"] == consumed.decision_id


def test_health_constraint_rejects_expired_or_unauthorized() -> None:
    from cmm.agent_runtime.domain_permission_contracts import PermissionOutcome
    from cmm.domains.permission_contracts import CrossDomainPermissionDecision

    perm_dec = CrossDomainPermissionDecision(
        request_id="auth.scope.001",
        decision=PermissionOutcome.ALLOW,
    )
    projection = {
        "constraint_id": "const-123",
        "status": "active",
    }
    res_unauth = evaluate_health_constraint(
        projection, is_authorized=False, is_current=True
    )
    assert res_unauth["applied"] is False

    res_expired = evaluate_health_constraint(
        projection, permission_decision=perm_dec, is_current=False
    )
    assert res_expired["applied"] is False


def test_health_constraint_rejects_raw_medical_report() -> None:
    medical_dossier = {
        "full_clinical_history": ["surgery_2020", "diagnosis_X"],
        "medication_list": ["medA", "medB"],
        "raw_health_memory": True,
    }
    res = evaluate_health_constraint(
        medical_dossier, is_authorized=True, is_current=True
    )
    assert res["applied"] is False
    assert res["reason"] == "rejected_unauthorized_dossier"


# ── Measurement Trend Rule Tests ──────────────────────────────────────────────


def test_measurement_trend_requires_sufficient_observations() -> None:
    single_obs = [
        {"timestamp": "2026-08-01", "value": 70.0, "unit": "kg", "method": "scale"}
    ]
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
        {
            "timestamp": "2026-08-01T07:00:00Z",
            "value": 70.0,
            "unit": "kg",
            "method": "scale",
            "metric": "weight",
        },
        {
            "timestamp": "2026-08-02T07:00:00Z",
            "value": 85.0,
            "unit": "kg",
            "method": "scale",
            "metric": "weight",
        },  # outlier
        {
            "timestamp": "2026-08-08T07:00:00Z",
            "value": 70.2,
            "unit": "kg",
            "method": "scale",
            "metric": "weight",
        },
    ]
    res = evaluate_measurement_trend(obs, metric="weight")
    assert res["status"] == "evaluated"
    assert len(res["outliers"]) == 1
    assert res["outliers"][0]["value"] == 85.0


def test_measurement_trend_requires_valid_timestamps_and_deterministic_sorting() -> (
    None
):
    # Missing timestamp in observations
    missing_ts = [
        {"value": 70.0, "unit": "kg", "method": "scale", "metric": "weight"},
        {"value": 69.0, "unit": "kg", "method": "scale", "metric": "weight"},
    ]
    res_missing = evaluate_measurement_trend(missing_ts, metric="weight")
    assert res_missing["status"] == "invalid_evidence"

    # Unsorted input timestamps: earlier date is second in list
    unsorted_obs = [
        {
            "timestamp": "2026-08-15T00:00:00Z",
            "value": 68.0,
            "unit": "kg",
            "method": "scale",
            "metric": "weight",
        },
        {
            "timestamp": "2026-08-01T00:00:00Z",
            "value": 70.0,
            "unit": "kg",
            "method": "scale",
            "metric": "weight",
        },
    ]
    # Chronologically: 70.0 (Aug 1) -> 68.0 (Aug 15) = decreasing
    res_sorted = evaluate_measurement_trend(unsorted_obs, metric="weight")
    assert res_sorted["status"] == "evaluated"
    assert res_sorted["direction"] == "decreasing"

    # Mismatched metric in observation
    mismatched_metric = [
        {
            "timestamp": "2026-08-01T00:00:00Z",
            "value": 70.0,
            "unit": "kg",
            "method": "scale",
            "metric": "weight",
        },
        {
            "timestamp": "2026-08-15T00:00:00Z",
            "value": 68.0,
            "unit": "kg",
            "method": "scale",
            "metric": "height",
        },
    ]
    res_mismatch = evaluate_measurement_trend(mismatched_metric, metric="weight")
    assert res_mismatch["status"] == "invalid_evidence"


def test_progressive_overload_rejects_non_finite_and_boolean() -> None:
    # NaN proposed load
    res_nan_prop = evaluate_progressive_overload(
        baseline_load=100.0,
        proposed_load=float("nan"),
        threshold_percentage=10.0,
    )
    assert res_nan_prop["status"] == "invalid_evidence"
    assert res_nan_prop["certainty"] is False

    # Inf proposed load
    res_inf_prop = evaluate_progressive_overload(
        baseline_load=100.0,
        proposed_load=float("inf"),
        threshold_percentage=10.0,
    )
    assert res_inf_prop["status"] == "invalid_evidence"
    assert res_inf_prop["certainty"] is False

    # NaN threshold
    res_nan_thresh = evaluate_progressive_overload(
        baseline_load=100.0,
        proposed_load=105.0,
        threshold_percentage=float("nan"),
    )
    assert res_nan_thresh["status"] == "invalid_evidence"
    assert res_nan_thresh["certainty"] is False

    # Boolean threshold
    res_bool_thresh = evaluate_progressive_overload(
        baseline_load=100.0,
        proposed_load=105.0,
        threshold_percentage=True,
    )
    assert res_bool_thresh["status"] == "invalid_evidence"
    assert res_bool_thresh["certainty"] is False
