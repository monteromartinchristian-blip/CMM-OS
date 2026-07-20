"""In-memory lifecycle management for non-executing action queues."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from cmm.execution.action_planner import ActionPlanner


class ActionStatus(str, Enum):
    """Lifecycle states for queued actions."""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


@dataclass(frozen=True)
class ActionExecution:
    """Immutable state record for one action in the runtime queue."""

    action: object
    status: ActionStatus
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    error: Optional[str] = None
    result: object = None


@dataclass
class RuntimeStatus:
    """Aggregate state counts and terminal-action progress for the runtime."""

    total: int
    pending: int
    running: int
    completed: int
    failed: int
    skipped: int
    progress: float


class ActionRuntime:
    """Manage action state transitions without executing any action."""

    def __init__(self, action_planner: ActionPlanner) -> None:
        """Initialize an empty runtime using the public action-planning facade."""
        self._action_planner = action_planner
        self._executions: list[ActionExecution] = []

    def enqueue(self, actions: list[object]) -> None:
        """Append validated actions to the runtime as pending executions."""
        validation = self._action_planner.validate(actions)
        if not validation["valid"]:
            errors = validation["errors"]
            raise ValueError("Invalid action queue: " + " ".join(errors))

        existing_ids = {
            self._action_id(execution.action)
            for execution in self._executions
        }
        new_ids = [self._action_id(action) for action in actions]
        if any(identifier in existing_ids for identifier in new_ids):
            raise ValueError("Action queue contains duplicate action ids.")

        self._executions.extend(
            ActionExecution(action=action, status=ActionStatus.PENDING)
            for action in actions
        )

    def next_action(self) -> Optional[object]:
        """Return the first pending action without changing its state."""
        for execution in self._executions:
            if execution.status == ActionStatus.PENDING:
                return execution.action
        return None

    def mark_running(self, action_id: str) -> ActionExecution:
        """Mark a pending action as running and record its start time."""
        return self._transition(
            action_id,
            expected_statuses={ActionStatus.PENDING},
            new_status=ActionStatus.RUNNING,
            started_at=self._now(),
        )

    def mark_completed(
        self,
        action_id: str,
        result: object = None,
    ) -> ActionExecution:
        """Mark a running action as completed and record its result."""
        return self._transition(
            action_id,
            expected_statuses={ActionStatus.RUNNING},
            new_status=ActionStatus.COMPLETED,
            finished_at=self._now(),
            result=result,
        )

    def mark_failed(self, action_id: str, reason: str) -> ActionExecution:
        """Mark a running action as failed and record its failure reason."""
        return self._transition(
            action_id,
            expected_statuses={ActionStatus.RUNNING},
            new_status=ActionStatus.FAILED,
            finished_at=self._now(),
            error=reason,
        )

    def mark_skipped(
        self,
        action_id: str,
        reason: Optional[str] = None,
    ) -> ActionExecution:
        """Mark a pending or running action as skipped."""
        return self._transition(
            action_id,
            expected_statuses={ActionStatus.PENDING, ActionStatus.RUNNING},
            new_status=ActionStatus.SKIPPED,
            finished_at=self._now(),
            error=reason,
        )

    def status(self) -> RuntimeStatus:
        """Return aggregate counts and terminal-action progress."""
        counts = {
            status: sum(
                execution.status == status
                for execution in self._executions
            )
            for status in ActionStatus
        }
        total = len(self._executions)
        terminal_count = (
            counts[ActionStatus.COMPLETED]
            + counts[ActionStatus.FAILED]
            + counts[ActionStatus.SKIPPED]
        )

        return RuntimeStatus(
            total=total,
            pending=counts[ActionStatus.PENDING],
            running=counts[ActionStatus.RUNNING],
            completed=counts[ActionStatus.COMPLETED],
            failed=counts[ActionStatus.FAILED],
            skipped=counts[ActionStatus.SKIPPED],
            progress=round(terminal_count / total * 100, 2) if total else 0.0,
        )

    def history(self) -> list[ActionExecution]:
        """Return lifecycle records in queue order."""
        return list(self._executions)

    def reset(self) -> None:
        """Clear every action and lifecycle record from the runtime."""
        self._executions.clear()

    def _transition(
        self,
        action_id: str,
        expected_statuses: set[ActionStatus],
        new_status: ActionStatus,
        started_at: Optional[datetime] = None,
        finished_at: Optional[datetime] = None,
        error: Optional[str] = None,
        result: object = None,
    ) -> ActionExecution:
        index, execution = self._find_execution(action_id)
        if execution.status not in expected_statuses:
            expected = ", ".join(status.value for status in expected_statuses)
            raise RuntimeError(
                f"Action {action_id} is {execution.status.value}; expected {expected}."
            )

        updated_execution = replace(
            execution,
            status=new_status,
            started_at=started_at if started_at is not None else execution.started_at,
            finished_at=finished_at,
            error=error,
            result=result,
        )
        self._executions[index] = updated_execution
        return updated_execution

    def _find_execution(self, action_id: str) -> tuple[int, ActionExecution]:
        for index, execution in enumerate(self._executions):
            if self._action_id(execution.action) == action_id:
                return index, execution
        raise ValueError(f"Unknown action id: {action_id}.")

    def _action_id(self, action: object) -> str:
        identifier = getattr(action, "id", None)
        if not isinstance(identifier, str):
            raise ValueError("Action has no valid id.")
        return identifier

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)
