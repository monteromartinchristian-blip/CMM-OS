"""Phase 9.19 – Agent Runtime Trace Contracts.

Immutable, serializable, timezone-aware dataclasses for structured
tracing of autonomous agent executions.  No chain-of-thought, no private
prompts, no secrets, no stack traces, no arbitrary object serialization.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from cmm.agent_runtime.enums import (
    AgentAutonomyLevel,
)

# ── Helpers ────────────────────────────────────────────────────────────────────


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _compute_fingerprint(*, stable: str) -> str:
    return hashlib.sha256(stable.encode("utf-8")).hexdigest()[:32]


def _freeze_payload(payload: Any) -> tuple[tuple[str, Any], ...]:
    """Freeze a mutable dict into a sorted tuple of key-value pairs."""
    if not isinstance(payload, dict):
        return (("value", str(payload)),)
    return tuple(sorted((k, _freeze_payload(v)) for k, v in payload.items()))


# ── AgentTraceHeader ───────────────────────────────────────────────────────────


@dataclass(frozen=True)
class AgentTraceHeader:
    """Immutable header for an AgentTrace."""

    trace_id: str
    agent_run_id: str
    goal_id: str
    goal_created_by: str
    agent_id: str
    workflow_id: str
    autonomy_level: AgentAutonomyLevel | int
    status: str = "open"
    started_at: datetime = field(default_factory=_utcnow)
    completed_at: datetime | None = None
    duration_ms: int | None = None
    event_count: int = 0
    source_event_ids: tuple[str, ...] = field(default_factory=tuple)
    correlation_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    fingerprint: str = ""

    def __post_init__(self) -> None:
        if not self.trace_id or not isinstance(self.trace_id, str):
            raise ValueError("trace_id must be a non-empty string")
        if not self.agent_run_id or not isinstance(self.agent_run_id, str):
            raise ValueError("agent_run_id must be a non-empty string")
        if not self.goal_id or not isinstance(self.goal_id, str):
            raise ValueError("goal_id must be a non-empty string")
        if self.completed_at is not None and self.started_at > self.completed_at:
            raise ValueError("completed_at must not be before started_at")
        if self.duration_ms is not None and self.duration_ms < 0:
            raise ValueError("duration_ms must not be negative")

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "trace_id": self.trace_id,
            "agent_run_id": self.agent_run_id,
            "goal_id": self.goal_id,
            "goal_created_by": self.goal_created_by,
            "agent_id": self.agent_id,
            "workflow_id": self.workflow_id,
            "autonomy_level": int(self.autonomy_level)
            if isinstance(self.autonomy_level, AgentAutonomyLevel)
            else self.autonomy_level,
            "status": self.status,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat()
            if self.completed_at
            else None,
            "duration_ms": self.duration_ms,
            "event_count": self.event_count,
            "source_event_ids": list(self.source_event_ids),
            "correlation_id": self.correlation_id,
            "metadata": dict(self.metadata),
            "fingerprint": self.fingerprint,
        }
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentTraceHeader:
        return cls(
            trace_id=str(data["trace_id"]),
            agent_run_id=str(data["agent_run_id"]),
            goal_id=str(data["goal_id"]),
            goal_created_by=str(data.get("goal_created_by", "")),
            agent_id=str(data.get("agent_id", "")),
            workflow_id=str(data.get("workflow_id", "")),
            autonomy_level=data.get("autonomy_level", 0),
            status=str(data.get("status", "open")),
            started_at=datetime.fromisoformat(data["started_at"])
            if isinstance(data.get("started_at"), str)
            else data.get("started_at", _utcnow()),
            completed_at=datetime.fromisoformat(data["completed_at"])
            if isinstance(data.get("completed_at"), str)
            else data.get("completed_at"),
            duration_ms=data.get("duration_ms"),
            event_count=int(data.get("event_count", 0)),
            source_event_ids=tuple(data.get("source_event_ids", [])),
            correlation_id=str(data.get("correlation_id", "")),
            metadata=dict(data.get("metadata", {})),
            fingerprint=str(data.get("fingerprint", "")),
        )


# ── AgentTraceIteration ────────────────────────────────────────────────────────


@dataclass(frozen=True)
class AgentTraceIteration:
    """Trace record for a single iteration within an agent run."""

    iteration_id: str
    sequence: int
    started_at: datetime = field(default_factory=_utcnow)
    completed_at: datetime | None = None
    initial_state: str = ""
    final_state: str = ""
    record_ids: tuple[str, ...] = field(default_factory=tuple)
    operation_ids: tuple[str, ...] = field(default_factory=tuple)
    validation_ids: tuple[str, ...] = field(default_factory=tuple)
    recovery_ids: tuple[str, ...] = field(default_factory=tuple)
    budget_event_ids: tuple[str, ...] = field(default_factory=tuple)
    decision_id: str = ""
    continue_reason_codes: tuple[str, ...] = field(default_factory=tuple)
    stop_reason_codes: tuple[str, ...] = field(default_factory=tuple)
    warnings: tuple[str, ...] = field(default_factory=tuple)
    errors: tuple[str, ...] = field(default_factory=tuple)
    metadata: dict[str, Any] = field(default_factory=dict)
    fingerprint: str = ""

    def __post_init__(self) -> None:
        if not self.iteration_id or not isinstance(self.iteration_id, str):
            raise ValueError("iteration_id must be a non-empty string")
        if self.sequence < 0:
            raise ValueError("sequence must not be negative")
        if self.completed_at is not None and self.started_at > self.completed_at:
            raise ValueError("completed_at must not be before started_at")

    def to_dict(self) -> dict[str, Any]:
        return {
            "iteration_id": self.iteration_id,
            "sequence": self.sequence,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat()
            if self.completed_at
            else None,
            "initial_state": self.initial_state,
            "final_state": self.final_state,
            "record_ids": list(self.record_ids),
            "operation_ids": list(self.operation_ids),
            "validation_ids": list(self.validation_ids),
            "recovery_ids": list(self.recovery_ids),
            "budget_event_ids": list(self.budget_event_ids),
            "decision_id": self.decision_id,
            "continue_reason_codes": list(self.continue_reason_codes),
            "stop_reason_codes": list(self.stop_reason_codes),
            "warnings": list(self.warnings),
            "errors": list(self.errors),
            "metadata": dict(self.metadata),
            "fingerprint": self.fingerprint,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentTraceIteration:
        return cls(
            iteration_id=str(data["iteration_id"]),
            sequence=int(data.get("sequence", 0)),
            started_at=datetime.fromisoformat(data["started_at"])
            if isinstance(data.get("started_at"), str)
            else data.get("started_at", _utcnow()),
            completed_at=datetime.fromisoformat(data["completed_at"])
            if isinstance(data.get("completed_at"), str)
            else data.get("completed_at"),
            initial_state=str(data.get("initial_state", "")),
            final_state=str(data.get("final_state", "")),
            record_ids=tuple(data.get("record_ids", [])),
            operation_ids=tuple(data.get("operation_ids", [])),
            validation_ids=tuple(data.get("validation_ids", [])),
            recovery_ids=tuple(data.get("recovery_ids", [])),
            budget_event_ids=tuple(data.get("budget_event_ids", [])),
            decision_id=str(data.get("decision_id", "")),
            continue_reason_codes=tuple(data.get("continue_reason_codes", [])),
            stop_reason_codes=tuple(data.get("stop_reason_codes", [])),
            warnings=tuple(data.get("warnings", [])),
            errors=tuple(data.get("errors", [])),
            metadata=dict(data.get("metadata", {})),
            fingerprint=str(data.get("fingerprint", "")),
        )


# ── AgentTraceObservation ──────────────────────────────────────────────────────


@dataclass(frozen=True)
class AgentTraceObservation:
    """Trace record for an observation made during execution."""

    observation_id: str
    kind: str = ""
    summary: str = ""
    source: str = ""
    significance: str = "info"
    observation_ref: str = ""
    timestamp: datetime = field(default_factory=_utcnow)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "observation_id": self.observation_id,
            "kind": self.kind,
            "summary": self.summary,
            "source": self.source,
            "significance": self.significance,
            "observation_ref": self.observation_ref,
            "timestamp": self.timestamp.isoformat(),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentTraceObservation:
        return cls(
            observation_id=str(data["observation_id"]),
            kind=str(data.get("kind", "")),
            summary=str(data.get("summary", "")),
            source=str(data.get("source", "")),
            significance=str(data.get("significance", "info")),
            observation_ref=str(data.get("observation_ref", "")),
            timestamp=datetime.fromisoformat(data["timestamp"])
            if isinstance(data.get("timestamp"), str)
            else data.get("timestamp", _utcnow()),
            metadata=dict(data.get("metadata", {})),
        )


# ── AgentTraceKnowledgeLoad ────────────────────────────────────────────────────


@dataclass(frozen=True)
class AgentTraceKnowledgeLoad:
    """Trace record for knowledge loaded during execution."""

    load_id: str
    source: str = ""
    knowledge_ids: tuple[str, ...] = field(default_factory=tuple)
    summary: str = ""
    timestamp: datetime = field(default_factory=_utcnow)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "load_id": self.load_id,
            "source": self.source,
            "knowledge_ids": list(self.knowledge_ids),
            "summary": self.summary,
            "timestamp": self.timestamp.isoformat(),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentTraceKnowledgeLoad:
        return cls(
            load_id=str(data["load_id"]),
            source=str(data.get("source", "")),
            knowledge_ids=tuple(data.get("knowledge_ids", [])),
            summary=str(data.get("summary", "")),
            timestamp=datetime.fromisoformat(data["timestamp"])
            if isinstance(data.get("timestamp"), str)
            else data.get("timestamp", _utcnow()),
            metadata=dict(data.get("metadata", {})),
        )


# ── AgentTraceCognitiveProfile ─────────────────────────────────────────────────


@dataclass(frozen=True)
class AgentTraceCognitiveProfile:
    """Trace record for the cognitive profile used during reasoning."""

    profile_id: str
    profile_name: str = ""
    strategy: str = ""
    session_id: str = ""
    timestamp: datetime = field(default_factory=_utcnow)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile_id": self.profile_id,
            "profile_name": self.profile_name,
            "strategy": self.strategy,
            "session_id": self.session_id,
            "timestamp": self.timestamp.isoformat(),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentTraceCognitiveProfile:
        return cls(
            profile_id=str(data["profile_id"]),
            profile_name=str(data.get("profile_name", "")),
            strategy=str(data.get("strategy", "")),
            session_id=str(data.get("session_id", "")),
            timestamp=datetime.fromisoformat(data["timestamp"])
            if isinstance(data.get("timestamp"), str)
            else data.get("timestamp", _utcnow()),
            metadata=dict(data.get("metadata", {})),
        )


# ── AgentTraceInformationGap ───────────────────────────────────────────────────


@dataclass(frozen=True)
class AgentTraceInformationGap:
    """Trace record for an information gap detected during execution."""

    gap_id: str
    description: str = ""
    strategy: str = ""
    resolved: bool = False
    resolution_ref: str = ""
    timestamp: datetime = field(default_factory=_utcnow)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "gap_id": self.gap_id,
            "description": self.description,
            "strategy": self.strategy,
            "resolved": self.resolved,
            "resolution_ref": self.resolution_ref,
            "timestamp": self.timestamp.isoformat(),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentTraceInformationGap:
        return cls(
            gap_id=str(data["gap_id"]),
            description=str(data.get("description", "")),
            strategy=str(data.get("strategy", "")),
            resolved=bool(data.get("resolved", False)),
            resolution_ref=str(data.get("resolution_ref", "")),
            timestamp=datetime.fromisoformat(data["timestamp"])
            if isinstance(data.get("timestamp"), str)
            else data.get("timestamp", _utcnow()),
            metadata=dict(data.get("metadata", {})),
        )


# ── AgentTraceQuestion ─────────────────────────────────────────────────────────


@dataclass(frozen=True)
class AgentTraceQuestion:
    """Trace record for a question asked during execution."""

    question_id: str
    question_summary: str = ""
    asked_to: str = ""
    answer_summary: str = ""
    answered: bool = False
    timestamp: datetime = field(default_factory=_utcnow)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "question_id": self.question_id,
            "question_summary": self.question_summary,
            "asked_to": self.asked_to,
            "answer_summary": self.answer_summary,
            "answered": self.answered,
            "timestamp": self.timestamp.isoformat(),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentTraceQuestion:
        return cls(
            question_id=str(data["question_id"]),
            question_summary=str(data.get("question_summary", "")),
            asked_to=str(data.get("asked_to", "")),
            answer_summary=str(data.get("answer_summary", "")),
            answered=bool(data.get("answered", False)),
            timestamp=datetime.fromisoformat(data["timestamp"])
            if isinstance(data.get("timestamp"), str)
            else data.get("timestamp", _utcnow()),
            metadata=dict(data.get("metadata", {})),
        )


# ── AgentTraceReasoningReference ───────────────────────────────────────────────


@dataclass(frozen=True)
class AgentTraceReasoningReference:
    """Reference to a reasoning result without storing chain-of-thought."""

    reasoning_result_id: str
    cognitive_request_id: str = ""
    status: str = ""
    decision: str = ""
    summary: str = ""
    timestamp: datetime = field(default_factory=_utcnow)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "reasoning_result_id": self.reasoning_result_id,
            "cognitive_request_id": self.cognitive_request_id,
            "status": self.status,
            "decision": self.decision,
            "summary": self.summary,
            "timestamp": self.timestamp.isoformat(),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentTraceReasoningReference:
        return cls(
            reasoning_result_id=str(data["reasoning_result_id"]),
            cognitive_request_id=str(data.get("cognitive_request_id", "")),
            status=str(data.get("status", "")),
            decision=str(data.get("decision", "")),
            summary=str(data.get("summary", "")),
            timestamp=datetime.fromisoformat(data["timestamp"])
            if isinstance(data.get("timestamp"), str)
            else data.get("timestamp", _utcnow()),
            metadata=dict(data.get("metadata", {})),
        )


# ── AgentTraceRuntimeDecision ──────────────────────────────────────────────────


@dataclass(frozen=True)
class AgentTraceRuntimeDecision:
    """Trace record for a runtime decision (continue, stop, retry, replan, etc.)."""

    decision_id: str
    decision_kind: str = ""
    state_before: str = ""
    state_after: str = ""
    reason_codes: tuple[str, ...] = field(default_factory=tuple)
    policy_refs: tuple[str, ...] = field(default_factory=tuple)
    evidence_refs: tuple[str, ...] = field(default_factory=tuple)
    approval_refs: tuple[str, ...] = field(default_factory=tuple)
    budget_refs: tuple[str, ...] = field(default_factory=tuple)
    validation_refs: tuple[str, ...] = field(default_factory=tuple)
    outcome_refs: tuple[str, ...] = field(default_factory=tuple)
    timestamp: datetime = field(default_factory=_utcnow)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "decision_kind": self.decision_kind,
            "state_before": self.state_before,
            "state_after": self.state_after,
            "reason_codes": list(self.reason_codes),
            "policy_refs": list(self.policy_refs),
            "evidence_refs": list(self.evidence_refs),
            "approval_refs": list(self.approval_refs),
            "budget_refs": list(self.budget_refs),
            "validation_refs": list(self.validation_refs),
            "outcome_refs": list(self.outcome_refs),
            "timestamp": self.timestamp.isoformat(),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentTraceRuntimeDecision:
        return cls(
            decision_id=str(data["decision_id"]),
            decision_kind=str(data.get("decision_kind", "")),
            state_before=str(data.get("state_before", "")),
            state_after=str(data.get("state_after", "")),
            reason_codes=tuple(data.get("reason_codes", [])),
            policy_refs=tuple(data.get("policy_refs", [])),
            evidence_refs=tuple(data.get("evidence_refs", [])),
            approval_refs=tuple(data.get("approval_refs", [])),
            budget_refs=tuple(data.get("budget_refs", [])),
            validation_refs=tuple(data.get("validation_refs", [])),
            outcome_refs=tuple(data.get("outcome_refs", [])),
            timestamp=datetime.fromisoformat(data["timestamp"])
            if isinstance(data.get("timestamp"), str)
            else data.get("timestamp", _utcnow()),
            metadata=dict(data.get("metadata", {})),
        )


# ── AgentTracePlanReference ────────────────────────────────────────────────────


@dataclass(frozen=True)
class AgentTracePlanReference:
    """Reference to a plan created during execution."""

    plan_id: str
    plan_status: str = ""
    operation_count: int = 0
    summary: str = ""
    timestamp: datetime = field(default_factory=_utcnow)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "plan_status": self.plan_status,
            "operation_count": self.operation_count,
            "summary": self.summary,
            "timestamp": self.timestamp.isoformat(),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentTracePlanReference:
        return cls(
            plan_id=str(data["plan_id"]),
            plan_status=str(data.get("plan_status", "")),
            operation_count=int(data.get("operation_count", 0)),
            summary=str(data.get("summary", "")),
            timestamp=datetime.fromisoformat(data["timestamp"])
            if isinstance(data.get("timestamp"), str)
            else data.get("timestamp", _utcnow()),
            metadata=dict(data.get("metadata", {})),
        )


# ── AgentTracePolicyDecision ───────────────────────────────────────────────────


@dataclass(frozen=True)
class AgentTracePolicyDecision:
    """Trace record for a policy evaluation decision."""

    policy_decision_id: str
    decision: str = ""
    policy_refs: tuple[str, ...] = field(default_factory=tuple)
    obligations: tuple[str, ...] = field(default_factory=tuple)
    summary: str = ""
    timestamp: datetime = field(default_factory=_utcnow)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "policy_decision_id": self.policy_decision_id,
            "decision": self.decision,
            "policy_refs": list(self.policy_refs),
            "obligations": list(self.obligations),
            "summary": self.summary,
            "timestamp": self.timestamp.isoformat(),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentTracePolicyDecision:
        return cls(
            policy_decision_id=str(data["policy_decision_id"]),
            decision=str(data.get("decision", "")),
            policy_refs=tuple(data.get("policy_refs", [])),
            obligations=tuple(data.get("obligations", [])),
            summary=str(data.get("summary", "")),
            timestamp=datetime.fromisoformat(data["timestamp"])
            if isinstance(data.get("timestamp"), str)
            else data.get("timestamp", _utcnow()),
            metadata=dict(data.get("metadata", {})),
        )


# ── AgentTraceApprovalRequest ──────────────────────────────────────────────────


@dataclass(frozen=True)
class AgentTraceApprovalRequest:
    """Trace record for an approval request."""

    approval_request_id: str
    requested_by: str = ""
    required_approvers: tuple[str, ...] = field(default_factory=tuple)
    status: str = ""
    summary: str = ""
    timestamp: datetime = field(default_factory=_utcnow)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "approval_request_id": self.approval_request_id,
            "requested_by": self.requested_by,
            "required_approvers": list(self.required_approvers),
            "status": self.status,
            "summary": self.summary,
            "timestamp": self.timestamp.isoformat(),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentTraceApprovalRequest:
        return cls(
            approval_request_id=str(data["approval_request_id"]),
            requested_by=str(data.get("requested_by", "")),
            required_approvers=tuple(data.get("required_approvers", [])),
            status=str(data.get("status", "")),
            summary=str(data.get("summary", "")),
            timestamp=datetime.fromisoformat(data["timestamp"])
            if isinstance(data.get("timestamp"), str)
            else data.get("timestamp", _utcnow()),
            metadata=dict(data.get("metadata", {})),
        )


# ── AgentTraceApprovalDecision ─────────────────────────────────────────────────


@dataclass(frozen=True)
class AgentTraceApprovalDecision:
    """Trace record for an approval decision."""

    approval_decision_id: str
    approval_request_id: str = ""
    decided_by: str = ""
    decision: str = ""
    summary: str = ""
    timestamp: datetime = field(default_factory=_utcnow)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "approval_decision_id": self.approval_decision_id,
            "approval_request_id": self.approval_request_id,
            "decided_by": self.decided_by,
            "decision": self.decision,
            "summary": self.summary,
            "timestamp": self.timestamp.isoformat(),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentTraceApprovalDecision:
        return cls(
            approval_decision_id=str(data["approval_decision_id"]),
            approval_request_id=str(data.get("approval_request_id", "")),
            decided_by=str(data.get("decided_by", "")),
            decision=str(data.get("decision", "")),
            summary=str(data.get("summary", "")),
            timestamp=datetime.fromisoformat(data["timestamp"])
            if isinstance(data.get("timestamp"), str)
            else data.get("timestamp", _utcnow()),
            metadata=dict(data.get("metadata", {})),
        )


# ── AgentTraceOperation ────────────────────────────────────────────────────────


@dataclass(frozen=True)
class AgentTraceOperation:
    """Trace record for an operation executed."""

    operation_id: str
    operation_name: str = ""
    status: str = ""
    effect: str = ""
    summary: str = ""
    timestamp: datetime = field(default_factory=_utcnow)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "operation_id": self.operation_id,
            "operation_name": self.operation_name,
            "status": self.status,
            "effect": self.effect,
            "summary": self.summary,
            "timestamp": self.timestamp.isoformat(),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentTraceOperation:
        return cls(
            operation_id=str(data["operation_id"]),
            operation_name=str(data.get("operation_name", "")),
            status=str(data.get("status", "")),
            effect=str(data.get("effect", "")),
            summary=str(data.get("summary", "")),
            timestamp=datetime.fromisoformat(data["timestamp"])
            if isinstance(data.get("timestamp"), str)
            else data.get("timestamp", _utcnow()),
            metadata=dict(data.get("metadata", {})),
        )


# ── AgentTraceResourceChange ───────────────────────────────────────────────────


@dataclass(frozen=True)
class AgentTraceResourceChange:
    """Trace record for a resource modification."""

    change_id: str
    resource: str = ""
    change_kind: str = ""
    summary: str = ""
    timestamp: datetime = field(default_factory=_utcnow)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "change_id": self.change_id,
            "resource": self.resource,
            "change_kind": self.change_kind,
            "summary": self.summary,
            "timestamp": self.timestamp.isoformat(),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentTraceResourceChange:
        return cls(
            change_id=str(data["change_id"]),
            resource=str(data.get("resource", "")),
            change_kind=str(data.get("change_kind", "")),
            summary=str(data.get("summary", "")),
            timestamp=datetime.fromisoformat(data["timestamp"])
            if isinstance(data.get("timestamp"), str)
            else data.get("timestamp", _utcnow()),
            metadata=dict(data.get("metadata", {})),
        )


# ── AgentTraceValidation ───────────────────────────────────────────────────────


@dataclass(frozen=True)
class AgentTraceValidation:
    """Trace record for a validation performed."""

    validation_id: str
    stage: str = ""
    status: str = ""
    findings_count: int = 0
    summary: str = ""
    timestamp: datetime = field(default_factory=_utcnow)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "validation_id": self.validation_id,
            "stage": self.stage,
            "status": self.status,
            "findings_count": self.findings_count,
            "summary": self.summary,
            "timestamp": self.timestamp.isoformat(),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentTraceValidation:
        return cls(
            validation_id=str(data["validation_id"]),
            stage=str(data.get("stage", "")),
            status=str(data.get("status", "")),
            findings_count=int(data.get("findings_count", 0)),
            summary=str(data.get("summary", "")),
            timestamp=datetime.fromisoformat(data["timestamp"])
            if isinstance(data.get("timestamp"), str)
            else data.get("timestamp", _utcnow()),
            metadata=dict(data.get("metadata", {})),
        )


# ── AgentTraceRecoveryDecision ─────────────────────────────────────────────────


@dataclass(frozen=True)
class AgentTraceRecoveryDecision:
    """Trace record for a recovery decision."""

    recovery_decision_id: str
    strategy: str = ""
    reason_codes: tuple[str, ...] = field(default_factory=tuple)
    retry_count: int = 0
    summary: str = ""
    timestamp: datetime = field(default_factory=_utcnow)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "recovery_decision_id": self.recovery_decision_id,
            "strategy": self.strategy,
            "reason_codes": list(self.reason_codes),
            "retry_count": self.retry_count,
            "summary": self.summary,
            "timestamp": self.timestamp.isoformat(),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentTraceRecoveryDecision:
        return cls(
            recovery_decision_id=str(data["recovery_decision_id"]),
            strategy=str(data.get("strategy", "")),
            reason_codes=tuple(data.get("reason_codes", [])),
            retry_count=int(data.get("retry_count", 0)),
            summary=str(data.get("summary", "")),
            timestamp=datetime.fromisoformat(data["timestamp"])
            if isinstance(data.get("timestamp"), str)
            else data.get("timestamp", _utcnow()),
            metadata=dict(data.get("metadata", {})),
        )


# ── AgentTraceRecoveryExecution ────────────────────────────────────────────────


@dataclass(frozen=True)
class AgentTraceRecoveryExecution:
    """Trace record for a recovery execution."""

    recovery_execution_id: str
    strategy: str = ""
    status: str = ""
    summary: str = ""
    timestamp: datetime = field(default_factory=_utcnow)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "recovery_execution_id": self.recovery_execution_id,
            "strategy": self.strategy,
            "status": self.status,
            "summary": self.summary,
            "timestamp": self.timestamp.isoformat(),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentTraceRecoveryExecution:
        return cls(
            recovery_execution_id=str(data["recovery_execution_id"]),
            strategy=str(data.get("strategy", "")),
            status=str(data.get("status", "")),
            summary=str(data.get("summary", "")),
            timestamp=datetime.fromisoformat(data["timestamp"])
            if isinstance(data.get("timestamp"), str)
            else data.get("timestamp", _utcnow()),
            metadata=dict(data.get("metadata", {})),
        )


# ── AgentTraceCheckpoint ───────────────────────────────────────────────────────


@dataclass(frozen=True)
class AgentTraceCheckpoint:
    """Trace record for a checkpoint."""

    checkpoint_id: str
    status: str = ""
    integrity_status: str = ""
    summary: str = ""
    timestamp: datetime = field(default_factory=_utcnow)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "checkpoint_id": self.checkpoint_id,
            "status": self.status,
            "integrity_status": self.integrity_status,
            "summary": self.summary,
            "timestamp": self.timestamp.isoformat(),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentTraceCheckpoint:
        return cls(
            checkpoint_id=str(data["checkpoint_id"]),
            status=str(data.get("status", "")),
            integrity_status=str(data.get("integrity_status", "")),
            summary=str(data.get("summary", "")),
            timestamp=datetime.fromisoformat(data["timestamp"])
            if isinstance(data.get("timestamp"), str)
            else data.get("timestamp", _utcnow()),
            metadata=dict(data.get("metadata", {})),
        )


# ── AgentTraceTransaction ──────────────────────────────────────────────────────


@dataclass(frozen=True)
class AgentTraceTransaction:
    """Trace record for a transaction boundary."""

    transaction_id: str
    boundary_kind: str = ""
    status: str = ""
    summary: str = ""
    timestamp: datetime = field(default_factory=_utcnow)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "transaction_id": self.transaction_id,
            "boundary_kind": self.boundary_kind,
            "status": self.status,
            "summary": self.summary,
            "timestamp": self.timestamp.isoformat(),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentTraceTransaction:
        return cls(
            transaction_id=str(data["transaction_id"]),
            boundary_kind=str(data.get("boundary_kind", "")),
            status=str(data.get("status", "")),
            summary=str(data.get("summary", "")),
            timestamp=datetime.fromisoformat(data["timestamp"])
            if isinstance(data.get("timestamp"), str)
            else data.get("timestamp", _utcnow()),
            metadata=dict(data.get("metadata", {})),
        )


# ── AgentTraceOutcomeEvaluation ────────────────────────────────────────────────


@dataclass(frozen=True)
class AgentTraceOutcomeEvaluation:
    """Trace record for an outcome evaluation."""

    evaluation_id: str
    outcome: str = ""
    completion_decision: str = ""
    criteria_satisfied: int = 0
    criteria_total: int = 0
    regressions: int = 0
    warnings: int = 0
    summary: str = ""
    timestamp: datetime = field(default_factory=_utcnow)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "evaluation_id": self.evaluation_id,
            "outcome": self.outcome,
            "completion_decision": self.completion_decision,
            "criteria_satisfied": self.criteria_satisfied,
            "criteria_total": self.criteria_total,
            "regressions": self.regressions,
            "warnings": self.warnings,
            "summary": self.summary,
            "timestamp": self.timestamp.isoformat(),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentTraceOutcomeEvaluation:
        return cls(
            evaluation_id=str(data["evaluation_id"]),
            outcome=str(data.get("outcome", "")),
            completion_decision=str(data.get("completion_decision", "")),
            criteria_satisfied=int(data.get("criteria_satisfied", 0)),
            criteria_total=int(data.get("criteria_total", 0)),
            regressions=int(data.get("regressions", 0)),
            warnings=int(data.get("warnings", 0)),
            summary=str(data.get("summary", "")),
            timestamp=datetime.fromisoformat(data["timestamp"])
            if isinstance(data.get("timestamp"), str)
            else data.get("timestamp", _utcnow()),
            metadata=dict(data.get("metadata", {})),
        )


# ── AgentTraceKnowledgeUpdate ──────────────────────────────────────────────────


@dataclass(frozen=True)
class AgentTraceKnowledgeUpdate:
    """Trace record for a knowledge update."""

    proposal_id: str
    status: str = ""
    additions: int = 0
    updates: int = 0
    invalidations: int = 0
    merges: int = 0
    rejections: int = 0
    summary: str = ""
    timestamp: datetime = field(default_factory=_utcnow)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "proposal_id": self.proposal_id,
            "status": self.status,
            "additions": self.additions,
            "updates": self.updates,
            "invalidations": self.invalidations,
            "merges": self.merges,
            "rejections": self.rejections,
            "summary": self.summary,
            "timestamp": self.timestamp.isoformat(),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentTraceKnowledgeUpdate:
        return cls(
            proposal_id=str(data["proposal_id"]),
            status=str(data.get("status", "")),
            additions=int(data.get("additions", 0)),
            updates=int(data.get("updates", 0)),
            invalidations=int(data.get("invalidations", 0)),
            merges=int(data.get("merges", 0)),
            rejections=int(data.get("rejections", 0)),
            summary=str(data.get("summary", "")),
            timestamp=datetime.fromisoformat(data["timestamp"])
            if isinstance(data.get("timestamp"), str)
            else data.get("timestamp", _utcnow()),
            metadata=dict(data.get("metadata", {})),
        )


# ── AgentTraceMemoryUpdate ─────────────────────────────────────────────────────


@dataclass(frozen=True)
class AgentTraceMemoryUpdate:
    """Trace record for a memory update."""

    memory_update_id: str
    decision: str = ""
    candidates_count: int = 0
    written_count: int = 0
    summary: str = ""
    timestamp: datetime = field(default_factory=_utcnow)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "memory_update_id": self.memory_update_id,
            "decision": self.decision,
            "candidates_count": self.candidates_count,
            "written_count": self.written_count,
            "summary": self.summary,
            "timestamp": self.timestamp.isoformat(),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentTraceMemoryUpdate:
        return cls(
            memory_update_id=str(data["memory_update_id"]),
            decision=str(data.get("decision", "")),
            candidates_count=int(data.get("candidates_count", 0)),
            written_count=int(data.get("written_count", 0)),
            summary=str(data.get("summary", "")),
            timestamp=datetime.fromisoformat(data["timestamp"])
            if isinstance(data.get("timestamp"), str)
            else data.get("timestamp", _utcnow()),
            metadata=dict(data.get("metadata", {})),
        )


# ── AgentTraceBudgetEvent ──────────────────────────────────────────────────────


@dataclass(frozen=True)
class AgentTraceBudgetEvent:
    """Trace record for a budget event."""

    budget_event_id: str
    event_kind: str = ""
    resource_type: str = ""
    amount: float = 0.0
    remaining: float = 0.0
    summary: str = ""
    timestamp: datetime = field(default_factory=_utcnow)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "budget_event_id": self.budget_event_id,
            "event_kind": self.event_kind,
            "resource_type": self.resource_type,
            "amount": self.amount,
            "remaining": self.remaining,
            "summary": self.summary,
            "timestamp": self.timestamp.isoformat(),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentTraceBudgetEvent:
        return cls(
            budget_event_id=str(data["budget_event_id"]),
            event_kind=str(data.get("event_kind", "")),
            resource_type=str(data.get("resource_type", "")),
            amount=float(data.get("amount", 0.0)),
            remaining=float(data.get("remaining", 0.0)),
            summary=str(data.get("summary", "")),
            timestamp=datetime.fromisoformat(data["timestamp"])
            if isinstance(data.get("timestamp"), str)
            else data.get("timestamp", _utcnow()),
            metadata=dict(data.get("metadata", {})),
        )


# ── AgentTraceWarning ──────────────────────────────────────────────────────────


@dataclass(frozen=True)
class AgentTraceWarning:
    """Trace record for a warning."""

    warning_id: str
    message: str = ""
    source: str = ""
    code: str = ""
    timestamp: datetime = field(default_factory=_utcnow)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "warning_id": self.warning_id,
            "message": self.message,
            "source": self.source,
            "code": self.code,
            "timestamp": self.timestamp.isoformat(),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentTraceWarning:
        return cls(
            warning_id=str(data["warning_id"]),
            message=str(data.get("message", "")),
            source=str(data.get("source", "")),
            code=str(data.get("code", "")),
            timestamp=datetime.fromisoformat(data["timestamp"])
            if isinstance(data.get("timestamp"), str)
            else data.get("timestamp", _utcnow()),
            metadata=dict(data.get("metadata", {})),
        )


# ── AgentTraceError ────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class AgentTraceError:
    """Trace record for a safe error (no traceback, no secrets)."""

    error_id: str
    kind: str = ""
    safe_message: str = ""
    error_code: str = ""
    operation_id: str = ""
    validation_id: str = ""
    recovery_id: str = ""
    retryable: bool = False
    resolved: bool = False
    resolution_ref: str = ""
    timestamp: datetime = field(default_factory=_utcnow)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "error_id": self.error_id,
            "kind": self.kind,
            "safe_message": self.safe_message,
            "error_code": self.error_code,
            "operation_id": self.operation_id,
            "validation_id": self.validation_id,
            "recovery_id": self.recovery_id,
            "retryable": self.retryable,
            "resolved": self.resolved,
            "resolution_ref": self.resolution_ref,
            "timestamp": self.timestamp.isoformat(),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentTraceError:
        return cls(
            error_id=str(data["error_id"]),
            kind=str(data.get("kind", "")),
            safe_message=str(data.get("safe_message", "")),
            error_code=str(data.get("error_code", "")),
            operation_id=str(data.get("operation_id", "")),
            validation_id=str(data.get("validation_id", "")),
            recovery_id=str(data.get("recovery_id", "")),
            retryable=bool(data.get("retryable", False)),
            resolved=bool(data.get("resolved", False)),
            resolution_ref=str(data.get("resolution_ref", "")),
            timestamp=datetime.fromisoformat(data["timestamp"])
            if isinstance(data.get("timestamp"), str)
            else data.get("timestamp", _utcnow()),
            metadata=dict(data.get("metadata", {})),
        )


# ── AgentTraceStopDecision ─────────────────────────────────────────────────────


@dataclass(frozen=True)
class AgentTraceStopDecision:
    """Trace record for the final stop decision."""

    stop_decision_id: str
    reason_codes: tuple[str, ...] = field(default_factory=tuple)
    goal_satisfied: bool = False
    outcome: str = ""
    completion_decision: str = ""
    summary: str = ""
    timestamp: datetime = field(default_factory=_utcnow)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "stop_decision_id": self.stop_decision_id,
            "reason_codes": list(self.reason_codes),
            "goal_satisfied": self.goal_satisfied,
            "outcome": self.outcome,
            "completion_decision": self.completion_decision,
            "summary": self.summary,
            "timestamp": self.timestamp.isoformat(),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentTraceStopDecision:
        return cls(
            stop_decision_id=str(data["stop_decision_id"]),
            reason_codes=tuple(data.get("reason_codes", [])),
            goal_satisfied=bool(data.get("goal_satisfied", False)),
            outcome=str(data.get("outcome", "")),
            completion_decision=str(data.get("completion_decision", "")),
            summary=str(data.get("summary", "")),
            timestamp=datetime.fromisoformat(data["timestamp"])
            if isinstance(data.get("timestamp"), str)
            else data.get("timestamp", _utcnow()),
            metadata=dict(data.get("metadata", {})),
        )


# ── AgentTraceSummary ──────────────────────────────────────────────────────────


@dataclass(frozen=True)
class AgentTraceSummary:
    """Structured summary of an agent trace (no reasoning narrative)."""

    goal_status: str = ""
    outcome: str = ""
    completion_decision: str = ""
    operation_count: int = 0
    validation_count: int = 0
    retry_count: int = 0
    rollback_count: int = 0
    replan_count: int = 0
    budget_consumed: dict[str, float] = field(default_factory=dict)
    modified_resources: tuple[str, ...] = field(default_factory=tuple)
    warnings: tuple[str, ...] = field(default_factory=tuple)
    stop_reason_codes: tuple[str, ...] = field(default_factory=tuple)
    goal_satisfied: bool = False
    knowledge_updates: int = 0
    memory_updates: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "goal_status": self.goal_status,
            "outcome": self.outcome,
            "completion_decision": self.completion_decision,
            "operation_count": self.operation_count,
            "validation_count": self.validation_count,
            "retry_count": self.retry_count,
            "rollback_count": self.rollback_count,
            "replan_count": self.replan_count,
            "budget_consumed": dict(self.budget_consumed),
            "modified_resources": list(self.modified_resources),
            "warnings": list(self.warnings),
            "stop_reason_codes": list(self.stop_reason_codes),
            "goal_satisfied": self.goal_satisfied,
            "knowledge_updates": self.knowledge_updates,
            "memory_updates": self.memory_updates,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentTraceSummary:
        return cls(
            goal_status=str(data.get("goal_status", "")),
            outcome=str(data.get("outcome", "")),
            completion_decision=str(data.get("completion_decision", "")),
            operation_count=int(data.get("operation_count", 0)),
            validation_count=int(data.get("validation_count", 0)),
            retry_count=int(data.get("retry_count", 0)),
            rollback_count=int(data.get("rollback_count", 0)),
            replan_count=int(data.get("replan_count", 0)),
            budget_consumed=dict(data.get("budget_consumed", {})),
            modified_resources=tuple(data.get("modified_resources", [])),
            warnings=tuple(data.get("warnings", [])),
            stop_reason_codes=tuple(data.get("stop_reason_codes", [])),
            goal_satisfied=bool(data.get("goal_satisfied", False)),
            knowledge_updates=int(data.get("knowledge_updates", 0)),
            memory_updates=int(data.get("memory_updates", 0)),
            metadata=dict(data.get("metadata", {})),
        )


# ── AgentTraceQuery ────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class AgentTraceQuery:
    """Query parameters for trace retrieval."""

    filters: dict[str, Any] = field(default_factory=dict)
    limit: int = 100
    cursor: str = ""
    sort: str = "started_at"
    include_summary: bool = True
    include_records: bool = False
    permission_context: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.limit < 1:
            raise ValueError("limit must be >= 1")
        if self.limit > 10000:
            raise ValueError("limit must be <= 10000")


@dataclass(frozen=True)
class AgentTraceQueryResult:
    """Result of a trace query."""

    traces: tuple[AgentTrace, ...] = field(default_factory=tuple)
    total: int = 0
    next_cursor: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


# ── AgentTracePage ─────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class AgentTracePage:
    """A page of trace results for paginated queries."""

    items: tuple[AgentTrace, ...] = field(default_factory=tuple)
    total: int = 0
    page: int = 1
    page_size: int = 100
    has_next: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


# ── AgentTraceIntegrityReport ──────────────────────────────────────────────────


@dataclass(frozen=True)
class AgentTraceIntegrityReport:
    """Report of integrity verification results."""

    trace_id: str = ""
    status: str = ""
    issues: tuple[str, ...] = field(default_factory=tuple)
    missing_events: tuple[str, ...] = field(default_factory=tuple)
    duplicate_events: tuple[str, ...] = field(default_factory=tuple)
    ordering_errors: tuple[str, ...] = field(default_factory=tuple)
    causality_errors: tuple[str, ...] = field(default_factory=tuple)
    fingerprint_valid: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "status": self.status,
            "issues": list(self.issues),
            "missing_events": list(self.missing_events),
            "duplicate_events": list(self.duplicate_events),
            "ordering_errors": list(self.ordering_errors),
            "causality_errors": list(self.causality_errors),
            "fingerprint_valid": self.fingerprint_valid,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentTraceIntegrityReport:
        return cls(
            trace_id=str(data.get("trace_id", "")),
            status=str(data.get("status", "")),
            issues=tuple(data.get("issues", [])),
            missing_events=tuple(data.get("missing_events", [])),
            duplicate_events=tuple(data.get("duplicate_events", [])),
            ordering_errors=tuple(data.get("ordering_errors", [])),
            causality_errors=tuple(data.get("causality_errors", [])),
            fingerprint_valid=bool(data.get("fingerprint_valid", True)),
            metadata=dict(data.get("metadata", {})),
        )


# ── AgentTraceRedactionReport ──────────────────────────────────────────────────


@dataclass(frozen=True)
class AgentTraceRedactionReport:
    """Report of redaction applied to a trace."""

    trace_id: str = ""
    redacted_fields: tuple[str, ...] = field(default_factory=tuple)
    dropped_fields: tuple[str, ...] = field(default_factory=tuple)
    reason_codes: tuple[str, ...] = field(default_factory=tuple)
    retained_references: tuple[str, ...] = field(default_factory=tuple)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "redacted_fields": list(self.redacted_fields),
            "dropped_fields": list(self.dropped_fields),
            "reason_codes": list(self.reason_codes),
            "retained_references": list(self.retained_references),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentTraceRedactionReport:
        return cls(
            trace_id=str(data.get("trace_id", "")),
            redacted_fields=tuple(data.get("redacted_fields", [])),
            dropped_fields=tuple(data.get("dropped_fields", [])),
            reason_codes=tuple(data.get("reason_codes", [])),
            retained_references=tuple(data.get("retained_references", [])),
            metadata=dict(data.get("metadata", {})),
        )


# ── AgentTraceRetentionPolicy ──────────────────────────────────────────────────


@dataclass(frozen=True)
class AgentTraceRetentionPolicy:
    """Retention policy for trace archival and expiration."""

    max_age_days: int = 365
    archive_after_days: int = 90
    important_statuses: tuple[str, ...] = ("failed", "corrupted", "partial")
    incident_retention_days: int = 730
    min_free_space_percent: float = 10.0
    metadata: dict[str, Any] = field(default_factory=dict)


# ── AgentTraceExportRequest ────────────────────────────────────────────────────


@dataclass(frozen=True)
class AgentTraceExportRequest:
    """Request to export a trace."""

    trace_id: str = ""
    format: str = "json"
    include_summary: bool = True
    include_records: bool = False
    redact: bool = True
    permission_context: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AgentTraceExportResult:
    """Result of a trace export."""

    trace_id: str = ""
    format: str = "json"
    data: str = ""
    schema_version: str = "1.0"
    fingerprint: str = ""
    export_timestamp: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


# ── AgentTrace (root aggregate) ────────────────────────────────────────────────


@dataclass(frozen=True)
class AgentTrace:
    """Root aggregate for an agent runtime trace.

    Composed entirely of structured facts, references, and safe summaries.
    No chain-of-thought, no private prompts, no secrets, no stack traces.
    """

    trace_id: str
    agent_run_id: str
    goal_id: str
    goal_created_by: str = ""
    agent_id: str = ""
    workflow_id: str = ""
    autonomy_level: AgentAutonomyLevel | int = AgentAutonomyLevel.ANALYZE_ONLY
    status: str = "open"
    iterations: tuple[AgentTraceIteration, ...] = field(default_factory=tuple)
    observations: tuple[AgentTraceObservation, ...] = field(default_factory=tuple)
    knowledge_loads: tuple[AgentTraceKnowledgeLoad, ...] = field(default_factory=tuple)
    cognitive_profiles: tuple[AgentTraceCognitiveProfile, ...] = field(
        default_factory=tuple
    )
    information_gaps: tuple[AgentTraceInformationGap, ...] = field(
        default_factory=tuple
    )
    questions: tuple[AgentTraceQuestion, ...] = field(default_factory=tuple)
    reasoning_result_ids: tuple[str, ...] = field(default_factory=tuple)
    runtime_decisions: tuple[AgentTraceRuntimeDecision, ...] = field(
        default_factory=tuple
    )
    plans: tuple[AgentTracePlanReference, ...] = field(default_factory=tuple)
    policy_decisions: tuple[AgentTracePolicyDecision, ...] = field(
        default_factory=tuple
    )
    approval_requests: tuple[AgentTraceApprovalRequest, ...] = field(
        default_factory=tuple
    )
    approval_decisions: tuple[AgentTraceApprovalDecision, ...] = field(
        default_factory=tuple
    )
    operations: tuple[AgentTraceOperation, ...] = field(default_factory=tuple)
    resource_changes: tuple[AgentTraceResourceChange, ...] = field(
        default_factory=tuple
    )
    validations: tuple[AgentTraceValidation, ...] = field(default_factory=tuple)
    recovery_decisions: tuple[AgentTraceRecoveryDecision, ...] = field(
        default_factory=tuple
    )
    recovery_executions: tuple[AgentTraceRecoveryExecution, ...] = field(
        default_factory=tuple
    )
    checkpoints: tuple[AgentTraceCheckpoint, ...] = field(default_factory=tuple)
    transactions: tuple[AgentTraceTransaction, ...] = field(default_factory=tuple)
    outcome_evaluations: tuple[AgentTraceOutcomeEvaluation, ...] = field(
        default_factory=tuple
    )
    knowledge_updates: tuple[AgentTraceKnowledgeUpdate, ...] = field(
        default_factory=tuple
    )
    memory_updates: tuple[AgentTraceMemoryUpdate, ...] = field(default_factory=tuple)
    budget_events: tuple[AgentTraceBudgetEvent, ...] = field(default_factory=tuple)
    warnings: tuple[AgentTraceWarning, ...] = field(default_factory=tuple)
    errors: tuple[AgentTraceError, ...] = field(default_factory=tuple)
    stop_decision: AgentTraceStopDecision | None = None
    summary: AgentTraceSummary | None = None
    started_at: datetime = field(default_factory=_utcnow)
    completed_at: datetime | None = None
    duration_ms: int | None = None
    event_count: int = 0
    source_event_ids: tuple[str, ...] = field(default_factory=tuple)
    correlation_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    fingerprint: str = ""

    def __post_init__(self) -> None:
        if not self.trace_id or not isinstance(self.trace_id, str):
            raise ValueError("trace_id must be a non-empty string")
        if not self.agent_run_id or not isinstance(self.agent_run_id, str):
            raise ValueError("agent_run_id must be a non-empty string")
        if not self.goal_id or not isinstance(self.goal_id, str):
            raise ValueError("goal_id must be a non-empty string")
        if self.completed_at is not None and self.started_at > self.completed_at:
            raise ValueError("completed_at must not be before started_at")
        if self.duration_ms is not None and self.duration_ms < 0:
            raise ValueError("duration_ms must not be negative")

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "trace_id": self.trace_id,
            "agent_run_id": self.agent_run_id,
            "goal_id": self.goal_id,
            "goal_created_by": self.goal_created_by,
            "agent_id": self.agent_id,
            "workflow_id": self.workflow_id,
            "autonomy_level": int(self.autonomy_level)
            if isinstance(self.autonomy_level, AgentAutonomyLevel)
            else self.autonomy_level,
            "status": self.status,
            "iterations": [i.to_dict() for i in self.iterations],
            "observations": [o.to_dict() for o in self.observations],
            "knowledge_loads": [k.to_dict() for k in self.knowledge_loads],
            "cognitive_profiles": [c.to_dict() for c in self.cognitive_profiles],
            "information_gaps": [g.to_dict() for g in self.information_gaps],
            "questions": [q.to_dict() for q in self.questions],
            "reasoning_result_ids": list(self.reasoning_result_ids),
            "runtime_decisions": [d_.to_dict() for d_ in self.runtime_decisions],
            "plans": [p.to_dict() for p in self.plans],
            "policy_decisions": [p.to_dict() for p in self.policy_decisions],
            "approval_requests": [a.to_dict() for a in self.approval_requests],
            "approval_decisions": [a.to_dict() for a in self.approval_decisions],
            "operations": [o.to_dict() for o in self.operations],
            "resource_changes": [r.to_dict() for r in self.resource_changes],
            "validations": [v.to_dict() for v in self.validations],
            "recovery_decisions": [r.to_dict() for r in self.recovery_decisions],
            "recovery_executions": [r.to_dict() for r in self.recovery_executions],
            "checkpoints": [c.to_dict() for c in self.checkpoints],
            "transactions": [t.to_dict() for t in self.transactions],
            "outcome_evaluations": [e.to_dict() for e in self.outcome_evaluations],
            "knowledge_updates": [k.to_dict() for k in self.knowledge_updates],
            "memory_updates": [m.to_dict() for m in self.memory_updates],
            "budget_events": [b.to_dict() for b in self.budget_events],
            "warnings": [w.to_dict() for w in self.warnings],
            "errors": [e.to_dict() for e in self.errors],
            "stop_decision": self.stop_decision.to_dict()
            if self.stop_decision
            else None,
            "summary": self.summary.to_dict() if self.summary else None,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat()
            if self.completed_at
            else None,
            "duration_ms": self.duration_ms,
            "event_count": self.event_count,
            "source_event_ids": list(self.source_event_ids),
            "correlation_id": self.correlation_id,
            "metadata": dict(self.metadata),
            "fingerprint": self.fingerprint,
        }
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentTrace:
        return cls(
            trace_id=str(data["trace_id"]),
            agent_run_id=str(data["agent_run_id"]),
            goal_id=str(data["goal_id"]),
            goal_created_by=str(data.get("goal_created_by", "")),
            agent_id=str(data.get("agent_id", "")),
            workflow_id=str(data.get("workflow_id", "")),
            autonomy_level=data.get("autonomy_level", AgentAutonomyLevel.ANALYZE_ONLY),
            status=str(data.get("status", "open")),
            iterations=tuple(
                AgentTraceIteration.from_dict(i) for i in data.get("iterations", [])
            ),
            observations=tuple(
                AgentTraceObservation.from_dict(o) for o in data.get("observations", [])
            ),
            knowledge_loads=tuple(
                AgentTraceKnowledgeLoad.from_dict(k)
                for k in data.get("knowledge_loads", [])
            ),
            cognitive_profiles=tuple(
                AgentTraceCognitiveProfile.from_dict(c)
                for c in data.get("cognitive_profiles", [])
            ),
            information_gaps=tuple(
                AgentTraceInformationGap.from_dict(g)
                for g in data.get("information_gaps", [])
            ),
            questions=tuple(
                AgentTraceQuestion.from_dict(q) for q in data.get("questions", [])
            ),
            reasoning_result_ids=tuple(data.get("reasoning_result_ids", [])),
            runtime_decisions=tuple(
                AgentTraceRuntimeDecision.from_dict(d_)
                for d_ in data.get("runtime_decisions", [])
            ),
            plans=tuple(
                AgentTracePlanReference.from_dict(p) for p in data.get("plans", [])
            ),
            policy_decisions=tuple(
                AgentTracePolicyDecision.from_dict(p)
                for p in data.get("policy_decisions", [])
            ),
            approval_requests=tuple(
                AgentTraceApprovalRequest.from_dict(a)
                for a in data.get("approval_requests", [])
            ),
            approval_decisions=tuple(
                AgentTraceApprovalDecision.from_dict(a)
                for a in data.get("approval_decisions", [])
            ),
            operations=tuple(
                AgentTraceOperation.from_dict(o) for o in data.get("operations", [])
            ),
            resource_changes=tuple(
                AgentTraceResourceChange.from_dict(r)
                for r in data.get("resource_changes", [])
            ),
            validations=tuple(
                AgentTraceValidation.from_dict(v) for v in data.get("validations", [])
            ),
            recovery_decisions=tuple(
                AgentTraceRecoveryDecision.from_dict(r)
                for r in data.get("recovery_decisions", [])
            ),
            recovery_executions=tuple(
                AgentTraceRecoveryExecution.from_dict(r)
                for r in data.get("recovery_executions", [])
            ),
            checkpoints=tuple(
                AgentTraceCheckpoint.from_dict(c) for c in data.get("checkpoints", [])
            ),
            transactions=tuple(
                AgentTraceTransaction.from_dict(t) for t in data.get("transactions", [])
            ),
            outcome_evaluations=tuple(
                AgentTraceOutcomeEvaluation.from_dict(e)
                for e in data.get("outcome_evaluations", [])
            ),
            knowledge_updates=tuple(
                AgentTraceKnowledgeUpdate.from_dict(k)
                for k in data.get("knowledge_updates", [])
            ),
            memory_updates=tuple(
                AgentTraceMemoryUpdate.from_dict(m)
                for m in data.get("memory_updates", [])
            ),
            budget_events=tuple(
                AgentTraceBudgetEvent.from_dict(b)
                for b in data.get("budget_events", [])
            ),
            warnings=tuple(
                AgentTraceWarning.from_dict(w) for w in data.get("warnings", [])
            ),
            errors=tuple(AgentTraceError.from_dict(e) for e in data.get("errors", [])),
            stop_decision=AgentTraceStopDecision.from_dict(data["stop_decision"])
            if data.get("stop_decision")
            else None,
            summary=AgentTraceSummary.from_dict(data["summary"])
            if data.get("summary")
            else None,
            started_at=datetime.fromisoformat(data["started_at"])
            if isinstance(data.get("started_at"), str)
            else data.get("started_at", _utcnow()),
            completed_at=datetime.fromisoformat(data["completed_at"])
            if isinstance(data.get("completed_at"), str)
            else data.get("completed_at"),
            duration_ms=data.get("duration_ms"),
            event_count=int(data.get("event_count", 0)),
            source_event_ids=tuple(data.get("source_event_ids", [])),
            correlation_id=str(data.get("correlation_id", "")),
            metadata=dict(data.get("metadata", {})),
            fingerprint=str(data.get("fingerprint", "")),
        )

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str, ensure_ascii=False)

    @classmethod
    def from_json(cls, data: str) -> AgentTrace:
        return cls.from_dict(json.loads(data))
