"""Builder for semantic contexts backed by Python project snapshots."""

import libcst as cst

from cmm.execution.python.python_project_parser import PythonProjectSnapshot
from cmm.execution.python.reference_index import ReferenceIndex
from cmm.execution.python.semantic_context import SemanticContext
from cmm.execution.python.visitors import ReferenceLocator


class _NameCollector(cst.CSTVisitor):
    def __init__(self) -> None:
        self.names: set[str] = set()

    def visit_Name(self, node: cst.Name) -> None:
        self.names.add(node.value)


class SemanticContextBuilder:
    """Wrap a project snapshot without performing additional analysis."""

    def build(
        self,
        snapshot: PythonProjectSnapshot,
        build_reference_index: bool = False,
    ) -> SemanticContext:
        """Create a context and optionally index simple module references."""
        reference_index = (
            self._build_reference_index(snapshot)
            if build_reference_index
            else None
        )
        return SemanticContext(
            snapshot=snapshot,
            reference_index=reference_index,
        )

    def _build_reference_index(
        self,
        snapshot: PythonProjectSnapshot,
    ) -> ReferenceIndex:
        locator = ReferenceLocator()
        locations = []
        for module in snapshot.modules:
            if module.parsed_module is None:
                continue
            for symbol_name in self._symbol_names(module.parsed_module):
                locations.extend(
                    locator.find(
                        module.module_name,
                        module.parsed_module,
                        symbol_name,
                    )
                )
        return ReferenceIndex(locations=tuple(locations))

    def _symbol_names(self, module: cst.Module) -> set[str]:
        collector = _NameCollector()
        module.visit(collector)
        return collector.names
