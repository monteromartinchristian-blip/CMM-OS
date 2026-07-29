"""Phase 9.24 Agent Delegation Errors.

Error hierarchy for the Agent Delegation subsystem.
"""

from __future__ import annotations

from typing import Any

from cmm.agent_runtime.agent_delegation_enums import DelegationErrorCode
from cmm.agent_runtime.errors import AgentRuntimeError


class AgentDelegationError(AgentRuntimeError):
    """Base exception for all delegation errors."""

    error_code: DelegationErrorCode = DelegationErrorCode.INTERNAL_ERROR

    def __init__(
        self,
        message: str,
        details: dict[str, Any] | None = None,
        *,
        delegation_id: str | None = None,
    ) -> None:
        super().__init__(message)
        self.details = details or {}
        self.delegation_id = delegation_id


class AgentDelegationValidationError(AgentDelegationError, ValueError):
    """Raised when delegation contract validation fails."""

    error_code = DelegationErrorCode.VALIDATION_ERROR


class AgentDelegationNotFoundError(AgentDelegationError, KeyError):
    """Raised when a delegation is not found."""

    error_code = DelegationErrorCode.DELEGATION_NOT_FOUND


class AgentDelegationSourceAgentNotFoundError(AgentDelegationError, KeyError):
    """Raised when the source agent does not exist."""

    error_code = DelegationErrorCode.SOURCE_AGENT_NOT_FOUND


class AgentDelegationTargetAgentNotFoundError(AgentDelegationError, KeyError):
    """Raised when the target agent does not exist."""

    error_code = DelegationErrorCode.TARGET_AGENT_NOT_FOUND


class AgentDelegationParentGoalNotFoundError(AgentDelegationError, KeyError):
    """Raised when the parent goal does not exist."""

    error_code = DelegationErrorCode.PARENT_GOAL_NOT_FOUND


class AgentDelegationAgentsIncompatibleError(AgentDelegationError, ValueError):
    """Raised when source and target agents are incompatible."""

    error_code = DelegationErrorCode.AGENTS_INCOMPATIBLE


class AgentDelegationTargetUnsupportedGoalError(AgentDelegationError, ValueError):
    """Raised when the target agent does not support the goal type."""

    error_code = DelegationErrorCode.TARGET_AGENT_UNSUPPORTED_GOAL


class AgentDelegationInsufficientPermissionsError(
    AgentDelegationError, PermissionError
):
    """Raised when permissions are insufficient for delegation."""

    error_code = DelegationErrorCode.INSUFFICIENT_PERMISSIONS


class AgentDelegationPolicyDeniedError(AgentDelegationError, PermissionError):
    """Raised when a policy denies the delegation."""

    error_code = DelegationErrorCode.POLICY_DENIED


class AgentDelegationMaxDepthExceededError(AgentDelegationError, ValueError):
    """Raised when maximum delegation depth is exceeded."""

    error_code = DelegationErrorCode.MAX_DEPTH_EXCEEDED


class AgentDelegationCycleDetectedError(AgentDelegationError, ValueError):
    """Raised when a delegation cycle is detected."""

    error_code = DelegationErrorCode.CYCLE_DETECTED


class AgentDelegationDuplicateError(AgentDelegationError, ValueError):
    """Raised when a duplicate delegation is detected."""

    error_code = DelegationErrorCode.DUPLICATE_DELEGATION


class AgentDelegationParentGoalTerminalError(AgentDelegationError, ValueError):
    """Raised when the parent goal is in a terminal state."""

    error_code = DelegationErrorCode.PARENT_GOAL_TERMINAL


class AgentDelegationChildGoalIncompatibleError(AgentDelegationError, ValueError):
    """Raised when the child goal is incompatible with parent constraints."""

    error_code = DelegationErrorCode.CHILD_GOAL_INCOMPATIBLE


class AgentDelegationAutonomyEscalationError(AgentDelegationError, ValueError):
    """Raised when delegation attempts to escalate autonomy."""

    error_code = DelegationErrorCode.AUTONOMY_ESCALATION


class AgentDelegationPermissionEscalationError(AgentDelegationError, ValueError):
    """Raised when delegation attempts to escalate permissions."""

    error_code = DelegationErrorCode.PERMISSION_ESCALATION


class AgentDelegationInvalidStateTransitionError(AgentDelegationError, ValueError):
    """Raised when an invalid state transition is attempted."""

    error_code = DelegationErrorCode.INVALID_STATE_TRANSITION


class AgentDelegationExpiredError(AgentDelegationError, ValueError):
    """Raised when a delegation has expired."""

    error_code = DelegationErrorCode.DELEGATION_EXPIRED


__all__ = [
    "AgentDelegationAgentsIncompatibleError",
    "AgentDelegationAutonomyEscalationError",
    "AgentDelegationChildGoalIncompatibleError",
    "AgentDelegationCycleDetectedError",
    "AgentDelegationDuplicateError",
    "AgentDelegationError",
    "AgentDelegationExpiredError",
    "AgentDelegationInsufficientPermissionsError",
    "AgentDelegationInvalidStateTransitionError",
    "AgentDelegationMaxDepthExceededError",
    "AgentDelegationNotFoundError",
    "AgentDelegationParentGoalNotFoundError",
    "AgentDelegationParentGoalTerminalError",
    "AgentDelegationPermissionEscalationError",
    "AgentDelegationPolicyDeniedError",
    "AgentDelegationSourceAgentNotFoundError",
    "AgentDelegationTargetAgentNotFoundError",
    "AgentDelegationTargetUnsupportedGoalError",
    "AgentDelegationValidationError",
]
