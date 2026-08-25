"""Tests for Phase 10.29 Life Plan Cross-Domain Trust Boundary."""

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
from cmm.domains.life_plan.catalog import LIFE_PLAN_DOMAIN_ID
from cmm.domains.life_plan.permissions import build_life_plan_permission_policy
from cmm.domains.life_plan.rules import (
    AuthorizedCrossDomainContribution,
    evaluate_cross_domain_impact,
)
from cmm.domains.permission_contracts import CrossDomainPermissionRequest
from cmm.domains.permission_gate import DomainPermissionGate, PermissionGateOutcome
from cmm.domains.permission_registry import DomainPermissionRegistry
from cmm.domains.permission_resolution import DomainPermissionResolver

NOW = datetime(2026, 8, 26, 12, 0, tzinfo=timezone.utc)


def _setup_runtime() -> tuple[
    DomainPermissionRegistry,
    DomainPermissionResolver,
    ApprovalService,
    DomainPermissionGate,
    CrossDomainPermissionRequest,
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

    cross_request = CrossDomainPermissionRequest(
        request_id="auth.scope.life_plan_health_impact",
        source_domain="domain:health",
        target_domain=LIFE_PLAN_DOMAIN_ID,
        capability=PermissionCapability.RESOURCE_READ,
        reason="health constraint on life plan relocation",
        actor_id="actor-user",
        session_id="sess-user",
        sensitivity_level="restricted",
        resource_ids=("health.resource.health_profile:hp-001",),
        resource_kinds=("resource.health_constraints",),
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
        to_approval_requirement(req_item, agent_run_id="run-life-plan-1"),
        requested_by="user",
    )
    approval_service.approve(app_req.id, "user")
    consumed = gate.evaluate_cross_domain(cross_request, approval_request_id=app_req.id)
    assert consumed.outcome is PermissionGateOutcome.APPROVAL_CONSUMED
    return consumed


def test_cross_domain_authorized_minimal_projection_only() -> None:
    _, _, approval_service, gate, cross_request = _setup_runtime()
    consumed = _get_approved_gate_result(gate, approval_service, cross_request)

    authorized_projection = {
        "constraint_id": "hc-life-001",
        "status": "active",
        "activity_limits": ["no_high_altitude_relocation"],
        "source_reference": "health.ref.901",
        "authorization_reference": consumed.decision_id,
    }
    res = evaluate_cross_domain_impact(
        authorized_projection,
        permission_request=cross_request,
        permission_decision=consumed,
        permission_gate=gate,
        now=NOW,
    )
    assert res["applied"] is True
    assert res["provenance"]["authorization_reference"] == consumed.decision_id
    assert res["authorization_verified"] is True
    assert isinstance(res["authorized_artifact"], AuthorizedCrossDomainContribution)


def test_caller_boolean_auth_fails() -> None:
    result = evaluate_cross_domain_impact(
        {
            "status": "active",
            "authorization_reference": "fake-auth",
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

    result = evaluate_cross_domain_impact(
        {
            "status": "active",
            "authorization_reference": "fake",
        },
        permission_decision=FakePermission(),
    )
    assert result["applied"] is False
    assert result["reason"] == "unauthorized_or_expired"


def test_expired_cross_domain_projection_fails() -> None:
    _, _, approval_service, gate, cross_request = _setup_runtime()
    consumed = _get_approved_gate_result(gate, approval_service, cross_request)

    expired_proj = {
        "constraint_id": "hc-expired-001",
        "status": "active",
        "effective_from": "2020-01-01T00:00:00+00:00",
        "effective_until": "2020-01-02T00:00:00+00:00",
    }
    res = evaluate_cross_domain_impact(
        expired_proj,
        permission_request=cross_request,
        permission_decision=consumed,
        permission_gate=gate,
        now=NOW,
    )
    assert res["applied"] is False
    assert res["reason"] == "unauthorized_or_expired"


def test_cross_domain_denies_full_clinical_dossier() -> None:
    _, _, approval_service, gate, cross_request = _setup_runtime()
    consumed = _get_approved_gate_result(gate, approval_service, cross_request)

    raw_dossier = {
        "constraint_id": "hc-life-001",
        "full_clinical_history": ["asthma_childhood", "allergy_penicillin"],
        "medication_list": ["inhaler_100mcg"],
        "raw_health_memory": {"sensitive_notes": "personal"},
    }
    res = evaluate_cross_domain_impact(
        raw_dossier,
        permission_request=cross_request,
        permission_decision=consumed,
        permission_gate=gate,
        now=NOW,
    )
    assert res["applied"] is False
    assert res["reason"] == "rejected_unauthorized_dossier"


def test_cross_domain_drops_unallowed_extra_keys() -> None:
    _, _, approval_service, gate, cross_request = _setup_runtime()
    consumed = _get_approved_gate_result(gate, approval_service, cross_request)

    projection = {
        "constraint_id": "hc-life-002",
        "status": "active",
        "activity_limits": ["no_dusty_environments"],
        "source_reference": "health:source:2",
        "authorization_reference": consumed.decision_id,
        "clinical_diagnosis": "Allergic Rhinitis",
        "prescriptions": ["antihistamine"],
    }

    result = evaluate_cross_domain_impact(
        projection,
        permission_request=cross_request,
        permission_decision=consumed,
        permission_gate=gate,
        now=NOW,
    )

    assert result["applied"] is True
    assert result["contribution"] == {
        "constraint_id": "hc-life-002",
        "status": "active",
        "activity_limits": ["no_dusty_environments"],
        "source_reference": "health:source:2",
        "authorization_reference": consumed.decision_id,
    }
    assert "clinical_diagnosis" not in result["contribution"]
    assert "prescriptions" not in result["contribution"]


def test_forged_permission_gate_result_rejected() -> None:
    from cmm.domains.permission_gate import PermissionGateResult

    _, _, _, _, cross_request = _setup_runtime()

    class RaisingGate:
        def evaluate_cross_domain(self, req: Any, **kwargs: Any) -> Any:
            raise RuntimeError("Should never be called if forged result were trusted")

    forged_result = PermissionGateResult(
        outcome="allow",
        action="domain_cross_access",
        domain_id="domain:evil",
        actor_id="attacker",
        session_id="attacker",
        decision_id="forged-decision-123",
        metadata={"target_domain": "domain:life-plan"},
    )

    proj = {
        "status": "active",
        "activity_limits": ["limit"],
    }

    res = evaluate_cross_domain_impact(
        proj,
        permission_request=cross_request,
        permission_decision=forged_result,
        permission_gate=RaisingGate(),
        now=NOW,
    )
    assert res["applied"] is False
    assert res["authorization_verified"] is False


def test_permission_context_mismatch_rejected() -> None:
    _, _, approval_service, gate, cross_request = _setup_runtime()
    consumed = _get_approved_gate_result(gate, approval_service, cross_request)

    proj = {
        "status": "active",
        "activity_limits": ["limit"],
    }

    # Wrong target domain
    bad_target_req = dataclasses.replace(cross_request, target_domain="domain:evil")
    res1 = evaluate_cross_domain_impact(
        proj,
        permission_request=bad_target_req,
        permission_decision=consumed,
        permission_gate=gate,
        now=NOW,
    )
    assert res1["applied"] is False
    assert res1["authorization_verified"] is False

    # Mismatched forged decision ID in caller decision object
    tampered_decision = dataclasses.replace(consumed, decision_id="forged-id-999")
    res2 = evaluate_cross_domain_impact(
        proj,
        permission_request=cross_request,
        permission_decision=tampered_decision,
        permission_gate=gate,
        now=NOW,
    )
    assert res2["applied"] is False
    assert res2["authorization_verified"] is False
