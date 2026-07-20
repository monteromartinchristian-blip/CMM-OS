"""Deterministic reasoning facade for CMM OS technical knowledge."""

from __future__ import annotations

from typing import Optional

from cmm.memory.technical_memory import TechnicalMemory


class TechnicalReasoner:
    """Organize technical knowledge from :class:`TechnicalMemory` deterministically.

    The reasoner does not access graph or persistence internals. It only composes
    information exposed by the public technical-memory facade.
    """

    def __init__(self, memory: TechnicalMemory) -> None:
        """Initialize the reasoner with a loaded technical-memory facade."""
        self._memory = memory

    def summarize_symbol(self, name: str) -> Optional[dict[str, object]]:
        """Return a structured summary for the first symbol matching ``name``."""
        symbol = self._find_symbol(name)
        if symbol is None:
            return None

        parents = self._memory.find_parents(symbol)
        return {
            "symbol": symbol,
            "type": symbol.kind,
            "location": symbol.source_path,
            "parent": parents[0] if parents else None,
            "children": self._memory.find_children(symbol),
            "relationships": {
                "callers": self._memory.find_callers(symbol),
                "callees": self._memory.find_callees(symbol),
                "uses": self._memory.find_uses(symbol),
                "used_by": self._memory.find_used_by(symbol),
                "imports": self._memory.find_imports(symbol),
                "imported_by": self._memory.find_imported_by(symbol),
                "inherits_from": self._memory.find_base_classes(symbol),
                "derived_classes": self._memory.find_derived_classes(symbol),
            },
        }

    def explain_dependencies(self, name: str) -> Optional[dict[str, object]]:
        """Return the direct dependency relationships for a symbol."""
        symbol = self._find_symbol(name)
        if symbol is None:
            return None

        return {
            "symbol": symbol,
            "uses": self._memory.find_uses(symbol),
            "used_by": self._memory.find_used_by(symbol),
            "imports": self._memory.find_imports(symbol),
            "imported_by": self._memory.find_imported_by(symbol),
            "inherits_from": self._memory.find_base_classes(symbol),
            "derived_classes": self._memory.find_derived_classes(symbol),
        }

    def explain_call_graph(self, name: str) -> Optional[dict[str, object]]:
        """Return direct callers and callees for a symbol."""
        symbol = self._find_symbol(name)
        if symbol is None:
            return None

        return {
            "symbol": symbol,
            "callers": self._memory.find_callers(symbol),
            "callees": self._memory.find_callees(symbol),
        }

    def impact_analysis(self, name: str) -> Optional[dict[str, object]]:
        """Estimate change impact from the symbol's direct graph dependents."""
        symbol = self._find_symbol(name)
        if symbol is None:
            return None

        callers = self._memory.find_callers(symbol)
        callees = self._memory.find_callees(symbol)
        direct_dependents = self._unique_nodes(
            callers
            + self._memory.find_imported_by(symbol)
            + self._memory.find_used_by(symbol)
            + self._memory.find_derived_classes(symbol)
        )

        return {
            "symbol": symbol,
            "direct_dependents": direct_dependents,
            "callers": callers,
            "callees": callees,
            "risk": self._risk_level(
                len(direct_dependents),
                len(callers),
                len(callees),
            ),
        }

    def locate_feature(self, keyword: str) -> list[object]:
        """Return symbols whose names contain ``keyword``."""
        return list(self._memory.search_symbols(keyword))

    def _find_symbol(self, name: str) -> Optional[object]:
        symbols = self._memory.find_symbol(name)
        return symbols[0] if symbols else None

    def _unique_nodes(self, nodes: list[object]) -> list[object]:
        seen_identifiers = set()
        unique_nodes = []

        for node in nodes:
            identifier = getattr(node, "identifier")
            if identifier in seen_identifiers:
                continue

            seen_identifiers.add(identifier)
            unique_nodes.append(node)

        return unique_nodes

    def _risk_level(
        self,
        dependent_count: int,
        caller_count: int,
        callee_count: int,
    ) -> str:
        if dependent_count >= 5 or (caller_count >= 3 and callee_count >= 3):
            return "high"
        if dependent_count >= 2 or caller_count >= 2 or callee_count >= 3:
            return "medium"
        return "low"
