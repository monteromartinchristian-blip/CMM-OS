"""Delete-symbol transformation operation."""

from dataclasses import dataclass

from cmm.transformations.operation import TransformationOperation


@dataclass(frozen=True)
class DeleteSymbolOperation(TransformationOperation):
    """Describe the intent to delete a symbol."""

    symbol: str
    module: str

    @property
    def name(self) -> str:
        return "delete_symbol"

    def describe(self) -> str:
        return f"Delete symbol {self.symbol} from module: {self.module}."

    def metadata(self) -> dict[str, object]:
        return {"symbol": self.symbol, "module": self.module}
