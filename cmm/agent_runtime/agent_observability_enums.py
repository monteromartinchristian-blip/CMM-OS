"""Phase 9.26 agent observability enumerations."""

from __future__ import annotations

from enum import Enum


class AgentTelemetryKind(str, Enum):
    """Stable kinds for normalized Agent Runtime telemetry."""

    RUN_STARTED = "run_started"
    RUN_RESUMED = "run_resumed"
    RUN_PAUSED = "run_paused"
    RUN_WAITING = "run_waiting"
    RUN_COMPLETED = "run_completed"
    RUN_FAILED = "run_failed"
    RUN_CANCELLED = "run_cancelled"
    GOAL_CREATED = "goal_created"
    GOAL_UPDATED = "goal_updated"
    GOAL_COMPLETED = "goal_completed"
    OPERATION_STARTED = "operation_started"
    OPERATION_COMPLETED = "operation_completed"
    OPERATION_FAILED = "operation_failed"
    OPERATION_RETRIED = "operation_retried"
    APPROVAL_REQUESTED = "approval_requested"
    APPROVAL_RESOLVED = "approval_resolved"
    POLICY_EVALUATED = "policy_evaluated"
    PERMISSION_EVALUATED = "permission_evaluated"
    DELEGATION_PROPOSED = "delegation_proposed"
    DELEGATION_ACCEPTED = "delegation_accepted"
    DELEGATION_COMPLETED = "delegation_completed"
    CHECKPOINT_CREATED = "checkpoint_created"
    ROLLBACK_STARTED = "rollback_started"
    ROLLBACK_COMPLETED = "rollback_completed"
    RECOVERY_STARTED = "recovery_started"
    RECOVERY_COMPLETED = "recovery_completed"
    SECURITY_FINDING = "security_finding"
    BUDGET_RESERVED = "budget_reserved"
    BUDGET_CONSUMED = "budget_consumed"
    MODEL_INVOCATION = "model_invocation"
    CUSTOM = "custom"


class AgentMetricKind(str, Enum):
    """Stable metric semantics."""

    COUNTER = "counter"
    GAUGE = "gauge"
    DURATION = "duration"
    HISTOGRAM = "histogram"
    RATE = "rate"
    RATIO = "ratio"
    COST = "cost"
    TOKENS = "tokens"
    BYTES = "bytes"


class AgentAuditSeverity(str, Enum):
    """Audit and telemetry severity."""

    DEBUG = "debug"
    INFO = "info"
    NOTICE = "notice"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AgentAuditOutcome(str, Enum):
    """Outcome of an audited action."""

    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    DENIED = "denied"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    UNKNOWN = "unknown"


class AgentHealthStatus(str, Enum):
    """Health classification for an observability scope."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    STALLED = "stalled"
    UNKNOWN = "unknown"


__all__ = [
    "AgentAuditOutcome",
    "AgentAuditSeverity",
    "AgentHealthStatus",
    "AgentMetricKind",
    "AgentTelemetryKind",
]
