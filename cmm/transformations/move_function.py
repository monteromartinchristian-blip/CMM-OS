"""Composite transformation for moving a top-level function between modules."""

from __future__ import annotations

from dataclasses import dataclass

from cmm.transformations.models import TransformationStep
from cmm.transformations.operations import (
    CopySymbolOperation,
    DeleteSymbolOperation,
    RenameSymbolOperation,
    UpdateImportsOperation,
    ValidateProjectOperation,
)
from cmm.transformations.plan import TransformationPlan
from cmm.transformations.transformation import Transformation


@dataclass(frozen=True)
class MoveFunctionTransformation(Transformation):
    """Describe a language-agnostic function move between two modules."""

    source_module: str
    target_module: str
    function_name: str
    new_name: str | None = None

    @property
    def name(self) -> str:
        """Return the stable transformation name."""
        return "move_function"

    def create_plan(self, goal: str) -> TransformationPlan:
        """Create this transformation's deterministic operation plan."""
        return MoveFunctionTransformationBuilder().build(self)


class MoveFunctionTransformationBuilder:
    """Build a plan from copy, optional rename, import update, delete, and validation."""

    def build(
        self,
        transformation: MoveFunctionTransformation,
    ) -> TransformationPlan:
        """Compose the ordered primitive operations for a function move."""
        operations = [
            CopySymbolOperation(
                symbol=transformation.function_name,
                source=transformation.source_module,
                destination=transformation.target_module,
            )
        ]
        if transformation.new_name is not None:
            operations.append(
                RenameSymbolOperation(
                    symbol=transformation.function_name,
                    new_name=transformation.new_name,
                )
            )
        operations.append(
            UpdateImportsOperation(module=transformation.target_module)
        )
        operations.append(
            DeleteSymbolOperation(
                symbol=transformation.function_name,
                module=transformation.source_module,
            )
        )
        operations.append(ValidateProjectOperation(scope="project"))

        return TransformationPlan(
            steps=tuple(
                TransformationStep(
                    id=f"move-function-{index}",
                    operation=operation,
                )
                for index, operation in enumerate(operations, start=1)
            )
        )
