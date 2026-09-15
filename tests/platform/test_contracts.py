"""Phase 11.1 – Tests for the platform boundary contracts."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from cmm.platform.contracts import (
    ContainerState,
    ContractCanonicalizationEntry,
    ContractClassification,
    ContractMetadata,
    ErrorResult,
    ServiceBinding,
    ServiceDependency,
    ServiceDescriptor,
    ServiceMode,
)


def _metadata(
    contract_name: str = "validation.application",
    contract_version: str = "1.0.0",
    schema_version: str = "1",
    owner: str = "cmm.validation",
) -> ContractMetadata:
    return ContractMetadata(
        contract_name=contract_name,
        contract_version=contract_version,
        schema_version=schema_version,
        owner=owner,
    )


def _descriptor(
    service_id: str = "validation.application",
    *,
    dependencies: tuple[ServiceDependency, ...] = (),
    authority: str | None = None,
    metadata: object = None,
    contract: ContractMetadata | None = None,
) -> ServiceDescriptor:
    return ServiceDescriptor(
        service_id=service_id,
        contract=contract if contract is not None else _metadata(),
        implementation_id="validation.default",
        dependencies=dependencies,
        mode=ServiceMode.LOCAL,
        authority=authority,
        metadata={} if metadata is None else metadata,  # type: ignore[arg-type]
    )


# ── ContractMetadata ─────────────────────────────────────────────────────────


def test_contract_metadata_is_immutable_and_requires_non_empty_identity() -> None:
    metadata = ContractMetadata(
        contract_name="validation.application",
        contract_version="1.0.0",
        schema_version="1",
        owner="cmm.validation",
    )

    assert metadata.contract_name == "validation.application"
    assert metadata.contract_version == "1.0.0"
    assert metadata.schema_version == "1"
    assert metadata.owner == "cmm.validation"

    with pytest.raises(FrozenInstanceError):
        metadata.owner = "other"  # type: ignore[misc]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("contract_name", ""),
        ("contract_version", ""),
        ("schema_version", ""),
        ("owner", ""),
    ],
)
def test_contract_metadata_rejects_empty_required_fields(
    field: str, value: str
) -> None:
    payload = {
        "contract_name": "validation.application",
        "contract_version": "1.0.0",
        "schema_version": "1",
        "owner": "cmm.validation",
    }
    payload[field] = value

    with pytest.raises(ValueError):
        ContractMetadata(**payload)


def test_contract_metadata_normalizes_surrounding_whitespace() -> None:
    metadata = ContractMetadata(
        contract_name=" validation.application ",
        contract_version=" 1.0.0 ",
        schema_version=" 1 ",
        owner=" cmm.validation ",
    )

    assert metadata == _metadata()


def test_contract_metadata_is_hashable_and_comparable_by_value() -> None:
    assert _metadata() == _metadata()
    assert len({_metadata(), _metadata()}) == 1


# ── Enumerations ─────────────────────────────────────────────────────────────


def test_platform_enumerations_expose_the_documented_values() -> None:
    assert ContractClassification.CANONICAL_EXISTING.value == "canonical_existing"
    assert ContractClassification.CANONICAL_ADAPTED.value == "canonical_adapted"
    assert ContractClassification.NEW_PLATFORM_BOUNDARY.value == "new_platform_boundary"
    assert ServiceMode.LOCAL.value == "local"
    assert ServiceMode.ADAPTER.value == "adapter"
    assert ContainerState.BUILDING.value == "building"
    assert ContainerState.READY.value == "ready"
    assert ContainerState.FAILED.value == "failed"


# ── ContractCanonicalizationEntry ────────────────────────────────────────────


def test_canonicalization_entry_records_classification_immutably() -> None:
    entry = ContractCanonicalizationEntry(
        roadmap_name="DomainDefinition",
        python_symbol="cmm.domains.contracts.DomainDefinition",
        owner="cmm.domains",
        metadata=_metadata("domain.definition", "1.0.0", "1", "cmm.domains"),
        classification=ContractClassification.CANONICAL_EXISTING,
        justification="canonical domain contract owner",
    )

    assert entry.classification is ContractClassification.CANONICAL_EXISTING
    assert entry.python_symbol == "cmm.domains.contracts.DomainDefinition"

    with pytest.raises(FrozenInstanceError):
        entry.owner = "other"  # type: ignore[misc]


# ── ServiceDependency / ServiceDescriptor ────────────────────────────────────


def test_service_dependency_and_descriptor_canonicalize_order() -> None:
    contract = _metadata()
    descriptor = ServiceDescriptor(
        service_id="validation.application",
        contract=contract,
        implementation_id="validation.default",
        dependencies=(
            ServiceDependency(service_id="domain.registry", contract=contract),
        ),
        mode=ServiceMode.LOCAL,
        authority="validation",
        metadata={"safe": True},
    )

    assert descriptor.service_id == "validation.application"
    assert descriptor.dependencies[0].service_id == "domain.registry"
    assert descriptor.metadata == {"safe": True}


def test_service_descriptor_sorts_dependencies_deterministically() -> None:
    contract = _metadata()
    descriptor = _descriptor(
        dependencies=(
            ServiceDependency(service_id="z.service", contract=contract),
            ServiceDependency(service_id="a.service", contract=contract),
        )
    )

    assert tuple(dep.service_id for dep in descriptor.dependencies) == (
        "a.service",
        "z.service",
    )


@pytest.mark.parametrize("value", ["", "   ", "\t"])
def test_service_dependency_rejects_empty_service_id(value: str) -> None:
    with pytest.raises(ValueError):
        ServiceDependency(service_id=value, contract=_metadata())


@pytest.mark.parametrize("value", ["", "   "])
def test_service_descriptor_rejects_empty_service_id(value: str) -> None:
    with pytest.raises(ValueError):
        _descriptor(service_id=value)


@pytest.mark.parametrize("value", ["", "   "])
def test_service_descriptor_rejects_empty_implementation_id(value: str) -> None:
    with pytest.raises(ValueError):
        ServiceDescriptor(
            service_id="validation.application",
            contract=_metadata(),
            implementation_id=value,
        )


def test_service_descriptor_rejects_self_dependency() -> None:
    with pytest.raises(ValueError):
        _descriptor(
            "validation.application",
            dependencies=(
                ServiceDependency(
                    service_id="validation.application", contract=_metadata()
                ),
            ),
        )


def test_service_descriptor_rejects_duplicate_dependency_ids() -> None:
    contract = _metadata()
    with pytest.raises(ValueError):
        _descriptor(
            dependencies=(
                ServiceDependency(service_id="domain.registry", contract=contract),
                ServiceDependency(service_id="domain.registry", contract=contract),
            )
        )


def test_service_descriptor_rejects_blank_authority_when_provided() -> None:
    with pytest.raises(ValueError):
        _descriptor(authority="   ")


def test_service_descriptor_normalizes_absent_authority_to_none() -> None:
    assert _descriptor(authority=None).authority is None


def test_service_descriptor_defensively_copies_metadata() -> None:
    source = {"safe": "value"}
    descriptor = _descriptor(metadata=source)

    source["injected"] = "later"

    assert dict(descriptor.metadata) == {"safe": "value"}

    with pytest.raises(TypeError):
        descriptor.metadata["injected"] = "later"  # type: ignore[index]


def test_service_descriptor_is_immutable() -> None:
    descriptor = _descriptor()

    with pytest.raises(FrozenInstanceError):
        descriptor.service_id = "other"  # type: ignore[misc]


def test_service_descriptor_defaults_to_local_mode_without_authority() -> None:
    descriptor = _descriptor()

    assert descriptor.mode is ServiceMode.LOCAL
    assert descriptor.authority is None
    assert descriptor.dependencies == ()


# ── ServiceBinding ───────────────────────────────────────────────────────────


def test_service_binding_preserves_implementation_identity() -> None:
    implementation = object()
    descriptor = _descriptor()
    binding = ServiceBinding(descriptor=descriptor, implementation=implementation)

    assert binding.implementation is implementation
    assert binding.descriptor is descriptor
    assert binding.runtime_contract is None


def test_service_binding_is_immutable() -> None:
    binding = ServiceBinding(descriptor=_descriptor(), implementation=object())

    with pytest.raises(FrozenInstanceError):
        binding.implementation = object()  # type: ignore[misc]


# ── ErrorResult ──────────────────────────────────────────────────────────────


def test_error_result_requires_non_empty_identity() -> None:
    result = ErrorResult(
        code="MISSING_DEPENDENCY",
        message="Required service is missing",
        category="composition",
    )

    assert result.code == "MISSING_DEPENDENCY"
    assert result.message == "Required service is missing"
    assert result.category == "composition"
    assert dict(result.details) == {}


@pytest.mark.parametrize("field", ["code", "message", "category"])
def test_error_result_rejects_empty_required_fields(field: str) -> None:
    payload = {
        "code": "MISSING_DEPENDENCY",
        "message": "Required service is missing",
        "category": "composition",
    }
    payload[field] = "  "

    with pytest.raises(ValueError):
        ErrorResult(**payload)


def test_error_result_details_are_immutable_and_defensively_copied() -> None:
    source = {"service_id": "agent.runtime"}
    result = ErrorResult(
        code="MISSING_DEPENDENCY",
        message="Required service is missing",
        category="composition",
        details=source,
    )

    source["injected"] = "later"

    assert dict(result.details) == {"service_id": "agent.runtime"}

    with pytest.raises(TypeError):
        result.details["injected"] = "later"  # type: ignore[index]


def test_error_result_rejects_non_string_detail_values() -> None:
    with pytest.raises(TypeError):
        ErrorResult(
            code="MISSING_DEPENDENCY",
            message="Required service is missing",
            category="composition",
            details={"service_id": object()},  # type: ignore[dict-item]
        )


def test_error_result_is_immutable() -> None:
    result = ErrorResult(code="X", message="Y", category="Z")

    with pytest.raises(FrozenInstanceError):
        result.code = "other"  # type: ignore[misc]
