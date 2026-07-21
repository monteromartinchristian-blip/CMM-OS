"""Extensible semantic context for Python operation executors."""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Mapping, TypeAlias

from cmm.execution.python.python_project_parser import PythonProjectSnapshot

SymbolIndex: TypeAlias = Any
ReferenceIndex: TypeAlias = Any
ImportGraph: TypeAlias = Any
TypeIndex: TypeAlias = Any


@dataclass(frozen=True)
class SemanticContext:
    """Immutable semantic data available to Python operation executors."""

    snapshot: PythonProjectSnapshot
    symbol_index: SymbolIndex | None = None
    reference_index: ReferenceIndex | None = None
    import_graph: ImportGraph | None = None
    type_index: TypeIndex | None = None
    cache: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "cache", MappingProxyType(dict(self.cache)))
