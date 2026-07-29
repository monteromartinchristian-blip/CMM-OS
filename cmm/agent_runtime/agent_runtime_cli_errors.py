"""Phase 9.22 – Agent Runtime CLI Error Hierarchy.

CLI-local error types, distinct from ``agent_runtime_api_errors``. These
represent failures in the transport layer itself (bad arguments, unsafe
input, unreadable config) rather than application-level API errors, which
already carry their own ``AgentRuntimeApiException`` hierarchy and are
mapped to exit codes via ``map_api_error_to_exit_code``.

No message here may contain a traceback, a filesystem path outside the
user's own input, or secret material. Messages are short, CLI-authored
strings only.
"""

from __future__ import annotations

from typing import Any


class AgentRuntimeCliError(Exception):
    """Base class for all Agent Runtime CLI errors."""

    exit_code: int = 1

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class AgentRuntimeCliUsageError(AgentRuntimeCliError):
    """The command line was well-formed JSON/argparse-wise but not usable:
    missing required actor/permission, incompatible flags, etc."""

    exit_code = 2


class AgentRuntimeCliValidationError(AgentRuntimeCliError):
    """A value failed validation (bad enum, bad range, empty field)."""

    exit_code = 2


class AgentRuntimeCliConfigError(AgentRuntimeCliError):
    """The config file is missing, unreadable, too large, or invalid."""

    exit_code = 2


class AgentRuntimeCliParsingError(AgentRuntimeCliError):
    """Inline or file-based JSON/metadata could not be parsed safely."""

    exit_code = 2


class AgentRuntimeCliFormattingError(AgentRuntimeCliError):
    """A response could not be safely rendered by the selected formatter."""

    exit_code = 1


class AgentRuntimeCliOutputError(AgentRuntimeCliError):
    """Writing CLI output (e.g. an export file) failed."""

    exit_code = 1


class AgentRuntimeCliSecurityError(AgentRuntimeCliError):
    """A request would violate a security invariant (path traversal, unsafe
    overwrite, disallowed content) and was rejected before execution."""

    exit_code = 2


class AgentRuntimeCliUnavailableError(AgentRuntimeCliError):
    """A required dependency (e.g. the API service) is not available."""

    exit_code = 10


__all__ = [
    "AgentRuntimeCliConfigError",
    "AgentRuntimeCliError",
    "AgentRuntimeCliFormattingError",
    "AgentRuntimeCliOutputError",
    "AgentRuntimeCliParsingError",
    "AgentRuntimeCliSecurityError",
    "AgentRuntimeCliUnavailableError",
    "AgentRuntimeCliUsageError",
    "AgentRuntimeCliValidationError",
]
