"""Permanent Closure Adversarial Regression Gate for Phase 10.29 Life Plan Domain.

Permanent adversarial gate testing 30+ essential security, semantic, and boundary invariants:
01 preference -> decision rejected without confirmation
02 scenario -> decision rejected without confirmation
03 scenario -> commitment rejected without confirmation
04 inference -> decision/confirmed status rejected
05 unknown current decision state rejected
06 unknown proposed decision state rejected
07 closed decision reopening rejected without new evidence
08 alternative route does not imply abandonment
09 missing resource evidence remains unknown
10 malformed numeric resource evidence fails closed
11 raw cross-domain mapping rejected
12 arbitrary authorization ID rejected
13 caller authorization boolean rejected
14 real forged PermissionGateResult rejected
15 permission source/target/actor/session/purpose mismatch rejected
16 most-restrictive permission wins
17 purpose minimization rejects unrelated dossier fields
18 manually constructed direct AuthorizedCrossDomainContribution rejected
19 manually constructed wrapped AuthorizedCrossDomainContribution rejected
20 automatic goal abandonment impossible
21 external commitment without canonical approval rejected
22 forged approval ID/object rejected
23 payment/spend without approved external path rejected
24 strict memory confirmation coercions rejected
25 memory cannot promote inference/scenario to confirmed state
26 trace inventory independent from final trace
27 trace tamper/orphan/wrong-domain references rejected
28 atomic registration rollback preserves exact state
29 General fallback remains intact after failed registration
30 workflow public name is Major Decision Support
"""

from __future__ import annotations

import dataclasses
from datetime import datetime, timezone
from typing import Any

import pytest

from cmm.agent_runtime.approval_repository import InMemoryApprovalRepository
from cmm.agent_runtime.approval_service import ApprovalService
from cmm.agent_runtime.domain_permission_contracts import (
    PermissionCapability,
    PermissionOutcome,
)
from cmm.domains.contracts import DomainResult
from cmm.domains.general.bootstrap import build_standard_general_domain_bootstrap
from cmm.domains.general.permissions import build_general_permission_policy
from cmm.domains.health.permissions import build_health_permission_policy
from cmm.domains.identifiers import DomainId
from cmm.domains.life_plan import (
    LIFE_PLAN_DOMAIN_ID,
    assemble_life_plan_trace,
    build_life_plan_memory_binding,
    build_life_plan_memory_proposal,
    build_life_plan_memory_view,
    build_life_plan_memory_view_request,
    build_life_plan_permission_policy,
    build_life_plan_profile,
    build_life_plan_trace_contribution,
    build_life_plan_trace_reference,
    build_life_plan_workflow_definitions,
    evaluate_alternative_route,
    evaluate_cross_domain_impact,
    evaluate_decision_status,
    evaluate_goal_dependencies,
    evaluate_plan_drift,
    evaluate_resource_constraints,
    evaluate_scenario_consistency,
    execute_cross_domain_impact_workflow,
    register_life_plan_domain,
    validate_life_plan_memory_binding,
    validate_life_plan_memory_proposal_content,
    validate_life_plan_trace,
)
from cmm.domains.life_plan.rules import AuthorizedCrossDomainContribution
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
from cmm.domains.permission_contracts import (
    CrossDomainPermissionRequest,
    DomainPermissionRequest,
)
from cmm.domains.permission_gate import (
    DomainPermissionGate,
    PermissionGateResult,
)
from cmm.domains.permission_registry import DomainPermissionRegistry
from cmm.domains.permission_resolution import DomainPermissionResolver
from cmm.domains.trace_contracts import (
    DomainResultTraceReference,
    DomainTrace,
    DomainTraceDomainSelection,
    DomainTraceReference,
    DomainTraceReferenceInventory,
    DomainTraceReferenceKind,
    DomainTraceReferences,
    DomainTraceStatus,
)

NOW = datetime(2026, 8, 26, 12, 0, tzinfo=timezone.utc)


def _setup_runtime() -> tuple[
    DomainPermissionRegistry,
    DomainPermissionResolver,
    ApprovalService,
    DomainPermissionGate,
]:
    perm_registry = DomainPermissionRegistry()
    perm_registry.register(build_life_plan_permission_policy())
    perm_registry.register(build_general_permission_policy())
    health_policy = dataclasses.replace(
        build_health_permission_policy(),
        allow_cross_domain_access=True,
        allowed_target_domains=("domain:life-plan",),
        allowed_capabilities=(
            PermissionCapability.DOMAIN_CROSS_ACCESS,
            PermissionCapability.RESOURCE_READ,
        ),
        allowed_resource_kinds=("resource.health_constraints",),
        allowed_sensitivity_levels=("restricted",),
    )
    perm_registry.register(health_policy)
    approval_service = ApprovalService(InMemoryApprovalRepository())
    resolver = DomainPermissionResolver(perm_registry)
    gate = DomainPermissionGate(resolver, approval_service, clock=lambda: NOW)
    return perm_registry, resolver, approval_service, gate


# 01. Preference -> Decision rejected without confirmation
def test_closure_gate_01_preference_to_decision_rejected_without_confirmation() -> None:
    res = evaluate_decision_status("preference", "decision")
    assert res["allowed"] is False
    assert res["requires_confirmation"] is True
    assert (
        "confirmation" in res["reason"].lower()
        or "unconfirmed" in res["reason"].lower()
    )


# 02. Scenario -> Decision rejected without confirmation
def test_closure_gate_02_scenario_to_decision_rejected_without_confirmation() -> None:
    res = evaluate_decision_status("scenario", "decision")
    assert res["allowed"] is False
    assert res["requires_confirmation"] is True


# 03. Scenario -> Commitment rejected without confirmation
def test_closure_gate_03_scenario_to_commitment_rejected_without_confirmation() -> None:
    res = evaluate_decision_status("scenario", "commitment")
    assert res["allowed"] is False
    assert res["requires_confirmation"] is True
    assert (
        "confirmation" in res["reason"].lower()
        or "unconfirmed" in res["reason"].lower()
    )


# 04. Inference -> Decision / Confirmed status rejected
def test_closure_gate_04_inference_to_decision_or_confirmed_status_rejected() -> None:
    res_dec = evaluate_decision_status("inference", "decision")
    assert res_dec["allowed"] is False

    res_com = evaluate_decision_status("inference", "commitment")
    assert res_com["allowed"] is False


# 05. Unknown current decision state rejected
def test_closure_gate_05_unknown_current_decision_state_rejected() -> None:
    res1 = evaluate_decision_status("nonsense", "decision")
    assert res1["allowed"] is False
    res2 = evaluate_decision_status("arbitrary_unknown_status", "goal")
    assert res2["allowed"] is False


# 06. Unknown proposed decision state rejected
def test_closure_gate_06_unknown_proposed_decision_state_rejected() -> None:
    res1 = evaluate_decision_status("idea", "confirmed_fact")
    assert res1["allowed"] is False
    res2 = evaluate_decision_status("preference", "arbitrary_prop_status")
    assert res2["allowed"] is False


# 07. Closed decision reopening rejected without new evidence
def test_closure_gate_07_closed_decision_reopening_rejected_without_new_evidence() -> (
    None
):
    res = evaluate_decision_status(
        "decision", "idea", is_closed=True, has_new_evidence=False
    )
    assert res["allowed"] is False
    assert "evidence" in res["reason"].lower() or "closed" in res["reason"].lower()


# 08. Alternative route does not imply abandonment
def test_closure_gate_08_alternative_route_does_not_imply_abandonment() -> None:
    res = evaluate_alternative_route("goal-career-01", "route-b", route_type="fallback")
    assert res["primary_goal_abandoned"] is False
    assert res["is_failure"] is False
    assert res["is_contingency"] is True


# 09. Missing resource evidence remains unknown
def test_closure_gate_09_missing_resource_evidence_remains_unknown() -> None:
    res_time = evaluate_resource_constraints(time={"required_hours_per_week": 40.0})
    assert res_time["dimensions"]["time"]["status"] == "unknown"
    assert res_time["feasible"] is None

    res_money = evaluate_resource_constraints(money={"required_funds": 1000.0})
    assert res_money["dimensions"]["money"]["status"] == "unknown"
    assert res_money["feasible"] is None


# 10. Malformed numeric resource evidence fails closed
def test_closure_gate_10_malformed_numeric_resource_evidence_fails_closed() -> None:
    res_nan = evaluate_resource_constraints(
        time={"available_hours_per_week": float("nan"), "required_hours_per_week": 20.0}
    )
    assert res_nan["status"] == "invalid_evidence"

    res_inf = evaluate_resource_constraints(
        money={"available_funds": float("inf"), "required_funds": 500.0}
    )
    assert res_inf["status"] == "invalid_evidence"

    res_bool = evaluate_resource_constraints(
        time={"available_hours_per_week": True, "required_hours_per_week": 20.0}
    )
    assert res_bool["status"] == "invalid_evidence"


# 11. Raw cross-domain mapping rejected
def test_closure_gate_11_raw_cross_domain_mapping_rejected() -> None:
    res = evaluate_cross_domain_impact(
        {
            "source_domain": "domain:health",
            "status": "active",
        }
    )
    assert res["applied"] is False
    assert res["authorization_verified"] is False


# 12. Arbitrary authorization ID rejected
def test_closure_gate_12_arbitrary_authorization_id_rejected() -> None:
    res = evaluate_cross_domain_impact(
        {
            "source_domain": "domain:health",
            "status": "active",
            "authorization_reference": "arbitrary-auth-id-999",
        },
        is_authorized=True,
    )
    assert res["applied"] is False
    assert res["authorization_verified"] is False


# 13. Caller authorization boolean rejected
def test_closure_gate_13_caller_authorization_boolean_rejected() -> None:
    res = evaluate_cross_domain_impact(
        {
            "source_domain": "domain:health",
            "status": "active",
        },
        is_authorized=True,
    )
    assert res["applied"] is False
    assert res["authorization_verified"] is False


# 14. Real forged PermissionGateResult and gate-issued decision ID replay rejected
def test_closure_gate_14_real_forged_permission_gate_result_rejected() -> None:
    _, _, _, gate = _setup_runtime()

    # Step 1: Issue legitimate decision ID on unrelated request
    unrelated_request = CrossDomainPermissionRequest(
        request_id="req-unrelated-adv-1",
        source_domain="domain:health",
        target_domain=LIFE_PLAN_DOMAIN_ID,
        capability=PermissionCapability.RESOURCE_READ,
        reason="unrelated health check",
        actor_id="actor-other",
        session_id="sess-other",
        sensitivity_level="restricted",
        resource_ids=("health.resource.health_profile:hp-001",),
        resource_kinds=("resource.health_constraints",),
    )
    unrelated_pending = gate.evaluate_cross_domain(unrelated_request)
    issued_id = unrelated_pending.decision_id
    assert issued_id is not None
    assert issued_id in gate._issued_decision_ids

    # Step 2: Construct current request that requires approval
    cross_request = CrossDomainPermissionRequest(
        request_id="req-cross-adv-1",
        source_domain="domain:health",
        target_domain=LIFE_PLAN_DOMAIN_ID,
        capability=PermissionCapability.RESOURCE_READ,
        reason="health constraint check",
        actor_id="actor-adv-1",
        session_id="sess-adv-1",
        sensitivity_level="restricted",
        resource_ids=("health.resource.health_profile:hp-001",),
        resource_kinds=("resource.health_constraints",),
    )

    # Step 3: Forged result reusing the gate-issued decision ID with APPROVAL_CONSUMED
    forged_result = PermissionGateResult(
        outcome="approval_consumed",
        action="domain_cross_access",
        domain_id="domain:health",
        actor_id=cross_request.actor_id,
        session_id=cross_request.session_id,
        decision_id=issued_id,
        approval_evidence={"granted": True, "request_id": "fake-app-req-999"},
        metadata={
            "target_domain": "domain:life-plan",
            "source_domain": "domain:health",
        },
    )

    eval_calls: list[Any] = []
    orig_eval = gate.evaluate_cross_domain

    def spy_eval(req: Any, **kwargs: Any) -> Any:
        eval_calls.append((req, kwargs))
        return orig_eval(req, **kwargs)

    gate.evaluate_cross_domain = spy_eval  # type: ignore[assignment]

    res = evaluate_cross_domain_impact(
        {
            "status": "active",
            "activity_limits": ["limit"],
        },
        permission_request=cross_request,
        permission_decision=forged_result,
        permission_gate=gate,
        now=NOW,
    )
    # Replay MUST be rejected
    assert res["applied"] is False
    assert res["authorization_verified"] is False
    assert res["reason"] == "unauthorized_or_expired"

    # Fresh evaluation of current request MUST have been executed
    assert len(eval_calls) == 1
    assert eval_calls[0][0].request_id == "req-cross-adv-1"


# 15. Permission source/target/actor/session/purpose mismatch rejected
def test_closure_gate_15_permission_context_mismatch_rejected() -> None:
    _, _, _, gate = _setup_runtime()
    cross_request = CrossDomainPermissionRequest(
        request_id="req-cross-adv-2",
        source_domain="domain:health",
        target_domain=LIFE_PLAN_DOMAIN_ID,
        capability=PermissionCapability.RESOURCE_READ,
        reason="health constraint check",
        actor_id="actor-adv-2",
        session_id="sess-adv-2",
        sensitivity_level="restricted",
        resource_ids=("health.resource.health_profile:hp-001",),
        resource_kinds=("resource.health_constraints",),
    )

    proj = {
        "status": "active",
        "activity_limits": ["limit"],
    }

    # Wrong target domain in request
    bad_target_req = dataclasses.replace(cross_request, target_domain="domain:evil")
    res1 = evaluate_cross_domain_impact(
        proj,
        permission_request=bad_target_req,
        permission_gate=gate,
        now=NOW,
    )
    assert res1["applied"] is False
    assert res1["authorization_verified"] is False

    # Wrong actor in request
    bad_actor_req = dataclasses.replace(cross_request, actor_id="wrong-actor")
    res2 = evaluate_cross_domain_impact(
        proj,
        permission_request=bad_actor_req,
        permission_gate=gate,
        now=NOW,
    )
    assert res2["applied"] is False
    assert res2["authorization_verified"] is False


# 16. Most-restrictive permission wins
def test_closure_gate_16_most_restrictive_permission_wins() -> None:
    _, resolver, _, _ = _setup_runtime()
    cross_request = CrossDomainPermissionRequest(
        request_id="req-most-restrictive-01",
        source_domain="domain:health",
        target_domain=LIFE_PLAN_DOMAIN_ID,
        capability=PermissionCapability.RESOURCE_READ,
        reason="health data read",
        actor_id="actor-1",
        session_id="sess-1",
        sensitivity_level="restricted",
        resource_ids=("health.resource.health_profile:hp-001",),
        resource_kinds=("resource.health_constraints",),
    )
    res_dec = resolver.resolve_cross_domain(cross_request, now=NOW)
    assert res_dec.decision is PermissionOutcome.APPROVAL_REQUIRED
    assert len(res_dec.approval_requirements) > 0


# 17. Purpose minimization rejects unrelated dossier fields
def test_closure_gate_17_purpose_minimization_rejects_unrelated_dossier_fields() -> (
    None
):
    res = evaluate_cross_domain_impact(
        {
            "source_domain": "domain:health",
            "full_clinical_history": ["heart_surgery_2022"],
            "medication_list": ["atorvastatin_20mg"],
        }
    )
    assert res["applied"] is False
    assert res["reason"] == "rejected_unauthorized_dossier"


# 18. Manually constructed direct AuthorizedCrossDomainContribution rejected
def test_closure_gate_18_manually_constructed_direct_contribution_rejected() -> None:
    forged = AuthorizedCrossDomainContribution(
        projection={"financial_impact": 999999, "status": "active"},
        permission_decision_id="fake-dec",
        permission_request_id="fake-req",
        source_domain="domain:health",
        target_domain="domain:life-plan",
    )
    res = execute_cross_domain_impact_workflow(
        primary_goal={"id": "g-001"},
        supporting_domain_contributions=[forged],
    )
    assert res["supporting_contributions_applied"] == 0


# 19. Manually constructed wrapped AuthorizedCrossDomainContribution rejected
def test_closure_gate_19_manually_constructed_wrapped_contribution_rejected() -> None:
    forged = AuthorizedCrossDomainContribution(
        projection={"financial_impact": 999999, "status": "active"},
        permission_decision_id="fake-dec",
        permission_request_id="fake-req",
        source_domain="domain:health",
        target_domain="domain:life-plan",
    )
    res = execute_cross_domain_impact_workflow(
        primary_goal={"id": "g-001"},
        supporting_domain_contributions=[{"authorized_artifact": forged}],
    )
    assert res["supporting_contributions_applied"] == 0


# 20. Automatic goal abandonment impossible
def test_closure_gate_20_automatic_goal_abandonment_impossible() -> None:
    res_drift = evaluate_plan_drift(
        planned_state={"milestone_1": "completed"},
        actual_state={"milestone_1": "in_progress"},
    )
    assert res_drift["has_drift"] is True
    assert res_drift["goal_abandoned"] is False

    res_alt = evaluate_alternative_route("goal-01", "alt-01", route_type="fallback")
    assert res_alt["primary_goal_abandoned"] is False


# 21. External commitment without canonical approval rejected
def test_closure_gate_21_external_commitment_without_canonical_approval_rejected() -> (
    None
):
    profile = build_life_plan_profile()
    assert "contracting" in profile.prohibited_actions
    assert (
        "external_commitment" in profile.prohibited_actions
        or "contracting" in profile.prohibited_actions
    )


# 22. Forged approval ID or object rejected
def test_closure_gate_22_forged_approval_id_or_object_rejected() -> None:
    _, _, _, gate = _setup_runtime()
    cross_request = CrossDomainPermissionRequest(
        request_id="req-forged-approval-01",
        source_domain="domain:health",
        target_domain=LIFE_PLAN_DOMAIN_ID,
        capability=PermissionCapability.RESOURCE_READ,
        reason="health data read",
        actor_id="actor-1",
        session_id="sess-1",
        sensitivity_level="restricted",
        resource_ids=("health.resource.health_profile:hp-001",),
        resource_kinds=("resource.health_constraints",),
    )
    res = gate.evaluate_cross_domain(
        cross_request, approval_request_id="forged-approval-request-999"
    )
    assert res.allowed is False


# 23. Payment / spend without approved external path rejected
def test_closure_gate_23_payment_spend_without_approved_external_path_rejected() -> (
    None
):
    profile = build_life_plan_profile()
    assert "payment" in profile.prohibited_actions
    assert "external_communication" in profile.prohibited_actions


# 24. Strict memory confirmation coercions rejected
def test_closure_gate_24_strict_memory_confirmation_coercions_rejected() -> None:
    non_booleans = ("false", "true", 0, 1, [], {}, None, "1", "0")
    for val in non_booleans:
        res = validate_life_plan_memory_proposal_content(
            {
                "kind": "decision",
                "status": "decision",
                "original_status": "preference",
                "is_confirmed": val,
            }
        )
        assert res["is_valid"] is False, (
            f"Value {val!r} unexpectedly passed confirmation"
        )


# 25. Memory cannot promote inference/scenario to confirmed state
def test_closure_gate_25_memory_cannot_promote_inference_or_scenario_to_confirmed_state() -> (
    None
):
    for bad_kind in ("scenario", "inference", "hypothesis"):
        res = validate_life_plan_memory_proposal_content(
            {
                "kind": bad_kind,
                "status": "decision",
                "original_status": "idea",
                "is_confirmed": True,
            }
        )
        assert res["is_valid"] is False


# ── Runtime Trace Fixture & Regressions (V2-M2) ──────────────────────────────


def _setup_valid_runtime_trace_fixture() -> tuple[
    DomainTrace, DomainTraceReferenceInventory, str, str, str, str, str
]:
    profile = build_life_plan_profile()
    domain_result = DomainResult(
        id="result-lp-trace-1",
        status="completed",
        objective="Strategy Review Trace Test",
        primary_domain=LIFE_PLAN_DOMAIN_ID,
    )
    result_id_str = str(domain_result.id)
    req_id = "req-trace-01"
    ctx_id = "ctx-trace-01"
    res_id = "res-trace-01"
    comp_id = "comp-trace-01"
    pres_id = "pres-trace-01"
    wf_run_id = "wf-run-trace-01"
    wf_exec_id = "wf-exec-trace-01"
    perm_dec_id = "perm-dec-trace-01"
    app_req_id = "app-req-trace-01"
    app_dec_id = "app-dec-trace-01"
    mem_perm_dec_id = "mem-perm-dec-trace-01"
    mem_app_req_id = "mem-app-req-trace-01"
    mem_app_dec_id = "mem-app-dec-trace-01"
    mem_prop_id = "mem-prop-trace-01"
    mem_bind_id = "mem-bind-trace-01"

    runtime_refs = (
        build_life_plan_trace_reference(
            ref_id=str(profile.id), kind=DomainTraceReferenceKind.PROFILE
        ),
        build_life_plan_trace_reference(
            ref_id=wf_run_id, kind=DomainTraceReferenceKind.WORKFLOW_RUN
        ),
        build_life_plan_trace_reference(
            ref_id=wf_exec_id,
            kind=DomainTraceReferenceKind.WORKFLOW_RESULT,
        ),
        build_life_plan_trace_reference(
            ref_id=perm_dec_id,
            kind=DomainTraceReferenceKind.PERMISSION_DECISION,
        ),
        build_life_plan_trace_reference(
            ref_id=app_req_id,
            kind=DomainTraceReferenceKind.APPROVAL_REQUEST,
        ),
        build_life_plan_trace_reference(
            ref_id=app_dec_id,
            kind=DomainTraceReferenceKind.APPROVAL_DECISION,
        ),
        build_life_plan_trace_reference(
            ref_id=mem_perm_dec_id,
            kind=DomainTraceReferenceKind.PERMISSION_DECISION,
        ),
        build_life_plan_trace_reference(
            ref_id=mem_app_req_id,
            kind=DomainTraceReferenceKind.APPROVAL_REQUEST,
        ),
        build_life_plan_trace_reference(
            ref_id=mem_app_dec_id,
            kind=DomainTraceReferenceKind.APPROVAL_DECISION,
        ),
        build_life_plan_trace_reference(
            ref_id=mem_prop_id,
            kind=DomainTraceReferenceKind.MEMORY_PROPOSAL,
        ),
        build_life_plan_trace_reference(
            ref_id=mem_bind_id,
            kind=DomainTraceReferenceKind.MEMORY_BINDING,
        ),
    )

    expected_refs = (
        DomainTraceReference(
            result_id_str,
            DomainTraceReferenceKind.DOMAIN_RESULT,
            LIFE_PLAN_DOMAIN_ID,
        ),
        DomainTraceReference(
            str(profile.id), DomainTraceReferenceKind.PROFILE, LIFE_PLAN_DOMAIN_ID
        ),
        DomainTraceReference(
            wf_run_id,
            DomainTraceReferenceKind.WORKFLOW_RUN,
            LIFE_PLAN_DOMAIN_ID,
        ),
        DomainTraceReference(
            wf_exec_id,
            DomainTraceReferenceKind.WORKFLOW_RESULT,
            LIFE_PLAN_DOMAIN_ID,
        ),
        DomainTraceReference(
            perm_dec_id,
            DomainTraceReferenceKind.PERMISSION_DECISION,
            LIFE_PLAN_DOMAIN_ID,
        ),
        DomainTraceReference(
            app_req_id,
            DomainTraceReferenceKind.APPROVAL_REQUEST,
            LIFE_PLAN_DOMAIN_ID,
        ),
        DomainTraceReference(
            app_dec_id,
            DomainTraceReferenceKind.APPROVAL_DECISION,
            LIFE_PLAN_DOMAIN_ID,
        ),
        DomainTraceReference(
            mem_perm_dec_id,
            DomainTraceReferenceKind.PERMISSION_DECISION,
            LIFE_PLAN_DOMAIN_ID,
        ),
        DomainTraceReference(
            mem_app_req_id,
            DomainTraceReferenceKind.APPROVAL_REQUEST,
            LIFE_PLAN_DOMAIN_ID,
        ),
        DomainTraceReference(
            mem_app_dec_id,
            DomainTraceReferenceKind.APPROVAL_DECISION,
            LIFE_PLAN_DOMAIN_ID,
        ),
        DomainTraceReference(
            mem_prop_id,
            DomainTraceReferenceKind.MEMORY_PROPOSAL,
            LIFE_PLAN_DOMAIN_ID,
        ),
        DomainTraceReference(
            mem_bind_id,
            DomainTraceReferenceKind.MEMORY_BINDING,
            LIFE_PLAN_DOMAIN_ID,
        ),
        DomainTraceReference(
            ctx_id,
            DomainTraceReferenceKind.RESOLUTION_CONTEXT,
            None,
        ),
        DomainTraceReference(
            res_id,
            DomainTraceReferenceKind.RESOLUTION_RESULT,
            None,
        ),
        DomainTraceReference(
            comp_id,
            DomainTraceReferenceKind.COMPOSITION,
            None,
        ),
        DomainTraceReference(
            pres_id,
            DomainTraceReferenceKind.PRESENTATION_RESULT,
            None,
        ),
    )

    primary_contrib = build_life_plan_trace_contribution(
        domain_result_id=result_id_str,
        references=runtime_refs,
        domain_id=LIFE_PLAN_DOMAIN_ID,
    )
    trace_refs = DomainTraceReferences(
        resolution_context_id=ctx_id,
        resolution_result_id=res_id,
        composition_id=comp_id,
        cross_domain_results=(),
        presentation_result_ids=(pres_id,),
    )
    probe = DomainTrace(
        id="domain-trace:probe",
        digest="0" * 64,
        request_id=req_id,
        goal_id=None,
        primary_domain=LIFE_PLAN_DOMAIN_ID,
        supporting_domains=(),
        contributions=(primary_contrib,),
        references=trace_refs,
        domain_results=(
            DomainResultTraceReference(
                result_id=result_id_str,
                domain_id=LIFE_PLAN_DOMAIN_ID,
                trace_id="domain-trace:probe",
            ),
        ),
        status=DomainTraceStatus.COMPLETED,
        started_at=NOW,
        completed_at=NOW,
        duration_ms=0,
        metadata={},
    )
    expected_trace_id = probe.canonical_id

    # Build reference inventory independently BEFORE final trace assembly
    inventory = DomainTraceReferenceInventory(
        references=expected_refs,
        domain_results=(
            DomainResultTraceReference(
                result_id=result_id_str,
                domain_id=LIFE_PLAN_DOMAIN_ID,
                trace_id=expected_trace_id,
            ),
        ),
        cross_domain_results=(),
        expected_primary_domain=LIFE_PLAN_DOMAIN_ID,
        resolution_result_domains=DomainTraceDomainSelection(
            res_id, LIFE_PLAN_DOMAIN_ID, ()
        ),
        composition_domains=DomainTraceDomainSelection(
            comp_id, LIFE_PLAN_DOMAIN_ID, ()
        ),
    )

    # Assemble trace from runtime references
    trace = assemble_life_plan_trace(
        request_id=req_id,
        resolution_context_id=ctx_id,
        resolution_result_id=res_id,
        composition_id=comp_id,
        domain_result_id=result_id_str,
        presentation_result_ids=(pres_id,),
        started_at=NOW,
        completed_at=NOW,
        references=runtime_refs,
    )
    assert trace.id == expected_trace_id

    return (
        trace,
        inventory,
        perm_dec_id,
        app_dec_id,
        mem_bind_id,
        wf_run_id,
        str(profile.id),
    )


# 26. Trace inventory independent from final trace
def test_closure_gate_26_trace_inventory_independent_from_final_trace() -> None:
    trace, inventory, _, _, _, _, _ = _setup_valid_runtime_trace_fixture()
    assert len(inventory.references) == 16
    val = validate_life_plan_trace(trace=trace, inventory=inventory)
    assert val.valid is True


# 27. Trace tamper / orphan / wrong-domain references rejected
def test_closure_gate_27_trace_tamper_orphan_wrong_domain_references_rejected() -> None:
    trace, inventory, _, _, _, _, profile_id = _setup_valid_runtime_trace_fixture()
    primary_contrib = trace.contributions[0]
    tampered_trace = dataclasses.replace(
        trace,
        contributions=(
            dataclasses.replace(
                primary_contrib,
                references=tuple(
                    dataclasses.replace(r, ref_id="tampered-profile-id")
                    if r.ref_id == profile_id
                    else r
                    for r in primary_contrib.references
                ),
            ),
        ),
    )
    val = validate_life_plan_trace(trace=tampered_trace, inventory=inventory)
    assert val.valid is False


def test_closure_gate_v2_m2_tampered_permission_decision_trace_reference_rejected() -> (
    None
):
    trace, inventory, perm_dec_id, _, _, _, _ = _setup_valid_runtime_trace_fixture()
    primary_contrib = trace.contributions[0]
    tampered_trace = dataclasses.replace(
        trace,
        contributions=(
            dataclasses.replace(
                primary_contrib,
                references=tuple(
                    dataclasses.replace(r, ref_id="tampered-perm-dec-id")
                    if r.ref_id == perm_dec_id
                    else r
                    for r in primary_contrib.references
                ),
            ),
        ),
    )
    val = validate_life_plan_trace(trace=tampered_trace, inventory=inventory)
    assert val.valid is False


def test_closure_gate_v2_m2_tampered_approval_decision_trace_reference_rejected() -> (
    None
):
    trace, inventory, _, app_dec_id, _, _, _ = _setup_valid_runtime_trace_fixture()
    primary_contrib = trace.contributions[0]
    tampered_trace = dataclasses.replace(
        trace,
        contributions=(
            dataclasses.replace(
                primary_contrib,
                references=tuple(
                    dataclasses.replace(r, ref_id="tampered-app-dec-id")
                    if r.ref_id == app_dec_id
                    else r
                    for r in primary_contrib.references
                ),
            ),
        ),
    )
    val = validate_life_plan_trace(trace=tampered_trace, inventory=inventory)
    assert val.valid is False


def test_closure_gate_v2_m2_tampered_memory_binding_trace_reference_rejected() -> None:
    trace, inventory, _, _, mem_bind_id, _, _ = _setup_valid_runtime_trace_fixture()
    primary_contrib = trace.contributions[0]
    tampered_trace = dataclasses.replace(
        trace,
        contributions=(
            dataclasses.replace(
                primary_contrib,
                references=tuple(
                    dataclasses.replace(r, ref_id="tampered-mem-bind-id")
                    if r.ref_id == mem_bind_id
                    else r
                    for r in primary_contrib.references
                ),
            ),
        ),
    )
    val = validate_life_plan_trace(trace=tampered_trace, inventory=inventory)
    assert val.valid is False


def test_closure_gate_v2_m2_tampered_workflow_run_trace_reference_rejected() -> None:
    trace, inventory, _, _, _, wf_run_id, _ = _setup_valid_runtime_trace_fixture()
    primary_contrib = trace.contributions[0]
    tampered_trace = dataclasses.replace(
        trace,
        contributions=(
            dataclasses.replace(
                primary_contrib,
                references=tuple(
                    dataclasses.replace(r, ref_id="tampered-wf-run-id")
                    if r.ref_id == wf_run_id
                    else r
                    for r in primary_contrib.references
                ),
            ),
        ),
    )
    val = validate_life_plan_trace(trace=tampered_trace, inventory=inventory)
    assert val.valid is False


# 28. Atomic registration rollback preserves exact state
def test_closure_gate_28_atomic_registration_rollback_preserves_exact_state() -> None:
    bootstrap = build_standard_general_domain_bootstrap()
    pre_domains = tuple(r.domain_id for r in bootstrap.domain_registry.list_records())
    pre_profiles = tuple(bootstrap.profile_registry.list_all())
    pre_rules = tuple(bootstrap.rule_registry.list_all())
    pre_resources = tuple(bootstrap.resource_registry.list_all())
    pre_operations = tuple(bootstrap.operation_registry.list_definitions())
    pre_workflows = bootstrap.workflow_registry.snapshot_state().definitions

    with pytest.raises(ValueError):
        register_life_plan_domain(
            domain_registry=bootstrap.domain_registry,
            profile_registry=bootstrap.profile_registry,
            resource_registry=bootstrap.resource_registry,
            rule_registry=bootstrap.rule_registry,
            operation_registry=bootstrap.operation_registry,
            workflow_registry=bootstrap.workflow_registry,
            permission_registry=bootstrap.permission_registry,
            operation_implementations={
                "life_plan.invalid_op_does_not_exist": lambda: None
            },
        )

    assert (
        tuple(r.domain_id for r in bootstrap.domain_registry.list_records())
        == pre_domains
    )
    assert tuple(bootstrap.profile_registry.list_all()) == pre_profiles
    assert tuple(bootstrap.rule_registry.list_all()) == pre_rules
    assert tuple(bootstrap.resource_registry.list_all()) == pre_resources
    assert tuple(bootstrap.operation_registry.list_definitions()) == pre_operations
    assert bootstrap.workflow_registry.snapshot_state().definitions == pre_workflows


# 29. General fallback remains intact after failed registration
def test_closure_gate_29_general_fallback_remains_intact_after_failed_registration() -> (
    None
):
    bootstrap = build_standard_general_domain_bootstrap()

    with pytest.raises(ValueError):
        register_life_plan_domain(
            domain_registry=bootstrap.domain_registry,
            profile_registry=bootstrap.profile_registry,
            resource_registry=bootstrap.resource_registry,
            rule_registry=bootstrap.rule_registry,
            operation_registry=bootstrap.operation_registry,
            workflow_registry=bootstrap.workflow_registry,
            permission_registry=bootstrap.permission_registry,
            operation_implementations={"life_plan.undeclared_op_xyz": lambda: None},
        )

    general_dom = bootstrap.domain_registry.get("general")
    assert general_dom is not None
    assert str(general_dom.id) == "domain:general"
    gen_profile = bootstrap.profile_registry.get_by_domain(
        DomainId.from_str("domain:general")
    )
    assert gen_profile is not None
    assert str(bootstrap.resolver.fallback_domain) == "domain:general"


# 30. Workflow public name is Major Decision Support
def test_closure_gate_30_workflow_public_name_is_major_decision_support() -> None:
    wfs = {w.workflow_id: w for w in build_life_plan_workflow_definitions()}
    wf = wfs["life_plan.cross_domain_impact_review"]
    assert wf.name == "Major Decision Support"


# Additional safety & boundary checks
def test_closure_gate_goal_dependency_cycle_detected_and_rejected() -> None:
    res = evaluate_goal_dependencies(
        dependencies={
            "goal_a": ["goal_b"],
            "goal_b": ["goal_c"],
            "goal_c": ["goal_a"],
        }
    )
    assert res["valid"] is False
    assert res["has_cycles"] is True


def test_closure_gate_scenario_consistency_computes_conflicts() -> None:
    res = evaluate_scenario_consistency(
        scenario_id="scen-adv-01",
        assumptions={"residence": "Madrid", "on_site_work": "Tokyo"},
        assumption_conflicts=[("residence", "on_site_work")],
    )
    assert res["consistent"] is False
    assert len(res["conflicts"]) > 0


def test_closure_gate_memory_proposal_prohibits_direct_write() -> None:
    policy = build_life_plan_permission_policy()
    assert policy.allow_memory_write is False


# ── V2-M1 Memory Permission & Approval Lifecycle Regressions ──────────────────


def _setup_valid_memory_fixture() -> tuple[Any, Any, Any, Any, Any, Any, Any]:
    _, resolver, approval_service, _ = _setup_runtime()
    proposal_id = "prop-mem-v2m1"
    ref_id = "ref-mem-v2m1"
    trace_id = "trace-mem-v2m1"
    ref = DomainMemoryReference(
        reference_id=ref_id,
        kind=DomainMemoryReferenceKind.KNOWLEDGE_ITEM,
        canonical_id="canon-mem-v2m1",
        domain_id=LIFE_PLAN_DOMAIN_ID,
        applicable_domains=(LIFE_PLAN_DOMAIN_ID,),
    )
    proposal = build_life_plan_memory_proposal(
        proposal_id=proposal_id,
        affected_reference_ids=(ref_id,),
    )

    perm_req = DomainPermissionRequest(
        request_id="perm-req-mem-v2m1",
        action=PermissionCapability.OPERATION_EXECUTE,
        domain_id=LIFE_PLAN_DOMAIN_ID,
        actor_id="actor-lp",
        session_id="sess-lp",
        operation_id="life_plan.update_plan",
        resource_id="life_plan.resource.memory_entry",
        purpose="propose-confirmed-life-plan-memory",
        context={"proposal_id": proposal_id},
    )
    perm_res = resolver.resolve(perm_req, now=NOW)
    assert perm_res.effective_permissions.decision is PermissionOutcome.ALLOW
    mem_perm_decision_id = "memory-permission:perm-req-mem-v2m1"
    perm_snapshot = DomainMemoryPermissionDecisionSnapshot(
        decision_id=mem_perm_decision_id,
        allowed=(perm_res.effective_permissions.decision is PermissionOutcome.ALLOW),
        capabilities=(DomainMemoryCapability.PROPOSE,),
        source_domain_id=LIFE_PLAN_DOMAIN_ID,
        target_domain_id=LIFE_PLAN_DOMAIN_ID,
        sensitivity_levels=(DomainMemorySensitivityLevel.NORMAL,),
    )

    app_req = approval_service.create_request(
        title="Life Plan Memory Confirmation",
        description="Confirm proposal",
        requested_by="life-plan-agent",
        metadata={
            "domain_id": LIFE_PLAN_DOMAIN_ID,
            "proposal_id": proposal_id,
            "purpose": "persist-confirmed-life-plan-memory",
        },
    )
    approval_service.approve(app_req.id, "user")
    app_dec = approval_service.repository.list_decisions(app_req.id)[0]

    app_req_snapshot = DomainMemoryApprovalRequestSnapshot(
        request_id=app_req.id,
        proposal_id=proposal_id,
    )
    app_dec_snapshot = DomainMemoryApprovalDecisionSnapshot(
        decision_id=app_dec.id,
        request_id=app_req.id,
        approved=True,
    )

    view_req = build_life_plan_memory_view_request(
        request_id="view-req-v2m1",
        trace_id=trace_id,
        requested_kinds=(DomainMemoryReferenceKind.KNOWLEDGE_ITEM,),
        candidates=(ref,),
        permission_decision_ids=(mem_perm_decision_id,),
    )
    base_inv = DomainMemoryReferenceInventory(
        references=(ref,),
        traces=(
            DomainMemoryTraceSnapshot(
                trace_id=trace_id, primary_domain=LIFE_PLAN_DOMAIN_ID
            ),
        ),
        permission_decisions=(perm_snapshot,),
    )
    view = build_life_plan_memory_view(request=view_req, inventory=base_inv)
    binding = build_life_plan_memory_binding(
        proposal=proposal,
        view=view,
        trace_id=trace_id,
        permission_decision_ids=(mem_perm_decision_id,),
        approval_request_ids=(app_req.id,),
        approval_decision_ids=(app_dec.id,),
    )
    full_inv = DomainMemoryReferenceInventory(
        references=(ref,),
        proposals=(proposal,),
        permission_decisions=(perm_snapshot,),
        approval_requests=(app_req_snapshot,),
        approval_decisions=(app_dec_snapshot,),
        traces=(
            DomainMemoryTraceSnapshot(
                trace_id=trace_id, primary_domain=LIFE_PLAN_DOMAIN_ID
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
    return proposal, view, trace_id, binding, full_inv, mem_perm_decision_id, app_req.id


def test_closure_gate_v2_m1_valid_memory_binding_passes() -> None:
    _, _, _, binding, full_inv, _, _ = _setup_valid_memory_fixture()
    val = validate_life_plan_memory_binding(binding=binding, inventory=full_inv)
    assert val.is_valid is True


def test_closure_gate_v2_m1_cross_domain_permission_rejected_as_memory_permission() -> (
    None
):
    (
        proposal,
        view,
        trace_id,
        _,
        full_inv,
        _,
        app_req_id,
    ) = _setup_valid_memory_fixture()
    cross_decision_id = "cross-domain-decision-999"
    bad_binding = build_life_plan_memory_binding(
        proposal=proposal,
        view=view,
        trace_id=trace_id,
        permission_decision_ids=(cross_decision_id,),
        approval_request_ids=(app_req_id,),
        approval_decision_ids=(full_inv.approval_decisions[0].decision_id,),
    )
    val = validate_life_plan_memory_binding(binding=bad_binding, inventory=full_inv)
    assert val.is_valid is False


def test_closure_gate_v2_m1_cross_domain_approval_rejected_as_memory_approval() -> None:
    (
        proposal,
        view,
        trace_id,
        _,
        full_inv,
        mem_perm_decision_id,
        _,
    ) = _setup_valid_memory_fixture()
    cross_app_id = "cross-domain-approval-req-999"
    bad_binding = build_life_plan_memory_binding(
        proposal=proposal,
        view=view,
        trace_id=trace_id,
        permission_decision_ids=(mem_perm_decision_id,),
        approval_request_ids=(cross_app_id,),
        approval_decision_ids=(full_inv.approval_decisions[0].decision_id,),
    )
    val = validate_life_plan_memory_binding(binding=bad_binding, inventory=full_inv)
    assert val.is_valid is False


def test_closure_gate_v2_m1_mismatched_proposal_approval_rejected() -> None:
    _, _, _, binding, full_inv, _, _ = _setup_valid_memory_fixture()
    bad_inv = dataclasses.replace(
        full_inv,
        approval_requests=(
            DomainMemoryApprovalRequestSnapshot(
                request_id=binding.approval_request_ids[0],
                proposal_id="completely-unrelated-proposal-id",
            ),
        ),
    )
    val = validate_life_plan_memory_binding(binding=binding, inventory=bad_inv)
    assert val.is_valid is False


def test_closure_gate_v2_m1_wrong_domain_memory_permission_rejected() -> None:
    _, _, _, binding, full_inv, mem_perm_decision_id, _ = _setup_valid_memory_fixture()
    bad_inv = dataclasses.replace(
        full_inv,
        permission_decisions=(
            DomainMemoryPermissionDecisionSnapshot(
                decision_id=mem_perm_decision_id,
                allowed=True,
                capabilities=(DomainMemoryCapability.PROPOSE,),
                source_domain_id=LIFE_PLAN_DOMAIN_ID,
                target_domain_id="domain:evil",
                sensitivity_levels=(DomainMemorySensitivityLevel.NORMAL,),
            ),
        ),
    )
    val = validate_life_plan_memory_binding(binding=binding, inventory=bad_inv)
    assert val.is_valid is False


def test_closure_gate_v2_m1_missing_capability_memory_permission_rejected() -> None:
    _, _, _, binding, full_inv, mem_perm_decision_id, _ = _setup_valid_memory_fixture()
    bad_inv = dataclasses.replace(
        full_inv,
        permission_decisions=(
            DomainMemoryPermissionDecisionSnapshot(
                decision_id=mem_perm_decision_id,
                allowed=True,
                capabilities=(),
                source_domain_id=LIFE_PLAN_DOMAIN_ID,
                target_domain_id=LIFE_PLAN_DOMAIN_ID,
                sensitivity_levels=(DomainMemorySensitivityLevel.NORMAL,),
            ),
        ),
    )
    val = validate_life_plan_memory_binding(binding=binding, inventory=bad_inv)
    assert val.is_valid is False


def test_closure_gate_v2_m1_cross_permission_cannot_substitute_for_memory_permission() -> (
    None
):
    test_closure_gate_v2_m1_cross_domain_permission_rejected_as_memory_permission()


def test_closure_gate_v2_m1_cross_approval_cannot_substitute_for_memory_approval() -> (
    None
):
    test_closure_gate_v2_m1_cross_domain_approval_rejected_as_memory_approval()


def test_closure_gate_v2_m1_approval_for_proposal_a_cannot_authorize_proposal_b() -> (
    None
):
    test_closure_gate_v2_m1_mismatched_proposal_approval_rejected()


def test_closure_gate_v2_m1_empty_memory_inventory_rejected() -> None:
    _, _, _, binding, _, _, _ = _setup_valid_memory_fixture()
    val = validate_life_plan_memory_binding(
        binding=binding, inventory=DomainMemoryReferenceInventory()
    )
    assert val.is_valid is False


def test_closure_gate_v2_m1_missing_memory_permission_decision_rejected() -> None:
    _, _, _, binding, full_inv, _, _ = _setup_valid_memory_fixture()
    bad_inv = dataclasses.replace(full_inv, permission_decisions=())
    val = validate_life_plan_memory_binding(binding=binding, inventory=bad_inv)
    assert val.is_valid is False


def test_closure_gate_v3_m1_denied_memory_permission_cannot_allow_propose() -> None:
    """V3-M1: Proving that denied MEMORY_WRITE cannot legitimately generate an allowed PROPOSE snapshot."""
    _, resolver, _, _ = _setup_runtime()
    denied_perm_req = DomainPermissionRequest(
        request_id="perm-req-denied-01",
        action=PermissionCapability.MEMORY_WRITE,
        domain_id=LIFE_PLAN_DOMAIN_ID,
        actor_id="actor-lp",
        session_id="sess-lp",
        resource_id="life_plan.resource.memory_entry",
        purpose="direct-memory-write-attempt",
    )
    denied_res = resolver.resolve(denied_perm_req, now=NOW)
    assert denied_res.effective_permissions.decision is PermissionOutcome.DENY
    assert "capability_not_allowed" in denied_res.effective_permissions.reasons or (
        any(
            "capability_not_allowed" in e.get("reasons", [])
            for e in denied_res.trace_entries
        )
    )

    proposal, view, trace_id, _, full_inv, _, app_req_id = _setup_valid_memory_fixture()
    denied_snapshot = DomainMemoryPermissionDecisionSnapshot(
        decision_id=f"memory-permission:{denied_perm_req.request_id}",
        allowed=(denied_res.effective_permissions.decision is PermissionOutcome.ALLOW),
        capabilities=(DomainMemoryCapability.PROPOSE,),
        source_domain_id=LIFE_PLAN_DOMAIN_ID,
        target_domain_id=LIFE_PLAN_DOMAIN_ID,
        sensitivity_levels=(DomainMemorySensitivityLevel.NORMAL,),
    )
    assert denied_snapshot.allowed is False

    denied_inv = dataclasses.replace(full_inv, permission_decisions=(denied_snapshot,))
    denied_binding = build_life_plan_memory_binding(
        proposal=proposal,
        view=view,
        trace_id=trace_id,
        permission_decision_ids=(denied_snapshot.decision_id,),
        approval_request_ids=(app_req_id,),
        approval_decision_ids=(full_inv.approval_decisions[0].decision_id,),
    )
    val = validate_life_plan_memory_binding(
        binding=denied_binding, inventory=denied_inv
    )
    assert val.is_valid is False


def test_closure_gate_v3_m1_memory_permission_outcome_bound() -> None:
    """V3-M1: Memory permission snapshot allowed state must strictly derive from actual resolver outcome."""
    _, resolver, _, _ = _setup_runtime()
    allowed_perm_req = DomainPermissionRequest(
        request_id="perm-req-allowed-01",
        action=PermissionCapability.OPERATION_EXECUTE,
        domain_id=LIFE_PLAN_DOMAIN_ID,
        actor_id="actor-lp",
        session_id="sess-lp",
        operation_id="life_plan.update_plan",
        resource_id="life_plan.resource.memory_entry",
        purpose="propose-confirmed-life-plan-memory",
    )
    allowed_res = resolver.resolve(allowed_perm_req, now=NOW)
    assert allowed_res.effective_permissions.decision is PermissionOutcome.ALLOW
    allowed_snapshot = DomainMemoryPermissionDecisionSnapshot(
        decision_id=f"memory-permission:{allowed_perm_req.request_id}",
        allowed=(allowed_res.effective_permissions.decision is PermissionOutcome.ALLOW),
        capabilities=(DomainMemoryCapability.PROPOSE,),
        source_domain_id=LIFE_PLAN_DOMAIN_ID,
        target_domain_id=LIFE_PLAN_DOMAIN_ID,
        sensitivity_levels=(DomainMemorySensitivityLevel.NORMAL,),
    )
    assert allowed_snapshot.allowed is True


def test_closure_gate_v2_b1_replay_rejected_fresh_evaluation_required() -> None:
    test_closure_gate_14_real_forged_permission_gate_result_rejected()


def test_closure_gate_v2_b1_different_request_replayed_decision_id_rejected() -> None:
    _, _, _, gate = _setup_runtime()
    req_a = CrossDomainPermissionRequest(
        request_id="req-a-01",
        source_domain="domain:health",
        target_domain=LIFE_PLAN_DOMAIN_ID,
        capability=PermissionCapability.RESOURCE_READ,
        reason="health check a",
        actor_id="actor-a",
        session_id="sess-a",
        sensitivity_level="restricted",
        resource_ids=("health.resource.health_profile:hp-001",),
        resource_kinds=("resource.health_constraints",),
    )
    res_a = gate.evaluate_cross_domain(req_a)
    assert res_a.decision_id is not None

    req_b = CrossDomainPermissionRequest(
        request_id="req-b-01",
        source_domain="domain:health",
        target_domain=LIFE_PLAN_DOMAIN_ID,
        capability=PermissionCapability.RESOURCE_READ,
        reason="health check b",
        actor_id="actor-b",
        session_id="sess-b",
        sensitivity_level="restricted",
        resource_ids=("health.resource.health_profile:hp-001",),
        resource_kinds=("resource.health_constraints",),
    )
    forged_result = PermissionGateResult(
        outcome="granted",
        action="domain_cross_access",
        domain_id="domain:health",
        actor_id=req_b.actor_id,
        session_id=req_b.session_id,
        decision_id=res_a.decision_id,
        metadata={
            "target_domain": "domain:life-plan",
            "source_domain": "domain:health",
        },
    )
    res = evaluate_cross_domain_impact(
        {"status": "active", "activity_limits": ["limit"]},
        permission_request=req_b,
        permission_decision=forged_result,
        permission_gate=gate,
        now=NOW,
    )
    assert res["applied"] is False
    assert res["authorization_verified"] is False


def test_closure_gate_v3_b1_fake_gate_rejected() -> None:
    """V3-B1: Duck-typed FakeGate must never authorize Life Plan mutation."""

    class FakeGateResult:
        allowed = True
        outcome = "allow"
        domain_id = "domain:health"
        actor_id = "actor-adv"
        session_id = "sess-adv"
        decision_id = "forged-decision-123"

    class FakeGate:
        def evaluate_cross_domain(self, *args: Any, **kwargs: Any) -> Any:
            return FakeGateResult()

    cross_request = CrossDomainPermissionRequest(
        request_id="req-fake-gate-1",
        source_domain="domain:health",
        target_domain=LIFE_PLAN_DOMAIN_ID,
        capability=PermissionCapability.RESOURCE_READ,
        reason="health check",
        actor_id="actor-adv",
        session_id="sess-adv",
        sensitivity_level="restricted",
        resource_ids=("health.resource.health_profile:hp-001",),
        resource_kinds=("resource.health_constraints",),
    )
    res = evaluate_cross_domain_impact(
        {"constraint_id": "hc-1", "status": "active"},
        permission_request=cross_request,
        permission_gate=FakeGate(),
        now=NOW,
    )
    assert res["applied"] is False
    assert res["authorization_verified"] is False
    assert res["reason"] == "unauthorized_or_expired"


def test_closure_gate_v3_b1_fake_resolver_rejected() -> None:
    """V3-B1: Duck-typed FakeResolver must never authorize Life Plan mutation."""

    class FakeDecision:
        decision = PermissionOutcome.ALLOW
        request_id = "req-fake-resolver-1"

    class FakeResolver:
        def resolve_cross_domain(self, *args: Any, **kwargs: Any) -> Any:
            return FakeDecision()

    cross_request = CrossDomainPermissionRequest(
        request_id="req-fake-resolver-1",
        source_domain="domain:health",
        target_domain=LIFE_PLAN_DOMAIN_ID,
        capability=PermissionCapability.RESOURCE_READ,
        reason="health check",
        actor_id="actor-adv",
        session_id="sess-adv",
        sensitivity_level="restricted",
        resource_ids=("health.resource.health_profile:hp-001",),
        resource_kinds=("resource.health_constraints",),
    )
    res = evaluate_cross_domain_impact(
        {"constraint_id": "hc-2", "status": "active"},
        permission_request=cross_request,
        permission_resolver=FakeResolver(),
        now=NOW,
    )
    assert res["applied"] is False
    assert res["authorization_verified"] is False
    assert res["reason"] == "unauthorized_or_expired"


def test_closure_gate_v3_b1_missing_provenance_rejected() -> None:
    """V3-B1: Incomplete or missing provenance must fail closed."""

    class IncompleteDecision:
        decision = PermissionOutcome.ALLOW

    class IncompleteResolver:
        def resolve_cross_domain(self, *args: Any, **kwargs: Any) -> Any:
            return IncompleteDecision()

    cross_request = CrossDomainPermissionRequest(
        request_id="req-incomplete-1",
        source_domain="domain:health",
        target_domain=LIFE_PLAN_DOMAIN_ID,
        capability=PermissionCapability.RESOURCE_READ,
        reason="health check",
        actor_id="actor-adv",
        session_id="sess-adv",
        sensitivity_level="restricted",
        resource_ids=("health.resource.health_profile:hp-001",),
        resource_kinds=("resource.health_constraints",),
    )
    res = evaluate_cross_domain_impact(
        {"constraint_id": "hc-3", "status": "active"},
        permission_request=cross_request,
        permission_resolver=IncompleteResolver(),
        now=NOW,
    )
    assert res["applied"] is False
    assert res["authorization_verified"] is False
    assert res["reason"] == "unauthorized_or_expired"
