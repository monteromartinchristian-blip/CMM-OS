"""LibCST transformer for safe symbol and qualified-module import rewrites."""

from __future__ import annotations

import libcst as cst

from cmm.transformations.relative_import_resolver import RelativeImportResolver


class UpdateImportTransformer(cst.CSTTransformer):
    """Rewrite one moved symbol while preserving unrelated import bindings."""

    def __init__(
        self,
        old_module: str,
        new_module: str,
        symbol_name: str,
        new_symbol_name: str | None = None,
        *,
        consumer_module: str = "",
        consumer_is_package: bool = False,
        rewrite_qualified_module: bool = True,
    ) -> None:
        self._old_module = old_module
        self._new_module = new_module
        self._symbol_name = symbol_name
        self._new_symbol_name = new_symbol_name or symbol_name
        self._consumer_module = consumer_module
        self._consumer_is_package = consumer_is_package
        self._relative_resolver = RelativeImportResolver()
        self._rewrite_qualified_module = rewrite_qualified_module
        self._rename_unaliased_references = False
        self._qualified_bindings: dict[str, bool] = {}
        self._emitted_from_bindings: set[tuple[str, str | None]] = set()
        self.blocking_reason: str | None = None
        self.changed = False

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
        if isinstance(original_import.names, cst.ImportStar) or original_import.module is None:
            return updated_node
        absolute = self._absolute_from_module(original_import)
        if absolute != self._old_module:
            return updated_node
        moved = [
            alias for alias in original_import.names
            if self._name(alias.name) == self._symbol_name
        ]
        if not moved:
            return updated_node
        unique_moved = []
        for alias in moved:
            binding = (
                self._new_symbol_name,
                alias.asname.name.value if alias.asname is not None else None,
            )
            if binding in self._emitted_from_bindings:
                continue
            self._emitted_from_bindings.add(binding)
            unique_moved.append(alias)
        remaining = [
            alias for alias in original_import.names
            if self._name(alias.name) != self._symbol_name
        ]
        rewritten = [
            alias.with_changes(name=cst.Name(self._new_symbol_name))
            for alias in unique_moved
        ]
        if any(alias.asname is None for alias in unique_moved) and self._new_symbol_name != self._symbol_name:
            self._rename_unaliased_references = True
        if not rewritten:
            self.changed = True
            if remaining:
                return updated_node.with_changes(body=(original_import.with_changes(
                    names=self._split_aliases(remaining, original_import)
                ),))
            return cst.RemovalSentinel.REMOVE
        relative = bool(original_import.relative)
        relative_target = self._relative_resolution(relative)
        if relative and relative_target is None:
            self.blocking_reason = (
                f"Cannot preserve a relative import from {self._consumer_module} "
                f"to {self._new_module}."
            )
            return updated_node
        new_import = original_import.with_changes(
            module=self._module_node(
                relative_target.module if relative_target is not None else self._new_module
            ),
            relative=(
                tuple(cst.Dot() for _ in range(relative_target.level))
                if relative_target is not None else ()
            ),
            names=(
                tuple(rewritten)
                if not remaining
                else self._split_aliases(rewritten, original_import)
            ),
        )
        self.changed = True
        if not remaining:
            return updated_node.with_changes(body=(new_import,))
        old_import = original_import.with_changes(
            names=self._split_aliases(remaining, original_import)
        )
        first = updated_node.with_changes(body=(old_import,))
        second = cst.SimpleStatementLine(body=(new_import,))
        return cst.FlattenSentinel((first, second))

    def leave_Import(self, original_node: cst.Import, updated_node: cst.Import) -> cst.Import:
        aliases = []
        changed = False
        for alias in updated_node.names:
            module_name = self._name(alias.name)
            if module_name != self._old_module or not self._rewrite_qualified_module:
                aliases.append(alias)
                continue
            binding = alias.asname.name.value if alias.asname is not None else self._old_module.split(".")[0]
            self._qualified_bindings[binding] = alias.asname is None
            aliases.append(alias.with_changes(name=self._module_node(self._new_module)))
            changed = True
        if changed:
            self.changed = True
            return updated_node.with_changes(names=tuple(aliases))
        return updated_node

    def leave_Attribute(self, original_node: cst.Attribute, updated_node: cst.Attribute) -> cst.BaseExpression:
        dotted = self._name(original_node)
        for binding, unaliased in self._qualified_bindings.items():
            if unaliased:
                prefix = f"{self._old_module}.{self._symbol_name}"
                replacement = f"{self._new_module}.{self._new_symbol_name}"
            else:
                prefix = f"{binding}.{self._symbol_name}"
                replacement = f"{binding}.{self._new_symbol_name}"
            if dotted == prefix or dotted.startswith(prefix + "."):
                self.changed = True
                return cst.parse_expression(replacement + dotted[len(prefix):])
        return updated_node

    def leave_Name(self, original_node: cst.Name, updated_node: cst.Name) -> cst.Name:
        if self._rename_unaliased_references and original_node.value == self._symbol_name:
            self.changed = True
            return updated_node.with_changes(value=self._new_symbol_name)
        return updated_node

    def leave_Assign(self, original_node: cst.Assign, updated_node: cst.Assign) -> cst.Assign:
        if not self._rename_unaliased_references or not any(
            isinstance(target.target, cst.Name) and target.target.value == "__all__"
            for target in original_node.targets
        ):
            return updated_node
        if not isinstance(updated_node.value, (cst.List, cst.Tuple)):
            return updated_node
        elements = []
        changed = False
        for element in updated_node.value.elements:
            if element is None or not isinstance(element.value, cst.SimpleString):
                elements.append(element)
                continue
            if element.value.evaluated_value != self._symbol_name:
                elements.append(element)
                continue
            elements.append(element.with_changes(value=cst.SimpleString(repr(self._new_symbol_name))))
            changed = True
        if not changed:
            return updated_node
        self.changed = True
        return updated_node.with_changes(value=updated_node.value.with_changes(elements=tuple(elements)))

    def _absolute_from_module(self, node: cst.ImportFrom) -> str | None:
        module = self._name(node.module) if node.module is not None else ""
        resolution = self._relative_resolver.resolve(
            self._consumer_module,
            len(node.relative),
            module,
            consumer_is_package=self._consumer_is_package,
        )
        return resolution.absolute_module if resolution is not None else None

    def _relative_resolution(self, relative: bool):
        if not relative:
            return None
        return self._relative_resolver.render_relative(
            self._consumer_module,
            self._new_module,
            consumer_is_package=self._consumer_is_package,
        )

    def _normalize_aliases(self, aliases: list[cst.ImportAlias]) -> tuple[cst.ImportAlias, ...]:
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
        return self._normalize_aliases(aliases)

    def _name(self, node: cst.Name | cst.Attribute) -> str:
        if isinstance(node, cst.Name):
            return node.value
        return f"{self._name(node.value)}.{node.attr.value}"

    def _module_node(self, module_name: str) -> cst.Name | cst.Attribute:
        return cst.parse_expression(module_name)
