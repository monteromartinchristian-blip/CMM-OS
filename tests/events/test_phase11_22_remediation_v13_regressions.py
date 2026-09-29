"""Phase 11.22 — Remediation V13 adversarial regressions.

These tests make the independent Re-audit V13 reproduction executable and
permanent.  The V13 finding gets its own named tests; the finding is not hidden
inside another test's assertions.

Covered finding::

    MAJOR-V13-001  the canonical lexical path analysis did not account for
                   ordinary Win32 trailing-period component normalization, so a
                   Windows-equivalent spelling of an already-sensitive path
                   component kept the public verdict and was durably persisted::

                       provider/.ssh/config       REJECT
                       provider/.ssh./config      ACCEPT + persist
                       provider/.ssh../config     ACCEPT + persist

                   Win32 removes trailing ASCII periods from an otherwise named
                   path component when it resolves a name, so ``.ssh.``, ``.ssh..``
                   and ``.ssh`` denote the same location — and ``Users.`` /
                   ``Users..`` denote ``Users``, ``home.`` denotes ``home``, and so
                   on for the already-sensitive families ``.aws``, ``.gnupg``,
                   ``.kube``, ``.docker`` and ``.azure``.  Because the analysis
                   form kept the trailing period, no sensitive-family signature
                   matched and the allowlisted public slash root made the
                   reference look public::

                       provider/.ssh./config
                       cmm/.ssh./config
                       provider/.aws./config
                       provider/.kube./config
                       provider/Users./alice/config
                       cmm/Users./alice/config
                       provider/.ssh../config
                       provider/Users../alice/config

                   (and the wider fresh family: ``.SSH.``, ``.gnupg.``,
                   ``.docker.``, ``.azure.``, ``.netrc.``, ``.pgpass.``,
                   ``.npmrc.``, ``.git-credentials.``, ``users.``, ``home.`` and
                   repeated trailing-period variants) all passed
                   :func:`is_private_filesystem_reference`, passed
                   :func:`validate_platform_identifier`, were accepted by the
                   canonical ``EventSystem`` and were durably appended — through
                   all 13 shared identifier-bearing channels, in both official
                   repositories, and through a manual ``publish_event`` call.
                   ``.ssh`` is already a sensitive private directory in the
                   canonical policy, so this is not a naming ambiguity: the
                   trailing period was *shielding* a known private location.

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

Every adversarial test here reproduces the behaviour the independent Re-audit V13
reported, so it fails before the remediation and passes after it.

The remediation is deliberately *structural*: the **existing**
``_analyze_lexical_path`` safety-analysis form gains the Win32 trailing-period rule
for classification — each component's trailing ASCII periods are removed for
classification only, exactly as Win32 removes them when resolving a name — while
the raw value is never rewritten, ``..`` traversal is still detected on the raw
segment sequence before any normalization, and a component that normalizes to
empty contributes nothing (it is never folded into ``..``).  It is the same
analysis form, in the same ``event_payload_safety`` authority, consumed by the
same retained signatures — no second Win32 normalizer, path-policy module,
classifier or registry is introduced, and no literal is appended for any audited
spelling.
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

MOMENT = datetime(2026, 9, 29, 12, 0, 0, tzinfo=timezone.utc)

REJECTIONS = (PlatformEventPayloadError, TypeError, ValueError)

#: A monotonic counter so every adversarial case gets a fresh, plain-safe
#: canonical event identity instead of deriving one from the audited value.
_CONTROL_IDS = itertools.count()


# ══════════════════════════════════════════════════════════════════════════
# MAJOR-V13-001 — Win32 trailing-period path-component equivalents keep the
# unsafe verdict of their already-sensitive canonical spelling
# ══════════════════════════════════════════════════════════════════════════

#: The trailing-period sensitive references the independent Re-audit V13
#: demonstrated being **accepted and durably persisted**.  Every member is
#: admitted by the shared identifier grammar, and the analysis form kept the
#: trailing period, so no sensitive-family signature matched the wrapped location.
REPORTED_TRAILING_PERIOD_REFERENCES = (
    "provider/.ssh./config",
    "provider/.SSH./config",
    "provider/.aws./config",
    "provider/.gnupg./trustdb.gpg",
    "provider/.kube./config",
    "provider/.docker./config.json",
    "provider/.azure./profile",
    "provider/Users./alice/config",
    "provider/users./alice/config",
    "provider/home./alice/config",
    "cmm/.ssh./config",
    "cmm/Users./alice/config",
    "provider/.ssh../config",
    "provider/Users../alice/config",
)

#: Repeated trailing-period variants.  Win32 removes every trailing period, so
#: ``.ssh..`` and ``.ssh...`` are the same location as ``.ssh`` and must keep the
#: identical unsafe verdict.
REPORTED_REPEATED_TRAILING_PERIOD_REFERENCES = (
    "provider/.ssh.../config",
    "provider/.gnupg../trustdb.gpg",
    "cmm/.ssh../config",
    "provider/Users.../alice/config",
)

#: Fresh adversarial probes from the independent Re-audit V13 probe list: families,
#: casings and depths the audit did not use as its canonical example.  Each one
#: must receive the identical verdict, so the fix cannot be a literal exception
#: for the audited strings.
FRESH_TRAILING_PERIOD_REFERENCES = (
    "cmm/.aws./credentials",
    "cmm/.kube./config",
    "cmm/.gnupg./trustdb.gpg",
    "cmm/home./alice/config",
    "cmm/Users../alice/config",
    "provider/.gnupg./private-keys-v1.d/key",
    "provider/.netrc./machine",
    "provider/.pgpass./config",
    "provider/.npmrc./config",
    "provider/.git-credentials./config",
    "provider/.docker../config.json",
    "provider/.azure../profile",
    "provider/Users./alice/.ssh./config",
    "provider/home../alice/config",
    "provider/.ssh./",
)

#: Every V13 adversarial spelling, de-duplicated so the parameter ids stay
#: one-to-one with the corpus.
ALL_TRAILING_PERIOD_REFERENCES = tuple(
    dict.fromkeys(
        REPORTED_TRAILING_PERIOD_REFERENCES
        + REPORTED_REPEATED_TRAILING_PERIOD_REFERENCES
        + FRESH_TRAILING_PERIOD_REFERENCES
    )
)

#: Families of spellings of one private location.  A trailing ASCII period (or
#: several) is the same Win32 location as the canonical spelling, so every member
#: must receive the identical verdict.  This is the executable form of
#: ``WINDOWS_TRAILING_PERIOD_PATH_COMPONENT_EQUIVALENTS_HAVE_IDENTICAL_SAFETY_CLASSIFICATION``.
TRAILING_PERIOD_EQUIVALENCE_FAMILIES = (
    (
        "provider/.ssh/config",
        "provider/.ssh./config",
        "provider/.ssh../config",
        "provider/.ssh.../config",
    ),
    ("cmm/.ssh/config", "cmm/.ssh./config", "cmm/.ssh../config"),
    ("provider/.SSH/config", "provider/.SSH./config"),
    (
        "provider/Users/alice/config",
        "provider/Users./alice/config",
        "provider/Users../alice/config",
        "provider/Users.../alice/config",
    ),
    ("cmm/Users/alice/config", "cmm/Users./alice/config", "cmm/Users../alice/config"),
    ("provider/users/alice/config", "provider/users./alice/config"),
    (
        "provider/home/alice/config",
        "provider/home./alice/config",
        "provider/home../alice/config",
    ),
    ("cmm/home/alice/config", "cmm/home./alice/config"),
    ("provider/.aws/config", "provider/.aws./config"),
    ("cmm/.aws/credentials", "cmm/.aws./credentials"),
    (
        "provider/.gnupg/trustdb.gpg",
        "provider/.gnupg./trustdb.gpg",
        "provider/.gnupg../trustdb.gpg",
    ),
    ("provider/.kube/config", "provider/.kube./config"),
    ("cmm/.kube/config", "cmm/.kube./config"),
    (
        "provider/.docker/config.json",
        "provider/.docker./config.json",
        "provider/.docker../config.json",
    ),
    (
        "provider/.azure/profile",
        "provider/.azure./profile",
        "provider/.azure../profile",
    ),
    ("provider/.netrc/machine", "provider/.netrc./machine"),
    ("provider/.pgpass/config", "provider/.pgpass./config"),
    ("provider/.npmrc/config", "provider/.npmrc./config"),
    ("provider/.git-credentials/config", "provider/.git-credentials./config"),
)

#: Every spelling in every equivalence family.
TRAILING_PERIOD_EQUIVALENT_SPELLINGS = tuple(
    spelling for family in TRAILING_PERIOD_EQUIVALENCE_FAMILIES for spelling in family
)

#: The already-sensitive component families, paired with one representative tail,
#: so the structural probe can enumerate roots, families and period counts instead
#: of trusting a fixed corpus.
TRAILING_PERIOD_FAMILY_SEGMENTS = (
    (".ssh", "config"),
    (".SSH", "config"),
    (".aws", "config"),
    (".gnupg", "trustdb.gpg"),
    (".kube", "config"),
    (".docker", "config.json"),
    (".azure", "profile"),
    (".netrc", "machine"),
    (".pgpass", "config"),
    (".npmrc", "config"),
    (".git-credentials", "config"),
    ("Users", "alice/config"),
    ("users", "alice/config"),
    ("home", "alice/config"),
)

#: Nearby *non-equivalent* logical components the V13 remediation must preserve:
#: stripping their trailing periods still leaves a value that is not one of the
#: already-sensitive families, so the narrow rule cannot refuse them.
TRAILING_PERIOD_PRESERVED_SEGMENTS = (
    ("release", "v1"),
    ("version", "node"),
    (".sshx", "config"),
    ("Usersx", "alice/config"),
)

#: The exact analysis-form expectation for representative spellings: the stripped
#: form is what classification consumes, while the raw value is never rewritten.
TRAILING_PERIOD_ANALYSIS_FORM = (
    ("provider/.ssh./config", "provider/.ssh/config"),
    ("provider/.ssh../config", "provider/.ssh/config"),
    ("provider/Users./alice/config", "provider/Users/alice/config"),
    ("cmm/Users../alice/config", "cmm/Users/alice/config"),
    ("provider/release./v1", "provider/release/v1"),
    ("cmm/version./node", "cmm/version/node"),
)

#: The positive controls the V13 prompt requires to keep their verdict: the
#: trailing-period spelling strip must not turn a nearby non-equivalent logical
#: identifier into a refusal, and the retained public references must stay valid.
REQUIRED_POSITIVE_CONTROLS = (
    "provider/model",
    "cmm/orchestration/step",
    "provider/release./v1",
    "cmm/version./node",
    "provider/.sshx./config",
    "provider/Usersx./alice/config",
    "workflow:123",
    "domain:legal",
    "events:read",
    "foo.txt:stream",
    "provider/foo.txt:stream",
    "https://example.com/model",
    "provider/https://example.com/model",
    "jdbc:postgresql://example.com/db",
)

#: Retained V1–V12 accepted controls.  The V13 rule must not disturb any of them.
RETAINED_V1_V12_ACCEPTED_CONTROLS = (
    "urn:cmm:event:message.received",
    "workflow:file:123",
    "domain:file:legal",
    "req:file:mod",
    "cmm:file:reference",
    "model:id_rsa",
    "workflow:id_rsa",
    "model:known_hosts",
    "workflow:id_ed25519",
    "prefix_id_rsa",
    "my-known_hosts",
    "provider/a:1/model",
    "provider/x:0/step",
    "cmm/v2:3/detail",
    "cmm/orchestration:step",
    "provider/a:1/model/detail",
    "report.json:ads",
    "cmm/artifact.bin:stream",
    "provider//model",
    "provider/./model",
    "cmm.orchestration",
    "CORR-ORIGINAL",
    "user-42",
)

#: Every accepted control the V13 module asserts in both directions.
ALL_ACCEPTED_CONTROLS = REQUIRED_POSITIVE_CONTROLS + RETAINED_V1_V12_ACCEPTED_CONTROLS

#: Backslash spellings of a trailing-period reference that the outer identifier
#: grammar refuses anyway, because ``\`` is not in the accepted identifier
#: character set.  Recorded as positive fail-closed facts: the grammar does not
#: have to be widened for the Windows-backslash spelling, and the V13 rule does
#: not rely on it.
BACKSLASH_TRAILING_PERIOD_REFERENCES = (
    "provider\\.ssh.\\config",
    ".ssh.\\config",
    "Users.\\alice\\config",
)

#: Retained non-public filesystem families from Re-audits V6–V12.  The V13 rule
#: must not disturb any of them: traversal, absolute paths, the ``~`` home
#: shorthand, relative system roots, drive-root paths, wrapped drive-root paths,
#: drive-relative paths, ``file:`` URIs and wrapped ``file:`` URIs, named private
#: locations, and the V12 case-varied / named-stream private filenames.
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
    "ID_RSA",
    "KNOWN_HOSTS",
    "Id_Ed25519.pub",
    "id_rsa:stream",
    "known_hosts:ads",
    "provider/ID_RSA",
    "provider/id_rsa:stream",
    "cmm/known_hosts:ads",
)

#: Retained URI-userinfo credential families from Re-audits V7/V8.
RETAINED_USERINFO_CREDENTIAL_REFERENCES = (
    "https://alice:***@example.com/db",
    "jdbc:postgresql://alice:***@example.com/db",
    "provider/https://alice:***@example.com/db",
)

#: Retained civil-hour invariant corpus from Re-audit V9.
RETAINED_END_OF_DAY_TIMESTAMPS = (
    "2026-09-27T24:00:00Z",
    "2026-09-27T24:00:00+00:00",
    "2026-09-27 24:00:00Z",
)

RETAINED_VALID_TIMESTAMPS = (
    "2026-09-27T00:00:00Z",
    "2026-09-27T23:59:59Z",
)

#: Every module name that must not exist: the V13 rule is a refinement of the
#: existing analysis form, never a parallel Win32 normalization subsystem.
FORBIDDEN_PARALLEL_MODULES = (
    "event_path_policy.py",
    "event_ads_policy.py",
    "event_named_stream_policy.py",
    "event_windows_filename_policy.py",
    "event_win32_period_policy.py",
    "event_trailing_period_policy.py",
    "win32_normalization.py",
    "path_canonicalization.py",
    "identifier_policy.py",
)

#: Every shared persisted identifier channel, as a ``(label, builder)`` pair whose
#: builder places one audited reference into that channel and returns
#: ``(payload, header_facts)``.  Enumerating them keeps the coverage reviewable
#: and makes "do not patch ``request_id`` only" an executable claim.
SHARED_CHANNELS = (
    ("payload_request_id", lambda r: ({"request_id": r}, {})),
    (
        "payload_workflow_id",
        lambda r: ({"request_id": "req-v13-channel", "workflow_id": r}, {}),
    ),
    (
        "payload_aggregate_id",
        lambda r: ({"request_id": "req-v13-channel", "aggregate_id": r}, {}),
    ),
    (
        "payload_producer",
        lambda r: ({"request_id": "req-v13-channel", "producer": r}, {}),
    ),
    (
        "header_producer",
        lambda r: ({"request_id": "req-v13-channel"}, {"producer": r}),
    ),
    (
        "header_aggregate_id",
        lambda r: ({"request_id": "req-v13-channel"}, {"aggregate_id": r}),
    ),
    (
        "header_correlation_id",
        lambda r: ({"request_id": "req-v13-channel"}, {"correlation_id": r}),
    ),
    ("header_source", lambda r: ({"request_id": "req-v13-channel"}, {"source": r})),
    (
        "permissions",
        lambda r: ({"request_id": "req-v13-channel"}, {"permissions": [r]}),
    ),
    (
        "metadata_error_type",
        lambda r: ({"request_id": "req-v13-channel"}, {"metadata": {"error_type": r}}),
    ),
    (
        "nested_result_reference",
        lambda r: (
            {"request_id": "req-v13-channel", "result_reference": {"reference_id": r}},
            {},
        ),
    ),
    (
        "structured_reference_sequence",
        lambda r: (
            {"request_id": "req-v13-channel", "approval_refs": [{"reference_id": r}]},
            {},
        ),
    ),
    (
        "domain_reference_sequence",
        lambda r: (
            {"request_id": "req-v13-channel", "supporting_domains": [r]},
            {},
        ),
    ),
)

_SHARED_CHANNEL_IDS = [case[0] for case in SHARED_CHANNELS]

#: The canonical trailing-period reference and its user-home sibling Re-audit V13
#: proved were persisted through all 13 channels.  They are repeated per channel
#: below.
REPORTED_CANONICAL_TRAILING_PERIOD = "provider/.ssh./config"
REPORTED_CANONICAL_HOME_PERIOD = "provider/Users./alice/config"


def _REFERENCE_IDS(reference: str) -> str:
    """Return a pytest parameter id for one adversarial reference spelling."""

    return reference.replace("/", "_").replace("\\", "b").replace(":", "-")


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
    event_id: str = "evt-v13-manual",
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


# ── the classifier itself ──────────────────────────────────────────────────


@pytest.mark.parametrize("reference", REPORTED_TRAILING_PERIOD_REFERENCES)
def test_the_classifier_refuses_a_reported_trailing_period_reference(
    reference: str,
) -> None:
    """MAJOR-V13-001: the Windows-equivalent spelling is classified as private.

    ``WINDOWS_TRAILING_PERIOD_PATH_COMPONENT_EQUIVALENTS_HAVE_IDENTICAL_SAFETY_CLASSIFICATION``
    """

    from cmm.events.event_payload_safety import is_private_filesystem_reference

    assert is_private_filesystem_reference(reference) is True, reference


@pytest.mark.parametrize("reference", FRESH_TRAILING_PERIOD_REFERENCES)
def test_the_classifier_refuses_a_fresh_trailing_period_reference(
    reference: str,
) -> None:
    """MAJOR-V13-001: fresh families, casings and depths are refused too."""

    from cmm.events.event_payload_safety import is_private_filesystem_reference

    assert is_private_filesystem_reference(reference) is True, reference


@pytest.mark.parametrize("reference", REPORTED_REPEATED_TRAILING_PERIOD_REFERENCES)
def test_repeated_trailing_period_variants_keep_the_unsafe_verdict(
    reference: str,
) -> None:
    """MAJOR-V13-001: ``.ssh..`` / ``.ssh...`` are still ``.ssh`` for safety.

    Win32 removes every trailing period from a component, so a repeated-period
    variant cannot become public merely by repeating the period.
    """

    from cmm.events import event_payload_safety as authority

    assert authority.is_private_filesystem_reference(reference) is True, reference
    analysis = authority._analyze_lexical_path(reference)
    assert not any(segment.endswith(".") for segment in analysis.segments), (
        reference,
        analysis.segments,
    )


@pytest.mark.parametrize(
    "family",
    TRAILING_PERIOD_EQUIVALENCE_FAMILIES,
    ids=lambda family: family[0].replace("/", "_").replace(":", "-"),
)
def test_trailing_period_equivalence_families_share_one_verdict(
    family: tuple[str, ...],
) -> None:
    """MAJOR-V13-001: equivalent spellings of one private location never disagree.

    The canonical spelling is asserted to be refused first, so the family's one
    verdict is the already-established private verdict rather than a vacuous one.
    """

    from cmm.events import event_payload_safety as authority

    assert authority.is_private_filesystem_reference(family[0]) is True, family[0]
    verdicts = {
        authority.is_private_filesystem_reference(spelling) for spelling in family
    }
    assert verdicts == {True}, family


def test_every_sensitive_family_with_trailing_periods_is_refused_structurally() -> None:
    """MAJOR-V13-001: the rule is structural for the whole declared family set.

    Roots, families and period counts are enumerated instead of trusting a fixed
    corpus, and the nearby non-equivalent components keep their public verdict
    under the same enumeration.
    """

    from cmm.events import event_payload_safety as authority

    for segment, tail in TRAILING_PERIOD_FAMILY_SEGMENTS:
        for periods in (".", "..", "..."):
            for root in ("provider", "cmm"):
                reference = f"{root}/{segment}{periods}/{tail}"
                assert authority.is_private_filesystem_reference(reference) is True, (
                    reference
                )

    for segment, tail in TRAILING_PERIOD_PRESERVED_SEGMENTS:
        for periods in (".", "..", "..."):
            for root in ("provider", "cmm"):
                reference = f"{root}/{segment}{periods}/{tail}"
                assert authority.is_private_filesystem_reference(reference) is False, (
                    reference
                )


def test_the_identifier_grammar_admits_the_adversarial_spellings() -> None:
    """MAJOR-V13-001: the bypass is a classifier defect, not a grammar defect.

    The V13 reproductions are single safe-character tokens.  The refusal therefore
    has to come from the filesystem classifier; if this assertion ever fails the
    finding has moved and this module no longer proves what it claims.
    """

    from cmm.events import event_payload_safety as authority

    for reference in ALL_TRAILING_PERIOD_REFERENCES:
        assert authority._SAFE_IDENTIFIER_PATTERN.match(reference) is not None, (
            reference
        )
        assert authority.is_private_filesystem_reference(reference) is True, reference


def test_the_trailing_period_rule_lives_in_the_analysis_form() -> None:
    """MAJOR-V13-001: the rule is the existing analysis form, not a new scanner.

    Each adversarial value is refused because the *existing* canonical filesystem
    signatures match it on the stripped analysis form.  This is what makes the
    fix structural rather than a second Win32 path authority.
    """

    from cmm.events import event_payload_safety as authority

    for reference in ALL_TRAILING_PERIOD_REFERENCES:
        analysis = authority._analyze_lexical_path(reference)
        assert not any(segment.endswith(".") for segment in analysis.segments), (
            reference,
            analysis.segments,
        )
        assert any(
            pattern.search(analysis.canonical)
            for pattern in authority._PRIVATE_FILESYSTEM_PATTERNS
        ), (reference, analysis.canonical)


def test_the_trailing_period_rule_is_not_a_reproduced_literal_denylist() -> None:
    """MAJOR-V13-001: the rule is structural, so an unnamed spelling is refused too.

    The audit named ``.ssh.``, ``Users.``, ``.aws.``, ``.kube.`` and equivalents.
    The existing sensitive-family signatures are located by their declared family,
    no audited trailing-period literal appears in the pattern tuple, and fresh
    families, casings and depths no pattern mentions are refused by the same rule.
    """

    from cmm.events import event_payload_safety as authority

    joined = " ".join(
        pattern.pattern for pattern in authority._PRIVATE_FILESYSTEM_PATTERNS
    )
    for audited_literal in (
        ".ssh.",
        ".ssh..",
        "Users.",
        "Users..",
        ".aws.",
        ".kube.",
        ".gnupg.",
        ".docker.",
        ".azure.",
        "home.",
        "users.",
    ):
        assert audited_literal not in joined, audited_literal

    for reference in (
        "cmm/.netrc./machine",
        "provider/.pgpass../config",
        "cmm/.git-credentials./config",
        "provider/.azure.../profile",
        "cmm/users./alice/config",
        "provider/home../alice/config",
    ):
        assert authority.is_private_filesystem_reference(reference) is True, reference


def test_the_trailing_period_classifier_performs_no_filesystem_io() -> None:
    """MAJOR-V13-001: classification stays lexical — no I/O and no resolution."""

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
        for reference in ALL_TRAILING_PERIOD_REFERENCES:
            assert authority.is_private_filesystem_reference(reference) is True
        for reference in ALL_ACCEPTED_CONTROLS:
            assert authority.is_private_filesystem_reference(reference) is False
    finally:
        for holder, name, original in saved:
            setattr(holder, name, original)


def test_the_trailing_period_rule_reuses_the_existing_safety_authority() -> None:
    """MAJOR-V13-001: no second Win32 normalizer, parser, scanner or policy."""

    import cmm.events.event_payload_safety as authority

    module_files = {path.name for path in Path(authority.__file__).parent.glob("*.py")}
    for forbidden in FORBIDDEN_PARALLEL_MODULES:
        assert forbidden not in module_files, forbidden


def test_raw_traversal_semantics_are_detected_before_any_normalization() -> None:
    """MAJOR-V13-001: normalization can never hide a ``..`` traversal segment.

    Traversal is detected on the raw segment sequence, before any normalization,
    and a ``..`` segment is never folded into a harmless value.  A named component
    with trailing periods is not a traversal segment, and a period tail can never
    conceal a sensitive component behind it.
    """

    from cmm.events import event_payload_safety as authority

    for reference in (
        "safe/../x",
        "provider/../config",
        "a/../../b",
        "provider/.ssh../..",
    ):
        assert authority._analyze_lexical_path(reference).has_traversal is True, (
            reference
        )

    assert authority._analyze_lexical_path("a/../b").canonical == "a/../b"

    analysis = authority._analyze_lexical_path("provider/.ssh../config")
    assert analysis.has_traversal is False
    assert analysis.canonical == "provider/.ssh/config"

    # Hidden private content remains reachable for the retained signatures no
    # matter how many period tails precede it.
    assert authority.is_private_filesystem_reference("provider/.../.ssh/config") is True
    assert (
        authority.is_private_filesystem_reference("provider/...../etc/shadow") is True
    )
    assert (
        authority.is_private_filesystem_reference("provider/.../../etc/shadow") is True
    )


def test_the_trailing_period_strip_is_analysis_only_and_never_rewrites() -> None:
    """MAJOR-V13-001: classification consumes the stripped form; persistence does not.

    The analysis form folds the trailing period for classification, while the
    shared identifier authority returns the *raw* value unchanged — an accepted
    identifier is never normalized, lowercased or rewritten.
    """

    from cmm.events import event_payload_safety as authority

    for reference, canonical in TRAILING_PERIOD_ANALYSIS_FORM:
        assert authority._analyze_lexical_path(reference).canonical == canonical, (
            reference
        )

    assert authority._analyze_lexical_path("provider/.ssh./config").segments == (
        "provider",
        ".ssh",
        "config",
    )
    assert (
        authority.validate_platform_identifier("provider/release./v1", field="probe")
        == "provider/release./v1"
    )
    assert (
        authority.validate_platform_identifier("cmm/version./node", field="probe")
        == "cmm/version./node"
    )
    assert (
        authority.validate_platform_identifier("provider/.sshx./config", field="probe")
        == "provider/.sshx./config"
    )


@pytest.mark.parametrize("reference", ALL_ACCEPTED_CONTROLS)
def test_supported_public_controls_are_still_accepted(reference: str) -> None:
    """MAJOR-V13-001 positive control: the fix does not over-correct.

    The nearby non-equivalent trailing-period controls (``provider/release./v1``,
    ``cmm/version./node``, ``provider/.sshx./config``,
    ``provider/Usersx./alice/config``), multi-letter colon identifiers, wrapped
    segment-colon logical identifiers, generic ``filename:stream`` controls,
    sensitive-looking suffixes, plain slash references and credential-free URIs
    all keep their verdict.
    """

    from cmm.events.event_payload_safety import (
        is_private_filesystem_reference,
        validate_platform_identifier,
    )

    assert validate_platform_identifier(reference, field="probe") == reference
    assert is_private_filesystem_reference(reference) is False, reference


@pytest.mark.parametrize("reference", BACKSLASH_TRAILING_PERIOD_REFERENCES)
def test_backslash_trailing_period_references_are_refused_by_the_grammar(
    reference: str,
) -> None:
    """MAJOR-V13-001: ``\\`` is outside the grammar, so it is refused earlier.

    This is a positive fail-closed fact: the V13 fix does not need to widen the
    identifier grammar for the Windows-backslash spelling, and it does not rely on
    doing so.
    """

    from cmm.events import event_payload_safety as authority

    assert authority._SAFE_IDENTIFIER_PATTERN.match(reference) is None, reference
    with pytest.raises(REJECTIONS):
        authority.validate_platform_identifier(reference, field="probe")


# ── the shared identifier authority ────────────────────────────────────────


@pytest.mark.parametrize("reference", ALL_TRAILING_PERIOD_REFERENCES)
def test_the_identifier_authority_refuses_every_trailing_period_reference(
    reference: str,
) -> None:
    """MAJOR-V13-001: the shared validator refuses every trailing-period spelling."""

    from cmm.events.event_payload_safety import validate_platform_identifier

    with pytest.raises(REJECTIONS):
        validate_platform_identifier(reference, field="probe")


def test_the_trailing_period_refusal_message_is_static() -> None:
    """MAJOR-V13-001: the refusal never echoes the audited private location."""

    from cmm.events.event_payload_safety import validate_platform_identifier

    for reference in (
        REPORTED_CANONICAL_TRAILING_PERIOD,
        REPORTED_CANONICAL_HOME_PERIOD,
        "cmm/.ssh./config",
        "provider/.kube./config",
    ):
        with pytest.raises(PlatformEventPayloadError) as excinfo:
            validate_platform_identifier(reference, field="probe")

        message = str(excinfo.value)
        assert reference not in message
        assert ".ssh" not in message.lower()
        assert "private filesystem location" in message


# ── the canonical EventSystem ──────────────────────────────────────────────


@pytest.mark.parametrize("reference", REPORTED_TRAILING_PERIOD_REFERENCES)
def test_the_event_system_refuses_a_trailing_period_reference(
    reference: str,
) -> None:
    """MAJOR-V13-001: canonical publication refuses before persistence.

    ``NON_PUBLIC_FILESYSTEM_PATHS_NEVER_ENTER_EVENT_PERSISTENCE``
    """

    system, received = _watching_system()

    with pytest.raises(REJECTIONS):
        system.publish(
            "message.received",
            {"request_id": reference},
            event_id=f"evt-v13-sys-{next(_CONTROL_IDS)}",
        )

    _assert_nothing_reached_persistence(system, received)


@pytest.mark.parametrize("reference", ALL_TRAILING_PERIOD_REFERENCES)
def test_the_file_backed_repository_persists_nothing_for_a_trailing_period_reference(
    tmp_path: Path, reference: str
) -> None:
    """MAJOR-V13-001: the durable store is byte-identical after refusal."""

    store = _durable_store(tmp_path)
    system = _file_backed_system(store)
    before = _durable_bytes(store)

    with pytest.raises(REJECTIONS):
        system.publish(
            "message.received",
            {"request_id": reference},
            event_id=f"evt-v13-durable-{next(_CONTROL_IDS)}",
        )

    assert system.repository.count() == 0
    assert system.dead_letter_count() == 0
    assert _durable_bytes(store) == before
    assert not store.exists() or store.read_bytes() == b""


@pytest.mark.parametrize("reference", ALL_TRAILING_PERIOD_REFERENCES)
def test_a_reopened_file_backed_repository_reveals_no_rejected_value(
    tmp_path: Path, reference: str
) -> None:
    """MAJOR-V13-001: reopening the durable store must not reveal the value.

    Independent Re-audit V13 reopened the file-backed store and found the exact
    unsafe spelling persisted.  Reopening after the refusal must yield no event and
    no trace of the unsafe value.
    """

    store = _durable_store(tmp_path)
    system = _file_backed_system(store)
    event_id = f"evt-v13-reopen-{next(_CONTROL_IDS)}"
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
        assert reference.encode() not in store.read_bytes()


@pytest.mark.parametrize("reference", ALL_TRAILING_PERIOD_REFERENCES)
def test_a_manual_publish_event_cannot_bypass_the_trailing_period_rule(
    reference: str,
) -> None:
    """MAJOR-V13-001: the manual canonical boundary re-applies the same rule."""

    system, received = _watching_system()
    event = manual_event(
        "message.received",
        {"request_id": reference},
        event_id=f"evt-v13-manual-{next(_CONTROL_IDS)}",
    )

    with pytest.raises(REJECTIONS):
        system.publish_event(event)

    _assert_nothing_reached_persistence(system, received)


@pytest.mark.parametrize(
    "reference",
    (
        "provider/release./v1",
        "cmm/version./node",
        "provider/.sshx./config",
        "provider/Usersx./alice/config",
    ),
)
def test_accepted_trailing_period_controls_still_publish_with_raw_spelling(
    reference: str,
) -> None:
    """MAJOR-V13-001 positive control: near-miss identifiers are not rewritten.

    The accepted event keeps the exact producer spelling — including its trailing
    period — and the stored identity, correlation and causation semantics are
    unchanged by the classification-only fix.
    """

    system, received = _watching_system()
    event_id = f"evt-v13-ok-{next(_CONTROL_IDS)}"

    result = system.publish(
        "message.received",
        {"request_id": "req-v13-ok", "workflow_id": reference},
        event_id=event_id,
        aggregate_id=reference,
        correlation_id="CORR-V13-ORIGINAL",
        causation_id="CAUSE-V13-ORIGINAL",
    )

    assert result.persisted is True
    assert system.repository.count() == 1
    assert len(received) == 1
    assert system.dead_letter_count() == 0
    stored = system.repository.get(event_id)
    assert stored is not None
    assert stored.header.workflow_id == reference
    assert stored.header.aggregate_id == reference
    assert stored.header.correlation_id == "CORR-V13-ORIGINAL"
    assert stored.header.causation_id == "CAUSE-V13-ORIGINAL"


# ── every shared persisted identifier channel ──────────────────────────────


@pytest.mark.parametrize(
    ("label", "build"),
    SHARED_CHANNELS,
    ids=_SHARED_CHANNEL_IDS,
)
@pytest.mark.parametrize(
    "reference",
    (REPORTED_CANONICAL_TRAILING_PERIOD, REPORTED_CANONICAL_HOME_PERIOD),
    ids=("canonical_ssh_period", "canonical_users_period"),
)
def test_every_shared_channel_refuses_a_trailing_period_reference(
    label: str, build: Any, reference: str
) -> None:
    """MAJOR-V13-001: all 13 shared channels refuse, not just ``request_id``."""

    payload, header_facts = build(reference)
    system, received = _watching_system()

    with pytest.raises(REJECTIONS):
        system.publish(
            "message.received",
            payload,
            event_id=f"evt-v13-ch-{label}-{next(_CONTROL_IDS)}",
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
    """MAJOR-V13-001: refusal through the file-backed repository adds no bytes."""

    store = _durable_store(tmp_path)
    system = _file_backed_system(store)
    before = _durable_bytes(store)
    payload, header_facts = build(REPORTED_CANONICAL_TRAILING_PERIOD)

    with pytest.raises(REJECTIONS):
        system.publish(
            "message.received",
            payload,
            event_id=f"evt-v13-ch-durable-{label}-{next(_CONTROL_IDS)}",
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
def test_every_shared_channel_still_accepts_a_public_reference(
    label: str, build: Any
) -> None:
    """MAJOR-V13-001 positive control: public references persist on every channel."""

    payload, header_facts = build("provider/release./v1")
    system, received = _watching_system()

    result = system.publish(
        "message.received",
        payload,
        event_id=f"evt-v13-ok-{label}-{next(_CONTROL_IDS)}",
        **header_facts,
    )

    assert result.persisted is True
    assert system.repository.count() == 1
    assert len(received) == 1
    assert system.dead_letter_count() == 0


# ── retained V1–V12 protections ────────────────────────────────────────────


@pytest.mark.parametrize("reference", RETAINED_UNSAFE_REFERENCES)
def test_every_retained_filesystem_protection_still_refuses(reference: str) -> None:
    """MAJOR-V13-001: V6–V12 path protections are preserved, not replaced."""

    from cmm.events.event_payload_safety import validate_platform_identifier

    with pytest.raises(REJECTIONS):
        validate_platform_identifier(reference, field="probe")


@pytest.mark.parametrize("reference", RETAINED_USERINFO_CREDENTIAL_REFERENCES)
def test_every_retained_userinfo_credential_protection_still_refuses(
    reference: str,
) -> None:
    """MAJOR-V13-001: V7/V8 URI-userinfo protections are preserved.

    ``URI_USERINFO_CREDENTIALS_REJECTED_REGARDLESS_OF_PREFIX_OR_WRAPPER``
    """

    from cmm.events.event_payload_safety import validate_platform_identifier

    with pytest.raises(REJECTIONS):
        validate_platform_identifier(reference, field="probe")


@pytest.mark.parametrize("timestamp", RETAINED_END_OF_DAY_TIMESTAMPS)
def test_the_retained_civil_hour_bound_still_refuses(timestamp: str) -> None:
    """MAJOR-V13-001: the V9 timestamp invariant is untouched.

    ``PHASE11_22_TIMESTAMP_ACCEPTANCE_IS_INTERPRETER_VERSION_INDEPENDENT``
    """

    from cmm.events.event_payload_safety import _validate_canonical_timestamp

    with pytest.raises(REJECTIONS):
        _validate_canonical_timestamp(timestamp, field="occurred_at")


@pytest.mark.parametrize("timestamp", RETAINED_VALID_TIMESTAMPS)
def test_the_retained_valid_timestamps_still_validate(timestamp: str) -> None:
    """MAJOR-V13-001: the V9 timestamp acceptance is untouched."""

    from cmm.events.event_payload_safety import _validate_canonical_timestamp

    assert _validate_canonical_timestamp(timestamp, field="occurred_at") == timestamp


# ── the analysis form and the signature itself ─────────────────────────────


def test_the_trailing_period_rule_is_applied_on_the_analysis_form() -> None:
    """MAJOR-V13-001: rows and wrappers classify on the canonical analysis form.

    The existing signatures are consulted against the same lexical analysis form
    as the retained V6–V12 rules, so ``provider/.ssh./config`` and
    ``cmm/Users./alice/config`` receive the verdict their canonical spelling
    already had at the top level.
    """

    from cmm.events import event_payload_safety as authority

    for reference in (
        "provider/.ssh./config",
        "provider/.ssh../config",
        "provider/Users./alice/config",
        "cmm/Users./alice/config",
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


def test_the_trailing_period_patterns_are_still_compiled_patterns() -> None:
    """MAJOR-V13-001: no grammar widening and no second classification mechanism."""

    from cmm.events import event_payload_safety as authority

    assert authority._PRIVATE_FILESYSTEM_PATTERNS
    for pattern in authority._PRIVATE_FILESYSTEM_PATTERNS:
        assert isinstance(pattern, re.Pattern), pattern

    # The identifier grammar itself is unchanged: the V13 reproductions are still
    # admitted by it, which is why the classifier has to refuse them.
    assert (
        authority._SAFE_IDENTIFIER_PATTERN.pattern
        == r"^[A-Za-z0-9][A-Za-z0-9._:@+\-/]*$"
    )
