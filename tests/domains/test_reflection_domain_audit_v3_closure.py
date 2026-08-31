"""Phase 10.24 — Reflection Domain Audit V3 remediation closure suite.

This file permanently encodes the adversarial reproductions and closure proofs
for all findings from ``the historical Phase 10.24 independent Audit V3 findings``:

- V3-I1 — Shared VALIDATE reads declared dependency outputs only (not all outputs).
- V3-I2 — Persistence requires validated shared binding + reference inventory chain.
- V3-I3 — Structural-first diagnosis / restricted-inference safety with direct classification shapes.
- V3-I4 — Structural, conclusion-scoped NoForcedConclusion policy (no whole-tree scanning).
- V3-M1 — Ruff import ordering and hygiene.

Every assertion below is a real executable proof; no gate string is hard-coded
without a live assertion behind it.
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
    validate_reflection_memory_binding,
)
from cmm.domains.reflection.presentation import (
    present_reflection_result,
)
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
from cmm.workflows.contracts import WorkflowDefinition, WorkflowNode
from cmm.workflows.engine import NodeExecution, WorkflowEngine
from cmm.workflows.enums import WorkflowRunStatus

NOW = datetime(2026, 8, 20, 20, 0, tzinfo=timezone.utc)


# ─────────────────────────────────────────────────────────────────────────────
# Memory / Persistence fixture builder
# ─────────────────────────────────────────────────────────────────────────────


def _build_valid_reflection_chain(
    proposal_id: str = "prop-v3-1",
    *,
    domain_id: str = "domain:reflection",
    approved: bool = True,
    wrong_request_prop_id: str | None = None,
    wrong_decision_req_id: str | None = None,
):
    ref = DomainMemoryReference(
        reference_id=f"ref:{proposal_id}",
        kind=DomainMemoryReferenceKind.KNOWLEDGE_ITEM,
        canonical_id=f"item:{proposal_id}",
        domain_id=domain_id,
        applicable_domains=(domain_id,),
        evidence_ids=("ev:1",),
        resource_ids=("res:1",),
    )
    permission = DomainMemoryPermissionDecisionSnapshot(
        decision_id=f"perm:{proposal_id}",
        allowed=True,
        capabilities=(DomainMemoryCapability.PROPOSE,),
        source_domain_id=domain_id,
        target_domain_id=domain_id,
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
                trace_id=f"trace:{proposal_id}", primary_domain=domain_id
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

    req_prop_id = wrong_request_prop_id if wrong_request_prop_id else proposal_id
    dec_req_id = (
        wrong_decision_req_id if wrong_decision_req_id else f"appr-req:{proposal_id}"
    )

    requests = (
        DomainMemoryApprovalRequestSnapshot(
            request_id=f"appr-req:{proposal_id}", proposal_id=req_prop_id
        ),
    )
    decisions = (
        DomainMemoryApprovalDecisionSnapshot(
            decision_id=f"appr-dec:{proposal_id}",
            request_id=dec_req_id,
            approved=approved,
        ),
    )

    inventory = DomainMemoryReferenceInventory(
        references=(ref,),
        proposals=(proposal,),
        permission_decisions=(permission,),
        approval_requests=requests,
        approval_decisions=decisions,
        traces=(
            DomainMemoryTraceSnapshot(
                trace_id=f"trace:{proposal_id}", primary_domain=domain_id
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
# 1. V3-I1: VALIDATE DEPENDENCY SCOPE GATE
# ─────────────────────────────────────────────────────────────────────────────


def _make_validate_flow(nodes, metadata=None):
    return WorkflowDefinition(
        "v3.validate.flow",
        "1.0.0",
        "V3ValidateFlow",
        nodes=tuple(nodes),
        metadata=metadata or {},
    )


def _run_validate_nodes(nodes, node_outputs, metadata=None):
    def adapter(node, run):
        return NodeExecution.complete(node_outputs.get(node.node_id, {"ok": True}))

    engine = WorkflowEngine(
        _make_validate_flow(nodes, metadata),
        id_factory=lambda: "run-v3-val",
        clock=lambda: datetime.now(timezone.utc),
        node_adapter=adapter,
    )
    return engine.start({})


def test_v3_validate_unrelated_node_cannot_satisfy_missing_dependency():
    """An unrelated completed node with safe=True must NOT satisfy a gate."""
    nodes = (
        WorkflowNode(
            "unrelated",
            "execute_operation",
            "Unrelated",
            operation_id="op.u",
            operation_version="1.0.0",
        ),
        WorkflowNode(
            "producer",
            "execute_operation",
            "Producer",
            operation_id="op.p",
            operation_version="1.0.0",
        ),
        WorkflowNode(
            "validate",
            "validate",
            "Validate",
            dependencies=("producer",),
            wait_condition={"safe": True},
        ),
        WorkflowNode("finish", "complete", "Finish", dependencies=("validate",)),
    )
    result = _run_validate_nodes(
        nodes,
        {
            "unrelated": {"safe": True},
            "producer": {"other": "value"},
        },
    )
    assert result.run.status is not WorkflowRunStatus.COMPLETED
    assert result.run.error_code == "validate.condition_unknown"


def test_v3_validate_unrelated_node_cannot_manufacture_conflict():
    """An unrelated completed node with safe=False must NOT conflict with declared dependency."""
    nodes = (
        WorkflowNode(
            "unrelated",
            "execute_operation",
            "Unrelated",
            operation_id="op.u",
            operation_version="1.0.0",
        ),
        WorkflowNode(
            "producer",
            "execute_operation",
            "Producer",
            operation_id="op.p",
            operation_version="1.0.0",
        ),
        WorkflowNode(
            "validate",
            "validate",
            "Validate",
            dependencies=("producer",),
            wait_condition={"safe": True},
        ),
        WorkflowNode("finish", "complete", "Finish", dependencies=("validate",)),
    )
    result = _run_validate_nodes(
        nodes,
        {
            "unrelated": {"safe": False},
            "producer": {"safe": True},
        },
    )
    assert result.run.status is WorkflowRunStatus.COMPLETED


def test_v3_validate_declared_dependency_conflict_fails_closed():
    """Two declared dependencies disagreeing on safe must fail closed."""
    nodes = (
        WorkflowNode(
            "producer_a",
            "execute_operation",
            "ProducerA",
            operation_id="op.a",
            operation_version="1.0.0",
        ),
        WorkflowNode(
            "producer_z",
            "execute_operation",
            "ProducerZ",
            operation_id="op.z",
            operation_version="1.0.0",
        ),
        WorkflowNode(
            "validate",
            "validate",
            "Validate",
            dependencies=("producer_a", "producer_z"),
            wait_condition={"safe": True},
        ),
        WorkflowNode("finish", "complete", "Finish", dependencies=("validate",)),
    )
    result = _run_validate_nodes(
        nodes,
        {
            "producer_a": {"safe": False},
            "producer_z": {"safe": True},
        },
    )
    assert result.run.status is not WorkflowRunStatus.COMPLETED
    assert result.run.error_code == "validate.condition_conflict"


def test_v3_validate_declared_dependencies_agree_passes():
    """Two declared dependencies agreeing on safe=True pass the gate."""
    nodes = (
        WorkflowNode(
            "producer_a",
            "execute_operation",
            "ProducerA",
            operation_id="op.a",
            operation_version="1.0.0",
        ),
        WorkflowNode(
            "producer_z",
            "execute_operation",
            "ProducerZ",
            operation_id="op.z",
            operation_version="1.0.0",
        ),
        WorkflowNode(
            "validate",
            "validate",
            "Validate",
            dependencies=("producer_a", "producer_z"),
            wait_condition={"safe": True},
        ),
        WorkflowNode("finish", "complete", "Finish", dependencies=("validate",)),
    )
    result = _run_validate_nodes(
        nodes,
        {
            "producer_a": {"safe": True},
            "producer_z": {"safe": True},
        },
    )
    assert result.run.status is WorkflowRunStatus.COMPLETED


def test_v3_validate_strict_boolean_semantics():
    """Numeric 1, 0, string 'true', 'false' are denied for boolean expectations."""
    nodes = (
        WorkflowNode(
            "producer",
            "execute_operation",
            "Producer",
            operation_id="op.p",
            operation_version="1.0.0",
        ),
        WorkflowNode(
            "validate",
            "validate",
            "Validate",
            dependencies=("producer",),
            wait_condition={"flag": True},
        ),
        WorkflowNode("finish", "complete", "Finish", dependencies=("validate",)),
    )
    for bad_value in (1, "true", "True", [True], {"flag": True}):
        res = _run_validate_nodes(nodes, {"producer": {"flag": bad_value}})
        assert res.run.status is not WorkflowRunStatus.COMPLETED

    res_good = _run_validate_nodes(nodes, {"producer": {"flag": True}})
    assert res_good.run.status is WorkflowRunStatus.COMPLETED


def test_v3_validate_preserves_metadata_and_input_defaults():
    """Metadata default is used when no dependency overrides, but dependency is authoritative."""
    nodes = (
        WorkflowNode(
            "producer",
            "execute_operation",
            "Producer",
            operation_id="op.p",
            operation_version="1.0.0",
        ),
        WorkflowNode(
            "validate",
            "validate",
            "Validate",
            dependencies=("producer",),
            wait_condition={"policy_ok": True},
        ),
        WorkflowNode("finish", "complete", "Finish", dependencies=("validate",)),
    )
    # Metadata default satisfied
    res_meta = _run_validate_nodes(
        nodes,
        {"producer": {"data": 123}},
        metadata={"policy_ok": True},
    )
    assert res_meta.run.status is WorkflowRunStatus.COMPLETED

    # Declared dependency overriding metadata default to False fails
    res_override = _run_validate_nodes(
        nodes,
        {"producer": {"policy_ok": False}},
        metadata={"policy_ok": True},
    )
    assert res_override.run.status is not WorkflowRunStatus.COMPLETED
    assert res_override.run.error_code == "validate.condition_false"


# ─────────────────────────────────────────────────────────────────────────────
# 2. V3-I2: PERSISTENCE AUTHENTICITY GATE
# ─────────────────────────────────────────────────────────────────────────────


def test_v3_persistence_raw_and_mapping_denied():
    """Raw boolean, Mapping, and arbitrary dicts never confirm persistence."""
    for raw in (
        True,
        False,
        "confirmed",
        1,
        {"approved": True},
        {"decision_id": "d-1", "request_id": "r-1", "approved": True},
    ):
        record = classify_persistence(
            {"proposal_id": "p-1", "pattern": "x", "sources": ("msg:1", "msg:2")},
            confirmation=raw,
        )
        assert record["confirmed"] is False
        assert record["persistence_state"] != "confirmed"


def test_v3_persistence_standalone_snapshot_alone_denied():
    """A standalone DomainMemoryApprovalDecisionSnapshot without valid inventory fails closed."""
    snap = DomainMemoryApprovalDecisionSnapshot(
        decision_id="dec-1", request_id="req-1", approved=True
    )
    record = classify_persistence(
        {"proposal_id": "p-1", "pattern": "x", "sources": ("msg:1", "msg:2")},
        confirmation=snap,
    )
    assert record["confirmed"] is False
    assert record["authorization_accepted"] is False
    assert record["authorization_malformed"] is True
    assert record["persistence_state"] == "candidate"


def test_v3_persistence_binding_or_inventory_alone_denied():
    """Supplying only binding or only inventory fails closed."""
    binding, inventory = _build_valid_reflection_chain("prop-alone", approved=True)

    # Binding only
    rec1 = classify_persistence(
        {"proposal_id": "prop-alone", "pattern": "x", "sources": ("msg:1", "msg:2")},
        confirmation_binding=binding,
        confirmation_inventory=None,
    )
    assert rec1["confirmed"] is False
    assert rec1["authorization_accepted"] is False

    # Inventory only
    rec2 = classify_persistence(
        {"proposal_id": "prop-alone", "pattern": "x", "sources": ("msg:1", "msg:2")},
        confirmation_binding=None,
        confirmation_inventory=inventory,
    )
    assert rec2["confirmed"] is False
    assert rec2["authorization_accepted"] is False


def test_v3_persistence_wrong_proposal_id_denied():
    """Binding for proposal A cannot authorize persistence record for proposal B."""
    binding, inventory = _build_valid_reflection_chain("prop-alpha", approved=True)
    record = classify_persistence(
        {"proposal_id": "prop-beta", "pattern": "x", "sources": ("msg:1", "msg:2")},
        confirmation_binding=binding,
        confirmation_inventory=inventory,
    )
    assert record["confirmed"] is False
    assert record["authorization_accepted"] is False


def test_v3_persistence_broken_chain_denied():
    """Request for different proposal or decision for different request fails closed."""
    # Request points to wrong proposal
    b1, inv1 = _build_valid_reflection_chain(
        "prop-chain-1", approved=True, wrong_request_prop_id="prop-other"
    )
    rec1 = classify_persistence(
        {"proposal_id": "prop-chain-1", "pattern": "x", "sources": ("msg:1", "msg:2")},
        confirmation_binding=b1,
        confirmation_inventory=inv1,
    )
    assert rec1["confirmed"] is False

    # Decision points to wrong request
    b2, inv2 = _build_valid_reflection_chain(
        "prop-chain-2", approved=True, wrong_decision_req_id="req-other"
    )
    rec2 = classify_persistence(
        {"proposal_id": "prop-chain-2", "pattern": "x", "sources": ("msg:1", "msg:2")},
        confirmation_binding=b2,
        confirmation_inventory=inv2,
    )
    assert rec2["confirmed"] is False


def test_v3_persistence_unlinked_extra_approval_denied():
    """Missing or unlinked approval request/decision fails closed."""
    b, inv = _build_valid_reflection_chain("prop-extra-req", approved=True)
    # Inventory with approval requests stripped out
    bad_inv1 = DomainMemoryReferenceInventory(
        references=inv.references,
        proposals=inv.proposals,
        permission_decisions=inv.permission_decisions,
        approval_requests=(),
        approval_decisions=inv.approval_decisions,
        traces=inv.traces,
        views=inv.views,
    )
    rec1 = classify_persistence(
        {
            "proposal_id": "prop-extra-req",
            "pattern": "x",
            "sources": ("msg:1", "msg:2"),
        },
        confirmation_binding=b,
        confirmation_inventory=bad_inv1,
    )
    assert rec1["confirmed"] is False

    # Inventory with approval decisions stripped out
    bad_inv2 = DomainMemoryReferenceInventory(
        references=inv.references,
        proposals=inv.proposals,
        permission_decisions=inv.permission_decisions,
        approval_requests=inv.approval_requests,
        approval_decisions=(),
        traces=inv.traces,
        views=inv.views,
    )
    rec2 = classify_persistence(
        {
            "proposal_id": "prop-extra-req",
            "pattern": "x",
            "sources": ("msg:1", "msg:2"),
        },
        confirmation_binding=b,
        confirmation_inventory=bad_inv2,
    )
    assert rec2["confirmed"] is False


def test_v3_persistence_wrong_domain_denied():
    """Binding for another domain (e.g. domain:health) cannot authorize reflection persistence."""
    b, inv = _build_valid_reflection_chain(
        "prop-wrong-dom", domain_id="domain:health", approved=True
    )
    record = classify_persistence(
        {
            "proposal_id": "prop-wrong-dom",
            "pattern": "x",
            "sources": ("msg:1", "msg:2"),
        },
        confirmation_binding=b,
        confirmation_inventory=inv,
    )
    assert record["confirmed"] is False
    assert record["authorization_accepted"] is False


def test_v3_persistence_tampered_binding_denied():
    """Tampered view digest in inventory fails validation and is denied."""
    b, inv = _build_valid_reflection_chain("prop-tamper", approved=True)
    bad_view = DomainMemoryViewSnapshot(
        view_id="view:req:prop-tamper:" + "0" * 12,
        request_id="req:prop-tamper",
        primary_domain="domain:reflection",
        trace_id="trace:prop-tamper",
        view_digest="0" * 64,
    )
    tampered_inv = DomainMemoryReferenceInventory(
        references=inv.references,
        proposals=inv.proposals,
        permission_decisions=inv.permission_decisions,
        approval_requests=inv.approval_requests,
        approval_decisions=inv.approval_decisions,
        traces=inv.traces,
        views=(bad_view,),
    )
    record = classify_persistence(
        {"proposal_id": "prop-tamper", "pattern": "x", "sources": ("msg:1", "msg:2")},
        confirmation_binding=b,
        confirmation_inventory=tampered_inv,
    )
    assert record["confirmed"] is False
    assert record["authorization_accepted"] is False


def test_v3_persistence_valid_chain_accepted_when_grounded():
    """A valid inventory-backed binding chain authorizes persistence when grounded."""
    binding, inventory = _build_valid_reflection_chain("prop-valid-1", approved=True)
    val_res = validate_reflection_memory_binding(binding=binding, inventory=inventory)
    assert val_res.is_valid is True

    record = classify_persistence(
        {
            "proposal_id": "prop-valid-1",
            "pattern": "avoids intimacy",
            "sources": ("msg:1", "msg:2"),
        },
        confirmation_binding=binding,
        confirmation_inventory=inventory,
    )
    assert record["authorization_accepted"] is True
    assert record["eligible_for_confirmation"] is True
    assert record["confirmed"] is True
    assert record["persistence_state"] == "confirmed"


def test_v3_persistence_valid_chain_insufficient_basis_not_confirmed():
    """A valid chain with model-inferred or single-conversation basis stays pending_confirmation."""
    binding, inventory = _build_valid_reflection_chain("prop-valid-weak", approved=True)
    record = classify_persistence(
        {
            "proposal_id": "prop-valid-weak",
            "pattern": "avoids intimacy",
            "sources": ("model:inferred",),
            "model_inferred": True,
        },
        confirmation_binding=binding,
        confirmation_inventory=inventory,
    )
    assert record["authorization_accepted"] is True
    assert record["basis_sufficient"] is False
    assert record["confirmed"] is False
    assert record["persistence_state"] == "pending_confirmation"


# ─────────────────────────────────────────────────────────────────────────────
# 3. V3-I3: DIAGNOSIS / RESTRICTED-INFERENCE SAFETY GATE
# ─────────────────────────────────────────────────────────────────────────────


def test_v3_diagnosis_unseen_spanish_direct_classifications_restricted():
    """Unseen Spanish direct diagnoses and assertive personality classifications are flagged."""
    unseen_spanish = (
        "Padeces depresión mayor",
        "Eres depresivo",
        "Sufres de ansiedad",
        "Tienes dependencia emocional",
        "Tu apego es evitativo",
        "Es una persona tóxica por naturaleza",
        "Su motivo real es manipular",
    )
    for stmt in unseen_spanish:
        res = evaluate_hypotheses(
            hypotheses=(
                {"identity": "h-es", "statement": stmt, "supporting_ids": ("s1",)},
            )
        )
        assert res["no_diagnosis"] is False, (
            f"Expected {stmt!r} to be flagged as diagnostic"
        )
        hyp = res["hypotheses"][0]
        assert hyp["diagnostic"] is True
        assert hyp["restricted_inference"] is True
        assert hyp["relative_strength"] is None


def test_v3_diagnosis_unseen_english_direct_classifications_restricted():
    """Unseen English direct diagnoses and assertive personality classifications are flagged."""
    unseen_english = (
        "You suffer from major depression",
        "You have an avoidant attachment style",
        "You are emotionally dependent",
        "Their real motive is to manipulate everyone",
    )
    for stmt in unseen_english:
        res = evaluate_hypotheses(
            hypotheses=(
                {"identity": "h-en", "statement": stmt, "supporting_ids": ("s1",)},
            )
        )
        assert res["no_diagnosis"] is False, (
            f"Expected {stmt!r} to be flagged as diagnostic"
        )
        hyp = res["hypotheses"][0]
        assert hyp["diagnostic"] is True
        assert hyp["restricted_inference"] is True
        assert hyp["relative_strength"] is None


def test_v3_diagnosis_tentative_safe_controls_allowed():
    """Tentative, exploratory hypotheses remain valid non-diagnostic hypotheses."""
    tentative_controls = (
        "Podría estar sintiendo ansiedad en esta situación",
        "Una posibilidad es que aquí evite el conflicto",
        "Puede que esta relación active inseguridad; no hay base para concluir una causa",
        "They may be avoiding this particular conflict",
        "One possibility is that the reaction stems from fatigue",
    )
    for stmt in tentative_controls:
        res = evaluate_hypotheses(
            hypotheses=(
                {"identity": "h-safe", "statement": stmt, "supporting_ids": ("s1",)},
            )
        )
        assert res["no_diagnosis"] is True, (
            f"Expected tentative {stmt!r} to NOT be diagnostic"
        )
        hyp = res["hypotheses"][0]
        assert hyp["diagnostic"] is False
        assert hyp["restricted_inference"] is False


def test_v3_diagnosis_explicit_structural_restriction():
    """Explicit structural safety markers (diagnostic=True, classification_kind) are preserved."""
    res1 = evaluate_hypotheses(
        hypotheses=(
            {
                "identity": "h-struct-1",
                "statement": "Neutral statement without diagnostic words",
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
                "identity": "h-struct-2",
                "statement": "Another neutral statement",
                "supporting_ids": ("s1",),
                "classification_kind": "personality_classification",
            },
        )
    )
    assert res2["no_diagnosis"] is False
    assert res2["hypotheses"][0]["diagnostic"] is True


def test_v3_diagnosis_presentation_parity():
    """Restricted classifications are withheld and presented as [restricted: claim withheld]."""
    raw_eval = evaluate_hypotheses(
        hypotheses=(
            {
                "identity": "h-pres",
                "statement": "Padeces depresión mayor",
                "supporting_ids": ("s1",),
            },
        )
    )
    presented = present_reflection_result(raw_eval)
    presented_hyp = presented["hypotheses"][0]
    assert presented_hyp["diagnosis"] is True
    assert presented_hyp["restricted_inference"] is True
    assert (
        presented_hyp["statement"]
        == "[restricted: diagnostic/classifying claim withheld]"
    )
    assert "Padeces" not in presented_hyp["statement"]


# ─────────────────────────────────────────────────────────────────────────────
# 4. V3-I4: NO FORCED CONCLUSION (STRUCTURAL & CONCLUSION-SCOPED)
# ─────────────────────────────────────────────────────────────────────────────


def test_v3_no_forced_conclusion_unseen_certainty_conclusions_flagged():
    """Unresolved results with unseen unsupported certainty in conclusion fields are flagged."""
    unseen_certainty = (
        "Tengo la certeza absoluta de que todo fue por rechazo",
        "Definitivamente él actuó por celos",
        "No hay ninguna duda: esa es la causa",
        "This proves beyond doubt that rejection caused everything",
        "There can be no doubt that this was the motive",
    )
    for cert_text in unseen_certainty:
        res = {
            "unresolved": True,
            "conclusion": cert_text,
        }
        policy = no_forced_conclusion_policy(res)
        assert policy["forced_conclusion"] is True, (
            f"Expected {cert_text!r} to be flagged"
        )
        assert policy["valid_unresolved_completion"] is False


def test_v3_no_forced_conclusion_quoted_evidence_not_flagged():
    """Certainty wording occurring ONLY in evidence/observations/quotes is NOT a forced conclusion."""
    cases = (
        {
            "unresolved": True,
            "evidence": ("La otra persona dijo: 'obviamente no iba a venir'",),
        },
        {
            "unresolved": True,
            "observation": "Escribió literalmente: 'está claro que no quiero hablar'",
        },
        {
            "unresolved": True,
            "counterevidence": ("Un amigo aseguró que era definitivamente imposible",),
        },
        {
            "unresolved": True,
            "source": "User quote: 'there is no doubt I will be late'",
        },
    )
    for case in cases:
        policy = no_forced_conclusion_policy(case)
        assert policy["forced_conclusion"] is False, (
            f"Expected quoted certainty in {case} to NOT be forced"
        )
        assert policy["valid_unresolved_completion"] is True


def test_v3_no_forced_conclusion_tentative_conclusions_allowed():
    """Tentative, non-definitive conclusions in unresolved reflections are allowed."""
    tentative_conclusions = (
        "Una posibilidad es que influyera el rechazo",
        "No puedo concluir una causa",
        "Podría ser una explicación, pero hay incertidumbre",
        "One possibility is context, but the evidence is incomplete",
    )
    for stmt in tentative_conclusions:
        res = {
            "unresolved": True,
            "conclusion": stmt,
        }
        policy = no_forced_conclusion_policy(res)
        assert policy["forced_conclusion"] is False, (
            f"Expected tentative {stmt!r} to NOT be forced"
        )
        assert policy["valid_unresolved_completion"] is True


def test_v3_no_forced_conclusion_structural_state_enforcement():
    """Structural certainty/adoption flags force-close the gate when unresolved."""
    for field, val in (
        ("conclusion_status", "final"),
        ("conclusion_status", "certain"),
        ("certainty_state", "absolute"),
        ("certainty_level", "definitive"),
        ("fact", True),
        ("winner_selected", True),
        ("conclusion_adopted", True),
        ("decision_adopted", True),
    ):
        res = {"unresolved": True, field: val}
        policy = no_forced_conclusion_policy(res)
        assert policy["forced_conclusion"] is True, (
            f"Expected {field}={val} to flag forced conclusion"
        )
        assert policy["valid_unresolved_completion"] is False


def test_v3_no_forced_conclusion_rule_and_presentation_parity():
    """NoForcedConclusionRule and present_reflection_result preserve forced conclusion status."""
    res_forced = {
        "unresolved": True,
        "conclusion": "Tengo la certeza absoluta de que todo fue por rechazo",
    }
    context = ReasoningRuleContext(
        reasoning_id="rr-v3-nfc",
        timestamp=NOW,
        active_domains=("domain:reflection",),
        primary_domain="domain:reflection",
        metadata={"result": res_forced},
    )
    rule = next(
        r
        for r in build_reflection_rules()
        if r.definition.id == "reflection.no_forced_conclusion"
    )
    rule_res = rule.evaluate(context)
    assert rule_res.status is ReasoningRuleResultStatus.APPLIED
    assert rule_res.findings[0].metadata["forced_conclusion"] is True

    pres = present_reflection_result(res_forced)
    assert pres["unresolved"] is True
    assert pres["conclusion_presented"] is False


# ─────────────────────────────────────────────────────────────────────────────
# 5. ROBUSTNESS, STRICT JSON, NON-MUTATION
# ─────────────────────────────────────────────────────────────────────────────


def test_v3_strict_json_all_outputs():
    """All public helper and rule outputs must be strictly JSON-serializable."""
    binding, inventory = _build_valid_reflection_chain("prop-json", approved=True)

    outputs = (
        classify_persistence(
            {"proposal_id": "prop-json", "pattern": "x", "sources": ("s1", "s2")},
            confirmation_binding=binding,
            confirmation_inventory=inventory,
        ),
        evaluate_hypotheses(
            hypotheses=(
                {"identity": "h1", "statement": "test stmt", "supporting_ids": ("s1",)},
            )
        ),
        no_forced_conclusion_policy({"unresolved": True, "conclusion": "safe"}),
        evaluate_ambivalence(records=()),
        evaluate_open_questions(questions=()),
        evaluate_persistence_basis({"pattern": "x", "sources": ("s1",)}),
        map_interests(records=()),
        classify_belief_evidence(records=()),
    )
    for out in outputs:
        encoded = json.dumps(out, allow_nan=False)
        assert isinstance(encoded, str)


def test_v3_input_non_mutation():
    """Input structures must not be mutated by helper execution."""
    binding, inventory = _build_valid_reflection_chain("prop-mut", approved=True)
    raw_record = {"proposal_id": "prop-mut", "pattern": "test", "sources": ["s1", "s2"]}
    raw_copy = copy.deepcopy(raw_record)

    classify_persistence(
        raw_record,
        confirmation_binding=binding,
        confirmation_inventory=inventory,
    )
    assert raw_record == raw_copy

    raw_hyp = [
        {
            "identity": "h1",
            "statement": "Padeces depresión mayor",
            "supporting_ids": ["s1"],
        }
    ]
    hyp_copy = copy.deepcopy(raw_hyp)
    evaluate_hypotheses(hypotheses=raw_hyp)
    assert raw_hyp == hyp_copy
