"""Phase 11.22 — Remediation V2 adversarial regressions.

These tests make the independent Re-audit V2 reproductions executable and
permanent.  Each V2 finding gets its own named test; no finding is hidden inside
another test's assertions.

Covered findings::

    MAJOR-V2-001  persisted free-form header facts bypass the safety boundary
    MAJOR-V2-002  unsupported schema can be durably written and cannot be reopened
    MAJOR-V2-003  canonical event contracts are only shallow-frozen
    MAJOR-V2-004  real Domain Event mapped facts and source sensitivity are lost

Every test here is adversarial: it reproduces the exact behaviour the independent
re-audit V2 reported, so it must fail before the remediation and pass after it.

All four findings are exercised through real components — the public
``EventSystem`` facade, the canonical factory/registry/repository/bus, and the
real ``DomainEvent`` → ``DomainKernelEventPublisher`` → ``kernel.events.Event``
→ ``PlatformKernelEventAdapter`` → ``EventSystem`` chain.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from cmm.agent_runtime.runtime_event_contracts import (
    AgentRuntimeEvent,
    AgentRuntimeEventHeader,
    AgentRuntimeEventPayload,
    EventSensitivity,
)
from cmm.agent_runtime.runtime_event_errors import (
    AgentRuntimeEventSerializationError,
)
from cmm.agent_runtime.runtime_event_factory import event_fingerprint
from cmm.agent_runtime.runtime_event_repository import (
    FileAgentRuntimeEventRepository,
)
from cmm.events.event_payload_safety import PlatformEventPayloadError
from kernel.events.event import Event as KernelEvent
from tests.events.test_phase11_22_event_system import build_system

MOMENT = datetime(2026, 9, 26, 12, 0, 0, tzinfo=timezone.utc)

#: A credential-shaped value the canonical Phase 10.33 detector rejects.
CREDENTIAL_VALUE = "api_key=abcdef1234567890"

#: A high-confidence prefixed key, as independently persisted by Re-audit V2.
PREFIXED_KEY_VALUE = "sk-abcdefghijklmnop"


def manual_event(
    event_type: str,
    payload: dict,
    *,
    event_id: str = "evt-v2-manual",
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
        header=header, payload=AgentRuntimeEventPayload(data=payload)
    )


def _watching_system():
    """Return a system, the events a subscriber received, and its repository."""

    system = build_system()
    received: list[AgentRuntimeEvent] = []
    system.subscribe(received.append, ["goal.created"])
    return system, received


# ══════════════════════════════════════════════════════════════════════════
# MAJOR-V2-001 — every persisted free-form event fact passes the safety gate
# ══════════════════════════════════════════════════════════════════════════


#: Producer-controlled persisted channels carrying forbidden/private/credential
#: content.  Each case must be rejected before anything is persisted.
UNSAFE_HEADER_FACTS = (
    ("event_id_forbidden_text", {"event_id": "system_prompt=TOP SECRET"}),
    ("metadata_prompt_key", {"metadata": {"prompt": "TOP SECRET"}}),
    ("metadata_system_prompt_key", {"metadata": {"system_prompt": "you are"}}),
    ("metadata_api_key_key", {"metadata": {"api_key": PREFIXED_KEY_VALUE}}),
    ("metadata_reasoning_key", {"metadata": {"hidden_reasoning": "because"}}),
    (
        "metadata_nested_forbidden",
        {"metadata": {"nested": {"developer_prompt": "leak"}}},
    ),
    (
        "metadata_credential_value",
        {"metadata": {"note": "Bearer abcdefghijklmnopqrstuvwxyz0123456"}},
    ),
    ("permissions_credential", {"permissions": [CREDENTIAL_VALUE]}),
    ("permissions_prefixed_key", {"permissions": [PREFIXED_KEY_VALUE]}),
    (
        "permissions_credential_assignment",
        {"permissions": ["password=hunter2hunter2"]},
    ),
    ("producer_credential", {"producer": CREDENTIAL_VALUE}),
    ("producer_forbidden_text", {"producer": "system_prompt=TOP SECRET"}),
    ("aggregate_id_prefixed_key", {"aggregate_id": PREFIXED_KEY_VALUE}),
    ("aggregate_id_forbidden_text", {"aggregate_id": "system_prompt=TOP SECRET"}),
    ("source_forbidden_text", {"source": "system_prompt=TOP SECRET"}),
    ("source_credential", {"source": PREFIXED_KEY_VALUE}),
    ("actor_id_forbidden_text", {"actor_id": "system_prompt=TOP SECRET"}),
    (
        "agent_id_credential",
        {"agent_id": "Bearer abcdefghijklmnopqrstuvwxyz0123456"},
    ),
    ("agent_run_id_forbidden_text", {"agent_run_id": "reasoning trace"}),
    ("goal_id_prefixed_key", {"goal_id": PREFIXED_KEY_VALUE}),
    ("workflow_id_forbidden_text", {"workflow_id": "raw provider payload"}),
    ("task_id_credential_assignment", {"task_id": "credential=abc12345"}),
    ("iteration_id_credential", {"iteration_id": CREDENTIAL_VALUE}),
    ("correlation_id_forbidden_text", {"correlation_id": "system_prompt=leak"}),
    ("causation_id_credential", {"causation_id": CREDENTIAL_VALUE}),
)


@pytest.mark.parametrize(
    ("label", "facts"),
    UNSAFE_HEADER_FACTS,
    ids=[case[0] for case in UNSAFE_HEADER_FACTS],
)
def test_unsafe_header_facts_fail_closed_before_persistence(label, facts) -> None:
    """MAJOR-V2-001: forbidden content never enters any persisted event field."""

    system, received = _watching_system()

    with pytest.raises((ValueError, PlatformEventPayloadError)):
        system.publish("goal.created", {"status": "created"}, **facts)

    assert system.repository.count() == 0, label
    assert system.bus.stats.published_total == 0, label
    assert received == [], label
    assert system.dead_letter_count() == 0, label


@pytest.mark.parametrize(
    ("label", "facts"),
    UNSAFE_HEADER_FACTS,
    ids=[case[0] for case in UNSAFE_HEADER_FACTS],
)
def test_unsafe_header_facts_fail_closed_on_the_direct_route(label, facts) -> None:
    """MAJOR-V2-001: safety cannot depend on the caller picking a safe method."""

    system, received = _watching_system()

    with pytest.raises((ValueError, PlatformEventPayloadError)):
        system.publish_event(
            manual_event("goal.created", {"status": "created"}, **facts)
        )

    assert system.repository.count() == 0, label
    assert system.bus.stats.published_total == 0, label
    assert received == [], label


@pytest.mark.parametrize(
    ("label", "facts"),
    UNSAFE_HEADER_FACTS,
    ids=[case[0] for case in UNSAFE_HEADER_FACTS],
)
def test_unsafe_header_facts_fail_closed_at_creation(label, facts) -> None:
    """MAJOR-V2-001: ``create_event()`` is the same safety boundary."""

    system = build_system()

    with pytest.raises((ValueError, PlatformEventPayloadError)):
        system.create_event("goal.created", {"status": "created"}, **facts)

    assert system.repository.count() == 0, label


def test_forbidden_header_fact_never_reaches_a_file_backed_store(tmp_path) -> None:
    """MAJOR-V2-001: rejection happens before bytes are committed."""

    store = tmp_path / "data" / "events" / "runtime_events.jsonl"
    system = build_system(repository=FileAgentRuntimeEventRepository(store))

    with pytest.raises((ValueError, PlatformEventPayloadError)):
        system.publish(
            "goal.created",
            {"status": "created"},
            metadata={"prompt": "TOP SECRET"},
        )

    assert system.repository.count() == 0
    assert not store.exists()


#: Legitimate values that must keep working: the safety gate must preserve
#: genuine identifiers, categorical values and bounded metadata.
SAFE_HEADER_FACTS = (
    ("producer", {"producer": "orchestration"}),
    ("aggregate_id", {"aggregate_id": "workflow:123"}),
    ("source", {"source": "domain.execution.completed"}),
    ("permissions", {"permissions": ["events:read"]}),
    ("metadata", {"metadata": {"status_code": "ok", "attempt": 1}}),
    ("actor_id", {"actor_id": "user-42"}),
    ("agent_id", {"agent_id": "cmm.orchestrator"}),
    ("agent_run_id", {"agent_run_id": "run-1"}),
    ("goal_id", {"goal_id": "goal-1"}),
    ("workflow_id", {"workflow_id": "workflow:123"}),
    ("task_id", {"task_id": "task-1"}),
    ("iteration_id", {"iteration_id": "iter-1"}),
    ("correlation_id", {"correlation_id": "CORR-ORIGINAL"}),
    ("causation_id", {"causation_id": "CAUSE-ORIGINAL"}),
)


@pytest.mark.parametrize(
    ("label", "facts"),
    SAFE_HEADER_FACTS,
    ids=[case[0] for case in SAFE_HEADER_FACTS],
)
def test_legitimate_header_facts_stay_accepted(label, facts) -> None:
    """MAJOR-V2-001 control: real identifiers and bounded metadata stay valid."""

    system, received = _watching_system()

    result = system.publish(
        "goal.created",
        {"status": "created"},
        event_id=f"evt-safe-{label}",
        **facts,
    )

    assert result.persisted is True, label
    assert system.repository.count() == 1, label
    assert len(received) == 1, label


def test_all_legitimate_header_facts_together_stay_accepted() -> None:
    """MAJOR-V2-001 control: the documented safe combination is not over-rejected."""

    system, received = _watching_system()

    result = system.publish(
        "goal.created",
        {"status": "created"},
        event_id="evt-safe-combined",
        producer="orchestration",
        aggregate_id="workflow:123",
        source="domain.execution.completed",
        permissions=["events:read"],
        metadata={"status_code": "ok", "attempt": 1},
        correlation_id="CORR-ORIGINAL",
        causation_id="CAUSE-ORIGINAL",
    )

    assert result.persisted is True
    stored = system.repository.get("evt-safe-combined")
    assert stored is not None
    assert stored.header.producer == "orchestration"
    assert stored.header.aggregate_id == "workflow:123"
    assert stored.header.source == "domain.execution.completed"
    assert stored.header.permissions == ["events:read"]
    assert stored.header.metadata == {"status_code": "ok", "attempt": 1}
    assert len(received) == 1


# ══════════════════════════════════════════════════════════════════════════
# MAJOR-V2-002 — a durable save is always reopenable by the same build
# ══════════════════════════════════════════════════════════════════════════

UNSUPPORTED_SCHEMA = "9.9.9"


def test_public_facade_rejects_an_unsupported_schema_before_persistence() -> None:
    """MAJOR-V2-002: the public durable path must not poison its own store."""

    system, received = _watching_system()

    with pytest.raises((ValueError, AgentRuntimeEventSerializationError)):
        system.publish(
            "goal.created",
            {"status": "created"},
            schema_version=UNSUPPORTED_SCHEMA,
        )

    assert system.repository.count() == 0
    assert system.bus.stats.published_total == 0
    assert received == []
    assert system.dead_letter_count() == 0


def test_direct_publication_route_rejects_an_unsupported_schema() -> None:
    """MAJOR-V2-002: the direct route is the same boundary."""

    system, received = _watching_system()

    with pytest.raises((ValueError, AgentRuntimeEventSerializationError)):
        system.publish_event(
            manual_event(
                "goal.created",
                {"status": "created"},
                schema_version=UNSUPPORTED_SCHEMA,
            )
        )

    assert system.repository.count() == 0
    assert received == []


def test_durable_repository_rejects_an_unsupported_schema_before_append(
    tmp_path,
) -> None:
    """MAJOR-V2-002: the canonical repository contract fails closed before bytes."""

    store = tmp_path / "data" / "events" / "runtime_events.jsonl"
    repository = FileAgentRuntimeEventRepository(store)

    with pytest.raises((ValueError, AgentRuntimeEventSerializationError)):
        repository.save(
            manual_event(
                "goal.created",
                {"status": "created"},
                schema_version=UNSUPPORTED_SCHEMA,
            )
        )

    assert repository.count() == 0
    assert not store.exists()

    # The store is still perfectly readable by this build.
    assert FileAgentRuntimeEventRepository(store).count() == 0


def test_rejected_unsupported_schema_leaves_an_existing_store_intact(tmp_path) -> None:
    """MAJOR-V2-002: a rejected append must not disturb earlier evidence."""

    store = tmp_path / "data" / "events" / "runtime_events.jsonl"
    repository = FileAgentRuntimeEventRepository(store)
    repository.save(
        manual_event("goal.created", {"status": "created"}, event_id="evt-good")
    )
    before = store.read_bytes()

    with pytest.raises((ValueError, AgentRuntimeEventSerializationError)):
        repository.save(
            manual_event(
                "goal.created",
                {"status": "created"},
                event_id="evt-bad",
                schema_version=UNSUPPORTED_SCHEMA,
            )
        )

    assert store.read_bytes() == before
    assert repository.count() == 1

    reopened = FileAgentRuntimeEventRepository(store)
    assert reopened.count() == 1
    assert reopened.get("evt-good") is not None


def test_supported_schema_survives_close_and_reopen(tmp_path) -> None:
    """MAJOR-V2-002: the supported schema is genuinely round-trippable."""

    store = tmp_path / "data" / "events" / "runtime_events.jsonl"
    system = build_system(repository=FileAgentRuntimeEventRepository(store))

    result = system.publish(
        "goal.created",
        {"status": "created", "goal_id": "goal-rt"},
        event_id="evt-schema-roundtrip",
        source="domain.execution.completed",
        producer="orchestration",
        aggregate_id="workflow:123",
        permissions=["events:read"],
        metadata={"status_code": "ok", "attempt": 1},
        correlation_id="CORR-RT",
    )

    reopened = FileAgentRuntimeEventRepository(store)
    restored = reopened.get("evt-schema-roundtrip")

    assert restored is not None
    assert restored.header.schema_version == "1.0.0"
    assert restored.header.event_type == result.event.header.event_type
    assert restored.header.source == "domain.execution.completed"
    assert restored.header.producer == "orchestration"
    assert restored.header.aggregate_id == "workflow:123"
    assert restored.header.permissions == ["events:read"]
    assert restored.header.metadata == {"status_code": "ok", "attempt": 1}
    assert restored.header.correlation_id == "CORR-RT"
    assert restored.payload.data == dict(result.event.payload.data)
    assert event_fingerprint(restored) == event_fingerprint(result.event)


def test_durable_save_refuses_any_record_this_build_cannot_reopen(tmp_path) -> None:
    """MAJOR-V2-002 invariant: a durable save is always reopenable by this build."""

    store = tmp_path / "data" / "events" / "runtime_events.jsonl"
    repository = FileAgentRuntimeEventRepository(store)

    # An event type the canonical factory refuses to deserialize cannot be durably
    # written either, because the same build could not read its own record back.
    unreadable = manual_event(
        "not.a.registered.event", {"status": "created"}, event_id="evt-unreadable"
    )

    with pytest.raises((ValueError, AgentRuntimeEventSerializationError)):
        repository.save(unreadable)

    assert repository.count() == 0
    assert not store.exists()


# ══════════════════════════════════════════════════════════════════════════
# MAJOR-V2-003 — published canonical event facts are effectively immutable
# ══════════════════════════════════════════════════════════════════════════


def _mutating_subscriber(observed: list) -> object:
    """Return a subscriber that tries to tamper with the delivered canonical event."""

    def tamper(event: AgentRuntimeEvent) -> None:
        observed.append(event)
        event.payload.data["status"] = "tampered-by-A"
        event.header.metadata["tampered"] = "yes"
        event.header.permissions.append("escalate")

    return tamper


def test_subscriber_a_cannot_change_what_subscriber_b_sees() -> None:
    """MAJOR-V2-003: later subscribers observe the original canonical facts."""

    system = build_system()
    seen_by_b: list[tuple] = []

    system.subscribe(_mutating_subscriber([]), ["goal.created"], priority=0)
    system.subscribe(
        lambda event: seen_by_b.append(
            (
                dict(event.payload.data),
                dict(event.header.metadata),
                list(event.header.permissions),
            )
        ),
        ["goal.created"],
        priority=1,
    )

    system.publish(
        "goal.created",
        {"status": "created"},
        event_id="evt-iso-b",
        metadata={"origin": "original"},
        permissions=["events:read"],
    )

    assert seen_by_b == [
        (
            {"status": "created"},
            {"origin": "original"},
            ["events:read"],
        )
    ]


def test_subscriber_cannot_mutate_the_repository_or_publication_result() -> None:
    """MAJOR-V2-003: persisted evidence and the publication result stay stable."""

    system = build_system()

    system.subscribe(_mutating_subscriber([]), ["goal.created"], priority=0)

    result = system.publish(
        "goal.created",
        {"status": "created"},
        event_id="evt-iso-repo",
        metadata={"origin": "original"},
        permissions=["events:read"],
    )

    stored = system.repository.get("evt-iso-repo")
    assert stored is not None
    assert stored.payload.data == {"status": "created"}
    assert stored.header.metadata == {"origin": "original"}
    assert stored.header.permissions == ["events:read"]

    listed = system.repository.list(event_type="goal.created")
    assert listed[0].payload.data == {"status": "created"}
    assert listed[0].header.metadata == {"origin": "original"}
    assert listed[0].header.permissions == ["events:read"]

    assert result.event.payload.data == {"status": "created"}
    assert result.event.header.metadata == {"origin": "original"}
    assert result.event.header.permissions == ["events:read"]


def test_fingerprint_is_stable_after_a_subscriber_mutation_attempt() -> None:
    """MAJOR-V2-003: content-bound identity is unchanged by delivery."""

    system = build_system()
    before: list[str] = []

    def capture_then_tamper(event: AgentRuntimeEvent) -> None:
        before.append(event_fingerprint(event))
        event.payload.data["status"] = "tampered"

    system.subscribe(capture_then_tamper, ["goal.created"])
    system.subscribe(_mutating_subscriber([]), ["goal.created"], priority=1)

    result = system.publish(
        "goal.created",
        {"status": "created"},
        event_id="evt-iso-fp",
        metadata={"origin": "original"},
    )

    stored = system.repository.get("evt-iso-fp")
    assert stored is not None
    assert before == [event_fingerprint(stored)]
    assert event_fingerprint(result.event) == event_fingerprint(stored)


def test_file_backed_live_and_reopened_facts_match_after_a_mutation_attempt(
    tmp_path,
) -> None:
    """MAJOR-V2-003: subscriber mutation cannot split live state from disk bytes."""

    store = tmp_path / "data" / "events" / "runtime_events.jsonl"
    system = build_system(repository=FileAgentRuntimeEventRepository(store))
    system.subscribe(_mutating_subscriber([]), ["goal.created"])

    system.publish(
        "goal.created",
        {"status": "created"},
        event_id="evt-iso-file",
        metadata={"origin": "original"},
        permissions=["events:read"],
    )

    live = system.repository.get("evt-iso-file")
    reopened = FileAgentRuntimeEventRepository(store).get("evt-iso-file")

    assert live is not None and reopened is not None
    assert event_fingerprint(live) == event_fingerprint(reopened)
    assert reopened.payload.data == {"status": "created"}
    assert reopened.header.metadata == {"origin": "original"}
    assert reopened.header.permissions == ["events:read"]


def test_repository_returns_detached_evidence_a_caller_cannot_mutate() -> None:
    """MAJOR-V2-003: mutating a read result cannot change stored evidence."""

    system = build_system()
    system.publish(
        "goal.created",
        {"status": "created"},
        event_id="evt-detached",
        metadata={"origin": "original"},
        permissions=["events:read"],
    )

    first = system.repository.get("evt-detached")
    assert first is not None
    first.payload.data["status"] = "tampered"
    first.header.metadata["tampered"] = "yes"
    first.header.permissions.append("escalate")

    second = system.repository.get("evt-detached")
    assert second is not None
    assert second.payload.data == {"status": "created"}
    assert second.header.metadata == {"origin": "original"}
    assert second.header.permissions == ["events:read"]


def test_replay_also_delivers_detached_canonical_facts() -> None:
    """MAJOR-V2-003: the replay path has the same immutability guarantee."""

    from cmm.agent_runtime.runtime_event_contracts import (
        AgentRuntimeEventReplayRequest,
    )

    system = build_system()
    seen: list[tuple] = []

    system.subscribe(_mutating_subscriber([]), ["goal.created"], accept_replay=True)
    system.subscribe(
        lambda event: seen.append(
            (dict(event.payload.data), dict(event.header.metadata))
        ),
        ["goal.created"],
        accept_replay=True,
        priority=1,
    )

    system.publish(
        "goal.created",
        {"status": "created"},
        event_id="evt-iso-replay",
        metadata={"origin": "original"},
    )
    system.replay(AgentRuntimeEventReplayRequest(event_id="evt-iso-replay"))

    assert seen == [({"status": "created"}, {"origin": "original"})] * 2


def test_dead_letter_evidence_is_detached_from_subscriber_mutation() -> None:
    """MAJOR-V2-003: the dead-letter record keeps the canonical facts."""

    system = build_system(max_delivery_attempts=1)

    def failing_then_mutating(event: AgentRuntimeEvent) -> None:
        event.payload.data["status"] = "tampered"
        raise RuntimeError("boom")

    system.subscribe(failing_then_mutating, ["goal.created"])

    system.publish(
        "goal.created",
        {"status": "created"},
        event_id="evt-iso-dlq",
        metadata={"origin": "original"},
    )

    entries = system.list_dead_letters()
    assert len(entries) == 1
    assert entries[0].event.payload.data == {"status": "created"}
    assert entries[0].event.header.metadata == {"origin": "original"}


# ══════════════════════════════════════════════════════════════════════════
# MAJOR-V2-004 — real Domain Event bridge fidelity and sensitivity
# ══════════════════════════════════════════════════════════════════════════


def _real_domain_bridge(*, event_store_path=None):
    """Build the real Domain → Kernel → Platform chain with no mocks."""

    from cmm.domains.event_factory import DomainEventFactory
    from cmm.domains.event_publisher import DomainKernelEventPublisher
    from cmm.events.kernel_adapter import PlatformKernelEventAdapter

    repository = (
        FileAgentRuntimeEventRepository(event_store_path)
        if event_store_path is not None
        else None
    )
    system = build_system(repository=repository)
    adapter = PlatformKernelEventAdapter(system)
    publisher = DomainKernelEventPublisher(event_listener=adapter)
    return DomainEventFactory(), publisher, adapter, system


def _domain_event(
    factory,
    event_type: str,
    payload: dict,
    *,
    event_id: str,
    sensitivity: str = "internal",
    correlation_id: str | None = "CORR-ORIGINAL",
    causation_id: str | None = "CAUSE-ORIGINAL",
):
    return factory.create_event(
        event_type=event_type,
        domain_id="domain:general",
        actor="system",
        event_id=event_id,
        occurred_at=MOMENT,
        sensitivity=sensitivity,
        correlation_id=correlation_id,
        causation_id=causation_id,
        payload=payload,
    )


def test_real_domain_execution_completed_preserves_mapped_facts() -> None:
    """MAJOR-V2-004: execution identity and status survive the real bridge."""

    factory, publisher, adapter, system = _real_domain_bridge()
    domain_event = _domain_event(
        factory,
        "domain.execution.completed",
        {"execution_id": "EXEC-1", "status": "completed"},
        event_id="DOM-EXEC-1",
    )

    kernel_event = publisher.publish(domain_event)
    # The real source serialization really stores these facts nested.
    assert kernel_event.payload["payload"]["execution_id"] == "EXEC-1"
    assert kernel_event.payload["payload"]["status"] == "completed"

    stored = system.repository.query(event_type="operation.executed")[0]

    assert stored.payload.data["execution_id"] == "EXEC-1"
    assert stored.payload.data["status"] == "completed"
    assert stored.payload.data["domain_id"] == "domain:general"
    assert stored.header.correlation_id == "CORR-ORIGINAL"
    assert stored.header.causation_id == "CAUSE-ORIGINAL"
    assert adapter.skipped_events() == ()


def test_real_domain_approval_requested_preserves_approval_identity() -> None:
    """MAJOR-V2-004: approval identity survives, and no status is invented."""

    factory, publisher, _adapter, system = _real_domain_bridge()
    domain_event = _domain_event(
        factory,
        "domain.approval.requested",
        {"approval_id": "APP-1", "action": "delete"},
        event_id="DOM-APP-REQ-1",
    )

    publisher.publish(domain_event)

    stored = system.repository.query(event_type="approval.requested")[0]

    assert stored.payload.data["approval_id"] == "APP-1"
    assert stored.payload.data["domain_id"] == "domain:general"
    # The source carries no approval status, so the bridge must not invent one.
    assert "status" not in stored.payload.data


def test_real_domain_approval_received_preserves_identity_and_resolution() -> None:
    """MAJOR-V2-004: approval identity and the bounded resolution fact survive."""

    factory, publisher, _adapter, system = _real_domain_bridge()
    domain_event = _domain_event(
        factory,
        "domain.approval.received",
        {"approval_id": "APP-2", "approved": True, "decision_by": "u1"},
        event_id="DOM-APP-REC-1",
    )

    publisher.publish(domain_event)

    stored = system.repository.query(event_type="approval.resolved")[0]

    assert stored.payload.data["approval_id"] == "APP-2"
    assert stored.payload.data["approved"] is True
    assert stored.payload.data["domain_id"] == "domain:general"
    # ``decision_by`` is outside the bounded platform vocabulary on purpose.
    assert "decision_by" not in stored.payload.data
    # No raw arbitrary Domain payload is exposed.
    assert "action" not in stored.payload.data


def test_real_domain_memory_updated_preserves_mapped_status() -> None:
    """MAJOR-V2-004: the mapped memory update status survives."""

    factory, publisher, _adapter, system = _real_domain_bridge()
    domain_event = _domain_event(
        factory,
        "domain.memory.updated",
        {"update_id": "UPD-1", "status": "updated"},
        event_id="DOM-MEM-1",
    )

    publisher.publish(domain_event)

    stored = system.repository.query(event_type="memory.updated")[0]

    assert stored.payload.data["status"] == "updated"
    assert stored.payload.data["domain_id"] == "domain:general"
    # ``update_id`` is outside the bounded platform vocabulary on purpose.
    assert "update_id" not in stored.payload.data


#: Platform restriction order, least to most restrictive.
_PLATFORM_SENSITIVITY_RANK = {
    EventSensitivity.PUBLIC: 0,
    EventSensitivity.INTERNAL: 1,
    EventSensitivity.CONFIDENTIAL: 2,
    EventSensitivity.RESTRICTED: 3,
}

#: Domain source classifications and their semantic restriction rank.
_SOURCE_SENSITIVITY_RANK = {
    "public": 0,
    "internal": 1,
    "personal": 2,
    "confidential": 2,
    "sensitive": 2,
    "highly_sensitive": 3,
    "restricted": 3,
}


@pytest.mark.parametrize(
    ("source_sensitivity", "expected_platform"),
    (
        ("public", EventSensitivity.PUBLIC),
        ("internal", EventSensitivity.INTERNAL),
        ("confidential", EventSensitivity.CONFIDENTIAL),
        ("restricted", EventSensitivity.RESTRICTED),
        ("personal", EventSensitivity.CONFIDENTIAL),
        ("sensitive", EventSensitivity.CONFIDENTIAL),
        ("highly_sensitive", EventSensitivity.RESTRICTED),
    ),
)
def test_domain_sensitivity_is_never_downgraded(
    source_sensitivity, expected_platform
) -> None:
    """MAJOR-V2-004: SOURCE_SENSITIVITY_IS_NOT_DOWNGRADED across the real bridge."""

    factory, publisher, _adapter, system = _real_domain_bridge()
    domain_event = _domain_event(
        factory,
        "domain.execution.completed",
        {"execution_id": "EXEC-S", "status": "completed"},
        event_id=f"DOM-SENS-{source_sensitivity}",
        sensitivity=source_sensitivity,
    )

    publisher.publish(domain_event)

    stored = system.repository.query(event_type="operation.executed")[0]
    assert stored.header.sensitivity is expected_platform
    assert (
        _PLATFORM_SENSITIVITY_RANK[stored.header.sensitivity]
        >= (_SOURCE_SENSITIVITY_RANK[source_sensitivity])
    )


def test_restricted_domain_sensitivity_is_not_mapped_to_internal() -> None:
    """MAJOR-V2-004: the exact downgrade Re-audit V2 reproduced."""

    factory, publisher, _adapter, system = _real_domain_bridge()
    domain_event = _domain_event(
        factory,
        "domain.execution.completed",
        {"execution_id": "EXEC-R", "status": "completed"},
        event_id="DOM-SENS-RESTRICTED",
        sensitivity="restricted",
    )

    publisher.publish(domain_event)

    stored = system.repository.query(event_type="operation.executed")[0]
    assert stored.header.sensitivity is EventSensitivity.RESTRICTED


def test_nested_forbidden_domain_content_still_fails_closed() -> None:
    """MAJOR-V2-004: reading nested facts must not weaken nested scanning."""

    _factory, _publisher, adapter, system = _real_domain_bridge()

    for unsafe in (
        {"prompt": "leaked prompt"},
        {"chain_of_thought": "step 1"},
        {"provider_response": {"raw": "body"}},
        {"api_key": CREDENTIAL_VALUE},
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
        assert system.repository.count() == 0, unsafe


def test_top_level_execution_id_is_accepted_and_projected_consistently() -> None:
    """MAJOR-V2-004: no adapter path may generate a key the validator rejects."""

    _factory, _publisher, adapter, system = _real_domain_bridge()

    event_id = adapter.handle(
        KernelEvent(
            name="domain.execution.completed",
            payload={
                "domain_id": "domain:general",
                "execution_id": "EXEC-TOP",
                "status": "completed",
            },
        )
    )

    assert event_id is not None
    stored = system.repository.get(event_id)
    assert stored is not None
    assert stored.payload.data["execution_id"] == "EXEC-TOP"
    assert stored.payload.data["status"] == "completed"


def test_only_explicitly_mapped_nested_facts_cross_the_bridge() -> None:
    """MAJOR-V2-004: arbitrary nested Domain payload keys stay unreadable."""

    _factory, _publisher, adapter, system = _real_domain_bridge()

    event_id = adapter.handle(
        KernelEvent(
            name="domain.execution.completed",
            payload={
                "domain_id": "domain:general",
                "payload": {
                    "execution_id": "EXEC-ONLY",
                    "status": "completed",
                    "internal_debug_blob": {"x": 1},
                    "harmless_note": "note",
                },
            },
        )
    )

    stored = system.repository.get(event_id)
    assert stored is not None
    assert stored.payload.data["execution_id"] == "EXEC-ONLY"
    assert stored.payload.data["status"] == "completed"
    assert "internal_debug_blob" not in stored.payload.data
    assert "harmless_note" not in stored.payload.data


def test_nested_domain_facts_survive_the_durable_round_trip(tmp_path) -> None:
    """MAJOR-V2-004: mapped nested facts are durable, not delivery-only."""

    store = tmp_path / "data" / "events" / "runtime_events.jsonl"
    factory, publisher, _adapter, system = _real_domain_bridge(event_store_path=store)
    domain_event = _domain_event(
        factory,
        "domain.execution.completed",
        {"execution_id": "EXEC-DURABLE", "status": "completed"},
        event_id="DOM-DURABLE-1",
    )

    publisher.publish(domain_event)

    live = system.repository.query(event_type="operation.executed")[0]
    reopened = FileAgentRuntimeEventRepository(store).query(
        event_type="operation.executed"
    )[0]

    assert reopened.payload.data["execution_id"] == "EXEC-DURABLE"
    assert reopened.payload.data["status"] == "completed"
    assert event_fingerprint(live) == event_fingerprint(reopened)


def test_domain_event_records_are_still_serialized_by_the_domain_authority() -> None:
    """MAJOR-V2-004: the Domain Event contract itself is unchanged."""

    factory, publisher, _adapter, _system = _real_domain_bridge()
    domain_event = _domain_event(
        factory,
        "domain.approval.received",
        {"approval_id": "APP-3", "approved": False, "decision_by": "u2"},
        event_id="DOM-UNCHANGED-1",
    )

    kernel_event = publisher.publish(domain_event)

    assert kernel_event.name == domain_event.event_type
    assert kernel_event.payload == domain_event.to_dict()
    assert kernel_event.payload["payload"]["decision_by"] == "u2"
    assert publisher.emitted_events[-1] is kernel_event


def test_domain_authority_still_rejects_unsafe_payload_before_the_bridge() -> None:
    """MAJOR-V2-004: the Domain owner remains the first, unchanged safety gate."""

    from cmm.domains.errors import DomainContractValidationError
    from cmm.domains.event_factory import DomainEventFactory

    with pytest.raises((DomainContractValidationError, ValueError)):
        DomainEventFactory().create_event(
            event_type="domain.execution.completed",
            domain_id="domain:general",
            actor="system",
            occurred_at=MOMENT,
            payload={"execution_id": "EXEC-1", "prompt": "leaked"},
        )


# ══════════════════════════════════════════════════════════════════════════
# Persistence regression set (Remediation V2 required invariants)
# ══════════════════════════════════════════════════════════════════════════


def test_unsupported_schema_is_rejected_before_append_and_supported_round_trips(
    tmp_path,
) -> None:
    """UNSUPPORTED_SCHEMA_REJECTED_BEFORE_APPEND + SUPPORTED_SCHEMA_REOPEN_ROUNDTRIP."""

    store = tmp_path / "data" / "events" / "runtime_events.jsonl"
    system = build_system(repository=FileAgentRuntimeEventRepository(store))

    with pytest.raises((ValueError, AgentRuntimeEventSerializationError)):
        system.publish(
            "goal.created",
            {"status": "created"},
            event_id="evt-unsupported",
            schema_version="2.0.0",
        )

    assert json.loads(json.dumps({"count": system.repository.count()})) == {"count": 0}
    assert not store.exists()

    system.publish(
        "goal.created",
        {"status": "created"},
        event_id="evt-supported",
        occurred_at=MOMENT,
        emitted_at=MOMENT,
    )

    reopened = FileAgentRuntimeEventRepository(store)
    restored = reopened.get("evt-supported")

    assert restored is not None
    assert restored.header.schema_version == "1.0.0"
    assert restored.payload.data == {"status": "created"}


def test_live_event_facts_remain_stable_and_file_state_matches_reopen(tmp_path) -> None:
    """LIVE_EVENT_FACTS_STABLE_AFTER_DELIVERY + FILE_LIVE_AND_REOPENED_FACTS_MATCH."""

    store = tmp_path / "data" / "events" / "runtime_events.jsonl"
    system = build_system(repository=FileAgentRuntimeEventRepository(store))
    system.subscribe(_mutating_subscriber([]), ["goal.created"])

    system.publish(
        "goal.created",
        {"status": "created"},
        event_id="evt-live-stable",
        metadata={"origin": "original"},
        permissions=["events:read"],
    )

    live = system.repository.list()
    reopened = FileAgentRuntimeEventRepository(store).list()

    assert len(live) == len(reopened) == 1
    assert event_fingerprint(live[0]) == event_fingerprint(reopened[0])
    assert live[0].payload.data == {"status": "created"}
    assert live[0].header.metadata == {"origin": "original"}
    assert live[0].header.permissions == ["events:read"]


def test_the_safety_gate_accounts_for_every_persisted_event_channel() -> None:
    """MAJOR-V2-001: no persisted canonical channel is left ungoverned.

    This is the completeness gate for the finding: every persisted header field is
    either governed as an identifier fact, governed as a scanned container, or is
    a non-textual/closed-vocabulary fact that cannot carry producer prose.  Adding
    a new persisted header field therefore fails this gate until it is classified.
    """

    import dataclasses

    from cmm.agent_runtime.runtime_event_contracts import AgentRuntimeEventHeader
    from cmm.events.event_payload_safety import (
        PLATFORM_CONTAINER_HEADER_FIELDS,
        PLATFORM_IDENTIFIER_HEADER_FIELDS,
    )

    persisted = {field.name for field in dataclasses.fields(AgentRuntimeEventHeader)}
    accounted_for = (
        set(PLATFORM_IDENTIFIER_HEADER_FIELDS)
        | set(PLATFORM_CONTAINER_HEADER_FIELDS)
        | {
            # Registry-closed, schema-closed, datetime or enum facts: not free-form
            # producer text.
            "event_type",
            "schema_version",
            "occurred_at",
            "emitted_at",
            "sensitivity",
        }
    )

    assert accounted_for == persisted
    # The payload channel is governed by the bounded payload vocabulary itself.
    assert PLATFORM_IDENTIFIER_HEADER_FIELDS
    assert PLATFORM_CONTAINER_HEADER_FIELDS == ("metadata", "permissions")


def test_every_governed_identifier_field_has_an_adversarial_case() -> None:
    """MAJOR-V2-001: each governed identifier field is really exercised."""

    from cmm.events.event_payload_safety import PLATFORM_IDENTIFIER_HEADER_FIELDS

    exercised = {
        field
        for _label, facts in UNSAFE_HEADER_FACTS
        for field in facts
        if field in PLATFORM_IDENTIFIER_HEADER_FIELDS
    }

    assert exercised == set(PLATFORM_IDENTIFIER_HEADER_FIELDS)
