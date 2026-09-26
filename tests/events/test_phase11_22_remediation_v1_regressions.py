"""Phase 11.22 — Remediation V1 adversarial regressions.

These tests make the independent Audit V1 reproductions executable and permanent.
Each finding gets its own named test; no finding is hidden inside another test's
assertions.

Covered findings::

    MAJOR-001  event fingerprint is not genuinely content-bound
    MAJOR-002  EventSystem.publish_event() bypasses the platform boundary
    MAJOR-003  dead-letter replay is not subscriber-targeted
    MAJOR-004  kernel adapter loses explicit source correlation/causation
    MINOR-001  retry_total undercounts successful retries
    MINOR-002  malformed persisted payload shapes escape the corruption error

MINOR-003 (forbidden kernel source content must fail closed) is proven in
``test_phase11_22_kernel_adapter.py``; MINOR-004 in
``test_phase11_22_event_catalog.py``.

Every test here is adversarial: it reproduces the exact behaviour the audit
reported, and it must fail before the remediation and pass after it.
"""

from __future__ import annotations

import dataclasses
import json
from datetime import datetime, timedelta, timezone

import pytest

from cmm.agent_runtime.runtime_event_contracts import (
    AgentRuntimeEvent,
    AgentRuntimeEventHeader,
    AgentRuntimeEventPayload,
    EventSensitivity,
)
from cmm.agent_runtime.runtime_event_errors import (
    AgentRuntimeEventIdentityConflictError,
    AgentRuntimeEventPersistenceCorruptionError,
)
from cmm.agent_runtime.runtime_event_factory import (
    AgentRuntimeEventFactory,
    event_fingerprint,
)
from cmm.agent_runtime.runtime_event_repository import (
    FileAgentRuntimeEventRepository,
)
from cmm.events.event_payload_safety import PlatformEventPayloadError
from tests.events.test_phase11_22_event_system import build_system

MOMENT = datetime(2026, 9, 26, 12, 0, 0, tzinfo=timezone.utc)


# ══════════════════════════════════════════════════════════════════════════
# MAJOR-001 — the fingerprint must cover the complete canonical event content
# ══════════════════════════════════════════════════════════════════════════


def base_fingerprint_event() -> AgentRuntimeEvent:
    """One canonical event that exercises every persisted header/payload field."""

    factory = AgentRuntimeEventFactory()
    return factory.create_event(
        "message.received",
        {"request_id": "req-base", "status": "ok"},
        event_id="evt-fp-base",
        occurred_at=MOMENT,
        emitted_at=MOMENT,
        agent_id="agent-1",
        agent_run_id="run-1",
        goal_id="goal-1",
        workflow_id="wf-1",
        task_id="task-1",
        iteration_id="iter-1",
        correlation_id="corr-1",
        causation_id="cause-1",
        actor_id="actor-1",
        source="platform",
        sensitivity=EventSensitivity.INTERNAL,
        permissions=["permission-1"],
        metadata={"origin": "regression"},
        producer="cmm.test",
        aggregate_id="agg-1",
    )


#: Every material field the canonical serializer persists, with a value that
#: differs from ``base_fingerprint_event()``.  The list is derived from the
#: canonical ``to_dict()`` serialization, not from the fingerprint helper.
HEADER_MATERIAL_CHANGES = (
    ("event_id", "evt-fp-other"),
    ("event_type", "goal.created"),
    ("schema_version", "1.1.0"),
    ("occurred_at", MOMENT - timedelta(seconds=1)),
    ("emitted_at", MOMENT + timedelta(seconds=1)),
    ("agent_id", "agent-2"),
    ("agent_run_id", "run-2"),
    ("goal_id", "goal-2"),
    ("workflow_id", "wf-2"),
    ("task_id", "task-2"),
    ("iteration_id", "iter-2"),
    ("correlation_id", "corr-2"),
    ("causation_id", "cause-2"),
    ("actor_id", "actor-2"),
    ("source", "other-surface"),
    ("sensitivity", EventSensitivity.CONFIDENTIAL),
    ("permissions", ["permission-2"]),
    ("metadata", {"origin": "tampered"}),
    ("producer", "cmm.other"),
    ("aggregate_id", "agg-2"),
)


@pytest.mark.parametrize(
    ("field", "changed"),
    HEADER_MATERIAL_CHANGES,
    ids=[c[0] for c in HEADER_MATERIAL_CHANGES],
)
def test_fingerprint_changes_when_a_persisted_header_field_changes(
    field, changed
) -> None:
    """MAJOR-001: each canonical header field is material to the fingerprint."""

    factory = AgentRuntimeEventFactory()
    base = base_fingerprint_event()
    variant = dataclasses.replace(
        base, header=dataclasses.replace(base.header, **{field: changed})
    )

    # The mutation must really be material in the canonical serialization...
    assert factory.to_dict(base) != factory.to_dict(variant), field
    # ...and it must therefore change the fingerprint.
    assert event_fingerprint(base) != event_fingerprint(variant), field


PAYLOAD_MATERIAL_CHANGES = (
    (
        "payload_data",
        AgentRuntimeEventPayload(
            data={"request_id": "req-changed", "status": "ok"}, raw=None
        ),
    ),
    (
        "payload_data_status_only",
        AgentRuntimeEventPayload(
            data={"request_id": "req-base", "status": "different"}, raw=None
        ),
    ),
    (
        "payload_raw",
        AgentRuntimeEventPayload(
            data={"request_id": "req-base", "status": "ok"}, raw="raw-body"
        ),
    ),
)


@pytest.mark.parametrize(
    ("field", "changed"),
    PAYLOAD_MATERIAL_CHANGES,
    ids=[c[0] for c in PAYLOAD_MATERIAL_CHANGES],
)
def test_fingerprint_changes_when_a_persisted_payload_field_changes(
    field, changed
) -> None:
    """MAJOR-001: ``payload.data`` and ``payload.raw`` are material."""

    factory = AgentRuntimeEventFactory()
    base = base_fingerprint_event()
    variant = dataclasses.replace(base, payload=changed)

    assert factory.to_dict(base) != factory.to_dict(variant), field
    assert event_fingerprint(base) != event_fingerprint(variant), field


def test_fingerprint_is_deterministic_for_identical_content() -> None:
    """The content-bound fingerprint stays deterministic."""

    factory = AgentRuntimeEventFactory()
    assert event_fingerprint(base_fingerprint_event()) == event_fingerprint(
        base_fingerprint_event()
    )
    assert factory.to_dict(base_fingerprint_event()) == factory.to_dict(
        base_fingerprint_event()
    )


@pytest.mark.parametrize(
    ("field", "changed"),
    (
        ("correlation_id", "corr-2"),
        ("causation_id", "cause-2"),
        ("sensitivity", EventSensitivity.CONFIDENTIAL),
        ("metadata", {"origin": "tampered"}),
    ),
    ids=["correlation", "causation", "sensitivity", "metadata"],
)
def test_same_id_with_one_material_header_change_is_an_identity_conflict(
    field, changed
) -> None:
    """MAJOR-001: a same-ID material change must fail closed, not deduplicate."""

    factory = AgentRuntimeEventFactory()
    system = build_system()
    base = base_fingerprint_event()
    variant = dataclasses.replace(
        base, header=dataclasses.replace(base.header, **{field: changed})
    )

    assert factory.to_dict(base) != factory.to_dict(variant)

    first = system.publish_event(base)
    assert first.persisted is True

    with pytest.raises(AgentRuntimeEventIdentityConflictError):
        system.publish_event(variant)

    assert system.repository.count() == 1
    stored = system.repository.get(base.header.event_id)
    assert stored is not None
    assert getattr(stored.header, field) == getattr(base.header, field)


@pytest.mark.parametrize(
    ("field", "changed"),
    (
        ("correlation_id", "corr-2"),
        ("sensitivity", EventSensitivity.CONFIDENTIAL),
        ("metadata", {"origin": "tampered"}),
    ),
    ids=["correlation", "sensitivity", "metadata"],
)
def test_durable_repository_rejects_same_id_material_header_change(
    tmp_path, field, changed
) -> None:
    """MAJOR-001: the durable repository fails closed on the same conflict."""

    repository = FileAgentRuntimeEventRepository(tmp_path / "runtime_events.jsonl")
    base = base_fingerprint_event()
    variant = dataclasses.replace(
        base, header=dataclasses.replace(base.header, **{field: changed})
    )

    repository.save(base)

    with pytest.raises(AgentRuntimeEventIdentityConflictError):
        repository.save(variant)

    assert repository.count() == 1


def _write_durable_record(repository_path, event: AgentRuntimeEvent) -> dict:
    """Write one valid durable record and return its parsed JSON object."""

    FileAgentRuntimeEventRepository(repository_path).save(event)
    line = repository_path.read_text(encoding="utf-8").strip()
    return json.loads(line)


def _rewrite_record(repository_path, record: dict) -> None:
    repository_path.write_text(
        json.dumps(record, sort_keys=True, default=str) + "\n", encoding="utf-8"
    )


@pytest.mark.parametrize(
    ("field", "changed"),
    (
        ("correlation_id", "CORR-TAMPERED"),
        ("causation_id", "CAUSE-TAMPERED"),
        ("sensitivity", "restricted"),
        ("metadata", {"origin": "tampered"}),
        ("permissions", ["elevated"]),
    ),
    ids=["correlation", "causation", "sensitivity", "metadata", "permissions"],
)
def test_durable_store_detects_tampering_of_a_material_stored_field(
    tmp_path, field, changed
) -> None:
    """MAJOR-001: mutating a stored field without updating the fingerprint is corruption."""

    path = tmp_path / "events" / "runtime_events.jsonl"
    record = _write_durable_record(path, base_fingerprint_event())

    record["header"][field] = changed
    _rewrite_record(path, record)

    with pytest.raises(AgentRuntimeEventPersistenceCorruptionError):
        FileAgentRuntimeEventRepository(path)


def test_durable_store_still_accepts_its_own_untampered_record(tmp_path) -> None:
    """MAJOR-001: the strengthening must not reject a legitimate stored record."""

    path = tmp_path / "events" / "runtime_events.jsonl"
    event = base_fingerprint_event()
    _write_durable_record(path, event)

    reopened = FileAgentRuntimeEventRepository(path)

    restored = reopened.get(event.header.event_id)
    assert restored is not None
    assert event_fingerprint(restored) == event_fingerprint(event)
    assert reopened.count() == 1


# ══════════════════════════════════════════════════════════════════════════
# MAJOR-002 — publish_event() is itself the canonical platform boundary
# ══════════════════════════════════════════════════════════════════════════

FORBIDDEN_DIRECT_PUBLICATION_KEYS = (
    "prompt",
    "system_prompt",
    "developer_prompt",
    "chain_of_thought",
    "hidden_reasoning",
    "reasoning",
    "provider_request",
    "provider_response",
    "api_key",
    "password",
    "token",
    "authorization",
)


def manual_event(
    event_type: str,
    payload: dict,
    *,
    event_id: str = "evt-manual",
    raw: str | None = None,
    **header_facts,
) -> AgentRuntimeEvent:
    """Build a canonical event object directly, bypassing the safe factory path."""

    header = AgentRuntimeEventHeader(
        event_id=event_id,
        event_type=event_type,
        occurred_at=MOMENT,
        emitted_at=MOMENT,
        **header_facts,
    )
    return AgentRuntimeEvent(
        header=header, payload=AgentRuntimeEventPayload(data=payload, raw=raw)
    )


def _boundary_system():
    system = build_system()
    received: list[AgentRuntimeEvent] = []
    system.subscribe(received.append, ["goal.created"])
    return system, received


def _assert_nothing_reached_persistence(system, received) -> None:
    assert system.repository.count() == 0
    assert system.bus.stats.published_total == 0
    assert received == []
    assert system.dead_letter_count() == 0


def test_direct_publish_event_rejects_an_unknown_event_type() -> None:
    """MAJOR-002 reproduction B: an unknown canonical type must fail closed."""

    system, received = _boundary_system()

    with pytest.raises(ValueError):
        system.publish_event(
            manual_event("totally.unknown.event", {"request_id": "req-1"})
        )

    _assert_nothing_reached_persistence(system, received)


@pytest.mark.parametrize("key", FORBIDDEN_DIRECT_PUBLICATION_KEYS)
def test_direct_publish_event_rejects_forbidden_payload_keys(key: str) -> None:
    """MAJOR-002 reproduction A: forbidden content cannot reach persistence."""

    system, received = _boundary_system()

    with pytest.raises(PlatformEventPayloadError):
        system.publish_event(manual_event("goal.created", {key: "TOP SECRET"}))

    _assert_nothing_reached_persistence(system, received)


def test_direct_publish_event_rejects_a_credential_like_value() -> None:
    system, received = _boundary_system()

    with pytest.raises(PlatformEventPayloadError):
        system.publish_event(
            manual_event(
                "goal.created", {"goal_id": "Bearer abcdefghijklmnopqrstuvwxyz012"}
            )
        )

    _assert_nothing_reached_persistence(system, received)


def test_direct_publish_event_rejects_an_opaque_value() -> None:
    system, received = _boundary_system()

    with pytest.raises(PlatformEventPayloadError):
        system.publish_event(manual_event("goal.created", {"opaque": object()}))

    _assert_nothing_reached_persistence(system, received)


def test_direct_publish_event_rejects_a_binary_value() -> None:
    system, received = _boundary_system()

    with pytest.raises(PlatformEventPayloadError):
        system.publish_event(manual_event("goal.created", {"goal_id": b"\x00\x01"}))

    _assert_nothing_reached_persistence(system, received)


def test_direct_publish_event_rejects_a_key_outside_the_vocabulary() -> None:
    system, received = _boundary_system()

    with pytest.raises(PlatformEventPayloadError):
        system.publish_event(manual_event("goal.created", {"some_new_field": "value"}))

    _assert_nothing_reached_persistence(system, received)


def test_direct_publish_event_rejects_unsafe_raw_payload_content() -> None:
    system, received = _boundary_system()

    with pytest.raises(PlatformEventPayloadError):
        system.publish_event(
            manual_event("goal.created", {"goal_id": "g1"}, raw="raw provider text")
        )

    _assert_nothing_reached_persistence(system, received)


def test_direct_publish_event_accepts_a_safe_manual_event_and_preserves_identity() -> (
    None
):
    """MAJOR-002: the boundary must not break legitimate direct publication."""

    system = build_system()
    received: list[AgentRuntimeEvent] = []
    system.subscribe(received.append, ["goal.created"])

    result = system.publish_event(
        manual_event(
            "goal.created",
            {"goal_id": "g1"},
            event_id="evt-manual-safe",
            correlation_id="corr-manual",
            causation_id="cause-manual",
            metadata={"origin": "manual"},
            permissions=[],
        )
    )

    assert result.persisted is True
    assert result.delivered is True
    assert result.event.header.event_id == "evt-manual-safe"
    assert result.event.header.correlation_id == "corr-manual"
    assert result.event.header.causation_id == "cause-manual"
    assert result.event.header.metadata == {"origin": "manual"}
    stored = system.repository.get("evt-manual-safe")
    assert stored is not None
    assert stored.header.correlation_id == "corr-manual"
    assert [event.header.event_id for event in received] == ["evt-manual-safe"]


def test_facade_create_event_also_enforces_the_platform_vocabulary() -> None:
    """``create_event`` must not claim a bounded vocabulary it does not enforce."""

    system = build_system()

    with pytest.raises(PlatformEventPayloadError):
        system.create_event("goal.created", {"prompt": "leak me"})

    assert system.repository.count() == 0


# ══════════════════════════════════════════════════════════════════════════
# MAJOR-003 — dead-letter replay targets the original failed subscriber
# ══════════════════════════════════════════════════════════════════════════


def test_dlq_replay_is_not_satisfied_by_another_replay_enabled_subscriber() -> None:
    """MAJOR-003 reproduction: subscriber B must not resolve subscriber A's DLQ entry."""

    system = build_system(max_delivery_attempts=2)
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
        {"request_id": "req-dlq-target"},
        event_id="evt-dlq-target",
        occurred_at=MOMENT,
        emitted_at=MOMENT,
    )

    assert system.dead_letter_count() == 1
    entry = system.list_dead_letters()[0]
    assert entry.subscription_id == subscription_a
    assert len(a_calls) == 2
    assert len(b_calls) == 1

    result = system.replay_dead_letter(0)

    # A did not opt in to replay, so nothing was retried...
    assert result.replayed_count == 0
    assert len(a_calls) == 2
    # ...subscriber B must never stand in for A's failed delivery...
    assert len(b_calls) == 1
    # ...and A's dead-letter entry stays unresolved.
    assert system.dead_letter_count() == 1


def test_targeted_dlq_replay_reaches_only_the_failed_subscriber() -> None:
    """MAJOR-003: a successful targeted replay resolves A and never invokes B."""

    system = build_system(max_delivery_attempts=2)
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
        {"request_id": "req-dlq-targeted"},
        event_id="evt-dlq-targeted",
        occurred_at=MOMENT,
        emitted_at=MOMENT,
    )

    assert system.dead_letter_count() == 1
    assert system.list_dead_letters()[0].subscription_id == subscription_a
    assert len(a_calls) == 2
    assert len(b_calls) == 1

    state["fail"] = False
    result = system.replay_dead_letter(0)

    assert result.replayed_count == 1
    assert result.failed_count == 0
    # Only A was retried, exactly once, with the original event identity.
    assert a_calls == ["evt-dlq-targeted"] * 3
    # B was not invoked by this targeted dead-letter replay.
    assert len(b_calls) == 1
    assert system.dead_letter_count() == 0
    assert system.repository.count() == 1


def test_targeted_dlq_replay_keeps_the_entry_when_the_target_keeps_failing() -> None:
    """MAJOR-003: a failing target leaves the dead-letter entry intact."""

    system = build_system(max_delivery_attempts=2)
    a_calls: list[str] = []
    b_calls: list[str] = []

    def subscriber_a(event: AgentRuntimeEvent) -> None:
        a_calls.append(event.header.event_id)
        raise RuntimeError("subscriber A keeps failing")

    def subscriber_b(event: AgentRuntimeEvent) -> None:
        b_calls.append(event.header.event_id)

    subscription_a = system.subscribe(
        subscriber_a, ["message.received"], accept_replay=True
    )
    system.subscribe(subscriber_b, ["message.received"], accept_replay=True)

    system.publish(
        "message.received",
        {"request_id": "req-dlq-keeps-failing"},
        event_id="evt-dlq-keeps-failing",
        occurred_at=MOMENT,
        emitted_at=MOMENT,
    )

    result = system.replay_dead_letter(0)

    assert system.list_dead_letters()[0].subscription_id == subscription_a
    assert result.replayed_count == 0
    assert result.failed_count == 1
    # Bounded retry applies to the target only: two normal + two replay attempts.
    assert len(a_calls) == 4
    assert len(b_calls) == 1
    assert system.dead_letter_count() == 1
    assert system.repository.count() == 1


def test_targeted_dlq_replay_cannot_bypass_replay_policy() -> None:
    """MAJOR-003: a replay-disabled target keeps its entry unresolved."""

    system = build_system(max_delivery_attempts=2)
    calls: list[str] = []

    def subscriber_a(event: AgentRuntimeEvent) -> None:
        calls.append(event.header.event_id)
        raise RuntimeError("subscriber A failed")

    system.subscribe(subscriber_a, ["message.received"])

    system.publish(
        "message.received",
        {"request_id": "req-dlq-no-optin"},
        event_id="evt-dlq-no-optin",
        occurred_at=MOMENT,
        emitted_at=MOMENT,
    )

    result = system.replay_dead_letter(0)

    assert result.replayed_count == 0
    assert len(calls) == 2
    assert system.dead_letter_count() == 1


# ══════════════════════════════════════════════════════════════════════════
# MAJOR-004 — explicit source correlation/causation survives the kernel adapter
# ══════════════════════════════════════════════════════════════════════════


def _domain_event_with_explicit_tracing():
    from cmm.domains.event_factory import DomainEventFactory

    return DomainEventFactory().create_event(
        event_type="domain.execution.completed",
        domain_id="domain:general",
        actor="system",
        event_id="DOM-E1",
        occurred_at=MOMENT,
        correlation_id="CORR-ORIGINAL",
        causation_id="CAUSE-ORIGINAL",
        payload={"execution_id": "EXEC-1", "status": "completed"},
    )


def test_explicit_domain_correlation_and_causation_survive_the_kernel_adapter() -> None:
    """MAJOR-004 reproduction: explicit authoritative values must win."""

    from cmm.domains.event_publisher import DomainKernelEventPublisher
    from cmm.events.kernel_adapter import PlatformKernelEventAdapter

    system = build_system()
    adapter = PlatformKernelEventAdapter(system)
    publisher = DomainKernelEventPublisher(event_listener=adapter)

    kernel_event = publisher.publish(_domain_event_with_explicit_tracing())
    # The source serialization really carries both explicit values.
    assert kernel_event.payload["correlation_id"] == "CORR-ORIGINAL"
    assert kernel_event.payload["causation_id"] == "CAUSE-ORIGINAL"
    assert kernel_event.payload["event_id"] == "DOM-E1"
    assert kernel_event.payload["payload"]["execution_id"] == "EXEC-1"

    stored = system.repository.query(event_type="operation.executed")[0]

    assert stored.header.correlation_id == "CORR-ORIGINAL"
    assert stored.header.causation_id == "CAUSE-ORIGINAL"


def test_explicit_kernel_source_correlation_wins_over_derived_fallback() -> None:
    """MAJOR-004: an explicit source value beats the documented fallback."""

    from cmm.events.kernel_adapter import PlatformKernelEventAdapter
    from kernel.events.event import Event as KernelEvent

    system = build_system()
    adapter = PlatformKernelEventAdapter(system)

    event_id = adapter.handle(
        KernelEvent(
            name="workflow.completed",
            payload={
                "workflow_id": "wf-derived",
                "correlation_id": "CORR-EXPLICIT",
                "causation_id": "CAUSE-EXPLICIT",
                "status": "completed",
            },
        )
    )

    stored = system.repository.get(event_id)
    assert stored is not None
    assert stored.header.correlation_id == "CORR-EXPLICIT"
    assert stored.header.causation_id == "CAUSE-EXPLICIT"


def test_missing_explicit_tracing_still_allows_documented_fallback() -> None:
    """MAJOR-004: fallback derivation remains when the source has no explicit value."""

    from cmm.events.kernel_adapter import PlatformKernelEventAdapter
    from kernel.events.event import Event as KernelEvent

    system = build_system()
    adapter = PlatformKernelEventAdapter(system)

    event_id = adapter.handle(
        KernelEvent(name="workflow.completed", payload={"workflow_id": "wf-fallback"})
    )

    stored = system.repository.get(event_id)
    assert stored is not None
    # Both fall back to the documented derivation order, which reads
    # ``workflow_id`` first for each field.
    assert stored.header.correlation_id == "wf-fallback"
    assert stored.header.causation_id == "wf-fallback"


def test_explicit_causation_only_is_preserved_and_correlation_falls_back() -> None:
    """MAJOR-004: the two fields are independent."""

    from cmm.events.kernel_adapter import PlatformKernelEventAdapter
    from kernel.events.event import Event as KernelEvent

    system = build_system()
    adapter = PlatformKernelEventAdapter(system)

    event_id = adapter.handle(
        KernelEvent(
            name="workflow.completed",
            payload={"workflow_id": "wf-mixed", "causation_id": "CAUSE-ONLY"},
        )
    )

    stored = system.repository.get(event_id)
    assert stored is not None
    # Explicit causation wins; correlation falls back to the documented order.
    assert stored.header.causation_id == "CAUSE-ONLY"
    assert stored.header.correlation_id == "wf-mixed"


# ══════════════════════════════════════════════════════════════════════════
# MINOR-001 — retry_total counts retries, not initial attempts
# ══════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize(
    ("failures_before_success", "expected_retries"),
    ((0, 0), (1, 1), (2, 2), (3, 3)),
)
def test_retry_total_counts_successful_retries(
    failures_before_success: int, expected_retries: int
) -> None:
    """MINOR-001: a subscriber that eventually succeeds still counts its retries."""

    system = build_system(max_delivery_attempts=5)
    calls: list[str] = []

    def flaky(event: AgentRuntimeEvent) -> None:
        calls.append(event.header.event_id)
        if len(calls) <= failures_before_success:
            raise RuntimeError("transient failure")

    system.subscribe(flaky, ["message.received"])
    system.publish(
        "message.received",
        {"request_id": "req-retry-total"},
        event_id="evt-retry-total",
        occurred_at=MOMENT,
        emitted_at=MOMENT,
    )

    assert len(calls) == failures_before_success + 1
    assert system.stats().retry_total == expected_retries
    assert system.dead_letter_count() == 0
    assert system.stats().delivered_total == 1


@pytest.mark.parametrize("max_attempts", (1, 2, 3, 5))
def test_retry_total_counts_exhausted_retries_exactly(max_attempts: int) -> None:
    """MINOR-001: exhaustion counts exactly the retries that actually happened."""

    system = build_system(max_delivery_attempts=max_attempts)
    calls: list[str] = []

    def failing(event: AgentRuntimeEvent) -> None:
        calls.append(event.header.event_id)
        raise RuntimeError("permanent failure")

    system.subscribe(failing, ["message.received"])
    system.publish(
        "message.received",
        {"request_id": "req-retry-exhaust"},
        event_id="evt-retry-exhaust",
        occurred_at=MOMENT,
        emitted_at=MOMENT,
    )

    assert len(calls) == max_attempts
    assert system.stats().retry_total == max_attempts - 1
    assert system.dead_letter_count() == 1


def test_successful_first_attempt_never_counts_a_retry() -> None:
    """MINOR-001: no retry is invented for a first-attempt success."""

    system = build_system(max_delivery_attempts=4)
    received: list[AgentRuntimeEvent] = []
    system.subscribe(received.append, ["message.received"])

    for index in range(3):
        system.publish(
            "message.received",
            {"request_id": f"req-clean-{index}"},
            event_id=f"evt-clean-{index}",
            occurred_at=MOMENT,
            emitted_at=MOMENT,
        )

    assert len(received) == 3
    assert system.stats().retry_total == 0
    assert system.stats().delivered_total == 3


# ══════════════════════════════════════════════════════════════════════════
# MINOR-002 — malformed persisted payload shapes fail as canonical corruption
# ══════════════════════════════════════════════════════════════════════════


def _canonical_record(event: AgentRuntimeEvent) -> dict:
    factory = AgentRuntimeEventFactory()
    serialized = factory.to_dict(event)
    return {
        "header": serialized["header"],
        "payload": serialized["payload"],
        "fingerprint": event_fingerprint(event),
        "record_schema_version": "1.0.0",
    }


@pytest.mark.parametrize(
    "payload_shape",
    ([], "string", 1, None, 1.5, True),
    ids=["list", "string", "int", "null", "float", "bool"],
)
def test_non_mapping_persisted_payload_is_canonical_corruption(
    tmp_path, payload_shape
) -> None:
    """MINOR-002: ``payload`` that is not a mapping must not raise ``AttributeError``."""

    path = tmp_path / "runtime_events.jsonl"
    record = _canonical_record(base_fingerprint_event())
    record["payload"] = payload_shape
    _rewrite_record(path, record)

    with pytest.raises(AgentRuntimeEventPersistenceCorruptionError):
        FileAgentRuntimeEventRepository(path)


@pytest.mark.parametrize(
    "payload_data_shape",
    ([], "string", 1, None),
    ids=["list", "string", "int", "null"],
)
def test_non_mapping_persisted_payload_data_is_canonical_corruption(
    tmp_path, payload_data_shape
) -> None:
    """MINOR-002: a non-mapping ``payload.data`` is canonical corruption too."""

    path = tmp_path / "runtime_events.jsonl"
    record = _canonical_record(base_fingerprint_event())
    record["payload"] = {"data": payload_data_shape, "raw": None}
    _rewrite_record(path, record)

    with pytest.raises(AgentRuntimeEventPersistenceCorruptionError):
        FileAgentRuntimeEventRepository(path)


def test_factory_reports_a_deterministic_error_for_a_non_mapping_payload() -> None:
    """MINOR-002: the factory itself fails deterministically, never with AttributeError."""

    factory = AgentRuntimeEventFactory()
    record = _canonical_record(base_fingerprint_event())
    record["payload"] = []

    with pytest.raises((TypeError, ValueError)):
        factory.from_dict({"header": record["header"], "payload": record["payload"]})


def test_factory_reports_a_deterministic_error_for_a_non_mapping_record() -> None:
    factory = AgentRuntimeEventFactory()

    with pytest.raises((TypeError, ValueError)):
        factory.from_dict(["not", "a", "record"])  # type: ignore[arg-type]
