"""LibCST transformer for moving selected top-level symbols and imports."""

from __future__ import annotations

import libcst as cst

from cmm.transformations.relative_import_resolver import RelativeImportResolver


class AppendSelectedSymbolsTransformer(cst.CSTTransformer):
    def __init__(
        self,
        symbols: tuple[cst.FunctionDef | cst.ClassDef, ...],
        imports: tuple[cst.SimpleStatementLine, ...] = (),
    ) -> None:
        self._symbols = symbols
        self._imports = imports

    def leave_Module(self, original_node: cst.Module, updated_node: cst.Module) -> cst.Module:
        return updated_node.with_changes(body=(*self._imports, *updated_node.body, *self._symbols))


class DeleteSelectedSymbolsTransformer(cst.CSTTransformer):
    def __init__(self, names: frozenset[str]) -> None:
        self._names = names

    def leave_Module(self, original_node: cst.Module, updated_node: cst.Module) -> cst.Module:
        return updated_node.with_changes(
            body=tuple(
                statement for statement in updated_node.body
                if not isinstance(statement, (cst.FunctionDef, cst.ClassDef))
                or statement.name.value not in self._names
            )
        )


class UpdateSelectedImportsTransformer(cst.CSTTransformer):
    def __init__(
        self,
        old_module: str,
        new_module: str,
        symbols: frozenset[str],
        *,
        consumer_module: str = "",
        consumer_is_package: bool = False,
    ) -> None:
        self._old_module = old_module
        self._new_module = new_module
        self._symbols = symbols
        self._consumer_module = consumer_module
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
        original_import = original_node.body[0]
        if original_import.module is None or isinstance(original_import.names, cst.ImportStar):
            return updated_node
        resolution = self._resolver.resolve(
            self._consumer_module,
            len(original_import.relative),
            self._name(original_import.module),
            consumer_is_package=self._consumer_is_package,
        )
        if resolution is None or resolution.absolute_module != self._old_module:
            return updated_node
        moved = [alias for alias in original_import.names if self._name(alias.name) in self._symbols]
        remaining = [alias for alias in original_import.names if self._name(alias.name) not in self._symbols]
        if not moved:
            return updated_node
        relative = bool(original_import.relative)
        target = self._resolver.render_relative(
            self._consumer_module,
            self._new_module,
            consumer_is_package=self._consumer_is_package,
        ) if relative else None
        if relative and target is None:
            self.blocking_reason = (
                f"Cannot preserve a relative import from {self._consumer_module} "
                f"to {self._new_module}."
            )
            return updated_node
        new_import = original_import.with_changes(
            module=self._module(target.module if target is not None else self._new_module),
            relative=tuple(cst.Dot() for _ in range(target.level)) if target is not None else (),
            names=(
                tuple(moved)
                if not remaining
                else self._split_aliases(moved, original_import)
            ),
        )
        self.changed = True
        if not remaining:
            return updated_node.with_changes(body=(new_import,))
        old_import = original_import.with_changes(
            names=self._split_aliases(remaining, original_import)
        )
        return cst.FlattenSentinel((
            updated_node.with_changes(body=(old_import,)),
            cst.SimpleStatementLine(body=(new_import,)),
        ))

    def _normalize(self, aliases: list[cst.ImportAlias]) -> tuple[cst.ImportAlias, ...]:
        return tuple(
            alias.with_changes(comma=cst.Comma() if index < len(aliases) - 1 else cst.MaybeSentinel.DEFAULT)
            for index, alias in enumerate(aliases)
        )

    def _split_aliases(
        self,
        aliases: list[cst.ImportAlias],
        original: cst.ImportFrom,
    ) -> tuple[cst.ImportAlias, ...]:
        if original.lpar is not None:
            result = list(aliases)
            last = result[-1]
            if isinstance(last.comma, cst.Comma) and isinstance(
                last.comma.whitespace_after, cst.ParenthesizedWhitespace
            ):
                result[-1] = last.with_changes(comma=last.comma.with_changes(
                    whitespace_after=last.comma.whitespace_after.with_changes(
                        last_line=cst.SimpleWhitespace("")
                    )
                ))
            return tuple(result)
        return self._normalize(aliases)

    def _name(self, node: cst.Name | cst.Attribute) -> str:
        if isinstance(node, cst.Name):
            return node.value
        return f"{self._name(node.value)}.{node.attr.value}"

    def _module(self, name: str) -> cst.Name | cst.Attribute:
        parts = name.split(".")
        node: cst.Name | cst.Attribute = cst.Name(parts[0])
        for part in parts[1:]:
            node = cst.Attribute(value=node, attr=cst.Name(part))
        return node
