"""Composite transformation for moving a top-level class between modules."""

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
from cmm.transformations.preconditions import (
    ModuleExistsPrecondition,
    SymbolAbsentPrecondition,
    SymbolDependenciesPrecondition,
    SymbolExistsPrecondition,
    SupportedSymbolReferencesPrecondition,
    ImpactAnalysisPrecondition,
)
from cmm.transformations.impact_analysis import ImpactAnalysisRequest
from cmm.transformations.transformation import Transformation


@dataclass(frozen=True)
class MoveClassTransformation(Transformation):
    """Move a top-level class between existing Python modules."""

    class_name: str
    source_module: str
    target_module: str
    new_name: str | None = None

    @property
    def name(self) -> str:
        return "move_class"

    def build_plan(self) -> TransformationPlan:
        """Build the deterministic copy, import, delete, validate plan."""
        if self.source_module == self.target_module:
            raise ValueError("Source and target modules must differ.")

        destination_symbol = self.new_name or self.class_name
        operations = [
            CopySymbolOperation(
                symbol=self.class_name,
                source=self.source_module,
                destination=self.target_module,
                symbol_kind="class",
            ),
        ]
        if self.new_name is not None:
            operations.append(
                RenameSymbolOperation(
                    symbol=self.class_name,
                    new_name=self.new_name,
                    module=self.target_module,
                    symbol_kind="class",
                )
            )
        operations.extend(
            [
                UpdateImportsOperation(
                    module=self.target_module,
                    old_module=self.source_module,
                    new_module=self.target_module,
                    symbol_name=self.class_name,
                    new_symbol_name=destination_symbol,
                ),
                DeleteSymbolOperation(
                    symbol=self.class_name,
                    module=self.source_module,
                    symbol_kind="class",
                ),
                ValidateProjectOperation(scope="project"),
            ]
        )
        steps = tuple(
            TransformationStep(
                id=f"move-class-{index}",
                operation=operation,
                dependencies=(f"move-class-{index - 1}",) if index > 1 else (),
            )
            for index, operation in enumerate(operations, start=1)
        )
        return TransformationPlan(
            id="move-class",
            steps=steps,
            preconditions=(
                ModuleExistsPrecondition(self.source_module),
                SymbolExistsPrecondition(
                    self.source_module,
                    self.class_name,
                    "class",
                ),
                ModuleExistsPrecondition(self.target_module),
                SymbolAbsentPrecondition(self.target_module, destination_symbol),
                *(() if destination_symbol == self.class_name else (
                    SymbolAbsentPrecondition(self.target_module, self.class_name),
                )),
                ImpactAnalysisPrecondition(ImpactAnalysisRequest(
                    source_module=self.source_module,
                    target_module=self.target_module,
                    symbols=(self.class_name,),
                    renamed_symbols=((destination_symbol,) if self.new_name else ()),
                    transformation_id="move_class",
                )),
                SupportedSymbolReferencesPrecondition(
                    self.source_module,
                    self.class_name,
                    self.target_module,
                    destination_symbol,
                ),
                SymbolDependenciesPrecondition(
                    self.source_module,
                    self.target_module,
                    self.class_name,
                    "class",
                ),
            ),
        )

    def create_plan(self, goal: str) -> TransformationPlan:
        return self.build_plan()
