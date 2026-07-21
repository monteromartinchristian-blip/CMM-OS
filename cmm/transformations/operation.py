"""Base contract for language-agnostic transformation operations."""

from __future__ import annotations

from abc import ABC, abstractmethod


class TransformationOperation(ABC):
    """Immutable domain intent that can be adapted into an action."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the stable operation name."""

    @abstractmethod
    def describe(self) -> str:
        """Return a human-readable description of the operation."""

    @abstractmethod
    def metadata(self) -> dict[str, object]:
        """Return serializable operation data."""
