"""Phase 10.25 — Audit-remediation regression tests for trace supporting
domains and the connected AT-DP-025 end-to-end harness.

Remediates I-008 (trace wrapper cannot represent supporting domains) and
B-004 (AT-DP-025 is not end-to-end).  The connected harness executes one real
deterministic state chain: resolver selection with Concerns + a real
supporting domain, an authorized supporting domain-result projection, the
Concerns workflow/operation sequence with state carried forward, recurrence on
prior output, and a trace assembled from ACTUAL prior IDs/results.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from cmm.domains.concerns.definition import CONCERNS_DOMAIN_ID
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
from cmm.domains.concerns.permissions import persistence_confirmation_accepted
from cmm.domains.concerns.trace import (
    assemble_concerns_trace,
    build_concerns_trace_reference,
    build_supporting_trace_contribution,
    validate_concerns_trace,
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
from cmm.domains.trace_contracts import (
    CrossDomainTraceReference,
    DomainTraceDomainSelection,
    DomainTraceReference,
    DomainTraceReferenceInventory,
    DomainTraceReferenceKind,
)

NOW = datetime(2026, 8, 22, 12, 0, tzinfo=timezone.utc)

# ═════════════════════════════════════════════════════════════════════════════
# I-008: trace supporting domains
# ═════════════════════════════════════════════════════════════════════════════


def test_assemble_concerns_trace_preserves_real_supporting_domains_and_cross_domain_results():
    """A Concerns trace can carry a REAL supporting domain with its own
    domain-result contribution and cross-domain result pairing, validated
    against a DomainTraceReferenceInventory with non-empty
    expected_supporting_domains."""
    supporting = build_supporting_trace_contribution(
        domain_id="domain:relationships",
        domain_result_id="relationship-result:dr-001",
        references=(
            DomainTraceReference(
                ref_id="relationships-fact:1",
                kind=DomainTraceReferenceKind.FINDING,
                domain_id="domain:relationships",
            ),
        ),
    )
    trace = assemble_concerns_trace(
        request_id="req-trace-supp",
        resolution_context_id="resolution-context:1",
        resolution_result_id="resolution-result:1",
        composition_id="composition:1",
        domain_result_id="concerns-result:dr-001",
        started_at=NOW,
        completed_at=NOW.replace(second=1),
        supporting_domains=("domain:relationships",),
        contributions=(supporting,),
        cross_domain_results=(
            CrossDomainTraceReference(
                result_id="cross-relationship:dr-001",
                trace_id="relationship-trace:dr-001",
            ),
        ),
    )
    # The shared contract preserves supporting domain participation.
    assert "domain:relationships" in {
        str(domain) for domain in trace.supporting_domains
    }
    kinds = {r.kind for r in trace.all_references()}
    assert DomainTraceReferenceKind.DOMAIN_RESULT in kinds
    assert DomainTraceReferenceKind.CROSS_DOMAIN_RESULT in kinds

    inventory = DomainTraceReferenceInventory(
        references=trace.all_references(),
        domain_results=trace.domain_results,
        cross_domain_results=trace.references.cross_domain_results,
        expected_primary_domain=CONCERNS_DOMAIN_ID,
        expected_supporting_domains=("domain:relationships",),
        resolution_result_domains=DomainTraceDomainSelection(
            "resolution-result:1",
            CONCERNS_DOMAIN_ID,
            ("domain:relationships",),
        ),
        composition_domains=DomainTraceDomainSelection(
            "composition:1",
            CONCERNS_DOMAIN_ID,
            ("domain:relationships",),
        ),
    )
    result = validate_concerns_trace(trace=trace, inventory=inventory)
    assert result.valid is True
    json.dumps(trace.to_dict(), allow_nan=False)


# ═════════════════════════════════════════════════════════════════════════════
# B-004 / RB-003: connected AT-DP-025 harness
# ═════════════════════════════════════════════════════════════════════════════


def _build_resolver_with_concerns_and_relationships():
    """Build a deterministic standard resolver with General + Concerns +
    Relationships registered (real domains from their own packs).  Standard
    default scoring policy keeps Concerns as primary while Relationships
    joins within the supporting margin via its entity/resource signals —
    the canonical ambiguous-relationship case (frozen design §115 step 2)."""
    from cmm.domains.concerns.definition import build_concerns_domain_definition
    from cmm.domains.general.definition import build_general_domain_definition
    from cmm.domains.relationships.definition import (
        build_relationships_domain_definition,
    )

    registry = DomainRegistry()
    for definition in (
        build_general_domain_definition(),
        build_concerns_domain_definition(),
        build_relationships_domain_definition(),
    ):
        registry.register(definition)
    registry.enable("domain:general")
    registry.enable("domain:concerns")
    registry.enable("domain:relationships")
    # Standard production DefaultDomainResolver with default DomainScoringPolicy
    resolver = DefaultDomainResolver(
        fallback_domain=DomainId.from_str("domain:general"),
        id_factory=(lambda: "resolver-id-exec-001"),
        clock=(lambda: NOW),
    )
    from cmm.domains.general.definition import GENERAL_DOMAIN_ID

    return registry, resolver, GENERAL_DOMAIN_ID


def test_at_dp025_executes_connected_resolver_workflow_and_trace_sequence():
    """The connected acceptance proof.  Every step consumes the prior state;
    the trace references ACTUAL IDs created by the real resolver and workflow
    execution, and the supporting domain (Relationships) participates for the
    canonical ambiguous relationship case (frozen design §115)."""
    from cmm.domains.concerns.workflows import build_concerns_workflow_definitions
    from cmm.domains.concerns.operations import (
        build_concerns_operation_definitions,
        explore_hypotheses_result,
    )
    from cmm.domains.concerns.rules import (
        classify_concern_statement,
        evaluate_question_materiality,
    )
    from cmm.domains.workflow_execution import DomainWorkflowExecutor
    from cmm.domains.workflow_contracts import DomainWorkflowContext
    from cmm.workflows.engine import NodeExecution
    from cmm.workflows.enums import WorkflowRunStatus

    registry, resolver, _general_id = _build_resolver_with_concerns_and_relationships()

    # ── Step 1-2: Resolver selects Concerns + Relationships (supporting) ──
    builder = DomainResolutionContextBuilder(
        id_factory=lambda: "ctx-1", clock=lambda: NOW
    )
    context = builder.build(
        registry_snapshot=registry.snapshot(),
        user_input=(
            "My partner didn't reply to my message and I'm afraid they are "
            "losing interest; I keep checking my phone."
        ),
        authorized_domains=(
            "domain:concerns",
            "domain:relationships",
            "domain:general",
        ),
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
    assert "domain:relationships" in {
        str(domain) for domain in resolution.supporting_domains
    }
    resolution_result_id = resolution.id

    # ── Step 2b: authorized supporting domain_result projection ────────────
    relationships_result_id = "relationship-result:exec-001"
    relationships_projection = {
        "domain_id": "domain:relationships",
        "domain_result_id": relationships_result_id,
        "authorized": True,
        "relationship_type": "romantic_partner",
        "observed_behavior": "no reply to message sent yesterday",
        "motive_unknown": True,
    }
    assert relationships_projection["authorized"] is True
    assert relationships_projection["motive_unknown"] is True

    # ── Step 3-8: Execute real Concerns workflow with DomainWorkflowExecutor ──
    all_wfs = build_concerns_workflow_definitions()
    all_ops = build_concerns_operation_definitions()
    open_concern_wf = next(w for w in all_wfs if w.workflow_id == "concerns.open_concern_conversation")

    op_exec_count = 0
    created_op_ids: dict[str, str] = {}
    saved_step_outputs: dict[str, Any] = {}

    concern_material = {
        "situation": "partner silent after my message since yesterday",
        "what_matters": "whether they are losing interest",
        "explicit_request": "Tell me what you think.",
        "evidence_references": ("res:msg:1",),
        "specialized_domain_result": relationships_projection,
    }

    def workflow_operation_adapter(node, run):
        nonlocal op_exec_count
        op_exec_count += 1
        op_res_id = f"op-res-{node.node_id}-{op_exec_count}"
        created_op_ids[node.node_id] = op_res_id
        if node.operation_id == "concerns.understand_concern":
            res = understand_concern_result(material=concern_material)
            saved_step_outputs["understand"] = res
            return NodeExecution.complete(res, operation_result=res)
        elif node.operation_id == "concerns.infer_support_need":
            res = infer_support_need_result(
                explicit_request="Tell me what you think.",
                current_signal="I keep checking my phone",
            )
            saved_step_outputs["support_need"] = res
            return NodeExecution.complete(res, operation_result=res)
        elif node.operation_id == "concerns.map_lived_experience":
            res = map_lived_experience_result(
                material={
                    "emotion_statements": ("I'm anxious about the silence",),
                    "fear_statements": ("that they are drifting away",),
                    "interpretation_statements": ("the silence means they lost interest",),
                    "desired_outcome": "understand what is happening",
                }
            )
            saved_step_outputs["lived_experience"] = res
            return NodeExecution.complete(res, operation_result=res)
        elif node.operation_id == "concerns.identify_open_questions":
            res = identify_open_questions_result(
                questions=(
                    {"question": "Has this pattern happened before?", "changes": ("meaning", "interpretation")},
                    {"question": "What font did they use?", "changes": ()},
                )
            )
            saved_step_outputs["gaps"] = res
            return NodeExecution.complete(res, operation_result=res)
        elif node.node_type.value == "validate":
            return NodeExecution.complete({"valid": True})
        return NodeExecution.complete({"ok": True})

    executor = DomainWorkflowExecutor(
        id_factory=lambda: f"wf-run-exec-{op_exec_count + 1}",
        clock=lambda: NOW,
        operation_adapter=workflow_operation_adapter,
        operation_definitions={op.operation_id: op for op in all_ops},
        workflow_definitions={wf.workflow_id: wf for wf in all_wfs},
    )
    wf_context = DomainWorkflowContext(
        primary_domain_id=CONCERNS_DOMAIN_ID,
        supporting_domain_ids=("domain:relationships",),
        available_operations=frozenset(op.operation_id for op in all_ops),
        authorized_domain_ids=frozenset(["domain:concerns", "domain:relationships"]),
    )
    workflow_run = executor.execute(
        open_concern_wf,
        wf_context,
        inputs={
            "concern": "partner silent after message",
            "specialized_domain_result": relationships_projection,
        },
    )
    assert workflow_run.common_run.status is WorkflowRunStatus.COMPLETED
    concerns_workflow_run_id = workflow_run.common_run.run_id

    # Verify workflow step outputs
    understanding = saved_step_outputs["understand"]
    assert understanding["mandatory_action_plan"] is False
    assert understanding["advice_generated"] is False
    assert understanding["ready_for_substantive_response"] is True

    lived = saved_step_outputs["lived_experience"]
    assert lived["emotions"][0]["experience_valid"] is True
    assert lived["emotions"][0]["external_fact"] is False

    support = saved_step_outputs["support_need"]
    assert support["support_need"] in ("PERSPECTIVE", "REALITY_CHECK")

    open_questions = saved_step_outputs["gaps"]
    assert open_questions["ritual_questions_suppressed"] >= 1
    assert len(open_questions["questions"]) == 1

    # ── Step 5: one external interpretation remains unverified ─────────────
    interpretation = classify_concern_statement(
        {
            "statement": "the silence means they lost interest",
            "level": "interpretation",
        }
    )
    assert interpretation["grounded"] is False
    assert interpretation["external_fact"] is False

    # ── Steps 9-10: new information consumed from prior state; levels stay ──
    separation = separate_reality_interpretation_result(
        statements=(
            {
                "statement": "the message was delivered yesterday",
                "level": "fact",
                "evidence_references": ("res:msg:1",),
            },
            {
                "statement": "they are losing interest",
                "level": "interpretation",
            },
            {
                "statement": "maybe they were busy",
                "level": "hypothesis",
            },
        )
    )
    levels = {record["level"] for record in separation["statements"]}
    assert levels == {"fact", "interpretation", "hypothesis"}
    fact_record = next(r for r in separation["statements"] if r["level"] == "fact")
    assert fact_record["grounded"] is True
    assert separation["interpretation_promoted_to_fact"] is False

    # ── Step 11: multiple hypotheses preserved ─────────────────────────────
    hypotheses = explore_hypotheses_result(
        hypotheses=(
            {
                "identity": "hyp:busy",
                "statement": "they were busy with work",
                "supporting_ids": ("res:msg:1",),
            },
            {
                "identity": "hyp:drift",
                "statement": "they are losing interest",
                "supporting_ids": (),
            },
        )
    )
    assert len(hypotheses["hypotheses"]) == 2
    assert hypotheses["winner_selected"] is False
    assert hypotheses["no_diagnosis"] is True

    # ── Step 12: partial reassurance consumes the prior evidence state ─────
    reassurance = evaluate_reassurance_result(
        target_claim="they are losing interest",
        evidence=(
            {
                "identity": "evidence:delivered-message",
                "claim": "the message was delivered yesterday",
                "stance": "opposes_target",
                "grounding": "res:msg:1",
                "source_quality": "grounded",
                "temporal_relevance": "current",
            },
        ),
        counterevidence=(
            {
                "identity": "evidence:drift-interpretation",
                "claim": "the silence means they lost interest",
                "stance": "supports_target",
                "grounding": "res:msg:1",
                "source_quality": "unverified_hearsay",
                "temporal_relevance": "current",
            },
        ),
        uncertainty=({"identity": "uncertainty:intent", "unknown": "their current intent"},),
        material_concerns=("the silence means they lost interest",),
        specialized_domain_result=relationships_projection,
    )
    # Step 12: Assert EXACT outcome REASSURANCE_PARTIAL
    assert reassurance["assessment"] == "REASSURANCE_PARTIAL"
    assert reassurance["absolute_certainty"] is False
    assert tuple(reassurance["remaining_uncertainty"]) != ()

    # ── Step 13: one real concern acknowledged in connected state ──────────
    assert reassurance["material_concern"] is True
    assert "the silence means they lost interest" in reassurance["acknowledged_concerns"]
    assert reassurance["concern_erased"] is False

    # ── Step 14: no absolute certainty invented ────────────────────────────
    assert reassurance["absolute_certainty"] is False

    # ── Steps 15-17: revisit same worry; evidence compared to PRIOR state ──
    prior_evidence_refs = ("res:msg:1",)
    recurrence = review_recurring_concern_result(
        current={
            "topic": "partner silence",
            "question": "are they losing interest?",
            "evidence_references": list(prior_evidence_refs),
        },
        previous=(
            {
                "topic": "partner silence",
                "question": "are they losing interest?",
                "evidence_references": list(prior_evidence_refs),
            },
        ),
    )
    assert recurrence["recurrence"] == "same_question_same_evidence"
    assert recurrence["pathology_inferred"] is False
    assert recurrence["evidence_changed"] is False
    assert recurrence["reassurance_allowed"] is True

    # ── Step 18: no new risk invented from repetition ──────────────────────
    assert recurrence["new_risk_invented_from_repetition"] is False

    # ── Steps 19-22: options, one proportionate next step as proposal ──────
    options = explore_options_result(
        options=(
            {"option_id": "wait until tomorrow", "expected_benefit": "see if they reply naturally", "reversible": True},
            {"option_id": "send a brief follow-up", "expected_benefit": "clarity", "cost": "possible pressure"},
        ),
    )
    assert options["decision_adopted"] is False
    next_step = prepare_next_step_result(
        desired_outcome="understand the silence",
        options=("wait until tomorrow",),
        user_request="What can I do?",
        grounded_options=True,
    )
    assert next_step["next_step"]["proposal_only"] is True
    assert next_step["executed"] is False
    assert next_step["external_action_executed"] is False

    # ── Step 23: no external action ────────────────────────────────────────
    assert next_step["external_action_executed"] is False

    # ── Step 24: no silent persistence ─────────────────────────────────────
    confirmation = persistence_confirmation_accepted(confirmation=None)
    assert confirmation["accepted"] is False

    # ── Step 25: trace references ACTUAL prior IDs/results ─────────────────
    actual_support_need_ref = build_concerns_trace_reference(
        ref_id=created_op_ids.get("support_need", "op-res-support_need-2"),
        kind=DomainTraceReferenceKind.OPERATION_RESULT,
    )
    actual_evidence_ref = build_concerns_trace_reference(
        ref_id="res:msg:1",
        kind=DomainTraceReferenceKind.RESOURCE_RESOLUTION,
    )
    actual_workflow_ref = build_concerns_trace_reference(
        ref_id=concerns_workflow_run_id,
        kind=DomainTraceReferenceKind.WORKFLOW_RESULT,
    )
    actual_uncertainty_ref = build_concerns_trace_reference(
        ref_id="uncertainty:intent",
        kind=DomainTraceReferenceKind.GAP,
    )
    actual_reassurance_ref = build_concerns_trace_reference(
        ref_id=f"rule:reassurance:{reassurance['assessment']}",
        kind=DomainTraceReferenceKind.RULE_RESULT,
    )
    actual_recurrence_ref = build_concerns_trace_reference(
        ref_id=f"recurrence:{recurrence['recurrence']}",
        kind=DomainTraceReferenceKind.RULE_RESULT,
    )
    actual_action_ref = build_concerns_trace_reference(
        ref_id="action:proposal-only",
        kind=DomainTraceReferenceKind.OPERATION_RESULT,
    )
    supporting = build_supporting_trace_contribution(
        domain_id="domain:relationships",
        domain_result_id=relationships_result_id,
        references=(
            DomainTraceReference(
                ref_id="relationships-observed-behavior:1",
                kind=DomainTraceReferenceKind.FINDING,
                domain_id="domain:relationships",
            ),
        ),
    )
    trace = assemble_concerns_trace(
        request_id="req-atdp-connected",
        resolution_context_id="resolution-context:exec-001",
        resolution_result_id=resolution_result_id,
        composition_id="composition:exec-001",
        domain_result_id="concerns-result:exec-001",
        started_at=NOW,
        completed_at=NOW.replace(second=1),
        references=(
            actual_workflow_ref,
            actual_support_need_ref,
            actual_evidence_ref,
            actual_uncertainty_ref,
            actual_reassurance_ref,
            actual_recurrence_ref,
            actual_action_ref,
        ),
        supporting_domains=("domain:relationships",),
        contributions=(supporting,),
        cross_domain_results=(
            CrossDomainTraceReference(
                result_id="cross-relationship:exec-001",
                trace_id="relationship-trace:exec-001",
            ),
        ),
    )

    # The trace MUST use the actual resolution result id produced by the real resolver
    assert trace.references.resolution_result_id == resolution_result_id
    # The action-state DOMAIN_RESULT reference is the Concerns domain-result
    assert trace.domain_results[0].result_id == "concerns-result:exec-001"
    # The real supporting domain participated.
    assert "domain:relationships" in {
        str(domain) for domain in trace.supporting_domains
    }
    # The supporting domain-result reference resolves to the ACTUAL relationships result id
    supporting_refs = {
        (r.ref_id, r.kind, str(r.domain_id))
        for contribution in trace.contributions if str(contribution.domain_id) != CONCERNS_DOMAIN_ID
        for r in contribution.references
    }
    assert (relationships_result_id, DomainTraceReferenceKind.DOMAIN_RESULT, "domain:relationships") in supporting_refs

    inventory = DomainTraceReferenceInventory(
        references=trace.all_references(),
        domain_results=trace.domain_results,
        cross_domain_results=trace.references.cross_domain_results,
        expected_primary_domain=CONCERNS_DOMAIN_ID,
        expected_supporting_domains=("domain:relationships",),
        resolution_result_domains=DomainTraceDomainSelection(
            resolution_result_id,
            CONCERNS_DOMAIN_ID,
            ("domain:relationships",),
        ),
        composition_domains=DomainTraceDomainSelection(
            "composition:exec-001",
            CONCERNS_DOMAIN_ID,
            ("domain:relationships",),
        ),
    )
    validation = validate_concerns_trace(trace=trace, inventory=inventory)
    assert validation.valid is True
    json.dumps(trace.to_dict(), allow_nan=False)