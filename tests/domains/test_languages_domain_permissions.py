"""Tests for Phase 10.26 Languages Domain Permissions."""

from __future__ import annotations

import dataclasses
from datetime import datetime, timezone

from cmm.agent_runtime.approval_contracts import ApprovalRequest
from cmm.agent_runtime.approval_repository import InMemoryApprovalRepository
from cmm.agent_runtime.approval_service import ApprovalService
from cmm.agent_runtime.domain_permission_contracts import PermissionCapability
from cmm.agent_runtime.enums import PolicyRiskLevel
from cmm.domains.approval_bridge import to_approval_requirement
from cmm.domains.enums import DomainOperationType
from cmm.domains.languages.permissions import (
    LANGUAGES_PERMISSION_POLICY_ID,
    LANGUAGES_PROHIBITED_CAPABILITIES,
    build_languages_permission_policy,
    permission_authorization_allows,
    persistence_confirmation_accepted,
)
from cmm.domains.operation_contracts import DomainOperationDefinition
from cmm.domains.permission_contracts import (
    DomainPermissionPolicy,
    DomainPermissionRequest,
)
from cmm.domains.permission_gate import DomainPermissionGate, PermissionGateOutcome
from cmm.domains.permission_registry import DomainPermissionRegistry
from cmm.domains.permission_resolution import DomainPermissionResolver

NOW = datetime(2026, 8, 23, 12, 0, tzinfo=timezone.utc)


def _memory_write_operation() -> DomainOperationDefinition:
    return DomainOperationDefinition(
        operation_id="languages.test_memory_write_boundary",
        domain_id="domain:languages",
        version="1.0.0",
        name="Test Languages memory-write boundary",
        description="Test-only harmless operation for the shared permission gate.",
        operation_type=DomainOperationType.ANALYSIS,
        required_permissions=(PermissionCapability.MEMORY_WRITE.value,),
        risk_level=PolicyRiskLevel.LOW,
        reversible=True,
    )


def _permission_stack() -> tuple[
    DomainPermissionRegistry, ApprovalService, DomainPermissionGate
]:
    registry = DomainPermissionRegistry()
    registry.register(build_languages_permission_policy())
    service = ApprovalService(InMemoryApprovalRepository())
    gate = DomainPermissionGate(
        DomainPermissionResolver(registry), service, clock=lambda: NOW
    )
    return registry, service, gate


def _approved_request(service: ApprovalService, pending: object) -> tuple[object, str]:
    from cmm.agent_runtime.domain_permission_contracts import (
        PermissionApprovalRequirement,
    )

    requirement = PermissionApprovalRequirement.from_dict(
        pending.approval_requirements[0]  # type: ignore[attr-defined]
    )
    bridged = to_approval_requirement(requirement, agent_run_id="run-languages-1")
    request = service.create_request_from_requirement(
        bridged, requested_by="agent-runtime"
    )
    service.approve(request.id, "human-approver")
    return requirement, request.id


def test_build_languages_permission_policy_structure() -> None:
    """Verify standard Languages permission policy."""
    policy = build_languages_permission_policy()
    assert isinstance(policy, DomainPermissionPolicy)
    assert (
        policy.policy_id
        == LANGUAGES_PERMISSION_POLICY_ID
        == "domain-permission:languages:1.0.0"
    )
    assert policy.domain_id == "domain:languages"

    # Memory write must be in allowed and approval capabilities, NOT prohibited
    assert PermissionCapability.MEMORY_WRITE in policy.allowed_capabilities
    assert PermissionCapability.MEMORY_WRITE in policy.approval_capabilities
    assert PermissionCapability.MEMORY_WRITE not in policy.prohibited_capabilities
    assert policy.allow_memory_write is True

    # Prohibited capabilities
    for cap in (
        PermissionCapability.COMMUNICATION_EXTERNAL,
        PermissionCapability.FILE_MODIFY,
        PermissionCapability.TASK_CREATE,
        PermissionCapability.SCHEDULE_MODIFY,
        PermissionCapability.FINANCIAL_ACTION,
        PermissionCapability.PERMISSION_MODIFY,
    ):
        assert cap in policy.prohibited_capabilities
        assert cap in LANGUAGES_PROHIBITED_CAPABILITIES

    # Autonomy level is 0
    assert policy.autonomy_limits.maximum_autonomy_level == 0
    assert policy.autonomy_limits.allow_reversible_changes is False
    assert policy.autonomy_limits.allow_irreversible_changes is False


def test_permission_authorization_allows_strict_bool() -> None:
    """Only literal True authorizes; strings, ints, None, and dicts fail."""
    assert permission_authorization_allows(True) is True
    assert permission_authorization_allows("true") is False
    assert permission_authorization_allows(1) is False
    assert permission_authorization_allows({"auth": True}) is False
    assert permission_authorization_allows(None) is False
    assert permission_authorization_allows(False) is False


def test_persistence_confirmation_accepted_no_grant_denied() -> None:
    """No approval grant -> persistence denied."""
    res = persistence_confirmation_accepted(proposal_id="prop-1")
    assert res["accepted"] is False
    assert res["chain_valid"] is False


def test_memory_write_real_approval_lifecycle_is_scoped_and_one_shot() -> None:
    _, service, gate = _permission_stack()
    operation = _memory_write_operation()
    kwargs = {
        "request_id": "languages-memory-write-1",
        "actor_id": "actor-1",
        "session_id": "session-1",
    }

    pending = gate.evaluate_operation_definition(operation, **kwargs)
    assert pending.outcome is PermissionGateOutcome.APPROVAL_REQUIRED
    assert not pending.allowed
    requirement, approval_id = _approved_request(service, pending)
    assert requirement.action is PermissionCapability.MEMORY_WRITE
    assert requirement.actor_id == "actor-1"
    assert requirement.session_id == "session-1"

    consumed = gate.evaluate_operation_definition(
        operation, approval_request_id=approval_id, **kwargs
    )
    assert consumed.outcome is PermissionGateOutcome.APPROVAL_CONSUMED
    assert consumed.allowed
    assert service.repository.is_consumed(approval_id)

    reused = gate.evaluate_operation_definition(
        operation, approval_request_id=approval_id, **kwargs
    )
    assert reused.outcome is PermissionGateOutcome.APPROVAL_DENIED
    assert not reused.allowed


def test_memory_write_wrong_context_and_expiry_do_not_consume_approval() -> None:
    _, service, gate = _permission_stack()
    operation = _memory_write_operation()
    pending = gate.evaluate_operation_definition(
        operation,
        request_id="languages-memory-scope-1",
        actor_id="actor-1",
        session_id="session-1",
    )
    _, approval_id = _approved_request(service, pending)

    for actor_id, session_id in (
        ("actor-2", "session-1"),
        ("actor-1", "session-2"),
    ):
        denied = gate.evaluate_operation_definition(
            operation,
            request_id="languages-memory-scope-1",
            actor_id=actor_id,
            session_id=session_id,
            approval_request_id=approval_id,
        )
        assert denied.outcome is PermissionGateOutcome.APPROVAL_DENIED
        assert not denied.allowed
        assert not service.repository.is_consumed(approval_id)

    stored = service.repository.get_request(approval_id)
    service.repository.update_request(
        ApprovalRequest.from_mapping(
            {**stored.to_dict(), "expires_at": NOW.replace(year=2025).isoformat()}
        )
    )
    expired = gate.evaluate_operation_definition(
        operation,
        request_id="languages-memory-scope-1",
        actor_id="actor-1",
        session_id="session-1",
        approval_request_id=approval_id,
    )
    assert expired.outcome is PermissionGateOutcome.APPROVAL_DENIED
    assert not service.repository.is_consumed(approval_id)


def test_memory_write_policy_is_reevaluated_before_approval_consumption() -> None:
    registry, service, gate = _permission_stack()
    operation = _memory_write_operation()
    kwargs = {
        "request_id": "languages-memory-policy-1",
        "actor_id": "actor-1",
        "session_id": "session-1",
    }
    pending = gate.evaluate_operation_definition(operation, **kwargs)
    _, approval_id = _approved_request(service, pending)

    registry.register(
        dataclasses.replace(
            build_languages_permission_policy(),
            version="2.0.0",
            allowed_capabilities=(),
            approval_capabilities=(),
            prohibited_capabilities=(
                *build_languages_permission_policy().prohibited_capabilities,
                PermissionCapability.MEMORY_WRITE,
            ),
            allow_memory_write=False,
        )
    )
    denied = gate.evaluate_operation_definition(
        operation, approval_request_id=approval_id, **kwargs
    )
    assert denied.outcome is PermissionGateOutcome.DENY
    assert not service.repository.is_consumed(approval_id)


def test_supporting_policy_cannot_widen_languages_memory_write() -> None:
    registry = DomainPermissionRegistry()
    registry.register(build_languages_permission_policy())
    registry.register(
        DomainPermissionPolicy(
            "permissive-support",
            "domain:test-support",
            "1.0.0",
            allowed_capabilities=(PermissionCapability.MEMORY_WRITE,),
            allowed_sensitivity_levels=("internal",),
            allow_memory_write=True,
        )
    )
    request = DomainPermissionRequest(
        "languages-supporting-permission-1",
        PermissionCapability.MEMORY_WRITE,
        "domain:languages",
        "actor-1",
        "session-1",
        sensitivity_level="internal",
    )
    result = DomainPermissionResolver(registry).resolve(
        request, supporting_domains=("domain:test-support",), now=NOW
    )
    assert result.effective_permissions.decision.value == "approval_required"
