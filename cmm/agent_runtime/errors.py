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
