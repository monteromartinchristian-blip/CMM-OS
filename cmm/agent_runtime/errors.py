"""Phase 9.1 – Agent Runtime Errors.

Defines the error hierarchy for the Autonomous Agent Runtime contracts.
"""

from __future__ import annotations


class AgentRuntimeError(Exception):
    """Base error for all Agent Runtime operations."""


class InvalidAgentContractError(AgentRuntimeError, ValueError):
    """Raised when an Agent Runtime contract is invalid, malformed, or violates invariants."""


class InvalidAgentIdentifierError(AgentRuntimeError, ValueError):
    """Raised when an Agent Runtime identifier is malformed or invalid."""


# ── Phase 9.2 – Goal System Errors ───────────────────────────────────────────


class GoalError(AgentRuntimeError):
    """Base exception for all Goal System operations."""


class InvalidGoalContractError(GoalError, InvalidAgentContractError):
    """Raised when a Goal contract or component is invalid or violates invariants."""


class GoalNotFoundError(GoalError, KeyError):
    """Raised when a requested goal is not found in the repository."""


class DuplicateGoalError(GoalError, ValueError):
    """Raised when attempting to register a goal with a duplicate identifier."""


class InvalidGoalTransitionError(GoalError, ValueError):
    """Raised when an invalid state transition is attempted on a Goal."""


class GoalCompletionError(GoalError, ValueError):
    """Raised when completing a goal fails (e.g., unsatisfied required criteria)."""


class GoalDependencyError(GoalError, ValueError):
    """Raised when a goal dependency is invalid or violated."""


# ── Phase 9.3 – Goal Intake Errors ───────────────────────────────────────────


class GoalIntakeError(GoalError):
    """Base exception for all Goal Intake operations."""


class InvalidGoalProposalError(GoalIntakeError, ValueError):
    """Raised when a GoalProposal contract is invalid or violates invariants."""


class GoalProposalNotFoundError(GoalIntakeError, KeyError):
    """Raised when a requested GoalProposal is not found in the repository."""


class GoalProposalStateError(GoalIntakeError, ValueError):
    """Raised when an invalid state operation is attempted on a GoalProposal."""


class GoalNormalizationError(GoalIntakeError, ValueError):
    """Raised when goal normalization fails or input is invalid/empty."""


class GoalProposalConversionError(GoalIntakeError, ValueError):
    """Raised when converting a GoalProposal into an operational Goal fails."""


# ── Phase 9.4 – Observation Engine Errors ─────────────────────────────────────


class ObservationEngineError(AgentRuntimeError):
    """Base exception for all Observation Engine operations."""


class InvalidObservationContractError(
    ObservationEngineError, InvalidAgentContractError
):
    """Raised when an Observation contract or snapshot is invalid or violates invariants."""


class ObserverNotFoundError(ObservationEngineError, KeyError):
    """Raised when a requested Observer is not registered or found."""


class DuplicateObserverError(ObservationEngineError, ValueError):
    """Raised when attempting to register an Observer with a duplicate name."""


class ObserverDisabledError(ObservationEngineError, ValueError):
    """Raised when attempting to execute a disabled Observer."""


class ObserverExecutionError(ObservationEngineError, RuntimeError):
    """Raised when an Observer encounters an unhandled runtime error during execution."""


class ObservationTimeoutError(ObservationEngineError, TimeoutError):
    """Raised when an Observation operation or Observer execution times out."""


class ObservationPermissionError(ObservationEngineError, PermissionError):
    """Raised when an Observation request lacks required permissions or sensitivity access."""


# ── Phase 9.5 – Cognitive Adapter Errors ──────────────────────────────────────


class CognitiveAdapterError(AgentRuntimeError):
    """Base exception for all Cognitive Adapter operations."""


class InvalidAgentCognitiveContractError(
    CognitiveAdapterError, InvalidAgentContractError
):
    """Raised when an AgentCognitive contract is invalid or violates invariants."""


class CognitiveSessionNotFoundError(CognitiveAdapterError, KeyError):
    """Raised when a requested cognitive session is not found."""


class CognitiveSessionMismatchError(CognitiveAdapterError, ValueError):
    """Raised when a cognitive session belongs to another Goal or AgentRun without authorization."""


class CognitiveProfileResolutionError(CognitiveAdapterError, ValueError):
    """Raised when resolving a cognitive reasoning profile fails."""


class CognitiveResourceAccessError(CognitiveAdapterError, PermissionError):
    """Raised when accessing required cognitive resources lacks permission."""


class CognitiveResultTranslationError(CognitiveAdapterError, ValueError):
    """Raised when translating a CognitiveResult to AgentCognitiveResult fails."""


class CognitiveAdapterExecutionError(CognitiveAdapterError, RuntimeError):
    """Raised when an unhandled execution error occurs in Cognitive Adapter."""


# ── Phase 9.6 – Information Acquisition Errors ────────────────────────────────


class InformationAcquisitionError(AgentRuntimeError):
    """Base exception for all Information Acquisition operations."""


class InvalidInformationAcquisitionContractError(
    InformationAcquisitionError, InvalidAgentContractError
):
    """Raised when an Information Acquisition contract is invalid or violates invariants."""


class InformationAcquisitionPermissionError(
    InformationAcquisitionError, PermissionError
):
    """Raised when an acquisition strategy lacks required permissions or sensitivity level."""


class InformationAcquisitionStrategyUnavailableError(
    InformationAcquisitionError, RuntimeError
):
    """Raised when a requested strategy is unavailable or lacks configured capability."""


class InformationAcquisitionLimitError(InformationAcquisitionError, ValueError):
    """Raised when information acquisition limits (calls, questions, cost) are exceeded."""


class InformationAcquisitionResolutionError(InformationAcquisitionError, RuntimeError):
    """Raised when strategy resolution or evaluation fails to make a valid decision."""


class InformationAcquisitionHandlerError(InformationAcquisitionError, RuntimeError):
    """Raised when an information acquisition handler fails during execution."""


# ── Phase 9.7 – Workflow Planner Adapter Errors ───────────────────────────────


class WorkflowPlannerAdapterError(AgentRuntimeError):
    """Base exception for all Workflow Planner Adapter operations."""


class InvalidAgentPlanningContractError(
    WorkflowPlannerAdapterError, InvalidAgentContractError
):
    """Raised when an agent planning contract is invalid or violates invariants."""


class PlannerUnavailableError(WorkflowPlannerAdapterError, RuntimeError):
    """Raised when the underlying Planner is unavailable or not provided."""


class PlannerExecutionError(WorkflowPlannerAdapterError, RuntimeError):
    """Raised when the underlying Planner fails during planning execution."""


class PlannerResultTranslationError(WorkflowPlannerAdapterError, ValueError):
    """Raised when translating Planner result into AgentWorkflowPlan fails."""


class WorkflowPlanValidationError(WorkflowPlannerAdapterError, ValueError):
    """Raised when an AgentWorkflowPlan fails structural validation."""


class WorkflowPlanCycleError(WorkflowPlanValidationError):
    """Raised when a circular dependency or cycle is detected in the plan DAG."""


class WorkflowOperationNotRegisteredError(WorkflowPlanValidationError):
    """Raised when an operation in the plan is not registered in the OperationRegistry."""


class WorkflowOperationNotAllowedError(WorkflowPlanValidationError):
    """Raised when an operation is not in allowed_operations."""


class WorkflowOperationProhibitedError(WorkflowPlanValidationError):
    """Raised when an operation is in prohibited_operations."""


class WorkflowPlanVersionError(WorkflowPlannerAdapterError, ValueError):
    """Raised when versioning or version transition is invalid."""


class WorkflowReplanningError(WorkflowPlannerAdapterError, RuntimeError):
    """Raised when replanning fails or cannot produce a valid updated plan."""


# ── Phase 9.8 – Policy Engine Errors ──────────────────────────────────────────


class PolicyEngineError(AgentRuntimeError):
    """Base exception for all Policy Engine operations."""


class InvalidPolicyContractError(PolicyEngineError, InvalidAgentContractError):
    """Raised when a policy contract or component is invalid or violates invariants."""


class PolicyNotFoundError(PolicyEngineError, KeyError):
    """Raised when a requested policy is not found in the repository."""


class PolicySetNotFoundError(PolicyEngineError, KeyError):
    """Raised when a requested policy set is not found in the repository."""


class DuplicatePolicyError(PolicyEngineError, ValueError):
    """Raised when attempting to add a policy with a duplicate ID and version."""


class DuplicatePolicySetError(PolicyEngineError, ValueError):
    """Raised when attempting to add a policy set with a duplicate ID."""


class PolicyConditionEvaluationError(PolicyEngineError, ValueError):
    """Raised when evaluating a policy condition fails due to invalid fields or syntax."""


class PolicyTargetEvaluationError(PolicyEngineError, ValueError):
    """Raised when evaluating a policy target fails."""


class PolicyCombiningError(PolicyEngineError, ValueError):
    """Raised when policy decision combining fails or algorithm encounters unexpected state."""


class PolicyResolutionError(PolicyEngineError, RuntimeError):
    """Raised when resolving policy sets or applicable policies fails."""


class PolicyVersionError(PolicyEngineError, ValueError):
    """Raised when policy versioning or version comparison is invalid."""


class PolicyEvaluationError(PolicyEngineError, RuntimeError):
    """Raised when policy evaluation encounters an unhandled runtime error."""


# ── Phase 9.9 – Autonomy Level Errors ────────────────────────────────────────


class AutonomyError(AgentRuntimeError):
    """Base exception for all Autonomy Level operations."""


class InvalidAutonomyContractError(AutonomyError, ValueError):
    """Raised when an Autonomy contract is invalid, malformed, or violates invariants."""


class AutonomyLevelError(AutonomyError, ValueError):
    """Raised when an autonomy level value is outside the supported range or malformed."""


class AutonomyCapabilityError(AutonomyError, ValueError):
    """Raised when an autonomy capability is invalid, unknown, or not allowed by the profile."""


class AutonomyTransitionError(AutonomyError, ValueError):
    """Raised when an autonomy transition is invalid for the current state or configuration."""


class AutonomyEscalationNotAuthorizedError(AutonomyError, PermissionError):
    """Raised when an autonomy escalation is attempted without explicit authorization."""


class AutonomyPolicyIntegrationError(AutonomyError, RuntimeError):
    """Raised when integrating Autonomy Evaluator with Policy Engine fails or is inconsistent."""


# ── Phase 9.10 – Human Approval System Errors ────────────────────────────────


class ApprovalError(AgentRuntimeError):
    """Base exception for all Human Approval System operations."""


class InvalidApprovalContractError(ApprovalError, InvalidAgentContractError):
    """Raised when an Approval contract is invalid, malformed, or violates invariants."""


class ApprovalRequestNotFoundError(ApprovalError, KeyError):
    """Raised when a requested ApprovalRequest is not found in the repository."""


class ApprovalDecisionNotFoundError(ApprovalError, KeyError):
    """Raised when a requested ApprovalDecision is not found in the repository."""


class DuplicateApprovalRequestError(ApprovalError, ValueError):
    """Raised when attempting to store an ApprovalRequest with a duplicate ID."""


class DuplicateApprovalDecisionError(ApprovalError, ValueError):
    """Raised when attempting to store an ApprovalDecision with a duplicate ID."""


class ApprovalAlreadyResolvedError(ApprovalError, ValueError):
    """Raised when submitting a decision on an already resolved or terminal ApprovalRequest."""


class ApprovalActorNotAuthorizedError(ApprovalError, PermissionError):
    """Raised when a decision actor is not in required_approvers or unauthorized."""


class ApprovalExpiredError(ApprovalError, ValueError):
    """Raised when operating on an expired approval request."""


class InvalidApprovalTransitionError(ApprovalError, ValueError):
    """Raised when an invalid status transition is attempted on an ApprovalRequest."""


class ApprovalSupersessionError(ApprovalError, ValueError):
    """Raised when superseding an approval request is invalid or malformed."""


class ApprovalPolicyIntegrationError(ApprovalError, RuntimeError):
    """Raised when integrating Policy Engine results into approval requirements fails or policy DENY is violated."""


class ApprovalAutonomyIntegrationError(ApprovalError, RuntimeError):
    """Raised when integrating Autonomy results into approval requirements fails or autonomy DENY is violated."""


# ── Phase 9.11 – Action Budget Errors ───────────────────────────────────────


class ActionBudgetError(AgentRuntimeError):
    """Base exception for all Action Budget operations."""


class InvalidActionBudgetContractError(ActionBudgetError, InvalidAgentContractError):
    """Raised when an Action Budget contract is invalid, malformed, or violates invariants."""


class ActionBudgetNotFoundError(ActionBudgetError, KeyError):
    """Raised when a requested ActionBudget is not found in the repository."""


class DuplicateActionBudgetError(ActionBudgetError, ValueError):
    """Raised when attempting to add an ActionBudget with a duplicate ID."""


class BudgetReservationNotFoundError(ActionBudgetError, KeyError):
    """Raised when a requested BudgetReservation is not found in the repository."""


class DuplicateBudgetReservationError(ActionBudgetError, ValueError):
    """Raised when attempting to add a BudgetReservation with a duplicate ID."""


class BudgetConsumptionNotFoundError(ActionBudgetError, KeyError):
    """Raised when a requested BudgetConsumption is not found in the repository."""


class DuplicateBudgetConsumptionError(ActionBudgetError, ValueError):
    """Raised when attempting to add a BudgetConsumption with a duplicate ID."""


class BudgetAdjustmentNotFoundError(ActionBudgetError, KeyError):
    """Raised when a requested BudgetAdjustment is not found in the repository."""


class DuplicateBudgetAdjustmentError(ActionBudgetError, ValueError):
    """Raised when attempting to add a BudgetAdjustment with a duplicate ID."""


class BudgetExhaustedError(ActionBudgetError, ValueError):
    """Raised when an operation is requested on an exhausted budget."""


class BudgetPausedError(ActionBudgetError, ValueError):
    """Raised when an operation is requested on a paused budget."""


class BudgetCancelledError(ActionBudgetError, ValueError):
    """Raised when an operation is requested on a cancelled budget."""


class InsufficientBudgetError(ActionBudgetError, ValueError):
    """Raised when available budget is insufficient for requested allocations."""


class InvalidBudgetAllocationError(ActionBudgetError, ValueError):
    """Raised when a BudgetAllocation specifies an invalid resource type or amount."""


class BudgetReservationExpiredError(ActionBudgetError, ValueError):
    """Raised when attempting to operate on an expired reservation."""


class BudgetReservationAlreadyResolvedError(ActionBudgetError, ValueError):
    """Raised when attempting to resolve an already confirmed, released, or expired reservation."""


class BudgetIncreaseNotAuthorizedError(ActionBudgetError, PermissionError):
    """Raised when an unauthorized actor attempts to increase budget limits."""


class BudgetApprovalIntegrationError(ActionBudgetError, RuntimeError):
    """Raised when integrating Human Approval System into budget increases fails."""


class BudgetPolicyIntegrationError(ActionBudgetError, RuntimeError):
    """Raised when integrating Policy Engine results into budget evaluation fails."""


class BudgetConcurrencyError(ActionBudgetError, ValueError):
    """Raised when parallel operation limits are exceeded or invalid concurrency state is reached."""


# ── Phase 9.12 – Agent Runtime Loop Errors ────────────────────────────────────


class AgentRuntimeLoopError(AgentRuntimeError):
    """Base exception for all Agent Runtime Loop operations."""


class InvalidRuntimeContractError(AgentRuntimeLoopError, InvalidAgentContractError):
    """Raised when a Runtime Loop contract is invalid or violates invariants."""


class AgentIterationNotFoundError(AgentRuntimeLoopError, KeyError):
    """Raised when a requested AgentIteration is not found in the repository."""


class DuplicateAgentIterationError(AgentRuntimeLoopError, ValueError):
    """Raised when attempting to store an AgentIteration with a duplicate ID."""


class RuntimeCheckpointNotFoundError(AgentRuntimeLoopError, KeyError):
    """Raised when a requested RuntimeCheckpoint is not found in the repository."""


class DuplicateRuntimeCheckpointError(AgentRuntimeLoopError, ValueError):
    """Raised when attempting to store a RuntimeCheckpoint with a duplicate ID."""


class RuntimeTransitionNotAllowedError(AgentRuntimeLoopError, ValueError):
    """Raised when an invalid state transition is attempted on an AgentRun."""


class DuplicateRuntimeTransitionError(AgentRuntimeLoopError, ValueError):
    """Raised when attempting to store a RuntimeTransition with a duplicate ID."""


class RuntimeStepHandlerNotFoundError(AgentRuntimeLoopError, KeyError):
    """Raised when no handler is registered for a requested RuntimeStep."""


class RuntimeStepExecutionError(AgentRuntimeLoopError, RuntimeError):
    """Raised when executing a runtime step fails during execution."""


class RuntimeIdempotencyConflictError(AgentRuntimeLoopError, ValueError):
    """Raised when an operation with an existing idempotency key is re-invoked with conflicting payload."""


class RuntimeResumeError(AgentRuntimeLoopError, ValueError):
    """Raised when resuming an AgentRun fails due to invalid checkpoint or state."""


class RuntimeCheckpointVersionError(AgentRuntimeLoopError, ValueError):
    """Raised when checkpoint state version is obsolete or incompatible."""


class RuntimeLockError(AgentRuntimeLoopError, ValueError):
    """Base exception for all Runtime Lock operations."""


class RuntimeLockConflictError(RuntimeLockError, ValueError):
    """Raised when acquiring a lock conflicts with an existing active lock."""


class RuntimeLockNotFoundError(RuntimeLockError, KeyError):
    """Raised when operating on a non-existent lock."""


class DuplicateRuntimeLockError(RuntimeLockError, ValueError):
    """Raised when attempting to create a lock with a duplicate ID."""


class RuntimeHeartbeatError(AgentRuntimeLoopError, ValueError):
    """Base exception for Heartbeat operations."""


class RuntimeHeartbeatExpiredError(RuntimeHeartbeatError, ValueError):
    """Raised when operating on an expired heartbeat."""


class RuntimeAbandonedError(AgentRuntimeLoopError, ValueError):
    """Raised when an AgentRun is detected as abandoned or stalled beyond thresholds."""


class RuntimeAlreadyTerminalError(AgentRuntimeLoopError, ValueError):
    """Raised when attempting an active transition or step on an already terminal run."""


class RuntimeConcurrentExecutionError(AgentRuntimeLoopError, ValueError):
    """Raised when concurrent incompatible operations are attempted on an AgentRun."""


class RuntimeRepositoryConsistencyError(AgentRuntimeLoopError, ValueError):
    """Raised when runtime repository encounters orphaned or inconsistent records."""


# ── Phase 9.13 – Operation Execution Errors ───────────────────────────


class AgentOperationError(AgentRuntimeError):
    """Base error for all Operation Selection and Execution Adapter operations."""


class InvalidAgentOperationContractError(
    AgentOperationError, InvalidAgentContractError
):
    """Raised when an Operation Execution contract is invalid, malformed, or violates invariants."""


class AgentOperationNotRegisteredError(AgentOperationError, KeyError):
    """Raised when an operation name is not registered in the AgentOperationRegistry."""


class AgentOperationVersionNotRegisteredError(AgentOperationError, KeyError):
    """Raised when an exact operation version is not registered in the AgentOperationRegistry."""


class DuplicateAgentOperationError(AgentOperationError, ValueError):
    """Raised when attempting to register an operation descriptor with a duplicate name and version."""


class AgentOperationRequestNotFoundError(AgentOperationError, KeyError):
    """Raised when a requested AgentOperationRequest is not found in the repository."""


class DuplicateAgentOperationRequestError(AgentOperationError, ValueError):
    """Raised when attempting to store an AgentOperationRequest with a duplicate ID."""


class AgentOperationResultNotFoundError(AgentOperationError, KeyError):
    """Raised when a requested AgentOperationExecutionResult is not found in the repository."""


class DuplicateAgentOperationResultError(AgentOperationError, ValueError):
    """Raised when attempting to store an AgentOperationExecutionResult with a duplicate ID."""


class AgentOperationCapabilityError(AgentOperationError, ValueError):
    """Raised when an operation capability is disabled or invalid."""


class AgentOperationCapabilityExceededError(AgentOperationError, ValueError):
    """Raised when an operation exceeds its configured maximum uses limit."""


class AgentOperationParameterValidationError(AgentOperationError, ValueError):
    """Raised when operation parameters fail schema validation or contain disallowed keys/types."""


class AgentOperationEnvironmentError(AgentOperationError, ValueError):
    """Raised when an operation request targets an unauthorized environment."""


class AgentOperationPermissionError(AgentOperationError, PermissionError):
    """Raised when an operation request lacks required permissions."""


class AgentOperationPolicyError(AgentOperationError, ValueError):
    """Raised when Policy Engine denies an operation request."""


class AgentOperationAutonomyError(AgentOperationError, ValueError):
    """Raised when Autonomy Level denies an operation request."""


class AgentOperationApprovalError(AgentOperationError, ValueError):
    """Raised when Human Approval is missing, invalid, or expired for an operation request."""


class AgentOperationBudgetError(AgentOperationError, ValueError):
    """Raised when Action Budget is insufficient or exhausted for an operation request."""


class AgentOperationCheckpointError(AgentOperationError, ValueError):
    """Raised when a runtime checkpoint is stale, invalid, or missing for an operation request."""


class AgentOperationResourceVersionError(AgentOperationError, ValueError):
    """Raised when resource pre-versions do not match current resource versions."""


class AgentOperationLockError(AgentOperationError, ValueError):
    """Raised when lock acquisition conflicts or lock checks fail for an operation."""


class AgentOperationRollbackError(AgentOperationError, ValueError):
    """Raised when rollback guarantees cannot be satisfied or rollback operation fails."""


class AgentOperationExecutionError(AgentOperationError, RuntimeError):
    """Raised when execution by the underlying execution engine encounters an error."""


class AgentOperationValidationError(AgentOperationError, ValueError):
    """Raised when post-execution validations fail."""


class AgentOperationIdempotencyConflictError(AgentOperationError, ValueError):
    """Raised when re-invoking an idempotency key with a conflicting payload."""


class AgentOperationRepositoryConsistencyError(AgentOperationError, ValueError):
    """Raised when repository operation records are orphaned or inconsistent."""


# ── Phase 9.14 – Validation Integration Errors ────────────────────────────────


class AgentValidationError(AgentRuntimeError):
    """Base exception for all Validation Integration operations."""


class ValidationRequirementError(AgentValidationError, ValueError):
    """Raised when a ValidationRequirement is invalid or violates invariants."""


class ValidationPolicySelectionError(AgentValidationError, ValueError):
    """Raised when selecting or building validation requirements fails."""


class ValidationAdapterError(AgentValidationError, RuntimeError):
    """Raised when an error occurs within the Validation Execution Adapter."""


class ValidationExecutionError(AgentValidationError, RuntimeError):
    """Raised when executing validation rules or pipeline encounters an error."""


class ValidationResultInvalidError(AgentValidationError, ValueError):
    """Raised when a ValidationResult is malformed or invalid."""


class ValidationRepositoryError(AgentValidationError, ValueError):
    """Raised when repository operation for validation records fails or conflicts."""


class ValidationDecisionError(AgentValidationError, ValueError):
    """Raised when evaluating or mapping a validation decision fails."""


class ValidationTimeoutError(AgentValidationError, TimeoutError):
    """Raised when a validation execution times out."""


class ValidationCommitGateError(AgentValidationError, ValueError):
    """Raised when Commit Gate evaluation fails or is denied."""


class ValidationPreExecutionBlockedError(AgentValidationError, ValueError):
    """Raised when pre-execution validation blocks operation execution."""


class ValidationPostExecutionBlockedError(AgentValidationError, ValueError):
    """Raised when post-execution validation blocks operation completion."""


class ValidationRollbackRequiredError(AgentValidationError, ValueError):
    """Raised when validation failure mandates a rollback."""


class ValidationInfrastructureError(AgentValidationError, RuntimeError):
    """Raised when an unexpected infrastructure exception occurs during validation."""


# ── Phase 9.15 – Checkpoint and Transaction Boundary Errors ───────────────────


class CheckpointError(AgentRuntimeError):
    """Base exception for all Checkpoint and Transaction Boundary operations."""


class CheckpointCreationError(CheckpointError, ValueError):
    """Raised when creating a checkpoint fails."""


class CheckpointNotFoundError(CheckpointError, KeyError):
    """Raised when a requested checkpoint is not found."""


class CheckpointAlreadyExistsError(CheckpointError, ValueError):
    """Raised when creating or saving a checkpoint with a conflicting ID occurs."""


class CheckpointInvalidError(CheckpointError, ValueError):
    """Raised when a checkpoint contract or state is invalid."""


class CheckpointExpiredError(CheckpointError, ValueError):
    """Raised when attempting to restore or access an expired checkpoint."""


class CheckpointIntegrityError(CheckpointError, ValueError):
    """Raised when checkpoint integrity verification fails."""


class CheckpointRepositoryError(CheckpointError, ValueError):
    """Raised when repository operations for checkpoints fail or violate constraints."""


class CheckpointRestorationError(CheckpointError, RuntimeError):
    """Raised when checkpoint restoration execution encounters an error."""


class CheckpointRestorationBlockedError(CheckpointError, ValueError):
    """Raised when checkpoint restoration is blocked by locks or policy."""


class CheckpointRestorationValidationError(CheckpointError, ValueError):
    """Raised when post-restoration validation fails."""


class CheckpointConcurrencyError(CheckpointError, RuntimeError):
    """Raised when concurrent restoration or lock conflicts occur."""


class TransactionBoundaryError(CheckpointError, ValueError):
    """Raised when transaction boundary rules or capabilities are violated."""


class TransactionStateError(CheckpointError, ValueError):
    """Raised when an invalid transition or operation is attempted on a Transaction."""


class TransactionCommitError(CheckpointError, RuntimeError):
    """Raised when committing a transaction fails."""


class TransactionRollbackError(CheckpointError, RuntimeError):
    """Raised when rolling back a transaction encounters an unrecoverable error."""


class CompensationError(CheckpointError, RuntimeError):
    """Raised when executing a compensation action fails."""


class IrreversibleOperationError(CheckpointError, PermissionError):
    """Raised when an irreversible operation lacks required approval or safety checks."""


class BackupRequiredError(CheckpointError, ValueError):
    """Raised when mandatory backup is missing or required before transaction."""


class ResourceSnapshotError(CheckpointError, RuntimeError):
    """Raised when snapshot capture of a resource fails."""


class ResourceVersionMismatchError(CheckpointError, ValueError):
    """Raised when resource versions diverge unexpectedly before restoration or commit."""


class GitStateRestorationError(CheckpointError, RuntimeError):
    """Raised when restoring Git repository state fails."""


class StorageSnapshotRestorationError(CheckpointError, RuntimeError):
    """Raised when restoring external storage snapshot fails."""


class MemoryStateRestorationError(CheckpointError, RuntimeError):
    """Raised when restoring memory state fails."""


class KnowledgeStateRestorationError(CheckpointError, RuntimeError):
    """Raised when restoring knowledge state fails."""


# ── Phase 9.16 – Recovery Manager Errors ──────────────────────────────────────


class RecoveryError(AgentRuntimeError):
    """Base exception for all Recovery Manager operations."""


class RecoveryContextError(RecoveryError, ValueError):
    """Raised when a RecoveryContext contract is invalid or violates invariants."""


class RecoveryDecisionError(RecoveryError, ValueError):
    """Raised when a RecoveryDecision is invalid or violates invariants."""


class RecoveryPolicyError(RecoveryError, ValueError):
    """Raised when recovery policies conflict or are violated."""


class RecoveryStrategyError(RecoveryError, ValueError):
    """Raised when a recovery strategy cannot be resolved or fails execution."""


class RecoveryRepositoryError(RecoveryError, ValueError):
    """Raised when recovery repository operations fail or violate invariants."""


class RecoveryExecutionError(RecoveryError, RuntimeError):
    """Raised when execution of a recovery strategy encounters an unhandled runtime error."""


class RecoveryBlockedError(RecoveryError, ValueError):
    """Raised when recovery execution is blocked by safety checks or state."""


class RecoveryEscalationError(RecoveryError, RuntimeError):
    """Raised when escalation processing encounters an error."""


class RecoveryBudgetError(RecoveryError, ValueError):
    """Raised when recovery execution exceeds allocated budget limits."""


class RecoveryRetryError(RecoveryError, RuntimeError):
    """Raised when a retry attempt fails."""


class RecoveryRetryExhaustedError(RecoveryRetryError, ValueError):
    """Raised when maximum retry attempts have been reached."""


class RecoveryNonRetryableError(RecoveryRetryError, ValueError):
    """Raised when a retry is attempted on an error classified as non-retryable."""


class RecoveryBackoffError(RecoveryError, ValueError):
    """Raised when backoff delay calculation parameters are invalid."""


class RecoveryReplanError(RecoveryError, RuntimeError):
    """Raised when requesting or building a recovery replan fails."""


class RecoveryRollbackError(RecoveryError, RuntimeError):
    """Raised when executing a recovery rollback fails."""


class RecoveryCompensationError(RecoveryError, RuntimeError):
    """Raised when executing a recovery compensation fails."""


class RecoveryApprovalRequiredError(RecoveryError, PermissionError):
    """Raised when a recovery strategy requires human approval that is missing or expired."""


class RecoveryPermissionError(RecoveryError, PermissionError):
    """Raised when a recovery strategy lacks required execution permissions."""


class RecoveryInconsistentStateError(RecoveryError, ValueError):
    """Raised when runtime or resource state is inconsistent, blocking continuation."""


class RecoveryEvidenceError(RecoveryError, ValueError):
    """Raised when required recovery evidence or artifact is missing or corrupted."""


class RecoveryIdempotencyError(RecoveryError, ValueError):
    """Raised when an idempotency key conflict occurs with mismatched metadata."""


class RecoveryStrategyUnavailableError(RecoveryError, ValueError):
    """Raised when a requested recovery strategy is not supported or registered."""


class RecoveryValidationError(RecoveryError, ValueError):
    """Raised when post-recovery validation fails."""


# ── Phase 9.17 – Outcome Evaluation Errors ───────────────────────────────────


class OutcomeEvaluationError(AgentRuntimeError):
    """Base exception for all Outcome Evaluation operations."""


class OutcomeEvaluationContextError(OutcomeEvaluationError, ValueError):
    """Raised when an OutcomeEvaluationContext is invalid or missing required resources."""


class OutcomeEvaluationRepositoryError(OutcomeEvaluationError, RuntimeError):
    """Raised when repository storage, retrieval, or concurrency operations fail."""


class OutcomeEvaluationPolicyError(OutcomeEvaluationError, ValueError):
    """Raised when an outcome evaluation policy is violated."""


class OutcomeEvaluationExecutionError(OutcomeEvaluationError, RuntimeError):
    """Raised when outcome evaluation execution fails unexpectedly."""


class OutcomeCriterionError(OutcomeEvaluationError):
    """Base exception for outcome criterion evaluation issues."""


class OutcomeCriterionNotFoundError(OutcomeCriterionError, KeyError):
    """Raised when a requested success criterion is not found."""


class OutcomeCriterionEvaluationError(OutcomeCriterionError, ValueError):
    """Raised when evaluating a criterion fails or encounters an invalid state."""


class OutcomeEvidenceError(OutcomeEvaluationError, ValueError):
    """Raised when evidence verification fails or evidence format is invalid."""


class OutcomeEvidenceInsufficientError(OutcomeEvidenceError):
    """Raised when required evidence is missing or insufficient to verify outcome."""


class OutcomeMetricError(OutcomeEvaluationError, ValueError):
    """Raised when evaluating outcome metrics fails or metric threshold is invalid."""


class OutcomeRegressionError(OutcomeEvaluationError, ValueError):
    """Raised when a regression is detected or cannot be safely analyzed."""


class OutcomeDebtError(OutcomeEvaluationError, ValueError):
    """Raised when technical/operational debt analysis encounters errors or unaccepted critical debt."""


class OutcomeSideEffectError(OutcomeEvaluationError, ValueError):
    """Raised when unexpected or unauthorized side effects are detected."""


class OutcomeKnowledgeError(OutcomeEvaluationError, ValueError):
    """Raised when knowledge acquisition analysis fails."""


class GoalCompletionDecisionError(OutcomeEvaluationError, ValueError):
    """Base exception for goal completion decision errors."""


class GoalCompletionBlockedError(GoalCompletionDecisionError):
    """Raised when goal completion is blocked by unsatisfied mandatory criteria or critical regression."""


class OutcomeInconclusiveError(OutcomeEvaluationError, ValueError):
    """Raised when evidence or state comparison is inconclusive."""


class OutcomeUserConfirmationRequiredError(OutcomeEvaluationError, PermissionError):
    """Raised when user confirmation is required to finalize goal completion."""


class OutcomeStateComparisonError(OutcomeEvaluationError, ValueError):
    """Raised when state comparison fails or states are incomparable."""


class OutcomeFingerprintError(OutcomeEvaluationError, ValueError):
    """Raised when a fingerprint mismatch or conflict occurs."""


# ── Phase 9.18 – Knowledge and Memory Update Errors ───────────────────────────


class KnowledgeUpdateError(AgentRuntimeError):
    """Base exception for all Knowledge and Memory Update operations."""


class KnowledgeUpdateContextError(KnowledgeUpdateError, ValueError):
    """Raised when a KnowledgeUpdateContext is invalid or missing required context."""


class KnowledgeProposalError(KnowledgeUpdateError, ValueError):
    """Raised when a KnowledgeUpdateProposal contract or operation is invalid."""


class KnowledgeCandidateError(KnowledgeUpdateError, ValueError):
    """Raised when a KnowledgeUpdateCandidate is invalid or malformed."""


class KnowledgeCandidateRejectedError(KnowledgeCandidateError, ValueError):
    """Raised when a Knowledge candidate is explicitly rejected during processing."""


class KnowledgePolicyError(KnowledgeUpdateError, ValueError):
    """Raised when a knowledge update policy evaluation fails."""


class KnowledgePermissionError(KnowledgeUpdateError, PermissionError):
    """Raised when knowledge update operations exceed authorized permissions."""


class KnowledgeSensitivityError(KnowledgeUpdateError, ValueError):
    """Raised when sensitivity classification or privacy policy fails or blocks write."""


class KnowledgeDeduplicationError(KnowledgeUpdateError, ValueError):
    """Raised when deduplication processing fails or detects unresolvable duplication conflicts."""


class KnowledgeVersioningError(KnowledgeUpdateError, ValueError):
    """Raised when knowledge version references or versioning operations fail."""


class KnowledgeInvalidationError(KnowledgeUpdateError, ValueError):
    """Raised when knowledge invalidation logic fails or invalid state transitions occur."""


class KnowledgeRelationError(KnowledgeUpdateError, ValueError):
    """Raised when knowledge relationship creation or linking fails."""


class KnowledgeProvenanceError(KnowledgeUpdateError, ValueError):
    """Raised when knowledge provenance or source evidence metadata is missing or invalid."""


class OperationalLessonError(KnowledgeUpdateError, ValueError):
    """Raised when operational lesson extraction or validation fails."""


class MemoryUpdateError(AgentRuntimeError):
    """Base exception for all Memory Update operations."""


class MemoryWriteBlockedError(MemoryUpdateError, ValueError):
    """Raised when a memory update is blocked by policy or validation rules."""


class MemoryConfirmationRequiredError(MemoryUpdateError, PermissionError):
    """Raised when a memory update requires explicit user confirmation."""


class MemoryPermissionError(MemoryUpdateError, PermissionError):
    """Raised when memory write operations violate permission boundaries."""


class MemorySensitivityError(MemoryUpdateError, ValueError):
    """Raised when memory sensitivity classification blocks an update."""


class MemoryDeduplicationError(MemoryUpdateError, ValueError):
    """Raised when memory deduplication encounters unresolvable conflicts."""


class KnowledgeApprovalRequiredError(KnowledgeUpdateError, PermissionError):
    """Raised when a knowledge update requires explicit approval before application."""


class KnowledgeWriteError(KnowledgeUpdateError, RuntimeError):
    """Raised when writing knowledge updates to the underlying knowledge store fails."""


class KnowledgeUpdateRepositoryError(KnowledgeUpdateError, RuntimeError):
    """Raised when repository persistence or retrieval operations encounter errors."""


class KnowledgeUpdateExecutionError(KnowledgeUpdateError, RuntimeError):
    """Raised when applying knowledge/memory updates encounters execution failures."""


class KnowledgeFingerprintError(KnowledgeUpdateError, ValueError):
    """Raised when a fingerprint mismatch or conflict occurs during proposal persistence."""


# ── Phase 9.19 – Agent Runtime Trace Errors ─────────────────────────────────────


class AgentTraceError(AgentRuntimeError):
    """Base exception for all Agent Runtime Trace operations."""


class AgentTraceContractError(AgentTraceError, ValueError):
    """Raised when a trace contract is invalid or violates invariants."""


class AgentTraceContextError(AgentTraceError, ValueError):
    """Raised when trace context is missing or invalid."""


class AgentTraceBuildError(AgentTraceError, RuntimeError):
    """Raised when trace assembly or building fails."""


class AgentTraceRepositoryError(AgentTraceError, RuntimeError):
    """Raised when trace repository operations fail."""


class AgentTraceNotFoundError(AgentTraceError, KeyError):
    """Raised when a requested trace is not found."""


class AgentTraceConflictError(AgentTraceError, ValueError):
    """Raised when a trace conflict occurs (e.g., fingerprint mismatch on existing)."""


class AgentTraceIntegrityError(AgentTraceError, ValueError):
    """Raised when trace integrity verification fails."""


class AgentTraceOrderingError(AgentTraceError, ValueError):
    """Raised when trace events are out of order."""


class AgentTraceCausalityError(AgentTraceError, ValueError):
    """Raised when trace causation chain is broken."""


class AgentTraceRedactionError(AgentTraceError, RuntimeError):
    """Raised when trace redaction fails."""


class AgentTracePermissionError(AgentTraceError, PermissionError):
    """Raised when trace access lacks required permissions."""


class AgentTraceSensitivityError(AgentTraceError, ValueError):
    """Raised when trace content violates sensitivity policies."""


class AgentTraceRetentionError(AgentTraceError, ValueError):
    """Raised when trace retention policy is violated."""


class AgentTraceExportError(AgentTraceError, RuntimeError):
    """Raised when trace export fails."""


class AgentTraceQueryError(AgentTraceError, ValueError):
    """Raised when a trace query is invalid."""


class AgentTraceSerializationError(AgentTraceError, ValueError):
    """Raised when trace serialization or deserialization fails."""


class AgentTraceFingerprintError(AgentTraceError, ValueError):
    """Raised when trace fingerprint computation or verification fails."""


class AgentTraceUnsupportedEventError(AgentTraceError, ValueError):
    """Raised when an event type is not supported for tracing."""


class AgentTraceSourceError(AgentTraceError, ValueError):
    """Raised when a source event reference is invalid or missing."""


class AgentTraceFinalizedError(AgentTraceError, ValueError):
    """Raised when attempting to modify a finalized trace."""


# ── Phase 9.20 – Runtime Event Bus Errors ─────────────────────────────────────


class AgentRuntimeEventError(Exception):
    """Base error for all Runtime Event Bus operations."""


class AgentRuntimeEventContractError(AgentRuntimeEventError, ValueError):
    """Raised when an event contract is invalid or violates invariants."""


class AgentRuntimeEventRegistryError(AgentRuntimeEventError, ValueError):
    """Raised when event registry operations fail."""


class AgentRuntimeEventDuplicateError(AgentRuntimeEventError, ValueError):
    """Raised when a duplicate event is detected."""


class AgentRuntimeEventUnknownTypeError(AgentRuntimeEventContractError):
    """Raised when an unknown event type is used."""


class AgentRuntimeEventSerializationError(AgentRuntimeEventError, ValueError):
    """Raised when event serialization or deserialization fails."""


class AgentRuntimeEventValidationError(AgentRuntimeEventError, ValueError):
    """Raised when event validation fails."""


class AgentRuntimeEventBusClosedError(AgentRuntimeEventError, RuntimeError):
    """Raised when publishing to a closed event bus."""


class AgentRuntimeEventQueueFullError(AgentRuntimeEventError, RuntimeError):
    """Raised when the event queue is full and backpressure is active."""


class AgentRuntimeEventDeliveryError(AgentRuntimeEventError, RuntimeError):
    """Raised when event delivery to a handler fails."""


class AgentRuntimeEventReplayError(AgentRuntimeEventError, RuntimeError):
    """Raised when event replay fails."""


class AgentRuntimeEventPermissionError(AgentRuntimeEventError, PermissionError):
    """Raised when event permissions are insufficient."""


class AgentRuntimeEventSensitivityError(AgentRuntimeEventError, ValueError):
    """Raised when event sensitivity constraints are violated."""


class AgentRuntimeEventDeadLetterQueueError(AgentRuntimeEventError, RuntimeError):
    """Raised when dead letter queue operations fail."""


class AgentRuntimeEventRepositoryError(AgentRuntimeEventError, RuntimeError):
    """Raised when event repository operations fail."""


class AgentRuntimeEventTraceSubscriberError(AgentRuntimeEventError, RuntimeError):
    """Raised when the trace subscriber encounters an error."""
