"""Phase 11.21 — canonical Model Gateway platform composition binding tests.

Phase 11.21 binds the gateway through the existing Phase 11.1 composition root:
one canonical service, the exact canonical ProviderRegistry dependency, no
duplicate provider authority, no circular dependency, secret-free inspection and
readiness that fails when the required dependency is absent or incompatible.
"""

from __future__ import annotations

import json

import pytest

from cmm.platform import model_gateway_binding, provider_registry_binding
from cmm.platform.canonical import PROVIDER_REGISTRY_CONTRACT_VERSION
from cmm.platform.configuration import CompositionConfiguration
from cmm.platform.container import ApplicationContainer, ContainerState
from cmm.platform.contracts import (
    ContractMetadata,
    ServiceBinding,
    ServiceDependency,
    ServiceDescriptor,
    ServiceMode,
)
from cmm.platform.errors import (
    DuplicateServiceError,
    IncompatibleContractError,
    MissingDependencyError,
)
from cmm.platform.inspection import build_composition_snapshot
from cmm.platform.modules import StaticCompositionModule
from cmm.platform.service_registry import IntegrationServiceRegistry
from kernel.llm.model_catalog import ModelCatalog
from kernel.llm.model_gateway import ModelGateway
from kernel.llm.provider_registry import ProviderRegistry
from kernel.llm.provider_state import SCHEMA_VERSION as PROVIDER_STATE_SCHEMA_VERSION


def _gateway() -> tuple[ModelGateway, ProviderRegistry]:
    registry = ProviderRegistry()
    catalog = ModelCatalog(registry)
    return ModelGateway(provider_registry=registry, model_catalog=catalog), registry


def _container(
    bindings: tuple[ServiceBinding, ...],
    *,
    required: tuple[str, ...] = ("model.gateway", "provider.registry"),
) -> ApplicationContainer:
    module = StaticCompositionModule("canonical", bindings)
    return ApplicationContainer.build(
        CompositionConfiguration(
            required_services=required,
            enabled_modules=("canonical",),
        ),
        modules=(module,),
    )


# ── Binding identity ────────────────────────────────────────────────────────


def test_binding_binds_the_exact_gateway_instance() -> None:
    gateway, _ = _gateway()

    binding = model_gateway_binding(gateway)

    assert isinstance(binding, ServiceBinding)
    assert binding.implementation is gateway
    assert binding.runtime_contract is ModelGateway
    assert isinstance(binding.implementation, binding.runtime_contract)


def test_binding_declares_the_canonical_service_identity() -> None:
    gateway, _ = _gateway()

    descriptor = model_gateway_binding(gateway).descriptor

    assert descriptor.service_id == "model.gateway"
    assert descriptor.implementation_id == "kernel.llm.model_gateway.ModelGateway"
    assert descriptor.mode is ServiceMode.LOCAL
    assert descriptor.authority is None
    assert descriptor.contract.owner == "kernel.llm"
    assert descriptor.contract.contract_name == "model.gateway"


def test_binding_depends_on_the_exact_canonical_provider_registry_contract() -> None:
    gateway, _ = _gateway()

    descriptor = model_gateway_binding(gateway).descriptor

    assert tuple(dep.service_id for dep in descriptor.dependencies) == (
        "provider.registry",
    )
    assert descriptor.dependencies[0].contract == (
        provider_registry_binding(ProviderRegistry()).descriptor.contract
    )
    assert (
        descriptor.dependencies[0].contract.contract_version
        == PROVIDER_REGISTRY_CONTRACT_VERSION
    )
    assert (
        descriptor.dependencies[0].contract.schema_version
        == PROVIDER_STATE_SCHEMA_VERSION
    )


def test_binding_rejects_a_foreign_implementation() -> None:
    with pytest.raises(TypeError):
        model_gateway_binding(object())
    with pytest.raises(TypeError):
        model_gateway_binding(ModelCatalog(ProviderRegistry()))


# ── Composed container ──────────────────────────────────────────────────────


def test_composed_container_is_ready_and_reuses_the_exact_canonical_registry() -> None:
    gateway, registry = _gateway()

    container = _container(
        (provider_registry_binding(registry), model_gateway_binding(gateway))
    )

    assert container.state is ContainerState.READY
    bound_gateway = container.get_service("model.gateway")
    assert bound_gateway is gateway
    assert container.get_service("provider.registry") is registry
    assert bound_gateway.provider_registry is registry
    assert bound_gateway.model_catalog.provider_registry is registry


def test_dependency_order_places_the_provider_registry_first() -> None:
    gateway, registry = _gateway()
    module = StaticCompositionModule(
        "canonical",
        (provider_registry_binding(registry), model_gateway_binding(gateway)),
    )
    service_registry = IntegrationServiceRegistry()
    service_registry.register(provider_registry_binding(registry))
    service_registry.register(model_gateway_binding(gateway))
    service_registry.validate_graph()

    order = service_registry.dependency_order()
    assert order.index("provider.registry") < order.index("model.gateway")
    assert module.module_id == "canonical"


def test_a_missing_provider_registry_dependency_fails_readiness() -> None:
    gateway, _ = _gateway()

    with pytest.raises(MissingDependencyError) as error:
        _container((model_gateway_binding(gateway),), required=("model.gateway",))

    assert error.value.result.details["dependency_id"] == "provider.registry"
    assert error.value.result.details["service_id"] == "model.gateway"


def test_a_wrong_provider_registry_contract_fails_with_a_schema_mismatch() -> None:
    gateway, registry = _gateway()
    stale_dependency = ServiceBinding(
        descriptor=ServiceDescriptor(
            service_id="model.gateway",
            contract=ContractMetadata(
                contract_name="model.gateway",
                contract_version="1.0.0",
                schema_version="1",
                owner="kernel.llm",
            ),
            implementation_id="kernel.llm.model_gateway.ModelGateway",
            dependencies=(
                ServiceDependency(
                    service_id="provider.registry",
                    contract=ContractMetadata(
                        contract_name="provider.registry",
                        contract_version="2.0.0",
                        schema_version="1",
                        owner="kernel.llm",
                    ),
                ),
            ),
        ),
        implementation=gateway,
        runtime_contract=ModelGateway,
    )

    with pytest.raises(IncompatibleContractError) as error:
        _container((provider_registry_binding(registry), stale_dependency))

    assert error.value.result.details["reason_code"] == "SCHEMA_VERSION_MISMATCH"


def test_no_second_gateway_service_can_be_composed() -> None:
    first, registry = _gateway()
    second, _ = _gateway()

    with pytest.raises(DuplicateServiceError):
        _container(
            (
                provider_registry_binding(registry),
                model_gateway_binding(first),
                model_gateway_binding(second),
            )
        )


def test_the_gateway_claims_no_existing_authority() -> None:
    gateway, registry = _gateway()
    service_registry = IntegrationServiceRegistry()
    service_registry.register(provider_registry_binding(registry))
    service_registry.register(model_gateway_binding(gateway))

    authorities = [
        binding.descriptor.authority
        for binding in service_registry.list_bindings()
        if binding.descriptor.authority is not None
    ]
    assert authorities == ["provider-registry"]


# ── Inspection ──────────────────────────────────────────────────────────────


def test_snapshot_inspection_names_the_gateway_without_leaking_secrets() -> None:
    gateway, registry = _gateway()
    container = _container(
        (provider_registry_binding(registry), model_gateway_binding(gateway))
    )
    service_registry = IntegrationServiceRegistry()
    service_registry.register(provider_registry_binding(registry))
    service_registry.register(model_gateway_binding(gateway))

    snapshot = build_composition_snapshot(container.state, service_registry)
    payload = snapshot.to_dict()
    serialized = json.dumps(payload)

    assert "model.gateway" in serialized
    assert "kernel.llm.model_gateway.ModelGateway" in serialized
    assert [entry["service_id"] for entry in payload["services"]] == sorted(
        entry["service_id"] for entry in payload["services"]
    )
    lowered = serialized.lower()
    for forbidden in ("secret", "credential", "password", "api_key", "prompt"):
        assert forbidden not in lowered
