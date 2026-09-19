"""Normalized Computer Use failures. Secret-free by construction."""

from __future__ import annotations

__all__ = ["COMPUTER_ERROR_CODES", "ComputerUseError"]

COMPUTER_ERROR_CODES = frozenset(
    {
        "COMPUTER_RUNTIME_UNAVAILABLE",
        "COMPUTER_PERMISSION_DENIED",
        "COMPUTER_TARGET_UNAVAILABLE",
        "ACTION_FAILED",
        "APPROVAL_REJECTED",
        "CAPABILITY_UNSUPPORTED",
        "CANCELLED",
    }
)


class ComputerUseError(Exception):
    """One normalized computer-use failure with a stable product code."""

    def __init__(self, message: str, *, code: str, detail: str = "") -> None:
        if code not in COMPUTER_ERROR_CODES:
            raise ValueError(f"unknown computer use error code: {code}")
        super().__init__(message)
        self.message = message
        self.code = code
        self.detail = detail
