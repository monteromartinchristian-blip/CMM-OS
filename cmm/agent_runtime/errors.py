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
