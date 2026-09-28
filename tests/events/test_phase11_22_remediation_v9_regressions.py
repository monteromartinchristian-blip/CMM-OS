"""Phase 11.22 — Remediation V9 adversarial regressions.

These tests make the independent Re-audit V9 reproductions executable and
permanent.  Each V9 finding gets its own named test; no finding is hidden inside
another test's assertions.

Covered findings::

    MAJOR-V9-001  the shared identifier/path safety authority recognized a
                  ``file:`` reference only as an *authority-bearing* URI
                  (``scheme://authority``) or at character zero (``^file:``).  A
                  **non-authority** ``file:`` reference reached through a public
                  logical wrapper was therefore classified as a public reference:
                  ``provider/file:C:/Windows/System32/config/SAM`` returned
                  non-private from the classifier, passed the canonical identifier
                  validator, passed canonical ``EventSystem`` publication and was
                  durably persisted.  ``cmm/file:…``, ``provider/file:/…`` and the
                  POSIX/macOS spellings behaved the same way.  The outer public
                  slash-root allowlist accepted the wrapper, so the unsafe local
                  semantics hidden behind it were never classified.
    MAJOR-V9-002  the canonical Phase 11.22 timestamp authority delegated the
                  civil-hour bound to ``datetime.fromisoformat``.  CPython 3.14
                  widened that parser to accept the ISO end-of-day spelling
                  ``24:00`` and roll it into the next day, so the retained V6
                  regression case ``2026-09-27T24:00:00Z`` was accepted and
                  persisted on the canonical runtime although the frozen Phase
                  11.22 contract admits only hours ``00..23``.  The persisted
                  timestamp contract was therefore interpreter-version dependent.

Both findings are exercised through the real canonical components — the public
``EventSystem`` facade, the canonical factory/registry/bus/DLQ and both official
repository implementations (in-memory and file-backed).  Nothing is mocked.

The shared identifier authority is one function, so every persisted channel is
covered here explicitly rather than by patching ``request_id`` alone::

    payload identifier fields          (``request_id``, ``workflow_id``, ...)
    header producer                    (``producer`` and the other header facts)
    permissions                        (``permissions[]``)
    metadata identifier facts          (``metadata.error_type``)
    nested structured references       (``result_reference.reference_id``)
    reference sequences                (``supporting_domains[]``, ``approval_refs[]``)

Every adversarial test here reproduces the behaviour the independent Re-audit V9
reported, so it fails before the remediation and passes after it.
"""

from __future__ import annotations

import itertools
import os
import pathlib
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

MOMENT = datetime(2026, 9, 28, 12, 0, 0, tzinfo=timezone.utc)

REJECTIONS = (PlatformEventPayloadError, TypeError, ValueError)

#: A monotonic counter so every adversarial case gets a fresh, plain-safe
#: canonical event identity instead of deriving one from the audited value.
_CONTROL_IDS = itertools.count()


# ══════════════════════════════════════════════════════════════════════════
# MAJOR-V9-001 — a wrapped non-authority ``file:`` reference is not public-safe
# ══════════════════════════════════════════════════════════════════════════

#: The wrapped non-authority ``file:`` references the independent Re-audit V9
#: demonstrated being **accepted and durably persisted**.  Every member of this
#: tuple is admitted by the shared identifier grammar (so the character-set rule
#: cannot refuse it) and is accepted by the pre-V9 filesystem classifier, because
#: the ``file:`` token is not at character zero and carries no ``//`` authority.
REPORTED_WRAPPED_FILE_URI_REFERENCES = (
    "provider/file:C:/Windows/System32/config/SAM",
    "cmm/file:C:/Windows/System32/config/SAM",
    "provider/file:C:/Windows/System32/config/SECURITY",
    "provider/file:/Windows/System32/config/SAM",
    "provider/file:C:/ProgramData/Microsoft/Crypto/RSA/MachineKeys",
)

#: The wrapped spellings of already-recognized sensitive locations.  These were
#: refused before V9 only because the *location* signature (``etc/shadow``) also
#: matched; they are retained here so the ``file:`` rule is proven to carry them
#: independently of any location list.
WRAPPED_FILE_URI_SENSITIVE_LOCATIONS = (
    "provider/file:/etc/shadow",
    "cmm/file:/private/var/db/keychains",
    "provider/file:/var/db/dslocal/nodes/Default/users/root.plist",
    "provider/file:C:/Users/alice/.ssh/id_rsa",
    "provider/file:/etc/hosts",
)

#: Fresh V9 probes: the same wrapped ``file:`` semantics through the other
#: plausible wrappers and locations the audit did not name.  Each one is accepted
#: by the pre-V9 classifier, so the fix cannot be a pair of literal exceptions.
FRESH_WRAPPED_FILE_URI_REFERENCES = (
    "provider/file:/Library/Keychains/login.keychain-db",
    "cmm/file:/Library/Keychains/login.keychain-db",
    "cmm/file:/Windows/System32/config/SAM",
    "provider/file:/boot/grub/grub.cfg",
    "cmm/file:/Applications/Secrets.app/Contents/Resources/key",
)

#: Unsafe top-level ``file:`` references.  These are the retained controls: the
#: frozen contract already refused them, and the V9 fix must keep refusing them.
TOP_LEVEL_FILE_URI_REFERENCES = (
    "file:/etc/shadow",
    "file:///etc/shadow",
    "file:C:/Windows/System32/config/SAM",
    "file://server/share/secret",
)

#: Every wrapped ``file:`` reference the classifier must refuse: the V9 audit
#: reproductions, the wrapped sensitive locations, and the fresh probes.
WRAPPED_FILE_URI_REFERENCES = (
    REPORTED_WRAPPED_FILE_URI_REFERENCES
    + WRAPPED_FILE_URI_SENSITIVE_LOCATIONS
    + FRESH_WRAPPED_FILE_URI_REFERENCES
)

#: The complete non-public ``file:`` corpus, top-level and wrapped.
ALL_FILE_URI_REFERENCES = TOP_LEVEL_FILE_URI_REFERENCES + WRAPPED_FILE_URI_REFERENCES

#: Structurally adjacent wrapper spellings that are meaningful under the existing
#: grammar and must receive the *same* verdict as the audited spelling: a repeated
#: separator, a ``.`` current-directory segment, a trailing separator and the
#: case variants of the scheme/wrapper.  ``file:`` is a case-insensitive URI
#: scheme, so ``FILE:`` is the same unsafe local reference.
WRAPPED_FILE_URI_EQUIVALENCE_FAMILIES = (
    (
        "provider/file:C:/Windows/System32/config/SAM",
        "provider//file:C:/Windows/System32/config/SAM",
        "provider/./file:C:/Windows/System32/config/SAM",
        "provider/file:C:/Windows/System32/config/SAM/",
        "Provider/File:C:/Windows/System32/config/SAM",
        "PROVIDER/FILE:C:/Windows/System32/config/SAM",
    ),
    (
        "cmm/file:C:/Windows/System32/config/SAM",
        "cmm//file:C:/Windows/System32/config/SAM",
        "cmm/./file:C:/Windows/System32/config/SAM",
        "CMM/File:C:/Windows/System32/config/SAM",
    ),
    (
        "provider/file:/etc/shadow",
        "provider//file:/etc/shadow",
        "provider/./file:/etc/shadow",
        "file:/etc/shadow",
        "File:/etc/shadow",
    ),
    (
        "provider/file:/Library/Keychains/login.keychain-db",
        "provider//file:/Library/Keychains/login.keychain-db",
        "provider/./file:/Library/Keychains/login.keychain-db",
    ),
)

#: Every spelling in every equivalence family.  The whole family is one location
#: with one required classification: refused.
WRAPPED_FILE_URI_EQUIVALENT_SPELLINGS = tuple(
    spelling for family in WRAPPED_FILE_URI_EQUIVALENCE_FAMILIES for spelling in family
)

#: Wrapped ``file:`` spellings that the outer identifier grammar refuses earlier,
#: because ``\`` is not in the accepted identifier character set.  These are
#: recorded as positive fail-closed facts: the grammar does not have to be widened
#: to refuse them.
BACKSLASH_FILE_URI_REFERENCES = (
    "provider/file:C:\\Windows\\System32\\config\\SAM",
    "provider\\file:C:\\Windows\\System32\\config\\SAM",
)

#: Public references that must survive the V9 rule untouched.  Every member is a
#: form the existing contract actually admits.
PUBLIC_REFERENCES_UNCHANGED = (
    "provider/model",
    "provider//model",
    "provider/./model",
    "cmm/orchestration/step",
    "workflow:123",
    "domain:legal",
    "cmm.orchestration",
    "events:read",
    "CORR-ORIGINAL",
    "user-42",
)

#: Credential-free URI references that must survive the V9 rule untouched.
CREDENTIAL_FREE_URIS_UNCHANGED = (
    "https://example.com/model",
    "http://localhost:8080/health",
    "postgres://example.com/db",
    "jdbc:postgresql://example.com/db",
    "provider/https://example.com/model",
    "urn:cmm:event:message.received",
)

#: Colon-bearing logical identifiers whose ``file`` token does *not* begin a path
#: segment.  Under RFC 3986 the scheme of ``workflow:file:123`` is ``workflow``, so
#: it is an ordinary logical identifier and not a ``file:`` URI.  The V9 rule must
#: stay segment-scoped rather than becoming a substring search for ``file:``.
COLON_LOGICAL_IDENTIFIERS_UNCHANGED = (
    "workflow:file:123",
    "domain:file:legal",
    "req:file:mod",
    "cmm:file:reference",
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
    event_id: str = "evt-v9-manual",
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


#: Every shared persisted identifier channel, as a ``(label, builder)`` pair whose
#: builder places one audited reference into that channel and returns
#: ``(payload, header_facts)``.  Enumerating them keeps the coverage reviewable and
#: makes "do not patch ``request_id`` only" an executable claim.
SHARED_CHANNELS = (
    ("payload_request_id", lambda r: ({"request_id": r}, {})),
    (
        "payload_workflow_id",
        lambda r: ({"request_id": "req-v9-channel", "workflow_id": r}, {}),
    ),
    (
        "payload_aggregate_id",
        lambda r: ({"request_id": "req-v9-channel", "aggregate_id": r}, {}),
    ),
    (
        "payload_producer",
        lambda r: ({"request_id": "req-v9-channel", "producer": r}, {}),
    ),
    ("header_producer", lambda r: ({"request_id": "req-v9-channel"}, {"producer": r})),
    (
        "header_aggregate_id",
        lambda r: ({"request_id": "req-v9-channel"}, {"aggregate_id": r}),
    ),
    (
        "header_correlation_id",
        lambda r: ({"request_id": "req-v9-channel"}, {"correlation_id": r}),
    ),
    ("header_source", lambda r: ({"request_id": "req-v9-channel"}, {"source": r})),
    (
        "permissions",
        lambda r: ({"request_id": "req-v9-channel"}, {"permissions": [r]}),
    ),
    (
        "metadata_error_type",
        lambda r: ({"request_id": "req-v9-channel"}, {"metadata": {"error_type": r}}),
    ),
    (
        "nested_result_reference",
        lambda r: (
            {"request_id": "req-v9-channel", "result_reference": {"reference_id": r}},
            {},
        ),
    ),
    (
        "structured_reference_sequence",
        lambda r: (
            {"request_id": "req-v9-channel", "approval_refs": [{"reference_id": r}]},
            {},
        ),
    ),
    (
        "domain_reference_sequence",
        lambda r: (
            {"request_id": "req-v9-channel", "supporting_domains": [r]},
            {},
        ),
    ),
)

_SHARED_CHANNEL_IDS = [case[0] for case in SHARED_CHANNELS]


# ── the classifier itself ──────────────────────────────────────────────────


@pytest.mark.parametrize("reference", WRAPPED_FILE_URI_REFERENCES)
def test_the_classifier_refuses_a_wrapped_non_authority_file_uri(
    reference: str,
) -> None:
    """MAJOR-V9-001: the ``file:`` signature is not anchored at character zero."""

    from cmm.events.event_payload_safety import is_private_filesystem_reference

    assert is_private_filesystem_reference(reference) is True, reference


@pytest.mark.parametrize("reference", TOP_LEVEL_FILE_URI_REFERENCES)
def test_the_classifier_still_refuses_a_top_level_file_uri(reference: str) -> None:
    """MAJOR-V9-001: the retained top-level controls keep their verdict."""

    from cmm.events.event_payload_safety import is_private_filesystem_reference

    assert is_private_filesystem_reference(reference) is True, reference


@pytest.mark.parametrize("reference", WRAPPED_FILE_URI_EQUIVALENT_SPELLINGS)
def test_every_wrapped_file_uri_spelling_is_classified_identically(
    reference: str,
) -> None:
    """MAJOR-V9-001: one location, one verdict — no spelling may be admitted.

    ``WRAPPED_FILE_URI_REFERENCES_HAVE_THE_SAME_UNSAFE_CLASSIFICATION_AS_TOP_LEVEL_FILE_URI_REFERENCES``
    """

    from cmm.events.event_payload_safety import is_private_filesystem_reference

    assert is_private_filesystem_reference(reference) is True, reference


@pytest.mark.parametrize(
    "family",
    WRAPPED_FILE_URI_EQUIVALENCE_FAMILIES,
    ids=lambda family: family[0].replace("/", "_").replace(":", "-"),
)
def test_wrapped_file_uri_equivalence_families_share_one_verdict(
    family: tuple[str, ...],
) -> None:
    """MAJOR-V9-001: equivalent spellings of one location never disagree."""

    from cmm.events import event_payload_safety as authority

    verdicts = {
        authority.is_private_filesystem_reference(spelling) for spelling in family
    }
    assert verdicts == {True}, family


def test_the_identifier_grammar_admits_the_wrapper_so_the_classifier_must_refuse() -> (
    None
):
    """MAJOR-V9-001: the bypass is a classifier defect, not a grammar defect.

    The V9 reproductions are single safe-character tokens.  The refusal therefore
    has to come from the filesystem classifier; if this assertion ever fails the
    finding has moved and this module no longer proves what it claims.
    """

    from cmm.events import event_payload_safety as authority

    for reference in WRAPPED_FILE_URI_REFERENCES:
        assert authority._SAFE_IDENTIFIER_PATTERN.match(reference) is not None, (
            reference
        )
        assert authority.is_private_filesystem_reference(reference) is True, reference


def test_the_wrapped_file_uri_rule_is_not_a_reproduced_filename_denylist() -> None:
    """MAJOR-V9-001: the rule is structural, so an unnamed location is refused too.

    The audit named ``Windows/System32/config/SAM`` and ``.../SECURITY``.  No
    pattern mentions those location names, and the fresh probes name locations no
    pattern mentions either, yet all of them are refused.  The V9 fix is therefore
    a structural classification of the wrapped ``file:`` scheme rather than a
    literal appended for each audited string.
    """

    from cmm.events import event_payload_safety as authority

    pattern_sources = " ".join(
        pattern.pattern for pattern in authority._PRIVATE_FILESYSTEM_PATTERNS
    )
    for audited_name in ("SAM", "SECURITY", "MachineKeys", "System32", "ProgramData"):
        assert audited_name not in pattern_sources, audited_name

    for reference in FRESH_WRAPPED_FILE_URI_REFERENCES:
        assert authority.is_private_filesystem_reference(reference) is True, reference


def test_the_wrapped_file_uri_classifier_performs_no_filesystem_io() -> None:
    """MAJOR-V9-001: classification stays lexical — no I/O and no resolution."""

    from cmm.events import event_payload_safety as authority

    def _forbidden(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("the path classifier must not touch the filesystem")

    targets = (
        (pathlib.Path, "resolve"),
        (pathlib.Path, "stat"),
        (pathlib.Path, "is_file"),
        (pathlib.Path, "is_dir"),
        (os.path, "realpath"),
        (os.path, "abspath"),
        (os, "lstat"),
        (os, "readlink"),
    )
    saved = [(holder, name, getattr(holder, name)) for holder, name in targets]
    try:
        for holder, name in targets:
            setattr(holder, name, _forbidden)
        for reference in ALL_FILE_URI_REFERENCES:
            assert authority.is_private_filesystem_reference(reference) is True
        for reference in (
            PUBLIC_REFERENCES_UNCHANGED
            + CREDENTIAL_FREE_URIS_UNCHANGED
            + COLON_LOGICAL_IDENTIFIERS_UNCHANGED
        ):
            assert authority.is_private_filesystem_reference(reference) is False
    finally:
        for holder, name, original in saved:
            setattr(holder, name, original)


def test_the_wrapped_file_uri_rule_reuses_the_existing_safety_authority() -> None:
    """MAJOR-V9-001: no second path/URI policy module was introduced."""

    import cmm.events.event_payload_safety as authority

    module_files = {path.name for path in Path(authority.__file__).parent.glob("*.py")}
    assert "event_path_policy.py" not in module_files
    assert "event_file_uri_policy.py" not in module_files
    assert "identifier_policy.py" not in module_files
    assert "path_canonicalization.py" not in module_files


# ── the shared identifier authority ────────────────────────────────────────


@pytest.mark.parametrize("reference", WRAPPED_FILE_URI_REFERENCES)
def test_the_identifier_authority_refuses_a_wrapped_file_uri(reference: str) -> None:
    """MAJOR-V9-001: the shared validator refuses every wrapped spelling."""

    from cmm.events.event_payload_safety import validate_platform_identifier

    with pytest.raises(REJECTIONS):
        validate_platform_identifier(reference, field="probe")


@pytest.mark.parametrize("reference", BACKSLASH_FILE_URI_REFERENCES)
def test_backslash_file_uri_spellings_are_refused_by_the_identifier_grammar(
    reference: str,
) -> None:
    """MAJOR-V9-001: ``\\`` is outside the grammar, so it is refused earlier.

    This is a positive fail-closed fact: the V9 fix does not need to widen the
    identifier grammar to cover the Windows-backslash spelling.
    """

    from cmm.events import event_payload_safety as authority

    assert authority._SAFE_IDENTIFIER_PATTERN.match(reference) is None, reference
    with pytest.raises(REJECTIONS):
        authority.validate_platform_identifier(reference, field="probe")


@pytest.mark.parametrize(
    "reference", PUBLIC_REFERENCES_UNCHANGED + CREDENTIAL_FREE_URIS_UNCHANGED
)
def test_supported_public_references_are_still_accepted(reference: str) -> None:
    """MAJOR-V9-001 positive control: the fix does not over-correct."""

    from cmm.events.event_payload_safety import validate_platform_identifier

    assert validate_platform_identifier(reference, field="probe") == reference


@pytest.mark.parametrize("reference", COLON_LOGICAL_IDENTIFIERS_UNCHANGED)
def test_colon_bearing_logical_identifiers_are_still_accepted(reference: str) -> None:
    """MAJOR-V9-001 positive control: not every ``file:`` substring is a URI."""

    from cmm.events.event_payload_safety import validate_platform_identifier

    assert validate_platform_identifier(reference, field="probe") == reference


def test_the_wrapped_file_uri_refusal_message_is_static() -> None:
    """MAJOR-V9-001: the refusal never echoes the audited local location."""

    from cmm.events.event_payload_safety import validate_platform_identifier

    reference = "provider/file:C:/Windows/System32/config/SAM"
    with pytest.raises(PlatformEventPayloadError) as excinfo:
        validate_platform_identifier(reference, field="probe")

    message = str(excinfo.value)
    assert "provider" not in message
    assert "SAM" not in message
    assert reference not in message
    assert "private filesystem location" in message


# ── the canonical EventSystem ──────────────────────────────────────────────


@pytest.mark.parametrize("reference", REPORTED_WRAPPED_FILE_URI_REFERENCES)
def test_the_event_system_refuses_a_reported_wrapped_file_uri(
    reference: str,
) -> None:
    """MAJOR-V9-001: canonical publication refuses before persistence."""

    system, received = _watching_system()

    with pytest.raises(REJECTIONS):
        system.publish(
            "message.received",
            {"request_id": reference},
            event_id=f"evt-v9-ts-{next(_CONTROL_IDS)}",
        )

    _assert_nothing_reached_persistence(system, received)


@pytest.mark.parametrize("reference", WRAPPED_FILE_URI_REFERENCES)
def test_the_file_backed_repository_persists_nothing_for_a_wrapped_file_uri(
    tmp_path: Path, reference: str
) -> None:
    """MAJOR-V9-001: the durable store is byte-identical after refusal."""

    store = _durable_store(tmp_path)
    system = _file_backed_system(store)
    before = _durable_bytes(store)

    with pytest.raises(REJECTIONS):
        system.publish(
            "message.received",
            {"request_id": reference},
            event_id=f"evt-v9-durable-{next(_CONTROL_IDS)}",
        )

    assert system.repository.count() == 0
    assert system.dead_letter_count() == 0
    assert _durable_bytes(store) == before
    assert not store.exists() or store.read_bytes() == b""


@pytest.mark.parametrize("reference", WRAPPED_FILE_URI_REFERENCES)
def test_a_manual_publish_event_cannot_bypass_the_wrapped_file_uri_rule(
    reference: str,
) -> None:
    """MAJOR-V9-001: the manual canonical boundary re-applies the same rule."""

    system, received = _watching_system()
    event = manual_event(
        "message.received",
        {"request_id": reference},
        event_id=f"evt-v9-manual-{next(_CONTROL_IDS)}",
    )

    with pytest.raises(REJECTIONS):
        system.publish_event(event)

    _assert_nothing_reached_persistence(system, received)


# ── every shared persisted identifier channel ─────────────────────────────


@pytest.mark.parametrize(
    ("label", "build"),
    SHARED_CHANNELS,
    ids=_SHARED_CHANNEL_IDS,
)
@pytest.mark.parametrize(
    "reference",
    REPORTED_WRAPPED_FILE_URI_REFERENCES,
    ids=lambda reference: reference.replace("/", "_").replace(":", "-"),
)
def test_every_shared_channel_refuses_the_reported_wrapped_file_uri(
    label: str, build: Any, reference: str
) -> None:
    """MAJOR-V9-001: all 13 shared channels refuse, not just ``request_id``."""

    payload, header_facts = build(reference)
    system, received = _watching_system()

    with pytest.raises(REJECTIONS):
        system.publish(
            "message.received",
            payload,
            event_id=f"evt-v9-channel-{label}-{next(_CONTROL_IDS)}",
            **header_facts,
        )

    _assert_nothing_reached_persistence(system, received)


@pytest.mark.parametrize(
    ("label", "build"),
    SHARED_CHANNELS,
    ids=_SHARED_CHANNEL_IDS,
)
def test_every_shared_channel_leaves_the_durable_store_untouched(
    tmp_path: Path, label: str, build: Any
) -> None:
    """MAJOR-V9-001: refusal is proven by the durable store, per channel."""

    store = _durable_store(tmp_path)
    system = _file_backed_system(store)
    payload, header_facts = build(REPORTED_WRAPPED_FILE_URI_REFERENCES[0])
    before = _durable_bytes(store)

    with pytest.raises(REJECTIONS):
        system.publish(
            "message.received",
            payload,
            event_id=f"evt-v9-durable-channel-{label}",
            **header_facts,
        )

    assert system.repository.count() == 0
    assert system.dead_letter_count() == 0
    assert _durable_bytes(store) == before


@pytest.mark.parametrize(
    ("label", "build"),
    SHARED_CHANNELS,
    ids=_SHARED_CHANNEL_IDS,
)
@pytest.mark.parametrize(
    "reference",
    PUBLIC_REFERENCES_UNCHANGED,
    ids=lambda reference: reference.replace("/", "_").replace(":", "-"),
)
def test_every_shared_channel_still_accepts_a_public_reference(
    label: str, build: Any, reference: str
) -> None:
    """MAJOR-V9-001 positive control: public references persist on every channel."""

    payload, header_facts = build(reference)
    system, received = _watching_system()

    result = system.publish(
        "message.received",
        payload,
        event_id=f"evt-v9-ok-{label}-{next(_CONTROL_IDS)}",
        **header_facts,
    )

    assert result.persisted is True
    assert system.repository.count() == 1
    assert len(received) == 1
    assert system.dead_letter_count() == 0


# ══════════════════════════════════════════════════════════════════════════
# MAJOR-V9-002 — the timestamp contract must not depend on the interpreter
# ══════════════════════════════════════════════════════════════════════════

#: The retained V6 civil-time case, plus the structurally adjacent end-of-day
#: spellings the same widened parser accepts.  CPython 3.14.7 accepts every one of
#: them through ``datetime.fromisoformat``, rolling each into the next day, so the
#: pre-V9 authority persisted them although the frozen contract admits ``00..23``.
END_OF_DAY_TIMESTAMPS = (
    "2026-09-27T24:00:00Z",
    "2026-09-27T24:00Z",
    "2026-09-27T24:00:00+00:00",
    "2026-09-27T24:00:00-05:00",
    "2026-09-27 24:00:00Z",
    "2026-09-27T24:00:00.000000Z",
)

#: Civil-time bounds that were already refused explicitly or by the interpreter
#: before V9.  The fix must not disturb them.
RETAINED_INVALID_TIMESTAMPS = (
    "9999-99-99T99:99Z",
    "2026-13-01T12:00:00Z",
    "2026-02-31T12:00:00Z",
    "2026-04-31T12:00:00Z",
    "2026-09-27T25:00:00Z",
    "2026-09-27T25:61:00Z",
    "2026-09-27T24:00:00.123456Z",
    "2026-09-27T24:01:00Z",
    "2026-09-27T12:61:00Z",
    "2026-09-27T12:00:61Z",
    "2026-09-27T12:00:00+25:00",
    "2026-09-27T12:00",
    "2026-09-27T12:00:00",
    "2026-09-27",
)

#: Timestamps the frozen Phase 11.22 contract admits.  The hour bound must reject
#: ``24:00`` without touching the last hour of a day or the first of the next.
VALID_TIMESTAMPS = (
    "2026-09-27T00:00:00Z",
    "2026-09-27T12:00:00Z",
    "2026-09-27T23:00:00Z",
    "2026-09-27T23:59:59Z",
    "2026-09-27T23:59Z",
    "2026-09-28T00:00:00Z",
    "2026-09-27T12:00:00.123456Z",
    "2026-09-27T12:00:00+02:00",
    "2026-09-27T12:00:00-05:00",
    "2026-09-27 12:00:00Z",
    "2026-12-31T23:59:59Z",
    "2027-01-01T00:00:00Z",
)

#: The explicit frozen verdict table: ``(timestamp, accepted)``.  It is the Phase
#: 11.22 contract written down, so the authority is checked against the contract
#: rather than against whatever the running interpreter happens to parse.
TIMESTAMP_VERDICT_TABLE = (
    tuple((timestamp, False) for timestamp in END_OF_DAY_TIMESTAMPS)
    + tuple((timestamp, False) for timestamp in RETAINED_INVALID_TIMESTAMPS)
    + tuple((timestamp, True) for timestamp in VALID_TIMESTAMPS)
)


@pytest.mark.parametrize("timestamp", END_OF_DAY_TIMESTAMPS)
def test_the_canonical_timestamp_authority_rejects_the_end_of_day_spelling(
    timestamp: str,
) -> None:
    """MAJOR-V9-002: ``PHASE11_22_TIMESTAMP_ACCEPTANCE_IS_INTERPRETER_VERSION_INDEPENDENT``."""

    from cmm.events.event_payload_safety import (
        _parse_canonical_timestamp,
        _validate_canonical_timestamp,
    )

    with pytest.raises(REJECTIONS):
        _validate_canonical_timestamp(timestamp, field="occurred_at")
    with pytest.raises(REJECTIONS):
        _parse_canonical_timestamp(timestamp, field="occurred_at")


@pytest.mark.parametrize(
    ("timestamp", "accepted"),
    TIMESTAMP_VERDICT_TABLE,
    ids=lambda value: str(value).replace(":", "").replace("+", "p").replace(" ", "_"),
)
def test_the_frozen_timestamp_verdict_table_holds(
    timestamp: str, accepted: bool
) -> None:
    """MAJOR-V9-002: the written contract, not the interpreter, decides."""

    from cmm.events.event_payload_safety import _validate_canonical_timestamp

    if accepted:
        assert (
            _validate_canonical_timestamp(timestamp, field="occurred_at") == timestamp
        )
        return
    with pytest.raises(REJECTIONS):
        _validate_canonical_timestamp(timestamp, field="occurred_at")


def test_the_civil_hour_bound_is_not_delegated_to_the_interpreter_parser(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """MAJOR-V9-002: a *wider* interpreter parser cannot widen the contract.

    The authority is re-run with the parser subrogated by a hypothetical future
    interpreter that accepts everything the shape admits.  Every frozen verdict
    must be unchanged, which is only possible if the hour bound is enforced by the
    Phase 11.22 authority itself rather than by ``datetime.fromisoformat``.
    """

    from cmm.events import event_payload_safety as authority

    class _PermissiveDatetime(datetime):
        """A parser that accepts every shape the canonical pattern admits."""

        @classmethod
        def fromisoformat(cls, value: str) -> _PermissiveDatetime:
            return cls(2026, 9, 28, 0, 0, tzinfo=timezone.utc)

    monkeypatch.setattr(authority, "datetime", _PermissiveDatetime)

    for timestamp in END_OF_DAY_TIMESTAMPS + RETAINED_INVALID_TIMESTAMPS:
        with pytest.raises(REJECTIONS):
            authority._validate_canonical_timestamp(timestamp, field="occurred_at")
    for timestamp in VALID_TIMESTAMPS:
        assert (
            authority._validate_canonical_timestamp(timestamp, field="occurred_at")
            == timestamp
        )


def test_the_end_of_day_spelling_is_refused_before_any_interpreter_parse(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """MAJOR-V9-002: the bound is applied without consulting the parser."""

    from cmm.events import event_payload_safety as authority

    class _ExplodingDatetime(datetime):
        """A parser that fails loudly if it is reached at all."""

        @classmethod
        def fromisoformat(cls, value: str) -> _ExplodingDatetime:
            raise AssertionError("hour 24 must be refused before any parse")

    monkeypatch.setattr(authority, "datetime", _ExplodingDatetime)

    for timestamp in END_OF_DAY_TIMESTAMPS:
        with pytest.raises(PlatformEventPayloadError):
            authority._validate_canonical_timestamp(timestamp, field="occurred_at")


@pytest.mark.parametrize("timestamp", END_OF_DAY_TIMESTAMPS)
def test_the_end_of_day_spelling_never_reaches_persistence(timestamp: str) -> None:
    """MAJOR-V9-002: an in-memory publication refuses before persistence."""

    system, received = _watching_system()

    with pytest.raises(REJECTIONS):
        system.publish(
            "message.received",
            {"request_id": "req-v9-ts", "occurred_at": timestamp},
            event_id=f"evt-v9-ts-{next(_CONTROL_IDS)}",
        )

    _assert_nothing_reached_persistence(system, received)


@pytest.mark.parametrize("timestamp", END_OF_DAY_TIMESTAMPS)
def test_the_end_of_day_spelling_leaves_the_durable_store_untouched(
    tmp_path: Path, timestamp: str
) -> None:
    """MAJOR-V9-002: the file-backed store is byte-identical after refusal."""

    store = _durable_store(tmp_path)
    system = _file_backed_system(store)
    before = _durable_bytes(store)

    with pytest.raises(REJECTIONS):
        system.publish(
            "message.received",
            {"request_id": "req-v9-ts", "occurred_at": timestamp},
            event_id=f"evt-v9-ts-durable-{next(_CONTROL_IDS)}",
        )

    assert system.repository.count() == 0
    assert system.dead_letter_count() == 0
    assert _durable_bytes(store) == before


@pytest.mark.parametrize("timestamp", END_OF_DAY_TIMESTAMPS)
def test_a_manual_publish_event_cannot_bypass_the_civil_hour_bound(
    timestamp: str,
) -> None:
    """MAJOR-V9-002: the manual canonical boundary re-applies the same bound."""

    system, received = _watching_system()
    event = manual_event(
        "message.received",
        {"request_id": "req-v9-ts", "occurred_at": timestamp},
        event_id=f"evt-v9-ts-manual-{next(_CONTROL_IDS)}",
    )

    with pytest.raises(REJECTIONS):
        system.publish_event(event)

    _assert_nothing_reached_persistence(system, received)


@pytest.mark.parametrize("timestamp", VALID_TIMESTAMPS)
def test_valid_timezone_aware_timestamps_still_persist(timestamp: str) -> None:
    """MAJOR-V9-002 positive control: every admitted timestamp is unchanged.

    ``emitted_at`` is supplied explicitly so the publication also satisfies the
    pre-existing canonical chronology rule (``emitted_at >= occurred_at``) for the
    controls whose ``occurred_at`` lies in the future; that rule is untouched here.
    """

    system, received = _watching_system()

    result = system.publish(
        "message.received",
        {"request_id": "req-v9-ts-ok", "occurred_at": timestamp},
        event_id=f"evt-v9-ts-ok-{next(_CONTROL_IDS)}",
        emitted_at=datetime(2030, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
    )

    assert result.persisted is True
    assert system.repository.count() == 1
    assert len(received) == 1
    assert system.dead_letter_count() == 0


def test_normalization_behavior_of_accepted_timestamps_is_unchanged() -> None:
    """MAJOR-V9-002: the guard rejects; it never repairs or rewrites a value."""

    from cmm.events.event_payload_safety import (
        _parse_canonical_timestamp,
        _validate_canonical_timestamp,
    )

    for timestamp in VALID_TIMESTAMPS:
        assert (
            _validate_canonical_timestamp(timestamp, field="occurred_at") == timestamp
        )
        parsed = _parse_canonical_timestamp(timestamp, field="occurred_at")
        assert parsed.tzinfo is not None
        assert parsed.utcoffset() is not None

    # The retained V6 contract still requires a real timezone-aware instant.
    assert _parse_canonical_timestamp(
        "2026-09-27T23:59:59Z", field="occurred_at"
    ) == datetime(2026, 9, 27, 23, 59, 59, tzinfo=timezone.utc)
