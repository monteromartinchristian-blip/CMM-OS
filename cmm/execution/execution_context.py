"""Shared project-aware context for transformation execution."""

from __future__ import annotations

import ast
import builtins
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

    def module_contains_symbol(
        self,
        module_name: str,
        symbol_name: str,
        symbol_kind: str | None = None,
    ) -> bool:
        """Return whether ``module_name`` contains a matching top-level symbol."""
        return self.module_symbol_count(module_name, symbol_name, symbol_kind) > 0

    def module_symbol_count(
        self,
        module_name: str,
        symbol_name: str,
        symbol_kind: str | None = None,
    ) -> int:
        """Return the number of matching top-level symbols."""
        module_path = self.module_path(module_name)
        if not module_path.is_file():
            return 0
        try:
            tree = ast.parse(module_path.read_text(encoding="utf-8"))
        except SyntaxError:
            return 0
        count = 0
        for node in tree.body:
            if symbol_kind is None and isinstance(node, ast.Import | ast.ImportFrom):
                bound_names = self._ast_import_bindings(node)
                if symbol_name in bound_names:
                    count += 1
            if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
                continue
            if node.name != symbol_name:
                continue
            if symbol_kind is None:
                count += 1
            if symbol_kind == "function" and isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                count += 1
            if symbol_kind == "class" and isinstance(node, ast.ClassDef):
                count += 1
        return count

    def validate_symbol_move_references(
        self,
        source_module: str,
        symbol_name: str,
        target_module: str,
        new_symbol_name: str,
    ) -> tuple[bool, str]:
        """Validate the conservative import/reference subset supported by moves."""
        from cmm.execution.python.visitors import ReferenceLocator
        import libcst as cst

        locator = ReferenceLocator()
        for module in self.semantic_context.snapshot.modules:
            try:
                self.resolve_project_path(module.path)
            except ProjectPathError:
                return False, f"Module path escapes project_root: {module.path}."
            if module.parsed_module is None:
                return False, f"References are not analyzable in {module.module_name}."
            bindings: set[str] = set()
            for statement in module.parsed_module.body:
                if not isinstance(statement, cst.SimpleStatementLine):
                    continue
                for small_statement in statement.body:
                    if isinstance(small_statement, cst.ImportFrom):
                        imported_module = self._cst_module_name(small_statement)
                        if imported_module == target_module:
                            if isinstance(small_statement.names, cst.ImportStar):
                                return False, f"Wildcard target import is unsupported in {module.module_name}."
                            for imported in small_statement.names:
                                bound_name = (
                                    imported.asname.name.value
                                    if imported.asname is not None
                                    else self._cst_name(imported.name)
                                )
                                if bound_name == new_symbol_name:
                                    return False, f"Import collision in {module.module_name}: {new_symbol_name}."
                        if imported_module != source_module:
                            continue
                        if isinstance(small_statement.names, cst.ImportStar):
                            return False, f"Wildcard import is unsupported in {module.module_name}."
                        if len(small_statement.names) != 1:
                            return False, f"Multiple imported symbols are unsupported in {module.module_name}."
                        for imported in small_statement.names:
                            if isinstance(imported.name, cst.Name) and imported.name.value == symbol_name:
                                bindings.add(
                                    imported.asname.name.value
                                    if imported.asname is not None
                                    else symbol_name
                                )
                    elif isinstance(small_statement, cst.Import):
                        if any(
                            self._cst_name(alias.name) == source_module
                            for alias in small_statement.names
                        ):
                            return False, f"Direct module import is unsupported in {module.module_name}."

            references = locator.find(module.module_name, module.parsed_module, symbol_name)
            if module.module_name == source_module and references:
                return False, f"Internal references to {source_module}.{symbol_name} are unsupported."
            if module.module_name != source_module and references and not bindings:
                return False, f"Ambiguous reference to {symbol_name} in {module.module_name}."
            if module.module_name != source_module and bindings:
                if self._has_ambiguous_local_binding(module.path, symbol_name, source_module):
                    return False, f"Ambiguous local binding for {symbol_name} in {module.module_name}."
        return True, f"References to {source_module}.{symbol_name} are supported."

    def _has_ambiguous_local_binding(
        self,
        module_path: Path,
        symbol_name: str,
        source_module: str,
    ) -> bool:
        """Detect local homonyms that a simple-name rewrite cannot disambiguate."""
        try:
            tree = ast.parse(module_path.read_text(encoding="utf-8"))
        except (OSError, SyntaxError, UnicodeError):
            return True
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if self._ast_import_module_name(node) == source_module:
                    continue
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                if node.name == symbol_name:
                    return True
            if isinstance(node, ast.arg) and node.arg == symbol_name:
                return True
            if (
                isinstance(node, ast.Name)
                and node.id == symbol_name
                and isinstance(node.ctx, ast.Store)
            ):
                return True
        return False

    def _ast_import_module_name(self, node: ast.ImportFrom) -> str:
        prefix = "." * node.level
        return prefix + (node.module or "")

    def validate_function_dependencies(
        self,
        source_module: str,
        target_module: str,
        symbol_name: str,
    ) -> tuple[bool, str]:
        """Reject moved functions whose non-local globals are absent in target."""
        return self.validate_symbol_dependencies(
            source_module, target_module, symbol_name, "function"
        )

    def validate_symbol_dependencies(
        self,
        source_module: str,
        target_module: str,
        symbol_name: str,
        symbol_kind: str,
    ) -> tuple[bool, str]:
        """Reject typed symbols whose non-local globals are absent in target."""
        source_path = self.module_path(source_module)
        target_path = self.module_path(target_module)
        try:
            source_tree = ast.parse(source_path.read_text(encoding="utf-8"))
            target_tree = ast.parse(target_path.read_text(encoding="utf-8"))
        except (OSError, SyntaxError, UnicodeError) as error:
            return False, f"Symbol dependencies are not analyzable: {error}."

        expected = {
            "function": (ast.FunctionDef, ast.AsyncFunctionDef),
            "class": (ast.ClassDef,),
        }.get(symbol_kind)
        if expected is None:
            return False, f"Unsupported symbol kind: {symbol_kind}."
        symbol = next(
            (
                node
                for node in source_tree.body
                if isinstance(node, expected)
                and node.name == symbol_name
            ),
            None,
        )
        if symbol is None:
            return False, f"{symbol_kind.title()} not found: {source_module}.{symbol_name}."

        available = set(dir(builtins))
        for node in target_tree.body:
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
                available.add(node.name)
            elif isinstance(node, ast.Import | ast.ImportFrom):
                available.update(self._ast_import_bindings(node))

        bound = {symbol.name}
        for node in ast.walk(symbol):
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                bound.add(node.name)
                bound.update(argument.arg for argument in (
                    *node.args.posonlyargs,
                    *node.args.args,
                    *node.args.kwonlyargs,
                ))
                if node.args.vararg is not None:
                    bound.add(node.args.vararg.arg)
                if node.args.kwarg is not None:
                    bound.add(node.args.kwarg.arg)
            elif isinstance(node, ast.ClassDef):
                bound.add(node.name)
        bound.update(
            node.id
            for node in ast.walk(symbol)
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store)
        )
        required = {
            node.id
            for node in ast.walk(symbol)
            if isinstance(node, ast.Name)
            and isinstance(node.ctx, ast.Load)
            and node.id not in bound
        }
        missing = sorted(required - available)
        if missing:
            return False, (
                f"Unsupported global dependencies for {source_module}.{symbol_name}: "
                + ", ".join(missing)
                + "."
            )
        return True, f"Dependencies for {source_module}.{symbol_name} are available in {target_module}."

    def _ast_import_bindings(self, node: ast.Import | ast.ImportFrom) -> set[str]:
        if isinstance(node, ast.Import):
            return {alias.asname or alias.name.split(".", maxsplit=1)[0] for alias in node.names}
        return {
            alias.asname or alias.name
            for alias in node.names
            if alias.name != "*"
        }

    def _cst_module_name(self, statement: object) -> str:
        import libcst as cst

        if not isinstance(statement, cst.ImportFrom) or statement.module is None:
            return ""
        return self._cst_name(statement.module)

    def _cst_name(self, node: object) -> str:
        import libcst as cst

        if isinstance(node, cst.Name):
            return node.value
        if isinstance(node, cst.Attribute):
            return f"{self._cst_name(node.value)}.{node.attr.value}"
        return ""

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
