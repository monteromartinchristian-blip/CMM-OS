"""Read-only LibCST locator for simple name references."""

from __future__ import annotations

from dataclasses import dataclass

import libcst as cst
from libcst.metadata import ParentNodeProvider, PositionProvider


@dataclass(frozen=True)
class ReferenceLocation:
    """One simple-name reference and its source location."""

    module_name: str
    line: int
    column: int
    node: cst.Name


class _NameReferenceVisitor(cst.CSTVisitor):
    METADATA_DEPENDENCIES = (ParentNodeProvider, PositionProvider)

    def __init__(self, module_name: str, symbol_name: str) -> None:
        self._module_name = module_name
        self._symbol_name = symbol_name
        self.locations: list[ReferenceLocation] = []

    def visit_Name(self, node: cst.Name) -> None:
        if node.value != self._symbol_name:
            return

        parent = self.get_metadata(ParentNodeProvider, node)
        if isinstance(parent, cst.FunctionDef) and parent.name is node:
            return

        position = self.get_metadata(PositionProvider, node).start
        self.locations.append(
            ReferenceLocation(
                module_name=self._module_name,
                line=position.line,
                column=position.column,
                node=node,
            )
        )


class ReferenceLocator:
    """Locate simple references to a symbol in one Python module."""

    def find(self, module_name: str, module: cst.Module, symbol_name: str) -> list[ReferenceLocation]:
        """Return every simple-name usage matching ``symbol_name``."""
        visitor = _NameReferenceVisitor(module_name, symbol_name)
        cst.MetadataWrapper(module).visit(visitor)
        return visitor.locations
