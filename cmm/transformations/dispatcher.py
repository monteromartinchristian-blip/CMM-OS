"""Dispatcher contract for transformation step execution."""

from __future__ import annotations

from abc import ABC, abstractmethod

from cmm.transformations.models import TransformationStep


class TransformationDispatcher(ABC):
    """Dispatch one transformation step to its concrete runtime implementation."""

    @abstractmethod
    def dispatch(self, step: TransformationStep) -> object:
        """Execute ``step`` and return an implementation-defined result."""
