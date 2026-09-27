"""Phase 11.22 — Remediation V7 adversarial regressions.

These tests make the independent Re-audit V7 reproductions executable and
permanent.  Each V7 finding gets its own named test; no finding is hidden inside
another test's assertions.

Covered findings::

    MAJOR-V7-001  the identifier/path safety authority classified absolute
                  filesystem locations but had no traversal-segment rule, so a
                  relative traversal prefixed with an apparently safe identifier
                  segment (``safe/../../etc/shadow``,
                  ``foo/../bar/../../private/var``) passed
                  ``validate_platform_identifier()`` and was durably persisted
                  through every shared identifier channel.
    MAJOR-V7-002  the identifier grammar deliberately admits ``:``, ``/`` and
                  ``@``, but the composed credential scanner did not treat URI
                  userinfo password syntax as credential structure, so
                  ``https://admin:hunter2hunter2@example.com/path`` and
                  ``postgres://alice:supersecret@example.com/db`` qualified as
                  safe identifiers and were durably persisted.

Both findings are exercised through the real canonical components — the public
``EventSystem`` facade, the canonical factory/registry/bus/DLQ, and both official
repository implementations (in-memory and file-backed).  Nothing is mocked.

The shared identifier authority is one function, so every persisted channel is
covered here explicitly rather than by patching ``request_id`` alone::

    payload identifier fields          (``request_id``, ``workflow_id``, ...)
    header producer                    (``producer`` and the other header facts)
    permissions                        (``permissions[]``)
    metadata identifier facts          (``metadata.error_type``)
    nested structured references       (``result_reference.reference_id``)
    reference sequences                (``supporting_domains[]``, ``approval_refs[]``)

Every test here is adversarial: it reproduces the exact behaviour the independent
re-audit V7 reported, so it must fail before the remediation and pass after it.
"""

from __future__ import annotations

import itertools
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from cmm.agent_runtime.runtime_event_contracts import (
    AgentRuntimeEvent,
    AgentRuntimeEventHeader,
    AgentRuntimeEventPayload,
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

#: A monotonic counter so every adversarial case gets a fresh, plain-safe
#: canonical event identity instead of deriving one from the audited value.
_CONTROL_IDS = itertools.count()

#: The exact relative traversals the independent re-audit V7 published.
TRAVERSAL_REFERENCES = (
    "safe/../../etc/shadow",
    "foo/../bar/../../private/var",
)

#: Further traversal spellings the V7 rule must cover: backslash-delimited,
#: mixed-separator and trailing forms, plus a bare relative private system root.
EXTRA_TRAVERSAL_REFERENCES = (
    "safe\\..\\..\\etc\\shadow",
    "safe/..\\../etc/shadow",
    "..\\..\\windows\\system32",
    "a/b/../..",
    "private/var/db/keychains",
)

#: Every traversal spelling the V7 rule must reject.
ALL_TRAVERSAL_REFERENCES = TRAVERSAL_REFERENCES + EXTRA_TRAVERSAL_REFERENCES

#: The exact URI userinfo credentials the independent re-audit V7 published.
URI_USERINFO_REFERENCES = (
    "https://admin:hunter2hunter2@example.com/path",
    "postgres://alice:supersecret@example.com/db",
)

#: Percent-encoded spellings of the same semantic credential structure.  A URI
#: whose userinfo decodes to ``name:secret`` still carries a password even
#: though the raw string has no literal colon before the ``@``.
PERCENT_ENCODED_USERINFO_REFERENCES = (
    "https://admin%3Ahunter2hunter2@example.com/path",
    "postgres://alice%3Asupersecret@example.com/db",
    "https://admin:hunter2%2Ehunter2@example.com/path",
)

#: Every URI-userinfo spelling the V7 rule must reject.
ALL_URI_USERINFO_REFERENCES = (
    URI_USERINFO_REFERENCES + PERCENT_ENCODED_USERINFO_REFERENCES
)

#: Legitimate public references that must survive both V7 rules untouched.
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

#: Legitimate credential-free URIs that the userinfo rule must not over-correct.
LEGITIMATE_CREDENTIAL_FREE_URIS = (
    "https://example.com/model",
    "postgres://example.com/db",
    "http://localhost:8080/health",
    "urn:cmm:event:message.received",
    "mailto:ops@example.com",
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
    event_id: str = "evt-v7-manual",
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
# MAJOR-V7-001 — relative traversal never enters event persistence
# ══════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize("reference", TRAVERSAL_REFERENCES)
def test_traversal_in_the_payload_identifier_is_rejected(reference: str) -> None:
    """MAJOR-V7-001: the exact audited reproduction, on the payload channel."""

    system, received = _watching_system()

    with pytest.raises(REJECTIONS):
        system.publish(
            "message.received",
            {"request_id": reference},
            event_id=f"evt-v7-trav-payload-{next(_CONTROL_IDS)}",
        )

    _assert_nothing_reached_persistence(system, received)


@pytest.mark.parametrize("reference", TRAVERSAL_REFERENCES)
def test_traversal_in_the_header_producer_is_rejected(reference: str) -> None:
    """MAJOR-V7-001: the canonical header producer channel is not an escape hatch."""

    system, received = _watching_system()

    with pytest.raises(REJECTIONS):
        system.publish(
            "message.received",
            {"request_id": "req-v7-trav-producer"},
            event_id=f"evt-v7-trav-producer-{next(_CONTROL_IDS)}",
            producer=reference,
        )

    _assert_nothing_reached_persistence(system, received)


@pytest.mark.parametrize("reference", TRAVERSAL_REFERENCES)
def test_traversal_in_a_metadata_identifier_is_rejected(reference: str) -> None:
    """MAJOR-V7-001: an identifier-classified metadata fact is judged the same."""

    system, received = _watching_system()

    with pytest.raises(REJECTIONS):
        system.publish(
            "message.received",
            {"request_id": "req-v7-trav-meta"},
            event_id=f"evt-v7-trav-meta-{next(_CONTROL_IDS)}",
            metadata={"error_type": reference},
        )

    _assert_nothing_reached_persistence(system, received)


@pytest.mark.parametrize("reference", TRAVERSAL_REFERENCES)
def test_traversal_in_permissions_is_rejected(reference: str) -> None:
    """MAJOR-V7-001: every persisted identifier channel applies the one rule."""

    system, received = _watching_system()

    with pytest.raises(REJECTIONS):
        system.publish(
            "message.received",
            {"request_id": "req-v7-trav-perm"},
            event_id=f"evt-v7-trav-perm-{next(_CONTROL_IDS)}",
            permissions=[reference],
        )

    _assert_nothing_reached_persistence(system, received)


@pytest.mark.parametrize("reference", TRAVERSAL_REFERENCES)
def test_traversal_in_a_nested_structured_reference_is_rejected(
    reference: str,
) -> None:
    """MAJOR-V7-001: a nested structured reference identifier is not a bypass."""

    system, received = _watching_system()

    with pytest.raises(REJECTIONS):
        system.publish(
            "message.received",
            {
                "request_id": "req-v7-trav-structured",
                "result_reference": {"reference_id": reference},
            },
            event_id=f"evt-v7-trav-structured-{next(_CONTROL_IDS)}",
        )

    _assert_nothing_reached_persistence(system, received)


@pytest.mark.parametrize("reference", TRAVERSAL_REFERENCES)
def test_traversal_in_a_reference_sequence_is_rejected(reference: str) -> None:
    """MAJOR-V7-001: a reference sequence element is judged by the same authority."""

    system, received = _watching_system()

    with pytest.raises(REJECTIONS):
        system.publish(
            "message.received",
            {
                "request_id": "req-v7-trav-sequence",
                "supporting_domains": [reference],
            },
            event_id=f"evt-v7-trav-sequence-{next(_CONTROL_IDS)}",
        )

    _assert_nothing_reached_persistence(system, received)


@pytest.mark.parametrize("reference", TRAVERSAL_REFERENCES)
def test_traversal_in_a_structured_reference_sequence_is_rejected(
    reference: str,
) -> None:
    """MAJOR-V7-001: a structured reference sequence is covered too."""

    system, received = _watching_system()

    with pytest.raises(REJECTIONS):
        system.publish(
            "message.received",
            {
                "request_id": "req-v7-trav-structured-sequence",
                "approval_refs": [{"reference_id": reference}],
            },
            event_id=f"evt-v7-trav-structured-seq-{next(_CONTROL_IDS)}",
        )

    _assert_nothing_reached_persistence(system, received)


@pytest.mark.parametrize("reference", EXTRA_TRAVERSAL_REFERENCES)
def test_every_traversal_spelling_is_rejected(reference: str) -> None:
    """MAJOR-V7-001: backslash, mixed-separator and relative-private forms too."""

    system, received = _watching_system()

    with pytest.raises(REJECTIONS):
        system.publish(
            "message.received",
            {"request_id": "req-v7-trav-extra", "workflow_id": reference},
            event_id=f"evt-v7-trav-extra-{next(_CONTROL_IDS)}",
        )

    _assert_nothing_reached_persistence(system, received)


def test_traversal_in_a_manual_event_is_rejected() -> None:
    """MAJOR-V7-001: the manual publication boundary applies the same rule."""

    system, received = _watching_system()

    with pytest.raises(REJECTIONS):
        system.publish_event(
            manual_event(
                "message.received",
                {"request_id": "safe/../../etc/shadow"},
                event_id="evt-v7-trav-manual",
            )
        )

    _assert_nothing_reached_persistence(system, received)


def test_traversal_never_reaches_the_durable_file(tmp_path: Path) -> None:
    """MAJOR-V7-001: no durable byte may contain an audited traversal."""

    store = _durable_store(tmp_path)
    system = _file_backed_system(store)
    before = _durable_bytes(store)

    for reference in ALL_TRAVERSAL_REFERENCES:
        with pytest.raises(REJECTIONS):
            system.publish(
                "message.received",
                {"request_id": reference},
                event_id=f"evt-v7-trav-durable-{next(_CONTROL_IDS)}",
            )

    assert system.repository.count() == 0
    assert _durable_bytes(store) == before
    assert b".." not in _durable_bytes(store)


def test_traversal_is_rejected_through_the_file_backed_repository(
    tmp_path: Path,
) -> None:
    """MAJOR-V7-001: the durable repository is never the safety boundary."""

    store = _durable_store(tmp_path)
    system = _file_backed_system(store)
    before = _durable_bytes(store)

    with pytest.raises(REJECTIONS):
        system.publish(
            "message.received",
            {"request_id": "safe/../../etc/shadow"},
            event_id="evt-v7-trav-file",
        )

    assert system.repository.count() == 0
    assert _durable_bytes(store) == before


#: Every shared persisted identifier channel, as a ``(label, builder)`` pair whose
#: builder places one audited reference into that channel and returns
#: ``(payload, header_facts)``.  Enumerating them keeps the coverage reviewable and
#: makes "do not patch ``request_id`` only" an executable claim.
SHARED_CHANNELS = (
    (
        "payload_request_id",
        lambda r: ({"request_id": r}, {}),
    ),
    (
        "payload_workflow_id",
        lambda r: ({"request_id": "req-v7-channel", "workflow_id": r}, {}),
    ),
    (
        "payload_aggregate_id",
        lambda r: ({"request_id": "req-v7-channel", "aggregate_id": r}, {}),
    ),
    (
        "payload_producer",
        lambda r: ({"request_id": "req-v7-channel", "producer": r}, {}),
    ),
    (
        "header_producer",
        lambda r: ({"request_id": "req-v7-channel"}, {"producer": r}),
    ),
    (
        "header_aggregate_id",
        lambda r: ({"request_id": "req-v7-channel"}, {"aggregate_id": r}),
    ),
    (
        "header_correlation_id",
        lambda r: ({"request_id": "req-v7-channel"}, {"correlation_id": r}),
    ),
    (
        "header_source",
        lambda r: ({"request_id": "req-v7-channel"}, {"source": r}),
    ),
    (
        "permissions",
        lambda r: ({"request_id": "req-v7-channel"}, {"permissions": [r]}),
    ),
    (
        "metadata_error_type",
        lambda r: ({"request_id": "req-v7-channel"}, {"metadata": {"error_type": r}}),
    ),
    (
        "nested_result_reference",
        lambda r: (
            {"request_id": "req-v7-channel", "result_reference": {"reference_id": r}},
            {},
        ),
    ),
    (
        "structured_reference_sequence",
        lambda r: (
            {"request_id": "req-v7-channel", "approval_refs": [{"reference_id": r}]},
            {},
        ),
    ),
    (
        "domain_reference_sequence",
        lambda r: (
            {"request_id": "req-v7-channel", "supporting_domains": [r]},
            {},
        ),
    ),
)


@pytest.mark.parametrize(
    ("label", "build"),
    SHARED_CHANNELS,
    ids=[case[0] for case in SHARED_CHANNELS],
)
@pytest.mark.parametrize("reference", TRAVERSAL_REFERENCES)
def test_traversal_is_rejected_on_every_shared_channel(
    label: str,
    build: Any,
    reference: str,
) -> None:
    """MAJOR-V7-001: one authority, therefore every persisted channel fails closed."""

    payload, header_facts = build(reference)
    system, received = _watching_system()

    with pytest.raises(REJECTIONS):
        system.publish(
            "message.received",
            payload,
            event_id=f"evt-v7-{label}-{next(_CONTROL_IDS)}",
            **header_facts,
        )

    _assert_nothing_reached_persistence(system, received)


@pytest.mark.parametrize("reference", LEGITIMATE_REFERENCES)
def test_legitimate_references_survive_the_traversal_rule(reference: str) -> None:
    """MAJOR-V7-001 control: real references are not path-shaped and stay valid."""

    system, received = _watching_system()

    event_id = f"evt-v7-ref-{next(_CONTROL_IDS)}"
    result = system.publish(
        "message.received",
        {"request_id": "req-v7-ref", "workflow_id": reference},
        event_id=event_id,
    )

    assert result.persisted is True
    assert result.event.header.workflow_id == reference
    assert len(received) == 1
    assert system.repository.count() == 1


def test_legitimate_identifiers_survive_every_canonical_header_channel() -> None:
    """MAJOR-V7-001 control: the header identifier channels keep real references."""

    system, _received = _watching_system()

    result = system.publish(
        "message.received",
        {"request_id": "req-v7-ref-header", "domain_id": "domain:legal"},
        event_id="evt-v7-ref-header",
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


def test_a_path_separator_alone_is_not_traversal() -> None:
    """MAJOR-V7-001 control: the rule rejects ``..`` segments, not every separator."""

    system, _received = _watching_system()

    result = system.publish(
        "message.received",
        {"request_id": "req-v7-sep", "workflow_id": "provider/model"},
        event_id="evt-v7-sep",
        aggregate_id="cmm/orchestration/step",
        permissions=["events:read", "events:write"],
    )

    assert result.persisted is True
    stored = system.repository.get("evt-v7-sep")
    assert stored is not None
    assert stored.header.aggregate_id == "cmm/orchestration/step"


# ══════════════════════════════════════════════════════════════════════════
# MAJOR-V7-002 — URI userinfo credentials never enter event persistence
# ══════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize("reference", URI_USERINFO_REFERENCES)
def test_uri_userinfo_in_the_payload_identifier_is_rejected(reference: str) -> None:
    """MAJOR-V7-002: the exact audited reproduction, on the payload channel."""

    system, received = _watching_system()

    with pytest.raises(REJECTIONS):
        system.publish(
            "message.received",
            {"request_id": reference},
            event_id=f"evt-v7-uri-payload-{next(_CONTROL_IDS)}",
        )

    _assert_nothing_reached_persistence(system, received)


@pytest.mark.parametrize("reference", URI_USERINFO_REFERENCES)
def test_uri_userinfo_in_the_header_producer_is_rejected(reference: str) -> None:
    """MAJOR-V7-002: the canonical header producer channel is not an escape hatch."""

    system, received = _watching_system()

    with pytest.raises(REJECTIONS):
        system.publish(
            "message.received",
            {"request_id": "req-v7-uri-producer"},
            event_id=f"evt-v7-uri-producer-{next(_CONTROL_IDS)}",
            producer=reference,
        )

    _assert_nothing_reached_persistence(system, received)


@pytest.mark.parametrize("reference", URI_USERINFO_REFERENCES)
def test_uri_userinfo_in_a_metadata_identifier_is_rejected(reference: str) -> None:
    """MAJOR-V7-002: an identifier-classified metadata fact is judged the same."""

    system, received = _watching_system()

    with pytest.raises(REJECTIONS):
        system.publish(
            "message.received",
            {"request_id": "req-v7-uri-meta"},
            event_id=f"evt-v7-uri-meta-{next(_CONTROL_IDS)}",
            metadata={"error_type": reference},
        )

    _assert_nothing_reached_persistence(system, received)


@pytest.mark.parametrize("reference", URI_USERINFO_REFERENCES)
def test_uri_userinfo_in_permissions_is_rejected(reference: str) -> None:
    """MAJOR-V7-002: every persisted identifier channel applies the one rule."""

    system, received = _watching_system()

    with pytest.raises(REJECTIONS):
        system.publish(
            "message.received",
            {"request_id": "req-v7-uri-perm"},
            event_id=f"evt-v7-uri-perm-{next(_CONTROL_IDS)}",
            permissions=[reference],
        )

    _assert_nothing_reached_persistence(system, received)


@pytest.mark.parametrize("reference", URI_USERINFO_REFERENCES)
def test_uri_userinfo_in_a_nested_structured_reference_is_rejected(
    reference: str,
) -> None:
    """MAJOR-V7-002: a nested structured reference identifier is not a bypass."""

    system, received = _watching_system()

    with pytest.raises(REJECTIONS):
        system.publish(
            "message.received",
            {
                "request_id": "req-v7-uri-structured",
                "result_reference": {"reference_id": reference},
            },
            event_id=f"evt-v7-uri-structured-{next(_CONTROL_IDS)}",
        )

    _assert_nothing_reached_persistence(system, received)


@pytest.mark.parametrize("reference", URI_USERINFO_REFERENCES)
def test_uri_userinfo_in_a_reference_sequence_is_rejected(reference: str) -> None:
    """MAJOR-V7-002: a reference sequence element is judged by the same authority."""

    system, received = _watching_system()

    with pytest.raises(REJECTIONS):
        system.publish(
            "message.received",
            {
                "request_id": "req-v7-uri-sequence",
                "supporting_domains": [reference],
            },
            event_id=f"evt-v7-uri-sequence-{next(_CONTROL_IDS)}",
        )

    _assert_nothing_reached_persistence(system, received)


@pytest.mark.parametrize("reference", PERCENT_ENCODED_USERINFO_REFERENCES)
def test_percent_encoded_uri_userinfo_is_rejected(reference: str) -> None:
    """MAJOR-V7-002: an encoded userinfo that decodes to ``name:secret`` is a credential."""

    system, received = _watching_system()

    with pytest.raises(REJECTIONS):
        system.publish(
            "message.received",
            {"request_id": "req-v7-uri-encoded", "workflow_id": reference},
            event_id=f"evt-v7-uri-encoded-{next(_CONTROL_IDS)}",
        )

    _assert_nothing_reached_persistence(system, received)


def test_the_userinfo_rule_is_semantic_not_character_set_incidental() -> None:
    """MAJOR-V7-002: the rule decodes the userinfo instead of trusting the raw text.

    The identifier grammar refuses ``%`` outright, so a percent-encoded userinfo
    never reaches persistence through the identifier channels.  That is a
    defence, not the rule: if the grammar ever admitted ``%`` the semantic check
    must already catch the decoded ``name:secret`` form.  This test proves the
    decoded-form detection itself, through the same shared authority.
    """

    from cmm.events.event_payload_safety import contains_uri_userinfo_credential

    for value in URI_USERINFO_REFERENCES + PERCENT_ENCODED_USERINFO_REFERENCES:
        assert contains_uri_userinfo_credential(value) is True

    for value in LEGITIMATE_CREDENTIAL_FREE_URIS:
        assert contains_uri_userinfo_credential(value) is False

    # A bare username is userinfo without a password component, so it is not a
    # credential by this rule; a password without a username still is.
    assert contains_uri_userinfo_credential("https://alice@example.com/db") is False
    assert contains_uri_userinfo_credential("https://:secret@example.com/db") is True
    assert contains_uri_userinfo_credential("https://alice:@example.com/db") is False


def test_uri_userinfo_in_a_manual_event_is_rejected() -> None:
    """MAJOR-V7-002: the manual publication boundary applies the same rule."""

    system, received = _watching_system()

    with pytest.raises(REJECTIONS):
        system.publish_event(
            manual_event(
                "message.received",
                {"request_id": "postgres://alice:supersecret@example.com/db"},
                event_id="evt-v7-uri-manual",
            )
        )

    _assert_nothing_reached_persistence(system, received)


def test_uri_userinfo_never_reaches_the_durable_file(tmp_path: Path) -> None:
    """MAJOR-V7-002: no durable byte may contain an audited URI password."""

    store = _durable_store(tmp_path)
    system = _file_backed_system(store)
    before = _durable_bytes(store)

    for reference in ALL_URI_USERINFO_REFERENCES:
        with pytest.raises(REJECTIONS):
            system.publish(
                "message.received",
                {"request_id": reference},
                event_id=f"evt-v7-uri-durable-{next(_CONTROL_IDS)}",
            )

    assert system.repository.count() == 0
    assert _durable_bytes(store) == before
    assert b"supersecret" not in _durable_bytes(store)
    assert b"hunter2hunter2" not in _durable_bytes(store)


def test_uri_userinfo_is_rejected_through_the_file_backed_repository(
    tmp_path: Path,
) -> None:
    """MAJOR-V7-002: the durable repository is never the safety boundary."""

    store = _durable_store(tmp_path)
    system = _file_backed_system(store)
    before = _durable_bytes(store)

    with pytest.raises(REJECTIONS):
        system.publish(
            "message.received",
            {"request_id": "https://admin:hunter2hunter2@example.com/path"},
            event_id="evt-v7-uri-file",
        )

    assert system.repository.count() == 0
    assert _durable_bytes(store) == before


def test_the_uri_password_never_appears_in_the_rejection_message() -> None:
    """MAJOR-V7-002: the gate refuses without echoing the secret it refused."""

    system, _received = _watching_system()

    with pytest.raises(REJECTIONS) as captured:
        system.publish(
            "message.received",
            {"request_id": "https://admin:hunter2hunter2@example.com/path"},
            event_id="evt-v7-uri-echo",
        )

    assert "hunter2hunter2" not in str(captured.value)
    assert "supersecret" not in str(captured.value)


@pytest.mark.parametrize(
    ("label", "build"),
    SHARED_CHANNELS,
    ids=[case[0] for case in SHARED_CHANNELS],
)
@pytest.mark.parametrize("reference", URI_USERINFO_REFERENCES)
def test_uri_userinfo_is_rejected_on_every_shared_channel(
    label: str,
    build: Any,
    reference: str,
) -> None:
    """MAJOR-V7-002: one authority, therefore every persisted channel fails closed."""

    payload, header_facts = build(reference)
    system, received = _watching_system()

    with pytest.raises(REJECTIONS):
        system.publish(
            "message.received",
            payload,
            event_id=f"evt-v7-{label}-{next(_CONTROL_IDS)}",
            **header_facts,
        )

    _assert_nothing_reached_persistence(system, received)


@pytest.mark.parametrize(
    "reference", LEGITIMATE_CREDENTIAL_FREE_URIS + LEGITIMATE_REFERENCES
)
def test_credential_free_uris_and_references_survive(reference: str) -> None:
    """MAJOR-V7-002 control: only semantic userinfo credentials are refused."""

    system, received = _watching_system()

    result = system.publish(
        "message.received",
        {"request_id": "req-v7-uri-ref", "workflow_id": reference},
        event_id=f"evt-v7-uri-ref-{next(_CONTROL_IDS)}",
    )

    assert result.persisted is True
    assert result.event.header.workflow_id == reference
    assert len(received) == 1


def test_credential_free_uris_survive_the_canonical_header_channels() -> None:
    """MAJOR-V7-002 control: a credential-free URI is a legitimate public reference."""

    system, _received = _watching_system()

    result = system.publish(
        "message.received",
        {"request_id": "req-v7-uri-header"},
        event_id="evt-v7-uri-header",
        producer="cmm.orchestration",
        aggregate_id="https://example.com/model",
        permissions=["events:read"],
    )

    assert result.persisted is True
    stored = system.repository.get("evt-v7-uri-header")
    assert stored is not None
    assert stored.header.aggregate_id == "https://example.com/model"
    assert stored.header.permissions == ["events:read"]


# ══════════════════════════════════════════════════════════════════════════
# The two V7 rules are one shared authority, not a request_id-only patch
# ══════════════════════════════════════════════════════════════════════════


def test_the_shared_identifier_authority_is_the_one_used_by_every_channel() -> None:
    """MAJOR-V7-001/002: the shared authority is the single point of enforcement."""

    from cmm.events import event_payload_safety

    rejected = TRAVERSAL_REFERENCES + URI_USERINFO_REFERENCES
    accepted = LEGITIMATE_REFERENCES + LEGITIMATE_CREDENTIAL_FREE_URIS

    for value in rejected:
        with pytest.raises(PlatformEventPayloadError):
            event_payload_safety.validate_platform_identifier(value, field="probe")
    for value in accepted:
        assert (
            event_payload_safety.validate_platform_identifier(value, field="probe")
            == value
        )


def test_the_public_path_classifier_reports_traversal() -> None:
    """MAJOR-V7-001: the existing classifier answers traversal, not a new module."""

    from cmm.events.event_payload_safety import is_private_filesystem_reference

    for value in ALL_TRAVERSAL_REFERENCES:
        assert is_private_filesystem_reference(value) is True
    for value in LEGITIMATE_REFERENCES + LEGITIMATE_CREDENTIAL_FREE_URIS:
        assert is_private_filesystem_reference(value) is False


def test_no_second_path_or_credential_policy_module_was_added() -> None:
    """Architecture guard: the V7 fix extends the existing authority in place."""

    import cmm.events.event_payload_safety as authority

    module_files = {path.name for path in Path(authority.__file__).parent.glob("*.py")}
    assert "event_path_policy.py" not in module_files
    assert "event_credential_policy.py" not in module_files
    assert "identifier_policy.py" not in module_files
