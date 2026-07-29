"""Phase 9.21 – Agent Runtime API Enumerations.

Enums for operations, status codes, error codes, resource kinds, and sort direction
used by the Agent Runtime API surface.
"""

from __future__ import annotations

from enum import Enum


class AgentRuntimeApiOperation(str, Enum):
    """Every operation exposed through the Agent Runtime API."""

    GOAL_CREATE = "goal.create"
    GOAL_GET = "goal.get"
    GOAL_LIST = "goal.list"
    GOAL_UPDATE = "goal.update"
    GOAL_PRIORITIZE = "goal.prioritize"
    GOAL_PAUSE = "goal.pause"
    GOAL_RESUME = "goal.resume"
    GOAL_CANCEL = "goal.cancel"
    RUN_START = "run.start"
    RUN_GET = "run.get"
    RUN_LIST = "run.list"
    RUN_PAUSE = "run.pause"
    RUN_RESUME = "run.resume"
    RUN_CANCEL = "run.cancel"
    APPROVAL_LIST = "approval.list"
    APPROVAL_GET = "approval.get"
    APPROVAL_APPROVE = "approval.approve"
    APPROVAL_REJECT = "approval.reject"
    BUDGET_GET = "budget.get"
    BUDGET_RESERVE = "budget.reserve"
    BUDGET_RELEASE = "budget.release"
    TRACE_GET = "trace.get"
    TRACE_LIST = "trace.list"
    TRACE_VERIFY = "trace.verify"
    TRACE_EXPORT = "trace.export"
    EVENT_PUBLISH = "event.publish"
    EVENT_LIST = "event.list"
    EVENT_REPLAY = "event.replay"
    DEAD_LETTER_LIST = "dead_letter.list"
    DEAD_LETTER_REPLAY = "dead_letter.replay"
    RUNTIME_HEALTH = "runtime.health"
    RUNTIME_STATS = "runtime.stats"

    @classmethod
    def from_string(cls, value: str) -> AgentRuntimeApiOperation:
        """Lookup operation by string value; raises ValueError if unknown."""
        for member in cls:
            if member.value == value:
                return member
        raise AgentRuntimeApiUnsupportedOperationError(f"Unknown operation: {value}")


class AgentRuntimeApiStatus(str, Enum):
    """API response status."""

    SUCCESS = "success"
    ERROR = "error"
    PARTIAL = "partial"


class AgentRuntimeApiErrorCode(str, Enum):
    """Structured error codes for the Agent Runtime API."""

    CONTRACT_ERROR = "CONTRACT_ERROR"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    NOT_FOUND = "NOT_FOUND"
    CONFLICT = "CONFLICT"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    POLICY_DENIED = "POLICY_DENIED"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
    BUDGET_EXCEEDED = "BUDGET_EXCEEDED"
    STATE_ERROR = "STATE_ERROR"
    SERIALIZATION_ERROR = "SERIALIZATION_ERROR"
    UNSUPPORTED_OPERATION = "UNSUPPORTED_OPERATION"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    IDEMPOTENCY_CONFLICT = "IDEMPOTENCY_CONFLICT"


class AgentRuntimeApiResourceKind(str, Enum):
    """Resource kinds addressable by the API."""

    GOAL = "goal"
    AGENT_RUN = "agent_run"
    APPROVAL = "approval"
    BUDGET = "budget"
    TRACE = "trace"
    EVENT = "event"
    DEAD_LETTER = "dead_letter"
    RUNTIME = "runtime"


class AgentRuntimeApiSortDirection(str, Enum):
    """Sort direction for API queries."""

    ASC = "asc"
    DESC = "desc"


# Prevent circular imports -- placed here at the bottom intentionally
class AgentRuntimeApiUnsupportedOperationError(ValueError):
    """Raised when an unknown operation string is requested."""
