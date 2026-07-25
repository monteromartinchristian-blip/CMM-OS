"""Phase 9.1 – Agent Runtime Enumerations.

Defines the core enums for agent runtime status, decision types, and result outcomes.
"""

from __future__ import annotations

from enum import Enum


class AgentRuntimeStatus(str, Enum):
    """General runtime execution states for an autonomous agent run."""

    CREATED = "created"
    INITIALIZING = "initializing"
    OBSERVING = "observing"
    REASONING = "reasoning"
    WAITING_FOR_USER = "waiting_for_user"
    WAITING_FOR_RESOURCE = "waiting_for_resource"
    PLANNING = "planning"
    WAITING_FOR_APPROVAL = "waiting_for_approval"
    EXECUTING = "executing"
    VALIDATING = "validating"
    EVALUATING = "evaluating"
    RECOVERING = "recovering"
    PAUSED = "paused"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"
    ABORTED = "aborted"


class RuntimeDecisionType(str, Enum):
    """Structured decision types emitted during runtime step transitions."""

    OBSERVE = "observe"
    LOAD_KNOWLEDGE = "load_knowledge"
    REASON = "reason"
    ASK_USER = "ask_user"
    LOAD_RESOURCE = "load_resource"
    SEARCH = "search"
    PLAN = "plan"
    EXECUTE = "execute"
    VALIDATE = "validate"
    EVALUATE = "evaluate"
    CONTINUE = "continue"
    RETRY = "retry"
    REPLAN = "replan"
    ROLLBACK = "rollback"
    PAUSE = "pause"
    ESCALATE = "escalate"
    COMPLETE = "complete"
    FAIL = "fail"
    ABORT = "abort"


class AgentResultOutcome(str, Enum):
    """High-level outcome status for an agent run result."""

    SUCCESS = "success"
    PARTIAL_SUCCESS = "partial_success"
    FAILURE = "failure"
    CANCELLED = "cancelled"
    ABORTED = "aborted"


# ── Phase 9.2 – Goal System Enumerations ──────────────────────────────────────


class GoalStatus(str, Enum):
    """Minimum required execution and lifecycle states for an operational Goal."""

    PROPOSED = "proposed"
    ACCEPTED = "accepted"
    ACTIVE = "active"
    PLANNING = "planning"
    IN_PROGRESS = "in_progress"
    WAITING_FOR_USER = "waiting_for_user"
    WAITING_FOR_RESOURCE = "waiting_for_resource"
    WAITING_FOR_APPROVAL = "waiting_for_approval"
    BLOCKED = "blocked"
    PAUSED = "paused"
    COMPLETED = "completed"
    PARTIALLY_COMPLETED = "partially_completed"
    FAILED = "failed"
    ABANDONED = "abandoned"
    CANCELLED = "cancelled"
    SUPERSEDED = "superseded"


class GoalKind(str, Enum):
    """Minimum required functional categories for an operational Goal."""

    INFORMATION = "information"
    ANALYSIS = "analysis"
    PLANNING = "planning"
    TRANSFORMATION = "transformation"
    VALIDATION = "validation"
    MAINTENANCE = "maintenance"
    MONITORING = "monitoring"
    RESEARCH = "research"
    DOCUMENTATION = "documentation"
    INTEGRATION = "integration"
    REMEDIATION = "remediation"
    OPTIMIZATION = "optimization"
    PROJECT_IMPROVEMENT = "project_improvement"
    PERSONAL = "personal"
    DOMAIN_SPECIFIC = "domain_specific"
    RECURRING = "recurring"
    COMPOSITE = "composite"


class SuccessCriterionStatus(str, Enum):
    """Evaluation status states for a success criterion."""

    PENDING = "pending"
    SATISFIED = "satisfied"
    PARTIALLY_SATISFIED = "partially_satisfied"
    UNSATISFIED = "unsatisfied"
    NOT_EVALUABLE = "not_evaluable"
    WAIVED = "waived"


class SuccessCriterionKind(str, Enum):
    """Functional types of success criteria."""

    STATE = "state"
    VALIDATION = "validation"
    METRIC = "metric"
    ARTIFACT = "artifact"
    KNOWLEDGE = "knowledge"
    USER_CONFIRMATION = "user_confirmation"
    WORKFLOW_COMPLETION = "workflow_completion"
    OPERATION_RESULT = "operation_result"
    TEMPORAL = "temporal"
    COMPOSITE = "composite"


class GoalConstraintKind(str, Enum):
    """Functional categories for goal constraints."""

    TIME = "time"
    COST = "cost"
    OPERATION = "operation"
    PERMISSION = "permission"
    SAFETY = "safety"
    DOMAIN = "domain"
    RESOURCE = "resource"
    QUALITY = "quality"
    LEGAL = "legal"
    PRIVACY = "privacy"
    USER_DEFINED = "user_defined"
    TECHNICAL = "technical"


class GoalDependencyType(str, Enum):
    """Relationship categories between goals."""

    REQUIRES_COMPLETION = "requires_completion"
    REQUIRES_PARTIAL_RESULT = "requires_partial_result"
    REQUIRES_KNOWLEDGE = "requires_knowledge"
    REQUIRES_RESOURCE = "requires_resource"
    CONFLICTS_WITH = "conflicts_with"
    ENABLES = "enables"
    SUPERSEDES = "supersedes"
    RELATED_TO = "related_to"


# ── Phase 9.3 – Goal Intake Enumerations ──────────────────────────────────────


class GoalProposalStatus(str, Enum):
    """Lifecycle states for a GoalProposal."""

    CREATED = "created"
    NORMALIZING = "normalizing"
    READY = "ready"
    REQUIRES_CLARIFICATION = "requires_clarification"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    EXPIRED = "expired"
    FAILED = "failed"


class GoalSource(str, Enum):
    """Origin sources for goal intake."""

    USER_MESSAGE = "user_message"
    WORKFLOW = "workflow"
    AGENT = "agent"
    KERNEL_EVENT = "kernel_event"
    VALIDATION_RESULT = "validation_result"
    ERROR_DETECTION = "error_detection"
    RECURRING_GOAL = "recurring_goal"
    MAINTENANCE_POLICY = "maintenance_policy"
    PERIODIC_REVIEW = "periodic_review"
    DOMAIN = "domain"
    EXTERNAL_INTEGRATION = "external_integration"
    SUBGOAL = "subgoal"
    RECOVERY = "recovery"


class GoalAmbiguityKind(str, Enum):
    """Categories of ambiguity in goal proposals."""

    OBJECTIVE = "objective"
    SCOPE = "scope"
    SUCCESS_CRITERIA = "success_criteria"
    CONSTRAINT = "constraint"
    DEADLINE = "deadline"
    PRIORITY = "priority"
    OWNER = "owner"
    RESOURCE = "resource"
    DEPENDENCY = "dependency"
    SENSITIVITY = "sensitivity"
    PERMISSION = "permission"
    AUTONOMY = "autonomy"
    CONFLICT = "conflict"
    DUPLICATE = "duplicate"


class GoalIntakeDecisionType(str, Enum):
    """Decision types produced during goal intake and normalization."""

    ACCEPT = "accept"
    REQUEST_CLARIFICATION = "request_clarification"
    REJECT = "reject"
    DEFER = "defer"
    CREATE_PROPOSED_GOAL = "create_proposed_goal"
    MERGE_WITH_EXISTING = "merge_with_existing"


# ── Phase 9.4 – Observation Engine Enumerations ───────────────────────────────


class ObservationStatus(str, Enum):
    """Lifecycle and execution status of an observation or observation snapshot."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    PARTIAL = "partial"
    DEGRADED = "degraded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class ObservationKind(str, Enum):
    """Functional categories for individual observations."""

    STATE = "state"
    METRIC = "metric"
    STRUCTURE = "structure"
    EVENT = "event"
    CHANGE = "change"
    VALIDATION = "validation"
    MEMORY = "memory"
    HEALTH = "health"
    GOAL = "goal"
    REPOSITORY = "repository"
    GIT = "git"
    CONFIGURATION = "configuration"
    EXTERNAL = "external"


class ObservedChangeKind(str, Enum):
    """Types of state changes detected between snapshots or observations."""

    CREATED = "created"
    MODIFIED = "modified"
    DELETED = "deleted"
    RENAMED = "renamed"
    MOVED = "moved"
    STATUS_CHANGED = "status_changed"
    VALIDATION_CHANGED = "validation_changed"
    METRIC_CHANGED = "metric_changed"
    DEPENDENCY_CHANGED = "dependency_changed"
    KNOWLEDGE_CHANGED = "knowledge_changed"
    PERMISSION_CHANGED = "permission_changed"
    CONFIGURATION_CHANGED = "configuration_changed"
    EXTERNAL_STATE_CHANGED = "external_state_changed"


class ObservationSignificance(str, Enum):
    """Impact or significance level of an observed change or state."""

    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# Alias for backward compatibility / specification equivalence
Significance = ObservationSignificance


class ObserverStatus(str, Enum):
    """Lifecycle and operational state of an individual Observer."""

    REGISTERED = "registered"
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    RUNNING = "running"
    COMPLETED = "completed"
    DEGRADED = "degraded"
    FAILED = "failed"
    DISABLED = "disabled"


# ── Phase 9.5 – Cognitive Adapter Enumerations ───────────────────────────────


class AgentCognitiveStatus(str, Enum):
    """Execution and outcome status for agent cognitive analysis."""

    PENDING = "pending"
    PREPARING = "preparing"
    REASONING = "reasoning"
    WAITING_FOR_USER = "waiting_for_user"
    WAITING_FOR_RESOURCE = "waiting_for_resource"
    COMPLETED = "completed"
    PARTIAL = "partial"
    INSUFFICIENT_INFORMATION = "insufficient_information"
    BLOCKED = "blocked"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AgentCognitiveDecision(str, Enum):
    """Actionable runtime decisions translated from cognitive analysis."""

    CONTINUE_REASONING = "continue_reasoning"
    ASK_USER = "ask_user"
    LOAD_RESOURCE = "load_resource"
    SEARCH = "search"
    PLAN = "plan"
    PAUSE = "pause"
    ESCALATE = "escalate"
    COMPLETE_WITHOUT_ACTION = "complete_without_action"
    INSUFFICIENT_INFORMATION = "insufficient_information"
    FAIL = "fail"


class CognitiveSessionMode(str, Enum):
    """Session management modes for cognitive execution."""

    NEW = "new"
    RESUME = "resume"
    FORK = "fork"
    STATELESS = "stateless"


class CognitiveResourceStrategy(str, Enum):
    """Resource aggregation strategies for building reasoning context."""

    OBSERVATIONS_ONLY = "observations_only"
    KNOWLEDGE_ONLY = "knowledge_only"
    OBSERVATIONS_AND_KNOWLEDGE = "observations_and_knowledge"
    EXPLICIT_RESOURCES = "explicit_resources"
    AUTOMATIC = "automatic"
