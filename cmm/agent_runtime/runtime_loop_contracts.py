"""Phase 9.12 – Agent Runtime Loop Contracts.

Defines the typed, immutable contracts for iterations, checkpoints, transitions,
step results, heartbeats, locks, resume requests, and step contexts.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from types import MappingProxyType
from typing import Any

from cmm.agent_runtime.contracts import AgentRun
from cmm.agent_runtime.enums import (
    AgentIterationStatus,
    AgentRuntimeStatus,
    RuntimeHealthStatus,
    RuntimeLockStatus,
    RuntimeLockType,
    RuntimeStep,
    RuntimeStepStatus,
)
from cmm.agent_runtime.errors import InvalidRuntimeContractError


def _ensure_aware_iso(dt_str: str, field_name: str) -> str:
    """Validate that dt_str is a non-empty string representing a timezone-aware ISO 8601 timestamp."""
    if not isinstance(dt_str, str) or not dt_str.strip():
        raise InvalidRuntimeContractError(
            f"Field '{field_name}' must be a non-empty ISO 8601 timestamp string."
        )
    try:
        dt = datetime.fromisoformat(dt_str)
    except Exception as exc:
        raise InvalidRuntimeContractError(
            f"Field '{field_name}' contains invalid ISO 8601 timestamp: {dt_str!r}"
        ) from exc

    if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
        raise InvalidRuntimeContractError(
            f"Field '{field_name}' must be timezone-aware (UTC required): {dt_str!r}"
        )
    return dt_str


def current_aware_iso() -> str:
    """Return the current system time in ISO 8601 format with UTC timezone offset."""
    return datetime.now(timezone.utc).isoformat()


def _freeze_dict(d: Mapping[str, Any] | None) -> Mapping[str, Any]:
    if d is None:
        return MappingProxyType({})
    if isinstance(d, MappingProxyType):
        return d
    return MappingProxyType(dict(d))


@dataclass(frozen=True)
class AgentIteration:
    """Represents a single full or partial iteration within an AgentRun lifecycle."""

    id: str
    agent_run_id: str
    number: int
    status: AgentIterationStatus | str
    started_at: str
    observation_snapshot_id: str | None = None
    reasoning_result_id: str | None = None
    runtime_decision_id: str | None = None
    workflow_plan_id: str | None = None
    workflow_execution_id: str | None = None
    validation_result_ids: tuple[str, ...] = ()
    outcome_evaluation_id: str | None = None
    completed_at: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or not self.id.strip():
            raise InvalidRuntimeContractError(
                "AgentIteration 'id' must be a non-empty string."
            )
        if not isinstance(self.agent_run_id, str) or not self.agent_run_id.strip():
            raise InvalidRuntimeContractError(
                "AgentIteration 'agent_run_id' must be a non-empty string."
            )
        if not isinstance(self.number, int) or self.number < 1:
            raise InvalidRuntimeContractError(
                "AgentIteration 'number' must be a positive integer >= 1."
            )

        # Validate status enum
        status_val = (
            self.status.value
            if isinstance(self.status, AgentIterationStatus)
            else self.status
        )
        if not isinstance(status_val, str) or not status_val.strip():
            raise InvalidRuntimeContractError(
                "AgentIteration 'status' cannot be empty."
            )
        object.__setattr__(self, "status", status_val)

        _ensure_aware_iso(self.started_at, "started_at")
        if self.completed_at is not None:
            _ensure_aware_iso(self.completed_at, "completed_at")

        # Ensure tuple containers
        if not isinstance(self.validation_result_ids, tuple):
            object.__setattr__(
                self, "validation_result_ids", tuple(self.validation_result_ids)
            )

        # Freeze metadata
        object.__setattr__(self, "metadata", _freeze_dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        """Return canonical dictionary representation."""
        return {
            "id": self.id,
            "agent_run_id": self.agent_run_id,
            "number": self.number,
            "status": str(self.status),
            "started_at": self.started_at,
            "observation_snapshot_id": self.observation_snapshot_id,
            "reasoning_result_id": self.reasoning_result_id,
            "runtime_decision_id": self.runtime_decision_id,
            "workflow_plan_id": self.workflow_plan_id,
            "workflow_execution_id": self.workflow_execution_id,
            "validation_result_ids": list(self.validation_result_ids),
            "outcome_evaluation_id": self.outcome_evaluation_id,
            "completed_at": self.completed_at,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentIteration:
        """Construct AgentIteration from dictionary."""
        if not isinstance(data, dict):
            raise InvalidRuntimeContractError("Data for AgentIteration must be a dict.")
        data_copy = dict(data)
        if "validation_result_ids" in data_copy and isinstance(
            data_copy["validation_result_ids"], list
        ):
            data_copy["validation_result_ids"] = tuple(
                data_copy["validation_result_ids"]
            )
        return cls(**data_copy)


@dataclass(frozen=True)
class RuntimeCheckpoint:
    """Represents a persistent, resumable checkpoint of an AgentRun state."""

    id: str
    agent_run_id: str
    iteration_id: str
    runtime_status: AgentRuntimeStatus | str
    step: RuntimeStep | str
    last_activity_at: str
    created_at: str
    state_version: int = 1
    goal_version: int = 1
    workflow_plan_id: str | None = None
    approval_request_ids: tuple[str, ...] = ()
    budget_reservation_ids: tuple[str, ...] = ()
    completed_operation_ids: tuple[str, ...] = ()
    completed_validation_ids: tuple[str, ...] = ()
    emitted_event_ids: tuple[str, ...] = ()
    memory_update_ids: tuple[str, ...] = ()
    question_ids: tuple[str, ...] = ()
    lock_ids: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or not self.id.strip():
            raise InvalidRuntimeContractError(
                "RuntimeCheckpoint 'id' must be a non-empty string."
            )
        if not isinstance(self.agent_run_id, str) or not self.agent_run_id.strip():
            raise InvalidRuntimeContractError(
                "RuntimeCheckpoint 'agent_run_id' must be a non-empty string."
            )
        if not isinstance(self.iteration_id, str) or not self.iteration_id.strip():
            raise InvalidRuntimeContractError(
                "RuntimeCheckpoint 'iteration_id' must be a non-empty string."
            )
        if not isinstance(self.state_version, int) or self.state_version < 1:
            raise InvalidRuntimeContractError(
                "RuntimeCheckpoint 'state_version' must be a positive int >= 1."
            )

        rs_val = (
            self.runtime_status.value
            if isinstance(self.runtime_status, AgentRuntimeStatus)
            else self.runtime_status
        )
        if not isinstance(rs_val, str) or not rs_val.strip():
            raise InvalidRuntimeContractError(
                "RuntimeCheckpoint 'runtime_status' cannot be empty."
            )
        object.__setattr__(self, "runtime_status", rs_val)

        step_val = self.step.value if isinstance(self.step, RuntimeStep) else self.step
        if not isinstance(step_val, str):
            raise InvalidRuntimeContractError(
                "RuntimeCheckpoint 'step' must be a string."
            )
        object.__setattr__(self, "step", step_val)

        _ensure_aware_iso(self.last_activity_at, "last_activity_at")
        _ensure_aware_iso(self.created_at, "created_at")

        # Convert lists/iterables to tuples
        for field_name in (
            "approval_request_ids",
            "budget_reservation_ids",
            "completed_operation_ids",
            "completed_validation_ids",
            "emitted_event_ids",
            "memory_update_ids",
            "question_ids",
            "lock_ids",
        ):
            val = getattr(self, field_name)
            if not isinstance(val, tuple):
                object.__setattr__(self, field_name, tuple(val))

        object.__setattr__(self, "metadata", _freeze_dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        """Return canonical dictionary representation."""
        return {
            "id": self.id,
            "agent_run_id": self.agent_run_id,
            "iteration_id": self.iteration_id,
            "runtime_status": str(self.runtime_status),
            "step": str(self.step),
            "state_version": self.state_version,
            "goal_version": self.goal_version,
            "workflow_plan_id": self.workflow_plan_id,
            "approval_request_ids": list(self.approval_request_ids),
            "budget_reservation_ids": list(self.budget_reservation_ids),
            "completed_operation_ids": list(self.completed_operation_ids),
            "completed_validation_ids": list(self.completed_validation_ids),
            "emitted_event_ids": list(self.emitted_event_ids),
            "memory_update_ids": list(self.memory_update_ids),
            "question_ids": list(self.question_ids),
            "lock_ids": list(self.lock_ids),
            "last_activity_at": self.last_activity_at,
            "created_at": self.created_at,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RuntimeCheckpoint:
        """Construct RuntimeCheckpoint from dictionary."""
        if not isinstance(data, dict):
            raise InvalidRuntimeContractError(
                "Data for RuntimeCheckpoint must be a dict."
            )
        data_copy = dict(data)
        for key in (
            "approval_request_ids",
            "budget_reservation_ids",
            "completed_operation_ids",
            "completed_validation_ids",
            "emitted_event_ids",
            "memory_update_ids",
            "question_ids",
            "lock_ids",
        ):
            if key in data_copy and isinstance(data_copy[key], list):
                data_copy[key] = tuple(data_copy[key])
        return cls(**data_copy)


@dataclass(frozen=True)
class RuntimeTransition:
    """Records a single state transition of an AgentRun."""

    id: str
    agent_run_id: str
    from_status: AgentRuntimeStatus | str
    to_status: AgentRuntimeStatus | str
    created_at: str
    iteration_id: str | None = None
    reason_codes: tuple[str, ...] = ()
    triggered_by: str = "runtime"
    idempotency_key: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or not self.id.strip():
            raise InvalidRuntimeContractError(
                "RuntimeTransition 'id' must be a non-empty string."
            )
        if not isinstance(self.agent_run_id, str) or not self.agent_run_id.strip():
            raise InvalidRuntimeContractError(
                "RuntimeTransition 'agent_run_id' must be a non-empty string."
            )

        from_val = (
            self.from_status.value
            if isinstance(self.from_status, AgentRuntimeStatus)
            else self.from_status
        )
        to_val = (
            self.to_status.value
            if isinstance(self.to_status, AgentRuntimeStatus)
            else self.to_status
        )
        if not isinstance(from_val, str) or not from_val.strip():
            raise InvalidRuntimeContractError(
                "RuntimeTransition 'from_status' cannot be empty."
            )
        if not isinstance(to_val, str) or not to_val.strip():
            raise InvalidRuntimeContractError(
                "RuntimeTransition 'to_status' cannot be empty."
            )
        object.__setattr__(self, "from_status", from_val)
        object.__setattr__(self, "to_status", to_val)

        _ensure_aware_iso(self.created_at, "created_at")

        if not isinstance(self.reason_codes, tuple):
            object.__setattr__(self, "reason_codes", tuple(self.reason_codes))

        object.__setattr__(self, "metadata", _freeze_dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        """Return canonical dictionary representation."""
        return {
            "id": self.id,
            "agent_run_id": self.agent_run_id,
            "iteration_id": self.iteration_id,
            "from_status": str(self.from_status),
            "to_status": str(self.to_status),
            "reason_codes": list(self.reason_codes),
            "triggered_by": self.triggered_by,
            "idempotency_key": self.idempotency_key,
            "created_at": self.created_at,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RuntimeTransition:
        """Construct RuntimeTransition from dictionary."""
        if not isinstance(data, dict):
            raise InvalidRuntimeContractError(
                "Data for RuntimeTransition must be a dict."
            )
        data_copy = dict(data)
        if "reason_codes" in data_copy and isinstance(data_copy["reason_codes"], list):
            data_copy["reason_codes"] = tuple(data_copy["reason_codes"])
        return cls(**data_copy)


@dataclass(frozen=True)
class RuntimeStepResult:
    """Represents the structured outcome of executing a single RuntimeStep."""

    agent_run_id: str
    iteration_id: str
    step: RuntimeStep | str
    created_at: str
    status: RuntimeStepStatus | str = RuntimeStepStatus.COMPLETED
    next_status: AgentRuntimeStatus | str = AgentRuntimeStatus.REASONING
    success: bool = True
    retryable: bool = False
    requires_user: bool = False
    requires_resource: bool = False
    requires_approval: bool = False
    checkpoint_required: bool = True
    reason_codes: tuple[str, ...] = ()
    produced_ids: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        if not isinstance(self.agent_run_id, str) or not self.agent_run_id.strip():
            raise InvalidRuntimeContractError(
                "RuntimeStepResult 'agent_run_id' must be a non-empty string."
            )
        if not isinstance(self.iteration_id, str) or not self.iteration_id.strip():
            raise InvalidRuntimeContractError(
                "RuntimeStepResult 'iteration_id' must be a non-empty string."
            )

        step_val = self.step.value if isinstance(self.step, RuntimeStep) else self.step
        status_val = (
            self.status.value
            if isinstance(self.status, RuntimeStepStatus)
            else self.status
        )
        next_val = (
            self.next_status.value
            if isinstance(self.next_status, AgentRuntimeStatus)
            else self.next_status
        )

        object.__setattr__(self, "step", step_val)
        object.__setattr__(self, "status", status_val)
        object.__setattr__(self, "next_status", next_val)

        _ensure_aware_iso(self.created_at, "created_at")

        if not isinstance(self.reason_codes, tuple):
            object.__setattr__(self, "reason_codes", tuple(self.reason_codes))
        if not isinstance(self.produced_ids, tuple):
            object.__setattr__(self, "produced_ids", tuple(self.produced_ids))

        object.__setattr__(self, "metadata", _freeze_dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        """Return canonical dictionary representation."""
        return {
            "agent_run_id": self.agent_run_id,
            "iteration_id": self.iteration_id,
            "step": str(self.step),
            "status": str(self.status),
            "next_status": str(self.next_status),
            "success": self.success,
            "retryable": self.retryable,
            "requires_user": self.requires_user,
            "requires_resource": self.requires_resource,
            "requires_approval": self.requires_approval,
            "checkpoint_required": self.checkpoint_required,
            "reason_codes": list(self.reason_codes),
            "produced_ids": list(self.produced_ids),
            "created_at": self.created_at,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RuntimeStepResult:
        """Construct RuntimeStepResult from dictionary."""
        if not isinstance(data, dict):
            raise InvalidRuntimeContractError(
                "Data for RuntimeStepResult must be a dict."
            )
        data_copy = dict(data)
        for k in ("reason_codes", "produced_ids"):
            if k in data_copy and isinstance(data_copy[k], list):
                data_copy[k] = tuple(data_copy[k])
        return cls(**data_copy)


@dataclass(frozen=True)
class RuntimeHeartbeat:
    """Records operational health and current activity state of an active AgentRun."""

    agent_run_id: str
    status: AgentRuntimeStatus | str
    last_activity_at: str
    expires_at: str
    current_iteration: int = 0
    current_task_id: str | None = None
    current_lock_ids: tuple[str, ...] = ()
    budget_id: str | None = None
    next_action: str | None = None
    health: RuntimeHealthStatus | str = RuntimeHealthStatus.HEALTHY
    metadata: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        if not isinstance(self.agent_run_id, str) or not self.agent_run_id.strip():
            raise InvalidRuntimeContractError(
                "RuntimeHeartbeat 'agent_run_id' must be a non-empty string."
            )
        status_val = (
            self.status.value
            if isinstance(self.status, AgentRuntimeStatus)
            else self.status
        )
        health_val = (
            self.health.value
            if isinstance(self.health, RuntimeHealthStatus)
            else self.health
        )
        object.__setattr__(self, "status", status_val)
        object.__setattr__(self, "health", health_val)

        _ensure_aware_iso(self.last_activity_at, "last_activity_at")
        _ensure_aware_iso(self.expires_at, "expires_at")

        if not isinstance(self.current_lock_ids, tuple):
            object.__setattr__(self, "current_lock_ids", tuple(self.current_lock_ids))

        object.__setattr__(self, "metadata", _freeze_dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        """Return canonical dictionary representation."""
        return {
            "agent_run_id": self.agent_run_id,
            "status": str(self.status),
            "current_iteration": self.current_iteration,
            "current_task_id": self.current_task_id,
            "current_lock_ids": list(self.current_lock_ids),
            "budget_id": self.budget_id,
            "next_action": self.next_action,
            "health": str(self.health),
            "last_activity_at": self.last_activity_at,
            "expires_at": self.expires_at,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RuntimeHeartbeat:
        """Construct RuntimeHeartbeat from dictionary."""
        if not isinstance(data, dict):
            raise InvalidRuntimeContractError(
                "Data for RuntimeHeartbeat must be a dict."
            )
        data_copy = dict(data)
        if "current_lock_ids" in data_copy and isinstance(
            data_copy["current_lock_ids"], list
        ):
            data_copy["current_lock_ids"] = tuple(data_copy["current_lock_ids"])
        return cls(**data_copy)


@dataclass(frozen=True)
class RuntimeLock:
    """Represents an active or released lock on a resource or goal."""

    id: str
    resource_key: str
    owner_agent_run_id: str
    acquired_at: str
    expires_at: str
    lock_type: RuntimeLockType | str = RuntimeLockType.EXCLUSIVE
    status: RuntimeLockStatus | str = RuntimeLockStatus.ACTIVE
    released_at: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or not self.id.strip():
            raise InvalidRuntimeContractError(
                "RuntimeLock 'id' must be a non-empty string."
            )
        if not isinstance(self.resource_key, str) or not self.resource_key.strip():
            raise InvalidRuntimeContractError(
                "RuntimeLock 'resource_key' must be a non-empty string."
            )
        if (
            not isinstance(self.owner_agent_run_id, str)
            or not self.owner_agent_run_id.strip()
        ):
            raise InvalidRuntimeContractError(
                "RuntimeLock 'owner_agent_run_id' must be a non-empty string."
            )

        lock_type_val = (
            self.lock_type.value
            if isinstance(self.lock_type, RuntimeLockType)
            else self.lock_type
        )
        status_val = (
            self.status.value
            if isinstance(self.status, RuntimeLockStatus)
            else self.status
        )
        object.__setattr__(self, "lock_type", lock_type_val)
        object.__setattr__(self, "status", status_val)

        _ensure_aware_iso(self.acquired_at, "acquired_at")
        _ensure_aware_iso(self.expires_at, "expires_at")
        if self.released_at is not None:
            _ensure_aware_iso(self.released_at, "released_at")

        object.__setattr__(self, "metadata", _freeze_dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        """Return canonical dictionary representation."""
        return {
            "id": self.id,
            "resource_key": self.resource_key,
            "owner_agent_run_id": self.owner_agent_run_id,
            "lock_type": str(self.lock_type),
            "status": str(self.status),
            "acquired_at": self.acquired_at,
            "expires_at": self.expires_at,
            "released_at": self.released_at,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RuntimeLock:
        """Construct RuntimeLock from dictionary."""
        if not isinstance(data, dict):
            raise InvalidRuntimeContractError("Data for RuntimeLock must be a dict.")
        return cls(**dict(data))


@dataclass(frozen=True)
class RuntimeResumeRequest:
    """Request payload to resume a paused or resumable AgentRun."""

    agent_run_id: str
    checkpoint_id: str
    created_at: str
    requested_by: str = "actor-user"
    expected_state_version: int | None = None
    idempotency_key: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        if not isinstance(self.agent_run_id, str) or not self.agent_run_id.strip():
            raise InvalidRuntimeContractError(
                "RuntimeResumeRequest 'agent_run_id' must be a non-empty string."
            )
        if not isinstance(self.checkpoint_id, str) or not self.checkpoint_id.strip():
            raise InvalidRuntimeContractError(
                "RuntimeResumeRequest 'checkpoint_id' must be a non-empty string."
            )
        _ensure_aware_iso(self.created_at, "created_at")
        object.__setattr__(self, "metadata", _freeze_dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        """Return canonical dictionary representation."""
        return {
            "agent_run_id": self.agent_run_id,
            "checkpoint_id": self.checkpoint_id,
            "requested_by": self.requested_by,
            "expected_state_version": self.expected_state_version,
            "idempotency_key": self.idempotency_key,
            "created_at": self.created_at,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RuntimeResumeRequest:
        """Construct RuntimeResumeRequest from dictionary."""
        if not isinstance(data, dict):
            raise InvalidRuntimeContractError(
                "Data for RuntimeResumeRequest must be a dict."
            )
        return cls(**dict(data))


@dataclass(frozen=True)
class RuntimeStepContext:
    """Immutable execution context provided to step handlers during step execution."""

    agent_run: AgentRun
    now: str
    goal: Any | None = None
    iteration: AgentIteration | None = None
    checkpoint: RuntimeCheckpoint | None = None
    current_step: RuntimeStep | str = RuntimeStep.OBSERVE
    workflow_plan: Any | None = None
    policy_results: tuple[Any, ...] = ()
    approval_resolutions: tuple[Any, ...] = ()
    budget: Any | None = None
    locks: tuple[RuntimeLock, ...] = ()
    idempotency_key: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        if not isinstance(self.agent_run, AgentRun):
            raise InvalidRuntimeContractError(
                "RuntimeStepContext 'agent_run' must be an AgentRun instance."
            )
        _ensure_aware_iso(self.now, "now")

        step_val = (
            self.current_step.value
            if isinstance(self.current_step, RuntimeStep)
            else self.current_step
        )
        object.__setattr__(self, "current_step", step_val)

        for k in ("policy_results", "approval_resolutions", "locks"):
            val = getattr(self, k)
            if not isinstance(val, tuple):
                object.__setattr__(self, k, tuple(val))

        object.__setattr__(self, "metadata", _freeze_dict(self.metadata))
