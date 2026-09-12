"""Phase 10.52 — Canonical Mental Health Domain Bootstrap.

Provides the official, recommended factory for constructing the standard
domain registries with the Mental Health Domain integrated.  This reuses the
standard General Domain bootstrap (shared registries plus a resolver whose
fallback is ``domain:general``), registers the complete Mental Health Domain
into those exact same registry objects, and returns the composed system.

General remains the fallback, so a generic request never resolves to Mental
Health merely because Mental Health is present.  A Mental Health signal routes
to Mental Health when eligible and is fail-closed (never silently absorbed by
General) when it is not.

Operations are registered as **UNAVAILABLE** (fail-closed) unless real
implementations are injected via ``operation_implementations``.

No side effects occur at import time; all registries are created fresh on each
call.  Phase 10.53 Neurodivergence is intentionally absent and is not required.
"""

from __future__ import annotations

from dataclasses import dataclass

from cmm.cognitive.reasoning_rule_registry import InMemoryReasoningRuleRegistry
from cmm.domains.general.bootstrap import build_standard_general_domain_bootstrap
from cmm.domains.mental_health.integration import register_mental_health_domain
from cmm.domains.operation_registry import InMemoryDomainOperationRegistry
from cmm.domains.permission_registry import DomainPermissionRegistry
from cmm.domains.profile_registry import InMemoryDomainProfileRegistry
from cmm.domains.registry import DomainRegistry
from cmm.domains.resolver import DefaultDomainResolver
from cmm.domains.resource_registry import InMemoryDomainResourceRegistry
from cmm.domains.workflow_registry import InMemoryDomainWorkflowRegistry

MENTAL_HEALTH_BOOTSTRAP_NAME = "MentalHealthDomainBootstrap"


@dataclass(frozen=True, slots=True)
class MentalHealthDomainBootstrap:
    """The standard registries with the Mental Health Domain integrated."""

    domain_registry: DomainRegistry
    profile_registry: InMemoryDomainProfileRegistry
    resource_registry: InMemoryDomainResourceRegistry
    rule_registry: InMemoryReasoningRuleRegistry
    operation_registry: InMemoryDomainOperationRegistry
    workflow_registry: InMemoryDomainWorkflowRegistry
    permission_registry: DomainPermissionRegistry
    resolver: DefaultDomainResolver


def build_standard_mental_health_domain_bootstrap(
    *,
    operation_implementations: dict | None = None,
) -> MentalHealthDomainBootstrap:
    """Build the standard registries with the Mental Health Domain integrated.

    This is the canonical, recommended composition path.  It reuses the
    standard General Domain bootstrap, registers the complete Mental Health
    Domain into those exact same registries, and returns the composed system.

    A Health-connected composition is obtained by additionally registering the
    existing Health Domain through its own canonical bootstrap/integration path
    (``cmm.domains.health``); Mental Health never copies Health declarations and
    never needs Health to be present to function.
    """
    general = build_standard_general_domain_bootstrap()

    register_mental_health_domain(
        domain_registry=general.domain_registry,
        profile_registry=general.profile_registry,
        resource_registry=general.resource_registry,
        rule_registry=general.rule_registry,
        operation_registry=general.operation_registry,
        workflow_registry=general.workflow_registry,
        permission_registry=general.permission_registry,
        operation_implementations=operation_implementations,
    )

    return MentalHealthDomainBootstrap(
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
    "MENTAL_HEALTH_BOOTSTRAP_NAME",
    "MentalHealthDomainBootstrap",
    "build_standard_mental_health_domain_bootstrap",
]
