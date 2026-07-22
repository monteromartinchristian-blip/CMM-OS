"""Real filesystem and LibCST executors for project reorganization."""

from __future__ import annotations

import ast
from pathlib import Path
import shutil
from typing import Any

import libcst as cst

from cmm.execution.execution_result import ExecutionResult
from cmm.execution.operation_executor import OperationExecutor
from cmm.execution.python.visitors import (
    ModuleReferenceRewriteTransformer,
    SymbolDestinationRewriteTransformer,
)
from cmm.transformations.execution_request import ExecutionRequest
from cmm.transformations.operation import TransformationOperation
from cmm.transformations.operations import (
    MergeModulesOperation,
    MoveModuleOperation,
    MovePackageOperation,
    RenameModuleOperation,
    RenamePackageOperation,
    ReorganizationOperation,
    SplitModuleOperation,
)
from cmm.transformations.reorganization_validation import (
    ReorganizationValidator,
    top_level_symbols,
)


class PythonReorganizationExecutor(OperationExecutor):
    """Shared implementation used by concrete exact-type registry adapters."""

    operation_class: type[ReorganizationOperation]

    @property
    def operation_type(self) -> type[TransformationOperation]:
        return self.operation_class

    def execute(self, request: ExecutionRequest) -> ExecutionResult:
        operation = request.operation
        context = request.metadata.get("execution_context")
        if not isinstance(operation, ReorganizationOperation) or context is None:
            return ExecutionResult(False, operation, ("Invalid reorganization request.",))
        validation = ReorganizationValidator().validate(context, operation)
        if not validation.success:
            return ExecutionResult(False, operation, validation.diagnostics)
        try:
            if isinstance(operation, RenameModuleOperation | MoveModuleOperation):
                changed = self._move_module(context, operation)
            elif isinstance(operation, SplitModuleOperation):
                changed = self._split_module(context, operation)
            elif isinstance(operation, MergeModulesOperation):
                changed = self._merge_modules(context, operation)
            elif isinstance(operation, RenamePackageOperation | MovePackageOperation):
                changed = self._move_package(context, operation)
            else:
                return ExecutionResult(False, operation, ("Unsupported reorganization operation.",))
        except (OSError, ValueError, cst.ParserSyntaxError) as error:
            return ExecutionResult(False, operation, (str(error),))
        changed_paths = tuple(sorted(set(changed)))
        deleted_paths = tuple(path for path in changed_paths if not path.exists())
        return ExecutionResult(
            True,
            operation,
            created_paths=changed_paths,
            metadata={"deleted_paths": deleted_paths},
        )

    def _move_module(self, context: Any, operation: Any) -> tuple[Path, ...]:
        moves = ((operation.source_module, operation.target_module),)
        updates = self._rewrite_project(context, moves, ())
        source = self._module_info(context, operation.source_module).path.resolve()
        target = context.module_path(operation.target_module)
        if bool(getattr(operation, "create_target_package", False)):
            self._create_package_parents(context, operation.target_module.split(".")[:-1])
        target.parent.mkdir(parents=True, exist_ok=True)
        source.replace(target)
        changed = [source, target]
        for old_path, module_name, code in updates:
            output = target if module_name == operation.source_module else old_path
            if output.read_text(encoding="utf-8") != code:
                output.write_text(code, encoding="utf-8")
                changed.append(output)
        if bool(getattr(operation, "delete_empty_source_package", False)):
            self._remove_empty_parents(source.parent, context.project_root)
        return tuple(changed)

    def _move_package(self, context: Any, operation: Any) -> tuple[Path, ...]:
        graph_modules = tuple(item.module_name for item in context.semantic_context.snapshot.modules)
        moves = tuple(
            (module, operation.target_package + module[len(operation.source_package):])
            for module in graph_modules
            if module == operation.source_package or module.startswith(operation.source_package + ".")
        )
        updates = self._rewrite_project(context, moves, ())
        source = context.resolve_project_path(Path(*operation.source_package.split(".")))
        target = context.resolve_project_path(Path(*operation.target_package.split(".")))
        if bool(getattr(operation, "create_target_parents", False)):
            self._create_package_parents(context, operation.target_package.split(".")[:-1])
        target.parent.mkdir(parents=True, exist_ok=True)
        source.replace(target)
        changed = [source, target]
        for old_path, module_name, code in updates:
            if old_path.is_relative_to(source):
                output = target / old_path.relative_to(source)
            else:
                output = old_path
            if output.read_text(encoding="utf-8") != code:
                output.write_text(code, encoding="utf-8")
                changed.append(output)
        if bool(getattr(operation, "delete_empty_source_parents", False)):
            self._remove_empty_parents(source.parent, context.project_root)
        return tuple(changed)

    def _split_module(self, context: Any, operation: SplitModuleOperation) -> tuple[Path, ...]:
        source_info = self._module_info(context, operation.source_module)
        source_module = source_info.parsed_module
        if source_module is None:
            raise ValueError(f"Source module is not analyzable: {operation.source_module}.")
        source_tree = ast.parse(source_module.code)
        ast_symbols = top_level_symbols(source_tree)
        source_public = self._literal_all_names(source_tree)
        target_for = {
            symbol: group.target_module for group in operation.groups for symbol in group.symbols
        }
        selected = set(target_for)
        source_imports = tuple(
            statement for statement in source_module.body if self._is_import_statement(statement)
        )
        statement_names = {id(statement): self._statement_names(statement) for statement in source_module.body}
        destinations: dict[str, list[cst.BaseStatement]] = {
            group.target_module: [] for group in operation.groups
        }
        for statement in source_module.body:
            names = statement_names[id(statement)]
            matched = names & selected
            if matched:
                if names - selected:
                    raise ValueError("A multi-binding assignment cannot be partially split.")
                destination_names = {target_for[name] for name in matched}
                if len(destination_names) != 1:
                    raise ValueError("One statement cannot be split across multiple destinations.")
                destinations[destination_names.pop()].append(statement)
        cross_imports = self._split_dependency_imports(
            source_tree, ast_symbols, target_for, operation.source_module
        )
        changed: list[Path] = []
        for target, statements in destinations.items():
            selected_names = {
                symbol for symbol, destination in target_for.items() if destination == target
            }
            loaded = set().union(*(
                self._loaded_names(ast_symbols[symbol]) for symbol in selected_names
            )) if selected_names else set()
            body = [
                self._relocate_import_statement(statement, operation.source_module, target)
                for statement in source_imports
                if self._import_bindings(statement) & loaded
                or self._is_future_import(statement)
            ]
            body.extend(cst.parse_statement(line) for line in cross_imports.get(target, ()))
            public_names = tuple(name for name in source_public if name in selected_names)
            if public_names:
                body.append(cst.parse_statement(f"__all__ = {list(public_names)!r}\n"))
            body.extend(statements)
            path = context.module_path(target)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(cst.Module(body=tuple(body)).code, encoding="utf-8")
            changed.append(path)
        source_body = tuple(
            statement for statement in source_module.body
            if not (statement_names[id(statement)] & selected)
        )
        remaining_imports = self._remaining_source_imports(
            source_tree, ast_symbols, target_for, selected
        )
        source_body_list = list(source_body)
        source_insertion = self._after_header(source_body_list)
        source_body_list[source_insertion:source_insertion] = [
            cst.parse_statement(line) for line in remaining_imports
        ]
        updated_source = cst.Module(body=tuple(source_body_list))
        updated_source = updated_source.visit(_RemoveLiteralAllNames(selected))
        source_path = source_info.path.resolve()
        source_path.write_text(updated_source.code, encoding="utf-8")
        changed.append(source_path)
        symbol_moves = tuple(
            (operation.source_module, symbol, target)
            for symbol, target in sorted(target_for.items())
        )
        for path, module_name, code in self._rewrite_project(context, (), symbol_moves):
            if path == source_path or module_name in destinations:
                continue
            if path.read_text(encoding="utf-8") != code:
                path.write_text(code, encoding="utf-8")
                changed.append(path)
        if operation.delete_empty_source and not self._has_meaningful_body(updated_source):
            source_path.unlink()
        return tuple(changed)

    def _merge_modules(self, context: Any, operation: MergeModulesOperation) -> tuple[Path, ...]:
        source_infos = [self._module_info(context, source) for source in operation.source_modules]
        target_info = next(
            (item for item in context.semantic_context.snapshot.modules if item.module_name == operation.target_module),
            None,
        )
        target_body = list(target_info.parsed_module.body) if target_info and target_info.parsed_module else []
        target_public = (
            self._literal_all_names(ast.parse(target_info.parsed_module.code))
            if target_info and target_info.parsed_module
            else ()
        )
        target_body = [statement for statement in target_body if not self._is_all_statement(statement)]
        import_codes = {
            cst.Module(body=(statement,)).code
            for statement in target_body if self._is_import_statement(statement)
        }
        imports: list[cst.BaseStatement] = []
        symbols: list[cst.BaseStatement] = []
        symbol_moves: list[tuple[str, str, str]] = []
        public_names = list(target_public)
        for source, info in zip(operation.source_modules, source_infos, strict=True):
            assert info.parsed_module is not None
            source_tree = ast.parse(info.parsed_module.code)
            for name in self._literal_all_names(source_tree):
                if name not in public_names:
                    public_names.append(name)
            loaded = set().union(*(
                self._loaded_names(node) for node in top_level_symbols(source_tree).values()
            ))
            for statement in info.parsed_module.body:
                if self._is_import_statement(statement):
                    if self._is_internal_merge_import(
                        statement, source, set(operation.source_modules), info.path.name == "__init__.py"
                    ):
                        continue
                    if not (
                        self._import_bindings(statement) & loaded
                        or self._is_future_import(statement)
                    ):
                        continue
                    statement = self._relocate_import_statement(
                        statement, source, operation.target_module
                    )
                    code = cst.Module(body=(statement,)).code
                    if code not in import_codes:
                        imports.append(statement)
                        import_codes.add(code)
                    continue
                names = self._statement_names(statement)
                if not names:
                    continue
                symbols.append(statement)
                symbol_moves.extend((source, name, operation.target_module) for name in sorted(names))
        future_imports = [statement for statement in imports if self._is_future_import(statement)]
        normal_imports = [statement for statement in imports if not self._is_future_import(statement)]
        future_insertion = self._after_docstring(target_body)
        target_body[future_insertion:future_insertion] = future_imports
        insertion = self._after_header(target_body)
        target_body[insertion:insertion] = normal_imports
        symbol_insertion = self._after_header(target_body)
        ordered_symbols = self._order_symbol_statements(
            [*target_body[symbol_insertion:], *symbols]
        )
        target_body = [*target_body[:symbol_insertion], *ordered_symbols]
        if public_names:
            target_body.append(cst.parse_statement(f"__all__ = {public_names!r}\n"))
        target_path = context.module_path(operation.target_module)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(cst.Module(body=tuple(target_body)).code, encoding="utf-8")
        changed = [target_path]
        updates = self._rewrite_project(
            context,
            tuple((source, operation.target_module) for source in operation.source_modules),
            tuple(symbol_moves),
        )
        source_paths = {info.path.resolve() for info in source_infos}
        for path, module_name, code in updates:
            if path in source_paths or module_name == operation.target_module:
                continue
            if path.read_text(encoding="utf-8") != code:
                path.write_text(code, encoding="utf-8")
                changed.append(path)
        if not operation.keep_sources:
            for path in source_paths:
                path.unlink()
                changed.append(path)
        return tuple(changed)

    def _rewrite_project(
        self,
        context: Any,
        module_moves: tuple[tuple[str, str], ...],
        symbol_moves: tuple[tuple[str, str, str], ...],
    ) -> tuple[tuple[Path, str, str], ...]:
        updates = []
        for info in context.semantic_context.snapshot.modules:
            if info.parsed_module is None:
                raise ValueError(f"Python module is not analyzable: {info.module_name}.")
            updated = info.parsed_module
            if module_moves:
                module_transformer = ModuleReferenceRewriteTransformer(
                    module_moves,
                    consumer_module=info.module_name,
                    consumer_is_package=info.path.name == "__init__.py",
                )
                updated = updated.visit(module_transformer)
                if module_transformer.blocking_reason:
                    raise ValueError(module_transformer.blocking_reason)
            if symbol_moves:
                symbol_transformer = SymbolDestinationRewriteTransformer(
                    symbol_moves,
                    consumer_module=info.module_name,
                    consumer_is_package=info.path.name == "__init__.py",
                )
                updated = updated.visit(symbol_transformer)
                if symbol_transformer.blocking_reason:
                    raise ValueError(symbol_transformer.blocking_reason)
            updates.append((info.path.resolve(), info.module_name, updated.code))
        return tuple(updates)

    def _split_dependency_imports(
        self,
        tree: ast.Module,
        definitions: dict[str, ast.AST],
        target_for: dict[str, str],
        source_module: str,
    ) -> dict[str, tuple[str, ...]]:
        result: dict[str, set[str]] = {target: set() for target in set(target_for.values())}
        for symbol, target in target_for.items():
            node = definitions[symbol]
            local = self._bound_names(node)
            loaded = self._loaded_names(node) - local
            for dependency in sorted(loaded & set(definitions)):
                dependency_target = target_for.get(dependency)
                if dependency_target is None:
                    result[target].add(f"from {source_module} import {dependency}\n")
                elif dependency_target != target:
                    result[target].add(f"from {dependency_target} import {dependency}\n")
        return {target: tuple(sorted(lines)) for target, lines in result.items()}

    def _remaining_source_imports(
        self,
        tree: ast.Module,
        definitions: dict[str, ast.AST],
        target_for: dict[str, str],
        selected: set[str],
    ) -> tuple[str, ...]:
        lines = set()
        for symbol, node in definitions.items():
            if symbol in selected:
                continue
            for dependency in sorted(self._loaded_names(node) & selected):
                lines.add(f"from {target_for[dependency]} import {dependency}\n")
        return tuple(sorted(lines))

    def _module_info(self, context: Any, module: str) -> Any:
        info = next(
            (item for item in context.semantic_context.snapshot.modules if item.module_name == module),
            None,
        )
        if info is None or info.parsed_module is None:
            raise ValueError(f"Module is not analyzable: {module}.")
        return info

    def _create_package_parents(self, context: Any, parts: list[str]) -> None:
        current = context.project_root
        for part in parts:
            current /= part
            current.mkdir(exist_ok=True)
            init = current / "__init__.py"
            if not init.exists():
                init.write_text("", encoding="utf-8")

    def _remove_empty_parents(self, path: Path, root: Path) -> None:
        while path != root and path.is_relative_to(root):
            entries = list(path.iterdir())
            if entries == [path / "__init__.py"] and entries[0].read_text(encoding="utf-8") == "":
                entries[0].unlink()
            try:
                path.rmdir()
            except OSError:
                return
            path = path.parent

    def _statement_names(self, statement: cst.BaseStatement) -> set[str]:
        if isinstance(statement, cst.FunctionDef | cst.ClassDef):
            return {statement.name.value}
        if not isinstance(statement, cst.SimpleStatementLine):
            return set()
        result = set()
        for item in statement.body:
            if isinstance(item, cst.Assign):
                result.update(
                    target.target.value for target in item.targets
                    if isinstance(target.target, cst.Name) and target.target.value != "__all__"
                )
            elif isinstance(item, cst.AnnAssign) and isinstance(item.target, cst.Name):
                if item.target.value != "__all__":
                    result.add(item.target.value)
        return result

    def _is_import_statement(self, statement: cst.BaseStatement) -> bool:
        return isinstance(statement, cst.SimpleStatementLine) and all(
            isinstance(item, cst.Import | cst.ImportFrom) for item in statement.body
        )

    def _import_bindings(self, statement: cst.BaseStatement) -> set[str]:
        from cmm.execution.python.visitors.reorganization_transformer import dotted_name

        result: set[str] = set()
        if not isinstance(statement, cst.SimpleStatementLine):
            return result
        for item in statement.body:
            if isinstance(item, cst.Import):
                result.update(
                    alias.asname.name.value
                    if alias.asname is not None
                    else dotted_name(alias.name).split(".", 1)[0]
                    for alias in item.names
                )
            elif isinstance(item, cst.ImportFrom) and not isinstance(item.names, cst.ImportStar):
                result.update(
                    alias.asname.name.value
                    if alias.asname is not None
                    else dotted_name(alias.name)
                    for alias in item.names
                )
        return result

    def _is_future_import(self, statement: cst.BaseStatement) -> bool:
        from cmm.execution.python.visitors.reorganization_transformer import dotted_name

        return isinstance(statement, cst.SimpleStatementLine) and any(
            isinstance(item, cst.ImportFrom) and dotted_name(item.module) == "__future__"
            for item in statement.body
        )

    def _relocate_import_statement(
        self, statement: cst.BaseStatement, source_module: str, target_module: str
    ) -> cst.BaseStatement:
        from cmm.execution.python.visitors.reorganization_transformer import module_node, dotted_name
        from cmm.transformations.relative_import_resolver import RelativeImportResolver

        if not isinstance(statement, cst.SimpleStatementLine):
            return statement
        resolver = RelativeImportResolver()
        body = []
        for item in statement.body:
            if not isinstance(item, cst.ImportFrom) or not item.relative:
                body.append(item)
                continue
            resolution = resolver.resolve(source_module, len(item.relative), dotted_name(item.module))
            if resolution is None:
                raise ValueError(f"Relative import in {source_module} cannot be resolved.")
            rendered = resolver.render_relative(target_module, resolution.absolute_module)
            if rendered is None:
                raise ValueError(
                    f"Relative import from {source_module} cannot be preserved in {target_module}."
                )
            body.append(item.with_changes(
                module=module_node(rendered.module),
                relative=tuple(cst.Dot() for _ in range(rendered.level)),
            ))
        return statement.with_changes(body=tuple(body))

    def _is_internal_merge_import(
        self,
        statement: cst.BaseStatement,
        consumer_module: str,
        sources: set[str],
        consumer_is_package: bool,
    ) -> bool:
        from cmm.execution.python.visitors.reorganization_transformer import dotted_name
        from cmm.transformations.relative_import_resolver import RelativeImportResolver

        if not isinstance(statement, cst.SimpleStatementLine):
            return False
        resolver = RelativeImportResolver()
        for item in statement.body:
            if not isinstance(item, cst.ImportFrom):
                continue
            resolution = resolver.resolve(
                consumer_module,
                len(item.relative),
                dotted_name(item.module),
                consumer_is_package=consumer_is_package,
            )
            if resolution is not None and resolution.absolute_module in sources:
                return True
        return False

    def _loaded_names(self, node: ast.AST) -> set[str]:
        return {item.id for item in ast.walk(node) if isinstance(item, ast.Name) and isinstance(item.ctx, ast.Load)}

    def _bound_names(self, node: ast.AST) -> set[str]:
        result = {item.id for item in ast.walk(node) if isinstance(item, ast.Name) and isinstance(item.ctx, ast.Store)}
        result.update(item.arg for item in ast.walk(node) if isinstance(item, ast.arg))
        return result

    def _after_docstring(self, body: list[cst.BaseStatement]) -> int:
        if body and isinstance(body[0], cst.SimpleStatementLine):
            first = body[0]
            if (
                len(first.body) == 1
                and isinstance(first.body[0], cst.Expr)
                and isinstance(first.body[0].value, cst.SimpleString)
            ):
                return 1
        return 0

    def _after_header(self, body: list[cst.BaseStatement]) -> int:
        index = self._after_docstring(body)
        while index < len(body) and self._is_import_statement(body[index]):
            index += 1
        return index

    def _has_meaningful_body(self, module: cst.Module) -> bool:
        return any(self._statement_names(statement) for statement in module.body)

    def _literal_all_names(self, tree: ast.Module) -> tuple[str, ...]:
        for node in tree.body:
            if not isinstance(node, ast.Assign) or not any(
                isinstance(target, ast.Name) and target.id == "__all__"
                for target in node.targets
            ):
                continue
            if isinstance(node.value, (ast.List, ast.Tuple)) and all(
                isinstance(item, ast.Constant) and isinstance(item.value, str)
                for item in node.value.elts
            ):
                return tuple(item.value for item in node.value.elts)
        return ()

    def _is_all_statement(self, statement: cst.BaseStatement) -> bool:
        if not isinstance(statement, cst.SimpleStatementLine):
            return False
        return any(
            isinstance(item, cst.Assign)
            and any(
                isinstance(target.target, cst.Name) and target.target.value == "__all__"
                for target in item.targets
            )
            for item in statement.body
        )

    def _order_symbol_statements(
        self, statements: list[cst.BaseStatement]
    ) -> list[cst.BaseStatement]:
        if not statements:
            return []
        definitions: dict[str, int] = {}
        parsed: list[ast.AST] = []
        for index, statement in enumerate(statements):
            tree = ast.parse(cst.Module(body=(statement,)).code)
            if len(tree.body) != 1:
                raise ValueError("Merged symbol statements must be independently analyzable.")
            node = tree.body[0]
            parsed.append(node)
            for name in self._statement_names(statement):
                definitions[name] = index
        dependencies: dict[int, set[int]] = {index: set() for index in range(len(statements))}
        for index, node in enumerate(parsed):
            for name in self._eager_loaded_names(node):
                dependency = definitions.get(name)
                if dependency is not None and dependency != index:
                    dependencies[index].add(dependency)
        ready = sorted(index for index, deps in dependencies.items() if not deps)
        ordered: list[int] = []
        while ready:
            current = ready.pop(0)
            ordered.append(current)
            for candidate in range(len(statements)):
                if current not in dependencies[candidate]:
                    continue
                dependencies[candidate].remove(current)
                if not dependencies[candidate] and candidate not in ordered and candidate not in ready:
                    ready.append(candidate)
                    ready.sort()
        if len(ordered) != len(statements):
            raise ValueError("Merged symbols have cyclic eager initialization dependencies.")
        return [statements[index] for index in ordered]

    def _eager_loaded_names(self, node: ast.AST) -> set[str]:
        expressions: list[ast.AST] = []
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            value = getattr(node, "value", None)
            annotation = getattr(node, "annotation", None)
            expressions.extend(item for item in (value, annotation) if item is not None)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            expressions.extend(node.decorator_list)
            expressions.extend(node.args.defaults)
            expressions.extend(item for item in node.args.kw_defaults if item is not None)
            expressions.extend(
                argument.annotation
                for argument in (*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs)
                if argument.annotation is not None
            )
            if node.args.vararg is not None and node.args.vararg.annotation is not None:
                expressions.append(node.args.vararg.annotation)
            if node.args.kwarg is not None and node.args.kwarg.annotation is not None:
                expressions.append(node.args.kwarg.annotation)
            if node.returns is not None:
                expressions.append(node.returns)
        elif isinstance(node, ast.ClassDef):
            expressions.extend(node.decorator_list)
            expressions.extend(node.bases)
            expressions.extend(keyword.value for keyword in node.keywords)
            for statement in node.body:
                expressions.extend(self._eager_expressions_in_class(statement))
        return {
            item.id
            for expression in expressions
            for item in ast.walk(expression)
            if isinstance(item, ast.Name) and isinstance(item.ctx, ast.Load)
        }

    def _eager_expressions_in_class(self, node: ast.AST) -> list[ast.AST]:
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            return [
                item for item in (getattr(node, "value", None), getattr(node, "annotation", None))
                if item is not None
            ]
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names = self._eager_loaded_names(node)
            return [ast.Name(id=name, ctx=ast.Load()) for name in names]
        return []


class PythonRenameModuleExecutor(PythonReorganizationExecutor):
    operation_class = RenameModuleOperation


class PythonMoveModuleExecutor(PythonReorganizationExecutor):
    operation_class = MoveModuleOperation


class PythonSplitModuleExecutor(PythonReorganizationExecutor):
    operation_class = SplitModuleOperation


class PythonMergeModulesExecutor(PythonReorganizationExecutor):
    operation_class = MergeModulesOperation


class PythonRenamePackageExecutor(PythonReorganizationExecutor):
    operation_class = RenamePackageOperation


class PythonMovePackageExecutor(PythonReorganizationExecutor):
    operation_class = MovePackageOperation


class _RemoveLiteralAllNames(cst.CSTTransformer):
    def __init__(self, names: set[str]) -> None:
        self._names = names

    def leave_Assign(self, original_node: cst.Assign, updated_node: cst.Assign) -> cst.Assign:
        if not any(
            isinstance(target.target, cst.Name) and target.target.value == "__all__"
            for target in original_node.targets
        ) or not isinstance(updated_node.value, cst.List | cst.Tuple):
            return updated_node
        elements = tuple(
            element for element in updated_node.value.elements
            if element is None
            or not isinstance(element.value, cst.SimpleString)
            or element.value.evaluated_value not in self._names
        )
        return updated_node.with_changes(value=updated_node.value.with_changes(elements=elements))
