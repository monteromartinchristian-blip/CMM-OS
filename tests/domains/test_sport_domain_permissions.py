"""Tests for Phase 10.28 Sport Domain Permissions."""

from __future__ import annotations

from cmm.agent_runtime.domain_permission_contracts import PermissionCapability
from cmm.domains.sport.permissions import (
    SPORT_PERMISSION_POLICY_ID,
    build_sport_permission_policy,
)


def test_sport_permission_policy_identity() -> None:
    policy = build_sport_permission_policy()
    assert policy.policy_id == SPORT_PERMISSION_POLICY_ID
    assert policy.domain_id == "domain:sport"
    assert policy.version == "1.0.0"


def test_sport_permission_policy_capabilities() -> None:
    policy = build_sport_permission_policy()
    assert PermissionCapability.RESOURCE_READ in policy.allowed_capabilities
    assert PermissionCapability.OPERATION_EXECUTE in policy.allowed_capabilities
    assert PermissionCapability.WORKFLOW_EXECUTE in policy.allowed_capabilities

    assert PermissionCapability.MEMORY_WRITE in policy.prohibited_capabilities
    assert PermissionCapability.SCHEDULE_MODIFY in policy.prohibited_capabilities
    assert PermissionCapability.COMMUNICATION_EXTERNAL in policy.prohibited_capabilities
    assert PermissionCapability.MEDICAL_DECISION in policy.prohibited_capabilities
    assert PermissionCapability.MEDICAL_ACTION in policy.prohibited_capabilities
    assert PermissionCapability.DOMAIN_CROSS_ACCESS in policy.prohibited_capabilities


def test_sport_permission_policy_flags() -> None:
    policy = build_sport_permission_policy()
    assert policy.allow_memory_read is True
    assert policy.allow_memory_write is False
    assert policy.allow_schedule_modification is False
    assert policy.allow_cross_domain_access is False
    assert policy.autonomy_limits.maximum_autonomy_level == 0
