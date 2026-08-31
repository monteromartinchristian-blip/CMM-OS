"""Phase 10.25 — Audit-remediation regression tests for support-need
precedence, repetitive-certainty grounding, and explicit wait/no-advice intent.

Remediates I-001 (lower-precedence signals override explicit SupportNeed),
I-002 (same_question fabricates impossible-certainty pursuit), and I-003
(explicit wait/no-advice is detected then discarded).
"""

from __future__ import annotations

import json

from cmm.domains.concerns.rules import (
    ACTION_NO_ACTION_NEEDED,
    DOMAIN_ESCALATION_NEEDED,
    SUPPORT_EMOTIONAL_PROCESSING,
    SUPPORT_MIXED,
    SUPPORT_PERSPECTIVE,
    SUPPORT_REASSURANCE,
    evaluate_action_state,
    evaluate_repetitive_certainty_pattern,
    infer_support_need,
)

# ═════════════════════════════════════════════════════════════════════════════
# I-001: SupportNeed tiered precedence
# ═════════════════════════════════════════════════════════════════════════════


def test_explicit_reassurance_beats_conflicting_current_signal():
    """Explicit current request (highest tier) wins over a conflicting clear
    current signal; MIXED is forbidden from lower tiers."""
    record = infer_support_need(
        explicit_request="Can you reassure me",
        current_signal="Tell me what you think",
    )
    assert record["support_need"] != SUPPORT_MIXED
    assert record["support_need"] == SUPPORT_REASSURANCE
    assert record["basis"] == "explicit_current_request"


def test_explicit_no_advice_beats_problem_solving_current_signal():
    """'No advice, I just need to talk' beats 'What can I do?' without
    becoming MIXED and without enabling problem solving."""
    record = infer_support_need(
        explicit_request="No advice, I just need to talk",
        current_signal="What can I do?",
    )
    assert record["support_need"] != SUPPORT_MIXED
    assert record["support_need"] == SUPPORT_EMOTIONAL_PROCESSING
    assert record["problem_solving_allowed"] is False


def test_explicit_request_beats_conflicting_session_context():
    """Recent session context must not override or MIX with the explicit
    current request."""
    record = infer_support_need(
        explicit_request="Tell me what you think",
        session_context={"current_turn_signal": "what can i do"},
    )
    assert record["support_need"] != SUPPORT_MIXED
    assert record["support_need"] == SUPPORT_PERSPECTIVE


def test_mixed_is_allowed_only_within_highest_precedence_source():
    """MIXED is legitimate only when the HIGHEST-precedence source itself
    clearly expresses multiple concurrent needs — not when lower tiers add
    components."""
    mixed_within_explicit = infer_support_need(
        explicit_request="Tell me what you think, then help me decide",
    )
    assert mixed_within_explicit["support_need"] == SUPPORT_MIXED
    assert SUPPORT_PERSPECTIVE in mixed_within_explicit["components"]

    # Lower-tier conflict never expands the explicit tier into MIXED.
    not_mixed = infer_support_need(
        explicit_request="Tell me what you think",
        current_signal="What can I do?",
        session_context={"current_turn_signal": "Can you reassure me"},
    )
    assert not_mixed["support_need"] == SUPPORT_PERSPECTIVE
    assert not_mixed["support_need"] != SUPPORT_MIXED


# ═════════════════════════════════════════════════════════════════════════════
# I-002: same_question must never imply impossible-certainty pursuit
# ═════════════════════════════════════════════════════════════════════════════


def test_same_question_unchanged_evidence_and_relief_is_not_certainty_pattern_without_certainty_pursuit():
    """Four turns with same question + unchanged evidence + relief/checking +
    multiple turns but WITHOUT any certainty-pursuit marker: pattern must NOT
    be detected (every dimension independently grounded)."""
    turns = (
        {"turn": 1, "same_question": True, "evidence_state": "unchanged"},
        {"turn": 2, "same_question": True, "evidence_state": "unchanged"},
        {"turn": 3, "same_question": True, "evidence_state": "unchanged"},
        {"turn": 4, "same_question": True, "relief_followed_by_checking": True},
    )
    record = evaluate_repetitive_certainty_pattern(turns=turns)
    assert record["pattern_detected"] is False
    assert "impossible_certainty_pursuit" not in record["dimensions_present"]
    # Non-negotiable safety outcomes still hold.
    assert record["pathology_inferred"] is False
    assert record["reassurance_allowed"] is True


def test_explicit_certainty_pursuit_with_all_other_dimensions_yields_true():
    """An explicit certainty-pursuit marker plus the other grounded dimensions
    → pattern detected True."""
    turns = (
        {
            "turn": 1,
            "same_question": True,
            "evidence_state": "unchanged",
            "pursuing_certainty": True,
        },
        {
            "turn": 2,
            "same_question": True,
            "evidence_state": "unchanged",
            "pursuing_certainty": True,
        },
        {
            "turn": 3,
            "same_question": True,
            "evidence_state": "unchanged",
            "impossible_certainty": True,
        },
        {
            "turn": 4,
            "same_question": True,
            "relief_followed_by_checking": True,
            "pursuing_certainty": True,
        },
    )
    record = evaluate_repetitive_certainty_pattern(turns=turns)
    assert record["pattern_detected"] is True
    assert "impossible_certainty_pursuit" in record["dimensions_present"]
    assert record["pathology_inferred"] is False
    assert record["psychiatric_label"] is False


# ═════════════════════════════════════════════════════════════════════════════
# I-003: explicit wait / no-advice → NO_ACTION_NEEDED
# ═════════════════════════════════════════════════════════════════════════════


def test_explicit_wait_yields_no_action_needed_without_immediate_risk():
    """'I want to wait' with options but no grounded immediate specialized
    risk must yield NO_ACTION_NEEDED, never ACTION_OPTIONAL."""
    record = evaluate_action_state(
        options=("contact them now",),
        user_request="I want to wait.",
    )
    assert record["state"] == ACTION_NO_ACTION_NEEDED


def test_explicit_no_advice_yields_no_action_needed():
    """'No advice, I just need to talk' must yield NO_ACTION_NEEDED even when
    options exist."""
    record = evaluate_action_state(
        options=("contact them now",),
        user_request="No advice, I just need to talk.",
    )
    assert record["state"] == ACTION_NO_ACTION_NEEDED


def test_immediate_specialized_risk_can_override_wait_only_for_domain_escalation():
    """Only grounded immediate specialized risk overrides explicit wait, and
    only to DOMAIN_ESCALATION_NEEDED — never to a personal adopted action."""
    record = evaluate_action_state(
        options=("contact them now",),
        user_request="I want to wait.",
        urgency="now",
        specialized_domain_result={
            "domain_id": "domain:health",
            "red_flags": ("imminent danger signal",),
            "authorized": True,
        },
    )
    assert record["state"] == DOMAIN_ESCALATION_NEEDED
    assert record["decision_adopted"] is False
    assert record["external_action_executed"] is False


def test_just_talking_not_action_optional():
    wait = evaluate_action_state(
        options=("say something",),
        user_request="I just need to talk.",
    )
    assert wait["state"] == ACTION_NO_ACTION_NEEDED
    json.dumps(wait, allow_nan=False)
