"""Create-module transformation operation."""

from dataclasses import dataclass

from cmm.transformations.operation import TransformationOperation


@dataclass(frozen=True)
class CreateModuleOperation(TransformationOperation):
    """Describe the intent to create a module."""

    module_name: str
    project_root: str = "."

    @property
    def name(self) -> str:
        return "create_module"

    def describe(self) -> str:
        return f"Create module: {self.module_name}."

    def metadata(self) -> dict[str, object]:
        return {
            "module_name": self.module_name,
            "project_root": self.project_root,
        }
