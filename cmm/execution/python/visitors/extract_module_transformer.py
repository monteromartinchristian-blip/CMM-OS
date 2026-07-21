"""LibCST transformer for moving selected top-level symbols and imports."""

from __future__ import annotations

import libcst as cst


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
    def __init__(self, old_module: str, new_module: str, symbols: frozenset[str]) -> None:
        self._old_module = old_module
        self._new_module = new_module
        self._symbols = symbols
        self.changed = False

    def leave_ImportFrom(self, original_node: cst.ImportFrom, updated_node: cst.ImportFrom) -> cst.ImportFrom:
        if (
            original_node.relative
            or original_node.module is None
            or self._name(original_node.module) != self._old_module
            or isinstance(original_node.names, cst.ImportStar)
        ):
            return updated_node
        names = tuple(updated_node.names)
        imported = {self._name(item.name) for item in names}
        if not imported & self._symbols:
            return updated_node
        if not imported <= self._symbols:
            return updated_node
        self.changed = True
        return updated_node.with_changes(module=self._module(self._new_module))

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
