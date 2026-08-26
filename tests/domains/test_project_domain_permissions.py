"""Phase 10.30 — Project Domain Permissions Tests."""

from __future__ import annotations

from cmm.agent_runtime.approval_repository import InMemoryApprovalRepository
from cmm.agent_runtime.approval_service import ApprovalService
from cmm.agent_runtime.domain_permission_contracts import (
    PermissionCapability,
    PermissionOutcome,
)
from cmm.domains.permission_contracts import (
    DomainPermissionPolicy,
    DomainPermissionRequest,
)
from cmm.domains.permission_gate import DomainPermissionGate, PermissionGateOutcome
from cmm.domains.permission_registry import DomainPermissionRegistry
from cmm.domains.permission_resolution import DomainPermissionResolver
from cmm.domains.project.operations import build_project_operation_definitions
from cmm.domains.project.permissions import (
    PROJECT_PERMISSION_POLICY_ID,
    PROJECT_PROHIBITED_CAPABILITIES,
    build_project_permission_policy,
    permission_authorization_allows,
)


def test_project_permission_policy_identity_and_autonomy() -> None:
    policy = build_project_permission_policy()
    assert isinstance(policy, DomainPermissionPolicy)
    assert policy.policy_id == PROJECT_PERMISSION_POLICY_ID
    assert policy.domain_id == "domain:project"
    assert policy.autonomy_limits.maximum_autonomy_level == 1
    assert policy.autonomy_limits.allow_reversible_changes is True
    assert policy.autonomy_limits.allow_irreversible_changes is False


def test_baseline_and_prohibited_capabilities() -> None:
    policy = build_project_permission_policy()

    # Allowed baseline
    assert PermissionCapability.RESOURCE_READ in policy.allowed_capabilities
    assert PermissionCapability.MEMORY_READ in policy.allowed_capabilities
    assert PermissionCapability.OPERATION_EXECUTE in policy.allowed_capabilities
    assert PermissionCapability.WORKFLOW_EXECUTE in policy.allowed_capabilities
    assert PermissionCapability.FILE_MODIFY in policy.allowed_capabilities

    # Approval required for FILE_MODIFY
    assert PermissionCapability.FILE_MODIFY in policy.approval_capabilities

    # Prohibited
    for prohibited in (
        PermissionCapability.IRREVERSIBLE_CHANGE,
        PermissionCapability.PERMISSION_MODIFY,
        PermissionCapability.COMMUNICATION_EXTERNAL,
        PermissionCapability.PUBLICATION,
        PermissionCapability.FINANCIAL_ACTION,
        PermissionCapability.FINANCIAL_SPEND,
        PermissionCapability.SEARCH_EXTERNAL,
        PermissionCapability.MODEL_EXTERNAL,
        PermissionCapability.KNOWLEDGE_DELETE,
    ):
        assert prohibited in policy.prohibited_capabilities
        assert prohibited in PROJECT_PROHIBITED_CAPABILITIES


def test_permission_authorization_allows_strict() -> None:
    assert permission_authorization_allows(True) is True
    assert permission_authorization_allows(False) is False
    assert permission_authorization_allows(1) is False
    assert permission_authorization_allows("true") is False
    assert permission_authorization_allows({"authorized": True}) is False
    assert permission_authorization_allows(None) is False


def test_permission_resolution_requires_approval_for_file_modify() -> None:
    policy = build_project_permission_policy()
    registry = DomainPermissionRegistry()
    registry.register(policy)

    resolver = DomainPermissionResolver(registry)

    # Request FILE_MODIFY without approval
    request = DomainPermissionRequest(
        request_id="req:1",
        action=PermissionCapability.FILE_MODIFY,
        domain_id="domain:project",
        actor_id="actor:test",
        session_id="session:test",
    )
    resolution = resolver.resolve(request)
    assert (
        resolution.effective_permissions.decision is PermissionOutcome.APPROVAL_REQUIRED
    )


def test_forged_approval_rejected() -> None:
    policy = build_project_permission_policy()
    registry = DomainPermissionRegistry()
    registry.register(policy)

    resolver = DomainPermissionResolver(registry)
    approval_service = ApprovalService(InMemoryApprovalRepository())
    gate = DomainPermissionGate(resolver, approval_service=approval_service)

    ops = {op.operation_id: op for op in build_project_operation_definitions()}
    modify_op = ops["project.modify_code"]

    # Caller-forged approval request without valid approval in ApprovalService
    result = gate.evaluate_operation_definition(
        modify_op,
        request_id="req:1",
        actor_id="actor:test",
        session_id="session:test",
        approval_request_id="forged_approval_id",
    )
    assert result.outcome in (
        PermissionGateOutcome.APPROVAL_DENIED,
        PermissionGateOutcome.APPROVAL_REQUIRED,
        PermissionGateOutcome.DENY,
    )
