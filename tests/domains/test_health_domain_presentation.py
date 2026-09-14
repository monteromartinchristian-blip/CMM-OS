"""Tests for Phase 10.20 Health Domain presentation."""

from __future__ import annotations

from cmm.domains import health


def test_presentation_policy_from_profile():
    policy = health.build_health_presentation_policy()
    assert policy.allow_speculation is False
    assert policy.require_disclaimers is True


def test_required_safety_sections():
    policy = health.build_health_presentation_policy()
    required = {
        "documented_information",
        "reported_symptoms",
        "temporal_changes",
        "hypotheses_and_possibilities",
        "contradictions",
        "missing_information",
        "red_flags",
        "questions_for_professional",
        "authorized_next_steps",
    }
    assert set(policy.required_sections) == required


def test_structured_only_output():
    policy = health.build_health_presentation_policy()
    assert policy.allowed_output_types == ("HUMAN_READABLE", "STRUCTURED")
    assert policy.preferred_output_types == ("STRUCTURED",)


def test_protected_terms_cover_uncertainty_and_provenance():
    policy = health.build_health_presentation_policy()
    assert "uncertainty" in policy.protected_terms
    assert "provenance" in policy.protected_terms
    assert "temporal_association" in policy.protected_terms
    assert "definitive" in policy.protected_terms
