"""Tests for Phase 10.28 Sport Domain Presentation."""

from __future__ import annotations

from cmm.domains.sport.presentation import (
    build_sport_presentation_policy,
    present_sport_result,
)


def test_sport_presentation_policy_from_profile() -> None:
    policy = build_sport_presentation_policy()
    assert policy.detail_level == "detailed"
    assert policy.include_uncertainty is True
    assert "training_load" in policy.protected_terms


def test_present_sport_result_preserves_semantics() -> None:
    raw_result = {
        "status": "evaluated",
        "readiness_state": "limited",
        "injury_signal_action": "reduce_load",
        "health_constraint": {"status": "active", "activity_limits": ["no_sprinting"]},
    }
    presented = present_sport_result(raw_result)
    assert presented["domain_display_name"] == "Sport"
    assert presented["uncertainty_preserved"] is True
    assert presented["is_diagnosis"] is False
    assert presented["presentation_format"] == "standard_sport"
