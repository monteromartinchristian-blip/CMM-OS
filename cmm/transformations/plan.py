"""Transformation planning models."""

from __future__ import annotations

from dataclasses import dataclass

from cmm.transformations.models import TransformationStep


@dataclass(frozen=True, kw_only=True)
class TransformationPlan:
    """Versioned, immutable sequence of transformation steps."""

    version: str = "1.0"
    steps: tuple[TransformationStep, ...]
