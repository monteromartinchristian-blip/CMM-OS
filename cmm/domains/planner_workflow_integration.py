"""Phase 10.42 — Domain-owned planner/workflow coordination boundary.

DP-042 — Domain-specialized Planner and Workflow Engine integration.

Coordination only. All stateful owners (resolver, composer, registries,
planning service, workflow executor) are received by dependency injection;
this boundary owns no planner, engine, runtime, store, registry, permission,
approval, validation, event, checkpoint, persistence, or state infrastructure.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from cmm.agent_runtime.enums import WorkflowPlanChangeReason
from cmm.domains.planner_workflow_integration_contracts import (
    DomainPlannerWorkflowIntegrationRequest,
    DomainPlannerWorkflowIntegrationResult,
    DomainPlanningCapabilityView,
)
from cmm.domains.workflow_contracts import DomainWorkflowContext, DomainWorkflowResult


class DefaultDomainPlannerWorkflowIntegrator:
    """Default coordination-only integrator (Task 1 skeleton)."""

    def integrate(
        self,
        request: DomainPlannerWorkflowIntegrationRequest,
    ) -> DomainPlannerWorkflowIntegrationResult:
        """Project capabilities and plan through the canonical planner."""
        raise NotImplementedError

    def execute_workflow_reference(
        self,
        *,
        workflow_id: str,
        context: DomainWorkflowContext,
        inputs: Mapping[str, Any],
    ) -> DomainWorkflowResult:
        """Delegate a planned workflow reference to the canonical executor."""
        raise NotImplementedError

    def replan(
        self,
        request: DomainPlannerWorkflowIntegrationRequest,
        *,
        reason: WorkflowPlanChangeReason,
        reason_details: str,
    ) -> DomainPlannerWorkflowIntegrationResult:
        """Replan through the canonical ``AgentPlanningService``."""
        raise NotImplementedError


__all__ = [
    "DefaultDomainPlannerWorkflowIntegrator",
    "DomainPlanningCapabilityView",
]
