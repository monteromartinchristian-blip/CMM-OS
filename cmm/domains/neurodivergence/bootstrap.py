"""Phase 10.53 — Canonical Neurodivergence Domain Bootstrap.

Provides the official, recommended factory for constructing the standard
domain registries with the Neurodivergence Domain integrated.  This reuses the
standard General Domain bootstrap (shared registries plus a resolver whose
fallback is ``domain:general``), registers the complete Neurodivergence Domain
into those exact same registry objects, and returns the composed system.

General remains the fallback, so a generic request never resolves to
Neurodivergence merely because Neurodivergence is present.  A Neurodivergence
signal routes to Neurodivergence when eligible and is fail-closed (never
silently absorbed by General) when it is not.

Operations are registered as **UNAVAILABLE** (fail-closed) unless real
implementations are injected via ``operation_implementations``.

No side effects occur at import time; all registries are created fresh on each
call.
"""

from __future__ import annotations

from dataclasses import dataclass

from cmm.cognitive.reasoning_rule_registry import InMemoryReasoningRuleRegistry
from cmm.domains.general.bootstrap import build_standard_general_domain_bootstrap
from cmm.domains.neurodivergence.integration import register_neurodivergence_domain
from cmm.domains.operation_registry import InMemoryDomainOperationRegistry
from cmm.domains.permission_registry import DomainPermissionRegistry
from cmm.domains.profile_registry import InMemoryDomainProfileRegistry
from cmm.domains.registry import DomainRegistry
from cmm.domains.resolver import DefaultDomainResolver
from cmm.domains.resource_registry import InMemoryDomainResourceRegistry
from cmm.domains.workflow_registry import InMemoryDomainWorkflowRegistry

NEURODIVERGENCE_BOOTSTRAP_NAME = "NeurodivergenceDomainBootstrap"


@dataclass(frozen=True, slots=True)
class NeurodivergenceDomainBootstrap:
    """The standard registries with the Neurodivergence Domain integrated."""

    domain_registry: DomainRegistry
    profile_registry: InMemoryDomainProfileRegistry
    resource_registry: InMemoryDomainResourceRegistry
    rule_registry: InMemoryReasoningRuleRegistry
    operation_registry: InMemoryDomainOperationRegistry
    workflow_registry: InMemoryDomainWorkflowRegistry
    permission_registry: DomainPermissionRegistry
    resolver: DefaultDomainResolver


def build_standard_neurodivergence_domain_bootstrap(
    *,
    operation_implementations: dict | None = None,
) -> NeurodivergenceDomainBootstrap:
    """Build the standard registries with the Neurodivergence Domain integrated.

    This is the canonical, recommended composition path.  It reuses the
    standard General Domain bootstrap, registers the complete Neurodivergence
    Domain into those exact same registries, and returns the composed system.

    A Health-, Mental Health-, University- or Relationships-connected
    composition is obtained by additionally registering those existing packs
    through their own canonical bootstrap/integration paths.
    Neurodivergence never copies sibling declarations and never needs a sibling
    pack to be present to function.
    """
    general = build_standard_general_domain_bootstrap()

    register_neurodivergence_domain(
        domain_registry=general.domain_registry,
        profile_registry=general.profile_registry,
        resource_registry=general.resource_registry,
        rule_registry=general.rule_registry,
        operation_registry=general.operation_registry,
        workflow_registry=general.workflow_registry,
        permission_registry=general.permission_registry,
        operation_implementations=operation_implementations,
    )

    return NeurodivergenceDomainBootstrap(
        domain_registry=general.domain_registry,
        profile_registry=general.profile_registry,
        resource_registry=general.resource_registry,
        rule_registry=general.rule_registry,
        operation_registry=general.operation_registry,
        workflow_registry=general.workflow_registry,
        permission_registry=general.permission_registry,
        resolver=general.resolver,
    )


__all__ = [
    "NEURODIVERGENCE_BOOTSTRAP_NAME",
    "NeurodivergenceDomainBootstrap",
    "build_standard_neurodivergence_domain_bootstrap",
]
