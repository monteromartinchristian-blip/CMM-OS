"""Phase 9.2 – Goal System Contracts.

Defines immutable, typed, serializable contracts for Goal, GoalPriority,
SuccessCriterion, GoalConstraint, GoalDependency, GoalHistoryEntry, GoalQuery,
and GoalSearchResult.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from types import MappingProxyType
from typing import Any

from cmm.agent_runtime.contracts import (
    _freeze_metadata,
    _freeze_str_tuple,
)
from cmm.agent_runtime.enums import (
    GoalConstraintKind,
    GoalDependencyType,
    GoalKind,
    GoalStatus,
    SuccessCriterionKind,
    SuccessCriterionStatus,
)
from cmm.agent_runtime.errors import (
    GoalDependencyError,
    InvalidGoalContractError,
)


def _enum_value(value: Any) -> Any:
    """Serialize enum-like contract values without assuming normalization."""
    return value.value if isinstance(value, Enum) else value


def _ensure_tz_aware(dt: datetime, field_name: str) -> datetime:
    """Ensure a datetime object is timezone-aware."""
    if not isinstance(dt, datetime):
        raise InvalidGoalContractError(f"{field_name} must be a datetime instance")
    if dt.tzinfo is None:
        raise InvalidGoalContractError(f"{field_name} must be timezone-aware")
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
            raise InvalidGoalContractError(
                f"Invalid isoformat datetime string for {field_name}: {val!r}"
            ) from exc
    raise InvalidGoalContractError(
        f"{field_name} must be an ISO string or datetime instance"
    )


def _validate_non_empty_str(val: Any, field_name: str) -> str:
    """Validate that value is a non-empty string."""
    if not isinstance(val, str) or not val.strip():
        raise InvalidGoalContractError(f"{field_name} must be a non-empty string")
    return val.strip()


def _validate_score_range(
    val: Any, field_name: str, min_val: float = 0.0, max_val: float = 100.0
) -> float:
    """Validate numeric score within range."""
    if not isinstance(val, (int, float)) or isinstance(val, bool):
        raise InvalidGoalContractError(f"{field_name} must be a number")
    fval = float(val)
    if fval < min_val or fval > max_val:
        raise InvalidGoalContractError(
            f"{field_name} must be between {min_val} and {max_val}, got {fval}"
        )
    return fval


def _validate_non_negative_float(val: Any, field_name: str) -> float:
    """Validate number >= 0.0."""
    if not isinstance(val, (int, float)) or isinstance(val, bool):
        raise InvalidGoalContractError(f"{field_name} must be a number")
    fval = float(val)
    if fval < 0.0:
        raise InvalidGoalContractError(f"{field_name} must be >= 0.0, got {fval}")
    return fval


@dataclass(frozen=True, slots=True)
class GoalPriority:
    """Multi-factorial priority calculation for operational goals."""

    score: float = 50.0
    urgency: float = 50.0
    importance: float = 50.0
    user_priority: float = 50.0
    deadline_pressure: float = 0.0
    dependency_impact: float = 0.0
    risk_reduction: float = 0.0
    estimated_cost: float = 0.0
    reasons: tuple[str, ...] = ()
    calculated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: MappingProxyType[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )

    def __post_init__(self) -> None:
        object.__setattr__(self, "score", _validate_score_range(self.score, "score"))
        object.__setattr__(
            self, "urgency", _validate_score_range(self.urgency, "urgency")
        )
        object.__setattr__(
            self, "importance", _validate_score_range(self.importance, "importance")
        )
        object.__setattr__(
            self,
            "user_priority",
            _validate_score_range(self.user_priority, "user_priority"),
        )
        object.__setattr__(
            self,
            "deadline_pressure",
            _validate_score_range(self.deadline_pressure, "deadline_pressure"),
        )
        object.__setattr__(
            self,
            "dependency_impact",
            _validate_score_range(self.dependency_impact, "dependency_impact"),
        )
        object.__setattr__(
            self,
            "risk_reduction",
            _validate_score_range(self.risk_reduction, "risk_reduction"),
        )
        object.__setattr__(
            self,
            "estimated_cost",
            _validate_non_negative_float(self.estimated_cost, "estimated_cost"),
        )
        object.__setattr__(self, "reasons", _freeze_str_tuple(self.reasons, "reasons"))
        object.__setattr__(
            self,
            "calculated_at",
            _parse_datetime(self.calculated_at, "calculated_at"),
        )
        object.__setattr__(self, "metadata", _freeze_metadata(self.metadata))

    def serialize(self) -> dict[str, Any]:
        """Serialize contract to dictionary."""
        return {
            "score": self.score,
            "urgency": self.urgency,
            "importance": self.importance,
            "user_priority": self.user_priority,
            "deadline_pressure": self.deadline_pressure,
            "dependency_impact": self.dependency_impact,
            "risk_reduction": self.risk_reduction,
            "estimated_cost": self.estimated_cost,
            "reasons": list(self.reasons),
            "calculated_at": self.calculated_at.isoformat(),
            "metadata": dict(self.metadata),
        }

    def to_dict(self) -> dict[str, Any]:
        """Alias for serialize()."""
        return self.serialize()

    @classmethod
    def from_mapping(cls, mapping: Mapping[str, Any]) -> GoalPriority:
        """Construct GoalPriority from a mapping."""
        if not isinstance(mapping, Mapping):
            raise InvalidGoalContractError("mapping must be a Mapping instance")

        return cls(
            score=mapping.get("score", 50.0),
            urgency=mapping.get("urgency", 50.0),
            importance=mapping.get("importance", 50.0),
            user_priority=mapping.get("user_priority", 50.0),
            deadline_pressure=mapping.get("deadline_pressure", 0.0),
            dependency_impact=mapping.get("dependency_impact", 0.0),
            risk_reduction=mapping.get("risk_reduction", 0.0),
            estimated_cost=mapping.get("estimated_cost", 0.0),
            reasons=tuple(mapping.get("reasons", ())),
            calculated_at=_parse_datetime(
                mapping.get("calculated_at", datetime.now(timezone.utc)),
                "calculated_at",
            ),
            metadata=mapping.get("metadata", {}),
        )

    @classmethod
    def from_dict(cls, mapping: Mapping[str, Any]) -> GoalPriority:
        """Alias for from_mapping()."""
        return cls.from_mapping(mapping)


@dataclass(frozen=True, slots=True)
class SuccessCriterion:
    """Verifiable condition required for goal satisfaction."""

    id: str
    description: str
    kind: SuccessCriterionKind | str = SuccessCriterionKind.VALIDATION
    required: bool = True
    measurable: bool = True
    evaluator: str = ""
    expected_value: Any = None
    actual_value: Any = None
    status: SuccessCriterionStatus | str = SuccessCriterionStatus.PENDING
    evidence: tuple[str, ...] = ()
    metadata: MappingProxyType[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )

    def __post_init__(self) -> None:
        _validate_non_empty_str(self.id, "id")
        _validate_non_empty_str(self.description, "description")

        if isinstance(self.kind, str):
            try:
                object.__setattr__(self, "kind", SuccessCriterionKind(self.kind))
            except ValueError as exc:
                raise InvalidGoalContractError(
                    f"Invalid SuccessCriterionKind string: {self.kind!r}"
                ) from exc
        elif not isinstance(self.kind, SuccessCriterionKind):
            raise InvalidGoalContractError(
                "kind must be a SuccessCriterionKind or valid string"
            )

        if isinstance(self.status, str):
            try:
                object.__setattr__(self, "status", SuccessCriterionStatus(self.status))
            except ValueError as exc:
                raise InvalidGoalContractError(
                    f"Invalid SuccessCriterionStatus string: {self.status!r}"
                ) from exc
        elif not isinstance(self.status, SuccessCriterionStatus):
            raise InvalidGoalContractError(
                "status must be a SuccessCriterionStatus or valid string"
            )

        if not isinstance(self.required, bool):
            raise InvalidGoalContractError("required must be a boolean")
        if not isinstance(self.measurable, bool):
            raise InvalidGoalContractError("measurable must be a boolean")

        object.__setattr__(
            self, "evidence", _freeze_str_tuple(self.evidence, "evidence")
        )
        object.__setattr__(self, "metadata", _freeze_metadata(self.metadata))

    def serialize(self) -> dict[str, Any]:
        """Serialize contract to dictionary."""
        return {
            "id": self.id,
            "description": self.description,
            "kind": _enum_value(self.kind),
            "required": self.required,
            "measurable": self.measurable,
            "evaluator": self.evaluator,
            "expected_value": self.expected_value,
            "actual_value": self.actual_value,
            "status": _enum_value(self.status),
            "evidence": list(self.evidence),
            "metadata": dict(self.metadata),
        }

    def to_dict(self) -> dict[str, Any]:
        """Alias for serialize()."""
        return self.serialize()

    @classmethod
    def from_mapping(cls, mapping: Mapping[str, Any]) -> SuccessCriterion:
        """Construct SuccessCriterion from a mapping."""
        if not isinstance(mapping, Mapping):
            raise InvalidGoalContractError("mapping must be a Mapping instance")

        required_keys = {"id", "description"}
        missing = required_keys - set(mapping.keys())
        if missing:
            raise InvalidGoalContractError(
                f"Missing required fields in mapping: {sorted(missing)}"
            )

        return cls(
            id=str(mapping["id"]),
            description=str(mapping["description"]),
            kind=mapping.get("kind", SuccessCriterionKind.VALIDATION),
            required=bool(mapping.get("required", True)),
            measurable=bool(mapping.get("measurable", True)),
            evaluator=str(mapping.get("evaluator", "")),
            expected_value=mapping.get("expected_value"),
            actual_value=mapping.get("actual_value"),
            status=mapping.get("status", SuccessCriterionStatus.PENDING),
            evidence=tuple(mapping.get("evidence", ())),
            metadata=mapping.get("metadata", {}),
        )

    @classmethod
    def from_dict(cls, mapping: Mapping[str, Any]) -> SuccessCriterion:
        """Alias for from_mapping()."""
        return cls.from_mapping(mapping)


@dataclass(frozen=True, slots=True)
class GoalConstraint:
    """Operational constraint or boundary for goal pursuit."""

    id: str
    description: str
    kind: GoalConstraintKind | str = GoalConstraintKind.TECHNICAL
    severity: str = "blocking"
    source: str = "user"
    condition: MappingProxyType[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )
    metadata: MappingProxyType[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )

    def __post_init__(self) -> None:
        _validate_non_empty_str(self.id, "id")
        _validate_non_empty_str(self.description, "description")

        if isinstance(self.kind, str):
            try:
                object.__setattr__(self, "kind", GoalConstraintKind(self.kind))
            except ValueError as exc:
                raise InvalidGoalContractError(
                    f"Invalid GoalConstraintKind string: {self.kind!r}"
                ) from exc
        elif not isinstance(self.kind, GoalConstraintKind):
            raise InvalidGoalContractError(
                "kind must be a GoalConstraintKind or valid string"
            )

        _validate_non_empty_str(self.severity, "severity")
        _validate_non_empty_str(self.source, "source")

        object.__setattr__(self, "condition", _freeze_metadata(self.condition))
        object.__setattr__(self, "metadata", _freeze_metadata(self.metadata))

    def serialize(self) -> dict[str, Any]:
        """Serialize contract to dictionary."""
        return {
            "id": self.id,
            "description": self.description,
            "kind": _enum_value(self.kind),
            "severity": self.severity,
            "source": self.source,
            "condition": dict(self.condition),
            "metadata": dict(self.metadata),
        }

    def to_dict(self) -> dict[str, Any]:
        """Alias for serialize()."""
        return self.serialize()

    @classmethod
    def from_mapping(cls, mapping: Mapping[str, Any]) -> GoalConstraint:
        """Construct GoalConstraint from a mapping."""
        if not isinstance(mapping, Mapping):
            raise InvalidGoalContractError("mapping must be a Mapping instance")

        required_keys = {"id", "description"}
        missing = required_keys - set(mapping.keys())
        if missing:
            raise InvalidGoalContractError(
                f"Missing required fields in mapping: {sorted(missing)}"
            )

        return cls(
            id=str(mapping["id"]),
            description=str(mapping["description"]),
            kind=mapping.get("kind", GoalConstraintKind.TECHNICAL),
            severity=str(mapping.get("severity", "blocking")),
            source=str(mapping.get("source", "user")),
            condition=mapping.get("condition", {}),
            metadata=mapping.get("metadata", {}),
        )

    @classmethod
    def from_dict(cls, mapping: Mapping[str, Any]) -> GoalConstraint:
        """Alias for from_mapping()."""
        return cls.from_mapping(mapping)


@dataclass(frozen=True, slots=True)
class GoalDependency:
    """Dependency relationship between goals."""

    goal_id: str
    depends_on_goal_id: str
    dependency_type: GoalDependencyType | str = GoalDependencyType.REQUIRES_COMPLETION
    blocking: bool = True
    metadata: MappingProxyType[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )

    def __post_init__(self) -> None:
        _validate_non_empty_str(self.goal_id, "goal_id")
        _validate_non_empty_str(self.depends_on_goal_id, "depends_on_goal_id")

        if self.goal_id == self.depends_on_goal_id:
            raise GoalDependencyError("A goal cannot depend on itself")

        if isinstance(self.dependency_type, str):
            try:
                object.__setattr__(
                    self, "dependency_type", GoalDependencyType(self.dependency_type)
                )
            except ValueError as exc:
                raise InvalidGoalContractError(
                    f"Invalid GoalDependencyType string: {self.dependency_type!r}"
                ) from exc
        elif not isinstance(self.dependency_type, GoalDependencyType):
            raise InvalidGoalContractError(
                "dependency_type must be a GoalDependencyType or valid string"
            )

        if not isinstance(self.blocking, bool):
            raise InvalidGoalContractError("blocking must be a boolean")

        object.__setattr__(self, "metadata", _freeze_metadata(self.metadata))

    def serialize(self) -> dict[str, Any]:
        """Serialize contract to dictionary."""
        return {
            "goal_id": self.goal_id,
            "depends_on_goal_id": self.depends_on_goal_id,
            "dependency_type": _enum_value(self.dependency_type),
            "blocking": self.blocking,
            "metadata": dict(self.metadata),
        }

    def to_dict(self) -> dict[str, Any]:
        """Alias for serialize()."""
        return self.serialize()

    @classmethod
    def from_mapping(cls, mapping: Mapping[str, Any]) -> GoalDependency:
        """Construct GoalDependency from a mapping."""
        if not isinstance(mapping, Mapping):
            raise InvalidGoalContractError("mapping must be a Mapping instance")

        required_keys = {"goal_id", "depends_on_goal_id"}
        missing = required_keys - set(mapping.keys())
        if missing:
            raise InvalidGoalContractError(
                f"Missing required fields in mapping: {sorted(missing)}"
            )

        return cls(
            goal_id=str(mapping["goal_id"]),
            depends_on_goal_id=str(mapping["depends_on_goal_id"]),
            dependency_type=mapping.get(
                "dependency_type", GoalDependencyType.REQUIRES_COMPLETION
            ),
            blocking=bool(mapping.get("blocking", True)),
            metadata=mapping.get("metadata", {}),
        )

    @classmethod
    def from_dict(cls, mapping: Mapping[str, Any]) -> GoalDependency:
        """Alias for from_mapping()."""
        return cls.from_mapping(mapping)


@dataclass(frozen=True, slots=True)
class GoalHistoryEntry:
    """Audit log entry capturing state transitions and decision events on a Goal."""

    id: str
    goal_id: str
    previous_status: GoalStatus | str | None
    new_status: GoalStatus | str
    actor_id: str
    reason: str
    decision_id: str | None = None
    evidence: tuple[str, ...] = ()
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    related_run_id: str | None = None
    applied_policy: str | None = None
    metadata: MappingProxyType[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )

    def __post_init__(self) -> None:
        _validate_non_empty_str(self.id, "id")
        _validate_non_empty_str(self.goal_id, "goal_id")
        _validate_non_empty_str(self.actor_id, "actor_id")
        _validate_non_empty_str(self.reason, "reason")

        if self.previous_status is not None:
            if isinstance(self.previous_status, str):
                try:
                    object.__setattr__(
                        self, "previous_status", GoalStatus(self.previous_status)
                    )
                except ValueError as exc:
                    raise InvalidGoalContractError(
                        f"Invalid GoalStatus string for previous_status: {self.previous_status!r}"
                    ) from exc
            elif not isinstance(self.previous_status, GoalStatus):
                raise InvalidGoalContractError(
                    "previous_status must be a GoalStatus, valid string, or None"
                )

        if isinstance(self.new_status, str):
            try:
                object.__setattr__(self, "new_status", GoalStatus(self.new_status))
            except ValueError as exc:
                raise InvalidGoalContractError(
                    f"Invalid GoalStatus string for new_status: {self.new_status!r}"
                ) from exc
        elif not isinstance(self.new_status, GoalStatus):
            raise InvalidGoalContractError(
                "new_status must be a GoalStatus or valid string"
            )

        object.__setattr__(
            self, "evidence", _freeze_str_tuple(self.evidence, "evidence")
        )
        object.__setattr__(
            self, "timestamp", _parse_datetime(self.timestamp, "timestamp")
        )
        object.__setattr__(self, "metadata", _freeze_metadata(self.metadata))

    def serialize(self) -> dict[str, Any]:
        """Serialize contract to dictionary."""
        return {
            "id": self.id,
            "goal_id": self.goal_id,
            "previous_status": _enum_value(self.previous_status),
            "new_status": (
                self.new_status.value
                if isinstance(self.new_status, GoalStatus)
                else self.new_status
            ),
            "actor_id": self.actor_id,
            "reason": self.reason,
            "decision_id": self.decision_id,
            "evidence": list(self.evidence),
            "timestamp": self.timestamp.isoformat(),
            "related_run_id": self.related_run_id,
            "applied_policy": self.applied_policy,
            "metadata": dict(self.metadata),
        }

    def to_dict(self) -> dict[str, Any]:
        """Alias for serialize()."""
        return self.serialize()

    @classmethod
    def from_mapping(cls, mapping: Mapping[str, Any]) -> GoalHistoryEntry:
        """Construct GoalHistoryEntry from a mapping."""
        if not isinstance(mapping, Mapping):
            raise InvalidGoalContractError("mapping must be a Mapping instance")

        required_keys = {"id", "goal_id", "new_status", "actor_id", "reason"}
        missing = required_keys - set(mapping.keys())
        if missing:
            raise InvalidGoalContractError(
                f"Missing required fields in mapping: {sorted(missing)}"
            )

        return cls(
            id=str(mapping["id"]),
            goal_id=str(mapping["goal_id"]),
            previous_status=mapping.get("previous_status"),
            new_status=mapping["new_status"],
            actor_id=str(mapping["actor_id"]),
            reason=str(mapping["reason"]),
            decision_id=mapping.get("decision_id"),
            evidence=tuple(mapping.get("evidence", ())),
            timestamp=_parse_datetime(
                mapping.get("timestamp", datetime.now(timezone.utc)), "timestamp"
            ),
            related_run_id=mapping.get("related_run_id"),
            applied_policy=mapping.get("applied_policy"),
            metadata=mapping.get("metadata", {}),
        )

    @classmethod
    def from_dict(cls, mapping: Mapping[str, Any]) -> GoalHistoryEntry:
        """Alias for from_mapping()."""
        return cls.from_mapping(mapping)


@dataclass(frozen=True, slots=True)
class Goal:
    """Core operational goal entity in the Agent Runtime."""

    id: str
    title: str
    description: str
    kind: GoalKind | str
    status: GoalStatus | str
    priority: GoalPriority
    urgency: float = 0.0
    importance: float = 0.0
    value: float = 0.0
    confidence: float = 1.0
    success_criteria: tuple[SuccessCriterion, ...] = ()
    constraints: tuple[GoalConstraint, ...] = ()
    requirements: tuple[str, ...] = ()
    dependencies: tuple[GoalDependency, ...] = ()
    blocked_by: tuple[str, ...] = ()
    parent_goal_id: str | None = None
    child_goal_ids: tuple[str, ...] = ()
    source: str = "user"
    owner_actor_id: str = "actor-user"
    assigned_agent_id: str | None = None
    autonomy_level: int | None = None
    deadline: datetime | None = None
    temporal_scope: MappingProxyType[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )
    sensitivity: str = "internal"
    permissions: tuple[str, ...] = ()
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime | None = None
    metadata: MappingProxyType[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )

    def __post_init__(self) -> None:
        _validate_non_empty_str(self.id, "id")
        _validate_non_empty_str(self.title, "title")

        if isinstance(self.kind, str):
            try:
                object.__setattr__(self, "kind", GoalKind(self.kind))
            except ValueError as exc:
                raise InvalidGoalContractError(
                    f"Invalid GoalKind string: {self.kind!r}"
                ) from exc
        elif not isinstance(self.kind, GoalKind):
            raise InvalidGoalContractError("kind must be a GoalKind or valid string")

        if isinstance(self.status, str):
            try:
                object.__setattr__(self, "status", GoalStatus(self.status))
            except ValueError as exc:
                raise InvalidGoalContractError(
                    f"Invalid GoalStatus string: {self.status!r}"
                ) from exc
        elif not isinstance(self.status, GoalStatus):
            raise InvalidGoalContractError(
                "status must be a GoalStatus or valid string"
            )

        if not isinstance(self.priority, GoalPriority):
            raise InvalidGoalContractError("priority must be a GoalPriority instance")

        object.__setattr__(
            self, "urgency", _validate_score_range(self.urgency, "urgency")
        )
        object.__setattr__(
            self, "importance", _validate_score_range(self.importance, "importance")
        )
        object.__setattr__(self, "value", _validate_score_range(self.value, "value"))
        object.__setattr__(
            self,
            "confidence",
            _validate_score_range(
                self.confidence, "confidence", min_val=0.0, max_val=1.0
            ),
        )

        # Validate parent / child invariants
        if self.parent_goal_id is not None:
            _validate_non_empty_str(self.parent_goal_id, "parent_goal_id")
            if self.parent_goal_id == self.id:
                raise InvalidGoalContractError("A goal cannot be a parent of itself")

        child_ids = _freeze_str_tuple(self.child_goal_ids, "child_goal_ids")
        if self.id in child_ids:
            raise InvalidGoalContractError("A goal cannot be a child of itself")
        object.__setattr__(self, "child_goal_ids", child_ids)

        # Freeze criteria
        if self.success_criteria:
            criteria_list = []
            for sc in self.success_criteria:
                if isinstance(sc, Mapping):
                    sc = SuccessCriterion.from_mapping(sc)
                elif not isinstance(sc, SuccessCriterion):
                    raise InvalidGoalContractError(
                        "success_criteria items must be SuccessCriterion instances"
                    )
                criteria_list.append(sc)
            object.__setattr__(self, "success_criteria", tuple(criteria_list))

        # Freeze constraints
        if self.constraints:
            constraints_list = []
            for gc in self.constraints:
                if isinstance(gc, Mapping):
                    gc = GoalConstraint.from_mapping(gc)
                elif not isinstance(gc, GoalConstraint):
                    raise InvalidGoalContractError(
                        "constraints items must be GoalConstraint instances"
                    )
                constraints_list.append(gc)
            object.__setattr__(self, "constraints", tuple(constraints_list))

        object.__setattr__(
            self, "requirements", _freeze_str_tuple(self.requirements, "requirements")
        )

        # Freeze dependencies & check self-dependency / duplicate dependencies
        if self.dependencies:
            deps_list = []
            seen_dep_keys: set[tuple[str, str]] = set()
            for dep in self.dependencies:
                if isinstance(dep, Mapping):
                    dep = GoalDependency.from_mapping(dep)
                elif not isinstance(dep, GoalDependency):
                    raise InvalidGoalContractError(
                        "dependencies items must be GoalDependency instances"
                    )
                if dep.depends_on_goal_id == self.id:
                    raise InvalidGoalContractError(
                        f"Goal {self.id} cannot depend on itself"
                    )
                dep_key = (
                    dep.depends_on_goal_id,
                    _enum_value(dep.dependency_type),
                )
                if dep_key in seen_dep_keys:
                    raise InvalidGoalContractError(
                        f"Duplicate dependency detected: {dep_key}"
                    )
                seen_dep_keys.add(dep_key)
                deps_list.append(dep)
            object.__setattr__(self, "dependencies", tuple(deps_list))

        object.__setattr__(
            self, "blocked_by", _freeze_str_tuple(self.blocked_by, "blocked_by")
        )
        object.__setattr__(
            self, "permissions", _freeze_str_tuple(self.permissions, "permissions")
        )

        _validate_non_empty_str(self.source, "source")
        _validate_non_empty_str(self.owner_actor_id, "owner_actor_id")
        _validate_non_empty_str(self.sensitivity, "sensitivity")

        if self.deadline is not None:
            object.__setattr__(
                self, "deadline", _parse_datetime(self.deadline, "deadline")
            )

        object.__setattr__(
            self,
            "created_at",
            _parse_datetime(self.created_at, "created_at"),
        )
        object.__setattr__(
            self,
            "updated_at",
            _parse_datetime(self.updated_at, "updated_at"),
        )

        # Completed_at invariants
        terminal_completed = (
            GoalStatus.COMPLETED,
            GoalStatus.PARTIALLY_COMPLETED,
        )
        if self.completed_at is not None:
            dt_comp = _parse_datetime(self.completed_at, "completed_at")
            if dt_comp < self.created_at:
                raise InvalidGoalContractError(
                    "completed_at cannot be prior to created_at"
                )
            object.__setattr__(self, "completed_at", dt_comp)
            if self.status not in terminal_completed:
                raise InvalidGoalContractError(
                    f"Non-completed goal with status '{self.status}' cannot have completed_at populated"
                )
        else:
            if self.status in terminal_completed:
                raise InvalidGoalContractError(
                    f"Completed goal with status '{self.status}' must have completed_at populated"
                )

        object.__setattr__(
            self, "temporal_scope", _freeze_metadata(self.temporal_scope)
        )
        object.__setattr__(self, "metadata", _freeze_metadata(self.metadata))

    def serialize(self) -> dict[str, Any]:
        """Serialize contract to dictionary."""
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "kind": _enum_value(self.kind),
            "status": _enum_value(self.status),
            "priority": self.priority.serialize(),
            "urgency": self.urgency,
            "importance": self.importance,
            "value": self.value,
            "confidence": self.confidence,
            "success_criteria": [sc.serialize() for sc in self.success_criteria],
            "constraints": [gc.serialize() for gc in self.constraints],
            "requirements": list(self.requirements),
            "dependencies": [dep.serialize() for dep in self.dependencies],
            "blocked_by": list(self.blocked_by),
            "parent_goal_id": self.parent_goal_id,
            "child_goal_ids": list(self.child_goal_ids),
            "source": self.source,
            "owner_actor_id": self.owner_actor_id,
            "assigned_agent_id": self.assigned_agent_id,
            "autonomy_level": self.autonomy_level,
            "deadline": self.deadline.isoformat() if self.deadline else None,
            "temporal_scope": dict(self.temporal_scope),
            "sensitivity": self.sensitivity,
            "permissions": list(self.permissions),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "completed_at": self.completed_at.isoformat()
            if self.completed_at
            else None,
            "metadata": dict(self.metadata),
        }

    def to_dict(self) -> dict[str, Any]:
        """Alias for serialize()."""
        return self.serialize()

    @classmethod
    def from_mapping(cls, mapping: Mapping[str, Any]) -> Goal:
        """Construct Goal from a mapping."""
        if not isinstance(mapping, Mapping):
            raise InvalidGoalContractError("mapping must be a Mapping instance")

        required_keys = {"id", "title", "description", "kind", "status"}
        missing = required_keys - set(mapping.keys())
        if missing:
            raise InvalidGoalContractError(
                f"Missing required fields in mapping: {sorted(missing)}"
            )

        p_map = mapping.get("priority", {})
        priority_obj = (
            GoalPriority.from_mapping(p_map) if isinstance(p_map, Mapping) else p_map
        )
        if not isinstance(priority_obj, GoalPriority):
            priority_obj = GoalPriority(
                score=float(p_map) if isinstance(p_map, (int, float)) else 50.0
            )

        sc_raw = mapping.get("success_criteria", ())
        sc_list = [
            SuccessCriterion.from_mapping(item) if isinstance(item, Mapping) else item
            for item in sc_raw
        ]

        c_raw = mapping.get("constraints", ())
        c_list = [
            GoalConstraint.from_mapping(item) if isinstance(item, Mapping) else item
            for item in c_raw
        ]

        dep_raw = mapping.get("dependencies", ())
        dep_list = [
            GoalDependency.from_mapping(item) if isinstance(item, Mapping) else item
            for item in dep_raw
        ]

        return cls(
            id=str(mapping["id"]),
            title=str(mapping["title"]),
            description=str(mapping["description"]),
            kind=mapping["kind"],
            status=mapping["status"],
            priority=priority_obj,
            urgency=mapping.get("urgency", 0.0),
            importance=mapping.get("importance", 0.0),
            value=mapping.get("value", 0.0),
            confidence=mapping.get("confidence", 1.0),
            success_criteria=tuple(sc_list),
            constraints=tuple(c_list),
            requirements=tuple(mapping.get("requirements", ())),
            dependencies=tuple(dep_list),
            blocked_by=tuple(mapping.get("blocked_by", ())),
            parent_goal_id=mapping.get("parent_goal_id"),
            child_goal_ids=tuple(mapping.get("child_goal_ids", ())),
            source=str(mapping.get("source", "user")),
            owner_actor_id=str(mapping.get("owner_actor_id", "actor-user")),
            assigned_agent_id=mapping.get("assigned_agent_id"),
            autonomy_level=mapping.get("autonomy_level"),
            deadline=_parse_datetime(mapping["deadline"], "deadline")
            if mapping.get("deadline")
            else None,
            temporal_scope=mapping.get("temporal_scope", {}),
            sensitivity=str(mapping.get("sensitivity", "internal")),
            permissions=tuple(mapping.get("permissions", ())),
            created_at=_parse_datetime(
                mapping.get("created_at", datetime.now(timezone.utc)), "created_at"
            ),
            updated_at=_parse_datetime(
                mapping.get("updated_at", datetime.now(timezone.utc)), "updated_at"
            ),
            completed_at=_parse_datetime(mapping["completed_at"], "completed_at")
            if mapping.get("completed_at")
            else None,
            metadata=mapping.get("metadata", {}),
        )

    @classmethod
    def from_dict(cls, mapping: Mapping[str, Any]) -> Goal:
        """Alias for from_mapping()."""
        return cls.from_mapping(mapping)


@dataclass(frozen=True, slots=True)
class GoalQuery:
    """Criteria filter for querying goals in a GoalRepository."""

    statuses: tuple[GoalStatus, ...] = ()
    kinds: tuple[GoalKind, ...] = ()
    min_priority: float | None = None
    owner_actor_id: str | None = None
    assigned_agent_id: str | None = None
    parent_goal_id: str | None = None
    text_search: str | None = None
    limit: int | None = None
    offset: int = 0

    def __post_init__(self) -> None:
        if self.statuses:
            status_list = []
            for st in self.statuses:
                if isinstance(st, str):
                    try:
                        st = GoalStatus(st)
                    except ValueError as exc:
                        raise InvalidGoalContractError(
                            f"Invalid GoalStatus string in query: {st!r}"
                        ) from exc
                elif not isinstance(st, GoalStatus):
                    raise InvalidGoalContractError(
                        "statuses items must be GoalStatus or valid strings"
                    )
                status_list.append(st)
            object.__setattr__(self, "statuses", tuple(status_list))

        if self.kinds:
            kind_list = []
            for k in self.kinds:
                if isinstance(k, str):
                    try:
                        k = GoalKind(k)
                    except ValueError as exc:
                        raise InvalidGoalContractError(
                            f"Invalid GoalKind string in query: {k!r}"
                        ) from exc
                elif not isinstance(k, GoalKind):
                    raise InvalidGoalContractError(
                        "kinds items must be GoalKind or valid strings"
                    )
                kind_list.append(k)
            object.__setattr__(self, "kinds", tuple(kind_list))

        if self.min_priority is not None:
            object.__setattr__(
                self,
                "min_priority",
                _validate_score_range(self.min_priority, "min_priority"),
            )

        if (
            not isinstance(self.offset, int)
            or isinstance(self.offset, bool)
            or self.offset < 0
        ):
            raise InvalidGoalContractError("offset must be a non-negative integer")

        if self.limit is not None and (
            not isinstance(self.limit, int)
            or isinstance(self.limit, bool)
            or self.limit <= 0
        ):
            raise InvalidGoalContractError("limit must be a positive integer")


@dataclass(frozen=True, slots=True)
class GoalSearchResult:
    """Paginated search results container returned by GoalRepository."""

    goals: tuple[Goal, ...]
    total_count: int
    limit: int | None
    offset: int

    def __post_init__(self) -> None:
        if not isinstance(self.total_count, int) or self.total_count < 0:
            raise InvalidGoalContractError("total_count must be a non-negative integer")
        if not isinstance(self.offset, int) or self.offset < 0:
            raise InvalidGoalContractError("offset must be a non-negative integer")
        if self.limit is not None and (
            not isinstance(self.limit, int) or self.limit <= 0
        ):
            raise InvalidGoalContractError("limit must be a positive integer")

        goals_list = []
        for g in self.goals:
            if not isinstance(g, Goal):
                raise InvalidGoalContractError("goals items must be Goal instances")
            goals_list.append(g)
        object.__setattr__(self, "goals", tuple(goals_list))
