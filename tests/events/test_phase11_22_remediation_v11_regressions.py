"""Phase 11.22 — Remediation V11 adversarial regressions.

These tests make the independent Re-audit V11 reproduction executable and
permanent.  The V11 finding gets its own named tests; the finding is not hidden
inside another test's assertions.

Covered finding::

    MAJOR-V11-001  the canonical identifier/filesystem safety authority detected a
                   Windows drive token only when a path separator followed the
                   drive colon::

                       re.compile(r"(?:^|/)[A-Za-z]:[\\/]")

                   Windows distinguishes a *drive-root* path (``C:/name``) from a
                   *drive-relative* path (``C:name``), and the latter is still a
                   drive-qualified local filesystem reference::

                       ntpath.splitdrive("C:Windows") == ("C:", "Windows")

                   Because the rule required a separator after the colon, a
                   drive-relative reference such as ``C:id_rsa`` carried no
                   filesystem signature at all, and the final path-shape branch
                   treated any value without ``/`` or ``\\`` as "not path-shaped".
                   The value was therefore admitted by the identifier grammar,
                   accepted by the canonical ``EventSystem`` and durably persisted —
                   through all 13 shared identifier-bearing channels, in both
                   official repositories, and through a manual ``publish_event``
                   call.  ``id_rsa`` is already a sensitive private-file marker in
                   the canonical policy, so this is not merely a naming ambiguity:
                   the drive-designator colon prevented the existing boundary rule
                   from recognizing it.

The finding is exercised through the real canonical components — the public
``EventSystem`` facade, the canonical registry/bus/DLQ and both official
repository implementations (in-memory and file-backed).  Nothing is mocked.

The shared identifier authority is one function, so every persisted channel is
covered here explicitly rather than by patching ``request_id`` alone::

    payload identifier fields          (``request_id``, ``workflow_id``, ...)
    header producer                    (``producer`` and the other header facts)
    permissions                        (``permissions[]``)
    metadata identifier facts          (``metadata.error_type``)
    nested structured references       (``result_reference.reference_id``)
    reference sequences                (``approval_refs[]``, ``supporting_domains[]``)

Every adversarial test here reproduces the behaviour the independent Re-audit V11
reported, so it fails before the remediation and passes after it.

The remediation is deliberately *structural*: a **whole-value Windows drive
designator** is a local filesystem reference whether it is rooted (``C:/…``) or
drive-relative (``C:…``).  The rule is anchored to the start of the reference, not
to a segment boundary, because the frozen contract deliberately preserves wrapped
*segment-colon* logical identifiers such as ``provider/a:1/model`` and
``cmm/v2:3/detail`` — a drive-relative spelling is only drive-relative at the start
of a path, so a colon-bearing *segment* inside an allowlisted logical wrapper is not
a drive designator.  No pattern names an audited literal (``Windows``,
``ProgramData``, ``id_rsa``, ``.ssh``, ``tmp``) and no second path/URI policy module
is introduced.
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

#: A monotonic counter so every adversarial case gets a fresh, plain-safe canonical
#: event identity instead of deriving one from the audited value.
_CONTROL_IDS = itertools.count()


# ══════════════════════════════════════════════════════════════════════════
# MAJOR-V11-001 — a Windows drive-relative reference is not public-safe
# ══════════════════════════════════════════════════════════════════════════

#: The drive-relative references the independent Re-audit V11 demonstrated being
#: **accepted and durably persisted**.  Every member is admitted by the shared
#: identifier grammar and carries no path separator at all, so the retained
#: separator-requiring drive rule and the final "no separator, not path-shaped"
#: escape both missed it.
REPORTED_DRIVE_RELATIVE_REFERENCES = (
    "C:Windows",
    "C:id_rsa",
    "C:.ssh",
    "D:ProgramData",
    "Z:tmp",
)

#: Fresh V11 probes: the same drive-relative semantics through drive letters,
#: locations and spellings the audit did not name, plus the bare drive designator
#: (the drive's current directory).  Each one must receive the identical verdict, so
#: the fix cannot be a literal exception for the audited strings.
FRESH_DRIVE_RELATIVE_REFERENCES = (
    "C:",
    "C:a",
    "c:id_rsa",
    "X:foo.bar",
    "D:Users",
    "E:secret.txt",
    "Q:zzz-not-a-real-location",
)

#: Lowercase drive letters.  Windows drive designators are case-insensitive, so the
#: lowercase spelling is the same reference and must not survive merely because the
#: audited corpus used uppercase.
LOWERCASE_DRIVE_LETTER_REFERENCES = (
    "c:id_rsa",
    "c:Windows",
    "d:ProgramData",
    "z:tmp",
)

#: Every drive-relative reference the classifier must refuse, de-duplicated so the
#: parameter ids stay one-to-one with the corpus.
ALL_DRIVE_RELATIVE_REFERENCES = tuple(
    dict.fromkeys(
        REPORTED_DRIVE_RELATIVE_REFERENCES
        + FRESH_DRIVE_RELATIVE_REFERENCES
        + LOWERCASE_DRIVE_LETTER_REFERENCES
    )
)

#: Families of spellings of one drive-relative reference.  A trailing separator, a
#: case-varied drive letter and a case-varied remainder are all the *same*
#: drive-qualified local reference, so every member must receive the identical
#: verdict.
DRIVE_RELATIVE_EQUIVALENCE_FAMILIES = (
    ("C:Windows", "c:Windows", "C:windows", "C:Windows/"),
    ("C:id_rsa", "c:id_rsa", "C:id_rsa/"),
    ("D:ProgramData", "d:ProgramData", "D:ProgramData/"),
    ("C:.ssh", "c:.ssh"),
    ("C:", "c:"),
    ("Z:tmp", "z:tmp", "Z:tmp/"),
)

#: Every spelling in every equivalence family.  The whole family is one
#: drive-qualified local reference with one required classification: refused.
DRIVE_RELATIVE_EQUIVALENT_SPELLINGS = tuple(
    spelling for family in DRIVE_RELATIVE_EQUIVALENCE_FAMILIES for spelling in family
)

#: Backslash drive-relative spellings that the outer identifier grammar refuses
#: anyway, because ``\`` is not in the accepted identifier character set.  These are
#: recorded as positive fail-closed facts: the grammar does not have to be widened to
#: refuse the Windows-backslash spelling, and the V11 rule does not rely on it.
BACKSLASH_DRIVE_RELATIVE_REFERENCES = (
    "C:\\Windows",
    "C:\\id_rsa",
    "D:\\ProgramData",
)

#: Raw drive-root references retained from Re-audit V10.  They were already refused
#: before V11 and must keep their verdict, so the V11 whole-value rule strengthens
#: the drive classification without disturbing the rooted one.
TOP_LEVEL_DRIVE_ROOT_REFERENCES_RETAINED = (
    "C:/Windows/System32/config/SAM",
    "D:/private/example",
    "Z:/tmp/example",
    "c:/Windows/System32/config/SAM",
)

#: Wrapped drive-root references retained from Re-audit V10.  The V10 segment-boundary
#: rule refuses a *rooted* drive token carried by an allowlisted logical wrapper; the
#: V11 whole-value rule must not weaken or replace that behaviour.
WRAPPED_DRIVE_ROOT_REFERENCES_RETAINED = (
    "provider/C:/Windows/System32/config/SAM",
    "cmm/C:/Windows/System32/config/SAM",
    "provider//C:/Windows/System32/config/SAM",
    "provider/./C:/Windows/System32/config/SAM",
    "provider/C:/Windows/System32/config/SECURITY",
    "cmm/Z:/tmp/example",
    "provider/c:/Windows/System32/config/SAM",
)

#: Multi-letter colon identifiers that the frozen contract explicitly preserves.
#: None of them is a drive designator, because the character after the first letter
#: is not a colon.
MULTI_LETTER_COLON_IDENTIFIERS_UNCHANGED = (
    "workflow:123",
    "domain:legal",
    "events:read",
    "urn:cmm:event:message.received",
    "workflow:file:123",
    "domain:file:legal",
    "req:file:mod",
    "cmm:file:reference",
)

#: Wrapped *segment-colon* logical identifiers.  V10's regression suite preserves
#: these deliberately, and they are the reason the V11 drive rule is anchored to the
#: start of the whole reference rather than to a path-segment boundary: ``a:1`` here
#: is a logical route segment, not a Windows drive-relative reference.
SEGMENT_COLON_REFERENCES_UNCHANGED = (
    "provider/a:1/model",
    "provider/x:0/step",
    "cmm/v2:3/detail",
    "cmm/orchestration:step",
    "provider/a:1/model/detail",
)

#: Public slash references that must survive the V11 rule untouched.
PUBLIC_REFERENCES_UNCHANGED = (
    "provider/model",
    "provider//model",
    "provider/./model",
    "cmm/orchestration/step",
    "cmm.orchestration",
    "CORR-ORIGINAL",
    "user-42",
)

#: Credential-free URI references that must survive the V11 rule untouched.
CREDENTIAL_FREE_URIS_UNCHANGED = (
    "https://example.com/model",
    "http://localhost:8080/health",
    "postgres://example.com/db",
    "jdbc:postgresql://example.com/db",
    "provider/https://example.com/model",
)

#: Every accepted control the V11 module asserts in both directions.
ALL_ACCEPTED_CONTROLS = (
    MULTI_LETTER_COLON_IDENTIFIERS_UNCHANGED
    + SEGMENT_COLON_REFERENCES_UNCHANGED
    + PUBLIC_REFERENCES_UNCHANGED
    + CREDENTIAL_FREE_URIS_UNCHANGED
)

#: Retained non-public filesystem families from Re-audits V6–V10.  The V11 rule must
#: not disturb any of them: traversal, absolute paths, the ``~`` home shorthand,
#: relative system roots, drive-root paths, wrapped drive-root paths, ``file:`` URIs
#: and wrapped ``file:`` URIs, and named private locations.
RETAINED_UNSAFE_REFERENCES = (
    (
        "safe/../../etc/shadow",
        "foo/../bar/../../private/var",
        "/etc/shadow",
        "~/.ssh/id_rsa",
        "etc/shadow",
        "etc//shadow",
        "etc/./shadow",
        "proc/self/environ",
        "Windows/System32/config/SAM",
        "Library/Keychains/login.keychain-db",
        "file:///Users/alice/.ssh/id_rsa",
        "provider/file:C:/Windows/System32/config/SAM",
        "cmm/file:/Library/Keychains/login.keychain-db",
        "Users/alice/.ssh/id_rsa",
    )
    + TOP_LEVEL_DRIVE_ROOT_REFERENCES_RETAINED
    + WRAPPED_DRIVE_ROOT_REFERENCES_RETAINED
)

#: Retained URI-userinfo credential families from Re-audits V7/V8.
RETAINED_USERINFO_CREDENTIAL_REFERENCES = (
    "https://alice:supersecret@example.com/db",
    "jdbc:postgresql://alice:supersecret@example.com/db",
    "provider/https://alice:supersecret@example.com/db",
)

#: Retained civil-hour invariant corpus from Re-audit V9
#: (``PHASE11_22_TIMESTAMP_ACCEPTANCE_IS_INTERPRETER_VERSION_INDEPENDENT``).
RETAINED_END_OF_DAY_TIMESTAMPS = (
    "2026-09-27T24:00:00Z",
    "2026-09-27T24:00:00+00:00",
    "2026-09-27 24:00:00Z",
)

RETAINED_VALID_TIMESTAMPS = (
    "2026-09-27T00:00:00Z",
    "2026-09-27T23:59:59Z",
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
    event_id: str = "evt-v11-manual",
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
        lambda r: ({"request_id": "req-v11-channel", "workflow_id": r}, {}),
    ),
    (
        "payload_aggregate_id",
        lambda r: ({"request_id": "req-v11-channel", "aggregate_id": r}, {}),
    ),
    (
        "payload_producer",
        lambda r: ({"request_id": "req-v11-channel", "producer": r}, {}),
    ),
    (
        "header_producer",
        lambda r: ({"request_id": "req-v11-channel"}, {"producer": r}),
    ),
    (
        "header_aggregate_id",
        lambda r: ({"request_id": "req-v11-channel"}, {"aggregate_id": r}),
    ),
    (
        "header_correlation_id",
        lambda r: ({"request_id": "req-v11-channel"}, {"correlation_id": r}),
    ),
    ("header_source", lambda r: ({"request_id": "req-v11-channel"}, {"source": r})),
    (
        "permissions",
        lambda r: ({"request_id": "req-v11-channel"}, {"permissions": [r]}),
    ),
    (
        "metadata_error_type",
        lambda r: ({"request_id": "req-v11-channel"}, {"metadata": {"error_type": r}}),
    ),
    (
        "nested_result_reference",
        lambda r: (
            {"request_id": "req-v11-channel", "result_reference": {"reference_id": r}},
            {},
        ),
    ),
    (
        "structured_reference_sequence",
        lambda r: (
            {"request_id": "req-v11-channel", "approval_refs": [{"reference_id": r}]},
            {},
        ),
    ),
    (
        "domain_reference_sequence",
        lambda r: (
            {"request_id": "req-v11-channel", "supporting_domains": [r]},
            {},
        ),
    ),
)

_SHARED_CHANNEL_IDS = [case[0] for case in SHARED_CHANNELS]

#: The one canonical reference Re-audit V11 proved was persisted through all 13
#: channels.  It is repeated per channel below as the reported corpus.
REPORTED_CANONICAL_UNSAFE_REFERENCE = "C:id_rsa"


def _REFERENCE_IDS(reference: str) -> str:
    """Return a pytest parameter id for one adversarial reference spelling."""

    return reference.replace("/", "_").replace("\\", "b").replace(":", "-")


# ── the classifier itself ──────────────────────────────────────────────────


@pytest.mark.parametrize("reference", REPORTED_DRIVE_RELATIVE_REFERENCES)
def test_the_classifier_refuses_a_windows_drive_relative_reference(
    reference: str,
) -> None:
    """MAJOR-V11-001: a drive token needs no separator to be a local reference.

    ``WINDOWS_DRIVE_RELATIVE_REFERENCES_NEVER_ENTER_EVENT_PERSISTENCE``
    """

    from cmm.events.event_payload_safety import is_private_filesystem_reference

    assert is_private_filesystem_reference(reference) is True, reference


@pytest.mark.parametrize("reference", FRESH_DRIVE_RELATIVE_REFERENCES)
def test_the_classifier_refuses_a_fresh_windows_drive_relative_reference(
    reference: str,
) -> None:
    """MAJOR-V11-001: the fix is structural, so unnamed drives are refused too."""

    from cmm.events.event_payload_safety import is_private_filesystem_reference

    assert is_private_filesystem_reference(reference) is True, reference


@pytest.mark.parametrize("reference", LOWERCASE_DRIVE_LETTER_REFERENCES)
def test_the_classifier_refuses_a_lowercase_drive_letter(reference: str) -> None:
    """MAJOR-V11-001: Windows drive designators are case-insensitive."""

    from cmm.events.event_payload_safety import is_private_filesystem_reference

    assert is_private_filesystem_reference(reference) is True, reference


@pytest.mark.parametrize("reference", TOP_LEVEL_DRIVE_ROOT_REFERENCES_RETAINED)
def test_the_classifier_still_refuses_a_top_level_drive_root(reference: str) -> None:
    """MAJOR-V11-001: the retained V10 top-level controls keep their verdict."""

    from cmm.events.event_payload_safety import is_private_filesystem_reference

    assert is_private_filesystem_reference(reference) is True, reference


@pytest.mark.parametrize("reference", WRAPPED_DRIVE_ROOT_REFERENCES_RETAINED)
def test_the_classifier_still_refuses_a_wrapped_drive_root(reference: str) -> None:
    """MAJOR-V11-001: the V10 segment-boundary rule is not weakened.

    ``WRAPPED_WINDOWS_DRIVE_ROOT_REFERENCES_HAVE_THE_SAME_UNSAFE_CLASSIFICATION_AS_TOP_LEVEL_DRIVE_ROOT_REFERENCES``
    """

    from cmm.events.event_payload_safety import is_private_filesystem_reference

    assert is_private_filesystem_reference(reference) is True, reference


@pytest.mark.parametrize("reference", DRIVE_RELATIVE_EQUIVALENT_SPELLINGS)
def test_every_drive_relative_spelling_is_classified_identically(
    reference: str,
) -> None:
    """MAJOR-V11-001: one drive-qualified location, one verdict.

    ``PATH_EQUIVALENT_SPELLINGS_HAVE_IDENTICAL_SAFETY_CLASSIFICATION``
    """

    from cmm.events.event_payload_safety import is_private_filesystem_reference

    assert is_private_filesystem_reference(reference) is True, reference


@pytest.mark.parametrize(
    "family",
    DRIVE_RELATIVE_EQUIVALENCE_FAMILIES,
    ids=lambda family: family[0].replace("/", "_").replace(":", "-"),
)
def test_drive_relative_equivalence_families_share_one_verdict(
    family: tuple[str, ...],
) -> None:
    """MAJOR-V11-001: equivalent spellings of one reference never disagree."""

    from cmm.events import event_payload_safety as authority

    verdicts = {
        authority.is_private_filesystem_reference(spelling) for spelling in family
    }
    assert verdicts == {True}, family


def test_the_identifier_grammar_admits_the_drive_relative_spelling() -> None:
    """MAJOR-V11-001: the bypass is a classifier defect, not a grammar defect.

    The V11 reproductions are single safe-character tokens with no separator at all.
    The refusal therefore has to come from the filesystem classifier; if this
    assertion ever fails the finding has moved and this module no longer proves what
    it claims.
    """

    from cmm.events import event_payload_safety as authority

    for reference in ALL_DRIVE_RELATIVE_REFERENCES:
        assert authority._SAFE_IDENTIFIER_PATTERN.match(reference) is not None, (
            reference
        )
        assert authority.is_private_filesystem_reference(reference) is True, reference


def test_the_drive_relative_rule_lives_in_the_canonical_pattern_set() -> None:
    """MAJOR-V11-001: the rule is a canonical signature, not a new scanner.

    A whole-value drive designator is refused because one of the *existing* canonical
    filesystem signatures matches it on the analysis form.  This is what makes the
    fix structural rather than a second Windows path authority.
    """

    from cmm.events import event_payload_safety as authority

    for reference in ALL_DRIVE_RELATIVE_REFERENCES:
        canonical = authority._analyze_lexical_path(reference).canonical
        assert canonical[:2].lower() == reference[:2].lower(), (reference, canonical)
        assert any(
            pattern.search(canonical)
            for pattern in authority._PRIVATE_FILESYSTEM_PATTERNS
        ), canonical


def test_the_drive_relative_rule_is_not_a_reproduced_literal_denylist() -> None:
    """MAJOR-V11-001: the rule is structural, so an unnamed location is refused too.

    The audit named ``Windows``, ``ProgramData``, ``id_rsa``, ``.ssh`` and ``tmp``.
    No pattern mentions those location names as a *drive-relative* literal, and the
    fresh probes name drives and remainders no pattern mentions either, yet all of
    them are refused.  The V11 fix is therefore a structural classification of the
    drive designator rather than a literal appended for each audited string.
    """

    from cmm.events import event_payload_safety as authority

    drive_pattern_sources = " ".join(
        pattern.pattern
        for pattern in authority._PRIVATE_FILESYSTEM_PATTERNS
        if "[A-Za-z]:" in pattern.pattern
    )
    for audited_name in ("Windows", "ProgramData", "foo.bar"):
        assert audited_name not in drive_pattern_sources, audited_name
    # The drive rules name no drive letter and no location: they are a character
    # class, a colon and a separator requirement.
    assert "C" not in drive_pattern_sources.replace("A-Za-z", "")

    for reference in (
        "Q:zzz-not-a-real-location",
        "X:foo.bar",
        "E:secret.txt",
    ):
        assert authority.is_private_filesystem_reference(reference) is True, reference


def test_the_drive_relative_classifier_performs_no_filesystem_io() -> None:
    """MAJOR-V11-001: classification stays lexical — no I/O and no resolution."""

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
        for reference in ALL_DRIVE_RELATIVE_REFERENCES:
            assert authority.is_private_filesystem_reference(reference) is True
        for reference in ALL_ACCEPTED_CONTROLS:
            assert authority.is_private_filesystem_reference(reference) is False
    finally:
        for holder, name, original in saved:
            setattr(holder, name, original)


def test_the_drive_relative_rule_reuses_the_existing_safety_authority() -> None:
    """MAJOR-V11-001: no second path/URI policy module was introduced."""

    import cmm.events.event_payload_safety as authority

    module_files = {path.name for path in Path(authority.__file__).parent.glob("*.py")}
    assert "event_path_policy.py" not in module_files
    assert "event_drive_relative_policy.py" not in module_files
    assert "event_windows_path_policy.py" not in module_files
    assert "identifier_policy.py" not in module_files
    assert "path_canonicalization.py" not in module_files


# ── the shared identifier authority ────────────────────────────────────────


@pytest.mark.parametrize("reference", REPORTED_DRIVE_RELATIVE_REFERENCES)
def test_the_identifier_authority_refuses_a_reported_drive_relative_reference(
    reference: str,
) -> None:
    """MAJOR-V11-001: the shared validator refuses every reported spelling."""

    from cmm.events.event_payload_safety import validate_platform_identifier

    with pytest.raises(REJECTIONS):
        validate_platform_identifier(reference, field="probe")


@pytest.mark.parametrize("reference", FRESH_DRIVE_RELATIVE_REFERENCES)
def test_the_identifier_authority_refuses_a_fresh_drive_relative_reference(
    reference: str,
) -> None:
    """MAJOR-V11-001: the shared validator is structural, not string-specific."""

    from cmm.events.event_payload_safety import validate_platform_identifier

    with pytest.raises(REJECTIONS):
        validate_platform_identifier(reference, field="probe")


@pytest.mark.parametrize("reference", LOWERCASE_DRIVE_LETTER_REFERENCES)
def test_the_identifier_authority_refuses_a_lowercase_drive_letter(
    reference: str,
) -> None:
    """MAJOR-V11-001: the lowercase drive letter is the same reference."""

    from cmm.events.event_payload_safety import validate_platform_identifier

    with pytest.raises(REJECTIONS):
        validate_platform_identifier(reference, field="probe")


@pytest.mark.parametrize("reference", BACKSLASH_DRIVE_RELATIVE_REFERENCES)
def test_backslash_drive_relative_spellings_are_refused_by_the_identifier_grammar(
    reference: str,
) -> None:
    """MAJOR-V11-001: ``\\`` is outside the grammar, so it is refused earlier.

    This is a positive fail-closed fact: the V11 fix does not need to widen the
    identifier grammar to cover the Windows-backslash spelling, and it does not rely
    on doing so.
    """

    from cmm.events import event_payload_safety as authority

    assert authority._SAFE_IDENTIFIER_PATTERN.match(reference) is None, reference
    with pytest.raises(REJECTIONS):
        authority.validate_platform_identifier(reference, field="probe")


@pytest.mark.parametrize("reference", ALL_ACCEPTED_CONTROLS)
def test_supported_public_and_colon_identifiers_are_still_accepted(
    reference: str,
) -> None:
    """MAJOR-V11-001 positive control: the fix does not over-correct.

    Multi-letter colon identifiers (``workflow:123``, ``domain:legal``), wrapped
    segment-colon logical identifiers (``provider/a:1/model``, ``cmm/v2:3/detail``),
    plain slash references and credential-free URIs all keep their verdict.  This is
    the executable form of "do not break the wrapped logical forms".
    """

    from cmm.events.event_payload_safety import (
        is_private_filesystem_reference,
        validate_platform_identifier,
    )

    assert validate_platform_identifier(reference, field="probe") == reference
    assert is_private_filesystem_reference(reference) is False, reference


@pytest.mark.parametrize("reference", RETAINED_UNSAFE_REFERENCES)
def test_every_retained_filesystem_protection_still_refuses(reference: str) -> None:
    """MAJOR-V11-001: V6–V10 path protections are preserved, not replaced."""

    from cmm.events.event_payload_safety import validate_platform_identifier

    with pytest.raises(REJECTIONS):
        validate_platform_identifier(reference, field="probe")


@pytest.mark.parametrize("reference", RETAINED_USERINFO_CREDENTIAL_REFERENCES)
def test_every_retained_userinfo_credential_protection_still_refuses(
    reference: str,
) -> None:
    """MAJOR-V11-001: V7/V8 URI-userinfo protections are preserved.

    ``URI_USERINFO_CREDENTIALS_REJECTED_REGARDLESS_OF_PREFIX_OR_WRAPPER``
    """

    from cmm.events.event_payload_safety import validate_platform_identifier

    with pytest.raises(REJECTIONS):
        validate_platform_identifier(reference, field="probe")


@pytest.mark.parametrize("timestamp", RETAINED_END_OF_DAY_TIMESTAMPS)
def test_the_retained_civil_hour_bound_still_refuses(timestamp: str) -> None:
    """MAJOR-V11-001: the V9 timestamp invariant is untouched.

    ``PHASE11_22_TIMESTAMP_ACCEPTANCE_IS_INTERPRETER_VERSION_INDEPENDENT``
    """

    from cmm.events.event_payload_safety import _validate_canonical_timestamp

    with pytest.raises(REJECTIONS):
        _validate_canonical_timestamp(timestamp, field="occurred_at")


@pytest.mark.parametrize("timestamp", RETAINED_VALID_TIMESTAMPS)
def test_the_retained_valid_timestamps_still_validate(timestamp: str) -> None:
    """MAJOR-V11-001: the V9 timestamp acceptance is untouched."""

    from cmm.events.event_payload_safety import _validate_canonical_timestamp

    assert _validate_canonical_timestamp(timestamp, field="occurred_at") == timestamp


def test_the_drive_relative_refusal_message_is_static() -> None:
    """MAJOR-V11-001: the refusal never echoes the audited local location."""

    from cmm.events.event_payload_safety import validate_platform_identifier

    reference = REPORTED_CANONICAL_UNSAFE_REFERENCE
    with pytest.raises(PlatformEventPayloadError) as excinfo:
        validate_platform_identifier(reference, field="probe")

    message = str(excinfo.value)
    assert "id_rsa" not in message
    assert reference not in message
    assert "private filesystem location" in message


def test_an_accepted_reference_is_persisted_without_its_spelling_mutated() -> None:
    """MAJOR-V11-001: the fix classifies; it never rewrites an accepted value."""

    from cmm.events.event_payload_safety import validate_platform_identifier

    for reference in ALL_ACCEPTED_CONTROLS:
        assert validate_platform_identifier(reference, field="probe") == reference


# ── the canonical EventSystem ──────────────────────────────────────────────


@pytest.mark.parametrize("reference", REPORTED_DRIVE_RELATIVE_REFERENCES)
def test_the_event_system_refuses_a_reported_drive_relative_reference(
    reference: str,
) -> None:
    """MAJOR-V11-001: canonical publication refuses before persistence.

    ``NON_PUBLIC_FILESYSTEM_PATHS_NEVER_ENTER_EVENT_PERSISTENCE``
    """

    system, received = _watching_system()

    with pytest.raises(REJECTIONS):
        system.publish(
            "message.received",
            {"request_id": reference},
            event_id=f"evt-v11-sys-{next(_CONTROL_IDS)}",
        )

    _assert_nothing_reached_persistence(system, received)


@pytest.mark.parametrize("reference", FRESH_DRIVE_RELATIVE_REFERENCES)
def test_the_event_system_refuses_a_fresh_drive_relative_reference(
    reference: str,
) -> None:
    """MAJOR-V11-001: the official in-memory repository stays unchanged."""

    system, received = _watching_system()

    with pytest.raises(REJECTIONS):
        system.publish(
            "message.received",
            {"request_id": reference},
            event_id=f"evt-v11-fresh-{next(_CONTROL_IDS)}",
        )

    _assert_nothing_reached_persistence(system, received)


@pytest.mark.parametrize("reference", ALL_DRIVE_RELATIVE_REFERENCES)
def test_the_file_backed_repository_persists_nothing_for_a_drive_relative_reference(
    tmp_path: Path, reference: str
) -> None:
    """MAJOR-V11-001: the durable store is byte-identical after refusal."""

    store = _durable_store(tmp_path)
    system = _file_backed_system(store)
    before = _durable_bytes(store)

    with pytest.raises(REJECTIONS):
        system.publish(
            "message.received",
            {"request_id": reference},
            event_id=f"evt-v11-durable-{next(_CONTROL_IDS)}",
        )

    assert system.repository.count() == 0
    assert system.dead_letter_count() == 0
    assert _durable_bytes(store) == before
    assert not store.exists() or store.read_bytes() == b""


@pytest.mark.parametrize("reference", ALL_DRIVE_RELATIVE_REFERENCES)
def test_a_manual_publish_event_cannot_bypass_the_drive_relative_rule(
    reference: str,
) -> None:
    """MAJOR-V11-001: the manual canonical boundary re-applies the same rule."""

    system, received = _watching_system()
    event = manual_event(
        "message.received",
        {"request_id": reference},
        event_id=f"evt-v11-manual-{next(_CONTROL_IDS)}",
    )

    with pytest.raises(REJECTIONS):
        system.publish_event(event)

    _assert_nothing_reached_persistence(system, received)


@pytest.mark.parametrize("reference", ALL_ACCEPTED_CONTROLS)
def test_accepted_references_still_publish_and_keep_their_identity(
    reference: str,
) -> None:
    """MAJOR-V11-001 positive control: identity/correlation/causation unchanged."""

    system, received = _watching_system()
    event_id = f"evt-v11-ok-{next(_CONTROL_IDS)}"

    result = system.publish(
        "message.received",
        {"request_id": "req-v11-ok", "workflow_id": reference},
        event_id=event_id,
        aggregate_id=reference,
        correlation_id="CORR-V11-ORIGINAL",
        causation_id="CAUSE-V11-ORIGINAL",
    )

    assert result.persisted is True
    assert system.repository.count() == 1
    assert len(received) == 1
    assert system.dead_letter_count() == 0
    stored = system.repository.get(event_id)
    assert stored is not None
    assert stored.header.workflow_id == reference
    assert stored.header.aggregate_id == reference
    assert stored.header.correlation_id == "CORR-V11-ORIGINAL"
    assert stored.header.causation_id == "CAUSE-V11-ORIGINAL"


# ── every shared persisted identifier channel ─────────────────────────────


@pytest.mark.parametrize(
    ("label", "build"),
    SHARED_CHANNELS,
    ids=_SHARED_CHANNEL_IDS,
)
@pytest.mark.parametrize(
    "reference",
    REPORTED_DRIVE_RELATIVE_REFERENCES,
    ids=_REFERENCE_IDS,
)
def test_every_shared_channel_refuses_a_reported_drive_relative_reference(
    label: str, build: Any, reference: str
) -> None:
    """MAJOR-V11-001: all 13 shared channels refuse, not just ``request_id``."""

    payload, header_facts = build(reference)
    system, received = _watching_system()

    with pytest.raises(REJECTIONS):
        system.publish(
            "message.received",
            payload,
            event_id=f"evt-v11-channel-{label}-{next(_CONTROL_IDS)}",
            **header_facts,
        )

    _assert_nothing_reached_persistence(system, received)


@pytest.mark.parametrize(
    ("label", "build"),
    SHARED_CHANNELS,
    ids=_SHARED_CHANNEL_IDS,
)
@pytest.mark.parametrize(
    "reference",
    FRESH_DRIVE_RELATIVE_REFERENCES + LOWERCASE_DRIVE_LETTER_REFERENCES,
    ids=_REFERENCE_IDS,
)
def test_every_shared_channel_refuses_a_fresh_drive_relative_reference(
    label: str, build: Any, reference: str
) -> None:
    """MAJOR-V11-001: the fix is structural on every channel."""

    payload, header_facts = build(reference)
    system, received = _watching_system()

    with pytest.raises(REJECTIONS):
        system.publish(
            "message.received",
            payload,
            event_id=f"evt-v11-fresh-{label}-{next(_CONTROL_IDS)}",
            **header_facts,
        )

    _assert_nothing_reached_persistence(system, received)


@pytest.mark.parametrize(
    ("label", "build"),
    SHARED_CHANNELS,
    ids=_SHARED_CHANNEL_IDS,
)
def test_every_shared_channel_refuses_the_canonical_unsafe_reference(
    label: str, build: Any
) -> None:
    """MAJOR-V11-001: the exact audited ``C:id_rsa`` value is refused per channel.

    ``CREDENTIALS_NEVER_ENTER_EVENT_PERSISTENCE`` — ``id_rsa`` is an already-known
    sensitive private-file marker, so the drive designator must not shield it.
    """

    payload, header_facts = build(REPORTED_CANONICAL_UNSAFE_REFERENCE)
    system, received = _watching_system()

    with pytest.raises(REJECTIONS):
        system.publish(
            "message.received",
            payload,
            event_id=f"evt-v11-canonical-{label}-{next(_CONTROL_IDS)}",
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
    """MAJOR-V11-001: refusal is proven by the durable store, per channel."""

    store = _durable_store(tmp_path)
    system = _file_backed_system(store)
    payload, header_facts = build(REPORTED_CANONICAL_UNSAFE_REFERENCE)
    before = _durable_bytes(store)

    with pytest.raises(REJECTIONS):
        system.publish(
            "message.received",
            payload,
            event_id=f"evt-v11-durable-channel-{label}",
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
def test_every_shared_channel_refuses_through_the_file_backed_repository(
    tmp_path: Path, label: str, build: Any
) -> None:
    """MAJOR-V11-001: the official file-backed repository rejects all 13 channels."""

    store = _durable_store(tmp_path)
    system = _file_backed_system(store)
    payload, header_facts = build(REPORTED_CANONICAL_UNSAFE_REFERENCE)
    before = _durable_bytes(store)
    event = manual_event(
        "message.received",
        payload,
        event_id=f"evt-v11-filebacked-{label}",
        **header_facts,
    )

    with pytest.raises(REJECTIONS):
        system.publish_event(event)

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
    MULTI_LETTER_COLON_IDENTIFIERS_UNCHANGED
    + SEGMENT_COLON_REFERENCES_UNCHANGED
    + PUBLIC_REFERENCES_UNCHANGED,
    ids=_REFERENCE_IDS,
)
def test_every_shared_channel_still_accepts_a_public_reference(
    label: str, build: Any, reference: str
) -> None:
    """MAJOR-V11-001 positive control: public references persist on every channel."""

    payload, header_facts = build(reference)
    system, received = _watching_system()

    result = system.publish(
        "message.received",
        payload,
        event_id=f"evt-v11-ok-{label}-{next(_CONTROL_IDS)}",
        **header_facts,
    )

    assert result.persisted is True
    assert system.repository.count() == 1
    assert len(received) == 1
    assert system.dead_letter_count() == 0
