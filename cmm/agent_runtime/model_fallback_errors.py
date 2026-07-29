"""Structured errors for model fallback policy evaluation."""

from __future__ import annotations


class ModelFallbackError(Exception):
    """Base error for invalid or unsafe model fallback contracts."""


class InvalidModelFallbackContractError(ModelFallbackError, ValueError):
    """Raised when a fallback contract violates its invariants."""


class ModelFallbackConflictError(ModelFallbackError):
    """Raised when fallback requirements conflict with inherited constraints."""
