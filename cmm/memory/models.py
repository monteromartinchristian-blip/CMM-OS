"""Domain models for the CMM OS technical knowledge graph."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Mapping, Optional


class RelationType(str, Enum):
    """Supported relationship types in the technical knowledge graph."""

    CONTAINS = "CONTAINS"
    IMPORTS = "IMPORTS"
    INHERITS = "INHERITS"
    CALLS = "CALLS"
    USES = "USES"


@dataclass(frozen=True)
class KnowledgeNode:
    """A knowledge graph unit that can represent code, docs, or decisions."""

    identifier: str
    title: str
    kind: str
    summary: str = ""
    source_path: Optional[Path] = None
    metadata: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class KnowledgeEdge:
    """A typed relationship between two knowledge graph nodes."""

    source_id: str
    target_id: str
    relation: RelationType
    metadata: Mapping[str, object] = field(default_factory=dict)
