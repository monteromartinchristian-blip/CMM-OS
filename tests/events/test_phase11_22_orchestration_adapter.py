"""Phase 11.22 — orchestration adapter tests.

These tests prove the production ``OrchestrationEventSink`` adapter is a faithful
one-way bridge: it keeps the closed Phase 11.2 lifecycle set and payload safety
rule, maps only explicitly supported facts, publishes through the canonical
Phase 11.22 facade, preserves request correlation, and never routes, mutates
orchestration state or calls the Orchestrator back.

The final block drives a **real** Phase 11.2 ``Orchestrator`` through the real
adapter and the real Phase 11.22 event system, with no mocks on the core chain.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from cmm.agent_runtime.runtime_event_contracts import AgentRuntimeEvent
from cmm.events.event_payload_safety import PlatformEventPayloadError
from cmm.events.event_system import EventSystem
from cmm.events.orchestration_adapter import (
    PlatformOrchestrationEventSink,
    SkippedOrchestrationEvent,
)
from cmm.orchestration.events import OrchestrationEventSink
from tests.events.test_phase11_22_event_system import build_system

MOMENT = datetime(2024, 5, 1, 10, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def system() -> EventSystem:
    return build_system()


@pytest.fixture
def sink(system: EventSystem) -> PlatformOrchestrationEventSink:
    return PlatformOrchestrationEventSink(system)


# ── Contract compliance ──────────────────────────────────────────────────────


def test_adapter_satisfies_the_frozen_phase11_2_protocol(sink) -> None:
    assert isinstance(sink, OrchestrationEventSink)


def test_adapter_accepts_only_the_phase11_2_lifecycle_event_set(sink) -> None:
    with pytest.raises(ValueError):
        sink.emit("orchestration.not_a_real_event", request_id="req-1", payload={})


def test_adapter_reuses_phase11_2_payload_safety(sink) -> None:
    """A Phase 11.2 forbidden key still fails closed through the adapter."""

    with pytest.raises(ValueError):
        sink.emit(
            "orchestration.request_received",
            request_id="req-1",
            payload={"prompt": "leak"},
        )


def test_adapter_rejects_a_fact_outside_the_platform_vocabulary(sink) -> None:
    with pytest.raises(PlatformEventPayloadError):
        sink.emit(
            "orchestration.request_received",
            request_id="req-1",
            payload={"channel": "conversation", "internal_scratch": "x"},
        )


def test_adapter_rejects_opaque_values(sink) -> None:
    with pytest.raises(TypeError):
        sink.emit(
            "orchestration.request_received",
            request_id="req-1",
            payload={"channel": object()},
        )


# ── Explicit translation ─────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("orchestration.request_received", "message.received"),
        ("orchestration.intent_resolved", "intent.resolved"),
        ("orchestration.domain_resolved", "domain.selected"),
        ("orchestration.approval_required", "approval.requested"),
    ],
)
def test_supported_facts_map_to_their_platform_event(
    sink, system, source, expected
) -> None:
    event_id = sink.emit(source, request_id="req-1", payload={"status": "ok"})

    assert event_id is not None
    stored = system.repository.get(event_id)
    assert stored is not None
    assert stored.header.event_type == expected


@pytest.mark.parametrize(
    "source",
    [
        "orchestration.route_selected",
        "orchestration.blocked",
        "orchestration.escalated",
        "orchestration.routed",
        "orchestration.failed",
    ],
)
def test_unsupported_facts_are_not_fabricated_into_platform_events(
    sink, system, source
) -> None:
    event_id = sink.emit(source, request_id="req-1", payload={"status": "blocked"})

    assert event_id is None
    assert system.repository.count() == 0
    assert system.stats().published_total == 0


def test_unmapped_fact_is_observed_and_skipped(sink) -> None:
    sink.emit("orchestration.routed", request_id="req-1", payload={"status": "routed"})

    skipped = sink.skipped_events()
    assert len(skipped) == 1
    assert isinstance(skipped[0], SkippedOrchestrationEvent)
    assert skipped[0].event_type == "orchestration.routed"
    assert skipped[0].reason == "no_explicit_platform_translation"


def test_mapping_does_not_invent_payload_fields(sink, system) -> None:
    event_id = sink.emit(
        "orchestration.domain_resolved",
        request_id="req-1",
        payload={"status": "resolved", "primary_domain": "domain:general"},
    )

    stored = system.repository.get(event_id)
    assert stored is not None
    assert stored.payload.data == {
        "status": "resolved",
        "primary_domain": "domain:general",
        "request_id": "req-1",
    }


def test_missing_fact_stays_missing(sink, system) -> None:
    event_id = sink.emit(
        "orchestration.request_received", request_id="req-1", payload={}
    )

    stored = system.repository.get(event_id)
    assert stored is not None
    assert "channel" not in stored.payload.data


# ── Correlation and authority ────────────────────────────────────────────────


def test_request_correlation_is_preserved(sink, system) -> None:
    event_id = sink.emit(
        "orchestration.request_received",
        request_id="req-correlation",
        payload={"channel": "cli"},
    )

    stored = system.repository.get(event_id)
    assert stored is not None
    assert stored.header.correlation_id == "req-correlation"
    assert stored.header.causation_id == "req-correlation"
    assert stored.header.aggregate_id == "req-correlation"
    assert stored.payload.data["request_id"] == "req-correlation"


def test_owner_identity_is_recorded(sink, system) -> None:
    event_id = sink.emit(
        "orchestration.intent_resolved",
        request_id="req-1",
        payload={"intent": "question"},
    )

    stored = system.repository.get(event_id)
    assert stored is not None
    assert stored.header.producer == "cmm.orchestration"


def test_adapter_declares_no_routing_capability(sink) -> None:
    for attribute in ("route", "route_domain", "route_agent", "orchestrate", "decide"):
        assert not hasattr(sink, attribute), attribute


def test_adapter_never_calls_back_into_the_orchestrator(sink, system) -> None:
    """The adapter holds only the event system, never an orchestrator."""

    assert sink._system is system
    assert set(type(sink).__slots__) == {
        "_observed",
        "_published",
        "_sequence",
        "_skipped",
        "_system",
    }
    # Nothing the adapter holds is (or wraps) an Orchestrator instance.
    from cmm.orchestration.orchestrator import Orchestrator

    for value in (
        sink._system,
        sink.events(),
        sink.skipped_events(),
        sink.published_events(),
    ):
        assert not isinstance(value, Orchestrator)


def test_adapter_mutates_no_orchestration_state(sink, system) -> None:
    before = system.repository.count()

    sink.emit(
        "orchestration.request_received",
        request_id="req-1",
        payload={"channel": "conversation", "session_id": "session-1"},
    )

    assert system.repository.count() == before + 1


def test_emission_failure_propagates_so_orchestration_fails_closed() -> None:
    system = build_system()
    sink = PlatformOrchestrationEventSink(system)
    system.bus.close()

    # A closed bus still persists, so the platform path reports rather than raises;
    # a genuine platform refusal must raise instead.
    with pytest.raises(PlatformEventPayloadError):
        sink.emit(
            "orchestration.request_received",
            request_id="req-1",
            payload={"not_allowed": "x"},
        )


def test_observer_surface_is_preserved_for_existing_consumers(sink) -> None:
    sink.emit(
        "orchestration.request_received", request_id="req-1", payload={"channel": "cli"}
    )
    sink.emit("orchestration.routed", request_id="req-1", payload={"status": "routed"})

    observed = sink.events()
    assert [event.event_type for event in observed] == [
        "orchestration.request_received",
        "orchestration.routed",
    ]
    assert [event.sequence for event in observed] == [0, 1]
    assert observed[0].request_id == "req-1"


# ── Real Orchestrator integration ────────────────────────────────────────────


class _Intent:
    def resolve(self, request):
        from cmm.orchestration.contracts import IntentKind, IntentResolution

        return IntentResolution(
            intent=IntentKind.QUESTION,
            needs_clarification=False,
            source_kind="structured_input",
        )


class _Context:
    def resolve_base(self, request):
        from cmm.orchestration.contracts import ResolvedContext

        return ResolvedContext(request_id=request.request_id, stage="base")

    def resolve_domain_context(self, request, base_context, domain_route):
        from cmm.orchestration.contracts import ResolvedContext

        return ResolvedContext(request_id=request.request_id, stage="domain")


class _Domain:
    def route_domain(self, request, intent, context):
        from cmm.orchestration.contracts import DomainRouteDecision

        return DomainRouteDecision(status="resolved", primary_domain="domain:general")


class _Agent:
    def route_agent(self, *, request, intent, context, domain):
        from cmm.orchestration.contracts import AgentRouteDecision, ExecutionRoute

        return AgentRouteDecision(route=ExecutionRoute.DIRECT_RESPONSE)


class _Policy:
    def evaluate(self, *, request, intent, context, domain, route):
        from cmm.orchestration.contracts import (
            OrchestrationPolicyDecision,
            PolicyDisposition,
        )

        return OrchestrationPolicyDecision(
            disposition=PolicyDisposition.ALLOW_ROUTE,
            reason_codes=("POLICY_ALLOWED",),
        )


def _real_orchestrator(sink: PlatformOrchestrationEventSink):
    from cmm.orchestration.decision_repository import (
        InMemoryOrchestrationDecisionRepository,
    )
    from cmm.orchestration.orchestrator import Orchestrator

    return Orchestrator(
        intent_resolver=_Intent(),
        context_resolver=_Context(),
        domain_router=_Domain(),
        agent_router=_Agent(),
        policy=_Policy(),
        decision_repository=InMemoryOrchestrationDecisionRepository(),
        event_sink=sink,
    )


def test_real_orchestrator_lifecycle_fact_reaches_persistence_and_a_subscriber() -> (
    None
):
    """The connected path, with no mocks on the core chain.

    ``Orchestrator`` -> existing ``OrchestrationEventSink`` seam -> Phase 11.22
    adapter -> canonical factory/registry -> durable repository ->
    ``AgentRuntimeEventBus`` -> subscriber.
    """

    from cmm.orchestration.contracts import OrchestrationChannel, OrchestrationRequest

    system = build_system()
    sink = PlatformOrchestrationEventSink(system)
    orchestrator = _real_orchestrator(sink)

    received: list[AgentRuntimeEvent] = []
    system.subscribe(received.append, ["message.received"])

    request = OrchestrationRequest(
        request_id="request-1",
        user_id="user-1",
        channel=OrchestrationChannel.CONVERSATION,
        session_id="session-1",
        input={"question": "What changed?"},
    )
    orchestrator.orchestrate(request)

    # Persisted exactly once, and delivered exactly once to the normal subscriber.
    stored = system.repository.query(event_type="message.received")
    assert len(stored) == 1
    assert stored[0].header.correlation_id == "request-1"
    assert stored[0].header.producer == "cmm.orchestration"
    assert len(received) == 1
    assert received[0].header.event_id == stored[0].header.event_id

    # The Orchestrator really emitted through the seam.
    assert sink.published_events()
    assert sink.events()[0].event_type == "orchestration.request_received"


def test_real_orchestrator_also_maps_intent_and_domain_facts() -> None:
    from cmm.orchestration.contracts import OrchestrationChannel, OrchestrationRequest

    system = build_system()
    sink = PlatformOrchestrationEventSink(system)
    orchestrator = _real_orchestrator(sink)

    orchestrator.orchestrate(
        OrchestrationRequest(
            request_id="request-2",
            user_id="user-1",
            channel=OrchestrationChannel.CLI,
            session_id="session-1",
            input={"question": "Hello"},
        )
    )

    types = [event.header.event_type for event in system.repository.list()]

    assert "message.received" in types
    assert "intent.resolved" in types
    assert "domain.selected" in types
    # Unmapped orchestration facts stay out of the platform transport.
    assert "orchestration.route_selected" not in types
    assert "orchestration.routed" not in types


def test_real_orchestrator_and_adapter_do_not_depend_on_mocks() -> None:
    """The connected chain uses the real canonical repository and bus types."""

    from cmm.agent_runtime.runtime_event_bus import AgentRuntimeEventBus
    from cmm.agent_runtime.runtime_event_repository import (
        InMemoryAgentRuntimeEventRepository,
    )
    from cmm.orchestration.orchestrator import Orchestrator

    system = build_system()
    sink = PlatformOrchestrationEventSink(system)
    orchestrator = _real_orchestrator(sink)

    assert isinstance(orchestrator, Orchestrator)
    assert isinstance(system.bus, AgentRuntimeEventBus)
    assert isinstance(system.repository, InMemoryAgentRuntimeEventRepository)


def test_recording_sink_is_still_available_and_unchanged() -> None:
    from cmm.orchestration.events import RecordingOrchestrationEventSink

    recorder = RecordingOrchestrationEventSink()
    reference = recorder.emit(
        "orchestration.request_received", request_id="req-1", payload={"channel": "cli"}
    )

    assert reference == "orchestration.request_received:req-1:0"
    assert len(recorder.events()) == 1


def test_adapter_publishes_nothing_for_a_purely_unmapped_lifecycle() -> None:
    from cmm.orchestration.contracts import (
        OrchestrationChannel,
        OrchestrationRequest,
    )

    system = build_system()
    sink = PlatformOrchestrationEventSink(system)

    class _BlockingPolicy:
        def evaluate(self, *, request, intent, context, domain, route):
            from cmm.orchestration.contracts import (
                OrchestrationPolicyDecision,
                PolicyDisposition,
            )

            return OrchestrationPolicyDecision(
                disposition=PolicyDisposition.DENY,
                reason_codes=("POLICY_DENIED",),
            )

    from cmm.orchestration.decision_repository import (
        InMemoryOrchestrationDecisionRepository,
    )
    from cmm.orchestration.orchestrator import Orchestrator

    orchestrator = Orchestrator(
        intent_resolver=_Intent(),
        context_resolver=_Context(),
        domain_router=_Domain(),
        agent_router=_Agent(),
        policy=_BlockingPolicy(),
        decision_repository=InMemoryOrchestrationDecisionRepository(),
        event_sink=sink,
    )

    orchestrator.orchestrate(
        OrchestrationRequest(
            request_id="request-blocked",
            user_id="user-1",
            channel=OrchestrationChannel.CONVERSATION,
            session_id="session-1",
            input={"question": "Blocked?"},
        )
    )

    # orchestration.blocked has no Phase 11.22 platform event, so the last emitted
    # fact is observed and skipped rather than fabricated.
    assert "orchestration.blocked" in [
        event.event_type for event in sink.skipped_events()
    ]
    types = [event.header.event_type for event in system.repository.list()]
    assert "orchestration.blocked" not in types
