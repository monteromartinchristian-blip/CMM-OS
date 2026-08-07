"""Tests for General Domain presentation."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from cmm.domains.general import build_general_presentation_policy


def test_presentation_policy_built():
    policy = build_general_presentation_policy()
    assert policy is not None


def test_required_sections():
    policy = build_general_presentation_policy()
    assert "summary" in policy.required_sections
    assert "facts" in policy.required_sections
    assert "inferences" in policy.required_sections
    assert "hypotheses" in policy.required_sections
    assert "sources" in policy.required_sections
    assert "confidence" in policy.required_sections
    assert "contradictions" in policy.required_sections
    assert "gaps" in policy.required_sections
    assert "questions" in policy.required_sections


def test_uncertainty_visible():
    policy = build_general_presentation_policy()
    assert policy.include_uncertainty is True


def test_provenance_visible():
    policy = build_general_presentation_policy()
    assert policy.include_provenance is True


def test_contradictions_visible():
    policy = build_general_presentation_policy()
    assert "contradictions" in policy.required_sections


def test_terminology_protected():
    policy = build_general_presentation_policy()
    assert "fact" in policy.protected_terms
    assert "inference" in policy.protected_terms
    assert "hypothesis" in policy.protected_terms
    assert "uncertainty" in policy.protected_terms


def test_no_speculation():
    policy = build_general_presentation_policy()
    assert policy.allow_speculation is False


def test_warning_position():
    policy = build_general_presentation_policy()
    assert policy.warning_position == "before_content"


def test_deterministic():
    a = build_general_presentation_policy()
    b = build_general_presentation_policy()
    assert a.to_dict() == b.to_dict()


def test_no_mutation():
    policy = build_general_presentation_policy()
    before = policy.to_dict()
    # Attempt to mutate
    with pytest.raises(FrozenInstanceError):
        policy.include_uncertainty = False  # type: ignore[misc]
    assert policy.to_dict() == before
