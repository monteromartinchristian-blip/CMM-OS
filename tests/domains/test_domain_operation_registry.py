from __future__ import annotations

from dataclasses import replace

import pytest

from cmm.agent_runtime.operation_execution_contracts import AgentOperationRequest
from cmm.agent_runtime.operation_registry import InMemoryAgentOperationRegistry
from cmm.domains import (
    DomainOperationAvailabilityContext,
    DomainOperationAvailabilityResolver,
    DomainOperationDefinition,
    DomainOperationRegistryError,
    DomainOperationStatus,
    DomainOperationType,
    InMemoryDomainOperationRegistry,
)


def _definition(
    operation_id: str = "project.analyse_architecture",
    version: str = "1.0.0",
    **kwargs: object,
) -> DomainOperationDefinition:
    values = {
        "operation_id": operation_id,
        "domain_id": f"domain:{operation_id.split('.', 1)[0]}",
        "version": version,
        "name": "Analyse architecture",
        "description": "Return a structural analysis",
        "operation_type": DomainOperationType.ANALYSIS,
        "output_schema": {"type": "object"},
    }
    values.update(kwargs)
    return DomainOperationDefinition(**values)  # type: ignore[arg-type]


class Implementation:
    def __init__(self, definition: DomainOperationDefinition) -> None:
        self.definition = definition
        self.calls = 0

    def execute(self, request: AgentOperationRequest) -> dict[str, object]:
        self.calls += 1
        return {"success": True, "output": {"operation": request.operation_name}}


def test_registry_adapts_to_common_registry_without_execution() -> None:
    common = InMemoryAgentOperationRegistry()
    registry = InMemoryDomainOperationRegistry(common)
    definition = _definition()
    implementation = Implementation(definition)
    registry.register(definition, implementation)
    assert implementation.calls == 0
    assert (
        common.resolve(definition.operation_id, definition.version).name
        == definition.operation_id
    )
    assert registry.get(definition.operation_id, definition.version) == definition
    assert (
        registry.get_implementation(definition.operation_id, definition.version)
        is implementation
    )


def test_registry_uses_real_semver_and_deterministic_order() -> None:
    registry = InMemoryDomainOperationRegistry(InMemoryAgentOperationRegistry())
    for version in ("1.9.0", "1.10.0-alpha.1", "1.10.0"):
        definition = _definition(version=version)
        registry.register(definition, Implementation(definition))
    assert registry.resolve_active("project.analyse_architecture").version == "1.10.0"
    assert [item.version for item in registry.list_definitions()] == [
        "1.10.0",
        "1.10.0-alpha.1",
        "1.9.0",
    ]


def test_registry_rejects_duplicates_mismatch_and_bad_signature() -> None:
    registry = InMemoryDomainOperationRegistry(InMemoryAgentOperationRegistry())
    definition = _definition()
    registry.register(definition, Implementation(definition))
    with pytest.raises(DomainOperationRegistryError, match="already registered"):
        registry.register(definition, Implementation(definition))
    with pytest.raises(DomainOperationRegistryError, match="definition"):
        registry.register(
            replace(definition, version="1.1.0"), Implementation(definition)
        )

    class BadImplementation:
        definition = _definition(version="1.2.0")

        def execute(self) -> dict[str, object]:
            return {}

    with pytest.raises(DomainOperationRegistryError, match="signature"):
        registry.register(BadImplementation.definition, BadImplementation())


@pytest.mark.parametrize(
    "implementation_factory",
    [
        lambda definition: type(
            "VarArgsImplementation",
            (),
            {
                "definition": definition,
                "execute": lambda self, request, *args: {},
            },
        )(),
        lambda definition: type(
            "RequiredKeywordOnlyImplementation",
            (),
            {
                "definition": definition,
                "execute": lambda self, request, *, context: {},
            },
        )(),
        lambda definition: type(
            "TwoRequiredPositionalImplementation",
            (),
            {
                "definition": definition,
                "execute": lambda self, request, context: {},
            },
        )(),
    ],
)
def test_registry_rejects_non_optional_execution_parameters(implementation_factory):
    definition = _definition(
        operation_id=f"project.signature_{id(implementation_factory)}"
    )
    with pytest.raises(DomainOperationRegistryError, match="signature"):
        InMemoryDomainOperationRegistry(InMemoryAgentOperationRegistry()).register(
            definition, implementation_factory(definition)
        )


def test_registry_accepts_only_optional_additional_execution_parameters() -> None:
    definition = _definition(operation_id="project.optional_signature")

    class OptionalParameters:
        def __init__(self) -> None:
            self.definition = definition

        def execute(
            self,
            request: AgentOperationRequest,
            context: object | None = None,
            *,
            trace: object | None = None,
        ) -> dict[str, object]:
            return {}

    registry = InMemoryDomainOperationRegistry(InMemoryAgentOperationRegistry())
    registry.register(definition, OptionalParameters())


def test_enable_disable_and_queries_return_definitions_only() -> None:
    registry = InMemoryDomainOperationRegistry(InMemoryAgentOperationRegistry())
    project = _definition()
    health = _definition(
        "health.prepare_clinical_questions",
        operation_type="preparation",
        risk_level="high",
    )
    registry.register(project, Implementation(project))
    registry.register(health, Implementation(health))
    registry.set_enabled(project.operation_id, project.version, False)
    assert registry.get(project.operation_id, project.version).enabled is False
    assert registry.resolve_active(project.operation_id, required=False) is None
    assert registry.list_definitions(domain_id="domain:health") == (health,)
    assert registry.list_definitions(
        operation_type=DomainOperationType.PREPARATION
    ) == (health,)


def test_registry_instances_and_homonymous_short_names_are_isolated() -> None:
    first = InMemoryDomainOperationRegistry(InMemoryAgentOperationRegistry())
    second = InMemoryDomainOperationRegistry(InMemoryAgentOperationRegistry())
    project = _definition("project.prepare_summary")
    health = _definition("health.prepare_summary")
    first.register(project, Implementation(project))
    first.register(health, Implementation(health))
    assert [item.operation_id for item in first.list_definitions()] == [
        "health.prepare_summary",
        "project.prepare_summary",
    ]
    assert second.list_definitions() == ()


def test_registry_can_query_by_resolved_availability() -> None:
    registry = InMemoryDomainOperationRegistry(InMemoryAgentOperationRegistry())
    definition = _definition(reversible=False)
    registry.register(definition, Implementation(definition))
    context = DomainOperationAvailabilityContext(
        primary_domain_id="domain:project", capabilities=("execute",)
    )
    assert registry.list_by_availability(
        DomainOperationStatus.AVAILABLE,
        resolver=DomainOperationAvailabilityResolver(),
        context=context,
    ) == (definition,)
