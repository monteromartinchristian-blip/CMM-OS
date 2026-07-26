"""Phase 9.17 – Outcome Evaluation Contracts.

Defines immutable, typed, serializable contracts for Outcome Evaluation,
Goal Completion Decisions, Criteria Results, Metrics, Regressions, Impact,
Knowledge Acquisition, State Snapshots, and User Confirmation Requirements.
"""

from __future__ import annotations

import hashlib
import json
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
    CriterionEvaluationStatus,
    CriterionImportance,
    GoalCompletionDecisionKind,
    Outcome,
    OutcomeEvaluationStatus,
    OutcomeReasonCode,
)
from cmm.agent_runtime.errors import (
    InvalidGoalContractError,
    OutcomeEvaluationContextError,
)


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


def _canonical_json(data: Any) -> str:
    """Serialize data structures to canonical JSON for hashing."""

    def default_serializer(obj: Any) -> Any:
        if isinstance(obj, datetime):
            return obj.isoformat()
        if hasattr(obj, "value"):
            return obj.value
        if hasattr(obj, "to_dict"):
            return obj.to_dict()
        if isinstance(obj, (set, tuple)):
            return list(obj)
        if isinstance(obj, MappingProxyType):
            return dict(obj)
        return str(obj)

    return json.dumps(data, default=default_serializer, sort_keys=True)


def compute_contract_fingerprint(*args: Any) -> str:
    """Compute a deterministic SHA-256 fingerprint from arbitrary payload elements."""
    raw = ":".join(_canonical_json(arg) for arg in args)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class OutcomeEvidence:
    """Immutable evidence artifact supporting an evaluation result."""

    evidence_id: str
    source: str
    description: str
    data: Mapping[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.evidence_id or not isinstance(self.evidence_id, str):
            raise InvalidGoalContractError("evidence_id must be a non-empty string")
        if not self.source or not isinstance(self.source, str):
            raise InvalidGoalContractError("source must be a non-empty string")
        object.__setattr__(
            self, "timestamp", _ensure_tz_aware(self.timestamp, "timestamp")
        )
        object.__setattr__(self, "data", _freeze_metadata(dict(self.data)))
        object.__setattr__(self, "metadata", _freeze_metadata(dict(self.metadata)))

    def to_dict(self) -> dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "source": self.source,
            "description": self.description,
            "data": dict(self.data),
            "timestamp": self.timestamp.isoformat(),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> OutcomeEvidence:
        return cls(
            evidence_id=data["evidence_id"],
            source=data["source"],
            description=data["description"],
            data=data.get("data", {}),
            timestamp=_parse_datetime(data["timestamp"], "timestamp"),
            metadata=data.get("metadata", {}),
        )


@dataclass(frozen=True)
class OutcomeMetricResult:
    """Evaluation result for a specific numeric or categorical metric."""

    metric_id: str
    name: str
    expected: Any
    actual: Any
    comparator: str
    status: CriterionEvaluationStatus
    deviation: float | None = None
    confidence: float = 1.0
    evidence_ids: tuple[str, ...] = field(default_factory=tuple)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.metric_id or not isinstance(self.metric_id, str):
            raise InvalidGoalContractError("metric_id must be a non-empty string")
        if not (0.0 <= self.confidence <= 1.0):
            raise InvalidGoalContractError("confidence must be between 0.0 and 1.0")
        object.__setattr__(self, "status", CriterionEvaluationStatus(self.status))
        object.__setattr__(
            self, "evidence_ids", _freeze_str_tuple(self.evidence_ids, "evidence_ids")
        )
        object.__setattr__(self, "metadata", _freeze_metadata(dict(self.metadata)))

    def to_dict(self) -> dict[str, Any]:
        return {
            "metric_id": self.metric_id,
            "name": self.name,
            "expected": self.expected,
            "actual": self.actual,
            "comparator": self.comparator,
            "status": self.status.value,
            "deviation": self.deviation,
            "confidence": self.confidence,
            "evidence_ids": list(self.evidence_ids),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> OutcomeMetricResult:
        return cls(
            metric_id=data["metric_id"],
            name=data["name"],
            expected=data.get("expected"),
            actual=data.get("actual"),
            comparator=data["comparator"],
            status=CriterionEvaluationStatus(data["status"]),
            deviation=data.get("deviation"),
            confidence=float(data.get("confidence", 1.0)),
            evidence_ids=tuple(data.get("evidence_ids", [])),
            metadata=data.get("metadata", {}),
        )


@dataclass(frozen=True)
class OutcomeSideEffect:
    """Recorded side effect resulting from operation execution."""

    side_effect_id: str
    description: str
    expected: bool
    reversible: bool
    authorized: bool
    affected_resources: tuple[str, ...] = field(default_factory=tuple)
    evidence_ids: tuple[str, ...] = field(default_factory=tuple)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.side_effect_id or not isinstance(self.side_effect_id, str):
            raise InvalidGoalContractError("side_effect_id must be a non-empty string")
        object.__setattr__(
            self,
            "affected_resources",
            _freeze_str_tuple(self.affected_resources, "affected_resources"),
        )
        object.__setattr__(
            self, "evidence_ids", _freeze_str_tuple(self.evidence_ids, "evidence_ids")
        )
        object.__setattr__(self, "metadata", _freeze_metadata(dict(self.metadata)))

    def to_dict(self) -> dict[str, Any]:
        return {
            "side_effect_id": self.side_effect_id,
            "description": self.description,
            "expected": self.expected,
            "reversible": self.reversible,
            "authorized": self.authorized,
            "affected_resources": list(self.affected_resources),
            "evidence_ids": list(self.evidence_ids),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> OutcomeSideEffect:
        return cls(
            side_effect_id=data["side_effect_id"],
            description=data["description"],
            expected=bool(data["expected"]),
            reversible=bool(data["reversible"]),
            authorized=bool(data["authorized"]),
            affected_resources=tuple(data.get("affected_resources", [])),
            evidence_ids=tuple(data.get("evidence_ids", [])),
            metadata=data.get("metadata", {}),
        )


@dataclass(frozen=True)
class OutcomeRegression:
    """Detected regression comparing pre- and post-execution state."""

    regression_id: str
    category: str
    severity: str
    previous_value: Any
    current_value: Any
    evidence_ids: tuple[str, ...] = field(default_factory=tuple)
    affected_resources: tuple[str, ...] = field(default_factory=tuple)
    reversible: bool = True
    rollback_recommended: bool = False
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.regression_id or not isinstance(self.regression_id, str):
            raise InvalidGoalContractError("regression_id must be a non-empty string")
        if self.severity not in ("low", "medium", "high", "critical"):
            raise InvalidGoalContractError(f"Invalid severity level: {self.severity}")
        object.__setattr__(
            self, "evidence_ids", _freeze_str_tuple(self.evidence_ids, "evidence_ids")
        )
        object.__setattr__(
            self,
            "affected_resources",
            _freeze_str_tuple(self.affected_resources, "affected_resources"),
        )
        object.__setattr__(self, "metadata", _freeze_metadata(dict(self.metadata)))

    def to_dict(self) -> dict[str, Any]:
        return {
            "regression_id": self.regression_id,
            "category": self.category,
            "severity": self.severity,
            "previous_value": self.previous_value,
            "current_value": self.current_value,
            "evidence_ids": list(self.evidence_ids),
            "affected_resources": list(self.affected_resources),
            "reversible": self.reversible,
            "rollback_recommended": self.rollback_recommended,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> OutcomeRegression:
        return cls(
            regression_id=data["regression_id"],
            category=data["category"],
            severity=data["severity"],
            previous_value=data.get("previous_value"),
            current_value=data.get("current_value"),
            evidence_ids=tuple(data.get("evidence_ids", [])),
            affected_resources=tuple(data.get("affected_resources", [])),
            reversible=bool(data.get("reversible", True)),
            rollback_recommended=bool(data.get("rollback_recommended", False)),
            metadata=data.get("metadata", {}),
        )


@dataclass(frozen=True)
class OutcomeGeneratedDebt:
    """Recorded technical, operational, or validation debt generated during execution."""

    debt_id: str
    category: str
    description: str
    severity: str = "medium"
    accepted: bool = False
    mitigation_plan: str | None = None
    linked_artifacts: tuple[str, ...] = field(default_factory=tuple)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.debt_id or not isinstance(self.debt_id, str):
            raise InvalidGoalContractError("debt_id must be a non-empty string")
        if self.severity not in ("low", "medium", "high", "critical"):
            raise InvalidGoalContractError(f"Invalid severity level: {self.severity}")
        object.__setattr__(
            self,
            "linked_artifacts",
            _freeze_str_tuple(self.linked_artifacts, "linked_artifacts"),
        )
        object.__setattr__(self, "metadata", _freeze_metadata(dict(self.metadata)))

    def to_dict(self) -> dict[str, Any]:
        return {
            "debt_id": self.debt_id,
            "category": self.category,
            "description": self.description,
            "severity": self.severity,
            "accepted": self.accepted,
            "mitigation_plan": self.mitigation_plan,
            "linked_artifacts": list(self.linked_artifacts),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> OutcomeGeneratedDebt:
        return cls(
            debt_id=data["debt_id"],
            category=data["category"],
            description=data["description"],
            severity=data.get("severity", "medium"),
            accepted=bool(data.get("accepted", False)),
            mitigation_plan=data.get("mitigation_plan"),
            linked_artifacts=tuple(data.get("linked_artifacts", [])),
            metadata=data.get("metadata", {}),
        )


@dataclass(frozen=True)
class OutcomeKnowledgeAcquisition:
    """Acquired fact, inference, or invalidated knowledge during goal execution."""

    knowledge_id: str
    kind: str
    statement: str
    confidence: float = 1.0
    evidence_ids: tuple[str, ...] = field(default_factory=tuple)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.knowledge_id or not isinstance(self.knowledge_id, str):
            raise InvalidGoalContractError("knowledge_id must be a non-empty string")
        if not (0.0 <= self.confidence <= 1.0):
            raise InvalidGoalContractError("confidence must be between 0.0 and 1.0")
        object.__setattr__(
            self, "evidence_ids", _freeze_str_tuple(self.evidence_ids, "evidence_ids")
        )
        object.__setattr__(self, "metadata", _freeze_metadata(dict(self.metadata)))

    def to_dict(self) -> dict[str, Any]:
        return {
            "knowledge_id": self.knowledge_id,
            "kind": self.kind,
            "statement": self.statement,
            "confidence": self.confidence,
            "evidence_ids": list(self.evidence_ids),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> OutcomeKnowledgeAcquisition:
        return cls(
            knowledge_id=data["knowledge_id"],
            kind=data["kind"],
            statement=data["statement"],
            confidence=float(data.get("confidence", 1.0)),
            evidence_ids=tuple(data.get("evidence_ids", [])),
            metadata=data.get("metadata", {}),
        )


@dataclass(frozen=True)
class OutcomeGap:
    """Identified information or operational gap remaining after execution."""

    gap_id: str
    description: str
    impact: str = "medium"
    resolved: bool = False
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.gap_id or not isinstance(self.gap_id, str):
            raise InvalidGoalContractError("gap_id must be a non-empty string")
        object.__setattr__(self, "metadata", _freeze_metadata(dict(self.metadata)))

    def to_dict(self) -> dict[str, Any]:
        return {
            "gap_id": self.gap_id,
            "description": self.description,
            "impact": self.impact,
            "resolved": self.resolved,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> OutcomeGap:
        return cls(
            gap_id=data["gap_id"],
            description=data["description"],
            impact=data.get("impact", "medium"),
            resolved=bool(data.get("resolved", False)),
            metadata=data.get("metadata", {}),
        )


@dataclass(frozen=True)
class OutcomeTaskStatus:
    """Status of a task associated with the goal scope."""

    task_id: str
    description: str
    completed: bool
    blocking: bool = False
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.task_id or not isinstance(self.task_id, str):
            raise InvalidGoalContractError("task_id must be a non-empty string")
        object.__setattr__(self, "metadata", _freeze_metadata(dict(self.metadata)))

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "description": self.description,
            "completed": self.completed,
            "blocking": self.blocking,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> OutcomeTaskStatus:
        return cls(
            task_id=data["task_id"],
            description=data["description"],
            completed=bool(data["completed"]),
            blocking=bool(data.get("blocking", False)),
            metadata=data.get("metadata", {}),
        )


@dataclass(frozen=True)
class OutcomeCriterionResult:
    """Evaluated result for a single SuccessCriterion."""

    criterion_id: str
    status: CriterionEvaluationStatus
    importance: CriterionImportance
    expected_value: Any = None
    actual_value: Any = None
    evidence_ids: tuple[str, ...] = field(default_factory=tuple)
    validation_result_ids: tuple[str, ...] = field(default_factory=tuple)
    reason_codes: tuple[OutcomeReasonCode, ...] = field(default_factory=tuple)
    confidence: float = 1.0
    warnings: tuple[str, ...] = field(default_factory=tuple)
    blocking: bool = False
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.criterion_id or not isinstance(self.criterion_id, str):
            raise InvalidGoalContractError("criterion_id must be a non-empty string")
        if not (0.0 <= self.confidence <= 1.0):
            raise InvalidGoalContractError("confidence must be between 0.0 and 1.0")
        object.__setattr__(self, "status", CriterionEvaluationStatus(self.status))
        object.__setattr__(self, "importance", CriterionImportance(self.importance))
        object.__setattr__(
            self, "evidence_ids", _freeze_str_tuple(self.evidence_ids, "evidence_ids")
        )
        object.__setattr__(
            self,
            "validation_result_ids",
            _freeze_str_tuple(self.validation_result_ids, "validation_result_ids"),
        )
        object.__setattr__(
            self,
            "reason_codes",
            tuple(OutcomeReasonCode(code) for code in self.reason_codes),
        )
        object.__setattr__(
            self, "warnings", _freeze_str_tuple(self.warnings, "warnings")
        )
        object.__setattr__(self, "metadata", _freeze_metadata(dict(self.metadata)))

    def to_dict(self) -> dict[str, Any]:
        return {
            "criterion_id": self.criterion_id,
            "status": self.status.value,
            "importance": self.importance.value,
            "expected_value": self.expected_value,
            "actual_value": self.actual_value,
            "evidence_ids": list(self.evidence_ids),
            "validation_result_ids": list(self.validation_result_ids),
            "reason_codes": [rc.value for rc in self.reason_codes],
            "confidence": self.confidence,
            "warnings": list(self.warnings),
            "blocking": self.blocking,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> OutcomeCriterionResult:
        return cls(
            criterion_id=data["criterion_id"],
            status=CriterionEvaluationStatus(data["status"]),
            importance=CriterionImportance(data["importance"]),
            expected_value=data.get("expected_value"),
            actual_value=data.get("actual_value"),
            evidence_ids=tuple(data.get("evidence_ids", [])),
            validation_result_ids=tuple(data.get("validation_result_ids", [])),
            reason_codes=tuple(
                OutcomeReasonCode(c) for c in data.get("reason_codes", [])
            ),
            confidence=float(data.get("confidence", 1.0)),
            warnings=tuple(data.get("warnings", [])),
            blocking=bool(data.get("blocking", False)),
            metadata=data.get("metadata", {}),
        )


@dataclass(frozen=True)
class OutcomeRiskAssessment:
    """Evaluated risk level associated with outcome."""

    risk_id: str
    category: str
    level: str
    description: str
    acceptable: bool = True
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.risk_id or not isinstance(self.risk_id, str):
            raise InvalidGoalContractError("risk_id must be a non-empty string")
        if self.level not in ("low", "medium", "high", "critical"):
            raise InvalidGoalContractError(f"Invalid risk level: {self.level}")
        object.__setattr__(self, "metadata", _freeze_metadata(dict(self.metadata)))

    def to_dict(self) -> dict[str, Any]:
        return {
            "risk_id": self.risk_id,
            "category": self.category,
            "level": self.level,
            "description": self.description,
            "acceptable": self.acceptable,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> OutcomeRiskAssessment:
        return cls(
            risk_id=data["risk_id"],
            category=data["category"],
            level=data["level"],
            description=data["description"],
            acceptable=bool(data.get("acceptable", True)),
            metadata=data.get("metadata", {}),
        )


@dataclass(frozen=True)
class OutcomeStateSnapshot:
    """Immutable state snapshot for resources and versions."""

    snapshot_id: str
    resources: Mapping[str, Any] = field(default_factory=dict)
    versions: Mapping[str, str] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.snapshot_id or not isinstance(self.snapshot_id, str):
            raise InvalidGoalContractError("snapshot_id must be a non-empty string")
        object.__setattr__(
            self, "timestamp", _ensure_tz_aware(self.timestamp, "timestamp")
        )
        object.__setattr__(self, "resources", _freeze_metadata(dict(self.resources)))
        object.__setattr__(self, "versions", _freeze_metadata(dict(self.versions)))
        object.__setattr__(self, "metadata", _freeze_metadata(dict(self.metadata)))

    def to_dict(self) -> dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "resources": dict(self.resources),
            "versions": dict(self.versions),
            "timestamp": self.timestamp.isoformat(),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> OutcomeStateSnapshot:
        return cls(
            snapshot_id=data["snapshot_id"],
            resources=data.get("resources", {}),
            versions=data.get("versions", {}),
            timestamp=_parse_datetime(data["timestamp"], "timestamp"),
            metadata=data.get("metadata", {}),
        )


@dataclass(frozen=True)
class OutcomeUserConfirmationRequirement:
    """Structured human confirmation requirement for completion."""

    confirmation_id: str
    reason: str
    status: str = "pending"  # pending, confirmed, rejected, expired
    confirmed_by: str | None = None
    confirmed_at: datetime | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.confirmation_id or not isinstance(self.confirmation_id, str):
            raise InvalidGoalContractError("confirmation_id must be a non-empty string")
        if self.status not in ("pending", "confirmed", "rejected", "expired"):
            raise InvalidGoalContractError(
                f"Invalid confirmation status: {self.status}"
            )
        if self.confirmed_at is not None:
            object.__setattr__(
                self,
                "confirmed_at",
                _ensure_tz_aware(self.confirmed_at, "confirmed_at"),
            )
        object.__setattr__(self, "metadata", _freeze_metadata(dict(self.metadata)))

    def to_dict(self) -> dict[str, Any]:
        return {
            "confirmation_id": self.confirmation_id,
            "reason": self.reason,
            "status": self.status,
            "confirmed_by": self.confirmed_by,
            "confirmed_at": self.confirmed_at.isoformat()
            if self.confirmed_at
            else None,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> OutcomeUserConfirmationRequirement:
        return cls(
            confirmation_id=data["confirmation_id"],
            reason=data["reason"],
            status=data.get("status", "pending"),
            confirmed_by=data.get("confirmed_by"),
            confirmed_at=_parse_datetime(data["confirmed_at"], "confirmed_at")
            if data.get("confirmed_at")
            else None,
            metadata=data.get("metadata", {}),
        )


@dataclass(frozen=True)
class OutcomeEvaluation:
    """Comprehensive evaluation record determining if an outcome satisfies a Goal."""

    outcome_evaluation_id: str
    goal_id: str
    agent_run_id: str
    workflow_id: str
    iteration_id: str
    status: OutcomeEvaluationStatus
    outcome: Outcome
    criterion_results: tuple[OutcomeCriterionResult, ...] = field(default_factory=tuple)
    expected_state: OutcomeStateSnapshot | Mapping[str, Any] = field(
        default_factory=dict
    )
    actual_state: OutcomeStateSnapshot | Mapping[str, Any] = field(default_factory=dict)
    validation_result_ids: tuple[str, ...] = field(default_factory=tuple)
    evidence: tuple[OutcomeEvidence, ...] = field(default_factory=tuple)
    side_effects: tuple[OutcomeSideEffect, ...] = field(default_factory=tuple)
    regressions: tuple[OutcomeRegression, ...] = field(default_factory=tuple)
    generated_debt: tuple[OutcomeGeneratedDebt, ...] = field(default_factory=tuple)
    acquired_knowledge: tuple[OutcomeKnowledgeAcquisition, ...] = field(
        default_factory=tuple
    )
    remaining_gaps: tuple[OutcomeGap, ...] = field(default_factory=tuple)
    remaining_tasks: tuple[OutcomeTaskStatus, ...] = field(default_factory=tuple)
    risks: tuple[OutcomeRiskAssessment, ...] = field(default_factory=tuple)
    warnings: tuple[str, ...] = field(default_factory=tuple)
    confidence: float = 1.0
    recommended_decision: GoalCompletionDecisionKind = (
        GoalCompletionDecisionKind.CONTINUE
    )
    requires_user_confirmation: bool = False
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Mapping[str, Any] = field(default_factory=dict)
    fingerprint: str = ""

    def __post_init__(self) -> None:
        if not self.outcome_evaluation_id or not isinstance(
            self.outcome_evaluation_id, str
        ):
            raise InvalidGoalContractError(
                "outcome_evaluation_id must be a non-empty string"
            )
        if not self.goal_id or not isinstance(self.goal_id, str):
            raise InvalidGoalContractError("goal_id must be a non-empty string")
        if not (0.0 <= self.confidence <= 1.0):
            raise InvalidGoalContractError("confidence must be between 0.0 and 1.0")

        object.__setattr__(self, "status", OutcomeEvaluationStatus(self.status))
        object.__setattr__(self, "outcome", Outcome(self.outcome))
        object.__setattr__(
            self,
            "recommended_decision",
            GoalCompletionDecisionKind(self.recommended_decision),
        )
        object.__setattr__(
            self, "created_at", _ensure_tz_aware(self.created_at, "created_at")
        )
        object.__setattr__(
            self,
            "validation_result_ids",
            _freeze_str_tuple(self.validation_result_ids, "validation_result_ids"),
        )
        object.__setattr__(
            self, "warnings", _freeze_str_tuple(self.warnings, "warnings")
        )
        object.__setattr__(self, "metadata", _freeze_metadata(dict(self.metadata)))

        # Freeze mapping states if dicts provided
        if isinstance(self.expected_state, dict):
            object.__setattr__(
                self, "expected_state", _freeze_metadata(dict(self.expected_state))
            )
        if isinstance(self.actual_state, dict):
            object.__setattr__(
                self, "actual_state", _freeze_metadata(dict(self.actual_state))
            )

        # Compute deterministic fingerprint if empty
        if not self.fingerprint:
            computed_fp = compute_contract_fingerprint(
                self.outcome_evaluation_id,
                self.goal_id,
                self.agent_run_id,
                self.status.value,
                self.outcome.value,
                [cr.to_dict() for cr in self.criterion_results],
                self.recommended_decision.value,
                self.created_at.isoformat(),
            )
            object.__setattr__(self, "fingerprint", computed_fp)

    def to_dict(self) -> dict[str, Any]:
        exp_st = (
            self.expected_state.to_dict()
            if hasattr(self.expected_state, "to_dict")
            else dict(self.expected_state)
        )
        act_st = (
            self.actual_state.to_dict()
            if hasattr(self.actual_state, "to_dict")
            else dict(self.actual_state)
        )
        return {
            "outcome_evaluation_id": self.outcome_evaluation_id,
            "goal_id": self.goal_id,
            "agent_run_id": self.agent_run_id,
            "workflow_id": self.workflow_id,
            "iteration_id": self.iteration_id,
            "status": self.status.value,
            "outcome": self.outcome.value,
            "criterion_results": [cr.to_dict() for cr in self.criterion_results],
            "expected_state": exp_st,
            "actual_state": act_st,
            "validation_result_ids": list(self.validation_result_ids),
            "evidence": [ev.to_dict() for ev in self.evidence],
            "side_effects": [se.to_dict() for se in self.side_effects],
            "regressions": [rg.to_dict() for rg in self.regressions],
            "generated_debt": [gd.to_dict() for gd in self.generated_debt],
            "acquired_knowledge": [ak.to_dict() for ak in self.acquired_knowledge],
            "remaining_gaps": [rg.to_dict() for rg in self.remaining_gaps],
            "remaining_tasks": [rt.to_dict() for rt in self.remaining_tasks],
            "risks": [rk.to_dict() for rk in self.risks],
            "warnings": list(self.warnings),
            "confidence": self.confidence,
            "recommended_decision": self.recommended_decision.value,
            "requires_user_confirmation": self.requires_user_confirmation,
            "created_at": self.created_at.isoformat(),
            "metadata": dict(self.metadata),
            "fingerprint": self.fingerprint,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> OutcomeEvaluation:
        exp_st = (
            OutcomeStateSnapshot.from_dict(data["expected_state"])
            if "snapshot_id" in data.get("expected_state", {})
            else data.get("expected_state", {})
        )
        act_st = (
            OutcomeStateSnapshot.from_dict(data["actual_state"])
            if "snapshot_id" in data.get("actual_state", {})
            else data.get("actual_state", {})
        )
        return cls(
            outcome_evaluation_id=data["outcome_evaluation_id"],
            goal_id=data["goal_id"],
            agent_run_id=data["agent_run_id"],
            workflow_id=data["workflow_id"],
            iteration_id=data["iteration_id"],
            status=OutcomeEvaluationStatus(data["status"]),
            outcome=Outcome(data["outcome"]),
            criterion_results=tuple(
                OutcomeCriterionResult.from_dict(cr)
                for cr in data.get("criterion_results", [])
            ),
            expected_state=exp_st,
            actual_state=act_st,
            validation_result_ids=tuple(data.get("validation_result_ids", [])),
            evidence=tuple(
                OutcomeEvidence.from_dict(ev) for ev in data.get("evidence", [])
            ),
            side_effects=tuple(
                OutcomeSideEffect.from_dict(se) for se in data.get("side_effects", [])
            ),
            regressions=tuple(
                OutcomeRegression.from_dict(rg) for rg in data.get("regressions", [])
            ),
            generated_debt=tuple(
                OutcomeGeneratedDebt.from_dict(gd)
                for gd in data.get("generated_debt", [])
            ),
            acquired_knowledge=tuple(
                OutcomeKnowledgeAcquisition.from_dict(ak)
                for ak in data.get("acquired_knowledge", [])
            ),
            remaining_gaps=tuple(
                OutcomeGap.from_dict(rg) for rg in data.get("remaining_gaps", [])
            ),
            remaining_tasks=tuple(
                OutcomeTaskStatus.from_dict(rt)
                for rt in data.get("remaining_tasks", [])
            ),
            risks=tuple(
                OutcomeRiskAssessment.from_dict(rk) for rk in data.get("risks", [])
            ),
            warnings=tuple(data.get("warnings", [])),
            confidence=float(data.get("confidence", 1.0)),
            recommended_decision=GoalCompletionDecisionKind(
                data["recommended_decision"]
            ),
            requires_user_confirmation=bool(
                data.get("requires_user_confirmation", False)
            ),
            created_at=_parse_datetime(data["created_at"], "created_at"),
            metadata=data.get("metadata", {}),
            fingerprint=data.get("fingerprint", ""),
        )


@dataclass(frozen=True)
class GoalCompletionDecision:
    """Formal decision determining how to handle Goal completion/continuation."""

    completion_decision_id: str
    outcome_evaluation_id: str
    goal_id: str
    decision: GoalCompletionDecisionKind
    satisfied_criteria: tuple[str, ...] = field(default_factory=tuple)
    unsatisfied_criteria: tuple[str, ...] = field(default_factory=tuple)
    waived_criteria: tuple[str, ...] = field(default_factory=tuple)
    blocking_criteria: tuple[str, ...] = field(default_factory=tuple)
    evidence: tuple[OutcomeEvidence, ...] = field(default_factory=tuple)
    confidence: float = 1.0
    requires_user_confirmation: bool = False
    reason_codes: tuple[OutcomeReasonCode, ...] = field(default_factory=tuple)
    residual_risk: float = 0.0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Mapping[str, Any] = field(default_factory=dict)
    fingerprint: str = ""

    def __post_init__(self) -> None:
        if not self.completion_decision_id or not isinstance(
            self.completion_decision_id, str
        ):
            raise InvalidGoalContractError(
                "completion_decision_id must be a non-empty string"
            )
        if not self.outcome_evaluation_id or not isinstance(
            self.outcome_evaluation_id, str
        ):
            raise InvalidGoalContractError(
                "outcome_evaluation_id must be a non-empty string"
            )
        if not self.goal_id or not isinstance(self.goal_id, str):
            raise InvalidGoalContractError("goal_id must be a non-empty string")
        if not (0.0 <= self.confidence <= 1.0):
            raise InvalidGoalContractError("confidence must be between 0.0 and 1.0")
        if not (0.0 <= self.residual_risk <= 1.0):
            raise InvalidGoalContractError("residual_risk must be between 0.0 and 1.0")

        object.__setattr__(self, "decision", GoalCompletionDecisionKind(self.decision))
        object.__setattr__(
            self,
            "satisfied_criteria",
            _freeze_str_tuple(self.satisfied_criteria, "satisfied_criteria"),
        )
        object.__setattr__(
            self,
            "unsatisfied_criteria",
            _freeze_str_tuple(self.unsatisfied_criteria, "unsatisfied_criteria"),
        )
        object.__setattr__(
            self,
            "waived_criteria",
            _freeze_str_tuple(self.waived_criteria, "waived_criteria"),
        )
        object.__setattr__(
            self,
            "blocking_criteria",
            _freeze_str_tuple(self.blocking_criteria, "blocking_criteria"),
        )
        object.__setattr__(
            self,
            "reason_codes",
            tuple(OutcomeReasonCode(rc) for rc in self.reason_codes),
        )
        object.__setattr__(
            self, "created_at", _ensure_tz_aware(self.created_at, "created_at")
        )
        object.__setattr__(self, "metadata", _freeze_metadata(dict(self.metadata)))

        if not self.fingerprint:
            computed_fp = compute_contract_fingerprint(
                self.completion_decision_id,
                self.outcome_evaluation_id,
                self.goal_id,
                self.decision.value,
                list(self.satisfied_criteria),
                list(self.unsatisfied_criteria),
                [rc.value for rc in self.reason_codes],
                self.created_at.isoformat(),
            )
            object.__setattr__(self, "fingerprint", computed_fp)

    def to_dict(self) -> dict[str, Any]:
        return {
            "completion_decision_id": self.completion_decision_id,
            "outcome_evaluation_id": self.outcome_evaluation_id,
            "goal_id": self.goal_id,
            "decision": self.decision.value,
            "satisfied_criteria": list(self.satisfied_criteria),
            "unsatisfied_criteria": list(self.unsatisfied_criteria),
            "waived_criteria": list(self.waived_criteria),
            "blocking_criteria": list(self.blocking_criteria),
            "evidence": [ev.to_dict() for ev in self.evidence],
            "confidence": self.confidence,
            "requires_user_confirmation": self.requires_user_confirmation,
            "reason_codes": [rc.value for rc in self.reason_codes],
            "residual_risk": self.residual_risk,
            "created_at": self.created_at.isoformat(),
            "metadata": dict(self.metadata),
            "fingerprint": self.fingerprint,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GoalCompletionDecision:
        return cls(
            completion_decision_id=data["completion_decision_id"],
            outcome_evaluation_id=data["outcome_evaluation_id"],
            goal_id=data["goal_id"],
            decision=GoalCompletionDecisionKind(data["decision"]),
            satisfied_criteria=tuple(data.get("satisfied_criteria", [])),
            unsatisfied_criteria=tuple(data.get("unsatisfied_criteria", [])),
            waived_criteria=tuple(data.get("waived_criteria", [])),
            blocking_criteria=tuple(data.get("blocking_criteria", [])),
            evidence=tuple(
                OutcomeEvidence.from_dict(ev) for ev in data.get("evidence", [])
            ),
            confidence=float(data.get("confidence", 1.0)),
            requires_user_confirmation=bool(
                data.get("requires_user_confirmation", False)
            ),
            reason_codes=tuple(
                OutcomeReasonCode(rc) for rc in data.get("reason_codes", [])
            ),
            residual_risk=float(data.get("residual_risk", 0.0)),
            created_at=_parse_datetime(data["created_at"], "created_at"),
            metadata=data.get("metadata", {}),
            fingerprint=data.get("fingerprint", ""),
        )


@dataclass(frozen=True)
class OutcomeEvaluationRequest:
    """Request payload to perform an outcome evaluation."""

    goal_id: str
    agent_run_id: str
    workflow_id: str = ""
    iteration_id: str = ""
    expected_state: Mapping[str, Any] = field(default_factory=dict)
    actual_state: Mapping[str, Any] = field(default_factory=dict)
    previous_state: Mapping[str, Any] = field(default_factory=dict)
    operation_results: tuple[Any, ...] = field(default_factory=tuple)
    validations: tuple[Any, ...] = field(default_factory=tuple)
    metrics: tuple[Mapping[str, Any], ...] = field(default_factory=tuple)
    evidence: tuple[OutcomeEvidence, ...] = field(default_factory=tuple)
    user_confirmation: OutcomeUserConfirmationRequirement | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.goal_id or not isinstance(self.goal_id, str):
            raise InvalidGoalContractError("goal_id must be a non-empty string")
        if not self.agent_run_id or not isinstance(self.agent_run_id, str):
            raise InvalidGoalContractError("agent_run_id must be a non-empty string")
        object.__setattr__(
            self, "expected_state", _freeze_metadata(dict(self.expected_state))
        )
        object.__setattr__(
            self, "actual_state", _freeze_metadata(dict(self.actual_state))
        )
        object.__setattr__(
            self, "previous_state", _freeze_metadata(dict(self.previous_state))
        )
        object.__setattr__(self, "metadata", _freeze_metadata(dict(self.metadata)))


@dataclass(frozen=True)
class OutcomeEvaluationResult:
    """Aggregated result wrapper for evaluation and decision."""

    evaluation: OutcomeEvaluation
    decision: GoalCompletionDecision
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "metadata", _freeze_metadata(dict(self.metadata)))


@dataclass(frozen=True)
class OutcomeEvaluationContext:
    """Execution context for an outcome evaluation operation."""

    goal: Any
    request: OutcomeEvaluationRequest
    evaluation_id: str
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.goal is None:
            raise OutcomeEvaluationContextError("goal cannot be None")
        if not self.evaluation_id:
            raise OutcomeEvaluationContextError("evaluation_id cannot be empty")
        object.__setattr__(
            self, "created_at", _ensure_tz_aware(self.created_at, "created_at")
        )
        object.__setattr__(self, "metadata", _freeze_metadata(dict(self.metadata)))
