"""Phase 11.22 — Remediation V6 adversarial regressions.

These tests make the independent Re-audit V6 reproductions executable and
permanent.  Each V6 finding gets its own named test; no finding is hidden inside
another test's assertions.

Covered findings::

    MAJOR-V6-001  the semantic numeric validator checked only "is a finite Python
                  number", so an unbounded lifecycle integer (``10 ** 5000``) was
                  accepted by the official in-memory repository and crashed the
                  official file-backed repository during serialization — the same
                  public event behaved differently on the two official
                  repositories.  Negative counts/durations/attempts/sequences and
                  absurd finite floats such as ``1e308`` were accepted too.
    MAJOR-V6-002  the identifier policy allowed ``:``, ``/`` and ``.`` with no
                  path-safety classification, so non-public local filesystem
                  locations (``file:///Users/alice/.ssh/id_rsa``,
                  ``Users/alice/.ssh/id_rsa``, ``C:/Users/alice/.ssh/id_rsa``)
                  qualified as identifiers and reached durable event content —
                  including in the canonical header ``producer`` fact.
    MAJOR-V6-003  the payload vocabulary still contained keys equivalent to
                  canonical header facts, and each copy was validated
                  independently, so two contradictory versions of one event fact
                  (``event_id``, ``correlation_id``, ``causation_id``,
                  ``producer``, ``sensitivity``, ``event_type``,
                  ``schema_version``, ``occurred_at``) were persisted together.
    MINOR-V6-001  the timestamp class validated textual shape rather than civil
                  time, so ``9999-99-99T99:99Z``, ``2026-02-31T12:00Z`` and
                  ``2026-09-27T25:61Z`` were accepted, and a timezone-less
                  ``2026-09-27T12:00`` was accepted despite the canonical
                  timezone-aware chronology contract.

Every test here is adversarial: it reproduces the exact behaviour the independent
re-audit V6 reported, so it must fail before the remediation and pass after it.

All four findings are exercised through real canonical components — the public
``EventSystem`` facade, the canonical factory/registry/bus/DLQ, and both official
repository implementations (in-memory and file-backed).  Nothing is mocked.
"""

from __future__ import annotations

import itertools
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from cmm.agent_runtime.runtime_event_contracts import (
    AgentRuntimeEvent,
    AgentRuntimeEventHeader,
    AgentRuntimeEventPayload,
    EventSensitivity,
)
from cmm.agent_runtime.runtime_event_repository import (
    FileAgentRuntimeEventRepository,
)
from cmm.events.event_payload_safety import (
    PlatformEventPayloadError,
)
from cmm.events.event_system import EventSystem
from tests.events.test_phase11_22_event_system import build_system

MOMENT = datetime(2026, 9, 27, 12, 0, 0, tzinfo=timezone.utc)

REJECTIONS = (PlatformEventPayloadError, TypeError, ValueError)

#: The canonical signed 64-bit bound every persisted numeric lifecycle fact must
#: respect.  It is repeated here as a literal so the regression module imports
#: against the pre-remediation production code, and the module constant is
#: separately asserted to match it.
MAX_NUMERIC_BOUND = 2**63 - 1

#: A monotonic counter so a parametrized control case always gets a fresh,
#: plain-safe canonical event identity instead of deriving one from a key name.
_CONTROL_IDS = itertools.count()

#: The exact unbounded integer the independent re-audit V6 published.
HUGE_INTEGER = 10**5000

#: The exact oversized finite float the independent re-audit V6 published.
OVERSIZED_FLOAT = 1e308

#: The exact non-public filesystem locations the independent re-audit V6 used.
PRIVATE_FILESYSTEM_PATHS = (
    "file:///Users/alice/.ssh/id_rsa",
    "/Users/alice/.ssh/id_rsa",
    "Users/alice/.ssh/id_rsa",
    "/home/alice/.ssh/id_rsa",
    "C:/Users/alice/.ssh/id_rsa",
    "C:\\Users\\alice\\.ssh\\id_rsa",
)

#: Legitimate public references that must survive the path classifier.
LEGITIMATE_REFERENCES = (
    "workflow:123",
    "domain:legal",
    "domain:general",
    "provider/model",
    "cmm.orchestration",
    "cmm.agent_runtime",
    "CORR-ORIGINAL",
    "workflow.execution.started",
    "events:read",
    "user-42",
    "EXEC-TOP",
)


def _watching_system() -> tuple[EventSystem, list[AgentRuntimeEvent]]:
    """Return an in-memory system plus the events one subscriber received."""

    system = build_system()
    received: list[AgentRuntimeEvent] = []
    system.subscribe(received.append, ["message.received"])
    return system, received


def _durable_store(tmp_path: Path) -> Path:
    return tmp_path / "data" / "events" / "runtime_events.jsonl"


def _file_backed_system(store: Path) -> EventSystem:
    return build_system(
        repository_factory=lambda: FileAgentRuntimeEventRepository(store)
    )


def _assert_nothing_reached_persistence(
    system: EventSystem, received: list[AgentRuntimeEvent]
) -> None:
    assert system.repository.count() == 0
    assert system.bus.stats.published_total == 0
    assert received == []
    assert system.dead_letter_count() == 0


def _durable_bytes(store: Path) -> bytes:
    return store.read_bytes() if store.exists() else b""


def manual_event(
    event_type: str,
    payload: dict[str, Any],
    *,
    event_id: str = "evt-v6-manual",
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


# ══════════════════════════════════════════════════════════════════════════
# MAJOR-V6-001 — numeric lifecycle facts must be truly bounded
# ══════════════════════════════════════════════════════════════════════════


def test_huge_integer_count_is_rejected_by_the_in_memory_repository() -> None:
    """MAJOR-V6-001: the official in-memory repository must never see it."""

    system, received = _watching_system()

    with pytest.raises(REJECTIONS):
        system.publish(
            "message.received",
            {"request_id": "req-v6-huge-mem", "count": HUGE_INTEGER},
            event_id="evt-v6-huge-mem",
        )

    _assert_nothing_reached_persistence(system, received)


def test_huge_integer_count_is_rejected_by_the_file_backed_repository(
    tmp_path: Path,
) -> None:
    """MAJOR-V6-001: the durable repository must not be the safety boundary."""

    store = _durable_store(tmp_path)
    system = _file_backed_system(store)
    before = _durable_bytes(store)

    with pytest.raises(REJECTIONS):
        system.publish(
            "message.received",
            {"request_id": "req-v6-huge-file", "count": HUGE_INTEGER},
            event_id="evt-v6-huge-file",
        )

    assert system.repository.count() == 0
    assert _durable_bytes(store) == before


def test_huge_integer_lifecycle_fact_is_repository_independent(
    tmp_path: Path,
) -> None:
    """MAJOR-V6-001: both official repositories must agree, and both must fail closed."""

    memory = build_system()
    store = _durable_store(tmp_path)
    durable = _file_backed_system(store)

    memory_outcome: object
    durable_outcome: object
    try:
        memory.publish(
            "message.received",
            {"request_id": "req-v6-parity-mem", "count": HUGE_INTEGER},
            event_id="evt-v6-parity",
        )
        memory_outcome = "accepted"
    except REJECTIONS as exc:
        memory_outcome = type(exc)

    try:
        durable.publish(
            "message.received",
            {"request_id": "req-v6-parity-file", "count": HUGE_INTEGER},
            event_id="evt-v6-parity",
        )
        durable_outcome = "accepted"
    except REJECTIONS as exc:
        durable_outcome = type(exc)

    assert memory_outcome != "accepted"
    assert durable_outcome != "accepted"
    assert memory_outcome is durable_outcome
    assert memory.repository.count() == 0
    assert durable.repository.count() == 0


#: Every negative numeric lifecycle shape the independent re-audit V6 published,
#: with the payload and header channel each one uses.
NEGATIVE_NUMERIC_CASES = (
    ("payload_count", {"count": -1}, {}),
    ("payload_attempts", {"attempts": -1}, {}),
    ("payload_sequence", {"sequence": -1}, {}),
    ("payload_duration_ms", {"duration_ms": -5}, {}),
    ("structured_reference_count", {"result_reference": {"count": -1}}, {}),
    ("structured_reference_sequence", {"result_reference": {"sequence": [-1]}}, {}),
    ("metadata_attempt", {}, {"metadata": {"attempt": -1}}),
    ("metadata_count", {}, {"metadata": {"count": -1}}),
    ("nested_metadata_count", {}, {"metadata": {"detail": {"count": -1}}}),
)


@pytest.mark.parametrize(
    ("label", "payload", "header_facts"),
    NEGATIVE_NUMERIC_CASES,
    ids=[case[0] for case in NEGATIVE_NUMERIC_CASES],
)
def test_negative_numeric_lifecycle_facts_are_rejected(
    label: str, payload: dict[str, Any], header_facts: dict[str, Any]
) -> None:
    """MAJOR-V6-001: a count, attempt, sequence or duration is never negative."""

    system, received = _watching_system()

    with pytest.raises(REJECTIONS):
        system.publish(
            "message.received",
            {"request_id": f"req-v6-neg-{label}", **payload},
            event_id=f"evt-v6-neg-{label}",
            **header_facts,
        )

    _assert_nothing_reached_persistence(system, received)


def test_negative_duration_is_rejected_and_leaves_the_file_untouched(
    tmp_path: Path,
) -> None:
    """MAJOR-V6-001: a negative duration must fail before the durable append."""

    store = _durable_store(tmp_path)
    system = _file_backed_system(store)
    before = _durable_bytes(store)

    with pytest.raises(REJECTIONS):
        system.publish(
            "message.received",
            {"request_id": "req-v6-neg-durable", "duration_ms": -5},
            event_id="evt-v6-neg-durable",
        )

    assert system.repository.count() == 0
    assert _durable_bytes(store) == before


#: Absurd-but-finite numbers the independent re-audit V6 published.  The huge
#: integer is intentionally kept out of pytest's own parameter-id rendering, which
#: would otherwise hit the interpreter's integer-string limit while collecting.
OVERSIZED_NUMERIC_CASES = (
    ("payload_duration_ms", OVERSIZED_FLOAT),
    ("payload_count", HUGE_INTEGER),
    ("payload_attempts", HUGE_INTEGER),
    ("payload_sequence", HUGE_INTEGER),
    ("payload_version", OVERSIZED_FLOAT),
)

#: The same class of value inside bounded metadata.
OVERSIZED_METADATA_CASES = (
    ("metadata_attempt", {"attempt": HUGE_INTEGER}),
    ("metadata_count", {"count": HUGE_INTEGER}),
    ("metadata_ratio", {"ratio": OVERSIZED_FLOAT}),
    ("nested_metadata_count", {"detail": {"count": HUGE_INTEGER}}),
)


@pytest.mark.parametrize(
    ("label", "value"),
    OVERSIZED_NUMERIC_CASES,
    ids=[case[0] for case in OVERSIZED_NUMERIC_CASES],
)
def test_oversized_numeric_lifecycle_facts_are_rejected(
    label: str, value: object
) -> None:
    """MAJOR-V6-001: an explicit bound must reject absurd finite numbers."""

    system, received = _watching_system()
    key = label.removeprefix("payload_")

    with pytest.raises(REJECTIONS):
        system.publish(
            "message.received",
            {"request_id": f"req-v6-big-{label}", key: value},
            event_id=f"evt-v6-big-{label}",
        )

    _assert_nothing_reached_persistence(system, received)


@pytest.mark.parametrize(
    ("label", "metadata"),
    OVERSIZED_METADATA_CASES,
    ids=[case[0] for case in OVERSIZED_METADATA_CASES],
)
def test_oversized_metadata_numeric_facts_are_rejected(
    label: str, metadata: dict[str, Any]
) -> None:
    """MAJOR-V6-001: bounded metadata numbers are bounded too."""

    system, received = _watching_system()

    with pytest.raises(REJECTIONS):
        system.publish(
            "message.received",
            {"request_id": f"req-v6-big-{label}"},
            event_id=f"evt-v6-big-{label}",
            metadata=metadata,
        )

    _assert_nothing_reached_persistence(system, received)


@pytest.mark.parametrize(
    ("label", "payload"),
    (
        ("payload_count_float", {"count": 2.5}),
        ("payload_attempts_float", {"attempts": 1.5}),
        ("payload_sequence_float", {"sequence": 0.5}),
        ("structured_count_float", {"result_reference": {"count": 1.5}}),
        ("structured_sequence_float", {"result_reference": {"sequence": [1.5]}}),
        ("metadata_attempt_float", {"request_id": "x"}),
    ),
    ids=lambda value: value if isinstance(value, str) else "",
)
def test_count_semantics_require_a_real_integer(
    label: str, payload: dict[str, Any]
) -> None:
    """MAJOR-V6-001: a count/attempt/sequence fact is an integer, not a float."""

    system, received = _watching_system()
    header_facts: dict[str, Any] = {}
    if label == "metadata_attempt_float":
        header_facts = {"metadata": {"attempt": 1.5}}

    with pytest.raises(REJECTIONS):
        system.publish(
            "message.received",
            payload,
            event_id=f"evt-v6-int-{label}",
            **header_facts,
        )

    _assert_nothing_reached_persistence(system, received)


@pytest.mark.parametrize(
    ("ratio", "accepted"),
    ((0.0, True), (0.5, True), (1.0, True), (1.5, False), (-0.1, False), (2, False)),
)
def test_normalized_ratio_semantics_are_enforced(ratio: float, accepted: bool) -> None:
    """MAJOR-V6-001: ``ratio`` is the normalized ratio current producers use."""

    system, received = _watching_system()
    kwargs = {"metadata": {"ratio": ratio}}

    if accepted:
        result = system.publish(
            "message.received",
            {"request_id": "req-v6-ratio"},
            event_id=f"evt-v6-ratio-{next(_CONTROL_IDS)}",
            **kwargs,
        )
        assert result.persisted is True
        assert result.event.header.metadata["ratio"] == ratio
        return

    with pytest.raises(REJECTIONS):
        system.publish(
            "message.received",
            {"request_id": "req-v6-ratio"},
            event_id=f"evt-v6-ratio-{next(_CONTROL_IDS)}",
            **kwargs,
        )
    _assert_nothing_reached_persistence(system, received)


@pytest.mark.parametrize(
    ("key", "value"),
    (
        ("count", 0),
        ("count", 1),
        ("count", MAX_NUMERIC_BOUND),
        ("attempts", 1),
        ("sequence", 0),
        ("sequence", 7),
        ("duration_ms", 0),
        ("duration_ms", 125),
        ("duration_ms", 1000),
        ("duration_ms", 125.5),
        ("version", 1),
        ("version", 3),
    ),
)
def test_legitimate_small_numeric_facts_still_pass(key: str, value: object) -> None:
    """MAJOR-V6-001 control: bounded lifecycle numbers remain supported."""

    system, received = _watching_system()

    result = system.publish(
        "message.received",
        {"request_id": "req-v6-control-num", key: value},
        event_id=f"evt-v6-control-{next(_CONTROL_IDS)}",
    )

    assert result.persisted is True
    assert result.event.payload.data[key] == value
    assert len(received) == 1


@pytest.mark.parametrize(
    ("attempt", "ratio", "count"),
    ((1, 0.5, 2), (0, 0.0, 0), (MAX_NUMERIC_BOUND, 1.0, 1)),
)
def test_legitimate_metadata_numeric_facts_still_pass(
    attempt: int, ratio: float, count: int
) -> None:
    """MAJOR-V6-001 control: bounded metadata numbers remain supported."""

    system, _received = _watching_system()

    result = system.publish(
        "message.received",
        {"request_id": "req-v6-control-meta"},
        event_id=f"evt-v6-control-meta-{next(_CONTROL_IDS)}",
        metadata={"attempt": attempt, "ratio": ratio, "count": count},
    )

    assert result.persisted is True
    assert result.event.header.metadata == {
        "attempt": attempt,
        "ratio": ratio,
        "count": count,
    }


def test_retry_after_ms_is_not_part_of_the_bounded_numeric_vocabulary() -> None:
    """MAJOR-V6-001: a key the platform does not model cannot carry a bound fact."""

    system, received = _watching_system()

    with pytest.raises(REJECTIONS):
        system.publish(
            "message.received",
            {"request_id": "req-v6-retry-after", "retry_after_ms": 1000},
            event_id="evt-v6-retry-after",
        )

    _assert_nothing_reached_persistence(system, received)


def test_every_bounded_numeric_field_has_an_explicit_semantic_bound() -> None:
    """MAJOR-V6-001: no numeric lifecycle key falls through to "any finite number"."""

    from cmm.events.event_payload_safety import (
        MAX_PLATFORM_NUMERIC_FACT,
        METADATA_KEY_CLASSES,
        NUMERIC_FACT_SEMANTICS,
        PAYLOAD_KEY_CLASSES,
    )

    assert MAX_PLATFORM_NUMERIC_FACT == MAX_NUMERIC_BOUND

    numeric_keys = set(PAYLOAD_KEY_CLASSES["number"])
    numeric_keys |= {
        key
        for key, value_class in METADATA_KEY_CLASSES.items()
        if value_class == "number"
    }
    assert numeric_keys
    assert numeric_keys <= set(NUMERIC_FACT_SEMANTICS)

    # Every declared semantic must be a real bounded kind, not a placeholder that
    # re-opens the audited "any finite Python number" policy.
    assert set(NUMERIC_FACT_SEMANTICS.values()) <= {
        "count",
        "duration",
        "ratio",
    }


# ══════════════════════════════════════════════════════════════════════════
# MAJOR-V6-002 — non-public filesystem paths never enter persistence
# ══════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize("path", PRIVATE_FILESYSTEM_PATHS)
def test_private_filesystem_path_payload_identifier_is_rejected(path: str) -> None:
    """MAJOR-V6-002: a local secret location is not a public identifier."""

    system, received = _watching_system()

    with pytest.raises(REJECTIONS):
        system.publish(
            "message.received",
            {"request_id": path},
            event_id=f"evt-v6-path-{next(_CONTROL_IDS)}",
        )

    _assert_nothing_reached_persistence(system, received)


@pytest.mark.parametrize("path", PRIVATE_FILESYSTEM_PATHS)
def test_private_filesystem_path_in_a_canonical_header_is_rejected(path: str) -> None:
    """MAJOR-V6-002: the canonical header identifier channel is not an escape hatch."""

    system, received = _watching_system()

    with pytest.raises(REJECTIONS):
        system.publish(
            "message.received",
            {"request_id": "req-v6-path-header"},
            event_id=f"evt-v6-path-header-{next(_CONTROL_IDS)}",
            producer=path,
        )

    _assert_nothing_reached_persistence(system, received)


@pytest.mark.parametrize("path", PRIVATE_FILESYSTEM_PATHS)
def test_private_filesystem_path_in_metadata_is_rejected(path: str) -> None:
    """MAJOR-V6-002: an identifier-classified metadata fact is judged the same."""

    system, received = _watching_system()

    with pytest.raises(REJECTIONS):
        system.publish(
            "message.received",
            {"request_id": "req-v6-path-meta"},
            event_id=f"evt-v6-path-meta-{next(_CONTROL_IDS)}",
            metadata={"error_type": path},
        )

    _assert_nothing_reached_persistence(system, received)


@pytest.mark.parametrize("path", PRIVATE_FILESYSTEM_PATHS)
def test_private_filesystem_path_in_permissions_is_rejected(path: str) -> None:
    """MAJOR-V6-002: every persisted identifier channel applies one rule."""

    system, received = _watching_system()

    with pytest.raises(REJECTIONS):
        system.publish(
            "message.received",
            {"request_id": "req-v6-path-perm"},
            event_id=f"evt-v6-path-perm-{next(_CONTROL_IDS)}",
            permissions=[path],
        )

    _assert_nothing_reached_persistence(system, received)


def test_private_filesystem_path_in_a_manual_event_is_rejected() -> None:
    """MAJOR-V6-002: the manual publication boundary applies the same classifier."""

    system, received = _watching_system()

    with pytest.raises(REJECTIONS):
        system.publish_event(
            manual_event(
                "message.received",
                {"request_id": "file:///Users/alice/.ssh/id_rsa"},
                event_id="evt-v6-path-manual",
            )
        )

    _assert_nothing_reached_persistence(system, received)


def test_private_filesystem_path_never_reaches_the_durable_file(
    tmp_path: Path,
) -> None:
    """MAJOR-V6-002: no durable byte may contain the audited secret location."""

    store = _durable_store(tmp_path)
    system = _file_backed_system(store)
    before = _durable_bytes(store)

    for path in PRIVATE_FILESYSTEM_PATHS:
        with pytest.raises(REJECTIONS):
            system.publish(
                "message.received",
                {"request_id": path},
                event_id=f"evt-v6-path-durable-{next(_CONTROL_IDS)}",
            )

    assert system.repository.count() == 0
    assert _durable_bytes(store) == before
    assert b".ssh" not in _durable_bytes(store)


@pytest.mark.parametrize("reference", LEGITIMATE_REFERENCES)
def test_legitimate_references_survive_the_path_classifier(reference: str) -> None:
    """MAJOR-V6-002 control: real references are not path-shaped and stay valid."""

    system, received = _watching_system()

    result = system.publish(
        "message.received",
        {"request_id": "req-v6-ref", "workflow_id": reference},
        event_id=f"evt-v6-ref-{next(_CONTROL_IDS)}",
    )

    assert result.persisted is True
    assert result.event.header.workflow_id == reference
    assert len(received) == 1


def test_legitimate_identifiers_survive_every_canonical_header_channel() -> None:
    """MAJOR-V6-002 control: the header identifier channels keep real references."""

    system, _received = _watching_system()

    result = system.publish(
        "message.received",
        {"request_id": "req-v6-ref-header", "domain_id": "domain:legal"},
        event_id="evt-v6-ref-header",
        producer="cmm.orchestration",
        aggregate_id="workflow:123",
        correlation_id="CORR-ORIGINAL",
        permissions=["events:read"],
    )

    stored = system.repository.get(result.event.header.event_id)
    assert stored is not None
    assert stored.header.producer == "cmm.orchestration"
    assert stored.header.aggregate_id == "workflow:123"
    assert stored.header.correlation_id == "CORR-ORIGINAL"
    assert stored.header.permissions == ["events:read"]
    assert stored.payload.data["domain_id"] == "domain:legal"


# ══════════════════════════════════════════════════════════════════════════
# MAJOR-V6-003 — one canonical header fact authority
# ══════════════════════════════════════════════════════════════════════════


def test_every_canonical_header_duplicate_key_is_declared() -> None:
    """MAJOR-V6-003: the consumed vocabulary is exactly the header-named payload keys."""

    from cmm.events.event_payload_safety import (
        ALLOWED_PAYLOAD_KEYS,
        CANONICAL_HEADER_FACT_KEYS,
        CANONICAL_HEADER_PAYLOAD_KEYS,
    )

    assert CANONICAL_HEADER_PAYLOAD_KEYS == (
        ALLOWED_PAYLOAD_KEYS & CANONICAL_HEADER_FACT_KEYS
    )
    assert {
        "event_id",
        "event_type",
        "schema_version",
        "occurred_at",
        "correlation_id",
        "causation_id",
        "producer",
        "sensitivity",
    } <= CANONICAL_HEADER_PAYLOAD_KEYS


@pytest.mark.parametrize(
    ("key", "payload_value", "header_fact", "header_value"),
    (
        ("event_id", "payload-event", "event_id", "header-event"),
        ("correlation_id", "payload-corr", "correlation_id", "header-corr"),
        ("causation_id", "payload-cause", "causation_id", "header-cause"),
        ("producer", "payload-producer", "producer", "header-producer"),
        ("event_type", "some.other.event", "event_type", "message.received"),
        ("schema_version", "1.1.0", "schema_version", "1.0.0"),
        ("occurred_at", "2024-01-01T00:00:00Z", "occurred_at", MOMENT),
    ),
    ids=lambda value: value if isinstance(value, str) else "",
)
def test_conflicting_canonical_payload_and_header_facts_cannot_persist(
    key: str,
    payload_value: object,
    header_fact: str,
    header_value: object,
) -> None:
    """MAJOR-V6-003: two contradictory versions of one fact cannot coexist."""

    system, received = _watching_system()

    with pytest.raises(REJECTIONS):
        system.publish(
            "message.received",
            {"request_id": "req-v6-conflict", key: payload_value},
            event_id="evt-v6-conflict",
            **{header_fact: header_value},
        )

    _assert_nothing_reached_persistence(system, received)


def test_conflicting_canonical_payload_and_header_facts_leave_the_file_untouched(
    tmp_path: Path,
) -> None:
    """MAJOR-V6-003: the conflict fails before the durable append."""

    store = _durable_store(tmp_path)
    system = _file_backed_system(store)
    before = _durable_bytes(store)

    with pytest.raises(REJECTIONS):
        system.publish(
            "message.received",
            {
                "request_id": "req-v6-conflict-durable",
                "event_id": "payload-event",
                "correlation_id": "payload-corr",
            },
            event_id="header-event",
            correlation_id="header-corr",
        )

    assert system.repository.count() == 0
    assert _durable_bytes(store) == before


def test_payload_cannot_shadow_the_canonical_header_identity_facts() -> None:
    """MAJOR-V6-003: the exact audited five-fact conflict cannot persist."""

    system, received = _watching_system()

    with pytest.raises(REJECTIONS):
        system.publish(
            "message.received",
            {
                "event_id": "payload-event",
                "correlation_id": "payload-corr",
                "causation_id": "payload-cause",
                "producer": "payload-producer",
                "sensitivity": "restricted",
            },
            event_id="header-event",
            correlation_id="header-corr",
            causation_id="header-cause",
            producer="header-producer",
            sensitivity="internal",
        )

    _assert_nothing_reached_persistence(system, received)


def test_canonical_header_facts_are_never_persisted_as_payload_facts() -> None:
    """MAJOR-V6-003: a payload copy is consumed into the one authoritative header."""

    system, _received = _watching_system()

    result = system.publish(
        "message.received",
        {
            "request_id": "req-v6-authority",
            "event_id": "payload-event",
            "correlation_id": "payload-corr",
            "causation_id": "payload-cause",
            "producer": "payload-producer",
            "sensitivity": "confidential",
            "workflow_id": "workflow:123",
            "goal_id": "goal-1",
            "task_id": "task-1",
            "agent_id": "cmm.orchestrator",
            "aggregate_id": "aggregate-1",
            "schema_version": "1.0.0",
        },
        correlation_id="payload-corr",
        causation_id="payload-cause",
        producer="payload-producer",
    )

    stored = system.repository.get("payload-event")
    assert stored is not None
    assert stored.payload.data == {"request_id": "req-v6-authority"}

    assert stored.header.event_id == "payload-event"
    assert stored.header.correlation_id == "payload-corr"
    assert stored.header.causation_id == "payload-cause"
    assert stored.header.producer == "payload-producer"
    assert stored.header.sensitivity is EventSensitivity.CONFIDENTIAL
    assert stored.header.workflow_id == "workflow:123"
    assert stored.header.goal_id == "goal-1"
    assert stored.header.task_id == "task-1"
    assert stored.header.agent_id == "cmm.orchestrator"
    assert stored.header.aggregate_id == "aggregate-1"
    assert stored.header.schema_version == "1.0.0"
    assert result.event.payload.data == {"request_id": "req-v6-authority"}


def test_payload_can_adopt_an_unset_canonical_header_identity_fact() -> None:
    """MAJOR-V6-003: an unset header fact is filled from the source payload once."""

    system, _received = _watching_system()

    result = system.publish(
        "message.received",
        {
            "request_id": "req-v6-adopt",
            "event_id": "payload-only-event",
            "producer": "payload-only-producer",
        },
    )

    stored = system.repository.get("payload-only-event")
    assert stored is not None
    assert stored.header.event_id == "payload-only-event"
    assert stored.header.producer == "payload-only-producer"
    assert "event_id" not in stored.payload.data
    assert "producer" not in stored.payload.data
    assert result.event.header.event_id == "payload-only-event"


def test_payload_sensitivity_stricter_than_the_header_is_promoted() -> None:
    """MAJOR-V6-003: a stricter source classification reaches the canonical header."""

    system, _received = _watching_system()

    result = system.publish(
        "message.received",
        {"request_id": "req-v6-sens-up", "sensitivity": "restricted"},
        event_id="evt-v6-sens-up",
        sensitivity="internal",
    )

    stored = system.repository.get("evt-v6-sens-up")
    assert stored is not None
    assert stored.header.sensitivity is EventSensitivity.RESTRICTED
    assert "sensitivity" not in stored.payload.data
    assert result.event.header.sensitivity is EventSensitivity.RESTRICTED


def test_payload_sensitivity_lower_than_the_header_cannot_downgrade_it() -> None:
    """MAJOR-V6-003: a lower payload classification never downgrades the header."""

    system, _received = _watching_system()

    result = system.publish(
        "message.received",
        {"request_id": "req-v6-sens-down", "sensitivity": "public"},
        event_id="evt-v6-sens-down",
        sensitivity="restricted",
    )

    stored = system.repository.get("evt-v6-sens-down")
    assert stored is not None
    assert stored.header.sensitivity is EventSensitivity.RESTRICTED
    assert "sensitivity" not in stored.payload.data
    assert result.event.header.sensitivity is EventSensitivity.RESTRICTED


def test_an_equal_canonical_payload_fact_does_not_persist_a_second_copy() -> None:
    """MAJOR-V6-003: an equal duplicate is still not a second persisted fact."""

    system, _received = _watching_system()

    system.publish(
        "message.received",
        {
            "request_id": "req-v6-equal",
            "event_type": "message.received",
            "schema_version": "1.0.0",
            "sensitivity": "internal",
        },
        event_id="evt-v6-equal",
        sensitivity="internal",
    )

    stored = system.repository.get("evt-v6-equal")
    assert stored is not None
    assert stored.payload.data == {"request_id": "req-v6-equal"}
    assert stored.header.sensitivity is EventSensitivity.INTERNAL


def test_manual_event_conflicting_with_its_own_header_is_rejected() -> None:
    """MAJOR-V6-003: the manual publication boundary keeps one authority too."""

    system, received = _watching_system()

    with pytest.raises(REJECTIONS):
        system.publish_event(
            manual_event(
                "message.received",
                {
                    "request_id": "req-v6-manual-conflict",
                    "correlation_id": "payload-corr",
                    "sensitivity": "public",
                },
                event_id="evt-v6-manual-conflict",
                correlation_id="header-corr",
                sensitivity="restricted",
            )
        )

    _assert_nothing_reached_persistence(system, received)


def test_manual_event_duplicate_header_fact_is_not_persisted_twice() -> None:
    """MAJOR-V6-003: a consistent manual duplicate is folded into the header."""

    system, _received = _watching_system()

    result = system.publish_event(
        manual_event(
            "message.received",
            {"request_id": "req-v6-manual-ok", "workflow_id": "workflow:123"},
            event_id="evt-v6-manual-ok",
        )
    )

    stored = system.repository.get("evt-v6-manual-ok")
    assert stored is not None
    assert stored.header.workflow_id == "workflow:123"
    assert stored.payload.data == {"request_id": "req-v6-manual-ok"}
    assert result.event.payload.data == {"request_id": "req-v6-manual-ok"}


def test_manual_event_conflicting_sensitivity_never_downgrades_the_header() -> None:
    """MAJOR-V6-003: manual sensitivity keeps the strictest canonical class."""

    system, _received = _watching_system()

    result = system.publish_event(
        manual_event(
            "message.received",
            {"request_id": "req-v6-manual-sens", "sensitivity": "restricted"},
            event_id="evt-v6-manual-sens",
            sensitivity="internal",
        )
    )

    stored = system.repository.get("evt-v6-manual-sens")
    assert stored is not None
    assert stored.header.sensitivity is EventSensitivity.RESTRICTED
    assert result.event.header.sensitivity is EventSensitivity.RESTRICTED


def test_payload_header_authority_holds_across_the_durable_reopen(
    tmp_path: Path,
) -> None:
    """MAJOR-V6-003: the single authority survives a durable restart unchanged."""

    store = _durable_store(tmp_path)
    system = _file_backed_system(store)

    system.publish(
        "message.received",
        {
            "request_id": "req-v6-durable-authority",
            "correlation_id": "corr-v6",
            "sensitivity": "confidential",
        },
        event_id="evt-v6-durable-authority",
        correlation_id="corr-v6",
    )

    reopened = FileAgentRuntimeEventRepository(store).get("evt-v6-durable-authority")
    assert reopened is not None
    assert reopened.header.correlation_id == "corr-v6"
    assert reopened.header.sensitivity is EventSensitivity.CONFIDENTIAL
    assert reopened.payload.data == {"request_id": "req-v6-durable-authority"}
    assert "sensitivity" not in json.dumps(reopened.payload.data), (
        "a second classification copy must not persist"
    )


def test_source_sensitivity_still_reaches_the_canonical_header() -> None:
    """MAJOR-V6-003 control: the real Domain bridge keeps its classification."""

    from cmm.domains.event_factory import DomainEventFactory
    from cmm.domains.event_publisher import DomainKernelEventPublisher
    from cmm.events.kernel_adapter import PlatformKernelEventAdapter

    system = build_system()
    adapter = PlatformKernelEventAdapter(system)
    publisher = DomainKernelEventPublisher(event_listener=adapter)

    domain_event = DomainEventFactory().create_event(
        event_type="domain.execution.completed",
        domain_id="domain:general",
        actor="system",
        event_id="DOM-V6-EXEC",
        occurred_at=MOMENT,
        sensitivity="restricted",
        correlation_id="CORR-V6",
        causation_id="CAUSE-V6",
        payload={"execution_id": "EXEC-V6", "status": "completed"},
    )
    publisher.publish(domain_event)

    stored = system.repository.query(event_type="operation.executed")
    assert stored, "the domain execution lifecycle fact must be bridged"
    assert stored[0].header.sensitivity is EventSensitivity.RESTRICTED
    assert "sensitivity" not in stored[0].payload.data


# ══════════════════════════════════════════════════════════════════════════
# MINOR-V6-001 — timestamp validation must enforce real time semantics
# ══════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize(
    "timestamp",
    (
        "9999-99-99T99:99Z",
        "2026-13-01T12:00:00Z",
        "2026-02-31T12:00:00Z",
        "2026-04-31T12:00:00Z",
        "2026-09-27T25:61:00Z",
        "2026-09-27T24:00:00Z",
        "2026-09-27T12:61:00Z",
        "2026-09-27T12:00:61Z",
    ),
)
def test_invalid_civil_timestamps_are_rejected(timestamp: str) -> None:
    """MINOR-V6-001: a real calendar/time value is required, not a text shape."""

    system, received = _watching_system()

    with pytest.raises(REJECTIONS):
        system.publish(
            "message.received",
            {"request_id": "req-v6-ts", "occurred_at": timestamp},
            event_id=f"evt-v6-ts-{next(_CONTROL_IDS)}",
        )

    _assert_nothing_reached_persistence(system, received)


@pytest.mark.parametrize(
    "timestamp",
    (
        "2026-09-27T12:00",
        "2026-09-27T12:00:00",
        "2026-09-27T12:00:00.123456",
        "2026-09-27",
    ),
)
def test_timezone_ambiguous_timestamps_are_rejected(timestamp: str) -> None:
    """MINOR-V6-001: the canonical chronology contract is timezone-aware."""

    system, received = _watching_system()

    with pytest.raises(REJECTIONS):
        system.publish(
            "message.received",
            {"request_id": "req-v6-ts-tz", "emitted_at": timestamp},
            event_id=f"evt-v6-ts-tz-{next(_CONTROL_IDS)}",
        )

    _assert_nothing_reached_persistence(system, received)


@pytest.mark.parametrize(
    "timestamp",
    (
        "2026-09-27T12:00:00Z",
        "2026-09-27T12:00:00+02:00",
        "2024-01-01T12:00:00+00:00",
        "2024-01-01T12:00:00.123456Z",
        "2024-02-29T00:00:00Z",
    ),
)
def test_valid_timezone_aware_timestamps_are_accepted(timestamp: str) -> None:
    """MINOR-V6-001 control: real, timezone-aware canonical timestamps stay valid."""

    system, _received = _watching_system()

    result = system.publish(
        "message.received",
        {"request_id": "req-v6-ts-ok", "occurred_at": timestamp},
        event_id=f"evt-v6-ts-ok-{next(_CONTROL_IDS)}",
        emitted_at=datetime(2030, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
    )

    assert result.persisted is True
    assert "occurred_at" not in result.event.payload.data


def test_invalid_civil_timestamp_never_reaches_the_durable_file(
    tmp_path: Path,
) -> None:
    """MINOR-V6-001: an impossible timestamp fails before the durable append."""

    store = _durable_store(tmp_path)
    system = _file_backed_system(store)
    before = _durable_bytes(store)

    for timestamp in (
        "9999-99-99T99:99Z",
        "2026-02-31T12:00Z",
        "2026-09-27T25:61Z",
        "2026-09-27T12:00",
    ):
        with pytest.raises(REJECTIONS):
            system.publish(
                "message.received",
                {"request_id": "req-v6-ts-durable", "occurred_at": timestamp},
                event_id=f"evt-v6-ts-durable-{next(_CONTROL_IDS)}",
            )

    assert system.repository.count() == 0
    assert _durable_bytes(store) == before
