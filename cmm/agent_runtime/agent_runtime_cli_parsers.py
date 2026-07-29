"""Phase 9.22 – Agent Runtime CLI Parsers.

Small, explicit, independently-testable parsing functions used by the CLI
argument layer. None of these use ``eval``, ``exec``, ``literal_eval``,
``pickle`` or unsafe YAML loading. Every function fails closed: on any
doubt about safety, it raises rather than returning a best-effort value.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from cmm.agent_runtime.agent_runtime_cli_errors import (
    AgentRuntimeCliParsingError,
    AgentRuntimeCliSecurityError,
    AgentRuntimeCliValidationError,
)

# ── Shared safety constants ─────────────────────────────────────────────────

MAX_INLINE_JSON_BYTES = 64 * 1024
MAX_JSON_FILE_BYTES = 5 * 1024 * 1024
MAX_METADATA_VALUE_BYTES = 4 * 1024
MAX_IDENTIFIER_LENGTH = 256

_FORBIDDEN_SUBSTRINGS = (
    "chain_of_thought",
    "internal_reasoning",
    "private_prompt",
    "password",
    "token",
    "api_key",
    "bearer",
    "private_key",
    "secret",
    "credential",
    "authorization",
    "refresh_token",
    "access_token",
)

_FORBIDDEN_CODE_MARKERS = (
    "eval(",
    "exec(",
    "subprocess",
    "__import__",
    "os.system",
    "pickle",
)

_IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z0-9_.:\-]+$")
_PERMISSION_PATTERN = re.compile(r"^[a-z][a-z0-9_]*:[a-z][a-z0-9_]*$")


def _reject_unsafe_blob(blob: str, *, on: str) -> None:
    lowered = blob.lower()
    for marker in _FORBIDDEN_SUBSTRINGS:
        if marker in lowered:
            raise AgentRuntimeCliSecurityError(
                f"{on} contains a restricted field name: {marker}"
            )
    for marker in _FORBIDDEN_CODE_MARKERS:
        if marker in lowered:
            raise AgentRuntimeCliSecurityError(f"{on} contains disallowed content")


def _reject_unsafe_json_value(value: Any, *, on: str) -> None:
    """Recursively reject forbidden keys/content inside a decoded JSON value."""
    if isinstance(value, dict):
        for key, nested in value.items():
            lowered_key = str(key).lower()
            if any(marker in lowered_key for marker in _FORBIDDEN_SUBSTRINGS):
                raise AgentRuntimeCliSecurityError(
                    f"{on} contains a restricted field name: {key}"
                )
            _reject_unsafe_json_value(nested, on=on)
    elif isinstance(value, list):
        for item in value:
            _reject_unsafe_json_value(item, on=on)
    elif isinstance(value, str):
        _reject_unsafe_blob(value, on=on)


# ── JSON ─────────────────────────────────────────────────────────────────


def parse_json_inline(text: str) -> dict[str, Any]:
    """Parse a JSON object passed inline on the command line.

    Rejects non-object top-level values, oversized input and forbidden
    field names/content. Never uses ``eval``/``literal_eval``.
    """
    if text is None:
        raise AgentRuntimeCliParsingError("payload must not be empty")
    encoded = text.encode("utf-8", errors="strict")
    if len(encoded) > MAX_INLINE_JSON_BYTES:
        raise AgentRuntimeCliParsingError("payload exceeds the maximum inline size")
    try:
        value = json.loads(text)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise AgentRuntimeCliParsingError("payload is not valid JSON") from exc
    if not isinstance(value, dict):
        raise AgentRuntimeCliParsingError("payload must be a JSON object")
    _reject_unsafe_json_value(value, on="payload")
    return value


def parse_json_file(
    path_text: str, *, max_bytes: int = MAX_JSON_FILE_BYTES
) -> dict[str, Any]:
    """Parse a JSON object from a file, with the same safety rules as
    ``parse_json_inline`` plus filesystem-specific limits."""
    if not path_text or not path_text.strip():
        raise AgentRuntimeCliParsingError("payload file path must not be empty")
    path = Path(path_text).expanduser()
    try:
        resolved = path.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise AgentRuntimeCliParsingError("payload file does not exist") from exc
    if not resolved.is_file():
        raise AgentRuntimeCliParsingError("payload file is not a regular file")
    try:
        size = resolved.stat().st_size
    except OSError as exc:
        raise AgentRuntimeCliParsingError("payload file could not be read") from exc
    if size > max_bytes:
        raise AgentRuntimeCliParsingError("payload file exceeds the maximum size")
    try:
        text = resolved.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise AgentRuntimeCliParsingError("payload file could not be read") from exc
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        raise AgentRuntimeCliParsingError("payload file is not valid JSON") from exc
    if not isinstance(value, dict):
        raise AgentRuntimeCliParsingError("payload file must contain a JSON object")
    _reject_unsafe_json_value(value, on="payload file")
    return value


# ── Metadata ─────────────────────────────────────────────────────────────


def parse_metadata(pairs: list[str] | None) -> dict[str, str]:
    """Parse repeated ``key=value`` metadata options into a dict.

    Rejects empty keys, sensitive keys, oversized values and conflicting
    duplicates (same key, different value).
    """
    result: dict[str, str] = {}
    for raw in pairs or []:
        if "=" not in raw:
            raise AgentRuntimeCliValidationError("metadata must be in key=value form")
        key, _, value = raw.partition("=")
        key = key.strip()
        if not key:
            raise AgentRuntimeCliValidationError("metadata key must not be empty")
        lowered_key = key.lower()
        if any(marker in lowered_key for marker in _FORBIDDEN_SUBSTRINGS):
            raise AgentRuntimeCliSecurityError(f"metadata key is restricted: {key}")
        if len(value.encode("utf-8")) > MAX_METADATA_VALUE_BYTES:
            raise AgentRuntimeCliValidationError(
                f"metadata value for '{key}' is too large"
            )
        _reject_unsafe_blob(value, on=f"metadata value for '{key}'")
        if key in result and result[key] != value:
            raise AgentRuntimeCliValidationError(
                f"conflicting metadata values for key: {key}"
            )
        result[key] = value
    return result


# ── Permissions ──────────────────────────────────────────────────────────


def parse_permissions(values: list[str] | None) -> frozenset[str]:
    """Parse repeated ``--permission resource:action`` options."""
    permissions: set[str] = set()
    for raw in values or []:
        candidate = raw.strip()
        if not candidate or not _PERMISSION_PATTERN.match(candidate):
            raise AgentRuntimeCliValidationError(
                "permission must be in 'resource:action' form"
            )
        permissions.add(candidate)
    return frozenset(permissions)


# ── Timestamps ───────────────────────────────────────────────────────────


def parse_iso_datetime(value: str) -> str:
    """Parse an ISO 8601 timestamp and normalize it to timezone-aware UTC."""
    if not value or not value.strip():
        raise AgentRuntimeCliValidationError("timestamp must not be empty")
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise AgentRuntimeCliValidationError("timestamp is not valid ISO 8601") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat()


# ── Decimal ──────────────────────────────────────────────────────────────


def parse_decimal(value: str, *, positive: bool = False) -> Decimal:
    """Parse a decimal amount. Never uses ``float`` for the parse itself."""
    if value is None or not str(value).strip():
        raise AgentRuntimeCliValidationError("amount must not be empty")
    text = str(value).strip()
    try:
        parsed = Decimal(text)
    except InvalidOperation as exc:
        raise AgentRuntimeCliValidationError("amount is not a valid decimal") from exc
    if not parsed.is_finite():
        raise AgentRuntimeCliValidationError("amount must be a finite number")
    if positive and parsed <= 0:
        raise AgentRuntimeCliValidationError("amount must be positive")
    return parsed


# ── Identifiers ──────────────────────────────────────────────────────────


def parse_identifier(value: str, *, field_name: str = "id") -> str:
    """Parse a resource identifier: non-empty, bounded, no path separators."""
    if value is None or not str(value).strip():
        raise AgentRuntimeCliValidationError(f"{field_name} must not be empty")
    text = str(value).strip()
    if len(text) > MAX_IDENTIFIER_LENGTH:
        raise AgentRuntimeCliValidationError(f"{field_name} is too long")
    if "/" in text or "\\" in text or ".." in text or "\x00" in text:
        raise AgentRuntimeCliSecurityError(
            f"{field_name} contains disallowed characters"
        )
    if not _IDENTIFIER_PATTERN.match(text):
        raise AgentRuntimeCliValidationError(
            f"{field_name} contains disallowed characters"
        )
    return text


# ── Enums ────────────────────────────────────────────────────────────────


def parse_enum(
    value: str, allowed: frozenset[str], *, field_name: str = "value"
) -> str:
    """Validate a free-form string against an allowed set of values."""
    if value is None:
        raise AgentRuntimeCliValidationError(f"{field_name} must not be empty")
    if value not in allowed:
        choices = ", ".join(sorted(allowed))
        raise AgentRuntimeCliValidationError(f"{field_name} must be one of: {choices}")
    return value


_OUTPUT_FORMATS = frozenset({"human", "json", "jsonl", "quiet"})


def parse_output_format(value: str) -> str:
    return parse_enum(value, _OUTPUT_FORMATS, field_name="--output")


# ── Pagination ───────────────────────────────────────────────────────────


def parse_limit(value: str, *, minimum: int = 1, maximum: int = 500) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise AgentRuntimeCliValidationError("limit must be an integer") from exc
    if not (minimum <= parsed <= maximum):
        raise AgentRuntimeCliValidationError(
            f"limit must be between {minimum} and {maximum}"
        )
    return parsed


def parse_cursor(value: str) -> str:
    if value is None or not str(value).strip():
        raise AgentRuntimeCliValidationError("cursor must not be empty")
    text = str(value).strip()
    if len(text) > MAX_IDENTIFIER_LENGTH:
        raise AgentRuntimeCliValidationError("cursor is too long")
    if "\x00" in text:
        raise AgentRuntimeCliSecurityError("cursor contains disallowed characters")
    return text


__all__ = [
    "MAX_INLINE_JSON_BYTES",
    "MAX_JSON_FILE_BYTES",
    "MAX_METADATA_VALUE_BYTES",
    "parse_cursor",
    "parse_decimal",
    "parse_enum",
    "parse_identifier",
    "parse_iso_datetime",
    "parse_json_file",
    "parse_json_inline",
    "parse_limit",
    "parse_metadata",
    "parse_output_format",
    "parse_permissions",
]
