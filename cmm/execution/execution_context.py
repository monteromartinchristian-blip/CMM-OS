"""Shared project-aware context for transformation execution."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

from cmm.transformations.operation import TransformationOperation
from cmm.transformations.operations import (
    CopySymbolOperation,
    CreateFileOperation,
    CreateModuleOperation,
    DeleteFileOperation,
    DeleteModuleOperation,
    DeleteSymbolOperation,
    RenameSymbolOperation,
    UpdateImportsOperation,
)


class ProjectPathError(ValueError):
    """Raised when a path cannot be safely resolved inside a project."""


class ExecutionContext:
    """Normalize project paths and share semantic context across components."""

    def __init__(
        self,
        project_root: str | Path,
        semantic_context: Any | None = None,
        parser: Any | None = None,
        context_builder: Any | None = None,
    ) -> None:
        if project_root is None:
            raise ProjectPathError("project_root is required.")
        self.project_root = Path(project_root).expanduser().resolve()
        if not self.project_root.is_dir():
            raise ProjectPathError(f"project_root is not a directory: {self.project_root}.")
        from cmm.execution.python.python_project_parser import PythonProjectParser
        from cmm.execution.python.semantic_context_builder import SemanticContextBuilder

        self._parser = parser or PythonProjectParser()
        self._context_builder = context_builder or SemanticContextBuilder()
        self.semantic_context = semantic_context or self.refresh_semantic_context()

    def refresh_semantic_context(self) -> Any:
        """Reparse the project and store a fresh semantic context."""
        snapshot = self._parser.parse(self.project_root)
        self.semantic_context = self._context_builder.build(
            snapshot,
            build_reference_index=True,
        )
        return self.semantic_context

    def resolve_project_path(self, path: str | Path) -> Path:
        """Resolve ``path`` below project_root and reject path traversal."""
        candidate = Path(path)
        if not candidate.is_absolute():
            candidate = self.project_root / candidate
        resolved = candidate.expanduser().resolve()
        if not resolved.is_relative_to(self.project_root):
            raise ProjectPathError(f"Path escapes project_root: {path}.")
        return resolved

    def module_path(self, module_name: str) -> Path:
        """Return the expected path for a Python module in this project."""
        normalized_name = module_name[:-3] if module_name.endswith(".py") else module_name
        if not normalized_name or any(part in {"", ".", ".."} for part in normalized_name.split(".")):
            raise ProjectPathError(f"Invalid module name: {module_name}.")
        return self.resolve_project_path(Path(*normalized_name.split(".")).with_suffix(".py"))

    def module_contains_symbol(self, module_name: str, symbol_name: str) -> bool:
        """Return whether ``module_name`` contains a top-level class or function."""
        module_path = self.module_path(module_name)
        if not module_path.is_file():
            return False
        try:
            tree = ast.parse(module_path.read_text(encoding="utf-8"))
        except SyntaxError:
            return False
        return any(
            isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef)
            and node.name == symbol_name
            for node in tree.body
        )

    def affected_paths_for(self, operation: TransformationOperation) -> tuple[Path, ...]:
        """Return conservative in-project files an operation can affect."""
        if isinstance(operation, CreateFileOperation | DeleteFileOperation):
            return self._path_with_missing_parents(operation.path)
        if isinstance(operation, CreateModuleOperation):
            module_path = self.module_path(operation.module_name)
            package_path = self.project_root
            package_paths = []
            for package_name in operation.module_name.split(".")[:-1]:
                package_path /= package_name
                package_paths.append(package_path)
            init_paths = [package_path / "__init__.py" for package_path in package_paths]
            return tuple(sorted({module_path, *package_paths, *init_paths}))
        if isinstance(operation, DeleteModuleOperation):
            return (self.module_path(operation.module),)
        if isinstance(operation, CopySymbolOperation):
            return (self.module_path(operation.destination),)
        if isinstance(operation, DeleteSymbolOperation):
            return (self.module_path(operation.module),)
        if isinstance(operation, RenameSymbolOperation):
            return tuple(
                self.resolve_project_path(module.path)
                for module in self.semantic_context.snapshot.modules
                if module.path.resolve().is_relative_to(self.project_root)
            )
        if isinstance(operation, UpdateImportsOperation):
            return tuple(
                self.resolve_project_path(module.path)
                for module in self.semantic_context.snapshot.modules
                if module.path.resolve().is_relative_to(self.project_root)
            )
        metadata = operation.metadata()
        path = metadata.get("path")
        if isinstance(path, str):
            return self._path_with_missing_parents(path)
        return ()

    def _path_with_missing_parents(self, path: str | Path) -> tuple[Path, ...]:
        resolved = self.resolve_project_path(path)
        paths = [resolved]
        parent = resolved.parent
        while parent != self.project_root and parent.is_relative_to(self.project_root):
            paths.append(parent)
            parent = parent.parent
        return tuple(sorted(paths))
