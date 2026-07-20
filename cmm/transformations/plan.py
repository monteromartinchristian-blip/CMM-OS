"""Transformation planning models."""

from __future__ import annotations

from dataclasses import dataclass

from cmm.transformations.models import TransformationStep


@dataclass(frozen=True)
class TransformationPlan:
    """Ordered, non-executing plan for a high-level transformation goal."""

    goal: str
    steps: list[TransformationStep]
