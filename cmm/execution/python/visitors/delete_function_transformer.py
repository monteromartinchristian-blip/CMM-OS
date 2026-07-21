"""LibCST transformer that removes one top-level function definition."""

from __future__ import annotations

import libcst as cst


class DeleteFunctionTransformer(cst.CSTTransformer):
    """Remove a direct module-level function with a matching name."""

    def __init__(self, function_name: str) -> None:
        self._function_name = function_name

    def leave_Module(
        self,
        original_node: cst.Module,
        updated_node: cst.Module,
    ) -> cst.Module:
        return updated_node.with_changes(
            body=tuple(
                statement
                for statement in updated_node.body
                if not (
                    isinstance(statement, cst.FunctionDef)
                    and statement.name.value == self._function_name
                )
            )
        )
