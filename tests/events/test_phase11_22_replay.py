"""Phase 11.22 — safe replay, replay opt-in and dead-letter replay.

Replay means re-notification of stored event evidence, never re-execution of
business commands.  These tests prove replay preserves identity, correlation and
causation, honours filters, supports dry-run, appends no second repository record
and reaches only subscribers that explicitly opted in.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from cmm.agent_runtime.runtime_event_contracts import (
    AgentRuntimeEvent,
    AgentRuntimeEventReplayRequest,
)
from cmm.agent_runtime.runtime_event_repository import (
    FileAgentRuntimeEventRepository,
    InMemoryAgentRuntimeEventRepository,
)
from cmm.events.event_system import EventSystem
from tests.events.test_phase11_22_event_system import build_system

MOMENT = datetime(2024, 5, 1, 10, 0, 0, tzinfo=timezone.utc)


def _publish(
    system: EventSystem,
    *,
    event_id: str,
    request_id: str = "req-1",
    correlation_id: str | None = None,
    causation_id: str | None = None,
    occurred_at: datetime | None = None,
) -> AgentRuntimeEvent:
    result = system.publish(
        "message.received",
        {"request_id": request_id},
        event_id=event_id,
        correlation_id=correlation_id,
        causation_id=causation_id,
        occurred_at=occurred_at or MOMENT,
        emitted_at=occurred_at or MOMENT,
    )
    # Publication legitimately performs one normal delivery.  Replay tests care
    # only about what replay delivers, so the capture list is cleared here.
    for captured in _CAPTURES:
        captured.clear()
    return result.event


#: Capture lists cleared after every helper publication, so an assertion about a
#: subscriber sees only replayed deliveries.
_CAPTURES: list[list] = []


def _capture(system: EventSystem, event_types: list[str], **kwargs):
    """Subscribe and register the list so helper publications do not pollute it."""

    received: list[AgentRuntimeEvent] = []
    _CAPTURES.append(received)
    system.subscribe(received.append, event_types, **kwargs)
    return received


# ── Replay reads canonical storage ───────────────────────────────────────────


def test_replay_reads_canonical_stored_events() -> None:
    system = build_system()
    received = _capture(system, ["message.received"], accept_replay=True)
    _publish(system, event_id="evt_r1")

    result = system.replay(AgentRuntimeEventReplayRequest(event_id="evt_r1"))

    assert [event.header.event_id for event in received] == ["evt_r1"]
    assert result.replayed_count == 1
    # Replay re-notified a subscriber with the canonical stored event identity.
    assert received[0] is system.repository.get("evt_r1")


def test_dry_run_invokes_no_subscriber() -> None:
    system = build_system()
    received = _capture(system, ["message.received"], accept_replay=True)
    _publish(system, event_id="evt_r1")

    result = system.replay(
        AgentRuntimeEventReplayRequest(event_id="evt_r1", dry_run=True)
    )

    assert result.dry_run is True
    assert received == []
    assert result.replayed_count == 0
    assert result.skipped_count >= 1


def test_replay_preserves_original_event_identity() -> None:
    system = build_system()
    received = _capture(system, ["message.received"], accept_replay=True)
    _publish(system, event_id="evt_identity")

    system.replay(AgentRuntimeEventReplayRequest(event_id="evt_identity"))

    assert received[0].header.event_id == "evt_identity"


def test_replay_preserves_correlation_and_causation() -> None:
    system = build_system()
    received = _capture(system, ["message.received"], accept_replay=True)
    _publish(
        system,
        event_id="evt_corr",
        correlation_id="corr-1",
        causation_id="cause-1",
    )

    system.replay(AgentRuntimeEventReplayRequest(event_id="evt_corr"))

    assert received[0].header.correlation_id == "corr-1"
    assert received[0].header.causation_id == "cause-1"


def test_replay_preserves_event_facts() -> None:
    system = build_system()
    received = _capture(system, ["message.received"], accept_replay=True)
    stored = _publish(system, event_id="evt_facts", request_id="req-facts")

    system.replay(AgentRuntimeEventReplayRequest(event_id="evt_facts"))

    assert received[0].payload.data == stored.payload.data


def test_replay_does_not_append_a_second_repository_record() -> None:
    system = build_system()
    system.subscribe(lambda event: None, ["message.received"], accept_replay=True)
    _publish(system, event_id="evt_once")

    assert system.repository.count() == 1

    system.replay(AgentRuntimeEventReplayRequest(event_id="evt_once"))
    system.replay(AgentRuntimeEventReplayRequest(event_id="evt_once"))

    assert system.repository.count() == 1


def test_replay_does_not_mutate_the_original_record() -> None:
    system = build_system()
    system.subscribe(lambda event: None, ["message.received"], accept_replay=True)
    _publish(system, event_id="evt_immutable")
    before = system.repository.get("evt_immutable")

    system.replay(AgentRuntimeEventReplayRequest(event_id="evt_immutable"))

    after = system.repository.get("evt_immutable")
    assert after is before


def test_replay_order_is_deterministic() -> None:
    """Replay follows the canonical repository's deterministic stored order."""

    system = build_system()
    received: list[str] = []
    _CAPTURES.append(received)

    def handler(event: AgentRuntimeEvent) -> None:
        received.append(event.header.event_id)

    system.subscribe(handler, ["message.received"], accept_replay=True)
    moments = []
    for index in range(4):
        moment = MOMENT - timedelta(hours=index)
        moments.append(moment)
        _publish(
            system,
            event_id=f"evt_{index}",
            request_id=f"req-{index}",
            occurred_at=moment,
        )

    # The canonical repository lists stored evidence in chronological order; that
    # order is what replay must reproduce, run after run.
    expected = [event.header.event_id for event in system.repository.list()]
    assert expected == ["evt_3", "evt_2", "evt_1", "evt_0"]

    system.replay(AgentRuntimeEventReplayRequest())
    first_pass = list(received)
    received.clear()
    system.replay(AgentRuntimeEventReplayRequest())

    assert first_pass == expected
    assert received == first_pass


def test_replay_honours_filters() -> None:
    system = build_system()
    _capture(system, ["message.received"], accept_replay=True)
    received: list[str] = []
    _CAPTURES.append(received)

    def handler(event: AgentRuntimeEvent) -> None:
        received.append(event.header.event_id)

    system.subscribe(handler, ["message.received"], accept_replay=True)
    _publish(system, event_id="evt_a", correlation_id="corr-a")
    _publish(system, event_id="evt_b", correlation_id="corr-b")

    result = system.replay(AgentRuntimeEventReplayRequest(correlation_id="corr-b"))

    assert received == ["evt_b"]
    assert result.replayed_count == 1


def test_replay_respects_the_requested_limit() -> None:
    system = build_system()
    _capture(system, ["message.received"], accept_replay=True)
    received: list[str] = []
    _CAPTURES.append(received)

    def handler(event: AgentRuntimeEvent) -> None:
        received.append(event.header.event_id)

    system.subscribe(handler, ["message.received"], accept_replay=True)
    for index in range(5):
        _publish(system, event_id=f"evt_{index}", request_id=f"req-{index}")

    system.replay(AgentRuntimeEventReplayRequest(limit=2))

    assert received == ["evt_0", "evt_1"]


# ── Replay opt-in ────────────────────────────────────────────────────────────


def test_replay_skips_a_subscriber_that_did_not_opt_in() -> None:
    system = build_system()
    side_effects: list[AgentRuntimeEvent] = []
    read_model: list[AgentRuntimeEvent] = []
    _CAPTURES.extend((side_effects, read_model))

    system.subscribe(side_effects.append, ["message.received"])
    system.subscribe(read_model.append, ["message.received"], accept_replay=True)
    _publish(system, event_id="evt_optin")

    system.replay(AgentRuntimeEventReplayRequest(event_id="evt_optin"))

    assert side_effects == []
    assert [event.header.event_id for event in read_model] == ["evt_optin"]


def test_default_subscription_is_never_silently_upgraded() -> None:
    system = build_system()
    received: list[AgentRuntimeEvent] = []
    _CAPTURES.append(received)
    subscription_id = system.subscribe(received.append, ["message.received"])
    _publish(system, event_id="evt_default")

    system.replay(AgentRuntimeEventReplayRequest(event_id="evt_default"))

    assert received == []

    from cmm.agent_runtime.runtime_event_replay import AgentRuntimeEventReplayer

    replayer = AgentRuntimeEventReplayer(system.repository, system.bus)
    deliveries = replayer._bus.deliver_replay(system.repository.get("evt_default"))
    skipped = [d for d in deliveries if d.subscription_id == subscription_id]
    assert skipped and skipped[0].status.value == "skipped"


def test_normal_publication_is_unaffected_by_the_replay_flag() -> None:
    system = build_system()
    received: list[AgentRuntimeEvent] = []
    _CAPTURES.append(received)
    system.subscribe(received.append, ["message.received"])  # accept_replay=False

    system.publish("message.received", {"request_id": "req-1"})

    assert len(received) == 1


def test_replay_can_be_repeated_to_the_same_opted_in_subscriber() -> None:
    system = build_system()
    received = _capture(system, ["message.received"], accept_replay=True)
    _publish(system, event_id="evt_repeat")

    for _ in range(3):
        system.replay(AgentRuntimeEventReplayRequest(event_id="evt_repeat"))

    assert len(received) == 3
    assert system.repository.count() == 1


def test_replay_reports_failure_when_delivery_fails() -> None:
    system = build_system()

    def failing(event: AgentRuntimeEvent) -> None:
        raise RuntimeError("replay boom")

    system.subscribe(failing, ["message.received"], accept_replay=True)
    _publish(system, event_id="evt_fail")

    result = system.replay(AgentRuntimeEventReplayRequest(event_id="evt_fail"))

    assert result.failed_count == 1
    assert result.replayed_count == 0
    assert result.errors


def test_replay_validates_its_request_type() -> None:
    system = build_system()

    with pytest.raises(TypeError):
        system.replay("not a request")  # type: ignore[arg-type]


def test_durable_storage_replays_across_reopen(tmp_path) -> None:
    path = tmp_path / "events.jsonl"
    system = build_system(repository=FileAgentRuntimeEventRepository(path))
    _publish(system, event_id="evt_persisted", correlation_id="corr-p")

    reopened = build_system(repository=FileAgentRuntimeEventRepository(path))
    received: list[AgentRuntimeEvent] = []
    reopened.subscribe(received.append, ["message.received"], accept_replay=True)

    result = reopened.replay(AgentRuntimeEventReplayRequest(event_id="evt_persisted"))

    assert result.replayed_count == 1
    assert received[0].header.event_id == "evt_persisted"
    assert received[0].header.correlation_id == "corr-p"
    assert reopened.repository.count() == 1


# ── Dead-letter replay ───────────────────────────────────────────────────────


def _system_with_dead_letter() -> tuple[EventSystem, list, dict]:
    """Build a system whose one opted-in subscriber has exhausted its delivery.

    Returns the system, the recorded attempt identities, and a mutable state
    mapping whose ``fail`` flag lets a test make the subscriber healthy before
    replaying the dead letter.
    """

    system = build_system(max_delivery_attempts=2)
    attempts: list[str] = []
    state = {"fail": True}

    def handler(event: AgentRuntimeEvent) -> None:
        attempts.append(event.header.event_id)
        if state["fail"]:
            raise RuntimeError("boom")

    _CAPTURES.append(attempts)
    system.subscribe(handler, ["message.received"], accept_replay=True)
    _publish(system, event_id="evt_dlq")
    assert system.dead_letter_count() == 1
    return system, attempts, state


def test_dead_letter_replay_resolves_the_original_stored_event() -> None:
    system, _attempts, _state = _system_with_dead_letter()
    entry = system._dead_letters.list()[0]

    # The entry references the persisted original, not a copy of it.
    stored = system.repository.get(entry.event.header.event_id)
    assert stored is not None
    assert entry.event.header.event_id == "evt_dlq"


def test_dead_letter_replay_success_removes_exactly_that_entry() -> None:
    system, attempts, state = _system_with_dead_letter()
    # The subscriber recovers, so the dead-letter replay can succeed.
    state["fail"] = False

    result = system.replay_dead_letter(0)

    assert result.replayed_count == 1
    assert system.dead_letter_count() == 0
    # No second event was persisted by the replay.
    assert system.repository.count() == 1
    assert attempts[-1] == "evt_dlq"


def test_dead_letter_replay_failure_leaves_the_entry_intact() -> None:
    system, _attempts, _state = _system_with_dead_letter()
    # The subscriber keeps failing, so replay cannot succeed.
    result = system.replay_dead_letter(0)

    assert result.failed_count == 1
    assert system.dead_letter_count() == 1
    # A failed replay must not create a second repository record either.
    assert system.repository.count() == 1


def test_dead_letter_replay_preserves_event_identity() -> None:
    system, attempts, _state = _system_with_dead_letter()
    before = len(attempts)

    system.replay_dead_letter(0)

    # Every replay attempt carries the original stored event identity; the
    # bounded policy allows two further attempts and no new event identity.
    assert set(attempts[before:]) == {"evt_dlq"}


def test_dead_letter_replay_dry_run_changes_nothing() -> None:
    system, _attempts, _state = _system_with_dead_letter()

    result = system.replay_dead_letter(
        0, request=AgentRuntimeEventReplayRequest(dry_run=True)
    )

    assert result.dry_run is True
    assert system.dead_letter_count() == 1


def test_dead_letter_replay_refuses_an_out_of_range_index() -> None:
    system = build_system()

    with pytest.raises(IndexError):
        system.replay_dead_letter(0)


def test_dead_letter_replay_cannot_bypass_subscriber_policy() -> None:
    """A non-opted-in subscriber is still skipped during dead-letter replay."""

    system = build_system(max_delivery_attempts=2)
    received: list[AgentRuntimeEvent] = []

    def failing(event: AgentRuntimeEvent) -> None:
        raise RuntimeError("boom")

    system.subscribe(failing, ["message.received"])
    _publish(system, event_id="evt_no_optin")
    assert system.dead_letter_count() == 1

    result = system.replay_dead_letter(0)

    # The failing subscriber did not opt in, so replay delivered to nobody and the
    # dead-letter entry must therefore remain unresolved.
    assert result.replayed_count == 0
    assert system.dead_letter_count() == 1
    assert received == []


def test_dead_letter_replay_does_not_elevate_permissions() -> None:
    """Replay adds no authority: it only re-notifies opted-in subscribers."""

    system, _attempts, _state = _system_with_dead_letter()
    entry = system.list_dead_letters()[0]

    assert entry.subscription_id.startswith("sub_")
    # The replayed event carries no permission grant.
    assert entry.event.header.permissions == []


def test_memory_and_durable_repositories_replay_identically(tmp_path) -> None:
    memory_system = build_system()
    durable_system = build_system(
        repository=FileAgentRuntimeEventRepository(tmp_path / "events.jsonl")
    )

    for system in (memory_system, durable_system):
        _publish(system, event_id="evt_same", correlation_id="corr-same")

    memory_received: list[AgentRuntimeEvent] = []
    durable_received: list[AgentRuntimeEvent] = []
    _CAPTURES.extend((memory_received, durable_received))
    memory_system.subscribe(
        memory_received.append, ["message.received"], accept_replay=True
    )
    durable_system.subscribe(
        durable_received.append, ["message.received"], accept_replay=True
    )

    memory_result = memory_system.replay(
        AgentRuntimeEventReplayRequest(correlation_id="corr-same")
    )
    durable_result = durable_system.replay(
        AgentRuntimeEventReplayRequest(correlation_id="corr-same")
    )

    assert memory_result.replayed_count == durable_result.replayed_count == 1
    assert memory_received[0].header.event_id == durable_received[0].header.event_id
    assert isinstance(memory_system.repository, InMemoryAgentRuntimeEventRepository)
