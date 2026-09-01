"""Phase 10.38 — Domain trust permission ceiling tests (RED target for Task 3).

Proves trust is a permission **ceiling** integrated through the existing
canonical permission intersection:

- The trust layer may return only DENY or ABSTAIN.
- It can never turn a canonical DENY into ALLOW.
- It can never add authority.
- Supporting/cross-domain trust ceilings may only make results restrictive.
"""

from __future__ import annotations

from datetime import datetime, timezone

from cmm.agent_runtime.agent_security_enums import SensitivityLevel
from cmm.agent_runtime.domain_permission_contracts import (
    PermissionCapability,
    PermissionLayer,
    PermissionOutcome,
)
from cmm.domains.enums import DomainTrustLevel
from cmm.domains.permission_contracts import (
    CrossDomainPermissionRequest,
    DomainPermissionPolicy,
    DomainPermissionRequest,
)
from cmm.domains.permission_registry import DomainPermissionRegistry
from cmm.domains.permission_resolution import DomainPermissionResolver
from cmm.domains.trust_contracts import DomainTrustPolicy
from cmm.domains.trust_evaluator import evaluate_domain_trust_permission

_NOW = datetime(2026, 9, 1, tzinfo=timezone.utc)


def _trust_policy(
    *,
    domain_id: str = "domain:external-1",
    allow_code_execution: bool = False,
    allow_external_access: bool = False,
    allow_memory_write: bool = False,
    allow_sensitive_resources: bool = False,
    allow_destructive_operations: bool = False,
) -> DomainTrustPolicy:
    return DomainTrustPolicy(
        domain_id=domain_id,
        trust_level=DomainTrustLevel.COMMUNITY,
        authorized_source_ids=("source:external-1",),
        allow_code_execution=allow_code_execution,
        allow_external_access=allow_external_access,
        allow_memory_write=allow_memory_write,
        allow_sensitive_resources=allow_sensitive_resources,
        allow_destructive_operations=allow_destructive_operations,
    )


def _perm_policy(
    policy_id: str = "p-external-1",
    *,
    domain_id: str = "domain:external-1",
    allowed_capabilities: tuple[PermissionCapability, ...] = (),
    allow_memory_read: bool = False,
    allow_memory_write: bool = False,
    allow_external_search: bool = False,
    allow_sensitive_inference: bool = False,
    allow_file_modification: bool = False,
    allow_cross_domain_access: bool = False,
    allowed_target_domains: tuple[str, ...] | None = None,
    allow_inbound_cross_domain_access: bool = False,
    allowed_sensitivity_levels: tuple[str, ...] | None = ("public", "internal"),
) -> DomainPermissionPolicy:
    return DomainPermissionPolicy(
        policy_id,
        domain_id,
        "1.0.0",
        allowed_capabilities=allowed_capabilities,
        allow_memory_read=allow_memory_read,
        allow_memory_write=allow_memory_write,
        allow_external_search=allow_external_search,
        allow_sensitive_inference=allow_sensitive_inference,
        allow_file_modification=allow_file_modification,
        allow_cross_domain_access=allow_cross_domain_access,
        allowed_target_domains=tuple(allowed_target_domains or ()),
        allow_inbound_cross_domain_access=allow_inbound_cross_domain_access,
        allowed_sensitivity_levels=tuple(allowed_sensitivity_levels or ()),
    )


def _request(
    *,
    action: PermissionCapability,
    domain_id: str = "domain:external-1",
    sensitivity_level: SensitivityLevel | None = None,
    operation_id: str | None = None,
    workflow_id: str | None = None,
    resource_id: str | None = None,
    resource_kind: str | None = None,
) -> DomainPermissionRequest:
    return DomainPermissionRequest(
        "req-1",
        action,
        domain_id,
        "actor-1",
        "session-1",
        sensitivity_level=sensitivity_level,
        operation_id=operation_id,
        workflow_id=workflow_id,
        resource_id=resource_id,
        resource_kind=resource_kind,
    )


class TestTrustLayerSemantics:
    def test_trust_layer_never_returns_allow(self) -> None:
        policy = _trust_policy(
            allow_code_execution=True,
            allow_external_access=True,
            allow_memory_write=True,
            allow_sensitive_resources=True,
            allow_destructive_operations=True,
        )
        request = _request(action=PermissionCapability.MEMORY_WRITE)
        evaluation = evaluate_domain_trust_permission(policy, request)
        assert evaluation.effect in (PermissionOutcome.DENY, PermissionOutcome.ABSTAIN)
        assert evaluation.effect is not PermissionOutcome.ALLOW
        assert evaluation.source is PermissionLayer.DOMAIN

    def test_trust_layer_denies_denied_capability(self) -> None:
        policy = _trust_policy(allow_memory_write=False)
        request = _request(action=PermissionCapability.MEMORY_WRITE)
        evaluation = evaluate_domain_trust_permission(policy, request)
        assert evaluation.effect is PermissionOutcome.DENY
        assert "trust.memory_write_denied" in evaluation.reasons

    def test_trust_layer_abstains_on_allowed_capability(self) -> None:
        policy = _trust_policy(allow_memory_write=True)
        request = _request(action=PermissionCapability.MEMORY_WRITE)
        evaluation = evaluate_domain_trust_permission(policy, request)
        assert evaluation.effect is PermissionOutcome.ABSTAIN

    def test_trust_layer_source_id_is_scoped(self) -> None:
        policy = _trust_policy()
        request = _request(action=PermissionCapability.MEMORY_WRITE)
        evaluation = evaluate_domain_trust_permission(policy, request)
        assert evaluation.source_id == f"domain-trust:{policy.domain_id}"


class TestTrustCannotGrant:
    def test_trust_cannot_turn_canonical_deny_into_allow(self) -> None:
        registry = DomainPermissionRegistry()
        registry.register(_perm_policy(allowed_capabilities=()))
        resolver = DomainPermissionResolver(
            registry,
            trust_policy_lookup=lambda _: _trust_policy(
                allow_code_execution=True,
                allow_external_access=True,
                allow_memory_write=True,
                allow_sensitive_resources=True,
                allow_destructive_operations=True,
            ),
        )
        request = _request(
            action=PermissionCapability.OPERATION_EXECUTE, operation_id="op-1"
        )
        result = resolver.resolve(request)
        assert result.effective_permissions.decision is PermissionOutcome.DENY

    def test_trust_with_all_flags_true_never_creates_permissions(self) -> None:
        policy = _trust_policy(
            allow_code_execution=True,
            allow_external_access=True,
            allow_memory_write=True,
            allow_sensitive_resources=True,
            allow_destructive_operations=True,
        )
        request = _request(
            action=PermissionCapability.OPERATION_EXECUTE, operation_id="op-1"
        )
        evaluation = evaluate_domain_trust_permission(policy, request)
        assert evaluation.effect is PermissionOutcome.ABSTAIN
        # A Domain policy that also denies keeps the final result DENY.
        registry = DomainPermissionRegistry()
        registry.register(_perm_policy(allowed_capabilities=()))
        resolver = DomainPermissionResolver(
            registry, trust_policy_lookup=lambda _: policy
        )
        result = resolver.resolve(request)
        assert result.effective_permissions.decision is PermissionOutcome.DENY


class TestCapabilityCeilings:
    def test_code_execution_ceiling(self) -> None:
        registry = DomainPermissionRegistry()
        registry.register(
            _perm_policy(allowed_capabilities=(PermissionCapability.OPERATION_EXECUTE,))
        )
        resolver = DomainPermissionResolver(
            registry,
            trust_policy_lookup=lambda _: _trust_policy(allow_code_execution=False),
        )
        request = _request(
            action=PermissionCapability.OPERATION_EXECUTE, operation_id="op-1"
        )
        result = resolver.resolve(request)
        assert result.effective_permissions.decision is PermissionOutcome.DENY
        assert any(
            "trust.code_execution_denied" in e.reasons
            for e in result.effective_permissions.layer_evaluations
        )

    def test_memory_write_ceiling(self) -> None:
        registry = DomainPermissionRegistry()
        registry.register(_perm_policy(allow_memory_write=True))
        resolver = DomainPermissionResolver(
            registry,
            trust_policy_lookup=lambda _: _trust_policy(allow_memory_write=False),
        )
        request = _request(action=PermissionCapability.MEMORY_WRITE)
        result = resolver.resolve(request)
        assert result.effective_permissions.decision is PermissionOutcome.DENY
        assert any(
            "trust.memory_write_denied" in e.reasons
            for e in result.effective_permissions.layer_evaluations
        )

    def test_external_access_ceiling(self) -> None:
        registry = DomainPermissionRegistry()
        registry.register(_perm_policy(allow_external_search=True))
        resolver = DomainPermissionResolver(
            registry,
            trust_policy_lookup=lambda _: _trust_policy(allow_external_access=False),
        )
        request = _request(action=PermissionCapability.SEARCH_EXTERNAL)
        result = resolver.resolve(request)
        assert result.effective_permissions.decision is PermissionOutcome.DENY
        assert any(
            "trust.external_access_denied" in e.reasons
            for e in result.effective_permissions.layer_evaluations
        )

    def test_sensitive_resource_ceiling_isolation(self) -> None:
        # Canonical allowlist includes the sensitive capability; trust
        # ceiling denies it.
        registry = DomainPermissionRegistry()
        registry.register(
            _perm_policy(
                allow_sensitive_inference=True,
                allowed_sensitivity_levels=("public", "internal", "confidential"),
            )
        )
        resolver = DomainPermissionResolver(
            registry,
            trust_policy_lookup=lambda _: _trust_policy(
                allow_sensitive_resources=False
            ),
        )
        request = _request(action=PermissionCapability.SENSITIVE_INFERENCE)
        result = resolver.resolve(request)
        assert result.effective_permissions.decision is PermissionOutcome.DENY
        assert any(
            "trust.sensitive_resource_denied" in e.reasons
            for e in result.effective_permissions.layer_evaluations
        )

    def test_confidential_resource_read_ceiling(self) -> None:
        registry = DomainPermissionRegistry()
        registry.register(
            _perm_policy(allowed_sensitivity_levels=("public", "confidential"))
        )
        resolver = DomainPermissionResolver(
            registry,
            trust_policy_lookup=lambda _: _trust_policy(
                allow_sensitive_resources=False
            ),
        )
        request = _request(
            action=PermissionCapability.RESOURCE_READ,
            sensitivity_level=SensitivityLevel.CONFIDENTIAL,
            resource_id="res-1",
        )
        result = resolver.resolve(request)
        assert result.effective_permissions.decision is PermissionOutcome.DENY
        assert any(
            "trust.sensitive_resource_denied" in e.reasons
            for e in result.effective_permissions.layer_evaluations
        )

    def test_public_resource_read_not_denied_by_sensitivity(self) -> None:
        registry = DomainPermissionRegistry()
        registry.register(
            _perm_policy(allowed_sensitivity_levels=("public", "internal"))
        )
        resolver = DomainPermissionResolver(
            registry,
            trust_policy_lookup=lambda _: _trust_policy(
                allow_sensitive_resources=False
            ),
        )
        request = _request(
            action=PermissionCapability.RESOURCE_READ,
            sensitivity_level=SensitivityLevel.PUBLIC,
            resource_id="res-1",
        )
        result = resolver.resolve(request)
        assert result.effective_permissions.decision is PermissionOutcome.ALLOW

    def test_destructive_operation_ceiling(self) -> None:
        registry = DomainPermissionRegistry()
        registry.register(_perm_policy(allow_file_modification=True))
        resolver = DomainPermissionResolver(
            registry,
            trust_policy_lookup=lambda _: _trust_policy(
                allow_destructive_operations=False
            ),
        )
        request = _request(action=PermissionCapability.FILE_MODIFY)
        result = resolver.resolve(request)
        assert result.effective_permissions.decision is PermissionOutcome.DENY
        assert any(
            "trust.destructive_operation_denied" in e.reasons
            for e in result.effective_permissions.layer_evaluations
        )


class TestNoPolicyCompatibility:
    def test_no_trust_lookup_preserves_pre_1038_behavior(self) -> None:
        registry = DomainPermissionRegistry()
        registry.register(_perm_policy(allow_memory_read=True))
        resolver = DomainPermissionResolver(registry)
        request = _request(
            action=PermissionCapability.MEMORY_READ,
            sensitivity_level=SensitivityLevel.PUBLIC,
        )
        result = resolver.resolve(request)
        assert result.effective_permissions.decision is PermissionOutcome.ALLOW

    def test_lookup_returning_none_preserves_pre_1038_behavior(self) -> None:
        registry = DomainPermissionRegistry()
        registry.register(_perm_policy(allow_memory_read=True))
        resolver = DomainPermissionResolver(
            registry, trust_policy_lookup=lambda _: None
        )
        request = _request(
            action=PermissionCapability.MEMORY_READ,
            sensitivity_level=SensitivityLevel.PUBLIC,
        )
        result = resolver.resolve(request)
        assert result.effective_permissions.decision is PermissionOutcome.ALLOW


class TestSupportingDomainCannotWiden:
    def test_primary_trust_deny_not_widened_by_supporting(self) -> None:
        registry = DomainPermissionRegistry()
        registry.register(
            _perm_policy(
                policy_id="p-external-1",
                domain_id="domain:external-1",
                allowed_capabilities=(PermissionCapability.MEMORY_WRITE,),
            )
        )

        def lookups(domain_id: str) -> DomainTrustPolicy | None:
            if domain_id == "domain:external-1":
                return _trust_policy(
                    domain_id="domain:external-1", allow_memory_write=False
                )
            return None

        resolver = DomainPermissionResolver(registry, trust_policy_lookup=lookups)
        request = _request(action=PermissionCapability.MEMORY_WRITE)
        result = resolver.resolve(request, supporting_domains=("domain:other",))
        assert result.effective_permissions.decision is PermissionOutcome.DENY


class TestCrossDomainCeiling:
    def test_cross_domain_trust_deny_cannot_be_widened(self) -> None:
        registry = DomainPermissionRegistry()
        registry.register(
            _perm_policy(
                policy_id="source",
                domain_id="domain:external-1",
                allow_cross_domain_access=True,
                allowed_target_domains=("domain:target",),
                allowed_capabilities=(PermissionCapability.DOMAIN_CROSS_ACCESS,),
                allowed_sensitivity_levels=("internal",),
            )
        )
        registry.register(
            _perm_policy(
                policy_id="target",
                domain_id="domain:target",
                allow_inbound_cross_domain_access=True,
                allowed_sensitivity_levels=("internal",),
            )
        )

        def lookups(domain_id: str) -> DomainTrustPolicy | None:
            if domain_id == "domain:external-1":
                return _trust_policy(
                    domain_id="domain:external-1", allow_external_access=False
                )
            return None

        resolver = DomainPermissionResolver(registry, trust_policy_lookup=lookups)
        request = CrossDomainPermissionRequest(
            "xreq",
            "domain:external-1",
            "domain:target",
            requested_operations=(),
            reason="test",
            actor_id="actor-1",
            session_id="session-1",
            sensitivity_level=SensitivityLevel.INTERNAL,
            capability=PermissionCapability.DOMAIN_CROSS_ACCESS,
            requires_approval=False,
        )
        decision = resolver.resolve_cross_domain(request)
        assert decision.decision is PermissionOutcome.DENY
