"""Phase 9.25 – Agent Security, Permissions, and Isolation Errors.

Defines the error hierarchy for the security authorization boundary.
All errors expose a stable ``error_code`` for callers and audits.
"""

from __future__ import annotations

from typing import Any

from cmm.agent_runtime.agent_security_enums import SecurityErrorCode
from cmm.agent_runtime.errors import (
    AgentRuntimeError,
    InvalidAgentContractError,
)


class AgentSecurityError(AgentRuntimeError):
    """Base error for all Agent Security operations."""

    error_code: SecurityErrorCode = SecurityErrorCode.INTERNAL_ERROR

    def __init__(
        self,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.details = dict(details or {})


class InvalidSecurityContractError(AgentSecurityError, InvalidAgentContractError):
    """Raised when a security contract is invalid, malformed, or violates invariants."""

    error_code = SecurityErrorCode.INVALID_CONTRACT


class PermissionEvaluationError(AgentSecurityError, RuntimeError):
    """Raised when permission evaluation fails unexpectedly."""

    error_code = SecurityErrorCode.EVALUATION_ERROR


class PermissionDeniedError(AgentSecurityError, PermissionError):
    """Raised when an operation is denied by security policy."""

    error_code = SecurityErrorCode.PERMISSION_DENIED


class ApprovalRequiredError(PermissionDeniedError):
    """Raised when an operation requires human approval before proceeding."""

    error_code = SecurityErrorCode.APPROVAL_REQUIRED


class ApprovalNotFoundError(AgentSecurityError, KeyError):
    """Raised when a required approval is not found."""

    error_code = SecurityErrorCode.APPROVAL_NOT_FOUND


class ApprovalNotAuthorizedError(AgentSecurityError, PermissionError):
    """Raised when an approval is not authorized for the requesting actor."""

    error_code = SecurityErrorCode.APPROVAL_NOT_AUTHORIZED


class SecurityApprovalExpiredError(AgentSecurityError, TimeoutError):
    """Raised when an approval attached to a security decision has expired."""

    error_code = SecurityErrorCode.APPROVAL_EXPIRED


class DuplicateApprovalError(AgentSecurityError, ValueError):
    """Raised when attempting to create a duplicate approval."""

    error_code = SecurityErrorCode.DUPLICATE_APPROVAL


class InvalidPermissionContextError(InvalidSecurityContractError):
    """Raised when a permission context contract is invalid."""

    error_code = SecurityErrorCode.INVALID_PERMISSION_CONTEXT


class PermissionContextExpiredError(PermissionDeniedError):
    """Raised when a permission context has expired."""

    error_code = SecurityErrorCode.PERMISSION_CONTEXT_EXPIRED


class PermissionContextNotFoundError(AgentSecurityError, KeyError):
    """Raised when a requested permission context is not found."""

    error_code = SecurityErrorCode.PERMISSION_CONTEXT_NOT_FOUND


class AutonomyLevelExceededError(PermissionDeniedError):
    """Raised when required autonomy exceeds the allowed maximum."""

    error_code = SecurityErrorCode.AUTONOMY_LEVEL_EXCEEDED


class SensitivityLevelNotAllowedError(PermissionDeniedError):
    """Raised when a sensitivity level is not in the allowed list."""

    error_code = SecurityErrorCode.SENSITIVITY_LEVEL_NOT_ALLOWED


class ResourceNotAuthorizedError(PermissionDeniedError):
    """Raised when a resource is not in the allowed list."""

    error_code = SecurityErrorCode.RESOURCE_NOT_AUTHORIZED


class OperationNotPermittedError(PermissionDeniedError):
    """Raised when an operation is not in the allowlist."""

    error_code = SecurityErrorCode.OPERATION_NOT_PERMITTED


class ExternalAccessNotAllowedError(PermissionDeniedError):
    """Raised when external access is attempted without permission."""

    error_code = SecurityErrorCode.EXTERNAL_ACCESS_NOT_ALLOWED


class ExternalModelNotAllowedError(PermissionDeniedError):
    """Raised when external model usage is attempted without permission."""

    error_code = SecurityErrorCode.EXTERNAL_MODEL_NOT_ALLOWED


class MemoryWriteNotAllowedError(PermissionDeniedError):
    """Raised when memory write is attempted without permission."""

    error_code = SecurityErrorCode.MEMORY_WRITE_NOT_ALLOWED


class GoalCreationNotAllowedError(PermissionDeniedError):
    """Raised when goal creation is attempted without permission."""

    error_code = SecurityErrorCode.GOAL_CREATION_NOT_ALLOWED


class DelegationNotAllowedError(PermissionDeniedError):
    """Raised when delegation is attempted without permission."""

    error_code = SecurityErrorCode.DELEGATION_NOT_ALLOWED


class PublicationNotAllowedError(PermissionDeniedError):
    """Raised when publication is attempted without permission."""

    error_code = SecurityErrorCode.PUBLICATION_NOT_ALLOWED


class CommunicationNotAllowedError(PermissionDeniedError):
    """Raised when communication is attempted without permission."""

    error_code = SecurityErrorCode.COMMUNICATION_NOT_ALLOWED


class DestructiveActionNotAllowedError(PermissionDeniedError):
    """Raised when a destructive action is attempted without explicit permission."""

    error_code = SecurityErrorCode.DESTRUCTIVE_ACTION_NOT_ALLOWED


class PermissionElevationNotAllowedError(PermissionDeniedError):
    """Raised when permission elevation is attempted without authorization."""

    error_code = SecurityErrorCode.PERMISSION_ELEVATION_NOT_ALLOWED


class PromptInjectionDetectedError(AgentSecurityError, ValueError):
    """Raised when prompt injection is detected in untrusted content."""

    error_code = SecurityErrorCode.PROMPT_INJECTION_DETECTED


class PromptInjectionBlockedError(PromptInjectionDetectedError):
    """Raised when prompt injection causes content to be blocked."""

    error_code = SecurityErrorCode.PROMPT_INJECTION_BLOCKED


class ExternalActionNotAllowedError(PermissionDeniedError):
    """Raised when an external action is attempted without authorization."""

    error_code = SecurityErrorCode.EXTERNAL_ACTION_NOT_ALLOWED


class ExternalActionNotRegisteredError(AgentSecurityError, ValueError):
    """Raised when an external action category is not registered."""

    error_code = SecurityErrorCode.EXTERNAL_ACTION_NOT_REGISTERED


class ExternalActionCheckpointRequiredError(PermissionDeniedError):
    """Raised when an external action requires a checkpoint."""

    error_code = SecurityErrorCode.EXTERNAL_ACTION_CHECKPOINT_REQUIRED


class DelegationPermissionEscalationError(PermissionDeniedError):
    """Raised when a delegated context attempts to exceed source permissions."""

    error_code = SecurityErrorCode.PERMISSION_DENIED


class KillSwitchError(AgentSecurityError):
    """Base exception for Kill Switch operations."""

    error_code = SecurityErrorCode.INTERNAL_ERROR


class KillSwitchActivationError(KillSwitchError, RuntimeError):
    """Raised when kill switch activation fails."""

    error_code = SecurityErrorCode.KILL_SWITCH_ACTIVATION_FAILED


class KillSwitchReleaseError(KillSwitchError, PermissionError):
    """Raised when kill switch release is not authorized."""

    error_code = SecurityErrorCode.KILL_SWITCH_RELEASE_UNAUTHORIZED


class KillSwitchAlreadyActiveError(KillSwitchError, ValueError):
    """Raised when attempting to activate an already active kill switch."""

    error_code = SecurityErrorCode.KILL_SWITCH_ALREADY_ACTIVE


class KillSwitchNotActiveError(KillSwitchError, ValueError):
    """Raised when attempting to release a non-active kill switch."""

    error_code = SecurityErrorCode.KILL_SWITCH_NOT_ACTIVE


__all__ = [
    "AgentSecurityError",
    "ApprovalNotAuthorizedError",
    "ApprovalNotFoundError",
    "ApprovalRequiredError",
    "AutonomyLevelExceededError",
    "CommunicationNotAllowedError",
    "DelegationNotAllowedError",
    "DelegationPermissionEscalationError",
    "DestructiveActionNotAllowedError",
    "DuplicateApprovalError",
    "ExternalAccessNotAllowedError",
    "ExternalActionCheckpointRequiredError",
    "ExternalActionNotAllowedError",
    "ExternalActionNotRegisteredError",
    "ExternalModelNotAllowedError",
    "GoalCreationNotAllowedError",
    "InvalidPermissionContextError",
    "InvalidSecurityContractError",
    "KillSwitchActivationError",
    "KillSwitchAlreadyActiveError",
    "KillSwitchError",
    "KillSwitchNotActiveError",
    "KillSwitchReleaseError",
    "MemoryWriteNotAllowedError",
    "OperationNotPermittedError",
    "PermissionContextExpiredError",
    "PermissionContextNotFoundError",
    "PermissionDeniedError",
    "PermissionElevationNotAllowedError",
    "PermissionEvaluationError",
    "PromptInjectionBlockedError",
    "PromptInjectionDetectedError",
    "PublicationNotAllowedError",
    "ResourceNotAuthorizedError",
    "SecurityApprovalExpiredError",
    "SensitivityLevelNotAllowedError",
]
