"""Phase 11.22 — Remediation V8 adversarial regressions.

These tests make the independent Re-audit V8 reproductions executable and
permanent.  Each V8 finding gets its own named test; no finding is hidden inside
another test's assertions.

Covered findings::

    MAJOR-V8-001  the identifier/path safety authority classified the *raw text*
                  of a reference rather than a lexical path representation, so
                  lexically equivalent spellings of one non-public location
                  disagreed: ``etc/shadow`` was refused while ``etc//shadow`` and
                  ``etc/./shadow`` were durably persisted, and
                  ``private/var/db/keychains`` was refused while
                  ``private//var/db/keychains`` and
                  ``private/./var/db/keychains`` were too.  Fresh V8 probing also
                  showed unmistakable system/private path forms absent from the
                  pattern list still accepted (``proc/self/environ``,
                  ``etc/ssh/ssh_host_rsa_key``, ``Windows/System32/config/SAM``,
                  ``Library/Keychains/login.keychain-db``), so the classifier was
                  still a list of selected spellings rather than a fail-closed
                  classification of non-public filesystem references.
    MAJOR-V8-002  the V7 URI userinfo rule recognized a password-bearing
                  authority only when the URI began at character zero, so a
                  wrapped/nested connection URL
                  (``jdbc:postgresql://alice:supersecret@example.com/db``,
                  ``provider/https://alice:supersecret@example.com/db``,
                  ``foo:https://alice:supersecret@example.com/db``) passed the
                  identifier validator and was durably persisted.

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

Every adversarial test here reproduces the behaviour the independent Re-audit V8
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

#: The exact path-equivalent spellings the independent Re-audit V8 published.
PATH_EQUIVALENT_REFERENCES = (
    "safe/etc//shadow",
    "safe/etc/./shadow",
    "safe/private//var/db/keychains",
    "safe/private/./var/db/keychains",
)

#: The fresh V8 probes: unmistakable system/private path forms that the current
#: pattern list never named.
STRONG_NON_PUBLIC_PATH_REFERENCES = (
    "proc/self/environ",
    "etc/ssh/ssh_host_rsa_key",
    "Windows/System32/config/SAM",
    "Library/Keychains/login.keychain-db",
)

#: Every non-public filesystem reference the classifier must refuse.
NON_PUBLIC_FILESYSTEM_REFERENCES = (
    PATH_EQUIVALENT_REFERENCES + STRONG_NON_PUBLIC_PATH_REFERENCES
)

#: The V6/V7 reproductions that must stay refused.
PRIOR_NON_PUBLIC_REFERENCES = (
    "etc/shadow",
    "private/var/db/keychains",
    "safe/../../etc/shadow",
    "foo/../bar/../../private/var",
    "/Users/alice/.ssh/id_rsa",
    "Users/alice/.ssh/id_rsa",
    "C:/Users/alice/.ssh/id_rsa",
    "C:\\Users\\alice\\.ssh\\id_rsa",
    "file:///Users/alice/.ssh/id_rsa",
    "nfs://server/etc/shadow",
)

#: Non-public path spellings that merely *contain* a URI authority marker.  Under
#: POSIX path semantics ``a://x`` names ``a/x``, so a value must not be treated as
#: "a URI" — and therefore exempted from filesystem classification — merely because
#: a ``://`` appears inside it.  The path-shaped residue around every URI is
#: classified too.
URI_SUFFIXED_NON_PUBLIC_REFERENCES = (
    "proc/self/environ://x",
    "etc/shadow://x",
    "safe/etc/./shadow://x",
    "Windows/System32/config/SAM://x",
)

#: Families mixing a plain non-public path with its URI-suffixed spelling.  Both
#: members must receive the identical classification.
URI_SUFFIXED_EQUIVALENCE_FAMILIES = (
    ("proc/self/environ", "proc/self/environ://x"),
    ("etc/shadow", "etc/shadow://x"),
    ("safe/etc/./shadow", "safe/etc/./shadow://x"),
    ("Windows/System32/config/SAM", "Windows/System32/config/SAM://x"),
)

#: Families of lexically equivalent spellings of one location.  Every member of a
#: family must receive the *identical* safety classification: the invariant the
#: V8 finding is about.  Each family here is a non-public location, so the one
#: required classification is ``rejected``.
PATH_EQUIVALENCE_FAMILIES = (
    (
        "etc/shadow",
        "etc//shadow",
        "etc/./shadow",
        "ETC/SHADOW",
        "Etc/./Shadow",
        "etc/././shadow",
        "safe/../etc/shadow",
    ),
    (
        "private/var/db/keychains",
        "private//var/db/keychains",
        "private/./var/db/keychains",
        "PRIVATE/VAR/DB/KEYCHAINS",
        "safe/private/./var/db/keychains",
    ),
    (
        "proc/self/environ",
        "proc//self/./environ",
        "PROC/self/environ",
    ),
    (
        "etc/ssh/ssh_host_rsa_key",
        "etc//ssh/./ssh_host_rsa_key",
    ),
    (
        "Windows/System32/config/SAM",
        "Windows//System32/./config/SAM",
        "WINDOWS/System32/config/SAM",
    ),
    (
        "Library/Keychains/login.keychain-db",
        "Library//Keychains/./login.keychain-db",
    ),
)

#: Families of lexically equivalent spellings of one *public-safe* logical
#: reference.  The same invariant applies in the accepting direction.
LEGITIMATE_EQUIVALENCE_FAMILIES = (
    ("provider/model", "provider//model", "provider/./model"),
    (
        "cmm/orchestration/step",
        "cmm//orchestration/./step",
        "cmm/orchestration/step",
    ),
)

#: The exact wrapped/nested URI userinfo credentials the independent Re-audit V8
#: published, plus the structurally equivalent prefixed form it also reported.
WRAPPED_URI_USERINFO_REFERENCES = (
    "jdbc:postgresql://alice:supersecret@example.com/db",
    "jdbc:mysql://root:hunter2hunter2@example.com/db",
    "provider/https://alice:supersecret@example.com/db",
    "foo:https://alice:supersecret@example.com/db",
)

#: A value whose *first* authority-bearing URI is credential-free and whose later
#: authority carries a password.  A detector that inspects only the first
#: occurrence cannot see it.
LATER_AUTHORITY_USERINFO_REFERENCES = (
    "https://example.com/db+postgres://alice:supersecret@example.com/db",
)

#: Percent-encoded spellings of the same wrapped credential structure.  The outer
#: identifier grammar refuses ``%``, so these never reach persistence through the
#: identifier channels — the helper-level regression below still proves that the
#: decoded ``name:secret`` form is detected rather than trusted.
PERCENT_ENCODED_WRAPPED_REFERENCES = (
    "jdbc:postgresql://alice%3Asupersecret@example.com/db",
    "provider/https://alice%3Asupersecret@example.com/db",
)

#: Every wrapped/nested URI credential spelling the V8 rule must reject.
ALL_WRAPPED_URI_USERINFO_REFERENCES = (
    WRAPPED_URI_USERINFO_REFERENCES
    + LATER_AUTHORITY_USERINFO_REFERENCES
    + PERCENT_ENCODED_WRAPPED_REFERENCES
)

#: Credential-free wrapped URIs current producers can publish.  The fix must not
#: over-correct them: only a password-bearing authority is a credential.
CREDENTIAL_FREE_WRAPPED_URIS = (
    "jdbc:postgresql://example.com/db",
    "jdbc:mysql://example.com/db",
    "provider/https://example.com/db",
    "foo:https://example.com/db",
)

#: Legitimate public references that must survive every V8 rule untouched.
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

#: Legitimate credential-free URIs the userinfo rule must not over-correct.
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
    event_id: str = "evt-v8-manual",
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
        lambda r: ({"request_id": "req-v8-channel", "workflow_id": r}, {}),
    ),
    (
        "payload_aggregate_id",
        lambda r: ({"request_id": "req-v8-channel", "aggregate_id": r}, {}),
    ),
    (
        "payload_producer",
        lambda r: ({"request_id": "req-v8-channel", "producer": r}, {}),
    ),
    ("header_producer", lambda r: ({"request_id": "req-v8-channel"}, {"producer": r})),
    (
        "header_aggregate_id",
        lambda r: ({"request_id": "req-v8-channel"}, {"aggregate_id": r}),
    ),
    (
        "header_correlation_id",
        lambda r: ({"request_id": "req-v8-channel"}, {"correlation_id": r}),
    ),
    ("header_source", lambda r: ({"request_id": "req-v8-channel"}, {"source": r})),
    (
        "permissions",
        lambda r: ({"request_id": "req-v8-channel"}, {"permissions": [r]}),
    ),
    (
        "metadata_error_type",
        lambda r: ({"request_id": "req-v8-channel"}, {"metadata": {"error_type": r}}),
    ),
    (
        "nested_result_reference",
        lambda r: (
            {"request_id": "req-v8-channel", "result_reference": {"reference_id": r}},
            {},
        ),
    ),
    (
        "structured_reference_sequence",
        lambda r: (
            {"request_id": "req-v8-channel", "approval_refs": [{"reference_id": r}]},
            {},
        ),
    ),
    (
        "domain_reference_sequence",
        lambda r: (
            {"request_id": "req-v8-channel", "supporting_domains": [r]},
            {},
        ),
    ),
)

_SHARED_CHANNEL_IDS = [case[0] for case in SHARED_CHANNELS]


# ══════════════════════════════════════════════════════════════════════════
# MAJOR-V8-001 — one lexical path analysis, one safety classification
# ══════════════════════════════════════════════════════════════════════════


def test_the_path_classifier_uses_a_pure_lexical_canonical_form() -> None:
    """MAJOR-V8-001: the analysis form collapses separators and elides ``.``."""

    from cmm.events import event_payload_safety as authority

    analysis = authority._analyze_lexical_path("safe/etc//./shadow")
    assert analysis.canonical == "safe/etc/shadow"
    assert analysis.segments == ("safe", "etc", "shadow")
    assert analysis.has_traversal is False
    assert analysis.is_absolute is False

    # The canonical form is what the classification sees, so every equivalent
    # spelling of one location produces exactly one canonical form.
    for spelling in ("etc/shadow", "etc//shadow", "etc/./shadow", "etc/././shadow"):
        assert authority._analyze_lexical_path(spelling).canonical == "etc/shadow"


def test_the_lexical_analysis_detects_traversal_before_any_elision() -> None:
    """MAJOR-V8-001: ``..`` is refused as a segment, never elided away."""

    from cmm.events import event_payload_safety as authority

    for spelling in (
        "safe/../etc/shadow",
        "safe/..\\../etc/shadow",
        "safe\\..\\..\\etc\\shadow",
        "a/b/../..",
        "..",
        "../etc/shadow",
    ):
        assert authority._analyze_lexical_path(spelling).has_traversal is True

    # A dotted name is not a traversal segment.
    for spelling in ("cmm.orchestration", "v1..2", "provider/model"):
        assert authority._analyze_lexical_path(spelling).has_traversal is False


def test_the_lexical_analysis_normalizes_separators_and_detects_absoluteness() -> None:
    """MAJOR-V8-001: a Windows spelling is the same filesystem semantic."""

    from cmm.events import event_payload_safety as authority

    assert authority._analyze_lexical_path("a\\b").canonical == "a/b"
    assert authority._analyze_lexical_path("/Users/alice").is_absolute is True
    assert authority._analyze_lexical_path("\\\\server\\share").is_absolute is True
    assert authority._analyze_lexical_path("provider/model").is_absolute is False


def test_the_path_classifier_performs_no_filesystem_io() -> None:
    """MAJOR-V8-001: classification is lexical only — no I/O, no resolution.

    The probe replaces every host-resolution entry point the classifier could
    plausibly reach for, runs the whole reference corpus, and restores the
    originals in a ``finally`` so no other test and no interpreter-exit handler
    observes the substitution.
    """

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
        for reference in NON_PUBLIC_FILESYSTEM_REFERENCES + PRIOR_NON_PUBLIC_REFERENCES:
            assert authority.is_private_filesystem_reference(reference) is True
        for reference in LEGITIMATE_REFERENCES + LEGITIMATE_CREDENTIAL_FREE_URIS:
            assert authority.is_private_filesystem_reference(reference) is False
    finally:
        for holder, name, original in saved:
            setattr(holder, name, original)


@pytest.mark.parametrize(
    "family", PATH_EQUIVALENCE_FAMILIES, ids=lambda f: f[0].replace("/", "_")
)
def test_path_equivalent_spellings_have_one_identical_classification(
    family: tuple[str, ...],
) -> None:
    """MAJOR-V8-001: equivalent spellings never disagree semantically."""

    from cmm.events import event_payload_safety as authority

    verdicts = {
        authority.is_private_filesystem_reference(spelling) for spelling in family
    }
    assert verdicts == {True}, family


@pytest.mark.parametrize(
    "family", LEGITIMATE_EQUIVALENCE_FAMILIES, ids=lambda f: f[0].replace("/", "_")
)
def test_legitimate_equivalent_spellings_also_share_one_classification(
    family: tuple[str, ...],
) -> None:
    """MAJOR-V8-001 control: the invariant holds in the accepting direction too."""

    from cmm.events import event_payload_safety as authority

    verdicts = {
        authority.is_private_filesystem_reference(spelling) for spelling in family
    }
    assert verdicts == {False}, family


@pytest.mark.parametrize(
    "family",
    URI_SUFFIXED_EQUIVALENCE_FAMILIES,
    ids=lambda f: f[0].replace("/", "_").replace(":", "_"),
)
def test_a_uri_marker_does_not_exempt_a_path_shaped_residue(
    family: tuple[str, ...],
) -> None:
    """MAJOR-V8-001: ``a://x`` names ``a/x``, so a URI marker cannot launder a path.

    A value is not "a URI" merely because a ``://`` occurs inside it.  The
    path-shaped residue around every URI is classified by the same rule, so a
    non-public location cannot enter persistence by suffixing an authority marker.
    """

    from cmm.events import event_payload_safety as authority

    verdicts = {
        authority.is_private_filesystem_reference(spelling) for spelling in family
    }
    assert verdicts == {True}, family


@pytest.mark.parametrize("reference", URI_SUFFIXED_NON_PUBLIC_REFERENCES)
def test_uri_suffixed_non_public_reference_is_rejected(reference: str) -> None:
    """MAJOR-V8-001: the URI-suffixed spelling fails closed on the shared channels."""

    system, received = _watching_system()

    with pytest.raises(REJECTIONS):
        system.publish(
            "message.received",
            {"request_id": "req-v8-uri-suffixed", "workflow_id": reference},
            event_id=f"evt-v8-uri-suffixed-{next(_CONTROL_IDS)}",
            permissions=[reference],
        )

    _assert_nothing_reached_persistence(system, received)


@pytest.mark.parametrize("reference", PATH_EQUIVALENT_REFERENCES)
def test_path_equivalent_reference_in_the_payload_identifier_is_rejected(
    reference: str,
) -> None:
    """MAJOR-V8-001: the exact audited reproduction, on the payload channel."""

    system, received = _watching_system()

    with pytest.raises(REJECTIONS):
        system.publish(
            "message.received",
            {"request_id": reference},
            event_id=f"evt-v8-equiv-payload-{next(_CONTROL_IDS)}",
        )

    _assert_nothing_reached_persistence(system, received)


@pytest.mark.parametrize("reference", PATH_EQUIVALENT_REFERENCES)
def test_path_equivalent_reference_in_the_header_producer_is_rejected(
    reference: str,
) -> None:
    """MAJOR-V8-001: the canonical header producer channel is not an escape hatch."""

    system, received = _watching_system()

    with pytest.raises(REJECTIONS):
        system.publish(
            "message.received",
            {"request_id": "req-v8-equiv-producer"},
            event_id=f"evt-v8-equiv-producer-{next(_CONTROL_IDS)}",
            producer=reference,
        )

    _assert_nothing_reached_persistence(system, received)


@pytest.mark.parametrize("reference", PATH_EQUIVALENT_REFERENCES)
def test_path_equivalent_reference_in_a_metadata_identifier_is_rejected(
    reference: str,
) -> None:
    """MAJOR-V8-001: an identifier-classified metadata fact is judged the same."""

    system, received = _watching_system()

    with pytest.raises(REJECTIONS):
        system.publish(
            "message.received",
            {"request_id": "req-v8-equiv-meta"},
            event_id=f"evt-v8-equiv-meta-{next(_CONTROL_IDS)}",
            metadata={"error_type": reference},
        )

    _assert_nothing_reached_persistence(system, received)


@pytest.mark.parametrize("reference", PATH_EQUIVALENT_REFERENCES)
def test_path_equivalent_reference_in_permissions_is_rejected(reference: str) -> None:
    """MAJOR-V8-001: every persisted identifier channel applies the one rule."""

    system, received = _watching_system()

    with pytest.raises(REJECTIONS):
        system.publish(
            "message.received",
            {"request_id": "req-v8-equiv-perm"},
            event_id=f"evt-v8-equiv-perm-{next(_CONTROL_IDS)}",
            permissions=[reference],
        )

    _assert_nothing_reached_persistence(system, received)


@pytest.mark.parametrize("reference", PATH_EQUIVALENT_REFERENCES)
def test_path_equivalent_reference_in_a_nested_structured_reference_is_rejected(
    reference: str,
) -> None:
    """MAJOR-V8-001: a nested structured reference identifier is not a bypass."""

    system, received = _watching_system()

    with pytest.raises(REJECTIONS):
        system.publish(
            "message.received",
            {
                "request_id": "req-v8-equiv-structured",
                "result_reference": {"reference_id": reference},
            },
            event_id=f"evt-v8-equiv-structured-{next(_CONTROL_IDS)}",
        )

    _assert_nothing_reached_persistence(system, received)


@pytest.mark.parametrize("reference", PATH_EQUIVALENT_REFERENCES)
def test_path_equivalent_reference_in_a_reference_sequence_is_rejected(
    reference: str,
) -> None:
    """MAJOR-V8-001: a reference sequence element is judged by the same authority."""

    system, received = _watching_system()

    with pytest.raises(REJECTIONS):
        system.publish(
            "message.received",
            {
                "request_id": "req-v8-equiv-sequence",
                "supporting_domains": [reference],
            },
            event_id=f"evt-v8-equiv-sequence-{next(_CONTROL_IDS)}",
        )

    _assert_nothing_reached_persistence(system, received)


@pytest.mark.parametrize("reference", NON_PUBLIC_FILESYSTEM_REFERENCES)
def test_every_non_public_filesystem_reference_is_rejected(reference: str) -> None:
    """MAJOR-V8-001: the strong V8 probes cannot persist either."""

    system, received = _watching_system()

    with pytest.raises(REJECTIONS):
        system.publish(
            "message.received",
            {"request_id": "req-v8-strong", "workflow_id": reference},
            event_id=f"evt-v8-strong-{next(_CONTROL_IDS)}",
        )

    _assert_nothing_reached_persistence(system, received)


@pytest.mark.parametrize(
    ("label", "build"),
    SHARED_CHANNELS,
    ids=_SHARED_CHANNEL_IDS,
)
@pytest.mark.parametrize("reference", PATH_EQUIVALENT_REFERENCES)
def test_path_equivalent_reference_is_rejected_on_every_shared_channel(
    label: str,
    build: Any,
    reference: str,
) -> None:
    """MAJOR-V8-001: one authority, therefore every persisted channel fails closed."""

    payload, header_facts = build(reference)
    system, received = _watching_system()

    with pytest.raises(REJECTIONS):
        system.publish(
            "message.received",
            payload,
            event_id=f"evt-v8-{label}-{next(_CONTROL_IDS)}",
            **header_facts,
        )

    _assert_nothing_reached_persistence(system, received)


@pytest.mark.parametrize(
    ("label", "build"),
    SHARED_CHANNELS,
    ids=_SHARED_CHANNEL_IDS,
)
@pytest.mark.parametrize("reference", STRONG_NON_PUBLIC_PATH_REFERENCES)
def test_strong_non_public_path_is_rejected_on_every_shared_channel(
    label: str,
    build: Any,
    reference: str,
) -> None:
    """MAJOR-V8-001: the fail-closed classification, on every persisted channel."""

    payload, header_facts = build(reference)
    system, received = _watching_system()

    with pytest.raises(REJECTIONS):
        system.publish(
            "message.received",
            payload,
            event_id=f"evt-v8-strong-{label}-{next(_CONTROL_IDS)}",
            **header_facts,
        )

    _assert_nothing_reached_persistence(system, received)


def test_path_equivalent_reference_in_a_manual_event_is_rejected() -> None:
    """MAJOR-V8-001: the manual publication boundary applies the same rule."""

    system, received = _watching_system()

    with pytest.raises(REJECTIONS):
        system.publish_event(
            manual_event(
                "message.received",
                {"request_id": "safe/etc//shadow"},
                event_id="evt-v8-equiv-manual",
            )
        )

    _assert_nothing_reached_persistence(system, received)


def test_no_non_public_filesystem_reference_reaches_the_durable_file(
    tmp_path: Path,
) -> None:
    """MAJOR-V8-001: no durable byte may contain an audited non-public reference."""

    store = _durable_store(tmp_path)
    system = _file_backed_system(store)
    before = _durable_bytes(store)

    for reference in NON_PUBLIC_FILESYSTEM_REFERENCES + PRIOR_NON_PUBLIC_REFERENCES:
        with pytest.raises(REJECTIONS):
            system.publish(
                "message.received",
                {"request_id": reference},
                event_id=f"evt-v8-fs-durable-{next(_CONTROL_IDS)}",
            )

    assert system.repository.count() == 0
    assert _durable_bytes(store) == before
    durable = _durable_bytes(store)
    for marker in (b"shadow", b"keychain", b"environ", b"SAM", b"host_rsa"):
        assert marker not in durable


def test_prior_v6_v7_filesystem_references_stay_rejected(tmp_path: Path) -> None:
    """MAJOR-V8-001 regression gate: the V6/V7 refusals are preserved exactly."""

    store = _durable_store(tmp_path)
    system = _file_backed_system(store)
    before = _durable_bytes(store)

    for reference in PRIOR_NON_PUBLIC_REFERENCES:
        with pytest.raises(REJECTIONS):
            system.publish(
                "message.received",
                {"request_id": reference},
                event_id=f"evt-v8-prior-{next(_CONTROL_IDS)}",
            )

    assert system.repository.count() == 0
    assert _durable_bytes(store) == before


@pytest.mark.parametrize("reference", LEGITIMATE_REFERENCES)
def test_legitimate_references_survive_the_v8_path_rules(reference: str) -> None:
    """MAJOR-V8-001 control: real references are not path-shaped and stay valid."""

    system, received = _watching_system()

    event_id = f"evt-v8-ref-{next(_CONTROL_IDS)}"
    result = system.publish(
        "message.received",
        {"request_id": "req-v8-ref", "workflow_id": reference},
        event_id=event_id,
    )

    assert result.persisted is True
    assert result.event.header.workflow_id == reference
    assert len(received) == 1
    assert system.repository.count() == 1


@pytest.mark.parametrize(
    "reference",
    LEGITIMATE_CREDENTIAL_FREE_URIS + CREDENTIAL_FREE_WRAPPED_URIS,
)
def test_credential_free_uri_references_survive_the_v8_path_rules(
    reference: str,
) -> None:
    """MAJOR-V8-001 control: a credential-free URI is not a filesystem path."""

    system, _received = _watching_system()

    result = system.publish(
        "message.received",
        {"request_id": "req-v8-uri-ref", "workflow_id": reference},
        event_id=f"evt-v8-uri-ref-{next(_CONTROL_IDS)}",
        aggregate_id=reference,
    )

    assert result.persisted is True
    stored = system.repository.get(result.event.header.event_id)
    assert stored is not None
    assert stored.header.aggregate_id == reference


def test_the_classifier_never_rewrites_the_persisted_identifier() -> None:
    """MAJOR-V8-001: canonicalization is for analysis only, never for storage."""

    system, _received = _watching_system()

    result = system.publish(
        "message.received",
        {"request_id": "req-v8-nomutate", "workflow_id": "provider//model"},
        event_id="evt-v8-nomutate",
        aggregate_id="cmm//orchestration/./step",
    )

    assert result.persisted is True
    stored = system.repository.get("evt-v8-nomutate")
    assert stored is not None
    # The persisted fact is the caller's exact value; the canonical form exists
    # only inside the safety analysis.
    assert stored.header.workflow_id == "provider//model"
    assert stored.header.aggregate_id == "cmm//orchestration/./step"


def test_legitimate_identifiers_survive_every_canonical_header_channel() -> None:
    """MAJOR-V8-001 control: the header identifier channels keep real references."""

    system, _received = _watching_system()

    result = system.publish(
        "message.received",
        {"request_id": "req-v8-ref-header", "domain_id": "domain:legal"},
        event_id="evt-v8-ref-header",
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
# MAJOR-V8-002 — every authority-bearing URI is inspected, however wrapped
# ══════════════════════════════════════════════════════════════════════════


def test_the_userinfo_rule_inspects_every_authority_not_only_offset_zero() -> None:
    """MAJOR-V8-002: the helper is wrapper-independent and occurrence-independent."""

    from cmm.events.event_payload_safety import contains_uri_userinfo_credential

    for value in WRAPPED_URI_USERINFO_REFERENCES + LATER_AUTHORITY_USERINFO_REFERENCES:
        assert contains_uri_userinfo_credential(value) is True, value

    for value in LEGITIMATE_CREDENTIAL_FREE_URIS + CREDENTIAL_FREE_WRAPPED_URIS:
        assert contains_uri_userinfo_credential(value) is False, value

    # Only a *password* component is a credential: a bare username is not, and an
    # empty password is not.
    assert contains_uri_userinfo_credential("https://alice@example.com/db") is False
    assert (
        contains_uri_userinfo_credential("jdbc:postgresql://alice@example.com/db")
        is False
    )
    assert contains_uri_userinfo_credential("https://:secret@example.com/db") is True
    assert (
        contains_uri_userinfo_credential("jdbc:postgresql://:secret@example.com/db")
        is True
    )
    assert contains_uri_userinfo_credential("https://alice:@example.com/db") is False


def test_the_userinfo_rule_percent_decodes_before_the_password_test() -> None:
    """MAJOR-V8-002: an encoded userinfo that decodes to ``name:secret`` is a credential.

    The identifier grammar refuses ``%`` outright, so a percent-encoded userinfo
    never reaches persistence through the identifier channels.  That is a defence,
    not the rule: if the grammar ever admitted ``%`` the semantic check must
    already catch the decoded ``name:secret`` form.  This proves the decoded-form
    detection itself, for the top-level *and* the wrapped spelling.
    """

    from cmm.events.event_payload_safety import contains_uri_userinfo_credential

    for value in PERCENT_ENCODED_WRAPPED_REFERENCES:
        assert contains_uri_userinfo_credential(value) is True, value

    assert (
        contains_uri_userinfo_credential(
            "jdbc:postgresql://alice%3Asupersecret@example.com/db"
        )
        is True
    )
    assert (
        contains_uri_userinfo_credential(
            "https://admin%3Ahunter2hunter2@example.com/path"
        )
        is True
    )
    # A percent-encoded but password-free userinfo stays credential-free.
    assert contains_uri_userinfo_credential("https://alice%40example.com/db") is False


@pytest.mark.parametrize("reference", WRAPPED_URI_USERINFO_REFERENCES)
def test_wrapped_uri_userinfo_in_the_payload_identifier_is_rejected(
    reference: str,
) -> None:
    """MAJOR-V8-002: the exact audited reproduction, on the payload channel."""

    system, received = _watching_system()

    with pytest.raises(REJECTIONS):
        system.publish(
            "message.received",
            {"request_id": reference},
            event_id=f"evt-v8-uri-payload-{next(_CONTROL_IDS)}",
        )

    _assert_nothing_reached_persistence(system, received)


@pytest.mark.parametrize("reference", WRAPPED_URI_USERINFO_REFERENCES)
def test_wrapped_uri_userinfo_in_the_header_producer_is_rejected(
    reference: str,
) -> None:
    """MAJOR-V8-002: the canonical header producer channel is not an escape hatch."""

    system, received = _watching_system()

    with pytest.raises(REJECTIONS):
        system.publish(
            "message.received",
            {"request_id": "req-v8-uri-producer"},
            event_id=f"evt-v8-uri-producer-{next(_CONTROL_IDS)}",
            producer=reference,
        )

    _assert_nothing_reached_persistence(system, received)


@pytest.mark.parametrize("reference", WRAPPED_URI_USERINFO_REFERENCES)
def test_wrapped_uri_userinfo_in_a_metadata_identifier_is_rejected(
    reference: str,
) -> None:
    """MAJOR-V8-002: an identifier-classified metadata fact is judged the same."""

    system, received = _watching_system()

    with pytest.raises(REJECTIONS):
        system.publish(
            "message.received",
            {"request_id": "req-v8-uri-meta"},
            event_id=f"evt-v8-uri-meta-{next(_CONTROL_IDS)}",
            metadata={"error_type": reference},
        )

    _assert_nothing_reached_persistence(system, received)


@pytest.mark.parametrize("reference", WRAPPED_URI_USERINFO_REFERENCES)
def test_wrapped_uri_userinfo_in_permissions_is_rejected(reference: str) -> None:
    """MAJOR-V8-002: every persisted identifier channel applies the one rule."""

    system, received = _watching_system()

    with pytest.raises(REJECTIONS):
        system.publish(
            "message.received",
            {"request_id": "req-v8-uri-perm"},
            event_id=f"evt-v8-uri-perm-{next(_CONTROL_IDS)}",
            permissions=[reference],
        )

    _assert_nothing_reached_persistence(system, received)


@pytest.mark.parametrize("reference", WRAPPED_URI_USERINFO_REFERENCES)
def test_wrapped_uri_userinfo_in_a_nested_structured_reference_is_rejected(
    reference: str,
) -> None:
    """MAJOR-V8-002: a nested structured reference identifier is not a bypass."""

    system, received = _watching_system()

    with pytest.raises(REJECTIONS):
        system.publish(
            "message.received",
            {
                "request_id": "req-v8-uri-structured",
                "result_reference": {"reference_id": reference},
            },
            event_id=f"evt-v8-uri-structured-{next(_CONTROL_IDS)}",
        )

    _assert_nothing_reached_persistence(system, received)


@pytest.mark.parametrize("reference", WRAPPED_URI_USERINFO_REFERENCES)
def test_wrapped_uri_userinfo_in_a_reference_sequence_is_rejected(
    reference: str,
) -> None:
    """MAJOR-V8-002: a reference sequence element is judged by the same authority."""

    system, received = _watching_system()

    with pytest.raises(REJECTIONS):
        system.publish(
            "message.received",
            {
                "request_id": "req-v8-uri-sequence",
                "supporting_domains": [reference],
            },
            event_id=f"evt-v8-uri-sequence-{next(_CONTROL_IDS)}",
        )

    _assert_nothing_reached_persistence(system, received)


@pytest.mark.parametrize("reference", LATER_AUTHORITY_USERINFO_REFERENCES)
def test_a_later_authority_credential_is_rejected(reference: str) -> None:
    """MAJOR-V8-002: not inspecting only the first ``://`` occurrence matters."""

    system, received = _watching_system()

    with pytest.raises(REJECTIONS):
        system.publish(
            "message.received",
            {"request_id": reference},
            event_id=f"evt-v8-uri-multi-{next(_CONTROL_IDS)}",
        )

    _assert_nothing_reached_persistence(system, received)


@pytest.mark.parametrize(
    ("label", "build"),
    SHARED_CHANNELS,
    ids=_SHARED_CHANNEL_IDS,
)
@pytest.mark.parametrize("reference", WRAPPED_URI_USERINFO_REFERENCES)
def test_wrapped_uri_userinfo_is_rejected_on_every_shared_channel(
    label: str,
    build: Any,
    reference: str,
) -> None:
    """MAJOR-V8-002: one authority, therefore every persisted channel fails closed."""

    payload, header_facts = build(reference)
    system, received = _watching_system()

    with pytest.raises(REJECTIONS):
        system.publish(
            "message.received",
            payload,
            event_id=f"evt-v8-uri-{label}-{next(_CONTROL_IDS)}",
            **header_facts,
        )

    _assert_nothing_reached_persistence(system, received)


def test_wrapped_uri_userinfo_in_a_manual_event_is_rejected() -> None:
    """MAJOR-V8-002: the manual publication boundary applies the same rule."""

    system, received = _watching_system()

    with pytest.raises(REJECTIONS):
        system.publish_event(
            manual_event(
                "message.received",
                {"request_id": "jdbc:postgresql://alice:supersecret@example.com/db"},
                event_id="evt-v8-uri-manual",
            )
        )

    _assert_nothing_reached_persistence(system, received)


def test_wrapped_uri_userinfo_never_reaches_the_durable_file(tmp_path: Path) -> None:
    """MAJOR-V8-002: no durable byte may contain an audited URI password."""

    store = _durable_store(tmp_path)
    system = _file_backed_system(store)
    before = _durable_bytes(store)

    for reference in WRAPPED_URI_USERINFO_REFERENCES:
        with pytest.raises(REJECTIONS):
            system.publish(
                "message.received",
                {"request_id": reference},
                event_id=f"evt-v8-uri-durable-{next(_CONTROL_IDS)}",
            )

    assert system.repository.count() == 0
    assert _durable_bytes(store) == before
    durable = _durable_bytes(store)
    assert b"supersecret" not in durable
    assert b"hunter2hunter2" not in durable


def test_wrapped_uri_userinfo_is_rejected_through_the_file_backed_repository(
    tmp_path: Path,
) -> None:
    """MAJOR-V8-002: the durable repository is never the safety boundary."""

    store = _durable_store(tmp_path)
    system = _file_backed_system(store)
    before = _durable_bytes(store)

    with pytest.raises(REJECTIONS):
        system.publish(
            "message.received",
            {"request_id": "jdbc:postgresql://alice:supersecret@example.com/db"},
            event_id="evt-v8-uri-file",
        )

    assert system.repository.count() == 0
    assert _durable_bytes(store) == before


def test_the_wrapped_uri_password_never_appears_in_the_rejection_message() -> None:
    """MAJOR-V8-002: the gate refuses without echoing the secret it refused."""

    system, _received = _watching_system()

    with pytest.raises(REJECTIONS) as captured:
        system.publish(
            "message.received",
            {"request_id": "jdbc:postgresql://alice:supersecret@example.com/db"},
            event_id="evt-v8-uri-echo",
        )

    assert "supersecret" not in str(captured.value)
    assert "hunter2hunter2" not in str(captured.value)


@pytest.mark.parametrize(
    "reference",
    LEGITIMATE_CREDENTIAL_FREE_URIS
    + CREDENTIAL_FREE_WRAPPED_URIS
    + LEGITIMATE_REFERENCES,
)
def test_credential_free_uris_and_references_survive(reference: str) -> None:
    """MAJOR-V8-002 control: only semantic userinfo passwords are refused."""

    system, received = _watching_system()

    result = system.publish(
        "message.received",
        {"request_id": "req-v8-uri-ref", "workflow_id": reference},
        event_id=f"evt-v8-uri-ref-{next(_CONTROL_IDS)}",
    )

    assert result.persisted is True
    assert result.event.header.workflow_id == reference
    assert len(received) == 1


def test_credential_free_wrapped_uris_survive_the_canonical_header_channels() -> None:
    """MAJOR-V8-002 control: a credential-free wrapped URI is a public reference."""

    system, _received = _watching_system()

    result = system.publish(
        "message.received",
        {"request_id": "req-v8-uri-header"},
        event_id="evt-v8-uri-header",
        producer="cmm.orchestration",
        aggregate_id="jdbc:postgresql://example.com/db",
        permissions=["events:read"],
    )

    assert result.persisted is True
    stored = system.repository.get("evt-v8-uri-header")
    assert stored is not None
    assert stored.header.aggregate_id == "jdbc:postgresql://example.com/db"
    assert stored.header.permissions == ["events:read"]


# ══════════════════════════════════════════════════════════════════════════
# The V8 rules are one shared authority, not a request_id-only patch
# ══════════════════════════════════════════════════════════════════════════


def test_the_shared_identifier_authority_enforces_both_v8_rules() -> None:
    """MAJOR-V8-001/002: the shared authority is the single point of enforcement."""

    from cmm.events import event_payload_safety

    rejected = (
        NON_PUBLIC_FILESYSTEM_REFERENCES
        + PRIOR_NON_PUBLIC_REFERENCES
        + WRAPPED_URI_USERINFO_REFERENCES
    )
    accepted = (
        LEGITIMATE_REFERENCES
        + LEGITIMATE_CREDENTIAL_FREE_URIS
        + CREDENTIAL_FREE_WRAPPED_URIS
    )

    for value in rejected:
        with pytest.raises(PlatformEventPayloadError):
            event_payload_safety.validate_platform_identifier(value, field="probe")
    for value in accepted:
        assert (
            event_payload_safety.validate_platform_identifier(value, field="probe")
            == value
        )


def test_the_public_path_classifier_reports_every_v8_non_public_reference() -> None:
    """MAJOR-V8-001: the existing classifier answers, not a new module."""

    from cmm.events.event_payload_safety import is_private_filesystem_reference

    for value in NON_PUBLIC_FILESYSTEM_REFERENCES + PRIOR_NON_PUBLIC_REFERENCES:
        assert is_private_filesystem_reference(value) is True, value
    for value in (
        LEGITIMATE_REFERENCES
        + LEGITIMATE_CREDENTIAL_FREE_URIS
        + CREDENTIAL_FREE_WRAPPED_URIS
    ):
        assert is_private_filesystem_reference(value) is False, value


def test_the_fail_closed_classification_is_not_a_spelling_denylist() -> None:
    """MAJOR-V8-001: an unlisted system root is refused without being named.

    ``etc``/``private`` are named by the V6/V7 patterns, but ``proc``,
    ``Windows`` and ``Library`` are not.  They are refused because the classifier
    accepts only the declared public-safe slash-bearing reference classes, not
    because a new pattern was appended for each audited spelling.
    """

    from cmm.events import event_payload_safety as authority

    unlisted_roots = ("proc", "Windows", "Library", "sys", "dev", "boot", "srv")
    for root in unlisted_roots:
        assert authority.is_private_filesystem_reference(f"{root}/x/y") is True, root

    # The declared public-safe logical roots are the positive half of the same
    # fail-closed rule, and they are the roots real producers publish.
    assert authority.PUBLIC_SLASH_REFERENCE_ROOTS == frozenset({"cmm", "provider"})
    for root in sorted(authority.PUBLIC_SLASH_REFERENCE_ROOTS):
        assert authority.is_private_filesystem_reference(f"{root}/x/y") is False, root


def test_no_second_path_or_credential_policy_module_was_added() -> None:
    """Architecture guard: the V8 fix extends the existing authority in place."""

    import cmm.events.event_payload_safety as authority

    module_files = {path.name for path in Path(authority.__file__).parent.glob("*.py")}
    assert "event_path_policy.py" not in module_files
    assert "event_credential_policy.py" not in module_files
    assert "identifier_policy.py" not in module_files
    assert "path_canonicalization.py" not in module_files
