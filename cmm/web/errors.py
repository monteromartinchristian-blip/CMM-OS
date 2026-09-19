"""Normalized web-capability failures. Secret-free by construction."""

from __future__ import annotations

__all__ = ["WEB_ERROR_CODES", "WebCapabilityError"]

WEB_ERROR_CODES = frozenset(
    {
        "SEARCH_BACKEND_UNAVAILABLE",
        "SEARCH_TIMEOUT",
        "SEARCH_BLOCKED",
        "FETCH_FAILED",
        "SOURCE_BLOCKED",
        "CAPABILITY_UNSUPPORTED",
        "CANCELLED",
    }
)


class WebCapabilityError(Exception):
    """One normalized web-capability failure with a stable product code."""

    def __init__(self, message: str, *, code: str) -> None:
        if code not in WEB_ERROR_CODES:
            raise ValueError(f"unknown web capability error code: {code}")
        super().__init__(message)
        self.message = message
        self.code = code
