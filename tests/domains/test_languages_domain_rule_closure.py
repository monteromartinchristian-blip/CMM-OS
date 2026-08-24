"""Final mutation and property contracts for Languages domain rules."""

from __future__ import annotations

import json
from copy import deepcopy

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


@pytest.mark.parametrize(
    ("preferred_variety", "observed_variety"),
    (
        ("American English", "British English"),
        ("British English", "American English"),
        ("Mexican Spanish", "Peninsular Spanish"),
    ),
)
def test_language_variety_known_alternative_is_not_an_error(
    preferred_variety,
    observed_variety,
):
    """A recognized alternative remains valid even when it is not preferred."""
    result = classify_language_variety(
        preferred_variety=preferred_variety,
        observed_variety=observed_variety,
        assessment_standard="General English",
        form_status="valid",
    )

    assert result["classification"] == "valid_alternative"
    assert result["error"] is False
    assert result["error_rejected"] is True
    assert result["is_valid_alternative"] is True


def test_language_variety_preferred_form_remains_preferred_without_excluding_alternatives():
    """The preferred form is preferred, not an exclusive correctness source."""
    preferred = classify_language_variety(
        preferred_variety="American English",
        observed_variety="American English",
        form_status="valid",
    )
    alternative = classify_language_variety(
        preferred_variety="American English",
        observed_variety="British English",
        form_status="valid",
    )

    assert preferred["classification"] == "preferred"
    assert preferred["error"] is False
    assert alternative["classification"] == "valid_alternative"
    assert alternative["error"] is False


@pytest.mark.parametrize(
    ("preferred_variety", "observed_variety"),
    (
        ("American English", "Fictional Variety 99"),
        ("American English", "Fictional American English"),
        ("Fictional Variety 99", "British English"),
        ("Fictional Variety 99", "Fictional Variety 99"),
        ("Fictional Preferred", "Fictional Observed"),
    ),
)
def test_language_variety_unknown_caller_strings_fail_closed(
    preferred_variety,
    observed_variety,
):
    """Unknown caller labels do not silently become recognized alternatives."""
    result = classify_language_variety(
        preferred_variety=preferred_variety,
        observed_variety=observed_variety,
        form_status="valid",
    )

    assert result["classification"] == "uncertain"
    assert result["error"] is False
    assert result["is_valid_alternative"] is False


@pytest.mark.parametrize(
    ("preferred_variety", "observed_variety"),
    (
        (None, "British English"),
        ("", "British English"),
        ("American English", None),
        ("American English", ""),
    ),
)
def test_language_variety_missing_required_input_is_uncertain(
    preferred_variety,
    observed_variety,
):
    """Removing either side of a variety comparison removes the classification."""
    result = classify_language_variety(
        preferred_variety=preferred_variety,
        observed_variety=observed_variety,
        form_status="valid",
    )

    assert result["classification"] == "uncertain"
    assert result["error"] is False
    assert result["is_valid_alternative"] is False


@pytest.mark.parametrize(
    ("preferred_variety", "observed_variety"),
    (
        (["American English"], "British English"),
        ("American English", {"name": "British English"}),
        (123, "British English"),
        ("American English", 456),
    ),
)
def test_language_variety_malformed_variety_inputs_fail_closed(
    preferred_variety,
    observed_variety,
):
    """Non-string variety payloads cannot add a valid alternative claim."""
    result = classify_language_variety(
        preferred_variety=preferred_variety,
        observed_variety=observed_variety,
        form_status="valid",
    )

    assert result["classification"] == "uncertain"
    assert result["error"] is False
    assert result["is_valid_alternative"] is False


def test_language_variety_explicit_incorrect_form_remains_incorrect():
    """An explicit incorrect assessment overrides a recognized variety difference."""
    result = classify_language_variety(
        preferred_variety="American English",
        observed_variety="British English",
        form_status="incorrect",
    )

    assert result["classification"] == "incorrect"
    assert result["error"] is True
    assert result["is_valid_alternative"] is False


def test_language_variety_case_and_whitespace_normalization_is_equivalent():
    """Case and surrounding whitespace do not change variety semantics."""
    canonical = classify_language_variety(
        preferred_variety="American English",
        observed_variety="British English",
        assessment_standard="General English",
        form_status="valid",
    )
    normalized = classify_language_variety(
        preferred_variety="  aMeRiCaN eNgLiSh  ",
        observed_variety="\tBRITISH ENGLISH\n",
        assessment_standard=" general english ",
        form_status=" VALID ",
    )

    assert normalized == canonical


def test_language_variety_output_is_json_safe_and_inputs_are_immutable():
    """Classification normalizes output without mutating caller-owned input."""
    inputs = {
        "preferred_variety": " American English ",
        "observed_variety": " British English ",
        "assessment_standard": {"label": "General English"},
        "form_status": "valid",
    }
    before = deepcopy(inputs)

    result = classify_language_variety(**inputs)

    assert result["classification"] == "valid_alternative"
    assert inputs == before
    assert json.loads(json.dumps(result, allow_nan=False)) == result


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


@pytest.mark.parametrize(
    "evidence",
    (
        (
            {
                "source_kind": "audio_transcript",
                "source_id": "transcript-1",
                "skill": "pronunciation",
                "transcript": "Hello world",
            },
        ),
        (
            {
                "source_kind": "text_transcript",
                "source_id": "text-1",
                "skill": "pronunciation",
                "transcript": "Hello world",
            },
        ),
        (
            {
                "source_kind": "user_message",
                "source_id": "message-1",
                "skill": "pronunciation",
                "text": "My pronunciation is excellent.",
            },
        ),
        (
            {
                "source_kind": "self_report",
                "source_id": "report-1",
                "skill": "pronunciation",
                "observed": "excellent",
            },
        ),
        (
            {
                "source_kind": "sample",
                "sample_id": "sample-1",
                "skill": "pronunciation",
                "observed": "B2",
            },
        ),
        (
            {
                "source_kind": "acoustic_assessment",
                "assessment_id": "assessment-1",
                "skill": "pronunciation",
                "pronunciation_assessed": False,
            },
        ),
        (
            {
                "source_kind": "acoustic_assessment",
                "assessment_id": "assessment-2",
                "skill": "pronunciation",
            },
        ),
        (
            {
                "source_kind": "pronunciation_assessment",
                "provenance_id": "pronunciation-2",
                "skill": "pronunciation",
            },
        ),
        (
            {
                "source_kind": "pronunciation_assessment",
                "skill": "pronunciation",
                "pronunciation_assessed": True,
            },
        ),
    ),
)
def test_skill_separation_rejects_ungrounded_or_non_acoustic_pronunciation_evidence(evidence):
    """Text and self-claims cannot establish pronunciation assessment."""
    separated = separate_skill_evidence(evidence=evidence)

    assert separated["pronunciation_assessed"] is False
    assert separated["by_skill"]["pronunciation"] == {
        "status": "insufficient_evidence",
        "evidence_count": 0,
        "evidence": [],
    }


@pytest.mark.parametrize(
    "evidence",
    (
        (
            {
                "source_kind": "acoustic_assessment",
                "assessment_id": "acoustic-1",
                "skill": "pronunciation",
                "finding": "Vowel length is inconsistent.",
            },
        ),
        (
            {
                "source_kind": "pronunciation_assessment",
                "provenance_id": "pronunciation-1",
                "skill": "pronunciation",
                "score": 0.8,
            },
        ),
        (
            {
                "source_kind": "audio_sample",
                "sample_id": "audio-1",
                "skill": "pronunciation",
                "pronunciation_result": "Final consonants need practice.",
            },
        ),
    ),
)
def test_skill_separation_accepts_grounded_explicit_pronunciation_assessments(evidence):
    """Only explicit acoustic/pronunciation assessments can support this skill."""
    separated = separate_skill_evidence(evidence=evidence)

    assert separated["pronunciation_assessed"] is True
    assert separated["by_skill"]["pronunciation"]["status"] == "evidenced"
    assert separated["by_skill"]["pronunciation"]["evidence_count"] == 1
    assert separated["by_skill"]["pronunciation"]["evidence"] == list(evidence)


@pytest.mark.parametrize(
    "evidence",
    (
        (
            {
                "source_kind": "acoustic_assessment",
                "skill": "pronunciation",
            },
        ),
        (
            {
                "source_kind": "audio_sample",
                "sample_id": "audio-1",
                "skill": "pronunciation",
                "pronunciation_result": " ",
            },
        ),
        (
            {
                "source_kind": "audio_sample",
                "sample_id": "audio-2",
                "skill": "pronunciation",
                "score": float("nan"),
            },
        ),
        (
            {
                "source_kind": ["acoustic_assessment"],
                "assessment_id": "assessment-1",
                "skill": "pronunciation",
            },
        ),
        {},
        None,
    ),
)
def test_skill_separation_pronunciation_provenance_removal_and_malformed_records_fail_closed(evidence):
    """Removing assessment provenance or malformed assessment fields cannot add support."""
    separated = separate_skill_evidence(evidence=(evidence,))

    assert separated["pronunciation_assessed"] is False
    assert separated["by_skill"]["pronunciation"]["status"] == "insufficient_evidence"
    assert separated["by_skill"]["pronunciation"]["evidence_count"] == 0
    json.dumps(separated, allow_nan=False)


def test_skill_separation_pronunciation_filter_preserves_other_skills_json_and_inputs():
    """Pronunciation hardening is local, JSON-safe, and does not mutate evidence."""
    evidence = [
        {
            "source_kind": "sample",
            "sample_id": "pronunciation-claim",
            "skill": "pronunciation",
            "observed": "B2",
        },
        {"skill": "reading", "observed": "B2"},
        {"skill": "grammar", "observed": "85%"},
    ]
    before = deepcopy(evidence)

    separated = separate_skill_evidence(evidence=evidence)

    assert separated["by_skill"]["pronunciation"]["status"] == "insufficient_evidence"
    assert separated["by_skill"]["reading"]["status"] == "evidenced"
    assert separated["by_skill"]["grammar"]["status"] == "evidenced"
    assert evidence == before
    json.dumps(separated, allow_nan=False)


def test_framework_mapping_requires_provenance():
    result = evaluate_framework_mapping(
        source_framework="IELTS",
        source_value="6.5",
        target_framework="CEFR",
        mapping_evidence=({"target_range": "B2"},),
    )
    assert result["calibrated"] is False


def test_framework_mapping_rejects_arbitrary_target_range_record():
    """Removing provenance from a range record prevents cross-framework calibration."""
    result = evaluate_framework_mapping(
        source_framework="IELTS",
        source_value="6.5",
        target_framework="CEFR",
        mapping_evidence=({"target_range": "B2", "authority": "official"},),
    )

    assert result["mapping_status"] in {"identity_forbidden", "insufficient_evidence"}
    assert result["target_estimate_range"] is None
    assert result["is_exact"] is False
    assert result["calibrated"] is False


def test_framework_mapping_rejects_source_looking_display_string_without_provenance():
    """A source label is display context, not canonical mapping provenance."""
    result = evaluate_framework_mapping(
        source_framework="CEFR",
        source_value="C1",
        target_framework="IELTS",
        mapping_evidence=(
            {"source": "Cambridge English Concordance", "target_range": "7.0-8.0"},
        ),
    )

    assert result["mapping_status"] in {"identity_forbidden", "insufficient_evidence"}
    assert result["target_estimate_range"] is None
    assert result["is_exact"] is False
    assert result["calibrated"] is False


@pytest.mark.parametrize(
    "provenance_field",
    (
        "provenance_id",
        "source_id",
        "assessment_id",
        "sample_id",
        "context_id",
        "official_source_id",
    ),
)
def test_framework_mapping_accepts_each_canonical_provenance_alias(provenance_field):
    """Each established canonical provenance alias can ground a range mapping."""
    evidence = {provenance_field: "concordance-v1", "target_range": "B2"}

    result = evaluate_framework_mapping(
        source_framework="IELTS",
        source_value="6.5",
        target_framework="CEFR",
        mapping_evidence=(evidence,),
    )

    assert result["mapping_status"] == "grounded_approximate_mapping"
    assert result["target_estimate_range"] == "B2"
    assert result["is_exact"] is False
    assert result["approximate"] is True
    assert result["calibrated"] is True
    assert result["evidence"] == [evidence]


@pytest.mark.parametrize("target_range", (None, "", "  ", ["B2"], {"range": "B2"}, True))
def test_framework_mapping_requires_a_usable_target_range(target_range):
    """Removing or corrupting the target range prevents calibration despite provenance."""
    result = evaluate_framework_mapping(
        source_framework="IELTS",
        source_value="6.5",
        target_framework="CEFR",
        mapping_evidence=(
            {"source_id": "concordance-v1", "target_range": target_range},
        ),
    )

    assert result["mapping_status"] in {"identity_forbidden", "insufficient_evidence"}
    assert result["target_estimate_range"] is None
    assert result["is_exact"] is False
    assert result["calibrated"] is False


@pytest.mark.parametrize("provenance_field", ("source_id", "official_source_id"))
def test_framework_mapping_duplicate_provenance_does_not_add_mapping_authority(provenance_field):
    """Duplicate source occurrences collapse even when caller display fields differ."""
    evidence = [
        {"source": "Concordance copy A", provenance_field: "concordance-v1", "target_range": "B2"},
        {"source": "Concordance copy B", provenance_field: "concordance-v1", "target_range": "B2"},
    ]
    before = deepcopy(evidence)

    result = evaluate_framework_mapping(
        source_framework="IELTS",
        source_value="6.5",
        target_framework="CEFR",
        mapping_evidence=evidence,
    )

    assert result["mapping_status"] == "grounded_approximate_mapping"
    assert result["target_estimate_range"] == "B2"
    assert len(result["evidence"]) == 1
    assert evidence == before
    assert json.loads(json.dumps(result, allow_nan=False)) == result


def test_framework_mapping_evidence_order_does_not_change_result():
    """Equivalent sets of grounded mapping evidence have deterministic output order."""
    evidence = (
        {"source": "Concordance B", "source_id": "concordance-b", "target_range": "B2"},
        {"source": "Concordance A", "source_id": "concordance-a", "target_range": "B2"},
    )

    forward = evaluate_framework_mapping(
        source_framework="IELTS",
        source_value="6.5",
        target_framework="CEFR",
        mapping_evidence=evidence,
    )
    reverse = evaluate_framework_mapping(
        source_framework="IELTS",
        source_value="6.5",
        target_framework="CEFR",
        mapping_evidence=tuple(reversed(evidence)),
    )

    assert forward == reverse


def test_framework_mapping_conflicting_ranges_fail_closed_and_permutation_invariant():
    """Conflicting target ranges across or within sources cannot produce an authoritative calibrated range."""
    # Same-provenance conflict
    same_prov_conflict = evaluate_framework_mapping(
        source_framework="IELTS",
        source_value="6.5",
        target_framework="CEFR",
        mapping_evidence=(
            {"source_id": "concordance-v1", "target_range": "C1"},
            {"source_id": "concordance-v1", "target_range": "B1"},
        ),
    )
    assert same_prov_conflict["calibrated"] is False
    assert same_prov_conflict["target_estimate_range"] is None
    assert same_prov_conflict["mapping_status"] in {"identity_forbidden", "insufficient_evidence", "conflicting_evidence"}

    # Independent provenance conflict (forward and reverse)
    evidence_forward = (
        {"source_id": "source-a", "target_range": "B1"},
        {"source_id": "source-b", "target_range": "C1"},
    )
    forward = evaluate_framework_mapping(
        source_framework="IELTS",
        source_value="6.5",
        target_framework="CEFR",
        mapping_evidence=evidence_forward,
    )
    reverse = evaluate_framework_mapping(
        source_framework="IELTS",
        source_value="6.5",
        target_framework="CEFR",
        mapping_evidence=tuple(reversed(evidence_forward)),
    )

    assert forward == reverse
    assert forward["calibrated"] is False
    assert forward["target_estimate_range"] is None
    assert forward["mapping_status"] in {"identity_forbidden", "insufficient_evidence", "conflicting_evidence"}


@pytest.mark.parametrize("invalid_container", (None, 42, "string_container", True))
def test_framework_mapping_malformed_evidence_container_fails_closed(invalid_container):
    """Non-collection or malformed evidence containers fail closed without raising TypeError."""
    result = evaluate_framework_mapping(
        source_framework="IELTS",
        source_value="6.5",
        target_framework="CEFR",
        mapping_evidence=invalid_container,
    )
    assert result["calibrated"] is False
    assert result["target_estimate_range"] is None
    assert result["mapping_status"] in {"identity_forbidden", "insufficient_evidence"}
    assert json.loads(json.dumps(result, allow_nan=False)) == result


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


@pytest.mark.parametrize("invalid_threshold", (float("nan"), float("inf"), float("-inf"), "three", [3], {"min": 3}))
def test_error_pattern_nan_inf_nonnumeric_threshold_normalizes_to_canonical_minimum(invalid_threshold):
    """NaN/Inf or non-numeric thresholds fall back to canonical minimum 2."""
    obs_1 = (
        {"provenance_id": "p1", "comparison_key": "essay", "error_type": "tense", "comparable": True},
    )
    res_1 = evaluate_error_pattern(observations=obs_1, minimum_independent_occurrences=invalid_threshold)
    assert res_1["eligible"] is False
    assert res_1["pattern_state"] == "insufficient_evidence"

    obs_2 = (
        {"provenance_id": "p1", "comparison_key": "essay", "error_type": "tense", "comparable": True},
        {"provenance_id": "p2", "comparison_key": "essay", "error_type": "tense", "comparable": True},
    )
    res_2 = evaluate_error_pattern(observations=obs_2, minimum_independent_occurrences=invalid_threshold)
    assert res_2["eligible"] is True
    assert res_2["pattern_state"] == "candidate"


def test_error_pattern_stricter_caller_threshold_is_honored():
    """Callers may increase threshold above 2, requiring more evidence."""
    obs_2 = (
        {"provenance_id": "p1", "comparison_key": "essay", "error_type": "tense", "comparable": True},
        {"provenance_id": "p2", "comparison_key": "essay", "error_type": "tense", "comparable": True},
    )
    res_stricter = evaluate_error_pattern(observations=obs_2, minimum_independent_occurrences=3)
    assert res_stricter["eligible"] is False
    assert res_stricter["pattern_state"] == "insufficient_evidence"

    obs_3 = obs_2 + (
        {"provenance_id": "p3", "comparison_key": "essay", "error_type": "tense", "comparable": True},
    )
    res_met = evaluate_error_pattern(observations=obs_3, minimum_independent_occurrences=3)
    assert res_met["eligible"] is True
    assert res_met["pattern_state"] == "candidate"


def test_error_pattern_requires_same_error_type_and_comparison_key():
    """Mismatched error types or comparison keys do not form a single comparable pattern."""
    mismatched_types = (
        {"provenance_id": "p1", "comparison_key": "essay", "error_type": "tense", "comparable": True},
        {"provenance_id": "p2", "comparison_key": "essay", "error_type": "agreement", "comparable": True},
    )
    res_type = evaluate_error_pattern(observations=mismatched_types)
    assert res_type["eligible"] is False
    assert res_type["pattern_state"] == "insufficient_evidence"

    mismatched_keys = (
        {"provenance_id": "p1", "comparison_key": "essay", "error_type": "tense", "comparable": True},
        {"provenance_id": "p2", "comparison_key": "conversation", "error_type": "tense", "comparable": True},
    )
    res_key = evaluate_error_pattern(observations=mismatched_keys)
    assert res_key["eligible"] is False
    assert res_key["pattern_state"] == "insufficient_evidence"


def test_error_pattern_duplicate_provenance_does_not_inflate_occurrences():
    """Multiple observations with same provenance count as 1 occurrence."""
    duplicate_prov = (
        {"id": "c1", "provenance_id": "session-1", "comparison_key": "essay", "error_type": "tense", "comparable": True},
        {"id": "c2", "provenance_id": "session-1", "comparison_key": "essay", "error_type": "tense", "comparable": True},
    )
    res = evaluate_error_pattern(observations=duplicate_prov)
    assert res["eligible"] is False
    assert res["independent_occurrences"] == 1


def test_error_pattern_json_immutability_and_permutation_invariance():
    """Evaluation preserves input immutability, strict JSON serialization, and permutation invariance."""
    obs = [
        {"id": "c1", "provenance_id": "p1", "comparison_key": "essay", "error_type": "tense", "comparable": True},
        {"id": "c2", "provenance_id": "p2", "comparison_key": "essay", "error_type": "tense", "comparable": True},
    ]
    before = deepcopy(obs)
    forward = evaluate_error_pattern(observations=obs)
    reverse = evaluate_error_pattern(observations=list(reversed(obs)))

    assert forward == reverse
    assert obs == before
    assert json.loads(json.dumps(forward, allow_nan=False)) == forward


def test_correction_priority_hierarchy_and_mutation():
    """Verify priority hierarchy by mutating properties and observing priority shifts."""
    base_error = {"id": "err-1", "error_type": "style_flow", "category": "minor_style", "blocking": False}

    # 1. Minor style vs blocking
    blocking_error = {"id": "err-2", "error_type": "verb_drop", "category": "comprehension_blocking", "blocking": True}
    res_blocking = prioritize_corrections(errors=(base_error, blocking_error))
    assert res_blocking["prioritized_errors"][0]["id"] == "err-2"

    # 2. Recurrent outranks goal-critical
    recurrent_error = {"id": "err-3", "error_type": "tense", "category": "recurrent", "blocking": False}
    goal_error = {"id": "err-4", "error_type": "vocab_formal", "category": "register", "blocking": False}
    res_recur_goal = prioritize_corrections(
        errors=(goal_error, recurrent_error),
        active_goals=("vocab_formal",),
    )
    assert res_recur_goal["prioritized_errors"][0]["id"] == "err-3"
    assert res_recur_goal["prioritized_errors"][1]["id"] == "err-4"

    # 3. Mutating goal relevance changes priority: without active goal, register is below recurrent
    res_without_goal = prioritize_corrections(
        errors=(goal_error, base_error),
        active_goals=(),
    )
    # With active goal:
    res_with_goal = prioritize_corrections(
        errors=(goal_error, base_error),
        active_goals=("vocab_formal",),
    )
    assert res_with_goal["prioritized_errors"][0]["id"] == "err-4"

    # 4. Mutating certification relevance changes priority
    cert_error = {"id": "err-5", "error_type": "inversion", "category": "syntax", "blocking": False}
    res_cert = prioritize_corrections(
        errors=(cert_error, base_error),
        certification_relevance=("inversion",),
    )
    assert res_cert["prioritized_errors"][0]["id"] == "err-5"


def test_correction_priority_modes_defer_and_selective_density():
    """Assess mode defers all feedback; practice mode defers minor style when high priority errors present."""
    errors = (
        {"id": "e_block", "category": "comprehension_blocking", "blocking": True},
        {"id": "e_minor", "category": "minor_style", "blocking": False},
    )
    # Practice mode: e_minor is deferred
    res_practice = prioritize_corrections(errors=errors, mode="practice")
    assert res_practice["defer_feedback"] is False
    assert [e["id"] for e in res_practice["immediate_errors"]] == ["e_block"]
    assert [e["id"] for e in res_practice["deferred_errors"]] == ["e_minor"]

    # Assess mode: all feedback deferred
    res_assess = prioritize_corrections(errors=errors, mode="assess")
    assert res_assess["defer_feedback"] is True
    assert len(res_assess["immediate_errors"]) == 0
    assert len(res_assess["deferred_errors"]) == 2


def test_correction_priority_json_immutability_and_permutation_invariance():
    """Evaluation preserves input immutability, strict JSON serialization, and permutation invariance."""
    errors = [
        {"id": "e1", "category": "minor_style", "blocking": False},
        {"id": "e2", "category": "comprehension_blocking", "blocking": True},
    ]
    before = deepcopy(errors)
    forward = prioritize_corrections(errors=errors, active_goals=["g1"], certification_relevance=["c1"])
    reverse = prioritize_corrections(errors=list(reversed(errors)), active_goals=["g1"], certification_relevance=["c1"])

    assert forward == reverse
    assert errors == before
    assert json.loads(json.dumps(forward, allow_nan=False)) == forward


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
