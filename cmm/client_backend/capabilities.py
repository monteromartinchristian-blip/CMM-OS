"""Phase 11.50 — honest capability truth for first-party clients.

The reusable client backend reports what CMM OS can actually do for a
first-party client, and nothing more.  Every row of the manifest is derived from
*canonical evidence*:

* ``ApplicationCapability`` declarations of the Phase 11.3 gateway for the
  application-level facts (the public API version, response-event streaming and
  any explicitly declared cancellable owner);
* ``ConversationCapabilityState`` resolutions of the Phase 11.5
  ``ConversationCapabilityResolver`` for the conversational and end-to-end facts;
* explicitly injected ``ApplicationCapability`` declarations with the frozen
  Phase 11.50 *model-boundary* capability IDs for the Phase 11.21 model-boundary
  facts.  The Model Gateway is never resolved, imported or executed here: the
  declarations are read-only evidence supplied by the composition root.

Nothing is inspected by model name, provider name or vendor capability list.
Nothing is optimistically upgraded.  Two distinctions are load-bearing and are
preserved exactly:

* **boundary truth is not end-to-end truth.**  A Phase 11.21 capability at the
  model boundary is reported as :attr:`ClientBackendCapabilityStatus.BOUNDARY_ONLY`,
  which by its name states that it is available *at the model boundary* and not
  reachable end to end.  The matching ``end_to_end_*`` row reports the actual
  conversational truth until a later phase proves a connected path;
* **a response-event stream is not a token stream.**  ``response_event_stream``
  describes the existing public response-event delivery of the Phase 11.3
  application boundary and is projected from the canonical *application*
  ``streaming`` declaration.  It is never derived from the conversational
  ``response_streaming`` row — whose degraded status describes provider token
  streaming — and it is never relabelled as token streaming (Audit V1 MAJOR-04).

Attachment references stay ``reference_only`` and document upload stays
``UNAVAILABLE``: Phase 11.50 creates no file store, no upload and no path or URL
resolver.  Because the canonical conversational row is ``AVAILABLE`` only in the
``reference_only`` effective mode, the client-visible attachment status is
``DEGRADED`` and the canonical effective mode is preserved verbatim in
``attachment_effective_mode`` (Audit V1 MAJOR-04).

See ``docs/superpowers/specs/2026-09-25-phase-11.50-reusable-backend-interfaces-design.md``
(sections 18 to 23) and ``docs/reference/phase-11-reusable-backend-interfaces.md``.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Any

from cmm.application.contracts import (
    APPLICATION_API_VERSION,
    ApplicationCapability,
    CapabilityStatus,
)
from cmm.client_backend.contracts import (
    CLIENT_BACKEND_INTERFACE_VERSION,
    CLIENT_BACKEND_MAX_IDENTIFIER_LENGTH,
)
from cmm.conversation.capabilities import ConversationCapabilityResolver
from cmm.conversation.contracts import (
    ConversationCapabilityState,
    ConversationCapabilityStatus,
)

__all__ = [
    "CLIENT_BACKEND_MODEL_BOUNDARY_CAPABILITY_IDS",
    "MODEL_BOUNDARY_MULTIMODAL_CAPABILITY_ID",
    "MODEL_BOUNDARY_REASONING_CAPABILITY_ID",
    "MODEL_BOUNDARY_TOKEN_STREAM_CAPABILITY_ID",
    "REASON_MODEL_BOUNDARY_CAPABILITY_NOT_DECLARED",
    "REASON_MODEL_BOUNDARY_ONLY_NOT_END_TO_END",
    "REASON_NO_APPLICATION_DECLARATION",
    "REASON_NO_CONVERSATION_OWNER",
    "REFERENCE_ONLY_ATTACHMENT_MODE",
    "ClientBackendCapabilities",
    "ClientBackendCapabilityEvidence",
    "ClientBackendCapabilityStatus",
    "build_client_backend_capabilities",
]

#: The frozen Phase 11.50 model-boundary capability IDs.  A composition root that
#: has already inspected the canonical Phase 11.21 boundary may declare these on
#: the read-only evidence seam; they are never derived from a provider or model
#: name and they grant the client no execution authority.
MODEL_BOUNDARY_REASONING_CAPABILITY_ID = "model-boundary-reasoning"
MODEL_BOUNDARY_MULTIMODAL_CAPABILITY_ID = "model-boundary-multimodal"
MODEL_BOUNDARY_TOKEN_STREAM_CAPABILITY_ID = "model-boundary-token-stream"

#: The complete closed set of injected model-boundary declaration IDs.
CLIENT_BACKEND_MODEL_BOUNDARY_CAPABILITY_IDS = (
    MODEL_BOUNDARY_REASONING_CAPABILITY_ID,
    MODEL_BOUNDARY_MULTIMODAL_CAPABILITY_ID,
    MODEL_BOUNDARY_TOKEN_STREAM_CAPABILITY_ID,
)

#: The reason of a model-boundary row with no canonical declaration.
REASON_MODEL_BOUNDARY_CAPABILITY_NOT_DECLARED = "MODEL_BOUNDARY_CAPABILITY_NOT_DECLARED"

#: The reason of an end-to-end row whose model boundary is proven but whose
#: end-to-end path is deliberately not proven in Phase 11.50.
REASON_MODEL_BOUNDARY_ONLY_NOT_END_TO_END = "MODEL_BOUNDARY_ONLY_NOT_END_TO_END"

#: The reason of an application-level row whose canonical Phase 11.3 declaration
#: was not supplied to this projection.
REASON_NO_APPLICATION_DECLARATION = "NO_CANONICAL_APPLICATION_DECLARATION"

#: The reason reported for every conversational row while no canonical
#: conversational owner is composed.
REASON_NO_CONVERSATION_OWNER = "NO_CONVERSATION_OWNER"

#: The canonical effective mode of the Phase 11.5 attachment capability: the
#: conversational boundary keeps attachment *references* only.  Phase 11.50 adds
#: no upload, no file store and no path or URL resolver, so the client-visible
#: status of that row is ``DEGRADED`` and this qualifier must stay visible
#: (Audit V1 MAJOR-04).  The value is the canonical one, never invented here.
REFERENCE_ONLY_ATTACHMENT_MODE = "reference_only"

#: The canonical Phase 11.3 application capability ID of the public
#: response-event delivery (the SSE surface).  It is a *different* fact from
#: provider token streaming, which is why the dedicated ``response_event_stream``
#: row is projected from it and never from the conversational
#: ``response_streaming`` row (Audit V1 MAJOR-04).
_APPLICATION_RESPONSE_EVENT_STREAM_CAPABILITY_ID = "streaming"

#: The canonical Phase 11.5 conversational capability IDs read by this
#: projection: the token-stream (and response-event) row, the attachment
#: references and the document upload.
_CONVERSATION_RESPONSE_STREAMING_CAPABILITY_ID = "response_streaming"
_CONVERSATION_ATTACHMENTS_CAPABILITY_ID = "attachments"


class ClientBackendCapabilityStatus(str, Enum):
    """Closed status vocabulary of the client capability manifest.

    Four states are needed because two-state booleans cannot express the truth
    this layer must report:

    ``AVAILABLE``
        a real, end-to-end reachable capability of this client surface;
    ``DEGRADED``
        reachable in a reduced form that the canonical owner reports honestly;
    ``UNAVAILABLE``
        not reachable at this baseline;
    ``BOUNDARY_ONLY``
        proven available at the canonical *model* boundary and deliberately not
        proven end to end from a first-party client.  It is never an end-to-end
        availability claim.
    """

    AVAILABLE = "available"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"
    BOUNDARY_ONLY = "boundary_only"


#: Canonical conversational availability to client-interface availability.  The
#: conversational statuses that carry no effective mode map to ``UNAVAILABLE``.
_CAPABILITY_STATUS_MAP: Mapping[ConversationCapabilityStatus, Any] = MappingProxyType(
    {
        ConversationCapabilityStatus.AVAILABLE: (
            ClientBackendCapabilityStatus.AVAILABLE
        ),
        ConversationCapabilityStatus.DEGRADED: ClientBackendCapabilityStatus.DEGRADED,
        ConversationCapabilityStatus.UNAVAILABLE: (
            ClientBackendCapabilityStatus.UNAVAILABLE
        ),
        ConversationCapabilityStatus.BLOCKED: (
            ClientBackendCapabilityStatus.UNAVAILABLE
        ),
        ConversationCapabilityStatus.APPROVAL_REQUIRED: (
            ClientBackendCapabilityStatus.UNAVAILABLE
        ),
    }
)


@dataclass(frozen=True, slots=True)
class ClientBackendCapabilityEvidence:
    """Read-only canonical capability evidence supplied at construction.

    This is a *projection input*, not an owner: it copies two immutable canonical
    declaration tuples and one canonical version string, holds no callable, no
    service and no registry, and can execute nothing.
    """

    application_capabilities: tuple[ApplicationCapability, ...] = ()
    model_boundary_capabilities: tuple[ApplicationCapability, ...] = ()
    application_api_version: str = APPLICATION_API_VERSION

    def __post_init__(self) -> None:
        for declaration in self.application_capabilities:
            if not isinstance(declaration, ApplicationCapability):
                raise TypeError(
                    "application_capabilities must contain ApplicationCapability "
                    f"values, not {type(declaration).__name__}"
                )
        for declaration in self.model_boundary_capabilities:
            if not isinstance(declaration, ApplicationCapability):
                raise TypeError(
                    "model_boundary_capabilities must contain ApplicationCapability "
                    f"values, not {type(declaration).__name__}"
                )
            if (
                declaration.capability_id
                not in CLIENT_BACKEND_MODEL_BOUNDARY_CAPABILITY_IDS
            ):
                raise ValueError(
                    "model_boundary_capabilities must declare only a frozen "
                    "Phase 11.50 model-boundary capability ID"
                )
        if not isinstance(self.application_api_version, str) or (
            not self.application_api_version.strip()
        ):
            raise ValueError("application_api_version must be a non-empty string")


@dataclass(frozen=True, slots=True)
class ClientBackendCapabilities:
    """The one immutable capability projection of the reusable client backend.

    Every field is a closed status member or a canonical version string.  The
    manifest is a *description*: it grants nothing, enables nothing, and carries
    no reason object, no owner and no callable.
    """

    interface_version: str
    application_api_version: str

    session_create: ClientBackendCapabilityStatus
    session_get: ClientBackendCapabilityStatus
    conversation_load: ClientBackendCapabilityStatus
    conversation_submit: ClientBackendCapabilityStatus
    conversation_edit: ClientBackendCapabilityStatus
    conversation_regenerate: ClientBackendCapabilityStatus

    response_event_stream: ClientBackendCapabilityStatus
    request_cancellation: ClientBackendCapabilityStatus
    attachments: ClientBackendCapabilityStatus
    #: The canonical effective mode of the attachment row: ``reference_only`` at
    #: this baseline, or ``None`` when no canonical attachment state exists.  It
    #: is immutable client-visible evidence so a first-party client can tell
    #: "conversational reference metadata only" apart from real attachment
    #: reachability (Audit V1 MAJOR-04).
    attachment_effective_mode: str | None
    document_upload: ClientBackendCapabilityStatus

    model_boundary_reasoning: ClientBackendCapabilityStatus
    model_boundary_multimodal: ClientBackendCapabilityStatus
    model_boundary_token_stream: ClientBackendCapabilityStatus

    end_to_end_reasoning: ClientBackendCapabilityStatus
    end_to_end_multimodal: ClientBackendCapabilityStatus
    end_to_end_token_stream: ClientBackendCapabilityStatus

    reasons: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in self._status_fields():
            if not isinstance(getattr(self, name), ClientBackendCapabilityStatus):
                raise TypeError(f"{name} must be a ClientBackendCapabilityStatus")
        mode = self.attachment_effective_mode
        if mode is not None and (
            not isinstance(mode, str)
            or not mode.strip()
            or len(mode) > CLIENT_BACKEND_MAX_IDENTIFIER_LENGTH
        ):
            raise ValueError(
                "attachment_effective_mode must be None or a non-empty bounded "
                "canonical effective-mode string"
            )
        if not isinstance(self.reasons, MappingProxyType):
            object.__setattr__(self, "reasons", MappingProxyType(dict(self.reasons)))
        for key in self.reasons:
            if not isinstance(key, str) or not key.strip():
                raise ValueError("capability reason keys must be non-empty strings")

    @staticmethod
    def _status_fields() -> dict[str, Any]:
        """Return the closed status fields of the manifest."""

        return {
            "session_create": None,
            "session_get": None,
            "conversation_load": None,
            "conversation_submit": None,
            "conversation_edit": None,
            "conversation_regenerate": None,
            "response_event_stream": None,
            "request_cancellation": None,
            "attachments": None,
            "document_upload": None,
            "model_boundary_reasoning": None,
            "model_boundary_multimodal": None,
            "model_boundary_token_stream": None,
            "end_to_end_reasoning": None,
            "end_to_end_multimodal": None,
            "end_to_end_token_stream": None,
        }

    def status(self, field_name: str) -> ClientBackendCapabilityStatus:
        """Return one closed status field, failing closed on an unknown name."""

        if field_name not in self._status_fields():
            raise ValueError(f"{field_name} is not a client capability field")
        return getattr(self, field_name)

    def to_dict(self) -> dict[str, Any]:
        """Return the deterministic public representation of the manifest."""

        payload: dict[str, Any] = {
            "interface_version": self.interface_version,
            "application_api_version": self.application_api_version,
        }
        for name in self._status_fields():
            payload[name] = getattr(self, name).value
        payload["attachment_effective_mode"] = self.attachment_effective_mode
        payload["reasons"] = {key: self.reasons[key] for key in sorted(self.reasons)}
        return payload


def _declared(
    declarations: Sequence[ApplicationCapability], capability_id: str
) -> ApplicationCapability | None:
    """Return the first canonical declaration of *capability_id*, or ``None``."""

    return next(
        (
            declaration
            for declaration in declarations
            if declaration.capability_id == capability_id
        ),
        None,
    )


def _declared_reason(
    declarations: Sequence[ApplicationCapability],
    capability_id: str,
    *,
    default: str,
) -> str:
    """Return the canonical reason code of a declaration, or *default*."""

    declaration = _declared(declarations, capability_id)
    if declaration is not None and declaration.reason_code is not None:
        return declaration.reason_code
    return default


def _canonical_capability_status(
    declarations: Sequence[ApplicationCapability], capability_id: str
) -> ClientBackendCapabilityStatus:
    """Project one canonical application declaration into client truth."""

    declaration = _declared(declarations, capability_id)
    if declaration is None:
        return ClientBackendCapabilityStatus.UNAVAILABLE
    if declaration.status is CapabilityStatus.AVAILABLE:
        return ClientBackendCapabilityStatus.AVAILABLE
    if declaration.status is CapabilityStatus.DEFERRED:
        return ClientBackendCapabilityStatus.UNAVAILABLE
    return ClientBackendCapabilityStatus.UNAVAILABLE


def _boundary_status(
    declarations: Sequence[ApplicationCapability], capability_id: str
) -> ClientBackendCapabilityStatus:
    """Project one model-boundary declaration, or report it undeclared.

    Only a canonical ``AVAILABLE`` declaration proves the boundary fact, and even
    then the projection is ``BOUNDARY_ONLY``: it is never an end-to-end claim.
    """

    declaration = _declared(declarations, capability_id)
    if declaration is None:
        return ClientBackendCapabilityStatus.UNAVAILABLE
    if declaration.status is not CapabilityStatus.AVAILABLE:
        return ClientBackendCapabilityStatus.UNAVAILABLE
    return ClientBackendCapabilityStatus.BOUNDARY_ONLY


def _conversation_state(
    states: Sequence[ConversationCapabilityState], capability_id: str
) -> ConversationCapabilityState | None:
    """Return the canonical conversational state of *capability_id*, or ``None``."""

    return next((item for item in states if item.capability == capability_id), None)


def _conversation_row(
    states: Sequence[ConversationCapabilityState], capability_id: str
) -> tuple[ClientBackendCapabilityStatus, str | None]:
    """Project one conversational capability row into client truth."""

    state = _conversation_state(states, capability_id)
    if state is None:
        return ClientBackendCapabilityStatus.UNAVAILABLE, REASON_NO_CONVERSATION_OWNER
    status = _CAPABILITY_STATUS_MAP[state.status]
    reason = state.reason
    if reason is None and status is ClientBackendCapabilityStatus.AVAILABLE:
        reason = None
    return status, reason


def build_client_backend_capabilities(
    *,
    evidence: ClientBackendCapabilityEvidence,
    conversation_resolver: ConversationCapabilityResolver | None,
) -> ClientBackendCapabilities:
    """Build the one capability projection from canonical evidence.

    ``conversation_resolver`` is the canonical Phase 11.5 resolver of the exact
    composed ``ConversationService``, or ``None`` when no conversational owner is
    composed — in which case every conversational row reports ``UNAVAILABLE``
    with the ``NO_CONVERSATION_OWNER`` reason rather than an optimistic guess.
    """

    application = evidence.application_capabilities
    boundary = evidence.model_boundary_capabilities

    if conversation_resolver is None:
        states: tuple[ConversationCapabilityState, ...] = ()
        conversation_available = False
    else:
        states = conversation_resolver.resolve()
        conversation_available = True

    def _row(capability_id: str) -> ClientBackendCapabilityStatus:
        if not conversation_available:
            return ClientBackendCapabilityStatus.UNAVAILABLE
        status, _ = _conversation_row(states, capability_id)
        return status

    def _reason(capability_id: str, *, default: str) -> str:
        _, reason = _conversation_row(states, capability_id)
        if reason is not None:
            return reason
        return default

    reasons: dict[str, str] = {}

    if not conversation_available:
        for capability_id in ("continuous_conversation",):
            reasons[capability_id] = REASON_NO_CONVERSATION_OWNER

    session_create = _row("continuous_conversation")
    session_get = session_create
    conversation_load = _row("continuous_conversation")
    conversation_submit = _row("continuous_conversation")
    conversation_edit = _row("message_editing")
    conversation_regenerate = _row("controlled_regeneration")

    # The dedicated response-event stream is the existing public response
    # delivery of the Phase 11.3 application boundary, projected from the
    # canonical application ``streaming`` declaration.  It is deliberately NOT
    # derived from the conversational ``response_streaming`` row: that row is
    # degraded because *provider token streaming* is unavailable, and collapsing
    # the two truths is exactly the Audit V1 MAJOR-04 defect.
    response_event_stream_status = _canonical_capability_status(
        application, _APPLICATION_RESPONSE_EVENT_STREAM_CAPABILITY_ID
    )
    if response_event_stream_status is not ClientBackendCapabilityStatus.AVAILABLE:
        reasons["response_event_stream"] = _declared_reason(
            application,
            _APPLICATION_RESPONSE_EVENT_STREAM_CAPABILITY_ID,
            default=REASON_NO_APPLICATION_DECLARATION,
        )

    request_cancellation, cancellation_reason = _conversation_row(
        states, "request_cancellation"
    )
    if not conversation_available:
        request_cancellation = ClientBackendCapabilityStatus.UNAVAILABLE
        cancellation_reason = _declared_reason(
            application, "request-cancellation", default=REASON_NO_CONVERSATION_OWNER
        )
    if cancellation_reason is not None:
        reasons["request_cancellation"] = cancellation_reason

    # Attachments: the canonical conversational row is AVAILABLE with the
    # effective mode ``reference_only`` — attachment *references* stay in
    # conversation state and never enter the application message payload, and
    # Phase 11.50 adds no upload, no file store and no path or URL resolver.  The
    # client-visible status is therefore DEGRADED and the canonical effective mode
    # is preserved verbatim, so a first-party client can tell reference metadata
    # apart from real attachment reachability (Audit V1 MAJOR-04).
    attachments, attachments_reason = _conversation_row(
        states, _CONVERSATION_ATTACHMENTS_CAPABILITY_ID
    )
    attachment_state = _conversation_state(
        states, _CONVERSATION_ATTACHMENTS_CAPABILITY_ID
    )
    attachment_effective_mode = (
        None if attachment_state is None else attachment_state.effective
    )
    if not conversation_available:
        attachments = ClientBackendCapabilityStatus.UNAVAILABLE
        attachment_effective_mode = None
    elif (
        attachments is ClientBackendCapabilityStatus.AVAILABLE
        and attachment_effective_mode == REFERENCE_ONLY_ATTACHMENT_MODE
    ):
        attachments = ClientBackendCapabilityStatus.DEGRADED
    if attachments_reason is not None:
        reasons["attachments"] = attachments_reason

    document_upload, upload_reason = _conversation_row(states, "document_upload")
    if not conversation_available:
        document_upload = ClientBackendCapabilityStatus.UNAVAILABLE
    if upload_reason is not None:
        reasons["document_upload"] = upload_reason

    # Phase 11.50 deliberately does not add reasoning effort to the
    # submit-message payload, so no end-to-end reasoning row may claim
    # availability.  The boundary fact is reported separately.
    model_boundary_reasoning = _boundary_status(
        boundary, MODEL_BOUNDARY_REASONING_CAPABILITY_ID
    )
    model_boundary_multimodal = _boundary_status(
        boundary, MODEL_BOUNDARY_MULTIMODAL_CAPABILITY_ID
    )
    model_boundary_token_stream = _boundary_status(
        boundary, MODEL_BOUNDARY_TOKEN_STREAM_CAPABILITY_ID
    )

    end_to_end_reasoning = ClientBackendCapabilityStatus.UNAVAILABLE
    reasons["end_to_end_reasoning"] = (
        REASON_MODEL_BOUNDARY_ONLY_NOT_END_TO_END
        if model_boundary_reasoning is ClientBackendCapabilityStatus.BOUNDARY_ONLY
        else REASON_MODEL_BOUNDARY_CAPABILITY_NOT_DECLARED
    )

    # Multimodal bytes are equally out of scope for Phase 11.50: no upload, no
    # path resolver and no URL downloader exists here.
    end_to_end_multimodal = ClientBackendCapabilityStatus.UNAVAILABLE
    reasons["end_to_end_multimodal"] = (
        REASON_MODEL_BOUNDARY_ONLY_NOT_END_TO_END
        if model_boundary_multimodal is ClientBackendCapabilityStatus.BOUNDARY_ONLY
        else REASON_MODEL_BOUNDARY_CAPABILITY_NOT_DECLARED
    )

    # The end-to-end token stream is the degraded conversational row reported by
    # the canonical resolver; it is never upgraded from the model boundary.  A
    # response-event stream is not a token stream, so an ``AVAILABLE``
    # conversational streaming row is still only ``DEGRADED`` here, and this row
    # is a separate fact from ``response_event_stream``.
    end_to_end_token_stream, token_stream_reason = _conversation_row(
        states, _CONVERSATION_RESPONSE_STREAMING_CAPABILITY_ID
    )
    if not conversation_available:
        end_to_end_token_stream = ClientBackendCapabilityStatus.UNAVAILABLE
        token_stream_reason = REASON_MODEL_BOUNDARY_ONLY_NOT_END_TO_END
    elif end_to_end_token_stream is ClientBackendCapabilityStatus.AVAILABLE:
        end_to_end_token_stream = ClientBackendCapabilityStatus.DEGRADED
    if token_stream_reason is not None:
        reasons["end_to_end_token_stream"] = token_stream_reason
    elif end_to_end_token_stream is ClientBackendCapabilityStatus.AVAILABLE:
        end_to_end_token_stream = ClientBackendCapabilityStatus.DEGRADED

    for name, status in (
        ("model_boundary_reasoning", model_boundary_reasoning),
        ("model_boundary_multimodal", model_boundary_multimodal),
        ("model_boundary_token_stream", model_boundary_token_stream),
    ):
        if status is ClientBackendCapabilityStatus.UNAVAILABLE:
            reasons[name] = REASON_MODEL_BOUNDARY_CAPABILITY_NOT_DECLARED

    return ClientBackendCapabilities(
        interface_version=CLIENT_BACKEND_INTERFACE_VERSION,
        application_api_version=evidence.application_api_version,
        session_create=session_create,
        session_get=session_get,
        conversation_load=conversation_load,
        conversation_submit=conversation_submit,
        conversation_edit=conversation_edit,
        conversation_regenerate=conversation_regenerate,
        response_event_stream=response_event_stream_status,
        request_cancellation=request_cancellation,
        attachments=attachments,
        attachment_effective_mode=attachment_effective_mode,
        document_upload=document_upload,
        model_boundary_reasoning=model_boundary_reasoning,
        model_boundary_multimodal=model_boundary_multimodal,
        model_boundary_token_stream=model_boundary_token_stream,
        end_to_end_reasoning=end_to_end_reasoning,
        end_to_end_multimodal=end_to_end_multimodal,
        end_to_end_token_stream=end_to_end_token_stream,
        reasons=MappingProxyType(reasons),
    )
