"""Phase 10.53 — Neurodivergence permission declaration tests.

Neurodivergence is fail-closed: inference/reasoning is allowed, persisting it
is not.  Reading is not transferring, provider availability is never
permission, and a technical transfer object is never authority.

The policy is a declaration only — never a permission engine, resolver or
grant of cross-domain authority.  The canonical ``DomainPermissionResolver``
remains the only source of an effective decision.
"""

from __future__ import annotations

import dataclasses

import pytest

from cmm.agent_runtime.agent_security_enums import (
    SensitivityLevel as AgentSensitivityLevel,
)
from cmm.agent_runtime.domain_permission_contracts import (
    PermissionCapability,
    PermissionOutcome,
)
from cmm.domains.neurodivergence.permissions import (
    NEURODIVERGENCE_CAPABILITY_SEPARATION,
    NEURODIVERGENCE_PERMISSION_POLICY_ID,
    build_neurodivergence_permission_policy,
    permission_authorization_allows,
)
from cmm.domains.permission_contracts import DomainPermissionRequest
from cmm.domains.permission_registry import DomainPermissionRegistry
from cmm.domains.permission_resolution import DomainPermissionResolver

DOMAIN_ID = "domain:neurodivergence"


def _registry(*policies) -> DomainPermissionRegistry:
    registry = DomainPermissionRegistry()
    for policy in policies:
        registry.register(policy)
    return registry


_READ_CAPABILITIES = frozenset(
    {
        PermissionCapability.RESOURCE_READ,
        PermissionCapability.KNOWLEDGE_READ,
        PermissionCapability.ENTITY_READ,
    }
)

#: A Neurodivergence-owned resource kind (the policy's read allowlist).
_OWN_RESOURCE_KIND = "developmental_history"


def _request(capability, *, domain_id=DOMAIN_ID, **overrides):
    values = {
        "request_id": "req-1",
        "action": capability,
        "domain_id": domain_id,
        "actor_id": "user-1",
        "session_id": "session-1",
        "sensitivity_level": AgentSensitivityLevel.RESTRICTED,
    }
    # The canonical contract and evaluator require the structural fields each
    # capability actually operates on.
    if capability in _READ_CAPABILITIES:
        values["resource_kind"] = _OWN_RESOURCE_KIND
    if capability is PermissionCapability.DOMAIN_CROSS_ACCESS:
        values["source_domain"] = "domain:health"
        values["target_domain"] = DOMAIN_ID
    values.update(overrides)
    return DomainPermissionRequest(**values)


def _policy():
    return build_neurodivergence_permission_policy()


def test_policy_identity_is_canonical():
    policy = _policy()

    assert policy.policy_id == NEURODIVERGENCE_PERMISSION_POLICY_ID
    assert NEURODIVERGENCE_PERMISSION_POLICY_ID == (
        "domain-permission:neurodivergence:1.0.0"
    )
    assert str(policy.domain_id) == DOMAIN_ID
    assert policy.version == "1.0.0"
    assert policy.enabled is True


def test_read_and_reason_are_allowed_but_write_is_not_automatic():
    policy = _policy()

    for capability in (
        PermissionCapability.RESOURCE_READ,
        PermissionCapability.KNOWLEDGE_READ,
        PermissionCapability.MEMORY_READ,
        PermissionCapability.OPERATION_EXECUTE,
        PermissionCapability.WORKFLOW_EXECUTE,
        PermissionCapability.SENSITIVE_INFERENCE,
    ):
        assert capability in policy.allowed_capabilities, capability

    assert policy.allow_memory_read is True
    assert policy.allow_memory_write is False
    assert policy.allow_external_communication is False
    assert policy.allow_export is False
    assert policy.allow_cross_domain_access is False


def test_no_sensitive_path_is_automatic_and_every_one_requires_approval():
    policy = _policy()

    for capability in (
        PermissionCapability.MEMORY_WRITE,
        PermissionCapability.SENSITIVE_INFERENCE_PERSIST,
        PermissionCapability.EXPORT,
        PermissionCapability.COMMUNICATION_EXTERNAL,
        PermissionCapability.DOMAIN_CROSS_ACCESS,
    ):
        assert capability in policy.prohibited_capabilities, capability
        assert capability in policy.approval_capabilities, capability
        assert capability not in policy.allowed_capabilities, capability

    for requirement in (
        "memory.persist",
        "sensitive.inference.persist",
        "export",
        "communication.external",
        "domain.cross_access",
    ):
        assert requirement in policy.approval_requirements, requirement


def test_medical_and_irreversible_authority_is_denied_by_default():
    policy = _policy()

    for capability in (
        PermissionCapability.MEDICAL_DECISION,
        PermissionCapability.MEDICAL_ACTION,
        PermissionCapability.PERMISSION_MODIFY,
        PermissionCapability.IRREVERSIBLE_CHANGE,
        PermissionCapability.EXTERNAL_DOMAIN_ACTIVATE,
        PermissionCapability.DOMAIN_CROSS_ACCESS,
        PermissionCapability.EXPORT,
        PermissionCapability.COMMUNICATION_EXTERNAL,
        PermissionCapability.SENSITIVE_INFERENCE_PERSIST,
        PermissionCapability.MEMORY_WRITE,
        PermissionCapability.FILE_MODIFY,
        PermissionCapability.KNOWLEDGE_DELETE,
        PermissionCapability.PUBLICATION,
    ):
        assert capability in policy.prohibited_capabilities, capability


def test_inference_is_allowed_without_granting_persistence():
    policy = _policy()

    assert PermissionCapability.SENSITIVE_INFERENCE in policy.allowed_capabilities
    assert (
        PermissionCapability.SENSITIVE_INFERENCE_PERSIST
        in policy.prohibited_capabilities
    )


def test_capability_separation_is_explicit_and_distinct():
    """read != infer != propose != persist != transfer/export/communicate != mutate."""
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
        assert stage in NEURODIVERGENCE_CAPABILITY_SEPARATION, stage

    separation = NEURODIVERGENCE_CAPABILITY_SEPARATION
    assert separation["persist"] != separation["read"]
    assert separation["transfer"] != separation["read"]
    assert separation["export"] != separation["infer"]
    assert separation["communicate"] != separation["read"]
    # A local reading of a source domain is not a cross-domain transfer.
    assert (
        PermissionCapability.RESOURCE_READ in separation["read"]
        and PermissionCapability.DOMAIN_CROSS_ACCESS not in separation["read"]
    )


def test_capability_separation_is_surfaced_in_policy_metadata():
    policy = _policy()
    serialized = policy.metadata["capability_separation"]

    assert set(serialized) == set(NEURODIVERGENCE_CAPABILITY_SEPARATION)
    assert tuple(serialized["persist"]) == (
        PermissionCapability.SENSITIVE_INFERENCE_PERSIST.value,
    )
    # Reading is not transferring: no cross-domain authority hides in "read".
    assert PermissionCapability.DOMAIN_CROSS_ACCESS.value not in serialized["read"]


def test_authorization_requires_literal_true():
    assert permission_authorization_allows(True) is True
    for value in (False, 1, 0, "true", "True", [], {}, None, object()):
        assert permission_authorization_allows(value) is False


def test_autonomy_is_zero_and_irreversible_action_is_not_allowed():
    limits = _policy().autonomy_limits

    assert limits.maximum_autonomy_level == 0
    assert limits.allow_reversible_changes is False
    assert limits.allow_irreversible_changes is False


# ── Canonical resolver behavior ──────────────────────────────────────────────


def test_memory_write_resolves_denied_through_canonical_resolver():
    resolver = DomainPermissionResolver(_registry(_policy()))

    resolution = resolver.resolve(_request(PermissionCapability.MEMORY_WRITE))

    assert resolution.effective_permissions.decision is PermissionOutcome.DENY


@pytest.mark.parametrize(
    "capability",
    (
        "EXPORT",
        "COMMUNICATION_EXTERNAL",
        "SENSITIVE_INFERENCE_PERSIST",
        "MEDICAL_DECISION",
        "MEDICAL_ACTION",
        "DOMAIN_CROSS_ACCESS",
        "IRREVERSIBLE_CHANGE",
        "PERMISSION_MODIFY",
    ),
)
def test_sensitive_capabilities_resolve_denied(capability):
    resolver = DomainPermissionResolver(_registry(_policy()))

    resolution = resolver.resolve(_request(getattr(PermissionCapability, capability)))

    assert resolution.effective_permissions.decision is PermissionOutcome.DENY


@pytest.mark.parametrize(
    "capability",
    ("RESOURCE_READ", "KNOWLEDGE_READ", "MEMORY_READ", "SENSITIVE_INFERENCE"),
)
def test_read_and_reason_resolve_allowed(capability):
    resolver = DomainPermissionResolver(_registry(_policy()))

    resolution = resolver.resolve(_request(getattr(PermissionCapability, capability)))

    assert resolution.effective_permissions.decision is PermissionOutcome.ALLOW


def test_unregistered_domain_fails_closed():
    """A domain with no registered policy is never granted authority.

    No policy for the requested domain means the canonical evaluator cannot
    produce an ALLOW.  This pack depends only on the fail-closed property.
    """
    resolver = DomainPermissionResolver(_registry(_policy()))

    with pytest.raises(ValueError):
        resolver.resolve(
            _request(PermissionCapability.MEMORY_READ, domain_id="domain:unknown")
        )


def test_a_foreign_domain_resource_kind_is_not_readable():
    """Reading is scoped to Neurodivergence-owned resource kinds."""
    resolver = DomainPermissionResolver(_registry(_policy()))

    resolution = resolver.resolve(
        _request(
            PermissionCapability.RESOURCE_READ, resource_kind="therapy_session_note"
        )
    )

    assert resolution.effective_permissions.decision is PermissionOutcome.DENY


def test_authority_downgrade_is_revalidated_and_fails_closed():
    """A stale ALLOW is never reused after the effective authority tightens."""
    registry = _registry(_policy())
    resolver = DomainPermissionResolver(registry)

    before = resolver.resolve(_request(PermissionCapability.SENSITIVE_INFERENCE))
    assert before.effective_permissions.decision is PermissionOutcome.ALLOW

    # Authority becomes more restrictive after the initial resolution: the
    # revised policy removes inference authority entirely.
    downgraded = dataclasses.replace(
        _policy(),
        policy_id="domain-permission:neurodivergence:1.1.0",
        version="1.1.0",
        allowed_capabilities=(
            PermissionCapability.RESOURCE_READ,
            PermissionCapability.KNOWLEDGE_READ,
            PermissionCapability.MEMORY_READ,
        ),
        prohibited_capabilities=(
            *_policy().prohibited_capabilities,
            PermissionCapability.SENSITIVE_INFERENCE,
        ),
    )
    registry.register(downgraded)

    after = resolver.resolve(_request(PermissionCapability.SENSITIVE_INFERENCE))
    assert after.effective_permissions.decision is PermissionOutcome.DENY
    assert any(str(policy.version) == "1.1.0" for policy in after.domain_policies)
    assert all(str(policy.version) != "1.0.0" for policy in after.domain_policies)


def test_provider_availability_is_not_permission():
    """A remote/model route existing never authorizes remote sensitive work."""
    policy = _policy()

    assert PermissionCapability.MODEL_EXTERNAL in policy.prohibited_capabilities
    assert PermissionCapability.SEARCH_EXTERNAL in policy.prohibited_capabilities
    assert policy.allow_external_models is False
    assert policy.allow_external_search is False
