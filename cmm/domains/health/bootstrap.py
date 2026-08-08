"""Phase 10.20 — Canonical Health Domain Bootstrap.

Provides the official, recommended factory for constructing the standard
domain registries with Health Domain integrated.  This is the canonical
composition path for callers that need a complete, discoverable Health
Domain without manual registry wiring.

The bootstrap builds the standard registries, registers Health Domain
atomically, and exposes the standard ``DefaultDomainResolver`` configured
with ``domain:health`` as its fallback domain.

Operations are registered as **UNAVAILABLE** (fail-closed) unless real
implementations are injected via ``operation_implementations``.  No fake
delegates are installed: a declared operation that is not yet implemented
must not appear available or successful.

No side effects occur at import time; all registries are created fresh on
each call.
"""

from __future__ import annotations

from dataclasses import dataclass

from cmm.agent_runtime.operation_registry import InMemoryAgentOperationRegistry
from cmm.cognitive.reasoning_rule_registry import InMemoryReasoningRuleRegistry
from cmm.domains.health.definition import HEALTH_DOMAIN_ID
from cmm.domains.health.integration import register_health_domain
from cmm.domains.identifiers import DomainId
from cmm.domains.operation_registry import InMemoryDomainOperationRegistry
from cmm.domains.permission_registry import DomainPermissionRegistry
from cmm.domains.profile_registry import InMemoryDomainProfileRegistry
from cmm.domains.registry import DomainRegistry
from cmm.domains.resolver import DefaultDomainResolver
from cmm.domains.resource_registry import InMemoryDomainResourceRegistry
from cmm.domains.workflow_registry import InMemoryDomainWorkflowRegistry
from cmm.workflows.registry import InMemoryWorkflowRegistry


@dataclass(frozen=True, slots=True)
class HealthDomainBootstrap:
    """The standard registries with Health Domain fully integrated."""

    domain_registry: DomainRegistry
    profile_registry: InMemoryDomainProfileRegistry
    resource_registry: InMemoryDomainResourceRegistry
    rule_registry: InMemoryReasoningRuleRegistry
    operation_registry: InMemoryDomainOperationRegistry
    workflow_registry: InMemoryDomainWorkflowRegistry
    permission_registry: DomainPermissionRegistry
    resolver: DefaultDomainResolver


def build_standard_health_domain_bootstrap(
    *,
    operation_implementations: dict | None = None,
) -> HealthDomainBootstrap:
    """Build the standard registries with Health Domain integrated.

    This is the canonical, recommended composition path.  It creates fresh
    registries, registers the complete Health Domain atomically, and
    returns the composed system.  No global state is modified.

    The returned bootstrap exposes the standard ``DefaultDomainResolver``
    configured with ``fallback_domain=DomainId.from_str(HEALTH_DOMAIN_ID)``.

    ``operation_implementations`` is an optional mapping of
    ``operation_id -> implementation``.  Operations without an injected
    implementation are registered as **UNAVAILABLE** (fail-closed) and are
    never reported as available or successful.
    """
    domain_registry = DomainRegistry()
    profile_registry = InMemoryDomainProfileRegistry()
    resource_registry = InMemoryDomainResourceRegistry()
    rule_registry = InMemoryReasoningRuleRegistry()
    operation_registry = InMemoryDomainOperationRegistry(
        InMemoryAgentOperationRegistry()
    )
    workflow_registry = InMemoryDomainWorkflowRegistry(
        InMemoryWorkflowRegistry()
    )
    permission_registry = DomainPermissionRegistry()
    resolver = DefaultDomainResolver(
        fallback_domain=DomainId.from_str(HEALTH_DOMAIN_ID),
    )

    register_health_domain(
        domain_registry=domain_registry,
        profile_registry=profile_registry,
        resource_registry=resource_registry,
        rule_registry=rule_registry,
        operation_registry=operation_registry,
        workflow_registry=workflow_registry,
        permission_registry=permission_registry,
        operation_implementations=operation_implementations,
    )

    return HealthDomainBootstrap(
        domain_registry=domain_registry,
        profile_registry=profile_registry,
        resource_registry=resource_registry,
        rule_registry=rule_registry,
        operation_registry=operation_registry,
        workflow_registry=workflow_registry,
        permission_registry=permission_registry,
        resolver=resolver,
    )


__all__ = [
    "HealthDomainBootstrap",
    "build_standard_health_domain_bootstrap",
]
