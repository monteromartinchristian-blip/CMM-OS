"""Execution layer connecting the planner domain to the semantic engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from kernel.planner.execution_plan import ExecutionPlan
from kernel.planner.exceptions import PlannerError
from kernel.planner.operations import Operation
from kernel.planner.planning_engine import PlanningEngine
from kernel.planner.registry import OperationRegistry


@dataclass(slots=True)
class ExecutionResult:
    """Structured result of executing an execution plan."""

    executed_operations: list[Operation] = field(default_factory=list)
    failed_operations: list[Operation] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    success: bool = True


class Executor:
    """Execute an already validated execution plan through a registry."""

    def __init__(self, engine: Any, registry: OperationRegistry, planning_engine: PlanningEngine | None = None) -> None:
        self.engine = engine
        self.registry = registry
        self.planning_engine = planning_engine or PlanningEngine()

    def execute(self, plan: ExecutionPlan) -> ExecutionResult:
        """Execute each operation in the plan in order.

        The execution stops at the first failure.
        """

        result = ExecutionResult()

        try:
            ordered_operations = self.planning_engine.plan(plan)
        except PlannerError as exc:
            result.success = False
            result.errors.append(str(exc))
            return result

        for operation in ordered_operations:
            try:
                handler = self.registry.resolve(operation)
                handler.execute(operation, self.engine)
            except (PlannerError, Exception) as exc:  # pragma: no cover - defensive path
                result.failed_operations.append(operation)
                result.errors.append(str(exc))
                result.success = False
                break

            result.executed_operations.append(operation)

        return result


__all__ = ["ExecutionResult", "Executor"]
