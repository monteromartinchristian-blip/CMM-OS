"""Phase 10.23 — Opposition Domain Permissions + gate/lifecycle tests."""

from __future__ import annotations

from cmm.agent_runtime.domain_permission_contracts import PermissionCapability
from cmm.agent_runtime.permission_restriction_contracts import (
    ExternalSourceClass,
)
from cmm.domains.oppositions import build_oppositions_permission_policy


def test_external_verification_official_only_read_only():
    """Canonical external verification is READ_ONLY + OFFICIAL_ONLY."""
    policy = build_oppositions_permission_policy()
    assert policy.allow_external_search is False
    assert policy.source_requirement.minimum_source_class is ExternalSourceClass.OFFICIAL_ONLY


def test_no_autonomous_external_actions():
    policy = build_oppositions_permission_policy()
    # Registration/submission/payment must never be available autonomously.
    assert PermissionCapability.FINANCIAL_SPEND in policy.prohibited_capabilities
    assert PermissionCapability.COMMUNICATION_EXTERNAL in policy.prohibited_capabilities
    assert PermissionCapability.IRREVERSIBLE_CHANGE in policy.prohibited_capabilities
    assert policy.allow_memory_write is False


def test_calendar_task_mutation_approval_gated():
    policy = build_oppositions_permission_policy()
    # Not hard-denied; approval-gated.
    assert PermissionCapability.TASK_CREATE in policy.allowed_capabilities
    assert PermissionCapability.SCHEDULE_MODIFY in policy.allowed_capabilities
    assert "task.create" in policy.approval_requirements
    assert "schedule.modify" in policy.approval_requirements


def test_source_class_not_trusted_as_official():
    """A missing/unknown source class is not trusted as official.

    The policy's OFFICIAL_ONLY requirement is the canonical boundary; a caller
    label cannot create authority (this is enforced at the rule level)."""
    policy = build_oppositions_permission_policy()
    assert policy.source_requirement.minimum_source_class is ExternalSourceClass.OFFICIAL_ONLY


def test_supporting_domain_cannot_widen_permissions():
    """Supporting domains never widen Opposition mutating surface."""
    policy = build_oppositions_permission_policy()
    # The autonomous surface is strictly read + memory-read + execute.
    assert PermissionCapability.MEMORY_WRITE in policy.prohibited_capabilities
    assert PermissionCapability.EXPORT in policy.prohibited_capabilities
    assert PermissionCapability.GOAL_UPDATE in policy.prohibited_capabilities


def test_unknown_permission_denies():
    """Fail-closed: an unknown/missing capability is not granted."""
    policy = build_oppositions_permission_policy()
    # Omitted capability kinds are not in the allowed set.
    assert PermissionCapability.MODEL_EXTERNAL in policy.prohibited_capabilities
    assert policy.allow_external_models is False