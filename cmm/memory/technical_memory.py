"""Public technical memory facade for CMM OS."""

from __future__ import annotations

from typing import Optional, Union

from cmm.memory.models import KnowledgeNode
from cmm.memory.query import KnowledgeQuery
from cmm.memory.repository import KnowledgeRepository


class TechnicalMemory:
    """High-level public facade for accessing technical project knowledge.

    This class serves as the primary entry point for agents interacting with
    the project's technical knowledge graph, hiding internal graph and query
    complexity.
    """

    def __init__(self, repository: KnowledgeRepository) -> None:
        """Initialize TechnicalMemory with a knowledge repository.

        Args:
            repository: A KnowledgeRepository instance used to load the knowledge graph.
        """
        self._repository = repository
        self._query: Optional[KnowledgeQuery] = None

    def load(self) -> None:
        """Load the technical knowledge graph from the underlying repository."""
        graph = self._repository.load()
        self._query = KnowledgeQuery(graph)

    def _get_query(self) -> KnowledgeQuery:
        """Ensure the knowledge graph is loaded and return the active query interface.

        Returns:
            The initialized KnowledgeQuery instance.

        Raises:
            RuntimeError: If TechnicalMemory has not been loaded via load() yet.
        """
        if self._query is None:
            raise RuntimeError("TechnicalMemory is not loaded. Call load() before querying.")
        return self._query

    def find_symbol(self, name: str) -> list[KnowledgeNode]:
        """Locate modules, classes, functions, or methods by display name.

        Args:
            name: The display name of the symbol to find.

        Returns:
            A list of matching KnowledgeNode instances representing modules, classes,
            functions, or methods.
        """
        query = self._get_query()
        matching_nodes = query.find_nodes(name=name)
        allowed_kinds = {"Module", "Class", "Function", "Method"}
        return [node for node in matching_nodes if node.kind in allowed_kinds]

    def find_module(self, name: str) -> Optional[KnowledgeNode]:
        """Find a module node by module name.

        Args:
            name: The display name of the module.

        Returns:
            The matching KnowledgeNode if found, or None otherwise.
        """
        return self._get_query().find_module(name)

    def find_class(self, name: str) -> Optional[KnowledgeNode]:
        """Find a class node by class name.

        Args:
            name: The display name of the class.

        Returns:
            The matching KnowledgeNode if found, or None otherwise.
        """
        return self._get_query().find_class(name)

    def find_function(self, name: str) -> Optional[KnowledgeNode]:
        """Find a function node by function name.

        Args:
            name: The display name of the function.

        Returns:
            The matching KnowledgeNode if found, or None otherwise.
        """
        return self._get_query().find_function(name)

    def find_method(self, name: str) -> Optional[KnowledgeNode]:
        """Find a method node by method name.

        Args:
            name: The display name of the method.

        Returns:
            The matching KnowledgeNode if found, or None otherwise.
        """
        return self._get_query().find_method(name)

    def find_callers(self, symbol: Union[str, KnowledgeNode]) -> list[KnowledgeNode]:
        """Find functions or methods that call the specified symbol.

        Args:
            symbol: Either the stable identifier of a node or a KnowledgeNode instance.

        Returns:
            A list of KnowledgeNode instances representing calling functions or methods.
        """
        return self._get_query().callers(symbol)

    def find_callees(self, symbol: Union[str, KnowledgeNode]) -> list[KnowledgeNode]:
        """Find functions or methods called by the specified symbol.

        Args:
            symbol: Either the stable identifier of a node or a KnowledgeNode instance.

        Returns:
            A list of KnowledgeNode instances representing called functions or methods.
        """
        return self._get_query().callees(symbol)

    def find_parents(self, symbol: Union[str, KnowledgeNode]) -> list[KnowledgeNode]:
        """Find symbols that directly contain the specified symbol."""
        return self._get_query().parents(symbol)

    def find_children(self, symbol: Union[str, KnowledgeNode]) -> list[KnowledgeNode]:
        """Find symbols directly contained by the specified symbol."""
        return self._get_query().children(symbol)

    def find_imports(self, symbol: Union[str, KnowledgeNode]) -> list[KnowledgeNode]:
        """Find project modules imported by the specified symbol."""
        return self._get_query().imports(symbol)

    def find_imported_by(self, symbol: Union[str, KnowledgeNode]) -> list[KnowledgeNode]:
        """Find project modules that import the specified symbol."""
        return self._get_query().imported_by(symbol)

    def find_base_classes(self, symbol: Union[str, KnowledgeNode]) -> list[KnowledgeNode]:
        """Find direct base classes of the specified symbol."""
        return self._get_query().inherits_from(symbol)

    def find_derived_classes(self, symbol: Union[str, KnowledgeNode]) -> list[KnowledgeNode]:
        """Find classes that directly inherit from the specified symbol."""
        return self._get_query().derived_classes(symbol)

    def find_uses(self, symbol: Union[str, KnowledgeNode]) -> list[KnowledgeNode]:
        """Find classes directly used by the specified symbol."""
        return self._get_query().uses(symbol)

    def find_used_by(self, symbol: Union[str, KnowledgeNode]) -> list[KnowledgeNode]:
        """Find classes that directly use the specified symbol."""
        return self._get_query().used_by(symbol)

    def search_symbols(self, keyword: str) -> list[KnowledgeNode]:
        """Find supported symbols whose names contain a keyword, ignoring case."""
        normalized_keyword = keyword.lower()
        return [
            node
            for node in self._get_query().find_nodes()
            if node.kind in {"Module", "Class", "Function", "Method"}
            and normalized_keyword in node.title.lower()
        ]

    def project_summary(self) -> dict[str, int]:
        """Return general statistics of the project directly from the KnowledgeGraph.

        Returns:
            A dictionary containing counts for modules, classes, functions,
            methods, and relationships.
        """
        query = self._get_query()
        graph = query.graph

        counts = {
            "modules": 0,
            "classes": 0,
            "functions": 0,
            "methods": 0,
        }

        for node in graph.nodes.values():
            kind_lower = node.kind.lower()
            if kind_lower == "module":
                counts["modules"] += 1
            elif kind_lower == "class":
                counts["classes"] += 1
            elif kind_lower == "function":
                counts["functions"] += 1
            elif kind_lower == "method":
                counts["methods"] += 1

        counts["relationships"] = len(graph.edges)
        return counts
