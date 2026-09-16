"""Phase 11.3 — typed application failures and the one safe conversion path.

``cmm.application.contracts`` owns the public error *value*
(:class:`~cmm.application.contracts.ApplicationError`).  This module owns the
matching typed internal failures and the single checked conversion from an
arbitrary exception to that public value.

Two invariants make the boundary safe:

- a typed failure carries an application-owned constant message and a closed
  public code, so no caller text, exception repr, path, credential or hidden
  reasoning can reach a public response;
- everything that is not a typed application failure converts to
  ``INTERNAL_FAILURE`` with one generic message.

Details are validated through the public contract grammar at construction time,
so a secret-shaped key, binary data or an unbounded value fails closed before a
failure can be reported rather than while it is being reported.

HTTP status mapping deliberately does not live here: it belongs to ``cmm.api``.

See ``docs/reference/phase-11-application-backend.md``.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from cmm.application.contracts import (
    APPLICATION_API_VERSION,
    ApplicationError,
    ApplicationErrorCode,
    ApplicationResponse,
    ApplicationStatus,
)

__all__ = [
    "GENERIC_FAILURE_MESSAGE",
    "ApplicationCancelledError",
    "ApplicationConflictError",
    "ApplicationResourceNotFoundError",
    "ApplicationServiceError",
    "ApprovalRequiredApplicationError",
    "CapabilityUnavailableError",
    "ConcurrencyConflictError",
    "IdempotencyConflictError",
    "InternalApplicationError",
    "InvalidApplicationRequestError",
    "PolicyDeniedApplicationError",
    "UnsupportedApplicationVersionError",
    "failed_response",
    "safe_error_from_exception",
]

#: The one safe public message used for an unexpected internal failure.
GENERIC_FAILURE_MESSAGE = "Application request failed closed"


# ── Typed application failures ───────────────────────────────────────────────


class ApplicationServiceError(Exception):
    """Base typed application failure with one safe public projection.

    Subclasses narrow ``code``, ``safe_message`` and ``retryable`` as class
    attributes.  The instance never accepts free-form text: the public message
    is always application-owned, and ``details`` must satisfy the public
    contract grammar, so a typed failure can never smuggle internal content
    into a response.
    """

    code: ApplicationErrorCode = ApplicationErrorCode.INTERNAL_FAILURE
    safe_message: str = GENERIC_FAILURE_MESSAGE
    retryable: bool = False

    details: Mapping[str, Any]

    def __init__(self, *, details: Mapping[str, Any] | None = None) -> None:
        self.code = type(self).code
        self.safe_message = type(self).safe_message
        self.retryable = type(self).retryable
        # Building the public value here validates the safe details grammar
        # eagerly and freezes the result, so reporting a failure can not fail.
        self._public_error = ApplicationError(
            code=self.code,
            message=self.safe_message,
            retryable=self.retryable,
            details={} if details is None else details,
        )
        self.details = self._public_error.details
        super().__init__(self.safe_message)

    def to_public_error(self) -> ApplicationError:
        """Return the safe, immutable public error for this failure."""

        return self._public_error


class InvalidApplicationRequestError(ApplicationServiceError):
    """The public request is malformed, unknown or internally inconsistent."""

    code = ApplicationErrorCode.INVALID_REQUEST
    safe_message = "Application request is not valid"


class UnsupportedApplicationVersionError(ApplicationServiceError):
    """The requested public API version is not supported."""

    code = ApplicationErrorCode.UNSUPPORTED_VERSION
    safe_message = "Application API version is not supported"


class ApplicationResourceNotFoundError(ApplicationServiceError):
    """A canonical resource referenced by the request does not exist."""

    code = ApplicationErrorCode.RESOURCE_NOT_FOUND
    safe_message = "Application resource was not found"


class ApplicationConflictError(ApplicationServiceError):
    """The request conflicts with existing canonical state."""

    code = ApplicationErrorCode.CONFLICT
    safe_message = "Application resource state conflicts with the request"


class CapabilityUnavailableError(ApplicationServiceError):
    """No canonical owner exists for the requested capability."""

    code = ApplicationErrorCode.CAPABILITY_UNAVAILABLE
    safe_message = "Requested capability is unavailable"


class IdempotencyConflictError(ApplicationServiceError):
    """One idempotency key is bound to a materially different command.

    Not retryable: repeating the same key can not change the outcome, because
    the conflict is the key binding itself.
    """

    code = ApplicationErrorCode.IDEMPOTENCY_CONFLICT
    safe_message = "Idempotency key is already bound to a different command"


class ConcurrencyConflictError(ApplicationServiceError):
    """The caller's expected canonical revision is stale.

    Retryable in the optimistic-concurrency sense only: the caller must refetch
    the canonical revision.  No automatic retry happens inside the application
    layer.
    """

    code = ApplicationErrorCode.CONCURRENCY_CONFLICT
    safe_message = "Application resource revision conflicts with the request"
    retryable = True


class ApplicationCancelledError(ApplicationServiceError):
    """The request was cancelled through a canonical cancellable owner."""

    code = ApplicationErrorCode.CANCELLED
    safe_message = "Application request was cancelled"


class PolicyDeniedApplicationError(ApplicationServiceError):
    """Canonical policy denied the request."""

    code = ApplicationErrorCode.POLICY_DENIED
    safe_message = "Application request was denied by policy"


class ApprovalRequiredApplicationError(ApplicationServiceError):
    """Canonical approval is required before the request can proceed."""

    code = ApplicationErrorCode.APPROVAL_REQUIRED
    safe_message = "Application request requires approval"


class InternalApplicationError(ApplicationServiceError):
    """The application layer failed closed on an unexpected internal defect."""

    code = ApplicationErrorCode.INTERNAL_FAILURE
    safe_message = GENERIC_FAILURE_MESSAGE


# ── Safe conversion and failure response ─────────────────────────────────────


def safe_error_from_exception(exc: BaseException) -> ApplicationError:
    """Return the safe public error for *exc*.

    A typed application failure keeps its closed code and application-owned
    message.  Anything else — including a malformed typed failure — becomes one
    generic ``INTERNAL_FAILURE`` with empty details, so no internal text can
    cross the boundary.
    """

    if not isinstance(exc, BaseException):
        raise TypeError("exc must be a BaseException")

    if isinstance(exc, ApplicationServiceError):
        try:
            return exc.to_public_error()
        except Exception:  # noqa: BLE001 - a malformed typed failure fails closed
            return _internal_failure_error()
    return _internal_failure_error()


def _internal_failure_error() -> ApplicationError:
    return ApplicationError(
        code=ApplicationErrorCode.INTERNAL_FAILURE,
        message=GENERIC_FAILURE_MESSAGE,
        retryable=False,
        details={},
    )


def failed_response(request_id: str, error: ApplicationError) -> ApplicationResponse:
    """Return the versioned public failure response for one request."""

    if not isinstance(error, ApplicationError):
        raise TypeError("error must be an ApplicationError")
    return ApplicationResponse(
        request_id=request_id,
        api_version=APPLICATION_API_VERSION,
        status=ApplicationStatus.FAILED,
        data=None,
        error=error,
        metadata={},
    )
