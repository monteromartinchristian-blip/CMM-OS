"""Tests for Phase 10.28 Sport Domain Safety Boundaries."""

from __future__ import annotations

from cmm.domains.sport.rules import (
    evaluate_health_constraint,
    evaluate_injury_signal,
)


def test_safety_no_medical_diagnosis() -> None:
    res = evaluate_injury_signal(
        pain_score=9, pain_location="shoulder", fatigue_score=9
    )
    assert res["is_diagnosis"] is False
    assert "diagnosis" not in res
    assert res["action"] in ("stop_and_check", "request_health_review", "hold")


def test_safety_no_treatment_modification() -> None:
    health_data = {
        "constraint_id": "const-1",
        "status": "active",
        "treatment_instructions": "change medication X to 20mg",
    }
    res = evaluate_health_constraint(health_data, is_authorized=True, is_current=True)
    assert res.get("treatment_modification_allowed") is not True
    assert "treatment_instructions" not in res.get("applied_fields", ())


def test_safety_denies_unauthorized_health_memory() -> None:
    raw_memory = {
        "health_memory_entry_id": "mem-999",
        "clinical_notes": "Patient diagnosed with asthma",
    }
    res = evaluate_health_constraint(raw_memory, is_authorized=False, is_current=True)
    assert res["applied"] is False
