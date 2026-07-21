"""Indexing boundary for building the CMM OS technical knowledge graph."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from kernel.services.project_analyzer import ProjectAnalyzer
from kernel.services.python_index import PythonIndex

from cmm.memory.graph import KnowledgeGraph
from cmm.memory.models import KnowledgeEdge, KnowledgeNode, RelationType


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
        module_indexes = {}
        parse_errors = {}
        for relative_path in analyzer.python_files():
            try:
                module_indexes[relative_path] = python_index.index(project_root / relative_path)
            except (SyntaxError, UnicodeDecodeError) as error:
                module_indexes[relative_path] = {
                    "docstring": None,
                    "imports": (),
                    "import_targets": (),
                    "classes": (),
                    "functions": (),
                }
                parse_errors[relative_path] = str(error)
        module_names = {
            relative_path: self._module_name(relative_path)
            for relative_path in module_indexes
        }
        module_ids = {
            module_name: self._module_id(relative_path)
            for relative_path, module_name in module_names.items()
        }

        for relative_path, module_index in module_indexes.items():
            module_path = project_root / relative_path
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
                        **({"parse_error": parse_errors[relative_path]} if relative_path in parse_errors else {}),
                    },
                )
            )
            self._add_contains(graph, project_id, module_id)

            self._add_classes(graph, module_id, module_path, module_index)
            self._add_functions(graph, module_id, module_path, module_index)

        lookup = self._build_lookup(module_indexes, module_names)

        for relative_path, module_index in module_indexes.items():
            module_name = module_names[relative_path]
            module_id = self._module_id(relative_path)
            aliases = self._import_aliases(relative_path, module_name, module_index, module_ids)

            self._add_imports(graph, relative_path, module_name, module_id, module_index, module_ids)
            self._add_inherits(graph, module_name, module_index, aliases, lookup)
            self._add_calls(graph, module_name, module_index, aliases, lookup)
            self._add_uses(graph, module_name, module_index, aliases, lookup)

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
            self._add_relation(graph, module_id, class_id, RelationType.CONTAINS)

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
                self._add_relation(graph, class_id, method_id, RelationType.CONTAINS)

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
            self._add_relation(graph, module_id, function_id, RelationType.CONTAINS)

    def _add_contains(self, graph: KnowledgeGraph, source_id: str, target_id: str) -> None:
        self._add_relation(graph, source_id, target_id, RelationType.CONTAINS)

    def _add_imports(
        self,
        graph: KnowledgeGraph,
        relative_path: Path,
        module_name: str,
        module_id: str,
        module_index: Mapping[str, Any],
        module_ids: Mapping[str, str],
    ) -> None:
        for import_target in module_index.get("import_targets", ()):
            for imported_module in self._imported_project_modules(
                relative_path,
                module_name,
                import_target,
                module_ids,
            ):
                self._add_relation(
                    graph,
                    module_id,
                    module_ids[imported_module],
                    RelationType.IMPORTS,
                )

    def _add_inherits(
        self,
        graph: KnowledgeGraph,
        module_name: str,
        module_index: Mapping[str, Any],
        aliases: Mapping[str, str],
        lookup: Mapping[str, Any],
    ) -> None:
        module_id = self._lookup_module_id(module_name, lookup)

        for class_index in module_index.get("classes", ()):
            class_id = self._class_id(module_id, class_index["name"])

            for base in class_index.get("bases", ()):
                parent_id = self._resolve_class(base, module_name, aliases, lookup)
                if parent_id and parent_id != class_id:
                    self._add_relation(graph, class_id, parent_id, RelationType.INHERITS)

    def _add_calls(
        self,
        graph: KnowledgeGraph,
        module_name: str,
        module_index: Mapping[str, Any],
        aliases: Mapping[str, str],
        lookup: Mapping[str, Any],
    ) -> None:
        module_id = self._lookup_module_id(module_name, lookup)

        for function_index in module_index.get("functions", ()):
            function_id = self._function_id(module_id, function_index["name"])

            for call in function_index.get("calls", ()):
                target_id = self._resolve_function(call, module_name, aliases, lookup)
                if target_id and target_id != function_id:
                    self._add_relation(graph, function_id, target_id, RelationType.CALLS)

        for class_index in module_index.get("classes", ()):
            class_id = self._class_id(module_id, class_index["name"])

            for method_index in class_index.get("methods", ()):
                method_id = self._method_id(class_id, method_index["name"])

                for call in method_index.get("calls", ()):
                    target_id = self._resolve_method_call(
                        call,
                        module_name,
                        class_id,
                        aliases,
                        lookup,
                    )
                    if target_id and target_id != method_id:
                        self._add_relation(graph, method_id, target_id, RelationType.CALLS)

    def _add_uses(
        self,
        graph: KnowledgeGraph,
        module_name: str,
        module_index: Mapping[str, Any],
        aliases: Mapping[str, str],
        lookup: Mapping[str, Any],
    ) -> None:
        module_id = self._lookup_module_id(module_name, lookup)

        for class_index in module_index.get("classes", ()):
            class_id = self._class_id(module_id, class_index["name"])

            for candidate in class_index.get("uses", ()):
                target_id = self._resolve_class(candidate, module_name, aliases, lookup)
                if target_id and target_id != class_id:
                    self._add_relation(graph, class_id, target_id, RelationType.USES)

    def _add_relation(
        self,
        graph: KnowledgeGraph,
        source_id: str,
        target_id: str,
        relation: RelationType,
    ) -> None:
        if any(
            edge.source_id == source_id
            and edge.target_id == target_id
            and edge.relation == relation
            for edge in graph.edges
        ):
            return

        graph.add_edge(
            KnowledgeEdge(
                source_id=source_id,
                target_id=target_id,
                relation=relation,
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

    def _build_lookup(
        self,
        module_indexes: Mapping[Path, Mapping[str, Any]],
        module_names: Mapping[Path, str],
    ) -> dict[str, object]:
        classes_by_qualified = {}
        classes_by_name: dict[str, list[str]] = {}
        functions_by_qualified = {}
        methods_by_qualified = {}
        module_ids = {}

        for relative_path, module_index in module_indexes.items():
            module_name = module_names[relative_path]
            module_id = self._module_id(relative_path)
            module_ids[module_name] = module_id

            for class_index in module_index.get("classes", ()):
                class_name = class_index["name"]
                class_id = self._class_id(module_id, class_name)
                classes_by_qualified[f"{module_name}.{class_name}"] = class_id
                classes_by_name.setdefault(class_name, []).append(class_id)

                for method_index in class_index.get("methods", ()):
                    method_name = method_index["name"]
                    method_id = self._method_id(class_id, method_name)
                    methods_by_qualified[f"{module_name}.{class_name}.{method_name}"] = method_id

            for function_index in module_index.get("functions", ()):
                function_name = function_index["name"]
                function_id = self._function_id(module_id, function_name)
                functions_by_qualified[f"{module_name}.{function_name}"] = function_id

        return {
            "classes_by_qualified": classes_by_qualified,
            "classes_by_name": classes_by_name,
            "functions_by_qualified": functions_by_qualified,
            "methods_by_qualified": methods_by_qualified,
            "module_ids": module_ids,
        }

    def _lookup_module_id(self, module_name: str, lookup: Mapping[str, Any]) -> str:
        module_ids = lookup["module_ids"]
        if isinstance(module_ids, dict):
            module_id = module_ids.get(module_name)
            if isinstance(module_id, str):
                return module_id

        return f"module:{module_name.replace('.', '/')}.py"

    def _import_aliases(
        self,
        relative_path: Path,
        module_name: str,
        module_index: Mapping[str, Any],
        module_ids: Mapping[str, str],
    ) -> dict[str, str]:
        aliases = {}

        for import_target in module_index.get("import_targets", ()):
            kind = import_target.get("kind")
            module = self._resolve_import_module(relative_path, module_name, import_target)
            name = import_target.get("name")
            asname = import_target.get("asname")

            if kind == "import" and module:
                alias = asname or module.split(".", 1)[0]
                aliases[alias] = module
                aliases[module] = module

            if kind == "from" and module and isinstance(name, str) and name != "*":
                imported_module = f"{module}.{name}" if module else name
                alias = asname or name
                aliases[alias] = imported_module if imported_module in module_ids else f"{module}.{name}"

        return aliases

    def _imported_project_modules(
        self,
        relative_path: Path,
        module_name: str,
        import_target: Mapping[str, Any],
        module_ids: Mapping[str, str],
    ) -> list[str]:
        module = self._resolve_import_module(relative_path, module_name, import_target)
        name = import_target.get("name")
        matches = []

        if module in module_ids:
            matches.append(module)

        if isinstance(name, str) and name != "*":
            imported_module = f"{module}.{name}" if module else name
            if imported_module in module_ids:
                matches.append(imported_module)

        return sorted(set(matches))

    def _resolve_import_module(
        self,
        relative_path: Path,
        module_name: str,
        import_target: Mapping[str, Any],
    ) -> str:
        module = import_target.get("module")
        level = import_target.get("level", 0)

        if not isinstance(module, str):
            module = ""

        if not isinstance(level, int) or level == 0:
            return module

        package_parts = list(module_name.split("."))
        if relative_path.name != "__init__.py":
            package_parts = package_parts[:-1]

        base_length = len(package_parts) - level + 1
        if base_length < 0:
            return module

        base_parts = package_parts[:base_length]
        if module:
            base_parts.extend(module.split("."))

        return ".".join(part for part in base_parts if part)

    def _resolve_class(
        self,
        candidate: str,
        module_name: str,
        aliases: Mapping[str, str],
        lookup: Mapping[str, Any],
    ) -> str:
        expanded = self._expand_alias(candidate, aliases)
        classes_by_qualified = lookup["classes_by_qualified"]
        classes_by_name = lookup["classes_by_name"]

        if not isinstance(classes_by_qualified, dict) or not isinstance(classes_by_name, dict):
            return ""

        if expanded in classes_by_qualified:
            return classes_by_qualified[expanded]

        local_name = f"{module_name}.{expanded}"
        if local_name in classes_by_qualified:
            return classes_by_qualified[local_name]

        short_name = expanded.rsplit(".", 1)[-1]
        matches = classes_by_name.get(short_name, [])
        if len(matches) == 1 and expanded == short_name:
            return matches[0]

        return ""

    def _resolve_function(
        self,
        candidate: str,
        module_name: str,
        aliases: Mapping[str, str],
        lookup: Mapping[str, Any],
    ) -> str:
        expanded = self._expand_alias(candidate, aliases)
        functions_by_qualified = lookup["functions_by_qualified"]

        if not isinstance(functions_by_qualified, dict):
            return ""

        if expanded in functions_by_qualified:
            return functions_by_qualified[expanded]

        local_name = f"{module_name}.{expanded}"
        if local_name in functions_by_qualified:
            return functions_by_qualified[local_name]

        return ""

    def _resolve_method_call(
        self,
        candidate: str,
        module_name: str,
        class_id: str,
        aliases: Mapping[str, str],
        lookup: Mapping[str, Any],
    ) -> str:
        methods_by_qualified = lookup["methods_by_qualified"]

        if isinstance(methods_by_qualified, dict) and candidate.startswith("self."):
            method_name = candidate.split(".", 1)[1]
            method_id = self._method_id(class_id, method_name)
            if method_id in methods_by_qualified.values():
                return method_id

        function_id = self._resolve_function(candidate, module_name, aliases, lookup)
        if function_id:
            return function_id

        expanded = self._expand_alias(candidate, aliases)
        if isinstance(methods_by_qualified, dict) and expanded in methods_by_qualified:
            return methods_by_qualified[expanded]

        local_method = f"{module_name}.{expanded}"
        if isinstance(methods_by_qualified, dict) and local_method in methods_by_qualified:
            return methods_by_qualified[local_method]

        return ""

    def _expand_alias(self, candidate: str, aliases: Mapping[str, str]) -> str:
        if not candidate:
            return ""

        parts = candidate.split(".")
        first = parts[0]
        if first not in aliases:
            return candidate

        return ".".join([aliases[first]] + parts[1:])
