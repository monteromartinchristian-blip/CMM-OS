"""Phase 10.10 – Domain Resource Registry.

In-memory registry for ``DomainResourceDefinition`` records. No persistence,
no adapter loading, no filesystem or network access. Registered definitions
are returned as immutable tuples in deterministic order.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from cmm.domains.errors import DomainResourceRegistryError
from cmm.domains.identifiers import DomainId
from cmm.domains.resource_contracts import DomainResourceDefinition


@dataclass(frozen=True, slots=True)
class DomainResourceRegistrySnapshot:
    """Immutable snapshot of the resource registry state.

    ``definitions`` is the canonical ordered tuple of registered definitions.
    """

    definitions: tuple[DomainResourceDefinition, ...]


@runtime_checkable
class DomainResourceRegistry(Protocol):
    """Protocol for a Domain Resource definition registry."""

    def register(
        self, definition: DomainResourceDefinition
    ) -> DomainResourceDefinition: ...

    def get(self, definition_id: str) -> DomainResourceDefinition | None: ...

    def find_by_kind(self, kind: str) -> tuple[DomainResourceDefinition, ...]: ...

    def find_by_domain(
        self, domain_id: DomainId
    ) -> tuple[DomainResourceDefinition, ...]: ...

    def list_all(self) -> tuple[DomainResourceDefinition, ...]: ...

    def snapshot_state(self) -> DomainResourceRegistrySnapshot: ...

    def restore_state(self, snapshot: DomainResourceRegistrySnapshot) -> None: ...


class InMemoryDomainResourceRegistry:
    """Deterministic in-memory ``DomainResourceRegistry`` implementation."""

    def __init__(self) -> None:
        self._definitions: dict[str, DomainResourceDefinition] = {}

    def register(
        self, definition: DomainResourceDefinition
    ) -> DomainResourceDefinition:
        if not isinstance(definition, DomainResourceDefinition):
            raise DomainResourceRegistryError(
                "definition must be a DomainResourceDefinition",
                field="definition",
            )
        if definition.id in self._definitions:
            raise DomainResourceRegistryError(
                f"duplicate definition id: {definition.id!r}",
                field="id",
                details={"id": definition.id},
            )
        self._definitions[definition.id] = definition
        return definition

    def get(self, definition_id: str) -> DomainResourceDefinition | None:
        return self._definitions.get(definition_id)

    def find_by_kind(self, kind: str) -> tuple[DomainResourceDefinition, ...]:
        matches = [d for d in self._definitions.values() if d.kind == kind]
        matches.sort(key=lambda d: (-d.source_priority, d.domain_id.slug, d.id))
        return tuple(matches)

    def find_by_domain(
        self, domain_id: DomainId
    ) -> tuple[DomainResourceDefinition, ...]:
        matches = [d for d in self._definitions.values() if d.domain_id == domain_id]
        matches.sort(key=lambda d: (d.kind, -d.source_priority, d.id))
        return tuple(matches)

    def list_all(self) -> tuple[DomainResourceDefinition, ...]:
        matches = list(self._definitions.values())
        matches.sort(key=lambda d: (d.domain_id.slug, d.kind, d.id))
        return tuple(matches)

    # ── Snapshot / restore ───────────────────────────────────────────────────

    def snapshot_state(self) -> DomainResourceRegistrySnapshot:
        """Capture the full registry state for transactional rollback."""
        definitions = tuple(
            sorted(
                self._definitions.values(),
                key=lambda d: (d.domain_id.slug, d.kind, d.id),
            )
        )
        return DomainResourceRegistrySnapshot(definitions=definitions)

    def restore_state(self, snapshot: DomainResourceRegistrySnapshot) -> None:
        """Restore the full registry state from a snapshot.

        Validates the snapshot completely before mutating.  Rejects wrong
        types and invalid snapshots without modifying the registry.
        """
        if not isinstance(snapshot, DomainResourceRegistrySnapshot):
            raise DomainResourceRegistryError(
                "snapshot must be a DomainResourceRegistrySnapshot",
                field="snapshot",
            )
        if not isinstance(snapshot.definitions, tuple):
            raise DomainResourceRegistryError(
                "snapshot.definitions must be a tuple",
                field="snapshot.definitions",
            )
        for definition in snapshot.definitions:
            if not isinstance(definition, DomainResourceDefinition):
                raise DomainResourceRegistryError(
                    "snapshot.definitions contains a non-DomainResourceDefinition",
                    field="snapshot.definitions",
                )

        # Reject duplicate IDs before reconstructing the dictionary
        definition_ids = [d.id for d in snapshot.definitions]
        if len(definition_ids) != len(set(definition_ids)):
            raise DomainResourceRegistryError(
                "snapshot.definitions contains duplicate definition ids",
                field="snapshot.definitions",
            )

        # All validation passed — mutate
        self._definitions = {d.id: d for d in snapshot.definitions}


__all__ = [
    "DomainResourceRegistry",
    "DomainResourceRegistrySnapshot",
    "InMemoryDomainResourceRegistry",
]