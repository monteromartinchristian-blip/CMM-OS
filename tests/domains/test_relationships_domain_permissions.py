"""Tests for Phase 10.21 Relationships Domain permissions."""

from __future__ import annotations

from cmm.agent_runtime.domain_permission_contracts import PermissionCapability
from cmm.domains.relationships.permissions import (
    RELATIONSHIPS_PERMISSION_POLICY_ID,
    build_relationships_permission_policy,
)

_SENSITIVE_RELATIONAL = {
    PermissionCapability.COMMUNICATION_EXTERNAL,
    PermissionCapability.SENSITIVE_INFERENCE,
    PermissionCapability.SENSITIVE_INFERENCE_PERSIST,
    PermissionCapability.EXPORT,
    PermissionCapability.FILE_MODIFY,
    PermissionCapability.IRREVERSIBLE_CHANGE,
    PermissionCapability.KNOWLEDGE_DELETE,
    PermissionCapability.PERMISSION_MODIFY,
    PermissionCapability.MEMORY_WRITE,
    PermissionCapability.DOMAIN_CROSS_ACCESS,
}


def test_policy_identity():
    policy = build_relationships_permission_policy()
    assert policy.policy_id == RELATIONSHIPS_PERMISSION_POLICY_ID
    assert policy.domain_id == "domain:relationships"
    assert policy.enabled is True


def test_allowed_surface_includes_qualified_sensitive_analysis():
    policy = build_relationships_permission_policy()
    assert policy.allowed_capabilities == (
        PermissionCapability.RESOURCE_READ,
        PermissionCapability.MEMORY_READ,
        PermissionCapability.SENSITIVE_INFERENCE,
        PermissionCapability.OPERATION_EXECUTE,
        PermissionCapability.WORKFLOW_EXECUTE,
    )
    assert policy.allow_memory_write is False


def test_relational_effects_and_sensitive_persistence_denied():
    policy = build_relationships_permission_policy()

    assert (
        PermissionCapability.SENSITIVE_INFERENCE
        not in policy.prohibited_capabilities
    )

    for capability in _SENSITIVE_RELATIONAL - {
        PermissionCapability.SENSITIVE_INFERENCE
    }:
        assert capability in policy.prohibited_capabilities
        assert capability not in policy.allowed_capabilities


def test_external_actions_require_approval():
    policy = build_relationships_permission_policy()
    assert policy.allow_external_communication is False
    assert policy.allow_export is False
    assert PermissionCapability.COMMUNICATION_EXTERNAL in policy.approval_capabilities
    assert PermissionCapability.EXPORT in policy.approval_capabilities


def test_no_autonomous_relational_decision_capability():
    """No relational decision/action capability may ever be allowed."""
    policy = build_relationships_permission_policy()
    for capability in (
        PermissionCapability.MEDICAL_DECISION,
        PermissionCapability.MEDICAL_ACTION,
        PermissionCapability.LEGAL_DECISION,
        PermissionCapability.LEGAL_ACTION,
        PermissionCapability.FINANCIAL_DECISION,
        PermissionCapability.FINANCIAL_ACTION,
        PermissionCapability.FINANCIAL_SPEND,
    ):
        assert capability not in policy.allowed_capabilities


def test_no_cross_domain_and_no_autonomy():
    policy = build_relationships_permission_policy()
    assert policy.allow_cross_domain_access is False
    assert policy.autonomy_limits.maximum_autonomy_level == 0
    assert policy.autonomy_limits.allow_irreversible_changes is False
