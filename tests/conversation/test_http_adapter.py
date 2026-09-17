"""Phase 11.5 — thin HTTP conversation endpoints over the canonical service.

Task 8 locks the transport half of ``DP-105``.  ``create_app`` gains one
additive keyword — ``conversation`` — and serves five conversation routes under
the existing ``/v1`` surface exclusively through the one
``ConversationService``: the adapter parses, delegates, serializes and maps safe
errors, and reaches no orchestrator, session store, domain owner, provider or
second request registry of its own.

These tests lock three layers:

- the model half: the conversational request bodies carry every explicit
  identity, revision and timestamp (the adapter invents no hidden state and
  never infers authority from ``bot_id``), and the response models re-validate
  the canonical conversational contracts' ``to_dict()`` output instead of
  re-implementing it, so a drifted projection is rejected at the transport
  boundary rather than published;
- the endpoint half: submit, edit and regeneration answer with the serialized
  ``AssistantResponse`` the service returned, the read answers with the
  canonical ``ConversationState``, cancellation reports the canonical
  unavailable state honestly, and a stale revision is a safe conflict — every
  failure answering with the one public error envelope;
- the boundary half: an application built without the service still constructs
  and answers every conversation route with the stable capability-unavailable
  failure, the pre-existing endpoints behave identically either way (including
  byte-identical SSE frames), ``document_upload`` stays explicitly unavailable
  and no internal detail — traceback, path or exception text — can escape.

The conversation routes run over a real composed application graph (the
canonical local runtime) and the real ``ConversationService``, so the surface is
exercised as wired rather than simulated.

See ``docs/superpowers/specs/2026-09-17-phase-11.5-conversational-interface-design.md``
(sections 17, 22, 23, 25 and 26) and the committed Phase 11.5 plan.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, fields
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from cmm.api.app import _CONVERSATION_SUCCESS_STATUS, create_app
from cmm.api.errors import (
    REASON_INVALID_REQUEST_BODY,
    REASON_INVALID_REQUEST_CONTRACT,
    REASON_UNKNOWN_ROUTE,
    success_status_code,
)
from cmm.api.models import (
    AssistantResponseModel,
    ConversationEditBody,
    ConversationMessageBody,
    ConversationRegenerateBody,
    ConversationStateModel,
    assistant_response_model_from,
    conversation_state_model_from,
)
from cmm.application import (
    APPLICATION_API_VERSION,
    MAX_MESSAGE_LENGTH,
    ApplicationErrorCode,
    ApplicationOperation,
    ApplicationResponse,
    ApplicationStatus,
    InvalidApplicationRequestError,
)
from cmm.application.errors import GENERIC_FAILURE_MESSAGE
from cmm.application.gateway import CANCELLATION_UNAVAILABLE_MESSAGE
from cmm.application.local_runtime import (
    LocalApplicationRuntime,
    build_local_application_runtime,
)
from cmm.conversation.capabilities import ConversationCapabilityResolver
from cmm.conversation.contracts import (
    AssistantResponse,
    ConversationLineage,
    ConversationMessage,
    ConversationRole,
)
from cmm.conversation.errors import ConversationBoundaryError
from cmm.conversation.projection import ConversationResponseProjector
from cmm.conversation.service import ConversationService
from cmm.conversation.state import (
    ConversationState,
    SharedSessionConversationAdapter,
)

REQUEST_ID_HEADER = "X-Request-ID"
IDEMPOTENCY_KEY_HEADER = "Idempotency-Key"

SESSION_ID = "session-conversation-1"
OTHER_SESSION_ID = "session-conversation-2"

CORRELATION_ID = "request-correlation-1"

USER_REQUEST_ID = "request-turn-1"
EDIT_REQUEST_ID = "request-turn-2"
REGENERATE_REQUEST_ID = "request-turn-3"

USER_MESSAGE_ID = "user-message-1"
ASSISTANT_MESSAGE_ID = "assistant-message-1"
REPLACEMENT_MESSAGE_ID = "user-message-1-edit"
EDITED_ASSISTANT_MESSAGE_ID = "assistant-message-2"
REGENERATED_APPLICATION_MESSAGE_ID = "application-message-3"
REGENERATED_ASSISTANT_MESSAGE_ID = "assistant-message-3"

USER_CREATED_AT = "2026-09-17T10:00:00+00:00"
ASSISTANT_CREATED_AT = "2026-09-17T10:00:01+00:00"
EDIT_CREATED_AT = "2026-09-17T10:01:00+00:00"
EDITED_ASSISTANT_CREATED_AT = "2026-09-17T10:01:01+00:00"
REGENERATED_ASSISTANT_CREATED_AT = "2026-09-17T10:02:01+00:00"

USER_CONTENT = "What changed in the plan?"
EDITED_CONTENT = "What changed in the plan, exactly?"

#: The pinned public text of a canonical ``NEEDS_CLARIFICATION`` outcome: a
#: plain conversational message carries no structured intent shape, so the
#: deterministic canonical resolver answers clarification before routing.
NEEDS_CLARIFICATION_TEXT = "Additional information is required."

#: Raw internal defect text that must never reach a client.
RAW_DEFECT_TEXT = (
    "Traceback (most recent call last): internal defect at "
    "/private/tmp/cmm-internal-detail with secret AKIA-EXAMPLE-SECRET-KEY"
)

#: Fragments no conversation answer may ever carry.
FORBIDDEN_FRAGMENTS = (
    "Traceback",
    "cmm-internal-detail",
    "AKIA-EXAMPLE-SECRET-KEY",
)

#: The five additive conversation routes of Phase 11.5 (DP-105), under the
#: existing ``/v1`` surface.
FROZEN_CONVERSATION_ROUTES = (
    ("get", "/v1/conversations/{session_id}"),
    ("post", "/v1/conversations/{session_id}/messages"),
    ("post", "/v1/conversations/{session_id}/messages/{message_id}/edit"),
    ("post", "/v1/conversations/{session_id}/responses/{message_id}/regenerate"),
    ("post", "/v1/conversations/requests/{request_id}/cancel"),
)

#: The pre-existing Phase 11.3 route surface; the conversation seam may not
#: remove, rename or move any of it.
PRE_EXISTING_ROUTES = (
    ("get", "/v1/health"),
    ("get", "/v1/capabilities"),
    ("post", "/v1/sessions"),
    ("get", "/v1/sessions/{session_id}"),
    ("post", "/v1/sessions/{session_id}/messages"),
    ("post", "/v1/sessions/{session_id}/messages/stream"),
    ("post", "/v1/requests/{request_id}/cancel"),
)

#: The exact field sets of the conversational request bodies.
MESSAGE_BODY_FIELDS = frozenset(
    {
        "request_id",
        "message_id",
        "content",
        "expected_session_revision",
        "created_at",
        "assistant_message_id",
        "assistant_created_at",
        "bot_id",
        "requested_capabilities",
        "references",
        "attachments",
    }
)
REGENERATE_BODY_FIELDS = frozenset(
    {
        "request_id",
        "application_message_id",
        "expected_session_revision",
        "assistant_message_id",
        "assistant_created_at",
    }
)
ATTACHMENT_BODY_FIELDS = frozenset({"ref", "kind", "name", "media_type"})

#: The frozen serialized response shape of the canonical contract.
ASSISTANT_RESPONSE_FIELDS = frozenset(
    {
        "message",
        "sources",
        "reasoning_summary",
        "pending_questions",
        "proposed_actions",
        "approval_requests",
        "workflow_updates",
        "domain_state",
        "capability_state",
        "memory_updates",
        "warnings",
    }
)
CONVERSATION_STATE_FIELDS = frozenset(
    {"version", "session_id", "mode", "bot_id", "active_message_id", "messages"}
)


# ── Harness ──────────────────────────────────────────────────────────────────


class _RecordingConversationService(ConversationService):
    """The canonical conversational service plus the observation these tests need.

    The service class is never replaced: every call still lands on the real
    ``ConversationService`` and the recorded value is the one it returned.
    """

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.submitted: list[AssistantResponse] = []
        self.edited: list[AssistantResponse] = []
        self.regenerated: list[AssistantResponse] = []
        self.cancelled: list[ApplicationResponse] = []
        self.loaded: list[str] = []

    def load(self, session_id: str) -> ConversationState | None:
        state = super().load(session_id)
        self.loaded.append(session_id)
        return state

    def submit(self, message: ConversationMessage, **kwargs: Any) -> AssistantResponse:
        response = super().submit(message, **kwargs)
        self.submitted.append(response)
        return response

    def edit(self, **kwargs: Any) -> AssistantResponse:
        response = super().edit(**kwargs)
        self.edited.append(response)
        return response

    def regenerate(self, **kwargs: Any) -> AssistantResponse:
        response = super().regenerate(**kwargs)
        self.regenerated.append(response)
        return response

    def cancel(self, *, request_id: str, target_request_id: str) -> ApplicationResponse:
        response = super().cancel(
            request_id=request_id, target_request_id=target_request_id
        )
        self.cancelled.append(response)
        return response


class _DefectiveConversationService(_RecordingConversationService):
    """A real service whose one turn raises a raw internal defect."""

    def submit(self, message: ConversationMessage, **kwargs: Any) -> AssistantResponse:
        raise RuntimeError(RAW_DEFECT_TEXT)


class _DriftedAssistantResponse(AssistantResponse):
    """A drifted turn projection: the serialized shape gained an internal key."""

    def to_dict(self) -> dict[str, Any]:
        return {**super().to_dict(), "internal_trace": RAW_DEFECT_TEXT}


class _DriftedConversationState(ConversationState):
    """A drifted read projection: the serialized state gained an internal key."""

    def to_dict(self) -> dict[str, Any]:
        return {**super().to_dict(), "internal_trace": RAW_DEFECT_TEXT}


def _drifted_projection(value: Any, drifted_type: Any) -> Any:
    """Return *value* re-built as *drifted_type* with the same field values."""

    return drifted_type(
        **{field.name: getattr(value, field.name) for field in fields(value)}
    )


class _DriftedResponseConversationService(_RecordingConversationService):
    """A real service whose returned turn projection has drifted from the contract."""

    def submit(self, message: ConversationMessage, **kwargs: Any) -> AssistantResponse:
        return _drifted_projection(
            super().submit(message, **kwargs), _DriftedAssistantResponse
        )

    def edit(self, **kwargs: Any) -> AssistantResponse:
        return _drifted_projection(super().edit(**kwargs), _DriftedAssistantResponse)

    def regenerate(self, **kwargs: Any) -> AssistantResponse:
        return _drifted_projection(
            super().regenerate(**kwargs), _DriftedAssistantResponse
        )


class _DriftedStateConversationService(_RecordingConversationService):
    """A real service whose read projection has drifted from the contract."""

    def load(self, session_id: str) -> ConversationState | None:
        state = super().load(session_id)
        if state is None:
            return None
        return _drifted_projection(state, _DriftedConversationState)


class _InternalValueErrorConversationService(_RecordingConversationService):
    """A defective service whose own handling raises a raw ``ValueError``.

    The turn body is the canonical valid one, so nothing of the caller's input
    was rejected by the contract: the failure is the service's internal defect.
    """

    def submit(self, message: ConversationMessage, **kwargs: Any) -> AssistantResponse:
        raise ValueError(RAW_DEFECT_TEXT)


@dataclass(frozen=True, slots=True)
class _Harness:
    """One composed application, its service, its runtime and its client."""

    runtime: LocalApplicationRuntime
    service: _RecordingConversationService | None
    adapter: SharedSessionConversationAdapter
    app: FastAPI
    client: TestClient

    @property
    def revision(self) -> int:
        shared = self.adapter.load_shared_session(SESSION_ID)
        assert shared is not None
        return shared.revision

    @property
    def state(self) -> ConversationState:
        state = self.adapter.load_conversation(SESSION_ID)
        assert state is not None
        return state


def _service(
    runtime: LocalApplicationRuntime,
    service_type: type[ConversationService],
) -> _RecordingConversationService:
    """Compose the real conversational service over the canonical runtime."""

    service = service_type(
        gateway=runtime.gateway,
        state=SharedSessionConversationAdapter(runtime.session_store),
        capabilities=ConversationCapabilityResolver(),
        projector=ConversationResponseProjector(),
    )
    assert isinstance(service, _RecordingConversationService)
    return service


def _harness(
    *,
    with_service: bool = True,
    service_type: type[ConversationService] = _RecordingConversationService,
    create_session: bool = True,
    session_id: str = SESSION_ID,
) -> _Harness:
    """Return one composed application with (or without) the conversation service."""

    runtime = build_local_application_runtime()
    adapter = SharedSessionConversationAdapter(runtime.session_store)
    service = _service(runtime, service_type) if with_service else None
    app = create_app(runtime.gateway, conversation=service)
    client = TestClient(app)
    if create_session:
        created = client.post("/v1/sessions", json={"session_id": session_id})
        assert created.status_code == 201
    return _Harness(
        runtime=runtime,
        service=service,
        adapter=adapter,
        app=app,
        client=client,
    )


def _message_body(**overrides: Any) -> dict[str, Any]:
    """Return one explicit conversational turn body."""

    body: dict[str, Any] = {
        "request_id": USER_REQUEST_ID,
        "message_id": USER_MESSAGE_ID,
        "content": USER_CONTENT,
        "expected_session_revision": 1,
        "created_at": USER_CREATED_AT,
        "assistant_message_id": ASSISTANT_MESSAGE_ID,
        "assistant_created_at": ASSISTANT_CREATED_AT,
    }
    body.update(overrides)
    return body


def _edit_body(**overrides: Any) -> dict[str, Any]:
    """Return one explicit replacement body of an edit."""

    body = _message_body(
        request_id=EDIT_REQUEST_ID,
        message_id=REPLACEMENT_MESSAGE_ID,
        content=EDITED_CONTENT,
        created_at=EDIT_CREATED_AT,
        assistant_message_id=EDITED_ASSISTANT_MESSAGE_ID,
        assistant_created_at=EDITED_ASSISTANT_CREATED_AT,
        expected_session_revision=2,
    )
    body.update(overrides)
    return body


def _regenerate_body(**overrides: Any) -> dict[str, Any]:
    """Return one explicit regeneration body."""

    body: dict[str, Any] = {
        "request_id": REGENERATE_REQUEST_ID,
        "application_message_id": REGENERATED_APPLICATION_MESSAGE_ID,
        "expected_session_revision": 2,
        "assistant_message_id": REGENERATED_ASSISTANT_MESSAGE_ID,
        "assistant_created_at": REGENERATED_ASSISTANT_CREATED_AT,
    }
    body.update(overrides)
    return body


def _headers() -> dict[str, str]:
    return {REQUEST_ID_HEADER: CORRELATION_ID}


def _submit(harness: _Harness, **overrides: Any) -> Any:
    return harness.client.post(
        f"/v1/conversations/{SESSION_ID}/messages",
        json=_message_body(**overrides),
        headers=_headers(),
    )


def _first_turn(harness: _Harness) -> Any:
    """Submit one canonical first turn and return the HTTP response."""

    response = _submit(harness)
    assert response.status_code == 200
    assert harness.revision == 2
    return response


#: Fields the canonical session owner stamps from the wall clock; two
#: independently created sessions legitimately differ in them, so a
#: behaviour-identity comparison excludes exactly these.
_CLOCK_FIELDS = frozenset({"created_at", "updated_at"})


def _without_clock_fields(value: Any) -> Any:
    """Return *value* with the wall-clock-stamped fields removed."""

    if isinstance(value, dict):
        return {
            key: _without_clock_fields(item)
            for key, item in value.items()
            if key not in _CLOCK_FIELDS
        }
    if isinstance(value, list):
        return [_without_clock_fields(item) for item in value]
    return value


def _assert_safe_failure(body: dict[str, Any], code: ApplicationErrorCode) -> None:
    """Assert one public failure envelope carries *code* and no internal detail."""

    assert body["api_version"] == APPLICATION_API_VERSION
    assert body["status"] == ApplicationStatus.FAILED.value
    assert body["error"]["code"] == code.value
    dumped = json.dumps(body)
    for forbidden in FORBIDDEN_FRAGMENTS:
        assert forbidden not in dumped
    assert "detail" not in body


def _assert_internal_failure(response: Any) -> None:
    """Assert one answer is the 500 fail-closed defect with no leaked detail."""

    assert response.status_code == 500
    assert response.headers[REQUEST_ID_HEADER] == CORRELATION_ID
    body = response.json()
    _assert_safe_failure(body, ApplicationErrorCode.INTERNAL_FAILURE)
    assert body["error"]["message"] == GENERIC_FAILURE_MESSAGE
    assert body["error"]["details"] == {}


# ── Models ───────────────────────────────────────────────────────────────────


def test_conversation_message_body_carries_every_explicit_turn_input() -> None:
    """The adapter invents no hidden state: identity, revision and timestamps arrive."""

    body = ConversationMessageBody.model_validate(_message_body())

    assert set(ConversationMessageBody.model_fields) == MESSAGE_BODY_FIELDS
    assert body.request_id == USER_REQUEST_ID
    assert body.message_id == USER_MESSAGE_ID
    assert body.expected_session_revision == 1
    assert body.created_at == USER_CREATED_AT
    assert body.assistant_message_id == ASSISTANT_MESSAGE_ID
    assert body.assistant_created_at == ASSISTANT_CREATED_AT
    assert body.bot_id is None
    assert body.requested_capabilities == []
    assert body.references == []
    assert body.attachments == []


def test_conversation_edit_body_carries_the_replacement_identity() -> None:
    """An edit body names the replacement; the edited original is the path identity."""

    body = ConversationEditBody.model_validate(_edit_body())

    assert set(ConversationEditBody.model_fields) == MESSAGE_BODY_FIELDS
    assert body.message_id == REPLACEMENT_MESSAGE_ID
    assert body.content == EDITED_CONTENT
    assert body.expected_session_revision == 2


def test_conversation_regenerate_body_carries_every_explicit_input() -> None:
    body = ConversationRegenerateBody.model_validate(_regenerate_body())

    assert set(ConversationRegenerateBody.model_fields) == REGENERATE_BODY_FIELDS
    assert body.application_message_id == REGENERATED_APPLICATION_MESSAGE_ID
    assert body.assistant_message_id == REGENERATED_ASSISTANT_MESSAGE_ID


def test_conversation_message_body_pins_the_attachment_reference_fields() -> None:
    body = ConversationMessageBody.model_validate(
        _message_body(
            attachments=[
                {"ref": "attachment-1", "kind": "document", "name": "plan.md"},
                {"ref": "attachment-2", "kind": "image", "media_type": "image/png"},
            ]
        )
    )

    assert set(type(body.attachments[0]).model_fields) == ATTACHMENT_BODY_FIELDS
    assert body.attachments[0].ref == "attachment-1"
    assert body.attachments[0].name == "plan.md"
    assert body.attachments[1].media_type == "image/png"


def test_conversation_bodies_reject_unknown_input() -> None:
    """Closed bodies: a caller can not smuggle lineage, metadata or an unknown field."""

    for extra in ("lineage", "metadata", "session_id", "actor_id", "unknown"):
        with pytest.raises(ValidationError):
            ConversationMessageBody.model_validate(
                {**_message_body(), extra: {"supersedes_message_id": USER_MESSAGE_ID}}
            )


def test_conversation_body_revision_is_an_exact_non_negative_integer() -> None:
    """``True`` is an ``int`` subclass, so a lax field would read it as revision 1."""

    for value in (True, 1.0, "1", -1, None):
        with pytest.raises(ValidationError):
            ConversationMessageBody.model_validate(
                _message_body(expected_session_revision=value)
            )


def test_conversation_body_content_is_bounded_but_may_be_empty() -> None:
    """An attachment-only turn stays representable; an unbounded body never parses."""

    assert (
        ConversationMessageBody.model_validate(_message_body(content="")).content == ""
    )
    with pytest.raises(ValidationError):
        ConversationMessageBody.model_validate(
            _message_body(content="x" * (MAX_MESSAGE_LENGTH + 1))
        )
    with pytest.raises(ValidationError):
        ConversationMessageBody.model_validate(_message_body(content=None))


def test_assistant_response_model_re_validates_the_canonical_contract() -> None:
    """The transport view is the contract's ``to_dict()``, never a re-implementation."""

    response = AssistantResponse(
        message=ConversationMessage(
            id=ASSISTANT_MESSAGE_ID,
            session_id=SESSION_ID,
            role=ConversationRole.ASSISTANT,
            content=NEEDS_CLARIFICATION_TEXT,
            created_at=ASSISTANT_CREATED_AT,
            lineage=ConversationLineage(),
        ),
        sources=("domain:general",),
    )

    model = assistant_response_model_from(response)

    assert model.model_dump(mode="json") == response.to_dict()
    assert set(model.model_dump()) == ASSISTANT_RESPONSE_FIELDS

    drifted = {**response.to_dict(), "traceback": "internal detail"}
    with pytest.raises(ValidationError):
        AssistantResponseModel.model_validate(drifted)

    with pytest.raises(TypeError):
        assistant_response_model_from(object())  # type: ignore[arg-type]


def test_conversation_state_model_re_validates_the_canonical_contract() -> None:
    state = ConversationState(
        session_id=SESSION_ID,
        messages=(
            ConversationMessage(
                id=USER_MESSAGE_ID,
                session_id=SESSION_ID,
                role=ConversationRole.USER,
                content=USER_CONTENT,
                created_at=USER_CREATED_AT,
            ),
        ),
        active_message_id=USER_MESSAGE_ID,
    )

    model = conversation_state_model_from(state)

    assert model.model_dump(mode="json") == state.to_dict()
    assert set(model.model_dump()) == CONVERSATION_STATE_FIELDS

    with pytest.raises(ValidationError):
        ConversationStateModel.model_validate({**state.to_dict(), "unknown": "field"})

    with pytest.raises(TypeError):
        conversation_state_model_from(object())  # type: ignore[arg-type]


# ── The published surface ────────────────────────────────────────────────────


def test_the_five_conversation_routes_are_published_under_v1() -> None:
    """First-party and alternative clients discover the conversational surface."""

    harness = _harness(with_service=False)
    document = harness.app.openapi()

    for method, path in FROZEN_CONVERSATION_ROUTES:
        assert path in document["paths"], path
        operation = document["paths"][path][method]
        assert operation["summary"].strip()
        successes = [status for status in operation["responses"] if status[0] == "2"]
        assert successes == ["200"]


def test_the_conversation_success_status_is_the_frozen_default() -> None:
    """No conversation route creates a public resource."""

    assert _CONVERSATION_SUCCESS_STATUS == 200
    for operation in ApplicationOperation:
        if operation is ApplicationOperation.SESSION_CREATE:
            continue
        assert success_status_code(operation) == _CONVERSATION_SUCCESS_STATUS


# ── Submit, edit and regeneration ────────────────────────────────────────────


def test_submit_returns_the_serialized_assistant_response() -> None:
    harness = _harness()

    response = _submit(harness)

    assert response.status_code == 200
    assert response.headers[REQUEST_ID_HEADER] == CORRELATION_ID
    body = response.json()
    assert body["api_version"] == APPLICATION_API_VERSION
    assert body["status"] == ApplicationStatus.SUCCESS.value
    assert body["request_id"] == CORRELATION_ID
    assert body["error"] is None

    # The payload is exactly the canonical contract serialization of the
    # response the service returned — not a second, adapter-owned shape.
    payload = body["data"]
    assert payload == harness.service.submitted[0].to_dict()
    assert set(payload) == ASSISTANT_RESPONSE_FIELDS
    assert payload["message"]["id"] == ASSISTANT_MESSAGE_ID
    assert payload["message"]["role"] == ConversationRole.ASSISTANT.value
    assert payload["message"]["content"] == NEEDS_CLARIFICATION_TEXT
    assert payload["message"]["session_id"] == SESSION_ID
    assert payload["message"]["lineage"] == {
        "supersedes_message_id": None,
        "regenerates_message_id": None,
    }

    # The turn is committed through the canonical session authority.
    assert harness.revision == 2
    stored = harness.state
    assert [message.id for message in stored.messages] == [
        USER_MESSAGE_ID,
        ASSISTANT_MESSAGE_ID,
    ]
    assert payload["message"] == stored.message(ASSISTANT_MESSAGE_ID).to_dict()


def test_submit_carries_the_caller_identities_and_opaque_bot_association() -> None:
    """``bot_id`` is association metadata: it selects nothing and grants nothing."""

    harness = _harness()

    response = _submit(
        harness,
        bot_id="bot-untrusted",
        requested_capabilities=["response_streaming"],
        references=["reference-1"],
        attachments=[{"ref": "attachment-1", "kind": "document"}],
    )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["message"]["bot_id"] == "bot-untrusted"

    # The caller's references and attachment references bind to the submitted
    # user message in the canonical transcript — never to a transport-side list.
    stored = harness.state.message(USER_MESSAGE_ID)
    assert stored.references == ("reference-1",)
    assert [attachment.to_dict() for attachment in stored.attachments] == [
        {
            "ref": "attachment-1",
            "kind": "document",
            "name": None,
            "media_type": None,
        }
    ]

    # The opaque association selects nothing: the canonical capability truth is
    # the same one an association-free turn reports.
    declared = {state["capability"]: state for state in payload["capability_state"]}
    assert declared["response_streaming"]["requested"] is True
    assert declared["response_streaming"]["status"] == "degraded"
    assert declared["response_streaming"]["effective"] == "response_event_stream"
    assert declared["document_upload"]["status"] == "unavailable"


def test_edit_preserves_the_original_and_binds_the_supersedes_lineage() -> None:
    harness = _harness()
    _first_turn(harness)
    original = harness.state.message(USER_MESSAGE_ID).to_dict()

    response = harness.client.post(
        f"/v1/conversations/{SESSION_ID}/messages/{USER_MESSAGE_ID}/edit",
        json=_edit_body(),
        headers=_headers(),
    )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload == harness.service.edited[0].to_dict()
    assert payload["message"]["id"] == EDITED_ASSISTANT_MESSAGE_ID
    assert payload["message"]["content"] == NEEDS_CLARIFICATION_TEXT

    # Editing is append-only: the original is preserved byte-identical and the
    # replacement carries the enforced lineage; the service owns the lineage, so
    # the new assistant response carries none.
    assert harness.revision == 3
    stored = harness.state
    assert stored.message(USER_MESSAGE_ID).to_dict() == original
    replacement = stored.message(REPLACEMENT_MESSAGE_ID)
    assert replacement.role is ConversationRole.USER
    assert replacement.content == EDITED_CONTENT
    assert replacement.lineage.supersedes_message_id == USER_MESSAGE_ID
    assert payload["message"]["lineage"] == {
        "supersedes_message_id": None,
        "regenerates_message_id": None,
    }
    assert [message.id for message in stored.messages] == [
        USER_MESSAGE_ID,
        ASSISTANT_MESSAGE_ID,
        REPLACEMENT_MESSAGE_ID,
        EDITED_ASSISTANT_MESSAGE_ID,
    ]


def test_regeneration_preserves_the_original_and_binds_the_regenerates_lineage() -> (
    None
):
    harness = _harness()
    _first_turn(harness)
    original = harness.state.message(ASSISTANT_MESSAGE_ID).to_dict()

    response = harness.client.post(
        f"/v1/conversations/{SESSION_ID}/responses/{ASSISTANT_MESSAGE_ID}/regenerate",
        json=_regenerate_body(),
        headers=_headers(),
    )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload == harness.service.regenerated[0].to_dict()
    assert payload["message"]["id"] == REGENERATED_ASSISTANT_MESSAGE_ID
    assert payload["message"]["content"] == NEEDS_CLARIFICATION_TEXT
    assert payload["message"]["lineage"] == {
        "supersedes_message_id": None,
        "regenerates_message_id": ASSISTANT_MESSAGE_ID,
    }

    # Regeneration is canonical re-execution: the original is preserved and no
    # new user message is appended.
    assert harness.revision == 3
    stored = harness.state
    assert stored.message(ASSISTANT_MESSAGE_ID).to_dict() == original
    assert [message.id for message in stored.messages] == [
        USER_MESSAGE_ID,
        ASSISTANT_MESSAGE_ID,
        REGENERATED_ASSISTANT_MESSAGE_ID,
    ]


# ── Conversation read ────────────────────────────────────────────────────────


def test_the_conversation_read_returns_the_canonical_state() -> None:
    harness = _harness()
    _first_turn(harness)

    response = harness.client.get(f"/v1/conversations/{SESSION_ID}", headers=_headers())

    assert response.status_code == 200
    body = response.json()
    assert body["request_id"] == CORRELATION_ID
    # The read goes through the service, never the store, and returns the
    # deterministic ConversationState serialization.
    assert harness.service.loaded == [SESSION_ID]
    assert body["data"] == harness.state.to_dict()
    assert set(body["data"]) == CONVERSATION_STATE_FIELDS
    assert body["data"]["messages"][0]["id"] == USER_MESSAGE_ID


def test_an_absent_conversation_is_not_found() -> None:
    harness = _harness()

    unknown = harness.client.get("/v1/conversations/session-missing")
    absent = harness.client.get(f"/v1/conversations/{SESSION_ID}")

    for response in (unknown, absent):
        assert response.status_code == 404
        _assert_safe_failure(response.json(), ApplicationErrorCode.RESOURCE_NOT_FOUND)


def test_the_read_never_touches_a_foreign_session() -> None:
    harness = _harness()
    _first_turn(harness)

    response = harness.client.get(f"/v1/conversations/{OTHER_SESSION_ID}")

    assert response.status_code == 404
    assert harness.service.loaded == [OTHER_SESSION_ID]


# ── Cancellation ─────────────────────────────────────────────────────────────


def test_cancellation_returns_the_canonical_unavailable_state() -> None:
    harness = _harness()

    response = harness.client.post(
        "/v1/conversations/requests/req-target/cancel", headers=_headers()
    )

    assert response.status_code == 503
    assert response.headers[REQUEST_ID_HEADER] == CORRELATION_ID
    body = response.json()
    assert body["request_id"] == CORRELATION_ID
    assert body["error"]["code"] == ApplicationErrorCode.CAPABILITY_UNAVAILABLE.value
    assert body["error"]["message"] == CANCELLATION_UNAVAILABLE_MESSAGE

    # The canonical answer is reported honestly: the service delegated the
    # request-scoped command and nothing was written.
    canonical = harness.service.cancelled[0]
    assert canonical.error is not None
    assert canonical.error.code is ApplicationErrorCode.CAPABILITY_UNAVAILABLE
    assert harness.adapter.load_conversation(SESSION_ID) is None
    assert harness.revision == 1


# ── Failure mapping ──────────────────────────────────────────────────────────


def test_a_stale_revision_is_a_safe_conflict_without_a_write() -> None:
    harness = _harness()

    response = _submit(harness, expected_session_revision=0)

    assert response.status_code == 409
    body = response.json()
    _assert_safe_failure(body, ApplicationErrorCode.CONCURRENCY_CONFLICT)
    assert body["error"]["details"] == {}
    # A stale caller never traverses the canonical pipeline and never writes.
    assert harness.service.submitted == []
    assert harness.revision == 1
    assert harness.adapter.load_conversation(SESSION_ID) is None


def test_invalid_turn_input_maps_to_a_safe_invalid_request() -> None:
    harness = _harness()

    response = _submit(harness, assistant_created_at="2026-09-17 10:00:01")

    assert response.status_code == 400
    _assert_safe_failure(response.json(), ApplicationErrorCode.INVALID_REQUEST)
    assert harness.service.submitted == []


def test_an_unknown_edit_target_maps_to_a_safe_invalid_request() -> None:
    harness = _harness()
    _first_turn(harness)

    response = harness.client.post(
        f"/v1/conversations/{SESSION_ID}/messages/message-missing/edit",
        json=_edit_body(),
    )

    assert response.status_code == 400
    _assert_safe_failure(response.json(), ApplicationErrorCode.INVALID_REQUEST)
    assert harness.service.edited == []


def test_malformed_bodies_fail_at_transport_parse() -> None:
    """The existing convention maps a rejected body to a safe 400 envelope."""

    harness = _harness()

    missing = harness.client.post(
        f"/v1/conversations/{SESSION_ID}/messages",
        json={"request_id": USER_REQUEST_ID},
    )
    unknown = harness.client.post(
        f"/v1/conversations/{SESSION_ID}/messages",
        json={**_message_body(), "actor_id": "caller-chosen"},
    )

    for response in (missing, unknown):
        assert response.status_code == 400
        body = response.json()
        _assert_safe_failure(body, ApplicationErrorCode.INVALID_REQUEST)
        assert body["error"]["details"] == {"reason_code": REASON_INVALID_REQUEST_BODY}
    assert harness.service.submitted == []


def test_a_rejected_public_conversational_value_is_an_invalid_request() -> None:
    """A value the public contract rejects is the caller's defect, never a 500."""

    harness = _harness()

    response = _submit(harness, references=["reference-1", "reference-1"])

    assert response.status_code == 400
    body = response.json()
    _assert_safe_failure(body, ApplicationErrorCode.INVALID_REQUEST)
    assert body["error"]["details"] == {"reason_code": REASON_INVALID_REQUEST_CONTRACT}
    assert harness.service.submitted == []


def test_an_internal_defect_exposes_no_traceback_or_path() -> None:
    harness = _harness(service_type=_DefectiveConversationService)

    response = _submit(harness)

    assert response.status_code == 500
    body = response.json()
    assert body["error"]["code"] == ApplicationErrorCode.INTERNAL_FAILURE.value
    assert body["error"]["message"] == GENERIC_FAILURE_MESSAGE
    assert body["error"]["details"] == {}
    for forbidden in FORBIDDEN_FRAGMENTS:
        assert forbidden not in json.dumps(body)
    assert "detail" not in body


def test_the_conversational_message_is_mapped_not_copied() -> None:
    """The public message is application-owned; the conversational text is not copied."""

    harness = _harness()

    response = harness.client.post(
        f"/v1/conversations/{SESSION_ID}/messages/message-missing/edit",
        json=_edit_body(expected_session_revision=1),
    )

    assert response.status_code == 400
    body = response.json()
    application_message = InvalidApplicationRequestError().to_public_error().message
    assert body["error"]["message"] == application_message
    assert body["error"]["message"] != str(ConversationBoundaryError())
    assert harness.adapter.load_conversation(SESSION_ID) is None


def test_a_drifted_assistant_response_projection_is_an_internal_failure() -> None:
    """A defective turn projection is the server's defect, never the caller's 400."""

    harness = _harness(service_type=_DriftedResponseConversationService)

    response = _submit(harness)

    _assert_internal_failure(response)


def test_a_drifted_conversation_state_projection_is_an_internal_failure() -> None:
    """The read path classifies a drifted state projection the same way."""

    harness = _harness(service_type=_DriftedStateConversationService)
    _first_turn(harness)

    response = harness.client.get(f"/v1/conversations/{SESSION_ID}", headers=_headers())

    _assert_internal_failure(response)
    assert harness.service.loaded == [SESSION_ID]
    assert harness.revision == 2


def test_a_defective_service_value_error_is_not_reported_as_an_invalid_request() -> (
    None
):
    """The same turn is accepted by a healthy service, so a 400 would blame the caller."""

    accepted = _harness()
    assert _submit(accepted).status_code == 200

    harness = _harness(service_type=_InternalValueErrorConversationService)

    response = _submit(harness)

    _assert_internal_failure(response)


def test_a_caller_value_the_public_contract_rejects_is_still_a_safe_400() -> None:
    """The contract's own rejection of built caller values stays the caller's 400."""

    harness = _harness()

    submitted = _submit(harness, references=["reference-1", "reference-1"])
    edited = harness.client.post(
        f"/v1/conversations/{SESSION_ID}/messages/{USER_MESSAGE_ID}/edit",
        json=_edit_body(references=["reference-1", "reference-1"]),
        headers=_headers(),
    )

    for response in (submitted, edited):
        assert response.status_code == 400
        body = response.json()
        _assert_safe_failure(body, ApplicationErrorCode.INVALID_REQUEST)
        assert body["error"]["details"] == {
            "reason_code": REASON_INVALID_REQUEST_CONTRACT
        }
    # The rejection happens while the caller's values are built: the service is
    # never invoked and no turn is accepted.
    assert harness.service.submitted == []
    assert harness.service.edited == []


def test_the_conversational_boundary_statuses_stay_frozen() -> None:
    """409 conflict, 404 missing and 503 unavailable keep their frozen answers."""

    harness = _harness()

    stale = _submit(harness, expected_session_revision=0)
    missing = harness.client.get(
        "/v1/conversations/session-missing", headers=_headers()
    )
    unavailable = harness.client.post(
        "/v1/conversations/requests/req-target/cancel", headers=_headers()
    )

    assert stale.status_code == 409
    assert missing.status_code == 404
    assert unavailable.status_code == 503
    assert (
        stale.json()["error"]["code"] == ApplicationErrorCode.CONCURRENCY_CONFLICT.value
    )
    assert (
        missing.json()["error"]["code"] == ApplicationErrorCode.RESOURCE_NOT_FOUND.value
    )
    assert (
        unavailable.json()["error"]["code"]
        == ApplicationErrorCode.CAPABILITY_UNAVAILABLE.value
    )
    assert unavailable.json()["error"]["message"] == CANCELLATION_UNAVAILABLE_MESSAGE
    # No boundary answer traverses a caller classification or writes a turn.
    assert harness.revision == 1
    assert harness.adapter.load_conversation(SESSION_ID) is None


# ── Additive construction and preserved behaviour ───────────────────────────


def test_the_app_constructs_without_the_service_and_answers_unavailable() -> None:
    harness = _harness(with_service=False)

    health = harness.client.get("/v1/health")
    assert health.status_code == 200

    requests = (
        harness.client.get(f"/v1/conversations/{SESSION_ID}"),
        harness.client.post(
            f"/v1/conversations/{SESSION_ID}/messages", json=_message_body()
        ),
        harness.client.post(
            f"/v1/conversations/{SESSION_ID}/messages/{USER_MESSAGE_ID}/edit",
            json=_edit_body(),
        ),
        harness.client.post(
            f"/v1/conversations/{SESSION_ID}/responses/{ASSISTANT_MESSAGE_ID}/regenerate",
            json=_regenerate_body(),
        ),
        harness.client.post("/v1/conversations/requests/req-target/cancel"),
    )

    for response in requests:
        assert response.status_code == 503
        body = response.json()
        assert (
            body["error"]["code"] == ApplicationErrorCode.CAPABILITY_UNAVAILABLE.value
        )
        assert body["error"]["message"] == "Requested capability is unavailable"
        assert response.headers[REQUEST_ID_HEADER] == body["request_id"]
        for forbidden in FORBIDDEN_FRAGMENTS:
            assert forbidden not in json.dumps(body)


def test_create_app_refuses_a_foreign_conversation_service() -> None:
    """The additive keyword is fail-closed like the gateway it sits beside."""

    with pytest.raises(TypeError):
        create_app(_harness(with_service=False).runtime.gateway, conversation=object())


def test_existing_endpoints_behave_identically_when_the_service_is_supplied() -> None:
    bare = _harness(with_service=False)
    wired = _harness()

    # The pre-existing OpenAPI operations are unchanged by the seam.
    bare_document = bare.app.openapi()["paths"]
    wired_document = wired.app.openapi()["paths"]
    for method, path in PRE_EXISTING_ROUTES:
        assert bare_document[path][method] == wired_document[path][method]

    comparisons = (
        ("get", "/v1/health", {}),
        ("get", "/v1/capabilities", {}),
        ("get", f"/v1/sessions/{SESSION_ID}", {}),
        (
            "post",
            f"/v1/sessions/{SESSION_ID}/messages",
            {
                "json": {
                    "message_id": "message-1",
                    "actor_id": "actor-1",
                    "content": USER_CONTENT,
                    "expected_session_revision": 1,
                },
                "headers": {IDEMPOTENCY_KEY_HEADER: "key-1"},
            },
        ),
        ("post", "/v1/requests/req-target/cancel", {}),
    )

    for method, path, kwargs in comparisons:
        extra_headers = kwargs.pop("headers", {})
        without = getattr(bare.client, method)(
            path, headers=_headers() | dict(extra_headers), **kwargs
        )
        with_service = getattr(wired.client, method)(
            path, headers=_headers() | dict(extra_headers), **kwargs
        )
        assert without.status_code == with_service.status_code, (method, path)
        assert _without_clock_fields(without.json()) == _without_clock_fields(
            with_service.json()
        ), (method, path)
        assert (
            without.headers[REQUEST_ID_HEADER]
            == with_service.headers[REQUEST_ID_HEADER]
        )


def test_the_streaming_route_semantics_are_byte_identical() -> None:
    """The Phase 11.3 SSE surface is untouched by the conversation seam."""

    bare = _harness(with_service=False)
    wired = _harness()
    path = f"/v1/sessions/{SESSION_ID}/messages/stream"
    payload = {
        "json": {
            "message_id": "message-1",
            "actor_id": "actor-1",
            "content": USER_CONTENT,
            "expected_session_revision": 1,
        },
        "headers": _headers() | {IDEMPOTENCY_KEY_HEADER: "key-1"},
    }

    without = bare.client.post(path, **payload)
    with_service = wired.client.post(path, **payload)

    assert without.status_code == with_service.status_code == 200
    assert without.headers["content-type"] == with_service.headers["content-type"]
    assert without.content == with_service.content
    events = [
        block.splitlines()[0].split(": ", 1)[1]
        for block in without.text.split("\n\n")
        if block.strip()
    ]
    assert events == ["started", "data", "completed"]
    assert without.text.count(f"id: {CORRELATION_ID}:") == 3


def test_no_document_upload_endpoint_exists() -> None:
    """Upload/ingestion stays explicitly unavailable (spec section 19)."""

    harness = _harness()

    paths = {getattr(route, "path", "") for route in harness.app.routes}
    assert not [path for path in paths if "upload" in path]

    for path in (
        "/v1/documents",
        f"/v1/conversations/{SESSION_ID}/documents",
        f"/v1/conversations/{SESSION_ID}/documents/upload",
    ):
        response = harness.client.post(path, json={})
        assert response.status_code == 404
        body = response.json()
        assert body["error"]["code"] == ApplicationErrorCode.RESOURCE_NOT_FOUND.value
        assert body["error"]["details"] == {"reason_code": REASON_UNKNOWN_ROUTE}

    # The conversational capability surface reports the same truth.
    response = _submit(harness, requested_capabilities=["document_upload"])
    assert response.status_code == 200
    declared = {
        state["capability"]: state
        for state in response.json()["data"]["capability_state"]
    }
    assert declared["document_upload"]["status"] == "unavailable"
    assert declared["document_upload"]["effective"] is None
    assert declared["document_upload"]["reason"] == "NO_CANONICAL_STORAGE_OWNER"


# ── Thinness ─────────────────────────────────────────────────────────────────


def test_every_conversation_route_delegates_to_the_service_once() -> None:
    """The adapter parses, delegates and serializes — never a second owner."""

    harness = _harness()
    _first_turn(harness)

    harness.client.get(f"/v1/conversations/{SESSION_ID}")
    harness.client.post(
        f"/v1/conversations/{SESSION_ID}/messages/{USER_MESSAGE_ID}/edit",
        json=_edit_body(),
    )
    harness.client.post(
        f"/v1/conversations/{SESSION_ID}/responses/{EDITED_ASSISTANT_MESSAGE_ID}/regenerate",
        json=_regenerate_body(expected_session_revision=3),
    )
    harness.client.post("/v1/conversations/requests/req-target/cancel")

    assert len(harness.service.submitted) == 1
    assert len(harness.service.edited) == 1
    assert len(harness.service.regenerated) == 1
    assert len(harness.service.cancelled) == 1
    assert harness.service.loaded == [SESSION_ID]
    # The path identities reach the service verbatim: the enforced lineage the
    # replacement and the regenerated message carry is the one the path named.
    stored = harness.state
    assert (
        stored.message(REPLACEMENT_MESSAGE_ID).lineage.supersedes_message_id
        == USER_MESSAGE_ID
    )
    assert (
        stored.message(REGENERATED_ASSISTANT_MESSAGE_ID).lineage.regenerates_message_id
        == EDITED_ASSISTANT_MESSAGE_ID
    )
