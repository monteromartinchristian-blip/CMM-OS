"""Phase 10.22 — M4: Permission positive-path lifecycle.

The audit found the approval-gated path was covered only by deny-by-default
tests and a partial consume assertion; the full positive path — that a granted,
consumed approval actually unlocks the action — was never proven end-to-end.

This test drives the REAL Phase 10.15 permission stack
(``DomainPermissionResolver`` + ``build_university_permission_policy`` +
``ApprovalService``) through the complete capability lifecycle:

    request -> APPROVAL_REQUIRED -> approved -> validate_and_consume -> granted

proving that an approval-gated capability (calendar/task mutation) is denied by
default, requires a scoped approval, and is granted once that approval is
validated and consumed.
"""

from __future__ import annotations

import dataclasses
from datetime import datetime, timezone

import pytest

from cmm.agent_runtime.approval_contracts import (
    ApprovalConsumptionEvidence,
    ApprovalRequest,
)
from cmm.agent_runtime.approval_repository import InMemoryApprovalRepository
from cmm.agent_runtime.approval_service import ApprovalService
from cmm.agent_runtime.domain_permission_contracts import (
    PermissionApprovalRequirement,
    PermissionCapability,
)
from cmm.domains.approval_bridge import to_approval_requirement
from cmm.domains.health.permissions import build_health_permission_policy
from cmm.domains.permission_contracts import (
    CrossDomainPermissionRequest,
    DomainPermissionRequest,
)
from cmm.domains.permission_gate import DomainPermissionGate, PermissionGateOutcome
from cmm.domains.permission_registry import DomainPermissionRegistry
from cmm.domains.permission_resolution import DomainPermissionResolver
from cmm.domains.university.permissions import build_university_permission_policy

NOW = datetime(2026, 8, 9, tzinfo=timezone.utc)


def _resolver() -> DomainPermissionResolver:
    registry = DomainPermissionRegistry()
    registry.register(build_university_permission_policy())
    return DomainPermissionResolver(registry)


def _health_peered_resolver() -> DomainPermissionResolver:
    registry = DomainPermissionRegistry()
    registry.register(
        dataclasses.replace(
            build_health_permission_policy(),
            allow_cross_domain_access=True,
            allowed_target_domains=("domain:university",),
            allowed_capabilities=(
                PermissionCapability.DOMAIN_CROSS_ACCESS,
                PermissionCapability.RESOURCE_READ,
            ),
            allowed_resource_kinds=("study_session",),
            allowed_sensitivity_levels=("restricted",),
        )
    )
    registry.register(build_university_permission_policy())
    return DomainPermissionResolver(registry)


def _health_university_gate() -> tuple[
    DomainPermissionRegistry,
    DomainPermissionResolver,
    ApprovalService,
    DomainPermissionGate,
]:
    registry = DomainPermissionRegistry()
    registry.register(
        dataclasses.replace(
            build_health_permission_policy(),
            allow_cross_domain_access=True,
            allowed_target_domains=("domain:university",),
            allowed_capabilities=(
                PermissionCapability.DOMAIN_CROSS_ACCESS,
                PermissionCapability.RESOURCE_READ,
            ),
            allowed_resource_kinds=("study_session",),
            allowed_sensitivity_levels=("restricted",),
        )
    )
    registry.register(build_university_permission_policy())
    resolver = DomainPermissionResolver(registry)
    service = ApprovalService(InMemoryApprovalRepository())
    return (
        registry,
        resolver,
        service,
        DomainPermissionGate(resolver, service, clock=lambda: NOW),
    )


def _minimal_cross_domain_request(
    request_id: str = "health-university-minimal-1",
    *,
    actor_id: str = "actor-1",
    session_id: str = "sess-1",
    target_domain: str = "domain:university",
    resource_id: str = "university.study_session:9",
    resource_kind: str = "study_session",
    expires_at: datetime | None = None,
) -> CrossDomainPermissionRequest:
    return CrossDomainPermissionRequest(
        request_id,
        "domain:health",
        target_domain,
        resource_ids=(resource_id,),
        resource_kinds=(resource_kind,),
        reason="minimal reduced workload projection",
        actor_id=actor_id,
        session_id=session_id,
        sensitivity_level="restricted",
        expires_at=expires_at,
    )


def _approved_cross_domain_request(
    gate: DomainPermissionGate,
    service: ApprovalService,
    request: CrossDomainPermissionRequest,
    *,
    requirement_override: PermissionApprovalRequirement | None = None,
) -> tuple[PermissionApprovalRequirement, str]:
    pending = gate.evaluate_cross_domain(request)
    assert pending.outcome == PermissionGateOutcome.APPROVAL_REQUIRED
    requirement = PermissionApprovalRequirement.from_dict(
        pending.approval_requirements[0]
    )
    approval_requirement = requirement_override or requirement
    approval = to_approval_requirement(approval_requirement, agent_run_id="run-1")
    approval_request = service.create_request_from_requirement(
        approval, requested_by="agent-runtime"
    )
    service.approve(approval_request.id, "human-approver")
    return requirement, approval_request.id


def _request(action: PermissionCapability) -> DomainPermissionRequest:
    return DomainPermissionRequest(
        "req-1",
        action,
        "domain:university",
        "actor-1",
        "sess-1",
        sensitivity_level="restricted",
    )


def _approve_and_consume(requirement) -> object:
    """Create an approved approval and consume it, returning the evidence.

    Mirrors the real gate/approval flow: a requirement produced by the resolver
    is converted to a canonical approval, approved by a human, then validated
    and consumed to grant the action.
    """
    repo = InMemoryApprovalRepository()
    service = ApprovalService(repo)
    approval = to_approval_requirement(requirement, agent_run_id="run-1")
    request = service.create_request_from_requirement(
        approval, requested_by="agent-runtime"
    )
    service.approve(request.id, "human-approver", comment="Approved for testing")
    return service.validate_and_consume(
        request.id,
        actor_id="actor-1",
        session_id="sess-1",
        scope=requirement.scope,
        expected_requirement=requirement,
    )


def test_task_create_request_approval_required_then_succeeds():
    """task_create: APPROVAL_REQUIRED -> approved -> consumed -> granted."""
    resolver = _resolver()

    # 1. Request: denied by default, approval required.
    result = resolver.resolve(_request(PermissionCapability.TASK_CREATE), now=NOW)
    assert result.effective_permissions.decision.name == "APPROVAL_REQUIRED"
    assert len(result.approval_requirements) == 1
    requirement = result.approval_requirements[0]
    assert requirement.action is PermissionCapability.TASK_CREATE

    # 2. Approved and consumed: the action succeeds.
    evidence = _approve_and_consume(requirement)
    assert evidence.granted is True


def test_schedule_modify_request_approval_required_then_succeeds():
    """schedule_modify follows the same request->approve->consume->grant path."""
    resolver = _resolver()
    result = resolver.resolve(_request(PermissionCapability.SCHEDULE_MODIFY), now=NOW)
    assert result.effective_permissions.decision.name == "APPROVAL_REQUIRED"
    requirement = result.approval_requirements[0]

    evidence = _approve_and_consume(requirement)
    assert evidence.granted is True


def test_task_create_without_approval_never_grants():
    """A pending (not approved) approval does not grant the action."""
    resolver = _resolver()
    result = resolver.resolve(_request(PermissionCapability.TASK_CREATE), now=NOW)
    requirement = result.approval_requirements[0]

    repo = InMemoryApprovalRepository()
    service = ApprovalService(repo)
    approval = to_approval_requirement(requirement, agent_run_id="run-1")
    request = service.create_request_from_requirement(
        approval, requested_by="agent-runtime"
    )
    # Not approved: consuming a pending approval must not grant.
    evidence = service.validate_and_consume(
        request.id,
        actor_id="actor-1",
        session_id="sess-1",
        scope=requirement.scope,
        expected_requirement=requirement,
    )
    assert evidence.granted is False


def test_health_to_university_minimal_projection_approval_lifecycle_is_scoped():
    _, _, service, gate = _health_university_gate()
    request = _minimal_cross_domain_request()

    pending = gate.evaluate_cross_domain(request)
    assert pending.outcome == PermissionGateOutcome.APPROVAL_REQUIRED
    assert len(pending.approval_requirements) == 1
    requirement = PermissionApprovalRequirement.from_dict(
        pending.approval_requirements[0]
    )
    assert requirement.scope == "cross_domain"
    assert requirement.target_domain == "domain:university"
    assert requirement.resource_id == "university.study_session:9"
    assert requirement.resource_kind == "study_session"

    approval = to_approval_requirement(requirement, agent_run_id="run-1")
    approval_request = service.create_request_from_requirement(
        approval,
        requested_by="agent-runtime",
    )
    service.approve(
        approval_request.id, "human-approver", comment="Minimal projection approved"
    )
    permitted = gate.evaluate_cross_domain(
        request,
        approval_request_id=approval_request.id,
    )
    assert permitted.allowed
    assert permitted.outcome == PermissionGateOutcome.APPROVAL_CONSUMED
    assert permitted.approval_evidence["granted"] is True
    assert permitted.approval_evidence["consumed"] is True


def test_cross_domain_gate_rejects_forged_gate_evidence_and_missing_approval():
    _, resolver, _, gate = _health_university_gate()
    request = _minimal_cross_domain_request("health-university-forged-gate")
    forged = ApprovalConsumptionEvidence(
        request_id="approval-forged",
        requirement_id=f"cross-domain:{request.request_id}",
        actor_id=request.actor_id,
        session_id=request.session_id,
        domain_id=request.source_domain,
        target_domain=request.target_domain,
        action=PermissionCapability.DOMAIN_CROSS_ACCESS.value,
        scope="cross_domain",
        consumed=True,
        granted=True,
        validated_at=NOW,
    )

    pending = gate.evaluate_cross_domain(request)
    assert not pending.allowed
    assert pending.requires_approval
    with pytest.raises(TypeError):
        gate.evaluate_cross_domain(request, approval_evidence=forged)
    with pytest.raises(TypeError):
        resolver.resolve_cross_domain(request, now=NOW, approval_evidence=forged)


@pytest.mark.parametrize(
    ("label", "mutate"),
    (
        ("actor", lambda request: dataclasses.replace(request, actor_id="actor-2")),
        ("session", lambda request: dataclasses.replace(request, session_id="sess-2")),
        (
            "target",
            lambda request: dataclasses.replace(
                request, target_domain="domain:unknown"
            ),
        ),
        (
            "resource",
            lambda request: dataclasses.replace(
                request, resource_ids=("university.study_session:10",)
            ),
        ),
    ),
)
def test_cross_domain_gate_rejects_approval_bound_to_different_context(label, mutate):
    _, _, service, gate = _health_university_gate()
    request = _minimal_cross_domain_request(f"health-university-{label}")
    _, approval_request_id = _approved_cross_domain_request(gate, service, request)

    result = gate.evaluate_cross_domain(
        mutate(request), approval_request_id=approval_request_id
    )
    assert not result.allowed
    assert result.outcome in {
        PermissionGateOutcome.DENY,
        PermissionGateOutcome.APPROVAL_DENIED,
    }


def test_cross_domain_gate_rejects_wrong_scope_and_wrong_approval_request_id():
    _, _, service, gate = _health_university_gate()
    request = _minimal_cross_domain_request("health-university-scope")
    requirement, approval_request_id = _approved_cross_domain_request(
        gate, service, request
    )

    wrong_scope_requirement = dataclasses.replace(requirement, scope="resource")
    _, wrong_scope_approval_id = _approved_cross_domain_request(
        gate,
        service,
        _minimal_cross_domain_request("health-university-scope-mismatch"),
        requirement_override=wrong_scope_requirement,
    )
    wrong_scope = gate.evaluate_cross_domain(
        request, approval_request_id=wrong_scope_approval_id
    )
    assert wrong_scope.outcome == PermissionGateOutcome.APPROVAL_DENIED

    wrong_id = gate.evaluate_cross_domain(
        request, approval_request_id="approval-does-not-exist"
    )
    assert wrong_id.outcome == PermissionGateOutcome.APPROVAL_DENIED
    assert approval_request_id != wrong_scope_approval_id


def test_cross_domain_gate_rejects_consumed_revoked_and_expired_approvals():
    _, _, service, gate = _health_university_gate()
    consumed_request = _minimal_cross_domain_request("health-university-consumed")
    _, consumed_id = _approved_cross_domain_request(gate, service, consumed_request)
    first = gate.evaluate_cross_domain(
        consumed_request, approval_request_id=consumed_id
    )
    second = gate.evaluate_cross_domain(
        consumed_request, approval_request_id=consumed_id
    )
    assert first.allowed
    assert second.outcome == PermissionGateOutcome.APPROVAL_DENIED

    revoked_request = _minimal_cross_domain_request("health-university-revoked")
    _, revoked_id = _approved_cross_domain_request(gate, service, revoked_request)
    service.revoke(revoked_id, "human-approver")
    revoked = gate.evaluate_cross_domain(
        revoked_request, approval_request_id=revoked_id
    )
    assert revoked.outcome == PermissionGateOutcome.APPROVAL_DENIED

    expired_request = _minimal_cross_domain_request("health-university-expired")
    _, expired_id = _approved_cross_domain_request(gate, service, expired_request)
    stored = service.repository.get_request(expired_id)
    service.repository.update_request(
        ApprovalRequest.from_mapping(
            {
                **stored.to_dict(),
                "expires_at": NOW.replace(year=2025).isoformat(),
            }
        )
    )
    expired = gate.evaluate_cross_domain(
        expired_request, approval_request_id=expired_id
    )
    assert expired.outcome == PermissionGateOutcome.APPROVAL_DENIED
    assert not expired.allowed


def test_cross_domain_gate_denies_policy_change_before_consumption():
    registry, _, service, gate = _health_university_gate()
    request = _minimal_cross_domain_request("health-university-policy-change")
    _, approval_request_id = _approved_cross_domain_request(gate, service, request)

    current_health = registry.get("domain-permission:health:1.0.0")
    registry.register(
        dataclasses.replace(
            current_health,
            version="2.0.0",
            allow_cross_domain_access=False,
            allowed_target_domains=(),
            allowed_capabilities=(),
        )
    )
    denied = gate.evaluate_cross_domain(
        request, approval_request_id=approval_request_id
    )
    assert denied.outcome == PermissionGateOutcome.DENY
    assert service.repository.is_consumed(approval_request_id) is False


def test_cross_domain_gate_preserves_minimal_projection_boundaries():
    _, _, service, gate = _health_university_gate()
    minimal = _minimal_cross_domain_request("health-university-minimal-boundary")
    _, approval_request_id = _approved_cross_domain_request(gate, service, minimal)
    assert gate.evaluate_cross_domain(
        minimal, approval_request_id=approval_request_id
    ).allowed

    detailed = _minimal_cross_domain_request(
        "health-university-clinical-detail",
        resource_id="health.medical_report:1",
        resource_kind="medical_report",
    )
    assert gate.evaluate_cross_domain(detailed).outcome == PermissionGateOutcome.DENY

    outbound = dataclasses.replace(
        minimal,
        request_id="university-health-outbound",
        source_domain="domain:university",
        target_domain="domain:health",
        resource_ids=("health.study_session:9",),
    )
    assert gate.evaluate_cross_domain(outbound).outcome == PermissionGateOutcome.DENY


def test_cross_domain_resolver_has_no_caller_approval_evidence_api():
    resolver = _health_peered_resolver()
    request = CrossDomainPermissionRequest(
        "health-university-forged-1",
        "domain:health",
        "domain:university",
        resource_ids=("university.study_session:9",),
        resource_kinds=("study_session",),
        reason="forged evidence regression",
        actor_id="actor-1",
        session_id="sess-1",
        sensitivity_level="restricted",
    )
    forged = ApprovalConsumptionEvidence(
        request_id="approval-forged",
        requirement_id=f"cross-domain:{request.request_id}",
        actor_id=request.actor_id,
        session_id=request.session_id,
        domain_id=request.source_domain,
        target_domain=request.target_domain,
        action=PermissionCapability.DOMAIN_CROSS_ACCESS.value,
        scope="cross_domain",
        consumed=True,
        granted=True,
        validated_at=NOW,
    )

    with pytest.raises(TypeError):
        resolver.resolve_cross_domain(
            request,
            now=NOW,
            approval_evidence=forged,
        )
