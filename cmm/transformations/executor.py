"""Transformation execution contract."""

from __future__ import annotations

from abc import ABC, abstractmethod

from cmm.transformations.graph import TransformationGraph


class TransformationExecutor(ABC):
    """Execute a transformation graph through external semantic executors."""

    @abstractmethod
    def execute(self, graph: TransformationGraph) -> object:
        """Execute ``graph`` and return an implementation-defined result."""
