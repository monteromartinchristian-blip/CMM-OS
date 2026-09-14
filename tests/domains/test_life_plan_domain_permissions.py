"""Tests for Phase 10.29 Life Plan Domain Permissions."""

from __future__ import annotations

from cmm.agent_runtime.domain_permission_contracts import PermissionCapability
from cmm.domains.life_plan.catalog import LIFE_PLAN_RESOURCE_KINDS
from cmm.domains.life_plan.permissions import (
    LIFE_PLAN_PERMISSION_POLICY_ID,
    LIFE_PLAN_PROHIBITED_CAPABILITIES,
    build_life_plan_permission_policy,
    permission_authorization_allows,
)


def test_life_plan_permission_policy_properties() -> None:
    policy = build_life_plan_permission_policy()
    assert policy.policy_id == LIFE_PLAN_PERMISSION_POLICY_ID
    assert policy.policy_id == "domain-permission:life-plan:1.0.0"
    assert str(policy.domain_id) == "domain:life-plan"
    assert policy.version == "1.0.0"
    assert policy.enabled is True
    assert policy.allowed_resource_kinds == LIFE_PLAN_RESOURCE_KINDS

    # Prohibitions
    for cap in (
        PermissionCapability.MEMORY_WRITE,
        PermissionCapability.COMMUNICATION_EXTERNAL,
        PermissionCapability.FINANCIAL_SPEND,
        PermissionCapability.FINANCIAL_ACTION,
        PermissionCapability.IRREVERSIBLE_CHANGE,
    ):
        assert cap in policy.prohibited_capabilities
        assert cap not in policy.allowed_capabilities

    assert policy.prohibited_capabilities == LIFE_PLAN_PROHIBITED_CAPABILITIES

    # Capabilities
    assert PermissionCapability.RESOURCE_READ in policy.allowed_capabilities
    assert PermissionCapability.MEMORY_READ in policy.allowed_capabilities
    assert PermissionCapability.OPERATION_EXECUTE in policy.allowed_capabilities
    assert PermissionCapability.WORKFLOW_EXECUTE in policy.allowed_capabilities

    # Fail closed direct settings
    assert policy.allow_memory_read is True
    assert policy.allow_memory_write is False
    assert policy.allow_external_communication is False
    assert policy.allow_cross_domain_access is False
    assert policy.allow_inbound_cross_domain_access is True


def test_permission_authorization_allows() -> None:
    assert permission_authorization_allows(True) is True
    assert permission_authorization_allows(False) is False
    assert permission_authorization_allows(None) is False
    assert permission_authorization_allows("authorized") is False
    assert permission_authorization_allows(1) is False
