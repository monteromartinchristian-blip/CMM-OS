"""Phase 11.3 — HTTP v1 surface tests.

Task 10 locks the transport half of the frozen v1 HTTP contract before any
route exists:

- the error-code to HTTP status map, complete over the closed public error set;
- the success status rule (only session creation answers ``201``);
- the safe failure envelope: an internal defect becomes ``INTERNAL_FAILURE``
  with the application-owned message and no exception text, path or credential.

Route-level behaviour is added in Task 11.

See ``docs/superpowers/specs/2026-09-16-phase-11.3-application-backend-design.md``.
"""

from __future__ import annotations

import json

import pytest

from cmm.api.errors import (
    REASON_INVALID_IDEMPOTENCY_KEY,
    REASON_INVALID_REQUEST_ID,
    http_status_for,
    invalid_request_error,
    status_code_for,
    success_status_code,
)
from cmm.api.models import response_model_from
from cmm.application import (
    APPLICATION_API_VERSION,
    ApplicationError,
    ApplicationErrorCode,
    ApplicationOperation,
    ApplicationResponse,
    ApplicationStatus,
    InvalidApplicationRequestError,
    failed_response,
    safe_error_from_exception,
)
from cmm.application.errors import GENERIC_FAILURE_MESSAGE

REQUEST_ID = "req-http-1"

#: The frozen status map of the Phase 11.3 implementation plan.
FROZEN_STATUS_MAP = {
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

#: Raw internal defect text that must never reach a client.
RAW_DEFECT_TEXT = (
    "Traceback (most recent call last): internal defect at "
    "/private/tmp/cmm-internal-detail with secret AKIA-EXAMPLE-SECRET-KEY"
)


def _failed_response(error_code: ApplicationErrorCode) -> ApplicationResponse:
    """Return one safe failure response carrying *error_code*."""

    return failed_response(
        REQUEST_ID,
        ApplicationError(
            code=error_code,
            message="Application-owned public message",
            retryable=False,
            details={},
        ),
    )


# ── Frozen status map ────────────────────────────────────────────────────────


def test_frozen_status_map_covers_every_public_error_code() -> None:
    assert set(FROZEN_STATUS_MAP) == set(ApplicationErrorCode)


@pytest.mark.parametrize(
    ("error_code", "expected_status"),
    list(FROZEN_STATUS_MAP.items()),
    ids=[code.value for code in FROZEN_STATUS_MAP],
)
def test_status_code_for_matches_the_frozen_map(
    error_code: ApplicationErrorCode, expected_status: int
) -> None:
    assert status_code_for(error_code) == expected_status


def test_status_code_for_rejects_a_non_error_code() -> None:
    with pytest.raises(TypeError):
        status_code_for("INTERNAL_FAILURE")  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "operation",
    [
        ApplicationOperation.HEALTH_GET,
        ApplicationOperation.CAPABILITIES_LIST,
        ApplicationOperation.SESSION_GET,
        ApplicationOperation.MESSAGE_SUBMIT,
        ApplicationOperation.REQUEST_CANCEL,
    ],
)
def test_success_status_is_200_except_session_creation(
    operation: ApplicationOperation,
) -> None:
    assert success_status_code(operation) == 200


def test_success_status_of_session_creation_is_201() -> None:
    assert success_status_code(ApplicationOperation.SESSION_CREATE) == 201


def test_success_status_rejects_a_non_operation() -> None:
    with pytest.raises(TypeError):
        success_status_code("sessions.create")  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "status",
    [
        ApplicationStatus.SUCCESS,
        ApplicationStatus.ROUTED,
        ApplicationStatus.NEEDS_CLARIFICATION,
        ApplicationStatus.ESCALATED,
    ],
)
def test_successful_response_statuses_map_to_200(status: ApplicationStatus) -> None:
    response = ApplicationResponse(
        request_id=REQUEST_ID,
        api_version=APPLICATION_API_VERSION,
        status=status,
        data={"session_id": "session-1"},
        error=None,
        metadata={},
    )

    assert (
        http_status_for(response, operation=ApplicationOperation.MESSAGE_SUBMIT) == 200
    )


def test_session_creation_success_maps_to_201() -> None:
    response = ApplicationResponse(
        request_id=REQUEST_ID,
        api_version=APPLICATION_API_VERSION,
        status=ApplicationStatus.SUCCESS,
        data={"session_id": "session-1"},
        error=None,
        metadata={},
    )

    assert (
        http_status_for(response, operation=ApplicationOperation.SESSION_CREATE) == 201
    )


def test_a_public_error_decides_the_status_of_a_failed_response() -> None:
    assert (
        http_status_for(
            _failed_response(ApplicationErrorCode.RESOURCE_NOT_FOUND),
            operation=ApplicationOperation.SESSION_GET,
        )
        == 404
    )
    assert (
        http_status_for(
            _failed_response(ApplicationErrorCode.INTERNAL_FAILURE),
            operation=ApplicationOperation.MESSAGE_SUBMIT,
        )
        == 500
    )


def test_a_cancelled_response_without_a_public_error_maps_to_409() -> None:
    response = ApplicationResponse(
        request_id=REQUEST_ID,
        api_version=APPLICATION_API_VERSION,
        status=ApplicationStatus.CANCELLED,
        data=None,
        error=None,
        metadata={},
    )

    assert (
        http_status_for(response, operation=ApplicationOperation.MESSAGE_SUBMIT) == 409
    )


def test_http_status_for_rejects_a_non_response() -> None:
    with pytest.raises(TypeError):
        http_status_for(
            {"status": "success"}, operation=ApplicationOperation.HEALTH_GET
        )  # type: ignore[arg-type]


# ── Safe failure envelope ────────────────────────────────────────────────────


def test_internal_failure_envelope_hides_the_internal_defect() -> None:
    defect = RuntimeError(RAW_DEFECT_TEXT)

    response = failed_response(REQUEST_ID, safe_error_from_exception(defect))
    envelope = response_model_from(response)
    serialized = json.dumps(envelope.model_dump(mode="json"), sort_keys=True)

    assert envelope.error is not None
    assert envelope.error.code is ApplicationErrorCode.INTERNAL_FAILURE
    assert envelope.error.message == GENERIC_FAILURE_MESSAGE
    assert envelope.error.details == {}
    assert status_code_for(envelope.error.code) == 500
    for forbidden in (
        "Traceback",
        "/private/tmp/cmm-internal-detail",
        "AKIA-EXAMPLE-SECRET-KEY",
    ):
        assert forbidden not in serialized


def test_transport_defects_are_reported_as_application_owned_errors() -> None:
    error = invalid_request_error(REASON_INVALID_REQUEST_ID)

    assert error.code is ApplicationErrorCode.INVALID_REQUEST
    assert error.retryable is False
    assert error.details == {"reason_code": REASON_INVALID_REQUEST_ID}
    assert error.message == InvalidApplicationRequestError().to_public_error().message
    assert status_code_for(error.code) == 400


def test_transport_defect_reason_codes_are_distinct() -> None:
    assert REASON_INVALID_REQUEST_ID != REASON_INVALID_IDEMPOTENCY_KEY


def test_transport_defect_error_requires_a_reason_code() -> None:
    with pytest.raises(ValueError):
        invalid_request_error("")


def test_failure_envelope_is_json_serializable_and_deterministic() -> None:
    response = _failed_response(ApplicationErrorCode.CONFLICT)

    first = response_model_from(response).model_dump(mode="json")
    second = response_model_from(response).model_dump(mode="json")

    assert first == second == response.to_dict()
