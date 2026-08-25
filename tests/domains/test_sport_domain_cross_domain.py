"""Tests for Phase 10.28 Sport <-> Health Cross-Domain Boundary."""

from __future__ import annotations

import dataclasses
from datetime import datetime, timezone
from typing import Any

from cmm.agent_runtime.approval_repository import InMemoryApprovalRepository
from cmm.agent_runtime.approval_service import ApprovalService
from cmm.agent_runtime.domain_permission_contracts import (
    PermissionApprovalRequirement,
    PermissionCapability,
)
from cmm.domains.approval_bridge import to_approval_requirement
from cmm.domains.general.permissions import build_general_permission_policy
from cmm.domains.health.permissions import build_health_permission_policy
from cmm.domains.permission_contracts import CrossDomainPermissionRequest
from cmm.domains.permission_gate import DomainPermissionGate, PermissionGateOutcome
from cmm.domains.permission_registry import DomainPermissionRegistry
from cmm.domains.permission_resolution import DomainPermissionResolver
from cmm.domains.sport import SPORT_DOMAIN_ID, build_sport_permission_policy
from cmm.domains.sport.rules import evaluate_health_constraint
from cmm.domains.sport.workflows import execute_return_to_training_workflow

NOW = datetime(2026, 8, 25, 12, 0, tzinfo=timezone.utc)


def _setup_runtime() -> tuple[
    DomainPermissionRegistry,
    DomainPermissionResolver,
    ApprovalService,
    DomainPermissionGate,
    CrossDomainPermissionRequest,
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

    cross_request = CrossDomainPermissionRequest(
        request_id="auth.scope.sport_return_to_training",
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
    return perm_registry, resolver, approval_service, gate, cross_request


def _get_approved_gate_result(
    gate: DomainPermissionGate,
    approval_service: ApprovalService,
    cross_request: CrossDomainPermissionRequest,
) -> Any:
    pending = gate.evaluate_cross_domain(cross_request)
    req_item = PermissionApprovalRequirement.from_dict(pending.approval_requirements[0])
    app_req = approval_service.create_request_from_requirement(
        to_approval_requirement(req_item, agent_run_id="run-1"),
        requested_by="sports-physician",
    )
    approval_service.approve(app_req.id, "sports-physician")
    consumed = gate.evaluate_cross_domain(cross_request, approval_request_id=app_req.id)
    assert consumed.outcome is PermissionGateOutcome.APPROVAL_CONSUMED
    return consumed


def test_cross_domain_authorized_minimal_projection_only() -> None:
    _, _, approval_service, gate, cross_request = _setup_runtime()
    consumed = _get_approved_gate_result(gate, approval_service, cross_request)

    authorized_projection = {
        "constraint_id": "hc-2026-001",
        "status": "active",
        "activity_limits": ["no_weightbearing_on_right_knee"],
        "load_limits": {"max_hr": 130},
        "source_reference": "health.ref.404",
        "authorization_reference": consumed.decision_id,
    }
    res = evaluate_health_constraint(
        authorized_projection,
        permission_request=cross_request,
        permission_decision=consumed,
        permission_gate=gate,
        now=NOW,
    )
    assert res["applied"] is True
    assert res["provenance"]["authorization_reference"] == consumed.decision_id
    assert res["treatment_modification_allowed"] is False


def test_caller_boolean_health_auth_fails() -> None:
    result = evaluate_health_constraint(
        {
            "status": "active",
            "authorization_reference": "fake-auth",
            "load_limits": {"reduction_pct": 50},
        },
        is_authorized=True,
        is_current=True,
    )
    assert result["applied"] is False
    assert result["reason"] == "unauthorized_or_expired"


def test_fake_permission_object_fails() -> None:
    class FakePermission:
        allowed = True
        decision_id = "fake-decision"

    result = evaluate_health_constraint(
        {
            "status": "active",
            "authorization_reference": "fake",
            "load_limits": {"reduction_pct": 50},
        },
        permission_decision=FakePermission(),
    )
    assert result["applied"] is False
    assert result["reason"] == "unauthorized_or_expired"


def test_forged_verified_envelope_fails_at_operations() -> None:
    from cmm.domains.sport.operations import (
        adjust_training_load_result,
        generate_workout_result,
    )

    forged_envelope = {
        "applied": True,
        "authorization_verified": True,
        "constraint": {
            "status": "active",
            "authorization_reference": "fabricated",
            "load_limits": {"reduction_pct": 60},
        },
    }
    res_load = adjust_training_load_result(
        current_load=100.0,
        health_constraint=forged_envelope,
    )
    assert res_load["constraint_applied"] is False
    assert res_load["adjusted_load"] == 100.0

    res_workout = generate_workout_result(
        requested_type="high_intensity_plyometrics",
        health_constraint={
            "applied": True,
            "authorization_verified": True,
            "constraint": {
                "status": "active",
                "authorization_reference": "fake",
                "activity_limits": ["no_high_impact"],
            },
        },
    )
    assert res_workout["status"] == "generated"
    assert res_workout["workout"] is not None


def test_expired_constraint_fails_from_own_timestamps() -> None:
    _, _, approval_service, gate, cross_request = _setup_runtime()
    consumed = _get_approved_gate_result(gate, approval_service, cross_request)

    expired_proj = {
        "constraint_id": "hc-expired-001",
        "status": "active",
        "effective_from": "2020-01-01T00:00:00+00:00",
        "effective_until": "2020-01-02T00:00:00+00:00",
        "load_limits": {"reduction_pct": 50},
    }
    res = evaluate_health_constraint(
        expired_proj,
        permission_request=cross_request,
        permission_decision=consumed,
        permission_gate=gate,
        now=NOW,
    )
    assert res["applied"] is False
    assert res["reason"] == "unauthorized_or_expired"


def test_cross_domain_denies_full_health_dossier() -> None:
    _, _, approval_service, gate, cross_request = _setup_runtime()
    consumed = _get_approved_gate_result(gate, approval_service, cross_request)

    raw_dossier = {
        "constraint_id": "hc-2026-001",
        "full_clinical_history": ["meniscus_repair_2025", "cortisone_injection"],
        "medication_list": ["ibuprofen_800mg"],
        "raw_health_memory": {"patient_notes": "sensitive detail"},
    }
    res = evaluate_health_constraint(
        raw_dossier,
        permission_request=cross_request,
        permission_decision=consumed,
        permission_gate=gate,
        now=NOW,
    )
    assert res["applied"] is False
    assert res["reason"] == "rejected_unauthorized_dossier"


def test_cross_domain_stale_or_unauthorized_constraint_rejected() -> None:
    valid_projection = {
        "constraint_id": "hc-2026-001",
        "status": "active",
        "activity_limits": ["no_sprinting"],
    }

    # Unauthorized -> rejected
    res_unauth = evaluate_health_constraint(
        valid_projection, is_authorized=False, is_current=True
    )
    assert res_unauth["applied"] is False

    # Expired -> rejected
    res_expired = evaluate_health_constraint(
        valid_projection, is_authorized=True, is_current=False
    )
    assert res_expired["applied"] is False


def test_cross_domain_return_to_training_safety_invariant() -> None:
    _, _, approval_service, gate, cross_request = _setup_runtime()
    consumed = _get_approved_gate_result(gate, approval_service, cross_request)

    health_projection = {
        "constraint_id": "hc-002",
        "status": "active",
        "load_limits": {"max_intensity": 0.5},
        "authorization_reference": consumed.decision_id,
    }
    vetted = evaluate_health_constraint(
        health_projection,
        permission_request=cross_request,
        permission_decision=consumed,
        permission_gate=gate,
        now=NOW,
    )
    assert vetted["applied"] is True

    wf_res = execute_return_to_training_workflow(
        rest_hours=8.0,
        fatigue_score=2,
        pain_score=0,
        health_constraint=vetted,
        is_current=True,
    )
    assert wf_res["status"] == "completed"
    assert wf_res["health_constraint_applied"] is True
    assert wf_res["is_diagnosis"] is False
    assert wf_res["treatment_modified"] is False
    assert wf_res["clinical_clearance_claimed"] is False


def test_cross_domain_return_to_training_denies_raw_dict_without_vetted_evidence() -> (
    None
):
    health_projection = {
        "constraint_id": "hc-002",
        "status": "active",
        "load_limits": {"reduction_pct": 50},
        "authorization_reference": "auth.fake.999",
    }

    wf_res = execute_return_to_training_workflow(
        rest_hours=8.0,
        fatigue_score=2,
        pain_score=0,
        health_constraint=health_projection,
        is_authorized=True,
        is_current=True,
    )
    assert wf_res["status"] == "completed"
    assert wf_res["health_constraint_applied"] is False
    assert wf_res["recommendation"] == "continue"


def test_cross_domain_clinical_extras_dropped_from_minimized_projection() -> None:
    _, _, approval_service, gate, cross_request = _setup_runtime()
    consumed = _get_approved_gate_result(gate, approval_service, cross_request)

    projection = {
        "constraint_id": "hc-001",
        "status": "active",
        "activity_limits": ["no_running"],
        "load_limits": {"reduction_pct": 10},
        "source_reference": "health:source:1",
        "authorization_reference": consumed.decision_id,
        "diagnosis": "ACL tear",
        "treatment_plan": "surgery",
        "clinical_notes": "secret",
    }

    result = evaluate_health_constraint(
        projection,
        permission_request=cross_request,
        permission_decision=consumed,
        permission_gate=gate,
        now=NOW,
    )

    assert result["applied"] is True
    assert result["constraint"] == {
        "constraint_id": "hc-001",
        "status": "active",
        "activity_limits": ["no_running"],
        "load_limits": {"reduction_pct": 10},
        "source_reference": "health:source:1",
        "authorization_reference": consumed.decision_id,
    }
    assert "diagnosis" not in result["constraint"]
    assert "treatment_plan" not in result["constraint"]
    assert "clinical_notes" not in result["constraint"]
