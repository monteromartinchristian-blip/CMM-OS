"""Phase 11.3 — canonical application gateway tests.

``ApplicationGateway`` is the one transport-neutral public entrypoint of the
backend.  It validates the request role and version, dispatches explicitly to
the five application services, coordinates idempotency at the public command
boundary and normalizes a safe response or a safe failure.

These tests lock the boundaries that make it the *only* public entrypoint:

- constructor authority: each collaborator must be the official Phase 11.3
  concrete service, and idempotency must be the v1 in-memory repository;
- role/version validation: a query carrying a command operation, a command
  carrying a query operation, a bare ``ApplicationRequest`` or a tampered
  version fails closed as ``INVALID_REQUEST``/``UNSUPPORTED_VERSION``;
- explicit dispatch for exactly the six frozen operations, with no handler
  registry, import-by-string or dynamic resolution;
- idempotency: same key + same fingerprint replays the stored safe response,
  same key + different fingerprint is ``IDEMPOTENCY_CONFLICT``, a record exists
  only after a terminal safe response, and ``REQUEST_CANCEL`` is never recorded;
- concurrent idempotency: the complete keyed ``get -> execute -> put`` sequence
  is one atomic critical section, so two simultaneous equivalent commands enter
  the canonical owner once and a simultaneous conflicting command is rejected
  before it can execute anything;
- fail-closed failure: no exception escapes ``handle()`` for an accepted
  request, and no exception text ever reaches the public response.

The message path runs through a real Phase 11.2 ``Orchestrator`` so the adapter
is exercised as wired, not simulated.

See ``docs/superpowers/specs/2026-09-16-phase-11.3-application-backend-design.md``.
"""

from __future__ import annotations

import importlib
import json
import threading
import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field, replace
from typing import Any

import pytest

from cmm.application.capabilities import (
    CapabilityApplicationService,
    build_default_capabilities,
)
from cmm.application.contracts import (
    APPLICATION_API_VERSION,
    ApplicationCommand,
    ApplicationErrorCode,
    ApplicationOperation,
    ApplicationQuery,
    ApplicationRequest,
    ApplicationResponse,
    ApplicationStatus,
)
from cmm.application.gateway import (
    CANCELLATION_UNAVAILABLE_MESSAGE,
    ApplicationGateway,
)
from cmm.application.health import HealthApplicationService
from cmm.application.idempotency import (
    IdempotencyRecord,
    InMemoryIdempotencyRepository,
)
from cmm.application.requests import RequestApplicationService
from cmm.application.sessions import SessionApplicationService
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
    ErrorResult,
    ServiceBinding,
    ServiceDescriptor,
)
from cmm.platform.modules import StaticCompositionModule
from cmm.runtime.sessions import InMemorySessionStore

MESSAGE_CONTENT = "What changed in the plan?"

#: A raw internal defect that must never reach the public response.
RAW_DEFECT_TEXT = "internal defect at /private/tmp/cmm-internal-detail"


def _routed_result() -> OrchestrationResult:
    """Return one successful canonical result for tests that pin the outcome."""

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
    """A real orchestrator that records every adapted request.

    Subclassing keeps the canonical authority identity that the adapter
    validates while these tests observe the exact adapted request and can pin
    one internal defect or one terminal canonical result.
    """

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
            return replace(self.pinned, request_id=request.request_id)
        return super().orchestrate(request)


# ── Harness ──────────────────────────────────────────────────────────────────


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
                    implementation_id="tests.application.test_gateway.double",
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
    gateway: ApplicationGateway
    store: InMemorySessionStore
    sessions: SessionApplicationService
    orchestrator: _RecordingOrchestrator
    idempotency: InMemoryIdempotencyRepository
    container: ApplicationContainer = field(default_factory=_ready_container)

    def create_session(self, session_id: str) -> None:
        self.sessions.create_session(session_id)


def _harness(*, sessions: tuple[str, ...] = ("session-1", "session-2")) -> _Harness:
    store = InMemorySessionStore()
    session_service = SessionApplicationService(store)
    for session_id in sessions:
        session_service.create_session(session_id)

    orchestrator = _RecordingOrchestrator()
    idempotency = InMemoryIdempotencyRepository()
    container = _ready_container()
    gateway = ApplicationGateway(
        sessions=session_service,
        requests=RequestApplicationService(
            sessions=session_service, orchestrator=orchestrator
        ),
        capabilities=CapabilityApplicationService(build_default_capabilities()),
        health=HealthApplicationService(container),
        idempotency=idempotency,
    )

    return _Harness(
        gateway=gateway,
        store=store,
        sessions=session_service,
        orchestrator=orchestrator,
        idempotency=idempotency,
        container=container,
    )


# ── Public request builders ──────────────────────────────────────────────────


def _query(operation: ApplicationOperation, **overrides: Any) -> ApplicationRequest:
    fields: dict[str, Any] = {
        "request_id": "req-query",
        "api_version": APPLICATION_API_VERSION,
        "operation": operation,
    }
    fields.update(overrides)
    return ApplicationQuery(**fields)


def _command(operation: ApplicationOperation, **overrides: Any) -> ApplicationRequest:
    fields: dict[str, Any] = {
        "request_id": "req-command",
        "api_version": APPLICATION_API_VERSION,
        "operation": operation,
    }
    fields.update(overrides)
    return ApplicationCommand(**fields)


def _health_request(**overrides: Any) -> ApplicationRequest:
    return _query(ApplicationOperation.HEALTH_GET, request_id="req-health", **overrides)


def _capabilities_request(**overrides: Any) -> ApplicationRequest:
    return _query(
        ApplicationOperation.CAPABILITIES_LIST,
        request_id="req-capabilities",
        **overrides,
    )


def _session_create_request(
    session_id: str | None = None,
    *,
    request_id: str = "req-create",
    idempotency_key: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> ApplicationRequest:
    payload: dict[str, Any] = {} if session_id is None else {"session_id": session_id}
    return _command(
        ApplicationOperation.SESSION_CREATE,
        request_id=request_id,
        idempotency_key=idempotency_key,
        payload=payload,
        metadata={} if metadata is None else metadata,
    )


def _session_get_request(
    session_id: str | None, *, request_id: str = "req-get"
) -> ApplicationRequest:
    return _query(
        ApplicationOperation.SESSION_GET, request_id=request_id, session_id=session_id
    )


def _message_submit_request(
    *,
    request_id: str = "req-message",
    actor_id: str | None = "actor-1",
    session_id: str | None = "session-1",
    message_id: str | None = "message-1",
    content: str | None = MESSAGE_CONTENT,
    content_type: str | None = "text/plain",
    metadata: dict[str, Any] | None = None,
    idempotency_key: str | None = None,
    expected_session_revision: int | None = None,
) -> ApplicationRequest:
    payload: dict[str, Any] = {}
    for key, value in (
        ("message_id", message_id),
        ("content", content),
        ("content_type", content_type),
        ("metadata", metadata),
    ):
        if value is not None:
            payload[key] = value
    return _command(
        ApplicationOperation.MESSAGE_SUBMIT,
        request_id=request_id,
        actor_id=actor_id,
        session_id=session_id,
        idempotency_key=idempotency_key,
        expected_session_revision=expected_session_revision,
        payload=payload,
    )


def _cancel_request(
    *, request_id: str = "req-cancel", idempotency_key: str | None = None
) -> ApplicationRequest:
    return _command(
        ApplicationOperation.REQUEST_CANCEL,
        request_id=request_id,
        idempotency_key=idempotency_key,
    )


def _payload(response: ApplicationResponse) -> str:
    return json.dumps(response.to_dict(), sort_keys=True)


# ── Constructor authority boundary ───────────────────────────────────────────


class _DuckTypedSessions:
    def create_session(self, session_id: str) -> object:  # pragma: no cover
        raise AssertionError("a duck-typed session service must never be used")


class _DuckTypedIdempotency:
    def get(self, key: str) -> None:
        return None

    def put(self, record: object) -> None:  # pragma: no cover
        return None


def _collaborators(harness: _Harness) -> dict[str, object]:
    return {
        "sessions": harness.sessions,
        "requests": RequestApplicationService(
            sessions=harness.sessions, orchestrator=harness.orchestrator
        ),
        "capabilities": CapabilityApplicationService(build_default_capabilities()),
        "health": HealthApplicationService(_ready_container()),
        "idempotency": harness.idempotency,
    }


@pytest.mark.parametrize(
    "role",
    ["sessions", "requests", "capabilities", "health", "idempotency"],
)
@pytest.mark.parametrize("replacement", [object(), None, "collaborator"])
def test_constructor_rejects_non_official_collaborators(
    role: str, replacement: object
) -> None:
    collaborators = _collaborators(_harness())
    collaborators[role] = replacement

    with pytest.raises(TypeError):
        ApplicationGateway(**collaborators)  # type: ignore[arg-type]


def test_constructor_rejects_a_duck_typed_session_service() -> None:
    collaborators = _collaborators(_harness())
    collaborators["sessions"] = _DuckTypedSessions()

    with pytest.raises(TypeError):
        ApplicationGateway(**collaborators)  # type: ignore[arg-type]


def test_constructor_rejects_a_duck_typed_request_service() -> None:
    collaborators = _collaborators(_harness())
    collaborators["requests"] = _DuckTypedSessions()

    with pytest.raises(TypeError):
        ApplicationGateway(**collaborators)  # type: ignore[arg-type]


def test_constructor_rejects_a_duck_typed_idempotency_repository() -> None:
    """v1 idempotency is the application-owned in-memory repository only."""

    collaborators = _collaborators(_harness())
    collaborators["idempotency"] = _DuckTypedIdempotency()

    with pytest.raises(TypeError):
        ApplicationGateway(**collaborators)  # type: ignore[arg-type]


def test_collaborators_are_keyword_only() -> None:
    harness = _harness()
    collaborators = _collaborators(harness)

    with pytest.raises(TypeError):
        ApplicationGateway(  # type: ignore[misc]
            collaborators["sessions"],
            collaborators["requests"],
            collaborators["capabilities"],
            collaborators["health"],
            collaborators["idempotency"],
        )


# ── Request role and version validation ──────────────────────────────────────


@pytest.mark.parametrize(
    "operation",
    sorted(
        ApplicationOperation,
        key=lambda item: item.value,
    ),
)
def test_every_frozen_operation_is_dispatched_to_a_safe_response(
    operation: ApplicationOperation,
) -> None:
    harness = _harness()

    request: ApplicationRequest
    if operation in {ApplicationOperation.SESSION_CREATE}:
        request = _session_create_request("session-3")
    elif operation is ApplicationOperation.SESSION_GET:
        request = _session_get_request("session-1")
    elif operation is ApplicationOperation.MESSAGE_SUBMIT:
        request = _message_submit_request()
    elif operation is ApplicationOperation.REQUEST_CANCEL:
        request = _cancel_request()
    else:
        request = _query(operation)

    response = harness.gateway.handle(request)

    assert isinstance(response, ApplicationResponse)
    assert response.request_id == request.request_id
    assert response.api_version == APPLICATION_API_VERSION


def test_query_carrying_a_command_operation_fails_closed() -> None:
    harness = _harness()

    response = harness.gateway.handle(
        _query(ApplicationOperation.SESSION_CREATE, payload={"session_id": "s-1"})
    )

    assert response.status is ApplicationStatus.FAILED
    assert response.error is not None
    assert response.error.code is ApplicationErrorCode.INVALID_REQUEST
    assert harness.store.load("s-1") is None


def test_command_carrying_a_query_operation_fails_closed() -> None:
    harness = _harness()

    response = harness.gateway.handle(_command(ApplicationOperation.HEALTH_GET))

    assert response.status is ApplicationStatus.FAILED
    assert response.error is not None
    assert response.error.code is ApplicationErrorCode.INVALID_REQUEST
    assert response.data is None


def test_bare_application_request_fails_closed() -> None:
    """A request with no declared role must never be dispatched."""

    harness = _harness()

    request = ApplicationRequest(
        request_id="req-bare",
        api_version=APPLICATION_API_VERSION,
        operation=ApplicationOperation.HEALTH_GET,
    )

    response = harness.gateway.handle(request)

    assert response.status is ApplicationStatus.FAILED
    assert response.error is not None
    assert response.error.code is ApplicationErrorCode.INVALID_REQUEST


def test_unknown_api_version_fails_closed() -> None:
    """A tampered version fails closed rather than being served."""

    harness = _harness()

    @dataclass(frozen=True, slots=True)
    class _TamperedQuery(ApplicationQuery):
        def __post_init__(self) -> None:
            ApplicationRequest.__post_init__(self)
            object.__setattr__(self, "api_version", "v9")

    response = harness.gateway.handle(
        _TamperedQuery(
            request_id="req-tampered",
            api_version=APPLICATION_API_VERSION,
            operation=ApplicationOperation.HEALTH_GET,
        )
    )

    assert response.status is ApplicationStatus.FAILED
    assert response.error is not None
    assert response.error.code is ApplicationErrorCode.UNSUPPORTED_VERSION


@pytest.mark.parametrize("value", [object(), None, "health.get", 42])
def test_non_application_request_raises_type_error(value: object) -> None:
    harness = _harness()

    with pytest.raises(TypeError):
        harness.gateway.handle(value)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "accepted_request",
    [
        _session_get_request(None),
        _session_get_request("missing-session"),
        _message_submit_request(actor_id=None),
        _message_submit_request(session_id=None),
        _message_submit_request(message_id=None),
        _message_submit_request(content=None),
        _message_submit_request(content_type=123),
        _message_submit_request(metadata={"any": "value"}, session_id="missing"),
        _session_create_request(),
        _cancel_request(),
    ],
)
def test_no_exception_escapes_for_an_accepted_request(
    accepted_request: ApplicationRequest,
) -> None:
    harness = _harness()

    response = harness.gateway.handle(accepted_request)

    assert isinstance(response, ApplicationResponse)
    assert response.request_id == accepted_request.request_id


def test_dispatch_never_imports_a_handler_dynamically(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    harness = _harness()

    def _forbidden_import(name: str, *args: object, **kwargs: object) -> object:
        raise AssertionError(f"gateway dispatch must not import {name}")

    monkeypatch.setattr(importlib, "import_module", _forbidden_import)

    assert harness.gateway.handle(_health_request()).status is ApplicationStatus.SUCCESS
    assert (
        harness.gateway.handle(_capabilities_request()).status
        is ApplicationStatus.SUCCESS
    )


# ── Health and capability queries ────────────────────────────────────────────


def test_health_query_reports_safe_readiness() -> None:
    harness = _harness()

    response = harness.gateway.handle(_health_request())

    assert response.status is ApplicationStatus.SUCCESS
    assert response.error is None
    assert response.data is not None
    assert response.data["api_version"] == APPLICATION_API_VERSION
    assert response.data["platform_ready"] is True
    assert response.data["services"] == ("orchestration.orchestrator",)


def test_capabilities_query_projects_the_frozen_declarations() -> None:
    harness = _harness()

    response = harness.gateway.handle(_capabilities_request())

    assert response.status is ApplicationStatus.SUCCESS
    assert response.data is not None
    declarations = response.data["capabilities"]
    assert len(declarations) == 12
    statuses = {
        declaration["capability_id"]: declaration["status"]
        for declaration in declarations
    }
    assert statuses["request-cancellation"] == "unavailable"
    assert statuses["plugins"] == "deferred"
    assert statuses["sessions"] == "available"


# ── Session commands and queries ─────────────────────────────────────────────


def test_session_create_uses_the_payload_session_id() -> None:
    harness = _harness(sessions=())

    response = harness.gateway.handle(_session_create_request("session-9"))

    assert response.status is ApplicationStatus.SUCCESS
    assert response.data is not None
    assert response.data["session_id"] == "session-9"
    assert response.data["revision"] == 1
    assert harness.store.load("session-9") is not None


def test_session_create_generates_a_uuid4_when_the_payload_omits_it() -> None:
    harness = _harness(sessions=())

    response = harness.gateway.handle(_session_create_request())

    assert response.status is ApplicationStatus.SUCCESS
    assert response.data is not None
    session_id = response.data["session_id"]
    assert uuid.UUID(session_id).version == 4
    assert harness.store.load(session_id) is not None


def test_session_create_of_an_existing_session_is_a_conflict() -> None:
    harness = _harness()

    response = harness.gateway.handle(_session_create_request("session-1"))

    assert response.status is ApplicationStatus.FAILED
    assert response.error is not None
    assert response.error.code is ApplicationErrorCode.CONFLICT


@pytest.mark.parametrize("session_id", [123, "   ", True])
def test_session_create_rejects_a_malformed_payload_session_id(
    session_id: object,
) -> None:
    harness = _harness(sessions=())

    response = harness.gateway.handle(_session_create_request(session_id))  # type: ignore[arg-type]

    assert response.status is ApplicationStatus.FAILED
    assert response.error is not None
    assert response.error.code is ApplicationErrorCode.INVALID_REQUEST


def test_session_create_never_persists_public_metadata_into_the_session() -> None:
    harness = _harness(sessions=())

    response = harness.gateway.handle(
        _session_create_request("session-7", metadata={"channel": "api"})
    )

    assert response.status is ApplicationStatus.SUCCESS
    state = harness.store.load("session-7")
    assert state is not None
    assert dict(state.extensions) == {}
    assert state.revision == 1


def test_session_get_requires_a_request_session_id() -> None:
    harness = _harness()

    response = harness.gateway.handle(_session_get_request(None))

    assert response.status is ApplicationStatus.FAILED
    assert response.error is not None
    assert response.error.code is ApplicationErrorCode.INVALID_REQUEST


def test_session_get_projects_the_canonical_store_state() -> None:
    harness = _harness()

    response = harness.gateway.handle(_session_get_request("session-1"))

    assert response.status is ApplicationStatus.SUCCESS
    assert response.data is not None
    assert response.data["session_id"] == "session-1"
    assert response.data["revision"] == harness.store.load("session-1").revision  # type: ignore[union-attr]


def test_session_get_of_an_unknown_session_is_not_found() -> None:
    harness = _harness()

    response = harness.gateway.handle(_session_get_request("missing-session"))

    assert response.status is ApplicationStatus.FAILED
    assert response.error is not None
    assert response.error.code is ApplicationErrorCode.RESOURCE_NOT_FOUND


# ── Message commands ─────────────────────────────────────────────────────────


def test_message_submit_reaches_the_real_orchestrator() -> None:
    """The message path runs the real Phase 11.2 pipeline, unfabricated."""

    harness = _harness()

    response = harness.gateway.handle(_message_submit_request(request_id="req-m"))

    # The adapter fabricates no intent hint, so the real deterministic resolver
    # stops at clarification instead of inventing a routing decision.
    assert response.status is ApplicationStatus.NEEDS_CLARIFICATION
    assert response.error is None
    assert response.data is not None
    assert response.data["session_id"] == "session-1"
    assert response.data["intent"] == "unknown"
    assert "INTENT_UNKNOWN_NEEDS_CLARIFICATION" in response.data["reason_codes"]

    assert len(harness.orchestrator.requests) == 1
    adapted = harness.orchestrator.requests[0]
    assert adapted.request_id == "req-m"
    assert adapted.user_id == "actor-1"
    assert adapted.session_id == "session-1"
    assert adapted.channel is OrchestrationChannel.API
    assert adapted.bot_id is None
    assert adapted.intent_hint is None
    assert adapted.requested_capabilities == ()
    assert dict(adapted.context) == {}
    assert set(adapted.input) == {"message_id", "content", "content_type", "metadata"}
    assert adapted.input["message_id"] == "message-1"
    assert adapted.input["content"] == MESSAGE_CONTENT
    assert adapted.input["content_type"] == "text/plain"


def test_message_submit_projects_a_canonical_routed_decision() -> None:
    harness = _harness()
    harness.orchestrator.pinned = _routed_result()

    response = harness.gateway.handle(_message_submit_request())

    assert response.status is ApplicationStatus.ROUTED
    assert response.error is None
    assert response.data is not None
    assert response.data["primary_domain"] == "domain:general"
    assert response.data["agent_id"] == "agent-1"


def test_message_submit_maps_payload_metadata_and_command_fields() -> None:
    harness = _harness()
    harness.orchestrator.pinned = _routed_result()

    response = harness.gateway.handle(
        _message_submit_request(
            metadata={"channel": "api", "labels": ["a"]},
            idempotency_key="key-1",
            expected_session_revision=1,
            request_id="req-m",
        )
    )

    assert response.status is ApplicationStatus.ROUTED
    adapted = harness.orchestrator.requests[0]
    # The canonical contract freezes nested sequences, so labels stay immutable.
    assert adapted.input["metadata"] == {"channel": "api", "labels": ("a",)}


def test_message_submit_requires_an_actor_id() -> None:
    harness = _harness()

    response = harness.gateway.handle(_message_submit_request(actor_id=None))

    assert response.status is ApplicationStatus.FAILED
    assert response.error is not None
    assert response.error.code is ApplicationErrorCode.INVALID_REQUEST
    assert harness.orchestrator.requests == []


def test_message_submit_requires_a_session_id() -> None:
    harness = _harness()

    response = harness.gateway.handle(_message_submit_request(session_id=None))

    assert response.status is ApplicationStatus.FAILED
    assert response.error is not None
    assert response.error.code is ApplicationErrorCode.INVALID_REQUEST
    assert harness.orchestrator.requests == []


@pytest.mark.parametrize(
    "overrides",
    [
        {"message_id": None},
        {"message_id": "   "},
        {"message_id": 42},
        {"content": None},
        {"content": ""},
        {"content_type": 123},
        {"metadata": "not-a-mapping"},
    ],
)
def test_message_submit_rejects_a_malformed_payload(
    overrides: dict[str, Any],
) -> None:
    harness = _harness()

    response = harness.gateway.handle(_message_submit_request(**overrides))

    assert response.status is ApplicationStatus.FAILED
    assert response.error is not None
    assert response.error.code is ApplicationErrorCode.INVALID_REQUEST
    assert harness.orchestrator.requests == []


def test_message_submit_fails_before_orchestration_for_an_unknown_session() -> None:
    harness = _harness()

    response = harness.gateway.handle(
        _message_submit_request(session_id="missing-session")
    )

    assert response.status is ApplicationStatus.FAILED
    assert response.error is not None
    assert response.error.code is ApplicationErrorCode.RESOURCE_NOT_FOUND
    assert harness.orchestrator.requests == []


def test_message_submit_honors_the_expected_session_revision() -> None:
    harness = _harness()
    harness.orchestrator.pinned = _routed_result()

    stale = harness.gateway.handle(
        _message_submit_request(expected_session_revision=7, request_id="req-stale")
    )

    assert stale.status is ApplicationStatus.FAILED
    assert stale.error is not None
    assert stale.error.code is ApplicationErrorCode.CONCURRENCY_CONFLICT
    assert harness.orchestrator.requests == []

    fresh = harness.gateway.handle(_message_submit_request(expected_session_revision=1))

    assert fresh.status is ApplicationStatus.ROUTED


def test_message_submit_never_persists_metadata_into_the_session() -> None:
    harness = _harness()
    harness.orchestrator.pinned = _routed_result()

    response = harness.gateway.handle(
        _message_submit_request(metadata={"channel": "api"})
    )

    assert response.status is ApplicationStatus.ROUTED
    state = harness.store.load("session-1")
    assert state is not None
    assert dict(state.extensions) == {}
    assert state.revision == 1


# ── Cancellation ─────────────────────────────────────────────────────────────


def test_request_cancel_reports_the_capability_as_unavailable() -> None:
    harness = _harness()

    response = harness.gateway.handle(_cancel_request())

    assert response.status is ApplicationStatus.FAILED
    assert response.error is not None
    assert response.error.code is ApplicationErrorCode.CAPABILITY_UNAVAILABLE
    assert response.error.message == CANCELLATION_UNAVAILABLE_MESSAGE
    assert (
        CANCELLATION_UNAVAILABLE_MESSAGE
        == "Request cancellation is not available for the current execution boundary"
    )
    assert response.error.retryable is False


def test_request_cancel_consults_no_owner_and_never_orchestrates() -> None:
    harness = _harness()

    response = harness.gateway.handle(_cancel_request(request_id="unknown-request"))

    assert response.status is ApplicationStatus.FAILED
    assert harness.orchestrator.requests == []


def test_request_cancel_is_not_recorded_in_idempotency() -> None:
    harness = _harness()

    harness.gateway.handle(_cancel_request(idempotency_key="key-cancel"))

    assert harness.idempotency.get("key-cancel") is None


# ── Idempotency coordination ─────────────────────────────────────────────────


def test_same_key_and_same_command_replays_the_stored_response() -> None:
    harness = _harness(sessions=())

    first = harness.gateway.handle(
        _session_create_request(
            "session-5", request_id="req-a", idempotency_key="key-1"
        )
    )
    second = harness.gateway.handle(
        _session_create_request(
            "session-5", request_id="req-b", idempotency_key="key-1"
        )
    )

    assert first.status is ApplicationStatus.SUCCESS
    assert second == first
    assert second.request_id == "req-a"
    assert harness.idempotency.get("key-1") is not None


def test_same_key_and_same_message_command_replays_one_orchestration() -> None:
    harness = _harness()
    harness.orchestrator.pinned = _routed_result()

    first = harness.gateway.handle(
        _message_submit_request(request_id="req-a", idempotency_key="key-2")
    )
    second = harness.gateway.handle(
        _message_submit_request(request_id="req-b", idempotency_key="key-2")
    )

    assert first.status is ApplicationStatus.ROUTED
    assert second == first
    assert len(harness.orchestrator.requests) == 1


def test_same_key_with_a_different_payload_is_an_idempotency_conflict() -> None:
    harness = _harness(sessions=())

    harness.gateway.handle(
        _session_create_request(
            "session-5", request_id="req-a", idempotency_key="key-3"
        )
    )
    response = harness.gateway.handle(
        _session_create_request(
            "session-6", request_id="req-b", idempotency_key="key-3"
        )
    )

    assert response.status is ApplicationStatus.FAILED
    assert response.error is not None
    assert response.error.code is ApplicationErrorCode.IDEMPOTENCY_CONFLICT
    assert harness.store.load("session-6") is None


def test_same_key_against_a_different_session_is_an_idempotency_conflict() -> None:
    harness = _harness()

    harness.gateway.handle(
        _message_submit_request(
            session_id="session-1", request_id="req-a", idempotency_key="key-4"
        )
    )
    response = harness.gateway.handle(
        _message_submit_request(
            session_id="session-2", request_id="req-b", idempotency_key="key-4"
        )
    )

    assert response.status is ApplicationStatus.FAILED
    assert response.error is not None
    assert response.error.code is ApplicationErrorCode.IDEMPOTENCY_CONFLICT
    assert len(harness.orchestrator.requests) == 1


def test_same_key_with_a_different_operation_is_an_idempotency_conflict() -> None:
    harness = _harness(sessions=())

    harness.gateway.handle(
        _session_create_request(
            "session-5", request_id="req-a", idempotency_key="key-5"
        )
    )
    response = harness.gateway.handle(
        _message_submit_request(
            session_id="session-1", request_id="req-b", idempotency_key="key-5"
        )
    )

    assert response.status is ApplicationStatus.FAILED
    assert response.error is not None
    assert response.error.code is ApplicationErrorCode.IDEMPOTENCY_CONFLICT


def test_a_command_without_a_key_is_never_recorded() -> None:
    harness = _harness()

    harness.gateway.handle(_message_submit_request(request_id="req-a"))
    harness.gateway.handle(_message_submit_request(request_id="req-b"))

    assert len(harness.orchestrator.requests) == 2


def test_a_failure_is_recorded_only_after_a_terminal_safe_response() -> None:
    """An exception produced no response, so the key must stay unbound."""

    harness = _harness()
    harness.orchestrator.defect = ValueError(RAW_DEFECT_TEXT)

    failed = harness.gateway.handle(
        _message_submit_request(request_id="req-a", idempotency_key="key-6")
    )

    assert failed.status is ApplicationStatus.FAILED
    assert failed.error is not None
    assert failed.error.code is ApplicationErrorCode.INTERNAL_FAILURE
    assert RAW_DEFECT_TEXT not in _payload(failed)
    assert harness.idempotency.get("key-6") is None

    # The same key is free to succeed once the defect is gone: no failed
    # internal path was silently recorded as this key's result.
    harness.orchestrator.defect = None
    harness.orchestrator.pinned = _routed_result()
    recovered = harness.gateway.handle(
        _message_submit_request(request_id="req-b", idempotency_key="key-6")
    )

    assert recovered.status is ApplicationStatus.ROUTED


def test_a_rejected_command_is_not_recorded_under_its_key() -> None:
    """A raised typed failure is not a response, so the key stays unbound."""

    harness = _harness()

    first = harness.gateway.handle(
        _message_submit_request(
            session_id="missing-session",
            request_id="req-a",
            idempotency_key="key-7",
        )
    )

    assert first.status is ApplicationStatus.FAILED
    assert first.error is not None
    assert first.error.code is ApplicationErrorCode.RESOURCE_NOT_FOUND
    assert harness.idempotency.get("key-7") is None

    # The retry is dispatched again rather than replayed from an invented record.
    second = harness.gateway.handle(
        _message_submit_request(
            session_id="missing-session",
            request_id="req-b",
            idempotency_key="key-7",
        )
    )

    assert second.request_id == "req-b"
    assert second.error is not None
    assert second.error.code is ApplicationErrorCode.RESOURCE_NOT_FOUND


def test_a_terminal_pipeline_failure_is_replayed_for_the_same_key() -> None:
    """A completed dispatch is this key's result, failure included."""

    harness = _harness()
    harness.orchestrator.pinned = OrchestrationResult(
        request_id="req-a",
        status=OrchestrationStatus.FAILED,
        intent=IntentKind.UNKNOWN,
        error=ErrorResult(
            code="ORCHESTRATION_POLICY_ERROR",
            message="Orchestration policy failed closed",
            category="policy",
        ),
    )

    first = harness.gateway.handle(
        _message_submit_request(request_id="req-a", idempotency_key="key-8")
    )
    second = harness.gateway.handle(
        _message_submit_request(request_id="req-b", idempotency_key="key-8")
    )

    assert first.status is ApplicationStatus.FAILED
    assert first.error is not None
    assert first.error.code is ApplicationErrorCode.POLICY_DENIED
    assert second == first
    assert len(harness.orchestrator.requests) == 1


def test_an_internal_defect_never_leaks_internal_text() -> None:
    harness = _harness()
    harness.orchestrator.defect = RuntimeError(RAW_DEFECT_TEXT)

    response = harness.gateway.handle(_message_submit_request())

    assert response.status is ApplicationStatus.FAILED
    payload = _payload(response)
    assert RAW_DEFECT_TEXT not in payload
    assert "RuntimeError" not in payload
    assert "Traceback" not in payload


# ── Concurrent keyed commands (Independent Audit V1 — MAJOR-01) ──────────────


#: Bound on the forced lookup race.  Against a gateway without an atomic keyed
#: critical section both callers reach the lookup together, so the gate releases
#: immediately.  Against an atomic one the second caller can not reach the
#: lookup while the first is in flight, so the gate expires for the caller that
#: owns the critical section: the serialized outcome, not a defect.
_LOOKUP_GATE_TIMEOUT = 1.0

#: Bound on every worker join.  A worker that outlives the bound fails the test
#: instead of hanging the suite.
_WORKER_JOIN_TIMEOUT = 10.0


def _run_concurrently(targets: Sequence[Callable[[], Any]]) -> list[Any]:
    """Run *targets* on their own threads and return their results in order.

    Every worker is joined with a bounded timeout, a worker that is still alive
    afterwards fails the test, and a worker exception is re-raised here so a
    broken worker is never mistaken for a passing race.
    """

    results: list[Any] = [None] * len(targets)
    defects: list[BaseException] = []

    def _run(index: int, target: Callable[[], Any]) -> None:
        try:
            results[index] = target()
        except BaseException as exc:  # noqa: BLE001 - re-asserted below
            defects.append(exc)

    threads = [
        threading.Thread(
            target=_run, args=(index, target), name=f"gateway-worker-{index}"
        )
        for index, target in enumerate(targets)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=_WORKER_JOIN_TIMEOUT)

    stalled = sorted(thread.name for thread in threads if thread.is_alive())
    assert not stalled, (
        f"concurrent workers must finish within {_WORKER_JOIN_TIMEOUT}s: {stalled}"
    )
    assert not defects, f"concurrent workers raised: {defects!r}"

    return results


def _count_canonical_executions(
    monkeypatch: pytest.MonkeyPatch,
    gateway: ApplicationGateway,
    executions: list[ApplicationRequest],
) -> None:
    """Observe every entry into *gateway*'s canonical dispatch step.

    The counter wraps the gateway's own narrow dispatch step, so it counts
    canonical effects rather than public responses: a replayed or rejected keyed
    command shows up here as no additional execution at all.
    """

    canonical_dispatch = gateway._dispatch_once

    def counted(request: ApplicationRequest) -> ApplicationResponse:
        executions.append(request)
        return canonical_dispatch(request)

    monkeypatch.setattr(gateway, "_dispatch_once", counted)


def _observe_stored_records(
    monkeypatch: pytest.MonkeyPatch,
    repository: InMemoryIdempotencyRepository,
    stored: list[IdempotencyRecord],
) -> None:
    """Record every idempotency record the repository actually stores."""

    stored_put = repository.put

    def observed_put(record: IdempotencyRecord) -> None:
        stored_put(record)
        stored.append(record)

    monkeypatch.setattr(repository, "put", observed_put)


def _force_repository_lookup_race(
    monkeypatch: pytest.MonkeyPatch,
    repository: InMemoryIdempotencyRepository,
) -> None:
    """Force the interleaving Independent Audit V1 reproduced.

    Audit V1 showed that two concurrent same-key commands can both observe
    ``get(key) -> None`` before either stores its result.  This test-only gate
    reproduces exactly that window by making an absent lookup wait for the
    second caller, so both callers stand inside the window together.  The gate
    never serializes the callers itself, so it can not stand in for the atomic
    critical section under test.
    """

    barrier = threading.Barrier(2, timeout=_LOOKUP_GATE_TIMEOUT)
    stored_lookup = repository.get

    def gated_lookup(key: str) -> IdempotencyRecord | None:
        record = stored_lookup(key)
        if record is None:
            try:
                barrier.wait()
            except threading.BrokenBarrierError:
                # The atomic critical section admits one keyed caller at a time,
                # so the second party never arrives and the gate expires for the
                # caller inside the section.  That is the serialized outcome.
                pass
        return record

    monkeypatch.setattr(repository, "get", gated_lookup)


def test_concurrent_equivalent_idempotent_commands_execute_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Two simultaneous equivalent keyed commands are one application operation.

    Same key, same operation, same actor, same session, same expected revision,
    same semantic payload and only a different ``request_id``: the canonical
    owner must be entered exactly once and the second caller must replay the one
    stored safe response.
    """

    harness = _harness()
    harness.orchestrator.pinned = _routed_result()
    executions: list[ApplicationRequest] = []
    stored: list[IdempotencyRecord] = []
    _count_canonical_executions(monkeypatch, harness.gateway, executions)
    _observe_stored_records(monkeypatch, harness.idempotency, stored)
    _force_repository_lookup_race(monkeypatch, harness.idempotency)

    first, second = _run_concurrently(
        (
            lambda: harness.gateway.handle(
                _message_submit_request(request_id="req-1", idempotency_key="key-race")
            ),
            lambda: harness.gateway.handle(
                _message_submit_request(request_id="req-2", idempotency_key="key-race")
            ),
        )
    )

    # One semantic command entered the canonical owner once: the other caller
    # replayed the stored safe response instead of executing anything.
    assert len(executions) == 1, (
        "one keyed command must enter the canonical owner once, "
        f"entered {len(executions)} times"
    )
    assert len(harness.orchestrator.requests) == 1
    assert len(stored) == 1
    assert harness.idempotency.get("key-race") is stored[0]

    # Both callers observe the same one-operation result.
    assert first.status is ApplicationStatus.ROUTED
    assert second == first
    assert second.request_id == first.request_id
    assert harness.orchestrator.requests[0].request_id == first.request_id


def test_concurrent_conflicting_idempotent_commands_reject_before_second_execution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A simultaneous same-key conflicting command never enters the canonical owner.

    Same key, materially different semantic payload: at most one of the two
    commands may execute, exactly one caller is rejected as
    ``IDEMPOTENCY_CONFLICT``, and the rejected command leaves no canonical
    effect behind.
    """

    harness = _harness()
    executions: list[ApplicationRequest] = []
    stored: list[IdempotencyRecord] = []
    _count_canonical_executions(monkeypatch, harness.gateway, executions)
    _observe_stored_records(monkeypatch, harness.idempotency, stored)
    _force_repository_lookup_race(monkeypatch, harness.idempotency)

    responses = _run_concurrently(
        (
            lambda: harness.gateway.handle(
                _session_create_request(
                    "session-8", request_id="req-1", idempotency_key="key-race"
                )
            ),
            lambda: harness.gateway.handle(
                _session_create_request(
                    "session-9", request_id="req-2", idempotency_key="key-race"
                )
            ),
        )
    )

    conflicts = [
        response
        for response in responses
        if response.status is ApplicationStatus.FAILED
        and response.error is not None
        and response.error.code is ApplicationErrorCode.IDEMPOTENCY_CONFLICT
    ]
    created = [
        session_id
        for session_id in ("session-8", "session-9")
        if harness.store.load(session_id) is not None
    ]

    assert len(executions) == 1, (
        "the conflicting keyed command must not enter the canonical owner, "
        f"entered {len(executions)} times"
    )
    assert len(conflicts) == 1
    assert len(stored) == 1
    assert created == [executions[0].payload["session_id"]]


def test_a_raised_keyed_failure_releases_the_critical_section() -> None:
    """A raised keyed failure must never leave the keyed section held.

    A command that raises inside the critical section produced no response, so
    nothing is recorded for its key and the section must be released for every
    later command.  The follow-up call runs on a worker thread with a bounded
    join, so a leaked section fails this test instead of hanging the suite.
    """

    harness = _harness()
    harness.orchestrator.pinned = _routed_result()

    failed = harness.gateway.handle(
        _message_submit_request(
            session_id="missing-session", request_id="req-1", idempotency_key="key-9"
        )
    )

    assert failed.status is ApplicationStatus.FAILED
    assert failed.error is not None
    assert failed.error.code is ApplicationErrorCode.RESOURCE_NOT_FOUND
    assert harness.idempotency.get("key-9") is None

    (recovered,) = _run_concurrently(
        (
            lambda: harness.gateway.handle(
                _message_submit_request(request_id="req-2", idempotency_key="key-9")
            ),
        )
    )

    assert recovered.status is ApplicationStatus.ROUTED
