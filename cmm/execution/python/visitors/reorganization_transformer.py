"""LibCST rewrites for module layout and selected-symbol destinations."""

from __future__ import annotations

from collections import defaultdict

import libcst as cst

from cmm.transformations.relative_import_resolver import RelativeImportResolver


def dotted_name(node: cst.CSTNode | None) -> str:
    if isinstance(node, cst.Name):
        return node.value
    if isinstance(node, cst.Attribute):
        prefix = dotted_name(node.value)
        return f"{prefix}.{node.attr.value}" if prefix else node.attr.value
    return ""


def module_node(module: str) -> cst.Name | cst.Attribute:
    expression = cst.parse_expression(module)
    if not isinstance(expression, cst.Name | cst.Attribute):
        raise ValueError(f"Invalid module name: {module}.")
    return expression


class ModuleReferenceRewriteTransformer(cst.CSTTransformer):
    """Rewrite statically bound module paths while preserving import style."""

    def __init__(
        self,
        module_moves: tuple[tuple[str, str], ...],
        *,
        consumer_module: str,
        consumer_is_package: bool,
    ) -> None:
        self._moves = tuple(sorted(module_moves, key=lambda item: len(item[0]), reverse=True))
        self._consumer = consumer_module
        self._new_consumer = self._mapped(consumer_module)
        self._consumer_is_package = consumer_is_package
        self._resolver = RelativeImportResolver()
        self._unaliased: dict[str, str] = {}
        self.changed = False
        self.blocking_reason: str | None = None

    def visit_ImportFrom(self, node: cst.ImportFrom) -> bool:
        return False

    def leave_SimpleStatementLine(
        self,
        original_node: cst.SimpleStatementLine,
        updated_node: cst.SimpleStatementLine,
    ) -> cst.BaseStatement | cst.FlattenSentinel[cst.BaseStatement]:
        if len(original_node.body) != 1 or not isinstance(original_node.body[0], cst.ImportFrom):
            return updated_node
        original_import = original_node.body[0]
        if isinstance(original_import.names, cst.ImportStar):
            return updated_node
        raw = dotted_name(original_import.module)
        resolution = self._resolver.resolve(
            self._consumer,
            len(original_import.relative),
            raw,
            consumer_is_package=self._consumer_is_package,
        )
        if resolution is None:
            return updated_node
        old_absolute = resolution.absolute_module
        new_absolute = self._mapped(old_absolute)
        groups: dict[str, list[cst.ImportAlias]] = defaultdict(list)
        changed = new_absolute != old_absolute or self._new_consumer != self._consumer
        for alias in original_import.names:
            imported = dotted_name(alias.name)
            target_source = new_absolute
            rewritten = alias
            if new_absolute == old_absolute:
                candidate = f"{old_absolute}.{imported}" if old_absolute else imported
                mapped_candidate = self._mapped(candidate)
                if mapped_candidate != candidate:
                    target_source, _, new_leaf = mapped_candidate.rpartition(".")
                    if alias.asname is None and new_leaf != imported:
                        rewritten = alias.with_changes(
                            name=cst.Name(new_leaf),
                            asname=cst.AsName(cst.Name(imported)),
                        )
                    else:
                        rewritten = alias.with_changes(name=cst.Name(new_leaf))
                    changed = True
            groups[target_source].append(rewritten)
        if not changed:
            return updated_node
        if len(groups) == 1:
            target_source, aliases = next(iter(groups.items()))
            module, relative = self._render_import_target(
                original_import, target_source
            )
            if module is None:
                return updated_node
            self.changed = True
            return updated_node.with_changes(body=(original_import.with_changes(
                module=module,
                relative=relative,
                names=tuple(aliases),
            ),))
        lines = []
        for target_source, aliases in groups.items():
            module, relative = self._render_import_target(original_import, target_source)
            if module is None:
                return updated_node
            normalized = tuple(
                alias.with_changes(
                    comma=(
                        cst.Comma(whitespace_after=cst.SimpleWhitespace(" "))
                        if index < len(aliases) - 1
                        else cst.MaybeSentinel.DEFAULT
                    )
                )
                for index, alias in enumerate(aliases)
            )
            lines.append(cst.SimpleStatementLine(body=(original_import.with_changes(
                module=module,
                relative=relative,
                names=normalized,
                lpar=None,
                rpar=None,
            ),)))
        self.changed = True
        return cst.FlattenSentinel(tuple(lines))

    def _render_import_target(
        self, original_import: cst.ImportFrom, target_source: str
    ) -> tuple[cst.Name | cst.Attribute | None, tuple[cst.Dot, ...]]:
        if not original_import.relative:
            return module_node(target_source), ()
        rendered = self._resolver.render_relative(
            self._new_consumer,
            target_source,
            consumer_is_package=self._consumer_is_package,
        )
        if rendered is None:
            self.blocking_reason = (
                f"Cannot preserve relative import from {self._consumer} to {target_source}."
            )
            return None, ()
        return module_node(rendered.module), tuple(cst.Dot() for _ in range(rendered.level))

    def leave_Import(self, original_node: cst.Import, updated_node: cst.Import) -> cst.Import:
        aliases = []
        changed = False
        for original_alias, alias in zip(original_node.names, updated_node.names, strict=True):
            old = dotted_name(original_alias.name)
            new = self._mapped(old)
            if old != new:
                if original_alias.asname is None:
                    self._unaliased[old] = new
                alias = alias.with_changes(name=module_node(new))
                changed = True
            aliases.append(alias)
        if changed:
            self.changed = True
            return updated_node.with_changes(names=tuple(aliases))
        return updated_node

    def leave_Attribute(
        self, original_node: cst.Attribute, updated_node: cst.Attribute
    ) -> cst.BaseExpression:
        old = dotted_name(original_node)
        for source, target in sorted(self._unaliased.items(), key=lambda item: len(item[0]), reverse=True):
            if old == source or old.startswith(source + "."):
                self.changed = True
                return cst.parse_expression(target + old[len(source):])
        return updated_node

    def _mapped(self, module: str) -> str:
        for source, target in self._moves:
            if module == source:
                return target
            if module.startswith(source + "."):
                return target + module[len(source):]
        return module


class SymbolDestinationRewriteTransformer(cst.CSTTransformer):
    """Split from-import aliases according to each symbol's new module."""

    def __init__(
        self,
        symbol_moves: tuple[tuple[str, str, str], ...],
        *,
        consumer_module: str,
        consumer_is_package: bool,
    ) -> None:
        self._destinations = {(source, symbol): target for source, symbol, target in symbol_moves}
        self._consumer = consumer_module
        self._consumer_is_package = consumer_is_package
        self._resolver = RelativeImportResolver()
        self.changed = False
        self.blocking_reason: str | None = None

    def visit_ImportFrom(self, node: cst.ImportFrom) -> bool:
        return False

    def leave_SimpleStatementLine(
        self,
        original_node: cst.SimpleStatementLine,
        updated_node: cst.SimpleStatementLine,
    ) -> cst.BaseStatement | cst.FlattenSentinel[cst.BaseStatement]:
        if len(original_node.body) != 1 or not isinstance(original_node.body[0], cst.ImportFrom):
            return updated_node
        statement = original_node.body[0]
        if isinstance(statement.names, cst.ImportStar):
            return updated_node
        resolution = self._resolver.resolve(
            self._consumer,
            len(statement.relative),
            dotted_name(statement.module),
            consumer_is_package=self._consumer_is_package,
        )
        if resolution is None:
            return updated_node
        groups: dict[str, list[cst.ImportAlias]] = defaultdict(list)
        changed = False
        for alias in statement.names:
            symbol = dotted_name(alias.name)
            target = self._destinations.get((resolution.absolute_module, symbol), resolution.absolute_module)
            groups[target].append(alias)
            changed = changed or target != resolution.absolute_module
        if not changed:
            return updated_node
        if len(groups) == 1:
            target, aliases = next(iter(groups.items()))
            module, relative = self._render_target(statement, target)
            if module is None:
                return updated_node
            self.changed = True
            return updated_node.with_changes(body=(statement.with_changes(
                module=module,
                relative=relative,
                names=tuple(aliases),
            ),))
        lines = []
        for target, aliases in groups.items():
            module, relative = self._render_target(statement, target)
            if module is None:
                return updated_node
            normalized = tuple(
                alias.with_changes(
                    comma=(
                        cst.Comma(whitespace_after=cst.SimpleWhitespace(" "))
                        if index < len(aliases) - 1
                        else cst.MaybeSentinel.DEFAULT
                    )
                )
                for index, alias in enumerate(aliases)
            )
            lines.append(cst.SimpleStatementLine(body=(statement.with_changes(
                module=module,
                relative=relative,
                names=normalized,
                lpar=None,
                rpar=None,
            ),)))
        self.changed = True
        return cst.FlattenSentinel(tuple(lines))

    def _render_target(
        self, statement: cst.ImportFrom, target: str
    ) -> tuple[cst.Name | cst.Attribute | None, tuple[cst.Dot, ...]]:
        if not statement.relative:
            return module_node(target), ()
        rendered = self._resolver.render_relative(
            self._consumer,
            target,
            consumer_is_package=self._consumer_is_package,
        )
        if rendered is None:
            self.blocking_reason = f"Cannot preserve relative import from {self._consumer} to {target}."
            return None, ()
        return module_node(rendered.module), tuple(cst.Dot() for _ in range(rendered.level))
