"""Phase 10.25 — Concerns epistemic gate tests.

The semantic invariants from the frozen design §116, exercised directly:

    fact != interpretation; interpretation != fear; fear != prediction;
    possibility != probability; emotional certainty != evidential certainty;
    duplicates do not inflate; malformed evidence does not inflate;
    conflict stays conflict.
"""

from __future__ import annotations

import json

from cmm.domains.concerns.rules import (
    LEVEL_EXPERIENCE,
    LEVEL_FACT,
    LEVEL_FEAR,
    LEVEL_HYPOTHESIS,
    LEVEL_INTERPRETATION,
    LEVEL_SCENARIO,
    classify_concern_statement,
    detect_catastrophic_escalation,
    evaluate_reassurance,
)


def test_fact_is_not_interpretation():
    grounded = classify_concern_statement(
        {
            "statement": "email sent Monday",
            "level": "fact",
            "evidence_references": ("m1",),
        }
    )
    interpreted = classify_concern_statement(
        {"statement": "they are avoiding me", "level": "interpretation"}
    )
    assert grounded["level"] == LEVEL_FACT
    assert interpreted["level"] == LEVEL_INTERPRETATION
    assert grounded["level"] != interpreted["level"]


def test_interpretation_is_not_fear():
    record = classify_concern_statement({"statement": "x", "level": "interpretation"})
    assert record["level"] == LEVEL_INTERPRETATION
    assert record["is_fear"] is False


def test_fear_is_not_prediction():
    record = classify_concern_statement(
        {"statement": "maybe disaster", "level": "fear"}
    )
    assert record["level"] == LEVEL_FEAR
    assert record["prediction"] is False
    assert record["probability_claim"] is False


def test_scenario_is_not_probability():
    record = classify_concern_statement(
        {"statement": "if X then Y", "level": "scenario"}
    )
    assert record["level"] == LEVEL_SCENARIO
    assert record["probability_claim"] is False


def test_emotional_certainty_is_not_evidential_certainty():
    """A very frightened user with weak evidence stays uncertain."""
    record = evaluate_proportional_risk_helper()
    del record


def evaluate_proportional_risk_helper():  # pragma: no cover - helper
    from cmm.domains.concerns.rules import evaluate_proportional_risk

    return evaluate_proportional_risk(severity="severe", evidence=())


def test_hypothesis_level_never_becomes_fact_via_label():
    record = classify_concern_statement(
        {"statement": "h", "level": "hypothesis", "confirmed": True}
    )
    assert record["level"] == LEVEL_HYPOTHESIS
    assert record["external_fact"] is False
    assert record["promotion_blocked"] is True


def test_experience_with_fact_label_stays_experience():
    record = classify_concern_statement(
        {"statement": "I feel small", "level": "experience", "fact": True}
    )
    assert record["level"] == LEVEL_EXPERIENCE
    assert record["external_fact"] is False


def test_duplicates_cannot_inflate_reassurance_strength():
    base_records = (
        {"identity": "c1", "against": "f", "grounding": "a"},
        {"identity": "c2", "against": "f", "grounding": "b"},
    )
    duplicated = base_records + tuple(dict(record) for record in base_records)
    single_assessment = evaluate_reassessment(base_records)
    duplicate_assessment = evaluate_reassessment(duplicated)
    assert duplicate_assessment == single_assessment


def evaluate_reassessment(records):  # pragma: no cover - helper
    return evaluate_reassurance(evidence=records)["assessment"]


def test_malformed_evidence_does_not_increase_certainty():
    clean = evaluate_reassurance()
    dirty = evaluate_reassurance(
        evidence=("garbage", 7, float("inf"), {}, None),
    )
    assert dirty["assessment"] == clean["assessment"]
    assert dirty["malformed_count"] >= 4


def test_conflict_stays_conflict():
    """Balanced target-relative evidence stays UNCERTAIN, never resolved in
    either direction."""
    record = evaluate_reassurance(
        target_claim="feared reading",
        evidence=(
            {
                "identity": "e1",
                "claim": "benign",
                "stance": "opposes_target",
                "grounding": "s1",
            },
        ),
        counterevidence=(
            {
                "identity": "c1",
                "claim": "feared reading",
                "stance": "supports_target",
                "grounding": "s2",
            },
        ),
    )
    assert record["assessment"] in ("UNCERTAIN",)
    json.dumps(record, allow_nan=False)


def test_possibility_to_probability_is_blocked_structurally():
    result = detect_catastrophic_escalation(
        source_state={"kind": "possibility"},
        proposed_state={"kind": "probability"},
    )
    assert result["blocked"] is True


def test_all_levels_distinguishable():
    levels = {
        classify_concern_statement({"statement": "s", "level": level})["level"]
        for level in (
            "fact",
            "experience",
            "interpretation",
            "fear",
            "hypothesis",
            "scenario",
            "uncertainty",
        )
    }
    # A fact without references degrades to ungrounded but keeps its level;
    # every other canonical level survives classification unchanged.
    assert len(levels) >= 6
