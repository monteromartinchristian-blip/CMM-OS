"""Phase 9.5 – Cognitive Adapter Contracts.

Data contracts, configuration, references, context, and result structures for the
Cognitive Adapter bridge in the Autonomous Agent Runtime.
"""

from __future__ import annotations

import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from types import MappingProxyType
from typing import Any

from cmm.agent_runtime.contracts import AgentRun
from cmm.agent_runtime.enums import (
    AgentCognitiveDecision,
    AgentCognitiveStatus,
    CognitiveResourceStrategy,
    CognitiveSessionMode,
)
from cmm.agent_runtime.errors import InvalidAgentCognitiveContractError
from cmm.agent_runtime.goal_contracts import Goal
from cmm.agent_runtime.observation_contracts import (
    Observation,
    ObservationSnapshot,
)
from cmm.cognitive.query import KnowledgeQuery
from cmm.cognitive.resources import Resource


def utc_now() -> datetime:
    """Return timezone-aware current UTC datetime."""
    return datetime.now(timezone.utc)


def generate_cognitive_request_id() -> str:
    """Generate a unique request identifier for AgentCognitiveRequest."""
    return f"ag-cog-req-{uuid.uuid4().hex[:12]}"


def generate_cognitive_result_id() -> str:
    """Generate a unique result identifier for AgentCognitiveResult."""
    return f"ag-cog-res-{uuid.uuid4().hex[:12]}"


def generate_cognitive_context_id() -> str:
    """Generate a unique context identifier for AgentCognitiveContext."""
    return f"ag-cog-ctx-{uuid.uuid4().hex[:12]}"


VALID_REQUESTED_DEPTHS = ("minimal", "standard", "deep", "exhaustive")


@dataclass(frozen=True, slots=True)
class AgentCognitiveSessionReference:
    """Reference to an active or prior Cognitive Session in Cognitive Layer."""

    session_id: str
    mode: CognitiveSessionMode
    parent_session_id: str | None = None
    goal_id: str | None = None
    created_at: datetime = field(default_factory=utc_now)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.session_id.strip():
            raise InvalidAgentCognitiveContractError("session_id must not be empty")
        if self.created_at.tzinfo is None:
            raise InvalidAgentCognitiveContractError(
                "created_at must be timezone-aware"
            )

        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "mode": self.mode.value,
            "parent_session_id": self.parent_session_id,
            "goal_id": self.goal_id,
            "created_at": self.created_at.isoformat(),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, mapping: Mapping[str, Any]) -> AgentCognitiveSessionReference:
        dt = mapping.get("created_at")
        created_at = (
            datetime.fromisoformat(dt) if isinstance(dt, str) else (dt or utc_now())
        )
        return cls(
            session_id=str(mapping["session_id"]),
            mode=CognitiveSessionMode(mapping["mode"]),
            parent_session_id=mapping.get("parent_session_id"),
            goal_id=mapping.get("goal_id"),
            created_at=created_at,
            metadata=mapping.get("metadata", {}),
        )


@dataclass(frozen=True, slots=True)
class AgentCognitiveTraceReference:
    """Audit reference linking a Cognitive Request to Cognitive Layer reasoning traces."""

    trace_id: str
    request_id: str
    agent_run_id: str
    goal_id: str
    profile: str
    created_at: datetime = field(default_factory=utc_now)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.trace_id.strip():
            raise InvalidAgentCognitiveContractError("trace_id must not be empty")
        if not self.request_id.strip():
            raise InvalidAgentCognitiveContractError("request_id must not be empty")
        if not self.agent_run_id.strip():
            raise InvalidAgentCognitiveContractError("agent_run_id must not be empty")
        if not self.goal_id.strip():
            raise InvalidAgentCognitiveContractError("goal_id must not be empty")
        if self.created_at.tzinfo is None:
            raise InvalidAgentCognitiveContractError(
                "created_at must be timezone-aware"
            )

        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))

    def to_dict(self) -> dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "request_id": self.request_id,
            "agent_run_id": self.agent_run_id,
            "goal_id": self.goal_id,
            "profile": self.profile,
            "created_at": self.created_at.isoformat(),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, mapping: Mapping[str, Any]) -> AgentCognitiveTraceReference:
        dt = mapping.get("created_at")
        created_at = (
            datetime.fromisoformat(dt) if isinstance(dt, str) else (dt or utc_now())
        )
        return cls(
            trace_id=str(mapping["trace_id"]),
            request_id=str(mapping["request_id"]),
            agent_run_id=str(mapping["agent_run_id"]),
            goal_id=str(mapping["goal_id"]),
            profile=str(mapping["profile"]),
            created_at=created_at,
            metadata=mapping.get("metadata", {}),
        )


@dataclass(frozen=True, slots=True)
class AgentCognitiveWarning:
    """Warning message attached to a cognitive request/result."""

    code: str
    message: str
    source: str = "cognitive_adapter"
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.code.strip():
            raise InvalidAgentCognitiveContractError("warning code must not be empty")
        if not self.message.strip():
            raise InvalidAgentCognitiveContractError(
                "warning message must not be empty"
            )

        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "source": self.source,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, mapping: Mapping[str, Any]) -> AgentCognitiveWarning:
        return cls(
            code=str(mapping["code"]),
            message=str(mapping["message"]),
            source=str(mapping.get("source", "cognitive_adapter")),
            metadata=mapping.get("metadata", {}),
        )


@dataclass(frozen=True, slots=True)
class AgentCognitiveConfiguration:
    """Configuration settings for DefaultCognitiveRuntimeAdapter."""

    default_profile: str = "general"
    default_resource_strategy: CognitiveResourceStrategy = (
        CognitiveResourceStrategy.AUTOMATIC
    )
    default_session_mode: CognitiveSessionMode = CognitiveSessionMode.NEW
    max_questions: int = 3
    max_resources: int = 50
    default_depth: str = "standard"
    confidence_threshold: float = 0.5
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.max_questions < 0:
            raise InvalidAgentCognitiveContractError("max_questions must be >= 0")
        if self.max_resources < 1:
            raise InvalidAgentCognitiveContractError("max_resources must be >= 1")
        if self.default_depth not in VALID_REQUESTED_DEPTHS:
            raise InvalidAgentCognitiveContractError(
                f"default_depth must be one of {VALID_REQUESTED_DEPTHS}"
            )
        if not 0.0 <= float(self.confidence_threshold) <= 1.0:
            raise InvalidAgentCognitiveContractError(
                "confidence_threshold must be between 0.0 and 1.0"
            )

        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))

    def to_dict(self) -> dict[str, Any]:
        return {
            "default_profile": self.default_profile,
            "default_resource_strategy": self.default_resource_strategy.value,
            "default_session_mode": self.default_session_mode.value,
            "max_questions": self.max_questions,
            "max_resources": self.max_resources,
            "default_depth": self.default_depth,
            "confidence_threshold": self.confidence_threshold,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True, slots=True)
class AgentCognitiveRequest:
    """Request contract sent to Cognitive Adapter to perform cognitive analysis."""

    agent_run_id: str
    goal_id: str
    objective: str
    id: str = field(default_factory=generate_cognitive_request_id)
    reasoning_profile: str = "general"
    observation_snapshot_id: str | None = None
    observation_snapshot: ObservationSnapshot | None = None
    resource_ids: tuple[str, ...] = ()
    resources: tuple[Resource, ...] = ()
    knowledge_query: KnowledgeQuery | dict[str, Any] | None = None
    constraints: tuple[Any, ...] = ()
    permissions: tuple[str, ...] = ()
    maximum_questions: int = 3
    requested_depth: str = "standard"
    session_mode: CognitiveSessionMode = CognitiveSessionMode.NEW
    cognitive_session_id: str | None = None
    resource_strategy: CognitiveResourceStrategy = CognitiveResourceStrategy.AUTOMATIC
    temporal_reference: datetime | None = None
    language: str = "en"
    actor_id: str = "agent"
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        if not self.id.strip():
            raise InvalidAgentCognitiveContractError("request id must not be empty")
        if not self.agent_run_id.strip():
            raise InvalidAgentCognitiveContractError("agent_run_id must not be empty")
        if not self.goal_id.strip():
            raise InvalidAgentCognitiveContractError("goal_id must not be empty")
        if not self.objective.strip():
            raise InvalidAgentCognitiveContractError("objective must not be empty")
        if self.maximum_questions < 0:
            raise InvalidAgentCognitiveContractError("maximum_questions must be >= 0")
        if self.requested_depth not in VALID_REQUESTED_DEPTHS:
            raise InvalidAgentCognitiveContractError(
                f"requested_depth must be one of {VALID_REQUESTED_DEPTHS}"
            )
        if self.session_mode is CognitiveSessionMode.RESUME and not (
            self.cognitive_session_id and self.cognitive_session_id.strip()
        ):
            raise InvalidAgentCognitiveContractError(
                "cognitive_session_id is required when session_mode is 'resume'"
            )
        if self.created_at.tzinfo is None:
            raise InvalidAgentCognitiveContractError(
                "created_at must be timezone-aware"
            )
        if (
            self.temporal_reference is not None
            and self.temporal_reference.tzinfo is None
        ):
            raise InvalidAgentCognitiveContractError(
                "temporal_reference must be timezone-aware"
            )

        object.__setattr__(self, "resource_ids", tuple(self.resource_ids))
        object.__setattr__(self, "resources", tuple(self.resources))
        object.__setattr__(self, "constraints", tuple(self.constraints))
        object.__setattr__(self, "permissions", tuple(self.permissions))
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))

    def to_dict(self) -> dict[str, Any]:
        kq_dict = None
        if self.knowledge_query is not None:
            if hasattr(self.knowledge_query, "to_dict"):
                kq_dict = self.knowledge_query.to_dict()
            elif isinstance(self.knowledge_query, dict):
                kq_dict = dict(self.knowledge_query)
            else:
                kq_dict = str(self.knowledge_query)

        return {
            "id": self.id,
            "agent_run_id": self.agent_run_id,
            "goal_id": self.goal_id,
            "objective": self.objective,
            "reasoning_profile": self.reasoning_profile,
            "observation_snapshot_id": self.observation_snapshot_id,
            "observation_snapshot": self.observation_snapshot.to_dict()
            if self.observation_snapshot
            else None,
            "resource_ids": list(self.resource_ids),
            "resources": [r.to_dict() for r in self.resources],
            "knowledge_query": kq_dict,
            "constraints": list(self.constraints),
            "permissions": list(self.permissions),
            "maximum_questions": self.maximum_questions,
            "requested_depth": self.requested_depth,
            "session_mode": self.session_mode.value,
            "cognitive_session_id": self.cognitive_session_id,
            "resource_strategy": self.resource_strategy.value,
            "temporal_reference": self.temporal_reference.isoformat()
            if self.temporal_reference
            else None,
            "language": self.language,
            "actor_id": self.actor_id,
            "metadata": dict(self.metadata),
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, mapping: Mapping[str, Any]) -> AgentCognitiveRequest:
        created_dt = mapping.get("created_at")
        created_at = (
            datetime.fromisoformat(created_dt)
            if isinstance(created_dt, str)
            else (created_dt or utc_now())
        )
        temp_dt = mapping.get("temporal_reference")
        temporal_reference = (
            datetime.fromisoformat(temp_dt) if isinstance(temp_dt, str) else temp_dt
        )
        snapshot_raw = mapping.get("observation_snapshot")
        snapshot = (
            ObservationSnapshot.from_dict(snapshot_raw)
            if isinstance(snapshot_raw, dict)
            else None
        )

        resources_raw = mapping.get("resources", ())
        parsed_resources = []
        for r in resources_raw:
            if isinstance(r, dict):
                parsed_resources.append(Resource.from_dict(r))
            else:
                parsed_resources.append(r)

        return cls(
            id=str(mapping.get("id") or generate_cognitive_request_id()),
            agent_run_id=str(mapping["agent_run_id"]),
            goal_id=str(mapping["goal_id"]),
            objective=str(mapping["objective"]),
            reasoning_profile=str(mapping.get("reasoning_profile", "general")),
            observation_snapshot_id=mapping.get("observation_snapshot_id"),
            observation_snapshot=snapshot,
            resource_ids=tuple(mapping.get("resource_ids", ())),
            resources=tuple(parsed_resources),
            knowledge_query=mapping.get("knowledge_query"),
            constraints=tuple(mapping.get("constraints", ())),
            permissions=tuple(mapping.get("permissions", ())),
            maximum_questions=int(mapping.get("maximum_questions", 3)),
            requested_depth=str(mapping.get("requested_depth", "standard")),
            session_mode=CognitiveSessionMode(mapping.get("session_mode", "new")),
            cognitive_session_id=mapping.get("cognitive_session_id"),
            resource_strategy=CognitiveResourceStrategy(
                mapping.get("resource_strategy", "automatic")
            ),
            temporal_reference=temporal_reference,
            language=str(mapping.get("language", "en")),
            actor_id=str(mapping.get("actor_id", "agent")),
            metadata=mapping.get("metadata", {}),
            created_at=created_at,
        )


@dataclass(frozen=True, slots=True)
class AgentCognitiveContext:
    """Auditable evidence context delivered to Cognitive Layer before reasoning."""

    request_id: str
    id: str = field(default_factory=generate_cognitive_context_id)
    goal: Goal | None = None
    agent_run: AgentRun | None = None
    observation_snapshot: ObservationSnapshot | None = None
    derived_resources: tuple[Resource, ...] = ()
    explicit_resources: tuple[Resource, ...] = ()
    combined_resources: tuple[Resource, ...] = ()
    knowledge_query: KnowledgeQuery | dict[str, Any] | None = None
    constraints: tuple[Any, ...] = ()
    permissions: tuple[str, ...] = ()
    reasoning_profile: str = "general"
    session_reference: AgentCognitiveSessionReference | None = None
    temporal_reference: datetime | None = None
    maximum_questions: int = 3
    requested_depth: str = "standard"
    actor_id: str = "agent"
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        if not self.id.strip():
            raise InvalidAgentCognitiveContractError("context id must not be empty")
        if not self.request_id.strip():
            raise InvalidAgentCognitiveContractError("request_id must not be empty")
        if self.created_at.tzinfo is None:
            raise InvalidAgentCognitiveContractError(
                "created_at must be timezone-aware"
            )

        object.__setattr__(self, "derived_resources", tuple(self.derived_resources))
        object.__setattr__(self, "explicit_resources", tuple(self.explicit_resources))
        object.__setattr__(self, "combined_resources", tuple(self.combined_resources))
        object.__setattr__(self, "constraints", tuple(self.constraints))
        object.__setattr__(self, "permissions", tuple(self.permissions))
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "request_id": self.request_id,
            "goal": self.goal.to_dict() if self.goal else None,
            "agent_run": self.agent_run.to_dict() if self.agent_run else None,
            "observation_snapshot": self.observation_snapshot.to_dict()
            if self.observation_snapshot
            else None,
            "derived_resources": [r.to_dict() for r in self.derived_resources],
            "explicit_resources": [r.to_dict() for r in self.explicit_resources],
            "combined_resources": [r.to_dict() for r in self.combined_resources],
            "constraints": list(self.constraints),
            "permissions": list(self.permissions),
            "reasoning_profile": self.reasoning_profile,
            "session_reference": self.session_reference.to_dict()
            if self.session_reference
            else None,
            "temporal_reference": self.temporal_reference.isoformat()
            if self.temporal_reference
            else None,
            "maximum_questions": self.maximum_questions,
            "requested_depth": self.requested_depth,
            "actor_id": self.actor_id,
            "metadata": dict(self.metadata),
            "created_at": self.created_at.isoformat(),
        }


@dataclass(frozen=True, slots=True)
class AgentCognitiveResult:
    """Operational recommendation and cognitive output returned to Agent Runtime."""

    request_id: str
    agent_run_id: str
    goal_id: str
    status: AgentCognitiveStatus
    recommended_decision: AgentCognitiveDecision
    reasoning_result_id: str
    id: str = field(default_factory=generate_cognitive_result_id)
    reasoning_session_id: str | None = None
    reasoning_trace_id: str | None = None
    relevant_facts: tuple[Any, ...] = ()
    observations: tuple[Observation, ...] = ()
    inferences: tuple[Any, ...] = ()
    hypotheses: tuple[Any, ...] = ()
    contradictions: tuple[Any, ...] = ()
    information_gaps: tuple[Any, ...] = ()
    questions: tuple[Any, ...] = ()
    recommendations: tuple[str, ...] = ()
    unknowns: tuple[str, ...] = ()
    source_ids: tuple[str, ...] = ()
    confidence: float = 1.0
    blocked: bool = False
    requires_user_input: bool = False
    requires_resource: bool = False
    warnings: tuple[AgentCognitiveWarning, ...] = ()
    errors: tuple[str, ...] = ()
    created_at: datetime = field(default_factory=utc_now)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.id.strip():
            raise InvalidAgentCognitiveContractError("result id must not be empty")
        if not self.request_id.strip():
            raise InvalidAgentCognitiveContractError("request_id must not be empty")
        if not self.agent_run_id.strip():
            raise InvalidAgentCognitiveContractError("agent_run_id must not be empty")
        if not self.goal_id.strip():
            raise InvalidAgentCognitiveContractError("goal_id must not be empty")
        if not self.reasoning_result_id.strip():
            raise InvalidAgentCognitiveContractError(
                "reasoning_result_id must not be empty"
            )

        if isinstance(self.confidence, bool) or not isinstance(
            self.confidence, (int, float)
        ):
            raise InvalidAgentCognitiveContractError(
                "confidence must be a float between 0.0 and 1.0"
            )
        norm_confidence = float(self.confidence)
        if not 0.0 <= norm_confidence <= 1.0:
            raise InvalidAgentCognitiveContractError(
                "confidence must be between 0.0 and 1.0"
            )

        if self.created_at.tzinfo is None:
            raise InvalidAgentCognitiveContractError(
                "created_at must be timezone-aware"
            )

        object.__setattr__(self, "confidence", norm_confidence)
        object.__setattr__(self, "relevant_facts", tuple(self.relevant_facts))
        object.__setattr__(self, "observations", tuple(self.observations))
        object.__setattr__(self, "inferences", tuple(self.inferences))
        object.__setattr__(self, "hypotheses", tuple(self.hypotheses))
        object.__setattr__(self, "contradictions", tuple(self.contradictions))
        object.__setattr__(self, "information_gaps", tuple(self.information_gaps))
        object.__setattr__(self, "questions", tuple(self.questions))
        object.__setattr__(self, "recommendations", tuple(self.recommendations))
        object.__setattr__(self, "unknowns", tuple(self.unknowns))
        object.__setattr__(self, "source_ids", tuple(self.source_ids))
        object.__setattr__(self, "warnings", tuple(self.warnings))
        object.__setattr__(self, "errors", tuple(self.errors))
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "request_id": self.request_id,
            "agent_run_id": self.agent_run_id,
            "goal_id": self.goal_id,
            "status": self.status.value,
            "recommended_decision": self.recommended_decision.value,
            "reasoning_result_id": self.reasoning_result_id,
            "reasoning_session_id": self.reasoning_session_id,
            "reasoning_trace_id": self.reasoning_trace_id,
            "relevant_facts": list(self.relevant_facts),
            "observations": [
                o.to_dict() if hasattr(o, "to_dict") else o for o in self.observations
            ],
            "inferences": list(self.inferences),
            "hypotheses": list(self.hypotheses),
            "contradictions": [
                c.to_dict() if hasattr(c, "to_dict") else c for c in self.contradictions
            ],
            "information_gaps": [
                g.to_dict() if hasattr(g, "to_dict") else g
                for g in self.information_gaps
            ],
            "questions": [
                q.to_dict() if hasattr(q, "to_dict") else q for q in self.questions
            ],
            "recommendations": list(self.recommendations),
            "unknowns": list(self.unknowns),
            "source_ids": list(self.source_ids),
            "confidence": self.confidence,
            "blocked": self.blocked,
            "requires_user_input": self.requires_user_input,
            "requires_resource": self.requires_resource,
            "warnings": [w.to_dict() for w in self.warnings],
            "errors": list(self.errors),
            "created_at": self.created_at.isoformat(),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, mapping: Mapping[str, Any]) -> AgentCognitiveResult:
        created_dt = mapping.get("created_at")
        created_at = (
            datetime.fromisoformat(created_dt)
            if isinstance(created_dt, str)
            else (created_dt or utc_now())
        )

        warn_raw = mapping.get("warnings", ())
        warnings = tuple(
            AgentCognitiveWarning.from_dict(w) if isinstance(w, dict) else w
            for w in warn_raw
        )

        obs_raw = mapping.get("observations", ())
        parsed_obs = tuple(
            Observation.from_dict(o) if isinstance(o, dict) else o for o in obs_raw
        )

        return cls(
            id=str(mapping.get("id") or generate_cognitive_result_id()),
            request_id=str(mapping["request_id"]),
            agent_run_id=str(mapping["agent_run_id"]),
            goal_id=str(mapping["goal_id"]),
            status=AgentCognitiveStatus(mapping["status"]),
            recommended_decision=AgentCognitiveDecision(
                mapping["recommended_decision"]
            ),
            reasoning_result_id=str(mapping["reasoning_result_id"]),
            reasoning_session_id=mapping.get("reasoning_session_id"),
            reasoning_trace_id=mapping.get("reasoning_trace_id"),
            relevant_facts=tuple(mapping.get("relevant_facts", ())),
            observations=parsed_obs,
            inferences=tuple(mapping.get("inferences", ())),
            hypotheses=tuple(mapping.get("hypotheses", ())),
            contradictions=tuple(mapping.get("contradictions", ())),
            information_gaps=tuple(mapping.get("information_gaps", ())),
            questions=tuple(mapping.get("questions", ())),
            recommendations=tuple(mapping.get("recommendations", ())),
            unknowns=tuple(mapping.get("unknowns", ())),
            source_ids=tuple(mapping.get("source_ids", ())),
            confidence=float(mapping.get("confidence", 1.0)),
            blocked=bool(mapping.get("blocked", False)),
            requires_user_input=bool(mapping.get("requires_user_input", False)),
            requires_resource=bool(mapping.get("requires_resource", False)),
            warnings=warnings,
            errors=tuple(mapping.get("errors", ())),
            created_at=created_at,
            metadata=mapping.get("metadata", {}),
        )
