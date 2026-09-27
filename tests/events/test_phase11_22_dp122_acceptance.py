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

import array
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from cmm.agent_runtime.runtime_event_bus import AgentRuntimeEventBus
from cmm.agent_runtime.runtime_event_contracts import (
    AgentRuntimeEvent,
    AgentRuntimeEventBusStats,
    AgentRuntimeEventDelivery,
    AgentRuntimeEventReplayRequest,
    EventSensitivity,
)
from cmm.agent_runtime.runtime_event_dead_letter import (
    InMemoryAgentRuntimeDeadLetterQueue,
)
from cmm.agent_runtime.runtime_event_errors import (
    AgentRuntimeEventIdentityConflictError,
    AgentRuntimeEventSerializationError,
)
from cmm.agent_runtime.runtime_event_factory import (
    AgentRuntimeEventFactory,
    event_fingerprint,
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
        system.repository.get("evt-at-dp-122-adv-cor").header.correlation_id == "CORR-A"
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


# ══════════════════════════════════════════════════════════════════════════
# Remediation V2 — AT-DP-122 additions for the four new V2 majors
#
# The real composed event system (file-backed canonical repository, canonical
# registry/bus/DLQ, real Domain Event publisher and Kernel bridge) is used
# throughout; no component is replaced by a mock.
# ══════════════════════════════════════════════════════════════════════════

#: Producer-controlled persisted header channels carrying forbidden content.
AT_DP_122_UNSAFE_HEADER_FACTS = (
    ("metadata_prompt", {"metadata": {"prompt": "TOP SECRET"}}),
    (
        "metadata_api_key",
        {"metadata": {"api_key": "sk-abcdefghijklmnop"}},
    ),
    ("permissions_credential", {"permissions": ["api_key=sk-abcdefghijklmnop"]}),
    ("producer_credential", {"producer": "api_key=sk-abcdefghijklmnop"}),
    ("source_forbidden_text", {"source": "system_prompt=TOP SECRET"}),
    ("aggregate_id_credential", {"aggregate_id": "sk-abcdefghijklmnop"}),
)


@pytest.mark.parametrize(
    ("label", "facts"),
    AT_DP_122_UNSAFE_HEADER_FACTS,
    ids=[case[0] for case in AT_DP_122_UNSAFE_HEADER_FACTS],
)
def test_at_dp_122_unsafe_header_facts_fail_before_persistence(
    connected, label, facts
) -> None:
    """MAJOR-V2-001: no persisted event channel can carry forbidden content."""

    system = connected["system"]
    received: list[AgentRuntimeEvent] = []
    system.subscribe(received.append, ["message.received"])
    before = system.repository.count()
    stats_before = system.bus.stats.published_total

    with pytest.raises((ValueError, PlatformEventPayloadError)):
        system.publish(
            "message.received",
            {"request_id": "req-v2-header", "channel": "conversation"},
            **facts,
        )

    assert system.repository.count() == before, label
    assert system.bus.stats.published_total == stats_before, label
    assert received == [], label
    assert system.dead_letter_count() == 0, label


def test_at_dp_122_legitimate_header_facts_still_persist(connected) -> None:
    """MAJOR-V2-001 control: real identifiers and bounded metadata stay valid."""

    system = connected["system"]
    before = system.repository.count()

    result = system.publish(
        "message.received",
        {"request_id": "req-v2-safe-header", "channel": "conversation"},
        event_id="evt-v2-safe-header",
        producer="orchestration",
        aggregate_id="workflow:123",
        source="domain.execution.completed",
        permissions=["events:read"],
        metadata={"status_code": "ok", "attempt": 1},
    )

    assert result.persisted is True
    stored = system.repository.get("evt-v2-safe-header")
    assert stored is not None
    assert stored.header.producer == "orchestration"
    assert stored.header.aggregate_id == "workflow:123"
    assert stored.header.source == "domain.execution.completed"
    assert stored.header.permissions == ["events:read"]
    assert stored.header.metadata == {"status_code": "ok", "attempt": 1}
    assert system.repository.count() == before + 1


def test_at_dp_122_unsupported_schema_is_rejected_before_durable_append(
    connected,
) -> None:
    """MAJOR-V2-002: the durable store is never poisoned by this build."""

    system = connected["system"]
    store_path = Path(system.repository.path)
    received: list[AgentRuntimeEvent] = []
    system.subscribe(received.append, ["message.received"])
    before_bytes = store_path.read_bytes() if store_path.exists() else b""

    with pytest.raises((ValueError, AgentRuntimeEventSerializationError)):
        system.publish(
            "message.received",
            {"request_id": "req-v2-schema", "channel": "conversation"},
            event_id="evt-v2-unsupported-schema",
            schema_version="9.9.9",
        )

    assert received == []
    assert system.repository.get("evt-v2-unsupported-schema") is None
    assert (store_path.read_bytes() if store_path.exists() else b"") == before_bytes
    # The store is still openable by this build.
    reopened = FileAgentRuntimeEventRepository(store_path)
    assert reopened.count() == system.repository.count()


def test_at_dp_122_supported_schema_survives_close_and_reopen(connected) -> None:
    """MAJOR-V2-002: a supported-schema write is genuinely reopenable."""

    system = connected["system"]
    store_path = Path(system.repository.path)

    system.publish(
        "message.received",
        {"request_id": "req-v2-roundtrip", "channel": "conversation"},
        event_id="evt-v2-supported-roundtrip",
        metadata={"status_code": "ok"},
    )

    reopened = FileAgentRuntimeEventRepository(store_path)
    restored = reopened.get("evt-v2-supported-roundtrip")

    assert restored is not None
    assert restored.header.schema_version == "1.0.0"
    assert restored.payload.data == {
        "request_id": "req-v2-roundtrip",
        "channel": "conversation",
    }
    assert event_fingerprint(restored) == event_fingerprint(
        system.repository.get("evt-v2-supported-roundtrip")
    )


def _at_dp_122_mutating_subscriber(seen_by_later: list) -> object:
    def tamper(event: AgentRuntimeEvent) -> None:
        event.payload.data["request_id"] = "tampered-by-A"
        event.header.metadata["tampered"] = "yes"
        event.header.permissions.append("escalate")
        seen_by_later.append(dict(event.payload.data))

    return tamper


def test_at_dp_122_subscriber_a_cannot_change_what_subscriber_b_sees(
    connected,
) -> None:
    """MAJOR-V2-003: later subscribers observe the original canonical facts."""

    system = connected["system"]
    seen_by_b: list[tuple] = []

    system.subscribe(_at_dp_122_mutating_subscriber([]), ["message.received"])
    system.subscribe(
        lambda event: seen_by_b.append(
            (
                dict(event.payload.data),
                dict(event.header.metadata),
                list(event.header.permissions),
            )
        ),
        ["message.received"],
        priority=1,
    )

    system.publish(
        "message.received",
        {"request_id": "req-v2-isolation", "channel": "conversation"},
        event_id="evt-v2-isolation",
        metadata={"origin": "original"},
        permissions=["events:read"],
    )

    assert seen_by_b == [
        (
            {"request_id": "req-v2-isolation", "channel": "conversation"},
            {"origin": "original"},
            ["events:read"],
        )
    ]


def test_at_dp_122_subscriber_cannot_mutate_repository_evidence(connected) -> None:
    """MAJOR-V2-003: delivered mutation attempts never change stored evidence."""

    system = connected["system"]
    system.subscribe(_at_dp_122_mutating_subscriber([]), ["message.received"])

    result = system.publish(
        "message.received",
        {"request_id": "req-v2-evidence", "channel": "conversation"},
        event_id="evt-v2-evidence",
        metadata={"origin": "original"},
        permissions=["events:read"],
    )

    stored = system.repository.get("evt-v2-evidence")
    assert stored is not None
    assert stored.payload.data == {
        "request_id": "req-v2-evidence",
        "channel": "conversation",
    }
    assert stored.header.metadata == {"origin": "original"}
    assert stored.header.permissions == ["events:read"]
    assert result.event.payload.data["request_id"] == "req-v2-evidence"


def test_at_dp_122_file_live_and_reopened_facts_match_after_mutation_attempt(
    connected,
) -> None:
    """MAJOR-V2-003: live evidence cannot diverge from already-fsynced bytes."""

    system = connected["system"]
    store_path = Path(system.repository.path)
    system.subscribe(_at_dp_122_mutating_subscriber([]), ["message.received"])

    system.publish(
        "message.received",
        {"request_id": "req-v2-file-consistency", "channel": "conversation"},
        event_id="evt-v2-file-consistency",
        metadata={"origin": "original"},
        permissions=["events:read"],
    )

    live = system.repository.get("evt-v2-file-consistency")
    reopened = FileAgentRuntimeEventRepository(store_path).get(
        "evt-v2-file-consistency"
    )

    assert live is not None and reopened is not None
    assert event_fingerprint(live) == event_fingerprint(reopened)
    assert reopened.payload.data == {
        "request_id": "req-v2-file-consistency",
        "channel": "conversation",
    }
    assert reopened.header.metadata == {"origin": "original"}
    assert reopened.header.permissions == ["events:read"]


def _at_dp_122_domain_bridge(connected):
    """Real Domain Event → Kernel Event → Platform adapter over the composition."""

    from cmm.domains.event_factory import DomainEventFactory
    from cmm.domains.event_publisher import DomainKernelEventPublisher
    from cmm.events.kernel_adapter import PlatformKernelEventAdapter

    adapter = PlatformKernelEventAdapter(connected["system"])
    publisher = DomainKernelEventPublisher(event_listener=adapter)
    return DomainEventFactory(), publisher, adapter


def test_at_dp_122_real_domain_execution_preserves_mapped_facts_and_sensitivity(
    connected,
) -> None:
    """MAJOR-V2-004: real Domain execution identity, status and classification."""

    factory, publisher, _adapter = _at_dp_122_domain_bridge(connected)
    publisher.publish(
        factory.create_event(
            event_type="domain.execution.completed",
            domain_id="domain:general",
            actor="system",
            event_id="DOM-V2-EXEC",
            occurred_at=OCCURRED,
            sensitivity="restricted",
            correlation_id="CORR-ORIGINAL",
            causation_id="CAUSE-ORIGINAL",
            payload={"execution_id": "EXEC-V2", "status": "completed"},
        )
    )

    stored = connected["system"].repository.query(event_type="operation.executed")[0]

    assert stored.payload.data["execution_id"] == "EXEC-V2"
    assert stored.payload.data["status"] == "completed"
    assert stored.header.sensitivity is EventSensitivity.RESTRICTED
    # Audit V1 MAJOR-004 stays green on the same connected path.
    assert stored.header.correlation_id == "CORR-ORIGINAL"
    assert stored.header.causation_id == "CAUSE-ORIGINAL"


@pytest.mark.parametrize(
    ("source_sensitivity", "expected"),
    (
        ("public", EventSensitivity.PUBLIC),
        ("internal", EventSensitivity.INTERNAL),
        ("confidential", EventSensitivity.CONFIDENTIAL),
        ("restricted", EventSensitivity.RESTRICTED),
    ),
)
def test_at_dp_122_domain_sensitivity_is_not_downgraded(
    connected, source_sensitivity, expected
) -> None:
    """MAJOR-V2-004: SOURCE_SENSITIVITY_IS_NOT_DOWNGRADED on the real chain."""

    factory, publisher, _adapter = _at_dp_122_domain_bridge(connected)
    publisher.publish(
        factory.create_event(
            event_type="domain.execution.completed",
            domain_id="domain:general",
            actor="system",
            event_id=f"DOM-V2-SENS-{source_sensitivity}",
            occurred_at=OCCURRED,
            sensitivity=source_sensitivity,
            payload={"execution_id": "EXEC-SENS", "status": "completed"},
        )
    )

    stored = connected["system"].repository.query(event_type="operation.executed")[0]

    assert stored.header.sensitivity is expected


def test_at_dp_122_real_domain_approval_and_memory_preserve_mapped_facts(
    connected,
) -> None:
    """MAJOR-V2-004: approval identity/resolution and memory status are preserved."""

    factory, publisher, _adapter = _at_dp_122_domain_bridge(connected)
    system = connected["system"]

    publisher.publish(
        factory.create_event(
            event_type="domain.approval.requested",
            domain_id="domain:general",
            actor="system",
            event_id="DOM-V2-APP-REQ",
            occurred_at=OCCURRED,
            payload={"approval_id": "APP-V2-1", "action": "delete"},
        )
    )
    publisher.publish(
        factory.create_event(
            event_type="domain.approval.received",
            domain_id="domain:general",
            actor="system",
            event_id="DOM-V2-APP-REC",
            occurred_at=OCCURRED,
            payload={
                "approval_id": "APP-V2-2",
                "approved": True,
                "decision_by": "u1",
            },
        )
    )
    publisher.publish(
        factory.create_event(
            event_type="domain.memory.updated",
            domain_id="domain:general",
            actor="system",
            event_id="DOM-V2-MEM",
            occurred_at=OCCURRED,
            payload={"update_id": "UPD-V2", "status": "updated"},
        )
    )

    requested = system.repository.query(event_type="approval.requested")[0]
    resolved = system.repository.query(event_type="approval.resolved")[0]
    memory = system.repository.query(event_type="memory.updated")[0]

    assert requested.payload.data["approval_id"] == "APP-V2-1"
    # No invented approval status: the real source carries none.
    assert "status" not in requested.payload.data

    assert resolved.payload.data["approval_id"] == "APP-V2-2"
    assert resolved.payload.data["approved"] is True
    assert "decision_by" not in resolved.payload.data

    assert memory.payload.data["status"] == "updated"
    assert memory.payload.data["domain_id"] == "domain:general"


def test_at_dp_122_nested_forbidden_domain_content_still_fails_closed(
    connected,
) -> None:
    """MAJOR-V2-004: reading mapped nested facts must not weaken nested scanning."""

    from kernel.events.event import Event as KernelEvent

    _factory, _publisher, adapter = _at_dp_122_domain_bridge(connected)
    system = connected["system"]
    before = system.repository.count()

    for unsafe in (
        {"prompt": "leaked prompt"},
        {"chain_of_thought": "step 1"},
        {"provider_response": {"raw": "body"}},
        {"api_key": "api_key=abcdef1234567890"},
    ):
        with pytest.raises(PlatformEventPayloadError):
            adapter.handle(
                KernelEvent(
                    name="domain.execution.completed",
                    payload={
                        "domain_id": "domain:general",
                        "event_type": "domain.execution.completed",
                        "payload": unsafe,
                    },
                )
            )
        assert system.repository.count() == before, unsafe


# ══════════════════════════════════════════════════════════════════════════
# Remediation V3 — AT-DP-122 additions for the two V3 majors and one V3 minor
#
# The real composed event system is used throughout: the file-backed canonical
# repository, the canonical registry/bus/DLQ and the real production
# ``PlatformOrchestrationEventSink``.  No component is replaced by a mock.
# ══════════════════════════════════════════════════════════════════════════


class _AtDp122SecretObject:
    """Opaque metadata object whose string form is a credential."""

    def __str__(self) -> str:
        return "api_key=abcdef1234567890"

    def __repr__(self) -> str:
        return "<AtDp122SecretObject>"


#: Persisted metadata facts that are not JSON-safe descriptive values.
AT_DP_122_UNSAFE_METADATA_FACTS = (
    ("opaque_object", object()),
    ("bytes", b"abc"),
    ("bytearray", bytearray(b"abc")),
    ("nan", float("nan")),
    ("positive_infinity", float("inf")),
    ("secret_object", _AtDp122SecretObject()),
)


@pytest.mark.parametrize(
    ("label", "value"),
    AT_DP_122_UNSAFE_METADATA_FACTS,
    ids=[case[0] for case in AT_DP_122_UNSAFE_METADATA_FACTS],
)
def test_at_dp_122_unsafe_metadata_value_fails_before_persistence(
    connected, label, value
) -> None:
    """MAJOR-V3-001: no persisted metadata channel accepts an unsafe value type."""

    system = connected["system"]
    store: Path = connected["store"]
    received: list[AgentRuntimeEvent] = []
    system.subscribe(received.append, ["message.received"])
    before = system.repository.count()
    before_bytes = store.read_bytes() if store.exists() else b""

    with pytest.raises((PlatformEventPayloadError, TypeError, ValueError)):
        system.publish(
            "message.received",
            {"request_id": "req-v3-metadata", "channel": "conversation"},
            event_id=f"evt-v3-metadata-{label}".replace("_", "-"),
            metadata={"value": value},
        )

    assert system.repository.count() == before, label
    assert received == [], label
    assert system.dead_letter_count() == 0, label
    assert (store.read_bytes() if store.exists() else b"") == before_bytes, label


def test_at_dp_122_secret_object_credential_never_reaches_the_durable_store(
    connected,
) -> None:
    """MAJOR-V3-001: the mandatory SecretObject credential-stringification case."""

    system = connected["system"]
    store: Path = connected["store"]
    received: list[AgentRuntimeEvent] = []
    system.subscribe(received.append, ["message.received"])
    before = system.repository.count()
    before_bytes = store.read_bytes() if store.exists() else b""

    with pytest.raises((PlatformEventPayloadError, TypeError, ValueError)):
        system.publish(
            "message.received",
            {"request_id": "req-v3-opaque", "channel": "conversation"},
            event_id="evt-v3-opaque",
            metadata={"inner": _AtDp122SecretObject()},
        )

    durable = store.read_bytes() if store.exists() else b""
    assert b"api_key=abcdef1234567890" not in durable
    assert durable == before_bytes
    assert system.repository.count() == before
    assert received == []


#: Sensitivities that are not the one canonical runtime classification.
AT_DP_122_INVALID_SENSITIVITY = (
    ("integer", 123),
    ("none", None),
    ("credential_string", "api_key=abcdef1234567890"),
    ("private_marker", "system_prompt=TOP SECRET"),
    ("unknown_label", "definitely-not-a-sensitivity"),
)


@pytest.mark.parametrize(
    ("label", "value"),
    AT_DP_122_INVALID_SENSITIVITY,
    ids=[case[0] for case in AT_DP_122_INVALID_SENSITIVITY],
)
def test_at_dp_122_invalid_sensitivity_fails_before_persistence(
    connected, label, value
) -> None:
    """MAJOR-V3-001: the persisted classification is a runtime-enforced enum."""

    system = connected["system"]
    received: list[AgentRuntimeEvent] = []
    system.subscribe(received.append, ["message.received"])
    before = system.repository.count()

    with pytest.raises((PlatformEventPayloadError, TypeError, ValueError)):
        system.publish(
            "message.received",
            {"request_id": "req-v3-sensitivity", "channel": "conversation"},
            event_id=f"evt-v3-sensitivity-{label}".replace("_", "-"),
            sensitivity=value,
        )

    assert system.repository.count() == before, label
    assert received == [], label


def test_at_dp_122_supported_sensitivity_string_is_canonically_normalized(
    connected,
) -> None:
    """MAJOR-V3-001: the one supported string form becomes the canonical enum."""

    system = connected["system"]

    result = system.publish(
        "message.received",
        {"request_id": "req-v3-sensitivity-ok", "channel": "conversation"},
        event_id="evt-v3-sensitivity-ok",
        sensitivity="restricted",
    )

    assert result.event.header.sensitivity is EventSensitivity.RESTRICTED
    stored = system.repository.get("evt-v3-sensitivity-ok")
    assert stored is not None
    assert stored.header.sensitivity is EventSensitivity.RESTRICTED


def test_at_dp_122_permissions_string_is_rejected_not_coerced(connected) -> None:
    """MAJOR-V3-001: a plain string must not become a character list."""

    system = connected["system"]
    before = system.repository.count()

    with pytest.raises((PlatformEventPayloadError, TypeError, ValueError)):
        system.publish(
            "message.received",
            {"request_id": "req-v3-permissions", "channel": "conversation"},
            event_id="evt-v3-permissions",
            permissions="admin",
        )

    assert system.repository.count() == before
    assert system.repository.get("evt-v3-permissions") is None


def test_at_dp_122_nested_result_reference_publishes_and_round_trips(
    connected,
) -> None:
    """MAJOR-V3-002: a safe nested mapping publishes and reopens unchanged."""

    system = connected["system"]
    store: Path = connected["store"]

    result = system.publish(
        "message.received",
        {
            "request_id": "req-v3-result-reference",
            "channel": "conversation",
            "result_reference": {"reference_id": "ref-1"},
            "approval_refs": [{"approval_id": "app-1"}],
        },
        event_id="evt-v3-result-reference",
    )

    assert result.persisted is True
    live = result.event
    reopened = FileAgentRuntimeEventRepository(store).get("evt-v3-result-reference")

    assert reopened is not None
    assert live == reopened
    assert event_fingerprint(live) == event_fingerprint(reopened)
    assert type(live.payload.data["result_reference"]) is dict
    assert type(live.payload.data["approval_refs"]) is list
    assert type(live.payload.data["approval_refs"][0]) is dict


def test_at_dp_122_supporting_domains_shape_is_stable_across_reopen(
    connected,
) -> None:
    """MAJOR-V3-002: one canonical sequence shape live, persisted and reopened."""

    system = connected["system"]
    store: Path = connected["store"]

    result = system.publish(
        "message.received",
        {
            "request_id": "req-v3-sequence",
            "channel": "conversation",
            "supporting_domains": ["domain:legal", "domain:health"],
        },
        event_id="evt-v3-sequence",
    )

    reopened = FileAgentRuntimeEventRepository(store).get("evt-v3-sequence")

    assert reopened is not None
    assert type(result.event.payload.data["supporting_domains"]) is list
    assert type(reopened.payload.data["supporting_domains"]) is list
    assert result.event.payload.data == reopened.payload.data
    assert result.event == reopened


def test_at_dp_122_real_orchestration_sink_round_trip_is_equal(connected) -> None:
    """MAJOR-V3-002: the real production sink satisfies the round-trip invariant."""

    system = connected["system"]
    store: Path = connected["store"]
    sink = PlatformOrchestrationEventSink(system)

    event_id = sink.emit(
        "orchestration.domain_resolved",
        request_id="req-v3-orchestration",
        payload={
            "primary_domain": "domain:legal",
            "supporting_domains": ["domain:legal", "domain:health"],
            "status": "resolved",
        },
    )

    assert event_id is not None
    live = system.repository.get(event_id)
    reopened = FileAgentRuntimeEventRepository(store).get(event_id)

    assert live is not None
    assert reopened is not None
    assert type(live.payload.data["supporting_domains"]) is list
    assert type(reopened.payload.data["supporting_domains"]) is list
    assert live.payload.data["supporting_domains"] == [
        "domain:legal",
        "domain:health",
    ]
    assert live == reopened
    assert event_fingerprint(live) == event_fingerprint(reopened)


def test_at_dp_122_nested_caller_alias_cannot_mutate_the_publication_result(
    connected,
) -> None:
    """MAJOR-V3-002: a nested caller alias must not survive into the result."""

    from cmm.agent_runtime.runtime_event_contracts import (
        AgentRuntimeEventHeader,
        AgentRuntimeEventPayload,
    )

    system = connected["system"]
    caller_list = ["domain:a"]
    caller_nested = {"reference_id": "ref-1"}

    manual = AgentRuntimeEvent(
        header=AgentRuntimeEventHeader(
            event_id="evt-v3-alias",
            event_type="message.received",
            occurred_at=OCCURRED,
            emitted_at=OCCURRED,
        ),
        payload=AgentRuntimeEventPayload(
            data={
                "request_id": "req-v3-alias",
                "supporting_domains": caller_list,
                "result_reference": caller_nested,
            }
        ),
    )

    result = system.publish_event(manual)

    caller_list.append("domain:b")
    caller_nested["reference_id"] = "mutated"

    stored = system.repository.get("evt-v3-alias")
    assert result.event.payload.data["supporting_domains"] == ["domain:a"]
    assert result.event.payload.data["result_reference"] == {"reference_id": "ref-1"}
    assert stored is not None
    assert stored.payload.data["supporting_domains"] == ["domain:a"]
    assert event_fingerprint(stored) == event_fingerprint(result.event)


def test_at_dp_122_dead_letter_inspection_snapshots_are_detached(connected) -> None:
    """MINOR-V3-001: DLQ get/list snapshots cannot mutate retained evidence."""

    system = connected["system"]

    def failing(event: AgentRuntimeEvent) -> None:
        raise RuntimeError("subscriber failed")

    system.subscribe(failing, ["message.received"], priority=5)

    system.publish(
        "message.received",
        {
            "request_id": "req-v3-dlq",
            "channel": "conversation",
            "supporting_domains": ["domain:a"],
        },
        event_id="evt-v3-dlq",
        metadata={"origin": "original"},
    )

    assert system.dead_letter_count() == 1
    subscription_id = system.list_dead_letters()[0].subscription_id
    attempts_before = system.list_dead_letters()[0].attempts

    tampered = system.list_dead_letters()[0]
    tampered.event.payload.data["supporting_domains"].append("domain:tampered")
    tampered.event.header.metadata["injected"] = "yes"
    tampered.metadata["injected"] = "yes"

    for entry in (
        system.list_dead_letters()[0],
        system.dead_letters.get(0),
        system.dead_letters.list()[0],
    ):
        assert entry.event.payload.data["supporting_domains"] == ["domain:a"]
        assert entry.event.header.metadata == {"origin": "original"}
        assert "injected" not in entry.metadata
        assert entry.subscription_id == subscription_id
        assert entry.attempts == attempts_before

    assert system.dead_letter_count() == 1


# ══════════════════════════════════════════════════════════════════════════
# Remediation V4 — AT-DP-122 additions for the three V4 majors
#
# The real composed event system is used throughout: the file-backed canonical
# repository, the canonical registry/bus/DLQ and the real production
# ``PlatformOrchestrationEventSink``.  No component is replaced by a mock.
# ══════════════════════════════════════════════════════════════════════════

#: The exact binary buffer the independent Re-audit V4 published.
AT_DP_122_BINARY_BUFFER = memoryview(b"secret-binary")

#: The integer array the pre-remediation bypass produced for that buffer.
AT_DP_122_BINARY_AS_INTEGERS = list(AT_DP_122_BINARY_BUFFER.tobytes())

#: The exact credential text Re-audit V4 used as a dynamic exception class name.
AT_DP_122_CREDENTIAL_CLASS_NAME = "api_key=abcdef1234567890"

#: The exact private marker Re-audit V4 used as a dynamic exception class name.
AT_DP_122_PRIVATE_MARKER_CLASS_NAME = "system_prompt=TOP SECRET"


def _at_dp_122_manual_event(
    *, event_id: str, payload: dict, **header_facts
) -> AgentRuntimeEvent:
    """Build a canonical event object directly, as a manual publisher would."""

    from cmm.agent_runtime.runtime_event_contracts import (
        AgentRuntimeEventHeader,
        AgentRuntimeEventPayload,
    )

    header = AgentRuntimeEventHeader(
        event_id=event_id,
        event_type="message.received",
        occurred_at=OCCURRED,
        emitted_at=OCCURRED,
        **header_facts,
    )
    return AgentRuntimeEvent(
        header=header, payload=AgentRuntimeEventPayload(data=payload)
    )


@pytest.mark.parametrize(
    "binary",
    [
        pytest.param(memoryview(b"secret-binary"), id="memoryview"),
        pytest.param(b"secret-binary", id="bytes_control"),
        pytest.param(bytearray(b"secret-binary"), id="bytearray_control"),
    ],
)
def test_at_dp_122_payload_binary_is_rejected_before_persistence(
    connected, binary
) -> None:
    """MAJOR-V4-001: every binary container form fails closed in ``payload.data``."""

    system = connected["system"]
    store: Path = connected["store"]
    received: list[AgentRuntimeEvent] = []
    system.subscribe(received.append, ["message.received"])
    before = system.repository.count()
    before_bytes = store.read_bytes() if store.exists() else b""

    with pytest.raises((PlatformEventPayloadError, TypeError, ValueError)):
        system.publish(
            "message.received",
            {
                "request_id": "req-v4-binary",
                "channel": "conversation",
                "supporting_domains": binary,
            },
            event_id="evt-v4-binary",
        )

    durable = store.read_bytes() if store.exists() else b""
    assert durable == before_bytes
    assert b"115, 101, 99, 114, 101, 116" not in durable
    assert system.repository.count() == before
    assert received == []
    assert system.dead_letter_count() == 0


def test_at_dp_122_nested_payload_memoryview_is_rejected(connected) -> None:
    """MAJOR-V4-001: a nested ``memoryview`` in a mapping is still binary."""

    system = connected["system"]
    received: list[AgentRuntimeEvent] = []
    system.subscribe(received.append, ["message.received"])
    before = system.repository.count()

    with pytest.raises((PlatformEventPayloadError, TypeError, ValueError)):
        system.publish(
            "message.received",
            {
                "request_id": "req-v4-nested-binary",
                "channel": "conversation",
                "result_reference": {"sequence": [AT_DP_122_BINARY_BUFFER]},
            },
            event_id="evt-v4-nested-binary",
        )

    assert system.repository.count() == before
    assert received == []


def test_at_dp_122_metadata_memoryview_is_rejected(connected) -> None:
    """MAJOR-V4-001: persisted ``metadata`` classifies ``memoryview`` as binary."""

    system = connected["system"]
    store: Path = connected["store"]
    before = system.repository.count()
    before_bytes = store.read_bytes() if store.exists() else b""

    manual = _at_dp_122_manual_event(
        event_id="evt-v4-meta-binary",
        payload={"request_id": "req-v4-meta-binary", "channel": "conversation"},
        metadata={"value": AT_DP_122_BINARY_BUFFER},
    )

    with pytest.raises((PlatformEventPayloadError, TypeError, ValueError)):
        system.publish_event(manual)

    assert system.repository.count() == before
    assert (store.read_bytes() if store.exists() else b"") == before_bytes


def test_at_dp_122_manual_event_memoryview_never_becomes_integers(connected) -> None:
    """MAJOR-V4-001: the audited bypass must not emit an integer array."""

    system = connected["system"]
    manual = _at_dp_122_manual_event(
        event_id="evt-v4-meta-shape",
        payload={"request_id": "req-v4-meta-shape", "channel": "conversation"},
        metadata={"outer": {"inner": [AT_DP_122_BINARY_BUFFER]}},
    )

    try:
        result = system.publish_event(manual)
    except (PlatformEventPayloadError, TypeError, ValueError):
        assert system.repository.get("evt-v4-meta-shape") is None
        return

    accepted = list(
        dict(result.event.header.metadata).get("outer", {}).get("inner", [])
    )
    assert accepted != AT_DP_122_BINARY_AS_INTEGERS, (
        "memoryview binary was transformed into an integer array and accepted"
    )


def test_at_dp_122_manual_sensitivity_string_matches_file_repository(connected) -> None:
    """MAJOR-V4-002: the manual boundary produces one canonical representation.

    This is the exact independent Re-audit V4 divergence: against the composition's
    real file-backed repository the same call used to raise
    ``AttributeError: 'str' object has no attribute 'value'``.
    """

    system = connected["system"]

    result = system.publish_event(
        _at_dp_122_manual_event(
            event_id="evt-v4-sensitivity",
            payload={"request_id": "req-v4-sensitivity", "channel": "conversation"},
            sensitivity="restricted",
        )
    )

    assert result.event.header.sensitivity is EventSensitivity.RESTRICTED
    stored = system.repository.get("evt-v4-sensitivity")
    assert stored is not None
    assert stored.header.sensitivity is EventSensitivity.RESTRICTED


def test_at_dp_122_manual_sensitivity_is_repository_independent(tmp_path) -> None:
    """MAJOR-V4-002: in-memory and file-backed repositories agree exactly."""

    from cmm.agent_runtime.runtime_event_repository import (
        InMemoryAgentRuntimeEventRepository,
    )

    store = tmp_path / "data" / "events" / "runtime_events.jsonl"
    file_system = EventSystem(
        registry=AgentRuntimeEventRegistry(strict_mode=True),
        repository=FileAgentRuntimeEventRepository(store),
        bus=AgentRuntimeEventBus(max_delivery_attempts=1),
    )
    memory_system = EventSystem(
        registry=AgentRuntimeEventRegistry(strict_mode=True),
        repository=InMemoryAgentRuntimeEventRepository(),
        bus=AgentRuntimeEventBus(max_delivery_attempts=1),
    )

    def manual() -> AgentRuntimeEvent:
        return _at_dp_122_manual_event(
            event_id="evt-v4-parity",
            payload={"request_id": "req-v4-parity", "channel": "conversation"},
            sensitivity="restricted",
        )

    file_result = file_system.publish_event(manual())
    memory_result = memory_system.publish_event(manual())

    assert (
        file_result.event.header.sensitivity
        is memory_result.event.header.sensitivity
        is EventSensitivity.RESTRICTED
    )
    assert file_result.outcome == memory_result.outcome
    assert event_fingerprint(file_result.event) == event_fingerprint(
        memory_result.event
    )


def test_at_dp_122_manual_sensitivity_enum_control(connected) -> None:
    """MAJOR-V4-002 control: the already-canonical enum is unchanged."""

    system = connected["system"]

    result = system.publish_event(
        _at_dp_122_manual_event(
            event_id="evt-v4-sensitivity-enum",
            payload={
                "request_id": "req-v4-sensitivity-enum",
                "channel": "conversation",
            },
            sensitivity=EventSensitivity.RESTRICTED,
        )
    )

    assert result.event.header.sensitivity is EventSensitivity.RESTRICTED
    stored = system.repository.get("evt-v4-sensitivity-enum")
    assert stored is not None
    assert stored.header.sensitivity is EventSensitivity.RESTRICTED


def _at_dp_122_dead_letter_with_exception(
    connected, exception_class: type[BaseException]
) -> str:
    """Raise *exception_class* from a subscriber and render every DLQ field."""

    import json

    system = connected["system"]

    def failing(event: AgentRuntimeEvent) -> None:
        raise exception_class("subscriber exploded")

    system.subscribe(failing, ["message.received"])
    system.publish(
        "message.received",
        {"request_id": "req-v4-dlq", "channel": "conversation"},
        event_id="evt-v4-dlq",
        occurred_at=OCCURRED,
        emitted_at=OCCURRED,
    )

    entries = system.list_dead_letters()
    assert entries, "expected a canonical dead letter to be recorded"
    return json.dumps(
        [
            {
                "error": entry.error,
                "error_type": entry.error_type,
                "handler_name": entry.handler_name,
                "subscription_id": entry.subscription_id,
                "metadata": dict(entry.metadata),
            }
            for entry in entries
        ]
    )


def test_at_dp_122_credential_exception_class_name_never_reaches_dlq(
    connected,
) -> None:
    """MAJOR-V4-003: the exact audited credential leak must be closed."""

    credential_exception = type(AT_DP_122_CREDENTIAL_CLASS_NAME, (Exception,), {})

    rendered = _at_dp_122_dead_letter_with_exception(connected, credential_exception)

    assert "abcdef1234567890" not in rendered
    assert "api_key" not in rendered
    assert AT_DP_122_CREDENTIAL_CLASS_NAME not in rendered


def test_at_dp_122_private_marker_exception_class_name_never_reaches_dlq(
    connected,
) -> None:
    """MAJOR-V4-003: a private-marker class name is refused as well."""

    private_exception = type(AT_DP_122_PRIVATE_MARKER_CLASS_NAME, (Exception,), {})

    rendered = _at_dp_122_dead_letter_with_exception(connected, private_exception)

    assert "TOP SECRET" not in rendered
    assert "system_prompt" not in rendered


def test_at_dp_122_ordinary_exception_class_name_stays_useful(connected) -> None:
    """MAJOR-V4-003 control: an ordinary exception keeps a useful category."""

    rendered = _at_dp_122_dead_letter_with_exception(connected, RuntimeError)

    assert '"error_type": "RuntimeError"' in rendered
    assert "subscriber exploded" not in rendered
    assert "Traceback" not in rendered


# ══════════════════════════════════════════════════════════════════════════
# Remediation V5 — AT-DP-122 additions for the three V5 majors
#
# The real composed event system is used throughout: the file-backed canonical
# repository, the canonical registry/bus/DLQ and the real production
# ``PlatformOrchestrationEventSink``.  No component is replaced by a mock.
# ══════════════════════════════════════════════════════════════════════════

#: The exact ``array.array`` binary buffer the independent Re-audit V5 published.
AT_DP_122_ARRAY_BUFFER = array.array("B", b"secret-binary")

#: The integer list the pre-remediation bypass produced for that buffer.
AT_DP_122_ARRAY_AS_INTEGERS = list(b"secret-binary")

#: The exact raw user sentence the independent Re-audit V5 persisted under an
#: allowed key and under ordinary metadata.
AT_DP_122_RAW_USER_TEXT = (
    "My landlord entered my flat without permission yesterday and I need legal advice."
)

#: The exact credential-shaped dynamic exception class name Re-audit V5 used
#: against the direct canonical bus.
AT_DP_122_CREDENTIAL_IDENTIFIER_NAME = "api_key_abcdef1234567890"

#: A valid-identifier, private-marker-bearing dynamic exception class name.
AT_DP_122_PRIVATE_MARKER_IDENTIFIER_NAME = "system_prompt_TOP_SECRET"

#: The neutral bounded DLQ category the canonical transport falls back to when no
#: external error categorizer is bound.
AT_DP_122_NEUTRAL_ERROR_CATEGORY = "SubscriberDeliveryError"


def _at_dp_122_array_buffer() -> array.array:
    """Return a fresh ``array.array`` buffer for one scenario."""

    return array.array("B", b"secret-binary")


@pytest.mark.parametrize(
    "binary",
    [
        pytest.param(array.array("B", b"secret-binary"), id="array_b"),
        pytest.param(array.array("i", [1, 2, 3]), id="array_i"),
        pytest.param(array.array("d", [1.5, 2.5]), id="array_d"),
    ],
)
def test_at_dp_122_array_buffer_payload_is_rejected_before_persistence(
    connected, binary
) -> None:
    """MAJOR-V5-001: every ``array.array`` typecode fails closed in ``payload.data``."""

    system = connected["system"]
    store: Path = connected["store"]
    received: list[AgentRuntimeEvent] = []
    system.subscribe(received.append, ["message.received"])
    before = system.repository.count()

    with pytest.raises((PlatformEventPayloadError, TypeError, ValueError)):
        system.publish(
            "message.received",
            {
                "request_id": "req-v5-array",
                "channel": "conversation",
                "supporting_domains": binary,
            },
            event_id="evt-v5-array",
        )

    assert system.repository.count() == before
    assert system.repository.get("evt-v5-array") is None
    assert received == []
    assert system.dead_letter_count() == 0
    durable = store.read_bytes() if store.exists() else b""
    assert AT_DP_122_ARRAY_AS_INTEGERS[0:4] != [] and durable == b""


def test_at_dp_122_array_buffer_never_becomes_a_durable_integer_array(
    connected,
) -> None:
    """MAJOR-V5-001: the bypass integer array never reaches durable content."""

    system = connected["system"]
    before = system.repository.count()

    accepted: object = None
    try:
        accepted = system.publish(
            "message.received",
            {"request_id": "req-v5-array-int", "sequence": _at_dp_122_array_buffer()},
            event_id="evt-v5-array-int",
        ).event.payload.data.get("sequence")
    except (PlatformEventPayloadError, TypeError, ValueError):
        accepted = None

    assert accepted != AT_DP_122_ARRAY_AS_INTEGERS
    assert system.repository.count() == before
    assert system.repository.get("evt-v5-array-int") is None


def test_at_dp_122_nested_array_buffer_in_payload_is_rejected(connected) -> None:
    """MAJOR-V5-001: an ``array.array`` nested in a reference fails closed."""

    system = connected["system"]
    before = system.repository.count()

    with pytest.raises((PlatformEventPayloadError, TypeError, ValueError)):
        system.publish(
            "message.received",
            {
                "request_id": "req-v5-array-nested",
                "result_reference": {"sequence": _at_dp_122_array_buffer()},
            },
            event_id="evt-v5-array-nested",
        )

    assert system.repository.count() == before
    assert system.repository.get("evt-v5-array-nested") is None


def test_at_dp_122_array_buffer_in_metadata_is_rejected(connected) -> None:
    """MAJOR-V5-001: an ``array.array`` in ``metadata`` fails closed."""

    system = connected["system"]
    before = system.repository.count()

    with pytest.raises((PlatformEventPayloadError, TypeError, ValueError)):
        system.publish(
            "message.received",
            {"request_id": "req-v5-array-meta", "channel": "conversation"},
            event_id="evt-v5-array-meta",
            metadata={"detail": {"inner": [_at_dp_122_array_buffer()]}},
        )

    assert system.repository.count() == before
    assert system.repository.get("evt-v5-array-meta") is None


def test_at_dp_122_manual_array_buffer_event_is_rejected(connected) -> None:
    """MAJOR-V5-001: the manual publication boundary applies the same gate."""

    system = connected["system"]
    before = system.repository.count()
    event = _at_dp_122_manual_event(
        event_id="evt-v5-array-manual",
        payload={
            "request_id": "req-v5-array-manual",
            "sequence": _at_dp_122_array_buffer(),
        },
    )

    with pytest.raises((PlatformEventPayloadError, TypeError, ValueError)):
        system.publish_event(event)

    assert system.repository.count() == before
    assert system.repository.get("evt-v5-array-manual") is None


def test_at_dp_122_raw_user_text_cannot_relocate_into_request_id(
    connected,
) -> None:
    """MAJOR-V5-002: the exact V5 identity-key reproduction fails closed."""

    system = connected["system"]
    store: Path = connected["store"]
    before = system.repository.count()

    with pytest.raises((PlatformEventPayloadError, TypeError, ValueError)):
        system.publish(
            "message.received",
            {"request_id": AT_DP_122_RAW_USER_TEXT, "channel": "conversation"},
            event_id="evt-v5-raw-id",
        )

    assert system.repository.count() == before
    durable = store.read_bytes() if store.exists() else b""
    assert b"landlord" not in durable


def test_at_dp_122_raw_user_text_cannot_relocate_into_status(connected) -> None:
    """MAJOR-V5-002: the exact V5 categorical reproduction fails closed."""

    system = connected["system"]
    store: Path = connected["store"]
    before = system.repository.count()

    with pytest.raises((PlatformEventPayloadError, TypeError, ValueError)):
        system.publish(
            "message.received",
            {"request_id": "req-v5-raw-status", "status": AT_DP_122_RAW_USER_TEXT},
            event_id="evt-v5-raw-status",
        )

    assert system.repository.count() == before
    durable = store.read_bytes() if store.exists() else b""
    assert b"landlord" not in durable


def test_at_dp_122_raw_user_text_cannot_relocate_into_metadata(connected) -> None:
    """MAJOR-V5-002: the exact V5 metadata reproduction fails closed."""

    system = connected["system"]
    store: Path = connected["store"]
    before = system.repository.count()

    with pytest.raises((PlatformEventPayloadError, TypeError, ValueError)):
        system.publish(
            "message.received",
            {"request_id": "req-v5-raw-meta", "channel": "conversation"},
            event_id="evt-v5-raw-meta",
            metadata={"origin": AT_DP_122_RAW_USER_TEXT},
        )

    assert system.repository.count() == before
    durable = store.read_bytes() if store.exists() else b""
    assert b"landlord" not in durable


def test_at_dp_122_boolean_field_rejects_prose(connected) -> None:
    """MAJOR-V5-002: a boolean lifecycle fact requires a real boolean."""

    system = connected["system"]
    before = system.repository.count()

    with pytest.raises((PlatformEventPayloadError, TypeError, ValueError)):
        system.publish(
            "message.received",
            {"request_id": "req-v5-raw-bool", "approved": AT_DP_122_RAW_USER_TEXT},
            event_id="evt-v5-raw-bool",
        )

    assert system.repository.count() == before


def test_at_dp_122_numeric_field_rejects_prose(connected) -> None:
    """MAJOR-V5-002: a numeric lifecycle fact requires a real number."""

    system = connected["system"]
    before = system.repository.count()

    with pytest.raises((PlatformEventPayloadError, TypeError, ValueError)):
        system.publish(
            "message.received",
            {"request_id": "req-v5-raw-num", "duration_ms": AT_DP_122_RAW_USER_TEXT},
            event_id="evt-v5-raw-num",
        )

    assert system.repository.count() == before


@pytest.mark.parametrize(
    ("key", "value"),
    (
        ("request_id", "req-v5-ok"),
        ("execution_id", "EXEC-1"),
        ("approval_id", "APP-1"),
        ("status", "completed"),
        ("channel", "conversation"),
        ("route", "conversation"),
        ("primary_domain", "domain:legal"),
        ("duration_ms", 125),
        ("count", 2),
        ("approved", True),
    ),
)
def test_at_dp_122_legitimate_lifecycle_facts_still_persist(
    connected, key: str, value: object
) -> None:
    """MAJOR-V5-002 control: legitimate bounded facts still reach durable storage.

    Remediation V6 removed the ``event_type`` entry from this control: a payload key
    naming a canonical header fact is that same fact, and the platform event type is
    always supplied by construction, so a conflicting payload copy now fails closed
    (see the V6 block at the end of this module for the connected acceptance of that
    rule).  Every remaining bounded fact is unchanged.
    """

    import uuid as _uuid

    system = connected["system"]
    event_id = f"evt-v5-ok-{_uuid.uuid4().hex[:8]}"

    result = system.publish(
        "message.received",
        {"request_id": "req-v5-ok", key: value},
        event_id=event_id,
    )

    assert result.persisted is True
    stored = system.repository.get(event_id)
    assert stored is not None
    assert stored.payload.data[key] == value


def test_at_dp_122_legitimate_metadata_still_persists(connected) -> None:
    """MAJOR-V5-002 control: the documented safe metadata examples still persist."""

    system = connected["system"]

    result = system.publish(
        "message.received",
        {"request_id": "req-v5-meta-ok", "channel": "conversation"},
        event_id="evt-v5-meta-ok",
        metadata={"status_code": "ok", "attempt": 1},
    )

    assert result.persisted is True
    stored = system.repository.get("evt-v5-meta-ok")
    assert stored is not None
    assert stored.header.metadata == {"status_code": "ok", "attempt": 1}


def test_at_dp_122_legitimate_origin_metadata_still_persists(connected) -> None:
    """MAJOR-V5-002 control: the second documented metadata example still persists."""

    system = connected["system"]

    result = system.publish(
        "message.received",
        {"request_id": "req-v5-origin-ok", "channel": "conversation"},
        event_id="evt-v5-origin-ok",
        metadata={"origin": "original"},
    )

    assert result.persisted is True
    stored = system.repository.get("evt-v5-origin-ok")
    assert stored is not None
    assert stored.header.metadata == {"origin": "original"}


def _at_dp_122_direct_bus_dlq_rendering(
    exception_class: type[BaseException],
) -> str:
    """Drive the canonical bus + DLQ with **no** external categorizer bound.

    This uses the canonical components directly — the real
    ``AgentRuntimeEventBus``, the real canonical in-memory dead-letter queue and
    the real canonical event factory — exactly as the independent Re-audit V5 did.
    """

    import json

    bus = AgentRuntimeEventBus(max_delivery_attempts=2)
    dlq = InMemoryAgentRuntimeDeadLetterQueue()
    bus.bind_dead_letter_queue(dlq)

    def failing(event: AgentRuntimeEvent) -> None:
        raise exception_class("subscriber exploded")

    bus.subscribe(failing, ["message.received"])
    bus.publish(
        AgentRuntimeEventFactory().create_event(
            "message.received",
            {"request_id": "req-v5-direct-dlq", "channel": "conversation"},
            event_id="evt-v5-direct-dlq",
        )
    )

    entries = dlq.list()
    assert entries, "expected a canonical dead letter to be recorded"
    return json.dumps(
        [
            {
                "error": entry.error,
                "error_type": entry.error_type,
                "handler_name": entry.handler_name,
                "subscription_id": entry.subscription_id,
                "metadata": dict(entry.metadata),
            }
            for entry in entries
        ]
    )


def test_at_dp_122_direct_canonical_bus_dlq_without_categorizer_has_no_credential() -> (
    None
):
    """MAJOR-V5-003: the direct canonical bus DLQ cannot retain a credential."""

    credential_exception = type(AT_DP_122_CREDENTIAL_IDENTIFIER_NAME, (Exception,), {})

    rendered = _at_dp_122_direct_bus_dlq_rendering(credential_exception)

    assert "api_key" not in rendered
    assert "abcdef1234567890" not in rendered
    assert AT_DP_122_CREDENTIAL_IDENTIFIER_NAME not in rendered
    assert AT_DP_122_NEUTRAL_ERROR_CATEGORY in rendered


def test_at_dp_122_direct_canonical_bus_dlq_without_categorizer_has_no_private_marker() -> (
    None
):
    """MAJOR-V5-003: no private marker survives the direct canonical bus DLQ."""

    private_exception = type(AT_DP_122_PRIVATE_MARKER_IDENTIFIER_NAME, (Exception,), {})

    rendered = _at_dp_122_direct_bus_dlq_rendering(private_exception)

    assert "TOP_SECRET" not in rendered
    assert "TOP SECRET" not in rendered
    assert "system_prompt" not in rendered
    assert AT_DP_122_PRIVATE_MARKER_IDENTIFIER_NAME not in rendered
    assert AT_DP_122_NEUTRAL_ERROR_CATEGORY in rendered


def test_at_dp_122_composed_event_system_runtime_error_stays_useful(
    connected,
) -> None:
    """MAJOR-V5-003 control: the composed facade keeps ordinary categories useful."""

    rendered = _at_dp_122_dead_letter_with_exception(connected, RuntimeError)

    assert '"error_type": "RuntimeError"' in rendered


def test_at_dp_122_legacy_direct_single_attempt_bus_is_unchanged() -> None:
    """MAJOR-V5-003 control: historical direct single-attempt behaviour is intact."""

    bus = AgentRuntimeEventBus(max_delivery_attempts=1)
    observed: list[AgentRuntimeEventDelivery] = []

    def failing(event: AgentRuntimeEvent) -> None:
        raise RuntimeError("legacy exploded")

    bus.subscribe(failing, ["message.received"])
    original = bus._deliver_to_subscriber

    def spy(event: AgentRuntimeEvent, record) -> AgentRuntimeEventDelivery:
        delivery = original(event, record)
        observed.append(delivery)
        return delivery

    bus._deliver_to_subscriber = spy  # type: ignore[method-assign]
    bus.publish(
        AgentRuntimeEventFactory().create_event(
            "message.received",
            {"request_id": "req-v5-legacy", "channel": "conversation"},
            event_id="evt-v5-legacy",
        )
    )

    assert observed, "expected the legacy delivery to be observed"
    assert observed[0].error == "legacy exploded"
    assert observed[0].metadata["attempts"] == 1


# ══════════════════════════════════════════════════════════════════════════
# Remediation V6 — AT-DP-122 additions for the three V6 majors and one minor
#
# The real composed event system is used throughout: the file-backed canonical
# repository, the canonical registry/bus/DLQ and the real production
# ``PlatformOrchestrationEventSink``.  No component is replaced by a mock.  The
# in-memory/file-backed parity scenario uses the two *official* repository
# implementations and nothing else.
# ══════════════════════════════════════════════════════════════════════════

#: The exact unbounded integer the independent Re-audit V6 published.
AT_DP_122_HUGE_INTEGER = 10**5000

#: The exact oversized finite float the independent Re-audit V6 published.
AT_DP_122_OVERSIZED_FLOAT = 1e308

#: The exact non-public filesystem locations the independent Re-audit V6 used.
AT_DP_122_PRIVATE_PATHS = (
    pytest.param("file:///Users/alice/.ssh/id_rsa", id="file_uri"),
    pytest.param("/Users/alice/.ssh/id_rsa", id="posix_users"),
    pytest.param("/home/alice/.ssh/id_rsa", id="posix_home"),
    pytest.param("Users/alice/.ssh/id_rsa", id="relative_users"),
    pytest.param("C:/Users/alice/.ssh/id_rsa", id="windows_forward"),
    pytest.param("C:\\Users\\alice\\.ssh\\id_rsa", id="windows_back"),
)

#: Legitimate public references the path classifier must not over-correct.
AT_DP_122_LEGITIMATE_REFERENCES = (
    pytest.param("workflow:123", id="workflow_colon"),
    pytest.param("domain:legal", id="domain_colon"),
    pytest.param("provider/model", id="provider_slash"),
    pytest.param("cmm.orchestration", id="producer_dotted"),
    pytest.param("CORR-ORIGINAL", id="correlation_token"),
    pytest.param("events:read", id="permission_colon"),
)


def _at_dp_122_connected_bytes(connected) -> bytes:
    store: Path = connected["store"]
    return store.read_bytes() if store.exists() else b""


def _at_dp_122_assert_nothing_persisted(connected, before: int = 0) -> None:
    system = connected["system"]
    assert system.repository.count() == before
    assert system.dead_letter_count() == 0


# ── MAJOR-V6-001 — numeric lifecycle facts are actually bounded ────────────


def test_at_dp_122_huge_numeric_fact_is_rejected_before_persistence(connected) -> None:
    """MAJOR-V6-001: the durable repository is never the safety boundary."""

    system = connected["system"]
    before = system.repository.count()
    before_bytes = _at_dp_122_connected_bytes(connected)

    with pytest.raises((PlatformEventPayloadError, TypeError, ValueError)):
        system.publish(
            "message.received",
            {
                "request_id": "req-v6-huge",
                "count": AT_DP_122_HUGE_INTEGER,
            },
            event_id="evt-v6-huge",
        )

    assert system.repository.count() == before
    assert system.repository.get("evt-v6-huge") is None
    assert _at_dp_122_connected_bytes(connected) == before_bytes


def test_at_dp_122_huge_numeric_fact_result_is_repository_independent(
    connected,
) -> None:
    """MAJOR-V6-001: both official repositories agree on the same public event."""

    from cmm.agent_runtime.runtime_event_repository import (
        InMemoryAgentRuntimeEventRepository,
    )
    from tests.events.test_phase11_22_event_system import build_system

    durable_system = connected["system"]
    memory_system = build_system(repository=InMemoryAgentRuntimeEventRepository())

    durable_result: object
    memory_result: object
    for system, label in ((memory_system, "memory"), (durable_system, "durable")):
        try:
            system.publish(
                "message.received",
                {
                    "request_id": f"req-v6-parity-{label}",
                    "count": AT_DP_122_HUGE_INTEGER,
                },
                event_id="evt-v6-parity",
            )
            result: object = "accepted"
        except (PlatformEventPayloadError, TypeError, ValueError) as exc:
            result = type(exc)
        if label == "memory":
            memory_result = result
        else:
            durable_result = result

    assert memory_result != "accepted"
    assert durable_result != "accepted"
    assert memory_result is durable_result
    assert memory_system.repository.count() == 0
    assert durable_system.repository.get("evt-v6-parity") is None


@pytest.mark.parametrize(
    ("key", "value"),
    (
        pytest.param("count", -1, id="negative_count"),
        pytest.param("attempts", -1, id="negative_attempts"),
        pytest.param("sequence", -1, id="negative_sequence"),
        pytest.param("duration_ms", -5, id="negative_duration"),
        pytest.param("duration_ms", AT_DP_122_OVERSIZED_FLOAT, id="oversized_float"),
        pytest.param("count", AT_DP_122_HUGE_INTEGER, id="huge_count"),
    ),
)
def test_at_dp_122_unbounded_numeric_facts_are_rejected(
    connected, key: str, value: object
) -> None:
    """MAJOR-V6-001: negative, oversized and unbounded numbers fail closed."""

    system = connected["system"]
    before = system.repository.count()
    before_bytes = _at_dp_122_connected_bytes(connected)

    with pytest.raises((PlatformEventPayloadError, TypeError, ValueError)):
        system.publish(
            "message.received",
            {"request_id": f"req-v6-bound-{key}", key: value},
            event_id=f"evt-v6-bound-{key}",
        )

    _at_dp_122_assert_nothing_persisted(connected, before)
    assert _at_dp_122_connected_bytes(connected) == before_bytes


def test_at_dp_122_negative_metadata_attempt_is_rejected(connected) -> None:
    """MAJOR-V6-001: bounded metadata numbers are bounded too."""

    system = connected["system"]
    before = system.repository.count()

    with pytest.raises((PlatformEventPayloadError, TypeError, ValueError)):
        system.publish(
            "message.received",
            {"request_id": "req-v6-meta-attempt"},
            event_id="evt-v6-meta-attempt",
            metadata={"attempt": -1},
        )

    _at_dp_122_assert_nothing_persisted(connected, before)


@pytest.mark.parametrize(
    ("key", "value"),
    (
        pytest.param("count", 0, id="count_zero"),
        pytest.param("count", 1, id="count_one"),
        pytest.param("attempts", 1, id="attempts_one"),
        pytest.param("sequence", 0, id="sequence_zero"),
        pytest.param("duration_ms", 0, id="duration_zero"),
        pytest.param("duration_ms", 125, id="duration_125"),
        pytest.param("version", 3, id="version_three"),
    ),
)
def test_at_dp_122_legitimate_bounded_numeric_facts_still_persist(
    connected, key: str, value: object
) -> None:
    """MAJOR-V6-001 control: real bounded lifecycle numbers remain supported."""

    system = connected["system"]
    event_id = f"evt-v6-ok-{key}-{value}"

    result = system.publish(
        "message.received",
        {"request_id": "req-v6-ok", key: value},
        event_id=event_id,
    )

    assert result.persisted is True
    stored = system.repository.get(event_id)
    assert stored is not None
    assert stored.payload.data[key] == value


def test_at_dp_122_normalized_metadata_numeric_facts_still_persist(
    connected,
) -> None:
    """MAJOR-V6-001 control: bounded metadata counts and ratios remain supported."""

    system = connected["system"]
    event_id = "evt-v6-ok-metadata"

    result = system.publish(
        "message.received",
        {"request_id": "req-v6-ok-meta"},
        event_id=event_id,
        metadata={"attempt": 1, "ratio": 0.5, "count": 2},
    )

    assert result.persisted is True
    stored = system.repository.get(event_id)
    assert stored is not None
    assert stored.header.metadata == {"attempt": 1, "ratio": 0.5, "count": 2}


# ── MAJOR-V6-002 — non-public filesystem locations never enter persistence ─


@pytest.mark.parametrize("path", AT_DP_122_PRIVATE_PATHS)
def test_at_dp_122_private_filesystem_path_is_rejected(connected, path: str) -> None:
    """MAJOR-V6-002: a local secret location is not a public identifier."""

    system = connected["system"]
    before = system.repository.count()
    before_bytes = _at_dp_122_connected_bytes(connected)

    with pytest.raises((PlatformEventPayloadError, TypeError, ValueError)):
        system.publish(
            "message.received",
            {"request_id": path},
            event_id="evt-v6-path",
        )

    assert system.repository.get("evt-v6-path") is None
    _at_dp_122_assert_nothing_persisted(connected, before)
    assert b".ssh" not in _at_dp_122_connected_bytes(connected)
    assert _at_dp_122_connected_bytes(connected) == before_bytes


@pytest.mark.parametrize("path", AT_DP_122_PRIVATE_PATHS)
def test_at_dp_122_private_filesystem_path_in_the_canonical_header_is_rejected(
    connected, path: str
) -> None:
    """MAJOR-V6-002: the header identifier channel is not an escape hatch."""

    system = connected["system"]
    before = system.repository.count()

    with pytest.raises((PlatformEventPayloadError, TypeError, ValueError)):
        system.publish(
            "message.received",
            {"request_id": "req-v6-path-header"},
            event_id="evt-v6-path-header",
            producer=path,
        )

    assert system.repository.get("evt-v6-path-header") is None
    _at_dp_122_assert_nothing_persisted(connected, before)


@pytest.mark.parametrize("reference", AT_DP_122_LEGITIMATE_REFERENCES)
def test_at_dp_122_legitimate_references_are_still_accepted(
    connected, reference: str
) -> None:
    """MAJOR-V6-002 control: genuine public references survive the classifier."""

    system = connected["system"]
    event_id = f"evt-v6-ref-{reference.replace(':', '-').replace('/', '-')}"

    result = system.publish(
        "message.received",
        {"request_id": "req-v6-ref", "domain_id": "domain:legal"},
        event_id=event_id,
        producer="cmm.orchestration",
        aggregate_id=reference,
    )

    assert result.persisted is True
    stored = system.repository.get(event_id)
    assert stored is not None
    assert stored.header.aggregate_id == reference
    assert stored.header.producer == "cmm.orchestration"


# ── MAJOR-V6-003 — one canonical header fact authority ────────────────────


@pytest.mark.parametrize(
    ("key", "payload_value", "header_facts"),
    (
        pytest.param(
            "event_id",
            "payload-event",
            {"event_id": "header-event"},
            id="event_id",
        ),
        pytest.param(
            "correlation_id",
            "payload-corr",
            {"correlation_id": "header-corr"},
            id="correlation_id",
        ),
        pytest.param(
            "causation_id",
            "payload-cause",
            {"causation_id": "header-cause"},
            id="causation_id",
        ),
        pytest.param(
            "producer",
            "payload-producer",
            {"producer": "header-producer"},
            id="producer",
        ),
        pytest.param(
            "event_type",
            "some.other.event",
            {"event_type": "message.received"},
            id="event_type",
        ),
        pytest.param(
            "schema_version",
            "1.1.0",
            {"schema_version": "1.0.0"},
            id="schema_version",
        ),
    ),
)
def test_at_dp_122_payload_header_conflict_cannot_persist(
    connected, key: str, payload_value: object, header_facts: dict
) -> None:
    """MAJOR-V6-003: two contradictory versions of one event fact cannot coexist.

    ``sensitivity`` is deliberately absent from this list: it is the one canonical
    header fact with a documented non-equal resolution, so a stricter payload
    classification is promoted into the header and a lower one never downgrades it.
    Both directions are accepted — and asserted — by
    ``test_at_dp_122_payload_sensitivity_cannot_downgrade_the_header``.
    """

    system = connected["system"]
    before = system.repository.count()
    before_bytes = _at_dp_122_connected_bytes(connected)

    with pytest.raises((PlatformEventPayloadError, TypeError, ValueError)):
        system.publish(
            "message.received",
            {"request_id": "req-v6-conflict", key: payload_value},
            event_id="evt-v6-conflict",
            **header_facts,
        )

    assert system.repository.get("evt-v6-conflict") is None
    _at_dp_122_assert_nothing_persisted(connected, before)
    assert _at_dp_122_connected_bytes(connected) == before_bytes


def test_at_dp_122_canonical_header_facts_are_never_persisted_twice(
    connected,
) -> None:
    """MAJOR-V6-003: a payload copy is consumed into the one authoritative header."""

    system = connected["system"]
    event_id = "evt-v6-authority"

    result = system.publish(
        "message.received",
        {
            "request_id": "req-v6-authority",
            "correlation_id": "corr-v6",
            "causation_id": "cause-v6",
            "producer": "producer-v6",
            "workflow_id": "workflow:123",
        },
        event_id=event_id,
        correlation_id="corr-v6",
        causation_id="cause-v6",
        producer="producer-v6",
    )

    assert result.persisted is True
    stored = system.repository.get(event_id)
    assert stored is not None
    assert stored.payload.data == {"request_id": "req-v6-authority"}
    assert stored.header.correlation_id == "corr-v6"
    assert stored.header.causation_id == "cause-v6"
    assert stored.header.producer == "producer-v6"
    assert stored.header.workflow_id == "workflow:123"


def test_at_dp_122_payload_sensitivity_cannot_downgrade_the_header(
    connected,
) -> None:
    """MAJOR-V6-003: the canonical classification is never lowered by payload."""

    system = connected["system"]
    event_id = "evt-v6-sensitivity"

    result = system.publish(
        "message.received",
        {"request_id": "req-v6-sensitivity", "sensitivity": "confidential"},
        event_id=event_id,
        sensitivity="internal",
    )

    assert result.persisted is True
    stored = system.repository.get(event_id)
    assert stored is not None
    assert stored.header.sensitivity is EventSensitivity.CONFIDENTIAL
    assert "sensitivity" not in stored.payload.data

    lowered = system.publish(
        "message.received",
        {"request_id": "req-v6-sensitivity-low", "sensitivity": "public"},
        event_id="evt-v6-sensitivity-low",
        sensitivity="restricted",
    )
    stored_low = system.repository.get(lowered.event.header.event_id)
    assert stored_low is not None
    assert stored_low.header.sensitivity is EventSensitivity.RESTRICTED
    assert "sensitivity" not in stored_low.payload.data


def test_at_dp_122_source_sensitivity_still_reaches_the_canonical_header(
    connected,
) -> None:
    """MAJOR-V6-003 control: the real Domain bridge keeps its classification."""

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
            event_id="DOM-V6-AT",
            occurred_at=OCCURRED,
            sensitivity="restricted",
            correlation_id="CORR-V6-AT",
            causation_id="CAUSE-V6-AT",
            payload={"execution_id": "EXEC-V6-AT", "status": "completed"},
        )
    )

    stored = system.repository.query(event_type="operation.executed")
    assert stored, "the domain execution lifecycle fact must be bridged"
    assert stored[-1].header.sensitivity is EventSensitivity.RESTRICTED
    assert "sensitivity" not in stored[-1].payload.data


# ── MINOR-V6-001 — timestamp semantics ───────────────────────────────────


@pytest.mark.parametrize(
    "timestamp",
    (
        pytest.param("9999-99-99T99:99Z", id="everything_invalid"),
        pytest.param("2026-13-01T12:00:00Z", id="invalid_month"),
        pytest.param("2026-02-31T12:00:00Z", id="invalid_day"),
        pytest.param("2026-09-27T25:61:00Z", id="invalid_hour_minute"),
        pytest.param("2026-09-27T12:61:00Z", id="invalid_minute"),
    ),
)
def test_at_dp_122_invalid_civil_timestamps_are_rejected(
    connected, timestamp: str
) -> None:
    """MINOR-V6-001: a real calendar/time value is required, not a text shape."""

    system = connected["system"]
    before = system.repository.count()
    before_bytes = _at_dp_122_connected_bytes(connected)

    with pytest.raises((PlatformEventPayloadError, TypeError, ValueError)):
        system.publish(
            "message.received",
            {"request_id": "req-v6-ts", "occurred_at": timestamp},
            event_id="evt-v6-ts",
        )

    assert system.repository.get("evt-v6-ts") is None
    _at_dp_122_assert_nothing_persisted(connected, before)
    assert _at_dp_122_connected_bytes(connected) == before_bytes


@pytest.mark.parametrize(
    "timestamp",
    (
        pytest.param("2026-09-27T12:00", id="no_seconds_no_offset"),
        pytest.param("2026-09-27T12:00:00", id="no_offset"),
    ),
)
def test_at_dp_122_timezone_ambiguous_timestamps_are_rejected(
    connected, timestamp: str
) -> None:
    """MINOR-V6-001: the canonical chronology contract is timezone-aware."""

    system = connected["system"]
    before = system.repository.count()

    with pytest.raises((PlatformEventPayloadError, TypeError, ValueError)):
        system.publish(
            "message.received",
            {"request_id": "req-v6-ts-tz", "emitted_at": timestamp},
            event_id="evt-v6-ts-tz",
        )

    assert system.repository.get("evt-v6-ts-tz") is None
    _at_dp_122_assert_nothing_persisted(connected, before)


@pytest.mark.parametrize(
    "timestamp",
    (
        pytest.param("2026-09-27T12:00:00Z", id="utc_z"),
        pytest.param("2026-09-27T12:00:00+02:00", id="offset_positive"),
        pytest.param("2024-01-01T12:00:00+00:00", id="explicit_utc_offset"),
    ),
)
def test_at_dp_122_valid_timezone_aware_timestamps_are_accepted(
    connected, timestamp: str
) -> None:
    """MINOR-V6-001 control: real timezone-aware timestamps stay valid."""

    system = connected["system"]
    event_id = f"evt-v6-ts-ok-{timestamp.replace(':', '').replace('+', 'p')}"

    result = system.publish(
        "message.received",
        {"request_id": "req-v6-ts-ok", "occurred_at": timestamp},
        event_id=event_id,
        emitted_at=datetime(2030, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
    )

    assert result.persisted is True
    stored = system.repository.get(event_id)
    assert stored is not None
    assert stored.header.occurred_at == datetime.fromisoformat(timestamp)
    assert "occurred_at" not in stored.payload.data


# ══════════════════════════════════════════════════════════════════════════
# Remediation V7 — AT-DP-122 additions for the two V7 majors
#
# The real composed event system is used throughout: the real Phase 11.1
# container, the real file-backed canonical repository, the canonical
# registry/bus/DLQ and the real production ``PlatformOrchestrationEventSink``
# reached through the real Orchestrator.  No component is replaced by a mock.
#
# Both V7 findings are re-derived here through that composition, on every shared
# persisted identifier channel, and the real orchestration path is exercised end
# to end so "rejected before persistence" is proven by the durable store itself.
# ══════════════════════════════════════════════════════════════════════════

#: The exact relative traversals the independent Re-audit V7 published.
AT_DP_122_V7_TRAVERSALS = (
    pytest.param("safe/../../etc/shadow", id="etc_shadow"),
    pytest.param("foo/../bar/../../private/var", id="private_var"),
)

#: The exact URI userinfo credentials the independent Re-audit V7 published.
AT_DP_122_V7_URI_USERINFO = (
    pytest.param("https://admin:hunter2hunter2@example.com/path", id="https_password"),
    pytest.param("postgres://alice:supersecret@example.com/db", id="postgres_password"),
)

#: Every V7 adversarial value, with the plain-text secret it would leak.
AT_DP_122_V7_ADVERSARIAL = (
    pytest.param("safe/../../etc/shadow", "safe/../../etc/shadow", id="traversal_etc"),
    pytest.param(
        "foo/../bar/../../private/var",
        "foo/../bar/../../private/var",
        id="traversal_private",
    ),
    pytest.param(
        "https://admin:hunter2hunter2@example.com/path",
        "hunter2hunter2",
        id="uri_userinfo_https",
    ),
    pytest.param(
        "postgres://alice:supersecret@example.com/db",
        "supersecret",
        id="uri_userinfo_postgres",
    ),
)

#: Legitimate public references and credential-free URIs both V7 rules must keep.
AT_DP_122_V7_LEGITIMATE = (
    pytest.param("workflow:123", id="workflow_colon"),
    pytest.param("domain:legal", id="domain_colon"),
    pytest.param("provider/model", id="provider_slash"),
    pytest.param("cmm.orchestration", id="producer_dotted"),
    pytest.param("events:read", id="permission_colon"),
    pytest.param("https://example.com/model", id="credential_free_https"),
    pytest.param("postgres://example.com/db", id="credential_free_postgres"),
)

#: Every shared persisted identifier channel, as ``(label, builder)`` where the
#: builder places one audited value into that channel and returns
#: ``(payload, header_facts)``.  Enumerating the channels is what makes "not a
#: ``request_id``-only patch" an executable claim in the connected acceptance.
AT_DP_122_V7_SHARED_CHANNELS = (
    ("payload_request_id", lambda r: ({"request_id": r}, {})),
    (
        "payload_workflow_id",
        lambda r: ({"request_id": "req-v7-at", "workflow_id": r}, {}),
    ),
    (
        "payload_aggregate_id",
        lambda r: ({"request_id": "req-v7-at", "aggregate_id": r}, {}),
    ),
    (
        "payload_producer",
        lambda r: ({"request_id": "req-v7-at", "producer": r}, {}),
    ),
    ("header_producer", lambda r: ({"request_id": "req-v7-at"}, {"producer": r})),
    (
        "header_aggregate_id",
        lambda r: ({"request_id": "req-v7-at"}, {"aggregate_id": r}),
    ),
    (
        "header_correlation_id",
        lambda r: ({"request_id": "req-v7-at"}, {"correlation_id": r}),
    ),
    ("header_source", lambda r: ({"request_id": "req-v7-at"}, {"source": r})),
    (
        "permissions",
        lambda r: ({"request_id": "req-v7-at"}, {"permissions": [r]}),
    ),
    (
        "metadata_error_type",
        lambda r: ({"request_id": "req-v7-at"}, {"metadata": {"error_type": r}}),
    ),
    (
        "nested_result_reference",
        lambda r: (
            {"request_id": "req-v7-at", "result_reference": {"reference_id": r}},
            {},
        ),
    ),
    (
        "structured_reference_sequence",
        lambda r: (
            {"request_id": "req-v7-at", "approval_refs": [{"reference_id": r}]},
            {},
        ),
    ),
    (
        "domain_reference_sequence",
        lambda r: ({"request_id": "req-v7-at", "supporting_domains": [r]}, {}),
    ),
)


def _at_dp_122_v7_assert_refused(connected, event_id: str, before_bytes: bytes) -> None:
    """Assert one refused publication left the real durable store untouched."""

    system = connected["system"]
    store: Path = connected["store"]
    assert system.repository.get(event_id) is None
    assert system.dead_letter_count() == 0
    assert _at_dp_122_connected_bytes(connected) == before_bytes
    assert not store.exists() or store.read_bytes() == before_bytes


@pytest.mark.parametrize(
    ("label", "build"),
    AT_DP_122_V7_SHARED_CHANNELS,
    ids=[case[0] for case in AT_DP_122_V7_SHARED_CHANNELS],
)
@pytest.mark.parametrize("reference", AT_DP_122_V7_TRAVERSALS)
def test_at_dp_122_v7_traversal_is_refused_on_every_shared_channel(
    connected, label: str, build, reference: str
) -> None:
    """MAJOR-V7-001: relative traversal fails closed on every persisted channel."""

    payload, header_facts = build(reference)
    system = connected["system"]
    before = system.repository.count()
    before_bytes = _at_dp_122_connected_bytes(connected)
    event_id = f"evt-v7-at-{label}"

    with pytest.raises((PlatformEventPayloadError, TypeError, ValueError)):
        system.publish(
            "message.received",
            payload,
            event_id=event_id,
            **header_facts,
        )

    assert system.repository.count() == before, label
    _at_dp_122_v7_assert_refused(connected, event_id, before_bytes)


@pytest.mark.parametrize(
    ("label", "build"),
    AT_DP_122_V7_SHARED_CHANNELS,
    ids=[case[0] for case in AT_DP_122_V7_SHARED_CHANNELS],
)
@pytest.mark.parametrize("reference", AT_DP_122_V7_URI_USERINFO)
def test_at_dp_122_v7_uri_userinfo_is_refused_on_every_shared_channel(
    connected, label: str, build, reference: str
) -> None:
    """MAJOR-V7-002: URI userinfo credentials fail closed on every channel."""

    payload, header_facts = build(reference)
    system = connected["system"]
    before = system.repository.count()
    before_bytes = _at_dp_122_connected_bytes(connected)
    event_id = f"evt-v7-at-{label}"

    with pytest.raises((PlatformEventPayloadError, TypeError, ValueError)):
        system.publish(
            "message.received",
            payload,
            event_id=event_id,
            **header_facts,
        )

    assert system.repository.count() == before, label
    _at_dp_122_v7_assert_refused(connected, event_id, before_bytes)


@pytest.mark.parametrize(
    ("reference", "secret"),
    AT_DP_122_V7_ADVERSARIAL,
    ids=[case.id for case in AT_DP_122_V7_ADVERSARIAL],
)
def test_at_dp_122_v7_no_adversarial_value_enters_the_durable_store(
    connected, reference: str, secret: str
) -> None:
    """MAJOR-V7-001/002: the real durable store never receives either shape."""

    system = connected["system"]
    store: Path = connected["store"]
    before = system.repository.count()
    before_bytes = _at_dp_122_connected_bytes(connected)

    with pytest.raises((PlatformEventPayloadError, TypeError, ValueError)):
        system.publish(
            "message.received",
            {"request_id": "req-v7-at-durable", "workflow_id": reference},
            event_id="evt-v7-at-durable",
            permissions=[reference],
            metadata={"error_type": reference},
        )

    assert system.repository.count() == before
    assert system.repository.get("evt-v7-at-durable") is None
    assert system.dead_letter_count() == 0
    assert _at_dp_122_connected_bytes(connected) == before_bytes
    if store.exists():
        assert secret.encode() not in store.read_bytes()


@pytest.mark.parametrize("reference", AT_DP_122_V7_LEGITIMATE)
def test_at_dp_122_v7_legitimate_references_still_persist_and_reopen(
    connected, reference: str
) -> None:
    """MAJOR-V7-001/002 control: the two rules do not over-correct."""

    system = connected["system"]
    store: Path = connected["store"]
    event_id = f"evt-v7-at-ok-{reference.replace(':', '-').replace('/', '-')}"

    result = system.publish(
        "message.received",
        {"request_id": "req-v7-at-ok", "workflow_id": reference},
        event_id=event_id,
        producer="cmm.orchestration",
        aggregate_id=reference,
        permissions=["events:read"],
    )

    assert result.persisted is True
    reopened = FileAgentRuntimeEventRepository(store).get(event_id)
    assert reopened is not None
    assert reopened.header.workflow_id == reference
    assert reopened.header.aggregate_id == reference
    assert reopened.header.producer == "cmm.orchestration"
    assert reopened.header.permissions == ["events:read"]
    assert event_fingerprint(result.event) == event_fingerprint(reopened)


@pytest.mark.parametrize(
    "reference", AT_DP_122_V7_TRAVERSALS + AT_DP_122_V7_URI_USERINFO
)
def test_at_dp_122_v7_real_orchestration_sink_refuses_before_persistence(
    connected, reference: str
) -> None:
    """MAJOR-V7-001/002: the real production adapter cannot persist either shape."""

    system = connected["system"]
    before = system.repository.count()
    before_bytes = _at_dp_122_connected_bytes(connected)
    sink = PlatformOrchestrationEventSink(system)

    with pytest.raises((PlatformEventPayloadError, TypeError, ValueError)):
        sink.emit(
            "orchestration.request_received",
            request_id=reference,
            payload={"channel": "conversation", "session_id": "session-v7-at"},
        )

    assert system.repository.count() == before
    assert system.dead_letter_count() == 0
    assert _at_dp_122_connected_bytes(connected) == before_bytes


@pytest.mark.parametrize(
    ("reference", "secret"),
    AT_DP_122_V7_ADVERSARIAL,
    ids=[case.id for case in AT_DP_122_V7_ADVERSARIAL],
)
def test_at_dp_122_v7_real_orchestrator_fails_closed_without_persistence(
    connected, reference: str, secret: str
) -> None:
    """MAJOR-V7-001/002: the real Orchestrator's mandatory emission refuses them.

    The Orchestrator owns the mandatory ``orchestration.request_received`` fact, so
    an identifier the platform boundary refuses makes the emission fail rather than
    being silently dropped.  The observable result is a failed orchestration with
    no durable event evidence at all — and no secret in the store.
    """

    system = connected["system"]
    store: Path = connected["store"]
    before = system.repository.count()
    before_bytes = _at_dp_122_connected_bytes(connected)

    result = _orchestrate(connected, reference)

    assert result.status.value == "failed"
    assert result.reason_codes == ("ORCHESTRATION_EVENT_EMISSION_FAILED",)
    assert system.repository.count() == before
    assert system.dead_letter_count() == 0
    assert _at_dp_122_connected_bytes(connected) == before_bytes
    if store.exists():
        assert secret.encode() not in store.read_bytes()


def test_at_dp_122_v7_the_refusal_message_never_echoes_the_secret(connected) -> None:
    """MAJOR-V7-002: the boundary refuses the credential without repeating it."""

    system = connected["system"]

    with pytest.raises((PlatformEventPayloadError, TypeError, ValueError)) as captured:
        system.publish(
            "message.received",
            {"request_id": "postgres://alice:supersecret@example.com/db"},
            event_id="evt-v7-at-echo",
        )

    assert "supersecret" not in str(captured.value)
    assert "hunter2hunter2" not in str(captured.value)


def test_at_dp_122_v7_retains_the_two_v6_controls_it_builds_on(connected) -> None:
    """MAJOR-V7-001 control: the frozen V6 path rules are still enforced."""

    system = connected["system"]
    before_bytes = _at_dp_122_connected_bytes(connected)

    # The V6 absolute-path rule still refuses its exact reproductions...
    for path in ("file:///Users/alice/.ssh/id_rsa", "C:/Users/alice/.ssh/id_rsa"):
        with pytest.raises((PlatformEventPayloadError, TypeError, ValueError)):
            system.publish(
                "message.received",
                {"request_id": path},
                event_id="evt-v7-at-v6-regression",
            )
    assert _at_dp_122_connected_bytes(connected) == before_bytes

    # ...and the new relative rule does not refuse a bare separator or a version.
    result = system.publish(
        "message.received",
        {"request_id": "req-v7-at-v6-control", "workflow_id": "provider/model"},
        event_id="evt-v7-at-v6-control",
        aggregate_id="cmm/orchestration/step",
    )
    assert result.persisted is True
    stored = system.repository.get("evt-v7-at-v6-control")
    assert stored is not None
    assert stored.header.aggregate_id == "cmm/orchestration/step"
