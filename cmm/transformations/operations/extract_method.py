"""Primitive operation for extracting a contiguous method block."""

from dataclasses import dataclass

from cmm.transformations.operation import TransformationOperation


@dataclass(frozen=True)
class ExtractMethodOperation(TransformationOperation):
    """Describe extraction of ``[start_index:end_index]`` from a method."""

    module: str
    class_name: str
    method_name: str
    new_method_name: str
    start_index: int
    end_index: int

    @property
    def name(self) -> str:
        return "extract_method"

    def describe(self) -> str:
        return (
            f"Extract statements {self.start_index}:{self.end_index} from "
            f"{self.module}.{self.class_name}.{self.method_name}."
        )

    def metadata(self) -> dict[str, object]:
        return {
            "module": self.module,
            "class_name": self.class_name,
            "method_name": self.method_name,
            "new_method_name": self.new_method_name,
            "start_index": self.start_index,
            "end_index": self.end_index,
        }
