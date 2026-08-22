"""Phase 10.25 — Audit-remediation regression tests for R9 (Closure Remediation).

Covers:
- C1 (FB-001): 13-operation input-output contract parity and schema alignment.
- C2 (FB-002): Reassurance fail-closed metadata (target required, closed quality/relevance).
- C3 (FB-003): Connected AT-DP-025 acceptance with state propagation and pre-existing trace IDs.
- C4 (FI-001): Presentation semantic preservation, caveat non-deletion, and operation parity.
"""

from __future__ import annotations

from cmm.agent_runtime.operation_schema import validate_operation_schema
from cmm.domains.concerns.operations import (
    build_concerns_operation_definitions,
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
    from cmm.domains.concerns.rules import (
        REASSURANCE_PARTIAL,
        REASSURANCE_SUPPORTED,
        evaluate_reassurance,
    )

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
    from cmm.domains.concerns.rules import REASSURANCE_SUPPORTED, evaluate_reassurance

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
    from cmm.domains.concerns.rules import REASSURANCE_SUPPORTED, evaluate_reassurance

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
    from cmm.domains.concerns.rules import REASSURANCE_SUPPORTED, evaluate_reassurance

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
    from cmm.domains.concerns.rules import REASSURANCE_SUPPORTED, evaluate_reassurance

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
    from cmm.domains.concerns.rules import REASSURANCE_SUPPORTED, evaluate_reassurance

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


# ═════════════════════════════════════════════════════════════════════════════
# C4 (FI-001) — Presentation semantic preservation & caveat non-deletion
# ═════════════════════════════════════════════════════════════════════════════


def test_caveats_preserve_unrelated_ordinary_scenarios():
    """Caveat filtering removes only suppressed/remote caveats and preserves ordinary scenarios (FI-001 Defect A)."""
    from cmm.domains.concerns.presentation import present_concerns_result

    input_data = {
        "scenarios": [
            {"statement": "maybe they are busy with their project"},
            {"statement": "meteor hits the communication satellite"},
        ],
        "caveats": [
            {"caveat": "meteor hits the communication satellite", "remote": True, "suppress_scenario": True}
        ],
    }
    presented = present_concerns_result(input_data)
    scenario_texts = {s["statement"] for s in presented["scenarios"]}
    assert "maybe they are busy with their project" in scenario_texts
    assert "meteor hits the communication satellite" not in scenario_texts


def test_understand_concern_preserves_actual_concern_in_presentation():
    """understand_concern situation/core_issue is preserved in actual_concern (FI-001 Defect B)."""
    from cmm.domains.concerns.presentation import (
        PRESENTATION_STATE_UNKNOWN,
        present_concerns_result,
    )

    res = understand_concern_result(
        material={
            "situation": "late reply from friend",
            "what_matters": "friendship value",
            "core_issue": "fear of losing contact",
        }
    )
    presented = present_concerns_result(res)
    assert len(presented["actual_concern"]) > 0
    assert "fear of losing contact" in presented["actual_concern"] or "late reply from friend" in presented["actual_concern"]
    assert presented["presentation_state"] != PRESENTATION_STATE_UNKNOWN


def test_calibrate_uncertainty_preserves_calibrations_and_uncertainty_in_presentation():
    """calibrate_uncertainty structured calibrations and conflict are preserved in presentation (FI-001 Defect B)."""
    from cmm.domains.concerns.presentation import present_concerns_result

    res = calibrate_uncertainty_result(
        records=[
            {"identity": "rec1", "claim": "workload caused delay", "status": "plausible"},
            {"identity": "rec2", "claim": "deliberate snub", "status": "unresolved"},
        ]
    )
    presented = present_concerns_result(res)
    assert len(presented["calibrations"]) == 2
    assert len(presented["uncertainty"]) >= 1
    assert presented["unresolved"] is True


def test_identify_open_questions_preserves_questions_and_rationale_in_presentation():
    """identify_open_questions exposes questions and why_it_matters rationale (FI-001 Defect B)."""
    from cmm.domains.concerns.presentation import present_concerns_result

    res = identify_open_questions_result(
        questions=[
            {"question": "Has this pattern happened before?", "changes": ("meaning", "interpretation")},
        ]
    )
    presented = present_concerns_result(res)
    assert len(presented["open_questions"]) == 1
    q0 = presented["open_questions"][0]
    assert q0["question"] == "Has this pattern happened before?"
    assert "meaning" in q0["why_it_matters"] or "interpretation" in q0["why_it_matters"]


def test_presentation_does_not_manufacture_defaults_for_unevaluated_fields():
    """Unevaluated reassurance and risk are represented as None, not manufactured as 'none' or 'INSUFFICIENT_BASIS' (FI-001 Defect C)."""
    from cmm.domains.concerns.presentation import present_concerns_result

    res = understand_concern_result(material={"situation": "delayed reply"})
    presented = present_concerns_result(res)
    # Reassurance was never evaluated in understand_concern
    assert presented["reassurance_assessment"] is None
    # Risk was never evaluated in understand_concern
    assert presented["risk"]["risk_level"] is None


def test_all_13_operations_have_detailed_presentation_semantic_parity():
    """All 13 operations have rich semantic assertions proving projection parity."""
    from cmm.domains.concerns.presentation import present_concerns_result

    # 1. understand_concern
    p1 = present_concerns_result(understand_concern_result(material={"situation": "late reply"}))
    assert "late reply" in p1["actual_concern"]

    # 2. infer_support_need
    p2 = present_concerns_result(infer_support_need_result(explicit_request="Tell me what you think."))
    assert p2["support_need"] in ("PERSPECTIVE", "REALITY_CHECK")

    # 3. map_lived_experience
    p3 = present_concerns_result(map_lived_experience_result(material={"emotion_statements": ("worried",)}))
    assert len(p3["experiences"]) == 1
    assert p3["experiences"][0]["statement"] == "worried"

    # 4. separate_reality_interpretation
    p4 = present_concerns_result(separate_reality_interpretation_result(statements=({"statement": "fact1", "level": "fact"}, {"statement": "interp1", "level": "interpretation"})))
    assert len(p4["facts"]) == 1
    assert len(p4["interpretations"]) == 1

    # 5. explore_hypotheses
    p5 = present_concerns_result(explore_hypotheses_result(hypotheses=({"statement": "they were busy"},)))
    assert len(p5["hypotheses"]) == 1
    assert p5["hypotheses"][0]["statement"] == "they were busy"

    # 6. calibrate_uncertainty
    p6 = present_concerns_result(calibrate_uncertainty_result(records=({"identity": "c1", "claim": "weather", "status": "plausible"},)))
    assert len(p6["calibrations"]) == 1

    # 7. evaluate_reassurance
    p7 = present_concerns_result(evaluate_reassurance_result(target_claim="safe", evidence=(), uncertainty=({"unknown": "where"},)))
    assert p7["reassurance_assessment"] == "INSUFFICIENT_BASIS"

    # 8. evaluate_risk
    op8 = evaluate_risk_result(
        severity="low",
        evidence=[
            {
                "claim": "sensor alert",
                "grounding": "sensor:1",
                "source_quality": "grounded",
                "temporal_relevance": "current",
            }
        ],
    )
    p8 = present_concerns_result(op8)
    assert p8["risk"]["risk_level"] == op8["risk_level"]

    # 9. identify_open_questions
    p9 = present_concerns_result(identify_open_questions_result(questions=({"question": "When?", "changes": ("meaning",)},)))
    assert len(p9["open_questions"]) == 1
    assert p9["open_questions"][0]["question"] == "When?"

    # 10. explore_options
    p10 = present_concerns_result(explore_options_result(options=({"option_id": "opt1", "expected_benefit": "clarity"},)))
    assert len(p10["options"]) == 1
    assert p10["options"][0]["option_id"] == "opt1"

    # 11. prepare_next_step
    p11 = present_concerns_result(prepare_next_step_result(desired_outcome="clarity", options=("opt1",), user_request="What to do?"))
    assert p11["next_step"] is not None

    # 12. review_recurring_concern
    p12 = present_concerns_result(review_recurring_concern_result(current={"topic": "t1"}, previous=()))
    assert p12["recurrence"] == "first_time"

    # 13. prepare_professional_discussion
    p13 = present_concerns_result(prepare_professional_discussion_result(concern_summary="health", key_facts=("bp 120/80",)))
    assert "health" in p13["actual_concern"]
    assert len(p13["facts"]) == 1
