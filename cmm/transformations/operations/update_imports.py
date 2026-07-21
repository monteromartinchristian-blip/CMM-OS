"""Update-imports transformation operation."""

from dataclasses import dataclass

from cmm.transformations.operation import TransformationOperation


@dataclass(frozen=True)
class UpdateImportsOperation(TransformationOperation):
    """Describe the intent to update a module's imports."""

    module: str

    @property
    def name(self) -> str:
        return "update_imports"

    def describe(self) -> str:
        return f"Update imports for module: {self.module}."

    def metadata(self) -> dict[str, object]:
        return {"module": self.module}
