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
    evaluate_level_update,
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
            {
                "id": "caller-a",
                "provenance_id": "essay-1",
                "skill": "writing",
                "observed": "C1",
            },
            {
                "id": "caller-b",
                "provenance_id": "essay-1",
                "skill": "writing",
                "observed": "C1",
            },
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
                {
                    "provenance_id": "writing-1",
                    "skill": "writing",
                    "observed": "not-a-level",
                },
                {
                    "provenance_id": "writing-2",
                    "skill": "writing",
                    "observed": "not-a-level",
                },
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
def test_level_estimate_requires_evidence_relevant_to_scope_and_claim(
    level_or_score, evidence
):
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
        (
            "B2",
            (
                {
                    "provenance_id": "writing-1",
                    "skill": "writing",
                    "observed": "not-a-level",
                },
            ),
        ),
        (0.8, ({"provenance_id": "writing-1", "skill": "writing", "score": 0.7},)),
    ),
)
def test_observed_performance_requires_evidence_relevant_to_scope_and_claim(
    level_or_score, evidence
):
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
                "framework": "CEFR",
                "result": "C1",
                "valid_at": "2026-01-01",
            },
        ),
    )
    invalid = classify_proficiency_record(
        kind="CERTIFIED",
        framework="CEFR",
        level_or_score="C1",
        evidence=(
            {"source_kind": "official_certificate", "source_id": "unverified-record"},
        ),
    )

    assert valid["kind"] == "CERTIFIED"
    assert valid["level_or_score"] == "C1"
    assert valid["is_certified"] is True
    assert invalid["is_certified"] is False
    assert invalid["level_or_score"] == "unassessed"
    assert invalid["confidence"] == 0.0


def test_certified_record_without_claimed_level_remains_unassessed():
    """Sparse certificate without result or valid_at cannot certify and fails closed."""
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

    assert result["is_certified"] is False
    assert result["kind"] != "CERTIFIED"
    assert result["level_or_score"] == "unassessed"
    assert result["confidence"] == 0.0


@pytest.mark.parametrize(
    "evidence",
    (
        ({"provenance_id": "essay-1", "skill": "writing", "observed": "C1"},),
        (
            {
                "id": "caller-a",
                "provenance_id": "essay-1",
                "skill": "writing",
                "observed": "C1",
            },
            {
                "id": "caller-b",
                "provenance_id": "essay-1",
                "skill": "writing",
                "observed": "C1",
            },
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
def test_skill_separation_rejects_ungrounded_or_non_acoustic_pronunciation_evidence(
    evidence,
):
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
def test_skill_separation_pronunciation_provenance_removal_and_malformed_records_fail_closed(
    evidence,
):
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
    "source_field",
    (
        "source_id",
        "official_source_id",
    ),
)
def test_framework_mapping_accepts_dedicated_source_authority_fields(source_field):
    """Only dedicated source authority fields can ground a framework range mapping."""
    evidence = {
        source_field: "concordance-v1",
        "source_framework": "IELTS",
        "source_value": "6.5",
        "target_framework": "CEFR",
        "target_range": "B2",
    }

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


@pytest.mark.parametrize(
    "target_range", (None, "", "  ", ["B2"], {"range": "B2"}, True)
)
def test_framework_mapping_requires_a_usable_target_range(target_range):
    """Removing or corrupting the target range prevents calibration despite provenance."""
    result = evaluate_framework_mapping(
        source_framework="IELTS",
        source_value="6.5",
        target_framework="CEFR",
        mapping_evidence=(
            {
                "source_id": "concordance-v1",
                "source_framework": "IELTS",
                "source_value": "6.5",
                "target_framework": "CEFR",
                "target_range": target_range,
            },
        ),
    )

    assert result["mapping_status"] in {"identity_forbidden", "insufficient_evidence"}
    assert result["target_estimate_range"] is None
    assert result["is_exact"] is False
    assert result["calibrated"] is False


@pytest.mark.parametrize("provenance_field", ("source_id", "official_source_id"))
def test_framework_mapping_duplicate_provenance_does_not_add_mapping_authority(
    provenance_field,
):
    """Duplicate source occurrences collapse even when caller display fields differ."""
    evidence = [
        {
            "source": "Concordance copy A",
            provenance_field: "concordance-v1",
            "source_framework": "IELTS",
            "source_value": "6.5",
            "target_framework": "CEFR",
            "target_range": "B2",
        },
        {
            "source": "Concordance copy B",
            provenance_field: "concordance-v1",
            "source_framework": "IELTS",
            "source_value": "6.5",
            "target_framework": "CEFR",
            "target_range": "B2",
        },
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
        {
            "source": "Concordance B",
            "source_id": "concordance-b",
            "source_framework": "IELTS",
            "source_value": "6.5",
            "target_framework": "CEFR",
            "target_range": "B2",
        },
        {
            "source": "Concordance A",
            "source_id": "concordance-a",
            "source_framework": "IELTS",
            "source_value": "6.5",
            "target_framework": "CEFR",
            "target_range": "B2",
        },
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
            {
                "source_id": "concordance-v1",
                "source_framework": "IELTS",
                "source_value": "6.5",
                "target_framework": "CEFR",
                "target_range": "C1",
            },
            {
                "source_id": "concordance-v1",
                "source_framework": "IELTS",
                "source_value": "6.5",
                "target_framework": "CEFR",
                "target_range": "B1",
            },
        ),
    )
    assert same_prov_conflict["calibrated"] is False
    assert same_prov_conflict["target_estimate_range"] is None
    assert same_prov_conflict["mapping_status"] in {
        "identity_forbidden",
        "insufficient_evidence",
        "conflicting_evidence",
    }

    # Independent provenance conflict (forward and reverse)
    evidence_forward = (
        {
            "source_id": "source-a",
            "source_framework": "IELTS",
            "source_value": "6.5",
            "target_framework": "CEFR",
            "target_range": "B1",
        },
        {
            "source_id": "source-b",
            "source_framework": "IELTS",
            "source_value": "6.5",
            "target_framework": "CEFR",
            "target_range": "C1",
        },
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
    assert forward["mapping_status"] in {
        "identity_forbidden",
        "insufficient_evidence",
        "conflicting_evidence",
    }


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


@pytest.mark.parametrize(
    "invalid_threshold",
    (float("nan"), float("inf"), float("-inf"), "three", [3], {"min": 3}),
)
def test_error_pattern_nan_inf_nonnumeric_threshold_normalizes_to_canonical_minimum(
    invalid_threshold,
):
    """NaN/Inf or non-numeric thresholds fall back to canonical minimum 2."""
    obs_1 = (
        {
            "provenance_id": "p1",
            "comparison_key": "essay",
            "error_type": "tense",
            "comparable": True,
        },
    )
    res_1 = evaluate_error_pattern(
        observations=obs_1, minimum_independent_occurrences=invalid_threshold
    )
    assert res_1["eligible"] is False
    assert res_1["pattern_state"] == "insufficient_evidence"

    obs_2 = (
        {
            "provenance_id": "p1",
            "comparison_key": "essay",
            "error_type": "tense",
            "comparable": True,
        },
        {
            "provenance_id": "p2",
            "comparison_key": "essay",
            "error_type": "tense",
            "comparable": True,
        },
    )
    res_2 = evaluate_error_pattern(
        observations=obs_2, minimum_independent_occurrences=invalid_threshold
    )
    assert res_2["eligible"] is True
    assert res_2["pattern_state"] == "candidate"


def test_error_pattern_stricter_caller_threshold_is_honored():
    """Callers may increase threshold above 2, requiring more evidence."""
    obs_2 = (
        {
            "provenance_id": "p1",
            "comparison_key": "essay",
            "error_type": "tense",
            "comparable": True,
        },
        {
            "provenance_id": "p2",
            "comparison_key": "essay",
            "error_type": "tense",
            "comparable": True,
        },
    )
    res_stricter = evaluate_error_pattern(
        observations=obs_2, minimum_independent_occurrences=3
    )
    assert res_stricter["eligible"] is False
    assert res_stricter["pattern_state"] == "insufficient_evidence"

    obs_3 = obs_2 + (
        {
            "provenance_id": "p3",
            "comparison_key": "essay",
            "error_type": "tense",
            "comparable": True,
        },
    )
    res_met = evaluate_error_pattern(
        observations=obs_3, minimum_independent_occurrences=3
    )
    assert res_met["eligible"] is True
    assert res_met["pattern_state"] == "candidate"


def test_error_pattern_requires_same_error_type_and_comparison_key():
    """Mismatched error types or comparison keys do not form a single comparable pattern."""
    mismatched_types = (
        {
            "provenance_id": "p1",
            "comparison_key": "essay",
            "error_type": "tense",
            "comparable": True,
        },
        {
            "provenance_id": "p2",
            "comparison_key": "essay",
            "error_type": "agreement",
            "comparable": True,
        },
    )
    res_type = evaluate_error_pattern(observations=mismatched_types)
    assert res_type["eligible"] is False
    assert res_type["pattern_state"] == "insufficient_evidence"

    mismatched_keys = (
        {
            "provenance_id": "p1",
            "comparison_key": "essay",
            "error_type": "tense",
            "comparable": True,
        },
        {
            "provenance_id": "p2",
            "comparison_key": "conversation",
            "error_type": "tense",
            "comparable": True,
        },
    )
    res_key = evaluate_error_pattern(observations=mismatched_keys)
    assert res_key["eligible"] is False
    assert res_key["pattern_state"] == "insufficient_evidence"


def test_error_pattern_duplicate_provenance_does_not_inflate_occurrences():
    """Multiple observations with same provenance count as 1 occurrence."""
    duplicate_prov = (
        {
            "id": "c1",
            "provenance_id": "session-1",
            "comparison_key": "essay",
            "error_type": "tense",
            "comparable": True,
        },
        {
            "id": "c2",
            "provenance_id": "session-1",
            "comparison_key": "essay",
            "error_type": "tense",
            "comparable": True,
        },
    )
    res = evaluate_error_pattern(observations=duplicate_prov)
    assert res["eligible"] is False
    assert res["independent_occurrences"] == 1


def test_error_pattern_json_immutability_and_permutation_invariance():
    """Evaluation preserves input immutability, strict JSON serialization, and permutation invariance."""
    obs = [
        {
            "id": "c1",
            "provenance_id": "p1",
            "comparison_key": "essay",
            "error_type": "tense",
            "comparable": True,
        },
        {
            "id": "c2",
            "provenance_id": "p2",
            "comparison_key": "essay",
            "error_type": "tense",
            "comparable": True,
        },
    ]
    before = deepcopy(obs)
    forward = evaluate_error_pattern(observations=obs)
    reverse = evaluate_error_pattern(observations=list(reversed(obs)))

    assert forward == reverse
    assert obs == before
    assert json.loads(json.dumps(forward, allow_nan=False)) == forward


def test_correction_priority_hierarchy_and_mutation():
    """Verify priority hierarchy by mutating properties and observing priority shifts."""
    base_error = {
        "id": "err-1",
        "error_type": "style_flow",
        "category": "minor_style",
        "blocking": False,
    }

    # 1. Minor style vs blocking
    blocking_error = {
        "id": "err-2",
        "error_type": "verb_drop",
        "category": "comprehension_blocking",
        "blocking": True,
    }
    res_blocking = prioritize_corrections(errors=(base_error, blocking_error))
    assert res_blocking["prioritized_errors"][0]["id"] == "err-2"

    # 2. Recurrent outranks goal-critical
    recurrent_error = {
        "id": "err-3",
        "error_type": "tense",
        "category": "recurrent",
        "blocking": False,
    }
    goal_error = {
        "id": "err-4",
        "error_type": "vocab_formal",
        "category": "register",
        "blocking": False,
    }
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
    assert res_without_goal["prioritized_errors"][0]["id"] == "err-4"
    # With active goal:
    res_with_goal = prioritize_corrections(
        errors=(goal_error, base_error),
        active_goals=("vocab_formal",),
    )
    assert res_with_goal["prioritized_errors"][0]["id"] == "err-4"

    # 4. Mutating certification relevance changes priority
    cert_error = {
        "id": "err-5",
        "error_type": "inversion",
        "category": "syntax",
        "blocking": False,
    }
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
    forward = prioritize_corrections(
        errors=errors, active_goals=["g1"], certification_relevance=["c1"]
    )
    reverse = prioritize_corrections(
        errors=list(reversed(errors)),
        active_goals=["g1"],
        certification_relevance=["c1"],
    )

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


@pytest.mark.parametrize(
    "invalid_diff",
    (True, False, float("nan"), float("inf"), float("-inf"), -5, 0, "3", [3], None),
)
def test_adaptive_difficulty_invalid_current_difficulty_fails_closed(invalid_diff):
    """Invalid current difficulty values fail closed safely without crashing or increasing."""
    perf = (
        {
            "provenance_id": "p1",
            "comparison_key": "k1",
            "score": 0.95,
            "comparable": True,
        },
        {
            "provenance_id": "p2",
            "comparison_key": "k1",
            "score": 0.95,
            "comparable": True,
        },
    )
    result = adapt_difficulty(current_difficulty=invalid_diff, performance=perf)
    assert result["action"] == "insufficient_evidence"
    assert result["target_difficulty"] == 1
    assert result["current_difficulty"] == 1


@pytest.mark.parametrize(
    "invalid_score",
    (True, False, float("nan"), float("inf"), float("-inf"), -1.0, 2.0, "high", None),
)
def test_adaptive_difficulty_invalid_scores_ignored(invalid_score):
    """Non-numeric, bool, NaN, Inf, or out-of-range scores cannot drive difficulty changes."""
    perf = (
        {
            "provenance_id": "p1",
            "comparison_key": "k1",
            "score": invalid_score,
            "comparable": True,
        },
        {
            "provenance_id": "p2",
            "comparison_key": "k1",
            "score": invalid_score,
            "comparable": True,
        },
    )
    result = adapt_difficulty(current_difficulty=3, performance=perf)
    assert result["action"] == "insufficient_evidence"


def test_adaptive_difficulty_mismatched_comparison_keys_fail_closed():
    """Performance evidence across different comparison keys cannot combine into an increase."""
    perf = (
        {
            "provenance_id": "p1",
            "comparison_key": "free_writing",
            "score": 0.95,
            "comparable": True,
        },
        {
            "provenance_id": "p2",
            "comparison_key": "cloze_test",
            "score": 0.95,
            "comparable": True,
        },
    )
    result = adapt_difficulty(current_difficulty=3, performance=perf)
    assert result["action"] == "insufficient_evidence"


def test_adaptive_difficulty_duplicate_provenance_does_not_permit_increase():
    """Duplicate records for the same provenance cannot act as independent sessions for increase."""
    perf = (
        {
            "id": "c1",
            "provenance_id": "session-1",
            "comparison_key": "k1",
            "score": 0.95,
            "comparable": True,
        },
        {
            "id": "c2",
            "provenance_id": "session-1",
            "comparison_key": "k1",
            "score": 0.95,
            "comparable": True,
        },
    )
    result = adapt_difficulty(current_difficulty=3, performance=perf)
    # A single session cannot cause an increase; it maintains
    assert result["action"] != "increase"
    assert result["target_difficulty"] == 3


def test_adaptive_difficulty_json_immutability_and_permutation_invariance():
    """Evaluation preserves input immutability, strict JSON serialization, and permutation invariance."""
    perf = [
        {
            "id": "c1",
            "provenance_id": "p1",
            "comparison_key": "k1",
            "score": 0.95,
            "comparable": True,
        },
        {
            "id": "c2",
            "provenance_id": "p2",
            "comparison_key": "k1",
            "score": 0.90,
            "comparable": True,
        },
    ]
    before = deepcopy(perf)
    forward = adapt_difficulty(current_difficulty=3, performance=perf)
    reverse = adapt_difficulty(current_difficulty=3, performance=list(reversed(perf)))

    assert forward == reverse
    assert perf == before
    assert json.loads(json.dumps(forward, allow_nan=False)) == forward


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


def test_goal_alignment_activity_mutation_changes_alignment():
    """Mutating activity changes which goals align without changing goal definitions."""
    goals = (
        {"id": "g_cert", "kind": "certification", "target": "C1"},
        {"id": "g_conv", "kind": "conversation", "target": "conversation fluency"},
    )

    # 1. Roleplay matches conversation goal
    res_conv = align_activity_to_goals(activity={"type": "roleplay"}, goals=goals)
    assert res_conv["activity_fit"] == "aligned"
    assert res_conv["aligned_goals"] == ["g_conv"]

    # 2. Formal exam essay matches certification goal
    res_cert = align_activity_to_goals(
        activity={"type": "formal_exam_essay"}, goals=goals
    )
    assert res_cert["activity_fit"] == "aligned"
    assert res_cert["aligned_goals"] == ["g_cert"]

    # 3. Unrelated activity matches neither
    res_unrel = align_activity_to_goals(
        activity={"type": "unrelated_tax_filing"}, goals=goals
    )
    assert res_unrel["activity_fit"] != "aligned"
    assert res_unrel["aligned_goals"] == []


def test_goal_alignment_no_active_goals():
    """Empty goals list results in not_aligned."""
    res = align_activity_to_goals(activity={"type": "roleplay"}, goals=())
    assert res["activity_fit"] == "not_aligned"
    assert res["aligned_goals"] == []
    assert res["total_goals_count"] == 0


def test_goal_alignment_json_immutability_and_permutation_invariance():
    """Evaluation preserves input immutability, strict JSON safety, and permutation invariance."""
    goals = [
        {"id": "g1", "kind": "conversation", "target": "speaking fluency"},
        {"id": "g2", "kind": "certification", "target": "C1"},
    ]
    activity = {"type": "roleplay", "skill": "speaking"}
    before_goals = deepcopy(goals)
    before_act = deepcopy(activity)

    forward = align_activity_to_goals(activity=activity, goals=goals)
    reverse = align_activity_to_goals(activity=activity, goals=list(reversed(goals)))

    assert forward == reverse
    assert goals == before_goals
    assert activity == before_act
    assert json.loads(json.dumps(forward, allow_nan=False)) == forward


@pytest.mark.parametrize(
    "available_time",
    [float("inf"), float("-inf"), True, False, -10, float("nan"), "30", [30]],
)
def test_learning_load_invalid_time_fails_closed(available_time):
    result = evaluate_learning_load(available_time=available_time)
    assert result["load_status"] == "insufficient_constraints"
    assert result["recommended_duration_minutes"] == 0
    assert result["calendar_modified"] is False
    assert json.loads(json.dumps(result, allow_nan=False)) == result


def test_learning_load_energy_and_time_constraints_precede_preferences():
    """Hard time/energy constraints bound duration and never mutate calendar."""
    # Low energy caps at 15 even with 60 available
    res_low = evaluate_learning_load(
        available_time=60, energy="low", priorities=("reading", "writing")
    )
    assert res_low["recommended_duration_minutes"] == 15
    assert res_low["load_status"] == "scaffolded_light"
    assert res_low["calendar_modified"] is False

    # High energy allows full available time
    res_high = evaluate_learning_load(available_time=45, energy="high")
    assert res_high["recommended_duration_minutes"] == 45
    assert res_high["load_status"] == "optimal"
    assert res_high["calendar_modified"] is False


def test_learning_load_deadlines_and_recent_load_reflection():
    """Deadlines and recent load are reflected in the result structure without modifying calendar."""
    res = evaluate_learning_load(
        available_time=30,
        deadlines=[{"id": "d1", "exam_date": "2026-09-01"}],
        recent_load={"minutes_last_7_days": 120},
    )
    assert res["deadlines_considered"] == 1
    assert res["recent_load_considered"] == {"minutes_last_7_days": 120}
    assert res["calendar_modified"] is False


def test_learning_load_json_immutability():
    """Evaluation preserves input immutability and strict JSON safety."""
    inputs = {
        "available_time": 25,
        "energy": "low",
        "priorities": ["vocab", "grammar"],
        "deadlines": [{"id": "d1"}],
        "recent_load": {"sessions": 3},
        "review_backlog": [{"id": "b1"}],
    }
    before = deepcopy(inputs)
    result = evaluate_learning_load(**inputs)

    assert inputs == before
    assert json.loads(json.dumps(result, allow_nan=False)) == result


def test_spaced_review_deduplicates_logical_item():
    result = plan_spaced_review(
        items=(
            {"id": "v1", "due": True, "mastery": 0.2},
            {"id": "v1", "due": True, "mastery": 0.2},
        )
    )
    assert len(result["review_queue"]) == 1
    assert result["backlog_count"] == 1


def test_spaced_review_mastery_bounded_and_mutation_sensitive():
    """Lower mastery elevates review priority; invalid mastery defaults safely without inflating."""
    item_low_mastery = {"id": "v_low", "mastery": 0.1, "due": True}
    item_high_mastery = {"id": "v_high", "mastery": 0.9, "due": True}

    res = plan_spaced_review(items=(item_high_mastery, item_low_mastery))
    assert res["prioritized_items"][0]["id"] == "v_low"

    # Malformed mastery (e.g. -100, Inf, bool True) cannot bypass upper bound or crash
    item_invalid_mastery = {"id": "v_inv", "mastery": -100.0, "due": True}
    res_inv = plan_spaced_review(items=(item_invalid_mastery,))
    assert len(res_inv["review_queue"]) == 1


def test_spaced_review_recall_and_importance_sensitivity():
    """Recall and importance mutations directly influence ordering."""
    # Lower recall -> higher priority
    item_good_recall = {"id": "v_rec_high", "mastery": 0.5, "recall": 0.9, "due": True}
    item_poor_recall = {"id": "v_rec_low", "mastery": 0.5, "recall": 0.1, "due": True}
    res_rec = plan_spaced_review(items=(item_good_recall, item_poor_recall))
    assert res_rec["prioritized_items"][0]["id"] == "v_rec_low"

    # Higher importance -> higher priority
    item_low_imp = {"id": "v_imp_low", "mastery": 0.5, "importance": 0.1, "due": True}
    item_high_imp = {"id": "v_imp_high", "mastery": 0.5, "importance": 0.9, "due": True}
    res_imp = plan_spaced_review(items=(item_low_imp, item_high_imp))
    assert res_imp["prioritized_items"][0]["id"] == "v_imp_high"


def test_spaced_review_active_pattern_and_goal_sensitivity():
    """Active pattern and active goal matches elevate priority."""
    item_base = {"id": "v_base", "mastery": 0.5, "due": True}
    item_pattern = {"id": "v_pat", "mastery": 0.5, "due": True, "active_pattern": True}
    res_pat = plan_spaced_review(items=(item_base, item_pattern))
    assert res_pat["prioritized_items"][0]["id"] == "v_pat"

    # Goal relevance: mutate active goals
    item_goal = {"id": "v_goal", "term": "subtle", "mastery": 0.5, "due": True}
    res_no_goal = plan_spaced_review(items=(item_base, item_goal), active_goals=())
    assert res_no_goal["prioritized_items"][0]["id"] == "v_base"
    res_with_goal = plan_spaced_review(
        items=(item_base, item_goal), active_goals=("subtle",)
    )
    assert res_with_goal["prioritized_items"][0]["id"] == "v_goal"


def test_spaced_review_json_immutability_and_permutation_invariance():
    """Evaluation preserves input immutability, strict JSON serialization, and permutation invariance."""
    items = [
        {"id": "v1", "term": "word1", "mastery": 0.3, "due": True},
        {"id": "v2", "term": "word2", "mastery": 0.8, "due": False},
    ]
    before = deepcopy(items)
    forward = plan_spaced_review(items=items, active_goals=["word1"])
    reverse = plan_spaced_review(items=list(reversed(items)), active_goals=["word1"])

    assert forward == reverse
    assert items == before
    assert json.loads(json.dumps(forward, allow_nan=False)) == forward


# ── Task 11: ProgressionEvidenceRule ──────────────────────────────────────────


def test_progression_requires_comparable_baseline_and_current_evidence():
    """Progression cannot be established without baseline and comparable current evidence."""
    # No baseline
    res_no_prev = evaluate_progression(
        previous_evidence=(),
        current_evidence=(
            {
                "provenance_id": "c1",
                "score": 0.85,
                "comparable": True,
                "comparison_key": "k1",
            },
        ),
    )
    assert res_no_prev["progression_outcome"] == "insufficient_evidence"
    assert res_no_prev["stable_progression"] is False

    # Noncomparable evidence
    res_noncomp = evaluate_progression(
        previous_evidence=(
            {
                "provenance_id": "p1",
                "score": 0.6,
                "comparable": False,
                "comparison_key": "k1",
            },
        ),
        current_evidence=(
            {
                "provenance_id": "c1",
                "score": 0.85,
                "comparable": False,
                "comparison_key": "k1",
            },
        ),
    )
    assert res_noncomp["progression_outcome"] == "insufficient_evidence"
    assert res_noncomp["stable_progression"] is False


def test_progression_single_sample_vs_stable_improvement():
    """One better sample is short_term_improvement; two independent current samples form stable_improvement."""
    prev_ev = (
        {
            "provenance_id": "p1",
            "score": 0.5,
            "skill": "writing",
            "comparable": True,
            "comparison_key": "essay",
        },
    )

    # 1 sample -> short_term_improvement
    curr_single = (
        {
            "provenance_id": "c1",
            "score": 0.85,
            "skill": "writing",
            "comparable": True,
            "comparison_key": "essay",
        },
    )
    res_single = evaluate_progression(
        previous_evidence=prev_ev, current_evidence=curr_single, skill="writing"
    )
    assert res_single["progression_outcome"] == "short_term_improvement"
    assert res_single["stable_progression"] is False

    # 2 independent samples -> stable_improvement
    curr_multi = (
        {
            "provenance_id": "c1",
            "score": 0.85,
            "skill": "writing",
            "comparable": True,
            "comparison_key": "essay",
        },
        {
            "provenance_id": "c2",
            "score": 0.88,
            "skill": "writing",
            "comparable": True,
            "comparison_key": "essay",
        },
    )
    res_multi = evaluate_progression(
        previous_evidence=prev_ev, current_evidence=curr_multi, skill="writing"
    )
    assert res_multi["progression_outcome"] == "stable_improvement"
    assert res_multi["stable_progression"] is True


def test_progression_duplicate_current_provenance_not_stable():
    """Duplicate provenance in current evidence cannot satisfy independence requirement."""
    prev_ev = (
        {
            "provenance_id": "p1",
            "score": 0.5,
            "skill": "writing",
            "comparable": True,
            "comparison_key": "essay",
        },
    )
    curr_dup = (
        {
            "id": "a",
            "provenance_id": "c1",
            "score": 0.85,
            "skill": "writing",
            "comparable": True,
            "comparison_key": "essay",
        },
        {
            "id": "b",
            "provenance_id": "c1",
            "score": 0.85,
            "skill": "writing",
            "comparable": True,
            "comparison_key": "essay",
        },
    )
    res = evaluate_progression(
        previous_evidence=prev_ev, current_evidence=curr_dup, skill="writing"
    )
    assert res["progression_outcome"] == "short_term_improvement"
    assert res["stable_progression"] is False


# ── Task 12: CertificationTemporalRule ────────────────────────────────────────


def test_certification_temporal_precedence():
    """Current official source takes precedence over stale official and secondary sources."""
    sources = (
        {
            "id": "s1",
            "source_type": "official",
            "temporal_state": "stale",
            "source_id": "inst_1",
        },
        {
            "id": "s2",
            "source_type": "official",
            "temporal_state": "current",
            "official_source_id": "inst_2",
        },
        {
            "id": "s3",
            "source_type": "secondary",
            "temporal_state": "current",
            "source_id": "inst_3",
        },
    )
    res = evaluate_certification_source(sources=sources)
    assert res["selected_source"]["id"] == "s2"
    assert res["authority_rank"] == 6


def test_certification_source_requires_grounded_provenance_identity():
    """Stale official and memory sources require verification when decision critical."""
    sources_stale = (
        {
            "id": "s_stale",
            "source_type": "official",
            "temporal_state": "stale",
            "source_id": "inst_1",
        },
    )
    res = evaluate_certification_source(sources=sources_stale, decision_critical=True)
    assert res["authority_rank"] == 4
    assert res["needs_verification"] is True


def test_certification_source_conflict_detection():
    """Conflicting top-tier sources produce unresolved_conflict=True and needs_verification=True."""
    conflicting_sources = (
        {
            "id": "s1",
            "source_type": "official",
            "temporal_state": "current",
            "official_source_id": "o1",
            "format": "computer_based",
        },
        {
            "id": "s2",
            "source_type": "official",
            "temporal_state": "current",
            "official_source_id": "o2",
            "format": "paper_based",
        },
    )
    res = evaluate_certification_source(sources=conflicting_sources)
    assert res["unresolved_conflict"] is True
    assert res["needs_verification"] is True
    assert res["selected_source"] is None


# ── Task 13: CulturalContextEvidenceRule ──────────────────────────────────────


def test_cultural_context_universal_stereotypes_rejected():
    """Universal cultural claims are rejected in favor of qualified tendencies."""
    res_universal = evaluate_cultural_context(
        claim="All native speakers always pronounce this word with a rolled r.",
        universal_claim=True,
    )
    assert res_universal["universal_claim_rejected"] is True
    assert res_universal["qualified_tendency"] is True


def test_cultural_context_evidence_status_visibility():
    """Absence or presence of grounded evidence is explicitly visible in result."""
    res_no_ev = evaluate_cultural_context(
        claim="In formal settings, usted is commonly preferred."
    )
    assert res_no_ev["has_grounded_evidence"] is False
    assert res_no_ev["evidence_status"] == "weak_or_unprovenanced"

    res_with_ev = evaluate_cultural_context(
        claim="In formal settings, usted is commonly preferred.",
        evidence=({"corpus_reference": "RAE-2020", "source_id": "rae_1"},),
    )
    assert res_with_ev["has_grounded_evidence"] is True
    assert res_with_ev["evidence_status"] == "evidenced"


# ── Task 14: LanguageMemoryConsentRule ────────────────────────────────────────


def test_memory_consent_strict_boolean_and_permission_chain():
    """Session observation does not become durable state without literal boolean True consent and permission chain."""
    # Session only
    res_sess = evaluate_language_memory_consent(content_kind="note", session_only=True)
    assert res_sess["session_only_allowed"] is True
    assert res_sess["persistence_required"] is False
    assert res_sess["persistence_authorized"] is False
    assert res_sess["persistence_applied"] is False

    # String "true" or int 1 rejected
    res_str = evaluate_language_memory_consent(
        content_kind="error_profile",
        session_only=False,
        consent="true",
        permission_chain_valid=True,
    )
    assert res_str["persistence_authorized"] is False
    assert res_str["persistence_applied"] is False

    # Literal True with valid permission chain
    res_auth = evaluate_language_memory_consent(
        content_kind="error_profile",
        session_only=False,
        consent=True,
        permission_chain_valid=True,
    )
    assert res_auth["persistence_authorized"] is True
    assert (
        res_auth["persistence_applied"] is False
    )  # Never applied by domain rule helper


# ── Task 15: Cross-Rule Property Suite for All 14 Rules ───────────────────────


def test_all_14_rules_strict_json_serialization():
    """Verify all 14 public rule helpers produce strict JSON-safe serializable structures."""
    results = [
        classify_proficiency_record(
            kind="ESTIMATED", framework="CEFR", level_or_score="C1", evidence=()
        ),
        separate_skill_evidence(evidence=()),
        classify_language_variety(
            preferred_variety="American English", observed_variety="British English"
        ),
        evaluate_framework_mapping(
            source_framework="CEFR", source_value="B2", target_framework="IELTS"
        ),
        evaluate_error_pattern(observations=()),
        prioritize_corrections(errors=()),
        adapt_difficulty(current_difficulty=3, performance=()),
        plan_spaced_review(items=()),
        evaluate_learning_load(available_time=30),
        align_activity_to_goals(activity={"type": "roleplay"}, goals=()),
        evaluate_progression(previous_evidence=(), current_evidence=()),
        evaluate_certification_source(sources=()),
        evaluate_cultural_context(claim="Example claim"),
        evaluate_language_memory_consent(content_kind="profile", session_only=True),
    ]

    for res in results:
        serialized = json.dumps(res, allow_nan=False)
        assert json.loads(serialized) == res


def test_all_14_rules_input_immutability():
    """Verify none of the 14 public rule helpers mutate caller-supplied collections or dicts."""
    ev = [
        {
            "id": "e1",
            "score": 0.8,
            "comparable": True,
            "comparison_key": "k1",
            "provenance_id": "p1",
        }
    ]
    obs = [
        {
            "id": "o1",
            "error_type": "tense",
            "sentence": "He go.",
            "comparable": True,
            "comparison_key": "k1",
            "provenance_id": "p1",
        }
    ]
    errs = [{"id": "err1", "category": "minor_style", "blocking": False}]
    items = [{"id": "item1", "mastery": 0.5, "due": True}]
    goals = [{"id": "g1", "kind": "conversation", "target": "fluency"}]
    sources = [
        {
            "id": "s1",
            "source_type": "official",
            "temporal_state": "current",
            "official_source_id": "o1",
        }
    ]

    all_inputs = [ev, obs, errs, items, goals, sources]
    snapshots = [deepcopy(x) for x in all_inputs]

    classify_proficiency_record(
        kind="ESTIMATED", framework="CEFR", level_or_score="C1", evidence=ev
    )
    separate_skill_evidence(evidence=ev)
    classify_language_variety(
        preferred_variety="American English", observed_variety="British English"
    )
    evaluate_framework_mapping(
        source_framework="CEFR",
        source_value="B2",
        target_framework="IELTS",
        mapping_evidence=ev,
    )
    evaluate_error_pattern(observations=obs)
    prioritize_corrections(
        errors=errs, active_goals=["g1"], certification_relevance=["c1"]
    )
    adapt_difficulty(current_difficulty=3, performance=ev)
    plan_spaced_review(items=items, active_goals=["g1"])
    evaluate_learning_load(
        available_time=30,
        priorities=["p1"],
        deadlines=[{"id": "d1"}],
        review_backlog=[{"id": "b1"}],
    )
    align_activity_to_goals(activity={"type": "roleplay"}, goals=goals)
    evaluate_progression(previous_evidence=ev, current_evidence=ev)
    evaluate_certification_source(sources=sources)
    evaluate_cultural_context(claim="Claim", evidence=ev)
    evaluate_language_memory_consent(content_kind="profile", session_only=True)

    for current, snapshot in zip(all_inputs, snapshots, strict=True):
        assert current == snapshot


# ── Epistemic Binding Remediation (Findings 1–5) ─────────────────────────────


def test_certification_source_authority_unprovenanced_official_blocked():
    """Unprovenanced current official source must not receive rank 6 and must require verification."""
    unprov_official = {
        "id": "x",
        "source_type": "official",
        "temporal_state": "current",
        "format": "computer",
    }
    res = evaluate_certification_source(
        sources=(unprov_official,), decision_critical=True
    )
    assert res["authority_rank"] != 6
    assert res["needs_verification"] is True

    unprov_sec = {
        "id": "x",
        "source_type": "secondary",
        "temporal_state": "current",
    }
    res_sec = evaluate_certification_source(
        sources=(unprov_sec,), decision_critical=True
    )
    assert res_sec["authority_rank"] != 5

    # Grounded official gets rank 6 and needs no verification
    prov_official = {
        "id": "x",
        "source_type": "official",
        "temporal_state": "current",
        "official_source_id": "official-inst-1",
    }
    res_prov = evaluate_certification_source(
        sources=(prov_official,), decision_critical=True
    )
    assert res_prov["authority_rank"] == 6
    assert res_prov["needs_verification"] is False

    # Grounded secondary gets rank 5
    prov_sec = {
        "id": "x",
        "source_type": "secondary",
        "temporal_state": "current",
        "source_id": "sec-inst-1",
    }
    res_prov_sec = evaluate_certification_source(
        sources=(prov_sec,), decision_critical=True
    )
    assert res_prov_sec["authority_rank"] == 5

    # Grounded stale official gets rank 4 and requires verification if decision critical
    stale_official = {
        "id": "x",
        "source_type": "official",
        "temporal_state": "stale",
        "official_source_id": "official-inst-1",
    }
    res_stale = evaluate_certification_source(
        sources=(stale_official,), decision_critical=True
    )
    assert res_stale["authority_rank"] == 4
    assert res_stale["needs_verification"] is True


def test_language_level_framework_leakage_blocked():
    """Cross-framework evidence cannot ground an estimate in a different framework."""
    actfl_evidence = (
        {
            "provenance_id": "p1",
            "skill": "writing",
            "observed": "C1",
            "framework": "ACTFL",
        },
        {
            "provenance_id": "p2",
            "skill": "writing",
            "observed": "C1",
            "framework": "ACTFL",
        },
    )
    res_cefr = classify_proficiency_record(
        kind="ESTIMATED",
        framework="CEFR",
        level_or_score="C1",
        skill_scope="writing",
        evidence=actfl_evidence,
    )
    assert res_cefr["level_or_score"] == "unassessed"
    assert res_cefr["confidence"] == 0.0

    # Mixed framework: only matching framework evidence counts
    mixed_evidence = (
        {
            "provenance_id": "p1",
            "skill": "writing",
            "observed": "C1",
            "framework": "ACTFL",
        },
        {
            "provenance_id": "p2",
            "skill": "writing",
            "observed": "C1",
            "framework": "CEFR",
        },
    )
    res_mixed = classify_proficiency_record(
        kind="ESTIMATED",
        framework="CEFR",
        level_or_score="C1",
        skill_scope="writing",
        evidence=mixed_evidence,
    )
    # Only 1 matching CEFR record -> insufficient for ESTIMATED (requires 2 independent)
    assert res_mixed["kind"] == "OBSERVED_PERFORMANCE"

    # Two matching CEFR records -> ESTIMATED allowed
    cefr_evidence = (
        {
            "provenance_id": "p2",
            "skill": "writing",
            "observed": "C1",
            "framework": "CEFR",
        },
        {
            "provenance_id": "p3",
            "skill": "writing",
            "observed": "C1",
            "framework": "CEFR",
        },
    )
    res_valid = classify_proficiency_record(
        kind="ESTIMATED",
        framework="CEFR",
        level_or_score="C1",
        skill_scope="writing",
        evidence=cefr_evidence,
    )
    assert res_valid["kind"] == "ESTIMATED"
    assert res_valid["level_or_score"] == "C1"


def test_framework_mapping_source_value_and_applicability_required():
    """Mapping evidence must bind to source framework, target framework, source value, and target range."""
    # Missing source_value fails closed
    for bad_val in (None, "", "   ", float("nan"), float("inf"), True, False):
        res = evaluate_framework_mapping(
            source_framework="IELTS",
            source_value=bad_val,
            target_framework="CEFR",
            mapping_evidence=(
                {
                    "source_id": "c1",
                    "source_framework": "IELTS",
                    "source_value": "7.0",
                    "target_framework": "CEFR",
                    "target_range": "C1",
                },
            ),
        )
        assert res["calibrated"] is False
        assert res["target_estimate_range"] is None

    # Same framework with missing source_value fails closed
    res_same_bad = evaluate_framework_mapping(
        source_framework="CEFR",
        source_value=None,
        target_framework="CEFR",
    )
    assert res_same_bad["calibrated"] is False

    # Mapping record with wrong source framework fails closed
    res_wrong_src = evaluate_framework_mapping(
        source_framework="IELTS",
        source_value="7.0",
        target_framework="CEFR",
        mapping_evidence=(
            {
                "source_id": "c1",
                "source_framework": "TOEFL",
                "source_value": "7.0",
                "target_framework": "CEFR",
                "target_range": "C1",
            },
        ),
    )
    assert res_wrong_src["calibrated"] is False

    # Mapping record with wrong target framework fails closed
    res_wrong_tgt = evaluate_framework_mapping(
        source_framework="IELTS",
        source_value="7.0",
        target_framework="CEFR",
        mapping_evidence=(
            {
                "source_id": "c1",
                "source_framework": "IELTS",
                "source_value": "7.0",
                "target_framework": "DELE",
                "target_range": "C1",
            },
        ),
    )
    assert res_wrong_tgt["calibrated"] is False

    # Mapping record with wrong source value fails closed
    res_wrong_val = evaluate_framework_mapping(
        source_framework="IELTS",
        source_value="7.0",
        target_framework="CEFR",
        mapping_evidence=(
            {
                "source_id": "c1",
                "source_framework": "IELTS",
                "source_value": "5.0",
                "target_framework": "CEFR",
                "target_range": "B1",
            },
        ),
    )
    assert res_wrong_val["calibrated"] is False

    # Matching grounded mapping succeeds
    res_match = evaluate_framework_mapping(
        source_framework="IELTS",
        source_value="7.0",
        target_framework="CEFR",
        mapping_evidence=(
            {
                "source_id": "c1",
                "source_framework": "IELTS",
                "source_value": "7.0",
                "target_framework": "CEFR",
                "target_range": "C1",
            },
        ),
    )
    assert res_match["calibrated"] is True
    assert res_match["target_estimate_range"] == "C1"


def test_learning_load_semantic_inputs_mutation_sensitivity():
    """Priorities, review_backlog, deadlines, and recent_load semantically control recommendations."""
    base_res = evaluate_learning_load(available_time=30, energy="moderate")
    assert base_res["recommended_duration_minutes"] == 30
    assert base_res["load_status"] == "standard"

    # High recent load reduces duration/burden
    heavy_load_res = evaluate_learning_load(
        available_time=30,
        energy="moderate",
        recent_load={"hours": 5, "status": "high"},
    )
    assert (
        heavy_load_res["recommended_duration_minutes"]
        < base_res["recommended_duration_minutes"]
    )
    assert heavy_load_res["load_status"] == "scaffolded_light"
    assert heavy_load_res["recommended_duration_minutes"] <= 30
    assert heavy_load_res["calendar_modified"] is False

    # Urgent deadline prioritizes exam/prep activity
    deadline_res = evaluate_learning_load(
        available_time=30,
        energy="moderate",
        deadlines=({"id": "d1", "urgent": True},),
    )
    assert (
        "exam_practice" in deadline_res["recommended_activities"]
        or "targeted_practice" in deadline_res["recommended_activities"]
    )

    # Non-empty review backlog prioritizes spaced review
    backlog_res = evaluate_learning_load(
        available_time=30,
        energy="moderate",
        review_backlog=({"id": "b1"},),
    )
    assert "spaced_review" in backlog_res["recommended_activities"]

    # Explicit priorities influence recommended activities
    priority_res = evaluate_learning_load(
        available_time=30,
        energy="moderate",
        priorities=("writing_composition",),
    )
    assert "writing_composition" in priority_res["recommended_activities"]


def test_goal_alignment_approved_activity_contract_skills_and_purpose():
    """Activity skills (plural) and purpose fields are consumed for goal alignment."""
    goal = {"id": "g1", "kind": "conversation", "target": "fluency"}

    # Aligns via skills and purpose
    res_both = align_activity_to_goals(
        activity={"skills": ["speaking", "listening"], "purpose": "conversation"},
        goals=(goal,),
    )
    assert res_both["activity_fit"] == "aligned"
    assert res_both["aligned_goals"] == ["g1"]

    # Aligns via purpose only
    res_purpose = align_activity_to_goals(
        activity={"purpose": "conversation"},
        goals=(goal,),
    )
    assert res_purpose["activity_fit"] == "aligned"
    assert res_purpose["aligned_goals"] == ["g1"]

    # Aligns via skills only
    res_skills = align_activity_to_goals(
        activity={"skills": ["speaking"]},
        goals=(goal,),
    )
    assert res_skills["activity_fit"] == "aligned"
    assert res_skills["aligned_goals"] == ["g1"]

    # Unrelated activity fails closed
    res_unrelated = align_activity_to_goals(
        activity={"type": "unrelated_accounting", "purpose": "tax_filing"},
        goals=(goal,),
    )
    assert res_unrelated["activity_fit"] == "not_aligned"
    assert len(res_unrelated["aligned_goals"]) == 0


def test_malformed_evidence_container_fails_closed_across_all_helpers():
    """Non-iterable scalar/None/NaN/Inf/bool evidence containers fail closed safely without raising TypeError."""
    bad_containers = (
        None,
        True,
        False,
        42,
        float("nan"),
        float("inf"),
        object(),
        "invalid_string",
    )

    for bad in bad_containers:
        # classify_proficiency_record
        res_prof = classify_proficiency_record(
            kind="ESTIMATED",
            framework="CEFR",
            level_or_score="C1",
            evidence=bad,
        )
        assert isinstance(res_prof, dict)
        assert res_prof["level_or_score"] == "unassessed"

        # separate_skill_evidence
        res_sep = separate_skill_evidence(evidence=bad)
        assert isinstance(res_sep, dict)
        assert all(
            v["status"] == "insufficient_evidence" for v in res_sep["by_skill"].values()
        )
        assert res_sep["total_evidence_count"] == 0

        # evaluate_progression
        res_prog = evaluate_progression(
            previous_evidence=bad,
            current_evidence=bad,
            skill="writing",
        )
        assert isinstance(res_prog, dict)
        assert res_prog["progression_outcome"] == "insufficient_evidence"


def test_cultural_context_arbitrary_mapping_not_grounded():
    """Arbitrary unprovenanced mapping in cultural context is not labeled grounded evidence."""
    # Empty mapping
    res_empty = evaluate_cultural_context(claim="Native speakers do X", evidence=({},))
    assert res_empty["has_grounded_evidence"] is False
    assert res_empty["evidence_status"] == "weak_or_unprovenanced"

    # Arbitrary dict
    res_arbitrary = evaluate_cultural_context(
        claim="Native speakers do X", evidence=({"foo": "bar"},)
    )
    assert res_arbitrary["has_grounded_evidence"] is False
    assert res_arbitrary["evidence_status"] == "weak_or_unprovenanced"

    # Grounded evidence
    res_grounded = evaluate_cultural_context(
        claim="In Spain, direct forms are common",
        evidence=(
            {
                "source_id": "corpus-1",
                "reference_id": "ref-1",
                "observation": "common usage in Madrid",
            },
        ),
    )
    assert res_grounded["has_grounded_evidence"] is True
    assert res_grounded["evidence_status"] == "evidenced"


# ── Final Epistemic Invariant Consolidation RED Tests ─────────────────────────


def test_framework_mapping_incomplete_records_rejected():
    """Mapping evidence missing source_framework, source_value, target_framework, or target_range fails closed."""
    # 1. Missing source_framework, source_value, target_framework
    res_minimal = evaluate_framework_mapping(
        source_framework="IELTS",
        source_value="6.5",
        target_framework="CEFR",
        mapping_evidence=({"source_id": "conc-1", "target_range": "B2"},),
    )
    assert res_minimal["calibrated"] is False
    assert res_minimal["target_estimate_range"] is None

    # 2. Missing source_value, target_framework
    res_no_val = evaluate_framework_mapping(
        source_framework="IELTS",
        source_value="6.5",
        target_framework="CEFR",
        mapping_evidence=(
            {"source_framework": "IELTS", "source_id": "conc-1", "target_range": "B2"},
        ),
    )
    assert res_no_val["calibrated"] is False

    # 3. Missing source_framework, target_framework
    res_no_sfw = evaluate_framework_mapping(
        source_framework="IELTS",
        source_value="6.5",
        target_framework="CEFR",
        mapping_evidence=(
            {"source_value": "6.5", "source_id": "conc-1", "target_range": "B2"},
        ),
    )
    assert res_no_sfw["calibrated"] is False

    # 4. Missing source_framework, source_value
    res_no_sval = evaluate_framework_mapping(
        source_framework="IELTS",
        source_value="6.5",
        target_framework="CEFR",
        mapping_evidence=(
            {"target_framework": "CEFR", "source_id": "conc-1", "target_range": "B2"},
        ),
    )
    assert res_no_sval["calibrated"] is False

    # 5. Positive complete record calibrates
    res_complete = evaluate_framework_mapping(
        source_framework="IELTS",
        source_value="6.5",
        target_framework="CEFR",
        mapping_evidence=(
            {
                "source_id": "conc-1",
                "source_framework": "IELTS",
                "source_value": "6.5",
                "target_framework": "CEFR",
                "target_range": "B2",
            },
        ),
    )
    assert res_complete["calibrated"] is True
    assert res_complete["target_estimate_range"] == "B2"


def test_framework_mapping_textual_source_range_rejected():
    """Textual source_range without exact structured source_value cannot calibrate in final closure."""
    res = evaluate_framework_mapping(
        source_framework="IELTS",
        source_value="6.5",
        target_framework="CEFR",
        mapping_evidence=(
            {
                "source_id": "conc-1",
                "source_framework": "IELTS",
                "source_range": "6.5-7.5",
                "target_framework": "CEFR",
                "target_range": "B2",
            },
        ),
    )
    assert res["calibrated"] is False
    assert res["target_estimate_range"] is None


def test_evaluate_level_update_cross_framework_leakage_blocked():
    """Cross-framework evidence cannot update a CEFR level directly via ACTFL identity."""
    existing = {
        "kind": "ESTIMATED",
        "level_or_score": "B2",
        "skill_scope": "writing",
        "framework": "CEFR",
    }
    actfl_evidence = (
        {
            "provenance_id": "p1",
            "skill": "writing",
            "observed": "C1",
            "framework": "ACTFL",
            "comparable": True,
            "comparison_key": "essay",
        },
        {
            "provenance_id": "p2",
            "skill": "writing",
            "observed": "C1",
            "framework": "ACTFL",
            "comparable": True,
            "comparison_key": "essay",
        },
    )
    res = evaluate_level_update(
        existing=existing, evidence=actfl_evidence, target_skill="writing"
    )
    assert res["stable_update_supported"] is False
    assert res["proposed_level"] == "B2"


def test_evaluate_level_update_preserves_framework():
    """A valid stable level update preserves explicit framework in updated_record."""
    existing = {
        "kind": "ESTIMATED",
        "level_or_score": "B2",
        "skill_scope": "writing",
        "framework": "CEFR",
    }
    cefr_evidence = (
        {
            "provenance_id": "p1",
            "skill": "writing",
            "observed": "C1",
            "framework": "CEFR",
            "comparable": True,
            "comparison_key": "essay",
        },
        {
            "provenance_id": "p2",
            "skill": "writing",
            "observed": "C1",
            "framework": "CEFR",
            "comparable": True,
            "comparison_key": "essay",
        },
    )
    res = evaluate_level_update(
        existing=existing, evidence=cefr_evidence, target_skill="writing"
    )
    assert res["stable_update_supported"] is True
    assert res["proposed_level"] == "C1"
    assert res["updated_record"].get("framework") == "CEFR"


@pytest.mark.parametrize(
    "occurrence_alias", ("session_id", "sample_id", "assessment_id", "context_id")
)
def test_certification_source_authority_occurrence_aliases_not_authoritative(
    occurrence_alias,
):
    """Generic occurrence identifiers cannot confer certification source authority."""
    src = {
        "id": "s1",
        "source_type": "official",
        "temporal_state": "current",
        occurrence_alias: "occurrence-123",
    }
    res = evaluate_certification_source(sources=(src,), decision_critical=True)
    assert res["authority_rank"] != 6
    assert res["needs_verification"] is True


def test_goal_alignment_generic_practice_not_universal():
    """Generic practice does not automatically align all concurrent goals without semantic relevance."""
    goals = (
        {"id": "g_cert", "kind": "certification", "target": "C1 Exam"},
        {"id": "g_conv", "kind": "conversation", "target": "Daily fluency"},
    )
    res = align_activity_to_goals(
        activity={"type": "practice"},
        goals=goals,
    )
    assert set(res["aligned_goals"]) != {"g_cert", "g_conv"}


def test_learning_load_bool_numeric_deadline_days_remaining_rejected():
    """Boolean days_remaining=True cannot trigger urgent exam practice."""
    res = evaluate_learning_load(
        available_time=30,
        energy="moderate",
        deadlines=({"id": "d1", "days_remaining": True},),
    )
    assert "exam_practice" not in res["recommended_activities"]


# ── Cross-Path Invariant Meta-Tests Suite ─────────────────────────────────────


@pytest.mark.parametrize(
    "helper_call",
    [
        lambda ev: classify_proficiency_record(
            kind="ESTIMATED", framework="CEFR", level_or_score="B2", evidence=ev
        ),
        lambda ev: evaluate_error_pattern(observations=ev),
        lambda ev: adapt_difficulty(current_difficulty=2, performance=ev),
        lambda ev: evaluate_progression(
            previous_evidence=ev, current_evidence=ev, skill="writing"
        ),
        lambda ev: evaluate_cultural_context(claim="Specific claim", evidence=ev),
    ],
)
def test_meta_all_evidence_helpers_reject_unprovenanced_records(helper_call):
    """Every evidence-consuming rule helper strictly rejects records without canonical provenance."""
    unprovenanced_record = {
        "score": 0.8,
        "observed": "B2",
        "comparable": True,
        "comparison_key": "k1",
        "skill": "writing",
    }
    res = helper_call((unprovenanced_record,))
    assert isinstance(res, dict)
    # Check that unprovenanced record was not treated as valid grounded evidence
    if "level_or_score" in res:
        assert res["level_or_score"] == "unassessed"
    if "eligible" in res:
        assert res["eligible"] is False
    if "action" in res:
        assert res["action"] == "insufficient_evidence"
    if "progression_outcome" in res:
        assert res["progression_outcome"] == "insufficient_evidence"
    if "has_grounded_evidence" in res:
        assert res["has_grounded_evidence"] is False


@pytest.mark.parametrize(
    "source_fw,target_fw",
    [
        ("CEFR", "ACTFL"),
        ("ACTFL", "CEFR"),
        ("IELTS", "TOEFL"),
        ("TOEFL", "IELTS"),
        ("CEFR", "IELTS"),
    ],
)
def test_meta_cross_framework_direct_identity_always_forbidden(source_fw, target_fw):
    """Direct cross-framework identity is unconditionally forbidden without grounded concordance."""
    res = evaluate_framework_mapping(
        source_framework=source_fw,
        source_value="B2",
        target_framework=target_fw,
        mapping_evidence=(),
    )
    assert res["calibrated"] is False
    assert res["target_estimate_range"] is None
    assert res["mapping_status"] in {"identity_forbidden", "insufficient_evidence"}


@pytest.mark.parametrize(
    "bad_numeric",
    [
        True,
        False,
        float("nan"),
        float("inf"),
        float("-inf"),
        "0.8",
        [0.8],
        {"val": 0.8},
    ],
)
def test_meta_all_numeric_fields_fail_closed_on_non_finite_or_bool(bad_numeric):
    """All numeric fields across domain rules reject bool, NaN, Inf, string, and collection values."""
    # 1. Proficiency score
    res_prof = classify_proficiency_record(
        kind="ESTIMATED",
        framework="CEFR",
        level_or_score=bad_numeric,
        evidence=(
            {
                "provenance_id": "p1",
                "score": bad_numeric,
                "comparable": True,
                "comparison_key": "k1",
            },
        ),
    )
    assert res_prof["level_or_score"] == "unassessed"

    # 2. Adaptive difficulty current_difficulty & score
    res_diff = adapt_difficulty(
        current_difficulty=bad_numeric,
        performance=(
            {
                "provenance_id": "p1",
                "score": bad_numeric,
                "comparable": True,
                "comparison_key": "k1",
            },
        ),
    )
    assert res_diff["action"] == "insufficient_evidence"

    # 3. Spaced review mastery / recall / importance
    res_sr = plan_spaced_review(
        items=(
            {
                "id": "v1",
                "mastery": bad_numeric,
                "recall": bad_numeric,
                "importance": bad_numeric,
                "due": True,
            },
        ),
    )
    assert len(res_sr["prioritized_items"]) == 1

    # 4. Learning load available_time
    res_load = evaluate_learning_load(available_time=bad_numeric)
    assert res_load["load_status"] == "insufficient_constraints"
    assert res_load["recommended_duration_minutes"] == 0

    # 5. Error pattern minimum_independent_occurrences
    res_ep = evaluate_error_pattern(
        observations=(
            {
                "provenance_id": "p1",
                "error_type": "tense",
                "comparable": True,
                "comparison_key": "k1",
            },
        ),
        minimum_independent_occurrences=bad_numeric,
    )
    assert res_ep["eligible"] is False


@pytest.mark.parametrize(
    "generic_id_field", ["session_id", "sample_id", "assessment_id", "context_id"]
)
def test_meta_generic_occurrence_ids_never_grant_certification_authority(
    generic_id_field,
):
    """Generic occurrence identifiers never confer certification authority rank 6 or bypass verification."""
    source = {
        "id": "s1",
        "source_type": "official",
        "temporal_state": "current",
        generic_id_field: "occurrence-abc",
    }
    res = evaluate_certification_source(sources=(source,), decision_critical=True)
    assert res["authority_rank"] < 6
    assert res["needs_verification"] is True


def test_meta_goal_alignment_requires_explicit_semantic_link():
    """Goal alignment never matches without explicit goal ID, matching skill, or matching specific purpose."""
    goals = (
        {
            "id": "goal_reading",
            "kind": "reading",
            "skill": "reading",
            "target": "academic articles",
        },
        {
            "id": "goal_speaking",
            "kind": "conversation",
            "skill": "speaking",
            "target": "fluency in travel",
        },
    )
    # Generic practice without matching skill/topic/purpose
    res_generic = align_activity_to_goals(activity={"type": "practice"}, goals=goals)
    assert res_generic["activity_fit"] == "not_aligned"
    assert res_generic["aligned_goals"] == []

    # Specific reading activity only matches reading goal
    res_reading = align_activity_to_goals(
        activity={"type": "article_reading", "skill": "reading"}, goals=goals
    )
    assert res_reading["activity_fit"] == "aligned"
    assert res_reading["aligned_goals"] == ["goal_reading"]

    # Specific speaking activity only matches speaking goal
    res_speaking = align_activity_to_goals(
        activity={"type": "roleplay", "skill": "speaking"}, goals=goals
    )
    assert res_speaking["activity_fit"] == "aligned"
    assert res_speaking["aligned_goals"] == ["goal_speaking"]


def test_red_certified_mismatched_framework_result_skill_rejected() -> None:
    """ACTFL B1 speaking certificate requested as CEFR C2 writing fails closed."""
    res = classify_proficiency_record(
        kind="CERTIFIED",
        framework="CEFR",
        level_or_score="C2",
        skill_scope="writing",
        evidence=(
            {
                "source_kind": "official_certificate",
                "official_source_id": "official-1",
                "certificate_id": "cert-1",
                "framework": "ACTFL",
                "skill": "speaking",
                "observed": "B1",
                "result": "B1",
                "valid_at": "2026-01-01",
            },
        ),
    )
    assert res["is_certified"] is False
    assert res["level_or_score"] == "unassessed"
    assert res["confidence"] == 0.0


def test_red_certified_sparse_record_rejected() -> None:
    """Sparse certificate missing framework, result, or date fails closed."""
    res = classify_proficiency_record(
        kind="CERTIFIED",
        framework="CEFR",
        level_or_score="C2",
        skill_scope="writing",
        evidence=(
            {
                "source_kind": "official_certificate",
                "source_id": "official-2",
                "certificate_id": "cert-2",
            },
        ),
    )
    assert res["is_certified"] is False
    assert res["level_or_score"] == "unassessed"
    assert res["confidence"] == 0.0


def test_red_certified_complete_matching_record_accepted() -> None:
    """Complete matching certificate passes with confidence=0.95."""
    res = classify_proficiency_record(
        kind="CERTIFIED",
        framework="CEFR",
        level_or_score="B1",
        skill_scope="general",
        evidence=(
            {
                "source_kind": "official_certificate",
                "source_id": "official-certificate-record",
                "certificate_id": "certificate-B1",
                "framework": "CEFR",
                "result": "B1",
                "valid_at": "2026-01-01",
            },
        ),
    )
    assert res["kind"] == "CERTIFIED"
    assert res["is_certified"] is True
    assert res["level_or_score"] == "B1"
    assert res["framework"] == "CEFR"
    assert res["confidence"] == 0.95


def test_red_no_implicit_cefr_fallback() -> None:
    """Omitting framework with ACTFL evidence infers ACTFL, never CEFR."""
    res = classify_proficiency_record(
        kind="ESTIMATED",
        framework=None,
        level_or_score="C1",
        skill_scope="writing",
        evidence=(
            {
                "provenance_id": "p1",
                "framework": "ACTFL",
                "skill": "writing",
                "observed": "C1",
            },
            {
                "provenance_id": "p2",
                "framework": "ACTFL",
                "skill": "writing",
                "observed": "C1",
            },
        ),
    )
    assert res["framework"] == "ACTFL"
    assert res["level_or_score"] == "C1"


@pytest.mark.parametrize(
    "occurrence_field",
    ["provenance_id", "assessment_id", "sample_id", "context_id", "session_id"],
)
def test_red_mapping_occurrence_aliases_not_source_authority(
    occurrence_field: str,
) -> None:
    """Framework mapping rejects generic occurrence IDs as concordance authority."""
    evidence = {
        occurrence_field: "concordance-v1",
        "source_framework": "IELTS",
        "source_value": "6.5",
        "target_framework": "CEFR",
        "target_range": "B2",
    }
    result = evaluate_framework_mapping(
        source_framework="IELTS",
        source_value="6.5",
        target_framework="CEFR",
        mapping_evidence=(evidence,),
    )
    assert result["calibrated"] is False
    assert result["target_estimate_range"] is None


@pytest.mark.parametrize("source_field", ["source_id", "official_source_id"])
def test_red_mapping_source_fields_accepted(source_field: str) -> None:
    """Framework mapping accepts dedicated source-role authority fields."""
    evidence = {
        source_field: "concordance-v1",
        "source_framework": "IELTS",
        "source_value": "6.5",
        "target_framework": "CEFR",
        "target_range": "B2",
    }
    result = evaluate_framework_mapping(
        source_framework="IELTS",
        source_value="6.5",
        target_framework="CEFR",
        mapping_evidence=(evidence,),
    )
    assert result["calibrated"] is True
    assert result["target_estimate_range"] == "B2"


def test_red_cert_auth_provenance_id_not_source() -> None:
    """Certification source authority rejects provenance_id alone."""
    source = {
        "id": "s1",
        "source_type": "official",
        "temporal_state": "current",
        "provenance_id": "user-session-evidence",
    }
    res = evaluate_certification_source(sources=(source,), decision_critical=True)
    assert res["authority_rank"] < 6
    assert res["needs_verification"] is True


@pytest.mark.parametrize("source_field", ["source_id", "official_source_id"])
def test_red_cert_auth_source_fields_accepted(source_field: str) -> None:
    """Certification source authority accepts official_source_id and source_id."""
    source = {
        "id": "s1",
        "source_type": "official",
        "temporal_state": "current",
        source_field: "official-inst-1",
    }
    res = evaluate_certification_source(sources=(source,), decision_critical=True)
    assert res["authority_rank"] == 6
    assert res["needs_verification"] is False


def test_red_general_estimate_from_writing_rejected() -> None:
    """Two writing observations cannot directly establish a general ESTIMATED record."""
    res = classify_proficiency_record(
        kind="ESTIMATED",
        framework="CEFR",
        level_or_score="B1",
        skill_scope="general",
        evidence=(
            {
                "provenance_id": "p1",
                "framework": "CEFR",
                "skill": "writing",
                "observed": "B1",
            },
            {
                "provenance_id": "p2",
                "framework": "CEFR",
                "skill": "writing",
                "observed": "B1",
            },
        ),
    )
    assert res["level_or_score"] == "unassessed"
    assert res["confidence"] == 0.0


def test_red_general_observed_from_writing_rejected() -> None:
    """One writing observation cannot directly establish a general OBSERVED_PERFORMANCE record."""
    res = classify_proficiency_record(
        kind="OBSERVED_PERFORMANCE",
        framework="CEFR",
        level_or_score="B1",
        skill_scope="general",
        evidence=(
            {
                "provenance_id": "p1",
                "framework": "CEFR",
                "skill": "writing",
                "observed": "B1",
            },
        ),
    )
    assert res["level_or_score"] == "unassessed"
    assert res["confidence"] == 0.0


def test_red_general_level_update_from_writing_rejected() -> None:
    """Writing-only comparable evidence cannot update general proficiency."""
    res = evaluate_level_update(
        existing={
            "kind": "ESTIMATED",
            "framework": "CEFR",
            "level_or_score": "B1",
            "skill_scope": "general",
        },
        evidence=(
            {
                "provenance_id": "p1",
                "framework": "CEFR",
                "skill": "writing",
                "observed": "B2",
                "comparable": True,
                "comparison_key": "k1",
            },
            {
                "provenance_id": "p2",
                "framework": "CEFR",
                "skill": "writing",
                "observed": "B2",
                "comparable": True,
                "comparison_key": "k1",
            },
        ),
    )
    assert res["stable_update_supported"] is False


def test_red_general_progression_from_writing_rejected() -> None:
    """Writing-only progression with skill=None or 'general' cannot become stable general progression."""
    res = evaluate_progression(
        previous_evidence=(
            {
                "provenance_id": "p1",
                "skill": "writing",
                "score": 0.50,
                "comparable": True,
                "comparison_key": "essay-1",
            },
        ),
        current_evidence=(
            {
                "provenance_id": "c1",
                "skill": "writing",
                "score": 0.80,
                "comparable": True,
                "comparison_key": "essay-1",
            },
            {
                "provenance_id": "c2",
                "skill": "writing",
                "score": 0.82,
                "comparable": True,
                "comparison_key": "essay-1",
            },
        ),
        skill=None,
    )
    assert res["stable_progression"] is False
    assert res["progression_outcome"] == "insufficient_evidence"


def test_red_unknown_classify_scope_rejected() -> None:
    """Unknown non-canonical skill scope fails closed."""
    res = classify_proficiency_record(
        kind="ESTIMATED",
        framework="CEFR",
        level_or_score="B1",
        skill_scope="foobar",
        evidence=(
            {
                "provenance_id": "p1",
                "framework": "CEFR",
                "skill": "foobar",
                "observed": "B1",
            },
            {
                "provenance_id": "p2",
                "framework": "CEFR",
                "skill": "foobar",
                "observed": "B1",
            },
        ),
    )
    assert res["level_or_score"] == "unassessed"
    assert res["confidence"] == 0.0


def test_red_unknown_level_update_scope_rejected() -> None:
    """Unknown target skill in evaluate_level_update fails closed."""
    res = evaluate_level_update(
        existing={
            "kind": "ESTIMATED",
            "framework": "CEFR",
            "level_or_score": "B1",
            "skill_scope": "writing",
        },
        evidence=(
            {
                "provenance_id": "p1",
                "framework": "CEFR",
                "skill": "foobar",
                "observed": "B2",
                "comparable": True,
                "comparison_key": "k1",
            },
            {
                "provenance_id": "p2",
                "framework": "CEFR",
                "skill": "foobar",
                "observed": "B2",
                "comparable": True,
                "comparison_key": "k1",
            },
        ),
        target_skill="foobar",
    )
    assert res["stable_update_supported"] is False


def test_red_specific_writing_scope_still_accepted() -> None:
    """Specific writing evidence continues to ground writing proficiency."""
    res = classify_proficiency_record(
        kind="ESTIMATED",
        framework="CEFR",
        level_or_score="B1",
        skill_scope="writing",
        evidence=(
            {
                "provenance_id": "p1",
                "framework": "CEFR",
                "skill": "writing",
                "observed": "B1",
            },
            {
                "provenance_id": "p2",
                "framework": "CEFR",
                "skill": "writing",
                "observed": "B1",
            },
        ),
    )
    assert res["kind"] == "ESTIMATED"
    assert res["level_or_score"] == "B1"
    assert res["skill_scope"] == "writing"
    assert res["confidence"] == 0.75


def test_red_explicit_global_evidence_accepted_if_contract_supports_it() -> None:
    """Explicitly general or overall evidence grounds general proficiency."""
    res_gen = classify_proficiency_record(
        kind="ESTIMATED",
        framework="CEFR",
        level_or_score="B1",
        skill_scope="general",
        evidence=(
            {
                "provenance_id": "p1",
                "framework": "CEFR",
                "skill": "general",
                "observed": "B1",
            },
            {
                "provenance_id": "p2",
                "framework": "CEFR",
                "skill": "general",
                "observed": "B1",
            },
        ),
    )
    assert res_gen["kind"] == "ESTIMATED"
    assert res_gen["level_or_score"] == "B1"
    assert res_gen["skill_scope"] == "general"


def test_red_ungrounded_framework_tag_cannot_select_framework() -> None:
    """Ungrounded framework tag cannot select framework for framework-neutral evidence."""
    res = classify_proficiency_record(
        kind="ESTIMATED",
        framework=None,
        level_or_score="C1",
        skill_scope="writing",
        evidence=(
            {"framework": "IELTS"},  # no provenance, no observation
            {"provenance_id": "p1", "skill": "writing", "observed": "C1"},
            {"provenance_id": "p2", "skill": "writing", "observed": "C1"},
        ),
    )
    assert res["framework"] != "IELTS"


def test_red_grounded_framework_inference_only() -> None:
    """Framework is inferred only from grounded evidence."""
    res = classify_proficiency_record(
        kind="ESTIMATED",
        framework=None,
        level_or_score="C1",
        skill_scope="writing",
        evidence=(
            {
                "provenance_id": "p1",
                "framework": "ACTFL",
                "skill": "writing",
                "observed": "C1",
            },
            {
                "provenance_id": "p2",
                "framework": "ACTFL",
                "skill": "writing",
                "observed": "C1",
            },
        ),
    )
    assert res["framework"] == "ACTFL"
    assert res["level_or_score"] == "C1"


def test_red_mixed_grounded_frameworks_fail_closed() -> None:
    """Mixed grounded frameworks fail closed."""
    res = classify_proficiency_record(
        kind="ESTIMATED",
        framework=None,
        level_or_score="C1",
        skill_scope="writing",
        evidence=(
            {
                "provenance_id": "p1",
                "framework": "ACTFL",
                "skill": "writing",
                "observed": "C1",
            },
            {
                "provenance_id": "p2",
                "framework": "CEFR",
                "skill": "writing",
                "observed": "C1",
            },
        ),
    )
    assert res["level_or_score"] == "unassessed"
    assert res["confidence"] == 0.0


def test_red_level_update_missing_framework_no_cefr_default() -> None:
    """Missing framework in evaluate_level_update never defaults to CEFR."""
    res = evaluate_level_update(
        existing={
            "kind": "ESTIMATED",
            "level_or_score": "B1",
            "skill_scope": "writing",
        },
        evidence=(
            {
                "provenance_id": "p1",
                "skill": "writing",
                "observed": "B2",
                "comparable": True,
                "comparison_key": "k1",
            },
            {
                "provenance_id": "p2",
                "skill": "writing",
                "observed": "B2",
                "comparable": True,
                "comparison_key": "k1",
            },
        ),
    )
    assert res["stable_update_supported"] is False
    assert res.get("updated_record", {}).get("framework") != "CEFR"


def test_red_cert_invalid_date_string_rejected() -> None:
    """Certificate with invalid date string ('banana') is rejected."""
    res = classify_proficiency_record(
        kind="CERTIFIED",
        framework="CEFR",
        level_or_score="B1",
        skill_scope="general",
        evidence=(
            {
                "source_kind": "official_certificate",
                "source_id": "official-1",
                "certificate_id": "cert-1",
                "framework": "CEFR",
                "result": "B1",
                "valid_at": "banana",
            },
        ),
    )
    assert res["is_certified"] is False
    assert res["certification_evidence_valid"] is False
    assert res["level_or_score"] == "unassessed"


def test_red_cert_empty_date_rejected() -> None:
    """Certificate with empty date string is rejected."""
    res = classify_proficiency_record(
        kind="CERTIFIED",
        framework="CEFR",
        level_or_score="B1",
        skill_scope="general",
        evidence=(
            {
                "source_kind": "official_certificate",
                "source_id": "official-1",
                "certificate_id": "cert-1",
                "framework": "CEFR",
                "result": "B1",
                "valid_at": "",
            },
        ),
    )
    assert res["is_certified"] is False
    assert res["certification_evidence_valid"] is False
    assert res["level_or_score"] == "unassessed"


def test_red_cert_valid_iso_date_accepted() -> None:
    """Certificate with valid ISO date string is accepted."""
    res = classify_proficiency_record(
        kind="CERTIFIED",
        framework="CEFR",
        level_or_score="B1",
        skill_scope="general",
        evidence=(
            {
                "source_kind": "official_certificate",
                "source_id": "official-1",
                "certificate_id": "cert-1",
                "framework": "CEFR",
                "result": "B1",
                "valid_at": "2026-01-01",
            },
        ),
    )
    assert res["kind"] == "CERTIFIED"
    assert res["is_certified"] is True
    assert res["certification_evidence_valid"] is True
    assert res["level_or_score"] == "B1"
    assert res["confidence"] == 0.95
