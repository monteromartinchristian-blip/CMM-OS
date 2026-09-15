"""Phase 11.1 — canonical binding builders.

Every builder in this module accepts an **already-constructed** canonical
subsystem object and returns a :class:`~cmm.platform.contracts.ServiceBinding`
that references it.

No builder constructs a subsystem, clones its state, or wraps a second copy of
an authoritative object.  The canonical Phase 11.34 Provider Registry keeps its
exact identity, and the platform layer never becomes the owner of anything it
binds.

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


def _binding(
    implementation: Any,
    *,
    service_id: str,
    owner: str,
    dependencies: tuple[ServiceDependency, ...] = (),
    authority: str | None = None,
    mode: ServiceMode = ServiceMode.LOCAL,
    schema_version: str = PLATFORM_SCHEMA_VERSION,
    contract_version: str = PLATFORM_CONTRACT_VERSION,
) -> ServiceBinding:
    """Bind an existing canonical object without constructing or copying it."""

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
    )


def _cognitive_registry_dependency(service_id: str) -> ServiceDependency:
    return ServiceDependency(
        service_id=service_id,
        contract=_boundary_contract(service_id, "cmm.cognitive"),
    )


def validation_application_binding(service: Any) -> ServiceBinding:
    """Bind the canonical Phase 7 validation application service."""

    return _binding(
        service, service_id="validation.application", owner="cmm.validation"
    )


def cognitive_adapter_registry_binding(registry: Any) -> ServiceBinding:
    """Bind the canonical Cognitive Layer resource adapter registry."""

    return _binding(
        registry, service_id="cognitive.adapter_registry", owner="cmm.cognitive"
    )


def cognitive_extractor_registry_binding(registry: Any) -> ServiceBinding:
    """Bind the canonical Cognitive Layer knowledge extractor registry."""

    return _binding(
        registry, service_id="cognitive.extractor_registry", owner="cmm.cognitive"
    )


def cognitive_service_binding(service: Any) -> ServiceBinding:
    """Bind the canonical Cognitive Layer extraction service.

    ``ResourceExtractionService`` is constructed from its adapter and extractor
    registries, so those platform services are genuine dependencies.
    """

    return _binding(
        service,
        service_id="cognitive.service",
        owner="cmm.cognitive",
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

    return _binding(
        service, service_id="agent.runtime.integration", owner="cmm.agent_runtime"
    )


def domain_registry_binding(registry: Any) -> ServiceBinding:
    """Bind the canonical Phase 10 domain registry."""

    return _binding(registry, service_id="domain.registry", owner="cmm.domains")


def workflow_registry_binding(registry: Any) -> ServiceBinding:
    """Bind the canonical workflow registry."""

    return _binding(registry, service_id="workflow.registry", owner="cmm.workflows")


def execution_registry_binding(registry: Any) -> ServiceBinding:
    """Bind the canonical action executor registry."""

    return _binding(registry, service_id="execution.registry", owner="cmm.execution")


def provider_registry_binding(registry: Any) -> ServiceBinding:
    """Bind the canonical Phase 11.34 Provider Registry.

    The bound object is the authoritative provider registry itself.  Phase 11.1
    creates no second provider registry and stores no parallel provider state.
    """

    return _binding(
        registry,
        service_id="provider.registry",
        owner="kernel.llm",
        authority=PROVIDER_REGISTRY_AUTHORITY,
        schema_version=PROVIDER_STATE_SCHEMA_VERSION,
        contract_version="2.0.0",
    )


__all__ = [
    "PLATFORM_CONTRACT_VERSION",
    "PLATFORM_SCHEMA_VERSION",
    "PROVIDER_REGISTRY_AUTHORITY",
    "agent_runtime_integration_binding",
    "cognitive_adapter_registry_binding",
    "cognitive_extractor_registry_binding",
    "cognitive_service_binding",
    "domain_registry_binding",
    "execution_registry_binding",
    "provider_registry_binding",
    "validation_application_binding",
    "workflow_registry_binding",
]
