from dataclasses import replace
from datetime import datetime, timezone

import pytest

from cmm.agent_runtime.domain_permission_contracts import (
    PermissionApprovalGrant,
    PermissionCapability,
    PermissionLayer,
    PermissionLayerEvaluation,
    PermissionOutcome,
)
from cmm.domains.permission_contracts import (
    CrossDomainDuration,
    CrossDomainPermissionRequest,
    DomainAutonomyLimits,
    DomainPermissionPolicy,
    DomainPermissionRequest,
)
from cmm.domains.permission_registry import DomainPermissionRegistry
from cmm.domains.permission_resolution import DomainPermissionResolver


def test_global_deny_and_domain_allow_resolve_to_deny():
    registry = DomainPermissionRegistry()
    registry.register(DomainPermissionPolicy("p", "domain:health", "1.0.0", allow_memory_read=True))
    resolver = DomainPermissionResolver(registry)
    request = DomainPermissionRequest("r", PermissionCapability.MEMORY_READ, "domain:health", "a", "s")
    result = resolver.resolve(request, layer_evaluations=(PermissionLayerEvaluation(PermissionLayer.GLOBAL, PermissionOutcome.DENY, reasons=("global",)),))
    assert result.effective_permissions.decision is PermissionOutcome.DENY
    assert result.domain_policies[0].policy_id == "p"


def test_cross_domain_requires_both_policy_sides_and_is_scoped():
    registry = DomainPermissionRegistry()
    registry.register(DomainPermissionPolicy("source", "domain:life", "1.0.0", allow_cross_domain_access=True, allowed_target_domains=("domain:health",), allowed_capabilities=(PermissionCapability.DOMAIN_CROSS_ACCESS,), allowed_sensitivity_levels=("internal",)))
    registry.register(DomainPermissionPolicy("target", "domain:health", "1.0.0", allow_inbound_cross_domain_access=True, allowed_sensitivity_levels=("internal",)))
    resolver = DomainPermissionResolver(registry)
    request = CrossDomainPermissionRequest("x", "domain:life", "domain:health", resource_ids=("r1",), reason="reason", actor_id="a", session_id="s", sensitivity_level="internal")
    decision = resolver.resolve_cross_domain(request)
    assert decision.decision is PermissionOutcome.APPROVAL_REQUIRED
    assert decision.granted_resources == ()


def test_supporting_domain_deny_cannot_be_hidden_by_primary_allow():
    registry = DomainPermissionRegistry()
    registry.register(DomainPermissionPolicy("primary", "domain:life", "1.0.0", allow_memory_read=True))
    registry.register(DomainPermissionPolicy("support", "domain:health", "1.0.0", allow_memory_read=False))
    resolver = DomainPermissionResolver(registry)
    request = DomainPermissionRequest("r", PermissionCapability.MEMORY_READ, "domain:life", "a", "s", sensitivity_level="internal")
    result = resolver.resolve(request, supporting_domains=("domain:health",))
    assert result.effective_permissions.decision is PermissionOutcome.DENY


def test_cross_domain_target_can_explicitly_deny_source():
    registry = DomainPermissionRegistry()
    registry.register(DomainPermissionPolicy(
        "source", "domain:life", "1.0.0",
        allow_cross_domain_access=True,
        allowed_target_domains=("domain:health",),
        allowed_capabilities=(PermissionCapability.DOMAIN_CROSS_ACCESS,),
    ))
    registry.register(DomainPermissionPolicy(
        "target", "domain:health", "1.0.0",
        allow_inbound_cross_domain_access=False,
    ))
    request = CrossDomainPermissionRequest(
        "x", "domain:life", "domain:health", resource_ids=("r1",),
        reason="reason", actor_id="a", session_id="s",
    )
    decision = DomainPermissionResolver(registry).resolve_cross_domain(request)
    assert decision.decision is PermissionOutcome.DENY
    assert "target_cross_domain_denied" in decision.reasons


def test_cross_domain_target_capability_prohibition_dominates_source_allow():
    registry = DomainPermissionRegistry()
    registry.register(DomainPermissionPolicy(
        "source", "domain:life", "1.0.0",
        allow_cross_domain_access=True,
        allowed_target_domains=("domain:health",),
        allowed_capabilities=(PermissionCapability.DOMAIN_CROSS_ACCESS,),
        allowed_sensitivity_levels=("internal",),
    ))
    registry.register(DomainPermissionPolicy(
        "target", "domain:health", "1.0.0",
        allow_inbound_cross_domain_access=True,
        prohibited_capabilities=(PermissionCapability.DOMAIN_CROSS_ACCESS,),
        allowed_sensitivity_levels=("internal",),
    ))
    request = CrossDomainPermissionRequest(
        "x", "domain:life", "domain:health",
        capability=PermissionCapability.DOMAIN_CROSS_ACCESS,
        reason="reason", actor_id="a", session_id="s",
        sensitivity_level="internal",
    )

    decision = DomainPermissionResolver(registry).resolve_cross_domain(request)

    assert decision.decision is PermissionOutcome.DENY
    assert "target_capability_prohibited" in decision.reasons


def test_cross_domain_requested_capability_must_be_allowed_by_both_domains():
    registry = DomainPermissionRegistry()
    registry.register(DomainPermissionPolicy(
        "source", "domain:life", "1.0.0",
        allow_cross_domain_access=True,
        allowed_target_domains=("domain:health",),
        allowed_capabilities=(
            PermissionCapability.DOMAIN_CROSS_ACCESS,
            PermissionCapability.EXPORT,
        ),
        allowed_sensitivity_levels=("internal",),
    ))
    registry.register(DomainPermissionPolicy(
        "target", "domain:health", "1.0.0",
        allow_inbound_cross_domain_access=True,
        allowed_sensitivity_levels=("internal",),
    ))
    request = CrossDomainPermissionRequest(
        "x", "domain:life", "domain:health",
        capability=PermissionCapability.EXPORT,
        reason="reason", actor_id="a", session_id="s",
        sensitivity_level="internal", requires_approval=False,
    )

    decision = DomainPermissionResolver(registry).resolve_cross_domain(request)

    assert decision.decision is PermissionOutcome.DENY
    assert "target_capability_denied" in decision.reasons


def test_cross_domain_checks_both_resource_kinds_operations_and_workflows():
    registry = DomainPermissionRegistry()
    registry.register(DomainPermissionPolicy(
        "source", "domain:life", "1.0.0",
        allow_cross_domain_access=True,
        allowed_target_domains=("domain:health",),
        allowed_capabilities=(PermissionCapability.DOMAIN_CROSS_ACCESS,),
        allowed_resource_kinds=("record",),
        allowed_operations=("op:read",),
        allowed_workflows=("workflow:review",),
        allowed_sensitivity_levels=("internal",),
    ))
    registry.register(DomainPermissionPolicy(
        "target", "domain:health", "1.0.0",
        allow_inbound_cross_domain_access=True,
        allowed_resource_kinds=("record",),
        prohibited_operations=("op:delete",),
        allowed_workflows=("workflow:review",),
        allowed_sensitivity_levels=("internal",),
    ))
    request = CrossDomainPermissionRequest(
        "x", "domain:life", "domain:health",
        resource_ids=("record:1",), resource_kinds=("record",),
        requested_operations=("op:delete",),
        requested_workflows=("workflow:review",),
        reason="reason", actor_id="a", session_id="s",
        sensitivity_level="internal",
    )

    decision = DomainPermissionResolver(registry).resolve_cross_domain(request)

    assert decision.decision is PermissionOutcome.DENY
    assert "source_operation_denied" in decision.reasons
    assert "target_operation_prohibited" in decision.reasons


def test_cross_domain_target_exact_resource_prohibition_dominates_source_scope():
    registry = DomainPermissionRegistry()
    registry.register(DomainPermissionPolicy(
        "source", "domain:life", "1.0.0",
        allow_cross_domain_access=True,
        allowed_target_domains=("domain:health",),
        allowed_capabilities=(PermissionCapability.DOMAIN_CROSS_ACCESS,),
        allowed_resources=("record:1",),
        allowed_sensitivity_levels=("internal",),
    ))
    registry.register(DomainPermissionPolicy(
        "target", "domain:health", "1.0.0",
        allow_inbound_cross_domain_access=True,
        prohibited_resources=("record:1",),
        allowed_sensitivity_levels=("internal",),
    ))
    request = CrossDomainPermissionRequest(
        "x", "domain:life", "domain:health", resource_ids=("record:1",),
        reason="reason", actor_id="a", session_id="s",
        sensitivity_level="internal",
    )

    decision = DomainPermissionResolver(registry).resolve_cross_domain(request)

    assert decision.decision is PermissionOutcome.DENY
    assert "target_resource_prohibited" in decision.reasons


def test_cross_domain_enforces_declared_duration_and_scope_constraints():
    registry = DomainPermissionRegistry()
    registry.register(DomainPermissionPolicy(
        "source", "domain:life", "1.0.0",
        allow_cross_domain_access=True,
        allowed_target_domains=("domain:health",),
        allowed_capabilities=(PermissionCapability.DOMAIN_CROSS_ACCESS,),
        allowed_sensitivity_levels=("internal",),
    ))
    registry.register(DomainPermissionPolicy(
        "target", "domain:health", "1.0.0",
        allow_inbound_cross_domain_access=True,
        allowed_sensitivity_levels=("internal",),
    ))
    request = CrossDomainPermissionRequest(
        "x", "domain:life", "domain:health",
        requested_operations=("op:read",),
        reason="reason", actor_id="a", session_id="s",
        sensitivity_level="internal", duration=CrossDomainDuration.SESSION,
        constraints={
            "scopes": (CrossDomainDuration.REQUEST.value,),
            "allowed_operations": ("op:read",),
        },
    )

    decision = DomainPermissionResolver(registry).resolve_cross_domain(request)

    assert decision.decision is PermissionOutcome.DENY
    assert "duration_not_allowed_by_constraints" in decision.reasons


def test_resolution_generates_structured_conflict_for_primary_allow_supporting_deny():
    registry = DomainPermissionRegistry()
    registry.register(DomainPermissionPolicy("primary", "domain:life", "1.0.0", allow_memory_read=True))
    registry.register(DomainPermissionPolicy("support", "domain:health", "1.0.0", allow_memory_read=False))
    request = DomainPermissionRequest("r", PermissionCapability.MEMORY_READ, "domain:life", "a", "s", sensitivity_level="internal")
    result = DomainPermissionResolver(registry).resolve(request, supporting_domains=("domain:health",))
    assert result.conflicts[0].reason_code == "allow_deny_conflict"
    assert result.conflicts[0].allowing_sources == ("primary:primary:1.0.0",)


def test_legacy_approval_grants_never_authorize_resolution():
    registry = DomainPermissionRegistry()
    registry.register(DomainPermissionPolicy(
        "health", "domain:health", "1.0.0",
        allowed_capabilities=(PermissionCapability.MEDICAL_DECISION,),
        approval_capabilities=(PermissionCapability.MEDICAL_DECISION,),
    ))
    resolver = DomainPermissionResolver(registry)
    request = DomainPermissionRequest("r", PermissionCapability.MEDICAL_DECISION, "domain:health", "actor", "session")
    now = datetime(2026, 8, 2, tzinfo=timezone.utc)
    pending = resolver.resolve(request, now=now)
    requirement = pending.approval_requirements[0]
    bad_grant = PermissionApprovalGrant(replace(requirement, actor_id="other"), "2026-08-02T00:00:00+00:00")
    assert resolver.resolve(request, approval_grants=(bad_grant,), now=now).effective_permissions.decision is PermissionOutcome.APPROVAL_REQUIRED
    grant = PermissionApprovalGrant(requirement, "2026-08-02T00:00:00+00:00")
    result = resolver.resolve(request, approval_grants=(grant,), now=now)
    assert result.effective_permissions.decision is PermissionOutcome.APPROVAL_REQUIRED
    assert result.metadata["legacy_approval_grants_ignored"] == 1


def test_autonomy_limit_becomes_a_denying_layer_and_conflict():
    registry = DomainPermissionRegistry()
    registry.register(DomainPermissionPolicy(
        "project", "domain:project", "1.0.0", allow_memory_read=True,
        autonomy_limits=DomainAutonomyLimits(maximum_autonomy_level=1),
    ))
    request = DomainPermissionRequest("r", PermissionCapability.MEMORY_READ, "domain:project", "a", "s", sensitivity_level="internal", autonomy_level=2)
    result = DomainPermissionResolver(registry).resolve(request)
    assert result.effective_permissions.decision is PermissionOutcome.DENY
    assert "autonomy:domain:project" in result.effective_permissions.denied_by


def test_cross_domain_temporal_policy_requires_clock_and_uses_it_for_both_sides():
    registry = DomainPermissionRegistry()
    expires = datetime(2026, 8, 3, tzinfo=timezone.utc)
    registry.register(DomainPermissionPolicy(
        "source", "domain:life", "1.0.0", expires_at=expires,
        allowed_capabilities=(PermissionCapability.DOMAIN_CROSS_ACCESS,),
        allow_cross_domain_access=True, allowed_target_domains=("domain:health",),
        allowed_sensitivity_levels=("internal",),
    ))
    registry.register(DomainPermissionPolicy(
        "target", "domain:health", "1.0.0", expires_at=expires,
        allow_inbound_cross_domain_access=True, allowed_sensitivity_levels=("internal",),
    ))
    request = CrossDomainPermissionRequest("x", "domain:life", "domain:health", reason="r", actor_id="a", session_id="s", sensitivity_level="internal")
    resolver = DomainPermissionResolver(registry)
    with pytest.raises(ValueError, match="now"):
        resolver.resolve_cross_domain(request)
    assert resolver.resolve_cross_domain(request, now=datetime(2026, 8, 2, tzinfo=timezone.utc)).decision is PermissionOutcome.APPROVAL_REQUIRED
    assert resolver.resolve_cross_domain(request, now=datetime(2026, 8, 4, tzinfo=timezone.utc)).decision is PermissionOutcome.DENY
