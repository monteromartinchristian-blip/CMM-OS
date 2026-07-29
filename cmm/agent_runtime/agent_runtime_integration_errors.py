"""Errors for Agent Runtime integration orchestration storage."""

from __future__ import annotations

from typing import Any

from cmm.agent_runtime.agent_runtime_integration_enums import IntegrationFailureMode
from cmm.agent_runtime.errors import AgentRuntimeError


class AgentRuntimeIntegrationError(AgentRuntimeError):
    """Base error for Agent Runtime integration failures."""

    def __init__(
        self,
        message: str,
        *,
        failure_mode: IntegrationFailureMode = IntegrationFailureMode.MANDATORY_FAIL_CLOSED,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.failure_mode = failure_mode
        self.details = dict(details or {})


class IntegrationStoreError(AgentRuntimeIntegrationError):
    """Base error for integration store failures."""


class IntegrationNotFoundError(IntegrationStoreError, KeyError):
    """Raised when an integration execution cannot be found."""


class IntegrationDuplicateError(IntegrationStoreError, ValueError):
    """Raised when a unique integration index already belongs to another record."""


class IntegrationIdempotencyConflictError(IntegrationStoreError, ValueError):
    """Raised when an idempotency key is reused with different payload."""


class IntegrationVersionConflictError(IntegrationStoreError, ValueError):
    """Raised when an optimistic version check fails."""


class IntegrationStateError(IntegrationStoreError, ValueError):
    """Raised when an execution state mutation is invalid."""


class IntegrationStoreConsistencyError(IntegrationStoreError, RuntimeError):
    """Raised when primary and secondary store indexes disagree."""
