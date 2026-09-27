"""Phase 11.22 — Remediation V3 adversarial regressions.

These tests make the independent Re-audit V3 reproductions executable and
permanent.  Each V3 finding gets its own named test; no finding is hidden inside
another test's assertions.

Covered findings::

    MAJOR-V3-001  persisted metadata accepts opaque/binary/non-finite values,
                  ``sensitivity`` is not runtime-type validated and a plain-string
                  ``permissions`` value is coerced into a character list
    MAJOR-V3-002  safe structured payloads crash or drift shape across the
                  durable live/reopen boundary, and nested caller aliases survive
                  into ``PublicationResult.event``
    MINOR-V3-001  dead-letter inspection APIs return mutable nested aliases

Every test here is adversarial: it reproduces the exact behaviour the independent
re-audit V3 reported, so it must fail before the remediation and pass after it.

All three findings are exercised through real components — the public
``EventSystem`` facade, the canonical factory/registry/repository/bus, the real
file-backed durable repository and the real ``PlatformOrchestrationEventSink``.
"""

from __future__ import annotations

import copy
import math
from datetime import datetime, timezone
from pathlib import Path

import pytest

from cmm.agent_runtime.runtime_event_contracts import (
    AgentRuntimeEvent,
    AgentRuntimeEventHeader,
    AgentRuntimeEventPayload,
    EventSensitivity,
)
from cmm.agent_runtime.runtime_event_factory import event_fingerprint
from cmm.agent_runtime.runtime_event_repository import (
    FileAgentRuntimeEventRepository,
)
from cmm.events.event_payload_safety import PlatformEventPayloadError
from cmm.events.event_system import EventSystem
from cmm.events.orchestration_adapter import PlatformOrchestrationEventSink
from tests.events.test_phase11_22_event_system import build_system

MOMENT = datetime(2026, 9, 27, 12, 0, 0, tzinfo=timezone.utc)

#: The credential string the mandatory MAJOR-V3-001 adversarial object emits.
CREDENTIAL_VALUE = "api_key=abcdef1234567890"

#: A private-marker string that must never reach a persisted field.
PRIVATE_MARKER_VALUE = "system_prompt=TOP SECRET"


class SecretObject:
    """An opaque runtime object whose string form is a credential.

    Re-audit V3 proved that this object in ``metadata`` reached ``json.dumps`` and
    the durable JSONL contained ``api_key=abcdef1234567890``.  Its whole purpose is
    to prove the opaque-value gate fails closed *before* serialization.
    """

    def __str__(self) -> str:
        return CREDENTIAL_VALUE

    def __repr__(self) -> str:
        return "<SecretObject>"


def manual_event(
    event_type: str,
    payload: dict,
    *,
    event_id: str = "evt-v3-manual",
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


def _file_backed_system(tmp_path: Path) -> tuple[EventSystem, Path]:
    """Return a real file-backed event system and its durable store path."""

    store = tmp_path / "data" / "events" / "runtime_events.jsonl"
    system = EventSystem(
        registry=build_system().registry,
        repository=FileAgentRuntimeEventRepository(store),
        bus=build_system().bus,
    )
    return system, store


def _file_backed_watching_system(
    store: Path,
) -> tuple[EventSystem, list[AgentRuntimeEvent]]:
    """Return a file-backed system plus the events one subscriber received."""

    system = build_system(
        repository_factory=lambda: FileAgentRuntimeEventRepository(store)
    )
    received: list[AgentRuntimeEvent] = []
    system.subscribe(received.append, ["message.received"])
    return system, received


def _watching_system():
    """Return a system, the events a subscriber received, and its repository."""

    system = build_system()
    received: list[AgentRuntimeEvent] = []
    system.subscribe(received.append, ["message.received"])
    return system, received, system.repository


def _assert_nothing_reached_persistence(
    system: EventSystem, received: list[AgentRuntimeEvent]
) -> None:
    """Prove the refusal happened before persistence and before delivery."""

    assert received == []
    assert system.repository.count() == 0
    assert system.bus.stats.published_total == 0
    assert system.dead_letter_count() == 0


# ══════════════════════════════════════════════════════════════════════════
# MAJOR-V3-001 — persisted header facts must be content *and* type safe
# ══════════════════════════════════════════════════════════════════════════

#: Re-audit V3 accepted every one of these opaque/binary/non-finite values.
UNSAFE_METADATA_VALUES = (
    ("opaque_object", object()),
    ("bytes", b"abc"),
    ("bytearray", bytearray(b"abc")),
    ("nan", float("nan")),
    ("positive_inf", float("inf")),
    ("negative_inf", float("-inf")),
    ("nested_opaque", {"nested": {"deeper": object()}}),
    ("nested_bytes", [b"abc"]),
    ("nested_nan", {"nested": [float("nan")]}),
)


@pytest.mark.parametrize(
    ("label", "value"),
    UNSAFE_METADATA_VALUES,
    ids=[case[0] for case in UNSAFE_METADATA_VALUES],
)
def test_unsafe_metadata_value_is_rejected_before_persistence(
    label: str, value: object
) -> None:
    """MAJOR-V3-001 gap A: metadata must be a JSON-safe descriptive value."""

    system, received, _repository = _watching_system()

    with pytest.raises((PlatformEventPayloadError, TypeError, ValueError)):
        system.publish(
            "message.received",
            {"request_id": "req-v3-metadata"},
            event_id="evt-v3-metadata",
            metadata={"value": value},
        )

    _assert_nothing_reached_persistence(system, received)


def test_secret_object_is_rejected_before_durable_append(tmp_path: Path) -> None:
    """MAJOR-V3-001 gap B: ``SecretObject`` must never reach durable storage.

    This is the mandatory Remediation V3 adversarial regression.  It uses the real
    file-backed durable repository with **no** subscriber, because that is the exact
    configuration in which the independent re-audit observed an accepted
    publication whose ``__str__()`` credential became persisted evidence.
    """

    store = tmp_path / "data" / "events" / "runtime_events.jsonl"
    system = build_system(
        repository_factory=lambda: FileAgentRuntimeEventRepository(store)
    )

    with pytest.raises((PlatformEventPayloadError, TypeError, ValueError)):
        system.publish(
            "message.received",
            {"request_id": "req-v3-opaque"},
            event_id="evt-v3-opaque",
            metadata={"inner": SecretObject()},
        )

    durable = store.read_bytes() if store.exists() else b""
    assert CREDENTIAL_VALUE.encode() not in durable
    assert system.repository.count() == 0
    assert system.bus.stats.published_total == 0


def test_secret_object_credential_never_reaches_durable_jsonl(tmp_path: Path) -> None:
    """MAJOR-V3-001 gap B: the credential must not survive serialization at all."""

    store = tmp_path / "data" / "events" / "runtime_events.jsonl"
    system, received = _file_backed_watching_system(store)

    with pytest.raises((PlatformEventPayloadError, TypeError, ValueError)):
        system.publish(
            "message.received",
            {"request_id": "req-v3-opaque-durable"},
            event_id="evt-v3-opaque-durable",
            metadata={"inner": SecretObject()},
        )

    durable = store.read_bytes() if store.exists() else b""
    assert CREDENTIAL_VALUE.encode() not in durable
    assert received == []
    assert system.repository.count() == 0
    assert system.dead_letter_count() == 0


def test_secret_object_in_payload_data_is_rejected_before_persistence() -> None:
    """MAJOR-V3-001 gap B: the same opaque object is refused in ``payload.data``."""

    system, received, _repository = _watching_system()

    with pytest.raises((PlatformEventPayloadError, TypeError, ValueError)):
        system.publish(
            "message.received",
            {"request_id": "req-v3-opaque-payload", "status": SecretObject()},
            event_id="evt-v3-opaque-payload",
        )

    _assert_nothing_reached_persistence(system, received)


#: Re-audit V3 accepted ``sensitivity`` values that are not a canonical enum.
INVALID_SENSITIVITY_VALUES = (
    ("integer", 123),
    ("none", None),
    ("credential_string", CREDENTIAL_VALUE),
    ("private_marker_string", PRIVATE_MARKER_VALUE),
    ("unknown_string", "definitely-not-a-sensitivity"),
    ("arbitrary_object", object()),
)


@pytest.mark.parametrize(
    ("label", "value"),
    INVALID_SENSITIVITY_VALUES,
    ids=[case[0] for case in INVALID_SENSITIVITY_VALUES],
)
def test_non_canonical_sensitivity_is_rejected_before_persistence(
    label: str, value: object
) -> None:
    """MAJOR-V3-001 gap C: ``sensitivity`` must be the canonical runtime type."""

    system, received, _repository = _watching_system()

    with pytest.raises((PlatformEventPayloadError, TypeError, ValueError)):
        system.publish(
            "message.received",
            {"request_id": "req-v3-sensitivity"},
            event_id="evt-v3-sensitivity",
            sensitivity=value,
        )

    _assert_nothing_reached_persistence(system, received)


def test_supported_sensitivity_string_is_normalized_to_the_enum() -> None:
    """MAJOR-V3-001 gap C: the one supported string form canonicalizes safely.

    A legitimate ``"restricted"`` spelling is the single explicitly supported
    string normalization; it must be converted to :class:`EventSensitivity` before
    the event is constructed, so no persisted fact is ever a bare ``str``.
    """

    system, received, _repository = _watching_system()

    result = system.publish(
        "message.received",
        {"request_id": "req-v3-sensitivity-ok"},
        event_id="evt-v3-sensitivity-ok",
        sensitivity="restricted",
    )

    assert result.event.header.sensitivity is EventSensitivity.RESTRICTED
    assert len(received) == 1
    assert received[0].header.sensitivity is EventSensitivity.RESTRICTED


@pytest.mark.parametrize(
    "value",
    list(EventSensitivity),
    ids=[member.name for member in EventSensitivity],
)
def test_canonical_sensitivity_enum_is_preserved(value: EventSensitivity) -> None:
    """MAJOR-V3-001 control: every canonical enum member still publishes."""

    system, received, _repository = _watching_system()

    result = system.publish(
        "message.received",
        {"request_id": "req-v3-sensitivity-enum"},
        event_id="evt-v3-sensitivity-enum",
        sensitivity=value,
    )

    assert result.event.header.sensitivity is value
    assert received[0].header.sensitivity is value


def test_plain_string_permissions_is_rejected_not_coerced() -> None:
    """MAJOR-V3-001: ``permissions="admin"`` must not become a character list."""

    system, received, _repository = _watching_system()

    with pytest.raises((PlatformEventPayloadError, TypeError, ValueError)):
        system.publish(
            "message.received",
            {"request_id": "req-v3-permissions"},
            event_id="evt-v3-permissions",
            permissions="admin",
        )

    _assert_nothing_reached_persistence(system, received)


def test_bytes_permissions_container_is_rejected() -> None:
    """MAJOR-V3-001: a binary permissions container is not a permission sequence."""

    system, received, _repository = _watching_system()

    with pytest.raises((PlatformEventPayloadError, TypeError, ValueError)):
        system.publish(
            "message.received",
            {"request_id": "req-v3-permissions-bytes"},
            event_id="evt-v3-permissions-bytes",
            permissions=b"events:read",
        )

    _assert_nothing_reached_persistence(system, received)


def test_valid_permission_sequence_still_publishes() -> None:
    """MAJOR-V3-001 control: legitimate permissions remain valid."""

    system, received, _repository = _watching_system()

    result = system.publish(
        "message.received",
        {"request_id": "req-v3-permissions-ok"},
        event_id="evt-v3-permissions-ok",
        permissions=["events:read", "events:write"],
    )

    assert result.event.header.permissions == ["events:read", "events:write"]
    assert received[0].header.permissions == ["events:read", "events:write"]


def test_direct_publish_event_rejects_unsafe_metadata_types() -> None:
    """MAJOR-V3-001: the manual publication boundary applies the same gate."""

    system, received, _repository = _watching_system()

    with pytest.raises((PlatformEventPayloadError, TypeError, ValueError)):
        system.publish_event(
            manual_event(
                "message.received",
                {"request_id": "req-v3-manual"},
                event_id="evt-v3-manual-unsafe",
                metadata={"inner": SecretObject()},
            )
        )

    _assert_nothing_reached_persistence(system, received)


def test_direct_publish_event_rejects_non_canonical_sensitivity() -> None:
    """MAJOR-V3-001: the manual publication boundary enforces sensitivity type."""

    system, received, _repository = _watching_system()

    with pytest.raises((PlatformEventPayloadError, TypeError, ValueError)):
        system.publish_event(
            manual_event(
                "message.received",
                {"request_id": "req-v3-manual-sensitivity"},
                event_id="evt-v3-manual-sensitivity",
                sensitivity=CREDENTIAL_VALUE,  # type: ignore[arg-type]
            )
        )

    _assert_nothing_reached_persistence(system, received)


def test_finite_metadata_numbers_and_nesting_still_publish() -> None:
    """MAJOR-V3-001 control: finite scalars and safe nesting remain valid.

    Remediation V5 clarifies the stable half of this control: finite scalars and
    safe JSON-compatible nesting are still valid, but they are carried by the
    declared bounded lifecycle metadata vocabulary rather than by an arbitrary
    invented key.  The bounded container is the documented ``detail`` fact.
    """

    system, received, _repository = _watching_system()

    result = system.publish(
        "message.received",
        {"request_id": "req-v3-safe-metadata"},
        event_id="evt-v3-safe-metadata",
        metadata={
            "attempt": 2,
            "ratio": 0.5,
            "flag": True,
            "label": "ok",
            "detail": {"inner": ["a", 1, None]},
        },
    )

    assert result.event.header.metadata["detail"] == {"inner": ["a", 1, None]}
    assert math.isfinite(result.event.header.metadata["ratio"])
    assert received[0].header.metadata["attempt"] == 2


# ══════════════════════════════════════════════════════════════════════════
# MAJOR-V3-002 — stable canonical structured-payload normalization
# ══════════════════════════════════════════════════════════════════════════


def test_nested_result_reference_mapping_publishes() -> None:
    """MAJOR-V3-002 problem A: a nested ``result_reference`` must not crash."""

    system, received, _repository = _watching_system()

    result = system.publish(
        "message.received",
        {
            "request_id": "req-v3-result-reference",
            "result_reference": {"reference_id": "ref-1"},
        },
        event_id="evt-v3-result-reference",
    )

    assert result.persisted is True
    assert result.event.payload.data["result_reference"] == {"reference_id": "ref-1"}
    assert received[0].payload.data["result_reference"] == {"reference_id": "ref-1"}


def test_nested_approval_refs_mapping_list_publishes() -> None:
    """MAJOR-V3-002 problem A: a nested ``approval_refs`` must not crash."""

    system, received, _repository = _watching_system()

    result = system.publish(
        "message.received",
        {
            "request_id": "req-v3-approval-refs",
            "approval_refs": [{"approval_id": "app-1"}],
        },
        event_id="evt-v3-approval-refs",
    )

    assert result.persisted is True
    assert result.event.payload.data["approval_refs"] == [{"approval_id": "app-1"}]
    assert received[0].payload.data["approval_refs"] == [{"approval_id": "app-1"}]


def test_nested_payload_values_are_plain_json_compatible_containers() -> None:
    """MAJOR-V3-002: no frozen view reaches the canonical event factory."""

    import json

    system, _received, _repository = _watching_system()

    result = system.publish(
        "message.received",
        {
            "request_id": "req-v3-json-shape",
            "result_reference": {"reference_id": "ref-1"},
            "approval_refs": [{"approval_id": "app-1"}],
            "supporting_domains": ["domain:legal"],
        },
        event_id="evt-v3-json-shape",
    )

    data = result.event.payload.data
    assert type(data["result_reference"]) is dict
    assert type(data["approval_refs"]) is list
    assert type(data["approval_refs"][0]) is dict
    assert type(data["supporting_domains"]) is list
    # The canonical payload is genuinely JSON-serializable without ``default=str``.
    json.dumps(data)


def test_supporting_domains_shape_is_stable_across_durable_reopen(
    tmp_path: Path,
) -> None:
    """MAJOR-V3-002 problem B: live and reopened sequence shapes must match."""

    system, store = _file_backed_system(tmp_path)

    result = system.publish(
        "message.received",
        {
            "request_id": "req-v3-sequence-shape",
            "supporting_domains": ("domain:legal", "domain:health"),
        },
        event_id="evt-v3-sequence-shape",
    )

    live = result.event
    reopened = FileAgentRuntimeEventRepository(store).get("evt-v3-sequence-shape")

    assert reopened is not None
    assert type(live.payload.data["supporting_domains"]) is type(
        reopened.payload.data["supporting_domains"]
    )
    assert live.payload.data == reopened.payload.data
    assert live == reopened
    assert event_fingerprint(live) == event_fingerprint(reopened)


def test_live_and_reopened_header_facts_match(tmp_path: Path) -> None:
    """MAJOR-V3-002: the whole canonical event survives a durable reopen equal."""

    system, store = _file_backed_system(tmp_path)

    result = system.publish(
        "message.received",
        {
            "request_id": "req-v3-live-reopen",
            "supporting_domains": ["domain:legal"],
            "result_reference": {"reference_id": "ref-1"},
        },
        event_id="evt-v3-live-reopen",
        metadata={"detail": {"inner": [1, "two"]}},
        permissions=["events:read"],
    )

    live = result.event
    reopened = FileAgentRuntimeEventRepository(store).get("evt-v3-live-reopen")

    assert reopened is not None
    assert live == reopened
    assert event_fingerprint(live) == event_fingerprint(reopened)


def test_real_orchestration_supporting_domains_round_trip_is_equal(
    tmp_path: Path,
) -> None:
    """MAJOR-V3-002: the real production sink satisfies the round-trip invariant."""

    system, store = _file_backed_system(tmp_path)
    sink = PlatformOrchestrationEventSink(system)

    event_id = sink.emit(
        "orchestration.domain_resolved",
        request_id="req-v3-orchestration",
        payload={
            "primary_domain": "domain:legal",
            "supporting_domains": ("domain:legal", "domain:health"),
            "status": "resolved",
        },
    )

    assert event_id is not None
    live = system.repository.get(event_id)
    reopened = FileAgentRuntimeEventRepository(store).get(event_id)

    assert live is not None
    assert reopened is not None
    assert type(live.payload.data["supporting_domains"]) is type(
        reopened.payload.data["supporting_domains"]
    )
    assert live.payload.data["supporting_domains"] == [
        "domain:legal",
        "domain:health",
    ]
    assert live == reopened
    assert event_fingerprint(live) == event_fingerprint(reopened)


def test_nested_caller_mutation_cannot_change_publication_result() -> None:
    """MAJOR-V3-002 problem C: nested caller aliases must not survive publication."""

    system, _received, repository = _watching_system()
    caller_list = ["domain:a"]
    caller_nested = {"reference_id": "ref-1"}
    caller_meta = {"detail": {"inner": ["x"]}}

    event = manual_event(
        "message.received",
        {
            "request_id": "req-v3-alias",
            "supporting_domains": caller_list,
            "result_reference": caller_nested,
        },
        event_id="evt-v3-alias",
        metadata=caller_meta,
    )

    result = system.publish_event(event)

    caller_list.append("domain:b")
    caller_nested["reference_id"] = "mutated"
    caller_meta["detail"]["inner"].append("y")

    assert result.event.payload.data["supporting_domains"] == ["domain:a"]
    assert result.event.payload.data["result_reference"] == {"reference_id": "ref-1"}
    assert result.event.header.metadata == {"detail": {"inner": ["x"]}}
    stored = repository.get("evt-v3-alias")
    assert stored is not None
    assert stored.payload.data["supporting_domains"] == ["domain:a"]
    assert event_fingerprint(stored) == event_fingerprint(result.event)


def test_publish_does_not_retain_alias_to_caller_payload() -> None:
    """MAJOR-V3-002 problem C: the ``publish`` path is alias-isolated too."""

    system, _received, repository = _watching_system()
    caller_list = ["domain:a"]
    caller_nested = {"reference_id": "ref-1"}

    result = system.publish(
        "message.received",
        {
            "request_id": "req-v3-alias-publish",
            "supporting_domains": caller_list,
            "result_reference": caller_nested,
        },
        event_id="evt-v3-alias-publish",
    )

    caller_list.append("domain:b")
    caller_nested["reference_id"] = "mutated"

    assert result.event.payload.data["supporting_domains"] == ["domain:a"]
    assert result.event.payload.data["result_reference"] == {"reference_id": "ref-1"}
    stored = repository.get("evt-v3-alias-publish")
    assert stored is not None
    assert stored.payload.data == result.event.payload.data


def test_nested_forbidden_content_is_still_rejected() -> None:
    """MAJOR-V3-002 control: canonicalization must not loosen content safety."""

    system, received, _repository = _watching_system()

    with pytest.raises((PlatformEventPayloadError, TypeError, ValueError)):
        system.publish(
            "message.received",
            {
                "request_id": "req-v3-nested-forbidden",
                "result_reference": {"reference_id": CREDENTIAL_VALUE},
            },
            event_id="evt-v3-nested-forbidden",
        )

    _assert_nothing_reached_persistence(system, received)


def test_nested_opaque_value_is_rejected_not_stringified() -> None:
    """MAJOR-V3-002 control: nested opaque values fail closed, never stringify."""

    system, received, _repository = _watching_system()

    with pytest.raises((PlatformEventPayloadError, TypeError, ValueError)):
        system.publish(
            "message.received",
            {
                "request_id": "req-v3-nested-opaque",
                "result_reference": {"reference_id": SecretObject()},
            },
            event_id="evt-v3-nested-opaque",
        )

    _assert_nothing_reached_persistence(system, received)


# ══════════════════════════════════════════════════════════════════════════
# MINOR-V3-001 — dead-letter snapshots must really be detached
# ══════════════════════════════════════════════════════════════════════════


def _dead_lettered_system():
    """Return a system with exactly one retained dead letter for subscriber A."""

    system = build_system(max_delivery_attempts=2)

    def failing(event: AgentRuntimeEvent) -> None:
        raise RuntimeError("subscriber failed")

    subscription_id = system.subscribe(failing, ["message.received"])

    system.publish(
        "message.received",
        {"request_id": "req-v3-dlq", "supporting_domains": ["domain:a"]},
        event_id="evt-v3-dlq",
        metadata={"origin": "original"},
    )

    assert system.dead_letter_count() == 1
    return system, subscription_id


def _tamper(entry) -> None:
    """Attempt to mutate every nested container a dead letter exposes.

    The mutation is structural rather than value-specific, so it applies to any
    retained event: an existing nested sequence is extended when present, otherwise
    a new nested fact is injected.  A detached snapshot absorbs all of it; the
    queue's retained evidence does not.
    """

    payload = entry.event.payload.data
    for value in payload.values():
        if isinstance(value, list):
            value.append("domain:tampered")
            break
    else:
        payload["injected"] = "tampered"
    payload["request_id"] = "tampered"
    entry.event.header.metadata["injected"] = "yes"
    entry.event.header.permissions.append("escalate")
    entry.metadata["injected"] = "yes"


def test_queue_get_returns_a_detached_dead_letter() -> None:
    """MINOR-V3-001: ``queue.get()`` must not expose the retained entry."""

    system, subscription_id = _dead_lettered_system()
    queue = system.dead_letters

    first = queue.get(0)
    before = copy.deepcopy(
        (
            first.event.payload.data,
            first.event.header.metadata,
            first.event.header.permissions,
            first.metadata,
            first.subscription_id,
            first.attempts,
        )
    )
    _tamper(first)

    second = queue.get(0)
    assert second.event.payload.data == before[0]
    assert second.event.header.metadata == before[1]
    assert second.event.header.permissions == before[2]
    assert second.metadata == before[3]
    assert second.subscription_id == subscription_id
    assert second.attempts == before[5]


def test_queue_list_returns_detached_dead_letters() -> None:
    """MINOR-V3-001: ``queue.list()`` must not expose the retained entries."""

    system, _subscription_id = _dead_lettered_system()
    queue = system.dead_letters

    first = queue.list()[0]
    _tamper(first)

    second = queue.list()[0]
    assert second.event.payload.data == {
        "request_id": "req-v3-dlq",
        "supporting_domains": ["domain:a"],
    }
    assert second.event.header.metadata == {"origin": "original"}
    assert second.event.header.permissions == []
    assert "injected" not in second.metadata


def test_event_system_list_dead_letters_returns_detached_snapshots() -> None:
    """MINOR-V3-001: ``EventSystem.list_dead_letters()`` must be a real snapshot."""

    system, _subscription_id = _dead_lettered_system()

    first = system.list_dead_letters()[0]
    _tamper(first)

    second = system.list_dead_letters()[0]
    assert second.event.payload.data == {
        "request_id": "req-v3-dlq",
        "supporting_domains": ["domain:a"],
    }
    assert second.event.header.metadata == {"origin": "original"}
    assert second.event.header.permissions == []
    assert "injected" not in second.metadata


def test_mutating_a_removed_dead_letter_does_not_change_later_evidence() -> None:
    """MINOR-V3-001: ``remove()`` must return a detached copy as well."""

    system, _subscription_id = _dead_lettered_system()
    queue = system.dead_letters

    removed = queue.remove(0)
    assert queue.count() == 0

    removed.event.payload.data["supporting_domains"].append("domain:tampered")
    removed.event.header.metadata["injected"] = "yes"
    removed.metadata["injected"] = "yes"

    system.publish(
        "message.received",
        {"request_id": "req-v3-dlq-2", "supporting_domains": ["domain:b"]},
        event_id="evt-v3-dlq-2",
        metadata={"origin": "second"},
    )

    assert queue.count() == 1
    fresh = queue.get(0)
    assert fresh.event.payload.data == {
        "request_id": "req-v3-dlq-2",
        "supporting_domains": ["domain:b"],
    }
    assert fresh.event.header.metadata == {"origin": "second"}
    assert fresh.event.payload.data.get("request_id") != "tampered"
    assert "injected" not in fresh.metadata
    assert "escalate" not in fresh.event.header.permissions


def test_detached_dlq_snapshots_preserve_targeted_replay() -> None:
    """MINOR-V3-001 control: detachment must not break targeted DLQ replay."""

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
        {"request_id": "req-v3-dlq-replay"},
        event_id="evt-v3-dlq-replay",
    )

    assert system.dead_letter_count() == 1
    entry = system.list_dead_letters()[0]
    assert entry.subscription_id == subscription_a

    # A caller tampers with its snapshot; retained evidence must be unaffected.
    _tamper(entry)
    assert system.list_dead_letters()[0].event.payload.data == {
        "request_id": "req-v3-dlq-replay"
    }

    state["fail"] = False
    result = system.replay_dead_letter(0)

    assert result.replayed_count == 1
    assert result.failed_count == 0
    assert len(a_calls) == 3
    assert len(b_calls) == 1
    assert system.dead_letter_count() == 0
