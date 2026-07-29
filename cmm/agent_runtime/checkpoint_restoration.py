"""Phase 9.15 – Checkpoint Restoration Manager.

Coordinates thread-safe, verified restoration of state from Runtime Checkpoints.
Enforces exclusive lock ownership, integrity checks, reverse-order restoration,
compensation actions, Git/storage/memory/knowledge state restoration, post-restoration
validation, and separate preservation of original vs restoration errors.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime, timezone

from cmm.agent_runtime.checkpoint_contracts import (
    CheckpointDifference,
    CheckpointRestorationRequest,
    CheckpointRestorationResult,
    CompensationAction,
    RestorationValidationResult,
)
from cmm.agent_runtime.checkpoint_integrations import (
    DefaultRestorationValidator,
    GitStateProvider,
    KnowledgeStateProvider,
    MemoryStateProvider,
    ResourceVersionProvider,
    RestorationValidator,
    StorageSnapshotProvider,
)
from cmm.agent_runtime.checkpoint_integrity import CheckpointIntegrityVerifier
from cmm.agent_runtime.checkpoint_repository import CheckpointRepository
from cmm.agent_runtime.enums import (
    CheckpointIntegrityStatus,
    CheckpointStatus,
    RestorationStatus,
)
from cmm.agent_runtime.errors import (
    CheckpointExpiredError,
    CheckpointIntegrityError,
    CheckpointInvalidError,
    CheckpointRestorationBlockedError,
    CheckpointRestorationError,
    CheckpointRestorationValidationError,
    CompensationError,
    GitStateRestorationError,
    KnowledgeStateRestorationError,
    MemoryStateRestorationError,
    ResourceVersionMismatchError,
    StorageSnapshotRestorationError,
)
from cmm.agent_runtime.runtime_lock_manager import RuntimeLockManager


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class CheckpointRestorationManager:
    """Manages secure, verified restoration of checkpoint states."""

    def __init__(
        self,
        repository: CheckpointRepository,
        lock_manager: RuntimeLockManager | None = None,
        resource_provider: ResourceVersionProvider | None = None,
        git_provider: GitStateProvider | None = None,
        storage_provider: StorageSnapshotProvider | None = None,
        memory_provider: MemoryStateProvider | None = None,
        knowledge_provider: KnowledgeStateProvider | None = None,
        integrity_verifier: CheckpointIntegrityVerifier | None = None,
        restoration_validator: RestorationValidator | None = None,
        compensation_handlers: Mapping[str, Callable[[CompensationAction], bool]]
        | None = None,
    ) -> None:
        self._repository = repository
        self._lock_manager = lock_manager
        self._resource_provider = resource_provider
        self._git_provider = git_provider
        self._storage_provider = storage_provider
        self._memory_provider = memory_provider
        self._knowledge_provider = knowledge_provider
        self._integrity_verifier = integrity_verifier or CheckpointIntegrityVerifier(
            resource_provider=resource_provider,
            git_provider=git_provider,
            storage_provider=storage_provider,
            memory_provider=memory_provider,
            knowledge_provider=knowledge_provider,
        )
        self._restoration_validator = (
            restoration_validator
            or DefaultRestorationValidator(
                resource_provider=resource_provider,
                git_provider=git_provider,
            )
        )
        self._compensation_handlers = dict(compensation_handlers or {})

    def register_compensation_handler(
        self, handler_name: str, handler: Callable[[CompensationAction], bool]
    ) -> None:
        self._compensation_handlers[handler_name] = handler

    def restore_checkpoint(
        self,
        request: CheckpointRestorationRequest,
        original_error: str | None = None,
        compensations: tuple[CompensationAction, ...] = (),
        now: str | None = None,
    ) -> CheckpointRestorationResult:
        """Execute controlled restoration of a Checkpoint."""
        timestamp = now or _now_iso()
        cp = self._repository.get_checkpoint(request.checkpoint_id)

        # 1. Check status (must be ACTIVE)
        if cp.status == CheckpointStatus.EXPIRED.value:
            raise CheckpointExpiredError(
                f"Cannot restore expired checkpoint '{request.checkpoint_id}'."
            )
        if cp.status in (
            CheckpointStatus.INVALID.value,
            CheckpointStatus.DELETED.value,
            CheckpointStatus.FAILED.value,
            CheckpointStatus.RESTORED.value,
        ):
            raise CheckpointInvalidError(
                f"Cannot restore checkpoint '{request.checkpoint_id}' with status '{cp.status}'."
            )
        if cp.status != CheckpointStatus.ACTIVE.value and not request.force:
            raise CheckpointInvalidError(
                f"Checkpoint '{request.checkpoint_id}' is not ACTIVE (status='{cp.status}')."
            )

        # 2. Check Expiration
        if cp.expires_at:
            dt_now = datetime.fromisoformat(timestamp)
            dt_exp = datetime.fromisoformat(cp.expires_at)
            if dt_now >= dt_exp:
                self._repository.update_status(
                    cp.checkpoint_id, CheckpointStatus.EXPIRED
                )
                raise CheckpointExpiredError(
                    f"Checkpoint '{request.checkpoint_id}' expired at '{cp.expires_at}'."
                )

        # 3. Verify Integrity
        integrity = self._integrity_verifier.verify(cp, now=timestamp)
        if (
            integrity.status
            not in (
                CheckpointIntegrityStatus.VALID.value,
                CheckpointIntegrityStatus.VERSION_MISMATCH.value,
            )
            and not request.force
        ):
            raise CheckpointIntegrityError(
                f"Checkpoint '{request.checkpoint_id}' integrity check failed: {integrity.issues}"
            )

        # 4. Acquire Exclusive Locks & Check Ownership/Concurrency
        acquired_locks: list[str] = []
        if self._lock_manager:
            for rkey in cp.resource_versions:
                try:
                    lk = self._lock_manager.acquire(
                        resource_key=rkey,
                        owner_agent_run_id=request.agent_run_id,
                        ttl_seconds=300,
                        now=timestamp,
                    )
                    acquired_locks.append(lk.id)
                except Exception as exc:
                    # Release any acquired
                    for lk_id in acquired_locks:
                        try:
                            self._lock_manager.release(lk_id, request.agent_run_id)
                        except Exception as rel_exc:  # noqa: BLE001
                            _release_error = (
                                f"Failed to release lock '{lk_id}': {rel_exc}"
                            )
                    raise CheckpointRestorationBlockedError(
                        f"Lock acquisition failed during restoration for resource '{rkey}': {exc}"
                    ) from exc

        # Update status to RESTORING
        self._repository.update_status(cp.checkpoint_id, CheckpointStatus.RESTORING)

        restored_resources: list[str] = []
        failed_resources: list[str] = []
        version_diffs: dict[str, tuple[str, str]] = {}
        restoration_err: str | None = None
        partial = False

        try:
            # 5. Check resource versions and differences
            if self._resource_provider:
                for rkey, expected_v in cp.resource_versions.items():
                    current_v = self._resource_provider.capture_version(rkey)
                    if current_v != expected_v:
                        version_diffs[rkey] = (current_v, expected_v)
                        if not request.force and not cp.resource_versions:
                            raise ResourceVersionMismatchError(
                                f"Resource version changed for '{rkey}': got '{current_v}', expected '{expected_v}'."
                            )

                    # Restore resource
                    try:
                        ok = self._resource_provider.restore_version(rkey, expected_v)
                        if ok:
                            restored_resources.append(rkey)
                        else:
                            failed_resources.append(rkey)
                            partial = True
                    except Exception as exc:
                        failed_resources.append(rkey)
                        partial = True
                        raise CheckpointRestorationError(
                            f"Failed to restore resource '{rkey}': {exc}"
                        ) from exc

            # 6. Execute Compensations if provided (LIFO order)
            for comp in reversed(compensations):
                handler = self._compensation_handlers.get(comp.handler_name)
                if handler:
                    try:
                        ok = handler(comp)
                        if ok:
                            restored_resources.append(f"compensation:{comp.action_id}")
                        else:
                            failed_resources.append(f"compensation:{comp.action_id}")
                            partial = True
                    except Exception as exc:
                        failed_resources.append(f"compensation:{comp.action_id}")
                        partial = True
                        raise CompensationError(
                            f"Compensation handler '{comp.handler_name}' failed: {exc}"
                        ) from exc
                else:
                    # Record non-handled compensation
                    restored_resources.append(f"compensation_noted:{comp.action_id}")

            # 7. Restore Git State
            if self._git_provider and cp.git_state:
                try:
                    ok = self._git_provider.restore_git_state(cp.git_state)
                    if ok:
                        restored_resources.append("git_state")
                    else:
                        failed_resources.append("git_state")
                        partial = True
                except Exception as exc:
                    failed_resources.append("git_state")
                    partial = True
                    raise GitStateRestorationError(
                        f"Failed to restore Git state: {exc}"
                    ) from exc

            # 8. Restore Storage Snapshot
            if self._storage_provider and cp.storage_snapshot_id:
                try:
                    ok = self._storage_provider.restore_snapshot(cp.storage_snapshot_id)
                    if ok:
                        restored_resources.append("storage_snapshot")
                    else:
                        failed_resources.append("storage_snapshot")
                        partial = True
                except Exception as exc:
                    failed_resources.append("storage_snapshot")
                    partial = True
                    raise StorageSnapshotRestorationError(
                        f"Failed to restore storage snapshot '{cp.storage_snapshot_id}': {exc}"
                    ) from exc

            # 9. Restore Memory State
            if self._memory_provider and cp.memory_state_version:
                try:
                    ok = self._memory_provider.restore_memory_version(
                        cp.agent_run_id, cp.memory_state_version
                    )
                    if ok:
                        restored_resources.append("memory_state")
                    else:
                        failed_resources.append("memory_state")
                        partial = True
                except Exception as exc:
                    failed_resources.append("memory_state")
                    partial = True
                    raise MemoryStateRestorationError(
                        f"Failed to restore memory state: {exc}"
                    ) from exc

            # 10. Restore Knowledge State
            if self._knowledge_provider and cp.knowledge_state_version:
                try:
                    ok = self._knowledge_provider.restore_knowledge_version(
                        cp.goal_id, cp.knowledge_state_version
                    )
                    if ok:
                        restored_resources.append("knowledge_state")
                    else:
                        failed_resources.append("knowledge_state")
                        partial = True
                except Exception as exc:
                    failed_resources.append("knowledge_state")
                    partial = True
                    raise KnowledgeStateRestorationError(
                        f"Failed to restore knowledge state: {exc}"
                    ) from exc

            # 11. Execute Post-Restoration Validation
            val_res: RestorationValidationResult = (
                self._restoration_validator.validate_restored_state(
                    cp.checkpoint_id, cp.resource_versions, cp.git_state
                )
            )

            if not val_res.valid:
                self._repository.update_status(
                    cp.checkpoint_id,
                    new_status=CheckpointStatus.FAILED,
                    restored_at=timestamp,
                )
                raise CheckpointRestorationValidationError(
                    f"Post-restoration validation failed: {val_res.findings}"
                )

            # 12. Final Status Decision
            if partial or failed_resources:
                final_st = RestorationStatus.PARTIALLY_RESTORED
                cp_st = CheckpointStatus.FAILED
            else:
                final_st = RestorationStatus.RESTORED
                cp_st = CheckpointStatus.RESTORED

            self._repository.update_status(
                cp.checkpoint_id, new_status=cp_st, restored_at=timestamp
            )

            diffs = CheckpointDifference(
                checkpoint_id=cp.checkpoint_id,
                changed_resources=tuple(version_diffs.keys()),
                version_diffs=version_diffs,
            )

            return CheckpointRestorationResult(
                checkpoint_id=cp.checkpoint_id,
                status=final_st,
                success=final_st == RestorationStatus.RESTORED,
                restored_at=timestamp,
                restored_resources=tuple(restored_resources),
                failed_resources=tuple(failed_resources),
                original_error=original_error,
                restoration_error=None,
                differences=diffs,
                validation_result=val_res,
            )

        except Exception as exc:  # noqa: BLE001
            restoration_err = str(exc)
            self._repository.update_status(
                cp.checkpoint_id, CheckpointStatus.FAILED, restored_at=timestamp
            )

            diffs = CheckpointDifference(
                checkpoint_id=cp.checkpoint_id,
                changed_resources=tuple(version_diffs.keys()),
                version_diffs=version_diffs,
            )

            status_val = (
                RestorationStatus.PARTIALLY_RESTORED
                if restored_resources
                else RestorationStatus.FAILED
            )

            return CheckpointRestorationResult(
                checkpoint_id=cp.checkpoint_id,
                status=status_val,
                success=False,
                restored_at=timestamp,
                restored_resources=tuple(restored_resources),
                failed_resources=tuple(failed_resources),
                original_error=original_error,
                restoration_error=restoration_err,
                differences=diffs,
            )

        finally:
            # 13. Release exclusive locks
            if self._lock_manager:
                for lk_id in acquired_locks:
                    try:
                        self._lock_manager.release(lk_id, request.agent_run_id)
                    except Exception:  # noqa: BLE001, S110
                        pass
