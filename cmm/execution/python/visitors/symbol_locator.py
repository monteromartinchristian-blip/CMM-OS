"""Locators for direct module-level Python symbols."""

from __future__ import annotations

import libcst as cst


class SymbolLocator:
    """Locate a top-level function or class without guessing its kind."""

    def find(
        self,
        module: cst.Module,
        name: str,
        symbol_kind: str = "function",
    ) -> cst.FunctionDef | cst.ClassDef | None:
        expected = {
            "function": (cst.FunctionDef,),
            "class": (cst.ClassDef,),
        }.get(symbol_kind)
        if expected is None:
            raise ValueError(f"Unsupported symbol kind: {symbol_kind}.")
        for index, statement in enumerate(module.body):
            if isinstance(statement, expected) and statement.name.value == name:
                if index == 0 and module.header:
                    return statement.with_changes(
                        leading_lines=(*module.header, *statement.leading_lines)
                    )
                return statement
        return None
