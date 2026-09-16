"""Phase 11.3 — safe application error mapping tests.

The public application error model is fail-closed.  A typed application failure
maps to exactly one closed public code with an application-owned constant
message; any unexpected internal exception maps to ``INTERNAL_FAILURE`` with a
generic public message, so no internal text, exception repr, filesystem path,
traceback or secret value can reach a public response.

See ``docs/superpowers/specs/2026-09-16-phase-11.3-application-backend-design.md``.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from types import MappingProxyType

import pytest

from cmm.application.contracts import (
    APPLICATION_API_VERSION,
    ApplicationError,
    ApplicationErrorCode,
    ApplicationStatus,
)
from cmm.application.errors import (
    ApplicationCancelledError,
    ApplicationConflictError,
    ApplicationResourceNotFoundError,
    ApplicationServiceError,
    ApprovalRequiredApplicationError,
    CapabilityUnavailableError,
    ConcurrencyConflictError,
    IdempotencyConflictError,
    InternalApplicationError,
    InvalidApplicationRequestError,
    PolicyDeniedApplicationError,
    UnsupportedApplicationVersionError,
    failed_response,
    safe_error_from_exception,
)

#: Every typed application failure and the one public code it must expose.
TYPED_ERRORS: tuple[tuple[type[ApplicationServiceError], ApplicationErrorCode], ...] = (
    (ApplicationServiceError, ApplicationErrorCode.INTERNAL_FAILURE),
    (InvalidApplicationRequestError, ApplicationErrorCode.INVALID_REQUEST),
    (UnsupportedApplicationVersionError, ApplicationErrorCode.UNSUPPORTED_VERSION),
    (ApplicationResourceNotFoundError, ApplicationErrorCode.RESOURCE_NOT_FOUND),
    (ApplicationConflictError, ApplicationErrorCode.CONFLICT),
    (CapabilityUnavailableError, ApplicationErrorCode.CAPABILITY_UNAVAILABLE),
    (IdempotencyConflictError, ApplicationErrorCode.IDEMPOTENCY_CONFLICT),
    (ConcurrencyConflictError, ApplicationErrorCode.CONCURRENCY_CONFLICT),
    (ApplicationCancelledError, ApplicationErrorCode.CANCELLED),
    (PolicyDeniedApplicationError, ApplicationErrorCode.POLICY_DENIED),
    (ApprovalRequiredApplicationError, ApplicationErrorCode.APPROVAL_REQUIRED),
    (InternalApplicationError, ApplicationErrorCode.INTERNAL_FAILURE),
)

#: Every typed failure that must not advertise automatic retry.
NON_RETRYABLE_ERRORS = tuple(
    item for item in TYPED_ERRORS if item[0] is not ConcurrencyConflictError
)

#: The one safe public message used for unexpected internal failures.
GENERIC_FAILURE_MESSAGE = "Application request failed closed"


# ── Typed failure identity ───────────────────────────────────────────────────


@pytest.mark.parametrize(("error_type", "expected_code"), TYPED_ERRORS)
def test_typed_error_maps_to_its_public_code(
    error_type: type[ApplicationServiceError],
    expected_code: ApplicationErrorCode,
) -> None:
    error = safe_error_from_exception(error_type())

    assert error.code is expected_code
    assert isinstance(error.message, str)
    assert error.message.strip()


@pytest.mark.parametrize(("error_type", "expected_code"), TYPED_ERRORS)
def test_public_error_code_is_declared_on_the_type(
    error_type: type[ApplicationServiceError],
    expected_code: ApplicationErrorCode,
) -> None:
    assert error_type.code is expected_code


@pytest.mark.parametrize(("error_type", "expected_code"), TYPED_ERRORS)
def test_typed_error_stores_code_message_retryable_and_details(
    error_type: type[ApplicationServiceError],
    expected_code: ApplicationErrorCode,
) -> None:
    error = error_type()

    assert error.code is expected_code
    assert error.safe_message == str(error)
    assert error.safe_message.strip()
    assert isinstance(error.retryable, bool)
    assert dict(error.details) == {}


@pytest.mark.parametrize(("error_type", "_code"), TYPED_ERRORS)
def test_every_typed_error_is_a_application_service_error(
    error_type: type[ApplicationServiceError],
    _code: ApplicationErrorCode,
) -> None:
    """The one catchable failure family keeps the boundary mappable."""

    with pytest.raises(ApplicationServiceError):
        raise error_type()


def test_concurrency_conflict_declares_a_safe_retry() -> None:
    """An optimistic revision conflict is retryable after refetching state."""

    error = safe_error_from_exception(ConcurrencyConflictError())

    assert error.code is ApplicationErrorCode.CONCURRENCY_CONFLICT
    assert error.retryable is True


@pytest.mark.parametrize(("error_type", "_code"), NON_RETRYABLE_ERRORS)
def test_other_typed_errors_do_not_declare_a_retry(
    error_type: type[ApplicationServiceError],
    _code: ApplicationErrorCode,
) -> None:
    assert safe_error_from_exception(error_type()).retryable is False


# ── Safe text boundary ───────────────────────────────────────────────────────


def test_internal_exception_text_is_not_exposed() -> None:
    error = safe_error_from_exception(RuntimeError("/Users/chris/token=secret"))

    assert error.code is ApplicationErrorCode.INTERNAL_FAILURE
    assert "secret" not in error.message
    assert "/Users/" not in error.message
    assert error.message == GENERIC_FAILURE_MESSAGE
    assert dict(error.details) == {}
    assert error.retryable is False


@pytest.mark.parametrize(
    "exc",
    [
        ValueError("/Users/chris/CMM OS/cmm/private.py boom"),
        KeyError("sk-live-0000000000000000"),
        OSError("permission denied for /Users/chris/.env"),
        RuntimeError(""),
    ],
)
def test_unexpected_exceptions_fail_closed(exc: BaseException) -> None:
    error = safe_error_from_exception(exc)

    assert error.code is ApplicationErrorCode.INTERNAL_FAILURE
    assert error.message == GENERIC_FAILURE_MESSAGE
    assert dict(error.details) == {}


def test_chained_cause_never_reaches_the_public_error() -> None:
    try:
        try:
            raise RuntimeError("/Users/chris/token=secret")
        except RuntimeError as cause:
            raise InternalApplicationError() from cause
    except InternalApplicationError as error:
        public = safe_error_from_exception(error)

    assert public.code is ApplicationErrorCode.INTERNAL_FAILURE
    assert public.message == GENERIC_FAILURE_MESSAGE
    assert "secret" not in public.message
    assert "/Users/" not in public.message
    assert dict(public.details) == {}


def test_typed_error_text_is_the_application_owned_safe_message() -> None:
    """``str(error)`` is the safe message, never internal provenance."""

    error = PolicyDeniedApplicationError()

    assert str(error) == error.safe_message
    assert error.safe_message == "Application request was denied by policy"
    assert safe_error_from_exception(error).message == error.safe_message


def test_safe_conversion_rejects_non_exceptions() -> None:
    with pytest.raises(TypeError):
        safe_error_from_exception("boom")  # type: ignore[arg-type]


# ── Safe details grammar ─────────────────────────────────────────────────────


def test_safe_details_are_preserved_and_frozen() -> None:
    details = {"session_id": "session-1", "reason_code": "SESSION_REVISION_STALE"}
    error = ApplicationResourceNotFoundError(details=details)

    details["session_id"] = "session-2"

    assert isinstance(error.details, Mapping)
    assert error.details["session_id"] == "session-1"
    assert error.details["reason_code"] == "SESSION_REVISION_STALE"
    assert isinstance(error.to_public_error().details, MappingProxyType)


def test_public_error_details_are_independent_of_the_typed_error() -> None:
    error = ApplicationConflictError(details={"session_id": "session-1"})
    public = error.to_public_error()

    assert isinstance(public, ApplicationError)
    assert public.code is ApplicationErrorCode.CONFLICT
    assert public.message == error.safe_message
    assert dict(public.details) == {"session_id": "session-1"}


@pytest.mark.parametrize(
    "key",
    [
        "token",
        "secret",
        "password",
        "apiKey",
        "api-key",
        "api_key",
        "private_key",
        "authorization",
        "cookie",
        "credential",
    ],
)
def test_secret_shaped_detail_keys_fail_closed(key: str) -> None:
    with pytest.raises(ValueError):
        InternalApplicationError(details={key: "value"})


@pytest.mark.parametrize(
    "details",
    [
        {"reason_code": b"raw-bytes"},
        {"reason_code": object()},
        {"nested": {"token": "value"}},
        {"reason_code": {"inner": {"apiKey": "value"}}},
        ("session-1",),
    ],
)
def test_unsafe_detail_values_fail_closed(details: object) -> None:
    with pytest.raises((TypeError, ValueError)):
        InternalApplicationError(details=details)  # type: ignore[arg-type]


# ── Failed response helper ───────────────────────────────────────────────────


def test_failed_response_is_versioned_and_carries_the_error() -> None:
    error = PolicyDeniedApplicationError().to_public_error()

    response = failed_response("req-1", error)

    assert response.request_id == "req-1"
    assert response.api_version == APPLICATION_API_VERSION
    assert response.status is ApplicationStatus.FAILED
    assert response.error is error
    assert response.data is None
    assert dict(response.metadata) == {}


def test_failed_response_serializes_without_internal_text() -> None:
    response = failed_response(
        "req-1", safe_error_from_exception(RuntimeError("/Users/chris/token=secret"))
    )

    document = response.to_dict()
    rendered = json.dumps(document)

    assert document["status"] == ApplicationStatus.FAILED.value
    assert document["error"]["code"] == ApplicationErrorCode.INTERNAL_FAILURE.value
    assert document["error"]["message"] == GENERIC_FAILURE_MESSAGE
    assert document["error"]["retryable"] is False
    assert document["error"]["details"] == {}
    assert document["data"] is None
    assert "secret" not in rendered
    assert "/Users/" not in rendered


def test_failed_response_requires_a_public_application_error() -> None:
    with pytest.raises(TypeError):
        failed_response("req-1", RuntimeError("boom"))  # type: ignore[arg-type]


def test_failed_response_fails_closed_on_an_invalid_request_id() -> None:
    with pytest.raises(ValueError):
        failed_response("", InternalApplicationError().to_public_error())
