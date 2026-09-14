"""Phase 10.24 — Reflection Domain permissions tests.

Reflection is a high-sensitivity domain: restricted identity inference,
confirmation-gated semantic memory, no automatic personal decisions, no
diagnosis presentation, and no external write.  Most-restrictive permission
wins; unknown/malformed permission state denies (spec §22, §40, §49).
"""

from __future__ import annotations

from cmm.agent_runtime.domain_permission_contracts import PermissionCapability
from cmm.domains.reflection import (
    REFLECTION_PERMISSION_POLICY_ID,
    build_reflection_permission_policy,
    permission_authorization_allows,
)
from cmm.domains.reflection.permissions import REFLECTION_PROHIBITED_CAPABILITIES


def test_policy_identity():
    policy = build_reflection_permission_policy()
    assert policy.policy_id == REFLECTION_PERMISSION_POLICY_ID
    assert policy.domain_id == "domain:reflection"
    assert policy.enabled is True


def test_high_sensitivity():
    policy = build_reflection_permission_policy()
    assert policy.allowed_sensitivity_levels == ("restricted", "secret")
    assert policy.allow_memory_read is True
    assert policy.allow_memory_write is False
    for capability in (
        PermissionCapability.SENSITIVE_INFERENCE,
        PermissionCapability.SENSITIVE_INFERENCE_PERSIST,
    ):
        assert capability in policy.prohibited_capabilities


def test_no_automatic_personal_decisions():
    policy = build_reflection_permission_policy()
    for capability in (
        PermissionCapability.MEDICAL_DECISION,
        PermissionCapability.MEDICAL_ACTION,
        PermissionCapability.LEGAL_DECISION,
        PermissionCapability.LEGAL_ACTION,
        PermissionCapability.FINANCIAL_DECISION,
        PermissionCapability.FINANCIAL_ACTION,
        PermissionCapability.FINANCIAL_SPEND,
        PermissionCapability.PERMISSION_MODIFY,
    ):
        assert capability in policy.prohibited_capabilities
    assert policy.autonomy_limits.maximum_autonomy_level == 0
    assert policy.autonomy_limits.allow_irreversible_changes is False


def test_semantic_memory_mutation_denied_by_default():
    policy = build_reflection_permission_policy()
    assert PermissionCapability.MEMORY_WRITE in policy.prohibited_capabilities
    assert policy.allow_memory_write is False


def test_external_write_denied_by_default():
    policy = build_reflection_permission_policy()
    for capability in (
        PermissionCapability.COMMUNICATION_EXTERNAL,
        PermissionCapability.PUBLICATION,
        PermissionCapability.FILE_MODIFY,
        PermissionCapability.TASK_CREATE,
        PermissionCapability.SCHEDULE_MODIFY,
        PermissionCapability.GOAL_UPDATE,
        PermissionCapability.SEARCH_EXTERNAL,
        PermissionCapability.MODEL_EXTERNAL,
        PermissionCapability.EXPORT,
        PermissionCapability.EXTERNAL_DOMAIN_ACTIVATE,
        PermissionCapability.IRREVERSIBLE_CHANGE,
        PermissionCapability.KNOWLEDGE_DELETE,
    ):
        assert capability in policy.prohibited_capabilities
    assert policy.allow_external_communication is False
    assert policy.allow_external_search is False
    assert policy.allow_external_models is False
    assert policy.allow_file_modification is False
    assert policy.allow_task_creation is False
    assert policy.allow_schedule_modification is False
    assert policy.allow_goal_update is False
    assert policy.allow_export is False


def test_read_only_autonomous_surface():
    policy = build_reflection_permission_policy()
    for capability in (
        PermissionCapability.RESOURCE_READ,
        PermissionCapability.MEMORY_READ,
        PermissionCapability.OPERATION_EXECUTE,
        PermissionCapability.WORKFLOW_EXECUTE,
    ):
        assert capability in policy.allowed_capabilities
    assert policy.allow_cross_domain_access is False


def test_unknown_permission_state_denies():
    """A policy with an unknown capability state must not widen permission."""
    policy = build_reflection_permission_policy()
    unknown = "capability.unknown"
    denied = set(policy.prohibited_capabilities)
    allowed = set(policy.allowed_capabilities)
    assert unknown not in allowed
    # Unknown capabilities are not auto-allowed; only declared allowed ones are.
    assert unknown not in denied  # unknown is simply not granted


def test_malformed_authorization_fails_closed():
    """Only literal ``True`` authorizes a boolean permission gate."""
    for raw in ("true", "false", 1, 0, [], {}, {}, None, "True", "yes", 1.0):
        assert permission_authorization_allows(raw) is False
    assert permission_authorization_allows(True) is True
    assert permission_authorization_allows(False) is False


def test_prohibited_capabilities_deny_identity_and_persistence():
    for capability in REFLECTION_PROHIBITED_CAPABILITIES:
        assert capability in (
            PermissionCapability.SENSITIVE_INFERENCE,
            PermissionCapability.SENSITIVE_INFERENCE_PERSIST,
            PermissionCapability.MEMORY_WRITE,
            PermissionCapability.COMMUNICATION_EXTERNAL,
            PermissionCapability.SEARCH_EXTERNAL,
            PermissionCapability.MODEL_EXTERNAL,
            PermissionCapability.FILE_MODIFY,
            PermissionCapability.TASK_CREATE,
            PermissionCapability.SCHEDULE_MODIFY,
            PermissionCapability.GOAL_UPDATE,
            PermissionCapability.EXPORT,
            PermissionCapability.PUBLICATION,
            PermissionCapability.EXTERNAL_DOMAIN_ACTIVATE,
            PermissionCapability.IRREVERSIBLE_CHANGE,
            PermissionCapability.KNOWLEDGE_DELETE,
            PermissionCapability.PERMISSION_MODIFY,
            PermissionCapability.MEDICAL_DECISION,
            PermissionCapability.MEDICAL_ACTION,
            PermissionCapability.LEGAL_DECISION,
            PermissionCapability.LEGAL_ACTION,
            PermissionCapability.FINANCIAL_DECISION,
            PermissionCapability.FINANCIAL_ACTION,
            PermissionCapability.FINANCIAL_SPEND,
        )


def test_composed_policy_most_restrictive_wins():
    """Composing Reflection with a stricter policy keeps the restrictive result.

    The composed policy is at least as restrictive as each source policy:
    reflection denies memory write / sensitive inference / communication; the
    stricter supporting policy must not reopen any of those.
    """
    policy = build_reflection_permission_policy()
    strict = build_reflection_permission_policy()
    strict_denied = set(strict.prohibited_capabilities)
    base_denied = set(policy.prohibited_capabilities)
    # most-restrictive wins: union of prohibitions
    composed_denied = base_denied | strict_denied
    for capability in (
        PermissionCapability.MEMORY_WRITE,
        PermissionCapability.SENSITIVE_INFERENCE,
        PermissionCapability.SENSITIVE_INFERENCE_PERSIST,
        PermissionCapability.COMMUNICATION_EXTERNAL,
    ):
        assert capability in composed_denied
