"""LibCST transformer for minimal single-symbol from-import rewrites."""

from __future__ import annotations

import libcst as cst


class UpdateImportTransformer(cst.CSTTransformer):
    """Rewrite one matching `from module import symbol` declaration."""

    def __init__(
        self,
        old_module: str,
        new_module: str,
        symbol_name: str,
        new_symbol_name: str | None = None,
    ) -> None:
        self._old_module = old_module
        self._new_module = new_module
        self._symbol_name = symbol_name
        self._new_symbol_name = new_symbol_name or symbol_name
        self.changed = False

    def leave_ImportFrom(
        self,
        original_node: cst.ImportFrom,
        updated_node: cst.ImportFrom,
    ) -> cst.ImportFrom:
        if (
            original_node.relative
            or original_node.module is None
            or self._module_name(original_node.module) != self._old_module
            or isinstance(original_node.names, cst.ImportStar)
        ):
            return updated_node
        changed = False
        updated_names = []
        for imported in updated_node.names:
            if (
                isinstance(imported.name, cst.Name)
                and imported.name.value == self._symbol_name
            ):
                imported = imported.with_changes(
                    name=cst.Name(self._new_symbol_name),
                )
                changed = True
            updated_names.append(imported)
        if not changed:
            return updated_node

        self.changed = True
        return updated_node.with_changes(
            module=self._module_node(self._new_module),
            names=tuple(updated_names),
        )

    def _module_name(self, node: cst.Name | cst.Attribute) -> str:
        if isinstance(node, cst.Name):
            return node.value
        return f"{self._module_name(node.value)}.{node.attr.value}"

    def _module_node(self, module_name: str) -> cst.Name | cst.Attribute:
        parts = module_name.split(".")
        node: cst.Name | cst.Attribute = cst.Name(parts[0])
        for part in parts[1:]:
            node = cst.Attribute(value=node, attr=cst.Name(part))
        return node
