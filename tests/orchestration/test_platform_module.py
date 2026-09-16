"""Phase 11.2 — orchestration composition module tests.

``build_orchestration_composition_module`` returns a Phase 11.1
``StaticCompositionModule`` contribution holding the eight stable orchestration
service bindings.  It never modifies ``cmm.platform`` ownership: every binding
is a normal new service binding, and only the global Orchestrator claims an
exclusive orchestration authority.
"""

from __future__ import annotations

import json

import pytest

from cmm.orchestration.contracts import (
    AgentRouteDecision,
    DomainRouteDecision,
    ExecutionRoute,
    IntentKind,
    IntentResolution,
    OrchestrationPolicyDecision,
    OrchestrationRequest,
    PolicyDisposition,
    ResolvedContext,
)
from cmm.orchestration.decision_repository import (
    InMemoryOrchestrationDecisionRepository,
)
from cmm.orchestration.events import RecordingOrchestrationEventSink
from cmm.orchestration.orchestrator import Orchestrator
from cmm.orchestration.platform_module import (
    ORCHESTRATION_AUTHORITY,
    ORCHESTRATION_SERVICE_IDS,
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
from cmm.platform.modules import StaticCompositionModule
from cmm.platform.service_registry import IntegrationServiceRegistry

MODULE_ID = "orchestration"

COLLABORATOR_SERVICE_IDS = (
    "orchestration.agent_router",
    "orchestration.context_resolver",
    "orchestration.decision_repository",
    "orchestration.domain_router",
    "orchestration.event_sink",
    "orchestration.intent_resolver",
    "orchestration.policy",
)


# ── Collaborator doubles ─────────────────────────────────────────────────────


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

    def resolve_domain_context(self, request, base_context, domain_route):
        return ResolvedContext(request_id=request.request_id, stage="domain")


class _DomainRouter:
    def route(self, request, intent, context) -> DomainRouteDecision:
        return DomainRouteDecision(status="resolved", primary_domain="domain:general")


class _AgentRouter:
    def route(self, *, request, intent, context, domain) -> AgentRouteDecision:
        return AgentRouteDecision(route=ExecutionRoute.DIRECT_RESPONSE)


class _Policy:
    def evaluate(self, *, request, intent, context, domain, route):
        return OrchestrationPolicyDecision(
            disposition=PolicyDisposition.ALLOW_ROUTE, reason_codes=("POLICY_ALLOWED",)
        )


class _Orchestrator:
    def orchestrate(self, request: OrchestrationRequest):
        raise AssertionError("composition must not execute the orchestrator")


def _collaborators() -> dict[str, object]:
    return {
        "intent_resolver": _IntentResolver(),
        "context_resolver": _ContextResolver(),
        "domain_router": _DomainRouter(),
        "agent_router": _AgentRouter(),
        "policy": _Policy(),
        "decision_repository": InMemoryOrchestrationDecisionRepository(),
        "event_sink": RecordingOrchestrationEventSink(),
        "orchestrator": _Orchestrator(),
    }


def _module() -> StaticCompositionModule:
    return build_orchestration_composition_module(**_collaborators())  # type: ignore[arg-type]


# ── Contribution shape ───────────────────────────────────────────────────────


def test_module_is_a_static_composition_module_with_a_stable_identity() -> None:
    module = _module()

    assert isinstance(module, StaticCompositionModule)
    assert module.module_id == MODULE_ID
    assert len(ORCHESTRATION_SERVICE_IDS) == 8
    assert "orchestration.orchestrator" in ORCHESTRATION_SERVICE_IDS


def test_module_contributes_every_stable_orchestration_service() -> None:
    configuration = CompositionConfiguration()

    contributed = _module().contribute(configuration)

    assert isinstance(contributed, tuple)
    assert all(isinstance(binding, ServiceBinding) for binding in contributed)
    assert (
        tuple(binding.descriptor.service_id for binding in contributed)
        == ORCHESTRATION_SERVICE_IDS
    )


def test_module_contributes_nothing_until_it_is_invoked() -> None:
    """Building the module registers nothing: contribution stays explicit."""

    registry = IntegrationServiceRegistry()

    _module()

    assert registry.service_ids() == ()


@pytest.mark.parametrize("service_id", ORCHESTRATION_SERVICE_IDS)
def test_every_binding_declares_its_boundary_and_identity(service_id: str) -> None:
    binding = next(
        item
        for item in _module().contribute(CompositionConfiguration())
        if item.descriptor.service_id == service_id
    )

    assert binding.descriptor.contract.contract_name == service_id
    assert binding.descriptor.contract.owner == "cmm.orchestration"
    assert binding.descriptor.contract.contract_version
    assert binding.descriptor.contract.schema_version
    assert binding.descriptor.mode is ServiceMode.LOCAL
    assert binding.runtime_contract is not None
    assert isinstance(binding.implementation, binding.runtime_contract)
    implementation_type = type(binding.implementation)
    assert binding.descriptor.implementation_id == (
        f"{implementation_type.__module__}.{implementation_type.__qualname__}"
    )


def test_orchestrator_declares_its_seven_collaborators() -> None:
    bindings = _module().contribute(CompositionConfiguration())
    orchestrator = next(
        item
        for item in bindings
        if item.descriptor.service_id == "orchestration.orchestrator"
    )

    assert (
        tuple(
            dependency.service_id for dependency in orchestrator.descriptor.dependencies
        )
        == COLLABORATOR_SERVICE_IDS
    )


def test_only_the_orchestrator_claims_the_orchestration_authority() -> None:
    bindings = _module().contribute(CompositionConfiguration())

    authorities = {
        binding.descriptor.service_id: binding.descriptor.authority
        for binding in bindings
    }

    assert authorities == {
        **{service_id: None for service_id in COLLABORATOR_SERVICE_IDS},
        "orchestration.orchestrator": ORCHESTRATION_AUTHORITY,
    }
    assert ORCHESTRATION_AUTHORITY == "orchestration-request-coordinator"


def test_no_binding_claims_a_canonical_authority() -> None:
    bindings = _module().contribute(CompositionConfiguration())

    for binding in bindings:
        assert binding.descriptor.authority != "provider-registry"
        assert binding.descriptor.authority not in {
            "domain-registry",
            "agent-registry",
            "workflow-registry",
            "execution-registry",
        }


def test_registry_accepts_the_contribution_and_validates_the_graph() -> None:
    registry = IntegrationServiceRegistry()

    for binding in _module().contribute(CompositionConfiguration()):
        registry.register(binding)

    registry.validate_graph()

    assert registry.service_ids() == ORCHESTRATION_SERVICE_IDS
    assert registry.dependency_order()[-1] == "orchestration.orchestrator"


# ── Fail-closed boundaries ───────────────────────────────────────────────────


@pytest.mark.parametrize("role", sorted(_collaborators()))
def test_builder_rejects_an_unrelated_object(role: str) -> None:
    collaborators = _collaborators()
    collaborators[role] = object()

    with pytest.raises(TypeError):
        build_orchestration_composition_module(**collaborators)  # type: ignore[arg-type]


def test_builder_rejects_a_cross_role_object() -> None:
    collaborators = _collaborators()
    collaborators["intent_resolver"] = _collaborators()["event_sink"]

    with pytest.raises(TypeError):
        build_orchestration_composition_module(**collaborators)  # type: ignore[arg-type]


def test_unrelated_object_cannot_claim_an_orchestration_identity() -> None:
    """A hand-built binding is still bounded by the declared runtime contract."""

    from cmm.platform.errors import IncompatibleContractError

    registry = IntegrationServiceRegistry()
    original = _module().contribute(CompositionConfiguration())[0]

    forged = ServiceBinding(
        descriptor=original.descriptor,
        implementation=object(),
        runtime_contract=original.runtime_contract,
    )

    with pytest.raises(IncompatibleContractError):
        registry.register(forged)


# ── Phase 11.1 integration ───────────────────────────────────────────────────


def _orchestration_configuration() -> CompositionConfiguration:
    return CompositionConfiguration(
        required_services=ORCHESTRATION_SERVICE_IDS,
        enabled_modules=(MODULE_ID,),
        expected_contracts=tuple(
            ServiceExpectation(
                service_id=service_id,
                contract=ContractMetadata(
                    contract_name=service_id,
                    contract_version="1.0.0",
                    schema_version="1",
                    owner="cmm.orchestration",
                ),
            )
            for service_id in ORCHESTRATION_SERVICE_IDS
        ),
    )


def test_container_reaches_ready_with_the_orchestration_contribution() -> None:
    container = ApplicationContainer.build(
        _orchestration_configuration(), modules=(_module(),)
    )

    assert container.state is ContainerState.READY
    assert container.get_service("orchestration.orchestrator") is not None


def test_ready_snapshot_serializes_safely() -> None:
    container = ApplicationContainer.build(
        _orchestration_configuration(), modules=(_module(),)
    )

    snapshot = container.snapshot()
    payload = snapshot.to_dict()

    assert payload["state"] == "ready"
    assert json.loads(json.dumps(payload, sort_keys=True)) == payload
    assert {service["service_id"] for service in payload["services"]} == set(
        ORCHESTRATION_SERVICE_IDS
    )


def test_orchestration_collaborators_are_individually_resolvable() -> None:
    collaborators = _collaborators()
    container = ApplicationContainer.build(
        _orchestration_configuration(),
        modules=(build_orchestration_composition_module(**collaborators),),  # type: ignore[arg-type]
    )

    for service_id in COLLABORATOR_SERVICE_IDS:
        assert container.get_service(service_id) is not None

    assert (
        container.get_service("orchestration.orchestrator")
        is collaborators["orchestrator"]
    )


def test_built_orchestrator_can_be_composed() -> None:
    repository = InMemoryOrchestrationDecisionRepository()
    sink = RecordingOrchestrationEventSink()
    orchestrator = Orchestrator(
        intent_resolver=_IntentResolver(),
        context_resolver=_ContextResolver(),
        domain_router=_DomainRouter(),
        agent_router=_AgentRouter(),
        policy=_Policy(),
        decision_repository=repository,
        event_sink=sink,
    )

    container = ApplicationContainer.build(
        _orchestration_configuration(),
        modules=(
            build_orchestration_composition_module(
                intent_resolver=_IntentResolver(),
                context_resolver=_ContextResolver(),
                domain_router=_DomainRouter(),
                agent_router=_AgentRouter(),
                policy=_Policy(),
                decision_repository=repository,
                event_sink=sink,
                orchestrator=orchestrator,
            ),
        ),
    )

    assert container.state is ContainerState.READY
    assert container.get_service("orchestration.orchestrator") is orchestrator


def test_missing_required_orchestration_service_fails_closed() -> None:
    from cmm.platform.errors import MissingDependencyError

    configuration = CompositionConfiguration(
        required_services=("orchestration.orchestrator",),
    )

    with pytest.raises(MissingDependencyError):
        ApplicationContainer.build(configuration, modules=(_module(),))
