"""Phase 11.3 — API transport model tests.

Phase 11.3 adds exactly one approved HTTP framework dependency.  These tests
lock that dependency boundary and the transport DTOs of the frozen v1 surface:

- the request bodies declare only public fields, with the frozen size bounds, so
  oversized input fails at transport parse;
- ``idempotency_key`` is deliberately *not* a body field — it is carried by the
  ``Idempotency-Key`` header and mapped into the application command;
- the response models re-validate the application contracts' ``to_dict()``, so
  the transport never re-implements the public shape and a projection that
  drifts from the frozen v1 envelope fails loudly instead of being served;
- the transport can not serve an API version the application layer does not own,
  and can not add a field the frozen envelope does not declare.

The safe metadata grammar (secret-shaped keys, binary data, unbounded nesting)
is owned by ``cmm.application.contracts`` and is deliberately *not* duplicated
here; the transport only bounds the container.

See ``docs/superpowers/specs/2026-09-16-phase-11.3-application-backend-design.md``.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from cmm.api.models import (
    ApplicationCapabilityModel,
    ApplicationErrorModel,
    ApplicationHealthModel,
    ApplicationResponseModel,
    ApplicationSessionModel,
    CreateSessionBody,
    MessageBody,
    capability_model_from,
    error_model_from,
    health_model_from,
    response_model_from,
    session_model_from,
)
from cmm.application import (
    APPLICATION_API_VERSION,
    MAX_IDENTIFIER_LENGTH,
    MAX_MESSAGE_LENGTH,
    ApplicationCapability,
    ApplicationError,
    ApplicationErrorCode,
    ApplicationHealth,
    ApplicationResponse,
    ApplicationSession,
    ApplicationStatus,
    CapabilityStatus,
)

REQUEST_ID = "req-transport-1"
SESSION_ID = "session-1"


def test_fastapi_dependency_is_available() -> None:
    import fastapi

    assert fastapi.__version__


# ── Request bodies ───────────────────────────────────────────────────────────


def test_create_session_body_defaults_to_a_generated_session_id() -> None:
    body = CreateSessionBody()

    assert body.session_id is None


def test_create_session_body_accepts_an_explicit_session_id() -> None:
    body = CreateSessionBody(session_id=SESSION_ID)

    assert body.session_id == SESSION_ID


def test_create_session_body_bounds_the_session_identifier() -> None:
    CreateSessionBody(session_id="s" * MAX_IDENTIFIER_LENGTH)

    with pytest.raises(ValidationError):
        CreateSessionBody(session_id="s" * (MAX_IDENTIFIER_LENGTH + 1))

    with pytest.raises(ValidationError):
        CreateSessionBody(session_id="")


def test_create_session_body_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        CreateSessionBody(session_id=SESSION_ID, idempotency_key="key-1")


def test_message_body_defaults_to_public_text() -> None:
    body = MessageBody(actor_id="actor-1", content="What changed?")

    assert body.message_id is None
    assert body.content_type == "text/plain"
    assert body.metadata == {}
    assert body.expected_session_revision is None


def test_message_body_never_declares_an_idempotency_key() -> None:
    """Idempotency is a header concern; the body must not offer a second path."""

    assert "idempotency_key" not in MessageBody.model_fields

    with pytest.raises(ValidationError):
        MessageBody(
            actor_id="actor-1", content="What changed?", idempotency_key="key-1"
        )


def test_message_body_requires_an_actor_and_content() -> None:
    with pytest.raises(ValidationError):
        MessageBody(actor_id="actor-1")

    with pytest.raises(ValidationError):
        MessageBody(content="What changed?")


def test_message_body_bounds_public_content() -> None:
    MessageBody(actor_id="actor-1", content="c" * MAX_MESSAGE_LENGTH)

    with pytest.raises(ValidationError):
        MessageBody(actor_id="actor-1", content="c" * (MAX_MESSAGE_LENGTH + 1))

    with pytest.raises(ValidationError):
        MessageBody(actor_id="actor-1", content="")


def test_message_body_bounds_the_actor_identifier() -> None:
    MessageBody(actor_id="a" * MAX_IDENTIFIER_LENGTH, content="hello")

    with pytest.raises(ValidationError):
        MessageBody(actor_id="a" * (MAX_IDENTIFIER_LENGTH + 1), content="hello")

    with pytest.raises(ValidationError):
        MessageBody(actor_id="", content="hello")


def test_message_body_bounds_an_optional_message_identifier() -> None:
    body = MessageBody(actor_id="actor-1", content="hello", message_id="message-1")

    assert body.message_id == "message-1"

    with pytest.raises(ValidationError):
        MessageBody(
            actor_id="actor-1",
            content="hello",
            message_id="m" * (MAX_IDENTIFIER_LENGTH + 1),
        )

    with pytest.raises(ValidationError):
        MessageBody(actor_id="actor-1", content="hello", message_id="")


def test_message_body_bounds_an_optional_expected_revision() -> None:
    body = MessageBody(actor_id="actor-1", content="hello", expected_session_revision=2)

    assert body.expected_session_revision == 2

    with pytest.raises(ValidationError):
        MessageBody(actor_id="actor-1", content="hello", expected_session_revision=-1)

    # A boolean is a caller defect, not a revision of one.
    with pytest.raises(ValidationError):
        MessageBody(actor_id="actor-1", content="hello", expected_session_revision=True)


def test_message_body_accepts_json_metadata_and_rejects_opaque_values() -> None:
    body = MessageBody(
        actor_id="actor-1",
        content="hello",
        metadata={"channel": "cli", "tags": ["a", "b"], "attempt": 2},
    )

    assert body.metadata["channel"] == "cli"

    with pytest.raises(ValidationError):
        MessageBody(actor_id="actor-1", content="hello", metadata={"raw": object()})


def test_message_body_leaves_metadata_grammar_to_the_application_layer() -> None:
    """The transport bounds the container only; the application owns the grammar."""

    body = MessageBody(
        actor_id="actor-1", content="hello", metadata={"client_secret": "value"}
    )

    assert body.metadata == {"client_secret": "value"}


# ── Response models ──────────────────────────────────────────────────────────


def _response(**overrides: object) -> ApplicationResponse:
    fields: dict[str, object] = {
        "request_id": REQUEST_ID,
        "api_version": APPLICATION_API_VERSION,
        "status": ApplicationStatus.ROUTED,
        "data": {"session_id": SESSION_ID, "status": "routed"},
        "error": None,
        "metadata": {},
    }
    fields.update(overrides)
    return ApplicationResponse(**fields)  # type: ignore[arg-type]


def test_response_envelope_round_trips_the_application_contract() -> None:
    response = _response()

    envelope = response_model_from(response)

    assert isinstance(envelope, ApplicationResponseModel)
    assert envelope.model_dump(mode="json") == response.to_dict()


def test_response_envelope_round_trips_a_safe_public_error() -> None:
    error = ApplicationError(
        code=ApplicationErrorCode.RESOURCE_NOT_FOUND,
        message="Application resource was not found",
        retryable=False,
        details={"reason_code": "SESSION_NOT_FOUND"},
    )
    response = _response(
        status=ApplicationStatus.FAILED,
        data=None,
        error=error,
    )

    envelope = response_model_from(response)

    assert envelope.model_dump(mode="json") == response.to_dict()
    assert envelope.error is not None
    assert envelope.error.code is ApplicationErrorCode.RESOURCE_NOT_FOUND


def test_response_envelope_rejects_an_unknown_field() -> None:
    with pytest.raises(ValidationError):
        ApplicationResponseModel(
            request_id=REQUEST_ID,
            api_version=APPLICATION_API_VERSION,
            status=ApplicationStatus.SUCCESS,
            data=None,
            error=None,
            metadata={},
            traceback="internal detail",
        )


def test_response_envelope_rejects_a_foreign_api_version() -> None:
    with pytest.raises(ValidationError):
        ApplicationResponseModel(
            request_id=REQUEST_ID,
            api_version="v2",
            status=ApplicationStatus.SUCCESS,
            data=None,
            error=None,
            metadata={},
        )


def test_response_envelope_rejects_an_unknown_public_status() -> None:
    with pytest.raises(ValidationError):
        ApplicationResponseModel(
            request_id=REQUEST_ID,
            api_version=APPLICATION_API_VERSION,
            status="finished",
            data=None,
            error=None,
            metadata={},
        )


def test_error_model_round_trips_an_application_error() -> None:
    error = ApplicationError(
        code=ApplicationErrorCode.CONFLICT,
        message="Application resource state conflicts with the request",
        retryable=True,
        details={"reason_code": "SESSION_ALREADY_EXISTS"},
    )

    model = error_model_from(error)

    assert isinstance(model, ApplicationErrorModel)
    assert model.model_dump(mode="json") == error.to_dict()


def test_error_model_rejects_an_unknown_error_code() -> None:
    with pytest.raises(ValidationError):
        ApplicationErrorModel(
            code="TEAPOT", message="boom", retryable=False, details={}
        )


def test_session_model_round_trips_an_application_session() -> None:
    session = ApplicationSession(
        session_id=SESSION_ID,
        revision=3,
        status="active",
        created_at="2026-09-16T10:00:00+00:00",
        updated_at="2026-09-16T10:05:00+00:00",
    )

    model = session_model_from(session)

    assert isinstance(model, ApplicationSessionModel)
    assert model.model_dump(mode="json") == session.to_dict()


def test_capability_model_round_trips_an_application_capability() -> None:
    capability = ApplicationCapability(
        capability_id="sessions",
        status=CapabilityStatus.AVAILABLE,
        version=APPLICATION_API_VERSION,
        operations=("sessions.create", "sessions.get"),
        reason_code=None,
    )

    model = capability_model_from(capability)

    assert isinstance(model, ApplicationCapabilityModel)
    assert model.model_dump(mode="json") == capability.to_dict()


def test_health_model_round_trips_an_application_health() -> None:
    health = ApplicationHealth(
        status="ok",
        api_version=APPLICATION_API_VERSION,
        platform_ready=True,
        services=("orchestration.orchestrator",),
    )

    model = health_model_from(health)

    assert isinstance(model, ApplicationHealthModel)
    assert model.model_dump(mode="json") == health.to_dict()


def test_health_model_rejects_a_foreign_api_version() -> None:
    with pytest.raises(ValidationError):
        ApplicationHealthModel(
            status="ok",
            api_version="v2",
            platform_ready=True,
            services=[],
        )


@pytest.mark.parametrize(
    "conversion",
    [
        error_model_from,
        session_model_from,
        capability_model_from,
        health_model_from,
        response_model_from,
    ],
)
def test_conversions_require_the_application_contract(conversion: object) -> None:
    """A structurally similar object is never accepted as a public contract."""

    class _Duck:
        def to_dict(self) -> dict[str, object]:  # pragma: no cover
            raise AssertionError("a duck-typed value must never be converted")

    with pytest.raises(TypeError):
        conversion(_Duck())  # type: ignore[operator]
