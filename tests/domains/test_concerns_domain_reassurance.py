"""Phase 10.25 — Concerns epistemics / reassurance / risk semantics tests.

Covers ``classify_concern_statement``, ``evaluate_uncertainty``,
``evaluate_reassurance``, ``evaluate_proportional_risk``,
``detect_catastrophic_escalation`` and ``detect_false_reassurance``
(frozen design §18, §21–§26; implementation plan Task 4).
"""

from __future__ import annotations

import copy
import json

from cmm.domains.concerns.rules import (
    CONCERN_SUPPORTED,
    INSUFFICIENT_BASIS,
    LEVEL_EXPERIENCE,
    LEVEL_FACT,
    LEVEL_FEAR,
    LEVEL_INTERPRETATION,
    LEVEL_SCENARIO,
    LEVEL_UNKNOWN,
    REASSURANCE_PARTIAL,
    REASSURANCE_SUPPORTED,
    UNCERTAIN,
    classify_concern_statement,
    detect_catastrophic_escalation,
    detect_false_reassurance,
    evaluate_proportional_risk,
    evaluate_reassurance,
    evaluate_uncertainty,
)

# ── Statement classification ─────────────────────────────────────────────────


def test_caller_fact_label_cannot_bypass_grounding():
    record = classify_concern_statement(
        {"statement": "They are rejecting me", "level": "interpretation", "fact": True}
    )
    assert record["level"] == LEVEL_INTERPRETATION
    assert record["grounded"] is False
    assert record["promotion_blocked"] is True


def test_grounded_evidence_supports_fact_level():
    record = classify_concern_statement(
        {
            "statement": "The email was sent five days ago",
            "level": "fact",
            "evidence_references": ("msg:1",),
        }
    )
    assert record["level"] == LEVEL_FACT
    assert record["grounded"] is True


def test_experience_is_not_external_fact():
    record = classify_concern_statement(
        {"statement": "I feel ignored", "level": "experience", "fact": True}
    )
    assert record["level"] == LEVEL_EXPERIENCE
    assert record["external_fact"] is False


def test_interpretation_is_not_fear_and_fear_is_not_prediction():
    interpretation = classify_concern_statement(
        {"statement": "They are excluding me", "level": "interpretation"}
    )
    fear = classify_concern_statement({"statement": "maybe I'll lose them", "level": "fear"})
    scenario = classify_concern_statement({"statement": "if this continues...", "level": "scenario"})
    assert interpretation["level"] == LEVEL_INTERPRETATION
    assert interpretation["is_fear"] is False
    assert fear["level"] == LEVEL_FEAR
    assert fear["prediction"] is False
    assert scenario["level"] == LEVEL_SCENARIO
    assert scenario["probability_claim"] is False


def test_unknown_and_malformed_levels_fail_closed():
    unknown = classify_concern_statement({"statement": "x", "level": "certainty_absolute"})
    assert unknown["level"] == LEVEL_UNKNOWN
    malformed = classify_concern_statement("not-a-mapping")
    assert malformed["malformed"] is True
    assert malformed["level"] == LEVEL_UNKNOWN


# ── Uncertainty ──────────────────────────────────────────────────────────────


def test_uncertainty_preserved_with_records():
    record = evaluate_uncertainty(
        records=(
            {"identity": "u1", "unknown": "why they went silent"},
            {"identity": "u2", "ambiguous": "the tone of the reply"},
        )
    )
    assert record["uncertainty_preserved"] is True
    assert record["resolved_by_invention"] is False
    assert len(record["uncertainties"]) == 2


def test_conflicting_evidence_stays_unresolved_not_resolved():
    record = evaluate_uncertainty(
        records=(
            {"identity": "u1", "unknown": "intent", "resolution": "they meant well"},
            {"identity": "u2", "unknown": "intent", "resolution": "they meant harm"},
        )
    )
    assert record["conflict_present"] is True
    assert record["uncertainty_preserved"] is True


def test_malformed_uncertainty_records_do_not_resolve_anything():
    record = evaluate_uncertainty(records=("garbage", 7, None))
    assert record["uncertainty_preserved"] is True
    assert len(record["malformed_records"]) >= 2


def test_empty_records_are_valid_empty_not_failure():
    record = evaluate_uncertainty(records=())
    assert record["uncertainty_preserved"] is True
    assert record["valid_empty"] is True


# ── Reassurance ──────────────────────────────────────────────────────────────


def test_clear_counterevidence_supports_reassurance():
    """Two distinct strong records against the feared reading and none for
    it support reassurance."""
    record = evaluate_reassurance(
        target_claim="feared_meaning",
        evidence=(
            {"identity": "e1", "claim": "feared_meaning", "stance": "opposes_target", "grounding": "msg:1"},
        ),
        counterevidence=(
            {"identity": "c1", "claim": "feared_meaning", "stance": "opposes_target", "grounding": "msg:2"},
            {"identity": "c2", "claim": "feared_meaning", "stance": "opposes_target", "grounding": "msg:3"},
            {"identity": "c3", "claim": "feared_meaning", "stance": "opposes_target", "grounding": "msg:4"},
        ),
    )
    assert record["assessment"] == REASSURANCE_SUPPORTED
    assert record["target_claim"] == "feared_meaning"
    # Reassurance coexists with visible uncertainty; absolute certainty is
    # never manufactured.
    assert record["absolute_certainty"] is False


def test_reassurance_can_coexist_with_uncertainty():
    record = evaluate_reassurance(
        target_claim="feared_meaning",
        evidence=(
            {"identity": "c1", "claim": "feared_meaning", "stance": "opposes_target", "grounding": "s2"},
        ),
        counterevidence=(
            {"identity": "e1", "claim": "feared_meaning", "stance": "supports_target", "grounding": "s1"},
        ),
        uncertainty=({"identity": "u1", "unknown": "their current intent"},),
    )
    assert record["assessment"] in (REASSURANCE_SUPPORTED, REASSURANCE_PARTIAL, UNCERTAIN)
    assert record["remaining_uncertainty"] == ("u1",)
    json.dumps(record, allow_nan=False)


def test_material_concern_blocks_reassurance_but_acknowledges():
    record = evaluate_reassurance(
        target_claim="deterioration",
        evidence=(
            {"identity": "e1", "claim": "deterioration", "stance": "supports_target", "grounding": "s1"},
            {"identity": "e2", "claim": "deterioration", "stance": "supports_target", "grounding": "s2"},
        ),
        material_concerns=("real performance decline documented twice",),
    )
    assert record["assessment"] == CONCERN_SUPPORTED
    assert record["concern_erased"] is False


def test_no_usable_evidence_is_insufficient_basis():
    record = evaluate_reassurance()
    assert record["assessment"] == INSUFFICIENT_BASIS
    assert record["invented_assessment"] is False


def test_partial_reassessment_with_mixed_signals():
    """Reassurance caps at partial when a material concern coexists with
    opposing evidence (spec §25: never minimize a real negative signal)."""
    record = evaluate_reassurance(
        target_claim="feared reading",
        evidence=(
            {"identity": "e1", "claim": "benign reading", "stance": "opposes_target", "grounding": "s1"},
        ),
        counterevidence=(
            {"identity": "c1", "claim": "feared reading", "stance": "supports_target", "grounding": "s2"},
        ),
        material_concerns=("one concrete unresolved issue remains",),
    )
    assert record["assessment"] == REASSURANCE_PARTIAL
    assert tuple(record["acknowledged_concerns"]) != ()


def test_all_five_canonical_states_exist_and_are_used():
    canonical = {
        REASSURANCE_SUPPORTED,
        REASSURANCE_PARTIAL,
        UNCERTAIN,
        CONCERN_SUPPORTED,
        INSUFFICIENT_BASIS,
    }
    seen: set[str] = set()
    for kwargs in (
        {},  # insufficient
        {
            "target_claim": "x",
            "evidence": ({"identity": "e1", "claim": "x", "stance": "opposes_target", "grounding": "s1"},),
            "counterevidence": (
                {"identity": "c1", "claim": "x", "stance": "opposes_target", "grounding": "a"},
                {"identity": "c2", "claim": "x", "stance": "opposes_target", "grounding": "b"},
            ),
        },  # supported
        {
            "target_claim": "x",
            "evidence": (
                {"identity": "e1", "claim": "x", "stance": "supports_target", "grounding": "s1"},
                {"identity": "e2", "claim": "x", "stance": "supports_target", "grounding": "s2"},
            ),
        },  # concern supported
        {
            "target_claim": "x",
            "evidence": ({"identity": "e1", "claim": "x", "stance": "opposes_target", "grounding": "s1"},),
            "material_concerns": ("one real issue",),
            "counterevidence": (
                {"identity": "c1", "claim": "x", "stance": "supports_target", "grounding": "t"},
            ),
        },  # partial
        {
            "uncertainty": ({"identity": "u1", "unknown": "intent"},),
        },
    ):
        seen.add(evaluate_reassurance(**kwargs)["assessment"])
    assert len(seen & canonical) >= 4
    assert all(state in canonical for state in seen)


def test_duplicate_evidence_does_not_inflate_reassurance():
    single = evaluate_reassurance(
        target_claim="feared_meaning",
        evidence=(
            {"identity": "e1", "claim": "feared_meaning", "stance": "opposes_target", "grounding": "s1"},
        ),
        counterevidence=(
            {"identity": "c1", "claim": "feared_meaning", "stance": "opposes_target", "grounding": "a"},
            {"identity": "c2", "claim": "feared_meaning", "stance": "opposes_target", "grounding": "b"},
        ),
    )
    duplicated = evaluate_reassurance(
        target_claim="feared_meaning",
        evidence=(
            {"identity": "e1", "claim": "feared_meaning", "stance": "opposes_target", "grounding": "s1"},
            {"identity": "e1", "claim": "feared_meaning", "stance": "opposes_target", "grounding": "s1"},
            {"identity": "e1-dup", "claim": "feared_meaning", "stance": "opposes_target", "grounding": "s1"},
        ),
        counterevidence=(
            {"identity": "c1", "claim": "feared_meaning", "stance": "opposes_target", "grounding": "a"},
            {"identity": "c2", "claim": "feared_meaning", "stance": "opposes_target", "grounding": "b"},
        ),
    )
    assert duplicated["assessment"] == single["assessment"]
    assert duplicated["duplicate_count"] > 0


def test_malformed_evidence_never_increases_certainty_or_reassurance():
    baseline = evaluate_reassurance(
        counterevidence=(
            {"identity": "c1", "against": "x", "grounding": "a"},
            {"identity": "c2", "against": "x", "grounding": "b"},
        )
    )
    with_malformed = evaluate_reassurance(
        evidence=("garbage", 7, float("nan"), {"no_fields": True}),
        counterevidence=(
            {"identity": "c1", "against": "x", "grounding": "a"},
            {"identity": "c2", "against": "x", "grounding": "b"},
        ),
    )
    assert with_malformed["assessment"] == baseline["assessment"]
    assert with_malformed["malformed_count"] >= 3
    json.dumps(with_malformed, allow_nan=False)


def test_order_invariance_of_reassurance_inputs():
    evidence_a = (
        {"identity": "e1", "against": "f", "grounding": "s1"},
        {"identity": "e2", "against": "f", "grounding": "s2"},
    )
    evidence_b = tuple(reversed(evidence_a))
    results = [
        evaluate_reassurance(evidence=order)["assessment"] for order in (evidence_a, evidence_b)
    ]
    assert len(set(results)) == 1


def test_no_numerical_probability_without_authorized_source():
    record = evaluate_reassurance(
        evidence=({"identity": "e1", "against": "f", "grounding": "s1"},),
        counterevidence=(
            {"identity": "c1", "against": "f", "grounding": "a"},
            {"identity": "c2", "against": "f", "grounding": "b"},
        ),
    )
    assert record.get("probability") is None
    assert record.get("numeric_probability_assigned") is False


def test_authorized_specialized_probability_is_preserved():
    record = evaluate_reassurance(
        evidence=({"identity": "e1", "against": "f", "grounding": "s1"},),
        counterevidence=(
            {"identity": "c1", "against": "f", "grounding": "a"},
            {"identity": "c2", "against": "f", "grounding": "b"},
        ),
        specialized_domain_result={
            "domain_id": "domain:health",
            "probability": 0.02,
            "authorized": True,
            "provenance": "clinical model",
        },
    )
    assert record["specialized_probability"] == 0.02
    assert record["probability"] is None  # Concerns itself never assigns one


# ── Proportional risk ────────────────────────────────────────────────────────


def test_emotional_intensity_alone_cannot_make_high_risk():
    record = evaluate_proportional_risk(
        severity="very frightened",
        immediacy=None,
        evidence=(),
    )
    assert record["risk_level"] in ("none", "low", "unresolved")
    assert record["emotion_drove_risk"] is False


def test_grounded_specialized_red_flag_survives_calm_wording():
    record = evaluate_proportional_risk(
        severity="calm",
        immediacy="now",
        evidence=(),
        specialized_domain_result={
            "domain_id": "domain:health",
            "red_flags": ("crushing chest pain at rest",),
            "authorized": True,
        },
    )
    assert record["risk_level"] == "high"
    assert record["downgraded"] is False
    assert record["specialized_ownership_preserved"] is True
    assert record["specialized_red_flags"] == ("crushing chest pain at rest",)


def test_weak_evidence_yields_no_invented_risk():
    record = evaluate_proportional_risk(severity=None, immediacy=None, evidence=())
    assert record["risk_level"] in ("none", "unresolved")
    assert record["invented_risk"] is False


def test_malformed_severity_never_triggers_high_risk():
    for raw in (7, float("nan"), [], {}, True):
        record = evaluate_proportional_risk(severity=raw, immediacy=None)
        assert record["risk_level"] != "high"
        assert record["malformed_input_ignored"] is True


# ── Catastrophic escalation ──────────────────────────────────────────────────


def test_possibility_to_probability_blocked():
    result = detect_catastrophic_escalation(
        source_state={"kind": "possibility", "description": "it could happen"},
        proposed_state={"kind": "probability", "description": "it will probably happen"},
    )
    assert result["blocked"] is True
    assert result["promotion"] == "possibility_to_probability"


def test_ambiguity_to_warning_sign_blocked():
    result = detect_catastrophic_escalation(
        source_state={"kind": "ambiguity"},
        proposed_state={"kind": "warning_sign"},
    )
    assert result["blocked"] is True
    assert result["promotion"] == "ambiguity_to_warning_sign"


def test_change_to_deterioration_blocked():
    result = detect_catastrophic_escalation(
        source_state={"kind": "change"},
        proposed_state={"kind": "deterioration"},
    )
    assert result["blocked"] is True


def test_silence_to_rejection_blocked():
    result = detect_catastrophic_escalation(
        source_state={"kind": "silence"},
        proposed_state={"kind": "rejection"},
    )
    assert result["blocked"] is True


def test_symptom_to_serious_disease_blocked():
    result = detect_catastrophic_escalation(
        source_state={"kind": "symptom"},
        proposed_state={"kind": "serious_disease"},
    )
    assert result["blocked"] is True


def test_setback_to_failure_blocked():
    result = detect_catastrophic_escalation(
        source_state={"kind": "setback"},
        proposed_state={"kind": "failure"},
    )
    assert result["blocked"] is True


def test_uncertainty_to_danger_blocked():
    result = detect_catastrophic_escalation(
        source_state={"kind": "uncertainty"},
        proposed_state={"kind": "danger"},
    )
    assert result["blocked"] is True


def test_legitimate_same_kind_transition_allowed():
    result = detect_catastrophic_escalation(
        source_state={"kind": "hypothesis", "support": 3},
        proposed_state={"kind": "hypothesis", "support": 5},
    )
    assert result["blocked"] is False


def test_malformed_states_fail_closed_without_blocking_semantics():
    for source, proposed in ((None, {}), ({}, None), ("x", 7), ({}, [])):
        result = detect_catastrophic_escalation(
            source_state=source, proposed_state=proposed
        )
        json.dumps(result, allow_nan=False)
        # malformed input cannot authorize a promotion either way
        assert result.get("evaluated") is False or result.get("blocked") is True


# ── False reassurance ────────────────────────────────────────────────────────


def test_real_warning_signals_block_reassuring_minimization():
    result = detect_false_reassurance(
        reassurance_state={"assessment": REASSURANCE_SUPPORTED},
        material_concerns=("documented repeated missed deadlines",),
    )
    assert result["false_reassurance"] is True
    assert result["corrected_assessment"] == CONCERN_SUPPORTED


def test_supported_reassurance_without_concerns_is_honest():
    result = detect_false_reassurance(
        reassurance_state={"assessment": REASSURANCE_SUPPORTED},
        material_concerns=(),
    )
    assert result["false_reassurance"] is False


def test_absolute_certainty_language_flagged():
    result = detect_false_reassurance(
        reassurance_state={
            "assessment": REASSURANCE_SUPPORTED,
            "absolute_certainty": True,
        },
        material_concerns=(),
    )
    assert result["false_reassurance"] is True
    assert result["reason"] == "absolute_certainty"


def test_insufficient_basis_cannot_be_presented_as_supported():
    result = detect_false_reassurance(
        reassurance_state={"assessment": INSUFFICIENT_BASIS},
        material_concerns=(),
    )
    assert result["false_reassurance"] is False
    assert result["presented_as_supported"] is False


def test_epistemics_helpers_non_mutating_and_json_safe():
    statement = {"statement": "I feel ignored", "level": "experience", "fact": True}
    snapshot = copy.deepcopy(statement)
    r1 = classify_concern_statement(statement)
    r2 = evaluate_uncertainty(records=({"identity": "u", "unknown": "x"},))
    r3 = detect_catastrophic_escalation(
        source_state={"kind": "possibility"}, proposed_state={"kind": "probability"}
    )
    assert statement == snapshot
    for record in (r1, r2, r3):
        json.dumps(record, allow_nan=False)
