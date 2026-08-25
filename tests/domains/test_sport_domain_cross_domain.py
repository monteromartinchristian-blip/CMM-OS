"""Tests for Phase 10.28 Sport <-> Health Cross-Domain Boundary."""

from __future__ import annotations

from cmm.domains.sport.rules import (
    evaluate_health_constraint,
)
from cmm.domains.sport.workflows import execute_return_to_training_workflow


def test_cross_domain_authorized_minimal_projection_only() -> None:
    authorized_projection = {
        "constraint_id": "hc-2026-001",
        "status": "active",
        "activity_limits": ["no_weightbearing_on_right_knee"],
        "load_limits": {"max_hr": 130},
        "source_reference": "health.ref.404",
        "authorization_reference": "auth.scope.sport_return_to_training",
    }
    res = evaluate_health_constraint(
        authorized_projection, is_authorized=True, is_current=True
    )
    assert res["applied"] is True
    assert (
        res["provenance"]["authorization_reference"]
        == "auth.scope.sport_return_to_training"
    )
    assert res["treatment_modification_allowed"] is False


def test_cross_domain_denies_full_health_dossier() -> None:
    raw_dossier = {
        "constraint_id": "hc-2026-001",
        "full_clinical_history": ["meniscus_repair_2025", "cortisone_injection"],
        "medication_list": ["ibuprofen_800mg"],
        "raw_health_memory": {"patient_notes": "sensitive detail"},
    }
    res = evaluate_health_constraint(raw_dossier, is_authorized=True, is_current=True)
    assert res["applied"] is False
    assert res["reason"] == "rejected_unauthorized_dossier"


def test_cross_domain_stale_or_unauthorized_constraint_rejected() -> None:
    valid_projection = {
        "constraint_id": "hc-2026-001",
        "status": "active",
        "activity_limits": ["no_sprinting"],
    }

    # Unauthorized -> rejected
    res_unauth = evaluate_health_constraint(
        valid_projection, is_authorized=False, is_current=True
    )
    assert res_unauth["applied"] is False

    # Expired -> rejected
    res_expired = evaluate_health_constraint(
        valid_projection, is_authorized=True, is_current=False
    )
    assert res_expired["applied"] is False


def test_cross_domain_return_to_training_safety_invariant() -> None:
    health_projection = {
        "constraint_id": "hc-002",
        "status": "active",
        "load_limits": {"max_intensity": 0.5},
        "authorization_reference": "auth.002",
    }
    vetted = evaluate_health_constraint(
        health_projection, is_authorized=True, is_current=True
    )

    wf_res = execute_return_to_training_workflow(
        rest_hours=8.0,
        fatigue_score=2,
        pain_score=0,
        health_constraint=vetted,
        is_current=True,
    )
    assert wf_res["status"] == "completed"
    assert wf_res["health_constraint_applied"] is True
    assert wf_res["is_diagnosis"] is False
    assert wf_res["treatment_modified"] is False
    assert wf_res["clinical_clearance_claimed"] is False


def test_cross_domain_return_to_training_denies_raw_dict_without_vetted_evidence() -> (
    None
):
    health_projection = {
        "constraint_id": "hc-002",
        "status": "active",
        "load_limits": {"reduction_pct": 50},
        "authorization_reference": "auth.fake.999",
    }

    wf_res = execute_return_to_training_workflow(
        rest_hours=8.0,
        fatigue_score=2,
        pain_score=0,
        health_constraint=health_projection,
        is_authorized=True,
        is_current=True,
    )
    assert wf_res["status"] == "completed"
    assert wf_res["health_constraint_applied"] is False
    assert wf_res["recommendation"] == "continue"


def test_cross_domain_clinical_extras_dropped_from_minimized_projection() -> None:
    projection = {
        "constraint_id": "hc-001",
        "status": "active",
        "activity_limits": ["no_running"],
        "load_limits": {"reduction_pct": 10},
        "source_reference": "health:source:1",
        "authorization_reference": "permission:decision:1",
        "diagnosis": "ACL tear",
        "treatment_plan": "surgery",
        "clinical_notes": "secret",
    }

    result = evaluate_health_constraint(
        projection,
        is_authorized=True,
        is_current=True,
    )

    assert result["applied"] is True
    assert result["constraint"] == {
        "constraint_id": "hc-001",
        "status": "active",
        "activity_limits": ["no_running"],
        "load_limits": {"reduction_pct": 10},
        "source_reference": "health:source:1",
        "authorization_reference": "permission:decision:1",
    }
    assert "diagnosis" not in result["constraint"]
    assert "treatment_plan" not in result["constraint"]
    assert "clinical_notes" not in result["constraint"]
