"""Transient index of simple Python symbol references."""

from __future__ import annotations

from dataclasses import dataclass

from cmm.execution.python.visitors.reference_locator import ReferenceLocation


@dataclass(frozen=True)
class ReferenceIndex:
    """Read-only collection of reference locations."""

    locations: tuple[ReferenceLocation, ...] = ()

    def find(self, symbol_name: str) -> list[ReferenceLocation]:
        """Return locations whose simple name matches ``symbol_name``."""
        return [
            location
            for location in self.locations
            if location.node.value == symbol_name
        ]
