"""Phase 11.2 — connected acceptance test ``AT-DP-102``.

Requirement: ``F11-016`` — Canonical Request Orchestration
Design Point: ``DP-102`` — Fail-Closed Canonical Request Orchestration Pipeline

This is a **connected** acceptance test, not a mock-only unit test.  It builds
the real :class:`~cmm.orchestration.orchestrator.Orchestrator` over real
canonical owners:

* ``cmm.domains`` — ``DomainRegistry``, ``DomainResolutionContextBuilder``,
  ``DefaultDomainResolver``, ``DomainPermissionRegistry`` /
  ``DomainPermissionResolver``, ``InMemoryDomainProfileRegistry``;
* ``cmm.agent_runtime`` — ``AgentRegistry`` over the official in-memory store,
  ``AgentFactoryRegistry``, ``AgentRegistryService`` / ``AgentResolver``;
* ``cmm.runtime.sessions`` — ``InMemorySessionStore``;
* ``cmm.platform`` — ``ApplicationContainer`` / ``StaticCompositionModule``.

Scenario boundary spies are used only to prove that forbidden downstream
actions did **not** occur.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from cmm.agent_runtime.action_budget_service import ActionBudgetService
from cmm.agent_runtime.agent_factory import AgentFactoryRegistry
from cmm.agent_runtime.agent_registry import AgentRegistry
from cmm.agent_runtime.agent_registry_contracts import (
    AgentCapability,
    AgentDescriptor,
    AgentInstance,
    AgentRequirement,
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
from cmm.orchestration.agent_router import AgentRouter, CanonicalAgentRouter
from cmm.orchestration.context import DefaultContextResolver
from cmm.orchestration.contracts import (
    DomainRouteDecision,
    ExecutionRoute,
    IntentKind,
    IntentResolution,
    OrchestrationChannel,
    OrchestrationRequest,
    OrchestrationStatus,
    PolicyDisposition,
)
from cmm.orchestration.decision_repository import (
    InMemoryOrchestrationDecisionRepository,
)
from cmm.orchestration.domain_router import CanonicalDomainRouter, DomainRouter
from cmm.orchestration.events import RecordingOrchestrationEventSink
from cmm.orchestration.intent import DeterministicIntentResolver
from cmm.orchestration.orchestrator import Orchestrator
from cmm.orchestration.platform_module import (
    ORCHESTRATION_AUTHORITY,
    ORCHESTRATION_SERVICE_IDS,
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
from cmm.platform.contracts import (
    ContainerState,
    ServiceBinding,
    ServiceDescriptor,
    ServiceMode,
)
from cmm.platform.errors import DuplicateAuthorityError
from cmm.platform.modules import StaticCompositionModule
from cmm.platform.service_registry import IntegrationServiceRegistry
from cmm.runtime.sessions import InMemorySessionStore, SharedSessionState
from cmm.workflows.registry import InMemoryWorkflowRegistry
from kernel.llm.provider_registry import ProviderRegistry

# ── Canonical fixture constants ──────────────────────────────────────────────

NOW = datetime(2026, 9, 16, tzinfo=timezone.utc)

GENERAL = DomainId(slug="general")
HEALTH = DomainId(slug="health")
UNIVERSITY = DomainId(slug="university")

HEALTH_POLICY_ID = "health.policy"
UNIVERSITY_POLICY_ID = "university.policy"
GENERAL_POLICY_ID = "general.policy"

GENERAL_POLICY = DomainPermissionPolicy(
    policy_id=GENERAL_POLICY_ID,
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

HEALTH_APPROVAL_POLICY = DomainPermissionPolicy(
    policy_id=HEALTH_POLICY_ID,
    domain_id="domain:health",
    version="1.0.0",
    allowed_capabilities=(PermissionCapability.OPERATION_EXECUTE,),
    allowed_operations=("project.inspect",),
    approval_capabilities=(PermissionCapability.OPERATION_EXECUTE,),
)

HEALTH_DENIED_POLICY = DomainPermissionPolicy(
    policy_id=HEALTH_POLICY_ID,
    domain_id="domain:health",
    version="1.0.0",
    prohibited_capabilities=(PermissionCapability.OPERATION_EXECUTE,),
)

UNIVERSITY_DENIED_POLICY = DomainPermissionPolicy(
    policy_id=UNIVERSITY_POLICY_ID,
    domain_id="domain:university",
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

SENSITIVE_MARKER = "sensitive-personal-marker-4f2a"


# ── Boundary spies (forbidden downstream actions only) ───────────────────────


class ForbiddenExecutionProbe:
    """Records any attempt to execute the downstream vertical."""

    def __init__(self) -> None:
        self.calls: list[object] = []

    def execute(self, operation: object) -> dict[str, object]:
        self.calls.append(operation)
        raise AssertionError("Phase 11.2 must never execute an operation")

    def __call__(self, operation: object) -> dict[str, object]:
        return self.execute(operation)


class InMemoryAgentFactory:
    """Official-style in-memory factory satisfying the canonical AgentFactory seam."""

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


# ── Connected graph ──────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class OrchestrationGraph:
    container: ApplicationContainer
    orchestrator: Orchestrator
    repository: InMemoryOrchestrationDecisionRepository
    sink: RecordingOrchestrationEventSink
    context_resolver: DefaultContextResolver
    domain_router: CanonicalDomainRouter
    agent_router: CanonicalAgentRouter
    policy: DefaultOrchestrationPolicy
    session_store: InMemorySessionStore
    agent_service: AgentRegistryService
    execution_probe: ForbiddenExecutionProbe


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


def _session_store(*session_ids: str) -> InMemorySessionStore:
    store = InMemorySessionStore()
    for session_id in session_ids:
        store.save(SharedSessionState(session_id=session_id, status="ACTIVE"))
    return store


def _composition_configuration() -> CompositionConfiguration:
    return CompositionConfiguration(
        required_services=(
            *ORCHESTRATION_SERVICE_IDS,
            "agent.runtime.integration",
            "domain.registry",
            "execution.registry",
            "provider.registry",
            "workflow.registry",
        ),
        enabled_modules=("canonical", "orchestration"),
    )


def _build_graph(
    *,
    policies: tuple[DomainPermissionPolicy, ...] = (GENERAL_POLICY,),
    agent_capabilities: tuple[str, ...] = (),
    channels: tuple[OrchestrationChannel, ...] = ALL_CHANNELS,
    profiles: tuple[DomainProfileDefinition, ...] = (HEALTH_PROFILE,),
) -> OrchestrationGraph:
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

    session_store = _session_store("session-1", "session-2")

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
        configuration=OrchestrationConfiguration(allowed_channels=channels)
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

    container = ApplicationContainer.build(
        _composition_configuration(),
        modules=(canonical_module, orchestration_module),
    )

    return OrchestrationGraph(
        container=container,
        orchestrator=orchestrator,
        repository=repository,
        sink=sink,
        context_resolver=context_resolver,
        domain_router=domain_router,
        agent_router=agent_router,
        policy=policy,
        session_store=session_store,
        agent_service=agent_service,
        execution_probe=probe,
    )


def _request(
    request_id: str,
    *,
    session_id: str | None = "session-1",
    channel: OrchestrationChannel = OrchestrationChannel.CONVERSATION,
    input_payload: dict[str, object] | None = None,
    context: dict[str, object] | None = None,
    capabilities: tuple[str, ...] = (),
) -> OrchestrationRequest:
    return OrchestrationRequest(
        request_id=request_id,
        user_id="user-1",
        channel=channel,
        session_id=session_id,
        input=input_payload if input_payload is not None else {},
        context=context or {},
        requested_capabilities=capabilities,
    )


def _health_signal(confidence: float = 0.9) -> dict[str, object]:
    return {"value": "medical", "domains": ["health"], "confidence": confidence}


def _university_signal(confidence: float = 0.6) -> dict[str, object]:
    return {"value": "study", "domains": ["university"], "confidence": confidence}


# ══════════════════════════════════════════════════════════════════════════
# Scenario A — simple question
# ══════════════════════════════════════════════════════════════════════════


def test_scenario_a_simple_question() -> None:
    graph = _build_graph()

    result = graph.orchestrator.orchestrate(
        _request("request-a", input_payload={"question": "What changed?"})
    )

    assert result.status is OrchestrationStatus.ROUTED
    assert result.intent is IntentKind.QUESTION
    assert result.primary_domain == "domain:general"
    assert result.route is ExecutionRoute.DIRECT_RESPONSE
    assert result.decision_id == "orchestration-decision:request-a"
    assert result.error is None

    record = graph.repository.get(result.decision_id)
    assert record is not None
    assert record.policy_disposition is PolicyDisposition.ALLOW_ROUTE
    assert record.execution_route is ExecutionRoute.DIRECT_RESPONSE
    assert record.session_id == "session-1"

    event_types = [event.event_type for event in graph.sink.events()]
    assert event_types == [
        "orchestration.request_received",
        "orchestration.intent_resolved",
        "orchestration.domain_resolved",
        "orchestration.route_selected",
        "orchestration.routed",
    ]
    assert graph.execution_probe.calls == []


# ══════════════════════════════════════════════════════════════════════════
# Scenario B — domain ambiguity
# ══════════════════════════════════════════════════════════════════════════


def test_scenario_b_domain_ambiguity_needs_clarification() -> None:
    graph = _build_graph()

    result = graph.orchestrator.orchestrate(
        _request(
            "request-b",
            input_payload={"question": "Something changed"},
            context={"explicit_domains": ["health", "university"]},
        )
    )

    assert result.status is OrchestrationStatus.NEEDS_CLARIFICATION
    assert result.primary_domain is None
    assert result.supporting_domains == ()
    assert result.profile_id is None
    assert result.route is ExecutionRoute.NONE
    assert result.decision_id is not None

    record = graph.repository.get(result.decision_id)
    assert record is not None
    assert record.execution_route is ExecutionRoute.NONE
    assert record.policy_disposition is None
    assert graph.execution_probe.calls == []


# ══════════════════════════════════════════════════════════════════════════
# Scenario C — cross-domain restriction
# ══════════════════════════════════════════════════════════════════════════


def test_scenario_c_supporting_domain_cannot_widen_permissions() -> None:
    graph = _build_graph(
        policies=(
            HEALTH_OPERATION_POLICY,
            UNIVERSITY_DENIED_POLICY,
        )
    )

    result = graph.orchestrator.orchestrate(
        _request(
            "request-c",
            input_payload={"command": {"operation": "project.inspect"}},
            context={"domain_signals": [_health_signal(), _university_signal()]},
        )
    )

    # The canonical permission intersection includes the supporting domain, so a
    # supporting-domain denial cannot be bypassed by the primary domain.
    assert result.status is OrchestrationStatus.BLOCKED
    assert result.primary_domain == "domain:health"
    assert result.supporting_domains == ("domain:university",)
    assert result.profile_id == "health.default"

    record = graph.repository.get(result.decision_id)
    assert record is not None
    assert record.policy_disposition is PolicyDisposition.DENY
    assert record.primary_domain == "domain:health"
    assert record.supporting_domains == ("domain:university",)
    assert graph.execution_probe.calls == []


# ══════════════════════════════════════════════════════════════════════════
# Scenario D — denied command
# ══════════════════════════════════════════════════════════════════════════


def test_scenario_d_denied_command_is_blocked() -> None:
    graph = _build_graph(policies=(HEALTH_DENIED_POLICY,))

    result = graph.orchestrator.orchestrate(
        _request(
            "request-d",
            input_payload={"command": {"operation": "project.inspect"}},
            context={"domain_signals": [_health_signal()]},
        )
    )

    assert result.status is OrchestrationStatus.BLOCKED
    assert result.primary_domain == "domain:health"
    assert result.route is ExecutionRoute.OPERATION
    assert result.decision_id is not None

    record = graph.repository.get(result.decision_id)
    assert record is not None
    assert record.policy_disposition is PolicyDisposition.DENY

    terminal = graph.sink.events()[-1]
    assert terminal.event_type == "orchestration.blocked"
    assert graph.execution_probe.calls == []


# ══════════════════════════════════════════════════════════════════════════
# Scenario E — approval required
# ══════════════════════════════════════════════════════════════════════════


def test_scenario_e_approval_required_is_non_executing() -> None:
    graph = _build_graph(policies=(HEALTH_APPROVAL_POLICY,))

    result = graph.orchestrator.orchestrate(
        _request(
            "request-e",
            input_payload={"command": {"operation": "project.inspect"}},
            context={"domain_signals": [_health_signal()]},
        )
    )

    assert result.status is OrchestrationStatus.ROUTED
    assert result.approval_refs
    assert result.route is ExecutionRoute.OPERATION

    record = graph.repository.get(result.decision_id)
    assert record is not None
    assert record.policy_disposition is PolicyDisposition.REQUIRE_APPROVAL
    assert record.approval_refs == result.approval_refs

    terminal = graph.sink.events()[-1]
    assert terminal.event_type == "orchestration.approval_required"
    assert "approval_refs" in terminal.payload
    assert graph.execution_probe.calls == []


# ══════════════════════════════════════════════════════════════════════════
# Scenario F — autonomous goal
# ══════════════════════════════════════════════════════════════════════════


def test_scenario_f_autonomous_goal_uses_the_canonical_agent_registry() -> None:
    graph = _build_graph(agent_capabilities=("knowledge.read",))

    result = graph.orchestrator.orchestrate(
        _request(
            "request-f",
            input_payload={"goal": {"title": "Complete task"}},
            capabilities=("knowledge.read",),
        )
    )

    assert result.status is OrchestrationStatus.ROUTED
    assert result.route is ExecutionRoute.AUTONOMOUS_AGENT
    assert result.agent_id == "agent.alpha"

    # The canonical registry service performed the selection.
    assert graph.agent_service.resolver.attempts == 1
    canonical = graph.agent_service.resolve_agent(
        AgentRequirement(required_capabilities=("knowledge.read",))
    )
    assert canonical.selected is not None
    assert canonical.selected.agent_id == result.agent_id

    record = graph.repository.get(result.decision_id)
    assert record is not None
    assert record.selected_agent_id == "agent.alpha"
    assert record.execution_route is ExecutionRoute.AUTONOMOUS_AGENT
    assert graph.execution_probe.calls == []


# ══════════════════════════════════════════════════════════════════════════
# Scenario G — no compatible agent
# ══════════════════════════════════════════════════════════════════════════


def test_scenario_g_no_compatible_agent_escalates() -> None:
    graph = _build_graph(agent_capabilities=("knowledge.read",))

    result = graph.orchestrator.orchestrate(
        _request(
            "request-g",
            input_payload={"goal": {"title": "Complete task"}},
            capabilities=("operation.execute",),
        )
    )

    assert result.status is OrchestrationStatus.ESCALATED
    assert result.agent_id is None

    record = graph.repository.get(result.decision_id)
    assert record is not None
    assert record.policy_disposition is PolicyDisposition.ESCALATE
    assert record.selected_agent_id is None

    terminal = graph.sink.events()[-1]
    assert terminal.event_type == "orchestration.escalated"
    assert graph.execution_probe.calls == []


# ══════════════════════════════════════════════════════════════════════════
# Scenario H — session resumption
# ══════════════════════════════════════════════════════════════════════════


def test_scenario_h_existing_session_is_loaded_canonically() -> None:
    graph = _build_graph()

    context = graph.context_resolver.resolve_base(
        _request("request-h", input_payload={"question": "What changed?"})
    )

    assert context.session_ref == "session-1"
    assert context.session_status == "ACTIVE"
    assert context.session_revision == 1
    assert "session:session-1" in context.context_refs
    assert context.missing_refs == ()
    # The canonical store itself serves the session.
    assert graph.session_store.load("session-1") is not None

    result = graph.orchestrator.orchestrate(
        _request("request-h", input_payload={"question": "What changed?"})
    )
    assert result.status is OrchestrationStatus.ROUTED
    assert graph.repository.get(result.decision_id).session_id == "session-1"


def test_scenario_h_unknown_session_is_reported_not_invented() -> None:
    graph = _build_graph()

    context = graph.context_resolver.resolve_base(
        _request("request-h2", session_id="session-missing")
    )

    assert context.session_ref is None
    assert context.missing_refs == ("session:session-missing",)

    result = graph.orchestrator.orchestrate(
        _request(
            "request-h2",
            session_id="session-missing",
            input_payload={"question": "What changed?"},
        )
    )
    assert result.status is OrchestrationStatus.NEEDS_CLARIFICATION
    assert "ORCHESTRATION_SESSION_UNRESOLVED" in result.reason_codes


# ══════════════════════════════════════════════════════════════════════════
# Scenario I — context minimization
# ══════════════════════════════════════════════════════════════════════════


def test_scenario_i_unsafe_context_is_not_copied_into_public_surfaces() -> None:
    graph = _build_graph()

    request = _request(
        "request-i",
        input_payload={"question": "What changed?"},
        context={
            "context_refs": ["note-1"],
            "secret_note": SENSITIVE_MARKER,
            "unrelated_field": SENSITIVE_MARKER,
        },
    )

    base = graph.context_resolver.resolve_base(request)
    assert base.context_refs == ("session:session-1", "caller:note-1")
    assert base.withheld_field_count == 2

    result = graph.orchestrator.orchestrate(request)
    record = graph.repository.get(result.decision_id)
    assert record is not None

    surfaces = json.dumps(
        {
            "result": result.to_dict(),
            "record": record.to_dict(),
            "events": [event.to_dict() for event in graph.sink.events()],
        },
        sort_keys=True,
    )

    assert SENSITIVE_MARKER not in surfaces
    assert "secret_note" not in surfaces
    assert "unrelated_field" not in surfaces
    assert "context_refs" not in surfaces


def test_scenario_i_result_carries_no_hidden_reasoning_field() -> None:
    graph = _build_graph()

    payload = graph.orchestrator.orchestrate(
        _request("request-i2", input_payload={"question": "What changed?"})
    ).to_dict()

    for forbidden in (
        "chain_of_thought",
        "hidden_reasoning",
        "raw_reasoning",
        "reasoning_trace",
        "prompt",
        "provider_payload",
    ):
        assert forbidden not in payload


# ══════════════════════════════════════════════════════════════════════════
# Scenario J — multichannel consistency
# ══════════════════════════════════════════════════════════════════════════


def test_scenario_j_every_channel_uses_the_same_core_routing() -> None:
    graph = _build_graph()

    outcomes = {}
    for index, channel in enumerate(ALL_CHANNELS):
        result = graph.orchestrator.orchestrate(
            _request(
                f"request-j-{index}",
                channel=channel,
                input_payload={"question": "What changed?"},
            )
        )
        outcomes[channel] = (
            result.status,
            result.intent,
            result.route,
            result.primary_domain,
        )

    assert len(set(outcomes.values())) == 1
    assert outcomes[OrchestrationChannel.API][0] is OrchestrationStatus.ROUTED


def test_scenario_j_channel_may_only_narrow_policy() -> None:
    graph = _build_graph(
        channels=(
            OrchestrationChannel.CONVERSATION,
            OrchestrationChannel.CLI,
            OrchestrationChannel.INTERNAL,
        )
    )

    denied = graph.orchestrator.orchestrate(
        _request(
            "request-j-api",
            channel=OrchestrationChannel.API,
            input_payload={"question": "What changed?"},
        )
    )
    allowed = graph.orchestrator.orchestrate(
        _request(
            "request-j-cli",
            channel=OrchestrationChannel.CLI,
            input_payload={"question": "What changed?"},
        )
    )

    assert denied.status is OrchestrationStatus.BLOCKED
    assert denied.route is allowed.route
    assert denied.primary_domain == allowed.primary_domain
    assert allowed.status is OrchestrationStatus.ROUTED


# ══════════════════════════════════════════════════════════════════════════
# Scenario K — decision persistence
# ══════════════════════════════════════════════════════════════════════════


def test_scenario_k_every_terminal_decision_is_recorded_exactly_once() -> None:
    graph = _build_graph()

    request_ids = [f"request-k-{index}" for index in range(5)]
    for request_id in request_ids:
        result = graph.orchestrator.orchestrate(
            _request(request_id, input_payload={"question": "What changed?"})
        )
        assert result.decision_id == f"orchestration-decision:{request_id}"

    records = graph.repository.list_for_session("session-1")
    assert len(records) == len(request_ids)
    assert {record.request_id for record in records} == set(request_ids)

    replay = graph.orchestrator.orchestrate(
        _request("request-k-0", input_payload={"question": "What changed?"})
    )
    assert replay.decision_id == "orchestration-decision:request-k-0"
    assert len(graph.repository.list_for_session("session-1")) == len(request_ids)


def test_scenario_k_records_contain_only_safe_categorical_facts() -> None:
    graph = _build_graph()

    result = graph.orchestrator.orchestrate(
        _request(
            "request-k-safe",
            input_payload={"question": "What changed?"},
            context={"secret_note": SENSITIVE_MARKER},
        )
    )
    record = graph.repository.get(result.decision_id)
    assert record is not None

    serialized = json.dumps(record.to_dict(), sort_keys=True)

    assert SENSITIVE_MARKER not in serialized
    assert "What changed?" not in serialized
    assert set(record.to_dict()) == {
        "decision_id",
        "request_id",
        "session_id",
        "channel",
        "intent",
        "primary_domain",
        "supporting_domains",
        "execution_route",
        "policy_disposition",
        "selected_agent_id",
        "workflow_id",
        "approval_refs",
        "reason_codes",
        "trace_refs",
        "occurred_at",
    }


# ══════════════════════════════════════════════════════════════════════════
# Scenario L — Phase 11.1 composition
# ══════════════════════════════════════════════════════════════════════════


def test_scenario_l_container_reaches_ready() -> None:
    graph = _build_graph()

    assert graph.container.state is ContainerState.READY


def test_scenario_l_every_orchestration_binding_satisfies_its_contract() -> None:
    graph = _build_graph()

    snapshot = graph.container.snapshot().to_dict()
    services = {service["service_id"]: service for service in snapshot["services"]}

    assert set(ORCHESTRATION_SERVICE_IDS) <= set(services)
    assert (
        services["orchestration.orchestrator"]["authority"] == ORCHESTRATION_AUTHORITY
    )
    for service_id in ORCHESTRATION_SERVICE_IDS:
        assert services[service_id]["contract_name"] == service_id
        assert services[service_id]["contract_version"]
        assert services[service_id]["schema_version"]
        assert services[service_id]["owner"] == "cmm.orchestration"
        assert services[service_id]["mode"] == "local"
        if service_id == "orchestration.orchestrator":
            continue
        assert services[service_id]["authority"] is None


def test_scenario_l_dependency_graph_is_acyclic_and_ordered() -> None:
    graph = _build_graph()

    snapshot = graph.container.snapshot().to_dict()
    services = {service["service_id"]: service for service in snapshot["services"]}

    # A container only reaches READY after the dependency graph validated, so
    # readiness itself proves the orchestration graph is acyclic.
    assert snapshot["state"] == "ready"
    assert services["orchestration.orchestrator"]["dependency_ids"] == sorted(
        service_id
        for service_id in ORCHESTRATION_SERVICE_IDS
        if service_id != "orchestration.orchestrator"
    )


def test_scenario_l_safe_snapshot_serializes() -> None:
    graph = _build_graph()

    payload = graph.container.snapshot().to_dict()

    assert json.loads(json.dumps(payload, sort_keys=True)) == payload
    assert payload["state"] == "ready"


def test_scenario_l_duplicate_orchestration_authority_fails_closed() -> None:
    """Two services may never claim the orchestration coordinator authority."""

    graph = _build_graph()
    module = build_orchestration_composition_module(
        intent_resolver=DeterministicIntentResolver(),
        context_resolver=graph.context_resolver,
        domain_router=graph.domain_router,
        agent_router=graph.agent_router,
        policy=graph.policy,
        decision_repository=graph.repository,
        event_sink=graph.sink,
        orchestrator=graph.orchestrator,
    )
    real = next(
        binding
        for binding in module.contribute(CompositionConfiguration())
        if binding.descriptor.service_id == "orchestration.orchestrator"
    )

    registry = IntegrationServiceRegistry()
    for binding in module.contribute(CompositionConfiguration()):
        registry.register(binding)

    registry.register(
        ServiceBinding(
            descriptor=ServiceDescriptor(
                service_id="orchestration.impostor",
                contract=real.descriptor.contract,
                implementation_id="tests.orchestration.SecondCoordinator",
                mode=ServiceMode.LOCAL,
                authority=ORCHESTRATION_AUTHORITY,
            ),
            implementation=object(),
        )
    )

    with pytest.raises(DuplicateAuthorityError):
        registry.validate_graph()


def test_scenario_l_orchestration_and_canonical_services_coexist() -> None:
    graph = _build_graph()

    assert (
        graph.container.get_service("orchestration.orchestrator") is graph.orchestrator
    )
    assert graph.container.get_service("domain.registry") is not None
    assert graph.container.get_service("agent.runtime.integration") is not None


# ══════════════════════════════════════════════════════════════════════════
# Scenario M — Audit V1 MAJOR-01: orchestration roles are not cross-wirable
# ══════════════════════════════════════════════════════════════════════════


def _cross_wired_container(
    graph: OrchestrationGraph, domain_router: object, agent_router: object
) -> ApplicationContainer:
    """Build the container on the real composition path with a cross-wired role."""

    return ApplicationContainer.build(
        _composition_configuration(),
        modules=(
            build_orchestration_composition_module(
                intent_resolver=DeterministicIntentResolver(),
                context_resolver=graph.context_resolver,
                domain_router=domain_router,
                agent_router=agent_router,
                policy=graph.policy,
                decision_repository=graph.repository,
                event_sink=graph.sink,
                orchestrator=graph.orchestrator,
            ),
        ),
    )


def test_scenario_m_real_graph_reaches_ready() -> None:
    """The remediation must not stop a correct graph from composing."""

    graph = _build_graph()

    assert graph.container.state is ContainerState.READY


@pytest.mark.parametrize(
    ("domain_role", "agent_role"),
    [("domain_router", "domain_router"), ("agent_router", "agent_router")],
)
def test_scenario_m_cross_wired_roles_can_never_reach_ready(
    domain_role: str, agent_role: str
) -> None:
    """Audit V1 MAJOR-01: the exact cross-wire must fail before ``READY``."""

    graph = _build_graph()

    with pytest.raises(TypeError) as captured:
        _cross_wired_container(
            graph, getattr(graph, domain_role), getattr(graph, agent_role)
        )

    assert "orchestration" in str(captured.value)


def test_scenario_m_domain_router_cannot_claim_the_agent_router_identity() -> None:
    graph = _build_graph()

    with pytest.raises(TypeError):
        _cross_wired_container(graph, graph.domain_router, graph.domain_router)


def test_scenario_m_agent_router_cannot_claim_the_domain_router_identity() -> None:
    graph = _build_graph()

    with pytest.raises(TypeError):
        _cross_wired_container(graph, graph.agent_router, graph.agent_router)


def test_scenario_m_role_methods_are_distinct_over_the_real_routers() -> None:
    graph = _build_graph()

    assert isinstance(graph.domain_router, DomainRouter)
    assert not isinstance(graph.domain_router, AgentRouter)
    assert isinstance(graph.agent_router, AgentRouter)
    assert not isinstance(graph.agent_router, DomainRouter)


def test_scenario_m_real_graph_still_routes_after_the_remediation() -> None:
    graph = _build_graph()

    result = graph.orchestrator.orchestrate(
        _request("request-m", input_payload={"question": "What changed?"})
    )

    assert result.status is OrchestrationStatus.ROUTED
    assert result.primary_domain == "domain:general"
    assert result.route is ExecutionRoute.DIRECT_RESPONSE


# ══════════════════════════════════════════════════════════════════════════
# Scenario N — Audit V1 MAJOR-02: canonical agent selection authority
# ══════════════════════════════════════════════════════════════════════════


class _FakeRegistryService:
    """A noncanonical authority able to fabricate an agent identifier."""

    def __init__(self) -> None:
        self.calls = 0

    def resolve_agent(self, requirement, **kwargs):  # type: ignore[no-untyped-def]
        self.calls += 1
        return SimpleNamespace(
            selected=SimpleNamespace(
                agent_id="forged.agent",
                version=SimpleNamespace(canonical=lambda: "9.9.9"),
            )
        )


def test_scenario_n_noncanonical_agent_authority_is_rejected() -> None:
    """Audit V1 MAJOR-02: a fake selector must never reach agent selection."""

    fake = _FakeRegistryService()

    with pytest.raises(TypeError) as captured:
        CanonicalAgentRouter(registry_service=fake)  # type: ignore[arg-type]

    assert fake.calls == 0
    assert AgentRegistryService.__name__ in str(captured.value)


def test_scenario_n_real_canonical_agent_authority_is_accepted() -> None:
    graph = _build_graph(agent_capabilities=("knowledge.read",))

    assert isinstance(graph.agent_router, AgentRouter)
    assert graph.container.state is ContainerState.READY

    result = graph.orchestrator.orchestrate(
        _request(
            "request-n-real",
            input_payload={"goal": {"title": "Complete task"}},
            capabilities=("knowledge.read",),
        )
    )

    assert result.route is ExecutionRoute.AUTONOMOUS_AGENT
    assert result.agent_id == "agent.alpha"
    assert graph.agent_service.resolver.attempts == 1


def test_scenario_n_no_compatible_canonical_agent_still_escalates() -> None:
    """The canonical no-match path stays owned by the real registry service."""

    graph = _build_graph(agent_capabilities=("knowledge.read",))
    request = _request(
        "request-n-none",
        input_payload={"goal": {"title": "Complete task"}},
        capabilities=("operation.execute",),
    )

    decision = graph.agent_router.route_agent(
        request=request,
        intent=IntentResolution(
            intent=IntentKind.GOAL,
            needs_clarification=False,
            source_kind="structured_input",
        ),
        context=graph.context_resolver.resolve_base(request),
        domain=DomainRouteDecision(status="resolved", primary_domain="domain:general"),
    )

    assert decision.route is ExecutionRoute.HUMAN_ESCALATION
    assert decision.agent_id is None
    assert "AGENT_ROUTING_NO_COMPATIBLE_AGENT" in decision.reason_codes
    assert graph.agent_service.resolver.attempts == 1


# ══════════════════════════════════════════════════════════════════════════
# Cross-scenario invariants
# ══════════════════════════════════════════════════════════════════════════


def test_no_scenario_executes_the_downstream_vertical() -> None:
    graph = _build_graph(agent_capabilities=("knowledge.read",))

    scenarios = (
        _request("probe-a", input_payload={"question": "What changed?"}),
        _request(
            "probe-b",
            input_payload={"question": "Something changed"},
            context={"explicit_domains": ["health", "university"]},
        ),
        _request(
            "probe-d",
            input_payload={"command": {"operation": "project.inspect"}},
            context={"domain_signals": [_health_signal()]},
        ),
        _request(
            "probe-f",
            input_payload={"goal": {"title": "Complete task"}},
            capabilities=("knowledge.read",),
        ),
        _request(
            "probe-g",
            input_payload={"goal": {"title": "Complete task"}},
            capabilities=("operation.execute",),
        ),
        _request(
            "probe-c",
            input_payload={"command": {"operation": "project.inspect"}},
            context={"domain_signals": [_health_signal(), _university_signal()]},
        ),
    )

    for request in scenarios:
        graph.orchestrator.orchestrate(request)

    assert graph.execution_probe.calls == []


def test_every_scenario_produces_exactly_one_terminal_event() -> None:
    graph = _build_graph()

    graph.orchestrator.orchestrate(
        _request("event-a", input_payload={"question": "What changed?"})
    )

    terminal_events = [
        event
        for event in graph.sink.events()
        if event.event_type
        in {
            "orchestration.routed",
            "orchestration.blocked",
            "orchestration.escalated",
            "orchestration.approval_required",
            "orchestration.failed",
        }
    ]

    assert len(terminal_events) == 1
    assert terminal_events[0].event_type == "orchestration.routed"
    assert terminal_events[0].payload["decision_id"] == (
        "orchestration-decision:event-a"
    )
