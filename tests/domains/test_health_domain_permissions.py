"""Tests for Phase 10.20 Health Domain permissions."""

from __future__ import annotations

from cmm.agent_runtime.domain_permission_contracts import PermissionCapability
from cmm.domains.health.permissions import (
    HEALTH_PERMISSION_POLICY_ID,
    build_health_permission_policy,
)

_SENSITIVE_MEDICAL = {
    PermissionCapability.MEDICAL_DECISION,
    PermissionCapability.MEDICAL_ACTION,
    PermissionCapability.SENSITIVE_INFERENCE,
    PermissionCapability.SENSITIVE_INFERENCE_PERSIST,
    PermissionCapability.COMMUNICATION_EXTERNAL,
    PermissionCapability.EXPORT,
    PermissionCapability.FILE_MODIFY,
    PermissionCapability.IRREVERSIBLE_CHANGE,
    PermissionCapability.KNOWLEDGE_DELETE,
    PermissionCapability.PERMISSION_MODIFY,
    PermissionCapability.MEMORY_WRITE,
}


def test_policy_identity():
    policy = build_health_permission_policy()
    assert policy.policy_id == HEALTH_PERMISSION_POLICY_ID
    assert policy.domain_id == "domain:health"
    assert policy.enabled is True


def test_allowed_surface_is_read_only():
    policy = build_health_permission_policy()
    assert policy.allowed_capabilities == (
        PermissionCapability.RESOURCE_READ,
        PermissionCapability.MEMORY_READ,
        PermissionCapability.OPERATION_EXECUTE,
    )
    assert policy.allow_memory_write is False


def test_medical_and_sensitive_capabilities_denied():
    policy = build_health_permission_policy()
    for capability in _SENSITIVE_MEDICAL:
        assert capability in policy.prohibited_capabilities
        assert capability not in policy.allowed_capabilities


def test_external_actions_require_approval():
    policy = build_health_permission_policy()
    assert policy.allow_external_communication is False
    assert policy.allow_external_search is False
    assert policy.allow_export is False
    assert PermissionCapability.COMMUNICATION_EXTERNAL in policy.approval_capabilities
    assert PermissionCapability.EXPORT in policy.approval_capabilities


def test_no_cross_domain_and_no_autonomy():
    policy = build_health_permission_policy()
    assert policy.allow_cross_domain_access is False
    assert policy.autonomy_limits.maximum_autonomy_level == 0
    assert policy.autonomy_limits.allow_irreversible_changes is False
