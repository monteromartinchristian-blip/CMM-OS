"""Rename-symbol transformation operation."""

from dataclasses import dataclass

from cmm.transformations.operation import TransformationOperation
from cmm.transformations.symbol_kind import SymbolKind, validate_symbol_kind


@dataclass(frozen=True)
class RenameSymbolOperation(TransformationOperation):
    """Describe the intent to rename a symbol."""

    symbol: str
    new_name: str
    module: str | None = None
    symbol_kind: SymbolKind = "function"

    def __post_init__(self) -> None:
        validate_symbol_kind(self.symbol_kind)

    @property
    def name(self) -> str:
        return "rename_symbol"

    def describe(self) -> str:
        return f"Rename symbol {self.symbol} to {self.new_name}."

    def metadata(self) -> dict[str, object]:
        return {
            "symbol": self.symbol,
            "new_name": self.new_name,
            **({"module": self.module} if self.module else {}),
            **({"symbol_kind": self.symbol_kind} if self.symbol_kind != "function" else {}),
        }
