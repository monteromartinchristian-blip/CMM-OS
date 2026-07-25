from __future__ import annotations

from typing import Protocol

from .context import ValidationContext
from .steps import ValidationStep, ValidationStepResult


class InternalValidator(Protocol):
    """Protocol for internal validators.

    Implementations must be pure in terms of not mutating the project unless an
    explicit step semantics in future phases allows it.
    """

    name: str

    def validate(self, context: ValidationContext, step: ValidationStep) -> ValidationStepResult:  # noqa: D401
        """Execute validation and return a structured result for this step."""


__all__ = ["InternalValidator"]
