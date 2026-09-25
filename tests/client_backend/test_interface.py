"""Phase 11.50 — facade delegation, owner identity and fail-closed gates.

``ClientBackend`` is a facade over two exact canonical owners.  These gates prove
each of the four properties the layer claims:

* **exact owner identity** — construction requires the concrete
  ``ApplicationGateway`` and ``ConversationService``, and rejects an incoherent
  pair whose conversational service writes through a *different* gateway;
* **delegation, not reimplementation** — session operations reuse the official
  Phase 11.3 session service, conversation operations reuse the exact Phase 11.5
  ``ConversationService`` methods, and canonical identities, revisions and
  lineage come back unchanged;
* **fail-closed interface validation** — an unsupported interface version and an
  unknown operation each fail closed with **zero** canonical gateway
  traversals;
* **safe error projection** — a canonical failure keeps its canonical safe code,
  and no client-visible string ever carries raw internal text.

Every test runs against the real canonical graph built by
``tests/client_backend/_canonical_graph.py``.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from cmm.application.contracts import ApplicationErrorCode, ApplicationSession
from cmm.application.errors import ApplicationResourceNotFoundError
from cmm.application.gateway import ApplicationGateway
from cmm.client_backend import (
    ClientBackend,
    ClientBackendError,
    ClientBackendErrorCode,
    ClientBackendRequest,
    ClientBackendResult,
    ClientOperation,
)
from cmm.conversation.contracts import (
    ConversationLineage,
    ConversationMessage,
    ConversationRole,
)
from cmm.conversation.errors import (
    ConversationBoundaryError,
    ConversationErrorCode,
    ConversationSessionConflictError,
)
from cmm.conversation.service import ConversationService
from tests.client_backend._canonical_graph import build_client_backend_graph

SESSION_ID = "client-backend-session"
TURN_AT = "2026-09-25T10:00:00+00:00"
TURN_RESPONSE_AT = "2026-09-25T10:00:01+00:00"
SECOND_TURN_AT = "2026-09-25T10:01:00+00:00"
SECOND_TURN_RESPONSE_AT = "2026-09-25T10:01:01+00:00"

#: A plain public conversational message.  The canonical application path routes
#: it through the composed orchestrator and reports the canonical routed text.
PLAIN_TEXT = "What changed in the plan?"


def _user(message_id: str, *, created_at: str = TURN_AT, content: str = PLAIN_TEXT):
    return ConversationMessage(
        id=message_id,
        session_id=SESSION_ID,
        role=ConversationRole.USER,
        content=content,
        created_at=created_at,
    )


# ── Owner identity ───────────────────────────────────────────────────────────


def test_the_facade_requires_the_canonical_conversation_service() -> None:
    """A duck-typed conversational stand-in is never accepted."""

    graph = build_client_backend_graph()

    class _LookAlike:
        def load(self, session_id):  # pragma: no cover - never reached
            return None

    with pytest.raises(TypeError):
        ClientBackend(
            gateway=graph.gateway,
            conversation=_LookAlike(),  # type: ignore[arg-type]
        )


def test_the_facade_requires_the_canonical_application_gateway() -> None:
    """A duck-typed gateway stand-in is never accepted."""

    graph = build_client_backend_graph()

    class _LookAlike:
        def handle(self, request):  # pragma: no cover - never reached
            return None

    with pytest.raises(TypeError):
        ClientBackend(
            gateway=_LookAlike(),  # type: ignore[arg-type]
            conversation=graph.conversation,
        )


def test_an_incoherent_gateway_pair_is_rejected() -> None:
    """A conversational service on a different gateway is not tolerated."""

    first = build_client_backend_graph()
    second = build_client_backend_graph()

    assert second.gateway is not first.gateway

    with pytest.raises(ValueError):
        ClientBackend(gateway=second.gateway, conversation=first.conversation)


def test_the_facade_retains_the_exact_owner_instances() -> None:
    """The facade delegates to the very instances it was constructed with."""

    graph = build_client_backend_graph()

    assert graph.client.gateway is graph.gateway
    assert graph.client.conversation is graph.conversation
    assert isinstance(graph.client.gateway, ApplicationGateway)
    assert isinstance(graph.client.conversation, ConversationService)
    # Owner coherence: the conversational service really uses this gateway.
    assert graph.conversation.gateway is graph.gateway


# ── Session operations ───────────────────────────────────────────────────────


def test_create_session_returns_the_canonical_session_and_zero_gateway_calls() -> None:
    """Session creation reuses the official session service, not the pipeline."""

    graph = build_client_backend_graph()

    session = graph.client.create_session(SESSION_ID)

    assert isinstance(session, ApplicationSession)
    assert session.session_id == SESSION_ID
    assert session.revision == 1
    assert session.status == "ACTIVE"
    assert datetime.fromisoformat(session.created_at).tzinfo is not None
    # The session path enters the one canonical gateway with the canonical
    # SESSION_CREATE command and never the conversational pipeline.
    assert graph.canonical_gateway_calls() == 1
    assert graph.session_gateway_calls() == 1
    assert graph.conversation_gateway_calls() == 0


def test_get_session_matches_the_canonical_session_state() -> None:
    """The round trip observes canonical shared session state, not a copy."""

    graph = build_client_backend_graph()
    created = graph.client.create_session(SESSION_ID)

    fetched = graph.client.get_session(SESSION_ID)
    canonical = graph.store.load(SESSION_ID)

    assert fetched == created
    assert canonical is not None
    assert canonical.session_id == fetched.session_id
    assert canonical.revision == fetched.revision
    # Both session operations entered the one public gateway entrypoint.
    assert graph.session_gateway_calls() == 2
    assert graph.conversation_gateway_calls() == 0


def test_creating_a_session_twice_fails_closed_at_the_interface() -> None:
    """A duplicate create is refused; the client layer adds no retry.

    The canonical session boundary reports the conflict as an
    ``ApplicationConflictError`` inside ``ApplicationGateway.handle``; the
    gateway's fail-closed boundary is the one public entrypoint, so a caller that
    is not the typed canonical pipeline (this facade) receives the safe canonical
    outcome projected into the closed client failure code.  Nothing is retried
    and nothing is replaced.
    """

    graph = build_client_backend_graph()
    graph.client.create_session(SESSION_ID)
    before = graph.store.load(SESSION_ID)

    with pytest.raises(ClientBackendError) as failure:
        graph.client.create_session(SESSION_ID)

    assert failure.value.code is ClientBackendErrorCode.INTERNAL_CLIENT_ERROR
    after = graph.store.load(SESSION_ID)
    assert after is not None and before is not None
    assert after.revision == before.revision
    assert after.created_at == before.created_at


def test_get_session_of_an_absent_session_fails_closed_safely() -> None:
    """An absent canonical session fails closed with no raw internal text."""

    graph = build_client_backend_graph()

    with pytest.raises(ClientBackendError) as failure:
        graph.client.get_session("does-not-exist")

    assert failure.value.code is ClientBackendErrorCode.INTERNAL_CLIENT_ERROR
    assert "does-not-exist" not in failure.value.message
    assert "Traceback" not in failure.value.message
    assert "/Users/" not in failure.value.message


# ── Conversation read ────────────────────────────────────────────────────────


def test_load_conversation_is_none_before_any_turn() -> None:
    """The read accessor returns canonical absence, never an empty invention."""

    graph = build_client_backend_graph()
    graph.client.create_session(SESSION_ID)

    assert graph.client.load_conversation(SESSION_ID) is None
    assert graph.conversation_gateway_calls() == 0


# ── Conversation operations ──────────────────────────────────────────────────


def test_submit_message_traverses_the_canonical_owners_exactly_once() -> None:
    """One turn is one canonical gateway traversal through the exact service."""

    graph = build_client_backend_graph()
    graph.client.create_session(SESSION_ID)

    response = graph.client.submit_message(
        _user("user-1"),
        request_id="request-1",
        expected_session_revision=1,
        assistant_message_id="assistant-1",
        assistant_created_at=TURN_RESPONSE_AT,
    )

    assert graph.conversation_gateway_calls() == 1
    assert response.message.session_id == SESSION_ID
    assert response.message.id == "assistant-1"
    assert response.message.created_at == TURN_RESPONSE_AT
    assert response.message.role is ConversationRole.ASSISTANT

    # Canonical identities and the canonical revision are preserved verbatim.
    state = graph.client.load_conversation(SESSION_ID)
    assert state is not None
    assert [message.id for message in state.messages] == ["user-1", "assistant-1"]
    assert state.session_id == SESSION_ID
    assert graph.store.load(SESSION_ID).revision == 2


def test_submit_message_preserves_canonical_lineage_and_message_identity() -> None:
    """A fresh turn carries no lineage, and no identity is rewritten."""

    graph = build_client_backend_graph()
    graph.client.create_session(SESSION_ID)

    response = graph.client.submit_message(
        _user("user-1"),
        request_id="request-1",
        expected_session_revision=1,
        assistant_message_id="assistant-1",
        assistant_created_at=TURN_RESPONSE_AT,
    )

    assert response.message.lineage == ConversationLineage()
    state = graph.client.load_conversation(SESSION_ID)
    assert state.messages[0].lineage == ConversationLineage()
    assert state.messages[0].content == PLAIN_TEXT


def test_a_stale_expected_revision_never_reaches_the_gateway() -> None:
    """A stale caller fails closed before the canonical pipeline is entered."""

    graph = build_client_backend_graph()
    graph.client.create_session(SESSION_ID)

    with pytest.raises(ConversationSessionConflictError):
        graph.client.submit_message(
            _user("user-1"),
            request_id="request-1",
            expected_session_revision=7,
            assistant_message_id="assistant-1",
            assistant_created_at=TURN_RESPONSE_AT,
        )

    assert graph.conversation_gateway_calls() == 0
    assert graph.client.load_conversation(SESSION_ID) is None


def test_edit_message_binds_canonical_lineage_and_preserves_the_original() -> None:
    """Editing is append-only and the lineage is bound by the canonical service."""

    graph = build_client_backend_graph()
    graph.client.create_session(SESSION_ID)
    graph.client.submit_message(
        _user("user-1"),
        request_id="request-1",
        expected_session_revision=1,
        assistant_message_id="assistant-1",
        assistant_created_at=TURN_RESPONSE_AT,
    )

    response = graph.client.edit_message(
        original_message_id="user-1",
        replacement=_user("user-1-edited", created_at=SECOND_TURN_AT),
        request_id="request-2",
        expected_session_revision=2,
        assistant_message_id="assistant-2",
        assistant_created_at=SECOND_TURN_RESPONSE_AT,
    )

    state = graph.client.load_conversation(SESSION_ID)
    assert state is not None
    assert [message.id for message in state.messages] == [
        "user-1",
        "assistant-1",
        "user-1-edited",
        "assistant-2",
    ]
    # The original is preserved byte-identically; the replacement is bound.
    assert state.messages[0].content == PLAIN_TEXT
    assert state.messages[0].lineage == ConversationLineage()
    assert state.messages[2].lineage.supersedes_message_id == "user-1"
    assert response.message.lineage == ConversationLineage()
    assert graph.conversation_gateway_calls() == 2


def test_regenerate_response_binds_canonical_lineage() -> None:
    """Regeneration is canonical re-execution with canonical lineage."""

    graph = build_client_backend_graph()
    graph.client.create_session(SESSION_ID)
    graph.client.submit_message(
        _user("user-1"),
        request_id="request-1",
        expected_session_revision=1,
        assistant_message_id="assistant-1",
        assistant_created_at=TURN_RESPONSE_AT,
    )

    regenerated = graph.client.regenerate_response(
        session_id=SESSION_ID,
        response_message_id="assistant-1",
        request_id="request-2",
        application_message_id="user-1-regenerated",
        expected_session_revision=2,
        assistant_message_id="assistant-2",
        assistant_created_at=SECOND_TURN_RESPONSE_AT,
    )

    state = graph.client.load_conversation(SESSION_ID)
    assert state is not None
    # The original response is preserved and no user message is re-appended.
    assert [message.id for message in state.messages] == [
        "user-1",
        "assistant-1",
        "assistant-2",
    ]
    assert regenerated.message.lineage.regenerates_message_id == "assistant-1"
    assert state.messages[1].lineage == ConversationLineage()


def test_cancel_request_reports_the_canonical_capability_unavailable() -> None:
    """Cancellation is delegated, never inferred from the model boundary."""

    graph = build_client_backend_graph()

    response = graph.client.cancel_request(
        request_id="request-cancel", target_request_id="request-1"
    )

    assert response.status.value == "failed"
    assert response.error is not None
    assert response.error.code is ApplicationErrorCode.CAPABILITY_UNAVAILABLE


def test_cancel_request_does_not_infer_availability_from_the_model_boundary() -> None:
    """A boundary-only declaration never upgrades conversational cancellation."""

    from cmm.application.contracts import ApplicationCapability, CapabilityStatus
    from cmm.client_backend.capabilities import (
        MODEL_BOUNDARY_REASONING_CAPABILITY_ID,
    )

    graph = build_client_backend_graph(
        model_boundary_capabilities=(
            ApplicationCapability(
                capability_id=MODEL_BOUNDARY_REASONING_CAPABILITY_ID,
                status=CapabilityStatus.AVAILABLE,
                version="1",
            ),
        )
    )

    capabilities = graph.client.capabilities()
    assert capabilities.request_cancellation.value == "unavailable"
    assert capabilities.model_boundary_reasoning.value == "boundary_only"


# ── Fail-closed version and operation ────────────────────────────────────────


def test_an_unsupported_interface_version_fails_closed_with_zero_calls() -> None:
    """The dispatch boundary validates the version before any owner."""

    graph = build_client_backend_graph()
    request = ClientBackendRequest.for_interface_version(
        "2",
        request_id="request-version",
        operation=ClientOperation.CAPABILITIES,
    )

    result = graph.client.dispatch(request)

    assert isinstance(result, ClientBackendResult)
    assert result.ok is False
    assert result.error is not None
    assert result.error.code is ClientBackendErrorCode.UNSUPPORTED_INTERFACE_VERSION
    assert result.data is None
    assert graph.canonical_gateway_calls() == 0


def test_the_constructor_gate_rejects_an_unsupported_version() -> None:
    """The normal envelope constructor is itself a version gate."""

    with pytest.raises(ClientBackendError) as failure:
        ClientBackendRequest(
            interface_version="2",
            request_id="request-version",
            operation=ClientOperation.CAPABILITIES,
        )

    assert failure.value.code is ClientBackendErrorCode.UNSUPPORTED_INTERFACE_VERSION


def test_a_blank_interface_version_is_an_invalid_client_contract() -> None:
    """A missing version is an invalid contract, not an unsupported one."""

    with pytest.raises(ClientBackendError) as failure:
        ClientBackendRequest(
            interface_version="   ",
            request_id="request-version",
            operation=ClientOperation.CAPABILITIES,
        )

    assert failure.value.code is ClientBackendErrorCode.INVALID_CLIENT_CONTRACT


def test_a_non_enum_operation_fails_closed_with_zero_calls() -> None:
    """An operation is a real enum member; a string never routes."""

    graph = build_client_backend_graph()

    with pytest.raises(TypeError):
        ClientBackendRequest(
            interface_version="1",
            request_id="request-op",
            operation="capabilities",  # type: ignore[arg-type]
        )

    assert graph.canonical_gateway_calls() == 0


def test_an_invalid_operation_fails_closed_with_zero_calls() -> None:
    """The dispatch boundary rejects a non-member operation before any owner.

    An operation is never routed by string.  The envelope constructor already
    refuses a raw string, so the dispatch boundary's own gate is exercised
    directly and its fail-closed behaviour is pinned here: no canonical owner is
    ever reached for a value that is not a real ``ClientOperation`` member.
    """

    graph = build_client_backend_graph()

    with pytest.raises(ClientBackendError) as failure:
        graph.client._require_supported_operation("capabilities")

    assert failure.value.code is ClientBackendErrorCode.INVALID_CLIENT_OPERATION
    assert graph.canonical_gateway_calls() == 0


def test_every_closed_operation_is_accepted_by_the_operation_gate() -> None:
    """Every frozen member passes the gate; the gate is not over-broad."""

    graph = build_client_backend_graph()

    for operation in ClientOperation:
        assert graph.client._require_supported_operation(operation) is operation


def test_dispatch_capabilities_returns_the_manifest() -> None:
    """The generic entrypoint projects the same capability truth."""

    graph = build_client_backend_graph()

    result = graph.client.dispatch(
        ClientBackendRequest(
            interface_version="1",
            request_id="request-caps",
            operation=ClientOperation.CAPABILITIES,
        )
    )

    assert result.ok is True
    assert result.error is None
    assert result.data is not None
    assert "capabilities" in result.data


def test_dispatch_create_and_get_session_round_trip() -> None:
    """The envelope path reaches the same canonical session owner."""

    graph = build_client_backend_graph()

    created = graph.client.dispatch(
        ClientBackendRequest(
            interface_version="1",
            request_id="request-create",
            operation=ClientOperation.CREATE_SESSION,
            payload={"session_id": SESSION_ID},
        )
    )
    fetched = graph.client.dispatch(
        ClientBackendRequest(
            interface_version="1",
            request_id="request-get",
            operation=ClientOperation.GET_SESSION,
            payload={"session_id": SESSION_ID},
        )
    )

    assert created.ok is True
    assert fetched.ok is True
    assert created.data["session"]["session_id"] == SESSION_ID
    assert fetched.data["session"] == created.data["session"]


def test_dispatch_load_conversation_reports_canonical_absence() -> None:
    """An absent conversation is reported as absent, not as an error."""

    graph = build_client_backend_graph()
    graph.client.create_session(SESSION_ID)

    result = graph.client.dispatch(
        ClientBackendRequest(
            interface_version="1",
            request_id="request-load",
            operation=ClientOperation.LOAD_CONVERSATION,
            payload={"session_id": SESSION_ID},
        )
    )

    assert result.ok is True
    assert result.data == {"conversation": None}


def test_dispatch_submit_message_returns_the_projected_response() -> None:
    """The envelope path traverses the canonical owners exactly once."""

    graph = build_client_backend_graph()
    graph.client.create_session(SESSION_ID)

    result = graph.client.dispatch(
        ClientBackendRequest(
            interface_version="1",
            request_id="request-submit",
            operation=ClientOperation.SUBMIT_MESSAGE,
            payload={
                "message": _user("user-1"),
                "message_request_id": "request-1",
                "expected_session_revision": 1,
                "assistant_message_id": "assistant-1",
                "assistant_created_at": TURN_RESPONSE_AT,
            },
        )
    )

    assert result.ok is True
    assert result.data["response"]["message"]["id"] == "assistant-1"
    assert graph.conversation_gateway_calls() == 1


def test_dispatch_with_a_missing_payload_field_fails_closed_contract() -> None:
    """A malformed envelope payload is an invalid client contract."""

    graph = build_client_backend_graph()

    result = graph.client.dispatch(
        ClientBackendRequest(
            interface_version="1",
            request_id="request-bad",
            operation=ClientOperation.GET_SESSION,
            payload={},
        )
    )

    assert result.ok is False
    assert result.error is not None
    assert result.error.code is ClientBackendErrorCode.INVALID_CLIENT_CONTRACT
    assert graph.canonical_gateway_calls() == 0


def test_dispatch_maps_an_unexpected_failure_to_the_generic_client_error() -> None:
    """An internal defect becomes one generic code with no raw internal message."""

    graph = build_client_backend_graph()
    graph.client.create_session(SESSION_ID)

    def _explode(*args, **kwargs):
        raise RuntimeError("internal path /Users/secret/token=sk-live-12345")

    graph.conversation.load = _explode  # type: ignore[method-assign]

    result = graph.client.dispatch(
        ClientBackendRequest(
            interface_version="1",
            request_id="request-explode",
            operation=ClientOperation.LOAD_CONVERSATION,
            payload={"session_id": SESSION_ID},
        )
    )

    assert result.ok is False
    assert result.error is not None
    assert result.error.code is ClientBackendErrorCode.INTERNAL_CLIENT_ERROR
    serialized = str(result.to_dict())
    assert "sk-live" not in serialized
    assert "/Users/" not in serialized
    assert "Traceback" not in serialized
    assert "RuntimeError" not in serialized


# ── Safe canonical failure projection ────────────────────────────────────────


def test_canonical_application_failure_keeps_its_canonical_code() -> None:
    """A canonical typed failure is reported with its own safe code and message."""

    graph = build_client_backend_graph()

    projection = graph.client.project_canonical_failure(
        ApplicationResourceNotFoundError(details={"reason_code": "SESSION_NOT_FOUND"})
    )

    assert projection["code"] == ApplicationErrorCode.RESOURCE_NOT_FOUND.value
    assert "Traceback" not in projection["message"]
    assert "/Users/" not in projection["message"]


def test_canonical_conversational_failure_keeps_its_canonical_code() -> None:
    """A canonical conversational failure is reported with its own safe code."""

    graph = build_client_backend_graph()

    projection = graph.client.project_canonical_failure(ConversationBoundaryError())

    assert projection["code"] == ConversationErrorCode.INVALID_REQUEST.value


def test_an_unknown_failure_projects_to_the_generic_client_error() -> None:
    """An arbitrary exception never leaks raw text through the projection."""

    graph = build_client_backend_graph()

    projection = graph.client.project_canonical_failure(
        ValueError("secret=/Users/christian/token")
    )

    assert projection["code"] == ClientBackendErrorCode.INTERNAL_CLIENT_ERROR.value
    assert "secret" not in projection["message"]
    assert "/Users/" not in projection["message"]
