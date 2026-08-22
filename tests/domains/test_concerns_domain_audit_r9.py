"""Phase 10.25 — Audit-remediation regression tests for R9 (Closure Remediation).

Covers:
- C1 (FB-001): 13-operation input-output contract parity and schema alignment.
- C2 (FB-002): Reassurance fail-closed metadata (target required, closed quality/relevance).
- C3 (FB-003): Connected AT-DP-025 acceptance with state propagation and pre-existing trace IDs.
- C4 (FI-001): Presentation semantic preservation, caveat non-deletion, and operation parity.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
import pytest

from cmm.agent_runtime.operation_schema import validate_operation_schema
from cmm.domains.concerns.operations import (
    build_concerns_operation_definitions,
    understand_concern_result,
    infer_support_need_result,
    map_lived_experience_result,
    separate_reality_interpretation_result,
    explore_hypotheses_result,
    calibrate_uncertainty_result,
    evaluate_reassurance_result,
    evaluate_risk_result,
    identify_open_questions_result,
    explore_options_result,
    prepare_next_step_result,
    review_recurring_concern_result,
    prepare_professional_discussion_result,
)


# ═════════════════════════════════════════════════════════════════════════════
# C1 (FB-001) — Operation input contract parity
# ═════════════════════════════════════════════════════════════════════════════


def test_all_13_operation_input_output_contract_parity():
    """Every of the 13 canonical operations has input+execution+output parity with validate_operation_schema."""
    ops = {op.operation_id: op for op in build_concerns_operation_definitions()}
    assert len(ops) == 13

    representative_inputs = {
        "concerns.understand_concern": (
            understand_concern_result,
            {"material": {"situation": "late reply", "what_matters": "friendship"}},
        ),
        "concerns.infer_support_need": (
            infer_support_need_result,
            {"explicit_request": "Tell me what you think.", "current_signal": "anxious"},
        ),
        "concerns.map_lived_experience": (
            map_lived_experience_result,
            {"material": {"emotion_statements": ("worried",)}},
        ),
        "concerns.separate_reality_interpretation": (
            separate_reality_interpretation_result,
            {
                "statements": [{"statement": "they are angry", "level": "interpretation"}],
                "transitions": [],
                "caveats": [],
            },
        ),
        "concerns.explore_hypotheses": (
            explore_hypotheses_result,
            {"hypotheses": [{"statement": "they were busy"}], "caveats": []},
        ),
        "concerns.calibrate_uncertainty": (
            calibrate_uncertainty_result,
            {"records": [{"statement": "might rain"}]},
        ),
        "concerns.evaluate_reassurance": (
            evaluate_reassurance_result,
            {
                "target_claim": "they are safe",
                "evidence": [
                    {
                        "claim": "spoke to them yesterday",
                        "stance": "supports_target",
                        "grounding": "phone_log:1",
                        "source_quality": "grounded",
                        "temporal_relevance": "current",
                    }
                ],
                "counterevidence": [],
                "uncertainty": [{"unknown": "exact time"}],
                "material_concerns": ["weather delay"],
                "base_plausibility": "high",
                "specialized_domain_result": {"authorized": True, "probability": 0.85},
            },
        ),
        "concerns.evaluate_risk": (
            evaluate_risk_result,
            {
                "evidence": [
                    {
                        "claim": "critical alert",
                        "stance": "supports_target",
                        "grounding": "sensor:1",
                        "source_quality": "grounded",
                        "temporal_relevance": "current",
                    }
                ],
                "severity": "high",
                "immediacy": "immediate",
                "specialized_domain_result": {
                    "authorized": True,
                    "domain_id": "domain:health",
                    "red_flags": ["anaphylaxis"],
                },
            },
        ),
        "concerns.identify_open_questions": (
            identify_open_questions_result,
            {"questions": [{"question": "When did you speak?", "changes": ["meaning"]}]},
        ),
        "concerns.explore_options": (
            explore_options_result,
            {"options": [{"option_id": "opt1", "expected_benefit": "clarity"}]},
        ),
        "concerns.prepare_next_step": (
            prepare_next_step_result,
            {
                "desired_outcome": "clarity",
                "options": ["wait until morning"],
                "user_request": "What should I do?",
                "grounded_options": True,
                "specialized_recommendation": "rest",
                "specialized_domain_result": {"authorized": True},
            },
        ),
        "concerns.review_recurring_concern": (
            review_recurring_concern_result,
            {"current": {"topic": "delay"}, "previous": [], "turns": []},
        ),
        "concerns.prepare_professional_discussion": (
            prepare_professional_discussion_result,
            {
                "concern_summary": "blood pressure symptoms",
                "key_facts": ["bp 140/90"],
                "open_questions": ["dosage change?"],
                "uncertainties": ["cause of spike"],
                "current_impact": "headaches",
                "documents_to_bring": ["log.pdf"],
                "decisions_required": ["adjust meds"],
            },
        ),
    }

    for op_id, (helper_fn, req_input) in representative_inputs.items():
        op_def = ops[op_id]
        # 1. Input validates against input_schema
        in_issues = validate_operation_schema(req_input, op_def.input_schema)
        assert in_issues == (), f"Operation {op_id} input failed input_schema validation: {in_issues}"

        # 2. Same validated input invokes helper
        output = helper_fn(**req_input)
        assert isinstance(output, dict), f"Operation {op_id} helper did not return dict"

        # 3. Helper output validates against output_schema
        out_issues = validate_operation_schema(output, op_def.output_schema)
        assert out_issues == (), f"Operation {op_id} output failed output_schema validation: {out_issues}"


def test_reassurance_request_with_target_and_specialized_result_validates():
    """concerns.evaluate_reassurance input schema accepts target_claim, specialized_domain_result, base_plausibility."""
    ops = {op.operation_id: op for op in build_concerns_operation_definitions()}
    op = ops["concerns.evaluate_reassurance"]

    req = {
        "target_claim": "they are safe",
        "evidence": [
            {
                "claim": "saw them",
                "stance": "supports_target",
                "grounding": "sight",
                "source_quality": "grounded",
                "temporal_relevance": "current",
            }
        ],
        "counterevidence": [],
        "uncertainty": [],
        "material_concerns": ["battery dead"],
        "base_plausibility": "high",
        "specialized_domain_result": {"authorized": True, "probability": 0.9},
    }
    issues = validate_operation_schema(req, op.input_schema)
    assert issues == ()
    result = evaluate_reassurance_result(**req)
    assert result["specialized_authorized"] is True


def test_risk_request_with_immediacy_and_specialized_result_validates():
    """concerns.evaluate_risk input schema accepts immediacy and specialized_domain_result."""
    ops = {op.operation_id: op for op in build_concerns_operation_definitions()}
    op = ops["concerns.evaluate_risk"]

    req = {
        "evidence": [],
        "severity": "high",
        "immediacy": "immediate",
        "specialized_domain_result": {
            "authorized": True,
            "domain_id": "domain:health",
            "red_flags": ["chest_pain"],
        },
    }
    issues = validate_operation_schema(req, op.input_schema)
    assert issues == ()
    result = evaluate_risk_result(**req)
    assert result["risk_level"] == "high"
    assert result["specialized_ownership_preserved"] is True


def test_support_need_validated_input_reaches_helper():
    """concerns.infer_support_need accepts semantic fields directly and infers support need."""
    ops = {op.operation_id: op for op in build_concerns_operation_definitions()}
    op = ops["concerns.infer_support_need"]

    req = {
        "explicit_request": "Tell me what you think.",
        "current_signal": "anxious checking",
        "session_context": {"active_topic": "email silence"},
        "historical_preference": "perspective",
    }
    issues = validate_operation_schema(req, op.input_schema)
    assert issues == ()
    result = infer_support_need_result(**req)
    assert result["support_need"] in ("PERSPECTIVE", "REALITY_CHECK")


def test_prepare_next_step_validated_input_preserves_semantics():
    """concerns.prepare_next_step input schema accepts desired_outcome, grounded_options, specialized_recommendation."""
    ops = {op.operation_id: op for op in build_concerns_operation_definitions()}
    op = ops["concerns.prepare_next_step"]

    req = {
        "desired_outcome": "rest and recover",
        "options": ["take medication", "sleep"],
        "user_request": "What should I do now?",
        "grounded_options": True,
        "specialized_recommendation": "rest",
        "specialized_domain_result": {"authorized": True},
    }
    issues = validate_operation_schema(req, op.input_schema)
    assert issues == ()
    result = prepare_next_step_result(**req)
    assert result["next_step"]["proposal_only"] is True


def test_professional_discussion_validated_input_preserves_semantics():
    """concerns.prepare_professional_discussion input schema accepts uncertainties, current_impact, decisions_required."""
    ops = {op.operation_id: op for op in build_concerns_operation_definitions()}
    op = ops["concerns.prepare_professional_discussion"]

    req = {
        "concern_summary": "blood pressure",
        "key_facts": ["140/90"],
        "open_questions": ["adjust dose?"],
        "uncertainties": ["cause"],
        "current_impact": "dizziness",
        "documents_to_bring": ["vitals.csv"],
        "decisions_required": ["switch prescription"],
    }
    issues = validate_operation_schema(req, op.input_schema)
    assert issues == ()
    result = prepare_professional_discussion_result(**req)
    assert "blood pressure" in result["prepared_content"]
    assert "140/90" in result["prepared_content"]
    assert "dizziness" in result["prepared_content"]


# ═════════════════════════════════════════════════════════════════════════════
# C2 (FB-002) — Reassurance metadata genuinely fail closed
# ═════════════════════════════════════════════════════════════════════════════


def test_missing_target_cannot_fully_reassure():
    """Missing target_claim prevents REASSURANCE_SUPPORTED even with multiple grounded opposing records."""
    from cmm.domains.concerns.rules import evaluate_reassurance, REASSURANCE_SUPPORTED, REASSURANCE_PARTIAL

    ev = (
        {
            "claim": "warm reply",
            "stance": "opposes_target",
            "grounding": "m1",
            "source_quality": "grounded",
            "temporal_relevance": "current",
        },
        {
            "claim": "invited me",
            "stance": "opposes_target",
            "grounding": "m2",
            "source_quality": "grounded",
            "temporal_relevance": "current",
        },
    )
    res = evaluate_reassurance(target_claim=None, evidence=ev)
    assert res["assessment"] != REASSURANCE_SUPPORTED
    assert res["assessment"] == REASSURANCE_PARTIAL
    assert res["target_claim"] is None


def test_missing_source_quality_cannot_fully_reassure():
    """Missing source_quality (None) fails closed and cannot produce REASSURANCE_SUPPORTED."""
    from cmm.domains.concerns.rules import evaluate_reassurance, REASSURANCE_SUPPORTED

    ev = (
        {
            "claim": "warm reply",
            "stance": "opposes_target",
            "grounding": "m1",
            "source_quality": None,
            "temporal_relevance": "current",
        },
        {
            "claim": "invited me",
            "stance": "opposes_target",
            "grounding": "m2",
            "source_quality": None,
            "temporal_relevance": "current",
        },
    )
    res = evaluate_reassurance(target_claim="they are ignoring me", evidence=ev)
    assert res["assessment"] != REASSURANCE_SUPPORTED


def test_unknown_source_quality_cannot_fully_reassure():
    """Unknown source_quality ('banana') fails closed and cannot produce REASSURANCE_SUPPORTED."""
    from cmm.domains.concerns.rules import evaluate_reassurance, REASSURANCE_SUPPORTED

    ev = (
        {
            "claim": "warm reply",
            "stance": "opposes_target",
            "grounding": "m1",
            "source_quality": "banana",
            "temporal_relevance": "current",
        },
        {
            "claim": "invited me",
            "stance": "opposes_target",
            "grounding": "m2",
            "source_quality": "banana",
            "temporal_relevance": "current",
        },
    )
    res = evaluate_reassurance(target_claim="they are ignoring me", evidence=ev)
    assert res["assessment"] != REASSURANCE_SUPPORTED


def test_missing_temporal_relevance_cannot_fully_reassure():
    """Missing temporal_relevance (None) fails closed and cannot produce REASSURANCE_SUPPORTED."""
    from cmm.domains.concerns.rules import evaluate_reassurance, REASSURANCE_SUPPORTED

    ev = (
        {
            "claim": "warm reply",
            "stance": "opposes_target",
            "grounding": "m1",
            "source_quality": "grounded",
            "temporal_relevance": None,
        },
        {
            "claim": "invited me",
            "stance": "opposes_target",
            "grounding": "m2",
            "source_quality": "grounded",
            "temporal_relevance": None,
        },
    )
    res = evaluate_reassurance(target_claim="they are ignoring me", evidence=ev)
    assert res["assessment"] != REASSURANCE_SUPPORTED


def test_unknown_temporal_relevance_cannot_fully_reassure():
    """Unknown temporal_relevance ('nonsense') fails closed and cannot produce REASSURANCE_SUPPORTED."""
    from cmm.domains.concerns.rules import evaluate_reassurance, REASSURANCE_SUPPORTED

    ev = (
        {
            "claim": "warm reply",
            "stance": "opposes_target",
            "grounding": "m1",
            "source_quality": "grounded",
            "temporal_relevance": "nonsense",
        },
        {
            "claim": "invited me",
            "stance": "opposes_target",
            "grounding": "m2",
            "source_quality": "grounded",
            "temporal_relevance": "nonsense",
        },
    )
    res = evaluate_reassurance(target_claim="they are ignoring me", evidence=ev)
    assert res["assessment"] != REASSURANCE_SUPPORTED


def test_explicit_grounded_current_evidence_can_fully_reassure():
    """Explicit recognized strong quality ('grounded') and temporal relevance ('current') can produce REASSURANCE_SUPPORTED."""
    from cmm.domains.concerns.rules import evaluate_reassurance, REASSURANCE_SUPPORTED

    ev = (
        {
            "claim": "warm reply",
            "stance": "opposes_target",
            "grounding": "m1",
            "source_quality": "grounded",
            "temporal_relevance": "current",
        },
        {
            "claim": "invited me",
            "stance": "opposes_target",
            "grounding": "m2",
            "source_quality": "grounded",
            "temporal_relevance": "current",
        },
    )
    res = evaluate_reassurance(target_claim="they are ignoring me", evidence=ev)
    assert res["assessment"] == REASSURANCE_SUPPORTED
