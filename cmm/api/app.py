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

See ``docs/reference/phase-11-application-backend.md``.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID, uuid4, uuid5

from fastapi import FastAPI, Path, Request, Response
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as FrameworkHTTPException
from starlette.responses import JSONResponse

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
    CreateSessionBody,
    MessageBody,
    response_model_from,
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
    ApplicationResponse,
    failed_response,
    safe_error_from_exception,
)

__all__ = ["create_app"]

#: Public request correlation header; generated when absent and always echoed.
REQUEST_ID_HEADER = "X-Request-ID"

#: Public idempotency header; only the commands that opt into replay read it.
IDEMPOTENCY_KEY_HEADER = "Idempotency-Key"

#: A public identifier as it appears in a request path.
_PathIdentifier = Annotated[str, Path(min_length=1, max_length=MAX_IDENTIFIER_LENGTH)]

#: Namespace of the generated message identity of a keyed command.  Deriving it
#: from the caller's idempotency key keeps a retry of the same keyed command
#: canonically identical, which is what makes the replay possible.
_MESSAGE_ID_NAMESPACE = UUID("9138a986-0034-48fe-8647-86a564918bb9")


def create_app(gateway: ApplicationGateway) -> FastAPI:
    """Build the v1 HTTP adapter over one composed application gateway."""

    if not isinstance(gateway, ApplicationGateway):
        raise TypeError(
            "gateway must be the canonical ApplicationGateway, "
            f"not {type(gateway).__name__}"
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

    return app
