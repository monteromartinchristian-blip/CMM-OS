"""Composite transformation for extracting selected top-level symbols."""

from dataclasses import dataclass

from cmm.transformations.models import TransformationStep
from cmm.transformations.operations import (
    CreateModuleOperation,
    ExtractModuleOperation,
    ValidateProjectOperation,
)
from cmm.transformations.plan import TransformationPlan
from cmm.transformations.preconditions import (
    ExtractModulePrecondition,
    ImpactAnalysisPrecondition,
    ModuleExistsPrecondition,
)
from cmm.transformations.impact_analysis import ImpactAnalysisRequest
from cmm.transformations.transformation import Transformation


@dataclass(frozen=True)
class ExtractModuleTransformation(Transformation):
    source_module: str
    target_module: str
    symbols: tuple[str, ...]
    create_target: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "symbols", tuple(self.symbols))

    @property
    def name(self) -> str:
        return "extract_module"

    def create_plan(self, goal: str) -> TransformationPlan:
        if self.source_module == self.target_module:
            raise ValueError("Source and target modules must differ.")
        operations = []
        if self.create_target:
            operations.append(CreateModuleOperation(self.target_module))
        operations.append(ExtractModuleOperation(self.source_module, self.target_module, self.symbols))
        operations.append(ValidateProjectOperation(scope="project"))
        steps = tuple(
            TransformationStep(
                id=f"extract-module-{index}",
                operation=operation,
                dependencies=(f"extract-module-{index - 1}",) if index > 1 else (),
            )
            for index, operation in enumerate(operations, start=1)
        )
        preconditions = [ModuleExistsPrecondition(self.source_module)]
        if not self.create_target:
            preconditions.append(ModuleExistsPrecondition(self.target_module))
        preconditions.append(ImpactAnalysisPrecondition(ImpactAnalysisRequest(
            source_module=self.source_module,
            target_module=self.target_module,
            symbols=self.symbols,
            transformation_id="extract_module",
        )))
        preconditions.append(
            ExtractModulePrecondition(
                self.source_module,
                self.target_module,
                self.symbols,
                self.create_target,
            )
        )
        return TransformationPlan(
            id="extract-module",
            steps=steps,
            preconditions=tuple(preconditions),
        )
