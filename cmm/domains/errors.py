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


# ── Phase 10.6 – Domain Resolution Errors ──────────────────────────────────────


class DomainResolutionError(DomainError):
    """Base error for Domain Resolution operations (Phase 10.6)."""

    code = "DOMAIN_RESOLUTION_ERROR"


class DomainResolutionContractError(DomainResolutionError, ValueError):
    """Raised when a resolution contract invariant is violated."""

    code = "DOMAIN_RESOLUTION_CONTRACT_ERROR"


class DomainResolutionSerializationError(DomainResolutionError):
    """Raised when serialization or deserialization of resolution contracts fails."""

    code = "DOMAIN_RESOLUTION_SERIALIZATION_ERROR"


class DomainResolutionContextInvalid(DomainResolutionError):
    """Raised when a DomainResolutionContext is structurally invalid or empty."""

    code = "DOMAIN_RESOLUTION_CONTEXT_INVALID"


class DomainResolutionPolicyError(DomainResolutionError):
    """Raised when a DomainResolutionPolicy has invalid invariants."""

    code = "DOMAIN_RESOLUTION_POLICY_ERROR"


class DomainResolutionSnapshotError(DomainResolutionError):
    """Raised when a registry snapshot used for resolution is invalid."""

    code = "DOMAIN_RESOLUTION_SNAPSHOT_ERROR"


class DomainResolutionLimitExceeded(DomainResolutionError):
    """Raised when a resolution input exceeds configured limits."""

    code = "DOMAIN_RESOLUTION_LIMIT_EXCEEDED"


# ── Phase 10.7 – Domain Resolver Errors ────────────────────────────────────────


class DomainResolverError(DomainResolutionError):
    """Base error for Domain Resolver operations (Phase 10.7)."""

    code = "DOMAIN_RESOLVER_ERROR"


class DomainResolverConfigurationError(DomainResolverError):
    """Raised when the resolver is configured with invalid or incompatible settings."""

    code = "DOMAIN_RESOLVER_CONFIGURATION_ERROR"


class DomainResolverExecutionError(DomainResolverError):
    """Raised when the resolver encounters a controlled internal error.

    Only raised via explicit controlled paths, never from blind ``except Exception``.
    """

    code = "DOMAIN_RESOLVER_EXECUTION_ERROR"


class DomainResolutionAmbiguityError(DomainResolverError):
    """Raised when the resolver detects material ambiguity and cannot proceed.

    Normally ambiguity produces an AMBIGUOUS result; this exception is reserved
    for cases where the caller explicitly requires a non-ambiguous resolution.
    """

    code = "DOMAIN_RESOLUTION_AMBIGUITY_ERROR"


class DomainResolutionUnsupportedError(DomainResolverError):
    """Raised when no eligible domain is available and no fallback is safe."""

    code = "DOMAIN_RESOLUTION_UNSUPPORTED_ERROR"


class DomainResolutionBlockedError(DomainResolverError):
    """Raised when a relevant candidate exists but policy/permissions block it."""

    code = "DOMAIN_RESOLUTION_BLOCKED_ERROR"


# ── Phase 10.8 – Domain Composition Errors ──────────────────────────────────────


class DomainCompositionError(DomainError):
    """Base error for Domain Composition operations (Phase 10.8)."""

    code = "DOMAIN_COMPOSITION_ERROR"


class DomainCompositionContractError(DomainCompositionError, ValueError):
    """Raised when a composition contract invariant is violated."""

    code = "DOMAIN_COMPOSITION_CONTRACT_ERROR"


class DomainCompositionSerializationError(DomainCompositionError):
    """Raised when serialization or deserialization of composition contracts fails."""

    code = "DOMAIN_COMPOSITION_SERIALIZATION_ERROR"


class DomainCompositionConfigurationError(DomainCompositionError):
    """Raised when the composer is configured with invalid settings."""

    code = "DOMAIN_COMPOSITION_CONFIGURATION_ERROR"


class DomainCompositionExecutionError(DomainCompositionError):
    """Raised when the composer encounters a controlled internal error.

    Only raised via explicit controlled paths, never from blind ``except Exception``.
    """

    code = "DOMAIN_COMPOSITION_EXECUTION_ERROR"


# ── Phase 10.9 – Cross-Domain Engine Errors ────────────────────────────────────


class CrossDomainError(DomainError):
    """Base error for Cross-Domain Engine operations (Phase 10.9)."""

    code = "CROSS_DOMAIN_ERROR"


class CrossDomainContractError(CrossDomainError, ValueError):
    """Raised when a Cross-Domain contract invariant is violated."""

    code = "CROSS_DOMAIN_CONTRACT_ERROR"


class CrossDomainSerializationError(CrossDomainError):
    """Raised when serialization or deserialization of Cross-Domain contracts fails."""

    code = "CROSS_DOMAIN_SERIALIZATION_ERROR"


class CrossDomainConfigurationError(CrossDomainError):
    """Raised when the engine is configured with invalid or incompatible settings."""

    code = "CROSS_DOMAIN_CONFIGURATION_ERROR"


class CrossDomainLimitError(CrossDomainError):
    """Raised when a limit configuration is invalid.

    Reaching a runtime limit is never an exception — it becomes a
    ``LIMIT_REACHED``/``PARTIAL`` result status. This error is reserved for
    invalid limit *configuration* (e.g. non-positive maximums).
    """

    code = "CROSS_DOMAIN_LIMIT_ERROR"


class CrossDomainPortError(CrossDomainError):
    """Raised when a port contract is violated (e.g. an unexpected return type)."""

    code = "CROSS_DOMAIN_PORT_ERROR"


class CrossDomainExecutionError(CrossDomainError):
    """Raised when the engine encounters a controlled internal error.

    Only raised via explicit controlled paths, never from blind
    ``except Exception``. Unexpected adapter errors propagate as-is.
    """

    code = "CROSS_DOMAIN_EXECUTION_ERROR"


# ── Phase 10.10 – Domain Resource Errors ───────────────────────────────────────


class DomainResourceError(DomainError):
    """Base error for Domain Resource operations (Phase 10.10)."""

    code = "DOMAIN_RESOURCE_ERROR"


class DomainResourceContractError(DomainResourceError, ValueError):
    """Raised when a Domain Resource contract invariant is violated."""

    code = "DOMAIN_RESOURCE_CONTRACT_ERROR"


class DomainResourceSerializationError(DomainResourceError):
    """Raised when serialization or deserialization of resource contracts fails."""

    code = "DOMAIN_RESOURCE_SERIALIZATION_ERROR"


class DomainResourceConfigurationError(DomainResourceError):
    """Raised when a resource component is configured with invalid settings."""

    code = "DOMAIN_RESOURCE_CONFIGURATION_ERROR"


class DomainResourceRegistryError(DomainResourceError):
    """Raised when a Domain Resource registry operation fails."""

    code = "DOMAIN_RESOURCE_REGISTRY_ERROR"


class DomainResourceResolutionError(DomainResourceError):
    """Raised when a Domain Resource resolution encounters a controlled internal error.

    Only raised via explicit controlled paths, never from blind ``except Exception``.
    """

    code = "DOMAIN_RESOURCE_RESOLUTION_ERROR"


class DomainResourceDerivationError(DomainResourceError):
    """Raised when a Domain Resource derivation invariant is violated."""

    code = "DOMAIN_RESOURCE_DERIVATION_ERROR"


# ── Phase 10.11 – Domain Profile Errors ────────────────────────────────────────


class DomainProfileError(DomainError):
    """Base error for Domain Profile operations (Phase 10.11)."""

    code = "DOMAIN_PROFILE_ERROR"


class DomainProfileContractError(DomainProfileError, ValueError):
    """Raised when a Domain Profile contract invariant is violated."""

    code = "DOMAIN_PROFILE_CONTRACT_ERROR"


class DomainProfileSerializationError(DomainProfileError):
    """Raised when serialization or deserialization of profile contracts fails."""

    code = "DOMAIN_PROFILE_SERIALIZATION_ERROR"


class DomainProfileConfigurationError(DomainProfileError):
    """Raised when a profile component is configured with invalid settings."""

    code = "DOMAIN_PROFILE_CONFIGURATION_ERROR"


class DomainProfileRegistryError(DomainProfileError):
    """Raised when a Domain Profile registry operation fails."""

    code = "DOMAIN_PROFILE_REGISTRY_ERROR"


class DomainProfileCompositionError(DomainProfileError):
    """Raised when Domain Profile composition encounters a controlled internal error."""

    code = "DOMAIN_PROFILE_COMPOSITION_ERROR"


class DomainProfileResolutionError(DomainProfileError):
    """Raised when Domain Profile resolution encounters a controlled internal error."""

    code = "DOMAIN_PROFILE_RESOLUTION_ERROR"


# ── Phase 10.12 – Domain Rule Errors ─────────────────────────────────────────


class DomainRuleError(DomainError):
    code = "DOMAIN_RULE_ERROR"


class DomainRuleContractError(DomainRuleError, ValueError):
    code = "DOMAIN_RULE_CONTRACT_ERROR"


class DomainRuleSerializationError(DomainRuleError, ValueError):
    code = "DOMAIN_RULE_SERIALIZATION_ERROR"


class DomainRuleConfigurationError(DomainRuleError):
    code = "DOMAIN_RULE_CONFIGURATION_ERROR"


class DomainRuleSelectionError(DomainRuleError):
    code = "DOMAIN_RULE_SELECTION_ERROR"


class DomainRuleExecutionError(DomainRuleError, RuntimeError):
    code = "DOMAIN_RULE_EXECUTION_ERROR"


# ── Phase 10.13 – Domain Operation Errors ───────────────────────────────────


class DomainOperationError(DomainError):
    code = "DOMAIN_OPERATION_ERROR"

    def to_dict(self) -> dict[str, Any]:
        def thaw(value: Any) -> Any:
            if isinstance(value, MappingProxyType):
                return {key: thaw(item) for key, item in value.items()}
            if isinstance(value, (tuple, frozenset)):
                return [thaw(item) for item in value]
            return value

        details = thaw(self.details)
        if self.field is not None and "field" not in details:
            details["field"] = self.field
        return {"code": self.code, "message": self.message, "details": details}


class DomainOperationContractError(DomainOperationError, ValueError):
    code = "DOMAIN_OPERATION_CONTRACT_ERROR"


class DomainOperationRegistryError(DomainOperationError):
    code = "DOMAIN_OPERATION_REGISTRY_ERROR"


class DomainOperationResolutionError(DomainOperationError):
    code = "DOMAIN_OPERATION_RESOLUTION_ERROR"


class DomainOperationUnavailableError(DomainOperationError):
    code = "DOMAIN_OPERATION_UNAVAILABLE_ERROR"


class DomainOperationPermissionDeniedError(DomainOperationError, PermissionError):
    code = "DOMAIN_OPERATION_PERMISSION_DENIED_ERROR"


class DomainOperationApprovalRequiredError(DomainOperationError):
    code = "DOMAIN_OPERATION_APPROVAL_REQUIRED_ERROR"


class DomainOperationValidationError(DomainOperationError):
    code = "DOMAIN_OPERATION_VALIDATION_ERROR"


class DomainOperationExecutionError(DomainOperationError, RuntimeError):
    code = "DOMAIN_OPERATION_EXECUTION_ERROR"


class DomainOperationRollbackError(DomainOperationError, RuntimeError):
    code = "DOMAIN_OPERATION_ROLLBACK_ERROR"


class DomainOperationCancellationError(DomainOperationError):
    code = "DOMAIN_OPERATION_CANCELLATION_ERROR"


class DomainOperationSerializationError(DomainOperationError, ValueError):
    code = "DOMAIN_OPERATION_SERIALIZATION_ERROR"


class DomainPermissionError(DomainError):
    code = "DOMAIN_PERMISSION_ERROR"


class DomainPermissionContractError(DomainPermissionError, ValueError):
    code = "DOMAIN_PERMISSION_CONTRACT_ERROR"


class DomainPermissionRegistryError(DomainPermissionError):
    code = "DOMAIN_PERMISSION_REGISTRY_ERROR"


class DomainPermissionResolutionError(DomainPermissionError):
    code = "DOMAIN_PERMISSION_RESOLUTION_ERROR"


class DomainPermissionEvaluationError(DomainPermissionError):
    code = "DOMAIN_PERMISSION_EVALUATION_ERROR"


class DomainPermissionDeniedError(DomainPermissionError):
    code = "DOMAIN_PERMISSION_DENIED_ERROR"


class DomainPermissionApprovalRequiredError(DomainPermissionError):
    code = "DOMAIN_PERMISSION_APPROVAL_REQUIRED_ERROR"


class DomainPermissionConflictError(DomainPermissionError):
    code = "DOMAIN_PERMISSION_CONFLICT_ERROR"


class DomainPermissionCrossDomainError(DomainPermissionError):
    code = "DOMAIN_PERMISSION_CROSS_DOMAIN_ERROR"


class DomainPermissionSerializationError(DomainPermissionError, ValueError):
    code = "DOMAIN_PERMISSION_SERIALIZATION_ERROR"


__all__ = [
    "CrossDomainConfigurationError",
    "CrossDomainContractError",
    "CrossDomainError",
    "CrossDomainExecutionError",
    "CrossDomainLimitError",
    "CrossDomainPortError",
    "CrossDomainSerializationError",
    "DomainCandidateInvalid",
    "DomainCapabilityConflict",
    "DomainChecksumMismatch",
    "DomainCompositionConfigurationError",
    "DomainCompositionContractError",
    "DomainCompositionError",
    "DomainCompositionExecutionError",
    "DomainCompositionSerializationError",
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
    "DomainOperationApprovalRequiredError",
    "DomainOperationCancellationError",
    "DomainOperationContractError",
    "DomainOperationError",
    "DomainOperationExecutionError",
    "DomainOperationPermissionDeniedError",
    "DomainOperationRegistryError",
    "DomainOperationResolutionError",
    "DomainOperationRollbackError",
    "DomainOperationSerializationError",
    "DomainOperationUnavailableError",
    "DomainOperationValidationError",
    "DomainPathEscape",
    "DomainPermissionApprovalRequiredError",
    "DomainPermissionConflictError",
    "DomainPermissionContractError",
    "DomainPermissionCrossDomainError",
    "DomainPermissionDeniedError",
    "DomainPermissionError",
    "DomainPermissionEvaluationError",
    "DomainPermissionRegistryError",
    "DomainPermissionResolutionError",
    "DomainPermissionSerializationError",
    "DomainProfileCompositionError",
    "DomainProfileConfigurationError",
    "DomainProfileContractError",
    "DomainProfileError",
    "DomainProfileRegistryError",
    "DomainProfileResolutionError",
    "DomainProfileSerializationError",
    "DomainRegistryConflict",
    "DomainRegistryError",
    "DomainRegistryNotFound",
    "DomainRegistryStateError",
    "DomainRegistryValidationError",
    "DomainRegistryVersionError",
    "DomainReloadFailed",
    "DomainReloadRollbackFailed",
    "DomainResolutionAmbiguityError",
    "DomainResolutionBlockedError",
    "DomainResolutionContextInvalid",
    "DomainResolutionContractError",
    "DomainResolutionError",
    "DomainResolutionLimitExceeded",
    "DomainResolutionPolicyError",
    "DomainResolutionSerializationError",
    "DomainResolutionSnapshotError",
    "DomainResolutionUnsupportedError",
    "DomainResolverConfigurationError",
    "DomainResolverError",
    "DomainResolverExecutionError",
    "DomainResourceConfigurationError",
    "DomainResourceContractError",
    "DomainResourceDerivationError",
    "DomainResourceError",
    "DomainResourceRegistryError",
    "DomainResourceResolutionError",
    "DomainResourceSerializationError",
    "DomainRollbackFailed",
    "DomainRuleConfigurationError",
    "DomainRuleContractError",
    "DomainRuleError",
    "DomainRuleExecutionError",
    "DomainRuleSelectionError",
    "DomainRuleSerializationError",
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
