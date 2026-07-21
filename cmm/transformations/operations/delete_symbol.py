"""Delete-symbol transformation operation."""

from dataclasses import dataclass

from cmm.transformations.operation import TransformationOperation
from cmm.transformations.symbol_kind import SymbolKind, validate_symbol_kind


@dataclass(frozen=True)
class DeleteSymbolOperation(TransformationOperation):
    """Describe the intent to delete a symbol."""

    symbol: str
    module: str
    symbol_kind: SymbolKind = "function"

    def __post_init__(self) -> None:
        validate_symbol_kind(self.symbol_kind)

    @property
    def name(self) -> str:
        return "delete_symbol"

    def describe(self) -> str:
        return f"Delete symbol {self.symbol} from module: {self.module}."

    def metadata(self) -> dict[str, object]:
        return {
            "symbol": self.symbol,
            "module": self.module,
            **({"symbol_kind": self.symbol_kind} if self.symbol_kind != "function" else {}),
        }
