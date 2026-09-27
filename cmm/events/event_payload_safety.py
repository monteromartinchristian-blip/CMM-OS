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

from cmm.domains.credential_policy import contains_high_confidence_credential
from cmm.domains.event_contracts import _contains_private_marker

__all__ = [
    "ALLOWED_PAYLOAD_KEYS",
    "FORBIDDEN_PAYLOAD_KEYS",
    "FORBIDDEN_PAYLOAD_KEY_TOKENS",
    "MAX_PLATFORM_IDENTIFIER_LENGTH",
    "PLATFORM_CONTAINER_HEADER_FIELDS",
    "PLATFORM_IDENTIFIER_HEADER_FIELDS",
    "PlatformEventPayloadError",
    "canonicalize_platform_event_sensitivity",
    "canonicalize_platform_payload",
    "freeze_platform_payload",
    "is_forbidden_platform_payload_key",
    "is_forbidden_source_content_key",
    "scan_for_forbidden_event_facts",
    "scan_for_forbidden_platform_content",
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

#: A persisted identifier is a single bounded token drawn from an explicit safe
#: character set.  Assignments, whitespace, quotes and free prose — the shapes a
#: leaked prompt or credential would arrive in — are refused outright, on top of
#: the credential/private-marker scan.
_SAFE_IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:@+\-/]*$")

#: Upper bound for one persisted identifier fact.
MAX_PLATFORM_IDENTIFIER_LENGTH = 256


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


def _is_sequence(value: object) -> bool:
    return isinstance(value, Sequence) and not isinstance(
        value, (str, bytes, bytearray)
    )


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
    if isinstance(value, (bytes, bytearray, memoryview)):
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
    """Validate a platform event payload, failing closed on any violation."""

    if not isinstance(payload, Mapping):
        raise PlatformEventPayloadError("payload must be a mapping")

    for key, value in payload.items():
        if not isinstance(key, str):
            raise PlatformEventPayloadError("payload keys must be strings")
        _check_key(key)
        _scan(value, key)


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


def validate_platform_identifier(value: object, *, field: str) -> str:
    """Validate one persisted platform identifier fact, failing closed.

    An identifier is a bounded, single-token value drawn from an explicit safe
    character set, and it additionally has to survive the canonical
    credential/private-marker scan.  Legitimate references such as
    ``workflow:123``, ``domain.execution.completed`` or ``CORR-ORIGINAL`` pass;
    assignments, prose and credential-shaped values do not.
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
    if _contains_private_marker(value):
        raise PlatformEventPayloadError("forbidden private marker", key=field)
    if not _SAFE_IDENTIFIER_PATTERN.match(value):
        raise PlatformEventPayloadError(
            "identifier fact is not a safe single-token identifier", key=field
        )
    return value


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


def validate_platform_permissions(permissions: object) -> None:
    """Validate the structural shape of a persisted permissions fact.

    This must run **before** any factory coercion.  A plain string is a
    ``Sequence`` of characters, so ``list(permissions)`` would silently turn
    ``"admin"`` into ``["a", "d", "m", "i", "n"]`` and persist a permission set the
    caller never expressed.  Only a real sequence of canonical permission
    identifiers is accepted, and binary containers are refused outright.
    """

    if isinstance(permissions, (str, bytes, bytearray, memoryview)) or not _is_sequence(
        permissions
    ):
        raise PlatformEventPayloadError(
            "event permissions must be a sequence of identifiers", key="permissions"
        )
    for index, entry in enumerate(permissions):
        validate_platform_identifier(entry, field=f"permissions[{index}]")


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
    """Return the canonical JSON-compatible ``dict``/``list``/scalar form of *value*."""

    if isinstance(value, Mapping):
        return {
            str(key): _canonicalize_payload_value(item) for key, item in value.items()
        }
    if isinstance(value, str):
        return value
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
