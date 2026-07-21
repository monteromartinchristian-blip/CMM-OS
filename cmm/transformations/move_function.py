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
from cmm.transformations.preconditions import (
    FunctionDependenciesPrecondition,
    ModuleExistsPrecondition,
    SymbolAbsentPrecondition,
    SymbolExistsPrecondition,
    SupportedSymbolReferencesPrecondition,
    ImpactAnalysisPrecondition,
)
from cmm.transformations.impact_analysis import ImpactAnalysisRequest
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
        if transformation.source_module == transformation.target_module:
            raise ValueError("Source and target modules must differ.")

        destination_symbol = transformation.new_name or transformation.function_name
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
                    module=transformation.target_module,
                )
            )
        operations.append(
            UpdateImportsOperation(
                module=transformation.target_module,
                old_module=transformation.source_module,
                new_module=transformation.target_module,
                symbol_name=transformation.function_name,
                new_symbol_name=destination_symbol,
            )
        )
        operations.append(
            DeleteSymbolOperation(
                symbol=transformation.function_name,
                module=transformation.source_module,
            )
        )
        operations.append(ValidateProjectOperation(scope="project"))

        steps = tuple(
            TransformationStep(
                id=f"move-function-{index}",
                operation=operation,
                dependencies=(f"move-function-{index - 1}",) if index > 1 else (),
            )
            for index, operation in enumerate(operations, start=1)
        )
        return TransformationPlan(
            id="move-function",
            preconditions=(
                ModuleExistsPrecondition(transformation.source_module),
                SymbolExistsPrecondition(
                    transformation.source_module,
                    transformation.function_name,
                    "function",
                ),
                ModuleExistsPrecondition(transformation.target_module),
                SymbolAbsentPrecondition(
                    transformation.target_module,
                    destination_symbol,
                ),
                *(() if destination_symbol == transformation.function_name else (
                    SymbolAbsentPrecondition(
                        transformation.target_module,
                        transformation.function_name,
                    ),
                )),
                ImpactAnalysisPrecondition(ImpactAnalysisRequest(
                    source_module=transformation.source_module,
                    target_module=transformation.target_module,
                    symbols=(transformation.function_name,),
                    renamed_symbols=((destination_symbol,) if transformation.new_name else ()),
                    transformation_id="move_function",
                )),
                SupportedSymbolReferencesPrecondition(
                    transformation.source_module,
                    transformation.function_name,
                    transformation.target_module,
                    destination_symbol,
                ),
                FunctionDependenciesPrecondition(
                    transformation.source_module,
                    transformation.target_module,
                    transformation.function_name,
                ),
            ),
            steps=steps,
        )
