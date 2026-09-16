"""Phase 11.2 — structured orchestration errors.

Phase 11.2 reuses the Phase 11.1 platform boundary value
:class:`cmm.platform.contracts.ErrorResult`; it deliberately creates no second
global error payload.

These typed exceptions carry safe identifiers and reason codes only.  Error
details are structurally restricted: keys naming secret-bearing or
reasoning-bearing content fail closed and values must be short descriptive
strings, so a raw request payload, prompt, credential, provider payload,
traceback or copied sensitive context can never reach a public result.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from types import MappingProxyType
from typing import Any

from cmm.platform.contracts import ErrorResult

__all__ = [
    "AgentRoutingError",
    "ContextResolutionError",
    "DecisionPersistenceError",
    "DomainRoutingError",
    "IntentResolutionError",
    "OrchestrationError",
    "OrchestrationPolicyError",
]

#: Normalized detail keys (``api_key``) that fail closed.
FORBIDDEN_DETAIL_KEYS = frozenset(
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
        "api_key",
        "apikey",
        "access_key",
        "private_key",
        "prompt",
        "prompts",
        "reasoning",
        "raw_reasoning",
        "hidden_reasoning",
        "chain_of_thought",
        "provider_payload",
        "payload",
        "traceback",
        "stack_trace",
        "request_text",
        "raw_request",
        "raw_input",
    }
)

#: Normalized detail key tokens whose presence in any segment fails closed.
FORBIDDEN_DETAIL_KEY_TOKENS = frozenset(
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
        "raw",
    }
)


def _normalize_key(key: str) -> str:
    """Return the deterministic normalized form of a detail key."""

    return re.sub(r"[^a-z0-9]+", "_", key.strip().lower()).strip("_")


#: Separator-free forms, so camelCase and separated spellings compare equal.
_FORBIDDEN_DETAIL_KEYS_SQUASHED = frozenset(
    key.replace("_", "") for key in FORBIDDEN_DETAIL_KEYS
)


def _is_forbidden_detail_key(key: str) -> bool:
    """Return whether *key* names content that must never enter a result.

    Comparison is exact over the normalized key and its deterministic segments,
    so it never guesses at arbitrary string content.
    """

    normalized = _normalize_key(key)
    if not normalized:
        return False
    if normalized in FORBIDDEN_DETAIL_KEYS:
        return True
    if normalized.replace("_", "") in _FORBIDDEN_DETAIL_KEYS_SQUASHED:
        return True
    segments = normalized.split("_")
    if any(segment in FORBIDDEN_DETAIL_KEY_TOKENS for segment in segments):
        return True
    return "".join(segments) in FORBIDDEN_DETAIL_KEY_TOKENS


def _text(value: Any, field_name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string")
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} must be non-empty")
    return normalized


def _normalize_details(details: Mapping[str, Any] | None) -> dict[str, str]:
    """Return a shallow, secret-free, string-to-string detail mapping."""

    if details is None:
        return {}
    if not isinstance(details, Mapping):
        raise TypeError("details must be a mapping of strings to strings")

    normalized: dict[str, str] = {}
    for key, value in details.items():
        if not isinstance(key, str):
            raise TypeError("detail keys must be strings")
        _text(key, "detail key")
        if _is_forbidden_detail_key(key):
            raise ValueError(f"detail key '{key}' is not permitted in an error result")
        if not isinstance(value, str):
            raise TypeError("detail values must be strings")
        normalized[key] = _text(value, "detail value")
    return normalized


class OrchestrationError(Exception):
    """Base typed Phase 11.2 orchestration failure.

    ``code``, ``category`` and ``retryable`` are class-level defaults that a
    subclass (or an explicit constructor argument) may narrow.  No traceback,
    no raw payload and no hidden reasoning is ever exposed through
    :meth:`to_error_result`.
    """

    code: str = "ORCHESTRATION_ERROR"
    category: str = "orchestration"
    retryable: bool = False

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        details: Mapping[str, Any] | None = None,
        retryable: bool | None = None,
    ) -> None:
        normalized_message = _text(message, "message")
        super().__init__(normalized_message)

        self.message = normalized_message
        if code is not None:
            self.code = _text(code, "code")
        if retryable is not None:
            if not isinstance(retryable, bool):
                raise TypeError("retryable must be a bool")
            self.retryable = retryable
        self.details: Mapping[str, str] = MappingProxyType(_normalize_details(details))

    def to_error_result(self) -> ErrorResult:
        """Return the safe platform-boundary result for this failure."""

        return ErrorResult(
            code=self.code,
            message=self.message,
            category=self.category,
            details=dict(self.details),
        )


class IntentResolutionError(OrchestrationError):
    """Deterministic intent resolution could not produce a safe decision."""

    code = "INTENT_RESOLUTION_ERROR"
    category = "intent"


class ContextResolutionError(OrchestrationError):
    """Authorized context resolution failed closed."""

    code = "CONTEXT_RESOLUTION_ERROR"
    category = "context"


class DomainRoutingError(OrchestrationError):
    """Canonical domain routing failed closed."""

    code = "DOMAIN_ROUTING_ERROR"
    category = "domain"


class AgentRoutingError(OrchestrationError):
    """Execution-path or canonical agent routing failed closed."""

    code = "AGENT_ROUTING_ERROR"
    category = "agent"


class OrchestrationPolicyError(OrchestrationError):
    """The restrictive orchestration policy could not be evaluated."""

    code = "ORCHESTRATION_POLICY_ERROR"
    category = "policy"


class DecisionPersistenceError(OrchestrationError):
    """The required orchestration decision record could not be persisted."""

    code = "DECISION_PERSISTENCE_ERROR"
    category = "persistence"
