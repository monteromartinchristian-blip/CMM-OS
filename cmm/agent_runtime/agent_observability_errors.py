"""Phase 9.26 agent observability error hierarchy."""

from __future__ import annotations

from typing import Any

from cmm.agent_runtime.errors import AgentRuntimeError, InvalidAgentContractError

_REDACTED = "[REDACTED]"
_SENSITIVE_PARTS = frozenset(
    {
        "password",
        "passwd",
        "secret",
        "token",
        "api_key",
        "apikey",
        "authorization",
        "cookie",
        "credential",
        "private_key",
        "access_key",
        "refresh_token",
        "session",
    }
)


def _sanitize_details(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: (
                _REDACTED
                if isinstance(key, str)
                and any(part in key.casefold() for part in _SENSITIVE_PARTS)
                else _sanitize_details(item)
            )
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple, set, frozenset)):
        return tuple(_sanitize_details(item) for item in value)
    return value


class AgentObservabilityError(AgentRuntimeError):
    """Base error for Phase 9.26 operations."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.details = _sanitize_details(dict(details or {}))


class InvalidAgentObservabilityContractError(
    AgentObservabilityError, InvalidAgentContractError
):
    """Raised when an observability contract violates its invariants."""


class AgentObservabilityDuplicateError(AgentObservabilityError, ValueError):
    """Raised when a primary identifier already exists."""


class AgentObservabilityNotFoundError(AgentObservabilityError, KeyError):
    """Raised when an observability record does not exist."""


class AgentObservabilityConflictError(AgentObservabilityError, ValueError):
    """Raised when stored state conflicts with the requested transition."""


class AgentObservabilityTraceFinalizedError(AgentObservabilityConflictError):
    """Raised when a finalized trace or span would be mutated."""


class AgentObservabilityAppendOnlyError(AgentObservabilityConflictError):
    """Raised when an append-only record would be replaced."""


class AgentObservabilityQueryError(AgentObservabilityError, ValueError):
    """Raised for invalid filters, time windows, or pagination."""


__all__ = [
    "AgentObservabilityAppendOnlyError",
    "AgentObservabilityConflictError",
    "AgentObservabilityDuplicateError",
    "AgentObservabilityError",
    "AgentObservabilityNotFoundError",
    "AgentObservabilityQueryError",
    "AgentObservabilityTraceFinalizedError",
    "InvalidAgentObservabilityContractError",
]
