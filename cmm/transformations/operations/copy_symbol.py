"""Copy-symbol transformation operation."""

from dataclasses import dataclass

from cmm.transformations.operation import TransformationOperation
from cmm.transformations.symbol_kind import SymbolKind, validate_symbol_kind


@dataclass(frozen=True)
class CopySymbolOperation(TransformationOperation):
    """Describe the intent to copy a symbol."""

    symbol: str
    source: str
    destination: str
    symbol_kind: SymbolKind = "function"

    def __post_init__(self) -> None:
        validate_symbol_kind(self.symbol_kind)

    @property
    def name(self) -> str:
        return "copy_symbol"

    def describe(self) -> str:
        return f"Copy symbol {self.symbol} from {self.source} to {self.destination}."

    def metadata(self) -> dict[str, object]:
        return {
            "symbol": self.symbol,
            "source": self.source,
            "destination": self.destination,
            **({"symbol_kind": self.symbol_kind} if self.symbol_kind != "function" else {}),
        }
