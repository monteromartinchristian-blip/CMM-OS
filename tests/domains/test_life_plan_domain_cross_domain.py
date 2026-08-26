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
    PermissionOutcome,
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
    pending = gate.evaluate_cross_domain(cross_request)
    req_item = PermissionApprovalRequirement.from_dict(pending.approval_requirements[0])
    app_req = approval_service.create_request_from_requirement(
        to_approval_requirement(req_item, agent_run_id="run-life-plan-1"),
        requested_by="user",
    )
    approval_service.approve(app_req.id, "user")

    authorized_projection = {
        "constraint_id": "hc-life-001",
        "status": "active",
        "activity_limits": ["no_high_altitude_relocation"],
        "source_reference": "health.ref.901",
    }
    res = evaluate_cross_domain_impact(
        authorized_projection,
        permission_request=cross_request,
        permission_gate=gate,
        approval_request_id=app_req.id,
        now=NOW,
    )
    assert res["applied"] is True
    assert res["authorization_verified"] is True
    assert res["provenance"]["authorization_reference"] is not None
    assert isinstance(res["authorized_artifact"], AuthorizedCrossDomainContribution)


def test_cross_domain_direct_allow_control() -> None:
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
        allowed_sensitivity_levels=("internal",),
    )
    perm_registry.register(health_policy)
    approval_service = ApprovalService(InMemoryApprovalRepository())
    resolver = DomainPermissionResolver(perm_registry)
    gate = DomainPermissionGate(resolver, approval_service, clock=lambda: NOW)

    cross_request = CrossDomainPermissionRequest(
        request_id="auth.scope.allow_test",
        source_domain="domain:health",
        target_domain=LIFE_PLAN_DOMAIN_ID,
        capability=PermissionCapability.RESOURCE_READ,
        reason="direct allow check",
        actor_id="actor-user",
        session_id="sess-user",
        sensitivity_level="internal",
        resource_ids=("health.resource.health_profile:hp-allow",),
        resource_kinds=("resource.health_constraints",),
        requires_approval=False,
    )

    proj = {
        "constraint_id": "hc-allow-001",
        "status": "active",
        "activity_limits": ["light_exercise_only"],
    }
    res = evaluate_cross_domain_impact(
        proj,
        permission_request=cross_request,
        permission_gate=gate,
        now=NOW,
    )
    assert res["applied"] is True
    assert res["authorization_verified"] is True
    assert res["provenance"]["authorization_reference"] is not None


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
    pending = gate.evaluate_cross_domain(cross_request)
    req_item = PermissionApprovalRequirement.from_dict(pending.approval_requirements[0])
    app_req = approval_service.create_request_from_requirement(
        to_approval_requirement(req_item, agent_run_id="run-life-plan-1"),
        requested_by="user",
    )
    approval_service.approve(app_req.id, "user")

    expired_proj = {
        "constraint_id": "hc-expired-001",
        "status": "active",
        "effective_from": "2020-01-01T00:00:00+00:00",
        "effective_until": "2020-01-02T00:00:00+00:00",
    }
    res = evaluate_cross_domain_impact(
        expired_proj,
        permission_request=cross_request,
        permission_gate=gate,
        approval_request_id=app_req.id,
        now=NOW,
    )
    assert res["applied"] is False
    assert res["reason"] == "unauthorized_or_expired"


def test_cross_domain_denies_full_clinical_dossier() -> None:
    _, _, approval_service, gate, cross_request = _setup_runtime()
    pending = gate.evaluate_cross_domain(cross_request)
    req_item = PermissionApprovalRequirement.from_dict(pending.approval_requirements[0])
    app_req = approval_service.create_request_from_requirement(
        to_approval_requirement(req_item, agent_run_id="run-life-plan-1"),
        requested_by="user",
    )
    approval_service.approve(app_req.id, "user")

    raw_dossier = {
        "constraint_id": "hc-life-001",
        "full_clinical_history": ["asthma_childhood", "allergy_penicillin"],
        "medication_list": ["inhaler_100mcg"],
        "raw_health_memory": {"sensitive_notes": "personal"},
    }
    res = evaluate_cross_domain_impact(
        raw_dossier,
        permission_request=cross_request,
        permission_gate=gate,
        approval_request_id=app_req.id,
        now=NOW,
    )
    assert res["applied"] is False
    assert res["reason"] == "rejected_unauthorized_dossier"


def test_cross_domain_drops_unallowed_extra_keys() -> None:
    _, _, approval_service, gate, cross_request = _setup_runtime()
    pending = gate.evaluate_cross_domain(cross_request)
    req_item = PermissionApprovalRequirement.from_dict(pending.approval_requirements[0])
    app_req = approval_service.create_request_from_requirement(
        to_approval_requirement(req_item, agent_run_id="run-life-plan-1"),
        requested_by="user",
    )
    approval_service.approve(app_req.id, "user")

    projection = {
        "constraint_id": "hc-life-002",
        "status": "active",
        "activity_limits": ["no_dusty_environments"],
        "source_reference": "health:source:2",
        "clinical_diagnosis": "Allergic Rhinitis",
        "prescriptions": ["antihistamine"],
    }

    result = evaluate_cross_domain_impact(
        projection,
        permission_request=cross_request,
        permission_gate=gate,
        approval_request_id=app_req.id,
        now=NOW,
    )

    assert result["applied"] is True
    assert result["contribution"] == {
        "constraint_id": "hc-life-002",
        "status": "active",
        "activity_limits": ["no_dusty_environments"],
        "source_reference": "health:source:2",
        "authorization_reference": result["provenance"]["authorization_reference"],
    }
    assert "clinical_diagnosis" not in result["contribution"]
    assert "prescriptions" not in result["contribution"]


def test_v2_b1_gate_issued_id_replay_rejected() -> None:
    """V2-B1: Prove gate-issued decision-ID replay from unrelated decision cannot authorize forged result."""
    from cmm.domains.permission_gate import PermissionGateResult

    _, _, _, gate, cross_request = _setup_runtime()

    # Step 1: Cause real gate to emit a legitimate decision ID for an unrelated request
    unrelated_request = CrossDomainPermissionRequest(
        request_id="auth.scope.unrelated_01",
        source_domain="domain:health",
        target_domain=LIFE_PLAN_DOMAIN_ID,
        capability=PermissionCapability.RESOURCE_READ,
        reason="unrelated health inquiry",
        actor_id="other-actor",
        session_id="other-sess",
        sensitivity_level="restricted",
        resource_ids=("health.resource.health_profile:hp-unrelated",),
        resource_kinds=("resource.health_constraints",),
    )
    unrelated_pending = gate.evaluate_cross_domain(unrelated_request)
    legitimate_issued_decision_id = unrelated_pending.decision_id
    assert legitimate_issued_decision_id is not None
    assert legitimate_issued_decision_id in gate._issued_decision_ids

    # Step 2: Construct forged PermissionGateResult reusing the gate-issued decision ID
    forged_result = PermissionGateResult(
        outcome="approval_consumed",
        action="domain_cross_access",
        domain_id="domain:health",
        actor_id=cross_request.actor_id,
        session_id=cross_request.session_id,
        decision_id=legitimate_issued_decision_id,
        approval_evidence={"granted": True, "request_id": "fake-app-req-999"},
        metadata={
            "source_domain": "domain:health",
            "target_domain": "domain:life-plan",
        },
    )

    # Step 3: Track that gate evaluation is actually called for the exact current request
    eval_called_with: list[Any] = []
    real_eval = gate.evaluate_cross_domain

    def spy_eval(req: Any, **kwargs: Any) -> Any:
        eval_called_with.append((req, kwargs))
        return real_eval(req, **kwargs)

    gate.evaluate_cross_domain = spy_eval  # type: ignore[assignment]

    proj = {
        "status": "active",
        "activity_limits": ["no_high_altitude_relocation"],
    }

    # Step 4: Evaluate cross-domain impact passing forged result and current request (without valid approval)
    res = evaluate_cross_domain_impact(
        proj,
        permission_request=cross_request,
        permission_decision=forged_result,
        permission_gate=gate,
        now=NOW,
    )

    # Step 5: Assert that forged supplied result did NOT authorize
    assert res["applied"] is False
    assert res["authorization_verified"] is False
    assert res["reason"] == "unauthorized_or_expired"

    # Step 6: Assert that the exact current request was evaluated through the real gate
    assert len(eval_called_with) == 1
    called_req, _called_kwargs = eval_called_with[0]
    assert called_req.request_id == cross_request.request_id
    assert called_req.actor_id == cross_request.actor_id


def test_permission_context_mismatch_rejected() -> None:
    _, _, _, gate, cross_request = _setup_runtime()

    proj = {
        "status": "active",
        "activity_limits": ["limit"],
    }

    # Wrong target domain
    bad_target_req = dataclasses.replace(cross_request, target_domain="domain:evil")
    res1 = evaluate_cross_domain_impact(
        proj,
        permission_request=bad_target_req,
        permission_gate=gate,
        now=NOW,
    )
    assert res1["applied"] is False
    assert res1["authorization_verified"] is False


def test_v3_b1_fake_gate_rejected() -> None:
    """V3-B1 RED: A duck-typed FakeGate must not authorize Life Plan mutation."""
    _, _, _, _, cross_request = _setup_runtime()

    class FakeGateResult:
        allowed = True
        outcome = "allow"
        domain_id = "domain:health"
        actor_id = cross_request.actor_id
        session_id = cross_request.session_id
        decision_id = "forged-gate-decision-123"

    class FakeGate:
        def evaluate_cross_domain(self, *args: Any, **kwargs: Any) -> Any:
            return FakeGateResult()

    proj = {
        "constraint_id": "hc-life-fake-001",
        "status": "active",
        "activity_limits": ["no_high_altitude_relocation"],
        "source_reference": "health.ref.901",
    }
    res = evaluate_cross_domain_impact(
        proj,
        permission_request=cross_request,
        permission_gate=FakeGate(),
        now=NOW,
    )
    assert res["applied"] is False
    assert res["authorization_verified"] is False
    assert res["reason"] == "unauthorized_or_expired"


def test_v3_b1_fake_resolver_rejected() -> None:
    """V3-B1 RED: A duck-typed FakeResolver must not authorize Life Plan mutation."""
    _, _, _, _, cross_request = _setup_runtime()

    class FakeDecision:
        decision = PermissionOutcome.ALLOW
        request_id = cross_request.request_id

    class FakeResolver:
        def resolve_cross_domain(self, *args: Any, **kwargs: Any) -> Any:
            return FakeDecision()

    proj = {
        "constraint_id": "hc-life-fake-002",
        "status": "active",
        "activity_limits": ["no_high_altitude_relocation"],
        "source_reference": "health.ref.902",
    }
    res = evaluate_cross_domain_impact(
        proj,
        permission_request=cross_request,
        permission_resolver=FakeResolver(),
        now=NOW,
    )
    assert res["applied"] is False
    assert res["authorization_verified"] is False
    assert res["reason"] == "unauthorized_or_expired"


def test_v3_b1_missing_provenance_rejected() -> None:
    """V3-B1 RED: A canonical-looking result missing required provenance must fail closed."""
    _, _, _, _, cross_request = _setup_runtime()

    class IncompleteDecision:
        decision = PermissionOutcome.ALLOW
        # Missing request_id attribute or empty request_id

    class IncompleteResolver:
        def resolve_cross_domain(self, *args: Any, **kwargs: Any) -> Any:
            return IncompleteDecision()

    proj = {
        "constraint_id": "hc-life-fake-003",
        "status": "active",
    }
    res = evaluate_cross_domain_impact(
        proj,
        permission_request=cross_request,
        permission_resolver=IncompleteResolver(),
        now=NOW,
    )
    assert res["applied"] is False
    assert res["authorization_verified"] is False
    assert res["reason"] == "unauthorized_or_expired"
