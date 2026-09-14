"""Phase 10.24 — Reflection Domain Audit V5 Compositional Closure test suite.

This module permanently encodes the closure proofs and regression tests for:
- V5-I1: Compositional diagnostic clause classification and normalization invariance.
- V5-I2: Compositional certainty stance classification, normalization invariance, and mixed clause resolution.
"""

from __future__ import annotations

import copy
import json
from datetime import datetime, timezone

import pytest

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

NOW = datetime(2026, 8, 20, 23, 0, tzinfo=timezone.utc)


def _build_valid_reflection_chain(
    proposal_id: str = "prop-v5-1", *, approved: bool = True
):
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
        traces=(
            DomainMemoryTraceSnapshot(
                trace_id=f"trace:{proposal_id}", primary_domain="domain:reflection"
            ),
        ),
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
# 1. V5-I1: DIAGNOSTIC NORMALIZATION & COMPOSITIONAL RESTRICTION
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "stmt",
    [
        "Su estilo de apego es patológico",
        "SU ESTILO DE APEGO ES PATOLÓGICO",
        "su estilo de apego es patologico.",
        "  su estilo de apego es patológico!  ",
        "Tu patrón de apego podría ser evitativo",
        "tu patron de apego podria ser evitativo",
        "Your attachment pattern may be disordered",
        "YOUR ATTACHMENT PATTERN MAY BE DISORDERED.",
        "Their attachment style is pathological",
        "Tal vez padezca un episodio depresivo mayor",
        "They might have clinical depression",
    ],
)
def test_v5_diagnostic_compositional_and_normalization_restricted(stmt: str):
    """Compositional attachment/diagnostic statements are restricted under all normalization variants."""
    res = evaluate_hypotheses(
        hypotheses=({"identity": "h1", "statement": stmt, "supporting_ids": ("s1",)},)
    )
    assert res["no_diagnosis"] is False, f"Expected {stmt!r} to be RESTRICTED"
    hyp = res["hypotheses"][0]
    assert hyp["diagnostic"] is True
    assert hyp["restricted_inference"] is True
    pres = present_reflection_result(res)
    assert (
        pres["hypotheses"][0]["statement"]
        == "[restricted: diagnostic/classifying claim withheld]"
    )


@pytest.mark.parametrize(
    "stmt",
    [
        "No corresponde diagnosticar aquí; solo describo malestar pasajero",
        "No hay base para diagnosticar con estos datos.",
        "NO CORRESPONDE DIAGNOSTICAR AQUÍ",
        "Sin pretender diagnosticar, observo cansancio",
        "Podría estar sintiendo ansiedad en esta situación",
        "PODRÍA ESTAR SINTIENDO ANSIEDAD EN ESTA SITUACIÓN",
        "Quizá esté experimentando nervios por este episodio concreto",
        "May be feeling anxious because of this event",
        "One possibility is temporary sadness after the loss",
    ],
)
def test_v5_diagnostic_disclaimers_and_contextual_safe(stmt: str):
    """Diagnostic disclaimers and situational symptom hypotheses are safe under all normalization variants."""
    res = evaluate_hypotheses(
        hypotheses=({"identity": "h1", "statement": stmt, "supporting_ids": ("s1",)},)
    )
    assert res["no_diagnosis"] is True, f"Expected {stmt!r} to be SAFE"
    hyp = res["hypotheses"][0]
    assert hyp["diagnostic"] is False
    assert hyp["statement"] == stmt


@pytest.mark.parametrize(
    "stmt",
    [
        "No puedo diagnosticar, pero tienes depresión mayor",
        "This is not a diagnosis, but you have bipolar disorder",
        "No corresponde diagnosticar aquí, aunque su estilo de apego es patológico",
        "Sin pretender diagnosticar; su motivo real es manipular",
    ],
)
def test_v5_diagnostic_mixed_clauses_restricted(stmt: str):
    """A disclaimer in one clause does NOT sanitize an affirmative diagnostic label in another clause."""
    res = evaluate_hypotheses(
        hypotheses=({"identity": "h1", "statement": stmt, "supporting_ids": ("s1",)},)
    )
    assert res["no_diagnosis"] is False, (
        f"Expected mixed statement {stmt!r} to be RESTRICTED"
    )
    assert res["hypotheses"][0]["diagnostic"] is True


# ─────────────────────────────────────────────────────────────────────────────
# 2. V5-I2: CERTAINTY STANCE & NORMALIZATION INVARIANCE
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "text",
    [
        "Carezco de certeza suficiente para atribuirlo al rechazo",
        "CAREZCO DE CERTEZA SUFICIENTE PARA ATRIBUIRLO AL RECHAZO",
        "carezco de certeza suficiente para atribuirlo al rechazo.",
        "No tengo certeza de que esa sea la causa",
        "No estoy seguro de que esa sea la causa",
        "No hay ninguna certeza sobre la causa",
        "I am unsure whether that was really the cause",
        "I cannot be certain from the evidence",
        "There is insufficient certainty to conclude",
    ],
)
def test_v5_certainty_negated_and_normalization_safe(text: str):
    """Explicitly negated certainty and lack of certainty remain safe under all normalization forms."""
    res = {"unresolved": True, "conclusion": text}
    policy = no_forced_conclusion_policy(res)
    assert policy["forced_conclusion"] is False, (
        f"Expected {text!r} to be SAFE (forced_conclusion=False)"
    )
    assert policy["valid_unresolved_completion"] is True


@pytest.mark.parametrize(
    "text",
    [
        "Sé con total seguridad que esa fue la causa",
        "SÉ CON TOTAL SEGURIDAD QUE ESA FUE LA CAUSA",
        "Se con total seguridad que esa fue la causa.",
        "Tengo certeza absoluta de que esa fue la causa",
        "Estoy completamente convencido de que esa fue la causa",
        "I know for certain that this explains everything",
        "I KNOW FOR CERTAIN THAT THIS EXPLAINS EVERYTHING",
        "I am completely convinced this was the cause",
        "There can be no doubt that this was the cause",
        "No cabe duda de que esa fue la causa",
        "Sin duda alguna esa fue la razón",
    ],
)
def test_v5_certainty_affirmed_and_normalization_forced(text: str):
    """Affirmative certainty is flagged as forced conclusion under all normalization forms."""
    res = {"unresolved": True, "conclusion": text}
    policy = no_forced_conclusion_policy(res)
    assert policy["forced_conclusion"] is True, (
        f"Expected {text!r} to be FORCED (forced_conclusion=True)"
    )
    assert policy["valid_unresolved_completion"] is False


@pytest.mark.parametrize(
    "text",
    [
        "No puedo asegurar todos los detalles, pero sé con total seguridad que él actuó por celos",
        "No tengo certeza sobre todo, aunque estoy completamente convencido de que fue por rechazo",
        "I'm unsure about the details, but I know for certain this caused it",
        "Carezco de certeza en parte, pero no hay duda de que esa fue la causa",
    ],
)
def test_v5_certainty_mixed_clauses_forced(text: str):
    """A contrastive clause with affirmative certainty forces conclusion even when preceded by uncertainty."""
    res = {"unresolved": True, "conclusion": text}
    policy = no_forced_conclusion_policy(res)
    assert policy["forced_conclusion"] is True, (
        f"Expected mixed certainty {text!r} to be FORCED"
    )
    assert policy["valid_unresolved_completion"] is False


def test_v5_certainty_quoted_evidence_excluded():
    """Certainty language present only in quoted evidence or observations does NOT force conclusion."""
    res = {
        "unresolved": True,
        "evidence": ("El testigo afirmó: 'sé con total seguridad que ocurrió así'",),
        "conclusion": "Carezco de certeza suficiente para confirmar la versión",
    }
    policy = no_forced_conclusion_policy(res)
    assert policy["forced_conclusion"] is False
    assert policy["valid_unresolved_completion"] is True


def test_v5_certainty_structural_override():
    """Structural certainty flags override safe conclusion text."""
    res = {
        "unresolved": True,
        "certainty_state": "certain",
        "conclusion": "Carezco de certeza suficiente",
    }
    policy = no_forced_conclusion_policy(res)
    assert policy["forced_conclusion"] is True
    assert policy["valid_unresolved_completion"] is False


def test_v5_no_forced_conclusion_rule_parity():
    """NoForcedConclusionRule evaluates negated vs affirmed certainty correctly."""
    context_safe = ReasoningRuleContext(
        reasoning_id="rr-v5-safe",
        timestamp=NOW,
        active_domains=("domain:reflection",),
        primary_domain="domain:reflection",
        metadata={
            "result": {
                "unresolved": True,
                "conclusion": "Carezco de certeza suficiente",
            }
        },
    )
    rule = next(
        r
        for r in build_reflection_rules()
        if r.definition.id == "reflection.no_forced_conclusion"
    )
    res_safe = rule.evaluate(context_safe)
    assert res_safe.status is ReasoningRuleResultStatus.APPLIED
    assert res_safe.findings[0].metadata["forced_conclusion"] is False

    context_forced = ReasoningRuleContext(
        reasoning_id="rr-v5-forced",
        timestamp=NOW,
        active_domains=("domain:reflection",),
        primary_domain="domain:reflection",
        metadata={
            "result": {
                "unresolved": True,
                "conclusion": "Sé con total seguridad que ocurrió",
            }
        },
    )
    res_forced = rule.evaluate(context_forced)
    assert res_forced.status is ReasoningRuleResultStatus.APPLIED
    assert res_forced.findings[0].metadata["forced_conclusion"] is True


# ─────────────────────────────────────────────────────────────────────────────
# 3. REGRESSION & ROBUSTNESS
# ─────────────────────────────────────────────────────────────────────────────


def test_v5_strict_json_all_outputs():
    """All public helper and rule outputs must be strictly JSON-serializable."""
    binding, inventory = _build_valid_reflection_chain("prop-json-v5", approved=True)

    outputs = (
        classify_persistence(
            {"proposal_id": "prop-json-v5", "pattern": "x", "sources": ("s1", "s2")},
            confirmation_binding=binding,
            confirmation_inventory=inventory,
        ),
        evaluate_hypotheses(
            hypotheses=(
                {
                    "identity": "h1",
                    "statement": "No corresponde diagnosticar aquí",
                    "supporting_ids": ("s1",),
                },
            )
        ),
        no_forced_conclusion_policy(
            {"unresolved": True, "conclusion": "Carezco de certeza suficiente"}
        ),
        evaluate_ambivalence(records=()),
        evaluate_open_questions(questions=()),
        evaluate_persistence_basis({"pattern": "x", "sources": ("s1",)}),
        map_interests(records=()),
        classify_belief_evidence(records=()),
    )
    for out in outputs:
        encoded = json.dumps(out, allow_nan=False)
        assert isinstance(encoded, str)


def test_v5_input_non_mutation():
    """Input structures must not be mutated by helper execution."""
    raw_hyp = [
        {
            "identity": "h1",
            "statement": "Su estilo de apego es patológico",
            "supporting_ids": ["s1"],
        }
    ]
    hyp_copy = copy.deepcopy(raw_hyp)
    evaluate_hypotheses(hypotheses=raw_hyp)
    assert raw_hyp == hyp_copy

    raw_res = {"unresolved": True, "conclusion": "Sé con total seguridad que ocurrió"}
    res_copy = copy.deepcopy(raw_res)
    no_forced_conclusion_policy(raw_res)
    assert raw_res == res_copy
