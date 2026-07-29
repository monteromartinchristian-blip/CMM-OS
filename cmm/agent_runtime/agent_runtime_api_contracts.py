"""Phase 9.21 – Agent Runtime API Contracts.

Immutable, serializable contracts for the Agent Runtime API surface.
Exposes operation types to CLI, UI, n8n, external integrations and future agents
without coupling those consumers to internal managers, repositories or services.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from cmm.agent_runtime.agent_runtime_api_enums import (
    AgentRuntimeApiErrorCode,
    AgentRuntimeApiOperation,
    AgentRuntimeApiSortDirection,
    AgentRuntimeApiStatus,
)

# ── Core API Contracts ───────────────────────────────────────────────────────


def _current_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _generate_uuid() -> str:
    return str(uuid.uuid4())


# ── Request ──────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class AgentRuntimeApiRequest:
    """Public immutable API request."""

    operation: AgentRuntimeApiOperation
    payload: dict[str, Any] = field(default_factory=dict)
    request_id: str = field(default_factory=_generate_uuid)
    idempotency_key: str | None = None
    timestamp: str = field(default_factory=_current_iso)

    def __post_init__(self) -> None:
        if not isinstance(self.request_id, str) or not self.request_id.strip():
            raise ValueError("request_id must be a non-empty string")
        if self.idempotency_key is not None and (
            not isinstance(self.idempotency_key, str)
            or not self.idempotency_key.strip()
        ):
            raise ValueError("idempotency_key must be a non-empty string or None")


@dataclass(frozen=True)
class AgentRuntimeApiContext:
    """Public API call context with permissions and actor."""

    actor: str
    actor_kind: str = "user"
    permissions: frozenset = field(default_factory=frozenset)
    session_id: str | None = None
    trace_id: str | None = None
    timestamp: str = field(default_factory=_current_iso)

    def __post_init__(self) -> None:
        if not isinstance(self.actor, str) or not self.actor.strip():
            raise ValueError("actor must be a non-empty string")


# ── Response ─────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class AgentRuntimeApiError:
    """Structured error in a response."""

    code: AgentRuntimeApiErrorCode
    message: str
    details: dict[str, Any] | None = None
    request_id: str | None = None

    def __post_init__(self) -> None:
        # Sensitive patterns to sanitize from message
        _sensitive_keywords = [
            "chain_of_thought",
            "private_prompt",
            "password",
            "token",
            "api_key",
            "bearer",
            "private_key",
            "Traceback",
            "File ",
            "raise ",
        ]
        msg = self.message or ""
        # Use contains check instead of direct replacement for immutable safety
        for kw in _sensitive_keywords:
            if kw.lower() in msg.lower():
                object.__setattr__(self, "message", "An internal error occurred")
                break


@dataclass(frozen=True)
class AgentRuntimeApiResponse:
    """Public API response."""

    status: AgentRuntimeApiStatus
    data: Any | None = None
    errors: list[AgentRuntimeApiError] = field(default_factory=list)
    request_id: str | None = None
    timestamp: str = field(default_factory=_current_iso)
    meta: dict[str, Any] = field(default_factory=dict)

    @property
    def success(self) -> bool:
        return self.status == AgentRuntimeApiStatus.SUCCESS


@dataclass(frozen=True)
class AgentRuntimeApiPage:
    """Paginated API response wrapper."""

    items: list[Any] = field(default_factory=list)
    limit: int = 50
    cursor: str | None = None
    offset: int | None = None
    total: int | None = None
    has_more: bool = False

    def __post_init__(self) -> None:
        if self.limit < 1 or self.limit > 500:
            raise ValueError("limit must be between 1 and 500")


@dataclass(frozen=True)
class AgentRuntimeApiQuery:
    """Standard query/filter parameters for list operations."""

    limit: int = 50
    offset: int | None = None
    cursor: str | None = None
    sort_by: str | None = None
    sort_direction: AgentRuntimeApiSortDirection = AgentRuntimeApiSortDirection.ASC
    filters: dict[str, Any] = field(default_factory=dict)
    time_range_start: str | None = None
    time_range_end: str | None = None
    ids: list[str] | None = None
    statuses: list[str] | None = None
    strict_filters: bool = True

    def __post_init__(self) -> None:
        if not (1 <= self.limit <= 500):
            raise ValueError("limit must be between 1 and 500")


@dataclass(frozen=True)
class AgentRuntimeApiPermissions:
    """Permission set for an API operation."""

    required: dict[str, bool] = field(default_factory=dict)
    resource_owner: str | None = None
    resource_creator: str | None = None

    def allows(self, permission: str) -> bool:
        return self.required.get(permission, False)


# ── Health / Stats ───────────────────────────────────────────────────────────


@dataclass(frozen=True)
class AgentRuntimeApiHealth:
    """Runtime system health response."""

    status: str
    version: str
    managers: dict[str, str]
    repositories: dict[str, str]
    event_bus: str
    trace_service: str
    timestamp: str
    warnings: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        for warning in self.warnings:
            _safe = [
                "chain_of_thought",
                "password",
                "token",
                "api_key",
                "bearer",
                "private_key",
            ]
            for s in _safe:
                if s.lower() in (warning or "").lower():
                    raise ValueError(f"warning contains sensitive data: {s}")


@dataclass(frozen=True)
class AgentRuntimeApiStats:
    """Runtime stats snapshot."""

    goals: dict[str, int] = field(default_factory=dict)
    runs: dict[str, int] = field(default_factory=dict)
    approvals_pending: int = 0
    budget_reserved: int | None = None
    budget_limit: int | None = None
    traces: int = 0
    events: int = 0
    dead_letters: int = 0
    api_errors: int = 0
    operations_executed: int = 0
    latency_accumulated_ms: float = 0.0
    latency_count: int = 0
    unavailable: list[str] = field(default_factory=list)

    @property
    def latency_average_ms(self) -> float | None:
        if self.latency_count > 0:
            return self.latency_accumulated_ms / self.latency_count
        return None


# ── Goal Requests ────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class CreateGoalRequest:
    title: str
    objective: str
    goal_kind: str = "GENERAL"
    priority: int = 5
    context: dict[str, Any] = field(default_factory=dict)
    constraints: list[dict[str, Any]] = field(default_factory=list)
    success_criteria: list[dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.title.strip():
            raise ValueError("title must not be empty")
        if not self.objective.strip():
            raise ValueError("objective must not be empty")
        if self.priority < 0:
            raise ValueError("priority must be non-negative")


@dataclass(frozen=True)
class GetGoalRequest:
    goal_id: str

    def __post_init__(self) -> None:
        if not self.goal_id.strip():
            raise ValueError("goal_id must not be empty")


@dataclass(frozen=True)
class ListGoalsRequest:
    query: AgentRuntimeApiQuery | None = None

    def __post_init__(self) -> None:
        if self.query is None:
            object.__setattr__(self, "query", AgentRuntimeApiQuery())


@dataclass(frozen=True)
class UpdateGoalRequest:
    goal_id: str
    title: str | None = None
    objective: str | None = None
    priority: int | None = None
    context: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        if not self.goal_id.strip():
            raise ValueError("goal_id must not be empty")


@dataclass(frozen=True)
class PrioritizeGoalRequest:
    goal_id: str
    new_priority: int

    def __post_init__(self) -> None:
        if not self.goal_id.strip():
            raise ValueError("goal_id must not be empty")
        if self.new_priority < 0:
            raise ValueError("new_priority must be non-negative")


@dataclass(frozen=True)
class PauseGoalRequest:
    goal_id: str
    reason: str | None = None

    def __post_init__(self) -> None:
        if not self.goal_id.strip():
            raise ValueError("goal_id must not be empty")


@dataclass(frozen=True)
class ResumeGoalRequest:
    goal_id: str

    def __post_init__(self) -> None:
        if not self.goal_id.strip():
            raise ValueError("goal_id must not be empty")


@dataclass(frozen=True)
class CancelGoalRequest:
    goal_id: str
    reason: str | None = None

    def __post_init__(self) -> None:
        if not self.goal_id.strip():
            raise ValueError("goal_id must not be empty")


# ── Run Requests ─────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class StartAgentRunRequest:
    goal_id: str
    config: dict[str, Any] = field(default_factory=dict)
    autonomy_level: int | None = None

    def __post_init__(self) -> None:
        if not self.goal_id.strip():
            raise ValueError("goal_id must not be empty")


@dataclass(frozen=True)
class GetAgentRunRequest:
    run_id: str

    def __post_init__(self) -> None:
        if not self.run_id.strip():
            raise ValueError("run_id must not be empty")


@dataclass(frozen=True)
class ListAgentRunsRequest:
    query: AgentRuntimeApiQuery | None = None

    def __post_init__(self) -> None:
        if self.query is None:
            object.__setattr__(self, "query", AgentRuntimeApiQuery())


@dataclass(frozen=True)
class PauseAgentRunRequest:
    run_id: str
    reason: str | None = None

    def __post_init__(self) -> None:
        if not self.run_id.strip():
            raise ValueError("run_id must not be empty")


@dataclass(frozen=True)
class ResumeAgentRunRequest:
    run_id: str

    def __post_init__(self) -> None:
        if not self.run_id.strip():
            raise ValueError("run_id must not be empty")


@dataclass(frozen=True)
class CancelAgentRunRequest:
    run_id: str
    reason: str | None = None

    def __post_init__(self) -> None:
        if not self.run_id.strip():
            raise ValueError("run_id must not be empty")


# ── Approval Requests ────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ListApprovalRequestsRequest:
    query: AgentRuntimeApiQuery | None = None

    def __post_init__(self) -> None:
        if self.query is None:
            object.__setattr__(
                self, "query", AgentRuntimeApiQuery(filters={"status": "pending"})
            )


@dataclass(frozen=True)
class GetApprovalRequestRequest:
    approval_id: str

    def __post_init__(self) -> None:
        if not self.approval_id.strip():
            raise ValueError("approval_id must not be empty")


@dataclass(frozen=True)
class ApproveRequestRequest:
    approval_id: str
    comment: str | None = None

    def __post_init__(self) -> None:
        if not self.approval_id.strip():
            raise ValueError("approval_id must not be empty")


@dataclass(frozen=True)
class RejectRequestRequest:
    approval_id: str
    reason: str | None = None

    def __post_init__(self) -> None:
        if not self.approval_id.strip():
            raise ValueError("approval_id must not be empty")


# ── Budget Requests ──────────────────────────────────────────────────────────


@dataclass(frozen=True)
class GetBudgetRequest:
    budget_id: str

    def __post_init__(self) -> None:
        if not self.budget_id.strip():
            raise ValueError("budget_id must not be empty")


@dataclass(frozen=True)
class ReserveBudgetRequest:
    budget_id: str
    amount: float
    unit: str = "iteration"
    reservation_id: str | None = None

    def __post_init__(self) -> None:
        if not self.budget_id.strip():
            raise ValueError("budget_id must not be empty")
        if self.amount <= 0:
            raise ValueError("amount must be positive")


@dataclass(frozen=True)
class ReleaseBudgetRequest:
    budget_id: str
    reservation_id: str
    amount: float

    def __post_init__(self) -> None:
        if not self.budget_id.strip():
            raise ValueError("budget_id must not be empty")
        if not self.reservation_id.strip():
            raise ValueError("reservation_id must not be empty")
        if self.amount <= 0:
            raise ValueError("amount must be positive")


# ── Trace Requests ───────────────────────────────────────────────────────────


@dataclass(frozen=True)
class GetAgentTraceRequest:
    trace_id: str

    def __post_init__(self) -> None:
        if not self.trace_id.strip():
            raise ValueError("trace_id must not be empty")


@dataclass(frozen=True)
class ListAgentTracesRequest:
    query: AgentRuntimeApiQuery | None = None

    def __post_init__(self) -> None:
        if self.query is None:
            object.__setattr__(self, "query", AgentRuntimeApiQuery())


@dataclass(frozen=True)
class VerifyAgentTraceRequest:
    trace_id: str

    def __post_init__(self) -> None:
        if not self.trace_id.strip():
            raise ValueError("trace_id must not be empty")


@dataclass(frozen=True)
class ExportAgentTraceRequest:
    trace_id: str
    format: str = "JSON"

    def __post_init__(self) -> None:
        if not self.trace_id.strip():
            raise ValueError("trace_id must not be empty")
        valid_formats = {"JSON", "JSONL", "SUMMARY"}
        if self.format.upper() not in valid_formats:
            raise ValueError(f"format must be one of {valid_formats}")


# ── Event Requests ───────────────────────────────────────────────────────────


@dataclass(frozen=True)
class PublishRuntimeEventRequest:
    event_type: str
    payload: dict[str, Any] = field(default_factory=dict)
    sensitivity: str = "internal"

    def __post_init__(self) -> None:
        if not self.event_type.strip():
            raise ValueError("event_type must not be empty")


@dataclass(frozen=True)
class ListRuntimeEventsRequest:
    query: AgentRuntimeApiQuery | None = None

    def __post_init__(self) -> None:
        if self.query is None:
            object.__setattr__(self, "query", AgentRuntimeApiQuery())


@dataclass(frozen=True)
class ReplayRuntimeEventsRequest:
    envelope_id: str | None = None
    event_type: str | None = None
    replay_mode: str = "skip_delivered"

    def __post_init__(self) -> None:
        if self.replay_mode not in ("skip_delivered", "force_all", "dead_letter_only"):
            raise ValueError(f"invalid replay_mode: {self.replay_mode}")


@dataclass(frozen=True)
class GetDeadLettersRequest:
    query: AgentRuntimeApiQuery | None = None

    def __post_init__(self) -> None:
        if self.query is None:
            object.__setattr__(self, "query", AgentRuntimeApiQuery())


@dataclass(frozen=True)
class ReplayDeadLetterRequest:
    dead_letter_id: str

    def __post_init__(self) -> None:
        if not self.dead_letter_id.strip():
            raise ValueError("dead_letter_id must not be empty")


# ── System Requests ──────────────────────────────────────────────────────────


@dataclass(frozen=True)
class GetRuntimeHealthRequest:
    """Health check request - no specific parameters needed."""


@dataclass(frozen=True)
class GetRuntimeStatsRequest:
    """Stats request - no specific parameters needed."""


# ── Response Types ───────────────────────────────────────────────────────────


@dataclass(frozen=True)
class GoalResponse:
    goal_id: str
    title: str
    objective: str
    status: str
    goal_kind: str
    priority: int
    created_at: str = field(default_factory=_current_iso)
    updated_at: str = field(default_factory=_current_iso)
    context: dict[str, Any] = field(default_factory=dict)
    constraints: list[dict[str, Any]] = field(default_factory=list)
    success_criteria: list[dict[str, Any]] = field(default_factory=list)
    creator: str | None = None
    owner: str | None = None


@dataclass(frozen=True)
class AgentRunResponse:
    run_id: str
    goal_id: str
    status: str
    autonomy_level: int
    created_at: str = field(default_factory=_current_iso)
    updated_at: str = field(default_factory=_current_iso)
    current_step: str | None = None
    iteration: int = 0
    error: str | None = None


@dataclass(frozen=True)
class ApprovalResponse:
    approval_id: str
    status: str
    requirement: dict[str, Any] | None = None
    decision: str | None = None
    actor: str | None = None
    comment: str | None = None
    created_at: str = field(default_factory=_current_iso)
    expires_at: str | None = None
    resolved_at: str | None = None


@dataclass(frozen=True)
class BudgetResponse:
    budget_id: str
    status: str
    limit: float
    used: float = 0.0
    reserved: float = 0.0
    unit: str = "iteration"
    created_at: str = field(default_factory=_current_iso)
    reservation: dict[str, Any] | None = None


@dataclass(frozen=True)
class TraceResponse:
    trace_id: str
    run_id: str | None = None
    goal_id: str | None = None
    status: str = "unknown"
    record_count: int = 0
    created_at: str = field(default_factory=_current_iso)
    finalized_at: str | None = None
    integrity_status: str | None = None
    export_format: str | None = None
    export_data: Any | None = None


@dataclass(frozen=True)
class EventResponse:
    event_id: str
    event_type: str
    category: str
    sensitivity: str
    timestamp: str = field(default_factory=_current_iso)
    delivery: dict[str, Any] | None = None
    replay: dict[str, Any] | None = None
    dead_letter_id: str | None = None
    original_event_id: str | None = None


@dataclass(frozen=True)
class RuntimeHealthResponse:
    status: str
    version: str
    managers: dict[str, str]
    repositories: dict[str, str]
    event_bus: str
    trace_service: str
    timestamp: str = field(default_factory=_current_iso)
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class RuntimeStatsResponse:
    goals_by_status: dict[str, int] = field(default_factory=dict)
    runs_by_status: dict[str, int] = field(default_factory=dict)
    approvals_pending: int = 0
    budget_reserved: float | None = None
    budget_limit: float | None = None
    traces: int = 0
    events: int = 0
    dead_letters: int = 0
    api_errors: int = 0
    operations_executed: int = 0
    latency_accumulated_ms: float = 0.0
    latency_count: int = 0
    unavailable: list[str] = field(default_factory=list)
    timestamp: str = field(default_factory=_current_iso)

    @property
    def latency_average_ms(self) -> float | None:
        if self.latency_count > 0:
            return self.latency_accumulated_ms / self.latency_count
        return None


# ── Idempotency Helpers ──────────────────────────────────────────────────────


def compute_request_fingerprint(
    request: AgentRuntimeApiRequest, payload: dict[str, Any]
) -> str:
    """Deterministic fingerprint for idempotency."""
    normalized = json.dumps(
        {
            "operation": request.operation.value,
            "payload": json.dumps(payload, sort_keys=True),
        },
        sort_keys=True,
    )
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()
