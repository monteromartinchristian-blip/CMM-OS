"""Tests for Phase 10.26 Languages Domain Permissions."""

from __future__ import annotations

from cmm.agent_runtime.domain_permission_contracts import PermissionCapability
from cmm.domains.languages.permissions import (
    LANGUAGES_PERMISSION_POLICY_ID,
    LANGUAGES_PROHIBITED_CAPABILITIES,
    build_languages_permission_policy,
    permission_authorization_allows,
    persistence_confirmation_accepted,
)
from cmm.domains.permission_contracts import DomainPermissionPolicy


def test_build_languages_permission_policy_structure() -> None:
    """Verify standard Languages permission policy."""
    policy = build_languages_permission_policy()
    assert isinstance(policy, DomainPermissionPolicy)
    assert policy.policy_id == LANGUAGES_PERMISSION_POLICY_ID == "domain-permission:languages:1.0.0"
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
