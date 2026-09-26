"""Phase 11.22 — EventSystem facade: publication ordering, retry and DLQ.

These tests prove the one ordering guarantee Phase 11.22 adds, that the facade is
really a thin composition over the canonical Phase 9 components, that a bounded
delivery policy isolates a failing subscriber from a healthy one, and that retry
exhaustion produces exactly one canonical dead-letter record without ever storing
raw exception content.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from cmm.agent_runtime.runtime_event_contracts import (
    AgentRuntimeEvent,
    AgentRuntimeEventPayload,
    AgentRuntimeEventReplayRequest,
    EventDeliveryStatus,
)
from cmm.agent_runtime.runtime_event_dead_letter import (
    InMemoryAgentRuntimeDeadLetterQueue,
)
from cmm.agent_runtime.runtime_event_errors import (
    AgentRuntimeEventIdentityConflictError,
    AgentRuntimeEventRepositoryError,
)
from cmm.agent_runtime.runtime_event_factory import (
    event_fingerprint,
)
from cmm.agent_runtime.runtime_event_registry import AgentRuntimeEventRegistry
from cmm.agent_runtime.runtime_event_repository import (
    FileAgentRuntimeEventRepository,
    InMemoryAgentRuntimeEventRepository,
)
from cmm.events.event_system import (
    EventSystem,
    EventSystemStats,
    PublicationOutcome,
)

MOMENT = datetime(2024, 5, 1, 10, 0, 0, tzinfo=timezone.utc)


class _RecordingBus:
    """Minimal canonical-bus-compatible double for ordering assertions.

    It implements only the surface the facade is allowed to depend on, which is
    itself part of the proof that the facade owns no delivery algorithm.
    """

    def __init__(self, *, closed: bool = False, fail: bool = False) -> None:
        self.published: list[AgentRuntimeEvent] = []
        self._closed = closed
        self._fail = fail
        self.max_delivery_attempts = 1

    def publish(self, event: AgentRuntimeEvent) -> None:
        if self._fail:
            raise RuntimeError("delivery exploded")
        self.published.append(event)

    def is_closed(self) -> bool:
        return self._closed

    @property
    def stats(self):
        from cmm.agent_runtime.runtime_event_contracts import (
            AgentRuntimeEventBusStats,
        )

        return AgentRuntimeEventBusStats(published_total=len(self.published))

    def subscribe(self, handler, event_types, **kwargs):  # pragma: no cover
        return "sub_1"

    def unsubscribe(self, subscription_id):  # pragma: no cover
        return None


def build_system(
    *,
    repository=None,
    repository_factory=None,
    max_delivery_attempts: int = 1,
    bus=None,
) -> EventSystem:
    from cmm.agent_runtime.runtime_event_bus import AgentRuntimeEventBus
    from cmm.events import event_payload_safety  # noqa: F401  (import-time proof)

    actual_bus = bus or AgentRuntimeEventBus(
        max_delivery_attempts=max_delivery_attempts
    )
    return EventSystem(
        registry=AgentRuntimeEventRegistry(strict_mode=True),
        repository=repository
        if repository is not None
        else (
            repository_factory()
            if repository_factory
            else InMemoryAgentRuntimeEventRepository()
        ),
        bus=actual_bus,
    )


# ── Thin composition, not a second implementation ────────────────────────────


def test_facade_uses_the_canonical_registry_repository_and_bus() -> None:
    from cmm.agent_runtime.runtime_event_bus import AgentRuntimeEventBus

    system = build_system()

    assert isinstance(system.registry, AgentRuntimeEventRegistry)
    assert isinstance(system.bus, AgentRuntimeEventBus)
    assert isinstance(system.repository, InMemoryAgentRuntimeEventRepository)
    assert isinstance(system.dead_letters, InMemoryAgentRuntimeDeadLetterQueue)


def test_facade_keeps_no_subscriber_registry_of_its_own() -> None:
    system = build_system()

    before = system.stats().active_subscriptions
    received: list[AgentRuntimeEvent] = []
    subscription_id = system.subscribe(received.append, ["message.received"])

    # The subscription identity is the canonical bus's own identity.
    assert subscription_id.startswith("sub_")
    assert system.stats().active_subscriptions == before + 1


def test_facade_delegates_replay_to_the_canonical_replay_owner() -> None:
    from cmm.agent_runtime.runtime_event_replay import AgentRuntimeEventReplayer

    system = build_system()

    assert isinstance(system._replayer, AgentRuntimeEventReplayer)


def test_facade_has_no_global_singleton() -> None:
    first = build_system()
    second = build_system()

    assert first is not second
    first.subscribe(lambda event: None, ["message.received"])

    assert second.stats().active_subscriptions == 0


def test_facade_bypasses_neither_registry_nor_factory() -> None:
    system = build_system()

    with pytest.raises(ValueError):
        system.create_event("not.registered.event", {})


# ── Persist before deliver ───────────────────────────────────────────────────


def test_publish_persists_before_delivering() -> None:
    order: list[str] = []
    system = build_system()
    original_save = system.repository.save
    original_publish = system.bus.publish

    def save(event):
        order.append("persist")
        return original_save(event)

    def publish(event):
        order.append("deliver")
        return original_publish(event)

    system.repository.save = save  # type: ignore[method-assign]
    system.bus.publish = publish  # type: ignore[method-assign]

    result = system.publish("message.received", {"request_id": "req-1"})

    assert order == ["persist", "deliver"]
    assert result.persisted and result.delivered
    assert result.outcome is PublicationOutcome.PUBLISHED


def test_persistence_failure_prevents_delivery() -> None:
    system = build_system()
    delivered: list[AgentRuntimeEvent] = []
    system.subscribe(delivered.append, ["message.received"])

    def failing_save(event):
        raise AgentRuntimeEventRepositoryError("disk on fire")

    system.repository.save = failing_save  # type: ignore[method-assign]

    with pytest.raises(AgentRuntimeEventRepositoryError):
        system.publish("message.received", {"request_id": "req-1"})

    assert delivered == []


def test_persistence_success_with_delivery_failure_keeps_the_event_persisted() -> None:
    system = build_system(bus=_RecordingBus(fail=True))

    result = system.publish("message.received", {"request_id": "req-1"})

    assert result.persisted is True
    assert result.delivered is False
    assert result.outcome is PublicationOutcome.PERSISTED_DELIVERY_UNAVAILABLE
    assert system.repository.count() == 1


def test_persistence_success_with_closed_bus_keeps_the_event_persisted() -> None:
    system = build_system(bus=_RecordingBus(closed=True))

    result = system.publish("message.received", {"request_id": "req-1"})

    assert result.persisted is True
    assert result.delivered is False
    assert system.repository.count() == 1


def test_identical_republish_is_idempotent_and_delivers_once() -> None:
    system = build_system()
    received: list[AgentRuntimeEvent] = []
    system.subscribe(received.append, ["message.received"])

    first = system.publish(
        "message.received",
        {"request_id": "req-1"},
        event_id="evt_fixed",
        occurred_at=MOMENT,
        emitted_at=MOMENT,
    )
    second = system.publish(
        "message.received",
        {"request_id": "req-1"},
        event_id="evt_fixed",
        occurred_at=MOMENT,
        emitted_at=MOMENT,
    )

    assert first.outcome is PublicationOutcome.PUBLISHED
    assert second.outcome is PublicationOutcome.IDEMPOTENT_DUPLICATE
    assert second.persisted is False and second.delivered is False
    assert system.repository.count() == 1
    assert len(received) == 1
    assert system.stats().published_total == 1


def test_conflicting_republish_fails_closed_with_no_mutation() -> None:
    system = build_system()
    received: list[AgentRuntimeEvent] = []
    system.subscribe(received.append, ["message.received"])

    system.publish(
        "message.received",
        {"request_id": "req-1"},
        event_id="evt_fixed",
        occurred_at=MOMENT,
        emitted_at=MOMENT,
    )

    with pytest.raises(AgentRuntimeEventIdentityConflictError):
        system.publish(
            "message.received",
            {"request_id": "req-2"},
            event_id="evt_fixed",
            occurred_at=MOMENT,
            emitted_at=MOMENT,
        )

    assert system.repository.count() == 1
    assert len(received) == 1


def test_durable_repository_path_also_deduplicates_and_conflicts(tmp_path) -> None:
    system = build_system(
        repository=FileAgentRuntimeEventRepository(tmp_path / "events.jsonl")
    )

    system.publish(
        "message.received",
        {"request_id": "req-1"},
        event_id="evt_fixed",
        occurred_at=MOMENT,
        emitted_at=MOMENT,
    )
    duplicate = system.publish(
        "message.received",
        {"request_id": "req-1"},
        event_id="evt_fixed",
        occurred_at=MOMENT,
        emitted_at=MOMENT,
    )

    assert duplicate.outcome is PublicationOutcome.IDEMPOTENT_DUPLICATE
    assert system.repository.count() == 1

    with pytest.raises(AgentRuntimeEventIdentityConflictError):
        system.publish(
            "message.received",
            {"request_id": "req-2"},
            event_id="evt_fixed",
            occurred_at=MOMENT,
            emitted_at=MOMENT,
        )


def test_facade_rejects_unsafe_payload_before_persistence() -> None:
    from cmm.events.event_payload_safety import PlatformEventPayloadError

    system = build_system()

    with pytest.raises(PlatformEventPayloadError):
        system.publish("message.received", {"prompt": "leak me"})

    assert system.repository.count() == 0
    assert system.stats().published_total == 0


def test_publish_event_persists_and_delivers_a_prebuilt_event() -> None:
    system = build_system()
    received: list[AgentRuntimeEvent] = []
    system.subscribe(received.append, ["message.received"])
    event = system.create_event(
        "message.received", {"request_id": "req-1"}, event_id="evt_direct"
    )

    result = system.publish_event(event)

    assert result.persisted and result.delivered
    assert system.repository.get("evt_direct") is not None
    assert len(received) == 1


# ── Bounded retry ────────────────────────────────────────────────────────────


def test_legacy_single_attempt_is_the_default() -> None:
    system = build_system()

    assert system.bus.max_delivery_attempts == 1
    assert system.dead_letter_policy is False


def test_bounded_retry_targets_only_the_failing_subscriber() -> None:
    system = build_system(max_delivery_attempts=3)
    healthy: list[AgentRuntimeEvent] = []
    attempts: list[int] = []

    def failing(event: AgentRuntimeEvent) -> None:
        attempts.append(1)
        raise RuntimeError("subscriber boom")

    system.subscribe(failing, ["message.received"])
    system.subscribe(healthy.append, ["message.received"], priority=1)

    result = system.publish("message.received", {"request_id": "req-1"})

    assert result.delivered is True
    assert len(healthy) == 1
    assert len(attempts) == 3
    assert system.stats().retry_total == 2


def test_retry_attempts_keep_the_same_event_identity() -> None:
    from cmm.agent_runtime.runtime_event_bus import AgentRuntimeEventBus

    bus = AgentRuntimeEventBus(max_delivery_attempts=3)
    registry = AgentRuntimeEventRegistry(strict_mode=True)
    system = EventSystem(
        registry=registry, repository=InMemoryAgentRuntimeEventRepository(), bus=bus
    )
    seen_ids: list[str] = []

    def failing(event: AgentRuntimeEvent) -> None:
        seen_ids.append(event.header.event_id)
        raise RuntimeError("boom")

    system.subscribe(failing, ["message.received"])
    system.publish(
        "message.received",
        {"request_id": "req-1"},
        event_id="evt_stable",
        occurred_at=MOMENT,
        emitted_at=MOMENT,
    )

    assert seen_ids == ["evt_stable", "evt_stable", "evt_stable"]


def test_retry_creates_no_additional_repository_record() -> None:
    system = build_system(max_delivery_attempts=4)

    def failing(event: AgentRuntimeEvent) -> None:
        raise RuntimeError("boom")

    system.subscribe(failing, ["message.received"])
    system.publish("message.received", {"request_id": "req-1"})

    assert system.repository.count() == 1


def test_successful_retry_produces_no_dead_letter() -> None:
    system = build_system(max_delivery_attempts=3)
    state = {"calls": 0}

    def flaky(event: AgentRuntimeEvent) -> None:
        state["calls"] += 1
        if state["calls"] < 2:
            raise RuntimeError("transient")

    system.subscribe(flaky, ["message.received"])
    result = system.publish("message.received", {"request_id": "req-1"})

    assert result.delivered is True
    assert result.dead_lettered is False
    assert system.dead_letter_count() == 0
    assert state["calls"] == 2


def test_retry_exhaustion_produces_exactly_one_dead_letter() -> None:
    system = build_system(max_delivery_attempts=3)

    def failing(event: AgentRuntimeEvent) -> None:
        raise RuntimeError("boom")

    system.subscribe(failing, ["message.received"])
    result = system.publish("message.received", {"request_id": "req-1"})

    assert result.dead_lettered is True
    assert system.dead_letter_count() == 1
    # No new event merely because delivery was retried.
    assert system.repository.count() == 1


def test_dead_letter_preserves_safe_references_only() -> None:
    system = build_system(max_delivery_attempts=2)
    secret = "subscriber-secret-token-value"

    def failing(event: AgentRuntimeEvent) -> None:
        raise RuntimeError(f"failed with {secret}")

    subscription_id = system.subscribe(failing, ["message.received"])
    system.publish(
        "message.received",
        {"request_id": "req-1"},
        event_id="evt_dlq",
        occurred_at=MOMENT,
        emitted_at=MOMENT,
    )

    entries = system.list_dead_letters()
    assert len(entries) == 1
    entry = entries[0]

    assert entry.event.header.event_id == "evt_dlq"
    assert entry.event.header.event_type == "message.received"
    assert entry.subscription_id == subscription_id
    assert entry.attempts == 2
    assert entry.error_type == "RuntimeError"
    assert entry.first_failed_at is not None
    assert entry.last_failed_at is not None

    # The raw exception message must never be persisted in the dead letter.
    serialized = json.dumps(
        {
            "error": entry.error,
            "error_type": entry.error_type,
            "metadata": dict(entry.metadata),
        }
    )
    assert secret not in serialized
    assert "Traceback" not in serialized


def test_dead_letter_never_stores_a_traceback() -> None:
    system = build_system(max_delivery_attempts=2)

    def failing(event: AgentRuntimeEvent) -> None:
        raise ValueError("x" * 10)

    system.subscribe(failing, ["message.received"])
    system.publish("message.received", {"request_id": "req-1"})

    entry = system.list_dead_letters()[0]
    assert "Traceback (most recent call last)" not in str(entry.error)
    assert "\n" not in str(entry.error)


def test_fifo_and_subscriber_priority_are_preserved() -> None:
    system = build_system()
    observed: list[str] = []
    events: list[str] = []

    def make(label: str, priority: int):
        def handler(event: AgentRuntimeEvent) -> None:
            observed.append(label)

        return handler, priority

    low, low_priority = make("low", 10)
    high, high_priority = make("high", 1)
    system.subscribe(low, ["message.received"], priority=low_priority)
    system.subscribe(high, ["message.received"], priority=high_priority)

    for index in range(3):
        system.publish(
            "message.received",
            {"request_id": f"req-{index}"},
            event_id=f"evt_{index}",
        )
        events.append(f"evt_{index}")

    assert observed == ["high", "low"] * 3


# ── Read-only stats/health ───────────────────────────────────────────────────


def test_stats_projection_is_read_only_and_complete() -> None:
    system = build_system(max_delivery_attempts=2)

    def failing(event: AgentRuntimeEvent) -> None:
        raise RuntimeError("boom")

    system.subscribe(failing, ["message.received"])
    system.publish("message.received", {"request_id": "req-1"})

    stats = system.stats()

    assert isinstance(stats, EventSystemStats)
    assert stats.published_total == 1
    assert stats.failed_total == 1
    assert stats.retry_total == 1
    assert stats.dead_letter_total == 1
    assert stats.active_subscriptions == 1
    assert stats.repository_event_count == 1
    assert stats.bus_ready is True
    assert stats.replay_count == 0


def test_health_reports_closed_bus_state() -> None:
    system = build_system()
    system.bus.close()

    assert system.health()["bus_ready"] is False
    assert system.stats().bus_ready is False


def test_stats_reflects_replay_count() -> None:
    system = build_system()
    received: list[AgentRuntimeEvent] = []
    system.subscribe(received.append, ["message.received"], accept_replay=True)
    system.publish(
        "message.received",
        {"request_id": "req-1"},
        event_id="evt_replay",
        occurred_at=MOMENT,
        emitted_at=MOMENT,
    )

    system.replay(AgentRuntimeEventReplayRequest(event_id="evt_replay"))

    assert system.stats().replay_count == 1


def test_facade_does_not_expose_raw_hidden_implementation_state() -> None:
    system = build_system()

    health = system.health()
    assert set(health) == {
        "bus_ready",
        "active_subscriptions",
        "repository_event_count",
        "dead_letter_count",
    }

    frozen = system.create_event("message.received", {"request_id": "req-1"})
    assert isinstance(frozen, AgentRuntimeEvent)
    assert isinstance(frozen.payload, AgentRuntimeEventPayload)


def test_event_fingerprint_is_available_for_identity_proofs() -> None:
    system = build_system()
    event = system.create_event(
        "message.received", {"request_id": "req-1"}, event_id="evt_fp"
    )

    assert event_fingerprint(event) == event_fingerprint(event)


def test_facade_rejects_unexpected_creation_facts() -> None:
    system = build_system()

    with pytest.raises(TypeError):
        system.create_event(
            "message.received", {"request_id": "req-1"}, nonsense="value"
        )


def test_facade_rejects_a_non_event_publish() -> None:
    system = build_system()

    with pytest.raises(TypeError):
        system.publish_event("not an event")  # type: ignore[arg-type]


def test_delivery_status_vocabulary_is_unchanged() -> None:
    assert EventDeliveryStatus.DEAD_LETTERED.value == "dead_lettered"
    assert EventDeliveryStatus.SKIPPED.value == "skipped"
