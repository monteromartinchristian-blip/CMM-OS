"""Goal-to-plan planner built on operation metadata discovery.

The planner is intentionally lightweight and deterministic. It delegates the
decision engine to an interchangeable strategy while keeping the public API
stable for callers.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from kernel.planner.execution_plan import ExecutionPlan
from kernel.planner.exceptions import PlannerError
from kernel.planner.operation_catalog import OperationCatalog
from kernel.planner.planner_strategy import PlannerStrategy, RuleBasedPlannerStrategy


@dataclass(slots=True)
class OperationPlanner:
    """Convert a high-level goal into an execution plan."""

    catalog: OperationCatalog = field(default_factory=OperationCatalog)
    strategy: PlannerStrategy = field(default_factory=RuleBasedPlannerStrategy)

    def plan(self, goal: str) -> ExecutionPlan:
        """Create a deterministic execution plan for a natural-language goal."""

        if not isinstance(goal, str) or not goal.strip():
            raise PlannerError("Goal must be a non-empty string.")

        return self.strategy.plan(goal.strip(), self.catalog)