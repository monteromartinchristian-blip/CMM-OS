"""Phase 11.3 — application composition module tests.

``build_application_composition_module`` contributes the one Phase 11.3 service
binding — ``application.gateway`` — through the existing Phase 11.1
``StaticCompositionModule`` / ``ServiceBinding`` model.  It adds no composition
mechanism, changes no Phase 11.1 semantics and never constructs a subsystem: the
gateway is an already-built object supplied by the composition root.

These tests lock the frozen identities, the declared dependency on the Phase
11.2 ``orchestration.orchestrator``, the exact authority claim, the fail-closed
role boundary (an unrelated object may not claim the service identity) and the
end-to-end readiness of a real ``ApplicationContainer`` holding both the
orchestration and the application contributions.

A gateway is contributed into the container it is built for, so its own
readiness projection is wired to the platform composition — the container built
from the orchestration contribution, exactly as a composition root wires it.

See ``docs/superpowers/specs/2026-09-16-phase-11.3-application-backend-design.md``.
"""

from __future__ import annotations

import pytest

from cmm.application.capabilities import (
    CapabilityApplicationService,
    build_default_capabilities,
)
from cmm.application.gateway import ApplicationGateway
from cmm.application.health import HealthApplicationService
from cmm.application.idempotency import InMemoryIdempotencyRepository
from cmm.application.platform_module import (
    APPLICATION_AUTHORITY,
    APPLICATION_CONTRACT_VERSION,
    APPLICATION_MODULE_ID,
    APPLICATION_OWNER,
    APPLICATION_SCHEMA_VERSION,
    APPLICATION_SERVICE_ID,
    ORCHESTRATOR_CONTRACT_VERSION,
    ORCHESTRATOR_DEPENDENCY_ID,
    ORCHESTRATOR_OWNER,
    ORCHESTRATOR_SCHEMA_VERSION,
    build_application_composition_module,
)
from cmm.application.requests import RequestApplicationService
from cmm.application.sessions import SessionApplicationService
from cmm.orchestration.contracts import (
    AgentRouteDecision,
    DomainRouteDecision,
    ExecutionRoute,
    IntentKind,
    IntentResolution,
    OrchestrationPolicyDecision,
    OrchestrationRequest,
    OrchestrationResult,
    PolicyDisposition,
    ResolvedContext,
)
from cmm.orchestration.decision_repository import (
    InMemoryOrchestrationDecisionRepository,
)
from cmm.orchestration.events import RecordingOrchestrationEventSink
from cmm.orchestration.orchestrator import Orchestrator
from cmm.orchestration.platform_module import (
    ORCHESTRATION_CONTRACT_VERSION,
    ORCHESTRATION_MODULE_ID,
    ORCHESTRATION_OWNER,
    ORCHESTRATION_SCHEMA_VERSION,
    ORCHESTRATOR_SERVICE_ID,
    build_orchestration_composition_module,
)
from cmm.platform.configuration import CompositionConfiguration, ServiceExpectation
from cmm.platform.container import ApplicationContainer
from cmm.platform.contracts import (
    ContainerState,
    ContractMetadata,
    ServiceBinding,
    ServiceMode,
)
from cmm.platform.errors import IncompatibleContractError, MissingDependencyError
from cmm.platform.modules import StaticCompositionModule
from cmm.platform.service_registry import IntegrationServiceRegistry
from cmm.runtime.sessions import InMemorySessionStore

# ── Orchestration collaborator doubles ───────────────────────────────────────


class _IntentResolver:
    def resolve(self, request: OrchestrationRequest) -> IntentResolution:
        return IntentResolution(
            intent=IntentKind.QUESTION,
            needs_clarification=False,
            source_kind="structured_input",
        )


class _ContextResolver:
    def resolve_base(self, request: OrchestrationRequest) -> ResolvedContext:
        return ResolvedContext(request_id=request.request_id, stage="base")

    def resolve_domain_context(
        self,
        request: OrchestrationRequest,
        base_context: ResolvedContext,
        domain_route: DomainRouteDecision,
    ) -> ResolvedContext:
        return ResolvedContext(request_id=request.request_id, stage="domain")


class _DomainRouter:
    def route_domain(
        self,
        request: OrchestrationRequest,
        intent: IntentResolution,
        context: ResolvedContext,
    ) -> DomainRouteDecision:
        return DomainRouteDecision(status="resolved", primary_domain="domain:general")


class _AgentRouter:
    def route_agent(
        self,
        *,
        request: OrchestrationRequest,
        intent: IntentResolution,
        context: ResolvedContext,
        domain: DomainRouteDecision,
    ) -> AgentRouteDecision:
        return AgentRouteDecision(route=ExecutionRoute.DIRECT_RESPONSE)


class _Policy:
    def evaluate(
        self,
        *,
        request: OrchestrationRequest,
        intent: IntentResolution,
        context: ResolvedContext,
        domain: DomainRouteDecision,
        route: AgentRouteDecision,
    ) -> OrchestrationPolicyDecision:
        return OrchestrationPolicyDecision(
            disposition=PolicyDisposition.ALLOW_ROUTE, reason_codes=("POLICY_ALLOWED",)
        )


class _Orchestrator(Orchestrator):
    """A canonical orchestrator that this composition gate never executes."""

    def __init__(self) -> None:
        pass

    def orchestrate(self, request: OrchestrationRequest) -> OrchestrationResult:
        raise AssertionError("composition must not execute the orchestrator")


def _orchestration_module() -> StaticCompositionModule:
    return build_orchestration_composition_module(
        intent_resolver=_IntentResolver(),
        context_resolver=_ContextResolver(),
        domain_router=_DomainRouter(),
        agent_router=_AgentRouter(),
        policy=_Policy(),
        decision_repository=InMemoryOrchestrationDecisionRepository(),
        event_sink=RecordingOrchestrationEventSink(),
        orchestrator=_Orchestrator(),
    )


# ── Wiring helpers ───────────────────────────────────────────────────────────


def _platform_configuration() -> CompositionConfiguration:
    return CompositionConfiguration(
        enabled_modules=(ORCHESTRATION_MODULE_ID,),
    )


def _platform_container() -> ApplicationContainer:
    """Return the platform composition a gateway's health projection reads."""

    return ApplicationContainer.build(
        _platform_configuration(), modules=(_orchestration_module(),)
    )


def _gateway(
    container: ApplicationContainer, orchestrator: Orchestrator | None = None
) -> ApplicationGateway:
    sessions = SessionApplicationService(InMemorySessionStore())
    return ApplicationGateway(
        sessions=sessions,
        requests=RequestApplicationService(
            sessions=sessions,
            orchestrator=_Orchestrator() if orchestrator is None else orchestrator,
        ),
        capabilities=CapabilityApplicationService(build_default_capabilities()),
        health=HealthApplicationService(container),
        idempotency=InMemoryIdempotencyRepository(),
    )


def _module() -> tuple[StaticCompositionModule, ApplicationGateway]:
    gateway = _gateway(_platform_container())
    return build_application_composition_module(gateway=gateway), gateway


def _backend_configuration() -> CompositionConfiguration:
    return CompositionConfiguration(
        required_services=(ORCHESTRATOR_DEPENDENCY_ID, APPLICATION_SERVICE_ID),
        enabled_modules=(ORCHESTRATION_MODULE_ID, APPLICATION_MODULE_ID),
        expected_contracts=(
            ServiceExpectation(
                service_id=APPLICATION_SERVICE_ID,
                contract=ContractMetadata(
                    contract_name=APPLICATION_SERVICE_ID,
                    contract_version=APPLICATION_CONTRACT_VERSION,
                    schema_version=APPLICATION_SCHEMA_VERSION,
                    owner=APPLICATION_OWNER,
                ),
            ),
        ),
    )


# ── Frozen identities ────────────────────────────────────────────────────────


def test_frozen_identifiers_are_stable() -> None:
    assert APPLICATION_MODULE_ID == "application"
    assert APPLICATION_SERVICE_ID == "application.gateway"
    assert APPLICATION_OWNER == "cmm.application"
    assert APPLICATION_CONTRACT_VERSION == "1.0.0"
    assert APPLICATION_SCHEMA_VERSION == "1"
    assert APPLICATION_AUTHORITY == "application-public-gateway"
    assert ORCHESTRATOR_DEPENDENCY_ID == "orchestration.orchestrator"


# ── Contribution shape ───────────────────────────────────────────────────────


def test_module_is_a_static_composition_module_with_a_stable_identity() -> None:
    module, _gateway_object = _module()

    assert isinstance(module, StaticCompositionModule)
    assert module.module_id == APPLICATION_MODULE_ID


def test_module_contributes_exactly_one_service_binding() -> None:
    module, gateway = _module()

    contributed = module.contribute(CompositionConfiguration())

    assert isinstance(contributed, tuple)
    assert len(contributed) == 1
    binding = contributed[0]
    assert isinstance(binding, ServiceBinding)
    assert binding.descriptor.service_id == APPLICATION_SERVICE_ID
    assert binding.implementation is gateway


def test_module_contributes_nothing_until_it_is_invoked() -> None:
    registry = IntegrationServiceRegistry()

    _module()

    assert registry.service_ids() == ()


def test_binding_declares_its_boundary_and_enforceable_runtime_contract() -> None:
    module, gateway = _module()

    binding = module.contribute(CompositionConfiguration())[0]

    assert binding.descriptor.contract.contract_name == APPLICATION_SERVICE_ID
    assert binding.descriptor.contract.owner == APPLICATION_OWNER
    assert binding.descriptor.contract.contract_version == APPLICATION_CONTRACT_VERSION
    assert binding.descriptor.contract.schema_version == APPLICATION_SCHEMA_VERSION
    assert binding.descriptor.mode is ServiceMode.LOCAL
    assert binding.runtime_contract is ApplicationGateway
    assert isinstance(binding.implementation, binding.runtime_contract)
    implementation_type = type(gateway)
    assert binding.descriptor.implementation_id == (
        f"{implementation_type.__module__}.{implementation_type.__qualname__}"
    )


def test_binding_declares_the_canonical_orchestrator_dependency() -> None:
    module, _gateway_object = _module()

    binding = module.contribute(CompositionConfiguration())[0]
    dependencies = binding.descriptor.dependencies

    assert len(dependencies) == 1
    dependency = dependencies[0]
    assert dependency.service_id == ORCHESTRATOR_DEPENDENCY_ID
    # The declared dependency contract must match the Phase 11.2 boundary
    # exactly, because Phase 11.1 compatibility is exact and fails closed.
    assert dependency.contract.contract_name == ORCHESTRATOR_DEPENDENCY_ID
    assert dependency.contract.owner == ORCHESTRATOR_OWNER
    assert dependency.contract.contract_version == ORCHESTRATOR_CONTRACT_VERSION
    assert dependency.contract.schema_version == ORCHESTRATOR_SCHEMA_VERSION


def test_declared_dependency_mirrors_the_phase_11_2_boundary() -> None:
    """The mirrored dependency contract can not silently drift from Phase 11.2."""

    assert ORCHESTRATOR_CONTRACT_VERSION == ORCHESTRATION_CONTRACT_VERSION
    assert ORCHESTRATOR_SCHEMA_VERSION == ORCHESTRATION_SCHEMA_VERSION
    assert ORCHESTRATOR_OWNER == ORCHESTRATION_OWNER
    assert ORCHESTRATOR_DEPENDENCY_ID == ORCHESTRATOR_SERVICE_ID


def test_only_the_gateway_claims_the_application_authority() -> None:
    module, _gateway_object = _module()

    bindings = module.contribute(CompositionConfiguration())

    assert [binding.descriptor.authority for binding in bindings] == [
        APPLICATION_AUTHORITY
    ]
    for binding in bindings:
        assert binding.descriptor.authority not in {
            "provider-registry",
            "domain-registry",
            "agent-registry",
            "workflow-registry",
            "execution-registry",
            "orchestration-request-coordinator",
        }


# ── Fail-closed role boundary ────────────────────────────────────────────────


class _DuckTypedGateway:
    """A gateway-shaped object that is not the concrete application gateway."""

    def handle(self, request: object) -> object:  # pragma: no cover
        raise AssertionError("an impostor gateway must never be composed")


@pytest.mark.parametrize(
    "candidate", [object(), None, "application.gateway", _DuckTypedGateway()]
)
def test_builder_rejects_a_non_gateway_object(candidate: object) -> None:
    with pytest.raises(TypeError):
        build_application_composition_module(gateway=candidate)  # type: ignore[arg-type]


def test_collaborators_are_keyword_only() -> None:
    with pytest.raises(TypeError):
        build_application_composition_module(_gateway(_platform_container()))  # type: ignore[misc]


def test_an_unrelated_object_cannot_claim_the_application_identity() -> None:
    """A hand-built binding is still bounded by the declared runtime contract."""

    module, _gateway_object = _module()
    original = module.contribute(CompositionConfiguration())[0]

    forged = ServiceBinding(
        descriptor=original.descriptor,
        implementation=object(),
        runtime_contract=original.runtime_contract,
    )

    with pytest.raises(IncompatibleContractError):
        IntegrationServiceRegistry().register(forged)


# ── Phase 11.1 integration ───────────────────────────────────────────────────


def test_registry_accepts_the_contribution_and_validates_the_graph() -> None:
    module, _gateway_object = _module()
    registry = IntegrationServiceRegistry()

    for binding in _orchestration_module().contribute(CompositionConfiguration()):
        registry.register(binding)
    for binding in module.contribute(CompositionConfiguration()):
        registry.register(binding)
    registry.validate_graph()

    order = registry.dependency_order()
    assert order.index(ORCHESTRATOR_DEPENDENCY_ID) < order.index(APPLICATION_SERVICE_ID)


def test_missing_orchestration_contribution_fails_closed() -> None:
    """The declared dependency is real: composing alone does not become ready."""

    module, _gateway_object = _module()

    with pytest.raises(MissingDependencyError):
        ApplicationContainer.build(
            CompositionConfiguration(
                required_services=(APPLICATION_SERVICE_ID,),
                enabled_modules=(APPLICATION_MODULE_ID,),
            ),
            modules=(module,),
        )


def test_container_reaches_ready_with_the_application_contribution() -> None:
    module, gateway = _module()

    container = ApplicationContainer.build(
        _backend_configuration(),
        modules=(_orchestration_module(), module),
    )

    assert container.state is ContainerState.READY
    assert container.get_service(APPLICATION_SERVICE_ID) is gateway


def test_ready_snapshot_projects_the_application_service_identity() -> None:
    module, _gateway_object = _module()

    container = ApplicationContainer.build(
        _backend_configuration(),
        modules=(_orchestration_module(), module),
    )

    payload = container.snapshot().to_dict()
    application = next(
        service
        for service in payload["services"]
        if service["service_id"] == APPLICATION_SERVICE_ID
    )

    assert payload["state"] == "ready"
    assert application["owner"] == APPLICATION_OWNER
    assert application["contract_version"] == APPLICATION_CONTRACT_VERSION
    assert application["schema_version"] == APPLICATION_SCHEMA_VERSION
    assert application["authority"] == APPLICATION_AUTHORITY
    assert application["dependency_ids"] == [ORCHESTRATOR_DEPENDENCY_ID]
    assert application["mode"] == "local"


def test_composed_gateway_serves_the_contributed_identity() -> None:
    """The composed service is the working public entrypoint, not just an object."""

    module, gateway = _module()
    container = ApplicationContainer.build(
        _backend_configuration(),
        modules=(_orchestration_module(), module),
    )

    composed = container.get_service(APPLICATION_SERVICE_ID)

    assert composed is gateway
