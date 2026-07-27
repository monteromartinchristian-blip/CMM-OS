"""Phase 9.24 Agent Delegation Store.

Storage abstraction for delegation contracts.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Protocol

from cmm.agent_runtime.agent_delegation_contracts import DelegatedGoal
from cmm.agent_runtime.agent_delegation_enums import DelegationStatus


class AgentDelegationStore(Protocol):
    """Protocol for delegation storage backends."""

    def add(self, delegation: DelegatedGoal) -> None:
        """Add a new delegation."""
        ...

    def get(self, delegation_id: str) -> DelegatedGoal | None:
        """Retrieve a delegation by ID."""
        ...

    def update(self, delegation: DelegatedGoal) -> None:
        """Update an existing delegation."""
        ...

    def list_by_parent_goal(self, parent_goal_id: str) -> list[DelegatedGoal]:
        """List all delegations for a parent goal."""
        ...

    def list_by_child_goal(self, child_goal_id: str) -> list[DelegatedGoal]:
        """List all delegations for a child goal."""
        ...

    def list_by_source_agent(self, source_agent_id: str) -> list[DelegatedGoal]:
        """List all delegations from a source agent."""
        ...

    def list_by_target_agent(self, target_agent_id: str) -> list[DelegatedGoal]:
        """List all delegations to a target agent."""
        ...

    def list_by_status(self, status: DelegationStatus) -> list[DelegatedGoal]:
        """List all delegations with a specific status."""
        ...

    def list_by_source_run(self, source_agent_run_id: str) -> list[DelegatedGoal]:
        """List all delegations from a source agent run."""
        ...

    def list_by_target_run(self, target_agent_run_id: str) -> list[DelegatedGoal]:
        """List all delegations to a target agent run."""
        ...

    def list_active_by_parent_goal(self, parent_goal_id: str) -> list[DelegatedGoal]:
        """List active (non-terminal) delegations for a parent goal."""
        ...

    def list_active_by_target_agent(self, target_agent_id: str) -> list[DelegatedGoal]:
        """List active delegations for a target agent."""
        ...

    def exists_delegation_between(
        self, source_agent_id: str, target_agent_id: str, parent_goal_id: str
    ) -> bool:
        """Check if an active delegation exists between agents for a parent goal."""
        ...

    def count_by_parent_goal(self, parent_goal_id: str) -> int:
        """Count delegations for a parent goal."""
        ...

    def delete(self, delegation_id: str) -> bool:
        """Delete a delegation. Returns True if deleted."""
        ...

    def clear(self) -> None:
        """Remove all delegations (testing only)."""
        ...


@dataclass
class InMemoryAgentDelegationStore:
    """
    In-memory implementation of AgentDelegationStore.

    Thread-safe for single-threaded use. For multi-threaded environments,
    use with appropriate locking or swap for a persistent backend.
    """

    _delegations: dict[str, DelegatedGoal] = field(default_factory=dict, init=False)
    _by_parent_goal: dict[str, set[str]] = field(default_factory=dict, init=False)
    _by_child_goal: dict[str, set[str]] = field(default_factory=dict, init=False)
    _by_source_agent: dict[str, set[str]] = field(default_factory=dict, init=False)
    _by_target_agent: dict[str, set[str]] = field(default_factory=dict, init=False)
    _by_status: dict[DelegationStatus, set[str]] = field(
        default_factory=dict, init=False
    )
    _by_source_run: dict[str, set[str]] = field(default_factory=dict, init=False)
    _by_target_run: dict[str, set[str]] = field(default_factory=dict, init=False)

    def _index_add(self, delegation: DelegatedGoal) -> None:
        """Add delegation to all indices."""
        dep_id = delegation.id

        # By parent goal
        self._by_parent_goal.setdefault(delegation.parent_goal_id, set()).add(dep_id)

        # By child goal
        self._by_child_goal.setdefault(delegation.child_goal_id, set()).add(dep_id)

        # By source agent
        self._by_source_agent.setdefault(delegation.source_agent_id, set()).add(dep_id)

        # By target agent
        self._by_target_agent.setdefault(delegation.target_agent_id, set()).add(dep_id)

        # By status
        self._by_status.setdefault(delegation.status, set()).add(dep_id)

        # By source run
        if delegation.source_agent_run_id:
            self._by_source_run.setdefault(delegation.source_agent_run_id, set()).add(
                dep_id
            )

        # By target run
        if delegation.target_agent_run_id:
            self._by_target_run.setdefault(delegation.target_agent_run_id, set()).add(
                dep_id
            )

    def _index_remove(self, deletion: DelegatedGoal) -> None:
        """Remove delegation from all indices."""
        dep_id = deletion.id

        # Each entry: (index_dict, lookup_key)
        index_entries: list[tuple[dict, str | None]] = [
            (self._by_parent_goal, deletion.parent_goal_id),
            (self._by_child_goal, deletion.child_goal_id),
            (self._by_source_agent, deletion.source_agent_id),
            (self._by_target_agent, deletion.target_agent_id),
            (self._by_status, deletion.status),
            (self._by_source_run, deletion.source_agent_run_id),
            (self._by_target_run, deletion.target_agent_run_id),
        ]

        for idx, key in index_entries:
            if key is None:
                continue
            ids_set = idx.get(key)
            if ids_set is None:
                continue
            ids_set.discard(dep_id)
            if not ids_set:
                idx.pop(key, None)

    def _update_indices(self, old: DelegatedGoal, new_: DelegatedGoal) -> None:
        """Update indices when delegation changes."""
        self._index_remove(old)
        self._index_add(new_)

    def add(self, delegation: DelegatedGoal) -> None:
        if delegation.id in self._delegations:
            raise ValueError(f"Delegation {delegation.id} already exists")
        self._delegations[delegation.id] = delegation
        self._index_add(delegation)

    def get(self, delegation_id: str) -> DelegatedGoal | None:
        return self._delegations.get(delegation_id)

    def update(self, delegation: DelegatedGoal) -> None:
        old = self._delegations.get(delegation.id)
        if old is None:
            raise KeyError(f"Delegation {delegation.id} not found")
        self._delegations[delegation.id] = delegation
        self._update_indices(old, delegation)

    def list_by_parent_goal(self, parent_goal_id: str) -> list[DelegatedGoal]:
        ids = self._by_parent_goal.get(parent_goal_id, set())
        return [self._delegations[did] for did in ids if did in self._delegations]

    def list_by_child_goal(self, child_goal_id: str) -> list[DelegatedGoal]:
        ids = self._by_child_goal.get(child_goal_id, set())
        return [self._delegations[did] for did in ids if did in self._delegations]

    def list_by_source_agent(self, source_agent_id: str) -> list[DelegatedGoal]:
        ids = self._by_source_agent.get(source_agent_id, set())
        return [self._delegations[did] for did in ids if did in self._delegations]

    def list_by_target_agent(self, target_agent_id: str) -> list[DelegatedGoal]:
        ids = self._by_target_agent.get(target_agent_id, set())
        return [self._delegations[did] for did in ids if did in self._delegations]

    def list_by_status(self, status: DelegationStatus) -> list[DelegatedGoal]:
        ids = self._by_status.get(status, set())
        return [self._delegations[did] for did in ids if did in self._delegations]

    def list_by_source_run(self, source_agent_run_id: str) -> list[DelegatedGoal]:
        ids = self._by_source_run.get(source_agent_run_id, set())
        return [self._delegations[did] for did in ids if did in self._delegations]

    def list_by_target_run(self, target_agent_run_id: str) -> list[DelegatedGoal]:
        ids = self._by_target_run.get(target_agent_run_id, set())
        return [self._delegations[did] for did in ids if did in self._delegations]

    def list_active_by_parent_goal(self, parent_goal_id: str) -> list[DelegatedGoal]:
        """List non-terminal delegations for a parent goal."""
        all_deps = self.list_by_parent_goal(parent_goal_id)
        return [d for d in all_deps if not d.is_terminal]

    def list_active_by_target_agent(self, target_agent_id: str) -> list[DelegatedGoal]:
        """List non-terminal delegations for a target agent."""
        all_deps = self.list_by_target_agent(target_agent_id)
        return [d for d in all_deps if not d.is_terminal]

    def exists_delegation_between(
        self, source_agent_id: str, target_agent_id: str, parent_goal_id: str
    ) -> bool:
        """Check if an active delegation exists between agents for a parent goal."""
        for dep in self.list_by_parent_goal(parent_goal_id):
            if (
                dep.source_agent_id == source_agent_id
                and dep.target_agent_id == target_agent_id
                and not dep.is_terminal
            ):
                return True
        return False

    def count_by_parent_goal(self, parent_goal_id: str) -> int:
        return len(self._by_parent_goal.get(parent_goal_id, set()))

    def delete(self, delegation_id: str) -> bool:
        delegation = self._delegations.pop(delegation_id, None)
        if delegation is None:
            return False
        self._index_remove(delegation)
        return True

    def clear(self) -> None:
        self._delegations.clear()
        self._by_parent_goal.clear()
        self._by_child_goal.clear()
        self._by_source_agent.clear()
        self._by_target_agent.clear()
        self._by_status.clear()
        self._by_source_run.clear()
        self._by_target_run.clear()

    def __len__(self) -> int:
        return len(self._delegations)

    def __iter__(self) -> Iterator[DelegatedGoal]:
        return iter(self._delegations.values())

    def all(self) -> list[DelegatedGoal]:
        return list(self._delegations.values())


__all__ = [
    "AgentDelegationStore",
    "InMemoryAgentDelegationStore",
]
