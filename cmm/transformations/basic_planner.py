"""Basic transformation planner implementation."""

from __future__ import annotations

from cmm.transformations.graph import TransformationGraph
from cmm.transformations.models import TransformationGraphNode
from cmm.transformations.plan import TransformationPlan
from cmm.transformations.planner import TransformationPlanner


class BasicTransformationPlanner(TransformationPlanner):
    """Build a linear dependency graph preserving the plan step order."""

    def build_graph(self, plan: TransformationPlan) -> TransformationGraph:
        """Create one node per step with linear dependencies between steps."""
        nodes: dict[str, TransformationGraphNode] = {}
        previous_step_id: str | None = None

        for step in plan.steps:
            dependencies = (previous_step_id,) if previous_step_id is not None else ()
            nodes[step.id] = TransformationGraphNode(
                step=step,
                dependencies=dependencies,
            )
            previous_step_id = step.id

        return TransformationGraph(nodes=nodes)
