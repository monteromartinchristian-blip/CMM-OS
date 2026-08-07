from dataclasses import dataclass

from cmm.domains.workflow_contracts import DomainWorkflowDefinition
from cmm.domains.workflow_errors import DomainWorkflowRegistryError
from cmm.workflows.errors import WorkflowRegistryError
from cmm.workflows.registry import InMemoryWorkflowRegistry, WorkflowRegistrySnapshot


@dataclass(frozen=True, slots=True)
class DomainWorkflowRegistrySnapshot:
    """Immutable snapshot of the domain workflow registry state.

    ``definitions`` is the canonical ordered tuple of registered definitions.
    ``common_registry`` is the snapshot of the underlying common workflow registry.
    """

    definitions: tuple[DomainWorkflowDefinition, ...]
    common_registry: WorkflowRegistrySnapshot


class InMemoryDomainWorkflowRegistry:
    def __init__(self, common_registry: InMemoryWorkflowRegistry | None = None) -> None:
        self.common_registry = common_registry or InMemoryWorkflowRegistry()
        self._definitions: dict[tuple[str, str], DomainWorkflowDefinition] = {}

    def register(self, definition: DomainWorkflowDefinition) -> None:
        self.common_registry.register(definition.to_common())
        self._definitions[(definition.workflow_id, definition.version)] = definition

    def get(self, workflow_id: str, version: str) -> DomainWorkflowDefinition:
        return self._definitions[(workflow_id, version)]

    def resolve_active(self, workflow_id: str) -> DomainWorkflowDefinition:
        common = self.common_registry.resolve_active(workflow_id)
        return self.get(common.workflow_id, common.version)

    def list_for_domain(self, domain_id: str) -> tuple[DomainWorkflowDefinition, ...]:
        return tuple(sorted((d for d in self._definitions.values() if d.domain_id == domain_id), key=lambda d: (d.workflow_id, d.version)))

    # ── Snapshot / restore ───────────────────────────────────────────────────

    def snapshot_state(self) -> DomainWorkflowRegistrySnapshot:
        """Capture the full registry state for transactional rollback."""
        definitions = tuple(
            sorted(
                self._definitions.values(),
                key=lambda d: (d.workflow_id, d.version),
            )
        )
        common_snapshot = self.common_registry.snapshot_state()
        return DomainWorkflowRegistrySnapshot(
            definitions=definitions,
            common_registry=common_snapshot,
        )

    def restore_state(self, snapshot: DomainWorkflowRegistrySnapshot) -> None:
        """Restore the full registry state from a snapshot.

        Validates the snapshot completely before mutating.  Rejects wrong
        types and invalid snapshots without modifying the registry.
        """
        if not isinstance(snapshot, DomainWorkflowRegistrySnapshot):
            raise WorkflowRegistryError(
                "snapshot must be a DomainWorkflowRegistrySnapshot"
            )
        if not isinstance(snapshot.definitions, tuple):
            raise WorkflowRegistryError("snapshot.definitions must be a tuple")
        if not isinstance(snapshot.common_registry, WorkflowRegistrySnapshot):
            raise WorkflowRegistryError(
                "snapshot.common_registry must be a WorkflowRegistrySnapshot"
            )
        for definition in snapshot.definitions:
            if not isinstance(definition, DomainWorkflowDefinition):
                raise WorkflowRegistryError(
                    "snapshot.definitions contains a non-DomainWorkflowDefinition"
                )

        # Reject duplicate (workflow_id, version) keys before reconstructing
        keys = [(d.workflow_id, d.version) for d in snapshot.definitions]
        if len(keys) != len(set(keys)):
            raise WorkflowRegistryError(
                "snapshot.definitions contains duplicate (workflow_id, version) keys"
            )

        # Cross-layer correspondence: the nested common registry must EXACTLY
        # match the definitions' to_common() representation in both keys and
        # values.  Validated purely BEFORE touching the nested common registry.
        expected_common_by_key = {
            (d.workflow_id, d.version): d.to_common() for d in snapshot.definitions
        }
        actual_common_by_key = {
            (c.workflow_id, c.version): c
            for c in snapshot.common_registry.definitions
        }
        expected_keys = set(expected_common_by_key)
        actual_keys = set(actual_common_by_key)
        if expected_keys != actual_keys:
            raise DomainWorkflowRegistryError(
                "Domain workflow snapshot common registry is inconsistent with "
                "its definitions",
                details={
                    "missing": sorted(expected_keys - actual_keys),
                    "extra": sorted(actual_keys - expected_keys),
                },
            )
        for key in expected_keys:
            if actual_common_by_key[key] != expected_common_by_key[key]:
                raise DomainWorkflowRegistryError(
                    "Domain workflow snapshot common definition does not match "
                    "its domain definition",
                    details={"workflow_id": key[0], "version": key[1]},
                )

        # Validate the nested common registry snapshot completely before any
        # local mutation.  This ensures a nested invalid restore cannot leave
        # partial state.
        self.common_registry.restore_state(snapshot.common_registry)

        # All validation passed — mutate
        self._definitions = {
            (d.workflow_id, d.version): d for d in snapshot.definitions
        }
