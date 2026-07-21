"""Backend-independent requests for executing transformation operations."""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Mapping

from cmm.transformations.operation import TransformationOperation


@dataclass(frozen=True)
class ExecutionRequest:
    """Immutable request containing an operation and its execution metadata."""

    operation: TransformationOperation
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.operation, TransformationOperation):
            raise TypeError("Execution request operation must implement TransformationOperation.")
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))
