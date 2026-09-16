"""Phase 11.3 — connected acceptance test ``AT-DP-103``.

Requirement: ``F11-017`` — Application Backend
Design Point: ``DP-103`` — Connected Application Backend

This is a **connected** acceptance test, not a mock-only endpoint test.  It
composes the real backend and drives it through its public surfaces:

* ``cmm.api`` — the real ``create_app`` factory and ``TestClient``;
* ``cmm.application`` — the real ``ApplicationGateway``, its four official
  services, the official in-memory idempotency repository and the Phase 11.1
  composition module;
* ``cmm.orchestration`` — the real ``Orchestrator`` over the real
  ``DeterministicIntentResolver``, ``DefaultContextResolver``,
  ``CanonicalDomainRouter``, ``CanonicalAgentRouter``,
  ``DefaultOrchestrationPolicy``, ``InMemoryOrchestrationDecisionRepository``
  and ``RecordingOrchestrationEventSink``;
* ``cmm.domains`` / ``cmm.agent_runtime`` — the canonical domain and agent
  owners the Phase 11.2 acceptance test drives;
* ``cmm.runtime.sessions`` — the official ``InMemorySessionStore``;
* ``cmm.platform`` — the real ``ApplicationContainer``.

The graph construction is copied from
``tests/orchestration/test_phase11_2_dp102_acceptance.py`` rather than imported,
so this file needs no cross-package fixture import and no test order.

Scenarios A–M are covered here.  Scenario N (inherited ``AT-DP-102`` /
``AT-DP-101`` / ``AT-DP-134``) is represented by separate required gate
commands, not by invoking other test modules from inside this one.

Two scenarios are deliberately asserted at the honest boundary the frozen
Phase 11.3 contracts reach:

* **Scenario D** — the public message contract carries no ``intent_hint`` and no
  structured intent shape, so the canonical deterministic intent resolver
  answers ``NEEDS_CLARIFICATION`` before domain or agent routing.  That honest
  canonical outcome is asserted instead of a fabricated model response.
* **Scenario E** — canonical domain and agent authority is proven live and
  deterministic on this exact composed graph through the real orchestrator, and
  the application layer is proven to be a faithful projection of canonical
  authority that owns no selection surface of its own.

See ``docs/superpowers/specs/2026-09-16-phase-11.3-application-backend-design.md``.
"""

from __future__ import annotations

import json
import threading
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from cmm.agent_runtime.action_budget_service import ActionBudgetService
from cmm.agent_runtime.agent_factory import AgentFactoryRegistry
from cmm.agent_runtime.agent_registry import AgentRegistry
from cmm.agent_runtime.agent_registry_contracts import (
    AgentCapability,
    AgentDescriptor,
    AgentInstance,
    AgentVersion,
)
from cmm.agent_runtime.agent_registry_enums import (
    AgentCapabilityKind,
    AgentFactoryScope,
    AgentKind,
    AgentLifecycle,
)
from cmm.agent_runtime.agent_registry_service import AgentRegistryService
from cmm.agent_runtime.agent_registry_store import InMemoryAgentRegistryStore
from cmm.agent_runtime.agent_runtime_integration_service import (
    AgentRuntimeIntegrationService,
)
from cmm.agent_runtime.agent_runtime_integration_store import (
    InMemoryAgentRuntimeIntegrationStore,
)
from cmm.agent_runtime.agent_security_service import AgentSecurityService
from cmm.agent_runtime.domain_permission_contracts import PermissionCapability
from cmm.agent_runtime.goal_manager import GoalManager
from cmm.agent_runtime.operation_execution_adapter import AgentExecutionAdapter
from cmm.agent_runtime.runtime_loop import AgentRuntimeLoop
from cmm.api.app import create_app
from cmm.api.errors import (
    REASON_INVALID_IDEMPOTENCY_KEY,
    REASON_INVALID_REQUEST_BODY,
    REASON_INVALID_REQUEST_ID,
    REASON_UNKNOWN_ROUTE,
)
from cmm.application import (
    APPLICATION_API_VERSION,
    APPLICATION_AUTHORITY,
    APPLICATION_CONTRACT_VERSION,
    APPLICATION_MODULE_ID,
    APPLICATION_OWNER,
    APPLICATION_SCHEMA_VERSION,
    APPLICATION_SERVICE_ID,
    CANCELLATION_UNAVAILABLE_MESSAGE,
    MAX_MESSAGE_LENGTH,
    REASON_CANCELLATION_UNAVAILABLE,
    ApplicationCommand,
    ApplicationErrorCode,
    ApplicationGateway,
    ApplicationOperation,
    ApplicationQuery,
    ApplicationStatus,
    CapabilityApplicationService,
    CapabilityStatus,
    HealthApplicationService,
    IdempotencyRecord,
    InMemoryIdempotencyRepository,
    RequestApplicationService,
    SessionApplicationService,
    build_application_composition_module,
    build_default_capabilities,
)
from cmm.application.errors import GENERIC_FAILURE_MESSAGE
from cmm.application.platform_module import ORCHESTRATOR_DEPENDENCY_ID
from cmm.domains.contracts import DomainDefinition
from cmm.domains.enums import DomainKind
from cmm.domains.identifiers import DomainId
from cmm.domains.permission_contracts import DomainPermissionPolicy
from cmm.domains.permission_registry import DomainPermissionRegistry
from cmm.domains.permission_resolution import DomainPermissionResolver
from cmm.domains.profile_contracts import DomainProfileDefinition
from cmm.domains.profile_registry import InMemoryDomainProfileRegistry
from cmm.domains.registry import DomainRegistry
from cmm.domains.resolution_builder import DomainResolutionContextBuilder
from cmm.domains.resolver import DefaultDomainResolver
from cmm.execution.executor_registry import ExecutorRegistry
from cmm.orchestration.agent_router import CanonicalAgentRouter
from cmm.orchestration.context import DefaultContextResolver
from cmm.orchestration.contracts import (
    ExecutionRoute,
    IntentKind,
    OrchestrationChannel,
    OrchestrationRequest,
    OrchestrationStatus,
    PolicyDisposition,
)
from cmm.orchestration.decision_repository import (
    InMemoryOrchestrationDecisionRepository,
)
from cmm.orchestration.domain_router import CanonicalDomainRouter
from cmm.orchestration.events import RecordingOrchestrationEventSink
from cmm.orchestration.intent import DeterministicIntentResolver
from cmm.orchestration.orchestrator import Orchestrator
from cmm.orchestration.platform_module import (
    ORCHESTRATION_AUTHORITY,
    ORCHESTRATION_SERVICE_IDS,
    ORCHESTRATOR_SERVICE_ID,
    build_orchestration_composition_module,
)
from cmm.orchestration.policy import (
    DefaultOrchestrationPolicy,
    OrchestrationConfiguration,
)
from cmm.platform.canonical import (
    agent_runtime_integration_binding,
    domain_registry_binding,
    execution_registry_binding,
    provider_registry_binding,
    workflow_registry_binding,
)
from cmm.platform.configuration import CompositionConfiguration
from cmm.platform.container import ApplicationContainer
from cmm.platform.contracts import ContainerState
from cmm.platform.errors import MissingDependencyError
from cmm.platform.modules import StaticCompositionModule
from cmm.platform.service_registry import IntegrationServiceRegistry
from cmm.runtime.sessions import InMemorySessionStore
from cmm.workflows.registry import InMemoryWorkflowRegistry
from kernel.llm.provider_registry import ProviderRegistry

# ── Canonical fixture constants (mirroring the Phase 11.2 acceptance test) ────

NOW = datetime(2026, 9, 16, tzinfo=timezone.utc)

GENERAL = DomainId(slug="general")
HEALTH = DomainId(slug="health")

HEALTH_POLICY_ID = "health.policy"

GENERAL_POLICY = DomainPermissionPolicy(
    policy_id="general.policy",
    domain_id="domain:general",
    version="1.0.0",
    allowed_capabilities=(PermissionCapability.GOAL_UPDATE,),
)

HEALTH_OPERATION_POLICY = DomainPermissionPolicy(
    policy_id=HEALTH_POLICY_ID,
    domain_id="domain:health",
    version="1.0.0",
    allowed_capabilities=(PermissionCapability.OPERATION_EXECUTE,),
    allowed_operations=("project.inspect",),
)

HEALTH_DENIED_POLICY = DomainPermissionPolicy(
    policy_id=HEALTH_POLICY_ID,
    domain_id="domain:health",
    version="1.0.0",
    prohibited_capabilities=(PermissionCapability.OPERATION_EXECUTE,),
)

HEALTH_PROFILE = DomainProfileDefinition(
    id="health.default",
    domain_id=HEALTH,
    profile_name="Health",
)

ALL_CHANNELS = (
    OrchestrationChannel.CONVERSATION,
    OrchestrationChannel.CLI,
    OrchestrationChannel.INTERNAL,
    OrchestrationChannel.API,
)

# ── Public transport constants ───────────────────────────────────────────────

REQUEST_ID_HEADER = "X-Request-ID"
IDEMPOTENCY_KEY_HEADER = "Idempotency-Key"

SESSION_ID = "session-1"
OTHER_SESSION_ID = "session-2"
ACTOR_ID = "actor-1"
MESSAGE_CONTENT = "What changed in the plan?"

#: Raw internal defect text that must never reach a public response.
RAW_DEFECT_TEXT = (
    "Traceback (most recent call last): internal defect at "
    "/private/tmp/cmm-internal-detail with secret AKIA-EXAMPLE-SECRET-KEY"
)

#: The frozen safe public projection of one canonical orchestration result.
PROJECTION_KEYS = frozenset(
    {
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
    }
)


# ── Boundary probe (forbidden downstream actions only) ───────────────────────


class ForbiddenExecutionProbe:
    """Records any attempt to execute the downstream vertical."""

    def __init__(self) -> None:
        self.calls: list[object] = []

    def execute(self, operation: object) -> dict[str, object]:
        self.calls.append(operation)
        raise AssertionError("Phase 11.3 must never execute an operation")

    def __call__(self, operation: object) -> dict[str, object]:
        return self.execute(operation)


class InMemoryAgentFactory:
    """Official-style in-memory factory satisfying the canonical factory seam."""

    def __init__(self, factory_id: str) -> None:
        self._factory_id = factory_id

    @property
    def factory_id(self) -> str:
        return self._factory_id

    @property
    def scope(self) -> AgentFactoryScope:
        return AgentFactoryScope.TRANSIENT

    @property
    def thread_safe(self) -> bool:
        return True

    def supports(self, descriptor: AgentDescriptor) -> bool:
        return descriptor.factory_id == self._factory_id

    def create(self, descriptor: AgentDescriptor, context: object) -> AgentInstance:
        return AgentInstance(
            instance_id=f"instance:{descriptor.agent_id}",
            descriptor=descriptor,
            runtime_object=object(),
            scope=AgentFactoryScope.TRANSIENT,
        )


# ── Connected backend ────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class ApplicationBackend:
    """The composed Phase 11.3 backend over the real canonical graph."""

    platform_container: ApplicationContainer
    container: ApplicationContainer
    app: FastAPI
    gateway: ApplicationGateway
    orchestrator: Orchestrator
    repository: InMemoryOrchestrationDecisionRepository
    sink: RecordingOrchestrationEventSink
    context_resolver: DefaultContextResolver
    domain_router: CanonicalDomainRouter
    agent_router: CanonicalAgentRouter
    agent_service: AgentRegistryService
    session_store: InMemorySessionStore
    sessions: SessionApplicationService
    idempotency: InMemoryIdempotencyRepository
    execution_probe: ForbiddenExecutionProbe


#: The canonical services the platform composition binds, in the order the
#: Phase 11.2 acceptance test requires them.
_CANONICAL_SERVICE_IDS = (
    "agent.runtime.integration",
    "domain.registry",
    "execution.registry",
    "provider.registry",
    "workflow.registry",
)


def _domain_registry() -> DomainRegistry:
    registry = DomainRegistry()
    for slug in ("general", "health", "university"):
        registry.register(
            DomainDefinition(
                id=f"domain:{slug}",
                name=slug,
                display_name=slug.title(),
                version="1.0.0",
                kind=DomainKind.CORE,
                description=f"{slug} domain",
                manifest_id=f"manifest:{slug}:1.0.0",
            )
        )
        registry.enable(f"domain:{slug}")
    return registry


def _agent_service(*capabilities: str) -> AgentRegistryService:
    service = AgentRegistryService(
        registry=AgentRegistry(store=InMemoryAgentRegistryStore()),
        factory_registry=AgentFactoryRegistry(),
    )
    if capabilities:
        descriptor = AgentDescriptor(
            agent_id="agent.alpha",
            name="Alpha Agent",
            version=AgentVersion(1, 0, 0),
            kind=AgentKind.GENERAL,
            lifecycle=AgentLifecycle.ACTIVE,
            description="alpha agent",
            capabilities=tuple(
                AgentCapability(name=name, kind=AgentCapabilityKind.OPERATION)
                for name in capabilities
            ),
            factory_id="factory.alpha",
        )
        service.register_factory(InMemoryAgentFactory(descriptor.factory_id))
        service.register_agent(descriptor)
    return service


def _platform_configuration() -> CompositionConfiguration:
    return CompositionConfiguration(
        required_services=(*ORCHESTRATION_SERVICE_IDS, *_CANONICAL_SERVICE_IDS),
        enabled_modules=("canonical", "orchestration"),
    )


def _backend_configuration() -> CompositionConfiguration:
    return CompositionConfiguration(
        required_services=(
            *ORCHESTRATION_SERVICE_IDS,
            *_CANONICAL_SERVICE_IDS,
            APPLICATION_SERVICE_ID,
        ),
        enabled_modules=("canonical", "orchestration", APPLICATION_MODULE_ID),
    )


def _build_backend(
    *,
    policies: tuple[DomainPermissionPolicy, ...] = (
        GENERAL_POLICY,
        HEALTH_OPERATION_POLICY,
    ),
    agent_capabilities: tuple[str, ...] = ("knowledge.read",),
    profiles: tuple[DomainProfileDefinition, ...] = (HEALTH_PROFILE,),
) -> ApplicationBackend:
    """Build the real Phase 11.3 backend over the real canonical graph.

    Two Phase 11.1 containers are used, exactly as the composition boundary
    requires: the *platform* container (canonical + orchestration) is the
    readiness owner the gateway's health projection reads, and the *backend*
    container additionally binds ``application.gateway``, because the gateway is
    the object the application module contributes and can not be built from a
    container that already contains it.
    """

    domain_registry = _domain_registry()

    permission_registry = DomainPermissionRegistry()
    for policy in policies:
        permission_registry.register(policy)
    permission_resolver = DomainPermissionResolver(
        permission_registry, trust_policy_lookup=None
    )

    profile_registry = InMemoryDomainProfileRegistry()
    for profile in profiles:
        profile_registry.register(profile)

    session_store = InMemorySessionStore()

    domain_router = CanonicalDomainRouter(
        resolver=DefaultDomainResolver(
            fallback_domain=GENERAL,
            clock=lambda: NOW,
            id_factory=lambda: "resolution-1",
        ),
        registry=domain_registry,
        context_builder=DomainResolutionContextBuilder(
            clock=lambda: NOW, id_factory=lambda: "resolution-context-1"
        ),
        profile_registry=profile_registry,
        permission_registry=permission_registry,
        permission_resolver=permission_resolver,
    )

    agent_service = _agent_service(*agent_capabilities)
    agent_router = CanonicalAgentRouter(registry_service=agent_service)

    context_resolver = DefaultContextResolver(session_store=session_store)
    policy = DefaultOrchestrationPolicy(
        configuration=OrchestrationConfiguration(allowed_channels=ALL_CHANNELS)
    )

    repository = InMemoryOrchestrationDecisionRepository()
    sink = RecordingOrchestrationEventSink()

    intent_resolver = DeterministicIntentResolver()
    orchestrator = Orchestrator(
        intent_resolver=intent_resolver,
        context_resolver=context_resolver,
        domain_router=domain_router,
        agent_router=agent_router,
        policy=policy,
        decision_repository=repository,
        event_sink=sink,
    )

    probe = ForbiddenExecutionProbe()
    agent_runtime_integration = AgentRuntimeIntegrationService(
        store=InMemoryAgentRuntimeIntegrationStore(),
        goal_manager=GoalManager(),
        registry_service=agent_service,
        runtime_loop=AgentRuntimeLoop(goal_repository=GoalManager().repository),
        security_service=AgentSecurityService(),
        budget_service=ActionBudgetService(),
        execution_adapter=AgentExecutionAdapter(execution_delegate=probe),
    )

    canonical_module = StaticCompositionModule(
        "canonical",
        (
            domain_registry_binding(domain_registry),
            execution_registry_binding(ExecutorRegistry()),
            provider_registry_binding(ProviderRegistry()),
            workflow_registry_binding(InMemoryWorkflowRegistry()),
            agent_runtime_integration_binding(agent_runtime_integration),
        ),
    )
    orchestration_module = build_orchestration_composition_module(
        intent_resolver=intent_resolver,
        context_resolver=context_resolver,
        domain_router=domain_router,
        agent_router=agent_router,
        policy=policy,
        decision_repository=repository,
        event_sink=sink,
        orchestrator=orchestrator,
    )

    platform_container = ApplicationContainer.build(
        _platform_configuration(),
        modules=(canonical_module, orchestration_module),
    )

    sessions = SessionApplicationService(session_store)
    idempotency = InMemoryIdempotencyRepository()
    gateway = ApplicationGateway(
        sessions=sessions,
        requests=RequestApplicationService(
            sessions=sessions, orchestrator=orchestrator
        ),
        capabilities=CapabilityApplicationService(build_default_capabilities()),
        health=HealthApplicationService(platform_container),
        idempotency=idempotency,
    )
    application_module = build_application_composition_module(gateway=gateway)

    container = ApplicationContainer.build(
        _backend_configuration(),
        modules=(canonical_module, orchestration_module, application_module),
    )

    return ApplicationBackend(
        platform_container=platform_container,
        container=container,
        app=create_app(gateway),
        gateway=gateway,
        orchestrator=orchestrator,
        repository=repository,
        sink=sink,
        context_resolver=context_resolver,
        domain_router=domain_router,
        agent_router=agent_router,
        agent_service=agent_service,
        session_store=session_store,
        sessions=sessions,
        idempotency=idempotency,
        execution_probe=probe,
    )


# ── Public request helpers ───────────────────────────────────────────────────


def _client(backend: ApplicationBackend) -> TestClient:
    return TestClient(backend.app)


def _client_with_sessions(backend: ApplicationBackend, *session_ids: str) -> TestClient:
    """Create the named sessions through the public API and return a client."""

    client = _client(backend)
    for session_id in session_ids:
        response = client.post("/v1/sessions", json={"session_id": session_id})
        assert response.status_code == 201
    return client


def _message_body(**overrides: Any) -> dict[str, Any]:
    body: dict[str, Any] = {"actor_id": ACTOR_ID, "content": MESSAGE_CONTENT}
    body.update(overrides)
    return body


def _submit_message(
    client: TestClient,
    session_id: str = SESSION_ID,
    *,
    request_id: str | None = None,
    idempotency_key: str | None = None,
    **body_overrides: Any,
) -> Any:
    headers: dict[str, str] = {}
    if request_id is not None:
        headers[REQUEST_ID_HEADER] = request_id
    if idempotency_key is not None:
        headers[IDEMPOTENCY_KEY_HEADER] = idempotency_key
    return client.post(
        f"/v1/sessions/{session_id}/messages",
        json=_message_body(**body_overrides),
        headers=headers,
    )


def _canonical_request(
    request_id: str,
    *,
    session_id: str | None = SESSION_ID,
    channel: OrchestrationChannel = OrchestrationChannel.CONVERSATION,
    input_payload: dict[str, object] | None = None,
    context: dict[str, object] | None = None,
    capabilities: tuple[str, ...] = (),
) -> OrchestrationRequest:
    """Return a canonical request shaped exactly as Phase 11.2 drives one."""

    return OrchestrationRequest(
        request_id=request_id,
        user_id=ACTOR_ID,
        channel=channel,
        session_id=session_id,
        input=input_payload if input_payload is not None else {},
        context=context or {},
        requested_capabilities=capabilities,
    )


def _health_signal(confidence: float = 0.9) -> dict[str, object]:
    return {"value": "medical", "domains": ["health"], "confidence": confidence}


# ── Canonical pipeline observation helpers ───────────────────────────────────


def _request_received_ids(backend: ApplicationBackend) -> list[str]:
    """Return the canonical request identities the real pipeline accepted.

    ``orchestration.request_received`` is the first event the canonical
    orchestrator emits for every accepted request, so the official recording
    sink is a faithful invocation count of the real pipeline; it is canonical
    Phase 11.2 evidence rather than an instrumented collaborator.
    """

    return [
        event.request_id
        for event in backend.sink.events()
        if event.event_type == "orchestration.request_received"
    ]


def _assert_orchestration_not_invoked(backend: ApplicationBackend) -> None:
    """Assert the canonical pipeline was never entered for this backend."""

    assert backend.sink.events() == ()
    assert backend.repository.list_for_session(SESSION_ID) == ()
    assert backend.repository.list_for_session(OTHER_SESSION_ID) == ()
    assert backend.platform_container.state is ContainerState.READY


def _events_for(backend: ApplicationBackend, request_id: str) -> list[str]:
    return [
        event.event_type
        for event in backend.sink.events()
        if event.request_id == request_id
    ]


# ══════════════════════════════════════════════════════════════════════════
# Scenario A — real backend composition
# ══════════════════════════════════════════════════════════════════════════


def test_scenario_a_backend_composes_the_real_container_to_ready() -> None:
    backend = _build_backend()

    assert backend.platform_container.state is ContainerState.READY
    assert backend.container.state is ContainerState.READY
    assert backend.container.failure() is None
    assert backend.container.get_service("orchestration.orchestrator") is (
        backend.orchestrator
    )
    assert backend.container.get_service("domain.registry") is not None
    assert backend.container.get_service("agent.runtime.integration") is not None


def test_scenario_a_gateway_identity_is_exact() -> None:
    backend = _build_backend()

    composed = backend.container.get_service(APPLICATION_SERVICE_ID)

    assert composed is backend.gateway
    # A subclass would be a parallel entrypoint of the same boundary.
    assert type(composed) is ApplicationGateway

    services = {
        service["service_id"]: service
        for service in backend.container.snapshot().to_dict()["services"]
    }
    application = services[APPLICATION_SERVICE_ID]

    assert application["owner"] == APPLICATION_OWNER
    assert application["contract_version"] == APPLICATION_CONTRACT_VERSION
    assert application["schema_version"] == APPLICATION_SCHEMA_VERSION
    assert application["authority"] == APPLICATION_AUTHORITY
    assert application["mode"] == "local"
    assert application["dependency_ids"] == [ORCHESTRATOR_DEPENDENCY_ID]
    assert services["orchestration.orchestrator"]["authority"] == (
        ORCHESTRATION_AUTHORITY
    )
    # The declared dependency mirrors the real Phase 11.2 service identity.
    assert ORCHESTRATOR_DEPENDENCY_ID == ORCHESTRATOR_SERVICE_ID
    assert ORCHESTRATOR_DEPENDENCY_ID in ORCHESTRATION_SERVICE_IDS


def test_scenario_a_application_module_alone_cannot_become_ready() -> None:
    backend = _build_backend()
    module = build_application_composition_module(gateway=backend.gateway)

    with pytest.raises(MissingDependencyError):
        ApplicationContainer.build(
            CompositionConfiguration(
                required_services=(APPLICATION_SERVICE_ID,),
                enabled_modules=(APPLICATION_MODULE_ID,),
            ),
            modules=(module,),
        )


# ══════════════════════════════════════════════════════════════════════════
# Scenario B — health
# ══════════════════════════════════════════════════════════════════════════


def test_scenario_b_health_reports_safe_readiness_on_the_v1_surface() -> None:
    backend = _build_backend()

    response = _client(backend).get(
        "/v1/health", headers={REQUEST_ID_HEADER: "request-b"}
    )

    assert response.status_code == 200
    assert response.headers[REQUEST_ID_HEADER] == "request-b"

    body = response.json()

    assert body["request_id"] == "request-b"
    assert body["api_version"] == APPLICATION_API_VERSION == "v1"
    assert body["status"] == ApplicationStatus.SUCCESS.value
    assert body["error"] is None
    assert body["metadata"] == {}

    data = body["data"]

    assert data["status"] == "ok"
    assert data["api_version"] == "v1"
    assert data["platform_ready"] is True
    assert "orchestration.orchestrator" in data["services"]
    assert "domain.registry" in data["services"]
    assert "agent.runtime.integration" in data["services"]
    # The readiness owner is the real Phase 11.1 composition.
    assert set(data["services"]) == {
        service.service_id for service in backend.platform_container.snapshot().services
    }


def test_scenario_b_health_exposes_no_implementation_identity() -> None:
    backend = _build_backend()

    response = _client(backend).get("/v1/health")

    body = response.text

    assert "detail" not in response.json()
    assert "tests." not in body
    assert "/users/" not in body.lower()
    assert "traceback" not in body.lower()
    for service in backend.platform_container.snapshot().services:
        assert service.implementation_id not in body
        assert service.owner not in body
        assert service.authority is None or service.authority not in body


# ══════════════════════════════════════════════════════════════════════════
# Scenario C — create/read session over the canonical store
# ══════════════════════════════════════════════════════════════════════════


def test_scenario_c_session_create_and_read_use_the_canonical_store() -> None:
    backend = _build_backend()

    created = _client(backend).post(
        "/v1/sessions",
        json={"session_id": SESSION_ID},
        headers={REQUEST_ID_HEADER: "request-c"},
    )

    assert created.status_code == 201
    session = created.json()["data"]

    assert session["session_id"] == SESSION_ID
    assert session["revision"] == 1
    assert session["status"] == "ACTIVE"
    for field in ("created_at", "updated_at"):
        assert datetime.fromisoformat(session[field]).utcoffset() == timedelta(0)

    # The canonical store itself holds the session Phase 11.3 created.
    stored = backend.session_store.load(SESSION_ID)
    assert stored is not None
    assert stored.revision == 1
    assert stored.status == "ACTIVE"

    read = _client(backend).get(f"/v1/sessions/{SESSION_ID}")

    assert read.status_code == 200
    assert read.json()["data"] == session


def test_scenario_c_read_reflects_the_canonical_store_not_a_copy() -> None:
    backend = _build_backend()
    client = _client_with_sessions(backend, SESSION_ID)

    # A canonical change written through the canonical owner is what the public
    # read reports; the application layer holds no session state of its own.
    committed = backend.session_store.save(
        backend.session_store.load(SESSION_ID).with_status("PAUSED")
    )
    assert committed.revision == 2

    read = client.get(f"/v1/sessions/{SESSION_ID}")

    assert read.json()["data"]["revision"] == committed.revision == 2
    assert read.json()["data"]["status"] == "PAUSED"


def test_scenario_c_duplicate_session_creation_is_a_conflict() -> None:
    backend = _build_backend()
    client = _client_with_sessions(backend, SESSION_ID)

    duplicate = client.post("/v1/sessions", json={"session_id": SESSION_ID})

    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == (ApplicationErrorCode.CONFLICT.value)
    # The canonical session was never re-versioned by the rejected create.
    assert backend.session_store.load(SESSION_ID).revision == 1
    _assert_orchestration_not_invoked(backend)


def test_scenario_c_created_session_is_usable_by_the_canonical_graph() -> None:
    backend = _build_backend()
    _client_with_sessions(backend, SESSION_ID)

    context = backend.context_resolver.resolve_base(
        _canonical_request("request-c-context")
    )

    assert context.session_ref == SESSION_ID
    assert context.session_status == "ACTIVE"
    assert context.session_revision == 1
    assert context.missing_refs == ()


# ══════════════════════════════════════════════════════════════════════════
# Scenario D — message reaches the real orchestrator
# ══════════════════════════════════════════════════════════════════════════


def test_scenario_d_message_reaches_the_real_orchestrator() -> None:
    backend = _build_backend()
    client = _client_with_sessions(backend, SESSION_ID)

    response = _submit_message(client, request_id="request-d")

    assert response.status_code == 200
    data = response.json()["data"]

    # The adapter sets no ``intent_hint`` and the public message shape carries
    # no structured intent, so the canonical deterministic resolver answers
    # ``NEEDS_CLARIFICATION``.  That honest canonical outcome is the assertion.
    assert data["status"] == ApplicationStatus.NEEDS_CLARIFICATION.value
    assert data["intent"] == IntentKind.UNKNOWN.value
    assert data["route"] == ExecutionRoute.NONE.value
    assert data["primary_domain"] is None
    assert data["supporting_domains"] == []
    assert data["agent_id"] is None
    assert data["profile_id"] is None
    assert data["decision_id"] == "orchestration-decision:request-d"
    assert "ORCHESTRATION_INTENT_UNKNOWN" in data["reason_codes"]
    assert "INTENT_UNKNOWN_NEEDS_CLARIFICATION" in data["reason_codes"]
    assert response.json()["error"] is None

    # The decision is the canonical repository's own record of that request.
    record = backend.repository.get_by_request_id("request-d")
    assert record is not None
    assert record.channel is OrchestrationChannel.API
    assert record.session_id == SESSION_ID
    assert record.intent is IntentKind.UNKNOWN
    assert record.execution_route is ExecutionRoute.NONE

    assert _events_for(backend, "request-d") == [
        "orchestration.request_received",
        "orchestration.intent_resolved",
        "orchestration.routed",
    ]


def test_scenario_d_public_data_is_the_canonical_decision_projection() -> None:
    backend = _build_backend()
    client = _client_with_sessions(backend, SESSION_ID)

    data = _submit_message(client, request_id="request-d").json()["data"]
    record = backend.repository.get_by_request_id("request-d")

    assert record is not None
    assert set(data) == PROJECTION_KEYS
    assert data["request_id"] == record.request_id
    assert data["session_id"] == record.session_id
    assert data["intent"] == record.intent.value
    assert data["route"] == record.execution_route.value
    assert data["primary_domain"] == record.primary_domain
    assert data["supporting_domains"] == list(record.supporting_domains)
    assert data["agent_id"] == record.selected_agent_id
    assert data["workflow_id"] == record.workflow_id
    assert data["approval_refs"] == list(record.approval_refs)
    assert data["decision_id"] == record.decision_id
    assert data["trace_refs"] == list(record.trace_refs)
    assert data["reason_codes"] == list(record.reason_codes)

    # Replaying the identical canonical request through the real orchestrator
    # returns the same decision (the canonical repository replays it), so the
    # public projection is the Orchestrator's own result rather than an
    # application-side interpretation of it.  This mirrors the frozen adapter
    # contract: API channel, empty context and no requested capability.
    mirrored = backend.orchestrator.orchestrate(
        _canonical_request(
            "request-d",
            channel=OrchestrationChannel.API,
            input_payload={
                "message_id": "message-mirror",
                "content": MESSAGE_CONTENT,
                "content_type": "text/plain",
                "metadata": {},
            },
        )
    )

    assert mirrored.decision_id == data["decision_id"]
    assert mirrored.status.value == data["status"]
    assert mirrored.intent.value == data["intent"]
    assert mirrored.route.value == data["route"]
    assert mirrored.primary_domain == data["primary_domain"]
    assert list(mirrored.supporting_domains) == data["supporting_domains"]
    assert mirrored.profile_id == data["profile_id"]
    assert mirrored.agent_id == data["agent_id"]
    assert mirrored.workflow_id == data["workflow_id"]
    assert list(mirrored.approval_refs) == data["approval_refs"]
    assert list(mirrored.reason_codes) == data["reason_codes"]


def test_scenario_d_message_never_reaches_the_downstream_vertical() -> None:
    backend = _build_backend()
    client = _client_with_sessions(backend, SESSION_ID)

    _submit_message(client, request_id="request-d")

    assert backend.execution_probe.calls == []
    assert backend.agent_service.resolver.attempts == 0


# ══════════════════════════════════════════════════════════════════════════
# Scenario E — canonical domain/agent authority preserved
# ══════════════════════════════════════════════════════════════════════════


def test_scenario_e_canonical_domain_authority_decides_on_this_graph() -> None:
    backend = _build_backend(policies=(HEALTH_DENIED_POLICY,))
    _client_with_sessions(backend, SESSION_ID)

    result = backend.orchestrator.orchestrate(
        _canonical_request(
            "request-e-domain",
            input_payload={"command": {"operation": "project.inspect"}},
            context={"domain_signals": [_health_signal()]},
        )
    )

    assert result.status is OrchestrationStatus.BLOCKED
    assert result.primary_domain == "domain:health"
    assert result.route is ExecutionRoute.OPERATION
    assert result.profile_id == "health.default"

    record = backend.repository.get(result.decision_id)
    assert record is not None
    assert record.policy_disposition is PolicyDisposition.DENY
    assert record.primary_domain == "domain:health"
    assert record.session_id == SESSION_ID
    assert backend.execution_probe.calls == []


def test_scenario_e_canonical_agent_authority_decides_on_this_graph() -> None:
    backend = _build_backend(agent_capabilities=("knowledge.read",))
    _client_with_sessions(backend, SESSION_ID)

    result = backend.orchestrator.orchestrate(
        _canonical_request(
            "request-e-agent",
            input_payload={"goal": {"title": "Complete task"}},
            capabilities=("knowledge.read",),
        )
    )

    assert result.status is OrchestrationStatus.ROUTED
    assert result.route is ExecutionRoute.AUTONOMOUS_AGENT
    assert result.agent_id == "agent.alpha"
    # The canonical registry service performed the selection exactly once.
    assert backend.agent_service.resolver.attempts == 1
    record = backend.repository.get(result.decision_id)
    assert record is not None
    assert record.selected_agent_id == "agent.alpha"
    assert backend.execution_probe.calls == []


def test_scenario_e_application_layer_projects_and_never_reselects() -> None:
    backend = _build_backend(agent_capabilities=("knowledge.read",))
    client = _client_with_sessions(backend, SESSION_ID)

    data = _submit_message(client, request_id="request-e").json()["data"]
    record = backend.repository.get_by_request_id("request-e")

    # Phase 11.3 reports the canonical decision and adds no selection of its own:
    # the intent the application path could not resolve stopped the canonical
    # pipeline before domain or agent routing, and the application layer did not
    # substitute a fallback decision, agent or domain.
    assert record is not None
    assert data["decision_id"] == record.decision_id
    assert record.primary_domain is None
    assert data["primary_domain"] is None
    assert record.selected_agent_id is None
    assert data["agent_id"] is None
    assert backend.agent_service.resolver.attempts == 0
    assert backend.execution_probe.calls == []

    # The gateway owns no domain/agent authority object at all.  Its instance
    # surface is exactly the five official collaborators plus the one private
    # in-process lock over the keyed idempotency critical section: a further
    # collaborator or a second concurrency object fails here.
    owned = vars(backend.gateway)
    assert set(owned) == {
        "_sessions",
        "_requests",
        "_capabilities",
        "_health",
        "_idempotency",
        "_idempotency_lock",
    }
    assert type(owned["_idempotency_lock"]) is type(threading.Lock())
    collaborators = [
        value for name, value in owned.items() if name != "_idempotency_lock"
    ]
    assert {type(collaborator) for collaborator in collaborators} == {
        SessionApplicationService,
        RequestApplicationService,
        CapabilityApplicationService,
        HealthApplicationService,
        InMemoryIdempotencyRepository,
    }
    for collaborator in collaborators:
        assert not isinstance(collaborator, CANONICAL_AUTHORITY_TYPES)

    # Domain and agent listing stay honestly deferred on the public surface.
    declared = {
        capability["capability_id"]: capability
        for capability in client.get("/v1/capabilities").json()["data"]["capabilities"]
    }
    assert declared["domains"]["status"] == CapabilityStatus.DEFERRED.value
    assert declared["agents"]["status"] == CapabilityStatus.DEFERRED.value


def test_scenario_e_agent_authority_is_not_reachable_from_the_public_path() -> None:
    """The public message path can not force agent selection it did not earn."""

    backend = _build_backend(agent_capabilities=("knowledge.read",))
    client = _client_with_sessions(backend, SESSION_ID)

    for request_id in ("request-e-1", "request-e-2"):
        response = _submit_message(
            client,
            request_id=request_id,
            metadata={"requested_capability": "knowledge.read"},
        )
        assert response.json()["data"]["route"] == ExecutionRoute.NONE.value

    assert backend.agent_service.resolver.attempts == 0


# ══════════════════════════════════════════════════════════════════════════
# Scenario F — malformed input fails before orchestration
# ══════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize(
    "body",
    [
        {"content": MESSAGE_CONTENT},
        {"actor_id": "", "content": MESSAGE_CONTENT},
        {"actor_id": ACTOR_ID, "content": ""},
        {"actor_id": ACTOR_ID, "content": "x" * (MAX_MESSAGE_LENGTH + 1)},
        {"actor_id": ACTOR_ID, "content": MESSAGE_CONTENT, "unknown": "field"},
        {
            "actor_id": ACTOR_ID,
            "content": MESSAGE_CONTENT,
            "expected_session_revision": True,
        },
        {
            "actor_id": ACTOR_ID,
            "content": MESSAGE_CONTENT,
            "metadata": {"a": [1] * 200},
        },
    ],
    ids=[
        "missing-actor",
        "blank-actor",
        "empty-content",
        "oversized-content",
        "unknown-field",
        "boolean-revision",
        "unbounded-metadata",
    ],
)
def test_scenario_f_malformed_message_input_fails_before_orchestration(
    body: dict[str, Any],
) -> None:
    backend = _build_backend()
    client = _client_with_sessions(backend, SESSION_ID)

    response = client.post(f"/v1/sessions/{SESSION_ID}/messages", json=body)

    assert response.status_code == 400
    error = response.json()["error"]
    assert error["code"] == ApplicationErrorCode.INVALID_REQUEST.value
    assert "detail" not in response.json()
    _assert_orchestration_not_invoked(backend)


def test_scenario_f_unknown_session_fails_before_orchestration() -> None:
    backend = _build_backend()
    client = _client(backend)

    response = _submit_message(client, session_id="session-missing")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == (
        ApplicationErrorCode.RESOURCE_NOT_FOUND.value
    )
    _assert_orchestration_not_invoked(backend)


def test_scenario_f_transport_defects_fail_before_orchestration() -> None:
    backend = _build_backend()
    client = _client_with_sessions(backend, SESSION_ID)

    oversized_key = _submit_message(client, idempotency_key="k" * 300)
    assert oversized_key.status_code == 400
    assert oversized_key.json()["error"]["details"]["reason_code"] == (
        REASON_INVALID_IDEMPOTENCY_KEY
    )

    oversized_request_id = _client(backend).get(
        "/v1/health", headers={REQUEST_ID_HEADER: "r" * 300}
    )
    assert oversized_request_id.status_code == 400
    assert oversized_request_id.json()["error"]["details"]["reason_code"] == (
        REASON_INVALID_REQUEST_ID
    )

    blank_message_id = _submit_message(client, message_id="   ")
    assert blank_message_id.status_code == 400
    assert blank_message_id.json()["error"]["code"] == (
        ApplicationErrorCode.INVALID_REQUEST.value
    )

    _assert_orchestration_not_invoked(backend)


def test_scenario_f_malformed_session_create_fails_closed() -> None:
    backend = _build_backend()
    client = _client(backend)

    response = client.post("/v1/sessions", json={"session_id": ""})

    assert response.status_code == 400
    assert response.json()["error"]["details"]["reason_code"] == (
        REASON_INVALID_REQUEST_BODY
    )
    assert backend.session_store.load("") is None
    _assert_orchestration_not_invoked(backend)


# ══════════════════════════════════════════════════════════════════════════
# Scenario G — unsupported version
# ══════════════════════════════════════════════════════════════════════════


def test_scenario_g_the_public_contract_rejects_an_unsupported_version() -> None:
    with pytest.raises(ValueError):
        ApplicationQuery(
            request_id="request-g-contract",
            api_version="v2",
            operation=ApplicationOperation.HEALTH_GET,
        )


def test_scenario_g_a_tampered_version_fails_safely_before_orchestration() -> None:
    backend = _build_backend()
    request = ApplicationQuery(
        request_id="request-g",
        api_version=APPLICATION_API_VERSION,
        operation=ApplicationOperation.HEALTH_GET,
    )
    object.__setattr__(request, "api_version", "v2")

    response = backend.gateway.handle(request)

    assert response.status is ApplicationStatus.FAILED
    assert response.error.code is ApplicationErrorCode.UNSUPPORTED_VERSION
    assert response.error.message == "Application API version is not supported"
    assert response.error.retryable is False
    assert response.data is None
    _assert_orchestration_not_invoked(backend)


def test_scenario_g_http_serves_no_v2_route() -> None:
    backend = _build_backend()
    client = _client(backend)

    paths = {route.path for route in backend.app.routes}
    assert not [path for path in paths if path.startswith("/v2")]
    assert {path for path in paths if path.startswith("/v1")} == {
        "/v1/health",
        "/v1/capabilities",
        "/v1/sessions",
        "/v1/sessions/{session_id}",
        "/v1/sessions/{session_id}/messages",
        "/v1/sessions/{session_id}/messages/stream",
        "/v1/requests/{request_id}/cancel",
    }

    for response in (
        client.get("/v2/health"),
        client.post("/v2/sessions", json={"session_id": SESSION_ID}),
    ):
        assert response.status_code == 404
        body = response.json()
        assert body["api_version"] == APPLICATION_API_VERSION
        assert body["error"]["code"] == (ApplicationErrorCode.RESOURCE_NOT_FOUND.value)
        assert body["error"]["details"]["reason_code"] == REASON_UNKNOWN_ROUTE
        assert "detail" not in body

    _assert_orchestration_not_invoked(backend)


# ══════════════════════════════════════════════════════════════════════════
# Scenario H — internal defect is safe
# ══════════════════════════════════════════════════════════════════════════


def test_scenario_h_canonical_defect_becomes_a_safe_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    backend = _build_backend()
    client = _client_with_sessions(backend, SESSION_ID)

    def _defective_orchestrate(request: object) -> object:
        raise RuntimeError(RAW_DEFECT_TEXT)

    monkeypatch.setattr(backend.orchestrator, "orchestrate", _defective_orchestrate)

    response = _submit_message(client, request_id="request-h", idempotency_key="key-h")

    assert response.status_code == 500
    body = response.json()

    assert body["status"] == ApplicationStatus.FAILED.value
    assert body["data"] is None
    assert body["error"]["code"] == ApplicationErrorCode.INTERNAL_FAILURE.value
    assert body["error"]["message"] == GENERIC_FAILURE_MESSAGE
    assert body["error"]["details"] == {}
    assert "detail" not in body

    leaked = response.text
    assert RAW_DEFECT_TEXT not in leaked
    assert "AKIA-EXAMPLE-SECRET-KEY" not in leaked
    assert "Traceback" not in leaked
    assert "RuntimeError" not in leaked
    assert "/private/tmp" not in leaked

    # No canonical decision exists for the defective request and the defect is
    # not pinned to the caller's idempotency key.
    assert backend.repository.get_by_request_id("request-h") is None
    assert _events_for(backend, "request-h") == []
    assert backend.idempotency.get("key-h") is None


def test_scenario_h_application_defect_in_a_service_is_safe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    backend = _build_backend()
    client = _client_with_sessions(backend, SESSION_ID)

    def _defective_create_session(session_id: str) -> object:
        raise ValueError(RAW_DEFECT_TEXT)

    monkeypatch.setattr(backend.sessions, "create_session", _defective_create_session)

    response = client.post("/v1/sessions", json={"session_id": "session-h"})

    assert response.status_code == 500
    assert response.json()["error"]["code"] == (
        ApplicationErrorCode.INTERNAL_FAILURE.value
    )
    assert response.json()["error"]["message"] == GENERIC_FAILURE_MESSAGE
    assert "AKIA-EXAMPLE-SECRET-KEY" not in response.text
    _assert_orchestration_not_invoked(backend)


# ══════════════════════════════════════════════════════════════════════════
# Scenario I — idempotent replay
# ══════════════════════════════════════════════════════════════════════════


def test_scenario_i_same_key_and_command_replays_one_orchestration() -> None:
    backend = _build_backend()
    client = _client_with_sessions(backend, SESSION_ID)

    first = _submit_message(client, request_id="request-i", idempotency_key="key-i")
    second = _submit_message(client, request_id="request-i-2", idempotency_key="key-i")

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json() == first.json()
    assert first.json()["data"]["decision_id"] == "orchestration-decision:request-i"
    # The replayed response keeps the stored correlation identity.
    assert second.headers[REQUEST_ID_HEADER] == "request-i"

    assert _request_received_ids(backend) == ["request-i"]
    records = backend.repository.list_for_session(SESSION_ID)
    assert len(records) == 1
    assert records[0].request_id == "request-i"

    stored = backend.idempotency.get("key-i")
    assert stored is not None
    assert stored.response.request_id == "request-i"
    assert stored.response.to_dict() == first.json()


def test_scenario_i_replay_is_not_an_authority_bypass() -> None:
    backend = _build_backend()
    client = _client_with_sessions(backend, SESSION_ID)

    _submit_message(client, request_id="request-i", idempotency_key="key-i")
    _submit_message(client, request_id="request-i-2", idempotency_key="key-i")

    # The replay served the stored safe response: no second canonical decision,
    # no downstream execution and no new capability was created.
    assert backend.repository.list_for_session(SESSION_ID)[0].request_id == (
        "request-i"
    )
    assert backend.execution_probe.calls == []
    assert backend.agent_service.resolver.attempts == 0


# ══════════════════════════════════════════════════════════════════════════
# Scenario J — idempotency conflict
# ══════════════════════════════════════════════════════════════════════════


def test_scenario_j_same_key_with_changed_content_is_a_conflict() -> None:
    backend = _build_backend()
    client = _client_with_sessions(backend, SESSION_ID)

    first = _submit_message(client, request_id="request-j", idempotency_key="key-j")
    conflict = _submit_message(
        client,
        request_id="request-j-2",
        idempotency_key="key-j",
        content="A materially different question",
    )

    assert first.status_code == 200
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == (
        ApplicationErrorCode.IDEMPOTENCY_CONFLICT.value
    )
    assert conflict.json()["error"]["retryable"] is False
    assert "A materially different question" not in conflict.text

    # The stored binding and the canonical decision are unchanged.
    assert backend.idempotency.get("key-j").response.request_id == "request-j"
    assert _request_received_ids(backend) == ["request-j"]


def test_scenario_j_same_key_against_another_session_is_a_conflict() -> None:
    backend = _build_backend()
    client = _client_with_sessions(backend, SESSION_ID, OTHER_SESSION_ID)

    first = _submit_message(client, request_id="request-j", idempotency_key="key-j")
    conflict = _submit_message(
        client,
        session_id=OTHER_SESSION_ID,
        request_id="request-j-2",
        idempotency_key="key-j",
    )

    assert first.status_code == 200
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == (
        ApplicationErrorCode.IDEMPOTENCY_CONFLICT.value
    )
    assert _request_received_ids(backend) == ["request-j"]
    assert backend.repository.list_for_session(OTHER_SESSION_ID) == ()


# ══════════════════════════════════════════════════════════════════════════
# Scenarios I/J (concurrent) — atomic keyed idempotency, Audit V1 MAJOR-01
# ══════════════════════════════════════════════════════════════════════════

#: Bound on the forced lookup race.  Against a gateway without an atomic keyed
#: critical section both callers reach the lookup together and the gate releases
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
            target=_run, args=(index, target), name=f"backend-worker-{index}"
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


def _observe_stored_records(
    monkeypatch: pytest.MonkeyPatch,
    backend: ApplicationBackend,
    stored: list[IdempotencyRecord],
) -> None:
    """Record every idempotency record the official repository stores."""

    stored_put = backend.idempotency.put

    def observed_put(record: IdempotencyRecord) -> None:
        stored_put(record)
        stored.append(record)

    monkeypatch.setattr(backend.idempotency, "put", observed_put)


def _force_repository_lookup_race(
    monkeypatch: pytest.MonkeyPatch,
    backend: ApplicationBackend,
) -> None:
    """Force the concurrent interleaving Independent Audit V1 reproduced.

    Audit V1 showed that two concurrent same-key commands can both observe
    ``get(key) -> None`` before either stores its result, and reproduced it by
    synchronizing two gateway calls right after the repository lookup.  This
    test-only gate reproduces exactly that window on the real composed graph.
    The gate never serializes the callers itself, so it can not stand in for the
    atomic critical section under test.  It is local to this file for the same
    reason the graph fixture is: no cross-module test import.
    """

    barrier = threading.Barrier(2, timeout=_LOOKUP_GATE_TIMEOUT)
    stored_lookup = backend.idempotency.get

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

    monkeypatch.setattr(backend.idempotency, "get", gated_lookup)


def _message_command(
    *,
    request_id: str,
    idempotency_key: str,
    content: str = MESSAGE_CONTENT,
) -> ApplicationCommand:
    """Shape one keyed message command exactly as the v1 adapter shapes it.

    The identity, content type and payload keys mirror ``cmm.api``'s message
    builder; the message identity is supplied explicitly so two callers of one
    key describe one canonical message rather than two.
    """

    return ApplicationCommand(
        request_id=request_id,
        api_version=APPLICATION_API_VERSION,
        operation=ApplicationOperation.MESSAGE_SUBMIT,
        actor_id=ACTOR_ID,
        session_id=SESSION_ID,
        idempotency_key=idempotency_key,
        payload={
            "message_id": f"message-{idempotency_key}",
            "content": content,
            "content_type": "text/plain",
            "metadata": {},
        },
    )


def test_scenario_i_concurrent_equivalent_commands_reach_the_owner_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Two simultaneous equivalent keyed commands are one canonical operation.

    Audit V1 reproduced duplicate canonical processing by letting two same-key
    commands both observe an absent idempotency record.  This connected scenario
    forces the same interleaving through the real gateway over the real
    Orchestrator and asserts the canonical effects, not only the responses: one
    ``orchestration.request_received`` event, one canonical decision record and
    one idempotency record.
    """

    backend = _build_backend()
    _client_with_sessions(backend, SESSION_ID)
    stored: list[IdempotencyRecord] = []
    _observe_stored_records(monkeypatch, backend, stored)
    _force_repository_lookup_race(monkeypatch, backend)

    responses = _run_concurrently(
        (
            lambda: backend.gateway.handle(
                _message_command(
                    request_id="request-race-1", idempotency_key="key-race"
                )
            ),
            lambda: backend.gateway.handle(
                _message_command(
                    request_id="request-race-2", idempotency_key="key-race"
                )
            ),
        )
    )

    received = _request_received_ids(backend)
    decisions = backend.repository.list_for_session(SESSION_ID)

    # One keyed command reached the canonical owner; the other replayed the one
    # stored safe response.
    assert len(received) == 1
    assert len(decisions) == 1
    assert len(stored) == 1
    assert backend.idempotency.get("key-race") is stored[0]

    # Both callers observe the same one-operation result, honestly at the
    # clarification boundary this graph reaches, and neither is a conflict.
    assert {response.status for response in responses} == {
        ApplicationStatus.NEEDS_CLARIFICATION
    }
    assert responses[0] == responses[1]
    assert decisions[0].request_id == received[0]
    assert responses[0].request_id == received[0]

    # The replay bypassed no authority and executed nothing downstream.
    assert backend.execution_probe.calls == []
    assert backend.agent_service.resolver.attempts == 0


def test_scenario_j_concurrent_conflicting_commands_reject_before_execution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A simultaneous same-key conflicting command never reaches the owner.

    Same key, materially different content: at most one canonical execution,
    exactly one ``IDEMPOTENCY_CONFLICT`` and no second canonical decision.
    """

    backend = _build_backend()
    _client_with_sessions(backend, SESSION_ID)
    stored: list[IdempotencyRecord] = []
    _observe_stored_records(monkeypatch, backend, stored)
    _force_repository_lookup_race(monkeypatch, backend)

    responses = _run_concurrently(
        (
            lambda: backend.gateway.handle(
                _message_command(
                    request_id="request-race-1", idempotency_key="key-race"
                )
            ),
            lambda: backend.gateway.handle(
                _message_command(
                    request_id="request-race-2",
                    idempotency_key="key-race",
                    content="A materially different question",
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

    assert len(conflicts) == 1
    assert len(_request_received_ids(backend)) == 1
    assert len(backend.repository.list_for_session(SESSION_ID)) == 1
    assert len(stored) == 1

    # The rejected command changed no canonical state and leaked no content.
    assert "A materially different question" not in json.dumps(conflicts[0].to_dict())
    assert backend.execution_probe.calls == []
    assert backend.agent_service.resolver.attempts == 0


# ══════════════════════════════════════════════════════════════════════════
# Scenario K — session revision conflict
# ══════════════════════════════════════════════════════════════════════════


def test_scenario_k_stale_expected_revision_is_a_concurrency_conflict() -> None:
    backend = _build_backend()
    client = _client_with_sessions(backend, SESSION_ID)

    stale = _submit_message(
        client, request_id="request-k", expected_session_revision=99
    )

    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == (
        ApplicationErrorCode.CONCURRENCY_CONFLICT.value
    )
    assert stale.json()["error"]["retryable"] is True
    assert stale.json()["error"]["details"]["reason_code"] == ("SESSION_REVISION_STALE")

    # The stale command never reached the canonical pipeline.
    _assert_orchestration_not_invoked(backend)
    assert backend.session_store.load(SESSION_ID).revision == 1


def test_scenario_k_matching_expected_revision_is_accepted() -> None:
    backend = _build_backend()
    client = _client_with_sessions(backend, SESSION_ID)

    rejected = _submit_message(
        client, request_id="request-k-stale", expected_session_revision=99
    )
    accepted = _submit_message(
        client, request_id="request-k-ok", expected_session_revision=1
    )

    assert rejected.status_code == 409
    assert accepted.status_code == 200
    assert accepted.json()["data"]["decision_id"] == (
        "orchestration-decision:request-k-ok"
    )
    # Only the accepted command created canonical history.
    assert _request_received_ids(backend) == ["request-k-ok"]
    assert backend.repository.list_for_session(SESSION_ID)[0].request_id == (
        "request-k-ok"
    )


# ══════════════════════════════════════════════════════════════════════════
# Scenario L — unavailable capability
# ══════════════════════════════════════════════════════════════════════════


def test_scenario_l_cancellation_reports_capability_unavailable() -> None:
    backend = _build_backend()
    client = _client(backend)

    response = client.post(
        "/v1/requests/request-l/cancel",
        headers={
            REQUEST_ID_HEADER: "request-l",
            IDEMPOTENCY_KEY_HEADER: "key-l",
        },
    )

    assert response.status_code == 503
    body = response.json()

    assert body["status"] == ApplicationStatus.FAILED.value
    assert body["data"] is None
    assert body["error"]["code"] == (ApplicationErrorCode.CAPABILITY_UNAVAILABLE.value)
    assert body["error"]["message"] == CANCELLATION_UNAVAILABLE_MESSAGE
    assert body["error"]["retryable"] is False
    assert body["error"]["details"] == {}

    # No canonical owner was consulted and the keyed command was not recorded.
    _assert_orchestration_not_invoked(backend)
    assert backend.idempotency.get("key-l") is None


def test_scenario_l_no_cancellation_runtime_is_created() -> None:
    backend = _build_backend()
    client = _client(backend)

    before = {service.service_id for service in backend.container.snapshot().services}

    response = client.post("/v1/requests/request-l/cancel")

    after = {service.service_id for service in backend.container.snapshot().services}
    assert response.status_code == 503
    assert after == before
    assert not [service_id for service_id in after if "cancel" in service_id]

    declared = {
        capability["capability_id"]: capability
        for capability in client.get("/v1/capabilities").json()["data"]["capabilities"]
    }
    cancellation = declared["request-cancellation"]

    assert cancellation["status"] == CapabilityStatus.UNAVAILABLE.value
    assert cancellation["reason_code"] == REASON_CANCELLATION_UNAVAILABLE
    assert cancellation["operations"] == []
    _assert_orchestration_not_invoked(backend)


# ══════════════════════════════════════════════════════════════════════════
# Scenario M — HTTP cannot bypass the application layer
# ══════════════════════════════════════════════════════════════════════════

#: Canonical owners the transport adapter must never reach directly.
CANONICAL_AUTHORITY_TYPES = (
    Orchestrator,
    CanonicalDomainRouter,
    CanonicalAgentRouter,
    AgentRegistryService,
    DomainRegistry,
    InMemorySessionStore,
    InMemoryOrchestrationDecisionRepository,
    RecordingOrchestrationEventSink,
    ProviderRegistry,
    ExecutorRegistry,
    InMemoryWorkflowRegistry,
    ApplicationContainer,
    IntegrationServiceRegistry,
)


def _closure_values(value: object) -> list[object]:
    """Return the closure cell contents of *value*, if it is a function."""

    values: list[object] = []
    for cell in getattr(value, "__closure__", None) or ():
        try:
            values.append(cell.cell_contents)
        except ValueError:  # pragma: no cover - an empty closure cell
            continue
    return values


def _module_globals(value: object) -> dict[str, Any] | None:
    """Return the adapter module globals of *value*, if it is an adapter function.

    Only ``cmm.api`` globals are expanded: the gate is about what the transport
    module itself can reach, so unrelated packages are not walked.
    """

    mapping = getattr(value, "__globals__", None)
    if not isinstance(mapping, dict):
        return None
    name = mapping.get("__name__")
    return mapping if isinstance(name, str) and name.startswith("cmm.api") else None


def _reachable_values(entrypoints: list[object]) -> list[object]:
    """Return every value reachable from *entrypoints* through live wiring."""

    found: list[object] = []
    seen: set[int] = set()
    frontier = list(entrypoints)

    while frontier:
        value = frontier.pop()
        if id(value) in seen:
            continue
        seen.add(id(value))
        found.append(value)
        frontier.extend(_closure_values(value))
        adapter_globals = _module_globals(value)
        if adapter_globals is not None:
            frontier.extend(adapter_globals.values())

    return found


def _dependant_calls(dependant: object) -> list[object]:
    """Return every callable in one FastAPI dependency graph node."""

    calls: list[object] = []
    call = getattr(dependant, "call", None)
    if call is not None:
        calls.append(call)
    for dependency in getattr(dependant, "dependencies", None) or ():
        calls.extend(_dependant_calls(dependency))
    return calls


def _route_entrypoints(app: FastAPI) -> list[object]:
    """Return the endpoint and dependency callables of every served route."""

    entrypoints: list[object] = []
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        entrypoints.append(route.endpoint)
        entrypoints.extend(_dependant_calls(route.dependant))
    return entrypoints


def test_scenario_m_http_reaches_only_the_application_gateway() -> None:
    backend = _build_backend()

    assert backend.app.state.application_gateway is backend.gateway

    reachable = _reachable_values(_route_entrypoints(backend.app))
    gateways = [value for value in reachable if isinstance(value, ApplicationGateway)]

    assert gateways == [backend.gateway]
    for value in reachable:
        assert not isinstance(value, CANONICAL_AUTHORITY_TYPES), (
            f"the transport adapter reaches {type(value).__name__} directly"
        )
        assert value is not backend.session_store
        assert value is not backend.repository
        assert value is not backend.sink


def test_scenario_m_route_wiring_exposes_application_contracts_only() -> None:
    backend = _build_backend()

    for route in backend.app.routes:
        if not isinstance(route, APIRoute):
            continue
        assert route.path.startswith("/v1")

    entrypoints = _route_entrypoints(backend.app)
    # Every route is an adapter over the one gateway; the adapter binds the
    # application contracts it dispatches with instead of canonical owners.
    assert entrypoints
    for entrypoint in entrypoints:
        for value in _closure_values(entrypoint):
            assert not isinstance(value, CANONICAL_AUTHORITY_TYPES)

    assert (
        len({route.path for route in backend.app.routes if isinstance(route, APIRoute)})
        == 7
    )


def test_scenario_m_the_gateway_is_the_one_public_entrypoint() -> None:
    backend = _build_backend()

    public = {name for name in vars(ApplicationGateway) if not name.startswith("_")}
    # No second entrypoint name exists: the boundary is ``handle`` only.
    assert public == {"handle"}
    assert not hasattr(backend.gateway, "invoke")
    assert not hasattr(backend.gateway, "execute")
    assert not hasattr(backend.gateway, "dispatch")


# ══════════════════════════════════════════════════════════════════════════
# Cross-scenario invariants
# ══════════════════════════════════════════════════════════════════════════


def test_every_public_scenario_keeps_the_phase_11_2_execution_boundary() -> None:
    backend = _build_backend(agent_capabilities=("knowledge.read",))
    client = _client_with_sessions(backend, SESSION_ID)

    _submit_message(client, request_id="invariant-message")
    _submit_message(
        client,
        request_id="invariant-stale",
        expected_session_revision=99,
    )
    client.post("/v1/requests/invariant-cancel/cancel")
    client.get("/v1/health")
    client.get("/v1/capabilities")
    client.get(f"/v1/sessions/{SESSION_ID}")
    backend.orchestrator.orchestrate(
        _canonical_request(
            "invariant-goal",
            input_payload={"goal": {"title": "Complete task"}},
            capabilities=("knowledge.read",),
        )
    )

    assert backend.execution_probe.calls == []


def test_the_composed_graph_serializes_safely() -> None:
    backend = _build_backend()

    payload = backend.container.snapshot().to_dict()

    assert json.loads(json.dumps(payload, sort_keys=True)) == payload
    assert payload["state"] == "ready"
