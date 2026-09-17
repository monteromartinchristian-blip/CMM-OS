"""Phase 11.3 — the v1 HTTP adapter: app factory, routes and error handling.

``create_app`` is the whole transport composition.  It receives one already
composed :class:`~cmm.application.gateway.ApplicationGateway` and never builds a
domain, agent, provider, workflow, session or orchestrator owner itself.  There
is no module-level gateway singleton: the gateway is captured in the route
closures (and exposed as ``app.state.application_gateway``) so two applications
built from two gateways stay independent.

Six rules make the adapter safe:

- **one public surface** — exactly the frozen ``/v1`` paths are served, with no
  unversioned alias, no ``/v2`` and no WebSocket route;
- **explicit versioned contracts** — every route builds a real
  ``ApplicationQuery`` or ``ApplicationCommand`` with
  ``api_version=APPLICATION_API_VERSION``; nothing is dispatched by string,
  reflection or a handler registry;
- **bounded transport input** — request bodies, path parameters and the
  correlation/idempotency headers are bounded, so oversized input fails before
  it can reach the application layer;
- **one response envelope** — success and failure share the public
  :class:`~cmm.api.models.ApplicationResponseModel`, and every error path
  (validation, routing status, internal defect) answers with that envelope
  instead of a framework default payload;
- **fail-closed** — no exception escapes a route: an adapter or application
  defect becomes ``INTERNAL_FAILURE`` with the application-owned message, and an
  input the public contract rejects becomes ``INVALID_REQUEST`` rather than a
  reported internal failure;
- **thin sync adapter** — handlers are synchronous, so the canonical
  synchronous application core is invoked from the framework's thread pool and
  no async duplicate of any service exists.

Phase 11.5 (DP-105) adds one strictly additive keyword — ``conversation`` — and
the five conversation routes of the conversational surface.  Those handlers
still only parse, delegate to the one ``ConversationService``, serialize and map
safe errors: without the service every conversation route answers the frozen
capability-unavailable failure, and a caller that passes no service keeps the
pre-existing behaviour and OpenAPI of every pre-existing endpoint.

See ``docs/reference/phase-11-application-backend.md``.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Annotated, Any
from uuid import UUID, uuid4, uuid5

from fastapi import FastAPI, Path, Request, Response
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as FrameworkHTTPException
from starlette.responses import JSONResponse, StreamingResponse

from cmm.api.errors import (
    REASON_INVALID_IDEMPOTENCY_KEY,
    REASON_INVALID_REQUEST_BODY,
    REASON_INVALID_REQUEST_CONTRACT,
    REASON_INVALID_REQUEST_ID,
    framework_error,
    http_status_for,
    invalid_request_error,
    status_code_for,
)
from cmm.api.models import (
    ApplicationResponseModel,
    ConversationEditBody,
    ConversationMessageBody,
    ConversationRegenerateBody,
    CreateSessionBody,
    MessageBody,
    assistant_response_model_from,
    conversation_state_model_from,
    response_model_from,
)
from cmm.api.streaming import (
    SSE_MEDIA_TYPE,
    events_for_response,
    sse_frames,
)
from cmm.application import (
    APPLICATION_API_VERSION,
    MAX_IDEMPOTENCY_KEY_LENGTH,
    MAX_IDENTIFIER_LENGTH,
    ApplicationCommand,
    ApplicationError,
    ApplicationGateway,
    ApplicationOperation,
    ApplicationQuery,
    ApplicationRequest,
    ApplicationResourceNotFoundError,
    ApplicationResponse,
    ApplicationServiceError,
    ApplicationStatus,
    ApprovalRequiredApplicationError,
    CapabilityUnavailableError,
    ConcurrencyConflictError,
    InternalApplicationError,
    InvalidApplicationRequestError,
    PolicyDeniedApplicationError,
    failed_response,
    safe_error_from_exception,
)
from cmm.conversation.contracts import (
    ConversationAttachmentRef,
    ConversationMessage,
    ConversationRole,
)
from cmm.conversation.errors import (
    ConversationBoundaryError,
    ConversationErrorCode,
    ConversationSessionNotFoundError,
)
from cmm.conversation.service import ConversationService

__all__ = ["create_app"]

#: Public request correlation header; generated when absent and always echoed.
REQUEST_ID_HEADER = "X-Request-ID"

#: Public idempotency header; only the commands that opt into replay read it.
IDEMPOTENCY_KEY_HEADER = "Idempotency-Key"

#: Phase 11.5 (DP-105) — the successful status of every conversation answer.  No
#: conversation route creates a public resource, so the frozen status map's
#: default applies; ``test_the_conversation_success_status_is_the_frozen_default``
#: pins the equality.
_CONVERSATION_SUCCESS_STATUS = 200

#: Phase 11.5 (DP-105) — the safe public application failure of every closed
#: conversational boundary code.  The mapping is total: a code the table does
#: not know (and any unexpected defect) becomes the one generic internal
#: failure, and the public message stays application-owned, so no conversational
#: text, path or traceback can be published by copying it.
_CONVERSATION_FAILURES: Mapping[
    ConversationErrorCode, type[ApplicationServiceError]
] = {
    ConversationErrorCode.INVALID_REQUEST: InvalidApplicationRequestError,
    ConversationErrorCode.SESSION_NOT_FOUND: ApplicationResourceNotFoundError,
    ConversationErrorCode.SESSION_CONFLICT: ConcurrencyConflictError,
    ConversationErrorCode.CAPABILITY_UNAVAILABLE: CapabilityUnavailableError,
    ConversationErrorCode.POLICY_DENIED: PolicyDeniedApplicationError,
    ConversationErrorCode.APPROVAL_REQUIRED: ApprovalRequiredApplicationError,
    ConversationErrorCode.INTERNAL_FAILURE: InternalApplicationError,
}

#: A public identifier as it appears in a request path.
_PathIdentifier = Annotated[str, Path(min_length=1, max_length=MAX_IDENTIFIER_LENGTH)]

#: Namespace of the generated message identity of a keyed command.  Deriving it
#: from the caller's idempotency key keeps a retry of the same keyed command
#: canonically identical, which is what makes the replay possible.
_MESSAGE_ID_NAMESPACE = UUID("9138a986-0034-48fe-8647-86a564918bb9")


def create_app(
    gateway: ApplicationGateway,
    *,
    conversation: ConversationService | None = None,
) -> FastAPI:
    """Build the v1 HTTP adapter over one composed application gateway.

    The optional keyword-only ``conversation`` service is the Phase 11.5
    (DP-105) additive seam: the transport adapter presents the conversational
    surface and delegates every conversational turn to that one service.  A
    caller that passes no service keeps the pre-existing routes and OpenAPI
    unchanged, and every conversation route answers the frozen
    capability-unavailable failure instead of failing at construction.
    """

    if not isinstance(gateway, ApplicationGateway):
        raise TypeError(
            "gateway must be the canonical ApplicationGateway, "
            f"not {type(gateway).__name__}"
        )

    if conversation is not None and not isinstance(conversation, ConversationService):
        raise TypeError(
            "conversation must be the canonical ConversationService or None, "
            f"not {type(conversation).__name__}"
        )

    app = FastAPI(title="CMM OS Application API", version="1.0.0")
    app.state.application_gateway = gateway

    # ── Transport parsing ───────────────────────────────────────────────────

    def _correlation_identity(
        raw_request: Request,
    ) -> tuple[str, ApplicationError | None]:
        """Return the usable request identity and the defect, if any.

        An absent or blank header is generated rather than rejected; an
        unusable one is a transport defect and never becomes the correlation
        identity of the response.
        """

        supplied = raw_request.headers.get(REQUEST_ID_HEADER)
        if supplied is None or not supplied.strip():
            return str(uuid4()), None
        normalized = supplied.strip()
        if len(normalized) > MAX_IDENTIFIER_LENGTH:
            return str(uuid4()), invalid_request_error(REASON_INVALID_REQUEST_ID)
        return normalized, None

    def _idempotency_key(
        raw_request: Request,
    ) -> tuple[str | None, ApplicationError | None]:
        """Return the usable idempotency key and the defect, if any."""

        supplied = raw_request.headers.get(IDEMPOTENCY_KEY_HEADER)
        if supplied is None or not supplied.strip():
            return None, None
        normalized = supplied.strip()
        if len(normalized) > MAX_IDEMPOTENCY_KEY_LENGTH:
            return None, invalid_request_error(REASON_INVALID_IDEMPOTENCY_KEY)
        return normalized, None

    # ── Dispatch ────────────────────────────────────────────────────────────

    def _dispatch(
        raw_request: Request,
        build: Callable[[str, str | None], ApplicationRequest],
        *,
        idempotent: bool = False,
    ) -> ApplicationResponse:
        """Parse transport input, build one request and dispatch it once."""

        request_id, defect = _correlation_identity(raw_request)
        key: str | None = None
        if defect is None and idempotent:
            key, defect = _idempotency_key(raw_request)
        if defect is not None:
            return failed_response(request_id, defect)

        try:
            application_request = build(request_id, key)
        except (TypeError, ValueError):
            # The public application contract rejected values built from caller
            # input, so the request is invalid rather than internally broken.
            return failed_response(
                request_id, invalid_request_error(REASON_INVALID_REQUEST_CONTRACT)
            )

        try:
            return gateway.handle(application_request)
        except Exception as exc:  # noqa: BLE001 - the adapter boundary fails closed
            return failed_response(request_id, safe_error_from_exception(exc))

    def _respond(
        raw_request: Request,
        raw_response: Response,
        *,
        operation: ApplicationOperation,
        build: Callable[[str, str | None], ApplicationRequest],
        idempotent: bool = False,
    ) -> ApplicationResponseModel:
        """Dispatch once and translate the public response into transport."""

        application_response = _dispatch(raw_request, build, idempotent=idempotent)
        envelope = response_model_from(application_response)
        raw_response.status_code = http_status_for(
            application_response, operation=operation
        )
        raw_response.headers[REQUEST_ID_HEADER] = envelope.request_id
        return envelope

    def _error_response(request_id: str, error: ApplicationError) -> JSONResponse:
        """Return one safe failure envelope as a deterministic JSON response."""

        envelope = response_model_from(failed_response(request_id, error))
        json_response = JSONResponse(
            status_code=status_code_for(error.code),
            content=envelope.model_dump(mode="json"),
        )
        json_response.headers[REQUEST_ID_HEADER] = envelope.request_id
        return json_response

    # ── Failure handlers ────────────────────────────────────────────────────

    @app.exception_handler(RequestValidationError)
    async def _invalid_transport_payload(
        raw_request: Request, _exc: RequestValidationError
    ) -> JSONResponse:
        """Answer a malformed request with the one public error envelope.

        The framework's own validation detail is deliberately not published:
        the public error model is the canonical one.
        """

        request_id, defect = _correlation_identity(raw_request)
        error = (
            defect
            if defect is not None
            else invalid_request_error(REASON_INVALID_REQUEST_BODY)
        )
        return _error_response(request_id, error)

    @app.exception_handler(FrameworkHTTPException)
    async def _framework_status(
        raw_request: Request, exc: FrameworkHTTPException
    ) -> JSONResponse:
        """Translate a routing status into the one public error envelope."""

        request_id, _defect = _correlation_identity(raw_request)
        return _error_response(request_id, framework_error(exc.status_code))

    @app.exception_handler(Exception)
    async def _unexpected_defect(raw_request: Request, exc: Exception) -> JSONResponse:
        """Answer an unexpected defect with the one public error envelope."""

        request_id, _defect = _correlation_identity(raw_request)
        return _error_response(request_id, safe_error_from_exception(exc))

    # ── Message command ─────────────────────────────────────────────────────

    def _message_command(
        session_id: str, body: MessageBody
    ) -> Callable[[str, str | None], ApplicationRequest]:
        """Return the builder of one versioned message command.

        A caller-supplied message identity is used verbatim.  A generated one is
        a pure function of the ``Idempotency-Key`` when the caller opted into
        replay — so a retry of the same keyed command is canonically the same
        command and replays instead of conflicting — and a fresh identity
        otherwise, so two independent submissions stay two public messages.
        """

        def build(request_id: str, key: str | None) -> ApplicationRequest:
            message_id = body.message_id
            if message_id is None:
                message_id = (
                    str(uuid4())
                    if key is None
                    else str(uuid5(_MESSAGE_ID_NAMESPACE, key))
                )

            return ApplicationCommand(
                request_id=request_id,
                api_version=APPLICATION_API_VERSION,
                operation=ApplicationOperation.MESSAGE_SUBMIT,
                actor_id=body.actor_id,
                session_id=session_id,
                idempotency_key=key,
                expected_session_revision=body.expected_session_revision,
                payload={
                    "message_id": message_id,
                    "content": body.content,
                    "content_type": body.content_type,
                    "metadata": dict(body.metadata),
                },
            )

        return build

    # ── Routes ──────────────────────────────────────────────────────────────

    @app.get(
        "/v1/health",
        response_model=ApplicationResponseModel,
        summary="Report safe public platform readiness",
    )
    def get_health(
        raw_request: Request, raw_response: Response
    ) -> ApplicationResponseModel:
        return _respond(
            raw_request,
            raw_response,
            operation=ApplicationOperation.HEALTH_GET,
            build=lambda request_id, _key: ApplicationQuery(
                request_id=request_id,
                api_version=APPLICATION_API_VERSION,
                operation=ApplicationOperation.HEALTH_GET,
            ),
        )

    @app.get(
        "/v1/capabilities",
        response_model=ApplicationResponseModel,
        summary="List the declared public capabilities",
    )
    def get_capabilities(
        raw_request: Request, raw_response: Response
    ) -> ApplicationResponseModel:
        return _respond(
            raw_request,
            raw_response,
            operation=ApplicationOperation.CAPABILITIES_LIST,
            build=lambda request_id, _key: ApplicationQuery(
                request_id=request_id,
                api_version=APPLICATION_API_VERSION,
                operation=ApplicationOperation.CAPABILITIES_LIST,
            ),
        )

    @app.post(
        "/v1/sessions",
        status_code=201,
        response_model=ApplicationResponseModel,
        summary="Create one public session",
    )
    def create_session(
        raw_request: Request,
        raw_response: Response,
        body: CreateSessionBody | None = None,
    ) -> ApplicationResponseModel:
        payload: dict[str, Any] = {}
        if body is not None and body.session_id is not None:
            payload["session_id"] = body.session_id

        return _respond(
            raw_request,
            raw_response,
            operation=ApplicationOperation.SESSION_CREATE,
            idempotent=True,
            build=lambda request_id, key: ApplicationCommand(
                request_id=request_id,
                api_version=APPLICATION_API_VERSION,
                operation=ApplicationOperation.SESSION_CREATE,
                idempotency_key=key,
                payload=payload,
            ),
        )

    @app.get(
        "/v1/sessions/{session_id}",
        response_model=ApplicationResponseModel,
        summary="Read one public session",
    )
    def get_session(
        session_id: _PathIdentifier,
        raw_request: Request,
        raw_response: Response,
    ) -> ApplicationResponseModel:
        return _respond(
            raw_request,
            raw_response,
            operation=ApplicationOperation.SESSION_GET,
            build=lambda request_id, _key: ApplicationQuery(
                request_id=request_id,
                api_version=APPLICATION_API_VERSION,
                operation=ApplicationOperation.SESSION_GET,
                session_id=session_id,
            ),
        )

    @app.post(
        "/v1/sessions/{session_id}/messages",
        response_model=ApplicationResponseModel,
        summary="Submit one message to a public session",
    )
    def submit_message(
        session_id: _PathIdentifier,
        body: MessageBody,
        raw_request: Request,
        raw_response: Response,
    ) -> ApplicationResponseModel:
        return _respond(
            raw_request,
            raw_response,
            operation=ApplicationOperation.MESSAGE_SUBMIT,
            idempotent=True,
            build=_message_command(session_id, body),
        )

    @app.post(
        "/v1/sessions/{session_id}/messages/stream",
        summary="Stream one message response as server-sent events",
    )
    def stream_message(
        session_id: _PathIdentifier,
        body: MessageBody,
        raw_request: Request,
    ) -> StreamingResponse:
        """Dispatch the message command once and stream its safe events.

        The command is the same versioned ``MESSAGE_SUBMIT`` command the
        non-streaming route builds, and it is invoked exactly once — before the
        response body starts — so the stream only ever delivers one already
        computed result and can never re-run a command.  A failed application
        response is delivered in-band as a terminal ``error`` event with HTTP
        ``200``, which is what makes the failure readable by an SSE client; a
        malformed body never reaches this point and answers with the one public
        error envelope, and no exception text, traceback or internal payload can
        enter a frame.
        """

        application_response = _dispatch(
            raw_request,
            _message_command(session_id, body),
            idempotent=True,
        )
        return StreamingResponse(
            sse_frames(events_for_response(application_response)),
            media_type=SSE_MEDIA_TYPE,
            headers={REQUEST_ID_HEADER: application_response.request_id},
        )

    @app.post(
        "/v1/requests/{request_id}/cancel",
        response_model=ApplicationResponseModel,
        summary="Request cancellation of a submitted request",
    )
    def cancel_request(
        request_id: _PathIdentifier,
        raw_request: Request,
        raw_response: Response,
    ) -> ApplicationResponseModel:
        # The path identity is the cancellation target; the correlation identity
        # stays the request identity of this call.
        return _respond(
            raw_request,
            raw_response,
            operation=ApplicationOperation.REQUEST_CANCEL,
            build=lambda correlation_id, _key: ApplicationCommand(
                request_id=correlation_id,
                api_version=APPLICATION_API_VERSION,
                operation=ApplicationOperation.REQUEST_CANCEL,
                payload={"target_request_id": request_id},
            ),
        )

    # ── Conversation surface (Phase 11.5 / DP-105) ──────────────────────────

    def _conversation_error(exc: ConversationBoundaryError) -> ApplicationError:
        """Return the safe public application error of one conversational failure.

        The closed conversational code selects the application layer's own typed
        failure, so the public code and message stay application-owned and no
        conversational text is copied; an unexpected code falls to the one
        generic internal failure instead of being published.
        """

        failure = _CONVERSATION_FAILURES.get(exc.code, InternalApplicationError)
        return failure().to_public_error()

    def _conversation_message(
        session_id: str, body: ConversationMessageBody | ConversationEditBody
    ) -> ConversationMessage:
        """Return the canonical message of one conversational turn body.

        The session identity is the path identity and the message identity is
        the body identity; ``bot_id`` is carried as the opaque association of
        the contract and never as authority.  No lineage and no metadata are
        invented here: the canonical service owns lineage and the canonical
        session owns the committed transcript.
        """

        return ConversationMessage(
            id=body.message_id,
            session_id=session_id,
            role=ConversationRole.USER,
            content=body.content,
            created_at=body.created_at,
            bot_id=body.bot_id,
            references=tuple(body.references),
            attachments=tuple(
                ConversationAttachmentRef(
                    ref=attachment.ref,
                    kind=attachment.kind,
                    name=attachment.name,
                    media_type=attachment.media_type,
                )
                for attachment in body.attachments
            ),
        )

    def _conversation_envelope(
        request_id: str, payload: dict[str, Any]
    ) -> ApplicationResponseModel:
        """Return the one public envelope carrying a conversational payload.

        The payload is the canonical conversational contract's serialization;
        the envelope is the frozen public response shape of the ``/v1``
        surface, so a client keeps one response shape and never sees an ad-hoc
        one.
        """

        return ApplicationResponseModel(
            request_id=request_id,
            api_version=APPLICATION_API_VERSION,
            status=ApplicationStatus.SUCCESS,
            data=payload,
        )

    def _conversation_answer(
        raw_request: Request,
        raw_response: Response,
        call: Callable[
            [ConversationService, str], tuple[ApplicationResponseModel, int]
        ],
    ) -> ApplicationResponseModel | JSONResponse:
        """Delegate one conversation route to the canonical service.

        The handler parses, delegates, serializes and maps safe errors only.  A
        raised conversational boundary failure becomes the application layer's
        own typed failure (never a copy), a rejected public conversational value
        becomes an invalid request, and anything unexpected fails closed as the
        generic internal failure — so no internal text, path or traceback can
        escape.  Without the service every conversation route reports the frozen
        capability-unavailable failure rather than crashing.
        """

        request_id, defect = _correlation_identity(raw_request)
        if defect is not None:
            return _error_response(request_id, defect)
        if conversation is None:
            return _error_response(
                request_id, CapabilityUnavailableError().to_public_error()
            )
        try:
            envelope, status_code = call(conversation, request_id)
        except ConversationBoundaryError as exc:
            return _error_response(request_id, _conversation_error(exc))
        except (TypeError, ValueError):
            # The public conversational contract rejected values built from
            # caller input, so the request is invalid rather than internally
            # broken.
            return _error_response(
                request_id, invalid_request_error(REASON_INVALID_REQUEST_CONTRACT)
            )
        except Exception as exc:  # noqa: BLE001 - the adapter boundary fails closed
            return _error_response(request_id, safe_error_from_exception(exc))
        raw_response.status_code = status_code
        raw_response.headers[REQUEST_ID_HEADER] = envelope.request_id
        return envelope

    @app.get(
        "/v1/conversations/{session_id}",
        response_model=ApplicationResponseModel,
        summary="Read one canonical conversation",
    )
    def get_conversation(
        session_id: _PathIdentifier,
        raw_request: Request,
        raw_response: Response,
    ) -> ApplicationResponseModel | JSONResponse:
        """Read the canonical conversation state through the service only."""

        def call(
            service: ConversationService, request_id: str
        ) -> tuple[ApplicationResponseModel, int]:
            state = service.load(session_id)
            if state is None:
                raise ConversationSessionNotFoundError()
            return (
                _conversation_envelope(
                    request_id,
                    conversation_state_model_from(state).model_dump(mode="json"),
                ),
                _CONVERSATION_SUCCESS_STATUS,
            )

        return _conversation_answer(raw_request, raw_response, call)

    @app.post(
        "/v1/conversations/{session_id}/messages",
        response_model=ApplicationResponseModel,
        summary="Submit one conversational user turn",
    )
    def submit_conversation_message(
        session_id: _PathIdentifier,
        body: ConversationMessageBody,
        raw_request: Request,
        raw_response: Response,
    ) -> ApplicationResponseModel | JSONResponse:
        """Submit one user turn built from the caller's explicit input only."""

        def call(
            service: ConversationService, request_id: str
        ) -> tuple[ApplicationResponseModel, int]:
            response = service.submit(
                _conversation_message(session_id, body),
                request_id=body.request_id,
                expected_session_revision=body.expected_session_revision,
                requested_capabilities=tuple(body.requested_capabilities),
                assistant_message_id=body.assistant_message_id,
                assistant_created_at=body.assistant_created_at,
            )
            return (
                _conversation_envelope(
                    request_id,
                    assistant_response_model_from(response).model_dump(mode="json"),
                ),
                _CONVERSATION_SUCCESS_STATUS,
            )

        return _conversation_answer(raw_request, raw_response, call)

    @app.post(
        "/v1/conversations/{session_id}/messages/{message_id}/edit",
        response_model=ApplicationResponseModel,
        summary="Edit one conversational user message",
    )
    def edit_conversation_message(
        session_id: _PathIdentifier,
        message_id: _PathIdentifier,
        body: ConversationEditBody,
        raw_request: Request,
        raw_response: Response,
    ) -> ApplicationResponseModel | JSONResponse:
        """Edit through a lineage-bound replacement; the original is the path identity."""

        def call(
            service: ConversationService, request_id: str
        ) -> tuple[ApplicationResponseModel, int]:
            response = service.edit(
                original_message_id=message_id,
                replacement=_conversation_message(session_id, body),
                request_id=body.request_id,
                expected_session_revision=body.expected_session_revision,
                requested_capabilities=tuple(body.requested_capabilities),
                assistant_message_id=body.assistant_message_id,
                assistant_created_at=body.assistant_created_at,
            )
            return (
                _conversation_envelope(
                    request_id,
                    assistant_response_model_from(response).model_dump(mode="json"),
                ),
                _CONVERSATION_SUCCESS_STATUS,
            )

        return _conversation_answer(raw_request, raw_response, call)

    @app.post(
        "/v1/conversations/{session_id}/responses/{message_id}/regenerate",
        response_model=ApplicationResponseModel,
        summary="Regenerate one conversational assistant response",
    )
    def regenerate_conversation_response(
        session_id: _PathIdentifier,
        message_id: _PathIdentifier,
        body: ConversationRegenerateBody,
        raw_request: Request,
        raw_response: Response,
    ) -> ApplicationResponseModel | JSONResponse:
        """Regenerate the target response through the canonical pipeline again."""

        def call(
            service: ConversationService, request_id: str
        ) -> tuple[ApplicationResponseModel, int]:
            response = service.regenerate(
                session_id=session_id,
                response_message_id=message_id,
                request_id=body.request_id,
                application_message_id=body.application_message_id,
                expected_session_revision=body.expected_session_revision,
                assistant_message_id=body.assistant_message_id,
                assistant_created_at=body.assistant_created_at,
            )
            return (
                _conversation_envelope(
                    request_id,
                    assistant_response_model_from(response).model_dump(mode="json"),
                ),
                _CONVERSATION_SUCCESS_STATUS,
            )

        return _conversation_answer(raw_request, raw_response, call)

    @app.post(
        "/v1/conversations/requests/{request_id}/cancel",
        response_model=ApplicationResponseModel,
        summary="Request cancellation of a conversational request",
    )
    def cancel_conversation_request(
        request_id: _PathIdentifier,
        raw_request: Request,
        raw_response: Response,
    ) -> ApplicationResponseModel | JSONResponse:
        """Delegate the request-scoped cancellation to the canonical service."""

        def call(
            service: ConversationService, correlation_id: str
        ) -> tuple[ApplicationResponseModel, int]:
            application_response = service.cancel(
                request_id=correlation_id, target_request_id=request_id
            )
            return (
                response_model_from(application_response),
                http_status_for(
                    application_response,
                    operation=ApplicationOperation.REQUEST_CANCEL,
                ),
            )

        return _conversation_answer(raw_request, raw_response, call)

    return app
