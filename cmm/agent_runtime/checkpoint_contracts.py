"""Phase 9.15 – Checkpoints and Transaction Boundaries Contracts.

Defines immutable, serializable, and timezone-aware contracts for checkpoints,
transaction boundaries, operation recovery classifications, and restoration results.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any

from cmm.agent_runtime.enums import (
    CheckpointIntegrityStatus,
    CheckpointStatus,
    OperationRecoveryKind,
    RestorationStatus,
    TransactionBoundaryKind,
    TransactionStatus,
)
from cmm.agent_runtime.errors import CheckpointInvalidError


def _freeze_dict(d: Mapping[str, Any] | None) -> Mapping[str, Any]:
    if d is None:
        return MappingProxyType({})
    if isinstance(d, MappingProxyType):
        return d
    # Recursively freeze nested dicts if needed
    cleaned = {}
    for k, v in d.items():
        if isinstance(v, dict):
            cleaned[k] = _freeze_dict(v)
        else:
            cleaned[k] = v
    return MappingProxyType(cleaned)


def _to_json_serializable(obj: Any) -> Any:
    if isinstance(obj, MappingProxyType):
        return {k: _to_json_serializable(v) for k, v in obj.items()}
    if isinstance(obj, (tuple, list)):
        return [_to_json_serializable(i) for i in obj]
    if isinstance(obj, dict):
        return {k: _to_json_serializable(v) for k, v in obj.items()}
    if hasattr(obj, "value"):
        return obj.value
    return obj


def compute_checkpoint_fingerprint(
    checkpoint_id: str,
    agent_run_id: str,
    goal_id: str,
    workflow_id: str,
    iteration_id: str,
    transaction_boundary_id: str,
    resource_versions: Mapping[str, str],
    git_state: Mapping[str, Any],
    storage_snapshot_id: str | None,
    created_at: str,
) -> str:
    """Compute deterministic SHA-256 fingerprint for a checkpoint."""
    payload = {
        "checkpoint_id": checkpoint_id,
        "agent_run_id": agent_run_id,
        "goal_id": goal_id,
        "workflow_id": workflow_id,
        "iteration_id": iteration_id,
        "transaction_boundary_id": transaction_boundary_id,
        "resource_versions": sorted(_to_json_serializable(resource_versions).items()),
        "git_state": sorted(_to_json_serializable(git_state).items())
        if isinstance(git_state, (dict, MappingProxyType))
        else str(git_state),
        "storage_snapshot_id": storage_snapshot_id or "",
        "created_at": created_at,
    }
    raw = json.dumps(payload, sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class CheckpointResource:
    """Represents a specific resource protected by a checkpoint."""

    resource_key: str
    resource_type: str
    version: str
    is_mandatory: bool = True
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.resource_key:
            raise CheckpointInvalidError(
                "CheckpointResource must have non-empty resource_key."
            )
        object.__setattr__(self, "metadata", _freeze_dict(self.metadata))


@dataclass(frozen=True)
class Checkpoint:
    """Immutable state snapshot preserving system state before transaction execution."""

    checkpoint_id: str
    agent_run_id: str
    goal_id: str
    workflow_id: str
    iteration_id: str
    name: str
    status: CheckpointStatus | str
    transaction_boundary_id: str
    resource_versions: Mapping[str, str]
    git_state: Mapping[str, Any]
    storage_snapshot_id: str | None
    memory_state_version: str | None
    knowledge_state_version: str | None
    reversible_operations: tuple[str, ...]
    compensable_operations: tuple[str, ...]
    irreversible_effects: tuple[str, ...]
    locks: tuple[str, ...]
    fingerprint: str
    created_at: str
    expires_at: str | None = None
    restored_at: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.checkpoint_id:
            raise CheckpointInvalidError(
                "Checkpoint must have a non-empty checkpoint_id."
            )
        if not self.agent_run_id:
            raise CheckpointInvalidError(
                "Checkpoint must have a non-empty agent_run_id."
            )
        if not self.created_at:
            raise CheckpointInvalidError("Checkpoint created_at must be specified.")

        st = (
            self.status.value
            if isinstance(self.status, CheckpointStatus)
            else str(self.status)
        )
        object.__setattr__(self, "status", st)
        object.__setattr__(
            self, "resource_versions", _freeze_dict(self.resource_versions)
        )
        object.__setattr__(self, "git_state", _freeze_dict(self.git_state))
        object.__setattr__(
            self, "reversible_operations", tuple(self.reversible_operations)
        )
        object.__setattr__(
            self, "compensable_operations", tuple(self.compensable_operations)
        )
        object.__setattr__(
            self, "irreversible_effects", tuple(self.irreversible_effects)
        )
        object.__setattr__(self, "locks", tuple(self.locks))
        object.__setattr__(self, "metadata", _freeze_dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "checkpoint_id": self.checkpoint_id,
            "agent_run_id": self.agent_run_id,
            "goal_id": self.goal_id,
            "workflow_id": self.workflow_id,
            "iteration_id": self.iteration_id,
            "name": self.name,
            "status": self.status,
            "transaction_boundary_id": self.transaction_boundary_id,
            "resource_versions": dict(self.resource_versions),
            "git_state": dict(self.git_state),
            "storage_snapshot_id": self.storage_snapshot_id,
            "memory_state_version": self.memory_state_version,
            "knowledge_state_version": self.knowledge_state_version,
            "reversible_operations": list(self.reversible_operations),
            "compensable_operations": list(self.compensable_operations),
            "irreversible_effects": list(self.irreversible_effects),
            "locks": list(self.locks),
            "fingerprint": self.fingerprint,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "restored_at": self.restored_at,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class CheckpointIntegrity:
    """Structured integrity verification result for a checkpoint."""

    status: CheckpointIntegrityStatus | str
    fingerprint_valid: bool
    resources_valid: bool
    issues: tuple[str, ...]
    verified_at: str
    details: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        st = (
            self.status.value
            if isinstance(self.status, CheckpointIntegrityStatus)
            else str(self.status)
        )
        object.__setattr__(self, "status", st)
        object.__setattr__(self, "issues", tuple(self.issues))
        object.__setattr__(self, "details", _freeze_dict(self.details))


@dataclass(frozen=True)
class CheckpointCreationRequest:
    """Request payload to create a checkpoint."""

    agent_run_id: str
    goal_id: str
    workflow_id: str
    iteration_id: str
    name: str
    transaction_boundary_id: str
    resource_keys: tuple[str, ...] = ()
    requires_backup: bool = False
    ttl_seconds: int | None = None
    idempotency_key: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.agent_run_id:
            raise CheckpointInvalidError(
                "CheckpointCreationRequest must include agent_run_id."
            )
        object.__setattr__(self, "resource_keys", tuple(self.resource_keys))
        object.__setattr__(self, "metadata", _freeze_dict(self.metadata))


@dataclass(frozen=True)
class CheckpointCreationResult:
    """Outcome result of checkpoint creation."""

    checkpoint_id: str
    status: CheckpointStatus | str
    success: bool
    fingerprint: str
    created_at: str
    error_message: str | None = None
    checkpoint: Checkpoint | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        st = (
            self.status.value
            if isinstance(self.status, CheckpointStatus)
            else str(self.status)
        )
        object.__setattr__(self, "status", st)
        object.__setattr__(self, "metadata", _freeze_dict(self.metadata))


@dataclass(frozen=True)
class CheckpointRestorationRequest:
    """Request payload to restore a checkpoint."""

    checkpoint_id: str
    agent_run_id: str
    requested_by: str = "runtime"
    force: bool = False
    reason: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.checkpoint_id:
            raise CheckpointInvalidError(
                "CheckpointRestorationRequest must include checkpoint_id."
            )
        object.__setattr__(self, "metadata", _freeze_dict(self.metadata))


@dataclass(frozen=True)
class CompensationAction:
    """Action definition to compensate a completed non-reversible operation."""

    action_id: str
    operation_name: str
    handler_name: str
    parameters: Mapping[str, Any] = field(default_factory=dict)
    is_exact_rollback: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "parameters", _freeze_dict(self.parameters))


@dataclass(frozen=True)
class RestorationValidationResult:
    """Post-restoration state validation result."""

    valid: bool
    status: str
    checked_items: tuple[str, ...] = ()
    findings: tuple[str, ...] = ()
    validated_at: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "checked_items", tuple(self.checked_items))
        object.__setattr__(self, "findings", tuple(self.findings))


@dataclass(frozen=True)
class CheckpointDifference:
    """Structural differences between a checkpoint state and current state."""

    checkpoint_id: str
    changed_resources: tuple[str, ...] = ()
    added_resources: tuple[str, ...] = ()
    removed_resources: tuple[str, ...] = ()
    version_diffs: Mapping[str, tuple[str, str]] = field(default_factory=dict)
    git_diff_summary: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "changed_resources", tuple(self.changed_resources))
        object.__setattr__(self, "added_resources", tuple(self.added_resources))
        object.__setattr__(self, "removed_resources", tuple(self.removed_resources))
        object.__setattr__(self, "version_diffs", _freeze_dict(self.version_diffs))


@dataclass(frozen=True)
class CheckpointRestorationResult:
    """Outcome result of checkpoint restoration."""

    checkpoint_id: str
    status: RestorationStatus | str
    success: bool
    restored_at: str
    restored_resources: tuple[str, ...] = ()
    failed_resources: tuple[str, ...] = ()
    original_error: str | None = None
    restoration_error: str | None = None
    differences: CheckpointDifference | None = None
    validation_result: RestorationValidationResult | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        st = (
            self.status.value
            if isinstance(self.status, RestorationStatus)
            else str(self.status)
        )
        object.__setattr__(self, "status", st)
        object.__setattr__(self, "restored_resources", tuple(self.restored_resources))
        object.__setattr__(self, "failed_resources", tuple(self.failed_resources))
        object.__setattr__(self, "metadata", _freeze_dict(self.metadata))


@dataclass(frozen=True)
class TransactionBoundary:
    """Defines transaction boundary properties and requirements for a set of operations."""

    id: str
    agent_run_id: str
    kind: TransactionBoundaryKind | str
    name: str
    checkpoint_id: str | None = None
    status: TransactionStatus | str = TransactionStatus.PENDING
    created_at: str = ""
    committed_at: str | None = None
    rolled_back_at: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.id:
            raise CheckpointInvalidError("TransactionBoundary must have non-empty id.")
        kd = (
            self.kind.value
            if isinstance(self.kind, TransactionBoundaryKind)
            else str(self.kind)
        )
        st = (
            self.status.value
            if isinstance(self.status, TransactionStatus)
            else str(self.status)
        )
        object.__setattr__(self, "kind", kd)
        object.__setattr__(self, "status", st)
        object.__setattr__(self, "metadata", _freeze_dict(self.metadata))


@dataclass(frozen=True)
class TransactionOperation:
    """Tracks an individual operation executed within a transaction boundary."""

    operation_id: str
    transaction_boundary_id: str
    operation_name: str
    recovery_kind: OperationRecoveryKind | str
    compensation_action: CompensationAction | None = None
    executed_at: str = ""
    is_executed: bool = False
    effects: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        rk = (
            self.recovery_kind.value
            if isinstance(self.recovery_kind, OperationRecoveryKind)
            else str(self.recovery_kind)
        )
        object.__setattr__(self, "recovery_kind", rk)
        object.__setattr__(self, "effects", tuple(self.effects))
        object.__setattr__(self, "metadata", _freeze_dict(self.metadata))


@dataclass(frozen=True)
class TransactionExecutionState:
    """Current state of a transaction execution."""

    transaction_boundary_id: str
    status: TransactionStatus | str
    executed_operations: tuple[TransactionOperation, ...] = ()
    active_checkpoint_id: str | None = None
    started_at: str = ""
    updated_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        st = (
            self.status.value
            if isinstance(self.status, TransactionStatus)
            else str(self.status)
        )
        object.__setattr__(self, "status", st)
        object.__setattr__(self, "executed_operations", tuple(self.executed_operations))
        object.__setattr__(self, "metadata", _freeze_dict(self.metadata))
