"""Tests for Phase 10.26 Languages Domain Operations and Schema Parity."""

from __future__ import annotations

from cmm.agent_runtime.enums import PolicyRiskLevel
from cmm.agent_runtime.operation_schema import validate_operation_schema
from cmm.domains.languages.catalog import (
    CANONICAL_LANGUAGES_OPERATION_IDS,
)
from cmm.domains.languages.operations import (
    assess_sample_result,
    build_languages_operation_definitions,
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


def _representative_helper_output(operation_id: str) -> dict:
    """Produce representative valid helper output for each operation ID."""
    if operation_id == "languages.assess_sample":
        return assess_sample_result(
            sample={"text": "I like reading books."},
            sample_type="writing",
            target_language="English",
            skill_scope="writing",
        )
    elif operation_id == "languages.update_level_evidence":
        return update_level_evidence_result(
            existing_record={"kind": "ESTIMATED", "level_or_score": "B1", "skill_scope": "writing"},
            assessment={"observed": "B2", "skill": "writing"},
            target_skill="writing",
        )
    elif operation_id == "languages.create_learning_plan":
        return create_learning_plan_result(
            language="English",
            goals=[{"id": "g1", "target": "B2"}],
            tracking_consent=True,
        )
    elif operation_id == "languages.generate_lesson":
        return generate_lesson_result(
            language="English",
            target_skill="writing",
            current_level="B1",
            topic="Opinion Essays",
        )
    elif operation_id == "languages.generate_exercises":
        return generate_exercises_result(
            language="English",
            skill="grammar",
            difficulty=2,
            target_topic="Past Tense",
        )
    elif operation_id == "languages.review_exercise":
        return review_exercise_result(
            exercise_result={"exercise_id": "ex1", "user_answer": "went", "is_correct": True},
            language="English",
        )
    elif operation_id == "languages.review_writing":
        return review_writing_result(
            writing_sample={"text": "This is an essay with colour."},
            language="English",
            preferred_variety="British English",
        )
    elif operation_id == "languages.generate_conversation_turn":
        return generate_conversation_turn_result(
            conversation={"turns": []},
            language="English",
            topic="Travel",
        )
    elif operation_id == "languages.generate_roleplay_turn":
        return generate_roleplay_turn_result(
            conversation={"turns": []},
            language="English",
            scenario="Restaurant order",
        )
    elif operation_id == "languages.review_speaking":
        return review_speaking_result(
            audio_transcript={"transcript": "Hello, how are you?"},
            target_language="English",
        )
    elif operation_id == "languages.review_errors":
        return review_errors_result(
            observed_errors=[{"id": "e1", "category": "minor_style"}],
            language="English",
        )
    elif operation_id == "languages.track_vocabulary":
        return track_vocabulary_result(
            vocabulary_list={"items": [{"id": "v1", "term": "ubiquitous"}]},
            language="English",
        )
    elif operation_id == "languages.plan_review_schedule":
        return plan_review_schedule_result(
            review_items=[{"id": "v1", "due": True}],
            available_time=20,
        )
    elif operation_id == "languages.prepare_certification":
        return prepare_certification_result(
            target_certification="Cambridge C1",
            current_profile={"estimated_level": "B2"},
        )
    elif operation_id == "languages.generate_progress_review":
        return generate_progress_review_result(
            language="English",
            period="last_30_days",
        )
    raise ValueError(f"Unknown operation ID: {operation_id}")


def test_build_languages_operation_definitions_count_and_types() -> None:
    """Verify exact 15 operations, domain, low risk, and types."""
    operations = build_languages_operation_definitions()
    assert len(operations) == 15
    assert tuple(op.operation_id for op in operations) == CANONICAL_LANGUAGES_OPERATION_IDS

    for op in operations:
        assert str(op.domain_id) == "domain:languages"
        assert op.version == "1.0.0"
        assert op.risk_level is PolicyRiskLevel.LOW
        assert op.metadata.get("phase") == "10.26"
        assert op.metadata.get("proposal_only", False) is True or op.metadata.get("no_external_mutation", False) is True


def test_languages_operation_required_resources() -> None:
    """Verify strict AND required resources for each operation."""
    operations = {op.operation_id: op for op in build_languages_operation_definitions()}

    assert operations["languages.assess_sample"].required_resources == ()
    assert operations["languages.update_level_evidence"].required_resources == ()
    assert operations["languages.create_learning_plan"].required_resources == ()
    assert operations["languages.review_exercise"].required_resources == ("languages.exercise_result",)
    assert operations["languages.review_writing"].required_resources == ("languages.writing_sample",)
    assert operations["languages.generate_conversation_turn"].required_resources == ("languages.conversation",)
    assert operations["languages.generate_roleplay_turn"].required_resources == ("languages.conversation",)
    assert operations["languages.track_vocabulary"].required_resources == ("languages.vocabulary_list",)
    assert operations["languages.review_speaking"].required_resources == ()


def test_languages_operation_schema_parity() -> None:
    """Verify that every helper output passes real validate_operation_schema against its declared output_schema."""
    for op in build_languages_operation_definitions():
        output = _representative_helper_output(op.operation_id)
        errors = validate_operation_schema(output, op.output_schema)
        assert errors == (), f"Operation {op.operation_id} output schema validation failed: {errors}"


def test_onboarding_learning_plan_fields() -> None:
    """Verify create_learning_plan emits tracking_choice, tracking_choice_resolved, memory_proposal_required, persistence_applied."""
    res = create_learning_plan_result(
        language="English",
        goals=[{"id": "g1", "target": "B2"}],
        tracking_consent=True,
    )
    assert res["tracking_choice"] == "opt_in"
    assert res["tracking_choice_resolved"] is True
    assert res["memory_proposal_required"] is True
    assert res["persistence_applied"] is False


def test_update_level_operation_uses_canonical_evidence_semantics() -> None:
    """Operation aliases cannot bypass canonical provenance/comparability checks."""
    result = update_level_evidence_result(
        existing_record={"kind": "ESTIMATED", "level_or_score": "B1", "skill_scope": "writing"},
        assessment={
            "id": "caller-a",
            "provenance_id": "sample-1",
            "observed": "B2",
            "skill": "writing",
            "comparable": True,
            "comparison_key": "writing-argumentative",
        },
        target_skill="writing",
        evidence=(
            {
                "id": "caller-b",
                "provenance_id": "sample-1",
                "observed": "B2",
                "skill": "writing",
                "comparable": True,
                "comparison_key": "writing-argumentative",
            },
        ),
    )

    assert result["stable_update_supported"] is False
    assert result["reason"] == "insufficient_comparable_evidence"
    assert result["certificate_overwritten"] is False
    assert result["skill_gaps_erased"] is False
    assert result["evidence_boundary_valid"] is True


def test_speaking_review_transcript_no_pronunciation() -> None:
    """Verify review_speaking without audio evidence has pronunciation_assessed=False."""
    res = review_speaking_result(
        audio_transcript={"transcript": "Hello"},
        target_language="English",
    )
    assert res["pronunciation_assessed"] is False
    assert res["pronunciation_evidence_valid"] is True
    assert res["pronunciation_inferred_from_transcript_only"] is False


def test_operation_outputs_expose_workflow_invariants() -> None:
    """Variable pedagogical outcomes expose invariant boundary fields separately."""
    wrong = review_exercise_result(
        exercise_result={"user_answer": "go", "is_correct": False},
        language="English",
    )
    assert wrong["stable_proficiency_changed"] is False
    assert wrong["error_pattern_promoted_without_evidence"] is False

    writing = review_writing_result(
        writing_sample={"text": "Short text."},
        language="English",
    )
    assert writing["estimated_level"] == "A2"
    assert writing["valid_variety_misclassified"] is False
    assert writing["proficiency_upgraded_without_evidence"] is False

    errors = review_errors_result(
        observed_errors=(
            {"context_id": "one", "error_type": "inversion", "comparable": True, "comparison_key": "free-writing"},
            {"context_id": "two", "error_type": "inversion", "comparable": True, "comparison_key": "free-writing"},
        ),
        language="English",
    )
    assert errors["error_patterns"]
    assert errors["pattern_evidence_valid"] is True
    assert errors["pattern_promoted_without_independent_recurrence"] is False

    certification = prepare_certification_result(
        target_certification="Cambridge C1",
        official_source={"source_type": "official", "date_valid": False},
    )
    assert certification["needs_verification"] is True
    assert certification["temporal_evidence_valid"] is True
    assert certification["readiness_promoted_to_proficiency"] is False


def test_progress_review_exposes_valid_stable_progression_invariant() -> None:
    """A justified stable outcome remains separate from its evidence invariant."""
    result = generate_progress_review_result(
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
    )

    assert result["stable_progression"] is True
    assert result["progression_evidence_valid"] is True
    assert result["cross_skill_inflation"] is False


def test_certification_preparation_no_external_mutation() -> None:
    """Verify prepare_certification output guarantees no registration/payment/submission performed."""
    res = prepare_certification_result(
        target_certification="Cambridge C1",
    )
    assert res["registration_performed"] is False
    assert res["payment_performed"] is False
    assert res["submission_performed"] is False


def test_plan_review_schedule_no_calendar_mutation() -> None:
    """Verify plan_review_schedule outputs calendar_modified=False and external_action_executed=False."""
    res = plan_review_schedule_result(
        review_items=[{"id": "v1", "due": True}],
    )
    assert res["calendar_modified"] is False
    assert res["external_action_executed"] is False
