from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from kernel.services.project_analyzer import ProjectAnalyzer
from kernel.services.python_index import PythonIndex
from cmm.validation.errors import ValidationContractError

from .contracts import DependencyEdge, DependencyGraph


def build_dependency_graph(
    project_root: Path,
    *,
    project_index: Any | None = None,
) -> DependencyGraph:
    root = Path(project_root).resolve(strict=False)
    analyzer = ProjectAnalyzer(root)
    python_index = PythonIndex()
    module_paths = {module_name_from_path(root, path): path for path in analyzer.python_files()}
    module_names = tuple(sorted(module_paths))
    edges: set[DependencyEdge] = set()

    for module_name, relative_path in module_paths.items():
        path = root / relative_path
        try:
            data = python_index.index(path)
        except Exception:
            continue
        for target in _resolve_import_targets(module_name, data.get("import_targets", ()), set(module_names)):
            if target != module_name:
                edges.add(DependencyEdge(source=module_name, target=target, kind="import"))

    if project_index is not None:
        _augment_from_project_index(project_index, edges, module_names)

    return DependencyGraph(
        modules=module_names,
        edges=tuple(sorted(edges, key=lambda edge: (edge.source, edge.target, edge.kind))),
        confidence=0.9 if edges else 1.0,
        metadata={"project_root": str(root)},
    )


def module_name_from_path(project_root: Path, path: Path) -> str:
    root = Path(project_root).resolve(strict=False)
    candidate = Path(path)
    if candidate.is_absolute():
        relative = candidate.resolve(strict=False).relative_to(root)
    else:
        relative = (root / candidate).resolve(strict=False).relative_to(root)
    parts = list(relative.with_suffix("").parts)
    if parts and parts[-1] == "__init__":
        parts.pop()
    if not parts:
        return Path(project_root).name
    return ".".join(parts)


def affected_dependents(graph: DependencyGraph, modules: set[str]) -> set[str]:
    impacted = set(modules)
    queue = list(modules)
    while queue:
        module = queue.pop(0)
        for dependent in graph.dependents_of(module):
            if dependent in impacted:
                continue
            impacted.add(dependent)
            queue.append(dependent)
    return impacted


def _resolve_import_targets(module_name: str, import_targets: Any, project_modules: set[str]) -> tuple[str, ...]:
    resolved: list[str] = []
    package_parts = module_name.split(".")
    for item in import_targets:
        if not isinstance(item, Mapping):
            continue
        kind = str(item.get("kind", "import"))
        target_module = str(item.get("module") or "")
        imported_name = item.get("name")
        level = int(item.get("level", 0) or 0)
        candidates: list[str] = []
        if kind == "import":
            candidates.append(target_module)
        else:
            base = target_module
            if level > 0:
                trimmed = package_parts[: max(0, len(package_parts) - level)]
                base = ".".join(trimmed + ([target_module] if target_module else []))
            if imported_name:
                if base:
                    candidates.append(f"{base}.{imported_name}")
                candidates.append(base)
            else:
                candidates.append(base)
        for candidate in candidates:
            if candidate and candidate in project_modules:
                resolved.append(candidate)
                break
    return tuple(dict.fromkeys(resolved))


def _augment_from_project_index(project_index: Any, edges: set[DependencyEdge], module_names: tuple[str, ...]) -> None:
    if not hasattr(project_index, "find_module") or not hasattr(project_index, "find_imported_by"):
        return
    for module_name in module_names:
        try:
            node = project_index.find_module(module_name)
        except Exception:
            node = None
        if node is None:
            continue
        try:
            dependents = project_index.find_imported_by(node)
        except Exception:
            continue
        for dependent in dependents or ():
            dependent_name = getattr(dependent, "title", None) or getattr(dependent, "identifier", None)
            if not dependent_name or dependent_name == module_name:
                continue
            edges.add(DependencyEdge(source=str(dependent_name), target=module_name, kind="technical_memory", confidence=0.6))
