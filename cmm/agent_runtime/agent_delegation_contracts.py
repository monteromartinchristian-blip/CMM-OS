"""Phase 9.24 Agent Delegation Contracts.

Immutable, JSON-serializable, type-safe contracts for Agent Delegation subsystem.

All dataclasses are ``frozen=True`` and never expose mutable internal state.
"""

from __future__ import annotations

import re
import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from types import MappingProxyType
from typing import Any

from cmm.agent_runtime.agent_delegation_enums import (
    DelegationStatus,
)
from cmm.agent_runtime.agent_delegation_errors import (
    AgentDelegationValidationError,
)
from cmm.agent_runtime.contracts import (
    _freeze_metadata,
    _freeze_str_tuple,
    _freeze_tuple,
)
from cmm.agent_runtime.enums import (
    GoalKind,
)
from cmm.agent_runtime.goal_contracts import Goal, GoalConstraint

# ── Helpers ──────────────────────────────────────────────────────────────────


_DELEGATION_ID_PATTERN = re.compile(r"^[a-zA-Z][a-zA-Z0-9_.\-]{1,63}$")
_IDENTIFIER_PATTERN = re.compile(r"^[a-zA-Z][a-zA-Z0-9_.\-]{0,127}$")

_FORBIDDEN_METADATA_KEYS: frozenset[str] = frozenset(
    {
        "chain_of_thought",
        "private_prompt",
        "internal_reasoning",
        "api_key",
        "apikey",
        "password",
        "passwd",
        "private_key",
        "secret",
        "bearer",
        "token",
    }
)

_MAX_DELEGATION_DEPTH = 10


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _validate_non_empty_str(val: Any, field_name: str) -> str:
    if not isinstance(val, str):
        raise AgentDelegationValidationError(
            f"{field_name} must be a string", {"field": field_name}
        )
    if not val.strip():
        raise AgentDelegationValidationError(
            f"{field_name} must be a non-empty string", {"field": field_name}
        )
    return val.strip()


def _validate_identifier(val: Any, field_name: str) -> str:
    s = _validate_non_empty_str(val, field_name)
    if not _IDENTIFIER_PATTERN.match(s):
        raise AgentDelegationValidationError(
            f"{field_name} has invalid format",
            {"field": field_name, "value": s},
        )
    return s


def _validate_delegation_id(val: Any, field_name: str) -> str:
    s = _validate_non_empty_str(val, field_name)
    if not _DELEGATION_ID_PATTERN.match(s):
        raise AgentDelegationValidationError(
            f"{field_name} has invalid format",
            {"field": field_name, "value": s},
        )
    return s


def _ensure_tz_aware(dt: Any, field_name: str) -> datetime:
    if not isinstance(dt, datetime):
        raise AgentDelegationValidationError(
            f"{field_name} must be a datetime", {"field": field_name}
        )
    if dt.tzinfo is None:
        raise AgentDelegationValidationError(
            f"{field_name} must be timezone-aware", {"field": field_name}
        )
    return dt


def _generate_id(prefix: str = "del") -> str:
    """Generate a unique delegation ID."""
    return f"{prefix}-{uuid.uuid4().hex[:16]}"


# ── DelegatedGoal (Core Delegation Contract) ─────────────────────────────────


@dataclass(frozen=True, slots=True)
class DelegatedGoal:
    """
    Immutable contract representing a delegation between two agents.

    A delegation links a parent goal to a child goal, assigns the child goal
    to a target agent, and tracks the delegation lifecycle through status.
    """

    id: str
    parent_goal_id: str
    child_goal_id: str
    source_agent_id: str
    target_agent_id: str
    source_agent_run_id: str | None
    target_agent_run_id: str | None
    expected_result: MappingProxyType[str, Any]
    constraints: tuple[GoalConstraint, ...]
    status: DelegationStatus
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None
    metadata: MappingProxyType[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )
    depth: int = 0
    correlation_id: str | None = None

    def __post_init__(self) -> None:
        # Validate identifiers
        object.__setattr__(self, "id", _validate_delegation_id(self.id, "id"))
        object.__setattr__(
            self,
            "parent_goal_id",
            _validate_identifier(self.parent_goal_id, "parent_goal_id"),
        )
        object.__setattr__(
            self,
            "child_goal_id",
            _validate_identifier(self.child_goal_id, "child_goal_id"),
        )
        object.__setattr__(
            self,
            "source_agent_id",
            _validate_identifier(self.source_agent_id, "source_agent_id"),
        )
        object.__setattr__(
            self,
            "target_agent_id",
            _validate_identifier(self.target_agent_id, "target_agent_id"),
        )

        if self.source_agent_run_id is not None:
            object.__setattr__(
                self,
                "source_agent_run_id",
                _validate_identifier(self.source_agent_run_id, "source_agent_run_id"),
            )

        if self.target_agent_run_id is not None:
            object.__setattr__(
                self,
                "target_agent_run_id",
                _validate_identifier(self.target_agent_run_id, "target_agent_run_id"),
            )

        # Validate expected_result
        if not isinstance(self.expected_result, Mapping):
            raise AgentDelegationValidationError(
                "expected_result must be a mapping",
                {"field": "expected_result"},
            )
        object.__setattr__(
            self, "expected_result", _freeze_metadata(dict(self.expected_result))
        )

        # Validate constraints
        constraints_list = []
        for c in self.constraints:
            if isinstance(c, Mapping):
                c = GoalConstraint.from_mapping(c)
            elif not isinstance(c, GoalConstraint):
                raise AgentDelegationValidationError(
                    "constraints items must be GoalConstraint instances",
                    {"field": "constraints"},
                )
            constraints_list.append(c)
        object.__setattr__(self, "constraints", tuple(constraints_list))

        # Validate status
        if isinstance(self.status, str):
            try:
                object.__setattr__(self, "status", DelegationStatus(self.status))
            except ValueError as exc:
                raise AgentDelegationValidationError(
                    f"Invalid DelegationStatus string: {self.status!r}"
                ) from exc
        elif not isinstance(self.status, DelegationStatus):
            raise AgentDelegationValidationError(
                f"status must be a DelegationStatus enum, got {type(self.status).__name__}"
            )

        # Validate timestamps
        object.__setattr__(
            self, "created_at", _ensure_tz_aware(self.created_at, "created_at")
        )
        object.__setattr__(
            self, "updated_at", _ensure_tz_aware(self.updated_at, "updated_at")
        )

        if self.completed_at is not None:
            completed = _ensure_tz_aware(self.completed_at, "completed_at")
            if completed < self.created_at:
                raise AgentDelegationValidationError(
                    "completed_at cannot be prior to created_at",
                    {"field": "completed_at"},
                )
            object.__setattr__(self, "completed_at", completed)
            if self.status not in {
                DelegationStatus.COMPLETED,
                DelegationStatus.FAILED,
                DelegationStatus.CANCELLED,
                DelegationStatus.REJECTED,
                DelegationStatus.EXPIRED,
            }:
                raise AgentDelegationValidationError(
                    "Terminal delegation must have terminal status",
                    {"field": "status"},
                )

        # Validate depth
        if not isinstance(self.depth, int) or isinstance(self.depth, bool):
            raise AgentDelegationValidationError(
                "depth must be an integer >= 0", {"field": "depth"}
            )
        if self.depth < 0:
            raise AgentDelegationValidationError(
                "depth cannot be negative", {"field": "depth"}
            )
        if self.depth > _MAX_DELEGATION_DEPTH:
            raise AgentDelegationValidationError(
                f"depth cannot exceed {_MAX_DELEGATION_DEPTH}",
                {"field": "depth", "max_depth": _MAX_DELEGATION_DEPTH},
            )

        # Validate correlation_id
        if self.correlation_id is not None:
            object.__setattr__(
                self,
                "correlation_id",
                _validate_identifier(self.correlation_id, "correlation_id"),
            )

        # Freeze metadata
        object.__setattr__(self, "metadata", _freeze_metadata(dict(self.metadata)))

        # Self-reference checks
        if self.parent_goal_id == self.child_goal_id:
            raise AgentDelegationValidationError(
                "parent_goal_id and child_goal_id cannot be identical",
                {"field": "child_goal_id"},
            )

        if self.source_agent_id == self.target_agent_id:
            raise AgentDelegationValidationError(
                "source_agent_id and target_agent_id cannot be identical",
                {"field": "target_agent_id"},
            )

    @property
    def is_terminal(self) -> bool:
        return self.status.is_terminal

    @property
    def is_active(self) -> bool:
        return self.status.is_active

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "id": self.id,
            "parent_goal_id": self.parent_goal_id,
            "child_goal_id": self.child_goal_id,
            "source_agent_id": self.source_agent_id,
            "target_agent_id": self.target_agent_id,
            "source_agent_run_id": self.source_agent_run_id,
            "target_agent_run_id": self.target_agent_run_id,
            "expected_result": dict(self.expected_result),
            "constraints": [c.to_dict() for c in self.constraints],
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "completed_at": self.completed_at.isoformat()
            if self.completed_at
            else None,
            "metadata": dict(self.metadata),
            "depth": self.depth,
            "correlation_id": self.correlation_id,
        }

    @classmethod
    def from_mapping(cls, mapping: Mapping[str, Any]) -> DelegatedGoal:
        """Construct from a mapping."""
        if not isinstance(mapping, Mapping):
            raise AgentDelegationValidationError("mapping must be a Mapping instance")

        required_keys = {
            "id",
            "parent_goal_id",
            "child_goal_id",
            "source_agent_id",
            "target_agent_id",
            "expected_result",
            "constraints",
            "status",
            "created_at",
            "updated_at",
        }
        missing = required_keys - set(mapping.keys())
        if missing:
            raise AgentDelegationValidationError(
                f"Missing required fields: {sorted(missing)}"
            )

        def parse_dt(val: Any, name: str) -> datetime | None:
            if val is None:
                return None
            if isinstance(val, datetime):
                return _ensure_tz_aware(val, name)
            if isinstance(val, str):
                return _ensure_tz_aware(datetime.fromisoformat(val), name)
            raise AgentDelegationValidationError(
                f"{name} must be datetime or ISO string"
            )

        def parse_required_dt(val: Any, name: str) -> datetime:
            parsed = parse_dt(val, name)
            if parsed is None:
                raise AgentDelegationValidationError(f"{name} is required")
            return parsed

        c_raw = mapping.get("constraints", ())
        c_list = [
            GoalConstraint.from_mapping(item) if isinstance(item, Mapping) else item
            for item in c_raw
        ]

        return cls(
            id=str(mapping["id"]),
            parent_goal_id=str(mapping["parent_goal_id"]),
            child_goal_id=str(mapping["child_goal_id"]),
            source_agent_id=str(mapping["source_agent_id"]),
            target_agent_id=str(mapping["target_agent_id"]),
            source_agent_run_id=mapping.get("source_agent_run_id"),
            target_agent_run_id=mapping.get("target_agent_run_id"),
            expected_result=MappingProxyType(dict(mapping["expected_result"])),
            constraints=tuple(c_list),
            status=mapping["status"],
            created_at=parse_required_dt(mapping["created_at"], "created_at"),
            updated_at=parse_required_dt(mapping["updated_at"], "updated_at"),
            completed_at=parse_dt(mapping.get("completed_at"), "completed_at"),
            metadata=MappingProxyType(dict(mapping.get("metadata", {}))),
            depth=mapping.get("depth", 0),
            correlation_id=mapping.get("correlation_id"),
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DelegatedGoal:
        return cls.from_mapping(data)


# ── DelegationProposal (for proposing a delegation) ──────────────────────────


@dataclass(frozen=True, slots=True)
class DelegationProposal:
    """
    Proposal to create a delegation. Used as input to the delegation service.

    This is a lightweight contract for the proposal phase, before the child
    goal is created and the delegation is fully established.
    """

    parent_goal_id: str
    target_agent_id: str
    child_goal_kind: GoalKind
    child_goal_title: str
    child_goal_description: str
    expected_result: MappingProxyType[str, Any]
    constraints: tuple[GoalConstraint, ...] = ()
    source_agent_id: str | None = None
    source_agent_run_id: str | None = None
    depth: int = 0
    correlation_id: str | None = None
    metadata: MappingProxyType[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "parent_goal_id",
            _validate_identifier(self.parent_goal_id, "parent_goal_id"),
        )
        object.__setattr__(
            self,
            "target_agent_id",
            _validate_identifier(self.target_agent_id, "target_agent_id"),
        )

        if isinstance(self.child_goal_kind, str):
            try:
                object.__setattr__(
                    self, "child_goal_kind", GoalKind(self.child_goal_kind)
                )
            except ValueError as exc:
                raise AgentDelegationValidationError(
                    f"Invalid GoalKind string: {self.child_goal_kind!r}"
                ) from exc
        elif not isinstance(self.child_goal_kind, GoalKind):
            raise AgentDelegationValidationError(
                "child_goal_kind must be a GoalKind or valid string"
            )

        object.__setattr__(
            self,
            "child_goal_title",
            _validate_non_empty_str(self.child_goal_title, "child_goal_title"),
        )
        object.__setattr__(
            self,
            "child_goal_description",
            _validate_non_empty_str(
                self.child_goal_description, "child_goal_description"
            ),
        )

        if not isinstance(self.expected_result, Mapping):
            raise AgentDelegationValidationError(
                "expected_result must be a mapping", {"field": "expected_result"}
            )
        object.__setattr__(
            self, "expected_result", _freeze_metadata(dict(self.expected_result))
        )

        constraints_list = []
        for c in self.constraints:
            if isinstance(c, Mapping):
                c = GoalConstraint.from_mapping(c)
            elif not isinstance(c, GoalConstraint):
                raise AgentDelegationValidationError(
                    "constraints items must be GoalConstraint instances",
                    {"field": "constraints"},
                )
            constraints_list.append(c)
        object.__setattr__(self, "constraints", tuple(constraints_list))

        if self.source_agent_id is not None:
            object.__setattr__(
                self,
                "source_agent_id",
                _validate_identifier(self.source_agent_id, "source_agent_id"),
            )

        if self.source_agent_run_id is not None:
            object.__setattr__(
                self,
                "source_agent_run_id",
                _validate_identifier(self.source_agent_run_id, "source_agent_run_id"),
            )

        if not isinstance(self.depth, int) or isinstance(self.depth, bool):
            raise AgentDelegationValidationError(
                "depth must be an integer >= 0", {"field": "depth"}
            )
        if self.depth < 0:
            raise AgentDelegationValidationError(
                "depth cannot be negative", {"field": "depth"}
            )
        if self.depth > _MAX_DELEGATION_DEPTH:
            raise AgentDelegationValidationError(
                f"depth cannot exceed {_MAX_DELEGATION_DEPTH}",
                {"field": "depth", "max_depth": _MAX_DELEGATION_DEPTH},
            )

        if self.correlation_id is not None:
            object.__setattr__(
                self,
                "correlation_id",
                _validate_identifier(self.correlation_id, "correlation_id"),
            )

        object.__setattr__(self, "metadata", _freeze_metadata(dict(self.metadata)))

    def to_dict(self) -> dict[str, Any]:
        return {
            "parent_goal_id": self.parent_goal_id,
            "target_agent_id": self.target_agent_id,
            "child_goal_kind": self.child_goal_kind.value,
            "child_goal_title": self.child_goal_title,
            "child_goal_description": self.child_goal_description,
            "expected_result": dict(self.expected_result),
            "constraints": [c.to_dict() for c in self.constraints],
            "source_agent_id": self.source_agent_id,
            "source_agent_run_id": self.source_agent_run_id,
            "depth": self.depth,
            "correlation_id": self.correlation_id,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_mapping(cls, mapping: Mapping[str, Any]) -> DelegationProposal:
        if not isinstance(mapping, Mapping):
            raise AgentDelegationValidationError("mapping must be a Mapping instance")

        required_keys = {
            "parent_goal_id",
            "target_agent_id",
            "child_goal_kind",
            "child_goal_title",
            "child_goal_description",
            "expected_result",
        }
        missing = required_keys - set(mapping.keys())
        if missing:
            raise AgentDelegationValidationError(
                f"Missing required fields: {sorted(missing)}"
            )

        c_raw = mapping.get("constraints", ())
        c_list = [
            GoalConstraint.from_mapping(item) if isinstance(item, Mapping) else item
            for item in c_raw
        ]

        return cls(
            parent_goal_id=str(mapping["parent_goal_id"]),
            target_agent_id=str(mapping["target_agent_id"]),
            child_goal_kind=mapping["child_goal_kind"],
            child_goal_title=str(mapping["child_goal_title"]),
            child_goal_description=str(mapping["child_goal_description"]),
            expected_result=MappingProxyType(dict(mapping["expected_result"])),
            constraints=tuple(c_list),
            source_agent_id=mapping.get("source_agent_id"),
            source_agent_run_id=mapping.get("source_agent_run_id"),
            depth=mapping.get("depth", 0),
            correlation_id=mapping.get("correlation_id"),
            metadata=MappingProxyType(dict(mapping.get("metadata", {}))),
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DelegationProposal:
        return cls.from_mapping(data)


# ── DelegationResult (for incorporating delegated result into parent) ────────


@dataclass(frozen=True, slots=True)
class DelegationResult:
    """
    Structured result returned from a delegated agent run.

    The parent goal can distinguish between various result states and
    decides how to incorporate this result.
    """

    delegation_id: str
    parent_goal_id: str
    child_goal_id: str
    delegated_run_id: str | None
    status: DelegationStatus
    agent_result_id: str | None
    outputs: tuple[Any, ...]
    knowledge_ids: tuple[str, ...]
    artifacts: tuple[str, ...]
    warnings: tuple[str, ...]
    errors: tuple[str, ...]
    completed_at: datetime
    metadata: MappingProxyType[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "delegation_id",
            _validate_delegation_id(self.delegation_id, "delegation_id"),
        )
        object.__setattr__(
            self,
            "parent_goal_id",
            _validate_identifier(self.parent_goal_id, "parent_goal_id"),
        )
        object.__setattr__(
            self,
            "child_goal_id",
            _validate_identifier(self.child_goal_id, "child_goal_id"),
        )

        if self.delegated_run_id is not None:
            object.__setattr__(
                self,
                "delegated_run_id",
                _validate_identifier(self.delegated_run_id, "delegated_run_id"),
            )

        if isinstance(self.status, str):
            try:
                object.__setattr__(self, "status", DelegationStatus(self.status))
            except ValueError as exc:
                raise AgentDelegationValidationError(
                    f"Invalid DelegationStatus string: {self.status!r}"
                ) from exc
        elif not isinstance(self.status, DelegationStatus):
            raise AgentDelegationValidationError(
                f"status must be a DelegationStatus enum, got {type(self.status).__name__}"
            )

        if self.agent_result_id is not None:
            object.__setattr__(
                self,
                "agent_result_id",
                _validate_identifier(self.agent_result_id, "agent_result_id"),
            )

        object.__setattr__(self, "outputs", _freeze_tuple(self.outputs, "outputs"))
        object.__setattr__(
            self,
            "knowledge_ids",
            _freeze_str_tuple(self.knowledge_ids, "knowledge_ids"),
        )
        object.__setattr__(
            self, "artifacts", _freeze_str_tuple(self.artifacts, "artifacts")
        )
        object.__setattr__(
            self, "warnings", _freeze_str_tuple(self.warnings, "warnings")
        )
        object.__setattr__(self, "errors", _freeze_str_tuple(self.errors, "errors"))

        object.__setattr__(
            self, "completed_at", _ensure_tz_aware(self.completed_at, "completed_at")
        )

        object.__setattr__(self, "metadata", _freeze_metadata(dict(self.metadata)))

    @property
    def is_success(self) -> bool:
        return self.status == DelegationStatus.COMPLETED

    @property
    def is_partial(self) -> bool:
        return self.status == DelegationStatus.COMPLETED and bool(self.warnings)

    @property
    def is_failure(self) -> bool:
        return self.status == DelegationStatus.FAILED

    @property
    def is_cancelled(self) -> bool:
        return self.status == DelegationStatus.CANCELLED

    @property
    def is_invalid(self) -> bool:
        return bool(self.errors)

    @property
    def is_pending(self) -> bool:
        return self.status in {
            DelegationStatus.PROPOSED,
            DelegationStatus.ACCEPTED,
            DelegationStatus.ACTIVE,
            DelegationStatus.WAITING,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "delegation_id": self.delegation_id,
            "parent_goal_id": self.parent_goal_id,
            "child_goal_id": self.child_goal_id,
            "delegated_run_id": self.delegated_run_id,
            "status": self.status.value,
            "agent_result_id": self.agent_result_id,
            "outputs": list(self.outputs),
            "knowledge_ids": list(self.knowledge_ids),
            "artifacts": list(self.artifacts),
            "warnings": list(self.warnings),
            "errors": list(self.errors),
            "completed_at": self.completed_at.isoformat(),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_mapping(cls, mapping: Mapping[str, Any]) -> DelegationResult:
        if not isinstance(mapping, Mapping):
            raise AgentDelegationValidationError("mapping must be a Mapping instance")

        required_keys = {
            "delegation_id",
            "parent_goal_id",
            "child_goal_id",
            "status",
            "completed_at",
        }
        missing = required_keys - set(mapping.keys())
        if missing:
            raise AgentDelegationValidationError(
                f"Missing required fields: {sorted(missing)}"
            )

        def parse_dt(val: Any, name: str) -> datetime:
            if isinstance(val, datetime):
                return _ensure_tz_aware(val, name)
            if isinstance(val, str):
                return _ensure_tz_aware(datetime.fromisoformat(val), name)
            raise AgentDelegationValidationError(
                f"{name} must be datetime or ISO string"
            )

        return cls(
            delegation_id=str(mapping["delegation_id"]),
            parent_goal_id=str(mapping["parent_goal_id"]),
            child_goal_id=str(mapping["child_goal_id"]),
            delegated_run_id=mapping.get("delegated_run_id"),
            status=mapping["status"],
            agent_result_id=mapping.get("agent_result_id"),
            outputs=tuple(mapping.get("outputs", ())),
            knowledge_ids=tuple(mapping.get("knowledge_ids", ())),
            artifacts=tuple(mapping.get("artifacts", ())),
            warnings=tuple(mapping.get("warnings", ())),
            errors=tuple(mapping.get("errors", ())),
            completed_at=parse_dt(mapping["completed_at"], "completed_at"),
            metadata=MappingProxyType(dict(mapping.get("metadata", {}))),
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DelegationResult:
        return cls.from_mapping(data)


# ── Factory function for creating delegations ────────────────────────────────


def create_delegation(
    *,
    parent_goal: Goal,
    child_goal: Goal,
    source_agent_id: str,
    target_agent_id: str,
    source_agent_run_id: str | None = None,
    expected_result: Mapping[str, Any] | None = None,
    constraints: tuple[GoalConstraint, ...] = (),
    depth: int = 0,
    correlation_id: str | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> DelegatedGoal:
    """
    Factory function to create a new delegation with proper validation.

    Args:
        parent_goal: The parent goal being delegated from.
        child_goal: The child goal created for delegation.
        source_agent_id: The agent proposing the delegation.
        target_agent_id: The agent receiving the delegation.
        source_agent_run_id: Optional run ID of the source agent.
        expected_result: Expected result structure.
        constraints: Constraints to apply to the delegation.
        depth: Delegation depth (0 for direct children).
        correlation_id: Optional correlation ID for tracing.
        metadata: Additional metadata.

    Returns:
        A new DelegatedGoal instance with status PROPOSED.
    """
    now = _now_utc()
    delegation_id = _generate_id()

    return DelegatedGoal(
        id=delegation_id,
        parent_goal_id=parent_goal.id,
        child_goal_id=child_goal.id,
        source_agent_id=source_agent_id,
        target_agent_id=target_agent_id,
        source_agent_run_id=source_agent_run_id,
        target_agent_run_id=None,
        expected_result=MappingProxyType(dict(expected_result or {})),
        constraints=constraints,
        status=DelegationStatus.PROPOSED,
        created_at=now,
        updated_at=now,
        completed_at=None,
        metadata=MappingProxyType(dict(metadata or {})),
        depth=depth,
        correlation_id=correlation_id,
    )


__all__ = [
    "DelegatedGoal",
    "DelegationProposal",
    "DelegationResult",
    "create_delegation",
]
