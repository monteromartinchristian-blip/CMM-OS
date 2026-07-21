"""Composite transformation for extracting a contiguous method block."""

from dataclasses import dataclass

from cmm.transformations.models import TransformationStep
from cmm.transformations.operations import ExtractMethodOperation, ValidateProjectOperation
from cmm.transformations.plan import TransformationPlan
from cmm.transformations.preconditions import (
    ExtractMethodPrecondition,
    ModuleExistsPrecondition,
    SymbolExistsPrecondition,
)
from cmm.transformations.transformation import Transformation


@dataclass(frozen=True)
class ExtractMethodTransformation(Transformation):
    module: str
    class_name: str
    method_name: str
    new_method_name: str
    start_index: int
    end_index: int

    @property
    def name(self) -> str:
        return "extract_method"

    def create_plan(self, goal: str) -> TransformationPlan:
        operation = ExtractMethodOperation(
            self.module,
            self.class_name,
            self.method_name,
            self.new_method_name,
            self.start_index,
            self.end_index,
        )
        return TransformationPlan(
            id="extract-method",
            steps=(
                TransformationStep(id="extract-method-1", operation=operation),
                TransformationStep(
                    id="extract-method-2",
                    operation=ValidateProjectOperation(scope="project"),
                    dependencies=("extract-method-1",),
                ),
            ),
            preconditions=(
                ModuleExistsPrecondition(self.module),
                SymbolExistsPrecondition(self.module, self.class_name, "class"),
                ExtractMethodPrecondition(
                    self.module,
                    self.class_name,
                    self.method_name,
                    self.new_method_name,
                    self.start_index,
                    self.end_index,
                ),
            ),
        )
