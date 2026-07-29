"""Phase 9.20 – Runtime Event Types.

Registers all event types for the Agent Runtime Event Bus.
"""

from __future__ import annotations

from cmm.agent_runtime.runtime_event_contracts import EventTypeCategory


class EventType:
    """Namespace for all registered event types."""

    # ── Goals ───────────────────────────────────────────────────────────────────
    GOAL_CREATED = "goal.created"
    GOAL_UPDATED = "goal.updated"
    GOAL_PRIORITIZED = "goal.prioritized"
    GOAL_BLOCKED = "goal.blocked"
    GOAL_PAUSED = "goal.paused"
    GOAL_RESUMED = "goal.resumed"
    GOAL_CANCELLED = "goal.cancelled"
    GOAL_COMPLETED = "goal.completed"
    GOAL_FAILED = "goal.failed"

    # ── Runtime ─────────────────────────────────────────────────────────────────
    AGENT_RUN_CREATED = "agent_run.created"
    AGENT_RUN_STARTED = "agent_run.started"
    AGENT_RUN_STATUS_CHANGED = "agent_run.status_changed"
    AGENT_RUN_PAUSED = "agent_run.paused"
    AGENT_RUN_RESUMED = "agent_run.resumed"
    AGENT_RUN_CANCELLED = "agent_run.cancelled"
    AGENT_RUN_COMPLETED = "agent_run.completed"
    AGENT_RUN_FAILED = "agent_run.failed"

    # ── Iterations ──────────────────────────────────────────────────────────────
    AGENT_ITERATION_STARTED = "agent_iteration.started"
    AGENT_ITERATION_COMPLETED = "agent_iteration.completed"
    AGENT_ITERATION_FAILED = "agent_iteration.failed"

    # ── Observation and Knowledge ────────────────────────────────────────────────
    OBSERVATION_STARTED = "observation.started"
    OBSERVATION_COMPLETED = "observation.completed"
    OBSERVATION_FAILED = "observation.failed"
    KNOWLEDGE_LOADED = "knowledge.loaded"
    COGNITIVE_ANALYSIS_COMPLETED = "cognitive_analysis.completed"
    INFORMATION_GAP_DETECTED = "information_gap.detected"
    QUESTION_CREATED = "question.created"
    QUESTION_ANSWERED = "question.answered"

    # ── Planning ────────────────────────────────────────────────────────────────
    WORKFLOW_PLAN_CREATED = "workflow_plan.created"
    WORKFLOW_PLAN_VALIDATED = "workflow_plan.validated"
    WORKFLOW_PLAN_REJECTED = "workflow_plan.rejected"
    WORKFLOW_PLAN_REPLANNED = "workflow_plan.replanned"

    # ── Policy, Approval, and Budget ────────────────────────────────────────────
    POLICY_EVALUATED = "policy.evaluated"
    POLICY_DENIED = "policy.denied"
    APPROVAL_REQUESTED = "approval.requested"
    APPROVAL_APPROVED = "approval.approved"
    APPROVAL_REJECTED = "approval.rejected"
    APPROVAL_EXPIRED = "approval.expired"
    BUDGET_RESERVED = "budget.reserved"
    BUDGET_CONSUMED = "budget.consumed"
    BUDGET_RELEASED = "budget.released"
    BUDGET_EXCEEDED = "budget.exceeded"

    # ── Execution and Validation ────────────────────────────────────────────────
    OPERATION_STARTED = "operation.started"
    OPERATION_COMPLETED = "operation.completed"
    OPERATION_FAILED = "operation.failed"
    VALIDATION_STARTED = "validation.started"
    VALIDATION_COMPLETED = "validation.completed"
    VALIDATION_FAILED = "validation.failed"

    # ── Recovery ────────────────────────────────────────────────────────────────
    RECOVERY_STARTED = "recovery.started"
    RECOVERY_RETRY_REQUESTED = "recovery.retry_requested"
    RECOVERY_REOBSERVE_REQUESTED = "recovery.reobserve_requested"
    RECOVERY_REPLAN_REQUESTED = "recovery.replan_requested"
    RECOVERY_ROLLBACK_REQUESTED = "recovery.rollback_requested"
    RECOVERY_ROLLBACK_COMPLETED = "recovery.rollback_completed"
    RECOVERY_ESCALATED = "recovery.escalated"
    RECOVERY_FAILED = "recovery.failed"

    # ── Outcome and Memory ──────────────────────────────────────────────────────
    OUTCOME_EVALUATION_STARTED = "outcome_evaluation.started"
    OUTCOME_EVALUATION_COMPLETED = "outcome_evaluation.completed"
    KNOWLEDGE_UPDATE_PROPOSED = "knowledge_update.proposed"
    KNOWLEDGE_UPDATE_APPLIED = "knowledge_update.applied"
    MEMORY_UPDATE_PROPOSED = "memory_update.proposed"
    MEMORY_UPDATE_APPLIED = "memory_update.applied"
    OPERATIONAL_LESSON_CREATED = "operational_lesson.created"

    # ── Trace and Control ───────────────────────────────────────────────────────
    AGENT_TRACE_CREATED = "agent_trace.created"
    AGENT_TRACE_FINALIZED = "agent_trace.finalized"
    RUNTIME_WARNING = "runtime.warning"
    RUNTIME_ERROR = "runtime.error"
    RUNTIME_KILL_SWITCH_ACTIVATED = "runtime.kill_switch_activated"


EVENT_TYPE_CATEGORY_MAP: dict[str, EventTypeCategory] = {
    # Goals
    EventType.GOAL_CREATED: EventTypeCategory.GOAL,
    EventType.GOAL_UPDATED: EventTypeCategory.GOAL,
    EventType.GOAL_PRIORITIZED: EventTypeCategory.GOAL,
    EventType.GOAL_BLOCKED: EventTypeCategory.GOAL,
    EventType.GOAL_PAUSED: EventTypeCategory.GOAL,
    EventType.GOAL_RESUMED: EventTypeCategory.GOAL,
    EventType.GOAL_CANCELLED: EventTypeCategory.GOAL,
    EventType.GOAL_COMPLETED: EventTypeCategory.GOAL,
    EventType.GOAL_FAILED: EventTypeCategory.GOAL,
    # Runtime
    EventType.AGENT_RUN_CREATED: EventTypeCategory.RUNTIME,
    EventType.AGENT_RUN_STARTED: EventTypeCategory.RUNTIME,
    EventType.AGENT_RUN_STATUS_CHANGED: EventTypeCategory.RUNTIME,
    EventType.AGENT_RUN_PAUSED: EventTypeCategory.RUNTIME,
    EventType.AGENT_RUN_RESUMED: EventTypeCategory.RUNTIME,
    EventType.AGENT_RUN_CANCELLED: EventTypeCategory.RUNTIME,
    EventType.AGENT_RUN_COMPLETED: EventTypeCategory.RUNTIME,
    EventType.AGENT_RUN_FAILED: EventTypeCategory.RUNTIME,
    # Iterations
    EventType.AGENT_ITERATION_STARTED: EventTypeCategory.ITERATION,
    EventType.AGENT_ITERATION_COMPLETED: EventTypeCategory.ITERATION,
    EventType.AGENT_ITERATION_FAILED: EventTypeCategory.ITERATION,
    # Observation and Knowledge
    EventType.OBSERVATION_STARTED: EventTypeCategory.OBSERVATION,
    EventType.OBSERVATION_COMPLETED: EventTypeCategory.OBSERVATION,
    EventType.OBSERVATION_FAILED: EventTypeCategory.OBSERVATION,
    EventType.KNOWLEDGE_LOADED: EventTypeCategory.KNOWLEDGE,
    EventType.COGNITIVE_ANALYSIS_COMPLETED: EventTypeCategory.KNOWLEDGE,
    EventType.INFORMATION_GAP_DETECTED: EventTypeCategory.OBSERVATION,
    EventType.QUESTION_CREATED: EventTypeCategory.OBSERVATION,
    EventType.QUESTION_ANSWERED: EventTypeCategory.OBSERVATION,
    # Planning
    EventType.WORKFLOW_PLAN_CREATED: EventTypeCategory.PLANNING,
    EventType.WORKFLOW_PLAN_VALIDATED: EventTypeCategory.PLANNING,
    EventType.WORKFLOW_PLAN_REJECTED: EventTypeCategory.PLANNING,
    EventType.WORKFLOW_PLAN_REPLANNED: EventTypeCategory.PLANNING,
    # Policy, Approval, and Budget
    EventType.POLICY_EVALUATED: EventTypeCategory.POLICY,
    EventType.POLICY_DENIED: EventTypeCategory.POLICY,
    EventType.APPROVAL_REQUESTED: EventTypeCategory.APPROVAL,
    EventType.APPROVAL_APPROVED: EventTypeCategory.APPROVAL,
    EventType.APPROVAL_REJECTED: EventTypeCategory.APPROVAL,
    EventType.APPROVAL_EXPIRED: EventTypeCategory.APPROVAL,
    EventType.BUDGET_RESERVED: EventTypeCategory.BUDGET,
    EventType.BUDGET_CONSUMED: EventTypeCategory.BUDGET,
    EventType.BUDGET_RELEASED: EventTypeCategory.BUDGET,
    EventType.BUDGET_EXCEEDED: EventTypeCategory.BUDGET,
    # Execution and Validation
    EventType.OPERATION_STARTED: EventTypeCategory.EXECUTION,
    EventType.OPERATION_COMPLETED: EventTypeCategory.EXECUTION,
    EventType.OPERATION_FAILED: EventTypeCategory.EXECUTION,
    EventType.VALIDATION_STARTED: EventTypeCategory.VALIDATION,
    EventType.VALIDATION_COMPLETED: EventTypeCategory.VALIDATION,
    EventType.VALIDATION_FAILED: EventTypeCategory.VALIDATION,
    # Recovery
    EventType.RECOVERY_STARTED: EventTypeCategory.RECOVERY,
    EventType.RECOVERY_RETRY_REQUESTED: EventTypeCategory.RECOVERY,
    EventType.RECOVERY_REOBSERVE_REQUESTED: EventTypeCategory.RECOVERY,
    EventType.RECOVERY_REPLAN_REQUESTED: EventTypeCategory.RECOVERY,
    EventType.RECOVERY_ROLLBACK_REQUESTED: EventTypeCategory.RECOVERY,
    EventType.RECOVERY_ROLLBACK_COMPLETED: EventTypeCategory.RECOVERY,
    EventType.RECOVERY_ESCALATED: EventTypeCategory.RECOVERY,
    EventType.RECOVERY_FAILED: EventTypeCategory.RECOVERY,
    # Outcome and Memory
    EventType.OUTCOME_EVALUATION_STARTED: EventTypeCategory.OUTCOME,
    EventType.OUTCOME_EVALUATION_COMPLETED: EventTypeCategory.OUTCOME,
    EventType.KNOWLEDGE_UPDATE_PROPOSED: EventTypeCategory.MEMORY,
    EventType.KNOWLEDGE_UPDATE_APPLIED: EventTypeCategory.MEMORY,
    EventType.MEMORY_UPDATE_PROPOSED: EventTypeCategory.MEMORY,
    EventType.MEMORY_UPDATE_APPLIED: EventTypeCategory.MEMORY,
    EventType.OPERATIONAL_LESSON_CREATED: EventTypeCategory.MEMORY,
    # Trace and Control
    EventType.AGENT_TRACE_CREATED: EventTypeCategory.TRACE,
    EventType.AGENT_TRACE_FINALIZED: EventTypeCategory.TRACE,
    EventType.RUNTIME_WARNING: EventTypeCategory.RUNTIME_SYSTEM,
    EventType.RUNTIME_ERROR: EventTypeCategory.RUNTIME_SYSTEM,
    EventType.RUNTIME_KILL_SWITCH_ACTIVATED: EventTypeCategory.RUNTIME_SYSTEM,
}


def get_event_category(event_type: str) -> EventTypeCategory:
    """Get the category for an event type."""
    if event_type not in EVENT_TYPE_CATEGORY_MAP:
        return EventTypeCategory.RUNTIME_SYSTEM
    return EVENT_TYPE_CATEGORY_MAP[event_type]


def is_registered_event_type(event_type: str) -> bool:
    """Check if an event type is registered."""
    return event_type in EVENT_TYPE_CATEGORY_MAP


def get_all_registered_event_types() -> list[str]:
    """Get all registered event types."""
    return list(EVENT_TYPE_CATEGORY_MAP.keys())
