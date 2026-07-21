"""LibCST transformer for deleting one direct module-level symbol."""

from __future__ import annotations

import libcst as cst


class DeleteSymbolTransformer(cst.CSTTransformer):
    """Delete exactly one top-level function or class of the requested kind."""

    def __init__(self, symbol_name: str, symbol_kind: str = "function") -> None:
        self._symbol_name = symbol_name
        self._symbol_kind = symbol_kind

    def leave_Module(
        self,
        original_node: cst.Module,
        updated_node: cst.Module,
    ) -> cst.Module:
        expected = {
            "function": (cst.FunctionDef,),
            "class": (cst.ClassDef,),
        }.get(self._symbol_kind)
        if expected is None:
            raise ValueError(f"Unsupported symbol kind: {self._symbol_kind}.")
        return updated_node.with_changes(
            body=tuple(
                statement
                for statement in updated_node.body
                if not (
                    isinstance(statement, expected)
                    and statement.name.value == self._symbol_name
                )
            )
        )
