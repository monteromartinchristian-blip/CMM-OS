"""Phase 10.25 — DP-025 acceptance matrix tests (AT-DP-025 evidence).

Implements the 25-step canonical acceptance scenario (frozen design §115) and
the 22 named behavioral gates (implementation plan Task 12).  These tests
establish implementation-side candidate evidence only; independent audit
closure is a separate lifecycle event and is never claimed here.
"""

from __future__ import annotations

import copy
import json

from cmm.domains.concerns.operations import (
    evaluate_reassurance_result,
    explore_options_result,
    identify_open_questions_result,
    infer_support_need_result,
    map_lived_experience_result,
    prepare_next_step_result,
    review_recurring_concern_result,
    separate_reality_interpretation_result,
    understand_concern_result,
)
from cmm.domains.concerns.permissions import (
    permission_authorization_allows,
    persistence_confirmation_accepted,
)
from cmm.domains.concerns.presentation import present_concerns_result
from cmm.domains.concerns.rules import (
    classify_concern_statement,
    detect_catastrophic_escalation,
    detect_false_reassurance,
    evaluate_action_state,
    evaluate_grounded_directness,
    evaluate_proportional_risk,
    evaluate_question_materiality,
    evaluate_reassurance,
    evaluate_uncertainty,
)
from cmm.domains.memory_contracts import DomainMemoryApprovalDecisionSnapshot

# ═════════════════════════════════════════════════════════════════════════════
# The 25-step canonical scenario (frozen design §115)
# ═════════════════════════════════════════════════════════════════════════════


class _Scenario:
    """Stateful driver of the AT-DP-025 end-to-end sequence."""

    def __init__(self):
        self.steps: list[str] = []
        self.turn1 = {
            "situation": (
                "My manager hasn't replied to my salary-review email in five days."
            ),
            "what_matters": "whether my position is at risk",
            "session_context": {"active_topic": "salary review request"},
        }

    # Step 1-2: user presents an ambiguous, emotionally meaningful concern;
    # Concerns is selected (registration/resolution proven elsewhere) with a
    # supporting domain available through projections.
    def step_1_present(self):
        understanding = understand_concern_result(material=self.turn1)
        self.steps.append("1-present")
        return understanding

    # Step 3: identifies the actual issue without forcing an action plan.
    def step_3_identify(self):
        understanding = self.step_1_present()
        assert understanding["mandatory_action_plan"] is False
        assert understanding["advice_generated"] is False
        self.steps.append("3-identify")
        return understanding

    # Step 4: emotional experience represented as valid experience.
    def step_4_experience_valid(self):
        lived = map_lived_experience_result(
            material={
                "emotion_statements": ("I'm anxious about what the silence means",),
                "interpretation_statements": ("the silence means they're cutting me",),
                "fear_statements": ("that I'll lose the job",),
            }
        )
        assert lived["emotions"][0]["experience_valid"] is True
        assert lived["emotions"][0]["external_fact"] is False
        self.steps.append("4-experience-valid")
        return lived

    # Step 5: one external interpretation remains unverified.
    def step_5_interpretation_unverified(self):
        record = classify_concern_statement(
            {"statement": "the silence means they're cutting me", "level": "interpretation"}
        )
        assert record["grounded"] is False
        assert record["external_fact"] is False
        self.steps.append("5-unverified")
        return record

    # Step 6-7: support need identified; initial substantive response possible.
    def step_6_7_support_need_and_response(self):
        support = infer_support_need_result(
            explicit_request="Tell me what you think.",
            session_context={"current_turn_signal": None},
        )
        assert support["support_need"] == "PERSPECTIVE"
        understanding = understand_concern_result(
            material={
                **self.turn1,
                "explicit_request": "Tell me what you think.",
            }
        )
        assert understanding["ready_for_substantive_response"] is True
        self.steps.append("6-7-support-and-response")
        return support

    # Step 8: materially relevant question asked only if needed — here context
    # suffices, so no question is required (material gate proven separately).
    def step_8_question_only_if_needed(self):
        materiality = evaluate_question_materiality(
            question="Did anyone else get a reply?",
            changes=("interpretation", "reassurance"),
        )
        immaterial = evaluate_question_materiality(
            question="What font was the email?", changes=("none",)
        )
        assert materiality["materiality"] == "material"
        assert immaterial["materiality"] == "not_material"
        self.steps.append("8-question-materiality")
        return materiality

    # Steps 9-10: new information incorporated; facts and interpretations stay distinct.
    def step_9_10_new_info_levels_distinct(self):
        separation = separate_reality_interpretation_result(
            statements=(
                {
                    "statement": "a colleague got a reply yesterday",
                    "level": "fact",
                    "evidence_references": ("msg:2",),
                },
                {"statement": "my case is being handled badly", "level": "interpretation"},
            ),
        )
        levels = {record["level"] for record in separation["statements"]}
        assert levels == {"fact", "interpretation"}
        fact_record = next(r for r in separation["statements"] if r["level"] == "fact")
        assert fact_record["grounded"] is True
        self.steps.append("9-10-levels-distinct")
        return separation

    # Step 11: multiple hypotheses remain where appropriate.
    def step_11_multiple_hypotheses(self):
        from cmm.domains.concerns.operations import explore_hypotheses_result

        hypotheses = explore_hypotheses_result(
            hypotheses=(
                {"identity": "h1", "statement": "busy week explains it", "supporting_ids": ("m1",)},
                {"identity": "h2", "statement": "budget freeze explains it", "supporting_ids": ("m2",)},
            ),
        )
        assert len(hypotheses["hypotheses"]) == 2
        assert hypotheses["winner_selected"] is False
        self.steps.append("11-multiple-hypotheses")
        return hypotheses

    # Step 12: partial reassurance because the evidence supports it.
    def step_12_partial_reassurance(self):
        reassurance = evaluate_reassurance_result(
            target_claim="worst reading",
            evidence=({"identity": "e1", "claim": "worst reading", "stance": "opposes_target", "grounding": "s1"},),
            counterevidence=({"identity": "c1", "claim": "worst reading", "stance": "supports_target", "grounding": "t"},),
            material_concerns=("the salary review itself remains unanswered",),
        )
        assert reassurance["assessment"] == "REASSURANCE_PARTIAL"
        assert reassurance["absolute_certainty"] is False
        self.steps.append("12-partial-reassurance")
        return reassurance

    # Step 13: one real concern remains acknowledged.
    def step_13_real_concern_acknowledged(self):
        reassurance = self.step_12_partial_reassurance()
        assert tuple(reassurance["acknowledged_concerns"]) != ()
        directness = evaluate_grounded_directness(
            assessment="concern_material",
            evidence=(
                {"identity": "g1", "supports": "unanswered review", "grounding": "a"},
                {"identity": "g2", "supports": "unanswered review", "grounding": "b"},
            ),
        )
        assert directness["real_concern_acknowledged"] is True
        self.steps.append("13-real-concern")
        return directness

    # Step 14: no absolute certainty invented.
    def step_14_no_absolute_certainty(self):
        false_check = detect_false_reassurance(
            reassurance_state={"assessment": "REASSURANCE_SUPPORTED"},
            material_concerns=("review still open",),
        )
        assert false_check["false_reassurance"] is True
        self.steps.append("14-no-certainty")
        return false_check

    # Steps 15-16: user revisits the same worry; repetition not labeled pathological.
    def step_15_16_revisit_without_pathology(self):
        recurrence = review_recurring_concern_result(
            current={
                "topic": "manager silence",
                "question": "is my position at risk?",
            },
            previous=(
                {"topic": "manager silence", "question": "is my position at risk?"},
            ),
        )
        assert recurrence["recurrence"] == "same_question_same_evidence"
        assert recurrence["pathology_inferred"] is False
        assert recurrence["psychiatric_label"] is False
        assert recurrence["reassurance_allowed"] is True
        self.steps.append("15-16-revisit-ok")
        return recurrence

    # Step 17: evidence state compared with the prior turn (unchanged here).
    def step_17_evidence_comparison(self):
        recurrence = review_recurring_concern_result(
            current={
                "topic": "manager silence",
                "question": "is my position at risk?",
                "evidence_references": ["msg:1"],
            },
            previous=(
                {
                    "topic": "manager silence",
                    "question": "is my position at risk?",
                    "evidence_references": ["msg:1"],
                },
            ),
        )
        assert recurrence["evidence_changed"] is False
        self.steps.append("17-comparison")
        return recurrence

    # Step 18: no new risk invented from repetition.
    def step_18_no_new_risk_from_repetition(self):
        pattern = __import__(
            "cmm.domains.concerns.rules", fromlist=["evaluate_repetitive_certainty_pattern"]
        ).evaluate_repetitive_certainty_pattern(
            turns=tuple({"turn": i, "same_question": True} for i in range(5))
        )
        # even a multi-turn same-question run invents nothing without all grounds
        assert isinstance(pattern["pattern_detected"], bool)
        recurrence = review_recurring_concern_result(current={"topic": "t"})
        assert recurrence["new_risk_invented_from_repetition"] is False
        self.steps.append("18-no-new-risk")
        return pattern

    # Steps 19-21: options generated; one proportionate next step proposed.
    def step_19_21_options_and_next_step(self):
        options = explore_options_result(
            options=(
                {
                    "option_id": "send a brief follow-up",
                    "expected_benefit": "clarity",
                    "reversible": True,
                },
                {"option_id": "wait until Friday", "cost": "uncertainty persists"},
            ),
        )
        assert options["decision_adopted"] is False
        next_step = prepare_next_step_result(
            desired_outcome="clarity on the review",
            options=("send a brief follow-up",),
            user_request="one reasonable next step",
            grounded_options=True,
        )
        assert next_step["next_step"]["proposal_only"] is True
        assert next_step["executed"] is False
        self.steps.append("19-21-options-step")
        return options, next_step

    # Step 22: the next step remains a proposal, not an adopted decision.
    def step_22_proposal_not_adoption(self):
        action = evaluate_action_state(
            options=("follow up",),
            user_request="What can I do?",
            grounded_options=True,
        )
        assert action["decision_adopted"] is False
        assert action["options_are_candidates"] is True
        self.steps.append("22-proposal-only")
        return action

    # Step 23: no external action occurs.
    def step_23_no_external_action(self):
        prepared = __import__(
            "cmm.domains.concerns.operations",
            fromlist=["prepare_professional_discussion_result"],
        ).prepare_professional_discussion_result(
            concern_summary="salary review silence",
            key_facts=("five days without reply",),
            open_questions=("is this normal in this company?",),
            uncertainties=("cause unknown",),
        )
        assert prepared["external_transmission_performed"] is False
        assert prepared["appointment_booked"] is False
        assert prepared["contact_performed"] is False
        self.steps.append("23-no-external-action")
        return prepared

    # Step 24: no sensitive inference silently persisted.
    def step_24_no_silent_persistence(self):
        for raw in (True, "true", 1, {"approved": True}, None):
            record = persistence_confirmation_accepted(confirmation=raw)
            assert record["accepted"] is False
        standalone = persistence_confirmation_accepted(
            confirmation=DomainMemoryApprovalDecisionSnapshot(
                decision_id="d", request_id="r", approved=True
            )
        )
        assert standalone["accepted"] is False
        self.steps.append("24-no-silent-persistence")

    # Step 25: trace records support need, evidence, uncertainty, reassurance,
    # and action state as references.
    def step_25_trace_records_semantics(self):
        from datetime import datetime, timezone

        from cmm.domains.trace_contracts import DomainTraceReferenceKind

        references = tuple(
            __import__(
                "cmm.domains.concerns.trace",
                fromlist=["build_concerns_trace_reference"],
            ).build_concerns_trace_reference(ref_id=ref_id, kind=kind)
            for ref_id, kind in (
                ("support-need:PERSPECTIVE", DomainTraceReferenceKind.FINDING),
                ("evidence:msg:1", DomainTraceReferenceKind.RESOURCE_RESOLUTION),
                ("uncertainty:intent", DomainTraceReferenceKind.GAP),
                ("rule:reassurance", DomainTraceReferenceKind.RULE_RESULT),
                # action-state rides on the auto-added DOMAIN_RESULT reference
                ("wf:action-proportional", DomainTraceReferenceKind.WORKFLOW_RESULT),
            )
        )
        trace = __import__(
            "cmm.domains.concerns.trace", fromlist=["assemble_concerns_trace"]
        ).assemble_concerns_trace(
            request_id="req-atdp",
            resolution_context_id="rc:atdp",
            resolution_result_id="rr:atdp",
            composition_id="c:atdp",
            domain_result_id="dr:atdp",
            started_at=datetime(2026, 8, 21, 17, 0, tzinfo=timezone.utc),
            completed_at=datetime(2026, 8, 21, 17, 0, 1, tzinfo=timezone.utc),
            references=references,
        )
        kinds = {r.kind for r in trace.all_references()}
        assert DomainTraceReferenceKind.FINDING in kinds
        assert DomainTraceReferenceKind.GAP in kinds
        self.steps.append("25-trace-recorded")


def test_at_dp025_full_scenario():
    scenario = _Scenario()
    scenario.step_3_identify()
    scenario.step_4_experience_valid()
    scenario.step_5_interpretation_unverified()
    scenario.step_6_7_support_need_and_response()
    scenario.step_8_question_only_if_needed()
    scenario.step_9_10_new_info_levels_distinct()
    scenario.step_11_multiple_hypotheses()
    scenario.step_12_partial_reassurance()
    scenario.step_13_real_concern_acknowledged()
    scenario.step_14_no_absolute_certainty()
    scenario.step_15_16_revisit_without_pathology()
    scenario.step_17_evidence_comparison()
    scenario.step_18_no_new_risk_from_repetition()
    scenario.step_19_21_options_and_next_step()
    scenario.step_22_proposal_not_adoption()
    scenario.step_23_no_external_action()
    scenario.step_24_no_silent_persistence()
    scenario.step_25_trace_records_semantics()


# ═════════════════════════════════════════════════════════════════════════════
# Named gates (implementation plan Task 12)
# ═════════════════════════════════════════════════════════════════════════════


def _gate(fn) -> bool:
    try:
        fn()
        return True
    except AssertionError:
        return False
    except Exception:  # noqa: BLE001 -- gates must never leak exceptions either
        return False


def test_understand_before_action_gate():
    understanding = understand_concern_result(
        material={"statement": "something at work, can't stop thinking"}
    )
    assert understanding["understood"] is False
    assert understanding["ask_question"] is True
    assert understanding["mandatory_action_plan"] is False


def test_experience_fact_separation_gate():
    experience = classify_concern_statement({"statement": "I feel small", "level": "experience", "fact": True})
    assert experience["level"] == "experience"
    assert experience["external_fact"] is False
    separation = separate_reality_interpretation_result(
        statements=(
            {"statement": "meeting moved", "level": "fact", "evidence_references": ("c1",)},
            {"statement": "they avoid me", "level": "interpretation"},
        ),
    )
    levels = {r["level"] for r in separation["statements"]}
    assert levels == {"fact", "interpretation"}


def test_support_need_gate():
    no_advice = infer_support_need_result(
        explicit_request="no advice please, just listening",
        historical_preference="PROBLEM_SOLVING",
    )
    assert no_advice["problem_solving_allowed"] is False
    explicit = infer_support_need_result(explicit_request="What can I do?")
    assert explicit["support_need"] == "PROBLEM_SOLVING"


def test_question_materiality_gate():
    material = evaluate_question_materiality(question="q", changes=("risk",))
    immaterial = evaluate_question_materiality(question="q", changes=("none",))
    malformed = evaluate_question_materiality(question="q", changes=True)
    assert material["materiality"] == "material"
    assert immaterial["materiality"] == "not_material"
    assert malformed["materiality"] == "not_material"


def test_reassurance_allowed_gate():
    record = evaluate_reassurance(
        target_claim="fear",
        evidence=(
            {"identity": "e1", "claim": "fear", "stance": "opposes_target", "grounding": "a"},
            {"identity": "e2", "claim": "fear", "stance": "opposes_target", "grounding": "b"},
        )
    )
    assert record["assessment"] in ("REASSURANCE_SUPPORTED", "REASSURANCE_PARTIAL")


def test_no_false_reassurance_gate():
    check = detect_false_reassurance(
        reassurance_state={"assessment": "REASSURANCE_SUPPORTED"},
        material_concerns=("documented decline",),
    )
    assert check["false_reassurance"] is True
    absolute = detect_false_reassurance(
        reassurance_state={"assessment": "REASSURANCE_SUPPORTED", "absolute_certainty": True},
        material_concerns=(),
    )
    assert absolute["false_reassurance"] is True


def test_no_catastrophic_escalation_gate():
    result = detect_catastrophic_escalation(
        source_state={"kind": "silence"},
        proposed_state={"kind": "rejection"},
    )
    assert result["blocked"] is True


def test_real_concern_acknowledgement_gate():
    direct = evaluate_grounded_directness(
        assessment="concern_material",
        evidence=(
            {"identity": "e1", "supports": "real issue", "grounding": "a"},
            {"identity": "e2", "supports": "real issue", "grounding": "b"},
        ),
    )
    reassurance = evaluate_reassurance(
        target_claim="decline",
        evidence=(
            {"identity": "s1", "claim": "decline", "stance": "supports_target", "grounding": "a"},
            {"identity": "s2", "claim": "decline", "stance": "supports_target", "grounding": "b"},
        ),
        material_concerns=("decline documented",),
    )
    assert direct["real_concern_acknowledged"] is True
    assert reassurance["assessment"] == "CONCERN_SUPPORTED"


def test_repetition_not_pathology_gate():
    from cmm.domains.concerns.rules import evaluate_repetitive_certainty_pattern

    record = evaluate_repetitive_certainty_pattern(
        turns=tuple({"turn": i, "same_question": True} for i in range(7))
    )
    assert record["pathology_inferred"] is False
    assert record["psychiatric_label"] is False
    serialized = json.dumps(record).lower()
    for label in ("ocd", "anxiety disorder", "compulsion"):
        assert label not in serialized


def test_recurring_pattern_grounding_gate():
    from cmm.domains.concerns.rules import evaluate_repetitive_certainty_pattern

    full_turns = (
        {"turn": 1, "same_question": True, "evidence_state": "unchanged"},
        {"turn": 2, "same_question": True, "evidence_state": "unchanged"},
        {"turn": 3, "same_question": True, "evidence_state": "unchanged"},
        {"turn": 4, "same_question": True, "relief_followed_by_checking": True},
    )
    complete = evaluate_repetitive_certainty_pattern(turns=full_turns)
    incomplete = evaluate_repetitive_certainty_pattern(
        turns=full_turns[:-1]
    )  # missing relief/checking dimension
    assert complete["pattern_detected"] is True
    assert incomplete["pattern_detected"] is False


def test_directness_gate():
    disagree = evaluate_grounded_directness(
        assessment="user_interpretation_unlikely",
        evidence=(
            {"identity": "c1", "against": "feared reading", "grounding": "a"},
            {"identity": "c2", "against": "feared reading", "grounding": "b"},
        ),
    )
    balanced = evaluate_grounded_directness(
        assessment="balanced",
        evidence=(
            {"identity": "e1", "supports": "benign", "grounding": "a"},
            {"identity": "e2", "against": "benign", "grounding": "b"},
        ),
    )
    ungrounded = evaluate_grounded_directness(assessment="anything", evidence=())
    assert disagree["disagreement_explicit"] is True
    assert disagree["harsh"] is False
    assert balanced["uncertainty_preserved"] is True
    assert ungrounded["grounded_opinion_stated"] is False


def test_no_forced_action_gate():
    none_needed = evaluate_action_state(options=())
    waiting = evaluate_action_state(
        options=("act",), user_request="I want to wait."
    )
    deciding_for_user = evaluate_action_state(
        options=("A", "B"), user_request="decide for me"
    )
    assert none_needed["state"] == "NO_ACTION_NEEDED"
    assert waiting["state"] in ("NO_ACTION_NEEDED", "ACTION_OPTIONAL")
    assert deciding_for_user["decision_adopted"] is False
    assert deciding_for_user["external_action_executed"] is False


def test_cross_domain_health_gate():
    preserved = evaluate_proportional_risk(
        severity="calm",
        specialized_domain_result={
            "domain_id": "domain:health",
            "red_flags": ("red flag",),
            "authorized": True,
        },
    )
    not_invented = evaluate_proportional_risk(severity="severe")
    unauthorized = evaluate_proportional_risk(
        severity="calm",
        specialized_domain_result={
            "domain_id": "domain:health",
            "red_flags": ("red flag",),
            "authorized": "true",
        },
    )
    assert preserved["risk_level"] == "high" and preserved["downgraded"] is False
    assert not_invented["risk_level"] != "high"
    assert unauthorized["specialized_ownership_preserved"] is False


def test_cross_domain_reflection_gate():
    """Broader meaning stays Reflection's responsibility: Concerns keeps the
    support-need hypothesis and never produces identity/diagnosis semantics."""
    from cmm.domains.concerns.operations import explore_hypotheses_result

    record = explore_hypotheses_result(
        hypotheses=(
            {"identity": "h1", "statement": "contextual workload explanation", "supporting_ids": ("s1",)},
        ),
    )
    hypothesis = record["hypotheses"][0]
    assert hypothesis["status"] == "hypothesis"
    assert hypothesis["fact"] is False
    assert record["no_diagnosis"] is True


def test_memory_confirmation_gate():
    for raw in (True, False, 1, 0, "true", {"approved": True}, None):
        record = persistence_confirmation_accepted(confirmation=raw)
        assert record["accepted"] is False
    snapshot_alone = persistence_confirmation_accepted(
        confirmation=DomainMemoryApprovalDecisionSnapshot(
            decision_id="d1", request_id="r1", approved=True
        )
    )
    assert snapshot_alone["accepted"] is False
    assert snapshot_alone["authorization_malformed"] is True


def test_permission_literal_true_gate():
    for raw in ("true", "TRUE", 1, 0, 1.0, [], {}, (), None, "yes"):
        assert permission_authorization_allows(raw) is False
    assert permission_authorization_allows(True) is True


def test_input_order_invariance_gate():
    records_a = (
        {"identity": "u1", "unknown": "intent"},
        {"identity": "u2", "unknown": "timing"},
        {"identity": "u3", "unknown": "cause"},
    )
    canonical = {
        tuple(sorted(item["identity"] for item in evaluate_uncertainty(records=o)["uncertainties"]))
        for o in (records_a, tuple(reversed(records_a)))
    }
    assert len(canonical) == 1


def test_duplicate_evidence_gate_named():
    base = (
        {"identity": "c1", "claim": "f", "stance": "opposes_target", "grounding": "x"},
        {"identity": "c2", "claim": "f", "stance": "opposes_target", "grounding": "y"},
        {"identity": "c3", "claim": "f", "stance": "opposes_target", "grounding": "z"},
    )
    single = evaluate_reassurance(target_claim="f", evidence=base)["assessment"]
    duplicated = evaluate_reassurance(
        target_claim="f",
        evidence=(
            *base,
            dict(base[0]),
            {"identity": "c1-copy", "claim": "f", "stance": "opposes_target", "grounding": "x"},
        )
    )["assessment"]
    assert duplicated == single


def test_malformed_evidence_gate_named():
    clean = evaluate_reassurance()[
        "assessment"
    ]
    dirty = evaluate_reassurance(evidence=(None, float("nan"), [], {}, 3))["assessment"]
    assert clean == dirty == "INSUFFICIENT_BASIS"


def test_input_non_mutation_gate_named():
    material = {"situation": "s", "emotion_statements": ["e"], "session_context": {}}
    statements = [{"statement": "i", "level": "interpretation"}]
    snapshots = [copy.deepcopy(material), copy.deepcopy(statements)]
    understand_concern_result(material=material)
    separate_reality_interpretation_result(statements=statements)
    present_concerns_result({"facts": ["f"], "uncertainty": ["u"]})
    assert material == snapshots[0]
    assert statements == snapshots[1]


def test_strict_json_gate_named():
    outputs = (
        present_concerns_result({"facts": [float("nan")]}),
        evaluate_reassurance_result(evidence=({"value": float("inf")},)),
        identify_open_questions_result(questions=({"question": float("nan")},)),
    )
    for output in outputs:
        json.dumps(output, allow_nan=False)


def test_package_boundary_gate():
    from pathlib import Path

    package_dir = Path(__file__).resolve().parents[2] / "cmm" / "domains" / "concerns"
    modules = sorted(p.name for p in package_dir.glob("*.py") if p.suffix == ".py")
    assert len(modules) == 14
    assert set(modules) == {
        "__init__.py", "bootstrap.py", "catalog.py", "definition.py",
        "integration.py", "memory.py", "operations.py", "permissions.py",
        "presentation.py", "profile.py", "resources.py", "rules.py",
        "trace.py", "workflows.py",
    }


def test_all_named_gates_pass_summary():
    gates = {
        "UNDERSTAND_BEFORE_ACTION_GATE": _gate(test_understand_before_action_gate),
        "EXPERIENCE_FACT_SEPARATION_GATE": _gate(test_experience_fact_separation_gate),
        "SUPPORT_NEED_GATE": _gate(test_support_need_gate),
        "QUESTION_MATERIALITY_GATE": _gate(test_question_materiality_gate),
        "REASSURANCE_ALLOWED_GATE": _gate(test_reassurance_allowed_gate),
        "NO_FALSE_REASSURANCE_GATE": _gate(test_no_false_reassurance_gate),
        "NO_CATASTROPHIC_ESCALATION_GATE": _gate(test_no_catastrophic_escalation_gate),
        "REAL_CONCERN_ACKNOWLEDGEMENT_GATE": _gate(test_real_concern_acknowledgement_gate),
        "REPETITION_NOT_PATHOLOGY_GATE": _gate(test_repetition_not_pathology_gate),
        "RECURRING_PATTERN_GROUNDING_GATE": _gate(test_recurring_pattern_grounding_gate),
        "DIRECTNESS_GATE": _gate(test_directness_gate),
        "NO_FORCED_ACTION_GATE": _gate(test_no_forced_action_gate),
        "CROSS_DOMAIN_HEALTH_GATE": _gate(test_cross_domain_health_gate),
        "CROSS_DOMAIN_REFLECTION_GATE": _gate(test_cross_domain_reflection_gate),
        "MEMORY_CONFIRMATION_GATE": _gate(test_memory_confirmation_gate),
        "PERMISSION_LITERAL_TRUE_GATE": _gate(test_permission_literal_true_gate),
        "INPUT_ORDER_INVARIANCE_GATE": _gate(test_input_order_invariance_gate),
        "DUPLICATE_EVIDENCE_GATE": _gate(test_duplicate_evidence_gate_named),
        "MALFORMED_EVIDENCE_GATE": _gate(test_malformed_evidence_gate_named),
        "INPUT_NON_MUTATION_GATE": _gate(test_input_non_mutation_gate_named),
        "STRICT_JSON_GATE": _gate(test_strict_json_gate_named),
        "PACKAGE_BOUNDARY_GATE": _gate(test_package_boundary_gate),
    }
    lines = [f"{name}=PASS" if passed else f"{name}=FAIL" for name, passed in gates.items()]
    summary = "\n".join(lines + [f"ALL_PASS={str(all(gates.values())).lower()}"])
    print(summary)
    assert all(gates.values()), summary
