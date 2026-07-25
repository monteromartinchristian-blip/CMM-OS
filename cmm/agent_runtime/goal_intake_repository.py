"""Phase 9.3 – Goal Proposal Repository.

Defines abstract interface and in-memory implementation for storing, retrieving,
updating, and querying GoalProposals.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from cmm.agent_runtime.enums import GoalProposalStatus, GoalSource
from cmm.agent_runtime.errors import (
    DuplicateGoalError,
    GoalProposalNotFoundError,
)
from cmm.agent_runtime.goal_intake_contracts import (
    GoalProposal,
    GoalProposalQuery,
)


@runtime_checkable
class GoalProposalRepository(Protocol):
    """Abstract protocol for GoalProposal persistence."""

    def add(self, proposal: GoalProposal) -> GoalProposal:
        """Store a new GoalProposal in the repository."""
        ...

    def get(self, proposal_id: str) -> GoalProposal | None:
        """Retrieve a GoalProposal by ID."""
        ...

    def update(self, proposal: GoalProposal) -> GoalProposal:
        """Update an existing GoalProposal in the repository."""
        ...

    def search(self, query: GoalProposalQuery) -> list[GoalProposal]:
        """Search GoalProposals matching query parameters."""
        ...


class InMemoryGoalProposalRepository:
    """Thread-safe, non-durable in-memory repository for GoalProposals."""

    def __init__(self) -> None:
        self._proposals: dict[str, GoalProposal] = {}

    def add(self, proposal: GoalProposal) -> GoalProposal:
        """Store a new GoalProposal.

        Raises:
            DuplicateGoalError: If a proposal with the same ID already exists.
        """
        if proposal.id in self._proposals:
            raise DuplicateGoalError(
                f"GoalProposal with ID {proposal.id!r} already exists in repository."
            )
        self._proposals[proposal.id] = proposal
        return proposal

    def get(self, proposal_id: str) -> GoalProposal | None:
        """Retrieve a GoalProposal by ID, returning None if not found."""
        return self._proposals.get(proposal_id)

    def update(self, proposal: GoalProposal) -> GoalProposal:
        """Update an existing GoalProposal.

        Raises:
            GoalProposalNotFoundError: If the proposal does not exist.
        """
        if proposal.id not in self._proposals:
            raise GoalProposalNotFoundError(
                f"GoalProposal with ID {proposal.id!r} not found for update."
            )
        self._proposals[proposal.id] = proposal
        return proposal

    def search(self, query: GoalProposalQuery) -> list[GoalProposal]:
        """Search proposals matching status, source, actor, or confirmation filters."""
        results: list[GoalProposal] = []

        for p in self._proposals.values():
            if query.status is not None:
                expected_status = (
                    query.status.value
                    if isinstance(query.status, GoalProposalStatus)
                    else query.status
                )
                actual_status = (
                    p.status.value
                    if isinstance(p.status, GoalProposalStatus)
                    else p.status
                )
                if actual_status != expected_status:
                    continue

            if query.source is not None:
                expected_source = (
                    query.source.value
                    if isinstance(query.source, GoalSource)
                    else query.source
                )
                actual_source = (
                    p.source.value if isinstance(p.source, GoalSource) else p.source
                )
                if actual_source != expected_source:
                    continue

            if (
                query.owner_actor_id is not None
                and p.proposed_owner_actor_id != query.owner_actor_id
            ):
                continue

            if (
                query.requires_confirmation is not None
                and p.requires_confirmation != query.requires_confirmation
            ):
                continue

            results.append(p)

        return results
