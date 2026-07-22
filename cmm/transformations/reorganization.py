"""End-to-end module and package reorganization transformations."""

from __future__ import annotations

from dataclasses import dataclass

from cmm.transformations.models import TransformationStep
from cmm.transformations.operations import (
    MergeModulesOperation,
    MoveModuleOperation,
    MovePackageOperation,
    RenameModuleOperation,
    RenamePackageOperation,
    ReorganizationOperation,
    SplitModuleGroup,
    SplitModuleOperation,
    ValidateProjectOperation,
)
from cmm.transformations.plan import TransformationPlan
from cmm.transformations.preconditions import (
    ImpactAnalysisPrecondition,
    ReorganizationPrecondition,
)
from cmm.transformations.reorganization_impact import ReorganizationImpactRequest
from cmm.transformations.transformation import Transformation


def _plan(identifier: str, operation: ReorganizationOperation) -> TransformationPlan:
    impact = ReorganizationImpactRequest.from_operation(operation, identifier)
    return TransformationPlan(
        id=identifier,
        preconditions=(
            ImpactAnalysisPrecondition(impact),
            ReorganizationPrecondition(operation),
        ),
        steps=(
            TransformationStep(f"{identifier}-1", operation),
            TransformationStep(
                f"{identifier}-2",
                ValidateProjectOperation(scope="project"),
                (f"{identifier}-1",),
            ),
        ),
    )


@dataclass(frozen=True)
class RenameModuleTransformation(Transformation):
    source_module: str
    target_module: str

    @property
    def name(self) -> str:
        return "rename_module"

    def create_plan(self, goal: str) -> TransformationPlan:
        return _plan(self.name, RenameModuleOperation(self.source_module, self.target_module))


@dataclass(frozen=True)
class MoveModuleTransformation(Transformation):
    source_module: str
    target_module: str
    create_target_package: bool = False
    delete_empty_source_package: bool = False

    @property
    def name(self) -> str:
        return "move_module"

    def create_plan(self, goal: str) -> TransformationPlan:
        return _plan(self.name, MoveModuleOperation(
            self.source_module,
            self.target_module,
            self.create_target_package,
            self.delete_empty_source_package,
        ))


@dataclass(frozen=True)
class SplitModuleTransformation(Transformation):
    source_module: str
    groups: tuple[SplitModuleGroup, ...]
    delete_empty_source: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "groups", tuple(self.groups))

    @property
    def name(self) -> str:
        return "split_module"

    def create_plan(self, goal: str) -> TransformationPlan:
        return _plan(self.name, SplitModuleOperation(
            self.source_module, self.groups, self.delete_empty_source
        ))


@dataclass(frozen=True)
class MergeModulesTransformation(Transformation):
    source_modules: tuple[str, ...]
    target_module: str
    create_target: bool = True
    keep_sources: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "source_modules", tuple(self.source_modules))

    @property
    def name(self) -> str:
        return "merge_modules"

    def create_plan(self, goal: str) -> TransformationPlan:
        return _plan(self.name, MergeModulesOperation(
            self.source_modules, self.target_module, self.create_target, self.keep_sources
        ))


@dataclass(frozen=True)
class RenamePackageTransformation(Transformation):
    source_package: str
    target_package: str

    @property
    def name(self) -> str:
        return "rename_package"

    def create_plan(self, goal: str) -> TransformationPlan:
        return _plan(self.name, RenamePackageOperation(self.source_package, self.target_package))


@dataclass(frozen=True)
class MovePackageTransformation(Transformation):
    source_package: str
    target_package: str
    create_target_parents: bool = False
    delete_empty_source_parents: bool = False

    @property
    def name(self) -> str:
        return "move_package"

    def create_plan(self, goal: str) -> TransformationPlan:
        return _plan(self.name, MovePackageOperation(
            self.source_package,
            self.target_package,
            self.create_target_parents,
            self.delete_empty_source_parents,
        ))


__all__ = [
    "MergeModulesTransformation",
    "MoveModuleTransformation",
    "MovePackageTransformation",
    "RenameModuleTransformation",
    "RenamePackageTransformation",
    "SplitModuleGroup",
    "SplitModuleTransformation",
]
