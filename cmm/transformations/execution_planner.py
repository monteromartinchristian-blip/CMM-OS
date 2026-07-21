"""Build backend-independent execution plans from transformation plans."""

from __future__ import annotations

from cmm.transformations.adapter import TransformationActionAdapter
from cmm.transformations.execution_plan import ExecutionPlan
from cmm.transformations.execution_request import ExecutionRequest
from cmm.transformations.execution_stage import ExecutionStage
from cmm.transformations.operation import TransformationOperation
from cmm.transformations.plan import TransformationPlan


class ExecutionPlanner:
    """Convert ordered transformation steps into one sequential execution stage."""

    def __init__(self, adapter: TransformationActionAdapter | None = None) -> None:
        self._adapter = adapter or TransformationActionAdapter()

    def build(self, plan: TransformationPlan) -> ExecutionPlan:
        """Build one sequential stage while preserving plan-step order."""
        requests = tuple(
            self._request_for(step.id, step.operation)
            for step in plan.steps
        )
        return ExecutionPlan(stages=(ExecutionStage(requests=requests),))

    def _request_for(
        self,
        step_id: str,
        operation: TransformationOperation,
    ) -> ExecutionRequest:
        request = self._adapter.adapt(operation)
        return ExecutionRequest(
            operation=request.operation,
            metadata={**request.metadata, "step_id": step_id},
        )
