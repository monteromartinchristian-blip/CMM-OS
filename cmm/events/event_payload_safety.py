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
from types import MappingProxyType
from typing import Any

from cmm.domains.credential_policy import contains_high_confidence_credential
from cmm.domains.event_contracts import _contains_private_marker

__all__ = [
    "ALLOWED_PAYLOAD_KEYS",
    "FORBIDDEN_PAYLOAD_KEYS",
    "FORBIDDEN_PAYLOAD_KEY_TOKENS",
    "PlatformEventPayloadError",
    "freeze_platform_payload",
    "is_forbidden_platform_payload_key",
    "thaw_platform_payload",
    "validate_platform_payload",
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

    if value is None or isinstance(value, bool):
        return
    if isinstance(value, int):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise PlatformEventPayloadError("numeric value must be finite", key=key)
        return

    raise PlatformEventPayloadError(
        "value must be a descriptive immutable value", key=key
    )


def validate_platform_payload(payload: Mapping[str, object]) -> None:
    """Validate a platform event payload, failing closed on any violation."""

    if not isinstance(payload, Mapping):
        raise PlatformEventPayloadError("payload must be a mapping")

    for key, value in payload.items():
        if not isinstance(key, str):
            raise PlatformEventPayloadError("payload keys must be strings")
        _check_key(key)
        _scan(value, key)


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


def thaw_platform_payload(payload: Mapping[str, object]) -> dict[str, Any]:
    """Return a plain mutable copy of a frozen platform payload."""

    def thaw(value: object) -> Any:
        if isinstance(value, Mapping):
            return {key: thaw(item) for key, item in value.items()}
        if isinstance(value, tuple):
            return [thaw(item) for item in value]
        return value

    return {key: thaw(value) for key, value in payload.items()}
