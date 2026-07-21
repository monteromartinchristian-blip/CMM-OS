"""Bounded structural analysis for planning context."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from kernel.services.python_index import PythonIndex


_EXCLUDED_PARTS = {".git", ".venv", "venv", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"}


@dataclass(frozen=True, slots=True)
class ProjectFile:
    path: str
    module: str
    size: int
    imports: tuple[str, ...]
    classes: tuple[dict[str, Any], ...]
    functions: tuple[dict[str, Any], ...]
    import_targets: tuple[dict[str, Any], ...]
    syntax_error: str | None = None

    def serialize(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "module": self.module,
            "size": self.size,
            "imports": list(self.imports),
            "classes": list(self.classes),
            "functions": list(self.functions),
            "import_targets": list(self.import_targets),
            "syntax_error": self.syntax_error,
        }


@dataclass(frozen=True, slots=True)
class ProjectContext:
    root: Path
    files: tuple[ProjectFile, ...]
    total_python_files: int
    truncated: bool

    def serialize(self) -> dict[str, Any]:
        return {
            "root": str(self.root),
            "total_python_files": self.total_python_files,
            "truncated": self.truncated,
            "files": [item.serialize() for item in self.files],
        }


class ProjectAnalyzer:
    """Build a relevant, size-limited Python project summary."""

    def __init__(self, indexer: PythonIndex | None = None) -> None:
        self._indexer = indexer or PythonIndex()

    def analyze(self, root: Path, goal: str, max_files: int = 40) -> ProjectContext:
        root = Path(root).resolve(strict=True)
        if max_files < 1:
            raise ValueError("max_files must be at least 1.")
        paths = [
            path
            for path in root.rglob("*.py")
            if not any(part in _EXCLUDED_PARTS for part in path.relative_to(root).parts)
            and path.is_file()
            and self._is_within_root(path, root)
        ]
        indexed = [self._summarize(root, path) for path in sorted(paths)]
        terms = set(re.findall(r"[A-Za-z_][A-Za-z0-9_.]*", goal.lower()))
        ranked = sorted(indexed, key=lambda item: (-self._score(item, terms), item.path))
        selected = tuple(ranked[:max_files])
        return ProjectContext(root, selected, len(indexed), len(indexed) > len(selected))

    def _summarize(self, root: Path, path: Path) -> ProjectFile:
        relative = path.relative_to(root)
        module = ".".join(relative.with_suffix("").parts)
        try:
            index = self._indexer.index(path)
            return ProjectFile(
                path=relative.as_posix(),
                module=module,
                size=path.stat().st_size,
                imports=tuple(index["imports"]),
                classes=tuple(index["classes"]),
                functions=tuple(index["functions"]),
                import_targets=tuple(index["import_targets"]),
            )
        except (SyntaxError, UnicodeDecodeError) as error:
            return ProjectFile(relative.as_posix(), module, path.stat().st_size, (), (), (), (), str(error))

    def _score(self, item: ProjectFile, terms: set[str]) -> int:
        searchable = [item.path.lower(), item.module.lower(), *[value.lower() for value in item.imports]]
        for cls in item.classes:
            searchable.append(str(cls.get("name", "")).lower())
            searchable.extend(str(method.get("name", "")).lower() for method in cls.get("methods", ()))
        searchable.extend(str(function.get("name", "")).lower() for function in item.functions)
        return sum(1 for term in terms if any(term in value or value in term for value in searchable if value))

    def _is_within_root(self, path: Path, root: Path) -> bool:
        try:
            path.resolve(strict=True).relative_to(root)
        except (OSError, ValueError):
            return False
        return True
