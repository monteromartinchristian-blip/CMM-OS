"""Graph container for technical knowledge relationships."""

from __future__ import annotations

from dataclasses import dataclass, field

from cmm.memory.models import KnowledgeEdge, KnowledgeNode


@dataclass
class KnowledgeGraph:
    """In-memory representation of technical knowledge nodes and relationships."""

    nodes: dict[str, KnowledgeNode] = field(default_factory=dict)
    edges: list[KnowledgeEdge] = field(default_factory=list)

    def add_node(self, node: KnowledgeNode) -> None:
        """Register a knowledge node by its stable identifier."""

        self.nodes[node.identifier] = node

    def add_edge(self, edge: KnowledgeEdge) -> None:
        """Register a relationship between two knowledge nodes."""

        self.edges.append(edge)
