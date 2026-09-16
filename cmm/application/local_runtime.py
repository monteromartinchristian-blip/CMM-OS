"""Phase 11.4 — the canonical local application runtime composition.

Design Point: ``DP-104`` — Single-Front-Door Fail-Closed Operational CLI

A standalone public CLI needs a real ``ApplicationGateway`` without starting a
server, a worker or an external provider.  ``build_local_application_runtime()``
is that one composition helper: it assembles the same official in-memory
canonical graph the Phase 11.3 connected acceptance proves, and hands back the
composed container, the one gateway the container exposes and the canonical
orchestrator behind it.

This module is the application package's **composition root**, and that is the
only reason it reaches canonical components: a composition root must name what it
wires.  It is not an authority — it defines no registry, store, router or engine
of its own, substitutes no canonical class, loads no external provider, opens no
socket, starts no worker or server, writes no file and mutates no global state.
Every call builds a fresh, independent graph, so two runtimes in one process can
never share state.  The composition-root exemption in the package architecture
gate is exact and guarded to this one module; every other application module
stays inside the frozen transport-neutral core allowlist.

Content decisions:

- domain content comes from the repository's own official integration path
  (``cmm.domains.general`` / ``health`` / ``university``), so the local graph
  carries canonical domain definitions instead of hand-written stand-ins;
- no canonical agent content exists, so the official ``AgentRegistryService`` is
  composed with no agents rather than seeded with an invented one;
- no execution delegate is installed, so the canonical
  ``AgentExecutionAdapter`` reports ``operation.no_execution_delegate`` instead
  of pretending to execute anything.

See ``docs/reference/phase-11-cli.md``.
"""

from __future__ import annotations

from dataclasses import dataclass

from cmm.agent_runtime.action_budget_service import ActionBudgetService
from cmm.agent_runtime.agent_factory import AgentFactoryRegistry
from cmm.agent_runtime.agent_registry import AgentRegistry
from cmm.agent_runtime.agent_registry_service import AgentRegistryService
from cmm.agent_runtime.agent_registry_store import InMemoryAgentRegistryStore
from cmm.agent_runtime.agent_runtime_integration_service import (
    AgentRuntimeIntegrationService,
)
from cmm.agent_runtime.agent_runtime_integration_store import (
    InMemoryAgentRuntimeIntegrationStore,
)
from cmm.agent_runtime.agent_security_service import AgentSecurityService
from cmm.agent_runtime.goal_manager import GoalManager
from cmm.agent_runtime.operation_execution_adapter import AgentExecutionAdapter
from cmm.agent_runtime.operation_registry import InMemoryAgentOperationRegistry
from cmm.agent_runtime.runtime_loop import AgentRuntimeLoop
from cmm.application.capabilities import (
    CapabilityApplicationService,
    build_default_capabilities,
)
from cmm.application.gateway import ApplicationGateway
from cmm.application.health import HealthApplicationService
from cmm.application.idempotency import InMemoryIdempotencyRepository
from cmm.application.platform_module import (
    APPLICATION_MODULE_ID,
    APPLICATION_SERVICE_ID,
    build_application_composition_module,
)
from cmm.application.requests import RequestApplicationService
from cmm.application.sessions import SessionApplicationService
from cmm.cognitive.reasoning_rule_registry import InMemoryReasoningRuleRegistry
from cmm.domains.general.definition import GENERAL_DOMAIN_ID
from cmm.domains.general.integration import register_general_domain
from cmm.domains.health.definition import HEALTH_DOMAIN_ID
from cmm.domains.health.integration import register_health_domain
from cmm.domains.identifiers import DomainId
from cmm.domains.operation_registry import InMemoryDomainOperationRegistry
from cmm.domains.permission_registry import DomainPermissionRegistry
from cmm.domains.permission_resolution import DomainPermissionResolver
from cmm.domains.profile_registry import InMemoryDomainProfileRegistry
from cmm.domains.registry import DomainRegistry
from cmm.domains.resolution_builder import DomainResolutionContextBuilder
from cmm.domains.resolver import DefaultDomainResolver
from cmm.domains.resource_registry import InMemoryDomainResourceRegistry
from cmm.domains.university.definition import UNIVERSITY_DOMAIN_ID
from cmm.domains.university.integration import register_university_domain
from cmm.domains.workflow_registry import InMemoryDomainWorkflowRegistry
from cmm.execution.executor_registry import ExecutorRegistry
from cmm.orchestration.agent_router import CanonicalAgentRouter
from cmm.orchestration.context import DefaultContextResolver
from cmm.orchestration.contracts import OrchestrationChannel
from cmm.orchestration.decision_repository import (
    InMemoryOrchestrationDecisionRepository,
)
from cmm.orchestration.domain_router import CanonicalDomainRouter
from cmm.orchestration.events import RecordingOrchestrationEventSink
from cmm.orchestration.intent import DeterministicIntentResolver
from cmm.orchestration.orchestrator import Orchestrator
from cmm.orchestration.platform_module import (
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
from cmm.platform.modules import StaticCompositionModule
from cmm.runtime.sessions import InMemorySessionStore
from cmm.workflows.registry import InMemoryWorkflowRegistry
from kernel.llm.provider_registry import ProviderRegistry

__all__ = ["LocalApplicationRuntime", "build_local_application_runtime"]

#: The canonical services this composition binds beside the orchestration ones.
CANONICAL_SERVICE_IDS: tuple[str, ...] = (
    "agent.runtime.integration",
    "domain.registry",
    "execution.registry",
    "provider.registry",
    "workflow.registry",
)

#: The canonical core domains the local graph enables.  Each is registered
#: through its own official integration path, so the graph carries canonical
#: definitions rather than local stand-ins.
CORE_DOMAIN_IDS: tuple[str, ...] = (
    GENERAL_DOMAIN_ID,
    HEALTH_DOMAIN_ID,
    UNIVERSITY_DOMAIN_ID,
)

#: Every channel the local policy admits, stated explicitly so a future default
#: change can not silently remove the CLI channel this phase depends on.
LOCAL_ALLOWED_CHANNELS: tuple[OrchestrationChannel, ...] = (
    OrchestrationChannel.CONVERSATION,
    OrchestrationChannel.CLI,
    OrchestrationChannel.INTERNAL,
    OrchestrationChannel.API,
)


@dataclass(frozen=True, slots=True)
class LocalApplicationRuntime:
    """One composed local application graph.

    ``container`` is the composition that exposes ``application.gateway``,
    ``gateway`` is that one gateway, and ``orchestrator`` is the canonical
    orchestrator its message path reaches.
    """

    container: ApplicationContainer
    gateway: ApplicationGateway
    orchestrator: Orchestrator


@dataclass(frozen=True, slots=True)
class _DomainGraph:
    """The canonical domain graph, built with no local stand-in definitions."""

    registry: DomainRegistry
    profiles: InMemoryDomainProfileRegistry
    permissions: DomainPermissionRegistry
    resolver: DefaultDomainResolver


@dataclass(frozen=True, slots=True)
class _OrchestrationGraph:
    """The canonical orchestration graph and the objects composition binds."""

    orchestrator: Orchestrator
    decisions: InMemoryOrchestrationDecisionRepository
    events: RecordingOrchestrationEventSink
    context_resolver: DefaultContextResolver
    domain_router: CanonicalDomainRouter
    agent_router: CanonicalAgentRouter
    agent_service: AgentRegistryService
    session_store: InMemorySessionStore
    intent_resolver: DeterministicIntentResolver
    policy: DefaultOrchestrationPolicy
    domains: _DomainGraph


def _build_domain_graph() -> _DomainGraph:
    """Build the canonical core-domain graph through each domain's own path."""

    registry = DomainRegistry()
    profiles = InMemoryDomainProfileRegistry()
    resources = InMemoryDomainResourceRegistry()
    rules = InMemoryReasoningRuleRegistry()
    operations = InMemoryDomainOperationRegistry(InMemoryAgentOperationRegistry())
    workflows = InMemoryDomainWorkflowRegistry(InMemoryWorkflowRegistry())
    permissions = DomainPermissionRegistry()

    registrations = (
        register_general_domain,
        register_health_domain,
        register_university_domain,
    )
    for register_domain in registrations:
        register_domain(
            domain_registry=registry,
            profile_registry=profiles,
            resource_registry=resources,
            rule_registry=rules,
            operation_registry=operations,
            workflow_registry=workflows,
            permission_registry=permissions,
        )

    for domain_id in CORE_DOMAIN_IDS:
        registry.enable(domain_id)

    return _DomainGraph(
        registry=registry,
        profiles=profiles,
        permissions=permissions,
        resolver=DefaultDomainResolver(
            fallback_domain=DomainId.from_str(GENERAL_DOMAIN_ID)
        ),
    )


def _build_orchestration_graph() -> _OrchestrationGraph:
    """Build the canonical orchestration graph over the local canonical owners."""

    domains = _build_domain_graph()

    domain_router = CanonicalDomainRouter(
        resolver=domains.resolver,
        registry=domains.registry,
        context_builder=DomainResolutionContextBuilder(),
        profile_registry=domains.profiles,
        permission_registry=domains.permissions,
        permission_resolver=DomainPermissionResolver(domains.permissions),
    )

    # No canonical agent content exists, so this composition installs none: the
    # official service is composed empty rather than seeded with an invented one.
    agent_service = AgentRegistryService(
        registry=AgentRegistry(store=InMemoryAgentRegistryStore()),
        factory_registry=AgentFactoryRegistry(),
    )

    session_store = InMemorySessionStore()
    context_resolver = DefaultContextResolver(session_store=session_store)
    policy = DefaultOrchestrationPolicy(
        configuration=OrchestrationConfiguration(
            allowed_channels=LOCAL_ALLOWED_CHANNELS
        )
    )
    decisions = InMemoryOrchestrationDecisionRepository()
    events = RecordingOrchestrationEventSink()
    intent_resolver = DeterministicIntentResolver()
    agent_router = CanonicalAgentRouter(registry_service=agent_service)

    return _OrchestrationGraph(
        orchestrator=Orchestrator(
            intent_resolver=intent_resolver,
            context_resolver=context_resolver,
            domain_router=domain_router,
            agent_router=agent_router,
            policy=policy,
            decision_repository=decisions,
            event_sink=events,
        ),
        decisions=decisions,
        events=events,
        context_resolver=context_resolver,
        domain_router=domain_router,
        agent_router=agent_router,
        agent_service=agent_service,
        session_store=session_store,
        intent_resolver=intent_resolver,
        policy=policy,
        domains=domains,
    )


def _canonical_module(graph: _OrchestrationGraph) -> StaticCompositionModule:
    """Return the canonical composition module of the local graph."""

    agent_runtime_integration = AgentRuntimeIntegrationService(
        store=InMemoryAgentRuntimeIntegrationStore(),
        goal_manager=GoalManager(),
        registry_service=graph.agent_service,
        runtime_loop=AgentRuntimeLoop(goal_repository=GoalManager().repository),
        security_service=AgentSecurityService(),
        budget_service=ActionBudgetService(),
        # Installed with no delegate on purpose: Phase 11.2 stops at route
        # selection and Phase 11.4 executes nothing, so the canonical adapter
        # fails closed rather than inventing an executor or a success.
        execution_adapter=AgentExecutionAdapter(),
    )

    return StaticCompositionModule(
        "canonical",
        (
            domain_registry_binding(graph.domains.registry),
            execution_registry_binding(ExecutorRegistry()),
            provider_registry_binding(ProviderRegistry()),
            workflow_registry_binding(InMemoryWorkflowRegistry()),
            agent_runtime_integration_binding(agent_runtime_integration),
        ),
    )


def _platform_configuration() -> CompositionConfiguration:
    return CompositionConfiguration(
        required_services=(*ORCHESTRATION_SERVICE_IDS, *CANONICAL_SERVICE_IDS),
        enabled_modules=("canonical", "orchestration"),
    )


def _application_configuration() -> CompositionConfiguration:
    return CompositionConfiguration(
        required_services=(
            *ORCHESTRATION_SERVICE_IDS,
            *CANONICAL_SERVICE_IDS,
            APPLICATION_SERVICE_ID,
        ),
        enabled_modules=("canonical", "orchestration", APPLICATION_MODULE_ID),
    )


def build_local_application_runtime() -> LocalApplicationRuntime:
    """Compose one fresh, independent local canonical application runtime.

    The graph is official and in-memory: real canonical registries, the real
    orchestrator, the official application services and the one
    ``ApplicationGateway``.  Nothing global is created, cached or mutated, so
    two calls yield two independent runtimes.

    Two Phase 11.1 containers are used exactly as the composition boundary
    requires: the platform container (canonical + orchestration) is the
    readiness owner the health projection reads, and the application container
    additionally binds ``application.gateway``, because the gateway is the
    object the application module contributes and can not be built from a
    container that already contains it.
    """

    graph = _build_orchestration_graph()
    canonical_module = _canonical_module(graph)
    orchestration_module = build_orchestration_composition_module(
        intent_resolver=graph.intent_resolver,
        context_resolver=graph.context_resolver,
        domain_router=graph.domain_router,
        agent_router=graph.agent_router,
        policy=graph.policy,
        decision_repository=graph.decisions,
        event_sink=graph.events,
        orchestrator=graph.orchestrator,
    )
    platform_container = ApplicationContainer.build(
        _platform_configuration(),
        modules=(canonical_module, orchestration_module),
    )

    sessions = SessionApplicationService(graph.session_store)
    gateway = ApplicationGateway(
        sessions=sessions,
        requests=RequestApplicationService(
            sessions=sessions, orchestrator=graph.orchestrator
        ),
        capabilities=CapabilityApplicationService(build_default_capabilities()),
        health=HealthApplicationService(platform_container),
        idempotency=InMemoryIdempotencyRepository(),
    )

    container = ApplicationContainer.build(
        _application_configuration(),
        modules=(
            canonical_module,
            orchestration_module,
            build_application_composition_module(gateway=gateway),
        ),
    )

    return LocalApplicationRuntime(
        container=container,
        gateway=gateway,
        orchestrator=graph.orchestrator,
    )
