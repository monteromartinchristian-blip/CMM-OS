"""Phase 11.22 — ordering and isolation guarantees, and no stronger claims.

Phase 11.22 is local-first and single-process, so it guarantees only what such a
system can prove:

* publication order inside one canonical process;
* FIFO delivery per the existing bus contract;
* deterministic subscriber priority;
* append order in the durable repository;
* deterministic replay order from stored evidence.

It explicitly does **not** claim distributed total ordering, cross-device global
ordering, exactly-once execution across processes, or transactional ordering with
external remote systems.  These tests also prove that no stronger claim is
encoded anywhere in the Phase 11.22 surface.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from cmm.agent_runtime.runtime_event_contracts import (
    AgentRuntimeEvent,
    AgentRuntimeEventReplayRequest,
)
from cmm.agent_runtime.runtime_event_repository import (
    FileAgentRuntimeEventRepository,
)
from tests.events.test_phase11_22_event_system import build_system

REPO_ROOT = Path(__file__).resolve().parents[2]
BASE = datetime(2026, 9, 26, 12, 0, 0, tzinfo=timezone.utc)


# ── FIFO and subscriber priority ─────────────────────────────────────────────


def test_normal_publication_is_fifo() -> None:
    system = build_system()
    observed: list[str] = []
    system.subscribe(
        lambda event: observed.append(event.header.event_id), ["message.received"]
    )

    for index in range(5):
        system.publish(
            "message.received",
            {"request_id": f"req-{index}"},
            event_id=f"evt_{index}",
            occurred_at=BASE + timedelta(seconds=index),
            emitted_at=BASE + timedelta(seconds=index),
        )

    assert observed == [f"evt_{index}" for index in range(5)]


def test_subscriber_priority_is_deterministic() -> None:
    system = build_system()
    observed: list[str] = []

    def make(label: str):
        return lambda event: observed.append(label)

    system.subscribe(make("low"), ["message.received"], priority=100)
    system.subscribe(make("mid"), ["message.received"], priority=50)
    system.subscribe(make("high"), ["message.received"], priority=-10)

    for index in range(2):
        system.publish(
            "message.received",
            {"request_id": f"req-{index}"},
            event_id=f"evt_{index}",
        )

    assert observed == ["high", "mid", "low", "high", "mid", "low"]


def test_repository_append_order_is_preserved(tmp_path) -> None:
    store = tmp_path / "events.jsonl"
    repository = FileAgentRuntimeEventRepository(store)
    system = build_system(repository=repository)

    # Deliberately reverse-chronological timestamps: append order must win.
    for offset, event_id in enumerate(("evt_a", "evt_b", "evt_c")):
        system.publish(
            "message.received",
            {"request_id": f"req-{event_id}"},
            event_id=event_id,
            occurred_at=BASE - timedelta(hours=offset),
            emitted_at=BASE - timedelta(hours=offset),
        )

    assert [event.header.event_id for event in repository.list()] == [
        "evt_a",
        "evt_b",
        "evt_c",
    ]
    reopened = FileAgentRuntimeEventRepository(store)
    assert [event.header.event_id for event in reopened.list()] == [
        "evt_a",
        "evt_b",
        "evt_c",
    ]


def test_replay_order_is_deterministic_and_repeatable() -> None:
    system = build_system()
    observed: list[str] = []
    system.subscribe(
        lambda event: observed.append(event.header.event_id),
        ["message.received"],
        accept_replay=True,
    )
    for index in range(4):
        system.publish(
            "message.received",
            {"request_id": f"req-{index}"},
            event_id=f"evt_{index}",
            occurred_at=BASE + timedelta(seconds=index),
            emitted_at=BASE + timedelta(seconds=index),
        )
    observed.clear()

    system.replay(AgentRuntimeEventReplayRequest())
    first = list(observed)
    observed.clear()
    system.replay(AgentRuntimeEventReplayRequest())
    second = list(observed)

    assert first == second == [f"evt_{index}" for index in range(4)]


# ── Isolation between subscribers ────────────────────────────────────────────


def test_one_failing_subscriber_does_not_block_a_successful_one() -> None:
    system = build_system(max_delivery_attempts=2)
    healthy: list[AgentRuntimeEvent] = []

    def failing(event: AgentRuntimeEvent) -> None:
        raise RuntimeError("boom")

    system.subscribe(failing, ["message.received"])
    system.subscribe(healthy.append, ["message.received"], priority=1)

    result = system.publish("message.received", {"request_id": "req-1"})

    assert len(healthy) == 1
    assert result.delivered is True


def test_retry_targets_only_the_failing_subscriber() -> None:
    system = build_system(max_delivery_attempts=3)
    healthy_calls: list[str] = []
    failing_calls: list[str] = []

    def healthy(event: AgentRuntimeEvent) -> None:
        healthy_calls.append(event.header.event_id)

    def failing(event: AgentRuntimeEvent) -> None:
        failing_calls.append(event.header.event_id)
        raise RuntimeError("boom")

    system.subscribe(failing, ["message.received"])
    system.subscribe(healthy, ["message.received"], priority=1)

    system.publish(
        "message.received",
        {"request_id": "req-1"},
        event_id="evt_isolated",
    )

    assert healthy_calls == ["evt_isolated"]
    assert failing_calls == ["evt_isolated"] * 3


def test_a_failing_subscriber_does_not_receive_a_second_normal_delivery() -> None:
    system = build_system(max_delivery_attempts=2)
    calls: list[str] = []

    def failing(event: AgentRuntimeEvent) -> None:
        calls.append(event.header.event_id)
        raise RuntimeError("boom")

    system.subscribe(failing, ["message.received"])
    system.publish("message.received", {"request_id": "req-1"}, event_id="evt_once")

    # Two bounded attempts, then the canonical dead-lettered outcome: the
    # subscription is never retried again by normal publication.
    assert len(calls) == 2
    assert system.dead_letter_count() == 1

    system.publish(
        "message.received",
        {"request_id": "req-2"},
        event_id="evt_second",
    )
    assert calls.count("evt_once") == 2


def test_subscriptions_are_isolated_between_compositions() -> None:
    first = build_system()
    second = build_system()
    first_calls: list[str] = []
    first.subscribe(
        lambda event: first_calls.append(event.header.event_id), ["message.received"]
    )

    second.publish("message.received", {"request_id": "req-1"}, event_id="evt_only_two")

    assert first_calls == []


def test_filtered_subscribers_are_reported_as_filtered_not_delivered() -> None:
    system = build_system()
    observed: list[str] = []
    system.subscribe(
        lambda event: observed.append(event.header.event_id),
        ["message.received"],
        filters={"correlation_id": "corr-wanted"},
    )

    system.publish(
        "message.received",
        {"request_id": "req-1"},
        event_id="evt_other",
        correlation_id="corr-other",
    )
    system.publish(
        "message.received",
        {"request_id": "req-2"},
        event_id="evt_wanted",
        correlation_id="corr-wanted",
    )

    assert observed == ["evt_wanted"]


def test_declared_event_types_are_honoured() -> None:
    """A subscriber never receives an event type it did not declare."""

    system = build_system()
    observed: list[str] = []
    system.subscribe(
        lambda event: observed.append(event.header.event_type), ["goal.created"]
    )

    system.publish(
        "message.received",
        {"request_id": "req-1"},
        event_id="evt_message",
        occurred_at=BASE,
        emitted_at=BASE,
    )
    system.publish(
        "goal.created",
        {"goal_id": "goal-1"},
        event_id="evt_goal",
        occurred_at=BASE,
        emitted_at=BASE,
    )

    assert observed == ["goal.created"]


# ── No stronger guarantee is claimed ─────────────────────────────────────────


def test_no_distributed_or_global_ordering_claim_is_encoded() -> None:
    """The Phase 11.22 surface must not claim guarantees it cannot prove."""

    forbidden = (
        "exactly_once",
        "exactly-once",
        "global_order",
        "global order",
        "distributed_order",
        "total_order",
        "cross_device",
        "consensus",
        "partition_tolerance",
        "replication_factor",
    )

    offenders: list[str] = []
    for path in sorted((REPO_ROOT / "cmm" / "events").glob("*.py")):
        text = path.read_text().lower()
        for token in forbidden:
            if token in text:
                offenders.append(f"{path.name}:{token}")

    assert not offenders, f"unsupported ordering claim encoded: {offenders}"


def test_no_async_event_bus_or_worker_was_introduced() -> None:
    """Phase 11.22 adds no asynchronous worker infrastructure."""

    forbidden = (
        "asyncio",
        "threading.Thread",
        "multiprocessing",
        "celery",
        "queue.Queue",
    )

    offenders: list[str] = []
    for path in sorted((REPO_ROOT / "cmm" / "events").glob("*.py")):
        text = path.read_text()
        for token in forbidden:
            if token in text:
                offenders.append(f"{path.name}:{token}")

    assert not offenders, f"async worker infrastructure introduced: {offenders}"


def test_no_circuit_breaker_or_general_recovery_was_introduced() -> None:
    offenders: list[str] = []
    forbidden = (
        "CircuitBreaker",
        "circuit_breaker",
        "SelfHealing",
        "RecoveryManager",
        "BackoffStrategy",
        "exponential_backoff",
    )
    for path in sorted((REPO_ROOT / "cmm" / "events").glob("*.py")):
        text = path.read_text()
        for token in forbidden:
            if token in text:
                offenders.append(f"{path.name}:{token}")

    assert not offenders, f"Phase 11.24 scope implemented early: {offenders}"


def test_ordering_guarantees_are_local_and_synchronous() -> None:
    """Delivery is synchronous: publish returns only after delivery attempted."""

    system = build_system()
    observed: list[str] = []
    system.subscribe(
        lambda event: observed.append(event.header.event_id), ["message.received"]
    )

    system.publish("message.received", {"request_id": "req-1"}, event_id="evt_sync")

    # No drain, no wait: the subscriber already ran.
    assert observed == ["evt_sync"]


@pytest.mark.parametrize("attempts", [1, 2, 5])
def test_bounded_attempt_count_is_exactly_as_configured(attempts: int) -> None:
    system = build_system(max_delivery_attempts=attempts)
    calls: list[str] = []

    def failing(event: AgentRuntimeEvent) -> None:
        calls.append(event.header.event_id)
        raise RuntimeError("boom")

    system.subscribe(failing, ["message.received"])
    system.publish("message.received", {"request_id": "req-1"}, event_id="evt_bounded")

    assert len(calls) == attempts
    assert system.bus.max_delivery_attempts == attempts


def test_retry_total_reflects_attempts_minus_one() -> None:
    system = build_system(max_delivery_attempts=4)

    def failing(event: AgentRuntimeEvent) -> None:
        raise RuntimeError("boom")

    system.subscribe(failing, ["message.received"])
    system.publish("message.received", {"request_id": "req-1"})

    assert system.stats().retry_total == 3
    assert system.stats().failed_total == 1
    assert system.stats().dead_letter_total == 1
