"""Delete-file transformation operation."""

from dataclasses import dataclass

from cmm.transformations.operation import TransformationOperation


@dataclass(frozen=True)
class DeleteFileOperation(TransformationOperation):
    """Describe the intent to delete a file."""

    path: str

    @property
    def name(self) -> str:
        return "delete_file"

    def describe(self) -> str:
        return f"Delete file: {self.path}."

    def metadata(self) -> dict[str, object]:
        return {"path": self.path}
