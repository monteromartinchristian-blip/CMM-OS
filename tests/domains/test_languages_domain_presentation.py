"""Tests for Phase 10.26 Languages Domain Presentation."""

from __future__ import annotations

from cmm.domains.languages.presentation import (
    build_languages_presentation_policy,
    present_languages_result,
)


def test_build_languages_presentation_policy() -> None:
    """Verify presentation policy matches LanguageLearningProfile."""
    policy = build_languages_presentation_policy()
    assert policy is not None
    assert policy.include_provenance is True
    assert policy.include_alternatives is True
    assert policy.include_uncertainty is True


def test_present_languages_result_epistemic_separation() -> None:
    """Presentation must preserve certified vs estimated vs observed distinction."""
    res = {
        "assessment_id": "as-1",
        "language": "English",
        "skill_scope": "writing",
        "observed_performance": "B2",
        "certified_level": "B1",
        "estimated_level": "B1+",
        "valid_alternatives": [{"token": "colour", "variety": "British English"}],
        "errors": [{"id": "err-1", "category": "concord"}],
    }
    presented = present_languages_result(res)
    assert presented["observed_performance"] == "B2"
    assert presented["certified_level"] == "B1"
    assert presented["estimated_level"] == "B1+"
    assert len(presented["valid_alternatives"]) == 1
    assert len(presented["errors"]) == 1
    assert presented["variety_distinction_preserved"] is True


def test_present_languages_result_speaking_without_audio() -> None:
    """Transcript without pronunciation audio evidence clearly indicates pronunciation unassessed."""
    res = {
        "review_id": "sr-1",
        "transcript_text": "Good morning",
        "pronunciation_assessed": False,
    }
    presented = present_languages_result(res)
    assert presented["pronunciation_assessed"] is False
    assert presented["pronunciation_badge"] == "Audio evidence not provided"
