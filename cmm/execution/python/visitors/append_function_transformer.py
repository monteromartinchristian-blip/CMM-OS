"""LibCST transformer that appends a function definition to a module."""

from __future__ import annotations

import libcst as cst


class AppendFunctionTransformer(cst.CSTTransformer):
    """Append one function definition without changing existing module content."""

    def __init__(self, function: cst.FunctionDef) -> None:
        self._function = function

    def leave_Module(
        self,
        original_node: cst.Module,
        updated_node: cst.Module,
    ) -> cst.Module:
        return updated_node.with_changes(body=(*updated_node.body, self._function))
