"""LibCST transformer for renaming a top-level function and simple names."""

from __future__ import annotations

import libcst as cst


class RenameFunctionTransformer(cst.CSTTransformer):
    """Rename matching simple names without touching imports or attributes."""

    def __init__(self, old_name: str, new_name: str) -> None:
        self._old_name = old_name
        self._new_name = new_name

    def visit_Import(self, node: cst.Import) -> bool:
        return False

    def visit_ImportFrom(self, node: cst.ImportFrom) -> bool:
        return False

    def visit_Attribute(self, node: cst.Attribute) -> bool:
        return False

    def leave_Name(
        self,
        original_node: cst.Name,
        updated_node: cst.Name,
    ) -> cst.Name:
        if original_node.value == self._old_name:
            return updated_node.with_changes(value=self._new_name)
        return updated_node
