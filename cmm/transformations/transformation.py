"""Abstract transformation contract."""

from __future__ import annotations

from abc import ABC, abstractmethod

from cmm.transformations.plan import TransformationPlan


class Transformation(ABC):
    """Language-agnostic transformation capable of producing a plan."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the transformation's stable name."""

    @abstractmethod
    def create_plan(self, goal: str) -> TransformationPlan:
        """Create a deterministic transformation plan for ``goal``."""
