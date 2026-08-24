"""Tests for Phase 10.26 Languages Domain Operations and Schema Parity."""

from __future__ import annotations

import json

import cmm.domains.languages.operations as languages_operations
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
from tests.domains._languages_runtime_state import (
    find_languages_runtime_purity_violations,
    snapshot_languages_module_state,
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


def test_track_vocabulary_derives_mastery_for_each_frozen_candidate_state() -> None:
    """Each canonical state yields a bounded, evidence-derived mastery summary."""
    expected_mastered = {
        "new": 0,
        "learning": 0,
        "review": 0,
        "consolidated": 1,
        "needs_reinforcement": 0,
    }

    for state, mastered in expected_mastered.items():
        result = track_vocabulary_result(
            vocabulary_list={"items": [{"id": f"word-{state}", "state": state}]}
        )

        assert result["candidate_updates"] == [
            {"id": f"word-{state}", "state": state}
        ]
        assert result["total_items"] == 1
        assert result["mastery_summary"] == {
            "mastered": mastered,
            "learning": 1 - mastered,
        }
        assert 0 <= result["mastery_summary"]["mastered"] <= result["total_items"]
        assert 0 <= result["mastery_summary"]["learning"] <= result["total_items"]
        assert (
            result["mastery_summary"]["mastered"]
            + result["mastery_summary"]["learning"]
            == result["total_items"]
        )


def test_track_vocabulary_applies_grounded_review_evidence_to_candidate_items() -> None:
    """Reviews update only matching candidates; a lone correct answer remains review."""
    result = track_vocabulary_result(
        vocabulary_list={
            "items": [
                {"id": "correct", "state": "learning"},
                {"item_id": "incorrect", "state": "review"},
                {"id": "explicit", "state": "learning"},
                {"id": "unusable-review", "state": "review"},
            ]
        },
        new_items=[{"id": "new-word", "state": "new"}],
        review_results=[
            {"id": "correct", "correct": True},
            {"item_id": "incorrect", "correct": False},
            {"id": "explicit", "state": "consolidated"},
            {"item_id": "new-word", "state": "learning"},
            {"id": "unusable-review", "state": "not-a-frozen-state"},
        ],
    )

    assert [item["state"] for item in result["candidate_updates"]] == [
        "review",
        "needs_reinforcement",
        "consolidated",
        "review",
        "learning",
    ]
    assert result["total_items"] == 5
    assert result["mastery_summary"] == {"mastered": 1, "learning": 4}
    assert result["persistence_applied"] is False
    assert 0 <= result["mastery_summary"]["mastered"] <= result["total_items"]
    assert 0 <= result["mastery_summary"]["learning"] <= result["total_items"]
    assert (
        result["mastery_summary"]["mastered"]
        + result["mastery_summary"]["learning"]
        == result["total_items"]
    )


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


def test_speaking_review_provenance_without_outcome_is_not_assessed() -> None:
    """Provenance identifies a source but cannot stand in for an assessment finding."""
    unusable_evidence = (
        [{"source_id": "audio-1"}],
        [{"source_id": "audio-1", "finding": "  "}],
        [{"source_id": "audio-1", "score": float("nan")}],
        [{"source_id": "audio-1", "score": float("inf")}],
        [{"source_id": "audio-1", "score": True}],
    )

    for pronunciation_evidence in unusable_evidence:
        result = review_speaking_result(
            audio_transcript={"transcript": "Hello"},
            pronunciation_evidence=pronunciation_evidence,
        )

        assert result["pronunciation_assessed"] is False
        assert result["pronunciation_feedback"] is None
        assert "pronunciation_evidence" in result["missing_evidence"]
        json.dumps(result, allow_nan=False)


def test_speaking_review_uses_only_grounded_pronunciation_outcomes() -> None:
    """A usable finding or finite score plus provenance supports neutral assessment output."""
    cases = (
        (
            [{"source_id": "audio-1", "score": 0.8}],
            "Pronunciation assessment recorded.",
        ),
        (
            [
                {
                    "provenance_id": "audio-2",
                    "finding": "Final consonants need practice.",
                }
            ],
            "Final consonants need practice.",
        ),
    )

    for pronunciation_evidence, expected_feedback in cases:
        result = review_speaking_result(
            audio_transcript={"transcript": "Hello"},
            pronunciation_evidence=pronunciation_evidence,
        )

        assert result["pronunciation_assessed"] is True
        assert result["pronunciation_feedback"] == expected_feedback
        assert "pronunciation_evidence" not in result["missing_evidence"]


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
    assert result["skill_progress"] == {"writing": "stable_improvement"}
    assert result["progression_evidence_valid"] is True
    assert result["cross_skill_inflation"] is False


def test_progress_review_without_evidence_has_no_positive_payload() -> None:
    result = generate_progress_review_result(
        language="English",
        period="last_30_days",
    )

    assert result["overall_progression"] == "insufficient_evidence"
    assert result["stable_progression"] is False
    assert result["skill_progress"] == {}
    assert result["active_patterns_count"] == 0
    assert result["certification_readiness"] == "not_assessed"
    assert result["recommended_next_focus"] == "not_assessed"
    assert result["progression_evidence_valid"] is True
    assert result["cross_skill_inflation"] is False


def test_progress_review_only_projects_evidenced_skills_and_state() -> None:
    result = generate_progress_review_result(
        language="English",
        period="last_30_days",
        previous_evidence=(
            {
                "provenance_id": "baseline-writing",
                "score": 0.6,
                "skill": "writing",
                "comparable": True,
                "comparison_key": "essay",
            },
        ),
        evidence=(
            {
                "provenance_id": "current-writing-1",
                "score": 0.85,
                "skill": "writing",
                "comparable": True,
                "comparison_key": "essay",
            },
            {
                "provenance_id": "current-writing-2",
                "score": 0.88,
                "skill": "writing",
                "comparable": True,
                "comparison_key": "essay",
            },
        ),
        skill="writing",
        patterns=({"error_type": "inversion", "eligible": True},),
        certification_profile={"readiness_score": 0.7},
        goals=({"id": "goal-c1", "target": "C1 writing"},),
    )

    assert result["skill_progress"] == {"writing": "stable_improvement"}
    assert "reading" not in result["skill_progress"]
    assert result["active_patterns_count"] == 1
    assert result["certification_readiness"] == "in_progress"
    assert result["recommended_next_focus"] == "inversion"
    assert set(result["skill_progress"]) <= {"writing"}
    assert result["cross_skill_inflation"] is False


def test_progress_review_non_finite_readiness_is_not_assessed() -> None:
    """Catches non-finite profile data being promoted to certification readiness."""
    for readiness_score in (float("nan"), float("inf"), float("-inf")):
        result = generate_progress_review_result(
            language="English",
            period="last_30_days",
            certification_profile={"readiness_score": readiness_score},
        )

        assert result["certification_readiness"] == "not_assessed"
        json.dumps(result, allow_nan=False)


def test_progress_review_multiple_skills_uses_only_each_skills_evidence() -> None:
    previous = (
        {"provenance_id": "w0", "score": 0.5, "skill": "writing", "comparable": True, "comparison_key": "essay"},
        {"provenance_id": "r0", "score": 0.55, "skill": "reading", "comparable": True, "comparison_key": "reading-test"},
    )
    current = (
        {"provenance_id": "w1", "score": 0.8, "skill": "writing", "comparable": True, "comparison_key": "essay"},
        {"provenance_id": "w2", "score": 0.82, "skill": "writing", "comparable": True, "comparison_key": "essay"},
        {"provenance_id": "r1", "score": 0.78, "skill": "reading", "comparable": True, "comparison_key": "reading-test"},
        {"provenance_id": "r2", "score": 0.8, "skill": "reading", "comparable": True, "comparison_key": "reading-test"},
    )

    result = generate_progress_review_result(
        language="English",
        period="month",
        previous_evidence=previous,
        evidence=current,
    )

    assert result["skill_progress"] == {
        "reading": "stable_improvement",
        "writing": "stable_improvement",
    }
    assert result["overall_progression"] == "stable_improvement"
    assert result["stable_progression"] is True
    assert result["progression_evidence_valid"] is True


def test_certification_preparation_no_external_mutation() -> None:
    """Verify prepare_certification output guarantees no registration/payment/submission performed."""
    res = prepare_certification_result(
        target_certification="Cambridge C1",
    )
    assert res["registration_performed"] is False
    assert res["payment_performed"] is False
    assert res["submission_performed"] is False


def test_review_exercise_malformed_scores_without_correctness_remain_unassessed() -> None:
    malformed_scores = (
        float("nan"),
        float("inf"),
        float("-inf"),
        True,
        False,
        "not-a-number",
        {},
        [],
        None,
    )

    for malformed_score in malformed_scores:
        result = review_exercise_result(
            exercise_result={
                "score": malformed_score,
                "user_answer": "unsupported",
            }
        )

        assert result["score"] is None
        assert result["is_correct"] is None
        assert result["observed_errors"] == []
        assert result["feedback"] == "Not assessed: missing exercise outcome."
        assert result["difficulty_adjustment"] == "hold"
        assert result["stable_proficiency_changed"] is False
        json.dumps(result, allow_nan=False)


def test_review_exercise_correctness_evidence_survives_malformed_score() -> None:
    """Catches malformed score data overriding an observed boolean outcome."""
    for malformed_score in (float("nan"), float("inf"), float("-inf"), True, "bad"):
        result = review_exercise_result(
            exercise_result={"is_correct": True, "score": malformed_score}
        )

        assert result["is_correct"] is True
        assert result["score"] == 1.0
        assert result["observed_errors"] == []
        assert result["feedback"] == "Great job!"
        assert result["difficulty_adjustment"] == "maintain"
        json.dumps(result, allow_nan=False)


def test_review_exercise_missing_outcome_remains_unassessed() -> None:
    """Catches a positive default when no exercise outcome was supplied."""
    result = review_exercise_result(exercise_result={})

    assert result["is_correct"] is None
    assert result["score"] is None
    assert result["observed_errors"] == []
    assert result["feedback"] == "Not assessed: missing exercise outcome."
    assert result["difficulty_adjustment"] == "hold"


def test_review_exercise_preserves_each_kind_of_observed_outcome() -> None:
    """Catches deriving correctness from score or discarding valid outcome evidence."""
    cases = (
        ({"is_correct": True}, True, 1.0, 0, "Great job!", "maintain"),
        ({"is_correct": False}, False, 0.0, 1, "Review the target structure.", "scaffold"),
        ({"score": 0.8}, None, 0.8, 0, "Not assessed: missing exercise outcome.", "hold"),
        ({"is_correct": False, "score": 0.2}, False, 0.2, 1, "Review the target structure.", "scaffold"),
    )

    for exercise_result, correct, score, error_count, feedback, difficulty in cases:
        result = review_exercise_result(exercise_result=exercise_result)

        assert result["is_correct"] is correct
        assert result["score"] == score
        assert len(result["observed_errors"]) == error_count
        assert result["feedback"] == feedback
        assert result["difficulty_adjustment"] == difficulty
        json.dumps(result, allow_nan=False)


def test_review_exercise_unassessed_container_inputs_remain_json_safe() -> None:
    """Catches coercing absent or non-mapping exercise outcomes into success."""
    for exercise_result in ({}, [], None):
        result = review_exercise_result(exercise_result=exercise_result)

        assert result["is_correct"] is None
        assert result["score"] is None
        assert result["observed_errors"] == []
        json.dumps(result, allow_nan=False)


def test_review_exercise_unassessed_output_matches_its_declared_schema() -> None:
    """Catches a nullable outcome rejected by the public operation schema."""
    definitions = {
        definition.operation_id: definition
        for definition in build_languages_operation_definitions()
    }
    definition = definitions["languages.review_exercise"]
    result = review_exercise_result(exercise_result={})
    assert result["is_correct"] is None
    assert result["score"] is None
    assert validate_operation_schema(
        result, definition.output_schema
    ) == ()


def test_other_numeric_operation_inputs_use_the_same_fail_closed_boundary() -> None:
    exercises = generate_exercises_result(
        language="English",
        skill="grammar",
        difficulty=float("inf"),
        target_topic="inversion",
        count="not-a-count",
    )
    schedule = plan_review_schedule_result(
        review_items=(),
        available_time=float("inf"),
    )

    assert exercises["difficulty"] == 1
    assert exercises["exercise_count"] == 3
    assert schedule["recommended_duration_minutes"] == 30
    json.dumps(exercises, allow_nan=False)
    json.dumps(schedule, allow_nan=False)


def test_plan_review_schedule_no_calendar_mutation() -> None:
    """Observe runtime purity independently of the helper's returned flags."""
    dependency_violations = find_languages_runtime_purity_violations(
        plan_review_schedule_result
    )
    before = snapshot_languages_module_state(languages_operations)
    res = plan_review_schedule_result(
        review_items=[{"id": "v1", "due": True}],
    )
    after = snapshot_languages_module_state(languages_operations)

    assert dependency_violations == ()
    assert after == before
    assert res["calendar_modified"] is False
    assert res["external_action_executed"] is False


def test_empty_assessment_fails_closed_without_proficiency_judgment() -> None:
    result = assess_sample_result(sample={})

    assert result["observed_performance"] == "unknown"
    assert result["confidence"] == 0.0
    assert result["strengths"] == []
    assert result["missing_evidence"] == ["writing_sample"]


def test_empty_writing_review_contains_no_unsupported_judgment() -> None:
    result = review_writing_result(writing_sample={})

    assert result["word_count"] == 0
    assert result["estimated_level"] == "unknown"
    assert result["score"] == 0.0
    assert result["strengths"] == []
    assert result["register_feedback"] == "not_assessed"
    assert result["missing_evidence"] == ["writing_sample"]
    assert result["proficiency_upgraded_without_evidence"] is False


def test_empty_speaking_review_contains_no_fluency_judgment() -> None:
    result = review_speaking_result(audio_transcript={})

    assert result["transcript_text"] == ""
    assert result["fluency_score"] == 0.0
    assert result["pronunciation_assessed"] is False
    assert result["missing_evidence"] == [
        "speaking_sample",
        "pronunciation_evidence",
    ]


def test_empty_error_review_has_no_evidence_derived_focus() -> None:
    """Catches a targeted correction being inferred from zero observed errors."""
    result = review_errors_result(observed_errors=())

    assert result["total_errors"] == 0
    assert result["error_patterns"] == []
    assert result["prioritized_corrections"] == []
    assert result["recommended_focus"] == "not_assessed"


def test_certification_readiness_derives_from_current_profile() -> None:
    missing = prepare_certification_result(target_certification="Cambridge C1")
    grounded = prepare_certification_result(
        target_certification="Cambridge C1",
        current_profile={
            "skill_levels": {
                "writing": "B2",
                "speaking": "B1",
            },
        },
    )

    assert missing["readiness_score"] == 0.0
    assert missing["skill_gaps"] == []
    assert missing["missing_evidence"] == ["current_profile"]
    assert missing["needs_verification"] is True
    assert grounded["readiness_score"] == 0.7
    assert grounded["skill_gaps"] == ["writing:B2->C1", "speaking:B1->C1"]
    assert grounded["missing_evidence"] == []


def test_certification_source_status_requires_current_authoritative_source() -> None:
    """A truthy stale, unknown, guide, or malformed source cannot be verified."""
    unverified_sources = (
        {"source_type": "official", "date_valid": False},
        {"source_type": "official"},
        {"source_type": "guide"},
        {"date_valid": True},
    )

    for official_source in unverified_sources:
        result = prepare_certification_result(
            target_certification="Cambridge C1",
            current_profile={"estimated_level": "B2"},
            official_source=official_source,
        )

        assert result["official_source_status"] == "needs_verification"
        assert result["needs_verification"] is True


def test_certification_source_status_accepts_current_authoritative_sources() -> None:
    """Preserve the existing evaluator's current authoritative source boundary."""
    authoritative_sources = (
        {"source_type": "official", "date_valid": True},
        {"source_type": "authoritative_secondary", "temporal_state": "current"},
    )

    for official_source in authoritative_sources:
        result = prepare_certification_result(
            target_certification="Cambridge C1",
            current_profile={"estimated_level": "B2"},
            official_source=official_source,
        )

        assert result["official_source_status"] == "verified"
        assert result["needs_verification"] is False
