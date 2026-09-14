from __future__ import annotations

from dataclasses import dataclass

from .contracts import WorkflowDefinition
from .errors import WorkflowGraphError, WorkflowRegistryError
from .graph import validate_workflow_graph


@dataclass(frozen=True, slots=True)
class WorkflowRegistrySnapshot:
    """Immutable snapshot of the workflow registry state.

    ``definitions`` is the canonical ordered tuple of registered definitions.
    """

    definitions: tuple[WorkflowDefinition, ...]


def _version(value: str) -> tuple[int, int, int]:
    parts = value.split(".")
    if len(parts) != 3 or any(not p.isdigit() for p in parts):
        raise WorkflowRegistryError("workflow version must be SemVer")
    return tuple(int(p) for p in parts)  # type: ignore[return-value]


def _validate_workflow_definition(definition: WorkflowDefinition) -> None:
    """Validate a workflow definition exactly as ``register()`` requires.

    Single source of truth shared by ``register()`` and ``restore_state()`` so
    a snapshot can never admit a definition that the normal registration
    contract would reject.  Side-effect free.
    """
    validate_workflow_graph(definition)
    _version(definition.version)


class InMemoryWorkflowRegistry:
    def __init__(self) -> None:
        self._definitions: dict[tuple[str, str], WorkflowDefinition] = {}

    def register(self, definition: WorkflowDefinition) -> None:
        _validate_workflow_definition(definition)
        key = (definition.workflow_id, definition.version)
        if key in self._definitions:
            raise WorkflowRegistryError("workflow version already registered")
        self._definitions[key] = definition

    def get(self, workflow_id: str, version: str) -> WorkflowDefinition:
        try:
            return self._definitions[(workflow_id, version)]
        except KeyError as exc:
            raise WorkflowRegistryError("workflow is not registered") from exc

    def resolve_active(self, workflow_id: str) -> WorkflowDefinition:
        values = [v for (wid, _), v in self._definitions.items() if wid == workflow_id and v.enabled]
        if not values:
            raise WorkflowRegistryError("no enabled workflow version")
        return max(values, key=lambda item: _version(item.version))

    def list_definitions(self) -> tuple[WorkflowDefinition, ...]:
        return tuple(sorted(self._definitions.values(), key=lambda d: (d.workflow_id, _version(d.version))))

    def resolve_subworkflow(self, workflow_id: str, version: str) -> WorkflowDefinition | None:
        return self._definitions.get((workflow_id, version))

    def validate_registry(self) -> None:
        graph: dict[tuple[str, str], set[tuple[str, str]]] = {key: set() for key in self._definitions}
        for key, definition in self._definitions.items():
            for node in definition.nodes:
                if node.subworkflow_id:
                    target = (node.subworkflow_id, node.subworkflow_version or "")
                    if target not in self._definitions:
                        raise WorkflowGraphError("subworkflow reference does not exist", details={"workflow_id": node.subworkflow_id, "version": node.subworkflow_version})
                    graph[key].add(target)
        visiting: set[tuple[str, str]] = set()
        visited: set[tuple[str, str]] = set()

        def visit(workflow_key: tuple[str, str]) -> None:
            if workflow_key in visiting:
                raise WorkflowGraphError("workflow registry contains a versioned subworkflow cycle")
            if workflow_key in visited:
                return
            visiting.add(workflow_key)
            for child in graph[workflow_key]:
                visit(child)
            visiting.remove(workflow_key)
            visited.add(workflow_key)

        for workflow_key in sorted(graph):
            visit(workflow_key)

    # ── Snapshot / restore ───────────────────────────────────────────────────

    def snapshot_state(self) -> WorkflowRegistrySnapshot:
        """Capture the full registry state for transactional rollback."""
        definitions = tuple(
            sorted(
                self._definitions.values(),
                key=lambda d: (d.workflow_id, _version(d.version)),
            )
        )
        return WorkflowRegistrySnapshot(definitions=definitions)

    def restore_state(self, snapshot: WorkflowRegistrySnapshot) -> None:
        """Restore the full registry state from a snapshot.

        Validates the snapshot completely before mutating.  Rejects wrong
        types and invalid snapshots without modifying the registry.
        """
        if not isinstance(snapshot, WorkflowRegistrySnapshot):
            raise WorkflowRegistryError("snapshot must be a WorkflowRegistrySnapshot")
        if not isinstance(snapshot.definitions, tuple):
            raise WorkflowRegistryError("snapshot.definitions must be a tuple")
        for definition in snapshot.definitions:
            if not isinstance(definition, WorkflowDefinition):
                raise WorkflowRegistryError(
                    "snapshot.definitions contains a non-WorkflowDefinition"
                )
            _validate_workflow_definition(definition)

        # Reject duplicate (workflow_id, version) keys before reconstructing
        keys = [(d.workflow_id, d.version) for d in snapshot.definitions]
        if len(keys) != len(set(keys)):
            raise WorkflowRegistryError(
                "snapshot.definitions contains duplicate (workflow_id, version) keys"
            )

        # All validation passed — mutate
        self._definitions = {
            (d.workflow_id, d.version): d for d in snapshot.definitions
        }
