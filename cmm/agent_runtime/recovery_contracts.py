"""Phase 9.16 – Recovery Manager Contracts.

Defines immutable, serializable, and timezone-aware dataclasses for recovery contexts,
decisions, attempts, policies, constraints, results, evidence, and risk assessments.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from types import MappingProxyType
from typing import Any

from cmm.agent_runtime.enums import (
    BackoffStrategy,
    CheckpointStatus,
    EscalationTarget,
    RecoveryErrorClass,
    RecoveryReasonCode,
    RecoveryStatus,
    RecoveryStrategy,
)
from cmm.agent_runtime.errors import (
    RecoveryContextError,
    RecoveryDecisionError,
)


def _freeze_dict(d: Mapping[str, Any] | None) -> Mapping[str, Any]:
    if d is None:
        return MappingProxyType({})
    if isinstance(d, MappingProxyType):
        return d
    cleaned = {}
    for k, v in d.items():
        if isinstance(v, dict):
            cleaned[k] = _freeze_dict(v)
        elif isinstance(v, list):
            cleaned[k] = tuple(_freeze_dict(i) if isinstance(i, dict) else i for i in v)
        else:
            cleaned[k] = v
    return MappingProxyType(cleaned)


def _freeze_tuple(items: Any) -> tuple[Any, ...]:
    if items is None:
        return ()
    if isinstance(items, tuple):
        res = []
        for item in items:
            if isinstance(item, dict):
                res.append(_freeze_dict(item))
            elif isinstance(item, list):
                res.append(_freeze_tuple(item))
            else:
                res.append(item)
        return tuple(res)
    if isinstance(items, list):
        res = []
        for item in items:
            if isinstance(item, dict):
                res.append(_freeze_dict(item))
            elif isinstance(item, list):
                res.append(_freeze_tuple(item))
            else:
                res.append(item)
        return tuple(res)
    return (items,)


def _to_json_serializable(obj: Any) -> Any:
    if isinstance(obj, MappingProxyType):
        return {k: _to_json_serializable(v) for k, v in obj.items()}
    if isinstance(obj, (tuple, list)):
        return [_to_json_serializable(i) for i in obj]
    if isinstance(obj, dict):
        return {k: _to_json_serializable(v) for k, v in obj.items()}
    if hasattr(obj, "to_dict") and callable(obj.to_dict):
        return obj.to_dict()
    if hasattr(obj, "value"):
        return obj.value
    return obj


def compute_recovery_context_fingerprint(
    recovery_context_id: str,
    agent_run_id: str,
    goal_id: str,
    workflow_id: str,
    iteration_id: str,
    failed_task_id: str,
    failed_operation_id: str,
    error: Mapping[str, Any],
    created_at: str,
) -> str:
    """Compute a deterministic SHA-256 fingerprint for a RecoveryContext."""
    payload = {
        "recovery_context_id": recovery_context_id,
        "agent_run_id": agent_run_id,
        "goal_id": goal_id,
        "workflow_id": workflow_id,
        "iteration_id": iteration_id,
        "failed_task_id": failed_task_id,
        "failed_operation_id": failed_operation_id,
        "error": sorted(_to_json_serializable(error).items())
        if isinstance(error, (dict, MappingProxyType))
        else str(error),
        "created_at": created_at,
    }
    raw = json.dumps(payload, sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def compute_recovery_decision_fingerprint(
    recovery_decision_id: str,
    recovery_context_id: str,
    strategy: str,
    reason_codes: tuple[str, ...],
    idempotency_key: str,
    decided_at: str,
) -> str:
    """Compute a deterministic SHA-256 fingerprint for a RecoveryDecision."""
    payload = {
        "recovery_decision_id": recovery_decision_id,
        "recovery_context_id": recovery_context_id,
        "strategy": strategy,
        "reason_codes": sorted(reason_codes),
        "idempotency_key": idempotency_key,
        "decided_at": decided_at,
    }
    raw = json.dumps(payload, sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class RecoveryError:
    """Structured details of a failure encountered by the agent runtime."""

    error_type: str
    message: str
    error_class: RecoveryErrorClass = RecoveryErrorClass.UNKNOWN
    retryable: bool = False
    stack_trace: str | None = None
    details: Mapping[str, Any] = field(default_factory=dict)
    timestamp: str = ""

    def __post_init__(self) -> None:
        if not self.timestamp:
            object.__setattr__(
                self, "timestamp", datetime.now(timezone.utc).isoformat()
            )
        object.__setattr__(self, "details", _freeze_dict(self.details))

    def to_dict(self) -> dict[str, Any]:
        return {
            "error_type": self.error_type,
            "message": self.message,
            "error_class": self.error_class.value
            if isinstance(self.error_class, RecoveryErrorClass)
            else str(self.error_class),
            "retryable": self.retryable,
            "stack_trace": self.stack_trace,
            "details": _to_json_serializable(self.details),
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RecoveryError:
        err_class = data.get("error_class", RecoveryErrorClass.UNKNOWN)
        if isinstance(err_class, str):
            try:
                err_class = RecoveryErrorClass(err_class)
            except ValueError:
                err_class = RecoveryErrorClass.UNKNOWN
        return cls(
            error_type=data.get("error_type", "UnknownError"),
            message=data.get("message", ""),
            error_class=err_class,
            retryable=bool(data.get("retryable", False)),
            stack_trace=data.get("stack_trace"),
            details=data.get("details", {}),
            timestamp=data.get("timestamp", ""),
        )


@dataclass(frozen=True)
class RecoveryAttempt:
    """Represents an individual execution attempt of a recovery strategy."""

    attempt_index: int
    strategy: RecoveryStrategy
    started_at: str
    completed_at: str | None = None
    status: RecoveryStatus = RecoveryStatus.PENDING
    result_outcome: str | None = None
    error: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.attempt_index < 1:
            raise RecoveryContextError("attempt_index must be >= 1.")
        object.__setattr__(self, "metadata", _freeze_dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "attempt_index": self.attempt_index,
            "strategy": self.strategy.value
            if isinstance(self.strategy, RecoveryStrategy)
            else str(self.strategy),
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "status": self.status.value
            if isinstance(self.status, RecoveryStatus)
            else str(self.status),
            "result_outcome": self.result_outcome,
            "error": self.error,
            "metadata": _to_json_serializable(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RecoveryAttempt:
        strat = RecoveryStrategy(data.get("strategy", RecoveryStrategy.FAIL))
        stat = RecoveryStatus(data.get("status", RecoveryStatus.PENDING))
        return cls(
            attempt_index=int(data.get("attempt_index", 1)),
            strategy=strat,
            started_at=data.get("started_at", ""),
            completed_at=data.get("completed_at"),
            status=stat,
            result_outcome=data.get("result_outcome"),
            error=data.get("error"),
            metadata=data.get("metadata", {}),
        )


@dataclass(frozen=True)
class RecoveryHistory:
    """Historical sequence of recovery attempts for a specific context."""

    recovery_context_id: str
    attempts: tuple[RecoveryAttempt, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "attempts", _freeze_tuple(self.attempts))
        object.__setattr__(self, "metadata", _freeze_dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "recovery_context_id": self.recovery_context_id,
            "attempts": [a.to_dict() for a in self.attempts],
            "metadata": _to_json_serializable(self.metadata),
        }


@dataclass(frozen=True)
class RetryPolicy:
    """Configuration rules for automatic retry behavior."""

    maximum_attempts: int = 3
    retryable_errors: tuple[str, ...] = ()
    non_retryable_errors: tuple[str, ...] = ()
    backoff_strategy: BackoffStrategy = BackoffStrategy.EXPONENTIAL
    initial_delay_seconds: float = 1.0
    maximum_delay_seconds: float = 60.0
    jitter: bool = True
    require_reobservation_after: tuple[str, ...] = ()
    allowed_operations: tuple[str, ...] = ()
    prohibited_operations: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.maximum_attempts < 0:
            raise ValueError("maximum_attempts cannot be negative.")
        if self.initial_delay_seconds < 0:
            raise ValueError("initial_delay_seconds cannot be negative.")
        if self.maximum_delay_seconds < self.initial_delay_seconds:
            raise ValueError(
                "maximum_delay_seconds cannot be smaller than initial_delay_seconds."
            )
        object.__setattr__(
            self, "retryable_errors", _freeze_tuple(self.retryable_errors)
        )
        object.__setattr__(
            self, "non_retryable_errors", _freeze_tuple(self.non_retryable_errors)
        )
        object.__setattr__(
            self,
            "require_reobservation_after",
            _freeze_tuple(self.require_reobservation_after),
        )
        object.__setattr__(
            self, "allowed_operations", _freeze_tuple(self.allowed_operations)
        )
        object.__setattr__(
            self, "prohibited_operations", _freeze_tuple(self.prohibited_operations)
        )
        object.__setattr__(self, "metadata", _freeze_dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "maximum_attempts": self.maximum_attempts,
            "retryable_errors": list(self.retryable_errors),
            "non_retryable_errors": list(self.non_retryable_errors),
            "backoff_strategy": self.backoff_strategy.value
            if isinstance(self.backoff_strategy, BackoffStrategy)
            else str(self.backoff_strategy),
            "initial_delay_seconds": self.initial_delay_seconds,
            "maximum_delay_seconds": self.maximum_delay_seconds,
            "jitter": self.jitter,
            "require_reobservation_after": list(self.require_reobservation_after),
            "allowed_operations": list(self.allowed_operations),
            "prohibited_operations": list(self.prohibited_operations),
            "metadata": _to_json_serializable(self.metadata),
        }


@dataclass(frozen=True)
class ReplanPolicy:
    """Configuration rules for replanning behavior upon failure."""

    allow_replan: bool = True
    maximum_replans: int = 2
    preserve_goal_criteria: bool = True
    prohibited_operations: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "prohibited_operations", _freeze_tuple(self.prohibited_operations)
        )
        object.__setattr__(self, "metadata", _freeze_dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "allow_replan": self.allow_replan,
            "maximum_replans": self.maximum_replans,
            "preserve_goal_criteria": self.preserve_goal_criteria,
            "prohibited_operations": list(self.prohibited_operations),
            "metadata": _to_json_serializable(self.metadata),
        }


@dataclass(frozen=True)
class RollbackPolicy:
    """Configuration rules for checkpoint restoration and rollback."""

    automatic_for: tuple[str, ...] = ()
    approval_required_for: tuple[str, ...] = ()
    prohibited_for: tuple[str, ...] = ()
    validate_after_rollback: bool = True
    preserve_artifacts: bool = True
    allowed_checkpoint_statuses: tuple[CheckpointStatus, ...] = (
        CheckpointStatus.ACTIVE,
    )
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "automatic_for", _freeze_tuple(self.automatic_for))
        object.__setattr__(
            self, "approval_required_for", _freeze_tuple(self.approval_required_for)
        )
        object.__setattr__(self, "prohibited_for", _freeze_tuple(self.prohibited_for))
        object.__setattr__(
            self,
            "allowed_checkpoint_statuses",
            _freeze_tuple(self.allowed_checkpoint_statuses),
        )
        object.__setattr__(self, "metadata", _freeze_dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "automatic_for": list(self.automatic_for),
            "approval_required_for": list(self.approval_required_for),
            "prohibited_for": list(self.prohibited_for),
            "validate_after_rollback": self.validate_after_rollback,
            "preserve_artifacts": self.preserve_artifacts,
            "allowed_checkpoint_statuses": [
                s.value if isinstance(s, CheckpointStatus) else str(s)
                for s in self.allowed_checkpoint_statuses
            ],
            "metadata": _to_json_serializable(self.metadata),
        }


@dataclass(frozen=True)
class EscalationPolicy:
    """Configuration rules for escalating recovery to human or higher level authority."""

    triggers: tuple[str, ...] = ()
    escalation_target: EscalationTarget = EscalationTarget.USER
    required_evidence: tuple[str, ...] = ()
    preserve_runtime_state: bool = True
    pause_runtime: bool = True
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "triggers", _freeze_tuple(self.triggers))
        object.__setattr__(
            self, "required_evidence", _freeze_tuple(self.required_evidence)
        )
        object.__setattr__(self, "metadata", _freeze_dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "triggers": list(self.triggers),
            "escalation_target": self.escalation_target.value
            if isinstance(self.escalation_target, EscalationTarget)
            else str(self.escalation_target),
            "required_evidence": list(self.required_evidence),
            "preserve_runtime_state": self.preserve_runtime_state,
            "pause_runtime": self.pause_runtime,
            "metadata": _to_json_serializable(self.metadata),
        }


@dataclass(frozen=True)
class RecoveryConstraints:
    """Evaluated runtime constraints restricting recovery decisions."""

    max_attempts_exceeded: bool = False
    budget_exhausted: bool = False
    inconsistent_state: bool = False
    irreversible_side_effects: bool = False
    approval_required: bool = False
    prohibited_strategies: tuple[RecoveryStrategy, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "prohibited_strategies", _freeze_tuple(self.prohibited_strategies)
        )
        object.__setattr__(self, "metadata", _freeze_dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "max_attempts_exceeded": self.max_attempts_exceeded,
            "budget_exhausted": self.budget_exhausted,
            "inconsistent_state": self.inconsistent_state,
            "irreversible_side_effects": self.irreversible_side_effects,
            "approval_required": self.approval_required,
            "prohibited_strategies": [
                s.value if isinstance(s, RecoveryStrategy) else str(s)
                for s in self.prohibited_strategies
            ],
            "metadata": _to_json_serializable(self.metadata),
        }


@dataclass(frozen=True)
class RecoveryStrategyResult:
    """Detailed result payload produced by a recovery strategy executor."""

    strategy: RecoveryStrategy
    status: RecoveryStatus
    success: bool
    error_message: str | None = None
    modified_state: Mapping[str, Any] = field(default_factory=dict)
    produced_artifacts: tuple[str, ...] = ()
    residual_risk: Mapping[str, Any] = field(default_factory=dict)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "modified_state", _freeze_dict(self.modified_state))
        object.__setattr__(
            self, "produced_artifacts", _freeze_tuple(self.produced_artifacts)
        )
        object.__setattr__(self, "residual_risk", _freeze_dict(self.residual_risk))
        object.__setattr__(self, "metadata", _freeze_dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "strategy": self.strategy.value
            if isinstance(self.strategy, RecoveryStrategy)
            else str(self.strategy),
            "status": self.status.value
            if isinstance(self.status, RecoveryStatus)
            else str(self.status),
            "success": self.success,
            "error_message": self.error_message,
            "modified_state": _to_json_serializable(self.modified_state),
            "produced_artifacts": list(self.produced_artifacts),
            "residual_risk": _to_json_serializable(self.residual_risk),
            "metadata": _to_json_serializable(self.metadata),
        }


@dataclass(frozen=True)
class RecoveryExecutionRequest:
    """Request payload to execute a decided recovery strategy."""

    recovery_decision_id: str
    recovery_context_id: str
    strategy: RecoveryStrategy
    idempotency_key: str
    requested_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.requested_at:
            object.__setattr__(
                self, "requested_at", datetime.now(timezone.utc).isoformat()
            )
        object.__setattr__(self, "metadata", _freeze_dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "recovery_decision_id": self.recovery_decision_id,
            "recovery_context_id": self.recovery_context_id,
            "strategy": self.strategy.value
            if isinstance(self.strategy, RecoveryStrategy)
            else str(self.strategy),
            "idempotency_key": self.idempotency_key,
            "requested_at": self.requested_at,
            "metadata": _to_json_serializable(self.metadata),
        }


@dataclass(frozen=True)
class RecoveryExecutionResult:
    """Outcome payload resulting from executing a recovery strategy."""

    recovery_execution_id: str
    recovery_decision_id: str
    recovery_context_id: str
    strategy: RecoveryStrategy
    status: RecoveryStatus
    success: bool
    attempt: RecoveryAttempt
    strategy_result: RecoveryStrategyResult | None = None
    error: str | None = None
    executed_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)
    fingerprint: str = ""

    def __post_init__(self) -> None:
        if not self.executed_at:
            object.__setattr__(
                self, "executed_at", datetime.now(timezone.utc).isoformat()
            )
        object.__setattr__(self, "metadata", _freeze_dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "recovery_execution_id": self.recovery_execution_id,
            "recovery_decision_id": self.recovery_decision_id,
            "recovery_context_id": self.recovery_context_id,
            "strategy": self.strategy.value
            if isinstance(self.strategy, RecoveryStrategy)
            else str(self.strategy),
            "status": self.status.value
            if isinstance(self.status, RecoveryStatus)
            else str(self.status),
            "success": self.success,
            "attempt": self.attempt.to_dict() if self.attempt else None,
            "strategy_result": self.strategy_result.to_dict()
            if self.strategy_result
            else None,
            "error": self.error,
            "executed_at": self.executed_at,
            "metadata": _to_json_serializable(self.metadata),
            "fingerprint": self.fingerprint,
        }


@dataclass(frozen=True)
class RecoveryEvidence:
    """Audit evidence bundle collected for failure investigation and escalation."""

    evidence_id: str
    recovery_context_id: str
    error_summary: str
    logs: tuple[str, ...] = ()
    validation_results: tuple[Mapping[str, Any], ...] = ()
    checkpoint_ids: tuple[str, ...] = ()
    side_effects: tuple[Mapping[str, Any], ...] = ()
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.created_at:
            object.__setattr__(
                self, "created_at", datetime.now(timezone.utc).isoformat()
            )
        object.__setattr__(self, "logs", _freeze_tuple(self.logs))
        object.__setattr__(
            self, "validation_results", _freeze_tuple(self.validation_results)
        )
        object.__setattr__(self, "checkpoint_ids", _freeze_tuple(self.checkpoint_ids))
        object.__setattr__(self, "side_effects", _freeze_tuple(self.side_effects))
        object.__setattr__(self, "metadata", _freeze_dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "recovery_context_id": self.recovery_context_id,
            "error_summary": self.error_summary,
            "logs": list(self.logs),
            "validation_results": _to_json_serializable(self.validation_results),
            "checkpoint_ids": list(self.checkpoint_ids),
            "side_effects": _to_json_serializable(self.side_effects),
            "created_at": self.created_at,
            "metadata": _to_json_serializable(self.metadata),
        }


@dataclass(frozen=True)
class RecoveryRiskAssessment:
    """Evaluated risk matrix for candidate recovery strategies."""

    risk_score: float
    has_irreversible_side_effects: bool
    inconsistent_state_detected: bool
    policy_violations: tuple[str, ...] = ()
    recommended_actions: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "policy_violations", _freeze_tuple(self.policy_violations)
        )
        object.__setattr__(
            self, "recommended_actions", _freeze_tuple(self.recommended_actions)
        )
        object.__setattr__(self, "metadata", _freeze_dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "risk_score": self.risk_score,
            "has_irreversible_side_effects": self.has_irreversible_side_effects,
            "inconsistent_state_detected": self.inconsistent_state_detected,
            "policy_violations": list(self.policy_violations),
            "recommended_actions": list(self.recommended_actions),
            "metadata": _to_json_serializable(self.metadata),
        }


@dataclass(frozen=True)
class RecoveryBudgetSnapshot:
    """Snapshot of budget remaining for recovery actions."""

    operations_remaining: int
    cost_remaining: float
    time_remaining_seconds: float
    retry_budget_remaining: int
    rollback_budget_remaining: int
    validation_budget_remaining: int
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "metadata", _freeze_dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "operations_remaining": self.operations_remaining,
            "cost_remaining": self.cost_remaining,
            "time_remaining_seconds": self.time_remaining_seconds,
            "retry_budget_remaining": self.retry_budget_remaining,
            "rollback_budget_remaining": self.rollback_budget_remaining,
            "validation_budget_remaining": self.validation_budget_remaining,
            "metadata": _to_json_serializable(self.metadata),
        }


@dataclass(frozen=True)
class RecoveryContext:
    """Immutable context capturing all relevant details of an agent execution failure."""

    recovery_context_id: str
    agent_run_id: str
    goal_id: str
    workflow_id: str
    iteration_id: str
    failed_task_id: str
    failed_operation_id: str
    error: Mapping[str, Any]
    validation_result_ids: tuple[str, ...] = ()
    retry_history: tuple[RecoveryAttempt, ...] = ()
    checkpoint_ids: tuple[str, ...] = ()
    transaction_boundary_id: str | None = None
    remaining_budget: Mapping[str, Any] = field(default_factory=dict)
    executed_operations: tuple[str, ...] = ()
    side_effects: tuple[Mapping[str, Any], ...] = ()
    partial_changes: tuple[Mapping[str, Any], ...] = ()
    current_state: Mapping[str, Any] = field(default_factory=dict)
    constraints: tuple[Mapping[str, Any], ...] = ()
    approvals: tuple[Mapping[str, Any], ...] = ()
    risks: tuple[Mapping[str, Any], ...] = ()
    knowledge_version: str | None = None
    memory_version: str | None = None
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)
    fingerprint: str = ""

    def __post_init__(self) -> None:
        if not self.recovery_context_id:
            raise RecoveryContextError(
                "RecoveryContext must have a non-empty recovery_context_id."
            )
        if not self.agent_run_id:
            raise RecoveryContextError(
                "RecoveryContext must have a non-empty agent_run_id."
            )

        if not self.created_at:
            object.__setattr__(
                self, "created_at", datetime.now(timezone.utc).isoformat()
            )

        object.__setattr__(self, "error", _freeze_dict(self.error))
        object.__setattr__(
            self, "validation_result_ids", _freeze_tuple(self.validation_result_ids)
        )
        object.__setattr__(self, "retry_history", _freeze_tuple(self.retry_history))
        object.__setattr__(self, "checkpoint_ids", _freeze_tuple(self.checkpoint_ids))
        object.__setattr__(
            self, "remaining_budget", _freeze_dict(self.remaining_budget)
        )
        object.__setattr__(
            self, "executed_operations", _freeze_tuple(self.executed_operations)
        )
        object.__setattr__(self, "side_effects", _freeze_tuple(self.side_effects))
        object.__setattr__(self, "partial_changes", _freeze_tuple(self.partial_changes))
        object.__setattr__(self, "current_state", _freeze_dict(self.current_state))
        object.__setattr__(self, "constraints", _freeze_tuple(self.constraints))
        object.__setattr__(self, "approvals", _freeze_tuple(self.approvals))
        object.__setattr__(self, "risks", _freeze_tuple(self.risks))
        object.__setattr__(self, "metadata", _freeze_dict(self.metadata))

        if not self.fingerprint:
            computed = compute_recovery_context_fingerprint(
                recovery_context_id=self.recovery_context_id,
                agent_run_id=self.agent_run_id,
                goal_id=self.goal_id,
                workflow_id=self.workflow_id,
                iteration_id=self.iteration_id,
                failed_task_id=self.failed_task_id,
                failed_operation_id=self.failed_operation_id,
                error=self.error,
                created_at=self.created_at,
            )
            object.__setattr__(self, "fingerprint", computed)

    def to_dict(self) -> dict[str, Any]:
        return {
            "recovery_context_id": self.recovery_context_id,
            "agent_run_id": self.agent_run_id,
            "goal_id": self.goal_id,
            "workflow_id": self.workflow_id,
            "iteration_id": self.iteration_id,
            "failed_task_id": self.failed_task_id,
            "failed_operation_id": self.failed_operation_id,
            "error": _to_json_serializable(self.error),
            "validation_result_ids": list(self.validation_result_ids),
            "retry_history": [a.to_dict() for a in self.retry_history],
            "checkpoint_ids": list(self.checkpoint_ids),
            "transaction_boundary_id": self.transaction_boundary_id,
            "remaining_budget": _to_json_serializable(self.remaining_budget),
            "executed_operations": list(self.executed_operations),
            "side_effects": _to_json_serializable(self.side_effects),
            "partial_changes": _to_json_serializable(self.partial_changes),
            "current_state": _to_json_serializable(self.current_state),
            "constraints": _to_json_serializable(self.constraints),
            "approvals": _to_json_serializable(self.approvals),
            "risks": _to_json_serializable(self.risks),
            "knowledge_version": self.knowledge_version,
            "memory_version": self.memory_version,
            "created_at": self.created_at,
            "metadata": _to_json_serializable(self.metadata),
            "fingerprint": self.fingerprint,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RecoveryContext:
        retry_hist = tuple(
            RecoveryAttempt.from_dict(a) if isinstance(a, dict) else a
            for a in data.get("retry_history", ())
        )
        return cls(
            recovery_context_id=data["recovery_context_id"],
            agent_run_id=data["agent_run_id"],
            goal_id=data.get("goal_id", ""),
            workflow_id=data.get("workflow_id", ""),
            iteration_id=data.get("iteration_id", ""),
            failed_task_id=data.get("failed_task_id", ""),
            failed_operation_id=data.get("failed_operation_id", ""),
            error=data.get("error", {}),
            validation_result_ids=tuple(data.get("validation_result_ids", ())),
            retry_history=retry_hist,
            checkpoint_ids=tuple(data.get("checkpoint_ids", ())),
            transaction_boundary_id=data.get("transaction_boundary_id"),
            remaining_budget=data.get("remaining_budget", {}),
            executed_operations=tuple(data.get("executed_operations", ())),
            side_effects=tuple(data.get("side_effects", ())),
            partial_changes=tuple(data.get("partial_changes", ())),
            current_state=data.get("current_state", {}),
            constraints=tuple(data.get("constraints", ())),
            approvals=tuple(data.get("approvals", ())),
            risks=tuple(data.get("risks", ())),
            knowledge_version=data.get("knowledge_version"),
            memory_version=data.get("memory_version"),
            created_at=data.get("created_at", ""),
            metadata=data.get("metadata", {}),
            fingerprint=data.get("fingerprint", ""),
        )


@dataclass(frozen=True)
class RecoveryDecision:
    """Immutable structured decision output generated by the Recovery Decision Engine."""

    recovery_decision_id: str
    recovery_context_id: str
    strategy: RecoveryStrategy
    reason_codes: tuple[RecoveryReasonCode, ...] = ()
    confidence: float = 1.0
    requires_approval: bool = False
    checkpoint_id: str | None = None
    delay_seconds: float | None = None
    modified_parameters: Mapping[str, Any] = field(default_factory=dict)
    modified_constraints: tuple[Mapping[str, Any], ...] = ()
    expected_state: Mapping[str, Any] = field(default_factory=dict)
    residual_risk: Mapping[str, Any] = field(default_factory=dict)
    idempotency_key: str = ""
    decided_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)
    fingerprint: str = ""

    def __post_init__(self) -> None:
        if not self.recovery_decision_id:
            raise RecoveryDecisionError(
                "RecoveryDecision must have a non-empty recovery_decision_id."
            )
        if not self.recovery_context_id:
            raise RecoveryDecisionError(
                "RecoveryDecision must have a non-empty recovery_context_id."
            )

        if not self.decided_at:
            object.__setattr__(
                self, "decided_at", datetime.now(timezone.utc).isoformat()
            )
        if not self.idempotency_key:
            strat_str = (
                self.strategy.value
                if hasattr(self.strategy, "value")
                else str(self.strategy)
            )
            object.__setattr__(
                self,
                "idempotency_key",
                f"dec-{self.recovery_context_id}-{strat_str}",
            )

        object.__setattr__(self, "reason_codes", _freeze_tuple(self.reason_codes))
        object.__setattr__(
            self, "modified_parameters", _freeze_dict(self.modified_parameters)
        )
        object.__setattr__(
            self, "modified_constraints", _freeze_tuple(self.modified_constraints)
        )
        object.__setattr__(self, "expected_state", _freeze_dict(self.expected_state))
        object.__setattr__(self, "residual_risk", _freeze_dict(self.residual_risk))
        object.__setattr__(self, "metadata", _freeze_dict(self.metadata))

        if not self.fingerprint:
            rc_strs = tuple(
                r.value if isinstance(r, RecoveryReasonCode) else str(r)
                for r in self.reason_codes
            )
            computed = compute_recovery_decision_fingerprint(
                recovery_decision_id=self.recovery_decision_id,
                recovery_context_id=self.recovery_context_id,
                strategy=self.strategy.value
                if isinstance(self.strategy, RecoveryStrategy)
                else str(self.strategy),
                reason_codes=rc_strs,
                idempotency_key=self.idempotency_key,
                decided_at=self.decided_at,
            )
            object.__setattr__(self, "fingerprint", computed)

    def to_dict(self) -> dict[str, Any]:
        return {
            "recovery_decision_id": self.recovery_decision_id,
            "recovery_context_id": self.recovery_context_id,
            "strategy": self.strategy.value
            if isinstance(self.strategy, RecoveryStrategy)
            else str(self.strategy),
            "reason_codes": [
                r.value if isinstance(r, RecoveryReasonCode) else str(r)
                for r in self.reason_codes
            ],
            "confidence": self.confidence,
            "requires_approval": self.requires_approval,
            "checkpoint_id": self.checkpoint_id,
            "delay_seconds": self.delay_seconds,
            "modified_parameters": _to_json_serializable(self.modified_parameters),
            "modified_constraints": _to_json_serializable(self.modified_constraints),
            "expected_state": _to_json_serializable(self.expected_state),
            "residual_risk": _to_json_serializable(self.residual_risk),
            "idempotency_key": self.idempotency_key,
            "decided_at": self.decided_at,
            "metadata": _to_json_serializable(self.metadata),
            "fingerprint": self.fingerprint,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RecoveryDecision:
        strat = RecoveryStrategy(data["strategy"])
        rcs = tuple(
            RecoveryReasonCode(r) if isinstance(r, str) else r
            for r in data.get("reason_codes", ())
        )
        return cls(
            recovery_decision_id=data["recovery_decision_id"],
            recovery_context_id=data["recovery_context_id"],
            strategy=strat,
            reason_codes=rcs,
            confidence=float(data.get("confidence", 1.0)),
            requires_approval=bool(data.get("requires_approval", False)),
            checkpoint_id=data.get("checkpoint_id"),
            delay_seconds=data.get("delay_seconds"),
            modified_parameters=data.get("modified_parameters", {}),
            modified_constraints=tuple(data.get("modified_constraints", ())),
            expected_state=data.get("expected_state", {}),
            residual_risk=data.get("residual_risk", {}),
            idempotency_key=data.get("idempotency_key", ""),
            decided_at=data.get("decided_at", ""),
            metadata=data.get("metadata", {}),
            fingerprint=data.get("fingerprint", ""),
        )
