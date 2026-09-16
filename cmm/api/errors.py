"""Phase 11.3 — the frozen HTTP status map and safe transport error reporting.

HTTP status is a transport concern, so the mapping from the closed public
application error codes to status codes lives here and nowhere else.  It is
total over the frozen error set and matches the Phase 11.3 status map exactly.

Three rules make the mapping safe:

- no exception, exception message or internal reason ever determines a status
  directly; only the closed public
  :class:`~cmm.application.contracts.ApplicationErrorCode` value does;
- an unmapped code fails closed to ``500`` instead of raising, so a future code
  can never turn a safe response into an unhandled transport defect (the frozen
  error set is locked by tests, so that default is a guard, not a policy);
- transport defects — an unusable ``X-Request-ID``, an oversized
  ``Idempotency-Key`` — are reported as public application errors built from the
  application layer's own typed failure, so the public message stays
  application-owned and no transport text is invented here.

See ``docs/reference/phase-11-application-backend.md``.
"""

from __future__ import annotations

from collections.abc import Mapping

from cmm.application import (
    ApplicationError,
    ApplicationErrorCode,
    ApplicationOperation,
    ApplicationResourceNotFoundError,
    ApplicationResponse,
    ApplicationServiceError,
    ApplicationStatus,
    InternalApplicationError,
    InvalidApplicationRequestError,
)

__all__ = [
    "REASON_INTERNAL_DEFECT",
    "REASON_INVALID_IDEMPOTENCY_KEY",
    "REASON_INVALID_REQUEST_BODY",
    "REASON_INVALID_REQUEST_CONTRACT",
    "REASON_INVALID_REQUEST_ID",
    "REASON_METHOD_NOT_ALLOWED",
    "REASON_UNKNOWN_ROUTE",
    "framework_error",
    "http_status_for",
    "invalid_request_error",
    "status_code_for",
    "success_status_code",
]

#: The caller supplied a request identity the public boundary can not use.
REASON_INVALID_REQUEST_ID = "INVALID_REQUEST_ID"

#: The caller supplied an idempotency key the public boundary can not use.
REASON_INVALID_IDEMPOTENCY_KEY = "INVALID_IDEMPOTENCY_KEY"

#: The request body failed transport validation.
REASON_INVALID_REQUEST_BODY = "INVALID_REQUEST_BODY"

#: The public application contract rejected the values built from the request.
REASON_INVALID_REQUEST_CONTRACT = "INVALID_REQUEST_CONTRACT"

#: No public route serves the requested path.
REASON_UNKNOWN_ROUTE = "UNKNOWN_ROUTE"

#: The requested method is not part of the public surface.
REASON_METHOD_NOT_ALLOWED = "METHOD_NOT_ALLOWED"

#: A framework status no public route can produce.
REASON_INTERNAL_DEFECT = "INTERNAL_DEFECT"

#: Frozen public error-code to HTTP status map.
_STATUS_CODES: Mapping[ApplicationErrorCode, int] = {
    ApplicationErrorCode.INVALID_REQUEST: 400,
    ApplicationErrorCode.UNSUPPORTED_VERSION: 400,
    ApplicationErrorCode.POLICY_DENIED: 403,
    ApplicationErrorCode.RESOURCE_NOT_FOUND: 404,
    ApplicationErrorCode.CONFLICT: 409,
    ApplicationErrorCode.IDEMPOTENCY_CONFLICT: 409,
    ApplicationErrorCode.CONCURRENCY_CONFLICT: 409,
    ApplicationErrorCode.APPROVAL_REQUIRED: 409,
    ApplicationErrorCode.CANCELLED: 409,
    ApplicationErrorCode.CAPABILITY_UNAVAILABLE: 503,
    ApplicationErrorCode.INTERNAL_FAILURE: 500,
}

#: Status of a code the map does not know: fail closed, never raise.
_UNMAPPED_STATUS = 500

#: HTTP status of a successful resource-creating command.  Only session
#: creation creates a public resource, so only it answers ``201``.
_SUCCESS_STATUS_CODES: Mapping[ApplicationOperation, int] = {
    ApplicationOperation.SESSION_CREATE: 201,
}

#: Status of every other successful operation.
_DEFAULT_SUCCESS_STATUS = 200

#: Framework routing status to the typed public failure that reports it.  Only
#: routing outcomes are listed; anything else is an internal defect.
_FRAMEWORK_ROUTING_FAILURES: Mapping[int, tuple[type[ApplicationServiceError], str]] = {
    404: (ApplicationResourceNotFoundError, REASON_UNKNOWN_ROUTE),
    405: (InvalidApplicationRequestError, REASON_METHOD_NOT_ALLOWED),
}


def status_code_for(error_code: ApplicationErrorCode) -> int:
    """Return the frozen HTTP status of one public application error code."""

    if not isinstance(error_code, ApplicationErrorCode):
        raise TypeError(
            f"error_code must be an ApplicationErrorCode, not {type(error_code).__name__}"
        )
    return _STATUS_CODES.get(error_code, _UNMAPPED_STATUS)


def success_status_code(operation: ApplicationOperation) -> int:
    """Return the HTTP status of a successful response for *operation*."""

    if not isinstance(operation, ApplicationOperation):
        raise TypeError(
            f"operation must be an ApplicationOperation, not {type(operation).__name__}"
        )
    return _SUCCESS_STATUS_CODES.get(operation, _DEFAULT_SUCCESS_STATUS)


def http_status_for(
    response: ApplicationResponse, *, operation: ApplicationOperation
) -> int:
    """Return the frozen HTTP status of one public application response.

    A response that carries a public error is decided by that error's code.  A
    response that carries no error is a success, except for a cancellation,
    which the frozen map records as ``409`` and never as a 2xx success.
    """

    if not isinstance(response, ApplicationResponse):
        raise TypeError(
            f"response must be an ApplicationResponse, not {type(response).__name__}"
        )
    if response.error is not None:
        return status_code_for(response.error.code)
    if response.status is ApplicationStatus.CANCELLED:
        return status_code_for(ApplicationErrorCode.CANCELLED)
    return success_status_code(operation)


def invalid_request_error(reason_code: str) -> ApplicationError:
    """Return the public error for one adapter-level transport defect.

    The message and the code stay application-owned; only the reason code names
    the transport defect, which keeps error reporting in one vocabulary.
    """

    if not isinstance(reason_code, str) or not reason_code:
        raise ValueError("reason_code must be a non-empty string")
    return InvalidApplicationRequestError(
        details={"reason_code": reason_code}
    ).to_public_error()


def framework_error(status_code: int) -> ApplicationError:
    """Return the safe public error for one framework routing status.

    Only the routing outcomes a public surface can produce are translated.  Any
    other framework status is reported as ``INTERNAL_FAILURE`` with the generic
    message, so an unexpected status can never be echoed to a client.
    """

    if isinstance(status_code, bool) or not isinstance(status_code, int):
        raise TypeError("status_code must be an int")
    failure, reason = _FRAMEWORK_ROUTING_FAILURES.get(
        status_code, (InternalApplicationError, REASON_INTERNAL_DEFECT)
    )
    return failure(details={"reason_code": reason}).to_public_error()
