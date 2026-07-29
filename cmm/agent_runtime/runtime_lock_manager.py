"""Phase 9.12 – Agent Runtime Lock Manager.

Provides thread-safe lock management, conflict detection, TTL expiration, and goal-level exclusion.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from threading import RLock

from cmm.agent_runtime.enums import RuntimeLockStatus, RuntimeLockType
from cmm.agent_runtime.errors import (
    RuntimeLockConflictError,
    RuntimeLockNotFoundError,
)
from cmm.agent_runtime.runtime_loop_contracts import (
    RuntimeLock,
    _ensure_aware_iso,
    current_aware_iso,
)
from cmm.agent_runtime.runtime_repository import AgentRuntimeRepository


def _parse_iso(dt_str: str) -> datetime:
    return datetime.fromisoformat(dt_str)


class RuntimeLockManager:
    """Manages resource locks, goal exclusion, TTL expiration, and atomic lock acquisition."""

    def __init__(self, repository: AgentRuntimeRepository) -> None:
        self._repository = repository
        self._rlock = RLock()

    def acquire(
        self,
        resource_key: str,
        owner_agent_run_id: str,
        lock_type: RuntimeLockType | str = RuntimeLockType.EXCLUSIVE,
        ttl_seconds: int = 300,
        idempotency_key: str | None = None,
        now: str | None = None,
    ) -> RuntimeLock:
        """Acquire a lock for resource_key on behalf of owner_agent_run_id."""
        with self._rlock:
            timestamp = now or current_aware_iso()
            _ensure_aware_iso(timestamp, "now")

            # Expire due locks first
            self.expire_due(now=timestamp)

            lt_str = (
                lock_type.value
                if isinstance(lock_type, RuntimeLockType)
                else str(lock_type)
            )
            active_locks = self._repository.find_active_locks(resource_key=resource_key)

            # Check conflict logic
            for active in active_locks:
                if active.owner_agent_run_id == owner_agent_run_id:
                    # Idempotent re-acquisition check
                    if (
                        idempotency_key is not None
                        and active.metadata.get("idempotency_key") == idempotency_key
                    ):
                        return active
                    if active.lock_type == lt_str:
                        # Renew TTL for same owner
                        exp_dt = datetime.fromisoformat(timestamp) + timedelta(
                            seconds=ttl_seconds
                        )
                        renewed = RuntimeLock(
                            id=active.id,
                            resource_key=active.resource_key,
                            owner_agent_run_id=active.owner_agent_run_id,
                            lock_type=active.lock_type,
                            status=active.status,
                            acquired_at=active.acquired_at,
                            expires_at=exp_dt.isoformat(),
                            released_at=active.released_at,
                            metadata=active.metadata,
                        )
                        self._repository.update_lock(renewed)
                        return renewed

                # Collision by another owner
                if lt_str in (
                    RuntimeLockType.EXCLUSIVE.value,
                    RuntimeLockType.GOAL.value,
                    RuntimeLockType.WRITE.value,
                    RuntimeLockType.COMPLETION.value,
                ) or active.lock_type in (
                    RuntimeLockType.EXCLUSIVE.value,
                    RuntimeLockType.GOAL.value,
                    RuntimeLockType.WRITE.value,
                    RuntimeLockType.COMPLETION.value,
                ):
                    raise RuntimeLockConflictError(
                        f"Lock conflict on resource '{resource_key}': held by agent_run '{active.owner_agent_run_id}' (lock_id={active.id})."
                    )

            # Create new lock
            lock_id = f"lock-{uuid.uuid4().hex[:12]}"
            dt_now = datetime.fromisoformat(timestamp)
            dt_exp = dt_now + timedelta(seconds=ttl_seconds)
            exp_iso = dt_exp.isoformat()

            meta = {}
            if idempotency_key:
                meta["idempotency_key"] = idempotency_key

            new_lock = RuntimeLock(
                id=lock_id,
                resource_key=resource_key,
                owner_agent_run_id=owner_agent_run_id,
                lock_type=lt_str,
                status=RuntimeLockStatus.ACTIVE,
                acquired_at=timestamp,
                expires_at=exp_iso,
                metadata=meta,
            )
            self._repository.add_lock(new_lock)
            return new_lock

    def acquire_goal_lock(
        self,
        goal_id: str,
        owner_agent_run_id: str,
        ttl_seconds: int = 600,
        idempotency_key: str | None = None,
        now: str | None = None,
    ) -> RuntimeLock:
        """Convenience method to acquire exclusive goal lock."""
        return self.acquire(
            resource_key=f"goal:{goal_id}",
            owner_agent_run_id=owner_agent_run_id,
            lock_type=RuntimeLockType.GOAL,
            ttl_seconds=ttl_seconds,
            idempotency_key=idempotency_key,
            now=now,
        )

    def release(
        self,
        lock_id: str,
        owner_agent_run_id: str,
        now: str | None = None,
    ) -> RuntimeLock:
        """Release an active lock."""
        with self._rlock:
            timestamp = now or current_aware_iso()
            lock = self._repository.get_lock(lock_id)
            if lock.owner_agent_run_id != owner_agent_run_id:
                raise RuntimeLockConflictError(
                    f"AgentRun '{owner_agent_run_id}' does not own lock '{lock_id}' (owned by '{lock.owner_agent_run_id}')."
                )

            if lock.status in (RuntimeLockStatus.RELEASED.value, "released"):
                return lock

            released_lock = RuntimeLock(
                id=lock.id,
                resource_key=lock.resource_key,
                owner_agent_run_id=lock.owner_agent_run_id,
                lock_type=lock.lock_type,
                status=RuntimeLockStatus.RELEASED,
                acquired_at=lock.acquired_at,
                expires_at=lock.expires_at,
                released_at=timestamp,
                metadata=lock.metadata,
            )
            self._repository.update_lock(released_lock)
            return released_lock

    def release_all_for_owner(
        self,
        owner_agent_run_id: str,
        now: str | None = None,
    ) -> tuple[RuntimeLock, ...]:
        """Release all active locks owned by owner_agent_run_id."""
        with self._rlock:
            timestamp = now or current_aware_iso()
            active_locks = self._repository.list_locks(
                owner_agent_run_id=owner_agent_run_id
            )
            released = []
            for lk in active_locks:
                if lk.status in (RuntimeLockStatus.ACTIVE.value, "active"):
                    rel = self.release(lk.id, owner_agent_run_id, now=timestamp)
                    released.append(rel)
            return tuple(released)

    def renew(
        self,
        lock_id: str,
        owner_agent_run_id: str,
        ttl_seconds: int = 300,
        now: str | None = None,
    ) -> RuntimeLock:
        """Renew an existing active lock's expiration timestamp."""
        with self._rlock:
            timestamp = now or current_aware_iso()
            lock = self._repository.get_lock(lock_id)
            if lock.owner_agent_run_id != owner_agent_run_id:
                raise RuntimeLockConflictError(
                    f"AgentRun '{owner_agent_run_id}' does not own lock '{lock_id}'."
                )
            if lock.status not in (RuntimeLockStatus.ACTIVE.value, "active"):
                raise RuntimeLockNotFoundError(
                    f"Cannot renew non-active lock '{lock_id}' (status={lock.status})."
                )

            dt_now = datetime.fromisoformat(timestamp)
            dt_exp = dt_now + timedelta(seconds=ttl_seconds)
            renewed = RuntimeLock(
                id=lock.id,
                resource_key=lock.resource_key,
                owner_agent_run_id=lock.owner_agent_run_id,
                lock_type=lock.lock_type,
                status=RuntimeLockStatus.ACTIVE,
                acquired_at=lock.acquired_at,
                expires_at=dt_exp.isoformat(),
                released_at=lock.released_at,
                metadata=lock.metadata,
            )
            self._repository.update_lock(renewed)
            return renewed

    def expire_due(self, now: str | None = None) -> tuple[RuntimeLock, ...]:
        """Expire all active locks whose expiration time has passed."""
        with self._rlock:
            timestamp = now or current_aware_iso()
            dt_now = datetime.fromisoformat(timestamp)
            active_locks = self._repository.find_active_locks()
            expired_list = []

            for lk in active_locks:
                dt_exp = datetime.fromisoformat(lk.expires_at)
                if dt_now >= dt_exp:
                    exp_lk = RuntimeLock(
                        id=lk.id,
                        resource_key=lk.resource_key,
                        owner_agent_run_id=lk.owner_agent_run_id,
                        lock_type=lk.lock_type,
                        status=RuntimeLockStatus.EXPIRED,
                        acquired_at=lk.acquired_at,
                        expires_at=lk.expires_at,
                        released_at=lk.released_at,
                        metadata=lk.metadata,
                    )
                    self._repository.update_lock(exp_lk)
                    expired_list.append(exp_lk)
            return tuple(expired_list)

    def assert_available(
        self,
        resource_key: str,
        owner_agent_run_id: str,
        lock_type: RuntimeLockType | str = RuntimeLockType.EXCLUSIVE,
        now: str | None = None,
    ) -> None:
        """Assert that resource_key is available for owner_agent_run_id without acquiring."""
        with self._rlock:
            timestamp = now or current_aware_iso()
            self.expire_due(now=timestamp)
            active_locks = self._repository.find_active_locks(resource_key=resource_key)
            lt_str = (
                lock_type.value
                if isinstance(lock_type, RuntimeLockType)
                else str(lock_type)
            )

            for lk in active_locks:
                if lk.owner_agent_run_id != owner_agent_run_id and (
                    lt_str
                    in (
                        RuntimeLockType.EXCLUSIVE.value,
                        RuntimeLockType.GOAL.value,
                        RuntimeLockType.WRITE.value,
                    )
                    or lk.lock_type
                    in (
                        RuntimeLockType.EXCLUSIVE.value,
                        RuntimeLockType.GOAL.value,
                        RuntimeLockType.WRITE.value,
                    )
                ):
                    raise RuntimeLockConflictError(
                        f"Resource '{resource_key}' is locked by agent_run '{lk.owner_agent_run_id}'."
                    )

    def list_active(
        self, owner_agent_run_id: str | None = None
    ) -> tuple[RuntimeLock, ...]:
        """List active non-expired locks."""
        with self._rlock:
            active = self._repository.find_active_locks()
            if owner_agent_run_id:
                active = tuple(
                    lk for lk in active if lk.owner_agent_run_id == owner_agent_run_id
                )
            return active
