"""Phase 10.51 — connected core conformance integration.

Real-component conformance across the canonical Domain Intelligence seams. No
chain of isolated mocks: every check drives production owners through their real
public interfaces, using the official first-party Project bootstrap as the
representative connected journey.

Seams proven here (extended by later Phase 10.51 tasks in this same module):

    canonical first-party DomainDefinition
      -> canonical pack/bootstrap/registry
      -> canonical resolution
      -> canonical composition
      -> canonical permission restriction
      -> resource / operation / workflow availability
"""

from __future__ import annotations

import dataclasses

from cmm.agent_runtime.domain_permission_contracts import (
    PermissionCapability,
    PermissionOutcome,
)
from cmm.domains.composer import DefaultDomainComposer
from cmm.domains.enums import DomainCompositionStatus, DomainResolutionStatus
from cmm.domains.identifiers import DomainId
from cmm.domains.life_plan.catalog import LIFE_PLAN_DOMAIN_ID
from cmm.domains.permission_contracts import DomainPermissionRequest
from cmm.domains.permission_registry import DomainPermissionRegistry
from cmm.domains.permission_resolution import DomainPermissionResolver
from cmm.domains.project.bootstrap import (
    ProjectDomainBootstrap,
    build_standard_project_domain_bootstrap,
)
from cmm.domains.project.catalog import PROJECT_DOMAIN_ID
from cmm.domains.resolution_contracts import DomainResolutionContext

# ── Connected-journey helpers (reuse the official bootstrap, never rewire) ────


def connected_bootstrap() -> ProjectDomainBootstrap:
    """The official Project bootstrap, with the primary Domain enabled."""
    bootstrap = build_standard_project_domain_bootstrap()
    bootstrap.domain_registry.enable(PROJECT_DOMAIN_ID)
    return bootstrap


def resolve_project(
    bootstrap: ProjectDomainBootstrap,
    *,
    context_id: str = "ctx:conformance:1",
    explicit: tuple[str, ...] = (PROJECT_DOMAIN_ID,),
):
    """Resolve through the canonical DefaultDomainResolver."""
    available = tuple(definition.id for definition in bootstrap.domain_registry.list())
    context = DomainResolutionContext(
        id=context_id,
        user_input="plan my project milestones",
        explicit_domains=tuple(DomainId.from_str(slug) for slug in explicit),
        available_domains=available,
        authorized_domains=available,
    )
    return bootstrap.resolver.resolve(context)


def compose_resolution(bootstrap: ProjectDomainBootstrap, resolution):
    """Compose through the canonical DefaultDomainComposer."""
    definitions = tuple(
        bootstrap.domain_registry.get_required(str(domain_id))
        for domain_id in (resolution.primary_domain, *resolution.supporting_domains)
    )
    return DefaultDomainComposer().compose(resolution, definitions)


def operation_execute_request(
    *,
    request_id: str = "req:conformance:op",
    operation_id: str = "project.review_status",
    operation_version: str = "1.0.0",
) -> DomainPermissionRequest:
    return DomainPermissionRequest(
        request_id=request_id,
        action=PermissionCapability.OPERATION_EXECUTE,
        domain_id=PROJECT_DOMAIN_ID,
        actor_id="actor:conformance",
        session_id="session:conformance",
        operation_id=operation_id,
        operation_version=operation_version,
    )


# ── Block 3/6/7: registry -> resolution -> composition are connected ──────────


def test_project_core_path_uses_canonical_registry_resolution_and_composition():
    bootstrap = connected_bootstrap()

    assert bootstrap.domain_registry.contains(PROJECT_DOMAIN_ID)
    assert bootstrap.resolver.fallback_domain == DomainId.from_str("domain:general")

    resolution = resolve_project(bootstrap)
    assert resolution.status is DomainResolutionStatus.RESOLVED
    assert resolution.primary_domain == DomainId.from_str(PROJECT_DOMAIN_ID)

    composition = compose_resolution(bootstrap, resolution)
    assert composition.primary_domain == DomainId.from_str(PROJECT_DOMAIN_ID)
    assert composition.status is DomainCompositionStatus.COMPOSED
    # Composition carries the canonical effective surfaces, not a parallel truth.
    assert composition.operations
    assert composition.rules
    assert composition.resources


def test_resolution_selects_exactly_one_primary_domain():
    bootstrap = connected_bootstrap()
    resolution = resolve_project(bootstrap)
    assert resolution.primary_domain is not None
    # supporting membership is explicit and bounded
    assert isinstance(resolution.supporting_domains, tuple)
    assert resolution.primary_domain not in resolution.supporting_domains


# ── Block 14: permissions restrict authority, never grant it ──────────────────


def test_permission_resolver_allows_declared_and_denies_prohibited():
    bootstrap = connected_bootstrap()
    resolver = DomainPermissionResolver(bootstrap.permission_registry)

    allowed = resolver.resolve(operation_execute_request(request_id="req:allow"))
    assert allowed.effective_permissions.decision is PermissionOutcome.ALLOW

    prohibited = resolver.resolve(
        DomainPermissionRequest(
            request_id="req:publication",
            action=PermissionCapability.PUBLICATION,
            domain_id=PROJECT_DOMAIN_ID,
            actor_id="actor:conformance",
            session_id="session:conformance",
        )
    )
    assert prohibited.effective_permissions.decision is PermissionOutcome.DENY


def test_supporting_domain_permission_intersection_is_most_restrictive():
    bootstrap = connected_bootstrap()
    resolver = DomainPermissionResolver(bootstrap.permission_registry)
    request = operation_execute_request(request_id="req:cross")

    baseline = resolver.resolve(request, supporting_domains=(LIFE_PLAN_DOMAIN_ID,))
    assert baseline.effective_permissions.decision is PermissionOutcome.ALLOW

    # Downgrade only the supporting Domain's policy; primary is unchanged.
    supporting_policy = bootstrap.permission_registry.active_for_domain(
        LIFE_PLAN_DOMAIN_ID
    )
    narrowed_registry = DomainPermissionRegistry()
    narrowed_registry.register(
        bootstrap.permission_registry.active_for_domain(PROJECT_DOMAIN_ID)
    )
    narrowed_registry.register(
        dataclasses.replace(
            supporting_policy,
            allowed_capabilities=tuple(
                capability
                for capability in supporting_policy.allowed_capabilities
                if capability is not PermissionCapability.OPERATION_EXECUTE
            ),
        )
    )
    narrowed_resolver = DomainPermissionResolver(narrowed_registry)

    restricted = narrowed_resolver.resolve(
        operation_execute_request(request_id="req:cross"),
        supporting_domains=(LIFE_PLAN_DOMAIN_ID,),
    )
    assert restricted.effective_permissions.decision is PermissionOutcome.DENY


def test_authority_downgrade_removing_permission_fails_closed():
    """Adversarial: drop OPERATION_EXECUTE from the canonical Project policy.

    A fresh registry/resolver re-evaluates from current authority; the stale
    ALLOW must not survive (STALE_AUTHORITY_REUSED=NO,
    DOWNGRADED_AUTHORITY=FAIL_CLOSED).
    """
    bootstrap = connected_bootstrap()
    request = operation_execute_request(request_id="req:downgrade")

    before = DomainPermissionResolver(bootstrap.permission_registry).resolve(request)
    assert before.effective_permissions.decision is PermissionOutcome.ALLOW

    project_policy = bootstrap.permission_registry.active_for_domain(PROJECT_DOMAIN_ID)
    downgraded = DomainPermissionRegistry()
    downgraded.register(
        dataclasses.replace(
            project_policy,
            allowed_capabilities=tuple(
                capability
                for capability in project_policy.allowed_capabilities
                if capability is not PermissionCapability.OPERATION_EXECUTE
            ),
        )
    )

    after = DomainPermissionResolver(downgraded).resolve(
        operation_execute_request(request_id="req:downgrade")
    )
    assert after.effective_permissions.decision is PermissionOutcome.DENY
