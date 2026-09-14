"""Phase 10.3 – Registry Validation.

Validates DomainDefinition entries against registry rules, including
dependency resolution, cycle detection, conflict detection, and
capability/operation/workflow compatibility.

All validation is read-only: it does not mutate the registry state.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone

from cmm.domains.contracts import (
    DomainDefinition,
)
from cmm.domains.errors import DomainContractValidationError
from cmm.domains.registry_contracts import (
    DomainValidationResult,
    _SemanticVersion,
    parse_semver,
)


class DomainDefinitionRegistryValidator:
    """Validates a DomainDefinition against registry constraints.

    All validation is pure: it does not mutate any state and returns
    an immutable ``DomainValidationResult``.
    """

    def validate(
        self,
        definition: DomainDefinition,
        *,
        registered: tuple[DomainDefinition, ...] = (),
    ) -> DomainValidationResult:
        """Validate *definition* against the set of already-registered definitions.

        Args:
            definition: The DomainDefinition to validate.
            registered: Already-registered definitions to check against.

        Returns:
            ``DomainValidationResult`` with structured errors, warnings,
            missing dependencies, and conflicts.
        """
        errors: list[str] = []
        warnings: list[str] = []
        missing_deps: list[str] = []
        conflicts: list[str] = []

        slug = definition.id.slug

        # ── 1. Type check ─────────────────────────────────────────────────
        if not isinstance(definition, DomainDefinition):
            errors.append(f"Expected DomainDefinition, got {type(definition).__name__}")
            return self._build_result(
                slug, definition.version, errors, warnings, missing_deps, conflicts
            )

        # ── 2. Identifier and version validity ────────────────────────────
        try:
            parse_semver(definition.version)
        except DomainContractValidationError:
            errors.append(f"Invalid version format: {definition.version!r}")

        if not definition.id.slug:
            errors.append("Domain id slug is empty")

        # ── 3. State coherence ───────────────────────────────────────────
        # DomainDefinition has no status field; we derive from enabled flag.
        # This is documented: enabled=False → effectively DISABLED or similar.

        # ── 4. Capability uniqueness within definition ─────────────────────
        cap_names: set[str] = set()
        for cap in definition.capabilities:
            if cap.name in cap_names:
                errors.append(f"Duplicate capability name: {cap.name!r}")
            cap_names.add(cap.name)

        # ── 5. Dependency uniqueness ──────────────────────────────────────
        all_deps = list(definition.dependencies) + list(
            definition.optional_dependencies
        )
        dep_slugs: set[str] = set()
        for dep in all_deps:
            if dep.domain_id.slug in dep_slugs:
                errors.append(f"Duplicate dependency: {dep.domain_id.slug}")
            dep_slugs.add(dep.domain_id.slug)

        # ── 6. No self-dependency ─────────────────────────────────────────
        # (Already validated by DomainDefinition.__post_init__ but double-check here)
        for dep in all_deps:
            if dep.domain_id.slug == slug:
                errors.append(f"Self-dependency detected: {slug}")
                break

        # ── 7. Dependency resolution ──────────────────────────────────────
        registered_by_slug: dict[str, list[DomainDefinition]] = defaultdict(list)
        for r in registered:
            registered_by_slug[r.id.slug].append(r)

        for dep in definition.dependencies:
            dep_slug = dep.domain_id.slug
            candidates = registered_by_slug.get(dep_slug, [])
            if not candidates:
                if dep.required:
                    missing_deps.append(dep_slug)
                    errors.append(f"Required dependency not registered: {dep_slug}")
                else:
                    warnings.append(f"Optional dependency not registered: {dep_slug}")
            else:
                # Check version constraint if specified
                if dep.version_constraint:
                    try:
                        min_ver = parse_semver(dep.version_constraint)
                    except DomainContractValidationError:
                        errors.append(
                            f"Invalid version constraint for dependency {dep_slug}: {dep.version_constraint!r}"
                        )
                        continue
                    satisfied = any(
                        self._version_satisfies(r.version, min_ver) for r in candidates
                    )
                    if not satisfied:
                        if dep.required:
                            errors.append(
                                f"Dependency {dep_slug} requires version >= {dep.version_constraint}, "
                                f"but registered versions: {[r.version for r in candidates]}"
                            )
                            missing_deps.append(dep_slug)
                        else:
                            warnings.append(
                                f"Optional dependency {dep_slug} version constraint "
                                f">= {dep.version_constraint} not satisfied by {[r.version for r in candidates]}"
                            )

        for dep in definition.optional_dependencies:
            dep_slug = dep.domain_id.slug
            candidates = registered_by_slug.get(dep_slug, [])
            if not candidates:
                warnings.append(f"Optional dependency not registered: {dep_slug}")
            elif dep.version_constraint:
                try:
                    min_ver = parse_semver(dep.version_constraint)
                except DomainContractValidationError:
                    errors.append(
                        f"Invalid version constraint for optional dependency {dep_slug}: {dep.version_constraint!r}"
                    )
                    continue
                satisfied = any(
                    self._version_satisfies(r.version, min_ver) for r in candidates
                )
                if not satisfied:
                    warnings.append(
                        f"Optional dependency {dep_slug} version constraint "
                        f">= {dep.version_constraint} not satisfied by {[r.version for r in candidates]}"
                    )

        # ── 8. Cycle detection ────────────────────────────────────────────
        cycle_result = self._detect_cycle(slug, definition, registered_by_slug)
        if cycle_result is not None:
            cycle_path, is_optional_only = cycle_result
            if is_optional_only:
                # Cycle formed only by optional deps: warning, not blocking
                warnings.append(
                    f"Optional dependency cycle detected: {' → '.join(cycle_path)}"
                )
            else:
                # Cycle contains at least one required edge: blocking
                errors.append(f"Dependency cycle detected: {' → '.join(cycle_path)}")
                conflicts.append(f"Dependency cycle: {' → '.join(cycle_path)}")

        # ── 9. Conflict detection ─────────────────────────────────────────
        # 9a. Declared conflicts
        for conflict in definition.conflicts:
            conflict_slug = conflict.domain_id.slug
            if conflict_slug in registered_by_slug:
                conflicts.append(
                    f"Declared conflict with registered domain {conflict_slug}: {conflict.reason}"
                )

        # Check reverse: do any registered domains declare a conflict with this one?
        for reg in registered:
            for reg_conflict in reg.conflicts:
                if reg_conflict.domain_id.slug == slug:
                    conflicts.append(
                        f"Registered domain {reg.id.slug} declares conflict with this domain: {reg_conflict.reason}"
                    )

        # 9b. Operations with same identifier
        op_conflicts = self._check_operation_conflicts(definition, registered)
        conflicts.extend(op_conflicts)

        # 9c. Workflows with same identifier
        wf_conflicts = self._check_workflow_conflicts(definition, registered)
        conflicts.extend(wf_conflicts)

        # ── 10. Build result ──────────────────────────────────────────────
        return self._build_result(
            slug, definition.version, errors, warnings, missing_deps, conflicts
        )

    # ── Private helpers ────────────────────────────────────────────────────

    @staticmethod
    def _version_satisfies(version: str, min_ver: _SemanticVersion) -> bool:
        """Check if a version string satisfies a minimum semantic version."""
        try:
            sv = parse_semver(version)
            return sv >= min_ver
        except DomainContractValidationError:
            return False

    @staticmethod
    def _detect_cycle(
        start_slug: str,
        definition: DomainDefinition,
        registered_by_slug: dict[str, list[DomainDefinition]],
    ) -> tuple[list[str], bool] | None:
        """Detect cycles in the dependency graph starting from start_slug.

        Returns ``(cycle_path, is_optional_only)`` or ``None``.
        ``is_optional_only`` is True when every edge in the cycle is
        an optional dependency (no required edges).

        Only follows edges that go TO a node that has required or optional
        deps registered.  The detection treats the graph formed by the
        definition's own deps PLUS all registered definitions' deps.
        """
        # Build adjacency with edge type info
        # required_edges: set of (from, to) edges that are required
        required_edges: set[tuple[str, str]] = set()
        optional_edges: set[tuple[str, str]] = set()

        def add_edges(slug: str, deps: list, is_required: bool) -> None:
            for dep in deps:
                to_slug = dep.domain_id.slug
                if is_required:
                    required_edges.add((slug, to_slug))
                else:
                    optional_edges.add((slug, to_slug))

        # Add edges from the definition being validated
        add_edges(start_slug, list(definition.dependencies), True)
        add_edges(start_slug, list(definition.optional_dependencies), False)

        # Add edges from all registered definitions
        for slug, defs in registered_by_slug.items():
            for d in defs:
                add_edges(slug, list(d.dependencies), True)
                add_edges(slug, list(d.optional_dependencies), False)

        # Build adjacency (both required and optional edges)
        adjacency: dict[str, set[str]] = {}
        for from_slug, to_slug in required_edges | optional_edges:
            adjacency.setdefault(from_slug, set()).add(to_slug)

        # DFS-based cycle detection with edge type tracking
        visited: set[str] = set()
        path: list[str] = []
        path_set: set[str] = set()
        # Track which edges on the current path are required
        _path_edges: list[tuple[str, str, bool]] = []  # (from, to, is_required)

        def dfs(node: str) -> tuple[list[str], bool] | None:
            if node in path_set:
                # Found cycle: extract from the entry point
                idx = path.index(node)
                cycle_path = list(path[idx:]) + [node]
                # Check if all edges in the cycle from idx onwards are optional
                cycle_edges = []
                for i in range(idx, len(path)):
                    edge = (path[i], path[i + 1] if i + 1 < len(path) else node)
                    is_req = edge in required_edges
                    cycle_edges.append(is_req)
                # Also check the closing edge (last -> node)
                if len(path) > idx:
                    closing_edge = (path[-1], node)
                    cycle_edges.append(closing_edge in required_edges)
                is_optional_only = not any(cycle_edges)
                return (cycle_path, is_optional_only)

            if node in visited:
                return None

            visited.add(node)
            path.append(node)
            path_set.add(node)

            neighbors = adjacency.get(node, set())
            for neighbor in sorted(neighbors):
                result = dfs(neighbor)
                if result is not None:
                    return result

            path.pop()
            path_set.discard(node)
            return None

        return dfs(start_slug)

    @staticmethod
    def _check_operation_conflicts(
        definition: DomainDefinition,
        registered: tuple[DomainDefinition, ...],
    ) -> list[str]:
        """Check for operation identifier conflicts across domains.

        Current limitation: DomainDefinition.operations are strings without
        contract metadata, so same identifiers are considered compatible
        rather than conflicting.  This will be refined when structural
        operation contracts become available (future phase).
        """
        # No automatic conflict — same operation IDs are compatible
        # until contract-level comparison is available.
        return []

    @staticmethod
    def _check_workflow_conflicts(
        definition: DomainDefinition,
        registered: tuple[DomainDefinition, ...],
    ) -> list[str]:
        """Check for workflow identifier conflicts across domains.

        Same limitation as operations: strings without structural contracts.
        """
        # No automatic conflict — same workflow IDs are compatible
        return []

    @staticmethod
    def _build_result(
        domain_id: str,
        version: str,
        errors: list[str],
        warnings: list[str],
        missing_deps: list[str],
        conflicts: list[str],
    ) -> DomainValidationResult:
        """Build a DomainValidationResult from collected issues.

        Errors, missing dependencies, and conflicts all make valid=False.
        This respects the strict DomainValidationResult contract.
        """
        valid = len(errors) == 0 and len(missing_deps) == 0 and len(conflicts) == 0
        return DomainValidationResult(
            domain_id=domain_id,
            version=version,
            valid=valid,
            errors=tuple(sorted(set(errors))),
            warnings=tuple(sorted(set(warnings))),
            missing_dependencies=tuple(sorted(set(missing_deps))),
            conflicts=tuple(sorted(set(conflicts))),
            checked_at=datetime.now(timezone.utc),
        )


__all__ = [
    "DomainDefinitionRegistryValidator",
]
