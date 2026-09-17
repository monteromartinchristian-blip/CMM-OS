"""Phase 11.3 — request application service tests.

``RequestApplicationService`` is the application-to-orchestration adapter: a
public :class:`ApplicationMessage` becomes a canonical ``OrchestrationRequest``
with channel ``API``, and the canonical ``OrchestrationResult`` becomes a safe
public :class:`ApplicationResponse`.

These tests lock the four things that matter for `DP-103`:

- the constructor authority boundary (only a canonical ``SessionApplicationService``
  and the concrete canonical ``Orchestrator`` are accepted);
- session preconditions evaluated *before* orchestration, so a stale or absent
  session never reaches the canonical pipeline;
- the exact adapted request: no fabricated ``bot_id``, no fabricated
  ``intent_hint``, no requested capabilities and no raw context;
- a conservative result projection: only safe categorical fields, no internal
  request/context objects, no hidden reasoning, and no internal failure text.

No downstream execution is introduced or implied: a `ROUTED` result reports the
canonical decision and nothing more.

See ``docs/superpowers/specs/2026-09-16-phase-11.3-application-backend-design.md``.
"""

from __future__ import annotations

import json
from collections.abc import Mapping

import pytest

from cmm.application.contracts import (
    APPLICATION_API_VERSION,
    ApplicationChannel,
    ApplicationErrorCode,
    ApplicationMessage,
    ApplicationStatus,
)
from cmm.application.errors import (
    ApplicationResourceNotFoundError,
    ApplicationServiceError,
    ConcurrencyConflictError,
    InternalApplicationError,
    InvalidApplicationRequestError,
    PolicyDeniedApplicationError,
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
from cmm.platform.contracts import ErrorResult
from cmm.runtime.sessions import InMemorySessionStore

#: The complete public projection of one orchestration result.
PROJECTED_FIELDS = (
    "session_id",
    "request_id",
    "status",
    "intent",
    "primary_domain",
    "supporting_domains",
    "profile_id",
    "route",
    "agent_id",
    "workflow_id",
    "approval_refs",
    "decision_id",
    "trace_refs",
    "reason_codes",
)


# ── Orchestrator collaborators ───────────────────────────────────────────────


class _RecordingOrchestrator(Orchestrator):
    """A real ``Orchestrator`` whose terminal outcome the test pins.

    Subclassing keeps the canonical authority identity — which is exactly what
    the service must validate — while these unit tests control one result.
    """

    def __init__(
        self,
        result: OrchestrationResult | None = None,
        *,
        error: BaseException | None = None,
    ) -> None:
        self.requests: list[OrchestrationRequest] = []
        self._result = result
        self._error = error

    def orchestrate(self, request: OrchestrationRequest) -> OrchestrationResult:
        self.requests.append(request)
        if self._error is not None:
            raise self._error
        assert self._result is not None
        return self._result


class _IntentResolver:
    def __init__(self, intent: IntentKind = IntentKind.QUESTION) -> None:
        self._intent = intent

    def resolve(self, request: OrchestrationRequest) -> IntentResolution:
        return IntentResolution(
            intent=self._intent,
            needs_clarification=self._intent is IntentKind.UNKNOWN,
            source_kind="structured_input",
        )


class _ContextResolver:
    def __init__(self, *, missing: tuple[str, ...] = ()) -> None:
        self._missing = missing

    def resolve_base(self, request: OrchestrationRequest) -> ResolvedContext:
        return ResolvedContext(
            request_id=request.request_id, stage="base", missing_refs=self._missing
        )

    def resolve_domain_context(
        self,
        request: OrchestrationRequest,
        base_context: ResolvedContext,
        domain_route: DomainRouteDecision,
    ) -> ResolvedContext:
        return ResolvedContext(
            request_id=request.request_id,
            stage="domain",
            missing_refs=base_context.missing_refs,
            domain_refs=(domain_route.primary_domain or "",),
        )


class _DomainRouter:
    def __init__(self, decision: DomainRouteDecision) -> None:
        self._decision = decision

    def route_domain(
        self,
        request: OrchestrationRequest,
        intent: IntentResolution,
        context: ResolvedContext,
    ) -> DomainRouteDecision:
        return self._decision


class _AgentRouter:
    def __init__(self, decision: AgentRouteDecision) -> None:
        self._decision = decision

    def route_agent(
        self,
        *,
        request: OrchestrationRequest,
        intent: IntentResolution,
        context: ResolvedContext,
        domain: DomainRouteDecision,
    ) -> AgentRouteDecision:
        return self._decision


def _real_orchestrator(
    *,
    intent_resolver: object | None = None,
    domain: DomainRouteDecision | None = None,
    route: AgentRouteDecision | None = None,
) -> Orchestrator:
    """Build a real canonical orchestrator over real Phase 11.2 components."""

    return Orchestrator(
        intent_resolver=(
            DeterministicIntentResolver()
            if intent_resolver is None
            else intent_resolver
        ),  # type: ignore[arg-type]
        context_resolver=_ContextResolver(),  # type: ignore[arg-type]
        domain_router=_DomainRouter(  # type: ignore[arg-type]
            domain
            if domain is not None
            else DomainRouteDecision(
                status="resolved",
                primary_domain="domain:general",
                permission_disposition="allow",
            )
        ),
        agent_router=_AgentRouter(  # type: ignore[arg-type]
            route
            if route is not None
            else AgentRouteDecision(
                route=ExecutionRoute.AUTONOMOUS_AGENT, agent_id="agent-1"
            )
        ),
        policy=DefaultOrchestrationPolicy(),
        decision_repository=InMemoryOrchestrationDecisionRepository(),
        event_sink=RecordingOrchestrationEventSink(),
    )


# ── Fixtures and builders ────────────────────────────────────────────────────


def _message(**overrides: object) -> ApplicationMessage:
    fields: dict[str, object] = {
        "message_id": "message-1",
        "session_id": "session-1",
        "actor_id": "actor-1",
        "content": "What changed in the plan?",
        "content_type": "text/plain",
        "metadata": {"channel": "api", "labels": ["a", "b"]},
    }
    fields.update(overrides)
    return ApplicationMessage(**fields)  # type: ignore[arg-type]


def _result(**overrides: object) -> OrchestrationResult:
    fields: dict[str, object] = {
        "request_id": "req-1",
        "status": OrchestrationStatus.ROUTED,
        "intent": IntentKind.QUESTION,
        "primary_domain": "domain:general",
        "supporting_domains": ("domain:health",),
        "profile_id": "profile-1",
        "route": ExecutionRoute.AUTONOMOUS_AGENT,
        "agent_id": "agent-1",
        "workflow_id": "workflow-1",
        "approval_refs": (),
        "decision_id": "orchestration-decision:req-1",
        "trace_refs": ("domain-resolution:1",),
        "reason_codes": ("POLICY_ALLOWED",),
        "error": None,
    }
    fields.update(overrides)
    return OrchestrationResult(**fields)  # type: ignore[arg-type]


def _failure(
    *,
    code: str = "ORCHESTRATION_POLICY_ERROR",
    category: str = "policy",
    message: str = "Orchestration policy failed closed",
    details: Mapping[str, str] | None = None,
) -> ErrorResult:
    return ErrorResult(
        code=code, message=message, category=category, details=dict(details or {})
    )


def _fixture(
    *,
    result: OrchestrationResult | None = None,
    error: BaseException | None = None,
    create_session: bool = True,
) -> tuple[
    RequestApplicationService, _RecordingOrchestrator, SessionApplicationService
]:
    sessions = SessionApplicationService(InMemorySessionStore())
    if create_session:
        sessions.create_session("session-1")
    probe = _RecordingOrchestrator(_result() if result is None else result, error=error)
    service = RequestApplicationService(sessions=sessions, orchestrator=probe)
    return service, probe, sessions


# ── Constructor authority boundary ───────────────────────────────────────────


def test_a_real_orchestrator_is_accepted() -> None:
    service, _probe, _sessions = _fixture()

    response = service.submit_message(request_id="req-1", message=_message())

    assert response.status is ApplicationStatus.ROUTED


def test_a_fake_orchestrator_is_rejected() -> None:
    sessions = SessionApplicationService(InMemorySessionStore())

    class _FakeOrchestrator:
        def orchestrate(self, request: object) -> object:  # pragma: no cover
            raise AssertionError("a fake orchestrator must never be used")

    with pytest.raises(TypeError):
        RequestApplicationService(
            sessions=sessions,
            orchestrator=_FakeOrchestrator(),  # type: ignore[arg-type]
        )


@pytest.mark.parametrize("orchestrator", [None, object(), "orchestrator", _message()])
def test_non_orchestrator_collaborators_are_rejected(orchestrator: object) -> None:
    sessions = SessionApplicationService(InMemorySessionStore())

    with pytest.raises(TypeError):
        RequestApplicationService(
            sessions=sessions,
            orchestrator=orchestrator,  # type: ignore[arg-type]
        )


def test_a_fake_session_service_is_rejected() -> None:
    class _FakeSessions:
        def require_revision(self, session_id: str, expected_revision: object) -> None:
            return None

    with pytest.raises(TypeError):
        RequestApplicationService(
            sessions=_FakeSessions(),  # type: ignore[arg-type]
            orchestrator=_RecordingOrchestrator(_result()),
        )


def test_collaborators_are_keyword_only() -> None:
    sessions = SessionApplicationService(InMemorySessionStore())

    with pytest.raises(TypeError):
        RequestApplicationService(  # type: ignore[misc]
            sessions, _RecordingOrchestrator(_result())
        )


def test_service_exposes_only_the_message_command() -> None:
    service, _probe, _sessions = _fixture()

    assert callable(service.submit_message)
    assert not hasattr(service, "handle")
    assert not hasattr(service, "orchestrate")


# ── Session precondition before orchestration ────────────────────────────────


def test_absent_session_fails_before_orchestration() -> None:
    service, probe, _sessions = _fixture()

    with pytest.raises(ApplicationResourceNotFoundError):
        service.submit_message(
            request_id="req-1", message=_message(session_id="session-absent")
        )

    assert probe.requests == []


def test_stale_expected_revision_fails_before_orchestration() -> None:
    service, probe, _sessions = _fixture()

    with pytest.raises(ConcurrencyConflictError):
        service.submit_message(
            request_id="req-1",
            message=_message(expected_session_revision=0),
        )

    assert probe.requests == []


def test_matching_expected_revision_reaches_the_orchestrator() -> None:
    service, probe, _sessions = _fixture()

    response = service.submit_message(
        request_id="req-1", message=_message(expected_session_revision=1)
    )

    assert response.status is ApplicationStatus.ROUTED
    assert len(probe.requests) == 1


def test_absent_expected_revision_reaches_the_orchestrator() -> None:
    service, probe, _sessions = _fixture()

    service.submit_message(request_id="req-1", message=_message())

    assert len(probe.requests) == 1


def test_precondition_reads_the_current_canonical_revision() -> None:
    service, probe, sessions = _fixture()
    session = sessions.get_session("session-1")
    assert session.revision == 1

    with pytest.raises(ConcurrencyConflictError):
        service.submit_message(
            request_id="req-1", message=_message(expected_session_revision=2)
        )

    assert probe.requests == []


@pytest.mark.parametrize("request_id", ["", "   ", None, 1])
def test_invalid_request_identity_fails_before_orchestration(
    request_id: object,
) -> None:
    service, probe, _sessions = _fixture()

    with pytest.raises(InvalidApplicationRequestError):
        service.submit_message(request_id=request_id, message=_message())  # type: ignore[arg-type]

    assert probe.requests == []


def test_oversized_request_identity_is_rejected() -> None:
    service, probe, _sessions = _fixture()

    with pytest.raises(InvalidApplicationRequestError):
        service.submit_message(request_id="r" * 300, message=_message())

    assert probe.requests == []


def test_a_foreign_message_value_is_rejected() -> None:
    service, probe, _sessions = _fixture()

    with pytest.raises(TypeError):
        service.submit_message(
            request_id="req-1",
            message={"content": "hello"},  # type: ignore[arg-type]
        )

    assert probe.requests == []


# ── Canonical request adaptation ─────────────────────────────────────────────


def test_the_adapted_orchestration_request_is_canonical() -> None:
    service, probe, _sessions = _fixture()

    service.submit_message(request_id="req-1", message=_message())

    assert len(probe.requests) == 1
    adapted = probe.requests[0]
    assert isinstance(adapted, OrchestrationRequest)
    assert adapted.request_id == "req-1"
    assert adapted.user_id == "actor-1"
    assert adapted.channel is OrchestrationChannel.API
    assert adapted.session_id == "session-1"
    assert dict(adapted.context) == {}
    assert adapted.requested_capabilities == ()


def test_the_adapted_request_fabricates_no_authority() -> None:
    """No bot identity, no intent hint and no requested capability is invented."""

    service, probe, _sessions = _fixture()

    service.submit_message(request_id="req-1", message=_message())

    adapted = probe.requests[0]
    assert adapted.bot_id is None
    assert adapted.intent_hint is None
    assert adapted.requested_capabilities == ()


def test_the_adapted_request_input_is_the_safe_message_projection() -> None:
    service, probe, _sessions = _fixture()

    service.submit_message(request_id="req-1", message=_message())

    assert probe.requests[0].to_dict()["input"] == {
        "message_id": "message-1",
        "content": "What changed in the plan?",
        "content_type": "text/plain",
        "metadata": {"channel": "api", "labels": ["a", "b"]},
    }


def test_the_adapted_request_invents_no_metadata() -> None:
    service, probe, _sessions = _fixture()

    service.submit_message(
        request_id="req-1", message=_message(content_type="text/plain", metadata={})
    )

    assert probe.requests[0].to_dict()["input"]["metadata"] == {}


def test_adaptation_never_shares_mutable_metadata_with_the_caller() -> None:
    metadata: dict[str, object] = {"labels": ["a"]}
    message = _message(metadata=metadata)
    service, probe, _sessions = _fixture()

    metadata["labels"] = ["mutated"]
    service.submit_message(request_id="req-1", message=message)

    assert probe.requests[0].to_dict()["input"]["metadata"] == {"labels": ["a"]}


def test_the_adapted_request_carries_no_raw_context_or_permissions() -> None:
    service, probe, _sessions = _fixture()

    service.submit_message(request_id="req-1", message=_message())

    to_dict = probe.requests[0].to_dict()
    assert to_dict["context"] == {}
    assert set(to_dict["input"]) == {
        "message_id",
        "content",
        "content_type",
        "metadata",
    }


def test_every_submission_adapts_its_own_request() -> None:
    first_service, first_probe, _sessions = _fixture()
    second_service, second_probe, _sessions = _fixture(
        result=_result(request_id="req-2")
    )

    first_service.submit_message(request_id="req-1", message=_message())
    second_service.submit_message(
        request_id="req-2", message=_message(message_id="message-2")
    )

    assert [request.request_id for request in first_probe.requests] == ["req-1"]
    assert [request.request_id for request in second_probe.requests] == ["req-2"]
    assert first_probe.requests[0].to_dict()["input"]["message_id"] == "message-1"
    assert second_probe.requests[0].to_dict()["input"]["message_id"] == "message-2"


# ── Channel adaptation ───────────────────────────────────────────────────────


def test_the_default_channel_still_maps_to_orchestration_api() -> None:
    """A caller that declares no channel keeps the closed Phase 11.3 behavior."""

    service, probe, _sessions = _fixture()

    service.submit_message(request_id="req-1", message=_message())

    assert len(probe.requests) == 1
    assert probe.requests[-1].channel is OrchestrationChannel.API


@pytest.mark.parametrize(
    ("channel", "mapped"),
    [
        (ApplicationChannel.API, OrchestrationChannel.API),
        (ApplicationChannel.CLI, OrchestrationChannel.CLI),
    ],
)
def test_api_and_cli_channels_still_map_exactly(
    channel: ApplicationChannel, mapped: OrchestrationChannel
) -> None:
    service, probe, _sessions = _fixture()

    service.submit_message(request_id="req-1", message=_message(), channel=channel)

    assert probe.requests[-1].channel is mapped


def test_conversation_channel_reaches_the_orchestrator() -> None:
    """The Phase 11.5 seam delivers the new origin to the canonical pipeline."""

    service, probe, _sessions = _fixture()

    response = service.submit_message(
        request_id="req-1",
        message=_message(),
        channel=ApplicationChannel.CONVERSATION,
    )

    assert response.status is ApplicationStatus.ROUTED
    assert probe.requests[-1].channel is OrchestrationChannel.CONVERSATION


# ── Result projection ────────────────────────────────────────────────────────


def test_routed_result_projects_the_safe_field_set() -> None:
    service, _probe, _sessions = _fixture()

    response = service.submit_message(request_id="req-1", message=_message())

    assert response.request_id == "req-1"
    assert response.api_version == APPLICATION_API_VERSION
    assert response.status is ApplicationStatus.ROUTED
    assert response.error is None
    # ``data`` is a frozen public mapping: sequences are immutable tuples, and
    # ``to_dict`` renders them as JSON lists.
    assert dict(response.data or {}) == {
        "session_id": "session-1",
        "request_id": "req-1",
        "status": "routed",
        "intent": "question",
        "primary_domain": "domain:general",
        "supporting_domains": ("domain:health",),
        "profile_id": "profile-1",
        "route": "autonomous_agent",
        "agent_id": "agent-1",
        "workflow_id": "workflow-1",
        "approval_refs": (),
        "decision_id": "orchestration-decision:req-1",
        "trace_refs": ("domain-resolution:1",),
        "reason_codes": ("POLICY_ALLOWED",),
    }
    assert response.to_dict()["data"] == {
        "session_id": "session-1",
        "request_id": "req-1",
        "status": "routed",
        "intent": "question",
        "primary_domain": "domain:general",
        "supporting_domains": ["domain:health"],
        "profile_id": "profile-1",
        "route": "autonomous_agent",
        "agent_id": "agent-1",
        "workflow_id": "workflow-1",
        "approval_refs": [],
        "decision_id": "orchestration-decision:req-1",
        "trace_refs": ["domain-resolution:1"],
        "reason_codes": ["POLICY_ALLOWED"],
    }


def test_the_projection_field_set_is_frozen() -> None:
    """Only the approved safe fields are projected; nothing internal is added."""

    service, _probe, _sessions = _fixture()

    response = service.submit_message(request_id="req-1", message=_message())

    assert response.data is not None
    assert set(response.data) == set(PROJECTED_FIELDS)


def test_the_projection_has_no_downstream_execution_surface() -> None:
    service, _probe, _sessions = _fixture()

    response = service.submit_message(request_id="req-1", message=_message())

    assert response.data is not None
    for forbidden in ("output", "result", "events", "execution", "memory"):
        assert forbidden not in response.data


def test_the_projection_serializes_without_internal_objects() -> None:
    service, _probe, _sessions = _fixture()

    response = service.submit_message(request_id="req-1", message=_message())

    rendered = json.dumps(response.to_dict())
    assert "OrchestrationResult" not in rendered
    assert "reasoning" not in rendered
    assert "mappingproxy" not in rendered


def test_the_projection_reports_the_canonical_session() -> None:
    service, _probe, _sessions = _fixture()

    response = service.submit_message(request_id="req-1", message=_message())

    assert response.data is not None
    assert response.data["session_id"] == "session-1"


@pytest.mark.parametrize(
    ("orchestration_status", "application_status"),
    [
        (OrchestrationStatus.ROUTED, ApplicationStatus.ROUTED),
        (
            OrchestrationStatus.NEEDS_CLARIFICATION,
            ApplicationStatus.NEEDS_CLARIFICATION,
        ),
        (OrchestrationStatus.BLOCKED, ApplicationStatus.BLOCKED),
        (OrchestrationStatus.ESCALATED, ApplicationStatus.ESCALATED),
        (OrchestrationStatus.CANCELLED, ApplicationStatus.CANCELLED),
        (OrchestrationStatus.FAILED, ApplicationStatus.FAILED),
    ],
)
def test_every_orchestration_status_maps_to_an_application_status(
    orchestration_status: OrchestrationStatus,
    application_status: ApplicationStatus,
) -> None:
    result = _result(
        status=orchestration_status,
        error=(
            _failure() if orchestration_status is OrchestrationStatus.FAILED else None
        ),
    )
    service, _probe, _sessions = _fixture(result=result)

    response = service.submit_message(request_id="req-1", message=_message())

    assert response.status is application_status


@pytest.mark.parametrize(
    "status",
    [
        OrchestrationStatus.NEEDS_CLARIFICATION,
        OrchestrationStatus.ESCALATED,
        OrchestrationStatus.CANCELLED,
    ],
)
def test_non_failure_terminal_statuses_carry_no_error(
    status: OrchestrationStatus,
) -> None:
    service, _probe, _sessions = _fixture(result=_result(status=status))

    response = service.submit_message(request_id="req-1", message=_message())

    assert response.status is ApplicationStatus(status.value)
    assert response.error is None
    assert response.data is not None


def test_approval_references_are_projected_as_safe_references() -> None:
    result = _result(
        status=OrchestrationStatus.ROUTED,
        approval_refs=("requirement-1",),
        reason_codes=("POLICY_APPROVAL_REQUIRED",),
    )
    service, _probe, _sessions = _fixture(result=result)

    response = service.submit_message(request_id="req-1", message=_message())

    assert response.status is ApplicationStatus.ROUTED
    assert response.data is not None
    assert response.data["approval_refs"] == ("requirement-1",)
    assert response.to_dict()["data"]["approval_refs"] == ["requirement-1"]  # type: ignore[index]
    assert response.error is None


# ── Orchestration failure mapping ────────────────────────────────────────────


@pytest.mark.parametrize(
    ("category", "expected_code"),
    [
        ("policy", ApplicationErrorCode.POLICY_DENIED),
        ("Policy", ApplicationErrorCode.POLICY_DENIED),
        ("policy ", ApplicationErrorCode.POLICY_DENIED),
        ("approval", ApplicationErrorCode.APPROVAL_REQUIRED),
        ("cancellation", ApplicationErrorCode.CANCELLED),
        ("persistence", ApplicationErrorCode.CONFLICT),
        ("intent", ApplicationErrorCode.INTERNAL_FAILURE),
        ("context", ApplicationErrorCode.INTERNAL_FAILURE),
        ("domain", ApplicationErrorCode.INTERNAL_FAILURE),
        ("agent", ApplicationErrorCode.INTERNAL_FAILURE),
        ("orchestration", ApplicationErrorCode.INTERNAL_FAILURE),
        ("unknown-category", ApplicationErrorCode.INTERNAL_FAILURE),
    ],
)
def test_orchestration_failure_categories_map_conservatively(
    category: str, expected_code: ApplicationErrorCode
) -> None:
    service, _probe, _sessions = _fixture(
        result=_result(
            status=OrchestrationStatus.FAILED, error=_failure(category=category)
        )
    )

    response = service.submit_message(request_id="req-1", message=_message())

    assert response.status is ApplicationStatus.FAILED
    assert response.error is not None
    assert response.error.code is expected_code
    assert response.error.message.strip()
    assert response.data is None


def test_failed_result_without_a_canonical_error_fails_closed() -> None:
    service, _probe, _sessions = _fixture(
        result=_result(status=OrchestrationStatus.FAILED, error=None)
    )

    response = service.submit_message(request_id="req-1", message=_message())

    assert response.error is not None
    assert response.error.code is ApplicationErrorCode.INTERNAL_FAILURE
    assert response.error.message == "Application request failed closed"


def test_internal_failure_text_is_never_projected() -> None:
    service, _probe, _sessions = _fixture(
        result=_result(
            status=OrchestrationStatus.FAILED,
            reason_codes=("ORCHESTRATION_INTERNAL_FAILURE",),
            error=_failure(
                code="ORCHESTRATION_INTERNAL_FAILURE",
                category="orchestration",
                message="/Users/chris/token=secret failed",
                details={"session_id": "/Users/chris/CMM OS"},
            ),
        )
    )

    response = service.submit_message(request_id="req-1", message=_message())

    rendered = json.dumps(response.to_dict())
    assert response.error is not None
    assert response.error.code is ApplicationErrorCode.INTERNAL_FAILURE
    assert "secret" not in rendered
    assert "/Users/" not in rendered
    assert "token" not in rendered
    assert dict(response.error.details) == {}


def test_policy_denial_exposes_only_the_application_message() -> None:
    service, _probe, _sessions = _fixture(
        result=_result(
            status=OrchestrationStatus.FAILED,
            error=_failure(
                category="policy",
                message="canonical policy internals: deny-list-v3",
            ),
        )
    )

    response = service.submit_message(request_id="req-1", message=_message())

    assert response.error is not None
    assert response.error.code is ApplicationErrorCode.POLICY_DENIED
    assert response.error.message == PolicyDeniedApplicationError().safe_message
    assert "deny-list-v3" not in json.dumps(response.to_dict())


def test_blocked_result_synthesizes_a_policy_denied_error() -> None:
    service, _probe, _sessions = _fixture(
        result=_result(
            status=OrchestrationStatus.BLOCKED,
            reason_codes=("POLICY_CANONICAL_DENY",),
        )
    )

    response = service.submit_message(request_id="req-1", message=_message())

    assert response.status is ApplicationStatus.BLOCKED
    assert response.error is not None
    assert response.error.code is ApplicationErrorCode.POLICY_DENIED
    assert response.error.retryable is False
    assert response.data is not None
    assert response.data["reason_codes"] == ("POLICY_CANONICAL_DENY",)


def test_blocked_result_with_a_canonical_policy_error_uses_that_mapping() -> None:
    service, _probe, _sessions = _fixture(
        result=_result(
            status=OrchestrationStatus.BLOCKED,
            error=_failure(category="policy", code="DOMAIN_ROUTING_ERROR"),
        )
    )

    response = service.submit_message(request_id="req-1", message=_message())

    assert response.error is not None
    assert response.error.code is ApplicationErrorCode.POLICY_DENIED


def test_unexpected_orchestrator_failure_becomes_a_safe_internal_error() -> None:
    service, _probe, _sessions = _fixture(
        error=RuntimeError("/Users/chris/token=secret")
    )

    with pytest.raises(ApplicationServiceError) as raised:
        service.submit_message(request_id="req-1", message=_message())

    assert isinstance(raised.value, InternalApplicationError)
    assert raised.value.code is ApplicationErrorCode.INTERNAL_FAILURE
    assert "secret" not in str(raised.value)
    assert "/Users/" not in str(raised.value)
    assert dict(raised.value.details) == {}


def test_a_mismatched_result_identity_fails_closed() -> None:
    """A result for another request is never reported as this request's result."""

    service, _probe, _sessions = _fixture(result=_result(request_id="other-request"))

    with pytest.raises(InternalApplicationError):
        service.submit_message(request_id="req-1", message=_message())


def test_a_mismatched_result_identity_never_reaches_a_response() -> None:
    service, _probe, _sessions = _fixture(result=_result(request_id="other-request"))

    with pytest.raises(InternalApplicationError) as raised:
        service.submit_message(request_id="req-1", message=_message())

    assert "other-request" not in str(raised.value)
    assert dict(raised.value.details) == {}


# ── Connected canonical behavior ─────────────────────────────────────────────


def test_a_content_only_message_needs_clarification_canonically() -> None:
    """The real resolver is never fed a fabricated intent signal."""

    sessions = SessionApplicationService(InMemorySessionStore())
    sessions.create_session("session-1")
    service = RequestApplicationService(
        sessions=sessions, orchestrator=_real_orchestrator()
    )

    response = service.submit_message(request_id="req-1", message=_message())

    assert response.status is ApplicationStatus.NEEDS_CLARIFICATION
    assert response.error is None
    assert response.data is not None
    assert response.data["intent"] == "unknown"
    assert response.data["decision_id"] == "orchestration-decision:req-1"


def test_a_structured_question_routes_over_real_canonical_components() -> None:
    sessions = SessionApplicationService(InMemorySessionStore())
    sessions.create_session("session-1")
    service = RequestApplicationService(
        sessions=sessions,
        orchestrator=_real_orchestrator(intent_resolver=_IntentResolver()),
    )

    response = service.submit_message(request_id="req-1", message=_message())

    assert response.status is ApplicationStatus.ROUTED
    assert response.error is None
    assert response.data is not None
    assert response.data["intent"] == "question"
    assert response.data["route"] == ExecutionRoute.AUTONOMOUS_AGENT.value
    assert response.data["agent_id"] == "agent-1"


def test_a_canonical_deny_becomes_a_blocked_application_response() -> None:
    sessions = SessionApplicationService(InMemorySessionStore())
    sessions.create_session("session-1")
    service = RequestApplicationService(
        sessions=sessions,
        orchestrator=_real_orchestrator(
            intent_resolver=_IntentResolver(),
            domain=DomainRouteDecision(
                status="resolved",
                primary_domain="domain:general",
                permission_disposition="deny",
            ),
        ),
    )

    response = service.submit_message(request_id="req-1", message=_message())

    assert response.status is ApplicationStatus.BLOCKED
    assert response.error is not None
    assert response.error.code is ApplicationErrorCode.POLICY_DENIED


def test_a_missing_session_never_reaches_the_real_pipeline() -> None:
    sessions = SessionApplicationService(InMemorySessionStore())
    repository = InMemoryOrchestrationDecisionRepository()
    orchestrator = Orchestrator(
        intent_resolver=_IntentResolver(),  # type: ignore[arg-type]
        context_resolver=_ContextResolver(),  # type: ignore[arg-type]
        domain_router=_DomainRouter(  # type: ignore[arg-type]
            DomainRouteDecision(
                status="resolved",
                primary_domain="domain:general",
                permission_disposition="allow",
            )
        ),
        agent_router=_AgentRouter(  # type: ignore[arg-type]
            AgentRouteDecision(route=ExecutionRoute.DIRECT_RESPONSE)
        ),
        policy=DefaultOrchestrationPolicy(),
        decision_repository=repository,
        event_sink=RecordingOrchestrationEventSink(),
    )
    service = RequestApplicationService(sessions=sessions, orchestrator=orchestrator)

    with pytest.raises(ApplicationResourceNotFoundError):
        service.submit_message(request_id="req-1", message=_message())

    assert repository.get("orchestration-decision:req-1") is None
