"""Delete-module transformation operation."""

from dataclasses import dataclass

from cmm.transformations.operation import TransformationOperation


@dataclass(frozen=True)
class DeleteModuleOperation(TransformationOperation):
    """Describe the intent to delete a module."""

    module: str

    @property
    def name(self) -> str:
        return "delete_module"

    def describe(self) -> str:
        return f"Delete module: {self.module}."

    def metadata(self) -> dict[str, object]:
        return {"module": self.module}
