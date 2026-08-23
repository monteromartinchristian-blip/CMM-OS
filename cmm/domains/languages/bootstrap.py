"""Phase 10.26 — Canonical Languages Domain Bootstrap.

Provides the official factory for constructing the standard domain registries
with the Languages Domain integrated. Reuses the standard General Domain registries,
registers the Languages Domain into those same registry objects, and returns a
bootstrap exposing the composed system. General remains the fallback.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from cmm.cognitive.reasoning_rule_registry import InMemoryReasoningRuleRegistry
from cmm.domains.general.bootstrap import (
    build_standard_general_domain_bootstrap,
)
from cmm.domains.languages.integration import register_languages_domain
from cmm.domains.operation_registry import InMemoryDomainOperationRegistry
from cmm.domains.permission_registry import DomainPermissionRegistry
from cmm.domains.profile_registry import InMemoryDomainProfileRegistry
from cmm.domains.registry import DomainRegistry
from cmm.domains.resolver import DefaultDomainResolver
from cmm.domains.resource_registry import InMemoryDomainResourceRegistry
from cmm.domains.workflow_registry import InMemoryDomainWorkflowRegistry

LANGUAGES_BOOTSTRAP_NAME = "LanguagesDomainBootstrap"


@dataclass(frozen=True, slots=True)
class LanguagesDomainBootstrap:
    """The standard registries with the Languages Domain fully integrated."""

    domain_registry: DomainRegistry
    profile_registry: InMemoryDomainProfileRegistry
    resource_registry: InMemoryDomainResourceRegistry
    rule_registry: InMemoryReasoningRuleRegistry
    operation_registry: InMemoryDomainOperationRegistry
    workflow_registry: InMemoryDomainWorkflowRegistry
    permission_registry: DomainPermissionRegistry
    resolver: DefaultDomainResolver


def build_standard_languages_domain_bootstrap(
    *,
    operation_implementations: dict[str, Any] | None = None,
) -> LanguagesDomainBootstrap:
    """Build the standard registries with the Languages Domain integrated."""
    general = build_standard_general_domain_bootstrap()

    register_languages_domain(
        domain_registry=general.domain_registry,
        profile_registry=general.profile_registry,
        resource_registry=general.resource_registry,
        rule_registry=general.rule_registry,
        operation_registry=general.operation_registry,
        workflow_registry=general.workflow_registry,
        permission_registry=general.permission_registry,
        operation_implementations=operation_implementations,
    )

    return LanguagesDomainBootstrap(
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
    "LANGUAGES_BOOTSTRAP_NAME",
    "LanguagesDomainBootstrap",
    "build_standard_languages_domain_bootstrap",
]
