"""Phase 9.20 – Runtime Event Bus Contracts.

Defines immutable, serializable contracts for the Agent Runtime Event Bus.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class EventSensitivity(str, Enum):
    """Sensitivity classification for events."""

    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"


class EventDeliveryStatus(str, Enum):
    """Status of event delivery to a subscriber."""

    DELIVERED = "delivered"
    SKIPPED = "skipped"
    FILTERED = "filtered"
    DUPLICATE = "duplicate"
    FAILED = "failed"
    DEAD_LETTERED = "dead_lettered"


class EventTypeCategory(str, Enum):
    """Category of event types for organization."""

    GOAL = "goal"
    RUNTIME = "runtime"
    ITERATION = "iteration"
    OBSERVATION = "observation"
    KNOWLEDGE = "knowledge"
    PLANNING = "planning"
    POLICY = "policy"
    APPROVAL = "approval"
    BUDGET = "budget"
    EXECUTION = "execution"
    VALIDATION = "validation"
    RECOVERY = "recovery"
    OUTCOME = "outcome"
    MEMORY = "memory"
    TRACE = "trace"
    RUNTIME_SYSTEM = "runtime_system"


@dataclass(frozen=True)
class AgentRuntimeEventHeader:
    """Header for runtime events with correlation and causation metadata."""

    event_id: str
    event_type: str
    schema_version: str = "1.0.0"
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    emitted_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    agent_id: str | None = None
    agent_run_id: str | None = None
    goal_id: str | None = None
    workflow_id: str | None = None
    task_id: str | None = None
    iteration_id: str | None = None
    correlation_id: str | None = None
    causation_id: str | None = None
    actor_id: str | None = None
    source: str = "agent_runtime"
    sensitivity: EventSensitivity = EventSensitivity.INTERNAL
    permissions: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.event_id:
            raise ValueError("event_id is required")
        if not self.event_type:
            raise ValueError("event_type is required")
        if not isinstance(self.occurred_at, datetime):
            raise TypeError("occurred_at must be a datetime")
        if not isinstance(self.emitted_at, datetime):
            raise TypeError("emitted_at must be a datetime")
        if self.occurred_at.tzinfo is None:
            raise ValueError("occurred_at must be timezone-aware")
        if self.emitted_at.tzinfo is None:
            raise ValueError("emitted_at must be timezone-aware")
        if self.emitted_at < self.occurred_at:
            raise ValueError("emitted_at must be after or equal to occurred_at")
        if self.correlation_id is not None and not self.correlation_id:
            raise ValueError("correlation_id cannot be empty")
        if self.causation_id is not None and not self.causation_id:
            raise ValueError("causation_id cannot be empty")


@dataclass(frozen=True)
class AgentRuntimeEventPayload:
    """Payload for runtime events."""

    data: dict[str, Any] = field(default_factory=dict)
    raw: str | None = None

    def __post_init__(self) -> None:
        if self.data is None:
            raise ValueError("payload.data cannot be None")


@dataclass(frozen=True)
class AgentRuntimeEvent:
    """Immutable runtime event contract."""

    header: AgentRuntimeEventHeader
    payload: AgentRuntimeEventPayload


@dataclass(frozen=True)
class AgentRuntimeEventEnvelope:
    """Envelope wrapping an event with delivery information."""

    event: AgentRuntimeEvent
    subscription_id: str | None = None
    delivery_status: EventDeliveryStatus = EventDeliveryStatus.DELIVERED
    delivery_metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AgentRuntimeEventSubscription:
    """Subscription definition for event bus."""

    id: str
    handler_name: str
    event_types: list[str]
    filters: dict[str, Any] = field(default_factory=dict)
    priority: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("subscription id is required")
        if not self.handler_name:
            raise ValueError("handler_name is required")
        if not self.event_types:
            raise ValueError("event_types cannot be empty")


@dataclass(frozen=True)
class AgentRuntimeEventFilter:
    """Filter criteria for event matching."""

    event_type: str | None = None
    agent_id: str | None = None
    agent_run_id: str | None = None
    goal_id: str | None = None
    workflow_id: str | None = None
    correlation_id: str | None = None
    custom: dict[str, Any] = field(default_factory=dict)

    def matches(self, event: AgentRuntimeEvent) -> bool:
        """Check if event matches this filter."""
        if self.event_type and event.header.event_type != self.event_type:
            return False
        if self.agent_id and event.header.agent_id != self.agent_id:
            return False
        if self.agent_run_id and event.header.agent_run_id != self.agent_run_id:
            return False
        if self.goal_id and event.header.goal_id != self.goal_id:
            return False
        if self.workflow_id and event.header.workflow_id != self.workflow_id:
            return False
        if self.correlation_id and event.header.correlation_id != self.correlation_id:
            return False
        for key, value in self.custom.items():
            if event.header.metadata.get(key) != value:
                return False
        return True


@dataclass(frozen=True)
class AgentRuntimeEventDelivery:
    """Delivery record for an event to a handler."""

    event_id: str
    subscription_id: str
    handler_name: str
    status: EventDeliveryStatus
    error: str | None = None
    duration_ms: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AgentRuntimeEventBatch:
    """Batch of events for bulk operations."""

    events: list[AgentRuntimeEvent]
    batch_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AgentRuntimeEventDeadLetter:
    """Dead letter event record."""

    event: AgentRuntimeEvent
    subscription_id: str
    handler_name: str
    error: str
    error_type: str
    attempts: int = 1
    first_failed_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    last_failed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AgentRuntimeEventReplayRequest:
    """Request for event replay."""

    event_id: str | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    event_type: str | None = None
    agent_run_id: str | None = None
    goal_id: str | None = None
    correlation_id: str | None = None
    limit: int = 1000
    dry_run: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AgentRuntimeEventReplayResult:
    """Result of event replay operation."""

    replayed_count: int
    skipped_count: int
    failed_count: int
    events: list[AgentRuntimeEvent] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    dry_run: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentRuntimeEventBusStats:
    """Statistics for the event bus."""

    published_total: int = 0
    delivered_total: int = 0
    filtered_total: int = 0
    duplicate_total: int = 0
    failed_total: int = 0
    dead_letter_total: int = 0
    active_subscriptions: int = 0
    queue_size: int = 0
    replay_count: int = 0
