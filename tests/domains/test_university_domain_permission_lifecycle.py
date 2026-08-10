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

from datetime import datetime, timezone

from cmm.agent_runtime.approval_repository import InMemoryApprovalRepository
from cmm.agent_runtime.approval_service import ApprovalService
from cmm.agent_runtime.domain_permission_contracts import PermissionCapability
from cmm.domains.approval_bridge import to_approval_requirement
from cmm.domains.permission_contracts import DomainPermissionRequest
from cmm.domains.permission_registry import DomainPermissionRegistry
from cmm.domains.permission_resolution import DomainPermissionResolver
from cmm.domains.university.permissions import build_university_permission_policy

NOW = datetime(2026, 8, 9, tzinfo=timezone.utc)


def _resolver() -> DomainPermissionResolver:
    registry = DomainPermissionRegistry()
    registry.register(build_university_permission_policy())
    return DomainPermissionResolver(registry)


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
    result = resolver.resolve(
        _request(PermissionCapability.SCHEDULE_MODIFY), now=NOW
    )
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