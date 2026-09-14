"""Tests for Phase 10.22 University Domain permissions."""

from __future__ import annotations

from cmm.agent_runtime.domain_permission_contracts import PermissionCapability
from cmm.domains.university.permissions import (
    UNIVERSITY_PERMISSION_POLICY_ID,
    build_university_permission_policy,
)

_SENSITIVE_ACADEMIC = {
    PermissionCapability.COMMUNICATION_EXTERNAL,
    PermissionCapability.SENSITIVE_INFERENCE,
    PermissionCapability.SENSITIVE_INFERENCE_PERSIST,
    PermissionCapability.EXPORT,
    PermissionCapability.FILE_MODIFY,
    PermissionCapability.IRREVERSIBLE_CHANGE,
    PermissionCapability.KNOWLEDGE_DELETE,
    PermissionCapability.PERMISSION_MODIFY,
    PermissionCapability.MEMORY_WRITE,
}


def test_policy_identity():
    policy = build_university_permission_policy()
    assert policy.policy_id == UNIVERSITY_PERMISSION_POLICY_ID
    assert policy.domain_id == "domain:university"
    assert policy.enabled is True


def test_allowed_surface_is_read_only():
    policy = build_university_permission_policy()
    # The autonomous core is read + memory-read + execute.  Three narrow,
    # authorization-enriched paths are additionally allowed but never
    # autonomous: external verification is OFFICIAL_ONLY-gated, and
    # task/schedule mutation is approval-gated.
    assert policy.allowed_capabilities == (
        PermissionCapability.RESOURCE_READ,
        PermissionCapability.MEMORY_READ,
        PermissionCapability.OPERATION_EXECUTE,
        PermissionCapability.WORKFLOW_EXECUTE,
        PermissionCapability.SEARCH_EXTERNAL,
        PermissionCapability.TASK_CREATE,
        PermissionCapability.SCHEDULE_MODIFY,
    )
    assert policy.allow_memory_write is False
    # The deny-by-default intent is not lost: the narrow paths are gated, not
    # auto-granted.
    assert policy.allow_task_creation is False
    assert policy.allow_schedule_modification is False
    assert policy.allow_external_search is False
    assert policy.source_requirement is not None


def test_academic_and_sensitive_capabilities_denied():
    policy = build_university_permission_policy()
    for capability in _SENSITIVE_ACADEMIC:
        assert capability in policy.prohibited_capabilities
        assert capability not in policy.allowed_capabilities


def test_calendar_and_task_denied():
    """Calendar/task mutation is denied by default and approval-gated, not
    hard-denied: the capability is allowed only with a valid scoped approval
    and never auto-granted."""
    policy = build_university_permission_policy()
    assert policy.allow_schedule_modification is False
    assert policy.allow_task_creation is False
    # Approval-gated, not hard-denied: the capability is in the allowed set AND
    # requires a scoped approval before it may execute.
    assert PermissionCapability.SCHEDULE_MODIFY in policy.allowed_capabilities
    assert PermissionCapability.TASK_CREATE in policy.allowed_capabilities
    assert PermissionCapability.SCHEDULE_MODIFY in policy.approval_capabilities
    assert PermissionCapability.TASK_CREATE in policy.approval_capabilities
    assert PermissionCapability.SCHEDULE_MODIFY not in policy.prohibited_capabilities
    assert PermissionCapability.TASK_CREATE not in policy.prohibited_capabilities


def test_external_actions_require_approval():
    policy = build_university_permission_policy()
    assert policy.allow_external_communication is False
    assert policy.allow_export is False
    assert PermissionCapability.COMMUNICATION_EXTERNAL in policy.approval_capabilities
    assert PermissionCapability.EXPORT in policy.approval_capabilities


def test_no_academic_decision_capability():
    """No decision/action capability may ever be allowed."""
    policy = build_university_permission_policy()
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
    policy = build_university_permission_policy()
    assert policy.allow_cross_domain_access is False
    assert policy.autonomy_limits.maximum_autonomy_level == 0
    assert policy.autonomy_limits.allow_irreversible_changes is False
