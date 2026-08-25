"""Permanent Closure Adversarial Regression Gate for Phase 10.29 Life Plan Domain.

Permanent adversarial gate testing 24 essential security, semantic, and boundary invariants:
1. Preference -> Decision bypass fails without explicit confirmation.
2. Scenario -> Commitment bypass fails without explicit confirmation.
3. Closed decision reopening without explicit new evidence fails.
4. Closed decision reopening with explicit new evidence succeeds.
5. Alternative route selection does not infer abandonment.
6. Missing time constraint fails closed.
7. Missing money constraint fails closed.
8. Missing energy constraint fails closed.
9. Missing available capacity constraint fails closed.
10. Resource constraint rejects NaN and Inf.
11. Resource constraint rejects boolean values.
12. Goal dependency cycle detected and rejected.
13. Goal dependency distinguishes hard vs soft dependencies.
14. Long-term temporal ordering conflict detected.
15. Long-term temporal preserves uncertain milestones.
16. Cross-domain raw dict input rejected.
17. Cross-domain caller boolean is_authorized=True rejected.
18. Cross-domain duck-typed permission object rejected.
19. Cross-domain clinical dossier rejected.
20. Cross-domain expired permission decision rejected.
21. Plan drift detected without inferring abandonment.
22. Memory proposals prohibit direct write.
23. Memory proposals require confirmation.
24. Profile prohibits direct payment and external contracting.
"""

from __future__ import annotations

import dataclasses
from datetime import datetime, timezone

from cmm.agent_runtime.approval_repository import InMemoryApprovalRepository
from cmm.agent_runtime.approval_service import ApprovalService
from cmm.agent_runtime.domain_permission_contracts import (
    PermissionCapability,
)
from cmm.domains.general.permissions import build_general_permission_policy
from cmm.domains.health.permissions import build_health_permission_policy
from cmm.domains.life_plan import (
    LIFE_PLAN_DOMAIN_ID,
    build_life_plan_memory_proposal,
    build_life_plan_permission_policy,
    build_life_plan_profile,
    evaluate_alternative_route,
    evaluate_cross_domain_impact,
    evaluate_decision_status,
    evaluate_goal_dependencies,
    evaluate_long_term_temporal,
    evaluate_plan_drift,
    evaluate_resource_constraints,
)
from cmm.domains.permission_contracts import (
    CrossDomainPermissionRequest,
)
from cmm.domains.permission_gate import (
    DomainPermissionGate,
)
from cmm.domains.permission_registry import DomainPermissionRegistry
from cmm.domains.permission_resolution import DomainPermissionResolver

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


# 1. Preference -> Decision bypass fails without explicit confirmation
def test_closure_gate_preference_to_decision_bypass_fails() -> None:
    res = evaluate_decision_status("preference", "decision")
    assert res["allowed"] is False
    assert res["requires_confirmation"] is True
    assert (
        "confirmation" in res["reason"].lower()
        or "unconfirmed" in res["reason"].lower()
    )


def test_closure_gate_scenario_to_decision_bypass_fails() -> None:
    res = evaluate_decision_status("scenario", "decision")
    assert res["allowed"] is False
    assert res["requires_confirmation"] is True


# 2. Scenario -> Commitment bypass fails without explicit confirmation
def test_closure_gate_scenario_to_commitment_bypass_fails() -> None:
    res = evaluate_decision_status("scenario", "commitment")
    assert res["allowed"] is False
    assert res["requires_confirmation"] is True
    assert (
        "confirmation" in res["reason"].lower()
        or "unconfirmed" in res["reason"].lower()
    )


def test_closure_gate_inference_to_decision_bypass_fails() -> None:
    res = evaluate_decision_status("inference", "decision")
    assert res["allowed"] is False


def test_closure_gate_inference_to_commitment_bypass_fails() -> None:
    res = evaluate_decision_status("inference", "commitment")
    assert res["allowed"] is False


def test_closure_gate_unknown_decision_status_fails_closed() -> None:
    res1 = evaluate_decision_status("nonsense", "decision")
    assert res1["allowed"] is False
    res2 = evaluate_decision_status("idea", "confirmed_fact")
    assert res2["allowed"] is False


# 3. Closed decision reopening without explicit new evidence fails
def test_closure_gate_closed_decision_reopening_without_new_evidence_fails() -> None:
    res = evaluate_decision_status(
        "decision", "idea", is_closed=True, has_new_evidence=False
    )
    assert res["allowed"] is False
    assert "evidence" in res["reason"].lower() or "closed" in res["reason"].lower()


# 4. Closed decision reopening with explicit new evidence succeeds
def test_closure_gate_closed_decision_reopening_with_new_evidence_succeeds() -> None:
    res = evaluate_decision_status(
        "decision",
        "idea",
        is_closed=True,
        has_new_evidence=True,
        new_evidence="Relocation offer",
    )
    assert res["allowed"] is True
    assert res["reopened"] is True


# 5. Alternative route selection does not infer abandonment
def test_closure_gate_alternative_route_does_not_infer_abandonment() -> None:
    res = evaluate_alternative_route("goal-career-01", "route-b", route_type="fallback")
    assert res["primary_goal_abandoned"] is False
    assert res["is_failure"] is False
    assert res["is_contingency"] is True


# 6. Missing time constraint fails closed
def test_closure_gate_resource_time_constraint_missing_fails_closed() -> None:
    res = evaluate_resource_constraints(time={"required_hours_per_week": 40.0})
    assert res["dimensions"]["time"]["status"] == "unknown"
    assert res["feasible"] is None
    assert res["status"] == "unknown"


# 7. Missing money constraint fails closed
def test_closure_gate_resource_money_constraint_missing_fails_closed() -> None:
    res = evaluate_resource_constraints(money={"required_funds": 1000.0})
    assert res["dimensions"]["money"]["status"] == "unknown"
    assert res["feasible"] is None
    assert res["status"] == "unknown"


# 8. Missing energy constraint fails closed
def test_closure_gate_resource_energy_constraint_missing_fails_closed() -> None:
    res = evaluate_resource_constraints(energy={})
    assert res["dimensions"]["energy"]["status"] == "unknown"
    assert res["feasible"] is None
    assert res["status"] == "unknown"


# 9. Missing available capacity constraint fails closed
def test_closure_gate_resource_capacity_constraint_missing_fails_closed() -> None:
    res = evaluate_resource_constraints(available_capacity={})
    assert res["dimensions"]["available_capacity"]["status"] == "unknown"
    assert res["feasible"] is None
    assert res["status"] == "unknown"


# 10. Resource constraint rejects NaN and Inf
def test_closure_gate_resource_nan_inf_rejected() -> None:
    res_nan = evaluate_resource_constraints(
        time={"available_hours_per_week": float("nan"), "required_hours_per_week": 20.0}
    )
    assert res_nan["status"] == "invalid_evidence"
    assert res_nan["dimensions"]["time"]["status"] == "invalid_evidence"

    res_inf = evaluate_resource_constraints(
        money={"available_funds": float("inf"), "required_funds": 500.0}
    )
    assert res_inf["status"] == "invalid_evidence"
    assert res_inf["dimensions"]["money"]["status"] == "invalid_evidence"


# 11. Resource constraint rejects boolean values
def test_closure_gate_resource_bool_rejected() -> None:
    res_bool = evaluate_resource_constraints(
        time={"available_hours_per_week": True, "required_hours_per_week": 20.0}
    )
    assert res_bool["status"] == "invalid_evidence"
    assert res_bool["dimensions"]["time"]["status"] == "invalid_evidence"


# 12. Goal dependency cycle detected and rejected
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
    assert len(res["cycles"]) > 0


# 13. Goal dependency distinguishes hard vs soft dependencies
def test_closure_gate_goal_dependency_soft_vs_hard_distinction() -> None:
    res = evaluate_goal_dependencies(
        dependencies={"goal_a": ["goal_b"]},
        soft_dependencies={"goal_x": ["goal_y"]},
    )
    assert res["valid"] is True
    assert res["prerequisites"] == {"goal_a": ["goal_b"]}
    assert res["soft_dependencies"] == {"goal_x": ["goal_y"]}


# 14. Long-term temporal ordering conflict detected
def test_closure_gate_long_term_temporal_ordering_conflict_detected() -> None:
    res = evaluate_long_term_temporal(
        milestones=[
            {"id": "m1", "target_date": "2028-06-01T00:00:00Z"},
            {"id": "m2", "target_date": "2027-01-01T00:00:00Z", "depends_on": "m1"},
        ]
    )
    assert res["valid"] is False
    assert len(res["ordering_conflicts"]) > 0


# 15. Long-term temporal preserves uncertain milestones
def test_closure_gate_long_term_temporal_preserves_uncertain_milestones() -> None:
    res = evaluate_long_term_temporal(milestones=[{"id": "m_future"}])
    assert res["valid"] is True
    assert "m_future" in res["uncertain_milestones"]


# 16. Cross-domain raw dict input rejected
def test_closure_gate_cross_domain_raw_dict_rejected() -> None:
    res = evaluate_cross_domain_impact(
        {
            "source_domain": "domain:health",
            "status": "active",
        }
    )
    assert res["applied"] is False
    assert res["authorization_verified"] is False


# 17. Cross-domain caller boolean is_authorized=True rejected
def test_closure_gate_cross_domain_caller_bool_rejected() -> None:
    res = evaluate_cross_domain_impact(
        {
            "source_domain": "domain:health",
            "status": "active",
        },
        is_authorized=True,
    )
    assert res["applied"] is False
    assert res["authorization_verified"] is False


# 18. Cross-domain duck-typed permission object rejected
def test_closure_gate_cross_domain_duck_typed_object_rejected() -> None:
    class DuckTypedPermission:
        allowed = True
        decision_id = "duck-001"

    res = evaluate_cross_domain_impact(
        {
            "source_domain": "domain:health",
            "status": "active",
        },
        permission_decision=DuckTypedPermission(),
    )
    assert res["applied"] is False
    assert res["authorization_verified"] is False


def test_closure_gate_real_forged_permission_gate_result_rejected() -> None:
    from cmm.domains.permission_gate import PermissionGateResult

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

    class RaisingGate:
        def evaluate_cross_domain(self, req: Any, **kwargs: Any) -> Any:
            raise RuntimeError("Fake gate should never be called")

    forged_result = PermissionGateResult(
        outcome="allow",
        action="domain_cross_access",
        domain_id="domain:evil",
        actor_id="attacker",
        session_id="attacker",
        decision_id="forged-decision-999",
        metadata={"target_domain": "domain:life-plan"},
    )

    res = evaluate_cross_domain_impact(
        {
            "status": "active",
            "activity_limits": ["limit"],
        },
        permission_request=cross_request,
        permission_decision=forged_result,
        permission_gate=RaisingGate(),
        now=NOW,
    )
    assert res["applied"] is False
    assert res["authorization_verified"] is False


def test_closure_gate_permission_context_mismatch_rejected() -> None:
    from cmm.domains.approval_bridge import to_approval_requirement
    from cmm.agent_runtime.domain_permission_contracts import PermissionApprovalRequirement

    _, _, approval_service, gate = _setup_runtime()
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
    pending = gate.evaluate_cross_domain(cross_request)
    req_item = PermissionApprovalRequirement.from_dict(pending.approval_requirements[0])
    app_req = approval_service.create_request_from_requirement(
        to_approval_requirement(req_item, agent_run_id="run-life-plan-adv"),
        requested_by="user",
    )
    approval_service.approve(app_req.id, "user")
    consumed = gate.evaluate_cross_domain(cross_request, approval_request_id=app_req.id)

    proj = {
        "status": "active",
        "activity_limits": ["limit"],
    }

    # Wrong target domain in request
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


# 19. Cross-domain clinical dossier rejected
def test_closure_gate_cross_domain_clinical_dossier_rejected() -> None:
    res = evaluate_cross_domain_impact(
        {
            "source_domain": "domain:health",
            "full_clinical_history": ["heart_surgery_2022"],
            "medication_list": ["atorvastatin_20mg"],
        }
    )
    assert res["applied"] is False
    assert res["reason"] == "rejected_unauthorized_dossier"


# 20. Cross-domain expired permission decision rejected
def test_closure_gate_cross_domain_expired_permission_rejected() -> None:
    _, _, _, gate = _setup_runtime()
    cross_request = CrossDomainPermissionRequest(
        request_id="req-exp-01",
        source_domain="domain:health",
        target_domain=LIFE_PLAN_DOMAIN_ID,
        capability=PermissionCapability.RESOURCE_READ,
        reason="health constraint check",
        actor_id="actor-1",
        session_id="sess-1",
        sensitivity_level="restricted",
        resource_ids=("health.resource.health_profile:hp-001",),
        resource_kinds=("resource.health_constraints",),
        expires_at=datetime(2020, 1, 1, 0, 0, tzinfo=timezone.utc),
    )
    res = evaluate_cross_domain_impact(
        {
            "source_domain": "domain:health",
            "status": "active",
        },
        permission_request=cross_request,
        permission_gate=gate,
        now=NOW,
    )
    assert res["applied"] is False
    assert res["authorization_verified"] is False


# 21. Plan drift detected without inferring abandonment
def test_closure_gate_plan_drift_detects_drift_without_abandonment() -> None:
    res = evaluate_plan_drift(
        planned_state={"milestone_1": "completed"},
        actual_state={"milestone_1": "in_progress"},
    )
    assert res["has_drift"] is True
    assert res["goal_abandoned"] is False


# 22. Memory proposals prohibit direct write
def test_closure_gate_memory_proposal_prohibits_direct_write() -> None:
    policy = build_life_plan_permission_policy()
    assert policy.allow_memory_write is False


# 23. Memory proposals require confirmation
def test_closure_gate_memory_proposal_requires_confirmation() -> None:
    prop = build_life_plan_memory_proposal(proposal_id="prop-closure-01")
    assert prop.requires_confirmation is True


# 24. Profile prohibits direct payment and external contracting
def test_closure_gate_prohibits_payment_and_external_contracting() -> None:
    profile = build_life_plan_profile()
    assert "payment" in profile.prohibited_actions
    assert "contracting" in profile.prohibited_actions
    assert "external_communication" in profile.prohibited_actions
