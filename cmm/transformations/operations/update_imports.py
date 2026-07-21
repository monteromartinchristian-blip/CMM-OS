"""Update-imports transformation operation."""

from dataclasses import dataclass

from cmm.transformations.operation import TransformationOperation


@dataclass(frozen=True)
class UpdateImportsOperation(TransformationOperation):
    """Describe the intent to update a module's imports."""

    module: str
    old_module: str | None = None
    new_module: str | None = None
    symbol_name: str | None = None
    new_symbol_name: str | None = None

    @property
    def name(self) -> str:
        return "update_imports"

    def describe(self) -> str:
        return f"Update imports for module: {self.module}."

    def metadata(self) -> dict[str, object]:
        return {
            "module": self.module,
            **({"old_module": self.old_module} if self.old_module else {}),
            **({"new_module": self.new_module} if self.new_module else {}),
            **({"symbol_name": self.symbol_name} if self.symbol_name else {}),
            **(
                {"new_symbol_name": self.new_symbol_name}
                if self.new_symbol_name
                else {}
            ),
        }
