"""Phase 11.22 — Remediation V12 adversarial regressions.

These tests make the independent Re-audit V12 reproduction executable and
permanent.  The V12 finding gets its own named tests; the finding is not hidden
inside another test's assertions.

Covered finding::

    MAJOR-V12-001  the canonical sensitive-private-filename signature was both
                   case-**sensitive** and unaware of the Windows NTFS
                   *named-stream* suffix, so an already-known private key
                   material basename stopped being private merely by changing
                   case or by attaching a ``:`` stream name::

                       re.compile(
                           r"(?:^|[\\\\/])(?:id_rsa|id_dsa|id_ecdsa|id_ed25519"
                           r"|known_hosts)(?:$|\\.)"
                       )

                   Windows ``ntfs`` defines ``name:stream`` as the ``stream``
                   alternate data stream of the file ``name``, so
                   ``id_rsa:stream`` still denotes the private key material
                   ``id_rsa``.  Because the signature required end-of-value or a
                   literal ``.`` after the basename, and because a value carrying
                   no path separator was never treated as path-shaped, the
                   audited spellings::

                       ID_RSA
                       KNOWN_HOSTS
                       Id_Ed25519.pub
                       id_rsa:stream
                       known_hosts:ads
                       id_ed25519:foo
                       id_ecdsa:data
                       provider/ID_RSA
                       provider/id_rsa:stream
                       cmm/known_hosts:ads

                   all passed :func:`is_private_filesystem_reference`, passed
                   :func:`validate_platform_identifier`, were accepted by the
                   canonical ``EventSystem`` and were durably appended — through
                   all 13 shared identifier-bearing channels, in both official
                   repositories, and through a manual ``publish_event`` call.
                   ``id_rsa`` is already a sensitive private-file marker in the
                   canonical policy, so this is not a naming ambiguity: case
                   variation and the named-stream colon were *shielding* a known
                   private location.

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

Every adversarial test here reproduces the behaviour the independent Re-audit V12
reported, so it fails before the remediation and passes after it.

The remediation is deliberately *structural*: the **existing** canonical
sensitive-private-filename signature becomes case-insensitive for the
already-sensitive basenames and treats ``:`` as a suffix boundary exactly as it
already treated ``.``.  It is the same rule, in the same ``event_payload_safety``
authority, with the same private basename family — no second parser, scanner,
registry, ADS policy or subsystem is introduced, no literal is appended for any
audited spelling, no generic ``:`` identifier is refused, and no generic
``filename:stream`` form is refused.
"""

from __future__ import annotations

import itertools
import os
import pathlib
import re
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
# MAJOR-V12-001 — a sensitive private filename keeps its secrecy through
# case variation and through an NTFS named-stream suffix
# ══════════════════════════════════════════════════════════════════════════

#: The case-varied sensitive private filenames the independent Re-audit V12
#: demonstrated being **accepted and durably persisted**.  Every member is admitted
#: by the shared identifier grammar, and the retained signature was case-sensitive,
#: so the basename stopped being classified as private merely by changing case.
REPORTED_CASE_VARIANT_PRIVATE_FILENAMES = (
    "ID_RSA",
    "KNOWN_HOSTS",
    "Id_Ed25519.pub",
    "provider/ID_RSA",
    "cmm/KNOWN_HOSTS",
)

#: The named-stream sensitive private filenames the independent Re-audit V12
#: demonstrated being **accepted and durably persisted**.  Windows defines
#: ``name:stream`` as the ``stream`` alternate data stream of the file ``name``, so
#: each of these still denotes the private basename before the colon.  The retained
#: signature accepted only end-of-value or a literal ``.`` after the basename, so the
#: stream colon hid the private file.
REPORTED_NAMED_STREAM_PRIVATE_FILENAMES = (
    "id_rsa:stream",
    "known_hosts:ads",
    "id_ed25519:foo",
    "id_ecdsa:data",
    "provider/id_rsa:stream",
    "cmm/known_hosts:ads",
)

#: Fresh adversarial probes from the independent Re-audit V12 probe list: case and
#: stream spellings the audit did not use as its canonical example.  Each one must
#: receive the identical verdict, so the fix cannot be a literal exception for the
#: audited strings.
FRESH_CASE_VARIANT_PRIVATE_FILENAMES = (
    "Id_Rsa",
    "id_RSA",
    "Known_Hosts",
    "ID_DSA.PUB",
    "ID_ECDSA",
    "Provider/Id_Ed25519",
)

FRESH_NAMED_STREAM_PRIVATE_FILENAMES = (
    "ID_RSA:STREAM",
    "Known_Hosts:ADS",
    "id_dsa:stream",
    "provider/id_ed25519:foo",
    "cmm/id_ecdsa:data",
)

#: Lowercase basenames that were *already* classified before V12 and must keep their
#: verdict, so the V12 change strengthens rather than replaces the retained family.
RETAINED_LOWERCASE_PRIVATE_FILENAMES = (
    "id_rsa",
    "id_dsa",
    "id_ecdsa",
    "id_ed25519",
    "known_hosts",
    "id_rsa.pub",
    "known_hosts.old",
    ".ssh/id_rsa",
    "provider/id_rsa",
)

#: Every V12 adversarial spelling, de-duplicated so the parameter ids stay one-to-one
#: with the corpus.
ALL_CASE_VARIANT_PRIVATE_FILENAMES = tuple(
    dict.fromkeys(
        REPORTED_CASE_VARIANT_PRIVATE_FILENAMES + FRESH_CASE_VARIANT_PRIVATE_FILENAMES
    )
)

ALL_NAMED_STREAM_PRIVATE_FILENAMES = tuple(
    dict.fromkeys(
        REPORTED_NAMED_STREAM_PRIVATE_FILENAMES + FRESH_NAMED_STREAM_PRIVATE_FILENAMES
    )
)

ALL_ADVERSARIAL_PRIVATE_FILENAMES = tuple(
    dict.fromkeys(
        ALL_CASE_VARIANT_PRIVATE_FILENAMES + ALL_NAMED_STREAM_PRIVATE_FILENAMES
    )
)

#: Families of spellings of one sensitive private filename.  Case variation and the
#: NTFS named-stream suffix are both the *same* private file, so every member must
#: receive the identical verdict.  This is the executable form of
#: ``PATH_EQUIVALENT_SPELLINGS_HAVE_IDENTICAL_SAFETY_CLASSIFICATION`` for the
#: sensitive-private-filename family.
SENSITIVE_FILENAME_EQUIVALENCE_FAMILIES = (
    ("id_rsa", "ID_RSA", "Id_Rsa", "id_RSA", "iD_rSa"),
    ("id_dsa", "ID_DSA", "Id_Dsa", "ID_DSA.PUB"),
    ("id_ecdsa", "ID_ECDSA", "Id_Ecdsa"),
    ("id_ed25519", "ID_ED25519", "Id_Ed25519", "Id_Ed25519.pub"),
    ("known_hosts", "KNOWN_HOSTS", "Known_Hosts"),
    ("id_rsa", "id_rsa:stream", "ID_RSA:STREAM"),
    ("known_hosts", "known_hosts:ads", "Known_Hosts:ADS"),
    ("id_ed25519", "id_ed25519:foo"),
    ("id_ecdsa", "id_ecdsa:data"),
    ("provider/id_rsa", "provider/ID_RSA", "provider/id_rsa:stream"),
    ("cmm/known_hosts", "cmm/KNOWN_HOSTS", "cmm/known_hosts:ads"),
)

#: Every spelling in every equivalence family.
SENSITIVE_FILENAME_EQUIVALENT_SPELLINGS = tuple(
    spelling
    for family in SENSITIVE_FILENAME_EQUIVALENCE_FAMILIES
    for spelling in family
)

#: Backslash spellings of the sensitive private filename that the outer identifier
#: grammar refuses anyway, because ``\`` is not in the accepted identifier character
#: set.  Recorded as positive fail-closed facts: the grammar does not have to be
#: widened for the Windows-backslash spelling, and the V12 rule does not rely on it.
BACKSLASH_PRIVATE_FILENAMES = (
    ".ssh\\id_rsa",
    "Users\\alice\\.ssh\\id_rsa",
    "ID_RSA:STREAM\\x",
)

#: Colon-bearing identifiers the frozen contract explicitly preserves.  None of them
#: has a sensitive private basename at a path-segment start, so none may be refused by
#: the V12 rule: the invariant is narrow and a colon is not by itself a defect.
PRESERVED_COLON_IDENTIFIERS = (
    "workflow:123",
    "domain:legal",
    "events:read",
    "urn:cmm:event:message.received",
    "workflow:file:123",
    "domain:file:legal",
    "req:file:mod",
    "cmm:file:reference",
    # The negative-space controls from the V12 probe list: a sensitive-looking *suffix*
    # is not a sensitive basename at a segment boundary.
    "model:id_rsa",
    "workflow:id_rsa",
    "model:known_hosts",
    "workflow:id_ed25519",
    "prefix_id_rsa",
    "my-known_hosts",
)

#: Wrapped *segment-colon* logical identifiers.  V10/V11 preserve these deliberately,
#: and they are the reason a colon-suffix rule must stay inside the existing
#: basename-anchored signature rather than becoming a generic colon ban.
SEGMENT_COLON_REFERENCES_UNCHANGED = (
    "provider/a:1/model",
    "provider/x:0/step",
    "cmm/v2:3/detail",
    "cmm/orchestration:step",
    "provider/a:1/model/detail",
)

#: Generic non-sensitive ``filename:stream`` controls the V12 prompt requires to stay
#: valid.  They are the load-bearing false-positive controls: a rule that refused every
#: ``filename:stream`` form would break them.
GENERIC_NAMED_STREAM_CONTROLS = (
    "foo.txt:stream",
    "provider/foo.txt:stream",
    "report.json:ads",
    "cmm/artifact.bin:stream",
)

#: Public slash references that must survive the V12 rule untouched.
PUBLIC_REFERENCES_UNCHANGED = (
    "provider/model",
    "provider//model",
    "provider/./model",
    "cmm/orchestration/step",
    "cmm.orchestration",
    "CORR-ORIGINAL",
    "user-42",
)

#: Credential-free URI references that must survive the V12 rule untouched.
CREDENTIAL_FREE_URIS_UNCHANGED = (
    "https://example.com/model",
    "http://localhost:8080/health",
    "postgres://example.com/db",
    "jdbc:postgresql://example.com/db",
    "provider/https://example.com/model",
)

#: Every accepted control the V12 module asserts in both directions.
ALL_ACCEPTED_CONTROLS = (
    PRESERVED_COLON_IDENTIFIERS
    + SEGMENT_COLON_REFERENCES_UNCHANGED
    + GENERIC_NAMED_STREAM_CONTROLS
    + PUBLIC_REFERENCES_UNCHANGED
    + CREDENTIAL_FREE_URIS_UNCHANGED
)

#: Retained non-public filesystem families from Re-audits V6–V11.  The V12 rule must
#: not disturb any of them: traversal, absolute paths, the ``~`` home shorthand,
#: relative system roots, drive-root paths, wrapped drive-root paths, drive-relative
#: paths, ``file:`` URIs and wrapped ``file:`` URIs, and named private locations.
RETAINED_UNSAFE_REFERENCES = (
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
    "C:/Windows/System32/config/SAM",
    "provider/C:/Windows/System32/config/SAM",
    "cmm/C:/Windows/System32/config/SAM",
    "C:id_rsa",
    "C:Windows",
    "c:id_rsa",
    "D:ProgramData",
    "Z:tmp",
    "C:",
    "X:foo.bar",
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


def _reopened(store: Path) -> FileAgentRuntimeEventRepository:
    """Reopen the official file-backed repository over the same store path."""

    return FileAgentRuntimeEventRepository(store)


def manual_event(
    event_type: str,
    payload: dict[str, Any],
    *,
    event_id: str = "evt-v12-manual",
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
        lambda r: ({"request_id": "req-v12-channel", "workflow_id": r}, {}),
    ),
    (
        "payload_aggregate_id",
        lambda r: ({"request_id": "req-v12-channel", "aggregate_id": r}, {}),
    ),
    (
        "payload_producer",
        lambda r: ({"request_id": "req-v12-channel", "producer": r}, {}),
    ),
    (
        "header_producer",
        lambda r: ({"request_id": "req-v12-channel"}, {"producer": r}),
    ),
    (
        "header_aggregate_id",
        lambda r: ({"request_id": "req-v12-channel"}, {"aggregate_id": r}),
    ),
    (
        "header_correlation_id",
        lambda r: ({"request_id": "req-v12-channel"}, {"correlation_id": r}),
    ),
    ("header_source", lambda r: ({"request_id": "req-v12-channel"}, {"source": r})),
    (
        "permissions",
        lambda r: ({"request_id": "req-v12-channel"}, {"permissions": [r]}),
    ),
    (
        "metadata_error_type",
        lambda r: ({"request_id": "req-v12-channel"}, {"metadata": {"error_type": r}}),
    ),
    (
        "nested_result_reference",
        lambda r: (
            {"request_id": "req-v12-channel", "result_reference": {"reference_id": r}},
            {},
        ),
    ),
    (
        "structured_reference_sequence",
        lambda r: (
            {"request_id": "req-v12-channel", "approval_refs": [{"reference_id": r}]},
            {},
        ),
    ),
    (
        "domain_reference_sequence",
        lambda r: (
            {"request_id": "req-v12-channel", "supporting_domains": [r]},
            {},
        ),
    ),
)

_SHARED_CHANNEL_IDS = [case[0] for case in SHARED_CHANNELS]

#: The one canonical case-variant reference and the one canonical named-stream
#: reference Re-audit V12 proved were persisted through all 13 channels.  They are
#: repeated per channel below.
REPORTED_CANONICAL_CASE_VARIANT = "ID_RSA"
REPORTED_CANONICAL_NAMED_STREAM = "id_rsa:stream"


def _REFERENCE_IDS(reference: str) -> str:
    """Return a pytest parameter id for one adversarial reference spelling."""

    return reference.replace("/", "_").replace("\\", "b").replace(":", "-")


# ── the classifier itself ──────────────────────────────────────────────────


@pytest.mark.parametrize("reference", REPORTED_CASE_VARIANT_PRIVATE_FILENAMES)
def test_the_classifier_refuses_a_reported_case_variant_private_filename(
    reference: str,
) -> None:
    """MAJOR-V12-001: an already-sensitive basename is case-insensitive for safety.

    ``WINDOWS_SENSITIVE_PRIVATE_FILENAME_EQUIVALENTS_NEVER_ENTER_EVENT_PERSISTENCE``
    """

    from cmm.events.event_payload_safety import is_private_filesystem_reference

    assert is_private_filesystem_reference(reference) is True, reference


@pytest.mark.parametrize("reference", REPORTED_NAMED_STREAM_PRIVATE_FILENAMES)
def test_the_classifier_refuses_a_reported_named_stream_private_filename(
    reference: str,
) -> None:
    """MAJOR-V12-001: a ``:`` named-stream suffix cannot make a private file public.

    Windows defines ``name:stream`` as the ``stream`` alternate data stream of
    ``name``; the private basename before the colon is the file that is referenced.
    """

    from cmm.events.event_payload_safety import is_private_filesystem_reference

    assert is_private_filesystem_reference(reference) is True, reference


@pytest.mark.parametrize("reference", FRESH_CASE_VARIANT_PRIVATE_FILENAMES)
def test_the_classifier_refuses_a_fresh_case_variant_private_filename(
    reference: str,
) -> None:
    """MAJOR-V12-001: the fix is structural, so unnamed casings are refused too."""

    from cmm.events.event_payload_safety import is_private_filesystem_reference

    assert is_private_filesystem_reference(reference) is True, reference


@pytest.mark.parametrize("reference", FRESH_NAMED_STREAM_PRIVATE_FILENAMES)
def test_the_classifier_refuses_a_fresh_named_stream_private_filename(
    reference: str,
) -> None:
    """MAJOR-V12-001: the fix is structural, so unnamed stream names are too."""

    from cmm.events.event_payload_safety import is_private_filesystem_reference

    assert is_private_filesystem_reference(reference) is True, reference


@pytest.mark.parametrize("reference", RETAINED_LOWERCASE_PRIVATE_FILENAMES)
def test_the_classifier_still_refuses_the_retained_private_filename_family(
    reference: str,
) -> None:
    """MAJOR-V12-001: the already-sensitive family keeps its verdict verbatim."""

    from cmm.events.event_payload_safety import is_private_filesystem_reference

    assert is_private_filesystem_reference(reference) is True, reference


@pytest.mark.parametrize("reference", SENSITIVE_FILENAME_EQUIVALENT_SPELLINGS)
def test_every_sensitive_filename_spelling_is_classified_identically(
    reference: str,
) -> None:
    """MAJOR-V12-001: one private file, one verdict.

    ``PATH_EQUIVALENT_SPELLINGS_HAVE_IDENTICAL_SAFETY_CLASSIFICATION``
    """

    from cmm.events.event_payload_safety import is_private_filesystem_reference

    assert is_private_filesystem_reference(reference) is True, reference


@pytest.mark.parametrize(
    "family",
    SENSITIVE_FILENAME_EQUIVALENCE_FAMILIES,
    ids=lambda family: family[0].replace("/", "_").replace(":", "-"),
)
def test_sensitive_filename_equivalence_families_share_one_verdict(
    family: tuple[str, ...],
) -> None:
    """MAJOR-V12-001: equivalent spellings of one private file never disagree."""

    from cmm.events import event_payload_safety as authority

    verdicts = {
        authority.is_private_filesystem_reference(spelling) for spelling in family
    }
    assert verdicts == {True}, family


def test_every_sensitive_basename_is_case_insensitive_structurally() -> None:
    """MAJOR-V12-001: case-insensitivity holds for the whole declared family.

    The check is behavioural rather than flag-introspective: every already-declared
    private basename must receive one verdict for its lowercase, uppercase and mixed
    spellings, so the guarantee cannot be satisfied by an exception for one audited
    string.
    """

    from cmm.events import event_payload_safety as authority

    for basename in ("id_rsa", "id_dsa", "id_ecdsa", "id_ed25519", "known_hosts"):
        spellings = (
            basename,
            basename.upper(),
            basename.title(),
            basename.capitalize(),
        )
        verdicts = {
            authority.is_private_filesystem_reference(spelling)
            for spelling in spellings
        }
        assert verdicts == {True}, (basename, spellings)


def test_the_identifier_grammar_admits_the_adversarial_spellings() -> None:
    """MAJOR-V12-001: the bypass is a classifier defect, not a grammar defect.

    The V12 reproductions are single safe-character tokens.  The refusal therefore has
    to come from the filesystem classifier; if this assertion ever fails the finding
    has moved and this module no longer proves what it claims.
    """

    from cmm.events import event_payload_safety as authority

    for reference in ALL_ADVERSARIAL_PRIVATE_FILENAMES:
        assert authority._SAFE_IDENTIFIER_PATTERN.match(reference) is not None, (
            reference
        )
        assert authority.is_private_filesystem_reference(reference) is True, reference


def test_the_sensitive_filename_rule_lives_in_the_canonical_pattern_set() -> None:
    """MAJOR-V12-001: the rule is the existing signature, not a new scanner.

    Each adversarial value is refused because one of the *existing* canonical
    filesystem signatures matches it on the analysis form.  This is what makes the
    fix structural rather than a second Windows path / ADS authority.
    """

    from cmm.events import event_payload_safety as authority

    for reference in ALL_ADVERSARIAL_PRIVATE_FILENAMES:
        canonical = authority._analyze_lexical_path(reference).canonical
        assert any(
            pattern.search(canonical)
            for pattern in authority._PRIVATE_FILESYSTEM_PATTERNS
        ), (reference, canonical)


def test_the_sensitive_filename_rule_is_not_a_reproduced_literal_denylist() -> None:
    """MAJOR-V12-001: the rule is structural, so an unnamed spelling is refused too.

    The audit named ``ID_RSA``, ``KNOWN_HOSTS``, ``Id_Ed25519.pub``, ``stream``,
    ``ads``, ``foo`` and ``data``.  The canonical sensitive-private-filename
    signature is located by its private basename family rather than by any audited
    casing or stream literal, and fresh casings and stream names no pattern mentions
    are refused by the same rule.
    """

    from cmm.events import event_payload_safety as authority

    signature_sources = [
        pattern.pattern
        for pattern in authority._PRIVATE_FILESYSTEM_PATTERNS
        if "known_hosts" in pattern.pattern
    ]
    assert signature_sources, "the sensitive-private-filename signature must exist"
    joined = " ".join(signature_sources)

    for audited_literal in (
        "ID_RSA",
        "KNOWN_HOSTS",
        "Id_Ed25519",
        "ID_DSA.PUB",
        ":stream",
        ":ads",
        ":foo",
        ":data",
        "STREAM",
    ):
        assert audited_literal not in joined, audited_literal

    for reference in (
        "Id_Rsa",
        "id_RSA",
        "Known_Hosts:ADS",
        "ID_ECDSA",
        "provider/id_ed25519:foo",
    ):
        assert authority.is_private_filesystem_reference(reference) is True, reference


def test_the_sensitive_filename_rule_does_not_ban_the_colon_in_general() -> None:
    """MAJOR-V12-001: the invariant is narrow, not a generic colon ban.

    The one canonical sensitive-private-filename signature is a basename-anchored
    rule; a colon-bearing identifier whose segment does not *start* with an
    already-sensitive basename must keep its verdict, including the generic
    ``filename:stream`` form and the ``model:id_rsa`` negative-space control.
    """

    from cmm.events import event_payload_safety as authority

    for reference in ALL_ACCEPTED_CONTROLS:
        assert authority.is_private_filesystem_reference(reference) is False, reference
        assert (
            authority.validate_platform_identifier(reference, field="probe")
            == reference
        ), reference


def test_the_sensitive_filename_classifier_performs_no_filesystem_io() -> None:
    """MAJOR-V12-001: classification stays lexical — no I/O and no resolution."""

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
        for reference in ALL_ADVERSARIAL_PRIVATE_FILENAMES:
            assert authority.is_private_filesystem_reference(reference) is True
        for reference in ALL_ACCEPTED_CONTROLS:
            assert authority.is_private_filesystem_reference(reference) is False
    finally:
        for holder, name, original in saved:
            setattr(holder, name, original)


def test_the_sensitive_filename_rule_reuses_the_existing_safety_authority() -> None:
    """MAJOR-V12-001: no second parser, scanner, registry or ADS policy module."""

    import cmm.events.event_payload_safety as authority

    module_files = {path.name for path in Path(authority.__file__).parent.glob("*.py")}
    assert "event_path_policy.py" not in module_files
    assert "event_ads_policy.py" not in module_files
    assert "event_named_stream_policy.py" not in module_files
    assert "event_windows_filename_policy.py" not in module_files
    assert "identifier_policy.py" not in module_files
    assert "path_canonicalization.py" not in module_files


# ── the shared identifier authority ────────────────────────────────────────


@pytest.mark.parametrize("reference", ALL_CASE_VARIANT_PRIVATE_FILENAMES)
def test_the_identifier_authority_refuses_every_case_variant(reference: str) -> None:
    """MAJOR-V12-001: the shared validator refuses every case-varied spelling."""

    from cmm.events.event_payload_safety import validate_platform_identifier

    with pytest.raises(REJECTIONS):
        validate_platform_identifier(reference, field="probe")


@pytest.mark.parametrize("reference", ALL_NAMED_STREAM_PRIVATE_FILENAMES)
def test_the_identifier_authority_refuses_every_named_stream(reference: str) -> None:
    """MAJOR-V12-001: the shared validator refuses every stream-suffixed spelling."""

    from cmm.events.event_payload_safety import validate_platform_identifier

    with pytest.raises(REJECTIONS):
        validate_platform_identifier(reference, field="probe")


@pytest.mark.parametrize("reference", BACKSLASH_PRIVATE_FILENAMES)
def test_backslash_private_filenames_are_refused_by_the_identifier_grammar(
    reference: str,
) -> None:
    """MAJOR-V12-001: ``\\`` is outside the grammar, so it is refused earlier.

    This is a positive fail-closed fact: the V12 fix does not need to widen the
    identifier grammar for the Windows-backslash spelling, and it does not rely on
    doing so.
    """

    from cmm.events import event_payload_safety as authority

    assert authority._SAFE_IDENTIFIER_PATTERN.match(reference) is None, reference
    with pytest.raises(REJECTIONS):
        authority.validate_platform_identifier(reference, field="probe")


@pytest.mark.parametrize("reference", ALL_ACCEPTED_CONTROLS)
def test_supported_colon_and_public_identifiers_are_still_accepted(
    reference: str,
) -> None:
    """MAJOR-V12-001 positive control: the fix does not over-correct.

    Multi-letter colon identifiers (``workflow:123``, ``domain:legal``), wrapped
    segment-colon logical identifiers (``provider/a:1/model``, ``cmm/v2:3/detail``),
    generic ``filename:stream`` controls (``foo.txt:stream``,
    ``provider/foo.txt:stream``), sensitive-looking suffixes (``model:id_rsa``),
    plain slash references and credential-free URIs all keep their verdict.
    """

    from cmm.events.event_payload_safety import (
        is_private_filesystem_reference,
        validate_platform_identifier,
    )

    assert validate_platform_identifier(reference, field="probe") == reference
    assert is_private_filesystem_reference(reference) is False, reference


@pytest.mark.parametrize("reference", RETAINED_UNSAFE_REFERENCES)
def test_every_retained_filesystem_protection_still_refuses(reference: str) -> None:
    """MAJOR-V12-001: V6–V11 path protections are preserved, not replaced."""

    from cmm.events.event_payload_safety import validate_platform_identifier

    with pytest.raises(REJECTIONS):
        validate_platform_identifier(reference, field="probe")


@pytest.mark.parametrize("reference", RETAINED_USERINFO_CREDENTIAL_REFERENCES)
def test_every_retained_userinfo_credential_protection_still_refuses(
    reference: str,
) -> None:
    """MAJOR-V12-001: V7/V8 URI-userinfo protections are preserved.

    ``URI_USERINFO_CREDENTIALS_REJECTED_REGARDLESS_OF_PREFIX_OR_WRAPPER``
    """

    from cmm.events.event_payload_safety import validate_platform_identifier

    with pytest.raises(REJECTIONS):
        validate_platform_identifier(reference, field="probe")


@pytest.mark.parametrize("timestamp", RETAINED_END_OF_DAY_TIMESTAMPS)
def test_the_retained_civil_hour_bound_still_refuses(timestamp: str) -> None:
    """MAJOR-V12-001: the V9 timestamp invariant is untouched.

    ``PHASE11_22_TIMESTAMP_ACCEPTANCE_IS_INTERPRETER_VERSION_INDEPENDENT``
    """

    from cmm.events.event_payload_safety import _validate_canonical_timestamp

    with pytest.raises(REJECTIONS):
        _validate_canonical_timestamp(timestamp, field="occurred_at")


@pytest.mark.parametrize("timestamp", RETAINED_VALID_TIMESTAMPS)
def test_the_retained_valid_timestamps_still_validate(timestamp: str) -> None:
    """MAJOR-V12-001: the V9 timestamp acceptance is untouched."""

    from cmm.events.event_payload_safety import _validate_canonical_timestamp

    assert _validate_canonical_timestamp(timestamp, field="occurred_at") == timestamp


def test_the_private_filename_refusal_message_is_static() -> None:
    """MAJOR-V12-001: the refusal never echoes the audited private basename."""

    from cmm.events.event_payload_safety import validate_platform_identifier

    for reference in (
        REPORTED_CANONICAL_CASE_VARIANT,
        REPORTED_CANONICAL_NAMED_STREAM,
        "provider/ID_RSA",
        "cmm/known_hosts:ads",
    ):
        with pytest.raises(PlatformEventPayloadError) as excinfo:
            validate_platform_identifier(reference, field="probe")

        message = str(excinfo.value)
        assert reference not in message
        assert "id_rsa" not in message.lower()
        assert "known_hosts" not in message.lower()
        assert "private filesystem location" in message


def test_an_accepted_reference_is_persisted_without_its_spelling_mutated() -> None:
    """MAJOR-V12-001: the fix classifies; it never rewrites an accepted value."""

    from cmm.events.event_payload_safety import validate_platform_identifier

    for reference in ALL_ACCEPTED_CONTROLS:
        assert validate_platform_identifier(reference, field="probe") == reference


def test_the_sensitive_filename_rule_does_not_lowercase_identifiers() -> None:
    """MAJOR-V12-001: no broadly lowercasing/rewriting of accepted identifiers.

    Case-insensitivity is a *classification* input only; the persisted value keeps
    the exact spelling the producer supplied.
    """

    from cmm.events.event_payload_safety import validate_platform_identifier

    for reference in ("provider/MODEL", "CMM/Orchestration/Step", "WORKFLOW:123"):
        assert validate_platform_identifier(reference, field="probe") == reference


# ── the canonical EventSystem ──────────────────────────────────────────────


@pytest.mark.parametrize("reference", ALL_CASE_VARIANT_PRIVATE_FILENAMES)
def test_the_event_system_refuses_a_case_variant_private_filename(
    reference: str,
) -> None:
    """MAJOR-V12-001: canonical publication refuses before persistence.

    ``NON_PUBLIC_FILESYSTEM_PATHS_NEVER_ENTER_EVENT_PERSISTENCE``
    """

    system, received = _watching_system()

    with pytest.raises(REJECTIONS):
        system.publish(
            "message.received",
            {"request_id": reference},
            event_id=f"evt-v12-sys-case-{next(_CONTROL_IDS)}",
        )

    _assert_nothing_reached_persistence(system, received)


@pytest.mark.parametrize("reference", ALL_NAMED_STREAM_PRIVATE_FILENAMES)
def test_the_event_system_refuses_a_named_stream_private_filename(
    reference: str,
) -> None:
    """MAJOR-V12-001: the official in-memory repository stays unchanged."""

    system, received = _watching_system()

    with pytest.raises(REJECTIONS):
        system.publish(
            "message.received",
            {"request_id": reference},
            event_id=f"evt-v12-sys-stream-{next(_CONTROL_IDS)}",
        )

    _assert_nothing_reached_persistence(system, received)


@pytest.mark.parametrize("reference", ALL_ADVERSARIAL_PRIVATE_FILENAMES)
def test_the_file_backed_repository_persists_nothing_for_a_private_filename(
    tmp_path: Path, reference: str
) -> None:
    """MAJOR-V12-001: the durable store is byte-identical after refusal."""

    store = _durable_store(tmp_path)
    system = _file_backed_system(store)
    before = _durable_bytes(store)

    with pytest.raises(REJECTIONS):
        system.publish(
            "message.received",
            {"request_id": reference},
            event_id=f"evt-v12-durable-{next(_CONTROL_IDS)}",
        )

    assert system.repository.count() == 0
    assert system.dead_letter_count() == 0
    assert _durable_bytes(store) == before
    assert not store.exists() or store.read_bytes() == b""


@pytest.mark.parametrize("reference", ALL_ADVERSARIAL_PRIVATE_FILENAMES)
def test_a_reopened_file_backed_repository_reveals_no_rejected_value(
    tmp_path: Path, reference: str
) -> None:
    """MAJOR-V12-001: reopening the durable store must not reveal the value.

    Independent Re-audit V12 reopened the file-backed store and found the exact
    unsafe value persisted.  Reopening after the refusal must yield no event and no
    trace of the private basename.
    """

    store = _durable_store(tmp_path)
    system = _file_backed_system(store)
    event_id = f"evt-v12-reopen-{next(_CONTROL_IDS)}"
    before = _durable_bytes(store)

    with pytest.raises(REJECTIONS):
        system.publish(
            "message.received",
            {"request_id": reference},
            event_id=event_id,
        )

    reopened = _reopened(store)
    assert reopened.count() == 0
    assert reopened.get(event_id) is None
    assert _durable_bytes(store) == before
    if store.exists():
        basename = reference.split("/")[-1].split(":")[0].lower()
        assert basename.encode() not in store.read_bytes()


@pytest.mark.parametrize("reference", ALL_ADVERSARIAL_PRIVATE_FILENAMES)
def test_a_manual_publish_event_cannot_bypass_the_private_filename_rule(
    reference: str,
) -> None:
    """MAJOR-V12-001: the manual canonical boundary re-applies the same rule."""

    system, received = _watching_system()
    event = manual_event(
        "message.received",
        {"request_id": reference},
        event_id=f"evt-v12-manual-{next(_CONTROL_IDS)}",
    )

    with pytest.raises(REJECTIONS):
        system.publish_event(event)

    _assert_nothing_reached_persistence(system, received)


@pytest.mark.parametrize("reference", ALL_ACCEPTED_CONTROLS)
def test_accepted_references_still_publish_and_keep_their_identity(
    reference: str,
) -> None:
    """MAJOR-V12-001 positive control: identity/correlation/causation unchanged."""

    system, received = _watching_system()
    event_id = f"evt-v12-ok-{next(_CONTROL_IDS)}"

    result = system.publish(
        "message.received",
        {"request_id": "req-v12-ok", "workflow_id": reference},
        event_id=event_id,
        aggregate_id=reference,
        correlation_id="CORR-V12-ORIGINAL",
        causation_id="CAUSE-V12-ORIGINAL",
    )

    assert result.persisted is True
    assert system.repository.count() == 1
    assert len(received) == 1
    assert system.dead_letter_count() == 0
    stored = system.repository.get(event_id)
    assert stored is not None
    assert stored.header.workflow_id == reference
    assert stored.header.aggregate_id == reference
    assert stored.header.correlation_id == "CORR-V12-ORIGINAL"
    assert stored.header.causation_id == "CAUSE-V12-ORIGINAL"


# ── every shared persisted identifier channel ─────────────────────────────


@pytest.mark.parametrize(
    ("label", "build"),
    SHARED_CHANNELS,
    ids=_SHARED_CHANNEL_IDS,
)
@pytest.mark.parametrize(
    "reference",
    REPORTED_CASE_VARIANT_PRIVATE_FILENAMES,
    ids=_REFERENCE_IDS,
)
def test_every_shared_channel_refuses_a_case_variant_private_filename(
    label: str, build: Any, reference: str
) -> None:
    """MAJOR-V12-001: all 13 shared channels refuse, not just ``request_id``."""

    payload, header_facts = build(reference)
    system, received = _watching_system()

    with pytest.raises(REJECTIONS):
        system.publish(
            "message.received",
            payload,
            event_id=f"evt-v12-channel-case-{label}-{next(_CONTROL_IDS)}",
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
    REPORTED_NAMED_STREAM_PRIVATE_FILENAMES,
    ids=_REFERENCE_IDS,
)
def test_every_shared_channel_refuses_a_named_stream_private_filename(
    label: str, build: Any, reference: str
) -> None:
    """MAJOR-V12-001: the named-stream rule is inherited by every channel."""

    payload, header_facts = build(reference)
    system, received = _watching_system()

    with pytest.raises(REJECTIONS):
        system.publish(
            "message.received",
            payload,
            event_id=f"evt-v12-channel-stream-{label}-{next(_CONTROL_IDS)}",
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
    (REPORTED_CANONICAL_CASE_VARIANT, REPORTED_CANONICAL_NAMED_STREAM),
    ids=_REFERENCE_IDS,
)
def test_every_shared_channel_refuses_the_canonical_private_filenames(
    label: str, build: Any, reference: str
) -> None:
    """MAJOR-V12-001: the exact audited values are refused on every channel.

    ``CREDENTIALS_NEVER_ENTER_EVENT_PERSISTENCE`` — ``id_rsa`` is an already-known
    sensitive private-file marker, so case and a named-stream colon must not shield
    it.
    """

    payload, header_facts = build(reference)
    system, received = _watching_system()

    with pytest.raises(REJECTIONS):
        system.publish(
            "message.received",
            payload,
            event_id=f"evt-v12-canonical-{label}-{next(_CONTROL_IDS)}",
            **header_facts,
        )

    _assert_nothing_reached_persistence(system, received)


@pytest.mark.parametrize(
    ("label", "build"),
    SHARED_CHANNELS,
    ids=_SHARED_CHANNEL_IDS,
)
@pytest.mark.parametrize(
    ("reference", "marker"),
    (
        (REPORTED_CANONICAL_CASE_VARIANT, b"ID_RSA"),
        (REPORTED_CANONICAL_NAMED_STREAM, b"id_rsa"),
    ),
    ids=["case_variant", "named_stream"],
)
def test_every_shared_channel_leaves_the_durable_store_untouched(
    tmp_path: Path, label: str, build: Any, reference: str, marker: bytes
) -> None:
    """MAJOR-V12-001: refusal is proven by the durable store, per channel."""

    store = _durable_store(tmp_path)
    system = _file_backed_system(store)
    payload, header_facts = build(reference)
    before = _durable_bytes(store)

    with pytest.raises(REJECTIONS):
        system.publish(
            "message.received",
            payload,
            event_id=f"evt-v12-durable-channel-{label}",
            **header_facts,
        )

    assert system.repository.count() == 0
    assert system.dead_letter_count() == 0
    assert _durable_bytes(store) == before
    assert _reopened(store).count() == 0
    if store.exists():
        assert marker not in store.read_bytes()


@pytest.mark.parametrize(
    ("label", "build"),
    SHARED_CHANNELS,
    ids=_SHARED_CHANNEL_IDS,
)
@pytest.mark.parametrize(
    "reference",
    (REPORTED_CANONICAL_CASE_VARIANT, REPORTED_CANONICAL_NAMED_STREAM),
    ids=_REFERENCE_IDS,
)
def test_every_shared_channel_refuses_through_the_file_backed_repository(
    tmp_path: Path, label: str, build: Any, reference: str
) -> None:
    """MAJOR-V12-001: the official file-backed repository rejects all 13 channels."""

    store = _durable_store(tmp_path)
    system = _file_backed_system(store)
    payload, header_facts = build(reference)
    before = _durable_bytes(store)
    event = manual_event(
        "message.received",
        payload,
        event_id=f"evt-v12-filebacked-{label}",
        **header_facts,
    )

    with pytest.raises(REJECTIONS):
        system.publish_event(event)

    assert system.repository.count() == 0
    assert system.dead_letter_count() == 0
    assert _durable_bytes(store) == before
    assert _reopened(store).count() == 0


@pytest.mark.parametrize(
    ("label", "build"),
    SHARED_CHANNELS,
    ids=_SHARED_CHANNEL_IDS,
)
@pytest.mark.parametrize(
    "reference",
    PRESERVED_COLON_IDENTIFIERS
    + SEGMENT_COLON_REFERENCES_UNCHANGED
    + GENERIC_NAMED_STREAM_CONTROLS
    + PUBLIC_REFERENCES_UNCHANGED,
    ids=_REFERENCE_IDS,
)
def test_every_shared_channel_still_accepts_a_public_reference(
    label: str, build: Any, reference: str
) -> None:
    """MAJOR-V12-001 positive control: public references persist on every channel."""

    payload, header_facts = build(reference)
    system, received = _watching_system()

    result = system.publish(
        "message.received",
        payload,
        event_id=f"evt-v12-ok-{label}-{next(_CONTROL_IDS)}",
        **header_facts,
    )

    assert result.persisted is True
    assert system.repository.count() == 1
    assert len(received) == 1
    assert system.dead_letter_count() == 0


# ── the canonical signature itself ─────────────────────────────────────────


def test_the_sensitive_filename_signature_is_case_insensitive_and_colon_aware() -> None:
    """MAJOR-V12-001: the fix is the canonical signature's own semantics.

    The located signature must classify one already-sensitive basename through
    lowercase, uppercase and mixed case, and must treat ``:`` as a suffix boundary
    exactly as it already treats ``.``, while a non-sensitive basename keeps the
    opposite verdict.
    """

    from cmm.events import event_payload_safety as authority

    signatures = [
        pattern
        for pattern in authority._PRIVATE_FILESYSTEM_PATTERNS
        if "known_hosts" in pattern.pattern
    ]
    assert len(signatures) == 1, "exactly one canonical sensitive-filename signature"

    signature = signatures[0]
    for admitted in ("id_rsa", "ID_RSA", "Id_Rsa", "KNOWN_HOSTS", "Id_Ed25519.pub"):
        assert signature.search(admitted) is not None, admitted
    for boundary_admitted in ("id_rsa:stream", "ID_RSA:STREAM", "known_hosts:ads"):
        assert signature.search(boundary_admitted) is not None, boundary_admitted
    for rejected in ("foo.txt", "provider/model", "model:id_rsa", "workflow:123"):
        assert signature.search(rejected) is None, rejected


def test_the_sensitive_filename_signature_is_applied_on_the_analysis_form() -> None:
    """MAJOR-V12-001: rows and wrappers classify on the canonical analysis form.

    The signature is consulted against the same lexical analysis form as the retained
    V6–V11 rules, so ``provider/ID_RSA`` and ``provider/id_rsa:stream`` receive the
    verdict their basename already had at the top level.
    """

    from cmm.events import event_payload_safety as authority

    for reference in (
        "provider/ID_RSA",
        "provider/id_rsa:stream",
        "cmm/KNOWN_HOSTS",
        "cmm/known_hosts:ads",
    ):
        canonical = authority._analyze_lexical_path(reference).canonical
        assert any(
            pattern.search(canonical)
            for pattern in authority._PRIVATE_FILESYSTEM_PATTERNS
        ), reference
        assert authority.is_private_filesystem_reference(reference) is True, reference
        assert (
            reference.split("/", 1)[0].lower() in authority.PUBLIC_SLASH_REFERENCE_ROOTS
        )


def test_the_sensitive_filename_patterns_are_still_compiled_patterns() -> None:
    """MAJOR-V12-001: no grammar widening and no second classification mechanism."""

    from cmm.events import event_payload_safety as authority

    assert authority._PRIVATE_FILESYSTEM_PATTERNS
    for pattern in authority._PRIVATE_FILESYSTEM_PATTERNS:
        assert isinstance(pattern, re.Pattern), pattern

    # The identifier grammar itself is unchanged: the V12 reproductions are still
    # admitted by it, which is why the classifier has to refuse them.
    assert (
        authority._SAFE_IDENTIFIER_PATTERN.pattern
        == r"^[A-Za-z0-9][A-Za-z0-9._:@+\-/]*$"
    )
