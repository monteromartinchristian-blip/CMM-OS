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
