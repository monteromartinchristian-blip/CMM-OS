"""Phase 11.3 — HTTP v1 surface tests.

The tests lock three layers of the frozen v1 HTTP contract:

- the transport half: the complete error-code to HTTP status map and the safe
  failure envelope an internal defect becomes;
- the adapter half: ``create_app`` accepts only the composed application
  gateway, publishes exactly the frozen v1 route surface and reaches the
  application layer through explicit, versioned contracts;
- the client-visible half: one deterministic JSON envelope for every outcome,
  safe correlation headers, bounded input rejection and honest
  ``CAPABILITY_UNAVAILABLE`` reporting for the surfaces Phase 11.3 does not own.

The message path runs through a real Phase 11.2 ``Orchestrator``, so the adapter
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
from starlette.routing import WebSocketRoute

from cmm.api.app import create_app
from cmm.api.errors import (
    REASON_INVALID_IDEMPOTENCY_KEY,
    REASON_INVALID_REQUEST_BODY,
    REASON_INVALID_REQUEST_CONTRACT,
    REASON_INVALID_REQUEST_ID,
    http_status_for,
    invalid_request_error,
    status_code_for,
    success_status_code,
)
from cmm.api.models import response_model_from
from cmm.application import (
    APPLICATION_API_VERSION,
    CANCELLATION_UNAVAILABLE_MESSAGE,
    MAX_IDEMPOTENCY_KEY_LENGTH,
    MAX_IDENTIFIER_LENGTH,
    ApplicationCommand,
    ApplicationError,
    ApplicationErrorCode,
    ApplicationOperation,
    ApplicationQuery,
    ApplicationRequest,
    ApplicationResponse,
    ApplicationStatus,
    CapabilityApplicationService,
    InvalidApplicationRequestError,
    RequestApplicationService,
    SessionApplicationService,
    build_default_capabilities,
    failed_response,
    safe_error_from_exception,
)
from cmm.application.errors import GENERIC_FAILURE_MESSAGE
from cmm.application.gateway import ApplicationGateway
from cmm.application.health import HealthApplicationService
from cmm.application.idempotency import InMemoryIdempotencyRepository
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
from cmm.platform.contracts import (
    ContractMetadata,
    ServiceBinding,
    ServiceDescriptor,
)
from cmm.platform.modules import StaticCompositionModule
from cmm.runtime.sessions import InMemorySessionStore

REQUEST_ID = "req-http-1"
SESSION_ID = "session-1"
MESSAGE_CONTENT = "What changed in the plan?"
REQUEST_ID_HEADER = "X-Request-ID"
IDEMPOTENCY_KEY_HEADER = "Idempotency-Key"

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

#: The frozen v1 route surface; updated only when the plan freezes a new route.
FROZEN_V1_PATHS = frozenset(
    {
        "/v1/health",
        "/v1/capabilities",
        "/v1/sessions",
        "/v1/sessions/{session_id}",
        "/v1/sessions/{session_id}/messages",
        "/v1/requests/{request_id}/cancel",
    }
)

#: Framework-owned documentation routes; they are not part of the public API.
FRAMEWORK_PATHS = frozenset(
    {"/openapi.json", "/docs", "/docs/oauth2-redirect", "/redoc"}
)

#: Raw internal defect text that must never reach a client.
RAW_DEFECT_TEXT = (
    "Traceback (most recent call last): internal defect at "
    "/private/tmp/cmm-internal-detail with secret AKIA-EXAMPLE-SECRET-KEY"
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
                    implementation_id="tests.api.test_http_v1.double",
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
    store: InMemorySessionStore
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
        store=store,
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
        data={"session_id": SESSION_ID},
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
        data={"session_id": SESSION_ID},
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


# ── App factory ──────────────────────────────────────────────────────────────


def test_create_app_refuses_a_foreign_gateway() -> None:
    with pytest.raises(TypeError):
        create_app(object())  # type: ignore[arg-type]


def test_create_app_refuses_a_structurally_similar_gateway() -> None:
    class _FakeGateway:
        def handle(self, request: object) -> object:  # pragma: no cover
            raise AssertionError("a fake gateway must never serve a request")

    with pytest.raises(TypeError):
        create_app(_FakeGateway())  # type: ignore[arg-type]


def test_create_app_declares_the_versioned_public_metadata() -> None:
    app = create_app(_harness().gateway)

    assert app.title == "CMM OS Application API"
    assert app.version == "1.0.0"


def test_create_app_binds_exactly_the_composed_gateway() -> None:
    harness = _harness()

    app = create_app(harness.gateway)

    assert app.state.application_gateway is harness.gateway


def test_two_apps_never_share_a_gateway() -> None:
    first = _client(_harness(sessions=("session-a",)))
    second = _client(_harness(sessions=("session-b",)))

    assert first.get("/v1/sessions/session-a").status_code == 200
    assert first.get("/v1/sessions/session-b").status_code == 404
    assert second.get("/v1/sessions/session-b").status_code == 200
    assert second.get("/v1/sessions/session-a").status_code == 404


# ── Public route surface ─────────────────────────────────────────────────────


def test_public_route_surface_matches_the_frozen_v1_paths() -> None:
    app = create_app(_harness().gateway)

    paths = {route.path for route in app.routes}

    assert {path for path in paths if path.startswith("/v1")} == FROZEN_V1_PATHS
    assert paths - FRAMEWORK_PATHS - FROZEN_V1_PATHS == set()


def test_no_unversioned_alias_is_served() -> None:
    client = _client(_harness())

    for path in ("/health", "/capabilities", "/sessions", "/v2/health"):
        assert client.get(path).status_code == 404


def test_no_websocket_route_is_served() -> None:
    app = create_app(_harness().gateway)

    assert not any(isinstance(route, WebSocketRoute) for route in app.routes)


def test_unknown_public_path_reports_a_safe_error_envelope() -> None:
    response = _client(_harness()).get("/v1/unknown")

    assert response.status_code == 404
    body = response.json()
    assert body["api_version"] == APPLICATION_API_VERSION
    assert body["status"] == ApplicationStatus.FAILED.value
    assert body["error"]["code"] == ApplicationErrorCode.RESOURCE_NOT_FOUND.value
    assert "detail" not in body


def test_unsupported_method_reports_a_safe_error_envelope() -> None:
    response = _client(_harness()).delete("/v1/health")

    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == ApplicationErrorCode.INVALID_REQUEST.value
    assert "detail" not in body


# ── Health and capabilities ──────────────────────────────────────────────────


def test_health_reports_safe_platform_readiness() -> None:
    harness = _harness()

    response = _client(harness).get(
        "/v1/health", headers={REQUEST_ID_HEADER: REQUEST_ID}
    )

    assert response.status_code == 200
    assert response.headers[REQUEST_ID_HEADER] == REQUEST_ID
    body = response.json()
    assert body == {
        "request_id": REQUEST_ID,
        "api_version": APPLICATION_API_VERSION,
        "status": ApplicationStatus.SUCCESS.value,
        "data": {
            "status": "ok",
            "api_version": APPLICATION_API_VERSION,
            "platform_ready": True,
            "services": ["orchestration.orchestrator"],
        },
        "error": None,
        "metadata": {},
    }
    request = harness.gateway.requests[-1]
    assert isinstance(request, ApplicationQuery)
    assert request.operation is ApplicationOperation.HEALTH_GET
    assert request.api_version == APPLICATION_API_VERSION


def test_health_generates_a_correlation_identity_when_absent() -> None:
    response = _client(_harness()).get("/v1/health")

    assert response.status_code == 200
    body = response.json()
    assert str(UUID(body["request_id"])) == body["request_id"]
    assert response.headers[REQUEST_ID_HEADER] == body["request_id"]


def test_capabilities_lists_the_frozen_declarations() -> None:
    response = _client(_harness()).get("/v1/capabilities")

    assert response.status_code == 200
    capabilities = response.json()["data"]["capabilities"]
    by_id = {capability["capability_id"]: capability for capability in capabilities}
    assert [capability["capability_id"] for capability in capabilities] == sorted(by_id)
    assert by_id["health"]["status"] == "available"
    assert by_id["sessions"]["operations"] == ["sessions.create", "sessions.get"]
    assert by_id["request-cancellation"]["status"] == "unavailable"
    assert by_id["request-cancellation"]["reason_code"] == "NO_CANCELLABLE_OWNER"
    assert by_id["domains"]["status"] == "deferred"


# ── Sessions ─────────────────────────────────────────────────────────────────


def test_session_creation_returns_201_and_the_public_projection() -> None:
    response = _client(_harness()).post(
        "/v1/sessions", json={"session_id": "session-new"}
    )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == ApplicationStatus.SUCCESS.value
    assert body["error"] is None
    assert body["data"]["session_id"] == "session-new"
    assert body["data"]["revision"] == 1
    assert body["data"]["status"] == "ACTIVE"
    assert body["data"]["created_at"].endswith("+00:00")


def test_session_creation_accepts_an_absent_body() -> None:
    response = _client(_harness()).post("/v1/sessions")

    assert response.status_code == 201
    session_id = response.json()["data"]["session_id"]
    assert str(UUID(session_id)) == session_id


def test_session_creation_of_an_existing_identity_is_a_conflict() -> None:
    harness = _harness(sessions=(SESSION_ID,))

    response = _client(harness).post("/v1/sessions", json={"session_id": SESSION_ID})

    assert response.status_code == 409
    body = response.json()
    assert body["status"] == ApplicationStatus.FAILED.value
    assert body["error"]["code"] == ApplicationErrorCode.CONFLICT.value
    assert body["error"]["details"] == {"reason_code": "SESSION_ALREADY_EXISTS"}
    # The canonical session keeps its committed revision.
    committed = harness.store.load(SESSION_ID)
    assert committed is not None
    assert committed.revision == 1


def test_session_creation_rejects_an_unknown_body_field_safely() -> None:
    response = _client(_harness()).post(
        "/v1/sessions", json={"session_id": "session-new", "idempotency_key": "key-1"}
    )

    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == ApplicationErrorCode.INVALID_REQUEST.value
    assert body["error"]["message"] == (
        InvalidApplicationRequestError().to_public_error().message
    )
    assert body["error"]["details"] == {"reason_code": REASON_INVALID_REQUEST_BODY}
    assert "detail" not in body
    assert "extra_forbidden" not in json.dumps(body)


def test_session_read_returns_the_public_projection() -> None:
    response = _client(_harness()).get(f"/v1/sessions/{SESSION_ID}")

    assert response.status_code == 200
    assert response.json()["data"]["session_id"] == SESSION_ID


def test_unknown_session_is_not_found() -> None:
    response = _client(_harness()).get("/v1/sessions/session-missing")

    assert response.status_code == 404
    assert (
        response.json()["error"]["code"]
        == ApplicationErrorCode.RESOURCE_NOT_FOUND.value
    )


def test_oversized_session_identifier_fails_at_transport_parse() -> None:
    response = _client(_harness()).get(
        "/v1/sessions/" + "s" * (MAX_IDENTIFIER_LENGTH + 1)
    )

    assert response.status_code == 400
    assert (
        response.json()["error"]["code"] == ApplicationErrorCode.INVALID_REQUEST.value
    )


def test_oversized_request_identity_header_fails_closed() -> None:
    response = _client(_harness()).get(
        "/v1/health",
        headers={REQUEST_ID_HEADER: "r" * (MAX_IDENTIFIER_LENGTH + 1)},
    )

    assert response.status_code == 400
    body = response.json()
    assert body["error"]["details"] == {"reason_code": REASON_INVALID_REQUEST_ID}
    # The unusable identifier is never echoed back as the correlation identity.
    assert body["request_id"] != "r" * (MAX_IDENTIFIER_LENGTH + 1)
    assert str(UUID(body["request_id"])) == body["request_id"]
    assert response.headers[REQUEST_ID_HEADER] == body["request_id"]


# ── Messages ─────────────────────────────────────────────────────────────────


def test_message_submission_reaches_the_canonical_orchestrator_once() -> None:
    harness = _routed_harness()

    response = _client(harness).post(
        f"/v1/sessions/{SESSION_ID}/messages",
        json=_message_body(),
        headers={REQUEST_ID_HEADER: REQUEST_ID, IDEMPOTENCY_KEY_HEADER: "key-1"},
    )

    assert response.status_code == 200
    assert response.headers[REQUEST_ID_HEADER] == REQUEST_ID
    body = response.json()
    assert body["request_id"] == REQUEST_ID
    assert body["status"] == ApplicationStatus.ROUTED.value
    assert body["error"] is None
    assert body["data"]["session_id"] == SESSION_ID
    assert body["data"]["primary_domain"] == "domain:general"
    assert body["data"]["request_id"] == REQUEST_ID

    assert len(harness.orchestrator.requests) == 1
    orchestration_request = harness.orchestrator.requests[0]
    assert orchestration_request.channel is OrchestrationChannel.API
    assert orchestration_request.request_id == REQUEST_ID
    assert orchestration_request.session_id == SESSION_ID
    assert orchestration_request.user_id == "actor-1"
    assert orchestration_request.context == {}
    assert orchestration_request.requested_capabilities == ()
    assert orchestration_request.input["content"] == MESSAGE_CONTENT
    assert orchestration_request.input["content_type"] == "text/plain"
    assert orchestration_request.input["metadata"] == {}
    message_id = orchestration_request.input["message_id"]
    assert str(UUID(message_id)) == message_id


def test_message_route_builds_one_versioned_application_command() -> None:
    harness = _routed_harness()

    _client(harness).post(
        f"/v1/sessions/{SESSION_ID}/messages",
        json=_message_body(message_id="message-1", expected_session_revision=1),
        headers={REQUEST_ID_HEADER: REQUEST_ID, IDEMPOTENCY_KEY_HEADER: "key-1"},
    )

    command = harness.gateway.requests[-1]
    assert isinstance(command, ApplicationCommand)
    assert command.operation is ApplicationOperation.MESSAGE_SUBMIT
    assert command.api_version == APPLICATION_API_VERSION
    assert command.request_id == REQUEST_ID
    assert command.session_id == SESSION_ID
    assert command.actor_id == "actor-1"
    assert command.idempotency_key == "key-1"
    assert command.expected_session_revision == 1
    assert dict(command.payload) == {
        "message_id": "message-1",
        "content": MESSAGE_CONTENT,
        "content_type": "text/plain",
        "metadata": {},
    }


def test_message_route_accepts_public_metadata() -> None:
    harness = _routed_harness()

    response = _client(harness).post(
        f"/v1/sessions/{SESSION_ID}/messages",
        json=_message_body(metadata={"channel": "cli", "attempt": 2}),
    )

    assert response.status_code == 200
    assert harness.orchestrator.requests[0].input["metadata"] == {
        "channel": "cli",
        "attempt": 2,
    }


def test_message_route_generates_a_correlation_identity_when_absent() -> None:
    harness = _routed_harness()

    response = _client(harness).post(
        f"/v1/sessions/{SESSION_ID}/messages", json=_message_body()
    )

    assert response.status_code == 200
    body = response.json()
    assert str(UUID(body["request_id"])) == body["request_id"]
    assert response.headers[REQUEST_ID_HEADER] == body["request_id"]
    assert harness.orchestrator.requests[0].request_id == body["request_id"]


def test_a_blank_request_identity_header_is_treated_as_absent() -> None:
    response = _client(_routed_harness()).post(
        f"/v1/sessions/{SESSION_ID}/messages",
        json=_message_body(),
        headers={REQUEST_ID_HEADER: "   "},
    )

    assert response.status_code == 200
    body = response.json()
    assert str(UUID(body["request_id"])) == body["request_id"]


def test_repeating_a_keyed_command_replays_the_stored_safe_response() -> None:
    harness = _routed_harness()
    client = _client(harness)

    first = client.post(
        f"/v1/sessions/{SESSION_ID}/messages",
        json=_message_body(),
        headers={REQUEST_ID_HEADER: REQUEST_ID, IDEMPOTENCY_KEY_HEADER: "key-1"},
    )
    second = client.post(
        f"/v1/sessions/{SESSION_ID}/messages",
        json=_message_body(),
        headers={REQUEST_ID_HEADER: "req-http-2", IDEMPOTENCY_KEY_HEADER: "key-1"},
    )

    assert first.status_code == second.status_code == 200
    assert first.json() == second.json()
    assert first.json()["status"] == ApplicationStatus.ROUTED.value
    assert len(harness.orchestrator.requests) == 1
    # The generated message identity of a keyed command is stable, which is what
    # makes the retry canonically the same command instead of a conflict.
    generated = [
        command.payload["message_id"]
        for command in harness.gateway.requests
        if isinstance(command, ApplicationCommand)
        and command.operation is ApplicationOperation.MESSAGE_SUBMIT
    ]
    assert len(set(generated)) == 1


def test_reusing_a_key_for_a_different_command_is_a_conflict() -> None:
    harness = _routed_harness()
    client = _client(harness)

    client.post(
        f"/v1/sessions/{SESSION_ID}/messages",
        json=_message_body(),
        headers={IDEMPOTENCY_KEY_HEADER: "key-1"},
    )
    response = client.post(
        f"/v1/sessions/{SESSION_ID}/messages",
        json=_message_body(content="A different question"),
        headers={IDEMPOTENCY_KEY_HEADER: "key-1"},
    )

    assert response.status_code == 409
    assert (
        response.json()["error"]["code"]
        == ApplicationErrorCode.IDEMPOTENCY_CONFLICT.value
    )
    assert len(harness.orchestrator.requests) == 1


def test_oversized_idempotency_key_fails_closed() -> None:
    response = _client(_harness()).post(
        f"/v1/sessions/{SESSION_ID}/messages",
        json=_message_body(),
        headers={
            IDEMPOTENCY_KEY_HEADER: "k" * (MAX_IDEMPOTENCY_KEY_LENGTH + 1),
        },
    )

    assert response.status_code == 400
    assert response.json()["error"]["details"] == {
        "reason_code": REASON_INVALID_IDEMPOTENCY_KEY
    }


def test_message_to_an_unknown_session_is_not_found() -> None:
    harness = _harness()

    response = _client(harness).post(
        "/v1/sessions/session-missing/messages", json=_message_body()
    )

    assert response.status_code == 404
    assert (
        response.json()["error"]["code"]
        == ApplicationErrorCode.RESOURCE_NOT_FOUND.value
    )
    assert harness.orchestrator.requests == []


def test_stale_expected_revision_is_a_concurrency_conflict() -> None:
    response = _client(_harness()).post(
        f"/v1/sessions/{SESSION_ID}/messages",
        json=_message_body(expected_session_revision=7),
    )

    assert response.status_code == 409
    assert (
        response.json()["error"]["code"]
        == ApplicationErrorCode.CONCURRENCY_CONFLICT.value
    )


def test_empty_message_content_fails_at_transport_parse() -> None:
    response = _client(_harness()).post(
        f"/v1/sessions/{SESSION_ID}/messages", json=_message_body(content="")
    )

    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == ApplicationErrorCode.INVALID_REQUEST.value
    assert body["error"]["details"] == {"reason_code": REASON_INVALID_REQUEST_BODY}


def test_secret_shaped_metadata_is_rejected_as_an_invalid_request() -> None:
    response = _client(_harness()).post(
        f"/v1/sessions/{SESSION_ID}/messages",
        json=_message_body(metadata={"api_key": "AKIA-EXAMPLE-SECRET-KEY"}),
    )

    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == ApplicationErrorCode.INVALID_REQUEST.value
    assert body["error"]["details"] == {"reason_code": REASON_INVALID_REQUEST_CONTRACT}
    assert "AKIA-EXAMPLE-SECRET-KEY" not in json.dumps(body)


def test_an_internal_defect_becomes_a_safe_500_envelope() -> None:
    harness = _harness()
    harness.orchestrator.defect = RuntimeError(RAW_DEFECT_TEXT)

    response = _client(harness).post(
        f"/v1/sessions/{SESSION_ID}/messages", json=_message_body()
    )

    assert response.status_code == 500
    body = response.json()
    assert body["status"] == ApplicationStatus.FAILED.value
    assert body["error"]["code"] == ApplicationErrorCode.INTERNAL_FAILURE.value
    assert body["error"]["message"] == GENERIC_FAILURE_MESSAGE
    assert body["error"]["details"] == {}
    for forbidden in (
        "Traceback",
        "cmm-internal-detail",
        "AKIA-EXAMPLE-SECRET-KEY",
    ):
        assert forbidden not in json.dumps(body)


def test_an_adapter_defect_fails_closed_with_a_safe_envelope() -> None:
    harness = _harness()
    harness.gateway.defect = RuntimeError(RAW_DEFECT_TEXT)

    response = _client(harness).get("/v1/health")

    assert response.status_code == 500
    body = response.json()
    assert body["error"]["code"] == ApplicationErrorCode.INTERNAL_FAILURE.value
    assert body["error"]["message"] == GENERIC_FAILURE_MESSAGE
    assert "cmm-internal-detail" not in json.dumps(body)


# ── Cancellation ─────────────────────────────────────────────────────────────


def test_cancellation_reports_capability_unavailable() -> None:
    harness = _harness()

    response = _client(harness).post(
        "/v1/requests/req-target/cancel", headers={REQUEST_ID_HEADER: REQUEST_ID}
    )

    assert response.status_code == 503
    body = response.json()
    assert body["request_id"] == REQUEST_ID
    assert body["error"]["code"] == ApplicationErrorCode.CAPABILITY_UNAVAILABLE.value
    assert body["error"]["message"] == CANCELLATION_UNAVAILABLE_MESSAGE
    assert harness.orchestrator.requests == []


def test_cancellation_builds_a_versioned_command_for_the_target() -> None:
    harness = _harness()

    _client(harness).post("/v1/requests/req-target/cancel")

    command = harness.gateway.requests[-1]
    assert isinstance(command, ApplicationCommand)
    assert command.operation is ApplicationOperation.REQUEST_CANCEL
    assert command.api_version == APPLICATION_API_VERSION
    assert dict(command.payload) == {"target_request_id": "req-target"}
    assert command.idempotency_key is None
