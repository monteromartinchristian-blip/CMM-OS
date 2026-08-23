"""Phase 10.26 — Languages Domain Adversarial & Failure-Mode Suite."""

from __future__ import annotations

from cmm.domains.languages.operations import (
    prepare_certification_result,
    review_speaking_result,
    update_level_evidence_result,
)
from cmm.domains.languages.permissions import (
    permission_authorization_allows,
)
from cmm.domains.languages.rules import (
    adapt_difficulty,
    classify_language_variety,
    evaluate_framework_mapping,
    evaluate_language_memory_consent,
)


def test_adversarial_certified_level_overwrite_attempt() -> None:
    """A higher observed sample must NEVER overwrite a certified proficiency record."""
    cert = {"kind": "CERTIFIED", "level_or_score": "B1", "framework": "CEFR", "evidence": [{"id": "c1"}]}
    ass = {"observed_performance": "C2", "skill": "writing"}
    res = update_level_evidence_result(existing_record=cert, assessment=ass, target_skill="writing")
    assert res["is_certified"] is True
    assert res["stable_update_supported"] is False
    assert res["proposed_level"] == "B1"


def test_adversarial_malformed_consent_strings() -> None:
    """String 'true', 'yes', 1, dicts must never authorize persistence."""
    for bad_consent in ("true", "TRUE", "yes", 1, 0, 1.0, {"consent": True}, [True]):
        eval_res = evaluate_language_memory_consent(content_kind="profile", session_only=False, consent=bad_consent)
        assert eval_res["persistence_authorized"] is False
        assert permission_authorization_allows(bad_consent) is False


def test_adversarial_audio_transcript_hallucination_prevention() -> None:
    """Text transcript alone must NEVER claim to have assessed pronunciation."""
    res = review_speaking_result(
        audio_transcript={"transcript": "Every sound was pronounced perfectly."},
        target_language="English",
        pronunciation_evidence=None,
    )
    assert res["pronunciation_assessed"] is False
    assert res["pronunciation_feedback"] is None


def test_adversarial_variety_difference_as_error_rejection() -> None:
    """A valid regional variety difference must never be classified as an error."""
    var_res = classify_language_variety(
        preferred_variety="Mexican Spanish",
        observed_variety="Peninsular Spanish",
        form_status="valid",
    )
    assert var_res["is_valid_alternative"] is True
    assert var_res["error_rejected"] is True


def test_adversarial_one_session_regression_not_stable() -> None:
    """A single bad session must not downgrade stable proficiency."""
    diff_res = adapt_difficulty(current_difficulty=3, performance=[{"score": 0.1}], stable_proficiency="B2")
    assert diff_res["stable_proficiency_changed"] is False
    assert diff_res["action"] != "stable_regression"


def test_adversarial_certification_auto_registration_prevention() -> None:
    """Certification prep must never perform external registration or payment."""
    res = prepare_certification_result(target_certification="DELE C1")
    assert res["registration_performed"] is False
    assert res["payment_performed"] is False
    assert res["submission_performed"] is False


def test_adversarial_unsupported_framework_mapping() -> None:
    """Mapping between unknown or uncalibrated frameworks must return unsupported_framework."""
    res = evaluate_framework_mapping(
        source_framework="UNKNOWN_FRAMEWORK",
        source_value="Level 5",
        target_framework="CEFR",
    )
    assert res["mapping_status"] == "unsupported_framework"
    assert res["calibrated"] is False
