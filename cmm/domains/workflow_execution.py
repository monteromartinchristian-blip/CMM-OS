from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any

from cmm.domains.permission_gate import (
    DomainPermissionGate,
    PermissionGateOutcome,
    PermissionGateReason,
)
from cmm.domains.workflow_contracts import (
    DomainWorkflowContext,
    DomainWorkflowDefinition,
    DomainWorkflowResult,
    DomainWorkflowRun,
)
from cmm.domains.workflow_errors import (
    DomainWorkflowApprovalError,
    DomainWorkflowUnavailableError,
)
from cmm.domains.workflow_resolution import resolve_domain_workflow
from cmm.workflows.contracts import (
    ApprovalRequest,
    WaitRequest,
    WorkflowResult,
    WorkflowRun,
)
from cmm.workflows.engine import NodeExecution, WorkflowEngine, WorkflowExecutionResult
from cmm.workflows.enums import WorkflowRunStatus


class DomainWorkflowExecutor:
    def __init__(self, *, id_factory, clock=None, operation_adapter=None, permission_gate: DomainPermissionGate | None = None, operation_definitions=None, workflow_definitions=None, parent_run_id=None, root_run_id=None, depth=0, maximum_depth=8) -> None:
        self._id_factory = id_factory
        self._clock = clock
        self._operation_adapter = operation_adapter
        self._permission_gate = permission_gate
        self._operation_definitions = dict(operation_definitions or {})
        self._workflow_definitions = dict(workflow_definitions or {})
        self._parent_run_id = parent_run_id
        self._root_run_id = root_run_id
        self._depth = depth
        self._maximum_depth = maximum_depth
        self._definitions: dict[tuple[str, str], DomainWorkflowDefinition] = {}
        self._permission_states: dict[str, dict[str, Any]] = {}

    def execute(self, definition: DomainWorkflowDefinition, context: DomainWorkflowContext, inputs: dict[str, Any]) -> DomainWorkflowRun:
        if self._permission_gate is None and (
            context.available_permissions or context.approved_gates
        ):
            raise DomainWorkflowUnavailableError(
                "domain workflow permission gate is unavailable",
                details={"reason_code": PermissionGateReason.GATE_UNAVAILABLE.value},
            )
        resolution = resolve_domain_workflow(definition, context)
        if resolution.status.value != "available":
            raise DomainWorkflowUnavailableError(
                "domain workflow is unavailable",
                details={
                    "reason_code": resolution.reasons[0]
                    if resolution.reasons
                    else "workflow.unavailable"
                },
            )

        # ── Phase 10.15 Permission Gate ──────────────────────────────────
        permission_request_id = self._id_factory()
        actor_id = context.metadata.get("actor_id", "system")
        session_id = context.metadata.get("session_id", "default")
        approval_request_ids = context.metadata.get("approval_request_ids", {})
        if not isinstance(approval_request_ids, Mapping):
            approval_request_ids = {}
        if self._permission_gate is not None:
            gate_result = self._permission_gate.evaluate_workflow_definition(
                definition,
                request_id=permission_request_id,
                actor_id=actor_id,
                session_id=session_id,
                operations=self._operation_definitions,
                workflows=self._workflow_definitions,
                approval_request_id=context.metadata.get("approval_request_id"),
                approval_request_ids=approval_request_ids,
            )
            if gate_result.outcome == PermissionGateOutcome.DENY:
                raise DomainWorkflowUnavailableError(
                    "domain workflow is blocked by current policy",
                    details={"reason_code": PermissionGateReason.POLICY_DENIED.value},
                )
            approval_pending = (
                gate_result.outcome == PermissionGateOutcome.APPROVAL_DENIED
                and gate_result.reasons[-1]
                == PermissionGateReason.APPROVAL_MISSING.value
            )
            if (
                gate_result.outcome == PermissionGateOutcome.APPROVAL_DENIED
                and not approval_pending
            ):
                raise DomainWorkflowApprovalError(
                    "domain workflow approval is not executable",
                    details={"reason_code": gate_result.reasons[-1]},
                )
            if gate_result.requires_approval or approval_pending:
                self._definitions[(definition.workflow_id, definition.version)] = definition
                now = (
                    self._clock()
                    if self._clock is not None
                    else datetime.now(timezone.utc)
                )
                run_id = self._id_factory()
                legacy_approval = ApprovalRequest(
                    self._id_factory(),
                    definition.workflow_id,
                    definition.version,
                    run_id,
                    "__workflow_start__",
                    inputs,
                )
                wait_request = WaitRequest(
                    "approval",
                    "approval required",
                    "__workflow_start__",
                    {"reason_code": PermissionGateReason.APPROVAL_MISSING.value},
                    approval_request=legacy_approval,
                )
                common_run = WorkflowRun(
                    run_id,
                    definition.workflow_id,
                    definition.version,
                    status=WorkflowRunStatus.WAITING_FOR_APPROVAL,
                    inputs=inputs,
                    checkpoint_id=self._id_factory(),
                    started_at=now,
                    updated_at=now,
                    wait_request=wait_request,
                    parent_run_id=self._parent_run_id,
                    root_run_id=self._root_run_id,
                    depth=self._depth,
                )
                execution = WorkflowExecutionResult(
                    common_run, {}, wait_request=wait_request
                )
                self._permission_states[common_run.run_id] = {
                    "context": context,
                    "request_id": permission_request_id,
                    "approval_request_id": context.metadata.get(
                        "approval_request_id"
                    ),
                    "approval_request_ids": dict(approval_request_ids),
                }
                return DomainWorkflowRun(
                    common_run,
                    definition.domain_id,
                    {"primary_domain_id": definition.domain_id},
                    execution,
                )
        # ── End Permission Gate ──────────────────────────────────────────

        self._definitions[(definition.workflow_id, definition.version)] = definition

        def adapter(node, run):
            if self._permission_gate is not None:
                node_gate = self._permission_gate.evaluate_workflow_node(
                    node,
                    definition,
                    request_id=permission_request_id,
                    actor_id=actor_id,
                    session_id=session_id,
                    operations=self._operation_definitions,
                    workflows=self._workflow_definitions,
                    approval_request_ids=approval_request_ids,
                )
                if node_gate.denied:
                    if (
                        node_gate.outcome == PermissionGateOutcome.APPROVAL_DENIED
                        and node_gate.reasons[-1]
                        == PermissionGateReason.APPROVAL_MISSING.value
                    ):
                        approval = ApprovalRequest(
                            self._id_factory(),
                            definition.workflow_id,
                            definition.version,
                            run.run_id,
                            node.node_id,
                            run.inputs,
                        )
                        return NodeExecution.wait(
                            WaitRequest(
                                "approval",
                                "approval required",
                                node.node_id,
                                {
                                    "reason_code": PermissionGateReason.APPROVAL_MISSING.value,
                                    "approval_requirement_ids": [
                                        item["requirement_id"]
                                        for item in node_gate.approval_requirements
                                    ],
                                },
                                approval_request=approval,
                            )
                        )
                    return NodeExecution.failure("permission.policy_denied")
                if node_gate.requires_approval:
                    approval = ApprovalRequest(
                        self._id_factory(),
                        definition.workflow_id,
                        definition.version,
                        run.run_id,
                        node.node_id,
                        run.inputs,
                    )
                    return NodeExecution.wait(
                        WaitRequest(
                            "approval",
                            "approval required",
                            node.node_id,
                            {
                                "reason_code": PermissionGateReason.APPROVAL_MISSING.value,
                                "approval_requirement_ids": [
                                    item["requirement_id"]
                                    for item in node_gate.approval_requirements
                                ],
                            },
                            approval_request=approval,
                        )
                    )
                if node.node_type.value == "request_approval":
                    return NodeExecution.complete({"approved": True})
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
        self._permission_states[result.run.run_id] = {
            "context": context,
            "request_id": permission_request_id,
            "approval_request_id": context.metadata.get("approval_request_id"),
            "approval_request_ids": dict(approval_request_ids),
        }
        return DomainWorkflowRun(result.run, definition.domain_id, {"primary_domain_id": definition.domain_id}, result)

    def execute_result(self, definition: DomainWorkflowDefinition, context: DomainWorkflowContext, inputs: dict[str, Any]):
        resolution = resolve_domain_workflow(definition, context)
        if resolution.status.value != "available":
            raise ValueError("domain workflow is unavailable")
        run = self.execute(definition, context, inputs)
        execution = run.execution_result
        return DomainWorkflowResult(WorkflowResult(run=execution.run, node_results=execution.node_results, events=execution.events, wait_request=execution.wait_request, attempts=execution.attempts, defined_node_ids=tuple(node.node_id for node in definition.nodes), error_code=execution.run.error_code), definition.domain_id, run.provenance)

    def resume(self, run: DomainWorkflowRun, *, condition_resolved: bool, inputs: dict[str, Any] | None = None, approval: ApprovalRequest | None = None, permission_approval_request_id: str | None = None, permission_approval_request_ids: Mapping[str, str] | None = None) -> DomainWorkflowRun:
        state = self._permission_states.get(run.common_run.run_id)
        if state is not None:
            if permission_approval_request_id is not None:
                state["approval_request_id"] = permission_approval_request_id
            if permission_approval_request_ids:
                state["approval_request_ids"].update(
                    permission_approval_request_ids
                )
            if (
                self._permission_gate is not None
                and run.common_run.wait_request is not None
                and run.common_run.wait_request.node_id == "__workflow_start__"
            ):
                definition = self._definitions[
                    (
                        run.common_run.workflow_id,
                        run.common_run.workflow_version,
                    )
                ]
                context = state["context"]
                gate_result = self._permission_gate.evaluate_workflow_definition(
                    definition,
                    request_id=state["request_id"],
                    actor_id=context.metadata.get("actor_id", "system"),
                    session_id=context.metadata.get("session_id", "default"),
                    operations=self._operation_definitions,
                    workflows=self._workflow_definitions,
                    approval_request_id=state["approval_request_id"],
                    approval_request_ids=state["approval_request_ids"],
                )
                if not gate_result.allowed:
                    raise DomainWorkflowApprovalError(
                        "domain workflow approval is not executable",
                        details={"reason_code": gate_result.reasons[-1]},
                    )
        result = self._engine_for_run(run).resume(run.common_run, condition_resolved=condition_resolved, inputs=inputs, approval=approval)
        return DomainWorkflowRun(result.run, run.primary_domain_id, run.provenance, result)

    def _engine_for_run(self, run: DomainWorkflowRun) -> WorkflowEngine:
        definition = self._definitions.get((run.common_run.workflow_id, run.common_run.workflow_version))
        if definition is None:
            raise ValueError("domain workflow definition is not available for resume")

        def adapter(node, current_run):
            state = self._permission_states.get(current_run.run_id)
            if self._permission_gate is not None and state is not None:
                context = state["context"]
                node_gate = self._permission_gate.evaluate_workflow_node(
                    node,
                    definition,
                    request_id=state["request_id"],
                    actor_id=context.metadata.get("actor_id", "system"),
                    session_id=context.metadata.get("session_id", "default"),
                    operations=self._operation_definitions,
                    workflows=self._workflow_definitions,
                    approval_request_ids=state["approval_request_ids"],
                )
                if node_gate.denied:
                    if (
                        node_gate.outcome == PermissionGateOutcome.APPROVAL_DENIED
                        and node_gate.reasons[-1]
                        == PermissionGateReason.APPROVAL_MISSING.value
                    ):
                        next_approval = ApprovalRequest(
                            self._id_factory(),
                            definition.workflow_id,
                            definition.version,
                            current_run.run_id,
                            node.node_id,
                            current_run.inputs,
                        )
                        return NodeExecution.wait(
                            WaitRequest(
                                "approval",
                                "approval required",
                                node.node_id,
                                {
                                    "reason_code": PermissionGateReason.APPROVAL_MISSING.value
                                },
                                approval_request=next_approval,
                            )
                        )
                    return NodeExecution.failure(node_gate.reasons[-1])
                if node_gate.requires_approval:
                    next_approval = ApprovalRequest(
                        self._id_factory(),
                        definition.workflow_id,
                        definition.version,
                        current_run.run_id,
                        node.node_id,
                        current_run.inputs,
                    )
                    return NodeExecution.wait(
                        WaitRequest(
                            "approval",
                            "approval required",
                            node.node_id,
                            {
                                "reason_code": PermissionGateReason.APPROVAL_MISSING.value
                            },
                            approval_request=next_approval,
                        )
                    )
                if node.node_type.value == "request_approval":
                    return NodeExecution.complete({"approved": True})
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
