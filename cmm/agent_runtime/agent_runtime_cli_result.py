"""Phase 9.22 – Agent Runtime CLI Result Contract.

Immutable, defensively-copied result of a single CLI invocation, plus the
single exit-code mapping table used by the whole CLI.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

# ── Exit codes ────────────────────────────────────────────────────────────

EXIT_SUCCESS = 0
EXIT_INTERNAL_ERROR = 1
EXIT_USAGE_ERROR = 2
EXIT_NOT_FOUND = 3
EXIT_CONFLICT = 4
EXIT_PERMISSION_DENIED = 5
EXIT_POLICY_DENIED = 6
EXIT_APPROVAL_REQUIRED = 7
EXIT_BUDGET_EXCEEDED = 8
EXIT_INVALID_STATE = 9
EXIT_UNAVAILABLE = 10
EXIT_INTERRUPTED = 130

VALID_EXIT_CODES = frozenset(
    {
        EXIT_SUCCESS,
        EXIT_INTERNAL_ERROR,
        EXIT_USAGE_ERROR,
        EXIT_NOT_FOUND,
        EXIT_CONFLICT,
        EXIT_PERMISSION_DENIED,
        EXIT_POLICY_DENIED,
        EXIT_APPROVAL_REQUIRED,
        EXIT_BUDGET_EXCEEDED,
        EXIT_INVALID_STATE,
        EXIT_UNAVAILABLE,
        EXIT_INTERRUPTED,
    }
)

# Maps AgentRuntimeApiErrorCode values (str) to CLI exit codes. This is the
# single place that performs this mapping; nothing else in the CLI encodes
# it independently.
_API_ERROR_CODE_TO_EXIT: dict[str, int] = {
    "CONTRACT_ERROR": EXIT_USAGE_ERROR,
    "VALIDATION_ERROR": EXIT_USAGE_ERROR,
    "NOT_FOUND": EXIT_NOT_FOUND,
    "CONFLICT": EXIT_CONFLICT,
    "IDEMPOTENCY_CONFLICT": EXIT_CONFLICT,
    "PERMISSION_DENIED": EXIT_PERMISSION_DENIED,
    "POLICY_DENIED": EXIT_POLICY_DENIED,
    "APPROVAL_REQUIRED": EXIT_APPROVAL_REQUIRED,
    "BUDGET_EXCEEDED": EXIT_BUDGET_EXCEEDED,
    "STATE_ERROR": EXIT_INVALID_STATE,
    "SERIALIZATION_ERROR": EXIT_INTERNAL_ERROR,
    "UNSUPPORTED_OPERATION": EXIT_USAGE_ERROR,
    "INTERNAL_ERROR": EXIT_INTERNAL_ERROR,
    "UNAVAILABLE": EXIT_UNAVAILABLE,
}


def map_api_error_to_exit_code(error_code: str | None) -> int:
    """Map an ``AgentRuntimeApiErrorCode`` value to a CLI exit code.

    Unknown/unrecognized codes fall back to the general internal-failure
    exit code rather than raising, since this runs on the response path and
    must never itself become a new source of failure.
    """
    if not error_code:
        return EXIT_INTERNAL_ERROR
    return _API_ERROR_CODE_TO_EXIT.get(str(error_code), EXIT_INTERNAL_ERROR)


def _freeze(value: Any) -> Any:
    """Recursively convert dict/list into read-only Mapping/Sequence.

    Applied to ``data``/``error`` so a caller holding a ``AgentRuntimeCliResult``
    can never mutate CLI-internal state through a nested container.
    """
    if isinstance(value, Mapping):
        return MappingProxyType({k: _freeze(v) for k, v in value.items()})
    if isinstance(value, (list, tuple)) and not isinstance(value, (str, bytes)):
        return tuple(_freeze(v) for v in value)
    return value


@dataclass(frozen=True)
class AgentRuntimeCliResult:
    """Immutable outcome of a single CLI invocation."""

    exit_code: int
    stdout: str
    stderr: str
    request_id: str | None
    operation: str | None
    status: str
    data: Mapping[str, Any] | Sequence[Any] | None = None
    error: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        if (
            not isinstance(self.exit_code, int)
            or self.exit_code not in VALID_EXIT_CODES
        ):
            raise ValueError(f"invalid CLI exit code: {self.exit_code!r}")
        if not isinstance(self.stdout, str):
            raise TypeError("stdout must be a string")
        if not isinstance(self.stderr, str):
            raise TypeError("stderr must be a string")
        object.__setattr__(self, "data", _freeze(self.data))
        object.__setattr__(self, "error", _freeze(self.error))


__all__ = [
    "EXIT_APPROVAL_REQUIRED",
    "EXIT_BUDGET_EXCEEDED",
    "EXIT_CONFLICT",
    "EXIT_INTERNAL_ERROR",
    "EXIT_INTERRUPTED",
    "EXIT_INVALID_STATE",
    "EXIT_NOT_FOUND",
    "EXIT_PERMISSION_DENIED",
    "EXIT_POLICY_DENIED",
    "EXIT_SUCCESS",
    "EXIT_UNAVAILABLE",
    "EXIT_USAGE_ERROR",
    "VALID_EXIT_CODES",
    "AgentRuntimeCliResult",
    "map_api_error_to_exit_code",
]
