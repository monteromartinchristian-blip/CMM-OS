"""Final mutation and property contracts for Languages domain rules."""

from __future__ import annotations

import pytest

from cmm.domains.languages.rules import (
    adapt_difficulty,
    align_activity_to_goals,
    classify_language_variety,
    classify_proficiency_record,
    evaluate_certification_source,
    evaluate_cultural_context,
    evaluate_error_pattern,
    evaluate_framework_mapping,
    evaluate_language_memory_consent,
    evaluate_learning_load,
    evaluate_progression,
    plan_spaced_review,
    prioritize_corrections,
    separate_skill_evidence,
)


def test_level_estimate_requires_evidence():
    result = classify_proficiency_record(
        kind="ESTIMATED",
        framework="CEFR",
        level_or_score="C1",
        evidence=(),
    )
    assert result["level_or_score"] == "unassessed"
    assert result["confidence"] == 0.0


@pytest.mark.parametrize("kind", ("CERTIFIED", "ESTIMATED", "OBSERVED_PERFORMANCE"))
def test_level_classification_without_evidence_is_unassessed(kind):
    """Caller labels without usable evidence cannot retain a grounded level."""
    result = classify_proficiency_record(
        kind=kind,
        framework="CEFR",
        level_or_score="C1",
        evidence=(),
    )

    assert result["is_certified"] is False
    assert result["level_or_score"] == "unassessed"
    assert result["confidence"] == 0.0


def test_level_estimate_from_one_grounded_sample_is_unassessed():
    """One session must remain an observation, not a stable estimated level."""
    result = classify_proficiency_record(
        kind="ESTIMATED",
        framework="CEFR",
        level_or_score="C1",
        skill_scope="writing",
        evidence=({"provenance_id": "essay-1", "skill": "writing", "observed": "C1"},),
    )

    assert result["kind"] != "ESTIMATED"
    assert result["level_or_score"] == "unassessed"
    assert result["confidence"] == 0.0


def test_level_estimate_rejects_duplicate_provenance_despite_caller_id_changes():
    """Caller-controlled IDs cannot turn one occurrence into independent evidence."""
    result = classify_proficiency_record(
        kind="ESTIMATED",
        framework="CEFR",
        level_or_score="C1",
        skill_scope="writing",
        evidence=(
            {"id": "caller-a", "provenance_id": "essay-1", "skill": "writing", "observed": "C1"},
            {"id": "caller-b", "provenance_id": "essay-1", "skill": "writing", "observed": "C1"},
        ),
    )

    assert result["kind"] != "ESTIMATED"
    assert result["level_or_score"] == "unassessed"
    assert result["confidence"] == 0.0


def test_level_estimate_requires_two_independent_grounded_evidence_units():
    """Two independently grounded observations may support an estimated level."""
    result = classify_proficiency_record(
        kind="ESTIMATED",
        framework="CEFR",
        level_or_score="C1",
        skill_scope="writing",
        evidence=(
            {"provenance_id": "essay-1", "skill": "writing", "observed": "C1"},
            {"provenance_id": "essay-2", "skill": "writing", "observed": "C1"},
        ),
    )

    assert result["kind"] == "ESTIMATED"
    assert result["level_or_score"] == "C1"
    assert result["confidence"] == 0.75


@pytest.mark.parametrize(
    "level_or_score,evidence",
    (
        (
            "C1",
            (
                {"provenance_id": "reading-1", "skill": "reading", "observed": "C1"},
                {"provenance_id": "reading-2", "skill": "reading", "observed": "C1"},
            ),
        ),
        (
            "C1",
            (
                {"provenance_id": "writing-1", "skill": "writing", "observed": "A1"},
                {"provenance_id": "writing-2", "skill": "writing", "observed": "A1"},
            ),
        ),
        (
            "C1",
            (
                {"provenance_id": "writing-1", "skill": "writing", "observed": "not-a-level"},
                {"provenance_id": "writing-2", "skill": "writing", "observed": "not-a-level"},
            ),
        ),
        (
            0.8,
            (
                {"provenance_id": "writing-1", "skill": "writing", "score": 0.7},
                {"provenance_id": "writing-2", "skill": "writing", "score": 0.7},
            ),
        ),
    ),
)
def test_level_estimate_requires_evidence_relevant_to_scope_and_claim(level_or_score, evidence):
    """Independent provenance cannot compensate for a different skill or claimed value."""
    result = classify_proficiency_record(
        kind="ESTIMATED",
        framework="CEFR",
        level_or_score=level_or_score,
        skill_scope="writing",
        evidence=evidence,
    )

    assert result["kind"] != "ESTIMATED"
    assert result["level_or_score"] == "unassessed"
    assert result["confidence"] == 0.0


def test_level_estimate_accepts_matching_grounded_numeric_scores():
    """A precise score is grounded only by independently matching numeric scores."""
    result = classify_proficiency_record(
        kind="ESTIMATED",
        framework="CEFR",
        level_or_score=0.8,
        skill_scope="writing",
        evidence=(
            {"provenance_id": "writing-1", "skill": "writing", "score": 0.8},
            {"provenance_id": "writing-2", "skill": "writing", "score": 0.8},
        ),
    )

    assert result["kind"] == "ESTIMATED"
    assert result["level_or_score"] == 0.8
    assert result["confidence"] == 0.75


@pytest.mark.parametrize(
    "level_or_score,evidence",
    (
        ("B2", ({"provenance_id": "reading-1", "skill": "reading", "observed": "B2"},)),
        ("B2", ({"provenance_id": "writing-1", "skill": "writing", "observed": "A1"},)),
        ("B2", ({"provenance_id": "writing-1", "skill": "writing", "observed": "not-a-level"},)),
        (0.8, ({"provenance_id": "writing-1", "skill": "writing", "score": 0.7},)),
    ),
)
def test_observed_performance_requires_evidence_relevant_to_scope_and_claim(level_or_score, evidence):
    """A task/session may ground only its own canonical skill and observed value."""
    result = classify_proficiency_record(
        kind="OBSERVED_PERFORMANCE",
        framework="CEFR",
        level_or_score=level_or_score,
        skill_scope="writing",
        evidence=evidence,
    )

    assert result["level_or_score"] == "unassessed"
    assert result["confidence"] == 0.0


def test_observed_performance_requires_grounded_session_evidence():
    """A concrete observed level must be tied to a task or session provenance."""
    result = classify_proficiency_record(
        kind="OBSERVED_PERFORMANCE",
        framework="CEFR",
        level_or_score="B2",
        evidence=({"id": "caller-only", "observed": "B2"},),
    )

    assert result["level_or_score"] == "unassessed"
    assert result["confidence"] == 0.0


def test_certification_level_requires_valid_official_credential_evidence():
    """Only a recognized credential with official provenance can preserve certification."""
    valid = classify_proficiency_record(
        kind="CERTIFIED",
        framework="CEFR",
        level_or_score="C1",
        evidence=(
            {
                "source_kind": "official_certificate",
                "source_id": "cambridge-record-1",
                "certificate_id": "CERT-1",
            },
        ),
    )
    invalid = classify_proficiency_record(
        kind="CERTIFIED",
        framework="CEFR",
        level_or_score="C1",
        evidence=({"source_kind": "official_certificate", "source_id": "unverified-record"},),
    )

    assert valid["kind"] == "CERTIFIED"
    assert valid["level_or_score"] == "C1"
    assert valid["is_certified"] is True
    assert invalid["is_certified"] is False
    assert invalid["level_or_score"] == "unassessed"
    assert invalid["confidence"] == 0.0


def test_certified_record_without_claimed_level_remains_unassessed():
    """Relevance filtering must preserve the existing unassessed level default."""
    result = classify_proficiency_record(
        kind="CERTIFIED",
        framework="CEFR",
        evidence=(
            {
                "source_kind": "official_certificate",
                "source_id": "cambridge-record-1",
                "certificate_id": "CERT-1",
            },
        ),
    )

    assert result["kind"] == "CERTIFIED"
    assert result["level_or_score"] == "unassessed"
    assert result["confidence"] == 0.95


@pytest.mark.parametrize(
    "evidence",
    (
        ({"provenance_id": "essay-1", "skill": "writing", "observed": "C1"},),
        (
            {"id": "caller-a", "provenance_id": "essay-1", "skill": "writing", "observed": "C1"},
            {"id": "caller-b", "provenance_id": "essay-1", "skill": "writing", "observed": "C1"},
        ),
        (
            {"id": "caller-a", "skill": "writing", "observed": "C1"},
            {"id": "caller-b", "skill": "writing", "observed": "C1"},
        ),
        ({"provenance_id": "essay-1", "skill": ["writing"], "observed": "C1"},),
    ),
)
def test_level_estimate_mutations_fail_closed_when_grounding_is_removed(evidence):
    """Removing independence or valid grounded records demotes a previously valid estimate."""
    result = classify_proficiency_record(
        kind="ESTIMATED",
        framework="CEFR",
        level_or_score="C1",
        skill_scope="writing",
        evidence=evidence,
    )

    assert result["kind"] != "ESTIMATED"
    assert result["level_or_score"] == "unassessed"
    assert result["confidence"] == 0.0


def test_framework_mapping_requires_provenance():
    result = evaluate_framework_mapping(
        source_framework="IELTS",
        source_value="6.5",
        target_framework="CEFR",
        mapping_evidence=({"target_range": "B2"},),
    )
    assert result["calibrated"] is False


@pytest.mark.parametrize(
    ("threshold", "observations"),
    [
        (0, ()),
        (
            1,
            (
                {
                    "provenance_id": "p1",
                    "comparison_key": "same",
                    "error_type": "tense",
                    "comparable": True,
                },
            ),
        ),
        (
            True,
            (
                {
                    "provenance_id": "p1",
                    "comparison_key": "same",
                    "error_type": "tense",
                    "comparable": True,
                },
            ),
        ),
        (-1, ()),
    ],
)
def test_error_pattern_canonical_minimum_cannot_be_lowered(threshold, observations):
    result = evaluate_error_pattern(
        observations=observations,
        minimum_independent_occurrences=threshold,
    )
    assert result["eligible"] is False
    assert result["pattern_state"] == "insufficient_evidence"


def test_adaptive_difficulty_ignores_noncomparable_high_scores():
    result = adapt_difficulty(
        current_difficulty=3,
        performance=(
            {
                "provenance_id": "p1",
                "comparison_key": "same",
                "score": 0.95,
                "comparable": False,
            },
            {
                "provenance_id": "p2",
                "comparison_key": "same",
                "score": 0.95,
                "comparable": False,
            },
        ),
    )
    assert result["action"] == "insufficient_evidence"


def test_goal_alignment_rejects_unrelated_activity():
    result = align_activity_to_goals(
        activity={"type": "unrelated_accounting"},
        goals=(
            {"id": "cert", "kind": "certification", "target": "C1"},
            {
                "id": "conv",
                "kind": "conversation",
                "target": "conversation fluency",
            },
        ),
    )
    assert result["activity_fit"] != "aligned"
    assert result["aligned_goals"] == []


@pytest.mark.parametrize("available_time", [float("inf"), float("-inf"), True, -10])
def test_learning_load_invalid_time_fails_closed(available_time):
    result = evaluate_learning_load(available_time=available_time)
    assert result["load_status"] == "insufficient_constraints"
    assert result["recommended_duration_minutes"] == 0


def test_spaced_review_deduplicates_logical_item():
    result = plan_spaced_review(
        items=(
            {"id": "v1", "due": True, "mastery": 0.2},
            {"id": "v1", "due": True, "mastery": 0.2},
        )
    )
    assert len(result["review_queue"]) == 1
    assert result["backlog_count"] == 1
