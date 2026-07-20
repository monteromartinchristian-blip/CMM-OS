"""Domain models for the CMM OS technical knowledge graph."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping, Optional


@dataclass(frozen=True)
class KnowledgeNode:
    """A knowledge graph unit that can represent code, docs, or decisions."""

    identifier: str
    title: str
    kind: str
    summary: str = ""
    source_path: Optional[Path] = None
    metadata: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class KnowledgeEdge:
    """A typed relationship between two knowledge graph nodes."""

    source_id: str
    target_id: str
    relation: str
    metadata: Mapping[str, str] = field(default_factory=dict)
