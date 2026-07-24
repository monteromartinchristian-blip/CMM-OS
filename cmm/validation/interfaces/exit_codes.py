"""Stable exit codes for CMM OS Validation (Phase 7.12)."""

from __future__ import annotations

from enum import IntEnum


class ValidationExitCode(IntEnum):
    """Public stable exit codes for validation CLI and CI integration."""

    SUCCESS = 0
    """All validation checks passed and gate allowed (if evaluated)."""

    VALIDATION_FAILED = 1
    """Validation failed or commit gate rejected."""

    INVALID_USAGE = 2
    """Invalid command usage or arguments."""

    NOT_FOUND = 3
    """Requested resource or validation execution not found."""

    CONFIGURATION_ERROR = 4
    """Configuration error (e.g. unknown policy or step)."""

    INTERNAL_ERROR = 5
    """Internal system or persistence error."""

    CANCELLED = 6
    """Execution was cancelled."""

    TIMEOUT = 7
    """Execution timed out."""


__all__ = ["ValidationExitCode"]
