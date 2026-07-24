"""Application API error domain for CMM OS Validation (Phase 7.12)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .exit_codes import ValidationExitCode


@dataclass(slots=True)
class ValidationApplicationError(Exception):
    """Base application exception for validation interface operations."""

    code: str
    message: str
    exit_code: int = ValidationExitCode.INTERNAL_ERROR
    details: dict[str, Any] = field(default_factory=dict)

    def serialize(self) -> dict[str, Any]:
        """Return structured, JSON-serializable error object."""
        return {
            "code": self.code,
            "message": self.message,
            "details": dict(self.details or {}),
        }

    def __str__(self) -> str:
        return f"[{self.code}] {self.message}"


class ValidationNotFoundError(ValidationApplicationError):
    """Raised when a requested validation record or artifact is not found."""

    def __init__(self, validation_id: str, message: str | None = None) -> None:
        super().__init__(
            code="validation_not_found",
            message=message
            or f"Validation execution record '{validation_id}' not found.",
            exit_code=ValidationExitCode.NOT_FOUND,
            details={"validation_id": validation_id},
        )


class ValidationInvalidRequestError(ValidationApplicationError):
    """Raised when request arguments or parameters fail validation."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(
            code="validation_invalid_request",
            message=message,
            exit_code=ValidationExitCode.INVALID_USAGE,
            details=details or {},
        )


class ValidationPolicyNotFoundError(ValidationApplicationError):
    """Raised when a requested policy does not exist in the policy registry."""

    def __init__(self, policy_name: str) -> None:
        super().__init__(
            code="validation_policy_not_found",
            message=f"Validation policy '{policy_name}' was not found.",
            exit_code=ValidationExitCode.CONFIGURATION_ERROR,
            details={"policy_name": policy_name},
        )


class ValidationStepNotFoundError(ValidationApplicationError):
    """Raised when a requested step is not registered or allowed."""

    def __init__(self, step_name: str) -> None:
        super().__init__(
            code="validation_step_not_found",
            message=f"Validation step '{step_name}' is not registered or allowed.",
            exit_code=ValidationExitCode.CONFIGURATION_ERROR,
            details={"step_name": step_name},
        )


class ValidationCancelledError(ValidationApplicationError):
    """Raised when a validation execution was cancelled."""

    def __init__(self, validation_id: str) -> None:
        super().__init__(
            code="validation_cancelled",
            message=f"Validation execution '{validation_id}' was cancelled.",
            exit_code=ValidationExitCode.CANCELLED,
            details={"validation_id": validation_id},
        )


class ValidationConflictError(ValidationApplicationError):
    """Raised when an operation conflicts with existing execution state or request_id."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(
            code="validation_conflict",
            message=message,
            exit_code=ValidationExitCode.INVALID_USAGE,
            details=details or {},
        )


class ValidationPersistenceApplicationError(ValidationApplicationError):
    """Raised when persistence operations fail at the application layer."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(
            code="validation_persistence_error",
            message=message,
            exit_code=ValidationExitCode.INTERNAL_ERROR,
            details=details or {},
        )


class ValidationInternalApplicationError(ValidationApplicationError):
    """Raised when an unexpected internal error occurs."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(
            code="validation_internal_error",
            message=message,
            exit_code=ValidationExitCode.INTERNAL_ERROR,
            details=details or {},
        )


__all__ = [
    "ValidationApplicationError",
    "ValidationCancelledError",
    "ValidationConflictError",
    "ValidationInternalApplicationError",
    "ValidationInvalidRequestError",
    "ValidationNotFoundError",
    "ValidationPersistenceApplicationError",
    "ValidationPolicyNotFoundError",
    "ValidationStepNotFoundError",
]
