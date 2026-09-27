"""Phase 11.22 — Remediation V5 adversarial regressions.

These tests make the independent Re-audit V5 reproductions executable and
permanent.  Each V5 finding gets its own named test; no finding is hidden inside
another test's assertions.

Covered findings::

    MAJOR-V5-001  ``array.array`` is a compact binary buffer *and* an ordinary
                  Python sequence, so the pre-remediation binary classifier treated
                  it as a descriptive integer sequence and recursively
                  canonicalized its byte values into durable event content
    MAJOR-V5-002  an allowed key name bounded the *vocabulary* but not the *value
                  semantics*, so raw user prose could be relocated into
                  ``request_id``, ``status``, ``metadata`` or a boolean/numeric
                  field and persisted verbatim
    MAJOR-V5-003  the canonical ``AgentRuntimeEventBus`` bounded-retry/DLQ path was
                  only secret-safe when the optional external error categorizer had
                  been bound, so direct canonical use wrote an identifier-shaped
                  credential class name straight into DLQ ``error_type``/``error``

Every test here is adversarial: it reproduces the exact behaviour the independent
re-audit V5 reported, so it must fail before the remediation and pass after it.

All three findings are exercised through real canonical components — the public
``EventSystem`` facade, the canonical factory/registry/bus/DLQ, and both official
repository implementations (in-memory and file-backed).  Nothing is mocked.
"""

from __future__ import annotations

import array
import itertools
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from cmm.agent_runtime.runtime_event_bus import (
    AgentRuntimeEventBus,
    safe_delivery_error_type,
)
from cmm.agent_runtime.runtime_event_contracts import (
    AgentRuntimeEvent,
    AgentRuntimeEventHeader,
    AgentRuntimeEventPayload,
)
from cmm.agent_runtime.runtime_event_dead_letter import (
    InMemoryAgentRuntimeDeadLetterQueue,
)
from cmm.agent_runtime.runtime_event_factory import AgentRuntimeEventFactory
from cmm.agent_runtime.runtime_event_registry import AgentRuntimeEventRegistry
from cmm.agent_runtime.runtime_event_repository import (
    FileAgentRuntimeEventRepository,
)
from cmm.events.event_payload_safety import (
    ALLOWED_PAYLOAD_KEYS,
    PlatformEventPayloadError,
)
from cmm.events.event_system import EventSystem
from tests.events.test_phase11_22_event_system import build_system

MOMENT = datetime(2026, 9, 27, 12, 0, 0, tzinfo=timezone.utc)

#: A monotonic counter so a parametrized control case always gets a fresh,
#: plain-safe canonical event identity instead of deriving one from a key name.
_CONTROL_IDS = itertools.count()

REJECTIONS = (PlatformEventPayloadError, TypeError, ValueError)

#: The exact raw user sentence the independent re-audit V5 persisted as a
#: lifecycle fact by relocating it under an allowed key.
RAW_USER_TEXT = (
    "My landlord entered my flat without permission yesterday and I need legal advice."
)

#: The neutral bounded DLQ category the canonical transport must fall back to
#: when no external categorizer is bound.
NEUTRAL_ERROR_CATEGORY = "SubscriberDeliveryError"

#: The exact credential-shaped dynamic exception class name the independent
#: re-audit V5 used against the direct canonical bus DLQ path.
CREDENTIAL_CLASS_NAME = "api_key_abcdef1234567890"

#: A private-marker-bearing dynamic exception class name.  It is a valid Python
#: identifier (so the transport-local bounded-name half accepts it), and it
#: carries a forbidden private marker (so the content half must refuse it).
PRIVATE_MARKER_CLASS_NAME = "system_prompt_TOP_SECRET"


def _array_binary() -> array.array:
    """Return the exact ``array.array`` binary buffer the re-audit V5 used."""

    return array.array("B", b"secret-binary")


#: The integer array the pre-remediation bypass produced for ``array.array("B")``.
ARRAY_BINARY_AS_INTEGERS = list(b"secret-binary")


def manual_event(
    event_type: str,
    payload: dict[str, Any],
    *,
    event_id: str = "evt-v5-manual",
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
    assert system.repository.count() == 0
    assert system.bus.stats.published_total == 0
    assert received == []
    assert system.dead_letter_count() == 0


# ══════════════════════════════════════════════════════════════════════════
# MAJOR-V5-001 — binary/buffer classification must include ``array.array``
# ══════════════════════════════════════════════════════════════════════════


def test_array_binary_payload_value_is_rejected_before_persistence() -> None:
    """MAJOR-V5-001: ``array.array`` is binary and must fail closed."""

    system, received = _watching_system()

    with pytest.raises(REJECTIONS):
        system.publish(
            "message.received",
            {
                "request_id": "req-v5-array",
                "supporting_domains": _array_binary(),
            },
            event_id="evt-v5-array",
        )

    _assert_nothing_reached_persistence(system, received)


def test_array_binary_value_never_becomes_an_integer_array() -> None:
    """MAJOR-V5-001: the byte values must never be canonicalized into integers.

    This is the exact defect: even if a caller catches the boundary rejection, the
    converted integer list must never exist as an accepted canonical value.
    """

    system, received = _watching_system()

    accepted: object = None
    try:
        accepted = system.publish(
            "message.received",
            {"request_id": "req-v5-array-int", "sequence": _array_binary()},
            event_id="evt-v5-array-int",
        ).event.payload.data.get("sequence")
    except REJECTIONS:
        accepted = None

    assert accepted != ARRAY_BINARY_AS_INTEGERS
    _assert_nothing_reached_persistence(system, received)


def test_array_binary_payload_value_is_rejected_by_the_public_safe_path() -> None:
    """MAJOR-V5-001: ``create_event`` refuses it too, before any construction."""

    system, received = _watching_system()

    with pytest.raises(REJECTIONS):
        system.create_event(
            "message.received",
            {"request_id": "req-v5-array-create", "sequence": _array_binary()},
            event_id="evt-v5-array-create",
        )

    _assert_nothing_reached_persistence(system, received)


def test_nested_array_binary_in_payload_is_rejected() -> None:
    """MAJOR-V5-001: an ``array.array`` nested in a mapping is refused."""

    system, received = _watching_system()

    with pytest.raises(REJECTIONS):
        system.publish(
            "message.received",
            {
                "request_id": "req-v5-array-nested",
                "result_reference": {"sequence": _array_binary()},
            },
            event_id="evt-v5-array-nested",
        )

    _assert_nothing_reached_persistence(system, received)


def test_array_binary_in_payload_sequence_is_rejected() -> None:
    """MAJOR-V5-001: an ``array.array`` inside a list is refused."""

    system, received = _watching_system()

    with pytest.raises(REJECTIONS):
        system.publish(
            "message.received",
            {
                "request_id": "req-v5-array-in-list",
                "supporting_domains": [_array_binary()],
            },
            event_id="evt-v5-array-in-list",
        )

    _assert_nothing_reached_persistence(system, received)


def test_array_binary_metadata_value_is_rejected() -> None:
    """MAJOR-V5-001: ``array.array`` in ``metadata`` is refused."""

    system, received = _watching_system()

    with pytest.raises(REJECTIONS):
        system.publish(
            "message.received",
            {"request_id": "req-v5-array-meta"},
            event_id="evt-v5-array-meta",
            metadata={"value": _array_binary()},
        )

    _assert_nothing_reached_persistence(system, received)


def test_nested_array_binary_metadata_is_rejected() -> None:
    """MAJOR-V5-001: an ``array.array`` nested in metadata is refused."""

    system, received = _watching_system()

    with pytest.raises(REJECTIONS):
        system.publish(
            "message.received",
            {"request_id": "req-v5-array-meta-nested"},
            event_id="evt-v5-array-meta-nested",
            metadata={"outer": {"inner": [_array_binary()]}},
        )

    _assert_nothing_reached_persistence(system, received)


def test_manual_publish_event_with_array_binary_is_rejected() -> None:
    """MAJOR-V5-001: the manual publication boundary applies the same gate."""

    system, received = _watching_system()
    event = manual_event(
        "message.received",
        {"request_id": "req-v5-array-manual", "sequence": _array_binary()},
        event_id="evt-v5-array-manual",
    )

    with pytest.raises(REJECTIONS):
        system.publish_event(event)

    _assert_nothing_reached_persistence(system, received)


def test_array_binary_publication_leaves_the_durable_file_unchanged(
    tmp_path: Path,
) -> None:
    """MAJOR-V5-001: the exact durable reproduction fails before any append."""

    store = _durable_store(tmp_path)
    system, received = _file_backed_system(store)

    with pytest.raises(REJECTIONS):
        system.publish(
            "message.received",
            {
                "request_id": "req-v5-array-durable",
                "supporting_domains": _array_binary(),
            },
            event_id="evt-v5-array-durable",
        )

    durable = store.read_bytes() if store.exists() else b""
    assert ARRAY_BINARY_AS_INTEGERS[0:4] != [] and durable == b""
    assert system.repository.count() == 0
    assert system.dead_letter_count() == 0
    assert received == []


def test_signed_and_unicode_array_buffers_are_rejected() -> None:
    """MAJOR-V5-001: every ``array.array`` typecode is a binary buffer.

    A closed list of ``array`` typecodes would leave the same class of bypass
    open, so the classifier must judge the value, not a hand-written type list.
    """

    system, received = _watching_system()

    for typecode, values in (
        ("b", [-1, 2, -3]),
        ("h", [1, 2, 3]),
        ("i", [1, 2, 3]),
        ("f", [1.5, 2.5]),
        ("d", [1.5, 2.5]),
    ):
        with pytest.raises(REJECTIONS):
            system.publish(
                "message.received",
                {
                    "request_id": f"req-v5-array-{typecode}",
                    "sequence": array.array(typecode, values),
                },
                event_id=f"evt-v5-array-{typecode}",
            )

    _assert_nothing_reached_persistence(system, received)


# ── MAJOR-V5-001 controls: descriptive sequences stay valid ────────────────


def test_ordinary_list_of_safe_identifiers_remains_valid() -> None:
    """MAJOR-V5-001 control: a descriptive identifier list is still allowed."""

    system, received = _watching_system()

    result = system.publish(
        "message.received",
        {
            "request_id": "req-v5-array-control",
            "supporting_domains": ["domain:legal", "domain:health"],
        },
        event_id="evt-v5-array-control",
    )

    assert result.event.payload.data["supporting_domains"] == [
        "domain:legal",
        "domain:health",
    ]
    assert len(received) == 1


def test_ordinary_tuple_of_safe_identifiers_remains_valid() -> None:
    """MAJOR-V5-001 control: a descriptive identifier tuple is still allowed."""

    system, received = _watching_system()

    result = system.publish(
        "message.received",
        {
            "request_id": "req-v5-array-control-tuple",
            "supporting_domains": ("domain:legal", "domain:health"),
        },
        event_id="evt-v5-array-control-tuple",
    )

    assert result.event.payload.data["supporting_domains"] == [
        "domain:legal",
        "domain:health",
    ]
    assert len(received) == 1


def test_ordinary_integer_list_stays_valid_in_a_structured_reference() -> None:
    """MAJOR-V5-001 control: an explicit ``list[int]`` reference stays valid.

    Remediation V5 must not solve the buffer bypass by banning every sequence.
    """

    system, received = _watching_system()

    result = system.publish(
        "message.received",
        {
            "request_id": "req-v5-array-control-ints",
            "result_reference": {"sequence": [1, 2, 3]},
        },
        event_id="evt-v5-array-control-ints",
    )

    assert result.event.payload.data["result_reference"] == {"sequence": [1, 2, 3]}
    assert len(received) == 1


# ══════════════════════════════════════════════════════════════════════════
# MAJOR-V5-002 — lifecycle-fact value semantics / no content mirroring
# ══════════════════════════════════════════════════════════════════════════


def test_raw_user_text_cannot_relocate_into_status() -> None:
    """MAJOR-V5-002: the exact re-audit V5 reproduction must fail closed."""

    system, received = _watching_system()

    with pytest.raises(REJECTIONS):
        system.publish(
            "message.received",
            {"request_id": "raw-user-1", "status": RAW_USER_TEXT},
            event_id="evt-v5-raw-status",
        )

    _assert_nothing_reached_persistence(system, received)


def test_raw_user_text_cannot_relocate_into_request_id() -> None:
    """MAJOR-V5-002: an identifier key must not accept prose."""

    system, received = _watching_system()

    with pytest.raises(REJECTIONS):
        system.publish(
            "message.received",
            {"request_id": RAW_USER_TEXT, "channel": "conversation"},
            event_id="evt-v5-raw-request-id",
        )

    _assert_nothing_reached_persistence(system, received)


def test_raw_user_text_cannot_relocate_into_metadata() -> None:
    """MAJOR-V5-002: metadata is not a prose side channel."""

    system, received = _watching_system()

    with pytest.raises(REJECTIONS):
        system.publish(
            "message.received",
            {"request_id": "req-v5-raw-meta", "channel": "conversation"},
            event_id="evt-v5-raw-meta",
            metadata={"note": RAW_USER_TEXT},
        )

    _assert_nothing_reached_persistence(system, received)


def test_raw_user_text_cannot_relocate_into_an_unknown_metadata_key() -> None:
    """MAJOR-V5-002: an unknown metadata key is not a content-mirroring path."""

    system, received = _watching_system()

    with pytest.raises(REJECTIONS):
        system.publish(
            "message.received",
            {"request_id": "req-v5-raw-comment"},
            event_id="evt-v5-raw-comment",
            metadata={"comment": RAW_USER_TEXT},
        )

    _assert_nothing_reached_persistence(system, received)


def test_raw_user_text_cannot_relocate_into_nested_metadata() -> None:
    """MAJOR-V5-002: nesting metadata does not launder prose either."""

    system, received = _watching_system()

    with pytest.raises(REJECTIONS):
        system.publish(
            "message.received",
            {"request_id": "req-v5-raw-meta-nested"},
            event_id="evt-v5-raw-meta-nested",
            metadata={"outer": {"inner": RAW_USER_TEXT}},
        )

    _assert_nothing_reached_persistence(system, received)


def test_raw_user_text_cannot_relocate_into_a_boolean_field() -> None:
    """MAJOR-V5-002: a boolean lifecycle fact requires a real boolean."""

    system, received = _watching_system()

    for key in ("approved", "needs_clarification", "is_success"):
        with pytest.raises(REJECTIONS):
            system.publish(
                "message.received",
                {"request_id": f"req-v5-raw-{key}", key: RAW_USER_TEXT},
                event_id=f"evt-v5-raw-{key}",
            )

    _assert_nothing_reached_persistence(system, received)


def test_raw_user_text_cannot_relocate_into_a_numeric_field() -> None:
    """MAJOR-V5-002: a numeric lifecycle fact requires a real number."""

    system, received = _watching_system()

    for key in ("duration_ms", "count", "attempts", "version", "sequence"):
        with pytest.raises(REJECTIONS):
            system.publish(
                "message.received",
                {"request_id": f"req-v5-raw-{key}", key: RAW_USER_TEXT},
                event_id=f"evt-v5-raw-num-{key}",
            )

    _assert_nothing_reached_persistence(system, received)


def test_raw_user_text_cannot_relocate_into_a_categorical_field() -> None:
    """MAJOR-V5-002: a categorical token is bounded, not free prose."""

    system, received = _watching_system()

    for key in ("channel", "state", "intent", "route", "policy", "error_code"):
        with pytest.raises(REJECTIONS):
            system.publish(
                "message.received",
                {"request_id": f"req-v5-raw-{key}", key: RAW_USER_TEXT},
                event_id=f"evt-v5-raw-cat-{key}",
            )

    _assert_nothing_reached_persistence(system, received)


def test_unbounded_categorical_text_is_rejected() -> None:
    """MAJOR-V5-002: a 10,000-character ``status`` must not be persisted."""

    system, received = _watching_system()

    with pytest.raises(REJECTIONS):
        system.publish(
            "message.received",
            {"request_id": "req-v5-unbounded-status", "status": "x" * 10_000},
            event_id="evt-v5-unbounded-status",
        )

    _assert_nothing_reached_persistence(system, received)


def test_raw_user_text_never_reaches_the_durable_file(tmp_path: Path) -> None:
    """MAJOR-V5-002: exact durable reproduction — repository count unchanged."""

    store = _durable_store(tmp_path)
    system, received = _file_backed_system(store)

    with pytest.raises(REJECTIONS):
        system.publish(
            "message.received",
            {"request_id": "raw-user-1", "status": RAW_USER_TEXT},
            event_id="evt-v5-raw-durable",
            metadata={"note": RAW_USER_TEXT},
        )

    durable = store.read_bytes() if store.exists() else b""
    assert RAW_USER_TEXT.encode() not in durable
    assert b"landlord" not in durable
    assert system.repository.count() == 0
    assert received == []


def test_manual_publish_event_with_prose_identifier_is_rejected() -> None:
    """MAJOR-V5-002: the manual boundary enforces value semantics too."""

    system, received = _watching_system()
    event = manual_event(
        "message.received",
        {"request_id": RAW_USER_TEXT, "channel": "conversation"},
        event_id="evt-v5-raw-manual",
    )

    with pytest.raises(REJECTIONS):
        system.publish_event(event)

    _assert_nothing_reached_persistence(system, received)


def test_structured_reference_nested_prose_is_rejected() -> None:
    """MAJOR-V5-002: prose hidden in a structured reference fails closed."""

    system, received = _watching_system()

    with pytest.raises(REJECTIONS):
        system.publish(
            "message.received",
            {"request_id": "req-v5-raw-ref", "result_reference": RAW_USER_TEXT},
            event_id="evt-v5-raw-ref",
        )

    _assert_nothing_reached_persistence(system, received)


def test_structured_reference_list_prose_is_rejected() -> None:
    """MAJOR-V5-002: prose inside a structured reference list fails closed."""

    system, received = _watching_system()

    with pytest.raises(REJECTIONS):
        system.publish(
            "message.received",
            {
                "request_id": "req-v5-raw-domains",
                "supporting_domains": [RAW_USER_TEXT],
            },
            event_id="evt-v5-raw-domains",
        )

    _assert_nothing_reached_persistence(system, received)


# ── MAJOR-V5-002 controls: legitimate lifecycle facts stay valid ───────────

#: The legitimate V5 control values whose key names a canonical header fact.
#:
#: Remediation V6 established that a payload key naming a canonical header fact is
#: *the same* lifecycle fact, so it is consumed into the header instead of being
#: persisted a second time (MAJOR-V6-003).  The control below still exercises every
#: one of these values; it asserts the one canonical header authority rather than a
#: second payload copy.  ``event_type`` is the single exception: the platform event
#: type is always supplied by construction, so a *different* payload value is a
#: contradiction and fails closed instead of being accepted (proved adversarially in
#: ``test_phase11_22_remediation_v6_regressions.py``).
CANONICAL_HEADER_CONTROL_KEYS = frozenset(
    {"workflow_id", "correlation_id", "schema_version", "producer"}
)


@pytest.mark.parametrize(
    ("key", "value"),
    (
        ("request_id", "req-123"),
        ("execution_id", "EXEC-1"),
        ("approval_id", "APP-1"),
        ("session_id", "sess-1"),
        ("workflow_id", "workflow:123"),
        ("domain_id", "domain:legal"),
        ("correlation_id", "cmm.orchestrator"),
        ("status", "completed"),
        ("state", "selected"),
        ("intent", "question"),
        ("route", "conversation"),
        ("channel", "conversation"),
        ("policy", "default"),
        ("primary_domain", "domain:general"),
        ("error_code", "E1"),
        ("schema_version", "1.0.0"),
        ("producer", "cmm.orchestration"),
    ),
)
def test_legitimate_identifier_and_categorical_facts_still_pass(
    key: str, value: str
) -> None:
    """MAJOR-V5-002 control: every legitimate current fact remains supported."""

    system, received = _watching_system()

    result = system.publish(
        "message.received",
        {"request_id": "req-v5-control", key: value},
        event_id=f"evt-v5-control-{next(_CONTROL_IDS)}",
    )

    if key in CANONICAL_HEADER_CONTROL_KEYS:
        assert getattr(result.event.header, key) == value
        assert key not in result.event.payload.data
    else:
        assert result.event.payload.data[key] == value
    assert len(received) == 1


def test_canonical_event_type_payload_fact_still_reaches_the_header() -> None:
    """MAJOR-V5-002 control: a legitimate `event_type` value is still supported.

    Remediation V6 moved this value out of the payload-key parametrization above and
    proves the clarified contract here: when a payload `event_type` agrees with the
    canonical event type it is consumed into the one header authority, and when it
    disagrees it fails closed (proved adversarially in
    ``test_phase11_22_remediation_v6_regressions.py``).  The legitimate fact is
    therefore still fully supported, exactly once.
    """

    system, received = _watching_system()

    result = system.publish(
        "message.received",
        {"request_id": "req-v5-control", "event_type": "message.received"},
        event_id=f"evt-v5-control-{next(_CONTROL_IDS)}",
    )

    assert result.event.header.event_type == "message.received"
    assert "event_type" not in result.event.payload.data
    assert len(received) == 1


@pytest.mark.parametrize(
    ("key", "value"),
    (
        ("duration_ms", 125),
        ("count", 2),
        ("attempts", 1),
        ("version", 3),
        ("sequence", 0),
    ),
)
def test_legitimate_numeric_facts_still_pass(key: str, value: int) -> None:
    """MAJOR-V5-002 control: bounded numeric facts remain supported."""

    system, received = _watching_system()

    result = system.publish(
        "message.received",
        {"request_id": "req-v5-control-num", key: value},
        event_id=f"evt-v5-control-{next(_CONTROL_IDS)}",
    )

    assert result.event.payload.data[key] == value
    assert len(received) == 1


@pytest.mark.parametrize(
    ("key", "value"),
    (
        ("approved", True),
        ("approved", False),
        ("needs_clarification", True),
        ("is_success", False),
    ),
)
def test_legitimate_boolean_facts_still_pass(key: str, value: bool) -> None:
    """MAJOR-V5-002 control: real boolean lifecycle facts remain supported."""

    system, received = _watching_system()

    result = system.publish(
        "message.received",
        {"request_id": "req-v5-control-bool", key: value},
        event_id=f"evt-v5-control-{next(_CONTROL_IDS)}",
    )

    assert result.event.payload.data[key] is value
    assert len(received) == 1


@pytest.mark.parametrize(
    ("key", "value"),
    (
        ("occurred_at", "2024-01-01T12:00:00+00:00"),
        ("emitted_at", "2024-01-01T12:00:00+00:00"),
    ),
)
def test_legitimate_canonical_timestamp_strings_still_pass(
    key: str, value: str
) -> None:
    """MAJOR-V5-002 control: the canonical timestamp string form stays valid.

    MAJOR-V6-003: a timestamp payload key names the canonical header fact, so this
    control asserts the string reaches the one canonical header rather than being
    persisted a second time.  ``occurred_at`` is supplied explicitly so that an
    adopted ``emitted_at`` still satisfies the canonical chronology contract.
    """

    system, received = _watching_system()

    result = system.publish(
        "message.received",
        {"request_id": "req-v5-control-time", key: value},
        event_id=f"evt-v5-control-{next(_CONTROL_IDS)}",
        occurred_at=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
    )

    assert getattr(result.event.header, key) == datetime(
        2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc
    )
    assert key not in result.event.payload.data
    assert len(received) == 1


def test_legitimate_structured_reference_containers_still_pass() -> None:
    """MAJOR-V5-002 control: documented structured references stay valid."""

    system, received = _watching_system()

    result = system.publish(
        "message.received",
        {
            "request_id": "req-v5-control-structured",
            "approval_refs": [{"approval_id": "app-1"}],
            "result_reference": {"reference_id": "ref-1"},
            "supporting_domains": ["domain:legal", "domain:health"],
            "related_domain_ids": ["domain:legal"],
        },
        event_id="evt-v5-control-structured",
    )

    data = result.event.payload.data
    assert data["approval_refs"] == [{"approval_id": "app-1"}]
    assert data["result_reference"] == {"reference_id": "ref-1"}
    assert data["supporting_domains"] == ["domain:legal", "domain:health"]
    assert data["related_domain_ids"] == ["domain:legal"]
    json.dumps(data)
    assert len(received) == 1


def test_legitimate_existing_metadata_still_passes() -> None:
    """MAJOR-V5-002 control: the documented safe metadata examples stay valid."""

    system, received = _watching_system()

    result = system.publish(
        "message.received",
        {"request_id": "req-v5-control-meta"},
        event_id="evt-v5-control-meta",
        metadata={"status_code": "ok", "attempt": 1},
    )

    assert result.event.header.metadata == {"status_code": "ok", "attempt": 1}
    assert len(received) == 1


def test_legitimate_origin_metadata_still_passes() -> None:
    """MAJOR-V5-002 control: the second documented metadata example stays valid."""

    system, received = _watching_system()

    result = system.publish(
        "message.received",
        {"request_id": "req-v5-control-origin"},
        event_id="evt-v5-control-origin",
        metadata={"origin": "original"},
    )

    assert result.event.header.metadata == {"origin": "original"}
    assert len(received) == 1


def test_numeric_metadata_and_safe_nesting_still_pass() -> None:
    """MAJOR-V5-002 control: bounded numeric metadata and safe nesting stay valid."""

    system, received = _watching_system()

    result = system.publish(
        "message.received",
        {"request_id": "req-v5-control-meta-nesting"},
        event_id="evt-v5-control-meta-nesting",
        metadata={
            "attempt": 2,
            "ratio": 0.5,
            "flag": True,
            "detail": {"inner": ["a", 1, None]},
        },
    )

    assert result.event.header.metadata["attempt"] == 2
    assert result.event.header.metadata["detail"] == {"inner": ["a", 1, None]}
    assert len(received) == 1


def test_every_allowed_payload_key_has_an_explicit_value_class() -> None:
    """MAJOR-V5-002: no allowed key may fall through to unrestricted prose."""

    from cmm.events import event_payload_safety as safety

    classified = set()
    for keys in safety.PAYLOAD_KEY_CLASSES.values():
        classified |= set(keys)

    assert classified == set(ALLOWED_PAYLOAD_KEYS)


def test_identifier_pattern_rejects_prose_shapes() -> None:
    """MAJOR-V5-002: the identifier rule is narrow enough to exclude prose."""

    from cmm.events.event_payload_safety import validate_platform_identifier

    for prose in (
        RAW_USER_TEXT,
        "My landlord entered my flat",
        "hello world",
        "two words",
        "",
    ):
        with pytest.raises(REJECTIONS):
            validate_platform_identifier(prose, field="request_id")

    for legitimate in ("req-123", "EXEC-1", "domain:legal", "workflow:123", "cmm.x.y"):
        assert (
            validate_platform_identifier(legitimate, field="request_id") == legitimate
        )


# ══════════════════════════════════════════════════════════════════════════
# MAJOR-V5-003 — canonical bus DLQ safety without external categorizer binding
# ══════════════════════════════════════════════════════════════════════════


def _canonical_bus_dlq(
    exception_class: type[BaseException], *, attempts: int = 2
) -> tuple[AgentRuntimeEventBus, InMemoryAgentRuntimeDeadLetterQueue]:
    """Bind the canonical bus to the canonical DLQ with **no** categorizer.

    This is exactly the canonical composition the independent re-audit V5 used:
    ``AgentRuntimeEventBus`` + canonical DLQ + bounded retry, and no call to
    ``bind_error_categorizer``.
    """

    bus = AgentRuntimeEventBus(
        registry=AgentRuntimeEventRegistry(strict_mode=True),
        max_delivery_attempts=attempts,
    )
    dlq = InMemoryAgentRuntimeDeadLetterQueue()
    bus.bind_dead_letter_queue(dlq)

    def failing(event: AgentRuntimeEvent) -> None:
        raise exception_class("subscriber exploded")

    bus.subscribe(failing, ["message.received"])
    event = AgentRuntimeEventFactory().create_event(
        "message.received",
        {"request_id": "req-v5-dlq"},
        event_id="evt-v5-dlq",
    )
    bus.publish(event)
    return bus, dlq


def test_direct_canonical_bus_dlq_has_no_categorizer_bound() -> None:
    """MAJOR-V5-003 precondition: the reproduction really uses no categorizer."""

    bus = AgentRuntimeEventBus(max_delivery_attempts=2)
    assert bus._error_categorizer is None


def test_direct_canonical_bus_dlq_never_retains_a_credential_class_name() -> None:
    """MAJOR-V5-003: the exact re-audit V5 reproduction must fail closed."""

    credential_exception = type(CREDENTIAL_CLASS_NAME, (Exception,), {})
    _bus, dlq = _canonical_bus_dlq(credential_exception)

    rendered = json.dumps(
        [{"error_type": entry.error_type, "error": entry.error} for entry in dlq.list()]
    )

    assert "api_key" not in rendered
    assert "abcdef1234567890" not in rendered
    assert CREDENTIAL_CLASS_NAME not in rendered


def test_direct_canonical_bus_dlq_never_retains_a_private_marker_class_name() -> None:
    """MAJOR-V5-003: a private-marker identifier-shaped class name fails closed."""

    private_exception = type(PRIVATE_MARKER_CLASS_NAME, (Exception,), {})
    _bus, dlq = _canonical_bus_dlq(private_exception)

    rendered = json.dumps(
        [{"error_type": entry.error_type, "error": entry.error} for entry in dlq.list()]
    )

    assert "TOP_SECRET" not in rendered
    assert "TOP SECRET" not in rendered
    assert "system_prompt" not in rendered
    assert PRIVATE_MARKER_CLASS_NAME not in rendered


def test_direct_canonical_bus_dlq_without_categorizer_uses_a_neutral_category() -> None:
    """MAJOR-V5-003: the fail-safe default is one bounded neutral category."""

    credential_exception = type(CREDENTIAL_CLASS_NAME, (Exception,), {})
    _bus, dlq = _canonical_bus_dlq(credential_exception)

    entries = dlq.list()
    assert len(entries) == 1
    assert entries[0].error_type == NEUTRAL_ERROR_CATEGORY
    assert entries[0].error == NEUTRAL_ERROR_CATEGORY
    assert entries[0].attempts == 2


def test_direct_canonical_bus_dlq_without_categorizer_neutralizes_an_ordinary_name() -> (
    None
):
    """MAJOR-V5-003: with no content scanner bound, no class name is trusted.

    The fail-safe rule is deliberately conservative: an unbound content scanner
    means the transport cannot prove a class name is free of a credential or a
    private marker, so it records the neutral bounded category instead.
    """

    _bus, dlq = _canonical_bus_dlq(RuntimeError)

    entry = dlq.list()[0]
    assert entry.error_type == NEUTRAL_ERROR_CATEGORY
    assert entry.error == NEUTRAL_ERROR_CATEGORY
    assert "subscriber exploded" not in json.dumps(
        {
            "error_type": entry.error_type,
            "error": entry.error,
            "metadata": dict(entry.metadata),
        }
    )


def test_direct_canonical_bus_dlq_metadata_never_carries_a_credential() -> None:
    """MAJOR-V5-003: no DLQ-facing field carries the credential text."""

    credential_exception = type(CREDENTIAL_CLASS_NAME, (Exception,), {})
    _bus, dlq = _canonical_bus_dlq(credential_exception)

    rendered = json.dumps(
        [
            {
                "error_type": entry.error_type,
                "error": entry.error,
                "metadata": dict(entry.metadata),
                "handler_name": entry.handler_name,
            }
            for entry in dlq.list()
        ]
    )
    assert "api_key" not in rendered
    assert "abcdef1234567890" not in rendered


def test_safe_delivery_error_type_without_categorizer_is_neutral() -> None:
    """MAJOR-V5-003: the shared helper itself fails safe when unbound."""

    credential_exception = type(CREDENTIAL_CLASS_NAME, (Exception,), {})

    assert safe_delivery_error_type(credential_exception()) == NEUTRAL_ERROR_CATEGORY
    assert safe_delivery_error_type(RuntimeError("x")) == NEUTRAL_ERROR_CATEGORY


def test_composed_event_system_keeps_useful_ordinary_categories() -> None:
    """MAJOR-V5-003 control: the composed facade binds the categorizer."""

    system = build_system(max_delivery_attempts=2)

    def failing(event: AgentRuntimeEvent) -> None:
        raise RuntimeError("subscriber exploded")

    system.subscribe(failing, ["message.received"])
    system.publish(
        "message.received",
        {"request_id": "req-v5-dlq-composed"},
        event_id="evt-v5-dlq-composed",
        occurred_at=MOMENT,
        emitted_at=MOMENT,
    )

    entry = system.list_dead_letters()[0]
    assert entry.error_type == "RuntimeError"
    assert entry.error == "RuntimeError"


def test_composed_event_system_still_neutralizes_a_credential_class_name() -> None:
    """MAJOR-V5-003 control: the V4 fix stays green on the composed path."""

    credential_exception = type(CREDENTIAL_CLASS_NAME, (Exception,), {})
    system = build_system(max_delivery_attempts=2)

    def failing(event: AgentRuntimeEvent) -> None:
        raise credential_exception("subscriber exploded")

    system.subscribe(failing, ["message.received"])
    system.publish(
        "message.received",
        {"request_id": "req-v5-dlq-composed-cls"},
        event_id="evt-v5-dlq-composed-cls",
        occurred_at=MOMENT,
        emitted_at=MOMENT,
    )

    entry = system.list_dead_letters()[0]
    assert entry.error_type == NEUTRAL_ERROR_CATEGORY
    assert entry.error == NEUTRAL_ERROR_CATEGORY


def test_legacy_direct_single_attempt_bus_behaviour_is_unchanged() -> None:
    """MAJOR-V5-003 control: the historical legacy path keeps its exact shape.

    With no dead-letter queue bound and the historical single attempt, the
    delivery result still reports the raw exception text — that is the frozen
    Phase 9 contract and Remediation V5 must not change it.
    """

    bus = AgentRuntimeEventBus(max_delivery_attempts=1)
    delivery_holder: list[Any] = []

    def failing(event: AgentRuntimeEvent) -> None:
        raise RuntimeError("legacy exploded")

    bus.subscribe(failing, ["message.received"])
    event = AgentRuntimeEventFactory().create_event(
        "message.received", {"request_id": "req-v5-legacy"}, event_id="evt-v5-legacy"
    )

    original = bus._deliver_to_subscriber

    def spy(event: AgentRuntimeEvent, record: Any) -> Any:
        delivery = original(event, record)
        delivery_holder.append(delivery)
        return delivery

    bus._deliver_to_subscriber = spy  # type: ignore[method-assign]
    bus.publish(event)

    assert delivery_holder, "expected the legacy delivery to be observed"
    delivery = delivery_holder[0]
    assert delivery.status.value == "failed"
    assert delivery.error == "legacy exploded"
    assert delivery.metadata["attempts"] == 1
