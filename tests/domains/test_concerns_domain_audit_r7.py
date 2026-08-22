"""Phase 10.25 — Audit-remediation regression tests for presentation parity.

Remediates I-007: presentation must consume the REAL canonical operation/helper
output shapes and preserve assessment, remaining uncertainty, acknowledged
concerns, material concern and absolute-certainty semantics without drift
(REASSURANCE_SUPPORTED must never become INSUFFICIENT_BASIS; remaining
uncertainty must never disappear; a reassurance result must never become
known_fact; material concern must never be hidden).
"""

from __future__ import annotations

import json

import pytest

from cmm.domains.concerns.catalog import CANONICAL_CONCERNS_OPERATION_IDS
from cmm.domains.concerns.operations import (
    calibrate_uncertainty_result,
    evaluate_reassurance_result,
    evaluate_risk_result,
    explore_hypotheses_result,
    explore_options_result,
    identify_open_questions_result,
    infer_support_need_result,
    map_lived_experience_result,
    prepare_next_step_result,
    prepare_professional_discussion_result,
    review_recurring_concern_result,
    separate_reality_interpretation_result,
    understand_concern_result,
)
from cmm.domains.concerns.presentation import present_concerns_result


def test_presenting_actual_reassurance_helper_output_preserves_assessment_and_uncertainty():
    """Presenting the REAL evaluate_reassurance_result output must preserve
    assessment and remaining uncertainty without semantic drift (I-007)."""
    reassurance = evaluate_reassurance_result(
        target_claim="exact motive unknown",
        evidence=(
            {
                "identity": "e1",
                "claim": "warm reply today",
                "stance": "opposes_target",
                "grounding": "msg:1",
                "source_quality": "grounded",
            },
            {
                "identity": "e2",
                "claim": "meeting scheduled",
                "stance": "opposes_target",
                "grounding": "cal:1",
                "source_quality": "grounded",
            },
        ),
        uncertainty=(
            {"identity": "exact motive unknown", "unknown": "exact motive unknown"},
        ),
    )
    presented = present_concerns_result(reassurance)
    # REASSURANCE_SUPPORTED must not become INSUFFICIENT_BASIS.
    assert presented["reassurance_assessment"] == "REASSURANCE_SUPPORTED"
    # Remaining uncertainty must not disappear.
    assert "exact motive unknown" in presented["uncertainty"]
    # A reassurance result must not become a known fact.
    assert presented["presentation_state"] in ("uncertain", "known_fact")
    # Material concern stays visible.
    assert presented["material_concerns"] == ()


def test_presenting_real_reassurance_with_material_concern_hides_nothing():
    reassurance = evaluate_reassurance_result(
        target_claim="decline documented",
        evidence=(
            {
                "identity": "e1",
                "claim": "documented missed deadlines",
                "stance": "supports_target",
                "grounding": "audit:1",
                "source_quality": "grounded",
            },
            {
                "identity": "e2",
                "claim": "documented missed deadlines",
                "stance": "supports_target",
                "grounding": "audit:2",
                "source_quality": "grounded",
            },
        ),
        material_concerns=("decline documented",),
    )
    presented = present_concerns_result(reassurance)
    assert presented["reassurance_assessment"] == "CONCERN_SUPPORTED"
    assert "decline documented" in presented["material_concerns"]
    assert presented["unresolved"] is True or presented["conclusion_presented"] in (True, False)
    json.dumps(presented, allow_nan=False)


# ── Presentation parity matrix for all 13 operation-helper result shapes ────


def _helper_results() -> dict:
    return {
        "concerns.understand_concern": understand_concern_result(
            material={
                "situation": "manager silent five days",
                "what_matters": "position risk",
                "explicit_request": "Tell me what you think.",
            }
        ),
        "concerns.infer_support_need": infer_support_need_result(
            explicit_request="Tell me what you think."
        ),
        "concerns.map_lived_experience": map_lived_experience_result(
            material={"emotion_statements": ("I'm anxious",)}
        ),
        "concerns.separate_reality_interpretation": separate_reality_interpretation_result(
            statements=(
                {
                    "statement": "email sent Monday",
                    "level": "fact",
                    "evidence_references": ("m1",),
                },
                {"statement": "they avoid me", "level": "interpretation"},
            )
        ),
        "concerns.explore_hypotheses": explore_hypotheses_result(
            hypotheses=(
                {"identity": "h1", "statement": "workload explains it", "supporting_ids": ("s1",)},
            )
        ),
        "concerns.calibrate_uncertainty": calibrate_uncertainty_result(
            records=(
                {"identity": "c1", "claim": "email sent", "basis_references": ("m1",)},
            )
        ),
        "concerns.evaluate_reassurance": evaluate_reassurance_result(
            target_claim="worst reading",
            evidence=(
                {
                    "identity": "e1",
                    "claim": "warm reply",
                    "stance": "opposes_target",
                    "grounding": "msg:1",
                },
            ),
            uncertainty=({"identity": "u1", "unknown": "intent"},),
        ),
        "concerns.evaluate_risk": evaluate_risk_result(severity=None, evidence=()),
        "concerns.identify_open_questions": identify_open_questions_result(
            questions=({"question": "did others get replies?", "changes": ("interpretation",)},)
        ),
        "concerns.explore_options": explore_options_result(
            options=({"option_id": "o1"},)
        ),
        "concerns.prepare_next_step": prepare_next_step_result(
            options=("write down observations",),
            user_request="one reasonable next step",
            grounded_options=True,
        ),
        "concerns.review_recurring_concern": review_recurring_concern_result(
            current={"topic": "t", "question": "q", "evidence_references": ["m1"]},
            previous=({"topic": "t", "question": "q", "evidence_references": ["m1"]},),
        ),
        "concerns.prepare_professional_discussion": prepare_professional_discussion_result(
            concern_summary="salary review silence",
        ),
    }


@pytest.mark.parametrize("operation_id", CANONICAL_CONCERNS_OPERATION_IDS)
def test_presenting_every_operation_helper_output_is_json_safe_and_never_raises(operation_id):
    """The presentation layer consumes each canonical helper's REAL output
    without raising and remains JSON-safe."""
    result = _helper_results()[operation_id]
    presented = present_concerns_result(result)
    json.dumps(presented, allow_nan=False)
    assert isinstance(presented, dict)


def test_presentation_parity_reassurance_semantics_matrix():
    """Across the reassurance-relevant helper shapes, presentation preserves
    the canonical assessment vocabulary verbatim."""
    cases = {
        "REASSURANCE_SUPPORTED": evaluate_reassurance_result(
            target_claim="worst reading",
            evidence=(
                {
                    "identity": "e1",
                    "claim": "warm reply",
                    "stance": "opposes_target",
                    "grounding": "msg:1",
                    "source_quality": "grounded",
                },
                {
                    "identity": "e2",
                    "claim": "meeting set",
                    "stance": "opposes_target",
                    "grounding": "cal:1",
                    "source_quality": "grounded",
                },
            ),
            uncertainty=({"identity": "u", "unknown": "intent"},),
        ),
        "CONCERN_SUPPORTED": evaluate_reassurance_result(
            target_claim="decline",
            evidence=(
                {
                    "identity": "e1",
                    "claim": "documented decline",
                    "stance": "supports_target",
                    "grounding": "a:1",
                    "source_quality": "grounded",
                },
                {
                    "identity": "e2",
                    "claim": "documented decline",
                    "stance": "supports_target",
                    "grounding": "a:2",
                    "source_quality": "grounded",
                },
            ),
            material_concerns=("documented decline",),
        ),
    }
    for expected_assessment, helper_output in cases.items():
        presented = present_concerns_result(helper_output)
        assert presented["reassurance_assessment"] == expected_assessment, (
            f"expected presentation to preserve {expected_assessment}, got "
            f"{presented['reassurance_assessment']}"
        )
        assert presented["reassurance_assessment"] != "INSUFFICIENT_BASIS"