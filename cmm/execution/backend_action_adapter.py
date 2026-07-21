"""Backend adapter from transformation execution requests to actions."""

from __future__ import annotations

from cmm.execution.action_planner import Action, ActionType
from cmm.transformations.execution_plan import ExecutionPlan
from cmm.transformations.execution_request import ExecutionRequest


class BackendActionAdapter:
    """Convert backend-independent execution requests into action queue entries."""

    def adapt(self, plan: ExecutionPlan) -> tuple[Action, ...]:
        """Translate every staged request in ``plan`` into ordered actions."""
        return tuple(
            self._action_for(request, order)
            for order, request in enumerate(plan.all_requests(), start=1)
        )

    def _action_for(self, request: ExecutionRequest, order: int) -> Action:
        metadata = request.metadata
        target = next(
            (
                metadata[key]
                for key in (
                    "target",
                    "path",
                    "module_name",
                    "module",
                    "symbol",
                    "scope",
                )
                if key in metadata
            ),
            request.operation.name,
        )
        if not isinstance(target, str) or not target.strip():
            target = request.operation.name

        action_id = metadata.get("step_id", f"action-{order}")
        if not isinstance(action_id, str) or not action_id.strip():
            action_id = f"action-{order}"

        return Action(
            id=action_id,
            order=order,
            action_type=ActionType.PREPARE_MODIFICATION,
            target=target,
            description=request.operation.describe(),
            metadata=metadata,
        )
