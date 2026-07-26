"""Phase 9.1 – Agent Runtime Enumerations.

Defines the core enums for agent runtime status, decision types, and result outcomes.
"""

from __future__ import annotations

from enum import Enum, IntEnum


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


# ── Phase 9.6 – Information Acquisition Enumerations ──────────────────────────


class InformationAcquisitionStrategy(str, Enum):
    """Available strategies for acquiring information to resolve a gap."""

    ASK_USER = "ask_user"
    LOAD_INTERNAL_RESOURCE = "load_internal_resource"
    SEARCH_KNOWLEDGE = "search_knowledge"
    SEARCH_REPOSITORY = "search_repository"
    SEARCH_EXTERNAL_SOURCE = "search_external_source"
    INFER_WITH_PERMISSION = "infer_with_permission"
    REQUEST_HUMAN_REVIEW = "request_human_review"
    ACCEPT_UNCERTAINTY = "accept_uncertainty"
    PAUSE = "pause"
    ABORT = "abort"


class InformationAcquisitionStatus(str, Enum):
    """Status lifecycle for an information acquisition process."""

    PENDING = "pending"
    EVALUATING = "evaluating"
    SELECTED = "selected"
    WAITING_FOR_USER = "waiting_for_user"
    WAITING_FOR_RESOURCE = "waiting_for_resource"
    SEARCHING = "searching"
    COMPLETED = "completed"
    PARTIAL = "partial"
    BLOCKED = "blocked"
    FAILED = "failed"
    CANCELLED = "cancelled"


class InformationAcquisitionSource(str, Enum):
    """Origin sources from which information can be acquired."""

    USER = "user"
    KNOWLEDGE_STORE = "knowledge_store"
    REPOSITORY = "repository"
    MEMORY = "memory"
    OBSERVATION = "observation"
    INTERNAL_SERVICE = "internal_service"
    EXTERNAL_SOURCE = "external_source"
    HUMAN_REVIEWER = "human_reviewer"
    INFERENCE = "inference"
    UNKNOWN = "unknown"


class InformationAcquisitionRisk(str, Enum):
    """Risk levels associated with information acquisition strategies."""

    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class InformationAcquisitionDecisionType(str, Enum):
    """Actionable decision types emitted by the Information Acquisition Resolver."""

    SELECT_STRATEGY = "select_strategy"
    ASK_USER = "ask_user"
    LOAD_RESOURCE = "load_resource"
    SEARCH = "search"
    INFER = "infer"
    REQUEST_HUMAN_REVIEW = "request_human_review"
    ACCEPT_UNCERTAINTY = "accept_uncertainty"
    PAUSE = "pause"
    ABORT = "abort"


# ── Phase 9.7 – Workflow Planner Adapter Enumerations ─────────────────────────


class AgentPlanningStatus(str, Enum):
    """Execution status for an agent planning process."""

    PENDING = "pending"
    PREPARING = "preparing"
    PLANNING = "planning"
    VALIDATING = "validating"
    COMPLETED = "completed"
    PARTIAL = "partial"
    BLOCKED = "blocked"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AgentPlanningDecision(str, Enum):
    """Actionable decisions resulting from agent planning."""

    CREATE_PLAN = "create_plan"
    REPLAN = "replan"
    REQUEST_INFORMATION = "request_information"
    REQUEST_APPROVAL = "request_approval"
    PAUSE = "pause"
    COMPLETE_WITHOUT_WORKFLOW = "complete_without_workflow"
    FAIL = "fail"


class WorkflowPlanStatus(str, Enum):
    """Status lifecycle states for an AgentWorkflowPlan."""

    DRAFT = "draft"
    VALIDATING = "validating"
    VALID = "valid"
    INVALID = "invalid"
    SUPERSEDED = "superseded"
    APPROVED = "approved"
    READY = "ready"
    BLOCKED = "blocked"
    CANCELLED = "cancelled"
    COMPLETED = "completed"
    FAILED = "failed"


class WorkflowPlanValidationStatus(str, Enum):
    """Validation status states for a workflow plan."""

    PENDING = "pending"
    PASSED = "passed"
    PASSED_WITH_WARNINGS = "passed_with_warnings"
    FAILED = "failed"
    BLOCKED = "blocked"


class WorkflowPlanNodeKind(str, Enum):
    """Functional node kinds inside an AgentWorkflowPlan DAG."""

    TASK = "task"
    OPERATION = "operation"
    VALIDATION = "validation"
    APPROVAL = "approval"
    CHECKPOINT = "checkpoint"
    DECISION = "decision"
    WAIT = "wait"
    COMPLETION = "completion"


class WorkflowPlanRisk(str, Enum):
    """Risk levels for workflow plans, nodes, and operations."""

    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class WorkflowPlanChangeReason(str, Enum):
    """Triggers and reasons for replanning or versioning a workflow plan."""

    GOAL_CHANGED = "goal_changed"
    NEW_INFORMATION = "new_information"
    OPERATION_FAILED = "operation_failed"
    VALIDATION_FAILED = "validation_failed"
    RESOURCE_CHANGED = "resource_changed"
    PERMISSION_CHANGED = "permission_changed"
    BUDGET_CHANGED = "budget_changed"
    APPROVAL_REJECTED = "approval_rejected"
    OUTCOME_DIVERGED = "outcome_diverged"
    SAFER_STRATEGY_FOUND = "safer_strategy_found"
    MANUAL_REQUEST = "manual_request"


# ── Phase 9.8 – Policy Engine Enumerations ────────────────────────────────────


class PolicyDecision(str, Enum):
    """Decision outcomes from Policy Engine evaluation."""

    ALLOW = "allow"
    DENY = "deny"
    ALLOW_WITH_RESTRICTIONS = "allow_with_restrictions"
    REQUIRE_APPROVAL = "require_approval"
    REQUIRE_VALIDATION = "require_validation"
    REQUIRE_INFORMATION = "require_information"
    PAUSE = "pause"
    NOT_APPLICABLE = "not_applicable"
    INDETERMINATE = "indeterminate"


class PolicyEvaluationStatus(str, Enum):
    """Evaluation status for policy evaluation requests and results."""

    PENDING = "pending"
    EVALUATING = "evaluating"
    COMPLETED = "completed"
    PARTIAL = "partial"
    BLOCKED = "blocked"
    FAILED = "failed"
    CANCELLED = "cancelled"


class PolicyEffect(str, Enum):
    """Consequence effects declared on policy rules and policies."""

    PERMIT = "permit"
    DENY = "deny"
    OBLIGATION = "obligation"
    ADVICE = "advice"
    RESTRICTION = "restriction"


class PolicyScope(str, Enum):
    """Granular target scopes for policies."""

    GLOBAL = "global"
    SYSTEM = "system"
    ENVIRONMENT = "environment"
    AGENT = "agent"
    GOAL = "goal"
    RUN = "run"
    WORKFLOW = "workflow"
    TASK = "task"
    OPERATION = "operation"
    RESOURCE = "resource"
    ACTOR = "actor"
    DOMAIN = "domain"


class PolicySubjectKind(str, Enum):
    """Categories of actors and execution entities subject to policy evaluation."""

    AGENT = "agent"
    USER = "user"
    SYSTEM = "system"
    ROLE = "role"
    SERVICE = "service"
    EXTERNAL = "external"


class PolicyResourceKind(str, Enum):
    """Categories of resources evaluated in policy checks."""

    FILE = "file"
    REPOSITORY = "repository"
    OPERATION = "operation"
    WORKFLOW = "workflow"
    GOAL = "goal"
    KNOWLEDGE = "knowledge"
    MEMORY = "memory"
    SYSTEM = "system"
    NETWORK = "network"
    EXTERNAL = "external"
    SECRET = "secret"
    ACQUISITION_STRATEGY = "acquisition_strategy"


class PolicyRiskLevel(str, Enum):
    """Risk classification levels for policy evaluation."""

    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class PolicySeverity(str, Enum):
    """Severity levels for violations, obligations, and restrictions."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    BLOCKING = "blocking"
    CRITICAL = "critical"


class PolicyConditionOperator(str, Enum):
    """Comparison operators supported by PolicyCondition."""

    EQUALS = "equals"
    NOT_EQUALS = "not_equals"
    IN = "in"
    NOT_IN = "not_in"
    CONTAINS = "contains"
    NOT_CONTAINS = "not_contains"
    GREATER_THAN = "greater_than"
    GREATER_THAN_OR_EQUAL = "greater_than_or_equal"
    LESS_THAN = "less_than"
    LESS_THAN_OR_EQUAL = "less_than_or_equal"
    EXISTS = "exists"
    NOT_EXISTS = "not_exists"
    MATCHES = "matches"
    STARTS_WITH = "starts_with"
    ENDS_WITH = "ends_with"
    INTERSECTS = "intersects"
    SUBSET_OF = "subset_of"


class PolicyCombiningAlgorithm(str, Enum):
    """Combining algorithms for resolving policy evaluation decisions."""

    DENY_OVERRIDES = "deny_overrides"
    PERMIT_OVERRIDES = "permit_overrides"
    FIRST_APPLICABLE = "first_applicable"
    ONLY_ONE_APPLICABLE = "only_one_applicable"
    ORDERED_DENY_OVERRIDES = "ordered_deny_overrides"
    ORDERED_PERMIT_OVERRIDES = "ordered_permit_overrides"


class PolicyObligationKind(str, Enum):
    """Types of obligations that policies can enforce."""

    REQUIRE_VALIDATION = "require_validation"
    REQUIRE_APPROVAL = "require_approval"
    LOG_AUDIT = "log_audit"
    USE_CHECKPOINT = "use_checkpoint"
    LIMIT_SCOPE = "limit_scope"
    ENFORCE_ROLLBACK = "enforce_rollback"
    MASK_DATA = "mask_data"
    REQUEST_INFORMATION = "request_information"
    RESTRICT_TIMEOUT = "restrict_timeout"
    RESTRICT_COST = "restrict_cost"
    LIMIT_OPERATIONS = "limit_operations"
    REQUIRE_HUMAN_INTERVENTION = "require_human_intervention"
    STOP_ON_CONDITION_CHANGE = "stop_on_condition_change"


class PolicyFailureMode(str, Enum):
    """Fail-safe default decision when evaluation encounters errors or indeterminate state."""

    DENY = "deny"
    PAUSE = "pause"
    REQUIRE_APPROVAL = "require_approval"


# ── Phase 9.9 – Autonomy Level Enumerations ──────────────────────────────────


class AgentAutonomyLevel(IntEnum):
    """Canonical autonomy levels for AgentDefinition and AgentRun.

    Implemented as IntEnum to preserve backward compatibility with the
    integer-based construction patterns used throughout the codebase:

        AgentDefinition(..., autonomy_level=2)
        AgentRun(..., autonomy_level=3)
    """

    ANALYZE_ONLY = 0
    PROPOSE_ACTIONS = 1
    REVERSIBLE_EXECUTION = 2
    SUPERVISED_AUTONOMY = 3
    POLICY_BOUNDED_AUTONOMY = 4


class AutonomyDecision(str, Enum):
    """Explicit, structured decisions emitted by the Autonomy Evaluator.

    Autonomy decisions are intentionally distinct from ``PolicyDecision``.
    Policy Engine can deny an operation that autonomy would otherwise allow,
    but autonomy itself is a binding, structural constraint: an operation
    denied by autonomy cannot be elevated solely by a permissive policy.
    """

    ALLOW = "allow"
    DENY = "deny"
    REQUIRE_APPROVAL = "require_approval"
    REQUIRE_VALIDATION = "require_validation"
    REQUIRE_ROLLBACK = "require_rollback"
    PAUSE = "pause"


class AutonomyCapability(str, Enum):
    """Canonical capabilities addressable by the Autonomy Evaluator.

    Capabilities are explicit, non-ambiguous verbs. They are evaluated
    against the structured characteristics of an operation (mutation,
    reversibility, externality, sensitivity, …) and the current
    autonomy level. Capabilities are not operations: a single operation
    may require multiple capabilities depending on its effects.
    """

    OBSERVE = "observe"
    LOAD_KNOWLEDGE = "load_knowledge"
    REASON = "reason"
    RECOMMEND = "recommend"
    PROPOSE_PLAN = "propose_plan"
    PROPOSE_OPERATION = "propose_operation"
    REQUEST_APPROVAL = "request_approval"
    EXECUTE_READ_ONLY = "execute_read_only"
    EXECUTE_VALIDATION = "execute_validation"
    EXECUTE_REVERSIBLE = "execute_reversible"
    EXECUTE_WORKFLOW = "execute_workflow"
    EXECUTE_IRREVERSIBLE = "execute_irreversible"
    PUBLISH = "publish"
    COMMUNICATE_EXTERNAL = "communicate_external"
    SPEND_BUDGET = "spend_budget"
    MODIFY_PERMISSIONS = "modify_permissions"
    MODIFY_POLICY = "modify_policy"


class AutonomyTransitionReason(str, Enum):
    """Canonical reasons for an autonomy level transition."""

    INITIAL_LEVEL = "initial_level"
    MANUAL_REDUCTION = "manual_reduction"
    MANUAL_ESCALATION = "manual_escalation"
    POLICY_VIOLATION = "policy_violation"
    APPROVAL_REJECTED = "approval_rejected"
    VALIDATION_FAILED = "validation_failed"
    ROLLBACK_TRIGGERED = "rollback_triggered"
    RECOVERY_MODE = "recovery_mode"
    FAILSAFE = "failsafe"
    SYSTEM_REQUEST = "system_request"


# ── Phase 9.10 – Human Approval System Enumerations ─────────────────────────


class ApprovalRequestStatus(str, Enum):
    """Lifecycle and resolution status states for an ApprovalRequest."""

    PENDING = "pending"
    APPROVED = "approved"
    APPROVED_WITH_CHANGES = "approved_with_changes"
    REJECTED = "rejected"
    POSTPONED = "postponed"
    EXPIRED = "expired"
    CANCELLED = "cancelled"
    SUPERSEDED = "superseded"


class ApprovalDecisionType(str, Enum):
    """Explicit, structured decision types submitted by an authorized human actor."""

    APPROVE = "approve"
    APPROVE_WITH_CHANGES = "approve_with_changes"
    REJECT = "reject"
    POSTPONE = "postpone"
    CANCEL = "cancel"


class ApprovalRequirementSource(str, Enum):
    """Origin sources that can mandate a human approval requirement."""

    POLICY = "policy"
    AUTONOMY = "autonomy"
    WORKFLOW = "workflow"
    OPERATION = "operation"
    VALIDATION = "validation"
    SECURITY = "security"
    BUDGET = "budget"
    RUNTIME = "runtime"
    MANUAL = "manual"


# ── Phase 9.11 – Action Budget Enumerations ─────────────────────────────────


class BudgetResourceType(str, Enum):
    """Structured resource types monitored and restricted by ActionBudget."""

    ITERATION = "iteration"
    OPERATION = "operation"
    WORKFLOW = "workflow"
    PLAN = "plan"
    REPLAN = "replan"
    RETRY = "retry"
    QUESTION = "question"
    EXTERNAL_CALL = "external_call"
    MODEL_CALL = "model_call"
    TOKEN = "token"
    COST = "cost"
    DURATION_SECONDS = "duration_seconds"
    PARALLEL_OPERATION = "parallel_operation"
    STORAGE_BYTES = "storage_bytes"
    MEMORY_WRITE = "memory_write"
    OBSERVATION = "observation"
    LOADED_RESOURCE = "loaded_resource"
    DATA_VOLUME_BYTES = "data_volume_bytes"


class ActionBudgetStatus(str, Enum):
    """Lifecycle and operational states for an ActionBudget."""

    ACTIVE = "active"
    WARNING = "warning"
    EXHAUSTED = "exhausted"
    PAUSED = "paused"
    INCREASED = "increased"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class BudgetReservationStatus(str, Enum):
    """Lifecycle states for a BudgetReservation."""

    RESERVED = "reserved"
    CONFIRMED = "confirmed"
    RELEASED = "released"
    EXPIRED = "expired"
    FAILED = "failed"
    CANCELLED = "cancelled"


class BudgetConsumptionOutcome(str, Enum):
    """Functional outcome classification for a confirmed budget consumption."""

    SUCCESS = "success"
    FAILURE = "failure"
    PARTIAL = "partial"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


class BudgetAdjustmentType(str, Enum):
    """Types of authorized adjustments to ActionBudget limits."""

    INCREASE = "increase"
    DECREASE = "decrease"
    RESET = "reset"


# ── Phase 9.12 – Agent Runtime Loop Enumerations ─────────────────────────────


class AgentIterationStatus(str, Enum):
    """Execution status states for an AgentIteration."""

    CREATED = "created"
    RUNNING = "running"
    WAITING = "waiting"
    PAUSED = "paused"
    COMPLETED = "completed"
    PARTIALLY_COMPLETED = "partially_completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RECOVERED = "recovered"


class RuntimeStep(str, Enum):
    """Operational steps executed during an Agent Runtime cycle."""

    LOAD_GOAL = "load_goal"
    VALIDATE_GOAL = "validate_goal"
    CHECK_DEPENDENCIES = "check_dependencies"
    OBSERVE = "observe"
    LOAD_KNOWLEDGE = "load_knowledge"
    REASON = "reason"
    RESOLVE_INFORMATION_GAPS = "resolve_information_gaps"
    DECIDE = "decide"
    PLAN = "plan"
    EVALUATE_POLICIES = "evaluate_policies"
    REQUEST_APPROVAL = "request_approval"
    RESERVE_BUDGET = "reserve_budget"
    EXECUTE = "execute"
    VALIDATE = "validate"
    EVALUATE_OUTCOME = "evaluate_outcome"
    UPDATE_GOAL = "update_goal"
    UPDATE_KNOWLEDGE = "update_knowledge"
    CONTINUE_CYCLE = "continue_cycle"
    RECOVER = "recover"
    COMPLETE = "complete"


class RuntimeStepStatus(str, Enum):
    """Execution status for a specific runtime step."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    SKIPPED = "skipped"
    WAITING = "waiting"
    FAILED = "failed"
    CANCELLED = "cancelled"


class RuntimeHealthStatus(str, Enum):
    """Health classification levels for an AgentRun heartbeat and process."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    STALLED = "stalled"
    ABANDONED = "abandoned"
    RECOVERING = "recovering"
    FAILED = "failed"


class RuntimeLockType(str, Enum):
    """Lock semantics supported by RuntimeLockManager."""

    SHARED = "shared"
    EXCLUSIVE = "exclusive"
    GOAL = "goal"
    RESOURCE = "resource"
    WRITE = "write"
    ROLLBACK = "rollback"
    COMPLETION = "completion"
    BUDGET = "budget"


class RuntimeLockStatus(str, Enum):
    """Lifecycle status states for a RuntimeLock."""

    ACTIVE = "active"
    RELEASED = "released"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


# ── Phase 9.13 – Operation Execution Enumerations ───────────────────────────


class AgentOperationExecutionStatus(str, Enum):
    """Lifecycle and execution status states for an AgentOperationExecution."""

    PENDING = "pending"
    VALIDATING = "validating"
    BLOCKED = "blocked"
    EXECUTING = "executing"
    COMPLETED = "completed"
    PARTIALLY_COMPLETED = "partially_completed"
    FAILED = "failed"
    VALIDATION_FAILED = "validation_failed"
    ROLLBACK_REQUIRED = "rollback_required"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"


class OperationEffectType(str, Enum):
    """Structured categories of operation effects and side effects."""

    READ = "read"
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    EXECUTE = "execute"
    PUBLISH = "publish"
    SEND = "send"
    PERMISSION_CHANGE = "permission_change"
    MEMORY_WRITE = "memory_write"
    EXTERNAL_CALL = "external_call"
    FINANCIAL_COMMITMENT = "financial_commitment"


class OperationReversibility(str, Enum):
    """Reversibility classification for an operation."""

    REVERSIBLE = "reversible"
    CONDITIONALLY_REVERSIBLE = "conditionally_reversible"
    IRREVERSIBLE = "irreversible"
    UNKNOWN = "unknown"


class OperationEnvironment(str, Enum):
    """Authorized environment targets for operation execution."""

    LOCAL = "local"
    CONTAINER = "container"
    SANDBOX = "sandbox"
    STAGING = "staging"
    PRODUCTION = "production"
    REMOTE = "remote"


# ── Phase 9.14 – Validation Integration Enumerations ──────────────────────────


class AgentValidationStage(str, Enum):
    """Lifecycle stages for agent operation validation execution."""

    PRE_EXECUTION = "pre_execution"
    POST_EXECUTION = "post_execution"
    PRE_COMMIT = "pre_commit"
    POST_ROLLBACK = "post_rollback"


class AgentValidationStatus(str, Enum):
    """Execution status states for an AgentValidationResult."""

    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    PASSED_WITH_WARNINGS = "passed_with_warnings"
    FAILED = "failed"
    BLOCKED = "blocked"
    ERROR = "error"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"


class AgentValidationDecision(str, Enum):
    """Explicit, closed decision outcomes resulting from validation evaluation."""

    CONTINUE = "continue"
    BLOCK = "block"
    RETRY = "retry"
    REPLAN = "replan"
    ROLLBACK = "rollback"
    ESCALATE = "escalate"
    PAUSE = "pause"
    ABORT = "abort"


class ValidationFailureClass(str, Enum):
    """Classification categories for validation findings and failures."""

    POLICY = "policy"
    FORMAT = "format"
    LINT = "lint"
    STATIC_ANALYSIS = "static_analysis"
    SYNTAX = "syntax"
    AST = "ast"
    UNIT_TEST = "unit_test"
    INTEGRATION_TEST = "integration_test"
    SECURITY = "security"
    COMMIT_GATE = "commit_gate"
    REGRESSION = "regression"
    INFRASTRUCTURE = "infrastructure"
    UNKNOWN = "unknown"


class ValidationRequirementKind(str, Enum):
    """Functional categories of validation requirements."""

    PREVENTATIVE = "preventative"
    SANITY = "sanity"
    SECURITY = "security"
    SYNTAX = "syntax"
    AST = "ast"
    LINT = "lint"
    UNIT_TEST = "unit_test"
    INTEGRATION_TEST = "integration_test"
    COMMIT_GATE = "commit_gate"
    POST_CONDITION = "post_condition"
    REGRESSION = "regression"
    CUSTOM = "custom"


# ── Phase 9.15 – Checkpoints and Transaction Boundaries Enumerations ───────────


class CheckpointStatus(str, Enum):
    """Lifecycle and execution status states for a Runtime Checkpoint."""

    CREATING = "creating"
    ACTIVE = "active"
    RESTORING = "restoring"
    RESTORED = "restored"
    EXPIRED = "expired"
    INVALID = "invalid"
    DELETED = "deleted"
    FAILED = "failed"


class CheckpointIntegrityStatus(str, Enum):
    """Integrity verification states for a Checkpoint."""

    UNKNOWN = "unknown"
    VALID = "valid"
    INVALID = "invalid"
    STALE = "stale"
    MISSING_RESOURCE = "missing_resource"
    VERSION_MISMATCH = "version_mismatch"
    CORRUPTED = "corrupted"


class TransactionBoundaryKind(str, Enum):
    """Functional categories of transaction boundaries and failure semantics."""

    ATOMIC = "atomic"
    COMPENSABLE = "compensable"
    CHECKPOINT_SEQUENCE = "checkpoint_sequence"
    INDEPENDENT = "independent"
    IRREVERSIBLE_WITH_APPROVAL = "irreversible_with_approval"


class TransactionStatus(str, Enum):
    """Lifecycle execution status states for a Runtime Transaction."""

    PENDING = "pending"
    ACTIVE = "active"
    COMMITTING = "committing"
    COMMITTED = "committed"
    ROLLING_BACK = "rolling_back"
    ROLLED_BACK = "rolled_back"
    COMPENSATING = "compensating"
    COMPENSATED = "compensated"
    FAILED = "failed"
    PARTIALLY_RESTORED = "partially_restored"
    ABORTED = "aborted"


class RestorationStatus(str, Enum):
    """Outcome status states for checkpoint restoration operations."""

    PENDING = "pending"
    RUNNING = "running"
    RESTORED = "restored"
    PARTIALLY_RESTORED = "partially_restored"
    FAILED = "failed"
    BLOCKED = "blocked"
    VALIDATION_FAILED = "validation_failed"


class OperationRecoveryKind(str, Enum):
    """Classification of recovery characteristics for a given operation."""

    REVERSIBLE = "reversible"
    COMPENSABLE = "compensable"
    IRREVERSIBLE = "irreversible"
    UNKNOWN = "unknown"


# ── Phase 9.16 – Recovery Manager Enumerations ────────────────────────────────


class RecoveryStrategy(str, Enum):
    """Explicit recovery strategies available to the Recovery Decision Engine."""

    RETRY = "retry"
    RETRY_WITH_MODIFIED_PARAMETERS = "retry_with_modified_parameters"
    RETRY_LATER = "retry_later"
    REOBSERVE = "reobserve"
    RELOAD_RESOURCE = "reload_resource"
    RERUN_VALIDATION = "rerun_validation"
    REPLAN = "replan"
    ROLLBACK = "rollback"
    COMPENSATE = "compensate"
    ASK_USER = "ask_user"
    REQUEST_APPROVAL = "request_approval"
    ESCALATE = "escalate"
    PAUSE = "pause"
    SKIP_OPTIONAL_TASK = "skip_optional_task"
    COMPLETE_PARTIALLY = "complete_partially"
    ABORT = "abort"
    FAIL = "fail"


class RecoveryStatus(str, Enum):
    """Execution and lifecycle status states for a Recovery Context or Execution."""

    PENDING = "pending"
    DECIDING = "deciding"
    WAITING = "waiting"
    EXECUTING = "executing"
    SUCCEEDED = "succeeded"
    PARTIALLY_SUCCEEDED = "partially_succeeded"
    BLOCKED = "blocked"
    ESCALATED = "escalated"
    ABORTED = "aborted"
    FAILED = "failed"


class RecoveryReasonCode(str, Enum):
    """Reason codes motivating a RecoveryDecision or Classification."""

    TRANSIENT_ERROR = "transient_error"
    VALIDATION_FAILED = "validation_failed"
    RESOURCE_STALE = "resource_stale"
    RESOURCE_MISSING = "resource_missing"
    RESOURCE_VERSION_MISMATCH = "resource_version_mismatch"
    PERMISSION_MISSING = "permission_missing"
    APPROVAL_REQUIRED = "approval_required"
    CHECKPOINT_AVAILABLE = "checkpoint_available"
    CHECKPOINT_INVALID = "checkpoint_invalid"
    ROLLBACK_AVAILABLE = "rollback_available"
    ROLLBACK_FAILED = "rollback_failed"
    COMPENSATION_AVAILABLE = "compensation_available"
    COMPENSATION_FAILED = "compensation_failed"
    RETRIES_EXHAUSTED = "retries_exhausted"
    BUDGET_EXHAUSTED = "budget_exhausted"
    INCONSISTENT_STATE = "inconsistent_state"
    PARTIAL_SIDE_EFFECTS = "partial_side_effects"
    NON_RETRYABLE_ERROR = "non_retryable_error"
    HIGH_IMPACT_DECISION = "high_impact_decision"
    POLICY_CONFLICT = "policy_conflict"
    CONTRADICTION_UNRESOLVED = "contradiction_unresolved"
    PROFESSIONAL_JUDGMENT_REQUIRED = "professional_judgment_required"
    UNKNOWN_FAILURE = "unknown_failure"


class BackoffStrategy(str, Enum):
    """Backoff delay calculation strategy for retries."""

    NONE = "none"
    CONSTANT = "constant"
    LINEAR = "linear"
    EXPONENTIAL = "exponential"


class RecoveryErrorClass(str, Enum):
    """High-level classification categories for Agent Runtime errors."""

    TRANSIENT = "transient"
    PERMANENT = "permanent"
    VALIDATION = "validation"
    PERMISSION = "permission"
    CONCURRENCY = "concurrency"
    RESOURCE = "resource"
    BUDGET = "budget"
    POLICY = "policy"
    EXTERNAL_SIDE_EFFECT = "external_side_effect"
    INCONSISTENT_STATE = "inconsistent_state"
    UNKNOWN = "unknown"


class EscalationTarget(str, Enum):
    """Target roles for recovery escalation."""

    USER = "user"
    OPERATOR = "operator"
    APPROVER = "approver"
    DOMAIN_EXPERT = "domain_expert"
    SYSTEM_ADMINISTRATOR = "system_administrator"


# ── Phase 9.17 – Outcome Evaluation Enumerations ───────────────────────────


class OutcomeEvaluationStatus(str, Enum):
    """Status lifecycle of an Outcome Evaluation."""

    PENDING = "pending"
    EVALUATING = "evaluating"
    COMPLETED = "completed"
    BLOCKED = "blocked"
    INCONCLUSIVE = "inconclusive"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Outcome(str, Enum):
    """Satisfaction outcome of a Goal evaluation."""

    SUCCESS = "success"
    PARTIAL_SUCCESS = "partial_success"
    NO_CHANGE = "no_change"
    FAILURE = "failure"
    REGRESSION = "regression"
    INCONCLUSIVE = "inconclusive"
    CANCELLED = "cancelled"


class GoalCompletionDecisionKind(str, Enum):
    """Decision kind determining the terminal or next lifecycle action for a Goal."""

    COMPLETE = "complete"
    COMPLETE_PARTIALLY = "complete_partially"
    CONTINUE = "continue"
    RETRY = "retry"
    REPLAN = "replan"
    ROLLBACK = "rollback"
    PAUSE = "pause"
    ESCALATE = "escalate"
    FAIL = "fail"


class CriterionEvaluationStatus(str, Enum):
    """Evaluation status of a specific Success Criterion."""

    SATISFIED = "satisfied"
    UNSATISFIED = "unsatisfied"
    PARTIALLY_SATISFIED = "partially_satisfied"
    WAIVED = "waived"
    NOT_EVALUATED = "not_evaluated"
    INCONCLUSIVE = "inconclusive"
    BLOCKED = "blocked"


class CriterionImportance(str, Enum):
    """Importance level of a Success Criterion."""

    MANDATORY = "mandatory"
    REQUIRED = "required"
    OPTIONAL = "optional"
    ADVISORY = "advisory"


class OutcomeReasonCode(str, Enum):
    """Reason codes explaining evaluation results and completion decisions."""

    ALL_MANDATORY_CRITERIA_SATISFIED = "all_mandatory_criteria_satisfied"
    MANDATORY_CRITERION_UNSATISFIED = "mandatory_criterion_unsatisfied"
    REQUIRED_CRITERION_UNSATISFIED = "required_criterion_unsatisfied"
    OPTIONAL_CRITERION_UNSATISFIED = "optional_criterion_unsatisfied"
    VALIDATION_FAILED = "validation_failed"
    REGRESSION_DETECTED = "regression_detected"
    DEBT_GENERATED = "debt_generated"
    SIDE_EFFECT_DETECTED = "side_effect_detected"
    HIGH_RESIDUAL_RISK = "high_residual_risk"
    EVIDENCE_INSUFFICIENT = "evidence_insufficient"
    METRIC_THRESHOLD_NOT_MET = "metric_threshold_not_met"
    USER_CONFIRMATION_REQUIRED = "user_confirmation_required"
    USER_EXPECTATION_UNCERTAIN = "user_expectation_uncertain"
    PARTIAL_PROGRESS = "partial_progress"
    NO_PROGRESS = "no_progress"
    REMAINING_TASKS = "remaining_tasks"
    REMAINING_GAPS = "remaining_gaps"
    BUDGET_EXHAUSTED = "budget_exhausted"
    RECOVERY_REQUIRED = "recovery_required"
    CHECKPOINT_RECOMMENDED = "checkpoint_recommended"
    INCONSISTENT_STATE = "inconsistent_state"
    UNKNOWN_OUTCOME = "unknown_outcome"


# ── Phase 9.18 – Knowledge and Memory Update Enumerations ─────────────────────


class KnowledgeCandidateKind(str, Enum):
    """Functional category of candidate knowledge extracted from runtime outcome."""

    CREATED_GOAL = "created_goal"
    COMPLETED_GOAL = "completed_goal"
    OPERATION_RESULT = "operation_result"
    VALIDATED_STATE = "validated_state"
    STRUCTURAL_CHANGE = "structural_change"
    DECISION = "decision"
    CONSTRAINT = "constraint"
    EXPLICIT_PREFERENCE = "explicit_preference"
    REPRODUCIBLE_ERROR = "reproducible_error"
    FAILED_STRATEGY = "failed_strategy"
    SUCCESSFUL_STRATEGY = "successful_strategy"
    DEPENDENCY = "dependency"
    CONTRADICTION = "contradiction"
    TECHNICAL_DEBT = "technical_debt"
    GENERATED_ARTIFACT = "generated_artifact"
    NEW_CAPABILITY = "new_capability"
    UPDATED_RESOURCE = "updated_resource"


class OperationalLessonKind(str, Enum):
    """Categorization of reusable operational lessons derived from execution."""

    SUCCESS_PATTERN = "success_pattern"
    FAILURE_PATTERN = "failure_pattern"
    RECOVERY_PATTERN = "recovery_pattern"
    ENVIRONMENT_CONSTRAINT = "environment_constraint"
    TOOL_LIMITATION = "tool_limitation"
    VALIDATION_REQUIREMENT = "validation_requirement"
    DEPENDENCY_BEHAVIOR = "dependency_behavior"
    USER_PREFERENCE = "user_preference"
    WORKFLOW_OPTIMIZATION = "workflow_optimization"


class KnowledgeProposalStatus(str, Enum):
    """Lifecycle status of a knowledge update proposal."""

    PENDING = "pending"
    EVALUATING = "evaluating"
    APPROVAL_REQUIRED = "approval_required"
    APPROVED = "approved"
    REJECTED = "rejected"
    APPLIED = "applied"
    PARTIALLY_APPLIED = "partially_applied"
    BLOCKED = "blocked"
    FAILED = "failed"
    CANCELLED = "cancelled"


class MemoryWriteDecisionKind(str, Enum):
    """Policy decision for writing memory candidates to memory store."""

    ALLOW = "allow"
    ALLOW_WITH_CONFIRMATION = "allow_with_confirmation"
    ALLOW_WITH_REDACTION = "allow_with_redaction"
    REJECT = "reject"
    DEFER = "defer"
    ESCALATE = "escalate"


class KnowledgeWriteDecisionKind(str, Enum):
    """Policy decision for writing knowledge candidates to knowledge store."""

    ADD = "add"
    UPDATE = "update"
    INVALIDATE = "invalidate"
    LINK = "link"
    MERGE = "merge"
    REJECT = "reject"
    DEFER = "defer"
    REQUIRE_APPROVAL = "require_approval"


class KnowledgeRejectionReason(str, Enum):
    """Explicit justification reason codes for rejecting knowledge candidates."""

    INTERNAL_REASONING = "internal_reasoning"
    TRIVIAL_ATTEMPT = "trivial_attempt"
    WEAK_HYPOTHESIS = "weak_hypothesis"
    SECRET = "secret"
    TEMPORARY_LOW_UTILITY = "temporary_low_utility"
    UNREPRODUCED_ERROR = "unreproduced_error"
    INVALIDATED_RESULT = "invalidated_result"
    INFERRED_PREFERENCE = "inferred_preference"
    UNCONFIRMED_PERSONAL_DECISION = "unconfirmed_personal_decision"
    OUTSIDE_PERMISSION = "outside_permission"
    DUPLICATE = "duplicate"
    LOW_CONFIDENCE = "low_confidence"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    SENSITIVE_DATA = "sensitive_data"
    CONFLICTING_INFORMATION = "conflicting_information"
    EXPIRED_INFORMATION = "expired_information"
    UNKNOWN = "unknown"


class KnowledgeSensitivityLevel(str, Enum):
    """Sensitivity levels for knowledge governance and permissions."""

    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"
    SECRET = "secret"


class KnowledgeConfidenceLevel(str, Enum):
    """Confidence classification levels for knowledge validation state."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERIFIED = "verified"


# ── Phase 9.19 – Agent Runtime Trace Enumerations ──────────────────────────────


class AgentTraceStatus(str, Enum):
    """Lifecycle and integrity status for an AgentTrace."""

    OPEN = "open"
    BUILDING = "building"
    COMPLETE = "complete"
    PARTIAL = "partial"
    FAILED = "failed"
    CORRUPTED = "corrupted"
    REDACTED = "redacted"
    ARCHIVED = "archived"


class AgentTraceRecordKind(str, Enum):
    """Kinds of records that can appear in a trace."""

    HEADER = "header"
    ITERATION = "iteration"
    OBSERVATION = "observation"
    KNOWLEDGE_LOAD = "knowledge_load"
    COGNITIVE_PROFILE = "cognitive_profile"
    INFORMATION_GAP = "information_gap"
    QUESTION = "question"
    REASONING_REFERENCE = "reasoning_reference"
    RUNTIME_DECISION = "runtime_decision"
    PLAN = "plan"
    POLICY_DECISION = "policy_decision"
    APPROVAL_REQUEST = "approval_request"
    APPROVAL_DECISION = "approval_decision"
    OPERATION = "operation"
    RESOURCE_CHANGE = "resource_change"
    VALIDATION = "validation"
    RECOVERY_DECISION = "recovery_decision"
    RECOVERY_EXECUTION = "recovery_execution"
    CHECKPOINT = "checkpoint"
    TRANSACTION = "transaction"
    OUTCOME_EVALUATION = "outcome_evaluation"
    KNOWLEDGE_UPDATE = "knowledge_update"
    MEMORY_UPDATE = "memory_update"
    BUDGET_EVENT = "budget_event"
    WARNING = "warning"
    ERROR = "error"
    STOP_DECISION = "stop_decision"


class AgentTraceDecisionKind(str, Enum):
    """Decision kinds expressed in trace runtime decisions."""

    CONTINUE = "continue"
    STOP = "stop"
    PAUSE = "pause"
    RETRY = "retry"
    REPLAN = "replan"
    ROLLBACK = "rollback"
    ESCALATE = "escalate"
    COMPLETE = "complete"
    FAIL = "fail"
    CANCEL = "cancel"


class AgentTraceErrorKind(str, Enum):
    """Classification of errors captured in traces."""

    OPERATION = "operation"
    VALIDATION = "validation"
    POLICY = "policy"
    APPROVAL = "approval"
    RECOVERY = "recovery"
    BUDGET = "budget"
    KNOWLEDGE = "knowledge"
    MEMORY = "memory"
    TRACE = "trace"
    UNKNOWN = "unknown"


class AgentTraceRedactionReason(str, Enum):
    """Reasons for redacting a field from a trace."""

    SECRET = "secret"
    CREDENTIAL = "credential"
    PRIVATE_PROMPT = "private_prompt"
    INTERNAL_REASONING = "internal_reasoning"
    PERSONAL_DATA = "personal_data"
    HEALTH_DATA = "health_data"
    FINANCIAL_DATA = "financial_data"
    PRECISE_LOCATION = "precise_location"
    OUTSIDE_PERMISSION = "outside_permission"
    UNRELATED_CONTENT = "unrelated_content"
    OVERSIZED_CONTENT = "oversized_content"
    UNSAFE_METADATA = "unsafe_metadata"
    UNKNOWN = "unknown"


class AgentTraceIntegrityStatus(str, Enum):
    """Integrity verification status for traces."""

    VALID = "valid"
    PARTIAL = "partial"
    MISSING_EVENTS = "missing_events"
    DUPLICATE_EVENTS = "duplicate_events"
    ORDERING_ERROR = "ordering_error"
    CAUSALITY_ERROR = "causality_error"
    FINGERPRINT_MISMATCH = "fingerprint_mismatch"
    CORRUPTED = "corrupted"


class AgentTraceExportFormat(str, Enum):
    """Export formats for traces."""

    JSON = "json"
    JSONL = "jsonl"
    NDJSON = "ndjson"
    SUMMARY = "summary"
