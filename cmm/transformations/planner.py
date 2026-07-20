"""Transformation graph planning contract."""

from __future__ import annotations

from abc import ABC, abstractmethod

from cmm.transformations.graph import TransformationGraph
from cmm.transformations.plan import TransformationPlan


class TransformationPlanner(ABC):
    """Convert a transformation plan into a dependency graph."""

    @abstractmethod
    def build_graph(self, plan: TransformationPlan) -> TransformationGraph:
        """Build a transformation graph from a non-executing transformation plan."""
