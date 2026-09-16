"""Phase 11.4 — the transport-neutral application request channel.

Design Point: ``DP-104`` — Single-Front-Door Fail-Closed Operational CLI

Phase 11.4 needs one thing from the closed Phase 11.3 boundary: a way for a
non-HTTP caller to say that a public request originated on the CLI, without
bypassing ``ApplicationGateway`` and without exposing a caller-selectable
channel on the HTTP surface.

The seam is one backward-compatible public field, ``ApplicationRequest.channel``,
defaulting to ``API``:

- it is part of the request's deterministic public serialization, so two
  otherwise identical commands from different channels have different
  fingerprints and can never share one idempotency replay record;
- ``RequestApplicationService`` maps it to the canonical
  ``OrchestrationChannel`` when it builds the canonical ``OrchestrationRequest``;
- nothing else changes: the HTTP adapter sets no channel, so its behavior — and
  the whole Phase 11.3 route/schema surface — stays exactly as closed.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any

import pytest

from cmm.application.capabilities import (
    CapabilityApplicationService,
    build_default_capabilities,
)
from cmm.application.contracts import (
    APPLICATION_API_VERSION,
    ApplicationChannel,
    ApplicationCommand,
    ApplicationErrorCode,
    ApplicationMessage,
    ApplicationOperation,
    ApplicationQuery,
    ApplicationStatus,
)
from cmm.application.gateway import ApplicationGateway
from cmm.application.health import HealthApplicationService
from cmm.application.idempotency import (
    InMemoryIdempotencyRepository,
    fingerprint_command,
)
from cmm.application.requests import RequestApplicationService
from cmm.application.sessions import SessionApplicationService
from cmm.orchestration.contracts import (
    AgentRouteDecision,
    DomainRouteDecision,
    ExecutionRoute,
    IntentResolution,
    OrchestrationChannel,
    OrchestrationRequest,
    OrchestrationResult,
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

SESSION_ID = "session-1"
ACTOR_ID = "actor-1"
MESSAGE_CONTENT = "What changed in the plan?"

#: The public request fields Phase 11.4 froze for serialization.
REQUEST_FIELDS = frozenset(
    {
        "request_id",
        "api_version",
        "operation",
        "actor_id",
        "session_id",
        "payload",
        "metadata",
        "channel",
    }
)


# ── Canonical collaborators (real Phase 11.2 pipeline) ───────────────────────


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
    """A real ``Orchestrator`` that records every adapted request.

    Subclassing keeps the canonical authority identity the adapter validates
    while these tests observe the exact adapted ``OrchestrationRequest``.
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

    def orchestrate(self, request: OrchestrationRequest) -> OrchestrationResult:
        self.requests.append(request)
        return super().orchestrate(request)


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
                    implementation_id="tests.application.test_channels.double",
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


class _Harness:
    def __init__(self) -> None:
        store = InMemorySessionStore()
        sessions = SessionApplicationService(store)
        sessions.create_session(SESSION_ID)

        self.store = store
        self.sessions = sessions
        self.orchestrator = _RecordingOrchestrator()
        self.idempotency = InMemoryIdempotencyRepository()
        self.requests = RequestApplicationService(
            sessions=sessions, orchestrator=self.orchestrator
        )
        self.gateway = ApplicationGateway(
            sessions=sessions,
            requests=self.requests,
            capabilities=CapabilityApplicationService(build_default_capabilities()),
            health=HealthApplicationService(_ready_container()),
            idempotency=self.idempotency,
        )

    def message(self, **overrides: Any) -> ApplicationMessage:
        fields: dict[str, Any] = {
            "message_id": "message-1",
            "session_id": SESSION_ID,
            "actor_id": ACTOR_ID,
            "content": MESSAGE_CONTENT,
        }
        fields.update(overrides)
        return ApplicationMessage(**fields)

    def command(self, **overrides: Any) -> ApplicationCommand:
        fields: dict[str, Any] = {
            "request_id": "req-1",
            "api_version": APPLICATION_API_VERSION,
            "operation": ApplicationOperation.MESSAGE_SUBMIT,
            "actor_id": ACTOR_ID,
            "session_id": SESSION_ID,
            "payload": {
                "message_id": "message-1",
                "content": MESSAGE_CONTENT,
                "content_type": "text/plain",
                "metadata": {},
            },
        }
        fields.update(overrides)
        return ApplicationCommand(**fields)


# ── The public channel value ─────────────────────────────────────────────────


def test_application_channel_values_are_frozen() -> None:
    assert {member.value for member in ApplicationChannel} == {"api", "cli"}


def test_the_default_request_channel_is_api() -> None:
    query = ApplicationQuery(
        request_id="req-1",
        api_version=APPLICATION_API_VERSION,
        operation=ApplicationOperation.HEALTH_GET,
    )
    command = _Harness().command()

    assert query.channel is ApplicationChannel.API
    assert command.channel is ApplicationChannel.API


def test_an_explicit_cli_channel_is_preserved() -> None:
    command = _Harness().command(channel=ApplicationChannel.CLI)

    assert command.channel is ApplicationChannel.CLI


def test_the_request_channel_is_part_of_the_public_document() -> None:
    command = _Harness().command()
    query = ApplicationQuery(
        request_id="req-2",
        api_version=APPLICATION_API_VERSION,
        operation=ApplicationOperation.HEALTH_GET,
        channel=ApplicationChannel.CLI,
    )

    assert set(command.to_dict()) == REQUEST_FIELDS | {
        "idempotency_key",
        "expected_session_revision",
    }
    assert command.to_dict()["channel"] == "api"
    assert set(query.to_dict()) == REQUEST_FIELDS
    assert query.to_dict()["channel"] == "cli"


def test_the_request_channel_rejects_a_raw_string() -> None:
    with pytest.raises(TypeError):
        _Harness().command(channel="cli")


# ── Fingerprint separation ───────────────────────────────────────────────────


def test_identical_commands_from_different_channels_fingerprint_differently() -> None:
    harness = _Harness()
    api_command = harness.command(channel=ApplicationChannel.API)
    cli_command = harness.command(channel=ApplicationChannel.CLI)

    assert fingerprint_command(api_command) != fingerprint_command(cli_command)


def test_the_fingerprint_is_stable_within_one_channel() -> None:
    harness = _Harness()

    assert fingerprint_command(
        harness.command(channel=ApplicationChannel.CLI)
    ) == fingerprint_command(harness.command(channel=ApplicationChannel.CLI))
    assert fingerprint_command(
        harness.command(request_id="req-other", channel=ApplicationChannel.CLI)
    ) == fingerprint_command(harness.command(channel=ApplicationChannel.CLI))


# ── Canonical orchestration channel ──────────────────────────────────────────


def test_message_submission_reaches_orchestration_as_api_by_default() -> None:
    harness = _Harness()

    harness.requests.submit_message(request_id="req-default", message=harness.message())

    assert len(harness.orchestrator.requests) == 1
    assert harness.orchestrator.requests[0].channel is OrchestrationChannel.API


def test_message_submission_reaches_orchestration_as_cli_when_requested() -> None:
    harness = _Harness()

    harness.requests.submit_message(
        request_id="req-cli",
        message=harness.message(),
        channel=ApplicationChannel.CLI,
    )

    assert len(harness.orchestrator.requests) == 1
    assert harness.orchestrator.requests[0].channel is OrchestrationChannel.CLI


def test_message_submission_rejects_a_non_channel_value() -> None:
    harness = _Harness()

    with pytest.raises(TypeError):
        harness.requests.submit_message(
            request_id="req-bad",
            message=harness.message(),
            channel="cli",  # type: ignore[arg-type]
        )


# ── The gateway forwards the request channel ─────────────────────────────────


def test_the_gateway_forwards_the_cli_channel_to_orchestration() -> None:
    harness = _Harness()

    response = harness.gateway.handle(harness.command(channel=ApplicationChannel.CLI))

    assert response.status is ApplicationStatus.NEEDS_CLARIFICATION
    assert len(harness.orchestrator.requests) == 1
    assert harness.orchestrator.requests[0].channel is OrchestrationChannel.CLI


def test_the_gateway_keeps_the_api_channel_for_an_api_request() -> None:
    harness = _Harness()

    harness.gateway.handle(harness.command())

    assert len(harness.orchestrator.requests) == 1
    assert harness.orchestrator.requests[0].channel is OrchestrationChannel.API


def test_the_http_shaped_request_never_selects_a_non_api_channel() -> None:
    """A request built the way ``cmm.api`` builds one stays on the API channel."""

    harness = _Harness()
    http_shaped = ApplicationCommand(
        request_id="req-http",
        api_version=APPLICATION_API_VERSION,
        operation=ApplicationOperation.MESSAGE_SUBMIT,
        actor_id=ACTOR_ID,
        session_id=SESSION_ID,
        payload={
            "message_id": "message-1",
            "content": MESSAGE_CONTENT,
            "content_type": "text/plain",
            "metadata": {"channel": "cli"},
        },
    )

    harness.gateway.handle(http_shaped)

    assert harness.orchestrator.requests[0].channel is OrchestrationChannel.API


# ── Idempotency replay separation ────────────────────────────────────────────


def test_a_keyed_command_does_not_replay_across_channels() -> None:
    """One idempotency key binds one channel's command, not both."""

    harness = _Harness()
    api_response = harness.gateway.handle(
        harness.command(request_id="req-api", idempotency_key="key-1")
    )
    cli_response = harness.gateway.handle(
        harness.command(
            request_id="req-cli",
            idempotency_key="key-1",
            channel=ApplicationChannel.CLI,
        )
    )

    assert api_response.status is ApplicationStatus.NEEDS_CLARIFICATION
    assert cli_response.status is ApplicationStatus.FAILED
    assert cli_response.error is not None
    assert cli_response.error.code is ApplicationErrorCode.IDEMPOTENCY_CONFLICT
    # The API channel's record was never replaced by the rejected CLI command.
    assert harness.idempotency.get("key-1").response == api_response
    assert len(harness.orchestrator.requests) == 1


def test_a_keyed_command_still_replays_within_the_cli_channel() -> None:
    harness = _Harness()
    first = harness.gateway.handle(
        harness.command(
            request_id="req-cli-1",
            idempotency_key="key-1",
            channel=ApplicationChannel.CLI,
        )
    )
    second = harness.gateway.handle(
        harness.command(
            request_id="req-cli-2",
            idempotency_key="key-1",
            channel=ApplicationChannel.CLI,
        )
    )

    assert first == second
    assert len(harness.orchestrator.requests) == 1
    assert harness.orchestrator.requests[0].channel is OrchestrationChannel.CLI


def test_a_replaced_channel_is_still_serialized_and_fingerprinted() -> None:
    """A tampered channel changes the fingerprint rather than being ignored."""

    harness = _Harness()
    tampered = replace(harness.command(), channel=ApplicationChannel.CLI)

    assert tampered.to_dict()["channel"] == "cli"
    assert fingerprint_command(tampered) != fingerprint_command(harness.command())
