"""LibCST transformer for appending one top-level symbol."""

from __future__ import annotations

import libcst as cst


class AppendSymbolTransformer(cst.CSTTransformer):
    """Append an already parsed function or class unchanged."""

    def __init__(self, symbol: cst.FunctionDef | cst.ClassDef) -> None:
        self._symbol = symbol

    def leave_Module(
        self,
        original_node: cst.Module,
        updated_node: cst.Module,
    ) -> cst.Module:
        return updated_node.with_changes(body=(*updated_node.body, self._symbol))
