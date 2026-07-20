"""Facade for graph-based planning.

PlanningEngine coordinates the graph-building, validation, and topological
sorting steps while keeping the current planner and executor layers unchanged.
"""

from __future__ import annotations

from kernel.planner.execution_plan import ExecutionPlan
from kernel.planner.execution_graph import ExecutionGraph
from kernel.planner.exceptions import PlannerError
from kernel.planner.graph_builder import GraphBuilder
from kernel.planner.graph_validator import GraphValidator
from kernel.planner.operations import Operation
from kernel.planner.topological_sorter import TopologicalSorter


class PlanningEngine:
    """Coordinate the execution graph pipeline without executing operations."""

    def __init__(
        self,
        builder: GraphBuilder | None = None,
        validator: GraphValidator | None = None,
        sorter: TopologicalSorter | None = None,
    ) -> None:
        self.builder = builder or GraphBuilder()
        self.validator = validator or GraphValidator()
        self.sorter = sorter or TopologicalSorter()

    def plan(self, execution_plan: ExecutionPlan) -> list[Operation]:
        """Build, validate, and sort an execution plan.

        Raises:
            PlannerError: If graph validation fails.
        """

        graph = self.builder.build(execution_plan)
        validation_result = self.validator.validate(graph)

        if validation_result.has_errors():
            raise PlannerError("Graph validation failed: " + "; ".join(validation_result.errors))

        return self.sorter.sort(graph)
