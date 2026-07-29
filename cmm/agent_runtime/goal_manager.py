"""Phase 9.2 – Goal System Manager.

Provides lifecycle management, status transition state machine, dependency resolution,
subgoal hierarchy, success criterion evaluation, duplicate detection, and audit history
preservation for operational Goal entities.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from types import MappingProxyType
from typing import Any

from cmm.agent_runtime.enums import GoalKind, GoalStatus, SuccessCriterionStatus
from cmm.agent_runtime.errors import (
    GoalCompletionError,
    GoalDependencyError,
    GoalNotFoundError,
    InvalidGoalTransitionError,
)
from cmm.agent_runtime.goal_contracts import (
    Goal,
    GoalDependency,
    GoalHistoryEntry,
    GoalQuery,
    GoalSearchResult,
    SuccessCriterion,
)
from cmm.agent_runtime.goal_repository import GoalRepository, InMemoryGoalRepository

TERMINAL_GOAL_STATUSES: set[GoalStatus] = {
    GoalStatus.COMPLETED,
    GoalStatus.PARTIALLY_COMPLETED,
    GoalStatus.FAILED,
    GoalStatus.ABANDONED,
    GoalStatus.CANCELLED,
    GoalStatus.SUPERSEDED,
}


def _normalize_goal_status(status: GoalStatus | str) -> GoalStatus:
    """Normalize a contract status before lifecycle evaluation."""
    return status if isinstance(status, GoalStatus) else GoalStatus(status)


ALLOWED_TRANSITIONS: dict[GoalStatus, set[GoalStatus]] = {
    GoalStatus.PROPOSED: {
        GoalStatus.ACCEPTED,
        GoalStatus.CANCELLED,
        GoalStatus.ABANDONED,
        GoalStatus.SUPERSEDED,
    },
    GoalStatus.ACCEPTED: {
        GoalStatus.ACTIVE,
        GoalStatus.PLANNING,
        GoalStatus.IN_PROGRESS,
        GoalStatus.BLOCKED,
        GoalStatus.PAUSED,
        GoalStatus.CANCELLED,
        GoalStatus.ABANDONED,
        GoalStatus.SUPERSEDED,
    },
    GoalStatus.ACTIVE: {
        GoalStatus.PLANNING,
        GoalStatus.IN_PROGRESS,
        GoalStatus.WAITING_FOR_USER,
        GoalStatus.WAITING_FOR_RESOURCE,
        GoalStatus.WAITING_FOR_APPROVAL,
        GoalStatus.BLOCKED,
        GoalStatus.PAUSED,
        GoalStatus.COMPLETED,
        GoalStatus.PARTIALLY_COMPLETED,
        GoalStatus.FAILED,
        GoalStatus.CANCELLED,
        GoalStatus.ABANDONED,
        GoalStatus.SUPERSEDED,
    },
    GoalStatus.PLANNING: {
        GoalStatus.ACTIVE,
        GoalStatus.IN_PROGRESS,
        GoalStatus.WAITING_FOR_USER,
        GoalStatus.WAITING_FOR_RESOURCE,
        GoalStatus.WAITING_FOR_APPROVAL,
        GoalStatus.BLOCKED,
        GoalStatus.PAUSED,
        GoalStatus.COMPLETED,
        GoalStatus.PARTIALLY_COMPLETED,
        GoalStatus.FAILED,
        GoalStatus.CANCELLED,
        GoalStatus.ABANDONED,
        GoalStatus.SUPERSEDED,
    },
    GoalStatus.IN_PROGRESS: {
        GoalStatus.ACTIVE,
        GoalStatus.PLANNING,
        GoalStatus.WAITING_FOR_USER,
        GoalStatus.WAITING_FOR_RESOURCE,
        GoalStatus.WAITING_FOR_APPROVAL,
        GoalStatus.BLOCKED,
        GoalStatus.PAUSED,
        GoalStatus.COMPLETED,
        GoalStatus.PARTIALLY_COMPLETED,
        GoalStatus.FAILED,
        GoalStatus.CANCELLED,
        GoalStatus.ABANDONED,
        GoalStatus.SUPERSEDED,
    },
    GoalStatus.WAITING_FOR_USER: {
        GoalStatus.ACTIVE,
        GoalStatus.IN_PROGRESS,
        GoalStatus.PLANNING,
        GoalStatus.BLOCKED,
        GoalStatus.PAUSED,
        GoalStatus.CANCELLED,
        GoalStatus.ABANDONED,
        GoalStatus.FAILED,
    },
    GoalStatus.WAITING_FOR_RESOURCE: {
        GoalStatus.ACTIVE,
        GoalStatus.IN_PROGRESS,
        GoalStatus.PLANNING,
        GoalStatus.BLOCKED,
        GoalStatus.PAUSED,
        GoalStatus.CANCELLED,
        GoalStatus.ABANDONED,
        GoalStatus.FAILED,
    },
    GoalStatus.WAITING_FOR_APPROVAL: {
        GoalStatus.ACCEPTED,
        GoalStatus.ACTIVE,
        GoalStatus.IN_PROGRESS,
        GoalStatus.PLANNING,
        GoalStatus.BLOCKED,
        GoalStatus.PAUSED,
        GoalStatus.CANCELLED,
        GoalStatus.ABANDONED,
        GoalStatus.FAILED,
    },
    GoalStatus.BLOCKED: {
        GoalStatus.ACTIVE,
        GoalStatus.IN_PROGRESS,
        GoalStatus.PLANNING,
        GoalStatus.PAUSED,
        GoalStatus.CANCELLED,
        GoalStatus.ABANDONED,
        GoalStatus.FAILED,
    },
    GoalStatus.PAUSED: {
        GoalStatus.ACTIVE,
        GoalStatus.IN_PROGRESS,
        GoalStatus.PLANNING,
        GoalStatus.WAITING_FOR_USER,
        GoalStatus.WAITING_FOR_RESOURCE,
        GoalStatus.WAITING_FOR_APPROVAL,
        GoalStatus.BLOCKED,
        GoalStatus.CANCELLED,
        GoalStatus.ABANDONED,
    },
    GoalStatus.COMPLETED: set(),
    GoalStatus.PARTIALLY_COMPLETED: set(),
    GoalStatus.FAILED: set(),
    GoalStatus.ABANDONED: set(),
    GoalStatus.CANCELLED: set(),
    GoalStatus.SUPERSEDED: set(),
}


class GoalManager:
    """Manager for operational Goal lifecycle, transitions, dependencies, and audit history."""

    def __init__(self, repository: GoalRepository | None = None) -> None:
        self.repository: GoalRepository = (
            repository if repository is not None else InMemoryGoalRepository()
        )

    def register_goal(
        self,
        goal: Goal,
        actor_id: str = "actor-user",
        reason: str = "Goal registered",
    ) -> Goal:
        """Register a new Goal in the system."""
        registered = self.repository.add(goal)

        history_entry = GoalHistoryEntry(
            id=f"ghist-{registered.id}-{int(datetime.now(timezone.utc).timestamp() * 1000)}",
            goal_id=registered.id,
            previous_status=None,
            new_status=registered.status,
            actor_id=actor_id,
            reason=reason,
        )
        self.repository.append_history(history_entry)

        return registered

    def get_goal(self, goal_id: str) -> Goal | None:
        """Retrieve a Goal by ID."""
        return self.repository.get(goal_id)

    def update_goal(self, goal: Goal) -> Goal:
        """Update an existing Goal."""
        return self.repository.update(goal)

    def search_goals(self, query: GoalQuery) -> GoalSearchResult:
        """Search goals using criteria."""
        return self.repository.search(query)

    def change_status(
        self,
        goal_id: str,
        new_status: GoalStatus | str,
        actor_id: str,
        reason: str,
        decision_id: str | None = None,
        evidence: Sequence[str] = (),
        metadata: Mapping | None = None,
    ) -> Goal:
        """Attempt to transition a Goal to a new status."""
        current_goal = self.repository.get(goal_id)
        if current_goal is None:
            raise GoalNotFoundError(f"Goal with ID {goal_id!r} not found")

        target_status = (
            GoalStatus(new_status) if isinstance(new_status, str) else new_status
        )
        current_status = _normalize_goal_status(current_goal.status)

        if current_status == target_status:
            return current_goal

        allowed = ALLOWED_TRANSITIONS.get(current_status, set())
        if target_status not in allowed:
            raise InvalidGoalTransitionError(
                f"Invalid status transition for goal {goal_id!r}: "
                f"cannot move from '{current_status.value}' to '{target_status.value}'"
            )

        # Check required success criteria when completing
        if target_status in (GoalStatus.COMPLETED, GoalStatus.PARTIALLY_COMPLETED):
            for sc in current_goal.success_criteria:
                criterion_status = (
                    sc.status
                    if isinstance(sc.status, SuccessCriterionStatus)
                    else SuccessCriterionStatus(sc.status)
                )
                if sc.required and criterion_status not in (
                    SuccessCriterionStatus.SATISFIED,
                    SuccessCriterionStatus.WAIVED,
                ):
                    raise GoalCompletionError(
                        f"Cannot mark goal {goal_id!r} as completed: "
                        f"required criterion '{sc.id}' is unsatisfied "
                        f"(status: '{criterion_status.value}')"
                    )

        now = datetime.now(timezone.utc)
        completed_at = (
            now
            if target_status in (GoalStatus.COMPLETED, GoalStatus.PARTIALLY_COMPLETED)
            else None
        )

        updated_goal = Goal.from_mapping(
            {
                **current_goal.serialize(),
                "status": target_status,
                "updated_at": now.isoformat(),
                "completed_at": completed_at.isoformat() if completed_at else None,
            }
        )

        saved_goal = self.repository.update(updated_goal)

        history_entry = GoalHistoryEntry(
            id=f"ghist-{goal_id}-{int(now.timestamp() * 1000)}",
            goal_id=goal_id,
            previous_status=current_status,
            new_status=target_status,
            actor_id=actor_id,
            reason=reason,
            decision_id=decision_id,
            evidence=tuple(evidence),
            timestamp=now,
            metadata=MappingProxyType(dict(metadata or {})),
        )
        self.repository.append_history(history_entry)

        return saved_goal

    def pause_goal(self, goal_id: str, actor_id: str, reason: str) -> Goal:
        """Pause pursuit of a Goal."""
        current_goal = self.repository.get(goal_id)
        if current_goal is None:
            raise GoalNotFoundError(f"Goal with ID {goal_id!r} not found")

        current_status = _normalize_goal_status(current_goal.status)
        if current_status in TERMINAL_GOAL_STATUSES:
            raise InvalidGoalTransitionError(
                f"Cannot pause goal {goal_id!r} in terminal status "
                f"'{current_status.value}'"
            )

        return self.change_status(
            goal_id=goal_id,
            new_status=GoalStatus.PAUSED,
            actor_id=actor_id,
            reason=reason,
        )

    def resume_goal(self, goal_id: str, actor_id: str, reason: str) -> Goal:
        """Resume a paused Goal, restoring its prior active status."""
        current_goal = self.repository.get(goal_id)
        if current_goal is None:
            raise GoalNotFoundError(f"Goal with ID {goal_id!r} not found")

        current_status = _normalize_goal_status(current_goal.status)
        if current_status != GoalStatus.PAUSED:
            raise InvalidGoalTransitionError(
                f"Cannot resume goal {goal_id!r}: current status is "
                f"'{current_status.value}', not 'paused'"
            )

        # Look up history to find pre-paused status
        history = self.get_history(goal_id)
        restored_status = GoalStatus.ACTIVE
        for entry in reversed(history):
            if (
                entry.new_status == GoalStatus.PAUSED
                and entry.previous_status is not None
                and entry.previous_status
                not in (GoalStatus.PAUSED, *TERMINAL_GOAL_STATUSES)
            ):
                restored_status = _normalize_goal_status(entry.previous_status)
                break

        return self.change_status(
            goal_id=goal_id,
            new_status=restored_status,
            actor_id=actor_id,
            reason=reason,
        )

    def cancel_goal(self, goal_id: str, actor_id: str, reason: str) -> Goal:
        """Cancel a Goal (idempotent if already cancelled)."""
        current_goal = self.repository.get(goal_id)
        if current_goal is None:
            raise GoalNotFoundError(f"Goal with ID {goal_id!r} not found")

        current_status = _normalize_goal_status(current_goal.status)
        if current_status == GoalStatus.CANCELLED:
            return current_goal

        if current_status in TERMINAL_GOAL_STATUSES:
            raise InvalidGoalTransitionError(
                f"Cannot cancel goal {goal_id!r} in terminal status "
                f"'{current_status.value}'"
            )

        return self.change_status(
            goal_id=goal_id,
            new_status=GoalStatus.CANCELLED,
            actor_id=actor_id,
            reason=reason,
        )

    def complete_goal(self, goal_id: str, actor_id: str, reason: str) -> Goal:
        """Mark a Goal as completed (evaluating required criteria first)."""
        return self.change_status(
            goal_id=goal_id,
            new_status=GoalStatus.COMPLETED,
            actor_id=actor_id,
            reason=reason,
        )

    def create_subgoal(
        self,
        parent_id: str,
        child_goal: Goal,
        actor_id: str = "actor-user",
        reason: str = "Created subgoal",
    ) -> Goal:
        """Create and attach a subgoal under parent_id."""
        parent = self.repository.get(parent_id)
        if parent is None:
            raise GoalNotFoundError(f"Parent goal with ID {parent_id!r} not found")

        if child_goal.id == parent_id:
            raise InvalidGoalTransitionError("A goal cannot be a subgoal of itself")

        # Prepare child goal with parent_goal_id set
        child_mapping = {
            **child_goal.serialize(),
            "parent_goal_id": parent_id,
        }
        updated_child = Goal.from_mapping(child_mapping)

        # Register child goal
        registered_child = self.register_goal(
            goal=updated_child, actor_id=actor_id, reason=reason
        )

        # Update parent's child_goal_ids list if not already present
        if registered_child.id not in parent.child_goal_ids:
            new_child_ids = list(parent.child_goal_ids) + [registered_child.id]
            updated_parent = Goal.from_mapping(
                {
                    **parent.serialize(),
                    "child_goal_ids": new_child_ids,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }
            )
            self.repository.update(updated_parent)

        return registered_child

    def get_children(self, goal_id: str) -> tuple[Goal, ...]:
        """Get subgoals for a given parent goal ID."""
        return self.repository.get_children(goal_id)

    def add_dependency(
        self,
        dependency: GoalDependency,
        actor_id: str = "actor-user",
        reason: str = "Added dependency",
    ) -> Goal:
        """Add a dependency relationship to target goal."""
        target_goal = self.repository.get(dependency.goal_id)
        if target_goal is None:
            raise GoalNotFoundError(f"Goal {dependency.goal_id!r} not found")

        depends_on_goal = self.repository.get(dependency.depends_on_goal_id)
        if depends_on_goal is None:
            raise GoalNotFoundError(
                f"Dependency Goal {dependency.depends_on_goal_id!r} not found"
            )

        if dependency.goal_id == dependency.depends_on_goal_id:
            raise GoalDependencyError("A goal cannot depend on itself")

        new_deps = list(target_goal.dependencies) + [dependency]
        updated_target = Goal.from_mapping(
            {
                **target_goal.serialize(),
                "dependencies": [d.serialize() for d in new_deps],
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        )

        saved = self.repository.update(updated_target)

        now = datetime.now(timezone.utc)
        self.repository.append_history(
            GoalHistoryEntry(
                id=f"ghist-{dependency.goal_id}-{int(now.timestamp() * 1000)}",
                goal_id=dependency.goal_id,
                previous_status=target_goal.status,
                new_status=target_goal.status,
                actor_id=actor_id,
                reason=f"{reason}: depends on {dependency.depends_on_goal_id}",
                timestamp=now,
            )
        )

        return saved

    def get_dependencies(self, goal_id: str) -> tuple[GoalDependency, ...]:
        """Get dependencies for a goal."""
        return self.repository.get_dependencies(goal_id)

    def evaluate_success_criteria(
        self,
        goal_id: str,
        evaluations: Mapping[
            str, tuple[SuccessCriterionStatus | str, Any] | Mapping[str, Any]
        ],
        actor_id: str = "actor-user",
        reason: str = "Evaluated success criteria",
    ) -> Goal:
        """Evaluate and update success criteria status for a goal."""
        goal = self.repository.get(goal_id)
        if goal is None:
            raise GoalNotFoundError(f"Goal with ID {goal_id!r} not found")

        updated_criteria = []
        for sc in goal.success_criteria:
            if sc.id in evaluations:
                eval_val = evaluations[sc.id]
                if isinstance(eval_val, Mapping):
                    new_st = eval_val.get("status", sc.status)
                    actual_val = eval_val.get("actual_value", sc.actual_value)
                    evidence_list = eval_val.get("evidence", sc.evidence)
                elif isinstance(eval_val, (tuple, list)) and len(eval_val) >= 2:
                    new_st, actual_val = eval_val[0], eval_val[1]
                    evidence_list = sc.evidence
                else:
                    new_st, actual_val, evidence_list = (
                        eval_val,
                        sc.actual_value,
                        sc.evidence,
                    )

                new_criterion = SuccessCriterion.from_mapping(
                    {
                        **sc.serialize(),
                        "status": new_st,
                        "actual_value": actual_val,
                        "evidence": evidence_list,
                    }
                )
                updated_criteria.append(new_criterion)
            else:
                updated_criteria.append(sc)

        now = datetime.now(timezone.utc)
        updated_goal = Goal.from_mapping(
            {
                **goal.serialize(),
                "success_criteria": [sc.serialize() for sc in updated_criteria],
                "updated_at": now.isoformat(),
            }
        )

        saved = self.repository.update(updated_goal)

        self.repository.append_history(
            GoalHistoryEntry(
                id=f"ghist-{goal_id}-{int(now.timestamp() * 1000)}",
                goal_id=goal_id,
                previous_status=goal.status,
                new_status=goal.status,
                actor_id=actor_id,
                reason=reason,
                timestamp=now,
            )
        )

        return saved

    def get_history(self, goal_id: str) -> tuple[GoalHistoryEntry, ...]:
        """Get audit log entries for a goal."""
        return self.repository.get_history(goal_id)

    def detect_duplicates(
        self, title: str, kind: GoalKind | str | None = None
    ) -> tuple[Goal, ...]:
        """Detect existing goals with identical or normalized matching titles."""
        clean_title = title.strip().lower()
        if not clean_title:
            return ()

        query_kind = GoalKind(kind) if isinstance(kind, str) else kind
        search_result = self.repository.search(
            GoalQuery(
                kinds=(query_kind,) if query_kind else (),
                text_search=clean_title,
            )
        )

        matches = [
            g for g in search_result.goals if g.title.strip().lower() == clean_title
        ]
        return tuple(matches)
