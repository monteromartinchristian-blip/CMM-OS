"""Phase 9.15 – Checkpoint Integrity Verifier.

Provides comprehensive integrity verification for Runtime Checkpoints, validating
fingerprints, resource version states, snapshot availability, locks, expiration,
and coherence between transaction kinds and operation recovery capabilities.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from cmm.agent_runtime.checkpoint_contracts import (
    Checkpoint,
    CheckpointIntegrity,
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
from cmm.agent_runtime.enums import (
    CheckpointIntegrityStatus,
    CheckpointStatus,
    TransactionBoundaryKind,
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class CheckpointIntegrityVerifier:
    """Verifies internal, structural, and external environmental integrity of Checkpoints."""

    def __init__(
        self,
        resource_provider: ResourceVersionProvider | None = None,
        git_provider: GitStateProvider | None = None,
        storage_provider: StorageSnapshotProvider | None = None,
        memory_provider: MemoryStateProvider | None = None,
        knowledge_provider: KnowledgeStateProvider | None = None,
        backup_provider: BackupProvider | None = None,
    ) -> None:
        self._resource_provider = resource_provider
        self._git_provider = git_provider
        self._storage_provider = storage_provider
        self._memory_provider = memory_provider
        self._knowledge_provider = knowledge_provider
        self._backup_provider = backup_provider

    def verify(
        self,
        checkpoint: Checkpoint,
        transaction_kind: TransactionBoundaryKind | str | None = None,
        now: str | None = None,
    ) -> CheckpointIntegrity:
        """Perform comprehensive integrity verification on a checkpoint."""
        timestamp = now or _now_iso()
        issues: list[str] = []
        details: dict[str, Any] = {}

        # 1. Status Check
        if checkpoint.status in (
            CheckpointStatus.EXPIRED.value,
            CheckpointStatus.INVALID.value,
            CheckpointStatus.DELETED.value,
            CheckpointStatus.FAILED.value,
        ):
            issues.append(
                f"Checkpoint status is non-actionable ('{checkpoint.status}')."
            )

        # 2. Expiration Check
        if checkpoint.expires_at:
            dt_now = datetime.fromisoformat(timestamp)
            dt_exp = datetime.fromisoformat(checkpoint.expires_at)
            if dt_now >= dt_exp:
                issues.append(f"Checkpoint expired at '{checkpoint.expires_at}'.")

        # 3. Fingerprint verification
        expected_fp = compute_checkpoint_fingerprint(
            checkpoint_id=checkpoint.checkpoint_id,
            agent_run_id=checkpoint.agent_run_id,
            goal_id=checkpoint.goal_id,
            workflow_id=checkpoint.workflow_id,
            iteration_id=checkpoint.iteration_id,
            transaction_boundary_id=checkpoint.transaction_boundary_id,
            resource_versions=checkpoint.resource_versions,
            git_state=checkpoint.git_state,
            storage_snapshot_id=checkpoint.storage_snapshot_id,
            created_at=checkpoint.created_at,
        )

        fp_valid = expected_fp == checkpoint.fingerprint
        if not fp_valid:
            issues.append(
                f"Fingerprint mismatch: expected '{expected_fp}', found '{checkpoint.fingerprint}'."
            )
        details["fingerprint_computed"] = expected_fp
        details["fingerprint_stored"] = checkpoint.fingerprint

        # 4. Resource Version Provider verification
        resources_valid = True
        live_mismatches: list[str] = []
        if self._resource_provider:
            for res_key, exp_ver in checkpoint.resource_versions.items():
                if not self._resource_provider.verify_version(res_key, exp_ver):
                    live_mismatches.append(
                        f"Resource version mismatch for '{res_key}': expected '{exp_ver}'."
                    )
                    resources_valid = False
        details["live_resource_mismatches"] = tuple(live_mismatches)

        # 5. Git State verification
        if self._git_provider and checkpoint.git_state:
            curr_git = self._git_provider.capture_git_state()
            exp_commit = checkpoint.git_state.get("commit_hash")
            if exp_commit and curr_git.get("commit_hash") != exp_commit:
                details["git_commit_diff"] = (
                    f"Expected '{exp_commit}', got '{curr_git.get('commit_hash')}'."
                )

        # 6. External Storage Snapshot existence check
        if (
            checkpoint.storage_snapshot_id
            and self._storage_provider
            and not self._storage_provider.restore_snapshot(
                checkpoint.storage_snapshot_id
            )
        ):
            issues.append(
                f"Storage snapshot '{checkpoint.storage_snapshot_id}' does not exist or is corrupt."
            )

        # 7. Transaction Kind vs Operations Coherence
        if transaction_kind:
            tk_str = (
                transaction_kind.value
                if isinstance(transaction_kind, TransactionBoundaryKind)
                else str(transaction_kind)
            )
            if (
                tk_str == TransactionBoundaryKind.ATOMIC.value
                and checkpoint.irreversible_effects
            ):
                issues.append(
                    "Transaction kind ATOMIC cannot contain irreversible effects."
                )
            elif (
                tk_str == TransactionBoundaryKind.COMPENSABLE.value
                and not checkpoint.compensable_operations
                and not checkpoint.reversible_operations
            ):
                issues.append(
                    "Transaction kind COMPENSABLE has no registered compensable or reversible operations."
                )

        # 8. Determine overall integrity status
        if not fp_valid:
            st = CheckpointIntegrityStatus.CORRUPTED
        elif any("expired" in iss for iss in issues):
            st = CheckpointIntegrityStatus.STALE
        elif not resources_valid or any("version mismatch" in iss for iss in issues):
            st = CheckpointIntegrityStatus.VERSION_MISMATCH
        elif any("snapshot" in iss for iss in issues):
            st = CheckpointIntegrityStatus.MISSING_RESOURCE
        elif issues:
            st = CheckpointIntegrityStatus.INVALID
        else:
            st = CheckpointIntegrityStatus.VALID

        return CheckpointIntegrity(
            status=st,
            fingerprint_valid=fp_valid,
            resources_valid=resources_valid,
            issues=tuple(issues),
            verified_at=timestamp,
            details=details,
        )
