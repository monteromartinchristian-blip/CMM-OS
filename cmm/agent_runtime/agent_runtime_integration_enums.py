"""Application-level lifecycle enumerations for Agent Runtime integration."""

from __future__ import annotations

from enum import Enum
from types import MappingProxyType


class IntegrationExecutionState(str, Enum):
    """Lifecycle of one integrated Agent Runtime execution."""

    CREATED = "created"
    VALIDATING = "validating"
    AUTHORIZED = "authorized"
    PLANNING = "planning"
    WAITING_APPROVAL = "waiting_approval"
    SCHEDULED = "scheduled"
    RUNNING = "running"
    WAITING = "waiting"
    DELEGATING = "delegating"
    RECOVERING = "recovering"
    COMPLETED = "completed"
    PARTIALLY_COMPLETED = "partially_completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    DENIED = "denied"
    TIMED_OUT = "timed_out"
    KILL_SWITCH_BLOCKED = "kill_switch_blocked"


class IntegrationFailureMode(str, Enum):
    """Criticality policy applied to an integration action."""

    MANDATORY_FAIL_CLOSED = "mandatory_fail_closed"
    MANDATORY_WITH_COMPENSATION = "mandatory_with_compensation"
    BEST_EFFORT = "best_effort"


class IntegrationCompensationStatus(str, Enum):
    """Durable execution status of a registered compensation action."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


TERMINAL_INTEGRATION_STATES = frozenset(
    {
        IntegrationExecutionState.COMPLETED,
        IntegrationExecutionState.PARTIALLY_COMPLETED,
        IntegrationExecutionState.FAILED,
        IntegrationExecutionState.CANCELLED,
        IntegrationExecutionState.DENIED,
        IntegrationExecutionState.TIMED_OUT,
    }
)

RESULT_SNAPSHOT_STATES = TERMINAL_INTEGRATION_STATES | frozenset(
    {
        IntegrationExecutionState.WAITING_APPROVAL,
        IntegrationExecutionState.WAITING,
        IntegrationExecutionState.KILL_SWITCH_BLOCKED,
    }
)


_CANCELLED = {IntegrationExecutionState.CANCELLED}

ALLOWED_INTEGRATION_TRANSITIONS = MappingProxyType(
    {
        IntegrationExecutionState.CREATED: frozenset(
            {IntegrationExecutionState.VALIDATING, *_CANCELLED}
        ),
        IntegrationExecutionState.VALIDATING: frozenset(
            {
                IntegrationExecutionState.AUTHORIZED,
                IntegrationExecutionState.DENIED,
                IntegrationExecutionState.FAILED,
                IntegrationExecutionState.TIMED_OUT,
                IntegrationExecutionState.KILL_SWITCH_BLOCKED,
                *_CANCELLED,
            }
        ),
        IntegrationExecutionState.AUTHORIZED: frozenset(
            {
                IntegrationExecutionState.PLANNING,
                IntegrationExecutionState.WAITING_APPROVAL,
                IntegrationExecutionState.SCHEDULED,
                IntegrationExecutionState.RUNNING,
                IntegrationExecutionState.DENIED,
                IntegrationExecutionState.TIMED_OUT,
                IntegrationExecutionState.KILL_SWITCH_BLOCKED,
                *_CANCELLED,
            }
        ),
        IntegrationExecutionState.PLANNING: frozenset(
            {
                IntegrationExecutionState.WAITING_APPROVAL,
                IntegrationExecutionState.SCHEDULED,
                IntegrationExecutionState.RUNNING,
                IntegrationExecutionState.FAILED,
                IntegrationExecutionState.TIMED_OUT,
                IntegrationExecutionState.KILL_SWITCH_BLOCKED,
                *_CANCELLED,
            }
        ),
        IntegrationExecutionState.WAITING_APPROVAL: frozenset(
            {
                IntegrationExecutionState.AUTHORIZED,
                IntegrationExecutionState.PLANNING,
                IntegrationExecutionState.SCHEDULED,
                IntegrationExecutionState.RUNNING,
                IntegrationExecutionState.DENIED,
                IntegrationExecutionState.FAILED,
                IntegrationExecutionState.TIMED_OUT,
                IntegrationExecutionState.KILL_SWITCH_BLOCKED,
                *_CANCELLED,
            }
        ),
        IntegrationExecutionState.SCHEDULED: frozenset(
            {
                IntegrationExecutionState.RUNNING,
                IntegrationExecutionState.WAITING,
                IntegrationExecutionState.WAITING_APPROVAL,
                IntegrationExecutionState.FAILED,
                IntegrationExecutionState.TIMED_OUT,
                IntegrationExecutionState.KILL_SWITCH_BLOCKED,
                *_CANCELLED,
            }
        ),
        IntegrationExecutionState.RUNNING: frozenset(
            {
                IntegrationExecutionState.WAITING,
                IntegrationExecutionState.WAITING_APPROVAL,
                IntegrationExecutionState.DELEGATING,
                IntegrationExecutionState.RECOVERING,
                IntegrationExecutionState.COMPLETED,
                IntegrationExecutionState.PARTIALLY_COMPLETED,
                IntegrationExecutionState.FAILED,
                IntegrationExecutionState.TIMED_OUT,
                IntegrationExecutionState.KILL_SWITCH_BLOCKED,
                *_CANCELLED,
            }
        ),
        IntegrationExecutionState.WAITING: frozenset(
            {
                IntegrationExecutionState.AUTHORIZED,
                IntegrationExecutionState.PLANNING,
                IntegrationExecutionState.WAITING_APPROVAL,
                IntegrationExecutionState.SCHEDULED,
                IntegrationExecutionState.RUNNING,
                IntegrationExecutionState.RECOVERING,
                IntegrationExecutionState.FAILED,
                IntegrationExecutionState.TIMED_OUT,
                IntegrationExecutionState.KILL_SWITCH_BLOCKED,
                *_CANCELLED,
            }
        ),
        IntegrationExecutionState.DELEGATING: frozenset(
            {
                IntegrationExecutionState.RUNNING,
                IntegrationExecutionState.WAITING,
                IntegrationExecutionState.WAITING_APPROVAL,
                IntegrationExecutionState.RECOVERING,
                IntegrationExecutionState.COMPLETED,
                IntegrationExecutionState.PARTIALLY_COMPLETED,
                IntegrationExecutionState.FAILED,
                IntegrationExecutionState.TIMED_OUT,
                IntegrationExecutionState.KILL_SWITCH_BLOCKED,
                *_CANCELLED,
            }
        ),
        IntegrationExecutionState.RECOVERING: frozenset(
            {
                IntegrationExecutionState.VALIDATING,
                IntegrationExecutionState.AUTHORIZED,
                IntegrationExecutionState.PLANNING,
                IntegrationExecutionState.WAITING_APPROVAL,
                IntegrationExecutionState.SCHEDULED,
                IntegrationExecutionState.RUNNING,
                IntegrationExecutionState.WAITING,
                IntegrationExecutionState.DELEGATING,
                IntegrationExecutionState.PARTIALLY_COMPLETED,
                IntegrationExecutionState.FAILED,
                IntegrationExecutionState.TIMED_OUT,
                IntegrationExecutionState.KILL_SWITCH_BLOCKED,
                *_CANCELLED,
            }
        ),
        IntegrationExecutionState.KILL_SWITCH_BLOCKED: frozenset(
            {
                IntegrationExecutionState.VALIDATING,
                IntegrationExecutionState.DENIED,
                IntegrationExecutionState.FAILED,
                IntegrationExecutionState.TIMED_OUT,
                *_CANCELLED,
            }
        ),
        **{state: frozenset() for state in TERMINAL_INTEGRATION_STATES},
    }
)


def can_transition_integration_state(
    source: IntegrationExecutionState | str,
    target: IntegrationExecutionState | str,
) -> bool:
    """Return whether ``source`` may transition to ``target``.

    Unknown values are invalid input and therefore return ``False`` rather than
    making callers handle an enum-conversion exception.
    """

    try:
        source_state = IntegrationExecutionState(source)
        target_state = IntegrationExecutionState(target)
    except (TypeError, ValueError):
        return False
    return target_state in ALLOWED_INTEGRATION_TRANSITIONS[source_state]
