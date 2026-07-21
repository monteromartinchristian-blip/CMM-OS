"""Composite transformation for moving a class between modules."""

from __future__ import annotations

from dataclasses import dataclass

from cmm.transformations.models import TransformationStep
from cmm.transformations.operation import TransformationOperation
from cmm.transformations.operations import (
    CopySymbolOperation,
    CreateModuleOperation,
    DeleteSymbolOperation,
    UpdateImportsOperation,
    ValidateProjectOperation,
)
from cmm.transformations.plan import TransformationPlan
from cmm.transformations.transformation import Transformation


@dataclass(frozen=True)
class MoveClassTransformation(Transformation):
    """Build a language-agnostic plan for moving a class between modules."""

    class_name: str
    source_module: str
    target_module: str

    @property
    def name(self) -> str:
        """Return the stable transformation name."""
        return "move_class"

    def build_plan(self) -> TransformationPlan:
        """Compose primitive operations into a deterministic move-class plan."""
        operations = [
            CreateModuleOperation(module_name=self.target_module),
            CopySymbolOperation(
                symbol=self.class_name,
                source=self.source_module,
                destination=self.target_module,
            ),
            UpdateImportsOperation(module=self.target_module),
            DeleteSymbolOperation(
                symbol=self.class_name,
                module=self.source_module,
            ),
            ValidateProjectOperation(scope="project"),
        ]
        return TransformationPlan(
            steps=tuple(
                self._step(f"move-class-{index}", operation)
                for index, operation in enumerate(operations, start=1)
            ),
        )

    def create_plan(self, goal: str) -> TransformationPlan:
        """Create the composed plan required by the transformation contract."""
        plan = self.build_plan()
        return TransformationPlan(steps=plan.steps)

    def _step(
        self,
        step_id: str,
        operation: TransformationOperation,
    ) -> TransformationStep:
        return TransformationStep(
            id=step_id,
            operation=operation,
        )
