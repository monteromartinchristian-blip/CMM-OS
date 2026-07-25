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
