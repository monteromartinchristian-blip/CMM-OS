"""Locator for top-level LibCST function definitions."""

from __future__ import annotations

import libcst as cst


class FunctionLocator:
    """Locate a top-level function definition by its name."""

    def find(self, module: cst.Module, name: str) -> cst.FunctionDef | None:
        """Return the direct module-level function named ``name``."""
        for index, statement in enumerate(module.body):
            if isinstance(statement, cst.FunctionDef) and statement.name.value == name:
                if index == 0 and module.header:
                    return statement.with_changes(
                        leading_lines=(*module.header, *statement.leading_lines)
                    )
                return statement
        return None
