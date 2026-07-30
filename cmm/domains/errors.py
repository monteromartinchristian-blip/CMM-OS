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


class DomainRegistryError(DomainError):
    """Base error for Domain Registry operations."""

    code = "DOMAIN_REGISTRY_ERROR"


class DomainRegistryValidationError(DomainRegistryError):
    """Raised when registry validation fails."""

    code = "DOMAIN_REGISTRY_VALIDATION_ERROR"


class DomainRegistryConflict(DomainRegistryError):
    """Raised when a registry conflict is detected (duplicate, incompatible states)."""

    code = "DOMAIN_REGISTRY_CONFLICT"


class DomainRegistryNotFound(DomainRegistryError):
    """Raised when a domain entry is not found in the registry."""

    code = "DOMAIN_REGISTRY_NOT_FOUND"


class DomainRegistryVersionError(DomainRegistryError):
    """Raised when version constraints or semantics are violated."""

    code = "DOMAIN_REGISTRY_VERSION_ERROR"


class DomainRegistryStateError(DomainRegistryError):
    """Raised when a state transition is invalid."""

    code = "DOMAIN_REGISTRY_STATE_ERROR"


class DomainDependencyMissing(DomainRegistryError):
    """Raised when a required dependency is absent."""

    code = "DOMAIN_DEPENDENCY_MISSING"


class DomainCapabilityConflict(DomainRegistryError):
    """Raised when capabilities conflict across domains."""

    code = "DOMAIN_CAPABILITY_CONFLICT"


class DomainDiscoveryError(DomainError):
    """Base error for Domain Discovery operations."""

    code = "DOMAIN_DISCOVERY_ERROR"


class DomainDiscoverySourceError(DomainDiscoveryError):
    """Raised when a discovery source cannot be scanned."""

    code = "DOMAIN_DISCOVERY_SOURCE_ERROR"


class DomainCandidateInvalid(DomainDiscoveryError):
    """Raised when a discovered candidate fails structural validation."""

    code = "DOMAIN_CANDIDATE_INVALID"


class DomainPathEscape(DomainDiscoveryError):
    """Raised when a resolved path escapes its authorized root."""

    code = "DOMAIN_PATH_ESCAPE"


class DomainLoaderError(DomainError):
    """Base error for Domain Loader operations."""

    code = "DOMAIN_LOADER_ERROR"


class DomainLoadRejected(DomainLoaderError):
    """Raised when a load is rejected by policy (e.g. untrusted source)."""

    code = "DOMAIN_LOAD_REJECTED"


class DomainLoadFailed(DomainLoaderError):
    """Raised when a load operation fails."""

    code = "DOMAIN_LOAD_FAILED"


class DomainUnloadFailed(DomainLoaderError):
    """Raised when an unload operation fails."""

    code = "DOMAIN_UNLOAD_FAILED"


class DomainReloadFailed(DomainLoaderError):
    """Raised when a reload operation fails."""

    code = "DOMAIN_RELOAD_FAILED"


class DomainChecksumMismatch(DomainLoaderError):
    """Raised when a recalculated checksum does not match the declared one."""

    code = "DOMAIN_CHECKSUM_MISMATCH"


class DomainSourceUntrusted(DomainLoaderError):
    """Raised when an untrusted candidate is loaded without explicit opt-in."""

    code = "DOMAIN_SOURCE_UNTRUSTED"


class DomainRollbackFailed(DomainLoaderError):
    """Base error for a failed rollback of a loader transaction.

    Raised when a loader operation (load/unload/reload) fails *and* the
    subsequent attempt to restore the registry to its pre-operation
    snapshot also fails. This must never be swallowed: a failed rollback
    means atomicity is lost, and callers must be told explicitly rather
    than have the loader silently continue in a possibly-inconsistent
    state.
    """

    code = "DOMAIN_ROLLBACK_FAILED"


class DomainLoadRollbackFailed(DomainRollbackFailed):
    """Raised when rollback after a failed load() also fails."""

    code = "DOMAIN_LOAD_ROLLBACK_FAILED"


class DomainUnloadRollbackFailed(DomainRollbackFailed):
    """Raised when rollback after a failed unload() also fails."""

    code = "DOMAIN_UNLOAD_ROLLBACK_FAILED"


class DomainReloadRollbackFailed(DomainRollbackFailed):
    """Raised when rollback after a failed reload() also fails."""

    code = "DOMAIN_RELOAD_ROLLBACK_FAILED"


# ── Phase 10.5 – Domain Validation Errors ──────────────────────────────────────


class DomainValidationError(DomainError):
    """Base error for Domain Validation operations (Phase 10.5)."""

    code = "DOMAIN_VALIDATION_ERROR"


class DomainValidationRequestInvalid(DomainValidationError):
    """Raised when a DomainValidationRequest is structurally invalid."""

    code = "DOMAIN_VALIDATION_REQUEST_INVALID"


class DomainValidationExecutionError(DomainValidationError):
    """Raised when validation execution fails unexpectedly."""

    code = "DOMAIN_VALIDATION_EXECUTION_ERROR"


class DomainValidationBlocked(DomainValidationError):
    """Raised when a domain operation is blocked by validation results."""

    code = "DOMAIN_VALIDATION_BLOCKED"


class DomainValidationStepMissing(DomainValidationError):
    """Raised when a required validation step is absent."""

    code = "DOMAIN_VALIDATION_STEP_MISSING"


class DomainValidationContextInvalid(DomainValidationError):
    """Raised when the validation context is invalid or inconsistent."""

    code = "DOMAIN_VALIDATION_CONTEXT_INVALID"


__all__ = [
    "DomainCandidateInvalid",
    "DomainCapabilityConflict",
    "DomainChecksumMismatch",
    "DomainContractError",
    "DomainContractValidationError",
    "DomainDependencyMissing",
    "DomainDiscoveryError",
    "DomainDiscoverySourceError",
    "DomainError",
    "DomainLoadFailed",
    "DomainLoadRejected",
    "DomainLoadRollbackFailed",
    "DomainLoaderError",
    "DomainPathEscape",
    "DomainRegistryConflict",
    "DomainRegistryError",
    "DomainRegistryNotFound",
    "DomainRegistryStateError",
    "DomainRegistryValidationError",
    "DomainRegistryVersionError",
    "DomainReloadFailed",
    "DomainReloadRollbackFailed",
    "DomainRollbackFailed",
    "DomainSerializationError",
    "DomainSourceUntrusted",
    "DomainUnloadFailed",
    "DomainUnloadRollbackFailed",
    "DomainValidationBlocked",
    "DomainValidationContextInvalid",
    "DomainValidationError",
    "DomainValidationExecutionError",
    "DomainValidationRequestInvalid",
    "DomainValidationStepMissing",
]
