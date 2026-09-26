"""Phase 11.1 — connected acceptance test ``AT-DP-101``.

Requirement: ``F11-015`` — Canonical Integration Core
Design Point: ``DP-101`` — Canonical Application Composition Root

This is a **connected** acceptance test, not a mock-only unit test.  It
instantiates the real :class:`~cmm.platform.container.ApplicationContainer` and
the real :class:`~cmm.platform.service_registry.IntegrationServiceRegistry`
around real canonical CMM OS subsystem objects, including the closed Phase 11.34
Provider Registry.

The composition root receives already-constructed canonical objects.  It never
builds them, clones them, or takes ownership of their state.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pytest

from cmm.agent_runtime.action_budget_service import ActionBudgetService
from cmm.agent_runtime.agent_factory import AgentFactoryRegistry
from cmm.agent_runtime.agent_registry import AgentRegistry
from cmm.agent_runtime.agent_registry_service import AgentRegistryService
from cmm.agent_runtime.agent_runtime_integration_service import (
    AgentRuntimeIntegrationService,
)
from cmm.agent_runtime.agent_runtime_integration_store import (
    InMemoryAgentRuntimeIntegrationStore,
)
from cmm.agent_runtime.agent_security_service import AgentSecurityService
from cmm.agent_runtime.goal_manager import GoalManager
from cmm.agent_runtime.operation_execution_adapter import AgentExecutionAdapter
from cmm.agent_runtime.runtime_loop import AgentRuntimeLoop
from cmm.cognitive.registries import (
    KnowledgeExtractorRegistry,
    ResourceAdapterRegistry,
)
from cmm.cognitive.service import ResourceExtractionService
from cmm.domains.contracts import DomainDefinition
from cmm.domains.enums import DomainKind
from cmm.domains.registry import DomainRegistry
from cmm.execution.executor_registry import create_default_executor_registry
from cmm.platform.canonical import (
    agent_runtime_integration_binding,
    cognitive_adapter_registry_binding,
    cognitive_extractor_registry_binding,
    cognitive_service_binding,
    domain_registry_binding,
    execution_registry_binding,
    provider_registry_binding,
    validation_application_binding,
    workflow_registry_binding,
)
from cmm.platform.configuration import (
    CompositionConfiguration,
    ServiceExpectation,
)
from cmm.platform.container import ApplicationContainer
from cmm.platform.contracts import (
    ContainerState,
    ContractMetadata,
    ServiceBinding,
    ServiceDependency,
    ServiceDescriptor,
    ServiceMode,
)
from cmm.platform.errors import (
    CircularDependencyError,
    DuplicateAuthorityError,
    FrozenServiceRegistryError,
    IncompatibleContractError,
    InvalidReplacementError,
    MissingDependencyError,
)
from cmm.platform.inspection import ServiceInspection
from cmm.platform.modules import StaticCompositionModule
from cmm.platform.service_registry import IntegrationServiceRegistry
from cmm.validation.interfaces.application import ValidationApplicationService
from cmm.workflows.contracts import WorkflowDefinition, WorkflowNode
from cmm.workflows.registry import InMemoryWorkflowRegistry
from kernel.llm.first_wave_providers import (
    register_first_wave_providers,
    register_subscription_bridge_providers,
)
from kernel.llm.provider_manifests import ProviderManifestRegistry
from kernel.llm.provider_registry import ProviderRegistry

CANONICAL_MODULE_ID = "canonical"

#: The representative canonical platform services, in canonical (sorted) order.
REQUIRED_SERVICE_IDS = (
    "agent.runtime.integration",
    "cognitive.adapter_registry",
    "cognitive.extractor_registry",
    "cognitive.service",
    "domain.registry",
    "execution.registry",
    "provider.registry",
    "validation.application",
    "workflow.registry",
)

FORBIDDEN_INSPECTION_KEYS = (
    "secret",
    "credential",
    "token",
    "password",
    "prompt",
    "reasoning",
    "payload",
)


def _snapshot_keys(value: object) -> set[str]:
    """Collect every key reachable in a serialized inspection snapshot."""

    if isinstance(value, dict):
        keys = set(value)
        for item in value.values():
            keys |= _snapshot_keys(item)
        return keys
    if isinstance(value, list):
        found: set[str] = set()
        for item in value:
            found |= _snapshot_keys(item)
        return found
    return set()


# ── Representative canonical object graph ────────────────────────────────────


@dataclass(frozen=True, slots=True)
class CanonicalComponents:
    """The already-constructed canonical subsystem objects under composition."""

    provider_registry: ProviderRegistry
    provider_manifests: ProviderManifestRegistry
    domain_registry: DomainRegistry
    validation_application: ValidationApplicationService
    cognitive_adapter_registry: ResourceAdapterRegistry
    cognitive_extractor_registry: KnowledgeExtractorRegistry
    cognitive_service: ResourceExtractionService
    agent_runtime_integration: AgentRuntimeIntegrationService
    workflow_registry: InMemoryWorkflowRegistry
    execution_registry: object


def _real_agent_runtime_integration() -> AgentRuntimeIntegrationService:
    """Build the real Agent Runtime integration service, canonically wired."""

    goal_manager = GoalManager()
    return AgentRuntimeIntegrationService(
        store=InMemoryAgentRuntimeIntegrationStore(),
        goal_manager=goal_manager,
        registry_service=AgentRegistryService(
            registry=AgentRegistry(), factory_registry=AgentFactoryRegistry()
        ),
        runtime_loop=AgentRuntimeLoop(goal_repository=goal_manager.repository),
        security_service=AgentSecurityService(),
        budget_service=ActionBudgetService(),
        execution_adapter=AgentExecutionAdapter(
            execution_delegate=lambda operation: {
                "ok": True,
                "operation": operation.operation_name,
            }
        ),
    )


def _real_domain_registry_with_content() -> DomainRegistry:
    """Build a real domain registry holding one real domain definition."""

    registry = DomainRegistry()
    registry.register(
        DomainDefinition(
            id="domain:test",
            name="test",
            display_name="Test domain",
            version="1.0.0",
            kind=DomainKind.CORE,
            description="Phase 11.1 acceptance domain",
            manifest_id="manifest:test:1.0.0",
        )
    )
    return registry


def _real_workflow_registry_with_content() -> InMemoryWorkflowRegistry:
    registry = InMemoryWorkflowRegistry()
    registry.register(
        WorkflowDefinition(
            "acceptance",
            "1.0.0",
            "Acceptance",
            nodes=(WorkflowNode("n", "complete", "N"),),
        )
    )
    return registry


def build_canonical_test_components(tmp_path: Path) -> CanonicalComponents:
    """Create the real canonical subsystem objects.

    Provider identities come from their canonical Phase 11.34 declarations, so
    the acceptance graph carries no fabricated provider or manifest state.
    """

    provider_registry = ProviderRegistry()
    provider_manifests = ProviderManifestRegistry(provider_registry)
    register_first_wave_providers(provider_registry, provider_manifests)
    register_subscription_bridge_providers(provider_registry, provider_manifests)

    cognitive_adapter_registry = ResourceAdapterRegistry()
    cognitive_extractor_registry = KnowledgeExtractorRegistry()

    return CanonicalComponents(
        provider_registry=provider_registry,
        provider_manifests=provider_manifests,
        domain_registry=_real_domain_registry_with_content(),
        validation_application=ValidationApplicationService(project_root=tmp_path),
        cognitive_adapter_registry=cognitive_adapter_registry,
        cognitive_extractor_registry=cognitive_extractor_registry,
        cognitive_service=ResourceExtractionService(
            cognitive_adapter_registry, cognitive_extractor_registry
        ),
        agent_runtime_integration=_real_agent_runtime_integration(),
        workflow_registry=_real_workflow_registry_with_content(),
        execution_registry=create_default_executor_registry(),
    )


def canonical_bindings(components: CanonicalComponents) -> tuple[ServiceBinding, ...]:
    """Bind every canonical object by reference through the platform layer."""

    return (
        validation_application_binding(components.validation_application),
        cognitive_adapter_registry_binding(components.cognitive_adapter_registry),
        cognitive_extractor_registry_binding(components.cognitive_extractor_registry),
        cognitive_service_binding(components.cognitive_service),
        agent_runtime_integration_binding(components.agent_runtime_integration),
        domain_registry_binding(components.domain_registry),
        workflow_registry_binding(components.workflow_registry),
        execution_registry_binding(components.execution_registry),
        provider_registry_binding(components.provider_registry),
    )


def canonical_configuration() -> CompositionConfiguration:
    return CompositionConfiguration(
        required_services=REQUIRED_SERVICE_IDS,
        enabled_modules=(CANONICAL_MODULE_ID,),
        expected_contracts=(
            ServiceExpectation(
                service_id="provider.registry",
                contract=provider_registry_binding(
                    ProviderRegistry()
                ).descriptor.contract,
            ),
        ),
    )


def build_phase11_1_test_container(
    components: CanonicalComponents,
    *,
    registry: IntegrationServiceRegistry | None = None,
) -> ApplicationContainer:
    """Compose the representative canonical graph into a ready container.

    Two equivalent composition paths exist, and both are exercised:

    * contribution path — an enabled module contributes the canonical bindings;
    * registry path — the caller supplies a registry that already holds the
      composition, which is what makes explicit replacement before readiness
      observable.

    A registry that already holds the bindings is composed with no contributing
    module, because re-registering a binding fails closed by design.
    """

    if registry is not None:
        ready_configuration = CompositionConfiguration(
            required_services=REQUIRED_SERVICE_IDS,
            enabled_modules=(),
            expected_contracts=canonical_configuration().expected_contracts,
        )
        return ApplicationContainer.build(
            ready_configuration, modules=(), registry=registry
        )

    module = StaticCompositionModule(
        module_id=CANONICAL_MODULE_ID, bindings=canonical_bindings(components)
    )
    return ApplicationContainer.build(canonical_configuration(), modules=(module,))


# ── Happy path ───────────────────────────────────────────────────────────────


def test_at_dp_101_connected_canonical_application_composition(
    tmp_path: Path,
) -> None:
    canonical = build_canonical_test_components(tmp_path)
    container = build_phase11_1_test_container(canonical)

    assert container.state is ContainerState.READY
    assert container.get_service("provider.registry") is canonical.provider_registry
    assert container.get_service("domain.registry") is canonical.domain_registry
    assert (
        container.get_service("agent.runtime.integration")
        is canonical.agent_runtime_integration
    )

    snapshot = container.snapshot()
    assert tuple(service.service_id for service in snapshot.services) == tuple(
        sorted(service.service_id for service in snapshot.services)
    )


def test_at_dp_101_reaches_ready_with_every_required_service(tmp_path: Path) -> None:
    canonical = build_canonical_test_components(tmp_path)

    container = build_phase11_1_test_container(canonical)

    assert container.state is ContainerState.READY
    assert container.snapshot().state == "ready"
    assert tuple(service.service_id for service in container.snapshot().services) == (
        REQUIRED_SERVICE_IDS
    )


def test_at_dp_101_preserves_canonical_object_identity(tmp_path: Path) -> None:
    canonical = build_canonical_test_components(tmp_path)

    container = build_phase11_1_test_container(canonical)

    assert container.get_service("validation.application") is (
        canonical.validation_application
    )
    assert container.get_service("cognitive.service") is canonical.cognitive_service
    assert container.get_service("cognitive.adapter_registry") is (
        canonical.cognitive_adapter_registry
    )
    assert container.get_service("cognitive.extractor_registry") is (
        canonical.cognitive_extractor_registry
    )
    assert container.get_service("domain.registry") is canonical.domain_registry
    assert container.get_service("workflow.registry") is canonical.workflow_registry
    assert container.get_service("execution.registry") is canonical.execution_registry
    assert container.get_service("provider.registry") is canonical.provider_registry


def test_at_dp_101_provider_binding_is_the_exact_canonical_registry(
    tmp_path: Path,
) -> None:
    canonical = build_canonical_test_components(tmp_path)

    container = build_phase11_1_test_container(canonical)

    bound = container.get_service("provider.registry")
    assert bound is canonical.provider_registry
    assert type(bound) is ProviderRegistry

    descriptor = next(
        service
        for service in container.snapshot().services
        if service.service_id == "provider.registry"
    )
    assert descriptor.authority == "provider-registry"
    assert descriptor.owner == "kernel.llm"


def test_at_dp_101_composition_does_not_mutate_canonical_registries(
    tmp_path: Path,
) -> None:
    canonical = build_canonical_test_components(tmp_path)
    providers_before = canonical.provider_registry.list()
    domains_before = canonical.domain_registry.list()
    workflows_before = canonical.workflow_registry.list_definitions()
    executors_before = canonical.execution_registry.all()

    build_phase11_1_test_container(canonical)

    assert canonical.provider_registry.list() == providers_before
    assert canonical.domain_registry.list() == domains_before
    assert canonical.workflow_registry.list_definitions() == workflows_before
    assert canonical.execution_registry.all() == executors_before


def test_at_dp_101_provider_authority_holds_real_canonical_provider_state(
    tmp_path: Path,
) -> None:
    """The bound provider authority is the live Phase 11.34 registry."""

    canonical = build_canonical_test_components(tmp_path)
    build_phase11_1_test_container(canonical)

    assert len(canonical.provider_registry.list()) > 0
    assert "deepseek" in {spec.id for spec in canonical.provider_registry.list()}


def test_at_dp_101_deterministic_inspection_snapshot(tmp_path: Path) -> None:
    canonical = build_canonical_test_components(tmp_path)

    first = build_phase11_1_test_container(canonical).snapshot().to_dict()
    second = build_phase11_1_test_container(canonical).snapshot().to_dict()

    assert first == second
    payload = json.dumps(first, sort_keys=True)
    assert "provider.registry" in payload
    assert "kernel.llm.provider_registry.ProviderRegistry" in payload


def test_at_dp_101_ready_snapshot_is_always_serializable(tmp_path: Path) -> None:
    """READY must always imply a valid, serializable public snapshot."""

    canonical = build_canonical_test_components(tmp_path)

    container = build_phase11_1_test_container(canonical)

    assert container.state is ContainerState.READY
    serialized = container.snapshot().to_dict()

    assert serialized["state"] == "ready"
    assert tuple(item["service_id"] for item in serialized["services"]) == (
        REQUIRED_SERVICE_IDS
    )
    assert json.loads(json.dumps(serialized)) == serialized
    assert all(item["mode"] in {"local", "adapter"} for item in serialized["services"])


def test_at_dp_101_dependency_order_is_deterministic(tmp_path: Path) -> None:
    canonical = build_canonical_test_components(tmp_path)
    registry = IntegrationServiceRegistry()
    module = StaticCompositionModule(
        module_id=CANONICAL_MODULE_ID, bindings=canonical_bindings(canonical)
    )
    for binding in module.contribute(canonical_configuration()):
        registry.register(binding)

    order = registry.dependency_order()

    assert isinstance(order, tuple)
    assert set(order) == set(REQUIRED_SERVICE_IDS)
    assert order.index("cognitive.adapter_registry") < order.index("cognitive.service")
    assert order.index("cognitive.extractor_registry") < order.index(
        "cognitive.service"
    )


# ── Failure path: fails closed before READY ──────────────────────────────────


def test_at_dp_101_missing_dependency_fails_before_ready(tmp_path: Path) -> None:
    canonical = build_canonical_test_components(tmp_path)
    bindings = tuple(
        binding
        for binding in canonical_bindings(canonical)
        if binding.descriptor.service_id != "cognitive.adapter_registry"
    )
    module = StaticCompositionModule(module_id=CANONICAL_MODULE_ID, bindings=bindings)

    with pytest.raises(MissingDependencyError) as exc:
        ApplicationContainer.build(canonical_configuration(), modules=(module,))

    assert exc.value.result.details["service_id"] in {
        "cognitive.adapter_registry",
        "cognitive.service",
    }


def test_at_dp_101_incompatible_schema_fails_before_ready(tmp_path: Path) -> None:
    canonical = build_canonical_test_components(tmp_path)
    configuration = CompositionConfiguration(
        required_services=REQUIRED_SERVICE_IDS,
        enabled_modules=(CANONICAL_MODULE_ID,),
        expected_contracts=(
            ServiceExpectation(
                service_id="provider.registry",
                contract=provider_registry_binding(
                    ProviderRegistry()
                ).descriptor.contract.__class__(
                    contract_name="provider.registry",
                    contract_version="2.0.0",
                    schema_version="999",
                    owner="kernel.llm",
                ),
            ),
        ),
    )
    module = StaticCompositionModule(
        module_id=CANONICAL_MODULE_ID, bindings=canonical_bindings(canonical)
    )

    with pytest.raises(IncompatibleContractError) as exc:
        ApplicationContainer.build(configuration, modules=(module,))

    assert exc.value.result.details["reason_code"] == "SCHEMA_VERSION_MISMATCH"


def test_at_dp_101_incompatible_contract_version_fails_before_ready(
    tmp_path: Path,
) -> None:
    canonical = build_canonical_test_components(tmp_path)
    expected = provider_registry_binding(ProviderRegistry()).descriptor.contract
    configuration = CompositionConfiguration(
        required_services=REQUIRED_SERVICE_IDS,
        enabled_modules=(CANONICAL_MODULE_ID,),
        expected_contracts=(
            ServiceExpectation(
                service_id="provider.registry",
                contract=type(expected)(
                    contract_name=expected.contract_name,
                    contract_version="99.0.0",
                    schema_version=expected.schema_version,
                    owner=expected.owner,
                ),
            ),
        ),
    )
    module = StaticCompositionModule(
        module_id=CANONICAL_MODULE_ID, bindings=canonical_bindings(canonical)
    )

    with pytest.raises(IncompatibleContractError) as exc:
        ApplicationContainer.build(configuration, modules=(module,))

    assert exc.value.result.details["reason_code"] == "CONTRACT_VERSION_MISMATCH"


def test_at_dp_101_circular_dependency_fails_before_ready(tmp_path: Path) -> None:
    canonical = build_canonical_test_components(tmp_path)
    original = cognitive_service_binding(canonical.cognitive_service).descriptor
    agent_original = agent_runtime_integration_binding(
        canonical.agent_runtime_integration
    ).descriptor

    # cognitive.service now also depends on agent.runtime.integration, and
    # agent.runtime.integration depends back on cognitive.service.
    cyclic = ServiceBinding(
        descriptor=ServiceDescriptor(
            service_id="cognitive.service",
            contract=original.contract,
            implementation_id=original.implementation_id,
            dependencies=(
                original.dependencies[0],
                original.dependencies[1],
                ServiceDependency(
                    service_id="agent.runtime.integration",
                    contract=agent_original.contract,
                ),
            ),
            mode=original.mode,
        ),
        implementation=canonical.cognitive_service,
    )
    agent_cyclic = ServiceBinding(
        descriptor=ServiceDescriptor(
            service_id="agent.runtime.integration",
            contract=agent_original.contract,
            implementation_id=agent_original.implementation_id,
            dependencies=(
                ServiceDependency(
                    service_id="cognitive.service", contract=original.contract
                ),
            ),
        ),
        implementation=canonical.agent_runtime_integration,
    )

    bindings = tuple(
        binding
        for binding in canonical_bindings(canonical)
        if binding.descriptor.service_id
        not in {"cognitive.service", "agent.runtime.integration"}
    ) + (cyclic, agent_cyclic)
    module = StaticCompositionModule(module_id=CANONICAL_MODULE_ID, bindings=bindings)

    with pytest.raises(CircularDependencyError) as exc:
        ApplicationContainer.build(canonical_configuration(), modules=(module,))

    assert "->" in exc.value.result.details["cycle"]


def test_at_dp_101_duplicate_authority_fails_before_ready(tmp_path: Path) -> None:
    canonical = build_canonical_test_components(tmp_path)
    imposter_module = StaticCompositionModule(
        module_id=CANONICAL_MODULE_ID,
        bindings=canonical_bindings(canonical)
        + (
            ServiceBinding(
                descriptor=ServiceDescriptor(
                    service_id="rogue.provider.authority",
                    contract=provider_registry_binding(
                        ProviderRegistry()
                    ).descriptor.contract,
                    implementation_id="tests.platform.RogueProviderAuthority",
                    authority="provider-registry",
                ),
                implementation=canonical.provider_manifests,
            ),
        ),
    )
    configuration = CompositionConfiguration(
        required_services=REQUIRED_SERVICE_IDS + ("rogue.provider.authority",),
        enabled_modules=(CANONICAL_MODULE_ID,),
    )

    with pytest.raises(DuplicateAuthorityError) as exc:
        ApplicationContainer.build(configuration, modules=(imposter_module,))

    assert exc.value.result.details["authority"] == "provider-registry"


# ── Replacement path ─────────────────────────────────────────────────────────


class ValidationPort:
    """Stable consumer-facing boundary for the validation service."""


class LocalValidationService(ValidationPort):
    """Local in-process implementation."""


class AdapterValidationService(ValidationPort):
    """Compatible adapter-backed implementation; no transport is involved."""


class ValidationConsumer:
    """Unchanged consumer: it only knows the stable service boundary."""

    def __init__(self, validation: object) -> None:
        self.validation = validation


def _wire_validation_consumer(
    registry: IntegrationServiceRegistry,
) -> ValidationConsumer:
    binding = registry.get("validation.application")
    assert binding is not None
    return ValidationConsumer(binding.implementation)


def _prepared_registry(
    components: CanonicalComponents, validation: LocalValidationService
) -> IntegrationServiceRegistry:
    registry = IntegrationServiceRegistry()
    original = validation_application_binding(components.validation_application)
    for binding in canonical_bindings(components):
        if binding.descriptor.service_id == "validation.application":
            registry.register(
                ServiceBinding(
                    descriptor=original.descriptor,
                    implementation=validation,
                )
            )
        else:
            registry.register(binding)
    return registry


def _adapter_binding(
    registry: IntegrationServiceRegistry, adapter: AdapterValidationService
) -> ServiceBinding:
    original = registry.get("validation.application")
    assert original is not None
    return ServiceBinding(
        descriptor=ServiceDescriptor(
            service_id="validation.application",
            contract=original.descriptor.contract,
            implementation_id="tests.platform.acceptance.AdapterValidationService",
            dependencies=original.descriptor.dependencies,
            mode=ServiceMode.ADAPTER,
            authority=original.descriptor.authority,
        ),
        implementation=adapter,
    )


def test_at_dp_101_invalid_replacement_fails(tmp_path: Path) -> None:
    canonical = build_canonical_test_components(tmp_path)
    registry = _prepared_registry(canonical, LocalValidationService())

    with pytest.raises(InvalidReplacementError):
        registry.replace(
            "validation.application",
            provider_registry_binding(canonical.provider_registry),
        )

    with pytest.raises(InvalidReplacementError):
        registry.replace(
            "unknown.service", _adapter_binding(registry, AdapterValidationService())
        )


def test_at_dp_101_replacement_with_incompatible_contract_fails(
    tmp_path: Path,
) -> None:
    canonical = build_canonical_test_components(tmp_path)
    registry = _prepared_registry(canonical, LocalValidationService())
    original = registry.get("validation.application")
    assert original is not None

    with pytest.raises(IncompatibleContractError):
        registry.replace(
            "validation.application",
            ServiceBinding(
                descriptor=ServiceDescriptor(
                    service_id="validation.application",
                    contract=type(original.descriptor.contract)(
                        contract_name="validation.application",
                        contract_version="9.9.9",
                        schema_version=original.descriptor.contract.schema_version,
                        owner=original.descriptor.contract.owner,
                    ),
                    implementation_id="tests.platform.Incompatible",
                ),
                implementation=AdapterValidationService(),
            ),
        )


def test_at_dp_101_compatible_adapter_replacement_before_readiness(
    tmp_path: Path,
) -> None:
    """A test adapter replaces a service with no change to consumer code."""

    canonical = build_canonical_test_components(tmp_path)
    registry = _prepared_registry(canonical, LocalValidationService())

    before = _wire_validation_consumer(registry)
    assert isinstance(before.validation, LocalValidationService)

    registry.replace(
        "validation.application", _adapter_binding(registry, AdapterValidationService())
    )

    after = _wire_validation_consumer(registry)
    assert isinstance(after.validation, AdapterValidationService)
    assert type(before) is type(after)

    container = build_phase11_1_test_container(canonical, registry=registry)

    assert container.state is ContainerState.READY
    assert isinstance(
        container.get_service("validation.application"), AdapterValidationService
    )


def test_at_dp_101_replacement_after_readiness_fails(tmp_path: Path) -> None:
    canonical = build_canonical_test_components(tmp_path)
    registry = _prepared_registry(canonical, LocalValidationService())

    container = build_phase11_1_test_container(canonical, registry=registry)
    assert container.state is ContainerState.READY

    with pytest.raises(FrozenServiceRegistryError):
        registry.replace(
            "validation.application",
            _adapter_binding(registry, AdapterValidationService()),
        )


def test_at_dp_101_adapter_mode_satisfies_the_same_contract(tmp_path: Path) -> None:
    """Adapter-backed and local bindings expose the same service contract."""

    canonical = build_canonical_test_components(tmp_path)
    registry = _prepared_registry(canonical, LocalValidationService())
    local_contract = registry.get("validation.application").descriptor.contract

    registry.replace(
        "validation.application", _adapter_binding(registry, AdapterValidationService())
    )

    replacement = registry.get("validation.application")
    assert replacement is not None
    assert replacement.descriptor.mode is ServiceMode.ADAPTER
    assert replacement.descriptor.contract == local_contract
    assert replacement.descriptor.service_id == "validation.application"


# ── Safety path: inspection reveals no internals ─────────────────────────────


def test_at_dp_101_inspection_contains_no_raw_implementation(tmp_path: Path) -> None:
    canonical = build_canonical_test_components(tmp_path)

    container = build_phase11_1_test_container(canonical)
    payload = json.dumps(container.snapshot().to_dict())

    assert repr(canonical.provider_registry) not in payload
    assert repr(canonical.domain_registry) not in payload
    assert repr(canonical.validation_application) not in payload
    for service in container.snapshot().services:
        assert not hasattr(service, "implementation")
        assert not hasattr(service, "metadata")


def test_at_dp_101_inspection_does_not_leak_arbitrary_descriptor_metadata(
    tmp_path: Path,
) -> None:
    """Descriptor metadata never reaches the public composition boundary."""

    marker = "SENSITIVE-PROVIDER-PAYLOAD-MARKER"
    canonical = build_canonical_test_components(tmp_path)
    carrier = ServiceDescriptor(
        service_id="diagnostic.carrier",
        contract=provider_registry_binding(ProviderRegistry()).descriptor.contract,
        implementation_id="tests.platform.DiagnosticCarrier",
        metadata={"display": {"label": marker}},
    )
    module = StaticCompositionModule(
        module_id=CANONICAL_MODULE_ID,
        bindings=canonical_bindings(canonical)
        + (
            ServiceBinding(
                descriptor=carrier, implementation=canonical.provider_manifests
            ),
        ),
    )
    configuration = CompositionConfiguration(
        required_services=REQUIRED_SERVICE_IDS + ("diagnostic.carrier",),
        enabled_modules=(CANONICAL_MODULE_ID,),
    )

    container = ApplicationContainer.build(configuration, modules=(module,))
    payload = json.dumps(container.snapshot().to_dict())

    assert container.state is ContainerState.READY
    assert marker not in payload
    assert "display" not in payload
    assert "metadata" not in _snapshot_keys(container.snapshot().to_dict())


def test_at_dp_101_inspection_exposes_no_forbidden_keys(tmp_path: Path) -> None:
    canonical = build_canonical_test_components(tmp_path)

    payload = build_phase11_1_test_container(canonical).snapshot().to_dict()

    keys = _snapshot_keys(payload)

    assert not any(
        token in key.lower() for key in keys for token in FORBIDDEN_INSPECTION_KEYS
    )


# ── Audit V1 remediation coverage ────────────────────────────────────────────


def test_at_dp_101_rejects_fake_provider_registry_authority() -> None:
    """Audit V1 MAJOR-01: an unrelated object cannot claim provider authority."""

    with pytest.raises(TypeError):
        provider_registry_binding(object())

    with pytest.raises(TypeError):
        provider_registry_binding(ProviderManifestRegistry(ProviderRegistry()))


def test_at_dp_101_provider_authority_keeps_canonical_object_and_boundary(
    tmp_path: Path,
) -> None:
    """The canonical Provider Registry is bound with its own runtime boundary."""

    canonical = build_canonical_test_components(tmp_path)

    binding = provider_registry_binding(canonical.provider_registry)

    assert binding.implementation is canonical.provider_registry
    assert binding.runtime_contract is ProviderRegistry
    assert isinstance(binding.implementation, binding.runtime_contract)

    container = build_phase11_1_test_container(canonical)

    assert container.get_service("provider.registry") is canonical.provider_registry


def test_at_dp_101_every_canonical_binding_enforces_a_runtime_boundary(
    tmp_path: Path,
) -> None:
    """Each canonical service is bound with an enforceable implementation boundary."""

    canonical = build_canonical_test_components(tmp_path)
    bindings = canonical_bindings(canonical)

    assert (
        tuple(sorted(binding.descriptor.service_id for binding in bindings))
        == REQUIRED_SERVICE_IDS
    )

    for binding in bindings:
        service_id = binding.descriptor.service_id
        assert binding.runtime_contract is not None, (
            f"{service_id} is bound without an enforceable runtime boundary"
        )
        assert isinstance(binding.implementation, binding.runtime_contract), (
            f"{service_id} implementation violates its canonical runtime boundary"
        )

    container = build_phase11_1_test_container(canonical)

    for binding in bindings:
        assert container.get_service(binding.descriptor.service_id) is (
            binding.implementation
        )


def test_at_dp_101_forged_provider_binding_cannot_reach_ready(
    tmp_path: Path,
) -> None:
    """A forged canonical binding is rejected before readiness by its boundary."""

    canonical = build_canonical_test_components(tmp_path)
    legitimate = provider_registry_binding(canonical.provider_registry)
    forged = ServiceBinding(
        descriptor=legitimate.descriptor,
        implementation=object(),
        runtime_contract=legitimate.runtime_contract,
    )
    module = StaticCompositionModule(
        module_id=CANONICAL_MODULE_ID,
        bindings=tuple(
            binding
            for binding in canonical_bindings(canonical)
            if binding.descriptor.service_id != "provider.registry"
        )
        + (forged,),
    )

    with pytest.raises(IncompatibleContractError) as exc:
        ApplicationContainer.build(canonical_configuration(), modules=(module,))

    assert exc.value.result.details["reason_code"] == "RUNTIME_CONTRACT_MISMATCH"
    assert exc.value.result.details["service_id"] == "provider.registry"


def test_at_dp_101_unsafe_descriptor_metadata_cannot_enter_the_composition(
    tmp_path: Path,
) -> None:
    """Audit V1 MAJOR-02: secret-shaped metadata cannot exist on a descriptor."""

    canonical = build_canonical_test_components(tmp_path)
    original = validation_application_binding(canonical.validation_application)

    for unsafe in (
        {"token": "sk-secret"},
        {"nested": {"password": "p"}},
        {"display": {"authorization": "Bearer secret"}},
        {"provider_payload": {"x": 1}},
        {"prompt": "internal"},
    ):
        with pytest.raises(ValueError):
            ServiceDescriptor(
                service_id="validation.application",
                contract=original.descriptor.contract,
                implementation_id=original.descriptor.implementation_id,
                metadata=unsafe,
            )

    with pytest.raises(TypeError):
        ServiceDescriptor(
            service_id="validation.application",
            contract=original.descriptor.contract,
            implementation_id=original.descriptor.implementation_id,
            metadata={"client": object()},
        )


def test_at_dp_101_descriptor_metadata_is_detached_and_immutable(
    tmp_path: Path,
) -> None:
    """Permitted metadata is copied and recursively frozen for the real graph."""

    canonical = build_canonical_test_components(tmp_path)
    original = validation_application_binding(canonical.validation_application)
    source = {"display": {"labels": ["one", "two"], "enabled": True}}

    descriptor = ServiceDescriptor(
        service_id="validation.application",
        contract=original.descriptor.contract,
        implementation_id=original.descriptor.implementation_id,
        metadata=source,
    )

    source["display"]["labels"].append("three")
    source["display"]["enabled"] = False

    assert descriptor.metadata["display"]["labels"] == ("one", "two")
    assert descriptor.metadata["display"]["enabled"] is True

    with pytest.raises(TypeError):
        descriptor.metadata["display"]["enabled"] = False  # type: ignore[index]


def test_at_dp_101_malformed_mode_cannot_reach_ready(tmp_path: Path) -> None:
    """Audit V1 MAJOR-03: a malformed mode must fail before any container is ready."""

    canonical = build_canonical_test_components(tmp_path)
    original = validation_application_binding(canonical.validation_application)

    with pytest.raises(TypeError):
        ServiceDescriptor(
            service_id="validation.application",
            contract=original.descriptor.contract,
            implementation_id=original.descriptor.implementation_id,
            mode="bogus",  # type: ignore[arg-type]
        )

    with pytest.raises(TypeError):
        ServiceInspection(
            service_id="validation.application",
            implementation_id=original.descriptor.implementation_id,
            contract_name=original.descriptor.contract.contract_name,
            contract_version=original.descriptor.contract.contract_version,
            schema_version=original.descriptor.contract.schema_version,
            owner=original.descriptor.contract.owner,
            dependency_ids=(),
            mode="bogus",  # type: ignore[arg-type]
            authority=None,
        )

    container = build_phase11_1_test_container(canonical)

    assert container.state is ContainerState.READY
    container.snapshot().to_dict()


# ── No second provider authority ─────────────────────────────────────────────


def test_at_dp_101_no_second_provider_registry_is_created(tmp_path: Path) -> None:
    """Platform code must not construct or hold a competing provider registry."""

    canonical = build_canonical_test_components(tmp_path)
    container = build_phase11_1_test_container(canonical)

    provider_services = [
        service
        for service in container.snapshot().services
        if service.authority == "provider-registry"
    ]

    assert len(provider_services) == 1
    assert provider_services[0].service_id == "provider.registry"
    assert container.get_service("provider.registry") is canonical.provider_registry


def test_at_dp_101_provider_registry_regresses_cleanly(tmp_path: Path) -> None:
    """Composition leaves Phase 11.34 provider identity semantics untouched."""

    canonical = build_canonical_test_components(tmp_path)
    before = tuple(spec.id for spec in canonical.provider_registry.list())

    build_phase11_1_test_container(canonical)

    assert tuple(spec.id for spec in canonical.provider_registry.list()) == before
    # Canonical phase-11.34 normalisation still applies to the same object.
    assert canonical.provider_registry.has(before[0])


# ── Remediation V3: legacy expectations keep Phase 11.1 semantics ────────────
#
# Remediation V3 for Phase 11.50 MAJOR_V3_01 extended the shared
# ``ServiceExpectation`` value with optional authoritative runtime identity.
# AT-DP-101 therefore also proves the extension is strictly additive: a legacy
# expectation with no runtime policy still constrains the descriptor contract
# only, and ordinary Phase 11.1 subtype-compatible bindings keep working
# unchanged.


def test_at_dp_101_legacy_service_expectation_still_works(tmp_path: Path) -> None:
    """``LEGACY_SERVICE_EXPECTATION_CONSTRUCTION=PRESERVED``."""

    canonical = build_canonical_test_components(tmp_path)
    expected = provider_registry_binding(
        canonical.provider_registry
    ).descriptor.contract
    expectation = ServiceExpectation(
        service_id="provider.registry",
        contract=expected,
    )

    assert expectation.runtime_contract is None
    assert expectation.runtime_contract_match is None

    configuration = CompositionConfiguration(
        required_services=REQUIRED_SERVICE_IDS,
        enabled_modules=(CANONICAL_MODULE_ID,),
        expected_contracts=(expectation,),
    )
    module = StaticCompositionModule(
        module_id=CANONICAL_MODULE_ID, bindings=canonical_bindings(canonical)
    )

    container = ApplicationContainer.build(configuration, modules=(module,))

    assert container.state is ContainerState.READY
    assert container.get_service("provider.registry") is canonical.provider_registry


def test_at_dp_101_ordinary_subtype_binding_survives_a_legacy_expectation() -> None:
    """``INHERITED_INSTANCE_OF_SEMANTICS=PRESERVED``.

    A legacy expectation adds no exact-type policy, so an ordinary
    subtype-compatible binding registered under it keeps the inherited Phase 11.1
    ``isinstance`` semantics.
    """

    class Port:
        """Test-local runtime contract boundary."""

    class OrdinarySubtype(Port):
        """A normal subtype-compatible implementation."""

    service_id = "subtype.service"
    contract = ContractMetadata(
        contract_name=service_id,
        contract_version="1.0.0",
        schema_version="1",
        owner="cmm.platform.test",
    )
    expectation = ServiceExpectation(service_id=service_id, contract=contract)
    registry = IntegrationServiceRegistry(expected_contracts=(expectation,))

    implementation = OrdinarySubtype()
    binding = ServiceBinding(
        descriptor=ServiceDescriptor(
            service_id=service_id,
            contract=contract,
            implementation_id="test.ordinary.subtype",
        ),
        implementation=implementation,
        runtime_contract=Port,
    )

    registry.register(binding)

    stored = registry.get(service_id)
    assert stored is binding
    assert stored is not None
    assert stored.implementation is implementation
    assert type(stored.implementation) is not Port
