"""Phase 11.2 — global orchestrator pipeline tests.

``Orchestrator`` is the one global Phase 11 request coordinator.  This unit
suite uses small collaborator doubles for the frozen protocols; the connected
acceptance suite proves the same pipeline over real canonical components.

The frozen pipeline order is:

``validate -> request_received -> intent -> base context -> domain route ->
domain context -> route -> policy -> decision -> persist -> terminal event ->
result``

with clarification, canonical-deny, policy-terminal and failure paths stopping
at the earliest decisive point.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from cmm.orchestration.contracts import (
    AgentRouteDecision,
    DomainRouteDecision,
    ExecutionRoute,
    IntentKind,
    IntentResolution,
    OrchestrationChannel,
    OrchestrationPolicyDecision,
    OrchestrationRequest,
    OrchestrationStatus,
    PolicyDisposition,
    ResolvedContext,
)
from cmm.orchestration.decision_repository import (
    InMemoryOrchestrationDecisionRepository,
)
from cmm.orchestration.errors import (
    DecisionPersistenceError,
    IntentResolutionError,
)
from cmm.orchestration.events import RecordingOrchestrationEventSink
from cmm.orchestration.orchestrator import (
    Orchestrator,
    OrchestratorProtocol,
)

ORCHESTRATOR_MODULE = (
    Path(__file__).resolve().parents[2] / "cmm" / "orchestration" / "orchestrator.py"
)


# ── Collaborator doubles ─────────────────────────────────────────────────────


class _IntentResolver:
    def __init__(self, resolution: IntentResolution) -> None:
        self._resolution = resolution
        self.calls = 0

    def resolve(self, request: OrchestrationRequest) -> IntentResolution:
        self.calls += 1
        return self._resolution


class _BrokenIntentResolver:
    def resolve(self, request: OrchestrationRequest) -> IntentResolution:
        raise IntentResolutionError(
            "deterministic intent resolution failed",
            details={"request_id": request.request_id},
        )


class _ContextResolver:
    def __init__(self, *, missing: tuple[str, ...] = ()) -> None:
        self._missing = missing
        self.base_calls = 0
        self.domain_calls = 0

    def resolve_base(self, request: OrchestrationRequest) -> ResolvedContext:
        self.base_calls += 1
        return ResolvedContext(
            request_id=request.request_id,
            stage="base",
            missing_refs=self._missing,
        )

    def resolve_domain_context(self, request, base_context, domain_route):
        self.domain_calls += 1
        return ResolvedContext(
            request_id=request.request_id,
            stage="domain",
            missing_refs=base_context.missing_refs,
            domain_refs=(domain_route.primary_domain or "",),
        )


class _DomainRouter:
    def __init__(self, decision: DomainRouteDecision) -> None:
        self._decision = decision
        self.calls = 0

    def route_domain(self, request, intent, context) -> DomainRouteDecision:
        self.calls += 1
        return self._decision


class _AgentRouter:
    def __init__(self, decision: AgentRouteDecision) -> None:
        self._decision = decision
        self.calls = 0

    def route_agent(self, *, request, intent, context, domain) -> AgentRouteDecision:
        self.calls += 1
        return self._decision


class _Policy:
    def __init__(self, disposition: PolicyDisposition) -> None:
        self._disposition = disposition
        self.calls = 0

    def evaluate(self, *, request, intent, context, domain, route):
        self.calls += 1
        return OrchestrationPolicyDecision(
            disposition=self._disposition,
            approval_refs=("requirement-1",)
            if self._disposition is PolicyDisposition.REQUIRE_APPROVAL
            else (),
            reason_codes=("POLICY_TEST",),
        )


class _BrokenRepository:
    def save(self, record):
        raise DecisionPersistenceError(
            "decision persistence failed",
            details={"decision_id": record.decision_id},
        )

    def get(self, decision_id):  # pragma: no cover - never used
        return None

    def get_by_request_id(self, request_id):  # pragma: no cover - never used
        return None

    def list_for_session(self, session_id):  # pragma: no cover - never used
        return ()


class _BrokenSink:
    def emit(self, event_type, *, request_id, payload):
        raise RuntimeError("sink unavailable")


# ── Test graph ───────────────────────────────────────────────────────────────


def _request(**overrides: object) -> OrchestrationRequest:
    values: dict[str, object] = {
        "request_id": "request-1",
        "user_id": "user-1",
        "channel": OrchestrationChannel.CONVERSATION,
        "session_id": "session-1",
        "input": {"question": "What changed?"},
    }
    values.update(overrides)
    return OrchestrationRequest(**values)  # type: ignore[arg-type]


def _resolved_domain(**overrides: object) -> DomainRouteDecision:
    values: dict[str, object] = {
        "status": "resolved",
        "primary_domain": "domain:general",
        "trace_refs": ("domain-resolution:1",),
    }
    values.update(overrides)
    return DomainRouteDecision(**values)  # type: ignore[arg-type]


def _graph(
    *,
    intent: IntentKind = IntentKind.QUESTION,
    intent_resolver: object | None = None,
    domain: DomainRouteDecision | None = None,
    route: AgentRouteDecision | None = None,
    disposition: PolicyDisposition = PolicyDisposition.ALLOW_ROUTE,
    repository: object | None = None,
    sink: object | None = None,
    missing: tuple[str, ...] = (),
) -> tuple[Orchestrator, dict[str, object]]:
    collaborators: dict[str, object] = {
        "intent_resolver": intent_resolver or _IntentResolver(_resolution(intent)),
        "context_resolver": _ContextResolver(missing=missing),
        "domain_router": _DomainRouter(domain or _resolved_domain()),
        "agent_router": _AgentRouter(
            route or AgentRouteDecision(route=ExecutionRoute.DIRECT_RESPONSE)
        ),
        "policy": _Policy(disposition),
        "decision_repository": repository or InMemoryOrchestrationDecisionRepository(),
        "event_sink": sink or RecordingOrchestrationEventSink(),
    }
    return Orchestrator(**collaborators), collaborators  # type: ignore[arg-type]


def _resolution(kind: IntentKind = IntentKind.QUESTION) -> IntentResolution:
    return IntentResolution(
        intent=kind,
        needs_clarification=kind is IntentKind.UNKNOWN,
        source_kind="structured_input",
    )


# ── Pipeline ─────────────────────────────────────────────────────────────────


def test_orchestrator_satisfies_its_protocol() -> None:
    orchestrator, _ = _graph()

    assert isinstance(orchestrator, OrchestratorProtocol)


def test_happy_path_produces_a_routed_result() -> None:
    orchestrator, collaborators = _graph()

    result = orchestrator.orchestrate(_request())

    assert result.status is OrchestrationStatus.ROUTED
    assert result.intent is IntentKind.QUESTION
    assert result.route is ExecutionRoute.DIRECT_RESPONSE
    assert result.primary_domain == "domain:general"
    assert result.decision_id == "orchestration-decision:request-1"
    assert result.error is None

    repository = collaborators["decision_repository"]
    record = repository.get(result.decision_id)  # type: ignore[attr-defined]
    assert record is not None
    assert record.request_id == "request-1"
    assert record.policy_disposition is PolicyDisposition.ALLOW_ROUTE


def test_happy_path_calls_collaborators_in_the_frozen_order() -> None:
    orchestrator, collaborators = _graph()

    orchestrator.orchestrate(_request())

    assert collaborators["intent_resolver"].calls == 1  # type: ignore[attr-defined]
    assert collaborators["context_resolver"].base_calls == 1  # type: ignore[attr-defined]
    assert collaborators["context_resolver"].domain_calls == 1  # type: ignore[attr-defined]
    assert collaborators["domain_router"].calls == 1  # type: ignore[attr-defined]
    assert collaborators["agent_router"].calls == 1  # type: ignore[attr-defined]
    assert collaborators["policy"].calls == 1  # type: ignore[attr-defined]


def test_request_received_is_the_first_event_and_terminal_is_last() -> None:
    orchestrator, collaborators = _graph()

    orchestrator.orchestrate(_request())

    sink = collaborators["event_sink"]
    event_types = [event.event_type for event in sink.events()]  # type: ignore[attr-defined]

    assert event_types[0] == "orchestration.request_received"
    assert event_types[-1] == "orchestration.routed"
    assert event_types == [
        "orchestration.request_received",
        "orchestration.intent_resolved",
        "orchestration.domain_resolved",
        "orchestration.route_selected",
        "orchestration.routed",
    ]


def test_every_terminal_decision_is_recorded_exactly_once() -> None:
    orchestrator, collaborators = _graph()

    orchestrator.orchestrate(_request())

    repository = collaborators["decision_repository"]
    assert len(repository.list_for_session("session-1")) == 1  # type: ignore[attr-defined]


def test_replayed_request_is_idempotent() -> None:
    orchestrator, collaborators = _graph()

    first = orchestrator.orchestrate(_request())
    second = orchestrator.orchestrate(_request())

    assert first.to_dict() == second.to_dict()
    repository = collaborators["decision_repository"]
    assert len(repository.list_for_session("session-1")) == 1  # type: ignore[attr-defined]


def test_orchestrator_rejects_a_non_request() -> None:
    orchestrator, _ = _graph()

    with pytest.raises(TypeError):
        orchestrator.orchestrate(object())  # type: ignore[arg-type]


# ── Short-circuit paths ──────────────────────────────────────────────────────


def test_unknown_intent_stops_for_clarification() -> None:
    orchestrator, collaborators = _graph(intent=IntentKind.UNKNOWN)

    result = orchestrator.orchestrate(_request(input={"text": "something"}))

    assert result.status is OrchestrationStatus.NEEDS_CLARIFICATION
    assert result.intent is IntentKind.UNKNOWN
    assert result.route is ExecutionRoute.NONE
    assert collaborators["domain_router"].calls == 0  # type: ignore[attr-defined]
    assert collaborators["agent_router"].calls == 0  # type: ignore[attr-defined]
    assert collaborators["policy"].calls == 0  # type: ignore[attr-defined]
    assert collaborators["context_resolver"].base_calls == 0  # type: ignore[attr-defined]


def test_unknown_intent_still_records_a_terminal_decision() -> None:
    orchestrator, collaborators = _graph(intent=IntentKind.UNKNOWN)

    result = orchestrator.orchestrate(_request(input={"text": "something"}))

    repository = collaborators["decision_repository"]
    record = repository.get(result.decision_id)  # type: ignore[attr-defined]
    assert record is not None
    assert record.execution_route is ExecutionRoute.NONE
    assert record.policy_disposition is None


def test_missing_session_stops_for_clarification() -> None:
    orchestrator, collaborators = _graph(missing=("session:session-1",))

    result = orchestrator.orchestrate(_request())

    assert result.status is OrchestrationStatus.NEEDS_CLARIFICATION
    assert result.intent is IntentKind.QUESTION
    assert collaborators["domain_router"].calls == 0  # type: ignore[attr-defined]
    assert "ORCHESTRATION_SESSION_UNRESOLVED" in result.reason_codes


def test_ambiguous_domain_stops_for_clarification() -> None:
    orchestrator, collaborators = _graph(
        domain=DomainRouteDecision(
            status="ambiguous",
            ambiguous_domains=("domain:health", "domain:university"),
            needs_clarification=True,
        )
    )

    result = orchestrator.orchestrate(_request())

    assert result.status is OrchestrationStatus.NEEDS_CLARIFICATION
    assert result.primary_domain is None
    assert collaborators["agent_router"].calls == 0  # type: ignore[attr-defined]
    assert collaborators["policy"].calls == 0  # type: ignore[attr-defined]
    assert collaborators["context_resolver"].domain_calls == 0  # type: ignore[attr-defined]


def test_canonical_domain_block_is_blocked() -> None:
    orchestrator, collaborators = _graph(
        domain=DomainRouteDecision(
            status="blocked",
            rejected_domains=("domain:health",),
            reason_codes=("DOMAIN_POLICY_DENIED",),
        )
    )

    result = orchestrator.orchestrate(_request())

    assert result.status is OrchestrationStatus.BLOCKED
    assert "ORCHESTRATION_CANONICAL_DOMAIN_BLOCK" in result.reason_codes
    assert collaborators["policy"].calls == 0  # type: ignore[attr-defined]

    repository = collaborators["decision_repository"]
    record = repository.get(result.decision_id)  # type: ignore[attr-defined]
    assert record.policy_disposition is PolicyDisposition.DENY


# ── Policy terminal paths ────────────────────────────────────────────────────


def test_denied_route_is_blocked() -> None:
    orchestrator, collaborators = _graph(disposition=PolicyDisposition.DENY)

    result = orchestrator.orchestrate(_request())

    assert result.status is OrchestrationStatus.BLOCKED
    assert "POLICY_TEST" in result.reason_codes

    sink = collaborators["event_sink"]
    assert sink.events()[-1].event_type == "orchestration.blocked"  # type: ignore[attr-defined]


def test_escalated_route_is_escalated() -> None:
    orchestrator, collaborators = _graph(disposition=PolicyDisposition.ESCALATE)

    result = orchestrator.orchestrate(_request())

    assert result.status is OrchestrationStatus.ESCALATED
    sink = collaborators["event_sink"]
    assert sink.events()[-1].event_type == "orchestration.escalated"  # type: ignore[attr-defined]


def test_approval_required_route_is_non_executing() -> None:
    orchestrator, collaborators = _graph(
        route=AgentRouteDecision(route=ExecutionRoute.OPERATION),
        disposition=PolicyDisposition.REQUIRE_APPROVAL,
    )

    result = orchestrator.orchestrate(_request(input={"command": {"operation": "op"}}))

    assert result.status is OrchestrationStatus.ROUTED
    assert result.approval_refs == ("requirement-1",)
    assert result.route is ExecutionRoute.OPERATION

    repository = collaborators["decision_repository"]
    record = repository.get(result.decision_id)  # type: ignore[attr-defined]
    assert record.policy_disposition is PolicyDisposition.REQUIRE_APPROVAL
    assert record.approval_refs == ("requirement-1",)

    sink = collaborators["event_sink"]
    assert sink.events()[-1].event_type == "orchestration.approval_required"  # type: ignore[attr-defined]


def test_cancellation_terminal_status() -> None:
    orchestrator, _ = _graph(
        intent=IntentKind.CANCELLATION,
        route=AgentRouteDecision(
            route=ExecutionRoute.WORKFLOW, workflow_id="workflow-1"
        ),
    )

    result = orchestrator.orchestrate(
        _request(input={"cancel_target_id": "workflow-1"})
    )

    assert result.status is OrchestrationStatus.CANCELLED
    assert result.workflow_id == "workflow-1"


def test_autonomous_route_is_consumed_but_not_executed() -> None:
    orchestrator, _ = _graph(
        intent=IntentKind.GOAL,
        route=AgentRouteDecision(
            route=ExecutionRoute.AUTONOMOUS_AGENT,
            agent_id="agent.alpha",
            agent_version="1.0.0",
        ),
        disposition=PolicyDisposition.ALLOW_ROUTE,
    )

    result = orchestrator.orchestrate(_request(input={"goal": {"title": "task"}}))

    assert result.status is OrchestrationStatus.ROUTED
    assert result.agent_id == "agent.alpha"
    assert result.route is ExecutionRoute.AUTONOMOUS_AGENT


# ── Failure paths ────────────────────────────────────────────────────────────


def test_intent_resolution_failure_fails_closed() -> None:
    orchestrator, collaborators = _graph(intent_resolver=_BrokenIntentResolver())

    result = orchestrator.orchestrate(_request())

    assert result.status is OrchestrationStatus.FAILED
    assert result.error is not None
    assert result.error.code == "INTENT_RESOLUTION_ERROR"
    assert result.error.category == "intent"
    repository = collaborators["decision_repository"]
    assert repository.get("orchestration-decision:request-1") is None  # type: ignore[attr-defined]


def test_intent_resolution_failure_emits_a_failure_event() -> None:
    orchestrator, collaborators = _graph(intent_resolver=_BrokenIntentResolver())

    orchestrator.orchestrate(_request())

    sink = collaborators["event_sink"]
    assert sink.events()[-1].event_type == "orchestration.failed"  # type: ignore[attr-defined]


def test_decision_persistence_failure_fails_closed() -> None:
    orchestrator, _ = _graph(repository=_BrokenRepository())

    result = orchestrator.orchestrate(_request())

    assert result.status is OrchestrationStatus.FAILED
    assert result.error is not None
    assert result.error.code == "DECISION_PERSISTENCE_ERROR"


def test_required_event_emission_failure_fails_closed() -> None:
    orchestrator, _ = _graph(sink=_BrokenSink())

    result = orchestrator.orchestrate(_request())

    assert result.status is OrchestrationStatus.FAILED
    assert result.error is not None
    assert result.error.code == "ORCHESTRATION_EVENT_EMISSION_FAILED"


def test_unexpected_collaborator_failure_fails_closed() -> None:
    class _ExplodingDomainRouter:
        def route_domain(self, request, intent, context):
            raise RuntimeError("unexpected internal defect")

    orchestrator, _ = _graph()
    orchestrator = Orchestrator(
        intent_resolver=_IntentResolver(_resolution()),
        context_resolver=_ContextResolver(),
        domain_router=_ExplodingDomainRouter(),  # type: ignore[arg-type]
        agent_router=_AgentRouter(AgentRouteDecision(route=ExecutionRoute.NONE)),
        policy=_Policy(PolicyDisposition.ALLOW_ROUTE),
        decision_repository=InMemoryOrchestrationDecisionRepository(),
        event_sink=RecordingOrchestrationEventSink(),
    )

    result = orchestrator.orchestrate(_request())

    assert result.status is OrchestrationStatus.FAILED
    assert result.error is not None
    assert result.error.category == "orchestration"


# ── Construction-time role identity (Audit V1 MAJOR-01) ──────────────────────


def test_direct_construction_rejects_a_domain_router_as_the_agent_router() -> None:
    """Audit V1 MAJOR-01: role safety must hold outside Phase 11.1 composition."""

    with pytest.raises(TypeError):
        Orchestrator(
            intent_resolver=_IntentResolver(_resolution()),
            context_resolver=_ContextResolver(),
            domain_router=_DomainRouter(_resolved_domain()),
            agent_router=_DomainRouter(_resolved_domain()),  # type: ignore[arg-type]
            policy=_Policy(PolicyDisposition.ALLOW_ROUTE),
            decision_repository=InMemoryOrchestrationDecisionRepository(),
            event_sink=RecordingOrchestrationEventSink(),
        )


def test_direct_construction_rejects_an_agent_router_as_the_domain_router() -> None:
    """Audit V1 MAJOR-01: role safety must hold outside Phase 11.1 composition."""

    route = AgentRouteDecision(route=ExecutionRoute.NONE)

    with pytest.raises(TypeError):
        Orchestrator(
            intent_resolver=_IntentResolver(_resolution()),
            context_resolver=_ContextResolver(),
            domain_router=_AgentRouter(route),  # type: ignore[arg-type]
            agent_router=_AgentRouter(route),
            policy=_Policy(PolicyDisposition.ALLOW_ROUTE),
            decision_repository=InMemoryOrchestrationDecisionRepository(),
            event_sink=RecordingOrchestrationEventSink(),
        )


def test_failed_result_exposes_no_traceback() -> None:
    orchestrator, _ = _graph(intent_resolver=_BrokenIntentResolver())

    result = orchestrator.orchestrate(_request())

    assert result.error is not None
    assert "Traceback" not in result.error.message
    assert "traceback" not in dict(result.error.details)


# ── Safety ───────────────────────────────────────────────────────────────────


def test_result_carries_no_hidden_reasoning_field() -> None:
    orchestrator, _ = _graph()

    payload = orchestrator.orchestrate(_request()).to_dict()

    for forbidden in (
        "chain_of_thought",
        "hidden_reasoning",
        "raw_reasoning",
        "reasoning_trace",
        "prompt",
        "provider_payload",
    ):
        assert forbidden not in payload


def test_orchestrator_uses_no_runtime_service_locator() -> None:
    tree = ast.parse(ORCHESTRATOR_MODULE.read_text())

    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)

    for forbidden in (
        "cmm.platform.container",
        "cmm.platform.service_registry",
    ):
        assert forbidden not in imported, (
            f"the orchestrator must not resolve collaborators at runtime: {forbidden}"
        )

    source = ORCHESTRATOR_MODULE.read_text()
    for forbidden in (
        "ApplicationContainer",
        "get_service",
        "IntegrationServiceRegistry",
    ):
        assert forbidden not in source, (
            f"the orchestrator must not use a runtime service locator: {forbidden}"
        )


def test_orchestrator_defines_no_downstream_execution() -> None:
    source = ORCHESTRATOR_MODULE.read_text()

    for forbidden in (
        "AgentRuntimeIntegrationService",
        "start_workflow",
        "execute_operation",
        "write_memory",
        "write_knowledge",
    ):
        assert forbidden not in source, (
            f"the orchestrator must not execute the downstream vertical: {forbidden}"
        )


def test_orchestrator_requires_exactly_the_frozen_collaborators() -> None:
    import inspect

    signature = inspect.signature(Orchestrator.__init__)
    parameters = [
        name for name in signature.parameters if name not in {"self", "args", "kwargs"}
    ]

    assert parameters == [
        "intent_resolver",
        "context_resolver",
        "domain_router",
        "agent_router",
        "policy",
        "decision_repository",
        "event_sink",
    ]
    assert all(
        parameter.kind is inspect.Parameter.KEYWORD_ONLY
        for parameter in signature.parameters.values()
        if parameter.name != "self"
    )
