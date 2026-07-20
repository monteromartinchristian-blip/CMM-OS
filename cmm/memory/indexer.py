"""Indexing boundary for building the CMM OS technical knowledge graph."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from kernel.services.project_analyzer import ProjectAnalyzer
from kernel.services.python_index import PythonIndex

from cmm.memory.graph import KnowledgeGraph
from cmm.memory.models import KnowledgeEdge, KnowledgeNode


CONTAINS = "CONTAINS"


@dataclass
class ProjectIndexer:
    """Build a structural knowledge graph for a Python project."""

    project_root: Path

    def build(self) -> KnowledgeGraph:
        """Build a knowledge graph containing project, module, class, and function structure."""

        project_root = Path(self.project_root)
        graph = KnowledgeGraph()
        project_id = self._project_id(project_root)

        graph.add_node(
            KnowledgeNode(
                identifier=project_id,
                title=project_root.name,
                kind="Project",
                source_path=project_root,
            )
        )

        analyzer = ProjectAnalyzer(project_root)
        python_index = PythonIndex()

        for relative_path in analyzer.python_files():
            module_path = project_root / relative_path
            module_index = python_index.index(module_path)
            module_id = self._module_id(relative_path)

            graph.add_node(
                KnowledgeNode(
                    identifier=module_id,
                    title=self._module_name(relative_path),
                    kind="Module",
                    summary=self._optional_text(module_index.get("docstring")),
                    source_path=module_path,
                    metadata={
                        "path": relative_path.as_posix(),
                        "imports": tuple(module_index.get("imports", ())),
                    },
                )
            )
            self._add_contains(graph, project_id, module_id)

            self._add_classes(graph, module_id, module_path, module_index)
            self._add_functions(graph, module_id, module_path, module_index)

        return graph

    def build_empty_graph(self) -> KnowledgeGraph:
        """Create an empty technical knowledge graph without inspecting the project."""

        return KnowledgeGraph()

    def _add_classes(
        self,
        graph: KnowledgeGraph,
        module_id: str,
        module_path: Path,
        module_index: Mapping[str, Any],
    ) -> None:
        for class_index in module_index.get("classes", ()):
            class_name = class_index["name"]
            class_id = self._class_id(module_id, class_name)

            graph.add_node(
                KnowledgeNode(
                    identifier=class_id,
                    title=class_name,
                    kind="Class",
                    summary=self._optional_text(class_index.get("docstring")),
                    source_path=module_path,
                    metadata={
                        "lineno": class_index.get("lineno"),
                        "end_lineno": class_index.get("end_lineno"),
                    },
                )
            )
            self._add_contains(graph, module_id, class_id)

            for method_index in class_index.get("methods", ()):
                method_name = method_index["name"]
                method_id = self._method_id(class_id, method_name)

                graph.add_node(
                    KnowledgeNode(
                        identifier=method_id,
                        title=method_name,
                        kind="Method",
                        summary=self._optional_text(method_index.get("docstring")),
                        source_path=module_path,
                        metadata={
                            "class": class_name,
                            "lineno": method_index.get("lineno"),
                            "end_lineno": method_index.get("end_lineno"),
                        },
                    )
                )
                self._add_contains(graph, class_id, method_id)

    def _add_functions(
        self,
        graph: KnowledgeGraph,
        module_id: str,
        module_path: Path,
        module_index: Mapping[str, Any],
    ) -> None:
        for function_index in module_index.get("functions", ()):
            function_name = function_index["name"]
            function_id = self._function_id(module_id, function_name)

            graph.add_node(
                KnowledgeNode(
                    identifier=function_id,
                    title=function_name,
                    kind="Function",
                    summary=self._optional_text(function_index.get("docstring")),
                    source_path=module_path,
                    metadata={
                        "lineno": function_index.get("lineno"),
                        "end_lineno": function_index.get("end_lineno"),
                    },
                )
            )
            self._add_contains(graph, module_id, function_id)

    def _add_contains(self, graph: KnowledgeGraph, source_id: str, target_id: str) -> None:
        graph.add_edge(
            KnowledgeEdge(
                source_id=source_id,
                target_id=target_id,
                relation=CONTAINS,
            )
        )

    def _project_id(self, project_root: Path) -> str:
        return f"project:{project_root.resolve()}"

    def _module_id(self, relative_path: Path) -> str:
        return f"module:{relative_path.as_posix()}"

    def _class_id(self, module_id: str, class_name: str) -> str:
        return f"{module_id}:class:{class_name}"

    def _function_id(self, module_id: str, function_name: str) -> str:
        return f"{module_id}:function:{function_name}"

    def _method_id(self, class_id: str, method_name: str) -> str:
        return f"{class_id}:method:{method_name}"

    def _module_name(self, relative_path: Path) -> str:
        if relative_path.name == "__init__.py":
            return ".".join(relative_path.parts[:-1]) or "__init__"

        return ".".join(relative_path.with_suffix("").parts)

    def _optional_text(self, value: object) -> str:
        if isinstance(value, str):
            return value

        return ""
