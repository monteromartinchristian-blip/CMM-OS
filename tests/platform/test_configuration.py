"""Phase 11.1 – Tests for strict composition configuration."""

from __future__ import annotations

import dataclasses
from dataclasses import FrozenInstanceError

import pytest

from cmm.platform.configuration import (
    CompositionConfiguration,
    ServiceExpectation,
)
from cmm.platform.contracts import ContractMetadata, RuntimeContractMatch
from cmm.platform.errors import InvalidConfigurationError


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


# ── Canonicalization ─────────────────────────────────────────────────────────


def test_composition_configuration_is_immutable_and_deterministic() -> None:
    config = CompositionConfiguration(
        required_services=("validation.application", "domain.registry"),
        enabled_modules=("core",),
        expected_contracts=(),
    )

    assert config.required_services == ("domain.registry", "validation.application")


def test_enabled_modules_are_canonicalized_to_a_sorted_tuple() -> None:
    config = CompositionConfiguration(
        required_services=(),
        enabled_modules=("zeta", "alpha"),
        expected_contracts=(),
    )

    assert config.enabled_modules == ("alpha", "zeta")
    assert isinstance(config.enabled_modules, tuple)


def test_default_configuration_is_empty() -> None:
    config = CompositionConfiguration()

    assert config.required_services == ()
    assert config.enabled_modules == ()
    assert config.expected_contracts == ()


def test_configuration_is_immutable() -> None:
    config = CompositionConfiguration(required_services=("a.service",))

    with pytest.raises(FrozenInstanceError):
        config.required_services = ()  # type: ignore[misc]


def test_configuration_is_hashable() -> None:
    assert len({CompositionConfiguration(), CompositionConfiguration()}) == 1


# ── Fail-closed validation ───────────────────────────────────────────────────


def test_duplicate_required_services_are_rejected() -> None:
    with pytest.raises(InvalidConfigurationError) as exc:
        CompositionConfiguration(
            required_services=("a.service", "a.service"),
        )

    assert exc.value.result.code == "INVALID_CONFIGURATION"
    assert exc.value.result.details["service_id"] == "a.service"


def test_duplicate_enabled_modules_are_rejected() -> None:
    with pytest.raises(InvalidConfigurationError) as exc:
        CompositionConfiguration(enabled_modules=("core", "core"))

    assert exc.value.result.details["module_id"] == "core"


@pytest.mark.parametrize("value", ["", "   ", "\t"])
def test_empty_required_service_id_is_rejected(value: str) -> None:
    with pytest.raises(InvalidConfigurationError):
        CompositionConfiguration(required_services=(value,))


@pytest.mark.parametrize("value", ["", "   "])
def test_empty_enabled_module_id_is_rejected(value: str) -> None:
    with pytest.raises(InvalidConfigurationError):
        CompositionConfiguration(enabled_modules=(value,))


def test_service_ids_are_normalized() -> None:
    config = CompositionConfiguration(required_services=(" a.service ",))

    assert config.required_services == ("a.service",)


def test_configuration_rejects_non_string_service_ids() -> None:
    with pytest.raises(InvalidConfigurationError):
        CompositionConfiguration(required_services=(42,))  # type: ignore[arg-type]


# ── Expected contracts ───────────────────────────────────────────────────────


def test_expected_contracts_are_sorted_and_immutable() -> None:
    config = CompositionConfiguration(
        required_services=("a.service", "b.service"),
        expected_contracts=(
            ServiceExpectation(service_id="b.service", contract=_contract("b.service")),
            ServiceExpectation(service_id="a.service", contract=_contract("a.service")),
        ),
    )

    assert tuple(item.service_id for item in config.expected_contracts) == (
        "a.service",
        "b.service",
    )


def test_duplicate_expected_contract_service_ids_are_rejected() -> None:
    with pytest.raises(InvalidConfigurationError) as exc:
        CompositionConfiguration(
            expected_contracts=(
                ServiceExpectation(
                    service_id="a.service", contract=_contract("a.service")
                ),
                ServiceExpectation(
                    service_id="a.service", contract=_contract("a.service")
                ),
            )
        )

    assert exc.value.result.details["service_id"] == "a.service"


def test_service_expectation_rejects_empty_service_id() -> None:
    with pytest.raises(InvalidConfigurationError):
        ServiceExpectation(service_id="  ", contract=_contract("a.service"))


def test_service_expectation_is_immutable() -> None:
    expectation = ServiceExpectation(
        service_id="a.service", contract=_contract("a.service")
    )

    with pytest.raises(FrozenInstanceError):
        expectation.service_id = "other"  # type: ignore[misc]


def test_expected_contract_lookup_by_service_id() -> None:
    expectation = ServiceExpectation(
        service_id="a.service", contract=_contract("a.service")
    )
    config = CompositionConfiguration(
        required_services=("a.service",), expected_contracts=(expectation,)
    )

    assert config.expected_contract_for("a.service") is expectation
    assert config.expected_contract_for("missing.service") is None


# ── Authoritative runtime expectations (Remediation V3) ──────────────────────
#
# Remediation V3 for Phase 11.50 MAJOR_V3_01 anchors a canonical service's
# runtime identity in the existing Phase 11.1 expectation path instead of the
# caller-authored ``ServiceBinding.runtime_contract`` field.  These tests cover
# the extension of the one canonical ``ServiceExpectation`` value.


class RuntimePort:
    """Test-local runtime contract type."""


def _runtime_expectation(**overrides: object) -> ServiceExpectation:
    values: dict[str, object] = {
        "service_id": "a.service",
        "contract": _contract("a.service"),
    }
    values.update(overrides)
    return ServiceExpectation(**values)  # type: ignore[arg-type]


def test_legacy_service_expectation_declaration_is_preserved() -> None:
    """``LEGACY_SERVICE_EXPECTATION_CONSTRUCTION=PRESERVED``.

    The Phase 11.1 expectation shape ``ServiceExpectation(service_id, contract)``
    stays source-compatible and adds no runtime policy of its own.
    """

    expectation = ServiceExpectation(
        service_id="a.service", contract=_contract("a.service")
    )

    assert expectation.runtime_contract is None
    assert expectation.runtime_contract_match is None


@pytest.mark.parametrize(
    "match",
    [RuntimeContractMatch.INSTANCE_OF, RuntimeContractMatch.EXACT_TYPE],
    ids=["INSTANCE_OF", "EXACT_TYPE"],
)
def test_service_expectation_accepts_a_complete_runtime_policy(
    match: RuntimeContractMatch,
) -> None:
    expectation = _runtime_expectation(
        runtime_contract=RuntimePort, runtime_contract_match=match
    )

    assert expectation.runtime_contract is RuntimePort
    assert expectation.runtime_contract_match is match


def test_service_expectation_rejects_a_match_without_a_runtime_contract() -> None:
    with pytest.raises(InvalidConfigurationError) as exc:
        _runtime_expectation(runtime_contract_match=RuntimeContractMatch.EXACT_TYPE)

    assert exc.value.result.details["field"] == "runtime_contract_match"


def test_service_expectation_rejects_a_runtime_contract_without_a_match() -> None:
    """A declared runtime contract with no match rule is ambiguous: fail closed."""

    with pytest.raises(InvalidConfigurationError) as exc:
        _runtime_expectation(runtime_contract=RuntimePort)

    assert exc.value.result.details["field"] == "runtime_contract_match"


@pytest.mark.parametrize(
    "value",
    ["cmm.platform.configuration.ServiceExpectation", object(), 42, RuntimePort()],
    ids=["import_path", "instance", "integer", "contract_instance"],
)
def test_service_expectation_rejects_a_non_type_runtime_contract(
    value: object,
) -> None:
    with pytest.raises(InvalidConfigurationError) as exc:
        _runtime_expectation(
            runtime_contract=value,
            runtime_contract_match=RuntimeContractMatch.INSTANCE_OF,
        )

    assert exc.value.result.details["field"] == "runtime_contract"


@pytest.mark.parametrize(
    "value",
    ["exact_type", 1, object(), RuntimePort],
    ids=["string", "integer", "object", "type"],
)
def test_service_expectation_rejects_a_non_enum_runtime_contract_match(
    value: object,
) -> None:
    with pytest.raises(InvalidConfigurationError) as exc:
        _runtime_expectation(runtime_contract=RuntimePort, runtime_contract_match=value)

    assert exc.value.result.details["field"] == "runtime_contract_match"


def test_runtime_expectations_are_immutable_hashable_values() -> None:
    first = _runtime_expectation(
        runtime_contract=RuntimePort,
        runtime_contract_match=RuntimeContractMatch.EXACT_TYPE,
    )
    second = _runtime_expectation(
        runtime_contract=RuntimePort,
        runtime_contract_match=RuntimeContractMatch.EXACT_TYPE,
    )

    assert first == second
    assert len({first, second}) == 1

    with pytest.raises(FrozenInstanceError):
        first.runtime_contract = None  # type: ignore[misc]


def test_configuration_carries_an_authoritative_runtime_expectation() -> None:
    expectation = _runtime_expectation(
        runtime_contract=RuntimePort,
        runtime_contract_match=RuntimeContractMatch.EXACT_TYPE,
    )
    config = CompositionConfiguration(
        required_services=("a.service",), expected_contracts=(expectation,)
    )

    assert config.expected_contract_for("a.service") is expectation


# ── Composition-only scope ───────────────────────────────────────────────────


def test_configuration_exposes_no_secret_bearing_fields() -> None:
    """Composition configuration must never carry secrets or credentials."""

    forbidden = ("secret", "credential", "token", "password", "api_key", "auth")

    for value_type in (CompositionConfiguration, ServiceExpectation):
        for field in dataclasses.fields(value_type):
            lowered = field.name.lower()
            assert not any(token in lowered for token in forbidden), (
                f"{value_type.__name__}.{field.name} looks like a secret-bearing field"
            )
