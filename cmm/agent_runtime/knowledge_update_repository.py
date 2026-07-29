"""Phase 9.18 – Knowledge Update Repository.

Provides in-memory thread-safe repository for persisting and querying proposals,
decisions, memory update proposals, and execution results with strict idempotency
and fingerprint conflict checks.
"""

from __future__ import annotations

from threading import RLock
from typing import Protocol

from cmm.agent_runtime.enums import KnowledgeProposalStatus
from cmm.agent_runtime.errors import (
    KnowledgeFingerprintError,
    KnowledgeUpdateRepositoryError,
)
from cmm.agent_runtime.knowledge_update_contracts import (
    AgentKnowledgeUpdateProposal,
    KnowledgeUpdateDecision,
    KnowledgeUpdateResult,
    MemoryUpdateProposal,
    MemoryUpdateResult,
)


class KnowledgeUpdateRepository(Protocol):
    """Protocol for persisting and accessing knowledge and memory update proposals."""

    def save_proposal(
        self, proposal: AgentKnowledgeUpdateProposal, idempotency_key: str | None = None
    ) -> AgentKnowledgeUpdateProposal: ...

    def get_proposal(self, proposal_id: str) -> AgentKnowledgeUpdateProposal | None: ...

    def save_decision(
        self, decision: KnowledgeUpdateDecision
    ) -> KnowledgeUpdateDecision: ...

    def get_decision(self, proposal_id: str) -> KnowledgeUpdateDecision | None: ...

    def save_result(self, result: KnowledgeUpdateResult) -> KnowledgeUpdateResult: ...

    def get_result(self, proposal_id: str) -> KnowledgeUpdateResult | None: ...

    def save_memory_proposal(
        self, proposal: MemoryUpdateProposal, idempotency_key: str | None = None
    ) -> MemoryUpdateProposal: ...

    def get_memory_proposal(
        self, memory_proposal_id: str
    ) -> MemoryUpdateProposal | None: ...

    def save_memory_result(self, result: MemoryUpdateResult) -> MemoryUpdateResult: ...

    def get_memory_result(
        self, memory_proposal_id: str
    ) -> MemoryUpdateResult | None: ...

    def get_proposals_by_run(
        self, agent_run_id: str
    ) -> tuple[AgentKnowledgeUpdateProposal, ...]: ...

    def get_proposals_by_goal(
        self, goal_id: str
    ) -> tuple[AgentKnowledgeUpdateProposal, ...]: ...

    def get_proposals_by_outcome_evaluation(
        self, outcome_evaluation_id: str
    ) -> tuple[AgentKnowledgeUpdateProposal, ...]: ...

    def get_pending_proposals(self) -> tuple[AgentKnowledgeUpdateProposal, ...]: ...

    def get_proposal_history(
        self, agent_run_id: str | None = None
    ) -> tuple[AgentKnowledgeUpdateProposal, ...]: ...


class InMemoryKnowledgeUpdateRepository:
    """Thread-safe in-memory repository implementing KnowledgeUpdateRepository."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._proposals: dict[str, AgentKnowledgeUpdateProposal] = {}
        self._decisions: dict[str, KnowledgeUpdateDecision] = {}
        self._results: dict[str, KnowledgeUpdateResult] = {}
        self._memory_proposals: dict[str, MemoryUpdateProposal] = {}
        self._memory_results: dict[str, MemoryUpdateResult] = {}
        self._idempotency_map: dict[
            str, tuple[str, str]
        ] = {}  # key -> (proposal_id, fingerprint)
        self._memory_idempotency_map: dict[str, tuple[str, str]] = {}

    def save_proposal(
        self, proposal: AgentKnowledgeUpdateProposal, idempotency_key: str | None = None
    ) -> AgentKnowledgeUpdateProposal:
        with self._lock:
            key = idempotency_key or proposal.proposal_id
            if key in self._idempotency_map:
                existing_id, existing_fp = self._idempotency_map[key]
                if existing_fp != proposal.fingerprint:
                    raise KnowledgeFingerprintError(
                        f"Fingerprint conflict for idempotency key '{key}': "
                        f"existing fingerprint {existing_fp} != new fingerprint {proposal.fingerprint}"
                    )
                return self._proposals[existing_id]

            if proposal.proposal_id in self._proposals:
                existing = self._proposals[proposal.proposal_id]
                if existing.fingerprint != proposal.fingerprint:
                    raise KnowledgeFingerprintError(
                        f"Proposal '{proposal.proposal_id}' already exists with different fingerprint"
                    )
                return existing

            self._proposals[proposal.proposal_id] = proposal
            self._idempotency_map[key] = (proposal.proposal_id, proposal.fingerprint)
            return proposal

    def get_proposal(self, proposal_id: str) -> AgentKnowledgeUpdateProposal | None:
        with self._lock:
            return self._proposals.get(proposal_id)

    def save_decision(
        self, decision: KnowledgeUpdateDecision
    ) -> KnowledgeUpdateDecision:
        with self._lock:
            if decision.proposal_id not in self._proposals:
                raise KnowledgeUpdateRepositoryError(
                    f"Cannot save decision for unknown proposal '{decision.proposal_id}'"
                )

            if decision.proposal_id in self._decisions:
                existing = self._decisions[decision.proposal_id]
                if (
                    existing.status
                    in (
                        KnowledgeProposalStatus.APPLIED,
                        KnowledgeProposalStatus.REJECTED,
                        KnowledgeProposalStatus.CANCELLED,
                    )
                    and existing.status != decision.status
                ):
                    raise KnowledgeUpdateRepositoryError(
                        f"Cannot mutate final proposal decision from '{existing.status.value}' to '{decision.status.value}'"
                    )

            self._decisions[decision.proposal_id] = decision
            return decision

    def get_decision(self, proposal_id: str) -> KnowledgeUpdateDecision | None:
        with self._lock:
            return self._decisions.get(proposal_id)

    def save_result(self, result: KnowledgeUpdateResult) -> KnowledgeUpdateResult:
        with self._lock:
            if result.proposal_id not in self._proposals:
                raise KnowledgeUpdateRepositoryError(
                    f"Cannot save result for unknown proposal '{result.proposal_id}'"
                )
            if result.proposal_id in self._results:
                existing = self._results[result.proposal_id]
                if (
                    existing.status == KnowledgeProposalStatus.APPLIED
                    and result.status != KnowledgeProposalStatus.APPLIED
                ):
                    raise KnowledgeUpdateRepositoryError(
                        f"Cannot overwrite APPLIED result for proposal '{result.proposal_id}'"
                    )
            self._results[result.proposal_id] = result
            return result

    def get_result(self, proposal_id: str) -> KnowledgeUpdateResult | None:
        with self._lock:
            return self._results.get(proposal_id)

    def save_memory_proposal(
        self, proposal: MemoryUpdateProposal, idempotency_key: str | None = None
    ) -> MemoryUpdateProposal:
        with self._lock:
            key = idempotency_key or proposal.memory_proposal_id
            if key in self._memory_idempotency_map:
                existing_id, existing_fp = self._memory_idempotency_map[key]
                if existing_fp != proposal.fingerprint:
                    raise KnowledgeFingerprintError(
                        f"Fingerprint conflict for memory idempotency key '{key}'"
                    )
                return self._memory_proposals[existing_id]

            self._memory_proposals[proposal.memory_proposal_id] = proposal
            self._memory_idempotency_map[key] = (
                proposal.memory_proposal_id,
                proposal.fingerprint,
            )
            return proposal

    def get_memory_proposal(
        self, memory_proposal_id: str
    ) -> MemoryUpdateProposal | None:
        with self._lock:
            return self._memory_proposals.get(memory_proposal_id)

    def save_memory_result(self, result: MemoryUpdateResult) -> MemoryUpdateResult:
        with self._lock:
            if result.memory_proposal_id not in self._memory_proposals:
                raise KnowledgeUpdateRepositoryError(
                    f"Cannot save memory result for unknown memory proposal '{result.memory_proposal_id}'"
                )
            self._memory_results[result.memory_proposal_id] = result
            return result

    def get_memory_result(self, memory_proposal_id: str) -> MemoryUpdateResult | None:
        with self._lock:
            return self._memory_results.get(memory_proposal_id)

    def get_proposals_by_run(
        self, agent_run_id: str
    ) -> tuple[AgentKnowledgeUpdateProposal, ...]:
        with self._lock:
            return tuple(
                p for p in self._proposals.values() if p.agent_run_id == agent_run_id
            )

    def get_proposals_by_goal(
        self, goal_id: str
    ) -> tuple[AgentKnowledgeUpdateProposal, ...]:
        with self._lock:
            return tuple(p for p in self._proposals.values() if p.goal_id == goal_id)

    def get_proposals_by_outcome_evaluation(
        self, outcome_evaluation_id: str
    ) -> tuple[AgentKnowledgeUpdateProposal, ...]:
        with self._lock:
            return tuple(
                p
                for p in self._proposals.values()
                if p.outcome_evaluation_id == outcome_evaluation_id
            )

    def get_pending_proposals(self) -> tuple[AgentKnowledgeUpdateProposal, ...]:
        with self._lock:
            pending = []
            for p in self._proposals.values():
                d = self._decisions.get(p.proposal_id)
                if d is None or d.status in (
                    KnowledgeProposalStatus.PENDING,
                    KnowledgeProposalStatus.EVALUATING,
                    KnowledgeProposalStatus.APPROVAL_REQUIRED,
                ):
                    pending.append(p)
            return tuple(pending)

    def get_proposal_history(
        self, agent_run_id: str | None = None
    ) -> tuple[AgentKnowledgeUpdateProposal, ...]:
        with self._lock:
            if agent_run_id:
                return self.get_proposals_by_run(agent_run_id)
            return tuple(self._proposals.values())
