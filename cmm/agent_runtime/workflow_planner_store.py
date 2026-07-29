"""Phase 9.7 – Workflow Planner Version Store.

In-memory repository and version manager for AgentWorkflowPlan instances.
"""

from __future__ import annotations

from cmm.agent_runtime.enums import WorkflowPlanStatus
from cmm.agent_runtime.errors import WorkflowPlanVersionError
from cmm.agent_runtime.workflow_planner_contracts import AgentWorkflowPlan


class InMemoryWorkflowPlanStore:
    """Decoupled in-memory store for AgentWorkflowPlan instances and version histories."""

    def __init__(self) -> None:
        self._plans_by_id: dict[str, AgentWorkflowPlan] = {}
        self._plans_by_workflow: dict[str, list[AgentWorkflowPlan]] = {}

    def add(self, plan: AgentWorkflowPlan) -> None:
        """Store a new plan version or plan instance."""
        if not plan or not plan.id:
            raise WorkflowPlanVersionError("Cannot store plan with empty id.")

        if plan.id in self._plans_by_id:
            raise WorkflowPlanVersionError(
                f"Plan id '{plan.id}' already exists in store."
            )

        self._plans_by_id[plan.id] = plan
        if plan.workflow_id not in self._plans_by_workflow:
            self._plans_by_workflow[plan.workflow_id] = []
        self._plans_by_workflow[plan.workflow_id].append(plan)

    def get(self, plan_id: str) -> AgentWorkflowPlan | None:
        """Retrieve plan by plan_id."""
        return self._plans_by_id.get(plan_id)

    def get_version(self, workflow_id: str, version: int) -> AgentWorkflowPlan | None:
        """Retrieve specific plan version for workflow_id."""
        versions = self._plans_by_workflow.get(workflow_id, [])
        for plan in versions:
            if plan.version == version:
                return plan
        return None

    def list_versions(self, workflow_id: str) -> list[AgentWorkflowPlan]:
        """Return all stored plan versions for workflow_id ordered by version ascending."""
        versions = self._plans_by_workflow.get(workflow_id, [])
        return sorted(versions, key=lambda p: p.version)

    def get_latest(self, workflow_id: str) -> AgentWorkflowPlan | None:
        """Return the latest plan version for workflow_id."""
        versions = self.list_versions(workflow_id)
        return versions[-1] if versions else None

    def supersede(self, plan_id: str, replacement_id: str) -> None:
        """Mark plan_id as superseded by replacement_id."""
        plan = self.get(plan_id)
        if not plan:
            raise WorkflowPlanVersionError(
                f"Cannot supersede non-existent plan: {plan_id}"
            )

        # Construct updated plan with SUPERSEDED status without mutating existing object
        plan_dict = plan.to_dict()
        plan_dict["status"] = WorkflowPlanStatus.SUPERSEDED.value
        plan_dict["metadata"] = {
            **plan_dict.get("metadata", {}),
            "superseded_by": replacement_id,
        }
        updated_plan = AgentWorkflowPlan.from_dict(plan_dict)

        self._plans_by_id[plan_id] = updated_plan

        # Update in workflow list
        if plan.workflow_id in self._plans_by_workflow:
            wf_list = self._plans_by_workflow[plan.workflow_id]
            self._plans_by_workflow[plan.workflow_id] = [
                updated_plan if p.id == plan_id else p for p in wf_list
            ]
