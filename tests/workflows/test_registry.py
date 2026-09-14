import pytest

from cmm.workflows.contracts import WorkflowDefinition, WorkflowNode
from cmm.workflows.errors import WorkflowRegistryError
from cmm.workflows.registry import InMemoryWorkflowRegistry


def definition(version):
    return WorkflowDefinition("x", version, "X", nodes=(WorkflowNode("n", "complete", "N"),))


def test_registry_resolves_semver_and_validates_late_references():
    registry = InMemoryWorkflowRegistry()
    registry.register(definition("1.9.0"))
    registry.register(definition("1.10.0"))
    assert registry.resolve_active("x").version == "1.10.0"
    with pytest.raises(WorkflowRegistryError):
        registry.register(definition("1.10.0"))
