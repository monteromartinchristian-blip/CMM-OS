"""Unit tests for ValidationExitCode values and contracts (Phase 7.12)."""

from __future__ import annotations

from cmm.validation import ValidationExitCode


def test_validation_exit_code_values() -> None:
    assert ValidationExitCode.SUCCESS == 0
    assert ValidationExitCode.VALIDATION_FAILED == 1
    assert ValidationExitCode.INVALID_USAGE == 2
    assert ValidationExitCode.NOT_FOUND == 3
    assert ValidationExitCode.CONFIGURATION_ERROR == 4
    assert ValidationExitCode.INTERNAL_ERROR == 5
    assert ValidationExitCode.CANCELLED == 6
    assert ValidationExitCode.TIMEOUT == 7


def test_validation_exit_code_int_compatibility() -> None:
    assert int(ValidationExitCode.SUCCESS) == 0
    assert issubclass(ValidationExitCode, int)
