"""Build backend-independent execution plans from transformation plans."""

from __future__ import annotations

from cmm.transformations.adapter import TransformationActionAdapter
from cmm.transformations.execution_plan import ExecutionPlan
from cmm.transformations.execution_request import ExecutionRequest
from cmm.transformations.execution_stage import ExecutionStage
from cmm.transformations.graph import TransformationGraph
from cmm.transformations.models import TransformationStep
from cmm.transformations.plan import TransformationPlan
from cmm.transformations.preconditions import ImpactAnalysisPrecondition


class InvalidTransformationGraphError(ValueError):
    """Raised when a transformation plan cannot form a valid DAG."""

    def __init__(self, message: str, errors=()) -> None:
        super().__init__(message)
        self.errors = tuple(errors)


class ExecutionPlanner:
    """Convert transformation DAG steps into one topologically ordered stage."""

    def __init__(self, adapter: TransformationActionAdapter | None = None) -> None:
        self._adapter = adapter or TransformationActionAdapter()

    def build(self, plan: TransformationPlan) -> ExecutionPlan:
        """Build one sequential stage using deterministic topological order."""
        validation = TransformationGraph.validate_plan(plan)
        if not validation.success:
            message = "; ".join(error.message for error in validation.errors)
            raise InvalidTransformationGraphError(message, validation.errors)
        graph = TransformationGraph.from_plan(plan)
        ordered_steps = tuple(node.step for node in graph.topological_order())
        requests = tuple(
            self._request_for(step)
            for step in ordered_steps
        )
        return ExecutionPlan(
            stages=(ExecutionStage(requests=requests),),
            plan_id=plan.id,
            planned_steps=tuple(step.id for step in ordered_steps),
            preconditions=plan.preconditions,
            impact_requests=tuple(
                precondition.request
                for precondition in plan.preconditions
                if isinstance(precondition, ImpactAnalysisPrecondition)
            ),
        )

    def _request_for(self, step: TransformationStep) -> ExecutionRequest:
        operation = step.operation
        request = self._adapter.adapt(operation)
        return ExecutionRequest(
            operation=request.operation,
            metadata={
                **request.metadata,
                "step_id": step.id,
                "preconditions": step.preconditions,
            },
        )
