"""Phase 11.1 – Tests for the application composition container."""

from __future__ import annotations

import json

import pytest

from cmm.platform.configuration import (
    CompositionConfiguration,
    ServiceExpectation,
)
from cmm.platform.container import ApplicationContainer
from cmm.platform.contracts import (
    ContainerState,
    ContractMetadata,
    ErrorResult,
    ServiceBinding,
    ServiceDependency,
    ServiceDescriptor,
    ServiceMode,
)
from cmm.platform.errors import (
    CircularDependencyError,
    ContainerNotReadyError,
    DuplicateAuthorityError,
    DuplicateServiceError,
    FrozenServiceRegistryError,
    IncompatibleContractError,
    InvalidConfigurationError,
    MissingDependencyError,
    PlatformCompositionError,
)
from cmm.platform.modules import StaticCompositionModule
from cmm.platform.service_registry import IntegrationServiceRegistry


def _contract(
    contract_name: str,
    contract_version: str = "1.0.0",
    schema_version: str = "1",
    owner: str = "cmm.platform.test",
) -> ContractMetadata:
    return ContractMetadata(
        contract_name=contract_name,
        contract_version=contract_version,
        schema_version=schema_version,
        owner=owner,
    )


def _binding(
    service_id: str,
    implementation: object,
    *,
    dependencies: tuple[str, ...] = (),
    authority: str | None = None,
    mode: ServiceMode = ServiceMode.LOCAL,
    contract: ContractMetadata | None = None,
) -> ServiceBinding:
    return ServiceBinding(
        descriptor=ServiceDescriptor(
            service_id=service_id,
            contract=contract if contract is not None else _contract(service_id),
            implementation_id=f"impl.{service_id}",
            dependencies=tuple(
                ServiceDependency(service_id=name, contract=_contract(name))
                for name in dependencies
            ),
            mode=mode,
            authority=authority,
        ),
        implementation=implementation,
    )


class BrokenModule:
    """Composition module whose contribution fails."""

    module_id = "broken"

    def contribute(self, configuration: CompositionConfiguration) -> tuple[()]:
        raise RuntimeError("contribution exploded")


class MalformedModule:
    """Composition module returning a malformed contribution."""

    module_id = "malformed"

    def contribute(self, configuration: CompositionConfiguration) -> object:
        return "not-a-tuple"


def _core_module() -> StaticCompositionModule:
    return StaticCompositionModule(
        module_id="core",
        bindings=(
            _binding("domain.registry", object()),
            _binding(
                "validation.application", object(), dependencies=("domain.registry",)
            ),
        ),
    )


def _core_config(
    *,
    required_services: tuple[str, ...] = ("domain.registry", "validation.application"),
    enabled_modules: tuple[str, ...] = ("core",),
    expected_contracts: tuple[ServiceExpectation, ...] = (),
) -> CompositionConfiguration:
    return CompositionConfiguration(
        required_services=required_services,
        enabled_modules=enabled_modules,
        expected_contracts=expected_contracts,
    )


# ── Happy path ───────────────────────────────────────────────────────────────


def test_container_becomes_ready_only_after_complete_graph_validation() -> None:
    container = ApplicationContainer.build(_core_config(), modules=(_core_module(),))

    assert container.state is ContainerState.READY
    assert container.snapshot().state == "ready"


def test_ready_container_exposes_sorted_service_snapshot() -> None:
    container = ApplicationContainer.build(_core_config(), modules=(_core_module(),))

    assert tuple(item.service_id for item in container.snapshot().services) == (
        "domain.registry",
        "validation.application",
    )


def test_container_without_enabled_modules_can_still_be_ready() -> None:
    container = ApplicationContainer.build(
        CompositionConfiguration(enabled_modules=("core",)),
        modules=(_core_module(),),
    )

    assert container.state is ContainerState.READY
    assert container.snapshot().services[0].service_id == "domain.registry"


def test_container_registers_validated_bindings_from_the_registry() -> None:
    container = ApplicationContainer.build(_core_config(), modules=(_core_module(),))

    assert container.snapshot().services[1].dependency_ids == ("domain.registry",)


def test_ready_container_snapshot_is_always_serializable() -> None:
    """READY must always imply a valid, serializable public snapshot."""

    container = ApplicationContainer.build(_core_config(), modules=(_core_module(),))

    assert container.state is ContainerState.READY
    serialized = container.snapshot().to_dict()

    assert serialized["state"] == "ready"
    assert [service["mode"] for service in serialized["services"]] == [
        ServiceMode.LOCAL.value,
        ServiceMode.LOCAL.value,
    ]
    assert json.loads(json.dumps(serialized)) == serialized


def test_container_records_a_deterministic_orderable_composition() -> None:
    container = ApplicationContainer.build(_core_config(), modules=(_core_module(),))
    first = container.snapshot().to_dict()
    second = (
        ApplicationContainer.build(_core_config(), modules=(_core_module(),))
        .snapshot()
        .to_dict()
    )

    assert first == second


# ── Enabled-module selection ─────────────────────────────────────────────────


def test_disabled_modules_do_not_contribute_bindings() -> None:
    extra = StaticCompositionModule(
        module_id="extra", bindings=(_binding("extra.service", object()),)
    )

    container = ApplicationContainer.build(
        _core_config(), modules=(_core_module(), extra)
    )

    assert "extra.service" not in tuple(
        item.service_id for item in container.snapshot().services
    )


def test_container_rejects_unknown_enabled_module() -> None:
    configuration = _core_config(enabled_modules=("core", "missing"))

    with pytest.raises(InvalidConfigurationError) as exc:
        ApplicationContainer.build(configuration, modules=(_core_module(),))

    assert exc.value.result.details["module_id"] == "missing"


def test_container_rejects_duplicate_module_id() -> None:
    modules = (
        _core_module(),
        StaticCompositionModule(module_id="core", bindings=()),
    )

    with pytest.raises(InvalidConfigurationError) as exc:
        ApplicationContainer.build(_core_config(), modules=modules)

    assert exc.value.result.details["module_id"] == "core"


# ── Fail-closed build paths ──────────────────────────────────────────────────


def test_container_rejects_missing_required_service() -> None:
    configuration = _core_config(
        required_services=("domain.registry", "missing.service")
    )

    with pytest.raises(MissingDependencyError) as exc:
        ApplicationContainer.build(configuration, modules=(_core_module(),))

    assert exc.value.result.details["service_id"] == "missing.service"


def test_container_rejects_missing_dependency_of_a_contributed_binding() -> None:
    module = StaticCompositionModule(
        module_id="core",
        bindings=(
            _binding(
                "validation.application", object(), dependencies=("absent.service",)
            ),
        ),
    )
    configuration = _core_config(required_services=("validation.application",))

    with pytest.raises(MissingDependencyError) as exc:
        ApplicationContainer.build(configuration, modules=(module,))

    assert exc.value.result.details["dependency_id"] == "absent.service"


def test_container_rejects_a_circular_dependency() -> None:
    module = StaticCompositionModule(
        module_id="core",
        bindings=(
            _binding("a.service", object(), dependencies=("b.service",)),
            _binding("b.service", object(), dependencies=("a.service",)),
        ),
    )
    configuration = _core_config(required_services=("a.service", "b.service"))

    with pytest.raises(CircularDependencyError) as exc:
        ApplicationContainer.build(configuration, modules=(module,))

    assert exc.value.result.details["cycle"] == "a.service -> b.service -> a.service"


def test_container_rejects_duplicate_authority() -> None:
    module = StaticCompositionModule(
        module_id="core",
        bindings=(
            _binding("a.service", object(), authority="shared"),
            _binding("b.service", object(), authority="shared"),
        ),
    )
    configuration = _core_config(required_services=("a.service", "b.service"))

    with pytest.raises(DuplicateAuthorityError):
        ApplicationContainer.build(configuration, modules=(module,))


def test_container_rejects_duplicate_contributed_service_ids() -> None:
    module = StaticCompositionModule(
        module_id="core",
        bindings=(_binding("a.service", object()), _binding("a.service", object())),
    )
    configuration = _core_config(required_services=("a.service",))

    with pytest.raises(DuplicateServiceError):
        ApplicationContainer.build(configuration, modules=(module,))


def test_container_rejects_module_contribution_failure() -> None:
    configuration = _core_config(required_services=(), enabled_modules=("broken",))

    with pytest.raises(PlatformCompositionError) as exc:
        ApplicationContainer.build(configuration, modules=(BrokenModule(),))

    assert exc.value.result.code == "MODULE_CONTRIBUTION_FAILED"
    assert exc.value.result.details["module_id"] == "broken"


def test_container_rejects_malformed_module_contribution() -> None:
    configuration = _core_config(required_services=(), enabled_modules=("malformed",))

    with pytest.raises(PlatformCompositionError) as exc:
        ApplicationContainer.build(configuration, modules=(MalformedModule(),))

    assert exc.value.result.details["module_id"] == "malformed"


def test_container_rejects_invalid_configuration_type() -> None:
    with pytest.raises(InvalidConfigurationError):
        ApplicationContainer.build(object(), modules=())  # type: ignore[arg-type]


def test_container_rejects_an_already_frozen_registry() -> None:
    registry = IntegrationServiceRegistry()
    registry.freeze()

    with pytest.raises(FrozenServiceRegistryError):
        ApplicationContainer.build(
            _core_config(), modules=(_core_module(),), registry=registry
        )


# ── Expected contract verification ───────────────────────────────────────────


def test_container_accepts_matching_expected_contract() -> None:
    configuration = _core_config(
        expected_contracts=(
            ServiceExpectation(
                service_id="validation.application",
                contract=_contract("validation.application"),
            ),
        )
    )

    container = ApplicationContainer.build(configuration, modules=(_core_module(),))

    assert container.state is ContainerState.READY


def test_container_rejects_mismatched_expected_contract() -> None:
    configuration = _core_config(
        expected_contracts=(
            ServiceExpectation(
                service_id="validation.application",
                contract=_contract("validation.application", contract_version="2.0.0"),
            ),
        )
    )

    with pytest.raises(IncompatibleContractError) as exc:
        ApplicationContainer.build(configuration, modules=(_core_module(),))

    assert exc.value.result.details["reason_code"] == "CONTRACT_VERSION_MISMATCH"
    assert exc.value.result.details["service_id"] == "validation.application"


def test_container_rejects_expected_contract_for_absent_service() -> None:
    configuration = _core_config(
        expected_contracts=(
            ServiceExpectation(
                service_id="absent.service", contract=_contract("absent.service")
            ),
        )
    )

    with pytest.raises(MissingDependencyError) as exc:
        ApplicationContainer.build(configuration, modules=(_core_module(),))

    assert exc.value.result.details["service_id"] == "absent.service"


# ── Failure semantics ────────────────────────────────────────────────────────


def test_failed_build_does_not_freeze_or_partially_ready_the_registry() -> None:
    registry = IntegrationServiceRegistry()
    registry.register(_binding("domain.registry", object()))
    configuration = _core_config(
        required_services=("missing.service",), enabled_modules=()
    )

    with pytest.raises(MissingDependencyError):
        ApplicationContainer.build(configuration, modules=(), registry=registry)

    assert registry.frozen is False


def test_failed_build_returns_no_container_instance() -> None:
    configuration = _core_config(
        required_services=("missing.service",), enabled_modules=()
    )

    result: object = "untouched"
    try:
        result = ApplicationContainer.build(configuration, modules=())
    except PlatformCompositionError:
        pass

    assert not isinstance(result, ApplicationContainer)


def test_failed_container_is_not_ready_and_refuses_service_lookup() -> None:
    container = ApplicationContainer.failed(
        ErrorResult(
            code="MISSING_DEPENDENCY",
            message="Required service is missing",
            category="composition",
            details={"service_id": "missing.service"},
        )
    )

    assert container.state is ContainerState.FAILED
    assert container.failure() is not None
    assert container.failure().code == "MISSING_DEPENDENCY"

    with pytest.raises(ContainerNotReadyError):
        container.snapshot()

    with pytest.raises(ContainerNotReadyError):
        container.get_service("domain.registry")


def test_ready_container_reports_no_failure() -> None:
    container = ApplicationContainer.build(_core_config(), modules=(_core_module(),))

    assert container.failure() is None


# ── Service access as a composition facility ─────────────────────────────────


def test_get_service_returns_the_bound_implementation_identity() -> None:
    implementation = object()
    module = StaticCompositionModule(
        module_id="core", bindings=(_binding("domain.registry", implementation),)
    )
    configuration = _core_config(required_services=("domain.registry",))

    container = ApplicationContainer.build(configuration, modules=(module,))

    assert container.get_service("domain.registry") is implementation


def test_get_service_rejects_an_uncomposed_service() -> None:
    container = ApplicationContainer.build(_core_config(), modules=(_core_module(),))

    with pytest.raises(MissingDependencyError):
        container.get_service("unknown.service")


def test_ready_container_does_not_expose_a_mutable_registry() -> None:
    container = ApplicationContainer.build(_core_config(), modules=(_core_module(),))

    with pytest.raises(AttributeError):
        container.registry = IntegrationServiceRegistry()  # type: ignore[misc]


def test_ready_container_is_immutable() -> None:
    container = ApplicationContainer.build(_core_config(), modules=(_core_module(),))

    with pytest.raises(AttributeError):
        container.state = ContainerState.FAILED  # type: ignore[misc]


# ── Replacement before readiness through the container path ──────────────────


def test_service_can_be_replaced_before_readiness_without_consumer_changes() -> None:
    class ValidationPort:
        pass

    class LocalValidation(ValidationPort):
        pass

    class AdapterValidation(ValidationPort):
        pass

    def wire_consumer(container: ApplicationContainer) -> ValidationPort:
        implementation = container.get_service("validation.application")
        assert isinstance(implementation, ValidationPort)
        return implementation

    registry = IntegrationServiceRegistry()
    registry.register(
        ServiceBinding(
            descriptor=ServiceDescriptor(
                service_id="validation.application",
                contract=_contract("validation.application"),
                implementation_id="impl.validation.application",
                dependencies=(
                    ServiceDependency(
                        service_id="domain.registry",
                        contract=_contract("domain.registry"),
                    ),
                ),
            ),
            implementation=LocalValidation(),
            runtime_contract=ValidationPort,
        )
    )
    registry.register(_binding("domain.registry", object()))
    configuration = _core_config(enabled_modules=())

    container = ApplicationContainer.build(configuration, modules=(), registry=registry)
    assert isinstance(wire_consumer(container), LocalValidation)

    replaceable = IntegrationServiceRegistry()
    replaceable.register(
        ServiceBinding(
            descriptor=ServiceDescriptor(
                service_id="validation.application",
                contract=_contract("validation.application"),
                implementation_id="impl.validation.application",
                dependencies=(
                    ServiceDependency(
                        service_id="domain.registry",
                        contract=_contract("domain.registry"),
                    ),
                ),
            ),
            implementation=LocalValidation(),
            runtime_contract=ValidationPort,
        )
    )
    replaceable.register(_binding("domain.registry", object()))
    replaceable.replace(
        "validation.application",
        ServiceBinding(
            descriptor=ServiceDescriptor(
                service_id="validation.application",
                contract=_contract("validation.application"),
                implementation_id="impl.validation.adapter",
                dependencies=(
                    ServiceDependency(
                        service_id="domain.registry",
                        contract=_contract("domain.registry"),
                    ),
                ),
                mode=ServiceMode.ADAPTER,
            ),
            implementation=AdapterValidation(),
            runtime_contract=ValidationPort,
        ),
    )

    replaced_container = ApplicationContainer.build(
        configuration, modules=(), registry=replaceable
    )

    assert isinstance(wire_consumer(replaced_container), AdapterValidation)
