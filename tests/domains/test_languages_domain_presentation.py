"""Tests for Phase 10.26 Languages Domain Presentation."""

from __future__ import annotations

import json

from cmm.domains.languages.operations import (
    assess_sample_result,
    create_learning_plan_result,
    generate_conversation_turn_result,
    generate_exercises_result,
    generate_lesson_result,
    generate_progress_review_result,
    generate_roleplay_turn_result,
    plan_review_schedule_result,
    prepare_certification_result,
    review_errors_result,
    review_exercise_result,
    review_speaking_result,
    review_writing_result,
    track_vocabulary_result,
    update_level_evidence_result,
)
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


def _actual_operation_outputs() -> dict[str, dict]:
    comparable = {
        "skill": "writing",
        "comparable": True,
        "comparison_key": "essay",
        "observed": "B2",
    }
    return {
        "assess_sample": assess_sample_result(
            sample={"text": "A sufficiently developed observed writing sample."},
            skill_scope="writing",
        ),
        "update_level": update_level_evidence_result(
            existing_record={
                "kind": "CERTIFIED",
                "level_or_score": "B1",
                "skill_scope": "writing",
            },
            assessment={**comparable, "provenance_id": "assessment-1"},
            target_skill="writing",
            evidence=({**comparable, "provenance_id": "assessment-2"},),
        ),
        "learning_plan": create_learning_plan_result(
            language="English", goals=({"target": "C1"},), tracking_consent=True
        ),
        "lesson": generate_lesson_result(
            language="English", target_skill="writing", current_level="B1",
            topic="argumentative essays",
        ),
        "exercises": generate_exercises_result(
            language="English", skill="grammar", difficulty=2,
            target_topic="inversion",
        ),
        "exercise_review": review_exercise_result(
            exercise_result={"is_correct": False, "user_answer": "I never saw"}
        ),
        "writing_review": review_writing_result(
            writing_sample={"text": "My favourite colour is blue."},
            preferred_variety="British English",
        ),
        "conversation": generate_conversation_turn_result(
            conversation={"turns": ()}, topic="travel", target_level="B2"
        ),
        "roleplay": generate_roleplay_turn_result(
            conversation={"turns": ()}, scenario="job interview"
        ),
        "speaking_review": review_speaking_result(
            audio_transcript={"transcript": "Good morning"}
        ),
        "error_review": review_errors_result(
            observed_errors=(
                {"provenance_id": "error-1", "error_type": "inversion"},
            )
        ),
        "vocabulary": track_vocabulary_result(
            vocabulary_list={"items": ({"id": "word-1", "due": True},)}
        ),
        "schedule": plan_review_schedule_result(
            review_items=({"id": "word-1", "due": True},), available_time=20
        ),
        "certification": prepare_certification_result(
            target_certification="Cambridge C1",
            official_source={"source_type": "official", "date_valid": False},
        ),
        "progress": generate_progress_review_result(
            language="English",
            period="last_30_days",
            previous_evidence=(
                {"provenance_id": "baseline", "score": 0.6, "skill": "writing", "comparable": True, "comparison_key": "essay"},
            ),
            evidence=(
                {"provenance_id": "current-1", "score": 0.85, "skill": "writing", "comparable": True, "comparison_key": "essay"},
                {"provenance_id": "current-2", "score": 0.88, "skill": "writing", "comparable": True, "comparison_key": "essay"},
            ),
            skill="writing",
        ),
    }


def test_all_actual_operation_outputs_preserve_epistemic_boundaries() -> None:
    actual = _actual_operation_outputs()
    assert len(actual) == 15
    presented = {
        name: present_languages_result(output) for name, output in actual.items()
    }
    for output in presented.values():
        json.dumps(output, allow_nan=False)

    assert presented["assess_sample"]["proficiency_kind"] == "OBSERVED_PERFORMANCE"
    assert presented["update_level"]["is_certified"] is True
    assert presented["update_level"]["certificate_overwritten"] is False
    assert presented["writing_review"]["valid_alternatives"][0]["status"] == "valid_alternative"
    assert presented["speaking_review"]["pronunciation_assessed"] is False
    assert presented["speaking_review"]["pronunciation_inferred_from_transcript_only"] is False
    assert presented["error_review"]["error_patterns"] == []
    assert presented["schedule"]["calendar_modified"] is False
    assert presented["schedule"]["external_action_executed"] is False
    assert presented["certification"]["needs_verification"] is True
    assert presented["progress"]["stable_progression"] is True
    assert presented["vocabulary"]["persistence_applied"] is False
    assert presented["learning_plan"]["memory_proposal_required"] is True
    assert presented["learning_plan"]["persistence_applied"] is False
