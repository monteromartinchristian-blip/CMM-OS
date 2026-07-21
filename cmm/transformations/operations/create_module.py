"""Create-module transformation operation."""

from dataclasses import dataclass

from cmm.transformations.operation import TransformationOperation


@dataclass(frozen=True)
class CreateModuleOperation(TransformationOperation):
    """Describe the intent to create a module."""

    module_name: str
    project_root: str | None = None

    @property
    def name(self) -> str:
        return "create_module"

    def describe(self) -> str:
        return f"Create module: {self.module_name}."

    def metadata(self) -> dict[str, object]:
        metadata: dict[str, object] = {"module_name": self.module_name}
        if self.project_root is not None:
            metadata["project_root"] = self.project_root
        return metadata
