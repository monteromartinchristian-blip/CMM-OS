"""Phase 10.27 — Canonical Parenthood Domain Bootstrap.

Provides the official factory for constructing standard domain registries
with the Parenthood Domain integrated. Reuses the standard General Domain registries,
registers the Parenthood Domain into those same registry objects, and returns a
bootstrap exposing the composed system. General remains the fallback.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from cmm.cognitive.reasoning_rule_registry import InMemoryReasoningRuleRegistry
from cmm.domains.general.bootstrap import (
    build_standard_general_domain_bootstrap,
)
from cmm.domains.operation_registry import InMemoryDomainOperationRegistry
from cmm.domains.parenthood.integration import register_parenthood_domain
from cmm.domains.permission_registry import DomainPermissionRegistry
from cmm.domains.profile_registry import InMemoryDomainProfileRegistry
from cmm.domains.registry import DomainRegistry
from cmm.domains.resolver import DefaultDomainResolver
from cmm.domains.resource_registry import InMemoryDomainResourceRegistry
from cmm.domains.workflow_registry import InMemoryDomainWorkflowRegistry

PARENTHOOD_BOOTSTRAP_NAME = "ParenthoodDomainBootstrap"


@dataclass(frozen=True, slots=True)
class ParenthoodDomainBootstrap:
    """The standard registries with the Parenthood Domain fully integrated."""

    domain_registry: DomainRegistry
    profile_registry: InMemoryDomainProfileRegistry
    resource_registry: InMemoryDomainResourceRegistry
    rule_registry: InMemoryReasoningRuleRegistry
    operation_registry: InMemoryDomainOperationRegistry
    workflow_registry: InMemoryDomainWorkflowRegistry
    permission_registry: DomainPermissionRegistry
    resolver: DefaultDomainResolver


def build_standard_parenthood_domain_bootstrap(
    *,
    operation_implementations: dict[str, Any] | None = None,
) -> ParenthoodDomainBootstrap:
    """Build the standard registries with the Parenthood Domain integrated."""
    general = build_standard_general_domain_bootstrap()

    register_parenthood_domain(
        domain_registry=general.domain_registry,
        profile_registry=general.profile_registry,
        resource_registry=general.resource_registry,
        rule_registry=general.rule_registry,
        operation_registry=general.operation_registry,
        workflow_registry=general.workflow_registry,
        permission_registry=general.permission_registry,
        operation_implementations=operation_implementations,
    )

    return ParenthoodDomainBootstrap(
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
    "PARENTHOOD_BOOTSTRAP_NAME",
    "ParenthoodDomainBootstrap",
    "build_standard_parenthood_domain_bootstrap",
]
