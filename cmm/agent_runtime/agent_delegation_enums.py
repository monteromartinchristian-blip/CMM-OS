"""Phase 9.24 Agent Delegation Enums.

Immutable enumerations for the Agent Delegation subsystem.
"""

from __future__ import annotations

from enum import Enum


class DelegationStatus(str, Enum):
    """Lifecycle states of a delegation between agents."""

    PROPOSED = "proposed"
    ACCEPTED = "accepted"
    ACTIVE = "active"
    WAITING = "waiting"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    EXPIRED = "expired"

    @property
    def is_terminal(self) -> bool:
        """Return True if this status represents a terminal state."""
        return self in {
            DelegationStatus.COMPLETED,
            DelegationStatus.FAILED,
            DelegationStatus.CANCELLED,
            DelegationStatus.REJECTED,
            DelegationStatus.EXPIRED,
        }

    @property
    def is_active(self) -> bool:
        """Return True if the delegation is actively being processed."""
        return self in {
            DelegationStatus.ACCEPTED,
            DelegationStatus.ACTIVE,
            DelegationStatus.WAITING,
        }


class DelegationErrorCode(str, Enum):
    """Stable error codes for delegation failures."""

    SOURCE_AGENT_NOT_FOUND = "SOURCE_AGENT_NOT_FOUND"
    TARGET_AGENT_NOT_FOUND = "TARGET_AGENT_NOT_FOUND"
    PARENT_GOAL_NOT_FOUND = "PARENT_GOAL_NOT_FOUND"
    AGENTS_INCOMPATIBLE = "AGENTS_INCOMPATIBLE"
    TARGET_AGENT_UNSUPPORTED_GOAL = "TARGET_AGENT_UNSUPPORTED_GOAL"
    INSUFFICIENT_PERMISSIONS = "INSUFFICIENT_PERMISSIONS"
    POLICY_DENIED = "POLICY_DENIED"
    MAX_DEPTH_EXCEEDED = "MAX_DEPTH_EXCEEDED"
    CYCLE_DETECTED = "CYCLE_DETECTED"
    DUPLICATE_DELEGATION = "DUPLICATE_DELEGATION"
    PARENT_GOAL_TERMINAL = "PARENT_GOAL_TERMINAL"
    CHILD_GOAL_INCOMPATIBLE = "CHILD_GOAL_INCOMPATIBLE"
    AUTONOMY_ESCALATION = "AUTONOMY_ESCALATION"
    PERMISSION_ESCALATION = "PERMISSION_ESCALATION"
    DELEGATION_NOT_FOUND = "DELEGATION_NOT_FOUND"
    INVALID_STATE_TRANSITION = "INVALID_STATE_TRANSITION"
    DELEGATION_EXPIRED = "DELEGATION_EXPIRED"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class DelegationEventType(str, Enum):
    """Event types emitted during delegation lifecycle."""

    PROPOSED = "agent.delegation.proposed"
    ACCEPTED = "agent.delegation.accepted"
    REJECTED = "agent.delegation.rejected"
    STARTED = "agent.delegation.started"
    WAITING = "agent.delegation.waiting"
    COMPLETED = "agent.delegation.completed"
    FAILED = "agent.delegation.failed"
    CANCELLED = "agent.delegation.cancelled"
    RESULT_RECEIVED = "agent.delegation.result_received"


__all__ = [
    "DelegationErrorCode",
    "DelegationEventType",
    "DelegationStatus",
]
