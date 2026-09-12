"""Phase 10.52 — Mental Health permissions tests.

Mental Health is a high-sensitivity personal domain: fail-closed permissions
with literal-True boolean authorization, deny-by-default on every sensitive
capability exposed by the shared enum, explicit capability separation, and
most-restrictive-wins composition.  The policy never grants cross-domain,
export or communication authority.
"""

from __future__ import annotations

import json

from cmm.agent_runtime.domain_permission_contracts import (
    PermissionCapability,
    PermissionOutcome,
)
from cmm.cognitive.enums import SensitivityLevel
from cmm.domains.mental_health.permissions import (
    MENTAL_HEALTH_CAPABILITY_SEPARATION,
    MENTAL_HEALTH_PERMISSION_POLICY_ID,
    build_mental_health_permission_policy,
    permission_authorization_allows,
)
from cmm.domains.permission_contracts import DomainPermissionRequest
from cmm.domains.permission_registry import DomainPermissionRegistry
from cmm.domains.permission_resolution import DomainPermissionResolver


def _registry(*policies) -> DomainPermissionRegistry:
    registry = DomainPermissionRegistry()
    for policy in policies:
        registry.register(policy)
    return registry


def _request(capability, *, domain_id="domain:mental-health", **overrides):
    values = {
        "request_id": "req-1",
        "action": capability,
        "domain_id": domain_id,
        "actor_id": "user-1",
        "session_id": "session-1",
        "sensitivity_level": SensitivityLevel.RESTRICTED,
    }
    values.update(overrides)
    return DomainPermissionRequest(**values)


def test_policy_identity_is_canonical():
    policy = build_mental_health_permission_policy()
    assert policy.policy_id == MENTAL_HEALTH_PERMISSION_POLICY_ID
    assert MENTAL_HEALTH_PERMISSION_POLICY_ID == (
        "domain-permission:mental-health:1.0.0"
    )
    assert str(policy.domain_id) == "domain:mental-health"
    assert policy.version == "1.0.0"
    assert policy.enabled is True


def test_read_is_allowed_but_write_is_not_automatic():
    policy = build_mental_health_permission_policy()
    assert policy.allow_memory_read is True
    assert policy.allow_memory_write is False
    assert policy.allow_external_communication is False
    assert policy.allow_export is False
    assert policy.allow_cross_domain_access is False


def test_sensitive_paths_require_approval_and_are_not_automatic():
    policy = build_mental_health_permission_policy()
    for capability in (
        PermissionCapability.MEMORY_WRITE,
        PermissionCapability.SENSITIVE_INFERENCE_PERSIST,
        PermissionCapability.EXPORT,
        PermissionCapability.COMMUNICATION_EXTERNAL,
        PermissionCapability.DOMAIN_CROSS_ACCESS,
    ):
        assert capability in policy.approval_capabilities
        assert capability in policy.prohibited_capabilities
    assert "memory.persist" in policy.approval_requirements
    assert "export" in policy.approval_requirements


def test_deny_by_default_sensitive_capabilities():
    policy = build_mental_health_permission_policy()
    for capability in (
        PermissionCapability.MEMORY_WRITE,
        PermissionCapability.FILE_MODIFY,
        PermissionCapability.TASK_CREATE,
        PermissionCapability.SCHEDULE_MODIFY,
        PermissionCapability.GOAL_UPDATE,
        PermissionCapability.COMMUNICATION_EXTERNAL,
        PermissionCapability.SENSITIVE_INFERENCE_PERSIST,
        PermissionCapability.EXPORT,
        PermissionCapability.PUBLICATION,
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
        PermissionCapability.EXTERNAL_DOMAIN_ACTIVATE,
    ):
        assert capability in policy.prohibited_capabilities


def test_capability_separation_is_explicit():
    """read != infer != propose persistence != persist != transfer/export/
    communicate != external mutation."""
    for stage in (
        "read",
        "infer",
        "propose_persistence",
        "persist",
        "transfer",
        "export",
        "communicate",
        "external_mutation",
    ):
        assert stage in MENTAL_HEALTH_CAPABILITY_SEPARATION
    assert (
        MENTAL_HEALTH_CAPABILITY_SEPARATION["persist"]
        != MENTAL_HEALTH_CAPABILITY_SEPARATION["read"]
    )
    # Inference is permitted; persisting it is denied.
    policy = build_mental_health_permission_policy()
    assert PermissionCapability.SENSITIVE_INFERENCE in policy.allowed_capabilities
    assert (
        PermissionCapability.SENSITIVE_INFERENCE_PERSIST
        in policy.prohibited_capabilities
    )
    # Reading memory is allowed but never implies write authority.
    assert PermissionCapability.MEMORY_READ in policy.allowed_capabilities
    assert PermissionCapability.MEMORY_WRITE in policy.prohibited_capabilities


def test_authorization_requires_literal_true():
    assert permission_authorization_allows(True) is True
    for value in (False, 1, 0, "true", "True", [], {}, None, object()):
        assert permission_authorization_allows(value) is False


def test_unavailable_by_default_and_autonomy_is_zero():
    policy = build_mental_health_permission_policy()
    limits = policy.autonomy_limits
    assert limits.maximum_autonomy_level == 0
    assert limits.allow_reversible_changes is False
    assert limits.allow_irreversible_changes is False


def test_memory_write_resolves_denied_through_canonical_resolver():
    policy = build_mental_health_permission_policy()
    resolver = DomainPermissionResolver(_registry(policy))
    resolution = resolver.resolve(_request(PermissionCapability.MEMORY_WRITE))
    assert resolution.effective_permissions.decision is PermissionOutcome.DENY


def test_export_and_external_communication_resolve_denied():
    policy = build_mental_health_permission_policy()
    resolver = DomainPermissionResolver(_registry(policy))
    for capability in (
        PermissionCapability.EXPORT,
        PermissionCapability.COMMUNICATION_EXTERNAL,
        PermissionCapability.SENSITIVE_INFERENCE_PERSIST,
    ):
        resolution = resolver.resolve(_request(capability))
        assert resolution.effective_permissions.decision is PermissionOutcome.DENY


def test_memory_read_resolves_allowed_through_canonical_resolver():
    policy = build_mental_health_permission_policy()
    resolver = DomainPermissionResolver(_registry(policy))
    resolution = resolver.resolve(_request(PermissionCapability.MEMORY_READ))
    assert resolution.effective_permissions.decision is PermissionOutcome.ALLOW


def test_serialization_round_trip_is_deterministic():
    policy = build_mental_health_permission_policy()
    payload = policy.to_dict()
    assert json.loads(json.dumps(payload, sort_keys=True)) == payload
    assert policy.metadata["phase"] == "10.52"


# ── Authority downgrade revalidation (Task 9) ────────────────────────────────


def _downgraded_policy():
    from dataclasses import replace

    policy = build_mental_health_permission_policy()
    return replace(
        policy,
        policy_id="domain-permission:mental-health:1.1.0",
        version="1.1.0",
        allowed_capabilities=(
            PermissionCapability.MEMORY_READ,
            PermissionCapability.OPERATION_EXECUTE,
        ),
        prohibited_capabilities=policy.prohibited_capabilities
        + (PermissionCapability.SENSITIVE_INFERENCE,),
        allow_sensitive_inference=False,
    )


def test_authority_downgrade_is_revalidated_and_fails_closed():
    """BEFORE=ALLOW / AFTER=DENY / STALE_AUTHORITY_REUSED=NO.

    A previously valid resolution does not grant permanent authority: the
    canonical resolver reads current registry state, so a later boundary sees
    the more restrictive policy and denies.
    """
    registry = _registry(build_mental_health_permission_policy())
    resolver = DomainPermissionResolver(registry)

    before = resolver.resolve(_request(PermissionCapability.SENSITIVE_INFERENCE))
    assert before.effective_permissions.decision is PermissionOutcome.ALLOW

    # Authority becomes more restrictive after the initial resolution.
    registry.register(_downgraded_policy())

    after = resolver.resolve(_request(PermissionCapability.SENSITIVE_INFERENCE))
    assert after.effective_permissions.decision is PermissionOutcome.DENY
    # The stale ALLOW result is not reused: the effective policy is the new one.
    assert any(str(policy.version) == "1.1.0" for policy in after.domain_policies)
    assert all(str(policy.version) != "1.0.0" for policy in after.domain_policies)


def test_privacy_downgrade_stays_denied_after_composition():
    from cmm.cognitive.privacy import (
        PrivacyMetadata,
        PrivacyPolicy,
        ProcessingLocation,
        resolve_effective_privacy_metadata,
    )
    from cmm.domains.mental_health.privacy import build_mental_health_privacy_policy

    declared = build_mental_health_privacy_policy().default_privacy
    # Even a maximally permissive sibling cannot widen Mental Health privacy.
    permissive = PrivacyMetadata(
        policy=PrivacyPolicy.REMOTE_ALLOWED,
        sensitivity=SensitivityLevel.PUBLIC,
        allowed_processing_locations=(
            ProcessingLocation.LOCAL,
            ProcessingLocation.REMOTE,
        ),
        allow_remote=True,
        allow_export=True,
    )
    effective = resolve_effective_privacy_metadata(permissive, declared).effective
    assert effective.allow_remote is False
    assert effective.allow_export is False
    assert effective.sensitivity is SensitivityLevel.SENSITIVE
