"""Phase 11.1 – Tests for side-effect-free composition modules."""

from __future__ import annotations

import pytest

from cmm.platform.configuration import CompositionConfiguration
from cmm.platform.contracts import (
    ContractMetadata,
    ServiceBinding,
    ServiceDescriptor,
)
from cmm.platform.errors import DuplicateServiceError
from cmm.platform.modules import CompositionModule, StaticCompositionModule
from cmm.platform.service_registry import IntegrationServiceRegistry


def _binding(service_id: str) -> ServiceBinding:
    return ServiceBinding(
        descriptor=ServiceDescriptor(
            service_id=service_id,
            contract=ContractMetadata(
                contract_name=service_id,
                contract_version="1.0.0",
                schema_version="1",
                owner="cmm.platform.test",
            ),
            implementation_id="test.implementation",
        ),
        implementation=object(),
    )


# ── Module contract ──────────────────────────────────────────────────────────


def test_static_module_satisfies_the_composition_module_protocol() -> None:
    module = StaticCompositionModule(
        module_id="core", bindings=(_binding("a.service"),)
    )

    assert isinstance(module, CompositionModule)


def test_module_id_is_stable_and_non_empty() -> None:
    module = StaticCompositionModule(module_id="core")

    assert module.module_id == "core"
    assert module.module_id == "core"


@pytest.mark.parametrize("value", ["", "   "])
def test_module_rejects_empty_module_id(value: str) -> None:
    with pytest.raises(ValueError):
        StaticCompositionModule(module_id=value)


def test_module_rejects_non_string_module_id() -> None:
    with pytest.raises(TypeError):
        StaticCompositionModule(module_id=42)  # type: ignore[arg-type]


# ── Side-effect freedom ──────────────────────────────────────────────────────


def test_constructing_a_module_registers_nothing() -> None:
    registry = IntegrationServiceRegistry()

    StaticCompositionModule(module_id="core", bindings=(_binding("a.service"),))

    assert registry.list_bindings() == ()


def test_contribute_returns_bindings_only_when_explicitly_invoked() -> None:
    registry = IntegrationServiceRegistry()
    module = StaticCompositionModule(
        module_id="core", bindings=(_binding("a.service"),)
    )
    configuration = CompositionConfiguration(required_services=("a.service",))

    assert registry.list_bindings() == ()

    contributed = module.contribute(configuration)

    assert tuple(item.descriptor.service_id for item in contributed) == ("a.service",)
    # Contribution itself still did not register anything.
    assert registry.list_bindings() == ()


def test_contribute_returns_an_immutable_tuple() -> None:
    module = StaticCompositionModule(module_id="core", bindings=())

    contributed = module.contribute(CompositionConfiguration())

    assert isinstance(contributed, tuple)


def test_module_does_not_mutate_the_configuration() -> None:
    configuration = CompositionConfiguration(
        required_services=("a.service",), enabled_modules=("core",)
    )
    module = StaticCompositionModule(
        module_id="core", bindings=(_binding("b.service"),)
    )

    module.contribute(configuration)

    assert configuration == CompositionConfiguration(
        required_services=("a.service",), enabled_modules=("core",)
    )


def test_module_is_immutable() -> None:
    module = StaticCompositionModule(
        module_id="core", bindings=(_binding("a.service"),)
    )

    with pytest.raises(AttributeError):
        module.module_id = "other"  # type: ignore[misc]


def test_module_defensively_copies_the_binding_sequence() -> None:
    bindings = [_binding("a.service")]
    module = StaticCompositionModule(module_id="core", bindings=tuple(bindings))

    bindings.append(_binding("b.service"))

    assert tuple(
        item.descriptor.service_id
        for item in module.contribute(CompositionConfiguration())
    ) == ("a.service",)


# ── Duplicate contributions go through the normal registry path ──────────────


def test_duplicate_contributed_service_ids_are_rejected_by_the_registry() -> None:
    module = StaticCompositionModule(
        module_id="core",
        bindings=(_binding("a.service"), _binding("a.service")),
    )
    registry = IntegrationServiceRegistry()

    contributed = module.contribute(CompositionConfiguration())
    registry.register(contributed[0])

    with pytest.raises(DuplicateServiceError):
        registry.register(contributed[1])
