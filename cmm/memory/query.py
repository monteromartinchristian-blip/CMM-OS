"""Query API for CMM OS technical knowledge graphs."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Optional, Union

from cmm.memory.graph import KnowledgeGraph
from cmm.memory.models import KnowledgeEdge, KnowledgeNode, RelationType


NodeRef = Union[str, KnowledgeNode]


@dataclass
class KnowledgeQuery:
    """Typed read-only query helper for a populated knowledge graph."""

    graph: KnowledgeGraph
    _outgoing: dict[str, list[KnowledgeEdge]] = field(init=False, repr=False)
    _incoming: dict[str, list[KnowledgeEdge]] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._outgoing = {}
        self._incoming = {}

        for edge in self.graph.edges:
            self._outgoing.setdefault(edge.source_id, []).append(edge)
            self._incoming.setdefault(edge.target_id, []).append(edge)

    def find_node(self, identifier: str) -> Optional[KnowledgeNode]:
        """Find a node by its stable identifier."""

        return self.graph.nodes.get(identifier)

    def find_nodes(
        self,
        node_type: Optional[str] = None,
        name: Optional[str] = None,
    ) -> list[KnowledgeNode]:
        """Find nodes by optional type and display name."""

        nodes = self.graph.nodes.values()

        if node_type is not None:
            nodes = [
                node
                for node in nodes
                if node.kind == node_type
            ]

        if name is not None:
            nodes = [
                node
                for node in nodes
                if node.title == name
            ]

        return list(nodes)

    def find_module(self, name: str) -> Optional[KnowledgeNode]:
        """Find a module node by module name."""

        return self._find_one("Module", name)

    def find_class(self, name: str) -> Optional[KnowledgeNode]:
        """Find a class node by class name."""

        return self._find_one("Class", name)

    def find_function(self, name: str) -> Optional[KnowledgeNode]:
        """Find a function node by function name."""

        return self._find_one("Function", name)

    def find_method(self, name: str) -> Optional[KnowledgeNode]:
        """Find a method node by method name."""

        return self._find_one("Method", name)

    def neighbors(self, node: NodeRef) -> list[KnowledgeNode]:
        """Return nodes connected by incoming or outgoing relationships."""

        resolved = self._resolve_node(node)
        if resolved is None:
            return []

        ids = []
        for edge in self._outgoing.get(resolved.identifier, ()):
            ids.append(edge.target_id)
        for edge in self._incoming.get(resolved.identifier, ()):
            ids.append(edge.source_id)

        return self._nodes_by_id(ids)

    def incoming(self, node: NodeRef) -> list[KnowledgeEdge]:
        """Return incoming relationships for a node."""

        resolved = self._resolve_node(node)
        if resolved is None:
            return []

        return list(self._incoming.get(resolved.identifier, ()))

    def outgoing(self, node: NodeRef) -> list[KnowledgeEdge]:
        """Return outgoing relationships for a node."""

        resolved = self._resolve_node(node)
        if resolved is None:
            return []

        return list(self._outgoing.get(resolved.identifier, ()))

    def relations(
        self,
        node: NodeRef,
        relation_type: Optional[RelationType] = None,
    ) -> list[KnowledgeEdge]:
        """Return all relationships connected to a node, optionally filtered by type."""

        edges = self.incoming(node) + self.outgoing(node)

        if relation_type is None:
            return edges

        return [
            edge
            for edge in edges
            if edge.relation == relation_type
        ]

    def children(self, node: NodeRef) -> list[KnowledgeNode]:
        """Return nodes directly contained by a node."""

        return self._targets(node, RelationType.CONTAINS)

    def parents(self, node: NodeRef) -> list[KnowledgeNode]:
        """Return nodes that directly contain a node."""

        return self._sources(node, RelationType.CONTAINS)

    def descendants(self, node: NodeRef) -> list[KnowledgeNode]:
        """Return nodes transitively contained by a node."""

        return self._walk(node, RelationType.CONTAINS, direction="outgoing")

    def ancestors(self, node: NodeRef) -> list[KnowledgeNode]:
        """Return nodes that transitively contain a node."""

        return self._walk(node, RelationType.CONTAINS, direction="incoming")

    def callers(self, node: NodeRef) -> list[KnowledgeNode]:
        """Return functions or methods that call this node."""

        return self._sources(node, RelationType.CALLS)

    def callees(self, node: NodeRef) -> list[KnowledgeNode]:
        """Return functions or methods called by this node."""

        return self._targets(node, RelationType.CALLS)

    def imports(self, node: NodeRef) -> list[KnowledgeNode]:
        """Return project modules imported by this module."""

        return self._targets(node, RelationType.IMPORTS)

    def imported_by(self, node: NodeRef) -> list[KnowledgeNode]:
        """Return project modules importing this module."""

        return self._sources(node, RelationType.IMPORTS)

    def inherits_from(self, node: NodeRef) -> list[KnowledgeNode]:
        """Return parent classes for this class."""

        return self._targets(node, RelationType.INHERITS)

    def derived_classes(self, node: NodeRef) -> list[KnowledgeNode]:
        """Return classes that inherit from this class."""

        return self._sources(node, RelationType.INHERITS)

    def uses(self, node: NodeRef) -> list[KnowledgeNode]:
        """Return classes used by this class."""

        return self._targets(node, RelationType.USES)

    def used_by(self, node: NodeRef) -> list[KnowledgeNode]:
        """Return classes that use this class."""

        return self._sources(node, RelationType.USES)

    def _find_one(self, node_type: str, name: str) -> Optional[KnowledgeNode]:
        matches = self.find_nodes(node_type=node_type, name=name)
        if not matches:
            return None

        return matches[0]

    def _targets(self, node: NodeRef, relation_type: RelationType) -> list[KnowledgeNode]:
        resolved = self._resolve_node(node)
        if resolved is None:
            return []

        return self._nodes_by_id(
            edge.target_id
            for edge in self._outgoing.get(resolved.identifier, ())
            if edge.relation == relation_type
        )

    def _sources(self, node: NodeRef, relation_type: RelationType) -> list[KnowledgeNode]:
        resolved = self._resolve_node(node)
        if resolved is None:
            return []

        return self._nodes_by_id(
            edge.source_id
            for edge in self._incoming.get(resolved.identifier, ())
            if edge.relation == relation_type
        )

    def _walk(
        self,
        node: NodeRef,
        relation_type: RelationType,
        direction: str,
    ) -> list[KnowledgeNode]:
        resolved = self._resolve_node(node)
        if resolved is None:
            return []

        visited = set()
        results = []
        queue = [resolved.identifier]

        while queue:
            current_id = queue.pop(0)
            edges = (
                self._outgoing.get(current_id, ())
                if direction == "outgoing"
                else self._incoming.get(current_id, ())
            )

            for edge in edges:
                if edge.relation != relation_type:
                    continue

                next_id = edge.target_id if direction == "outgoing" else edge.source_id
                if next_id in visited:
                    continue

                node = self.graph.nodes.get(next_id)
                if node is None:
                    continue

                visited.add(next_id)
                results.append(node)
                queue.append(next_id)

        return results

    def _resolve_node(self, node: NodeRef) -> Optional[KnowledgeNode]:
        if isinstance(node, KnowledgeNode):
            return node

        return self.find_node(node)

    def _nodes_by_id(self, identifiers: Iterable[str]) -> list[KnowledgeNode]:
        nodes = []
        seen = set()

        for identifier in identifiers:
            if identifier in seen:
                continue

            node = self.graph.nodes.get(identifier)
            if node is None:
                continue

            seen.add(identifier)
            nodes.append(node)

        return nodes
