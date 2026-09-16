"""Phase 11.3 — SSE streaming boundary tests.

The tests lock three layers of the frozen streaming contract:

- the serializer half: one ``ApplicationStreamEvent`` becomes one deterministic
  SSE frame — frozen field order, sorted compact JSON, no non-finite number and
  the application contract's own ``to_dict()`` as the only payload source;
- the projection half: one safe public response becomes exactly the frozen event
  sequence — ``STARTED``/``DATA``/``COMPLETED`` for a success and
  ``STARTED``/``ERROR`` for a failed response — so the stream terminates
  explicitly and never serializes an internal object raw;
- the adapter half: the v1 stream route builds and invokes the same versioned
  ``MESSAGE_SUBMIT`` command as the non-streaming route exactly once, answers
  with ``text/event-stream`` and keeps every internal defect out of the frames.

The message path runs through a real Phase 11.2 ``Orchestrator``, so the stream
is exercised as wired rather than simulated.

See ``docs/superpowers/specs/2026-09-16-phase-11.3-application-backend-design.md``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from dataclasses import replace as dataclass_replace
from typing import Any
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from cmm.api.app import create_app
from cmm.api.errors import REASON_INVALID_REQUEST_ID
from cmm.api.streaming import (
    SSE_MEDIA_TYPE,
    events_for_response,
    serialize_sse,
    sse_frames,
)
from cmm.application import (
    APPLICATION_API_VERSION,
    ApplicationCommand,
    ApplicationError,
    ApplicationErrorCode,
    ApplicationOperation,
    ApplicationRequest,
    ApplicationResponse,
    ApplicationStatus,
    ApplicationStreamEvent,
    CapabilityApplicationService,
    RequestApplicationService,
    SessionApplicationService,
    StreamEventKind,
    build_default_capabilities,
    failed_response,
    safe_error_from_exception,
)
from cmm.application.errors import GENERIC_FAILURE_MESSAGE
from cmm.application.gateway import ApplicationGateway
from cmm.application.health import HealthApplicationService
from cmm.application.idempotency import (
    InMemoryIdempotencyRepository,
    fingerprint_command,
)
from cmm.orchestration.contracts import (
    AgentRouteDecision,
    DomainRouteDecision,
    ExecutionRoute,
    IntentKind,
    IntentResolution,
    OrchestrationChannel,
    OrchestrationRequest,
    OrchestrationResult,
    OrchestrationStatus,
    ResolvedContext,
)
from cmm.orchestration.decision_repository import (
    InMemoryOrchestrationDecisionRepository,
)
from cmm.orchestration.events import RecordingOrchestrationEventSink
from cmm.orchestration.intent import DeterministicIntentResolver
from cmm.orchestration.orchestrator import Orchestrator
from cmm.orchestration.policy import DefaultOrchestrationPolicy
from cmm.platform.configuration import CompositionConfiguration
from cmm.platform.container import ApplicationContainer
from cmm.platform.contracts import ContractMetadata, ServiceBinding, ServiceDescriptor
from cmm.platform.modules import StaticCompositionModule
from cmm.runtime.sessions import InMemorySessionStore

REQUEST_ID = "req-stream-1"
SESSION_ID = "session-1"
MESSAGE_CONTENT = "What changed in the plan?"
REQUEST_ID_HEADER = "X-Request-ID"
IDEMPOTENCY_KEY_HEADER = "Idempotency-Key"
STREAM_PATH = f"/v1/sessions/{SESSION_ID}/messages/stream"
MESSAGES_PATH = f"/v1/sessions/{SESSION_ID}/messages"

#: Raw internal defect text that must never reach a serialized stream event.
RAW_DEFECT_TEXT = (
    "Traceback (most recent call last): internal defect at "
    "/private/tmp/cmm-internal-detail with secret password token "
    "chain_of_thought reasoning_trace AKIA-EXAMPLE-SECRET-KEY"
)

#: Fragments the streaming safety contract forbids in any serialized event.
FORBIDDEN_FRAGMENTS = (
    "traceback",
    "chain_of_thought",
    "reasoning_trace",
    "secret",
    "password",
    "token",
)

#: The terminal event kinds: a stream always ends with exactly one of them.
TERMINAL_KINDS = frozenset(
    {StreamEventKind.COMPLETED, StreamEventKind.ERROR, StreamEventKind.CANCELLED}
)


# ── SSE frame parsing ────────────────────────────────────────────────────────


@dataclass(frozen=True)
class _Frame:
    """One parsed SSE frame: its wire fields and its decoded event document."""

    event: str
    frame_id: str
    document: dict[str, Any]


def _frames(body: str) -> tuple[_Frame, ...]:
    """Return the parsed frames of one stream body, in wire order."""

    parsed: list[_Frame] = []
    for block in body.split("\n\n"):
        if not block:
            continue
        fields = dict(line.split(": ", 1) for line in block.split("\n") if line)
        parsed.append(
            _Frame(
                event=fields["event"],
                frame_id=fields["id"],
                document=json.loads(fields["data"]),
            )
        )
    return tuple(parsed)


def _kinds(body: str) -> list[str]:
    """Return the event names of one stream body, in wire order."""

    return [frame.event for frame in _frames(body)]


# ── Canonical orchestrator over real Phase 11.2 components ───────────────────


class _ContextResolver:
    def resolve_base(self, request: OrchestrationRequest) -> ResolvedContext:
        return ResolvedContext(request_id=request.request_id, stage="base")

    def resolve_domain_context(
        self,
        request: OrchestrationRequest,
        base_context: ResolvedContext,
        domain_route: DomainRouteDecision,
    ) -> ResolvedContext:
        return ResolvedContext(
            request_id=request.request_id,
            stage="domain",
            domain_refs=(domain_route.primary_domain or "",),
        )


class _DomainRouter:
    def route_domain(
        self,
        request: OrchestrationRequest,
        intent: IntentResolution,
        context: ResolvedContext,
    ) -> DomainRouteDecision:
        return DomainRouteDecision(
            status="resolved",
            primary_domain="domain:general",
            permission_disposition="allow",
        )


class _AgentRouter:
    def route_agent(
        self,
        *,
        request: OrchestrationRequest,
        intent: IntentResolution,
        context: ResolvedContext,
        domain: DomainRouteDecision,
    ) -> AgentRouteDecision:
        return AgentRouteDecision(
            route=ExecutionRoute.AUTONOMOUS_AGENT, agent_id="agent-1"
        )


def _routed_result() -> OrchestrationResult:
    """Return one canonical routed decision for tests that pin the outcome."""

    return OrchestrationResult(
        request_id="req-pinned",
        status=OrchestrationStatus.ROUTED,
        intent=IntentKind.QUESTION,
        primary_domain="domain:general",
        route=ExecutionRoute.AUTONOMOUS_AGENT,
        agent_id="agent-1",
        decision_id="orchestration-decision:pinned",
        reason_codes=("POLICY_ALLOWED",),
    )


class _RecordingOrchestrator(Orchestrator):
    """A real orchestrator that records every adapted request."""

    def __init__(self) -> None:
        super().__init__(
            intent_resolver=DeterministicIntentResolver(),
            context_resolver=_ContextResolver(),  # type: ignore[arg-type]
            domain_router=_DomainRouter(),  # type: ignore[arg-type]
            agent_router=_AgentRouter(),  # type: ignore[arg-type]
            policy=DefaultOrchestrationPolicy(),
            decision_repository=InMemoryOrchestrationDecisionRepository(),
            event_sink=RecordingOrchestrationEventSink(),
        )
        self.requests: list[OrchestrationRequest] = []
        self.defect: BaseException | None = None
        self.pinned: OrchestrationResult | None = None

    def orchestrate(self, request: OrchestrationRequest) -> OrchestrationResult:
        self.requests.append(request)
        if self.defect is not None:
            raise self.defect
        if self.pinned is not None:
            return dataclass_replace(self.pinned, request_id=request.request_id)
        return super().orchestrate(request)


class _RecordingGateway(ApplicationGateway):
    """The canonical gateway plus the observation the adapter tests need."""

    def __init__(
        self,
        *,
        sessions: SessionApplicationService,
        requests: RequestApplicationService,
        capabilities: CapabilityApplicationService,
        health: HealthApplicationService,
        idempotency: InMemoryIdempotencyRepository,
    ) -> None:
        super().__init__(
            sessions=sessions,
            requests=requests,
            capabilities=capabilities,
            health=health,
            idempotency=idempotency,
        )
        self.requests: list[ApplicationRequest] = []
        self.defect: BaseException | None = None

    def handle(self, request: ApplicationRequest) -> ApplicationResponse:
        self.requests.append(request)
        if self.defect is not None:
            raise self.defect
        return super().handle(request)


def _ready_container() -> ApplicationContainer:
    service_id = "orchestration.orchestrator"
    module = StaticCompositionModule(
        "test-doubles",
        (
            ServiceBinding(
                descriptor=ServiceDescriptor(
                    service_id=service_id,
                    contract=ContractMetadata(
                        contract_name=service_id,
                        contract_version="1.0.0",
                        schema_version="1",
                        owner="cmm.test.doubles",
                    ),
                    implementation_id="tests.api.test_streaming.double",
                ),
                implementation=object(),
            ),
        ),
    )
    return ApplicationContainer.build(
        CompositionConfiguration(
            required_services=(service_id,),
            enabled_modules=("test-doubles",),
        ),
        modules=(module,),
    )


@dataclass
class _Harness:
    gateway: _RecordingGateway
    sessions: SessionApplicationService
    orchestrator: _RecordingOrchestrator
    idempotency: InMemoryIdempotencyRepository


def _harness(*, sessions: tuple[str, ...] = (SESSION_ID,)) -> _Harness:
    store = InMemorySessionStore()
    session_service = SessionApplicationService(store)
    for session_id in sessions:
        session_service.create_session(session_id)

    orchestrator = _RecordingOrchestrator()
    idempotency = InMemoryIdempotencyRepository()
    gateway = _RecordingGateway(
        sessions=session_service,
        requests=RequestApplicationService(
            sessions=session_service, orchestrator=orchestrator
        ),
        capabilities=CapabilityApplicationService(build_default_capabilities()),
        health=HealthApplicationService(_ready_container()),
        idempotency=idempotency,
    )
    return _Harness(
        gateway=gateway,
        sessions=session_service,
        orchestrator=orchestrator,
        idempotency=idempotency,
    )


def _routed_harness(**overrides: Any) -> _Harness:
    """Return a harness whose canonical pipeline answers one routed decision."""

    harness = _harness(**overrides)
    harness.orchestrator.pinned = _routed_result()
    return harness


def _client(harness: _Harness) -> TestClient:
    return TestClient(create_app(harness.gateway))


def _message_body(**overrides: Any) -> dict[str, Any]:
    body: dict[str, Any] = {"actor_id": "actor-1", "content": MESSAGE_CONTENT}
    body.update(overrides)
    return body


def _stream(harness: _Harness, **post: Any) -> Any:
    """Post one message to the v1 stream route and return the raw response."""

    return _client(harness).post(STREAM_PATH, **post)


def _successful_response(**overrides: Any) -> ApplicationResponse:
    """Return one safe successful public response carrying a routed projection."""

    document: dict[str, Any] = {
        "request_id": REQUEST_ID,
        "api_version": APPLICATION_API_VERSION,
        "status": ApplicationStatus.ROUTED,
        "data": {"session_id": SESSION_ID, "primary_domain": "domain:general"},
        "error": None,
        "metadata": {},
    }
    document.update(overrides)
    return ApplicationResponse(**document)


def _failed_response(**overrides: Any) -> ApplicationResponse:
    """Return one safe failed public response carrying a public error."""

    document: dict[str, Any] = {
        "request_id": REQUEST_ID,
        "api_version": APPLICATION_API_VERSION,
        "status": ApplicationStatus.FAILED,
        "data": None,
        "error": ApplicationError(
            code=ApplicationErrorCode.RESOURCE_NOT_FOUND,
            message="Application-owned public message",
            retryable=False,
            details={},
        ),
        "metadata": {},
    }
    document.update(overrides)
    return ApplicationResponse(**document)


def _tampered(event: ApplicationStreamEvent, **fields: Any) -> ApplicationStreamEvent:
    """Return *event* with one contract-validating field replaced.

    Only the serializer guards the frame grammar against a value the public
    contracts would have rejected, so the tests simulate such a value directly.
    """

    for name, value in fields.items():
        object.__setattr__(event, name, value)
    return event


# ── SSE serialization ────────────────────────────────────────────────────────


def test_serialize_sse_produces_the_frozen_frame_shape() -> None:
    event = ApplicationStreamEvent(
        request_id="req-1", sequence=0, kind=StreamEventKind.STARTED
    )

    assert serialize_sse(event) == (
        "event: started\n"
        "id: req-1:0\n"
        'data: {"data":null,"error":null,"kind":"started",'
        '"request_id":"req-1","sequence":0}\n'
        "\n"
    )


def test_serialize_sse_uses_the_application_contract_as_its_only_payload() -> None:
    event = ApplicationStreamEvent(
        request_id="req-1",
        sequence=1,
        kind=StreamEventKind.DATA,
        data={"session_id": SESSION_ID, "revision": 2},
    )

    frame = serialize_sse(event)
    data_line = frame.split("\n")[2].removeprefix("data: ")

    assert json.loads(data_line) == event.to_dict()
    assert json.loads(data_line)["kind"] == StreamEventKind.DATA.value


def test_serialize_sse_is_deterministic_and_key_sorted() -> None:
    event = ApplicationStreamEvent(
        request_id="req-1",
        sequence=2,
        kind=StreamEventKind.DATA,
        data={"zulu": 1, "alpha": {"delta": [2, 1], "charlie": None}},
    )

    first = serialize_sse(event)
    second = serialize_sse(event)
    data_line = first.split("\n")[2].removeprefix("data: ")

    assert first == second
    # Compact, sorted, insignificant-whitespace-free JSON is what makes the frame
    # byte-identical across processes.
    assert data_line == json.dumps(
        json.loads(data_line), sort_keys=True, separators=(",", ":")
    )
    assert ", " not in data_line
    assert ": " not in data_line


def test_serialize_sse_escapes_a_payload_instead_of_interpreting_it() -> None:
    event = ApplicationStreamEvent(
        request_id="req-1",
        sequence=1,
        kind=StreamEventKind.DATA,
        data={"note": 'first\nsecond "quoted"'},
    )

    frame = serialize_sse(event)

    # The payload can not open a second frame or a second SSE field.
    assert len(frame.split("\n")) == 5
    assert frame.endswith("\n\n")
    assert json.loads(frame.split("\n")[2].removeprefix("data: "))["data"] == {
        "note": 'first\nsecond "quoted"'
    }


def test_serialize_sse_rejects_a_non_event() -> None:
    with pytest.raises(TypeError):
        serialize_sse({"request_id": "req-1"})  # type: ignore[arg-type]


def test_serialize_sse_fails_closed_on_a_non_finite_number() -> None:
    event = _tampered(
        ApplicationStreamEvent(
            request_id="req-1", sequence=1, kind=StreamEventKind.DATA, data={}
        ),
        data={"value": float("inf")},
    )

    with pytest.raises(ValueError):
        serialize_sse(event)


def test_sse_frames_preserve_the_given_event_order() -> None:
    events = (
        ApplicationStreamEvent(
            request_id="req-1", sequence=0, kind=StreamEventKind.STARTED
        ),
        ApplicationStreamEvent(
            request_id="req-1", sequence=1, kind=StreamEventKind.COMPLETED
        ),
    )

    frames = "".join(sse_frames(events))

    assert _kinds(frames) == ["started", "completed"]


# ── Event projection ─────────────────────────────────────────────────────────


def test_successful_response_projects_the_frozen_event_sequence() -> None:
    events = events_for_response(_successful_response())

    assert [event.kind for event in events] == [
        StreamEventKind.STARTED,
        StreamEventKind.DATA,
        StreamEventKind.COMPLETED,
    ]
    assert [event.sequence for event in events] == [0, 1, 2]
    assert {event.request_id for event in events} == {REQUEST_ID}
    assert events[0].data is None
    assert events[0].error is None
    assert dict(events[1].data or {}) == {
        "session_id": SESSION_ID,
        "primary_domain": "domain:general",
    }
    assert dict(events[2].data or {}) == {"status": ApplicationStatus.ROUTED.value}
    assert all(event.error is None for event in events)
    assert events[-1].kind in TERMINAL_KINDS


def test_failed_response_projects_started_then_error() -> None:
    response = _failed_response()

    events = events_for_response(response)

    assert [event.kind for event in events] == [
        StreamEventKind.STARTED,
        StreamEventKind.ERROR,
    ]
    assert [event.sequence for event in events] == [0, 1]
    assert events[0].error is None
    assert events[1].error == response.error
    assert dict(events[1].data or {}) == {"status": ApplicationStatus.FAILED.value}
    assert events[-1].kind in TERMINAL_KINDS


def test_event_projection_never_serializes_an_internal_object_raw() -> None:
    defect = RuntimeError(RAW_DEFECT_TEXT)
    defect.__traceback__ = None

    response = failed_response(REQUEST_ID, safe_error_from_exception(defect))
    body = "".join(sse_frames(events_for_response(response)))
    document = _frames(body)[-1].document

    assert document["error"]["code"] == ApplicationErrorCode.INTERNAL_FAILURE.value
    assert document["error"]["message"] == GENERIC_FAILURE_MESSAGE
    assert document["error"]["details"] == {}
    assert "RuntimeError" not in body
    for forbidden in FORBIDDEN_FRAGMENTS:
        assert forbidden not in body.lower()


def test_events_for_response_rejects_a_non_response() -> None:
    with pytest.raises(TypeError):
        events_for_response({"request_id": REQUEST_ID})  # type: ignore[arg-type]


# ── v1 stream route ──────────────────────────────────────────────────────────


def test_stream_route_returns_the_success_event_sequence() -> None:
    harness = _routed_harness()

    response = _stream(
        harness,
        json=_message_body(),
        headers={REQUEST_ID_HEADER: REQUEST_ID, IDEMPOTENCY_KEY_HEADER: "key-1"},
    )

    assert response.status_code == 200
    assert response.headers["content-type"] == f"{SSE_MEDIA_TYPE}; charset=utf-8"
    assert response.headers[REQUEST_ID_HEADER] == REQUEST_ID

    frames = _frames(response.text)
    assert [frame.event for frame in frames] == ["started", "data", "completed"]
    assert [frame.frame_id for frame in frames] == [
        f"{REQUEST_ID}:0",
        f"{REQUEST_ID}:1",
        f"{REQUEST_ID}:2",
    ]
    assert [frame.document["request_id"] for frame in frames] == [REQUEST_ID] * 3
    assert [frame.document["sequence"] for frame in frames] == [0, 1, 2]
    assert frames[0].document["data"] is None
    assert frames[1].document["data"]["session_id"] == SESSION_ID
    assert frames[1].document["data"]["primary_domain"] == "domain:general"
    assert frames[1].document["data"]["status"] == ApplicationStatus.ROUTED.value
    assert frames[2].document["data"] == {"status": ApplicationStatus.ROUTED.value}
    assert all(frame.document["error"] is None for frame in frames)


def test_stream_route_invokes_the_application_command_exactly_once() -> None:
    harness = _routed_harness()

    _stream(
        harness,
        json=_message_body(),
        headers={REQUEST_ID_HEADER: REQUEST_ID, IDEMPOTENCY_KEY_HEADER: "key-1"},
    )

    assert len(harness.gateway.requests) == 1
    assert len(harness.orchestrator.requests) == 1
    command = harness.gateway.requests[0]
    assert isinstance(command, ApplicationCommand)
    assert command.operation is ApplicationOperation.MESSAGE_SUBMIT
    assert command.api_version == APPLICATION_API_VERSION
    assert command.request_id == REQUEST_ID
    assert command.session_id == SESSION_ID
    assert command.actor_id == "actor-1"
    assert command.idempotency_key == "key-1"
    orchestration_request = harness.orchestrator.requests[0]
    assert orchestration_request.channel is OrchestrationChannel.API
    assert orchestration_request.session_id == SESSION_ID
    assert orchestration_request.input["content"] == MESSAGE_CONTENT


def test_stream_route_builds_the_same_command_as_the_non_streaming_route() -> None:
    streamed = _routed_harness()
    answered = _routed_harness()
    request = {
        "json": _message_body(message_id=None, expected_session_revision=1),
        "headers": {REQUEST_ID_HEADER: REQUEST_ID, IDEMPOTENCY_KEY_HEADER: "key-1"},
    }

    _stream(streamed, **request)
    _client(answered).post(MESSAGES_PATH, **request)

    stream_command = streamed.gateway.requests[0]
    answer_command = answered.gateway.requests[0]
    assert isinstance(stream_command, ApplicationCommand)
    assert isinstance(answer_command, ApplicationCommand)
    # Identical canonical command semantics: the stream is a delivery adapter of
    # the same MESSAGE_SUBMIT command, not a second application operation.
    assert fingerprint_command(stream_command) == fingerprint_command(answer_command)
    assert stream_command == answer_command


def test_stream_route_replays_a_keyed_command_instead_of_re_executing_it() -> None:
    harness = _routed_harness()
    request = {
        "json": _message_body(),
        "headers": {REQUEST_ID_HEADER: REQUEST_ID, IDEMPOTENCY_KEY_HEADER: "key-1"},
    }

    first = _stream(harness, **request)
    second = _stream(harness, **request)

    assert first.text == second.text
    assert _kinds(second.text) == ["started", "data", "completed"]
    assert len(harness.gateway.requests) == 2
    assert len(harness.orchestrator.requests) == 1


def test_stream_route_emits_started_then_error_for_a_failed_response() -> None:
    harness = _routed_harness()

    response = _client(harness).post(
        "/v1/sessions/session-missing/messages/stream",
        json=_message_body(),
        headers={REQUEST_ID_HEADER: REQUEST_ID},
    )

    assert response.status_code == 200
    assert response.headers["content-type"] == f"{SSE_MEDIA_TYPE}; charset=utf-8"
    frames = _frames(response.text)
    assert [frame.event for frame in frames] == ["started", "error"]
    assert [frame.frame_id for frame in frames] == [
        f"{REQUEST_ID}:0",
        f"{REQUEST_ID}:1",
    ]
    assert frames[0].document["error"] is None
    error_document = frames[1].document
    assert (
        error_document["error"]["code"] == ApplicationErrorCode.RESOURCE_NOT_FOUND.value
    )
    assert error_document["data"] == {"status": ApplicationStatus.FAILED.value}
    assert "detail" not in error_document
    # The failed command was dispatched once and never reached orchestration.
    assert len(harness.gateway.requests) == 1
    assert harness.orchestrator.requests == []


def test_stream_route_hides_an_internal_defect() -> None:
    harness = _routed_harness()
    harness.gateway.defect = RuntimeError(RAW_DEFECT_TEXT)

    response = _stream(
        harness,
        json=_message_body(),
        headers={REQUEST_ID_HEADER: REQUEST_ID},
    )

    assert response.status_code == 200
    frames = _frames(response.text)
    assert [frame.event for frame in frames] == ["started", "error"]
    assert frames[1].document["error"]["code"] == (
        ApplicationErrorCode.INTERNAL_FAILURE.value
    )
    assert frames[1].document["error"]["message"] == GENERIC_FAILURE_MESSAGE
    assert frames[1].document["error"]["details"] == {}
    assert len(harness.gateway.requests) == 1
    for forbidden in FORBIDDEN_FRAGMENTS:
        assert forbidden not in response.text.lower()


def test_stream_route_fails_closed_before_the_application_layer_on_a_bad_body() -> None:
    harness = _routed_harness()

    response = _stream(harness, json={"actor_id": "actor-1"})

    assert response.status_code == 400
    assert response.headers["content-type"].startswith("application/json")
    body = response.json()
    assert body["error"]["code"] == ApplicationErrorCode.INVALID_REQUEST.value
    assert "detail" not in body
    assert "event:" not in response.text
    assert harness.gateway.requests == []
    assert harness.orchestrator.requests == []


def test_stream_route_reports_an_unusable_correlation_identity_safely() -> None:
    harness = _routed_harness()

    response = _stream(
        harness,
        json=_message_body(),
        headers={REQUEST_ID_HEADER: "r" * 257},
    )

    frames = _frames(response.text)
    assert [frame.event for frame in frames] == ["started", "error"]
    document = frames[1].document
    assert document["error"]["code"] == ApplicationErrorCode.INVALID_REQUEST.value
    assert document["error"]["details"] == {"reason_code": REASON_INVALID_REQUEST_ID}
    # The unusable identifier is never echoed back as the correlation identity.
    assert document["request_id"] != "r" * 257
    assert str(UUID(document["request_id"])) == document["request_id"]
    assert response.headers[REQUEST_ID_HEADER] == document["request_id"]


def test_stream_route_generates_a_correlation_identity_when_absent() -> None:
    harness = _routed_harness()

    response = _stream(harness, json=_message_body())

    frames = _frames(response.text)
    identity = frames[0].document["request_id"]
    assert str(UUID(identity)) == identity
    assert {frame.document["request_id"] for frame in frames} == {identity}
    assert response.headers[REQUEST_ID_HEADER] == identity
    assert harness.orchestrator.requests[0].request_id == identity
