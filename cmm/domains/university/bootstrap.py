"""Phase 10.22 — Canonical University Domain Bootstrap.

Provides the official, recommended factory for constructing the standard
domain registries with University Domain integrated.  This is the canonical
composition path for callers that need a complete, discoverable University
Domain without manual registry wiring.

The bootstrap reuses the standard General Domain registries, registers the
University Domain into those exact same registries, and returns a bootstrap
exposing the composed registries.  University is a specialised/high-impact
domain; General is the generic fallback.  The resolver therefore keeps
``fallback_domain=domain:general`` so a generic request never resolves to
University merely because University is present.

Operations are registered as **UNAVAILABLE** (fail-closed) unless real
implementations are injected via ``operation_implementations``.  No fake
delegates are installed: a declared operation that is not yet implemented
must not appear available or successful.

No side effects occur at import time; all registries are created fresh on
each call.
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
from cmm.domains.registry import DomainRegistry
from cmm.domains.resolver import DefaultDomainResolver
from cmm.domains.resource_registry import InMemoryDomainResourceRegistry
from cmm.domains.university.integration import register_university_domain
from cmm.domains.workflow_registry import InMemoryDomainWorkflowRegistry


@dataclass(frozen=True, slots=True)
class UniversityDomainBootstrap:
    """The standard registries with University Domain fully integrated."""

    domain_registry: DomainRegistry
    profile_registry: InMemoryDomainProfileRegistry
    resource_registry: InMemoryDomainResourceRegistry
    rule_registry: InMemoryReasoningRuleRegistry
    operation_registry: InMemoryDomainOperationRegistry
    workflow_registry: InMemoryDomainWorkflowRegistry
    permission_registry: DomainPermissionRegistry
    resolver: DefaultDomainResolver


def build_standard_university_domain_bootstrap(
    *,
    operation_implementations: dict | None = None,
) -> UniversityDomainBootstrap:
    """Build the standard registries with University Domain integrated.

    This is the canonical, recommended composition path.  It reuses the
    standard General Domain bootstrap (shared registries + a resolver whose
    fallback is ``domain:general``), registers the complete University
    Domain into those exact same registries, and returns the composed system.
    No global state is modified.

    The returned bootstrap therefore contains BOTH General and University on
    the SAME registries, and exposes the standard ``DefaultDomainResolver``
    configured with ``fallback_domain=DomainId.from_str(GENERAL_DOMAIN_ID)``.
    A generic request resolves to General; a University signal routes to
    University when eligible, and is fail-closed (never silently diverted to
    General) when it is not.

    ``operation_implementations`` is an optional mapping of
    ``operation_id -> implementation`` for the UNIVERSITY operations.
    Operations without an injected implementation are registered as
    **UNAVAILABLE** (fail-closed) and are never reported as available or
    successful.
    """
    general = build_standard_general_domain_bootstrap()

    register_university_domain(
        domain_registry=general.domain_registry,
        profile_registry=general.profile_registry,
        resource_registry=general.resource_registry,
        rule_registry=general.rule_registry,
        operation_registry=general.operation_registry,
        workflow_registry=general.workflow_registry,
        permission_registry=general.permission_registry,
        operation_implementations=operation_implementations,
    )

    return UniversityDomainBootstrap(
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
    "UniversityDomainBootstrap",
    "build_standard_university_domain_bootstrap",
]