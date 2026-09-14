"""Phase 10.8 – Composition Conflicts.

Dependency analysis and declared conflict analysis for domain composition.
"""

from __future__ import annotations

from typing import Any

from cmm.domains.composition_contracts import (
    DomainCompositionConflict,
    DomainCompositionDecision,
    DomainCompositionPolicy,
)
from cmm.domains.contracts import DomainDefinition
from cmm.domains.enums import DomainConflictPolicy
from cmm.domains.identifiers import DomainId


def analyze_dependencies(
    definitions: tuple[DomainDefinition, ...],
) -> tuple[
    tuple[DomainCompositionDecision, ...],
    tuple[DomainCompositionConflict, ...],
]:
    """Analyze dependencies among selected definitions.

    Only analyzes between selected domain IDs. No registry lookup or autoload.
    """
    if not definitions:
        return (), ()

    selected_slugs: set[str] = {d.id.slug for d in definitions}
    decisions: list[DomainCompositionDecision] = []
    conflicts: list[DomainCompositionConflict] = []

    for defn in definitions:
        # Required dependencies
        for dep in defn.dependencies:
            dep_slug = dep.domain_id.slug
            if dep_slug == defn.id.slug:
                # Self-dependency — defensive; DomainDefinition rejects it
                conflicts.append(
                    DomainCompositionConflict(
                        code="DOMAIN_COMPOSITION_CONFLICT_DETECTED",
                        category="dependencies",
                        domains=(DomainId.from_str(str(defn.id)),),
                        severity="blocking",
                        message=f"Domain {defn.id.slug} depends on itself",
                        blocking=True,
                        resolved=False,
                    )
                )
            elif dep_slug not in selected_slugs:
                # Missing required dependency
                conflicts.append(
                    DomainCompositionConflict(
                        code="DOMAIN_COMPOSITION_REQUIRED_DEPENDENCY_MISSING",
                        category="dependencies",
                        domains=(
                            DomainId.from_str(str(defn.id)),
                            DomainId.from_str(str(dep.domain_id)),
                        ),
                        severity="blocking",
                        message=f"Required dependency '{dep_slug}' not among selected domains",
                        blocking=True,
                        resolved=False,
                    )
                )

        # Optional dependencies
        for dep in defn.optional_dependencies:
            dep_slug = dep.domain_id.slug
            if dep_slug == defn.id.slug:
                conflicts.append(
                    DomainCompositionConflict(
                        code="DOMAIN_COMPOSITION_OPTIONAL_DEPENDENCY_MISSING",
                        category="dependencies",
                        domains=(DomainId.from_str(str(defn.id)),),
                        severity="warning",
                        message=f"Domain {defn.id.slug} has optional self-dependency",
                        blocking=False,
                        resolved=False,
                    )
                )
            elif dep_slug not in selected_slugs:
                # Missing optional dependency
                conflicts.append(
                    DomainCompositionConflict(
                        code="DOMAIN_COMPOSITION_OPTIONAL_DEPENDENCY_MISSING",
                        category="dependencies",
                        domains=(
                            DomainId.from_str(str(defn.id)),
                            DomainId.from_str(str(dep.domain_id)),
                        ),
                        severity="warning",
                        message=f"Optional dependency '{dep_slug}' not among selected domains",
                        blocking=False,
                        resolved=False,
                    )
                )

    # Cycle detection — separate required from optional
    required_cycles, optional_cycles, mixed_cycles = _detect_separated_cycles(
        definitions
    )

    # Required-only cycles → blocking
    for cycle_slugs in required_cycles:
        cycle_domains = tuple(
            DomainId.from_str(f"domain:{s}") for s in sorted(cycle_slugs)
        )
        conflicts.append(
            DomainCompositionConflict(
                code="DOMAIN_COMPOSITION_DEPENDENCY_CYCLE",
                category="dependencies",
                domains=cycle_domains,
                severity="blocking",
                message=f"Required dependency cycle detected: {' -> '.join(sorted(cycle_slugs))}",
                blocking=True,
                resolved=False,
                metadata={"edge_types": ("required",)},
            )
        )

    # Optional-involved cycles → non-blocking (PARTIAL)
    for cycle_slugs in optional_cycles:
        cycle_domains = tuple(
            DomainId.from_str(f"domain:{s}") for s in sorted(cycle_slugs)
        )
        conflicts.append(
            DomainCompositionConflict(
                code="DOMAIN_COMPOSITION_DEPENDENCY_CYCLE",
                category="dependencies",
                domains=cycle_domains,
                severity="warning",
                message=f"Optional dependency cycle detected: {' -> '.join(sorted(cycle_slugs))}",
                blocking=False,
                resolved=False,
                metadata={"edge_types": ("optional",)},
            )
        )

    for cycle_slugs, edge_types in mixed_cycles:
        cycle_domains = tuple(
            DomainId.from_str(f"domain:{s}") for s in sorted(cycle_slugs)
        )
        conflicts.append(
            DomainCompositionConflict(
                code="DOMAIN_COMPOSITION_DEPENDENCY_CYCLE",
                category="dependencies",
                domains=cycle_domains,
                severity="warning",
                message=f"Mixed dependency cycle detected: {' -> '.join(sorted(cycle_slugs))}",
                blocking=False,
                resolved=False,
                metadata={"edge_types": tuple(sorted(edge_types))},
            )
        )

    # Deduplicate decisions
    seen_decision_keys: set[tuple[str, str, str | None, str, tuple[str, ...], bool]] = (
        set()
    )
    deduped_decisions: list[DomainCompositionDecision] = []
    for d in decisions:
        key = (
            d.code,
            d.category,
            d.identifier,
            d.action,
            tuple(sorted(str(dom) for dom in d.domains)),
            d.blocking,
        )
        if key not in seen_decision_keys:
            seen_decision_keys.add(key)
            deduped_decisions.append(d)

    return tuple(deduped_decisions), _deduplicate_conflicts(conflicts)


def _detect_separated_cycles(
    definitions: tuple[DomainDefinition, ...],
) -> tuple[list[set[str]], list[set[str]], list[tuple[set[str], set[str]]]]:
    """Detect cycles separating required from optional edges.

    Returns: (required_only_cycles, optional_only_cycles, mixed_cycles_with_edge_types)
    """
    slug_to_idx = {d.id.slug: i for i, d in enumerate(definitions)}

    required_graph: dict[str, set[str]] = {}
    optional_graph: dict[str, set[str]] = {}
    all_graph: dict[str, set[str]] = {}

    for defn in definitions:
        slug = defn.id.slug
        r_deps = set()
        o_deps = set()
        for dep in defn.dependencies:
            if dep.domain_id.slug in slug_to_idx:
                r_deps.add(dep.domain_id.slug)
        for dep in defn.optional_dependencies:
            if dep.domain_id.slug in slug_to_idx:
                o_deps.add(dep.domain_id.slug)
        required_graph[slug] = r_deps
        optional_graph[slug] = o_deps
        all_graph[slug] = r_deps | o_deps

    # Find all cycles in the combined graph and classify edge types
    all_cycles = _find_cycles(all_graph)
    required_cycles: list[set[str]] = []
    optional_cycles: list[set[str]] = []
    mixed_cycles: list[tuple[set[str], set[str]]] = []

    for cycle in all_cycles:
        cycle_list = sorted(cycle)
        # Determine edge types used in this cycle
        has_required = False
        has_optional = False
        for i, slug in enumerate(cycle_list):
            next_slug = cycle_list[(i + 1) % len(cycle_list)]
            # Check if edge exists in required or optional graph
            if next_slug in required_graph.get(slug, set()):
                has_required = True
            if next_slug in optional_graph.get(slug, set()):
                has_optional = True

        if has_required and not has_optional:
            required_cycles.append(cycle)
        elif has_optional and not has_required:
            optional_cycles.append(cycle)
        else:
            edge_types = set()
            if has_required:
                edge_types.add("required")
            if has_optional:
                edge_types.add("optional")
            mixed_cycles.append((cycle, edge_types))

    return required_cycles, optional_cycles, mixed_cycles


def _find_cycles(graph: dict[str, set[str]]) -> list[set[str]]:
    """Find all unique cycles in a directed graph using DFS.

    Returns cycles as sets of node slugs.
    """
    cycles: list[set[str]] = []
    visited: set[str] = set()
    in_stack: set[str] = set()

    def dfs(slug: str, stack: list[str]) -> None:
        if slug in in_stack:
            cycle_start = stack.index(slug)
            cycle_nodes = set(stack[cycle_start:])
            for existing in cycles:
                if cycle_nodes == existing:
                    return
            cycles.append(cycle_nodes)
            return
        if slug in visited:
            return
        visited.add(slug)
        in_stack.add(slug)
        stack.append(slug)
        for neighbor in sorted(graph.get(slug, set())):
            dfs(neighbor, stack)
        stack.pop()
        in_stack.discard(slug)

    for slug in sorted(graph.keys()):
        if slug not in visited:
            dfs(slug, [])

    return cycles


def analyze_declared_conflicts(
    definitions: tuple[DomainDefinition, ...],
    policy: DomainCompositionPolicy,
) -> tuple[
    tuple[DomainCompositionDecision, ...],
    tuple[DomainCompositionConflict, ...],
]:
    """Analyze declared conflicts among selected domains."""
    if not definitions:
        return (), ()

    selected_slugs: set[str] = {d.id.slug for d in definitions}
    blocking_set = set(policy.blocking_severities)
    partial_set = set(policy.partial_severities)

    conflicts: list[DomainCompositionConflict] = []
    decisions: list[DomainCompositionDecision] = []

    for defn in definitions:
        for conflict in defn.conflicts:
            target_slug = conflict.domain_id.slug

            if target_slug not in selected_slugs:
                continue

            severity = conflict.severity
            is_blocking_base = severity in blocking_set
            is_partial_base = severity in partial_set

            domain_ids = tuple(
                sorted(
                    [
                        DomainId.from_str(str(defn.id)),
                        DomainId.from_str(str(conflict.domain_id)),
                    ],
                    key=lambda d: d.slug,
                )
            )

            if is_blocking_base:
                # Blocking severity — always BLOCKED regardless of conflict policy
                conflicts.append(
                    DomainCompositionConflict(
                        code="DOMAIN_COMPOSITION_CONFLICT_BLOCKED",
                        category="declared_conflicts",
                        domains=domain_ids,
                        severity=severity,
                        message=f"Declared conflict: {conflict.reason}",
                        blocking=True,
                        resolved=False,
                    )
                )
            elif is_partial_base:
                # Non-blocking severity
                if policy.conflict_policy == DomainConflictPolicy.BLOCK_ON_CONFLICT:
                    conflicts.append(
                        DomainCompositionConflict(
                            code="DOMAIN_COMPOSITION_CONFLICT_BLOCKED",
                            category="declared_conflicts",
                            domains=domain_ids,
                            severity=severity,
                            message=f"Declared conflict: {conflict.reason}",
                            blocking=True,
                            resolved=False,
                        )
                    )
                elif policy.conflict_policy == DomainConflictPolicy.PRIMARY_PRECEDENCE:
                    primary_slug = definitions[0].id.slug
                    involved_slugs = {d.slug for d in domain_ids}
                    if primary_slug in involved_slugs:
                        # Primary is one of the parties → resolved
                        conflicts.append(
                            DomainCompositionConflict(
                                code="DOMAIN_COMPOSITION_CONFLICT_RESOLVED",
                                category="declared_conflicts",
                                domains=domain_ids,
                                severity=severity,
                                message=f"Declared conflict resolved by primary precedence: {conflict.reason}",
                                blocking=False,
                                resolved=True,
                                resolution="primary_precedence",
                            )
                        )
                        decisions.append(
                            DomainCompositionDecision(
                                code="DOMAIN_COMPOSITION_PRIMARY_PRECEDENCE",
                                category="declared_conflicts",
                                identifier=None,
                                action="primary_precedence",
                                domains=domain_ids,
                                reason="Declared conflict resolved by primary precedence",
                            )
                        )
                    else:
                        # Primary not involved → PARTIAL, unresolved
                        conflicts.append(
                            DomainCompositionConflict(
                                code="DOMAIN_COMPOSITION_CONFLICT_DETECTED",
                                category="declared_conflicts",
                                domains=domain_ids,
                                severity=severity,
                                message=f"Declared conflict (primary not involved): {conflict.reason}",
                                blocking=False,
                                resolved=False,
                            )
                        )
                else:
                    # MOST_RESTRICTIVE — non-blocking, unresolved
                    conflicts.append(
                        DomainCompositionConflict(
                            code="DOMAIN_COMPOSITION_CONFLICT_DETECTED",
                            category="declared_conflicts",
                            domains=domain_ids,
                            severity=severity,
                            message=f"Declared conflict (partial): {conflict.reason}",
                            blocking=False,
                            resolved=False,
                        )
                    )
            else:
                # Unknown severity → non-blocking, unresolved
                if policy.conflict_policy == DomainConflictPolicy.BLOCK_ON_CONFLICT:
                    conflicts.append(
                        DomainCompositionConflict(
                            code="DOMAIN_COMPOSITION_CONFLICT_BLOCKED",
                            category="declared_conflicts",
                            domains=domain_ids,
                            severity=severity,
                            message=f"Declared conflict: {conflict.reason}",
                            blocking=True,
                            resolved=False,
                        )
                    )
                else:
                    conflicts.append(
                        DomainCompositionConflict(
                            code="DOMAIN_COMPOSITION_CONFLICT_DETECTED",
                            category="declared_conflicts",
                            domains=domain_ids,
                            severity=severity,
                            message=f"Declared conflict with unknown severity '{severity}': {conflict.reason}",
                            blocking=False,
                            resolved=False,
                        )
                    )

    return tuple(decisions), _deduplicate_conflicts(conflicts)


def _deduplicate_conflicts(
    conflicts: list[DomainCompositionConflict],
) -> tuple[DomainCompositionConflict, ...]:
    """Deduplicate conflicts by canonical key including message and metadata."""
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
            tuple[tuple[str, Any], ...] | None,
        ],
        DomainCompositionConflict,
    ] = {}

    for c in conflicts:
        canonical_meta: tuple[tuple[str, Any], ...] | None = None
        if c.metadata is not None and len(c.metadata) > 0:
            canonical_meta = tuple(sorted((k, v) for k, v in c.metadata.items()))
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
        else:
            # Merge domains if needed
            existing = seen[key]
            merged_domains = tuple(
                sorted(
                    set(list(existing.domains) + list(c.domains)),
                    key=lambda d: d.slug,
                )
            )
            if merged_domains != existing.domains:
                seen[key] = DomainCompositionConflict(
                    code=existing.code,
                    category=existing.category,
                    domains=merged_domains,
                    severity=existing.severity,
                    message=existing.message,
                    blocking=existing.blocking,
                    resolved=existing.resolved,
                    resolution=existing.resolution,
                    metadata=existing.metadata,
                )

    # Sort deterministically
    sorted_conflicts = sorted(
        seen.values(),
        key=lambda c: (
            c.blocking,
            c.severity,
            c.category,
            tuple(d.slug for d in c.domains),
            c.code,
            c.message,
        ),
        reverse=True,
    )
    return tuple(sorted_conflicts)


__all__ = [
    "analyze_declared_conflicts",
    "analyze_dependencies",
]
