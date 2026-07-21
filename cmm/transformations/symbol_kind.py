"""Typed symbol kinds shared by transformation contracts."""

from __future__ import annotations

from typing import Literal

SymbolKind = Literal["function", "class"]
SUPPORTED_SYMBOL_KINDS = frozenset({"function", "class"})


def validate_symbol_kind(symbol_kind: str) -> None:
    """Reject symbol kinds outside the explicitly supported contract."""
    if symbol_kind not in SUPPORTED_SYMBOL_KINDS:
        raise ValueError(
            f"Unsupported symbol kind: {symbol_kind}. "
            "Expected 'function' or 'class'."
        )
