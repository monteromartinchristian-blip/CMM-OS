"""Tests for Phase 10.28 Sport Domain Profile."""

from __future__ import annotations

from cmm.domains.sport.profile import (
    SPORT_PROFILE_ID,
    SPORT_PROFILE_NAME,
    build_sport_profile,
)


def test_sport_profile_identity_and_contracts() -> None:
    profile = build_sport_profile()
    assert profile.id == SPORT_PROFILE_ID
    assert profile.domain_id == "domain:sport"
    assert profile.profile_name == SPORT_PROFILE_NAME
    assert profile.minimum_confidence == 0.7


def test_sport_profile_prohibited_inferences_and_actions() -> None:
    profile = build_sport_profile()
    assert "clinical_injury_diagnosis" in profile.prohibited_inferences
    assert "medical_treatment_modification" in profile.prohibited_inferences
    assert "high_risk_medical_recommendation" in profile.prohibited_inferences

    assert "direct_memory_write" in profile.prohibited_actions
    assert "clinical_diagnosis" in profile.prohibited_actions
    assert "treatment_modification" in profile.prohibited_actions
    assert "direct_calendar_mutation" in profile.prohibited_actions


def test_sport_profile_memory_policy() -> None:
    profile = build_sport_profile()
    assert profile.memory_policy.allow_read is True
    assert profile.memory_policy.allow_write is not True
    assert profile.memory_policy.allow_cross_domain is False
