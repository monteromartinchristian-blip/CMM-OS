"""Core data models for language-agnostic transformations."""

from __future__ import annotations

from dataclasses import dataclass

from cmm.transformations.operation import TransformationOperation


@dataclass(frozen=True)
class TransformationStep:
    """One language-agnostic semantic operation in a transformation plan."""

    id: str
    operation: TransformationOperation

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or not self.id.strip():
            raise ValueError("Transformation step id must be a non-empty string.")
        if not isinstance(self.operation, TransformationOperation):
            raise TypeError("Transformation step operation must implement TransformationOperation.")


@dataclass(frozen=True)
class TransformationGraphNode:
    """One transformation node with explicit dependencies in a DAG."""

    step: TransformationStep
    dependencies: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "dependencies", tuple(self.dependencies))
