"""Permanent Closure Adversarial Regression Gate for Phase 10.28 Sport Domain.

Reproduces and permanently blocks every trust-boundary and safety bypass
discovered across Independent Audits V1, Re-Audit V2, Re-Audit V3, and Re-Audit V4.

Invariants tested:
- TYPE IDENTITY != PROVENANCE: caller-constructed canonical objects do not authorize.
- HEALTH: Trust is resolver/gate-owned; direct dataclass construction, forged envelopes,
  unrelated gate results, and malformed temporal bounds fail closed.
- CALENDAR: ApprovalService is the single trust root; bare objects, unverified gate results,
  and forged IDs fail closed.
- TRACE: Inventory is assembled independently prior to final trace construction; no field
  in inventory reads from final trace.
- STABLE REGRESSIONS: Load semantics, finite overload, measurement trends, memory fail-closed,
  and workflow runtime authority remain frozen.
"""

from __future__ import annotations

import dataclasses
from dataclasses import replace
from datetime import datetime, timezone
from typing import Any

from cmm.agent_runtime.approval_contracts import (
    ApprovalDecision,
    ApprovalDecisionType,
    ApprovalRequest,
)
from cmm.agent_runtime.approval_repository import InMemoryApprovalRepository
from cmm.agent_runtime.approval_service import ApprovalService
from cmm.agent_runtime.domain_permission_contracts import (
    PermissionApprovalRequirement,
    PermissionCapability,
    PermissionOutcome,
)
from cmm.domains.approval_bridge import to_approval_requirement
from cmm.domains.contracts import DomainResult
from cmm.domains.general.permissions import build_general_permission_policy
from cmm.domains.health.permissions import build_health_permission_policy
from cmm.domains.memory_contracts import (
    DomainMemoryCapability,
    DomainMemoryPermissionDecisionSnapshot,
    DomainMemoryReference,
    DomainMemoryReferenceInventory,
    DomainMemoryReferenceKind,
    DomainMemorySensitivityLevel,
    DomainMemoryTraceSnapshot,
)
from cmm.domains.permission_contracts import (
    CrossDomainPermissionDecision,
    CrossDomainPermissionRequest,
)
from cmm.domains.permission_gate import (
    DomainPermissionGate,
    PermissionGateOutcome,
    PermissionGateResult,
)
from cmm.domains.permission_registry import DomainPermissionRegistry
from cmm.domains.permission_resolution import DomainPermissionResolver
from cmm.domains.sport import (
    SPORT_DOMAIN_ID,
    adjust_training_load_result,
    assemble_sport_trace,
    build_sport_memory_binding,
    build_sport_memory_proposal,
    build_sport_memory_view,
    build_sport_memory_view_request,
    build_sport_operation_definitions,
    build_sport_permission_policy,
    build_sport_profile,
    build_sport_trace_contribution,
    build_sport_trace_reference,
    build_sport_workflow_definitions,
    evaluate_health_constraint,
    evaluate_measurement_trend,
    evaluate_progressive_overload,
    schedule_sessions_result,
    track_measurements_result,
    validate_sport_memory_binding,
    validate_sport_trace,
)
from cmm.domains.sport.rules import AuthorizedHealthConstraint
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
from cmm.domains.workflow_contracts import DomainWorkflowContext
from cmm.domains.workflow_execution import DomainWorkflowExecutor
from cmm.workflows.engine import NodeExecution
from cmm.workflows.enums import WorkflowNodeType

NOW = datetime(2026, 8, 25, 12, 0, tzinfo=timezone.utc)


def _setup_permission_and_approval_runtime() -> tuple[
    DomainPermissionRegistry,
    DomainPermissionResolver,
    ApprovalService,
    DomainPermissionGate,
]:
    perm_registry = DomainPermissionRegistry()
    perm_registry.register(build_sport_permission_policy())
    perm_registry.register(build_general_permission_policy())
    health_policy = dataclasses.replace(
        build_health_permission_policy(),
        allow_cross_domain_access=True,
        allowed_target_domains=("domain:sport",),
        allowed_capabilities=(
            PermissionCapability.DOMAIN_CROSS_ACCESS,
            PermissionCapability.RESOURCE_READ,
        ),
        allowed_resource_kinds=("resource.health_resource",),
        allowed_sensitivity_levels=("restricted",),
    )
    perm_registry.register(health_policy)
    approval_service = ApprovalService(InMemoryApprovalRepository())
    resolver = DomainPermissionResolver(perm_registry)
    gate = DomainPermissionGate(resolver, approval_service, clock=lambda: NOW)
    return perm_registry, resolver, approval_service, gate


# ==============================================================================
# 1. Health Authorization Provenance Regressions (V1 - V4)
# ==============================================================================


def test_v1_health_field_leakage_rejected() -> None:
    """V1 regression: clinical dossiers, notes, and medications are stripped/rejected."""
    raw_dossier = {
        "constraint_id": "hc-v1-001",
        "status": "active",
        "full_clinical_history": ["knee_surgery_2024"],
        "medication_list": ["ibuprofen_800mg"],
        "raw_health_memory": {"diagnosis": "acl_tear"},
    }
    res = evaluate_health_constraint(raw_dossier, is_authorized=True, is_current=True)
    assert res["applied"] is False
    assert res["reason"] == "rejected_unauthorized_dossier"


def test_v2_raw_authorization_reference_forgery_fails() -> None:
    """V2 regression: raw dict with authorization_reference string alone cannot authorize."""
    res = evaluate_health_constraint(
        {
            "status": "active",
            "authorization_reference": "forged-auth-ref-999",
            "load_limits": {"reduction_pct": 50},
        }
    )
    assert res["applied"] is False
    assert res["reason"] == "unauthorized_or_expired"


def test_v3_caller_boolean_is_authorized_fails() -> None:
    """V3 regression: is_authorized=True parameter cannot grant authorization."""
    res = evaluate_health_constraint(
        {
            "status": "active",
            "load_limits": {"reduction_pct": 50},
        },
        is_authorized=True,
        is_current=True,
    )
    assert res["applied"] is False
    assert res["reason"] == "unauthorized_or_expired"


def test_v3_fake_duck_typed_permission_object_fails() -> None:
    """V3 regression: fake object with allowed=True attribute cannot authorize."""

    class FakePermission:
        allowed = True
        decision_id = "fake-decision-id"

    res = evaluate_health_constraint(
        {
            "status": "active",
            "load_limits": {"reduction_pct": 50},
        },
        permission_decision=FakePermission(),
    )
    assert res["applied"] is False
    assert res["reason"] == "unauthorized_or_expired"


def test_v3_forged_authorization_verified_envelope_fails_at_operations() -> None:
    """V3 regression: dict with authorization_verified=True cannot affect load operations."""
    forged_envelope = {
        "applied": True,
        "authorization_verified": True,
        "constraint": {
            "status": "active",
            "authorization_reference": "fake-auth",
            "load_limits": {"reduction_pct": 50},
        },
    }
    load_res = adjust_training_load_result(
        current_load=100.0,
        health_constraint=forged_envelope,
    )
    assert load_res["constraint_applied"] is False
    assert load_res["adjusted_load"] == 100.0


def test_v3_expired_constraint_fails() -> None:
    """V3 regression: is_current=False fails closed."""
    res = evaluate_health_constraint(
        {"status": "active", "load_limits": {"reduction_pct": 50}},
        is_current=False,
    )
    assert res["applied"] is False
    assert res["reason"] == "unauthorized_or_expired"


def test_v4_forged_canonical_permission_decision_fails() -> None:
    """V4 regression (B1-A): Manually constructed CrossDomainPermissionDecision(ALLOW) fails without resolver."""
    forged_dec = CrossDomainPermissionDecision(
        request_id="auth.scope.sport_return_to_training",
        decision=PermissionOutcome.ALLOW,
    )
    res = evaluate_health_constraint(
        {
            "constraint_id": "hc-v4-001",
            "status": "active",
            "load_limits": {"reduction_pct": 40},
            "source_reference": "health.ref.001",
        },
        permission_decision=forged_dec,
    )
    assert res["applied"] is False
    assert res["reason"] == "unauthorized_or_expired"


def test_v4_unrelated_permission_gate_result_fails() -> None:
    """V4 regression (B1-B): Caller-constructed / unrelated PermissionGateResult fails."""
    fake_gate_res = PermissionGateResult(
        decision_id="fake-gate-dec",
        outcome=PermissionGateOutcome.ALLOW,
        action="unrelated.action",
        domain_id="domain:other",
        actor_id="actor-fake",
        session_id="sess-fake",
        metadata={},
    )
    res = evaluate_health_constraint(
        {
            "status": "active",
            "load_limits": {"reduction_pct": 40},
        },
        permission_decision=fake_gate_res,
    )
    assert res["applied"] is False
    assert res["reason"] == "unauthorized_or_expired"


def test_v4_directly_constructed_authorized_health_constraint_fails() -> None:
    """V4 regression (B1-C): Manually constructed AuthorizedHealthConstraint cannot affect operations."""
    forged_artifact = AuthorizedHealthConstraint(
        constraint={
            "status": "active",
            "authorization_reference": "fake-auth",
            "load_limits": {"reduction_pct": 60},
        },
        permission_decision_id="fake-dec",
        permission_request_id="fake-req",
        source_domain="domain:health",
        target_domain="domain:sport",
    )
    load_res = adjust_training_load_result(
        current_load=100.0,
        health_constraint=forged_artifact,
    )
    assert load_res["constraint_applied"] is False
    assert load_res["adjusted_load"] == 100.0


def test_v4_malformed_effective_until_fails_closed() -> None:
    """V4 regression (B1-D): Malformed effective_until fails closed, not open."""
    _, _, _, gate = _setup_permission_and_approval_runtime()
    cross_request = CrossDomainPermissionRequest(
        request_id="req-v4-malformed-until",
        source_domain="domain:health",
        target_domain=SPORT_DOMAIN_ID,
        capability=PermissionCapability.RESOURCE_READ,
        reason="return-to-training functional constraint",
        actor_id="actor-1",
        session_id="sess-1",
        sensitivity_level="restricted",
        resource_ids=("sport.resource.health_resource:rtt-001",),
        resource_kinds=("resource.health_resource",),
    )
    res = evaluate_health_constraint(
        {
            "status": "active",
            "effective_until": "not-a-valid-iso-date",
            "load_limits": {"reduction_pct": 30},
        },
        permission_request=cross_request,
        permission_gate=gate,
    )
    assert res["applied"] is False
    assert res["reason"] == "unauthorized_or_expired"


def test_v4_malformed_effective_from_fails_closed() -> None:
    """V4 regression (B1-D): Malformed effective_from fails closed."""
    _, _, _, gate = _setup_permission_and_approval_runtime()
    cross_request = CrossDomainPermissionRequest(
        request_id="req-v4-malformed-from",
        source_domain="domain:health",
        target_domain=SPORT_DOMAIN_ID,
        capability=PermissionCapability.RESOURCE_READ,
        reason="return-to-training functional constraint",
        actor_id="actor-1",
        session_id="sess-1",
        sensitivity_level="restricted",
        resource_ids=("sport.resource.health_resource:rtt-001",),
        resource_kinds=("resource.health_resource",),
    )
    res = evaluate_health_constraint(
        {
            "status": "active",
            "effective_from": "not-a-valid-date",
            "load_limits": {"reduction_pct": 30},
        },
        permission_request=cross_request,
        permission_gate=gate,
    )
    assert res["applied"] is False
    assert res["reason"] == "unauthorized_or_expired"


def test_v4_future_effective_from_fails_closed() -> None:
    """V4 regression: Future effective_from is not yet active and fails closed."""
    _, _, _, gate = _setup_permission_and_approval_runtime()
    cross_request = CrossDomainPermissionRequest(
        request_id="req-v4-future-from",
        source_domain="domain:health",
        target_domain=SPORT_DOMAIN_ID,
        capability=PermissionCapability.RESOURCE_READ,
        reason="return-to-training functional constraint",
        actor_id="actor-1",
        session_id="sess-1",
        sensitivity_level="restricted",
        resource_ids=("sport.resource.health_resource:rtt-001",),
        resource_kinds=("resource.health_resource",),
    )
    res = evaluate_health_constraint(
        {
            "status": "active",
            "effective_from": "2099-01-01T00:00:00Z",
            "load_limits": {"reduction_pct": 30},
        },
        permission_request=cross_request,
        permission_gate=gate,
        now=NOW,
    )
    assert res["applied"] is False
    assert res["reason"] == "unauthorized_or_expired"


def test_v4_expired_effective_until_fails_closed() -> None:
    """V4 regression: Past effective_until is expired and fails closed."""
    _, _, _, gate = _setup_permission_and_approval_runtime()
    cross_request = CrossDomainPermissionRequest(
        request_id="req-v4-past-until",
        source_domain="domain:health",
        target_domain=SPORT_DOMAIN_ID,
        capability=PermissionCapability.RESOURCE_READ,
        reason="return-to-training functional constraint",
        actor_id="actor-1",
        session_id="sess-1",
        sensitivity_level="restricted",
        resource_ids=("sport.resource.health_resource:rtt-001",),
        resource_kinds=("resource.health_resource",),
    )
    res = evaluate_health_constraint(
        {
            "status": "active",
            "effective_until": "2020-01-01T00:00:00Z",
            "load_limits": {"reduction_pct": 30},
        },
        permission_request=cross_request,
        permission_gate=gate,
        now=NOW,
    )
    assert res["applied"] is False
    assert res["reason"] == "unauthorized_or_expired"


def test_health_real_resolver_gate_flow_succeeds() -> None:
    """Real runtime permission resolution + gate approval succeeds and authorizes constraint."""
    _, _, approval_service, gate = _setup_permission_and_approval_runtime()
    cross_request = CrossDomainPermissionRequest(
        request_id="req-real-health-001",
        source_domain="domain:health",
        target_domain=SPORT_DOMAIN_ID,
        capability=PermissionCapability.RESOURCE_READ,
        reason="return-to-training functional constraint",
        actor_id="actor-1",
        session_id="sess-1",
        sensitivity_level="restricted",
        resource_ids=("sport.resource.health_resource:rtt-001",),
        resource_kinds=("resource.health_resource",),
    )
    pending_gate = gate.evaluate_cross_domain(cross_request)
    assert pending_gate.outcome is PermissionGateOutcome.APPROVAL_REQUIRED

    req_item = PermissionApprovalRequirement.from_dict(
        pending_gate.approval_requirements[0]
    )
    approval_req = approval_service.create_request_from_requirement(
        to_approval_requirement(req_item, agent_run_id="run-1"),
        requested_by="physician",
    )
    approval_service.approve(approval_req.id, "sports-physician")

    consumed_gate = gate.evaluate_cross_domain(
        cross_request, approval_request_id=approval_req.id
    )
    assert consumed_gate.outcome is PermissionGateOutcome.APPROVAL_CONSUMED
    assert consumed_gate.allowed is True

    raw_hc = {
        "constraint_id": "hc-real-001",
        "status": "active",
        "activity_limits": ["no_plyometrics"],
        "load_limits": {"reduction_pct": 30},
        "source_reference": "health.ref.101",
        "authorization_reference": consumed_gate.decision_id,
        "diagnosis": "tendinitis",
    }
    hc_eval = evaluate_health_constraint(
        raw_hc,
        permission_request=cross_request,
        permission_decision=consumed_gate,
        permission_gate=gate,
        now=NOW,
    )
    assert hc_eval["applied"] is True
    assert hc_eval["authorization_verified"] is True
    assert "diagnosis" not in hc_eval["constraint"]
    assert hc_eval["constraint"]["load_limits"]["reduction_pct"] == 30

    load_res = adjust_training_load_result(
        current_load=100.0,
        health_constraint=hc_eval,
        now=NOW,
    )
    assert load_res["constraint_applied"] is True
    assert load_res["adjusted_load"] == 70.0


# ==============================================================================
# 2. Calendar Approval Provenance Regressions (V1 - V4)
# ==============================================================================


def test_v1_bare_has_approval_fails() -> None:
    """V1 regression: has_approval=True cannot authorize calendar execution."""
    res = schedule_sessions_result(
        sessions=[{"day": "Monday", "time": "08:00", "type": "easy_run"}],
        has_approval=True,
    )
    assert res["status"] == "proposal_pending_approval"
    assert res["external_calendar_mutated"] is False


def test_v2_fake_approval_id_strings_fail() -> None:
    """V2 regression: fake approval ID strings cannot authorize."""
    res = schedule_sessions_result(
        sessions=[{"day": "Monday", "time": "08:00", "type": "easy_run"}],
        approval_request_id="fake-request-id",
        approval_decision_id="fake-decision-id",
    )
    assert res["status"] == "proposal_pending_approval"


def test_v3_fake_duck_typed_approval_evidence_fails() -> None:
    """V3 regression: duck-typed approval evidence object fails."""

    class FakeApprovalEvidence:
        granted = True
        action = "sport.schedule_sessions"
        request_id = "fake-req"

    res = schedule_sessions_result(
        sessions=[{"day": "Monday", "time": "08:00", "type": "easy_run"}],
        approval_evidence=FakeApprovalEvidence(),
    )
    assert res["status"] == "proposal_pending_approval"


def test_v4_forged_canonical_approval_objects_fail_without_service() -> None:
    """V4 regression (M4-B): Manually constructed ApprovalRequest/Decision fail if not in ApprovalService."""
    forged_req = ApprovalRequest(
        id="req-forged-999",
        title="Forged schedule",
        description="Forged description",
        requested_by="attacker",
        operation_id="sport.schedule_sessions",
    )
    forged_dec = ApprovalDecision(
        id="dec-forged-999",
        request_id="req-forged-999",
        actor_id="attacker",
        decision=ApprovalDecisionType.APPROVE,
    )
    res = schedule_sessions_result(
        sessions=[{"day": "Monday", "time": "08:00", "type": "easy_run"}],
        approval_request=forged_req,
        approval_decision=forged_dec,
    )
    assert res["status"] == "proposal_pending_approval"
    assert res.get("approval_granted") is not True


def test_v4_forged_permission_gate_result_calendar_fails() -> None:
    """V4 regression (M4-A): Manually constructed PermissionGateResult(APPROVAL_CONSUMED) fails without stored approval."""
    fake_gate_res = PermissionGateResult(
        decision_id="fake-gate-approval-consumed",
        outcome=PermissionGateOutcome.APPROVAL_CONSUMED,
        action="sport.schedule_sessions",
        domain_id=SPORT_DOMAIN_ID,
        actor_id="actor-1",
        session_id="sess-1",
        metadata={"operation_id": "sport.schedule_sessions"},
    )
    res = schedule_sessions_result(
        sessions=[{"day": "Monday", "time": "08:00", "type": "easy_run"}],
        approval_evidence=fake_gate_res,
    )
    assert res["status"] == "proposal_pending_approval"
    assert res.get("approval_granted") is not True


def test_v4_mismatched_stored_approval_request_decision_fails() -> None:
    """V4 regression: Stored request paired with decision for a different request fails."""
    approval_service = ApprovalService(InMemoryApprovalRepository())
    req1 = approval_service.create_request(
        title="Schedule 1",
        description="Schedule 1",
        requested_by="athlete",
        operation_id="sport.schedule_sessions",
    )
    req2 = approval_service.create_request(
        title="Schedule 2",
        description="Schedule 2",
        requested_by="athlete",
        operation_id="sport.schedule_sessions",
    )
    approval_service.approve(req2.id, "athlete")
    dec2 = approval_service.repository.list_decisions(req2.id)[0]

    res = schedule_sessions_result(
        sessions=[{"day": "Monday", "time": "08:00", "type": "easy_run"}],
        approval_request=req1,
        approval_decision=dec2,
        approval_service=approval_service,
    )
    assert res["status"] == "proposal_pending_approval"


def test_v4_wrong_scope_stored_approval_fails() -> None:
    """V4 regression: Stored approval for an unrelated operation fails."""
    approval_service = ApprovalService(InMemoryApprovalRepository())
    req = approval_service.create_request(
        title="Delete profile",
        description="Unrelated action",
        requested_by="athlete",
        operation_id="sport.delete_profile",
    )
    approval_service.approve(req.id, "athlete")
    dec = approval_service.repository.list_decisions(req.id)[0]

    res = schedule_sessions_result(
        sessions=[{"day": "Monday", "time": "08:00", "type": "easy_run"}],
        approval_request=req,
        approval_decision=dec,
        approval_service=approval_service,
    )
    assert res["status"] == "proposal_pending_approval"


def test_calendar_real_approval_service_succeeds() -> None:
    """Real stored approval in ApprovalService authorizes calendar readiness."""
    approval_service = ApprovalService(InMemoryApprovalRepository())
    req = approval_service.create_request(
        title="Weekly marathon schedule",
        description="Schedule 3 weekly training sessions",
        requested_by="athlete-scheduler",
        operation_id="sport.schedule_sessions",
    )
    approval_service.approve(req.id, "athlete")
    dec = approval_service.repository.list_decisions(req.id)[0]

    res = schedule_sessions_result(
        sessions=[{"day": "Monday", "time": "08:00", "type": "easy_run"}],
        approval_request=req,
        approval_decision=dec,
        approval_service=approval_service,
    )
    assert res["status"] == "ready_for_external_execution"
    assert res["approval_granted"] is True
    assert res["approval_request_id"] == req.id
    assert res["approval_decision_id"] == dec.id
    assert res["external_calendar_mutated"] is False


# ==============================================================================
# 3. Trace Full Independence Regressions (V1 - V4)
# ==============================================================================


def test_v4_trace_full_independence_construction_order() -> None:
    """V4 regression (M5-B): Trace inventory is constructed independently BEFORE final trace assembly."""
    profile = build_sport_profile()
    domain_result = DomainResult(
        id="result-sport-trace-001",
        status="completed",
        objective="Sport return-to-training",
        primary_domain=SPORT_DOMAIN_ID,
        supporting_domains=("domain:health",),
    )
    domain_result_id = str(domain_result.id)
    request_id = "req-trace-001"
    resolution_ctx_id = "ctx-trace-001"
    resolution_id = "res-trace-001"
    composition_id = "comp-trace-001"
    goal_id = "goal-trace-001"

    ref1 = build_sport_trace_reference(
        ref_id=str(profile.id), kind=DomainTraceReferenceKind.PROFILE
    )
    runtime_refs = (ref1,)

    expected_refs = (
        DomainTraceReference(
            domain_result_id, DomainTraceReferenceKind.DOMAIN_RESULT, SPORT_DOMAIN_ID
        ),
        DomainTraceReference(
            str(profile.id), DomainTraceReferenceKind.PROFILE, SPORT_DOMAIN_ID
        ),
        DomainTraceReference(
            resolution_ctx_id, DomainTraceReferenceKind.RESOLUTION_CONTEXT, None
        ),
        DomainTraceReference(
            resolution_id, DomainTraceReferenceKind.RESOLUTION_RESULT, None
        ),
        DomainTraceReference(
            composition_id, DomainTraceReferenceKind.COMPOSITION, None
        ),
    )

    trace_refs = DomainTraceReferences(
        resolution_context_id=resolution_ctx_id,
        resolution_result_id=resolution_id,
        composition_id=composition_id,
        cross_domain_results=(),
        presentation_result_ids=(),
    )
    probe = DomainTrace(
        id="domain-trace:probe",
        digest="0" * 64,
        request_id=request_id,
        goal_id=goal_id,
        primary_domain=SPORT_DOMAIN_ID,
        supporting_domains=(),
        contributions=(
            build_sport_trace_contribution(
                domain_result_id=domain_result_id,
                references=runtime_refs,
            ),
        ),
        references=trace_refs,
        domain_results=(
            DomainResultTraceReference(
                domain_result_id,
                SPORT_DOMAIN_ID,
                "domain-trace:probe",
            ),
        ),
        status=DomainTraceStatus.COMPLETED,
        started_at=NOW,
        completed_at=NOW,
        duration_ms=0,
        metadata={},
    )
    expected_trace_id = probe.canonical_id

    # Build inventory BEFORE final trace is assembled, using expected_trace_id
    inventory = DomainTraceReferenceInventory(
        references=expected_refs,
        domain_results=(
            DomainResultTraceReference(
                result_id=domain_result_id,
                domain_id=SPORT_DOMAIN_ID,
                trace_id=expected_trace_id,
            ),
        ),
        cross_domain_results=(),
        expected_primary_domain=SPORT_DOMAIN_ID,
        resolution_result_domains=DomainTraceDomainSelection(
            resolution_id, SPORT_DOMAIN_ID, ()
        ),
        composition_domains=DomainTraceDomainSelection(
            composition_id, SPORT_DOMAIN_ID, ()
        ),
    )

    # Assemble trace after inventory is created
    trace = assemble_sport_trace(
        request_id=request_id,
        resolution_context_id=resolution_ctx_id,
        resolution_result_id=resolution_id,
        composition_id=composition_id,
        domain_result_id=domain_result_id,
        started_at=NOW,
        completed_at=NOW,
        references=runtime_refs,
        goal_id=goal_id,
    )
    assert trace.id == expected_trace_id

    val = validate_sport_trace(trace=trace, inventory=inventory)
    assert val.valid is True


def test_trace_fabricated_baseline_reference_fails() -> None:
    """Fabricated reference present in trace but missing from inventory fails."""
    domain_result = DomainResult(
        id="result-trace-fab",
        status="completed",
        objective="Trace test",
        primary_domain=SPORT_DOMAIN_ID,
    )
    domain_result_id = str(domain_result.id)
    profile = build_sport_profile()

    inventory = DomainTraceReferenceInventory(
        references=(
            DomainTraceReference(
                domain_result_id,
                DomainTraceReferenceKind.DOMAIN_RESULT,
                SPORT_DOMAIN_ID,
            ),
            DomainTraceReference(
                str(profile.id), DomainTraceReferenceKind.PROFILE, SPORT_DOMAIN_ID
            ),
            DomainTraceReference(
                "ctx-1", DomainTraceReferenceKind.RESOLUTION_CONTEXT, None
            ),
            DomainTraceReference(
                "res-1", DomainTraceReferenceKind.RESOLUTION_RESULT, None
            ),
            DomainTraceReference("comp-1", DomainTraceReferenceKind.COMPOSITION, None),
        ),
        domain_results=(
            DomainResultTraceReference(
                result_id=domain_result_id,
                domain_id=SPORT_DOMAIN_ID,
                trace_id="any",
            ),
        ),
        expected_primary_domain=SPORT_DOMAIN_ID,
        resolution_result_domains=DomainTraceDomainSelection(
            "res-1", SPORT_DOMAIN_ID, ()
        ),
        composition_domains=DomainTraceDomainSelection("comp-1", SPORT_DOMAIN_ID, ()),
    )

    fabricated_trace = assemble_sport_trace(
        request_id="req-1",
        resolution_context_id="ctx-1",
        resolution_result_id="res-1",
        composition_id="comp-1",
        domain_result_id=domain_result_id,
        started_at=NOW,
        completed_at=NOW,
        references=(
            build_sport_trace_reference(
                ref_id=str(profile.id), kind=DomainTraceReferenceKind.PROFILE
            ),
            build_sport_trace_reference(
                ref_id="ghost-reference-999", kind=DomainTraceReferenceKind.RULE_RESULT
            ),
        ),
    )
    val = validate_sport_trace(trace=fabricated_trace, inventory=inventory)
    assert val.valid is False
    assert "ghost-reference-999" in val.unexpected_references


def test_trace_post_construction_tamper_fails() -> None:
    """Tampering with trace references after assembly fails inventory validation."""
    domain_result = DomainResult(
        id="result-trace-tamper",
        status="completed",
        objective="Trace tamper test",
        primary_domain=SPORT_DOMAIN_ID,
    )
    domain_result_id = str(domain_result.id)
    profile = build_sport_profile()
    ref1 = build_sport_trace_reference(
        ref_id=str(profile.id), kind=DomainTraceReferenceKind.PROFILE
    )

    trace = assemble_sport_trace(
        request_id="req-1",
        resolution_context_id="ctx-1",
        resolution_result_id="res-1",
        composition_id="comp-1",
        domain_result_id=domain_result_id,
        started_at=NOW,
        completed_at=NOW,
        references=(ref1,),
    )
    inventory = DomainTraceReferenceInventory(
        references=(
            DomainTraceReference(
                domain_result_id,
                DomainTraceReferenceKind.DOMAIN_RESULT,
                SPORT_DOMAIN_ID,
            ),
            DomainTraceReference(
                str(profile.id), DomainTraceReferenceKind.PROFILE, SPORT_DOMAIN_ID
            ),
            DomainTraceReference(
                "ctx-1", DomainTraceReferenceKind.RESOLUTION_CONTEXT, None
            ),
            DomainTraceReference(
                "res-1", DomainTraceReferenceKind.RESOLUTION_RESULT, None
            ),
            DomainTraceReference("comp-1", DomainTraceReferenceKind.COMPOSITION, None),
        ),
        domain_results=(
            DomainResultTraceReference(
                result_id=domain_result_id,
                domain_id=SPORT_DOMAIN_ID,
                trace_id=trace.id,
            ),
        ),
        expected_primary_domain=SPORT_DOMAIN_ID,
        resolution_result_domains=DomainTraceDomainSelection(
            "res-1", SPORT_DOMAIN_ID, ()
        ),
        composition_domains=DomainTraceDomainSelection("comp-1", SPORT_DOMAIN_ID, ()),
    )

    primary_contrib = trace.contributions[0]
    tampered_trace = replace(
        trace,
        contributions=(
            replace(
                primary_contrib,
                references=tuple(
                    replace(r, ref_id="tampered-profile-id")
                    if r.ref_id == str(profile.id)
                    else r
                    for r in primary_contrib.references
                ),
            ),
        ),
    )
    val = validate_sport_trace(trace=tampered_trace, inventory=inventory)
    assert val.valid is False


# ==============================================================================
# 4. Previously Closed Safety Regressions
# ==============================================================================


def test_v1_load_limit_semantics_max_intensity_explicit_pending() -> None:
    """Load limit max_intensity is explicit/pending, not silently converted to load reduction."""
    res = adjust_training_load_result(
        current_load=100.0,
        health_constraint={
            "applied": True,
            "authorization_verified": True,
            "constraint": {
                "status": "active",
                "authorization_reference": "ref-1",
                "load_limits": {"max_intensity": "zone_2"},
            },
        },
    )
    # Without load reduction_pct, load remains unreduced and pending explicit application
    assert res["adjusted_load"] == 100.0


def test_v1_finite_overload_evidence_rejects_nan_inf() -> None:
    """Non-finite baseline or proposed load returns invalid_evidence."""
    res_nan = evaluate_progressive_overload(
        baseline_load=float("nan"), proposed_load=100.0
    )
    assert res_nan["status"] == "invalid_evidence"

    res_inf = evaluate_progressive_overload(
        baseline_load=100.0, proposed_load=float("inf")
    )
    assert res_inf["status"] == "invalid_evidence"


def test_v1_temporal_trend_requires_comparable_ordered_measurements() -> None:
    """Measurement trend derives direction only from multiple comparable ordered observations."""
    m1 = track_measurements_result(
        metric="weight", value=75.0, unit="kg", timestamp="2026-08-01T08:00:00Z"
    )
    m2 = track_measurements_result(
        metric="weight", value=74.0, unit="kg", timestamp="2026-08-08T08:00:00Z"
    )
    m3 = track_measurements_result(
        metric="weight", value=73.0, unit="kg", timestamp="2026-08-15T08:00:00Z"
    )

    # Single observation: insufficient
    single_res = evaluate_measurement_trend([m1["measurement"]], metric="weight")
    assert single_res["status"] == "insufficient_data"

    # Multi observations (even if passed out of order): evaluated correctly
    multi_res = evaluate_measurement_trend(
        [m3["measurement"], m1["measurement"], m2["measurement"]],
        metric="weight",
    )
    assert multi_res["status"] == "evaluated"
    assert multi_res["direction"] == "decreasing"


def test_v1_memory_fail_closed_on_empty_inventory() -> None:
    """Memory binding validation fails closed against empty or invalid inventory."""
    proposal = build_sport_memory_proposal(
        proposal_id="prop-1",
        affected_reference_ids=("ref-1",),
    )
    ref = DomainMemoryReference(
        reference_id="ref-1",
        kind=DomainMemoryReferenceKind.KNOWLEDGE_ITEM,
        canonical_id="canon-1",
        domain_id=SPORT_DOMAIN_ID,
        applicable_domains=(SPORT_DOMAIN_ID,),
        evidence_ids=("ev-1",),
    )
    perm_snapshot = DomainMemoryPermissionDecisionSnapshot(
        decision_id="dec-1",
        allowed=True,
        capabilities=(DomainMemoryCapability.PROPOSE,),
        source_domain_id=SPORT_DOMAIN_ID,
        target_domain_id=SPORT_DOMAIN_ID,
        sensitivity_levels=(DomainMemorySensitivityLevel.NORMAL,),
    )
    view_req = build_sport_memory_view_request(
        request_id="vreq-1",
        trace_id="tr-1",
        requested_kinds=(DomainMemoryReferenceKind.KNOWLEDGE_ITEM,),
        candidates=(ref,),
        permission_decision_ids=("dec-1",),
    )
    inv = DomainMemoryReferenceInventory(
        references=(ref,),
        traces=(
            DomainMemoryTraceSnapshot(trace_id="tr-1", primary_domain=SPORT_DOMAIN_ID),
        ),
        permission_decisions=(perm_snapshot,),
    )
    view = build_sport_memory_view(request=view_req, inventory=inv)
    binding = build_sport_memory_binding(
        proposal=proposal,
        view=view,
        trace_id="tr-1",
        permission_decision_ids=("dec-1",),
    )

    # Empty inventory fails closed
    bad_val = validate_sport_memory_binding(
        binding=binding, inventory=DomainMemoryReferenceInventory()
    )
    assert bad_val.is_valid is False


def test_v2_workflow_runtime_authoritative_output() -> None:
    """M5-A closure: Workflow output is authoritative from DomainWorkflowExecutor."""
    wf_defs = {w.workflow_id: w for w in build_sport_workflow_definitions()}
    rtt_def = wf_defs["sport.return_to_training_with_health_constraints"]

    def op_adapter(node: Any, run: Any) -> NodeExecution:
        if node.node_type == WorkflowNodeType.COMPLETE:
            return NodeExecution.complete(
                {
                    "status": "completed",
                    "workflow_id": "sport.return_to_training_with_health_constraints",
                    "recommendation": "reduce_load",
                    "health_constraint_applied": True,
                    "treatment_modified": False,
                    "clinical_clearance_claimed": False,
                }
            )
        return NodeExecution.complete({"status": "ok"})

    wf_ctx = DomainWorkflowContext(
        primary_domain_id=SPORT_DOMAIN_ID,
        known_domain_ids=frozenset(
            {SPORT_DOMAIN_ID, "domain:general", "domain:health"}
        ),
        authorized_domain_ids=frozenset({SPORT_DOMAIN_ID}),
        available_resources=frozenset(rtt_def.required_resources),
        available_operations=frozenset(
            op.operation_id for op in build_sport_operation_definitions()
        ),
    )
    executor = DomainWorkflowExecutor(
        id_factory=lambda: "wf-id-1",
        clock=lambda: NOW,
        operation_adapter=op_adapter,
    )
    run = executor.execute(rtt_def, wf_ctx, inputs={})
    assert run.common_run.status.value == "completed"
    complete_out = run.execution_result.node_results["complete"].output
    assert complete_out["recommendation"] == "reduce_load"
    assert complete_out["health_constraint_applied"] is True
