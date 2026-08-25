"""Tests for Phase 10.27 Parenthood Domain Permissions."""

from __future__ import annotations

from cmm.agent_runtime.domain_permission_contracts import PermissionCapability
from cmm.domains.parenthood.permissions import (
    PARENTHOOD_PERMISSION_POLICY_ID,
    PARENTHOOD_PROHIBITED_CAPABILITIES,
    build_parenthood_permission_policy,
    permission_authorization_allows,
    persistence_confirmation_accepted,
)


def test_parenthood_permission_constants() -> None:
    """Verify permission policy ID and prohibited capabilities."""
    assert PARENTHOOD_PERMISSION_POLICY_ID == "domain-permission:parenthood:1.0.0"
    assert PermissionCapability.MEMORY_WRITE in PARENTHOOD_PROHIBITED_CAPABILITIES
    assert (
        PermissionCapability.COMMUNICATION_EXTERNAL
        in PARENTHOOD_PROHIBITED_CAPABILITIES
    )
    assert PermissionCapability.MEDICAL_DECISION in PARENTHOOD_PROHIBITED_CAPABILITIES
    assert PermissionCapability.MEDICAL_ACTION in PARENTHOOD_PROHIBITED_CAPABILITIES
    assert PermissionCapability.LEGAL_DECISION in PARENTHOOD_PROHIBITED_CAPABILITIES
    assert PermissionCapability.LEGAL_ACTION in PARENTHOOD_PROHIBITED_CAPABILITIES
    assert PermissionCapability.FINANCIAL_DECISION in PARENTHOOD_PROHIBITED_CAPABILITIES
    assert PermissionCapability.FINANCIAL_ACTION in PARENTHOOD_PROHIBITED_CAPABILITIES
    assert PermissionCapability.FINANCIAL_SPEND in PARENTHOOD_PROHIBITED_CAPABILITIES


def test_parenthood_permission_policy_construction() -> None:
    """Verify fail-closed policy configuration."""
    policy = build_parenthood_permission_policy()
    assert policy.policy_id == PARENTHOOD_PERMISSION_POLICY_ID
    assert policy.domain_id == "domain:parenthood"
    assert policy.version == "1.0.0"

    # Allowed capabilities
    assert PermissionCapability.RESOURCE_READ in policy.allowed_capabilities
    assert PermissionCapability.MEMORY_READ in policy.allowed_capabilities
    assert PermissionCapability.SENSITIVE_INFERENCE in policy.allowed_capabilities
    assert PermissionCapability.OPERATION_EXECUTE in policy.allowed_capabilities
    assert PermissionCapability.WORKFLOW_EXECUTE in policy.allowed_capabilities

    # Policy flags
    assert policy.allow_memory_read is True
    assert policy.allow_memory_write is False
    assert policy.allow_external_search is False
    assert policy.allow_external_models is False
    assert policy.allow_external_communication is False
    assert policy.allow_file_modification is False
    assert policy.allow_task_creation is False
    assert policy.allow_schedule_modification is False
    assert policy.allow_goal_update is False
    assert policy.allow_export is False
    assert policy.allow_sensitive_inference is True
    assert policy.allow_cross_domain_access is False
    assert policy.autonomy_limits.maximum_autonomy_level == 0
    assert policy.autonomy_limits.allow_reversible_changes is False
    assert policy.autonomy_limits.allow_irreversible_changes is False


def test_permission_authorization_allows() -> None:
    """Verify strict boolean authorization (truthy values rejected)."""
    assert permission_authorization_allows(True) is True
    assert permission_authorization_allows(False) is False
    assert permission_authorization_allows(1) is False
    assert permission_authorization_allows("True") is False
    assert permission_authorization_allows(["yes"]) is False
    assert permission_authorization_allows(None) is False


def test_persistence_confirmation_accepted_fail_closed() -> None:
    """Verify memory persistence rejects unapproved/unbound requests."""
    res = persistence_confirmation_accepted(proposal_id="prop-123")
    assert res["accepted"] is False
    assert res["chain_valid"] is False
