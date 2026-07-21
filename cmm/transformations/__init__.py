"""Language-agnostic transformation framework for CMM OS."""

from cmm.transformations.adapter import TransformationActionAdapter
from cmm.transformations.basic_executor import BasicTransformationExecutor
from cmm.transformations.basic_planner import BasicTransformationPlanner
from cmm.transformations.dispatcher import TransformationDispatcher
from cmm.transformations.execution_request import ExecutionRequest
from cmm.transformations.execution_plan import ExecutionPlan
from cmm.transformations.execution_planner import ExecutionPlanner
from cmm.transformations.execution_stage import ExecutionStage
from cmm.transformations.executor import TransformationExecutor
from cmm.transformations.graph import (
    GraphValidationError,
    GraphValidationResult,
    TransformationGraph,
)
from cmm.transformations.models import TransformationGraphNode, TransformationStep
from cmm.transformations.move_class import MoveClassTransformation
from cmm.transformations.move_function import (
    MoveFunctionTransformation,
    MoveFunctionTransformationBuilder,
)
from cmm.transformations.operation import TransformationOperation
from cmm.transformations.operations import (
    CopySymbolOperation,
    CreateFileOperation,
    CreateModuleOperation,
    DeleteFileOperation,
    DeleteModuleOperation,
    DeleteSymbolOperation,
    MoveSymbolOperation,
    RenameSymbolOperation,
    UpdateImportsOperation,
    ValidateProjectOperation,
)
from cmm.transformations.plan import TransformationPlan
from cmm.transformations.preconditions import (
    FileExistsPrecondition,
    FunctionDependenciesPrecondition,
    ModuleExistsPrecondition,
    PreconditionResult,
    SymbolAbsentPrecondition,
    SymbolExistsPrecondition,
    SupportedSymbolReferencesPrecondition,
    TransformationPrecondition,
)
from cmm.transformations.planner import TransformationPlanner
from cmm.transformations.registry import (
    OperationRegistry,
    TransformationRegistry,
    UnsupportedOperationError,
    UnsupportedTransformationError,
)
from cmm.transformations.transformation import Transformation

__all__ = [
    "BasicTransformationExecutor",
    "BasicTransformationPlanner",
    "CopySymbolOperation",
    "CreateFileOperation",
    "CreateModuleOperation",
    "DeleteFileOperation",
    "DeleteModuleOperation",
    "DeleteSymbolOperation",
    "ExecutionRequest",
    "ExecutionPlan",
    "ExecutionPlanner",
    "ExecutionStage",
    "FileExistsPrecondition",
    "FunctionDependenciesPrecondition",
    "GraphValidationError",
    "GraphValidationResult",
    "MoveSymbolOperation",
    "MoveClassTransformation",
    "MoveFunctionTransformation",
    "MoveFunctionTransformationBuilder",
    "OperationRegistry",
    "RenameSymbolOperation",
    "Transformation",
    "TransformationActionAdapter",
    "TransformationOperation",
    "TransformationDispatcher",
    "TransformationExecutor",
    "TransformationGraph",
    "TransformationGraphNode",
    "TransformationPlan",
    "ModuleExistsPrecondition",
    "PreconditionResult",
    "TransformationPlanner",
    "TransformationRegistry",
    "TransformationStep",
    "SymbolExistsPrecondition",
    "SymbolAbsentPrecondition",
    "SupportedSymbolReferencesPrecondition",
    "TransformationPrecondition",
    "UnsupportedOperationError",
    "UnsupportedTransformationError",
    "UpdateImportsOperation",
    "ValidateProjectOperation",
]
