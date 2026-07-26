"""Phase 9.15 – Checkpoint Resource Integration Providers.

Defines protocols and default in-memory adapters for resource snapshot capture,
state restoration, backup verification, and post-restoration validation.
Does NOT execute shell commands or unverified external calls.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol, runtime_checkable

from cmm.agent_runtime.checkpoint_contracts import RestorationValidationResult


@runtime_checkable
class ResourceVersionProvider(Protocol):
    """Provider protocol for querying, verifying, and restoring resource versions."""

    def capture_version(self, resource_key: str) -> str:
        """Capture and return current version for a resource key."""

    def verify_version(self, resource_key: str, expected_version: str) -> bool:
        """Verify if current version matches expected_version."""

    def restore_version(self, resource_key: str, target_version: str) -> bool:
        """Restore resource to target_version."""


@runtime_checkable
class GitStateProvider(Protocol):
    """Provider protocol for capturing and restoring Git repository state without shell execution."""

    def capture_git_state(self) -> Mapping[str, Any]:
        """Capture commit, branch, dirty status, and file state."""

    def restore_git_state(self, target_git_state: Mapping[str, Any]) -> bool:
        """Restore workspace to target Git state."""


@runtime_checkable
class StorageSnapshotProvider(Protocol):
    """Provider protocol for creating and restoring storage snapshots."""

    def create_snapshot(self, storage_key: str) -> str:
        """Create a snapshot for storage_key and return snapshot_id."""

    def restore_snapshot(self, snapshot_id: str) -> bool:
        """Restore storage to state represented by snapshot_id."""


@runtime_checkable
class MemoryStateProvider(Protocol):
    """Provider protocol for capturing and restoring cognitive/agent memory state."""

    def capture_memory_version(self, agent_run_id: str) -> str:
        """Capture current memory version for run_id."""

    def restore_memory_version(self, agent_run_id: str, target_version: str) -> bool:
        """Restore agent run memory to target_version."""


@runtime_checkable
class KnowledgeStateProvider(Protocol):
    """Provider protocol for capturing and restoring knowledge base state."""

    def capture_knowledge_version(self, domain_id: str) -> str:
        """Capture knowledge base version."""

    def restore_knowledge_version(self, domain_id: str, target_version: str) -> bool:
        """Restore knowledge base state."""


@runtime_checkable
class BackupProvider(Protocol):
    """Provider protocol for creating and verifying required system backups."""

    def create_backup(self, scope: str) -> str:
        """Create backup for scope and return backup_id."""

    def verify_backup(self, backup_id: str) -> bool:
        """Verify backup integrity."""


@runtime_checkable
class RestorationValidator(Protocol):
    """Provider protocol for validating restored system state."""

    def validate_restored_state(
        self,
        checkpoint_id: str,
        expected_resource_versions: Mapping[str, str],
        expected_git_state: Mapping[str, Any],
    ) -> RestorationValidationResult:
        """Validate state post-restoration."""


# ── Default In-Memory Integration Implementations ────────────────────────────


class InMemoryResourceVersionProvider:
    """In-memory default implementation of ResourceVersionProvider."""

    def __init__(self, initial_versions: dict[str, str] | None = None) -> None:
        self._versions: dict[str, str] = initial_versions or {}

    def set_version(self, resource_key: str, version: str) -> None:
        self._versions[resource_key] = version

    def get_version(self, resource_uri: str) -> str:
        return self._versions.get(resource_uri, "v1.0.0")

    def capture_version(self, resource_key: str) -> str:
        return self.get_version(resource_key)

    def verify_version(self, resource_key: str, expected_version: str) -> bool:
        return self.get_version(resource_key) == expected_version

    def restore_version(self, resource_key: str, target_version: str) -> bool:
        self._versions[resource_key] = target_version
        return True


class InMemoryGitStateProvider:
    """In-memory default implementation of GitStateProvider."""

    def __init__(self, commit_hash: str = "abc1234", branch: str = "main") -> None:
        self._commit = commit_hash
        self._branch = branch
        self._is_clean = True

    def capture_git_state(self) -> dict[str, Any]:
        return {
            "commit_hash": self._commit,
            "branch": self._branch,
            "is_clean": self._is_clean,
        }

    def restore_git_state(self, target_git_state: Mapping[str, Any]) -> bool:
        self._commit = str(target_git_state.get("commit_hash", self._commit))
        self._branch = str(target_git_state.get("branch", self._branch))
        self._is_clean = bool(target_git_state.get("is_clean", True))
        return True


class InMemoryStorageSnapshotProvider:
    """In-memory default implementation of StorageSnapshotProvider."""

    def __init__(self) -> None:
        self._snapshots: dict[str, dict[str, Any]] = {}
        self._counter = 0

    def create_snapshot(self, storage_key: str) -> str:
        self._counter += 1
        snap_id = f"snap-{storage_key}-{self._counter}"
        self._snapshots[snap_id] = {"key": storage_key, "valid": True}
        return snap_id

    def restore_snapshot(self, snapshot_id: str) -> bool:
        return snapshot_id in self._snapshots and self._snapshots[snapshot_id]["valid"]


class InMemoryMemoryStateProvider:
    """In-memory default implementation of MemoryStateProvider."""

    def __init__(self) -> None:
        self._memory_versions: dict[str, str] = {}

    def capture_memory_version(self, agent_run_id: str) -> str:
        return self._memory_versions.get(agent_run_id, "mem-v1")

    def restore_memory_version(self, agent_run_id: str, target_version: str) -> bool:
        self._memory_versions[agent_run_id] = target_version
        return True


class InMemoryKnowledgeStateProvider:
    """In-memory default implementation of KnowledgeStateProvider."""

    def __init__(self) -> None:
        self._knowledge_versions: dict[str, str] = {}

    def capture_knowledge_version(self, domain_id: str) -> str:
        return self._knowledge_versions.get(domain_id, "know-v1")

    def restore_knowledge_version(self, domain_id: str, target_version: str) -> bool:
        self._knowledge_versions[domain_id] = target_version
        return True


class InMemoryBackupProvider:
    """In-memory default implementation of BackupProvider."""

    def __init__(self) -> None:
        self._backups: set[str] = set()
        self._counter = 0

    def create_backup(self, scope: str) -> str:
        self._counter += 1
        backup_id = f"backup-{scope}-{self._counter}"
        self._backups.add(backup_id)
        return backup_id

    def verify_backup(self, backup_id: str) -> bool:
        return backup_id in self._backups


class DefaultRestorationValidator:
    """Default implementation of RestorationValidator."""

    def __init__(
        self,
        resource_provider: ResourceVersionProvider | None = None,
        git_provider: GitStateProvider | None = None,
    ) -> None:
        self._resource_provider = resource_provider
        self._git_provider = git_provider

    def validate_restored_state(
        self,
        checkpoint_id: str,
        expected_resource_versions: Mapping[str, str],
        expected_git_state: Mapping[str, Any],
    ) -> RestorationValidationResult:
        findings = []
        checked = []

        if self._resource_provider:
            for k, expected_v in expected_resource_versions.items():
                checked.append(f"resource:{k}")
                if not self._resource_provider.verify_version(k, expected_v):
                    findings.append(
                        f"Resource version mismatch for '{k}': expected '{expected_v}'."
                    )

        if self._git_provider and expected_git_state:
            checked.append("git_state")
            current_git = self._git_provider.capture_git_state()
            if current_git.get("commit_hash") != expected_git_state.get("commit_hash"):
                findings.append("Git commit hash mismatch.")

        valid = len(findings) == 0
        return RestorationValidationResult(
            valid=valid,
            status="passed" if valid else "failed",
            checked_items=tuple(checked),
            findings=tuple(findings),
        )
