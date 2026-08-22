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


# ═════════════════════════════════════════════════════════════════════════════
# F5 — Make AT-DP-025 genuinely end-to-end (RB-003)
# ═════════════════════════════════════════════════════════════════════════════


def test_f5_connected_dp025_standard_resolver_and_workflow():
    """AT-DP-025 uses standard resolver scoring, real workflow execution, exact REASSURANCE_PARTIAL, and preserved concern."""
    from datetime import datetime, timezone
    from cmm.domains.concerns.definition import build_concerns_domain_definition, CONCERNS_DOMAIN_ID
    from cmm.domains.general.definition import build_general_domain_definition
    from cmm.domains.relationships.definition import build_relationships_domain_definition
    from cmm.domains.concerns.workflows import build_concerns_workflow_definitions
    from cmm.domains.concerns.operations import (
        build_concerns_operation_definitions,
        understand_concern_result,
        infer_support_need_result,
        map_lived_experience_result,
        identify_open_questions_result,
        evaluate_reassurance_result,
    )
    from cmm.domains.identifiers import DomainId
    from cmm.domains.registry import DomainRegistry
    from cmm.domains.resolution_builder import DomainResolutionContextBuilder
    from cmm.domains.resolution_contracts import (
        DomainResolutionKnowledgeItem,
        DomainResolutionResource,
        DomainResolutionSignal,
    )
    from cmm.domains.resolver import DefaultDomainResolver
    from cmm.domains.workflow_execution import DomainWorkflowExecutor
    from cmm.domains.workflow_contracts import DomainWorkflowContext
    from cmm.workflows.engine import NodeExecution
    from cmm.workflows.enums import WorkflowRunStatus

    now = datetime(2026, 8, 23, 12, 0, tzinfo=timezone.utc)

    # 1. Standard resolver with default scoring policy
    registry = DomainRegistry()
    registry.register(build_general_domain_definition())
    registry.register(build_concerns_domain_definition())
    registry.register(build_relationships_domain_definition())
    registry.enable("domain:general")
    registry.enable("domain:concerns")
    registry.enable("domain:relationships")

    resolver = DefaultDomainResolver(
        fallback_domain=DomainId.from_str("domain:general"),
        id_factory=lambda: "res-001",
        clock=lambda: now,
    )
    assert resolver.scoring_policy.supporting_margin == 15.0

    builder = DomainResolutionContextBuilder(
        id_factory=lambda: "ctx-1", clock=lambda: now
    )
    context = builder.build(
        registry_snapshot=registry.snapshot(),
        user_input="My partner didn't reply to my message and I'm afraid they are losing interest",
        authorized_domains=("domain:concerns", "domain:relationships", "domain:general"),
        resources=(
            DomainResolutionResource(
                id="res:msg:1",
                resource_type="message",
                source="domain:relationships",
                domain_ids=("domain:concerns", "domain:relationships"),
            ),
        ),
        knowledge_items=(
            DomainResolutionKnowledgeItem(
                id="kn:msg:1",
                knowledge_type="observed_behavior",
                source="domain:relationships",
                domain_ids=("domain:relationships",),
            ),
        ),
        signals=(
            DomainResolutionSignal(
                kind="intent",
                source="user",
                value="concern_support",
                domain_ids=("domain:concerns",),
            ),
            DomainResolutionSignal(
                kind="objective",
                source="user",
                value="reality_check",
                domain_ids=("domain:concerns",),
            ),
            DomainResolutionSignal(
                kind="entity",
                source="user",
                value="partner",
                domain_ids=("domain:relationships",),
            ),
        ),
    )
    resolution = resolver.resolve(context)
    assert resolution.status.value == "resolved"
    assert str(resolution.primary_domain) == CONCERNS_DOMAIN_ID
    assert "domain:relationships" in {str(d) for d in resolution.supporting_domains}

    # 2. Real supporting projection consumed by Concerns workflow
    relationships_projection = {
        "domain_id": "domain:relationships",
        "domain_result_id": "rel-res-001",
        "authorized": True,
        "relationship_type": "romantic_partner",
        "observed_behavior": "no reply to message sent yesterday",
        "motive_unknown": True,
    }

    # 3. Real workflow execution
    all_wfs = build_concerns_workflow_definitions()
    all_ops = build_concerns_operation_definitions()
    open_concern_wf = next(w for w in all_wfs if w.workflow_id == "concerns.open_concern_conversation")

    def adapter(node, run):
        if node.operation_id == "concerns.understand_concern":
            res = understand_concern_result(
                material={
                    "situation": "partner silent after message",
                    "what_matters": "whether they are losing interest",
                    "explicit_request": "What do you think?",
                    "specialized_domain_result": relationships_projection,
                }
            )
            return NodeExecution.complete(res, operation_result=res)
        elif node.operation_id == "concerns.infer_support_need":
            res = infer_support_need_result(explicit_request="What do you think?")
            return NodeExecution.complete(res, operation_result=res)
        elif node.operation_id == "concerns.map_lived_experience":
            res = map_lived_experience_result(
                material={
                    "emotion_statements": ("anxious",),
                    "interpretation_statements": ("they lost interest",),
                }
            )
            return NodeExecution.complete(res, operation_result=res)
        elif node.operation_id == "concerns.identify_open_questions":
            res = identify_open_questions_result(questions=())
            return NodeExecution.complete(res, operation_result=res)
        elif node.node_type.value == "validate":
            return NodeExecution.complete({"valid": True})
        return NodeExecution.complete({"ok": True})

    executor = DomainWorkflowExecutor(
        id_factory=lambda: "wf-run-1",
        clock=lambda: now,
        operation_adapter=adapter,
        operation_definitions={op.operation_id: op for op in all_ops},
        workflow_definitions={wf.workflow_id: wf for wf in all_wfs},
    )
    wf_context = DomainWorkflowContext(
        primary_domain_id=CONCERNS_DOMAIN_ID,
        supporting_domain_ids=("domain:relationships",),
        available_operations=frozenset(op.operation_id for op in all_ops),
        authorized_domain_ids=frozenset(["domain:concerns", "domain:relationships"]),
    )
    wf_run = executor.execute(
        open_concern_wf,
        wf_context,
        inputs={"concern": "silence", "specialized_domain_result": relationships_projection},
    )
    assert wf_run.common_run.status is WorkflowRunStatus.COMPLETED

    # 4. Exact reassurance and preserved concern
    reassurance = evaluate_reassurance_result(
        target_claim="they are losing interest",
        evidence=(
            {
                "identity": "e1",
                "claim": "message was delivered",
                "stance": "opposes_target",
                "grounding": "res:msg:1",
                "source_quality": "grounded",
                "temporal_relevance": "current",
            },
        ),
        counterevidence=(
            {
                "identity": "e2",
                "claim": "silence means they lost interest",
                "stance": "supports_target",
                "grounding": "res:msg:1",
                "source_quality": "unverified_hearsay",
                "temporal_relevance": "current",
            },
        ),
        uncertainty=({"identity": "u1", "unknown": "intent"},),
        material_concerns=("silence means they lost interest",),
        specialized_domain_result=relationships_projection,
    )
    assert reassurance["assessment"] == "REASSURANCE_PARTIAL"
    assert reassurance["material_concern"] is True
    assert "silence means they lost interest" in reassurance["acknowledged_concerns"]
    assert reassurance["concern_erased"] is False


# ═════════════════════════════════════════════════════════════════════════════
# F6 — Finish presentation semantic preservation (RI-005)
# ═════════════════════════════════════════════════════════════════════════════


def test_f6_presentation_preserves_flat_risk_and_epistemic_state():
    """Flat risk helper output is preserved in presentation; CONCERN_SUPPORTED is not known_fact without facts."""
    from cmm.domains.concerns.operations import evaluate_risk_result
    from cmm.domains.concerns.presentation import (
        present_concerns_result,
        PRESENTATION_STATE_KNOWN_FACT,
        PRESENTATION_STATE_INTERPRETATION,
    )

    # 1. Flat risk helper output preserved
    rec = {
        "identity": "r1",
        "claim": "user missed medication",
        "stance": "supports_target",
        "grounding": "med:1",
        "source_quality": "grounded",
        "temporal_relevance": "current",
    }
    risk_res = evaluate_risk_result(severity="low", evidence=(rec,))
    assert risk_res["risk_level"] == "low"
    presented_risk = present_concerns_result(risk_res)
    assert presented_risk["risk"]["risk_level"] == "low"
    assert presented_risk["proportional_action"]["risk"]["risk_level"] == "low"

    # 2. CONCERN_SUPPORTED is an epistemic assessment, NOT known_fact without facts
    concern_res = {
        "assessment": "CONCERN_SUPPORTED",
        "interpretations": ({"statement": "they are ignoring me"},),
        "facts": (),
    }
    presented_concern = present_concerns_result(concern_res)
    assert presented_concern["presentation_state"] != PRESENTATION_STATE_KNOWN_FACT
    assert presented_concern["presentation_state"] == PRESENTATION_STATE_INTERPRETATION


def test_f6_presentation_parity_across_all_13_operations():
    """All 13 canonical operations in Concerns Domain project cleanly through presentation without losing semantics."""
    from cmm.domains.concerns.operations import (
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
    from cmm.domains.concerns.presentation import present_concerns_result

    # 1. understand_concern
    op1 = understand_concern_result(material={"situation": "late reply", "what_matters": "friendship"})
    p1 = present_concerns_result(op1)
    assert "section_order" in p1

    # 2. infer_support_need
    op2 = infer_support_need_result(explicit_request="Tell me what you think.")
    p2 = present_concerns_result(op2)
    assert p2["support_need"] == op2["support_need"]

    # 3. map_lived_experience
    op3 = map_lived_experience_result(material={"emotion_statements": ("worried",)})
    p3 = present_concerns_result(op3)
    assert len(p3["experiences"]) == 1

    # 4. separate_reality_interpretation
    op4 = separate_reality_interpretation_result(statements=({"statement": "they are angry", "level": "interpretation"},))
    p4 = present_concerns_result(op4)
    assert len(p4["interpretations"]) == 1

    # 5. explore_hypotheses
    op5 = explore_hypotheses_result(hypotheses=({"statement": "they were busy"},))
    p5 = present_concerns_result(op5)
    assert len(p5["hypotheses"]) == 1

    # 6. calibrate_uncertainty
    op6 = calibrate_uncertainty_result(records=({"statement": "might rain"},))
    p6 = present_concerns_result(op6)
    assert "section_order" in p6

    # 7. evaluate_reassurance
    op7 = evaluate_reassurance_result(target_claim="they are safe", evidence=(), uncertainty=({"unknown": "whereabouts"},))
    p7 = present_concerns_result(op7)
    assert p7["reassurance_assessment"] == op7["assessment"]

    # 8. evaluate_risk
    op8 = evaluate_risk_result(severity="low")
    p8 = present_concerns_result(op8)
    assert p8["risk"]["risk_level"] == op8["risk_level"]

    # 9. identify_open_questions
    op9 = identify_open_questions_result(questions=({"question": "When did you last speak?", "changes": ("meaning",)},))
    p9 = present_concerns_result(op9)
    assert "section_order" in p9

    # 10. explore_options
    op10 = explore_options_result(options=({"option_id": "opt1", "expected_benefit": "clarity"},))
    p10 = present_concerns_result(op10)
    assert len(p10["options"]) == 1

    # 11. prepare_next_step
    op11 = prepare_next_step_result(desired_outcome="clarity", options=("opt1",), user_request="What to do?")
    p11 = present_concerns_result(op11)
    assert p11["next_step"] is not None

    # 12. review_recurring_concern
    op12 = review_recurring_concern_result(current={"topic": "t1"}, previous=())
    p12 = present_concerns_result(op12)
    assert "section_order" in p12

    # 13. prepare_professional_discussion
    op13 = prepare_professional_discussion_result(concern_summary="health symptoms", key_facts=("bp 120/80",))
    p13 = present_concerns_result(op13)
    assert "section_order" in p13
