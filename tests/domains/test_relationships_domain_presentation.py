"""Tests for Phase 10.21 Relationships Domain presentation."""

from __future__ import annotations

from cmm.domains import relationships


def test_presentation_policy_from_profile():
    policy = relationships.build_relationships_presentation_policy()
    assert policy.allow_speculation is False
    assert policy.require_disclaimers is True


def test_epistemic_safety_sections():
    policy = relationships.build_relationships_presentation_policy()
    required = {
        "facts",
        "statements",
        "emotions",
        "needs",
        "interpretations",
        "hypotheses",
        "patterns",
        "contradictions",
        "open_questions",
        "possible_actions",
    }
    assert set(policy.required_sections) == required


def test_structured_only_output():
    policy = relationships.build_relationships_presentation_policy()
    assert policy.allowed_output_types == ("HUMAN_READABLE", "STRUCTURED")
    assert policy.preferred_output_types == ("STRUCTURED",)


def test_protected_terms_cover_epistemic_uncertainty_and_provenance():
    policy = relationships.build_relationships_presentation_policy()
    assert "uncertainty" in policy.protected_terms
    assert "provenance" in policy.protected_terms
    assert "observed_fact" in policy.protected_terms
    assert "interpretation" in policy.protected_terms
    assert "hypothesis" in policy.protected_terms
    assert "ambivalence" in policy.protected_terms
    assert "contradiction" in policy.protected_terms
    assert "unknown" in policy.protected_terms
