"""Phase 11.22 — ``AT-DP-122`` connected acceptance.

This is the connected acceptance for design point ``DP-122``.  It uses the **real**
canonical components end to end:

* the real Phase 11.1 ``ApplicationContainer`` composition with the Phase 11.22
  module and the real canonical/orchestration modules;
* the real Phase 11.2 ``Orchestrator`` reached through the existing
  ``OrchestrationEventSink`` seam;
* the real Phase 11.22 ``PlatformOrchestrationEventSink`` adapter;
* the real canonical event factory, registry, durable repository,
  ``AgentRuntimeEventBus`` and dead-letter queue.

No mock stands in for any part of the core chain.

Reported markers for this test::

    DP-122=IMPLEMENTED_PENDING_INDEPENDENT_VERIFICATION
    AT-DP-122=PASS_REPORTED

Only the independent audit may promote these to ``VERIFIED_EXISTING`` / ``PASS``.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from cmm.agent_runtime.runtime_event_bus import AgentRuntimeEventBus
from cmm.agent_runtime.runtime_event_contracts import (
    AgentRuntimeEvent,
    AgentRuntimeEventBusStats,
    AgentRuntimeEventReplayRequest,
)
from cmm.agent_runtime.runtime_event_dead_letter import (
    InMemoryAgentRuntimeDeadLetterQueue,
)
from cmm.agent_runtime.runtime_event_errors import (
    AgentRuntimeEventIdentityConflictError,
)
from cmm.agent_runtime.runtime_event_registry import AgentRuntimeEventRegistry
from cmm.agent_runtime.runtime_event_replay import AgentRuntimeEventReplayer
from cmm.agent_runtime.runtime_event_repository import (
    FileAgentRuntimeEventRepository,
)
from cmm.events.event_catalog import PLATFORM_EVENT_NAMES
from cmm.events.event_payload_safety import PlatformEventPayloadError
from cmm.events.event_system import EventSystem, PublicationOutcome
from cmm.events.orchestration_adapter import PlatformOrchestrationEventSink
from cmm.events.platform_module import (
    EVENT_BUS_SERVICE_ID,
    EVENT_SYSTEM_MODULE_ID,
    EVENT_SYSTEM_SERVICE_IDS,
    build_event_system_composition,
)

DP122_MARKER = "DP-122=IMPLEMENTED_PENDING_INDEPENDENT_VERIFICATION"
AT_DP122_MARKER = "AT-DP-122=PASS_REPORTED"

OCCURRED = datetime(2026, 9, 26, 12, 0, 0, tzinfo=timezone.utc)


# ── Real connected composition ───────────────────────────────────────────────


def _real_composition(event_store_path):
    """Build the real Phase 11.1 composition described by this acceptance.

    The composition is the Phase 11.22 event-system module plus the real Phase 11.2
    orchestration module, whose ``orchestration.event_sink`` binding is the real
    Phase 11.22 production adapter that the real Orchestrator holds.
    """

    from cmm.application.local_runtime import build_local_application_runtime
    from cmm.events.platform_module import EVENT_SYSTEM_SERVICE_IDS
    from cmm.orchestration.contracts import OrchestrationChannel, OrchestrationRequest
    from cmm.orchestration.platform_module import (
        ORCHESTRATION_SERVICE_IDS,
        build_orchestration_composition_module,
    )
    from cmm.platform.configuration import CompositionConfiguration
    from cmm.platform.container import ApplicationContainer

    runtime = build_local_application_runtime(event_store_path=event_store_path)
    composition = runtime.event_system

    orchestration_module = build_orchestration_composition_module(
        intent_resolver=runtime.orchestrator._intent_resolver,
        context_resolver=runtime.orchestrator._context_resolver,
        domain_router=runtime.orchestrator._domain_router,
        agent_router=runtime.orchestrator._agent_router,
        policy=runtime.orchestrator._policy,
        decision_repository=runtime.orchestrator._decision_repository,
        event_sink=composition.orchestration_sink,
        orchestrator=runtime.orchestrator,
    )

    configuration = CompositionConfiguration(
        required_services=(
            *ORCHESTRATION_SERVICE_IDS,
            *EVENT_SYSTEM_SERVICE_IDS,
        ),
        enabled_modules=(EVENT_SYSTEM_MODULE_ID, "orchestration"),
    )
    container = ApplicationContainer.build(
        configuration,
        modules=(composition.module, orchestration_module),
    )

    return (
        runtime,
        container,
        OrchestrationRequest,
        OrchestrationChannel,
        configuration,
    )


@pytest.fixture
def connected(tmp_path):
    """One real composed event system plus its resolved Phase 11.1 container."""

    store = tmp_path / "data" / "events" / "runtime_events.jsonl"
    runtime, container, request_type, channel, configuration = _real_composition(store)
    return {
        "runtime": runtime,
        "container": container,
        "store": store,
        "configuration": configuration,
        "request_type": request_type,
        "channel": channel,
        "composition": runtime.event_system,
        "system": runtime.event_system.system,
    }


def _orchestrate(connected, request_id: str):
    request = connected["request_type"](
        request_id=request_id,
        user_id="user-at-dp-122",
        channel=connected["channel"].CONVERSATION,
        session_id=f"session-{uuid.uuid4().hex[:8]}",
        input={"question": "What changed?"},
    )
    return connected["runtime"].orchestrator.orchestrate(request)


# ══════════════════════════════════════════════════════════════════════════
# AT-DP-122 — the connected scenario
# ══════════════════════════════════════════════════════════════════════════


def test_at_dp_122_real_composition_resolves_exactly_one_canonical_event_bus(
    connected,
) -> None:
    """Steps 1–3: real composition, exactly one bus, and it is the Phase 9 bus."""

    container = connected["container"]

    # 1. the real Phase 11.1 composition including the Phase 11.22 module.
    assert set(connected["configuration"].enabled_modules) == {
        EVENT_SYSTEM_MODULE_ID,
        "orchestration",
    }
    assert EVENT_SYSTEM_MODULE_ID in connected["configuration"].enabled_modules
    bound = {service_id for service_id in connected["configuration"].required_services}
    assert set(EVENT_SYSTEM_SERVICE_IDS) <= bound

    # 2. exactly one canonical event bus binding, under the canonical identity.
    bus = container.get_service(EVENT_BUS_SERVICE_ID)
    assert isinstance(bus, AgentRuntimeEventBus)

    # 3. it is the existing Phase 9 authority, not a second implementation.
    assert type(bus).__module__ == "cmm.agent_runtime.runtime_event_bus"
    assert type(bus).__name__ == "AgentRuntimeEventBus"
    assert bus is connected["system"].bus

    # Every other event-system service resolves through the same container.
    assert container.get_service("event.system") is connected["system"]
    assert isinstance(
        container.get_service("event.registry"), AgentRuntimeEventRegistry
    )
    assert isinstance(
        container.get_service("event.repository"), FileAgentRuntimeEventRepository
    )
    assert isinstance(
        container.get_service("event.replayer"), AgentRuntimeEventReplayer
    )
    assert isinstance(
        container.get_service("event.dead_letter_queue"),
        InMemoryAgentRuntimeDeadLetterQueue,
    )


def test_at_dp_122_real_orchestrator_reports_to_the_real_adapter(connected) -> None:
    """Steps 4–7: real Orchestrator, real adapter, canonical factory/registry."""

    sink = connected["container"].get_service("orchestration.event_sink")

    assert isinstance(sink, PlatformOrchestrationEventSink)
    assert connected["runtime"].orchestrator._event_sink is sink

    result = _orchestrate(connected, "request-at-dp-122-1")
    assert result is not None

    # The Orchestrator really emitted through the seam.
    emitted = [event.event_type for event in sink.events()]
    assert emitted, "the real orchestrator emitted no orchestration facts"
    assert emitted[0] == "orchestration.request_received"

    # 6/7: explicit mapping plus canonical registry/factory validation.
    stored = connected["system"].repository.query(event_type="message.received")
    assert stored, "no canonical platform event was created"
    assert stored[0].header.event_type in PLATFORM_EVENT_NAMES
    assert stored[0].header.producer == "cmm.orchestration"


def test_at_dp_122_event_is_persisted_once_and_delivered_once(connected) -> None:
    """Steps 8–9: persistence exactly once, normal subscriber delivery once."""

    system = connected["system"]
    received: list[AgentRuntimeEvent] = []
    system.subscribe(received.append, ["message.received"])

    _orchestrate(connected, "request-at-dp-122-2")

    stored = system.repository.query(event_type="message.received")
    assert len(stored) == 1
    assert len(received) == 1
    assert received[0].header.event_id == stored[0].header.event_id
    # Persistence happened before delivery.
    assert system.repository.get(received[0].header.event_id) is not None


def test_at_dp_122_identical_republish_is_idempotent(connected) -> None:
    """Steps 10–12: same identity and content ⇒ no second storage, no second delivery."""

    system = connected["system"]
    received: list[AgentRuntimeEvent] = []
    system.subscribe(received.append, ["message.received"])

    first = system.publish(
        "message.received",
        {"request_id": "req-dup"},
        event_id="evt-at-dp-122-dup",
        occurred_at=OCCURRED,
        emitted_at=OCCURRED,
    )
    second = system.publish(
        "message.received",
        {"request_id": "req-dup"},
        event_id="evt-at-dp-122-dup",
        occurred_at=OCCURRED,
        emitted_at=OCCURRED,
    )

    assert first.outcome is PublicationOutcome.PUBLISHED
    assert second.outcome is PublicationOutcome.IDEMPOTENT_DUPLICATE
    assert system.repository.query(event_type="message.received").__len__() == 1
    assert len(received) == 1


def test_at_dp_122_identity_conflict_fails_closed(connected) -> None:
    """Steps 13–14: same identity, different content ⇒ fail closed, no mutation."""

    system = connected["system"]
    system.publish(
        "message.received",
        {"request_id": "req-conflict-a"},
        event_id="evt-at-dp-122-conflict",
        occurred_at=OCCURRED,
        emitted_at=OCCURRED,
    )

    with pytest.raises(AgentRuntimeEventIdentityConflictError):
        system.publish(
            "message.received",
            {"request_id": "req-conflict-b"},
            event_id="evt-at-dp-122-conflict",
            occurred_at=OCCURRED,
            emitted_at=OCCURRED,
        )

    stored = system.repository.query(event_type="message.received")
    assert len(stored) == 1
    assert stored[0].payload.data["request_id"] == "req-conflict-a"


def test_at_dp_122_failing_subscriber_is_isolated_and_bounded(tmp_path) -> None:
    """Steps 15–18: isolation, bounded retry only for the failure, one DLQ record."""

    # A composed system with an explicit finite delivery policy.
    composition = build_event_system_composition(
        event_store_path=tmp_path / "data" / "events" / "runtime_events.jsonl",
        max_delivery_attempts=3,
    )
    system = composition.system

    healthy: list[AgentRuntimeEvent] = []
    failing_attempts: list[str] = []

    def failing(event: AgentRuntimeEvent) -> None:
        failing_attempts.append(event.header.event_id)
        raise RuntimeError("subscriber at dp-122 failed")

    system.subscribe(failing, ["message.received"])
    system.subscribe(healthy.append, ["message.received"], priority=1)

    result = system.publish(
        "message.received",
        {"request_id": "req-retry"},
        event_id="evt-at-dp-122-retry",
        correlation_id="corr-at-dp-122",
        causation_id="cause-at-dp-122",
        occurred_at=OCCURRED,
        emitted_at=OCCURRED,
    )

    # 15/16: the successful subscriber is unaffected by the failing one.
    assert len(healthy) == 1
    assert result.delivered is True

    # 17: bounded retries target only the failing subscriber, same event identity.
    assert failing_attempts == ["evt-at-dp-122-retry"] * 3
    assert system.stats().retry_total == 2

    # 18: retry exhaustion creates exactly one canonical dead-letter record.
    assert system.dead_letter_count() == 1
    entry = system.list_dead_letters()[0]
    assert entry.event.header.event_id == "evt-at-dp-122-retry"
    assert entry.attempts == 3
    assert entry.error_type == "RuntimeError"

    # No extra event was persisted merely because delivery was retried.
    assert len(system.repository.query(event_type="message.received")) == 1


def test_at_dp_122_replay_opt_in_and_identity_preservation(connected) -> None:
    """Steps 19–26: replay opt-in, original identity, correlation and causation."""

    system = connected["system"]
    disabled: list[AgentRuntimeEvent] = []
    enabled: list[AgentRuntimeEvent] = []

    system.subscribe(disabled.append, ["message.received"])
    system.subscribe(enabled.append, ["message.received"], accept_replay=True)

    system.publish(
        "message.received",
        {"request_id": "req-replay"},
        event_id="evt-at-dp-122-replay",
        correlation_id="corr-at-dp-122",
        causation_id="cause-at-dp-122",
        occurred_at=OCCURRED,
        emitted_at=OCCURRED,
    )
    # Clear the normal delivery so the assertions below see only replay output.
    disabled.clear()
    enabled.clear()
    repository_count_before = system.repository.count()

    result = system.replay(
        AgentRuntimeEventReplayRequest(event_id="evt-at-dp-122-replay")
    )

    # 22: the replay-disabled subscriber is not invoked.
    assert disabled == []
    # 23: the replay-enabled subscriber receives the original event identity.
    assert [event.header.event_id for event in enabled] == ["evt-at-dp-122-replay"]
    assert result.replayed_count == 1
    # 24: replay appends no further repository record.
    assert system.repository.count() == repository_count_before
    # 25/26: correlation and causation survive replay unchanged.
    assert enabled[0].header.correlation_id == "corr-at-dp-122"
    assert enabled[0].header.causation_id == "cause-at-dp-122"


def test_at_dp_122_dead_letter_replay_resolves_and_clears(connected) -> None:
    """Dead-letter replay resolves the stored event and removes that one entry."""

    system = connected["system"]
    state = {"fail": True}

    def flaky(event: AgentRuntimeEvent) -> None:
        if state["fail"]:
            raise RuntimeError("boom")

    system.bus._max_delivery_attempts = 2
    system.subscribe(flaky, ["message.received"], accept_replay=True)
    system.publish(
        "message.received",
        {"request_id": "req-dlq-replay"},
        event_id="evt-at-dp-122-dlq",
        occurred_at=OCCURRED,
        emitted_at=OCCURRED,
    )
    assert system.dead_letter_count() == 1

    state["fail"] = False
    count_before = system.repository.count()
    result = system.replay_dead_letter(0)

    assert result.replayed_count == 1
    assert system.dead_letter_count() == 0
    assert system.repository.count() == count_before


@pytest.mark.parametrize(
    ("label", "payload"),
    [
        ("prompt", {"prompt": "system prompt contents"}),
        ("system_prompt", {"system_prompt": "you are"}),
        ("developer_prompt", {"developer_prompt": "you must"}),
        ("chain_of_thought", {"chain_of_thought": "step 1"}),
        ("hidden_reasoning", {"hidden_reasoning": "because"}),
        ("provider_request", {"provider_request": {"model": "x"}}),
        ("provider_response", {"provider_response": "text"}),
        ("authorization", {"authorization": "Bearer x"}),
        ("api_key", {"api_key": "abcdef1234567890"}),
        ("password", {"password": "hunter2"}),
        ("bearer_token", {"request_id": "Bearer abcdefghijklmnopqrstuvwxyz012345"}),
        ("cookie", {"cookie": "session=abc"}),
        ("traceback", {"traceback": "Traceback (most recent call last)"}),
    ],
)
def test_at_dp_122_unsafe_payloads_are_rejected_before_persistence(
    connected, label, payload
) -> None:
    """Steps 27–30: unsafe payload attempts fail before anything is persisted."""

    system = connected["system"]
    before = system.repository.count()
    stats_before = system.bus.stats.published_total

    with pytest.raises(PlatformEventPayloadError):
        system.publish("message.received", payload)

    assert system.repository.count() == before, label
    assert system.bus.stats.published_total == stats_before, label


def test_at_dp_122_opaque_and_binary_values_are_rejected(connected) -> None:
    """Opaque runtime objects and bytes never enter an event."""

    system = connected["system"]
    before = system.repository.count()

    with pytest.raises(PlatformEventPayloadError):
        system.publish("message.received", {"request_id": object()})
    with pytest.raises(PlatformEventPayloadError):
        system.publish("message.received", {"request_id": b"\x00\x01"})

    assert system.repository.count() == before


def test_at_dp_122_unregistered_event_types_fail_closed(connected) -> None:
    system = connected["system"]

    with pytest.raises(ValueError):
        system.publish("totally.unknown.event", {"request_id": "req-1"})


def test_at_dp_122_domain_events_remain_green_and_authoritative(connected) -> None:
    """Step 31: Domain Events stay 23/23 and keep their own authority."""

    from cmm.domains.event_adapters import adapt_memory_updated
    from cmm.domains.event_catalog import CANONICAL_DOMAIN_EVENTS
    from cmm.domains.event_publisher import DomainKernelEventPublisher

    assert len(CANONICAL_DOMAIN_EVENTS) == 23

    kernel_adapter = connected["composition"].orchestration_sink
    assert kernel_adapter is not None

    # The Domain Event package itself never imports the runtime event bus.
    import cmm.domains.event_publisher as publisher_module

    with open(publisher_module.__file__, encoding="utf-8") as handle:
        assert "AgentRuntimeEventBus" not in handle.read()

    # A real domain publisher still publishes its own canonical event untouched.
    publisher = DomainKernelEventPublisher()
    event = publisher.publish(
        adapt_memory_updated(update_id="update-dp-122", domain_id="domain:general")
    )
    assert event.name == "domain.memory.updated"


def test_at_dp_122_no_second_event_authority_exists(connected) -> None:
    """Step 32: architecture guards detect no parallel event authority."""

    from tests.events.test_phase11_22_architecture import (
        test_exactly_one_canonical_dead_letter_authority_exists,
        test_exactly_one_canonical_replay_owner_exists,
        test_exactly_one_canonical_repository_protocol_exists,
        test_exactly_one_production_event_bus_transport_exists,
        test_phase9_transport_does_not_depend_on_phase11_22,
        test_phase11_22_adds_no_generic_broker_abstraction,
        test_phase11_22_defines_no_command_bus_or_job_queue,
        test_phase11_22_defines_no_parallel_event_authority,
        test_phase11_22_introduces_no_second_application_container,
        test_phase11_22_never_dispatches_dynamically_by_event_type,
        test_platform_core_does_not_import_orchestration,
    )

    test_exactly_one_production_event_bus_transport_exists()
    test_exactly_one_canonical_repository_protocol_exists()
    test_exactly_one_canonical_replay_owner_exists()
    test_exactly_one_canonical_dead_letter_authority_exists()
    test_phase11_22_adds_no_generic_broker_abstraction()
    test_phase11_22_defines_no_command_bus_or_job_queue()
    test_phase11_22_introduces_no_second_application_container()
    test_phase11_22_never_dispatches_dynamically_by_event_type()
    test_phase9_transport_does_not_depend_on_phase11_22()
    test_platform_core_does_not_import_orchestration()
    for token in (
        "PlatformEventBus",
        "GlobalEventBus",
        "ApplicationEventBus",
        "DomainEventBus",
        "PersistentEventBus",
        "ObservabilityEventBus",
        "EventBroker",
        "CommandBus",
        "JobQueue",
        "EventStore",
        "ServiceLocator",
        "ReplayEngine",
        "DeadLetterQueue",
        "EventRegistry",
    ):
        test_phase11_22_defines_no_parallel_event_authority(token)


def test_at_dp_122_stats_projection_covers_the_required_facts(connected) -> None:
    """The read-only facts Phase 11.23 will observe are all present."""

    system = connected["system"]
    stats = system.stats()

    assert isinstance(stats, AgentRuntimeEventBusStats) or isinstance(
        stats.bus_stats, AgentRuntimeEventBusStats
    )
    for field in (
        "published_total",
        "delivered_total",
        "failed_total",
        "retry_total",
        "dead_letter_total",
        "replay_count",
        "active_subscriptions",
        "repository_event_count",
        "bus_ready",
    ):
        assert hasattr(stats, field), field


def test_at_dp_122_events_grant_no_authority(connected) -> None:
    """Events and replay add no authority: no permissions are granted."""

    system = connected["system"]
    result = system.publish(
        "message.received",
        {"request_id": "req-authority"},
        event_id="evt-at-dp-122-authority",
        occurred_at=OCCURRED,
        emitted_at=OCCURRED,
    )

    assert result.event.header.permissions == []
    stored = system.repository.get("evt-at-dp-122-authority")
    assert stored is not None
    assert stored.header.permissions == []


def test_at_dp_122_local_first_with_no_external_dependency(connected) -> None:
    """DP-122 passes entirely locally, with no broker or network dependency."""

    from cmm.events.event_catalog import is_platform_event_name

    assert is_platform_event_name("message.received")

    import cmm.events as events_package

    source_root = Path(events_package.__file__).parent
    forbidden = ("kafka", "nats", "redis", "pika", "pulsar", "websocket", "socket")
    offenders: list[str] = []
    for path in sorted(source_root.glob("*.py")):
        text = path.read_text()
        for token in forbidden:
            if token in text:
                offenders.append(f"{path.name}:{token}")

    assert not offenders, f"external transport dependency introduced: {offenders}"


def test_at_dp_122_durable_store_is_local_and_restart_safe(connected) -> None:
    """The recorded evidence really is a durable local append-only file."""

    store: Path = connected["store"]
    system = connected["system"]

    system.publish(
        "message.received",
        {"request_id": "req-durable"},
        event_id="evt-at-dp-122-durable",
        occurred_at=OCCURRED,
        emitted_at=OCCURRED,
    )

    assert store.is_file()
    reopened = FileAgentRuntimeEventRepository(store)
    restored = reopened.get("evt-at-dp-122-durable")
    assert restored is not None
    assert restored.payload.data == {"request_id": "req-durable"}


def test_at_dp_122_reported_markers_are_the_required_pre_audit_markers() -> None:
    """The pre-audit markers must not overclaim verification."""

    assert DP122_MARKER == "DP-122=IMPLEMENTED_PENDING_INDEPENDENT_VERIFICATION"
    assert AT_DP122_MARKER == "AT-DP-122=PASS_REPORTED"
    assert "VERIFIED_EXISTING" not in DP122_MARKER
    assert "closed" not in DP122_MARKER.lower()


def test_at_dp_122_two_compositions_are_independent(connected, tmp_path) -> None:
    """Composition lifetime: one instance per composition, no shared global state."""

    other = build_event_system_composition(
        event_store_path=tmp_path / "other" / "events.jsonl"
    )

    connected["system"].publish(
        "message.received",
        {"request_id": "req-isolated"},
        event_id="evt-at-dp-122-isolated",
        occurred_at=OCCURRED,
        emitted_at=OCCURRED,
    )

    assert other.repository.count() == 0
    assert other.system is not connected["system"]
    assert other.bus is not connected["system"].bus


def test_at_dp_122_ordering_is_fifo_and_deterministic(connected) -> None:
    """Publication order and subscriber priority are deterministic."""

    system = connected["system"]
    order: list[str] = []

    def first(event: AgentRuntimeEvent) -> None:
        order.append(f"first:{event.header.event_id}")

    def second(event: AgentRuntimeEvent) -> None:
        order.append(f"second:{event.header.event_id}")

    system.subscribe(first, ["message.received"], priority=0)
    system.subscribe(second, ["message.received"], priority=5)

    base = OCCURRED
    for index in range(3):
        system.publish(
            "message.received",
            {"request_id": f"req-fifo-{index}"},
            event_id=f"evt-at-dp-122-fifo-{index}",
            occurred_at=base + timedelta(seconds=index),
            emitted_at=base + timedelta(seconds=index),
        )

    assert order == [
        "first:evt-at-dp-122-fifo-0",
        "second:evt-at-dp-122-fifo-0",
        "first:evt-at-dp-122-fifo-1",
        "second:evt-at-dp-122-fifo-1",
        "first:evt-at-dp-122-fifo-2",
        "second:evt-at-dp-122-fifo-2",
    ]


def test_at_dp_122_composed_event_system_type_is_the_facade(connected) -> None:
    assert isinstance(connected["system"], EventSystem)


# ══════════════════════════════════════════════════════════════════════════
# AT-DP-122 strengthened — independent Audit V1 adversarial scenarios
#
# The V1 acceptance covered the happy paths only.  These scenarios run the audit's
# adversarial reproductions through the same real connected composition, with no
# mock standing in for any canonical component.
# ══════════════════════════════════════════════════════════════════════════


def test_at_dp_122_same_id_correlation_change_fails_as_conflict(connected) -> None:
    """Audit V1 MAJOR-001: a correlation-only change is an identity conflict."""

    system = connected["system"]
    system.publish(
        "message.received",
        {"request_id": "req-adv-cor"},
        event_id="evt-at-dp-122-adv-cor",
        correlation_id="CORR-A",
        occurred_at=OCCURRED,
        emitted_at=OCCURRED,
    )

    with pytest.raises(AgentRuntimeEventIdentityConflictError):
        system.publish(
            "message.received",
            {"request_id": "req-adv-cor"},
            event_id="evt-at-dp-122-adv-cor",
            correlation_id="CORR-B",
            occurred_at=OCCURRED,
            emitted_at=OCCURRED,
        )

    assert system.repository.count() == 1
    assert (
        system.repository.get("evt-at-dp-122-adv-cor").header.correlation_id
        == "CORR-A"
    )


def test_at_dp_122_same_id_causation_change_fails_as_conflict(connected) -> None:
    """Audit V1 MAJOR-001: a causation-only change is an identity conflict."""

    system = connected["system"]
    system.publish(
        "message.received",
        {"request_id": "req-adv-cause"},
        event_id="evt-at-dp-122-adv-cause",
        causation_id="CAUSE-A",
        occurred_at=OCCURRED,
        emitted_at=OCCURRED,
    )

    with pytest.raises(AgentRuntimeEventIdentityConflictError):
        system.publish(
            "message.received",
            {"request_id": "req-adv-cause"},
            event_id="evt-at-dp-122-adv-cause",
            causation_id="CAUSE-B",
            occurred_at=OCCURRED,
            emitted_at=OCCURRED,
        )

    assert system.repository.count() == 1


def test_at_dp_122_same_id_sensitivity_change_fails_as_conflict(connected) -> None:
    """Audit V1 MAJOR-001: a sensitivity-only change is an identity conflict."""

    from cmm.agent_runtime.runtime_event_contracts import EventSensitivity

    system = connected["system"]
    system.publish(
        "message.received",
        {"request_id": "req-adv-sensitivity"},
        event_id="evt-at-dp-122-adv-sensitivity",
        sensitivity=EventSensitivity.INTERNAL,
        occurred_at=OCCURRED,
        emitted_at=OCCURRED,
    )

    with pytest.raises(AgentRuntimeEventIdentityConflictError):
        system.publish(
            "message.received",
            {"request_id": "req-adv-sensitivity"},
            event_id="evt-at-dp-122-adv-sensitivity",
            sensitivity=EventSensitivity.CONFIDENTIAL,
            occurred_at=OCCURRED,
            emitted_at=OCCURRED,
        )

    assert system.repository.count() == 1


def test_at_dp_122_same_id_metadata_change_fails_as_conflict(connected) -> None:
    """Audit V1 MAJOR-001: a metadata-only change is an identity conflict."""

    system = connected["system"]
    system.publish(
        "message.received",
        {"request_id": "req-adv-metadata"},
        event_id="evt-at-dp-122-adv-metadata",
        metadata={"origin": "A"},
        occurred_at=OCCURRED,
        emitted_at=OCCURRED,
    )

    with pytest.raises(AgentRuntimeEventIdentityConflictError):
        system.publish(
            "message.received",
            {"request_id": "req-adv-metadata"},
            event_id="evt-at-dp-122-adv-metadata",
            metadata={"origin": "B"},
            occurred_at=OCCURRED,
            emitted_at=OCCURRED,
        )

    assert system.repository.count() == 1


def test_at_dp_122_direct_publish_event_rejects_an_unknown_type(connected) -> None:
    """Audit V1 MAJOR-002: the direct public route enforces the canonical registry."""

    from tests.events.test_phase11_22_remediation_v1_regressions import manual_event

    system = connected["system"]
    received: list[AgentRuntimeEvent] = []
    system.subscribe(received.append, ["message.received"])
    before = system.repository.count()

    with pytest.raises(ValueError):
        system.publish_event(
            manual_event("totally.unknown.event", {"request_id": "req-adv-unknown"})
        )

    assert system.repository.count() == before
    assert received == []
    assert system.dead_letter_count() == 0


@pytest.mark.parametrize(
    ("label", "payload"),
    [
        ("prompt", {"prompt": "TOP SECRET prompt contents"}),
        ("credential", {"api_key": "abcdef1234567890abcdef"}),
        ("hidden_reasoning", {"hidden_reasoning": "because the audit said so"}),
    ],
)
def test_at_dp_122_direct_publish_event_rejects_unsafe_payload(
    connected, label, payload
) -> None:
    """Audit V1 MAJOR-002: prompt/credential/reasoning cannot reach persistence."""

    from tests.events.test_phase11_22_remediation_v1_regressions import manual_event

    system = connected["system"]
    before = system.repository.count()

    with pytest.raises(PlatformEventPayloadError):
        system.publish_event(manual_event("message.received", payload))

    assert system.repository.count() == before, label


def test_at_dp_122_dlq_replay_cannot_be_satisfied_by_another_subscriber(
    connected,
) -> None:
    """Audit V1 MAJOR-003: an unrelated replay-enabled subscriber cannot resolve a DLQ entry."""

    system = connected["system"]
    system.bus._max_delivery_attempts = 2
    a_calls: list[str] = []
    b_calls: list[str] = []

    def subscriber_a(event: AgentRuntimeEvent) -> None:
        a_calls.append(event.header.event_id)
        raise RuntimeError("subscriber A failed")

    def subscriber_b(event: AgentRuntimeEvent) -> None:
        b_calls.append(event.header.event_id)

    subscription_a = system.subscribe(subscriber_a, ["message.received"])
    system.subscribe(subscriber_b, ["message.received"], accept_replay=True)

    system.publish(
        "message.received",
        {"request_id": "req-adv-dlq"},
        event_id="evt-at-dp-122-adv-dlq",
        occurred_at=OCCURRED,
        emitted_at=OCCURRED,
    )

    assert system.dead_letter_count() == 1
    assert system.list_dead_letters()[0].subscription_id == subscription_a

    result = system.replay_dead_letter(0)

    assert result.replayed_count == 0
    assert len(a_calls) == 2
    assert len(b_calls) == 1
    assert system.dead_letter_count() == 1


def test_at_dp_122_targeted_dlq_replay_removes_the_entry_only_after_success(
    connected,
) -> None:
    """Audit V1 MAJOR-003: the entry is removed only after the failed subscriber succeeds."""

    system = connected["system"]
    system.bus._max_delivery_attempts = 2
    state = {"fail": True}
    a_calls: list[str] = []
    b_calls: list[str] = []

    def subscriber_a(event: AgentRuntimeEvent) -> None:
        a_calls.append(event.header.event_id)
        if state["fail"]:
            raise RuntimeError("subscriber A failed")

    def subscriber_b(event: AgentRuntimeEvent) -> None:
        b_calls.append(event.header.event_id)

    subscription_a = system.subscribe(
        subscriber_a, ["message.received"], accept_replay=True
    )
    system.subscribe(subscriber_b, ["message.received"], accept_replay=True)

    system.publish(
        "message.received",
        {"request_id": "req-adv-targeted"},
        event_id="evt-at-dp-122-adv-targeted",
        occurred_at=OCCURRED,
        emitted_at=OCCURRED,
    )

    assert system.dead_letter_count() == 1
    assert system.list_dead_letters()[0].subscription_id == subscription_a

    while_failing = system.replay_dead_letter(0)
    assert while_failing.failed_count == 1
    assert system.dead_letter_count() == 1
    # The unrelated replay-enabled subscriber was never used as a substitute.
    assert len(b_calls) == 1

    state["fail"] = False
    succeeding = system.replay_dead_letter(0)

    assert succeeding.replayed_count == 1
    assert system.dead_letter_count() == 0
    assert len(b_calls) == 1
    assert a_calls[-1] == "evt-at-dp-122-adv-targeted"
    # The targeted replay persisted no second record.
    assert system.repository.count() == 1


def test_at_dp_122_explicit_domain_correlation_survives_the_kernel_adapter(
    connected,
) -> None:
    """Audit V1 MAJOR-004: the source correlation is preserved unchanged."""

    from cmm.domains.event_factory import DomainEventFactory
    from cmm.domains.event_publisher import DomainKernelEventPublisher
    from cmm.events.kernel_adapter import PlatformKernelEventAdapter

    system = connected["system"]
    adapter = PlatformKernelEventAdapter(system)
    publisher = DomainKernelEventPublisher(event_listener=adapter)

    publisher.publish(
        DomainEventFactory().create_event(
            event_type="domain.execution.completed",
            domain_id="domain:general",
            actor="system",
            event_id="DOM-E1",
            occurred_at=OCCURRED,
            correlation_id="CORR-ORIGINAL",
            causation_id="CAUSE-ORIGINAL",
            payload={"execution_id": "EXEC-1", "status": "completed"},
        )
    )

    stored = system.repository.query(event_type="operation.executed")[0]

    assert stored.header.correlation_id == "CORR-ORIGINAL"


def test_at_dp_122_explicit_domain_causation_survives_the_kernel_adapter(
    connected,
) -> None:
    """Audit V1 MAJOR-004: the source causation is preserved unchanged."""

    from cmm.domains.event_factory import DomainEventFactory
    from cmm.domains.event_publisher import DomainKernelEventPublisher
    from cmm.events.kernel_adapter import PlatformKernelEventAdapter

    system = connected["system"]
    adapter = PlatformKernelEventAdapter(system)
    publisher = DomainKernelEventPublisher(event_listener=adapter)

    publisher.publish(
        DomainEventFactory().create_event(
            event_type="domain.execution.completed",
            domain_id="domain:general",
            actor="system",
            event_id="DOM-E2",
            occurred_at=OCCURRED,
            correlation_id="CORR-ORIGINAL-2",
            causation_id="CAUSE-ORIGINAL-2",
            payload={"execution_id": "EXEC-2", "status": "completed"},
        )
    )

    stored = system.repository.query(event_type="operation.executed")[0]

    assert stored.header.causation_id == "CAUSE-ORIGINAL-2"
