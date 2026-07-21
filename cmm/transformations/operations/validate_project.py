"""Validate-project transformation operation."""

from dataclasses import dataclass

from cmm.transformations.operation import TransformationOperation


@dataclass(frozen=True)
class ValidateProjectOperation(TransformationOperation):
    """Describe the intent to validate a project scope."""

    scope: str

    @property
    def name(self) -> str:
        return "validate_project"

    def describe(self) -> str:
        return f"Validate project scope: {self.scope}."

    def metadata(self) -> dict[str, object]:
        return {"scope": self.scope}
