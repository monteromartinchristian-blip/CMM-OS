"""Phase 11.1 — strict in-memory composition configuration.

This is **composition configuration only**.  It is not the Phase 11.12
Configuration Center and it owns no secrets, credentials, user preferences,
model-routing policy, domain privacy policy, autonomy policy or general
application settings.

Phase 11.1 does not parse YAML, TOML, JSON or environment variables: the
contract receives values that were already loaded by the caller.  Validation is
strict and fails closed, so a malformed or ambiguous composition selection can
never be silently collapsed into a valid one.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from cmm.platform.contracts import ContractMetadata
from cmm.platform.errors import InvalidConfigurationError


def _normalized_identifier(value: object, *, label: str) -> str:
    if not isinstance(value, str):
        raise InvalidConfigurationError(
            f"{label} must be a string",
            details={"field": label},
        )
    normalized = value.strip()
    if not normalized:
        raise InvalidConfigurationError(
            f"{label} must be non-empty",
            details={"field": label},
        )
    return normalized


def _canonicalize_identifiers(
    values: tuple[str, ...], *, label: str, detail_key: str
) -> tuple[str, ...]:
    """Fail closed on duplicates, then return a sorted, deterministic tuple.

    Duplicates are rejected rather than silently collapsed: a repeated ID almost
    always means the composition selection is ambiguous, and hiding that would
    make an invalid configuration look valid.
    """

    if not isinstance(values, tuple):
        raise InvalidConfigurationError(
            f"{label} must be a tuple",
            details={"field": label},
        )

    normalized = [_normalized_identifier(value, label=label) for value in values]

    seen: set[str] = set()
    for value in normalized:
        if value in seen:
            raise InvalidConfigurationError(
                f"{label} must not contain duplicates",
                details={detail_key: value},
            )
        seen.add(value)

    return tuple(sorted(normalized))


@dataclass(frozen=True, slots=True)
class ServiceExpectation:
    """A configured expectation about one composed service contract."""

    service_id: str
    contract: ContractMetadata

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "service_id",
            _normalized_identifier(self.service_id, label="service_id"),
        )
        if not isinstance(self.contract, ContractMetadata):
            raise InvalidConfigurationError(
                "contract must be ContractMetadata",
                details={"field": "contract"},
            )


def _canonicalize_expectations(
    values: tuple[ServiceExpectation, ...],
) -> tuple[ServiceExpectation, ...]:
    if not isinstance(values, tuple):
        raise InvalidConfigurationError(
            "expected_contracts must be a tuple",
            details={"field": "expected_contracts"},
        )

    for value in values:
        if not isinstance(value, ServiceExpectation):
            raise InvalidConfigurationError(
                "expected_contracts must contain ServiceExpectation values",
                details={"field": "expected_contracts"},
            )

    seen: set[str] = set()
    for value in values:
        if value.service_id in seen:
            raise InvalidConfigurationError(
                "expected_contracts must not contain duplicate service IDs",
                details={"service_id": value.service_id},
            )
        seen.add(value.service_id)

    return tuple(sorted(values, key=lambda item: item.service_id))


@dataclass(frozen=True, slots=True)
class CompositionConfiguration:
    """Strict Phase 11.1 composition configuration."""

    required_services: tuple[str, ...] = ()
    enabled_modules: tuple[str, ...] = ()
    expected_contracts: tuple[ServiceExpectation, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "required_services",
            _canonicalize_identifiers(
                self.required_services,
                label="required_services",
                detail_key="service_id",
            ),
        )
        object.__setattr__(
            self,
            "enabled_modules",
            _canonicalize_identifiers(
                self.enabled_modules,
                label="enabled_modules",
                detail_key="module_id",
            ),
        )
        object.__setattr__(
            self,
            "expected_contracts",
            _canonicalize_expectations(self.expected_contracts),
        )

    def expected_contract_for(self, service_id: str) -> ServiceExpectation | None:
        """Return the configured contract expectation for *service_id*."""

        for expectation in self.expected_contracts:
            if expectation.service_id == service_id:
                return expectation
        return None


__all__ = ["CompositionConfiguration", "ServiceExpectation"]
