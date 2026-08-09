"""Tests for Phase 10.22 University Domain presentation policy."""

from __future__ import annotations

from cmm.domains import university


def test_presentation_policy_from_profile():
    policy = university.build_university_presentation_policy()
    assert policy.allow_speculation is False
    assert policy.require_disclaimers is True
    assert policy.include_provenance is True
    assert policy.include_uncertainty is True


def test_epistemic_safety_sections():
    policy = university.build_university_presentation_policy()
    required = {
        "facts",
        "source_authority",
        "interpretations",
        "hypotheses",
        "contradictions",
        "open_questions",
        "planning_proposals",
        "possible_actions",
    }
    assert set(policy.required_sections) == required


def test_structured_only_output():
    policy = university.build_university_presentation_policy()
    assert policy.allowed_output_types == ("HUMAN_READABLE", "STRUCTURED")
    assert policy.preferred_output_types == ("STRUCTURED",)
    assert policy.preferred_views == ("structured",)


def test_protected_terms_cover_epistemic_uncertainty_and_provenance():
    policy = university.build_university_presentation_policy()
    assert "uncertainty" in policy.protected_terms
    assert "provenance" in policy.protected_terms
    assert "source_authority" in policy.protected_terms
    assert "interpretation" in policy.protected_terms
    assert "hypothesis" in policy.protected_terms
    assert "contradiction" in policy.protected_terms
    assert "academic_state" in policy.protected_terms
    assert "personal_memory" in policy.protected_terms
    assert "performance_not_capacity" in policy.protected_terms
    assert "planning_proposal" in policy.protected_terms
    assert "open_question" in policy.protected_terms