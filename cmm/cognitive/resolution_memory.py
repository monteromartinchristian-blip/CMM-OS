"""Phase 8.13 – Resolution Memory Store & Execution Integrator.

Provides the historical memory layer for recording, querying, and auditing cognitive decision execution traces over time.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from threading import RLock
from typing import Any, Protocol, runtime_checkable

from cmm.cognitive.contracts import utc_now
from cmm.cognitive.errors import (
    InvalidResolutionMemoryEntryError,
    ResolutionMemoryConflictError,
)
from cmm.cognitive.resolution_contracts import ContradictionResolutionProposal
from cmm.cognitive.resolution_executor_contracts import (
    ResolutionAuditRecord,
    ResolutionExecutionResult,
)
from cmm.cognitive.resolution_memory_contracts import (
    ResolutionMemoryEntry,
    ResolutionMemoryQuery,
    ResolutionMemoryResult,
    generate_resolution_memory_id,
)
from cmm.cognitive.resolution_policy_contracts import (
    PolicyDecision,
    ResolutionPolicyEvaluation,
)


@runtime_checkable
class ResolutionMemoryStore(Protocol):
    """Protocol for resolution memory store implementations."""

    def save(self, entry: ResolutionMemoryEntry) -> ResolutionMemoryEntry: ...

    def get(self, entry_id: str) -> ResolutionMemoryEntry: ...

    def contains(self, entry_id: str) -> bool: ...

    def list(
        self, query: ResolutionMemoryQuery | None = None
    ) -> ResolutionMemoryResult: ...

    def count(self, query: ResolutionMemoryQuery | None = None) -> int: ...

    def delete(self, entry_id: str) -> None: ...


class InMemoryResolutionMemoryStore:
    """Thread-safe, in-memory implementation of ResolutionMemoryStore."""

    def __init__(self) -> None:
        self._entries: dict[str, ResolutionMemoryEntry] = {}
        self._lock = RLock()

    def save(self, entry: ResolutionMemoryEntry) -> ResolutionMemoryEntry:
        """Store a resolution memory entry immutably."""
        if not isinstance(entry, ResolutionMemoryEntry):
            raise InvalidResolutionMemoryEntryError(
                f"Expected ResolutionMemoryEntry, got {type(entry).__name__}"
            )

        with self._lock:
            existing = self._entries.get(entry.id)
            if existing is not None:
                if existing.serialize() != entry.serialize():
                    raise ResolutionMemoryConflictError(
                        f"ResolutionMemoryEntry with ID '{entry.id}' already exists with different data"
                    )
                return existing

            self._entries[entry.id] = entry
            return entry

    def get(self, entry_id: str) -> ResolutionMemoryEntry:
        """Retrieve a resolution memory entry by ID."""
        if not isinstance(entry_id, str) or not entry_id.strip():
            raise InvalidResolutionMemoryEntryError(
                "entry_id must be a non-empty string"
            )

        with self._lock:
            entry = self._entries.get(entry_id.strip())
            if entry is None:
                raise ResolutionMemoryConflictError(
                    f"ResolutionMemoryEntry not found: '{entry_id.strip()}'"
                )
            return entry

    def contains(self, entry_id: str) -> bool:
        """Check if an entry exists in memory."""
        if not isinstance(entry_id, str) or not entry_id.strip():
            return False

        with self._lock:
            return entry_id.strip() in self._entries

    def delete(self, entry_id: str) -> None:
        """Remove a resolution memory entry by ID."""
        if not isinstance(entry_id, str) or not entry_id.strip():
            raise InvalidResolutionMemoryEntryError(
                "entry_id must be a non-empty string"
            )

        with self._lock:
            key = entry_id.strip()
            if key not in self._entries:
                raise ResolutionMemoryConflictError(
                    f"ResolutionMemoryEntry not found for deletion: '{key}'"
                )
            del self._entries[key]

    def list(
        self, query: ResolutionMemoryQuery | None = None
    ) -> ResolutionMemoryResult:
        """List matching entries filtered and ordered deterministically."""
        with self._lock:
            all_entries = list(self._entries.values())

        if query is None:
            all_entries.sort(key=lambda e: (e.created_at, e.id))
            return ResolutionMemoryResult(
                entries=tuple(all_entries),
                total_count=len(all_entries),
                query=query,
                created_at=utc_now(),
            )

        filtered: list[ResolutionMemoryEntry] = []
        for entry in all_entries:
            if (
                query.contradiction_id is not None
                and entry.contradiction_id != query.contradiction_id
            ):
                continue

            if query.item_id is not None and (
                entry.item_a_id != query.item_id and entry.item_b_id != query.item_id
            ):
                continue

            if query.decision is not None and entry.decision != query.decision:
                continue

            if (
                query.policy_decision is not None
                and entry.policy_decision != query.policy_decision
            ):
                continue

            if (
                query.execution_status is not None
                and entry.execution_status != query.execution_status
            ):
                continue

            if query.actor_id is not None and entry.actor_id != query.actor_id:
                continue

            if (
                query.minimum_confidence is not None
                and entry.confidence < query.minimum_confidence
            ):
                continue

            if (
                query.created_after is not None
                and entry.created_at < query.created_after
            ):
                continue

            if (
                query.created_before is not None
                and entry.created_at > query.created_before
            ):
                continue

            filtered.append(entry)

        filtered.sort(key=lambda e: (e.created_at, e.id))
        total_count = len(filtered)

        offset_val = query.offset
        if offset_val > 0:
            filtered = filtered[offset_val:]

        if query.limit is not None:
            filtered = filtered[: query.limit]

        return ResolutionMemoryResult(
            entries=tuple(filtered),
            total_count=total_count,
            query=query,
            created_at=utc_now(),
        )

    def count(self, query: ResolutionMemoryQuery | None = None) -> int:
        """Count total matching entries matching the query."""
        res = self.list(query)
        return res.total_count


def memory_from_execution_result(
    execution_result: ResolutionExecutionResult,
    proposal: ContradictionResolutionProposal,
    policy_evaluation: ResolutionPolicyEvaluation | None = None,
    audit_record: ResolutionAuditRecord | None = None,
    entry_id: str | None = None,
    created_at: datetime | None = None,
    updated_at: datetime | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> ResolutionMemoryEntry:
    """Transform a resolution execution trace into a historical ResolutionMemoryEntry."""
    if not isinstance(execution_result, ResolutionExecutionResult):
        raise InvalidResolutionMemoryEntryError(
            f"Expected ResolutionExecutionResult, got {type(execution_result).__name__}"
        )
    if not isinstance(proposal, ContradictionResolutionProposal):
        raise InvalidResolutionMemoryEntryError(
            f"Expected ContradictionResolutionProposal, got {type(proposal).__name__}"
        )

    if policy_evaluation is not None and not isinstance(
        policy_evaluation, ResolutionPolicyEvaluation
    ):
        raise InvalidResolutionMemoryEntryError(
            f"Expected ResolutionPolicyEvaluation, got {type(policy_evaluation).__name__}"
        )

    if audit_record is not None and not isinstance(audit_record, ResolutionAuditRecord):
        raise InvalidResolutionMemoryEntryError(
            f"Expected ResolutionAuditRecord, got {type(audit_record).__name__}"
        )

    pol_decision = (
        policy_evaluation.decision
        if policy_evaluation is not None
        else PolicyDecision.AUTO_APPROVED
    )

    actor_id = (
        audit_record.actor_id
        if audit_record is not None and audit_record.actor_id is not None
        else proposal.actor_id
    )

    created_at_dt = created_at or execution_result.started_at
    updated_at_dt = (
        updated_at or execution_result.finished_at or execution_result.started_at
    )

    rationale_items = list(proposal.rationale)
    if policy_evaluation is not None and policy_evaluation.reasons:
        for reason in policy_evaluation.reasons:
            if reason not in rationale_items:
                rationale_items.append(reason)

    merged_metadata: dict[str, Any] = {}
    merged_metadata.update(dict(proposal.metadata))
    merged_metadata.update(dict(execution_result.metadata))
    if metadata:
        merged_metadata.update(dict(metadata))

    computed_id = entry_id
    if computed_id is None:
        computed_id = generate_resolution_memory_id(
            contradiction_id=proposal.contradiction_id,
            proposal_id=proposal.id,
            decision=proposal.decision,
            execution_status=execution_result.status,
            created_at=created_at_dt,
        )

    return ResolutionMemoryEntry(
        id=computed_id,
        contradiction_id=proposal.contradiction_id,
        item_a_id=proposal.item_a_id,
        item_b_id=proposal.item_b_id,
        proposal_id=proposal.id,
        decision=proposal.decision,
        policy_decision=pol_decision,
        execution_status=execution_result.status,
        confidence=proposal.confidence,
        actor_id=actor_id,
        created_at=created_at_dt,
        updated_at=updated_at_dt,
        rationale=tuple(rationale_items),
        evidence_ids=proposal.evidence_ids,
        metadata=merged_metadata,
    )
