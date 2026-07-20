"""Result objects for kernel execution."""

from __future__ import annotations

from dataclasses import dataclass

from kernel.planner.context import PlanningContext
from kernel.planner.execution_plan import ExecutionPlan
from kernel.planner.executor import ExecutionResult
from kernel.planner.validator import ValidationResult


@dataclass(frozen=True, slots=True)
class KernelResult:
    """Structured outcome of running the orchestration pipeline."""

    success: bool
    planning_context: PlanningContext
    execution_plan: ExecutionPlan
    validation_result: ValidationResult
    execution_result: ExecutionResult | None

    @property
    def has_validation_errors(self) -> bool:
        """Return whether validation reported errors."""

        return self.validation_result.has_errors()

    @property
    def has_execution_errors(self) -> bool:
        """Return whether execution reported errors."""

        return self.execution_result is not None and not self.execution_result.success
