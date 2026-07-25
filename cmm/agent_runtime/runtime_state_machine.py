"""Phase 9.12 – Agent Runtime State Machine.

Provides deterministic validation, categorization, and execution of state transitions for AgentRun.
"""

from __future__ import annotations

import uuid
from collections.abc import Mapping, Sequence
from datetime import datetime

from cmm.agent_runtime.contracts import AgentRun
from cmm.agent_runtime.enums import AgentRuntimeStatus
from cmm.agent_runtime.errors import RuntimeTransitionNotAllowedError
from cmm.agent_runtime.runtime_loop_contracts import (
    RuntimeTransition,
    current_aware_iso,
)


def _norm_status(val: AgentRuntimeStatus | str) -> str:
    if isinstance(val, AgentRuntimeStatus):
        return val.value
    return str(val)


TERMINAL_STATES: frozenset[str] = frozenset(
    {"completed", "cancelled", "failed", "aborted"}
)

RESUMABLE_STATES: frozenset[str] = frozenset(
    {
        "waiting_for_user",
        "waiting_for_resource",
        "waiting_for_approval",
        "paused",
        "recovering",
        "blocked",
    }
)

WAITING_STATES: frozenset[str] = frozenset(
    {"waiting_for_user", "waiting_for_resource", "waiting_for_approval"}
)

ACTIVE_STATES: frozenset[str] = frozenset(
    {
        "initializing",
        "observing",
        "reasoning",
        "planning",
        "executing",
        "validating",
        "evaluating",
        "recovering",
    }
)

VALID_TRANSITIONS: Mapping[str, frozenset[str]] = {
    "created": frozenset({"initializing", "cancelled", "failed", "aborted"}),
    "initializing": frozenset(
        {"observing", "paused", "cancelled", "failed", "aborted"}
    ),
    "observing": frozenset({"reasoning", "paused", "cancelled", "failed", "aborted"}),
    "reasoning": frozenset(
        {
            "waiting_for_user",
            "waiting_for_resource",
            "planning",
            "completed",
            "blocked",
            "failed",
            "paused",
            "cancelled",
            "aborted",
        }
    ),
    "planning": frozenset(
        {
            "waiting_for_approval",
            "executing",
            "blocked",
            "failed",
            "paused",
            "cancelled",
            "aborted",
        }
    ),
    "waiting_for_user": frozenset(
        {"reasoning", "paused", "cancelled", "failed", "aborted"}
    ),
    "waiting_for_resource": frozenset(
        {"reasoning", "paused", "failed", "cancelled", "aborted"}
    ),
    "waiting_for_approval": frozenset(
        {"planning", "executing", "paused", "cancelled", "failed", "aborted"}
    ),
    "executing": frozenset({"validating", "recovering", "paused", "failed", "aborted"}),
    "validating": frozenset(
        {
            "evaluating",
            "recovering",
            "planning",
            "waiting_for_approval",
            "blocked",
            "failed",
            "paused",
            "aborted",
        }
    ),
    "evaluating": frozenset(
        {
            "observing",
            "completed",
            "recovering",
            "paused",
            "blocked",
            "failed",
            "aborted",
        }
    ),
    "recovering": frozenset({"planning", "executing", "paused", "failed", "aborted"}),
    "paused": frozenset(
        {
            "observing",
            "reasoning",
            "planning",
            "executing",
            "cancelled",
            "failed",
            "aborted",
        }
    ),
    "blocked": frozenset({"reasoning", "cancelled", "failed", "aborted"}),
    "completed": frozenset(),
    "cancelled": frozenset(),
    "failed": frozenset(),
    "aborted": frozenset(),
}


class AgentRuntimeStateMachine:
    """Explicit state machine for validating and executing AgentRun status transitions."""

    @staticmethod
    def is_terminal(status: AgentRuntimeStatus | str) -> bool:
        """Check if status is terminal."""
        return _norm_status(status) in TERMINAL_STATES

    @staticmethod
    def is_waiting(status: AgentRuntimeStatus | str) -> bool:
        """Check if status is a waiting state."""
        return _norm_status(status) in WAITING_STATES

    @staticmethod
    def is_resumable(status: AgentRuntimeStatus | str) -> bool:
        """Check if status is a resumable state."""
        return _norm_status(status) in RESUMABLE_STATES

    @staticmethod
    def is_active(status: AgentRuntimeStatus | str) -> bool:
        """Check if status is an active processing state."""
        return _norm_status(status) in ACTIVE_STATES

    @staticmethod
    def allowed_next_states(status: AgentRuntimeStatus | str) -> set[str]:
        """Return the set of valid next status strings for current status."""
        st = _norm_status(status)
        return set(VALID_TRANSITIONS.get(st, frozenset()))

    @classmethod
    def can_transition(
        cls, from_status: AgentRuntimeStatus | str, to_status: AgentRuntimeStatus | str
    ) -> bool:
        """Return True if transition from from_status to to_status is valid or a no-op."""
        src = _norm_status(from_status)
        dst = _norm_status(to_status)
        if src == dst:
            return True
        allowed = VALID_TRANSITIONS.get(src, frozenset())
        return dst in allowed

    @classmethod
    def validate_transition(
        cls, from_status: AgentRuntimeStatus | str, to_status: AgentRuntimeStatus | str
    ) -> None:
        """Validate transition or raise RuntimeTransitionNotAllowedError."""
        src = _norm_status(from_status)
        dst = _norm_status(to_status)
        if src == dst:
            return
        if src in TERMINAL_STATES:
            raise RuntimeTransitionNotAllowedError(
                f"Cannot transition from terminal state '{src}' to '{dst}'."
            )
        allowed = VALID_TRANSITIONS.get(src, frozenset())
        if dst not in allowed:
            raise RuntimeTransitionNotAllowedError(
                f"Invalid transition from '{src}' to '{dst}'. Allowed: {sorted(allowed)}"
            )

    @classmethod
    def transition(
        cls,
        agent_run: AgentRun,
        to_status: AgentRuntimeStatus | str,
        reason_codes: Sequence[str] = (),
        iteration_id: str | None = None,
        triggered_by: str = "runtime",
        idempotency_key: str | None = None,
        now: str | None = None,
    ) -> tuple[AgentRun, RuntimeTransition]:
        """Perform a state transition on agent_run and return updated run and RuntimeTransition."""
        src = _norm_status(agent_run.status)
        dst = _norm_status(to_status)
        cls.validate_transition(src, dst)

        timestamp_str = now or current_aware_iso()
        dt_timestamp = datetime.fromisoformat(timestamp_str)
        transition_id = f"transition-{uuid.uuid4().hex[:12]}"

        dt_completed = dt_timestamp if cls.is_terminal(dst) else agent_run.completed_at

        # Update AgentRun status
        updated_run = AgentRun(
            id=agent_run.id,
            agent_id=agent_run.agent_id,
            goal_id=agent_run.goal_id,
            status=dst,
            autonomy_level=agent_run.autonomy_level,
            current_iteration=agent_run.current_iteration,
            started_at=agent_run.started_at,
            updated_at=dt_timestamp,
            current_workflow_id=agent_run.current_workflow_id,
            current_task_id=agent_run.current_task_id,
            reasoning_session_id=agent_run.reasoning_session_id,
            observation_snapshot_id=agent_run.observation_snapshot_id,
            budget_id=agent_run.budget_id,
            policy_context_id=agent_run.policy_context_id,
            paused_at=agent_run.paused_at,
            completed_at=dt_completed,
            metadata=agent_run.metadata,
        )

        transition = RuntimeTransition(
            id=transition_id,
            agent_run_id=agent_run.id,
            from_status=src,
            to_status=dst,
            created_at=timestamp_str,
            iteration_id=iteration_id,
            reason_codes=tuple(reason_codes),
            triggered_by=triggered_by,
            idempotency_key=idempotency_key,
        )

        return updated_run, transition
