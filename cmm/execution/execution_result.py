"""Results returned by primitive operation executors."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Mapping

from cmm.transformations.operation import TransformationOperation
from cmm.transformations.preconditions import PreconditionResult


@dataclass(frozen=True)
class ExecutionResult:
    """Immutable outcome of executing one transformation operation."""

    success: bool
    operation: TransformationOperation
    diagnostics: tuple[str, ...] = ()
    created_paths: tuple[Path, ...] = ()
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "diagnostics", tuple(self.diagnostics))
        object.__setattr__(self, "created_paths", tuple(self.created_paths))
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))


@dataclass(frozen=True)
class StructuredExecutionError:
    """Structured pipeline-level error."""

    code: str
    message: str
    step_id: str | None = None


@dataclass(frozen=True)
class OperationResultRecord:
    """Structured result for one operation request."""

    step_id: str | None
    operation: str
    success: bool
    diagnostics: tuple[str, ...] = ()


@dataclass(frozen=True)
class FinalValidationResult:
    """Structured result of final project validation."""

    success: bool
    diagnostics: tuple[str, ...] = ()
    checked_paths: tuple[Path, ...] = ()


@dataclass(frozen=True)
class RollbackResult:
    """Structured rollback outcome."""

    attempted: bool = False
    applied: bool = False
    restored_paths: tuple[Path, ...] = ()
    removed_created_paths: tuple[Path, ...] = ()
    errors: tuple[str, ...] = ()


@dataclass(frozen=True)
class PipelineExecutionResult:
    """Homogeneous outcome for a full transformation execution pipeline."""

    success: bool
    plan_id: str | None
    planned_steps: tuple[str, ...]
    executed_steps: tuple[str, ...]
    failed_step: str | None = None
    error: StructuredExecutionError | None = None
    precondition_results: tuple[PreconditionResult, ...] = ()
    operation_results: tuple[OperationResultRecord, ...] = ()
    validations: tuple[FinalValidationResult, ...] = ()
    rollback_attempted: bool = False
    rollback_applied: bool = False
    rollback_restored_paths: tuple[Path, ...] = ()
    rollback_errors: tuple[str, ...] = ()
    created_paths: tuple[Path, ...] = ()
    modified_paths: tuple[Path, ...] = ()
    deleted_paths: tuple[Path, ...] = ()

    @property
    def transformation_id(self) -> str | None:
        """Compatibility alias for callers that use transformation terminology."""
        return self.plan_id
