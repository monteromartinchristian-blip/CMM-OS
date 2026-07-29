"""Phase 10.1 – Domain Errors.

Error hierarchy for the Domain Intelligence subsystem.
"""

from __future__ import annotations

from types import MappingProxyType
from typing import Any


def _deep_freeze_details(d: dict[str, Any] | None) -> MappingProxyType[str, Any]:
    """Recursively freeze a dictionary into an immutable MappingProxyType."""
    if d is None:
        return MappingProxyType({})
    frozen: dict[str, Any] = {}
    for k, v in d.items():
        if not isinstance(k, str):
            raise TypeError("Details keys must be strings")
        frozen[k] = _freeze_value(v)
    return MappingProxyType(frozen)


def _freeze_value(v: Any) -> Any:
    """Recursively freeze a value: mappings → MappingProxyType, lists/tuples → tuple, sets → frozenset."""
    if isinstance(v, dict):
        return MappingProxyType({kk: _freeze_value(vv) for kk, vv in v.items()})
    if isinstance(v, (list, tuple)):
        return tuple(_freeze_value(vv) for vv in v)
    if isinstance(v, (set, frozenset)):
        return frozenset(_freeze_value(vv) for vv in v)
    return v


class DomainError(Exception):
    """Base error for all Domain operations."""

    code: str = "DOMAIN_ERROR"

    def __init__(
        self,
        message: str,
        *,
        field: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.field: str | None = field
        self._details: MappingProxyType[str, Any] = _deep_freeze_details(details)

    @property
    def details(self) -> MappingProxyType[str, Any]:
        """Immutable details dictionary (deeply frozen)."""
        return self._details


class DomainContractError(DomainError, ValueError):
    """Base error for Domain contract violations."""

    code = "DOMAIN_CONTRACT_ERROR"


class DomainContractValidationError(DomainContractError):
    """Raised when a Domain contract fails validation."""

    code = "DOMAIN_CONTRACT_VALIDATION_ERROR"


class DomainSerializationError(DomainError):
    """Raised when serialization or deserialization fails."""

    code = "DOMAIN_SERIALIZATION_ERROR"


__all__ = [
    "DomainContractError",
    "DomainContractValidationError",
    "DomainError",
    "DomainSerializationError",
]
