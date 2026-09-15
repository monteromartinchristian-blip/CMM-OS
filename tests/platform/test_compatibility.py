"""Phase 11.1 – Tests for deterministic offline contract compatibility."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from cmm.platform.compatibility import (
    CompatibilityResult,
    CompatibilityStatus,
    check_contract_compatibility,
)
from cmm.platform.contracts import ContractMetadata


def _required(
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


# ── Happy path ───────────────────────────────────────────────────────────────


def test_exact_contract_and_schema_are_compatible() -> None:
    required = ContractMetadata(
        "validation.application", "1.0.0", "1", "cmm.validation"
    )
    provided = ContractMetadata(
        "validation.application", "1.0.0", "1", "cmm.validation"
    )

    result = check_contract_compatibility(required, provided)

    assert result.compatible is True
    assert result.reason_code == "EXACT_MATCH"
    assert result.status is CompatibilityStatus.COMPATIBLE


# ── Fail-closed mismatches ───────────────────────────────────────────────────


def test_schema_mismatch_fails_closed() -> None:
    required = ContractMetadata(
        "validation.application", "1.0.0", "1", "cmm.validation"
    )
    provided = ContractMetadata(
        "validation.application", "1.0.0", "2", "cmm.validation"
    )

    result = check_contract_compatibility(required, provided)

    assert result.compatible is False
    assert result.reason_code == "SCHEMA_VERSION_MISMATCH"


def test_contract_name_mismatch_fails_closed() -> None:
    required = ContractMetadata(
        "validation.application", "1.0.0", "1", "cmm.validation"
    )
    provided = ContractMetadata("domain.registry", "1.0.0", "1", "cmm.domains")

    assert check_contract_compatibility(required, provided).compatible is False


def test_contract_name_mismatch_reason_code() -> None:
    required = _required()
    provided = _required(contract_name="domain.registry")

    result = check_contract_compatibility(required, provided)

    assert result.reason_code == "CONTRACT_NAME_MISMATCH"
    assert result.compatible is False


def test_owner_mismatch_fails_closed() -> None:
    required = _required()
    provided = _required(owner="cmm.other")

    result = check_contract_compatibility(required, provided)

    assert result.compatible is False
    assert result.reason_code == "OWNER_MISMATCH"


def test_contract_version_mismatch_fails_closed() -> None:
    required = _required()
    provided = _required(contract_version="2.0.0")

    result = check_contract_compatibility(required, provided)

    assert result.compatible is False
    assert result.reason_code == "CONTRACT_VERSION_MISMATCH"


def test_schema_mismatch_is_reported_before_contract_version_mismatch() -> None:
    """Check precedence is deterministic when several fields differ."""

    required = _required()
    provided = _required(schema_version="2", contract_version="9.9.9")

    assert (
        check_contract_compatibility(required, provided).reason_code
        == "SCHEMA_VERSION_MISMATCH"
    )


def test_owner_mismatch_is_reported_before_schema_mismatch() -> None:
    required = _required()
    provided = _required(owner="cmm.other", schema_version="2")

    assert (
        check_contract_compatibility(required, provided).reason_code == "OWNER_MISMATCH"
    )


# ── Malformed input fails closed ─────────────────────────────────────────────


@pytest.mark.parametrize(
    "value",
    [
        "not a version",
        "!",
        "1..0",
        "-1.0.0",
        "1.0.0 beta",
        "v2",
        "1.0.0-",
        "1.2.3.4.5b",
    ],
)
def test_malformed_contract_version_fails_closed(value: str) -> None:
    required = _required(contract_version=value)
    provided = _required(contract_version=value)

    result = check_contract_compatibility(required, provided)

    assert result.compatible is False
    assert result.reason_code == "MALFORMED_VERSION"


@pytest.mark.parametrize("value", ["!not-a-version!", "*", "one"])
def test_malformed_schema_version_fails_closed(value: str) -> None:
    required = _required(schema_version=value)
    provided = _required(schema_version=value)

    result = check_contract_compatibility(required, provided)

    assert result.compatible is False
    assert result.reason_code == "MALFORMED_VERSION"


@pytest.mark.parametrize(
    "value",
    ["1.0.0", "1.0.0-beta.1", "2026-09-15", "1", "1.0.0+build.5", "2.14.3", "10.0.1"],
)
def test_well_formed_versions_are_accepted(value: str) -> None:
    required = _required(contract_version=value)
    provided = _required(contract_version=value)

    assert check_contract_compatibility(required, provided).compatible is True


@pytest.mark.parametrize(
    ("required_value", "provided_value"),
    [
        (None, _required()),
        (_required(), None),
        ("validation.application", _required()),
        (_required(), 42),
    ],
)
def test_non_contract_metadata_input_fails_closed(
    required_value: object, provided_value: object
) -> None:
    result = check_contract_compatibility(required_value, provided_value)  # type: ignore[arg-type]

    assert result.compatible is False
    assert result.reason_code == "MALFORMED_CONTRACT_METADATA"


# ── Determinism and immutability ─────────────────────────────────────────────


def test_compatibility_check_is_deterministic_and_side_effect_free() -> None:
    required = _required()
    provided = _required()

    first = check_contract_compatibility(required, provided)
    second = check_contract_compatibility(required, provided)
    repeated = [check_contract_compatibility(required, provided) for _ in range(5)]

    assert first == second
    assert all(item == first for item in repeated)


def test_compatibility_result_is_immutable() -> None:
    result = check_contract_compatibility(_required(), _required())

    with pytest.raises(FrozenInstanceError):
        result.status = CompatibilityStatus.INCOMPATIBLE  # type: ignore[misc]


def test_compatibility_status_exposes_documented_values() -> None:
    assert CompatibilityStatus.COMPATIBLE.value == "compatible"
    assert CompatibilityStatus.INCOMPATIBLE.value == "incompatible"


def test_incompatible_status_is_used_for_every_failure_reason() -> None:
    failures = (
        check_contract_compatibility(_required(), _required(contract_name="other")),
        check_contract_compatibility(_required(), _required(owner="cmm.other")),
        check_contract_compatibility(_required(), _required(schema_version="2")),
        check_contract_compatibility(_required(), _required(contract_version="2.0.0")),
        check_contract_compatibility(_required(contract_version="!"), _required()),
        check_contract_compatibility(None, _required()),  # type: ignore[arg-type]
    )

    assert [item.compatible for item in failures] == [False] * len(failures)
    assert {item.status for item in failures} == {CompatibilityStatus.INCOMPATIBLE}
    assert len({item.reason_code for item in failures}) == len(failures)


def test_compatibility_result_constructs_from_status() -> None:
    result = CompatibilityResult(
        status=CompatibilityStatus.COMPATIBLE, reason_code="EXACT_MATCH"
    )

    assert result.compatible is True
