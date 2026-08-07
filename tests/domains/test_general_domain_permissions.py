"""Tests for General Domain permissions."""

from __future__ import annotations

from cmm.agent_runtime.domain_permission_contracts import PermissionCapability
from cmm.domains.general import (
    GENERAL_PERMISSION_POLICY_ID,
    build_general_permission_policy,
)
from cmm.domains.permission_contracts import DomainPermissionPolicy


def test_policy_id():
    policy = build_general_permission_policy()
    assert policy.policy_id == GENERAL_PERMISSION_POLICY_ID


def test_policy_domain():
    policy = build_general_permission_policy()
    assert policy.domain_id == "domain:general"


def test_policy_version():
    policy = build_general_permission_policy()
    assert policy.version == "1.0.0"


def test_allowed_capabilities():
    policy = build_general_permission_policy()
    assert PermissionCapability.RESOURCE_READ in policy.allowed_capabilities
    assert PermissionCapability.MEMORY_READ in policy.allowed_capabilities
    assert PermissionCapability.OPERATION_EXECUTE in policy.allowed_capabilities


def test_prohibited_capabilities():
    policy = build_general_permission_policy()
    assert PermissionCapability.SEARCH_EXTERNAL in policy.prohibited_capabilities
    assert PermissionCapability.MODEL_EXTERNAL in policy.prohibited_capabilities
    assert PermissionCapability.MEMORY_WRITE in policy.prohibited_capabilities
    assert PermissionCapability.FILE_MODIFY in policy.prohibited_capabilities
    assert PermissionCapability.SCHEDULE_MODIFY in policy.prohibited_capabilities
    assert PermissionCapability.TASK_CREATE in policy.prohibited_capabilities
    assert PermissionCapability.COMMUNICATION_EXTERNAL in policy.prohibited_capabilities
    assert PermissionCapability.SENSITIVE_INFERENCE in policy.prohibited_capabilities
    assert PermissionCapability.EXPORT in policy.prohibited_capabilities


def test_approval_capabilities():
    policy = build_general_permission_policy()
    assert PermissionCapability.TASK_CREATE in policy.approval_capabilities
    assert PermissionCapability.GOAL_UPDATE in policy.approval_capabilities


def test_memory_policy():
    policy = build_general_permission_policy()
    assert policy.allow_memory_read is True
    assert policy.allow_memory_write is False


def test_external_actions_denied():
    policy = build_general_permission_policy()
    assert policy.allow_external_search is False
    assert policy.allow_external_models is False
    assert policy.allow_external_communication is False


def test_file_and_schedule_denied():
    policy = build_general_permission_policy()
    assert policy.allow_file_modification is False
    assert policy.allow_schedule_modification is False


def test_task_and_goal_denied():
    policy = build_general_permission_policy()
    assert policy.allow_task_creation is False
    assert policy.allow_goal_update is False


def test_autonomy_limits():
    policy = build_general_permission_policy()
    assert policy.autonomy_limits.maximum_autonomy_level == 1
    assert policy.autonomy_limits.allow_reversible_changes is False
    assert policy.autonomy_limits.allow_irreversible_changes is False


def test_policy_serialization_round_trip():
    policy = build_general_permission_policy()
    restored = DomainPermissionPolicy.from_dict(policy.to_dict())
    assert restored.policy_id == policy.policy_id
    assert restored.domain_id == policy.domain_id


def test_policy_deterministic():
    a = build_general_permission_policy()
    b = build_general_permission_policy()
    assert a.to_dict() == b.to_dict()


def test_policy_can_be_registered():
    from cmm.domains.permission_registry import DomainPermissionRegistry

    registry = DomainPermissionRegistry()
    policy = build_general_permission_policy()
    registry.register(policy)
    assert registry.get(GENERAL_PERMISSION_POLICY_ID) == policy


def test_most_restrictive_wins():
    policy = build_general_permission_policy()
    # General Domain cannot expand permissions beyond its own policy
    assert PermissionCapability.SEARCH_EXTERNAL in policy.prohibited_capabilities
    assert PermissionCapability.MEMORY_WRITE in policy.prohibited_capabilities