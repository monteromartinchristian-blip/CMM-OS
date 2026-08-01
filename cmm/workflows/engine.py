from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from .completion import CompletionCriteria, evaluate_completion_criteria
from .contracts import (
    ApprovalRequest,
    WaitRequest,
    WorkflowDefinition,
    WorkflowEvent,
    WorkflowNodeResult,
    WorkflowRun,
)
from .enums import WorkflowNodeStatus, WorkflowRunStatus
from .errors import WorkflowExecutionError, WorkflowStateError
from .graph import ready_node_ids, validate_workflow_graph


@dataclass(frozen=True, slots=True)
class NodeExecution:
    status: WorkflowNodeStatus
    output: Mapping[str, Any] = field(default_factory=dict)
    wait_request: WaitRequest | None = None
    error_code: str | None = None
    retryable: bool = False
    operation_result: Mapping[str, Any] | None = None
    subworkflow_result: Mapping[str, Any] | None = None
    reason_code: str | None = None

    @classmethod
    def complete(cls, output: Mapping[str, Any] | None = None, *, operation_result: Mapping[str, Any] | None = None, subworkflow_result: Mapping[str, Any] | None = None) -> NodeExecution:
        return cls(WorkflowNodeStatus.COMPLETED, {} if output is None else output, operation_result=operation_result, subworkflow_result=subworkflow_result)

    @classmethod
    def wait(cls, request: WaitRequest) -> NodeExecution:
        return cls(WorkflowNodeStatus.WAITING, wait_request=request)

    @classmethod
    def failure(cls, error_code: str, *, retryable: bool = False) -> NodeExecution:
        return cls(WorkflowNodeStatus.FAILED, error_code=error_code, retryable=retryable)

    @classmethod
    def not_applicable(cls, reason_code: str) -> NodeExecution:
        return cls(WorkflowNodeStatus.SKIPPED, reason_code=reason_code)


@dataclass(frozen=True, slots=True)
class WorkflowExecutionResult:
    run: WorkflowRun
    node_results: Mapping[str, WorkflowNodeResult]
    wait_request: WaitRequest | None = None
    events: tuple[WorkflowEvent, ...] = ()
    attempts: Mapping[str, int] = field(default_factory=dict)

    @property
    def status(self) -> WorkflowRunStatus:
        return self.run.status


class WorkflowEngine:
    def __init__(self, definition: WorkflowDefinition, *, id_factory: Callable[[], str], clock: Callable[[], datetime] | None = None, node_adapter: Callable[[Any, WorkflowRun], Any] | None = None, parent_run_id: str | None = None, root_run_id: str | None = None, depth: int = 0, maximum_depth: int = 8) -> None:
        validate_workflow_graph(definition)
        if node_adapter is None:
            raise WorkflowExecutionError("node_adapter is required")
        self._definition = definition
        self._id_factory = id_factory
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._node_adapter = node_adapter
        self._parent_run_id = parent_run_id
        self._root_run_id = root_run_id
        self._depth = depth
        self._maximum_depth = maximum_depth
        self._node_results: dict[str, WorkflowNodeResult] = {}
        self._attempts: dict[str, int] = {}
        self._events: list[WorkflowEvent] = []
        self._run: WorkflowRun | None = None

    def _event(self, event_type: str, run_id: str, node_id: str | None = None) -> None:
        self._events.append(WorkflowEvent(self._id_factory(), event_type, self._definition.workflow_id, run_id, self._clock(), {"node_id": node_id} if node_id else {}))

    def _coerce(self, value: Any, node_id: str) -> NodeExecution:
        if isinstance(value, NodeExecution):
            return value
        if isinstance(value, WaitRequest):
            return NodeExecution.wait(value)
        if isinstance(value, Mapping):
            raise WorkflowExecutionError(f"node {node_id} adapter must return explicit NodeExecution")
        raise WorkflowExecutionError(f"node {node_id} adapter returned invalid result")

    def rehydrate(self, result: WorkflowExecutionResult) -> None:
        """Restore the accumulated in-memory execution state for a resumed run."""
        if result.run.workflow_id != self._definition.workflow_id or result.run.workflow_version != self._definition.version:
            raise WorkflowStateError("execution result does not match workflow definition")
        self._run = result.run
        self._node_results = dict(result.node_results)
        self._attempts = dict(result.attempts)
        self._events = list(result.events)

    def _run_ready(self, run: WorkflowRun, inputs: Mapping[str, Any], retry_policy: Mapping[str, int] | None = None) -> WorkflowExecutionResult:
        completed = list(run.completed_nodes)
        failed = list(run.failed_nodes)
        waiting = list(run.waiting_nodes)
        skipped = list(run.skipped_nodes)
        outputs = dict(run.outputs)
        processed: set[str] = set(completed) | set(failed) | set(skipped)
        while True:
            resolved_dependencies = tuple(completed + skipped)
            pending = set(ready_node_ids(self._definition, resolved_dependencies)) - processed
            if not pending:
                break
            for node_id in sorted(pending):
                node = next(node for node in self._definition.nodes if node.node_id == node_id)
                limit = max(1, int((retry_policy or {}).get(node_id, 1)))
                while True:
                    self._attempts[node_id] = self._attempts.get(node_id, 0) + 1
                    outcome = self._coerce(self._node_adapter(node, run), node_id)
                    if outcome.status is WorkflowNodeStatus.SKIPPED and node.required:
                        outcome = NodeExecution.failure(outcome.reason_code or "node.not_applicable")
                    if outcome.status is WorkflowNodeStatus.FAILED and outcome.retryable and self._attempts[node_id] < limit:
                        self._node_results[node_id] = WorkflowNodeResult(node_id, node.node_type, outcome.status, self._attempts[node_id], inputs, outcome.output, outcome.error_code, outcome.operation_result, outcome.subworkflow_result, outcome.reason_code, outcome.wait_request)
                        self._event("node." + outcome.status.value, run.run_id, node_id)
                        continue
                    if outcome.status is WorkflowNodeStatus.FAILED and not node.required:
                        outcome = NodeExecution.not_applicable(outcome.error_code or "node.failed")
                    self._node_results[node_id] = WorkflowNodeResult(node_id, node.node_type, outcome.status, self._attempts[node_id], inputs, outcome.output, outcome.error_code, outcome.operation_result, outcome.subworkflow_result, outcome.reason_code, outcome.wait_request)
                    self._event("node." + outcome.status.value, run.run_id, node_id)
                    if outcome.status is WorkflowNodeStatus.COMPLETED:
                        completed.append(node_id)
                        processed.add(node_id)
                        outputs[node_id] = dict(outcome.output)
                        break
                    if outcome.status is WorkflowNodeStatus.WAITING:
                        if outcome.wait_request is None:
                            raise WorkflowExecutionError("waiting node requires WaitRequest")
                        waiting.append(node_id)
                        status = {"input": WorkflowRunStatus.WAITING_FOR_INPUT, "resource": WorkflowRunStatus.WAITING_FOR_RESOURCE, "approval": WorkflowRunStatus.WAITING_FOR_APPROVAL}.get(outcome.wait_request.kind, WorkflowRunStatus.PAUSED)
                        checkpoint = self._id_factory()
                        updated = WorkflowRun(run.run_id, run.workflow_id, run.workflow_version, status=status, completed_nodes=tuple(completed), failed_nodes=tuple(failed), waiting_nodes=tuple(waiting), skipped_nodes=tuple(skipped), inputs=inputs, outputs=outputs, checkpoint_id=checkpoint, started_at=run.started_at, updated_at=self._clock(), wait_request=outcome.wait_request, parent_run_id=run.parent_run_id, root_run_id=run.root_run_id, depth=run.depth)
                        self._run = updated
                        return WorkflowExecutionResult(updated, dict(self._node_results), outcome.wait_request, tuple(self._events), dict(self._attempts))
                    if outcome.status is WorkflowNodeStatus.SKIPPED:
                        skipped.append(node_id)
                        processed.add(node_id)
                        break
                    failed.append(node_id)
                    processed.add(node_id)
                    updated = WorkflowRun(run.run_id, run.workflow_id, run.workflow_version, status=WorkflowRunStatus.FAILED, completed_nodes=tuple(completed), failed_nodes=tuple(failed), skipped_nodes=tuple(skipped), inputs=inputs, outputs=outputs, checkpoint_id=self._id_factory(), started_at=run.started_at, updated_at=self._clock(), error_code=outcome.error_code or "node.failed", parent_run_id=run.parent_run_id, root_run_id=run.root_run_id, depth=run.depth)
                    self._run = updated
                    return WorkflowExecutionResult(updated, dict(self._node_results), events=tuple(self._events), attempts=dict(self._attempts))
        if len(completed) + len(skipped) == len(self._definition.nodes):
            finished = self._clock()
            criteria = CompletionCriteria(**dict(self._definition.completion_criteria))
            required = tuple(node.node_id for node in self._definition.nodes if node.required)
            if not evaluate_completion_criteria(criteria, completed=completed, failed=failed, skipped=skipped, required_nodes=required):
                updated = WorkflowRun(run.run_id, run.workflow_id, run.workflow_version, status=WorkflowRunStatus.FAILED, completed_nodes=tuple(completed), failed_nodes=tuple(failed), skipped_nodes=tuple(skipped), inputs=inputs, outputs=outputs, started_at=run.started_at, updated_at=finished, error_code="completion.criteria", parent_run_id=run.parent_run_id, root_run_id=run.root_run_id, depth=run.depth)
            else:
                updated = WorkflowRun(run.run_id, run.workflow_id, run.workflow_version, status=WorkflowRunStatus.COMPLETED, completed_nodes=tuple(completed), skipped_nodes=tuple(skipped), inputs=inputs, outputs=outputs, started_at=run.started_at, updated_at=finished, completed_at=finished, parent_run_id=run.parent_run_id, root_run_id=run.root_run_id, depth=run.depth)
        else:
                updated = WorkflowRun(run.run_id, run.workflow_id, run.workflow_version, status=WorkflowRunStatus.FAILED, completed_nodes=tuple(completed), failed_nodes=tuple(failed), skipped_nodes=tuple(skipped), inputs=inputs, outputs=outputs, checkpoint_id=self._id_factory(), started_at=run.started_at, updated_at=self._clock(), error_code="workflow.unresolved", parent_run_id=run.parent_run_id, root_run_id=run.root_run_id, depth=run.depth)
        self._run = updated
        self._event("workflow." + updated.status.value, updated.run_id)
        return WorkflowExecutionResult(updated, dict(self._node_results), events=tuple(self._events), attempts=dict(self._attempts))

    def start(self, inputs: Mapping[str, Any], *, retry_policy: Mapping[str, int] | None = None) -> WorkflowExecutionResult:
        now = self._clock()
        run_id = self._id_factory()
        if self._depth > self._maximum_depth:
            raise WorkflowStateError("maximum subworkflow depth exceeded")
        run = WorkflowRun(run_id, self._definition.workflow_id, self._definition.version, inputs=inputs, status=WorkflowRunStatus.RUNNING, started_at=now, updated_at=now, parent_run_id=self._parent_run_id, root_run_id=self._root_run_id or run_id, depth=self._depth)
        self._run = run
        self._event("workflow.running", run.run_id)
        return self._run_ready(run, inputs, retry_policy)

    def resume(self, run: WorkflowRun, *, condition_resolved: bool, inputs: Mapping[str, Any] | None = None, retry_policy: Mapping[str, int] | None = None, approval: ApprovalRequest | None = None) -> WorkflowExecutionResult:
        if run.status not in (WorkflowRunStatus.PAUSED, WorkflowRunStatus.WAITING_FOR_INPUT, WorkflowRunStatus.WAITING_FOR_RESOURCE, WorkflowRunStatus.WAITING_FOR_APPROVAL):
            raise WorkflowStateError("run is not resumable")
        if not condition_resolved:
            raise WorkflowStateError("resume condition is not resolved")
        if run.status is WorkflowRunStatus.WAITING_FOR_APPROVAL:
            if approval is None or run.wait_request is None or run.wait_request.approval_request is None:
                raise WorkflowStateError("valid approval is required to resume")
            target = run.wait_request.approval_request
            approval.assert_matches(run_id=run.run_id, workflow_id=run.workflow_id, workflow_version=run.workflow_version, node_id=run.wait_request.node_id, inputs=run.inputs)
            if approval.status.value != "approved" or approval.fingerprint != target.fingerprint:
                raise WorkflowStateError("approval is not valid for this run")
        resumed = WorkflowRun(run.run_id, run.workflow_id, run.workflow_version, status=WorkflowRunStatus.RUNNING, completed_nodes=run.completed_nodes, failed_nodes=run.failed_nodes, waiting_nodes=(), skipped_nodes=run.skipped_nodes, inputs=run.inputs if inputs is None else inputs, outputs=run.outputs, checkpoint_id=run.checkpoint_id, started_at=run.started_at, updated_at=self._clock(), parent_run_id=run.parent_run_id, root_run_id=run.root_run_id, depth=run.depth)
        if run.started_at is None:
            return WorkflowExecutionResult(resumed, dict(self._node_results), attempts=dict(self._attempts))
        return self._run_ready(resumed, resumed.inputs, retry_policy)

    @staticmethod
    def pause(run: WorkflowRun, checkpoint_id: str) -> WorkflowRun:
        if run.status not in (WorkflowRunStatus.RUNNING, WorkflowRunStatus.WAITING_FOR_INPUT, WorkflowRunStatus.WAITING_FOR_RESOURCE, WorkflowRunStatus.WAITING_FOR_APPROVAL):
            raise WorkflowStateError("run cannot be paused from its current status")
        return WorkflowRun(run.run_id, run.workflow_id, run.workflow_version, status=WorkflowRunStatus.PAUSED, completed_nodes=run.completed_nodes, failed_nodes=run.failed_nodes, waiting_nodes=run.waiting_nodes, skipped_nodes=run.skipped_nodes, inputs=run.inputs, outputs=run.outputs, checkpoint_id=checkpoint_id, started_at=run.started_at, updated_at=run.updated_at, parent_run_id=run.parent_run_id, root_run_id=run.root_run_id, depth=run.depth)

    def cancel(self, run: WorkflowRun) -> WorkflowRun:
        if run.status in (WorkflowRunStatus.COMPLETED, WorkflowRunStatus.CANCELLED):
            raise WorkflowStateError("terminal run cannot be cancelled")
        known = set(run.completed_nodes) | set(run.failed_nodes) | set(run.skipped_nodes)
        remaining = tuple(node.node_id for node in self._definition.nodes if node.node_id not in known)
        return WorkflowRun(run.run_id, run.workflow_id, run.workflow_version, status=WorkflowRunStatus.CANCELLED, completed_nodes=run.completed_nodes, failed_nodes=run.failed_nodes, waiting_nodes=(), skipped_nodes=run.skipped_nodes + remaining, inputs=run.inputs, outputs=run.outputs, checkpoint_id=run.checkpoint_id, started_at=run.started_at, updated_at=run.updated_at, wait_request=None, parent_run_id=run.parent_run_id, root_run_id=run.root_run_id, depth=run.depth)

    @staticmethod
    def recover(run: WorkflowRun) -> WorkflowRun:
        if run.status is not WorkflowRunStatus.FAILED or not run.checkpoint_id:
            raise WorkflowStateError("recovery requires a failed run with a checkpoint")
        return WorkflowRun(run.run_id, run.workflow_id, run.workflow_version, status=WorkflowRunStatus.RECOVERING, completed_nodes=run.completed_nodes, failed_nodes=run.failed_nodes, skipped_nodes=run.skipped_nodes, inputs=run.inputs, outputs=run.outputs, checkpoint_id=run.checkpoint_id, started_at=run.started_at, updated_at=run.updated_at, parent_run_id=run.parent_run_id, root_run_id=run.root_run_id, depth=run.depth)
