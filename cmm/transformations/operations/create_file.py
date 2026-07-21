"""Create-file transformation operation."""

from dataclasses import dataclass

from cmm.transformations.operation import TransformationOperation


@dataclass(frozen=True)
class CreateFileOperation(TransformationOperation):
    """Describe the intent to create a file."""

    path: str

    @property
    def name(self) -> str:
        return "create_file"

    def describe(self) -> str:
        return f"Create file: {self.path}."

    def metadata(self) -> dict[str, object]:
        return {"path": self.path}
