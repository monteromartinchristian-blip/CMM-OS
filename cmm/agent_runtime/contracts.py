"""Phase 9.1 – Foundational Agent Runtime Contracts.

Defines immutable, typed, serializable, and provider-independent contracts
for AgentDefinition, AgentRun, RuntimeDecision, and AgentResult.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from types import MappingProxyType
from typing import Any

# Re-exported for convenience; this module re-uses the shared coercion
# helper from the autonomy contracts so the integer 0..4 construction
# pattern (e.g. ``AgentDefinition(..., autonomy_level=2)``) keeps working.
from cmm.agent_runtime.autonomy_contracts import (  # noqa: F401
    coerce_autonomy_level as _coerce_autonomy_level,
)
from cmm.agent_runtime.enums import (
    AgentResultOutcome,
    AgentRuntimeStatus,
    RuntimeDecisionType,
)
from cmm.agent_runtime.errors import (
    InvalidAgentContractError,
)


def _ensure_tz_aware(dt: datetime, field_name: str) -> datetime:
    """Ensure a datetime object is timezone-aware."""
    if not isinstance(dt, datetime):
        raise InvalidAgentContractError(f"{field_name} must be a datetime instance")
    if dt.tzinfo is None:
        raise InvalidAgentContractError(f"{field_name} must be timezone-aware")
    return dt


def _parse_datetime(val: Any, field_name: str) -> datetime:
    """Parse string or datetime to timezone-aware datetime."""
    if isinstance(val, datetime):
        return _ensure_tz_aware(val, field_name)
    if isinstance(val, str):
        try:
            parsed = datetime.fromisoformat(val)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed
        except ValueError as exc:
            raise InvalidAgentContractError(
                f"Invalid isoformat datetime string for {field_name}: {val!r}"
            ) from exc
    raise InvalidAgentContractError(
        f"{field_name} must be an ISO string or datetime instance"
    )


def _validate_non_empty_str(val: Any, field_name: str) -> str:
    """Validate that value is a non-empty string."""
    if not isinstance(val, str) or not val.strip():
        raise InvalidAgentContractError(f"{field_name} must be a non-empty string")
    return val.strip()


def _freeze_metadata(meta: Any) -> MappingProxyType[str, Any]:
    """Validate and freeze metadata dictionary into MappingProxyType."""
    if meta is None:
        return MappingProxyType({})
    if isinstance(meta, Mapping):
        meta_dict = dict(meta)
        for k in meta_dict:
            if not isinstance(k, str):
                raise InvalidAgentContractError("Metadata keys must be strings")
        return MappingProxyType(meta_dict)
    raise InvalidAgentContractError("metadata must be a Mapping instance")


def _freeze_str_tuple(
    seq: Any, field_name: str, allow_empty: bool = True
) -> tuple[str, ...]:
    """Validate and convert sequence to tuple of clean non-empty strings."""
    if seq is None:
        if allow_empty:
            return ()
        raise InvalidAgentContractError(f"{field_name} cannot be None")
    if not isinstance(seq, (tuple, list, set, Sequence)) or isinstance(
        seq, (str, bytes)
    ):
        raise InvalidAgentContractError(
            f"{field_name} must be a tuple, list, or sequence of strings"
        )
    result = []
    for item in seq:
        if not isinstance(item, str) or not item.strip():
            raise InvalidAgentContractError(
                f"All items in {field_name} must be non-empty strings"
            )
        result.append(item.strip())
    return tuple(result)


def _freeze_tuple(seq: Any, field_name: str) -> tuple[Any, ...]:
    """Validate and convert sequence to an immutable tuple."""
    if seq is None:
        return ()
    if not isinstance(seq, (tuple, list, set, Sequence)) or isinstance(
        seq, (str, bytes)
    ):
        raise InvalidAgentContractError(f"{field_name} must be a tuple or sequence")
    return tuple(seq)


@dataclass(frozen=True, slots=True)
class AgentDefinition:
    """Declarative configuration contract for an Agent Runtime profile."""

    id: str
    name: str
    version: str
    description: str
    reasoning_profile: str
    runtime_policy: str
    observation_profile: str
    autonomy_level: int
    allowed_goal_types: tuple[str, ...] = ()
    allowed_operations: tuple[str, ...] = ()
    prohibited_operations: tuple[str, ...] = ()
    budget_policy: str = ""
    approval_policy: str = ""
    recovery_policy: str = ""
    enabled: bool = True
    metadata: MappingProxyType[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )

    def __post_init__(self) -> None:
        _validate_non_empty_str(self.id, "id")
        _validate_non_empty_str(self.name, "name")
        _validate_non_empty_str(self.version, "version")

        if not isinstance(self.autonomy_level, int) or isinstance(
            self.autonomy_level, bool
        ):
            raise InvalidAgentContractError("autonomy_level must be an integer (>= 0)")
        if self.autonomy_level < 0:
            raise InvalidAgentContractError(
                f"autonomy_level cannot be negative, got {self.autonomy_level}"
            )

        if not isinstance(self.enabled, bool):
            raise InvalidAgentContractError("enabled must be a boolean")

        object.__setattr__(
            self,
            "allowed_goal_types",
            _freeze_str_tuple(self.allowed_goal_types, "allowed_goal_types"),
        )
        object.__setattr__(
            self,
            "allowed_operations",
            _freeze_str_tuple(self.allowed_operations, "allowed_operations"),
        )
        object.__setattr__(
            self,
            "prohibited_operations",
            _freeze_str_tuple(self.prohibited_operations, "prohibited_operations"),
        )
        object.__setattr__(self, "metadata", _freeze_metadata(self.metadata))

    def serialize(self) -> dict[str, Any]:
        """Serialize contract to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "reasoning_profile": self.reasoning_profile,
            "runtime_policy": self.runtime_policy,
            "observation_profile": self.observation_profile,
            "autonomy_level": self.autonomy_level,
            "allowed_goal_types": list(self.allowed_goal_types),
            "allowed_operations": list(self.allowed_operations),
            "prohibited_operations": list(self.prohibited_operations),
            "budget_policy": self.budget_policy,
            "approval_policy": self.approval_policy,
            "recovery_policy": self.recovery_policy,
            "enabled": self.enabled,
            "metadata": dict(self.metadata),
        }

    def to_dict(self) -> dict[str, Any]:
        """Alias for serialize()."""
        return self.serialize()

    @classmethod
    def from_mapping(cls, mapping: Mapping[str, Any]) -> AgentDefinition:
        """Construct AgentDefinition from a mapping."""
        if not isinstance(mapping, Mapping):
            raise InvalidAgentContractError("mapping must be a Mapping instance")

        required_keys = {
            "id",
            "name",
            "version",
            "description",
            "reasoning_profile",
            "runtime_policy",
            "observation_profile",
            "autonomy_level",
        }
        missing = required_keys - set(mapping.keys())
        if missing:
            raise InvalidAgentContractError(
                f"Missing required fields in mapping: {sorted(missing)}"
            )

        return cls(
            id=str(mapping["id"]),
            name=str(mapping["name"]),
            version=str(mapping["version"]),
            description=str(mapping["description"]),
            reasoning_profile=str(mapping["reasoning_profile"]),
            runtime_policy=str(mapping["runtime_policy"]),
            observation_profile=str(mapping["observation_profile"]),
            autonomy_level=mapping["autonomy_level"],
            allowed_goal_types=tuple(mapping.get("allowed_goal_types", ())),
            allowed_operations=tuple(mapping.get("allowed_operations", ())),
            prohibited_operations=tuple(mapping.get("prohibited_operations", ())),
            budget_policy=str(mapping.get("budget_policy", "")),
            approval_policy=str(mapping.get("approval_policy", "")),
            recovery_policy=str(mapping.get("recovery_policy", "")),
            enabled=bool(mapping.get("enabled", True)),
            metadata=mapping.get("metadata") or {},
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentDefinition:
        """Alias for from_mapping()."""
        return cls.from_mapping(data)


@dataclass(frozen=True, slots=True)
class AgentRun:
    """Active execution state contract for a single agent run pursuing a goal."""

    id: str
    agent_id: str
    goal_id: str
    status: AgentRuntimeStatus
    autonomy_level: int
    current_iteration: int
    started_at: datetime
    updated_at: datetime
    current_workflow_id: str | None = None
    current_task_id: str | None = None
    reasoning_session_id: str | None = None
    observation_snapshot_id: str | None = None
    budget_id: str | None = None
    policy_context_id: str | None = None
    paused_at: datetime | None = None
    completed_at: datetime | None = None
    metadata: MappingProxyType[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )

    def __post_init__(self) -> None:
        _validate_non_empty_str(self.id, "id")
        _validate_non_empty_str(self.agent_id, "agent_id")
        _validate_non_empty_str(self.goal_id, "goal_id")

        if isinstance(self.status, str):
            try:
                object.__setattr__(self, "status", AgentRuntimeStatus(self.status))
            except ValueError as exc:
                raise InvalidAgentContractError(
                    f"Invalid AgentRuntimeStatus string: {self.status!r}"
                ) from exc
        elif not isinstance(self.status, AgentRuntimeStatus):
            raise InvalidAgentContractError(
                f"status must be an AgentRuntimeStatus enum, got {type(self.status).__name__}"
            )

        if not isinstance(self.autonomy_level, int) or isinstance(
            self.autonomy_level, bool
        ):
            raise InvalidAgentContractError("autonomy_level must be an integer (>= 0)")
        if self.autonomy_level < 0:
            raise InvalidAgentContractError(
                f"autonomy_level cannot be negative, got {self.autonomy_level}"
            )

        if not isinstance(self.current_iteration, int) or isinstance(
            self.current_iteration, bool
        ):
            raise InvalidAgentContractError(
                "current_iteration must be an integer (>= 0)"
            )
        if self.current_iteration < 0:
            raise InvalidAgentContractError(
                f"current_iteration cannot be negative, got {self.current_iteration}"
            )

        object.__setattr__(
            self, "started_at", _ensure_tz_aware(self.started_at, "started_at")
        )
        object.__setattr__(
            self, "updated_at", _ensure_tz_aware(self.updated_at, "updated_at")
        )

        if self.paused_at is not None:
            object.__setattr__(
                self, "paused_at", _ensure_tz_aware(self.paused_at, "paused_at")
            )
        if self.completed_at is not None:
            object.__setattr__(
                self,
                "completed_at",
                _ensure_tz_aware(self.completed_at, "completed_at"),
            )
            if self.completed_at < self.started_at:
                raise InvalidAgentContractError(
                    "completed_at cannot be prior to started_at"
                )

        object.__setattr__(self, "metadata", _freeze_metadata(self.metadata))

    def serialize(self) -> dict[str, Any]:
        """Serialize contract to dictionary."""
        return {
            "id": self.id,
            "agent_id": self.agent_id,
            "goal_id": self.goal_id,
            "status": self.status.value,
            "autonomy_level": self.autonomy_level,
            "current_iteration": self.current_iteration,
            "current_workflow_id": self.current_workflow_id,
            "current_task_id": self.current_task_id,
            "reasoning_session_id": self.reasoning_session_id,
            "observation_snapshot_id": self.observation_snapshot_id,
            "budget_id": self.budget_id,
            "policy_context_id": self.policy_context_id,
            "started_at": self.started_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "paused_at": self.paused_at.isoformat() if self.paused_at else None,
            "completed_at": self.completed_at.isoformat()
            if self.completed_at
            else None,
            "metadata": dict(self.metadata),
        }

    def to_dict(self) -> dict[str, Any]:
        """Alias for serialize()."""
        return self.serialize()

    @classmethod
    def from_mapping(cls, mapping: Mapping[str, Any]) -> AgentRun:
        """Construct AgentRun from a mapping."""
        if not isinstance(mapping, Mapping):
            raise InvalidAgentContractError("mapping must be a Mapping instance")

        required_keys = {
            "id",
            "agent_id",
            "goal_id",
            "status",
            "autonomy_level",
            "current_iteration",
            "started_at",
            "updated_at",
        }
        missing = required_keys - set(mapping.keys())
        if missing:
            raise InvalidAgentContractError(
                f"Missing required fields in mapping: {sorted(missing)}"
            )

        paused_raw = mapping.get("paused_at")
        completed_raw = mapping.get("completed_at")

        return cls(
            id=str(mapping["id"]),
            agent_id=str(mapping["agent_id"]),
            goal_id=str(mapping["goal_id"]),
            status=mapping["status"],
            autonomy_level=mapping["autonomy_level"],
            current_iteration=mapping["current_iteration"],
            started_at=_parse_datetime(mapping["started_at"], "started_at"),
            updated_at=_parse_datetime(mapping["updated_at"], "updated_at"),
            current_workflow_id=mapping.get("current_workflow_id"),
            current_task_id=mapping.get("current_task_id"),
            reasoning_session_id=mapping.get("reasoning_session_id"),
            observation_snapshot_id=mapping.get("observation_snapshot_id"),
            budget_id=mapping.get("budget_id"),
            policy_context_id=mapping.get("policy_context_id"),
            paused_at=_parse_datetime(paused_raw, "paused_at") if paused_raw else None,
            completed_at=_parse_datetime(completed_raw, "completed_at")
            if completed_raw
            else None,
            metadata=mapping.get("metadata") or {},
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentRun:
        """Alias for from_mapping()."""
        return cls.from_mapping(data)


@dataclass(frozen=True, slots=True)
class RuntimeDecision:
    """Structured decision contract emitted by the runtime state machine."""

    id: str
    run_id: str
    decision: RuntimeDecisionType
    confidence: float
    created_at: datetime
    reason_codes: tuple[str, ...] = ()
    inputs: tuple[Any, ...] = ()
    policy_results: tuple[Any, ...] = ()
    requires_approval: bool = False
    metadata: MappingProxyType[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )

    def __post_init__(self) -> None:
        _validate_non_empty_str(self.id, "id")
        _validate_non_empty_str(self.run_id, "run_id")

        if isinstance(self.decision, str):
            try:
                object.__setattr__(self, "decision", RuntimeDecisionType(self.decision))
            except ValueError as exc:
                raise InvalidAgentContractError(
                    f"Invalid RuntimeDecisionType string: {self.decision!r}"
                ) from exc
        elif not isinstance(self.decision, RuntimeDecisionType):
            raise InvalidAgentContractError(
                f"decision must be a RuntimeDecisionType enum, got {type(self.decision).__name__}"
            )

        if not isinstance(self.confidence, (int, float)) or isinstance(
            self.confidence, bool
        ):
            raise InvalidAgentContractError(
                "confidence must be a float between 0.0 and 1.0"
            )
        if not (0.0 <= float(self.confidence) <= 1.0):
            raise InvalidAgentContractError(
                f"confidence must be between 0.0 and 1.0, got {self.confidence}"
            )
        object.__setattr__(self, "confidence", float(self.confidence))

        if not isinstance(self.requires_approval, bool):
            raise InvalidAgentContractError("requires_approval must be a boolean")

        object.__setattr__(
            self, "created_at", _ensure_tz_aware(self.created_at, "created_at")
        )
        object.__setattr__(
            self, "reason_codes", _freeze_str_tuple(self.reason_codes, "reason_codes")
        )
        object.__setattr__(self, "inputs", _freeze_tuple(self.inputs, "inputs"))
        object.__setattr__(
            self, "policy_results", _freeze_tuple(self.policy_results, "policy_results")
        )
        object.__setattr__(self, "metadata", _freeze_metadata(self.metadata))

    def serialize(self) -> dict[str, Any]:
        """Serialize contract to dictionary."""
        return {
            "id": self.id,
            "run_id": self.run_id,
            "decision": self.decision.value,
            "reason_codes": list(self.reason_codes),
            "inputs": list(self.inputs),
            "policy_results": list(self.policy_results),
            "confidence": self.confidence,
            "requires_approval": self.requires_approval,
            "created_at": self.created_at.isoformat(),
            "metadata": dict(self.metadata),
        }

    def to_dict(self) -> dict[str, Any]:
        """Alias for serialize()."""
        return self.serialize()

    @classmethod
    def from_mapping(cls, mapping: Mapping[str, Any]) -> RuntimeDecision:
        """Construct RuntimeDecision from a mapping."""
        if not isinstance(mapping, Mapping):
            raise InvalidAgentContractError("mapping must be a Mapping instance")

        required_keys = {
            "id",
            "run_id",
            "decision",
            "confidence",
            "created_at",
        }
        missing = required_keys - set(mapping.keys())
        if missing:
            raise InvalidAgentContractError(
                f"Missing required fields in mapping: {sorted(missing)}"
            )

        return cls(
            id=str(mapping["id"]),
            run_id=str(mapping["run_id"]),
            decision=mapping["decision"],
            confidence=mapping["confidence"],
            created_at=_parse_datetime(mapping["created_at"], "created_at"),
            reason_codes=tuple(mapping.get("reason_codes", ())),
            inputs=tuple(mapping.get("inputs", ())),
            policy_results=tuple(mapping.get("policy_results", ())),
            requires_approval=bool(mapping.get("requires_approval", False)),
            metadata=mapping.get("metadata") or {},
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RuntimeDecision:
        """Alias for from_mapping()."""
        return cls.from_mapping(data)


@dataclass(frozen=True, slots=True)
class AgentResult:
    """Final outcome and audit evidence contract for a completed or terminated agent run."""

    id: str
    agent_run_id: str
    goal_id: str
    status: AgentRuntimeStatus
    outcome: AgentResultOutcome | str
    confidence: float
    trace_id: str
    started_at: datetime
    completed_at: datetime
    duration_ms: float
    success_criteria: tuple[Any, ...] = ()
    completed_workflows: tuple[str, ...] = ()
    completed_operations: tuple[str, ...] = ()
    failed_operations: tuple[str, ...] = ()
    validations: tuple[Any, ...] = ()
    knowledge_updates: tuple[Any, ...] = ()
    memory_updates: tuple[Any, ...] = ()
    side_effects: tuple[Any, ...] = ()
    remaining_work: tuple[Any, ...] = ()
    metadata: MappingProxyType[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )

    def __post_init__(self) -> None:
        _validate_non_empty_str(self.id, "id")
        _validate_non_empty_str(self.agent_run_id, "agent_run_id")
        _validate_non_empty_str(self.goal_id, "goal_id")
        _validate_non_empty_str(self.trace_id, "trace_id")

        if isinstance(self.status, str):
            try:
                object.__setattr__(self, "status", AgentRuntimeStatus(self.status))
            except ValueError as exc:
                raise InvalidAgentContractError(
                    f"Invalid AgentRuntimeStatus string: {self.status!r}"
                ) from exc
        elif not isinstance(self.status, AgentRuntimeStatus):
            raise InvalidAgentContractError(
                f"status must be an AgentRuntimeStatus enum, got {type(self.status).__name__}"
            )

        if isinstance(self.outcome, str):
            try:
                object.__setattr__(self, "outcome", AgentResultOutcome(self.outcome))
            except ValueError:
                # Keep custom outcome string if non-empty
                _validate_non_empty_str(self.outcome, "outcome")
        elif not isinstance(self.outcome, AgentResultOutcome):
            raise InvalidAgentContractError(
                f"outcome must be an AgentResultOutcome or string, got {type(self.outcome).__name__}"
            )

        if not isinstance(self.confidence, (int, float)) or isinstance(
            self.confidence, bool
        ):
            raise InvalidAgentContractError(
                "confidence must be a float between 0.0 and 1.0"
            )
        if not (0.0 <= float(self.confidence) <= 1.0):
            raise InvalidAgentContractError(
                f"confidence must be between 0.0 and 1.0, got {self.confidence}"
            )
        object.__setattr__(self, "confidence", float(self.confidence))

        if not isinstance(self.duration_ms, (int, float)) or isinstance(
            self.duration_ms, bool
        ):
            raise InvalidAgentContractError("duration_ms must be a non-negative number")
        if float(self.duration_ms) < 0:
            raise InvalidAgentContractError("duration_ms cannot be negative")
        object.__setattr__(self, "duration_ms", float(self.duration_ms))

        object.__setattr__(
            self, "started_at", _ensure_tz_aware(self.started_at, "started_at")
        )
        object.__setattr__(
            self, "completed_at", _ensure_tz_aware(self.completed_at, "completed_at")
        )
        if self.completed_at < self.started_at:
            raise InvalidAgentContractError(
                "completed_at cannot be prior to started_at"
            )

        object.__setattr__(
            self,
            "success_criteria",
            _freeze_tuple(self.success_criteria, "success_criteria"),
        )
        object.__setattr__(
            self,
            "completed_workflows",
            _freeze_str_tuple(self.completed_workflows, "completed_workflows"),
        )
        object.__setattr__(
            self,
            "completed_operations",
            _freeze_str_tuple(self.completed_operations, "completed_operations"),
        )
        object.__setattr__(
            self,
            "failed_operations",
            _freeze_str_tuple(self.failed_operations, "failed_operations"),
        )
        object.__setattr__(
            self, "validations", _freeze_tuple(self.validations, "validations")
        )
        object.__setattr__(
            self,
            "knowledge_updates",
            _freeze_tuple(self.knowledge_updates, "knowledge_updates"),
        )
        object.__setattr__(
            self, "memory_updates", _freeze_tuple(self.memory_updates, "memory_updates")
        )
        object.__setattr__(
            self, "side_effects", _freeze_tuple(self.side_effects, "side_effects")
        )
        object.__setattr__(
            self, "remaining_work", _freeze_tuple(self.remaining_work, "remaining_work")
        )
        object.__setattr__(self, "metadata", _freeze_metadata(self.metadata))

    def serialize(self) -> dict[str, Any]:
        """Serialize contract to dictionary."""
        outcome_val = (
            self.outcome.value
            if isinstance(self.outcome, AgentResultOutcome)
            else self.outcome
        )
        return {
            "id": self.id,
            "agent_run_id": self.agent_run_id,
            "goal_id": self.goal_id,
            "status": self.status.value,
            "outcome": outcome_val,
            "success_criteria": list(self.success_criteria),
            "completed_workflows": list(self.completed_workflows),
            "completed_operations": list(self.completed_operations),
            "failed_operations": list(self.failed_operations),
            "validations": list(self.validations),
            "knowledge_updates": list(self.knowledge_updates),
            "memory_updates": list(self.memory_updates),
            "side_effects": list(self.side_effects),
            "remaining_work": list(self.remaining_work),
            "confidence": self.confidence,
            "trace_id": self.trace_id,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat(),
            "duration_ms": self.duration_ms,
            "metadata": dict(self.metadata),
        }

    def to_dict(self) -> dict[str, Any]:
        """Alias for serialize()."""
        return self.serialize()

    @classmethod
    def from_mapping(cls, mapping: Mapping[str, Any]) -> AgentResult:
        """Construct AgentResult from a mapping."""
        if not isinstance(mapping, Mapping):
            raise InvalidAgentContractError("mapping must be a Mapping instance")

        required_keys = {
            "id",
            "agent_run_id",
            "goal_id",
            "status",
            "outcome",
            "confidence",
            "trace_id",
            "started_at",
            "completed_at",
            "duration_ms",
        }
        missing = required_keys - set(mapping.keys())
        if missing:
            raise InvalidAgentContractError(
                f"Missing required fields in mapping: {sorted(missing)}"
            )

        return cls(
            id=str(mapping["id"]),
            agent_run_id=str(mapping["agent_run_id"]),
            goal_id=str(mapping["goal_id"]),
            status=mapping["status"],
            outcome=mapping["outcome"],
            confidence=mapping["confidence"],
            trace_id=str(mapping["trace_id"]),
            started_at=_parse_datetime(mapping["started_at"], "started_at"),
            completed_at=_parse_datetime(mapping["completed_at"], "completed_at"),
            duration_ms=mapping["duration_ms"],
            success_criteria=tuple(mapping.get("success_criteria", ())),
            completed_workflows=tuple(mapping.get("completed_workflows", ())),
            completed_operations=tuple(mapping.get("completed_operations", ())),
            failed_operations=tuple(mapping.get("failed_operations", ())),
            validations=tuple(mapping.get("validations", ())),
            knowledge_updates=tuple(mapping.get("knowledge_updates", ())),
            memory_updates=tuple(mapping.get("memory_updates", ())),
            side_effects=tuple(mapping.get("side_effects", ())),
            remaining_work=tuple(mapping.get("remaining_work", ())),
            metadata=mapping.get("metadata") or {},
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentResult:
        """Alias for from_mapping()."""
        return cls.from_mapping(data)
