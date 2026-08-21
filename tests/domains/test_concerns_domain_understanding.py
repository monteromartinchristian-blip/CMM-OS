"""Phase 10.25 — Concerns understanding / support-need semantics tests.

Covers ``understand_concern``, ``map_lived_experience``, ``infer_support_need``
and ``evaluate_question_materiality`` (frozen design §9.1, §11, §12, §20;
implementation plan Task 3):

- enough context + direct request gives a substantive-response-ready state
  with no mandatory action plan;
- materially missing context asks a targeted question; immaterial missing
  detail does not;
- "I don't want advice; I just need to talk" cannot become problem solving;
- explicit current request beats session context beats historical preference;
- emotional experience remains valid without an external interpretation
  becoming fact;
- malformed truthy primitives never mean "material question";
- no input mutation; strict JSON.
"""

from __future__ import annotations

import copy
import json

from cmm.domains.concerns.rules import (
    QUESTION_MATERIAL,
    QUESTION_NOT_MATERIAL,
    SUPPORT_EMOTIONAL_PROCESSING,
    SUPPORT_MIXED,
    SUPPORT_PROBLEM_SOLVING,
    SUPPORT_UNCLEAR,
    SUPPORT_UNDERSTANDING,
    evaluate_question_materiality,
    infer_support_need,
    map_lived_experience,
    understand_concern,
)


def test_enough_context_and_direct_request_is_response_ready_without_action_plan():
    material = {
        "situation": "My manager hasn't answered my email in five days.",
        "trigger": "the silence after my salary question",
        "what_matters": "whether my position is at risk",
        "support_need": "PERSPECTIVE",
        "explicit_request": "Tell me what you think.",
    }
    result = understand_concern(material)
    assert result["understood"] is True
    assert result["ready_for_substantive_response"] is True
    assert result["missing_material_context"] == ()
    # No mandatory action plan: understanding precedes intervention.
    assert result["mandatory_action_plan"] is False
    assert result["advice_generated"] is False


def test_vague_concern_with_session_context_understands():
    material = {
        "statement": "I don't know, this whole thing is really messing with my head.",
        "session_context": {"active_topic": "conflict with flatmate about rent"},
    }
    result = understand_concern(material)
    assert result["understood"] is True
    assert result["core_issue"] == "conflict with flatmate about rent"
    # One clarifying question only if necessary — here context resolves it.
    assert result["ask_question"] is False


def test_materially_missing_context_asks_targeted_question():
    material = {
        "situation": "Something happened at work and I can't stop thinking about it.",
        "session_context": None,
    }
    result = understand_concern(material)
    assert result["understood"] is False
    assert result["ask_question"] is True
    assert len(result["questions"]) == 1
    question = result["questions"][0]
    assert question["materiality"] == QUESTION_MATERIAL
    assert question["reason"] in ("changes_interpretation", "changes_meaning")


def test_immaterial_missing_detail_does_not_ask():
    """A missing detail that cannot change meaning/risk/reassurance/decision
    must not trigger a question."""
    material = {
        "situation": "My manager hasn't answered my salary email for five days.",
        "trigger": "the silence",
        "what_matters": "whether my position is at risk",
        "missing_detail": "which exact day the email was sent",
    }
    result = understand_concern(material)
    assert result["understood"] is True
    assert result["ask_question"] is False
    # minor gaps qualify the response rather than blocking it
    assert result["respond_with_qualification"] is True


def test_no_advice_request_cannot_become_problem_solving():
    record = infer_support_need(
        explicit_request="I don't want advice; I just need to talk.",
        current_signal="distressed, needs to elaborate",
        session_context={"previous_support_need": "PROBLEM_SOLVING"},
        historical_preference="PROBLEM_SOLVING",
    )
    assert record["support_need"] in (
        SUPPORT_UNDERSTANDING,
        SUPPORT_EMOTIONAL_PROCESSING,
    )
    assert record["basis"] == "explicit_current_request"
    assert record["problem_solving_allowed"] is False


def test_explicit_request_beats_historical_preference():
    record = infer_support_need(
        explicit_request="What can I do about this?",
        historical_preference="EMOTIONAL_PROCESSING",
    )
    assert record["support_need"] == SUPPORT_PROBLEM_SOLVING
    assert record["basis"] == "explicit_current_request"


def test_clear_current_signal_beats_session_context():
    record = infer_support_need(
        current_signal="Can you reassure me that this is nothing?",
        session_context={"previous_support_need": "EXPLORATION"},
    )
    assert record["support_need"] == "REASSURANCE"
    assert record["basis"] == "clear_current_signal"


def test_recent_session_context_precedes_historical_preference():
    record = infer_support_need(
        session_context={"current_turn_signal": "help me decide what to do"},
        historical_preference="UNDERSTANDING",
    )
    assert record["support_need"] == "DECISION_SUPPORT"
    assert record["basis"] == "recent_session_context"


def test_no_signal_yields_unclear_not_invention():
    record = infer_support_need()
    assert record["support_need"] == SUPPORT_UNCLEAR
    assert record["invented_classification"] is False


def test_mixed_need_preserved():
    record = infer_support_need(
        explicit_request="Tell me what you think, and then help me figure out a next step."
    )
    assert record["support_need"] == SUPPORT_MIXED
    assert set(record["components"]) >= {"PERSPECTIVE", "NEXT_STEP"}


def test_malformed_support_request_never_classified_as_problem_solving():
    for raw in (None, 1, True, [], {}, 1.5, "unknown"):
        record = infer_support_need(
            explicit_request=raw,
            current_signal=raw,
            session_context=raw,
            historical_preference=raw,
        )
        assert record["support_need"] in (
            SUPPORT_UNCLEAR,
            "UNCLEAR",
        )


def test_emotional_experience_remains_valid_without_interpretation_promotion():
    result = map_lived_experience(
        material={
            "emotion_statements": ("I feel ignored by them",),
            "interpretation_statements": ("They are deliberately excluding me",),
            "fear_statements": ("that I am becoming just another friend",),
        }
    )
    emotions = result["emotions"]
    interpretations = result["interpretations"]
    fears = result["fears"]
    # The emotion is valid lived experience.
    assert len(emotions) == 1
    assert emotions[0]["experience_valid"] is True
    assert emotions[0]["external_fact"] is False
    # The interpretation remains interpretation.
    assert len(interpretations) == 1
    assert interpretations[0]["promoted_to_fact"] is False
    # The fear stays a fear, not a prediction.
    assert len(fears) == 1
    assert fears[0]["prediction"] is False
    assert result["diagnosis"] is False


def test_map_lived_experience_partial_population_is_valid():
    result = map_lived_experience(material={})
    assert result["emotions"] == ()
    assert result["fears"] == ()
    assert result["needs"] == ()
    assert result["desired_outcome"] is None
    assert result["complete"] is False
    assert result["failure"] is False


def test_question_materiality_requires_real_change():
    material = evaluate_question_materiality(
        question="Did they reply to anyone else?",
        changes=("interpretation", "reassurance"),
    )
    assert material["materiality"] == QUESTION_MATERIAL

    immaterial = evaluate_question_materiality(
        question="What color was the email icon when you read it?",
        changes=("none",),
    )
    assert immaterial["materiality"] == QUESTION_NOT_MATERIAL

    empty = evaluate_question_materiality(
        question="How long has this been going on?",
        changes=(),
    )
    assert empty["materiality"] == QUESTION_NOT_MATERIAL


def test_malformed_changes_argument_never_means_material():
    """Malformed truthy primitives must not mean 'material question'."""
    for raw in (True, 1, 1.5, {}, "yes", object()):
        record = evaluate_question_materiality(
            question="anything", changes=raw
        )
        assert record["materiality"] == QUESTION_NOT_MATERIAL
        json.dumps(record, allow_nan=False)


def test_canonical_change_dimensions_only_are_accepted():
    canonical = {
        "meaning",
        "risk",
        "reassurance",
        "interpretation",
        "domain routing",
        "decision",
        "next step",
    }
    record = evaluate_question_materiality(
        question="q",
        changes=tuple(sorted(canonical)) + ("vibe", "arbitrary"),
    )
    assert set(record["recognized_changes"]) <= canonical
    assert record["materiality"] == QUESTION_MATERIAL
    assert "vibe" not in record["recognized_changes"]
    assert "arbitrary" not in record["recognized_changes"]


def test_inputs_not_mutated_and_outputs_json_safe():
    material = {
        "situation": "s",
        "trigger": "t",
        "what_matters": "m",
        "emotion_statements": ["e"],
        "interpretation_statements": ["i"],
        "fear_statements": ["f"],
    }
    snapshot = copy.deepcopy(material)
    r1 = understand_concern(material)
    r2 = map_lived_experience(material)
    r3 = infer_support_need(explicit_request="Tell me what you think.")
    r4 = evaluate_question_materiality(question="q?", changes=["meaning"])
    assert material == snapshot
    for record in (r1, r2, r3, r4):
        json.dumps(record, allow_nan=False)
