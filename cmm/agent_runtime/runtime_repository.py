"""Phase 9.12 – Agent Runtime Repository.

Defines the storage interface and thread-safe in-memory implementation for runtime entities.
"""

from __future__ import annotations

from threading import RLock
from typing import Any, Protocol

from cmm.agent_runtime.enums import RuntimeLockStatus
from cmm.agent_runtime.errors import (
    AgentIterationNotFoundError,
    DuplicateAgentIterationError,
    DuplicateRuntimeCheckpointError,
    DuplicateRuntimeLockError,
    DuplicateRuntimeTransitionError,
    RuntimeCheckpointNotFoundError,
    RuntimeLockNotFoundError,
)
from cmm.agent_runtime.runtime_loop_contracts import (
    AgentIteration,
    RuntimeCheckpoint,
    RuntimeHeartbeat,
    RuntimeLock,
    RuntimeTransition,
)


class AgentRuntimeRepository(Protocol):
    """Abstract repository protocol for managing runtime loop persistent state."""

    def add_iteration(self, iteration: AgentIteration) -> None: ...
    def get_iteration(self, iteration_id: str) -> AgentIteration: ...
    def update_iteration(self, iteration: AgentIteration) -> None: ...
    def list_iterations(
        self, agent_run_id: str | None = None
    ) -> tuple[AgentIteration, ...]: ...

    def add_transition(self, transition: RuntimeTransition) -> None: ...
    def get_transition(self, transition_id: str) -> RuntimeTransition: ...
    def list_transitions(
        self, agent_run_id: str | None = None
    ) -> tuple[RuntimeTransition, ...]: ...

    def add_checkpoint(self, checkpoint: RuntimeCheckpoint) -> None: ...
    def get_checkpoint(self, checkpoint_id: str) -> RuntimeCheckpoint: ...
    def list_checkpoints(
        self, agent_run_id: str | None = None
    ) -> tuple[RuntimeCheckpoint, ...]: ...
    def get_latest_checkpoint(self, agent_run_id: str) -> RuntimeCheckpoint | None: ...

    def save_heartbeat(self, heartbeat: RuntimeHeartbeat) -> None: ...
    def get_heartbeat(self, agent_run_id: str) -> RuntimeHeartbeat | None: ...
    def list_heartbeats(self) -> tuple[RuntimeHeartbeat, ...]: ...

    def add_lock(self, lock: RuntimeLock) -> None: ...
    def get_lock(self, lock_id: str) -> RuntimeLock: ...
    def update_lock(self, lock: RuntimeLock) -> None: ...
    def list_locks(
        self, owner_agent_run_id: str | None = None
    ) -> tuple[RuntimeLock, ...]: ...
    def find_active_locks(
        self, resource_key: str | None = None
    ) -> tuple[RuntimeLock, ...]: ...

    def get_idempotency_record(self, key: str) -> dict[str, Any] | None: ...
    def store_idempotency_record(
        self, key: str, payload_hash: str, result: Any
    ) -> None: ...


class InMemoryAgentRuntimeRepository:
    """Thread-safe in-memory implementation of AgentRuntimeRepository."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._iterations: dict[str, AgentIteration] = {}
        self._transitions: dict[str, RuntimeTransition] = {}
        self._checkpoints: dict[str, RuntimeCheckpoint] = {}
        self._heartbeats: dict[str, RuntimeHeartbeat] = {}
        self._locks: dict[str, RuntimeLock] = {}
        self._idempotency_records: dict[str, dict[str, Any]] = {}

    # ── Iterations ────────────────────────────────────────────────────────────

    def add_iteration(self, iteration: AgentIteration) -> None:
        with self._lock:
            if iteration.id in self._iterations:
                raise DuplicateAgentIterationError(
                    f"AgentIteration with ID '{iteration.id}' already exists."
                )
            self._iterations[iteration.id] = iteration

    def get_iteration(self, iteration_id: str) -> AgentIteration:
        with self._lock:
            if iteration_id not in self._iterations:
                raise AgentIterationNotFoundError(
                    f"AgentIteration with ID '{iteration_id}' not found."
                )
            return self._iterations[iteration_id]

    def update_iteration(self, iteration: AgentIteration) -> None:
        with self._lock:
            if iteration.id not in self._iterations:
                raise AgentIterationNotFoundError(
                    f"Cannot update non-existent AgentIteration '{iteration.id}'."
                )
            self._iterations[iteration.id] = iteration

    def list_iterations(
        self, agent_run_id: str | None = None
    ) -> tuple[AgentIteration, ...]:
        with self._lock:
            res = list(self._iterations.values())
            if agent_run_id is not None:
                res = [it for it in res if it.agent_run_id == agent_run_id]
            res.sort(key=lambda it: (it.agent_run_id, it.number, it.started_at))
            return tuple(res)

    # ── Transitions ───────────────────────────────────────────────────────────

    def add_transition(self, transition: RuntimeTransition) -> None:
        with self._lock:
            if transition.id in self._transitions:
                raise DuplicateRuntimeTransitionError(
                    f"RuntimeTransition with ID '{transition.id}' already exists."
                )
            self._transitions[transition.id] = transition

    def get_transition(self, transition_id: str) -> RuntimeTransition:
        with self._lock:
            if transition_id not in self._transitions:
                raise DuplicateRuntimeTransitionError(
                    f"RuntimeTransition with ID '{transition_id}' not found."
                )
            return self._transitions[transition_id]

    def list_transitions(
        self, agent_run_id: str | None = None
    ) -> tuple[RuntimeTransition, ...]:
        with self._lock:
            res = list(self._transitions.values())
            if agent_run_id is not None:
                res = [t for t in res if t.agent_run_id == agent_run_id]
            res.sort(key=lambda t: t.created_at)
            return tuple(res)

    # ── Checkpoints ───────────────────────────────────────────────────────────

    def add_checkpoint(self, checkpoint: RuntimeCheckpoint) -> None:
        with self._lock:
            if checkpoint.id in self._checkpoints:
                raise DuplicateRuntimeCheckpointError(
                    f"RuntimeCheckpoint with ID '{checkpoint.id}' already exists."
                )
            self._checkpoints[checkpoint.id] = checkpoint

    def get_checkpoint(self, checkpoint_id: str) -> RuntimeCheckpoint:
        with self._lock:
            if checkpoint_id not in self._checkpoints:
                raise RuntimeCheckpointNotFoundError(
                    f"RuntimeCheckpoint with ID '{checkpoint_id}' not found."
                )
            return self._checkpoints[checkpoint_id]

    def list_checkpoints(
        self, agent_run_id: str | None = None
    ) -> tuple[RuntimeCheckpoint, ...]:
        with self._lock:
            res = list(self._checkpoints.values())
            if agent_run_id is not None:
                res = [cp for cp in res if cp.agent_run_id == agent_run_id]
            res.sort(key=lambda cp: (cp.created_at, cp.state_version))
            return tuple(res)

    def get_latest_checkpoint(self, agent_run_id: str) -> RuntimeCheckpoint | None:
        with self._lock:
            cps = [
                cp
                for cp in self._checkpoints.values()
                if cp.agent_run_id == agent_run_id
            ]
            if not cps:
                return None
            cps.sort(key=lambda cp: (cp.state_version, cp.created_at))
            return cps[-1]

    # ── Heartbeats ────────────────────────────────────────────────────────────

    def save_heartbeat(self, heartbeat: RuntimeHeartbeat) -> None:
        with self._lock:
            self._heartbeats[heartbeat.agent_run_id] = heartbeat

    def get_heartbeat(self, agent_run_id: str) -> RuntimeHeartbeat | None:
        with self._lock:
            return self._heartbeats.get(agent_run_id)

    def list_heartbeats(self) -> tuple[RuntimeHeartbeat, ...]:
        with self._lock:
            res = list(self._heartbeats.values())
            res.sort(key=lambda h: h.last_activity_at)
            return tuple(res)

    # ── Locks ─────────────────────────────────────────────────────────────────

    def add_lock(self, lock: RuntimeLock) -> None:
        with self._lock:
            if lock.id in self._locks:
                raise DuplicateRuntimeLockError(
                    f"RuntimeLock with ID '{lock.id}' already exists."
                )
            self._locks[lock.id] = lock

    def get_lock(self, lock_id: str) -> RuntimeLock:
        with self._lock:
            if lock_id not in self._locks:
                raise RuntimeLockNotFoundError(
                    f"RuntimeLock with ID '{lock_id}' not found."
                )
            return self._locks[lock_id]

    def update_lock(self, lock: RuntimeLock) -> None:
        with self._lock:
            if lock.id not in self._locks:
                raise RuntimeLockNotFoundError(
                    f"Cannot update non-existent RuntimeLock '{lock.id}'."
                )
            self._locks[lock.id] = lock

    def list_locks(
        self, owner_agent_run_id: str | None = None
    ) -> tuple[RuntimeLock, ...]:
        with self._lock:
            res = list(self._locks.values())
            if owner_agent_run_id is not None:
                res = [lk for lk in res if lk.owner_agent_run_id == owner_agent_run_id]
            res.sort(key=lambda lk: lk.acquired_at)
            return tuple(res)

    def find_active_locks(
        self, resource_key: str | None = None
    ) -> tuple[RuntimeLock, ...]:
        with self._lock:
            active = [
                lk
                for lk in self._locks.values()
                if (
                    lk.status
                    in (
                        "active",
                        RuntimeLockStatus.ACTIVE,
                        RuntimeLockStatus.ACTIVE.value,
                    )
                )
            ]
            if resource_key is not None:
                active = [lk for lk in active if lk.resource_key == resource_key]
            active.sort(key=lambda lk: lk.acquired_at)
            return tuple(active)

    # ── Idempotency Records ───────────────────────────────────────────────────

    def get_idempotency_record(self, key: str) -> dict[str, Any] | None:
        with self._lock:
            rec = self._idempotency_records.get(key)
            if rec is None:
                return None
            return dict(rec)

    def store_idempotency_record(
        self, key: str, payload_hash: str, result: Any
    ) -> None:
        with self._lock:
            self._idempotency_records[key] = {
                "payload_hash": payload_hash,
                "result": result,
            }
