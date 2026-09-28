"""Phase 11.22 — Remediation V10 adversarial regressions.

These tests make the independent Re-audit V10 reproduction executable and
permanent.  The V10 finding gets its own named tests; the finding is not hidden
inside another test's assertions.

Covered finding::

    MAJOR-V10-001  the canonical identifier/filesystem safety authority detected a
                   raw Windows drive-root path only when the drive token sat at
                   character zero of the whole reference::

                       re.compile(r"^[A-Za-z]:[\\/]")

                   Remediation V9 had already moved the ``file:`` signature to a
                   *path-segment* boundary, but the structurally equivalent raw
                   drive-root token was left anchored to the start of the value.
                   Because ``provider`` and ``cmm`` are declared public slash
                   roots, a wrapped reference such as
                   ``provider/C:/Windows/System32/config/SAM`` was classified as a
                   public reference, admitted by the identifier grammar, accepted
                   by the canonical ``EventSystem`` and durably persisted — through
                   all 13 shared identifier-bearing channels, in both official
                   repositories.

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

Every adversarial test here reproduces the behaviour the independent Re-audit V10
reported, so it fails before the remediation and passes after it.

The remediation is deliberately *structural*: a raw drive-root token is unsafe at
a valid path-segment boundary, not merely at character zero.  No pattern names an
audited literal (``SAM``, ``SECURITY``, ``System32``, ``ProgramData``,
``MachineKeys``), and no second path/URI policy module is introduced.
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
# MAJOR-V10-001 — a wrapped raw Windows drive-root reference is not public-safe
# ══════════════════════════════════════════════════════════════════════════

#: Raw Windows drive-root references the frozen contract already refused, because
#: the drive token happens to sit at character zero.  They are the retained
#: controls for the V10 rule: the wrapped forms must receive this same verdict.
TOP_LEVEL_DRIVE_ROOT_REFERENCES = (
    "C:/Windows/System32/config/SAM",
    "D:/private/example",
    "Z:/tmp/example",
    "c:/Windows/System32/config/SAM",
)

#: The wrapped drive-root references the independent Re-audit V10 demonstrated
#: being **accepted and durably persisted**.  Every member is admitted by the
#: shared identifier grammar (so the character-set rule cannot refuse it) and was
#: accepted by the pre-V10 filesystem classifier, because the drive token is not
#: at character zero and the outer slash root (``provider``/``cmm``) is allowlisted.
REPORTED_WRAPPED_DRIVE_ROOT_REFERENCES = (
    "provider/C:/Windows/System32/config/SAM",
    "cmm/C:/Windows/System32/config/SAM",
    "provider//C:/Windows/System32/config/SAM",
    "provider/./C:/Windows/System32/config/SAM",
    "provider/C:/Windows/System32/config/SECURITY",
)

#: Fresh V10 probes: the same wrapped drive-root semantics through drive letters
#: and locations the audit did not name.  Each one was accepted by the pre-V10
#: classifier, so the fix cannot be a literal exception for the audited string.
FRESH_WRAPPED_DRIVE_ROOT_REFERENCES = (
    "provider/D:/private/example",
    "cmm/Z:/tmp/example",
    "provider/c:/Windows/System32/config/SAM",
    "cmm/E:/ProgramData/Example/config.xml",
    "provider/A:/boot/grub/grub.cfg",
    "cmm/B:/srv/backup/keys.tar",
)

#: Every wrapped drive-root reference the classifier must refuse.
WRAPPED_DRIVE_ROOT_REFERENCES = (
    REPORTED_WRAPPED_DRIVE_ROOT_REFERENCES + FRESH_WRAPPED_DRIVE_ROOT_REFERENCES
)

#: The complete non-public raw drive-root corpus, top-level and wrapped.
ALL_DRIVE_ROOT_REFERENCES = (
    TOP_LEVEL_DRIVE_ROOT_REFERENCES + WRAPPED_DRIVE_ROOT_REFERENCES
)

#: Families of spellings of one unsafe drive-root reference.  Repeated separators,
#: a ``.`` current-directory segment, a trailing separator, a case-varied wrapper
#: and a case-varied drive letter are all the *same* location under the canonical
#: analysis form, so every member must receive the identical verdict.
WRAPPED_DRIVE_ROOT_EQUIVALENCE_FAMILIES = (
    (
        "provider/C:/Windows/System32/config/SAM",
        "provider//C:/Windows/System32/config/SAM",
        "provider/./C:/Windows/System32/config/SAM",
        "provider/C:/Windows/System32/config/SAM/",
        "Provider/C:/Windows/System32/config/SAM",
        "PROVIDER/C:/Windows/System32/config/SAM",
    ),
    (
        "cmm/C:/Windows/System32/config/SAM",
        "cmm//C:/Windows/System32/config/SAM",
        "cmm/./C:/Windows/System32/config/SAM",
        "CMM/C:/Windows/System32/config/SAM",
    ),
    (
        "C:/Windows/System32/config/SAM",
        "C://Windows/System32/config/SAM",
        "C:/./Windows/System32/config/SAM",
        "c:/Windows/System32/config/SAM",
    ),
    (
        "provider/D:/private/example",
        "provider//D:/private/example",
        "provider/./D:/private/example",
        "provider/d:/private/example",
    ),
)

#: Every spelling in every equivalence family.  The whole family is one location
#: with one required classification: refused.
WRAPPED_DRIVE_ROOT_EQUIVALENT_SPELLINGS = tuple(
    spelling
    for family in WRAPPED_DRIVE_ROOT_EQUIVALENCE_FAMILIES
    for spelling in family
)

#: Raw drive-root spellings that the outer identifier grammar refuses anyway,
#: because ``\`` is not in the accepted identifier character set.  These are
#: recorded as positive fail-closed facts: the grammar does not have to be widened
#: to refuse the Windows-backslash spelling, and the V10 rule does not rely on it.
BACKSLASH_DRIVE_ROOT_REFERENCES = (
    "C:\\Windows\\System32\\config\\SAM",
    "provider/C:\\Windows\\System32\\config\\SAM",
    "provider\\C:\\Windows\\System32\\config\\SAM",
)

#: Public references that must survive the V10 rule untouched.  Every member is a
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

#: Colon-bearing logical identifiers that sit at a path-segment boundary yet are
#: *not* drive-root syntax, because the colon is not followed by a path separator.
#: They prove the V10 rule stayed narrow instead of becoming "a letter then a colon
#: somewhere in the value": ``provider/a:1/model`` names no local drive location.
SEGMENT_COLON_REFERENCES_UNCHANGED = (
    "provider/a:1/model",
    "provider/x:0/step",
    "cmm/v2:3/detail",
    "cmm/orchestration:step",
)

#: Credential-free URI references that must survive the V10 rule untouched.
CREDENTIAL_FREE_URIS_UNCHANGED = (
    "https://example.com/model",
    "http://localhost:8080/health",
    "postgres://example.com/db",
    "jdbc:postgresql://example.com/db",
    "provider/https://example.com/model",
    "urn:cmm:event:message.received",
)

#: Colon-bearing logical identifiers whose ``file`` token does not begin a path
#: segment.  The V9 rule must keep admitting them, and the V10 rule must not
#: disturb them.
COLON_LOGICAL_IDENTIFIERS_UNCHANGED = (
    "workflow:file:123",
    "domain:file:legal",
    "req:file:mod",
    "cmm:file:reference",
)

#: Every accepted control the V10 module asserts in both directions.
ALL_ACCEPTED_CONTROLS = (
    PUBLIC_REFERENCES_UNCHANGED
    + SEGMENT_COLON_REFERENCES_UNCHANGED
    + CREDENTIAL_FREE_URIS_UNCHANGED
    + COLON_LOGICAL_IDENTIFIERS_UNCHANGED
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
    event_id: str = "evt-v10-manual",
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
        lambda r: ({"request_id": "req-v10-channel", "workflow_id": r}, {}),
    ),
    (
        "payload_aggregate_id",
        lambda r: ({"request_id": "req-v10-channel", "aggregate_id": r}, {}),
    ),
    (
        "payload_producer",
        lambda r: ({"request_id": "req-v10-channel", "producer": r}, {}),
    ),
    (
        "header_producer",
        lambda r: ({"request_id": "req-v10-channel"}, {"producer": r}),
    ),
    (
        "header_aggregate_id",
        lambda r: ({"request_id": "req-v10-channel"}, {"aggregate_id": r}),
    ),
    (
        "header_correlation_id",
        lambda r: ({"request_id": "req-v10-channel"}, {"correlation_id": r}),
    ),
    ("header_source", lambda r: ({"request_id": "req-v10-channel"}, {"source": r})),
    (
        "permissions",
        lambda r: ({"request_id": "req-v10-channel"}, {"permissions": [r]}),
    ),
    (
        "metadata_error_type",
        lambda r: ({"request_id": "req-v10-channel"}, {"metadata": {"error_type": r}}),
    ),
    (
        "nested_result_reference",
        lambda r: (
            {"request_id": "req-v10-channel", "result_reference": {"reference_id": r}},
            {},
        ),
    ),
    (
        "structured_reference_sequence",
        lambda r: (
            {"request_id": "req-v10-channel", "approval_refs": [{"reference_id": r}]},
            {},
        ),
    ),
    (
        "domain_reference_sequence",
        lambda r: (
            {"request_id": "req-v10-channel", "supporting_domains": [r]},
            {},
        ),
    ),
)

_SHARED_CHANNEL_IDS = [case[0] for case in SHARED_CHANNELS]


def _REFERENCE_IDS(reference: str) -> str:
    """Return a pytest parameter id for one adversarial reference spelling."""

    return reference.replace("/", "_").replace(":", "-")


# ── the classifier itself ──────────────────────────────────────────────────


@pytest.mark.parametrize("reference", WRAPPED_DRIVE_ROOT_REFERENCES)
def test_the_classifier_refuses_a_wrapped_windows_drive_root(reference: str) -> None:
    """MAJOR-V10-001: the drive-root token is not anchored at character zero."""

    from cmm.events.event_payload_safety import is_private_filesystem_reference

    assert is_private_filesystem_reference(reference) is True, reference


@pytest.mark.parametrize("reference", TOP_LEVEL_DRIVE_ROOT_REFERENCES)
def test_the_classifier_still_refuses_a_top_level_drive_root(reference: str) -> None:
    """MAJOR-V10-001: the retained top-level controls keep their verdict."""

    from cmm.events.event_payload_safety import is_private_filesystem_reference

    assert is_private_filesystem_reference(reference) is True, reference


@pytest.mark.parametrize("reference", WRAPPED_DRIVE_ROOT_EQUIVALENT_SPELLINGS)
def test_every_wrapped_drive_root_spelling_is_classified_identically(
    reference: str,
) -> None:
    """MAJOR-V10-001: one location, one verdict — no spelling may be admitted.

    ``WRAPPED_WINDOWS_DRIVE_ROOT_REFERENCES_HAVE_THE_SAME_UNSAFE_CLASSIFICATION_AS_TOP_LEVEL_DRIVE_ROOT_REFERENCES``
    """

    from cmm.events.event_payload_safety import is_private_filesystem_reference

    assert is_private_filesystem_reference(reference) is True, reference


@pytest.mark.parametrize(
    "family",
    WRAPPED_DRIVE_ROOT_EQUIVALENCE_FAMILIES,
    ids=lambda family: family[0].replace("/", "_").replace(":", "-"),
)
def test_wrapped_drive_root_equivalence_families_share_one_verdict(
    family: tuple[str, ...],
) -> None:
    """MAJOR-V10-001: equivalent spellings of one location never disagree."""

    from cmm.events import event_payload_safety as authority

    verdicts = {
        authority.is_private_filesystem_reference(spelling) for spelling in family
    }
    assert verdicts == {True}, family


def test_the_identifier_grammar_admits_the_wrapper_so_the_classifier_must_refuse() -> (
    None
):
    """MAJOR-V10-001: the bypass is a classifier defect, not a grammar defect.

    The V10 reproductions are single safe-character tokens.  The refusal therefore
    has to come from the filesystem classifier; if this assertion ever fails the
    finding has moved and this module no longer proves what it claims.
    """

    from cmm.events import event_payload_safety as authority

    for reference in WRAPPED_DRIVE_ROOT_REFERENCES:
        assert authority._SAFE_IDENTIFIER_PATTERN.match(reference) is not None, (
            reference
        )
        assert authority.is_private_filesystem_reference(reference) is True, reference


def test_the_drive_root_rule_matches_at_a_segment_boundary_not_only_at_offset_zero() -> (
    None
):
    """MAJOR-V10-001: the rule lives in the canonical pattern set, segment-anchored.

    A wrapped reference is refused because one of the *existing* canonical
    filesystem signatures matches it on the analysis form at a path-segment
    boundary.  This is what makes the fix structural rather than a new scanner.
    """

    from cmm.events import event_payload_safety as authority

    canonical = authority._analyze_lexical_path(
        "provider/C:/Windows/System32/config/SAM"
    ).canonical
    assert canonical.startswith("provider/C:/")
    assert any(
        pattern.search(canonical) for pattern in authority._PRIVATE_FILESYSTEM_PATTERNS
    ), canonical


def test_the_drive_root_rule_is_not_a_reproduced_filename_denylist() -> None:
    """MAJOR-V10-001: the rule is structural, so an unnamed location is refused too.

    The audit named ``Windows/System32/config/SAM`` and ``.../SECURITY``.  No
    pattern mentions those location names, and the fresh probes name drives and
    locations no pattern mentions either, yet all of them are refused.  The V10 fix
    is therefore a structural classification of the drive-root token rather than a
    literal appended for each audited string.
    """

    from cmm.events import event_payload_safety as authority

    pattern_sources = " ".join(
        pattern.pattern for pattern in authority._PRIVATE_FILESYSTEM_PATTERNS
    )
    for audited_name in (
        "SAM",
        "SECURITY",
        "MachineKeys",
        "System32",
        "ProgramData",
        "Windows",
    ):
        assert audited_name not in pattern_sources, audited_name

    for reference in FRESH_WRAPPED_DRIVE_ROOT_REFERENCES:
        assert authority.is_private_filesystem_reference(reference) is True, reference


def test_the_drive_root_classifier_performs_no_filesystem_io() -> None:
    """MAJOR-V10-001: classification stays lexical — no I/O and no resolution."""

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
        for reference in ALL_DRIVE_ROOT_REFERENCES:
            assert authority.is_private_filesystem_reference(reference) is True
        for reference in ALL_ACCEPTED_CONTROLS:
            assert authority.is_private_filesystem_reference(reference) is False
    finally:
        for holder, name, original in saved:
            setattr(holder, name, original)


def test_the_drive_root_rule_reuses_the_existing_safety_authority() -> None:
    """MAJOR-V10-001: no second path/URI policy module was introduced."""

    import cmm.events.event_payload_safety as authority

    module_files = {path.name for path in Path(authority.__file__).parent.glob("*.py")}
    assert "event_path_policy.py" not in module_files
    assert "event_drive_root_policy.py" not in module_files
    assert "event_windows_path_policy.py" not in module_files
    assert "identifier_policy.py" not in module_files
    assert "path_canonicalization.py" not in module_files


# ── the shared identifier authority ────────────────────────────────────────


@pytest.mark.parametrize("reference", WRAPPED_DRIVE_ROOT_REFERENCES)
def test_the_identifier_authority_refuses_a_wrapped_drive_root(reference: str) -> None:
    """MAJOR-V10-001: the shared validator refuses every wrapped spelling."""

    from cmm.events.event_payload_safety import validate_platform_identifier

    with pytest.raises(REJECTIONS):
        validate_platform_identifier(reference, field="probe")


@pytest.mark.parametrize("reference", TOP_LEVEL_DRIVE_ROOT_REFERENCES)
def test_the_identifier_authority_still_refuses_a_top_level_drive_root(
    reference: str,
) -> None:
    """MAJOR-V10-001: the retained top-level validator controls are unchanged."""

    from cmm.events.event_payload_safety import validate_platform_identifier

    with pytest.raises(REJECTIONS):
        validate_platform_identifier(reference, field="probe")


@pytest.mark.parametrize("reference", BACKSLASH_DRIVE_ROOT_REFERENCES)
def test_backslash_drive_root_spellings_are_refused_by_the_identifier_grammar(
    reference: str,
) -> None:
    """MAJOR-V10-001: ``\\`` is outside the grammar, so it is refused earlier.

    This is a positive fail-closed fact: the V10 fix does not need to widen the
    identifier grammar to cover the Windows-backslash spelling, and it does not
    rely on doing so.
    """

    from cmm.events import event_payload_safety as authority

    assert authority._SAFE_IDENTIFIER_PATTERN.match(reference) is None, reference
    with pytest.raises(REJECTIONS):
        authority.validate_platform_identifier(reference, field="probe")


@pytest.mark.parametrize(
    "reference",
    PUBLIC_REFERENCES_UNCHANGED
    + SEGMENT_COLON_REFERENCES_UNCHANGED
    + CREDENTIAL_FREE_URIS_UNCHANGED,
)
def test_supported_public_references_are_still_accepted(reference: str) -> None:
    """MAJOR-V10-001 positive control: the fix does not over-correct."""

    from cmm.events.event_payload_safety import validate_platform_identifier

    assert validate_platform_identifier(reference, field="probe") == reference


@pytest.mark.parametrize("reference", COLON_LOGICAL_IDENTIFIERS_UNCHANGED)
def test_colon_bearing_logical_identifiers_are_still_accepted(reference: str) -> None:
    """MAJOR-V10-001 positive control: not every ``letter:`` is a drive root."""

    from cmm.events.event_payload_safety import validate_platform_identifier

    assert validate_platform_identifier(reference, field="probe") == reference


def test_the_wrapped_drive_root_refusal_message_is_static() -> None:
    """MAJOR-V10-001: the refusal never echoes the audited local location."""

    from cmm.events.event_payload_safety import validate_platform_identifier

    reference = "provider/C:/Windows/System32/config/SAM"
    with pytest.raises(PlatformEventPayloadError) as excinfo:
        validate_platform_identifier(reference, field="probe")

    message = str(excinfo.value)
    assert "provider" not in message
    assert "SAM" not in message
    assert reference not in message
    assert "private filesystem location" in message


def test_an_accepted_reference_is_persisted_without_its_spelling_mutated() -> None:
    """MAJOR-V10-001: the fix classifies; it never rewrites an accepted value."""

    from cmm.events.event_payload_safety import validate_platform_identifier

    for reference in ALL_ACCEPTED_CONTROLS:
        assert validate_platform_identifier(reference, field="probe") == reference


# ── the canonical EventSystem ──────────────────────────────────────────────


@pytest.mark.parametrize("reference", REPORTED_WRAPPED_DRIVE_ROOT_REFERENCES)
def test_the_event_system_refuses_a_reported_wrapped_drive_root(
    reference: str,
) -> None:
    """MAJOR-V10-001: canonical publication refuses before persistence."""

    system, received = _watching_system()

    with pytest.raises(REJECTIONS):
        system.publish(
            "message.received",
            {"request_id": reference},
            event_id=f"evt-v10-sys-{next(_CONTROL_IDS)}",
        )

    _assert_nothing_reached_persistence(system, received)


@pytest.mark.parametrize("reference", WRAPPED_DRIVE_ROOT_REFERENCES)
def test_the_file_backed_repository_persists_nothing_for_a_wrapped_drive_root(
    tmp_path: Path, reference: str
) -> None:
    """MAJOR-V10-001: the durable store is byte-identical after refusal."""

    store = _durable_store(tmp_path)
    system = _file_backed_system(store)
    before = _durable_bytes(store)

    with pytest.raises(REJECTIONS):
        system.publish(
            "message.received",
            {"request_id": reference},
            event_id=f"evt-v10-durable-{next(_CONTROL_IDS)}",
        )

    assert system.repository.count() == 0
    assert system.dead_letter_count() == 0
    assert _durable_bytes(store) == before
    assert not store.exists() or store.read_bytes() == b""


@pytest.mark.parametrize("reference", WRAPPED_DRIVE_ROOT_REFERENCES)
def test_a_manual_publish_event_cannot_bypass_the_wrapped_drive_root_rule(
    reference: str,
) -> None:
    """MAJOR-V10-001: the manual canonical boundary re-applies the same rule."""

    system, received = _watching_system()
    event = manual_event(
        "message.received",
        {"request_id": reference},
        event_id=f"evt-v10-manual-{next(_CONTROL_IDS)}",
    )

    with pytest.raises(REJECTIONS):
        system.publish_event(event)

    _assert_nothing_reached_persistence(system, received)


@pytest.mark.parametrize("reference", ALL_ACCEPTED_CONTROLS)
def test_accepted_references_still_publish_and_keep_their_identity(
    reference: str,
) -> None:
    """MAJOR-V10-001 positive control: identity/correlation/causation unchanged."""

    system, received = _watching_system()
    event_id = f"evt-v10-ok-{next(_CONTROL_IDS)}"

    result = system.publish(
        "message.received",
        {"request_id": "req-v10-ok", "workflow_id": reference},
        event_id=event_id,
        aggregate_id=reference,
        correlation_id="CORR-V10-ORIGINAL",
        causation_id="CAUSE-V10-ORIGINAL",
    )

    assert result.persisted is True
    assert system.repository.count() == 1
    assert len(received) == 1
    assert system.dead_letter_count() == 0
    stored = system.repository.get(event_id)
    assert stored is not None
    assert stored.header.workflow_id == reference
    assert stored.header.aggregate_id == reference
    assert stored.header.correlation_id == "CORR-V10-ORIGINAL"
    assert stored.header.causation_id == "CAUSE-V10-ORIGINAL"


# ── every shared persisted identifier channel ─────────────────────────────


@pytest.mark.parametrize(
    ("label", "build"),
    SHARED_CHANNELS,
    ids=_SHARED_CHANNEL_IDS,
)
@pytest.mark.parametrize(
    "reference",
    REPORTED_WRAPPED_DRIVE_ROOT_REFERENCES,
    ids=_REFERENCE_IDS,
)
def test_every_shared_channel_refuses_the_reported_wrapped_drive_root(
    label: str, build: Any, reference: str
) -> None:
    """MAJOR-V10-001: all 13 shared channels refuse, not just ``request_id``."""

    payload, header_facts = build(reference)
    system, received = _watching_system()

    with pytest.raises(REJECTIONS):
        system.publish(
            "message.received",
            payload,
            event_id=f"evt-v10-channel-{label}-{next(_CONTROL_IDS)}",
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
    FRESH_WRAPPED_DRIVE_ROOT_REFERENCES,
    ids=_REFERENCE_IDS,
)
def test_every_shared_channel_refuses_a_fresh_wrapped_drive_root(
    label: str, build: Any, reference: str
) -> None:
    """MAJOR-V10-001: the fix is structural on every channel, not string-specific."""

    payload, header_facts = build(reference)
    system, received = _watching_system()

    with pytest.raises(REJECTIONS):
        system.publish(
            "message.received",
            payload,
            event_id=f"evt-v10-fresh-{label}-{next(_CONTROL_IDS)}",
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
    """MAJOR-V10-001: refusal is proven by the durable store, per channel."""

    store = _durable_store(tmp_path)
    system = _file_backed_system(store)
    payload, header_facts = build(REPORTED_WRAPPED_DRIVE_ROOT_REFERENCES[0])
    before = _durable_bytes(store)

    with pytest.raises(REJECTIONS):
        system.publish(
            "message.received",
            payload,
            event_id=f"evt-v10-durable-channel-{label}",
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
    PUBLIC_REFERENCES_UNCHANGED + SEGMENT_COLON_REFERENCES_UNCHANGED,
    ids=_REFERENCE_IDS,
)
def test_every_shared_channel_still_accepts_a_public_reference(
    label: str, build: Any, reference: str
) -> None:
    """MAJOR-V10-001 positive control: public references persist on every channel."""

    payload, header_facts = build(reference)
    system, received = _watching_system()

    result = system.publish(
        "message.received",
        payload,
        event_id=f"evt-v10-ok-{label}-{next(_CONTROL_IDS)}",
        **header_facts,
    )

    assert result.persisted is True
    assert system.repository.count() == 1
    assert len(received) == 1
    assert system.dead_letter_count() == 0
