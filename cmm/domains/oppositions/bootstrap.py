"""Phase 10.23 — Canonical Opposition Domain Bootstrap.

Provides the official, recommended factory for constructing the standard
domain registries with the Opposition Domain integrated.  This is the canonical
composition path for callers that need a complete, discoverable Opposition
Domain without manual registry wiring.

The bootstrap reuses the standard General Domain registries, registers the
Opposition Domain into those exact same registries, and returns a bootstrap
exposing the composed registries.  General remains the fallback.

Operations are registered as **UNAVAILABLE** (fail-closed) unless real
implementations are injected via ``operation_implementations``.

Health/University participation occurs only through normal domain resolution/
composition/cross-domain flow when needed and authorized; their stores are never
loaded directly here.

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
from cmm.domains.oppositions.integration import register_oppositions_domain
from cmm.domains.permission_registry import DomainPermissionRegistry
from cmm.domains.profile_registry import InMemoryDomainProfileRegistry
from cmm.domains.registry import DomainRegistry
from cmm.domains.resolver import DefaultDomainResolver
from cmm.domains.resource_registry import InMemoryDomainResourceRegistry
from cmm.domains.workflow_registry import InMemoryDomainWorkflowRegistry


@dataclass(frozen=True, slots=True)
class OppositionsDomainBootstrap:
    """The standard registries with the Opposition Domain fully integrated."""

    domain_registry: DomainRegistry
    profile_registry: InMemoryDomainProfileRegistry
    resource_registry: InMemoryDomainResourceRegistry
    rule_registry: InMemoryReasoningRuleRegistry
    operation_registry: InMemoryDomainOperationRegistry
    workflow_registry: InMemoryDomainWorkflowRegistry
    permission_registry: DomainPermissionRegistry
    resolver: DefaultDomainResolver


def build_standard_oppositions_domain_bootstrap(
    *,
    operation_implementations: dict | None = None,
) -> OppositionsDomainBootstrap:
    """Build the standard registries with the Opposition Domain integrated.

    This reuses the standard General Domain bootstrap (shared registries + a
    resolver whose fallback is ``domain:general``), registers the complete
    Opposition Domain into those same registries, and returns the composed
    system.  No global state is modified.  General remains the fallback; a
    generic request resolves to General, and a Opposition signal routes to
    Oppositions when eligible, fail-closed otherwise.
    """
    general = build_standard_general_domain_bootstrap()

    register_oppositions_domain(
        domain_registry=general.domain_registry,
        profile_registry=general.profile_registry,
        resource_registry=general.resource_registry,
        rule_registry=general.rule_registry,
        operation_registry=general.operation_registry,
        workflow_registry=general.workflow_registry,
        permission_registry=general.permission_registry,
        operation_implementations=operation_implementations,
    )

    return OppositionsDomainBootstrap(
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
    "OppositionsDomainBootstrap",
    "build_standard_oppositions_domain_bootstrap",
]
