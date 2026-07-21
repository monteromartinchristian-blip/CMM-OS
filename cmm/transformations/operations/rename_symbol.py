"""Rename-symbol transformation operation."""

from dataclasses import dataclass

from cmm.transformations.operation import TransformationOperation


@dataclass(frozen=True)
class RenameSymbolOperation(TransformationOperation):
    """Describe the intent to rename a symbol."""

    symbol: str
    new_name: str

    @property
    def name(self) -> str:
        return "rename_symbol"

    def describe(self) -> str:
        return f"Rename symbol {self.symbol} to {self.new_name}."

    def metadata(self) -> dict[str, object]:
        return {"symbol": self.symbol, "new_name": self.new_name}
