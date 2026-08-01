from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from cmm.domains.workflow_contracts import (
    DomainWorkflowContext,
    DomainWorkflowDefinition,
    DomainWorkflowResult,
    DomainWorkflowRun,
)
from cmm.domains.workflow_resolution import resolve_domain_workflow
from cmm.workflows.contracts import ApprovalRequest, WaitRequest, WorkflowResult
from cmm.workflows.engine import NodeExecution, WorkflowEngine, WorkflowExecutionResult


class DomainWorkflowExecutor:
    def __init__(self, *, id_factory, clock=None, operation_adapter=None, parent_run_id=None, root_run_id=None, depth=0, maximum_depth=8) -> None:
        self._id_factory = id_factory
        self._clock = clock
        self._operation_adapter = operation_adapter
        self._parent_run_id = parent_run_id
        self._root_run_id = root_run_id
        self._depth = depth
        self._maximum_depth = maximum_depth
        self._definitions: dict[tuple[str, str], DomainWorkflowDefinition] = {}

    def execute(self, definition: DomainWorkflowDefinition, context: DomainWorkflowContext, inputs: dict[str, Any]) -> DomainWorkflowRun:
        resolution = resolve_domain_workflow(definition, context)
        if resolution.status.value != "available":
            raise ValueError("domain workflow is unavailable")

        self._definitions[(definition.workflow_id, definition.version)] = definition

        def adapter(node, run):
            if self._operation_adapter is not None:
                value = self._operation_adapter(node, run)
                if isinstance(value, NodeExecution):
                    return value
                if node.operation_id and isinstance(value, Mapping):
                    return NodeExecution.complete(value, operation_result=value)
                return value
            if node.node_type.value == "request_approval" and node.approval_gate not in context.approved_gates:
                approval = ApprovalRequest(self._id_factory(), definition.workflow_id, definition.version, run.run_id, node.node_id, run.inputs)
                return NodeExecution.wait(WaitRequest("approval", "approval required", node.node_id, {"gate": node.approval_gate}, approval_request=approval))
            return NodeExecution.not_applicable("capability.not_configured")

        result: WorkflowExecutionResult = WorkflowEngine(definition.to_common(), id_factory=self._id_factory, clock=self._clock, node_adapter=adapter, parent_run_id=self._parent_run_id, root_run_id=self._root_run_id, depth=self._depth, maximum_depth=self._maximum_depth).start(inputs)
        return DomainWorkflowRun(result.run, definition.domain_id, {"primary_domain_id": definition.domain_id}, result)

    def execute_result(self, definition: DomainWorkflowDefinition, context: DomainWorkflowContext, inputs: dict[str, Any]):
        resolution = resolve_domain_workflow(definition, context)
        if resolution.status.value != "available":
            raise ValueError("domain workflow is unavailable")
        run = self.execute(definition, context, inputs)
        execution = run.execution_result
        return DomainWorkflowResult(WorkflowResult(run=execution.run, node_results=execution.node_results, events=execution.events, wait_request=execution.wait_request, attempts=execution.attempts, defined_node_ids=tuple(node.node_id for node in definition.nodes), error_code=execution.run.error_code), definition.domain_id, run.provenance)

    def resume(self, run: DomainWorkflowRun, *, condition_resolved: bool, inputs: dict[str, Any] | None = None, approval: ApprovalRequest | None = None) -> DomainWorkflowRun:
        result = self._engine_for_run(run).resume(run.common_run, condition_resolved=condition_resolved, inputs=inputs, approval=approval)
        return DomainWorkflowRun(result.run, run.primary_domain_id, run.provenance, result)

    def _engine_for_run(self, run: DomainWorkflowRun) -> WorkflowEngine:
        definition = self._definitions.get((run.common_run.workflow_id, run.common_run.workflow_version))
        if definition is None:
            raise ValueError("domain workflow definition is not available for resume")

        def adapter(node, current_run):
            if self._operation_adapter is not None:
                value = self._operation_adapter(node, current_run)
                if isinstance(value, NodeExecution):
                    return value
                if node.operation_id and isinstance(value, Mapping):
                    return NodeExecution.complete(value, operation_result=value)
                return value
            if node.node_type.value == "request_approval":
                return NodeExecution.complete({"approved": True})
            return NodeExecution.not_applicable("capability.not_configured")

        engine = WorkflowEngine(definition.to_common(), id_factory=self._id_factory, clock=self._clock, node_adapter=adapter, maximum_depth=self._maximum_depth)
        if run.execution_result is None:
            raise ValueError("domain workflow run has no execution state to resume")
        engine.rehydrate(run.execution_result)
        return engine
