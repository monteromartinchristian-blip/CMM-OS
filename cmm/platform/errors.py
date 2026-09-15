"""Phase 11.1 — typed platform-composition errors.

Every error carries a structured :class:`~cmm.platform.contracts.ErrorResult`.
Structured details are restricted to identifiers and reason codes: arbitrary
runtime objects, exception instances, secrets, credentials, provider payloads,
prompts, tracebacks and hidden reasoning never reach the public error value.

These types describe **platform composition** failures only.  Canonical
subsystems keep their own authoritative error types internally.
"""

from __future__ import annotations

from collections.abc import Mapping

from cmm.platform.contracts import ErrorResult

COMPOSITION_CATEGORY = "composition"
CONFIGURATION_CATEGORY = "configuration"
LIFECYCLE_CATEGORY = "lifecycle"


class PlatformCompositionError(Exception):
    """Base class for typed platform composition failures.

    The exception message stays short and safe; the structured, inspectable
    detail lives in :attr:`result`.
    """

    default_code = "PLATFORM_COMPOSITION_ERROR"
    default_category = COMPOSITION_CATEGORY

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        category: str | None = None,
        details: Mapping[str, str] | None = None,
    ) -> None:
        self._result = ErrorResult(
            code=type(self).default_code if code is None else code,
            message=message,
            category=type(self).default_category if category is None else category,
            details={} if details is None else details,
        )
        super().__init__(self._result.message)

    @property
    def result(self) -> ErrorResult:
        """Return the safe structured error value."""

        return self._result


class DuplicateServiceError(PlatformCompositionError):
    """A service ID was registered twice without an explicit replacement."""

    default_code = "DUPLICATE_SERVICE_ID"


class MissingDependencyError(PlatformCompositionError):
    """A declared dependency does not resolve to a registered service."""

    default_code = "MISSING_DEPENDENCY"


class IncompatibleContractError(PlatformCompositionError):
    """A contract boundary is incompatible with the required contract."""

    default_code = "INCOMPATIBLE_CONTRACT"


class CircularDependencyError(PlatformCompositionError):
    """The platform service graph contains a dependency cycle."""

    default_code = "CIRCULAR_DEPENDENCY"


class DuplicateAuthorityError(PlatformCompositionError):
    """Two distinct service IDs claim the same platform authority."""

    default_code = "DUPLICATE_AUTHORITY"


class InvalidReplacementError(PlatformCompositionError):
    """An explicit replacement violates the binding or contract rules."""

    default_code = "INVALID_REPLACEMENT"


class InvalidConfigurationError(PlatformCompositionError):
    """The composition configuration is malformed or impossible."""

    default_code = "INVALID_CONFIGURATION"
    default_category = CONFIGURATION_CATEGORY


class ContainerNotReadyError(PlatformCompositionError):
    """The composition root is not ready for the requested operation."""

    default_code = "CONTAINER_NOT_READY"
    default_category = LIFECYCLE_CATEGORY


class FrozenServiceRegistryError(PlatformCompositionError):
    """A frozen registry rejected a mutation attempt."""

    default_code = "SERVICE_REGISTRY_FROZEN"
    default_category = LIFECYCLE_CATEGORY


__all__ = [
    "CircularDependencyError",
    "ContainerNotReadyError",
    "DuplicateAuthorityError",
    "DuplicateServiceError",
    "FrozenServiceRegistryError",
    "IncompatibleContractError",
    "InvalidConfigurationError",
    "InvalidReplacementError",
    "MissingDependencyError",
    "PlatformCompositionError",
]
