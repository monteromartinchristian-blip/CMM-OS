"""Read-only validation for Python layout transformations."""

from __future__ import annotations

import ast
import builtins
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from cmm.transformations.operations import (
    MergeModulesOperation,
    MoveModuleOperation,
    MovePackageOperation,
    RenameModuleOperation,
    RenamePackageOperation,
    ReorganizationOperation,
    SplitModuleOperation,
)


@dataclass(frozen=True)
class ReorganizationValidationResult:
    success: bool
    diagnostics: tuple[str, ...] = ()


class TopLevelSideEffectAnalyzer:
    """Classify top-level statements without evaluating project code."""

    def unsafe_statements(self, tree: ast.Module) -> tuple[str, ...]:
        diagnostics = []
        for node in tree.body:
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                continue
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                diagnostics.extend(self._unsafe_definition(node))
                continue
            if (
                isinstance(node, ast.Expr)
                and isinstance(node.value, ast.Constant)
                and isinstance(node.value.value, str)
            ):
                continue
            if isinstance(node, ast.Assign):
                if any(isinstance(target, ast.Name) and target.id == "__all__" for target in node.targets):
                    if isinstance(node.value, ast.List | ast.Tuple) and all(
                        isinstance(item, ast.Constant) and isinstance(item.value, str)
                        for item in node.value.elts
                    ):
                        continue
                    diagnostics.append(f"Dynamic __all__ at line {node.lineno} is unsupported.")
                    continue
                if all(isinstance(target, ast.Name) for target in node.targets) and self._safe_value(node.value):
                    continue
            if isinstance(node, ast.AnnAssign):
                if isinstance(node.target, ast.Name) and (node.value is None or self._safe_value(node.value)):
                    continue
            diagnostics.append(f"Unsupported top-level {type(node).__name__} at line {node.lineno}.")
        return tuple(diagnostics)

    def _safe_value(self, node: ast.AST) -> bool:
        if isinstance(node, ast.Constant | ast.Name | ast.Attribute):
            return True
        if isinstance(node, ast.UnaryOp):
            return self._literal_value(node.operand)
        if isinstance(node, ast.BinOp):
            return self._literal_value(node.left) and self._literal_value(node.right)
        if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
            return all(self._safe_value(item) for item in node.elts)
        if isinstance(node, ast.Dict):
            return all(
                key is not None and self._safe_value(key) and self._safe_value(value)
                for key, value in zip(node.keys, node.values, strict=True)
            )
        return False

    def _unsafe_definition(
        self, node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef
    ) -> tuple[str, ...]:
        diagnostics: list[str] = []
        if node.decorator_list:
            diagnostics.append(
                f"Decorated top-level {type(node).__name__} at line {node.lineno} is unsupported."
            )
        eager: list[ast.AST] = []
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            eager.extend(node.args.defaults)
            eager.extend(item for item in node.args.kw_defaults if item is not None)
        else:
            eager.extend(node.bases)
            eager.extend(keyword.value for keyword in node.keywords)
            for statement in node.body:
                if isinstance(statement, ast.Assign):
                    eager.append(statement.value)
                elif isinstance(statement, ast.AnnAssign) and statement.value is not None:
                    eager.append(statement.value)
                elif isinstance(
                    statement,
                    (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Pass),
                ):
                    continue
                elif (
                    isinstance(statement, ast.Expr)
                    and isinstance(statement.value, ast.Constant)
                    and isinstance(statement.value.value, str)
                ):
                    continue
                else:
                    diagnostics.append(
                        f"Executable class-body {type(statement).__name__} at line "
                        f"{statement.lineno} is unsupported."
                    )
        if any(
            isinstance(item, (ast.Call, ast.Await, ast.NamedExpr, ast.ListComp,
                              ast.SetComp, ast.DictComp, ast.GeneratorExp))
            for expression in eager
            for item in ast.walk(expression)
        ):
            diagnostics.append(
                f"Executable definition-time expression at line {node.lineno} is unsupported."
            )
        return tuple(diagnostics)

    def _literal_value(self, node: ast.AST) -> bool:
        if isinstance(node, ast.Constant):
            return True
        if isinstance(node, ast.UnaryOp):
            return self._literal_value(node.operand)
        if isinstance(node, ast.BinOp):
            return self._literal_value(node.left) and self._literal_value(node.right)
        if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
            return all(self._literal_value(item) for item in node.elts)
        if isinstance(node, ast.Dict):
            return all(
                key is not None
                and self._literal_value(key)
                and self._literal_value(value)
                for key, value in zip(node.keys, node.values, strict=True)
            )
        return False


def top_level_symbols(tree: ast.Module) -> dict[str, ast.AST]:
    result: dict[str, ast.AST] = {}
    for node in tree.body:
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            result[node.name] = node
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id != "__all__":
                    result[target.id] = node
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if node.target.id != "__all__":
                result[node.target.id] = node
    return result


class ReorganizationValidator:
    """Validate filesystem, syntax, bindings, dependencies, and policies."""

    def validate(
        self, context: Any, operation: ReorganizationOperation
    ) -> ReorganizationValidationResult:
        diagnostics: list[str] = []
        try:
            if isinstance(operation, RenameModuleOperation):
                diagnostics.extend(self._validate_module_move(context, operation, rename=True))
            elif isinstance(operation, MoveModuleOperation):
                diagnostics.extend(self._validate_module_move(context, operation, rename=False))
            elif isinstance(operation, SplitModuleOperation):
                diagnostics.extend(self._validate_split(context, operation))
            elif isinstance(operation, MergeModulesOperation):
                diagnostics.extend(self._validate_merge(context, operation))
            elif isinstance(operation, RenamePackageOperation):
                diagnostics.extend(self._validate_package_move(context, operation, rename=True))
            elif isinstance(operation, MovePackageOperation):
                diagnostics.extend(self._validate_package_move(context, operation, rename=False))
            else:
                diagnostics.append(f"Unsupported operation: {type(operation).__name__}.")
        except (OSError, SyntaxError, UnicodeError, ValueError) as error:
            diagnostics.append(str(error))
        return ReorganizationValidationResult(not diagnostics, tuple(diagnostics))

    def _validate_module_move(self, context: Any, operation: Any, *, rename: bool) -> list[str]:
        source = operation.source_module
        target = operation.target_module
        diagnostics = self._validate_distinct_names(source, target, "module")
        if rename and source.rpartition(".")[0] != target.rpartition(".")[0]:
            diagnostics.append("RenameModule requires source and target in the same package.")
        source_path = self._existing_module_path(context, source)
        target_path = context.module_path(target)
        diagnostics.extend(self._safe_source_path(context, source_path))
        if source_path.name == "__init__.py":
            diagnostics.append("Package __init__.py cannot be reorganized as a normal module.")
        if target_path.exists() or self._module_exists(context, target):
            diagnostics.append(f"Target module already exists: {target}.")
        create_package = bool(getattr(operation, "create_target_package", False))
        diagnostics.extend(self._validate_target_package(context, target, create_package))
        diagnostics.extend(self._dynamic_or_shadowed_references(context, (source,)))
        diagnostics.extend(self._validate_relative_rewrites(context, ((source, target),)))
        return diagnostics

    def _validate_split(self, context: Any, operation: SplitModuleOperation) -> list[str]:
        diagnostics: list[str] = []
        if not operation.groups:
            return ["Split groups cannot be empty."]
        source_path = self._existing_module_path(context, operation.source_module)
        diagnostics.extend(self._safe_source_path(context, source_path))
        if source_path.name == "__init__.py":
            diagnostics.append("A package initializer cannot be split as a normal module.")
        tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
        diagnostics.extend(TopLevelSideEffectAnalyzer().unsafe_statements(tree))
        if any(
            isinstance(node, ast.ImportFrom)
            and any(alias.name == "*" for alias in node.names)
            for node in tree.body
        ):
            diagnostics.append("Wildcard imports are unsupported for module splitting.")
        definitions = top_level_symbols(tree)
        if "__getattr__" in definitions:
            diagnostics.append("Module-level __getattr__ is unsupported for splitting.")
        selected = [symbol for group in operation.groups for symbol in group.symbols]
        if not selected:
            diagnostics.append("Split symbol selection cannot be empty.")
        duplicates = sorted({name for name in selected if selected.count(name) > 1})
        if duplicates:
            diagnostics.append("Symbols selected more than once: " + ", ".join(duplicates) + ".")
        missing = sorted(set(selected) - set(definitions))
        if missing:
            diagnostics.append("Unknown split symbols: " + ", ".join(missing) + ".")
        targets = [group.target_module for group in operation.groups]
        if len(set(targets)) != len(targets):
            diagnostics.append("Split target modules must be unique.")
        for target in targets:
            if target == operation.source_module:
                diagnostics.append("Split target must differ from the source module.")
            if context.module_path(target).exists() or self._module_exists(context, target):
                diagnostics.append(f"Split target already exists: {target}.")
            diagnostics.extend(self._validate_target_package(context, target, False))
            diagnostics.extend(
                self._validate_relative_relocation(
                    tree, operation.source_module, target
                )
            )
        diagnostics.extend(self._validate_split_dependencies(tree, operation, definitions))
        diagnostics.extend(self._dynamic_or_shadowed_references(context, (operation.source_module,), set(selected)))
        return diagnostics

    def _validate_merge(self, context: Any, operation: MergeModulesOperation) -> list[str]:
        diagnostics: list[str] = []
        if len(operation.source_modules) < 2:
            diagnostics.append("Merge requires at least two source modules.")
        if len(set(operation.source_modules)) != len(operation.source_modules):
            diagnostics.append("Merge source modules must be unique.")
        if operation.target_module in operation.source_modules:
            diagnostics.append("Merge target cannot also be a source module.")
        seen: dict[str, str] = {}
        merge_trees: dict[str, ast.Module] = {}
        for module in operation.source_modules:
            path = self._existing_module_path(context, module)
            diagnostics.extend(self._safe_source_path(context, path))
            if path.name == "__init__.py":
                diagnostics.append(f"Package initializer cannot be merged as a normal module: {module}.")
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            merge_trees[module] = tree
            diagnostics.extend(TopLevelSideEffectAnalyzer().unsafe_statements(tree))
            if "__getattr__" in top_level_symbols(tree):
                diagnostics.append(f"Module-level __getattr__ is unsupported in {module}.")
            if any(
                isinstance(node, ast.ImportFrom)
                and any(alias.name == "*" for alias in node.names)
                for node in tree.body
            ):
                diagnostics.append(f"Wildcard imports are unsupported in {module}.")
            for node in tree.body:
                if isinstance(node, ast.Import) and any(
                    alias.name in operation.source_modules for alias in node.names
                ):
                    diagnostics.append(
                        f"Qualified imports between merged modules are unsupported in {module}."
                    )
            for symbol in top_level_symbols(tree):
                if symbol in seen:
                    diagnostics.append(
                        f"Merge symbol conflict for {symbol}: {seen[symbol]} and {module}."
                    )
                seen[symbol] = module
        available_definitions = set(seen)
        for module, tree in merge_trees.items():
            imported = self._import_bindings(tree)
            for symbol, node in top_level_symbols(tree).items():
                missing = (
                    self._loaded_names(node)
                    - self._bound_names(node)
                    - available_definitions
                    - imported
                    - set(dir(builtins))
                    - {"self", "cls"}
                )
                if missing:
                    diagnostics.append(
                        f"Unresolvable merge dependencies in {module}.{symbol}: "
                        + ", ".join(sorted(missing))
                        + "."
                    )
        target_path = context.module_path(operation.target_module)
        target_exists = target_path.exists() or self._module_exists(context, operation.target_module)
        if operation.create_target and target_exists:
            diagnostics.append(f"Merge target already exists: {operation.target_module}.")
        if not operation.create_target and not target_exists:
            diagnostics.append(f"Merge target does not exist: {operation.target_module}.")
        existing_target = next(
            (
                item for item in context.semantic_context.snapshot.modules
                if item.module_name == operation.target_module
            ),
            None,
        )
        if existing_target is not None and existing_target.path.name == "__init__.py":
            diagnostics.append("Merge target cannot be a package initializer.")
        if target_path.is_file():
            tree = ast.parse(target_path.read_text(encoding="utf-8"), filename=str(target_path))
            diagnostics.extend(TopLevelSideEffectAnalyzer().unsafe_statements(tree))
            for symbol in top_level_symbols(tree):
                if symbol in seen:
                    diagnostics.append(f"Merge target symbol conflict: {symbol}.")
        diagnostics.extend(self._validate_target_package(context, operation.target_module, False))
        for module, tree in merge_trees.items():
            diagnostics.extend(
                self._validate_relative_relocation(tree, module, operation.target_module)
            )
        diagnostics.extend(self._dynamic_or_shadowed_references(context, operation.source_modules))
        return diagnostics

    def _validate_relative_relocation(
        self, tree: ast.Module, source_module: str, target_module: str
    ) -> list[str]:
        from cmm.transformations.relative_import_resolver import RelativeImportResolver

        resolver = RelativeImportResolver()
        diagnostics: list[str] = []
        for node in tree.body:
            if not isinstance(node, ast.ImportFrom) or node.level == 0:
                continue
            resolution = resolver.resolve(source_module, node.level, node.module or "")
            if resolution is None or resolver.render_relative(
                target_module, resolution.absolute_module
            ) is None:
                diagnostics.append(
                    f"Relative import from {source_module} cannot be preserved in {target_module}."
                )
        return diagnostics

    def _validate_package_move(self, context: Any, operation: Any, *, rename: bool) -> list[str]:
        source = operation.source_package
        target = operation.target_package
        diagnostics = self._validate_distinct_names(source, target, "package")
        if rename and source.rpartition(".")[0] != target.rpartition(".")[0]:
            diagnostics.append("RenamePackage requires source and target under the same parent.")
        if target.startswith(source + "."):
            diagnostics.append("A package cannot be moved inside itself.")
        source_path = context.resolve_project_path(Path(*source.split(".")))
        target_path = context.resolve_project_path(Path(*target.split(".")))
        diagnostics.extend(self._safe_source_path(context, source_path))
        if not source_path.is_dir() or not (source_path / "__init__.py").is_file():
            diagnostics.append(f"Source is not a regular Python package: {source}.")
        if target_path.exists():
            diagnostics.append(f"Target package already exists: {target}.")
        create_parents = bool(getattr(operation, "create_target_parents", False))
        parent_parts = target.split(".")[:-1]
        parent = context.resolve_project_path(Path(*parent_parts)) if parent_parts else context.project_root
        if parent != context.project_root and not parent.is_dir() and not create_parents:
            diagnostics.append(f"Target package parent does not exist: {'.'.join(parent_parts)}.")
        if parent.is_dir() and parent != context.project_root and not (parent / "__init__.py").is_file():
            diagnostics.append(f"Namespace package target is ambiguous: {'.'.join(parent_parts)}.")
        diagnostics.extend(self._dynamic_or_shadowed_references(context, (source,)))
        module_moves = tuple(
            (item.module_name, target + item.module_name[len(source):])
            for item in context.semantic_context.snapshot.modules
            if item.module_name == source or item.module_name.startswith(source + ".")
        )
        diagnostics.extend(self._validate_relative_rewrites(context, module_moves))
        return diagnostics

    def _validate_relative_rewrites(
        self, context: Any, moves: tuple[tuple[str, str], ...]
    ) -> list[str]:
        from cmm.transformations.relative_import_resolver import RelativeImportResolver

        resolver = RelativeImportResolver()
        ordered = tuple(sorted(moves, key=lambda item: len(item[0]), reverse=True))

        def mapped(module: str) -> str:
            for source, target in ordered:
                if module == source:
                    return target
                if module.startswith(source + "."):
                    return target + module[len(source):]
            return module

        diagnostics = []
        sources = tuple(source for source, _ in ordered)
        for module in context.semantic_context.snapshot.modules:
            if module.parsed_module is None:
                continue
            tree = ast.parse(module.parsed_module.code)
            for node in tree.body:
                if not isinstance(node, ast.ImportFrom):
                    continue
                resolution = resolver.resolve(
                    module.module_name,
                    node.level,
                    node.module or "",
                    consumer_is_package=module.path.name == "__init__.py",
                )
                if resolution is None:
                    diagnostics.append(f"Relative import in {module.module_name} is ambiguous.")
                    continue
                related = any(
                    resolution.absolute_module == source
                    or resolution.absolute_module.startswith(source + ".")
                    for source in sources
                )
                if any(alias.name == "*" for alias in node.names) and related:
                    diagnostics.append(f"Wildcard import in {module.module_name} is unsupported.")
                new_consumer = mapped(module.module_name)
                new_source = mapped(resolution.absolute_module)
                relative_targets = {new_source}
                if new_source == resolution.absolute_module:
                    for alias in node.names:
                        candidate = f"{resolution.absolute_module}.{alias.name}"
                        mapped_candidate = mapped(candidate)
                        if mapped_candidate != candidate:
                            relative_targets.add(mapped_candidate.rpartition(".")[0])
                if node.level and (
                    new_consumer != module.module_name
                    or relative_targets != {resolution.absolute_module}
                ):
                    for target in relative_targets:
                        if resolver.render_relative(
                            new_consumer,
                            target,
                            consumer_is_package=module.path.name == "__init__.py",
                        ) is None:
                            diagnostics.append(
                                f"Relative import from {module.module_name} to {target} cannot be preserved."
                            )
        return diagnostics

    def _validate_split_dependencies(
        self,
        tree: ast.Module,
        operation: SplitModuleOperation,
        definitions: dict[str, ast.AST],
    ) -> list[str]:
        group_for = {
            symbol: group.target_module for group in operation.groups for symbol in group.symbols
        }
        edges: set[tuple[str, str]] = set()
        imported = self._import_bindings(tree)
        for symbol, target in group_for.items():
            node = definitions.get(symbol)
            if node is None:
                continue
            local = self._bound_names(node)
            for name in self._loaded_names(node) - local - set(dir(builtins)):
                dependency_target = group_for.get(name)
                if dependency_target is not None and dependency_target != target:
                    edges.add((target, dependency_target))
                elif name not in definitions and name not in imported:
                    return [f"Unresolvable dependency {name} used by {symbol}."]
        graph = {group.target_module: set() for group in operation.groups}
        for source, target in edges:
            graph[source].add(target)
        if self._has_cycle(graph):
            return ["Split groups introduce a circular dependency."]
        return []

    def _dynamic_or_shadowed_references(
        self,
        context: Any,
        sources: tuple[str, ...],
        symbols: set[str] | None = None,
    ) -> list[str]:
        diagnostics: list[str] = []
        for module in context.semantic_context.snapshot.modules:
            if module.parsed_module is None:
                diagnostics.append(f"Python module is not analyzable: {module.module_name}.")
                continue
            tree = ast.parse(module.parsed_module.code, filename=str(module.path))
            aliases: set[str] = set()
            for node in tree.body:
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if any(alias.name == source or alias.name.startswith(source + ".") for source in sources):
                            aliases.add(alias.asname or alias.name.split(".", 1)[0])
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    call_name = self._dotted_name(node.func)
                    if call_name in {"__import__", "importlib.import_module"} and node.args:
                        value = node.args[0]
                        if isinstance(value, ast.Constant) and isinstance(value.value, str):
                            if any(value.value == source or value.value.startswith(source + ".") for source in sources):
                                diagnostics.append(
                                    f"Dynamic import of {value.value} in {module.module_name} is unsupported."
                                )
                    if call_name == "getattr" and len(node.args) >= 2:
                        name = node.args[1]
                        target_name = self._dotted_name(node.args[0])
                        if (
                            isinstance(name, ast.Constant)
                            and isinstance(name.value, str)
                            and (
                                target_name in aliases
                                or any(
                                    target_name == source
                                    or target_name.startswith(source + ".")
                                    for source in sources
                                )
                            )
                        ):
                            if symbols is None or name.value in symbols:
                                diagnostics.append(
                                    f"Dynamic attribute reference in {module.module_name} is unsupported."
                                )
                    if call_name in {"globals", "locals", "vars"} and (
                        aliases
                        or any(
                            module.module_name == source
                            or module.module_name.startswith(source + ".")
                            for source in sources
                        )
                    ):
                        diagnostics.append(
                            f"Dynamic namespace access in {module.module_name} is unsupported."
                        )
                if isinstance(node, ast.arg) and node.arg in aliases:
                    diagnostics.append(f"Shadowed module binding {node.arg} in {module.module_name}.")
                if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store) and node.id in aliases:
                    diagnostics.append(f"Reassigned module binding {node.id} in {module.module_name}.")
        return sorted(set(diagnostics))

    def _existing_module_path(self, context: Any, module: str) -> Path:
        matches = [
            item.path.resolve()
            for item in context.semantic_context.snapshot.modules
            if item.module_name == module
        ]
        if len(matches) != 1 or not matches[0].is_file():
            raise ValueError(f"Source module does not exist uniquely: {module}.")
        return matches[0]

    def _module_exists(self, context: Any, module: str) -> bool:
        return any(
            item.module_name == module for item in context.semantic_context.snapshot.modules
        )

    def _safe_source_path(self, context: Any, path: Path) -> list[str]:
        context.resolve_project_path(path)
        relative = path.relative_to(context.project_root)
        current = context.project_root
        for part in relative.parts:
            current /= part
            if current.is_symlink():
                return [f"Symlink paths are unsupported for reorganization: {current}."]
        return []

    def _validate_target_package(self, context: Any, module: str, create: bool) -> list[str]:
        parts = module.split(".")[:-1]
        if not parts:
            return []
        path = context.resolve_project_path(Path(*parts))
        if not path.exists():
            if not create:
                return [f"Target package does not exist: {'.'.join(parts)}."]
            current = context.project_root
            for index, part in enumerate(parts):
                current /= part
                if not current.exists():
                    continue
                if not current.is_dir() or not (current / "__init__.py").is_file():
                    name = ".".join(parts[: index + 1])
                    return [f"Target package is ambiguous or not regular: {name}."]
            return []
        if not path.is_dir() or not (path / "__init__.py").is_file():
            return [f"Target package is ambiguous or not regular: {'.'.join(parts)}."]
        return self._safe_source_path(context, path)

    def _validate_distinct_names(self, source: str, target: str, kind: str) -> list[str]:
        parts = (*source.split("."), *target.split("."))
        if not source or not target or any(part in {"", ".", ".."} for part in parts):
            return [f"Invalid {kind} name."]
        if source == target:
            return [f"Source and target {kind} must differ."]
        return []

    def _loaded_names(self, node: ast.AST) -> set[str]:
        return {item.id for item in ast.walk(node) if isinstance(item, ast.Name) and isinstance(item.ctx, ast.Load)}

    def _bound_names(self, node: ast.AST) -> set[str]:
        result = {item.id for item in ast.walk(node) if isinstance(item, ast.Name) and isinstance(item.ctx, ast.Store)}
        for item in ast.walk(node):
            if isinstance(item, ast.arg):
                result.add(item.arg)
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            result.add(node.name)
        return result

    def _import_bindings(self, tree: ast.Module) -> set[str]:
        result: set[str] = set()
        for node in tree.body:
            if isinstance(node, ast.Import):
                result.update(alias.asname or alias.name.split(".", 1)[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                result.update(alias.asname or alias.name for alias in node.names)
        return result

    def _dotted_name(self, node: ast.AST) -> str:
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            prefix = self._dotted_name(node.value)
            return f"{prefix}.{node.attr}" if prefix else node.attr
        return ""

    def _has_cycle(self, graph: dict[str, set[str]]) -> bool:
        indegree = {node: 0 for node in graph}
        for targets in graph.values():
            for target in targets:
                indegree[target] += 1
        ready = [node for node, degree in indegree.items() if degree == 0]
        visited = 0
        while ready:
            node = ready.pop()
            visited += 1
            for target in graph[node]:
                indegree[target] -= 1
                if indegree[target] == 0:
                    ready.append(target)
        return visited != len(graph)
