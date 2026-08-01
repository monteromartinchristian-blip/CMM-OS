from cmm.domains.workflow_contracts import DomainWorkflowDefinition
from cmm.workflows.registry import InMemoryWorkflowRegistry


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
