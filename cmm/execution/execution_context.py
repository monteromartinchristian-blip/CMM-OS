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
    ExtractMethodOperation,
    ExtractModuleOperation,
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
        technical_memory: Any | None = None,
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
        self.technical_memory = technical_memory
        self.impact_result = None
        self.post_impact_validation = None
        self.semantic_context = semantic_context or self.refresh_semantic_context()

    def analyze_impact(self, request: object) -> object:
        """Run one cached impact analysis against the current semantic snapshot."""
        from cmm.transformations.impact_analysis import ImpactAnalyzer, ImpactAnalysisRequest

        if not isinstance(request, ImpactAnalysisRequest):
            raise TypeError("Impact analysis requires ImpactAnalysisRequest.")
        if self.impact_result is not None:
            cached = self.impact_result.request
            if (
                cached.source_module,
                cached.target_module,
                cached.symbols,
                cached.renamed_symbols,
            ) == (
                request.source_module,
                request.target_module,
                request.symbols,
                request.renamed_symbols,
            ):
                return self.impact_result
        self.impact_result = ImpactAnalyzer(self.technical_memory).analyze(self, request)
        return self.impact_result

    def validate_post_impact(self, changed_paths: tuple[Path, ...]) -> object | None:
        """Validate the transformed graph against the cached expected impact."""
        from cmm.transformations.impact_analysis import ImpactAnalyzer

        if self.impact_result is None:
            return None
        self.post_impact_validation = ImpactAnalyzer().validate_post(
            self,
            self.impact_result,
            changed_paths,
        )
        return self.post_impact_validation

    def validate_rollback_impact(self) -> object | None:
        """Compare a restored project graph with the pre-execution impact graph."""
        if self.impact_result is None:
            return None
        from dataclasses import replace
        from cmm.transformations.impact_analysis import ImpactAnalyzer

        rollback_validation = ImpactAnalyzer().validate_rollback(
            self,
            self.impact_result,
        )
        if self.post_impact_validation is None:
            self.post_impact_validation = rollback_validation
        else:
            self.post_impact_validation = replace(
                self.post_impact_validation,
                rollback_graph_matches=rollback_validation.rollback_graph_matches,
                rollback_discrepancies=rollback_validation.rollback_discrepancies,
            )
        return self.post_impact_validation

    def refresh_technical_memory(self) -> tuple[bool, str | None]:
        """Refresh optional technical memory after a committed successful mutation."""
        if self.technical_memory is None:
            return True, None
        refresh = getattr(self.technical_memory, "refresh", None)
        if not callable(refresh):
            return False, "Technical memory has no refresh operation."
        try:
            result = refresh()
        except (OSError, RuntimeError, ValueError) as error:
            return False, str(error)
        success = bool(getattr(result, "success", True))
        if not success:
            errors = tuple(getattr(result, "errors", ()))
            message = "; ".join(str(error) for error in errors) or "Technical memory refresh failed."
            if self.impact_result is not None:
                from dataclasses import replace

                self.impact_result = replace(
                    self.impact_result,
                    memory_used=True,
                    memory_stale=True,
                    memory_errors=(*self.impact_result.memory_errors, message),
                )
            return False, message
        if success and self.impact_result is not None:
            from dataclasses import replace

            self.impact_result = replace(
                self.impact_result,
                memory_used=True,
                memory_refreshed=(
                    self.impact_result.memory_refreshed
                    or bool(getattr(result, "rebuilt", False))
                    or bool(getattr(result, "persisted", False))
                ),
                memory_stale=False,
            )
        return True, None

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
        """Validate statically rewritable direct, from, relative, and qualified references."""
        from cmm.execution.python.visitors import ReferenceLocator
        from cmm.transformations.relative_import_resolver import RelativeImportResolver
        from cmm.transformations.impact_analysis import ImpactAnalysisRequest
        import libcst as cst

        impact = self.analyze_impact(ImpactAnalysisRequest(
            source_module=source_module,
            target_module=target_module,
            symbols=(symbol_name,),
            renamed_symbols=((new_symbol_name,) if new_symbol_name != symbol_name else ()),
            transformation_id="move_symbol",
        ))
        if not impact.success:
            return False, impact.summary
        locator = ReferenceLocator()
        resolver = RelativeImportResolver()
        for module in self.semantic_context.snapshot.modules:
            try:
                self.resolve_project_path(module.path)
            except ProjectPathError:
                return False, f"Module path escapes project_root: {module.path}."
            if module.parsed_module is None:
                return False, f"References are not analyzable in {module.module_name}."
            bindings: set[str] = set()
            qualified_bindings: set[str] = set()
            for statement in module.parsed_module.body:
                if not isinstance(statement, cst.SimpleStatementLine):
                    continue
                for small_statement in statement.body:
                    if isinstance(small_statement, cst.ImportFrom):
                        raw_module = self._cst_module_name(small_statement)
                        resolution = resolver.resolve(
                            module.module_name,
                            len(small_statement.relative),
                            raw_module,
                            consumer_is_package=module.path.name == "__init__.py",
                        )
                        imported_module = resolution.absolute_module if resolution is not None else ""
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
                        if small_statement.relative and resolver.render_relative(
                            module.module_name,
                            target_module,
                            consumer_is_package=module.path.name == "__init__.py",
                        ) is None:
                            return False, (
                                f"Relative import from {module.module_name} to "
                                f"{target_module} cannot be preserved."
                            )
                        if isinstance(small_statement.names, cst.ImportStar):
                            return False, f"Wildcard import is unsupported in {module.module_name}."
                        for imported in small_statement.names:
                            if isinstance(imported.name, cst.Name) and imported.name.value == symbol_name:
                                bindings.add(
                                    imported.asname.name.value
                                    if imported.asname is not None
                                    else symbol_name
                                )
                    elif isinstance(small_statement, cst.Import):
                        for alias in small_statement.names:
                            if self._cst_name(alias.name) != source_module:
                                continue
                            binding = (
                                alias.asname.name.value
                                if alias.asname is not None
                                else source_module.split(".")[0]
                            )
                            qualified_bindings.add(binding)
                            if self._has_ambiguous_local_binding(
                                module.path,
                                binding,
                                source_module,
                                module.module_name,
                                module.path.name == "__init__.py",
                            ):
                                return False, f"Shadowed module binding {binding} in {module.module_name}."

            references = locator.find(module.module_name, module.parsed_module, symbol_name)
            if module.module_name == source_module and references:
                return False, f"Internal references to {source_module}.{symbol_name} are unsupported."
            if module.module_name != source_module and references and not bindings and not qualified_bindings:
                return False, f"Ambiguous reference to {symbol_name} in {module.module_name}."
            if module.module_name != source_module and bindings:
                for binding in bindings:
                    if self._has_ambiguous_local_binding(
                        module.path,
                        binding,
                        source_module,
                        module.module_name,
                        module.path.name == "__init__.py",
                    ):
                        return False, f"Ambiguous local binding for {binding} in {module.module_name}."
        return True, f"References to {source_module}.{symbol_name} are supported."

    def _has_ambiguous_local_binding(
        self,
        module_path: Path,
        symbol_name: str,
        source_module: str,
        consumer_module: str,
        consumer_is_package: bool,
    ) -> bool:
        """Detect local homonyms that a simple-name rewrite cannot disambiguate."""
        try:
            tree = ast.parse(module_path.read_text(encoding="utf-8"))
        except (OSError, SyntaxError, UnicodeError):
            return True
        from cmm.transformations.relative_import_resolver import RelativeImportResolver

        resolver = RelativeImportResolver()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                resolution = resolver.resolve(
                    consumer_module,
                    node.level,
                    node.module or "",
                    consumer_is_package=consumer_is_package,
                )
                if resolution is not None and resolution.absolute_module == source_module:
                    continue
                if any((alias.asname or alias.name) == symbol_name for alias in node.names):
                    return True
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == source_module:
                        continue
                    if (alias.asname or alias.name.split(".", 1)[0]) == symbol_name:
                        return True
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

    def validate_extract_method(
        self,
        module: str,
        class_name: str,
        method_name: str,
        new_method_name: str,
        start_index: int,
        end_index: int,
    ) -> tuple[bool, str]:
        from cmm.execution.python.extract_method_analysis import analyze_method_extraction

        path = self.module_path(module)
        analysis, message = analyze_method_extraction(
            path, class_name, method_name, new_method_name, start_index, end_index
        )
        if analysis is None:
            return False, message
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (OSError, SyntaxError, UnicodeError) as error:
            return False, f"Module is not analyzable: {error}."
        class_node = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == class_name)
        if any(
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == new_method_name
            for node in class_node.body
        ):
            return False, f"Extracted method already exists: {class_name}.{new_method_name}."
        return True, message

    def validate_extract_module(
        self,
        source_module: str,
        target_module: str,
        symbols: tuple[str, ...],
        allow_missing_target: bool = False,
    ) -> tuple[bool, str]:
        import libcst as cst
        from cmm.transformations.relative_import_resolver import RelativeImportResolver
        from cmm.execution.python.visitors import SymbolLocator

        if not symbols:
            return False, "Symbol selection is empty."
        if len(set(symbols)) != len(symbols):
            return False, "Symbol selection contains duplicates."
        if source_module == target_module:
            return False, "Source and target modules must differ."
        source = next((item for item in self.semantic_context.snapshot.modules if item.module_name == source_module), None)
        target = next((item for item in self.semantic_context.snapshot.modules if item.module_name == target_module), None)
        if source is None or source.parsed_module is None:
            return False, f"Source module is not analyzable: {source_module}."
        if target is None and allow_missing_target:
            target = type(source)(
                path=self.module_path(target_module),
                module_name=target_module,
                parsed_module=cst.Module(body=()),
            )
        if target is None or target.parsed_module is None:
            return False, f"Target module is not analyzable: {target_module}."
        locator = SymbolLocator()
        selected = []
        for name in symbols:
            function_count = self.module_symbol_count(source_module, name, "function")
            class_count = self.module_symbol_count(source_module, name, "class")
            if function_count + class_count > 1:
                return False, f"Ambiguous symbol: {source_module}.{name}."
            symbol = locator.find(source.parsed_module, name, "function") or locator.find(
                source.parsed_module, name, "class"
            )
            if symbol is None:
                return False, f"Symbol not found: {source_module}.{name}."
            selected.append(symbol)
            if self.module_symbol_count(target_module, name, "function") + self.module_symbol_count(target_module, name, "class"):
                return False, f"Destination conflict: {target_module}.{name}."
        selected_names = set(symbols)
        resolver = RelativeImportResolver()
        source_defs = {
            node.name.value for node in source.parsed_module.body
            if isinstance(node, (cst.FunctionDef, cst.ClassDef))
        }
        for symbol in selected:
            names = self._cst_loaded_names(symbol)
            missing_local = sorted((names & source_defs) - selected_names)
            if missing_local:
                return False, f"Unselected local dependencies for {symbol.name.value}: {', '.join(missing_local)}."
        for statement in source.parsed_module.body:
            if not isinstance(statement, cst.SimpleStatementLine):
                continue
            for small in statement.body:
                if isinstance(small, cst.Import):
                    imported_modules = {self._cst_name(alias.name) for alias in small.names}
                    if source_module in imported_modules:
                        return False, f"Direct import of source module is unsupported in {source_module}."
        for module in self.semantic_context.snapshot.modules:
            if module.parsed_module is None:
                return False, f"References are not analyzable in {module.module_name}."
            for statement in module.parsed_module.body:
                if not isinstance(statement, cst.SimpleStatementLine):
                    continue
                for small in statement.body:
                    if isinstance(small, cst.ImportFrom) and self._cst_module_name(small) == source_module:
                        if isinstance(small.names, cst.ImportStar):
                            return False, f"Unsupported import in {module.module_name}."
                    if isinstance(small, cst.ImportFrom) and small.module is not None:
                        resolution = resolver.resolve(
                            module.module_name,
                            len(small.relative),
                            self._cst_module_name(small),
                            consumer_is_package=module.path.name == "__init__.py",
                        )
                        if resolution is not None and resolution.absolute_module == source_module:
                            if small.relative and resolver.render_relative(
                                module.module_name,
                                target_module,
                                consumer_is_package=module.path.name == "__init__.py",
                            ) is None:
                                return False, (
                                    f"Relative import from {module.module_name} to "
                                    f"{target_module} cannot be preserved."
                                )
                            if isinstance(small.names, cst.ImportStar):
                                return False, f"Unsupported import in {module.module_name}."
                    if isinstance(small, cst.Import) and any(self._cst_name(alias.name) == source_module for alias in small.names):
                        return False, f"Direct module import is unsupported in {module.module_name}."
        return True, f"Selected symbols are safe to extract into {target_module}."

    def _cst_loaded_names(self, node: object) -> set[str]:
        import libcst as cst

        class Collector(cst.CSTVisitor):
            def __init__(self) -> None:
                self.names: set[str] = set()

            def visit_Name(self, name: cst.Name) -> None:
                self.names.add(name.value)

        collector = Collector()
        if isinstance(node, cst.CSTNode):
            node.visit(collector)
        return collector.names

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
        if isinstance(operation, ExtractMethodOperation):
            return (self.module_path(operation.module),)
        if isinstance(operation, ExtractModuleOperation):
            return tuple(
                self.resolve_project_path(module.path)
                for module in self.semantic_context.snapshot.modules
            ) + (self.module_path(operation.source_module), self.module_path(operation.target_module))
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
