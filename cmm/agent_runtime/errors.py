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
