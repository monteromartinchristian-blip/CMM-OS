"""Phase 11.1 — canonical binding builders.

Every builder in this module accepts an **already-constructed** canonical
subsystem object and returns a :class:`~cmm.platform.contracts.ServiceBinding`
that references it.

No builder constructs a subsystem, clones its state, or wraps a second copy of
an authoritative object.  The canonical Phase 11.34 Provider Registry keeps its
exact identity, and the platform layer never becomes the owner of anything it
binds.

Runtime boundaries
------------------
Descriptor identity alone is not authority.  Every builder therefore also
declares an enforceable ``runtime_contract`` — the canonical concrete class that
owns the service — and rejects any implementation that does not satisfy it.  An
arbitrary object can never claim a canonical service identity, while an
explicitly declared alternate implementation stays possible through
``IntegrationServiceRegistry`` replacement with its own boundary.

The canonical classes are imported **inside** each builder rather than at module
import time.  Importing ``cmm.platform`` therefore stays a thin,
side-effect-free import, and the boundary type of a canonical service is
necessarily already loaded by whoever constructs that service.

Contract versions
-----------------
``ContractMetadata`` describes the **platform boundary**.  Where a canonical
subsystem already publishes the relevant version, that canonical value is
reused (the Provider Registry state schema).  Otherwise the value is an
adapter-level platform boundary version owned by ``cmm.platform`` and recorded
in ``docs/reference/phase-11-integration-core.md``.  It never replaces a version
field that a canonical model already owns.

Dependencies
------------
Only real construction requirements are declared.  ``ResourceExtractionService``
cannot exist without its two canonical registries, so that edge is genuine.  No
other builder declares a dependency, because no other real composition
requirement exists.
"""

from __future__ import annotations

from typing import Any

from cmm.platform.contracts import (
    ContractMetadata,
    ServiceBinding,
    ServiceDependency,
    ServiceDescriptor,
    ServiceMode,
)
from kernel.llm.provider_state import SCHEMA_VERSION as PROVIDER_STATE_SCHEMA_VERSION

#: Platform boundary version for services whose canonical subsystem publishes no
#: equivalent boundary version.  Adapter-level only.
PLATFORM_CONTRACT_VERSION = "1.0.0"
PLATFORM_SCHEMA_VERSION = "1"

PROVIDER_REGISTRY_AUTHORITY = "provider-registry"

#: The canonical provider-registry boundary version.  It is the only canonical
#: binding whose versions differ from the platform defaults, so it is declared
#: once and reused by every dependency edge onto that authority.
PROVIDER_REGISTRY_CONTRACT_VERSION = "2.0.0"


def _boundary_contract(
    contract_name: str,
    owner: str,
    *,
    schema_version: str = PLATFORM_SCHEMA_VERSION,
    contract_version: str = PLATFORM_CONTRACT_VERSION,
) -> ContractMetadata:
    return ContractMetadata(
        contract_name=contract_name,
        contract_version=contract_version,
        schema_version=schema_version,
        owner=owner,
    )


def _implementation_id(implementation: Any) -> str:
    implementation_type = type(implementation)
    return f"{implementation_type.__module__}.{implementation_type.__qualname__}"


def _require_canonical_implementation(
    implementation: Any,
    runtime_contract: type[Any],
    service_id: str,
) -> None:
    """Fail closed unless *implementation* satisfies its canonical boundary."""

    if not isinstance(implementation, runtime_contract):
        raise TypeError(
            f"{service_id} implementation does not satisfy its canonical "
            f"runtime contract {runtime_contract.__module__}."
            f"{runtime_contract.__qualname__}"
        )


def _binding(
    implementation: Any,
    *,
    service_id: str,
    owner: str,
    runtime_contract: type[Any],
    dependencies: tuple[ServiceDependency, ...] = (),
    authority: str | None = None,
    mode: ServiceMode = ServiceMode.LOCAL,
    schema_version: str = PLATFORM_SCHEMA_VERSION,
    contract_version: str = PLATFORM_CONTRACT_VERSION,
) -> ServiceBinding:
    """Bind an existing canonical object without constructing or copying it."""

    _require_canonical_implementation(implementation, runtime_contract, service_id)

    return ServiceBinding(
        descriptor=ServiceDescriptor(
            service_id=service_id,
            contract=_boundary_contract(
                service_id,
                owner,
                schema_version=schema_version,
                contract_version=contract_version,
            ),
            implementation_id=_implementation_id(implementation),
            dependencies=dependencies,
            mode=mode,
            authority=authority,
        ),
        implementation=implementation,
        runtime_contract=runtime_contract,
    )


def _cognitive_registry_dependency(service_id: str) -> ServiceDependency:
    return ServiceDependency(
        service_id=service_id,
        contract=_boundary_contract(service_id, "cmm.cognitive"),
    )


def _provider_registry_dependency() -> ServiceDependency:
    """Describe the exact canonical Phase 11.34 provider-registry boundary.

    Platform compatibility is exact, so a dependency edge onto the provider
    registry must mirror its real versions instead of the platform defaults.
    """

    return ServiceDependency(
        service_id="provider.registry",
        contract=ContractMetadata(
            contract_name="provider.registry",
            contract_version=PROVIDER_REGISTRY_CONTRACT_VERSION,
            schema_version=PROVIDER_STATE_SCHEMA_VERSION,
            owner="kernel.llm",
        ),
    )


def validation_application_binding(service: Any) -> ServiceBinding:
    """Bind the canonical Phase 7 validation application service."""

    from cmm.validation.interfaces.application import ValidationApplicationService

    return _binding(
        service,
        service_id="validation.application",
        owner="cmm.validation",
        runtime_contract=ValidationApplicationService,
    )


def cognitive_adapter_registry_binding(registry: Any) -> ServiceBinding:
    """Bind the canonical Cognitive Layer resource adapter registry."""

    from cmm.cognitive.registries import ResourceAdapterRegistry

    return _binding(
        registry,
        service_id="cognitive.adapter_registry",
        owner="cmm.cognitive",
        runtime_contract=ResourceAdapterRegistry,
    )


def cognitive_extractor_registry_binding(registry: Any) -> ServiceBinding:
    """Bind the canonical Cognitive Layer knowledge extractor registry."""

    from cmm.cognitive.registries import KnowledgeExtractorRegistry

    return _binding(
        registry,
        service_id="cognitive.extractor_registry",
        owner="cmm.cognitive",
        runtime_contract=KnowledgeExtractorRegistry,
    )


def cognitive_service_binding(service: Any) -> ServiceBinding:
    """Bind the canonical Cognitive Layer extraction service.

    ``ResourceExtractionService`` is constructed from its adapter and extractor
    registries, so those platform services are genuine dependencies.
    """

    from cmm.cognitive.service import ResourceExtractionService

    return _binding(
        service,
        service_id="cognitive.service",
        owner="cmm.cognitive",
        runtime_contract=ResourceExtractionService,
        dependencies=(
            _cognitive_registry_dependency("cognitive.adapter_registry"),
            _cognitive_registry_dependency("cognitive.extractor_registry"),
        ),
    )


def agent_runtime_integration_binding(service: Any) -> ServiceBinding:
    """Bind the canonical Phase 9 Agent Runtime integration service.

    The service's required collaborators are Agent Runtime internals owned by
    ``cmm.agent_runtime``; the platform layer does not bind or duplicate them,
    so no platform dependency is declared.
    """

    from cmm.agent_runtime.agent_runtime_integration_service import (
        AgentRuntimeIntegrationService,
    )

    return _binding(
        service,
        service_id="agent.runtime.integration",
        owner="cmm.agent_runtime",
        runtime_contract=AgentRuntimeIntegrationService,
    )


def domain_registry_binding(registry: Any) -> ServiceBinding:
    """Bind the canonical Phase 10 domain registry."""

    from cmm.domains.registry import DomainRegistry

    return _binding(
        registry,
        service_id="domain.registry",
        owner="cmm.domains",
        runtime_contract=DomainRegistry,
    )


def workflow_registry_binding(registry: Any) -> ServiceBinding:
    """Bind the canonical workflow registry."""

    from cmm.workflows.registry import InMemoryWorkflowRegistry

    return _binding(
        registry,
        service_id="workflow.registry",
        owner="cmm.workflows",
        runtime_contract=InMemoryWorkflowRegistry,
    )


def execution_registry_binding(registry: Any) -> ServiceBinding:
    """Bind the canonical action executor registry."""

    from cmm.execution.executor_registry import ExecutorRegistry

    return _binding(
        registry,
        service_id="execution.registry",
        owner="cmm.execution",
        runtime_contract=ExecutorRegistry,
    )


def provider_registry_binding(registry: Any) -> ServiceBinding:
    """Bind the canonical Phase 11.34 Provider Registry.

    The bound object is the authoritative provider registry itself.  Phase 11.1
    creates no second provider registry and stores no parallel provider state.
    """

    from kernel.llm.provider_registry import ProviderRegistry

    return _binding(
        registry,
        service_id="provider.registry",
        owner="kernel.llm",
        runtime_contract=ProviderRegistry,
        authority=PROVIDER_REGISTRY_AUTHORITY,
        schema_version=PROVIDER_STATE_SCHEMA_VERSION,
        contract_version=PROVIDER_REGISTRY_CONTRACT_VERSION,
    )


def model_gateway_binding(gateway: Any) -> ServiceBinding:
    """Bind the canonical Phase 11.21 Model Gateway.

    The bound object is the one canonical gateway instance.  Phase 11.1 creates
    no second gateway and stores no parallel provider or model state; the
    gateway's only composition dependency is the exact canonical Phase 11.34
    provider registry it was constructed with.
    """

    from kernel.llm.model_gateway import ModelGateway

    return _binding(
        gateway,
        service_id="model.gateway",
        owner="kernel.llm",
        runtime_contract=ModelGateway,
        dependencies=(_provider_registry_dependency(),),
    )


__all__ = [
    "PLATFORM_CONTRACT_VERSION",
    "PLATFORM_SCHEMA_VERSION",
    "PROVIDER_REGISTRY_AUTHORITY",
    "PROVIDER_REGISTRY_CONTRACT_VERSION",
    "agent_runtime_integration_binding",
    "cognitive_adapter_registry_binding",
    "cognitive_extractor_registry_binding",
    "cognitive_service_binding",
    "domain_registry_binding",
    "execution_registry_binding",
    "model_gateway_binding",
    "provider_registry_binding",
    "validation_application_binding",
    "workflow_registry_binding",
]
