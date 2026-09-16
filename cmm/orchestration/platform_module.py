"""Phase 11.2 — Phase 11.1 composition contribution.

``build_orchestration_composition_module`` returns a side-effect-free
``StaticCompositionModule`` contribution containing the eight stable
orchestration service bindings.  Phase 11.1 remains the composition core: this
module adds new service bindings only, changes no Phase 11.1 semantics, and
``cmm.platform`` never imports ``cmm.orchestration``.

Every binding declares an enforceable runtime contract — the frozen Phase 11.2
protocol for that role — so an unrelated object can never claim an orchestration
service identity.  Only the global Orchestrator claims an exclusive authority
label; no orchestration binding claims provider, domain, agent, workflow,
execution, validation, memory or knowledge authority.
"""

from __future__ import annotations

from typing import Any

from cmm.orchestration.agent_router import AgentRouter
from cmm.orchestration.context import ContextResolver
from cmm.orchestration.decision_repository import OrchestrationDecisionRepository
from cmm.orchestration.domain_router import DomainRouter
from cmm.orchestration.events import OrchestrationEventSink
from cmm.orchestration.intent import IntentResolver
from cmm.orchestration.orchestrator import OrchestratorProtocol
from cmm.orchestration.policy import OrchestrationPolicy
from cmm.platform.contracts import (
    ContractMetadata,
    ServiceBinding,
    ServiceDependency,
    ServiceDescriptor,
    ServiceMode,
)
from cmm.platform.modules import StaticCompositionModule

__all__ = [
    "ORCHESTRATION_AUTHORITY",
    "ORCHESTRATION_CONTRACT_VERSION",
    "ORCHESTRATION_MODULE_ID",
    "ORCHESTRATION_OWNER",
    "ORCHESTRATION_SCHEMA_VERSION",
    "ORCHESTRATION_SERVICE_IDS",
    "build_orchestration_composition_module",
]

ORCHESTRATION_MODULE_ID = "orchestration"
ORCHESTRATION_OWNER = "cmm.orchestration"
ORCHESTRATION_CONTRACT_VERSION = "1.0.0"
ORCHESTRATION_SCHEMA_VERSION = "1"

#: The one exclusive authority the orchestration layer owns.
ORCHESTRATION_AUTHORITY = "orchestration-request-coordinator"

AGENT_ROUTER_SERVICE_ID = "orchestration.agent_router"
CONTEXT_RESOLVER_SERVICE_ID = "orchestration.context_resolver"
DECISION_REPOSITORY_SERVICE_ID = "orchestration.decision_repository"
DOMAIN_ROUTER_SERVICE_ID = "orchestration.domain_router"
EVENT_SINK_SERVICE_ID = "orchestration.event_sink"
INTENT_RESOLVER_SERVICE_ID = "orchestration.intent_resolver"
ORCHESTRATOR_SERVICE_ID = "orchestration.orchestrator"
POLICY_SERVICE_ID = "orchestration.policy"

#: Stable orchestration service IDs, in canonical (sorted) order.
ORCHESTRATION_SERVICE_IDS: tuple[str, ...] = (
    AGENT_ROUTER_SERVICE_ID,
    CONTEXT_RESOLVER_SERVICE_ID,
    DECISION_REPOSITORY_SERVICE_ID,
    DOMAIN_ROUTER_SERVICE_ID,
    EVENT_SINK_SERVICE_ID,
    INTENT_RESOLVER_SERVICE_ID,
    ORCHESTRATOR_SERVICE_ID,
    POLICY_SERVICE_ID,
)

#: The orchestrator's declared composition dependencies, in sorted order.
ORCHESTRATOR_DEPENDENCY_IDS: tuple[str, ...] = tuple(
    service_id
    for service_id in ORCHESTRATION_SERVICE_IDS
    if service_id != ORCHESTRATOR_SERVICE_ID
)

#: ``service_id -> enforceable runtime contract``.
RUNTIME_CONTRACTS: dict[str, Any] = {
    AGENT_ROUTER_SERVICE_ID: AgentRouter,
    CONTEXT_RESOLVER_SERVICE_ID: ContextResolver,
    DECISION_REPOSITORY_SERVICE_ID: OrchestrationDecisionRepository,
    DOMAIN_ROUTER_SERVICE_ID: DomainRouter,
    EVENT_SINK_SERVICE_ID: OrchestrationEventSink,
    INTENT_RESOLVER_SERVICE_ID: IntentResolver,
    ORCHESTRATOR_SERVICE_ID: OrchestratorProtocol,
    POLICY_SERVICE_ID: OrchestrationPolicy,
}


def _boundary_contract(service_id: str) -> ContractMetadata:
    return ContractMetadata(
        contract_name=service_id,
        contract_version=ORCHESTRATION_CONTRACT_VERSION,
        schema_version=ORCHESTRATION_SCHEMA_VERSION,
        owner=ORCHESTRATION_OWNER,
    )


def _dependency(service_id: str) -> ServiceDependency:
    return ServiceDependency(
        service_id=service_id,
        contract=_boundary_contract(service_id),
    )


def _implementation_id(implementation: Any) -> str:
    implementation_type = type(implementation)
    return f"{implementation_type.__module__}.{implementation_type.__qualname__}"


def _require_role_implementation(
    implementation: Any, service_id: str, runtime_contract: Any
) -> None:
    """Fail closed unless *implementation* satisfies its declared role boundary."""

    if not isinstance(implementation, runtime_contract):
        raise TypeError(
            f"{service_id} implementation does not satisfy its orchestration "
            f"runtime contract {runtime_contract.__name__}"
        )


def _binding(
    implementation: Any,
    service_id: str,
    *,
    authority: str | None = None,
    dependencies: tuple[ServiceDependency, ...] = (),
) -> ServiceBinding:
    """Bind an existing orchestration service without constructing anything."""

    runtime_contract = RUNTIME_CONTRACTS[service_id]
    _require_role_implementation(implementation, service_id, runtime_contract)

    return ServiceBinding(
        descriptor=ServiceDescriptor(
            service_id=service_id,
            contract=_boundary_contract(service_id),
            implementation_id=_implementation_id(implementation),
            dependencies=dependencies,
            mode=ServiceMode.LOCAL,
            authority=authority,
        ),
        implementation=implementation,
        runtime_contract=runtime_contract,
    )


def build_orchestration_composition_module(
    *,
    intent_resolver: Any,
    context_resolver: Any,
    domain_router: Any,
    agent_router: Any,
    policy: Any,
    decision_repository: Any,
    event_sink: Any,
    orchestrator: Any,
) -> StaticCompositionModule:
    """Return the Phase 11.1 contribution for the Phase 11.2 services.

    The builder constructs no subsystem: every collaborator is an
    already-constructed object supplied by the composition root.
    """

    orchestrator_dependencies = tuple(
        _dependency(service_id) for service_id in ORCHESTRATOR_DEPENDENCY_IDS
    )

    bindings = (
        _binding(agent_router, AGENT_ROUTER_SERVICE_ID),
        _binding(context_resolver, CONTEXT_RESOLVER_SERVICE_ID),
        _binding(decision_repository, DECISION_REPOSITORY_SERVICE_ID),
        _binding(domain_router, DOMAIN_ROUTER_SERVICE_ID),
        _binding(event_sink, EVENT_SINK_SERVICE_ID),
        _binding(intent_resolver, INTENT_RESOLVER_SERVICE_ID),
        _binding(
            orchestrator,
            ORCHESTRATOR_SERVICE_ID,
            authority=ORCHESTRATION_AUTHORITY,
            dependencies=orchestrator_dependencies,
        ),
        _binding(policy, POLICY_SERVICE_ID),
    )

    return StaticCompositionModule(ORCHESTRATION_MODULE_ID, bindings)
