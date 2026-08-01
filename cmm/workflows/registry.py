from __future__ import annotations

from .contracts import WorkflowDefinition
from .errors import WorkflowGraphError, WorkflowRegistryError
from .graph import validate_workflow_graph


def _version(value: str) -> tuple[int, int, int]:
    parts = value.split(".")
    if len(parts) != 3 or any(not p.isdigit() for p in parts):
        raise WorkflowRegistryError("workflow version must be SemVer")
    return tuple(int(p) for p in parts)  # type: ignore[return-value]


class InMemoryWorkflowRegistry:
    def __init__(self) -> None:
        self._definitions: dict[tuple[str, str], WorkflowDefinition] = {}

    def register(self, definition: WorkflowDefinition) -> None:
        validate_workflow_graph(definition)
        _version(definition.version)
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
