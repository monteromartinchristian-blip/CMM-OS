"""Phase 11.1 – Tests for the integration service registry.

This module also owns the structured composition error tests: the typed
platform exceptions are produced by registry and container operations, so their
safe-diagnostics contract is asserted next to the operations that raise them.
"""

from __future__ import annotations

import pytest

from cmm.platform.contracts import (
    ContractMetadata,
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
    InvalidReplacementError,
    MissingDependencyError,
    PlatformCompositionError,
)
from cmm.platform.service_registry import IntegrationServiceRegistry

TYPED_ERRORS = (
    DuplicateServiceError,
    MissingDependencyError,
    IncompatibleContractError,
    CircularDependencyError,
    DuplicateAuthorityError,
    InvalidReplacementError,
    InvalidConfigurationError,
    ContainerNotReadyError,
    FrozenServiceRegistryError,
)


# ── Structured platform composition errors ───────────────────────────────────


def test_platform_composition_error_exposes_safe_error_result() -> None:
    error = PlatformCompositionError(
        code="MISSING_DEPENDENCY",
        message="Required service is missing",
        category="composition",
        details={"service_id": "agent.runtime"},
    )

    assert error.result.code == "MISSING_DEPENDENCY"
    assert error.result.details == {"service_id": "agent.runtime"}
    assert "traceback" not in error.result.details


def test_platform_composition_error_details_are_immutable() -> None:
    source = {"service_id": "agent.runtime"}
    error = PlatformCompositionError(
        code="MISSING_DEPENDENCY",
        message="Required service is missing",
        category="composition",
        details=source,
    )

    source["injected"] = "later"

    assert dict(error.result.details) == {"service_id": "agent.runtime"}

    with pytest.raises(TypeError):
        error.result.details["injected"] = "later"  # type: ignore[index]


def test_platform_composition_error_rejects_non_string_details() -> None:
    with pytest.raises(TypeError):
        PlatformCompositionError(
            code="MISSING_DEPENDENCY",
            message="Required service is missing",
            category="composition",
            details={"service": object()},  # type: ignore[dict-item]
        )


def test_platform_composition_error_does_not_serialize_runtime_objects() -> None:
    """No arbitrary exception object may reach the public error result."""

    inner = RuntimeError("secret internal detail")
    error = PlatformCompositionError(
        code="COMPOSITION_FAILED",
        message="Composition failed",
        category="composition",
    )

    assert error.result.details == {}
    assert inner not in error.args
    assert error.__cause__ is None
    assert "secret internal detail" not in str(error)


def test_platform_composition_error_message_is_safe() -> None:
    error = PlatformCompositionError(
        code="MISSING_DEPENDENCY",
        message="Required service is missing",
        category="composition",
    )

    assert str(error) == "Required service is missing"
    assert "Traceback" not in str(error)


@pytest.mark.parametrize("error_type", TYPED_ERRORS)
def test_every_typed_error_carries_a_structured_result(
    error_type: type[PlatformCompositionError],
) -> None:
    error = error_type("deterministic diagnostic")

    assert isinstance(error, PlatformCompositionError)
    assert isinstance(error, Exception)
    assert error.result.code
    assert error.result.category
    assert error.result.message == "deterministic diagnostic"
    assert dict(error.result.details) == {}


def test_typed_errors_use_distinct_stable_codes() -> None:
    codes = {error_type.default_code for error_type in TYPED_ERRORS}

    assert len(codes) == len(TYPED_ERRORS)
    assert all(code.isupper() for code in codes)


def test_typed_errors_expose_stable_categories() -> None:
    assert DuplicateServiceError.default_category == "composition"
    assert CircularDependencyError.default_category == "composition"
    assert InvalidConfigurationError.default_category == "configuration"
    assert ContainerNotReadyError.default_category == "lifecycle"
    assert FrozenServiceRegistryError.default_category == "lifecycle"


def test_typed_error_accepts_safe_structured_details() -> None:
    error = MissingDependencyError(
        "Required service is missing",
        details={
            "service_id": "agent.runtime",
            "dependency_id": "validation.application",
        },
    )

    assert error.result.code == "MISSING_DEPENDENCY"
    assert error.result.details["service_id"] == "agent.runtime"
    assert error.result.details["dependency_id"] == "validation.application"


# ── Registration ─────────────────────────────────────────────────────────────


class ValidationPort:
    """Test-local runtime contract boundary."""


class ValidationService(ValidationPort):
    """Compatible implementation of ``ValidationPort``."""


class UnrelatedService:
    """Implementation that does not satisfy ``ValidationPort``."""


class CountingValidationService(ValidationPort):
    """Implementation carrying observable internal state."""

    def __init__(self) -> None:
        self.calls = 0


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
    runtime_contract: type | None = None,
    contract: ContractMetadata | None = None,
    implementation_id: str = "test.implementation",
    dependency_contracts: tuple[ServiceDependency, ...] | None = None,
) -> ServiceBinding:
    if dependency_contracts is None:
        dependency_contracts = tuple(
            ServiceDependency(service_id=name, contract=_contract(name))
            for name in dependencies
        )

    return ServiceBinding(
        descriptor=ServiceDescriptor(
            service_id=service_id,
            contract=contract if contract is not None else _contract(service_id),
            implementation_id=implementation_id,
            dependencies=dependency_contracts,
            mode=mode,
            authority=authority,
        ),
        implementation=implementation,
        runtime_contract=runtime_contract,
    )


def test_registry_registers_and_lists_bindings_deterministically() -> None:
    registry = IntegrationServiceRegistry()

    registry.register(_binding("z.service", ValidationService()))
    registry.register(_binding("a.service", ValidationService()))

    assert [binding.descriptor.service_id for binding in registry.list_bindings()] == [
        "a.service",
        "z.service",
    ]


def test_registry_is_not_a_global_singleton() -> None:
    first = IntegrationServiceRegistry()
    second = IntegrationServiceRegistry()

    first.register(_binding("a.service", ValidationService()))

    assert first is not second
    assert second.list_bindings() == ()
    assert second.get("a.service") is None


def test_registry_preserves_implementation_object_identity() -> None:
    registry = IntegrationServiceRegistry()
    implementation = ValidationService()

    registry.register(_binding("a.service", implementation))

    stored = registry.get("a.service")
    assert stored is not None
    assert stored.implementation is implementation


def test_registry_lookup_miss_returns_none() -> None:
    registry = IntegrationServiceRegistry()

    assert registry.get("unknown.service") is None


def test_registry_rejects_duplicate_service_id() -> None:
    registry = IntegrationServiceRegistry()
    registry.register(_binding("a.service", ValidationService()))

    with pytest.raises(DuplicateServiceError) as exc:
        registry.register(_binding("a.service", ValidationService()))

    assert exc.value.result.code == "DUPLICATE_SERVICE_ID"
    assert exc.value.result.details["service_id"] == "a.service"


def test_registry_rejects_non_binding_registration() -> None:
    registry = IntegrationServiceRegistry()

    with pytest.raises(TypeError):
        registry.register(object())  # type: ignore[arg-type]


def test_registry_rejects_implementation_violating_runtime_contract() -> None:
    registry = IntegrationServiceRegistry()

    with pytest.raises(IncompatibleContractError) as exc:
        registry.register(
            _binding("a.service", UnrelatedService(), runtime_contract=ValidationPort)
        )

    assert exc.value.result.details["reason_code"] == "RUNTIME_CONTRACT_MISMATCH"


def test_registry_revalidates_a_canonical_runtime_contract() -> None:
    """Defense in depth: a canonical boundary is re-checked at registration."""

    from cmm.platform.canonical import provider_registry_binding
    from kernel.llm.provider_registry import ProviderRegistry

    canonical = provider_registry_binding(ProviderRegistry())
    forged = ServiceBinding(
        descriptor=canonical.descriptor,
        implementation=object(),
        runtime_contract=canonical.runtime_contract,
    )

    with pytest.raises(IncompatibleContractError) as exc:
        IntegrationServiceRegistry().register(forged)

    assert exc.value.result.details["reason_code"] == "RUNTIME_CONTRACT_MISMATCH"
    assert exc.value.result.details["service_id"] == "provider.registry"


def test_registry_accepts_implementation_satisfying_runtime_contract() -> None:
    registry = IntegrationServiceRegistry()
    implementation = ValidationService()

    registry.register(
        _binding("a.service", implementation, runtime_contract=ValidationPort)
    )

    stored = registry.get("a.service")
    assert stored is not None
    assert stored.implementation is implementation


def test_registry_skips_runtime_contract_check_when_not_safely_checkable() -> None:
    registry = IntegrationServiceRegistry()

    registry.register(
        _binding(
            "a.service",
            ValidationService(),
            runtime_contract="not-a-type",  # type: ignore[arg-type]
        )
    )

    assert registry.get("a.service") is not None


def test_both_local_and_adapter_modes_satisfy_the_same_contract() -> None:
    """A stable contract accepts a local and an adapter-backed binding."""

    registry = IntegrationServiceRegistry()
    registry.register(
        _binding("a.service", ValidationService(), mode=ServiceMode.LOCAL)
    )
    registry.register(
        _binding("b.service", ValidationService(), mode=ServiceMode.ADAPTER)
    )

    modes = {
        binding.descriptor.service_id: binding.descriptor.mode
        for binding in registry.list_bindings()
    }
    assert modes == {"a.service": ServiceMode.LOCAL, "b.service": ServiceMode.ADAPTER}


# ── Freeze ───────────────────────────────────────────────────────────────────


def test_registry_is_not_frozen_by_default() -> None:
    assert IntegrationServiceRegistry().frozen is False


def test_registry_freeze_is_idempotent() -> None:
    registry = IntegrationServiceRegistry()

    registry.freeze()
    registry.freeze()

    assert registry.frozen is True


def test_registry_rejects_registration_after_freeze() -> None:
    registry = IntegrationServiceRegistry()
    registry.register(_binding("a.service", ValidationService()))
    registry.freeze()

    with pytest.raises(FrozenServiceRegistryError) as exc:
        registry.register(_binding("b.service", ValidationService()))

    assert exc.value.result.code == "SERVICE_REGISTRY_FROZEN"
    assert exc.value.result.details["service_id"] == "b.service"


def test_registry_rejects_replacement_after_freeze() -> None:
    registry = IntegrationServiceRegistry()
    registry.register(_binding("a.service", ValidationService()))
    registry.freeze()

    with pytest.raises(FrozenServiceRegistryError):
        registry.replace("a.service", _binding("a.service", ValidationService()))


# ── Explicit replacement ─────────────────────────────────────────────────────


def test_replacement_before_freeze_succeeds_for_compatible_contract() -> None:
    registry = IntegrationServiceRegistry()
    original = ValidationService()
    replacement = CountingValidationService()
    registry.register(_binding("a.service", original))

    returned = registry.replace("a.service", _binding("a.service", replacement))

    stored = registry.get("a.service")
    assert stored is not None
    assert stored.implementation is replacement
    assert returned.implementation is replacement
    assert len(registry.list_bindings()) == 1


def test_replacement_requires_an_existing_target() -> None:
    registry = IntegrationServiceRegistry()

    with pytest.raises(InvalidReplacementError):
        registry.replace(
            "missing.service", _binding("missing.service", ValidationService())
        )


def test_replacement_rejects_a_different_service_id() -> None:
    registry = IntegrationServiceRegistry()
    registry.register(_binding("a.service", ValidationService()))

    with pytest.raises(InvalidReplacementError) as exc:
        registry.replace("a.service", _binding("other.service", ValidationService()))

    assert exc.value.result.details["service_id"] == "a.service"
    assert exc.value.result.details["replacement_service_id"] == "other.service"


def test_replacement_rejects_incompatible_contract() -> None:
    registry = IntegrationServiceRegistry()
    registry.register(_binding("a.service", ValidationService()))

    with pytest.raises(IncompatibleContractError) as exc:
        registry.replace(
            "a.service",
            _binding(
                "a.service",
                ValidationService(),
                contract=_contract("a.service", contract_version="2.0.0"),
            ),
        )

    assert exc.value.result.details["reason_code"] == "CONTRACT_VERSION_MISMATCH"


def test_replacement_rejects_schema_version_mismatch() -> None:
    registry = IntegrationServiceRegistry()
    registry.register(_binding("a.service", ValidationService()))

    with pytest.raises(IncompatibleContractError) as exc:
        registry.replace(
            "a.service",
            _binding(
                "a.service",
                ValidationService(),
                contract=_contract("a.service", schema_version="2"),
            ),
        )

    assert exc.value.result.details["reason_code"] == "SCHEMA_VERSION_MISMATCH"


def test_replacement_rejects_runtime_contract_violation() -> None:
    registry = IntegrationServiceRegistry()
    registry.register(
        _binding("a.service", ValidationService(), runtime_contract=ValidationPort)
    )

    with pytest.raises(IncompatibleContractError) as exc:
        registry.replace(
            "a.service",
            _binding("a.service", UnrelatedService(), runtime_contract=ValidationPort),
        )

    assert exc.value.result.details["reason_code"] == "RUNTIME_CONTRACT_MISMATCH"


def test_replacement_leaves_original_implementation_untouched() -> None:
    """Replacing a binding must not mutate the replaced object's state."""

    registry = IntegrationServiceRegistry()
    original = CountingValidationService()
    registry.register(_binding("a.service", original))

    replacement = CountingValidationService()
    registry.replace("a.service", _binding("a.service", replacement))

    assert original.calls == 0
    assert replacement.calls == 0
    assert original is not replacement


def test_replacement_preserves_binding_identity_of_other_services() -> None:
    registry = IntegrationServiceRegistry()
    untouched = ValidationService()
    registry.register(_binding("a.service", ValidationService()))
    registry.register(_binding("b.service", untouched))

    registry.replace("a.service", _binding("a.service", ValidationService()))

    stored = registry.get("b.service")
    assert stored is not None
    assert stored.implementation is untouched


# ── Dependency graph validation ──────────────────────────────────────────────


class ExplodingImplementation:
    """Fails the test if graph validation touches a bound implementation."""

    def __getattr__(self, name: str) -> object:
        raise AssertionError(f"graph validation touched implementation.{name}")


def test_graph_validation_accepts_a_coherent_graph() -> None:
    registry = IntegrationServiceRegistry()
    registry.register(
        _binding("a.service", ValidationService(), dependencies=("b.service",))
    )
    registry.register(_binding("b.service", ValidationService()))

    registry.validate_graph()


def test_graph_validation_rejects_missing_dependency() -> None:
    registry = IntegrationServiceRegistry()
    registry.register(
        _binding("a.service", ValidationService(), dependencies=("missing.service",))
    )

    with pytest.raises(MissingDependencyError) as exc:
        registry.validate_graph()

    assert exc.value.result.details["service_id"] == "a.service"
    assert exc.value.result.details["dependency_id"] == "missing.service"


def test_graph_validation_rejects_dependency_contract_mismatch() -> None:
    registry = IntegrationServiceRegistry()
    registry.register(_binding("b.service", ValidationService()))
    registry.register(
        _binding(
            "a.service",
            ValidationService(),
            dependency_contracts=(
                ServiceDependency(
                    service_id="b.service",
                    contract=_contract("b.service", contract_version="2.0.0"),
                ),
            ),
        )
    )

    with pytest.raises(IncompatibleContractError) as exc:
        registry.validate_graph()

    assert exc.value.result.details["reason_code"] == "CONTRACT_VERSION_MISMATCH"
    assert exc.value.result.details["dependency_id"] == "b.service"


def test_graph_validation_rejects_dependency_schema_mismatch() -> None:
    registry = IntegrationServiceRegistry()
    registry.register(_binding("b.service", ValidationService()))
    registry.register(
        _binding(
            "a.service",
            ValidationService(),
            dependency_contracts=(
                ServiceDependency(
                    service_id="b.service",
                    contract=_contract("b.service", schema_version="2"),
                ),
            ),
        )
    )

    with pytest.raises(IncompatibleContractError) as exc:
        registry.validate_graph()

    assert exc.value.result.details["reason_code"] == "SCHEMA_VERSION_MISMATCH"


def test_graph_validation_rejects_dependency_owner_mismatch() -> None:
    registry = IntegrationServiceRegistry()
    registry.register(_binding("b.service", ValidationService()))
    registry.register(
        _binding(
            "a.service",
            ValidationService(),
            dependency_contracts=(
                ServiceDependency(
                    service_id="b.service",
                    contract=_contract("b.service", owner="cmm.other"),
                ),
            ),
        )
    )

    with pytest.raises(IncompatibleContractError) as exc:
        registry.validate_graph()

    assert exc.value.result.details["reason_code"] == "OWNER_MISMATCH"


def test_registry_rejects_two_node_dependency_cycle_before_readiness() -> None:
    registry = IntegrationServiceRegistry()
    registry.register(_binding("a", object(), dependencies=("b",)))
    registry.register(_binding("b", object(), dependencies=("a",)))

    with pytest.raises(CircularDependencyError) as exc:
        registry.validate_graph()

    assert exc.value.result.details["cycle"] == "a -> b -> a"


def test_registry_rejects_longer_dependency_cycle() -> None:
    registry = IntegrationServiceRegistry()
    registry.register(_binding("a", object(), dependencies=("b",)))
    registry.register(_binding("b", object(), dependencies=("c",)))
    registry.register(_binding("c", object(), dependencies=("a",)))

    with pytest.raises(CircularDependencyError) as exc:
        registry.validate_graph()

    assert exc.value.result.details["cycle"] == "a -> b -> c -> a"


def test_graph_validation_rejects_duplicate_authority() -> None:
    registry = IntegrationServiceRegistry()
    registry.register(_binding("a.service", ValidationService(), authority="shared"))
    registry.register(_binding("b.service", ValidationService(), authority="shared"))

    with pytest.raises(DuplicateAuthorityError) as exc:
        registry.validate_graph()

    assert exc.value.result.details["authority"] == "shared"
    assert exc.value.result.details["service_id"] == "a.service"
    assert exc.value.result.details["conflicting_service_id"] == "b.service"


def test_graph_validation_allows_repeated_none_authority() -> None:
    registry = IntegrationServiceRegistry()
    registry.register(_binding("a.service", ValidationService()))
    registry.register(_binding("b.service", ValidationService()))

    registry.validate_graph()


def test_graph_validation_allows_distinct_authorities() -> None:
    registry = IntegrationServiceRegistry()
    registry.register(_binding("a.service", ValidationService(), authority="one"))
    registry.register(_binding("b.service", ValidationService(), authority="two"))

    registry.validate_graph()


def test_graph_validation_does_not_execute_bound_services() -> None:
    registry = IntegrationServiceRegistry()
    registry.register(
        _binding(
            "a.service",
            ExplodingImplementation(),
            dependencies=("b.service",),
            authority="one",
        )
    )
    registry.register(_binding("b.service", ExplodingImplementation(), authority="two"))

    registry.validate_graph()


# ── Deterministic dependency order ───────────────────────────────────────────


def test_dependency_order_places_dependencies_before_dependents() -> None:
    registry = IntegrationServiceRegistry()
    registry.register(
        _binding("a.service", ValidationService(), dependencies=("b.service",))
    )
    registry.register(
        _binding("b.service", ValidationService(), dependencies=("c.service",))
    )
    registry.register(_binding("c.service", ValidationService()))

    assert registry.dependency_order() == ("c.service", "b.service", "a.service")


def test_dependency_order_breaks_ties_lexically() -> None:
    registry = IntegrationServiceRegistry()
    registry.register(_binding("z.service", ValidationService()))
    registry.register(_binding("a.service", ValidationService()))
    registry.register(_binding("m.service", ValidationService()))

    assert registry.dependency_order() == (
        "a.service",
        "m.service",
        "z.service",
    )


def test_dependency_order_is_deterministic_across_registration_orders() -> None:
    def build(order: tuple[str, ...]) -> IntegrationServiceRegistry:
        registry = IntegrationServiceRegistry()
        spec = {
            "a.service": ("b.service",),
            "b.service": ("c.service",),
            "c.service": (),
            "d.service": (),
        }
        for service_id in order:
            registry.register(
                _binding(service_id, ValidationService(), dependencies=spec[service_id])
            )
        return registry

    forward = build(("a.service", "b.service", "c.service", "d.service"))
    backward = build(("d.service", "c.service", "b.service", "a.service"))

    assert forward.dependency_order() == backward.dependency_order()
    assert forward.dependency_order() == (
        "c.service",
        "b.service",
        "a.service",
        "d.service",
    )


def test_dependency_order_returns_an_immutable_tuple() -> None:
    registry = IntegrationServiceRegistry()
    registry.register(_binding("a.service", ValidationService()))

    order = registry.dependency_order()

    assert isinstance(order, tuple)
    assert order == ("a.service",)


def test_dependency_order_rejects_a_cyclic_graph() -> None:
    registry = IntegrationServiceRegistry()
    registry.register(_binding("a", object(), dependencies=("b",)))
    registry.register(_binding("b", object(), dependencies=("a",)))

    with pytest.raises(CircularDependencyError):
        registry.dependency_order()


def test_dependency_order_does_not_execute_bound_services() -> None:
    registry = IntegrationServiceRegistry()
    registry.register(
        _binding("a.service", ExplodingImplementation(), dependencies=("b.service",))
    )
    registry.register(_binding("b.service", ExplodingImplementation()))

    assert registry.dependency_order() == ("b.service", "a.service")
