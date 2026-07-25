"""Phase 9.3 – Goal Intake and Goal Normalization Contracts.

Defines immutable, typed, serializable contracts for GoalProposal, GoalAmbiguity,
GoalInformationGap, GoalNormalizationRequest, GoalNormalizationResult,
GoalIntakeDecision, and GoalProposalQuery.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from types import MappingProxyType
from typing import Any

from cmm.agent_runtime.contracts import (
    _freeze_metadata,
    _freeze_str_tuple,
)
from cmm.agent_runtime.enums import (
    GoalAmbiguityKind,
    GoalIntakeDecisionType,
    GoalKind,
    GoalProposalStatus,
    GoalSource,
)
from cmm.agent_runtime.errors import (
    GoalNormalizationError,
    InvalidGoalProposalError,
)
from cmm.agent_runtime.goal_contracts import (
    GoalConstraint,
    GoalDependency,
    GoalPriority,
    SuccessCriterion,
    _parse_datetime,
    _validate_non_empty_str,
    _validate_score_range,
)


@dataclass(frozen=True, slots=True)
class GoalAmbiguity:
    """Represents a identified ambiguity or missing specification in a GoalProposal."""

    id: str
    kind: GoalAmbiguityKind | str
    description: str
    field_name: str = ""
    blocking: bool = True
    suggested_resolution: str = ""
    metadata: MappingProxyType[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )

    def __post_init__(self) -> None:
        _validate_non_empty_str(self.id, "id")
        _validate_non_empty_str(self.description, "description")

        if isinstance(self.kind, str):
            try:
                object.__setattr__(self, "kind", GoalAmbiguityKind(self.kind))
            except ValueError as exc:
                raise InvalidGoalProposalError(
                    f"Invalid GoalAmbiguityKind string: {self.kind!r}"
                ) from exc
        elif not isinstance(self.kind, GoalAmbiguityKind):
            raise InvalidGoalProposalError(
                "kind must be a GoalAmbiguityKind or valid string"
            )

        if not isinstance(self.blocking, bool):
            raise InvalidGoalProposalError("blocking must be a boolean")

        object.__setattr__(self, "metadata", _freeze_metadata(self.metadata))

    def serialize(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind.value
            if isinstance(self.kind, GoalAmbiguityKind)
            else self.kind,
            "description": self.description,
            "field_name": self.field_name,
            "blocking": self.blocking,
            "suggested_resolution": self.suggested_resolution,
            "metadata": dict(self.metadata),
        }

    def to_dict(self) -> dict[str, Any]:
        return self.serialize()

    @classmethod
    def from_mapping(cls, mapping: Mapping[str, Any]) -> GoalAmbiguity:
        if not isinstance(mapping, Mapping):
            raise InvalidGoalProposalError("mapping must be a Mapping instance")

        required_keys = {"id", "kind", "description"}
        missing = required_keys - set(mapping.keys())
        if missing:
            raise InvalidGoalProposalError(
                f"Missing required fields in mapping: {sorted(missing)}"
            )

        return cls(
            id=str(mapping["id"]),
            kind=mapping["kind"],
            description=str(mapping["description"]),
            field_name=str(mapping.get("field_name", "")),
            blocking=bool(mapping.get("blocking", True)),
            suggested_resolution=str(mapping.get("suggested_resolution", "")),
            metadata=mapping.get("metadata", {}),
        )

    @classmethod
    def from_dict(cls, mapping: Mapping[str, Any]) -> GoalAmbiguity:
        return cls.from_mapping(mapping)


@dataclass(frozen=True, slots=True)
class GoalInformationGap:
    """Represents a specific structured information gap that must be answered."""

    id: str
    question: str
    topic: str = ""
    impact: str = ""
    required: bool = True
    metadata: MappingProxyType[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )

    def __post_init__(self) -> None:
        _validate_non_empty_str(self.id, "id")
        _validate_non_empty_str(self.question, "question")

        if not isinstance(self.required, bool):
            raise InvalidGoalProposalError("required must be a boolean")

        object.__setattr__(self, "metadata", _freeze_metadata(self.metadata))

    def serialize(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "question": self.question,
            "topic": self.topic,
            "impact": self.impact,
            "required": self.required,
            "metadata": dict(self.metadata),
        }

    def to_dict(self) -> dict[str, Any]:
        return self.serialize()

    @classmethod
    def from_mapping(cls, mapping: Mapping[str, Any]) -> GoalInformationGap:
        if not isinstance(mapping, Mapping):
            raise InvalidGoalProposalError("mapping must be a Mapping instance")

        required_keys = {"id", "question"}
        missing = required_keys - set(mapping.keys())
        if missing:
            raise InvalidGoalProposalError(
                f"Missing required fields in mapping: {sorted(missing)}"
            )

        return cls(
            id=str(mapping["id"]),
            question=str(mapping["question"]),
            topic=str(mapping.get("topic", "")),
            impact=str(mapping.get("impact", "")),
            required=bool(mapping.get("required", True)),
            metadata=mapping.get("metadata", {}),
        )

    @classmethod
    def from_dict(cls, mapping: Mapping[str, Any]) -> GoalInformationGap:
        return cls.from_mapping(mapping)


@dataclass(frozen=True, slots=True)
class GoalProposal:
    """Structured proposal representation generated from goal intake and normalization."""

    id: str
    source: GoalSource | str
    raw_objective: str
    normalized_title: str
    normalized_description: str
    proposed_kind: GoalKind | str
    proposed_priority: GoalPriority | None = None
    proposed_success_criteria: tuple[SuccessCriterion, ...] = ()
    proposed_constraints: tuple[GoalConstraint, ...] = ()
    proposed_deadline: datetime | None = None
    proposed_owner_actor_id: str = "actor-user"
    proposed_autonomy_level: int = 1
    proposed_sensitivity: str = "internal"
    proposed_permissions: tuple[str, ...] = ()
    proposed_dependencies: tuple[GoalDependency, ...] = ()
    ambiguities: tuple[GoalAmbiguity, ...] = ()
    information_gaps: tuple[GoalInformationGap, ...] = ()
    requires_confirmation: bool = False
    confidence: float = 1.0
    status: GoalProposalStatus | str = GoalProposalStatus.CREATED
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: MappingProxyType[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )

    def __post_init__(self) -> None:
        _validate_non_empty_str(self.id, "id")
        _validate_non_empty_str(self.raw_objective, "raw_objective")
        _validate_non_empty_str(self.proposed_owner_actor_id, "proposed_owner_actor_id")

        if isinstance(self.source, str):
            try:
                object.__setattr__(self, "source", GoalSource(self.source))
            except ValueError as exc:
                raise InvalidGoalProposalError(
                    f"Invalid GoalSource string: {self.source!r}"
                ) from exc
        elif not isinstance(self.source, GoalSource):
            raise InvalidGoalProposalError(
                "source must be a GoalSource or valid string"
            )

        if isinstance(self.proposed_kind, str):
            try:
                object.__setattr__(self, "proposed_kind", GoalKind(self.proposed_kind))
            except ValueError as exc:
                raise InvalidGoalProposalError(
                    f"Invalid GoalKind string: {self.proposed_kind!r}"
                ) from exc
        elif not isinstance(self.proposed_kind, GoalKind):
            raise InvalidGoalProposalError(
                "proposed_kind must be a GoalKind or valid string"
            )

        if isinstance(self.status, str):
            try:
                object.__setattr__(self, "status", GoalProposalStatus(self.status))
            except ValueError as exc:
                raise InvalidGoalProposalError(
                    f"Invalid GoalProposalStatus string: {self.status!r}"
                ) from exc
        elif not isinstance(self.status, GoalProposalStatus):
            raise InvalidGoalProposalError(
                "status must be a GoalProposalStatus or valid string"
            )

        if self.proposed_priority is not None and not isinstance(
            self.proposed_priority, GoalPriority
        ):
            raise InvalidGoalProposalError(
                "proposed_priority must be a GoalPriority instance or None"
            )

        if not isinstance(self.proposed_autonomy_level, int) or isinstance(
            self.proposed_autonomy_level, bool
        ):
            raise InvalidGoalProposalError(
                "proposed_autonomy_level must be an integer (>= 0)"
            )
        if self.proposed_autonomy_level < 0:
            raise InvalidGoalProposalError(
                f"proposed_autonomy_level cannot be negative, got {self.proposed_autonomy_level}"
            )

        try:
            object.__setattr__(
                self,
                "confidence",
                _validate_score_range(
                    self.confidence, "confidence", min_val=0.0, max_val=1.0
                ),
            )
        except Exception as exc:
            raise InvalidGoalProposalError(str(exc)) from exc

        if self.proposed_deadline is not None:
            object.__setattr__(
                self,
                "proposed_deadline",
                _parse_datetime(self.proposed_deadline, "proposed_deadline"),
            )

        # Freeze collections
        object.__setattr__(
            self,
            "proposed_success_criteria",
            tuple(self.proposed_success_criteria),
        )
        for crit in self.proposed_success_criteria:
            if not isinstance(crit, SuccessCriterion):
                raise InvalidGoalProposalError(
                    "All items in proposed_success_criteria must be SuccessCriterion instances"
                )

        object.__setattr__(
            self,
            "proposed_constraints",
            tuple(self.proposed_constraints),
        )
        for constr in self.proposed_constraints:
            if not isinstance(constr, GoalConstraint):
                raise InvalidGoalProposalError(
                    "All items in proposed_constraints must be GoalConstraint instances"
                )

        object.__setattr__(
            self,
            "proposed_permissions",
            _freeze_str_tuple(self.proposed_permissions, "proposed_permissions"),
        )

        object.__setattr__(
            self,
            "proposed_dependencies",
            tuple(self.proposed_dependencies),
        )
        for dep in self.proposed_dependencies:
            if not isinstance(dep, GoalDependency):
                raise InvalidGoalProposalError(
                    "All items in proposed_dependencies must be GoalDependency instances"
                )
            if (
                dep.goal_id == dep.depends_on_goal_id
                or dep.depends_on_goal_id == self.id
            ):
                raise InvalidGoalProposalError(
                    f"Proposal dependency loop detected: proposal cannot depend on itself ({self.id})"
                )

        object.__setattr__(self, "ambiguities", tuple(self.ambiguities))
        for amb in self.ambiguities:
            if not isinstance(amb, GoalAmbiguity):
                raise InvalidGoalProposalError(
                    "All items in ambiguities must be GoalAmbiguity instances"
                )

        object.__setattr__(self, "information_gaps", tuple(self.information_gaps))
        for gap in self.information_gaps:
            if not isinstance(gap, GoalInformationGap):
                raise InvalidGoalProposalError(
                    "All items in information_gaps must be GoalInformationGap instances"
                )

        object.__setattr__(
            self, "created_at", _parse_datetime(self.created_at, "created_at")
        )
        object.__setattr__(self, "metadata", _freeze_metadata(self.metadata))

        # Validate invariants #5 and #6 regarding ambiguities & confirmation & READY status
        blocking_ambiguities = [amb for amb in self.ambiguities if amb.blocking]
        if blocking_ambiguities and not self.requires_confirmation:
            object.__setattr__(self, "requires_confirmation", True)

        if self.status == GoalProposalStatus.READY and blocking_ambiguities:
            raise InvalidGoalProposalError(
                "A proposal with status READY cannot contain blocking ambiguities"
            )

    def serialize(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "source": self.source.value
            if isinstance(self.source, GoalSource)
            else self.source,
            "raw_objective": self.raw_objective,
            "normalized_title": self.normalized_title,
            "normalized_description": self.normalized_description,
            "proposed_kind": (
                self.proposed_kind.value
                if isinstance(self.proposed_kind, GoalKind)
                else self.proposed_kind
            ),
            "proposed_priority": (
                self.proposed_priority.serialize()
                if self.proposed_priority is not None
                else None
            ),
            "proposed_success_criteria": [
                c.serialize() for c in self.proposed_success_criteria
            ],
            "proposed_constraints": [c.serialize() for c in self.proposed_constraints],
            "proposed_deadline": (
                self.proposed_deadline.isoformat()
                if self.proposed_deadline is not None
                else None
            ),
            "proposed_owner_actor_id": self.proposed_owner_actor_id,
            "proposed_autonomy_level": self.proposed_autonomy_level,
            "proposed_sensitivity": self.proposed_sensitivity,
            "proposed_permissions": list(self.proposed_permissions),
            "proposed_dependencies": [
                d.serialize() for d in self.proposed_dependencies
            ],
            "ambiguities": [a.serialize() for a in self.ambiguities],
            "information_gaps": [g.serialize() for g in self.information_gaps],
            "requires_confirmation": self.requires_confirmation,
            "confidence": self.confidence,
            "status": (
                self.status.value
                if isinstance(self.status, GoalProposalStatus)
                else self.status
            ),
            "created_at": self.created_at.isoformat(),
            "metadata": dict(self.metadata),
        }

    def to_dict(self) -> dict[str, Any]:
        return self.serialize()

    @classmethod
    def from_mapping(cls, mapping: Mapping[str, Any]) -> GoalProposal:
        if not isinstance(mapping, Mapping):
            raise InvalidGoalProposalError("mapping must be a Mapping instance")

        required_keys = {
            "id",
            "source",
            "raw_objective",
            "normalized_title",
            "normalized_description",
            "proposed_kind",
        }
        missing = required_keys - set(mapping.keys())
        if missing:
            raise InvalidGoalProposalError(
                f"Missing required fields in mapping: {sorted(missing)}"
            )

        p_priority = None
        if mapping.get("proposed_priority") is not None:
            p_priority = GoalPriority.from_dict(mapping["proposed_priority"])

        p_criteria = tuple(
            SuccessCriterion.from_dict(c)
            for c in mapping.get("proposed_success_criteria", ())
        )
        p_constraints = tuple(
            GoalConstraint.from_dict(c) for c in mapping.get("proposed_constraints", ())
        )
        p_dependencies = tuple(
            GoalDependency.from_dict(d)
            for d in mapping.get("proposed_dependencies", ())
        )
        ambiguities = tuple(
            GoalAmbiguity.from_dict(a) for a in mapping.get("ambiguities", ())
        )
        info_gaps = tuple(
            GoalInformationGap.from_dict(g) for g in mapping.get("information_gaps", ())
        )

        p_deadline = None
        if mapping.get("proposed_deadline") is not None:
            p_deadline = _parse_datetime(
                mapping["proposed_deadline"], "proposed_deadline"
            )

        return cls(
            id=str(mapping["id"]),
            source=mapping["source"],
            raw_objective=str(mapping["raw_objective"]),
            normalized_title=str(mapping["normalized_title"]),
            normalized_description=str(mapping["normalized_description"]),
            proposed_kind=mapping["proposed_kind"],
            proposed_priority=p_priority,
            proposed_success_criteria=p_criteria,
            proposed_constraints=p_constraints,
            proposed_deadline=p_deadline,
            proposed_owner_actor_id=str(
                mapping.get("proposed_owner_actor_id", "actor-user")
            ),
            proposed_autonomy_level=int(mapping.get("proposed_autonomy_level", 1)),
            proposed_sensitivity=str(mapping.get("proposed_sensitivity", "internal")),
            proposed_permissions=tuple(mapping.get("proposed_permissions", ())),
            proposed_dependencies=p_dependencies,
            ambiguities=ambiguities,
            information_gaps=info_gaps,
            requires_confirmation=bool(mapping.get("requires_confirmation", False)),
            confidence=float(mapping.get("confidence", 1.0)),
            status=mapping.get("status", GoalProposalStatus.CREATED),
            created_at=_parse_datetime(
                mapping.get("created_at", datetime.now(timezone.utc)), "created_at"
            ),
            metadata=mapping.get("metadata", {}),
        )

    @classmethod
    def from_dict(cls, mapping: Mapping[str, Any]) -> GoalProposal:
        return cls.from_mapping(mapping)


@dataclass(frozen=True, slots=True)
class GoalNormalizationRequest:
    """Request DTO containing raw objective and input parameters for normalization."""

    raw_objective: str
    source: GoalSource | str = GoalSource.USER_MESSAGE
    actor_id: str = "actor-user"
    context: MappingProxyType[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )
    kind_hint: GoalKind | str | None = None
    explicit_priority: GoalPriority | float | int | None = None
    explicit_deadline: datetime | None = None
    constraints: tuple[GoalConstraint, ...] = ()
    permissions: tuple[str, ...] = ()
    sensitivity: str = "internal"
    requested_autonomy_level: int = 1
    parent_goal_id: str | None = None
    metadata: MappingProxyType[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )

    def __post_init__(self) -> None:
        if not isinstance(self.raw_objective, str) or not self.raw_objective.strip():
            raise GoalNormalizationError("raw_objective cannot be empty or whitespace")
        _validate_non_empty_str(self.actor_id, "actor_id")

        if isinstance(self.source, str):
            try:
                object.__setattr__(self, "source", GoalSource(self.source))
            except ValueError as exc:
                raise InvalidGoalProposalError(
                    f"Invalid GoalSource string: {self.source!r}"
                ) from exc
        elif not isinstance(self.source, GoalSource):
            raise InvalidGoalProposalError(
                "source must be a GoalSource or valid string"
            )

        if self.kind_hint is not None:
            if isinstance(self.kind_hint, str):
                try:
                    object.__setattr__(self, "kind_hint", GoalKind(self.kind_hint))
                except ValueError as exc:
                    raise InvalidGoalProposalError(
                        f"Invalid GoalKind string for kind_hint: {self.kind_hint!r}"
                    ) from exc
            elif not isinstance(self.kind_hint, GoalKind):
                raise InvalidGoalProposalError(
                    "kind_hint must be a GoalKind, valid string, or None"
                )

        if not isinstance(self.requested_autonomy_level, int) or isinstance(
            self.requested_autonomy_level, bool
        ):
            raise InvalidGoalProposalError(
                "requested_autonomy_level must be an integer (>= 0)"
            )
        if self.requested_autonomy_level < 0:
            raise InvalidGoalProposalError(
                f"requested_autonomy_level cannot be negative, got {self.requested_autonomy_level}"
            )

        if self.explicit_deadline is not None:
            object.__setattr__(
                self,
                "explicit_deadline",
                _parse_datetime(self.explicit_deadline, "explicit_deadline"),
            )

        object.__setattr__(self, "context", _freeze_metadata(self.context))
        object.__setattr__(
            self,
            "constraints",
            tuple(self.constraints),
        )
        for c in self.constraints:
            if not isinstance(c, GoalConstraint):
                raise InvalidGoalProposalError(
                    "All items in constraints must be GoalConstraint instances"
                )

        object.__setattr__(
            self,
            "permissions",
            _freeze_str_tuple(self.permissions, "permissions"),
        )
        object.__setattr__(self, "metadata", _freeze_metadata(self.metadata))

    def serialize(self) -> dict[str, Any]:
        exp_p = None
        if isinstance(self.explicit_priority, GoalPriority):
            exp_p = self.explicit_priority.serialize()
        elif isinstance(self.explicit_priority, (int, float)):
            exp_p = float(self.explicit_priority)

        return {
            "raw_objective": self.raw_objective,
            "source": self.source.value
            if isinstance(self.source, GoalSource)
            else self.source,
            "actor_id": self.actor_id,
            "context": dict(self.context),
            "kind_hint": (
                self.kind_hint.value
                if isinstance(self.kind_hint, GoalKind)
                else self.kind_hint
            ),
            "explicit_priority": exp_p,
            "explicit_deadline": (
                self.explicit_deadline.isoformat()
                if self.explicit_deadline is not None
                else None
            ),
            "constraints": [c.serialize() for c in self.constraints],
            "permissions": list(self.permissions),
            "sensitivity": self.sensitivity,
            "requested_autonomy_level": self.requested_autonomy_level,
            "parent_goal_id": self.parent_goal_id,
            "metadata": dict(self.metadata),
        }

    def to_dict(self) -> dict[str, Any]:
        return self.serialize()

    @classmethod
    def from_mapping(cls, mapping: Mapping[str, Any]) -> GoalNormalizationRequest:
        if not isinstance(mapping, Mapping):
            raise InvalidGoalProposalError("mapping must be a Mapping instance")

        required_keys = {"raw_objective"}
        missing = required_keys - set(mapping.keys())
        if missing:
            raise InvalidGoalProposalError(
                f"Missing required fields in mapping: {sorted(missing)}"
            )

        exp_p = mapping.get("explicit_priority")
        if isinstance(exp_p, dict):
            exp_p = GoalPriority.from_dict(exp_p)

        constraints = tuple(
            GoalConstraint.from_dict(c) for c in mapping.get("constraints", ())
        )
        exp_dl = None
        if mapping.get("explicit_deadline") is not None:
            exp_dl = _parse_datetime(mapping["explicit_deadline"], "explicit_deadline")

        return cls(
            raw_objective=str(mapping["raw_objective"]),
            source=mapping.get("source", GoalSource.USER_MESSAGE),
            actor_id=str(mapping.get("actor_id", "actor-user")),
            context=mapping.get("context", {}),
            kind_hint=mapping.get("kind_hint"),
            explicit_priority=exp_p,
            explicit_deadline=exp_dl,
            constraints=constraints,
            permissions=tuple(mapping.get("permissions", ())),
            sensitivity=str(mapping.get("sensitivity", "internal")),
            requested_autonomy_level=int(mapping.get("requested_autonomy_level", 1)),
            parent_goal_id=mapping.get("parent_goal_id"),
            metadata=mapping.get("metadata", {}),
        )

    @classmethod
    def from_dict(cls, mapping: Mapping[str, Any]) -> GoalNormalizationRequest:
        return cls.from_mapping(mapping)


@dataclass(frozen=True, slots=True)
class GoalIntakeDecision:
    """Recorded intake decision statement."""

    decision_type: GoalIntakeDecisionType | str
    reason: str
    target_proposal_id: str = ""
    target_goal_id: str = ""
    candidate_goal_ids: tuple[str, ...] = ()
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: MappingProxyType[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )

    def __post_init__(self) -> None:
        _validate_non_empty_str(self.reason, "reason")

        if isinstance(self.decision_type, str):
            try:
                object.__setattr__(
                    self, "decision_type", GoalIntakeDecisionType(self.decision_type)
                )
            except ValueError as exc:
                raise InvalidGoalProposalError(
                    f"Invalid GoalIntakeDecisionType string: {self.decision_type!r}"
                ) from exc
        elif not isinstance(self.decision_type, GoalIntakeDecisionType):
            raise InvalidGoalProposalError(
                "decision_type must be a GoalIntakeDecisionType or valid string"
            )

        object.__setattr__(
            self,
            "candidate_goal_ids",
            _freeze_str_tuple(self.candidate_goal_ids, "candidate_goal_ids"),
        )
        object.__setattr__(
            self, "created_at", _parse_datetime(self.created_at, "created_at")
        )
        object.__setattr__(self, "metadata", _freeze_metadata(self.metadata))

    def serialize(self) -> dict[str, Any]:
        return {
            "decision_type": (
                self.decision_type.value
                if isinstance(self.decision_type, GoalIntakeDecisionType)
                else self.decision_type
            ),
            "reason": self.reason,
            "target_proposal_id": self.target_proposal_id,
            "target_goal_id": self.target_goal_id,
            "candidate_goal_ids": list(self.candidate_goal_ids),
            "created_at": self.created_at.isoformat(),
            "metadata": dict(self.metadata),
        }

    def to_dict(self) -> dict[str, Any]:
        return self.serialize()

    @classmethod
    def from_mapping(cls, mapping: Mapping[str, Any]) -> GoalIntakeDecision:
        if not isinstance(mapping, Mapping):
            raise InvalidGoalProposalError("mapping must be a Mapping instance")

        required_keys = {"decision_type", "reason"}
        missing = required_keys - set(mapping.keys())
        if missing:
            raise InvalidGoalProposalError(
                f"Missing required fields in mapping: {sorted(missing)}"
            )

        return cls(
            decision_type=mapping["decision_type"],
            reason=str(mapping["reason"]),
            target_proposal_id=str(mapping.get("target_proposal_id", "")),
            target_goal_id=str(mapping.get("target_goal_id", "")),
            candidate_goal_ids=tuple(mapping.get("candidate_goal_ids", ())),
            created_at=_parse_datetime(
                mapping.get("created_at", datetime.now(timezone.utc)), "created_at"
            ),
            metadata=mapping.get("metadata", {}),
        )

    @classmethod
    def from_dict(cls, mapping: Mapping[str, Any]) -> GoalIntakeDecision:
        return cls.from_mapping(mapping)


@dataclass(frozen=True, slots=True)
class GoalNormalizationResult:
    """Output DTO resulting from goal normalization."""

    proposal: GoalProposal
    status: GoalProposalStatus | str
    decisions: tuple[GoalIntakeDecision, ...] = ()
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()
    confidence: float = 1.0
    metadata: MappingProxyType[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )

    def __post_init__(self) -> None:
        if not isinstance(self.proposal, GoalProposal):
            raise InvalidGoalProposalError("proposal must be a GoalProposal instance")

        if isinstance(self.status, str):
            try:
                object.__setattr__(self, "status", GoalProposalStatus(self.status))
            except ValueError as exc:
                raise InvalidGoalProposalError(
                    f"Invalid GoalProposalStatus string: {self.status!r}"
                ) from exc
        elif not isinstance(self.status, GoalProposalStatus):
            raise InvalidGoalProposalError(
                "status must be a GoalProposalStatus or valid string"
            )

        object.__setattr__(
            self,
            "confidence",
            _validate_score_range(
                self.confidence, "confidence", min_val=0.0, max_val=1.0
            ),
        )

        object.__setattr__(self, "decisions", tuple(self.decisions))
        for d in self.decisions:
            if not isinstance(d, GoalIntakeDecision):
                raise InvalidGoalProposalError(
                    "All items in decisions must be GoalIntakeDecision instances"
                )

        object.__setattr__(
            self, "warnings", _freeze_str_tuple(self.warnings, "warnings")
        )
        object.__setattr__(self, "errors", _freeze_str_tuple(self.errors, "errors"))
        object.__setattr__(self, "metadata", _freeze_metadata(self.metadata))

    def serialize(self) -> dict[str, Any]:
        return {
            "proposal": self.proposal.serialize(),
            "status": (
                self.status.value
                if isinstance(self.status, GoalProposalStatus)
                else self.status
            ),
            "decisions": [d.serialize() for d in self.decisions],
            "warnings": list(self.warnings),
            "errors": list(self.errors),
            "confidence": self.confidence,
            "metadata": dict(self.metadata),
        }

    def to_dict(self) -> dict[str, Any]:
        return self.serialize()

    @classmethod
    def from_mapping(cls, mapping: Mapping[str, Any]) -> GoalNormalizationResult:
        if not isinstance(mapping, Mapping):
            raise InvalidGoalProposalError("mapping must be a Mapping instance")

        required_keys = {"proposal", "status"}
        missing = required_keys - set(mapping.keys())
        if missing:
            raise InvalidGoalProposalError(
                f"Missing required fields in mapping: {sorted(missing)}"
            )

        proposal = GoalProposal.from_dict(mapping["proposal"])
        decisions = tuple(
            GoalIntakeDecision.from_dict(d) for d in mapping.get("decisions", ())
        )

        return cls(
            proposal=proposal,
            status=mapping["status"],
            decisions=decisions,
            warnings=tuple(mapping.get("warnings", ())),
            errors=tuple(mapping.get("errors", ())),
            confidence=float(mapping.get("confidence", 1.0)),
            metadata=mapping.get("metadata", {}),
        )

    @classmethod
    def from_dict(cls, mapping: Mapping[str, Any]) -> GoalNormalizationResult:
        return cls.from_mapping(mapping)


@dataclass(frozen=True, slots=True)
class GoalProposalQuery:
    """Query object for searching GoalProposals in repository."""

    status: GoalProposalStatus | str | None = None
    source: GoalSource | str | None = None
    owner_actor_id: str | None = None
    requires_confirmation: bool | None = None
    parent_goal_id: str | None = None
