"""Phase 11.1 – Tests for safe deterministic composition inspection."""

from __future__ import annotations

import json
from dataclasses import FrozenInstanceError

import pytest

from cmm.platform.contracts import (
    ContainerState,
    ContractMetadata,
    ServiceBinding,
    ServiceDependency,
    ServiceDescriptor,
    ServiceMode,
)
from cmm.platform.inspection import (
    ApplicationCompositionSnapshot,
    ServiceInspection,
    build_composition_snapshot,
)
from cmm.platform.service_registry import IntegrationServiceRegistry

FORBIDDEN_KEYS = (
    "secret",
    "credential",
    "token",
    "password",
    "prompt",
    "reasoning",
    "payload",
)


def _contract(contract_name: str) -> ContractMetadata:
    return ContractMetadata(
        contract_name=contract_name,
        contract_version="1.0.0",
        schema_version="1",
        owner="cmm.platform.test",
    )


def _registry() -> IntegrationServiceRegistry:
    registry = IntegrationServiceRegistry()
    registry.register(
        ServiceBinding(
            descriptor=ServiceDescriptor(
                service_id="b.service",
                contract=_contract("b.service"),
                implementation_id="impl.b",
                dependencies=(
                    ServiceDependency(
                        service_id="a.service", contract=_contract("a.service")
                    ),
                ),
                mode=ServiceMode.ADAPTER,
                authority="b-authority",
                metadata={"leak_marker": "descriptor-metadata-value"},
            ),
            implementation=object(),
            runtime_contract=object,
        )
    )
    registry.register(
        ServiceBinding(
            descriptor=ServiceDescriptor(
                service_id="a.service",
                contract=_contract("a.service"),
                implementation_id="impl.a",
            ),
            implementation=object(),
        )
    )
    return registry


def _snapshot() -> ApplicationCompositionSnapshot:
    return build_composition_snapshot(ContainerState.READY, _registry())


# ── Content ──────────────────────────────────────────────────────────────────


def test_snapshot_lists_services_sorted_by_service_id() -> None:
    snapshot = _snapshot()

    assert tuple(service.service_id for service in snapshot.services) == (
        "a.service",
        "b.service",
    )


def test_snapshot_exposes_contract_boundary_metadata() -> None:
    service = _snapshot().services[0]

    assert service.service_id == "a.service"
    assert service.implementation_id == "impl.a"
    assert service.contract_name == "a.service"
    assert service.contract_version == "1.0.0"
    assert service.schema_version == "1"
    assert service.owner == "cmm.platform.test"


def test_snapshot_exposes_dependency_ids_sorted() -> None:
    service = _snapshot().services[1]

    assert service.dependency_ids == ("a.service",)


def test_snapshot_exposes_mode_and_authority() -> None:
    service = _snapshot().services[1]

    assert service.mode == "adapter"
    assert service.authority == "b-authority"


def test_snapshot_exposes_absent_authority_as_none() -> None:
    assert _snapshot().services[0].authority is None


def test_snapshot_exposes_container_state() -> None:
    snapshot = _snapshot()

    assert snapshot.state is ContainerState.READY
    assert snapshot.state == "ready"


def test_snapshot_of_building_state_is_distinct() -> None:
    snapshot = build_composition_snapshot(ContainerState.BUILDING, _registry())

    assert snapshot.state is ContainerState.BUILDING


def test_empty_registry_produces_an_empty_snapshot() -> None:
    snapshot = build_composition_snapshot(
        ContainerState.BUILDING, IntegrationServiceRegistry()
    )

    assert snapshot.services == ()
    assert snapshot.to_dict() == {"state": "building", "services": []}


# ── Safety ───────────────────────────────────────────────────────────────────


def test_service_inspection_carries_no_raw_implementation() -> None:
    service = _snapshot().services[0]

    assert not hasattr(service, "implementation")
    assert not hasattr(service, "runtime_contract")
    assert not hasattr(service, "metadata")


def test_snapshot_does_not_copy_descriptor_metadata() -> None:
    serialized = json.dumps(_snapshot().to_dict())

    assert "descriptor-metadata-value" not in serialized
    assert "leak_marker" not in serialized


def test_snapshot_output_contains_no_forbidden_keys() -> None:
    def collect_keys(value: object) -> set[str]:
        if isinstance(value, dict):
            keys = set(value)
            for item in value.values():
                keys |= collect_keys(item)
            return keys
        if isinstance(value, list):
            keys: set[str] = set()
            for item in value:
                keys |= collect_keys(item)
            return keys
        return set()

    keys = collect_keys(_snapshot().to_dict())

    assert not any(token in key.lower() for key in keys for token in FORBIDDEN_KEYS), (
        f"forbidden key found in snapshot output: {sorted(keys)}"
    )


def test_snapshot_output_is_json_serializable() -> None:
    """Proves the snapshot contains no raw runtime objects."""

    payload = json.dumps(_snapshot().to_dict())

    assert "a.service" in payload
    assert "impl.a" in payload


def test_snapshot_does_not_reference_the_bound_implementation() -> None:
    implementation = object()
    registry = IntegrationServiceRegistry()
    registry.register(
        ServiceBinding(
            descriptor=ServiceDescriptor(
                service_id="a.service",
                contract=_contract("a.service"),
                implementation_id="impl.a",
            ),
            implementation=implementation,
        )
    )

    snapshot = build_composition_snapshot(ContainerState.READY, registry)

    assert repr(implementation) not in json.dumps(snapshot.to_dict())


# ── Determinism and immutability ─────────────────────────────────────────────


def test_repeated_snapshots_of_unchanged_composition_are_equal() -> None:
    registry = _registry()

    first = build_composition_snapshot(ContainerState.READY, registry)
    second = build_composition_snapshot(ContainerState.READY, registry)

    assert first == second
    assert first.to_dict() == second.to_dict()


def test_snapshot_is_immutable() -> None:
    snapshot = _snapshot()

    with pytest.raises(FrozenInstanceError):
        snapshot.state = ContainerState.FAILED  # type: ignore[misc]


def test_service_inspection_is_immutable() -> None:
    service = _snapshot().services[0]

    with pytest.raises(FrozenInstanceError):
        service.service_id = "other"  # type: ignore[misc]


def test_to_dict_returns_fresh_structures() -> None:
    snapshot = _snapshot()

    payload = snapshot.to_dict()
    payload["services"].append({"service_id": "injected"})
    payload["state"] = "tampered"

    assert snapshot.to_dict()["state"] == "ready"
    assert len(snapshot.to_dict()["services"]) == 2


def test_to_dict_dependency_ids_are_plain_lists() -> None:
    payload = _snapshot().to_dict()
    service = next(
        item for item in payload["services"] if item["service_id"] == "b.service"
    )

    assert service["dependency_ids"] == ["a.service"]
    assert isinstance(service["dependency_ids"], list)


def test_snapshot_serialization_is_deterministic_across_registration_order() -> None:
    registry = _registry()
    reversed_registry = IntegrationServiceRegistry()
    for binding in reversed(registry.list_bindings()):
        reversed_registry.register(binding)

    assert (
        build_composition_snapshot(ContainerState.READY, registry).to_dict()
        == build_composition_snapshot(ContainerState.READY, reversed_registry).to_dict()
    )


def test_service_inspection_construction_requires_a_service_id() -> None:
    with pytest.raises(ValueError):
        ServiceInspection(
            service_id="  ",
            implementation_id="impl",
            contract_name="a.service",
            contract_version="1.0.0",
            schema_version="1",
            owner="cmm.platform.test",
            dependency_ids=(),
            mode=ServiceMode.LOCAL,
            authority=None,
        )
