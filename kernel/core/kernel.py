"""Core orchestration kernel for planner, validator, and executor."""

from __future__ import annotations

from kernel.planner.context import PlanningContext
from kernel.planner.execution_plan import ExecutionPlan
from kernel.planner.executor import ExecutionResult, Executor
from kernel.planner.validator import PlanValidator, ValidationResult
from kernel.core.result import KernelResult


class AgentKernel:
    """Coordinate planning, validation, and execution through a single entry point."""

    def __init__(
        self,
        planner: object,
        validator: PlanValidator,
        executor: Executor,
    ) -> None:
        self.planner = planner
        self.validator = validator
        self.executor = executor

    def execute(self, context: PlanningContext) -> KernelResult:
        """Run the orchestration pipeline for a planning context."""

        execution_plan = self.planner.plan(context)
        validation_result = self.validator.validate(execution_plan)

        if validation_result.has_errors():
            return KernelResult(
                success=False,
                planning_context=context,
                execution_plan=execution_plan,
                validation_result=validation_result,
                execution_result=None,
            )

        execution_result = self.executor.execute(execution_plan)
        return KernelResult(
            success=execution_result.success,
            planning_context=context,
            execution_plan=execution_plan,
            validation_result=validation_result,
            execution_result=execution_result,
        )
