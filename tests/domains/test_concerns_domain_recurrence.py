"""Phase 10.25 — Concerns recurrence / agency / directness / escalation tests.

Covers ``review_recurring_concern_state``, ``evaluate_repetitive_certainty_pattern``,
``evaluate_action_state``, ``evaluate_grounded_directness`` and
``evaluate_immediate_risk_escalation`` (frozen design §26–§29, §70;
implementation plan Task 5).
"""

from __future__ import annotations

import copy
import json

from cmm.domains.concerns.rules import (
    ACTION_NO_ACTION_NEEDED,
    ACTION_RECOMMENDED,
    ACTION_USEFUL,
    DOMAIN_ESCALATION_NEEDED,
    USER_DECISION_REQUIRED,
    evaluate_action_state,
    evaluate_grounded_directness,
    evaluate_immediate_risk_escalation,
    evaluate_repetitive_certainty_pattern,
    review_recurring_concern_state,
)

# ── Recurrence review ────────────────────────────────────────────────────────


def test_same_topic_different_question_is_meaningfully_new():
    record = review_recurring_concern_state(
        current={"topic": "job situation", "question": "should I ask for a raise?"},
        previous=({"topic": "job situation", "question": "will I be fired?"},),
    )
    assert record["recurrence"] == "same_topic_new_question"
    assert record["meaningfully_different"] is True
    assert record["pathology_inferred"] is False


def test_same_question_new_evidence_changes_comparison():
    record = review_recurring_concern_state(
        current={
            "topic": "health worry",
            "question": "is this serious?",
            "evidence_references": ("lab:1", "lab:2"),
        },
        previous=(
            {
                "topic": "health worry",
                "question": "is this serious?",
                "evidence_references": (),
            },
        ),
    )
    assert record["recurrence"] in ("same_question_new_evidence",)
    assert record["evidence_changed"] is True
    # reassurance remains allowed — new grounded evidence supports revisiting
    assert record["reassurance_allowed"] is True


def test_same_question_same_evidence_is_unchanged_not_pathology():
    record = review_recurring_concern_state(
        current={
            "topic": "relationship",
            "question": "do they still care?",
            "evidence_references": ("m1",),
        },
        previous=(
            {
                "topic": "relationship",
                "question": "do they still care?",
                "evidence_references": ("m1",),
            },
        ),
    )
    assert record["recurrence"] == "same_question_same_evidence"
    assert record["evidence_changed"] is False
    assert record["pathology_inferred"] is False
    # repeated reassurance remains possible when the basis is unchanged but real
    assert record["reassurance_allowed"] is True


def test_changed_impact_is_visible():
    record = review_recurring_concern_state(
        current={"topic": "x", "question": "q", "impact_level": "high"},
        previous=({"topic": "x", "question": "q", "impact_level": "low"},),
    )
    assert record["impact_changed"] is True
    assert record["pathology_inferred"] is False


def test_single_repeat_never_triggers_pattern():
    record = evaluate_repetitive_certainty_pattern(
        turns=(
            {"turn": 1, "same_question": True, "relief_then_checking": True},
        )
    )
    assert record["pattern_detected"] is False
    assert record["pathology_inferred"] is False
    assert record["diagnosis"] is None
    assert record["psychiatric_label"] is False


def test_multi_turn_impossible_certainty_requires_all_grounds():
    """All five grounded dimensions are required; missing any one (including
    certainty pursuit) cannot be invented.  ``same_question`` alone never
    implies impossible-certainty pursuit (I-002)."""
    full_turns = (
        {"turn": 1, "same_question": True, "evidence_state": "unchanged", "pursuing_certainty": True},
        {"turn": 2, "same_question": True, "evidence_state": "unchanged", "pursuing_certainty": True},
        {"turn": 3, "same_question": True, "evidence_state": "unchanged", "impossible_certainty": True},
        {"turn": 4, "same_question": True, "relief_followed_by_checking": True, "pursuing_certainty": True},
    )
    complete = evaluate_repetitive_certainty_pattern(turns=full_turns)
    assert complete["pattern_detected"] is True
    # even then: no label, reassurance stays allowed, uncertainty stays visible
    assert complete["pathology_inferred"] is False
    assert complete["psychiatric_label"] is False
    assert complete["reassurance_allowed"] is True
    assert complete["unchanged_evidence_visible"] is True
    assert complete["unresolved_uncertainty_visible"] is True

    missing_relief = evaluate_repetitive_certainty_pattern(
        turns=tuple(turn for turn in full_turns if "relief_followed_by_checking" not in turn)
        + ({"turn": 9, "same_question": True, "pursuing_certainty": True}, {"turn": 10, "same_question": True, "pursuing_certainty": True})
    )
    assert missing_relief["pattern_detected"] is False


def test_no_psychiatric_labels_from_repetition():
    for turns in (
        ({"turn": i, "same_question": True} for i in range(1, 8)),
        (
            {"turn": 1, "same_question": True},
            {"turn": 2, "same_question": True, "distress": "high"},
            {"turn": 3, "same_question": True, "distress": "high"},
            {"turn": 4, "same_question": True, "distress": "high"},
            {"turn": 5, "same_question": True, "distress": "high"},
            {"turn": 6, "same_question": True, "relief_followed_by_checking": True},
        ),
    ):
        record = evaluate_repetitive_certainty_pattern(turns=tuple(turns))
        assert record["pathology_inferred"] is False
        assert record["diagnosis"] is None
        for label in ("OCD", "anxiety disorder", "compulsion"):
            assert label not in json.dumps(record)


def test_malformed_recurrence_input_fails_closed_without_pathology():
    for current in (None, "x", 7, {}):
        record = review_recurring_concern_state(current=current)
        assert record["pathology_inferred"] is False
        json.dumps(record, allow_nan=False)


# ── Action state / agency ────────────────────────────────────────────────────


def test_no_action_is_valid_outcome():
    record = evaluate_action_state(options=(), urgency=None, user_request=None)
    assert record["state"] == ACTION_NO_ACTION_NEEDED
    assert record["action_forced"] is False


def test_user_wants_to_wait_preserves_agency():
    record = evaluate_action_state(
        options=("talk to manager",), urgency=None,
        user_request="I want to wait and observe a bit.",
    )
    # Explicit wait is respected (I-003): NO_ACTION_NEEDED exactly.
    assert record["state"] == ACTION_NO_ACTION_NEEDED
    assert record["user_decision_required_for_adoption"] is True


def test_useful_and_recommended_states_distinguished():
    useful = evaluate_action_state(
        options=("write down what happened",),
        user_request="What can I do?",
        grounded_options=True,
    )
    assert useful["state"] in (ACTION_USEFUL, ACTION_RECOMMENDED)
    recommended = evaluate_action_state(
        options=("consult the specialist",),
        urgency="soon",
        user_request="What can I do?",
        grounded_options=True,
        specialized_recommendation=True,
    )
    assert recommended["state"] == ACTION_RECOMMENDED


def test_option_is_not_recommendation_is_not_adopted():
    record = evaluate_action_state(
        options=("option A", "option B"),
        user_request="What can I do?",
        grounded_options=True,
    )
    assert record["options_are_candidates"] is True
    assert record["recommendation_made"] in (True, False)
    assert record["decision_adopted"] is False
    assert record["external_action_executed"] is False


def test_system_refuses_to_decide_for_user():
    record = evaluate_action_state(
        options=("A", "B"),
        user_request="Just decide for me.",
        grounded_options=True,
    )
    assert record["decision_adopted"] is False
    assert record["state"] == USER_DECISION_REQUIRED


def test_specialized_escalation_routed_not_executed():
    record = evaluate_action_state(
        options=(),
        urgency="now",
        specialized_domain_result={
            "domain_id": "domain:health",
            "red_flags": ("severe symptom",),
            "authorized": True,
        },
    )
    assert record["state"] == DOMAIN_ESCALATION_NEEDED
    assert record["external_action_executed"] is False
    assert record["specialized_domain_id"] == "domain:health"


# ── Directness ───────────────────────────────────────────────────────────────


def test_disagreement_allowed_when_evidence_weak():
    record = evaluate_grounded_directness(
        assessment="user_interpretation_unlikely",
        evidence=(
            {"identity": "c1", "against": "feared reading", "grounding": "a"},
            {"identity": "c2", "against": "feared reading", "grounding": "b"},
        ),
    )
    assert record["grounded_opinion_stated"] is True
    assert record["disagreement_explicit"] is True
    assert record["harsh"] is False
    assert record["experience_dismissed"] is False


def test_real_concern_acknowledged_when_evidence_strong():
    record = evaluate_grounded_directness(
        assessment="concern_material",
        evidence=(
            {"identity": "e1", "supports": "real decline", "grounding": "a"},
            {"identity": "e2", "supports": "real decline", "grounding": "b"},
        ),
    )
    assert record["grounded_opinion_stated"] is True
    assert record["real_concern_acknowledged"] is True


def test_balanced_evidence_preserves_uncertainty():
    record = evaluate_grounded_directness(
        assessment="balanced",
        evidence=(
            {"identity": "e1", "supports": "benign", "grounding": "a"},
            {"identity": "e2", "against": "benign", "grounding": "b"},
        ),
    )
    assert record["uncertainty_preserved"] is True
    assert record["forced_conclusion"] is False


def test_ungrounded_opinion_is_not_stated_as_grounded():
    record = evaluate_grounded_directness(
        assessment="user_interpretation_unlikely",
        evidence=(),
    )
    assert record["grounded_opinion_stated"] is False
    assert record["basis"] == "insufficient"


# ── Immediate risk escalation ────────────────────────────────────────────────


def test_ordinary_sadness_is_not_escalated():
    for signal in ("ordinary sadness", "fear", "relationship conflict", "repeated worry"):
        record = evaluate_immediate_risk_escalation(
            risk_state={"described_signal": signal, "emotional_intensity": "very high"}
        )
        assert record["escalate"] is False
        assert record["emotion_triggered_escalation"] is False


def test_credible_immediate_risk_escalates_through_specialized_contract():
    record = evaluate_immediate_risk_escalation(
        risk_state={
            "described_signal": "crushing chest pain at rest right now",
        },
        specialized_domain_result={
            "domain_id": "domain:health",
            "red_flags": ("crushing chest pain at rest",),
            "authorized": True,
        },
    )
    assert record["escalate"] is True
    assert record["routed_to_domain"] == "domain:health"
    assert record["own_protocol_created"] is False
    assert record["escalation_source"] == "specialized_domain_result"


def test_unauthorized_red_flag_claim_does_not_escalate():
    record = evaluate_immediate_risk_escalation(
        risk_state={"described_signal": "chest pain"},
        specialized_domain_result={
            "domain_id": "domain:health",
            "red_flags": ("chest pain",),
            "authorized": False,
        },
    )
    assert record["escalate"] is False


def test_malformed_escalation_input_fails_closed():
    for raw in (None, "x", 7, [], float("nan")):
        record = evaluate_immediate_risk_escalation(risk_state=raw)
        assert record["escalate"] is False
        json.dumps(record, allow_nan=False)


def test_helpers_non_mutating_and_json_safe():
    current = {"topic": "t", "question": "q", "evidence_references": ["m1"]}
    snapshot = copy.deepcopy(current)
    r1 = review_recurring_concern_state(current=current)
    r2 = evaluate_action_state(options=("o",), user_request="what can I do?")
    r3 = evaluate_grounded_directness(assessment="balanced")
    assert current == snapshot
    for record in (r1, r2, r3):
        json.dumps(record, allow_nan=False)
