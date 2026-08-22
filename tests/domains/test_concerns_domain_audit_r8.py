"""Regression test suite for Phase 10.25 Concerns Domain Re-Audit (R8).

Covers:
- F1 / RB-001 / RI-003 / RI-004: Reassurance runtime and evidence dimensions
"""

import math
import pytest

from cmm.domains.concerns.rules import (
    BASE_PLAUSIBILITY_HIGH,
    BASE_PLAUSIBILITY_LOW,
    BASE_PLAUSIBILITY_MODERATE,
    BASE_PLAUSIBILITY_UNKNOWN,
    CONCERN_SUPPORTED,
    INSUFFICIENT_BASIS,
    REASSURANCE_PARTIAL,
    REASSURANCE_SUPPORTED,
    STANCE_OPPOSES_TARGET,
    STANCE_SUPPORTS_TARGET,
    UNCERTAIN,
    detect_false_reassurance,
    evaluate_reassurance,
    NoFalseReassuranceRule,
)
from cmm.cognitive.enums import ReasoningRuleResultStatus
from cmm.cognitive.reasoning_rule_contracts import ReasoningRuleContext
from cmm.domains.rule_contracts import DomainReasoningRuleDefinition


# ═════════════════════════════════════════════════════════════════════════════
# F1.1 — Authorized specialized result must never crash
# ═════════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize(
    "prob_input, expected_prob",
    [
        ("missing", None),
        (None, None),
        ("0.2", None),
        (float("nan"), None),
        (float("inf"), None),
        (float("-inf"), None),
        (-0.1, None),
        (1.1, None),
        (0.0, 0.0),
        (1.0, 1.0),
        (0.42, 0.42),
    ],
)
def test_f1_1_authorized_specialized_probability_robustness(prob_input, expected_prob):
    specialized = {"authorized": True}
    if prob_input != "missing":
        specialized["probability"] = prob_input

    result = evaluate_reassurance(
        target_claim="safe",
        evidence=(),
        specialized_domain_result=specialized,
    )
    assert result["specialized_authorized"] is True
    assert result["specialized_probability"] == expected_prob
    assert result["numeric_probability_assigned"] is False
    assert result["probability"] is None


# ═════════════════════════════════════════════════════════════════════════════
# F1.2 — Base plausibility contract and calibration ceiling
# ═════════════════════════════════════════════════════════════════════════════


def test_f1_2_base_plausibility_contract_and_ceiling():
    """Identical evidence produces different calibration ceiling when base plausibility differs."""
    evidence = (
        {
            "identity": "e1",
            "claim": "friend smiled and replied warmly",
            "stance": STANCE_OPPOSES_TARGET,
            "grounding": "msg:1",
            "source_quality": "grounded",
            "temporal_relevance": "current",
        },
        {
            "identity": "e2",
            "claim": "friend invited user to lunch",
            "stance": STANCE_OPPOSES_TARGET,
            "grounding": "msg:2",
            "source_quality": "grounded",
            "temporal_relevance": "current",
        },
    )

    # When feared target claim has low base plausibility, 2 strong opposing records -> REASSURANCE_SUPPORTED
    low_res = evaluate_reassurance(
        target_claim="friend hates me",
        evidence=evidence,
        base_plausibility=BASE_PLAUSIBILITY_LOW,
    )
    assert low_res["base_plausibility"] == BASE_PLAUSIBILITY_LOW
    assert low_res["assessment"] == REASSURANCE_SUPPORTED

    # When feared target claim has high base plausibility, 2 strong opposing records are capped at REASSURANCE_PARTIAL
    high_res = evaluate_reassurance(
        target_claim="friend hates me",
        evidence=evidence,
        base_plausibility=BASE_PLAUSIBILITY_HIGH,
    )
    assert high_res["base_plausibility"] == BASE_PLAUSIBILITY_HIGH
    assert high_res["assessment"] == REASSURANCE_PARTIAL

    # Arbitrary strings do not act as trusted semantics
    arbitrary_res = evaluate_reassurance(
        target_claim="friend hates me",
        evidence=evidence,
        base_plausibility="some_arbitrary_untrusted_string",
    )
    assert arbitrary_res["base_plausibility"] in (None, BASE_PLAUSIBILITY_UNKNOWN)


# ═════════════════════════════════════════════════════════════════════════════
# F1.3 — Authorized specialized evidence influences reassurance
# ═════════════════════════════════════════════════════════════════════════════


def test_f1_3_authorized_specialized_concern_prevents_full_reassurance():
    """Authorized specialized red flag/concern prevents unsupported full reassurance."""
    evidence = (
        {
            "identity": "e1",
            "claim": "vital signs currently normal",
            "stance": STANCE_OPPOSES_TARGET,
            "grounding": "chart:1",
            "source_quality": "grounded",
            "temporal_relevance": "current",
        },
        {
            "identity": "e2",
            "claim": "user walked 2 miles",
            "stance": STANCE_OPPOSES_TARGET,
            "grounding": "chart:2",
            "source_quality": "grounded",
            "temporal_relevance": "current",
        },
    )
    # Authorized specialized result with red flag
    spec_result = {
        "authorized": True,
        "domain_id": "domain:health",
        "red_flags": ["chest_pain_with_exertion"],
    }
    result = evaluate_reassurance(
        target_claim="imminent heart attack",
        evidence=evidence,
        specialized_domain_result=spec_result,
    )
    assert result["specialized_authorized"] is True
    # Specialized red flag prevents REASSURANCE_SUPPORTED
    assert result["assessment"] != REASSURANCE_SUPPORTED
    assert result["assessment"] in (REASSURANCE_PARTIAL, CONCERN_SUPPORTED, UNCERTAIN)


def test_f1_3_authorized_specialized_reassurance_supports():
    """Authorized specialized reassuring result supports reassurance."""
    spec_result = {
        "authorized": True,
        "domain_id": "domain:health",
        "reassuring": True,
        "risk_level": "none",
    }
    result = evaluate_reassurance(
        target_claim="dangerous condition",
        evidence=(),
        specialized_domain_result=spec_result,
    )
    assert result["specialized_authorized"] is True
    assert result["assessment"] in (REASSURANCE_PARTIAL, REASSURANCE_SUPPORTED)


# ═════════════════════════════════════════════════════════════════════════════
# F1.4 — Weak/stale evidence remains visible but cannot upgrade reassurance
# ═════════════════════════════════════════════════════════════════════════════


def test_f1_4_weak_and_stale_evidence_remains_visible():
    """Weak and stale records remain visible with quality/relevance metadata and cannot upgrade."""
    evidence = (
        {
            "identity": "w1",
            "claim": "someone said it might be okay",
            "stance": STANCE_OPPOSES_TARGET,
            "grounding": "hearsay:1",
            "source_quality": "weak",
            "temporal_relevance": "current",
        },
        {
            "identity": "s1",
            "claim": "things were fine 3 years ago",
            "stance": STANCE_OPPOSES_TARGET,
            "grounding": "archive:1",
            "source_quality": "grounded",
            "temporal_relevance": "stale",
        },
    )
    result = evaluate_reassurance(
        target_claim="catastrophe",
        evidence=evidence,
    )
    # Output must retain the weak/stale records in supporting
    assert len(result["supporting"]) == 2
    qualities = [item["source_quality"] for item in result["supporting"]]
    temporals = [item["temporal_relevance"] for item in result["supporting"]]
    assert "weak" in qualities
    assert "stale" in temporals

    # Weak/stale records alone CANNOT produce REASSURANCE_SUPPORTED
    assert result["assessment"] != REASSURANCE_SUPPORTED
    assert result["assessment"] == REASSURANCE_PARTIAL


# ═════════════════════════════════════════════════════════════════════════════
# F1.5 — Normalize substantive claims for dedupe
# ═════════════════════════════════════════════════════════════════════════════


def test_f1_5_normalize_substantive_claims_for_dedupe():
    """Same provenance + same substantive claim (case/whitespace) + stance must dedupe."""
    evidence = (
        {
            "identity": "e1",
            "claim": "Warm reply",
            "stance": STANCE_OPPOSES_TARGET,
            "grounding": "email:123",
        },
        {
            "identity": "e2",
            "claim": "  warm reply  ",
            "stance": STANCE_OPPOSES_TARGET,
            "grounding": "email:123",
        },
    )
    result = evaluate_reassurance(
        target_claim="hostile email",
        evidence=evidence,
    )
    assert result["duplicate_count"] == 1
    assert len(result["supporting"]) == 1
    # Single record cannot give REASSURANCE_SUPPORTED
    assert result["assessment"] != REASSURANCE_SUPPORTED


# ═════════════════════════════════════════════════════════════════════════════
# F1.6 — Partial reassurance with acknowledged material concern is valid
# ═════════════════════════════════════════════════════════════════════════════


def test_f1_6_partial_reassurance_with_material_concern_is_honest():
    """REASSURANCE_PARTIAL + material concern acknowledged is honest, not false reassurance."""
    state = {
        "assessment": REASSURANCE_PARTIAL,
        "material_concern": True,
        "acknowledged_concerns": ("real deadline missed",),
    }
    false_check = detect_false_reassurance(
        reassurance_state=state,
        material_concerns=("real deadline missed",),
    )
    assert false_check["false_reassurance"] is False
    assert false_check["reason"] is None
    assert false_check["corrected_assessment"] == REASSURANCE_PARTIAL


def test_f1_6_supported_reassurance_with_unacknowledged_concern_is_false():
    """REASSURANCE_SUPPORTED with material concern is false reassurance."""
    state = {
        "assessment": REASSURANCE_SUPPORTED,
        "material_concern": True,
        "acknowledged_concerns": ("real deadline missed",),
    }
    false_check = detect_false_reassurance(
        reassurance_state=state,
        material_concerns=("real deadline missed",),
    )
    assert false_check["false_reassurance"] is True
    assert false_check["reason"] == "material_concern_minimized"
    assert false_check["corrected_assessment"] == CONCERN_SUPPORTED


def test_f1_6_absolute_certainty_is_false_reassurance():
    """Absolute certainty is always false reassurance."""
    state = {
        "assessment": REASSURANCE_SUPPORTED,
        "absolute_certainty": True,
    }
    false_check = detect_false_reassurance(
        reassurance_state=state,
        material_concerns=(),
    )
    assert false_check["false_reassurance"] is True
    assert false_check["reason"] == "absolute_certainty"


def test_f1_6_no_false_reassurance_rule_integration():
    """NoFalseReassuranceRule allows partial reassurance with acknowledged concerns."""
    from datetime import datetime, timezone
    from cmm.domains.concerns.rules import build_concerns_rules

    rules = build_concerns_rules()
    rule = next(r for r in rules if "no_false_reassurance" in r.definition.id)

    # Partial reassurance with acknowledged concern -> APPLIED (not BLOCKED)
    ctx_partial = ReasoningRuleContext(
        reasoning_id="r-partial",
        timestamp=datetime.now(timezone.utc),
        metadata={
            "reassurance_state": {
                "assessment": REASSURANCE_PARTIAL,
                "material_concern": True,
            },
            "material_concerns": ("budget shortfall",),
        },
    )
    res_partial = rule.evaluate(ctx_partial)
    assert res_partial.status == ReasoningRuleResultStatus.APPLIED
    assert res_partial.findings[0].code == "REASSURANCE_HONEST"

    # Supported reassurance with material concern -> BLOCKED
    ctx_supported = ReasoningRuleContext(
        reasoning_id="r-supported",
        timestamp=datetime.now(timezone.utc),
        metadata={
            "reassurance_state": {
                "assessment": REASSURANCE_SUPPORTED,
                "material_concern": True,
            },
            "material_concerns": ("budget shortfall",),
        },
    )
    res_supported = rule.evaluate(ctx_supported)
    assert res_supported.status == ReasoningRuleResultStatus.BLOCKED
    assert res_supported.findings[0].code == "FALSE_REASSURANCE_BLOCKED"


# ═════════════════════════════════════════════════════════════════════════════
# F2 — Workflow semantic gates (RB-002)
# ═════════════════════════════════════════════════════════════════════════════


def test_f2_1_question_gate_allows_correct_suppression_and_requires_all_emitted_material():
    """Suppression of immaterial questions is not a failure; all emitted questions must be material."""
    from cmm.domains.concerns.operations import identify_open_questions_result
    from cmm.domains.concerns.workflows import build_concerns_workflow_definitions

    # 1 material question + 1 immaterial question
    candidates = (
        {
            "question": "Has this happened before?",
            "changes": ("meaning",),
        },
        {
            "question": "What font should we use?",
            "changes": (),
        },
    )
    result = identify_open_questions_result(questions=candidates)
    assert result["ritual_questions_suppressed"] == 1
    assert len(result["questions"]) == 1
    assert result["all_questions_material"] is True

    # Check workflow gate
    wfs = build_concerns_workflow_definitions()
    open_concern = next(w for w in wfs if w.workflow_id == "concerns.open_concern_conversation")
    gate_node = next(n for n in open_concern.nodes if n.node_id == "material_question_gate")

    # Gate condition must match producer field
    for k, v in gate_node.wait_condition.items():
        assert result.get(k) == v, f"Workflow gate condition {k}={v} must match producer result {result.get(k)}"


def test_f2_2_catastrophic_escalation_all_seven_transitions():
    """All seven canonical catastrophic escalation transitions are detected by producer output."""
    from cmm.domains.concerns.operations import separate_reality_interpretation_result
    from cmm.domains.concerns.rules import (
        _CATASTROPHIC_PROMOTIONS,
        detect_catastrophic_escalation,
    )
    from cmm.domains.concerns.workflows import build_concerns_workflow_definitions

    transitions = [
        ("possibility", "probability"),
        ("ambiguity", "warning_sign"),
        ("change", "deterioration"),
        ("silence", "rejection"),
        ("symptom", "serious_disease"),
        ("setback", "failure"),
        ("uncertainty", "danger"),
    ]

    for src, prop in transitions:
        # Direct rule helper
        rule_res = detect_catastrophic_escalation(
            source_state={"kind": src},
            proposed_state={"kind": prop},
        )
        assert rule_res["evaluated"] is True
        assert rule_res["blocked"] is True
        assert rule_res["source_kind"] == src
        assert rule_res["proposed_kind"] == prop

        # Producer operation output
        op_res = separate_reality_interpretation_result(
            transitions=[{"source_kind": src, "proposed_kind": prop}]
        )
        assert op_res["catastrophic_promotions_detected"] >= 1
        assert op_res["catastrophic_escalation_present"] is False  # Safely caught & blocked!


def test_f2_2_safely_blocked_fact_label_promotion_passes_catastrophic_gate():
    """A safely blocked fact-label promotion does not fail the catastrophic gate."""
    from cmm.domains.concerns.operations import separate_reality_interpretation_result
    from cmm.domains.concerns.workflows import build_concerns_workflow_definitions

    # Caller attempts to promote an interpretation to fact
    input_statement = {
        "statement": "they reject me",
        "level": "interpretation",
        "fact": True,
    }
    result = separate_reality_interpretation_result(statements=[input_statement])
    assert result["promotions_blocked_total"] == 1
    assert result["interpretation_promoted_to_fact"] is False
    assert result["catastrophic_escalation_present"] is False

    # Check workflow gate
    wfs = build_concerns_workflow_definitions()
    reality_check = next(w for w in wfs if w.workflow_id == "concerns.reassurance_review")
    prop_gate = next(n for n in reality_check.nodes if n.node_id == "proportionality_gate")

    for k, v in prop_gate.wait_condition.items():
        assert result.get(k) == v, f"Workflow gate condition {k}={v} must match producer result {result.get(k)}"


# ═════════════════════════════════════════════════════════════════════════════
# F3 — Wire caveat stacking into canonical runtime path (RI-001)
# ═════════════════════════════════════════════════════════════════════════════


def test_f3_caveat_stacking_enforced_by_rule_and_presentation():
    """Remote technical negative caveats are filtered by rule and do not stack in output."""
    from datetime import datetime, timezone
    from cmm.domains.concerns.presentation import present_concerns_result
    from cmm.domains.concerns.rules import build_concerns_rules

    rules = build_concerns_rules()
    cat_rule = next(r for r in rules if "no_catastrophic_escalation" in r.definition.id)

    proposed_caveats = (
        {
            "caveat": "the building might collapse unexpectedly",
            "materiality": "remote_possibility",
            "relevance": "low",
            "uncertainty": "high",
        },
        {
            "caveat": "there is a severe storm warning in effect today",
            "materiality": "material_warning",
            "grounding": "weather_gov:alert:101",
            "relevance": "high",
            "uncertainty": "low",
        },
    )

    # 1. Rule path filters remote caveat and retains genuine grounded warning
    ctx = ReasoningRuleContext(
        reasoning_id="r-caveats",
        timestamp=datetime.now(timezone.utc),
        metadata={
            "caveats": proposed_caveats,
        },
    )
    rule_res = cat_rule.evaluate(ctx)
    assert rule_res.status == ReasoningRuleResultStatus.APPLIED
    finding = rule_res.findings[0]
    assert finding.metadata["suppressed_caveats_count"] == 1
    assert len(finding.metadata["retained_caveats"]) == 1
    assert finding.metadata["retained_caveats"][0]["caveat"] == "there is a severe storm warning in effect today"
    assert finding.metadata["remote_possibilities_not_stacked"] is True

    # 2. Presentation path filters remote caveats
    presented = present_concerns_result(
        {
            "scenarios": (
                {"statement": "the building might collapse unexpectedly"},
                {"statement": "there is a severe storm warning in effect today"},
            ),
            "caveats": proposed_caveats,
        }
    )
    scenario_texts = [s["statement"] for s in presented["scenarios"]]
    assert "the building might collapse unexpectedly" not in scenario_texts
    assert "there is a severe storm warning in effect today" in scenario_texts


# ═════════════════════════════════════════════════════════════════════════════
# F4 — Finish objective risk grounding (RI-002)
# ═════════════════════════════════════════════════════════════════════════════


def test_f4_objective_risk_grounding_matrix():
    """Subjective severity never creates objective risk without evidence; risk scales with grounded evidence."""
    from cmm.domains.concerns.rules import evaluate_proportional_risk

    # 1. Subjective severity x no evidence => no evidence-derived objective risk
    low_res = evaluate_proportional_risk(severity="low", evidence=())
    assert low_res["risk_level"] in ("none", "unresolved")
    assert low_res["grounded_risk_evidence"] is False

    med_res = evaluate_proportional_risk(severity="medium", evidence=())
    assert med_res["risk_level"] in ("none", "unresolved")
    assert med_res["grounded_risk_evidence"] is False

    high_res = evaluate_proportional_risk(severity="high", evidence=())
    assert high_res["risk_level"] in ("none", "unresolved")
    assert high_res["grounded_risk_evidence"] is False

    # 2. Grounded 1-record risk evidence => calibrated low risk
    rec1 = {
        "identity": "r1",
        "claim": "user missed critical medication dose",
        "stance": "supports_target",
        "grounding": "med_log:1",
        "source_quality": "grounded",
        "temporal_relevance": "current",
    }
    g1_res = evaluate_proportional_risk(severity="low", evidence=(rec1,))
    assert g1_res["risk_level"] == "low"
    assert g1_res["grounded_risk_evidence"] is True

    # 3. Grounded 2-record risk evidence => calibrated higher risk (medium)
    rec2 = {
        "identity": "r2",
        "claim": "user experiencing dizziness",
        "stance": "supports_target",
        "grounding": "vital:2",
        "source_quality": "grounded",
        "temporal_relevance": "current",
    }
    g2_res = evaluate_proportional_risk(severity="low", evidence=(rec1, rec2))
    assert g2_res["risk_level"] == "medium"
    assert g2_res["grounded_risk_evidence"] is True

    # 4. Authorized specialized red flag => preserve specialized high-risk semantics
    spec_res = evaluate_proportional_risk(
        severity="low",
        evidence=(),
        specialized_domain_result={
            "authorized": True,
            "domain_id": "domain:health",
            "red_flags": ["anaphylaxis"],
        },
    )
    assert spec_res["risk_level"] == "high"
    assert spec_res["specialized_ownership_preserved"] is True
