"""Tests for Phase 10.28 Sport Domain Operations."""

from __future__ import annotations

from cmm.agent_runtime.approval_service import ApprovalService
from cmm.domains.sport.catalog import (
    CANONICAL_SPORT_OPERATION_IDS,
)
from cmm.domains.sport.operations import (
    adjust_training_load_result,
    build_sport_operation_definitions,
    create_training_plan_result,
    generate_workout_result,
    identify_risks_result,
    review_progress_result,
    review_recovery_result,
    schedule_sessions_result,
    track_measurements_result,
)
from cmm.domains.sport.rules import evaluate_health_constraint


def test_sport_operation_definitions_canonical_parity() -> None:
    ops = build_sport_operation_definitions()
    assert len(ops) == 8
    assert tuple(op.operation_id for op in ops) == CANONICAL_SPORT_OPERATION_IDS
    assert all(op.domain_id == "domain:sport" for op in ops)


def test_create_training_plan_is_proposal_not_prescription() -> None:
    res = create_training_plan_result(goal="marathon", weeks=12)
    assert res["status"] == "completed"
    assert res["is_proposal"] is True
    assert res["is_medical_prescription"] is False
    assert len(res["plan"]["weeks"]) == 12


def test_review_progress_preserves_insufficient_evidence() -> None:
    res = review_progress_result(completed_workouts=[])
    assert res["status"] == "insufficient_data"
    assert res["is_proposal"] is True


def test_adjust_training_load_respects_health_constraint_and_readiness() -> None:
    import dataclasses
    from datetime import datetime, timezone

    from cmm.agent_runtime.approval_repository import InMemoryApprovalRepository
    from cmm.agent_runtime.domain_permission_contracts import (
        PermissionApprovalRequirement,
        PermissionCapability,
    )
    from cmm.domains.approval_bridge import to_approval_requirement
    from cmm.domains.general.permissions import build_general_permission_policy
    from cmm.domains.health.permissions import build_health_permission_policy
    from cmm.domains.permission_contracts import CrossDomainPermissionRequest
    from cmm.domains.permission_gate import (
        DomainPermissionGate,
        PermissionGateOutcome,
    )
    from cmm.domains.permission_registry import DomainPermissionRegistry
    from cmm.domains.permission_resolution import DomainPermissionResolver
    from cmm.domains.sport import SPORT_DOMAIN_ID, build_sport_permission_policy

    now = datetime(2026, 8, 25, 12, 0, tzinfo=timezone.utc)
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
    gate = DomainPermissionGate(resolver, approval_service, clock=lambda: now)

    cross_request = CrossDomainPermissionRequest(
        request_id="auth-001",
        source_domain="domain:health",
        target_domain=SPORT_DOMAIN_ID,
        capability=PermissionCapability.RESOURCE_READ,
        reason="return-to-training functional constraint",
        actor_id="actor-test",
        session_id="sess-test",
        sensitivity_level="restricted",
        resource_ids=("sport.resource.health_resource:rtt-001",),
        resource_kinds=("resource.health_resource",),
    )
    pending = gate.evaluate_cross_domain(cross_request)
    req_item = PermissionApprovalRequirement.from_dict(pending.approval_requirements[0])
    app_req = approval_service.create_request_from_requirement(
        to_approval_requirement(req_item, agent_run_id="run-1"),
        requested_by="sports-physician",
    )
    approval_service.approve(app_req.id, "sports-physician")
    consumed = gate.evaluate_cross_domain(cross_request, approval_request_id=app_req.id)
    assert consumed.outcome is PermissionGateOutcome.APPROVAL_CONSUMED

    raw_hc = {
        "status": "active",
        "authorization_reference": consumed.decision_id,
        "load_limits": {"reduction_pct": 20},
    }
    vetted_hc = evaluate_health_constraint(
        raw_hc,
        permission_request=cross_request,
        permission_decision=consumed,
        permission_gate=gate,
        now=now,
    )
    res = adjust_training_load_result(
        current_load=150.0,
        readiness_state="ready",
        health_constraint=vetted_hc,
        now=now,
    )
    assert res["status"] == "load_reduced"
    assert res["adjusted_load"] == 120.0
    assert res["constraint_applied"] is True
    assert res["constraint_pending_application"] is False
    assert res["effective_constraints"]["reduction_pct"] == 20

    # 0% reduction -> 150.0
    vetted_zero = evaluate_health_constraint(
        {
            "status": "active",
            "authorization_reference": consumed.decision_id,
            "load_limits": {"reduction_pct": 0},
        },
        permission_request=cross_request,
        permission_decision=consumed,
        permission_gate=gate,
        now=now,
    )
    res_zero = adjust_training_load_result(
        current_load=150.0,
        readiness_state="ready",
        health_constraint=vetted_zero,
        now=now,
    )
    assert res_zero["adjusted_load"] == 150.0
    assert res_zero["constraint_applied"] is True

    # max_load constraint
    vetted_max = evaluate_health_constraint(
        {
            "status": "active",
            "authorization_reference": consumed.decision_id,
            "load_limits": {"max_load": 80},
        },
        permission_request=cross_request,
        permission_decision=consumed,
        permission_gate=gate,
        now=now,
    )
    res_max = adjust_training_load_result(
        current_load=150.0,
        readiness_state="ready",
        health_constraint=vetted_max,
        now=now,
    )
    assert res_max["adjusted_load"] == 80.0
    assert res_max["constraint_applied"] is True
    assert res_max["effective_constraints"]["max_load"] == 80

    # Invalid reduction percentage -> not applied
    vetted_invalid = evaluate_health_constraint(
        {
            "status": "active",
            "authorization_reference": consumed.decision_id,
            "load_limits": {"reduction_pct": -10},
        },
        permission_request=cross_request,
        permission_decision=consumed,
        permission_gate=gate,
        now=now,
    )
    res_invalid = adjust_training_load_result(
        current_load=150.0,
        readiness_state="ready",
        health_constraint=vetted_invalid,
        now=now,
    )
    assert res_invalid["constraint_applied"] is False
    assert res_invalid["adjusted_load"] == 150.0

    # max_intensity does not invent reduction; marks constraint_pending_application=True and preserves value
    vetted_intensity = evaluate_health_constraint(
        {
            "status": "active",
            "authorization_reference": consumed.decision_id,
            "load_limits": {"max_intensity": 0.5},
        },
        permission_request=cross_request,
        permission_decision=consumed,
        permission_gate=gate,
        now=now,
    )
    res_intensity = adjust_training_load_result(
        current_load=150.0,
        readiness_state="ready",
        health_constraint=vetted_intensity,
        now=now,
    )
    assert res_intensity["constraint_applied"] is False
    assert res_intensity["constraint_pending_application"] is True
    assert res_intensity["adjusted_load"] == 150.0
    assert res_intensity["effective_constraints"]["max_intensity"] == 0.5


def test_raw_health_constraint_with_fabricated_authorization_is_not_applied() -> None:
    result = adjust_training_load_result(
        current_load=100.0,
        health_constraint={
            "status": "active",
            "authorization_reference": "totally-fabricated",
            "load_limits": {"reduction_pct": 50},
        },
    )
    assert result["constraint_applied"] is False
    assert result["adjusted_load"] == 100.0


def test_raw_health_constraint_with_fabricated_authorization_cannot_block_workout() -> (
    None
):
    result = generate_workout_result(
        requested_type="high_intensity_plyometrics",
        health_constraint={
            "status": "active",
            "authorization_reference": "fake",
            "activity_limits": ["no_high_impact"],
        },
    )
    assert result["status"] == "generated"
    assert result["workout"] is not None


def test_adjust_training_load_rejects_unvetted_raw_dict_without_authorization() -> None:
    raw_unauthorized = {"status": "active", "load_limits": {"reduction_pct": 20}}
    res = adjust_training_load_result(
        current_load=150.0,
        readiness_state="ready",
        health_constraint=raw_unauthorized,
    )
    assert res["constraint_applied"] is False
    assert res["adjusted_load"] == 150.0


def test_generate_workout_cannot_bypass_blocking_constraint() -> None:
    import dataclasses
    from datetime import datetime, timezone

    from cmm.agent_runtime.approval_repository import InMemoryApprovalRepository
    from cmm.agent_runtime.domain_permission_contracts import (
        PermissionApprovalRequirement,
        PermissionCapability,
    )
    from cmm.domains.approval_bridge import to_approval_requirement
    from cmm.domains.general.permissions import build_general_permission_policy
    from cmm.domains.health.permissions import build_health_permission_policy
    from cmm.domains.permission_contracts import CrossDomainPermissionRequest
    from cmm.domains.permission_gate import (
        DomainPermissionGate,
        PermissionGateOutcome,
    )
    from cmm.domains.permission_registry import DomainPermissionRegistry
    from cmm.domains.permission_resolution import DomainPermissionResolver
    from cmm.domains.sport import SPORT_DOMAIN_ID, build_sport_permission_policy

    now = datetime(2026, 8, 25, 12, 0, tzinfo=timezone.utc)
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
    gate = DomainPermissionGate(resolver, approval_service, clock=lambda: now)

    cross_request = CrossDomainPermissionRequest(
        request_id="auth-002",
        source_domain="domain:health",
        target_domain=SPORT_DOMAIN_ID,
        capability=PermissionCapability.RESOURCE_READ,
        reason="return-to-training functional constraint",
        actor_id="actor-test",
        session_id="sess-test",
        sensitivity_level="restricted",
        resource_ids=("sport.resource.health_resource:rtt-001",),
        resource_kinds=("resource.health_resource",),
    )
    pending = gate.evaluate_cross_domain(cross_request)
    req_item = PermissionApprovalRequirement.from_dict(pending.approval_requirements[0])
    app_req = approval_service.create_request_from_requirement(
        to_approval_requirement(req_item, agent_run_id="run-1"),
        requested_by="sports-physician",
    )
    approval_service.approve(app_req.id, "sports-physician")
    consumed = gate.evaluate_cross_domain(cross_request, approval_request_id=app_req.id)
    assert consumed.outcome is PermissionGateOutcome.APPROVAL_CONSUMED

    blocking_constraint = evaluate_health_constraint(
        {
            "status": "active",
            "authorization_reference": consumed.decision_id,
            "activity_limits": ["no_high_impact"],
        },
        permission_request=cross_request,
        permission_decision=consumed,
        permission_gate=gate,
        now=now,
    )
    res = generate_workout_result(
        requested_type="high_intensity_plyometrics",
        health_constraint=blocking_constraint,
    )
    assert res["status"] == "blocked_by_constraint"
    assert res["workout"] is None


def test_generate_workout_rejects_unauthorized_raw_blocking_dict() -> None:
    raw_blocking = {"status": "active", "activity_limits": ["no_high_impact"]}
    res = generate_workout_result(
        requested_type="high_intensity_plyometrics",
        health_constraint=raw_blocking,
    )
    assert res["status"] == "generated"
    assert res["workout"] is not None


def test_track_measurements_preserves_unit_and_provenance() -> None:
    res = track_measurements_result(
        metric="body_weight",
        value=75.5,
        unit="kg",
        timestamp="2026-08-25T10:00:00Z",
        source="smart_scale",
    )
    assert res["status"] == "tracked"
    assert res["measurement"]["unit"] == "kg"
    assert res["measurement"]["source"] == "smart_scale"


def test_review_recovery_uses_current_evidence() -> None:
    res = review_recovery_result(rest_hours=8.0, fatigue_score=2)
    assert res["readiness_state"] == "ready"
    assert res["is_mutable"] is True


def test_identify_risks_emits_non_diagnostic_signals() -> None:
    res = identify_risks_result(pain_score=6, load_spike=True)
    assert res["is_diagnosis"] is False
    assert res["risk_signal"] in (
        "stop_and_check",
        "reduce_load",
        "request_health_review",
    )


def test_schedule_sessions_creates_proposal_denies_direct_calendar_mutation() -> None:
    # No approval evidence -> proposal pending approval
    res_no_approval = schedule_sessions_result(
        sessions=[{"day": "Monday", "time": "08:00"}],
    )
    assert res_no_approval["status"] == "proposal_pending_approval"
    assert res_no_approval["external_calendar_mutated"] is False
    assert res_no_approval["approval_required"] is True

    # Bare boolean has_approval=True without scoped request/decision ID is rejected
    res_bare_bool = schedule_sessions_result(
        sessions=[{"day": "Monday", "time": "08:00"}],
        has_approval=True,
    )
    assert res_bare_bool["status"] == "proposal_pending_approval"
    assert res_bare_bool["approval_required"] is True

    # Fabricated string IDs without canonical approval service/decision are rejected
    res_fake_ids = schedule_sessions_result(
        sessions=[{"day": "Monday", "time": "08:00"}],
        approval_request_id="fake-req-001",
        approval_decision_id="fake-dec-001",
    )
    assert res_fake_ids["status"] == "proposal_pending_approval"
    assert res_fake_ids.get("approval_granted") is not True

    # Mismatched approval request and decision IDs fail
    approval_svc = ApprovalService()
    req_a = approval_svc.create_request(
        title="Approve Monday Run",
        description="Schedule Monday run",
        operation_id="sport.schedule_sessions",
    )
    approval_svc.approve(req_a.id, "athlete")
    dec_a = approval_svc.repository.list_decisions(req_a.id)[0]

    req_b = approval_svc.create_request(
        title="Approve Tuesday Run",
        description="Schedule Tuesday run",
        operation_id="sport.schedule_sessions",
    )

    res_mismatched = schedule_sessions_result(
        sessions=[{"day": "Monday", "time": "08:00"}],
        approval_request=req_b,
        approval_decision=dec_a,
        approval_service=approval_svc,
    )
    assert res_mismatched["status"] == "proposal_pending_approval"
    assert res_mismatched.get("approval_granted") is not True

    # Wrong operation scope fails
    req_wrong_scope = approval_svc.create_request(
        title="Approve unrelated operation",
        description="Unrelated operation approval",
        operation_id="sport.create_training_plan",
    )
    approval_svc.approve(req_wrong_scope.id, "athlete")
    dec_wrong_scope = approval_svc.repository.list_decisions(req_wrong_scope.id)[0]

    res_wrong_scope = schedule_sessions_result(
        sessions=[{"day": "Monday", "time": "08:00"}],
        approval_request=req_wrong_scope,
        approval_decision=dec_wrong_scope,
        approval_service=approval_svc,
    )
    assert res_wrong_scope["status"] == "proposal_pending_approval"
    assert res_wrong_scope.get("approval_granted") is not True

    # Fake duck-typed approval evidence fails
    class FakeEvidence:
        granted = True
        action = "sport.schedule_sessions"
        request_id = "fake-req"

    res_fake_ev = schedule_sessions_result(
        sessions=[{"day": "Monday", "time": "08:00"}],
        approval_evidence=FakeEvidence(),
        approval_decision_id="fake-dec",
        approval_service=approval_svc,
    )
    assert res_fake_ev["status"] == "proposal_pending_approval"
    assert res_fake_ev.get("approval_granted") is not True

    # Fake duck-typed request/decision objects fail
    class FakeReq:
        id = "req-fake-x"
        operation_id = "sport.schedule_sessions"

    class FakeDec:
        id = "dec-fake-x"
        request_id = "req-fake-x"
        decision = "approve"

    res_fake_objs = schedule_sessions_result(
        sessions=[{"day": "Monday", "time": "08:00"}],
        approval_request=FakeReq(),
        approval_decision=FakeDec(),
        approval_service=approval_svc,
    )
    assert res_fake_objs["status"] == "proposal_pending_approval"
    assert res_fake_objs.get("approval_granted") is not True

    # Real scoped approval evidence succeeds
    res_with_approval = schedule_sessions_result(
        sessions=[{"day": "Monday", "time": "08:00"}],
        approval_request=req_a,
        approval_decision=dec_a,
        approval_service=approval_svc,
    )
    assert res_with_approval["status"] == "ready_for_external_execution"
    assert res_with_approval["approval_granted"] is True
    assert res_with_approval["approval_request_id"] == req_a.id
    assert res_with_approval["approval_decision_id"] == dec_a.id
    assert res_with_approval["external_calendar_mutated"] is False
