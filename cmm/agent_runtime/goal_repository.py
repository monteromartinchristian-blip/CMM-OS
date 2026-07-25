"""Phase 9.2 – Goal Repository Protocol and In-Memory Implementation.

Defines GoalRepository protocol and InMemoryGoalRepository for storing,
retrieving, updating, and querying Goal entities with deep copy safety.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from cmm.agent_runtime.errors import (
    DuplicateGoalError,
    GoalNotFoundError,
)
from cmm.agent_runtime.goal_contracts import (
    Goal,
    GoalDependency,
    GoalHistoryEntry,
    GoalQuery,
    GoalSearchResult,
)


@runtime_checkable
class GoalRepository(Protocol):
    """Protocol establishing the storage contract for Goal entities."""

    def add(self, goal: Goal) -> Goal:
        """Add a new Goal to the repository."""
        ...

    def get(self, goal_id: str) -> Goal | None:
        """Retrieve a Goal by ID."""
        ...

    def update(self, goal: Goal) -> Goal:
        """Update an existing Goal in the repository."""
        ...

    def search(self, query: GoalQuery) -> GoalSearchResult:
        """Search Goals matching query criteria."""
        ...

    def get_children(self, goal_id: str) -> tuple[Goal, ...]:
        """Get direct child goals of a parent goal."""
        ...

    def get_dependencies(self, goal_id: str) -> tuple[GoalDependency, ...]:
        """Get registered dependencies for a goal."""
        ...

    def append_history(self, entry: GoalHistoryEntry) -> None:
        """Record an audit history entry for a goal."""
        ...

    def get_history(self, goal_id: str) -> tuple[GoalHistoryEntry, ...]:
        """Get audit history entries for a goal."""
        ...


class InMemoryGoalRepository:
    """In-memory thread-safe reference implementation of GoalRepository.

    Ensures mutation isolation by storing and returning serialized/reconstructed
    copies of Goal entities.
    """

    def __init__(self) -> None:
        self._goals: dict[str, dict] = {}
        self._history: dict[str, list[dict]] = {}

    def _copy_goal(self, goal: Goal) -> Goal:
        """Create an isolated deep copy of a Goal object."""
        return Goal.from_mapping(goal.serialize())

    def _copy_history_entry(self, entry: GoalHistoryEntry) -> GoalHistoryEntry:
        """Create an isolated deep copy of a GoalHistoryEntry object."""
        return GoalHistoryEntry.from_mapping(entry.serialize())

    def add(self, goal: Goal) -> Goal:
        """Add a new Goal to the repository.

        Raises DuplicateGoalError if goal.id already exists.
        """
        if goal.id in self._goals:
            raise DuplicateGoalError(f"Goal with ID {goal.id!r} already exists")

        self._goals[goal.id] = goal.serialize()
        return self._copy_goal(goal)

    def get(self, goal_id: str) -> Goal | None:
        """Retrieve a Goal by ID. Returns None if not found."""
        data = self._goals.get(goal_id)
        if data is None:
            return None
        return Goal.from_mapping(data)

    def update(self, goal: Goal) -> Goal:
        """Update an existing Goal in the repository.

        Raises GoalNotFoundError if goal.id is not registered.
        """
        if goal.id not in self._goals:
            raise GoalNotFoundError(f"Goal with ID {goal.id!r} not found")

        self._goals[goal.id] = goal.serialize()
        return self._copy_goal(goal)

    def search(self, query: GoalQuery) -> GoalSearchResult:
        """Search Goals using GoalQuery filters."""
        matched: list[Goal] = []

        for data in self._goals.values():
            goal = Goal.from_mapping(data)

            if query.statuses and goal.status not in query.statuses:
                continue

            if query.kinds and goal.kind not in query.kinds:
                continue

            if (
                query.min_priority is not None
                and goal.priority.score < query.min_priority
            ):
                continue

            if (
                query.owner_actor_id is not None
                and goal.owner_actor_id != query.owner_actor_id
            ):
                continue

            if (
                query.assigned_agent_id is not None
                and goal.assigned_agent_id != query.assigned_agent_id
            ):
                continue

            if (
                query.parent_goal_id is not None
                and goal.parent_goal_id != query.parent_goal_id
            ):
                continue

            if query.text_search is not None:
                term = query.text_search.lower()
                if (
                    term not in goal.title.lower()
                    and term not in goal.description.lower()
                ):
                    continue

            matched.append(goal)

        # Deterministic sorting: score descending, created_at ascending, id ascending
        matched.sort(key=lambda g: (-g.priority.score, g.created_at, g.id))

        total_count = len(matched)
        start = query.offset
        end = start + query.limit if query.limit is not None else None
        paged_goals = tuple(matched[start:end])

        return GoalSearchResult(
            goals=paged_goals,
            total_count=total_count,
            limit=query.limit,
            offset=query.offset,
        )

    def get_children(self, goal_id: str) -> tuple[Goal, ...]:
        """Get subgoals whose parent_goal_id equals goal_id."""
        if goal_id not in self._goals:
            raise GoalNotFoundError(f"Parent goal with ID {goal_id!r} not found")

        children: list[Goal] = []
        for data in self._goals.values():
            goal = Goal.from_mapping(data)
            if goal.parent_goal_id == goal_id:
                children.append(goal)

        children.sort(key=lambda g: (-g.priority.score, g.created_at, g.id))
        return tuple(children)

    def get_dependencies(self, goal_id: str) -> tuple[GoalDependency, ...]:
        """Get dependencies for goal_id."""
        goal = self.get(goal_id)
        if goal is None:
            raise GoalNotFoundError(f"Goal with ID {goal_id!r} not found")
        return goal.dependencies

    def append_history(self, entry: GoalHistoryEntry) -> None:
        """Append audit entry for a goal."""
        if entry.goal_id not in self._history:
            self._history[entry.goal_id] = []
        self._history[entry.goal_id].append(entry.serialize())

    def get_history(self, goal_id: str) -> tuple[GoalHistoryEntry, ...]:
        """Get history entries for goal_id."""
        entries_data = self._history.get(goal_id, [])
        entries = [GoalHistoryEntry.from_mapping(d) for d in entries_data]
        entries.sort(key=lambda e: e.timestamp)
        return tuple(entries)
