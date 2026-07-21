"""Read-only resolution of simple Python imports from semantic snapshots."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import libcst as cst

from cmm.execution.python.semantic_context import SemanticContext


class ImportType(str, Enum):
    """Supported forms of static Python imports."""

    DIRECT_IMPORT = "DIRECT_IMPORT"
    FROM_IMPORT = "FROM_IMPORT"
    RELATIVE_IMPORT = "RELATIVE_IMPORT"


@dataclass(frozen=True)
class ImportResolution:
    """Source information for one imported symbol."""

    imported: bool
    source_module: str
    imported_name: str
    alias: str | None
    import_type: ImportType


class ImportResolver:
    """Resolve imported names from modules in a semantic context."""

    def __init__(self, context: SemanticContext) -> None:
        self._context = context

    def resolve_symbol(
        self,
        module_name: str,
        symbol_name: str,
    ) -> ImportResolution | None:
        """Return import provenance for ``symbol_name`` in ``module_name``."""
        module = next(
            (
                item
                for item in self._context.snapshot.modules
                if item.module_name == module_name
            ),
            None,
        )
        if module is None or module.parsed_module is None:
            return None

        for statement in module.parsed_module.body:
            if not isinstance(statement, cst.SimpleStatementLine):
                continue
            for small_statement in statement.body:
                resolution = self._resolve_statement(small_statement, symbol_name)
                if resolution is not None:
                    return resolution
        return None

    def _resolve_statement(
        self,
        statement: cst.BaseSmallStatement,
        symbol_name: str,
    ) -> ImportResolution | None:
        if isinstance(statement, cst.Import):
            return self._resolve_direct_import(statement, symbol_name)
        if isinstance(statement, cst.ImportFrom):
            return self._resolve_from_import(statement, symbol_name)
        return None

    def _resolve_direct_import(
        self,
        statement: cst.Import,
        symbol_name: str,
    ) -> ImportResolution | None:
        for imported in statement.names:
            imported_name = self._name(imported.name)
            alias = imported.asname.name.value if imported.asname is not None else None
            bound_name = alias or imported_name.split(".", maxsplit=1)[0]
            if bound_name == symbol_name:
                return ImportResolution(
                    imported=True,
                    source_module=imported_name,
                    imported_name=imported_name,
                    alias=alias,
                    import_type=ImportType.DIRECT_IMPORT,
                )
        return None

    def _resolve_from_import(
        self,
        statement: cst.ImportFrom,
        symbol_name: str,
    ) -> ImportResolution | None:
        if isinstance(statement.names, cst.ImportStar):
            return None

        source_module = (
            "." * len(statement.relative)
            + (self._name(statement.module) if statement.module is not None else "")
        )
        import_type = (
            ImportType.RELATIVE_IMPORT
            if statement.relative
            else ImportType.FROM_IMPORT
        )
        for imported in statement.names:
            imported_name = self._name(imported.name)
            alias = imported.asname.name.value if imported.asname is not None else None
            if alias or imported_name == symbol_name:
                if (alias or imported_name) != symbol_name:
                    continue
                return ImportResolution(
                    imported=True,
                    source_module=source_module,
                    imported_name=imported_name,
                    alias=alias,
                    import_type=import_type,
                )
        return None

    def _name(self, node: cst.Name | cst.Attribute) -> str:
        if isinstance(node, cst.Name):
            return node.value
        return f"{self._name(node.value)}.{node.attr.value}"
