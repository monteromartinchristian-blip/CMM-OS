"""Persistence boundary for the CMM OS technical knowledge graph."""

from __future__ import annotations

from typing import Protocol

from cmm.memory.graph import KnowledgeGraph


class KnowledgeRepository(Protocol):
    """Storage contract for loading and saving technical knowledge graphs."""

    def load(self) -> KnowledgeGraph:
        """Load the current technical knowledge graph."""

    def save(self, graph: KnowledgeGraph) -> None:
        """Persist a technical knowledge graph."""
