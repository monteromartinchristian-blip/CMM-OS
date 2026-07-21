"""LibCST transformer for renaming a top-level symbol and simple references."""

from __future__ import annotations

import libcst as cst


class RenameSymbolTransformer(cst.CSTTransformer):
    """Rename one function/class and simple references in one module."""

    def __init__(self, old_name: str, new_name: str, symbol_kind: str = "function") -> None:
        self._old_name = old_name
        self._new_name = new_name
        self._symbol_kind = symbol_kind

    def visit_Import(self, node: cst.Import) -> bool:
        return False

    def visit_ImportFrom(self, node: cst.ImportFrom) -> bool:
        return False

    def visit_Attribute(self, node: cst.Attribute) -> bool:
        return False

    def leave_Name(self, original_node: cst.Name, updated_node: cst.Name) -> cst.Name:
        if original_node.value != self._old_name:
            return updated_node
        return updated_node.with_changes(value=self._new_name)
