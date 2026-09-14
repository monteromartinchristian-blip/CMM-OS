"""Phase 10.30 — Canonical Project Domain Bootstrap.

Provides the official factory for constructing standard domain registries
with the Project Domain integrated. Reuses the standard General Domain registries,
registers the Project Domain into those same registry objects, and returns a
bootstrap exposing the composed system. General remains the fallback.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from cmm.cognitive.reasoning_rule_registry import InMemoryReasoningRuleRegistry
from cmm.domains.life_plan.bootstrap import (
    build_standard_life_plan_domain_bootstrap,
)
from cmm.domains.operation_registry import InMemoryDomainOperationRegistry
from cmm.domains.permission_registry import DomainPermissionRegistry
from cmm.domains.profile_registry import InMemoryDomainProfileRegistry
from cmm.domains.project.integration import register_project_domain
from cmm.domains.registry import DomainRegistry
from cmm.domains.resolver import DefaultDomainResolver
from cmm.domains.resource_registry import InMemoryDomainResourceRegistry
from cmm.domains.workflow_registry import InMemoryDomainWorkflowRegistry

PROJECT_BOOTSTRAP_NAME = "ProjectDomainBootstrap"


@dataclass(frozen=True, slots=True)
class ProjectDomainBootstrap:
    """The standard registries with the Project Domain fully integrated."""

    domain_registry: DomainRegistry
    profile_registry: InMemoryDomainProfileRegistry
    resource_registry: InMemoryDomainResourceRegistry
    rule_registry: InMemoryReasoningRuleRegistry
    operation_registry: InMemoryDomainOperationRegistry
    workflow_registry: InMemoryDomainWorkflowRegistry
    permission_registry: DomainPermissionRegistry
    resolver: DefaultDomainResolver


def build_standard_project_domain_bootstrap(
    *,
    operation_implementations: dict[str, Any] | None = None,
) -> ProjectDomainBootstrap:
    """Build the standard registries with the Project Domain integrated extending Life Plan."""
    prior = build_standard_life_plan_domain_bootstrap()

    register_project_domain(
        domain_registry=prior.domain_registry,
        profile_registry=prior.profile_registry,
        resource_registry=prior.resource_registry,
        rule_registry=prior.rule_registry,
        operation_registry=prior.operation_registry,
        workflow_registry=prior.workflow_registry,
        permission_registry=prior.permission_registry,
        operation_implementations=operation_implementations,
    )

    return ProjectDomainBootstrap(
        domain_registry=prior.domain_registry,
        profile_registry=prior.profile_registry,
        resource_registry=prior.resource_registry,
        rule_registry=prior.rule_registry,
        operation_registry=prior.operation_registry,
        workflow_registry=prior.workflow_registry,
        permission_registry=prior.permission_registry,
        resolver=prior.resolver,
    )


__all__ = [
    "PROJECT_BOOTSTRAP_NAME",
    "ProjectDomainBootstrap",
    "build_standard_project_domain_bootstrap",
]
