"""Phase 11.22 — Remediation V4 adversarial regressions.

These tests make the independent Re-audit V4 reproductions executable and
permanent.  Each V4 finding gets its own named test; no finding is hidden inside
another test's assertions.

Covered findings::

    MAJOR-V4-001  ``memoryview`` is treated as an ordinary sequence and is
                  recursively converted into a plain integer list, so binary bytes
                  enter canonical persisted event content through ``payload.data``
                  and through persisted header containers
    MAJOR-V4-002  manual ``publish_event()`` validates a canonical sensitivity
                  string without replacing it, so the accepted event keeps a
                  ``str`` sensitivity: accepted by the in-memory repository and
                  crashing with the file-backed repository
    MAJOR-V4-003  the DLQ stores ``type(exc).__name__`` unvalidated, so a
                  dynamically created exception class name can carry a credential
                  or private marker into ``error_type``/``error``

Every test here is adversarial: it reproduces the exact behaviour the independent
re-audit V4 reported, so it must fail before the remediation and pass after it.

All three findings are exercised through real components — the public
``EventSystem`` facade, the canonical factory/registry/bus/DLQ, and both official
repository implementations (in-memory and file-backed).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from cmm.agent_runtime.runtime_event_contracts import (
    AgentRuntimeEvent,
    AgentRuntimeEventDelivery,
    AgentRuntimeEventHeader,
    AgentRuntimeEventPayload,
    AgentRuntimeEventReplayRequest,
    EventSensitivity,
)
from cmm.agent_runtime.runtime_event_factory import event_fingerprint
from cmm.agent_runtime.runtime_event_repository import (
    FileAgentRuntimeEventRepository,
    InMemoryAgentRuntimeEventRepository,
)
from cmm.events.event_payload_safety import PlatformEventPayloadError
from cmm.events.event_system import EventSystem
from tests.events.test_phase11_22_event_system import build_system

MOMENT = datetime(2026, 9, 27, 12, 0, 0, tzinfo=timezone.utc)

#: The exact credential text the independent re-audit V4 used as a dynamic
#: exception class name.
CREDENTIAL_CLASS_NAME = "api_key=abcdef1234567890"

#: The exact private-marker text the independent re-audit used as a dynamic
#: exception class name.
PRIVATE_MARKER_CLASS_NAME = "system_prompt=TOP SECRET"

#: The exact binary buffer the independent re-audit V4 published.  Its byte values
#: are what the bypass converted into a persisted integer array.
BINARY_BUFFER = memoryview(b"secret-binary")

#: The integer array the pre-remediation bypass produced for :data:`BINARY_BUFFER`.
BINARY_BUFFER_AS_INTEGERS = list(BINARY_BUFFER.tobytes())

REJECTIONS = (PlatformEventPayloadError, TypeError, ValueError)


def manual_event(
    event_type: str,
    payload: dict[str, Any],
    *,
    event_id: str = "evt-v4-manual",
    **header_facts: Any,
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


def _watching_system() -> tuple[EventSystem, list[AgentRuntimeEvent]]:
    """Return an in-memory system plus the events one subscriber received."""

    system = build_system()
    received: list[AgentRuntimeEvent] = []
    system.subscribe(received.append, ["message.received"])
    return system, received


def _durable_store(tmp_path: Path) -> Path:
    return tmp_path / "data" / "events" / "runtime_events.jsonl"


def _file_backed_system(
    store: Path,
) -> tuple[EventSystem, list[AgentRuntimeEvent]]:
    system = build_system(
        repository_factory=lambda: FileAgentRuntimeEventRepository(store)
    )
    received: list[AgentRuntimeEvent] = []
    system.subscribe(received.append, ["message.received"])
    return system, received


def _assert_nothing_reached_persistence(
    system: EventSystem, received: list[AgentRuntimeEvent]
) -> None:
    """Prove the refusal happened before persistence and before delivery."""

    assert received == []
    assert system.repository.count() == 0
    assert system.bus.stats.published_total == 0
    assert system.dead_letter_count() == 0


# ══════════════════════════════════════════════════════════════════════════
# MAJOR-V4-001 — ``memoryview`` is binary, never an ordinary sequence
# ══════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize(
    "binary",
    [
        pytest.param(memoryview(b"secret-binary"), id="memoryview"),
        pytest.param(b"secret-binary", id="bytes_control"),
        pytest.param(bytearray(b"secret-binary"), id="bytearray_control"),
    ],
)
def test_payload_top_level_binary_is_rejected_before_persistence(
    binary: object,
) -> None:
    """MAJOR-V4-001: every binary container form fails closed in ``payload.data``."""

    system, received = _watching_system()

    with pytest.raises(REJECTIONS):
        system.publish(
            "message.received",
            {
                "request_id": "req-v4-binary",
                "channel": "conversation",
                "supporting_domains": binary,
            },
            event_id="evt-v4-binary",
        )

    _assert_nothing_reached_persistence(system, received)


def test_payload_memoryview_is_never_transformed_into_an_integer_array() -> None:
    """MAJOR-V4-001: the exact audited bypass must not become an integer array.

    The independent re-audit observed an accepted live canonical payload of
    ``[115, 101, ...]``.  This test fails on that observed behaviour specifically,
    so a partial regression that merely moved the bypass is still caught.
    """

    system, received = _watching_system()

    try:
        result = system.publish(
            "message.received",
            {
                "request_id": "req-v4-binary-shape",
                "channel": "conversation",
                "supporting_domains": BINARY_BUFFER,
            },
            event_id="evt-v4-binary-shape",
        )
    except REJECTIONS as exc:
        _assert_nothing_reached_persistence(system, received)
        assert "binary" in str(exc)
        return

    accepted = list(result.event.payload.data.get("supporting_domains", []))
    assert accepted != BINARY_BUFFER_AS_INTEGERS, (
        "memoryview binary was transformed into an integer array and accepted"
    )
    pytest.fail("memoryview binary was accepted into canonical payload content")


def test_nested_payload_memoryview_is_rejected_before_persistence() -> None:
    """MAJOR-V4-001: a ``memoryview`` nested in a mapping is still binary."""

    system, received = _watching_system()

    with pytest.raises(REJECTIONS):
        system.publish(
            "message.received",
            {
                "request_id": "req-v4-nested-binary",
                "result_reference": {"sequence": [BINARY_BUFFER]},
            },
            event_id="evt-v4-nested-binary",
        )

    _assert_nothing_reached_persistence(system, received)


def test_payload_memoryview_is_rejected_before_durable_append(tmp_path: Path) -> None:
    """MAJOR-V4-001: the binary byte values must never reach the durable JSONL."""

    store = _durable_store(tmp_path)
    system, received = _file_backed_system(store)

    with pytest.raises(REJECTIONS):
        system.publish(
            "message.received",
            {
                "request_id": "req-v4-binary-durable",
                "channel": "conversation",
                "supporting_domains": BINARY_BUFFER,
            },
            event_id="evt-v4-binary-durable",
        )

    durable = store.read_bytes() if store.exists() else b""
    assert b"115, 101, 99, 114, 101, 116, 45, 98, 105, 110, 97, 114, 121" not in durable
    assert received == []
    assert system.repository.count() == 0
    assert system.dead_letter_count() == 0


def test_metadata_top_level_memoryview_is_rejected_before_persistence() -> None:
    """MAJOR-V4-001: persisted ``metadata`` classifies ``memoryview`` as binary."""

    system, received = _watching_system()
    event = manual_event(
        "message.received",
        {"request_id": "req-v4-meta-binary"},
        event_id="evt-v4-meta-binary",
        metadata={"value": BINARY_BUFFER},
    )

    with pytest.raises(REJECTIONS):
        system.publish_event(event)

    _assert_nothing_reached_persistence(system, received)


def test_nested_metadata_memoryview_is_rejected_before_persistence() -> None:
    """MAJOR-V4-001: a nested ``memoryview`` in ``metadata`` is still binary."""

    system, received = _watching_system()
    event = manual_event(
        "message.received",
        {"request_id": "req-v4-meta-nested-binary"},
        event_id="evt-v4-meta-nested-binary",
        metadata={"outer": {"inner": [BINARY_BUFFER]}},
    )

    with pytest.raises(REJECTIONS):
        system.publish_event(event)

    _assert_nothing_reached_persistence(system, received)


def test_manual_publish_event_memoryview_never_becomes_an_integer_array() -> None:
    """MAJOR-V4-001: the audited metadata bypass must not emit integer arrays."""

    system, received = _watching_system()
    event = manual_event(
        "message.received",
        {"request_id": "req-v4-meta-shape"},
        event_id="evt-v4-meta-shape",
        metadata={"value": BINARY_BUFFER},
    )

    try:
        result = system.publish_event(event)
    except REJECTIONS:
        _assert_nothing_reached_persistence(system, received)
        return

    accepted = list(dict(result.event.header.metadata).get("value", []))
    assert accepted != BINARY_BUFFER_AS_INTEGERS, (
        "memoryview binary was transformed into an integer array and accepted"
    )
    pytest.fail("memoryview binary was accepted into canonical metadata content")


def test_memoryview_is_not_an_approved_permissions_container() -> None:
    """MAJOR-V4-001: a binary buffer is not a sequence of permission identifiers."""

    system, received = _watching_system()
    event = manual_event(
        "message.received",
        {"request_id": "req-v4-perm-binary"},
        event_id="evt-v4-perm-binary",
        permissions=BINARY_BUFFER,
    )

    with pytest.raises(REJECTIONS):
        system.publish_event(event)

    _assert_nothing_reached_persistence(system, received)


# ══════════════════════════════════════════════════════════════════════════
# MAJOR-V4-002 — manual ``publish_event()`` sensitivity is canonicalized
# ══════════════════════════════════════════════════════════════════════════


def test_manual_publish_event_normalizes_sensitivity_string_in_memory() -> None:
    """MAJOR-V4-002: the in-memory repository must store the canonical enum."""

    system = build_system(repository=InMemoryAgentRuntimeEventRepository())
    event = manual_event(
        "message.received",
        {"request_id": "req-v4-sensitivity"},
        event_id="evt-v4-sensitivity",
        sensitivity="restricted",
    )

    result = system.publish_event(event)

    assert result.event.header.sensitivity is EventSensitivity.RESTRICTED
    stored = system.repository.get("evt-v4-sensitivity")
    assert stored is not None
    assert stored.header.sensitivity is EventSensitivity.RESTRICTED


def test_manual_publish_event_normalizes_sensitivity_string_file_backed(
    tmp_path: Path,
) -> None:
    """MAJOR-V4-002: the durable repository must not raise ``AttributeError``."""

    store = _durable_store(tmp_path)
    system = build_system(
        repository_factory=lambda: FileAgentRuntimeEventRepository(store)
    )
    event = manual_event(
        "message.received",
        {"request_id": "req-v4-sensitivity-durable"},
        event_id="evt-v4-sensitivity-durable",
        sensitivity="restricted",
    )

    result = system.publish_event(event)

    assert result.event.header.sensitivity is EventSensitivity.RESTRICTED
    reopened = system.repository.get("evt-v4-sensitivity-durable")
    assert reopened is not None
    assert reopened.header.sensitivity is EventSensitivity.RESTRICTED

    durable = json.loads(store.read_text(encoding="utf-8").splitlines()[0])
    assert durable["header"]["sensitivity"] == "restricted"


def test_manual_publish_event_sensitivity_is_repository_independent(
    tmp_path: Path,
) -> None:
    """MAJOR-V4-002: both official repositories must agree on one semantics.

    This is the exact divergence the independent re-audit reported: the same
    public call succeeded in memory and crashed for the durable repository.
    """

    store = _durable_store(tmp_path)
    in_memory = build_system(repository=InMemoryAgentRuntimeEventRepository())
    file_backed = build_system(
        repository_factory=lambda: FileAgentRuntimeEventRepository(store)
    )

    memory_result = in_memory.publish_event(
        manual_event(
            "message.received",
            {"request_id": "req-v4-parity"},
            event_id="evt-v4-parity",
            sensitivity="restricted",
        )
    )
    durable_result = file_backed.publish_event(
        manual_event(
            "message.received",
            {"request_id": "req-v4-parity"},
            event_id="evt-v4-parity",
            sensitivity="restricted",
        )
    )

    assert (
        memory_result.event.header.sensitivity
        is durable_result.event.header.sensitivity
        is EventSensitivity.RESTRICTED
    )
    assert memory_result.outcome == durable_result.outcome


def test_manual_publish_event_accepts_canonical_enum_control(tmp_path: Path) -> None:
    """MAJOR-V4-002 control: an already-canonical enum keeps working everywhere."""

    store = _durable_store(tmp_path)
    systems = (
        ("in_memory", build_system(repository=InMemoryAgentRuntimeEventRepository())),
        (
            "file_backed",
            build_system(
                repository_factory=lambda: FileAgentRuntimeEventRepository(store)
            ),
        ),
    )
    for label, system in systems:
        result = system.publish_event(
            manual_event(
                "message.received",
                {"request_id": f"req-v4-enum-{label}"},
                event_id=f"evt-v4-enum-{label}",
                sensitivity=EventSensitivity.RESTRICTED,
            )
        )
        assert result.event.header.sensitivity is EventSensitivity.RESTRICTED


def test_manual_publish_event_sensitivity_matches_create_event_identity() -> None:
    """MAJOR-V4-002: normalizing the string must not change content identity."""

    system = build_system()

    string_result = system.publish_event(
        manual_event(
            "message.received",
            {"request_id": "req-v4-fingerprint"},
            event_id="evt-v4-fingerprint",
            sensitivity="restricted",
        )
    )
    created = system.create_event(
        "message.received",
        {"request_id": "req-v4-fingerprint"},
        event_id="evt-v4-fingerprint",
        sensitivity=EventSensitivity.RESTRICTED,
        source="agent_runtime",
        occurred_at=MOMENT,
        emitted_at=MOMENT,
    )

    assert event_fingerprint(string_result.event) == event_fingerprint(created)


def test_manual_publish_event_does_not_mutate_the_caller_event() -> None:
    """MAJOR-V4-002: normalization returns a canonical copy, not aliased state."""

    system = build_system()
    event = manual_event(
        "message.received",
        {"request_id": "req-v4-alias"},
        event_id="evt-v4-alias",
        sensitivity="restricted",
    )

    result = system.publish_event(event)

    assert event.header.sensitivity == "restricted"
    assert result.event.header.sensitivity is EventSensitivity.RESTRICTED
    assert result.event is not event


# ══════════════════════════════════════════════════════════════════════════
# MAJOR-V4-003 — bounded safe DLQ error category
# ══════════════════════════════════════════════════════════════════════════

#: The neutral bounded category the safe derivation falls back to.
NEUTRAL_ERROR_CATEGORY = "SubscriberDeliveryError"


def _failing_system(
    exception_class: type[BaseException], attempts: int = 2
) -> EventSystem:
    """Return a system whose only subscriber always raises *exception_class*."""

    system = build_system(max_delivery_attempts=attempts)

    def failing(event: AgentRuntimeEvent) -> None:
        raise exception_class("subscriber exploded")

    system.subscribe(failing, ["message.received"])
    system.publish(
        "message.received",
        {"request_id": "req-v4-dlq"},
        event_id="evt-v4-dlq",
        occurred_at=MOMENT,
        emitted_at=MOMENT,
    )
    return system


def _dlq_rendering(system: EventSystem) -> str:
    """Return every DLQ-facing field of every entry as one scannable string."""

    entries = system.list_dead_letters()
    assert entries, "expected a dead letter to be recorded"
    return json.dumps(
        [
            {
                "error": entry.error,
                "error_type": entry.error_type,
                "handler_name": entry.handler_name,
                "subscription_id": entry.subscription_id,
                "metadata": dict(entry.metadata),
                "event_header": {
                    "event_id": entry.event.header.event_id,
                    "event_type": entry.event.header.event_type,
                },
            }
            for entry in entries
        ]
    )


def test_credential_bearing_exception_class_name_never_reaches_dlq() -> None:
    """MAJOR-V4-003: the exact audited credential leak must be closed."""

    credential_exception = type(CREDENTIAL_CLASS_NAME, (Exception,), {})
    system = _failing_system(credential_exception)

    rendered = _dlq_rendering(system)

    assert "abcdef1234567890" not in rendered
    assert "api_key" not in rendered
    assert CREDENTIAL_CLASS_NAME not in rendered
    for entry in system.list_dead_letters():
        assert entry.error_type != CREDENTIAL_CLASS_NAME
        assert entry.error != CREDENTIAL_CLASS_NAME


def test_private_marker_exception_class_name_never_reaches_dlq() -> None:
    """MAJOR-V4-003: a private-marker class name is also refused."""

    private_exception = type(PRIVATE_MARKER_CLASS_NAME, (Exception,), {})
    system = _failing_system(private_exception)

    rendered = _dlq_rendering(system)

    assert "TOP SECRET" not in rendered
    assert "system_prompt" not in rendered
    assert PRIVATE_MARKER_CLASS_NAME not in rendered


def test_ordinary_exception_class_name_stays_usefully_categorized() -> None:
    """MAJOR-V4-003 control: a normal exception keeps its bounded category."""

    system = _failing_system(RuntimeError)

    entry = system.list_dead_letters()[0]

    assert entry.error_type == "RuntimeError"
    assert entry.error == "RuntimeError"
    assert "subscriber exploded" not in _dlq_rendering(system)


def test_credential_bearing_class_name_is_neutralized_not_mangled() -> None:
    """MAJOR-V4-003: the fallback is a bounded neutral category, not a fragment."""

    credential_exception = type(CREDENTIAL_CLASS_NAME, (Exception,), {})
    system = _failing_system(credential_exception)

    entry = system.list_dead_letters()[0]

    assert entry.error_type == NEUTRAL_ERROR_CATEGORY
    assert entry.error == NEUTRAL_ERROR_CATEGORY
    assert entry.attempts == 2


def test_unbounded_exception_class_name_is_neutralized() -> None:
    """MAJOR-V4-003: an unbounded class name is refused as a category."""

    unbounded_exception = type("E" * 5000, (Exception,), {})
    system = _failing_system(unbounded_exception)

    entry = system.list_dead_letters()[0]

    assert entry.error_type == NEUTRAL_ERROR_CATEGORY
    assert len(entry.error_type) <= 128


def test_replay_failure_path_never_reports_an_unsafe_class_name() -> None:
    """MAJOR-V4-003: the replay-delivery failure metadata uses the safe category."""

    credential_exception = type(CREDENTIAL_CLASS_NAME, (Exception,), {})
    system = build_system(max_delivery_attempts=1)
    system.publish(
        "message.received",
        {"request_id": "req-v4-replay-dlq"},
        event_id="evt-v4-replay-dlq",
        occurred_at=MOMENT,
        emitted_at=MOMENT,
    )

    def failing(event: AgentRuntimeEvent) -> None:
        raise credential_exception("subscriber exploded")

    system.subscribe(failing, ["message.received"], accept_replay=True)

    observed: list[AgentRuntimeEventDelivery] = []
    original = system.bus._deliver_replay_to_subscriber

    def spy(event: AgentRuntimeEvent, record: Any) -> AgentRuntimeEventDelivery:
        delivery = original(event, record)
        observed.append(delivery)
        return delivery

    system.bus._deliver_replay_to_subscriber = spy  # type: ignore[method-assign]

    result = system.replay(AgentRuntimeEventReplayRequest())

    assert result.failed_count == 1
    assert observed, "expected the replay delivery to be observed"
    rendered = json.dumps(
        [
            {"metadata": dict(delivery.metadata), "error": delivery.error}
            for delivery in observed
        ]
    )
    assert "api_key" not in rendered
    assert "abcdef1234567890" not in rendered
    assert NEUTRAL_ERROR_CATEGORY in rendered


def test_publish_event_closes_memoryview_and_sensitivity_together() -> None:
    """MAJOR-V4-001/002: the public boundary closes both V4 gaps at once."""

    system, received = _watching_system()
    event = manual_event(
        "message.received",
        {"request_id": "req-v4-combined", "supporting_domains": BINARY_BUFFER},
        event_id="evt-v4-combined",
        sensitivity="restricted",
        metadata={"value": BINARY_BUFFER},
    )

    with pytest.raises(REJECTIONS):
        system.publish_event(event)

    _assert_nothing_reached_persistence(system, received)
