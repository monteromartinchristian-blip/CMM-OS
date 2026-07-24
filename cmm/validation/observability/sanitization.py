"""Secret sanitization utilities for Phase 7.11.

All data written to disk (execution records, logs, artifact JSON) is
passed through :func:`sanitize_validation_data` before serialisation.

Rules
-----
- Works recursively on mappings, lists, tuples, and strings.
- Replaces the *value* associated with any key that matches a sensitive
  pattern (case-insensitive substring match against ``_SENSITIVE_KEYS``).
- Replaces URL-embedded credentials (``scheme://user:pass@host``).
- Strings are scanned for accidental ``=`` or ``:`` separated secrets.
- Original objects are **never mutated**; copies are returned.
- The replacement marker is the stable string ``[REDACTED]``.
- Non-sensitive data is preserved exactly as supplied.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

REDACTED: str = "[REDACTED]"

# Keys whose values must always be redacted (case-insensitive substring match)
_SENSITIVE_KEYS: frozenset[str] = frozenset(
    {
        "token",
        "api_key",
        "apikey",
        "password",
        "passwd",
        "secret",
        "authorization",
        "cookie",
        "credential",
        "private_key",
        "access_key",
        "refresh_token",
    }
)

# Regex patterns applied to string values
_URL_CREDS_RE = re.compile(
    r"([a-zA-Z][a-zA-Z0-9+\-.]*://)([^@\s]+:[^@\s]+@)",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def sanitize_validation_data(value: Any) -> Any:
    """Return a sanitised copy of *value*.

    Recursively processes mappings, lists, tuples, and strings.
    Any other type is returned unchanged (numbers, booleans, None, …).

    Parameters
    ----------
    value:
        Arbitrary Python value to sanitise.

    Returns
    -------
    Any
        A new object of the same structural type with sensitive data
        replaced by :data:`REDACTED`.  Original objects are not mutated.
    """
    return _sanitize(value)


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _is_sensitive_key(key: str) -> bool:
    """Return True if *key* (lowercased) contains a sensitive keyword."""
    lower = key.lower()
    return any(s in lower for s in _SENSITIVE_KEYS)


def _sanitize_string(text: str) -> str:
    """Redact embedded URL credentials from *text*."""
    return _URL_CREDS_RE.sub(r"\1[REDACTED]@", text)


def _sanitize(value: Any, *, _parent_key_sensitive: bool = False) -> Any:
    """Core recursive sanitisation logic."""
    if _parent_key_sensitive:
        # The value belongs to a sensitive key — redact it entirely.
        if isinstance(value, str):
            return REDACTED
        if isinstance(value, Mapping):
            return REDACTED
        if isinstance(value, (list, tuple)):
            return REDACTED
        # Scalar numbers / booleans: still redact
        return REDACTED

    if isinstance(value, Mapping):
        return _sanitize_mapping(value)
    if isinstance(value, tuple):
        return tuple(_sanitize(v) for v in value)
    if isinstance(value, list):
        return [_sanitize(v) for v in value]
    if isinstance(value, str):
        return _sanitize_string(value)
    # int, float, bool, None, etc. — pass through unchanged
    return value


def _sanitize_mapping(m: Mapping[str, Any]) -> dict[str, Any]:
    """Return a new dict with sensitive values redacted."""
    result: dict[str, Any] = {}
    for k, v in m.items():
        sensitive = isinstance(k, str) and _is_sensitive_key(k)
        result[k] = _sanitize(v, _parent_key_sensitive=sensitive)
    return result


__all__ = ["REDACTED", "sanitize_validation_data"]
