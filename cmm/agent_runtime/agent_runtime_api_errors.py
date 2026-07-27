"""Phase 9.21 – Agent Runtime API Error Hierarchy.

Structured error types for the Agent Runtime API.
Internal errors must not leak stack traces, secrets or sensitive details.
"""

from __future__ import annotations

from typing import Any


class AgentRuntimeApiException(Exception):
    """Base exception for all Agent Runtime API errors."""

    def __init__(
        self,
        message: str,
        error_code: str = "INTERNAL_ERROR",
        details: dict[str, Any] | None = None,
        request_id: str | None = None,
    ) -> None:
        # Sanitize sensitive data from the message
        sanitized = self._sanitize_message(message)
        super().__init__(sanitized)
        self.error_code = error_code
        self.details = details
        self.request_id = request_id
        self._sanitized_message = sanitized

    @staticmethod
    def _sanitize_message(msg: str) -> str:
        """Remove sensitive patterns from error messages."""
        sensitive = [
            "chain_of_thought",
            "private_prompt",
            "password",
            "token=",
            "api_key=",
            "bearer ",
            "private_key=",
        ]
        lower = msg.lower()
        for s in sensitive:
            if s in lower:
                return "An internal error occurred"
        # Strip tracebacks
        if "Traceback (most recent call last)" in msg:
            return "An internal error occurred"
        return msg


class AgentRuntimeApiContractError(AgentRuntimeApiException):
    def __init__(self, message: str, **kwargs: Any) -> None:
        super().__init__(message, error_code="CONTRACT_ERROR", **kwargs)


class AgentRuntimeApiValidationError(AgentRuntimeApiException):
    def __init__(self, message: str, **kwargs: Any) -> None:
        super().__init__(message, error_code="VALIDATION_ERROR", **kwargs)


class AgentRuntimeApiNotFoundError(AgentRuntimeApiException):
    def __init__(self, message: str, **kwargs: Any) -> None:
        super().__init__(message, error_code="NOT_FOUND", **kwargs)


class AgentRuntimeApiConflictError(AgentRuntimeApiException):
    def __init__(self, message: str, **kwargs: Any) -> None:
        super().__init__(message, error_code="CONFLICT", **kwargs)


class AgentRuntimeApiIdempotencyConflictError(AgentRuntimeApiException):
    """Same idempotency key reused with a different payload."""

    def __init__(self, message: str, **kwargs: Any) -> None:
        super().__init__(message, error_code="IDEMPOTENCY_CONFLICT", **kwargs)


class AgentRuntimeApiPermissionError(AgentRuntimeApiException):
    def __init__(self, message: str, **kwargs: Any) -> None:
        super().__init__(message, error_code="PERMISSION_DENIED", **kwargs)


class AgentRuntimeApiPolicyDeniedError(AgentRuntimeApiException):
    def __init__(self, message: str, **kwargs: Any) -> None:
        super().__init__(message, error_code="POLICY_DENIED", **kwargs)


class AgentRuntimeApiApprovalRequiredError(AgentRuntimeApiException):
    def __init__(self, message: str, **kwargs: Any) -> None:
        super().__init__(message, error_code="APPROVAL_REQUIRED", **kwargs)


class AgentRuntimeApiBudgetExceededError(AgentRuntimeApiException):
    def __init__(self, message: str, **kwargs: Any) -> None:
        super().__init__(message, error_code="BUDGET_EXCEEDED", **kwargs)


class AgentRuntimeApiStateError(AgentRuntimeApiException):
    def __init__(self, message: str, **kwargs: Any) -> None:
        super().__init__(message, error_code="STATE_ERROR", **kwargs)


class AgentRuntimeApiSerializationError(AgentRuntimeApiException):
    def __init__(self, message: str, **kwargs: Any) -> None:
        super().__init__(message, error_code="SERIALIZATION_ERROR", **kwargs)


class AgentRuntimeApiUnsupportedOperationError(AgentRuntimeApiException):
    def __init__(self, message: str, **kwargs: Any) -> None:
        super().__init__(message, error_code="UNSUPPORTED_OPERATION", **kwargs)


class AgentRuntimeApiInternalError(AgentRuntimeApiException):
    """Internal error. MUST NOT leak stack traces or secrets."""

    def __init__(
        self, message: str = "An internal error occurred", **kwargs: Any
    ) -> None:
        # Force-sanitize any message in internal errors
        super().__init__(
            AgentRuntimeApiException._sanitize_message(message),
            error_code="INTERNAL_ERROR",
            **kwargs,
        )
