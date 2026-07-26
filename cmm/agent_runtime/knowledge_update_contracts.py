"""Phase 9.18 – Knowledge and Memory Update Contracts.

Defines immutable, serializable, timezone-aware data structures for proposing,
evaluating, filtering, and executing safe updates to knowledge and memory stores.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from cmm.agent_runtime.enums import (
    KnowledgeCandidateKind,
    KnowledgeProposalStatus,
    KnowledgeRejectionReason,
    KnowledgeSensitivityLevel,
    KnowledgeWriteDecisionKind,
    MemoryWriteDecisionKind,
    OperationalLessonKind,
)
from cmm.agent_runtime.errors import InvalidAgentContractError


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _compute_fingerprint(payload: dict[str, Any]) -> str:
    """Helper to compute deterministic SHA256 fingerprint for contract dataclasses."""
    try:
        serialized = json.dumps(payload, sort_keys=True, default=str)
    except Exception as exc:
        raise InvalidAgentContractError(
            f"Failed to serialize payload for fingerprint computation: {exc}"
        ) from exc
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class KnowledgeProvenance:
    """Provenance metadata tracing source run, goal, and evidence for knowledge items."""

    source_run_id: str
    source_goal_id: str
    workflow_id: str | None = None
    iteration_id: str | None = None
    outcome_evaluation_id: str | None = None
    evidence_ids: tuple[str, ...] = ()
    source_reliability: float = 1.0
    created_at: datetime = field(default_factory=_utc_now)
    metadata: Mapping[str, Any] = field(default_factory=dict)
    fingerprint: str = ""

    def __post_init__(self) -> None:
        if not self.source_run_id or not self.source_goal_id:
            raise InvalidAgentContractError(
                "KnowledgeProvenance requires non-empty source_run_id and source_goal_id"
            )
        if not self.fingerprint:
            payload = {
                "source_run_id": self.source_run_id,
                "source_goal_id": self.source_goal_id,
                "workflow_id": self.workflow_id,
                "iteration_id": self.iteration_id,
                "outcome_evaluation_id": self.outcome_evaluation_id,
                "evidence_ids": list(self.evidence_ids),
                "source_reliability": self.source_reliability,
            }
            object.__setattr__(self, "fingerprint", _compute_fingerprint(payload))


@dataclass(frozen=True)
class KnowledgeSensitivityAssessment:
    """Sensitivity and privacy classification for proposed knowledge or memory items."""

    assessment_id: str
    level: KnowledgeSensitivityLevel
    contains_secrets: bool = False
    contains_personal_data: bool = False
    contains_credentials: bool = False
    requires_redaction: bool = False
    redacted_fields: tuple[str, ...] = ()
    reasons: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)
    fingerprint: str = ""

    def __post_init__(self) -> None:
        if not self.assessment_id:
            raise InvalidAgentContractError("assessment_id cannot be empty")
        if not self.fingerprint:
            payload = {
                "assessment_id": self.assessment_id,
                "level": self.level.value,
                "contains_secrets": self.contains_secrets,
                "contains_personal_data": self.contains_personal_data,
                "contains_credentials": self.contains_credentials,
                "requires_redaction": self.requires_redaction,
                "redacted_fields": list(self.redacted_fields),
                "reasons": list(self.reasons),
            }
            object.__setattr__(self, "fingerprint", _compute_fingerprint(payload))


@dataclass(frozen=True)
class KnowledgeExpirationPolicy:
    """Temporal validity and expiration policy for knowledge/memory items."""

    ttl_seconds: float | None = None
    expires_at: datetime | None = None
    auto_invalidate: bool = True
    renew_on_access: bool = False


@dataclass(frozen=True)
class KnowledgeConfirmationRequirement:
    """Requirement for user confirmation prior to persisting personal/sensitive preferences."""

    requirement_id: str
    required: bool = False
    reason: str = ""
    scope: str = ""
    confirmed_by_user: bool = False
    confirmation_timestamp: datetime | None = None


@dataclass(frozen=True)
class KnowledgeVersionReference:
    """Version reference tracking knowledge history and superseding transitions."""

    item_id: str
    version: int = 1
    previous_version_id: str | None = None
    effective_from: datetime = field(default_factory=_utc_now)
    superseded_at: datetime | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class KnowledgeDeduplicationResult:
    """Result of evaluating candidates against existing knowledge for duplicates."""

    candidate_id: str
    is_duplicate: bool
    existing_item_id: str | None = None
    action: KnowledgeWriteDecisionKind = KnowledgeWriteDecisionKind.ADD
    match_type: str = "none"
    similarity_score: float = 0.0
    merged_content: Mapping[str, Any] | None = None
    reasons: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class KnowledgeUpdateCandidate:
    """Candidate unit of knowledge extracted from runtime execution results."""

    candidate_id: str
    kind: KnowledgeCandidateKind
    title: str
    content: Mapping[str, Any]
    provenance: KnowledgeProvenance
    confidence: float
    relevance_score: float
    reusable: bool
    temporal_stability: str = "stable"
    scope: Mapping[str, Any] = field(default_factory=dict)
    expiration: KnowledgeExpirationPolicy | None = None
    sensitivity: KnowledgeSensitivityAssessment | None = None
    evidence_ids: tuple[str, ...] = ()
    created_at: datetime = field(default_factory=_utc_now)
    metadata: Mapping[str, Any] = field(default_factory=dict)
    fingerprint: str = ""

    def __post_init__(self) -> None:
        if not self.candidate_id or not self.title:
            raise InvalidAgentContractError(
                "KnowledgeUpdateCandidate requires non-empty candidate_id and title"
            )
        if not (0.0 <= self.confidence <= 1.0):
            raise InvalidAgentContractError("confidence must be between 0.0 and 1.0")
        if not self.fingerprint:
            payload = {
                "candidate_id": self.candidate_id,
                "kind": self.kind.value,
                "title": self.title,
                "content": dict(self.content),
                "confidence": self.confidence,
                "provenance": self.provenance.fingerprint,
            }
            object.__setattr__(self, "fingerprint", _compute_fingerprint(payload))


@dataclass(frozen=True)
class KnowledgeAddition:
    """Addition item approved for insertion into Knowledge Store."""

    addition_id: str
    candidate_id: str
    topic: str
    content: Mapping[str, Any]
    provenance: KnowledgeProvenance
    confidence: float
    sensitivity_level: KnowledgeSensitivityLevel
    permissions: tuple[str, ...] = ()
    expiration: KnowledgeExpirationPolicy | None = None
    created_at: datetime = field(default_factory=_utc_now)
    metadata: Mapping[str, Any] = field(default_factory=dict)
    fingerprint: str = ""

    def __post_init__(self) -> None:
        if not self.addition_id or not self.candidate_id or not self.topic:
            raise InvalidAgentContractError(
                "KnowledgeAddition requires non-empty identifiers and topic"
            )
        if not self.fingerprint:
            payload = {
                "addition_id": self.addition_id,
                "candidate_id": self.candidate_id,
                "topic": self.topic,
                "content": dict(self.content),
                "confidence": self.confidence,
                "sensitivity_level": self.sensitivity_level.value,
            }
            object.__setattr__(self, "fingerprint", _compute_fingerprint(payload))


@dataclass(frozen=True)
class KnowledgeUpdate:
    """Update item approved for updating an existing entry in Knowledge Store."""

    update_id: str
    target_item_id: str
    candidate_id: str
    updated_fields: Mapping[str, Any]
    version_ref: KnowledgeVersionReference
    provenance: KnowledgeProvenance
    confidence: float
    created_at: datetime = field(default_factory=_utc_now)
    metadata: Mapping[str, Any] = field(default_factory=dict)
    fingerprint: str = ""

    def __post_init__(self) -> None:
        if not self.update_id or not self.target_item_id or not self.candidate_id:
            raise InvalidAgentContractError(
                "KnowledgeUpdate requires non-empty identifiers"
            )
        if not self.fingerprint:
            payload = {
                "update_id": self.update_id,
                "target_item_id": self.target_item_id,
                "candidate_id": self.candidate_id,
                "updated_fields": dict(self.updated_fields),
                "confidence": self.confidence,
            }
            object.__setattr__(self, "fingerprint", _compute_fingerprint(payload))


@dataclass(frozen=True)
class KnowledgeInvalidation:
    """Invalidation record marking prior knowledge as superseded or invalid."""

    invalidation_id: str
    target_item_id: str
    reason: str
    provenance: KnowledgeProvenance
    superseded_by_item_id: str | None = None
    invalidated_at: datetime = field(default_factory=_utc_now)
    metadata: Mapping[str, Any] = field(default_factory=dict)
    fingerprint: str = ""

    def __post_init__(self) -> None:
        if not self.invalidation_id or not self.target_item_id:
            raise InvalidAgentContractError(
                "KnowledgeInvalidation requires non-empty identifiers"
            )
        if not self.fingerprint:
            payload = {
                "invalidation_id": self.invalidation_id,
                "target_item_id": self.target_item_id,
                "reason": self.reason,
                "superseded_by_item_id": self.superseded_by_item_id,
            }
            object.__setattr__(self, "fingerprint", _compute_fingerprint(payload))


@dataclass(frozen=True)
class KnowledgeRelation:
    """Explicit semantic link or dependency relation created between knowledge items."""

    relation_id: str
    source_item_id: str
    target_item_id: str
    relation_type: str
    strength: float = 1.0
    provenance: KnowledgeProvenance | None = None
    created_at: datetime = field(default_factory=_utc_now)
    metadata: Mapping[str, Any] = field(default_factory=dict)
    fingerprint: str = ""

    def __post_init__(self) -> None:
        if not self.relation_id or not self.source_item_id or not self.target_item_id:
            raise InvalidAgentContractError(
                "KnowledgeRelation requires non-empty identifiers"
            )
        if not self.fingerprint:
            payload = {
                "relation_id": self.relation_id,
                "source_item_id": self.source_item_id,
                "target_item_id": self.target_item_id,
                "relation_type": self.relation_type,
                "strength": self.strength,
            }
            object.__setattr__(self, "fingerprint", _compute_fingerprint(payload))


@dataclass(frozen=True)
class OperationFact:
    """Auditable fact extracted from operation execution and side-effects."""

    fact_id: str
    operation_type: str
    target: str
    summary: str
    success: bool
    evidence_ids: tuple[str, ...] = ()
    provenance: KnowledgeProvenance | None = None
    created_at: datetime = field(default_factory=_utc_now)
    metadata: Mapping[str, Any] = field(default_factory=dict)
    fingerprint: str = ""

    def __post_init__(self) -> None:
        if not self.fact_id or not self.operation_type or not self.summary:
            raise InvalidAgentContractError(
                "OperationFact requires non-empty fact_id, operation_type, and summary"
            )
        if not self.fingerprint:
            payload = {
                "fact_id": self.fact_id,
                "operation_type": self.operation_type,
                "target": self.target,
                "summary": self.summary,
                "success": self.success,
            }
            object.__setattr__(self, "fingerprint", _compute_fingerprint(payload))


@dataclass(frozen=True)
class AgentDecisionRecord:
    """Auditable record of a key runtime decision made during execution."""

    decision_record_id: str
    decision_type: str
    context_summary: str
    rationale_summary: str
    selected_option: str
    rejected_options: tuple[str, ...] = ()
    confidence: float = 1.0
    provenance: KnowledgeProvenance | None = None
    created_at: datetime = field(default_factory=_utc_now)
    metadata: Mapping[str, Any] = field(default_factory=dict)
    fingerprint: str = ""

    def __post_init__(self) -> None:
        if (
            not self.decision_record_id
            or not self.decision_type
            or not self.selected_option
        ):
            raise InvalidAgentContractError(
                "AgentDecisionRecord requires non-empty identifiers and option"
            )
        if not self.fingerprint:
            payload = {
                "decision_record_id": self.decision_record_id,
                "decision_type": self.decision_type,
                "context_summary": self.context_summary,
                "selected_option": self.selected_option,
                "confidence": self.confidence,
            }
            object.__setattr__(self, "fingerprint", _compute_fingerprint(payload))


@dataclass(frozen=True)
class OperationalLesson:
    """Reusable operational pattern, constraint, or lesson learned from agent runs."""

    lesson_id: str
    statement: str
    kind: OperationalLessonKind
    evidence_ids: tuple[str, ...]
    scope: Mapping[str, Any]
    confidence: float
    reusable: bool
    expiration: KnowledgeExpirationPolicy | None = None
    validation_requirements: tuple[str, ...] = ()
    source_run_ids: tuple[str, ...] = ()
    source_goal_ids: tuple[str, ...] = ()
    created_at: datetime = field(default_factory=_utc_now)
    metadata: Mapping[str, Any] = field(default_factory=dict)
    fingerprint: str = ""

    def __post_init__(self) -> None:
        if not self.lesson_id or not self.statement:
            raise InvalidAgentContractError(
                "OperationalLesson requires non-empty lesson_id and statement"
            )
        if not (0.0 <= self.confidence <= 1.0):
            raise InvalidAgentContractError(
                "Lesson confidence must be between 0.0 and 1.0"
            )
        if not self.fingerprint:
            payload = {
                "lesson_id": self.lesson_id,
                "statement": self.statement,
                "kind": self.kind.value,
                "evidence_ids": list(self.evidence_ids),
                "scope": dict(self.scope),
                "confidence": self.confidence,
                "reusable": self.reusable,
            }
            object.__setattr__(self, "fingerprint", _compute_fingerprint(payload))


@dataclass(frozen=True)
class RejectedKnowledgeItem:
    """Record of a knowledge candidate explicitly rejected and not stored."""

    rejection_id: str
    candidate_id: str
    candidate_kind: KnowledgeCandidateKind
    reason_code: KnowledgeRejectionReason
    justification: str
    raw_summary: str
    rejected_at: datetime = field(default_factory=_utc_now)
    metadata: Mapping[str, Any] = field(default_factory=dict)
    fingerprint: str = ""

    def __post_init__(self) -> None:
        if not self.rejection_id or not self.candidate_id:
            raise InvalidAgentContractError(
                "RejectedKnowledgeItem requires non-empty identifiers"
            )
        if not self.fingerprint:
            payload = {
                "rejection_id": self.rejection_id,
                "candidate_id": self.candidate_id,
                "candidate_kind": self.candidate_kind.value,
                "reason_code": self.reason_code.value,
                "justification": self.justification,
            }
            object.__setattr__(self, "fingerprint", _compute_fingerprint(payload))


@dataclass(frozen=True)
class MemoryUpdateCandidate:
    """Candidate entry evaluated for persistence in Memory Store."""

    candidate_id: str
    memory_type: str
    key: str
    value: Any
    confidence: float
    is_explicit_preference: bool = False
    user_confirmed: bool = False
    sensitivity: KnowledgeSensitivityAssessment | None = None
    expiration: KnowledgeExpirationPolicy | None = None
    provenance: KnowledgeProvenance | None = None
    created_at: datetime = field(default_factory=_utc_now)
    metadata: Mapping[str, Any] = field(default_factory=dict)
    fingerprint: str = ""

    def __post_init__(self) -> None:
        if not self.candidate_id or not self.key:
            raise InvalidAgentContractError(
                "MemoryUpdateCandidate requires non-empty candidate_id and key"
            )
        if not (0.0 <= self.confidence <= 1.0):
            raise InvalidAgentContractError(
                "Memory candidate confidence must be between 0.0 and 1.0"
            )
        if not self.fingerprint:
            payload = {
                "candidate_id": self.candidate_id,
                "memory_type": self.memory_type,
                "key": self.key,
                "value": str(self.value),
                "confidence": self.confidence,
                "is_explicit_preference": self.is_explicit_preference,
                "user_confirmed": self.user_confirmed,
            }
            object.__setattr__(self, "fingerprint", _compute_fingerprint(payload))


@dataclass(frozen=True)
class MemoryWriteDecision:
    """Policy decision governing write access for a specific memory update candidate."""

    decision_id: str
    candidate_id: str
    decision: MemoryWriteDecisionKind
    reason_codes: tuple[str, ...] = ()
    confirmation_req: KnowledgeConfirmationRequirement | None = None
    redacted_value: Any | None = None
    decided_at: datetime = field(default_factory=_utc_now)
    metadata: Mapping[str, Any] = field(default_factory=dict)
    fingerprint: str = ""

    def __post_init__(self) -> None:
        if not self.decision_id or not self.candidate_id:
            raise InvalidAgentContractError(
                "MemoryWriteDecision requires non-empty identifiers"
            )
        if not self.fingerprint:
            payload = {
                "decision_id": self.decision_id,
                "candidate_id": self.candidate_id,
                "decision": self.decision.value,
                "reason_codes": list(self.reason_codes),
            }
            object.__setattr__(self, "fingerprint", _compute_fingerprint(payload))


@dataclass(frozen=True)
class MemoryUpdateProposal:
    """Proposal collecting candidate memory writes and their associated decisions."""

    memory_proposal_id: str
    agent_run_id: str
    goal_id: str
    candidates: tuple[MemoryUpdateCandidate, ...] = ()
    decisions: tuple[MemoryWriteDecision, ...] = ()
    requires_confirmation: bool = False
    created_at: datetime = field(default_factory=_utc_now)
    metadata: Mapping[str, Any] = field(default_factory=dict)
    fingerprint: str = ""

    def __post_init__(self) -> None:
        if not self.memory_proposal_id or not self.agent_run_id or not self.goal_id:
            raise InvalidAgentContractError(
                "MemoryUpdateProposal requires non-empty identifiers"
            )
        if not self.fingerprint:
            payload = {
                "memory_proposal_id": self.memory_proposal_id,
                "agent_run_id": self.agent_run_id,
                "goal_id": self.goal_id,
                "candidate_ids": [c.candidate_id for c in self.candidates],
                "decision_ids": [d.decision_id for d in self.decisions],
                "requires_confirmation": self.requires_confirmation,
            }
            object.__setattr__(self, "fingerprint", _compute_fingerprint(payload))


@dataclass(frozen=True)
class KnowledgeUpdateDecision:
    """Auditable decision record for an entire KnowledgeUpdateProposal."""

    decision_id: str
    proposal_id: str
    status: KnowledgeProposalStatus
    item_decisions: Mapping[str, KnowledgeWriteDecisionKind] = field(
        default_factory=dict
    )
    approved_by: str | None = None
    rejection_reason: str | None = None
    decided_at: datetime = field(default_factory=_utc_now)
    metadata: Mapping[str, Any] = field(default_factory=dict)
    fingerprint: str = ""

    def __post_init__(self) -> None:
        if not self.decision_id or not self.proposal_id:
            raise InvalidAgentContractError(
                "KnowledgeUpdateDecision requires non-empty identifiers"
            )
        if not self.fingerprint:
            payload = {
                "decision_id": self.decision_id,
                "proposal_id": self.proposal_id,
                "status": self.status.value,
                "item_decisions": {k: v.value for k, v in self.item_decisions.items()},
                "approved_by": self.approved_by,
                "rejection_reason": self.rejection_reason,
            }
            object.__setattr__(self, "fingerprint", _compute_fingerprint(payload))


@dataclass(frozen=True)
class KnowledgeUpdateResult:
    """Execution result summary after applying a KnowledgeUpdateProposal."""

    result_id: str
    proposal_id: str
    status: KnowledgeProposalStatus
    applied_additions: tuple[str, ...] = ()
    applied_updates: tuple[str, ...] = ()
    applied_invalidations: tuple[str, ...] = ()
    applied_relations: tuple[str, ...] = ()
    applied_facts: tuple[str, ...] = ()
    applied_lessons: tuple[str, ...] = ()
    failed_item_ids: tuple[str, ...] = ()
    error_message: str | None = None
    completed_at: datetime = field(default_factory=_utc_now)
    metadata: Mapping[str, Any] = field(default_factory=dict)
    fingerprint: str = ""

    def __post_init__(self) -> None:
        if not self.result_id or not self.proposal_id:
            raise InvalidAgentContractError(
                "KnowledgeUpdateResult requires non-empty identifiers"
            )
        if not self.fingerprint:
            payload = {
                "result_id": self.result_id,
                "proposal_id": self.proposal_id,
                "status": self.status.value,
                "applied_additions": list(self.applied_additions),
                "applied_updates": list(self.applied_updates),
                "applied_invalidations": list(self.applied_invalidations),
                "failed_item_ids": list(self.failed_item_ids),
                "error_message": self.error_message,
            }
            object.__setattr__(self, "fingerprint", _compute_fingerprint(payload))


@dataclass(frozen=True)
class MemoryUpdateResult:
    """Execution result summary after applying a MemoryUpdateProposal."""

    result_id: str
    memory_proposal_id: str
    written_keys: tuple[str, ...] = ()
    rejected_keys: tuple[str, ...] = ()
    deferred_keys: tuple[str, ...] = ()
    failed_keys: tuple[str, ...] = ()
    error_message: str | None = None
    completed_at: datetime = field(default_factory=_utc_now)
    metadata: Mapping[str, Any] = field(default_factory=dict)
    fingerprint: str = ""

    def __post_init__(self) -> None:
        if not self.result_id or not self.memory_proposal_id:
            raise InvalidAgentContractError(
                "MemoryUpdateResult requires non-empty identifiers"
            )
        if not self.fingerprint:
            payload = {
                "result_id": self.result_id,
                "memory_proposal_id": self.memory_proposal_id,
                "written_keys": list(self.written_keys),
                "rejected_keys": list(self.rejected_keys),
                "deferred_keys": list(self.deferred_keys),
                "failed_keys": list(self.failed_keys),
                "error_message": self.error_message,
            }
            object.__setattr__(self, "fingerprint", _compute_fingerprint(payload))


@dataclass(frozen=True)
class KnowledgeUpdateContext:
    """Contextual runtime environment passed to proposal engine and update pipeline."""

    context_id: str
    agent_run_id: str
    goal_id: str
    workflow_id: str | None = None
    iteration_id: str | None = None
    outcome_evaluation_id: str | None = None
    completion_decision_id: str | None = None
    permissions: tuple[str, ...] = ()
    user_confirmed_preferences: tuple[str, ...] = ()
    created_at: datetime = field(default_factory=_utc_now)
    metadata: Mapping[str, Any] = field(default_factory=dict)
    fingerprint: str = ""

    def __post_init__(self) -> None:
        if not self.context_id or not self.agent_run_id or not self.goal_id:
            raise InvalidAgentContractError(
                "KnowledgeUpdateContext requires non-empty identifiers"
            )
        if not self.fingerprint:
            payload = {
                "context_id": self.context_id,
                "agent_run_id": self.agent_run_id,
                "goal_id": self.goal_id,
                "workflow_id": self.workflow_id,
                "iteration_id": self.iteration_id,
                "outcome_evaluation_id": self.outcome_evaluation_id,
                "permissions": list(self.permissions),
            }
            object.__setattr__(self, "fingerprint", _compute_fingerprint(payload))


@dataclass(frozen=True)
class AgentKnowledgeUpdateProposal:
    """Comprehensive proposal containing proposed additions, updates, lessons, and memory updates."""

    proposal_id: str
    agent_run_id: str
    goal_id: str
    workflow_id: str | None
    iteration_id: str | None
    outcome_evaluation_id: str | None
    completion_decision_id: str | None
    additions: tuple[KnowledgeAddition, ...]
    updates: tuple[KnowledgeUpdate, ...]
    invalidations: tuple[KnowledgeInvalidation, ...]
    relations: tuple[KnowledgeRelation, ...]
    operation_facts: tuple[OperationFact, ...]
    decisions: tuple[AgentDecisionRecord, ...]
    lessons: tuple[OperationalLesson, ...]
    rejected_items: tuple[RejectedKnowledgeItem, ...]
    requires_approval: bool
    confidence: float
    reasons: tuple[str, ...]
    source_evidence_ids: tuple[str, ...]
    validation_result_ids: tuple[str, ...]
    permissions: tuple[str, ...]
    sensitivity: KnowledgeSensitivityAssessment
    created_at: datetime = field(default_factory=_utc_now)
    metadata: Mapping[str, Any] = field(default_factory=dict)
    fingerprint: str = ""

    def __post_init__(self) -> None:
        if not self.proposal_id or not self.agent_run_id or not self.goal_id:
            raise InvalidAgentContractError(
                "AgentKnowledgeUpdateProposal requires non-empty proposal_id, agent_run_id, and goal_id"
            )
        if not (0.0 <= self.confidence <= 1.0):
            raise InvalidAgentContractError(
                "Proposal confidence must be between 0.0 and 1.0"
            )
        if not self.fingerprint:
            payload = {
                "proposal_id": self.proposal_id,
                "agent_run_id": self.agent_run_id,
                "goal_id": self.goal_id,
                "additions": [a.addition_id for a in self.additions],
                "updates": [u.update_id for u in self.updates],
                "invalidations": [i.invalidation_id for i in self.invalidations],
                "relations": [r.relation_id for r in self.relations],
                "operation_facts": [f.fact_id for f in self.operation_facts],
                "decisions": [d.decision_record_id for d in self.decisions],
                "lessons": [l.lesson_id for l in self.lessons],
                "rejected_items": [rj.rejection_id for rj in self.rejected_items],
                "requires_approval": self.requires_approval,
                "confidence": self.confidence,
                "sensitivity": self.sensitivity.fingerprint,
            }
            object.__setattr__(self, "fingerprint", _compute_fingerprint(payload))
