"""Copy-symbol transformation operation."""

from dataclasses import dataclass

from cmm.transformations.operation import TransformationOperation


@dataclass(frozen=True)
class CopySymbolOperation(TransformationOperation):
    """Describe the intent to copy a symbol."""

    symbol: str
    source: str
    destination: str

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
        }
