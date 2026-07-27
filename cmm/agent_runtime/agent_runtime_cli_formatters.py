"""Phase 9.22 – Agent Runtime CLI Formatters.

Renders an ``AgentRuntimeCliResult`` for a chosen output mode. Formatting
is always deterministic (sorted keys, ISO dates, ``Decimal`` as strings,
enum ``.value``) and fail-closed on redaction: anything that cannot be
proven safe is replaced with a placeholder rather than emitted.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import fields, is_dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from types import MappingProxyType
from typing import Any

from cmm.agent_runtime.agent_runtime_cli_result import AgentRuntimeCliResult

# Any dict key matching (case-insensitively) one of these is redacted,
# regardless of nesting depth or which formatter is used.
SENSITIVE_FIELDS = frozenset(
    {
        "chain_of_thought",
        "internal_reasoning",
        "private_prompt",
        "password",
        "token",
        "access_token",
        "refresh_token",
        "api_key",
        "authorization",
        "bearer",
        "private_key",
        "secret",
        "credential",
    }
)

REDACTED = "**REDACTED**"
UNSERIALIZABLE = "**UNSERIALIZABLE**"

_PRIMARY_ID_FIELDS = (
    "goal_id",
    "run_id",
    "approval_id",
    "budget_id",
    "trace_id",
    "event_id",
    "dead_letter_id",
)


def _is_sensitive_key(key: Any) -> bool:
    text = str(key).lower()
    return any(marker in text for marker in SENSITIVE_FIELDS)


def to_serializable(value: Any) -> Any:
    """Recursively convert a value into a JSON-safe, redacted structure.

    Fail-closed: any object this function does not explicitly recognize is
    replaced by a placeholder rather than serialized via ``repr``/``str``,
    since that could leak internal state.
    """
    try:
        return _to_serializable(value)
    except Exception:  # noqa: BLE001 - redaction must fail closed, never crash
        return UNSERIALIZABLE


def _to_serializable(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, bool)):
        return value
    if isinstance(value, float):
        return str(Decimal(str(value)))
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, (Mapping, MappingProxyType)):
        return {
            str(k): (REDACTED if _is_sensitive_key(k) else _to_serializable(v))
            for k, v in value.items()
        }
    if is_dataclass(value) and not isinstance(value, type):
        return {
            f.name: (
                REDACTED
                if _is_sensitive_key(f.name)
                else _to_serializable(getattr(value, f.name))
            )
            for f in fields(value)
        }
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_to_serializable(v) for v in value]
    if isinstance(value, (bytes, bytearray)):
        return UNSERIALIZABLE
    # Unknown object type: fail closed rather than falling back to repr/str.
    return UNSERIALIZABLE


def _plain(value: Any) -> Any:
    """Convert frozen Mapping/tuple containers (as stored on a Result) back
    into plain dict/list so ``json.dumps`` can render them directly."""
    if isinstance(value, (Mapping, MappingProxyType)):
        return {str(k): _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    return value


def _human_lines(value: Any, *, indent: int = 0) -> list[str]:
    pad = "  " * indent
    lines: list[str] = []
    if isinstance(value, (Mapping, MappingProxyType)):
        for key in sorted(value.keys(), key=str):
            child = value[key]
            if isinstance(child, (Mapping, MappingProxyType)) or (
                isinstance(child, (list, tuple)) and child
            ):
                lines.append(f"{pad}{key}:")
                lines.extend(_human_lines(child, indent=indent + 1))
            else:
                lines.append(f"{pad}{key}: {_human_scalar(child)}")
    elif isinstance(value, (list, tuple)):
        if not value:
            lines.append(f"{pad}(none)")
        for i, item in enumerate(value):
            if isinstance(item, (Mapping, MappingProxyType, list, tuple)):
                lines.append(f"{pad}- [{i}]")
                lines.extend(_human_lines(item, indent=indent + 1))
            else:
                lines.append(f"{pad}- {_human_scalar(item)}")
    else:
        lines.append(f"{pad}{_human_scalar(value)}")
    return lines


def _human_scalar(value: Any) -> str:
    if value is None:
        return "(none)"
    if isinstance(value, bool):
        return "yes" if value else "no"
    return str(value)


class HumanFormatter:
    """Readable, dependency-free plain-text formatter."""

    def format(self, result: AgentRuntimeCliResult) -> str:
        lines: list[str] = []
        if result.error is not None:
            code = result.error.get("code", "ERROR")
            message = result.error.get("message", "An error occurred")
            lines.append(f"Error [{code}]: {message}")
            details = result.error.get("details")
            if details:
                lines.extend(_human_lines(details, indent=1))
            return "\n".join(lines)

        lines.append(f"Status: {result.status}")
        if result.operation:
            lines.append(f"Operation: {result.operation}")
        if result.request_id:
            lines.append(f"Request ID: {result.request_id}")
        if result.data is not None:
            lines.extend(_human_lines(result.data))
        return "\n".join(lines)


class JsonFormatter:
    """Deterministic, always-valid JSON formatter."""

    def format(self, result: AgentRuntimeCliResult) -> str:
        payload = {
            "status": result.status,
            "operation": result.operation,
            "request_id": result.request_id,
            "data": _plain(result.data),
            "error": _plain(result.error),
        }
        return json.dumps(
            payload,
            sort_keys=True,
            ensure_ascii=True,
            default=lambda _obj: UNSERIALIZABLE,
        )


class JsonLinesFormatter:
    """Single-line-per-record JSON formatter, used by ``batch``."""

    def format(self, result: AgentRuntimeCliResult) -> str:
        payload = {
            "status": result.status,
            "operation": result.operation,
            "request_id": result.request_id,
            "data": _plain(result.data),
            "error": _plain(result.error),
        }
        return json.dumps(
            payload,
            sort_keys=True,
            ensure_ascii=True,
            separators=(",", ":"),
            default=lambda _obj: UNSERIALIZABLE,
        )


class QuietFormatter:
    """Minimal-output formatter: the single most useful value, nothing more."""

    def format(self, result: AgentRuntimeCliResult) -> str:
        if result.error is not None:
            code = result.error.get("code", "ERROR")
            message = result.error.get("message", "An error occurred")
            return f"{code}: {message}"
        data = result.data
        if isinstance(data, (Mapping, MappingProxyType)):
            for field_name in _PRIMARY_ID_FIELDS:
                if field_name in data:
                    return str(data[field_name])
            if "total" in data:
                return str(data["total"])
            if "status" in data:
                return str(data["status"])
            return ""
        if isinstance(data, (list, tuple)):
            return str(len(data))
        if data is None:
            return ""
        return str(data)


__all__ = [
    "REDACTED",
    "SENSITIVE_FIELDS",
    "UNSERIALIZABLE",
    "HumanFormatter",
    "JsonFormatter",
    "JsonLinesFormatter",
    "QuietFormatter",
    "to_serializable",
]
