"""Phase 9.15 – Checkpoint Manager.

Coordinates resource version capture, Git state, external storage snapshots, memory/knowledge states,
integrity checking, and lock acquisition to create verifiable Runtime Checkpoints.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from cmm.agent_runtime.checkpoint_contracts import (
    Checkpoint,
    CheckpointCreationRequest,
    CheckpointCreationResult,
    compute_checkpoint_fingerprint,
)
from cmm.agent_runtime.checkpoint_integrations import (
    BackupProvider,
    GitStateProvider,
    KnowledgeStateProvider,
    MemoryStateProvider,
    ResourceVersionProvider,
    StorageSnapshotProvider,
)
from cmm.agent_runtime.checkpoint_integrity import CheckpointIntegrityVerifier
from cmm.agent_runtime.checkpoint_repository import (
    CheckpointRepository,
    InMemoryCheckpointRepository,
)
from cmm.agent_runtime.enums import (
    CheckpointIntegrityStatus,
    CheckpointStatus,
)
from cmm.agent_runtime.errors import (
    BackupRequiredError,
    CheckpointCreationError,
    CheckpointIntegrityError,
)
from cmm.agent_runtime.runtime_lock_manager import RuntimeLockManager


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _capture_resource_version(provider: Any, rkey: str) -> str:
    if hasattr(provider, "capture_version"):
        return provider.capture_version(rkey)
    if hasattr(provider, "get_version"):
        return provider.get_version(rkey)
    return "v1.0.0"


class CheckpointManager:
    """Manages the creation, verification, and lifecycle of Runtime Checkpoints."""

    def __init__(
        self,
        repository: CheckpointRepository | None = None,
        lock_manager: RuntimeLockManager | None = None,
        resource_provider: ResourceVersionProvider | None = None,
        git_provider: GitStateProvider | None = None,
        storage_provider: StorageSnapshotProvider | None = None,
        memory_provider: MemoryStateProvider | None = None,
        knowledge_provider: KnowledgeStateProvider | None = None,
        backup_provider: BackupProvider | None = None,
        integrity_verifier: CheckpointIntegrityVerifier | None = None,
    ) -> None:
        self._repository = repository or InMemoryCheckpointRepository()
        self._lock_manager = lock_manager
        self._resource_provider = resource_provider
        self._git_provider = git_provider
        self._storage_provider = storage_provider
        self._memory_provider = memory_provider
        self._knowledge_provider = knowledge_provider
        self._backup_provider = backup_provider
        self._integrity_verifier = integrity_verifier or CheckpointIntegrityVerifier(
            resource_provider=resource_provider,
            git_provider=git_provider,
            storage_provider=storage_provider,
            memory_provider=memory_provider,
            knowledge_provider=knowledge_provider,
            backup_provider=backup_provider,
        )

    @property
    def repository(self) -> CheckpointRepository:
        return self._repository

    def create_checkpoint(
        self,
        request: CheckpointCreationRequest,
        reversible_ops: tuple[str, ...] = (),
        compensable_ops: tuple[str, ...] = (),
        irreversible_effects: tuple[str, ...] = (),
        now: str | None = None,
    ) -> CheckpointCreationResult:
        """Create, verify, activate, and store a Checkpoint for request."""
        timestamp = now or _now_iso()
        checkpoint_id = f"cp-{uuid.uuid4().hex[:12]}"

        # 1. Check backup requirement
        if request.requires_backup:
            if not self._backup_provider:
                raise BackupRequiredError(
                    f"Checkpoint creation requested backup for run '{request.agent_run_id}', but no BackupProvider was configured."
                )
            try:
                backup_id = self._backup_provider.create_backup(request.name)
                if not self._backup_provider.verify_backup(backup_id):
                    raise BackupRequiredError(
                        f"Created backup '{backup_id}' failed verification."
                    )
            except Exception as exc:
                if isinstance(exc, BackupRequiredError):
                    raise
                raise BackupRequiredError(
                    f"Failed to create mandatory backup for checkpoint creation: {exc}"
                ) from exc

        # 2. Acquire Locks (if lock manager is provided)
        acquired_locks: list[str] = []
        if self._lock_manager:
            for rkey in request.resource_keys:
                try:
                    lk = self._lock_manager.acquire(
                        resource_key=rkey,
                        owner_agent_run_id=request.agent_run_id,
                        ttl_seconds=request.ttl_seconds or 300,
                        idempotency_key=request.idempotency_key,
                        now=timestamp,
                    )
                    acquired_locks.append(lk.id)
                except Exception as exc:
                    for lk_id in acquired_locks:
                        try:
                            self._lock_manager.release(lk_id, request.agent_run_id)
                        except Exception:  # noqa: BLE001, S110
                            pass
                    raise CheckpointCreationError(
                        f"Failed to acquire lock for resource '{rkey}': {exc}"
                    ) from exc

        try:
            # 3. Capture Resource Versions
            resource_versions: dict[str, str] = {}
            if self._resource_provider:
                for rkey in request.resource_keys:
                    try:
                        ver = _capture_resource_version(self._resource_provider, rkey)
                        resource_versions[rkey] = ver
                    except Exception as exc:
                        raise CheckpointCreationError(
                            f"Failed to capture version for resource '{rkey}': {exc}"
                        ) from exc

            # 4. Capture Git state
            git_state: dict[str, Any] = {}
            if self._git_provider:
                try:
                    git_state = dict(self._git_provider.capture_git_state())
                except Exception as exc:
                    raise CheckpointCreationError(
                        f"Failed to capture Git state: {exc}"
                    ) from exc

            # 5. Capture External Storage Snapshot
            storage_snapshot_id: str | None = None
            if self._storage_provider and request.name:
                try:
                    storage_snapshot_id = self._storage_provider.create_snapshot(
                        request.name
                    )
                except Exception as exc:
                    raise CheckpointCreationError(
                        f"Failed to capture storage snapshot: {exc}"
                    ) from exc

            # 6. Capture Memory & Knowledge versions
            memory_ver: str | None = None
            if self._memory_provider:
                try:
                    memory_ver = self._memory_provider.capture_memory_version(
                        request.agent_run_id
                    )
                except Exception as exc:
                    raise CheckpointCreationError(
                        f"Failed to capture memory version: {exc}"
                    ) from exc

            knowledge_ver: str | None = None
            if self._knowledge_provider and request.goal_id:
                try:
                    knowledge_ver = self._knowledge_provider.capture_knowledge_version(
                        request.goal_id
                    )
                except Exception as exc:
                    raise CheckpointCreationError(
                        f"Failed to capture knowledge version: {exc}"
                    ) from exc

            # 7. Expiration time calculation
            expires_at: str | None = None
            if request.ttl_seconds:
                dt_now = datetime.fromisoformat(timestamp)
                expires_at = (
                    dt_now + timedelta(seconds=request.ttl_seconds)
                ).isoformat()

            # 8. Compute Fingerprint
            fp = compute_checkpoint_fingerprint(
                checkpoint_id=checkpoint_id,
                agent_run_id=request.agent_run_id,
                goal_id=request.goal_id,
                workflow_id=request.workflow_id,
                iteration_id=request.iteration_id,
                transaction_boundary_id=request.transaction_boundary_id,
                resource_versions=resource_versions,
                git_state=git_state,
                storage_snapshot_id=storage_snapshot_id,
                created_at=timestamp,
            )

            # 9. Create draft checkpoint in CREATING status
            draft_cp = Checkpoint(
                checkpoint_id=checkpoint_id,
                agent_run_id=request.agent_run_id,
                goal_id=request.goal_id,
                workflow_id=request.workflow_id,
                iteration_id=request.iteration_id,
                name=request.name,
                status=CheckpointStatus.CREATING,
                transaction_boundary_id=request.transaction_boundary_id,
                resource_versions=resource_versions,
                git_state=git_state,
                storage_snapshot_id=storage_snapshot_id,
                memory_state_version=memory_ver,
                knowledge_state_version=knowledge_ver,
                reversible_operations=reversible_ops,
                compensable_operations=compensable_ops,
                irreversible_effects=irreversible_effects,
                locks=tuple(acquired_locks),
                fingerprint=fp,
                created_at=timestamp,
                expires_at=expires_at,
                metadata=request.metadata,
            )

            # 10. Integrity Verification
            integrity = self._integrity_verifier.verify(draft_cp, now=timestamp)
            if integrity.status != CheckpointIntegrityStatus.VALID.value:
                raise CheckpointIntegrityError(
                    f"Initial checkpoint integrity check failed: {integrity.issues}"
                )
        except Exception:
            if self._lock_manager:
                for lk_id in acquired_locks:
                    try:
                        self._lock_manager.release(lk_id, request.agent_run_id)
                    except Exception:  # noqa: BLE001, S110
                        pass
            raise

        # 11. Persist and Activate
        self._repository.save_checkpoint(
            draft_cp, idempotency_key=request.idempotency_key
        )
        active_cp = self._repository.update_status(
            checkpoint_id, new_status=CheckpointStatus.ACTIVE
        )

        return CheckpointCreationResult(
            checkpoint_id=active_cp.checkpoint_id,
            status=active_cp.status,
            success=True,
            fingerprint=active_cp.fingerprint,
            created_at=active_cp.created_at,
            checkpoint=active_cp,
        )
