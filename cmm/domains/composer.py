"""Phase 10.8 – Domain Composer.

Deterministic composer that converts a resolved set of domain definitions
into one immutable, declarative effective composition.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable, Iterable
from datetime import datetime, timezone
from typing import Any

from typing_extensions import Protocol, runtime_checkable

from cmm.domains.composition_conflicts import (
    analyze_declared_conflicts,
    analyze_dependencies,
)
from cmm.domains.composition_contracts import (
    DomainComposition,
    DomainCompositionConflict,
    DomainCompositionDecision,
    DomainCompositionPolicy,
)
from cmm.domains.composition_items import (
    compose_capability_items,
    compose_presentation,
    compose_reasoning_profile,
    compose_reference_items,
)
from cmm.domains.composition_permissions import (
    compose_permissions,
    filter_operations_by_permissions,
)
from cmm.domains.contracts import DomainDefinition
from cmm.domains.enums import DomainCompositionStatus, DomainResolutionStatus
from cmm.domains.errors import (
    DomainCompositionConfigurationError,
    DomainCompositionContractError,
)
from cmm.domains.resolver_contracts import DomainResolutionResult

# ── Protocol ──────────────────────────────────────────────────────────────────


@runtime_checkable
class DomainComposer(Protocol):
    """Protocol for domain composition.

    Implementations take a ``DomainResolutionResult`` and a collection of
    ``DomainDefinition`` instances and return a ``DomainComposition``.
    """

    def compose(
        self,
        resolution: DomainResolutionResult,
        definitions: Iterable[DomainDefinition],
    ) -> DomainComposition: ...


# ── Helpers ────────────────────────────────────────────────────────────────────


def _validate_resolution(resolution: DomainResolutionResult) -> None:
    """Validate that the resolution is acceptable for composition."""
    if not isinstance(resolution, DomainResolutionResult):
        raise DomainCompositionContractError(
            f"resolution must be a DomainResolutionResult, got {type(resolution).__name__}",
            field="resolution",
        )

    if resolution.status != DomainResolutionStatus.RESOLVED:
        raise DomainCompositionContractError(
            f"Cannot compose from resolution with status {resolution.status.value}",
            field="resolution.status",
        )

    if resolution.primary_domain is None:
        raise DomainCompositionContractError(
            "Resolution has no primary domain",
            field="resolution.primary_domain",
        )

    if resolution.requires_clarification:
        raise DomainCompositionContractError(
            "Cannot compose when resolution requires clarification",
            field="resolution.requires_clarification",
        )


def _normalize_definitions(
    definitions: Iterable[DomainDefinition],
    resolution: DomainResolutionResult,
) -> tuple[DomainDefinition, ...]:
    """Materialize, validate, and order definitions.

    Returns: (primary, supplying...) in resolution order.
    """
    def_list = list(definitions)

    if not def_list:
        raise DomainCompositionContractError(
            "No definitions provided for composition",
            field="definitions",
        )

    for defn in def_list:
        if not isinstance(defn, DomainDefinition):
            raise DomainCompositionContractError(
                f"All definitions must be DomainDefinition instances, got {type(defn).__name__}",
                field="definitions",
            )

    # Check for duplicate IDs
    seen_ids: set[str] = set()
    for defn in def_list:
        slug = defn.id.slug
        if slug in seen_ids:
            raise DomainCompositionContractError(
                f"Duplicate definition ID: {slug}",
                field="definitions",
                details={"duplicate": slug},
            )
        seen_ids.add(slug)

    # Build lookup by slug
    slug_to_def = {d.id.slug: d for d in def_list}

    # Validate primary presence
    primary_slug = resolution.primary_domain.slug
    if primary_slug not in slug_to_def:
        raise DomainCompositionContractError(
            f"Primary domain '{primary_slug}' not found in definitions",
            field="definitions",
        )

    primary_def = slug_to_def[primary_slug]

    # Validate primary is enabled
    if not primary_def.enabled:
        raise DomainCompositionContractError(
            f"Primary domain '{primary_slug}' is disabled",
            field="definitions",
            details={"domain": primary_slug},
        )

    # Build ordered tuple: primary first, then supporting in resolution order
    ordered: list[DomainDefinition] = [primary_def]
    supporting_slugs = [sd.slug for sd in resolution.supporting_domains]

    for sup_slug in supporting_slugs:
        if sup_slug not in slug_to_def:
            raise DomainCompositionContractError(
                f"Supporting domain '{sup_slug}' not found in definitions",
                field="definitions",
            )
        sup_def = slug_to_def[sup_slug]
        if not sup_def.enabled:
            raise DomainCompositionContractError(
                f"Supporting domain '{sup_slug}' is disabled",
                field="definitions",
                details={"domain": sup_slug},
            )
        ordered.append(sup_def)

    # Check for extra definitions not in resolution
    expected_slugs = {primary_slug} | set(supporting_slugs)
    actual_slugs = {d.id.slug for d in def_list}
    extra = actual_slugs - expected_slugs
    if extra:
        raise DomainCompositionContractError(
            f"Extra definitions not in resolution: {sorted(extra)}",
            field="definitions",
            details={"extra": sorted(extra)},
        )

    return tuple(ordered)


PARTIAL_DECISION_CODES: frozenset[str] = frozenset(
    {
        "DOMAIN_COMPOSITION_OPERATION_EXCLUDED",
        "DOMAIN_COMPOSITION_OPTIONAL_DEPENDENCY_MISSING",
    }
)


def _derive_status(
    conflicts: tuple[DomainCompositionConflict, ...],
    decisions: tuple[DomainCompositionDecision, ...],
) -> DomainCompositionStatus:
    """Derive composition status from conflicts and decisions."""
    # Blocking conflicts
    unresolved_blocking = any(c.blocking and not c.resolved for c in conflicts)
    if unresolved_blocking:
        return DomainCompositionStatus.BLOCKED

    # Partial: non-blocking unresolved conflicts or exclusion/partial decisions
    unresolved_non_blocking = any(not c.blocking and not c.resolved for c in conflicts)
    partial_decisions = any(d.code in PARTIAL_DECISION_CODES for d in decisions)
    if unresolved_non_blocking or partial_decisions:
        return DomainCompositionStatus.PARTIAL

    return DomainCompositionStatus.COMPOSED


def _deduplicate_decisions_by_key(
    decisions: list[DomainCompositionDecision],
) -> tuple[DomainCompositionDecision, ...]:
    """Deduplicate decisions by semantic key."""
    seen: dict[
        tuple[str, str, str | None, str, tuple[str, ...], bool],
        DomainCompositionDecision,
    ] = {}
    for d in decisions:
        key = (
            d.code,
            d.category,
            d.identifier,
            d.action,
            tuple(sorted(dom.slug for dom in d.domains)),
            d.blocking,
        )
        if key not in seen:
            seen[key] = d
    return tuple(seen.values())


def _deduplicate_conflicts_by_key(
    conflicts: list[DomainCompositionConflict],
) -> tuple[DomainCompositionConflict, ...]:
    """Deduplicate conflicts by semantic key — message, metadata included."""
    seen: dict[
        tuple[
            str,
            str,
            tuple[str, ...],
            str,
            str,
            bool,
            bool,
            str | None,
            tuple[tuple[str, Any], ...],
        ],
        DomainCompositionConflict,
    ] = {}
    for c in conflicts:
        canonical_meta: tuple[tuple[str, Any], ...] = (
            tuple(sorted((k, v) for k, v in c.metadata.items())) if c.metadata else ()
        )
        key = (
            c.code,
            c.category,
            tuple(sorted(d.slug for d in c.domains)),
            c.severity,
            c.message,
            c.blocking,
            c.resolved,
            c.resolution,
            canonical_meta,
        )
        if key not in seen:
            seen[key] = c
    return tuple(seen.values())


def _sort_decisions(
    decisions: tuple[DomainCompositionDecision, ...],
) -> tuple[DomainCompositionDecision, ...]:
    """Sort decisions deterministically."""
    return tuple(
        sorted(
            decisions,
            key=lambda d: (
                not d.blocking,  # blocking first
                d.category,
                d.identifier or "",
                d.code,
                d.action,
                tuple(d.slug for d in d.domains),
            ),
        )
    )


def _sort_conflicts(
    conflicts: tuple[DomainCompositionConflict, ...],
) -> tuple[DomainCompositionConflict, ...]:
    """Sort conflicts deterministically."""
    return tuple(
        sorted(
            conflicts,
            key=lambda c: (
                not c.blocking,  # blocking first
                c.severity,
                c.category,
                tuple(d.slug for d in c.domains),
                c.code,
                c.message,
            ),
        )
    )


# ── Default implementation ────────────────────────────────────────────────────


class DefaultDomainComposer:
    """Default deterministic domain composer.

    Pure function of resolution + definitions + policy.
    No registry, no stores, no filesystem, no LLM, no network.
    """

    def __init__(
        self,
        *,
        policy: DomainCompositionPolicy | None = None,
        clock: Callable[[], datetime] | None = None,
        id_factory: Callable[[], str] | None = None,
    ) -> None:
        """Initialize the composer with optional policy, clock, and ID factory.

        Args:
            policy: DomainCompositionPolicy (default if None).
            clock: Callable returning a timezone-aware datetime (default: UTC now).
            id_factory: Callable returning a non-empty composition ID (default: UUID-based).
        """
        self._policy = policy or DomainCompositionPolicy()
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._id_factory = id_factory or (lambda: f"domain-composition-{uuid.uuid4()}")

    def compose(
        self,
        resolution: DomainResolutionResult,
        definitions: Iterable[DomainDefinition],
    ) -> DomainComposition:
        """Compose a DomainComposition from a resolution and definitions."""
        # 1. Validate resolution
        _validate_resolution(resolution)

        # 2. Materialize and order definitions
        ordered_defs = _normalize_definitions(definitions, resolution)

        # 3. Compose reasoning profile
        effective_profile, profile_decisions = compose_reasoning_profile(ordered_defs)

        # 4. Compose exact-reference items
        rules, rules_decisions = compose_reference_items(
            category="rules",
            definitions=ordered_defs,
            value_getter=lambda d: d.rules,
        )
        resources, resources_decisions = compose_reference_items(
            category="resources",
            definitions=ordered_defs,
            value_getter=lambda d: d.resources,
        )
        operations_pre_filter, op_decisions = compose_reference_items(
            category="operations",
            definitions=ordered_defs,
            value_getter=lambda d: d.operations,
        )
        workflows, wf_decisions = compose_reference_items(
            category="workflows",
            definitions=ordered_defs,
            value_getter=lambda d: d.workflows,
        )
        validators, val_decisions = compose_reference_items(
            category="validators",
            definitions=ordered_defs,
            value_getter=lambda d: d.validators,
        )

        # Capabilities
        capabilities, cap_decisions = compose_capability_items(ordered_defs)

        # 5. Compose permissions
        permissions, perm_decisions, perm_conflicts = compose_permissions(
            ordered_defs, self._policy
        )

        # 6. Filter operations by permissions
        operations, op_filter_decisions = filter_operations_by_permissions(
            operations_pre_filter, permissions, ordered_defs
        )

        # 7. Compose presentation
        presentation, pres_decisions, pres_conflicts = compose_presentation(
            ordered_defs, self._policy
        )

        # 8. Analyze dependencies
        dep_decisions, dep_conflicts = analyze_dependencies(ordered_defs)

        # 9. Analyze declared conflicts
        decl_decisions, decl_conflicts = analyze_declared_conflicts(
            ordered_defs, self._policy
        )

        # 10. Aggregate all decisions and conflicts
        all_decisions: list[DomainCompositionDecision] = []
        all_conflicts: list[DomainCompositionConflict] = []

        for decisions_list in (
            profile_decisions,
            rules_decisions,
            resources_decisions,
            op_decisions,
            op_filter_decisions,
            wf_decisions,
            val_decisions,
            cap_decisions,
            perm_decisions,
            pres_decisions,
            dep_decisions,
            decl_decisions,
        ):
            all_decisions.extend(decisions_list)

        for conflicts_list in (
            perm_conflicts,
            pres_conflicts,
            dep_conflicts,
            decl_conflicts,
        ):
            all_conflicts.extend(conflicts_list)

        # 11. Deduplicate
        deduped_decisions = _deduplicate_decisions_by_key(all_decisions)
        deduped_conflicts = _deduplicate_conflicts_by_key(all_conflicts)

        # 12. Sort deterministically
        sorted_decisions = _sort_decisions(deduped_decisions)
        sorted_conflicts = _sort_conflicts(deduped_conflicts)

        # 13. Derive status
        status = _derive_status(sorted_conflicts, sorted_decisions)

        # 14. Invoke factories — errors propagate without wrapping
        composed_at = self._clock()
        if not isinstance(composed_at, datetime):
            raise DomainCompositionConfigurationError(
                f"Clock must return a datetime, got {type(composed_at).__name__}",
                field="clock",
            )
        if composed_at.tzinfo is None:
            raise DomainCompositionConfigurationError(
                "Clock must return a timezone-aware datetime",
                field="clock",
            )

        composition_id = self._id_factory()
        if not isinstance(composition_id, str) or not composition_id.strip():
            raise DomainCompositionConfigurationError(
                "ID factory must return a non-empty string",
                field="id_factory",
            )

        # 15. Build DomainComposition
        primary_domain = ordered_defs[0].id
        supporting_domains = tuple(d.id for d in ordered_defs[1:])

        return DomainComposition(
            id=composition_id,
            resolution_id=resolution.id,
            status=status,
            primary_domain=primary_domain,
            supporting_domains=supporting_domains,
            effective_profile=effective_profile,
            rules=rules,
            resources=resources,
            operations=operations,
            workflows=workflows,
            validators=validators,
            capabilities=capabilities,
            permissions=permissions,
            presentation=presentation,
            decisions=sorted_decisions,
            conflicts=sorted_conflicts,
            policy=self._policy,
            composed_at=composed_at,
        )


__all__ = [
    "DefaultDomainComposer",
    "DomainComposer",
]
