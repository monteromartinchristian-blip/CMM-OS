"""Phase 10.24 — Canonical Reflection Domain Bootstrap.

Provides the official, recommended factory for constructing the standard
domain registries with the Reflection Domain integrated.  This is the canonical
composition path for callers that need a complete, discoverable Reflection
Domain without manual registry wiring.

The bootstrap reuses the standard General Domain registries, registers the
Reflection Domain into those exact same registries, and returns a bootstrap
exposing the composed registries.  General remains the fallback.

Operations are registered as **UNAVAILABLE** (fail-closed) unless real
implementations are injected via ``operation_implementations``.

No side effects occur at import time; all registries are created fresh on each
call.
"""

from __future__ import annotations

from dataclasses import dataclass

from cmm.cognitive.reasoning_rule_registry import InMemoryReasoningRuleRegistry
from cmm.domains.general.bootstrap import (
    build_standard_general_domain_bootstrap,
)
from cmm.domains.operation_registry import InMemoryDomainOperationRegistry
from cmm.domains.permission_registry import DomainPermissionRegistry
from cmm.domains.profile_registry import InMemoryDomainProfileRegistry
from cmm.domains.reflection.integration import register_reflection_domain
from cmm.domains.registry import DomainRegistry
from cmm.domains.resolver import DefaultDomainResolver
from cmm.domains.resource_registry import InMemoryDomainResourceRegistry
from cmm.domains.workflow_registry import InMemoryDomainWorkflowRegistry

REFLECTION_BOOTSTRAP_NAME = "ReflectionDomainBootstrap"


@dataclass(frozen=True, slots=True)
class ReflectionDomainBootstrap:
    """The standard registries with the Reflection Domain fully integrated."""

    domain_registry: DomainRegistry
    profile_registry: InMemoryDomainProfileRegistry
    resource_registry: InMemoryDomainResourceRegistry
    rule_registry: InMemoryReasoningRuleRegistry
    operation_registry: InMemoryDomainOperationRegistry
    workflow_registry: InMemoryDomainWorkflowRegistry
    permission_registry: DomainPermissionRegistry
    resolver: DefaultDomainResolver


def build_standard_reflection_domain_bootstrap(
    *,
    operation_implementations: dict | None = None,
) -> ReflectionDomainBootstrap:
    """Build the standard registries with the Reflection Domain integrated.

    This reuses the standard General Domain bootstrap (shared registries + a
    resolver whose fallback is ``domain:general``), registers the complete
    Reflection Domain into those same registries, and returns the composed
    system.  No global state is modified.  General remains the fallback; a
    generic request resolves to General, and a Reflection signal routes to
    Reflection when eligible, fail-closed otherwise.
    """
    general = build_standard_general_domain_bootstrap()

    register_reflection_domain(
        domain_registry=general.domain_registry,
        profile_registry=general.profile_registry,
        resource_registry=general.resource_registry,
        rule_registry=general.rule_registry,
        operation_registry=general.operation_registry,
        workflow_registry=general.workflow_registry,
        permission_registry=general.permission_registry,
        operation_implementations=operation_implementations,
    )

    return ReflectionDomainBootstrap(
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
    "REFLECTION_BOOTSTRAP_NAME",
    "ReflectionDomainBootstrap",
    "build_standard_reflection_domain_bootstrap",
]
