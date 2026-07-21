"""Public technical memory facade for CMM OS."""

from __future__ import annotations

from pathlib import Path
from time import perf_counter
from typing import Optional, Union

from cmm.memory.graph import KnowledgeGraph
from cmm.memory.indexer import ProjectIndexer
from cmm.memory.models import KnowledgeNode
from cmm.memory.persistence import (
    CorruptRepositoryError,
    IncompatibleRepositoryError,
    PersistentKnowledgeRepository,
    ProjectMismatchError,
    ProjectSnapshot,
    RepositoryNotFoundError,
    compare_snapshots,
    scan_project,
)
from cmm.memory.query import KnowledgeQuery
from cmm.memory.repository import KnowledgeRepository
from cmm.memory.results import MemoryLoadResult, MemoryRefreshResult, ProjectChangeSet


class TechnicalMemory:
    """High-level public facade for accessing technical project knowledge.

    This class serves as the primary entry point for agents interacting with
    the project's technical knowledge graph, hiding internal graph and query
    complexity.
    """

    def __init__(self, repository: KnowledgeRepository | None = None, project_root: Path | None = None) -> None:
        """Initialize TechnicalMemory with a knowledge repository.

        Args:
            repository: A KnowledgeRepository instance used to load the knowledge graph.
        """
        if repository is None:
            if project_root is None:
                raise ValueError("TechnicalMemory requires a repository or project_root.")
            root = Path(project_root).resolve(strict=True)
            repository = PersistentKnowledgeRepository(root / ".cmm" / "memory.json", root)
        self._repository = repository
        requested_root = Path(project_root).resolve(strict=True) if project_root is not None else None
        repository_root = self._repository_root()
        if requested_root is not None and repository_root is not None and requested_root != repository_root:
            raise ProjectMismatchError(
                f"Memory repository belongs to {repository_root}, not {requested_root}."
            )
        self._project_root = requested_root or repository_root
        self._query: Optional[KnowledgeQuery] = None
        self._graph: Optional[KnowledgeGraph] = None
        self._snapshot: Optional[ProjectSnapshot] = None

    @classmethod
    def for_project(cls, project_root: Path) -> "TechnicalMemory":
        """Create a persistent memory facade using the project's local `.cmm` store."""

        return cls(project_root=project_root)

    def load(self) -> MemoryLoadResult:
        """Load persisted knowledge, rebuilding safely when it is absent or invalid."""
        started = perf_counter()
        warnings: list[str] = []
        origin = "persisted"
        rebuilt = False
        persisted = False
        try:
            if hasattr(self._repository, "load_snapshot"):
                graph, snapshot = self._repository.load_snapshot()
                self._snapshot = snapshot
            else:
                graph = self._repository.load()
                self._snapshot = None
                origin = "in_memory"
        except (RepositoryNotFoundError, CorruptRepositoryError, IncompatibleRepositoryError) as error:
            if self._project_root is None:
                raise
            graph = ProjectIndexer(self._project_root).build()
            snapshot = scan_project(self._project_root)
            self._persist(graph, snapshot)
            self._snapshot = snapshot
            origin = "reconstructed"
            rebuilt = True
            persisted = True
            warnings.append(str(error))
        except ProjectMismatchError:
            raise

        self._set_graph(graph)
        return MemoryLoadResult(
            success=True,
            origin=origin,
            persisted=persisted or origin == "persisted",
            rebuilt=rebuilt,
            warnings=tuple(warnings),
            duration_seconds=perf_counter() - started,
        )

    def refresh(self) -> MemoryRefreshResult:
        """Detect project changes, rebuild safely, and persist the current graph."""
        started = perf_counter()
        if self._query is None:
            self.load()
        if self._project_root is None:
            return MemoryRefreshResult(False, ProjectChangeSet(), errors=("Memory has no project root.",), duration_seconds=perf_counter() - started)
        current = scan_project(self._project_root)
        changes = compare_snapshots(self._snapshot, current)
        if changes.empty:
            return MemoryRefreshResult(True, changes, persisted=False, duration_seconds=perf_counter() - started)

        previous_nodes = set(self._graph.nodes) if self._graph is not None else set()
        graph = ProjectIndexer(self._project_root).build()
        current_nodes = set(graph.nodes)
        self._persist(graph, current)
        self._snapshot = current
        self._set_graph(graph)
        return MemoryRefreshResult(
            success=True,
            change_set=changes,
            nodes_added=tuple(sorted(current_nodes - previous_nodes)),
            nodes_modified=tuple(sorted(current_nodes & previous_nodes)),
            nodes_deleted=tuple(sorted(previous_nodes - current_nodes)),
            persisted=True,
            rebuilt=True,
            duration_seconds=perf_counter() - started,
        )

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

    def _set_graph(self, graph: KnowledgeGraph) -> None:
        self._graph = graph
        if self._project_root is None:
            project_nodes = [node for node in graph.nodes.values() if node.kind == "Project" and node.source_path is not None]
            if project_nodes:
                self._project_root = Path(project_nodes[0].source_path).resolve(strict=False)
        self._query = KnowledgeQuery(graph)

    def _persist(self, graph: KnowledgeGraph, snapshot: ProjectSnapshot) -> None:
        save_snapshot = getattr(self._repository, "save_snapshot", None)
        if callable(save_snapshot):
            save_snapshot(graph, snapshot)
        else:
            self._repository.save(graph)

    def _repository_root(self) -> Optional[Path]:
        root = getattr(self._repository, "project_root", None)
        if root is not None:
            return Path(root).resolve(strict=False)
        return None

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
