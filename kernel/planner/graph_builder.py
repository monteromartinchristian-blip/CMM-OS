"""Build execution graphs from execution plans.

This is the first bridge between the current linear plan model and the future
graph-based execution model. The builder intentionally performs no validation
or ordering logic.
"""

from __future__ import annotations

from kernel.planner.execution_graph import ExecutionGraph
from kernel.planner.execution_plan import ExecutionPlan


class GraphBuilder:
    """Convert an execution plan into an execution graph."""

    def build(self, plan: ExecutionPlan) -> ExecutionGraph:
        """Build a graph containing every operation from the plan."""

        graph = ExecutionGraph()

        for operation in plan:
            graph.add_operation(operation)

        return graph