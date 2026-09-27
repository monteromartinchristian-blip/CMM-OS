"""Phase 11.22 — platform event payload safety.

Platform events are lifecycle facts, not content mirrors.  Every value that
reaches the canonical transport and the durable repository passes through this
one gate first, so an unsafe payload fails **before** persistence rather than
being stored and redacted later.

Policy reuse
------------

This module deliberately does not invent a third incompatible event-safety
policy.  It composes the vocabulary already owned by closed phases:

* the Phase 11.2 orchestration boundary's forbidden-key rule, which fails closed
  on keys naming prompts, reasoning, provider payloads, credentials, cookies and
  tracebacks — the same normalisation, squash and segment tests, so the two
  boundaries agree on what a forbidden key is;
* Phase 10.33's high-confidence credential detector and its forbidden
  private-marker vocabulary, applied to every key and every string value.

What this gate adds is the Phase 11.22 allowlist discipline: a platform event
payload is *structurally restricted* to the bounded metadata vocabulary the
design permits, so an unrecognised key fails closed instead of being trusted.
"""

from __future__ import annotations

import math
import re
from collections.abc import Mapping, Sequence
from datetime import datetime
from types import MappingProxyType
from typing import Any
from urllib.parse import unquote

from cmm.domains.credential_policy import contains_high_confidence_credential
from cmm.domains.event_contracts import _contains_private_marker

__all__ = [
    "ALLOWED_PAYLOAD_KEYS",
    "CANONICAL_HEADER_FACT_KEYS",
    "CANONICAL_HEADER_PAYLOAD_KEYS",
    "FORBIDDEN_PAYLOAD_KEYS",
    "FORBIDDEN_PAYLOAD_KEY_TOKENS",
    "MAX_PLATFORM_IDENTIFIER_LENGTH",
    "MAX_PLATFORM_NUMERIC_FACT",
    "NUMERIC_FACT_SEMANTICS",
    "PLATFORM_CONTAINER_HEADER_FIELDS",
    "PLATFORM_IDENTIFIER_HEADER_FIELDS",
    "PlatformEventPayloadError",
    "canonical_header_fact_values",
    "canonicalize_platform_event_sensitivity",
    "canonicalize_platform_payload",
    "category_for_delivery_error",
    "contains_uri_userinfo_credential",
    "freeze_platform_payload",
    "is_forbidden_platform_payload_key",
    "is_forbidden_source_content_key",
    "is_private_filesystem_reference",
    "reconcile_canonical_header_fact",
    "scan_for_forbidden_event_facts",
    "scan_for_forbidden_platform_content",
    "split_canonical_header_facts",
    "strictest_platform_sensitivity",
    "thaw_platform_payload",
    "validate_platform_event_facts",
    "validate_platform_identifier",
    "validate_platform_payload",
    "validate_platform_permissions",
]

#: The bounded platform payload vocabulary: references, categorical states and
#: bounded metadata only.  These are exactly the kind of facts the design allows
#: — never prompts, reasoning, provider payloads, credentials or raw content.
ALLOWED_PAYLOAD_KEYS: frozenset[str] = frozenset(
    {
        # ── identity references ──────────────────────────────────────────────
        "request_id",
        "session_id",
        "workflow_id",
        "run_id",
        "goal_id",
        "operation_id",
        "approval_id",
        "approval_refs",
        "domain_id",
        "agent_id",
        "task_id",
        "validation_id",
        "event_id",
        "execution_id",
        "correlation_id",
        "causation_id",
        "aggregate_id",
        "producer",
        "parent_run_id",
        "root_run_id",
        "node_id",
        "plan_node_id",
        "decision_id",
        "reference_id",
        # ── categorical state ───────────────────────────────────────────────
        "status",
        "state",
        "intent",
        "route",
        "channel",
        "policy",
        "policy_disposition",
        "error_category",
        "error_code",
        "reason_code",
        "reason_codes",
        "sensitivity",
        "schema_version",
        "event_type",
        "primary_domain",
        "supporting_domains",
        "related_domain_ids",
        "capability_id",
        "result_reference",
        # ── bounded facts ───────────────────────────────────────────────────
        "duration_ms",
        "count",
        "attempts",
        "version",
        "sequence",
        "needs_clarification",
        "approved",
        "is_success",
        "occurred_at",
        "emitted_at",
    }
)

#: Payload keys that name content which must never enter an event.  Mirrors the
#: frozen Phase 11.2 orchestration rule so both boundaries agree.
FORBIDDEN_PAYLOAD_KEYS = frozenset(
    {
        "chain_of_thought",
        "hidden_reasoning",
        "raw_reasoning",
        "reasoning",
        "prompt",
        "prompts",
        "system_prompt",
        "developer_prompt",
        "provider_payload",
        "provider_request",
        "provider_response",
        "raw_context",
        "raw_payload",
        "raw_request",
        "request_text",
        "user_text",
        "secret",
        "secrets",
        "credential",
        "credentials",
        "password",
        "passwd",
        "token",
        "api_key",
        "apikey",
        "authorization",
        "auth_header",
        "cookie",
        "cookies",
        "traceback",
        "stack_trace",
    }
)

#: Payload key segments whose presence fails closed.
FORBIDDEN_PAYLOAD_KEY_TOKENS = frozenset(
    {
        "secret",
        "secrets",
        "credential",
        "credentials",
        "password",
        "passwd",
        "token",
        "auth",
        "authorization",
        "cookie",
        "prompt",
        "prompts",
        "reasoning",
        "chainofthought",
        "thought",
        "payload",
        "traceback",
    }
)

_FORBIDDEN_PAYLOAD_KEYS_SQUASHED = frozenset(
    key.replace("_", "") for key in FORBIDDEN_PAYLOAD_KEYS
)

#: Category label used for every platform safety rejection.
ERROR_CATEGORY = "PLATFORM_EVENT_PAYLOAD_UNSAFE"

#: The persisted canonical header facts that are producer-controlled free-form
#: identifier strings.  Each one is validated by
#: :func:`validate_platform_identifier` before persistence, because a caller could
#: otherwise move forbidden content out of ``payload.data`` and into a header
#: channel that reaches the same durable canonical event.
PLATFORM_IDENTIFIER_HEADER_FIELDS: tuple[str, ...] = (
    "event_id",
    "source",
    "producer",
    "aggregate_id",
    "agent_id",
    "agent_run_id",
    "goal_id",
    "workflow_id",
    "task_id",
    "iteration_id",
    "correlation_id",
    "causation_id",
    "actor_id",
)

#: The persisted canonical header facts that are free-form containers rather than
#: identifiers.  They are scanned recursively for forbidden keys, credentials and
#: private markers by :func:`scan_for_forbidden_event_facts`.
PLATFORM_CONTAINER_HEADER_FIELDS: tuple[str, ...] = ("metadata", "permissions")

#: Every persisted canonical header fact name.
#:
#: The header is the *one* authority for these facts.  A payload key with the same
#: name is not a second, independently validated copy of the same lifecycle fact;
#: it is the same fact, and it may only ever be consumed into the header.
CANONICAL_HEADER_FACT_KEYS: frozenset[str] = frozenset(
    {
        "event_id",
        "event_type",
        "schema_version",
        "occurred_at",
        "emitted_at",
        "agent_id",
        "agent_run_id",
        "goal_id",
        "workflow_id",
        "task_id",
        "iteration_id",
        "correlation_id",
        "causation_id",
        "actor_id",
        "source",
        "sensitivity",
        "permissions",
        "metadata",
        "producer",
        "aggregate_id",
    }
)

#: The payload keys that name a canonical header fact and are therefore consumed
#: into the header instead of being persisted a second time.
#:
#: Independent Re-audit V6 persisted both copies of every one of these facts at
#: once: ``payload.event_id = payload-event`` alongside ``header.event_id =
#: header-event``, and crucially ``payload.sensitivity = restricted`` alongside
#: ``header.sensitivity = internal`` — a stricter classification hidden where the
#: canonical header authority would never see it.  The audited key list is exactly
#: this intersection, and it is deliberately the *intersection* with the bounded
#: payload vocabulary: a payload key outside that vocabulary stays rejected rather
#: than becoming a new header channel.
CANONICAL_HEADER_PAYLOAD_KEYS: frozenset[str] = frozenset(
    {
        "event_id",
        "event_type",
        "schema_version",
        "occurred_at",
        "emitted_at",
        "agent_id",
        "goal_id",
        "workflow_id",
        "task_id",
        "correlation_id",
        "causation_id",
        "aggregate_id",
        "producer",
        "sensitivity",
    }
)

assert CANONICAL_HEADER_PAYLOAD_KEYS == (
    ALLOWED_PAYLOAD_KEYS & CANONICAL_HEADER_FACT_KEYS
), "the consumed canonical payload keys must be exactly the header-named vocabulary"

#: The canonical header facts that are timestamps rather than identifier tokens.
_TIMESTAMP_HEADER_FACT_KEYS: frozenset[str] = frozenset({"occurred_at", "emitted_at"})

#: A persisted identifier is a single bounded token drawn from an explicit safe
#: character set.  Assignments, whitespace, quotes and free prose — the shapes a
#: leaked prompt or credential would arrive in — are refused outright, on top of
#: the credential/private-marker scan.
_SAFE_IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:@+\-/]*$")

#: Strong syntactic signatures of a **non-public local filesystem location**.
#:
#: The identifier character set above deliberately keeps ``:``, ``/`` and ``.``
#: because legitimate platform references need them (``workflow:123``,
#: ``domain:legal``, ``provider/model``).  Safe characters are not path safety.
#: Independent Re-audit V6 showed that the missing piece was exactly this
#: classification: ``file:///Users/alice/.ssh/id_rsa``, ``Users/alice/.ssh/id_rsa``
#: and ``C:/Users/alice/.ssh/id_rsa`` all qualified as identifiers and were durably
#: persisted — including in the canonical header ``producer`` fact — although the
#: frozen design prohibits "filesystem secrets/paths where not public-safe".
#:
#: Independent Re-audit V7 then showed that absolute-path classification alone is
#: incomplete: a *relative* traversal prefixed with an apparently safe identifier
#: segment (``safe/../../etc/shadow``, ``foo/../bar/../../private/var``) matched no
#: pattern and was durably persisted through every shared identifier channel.  The
#: ``..`` traversal segment and the relative spellings of a private system root are
#: therefore part of this same classifier, not of a second path policy.
#:
#: This is purely *syntactic* safety classification.  It performs no I/O, resolves
#: no path and inspects no file; it only refuses the shapes that can denote a local
#: user/system location or a known secret-bearing path segment.  A legitimate
#: reference such as ``workflow:123``, ``domain:legal`` or ``provider/model``
#: matches none of them.
_PRIVATE_FILESYSTEM_PATTERNS: tuple[re.Pattern[str], ...] = (
    # A file: URI — the explicit spelling of one local filesystem location.
    re.compile(r"^file:", re.IGNORECASE),
    # A Windows drive-root path (``C:/…``, ``C:\…``).
    re.compile(r"^[A-Za-z]:[\\/]"),
    # A Windows UNC share (``\\server\share``).
    re.compile(r"^\\\\"),
    # An absolute POSIX path or the ``~`` home shorthand.
    re.compile(r"^[/~]"),
    # A syntactic ``..`` traversal segment, delimited by a path separator or
    # bounding the whole token.  ``..`` is a filesystem path semantic, never a
    # legitimate platform reference separator: without this rule a producer reaches
    # a sensitive relative location merely by prefixing it with a safe-looking
    # identifier segment.  Both separators are accepted, in any mix, because a
    # Windows spelling is a filesystem path semantic too.  The rule matches the
    # *segment* rather than a naive ``".." in value`` substring, so ``cmm.orchestration``
    # and ``v1..2`` remain ordinary references.
    re.compile(r"(?:^|[\\/])\.\.(?:[\\/]|$)"),
    # A well-known sensitive system file in relative form (``etc/shadow``).  A
    # network URI names the same file, so this also refuses ``nfs://server/etc/shadow``.
    re.compile(
        r"(?:^|[\\/])etc[\\/](?:shadow|passwd|sudoers)(?:$|[\\/])", re.IGNORECASE
    ),
    # The macOS private system roots in relative form (``private/var/db/keychains``).
    re.compile(
        r"(?:^|[\\/])private[\\/](?:var|etc|tmp|root)(?:[\\/]|$)", re.IGNORECASE
    ),
    # A user-home directory, on macOS (``Users``), Linux (``home``) or Windows.
    re.compile(r"(?:^|[\\/])(?:Users|home|Documents and Settings)[\\/]", re.IGNORECASE),
    # A known secret-bearing private directory segment.
    re.compile(
        r"(?:^|[\\/])(?:\.ssh|\.aws|\.gnupg|\.kube|\.docker|\.azure|\.netrc"
        r"|\.pgpass|\.npmrc|\.git-credentials)(?:[\\/]|$)",
        re.IGNORECASE,
    ),
    # A well-known private key material file name.
    re.compile(r"(?:^|[\\/])(?:id_rsa|id_dsa|id_ecdsa|id_ed25519|known_hosts)(?:$|\.)"),
)

#: Upper bound for one persisted identifier fact.
MAX_PLATFORM_IDENTIFIER_LENGTH = 256

#: A categorical lifecycle state is a bounded lowercase token, optionally
#: dot-separated into a small number of segments (``goal.created``,
#: ``domain.execution.completed``).  It is deliberately narrower than an
#: identifier: no colons, slashes or free-form paths, and — critically — no
#: whitespace, so a sentence can never masquerade as a lifecycle state.
_SAFE_CATEGORY_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9]*(?:[._\-][A-Za-z0-9]+)*$")

#: Upper bound for one persisted categorical token.  A 10,000-character "status"
#: is not a bounded lifecycle state, so the key vocabulary being closed is not by
#: itself a bound on the semantic fact.
MAX_PLATFORM_CATEGORY_LENGTH = 128

#: Upper bound for one persisted timestamp string.
MAX_PLATFORM_TIMESTAMP_LENGTH = 64

#: The canonical ISO-8601 timestamp form the durable JSON record stores.  A live
#: ``datetime`` is deliberately refused elsewhere, so this string shape is the one
#: canonical persisted representation.
_SAFE_TIMESTAMP_PATTERN = re.compile(
    r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(?::\d{2}(?:\.\d{1,6})?)?"
    r"(?:Z|[+-]\d{2}:?\d{2})?$"
)

#: Upper bound for a structured reference sequence.  Bounded containers are part of
#: the approved vocabulary; unbounded ones are not.
MAX_PLATFORM_REFERENCE_SEQUENCE_LENGTH = 256

#: The canonical upper bound for one persisted numeric lifecycle fact.
#:
#: Independent Re-audit V6 showed that a semantic class called "bounded number"
#: which accepted *any* finite Python number was not bounded at all: the same public
#: event carrying ``count = 10 ** 5000`` was accepted by the official in-memory
#: repository and raised ``ValueError`` inside the official file-backed repository,
#: because the interpreter's integer-to-string limit — not the Phase 11.22 boundary —
#: was the only thing standing in the way.  ``1e308`` and negative counts, durations,
#: attempts and sequences were accepted too.
#:
#: The bound is the signed 64-bit machine-integer range: nineteen decimal digits, far
#: below every serializer and interpreter conversion limit, and far above every
#: legitimate count, attempt, sequence, millisecond duration or version this platform
#: produces.  It is one explicit constant, not a second numeric-policy registry.
MAX_PLATFORM_NUMERIC_FACT = 9_223_372_036_854_775_807  # 2**63 - 1

#: The one semantic numeric-fact table: which bounded *kind of number* each numeric
#: lifecycle key may carry.
#:
#: A key name alone is not a contract.  ``count``, ``attempt``/``attempts`` and
#: ``sequence`` are non-negative integer counts; ``duration_ms`` is a non-negative
#: bounded duration; ``ratio`` is the normalized ratio current producers publish
#: (``0.0 <= ratio <= 1.0``).  A numeric fact whose key is absent from this table —
#: for example an anonymous list item — is still bounded by
#: :data:`MAX_PLATFORM_NUMERIC_FACT`, but no lifecycle name implies its sign, so the
#: generic class admits the whole bounded signed range.
NUMERIC_FACT_SEMANTICS: Mapping[str, str] = MappingProxyType(
    {
        "count": "count",
        "attempt": "count",
        "attempts": "count",
        "sequence": "count",
        "duration_ms": "duration",
        "ratio": "ratio",
    }
)

#: The one canonical payload-key → value-class specification.
#:
#: The allowlist above answers *which* lifecycle facts a platform event may carry.
#: This mapping answers the second, equally required half of the frozen policy:
#: *what kind of value each approved key may carry*.  Without it an approved key
#: name was the whole contract, so arbitrary prose could be relocated into
#: ``request_id``, ``status``, ``approved`` or ``duration_ms`` and persisted as
#: durable lifecycle evidence.
#:
#: Every allowed key belongs to exactly one explicit class, so no approved key can
#: fall through to unrestricted arbitrary prose.
PAYLOAD_KEY_CLASSES: Mapping[str, frozenset[str]] = MappingProxyType(
    {
        #: IDs/references: a bounded single-token identifier.
        "identifier": frozenset(
            {
                "request_id",
                "session_id",
                "workflow_id",
                "run_id",
                "goal_id",
                "operation_id",
                "approval_id",
                "domain_id",
                "agent_id",
                "task_id",
                "validation_id",
                "event_id",
                "execution_id",
                "correlation_id",
                "causation_id",
                "aggregate_id",
                "producer",
                "parent_run_id",
                "root_run_id",
                "node_id",
                "plan_node_id",
                "decision_id",
                "primary_domain",
                "capability_id",
                "reference_id",
            }
        ),
        #: Categorical states and tokens: a bounded token form, never free prose.
        "category": frozenset(
            {
                "status",
                "state",
                "intent",
                "route",
                "channel",
                "policy",
                "policy_disposition",
                "error_category",
                "error_code",
                "reason_code",
                "sensitivity",
                "event_type",
            }
        ),
        #: Boolean lifecycle facts.
        "boolean": frozenset({"needs_clarification", "approved", "is_success"}),
        #: Bounded counts and durations.
        "number": frozenset({"duration_ms", "count", "attempts", "sequence"}),
        #: Version facts (a bounded number or a bounded version token).
        "version": frozenset({"version", "schema_version"}),
        #: Timestamps: the canonical ISO-8601 string form only.
        "timestamp": frozenset({"occurred_at", "emitted_at"}),
        #: Structured reference containers, validated by their documented shape.
        "structured_reference": frozenset({"result_reference"}),
        #: Bounded sequences of structured reference containers/identifiers.
        "structured_reference_sequence": frozenset({"approval_refs"}),
        #: Bounded sequences of domain/capability references.
        "domain_reference_sequence": frozenset(
            {"supporting_domains", "related_domain_ids", "reason_codes"}
        ),
    }
)

#: The nested keys a structured reference container may carry, and the class of
#: each one.  Nested facts are validated recursively against this documented shape
#: rather than being treated as arbitrary containers, and an unknown nested key
#: fails closed instead of becoming a new mirroring path.
STRUCTURED_REFERENCE_KEYS: Mapping[str, str] = MappingProxyType(
    {
        "reference_id": "identifier",
        "sequence": "number_sequence",
        "approval_id": "identifier",
        "domain_id": "identifier",
        "count": "number",
    }
)

#: The one canonical metadata-key → value-class specification.
#:
#: Persisted metadata is lifecycle metadata, not an unrestricted prose side
#: channel.  Only the metadata keys current Phase 11.22 producers, adapters and
#: closed-phase contracts actually use are admitted, and each one belongs to an
#: explicit bounded value class.  An unknown metadata key fails closed rather than
#: becoming a new content-mirroring path.
METADATA_KEY_CLASSES: Mapping[str, str] = MappingProxyType(
    {
        "status_code": "category",
        "attempt": "number",
        "origin": "category",
        "reason": "category",
        "error_type": "identifier",
        "category": "category",
        "replay": "boolean",
        "flag": "boolean",
        "label": "category",
        "ratio": "number",
        "count": "number",
        "detail": "metadata_container",
    }
)

#: The nested keys a bounded metadata container may carry, and the class of each.
METADATA_CONTAINER_KEYS: Mapping[str, str] = MappingProxyType(
    {
        "inner": "bounded_sequence",
        "count": "number",
        "reference_id": "identifier",
    }
)

#: The bounded scalar classes a metadata list may carry.
_METADATA_SEQUENCE_ITEM_CLASSES: frozenset[str] = frozenset(
    {"category", "identifier", "number", "boolean", "null"}
)


class PlatformEventPayloadError(ValueError):
    """Raised when a would-be platform event payload is not safe to persist."""

    def __init__(self, reason: str, *, key: str | None = None) -> None:
        self.reason = reason
        self.key = key
        self.category = ERROR_CATEGORY
        message = f"platform event payload rejected: {reason}"
        if key is not None:
            message = f"{message} (key '{key}')"
        super().__init__(message)


def _normalize_key(key: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", key.strip().lower()).strip("_")


def is_forbidden_platform_payload_key(key: str) -> bool:
    """Return whether *key* names content that must never enter an event."""

    normalized = _normalize_key(key)
    if not normalized:
        return False
    if normalized in FORBIDDEN_PAYLOAD_KEYS:
        return True
    if normalized.replace("_", "") in _FORBIDDEN_PAYLOAD_KEYS_SQUASHED:
        return True
    segments = normalized.split("_")
    if any(segment in FORBIDDEN_PAYLOAD_KEY_TOKENS for segment in segments):
        return True
    return "".join(segments) in FORBIDDEN_PAYLOAD_KEY_TOKENS


#: Frozen source-contract envelope names that are structural containers rather
#: than content.  A ``kernel.events.Event`` payload and a Phase 10.33 Domain Event
#: serialization both legitimately use ``payload`` as the name of their own nested
#: container, so an adapter that already ignores that fact must not mistake the
#: envelope name for forbidden content.  The container's *contents* are still
#: scanned by :func:`scan_for_forbidden_platform_content`.
STRUCTURAL_SOURCE_ENVELOPE_KEYS: frozenset[str] = frozenset({"payload"})


def is_forbidden_source_content_key(key: str) -> bool:
    """Return whether an ignored *source* fact key names forbidden content.

    This is the canonical forbidden-key vocabulary applied to source facts the
    platform does not model.  It differs from
    :func:`is_forbidden_platform_payload_key` in exactly one documented way: the
    structural source envelope name ``payload`` is not itself forbidden, because
    closed-phase contracts use it as a container.  A prompt, credential or raw
    provider payload *inside* that container still fails closed.
    """

    if _normalize_key(key) in STRUCTURAL_SOURCE_ENVELOPE_KEYS:
        return False
    return is_forbidden_platform_payload_key(key)


def _check_key(key: str) -> None:
    if is_forbidden_platform_payload_key(key):
        raise PlatformEventPayloadError("forbidden payload key", key=key)
    if key not in ALLOWED_PAYLOAD_KEYS:
        raise PlatformEventPayloadError(
            "payload key is outside the bounded platform event vocabulary", key=key
        )


def _is_binary_buffer(value: object) -> bool:
    """Return whether *value* is a binary/buffer object by its semantics.

    The frozen rule is semantic — *arbitrary binary/buffer content never enters
    persisted event content* — not "reject a hand-written list of a few Python
    binary classes".  Enumerating ``bytes``/``bytearray``/``memoryview`` closed the
    V4 ``memoryview`` bypass but left ``array.array`` open, because an
    ``array.array`` is both a compact binary buffer **and** a registered
    ``collections.abc.Sequence`` whose iteration yields its elements.  It was
    therefore canonicalized into a plain integer list and persisted.

    The check is a bounded use of the language's own buffer protocol: a value is
    binary when the interpreter can expose its raw bytes as an unsigned byte view.
    ``bytes``, ``bytearray``, ``memoryview`` and every ``array.array`` typecode
    satisfy that; ``str``, the descriptive containers and every other approved
    scalar do not, because they do not support the buffer protocol at all.  The
    probe never reads, copies, resizes or exposes the buffer — it only asks whether
    a raw byte view exists, so a genuine secret never becomes a rendered value here.
    """

    if isinstance(value, (bytes, bytearray, memoryview)):
        return True
    if isinstance(value, (str, bool, int, float)) or value is None:
        # Fast paths for the approved descriptive scalars; none of them is a buffer,
        # and ``str``/``int`` must never be probed as one.
        return False
    try:
        view = memoryview(value)
    except TypeError:
        return False
    try:
        # A C-contiguous unsigned-byte view is exactly what makes a value raw
        # binary evidence; a non-contiguous or non-byte view would fail closed too.
        view.cast("B")
    except (TypeError, ValueError):
        return True
    finally:
        view.release()
    return True


def _reject_binary_buffer(value: object, key: str) -> None:
    """Fail closed when *value* is binary/buffer content.

    This runs **before** any generic sequence handling in every canonicalization
    path, so binary rejection is unreachable by no standard supported buffer
    container: an ``array.array`` can never be walked as an ordinary integer
    sequence, and its elements can never become a plain list.
    """

    if _is_binary_buffer(value):
        raise PlatformEventPayloadError("binary value must not be persisted", key=key)


def _is_sequence(value: object) -> bool:
    """Return whether *value* is an ordinary descriptive sequence.

    The excluded values are exactly the binary/buffer objects, judged semantically
    by :func:`_is_binary_buffer`.  ``memoryview`` is a registered
    :class:`collections.abc.Sequence` whose iteration yields integers, and
    ``array.array`` is a registered sequence too, so without this exclusion a binary
    buffer would be treated as an ordinary descriptive sequence and recursively
    canonicalized into a plain integer list — letting raw binary bytes enter
    persisted event content.
    """

    if isinstance(value, str):
        return False
    if _is_binary_buffer(value):
        return False
    return isinstance(value, Sequence)


def _reject_non_descriptive_value(value: object, key: str) -> None:
    """Fail closed on a value that is not a bounded descriptive JSON-safe value.

    This is the **structural** half of the one canonical safe-event policy, and it
    is deliberately shared by every persisted container — ``payload.data``,
    ``metadata`` and ``permissions`` — so "safe to persist" means exactly one thing
    everywhere.  A runtime object, a binary value or a non-finite number is refused
    here rather than being stringified later by a serializer.

    ``None``, booleans, integers, finite floats and strings are the approved
    descriptive scalar types.  Mappings and sequences are handled by the caller,
    which recurses into them.

    A ``datetime`` is deliberately **not** an approved scalar: the durable JSON
    record stores a timestamp as an ISO-8601 string, so a live ``datetime`` fact
    would reopen as a ``str`` and the live and persisted shapes of the same fact
    would differ.  Rejecting it here keeps one canonical shape rather than letting
    the type drift silently across a durable restart.
    """

    if value is None or isinstance(value, bool):
        return
    if _is_binary_buffer(value):
        raise PlatformEventPayloadError("binary value must not be persisted", key=key)
    if isinstance(value, int):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise PlatformEventPayloadError("numeric value must be finite", key=key)
        return
    if isinstance(value, str):
        return
    if isinstance(value, datetime):
        raise PlatformEventPayloadError(
            "timestamp values must be persisted as their canonical string form",
            key=key,
        )
    raise PlatformEventPayloadError(
        "value must be a descriptive JSON-safe value", key=key
    )


def _scan(value: object, key: str) -> None:
    """Fail closed on credential or private-marker content anywhere in *value*."""

    if isinstance(value, Mapping):
        for nested_key, nested_value in value.items():
            if not isinstance(nested_key, str):
                raise PlatformEventPayloadError("payload keys must be strings", key=key)
            _check_key(nested_key)
            _scan(nested_value, nested_key)
        return

    if isinstance(value, str):
        if contains_high_confidence_credential(value):
            raise PlatformEventPayloadError("credential-like value", key=key)
        if _contains_private_marker(value):
            raise PlatformEventPayloadError("forbidden private marker", key=key)
        return

    if _is_sequence(value):
        for item in value:
            _scan(item, key)
        return

    _reject_non_descriptive_value(value, key)


def validate_platform_payload(payload: Mapping[str, object]) -> None:
    """Validate a platform event payload, failing closed on any violation.

    Two halves of one policy run here: the content/structure half
    (:func:`_scan`) and the lifecycle-fact *value semantics* half
    (:func:`_validate_payload_key_classes`).  An approved key name alone is not a
    contract — the key must carry the bounded kind of fact its name claims, so raw
    user prose can no longer be relocated into ``request_id``, ``status``,
    ``approved`` or ``duration_ms`` and persisted as durable lifecycle evidence.
    """

    if not isinstance(payload, Mapping):
        raise PlatformEventPayloadError("payload must be a mapping")

    for key, value in payload.items():
        if not isinstance(key, str):
            raise PlatformEventPayloadError("payload keys must be strings")
        _check_key(key)
        _scan(value, key)

    _validate_payload_key_classes(payload)


def scan_for_forbidden_platform_content(value: object, *, key: str) -> None:
    """Fail closed on forbidden keys, credentials or private markers in *value*.

    Unlike :func:`validate_platform_payload` this applies **only** the content
    half of the policy: it deliberately does not require the key to belong to the
    bounded platform vocabulary.  It exists for one bounded purpose — an adapter
    that must ignore harmless source facts the platform does not model, while
    still refusing to ignore forbidden, private or credential-bearing source
    content that it would otherwise silently drop.
    """

    _scan_forbidden_content(
        value,
        key=key,
        structural_envelope_names=STRUCTURAL_SOURCE_ENVELOPE_KEYS,
        scan_key_content=False,
    )


def scan_for_forbidden_event_facts(value: object, *, key: str) -> None:
    """Fail closed on forbidden/private/credential content in persisted header facts.

    This is the same one content policy as
    :func:`scan_for_forbidden_platform_content`, applied to a persisted canonical
    header container (``metadata``, ``permissions``).  Two deliberate differences
    make it the strictest form of the policy, because these facts are persisted
    verbatim rather than merely observed on a source event:

    * there is no structural envelope name to exempt; and
    * a key is itself content, so it is judged by the canonical credential and
      private-marker rule exactly as the Phase 10.33 Domain authority judges every
      payload/metadata key.
    """

    _scan_forbidden_content(
        value,
        key=key,
        structural_envelope_names=frozenset(),
        scan_key_content=True,
    )


def _scan_forbidden_content(
    value: object,
    *,
    key: str,
    structural_envelope_names: frozenset[str],
    scan_key_content: bool,
) -> None:
    """Shared implementation of the one forbidden-content scan."""

    if isinstance(value, Mapping):
        for nested_key, nested_value in value.items():
            if not isinstance(nested_key, str):
                raise PlatformEventPayloadError("payload keys must be strings", key=key)
            if _normalize_key(nested_key) in structural_envelope_names:
                # A structural container name is not itself content, but what it
                # contains is still scanned.
                pass
            elif is_forbidden_platform_payload_key(nested_key):
                raise PlatformEventPayloadError("forbidden payload key", key=nested_key)
            if scan_key_content:
                # A persisted key is itself content: a credential-shaped or
                # private-marker key name must fail closed rather than being
                # trusted merely because it is not one of the forbidden words.
                if contains_high_confidence_credential(nested_key):
                    raise PlatformEventPayloadError(
                        "credential-like key", key=nested_key
                    )
                if _contains_private_marker(nested_key):
                    raise PlatformEventPayloadError(
                        "forbidden private marker", key=nested_key
                    )
            _scan_forbidden_content(
                nested_value,
                key=nested_key,
                structural_envelope_names=structural_envelope_names,
                scan_key_content=scan_key_content,
            )
        return

    if isinstance(value, str):
        if contains_high_confidence_credential(value):
            raise PlatformEventPayloadError("credential-like value", key=key)
        if _contains_private_marker(value):
            raise PlatformEventPayloadError("forbidden private marker", key=key)
        return

    if _is_sequence(value):
        for item in value:
            _scan_forbidden_content(
                item,
                key=key,
                structural_envelope_names=structural_envelope_names,
                scan_key_content=scan_key_content,
            )
        return

    # Structural type half of the same one policy.  These facts are persisted
    # verbatim, so an opaque runtime object, a binary value or a non-finite number
    # fails closed here instead of being stringified into durable evidence later.
    _reject_non_descriptive_value(value, key)


def is_private_filesystem_reference(value: str) -> bool:
    """Return whether *value* syntactically denotes a non-public local path.

    The classifier is narrow and fail-closed: it answers ``True`` only for strong
    filesystem signatures (a ``file:`` URI, an absolute POSIX path, a Windows
    drive-root path, a UNC share, a ``..`` traversal segment, a relative private
    system root, a user-home directory, a known secret-bearing path segment or a
    private key file name) and ``False`` for every legitimate reference shape
    current producers publish.
    """

    if not isinstance(value, str) or not value:
        return False
    return any(pattern.search(value) for pattern in _PRIVATE_FILESYSTEM_PATTERNS)


#: A URI carrying an authority component (``scheme://…``) with userinfo before the
#: ``@``.  The identifier grammar deliberately admits ``:``, ``/`` and ``@``
#: because legitimate references need them, so a URI authority has to be
#: classified *semantically* rather than character by character.  The userinfo is
#: captured up to the first ``/``, ``?`` or ``#``, which is where RFC 3986 ends it.
_URI_USERINFO_PATTERN = re.compile(
    r"^[A-Za-z][A-Za-z0-9+.\-]*://(?P<userinfo>[^/?#]*)@"
)


def contains_uri_userinfo_credential(value: str) -> bool:
    """Return whether *value* is a URI whose userinfo carries a password.

    Independent Re-audit V7 showed that the composed Phase 10.33 credential
    detector recognizes token formats and explicit secret markers but not the
    structural signal ``<scheme>://<name>:<secret>@<authority>``.  That shape is
    not a guess about a secret: the URI grammar itself names the component after
    the ``:`` a password, and persisting it contradicts the frozen rule that
    credentials never enter event persistence.

    The check is deliberately narrow so credential-free URIs survive:

    * it requires a real scheme and a ``//`` authority;
    * it requires userinfo terminated by ``@``;
    * it requires a colon inside that userinfo with a non-empty password component.

    ``https://example.com/model`` and ``postgres://example.com/db`` therefore stay
    valid identifiers, while ``https://admin:hunter2hunter2@example.com/path`` does
    not.  The userinfo is percent-decoded before the colon test, so an encoded
    ``%3A`` that decodes to a password separator is refused as the same credential
    rather than being trusted because the raw text has no literal colon.

    The answer is a boolean.  The refused value is never returned, logged or
    echoed by the caller, so the password cannot leak through a rejection message.
    """

    if not isinstance(value, str) or not value:
        return False
    match = _URI_USERINFO_PATTERN.match(value)
    if match is None:
        return False
    _name, separator, secret = unquote(match.group("userinfo")).partition(":")
    return bool(separator) and bool(secret)


def validate_platform_identifier(value: object, *, field: str) -> str:
    """Validate one persisted platform identifier fact, failing closed.

    An identifier is a bounded, single-token value drawn from an explicit safe
    character set, and it additionally has to survive the canonical
    credential/private-marker scan, the URI-userinfo credential rule and the
    non-public filesystem classifier.  Legitimate references such as
    ``workflow:123``, ``domain.execution.completed`` or ``CORR-ORIGINAL`` pass;
    assignments, prose, credential-shaped values, URI userinfo credentials and
    non-public local filesystem locations do not.

    This function is the single shared authority every persisted identifier channel
    routes through — payload identifier fields, the canonical header facts,
    ``permissions``, identifier-classified metadata facts and nested structured
    references — so each rule below is enforced once, everywhere.
    """

    if not isinstance(value, str) or not value:
        raise PlatformEventPayloadError(
            "identifier fact must be a non-empty string", key=field
        )
    if len(value) > MAX_PLATFORM_IDENTIFIER_LENGTH:
        raise PlatformEventPayloadError(
            "identifier fact is unbounded in length", key=field
        )
    if contains_high_confidence_credential(value):
        raise PlatformEventPayloadError("credential-like value", key=field)
    if contains_uri_userinfo_credential(value):
        # A URI userinfo password is explicit credential material.  The message is
        # static, so the refused secret is never echoed into a log or a DLQ record.
        raise PlatformEventPayloadError(
            "identifier fact must not carry URI userinfo credentials", key=field
        )
    if _contains_private_marker(value):
        raise PlatformEventPayloadError("forbidden private marker", key=field)
    if is_private_filesystem_reference(value):
        # A local filesystem location — absolute or reached by relative traversal —
        # is not a public platform reference.  This is the frozen design's
        # "filesystem secrets/paths where not public-safe" rule, applied on every
        # persisted identifier channel.
        raise PlatformEventPayloadError(
            "identifier fact must not be a private filesystem location", key=field
        )
    if not _SAFE_IDENTIFIER_PATTERN.match(value):
        raise PlatformEventPayloadError(
            "identifier fact is not a safe single-token identifier", key=field
        )
    return value


def _validate_bounded_category(value: object, *, field: str) -> str:
    """Validate one categorical lifecycle token, failing closed.

    A categorical fact is a bounded token, never prose: ``completed``, ``selected``,
    ``requested``, ``resolved``, ``conversation``, ``orchestration``, ``ok`` and
    ``goal.created`` all pass, while any value containing whitespace — the shape a
    raw user sentence arrives in — cannot qualify.
    """

    if not isinstance(value, str) or not value:
        raise PlatformEventPayloadError(
            "categorical fact must be a non-empty string", key=field
        )
    if len(value) > MAX_PLATFORM_CATEGORY_LENGTH:
        raise PlatformEventPayloadError(
            "categorical fact is unbounded in length", key=field
        )
    if contains_high_confidence_credential(value):
        raise PlatformEventPayloadError("credential-like value", key=field)
    if _contains_private_marker(value):
        raise PlatformEventPayloadError("forbidden private marker", key=field)
    if not _SAFE_CATEGORY_PATTERN.match(value):
        raise PlatformEventPayloadError(
            "categorical fact must be a bounded token, not prose", key=field
        )
    return value


def _numeric_semantics_for(field: str) -> str:
    """Return the bounded numeric kind *field* names, or the generic kind.

    The lookup is by the *key name* rather than by position, so a numeric fact
    cannot escape its semantic bound by being nested one container deeper.  A
    sequence item is addressed as ``field[index]``; the index is stripped so the
    item inherits the bound of the key that holds it.
    """

    base = field.split("[", 1)[0]
    return NUMERIC_FACT_SEMANTICS.get(base, "bounded_number")


def _validate_bounded_number(value: object, *, field: str) -> int | float:
    """Validate one *actually bounded* numeric lifecycle fact, failing closed.

    Independent Re-audit V6 reproduced the V5 class accepting any finite Python
    number.  The audited behaviours are all refused here, before any repository is
    reached:

    * ``count = 10 ** 5000`` (and every other oversized integer) — the interpreter's
      integer-to-string limit is not a safety boundary and cannot make the two
      official repositories disagree;
    * ``count = -1``, ``attempts = -1``, ``sequence = -1`` and ``duration_ms = -5`` —
      a count, attempt, sequence or duration the current contract defines as
      non-negative;
    * ``duration_ms = 1e308`` and every other absurd finite float;
    * a float where the lifecycle name requires a real integer count.
    """

    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise PlatformEventPayloadError(
            "numeric fact must be an int or float", key=field
        )
    if isinstance(value, float) and not math.isfinite(value):
        raise PlatformEventPayloadError("numeric fact must be finite", key=field)

    semantics = _numeric_semantics_for(field)
    if semantics == "count":
        if not isinstance(value, int):
            raise PlatformEventPayloadError(
                "count-like numeric fact must be an integer", key=field
            )
        if value < 0:
            raise PlatformEventPayloadError(
                "count-like numeric fact must not be negative", key=field
            )
        if value > MAX_PLATFORM_NUMERIC_FACT:
            raise PlatformEventPayloadError(
                "count-like numeric fact exceeds the platform bound", key=field
            )
        return value

    if semantics == "duration":
        if value < 0:
            raise PlatformEventPayloadError(
                "duration fact must not be negative", key=field
            )
        if value > MAX_PLATFORM_NUMERIC_FACT:
            raise PlatformEventPayloadError(
                "duration fact exceeds the platform bound", key=field
            )
        return value

    if semantics == "ratio":
        if value < 0.0 or value > 1.0:
            raise PlatformEventPayloadError(
                "ratio fact must be a normalized ratio between 0.0 and 1.0",
                key=field,
            )
        return value

    # The generic bounded number: no lifecycle name implies a sign, so the whole
    # signed 64-bit range is admitted and nothing larger is.
    if value < -MAX_PLATFORM_NUMERIC_FACT or value > MAX_PLATFORM_NUMERIC_FACT:
        raise PlatformEventPayloadError(
            "numeric fact exceeds the platform bound", key=field
        )
    return value


def _validate_bounded_boolean(value: object, *, field: str) -> bool:
    """Validate one boolean lifecycle fact, failing closed.

    ``bool`` is checked before any numeric acceptance, so ``True``/``False`` are the
    only accepted values and an integer never silently becomes a lifecycle flag.
    """

    if not isinstance(value, bool):
        raise PlatformEventPayloadError(
            "boolean fact must be a real boolean", key=field
        )
    return value


def _validate_version(value: object, *, field: str) -> object:
    """Validate one version fact: a bounded number or a bounded version token.

    A numeric version participates in the same one numeric bound as every other
    persisted numeric lifecycle fact, so ``version = 1e308`` cannot enter durable
    evidence merely because a version may also be spelled as a token.
    """

    if isinstance(value, bool):
        raise PlatformEventPayloadError(
            "version fact must be a number or version token", key=field
        )
    if isinstance(value, int):
        if value < 0 or value > MAX_PLATFORM_NUMERIC_FACT:
            raise PlatformEventPayloadError(
                "numeric version fact is outside the platform bound", key=field
            )
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise PlatformEventPayloadError("version fact must be finite", key=field)
        if value < 0 or value > MAX_PLATFORM_NUMERIC_FACT:
            raise PlatformEventPayloadError(
                "numeric version fact is outside the platform bound", key=field
            )
        return value
    return _validate_bounded_category(value, field=field)


def _parse_canonical_timestamp(value: object, *, field: str) -> datetime:
    """Parse one canonical persisted timestamp into a real timezone-aware instant.

    Independent Re-audit V6 showed that the "canonical ISO-8601" class validated
    text shape rather than civil time, so ``9999-99-99T99:99Z``,
    ``2026-02-31T12:00Z`` and ``2026-09-27T25:61Z`` all reached durable evidence,
    as did a timezone-less ``2026-09-27T12:00`` even though the canonical chronology
    contract is timezone-aware.

    The shape rule remains the existing one, but the value must additionally parse
    as a real calendar/time value *and* carry an explicit UTC offset.  Nothing is
    reinterpreted or normalized here: an invalid value fails closed instead of being
    silently repaired, and the caller keeps the documented canonical serialization.
    """

    if not isinstance(value, str) or not value:
        raise PlatformEventPayloadError(
            "timestamp fact must be its canonical string form", key=field
        )
    if len(value) > MAX_PLATFORM_TIMESTAMP_LENGTH:
        raise PlatformEventPayloadError(
            "timestamp fact is unbounded in length", key=field
        )
    if not _SAFE_TIMESTAMP_PATTERN.match(value):
        raise PlatformEventPayloadError(
            "timestamp fact must be canonical ISO-8601", key=field
        )
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise PlatformEventPayloadError(
            "timestamp fact is not a real calendar/time value", key=field
        ) from exc
    if parsed.tzinfo is None or parsed.tzinfo.utcoffset(parsed) is None:
        raise PlatformEventPayloadError(
            "timestamp fact must be timezone-aware", key=field
        )
    return parsed


def _validate_canonical_timestamp(value: object, *, field: str) -> str:
    """Validate one timestamp fact in the canonical persisted ISO-8601 string form.

    The durable record stores a timestamp as a string, so a live ``datetime`` would
    reopen as a ``str`` and the live and persisted shapes of the same fact would
    differ.  Only the canonical string form is accepted here, and it must be a real
    timezone-aware civil timestamp rather than merely timestamp-shaped text.
    """

    _parse_canonical_timestamp(value, field=field)
    return value


def _validate_domain_reference(value: object, *, field: str) -> object:
    """Validate one domain reference fact.

    A domain identity is a bounded reference string, or the structured identity
    mapping a canonical ``DomainId`` projection produces.  A structured identity is
    validated recursively against the documented nested shape rather than being
    flattened, and the caller rejects binary buffers before this point, so a buffer
    can never be read as a reference.
    """

    if isinstance(value, Mapping):
        _validate_structured_reference(value, field=field)
        return value
    return validate_platform_identifier(value, field=field)


def _validate_number_sequence(value: object, *, field: str) -> list[object]:
    """Validate a bounded sequence of integers, failing closed."""

    if not _is_sequence(value):
        raise PlatformEventPayloadError(
            "structured sequence must be a sequence of integers", key=field
        )
    items = list(value)
    if len(items) > MAX_PLATFORM_REFERENCE_SEQUENCE_LENGTH:
        raise PlatformEventPayloadError(
            "structured sequence is unbounded in length", key=field
        )
    for index, item in enumerate(items):
        _validate_bounded_number(item, field=f"{field}[{index}]")
    return items


def _validate_structured_reference(value: object, *, field: str) -> None:
    """Validate a structured reference container against its documented shape.

    Nested facts are validated recursively.  An unknown nested key fails closed
    instead of becoming a new mirroring path, and a nested identifier is judged by
    the same bounded rule as a top-level one — so the V3 mappingproxy/tuple/live
    reopen behaviour is preserved without reopening a prose escape hatch.
    """

    if not isinstance(value, Mapping):
        raise PlatformEventPayloadError(
            "structured reference must be a mapping of documented facts", key=field
        )
    for nested_key, nested_value in value.items():
        if not isinstance(nested_key, str):
            raise PlatformEventPayloadError("payload keys must be strings", key=field)
        nested_class = STRUCTURED_REFERENCE_KEYS.get(nested_key)
        if nested_class is None:
            raise PlatformEventPayloadError(
                "structured reference key is not a documented lifecycle fact",
                key=nested_key,
            )
        _validate_class(nested_class, nested_value, field=nested_key)


def _validate_structured_reference_sequence(value: object, *, field: str) -> None:
    """Validate a structured reference sequence against its documented shape."""

    if _is_binary_buffer(value) or not _is_sequence(value):
        raise PlatformEventPayloadError(
            "structured reference must be a sequence of documented facts", key=field
        )
    items = list(value)
    if len(items) > MAX_PLATFORM_REFERENCE_SEQUENCE_LENGTH:
        raise PlatformEventPayloadError(
            "structured reference is unbounded in length", key=field
        )
    for index, item in enumerate(items):
        if isinstance(item, Mapping):
            _validate_structured_reference(item, field=f"{field}[{index}]")
            continue
        _validate_domain_reference(item, field=f"{field}[{index}]")


def _validate_class(value_class: str, value: object, *, field: str) -> object:
    """Validate *value* against one explicit lifecycle value class, failing closed.

    This is the single dispatch point of the semantic half of the policy, so every
    approved key is judged by exactly one documented class and nothing can fall
    through to unrestricted prose.
    """

    if value_class == "null":
        if value is not None:
            raise PlatformEventPayloadError("value must be null", key=field)
        return None
    if value_class == "identifier":
        if value is None:
            # An absent optional reference is not a reference *value*: closed-phase
            # sources legitimately publish an explicit ``None`` for an optional
            # identifier, and the persisted header gate already skips ``None``
            # identifier facts.  Accepting it here keeps one consistent rule and
            # introduces no prose path, because a non-``None`` value still has to
            # pass the bounded single-token identifier rule.
            return None
        return validate_platform_identifier(value, field=field)
    if value_class == "category":
        return _validate_bounded_category(value, field=field)
    if value_class == "boolean":
        return _validate_bounded_boolean(value, field=field)
    if value_class == "number":
        return _validate_bounded_number(value, field=field)
    if value_class == "version":
        return _validate_version(value, field=field)
    if value_class == "timestamp":
        return _validate_canonical_timestamp(value, field=field)
    if value_class == "number_sequence":
        return _validate_number_sequence(value, field=field)
    if value_class == "bounded_sequence":
        return _validate_bounded_scalar_sequence(value, field=field)
    if value_class == "metadata_container":
        _validate_metadata_container(value, field=field)
        return value
    if value_class == "domain_reference_sequence":
        _validate_structured_reference_sequence(value, field=field)
        return value
    if value_class == "structured_reference":
        _validate_structured_reference(value, field=field)
        return value
    if value_class == "structured_reference_sequence":
        _validate_structured_reference_sequence(value, field=field)
        return value
    raise PlatformEventPayloadError(
        f"unknown lifecycle value class '{value_class}'", key=field
    )


def _validate_payload_key_classes(payload: Mapping[str, object]) -> None:
    """Enforce the semantic value class of every approved payload key."""

    for key, value in payload.items():
        value_class = _payload_value_class(key)
        if value_class is None:
            raise PlatformEventPayloadError(
                "payload key has no declared lifecycle value class", key=key
            )
        _validate_class(value_class, value, field=key)


def _payload_value_class(key: str) -> str | None:
    """Return the declared value class of one approved payload key, or ``None``."""

    for value_class, keys in PAYLOAD_KEY_CLASSES.items():
        if key in keys:
            return value_class
    return None


def _validate_bounded_scalar_sequence(value: object, *, field: str) -> list[object]:
    """Validate a bounded sequence of bounded scalar metadata values."""

    if _is_binary_buffer(value) or not _is_sequence(value):
        raise PlatformEventPayloadError(
            "metadata sequence must be a sequence of bounded values", key=field
        )
    items = list(value)
    if len(items) > MAX_PLATFORM_REFERENCE_SEQUENCE_LENGTH:
        raise PlatformEventPayloadError(
            "metadata sequence is unbounded in length", key=field
        )
    for index, item in enumerate(items):
        _validate_metadata_scalar(
            item, field=f"{field}[{index}]", classes=_METADATA_SEQUENCE_ITEM_CLASSES
        )
    return items


def _validate_metadata_scalar(
    value: object, *, field: str, classes: frozenset[str]
) -> object:
    """Validate one bounded metadata scalar against an allowed class set.

    The class is selected from the value's own Python type rather than by trying
    each allowed class in turn, so the rule stays total and explicit: a boolean is
    judged as a boolean, a number as a number, a string as the narrowest allowed
    token class, ``None`` only where a null is admitted, and every other type fails
    closed.
    """

    if value is None:
        return _validate_class("null", value, field=field)
    if isinstance(value, bool):
        return _validate_class("boolean", value, field=field)
    if isinstance(value, (int, float)):
        return _validate_class("number", value, field=field)
    if isinstance(value, str):
        if classes & {"category", "identifier"}:
            return _validate_bounded_category(value, field=field)
        raise PlatformEventPayloadError(
            "metadata value must be a bounded lifecycle value", key=field
        )
    raise PlatformEventPayloadError(
        "metadata value must be a bounded lifecycle value", key=field
    )


def _validate_metadata_container(value: object, *, field: str) -> None:
    """Validate one bounded metadata container against its documented nested shape."""

    if not isinstance(value, Mapping):
        raise PlatformEventPayloadError(
            "metadata container must be a mapping of documented facts", key=field
        )
    for nested_key, nested_value in value.items():
        if not isinstance(nested_key, str):
            raise PlatformEventPayloadError("metadata keys must be strings", key=field)
        nested_class = METADATA_CONTAINER_KEYS.get(nested_key)
        if nested_class is None:
            raise PlatformEventPayloadError(
                "metadata container key is not a documented lifecycle fact",
                key=nested_key,
            )
        _validate_class(nested_class, nested_value, field=nested_key)


def _validate_metadata_value_classes(metadata: Mapping[str, object]) -> None:
    """Enforce the semantic value class of every persisted metadata fact.

    Only the bounded lifecycle metadata vocabulary current Phase 11.22 producers,
    adapters and closed-phase contracts actually use is admitted, and each key
    carries an explicit bounded value class.  An unknown metadata key fails closed,
    so metadata cannot become a new content-mirroring path merely because a
    producer picks an innocuous-sounding key name for raw user text.
    """

    for key, value in metadata.items():
        value_class = METADATA_KEY_CLASSES.get(key)
        if value_class is None:
            raise PlatformEventPayloadError(
                "metadata key is outside the bounded lifecycle metadata vocabulary",
                key=key,
            )
        _validate_class(value_class, value, field=key)


def _header_identifier_facts(header: Any) -> tuple[tuple[str, object], ...]:
    """Return every persisted identifier header fact as ``(field, value)``.

    The fields are read explicitly rather than resolved by name, so the gate can
    never become dispatch driven by event data, and so adding a new persisted
    identifier field is a visible, deliberate edit here and in
    :data:`PLATFORM_IDENTIFIER_HEADER_FIELDS`.
    """

    return (
        ("event_id", header.event_id),
        ("source", header.source),
        ("producer", header.producer),
        ("aggregate_id", header.aggregate_id),
        ("agent_id", header.agent_id),
        ("agent_run_id", header.agent_run_id),
        ("goal_id", header.goal_id),
        ("workflow_id", header.workflow_id),
        ("task_id", header.task_id),
        ("iteration_id", header.iteration_id),
        ("correlation_id", header.correlation_id),
        ("causation_id", header.causation_id),
        ("actor_id", header.actor_id),
    )


def category_for_delivery_error(exception: BaseException) -> str | None:
    """Return the bounded safe DLQ category for *exception*, or ``None``.

    This is the credential/private-marker half of the one canonical DLQ
    safe-error-category rule, and it lives here because this is the module that
    already composes the Phase 10.33 high-confidence credential detector and the
    forbidden private-marker vocabulary.  ``cmm.agent_runtime`` is architecturally
    forbidden from importing ``cmm.domains``, so the composed Phase 11.22 event
    system injects this function into the canonical bus through
    :meth:`~cmm.agent_runtime.runtime_event_bus.AgentRuntimeEventBus.bind_error_categorizer`
    rather than the bus reaching for the vocabulary itself.

    The exception class name is attacker-influenced — Python permits
    ``type("api_key=abcdef1234567890", (Exception,), {})`` — so a name that carries a
    credential or a private marker returns ``None`` and the bus records its neutral
    bounded fallback instead.  The rule is a *content* scan only; the bus keeps
    ownership of the bounded-name half.
    """

    name = type(exception).__name__
    if not isinstance(name, str):
        return None
    if contains_high_confidence_credential(name):
        return None
    if _contains_private_marker(name):
        return None
    return name


def canonicalize_platform_event_sensitivity(value: object) -> Any:
    """Return the one canonical runtime representation of a sensitivity fact.

    The persisted sensitivity fact is an :class:`EventSensitivity` member.  Two
    inputs are accepted and nothing else:

    * an already-canonical :class:`EventSensitivity` member, returned unchanged; and
    * exactly one explicit supported-string normalization — a string that is one of
      the canonical enum's own values, immediately converted to that member.

    Every other input fails closed *before* the event is constructed or persisted:
    a number, ``None``, an arbitrary object, an unknown label and — critically — a
    credential-bearing or private-marker string.  Without this gate an arbitrary
    string could enter a persisted canonical header field the documentation
    describes as a closed classification.

    The canonical enum is imported lazily so this safety module keeps its place at
    the bottom of the dependency direction and no import cycle is introduced.
    """

    from cmm.agent_runtime.runtime_event_contracts import EventSensitivity

    if isinstance(value, EventSensitivity):
        return value

    if isinstance(value, str):
        # The credential/private-marker rule is applied to the *string* form, so a
        # secret cannot ride into persistence merely by spelling a valid label.
        if contains_high_confidence_credential(value):
            raise PlatformEventPayloadError("credential-like value", key="sensitivity")
        if _contains_private_marker(value):
            raise PlatformEventPayloadError(
                "forbidden private marker", key="sensitivity"
            )
        try:
            return EventSensitivity(value)
        except ValueError as exc:
            raise PlatformEventPayloadError(
                "sensitivity is outside the canonical classification", key="sensitivity"
            ) from exc

    raise PlatformEventPayloadError(
        "sensitivity must be a canonical EventSensitivity value", key="sensitivity"
    )


def strictest_platform_sensitivity(first: object, second: object) -> Any:
    """Return the stricter of two canonical sensitivity facts.

    This is the one classification rule behind "a stricter source sensitivity must be
    promoted to the canonical header, and a lower payload value must never downgrade
    it".  Both inputs are canonicalized first, so an arbitrary string cannot be
    smuggled in as a classification.  The canonical enum is imported lazily for the
    same dependency-direction reason as
    :func:`canonicalize_platform_event_sensitivity`.
    """

    from cmm.agent_runtime.runtime_event_contracts import EventSensitivity

    strictness = (
        EventSensitivity.PUBLIC,
        EventSensitivity.INTERNAL,
        EventSensitivity.CONFIDENTIAL,
        EventSensitivity.RESTRICTED,
    )
    first_canonical = canonicalize_platform_event_sensitivity(first)
    second_canonical = canonicalize_platform_event_sensitivity(second)
    if strictness.index(first_canonical) >= strictness.index(second_canonical):
        return first_canonical
    return second_canonical


def validate_platform_permissions(permissions: object) -> None:
    """Validate the structural shape of a persisted permissions fact.

    This must run **before** any factory coercion.  A plain string is a
    ``Sequence`` of characters, so ``list(permissions)`` would silently turn
    ``"admin"`` into ``["a", "d", "m", "i", "n"]`` and persist a permission set the
    caller never expressed.  Only a real sequence of canonical permission
    identifiers is accepted, and binary containers are refused outright.
    """

    if isinstance(permissions, str) or _is_binary_buffer(permissions):
        raise PlatformEventPayloadError(
            "event permissions must be a sequence of identifiers", key="permissions"
        )
    if not _is_sequence(permissions):
        raise PlatformEventPayloadError(
            "event permissions must be a sequence of identifiers", key="permissions"
        )
    for index, entry in enumerate(permissions):
        validate_platform_identifier(entry, field=f"permissions[{index}]")


def split_canonical_header_facts(
    payload: Mapping[str, object],
) -> tuple[dict[str, object], dict[str, object]]:
    """Split *payload* into ordinary payload facts and canonical header facts.

    Returns ``(remaining_payload, canonical_header_facts)``.  Only keys inside the
    bounded payload vocabulary that also name a canonical header fact are moved, so
    the closed payload vocabulary is preserved exactly and a key outside it is still
    rejected by the ordinary gate rather than becoming a header channel.
    """

    if not isinstance(payload, Mapping):
        raise PlatformEventPayloadError("payload must be a mapping")

    remaining: dict[str, object] = {}
    canonical: dict[str, object] = {}
    for key, value in payload.items():
        if isinstance(key, str) and key in CANONICAL_HEADER_PAYLOAD_KEYS:
            canonical[key] = value
        else:
            remaining[key] = value
    return remaining, canonical


def reconcile_canonical_header_fact(
    key: str,
    payload_value: object,
    header_value: object,
) -> object:
    """Return the one authoritative value of a canonical header fact.

    ``header_value`` is the value the canonical header already carries, or ``None``
    when the caller supplied nothing for that fact.  The rule is total and has one
    exception:

    * an unset header fact takes the payload value, so the payload copy becomes the
      single canonical header fact instead of a second persisted representation;
    * a header fact equal to the payload value stays as it is;
    * a header fact that contradicts the payload value fails closed, so two
      contradictory versions of one event fact can never both persist;
    * **sensitivity** is the exception: the canonical header keeps the *stricter*
      classification, so a stricter source value is promoted into the header and a
      lower payload value can never downgrade it.
    """

    if key not in CANONICAL_HEADER_PAYLOAD_KEYS:
        raise PlatformEventPayloadError("not a canonical header payload fact", key=key)

    if key == "sensitivity":
        if header_value is None:
            return canonicalize_platform_event_sensitivity(payload_value)
        return strictest_platform_sensitivity(header_value, payload_value)

    if key in _TIMESTAMP_HEADER_FACT_KEYS:
        parsed = _parse_canonical_timestamp(payload_value, field=key)
        if header_value is None:
            return parsed
        if isinstance(header_value, datetime) and parsed == header_value:
            return header_value
        raise PlatformEventPayloadError(
            "payload fact conflicts with the canonical header fact", key=key
        )

    if not isinstance(payload_value, str):
        # An explicit ``None`` for an optional reference is not a reference *value*:
        # closed-phase sources legitimately publish ``workflow_id=None``, and the
        # identifier class accepts exactly that meaning.  There is nothing to adopt
        # and nothing to contradict, so the header keeps what it already carries.
        if payload_value is None:
            return header_value
        raise PlatformEventPayloadError(
            "canonical header fact must be its canonical string form", key=key
        )
    if header_value is None:
        return payload_value
    if payload_value == header_value:
        return header_value
    raise PlatformEventPayloadError(
        "payload fact conflicts with the canonical header fact", key=key
    )


def canonical_header_fact_values(header: Any) -> Mapping[str, object]:
    """Return the canonical header facts a payload key could duplicate.

    Every field is read by explicit attribute access rather than resolved by name,
    so this can never become dispatch driven by event data — the same rule the
    persisted-identifier reader follows.  The result is the header side of the one
    canonical header authority: it is what a payload copy must be reconciled
    against, never a second source of truth.
    """

    return MappingProxyType(
        {
            "event_id": header.event_id,
            "event_type": header.event_type,
            "schema_version": header.schema_version,
            "occurred_at": header.occurred_at,
            "emitted_at": header.emitted_at,
            "agent_id": header.agent_id,
            "goal_id": header.goal_id,
            "workflow_id": header.workflow_id,
            "task_id": header.task_id,
            "correlation_id": header.correlation_id,
            "causation_id": header.causation_id,
            "aggregate_id": header.aggregate_id,
            "producer": header.producer,
            "sensitivity": header.sensitivity,
        }
    )


def validate_platform_event_facts(event: Any) -> None:
    """Apply the one canonical Phase 11.22 safety gate to every persisted fact.

    ``payload.data`` and every persisted free-form header channel are judged by
    the same policy, so forbidden material can no longer be moved out of the
    payload and into ``metadata``, ``permissions``, ``producer``, ``aggregate_id``
    or ``source`` to bypass the boundary — and no persisted header channel is left
    with an unchecked runtime type that a serializer could later stringify.
    """

    header = getattr(event, "header", None)
    if header is None:
        raise PlatformEventPayloadError("platform event has no canonical header")

    for field, value in _header_identifier_facts(header):
        if value is None:
            continue
        validate_platform_identifier(value, field=field)

    # The persisted classification is a closed vocabulary, enforced as the
    # canonical runtime enum rather than trusted as whatever the caller passed.
    canonicalize_platform_event_sensitivity(getattr(header, "sensitivity", None))

    metadata = getattr(header, "metadata", None)
    if not isinstance(metadata, Mapping):
        raise PlatformEventPayloadError(
            "event metadata must be a mapping", key="metadata"
        )
    for metadata_key in metadata:
        if not isinstance(metadata_key, str):
            raise PlatformEventPayloadError(
                "event metadata keys must be strings", key="metadata"
            )
    scan_for_forbidden_event_facts(metadata, key="metadata")
    # The content half above refuses forbidden keys, credentials and private
    # markers anywhere in metadata; this half refuses a *value* that is not the
    # bounded lifecycle fact its metadata key claims to represent, so metadata
    # cannot become a prose side channel under an innocuous key name.
    _validate_metadata_value_classes(metadata)

    permissions = getattr(header, "permissions", None)
    # The structural shape is checked *before* any factory coercion, so a plain
    # string can never be iterated into a character list.
    validate_platform_permissions(permissions)


def _freeze(value: object) -> object:
    """Return a recursively immutable copy of an already-validated value."""

    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, Mapping):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if _is_binary_buffer(value):
        raise PlatformEventPayloadError("binary value must not be persisted")
    if _is_sequence(value):
        return tuple(_freeze(item) for item in value)
    raise PlatformEventPayloadError("value must be a descriptive immutable value")


def freeze_platform_payload(payload: Mapping[str, object]) -> Mapping[str, object]:
    """Validate *payload* and return a recursively immutable detached copy.

    The result is safe to hand to the canonical event factory: every key is inside
    the bounded vocabulary, every value is a descriptive immutable value, and no
    key or value carries credentials, prompts, reasoning or provider content.
    """

    validate_platform_payload(payload)
    return MappingProxyType({key: _freeze(value) for key, value in payload.items()})


def canonicalize_platform_payload(payload: Mapping[str, object]) -> dict[str, Any]:
    """Validate *payload* and return one canonical JSON-compatible plain copy.

    This is the canonical payload normalization for the Phase 11.22 public
    boundary.  It applies the one safety gate, then produces the single stable
    representation the durable record necessarily reopens as:

    * mapping → plain ``dict``;
    * supported sequence → plain ``list``;
    * scalar → an approved finite descriptive scalar.

    The result therefore (a) shares no nested container with the caller, so a
    caller cannot mutate a published canonical event through an alias it still
    holds, and (b) has the same shape live, persisted, reopened and replayed —
    a tuple would otherwise reopen from JSON as a ``list``.

    The normalized result is re-validated, so the canonical output is proven to be
    inside the policy rather than assumed to be.
    """

    validate_platform_payload(payload)
    normalized = _canonicalize_payload_value(payload)
    validate_platform_payload(normalized)
    return normalized


def _canonicalize_payload_value(value: object) -> Any:
    """Return the canonical JSON-compatible ``dict``/``list``/scalar form of *value*.

    Binary containers are refused here as well, and **before** generic sequence
    handling, so this shape transform can never turn a binary buffer — including an
    ``array.array`` — into an integer list even if it is ever reached without the
    validation half having run first.
    """

    if isinstance(value, Mapping):
        return {
            str(key): _canonicalize_payload_value(item) for key, item in value.items()
        }
    if isinstance(value, str):
        return value
    _reject_binary_buffer(value, "payload")
    if _is_sequence(value):
        return [_canonicalize_payload_value(item) for item in value]
    return value


def thaw_platform_payload(payload: Mapping[str, object]) -> dict[str, Any]:
    """Return a plain mutable copy of a frozen platform payload."""

    def thaw(value: object) -> Any:
        if isinstance(value, Mapping):
            return {key: thaw(item) for key, item in value.items()}
        if isinstance(value, tuple):
            return [thaw(item) for item in value]
        return value

    return {key: thaw(value) for key, value in payload.items()}
