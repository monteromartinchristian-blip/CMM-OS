"""Phase 10.24 — Reflection Domain Audit V4 closure test suite.

This module permanently encodes the closure proofs and regression tests for:
- V4-I1: Diagnostic / restricted-inference polarity (disclaimers vs tentative diagnostic labels vs symptoms).
- V4-I2: Conclusion certainty polarity (negated certainty vs affirmative certainty vs mixed clauses).
- V4-M1: EOF diff hygiene and regression tests.
"""

from __future__ import annotations

import copy
import json
from datetime import datetime, timezone

from cmm.cognitive.enums import ReasoningRuleResultStatus
from cmm.cognitive.reasoning_rule_contracts import ReasoningRuleContext
from cmm.domains.memory_contracts import (
    DomainMemoryApprovalDecisionSnapshot,
    DomainMemoryApprovalRequestSnapshot,
    DomainMemoryCapability,
    DomainMemoryPermissionDecisionSnapshot,
    DomainMemoryReference,
    DomainMemoryReferenceInventory,
    DomainMemoryReferenceKind,
    DomainMemorySensitivityLevel,
    DomainMemoryTraceSnapshot,
    DomainMemoryViewSnapshot,
)
from cmm.domains.reflection.memory import (
    build_reflection_memory_binding,
    build_reflection_memory_proposal,
    build_reflection_memory_view,
    build_reflection_memory_view_request,
)
from cmm.domains.reflection.presentation import present_reflection_result
from cmm.domains.reflection.rules import (
    build_reflection_rules,
    classify_belief_evidence,
    classify_persistence,
    evaluate_ambivalence,
    evaluate_hypotheses,
    evaluate_open_questions,
    evaluate_persistence_basis,
    map_interests,
    no_forced_conclusion_policy,
)

NOW = datetime(2026, 8, 20, 22, 0, tzinfo=timezone.utc)


# ─────────────────────────────────────────────────────────────────────────────
# Helper for persistence valid memory chain
# ─────────────────────────────────────────────────────────────────────────────


def _build_valid_reflection_chain(proposal_id: str = "prop-v4-1", *, approved: bool = True):
    ref = DomainMemoryReference(
        reference_id=f"ref:{proposal_id}",
        kind=DomainMemoryReferenceKind.KNOWLEDGE_ITEM,
        canonical_id=f"item:{proposal_id}",
        domain_id="domain:reflection",
        applicable_domains=("domain:reflection",),
        evidence_ids=("ev:1",),
        resource_ids=("res:1",),
    )
    permission = DomainMemoryPermissionDecisionSnapshot(
        decision_id=f"perm:{proposal_id}",
        allowed=True,
        capabilities=(DomainMemoryCapability.PROPOSE,),
        source_domain_id="domain:reflection",
        target_domain_id="domain:reflection",
        sensitivity_levels=(DomainMemorySensitivityLevel.NORMAL,),
    )
    view_request = build_reflection_memory_view_request(
        request_id=f"req:{proposal_id}",
        trace_id=f"trace:{proposal_id}",
        requested_kinds=(DomainMemoryReferenceKind.KNOWLEDGE_ITEM,),
        candidates=(ref,),
        permission_decision_ids=(f"perm:{proposal_id}",),
    )
    proposal = build_reflection_memory_proposal(
        proposal_id=proposal_id,
        affected_reference_ids=(f"ref:{proposal_id}",),
    )
    temp_inventory = DomainMemoryReferenceInventory(
        references=(ref,),
        traces=(DomainMemoryTraceSnapshot(trace_id=f"trace:{proposal_id}", primary_domain="domain:reflection"),),
        permission_decisions=(permission,),
    )
    view = build_reflection_memory_view(request=view_request, inventory=temp_inventory)
    binding = build_reflection_memory_binding(
        proposal=proposal,
        view=view,
        trace_id=f"trace:{proposal_id}",
        permission_decision_ids=(f"perm:{proposal_id}",),
        approval_request_ids=(f"appr-req:{proposal_id}",),
        approval_decision_ids=(f"appr-dec:{proposal_id}",),
    )
    inventory = DomainMemoryReferenceInventory(
        references=(ref,),
        proposals=(proposal,),
        permission_decisions=(permission,),
        approval_requests=(
            DomainMemoryApprovalRequestSnapshot(
                request_id=f"appr-req:{proposal_id}", proposal_id=proposal_id
            ),
        ),
        approval_decisions=(
            DomainMemoryApprovalDecisionSnapshot(
                decision_id=f"appr-dec:{proposal_id}",
                request_id=f"appr-req:{proposal_id}",
                approved=approved,
            ),
        ),
        traces=(
            DomainMemoryTraceSnapshot(
                trace_id=f"trace:{proposal_id}", primary_domain="domain:reflection"
            ),
        ),
        views=(
            DomainMemoryViewSnapshot(
                view_id=view.view_id,
                request_id=view.request_id,
                primary_domain=view.primary_domain,
                trace_id=view.trace_id,
                view_digest=view.content_digest,
            ),
        ),
    )
    return binding, inventory


# ─────────────────────────────────────────────────────────────────────────────
# 1. V4-I1: DIAGNOSIS & RESTRICTED-INFERENCE POLARITY
# ─────────────────────────────────────────────────────────────────────────────


def test_v4_diagnosis_safe_disclaimers_allowed():
    """Diagnostic disclaimers and statements denying diagnostic authority must be SAFE."""
    disclaimers = (
        "Podría estar atravesando un periodo de tristeza; no hay base para diagnosticar",
        "No hay base para diagnosticar depresión; solo describo tristeza",
        "No puedo diagnosticar esto",
        "This is not a diagnosis; one possibility is situational sadness",
        "There is no basis to diagnose a disorder here",
        "Sin pretender diagnosticar, observo cansancio acumulado",
        "This does not imply a diagnosis; it is an exploration of feelings",
    )
    for stmt in disclaimers:
        res = evaluate_hypotheses(
            hypotheses=({"identity": "h-disc", "statement": stmt, "supporting_ids": ("s1",)},)
        )
        assert res["no_diagnosis"] is True, f"Expected disclaimer {stmt!r} to be safe (no_diagnosis=True)"
        hyp = res["hypotheses"][0]
        assert hyp["diagnostic"] is False
        assert hyp["restricted_inference"] is False
        assert hyp["statement"] == stmt


def test_v4_diagnosis_tentative_diagnostic_labels_restricted():
    """Tentative framing attached to diagnostic/clinical/personality labels must be RESTRICTED."""
    tentative_diagnoses = (
        "Podría ser bipolar",
        "Podría tener trastorno bipolar",
        "Puede que tenga depresión mayor",
        "Could have depression",
        "Might have major depression",
        "Could have an anxiety disorder",
        "They may have an avoidant attachment disorder",
        "Podría ser una persona narcisista",
        "Might be a narcissist",
        "Puede que padezca esquizofrenia",
    )
    for stmt in tentative_diagnoses:
        res = evaluate_hypotheses(
            hypotheses=({"identity": "h-tent-diag", "statement": stmt, "supporting_ids": ("s1",)},)
        )
        assert res["no_diagnosis"] is False, f"Expected tentative diagnosis {stmt!r} to be RESTRICTED"
        hyp = res["hypotheses"][0]
        assert hyp["diagnostic"] is True
        assert hyp["restricted_inference"] is True
        assert hyp["relative_strength"] is None
        pres = present_reflection_result(res)
        assert pres["hypotheses"][0]["statement"] == "[restricted: diagnostic/classifying claim withheld]"


def test_v4_diagnosis_contextual_symptom_hypotheses_safe():
    """Contextual, situational emotional symptom hypotheses must remain SAFE."""
    contextual_hypotheses = (
        "Podría estar sintiendo ansiedad en esta situación",
        "Puede que esta situación esté generando tristeza",
        "May be feeling anxious because of this event",
        "One possibility is temporary sadness after the loss",
        "Podría deberse al estrés laboral acumulado",
        "Una posibilidad es que aquí evite el conflicto",
        "One possibility is situational anxiety during public speaking",
    )
    for stmt in contextual_hypotheses:
        res = evaluate_hypotheses(
            hypotheses=({"identity": "h-ctx", "statement": stmt, "supporting_ids": ("s1",)},)
        )
        assert res["no_diagnosis"] is True, f"Expected contextual symptom {stmt!r} to be SAFE"
        hyp = res["hypotheses"][0]
        assert hyp["diagnostic"] is False
        assert hyp["restricted_inference"] is False


def test_v4_diagnosis_direct_assertions_restricted():
    """Direct assertive diagnoses and personality classifications must be RESTRICTED."""
    direct_assertions = (
        "Padece depresión mayor",
        "Tiene un trastorno de ansiedad",
        "You have major depression",
        "Eres bipolar",
        "Es una persona tóxica por naturaleza",
        "Su motivo real es manipular",
    )
    for stmt in direct_assertions:
        res = evaluate_hypotheses(
            hypotheses=({"identity": "h-dir", "statement": stmt, "supporting_ids": ("s1",)},)
        )
        assert res["no_diagnosis"] is False, f"Expected direct assertion {stmt!r} to be RESTRICTED"
        hyp = res["hypotheses"][0]
        assert hyp["diagnostic"] is True
        assert hyp["restricted_inference"] is True


def test_v4_diagnosis_mixed_disclaimer_plus_diagnosis_restricted():
    """A disclaimer does NOT sanitize a separate affirmative or tentative diagnosis in another clause."""
    mixed_statements = (
        "No puedo diagnosticar, pero eres bipolar",
        "No hay base para diagnosticar, aunque podría tener trastorno límite",
        "This is not a formal diagnosis, but you definitely have major depression",
        "Sin pretender diagnosticar, su motivo real es manipular a los demás",
    )
    for stmt in mixed_statements:
        res = evaluate_hypotheses(
            hypotheses=({"identity": "h-mix", "statement": stmt, "supporting_ids": ("s1",)},)
        )
        assert res["no_diagnosis"] is False, f"Expected mixed statement {stmt!r} to be RESTRICTED"
        hyp = res["hypotheses"][0]
        assert hyp["diagnostic"] is True


def test_v4_diagnosis_structural_markers_override_lexical_framing():
    """Explicit structural safety markers (diagnostic=True, classification_kind) always restrict."""
    res1 = evaluate_hypotheses(
        hypotheses=(
            {
                "identity": "h-s1",
                "statement": "No hay base para diagnosticar nada aquí",
                "supporting_ids": ("s1",),
                "diagnostic": True,
            },
        )
    )
    assert res1["no_diagnosis"] is False
    assert res1["hypotheses"][0]["diagnostic"] is True

    res2 = evaluate_hypotheses(
        hypotheses=(
            {
                "identity": "h-s2",
                "statement": "Una simple observación situacional",
                "supporting_ids": ("s1",),
                "classification_kind": "personality_classification",
            },
        )
    )
    assert res2["no_diagnosis"] is False
    assert res2["hypotheses"][0]["diagnostic"] is True


# ─────────────────────────────────────────────────────────────────────────────
# 2. V4-I2: CERTAINTY POLARITY & NO FORCED CONCLUSION
# ─────────────────────────────────────────────────────────────────────────────


def test_v4_certainty_negated_certainty_safe():
    """Explicitly negated certainty in conclusion fields must NOT trigger forced conclusion."""
    negated_conclusions = (
        "No tengo certeza de que fuera por rechazo",
        "No estoy seguro de que esa sea la causa",
        "No hay ninguna certeza sobre la causa",
        "No puedo estar seguro con estas pruebas",
        "I am not certain this was the cause",
        "I cannot be certain from the available evidence",
        "No es seguro que este factor fuera determinante",
        "There is no certainty regarding the real reason",
    )
    for text in negated_conclusions:
        res = {"unresolved": True, "conclusion": text}
        policy = no_forced_conclusion_policy(res)
        assert policy["forced_conclusion"] is False, f"Expected negated certainty {text!r} to be SAFE"
        assert policy["valid_unresolved_completion"] is True


def test_v4_certainty_affirmative_certainty_blocked():
    """Affirmative certainty in conclusion fields must trigger forced conclusion when unresolved."""
    affirmative_conclusions = (
        "Tengo certeza de que fue por rechazo",
        "Estoy seguro de que esa fue la causa",
        "Sin duda esa fue la causa",
        "No hay ninguna duda: esa es la causa",
        "There can be no doubt that this was the cause",
        "There is no doubt that this was the reason",
        "Definitivamente él actuó por celos",
        "La causa real es la falta de confianza",
    )
    for text in affirmative_conclusions:
        res = {"unresolved": True, "conclusion": text}
        policy = no_forced_conclusion_policy(res)
        assert policy["forced_conclusion"] is True, f"Expected affirmative certainty {text!r} to be BLOCKED"
        assert policy["valid_unresolved_completion"] is False


def test_v4_certainty_mixed_polarity_blocked():
    """Mixed polarity (uncertainty in one clause, affirmative certainty in another) must be BLOCKED."""
    mixed_conclusions = (
        "No estoy seguro, pero sin duda esa fue la causa",
        "No tengo certeza sobre todo, aunque definitivamente él lo hizo por celos",
        "I'm not certain about everything, but there can be no doubt this caused it",
        "No hay certeza absoluta de los detalles, pero la causa real es evidente",
    )
    for text in mixed_conclusions:
        res = {"unresolved": True, "conclusion": text}
        policy = no_forced_conclusion_policy(res)
        assert policy["forced_conclusion"] is True, f"Expected mixed certainty {text!r} to be BLOCKED"
        assert policy["valid_unresolved_completion"] is False


def test_v4_certainty_tentative_conclusions_safe():
    """Tentative, exploratory conclusion statements without certainty must remain SAFE."""
    tentative_conclusions = (
        "No puedo concluir una causa",
        "Puede ser una posibilidad, pero no estoy seguro",
        "I cannot be certain; the evidence is incomplete",
        "Una posibilidad a explorar es el contexto laboral",
    )
    for text in tentative_conclusions:
        res = {"unresolved": True, "conclusion": text}
        policy = no_forced_conclusion_policy(res)
        assert policy["forced_conclusion"] is False, f"Expected tentative conclusion {text!r} to be SAFE"
        assert policy["valid_unresolved_completion"] is True


def test_v4_certainty_quoted_evidence_irrelevant():
    """Certainty language occurring only in evidence/observation/quotes does NOT force conclusion."""
    cases = (
        {"unresolved": True, "evidence": ("El cliente dijo: 'sin duda alguna me voy'",)},
        {"unresolved": True, "observation": "Escribió: 'no hay duda de que es así'"},
        {"unresolved": True, "source": "Quote: 'there is no doubt I will be absent'"},
    )
    for case in cases:
        policy = no_forced_conclusion_policy(case)
        assert policy["forced_conclusion"] is False
        assert policy["valid_unresolved_completion"] is True


def test_v4_certainty_structural_flags_enforce_blocked():
    """Structural certainty/adoption flags enforce forced conclusion when unresolved."""
    for field, val in (
        ("conclusion_status", "final"),
        ("conclusion_status", "certain"),
        ("certainty_state", "absolute"),
        ("fact", True),
        ("winner_selected", True),
        ("conclusion_adopted", True),
        ("decision_adopted", True),
    ):
        res = {"unresolved": True, field: val, "conclusion": "No tengo certeza de nada"}
        policy = no_forced_conclusion_policy(res)
        assert policy["forced_conclusion"] is True, f"Expected {field}={val} to block despite negated conclusion text"
        assert policy["valid_unresolved_completion"] is False


def test_v4_no_forced_conclusion_rule_parity():
    """NoForcedConclusionRule evaluates correctly for negated vs affirmative certainty."""
    # Negated certainty -> NO finding of forced conclusion
    context_safe = ReasoningRuleContext(
        reasoning_id="rr-v4-safe",
        timestamp=NOW,
        active_domains=("domain:reflection",),
        primary_domain="domain:reflection",
        metadata={"result": {"unresolved": True, "conclusion": "No tengo certeza de la causa"}},
    )
    rule = next(r for r in build_reflection_rules() if r.definition.id == "reflection.no_forced_conclusion")
    res_safe = rule.evaluate(context_safe)
    assert res_safe.status is ReasoningRuleResultStatus.APPLIED
    assert res_safe.findings[0].metadata["forced_conclusion"] is False

    # Affirmative certainty -> finding of forced conclusion
    context_forced = ReasoningRuleContext(
        reasoning_id="rr-v4-forced",
        timestamp=NOW,
        active_domains=("domain:reflection",),
        primary_domain="domain:reflection",
        metadata={"result": {"unresolved": True, "conclusion": "Tengo certeza de que fue por rechazo"}},
    )
    res_forced = rule.evaluate(context_forced)
    assert res_forced.status is ReasoningRuleResultStatus.APPLIED
    assert res_forced.findings[0].metadata["forced_conclusion"] is True


# ─────────────────────────────────────────────────────────────────────────────
# 3. REGRESSION & ROBUSTNESS
# ─────────────────────────────────────────────────────────────────────────────


def test_v4_strict_json_all_outputs():
    """All public helper and rule outputs must be strictly JSON-serializable."""
    binding, inventory = _build_valid_reflection_chain("prop-json-v4", approved=True)

    outputs = (
        classify_persistence(
            {"proposal_id": "prop-json-v4", "pattern": "x", "sources": ("s1", "s2")},
            confirmation_binding=binding,
            confirmation_inventory=inventory,
        ),
        evaluate_hypotheses(
            hypotheses=({"identity": "h1", "statement": "No puedo diagnosticar esto", "supporting_ids": ("s1",)},)
        ),
        no_forced_conclusion_policy({"unresolved": True, "conclusion": "No tengo certeza sobre la causa"}),
        evaluate_ambivalence(records=()),
        evaluate_open_questions(questions=()),
        evaluate_persistence_basis({"pattern": "x", "sources": ("s1",)}),
        map_interests(records=()),
        classify_belief_evidence(records=()),
    )
    for out in outputs:
        encoded = json.dumps(out, allow_nan=False)
        assert isinstance(encoded, str)


def test_v4_input_non_mutation():
    """Input structures must not be mutated by helper execution."""
    raw_hyp = [
        {"identity": "h1", "statement": "No hay base para diagnosticar depresión", "supporting_ids": ["s1"]}
    ]
    hyp_copy = copy.deepcopy(raw_hyp)
    evaluate_hypotheses(hypotheses=raw_hyp)
    assert raw_hyp == hyp_copy

    raw_res = {"unresolved": True, "conclusion": "No tengo certeza de la causa"}
    res_copy = copy.deepcopy(raw_res)
    no_forced_conclusion_policy(raw_res)
    assert raw_res == res_copy
