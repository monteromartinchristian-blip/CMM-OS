"""Primitive operation for extracting selected top-level symbols."""

from dataclasses import dataclass

from cmm.transformations.operation import TransformationOperation


@dataclass(frozen=True)
class ExtractModuleOperation(TransformationOperation):
    """Move explicitly selected top-level symbols between modules."""

    source_module: str
    target_module: str
    symbols: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "symbols", tuple(self.symbols))

    @property
    def name(self) -> str:
        return "extract_module"

    def describe(self) -> str:
        return f"Extract {', '.join(self.symbols)} into {self.target_module}."

    def metadata(self) -> dict[str, object]:
        return {
            "source_module": self.source_module,
            "target_module": self.target_module,
            "symbols": list(self.symbols),
        }
