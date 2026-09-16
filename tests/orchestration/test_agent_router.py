"""Phase 11.2 — canonical agent / execution-path router tests.

``CanonicalAgentRouter`` selects the bounded execution path.  Agent
compatibility and selection stay owned by ``AgentRegistryService`` /
``AgentResolver``; this router implements no agent scoring and never calls
Agent Runtime execution.
"""

from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace

import pytest

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
from cmm.orchestration.agent_router import (
    AgentRouter,
    CanonicalAgentRouter,
)
from cmm.orchestration.contracts import (
    DomainRouteDecision,
    ExecutionRoute,
    IntentKind,
    IntentResolution,
    OrchestrationChannel,
    OrchestrationRequest,
    ResolvedContext,
)
from cmm.orchestration.errors import AgentRoutingError

AGENT_ROUTER_MODULE = (
    Path(__file__).resolve().parents[2] / "cmm" / "orchestration" / "agent_router.py"
)

FORBIDDEN_OWNER_CLASSES = (
    "AgentRegistry",
    "AgentRegistryService",
    "AgentResolver",
    "AgentCandidateScorer",
    "AgentCompatibilityChecker",
    "AgentRuntimeIntegrationService",
)


# ── Canonical fixtures ───────────────────────────────────────────────────────


class _InMemoryAgentFactory:
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


def _descriptor(
    agent_id: str = "agent.alpha",
    *,
    capability: str = "knowledge.read",
    factory_id: str = "factory.alpha",
) -> AgentDescriptor:
    return AgentDescriptor(
        agent_id=agent_id,
        name="Alpha Agent",
        version=AgentVersion(1, 0, 0),
        kind=AgentKind.GENERAL,
        lifecycle=AgentLifecycle.ACTIVE,
        description="alpha agent",
        capabilities=(
            AgentCapability(
                name=capability,
                kind=AgentCapabilityKind.OPERATION,
            ),
        ),
        factory_id=factory_id,
    )


def _service(
    descriptor: AgentDescriptor | None = None,
) -> AgentRegistryService:
    service = AgentRegistryService(
        registry=AgentRegistry(store=InMemoryAgentRegistryStore()),
        factory_registry=AgentFactoryRegistry(),
    )
    if descriptor is not None:
        service.register_factory(_InMemoryAgentFactory(descriptor.factory_id))
        service.register_agent(descriptor)
    return service


def _request(**overrides: object) -> OrchestrationRequest:
    values: dict[str, object] = {
        "request_id": "request-1",
        "user_id": "user-1",
        "channel": OrchestrationChannel.CONVERSATION,
        "session_id": "session-1",
    }
    values.update(overrides)
    return OrchestrationRequest(**values)  # type: ignore[arg-type]


def _intent(kind: IntentKind) -> IntentResolution:
    return IntentResolution(
        intent=kind, needs_clarification=False, source_kind="structured_input"
    )


def _domain(primary: str | None = "domain:general") -> DomainRouteDecision:
    return DomainRouteDecision(status="resolved", primary_domain=primary)


def _route_agent(
    router: CanonicalAgentRouter,
    intent: IntentKind,
    *,
    request: OrchestrationRequest | None = None,
    domain: DomainRouteDecision | None = None,
):
    return router.route_agent(
        request=request or _request(),
        intent=_intent(intent),
        context=ResolvedContext(request_id="request-1", stage="domain"),
        domain=domain or _domain(),
    )


# ── Route matrix ─────────────────────────────────────────────────────────────


def test_router_satisfies_its_protocol() -> None:
    assert isinstance(CanonicalAgentRouter(), AgentRouter)


def test_router_requires_real_inputs() -> None:
    router = CanonicalAgentRouter()

    with pytest.raises(TypeError):
        router.route_agent(
            request=object(),  # type: ignore[arg-type]
            intent=_intent(IntentKind.QUESTION),
            context=ResolvedContext(request_id="request-1", stage="domain"),
            domain=_domain(),
        )
    with pytest.raises(TypeError):
        router.route_agent(
            request=_request(),
            intent=object(),  # type: ignore[arg-type]
            context=ResolvedContext(request_id="request-1", stage="domain"),
            domain=_domain(),
        )
    with pytest.raises(TypeError):
        router.route_agent(
            request=_request(),
            intent=_intent(IntentKind.QUESTION),
            context=object(),  # type: ignore[arg-type]
            domain=_domain(),
        )


@pytest.mark.parametrize(
    ("intent", "expected"),
    [
        (IntentKind.QUESTION, ExecutionRoute.DIRECT_RESPONSE),
        (IntentKind.REFLECTION, ExecutionRoute.DIRECT_RESPONSE),
        (IntentKind.COMMAND, ExecutionRoute.OPERATION),
        (IntentKind.WORKFLOW_REQUEST, ExecutionRoute.WORKFLOW),
        (IntentKind.INFORMATION_UPDATE, ExecutionRoute.OPERATION),
        (IntentKind.APPROVAL_RESPONSE, ExecutionRoute.OPERATION),
        (IntentKind.CONTINUATION, ExecutionRoute.WORKFLOW),
        (IntentKind.CANCELLATION, ExecutionRoute.WORKFLOW),
        (IntentKind.CONFIGURATION_CHANGE, ExecutionRoute.HUMAN_ESCALATION),
        (IntentKind.UNKNOWN, ExecutionRoute.NONE),
    ],
)
def test_route_matrix_is_frozen(intent: IntentKind, expected: ExecutionRoute) -> None:
    decision = _route_agent(CanonicalAgentRouter(), intent)

    assert decision.route is expected


def test_route_matrix_is_independent_of_the_selected_domain() -> None:
    router = CanonicalAgentRouter()

    for primary in ("domain:general", "domain:health", None):
        decision = _route_agent(router, IntentKind.QUESTION, domain=_domain(primary))
        assert decision.route is ExecutionRoute.DIRECT_RESPONSE


def test_continuation_carries_the_referenced_workflow() -> None:
    request = _request(input={"continuation_id": "workflow-1"})

    decision = _route_agent(
        CanonicalAgentRouter(), IntentKind.CONTINUATION, request=request
    )

    assert decision.route is ExecutionRoute.WORKFLOW
    assert decision.workflow_id == "workflow-1"


def test_cancellation_carries_the_referenced_workflow() -> None:
    request = _request(input={"cancel_target_id": "workflow-2"})

    decision = _route_agent(
        CanonicalAgentRouter(), IntentKind.CANCELLATION, request=request
    )

    assert decision.route is ExecutionRoute.WORKFLOW
    assert decision.workflow_id == "workflow-2"


def test_workflow_request_carries_the_declared_workflow_identifier() -> None:
    request = _request(
        input={"workflow_request": {"workflow_type": "review", "workflow_id": "wf-9"}}
    )

    decision = _route_agent(
        CanonicalAgentRouter(), IntentKind.WORKFLOW_REQUEST, request=request
    )

    assert decision.workflow_id == "wf-9"


def test_workflow_request_without_an_identifier_does_not_invent_one() -> None:
    request = _request(input={"workflow_request": {"workflow_type": "review"}})

    decision = _route_agent(
        CanonicalAgentRouter(), IntentKind.WORKFLOW_REQUEST, request=request
    )

    assert decision.workflow_id is None


# ── Canonical agent delegation ───────────────────────────────────────────────


def test_autonomous_goal_delegates_to_the_canonical_registry_service() -> None:
    service = _service(_descriptor())
    router = CanonicalAgentRouter(registry_service=service)
    request = _request(
        input={"goal": {"title": "Complete task"}},
        requested_capabilities=("knowledge.read",),
    )

    decision = _route_agent(router, IntentKind.GOAL, request=request)

    assert decision.route is ExecutionRoute.AUTONOMOUS_AGENT
    assert decision.agent_id == "agent.alpha"
    assert decision.agent_version == "1.0.0"


def test_autonomous_goal_records_the_canonical_resolution_attempt() -> None:
    service = _service(_descriptor())
    router = CanonicalAgentRouter(registry_service=service)
    request = _request(
        input={"goal": {"title": "Complete task"}},
        requested_capabilities=("knowledge.read",),
    )

    _route_agent(router, IntentKind.GOAL, request=request)

    assert service.resolver.attempts == 1


def test_no_compatible_agent_escalates_without_inventing_an_agent() -> None:
    service = _service(_descriptor(capability="knowledge.read"))
    router = CanonicalAgentRouter(registry_service=service)
    request = _request(
        input={"goal": {"title": "Complete task"}},
        requested_capabilities=("operation.execute",),
    )

    decision = _route_agent(router, IntentKind.GOAL, request=request)

    assert decision.route is ExecutionRoute.HUMAN_ESCALATION
    assert decision.agent_id is None
    assert "AGENT_ROUTING_NO_COMPATIBLE_AGENT" in decision.reason_codes


def test_autonomous_goal_without_declared_capabilities_escalates() -> None:
    service = _service(_descriptor())
    router = CanonicalAgentRouter(registry_service=service)
    request = _request(input={"goal": {"title": "Complete task"}})

    decision = _route_agent(router, IntentKind.GOAL, request=request)

    assert decision.route is ExecutionRoute.HUMAN_ESCALATION
    assert decision.agent_id is None
    assert "AGENT_ROUTING_REQUIREMENT_MISSING" in decision.reason_codes


def test_autonomous_goal_without_a_registry_service_escalates() -> None:
    request = _request(
        input={"goal": {"title": "Complete task"}},
        requested_capabilities=("knowledge.read",),
    )

    decision = _route_agent(
        CanonicalAgentRouter(registry_service=None), IntentKind.GOAL, request=request
    )

    assert decision.route is ExecutionRoute.HUMAN_ESCALATION
    assert decision.agent_id is None


class _BrokenAgentRegistryService(AgentRegistryService):
    """Canonical authority whose resolution fails; proves fail-closed handling."""

    def resolve_agent(self, requirement, **kwargs):  # type: ignore[no-untyped-def]
        raise RuntimeError("registry unavailable")


class _RecordingAgentRegistryService(AgentRegistryService):
    """Canonical authority that records whether agent resolution was attempted."""

    def __init__(self) -> None:
        super().__init__()
        self.calls = 0

    def resolve_agent(self, requirement, **kwargs):  # type: ignore[no-untyped-def]
        self.calls += 1
        raise AssertionError("non-agent route must not resolve an agent")


def test_registry_failure_fails_closed() -> None:
    router = CanonicalAgentRouter(registry_service=_BrokenAgentRegistryService())
    request = _request(
        input={"goal": {"title": "Complete task"}},
        requested_capabilities=("knowledge.read",),
    )

    with pytest.raises(AgentRoutingError) as captured:
        _route_agent(router, IntentKind.GOAL, request=request)

    assert captured.value.category == "agent"


# ── Canonical authority (Audit V1 MAJOR-02) ──────────────────────────────────


class _FakeRegistryService:
    """A noncanonical authority that can fabricate an agent selection."""

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


def test_noncanonical_registry_service_is_rejected_before_routing() -> None:
    """Audit V1 MAJOR-02: canonical authority must be a real runtime boundary."""

    with pytest.raises(TypeError):
        CanonicalAgentRouter(registry_service=_FakeRegistryService())  # type: ignore[arg-type]


def test_noncanonical_registry_service_can_never_fabricate_an_agent() -> None:
    """The fake authority must be rejected before it is ever consulted."""

    fake = _FakeRegistryService()

    with pytest.raises(TypeError):
        CanonicalAgentRouter(registry_service=fake)  # type: ignore[arg-type]

    assert fake.calls == 0


def test_rejection_message_names_the_canonical_authority_safely() -> None:
    with pytest.raises(TypeError) as captured:
        CanonicalAgentRouter(  # type: ignore[arg-type]
            registry_service=_FakeRegistryService()
        )

    message = str(captured.value)
    assert AgentRegistryService.__name__ in message
    assert "_FakeRegistryService" in message
    assert "0x" not in message
    assert "object at" not in message


def test_real_canonical_registry_service_is_accepted() -> None:
    service = _service(_descriptor())

    router = CanonicalAgentRouter(registry_service=service)

    assert isinstance(router, AgentRouter)


def test_no_registry_service_is_accepted_for_non_agent_routes() -> None:
    """``None`` stays valid: a route that needs no agent selection needs no authority."""

    router = CanonicalAgentRouter(registry_service=None)

    assert isinstance(router, AgentRouter)
    assert (
        _route_agent(router, IntentKind.QUESTION).route
        is ExecutionRoute.DIRECT_RESPONSE
    )


def test_canonical_no_match_escalates_through_the_real_authority() -> None:
    """No compatible canonical agent means escalation, never an invented agent."""

    service = _service(_descriptor(capability="knowledge.read"))
    router = CanonicalAgentRouter(registry_service=service)
    request = _request(
        input={"goal": {"title": "Complete task"}},
        requested_capabilities=("operation.execute",),
    )

    decision = _route_agent(router, IntentKind.GOAL, request=request)

    assert service.resolver.attempts == 1
    assert decision.route is ExecutionRoute.HUMAN_ESCALATION
    assert decision.agent_id is None
    assert "AGENT_ROUTING_NO_COMPATIBLE_AGENT" in decision.reason_codes


@pytest.mark.parametrize(
    "intent",
    [
        IntentKind.QUESTION,
        IntentKind.REFLECTION,
        IntentKind.COMMAND,
        IntentKind.WORKFLOW_REQUEST,
        IntentKind.INFORMATION_UPDATE,
        IntentKind.UNKNOWN,
    ],
)
def test_non_agent_routes_do_not_consult_the_agent_registry(
    intent: IntentKind,
) -> None:
    service = _RecordingAgentRegistryService()

    _route_agent(CanonicalAgentRouter(registry_service=service), intent)

    assert service.calls == 0


def test_router_never_executes_an_agent() -> None:
    """The router returns a route decision; it never runs Agent Runtime."""

    source = AGENT_ROUTER_MODULE.read_text()

    for forbidden in ("execute", "run_agent", "runtime_loop", "dispatch"):
        assert f".{forbidden}(" not in source, f"agent router must not call {forbidden}"


def test_routing_is_deterministic() -> None:
    service = _service(_descriptor())
    router = CanonicalAgentRouter(registry_service=service)
    request = _request(
        input={"goal": {"title": "Complete task"}},
        requested_capabilities=("knowledge.read",),
    )

    assert _route_agent(router, IntentKind.GOAL, request=request).to_dict() == (
        _route_agent(router, IntentKind.GOAL, request=request).to_dict()
    )


# ── Architecture ─────────────────────────────────────────────────────────────


def test_agent_router_defines_no_canonical_owner() -> None:
    tree = ast.parse(AGENT_ROUTER_MODULE.read_text())

    offenders = [
        node.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ClassDef) and node.name in FORBIDDEN_OWNER_CLASSES
    ]

    assert not offenders, f"agent router must not define canonical owners: {offenders}"


def test_agent_router_holds_no_scoring_logic() -> None:
    tree = ast.parse(AGENT_ROUTER_MODULE.read_text())

    offenders = [
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
        and "score" in node.name.lower()
    ]

    assert not offenders, f"agent router must not implement agent scoring: {offenders}"
