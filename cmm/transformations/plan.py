"""Transformation planning models."""

from __future__ import annotations

from dataclasses import dataclass

from cmm.transformations.models import TransformationStep
from cmm.transformations.preconditions import TransformationPrecondition


@dataclass(frozen=True, kw_only=True)
class TransformationPlan:
    """Versioned, immutable sequence of transformation steps."""

    id: str = "transformation-plan"
    version: str = "1.0"
    steps: tuple[TransformationStep, ...]
    preconditions: tuple[TransformationPrecondition, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "steps", tuple(self.steps))
        object.__setattr__(self, "preconditions", tuple(self.preconditions))
