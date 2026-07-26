"""Phase 9.15 – Checkpoint Repository.

Provides thread-safe storage, query, idempotency control, and lifecycle transition enforcement
for Runtime Checkpoints.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping
from threading import RLock
from typing import Any

from cmm.agent_runtime.checkpoint_contracts import Checkpoint
from cmm.agent_runtime.enums import CheckpointStatus
from cmm.agent_runtime.errors import (
    CheckpointAlreadyExistsError,
    CheckpointNotFoundError,
    CheckpointRepositoryError,
)

# Terminal states for a Checkpoint
TERMINAL_CHECKPOINT_STATES: frozenset[str] = frozenset(
    {
        CheckpointStatus.RESTORED.value,
        CheckpointStatus.DELETED.value,
        CheckpointStatus.FAILED.value,
        CheckpointStatus.EXPIRED.value,
        CheckpointStatus.INVALID.value,
    }
)

VALID_CHECKPOINT_TRANSITIONS: Mapping[str, frozenset[str]] = {
    CheckpointStatus.CREATING.value: frozenset(
        {
            CheckpointStatus.ACTIVE.value,
            CheckpointStatus.FAILED.value,
            CheckpointStatus.INVALID.value,
            CheckpointStatus.DELETED.value,
        }
    ),
    CheckpointStatus.ACTIVE.value: frozenset(
        {
            CheckpointStatus.RESTORING.value,
            CheckpointStatus.RESTORED.value,
            CheckpointStatus.EXPIRED.value,
            CheckpointStatus.INVALID.value,
            CheckpointStatus.DELETED.value,
            CheckpointStatus.FAILED.value,
        }
    ),
    CheckpointStatus.RESTORING.value: frozenset(
        {
            CheckpointStatus.RESTORED.value,
            CheckpointStatus.ACTIVE.value,
            CheckpointStatus.FAILED.value,
            CheckpointStatus.INVALID.value,
        }
    ),
    CheckpointStatus.RESTORED.value: frozenset(),
    CheckpointStatus.EXPIRED.value: frozenset(),
    CheckpointStatus.INVALID.value: frozenset(),
    CheckpointStatus.DELETED.value: frozenset(),
    CheckpointStatus.FAILED.value: frozenset(),
}


class CheckpointRepository(ABC):
    """Abstract protocol for Checkpoint persistence."""

    @abstractmethod
    def save_checkpoint(
        self, checkpoint: Checkpoint, idempotency_key: str | None = None
    ) -> Checkpoint:
        """Save a new checkpoint or handle idempotent re-invocation."""

    @abstractmethod
    def get_checkpoint(self, checkpoint_id: str) -> Checkpoint:
        """Retrieve checkpoint by ID or raise CheckpointNotFoundError."""

    @abstractmethod
    def find_active(self, agent_run_id: str | None = None) -> tuple[Checkpoint, ...]:
        """Find active checkpoints."""

    @abstractmethod
    def find_by_agent_run(self, agent_run_id: str) -> tuple[Checkpoint, ...]:
        """Find all checkpoints for a given agent_run_id."""

    @abstractmethod
    def find_by_workflow(self, workflow_id: str) -> tuple[Checkpoint, ...]:
        """Find all checkpoints for a given workflow_id."""

    @abstractmethod
    def find_by_transaction_boundary(
        self, transaction_boundary_id: str
    ) -> tuple[Checkpoint, ...]:
        """Find all checkpoints for a given transaction_boundary_id."""

    @abstractmethod
    def update_status(
        self,
        checkpoint_id: str,
        new_status: CheckpointStatus | str,
        restored_at: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> Checkpoint:
        """Update checkpoint status adhering to lifecycle transition rules."""


class InMemoryCheckpointRepository(CheckpointRepository):
    """Thread-safe in-memory implementation of CheckpointRepository."""

    def __init__(self) -> None:
        self._checkpoints: dict[str, Checkpoint] = {}
        self._idempotency_map: dict[
            str, tuple[str, str]
        ] = {}  # key -> (checkpoint_id, fingerprint)
        self._rlock = RLock()

    def save_checkpoint(
        self, checkpoint: Checkpoint, idempotency_key: str | None = None
    ) -> Checkpoint:
        with self._rlock:
            if idempotency_key and idempotency_key in self._idempotency_map:
                existing_id, existing_fp = self._idempotency_map[idempotency_key]
                if existing_fp == checkpoint.fingerprint:
                    return self._checkpoints[existing_id]
                else:
                    raise CheckpointAlreadyExistsError(
                        f"Idempotency key '{idempotency_key}' re-used with conflicting fingerprint."
                    )

            if checkpoint.checkpoint_id in self._checkpoints:
                existing = self._checkpoints[checkpoint.checkpoint_id]
                if existing.fingerprint == checkpoint.fingerprint:
                    return existing
                raise CheckpointAlreadyExistsError(
                    f"Checkpoint '{checkpoint.checkpoint_id}' already exists."
                )

            self._checkpoints[checkpoint.checkpoint_id] = checkpoint
            if idempotency_key:
                self._idempotency_map[idempotency_key] = (
                    checkpoint.checkpoint_id,
                    checkpoint.fingerprint,
                )
            return checkpoint

    def get_checkpoint(self, checkpoint_id: str) -> Checkpoint:
        with self._rlock:
            if checkpoint_id not in self._checkpoints:
                raise CheckpointNotFoundError(
                    f"Checkpoint '{checkpoint_id}' was not found in repository."
                )
            return self._checkpoints[checkpoint_id]

    def find_active(self, agent_run_id: str | None = None) -> tuple[Checkpoint, ...]:
        with self._rlock:
            active_list = []
            for cp in self._checkpoints.values():
                if cp.status == CheckpointStatus.ACTIVE.value and (
                    agent_run_id is None or cp.agent_run_id == agent_run_id
                ):
                    active_list.append(cp)
            return tuple(active_list)

    def find_by_agent_run(self, agent_run_id: str) -> tuple[Checkpoint, ...]:
        with self._rlock:
            return tuple(
                cp
                for cp in self._checkpoints.values()
                if cp.agent_run_id == agent_run_id
            )

    def find_by_workflow(self, workflow_id: str) -> tuple[Checkpoint, ...]:
        with self._rlock:
            return tuple(
                cp for cp in self._checkpoints.values() if cp.workflow_id == workflow_id
            )

    def find_by_transaction_boundary(
        self, transaction_boundary_id: str
    ) -> tuple[Checkpoint, ...]:
        with self._rlock:
            return tuple(
                cp
                for cp in self._checkpoints.values()
                if cp.transaction_boundary_id == transaction_boundary_id
            )

    def update_status(
        self,
        checkpoint_id: str,
        new_status: CheckpointStatus | str,
        restored_at: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> Checkpoint:
        with self._rlock:
            existing = self.get_checkpoint(checkpoint_id)
            target_st = (
                new_status.value
                if isinstance(new_status, CheckpointStatus)
                else str(new_status)
            )

            if existing.status == target_st:
                return existing

            # Validate state transition
            allowed = VALID_CHECKPOINT_TRANSITIONS.get(existing.status, frozenset())
            if target_st not in allowed:
                raise CheckpointRepositoryError(
                    f"Invalid checkpoint status transition from '{existing.status}' to '{target_st}'."
                )

            new_meta = dict(existing.metadata)
            if metadata:
                new_meta.update(metadata)

            updated = Checkpoint(
                checkpoint_id=existing.checkpoint_id,
                agent_run_id=existing.agent_run_id,
                goal_id=existing.goal_id,
                workflow_id=existing.workflow_id,
                iteration_id=existing.iteration_id,
                name=existing.name,
                status=target_st,
                transaction_boundary_id=existing.transaction_boundary_id,
                resource_versions=existing.resource_versions,
                git_state=existing.git_state,
                storage_snapshot_id=existing.storage_snapshot_id,
                memory_state_version=existing.memory_state_version,
                knowledge_state_version=existing.knowledge_state_version,
                reversible_operations=existing.reversible_operations,
                compensable_operations=existing.compensable_operations,
                irreversible_effects=existing.irreversible_effects,
                locks=existing.locks,
                fingerprint=existing.fingerprint,
                created_at=existing.created_at,
                expires_at=existing.expires_at,
                restored_at=restored_at or existing.restored_at,
                metadata=new_meta,
            )
            self._checkpoints[checkpoint_id] = updated
            return updated
