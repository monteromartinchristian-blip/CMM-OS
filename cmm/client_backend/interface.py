"""Phase 11.50 — the reusable first-party client backend facade.

``ClientBackend`` is the one stable, versioned seam a first-party client (for
example CMMChat) consumes.  It is a **facade and capability projection only**:
it validates its own client-interface contract, delegates to the exact canonical
Phase 11.3 ``ApplicationGateway`` and Phase 11.5 ``ConversationService``, and
projects safe, stable client-facing results.  It owns no authority whatsoever —
no session, no conversation state, no transcript, no routing, no model
selection, no model execution, no provider dispatch, no store, no registry, no
runtime and no event bus.

The canonical dependency direction is one way only:

```text
first-party client
      ↓
cmm.client_backend
      ↓
ConversationService
      ↓
ApplicationGateway
      ↓
Orchestrator / existing canonical owners
```

Five properties are frozen here:

* **exact owner identity** — construction requires the *exact* canonical
  ``ApplicationGateway`` and ``ConversationService`` types (a duck-typed
  replacement and, since Remediation V1, a subclass of either owner both fail
  closed), and the facade additionally verifies through the narrowed,
  non-authoritative ``ConversationService.uses_application_gateway`` evidence
  that the supplied conversational service is wired to the *same* gateway
  instance.  A facade holding one gateway while the conversational service
  writes through another would be a silently split application boundary, so it
  is rejected rather than tolerated;
* **no live-owner access** — the public surface never returns a live
  authority-bearing canonical owner.  Remediation V1 removed the additive
  ``gateway``/``conversation`` accessors after Independent Audit V1 reproduced
  that ``client.gateway.handle(...)`` reached ``health.get``, a canonical
  application operation outside the frozen :class:`ClientOperation` set; there
  is no renamed equivalent and no generic service locator either;
* **delegation only** — every operation maps to one existing canonical call.
  ``create_session``/``get_session`` enter the one public
  ``ApplicationGateway.handle`` entrypoint with a canonical
  ``SESSION_CREATE``/``SESSION_GET`` request — the official Phase 11.3 session
  boundary, reached through the official gateway rather than by duplicating it —
  and ``load_conversation``, ``submit_message``, ``edit_message``,
  ``regenerate_response`` and ``cancel_request`` reuse the exact Phase 11.5
  ``ConversationService`` methods and return their canonical values unchanged.
  There is no orchestration code, no lineage reimplementation and no retry here;
* **fail-closed interface validation** — an unsupported interface version or an
  unknown operation fails closed *before* any owner is reached, and there is no
  dynamic routing, no service name, no import path and no callable anywhere in
  the surface;
* **safe error projection** — a client-interface-shape failure raises the
  layer's own closed :class:`~cmm.client_backend.contracts.ClientBackendError`;
  every canonical failure keeps its canonical safe code and message and is
  reported exactly as the canonical layers report it (the canonical
  ``ApplicationError`` or ``ConversationErrorCode``), never copied raw and never
  re-coded as a client error.  The generic dispatch entrypoint, whose caller has
  no canonical typed contract to match, maps an unexpected internal failure to
  ``INTERNAL_CLIENT_ERROR`` with no raw internal message.

Model-boundary capability facts are supplied as read-only canonical declarations
by the composition root; the Model Gateway itself is never imported, resolved or
executed from this package.

See ``docs/superpowers/specs/2026-09-25-phase-11.50-reusable-backend-interfaces-design.md``
(sections 8 to 17 and 24 to 28) and
``docs/reference/phase-11-reusable-backend-interfaces.md``.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from cmm.application.contracts import (
    APPLICATION_API_VERSION,
    ApplicationCapability,
    ApplicationChannel,
    ApplicationCommand,
    ApplicationError,
    ApplicationErrorCode,
    ApplicationOperation,
    ApplicationQuery,
    ApplicationResponse,
    ApplicationSession,
    ApplicationStatus,
)
from cmm.application.errors import ApplicationServiceError
from cmm.application.gateway import ApplicationGateway
from cmm.client_backend.capabilities import (
    ClientBackendCapabilities,
    ClientBackendCapabilityEvidence,
    build_client_backend_capabilities,
)
from cmm.client_backend.contracts import (
    CLIENT_BACKEND_INTERFACE_VERSION,
    ClientBackendError,
    ClientBackendErrorCode,
    ClientBackendRequest,
    ClientBackendResult,
    ClientOperation,
    require_supported_interface_version,
)
from cmm.conversation.contracts import (
    AssistantResponse,
    ConversationMessage,
)
from cmm.conversation.errors import (
    CONVERSATION_ERROR_MESSAGES,
    ConversationBoundaryError,
    ConversationErrorCode,
)
from cmm.conversation.service import ConversationService
from cmm.conversation.state import ConversationState

__all__ = ["ClientBackend"]


class ClientBackend:
    """The one reusable, non-authoritative first-party client backend facade."""

    #: Private validation metadata: the canonical ``client.backend`` composition
    #: identity is the exact concrete facade type.  The Phase 11.1 registry reads
    #: this marker off the runtime contract and treats exact matching as a
    #: *minimum* semantic, so no hand-built ``ServiceBinding`` can downgrade it
    #: back to ``isinstance``.  It is not a public API, grants no authority and
    #: creates no import edge into ``cmm.platform``.
    __cmm_exact_runtime_contract__ = True

    def __init__(
        self,
        *,
        gateway: ApplicationGateway,
        conversation: ConversationService,
        application_capabilities: tuple[ApplicationCapability, ...] = (),
        model_boundary_capabilities: tuple[ApplicationCapability, ...] = (),
        application_api_version: str = APPLICATION_API_VERSION,
    ) -> None:
        if type(gateway) is not ApplicationGateway:
            raise TypeError(
                "gateway must be the exact canonical Phase 11.3 "
                f"ApplicationGateway, not {type(gateway).__name__}"
            )
        if type(conversation) is not ConversationService:
            raise TypeError(
                "conversation must be the exact canonical Phase 11.5 "
                f"ConversationService, not {type(conversation).__name__}"
            )
        if not isinstance(application_capabilities, tuple):
            raise TypeError(
                "application_capabilities must be an immutable tuple of "
                "ApplicationCapability values"
            )
        if not isinstance(model_boundary_capabilities, tuple):
            raise TypeError(
                "model_boundary_capabilities must be an immutable tuple of "
                "ApplicationCapability values"
            )

        # Owner coherence: the conversational service must write through the very
        # gateway this facade was handed.  Two different gateways would be a
        # silently split application boundary, which the design forbids.  The
        # question is asked through the narrowed, non-authoritative identity seam
        # so no live owner is ever returned to this layer.
        if not conversation.uses_application_gateway(gateway):
            raise ValueError(
                "the composed ConversationService must use the exact "
                "ApplicationGateway supplied to the client backend"
            )

        self._gateway = gateway
        self._conversation = conversation
        # Immutable read-only evidence: the canonical declarations the composition
        # root supplied, never a callable, a service, a registry or a live runtime.
        self._evidence = ClientBackendCapabilityEvidence(
            application_capabilities=tuple(application_capabilities),
            model_boundary_capabilities=tuple(model_boundary_capabilities),
            application_api_version=application_api_version,
        )

    @classmethod
    def from_capability_declarations(
        cls,
        *,
        gateway: ApplicationGateway,
        conversation: ConversationService,
        capability_declarations: tuple[ApplicationCapability, ...],
        model_boundary_capabilities: tuple[ApplicationCapability, ...] = (),
    ) -> ClientBackend:
        """Build the facade from the canonical capability declarations.

        A composition root that has already obtained the Phase 11.3 public
        capability declarations — and, where it has inspected it, the Phase 11.21
        model-boundary evidence — uses this factory so the facade reports
        canonical capability truth instead of reporting every row unavailable.
        The declarations are copied; nothing is executed and no owner is created.
        """

        return cls(
            gateway=gateway,
            conversation=conversation,
            application_capabilities=capability_declarations,
            model_boundary_capabilities=model_boundary_capabilities,
        )

    # ── Capability truth ─────────────────────────────────────────────────────

    def capabilities(self) -> ClientBackendCapabilities:
        """Return the one immutable capability projection of this facade."""

        return build_client_backend_capabilities(
            evidence=self._evidence,
            conversation_resolver=self._conversation.capability_resolver,
        )

    # ── Session operations (canonical Phase 11.3 session boundary) ───────────

    def create_session(self, session_id: str) -> ApplicationSession:
        """Create one canonical session through the one public gateway entrypoint.

        The client layer owns no session persistence and duplicates no session
        service: it builds the canonical ``SESSION_CREATE`` command, enters the
        one ``ApplicationGateway.handle`` boundary and returns the canonical
        ``ApplicationSession`` projection unchanged.
        """

        target = _require_session_id(session_id)
        return self._session(
            ApplicationOperation.SESSION_CREATE,
            session_id=target,
            payload={"session_id": target},
        )

    def get_session(self, session_id: str) -> ApplicationSession:
        """Return one canonical session through the one public gateway entrypoint."""

        target = _require_session_id(session_id)
        return self._session(
            ApplicationOperation.SESSION_GET,
            session_id=target,
            payload={},
        )

    def _session(
        self,
        operation: ApplicationOperation,
        *,
        payload: Mapping[str, Any],
        session_id: str,
    ) -> ApplicationSession:
        """Enter the canonical gateway once and project one safe session value."""

        request_id = f"client-backend:{operation.value}:{session_id}"
        if operation is ApplicationOperation.SESSION_GET:
            request = ApplicationQuery(
                api_version=APPLICATION_API_VERSION,
                request_id=request_id,
                operation=operation,
                session_id=session_id,
                payload=payload,
                channel=ApplicationChannel.CONVERSATION,
            )
        else:
            request = ApplicationCommand(
                api_version=APPLICATION_API_VERSION,
                request_id=request_id,
                operation=operation,
                payload=payload,
                channel=ApplicationChannel.CONVERSATION,
            )

        response = self._gateway.handle(request)
        return _application_session_from_response(response)

    # ── Conversation read (canonical Phase 11.5 read accessor) ───────────────

    def load_conversation(self, session_id: str) -> ConversationState | None:
        """Return the canonical conversation state of one session, or ``None``."""

        return self._conversation.load(session_id)

    # ── Conversation operations (exact canonical ConversationService) ────────

    def submit_message(
        self,
        message: ConversationMessage,
        *,
        request_id: str,
        expected_session_revision: int,
        assistant_message_id: str,
        assistant_created_at: str,
        requested_capabilities: tuple[str, ...] = (),
    ) -> AssistantResponse:
        """Submit one conversational turn through the canonical service."""

        return self._conversation.submit(
            message,
            request_id=request_id,
            expected_session_revision=expected_session_revision,
            requested_capabilities=requested_capabilities,
            assistant_message_id=assistant_message_id,
            assistant_created_at=assistant_created_at,
        )

    def edit_message(
        self,
        *,
        original_message_id: str,
        replacement: ConversationMessage,
        request_id: str,
        expected_session_revision: int,
        assistant_message_id: str,
        assistant_created_at: str,
        requested_capabilities: tuple[str, ...] = (),
    ) -> AssistantResponse:
        """Edit one user message through the canonical service.

        Lineage stays service-owned: the canonical ``ConversationService`` binds
        the replacement lineage itself and this layer never reimplements or
        overrides it.
        """

        return self._conversation.edit(
            original_message_id=original_message_id,
            replacement=replacement,
            request_id=request_id,
            expected_session_revision=expected_session_revision,
            requested_capabilities=requested_capabilities,
            assistant_message_id=assistant_message_id,
            assistant_created_at=assistant_created_at,
        )

    def regenerate_response(
        self,
        *,
        session_id: str,
        response_message_id: str,
        request_id: str,
        application_message_id: str,
        expected_session_revision: int,
        assistant_message_id: str,
        assistant_created_at: str,
    ) -> AssistantResponse:
        """Regenerate one assistant response through the canonical service."""

        return self._conversation.regenerate(
            session_id=session_id,
            response_message_id=response_message_id,
            request_id=request_id,
            application_message_id=application_message_id,
            expected_session_revision=expected_session_revision,
            assistant_message_id=assistant_message_id,
            assistant_created_at=assistant_created_at,
        )

    def cancel_request(
        self, *, request_id: str, target_request_id: str
    ) -> ApplicationResponse:
        """Delegate one cancellation request to the canonical boundary.

        Cancellation availability is *not* inferred from the Phase 11.21 Model
        Gateway: the canonical response is returned unchanged, and at this
        baseline it reports ``CAPABILITY_UNAVAILABLE`` because no canonical
        cancellable-request owner exists.
        """

        return self._conversation.cancel(
            request_id=request_id, target_request_id=target_request_id
        )

    # ── Generic client entrypoint ────────────────────────────────────────────

    def dispatch(self, request: ClientBackendRequest) -> ClientBackendResult:
        """Execute one client request envelope, or fail closed safely.

        The interface version and the operation are validated before any
        canonical owner is reached, so an unsupported version or an unknown
        operation performs zero downstream calls.  A canonical failure keeps its
        canonical safe state on the real execution path: a canonical
        ``ApplicationError`` is projected through the canonical safe projection,
        a canonical conversational boundary failure keeps its closed code, and
        only a genuinely unknown internal failure becomes
        ``INTERNAL_CLIENT_ERROR`` with no raw internal message (Audit V1
        MAJOR-03).
        """

        if not isinstance(request, ClientBackendRequest):
            raise TypeError(
                f"request must be a ClientBackendRequest, not {type(request).__name__}"
            )

        try:
            require_supported_interface_version(request.interface_version)
            self._require_supported_operation(request.operation)
            data = self._execute(request)
        except ClientBackendError as error:
            return ClientBackendResult(
                interface_version=CLIENT_BACKEND_INTERFACE_VERSION,
                request_id=request.request_id,
                operation=request.operation,
                ok=False,
                data=None,
                error=error,
            )
        except (ApplicationServiceError, ConversationBoundaryError) as error:
            return ClientBackendResult(
                interface_version=CLIENT_BACKEND_INTERFACE_VERSION,
                request_id=request.request_id,
                operation=request.operation,
                ok=False,
                data=None,
                error=_canonical_client_failure(error),
            )
        except Exception:  # noqa: BLE001 - the client boundary fails closed
            return ClientBackendResult(
                interface_version=CLIENT_BACKEND_INTERFACE_VERSION,
                request_id=request.request_id,
                operation=request.operation,
                ok=False,
                data=None,
                error=ClientBackendError(ClientBackendErrorCode.INTERNAL_CLIENT_ERROR),
            )

        return ClientBackendResult(
            interface_version=CLIENT_BACKEND_INTERFACE_VERSION,
            request_id=request.request_id,
            operation=request.operation,
            ok=True,
            data=data,
            error=None,
        )

    # ── Dispatch internals ───────────────────────────────────────────────────

    @staticmethod
    def _require_supported_operation(operation: object) -> ClientOperation:
        """Fail closed unless *operation* is a member of the closed set.

        An operation is never routed by string: a value that is not a real
        ``ClientOperation`` member is an invalid client operation and never
        reaches a canonical owner.
        """

        if not isinstance(operation, ClientOperation):
            raise ClientBackendError(ClientBackendErrorCode.INVALID_CLIENT_OPERATION)
        return operation

    def _execute(self, request: ClientBackendRequest) -> Mapping[str, Any] | None:
        """Execute one validated operation through its canonical owner."""

        operation = request.operation
        payload = request.payload

        if operation is ClientOperation.CAPABILITIES:
            return {"capabilities": self.capabilities().to_dict()}

        if operation is ClientOperation.CREATE_SESSION:
            session = self.create_session(_required_identifier(payload, "session_id"))
            return {"session": session.to_dict()}

        if operation is ClientOperation.GET_SESSION:
            session = self.get_session(_required_identifier(payload, "session_id"))
            return {"session": session.to_dict()}

        if operation is ClientOperation.LOAD_CONVERSATION:
            state = self.load_conversation(_required_identifier(payload, "session_id"))
            return {
                "conversation": None if state is None else state.to_dict(),
            }

        if operation is ClientOperation.SUBMIT_MESSAGE:
            response = self.submit_message(
                _required_message(payload, "message"),
                request_id=_required_identifier(payload, "message_request_id"),
                expected_session_revision=_required_revision(payload),
                assistant_message_id=_required_identifier(
                    payload, "assistant_message_id"
                ),
                assistant_created_at=_required_identifier(
                    payload, "assistant_created_at"
                ),
            )
            return {"response": response.to_dict()}

        if operation is ClientOperation.EDIT_MESSAGE:
            response = self.edit_message(
                original_message_id=_required_identifier(
                    payload, "original_message_id"
                ),
                replacement=_required_message(payload, "message"),
                request_id=_required_identifier(payload, "message_request_id"),
                expected_session_revision=_required_revision(payload),
                assistant_message_id=_required_identifier(
                    payload, "assistant_message_id"
                ),
                assistant_created_at=_required_identifier(
                    payload, "assistant_created_at"
                ),
            )
            return {"response": response.to_dict()}

        if operation is ClientOperation.REGENERATE_RESPONSE:
            response = self.regenerate_response(
                session_id=_required_identifier(payload, "session_id"),
                response_message_id=_required_identifier(
                    payload, "response_message_id"
                ),
                request_id=_required_identifier(payload, "message_request_id"),
                application_message_id=_required_identifier(
                    payload, "application_message_id"
                ),
                expected_session_revision=_required_revision(payload),
                assistant_message_id=_required_identifier(
                    payload, "assistant_message_id"
                ),
                assistant_created_at=_required_identifier(
                    payload, "assistant_created_at"
                ),
            )
            return {"response": response.to_dict()}

        if operation is ClientOperation.CANCEL_REQUEST:
            application_response = self.cancel_request(
                request_id=_required_identifier(payload, "request_id"),
                target_request_id=_required_identifier(payload, "target_request_id"),
            )
            return {"application_response": application_response.to_dict()}

        # Unreachable while the operation enum is closed and validated above; a
        # future operation therefore fails closed instead of being dispatched.
        raise ClientBackendError(ClientBackendErrorCode.INVALID_CLIENT_OPERATION)

    # ── Canonical failure projection ─────────────────────────────────────────

    @staticmethod
    def project_canonical_failure(error: BaseException) -> dict[str, str]:
        """Project one canonical failure into its own safe public shape.

        A canonical typed application failure keeps its canonical code and
        message; a canonical conversational boundary failure keeps its canonical
        code.  Anything else is an internal defect and becomes the one generic
        client error with no raw internal message.  This helper exists so a
        first-party client can render a canonical failure safely without
        importing either canonical error hierarchy itself.
        """

        return _canonical_client_failure(error).to_dict()


def _canonical_client_failure(error: BaseException) -> ClientBackendError:
    """Return the safe client failure of one canonical downstream failure.

    A known canonical application or conversational failure keeps its own
    canonical safe code and safe message verbatim, so a first-party client sees
    the same ``RESOURCE_NOT_FOUND`` / ``CONFLICT`` / ``SESSION_CONFLICT`` /
    ``POLICY_DENIED`` identity the canonical layers report instead of a lossy
    re-code (Audit V1 MAJOR-03).

    A canonical *internal* failure is deliberately not preserved: it is an
    internal defect rather than a known caller-facing outcome, so it becomes the
    one generic client error.  Anything that is not a canonical typed failure at
    all is an unknown internal exception and becomes the same generic error.
    """

    if isinstance(error, ApplicationServiceError):
        return _application_error_client_failure(error.to_public_error())
    if isinstance(error, ConversationBoundaryError):
        code = error.code
        if code is ConversationErrorCode.INTERNAL_FAILURE:
            return ClientBackendError(ClientBackendErrorCode.INTERNAL_CLIENT_ERROR)
        return ClientBackendError.from_canonical(
            code=code.value, message=CONVERSATION_ERROR_MESSAGES[code]
        )
    return ClientBackendError(ClientBackendErrorCode.INTERNAL_CLIENT_ERROR)


def _application_error_client_failure(error: ApplicationError) -> ClientBackendError:
    """Return the safe client failure of one canonical public application error."""

    if error.code is ApplicationErrorCode.INTERNAL_FAILURE:
        return ClientBackendError(ClientBackendErrorCode.INTERNAL_CLIENT_ERROR)
    return ClientBackendError.from_canonical(
        code=error.code.value, message=error.message
    )


def _application_session_from_response(
    response: ApplicationResponse,
) -> ApplicationSession:
    """Project one canonical session response into its public session value.

    The projection is exact and lossless for the frozen public session fields: a
    canonical success carries the canonical session document, and every other
    outcome is reported as a failure with the canonical safe error code and
    message.  No canonical identity, revision or timestamp is rewritten.
    """

    if response.status is not ApplicationStatus.SUCCESS or response.data is None:
        error = response.error
        if error is None:
            raise ClientBackendError(ClientBackendErrorCode.INTERNAL_CLIENT_ERROR)
        # A real canonical failure keeps its canonical safe code and message: a
        # missing session is ``RESOURCE_NOT_FOUND``, a duplicate create is
        # ``CONFLICT``, and neither is recoded as a client-interface failure
        # (Audit V1 MAJOR-03).
        raise _application_error_client_failure(error)

    session = response.data.get("session_id")
    revision = response.data.get("revision")
    status = response.data.get("status")
    created_at = response.data.get("created_at")
    updated_at = response.data.get("updated_at")
    if (
        not isinstance(session, str)
        or not isinstance(status, str)
        or not isinstance(created_at, str)
        or not isinstance(updated_at, str)
        or isinstance(revision, bool)
        or not isinstance(revision, int)
    ):
        raise ClientBackendError(ClientBackendErrorCode.INTERNAL_CLIENT_ERROR)

    return ApplicationSession(
        session_id=session,
        revision=revision,
        status=status,
        created_at=created_at,
        updated_at=updated_at,
    )


def _require_session_id(session_id: object) -> str:
    """Return one non-empty session identifier, or fail closed as an invalid contract.

    The identifier is validated before any owner is reached, so a blank or
    non-textual value can never enter the canonical pipeline or be echoed back in
    a generated request identity.
    """

    if not isinstance(session_id, str) or not session_id.strip():
        raise ClientBackendError(ClientBackendErrorCode.INVALID_CLIENT_CONTRACT)
    return session_id


def _required_identifier(payload: Mapping[str, Any], field_name: str) -> str:
    """Return one required non-empty string payload field, or fail closed."""

    value = payload.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise ClientBackendError(ClientBackendErrorCode.INVALID_CLIENT_CONTRACT)
    return value


def _required_revision(payload: Mapping[str, Any]) -> int:
    """Return the required optimistic-concurrency revision, or fail closed."""

    value = payload.get("expected_session_revision")
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ClientBackendError(ClientBackendErrorCode.INVALID_CLIENT_CONTRACT)
    return value


def _required_message(
    payload: Mapping[str, Any], field_name: str
) -> ConversationMessage:
    """Return one required canonical conversational message, or fail closed."""

    value = payload.get(field_name)
    if not isinstance(value, ConversationMessage):
        raise ClientBackendError(ClientBackendErrorCode.INVALID_CLIENT_CONTRACT)
    return value
