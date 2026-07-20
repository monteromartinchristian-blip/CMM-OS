"""Indexing boundary for building the CMM OS technical knowledge graph."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from cmm.memory.graph import KnowledgeGraph


@dataclass
class ProjectIndexer:
    """Coordinates future project indexing into a technical knowledge graph."""

    project_root: Path

    def build_empty_graph(self) -> KnowledgeGraph:
        """Create an empty technical knowledge graph without inspecting the project."""

        return KnowledgeGraph()
