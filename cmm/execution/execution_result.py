"""Results returned by primitive operation executors."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Mapping

from cmm.transformations.operation import TransformationOperation


@dataclass(frozen=True)
class ExecutionResult:
    """Immutable outcome of executing one transformation operation."""

    success: bool
    operation: TransformationOperation
    diagnostics: tuple[str, ...] = ()
    created_paths: tuple[Path, ...] = ()
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "diagnostics", tuple(self.diagnostics))
        object.__setattr__(self, "created_paths", tuple(self.created_paths))
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))
