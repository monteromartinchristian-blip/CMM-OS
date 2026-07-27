"""Phase 9.23 – Agent Registry & Factory Error Hierarchy.

Structured exception hierarchy for the Agent Registry & Factory.

All errors:
* carry a stable ``error_code``;
* accept a structured ``details`` payload;
* never expose stack traces, secrets, prompts, or internal text;
* never propagate ``str(exc)`` of arbitrary internal errors.

The base class performs sanitization so that callers cannot accidentally
leak sensitive patterns (``chain_of_thought``, ``private_prompt``,
``api_key``, ``password``, ``private_key``, ``bearer`` …).
"""

from __future__ import annotations

from typing import Any

_SENSITIVE_PATTERNS: tuple[str, ...] = (
    "chain_of_thought",
    "private_prompt",
    "internal_reasoning",
    "api_key",
    "apikey",
    "password",
    "passwd",
    "private_key",
    "secret",
    "bearer ",
    "token=",
    "traceback (most recent call last)",
    "raise ",
)


def _is_sensitive_key(key: str) -> bool:
    if not isinstance(key, str):
        return False
    lowered = key.lower()
    for needle in _SENSITIVE_PATTERNS:
        if needle in lowered:
            return True
    return False


def _sanitize_text(text: str) -> str:
    """Sanitize a string to remove sensitive patterns and traceback text.

    Returns a generic safe string when any sensitive pattern is detected.
    """
    if not isinstance(text, str):
        return "An internal error occurred"
    lowered = text.lower()
    for needle in _SENSITIVE_PATTERNS:
        if needle in lowered:
            return "An internal error occurred"
    return text


def _is_safe_primitive(value: Any) -> bool:
    """Return True for primitives that are JSON-safe verbatim."""
    return isinstance(value, (bool, int, float))


def _sanitize_details(details: Any) -> dict[str, Any]:
    """Return a structured, sanitized view of error details.

    JSON-safe primitives (bool/int/float) are preserved verbatim. Lists,
    tuples and dicts are sanitized recursively. Other types are
    represented by a generic safe string to avoid leaking memory
    addresses or chain-of-thought fragments coming from ``repr``.

    Keys that look sensitive (contain *api_key*, *password*, ...) have
    their value replaced by a generic safe string regardless of the
    original content.
    """
    if details is None:
        return {}
    if not isinstance(details, dict):
        return {"value": "An internal error occurred"}
    out: dict[str, Any] = {}
    for key, value in details.items():
        safe_key = key if isinstance(key, str) else str(key)
        if _is_sensitive_key(safe_key):
            out[safe_key] = "An internal error occurred"
            continue
        if isinstance(value, str):
            out[safe_key] = _sanitize_text(value)
        elif _is_safe_primitive(value):
            out[safe_key] = value
        elif isinstance(value, dict):
            out[safe_key] = _sanitize_details(value)
        elif isinstance(value, (list, tuple)):
            cleaned: list[Any] = []
            for item in value:
                if isinstance(item, str):
                    cleaned.append(_sanitize_text(item))
                elif _is_safe_primitive(item):
                    cleaned.append(item)
                elif isinstance(item, dict):
                    cleaned.append(_sanitize_details(item))
                else:
                    cleaned.append("An internal error occurred")
            out[safe_key] = cleaned
        else:
            out[safe_key] = "An internal error occurred"
    return out


class AgentRegistryError(Exception):
    """Base error for the Agent Registry & Factory subsystem."""

    error_code: str = "AGENT_REGISTRY_ERROR"

    def __init__(
        self,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        safe_message = _sanitize_text(message)
        super().__init__(safe_message)
        self.message = safe_message
        self.details = _sanitize_details(details)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-safe representation of the error."""
        return {
            "error_code": self.error_code,
            "message": self.message,
            "details": self.details,
        }


# ── Registry validation errors ───────────────────────────────────────────────


class AgentRegistryValidationError(AgentRegistryError):
    error_code = "AGENT_REGISTRY_VALIDATION_ERROR"


class AgentRegistryConflictError(AgentRegistryError):
    error_code = "AGENT_REGISTRY_CONFLICT"


class AgentRegistryNotFoundError(AgentRegistryError):
    error_code = "AGENT_REGISTRY_NOT_FOUND"


class AgentRegistryDisabledError(AgentRegistryError):
    error_code = "AGENT_REGISTRY_DISABLED"


class AgentRegistryVersionError(AgentRegistryError):
    error_code = "AGENT_REGISTRY_VERSION_ERROR"


class AgentRegistryAliasConflictError(AgentRegistryError):
    error_code = "AGENT_REGISTRY_ALIAS_CONFLICT"


# ── Factory errors ───────────────────────────────────────────────────────────


class AgentFactoryError(AgentRegistryError):
    error_code = "AGENT_FACTORY_ERROR"


class AgentFactoryNotFoundError(AgentFactoryError):
    error_code = "AGENT_FACTORY_NOT_FOUND"


class AgentFactoryCreationError(AgentFactoryError):
    error_code = "AGENT_FACTORY_CREATION_ERROR"


class AgentFactoryCompatibilityError(AgentFactoryError):
    error_code = "AGENT_FACTORY_COMPATIBILITY_ERROR"


# ── Resolution errors ────────────────────────────────────────────────────────


class AgentResolutionError(AgentRegistryError):
    error_code = "AGENT_RESOLUTION_ERROR"


class AgentResolutionNotFoundError(AgentResolutionError):
    error_code = "AGENT_RESOLUTION_NOT_FOUND"


class AgentResolutionAmbiguousError(AgentResolutionError):
    error_code = "AGENT_RESOLUTION_AMBIGUOUS"


# ── Dependency errors ────────────────────────────────────────────────────────


class AgentDependencyUnavailableError(AgentRegistryError):
    error_code = "AGENT_DEPENDENCY_UNAVAILABLE"


__all__ = [
    "AgentDependencyUnavailableError",
    "AgentFactoryCompatibilityError",
    "AgentFactoryCreationError",
    "AgentFactoryError",
    "AgentFactoryNotFoundError",
    "AgentRegistryAliasConflictError",
    "AgentRegistryConflictError",
    "AgentRegistryDisabledError",
    "AgentRegistryError",
    "AgentRegistryNotFoundError",
    "AgentRegistryValidationError",
    "AgentRegistryVersionError",
    "AgentResolutionAmbiguousError",
    "AgentResolutionError",
    "AgentResolutionNotFoundError",
]
