from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from types import MappingProxyType
from typing import Any

from .enums import (
    ApprovalStatus,
    WorkflowNodeStatus,
    WorkflowNodeType,
    WorkflowRunStatus,
)
from .errors import (
    WorkflowContractError,
    WorkflowSerializationError,
    WorkflowStateError,
)


def _freeze(value: Any, path: str = "value") -> Any:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise WorkflowContractError(f"{path} must be finite")
        return value
    if isinstance(value, Mapping):
        if any(not isinstance(k, str) for k in value):
            raise WorkflowContractError(f"{path} keys must be strings")
        return MappingProxyType({k: _freeze(v, f"{path}.{k}") for k, v in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(v, f"{path}[]") for v in value)
    raise WorkflowContractError(f"{path} is not JSON-safe")


def _thaw(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {k: _thaw(v) for k, v in value.items()}
    if isinstance(value, tuple):
        return [_thaw(v) for v in value]
    return value


def _dt(value: datetime | None, name: str) -> datetime | None:
    if value is not None and (not isinstance(value, datetime) or value.tzinfo is None):
        raise WorkflowContractError(f"{name} must be timezone-aware")
    return value


def _enum(value: Any, kind: type, name: str):
    try:
        return value if isinstance(value, kind) else kind(value)
    except (TypeError, ValueError) as exc:
        raise WorkflowContractError(f"invalid {name}") from exc


def _text(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise WorkflowContractError(f"{name} must be non-empty")
    return value.strip()


@dataclass(frozen=True, slots=True)
class WorkflowNode:
    node_id: str
    node_type: WorkflowNodeType | str
    name: str
    dependencies: tuple[str, ...] = ()
    input_bindings: Mapping[str, Any] = field(default_factory=dict)
    output_bindings: Mapping[str, Any] = field(default_factory=dict)
    operation_id: str | None = None
    operation_version: str | None = None
    subworkflow_id: str | None = None
    subworkflow_version: str | None = None
    approval_gate: str | None = None
    wait_condition: Mapping[str, Any] | None = None
    required: bool = True
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "node_id", _text(self.node_id, "node_id"))
        object.__setattr__(self, "name", _text(self.name, "name"))
        object.__setattr__(self, "node_type", _enum(self.node_type, WorkflowNodeType, "node_type"))
        if not isinstance(self.required, bool):
            raise WorkflowContractError("required must be boolean")
        deps = tuple(_text(v, "dependency") for v in self.dependencies)
        if len(deps) != len(set(deps)):
            raise WorkflowContractError("dependencies must be unique")
        object.__setattr__(self, "dependencies", deps)
        for name in ("input_bindings", "output_bindings", "wait_condition", "metadata"):
            value = getattr(self, name)
            object.__setattr__(self, name, None if value is None else _freeze(value, name))

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id, "node_type": self.node_type.value, "name": self.name,
            "dependencies": list(self.dependencies), "input_bindings": _thaw(self.input_bindings),
            "output_bindings": _thaw(self.output_bindings), "operation_id": self.operation_id,
            "operation_version": self.operation_version, "subworkflow_id": self.subworkflow_id,
            "subworkflow_version": self.subworkflow_version, "approval_gate": self.approval_gate,
            "wait_condition": _thaw(self.wait_condition), "required": self.required,
            "metadata": _thaw(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> WorkflowNode:
        known = set(cls.__dataclass_fields__)
        if not isinstance(data, Mapping) or set(data) - known:
            raise WorkflowSerializationError("unknown or invalid WorkflowNode fields")
        return cls(**dict(data))


@dataclass(frozen=True, slots=True)
class WorkflowDefinition:
    workflow_id: str
    version: str
    name: str
    description: str = ""
    nodes: tuple[WorkflowNode, ...] = ()
    enabled: bool = True
    metadata: Mapping[str, Any] = field(default_factory=dict)
    completion_criteria: Mapping[str, Any] = field(default_factory=dict)
    terminal_node_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "workflow_id", _text(self.workflow_id, "workflow_id"))
        object.__setattr__(self, "version", _text(self.version, "version"))
        object.__setattr__(self, "name", _text(self.name, "name"))
        object.__setattr__(self, "nodes", tuple(self.nodes))
        if not isinstance(self.enabled, bool):
            raise WorkflowContractError("enabled must be boolean")
        object.__setattr__(self, "metadata", _freeze(self.metadata, "metadata"))
        object.__setattr__(self, "completion_criteria", _freeze(self.completion_criteria, "completion_criteria"))
        object.__setattr__(self, "terminal_node_ids", tuple(self.terminal_node_ids))

    def to_dict(self) -> dict[str, Any]:
        return {"workflow_id": self.workflow_id, "version": self.version, "name": self.name,
                "description": self.description, "nodes": [n.to_dict() for n in self.nodes],
                "enabled": self.enabled, "metadata": _thaw(self.metadata), "completion_criteria": _thaw(self.completion_criteria), "terminal_node_ids": list(self.terminal_node_ids)}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> WorkflowDefinition:
        known = {"workflow_id", "version", "name", "description", "nodes", "enabled", "metadata", "completion_criteria", "terminal_node_ids"}
        if not isinstance(data, Mapping) or set(data) - known:
            raise WorkflowSerializationError("unknown or invalid WorkflowDefinition fields")
        values = dict(data)
        values["nodes"] = tuple(WorkflowNode.from_dict(n) for n in values.get("nodes", ()))
        return cls(**values)


@dataclass(frozen=True, slots=True)
class WorkflowRun:
    run_id: str
    workflow_id: str
    workflow_version: str
    status: WorkflowRunStatus = WorkflowRunStatus.PENDING
    completed_nodes: tuple[str, ...] = ()
    failed_nodes: tuple[str, ...] = ()
    waiting_nodes: tuple[str, ...] = ()
    skipped_nodes: tuple[str, ...] = ()
    inputs: Mapping[str, Any] = field(default_factory=dict)
    outputs: Mapping[str, Any] = field(default_factory=dict)
    checkpoint_id: str | None = None
    started_at: datetime | None = None
    updated_at: datetime | None = None
    completed_at: datetime | None = None
    error_code: str | None = None
    wait_request: WaitRequest | None = None
    parent_run_id: str | None = None
    root_run_id: str | None = None
    depth: int = 0

    def __post_init__(self) -> None:
        for name in ("run_id", "workflow_id", "workflow_version"):
            object.__setattr__(self, name, _text(getattr(self, name), name))
        object.__setattr__(self, "status", _enum(self.status, WorkflowRunStatus, "status"))
        for name in ("completed_nodes", "failed_nodes", "waiting_nodes", "skipped_nodes"):
            vals = tuple(getattr(self, name))
            if len(vals) != len(set(vals)):
                raise WorkflowContractError(f"{name} must be unique")
            object.__setattr__(self, name, vals)
        for name in ("inputs", "outputs"):
            object.__setattr__(self, name, _freeze(getattr(self, name), name))
        for name in ("started_at", "updated_at", "completed_at"):
            _dt(getattr(self, name), name)
        if self.completed_at is not None and self.started_at is not None and self.completed_at < self.started_at:
            raise WorkflowContractError("completed_at cannot precede started_at")
        if self.status in (WorkflowRunStatus.PAUSED, WorkflowRunStatus.RECOVERING) and not self.checkpoint_id:
            raise WorkflowContractError("paused/recovering runs require checkpoint_id")
        if self.status in (WorkflowRunStatus.WAITING_FOR_INPUT, WorkflowRunStatus.WAITING_FOR_RESOURCE, WorkflowRunStatus.WAITING_FOR_APPROVAL) and (not self.checkpoint_id or self.wait_request is None):
            raise WorkflowContractError("waiting runs require checkpoint_id and wait_request")
        if self.wait_request is not None and not isinstance(self.wait_request, WaitRequest):
            raise WorkflowContractError("wait_request must be WaitRequest")
        if self.status not in (WorkflowRunStatus.WAITING_FOR_INPUT, WorkflowRunStatus.WAITING_FOR_RESOURCE, WorkflowRunStatus.WAITING_FOR_APPROVAL, WorkflowRunStatus.PAUSED) and self.wait_request is not None:
            raise WorkflowContractError("non-waiting run cannot contain wait_request")
        if self.status is WorkflowRunStatus.FAILED and not self.error_code:
            raise WorkflowContractError("failed runs require error_code")
        if self.depth < 0 or (self.parent_run_id == self.run_id):
            raise WorkflowContractError("invalid workflow run hierarchy")
        sets = [set(self.completed_nodes), set(self.failed_nodes), set(self.waiting_nodes), set(self.skipped_nodes)]
        if any(sets[i] & sets[j] for i in range(len(sets)) for j in range(i + 1, len(sets))):
            raise WorkflowContractError("node state sets must be disjoint")

    def to_dict(self) -> dict[str, Any]:
        return {"run_id": self.run_id, "workflow_id": self.workflow_id, "workflow_version": self.workflow_version,
                "status": self.status.value, "completed_nodes": list(self.completed_nodes),
                "failed_nodes": list(self.failed_nodes), "waiting_nodes": list(self.waiting_nodes), "skipped_nodes": list(self.skipped_nodes),
                "inputs": _thaw(self.inputs), "outputs": _thaw(self.outputs), "checkpoint_id": self.checkpoint_id,
                "started_at": self.started_at.isoformat() if self.started_at else None,
                "updated_at": self.updated_at.isoformat() if self.updated_at else None,
                "completed_at": self.completed_at.isoformat() if self.completed_at else None,
                "error_code": self.error_code, "wait_request": self.wait_request.to_dict() if self.wait_request else None,
                "parent_run_id": self.parent_run_id, "root_run_id": self.root_run_id, "depth": self.depth}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> WorkflowRun:
        known = {"run_id", "workflow_id", "workflow_version", "status", "completed_nodes", "failed_nodes", "waiting_nodes", "skipped_nodes", "inputs", "outputs", "checkpoint_id", "started_at", "updated_at", "completed_at", "error_code", "wait_request", "parent_run_id", "root_run_id", "depth"}
        if not isinstance(data, Mapping) or set(data) - known:
            raise WorkflowSerializationError("unknown WorkflowRun fields")
        values = dict(data)
        for name in ("started_at", "updated_at", "completed_at"):
            if values.get(name) is not None:
                values[name] = datetime.fromisoformat(values[name])
        if values.get("wait_request") is not None and not isinstance(values["wait_request"], WaitRequest):
            values["wait_request"] = WaitRequest.from_dict(values["wait_request"])
        return cls(**values)


@dataclass(frozen=True, slots=True)
class WorkflowDependency:
    source_node_id: str
    target_node_id: str
    required: bool = True


@dataclass(frozen=True, slots=True)
class WorkflowNodeResult:
    node_id: str
    node_type: WorkflowNodeType | str
    status: WorkflowNodeStatus | str
    attempt: int = 1
    input: Mapping[str, Any] = field(default_factory=dict)
    output: Mapping[str, Any] | None = None
    error_code: str | None = None
    operation_result: Mapping[str, Any] | None = None
    subworkflow_result: Mapping[str, Any] | None = None
    reason_code: str | None = None
    wait_request: WaitRequest | None = None

    def __post_init__(self) -> None:
        if isinstance(self.attempt, bool) or self.attempt < 1:
            raise WorkflowContractError("attempt must be positive")
        object.__setattr__(self, "node_type", _enum(self.node_type, WorkflowNodeType, "node_type"))
        object.__setattr__(self, "status", _enum(self.status, WorkflowNodeStatus, "status"))
        object.__setattr__(self, "input", _freeze(self.input, "input"))
        if self.output is not None:
            object.__setattr__(self, "output", _freeze(self.output, "output"))
        if self.operation_result is not None:
            object.__setattr__(self, "operation_result", _freeze(self.operation_result, "operation_result"))
        if self.subworkflow_result is not None:
            object.__setattr__(self, "subworkflow_result", _freeze(self.subworkflow_result, "subworkflow_result"))
        if self.status is WorkflowNodeStatus.FAILED and not self.error_code:
            raise WorkflowContractError("failed node result requires error_code")
        if self.status is WorkflowNodeStatus.COMPLETED and (self.error_code or self.wait_request is not None):
            raise WorkflowContractError("completed node cannot contain error or wait_request")
        if self.status is WorkflowNodeStatus.WAITING and not isinstance(self.wait_request, WaitRequest):
            raise WorkflowContractError("waiting node requires WaitRequest")
        if self.status is WorkflowNodeStatus.SKIPPED and not self.reason_code:
            raise WorkflowContractError("skipped node requires reason_code")
        if self.wait_request is not None and not isinstance(self.wait_request, WaitRequest):
            raise WorkflowContractError("wait_request must be WaitRequest")
        if self.operation_result is not None and self.node_type is not WorkflowNodeType.EXECUTE_OPERATION:
            raise WorkflowContractError("operation_result is only valid for operation nodes")
        if self.subworkflow_result is not None and self.node_type is not WorkflowNodeType.INVOKE_SUBWORKFLOW:
            raise WorkflowContractError("subworkflow_result is only valid for subworkflow nodes")

    def to_dict(self) -> dict[str, Any]:
        return {"node_id": self.node_id, "node_type": self.node_type.value, "status": self.status.value, "attempt": self.attempt, "input": _thaw(self.input), "output": _thaw(self.output) if self.output is not None else None, "error_code": self.error_code, "operation_result": _thaw(self.operation_result) if self.operation_result is not None else None, "subworkflow_result": _thaw(self.subworkflow_result) if self.subworkflow_result is not None else None, "reason_code": self.reason_code, "wait_request": self.wait_request.to_dict() if self.wait_request else None}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> WorkflowNodeResult:
        known = set(cls.__dataclass_fields__)
        if not isinstance(data, Mapping) or set(data) - known:
            raise WorkflowSerializationError("unknown WorkflowNodeResult fields")
        values = dict(data)
        if values.get("wait_request") is not None:
            values["wait_request"] = WaitRequest.from_dict(values["wait_request"])
        return cls(**values)


@dataclass(frozen=True, slots=True)
class WorkflowResult:
    run: WorkflowRun
    node_results: Mapping[str, WorkflowNodeResult] = field(default_factory=dict)
    output: Mapping[str, Any] | None = None
    error_code: str | None = None
    events: tuple[WorkflowEvent, ...] = ()
    rollback_valid: bool | None = None
    wait_request: WaitRequest | None = None
    attempts: Mapping[str, int] = field(default_factory=dict)
    defined_node_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "node_results", MappingProxyType(dict(self.node_results)))
        object.__setattr__(self, "attempts", MappingProxyType(dict(self.attempts)))
        object.__setattr__(self, "defined_node_ids", tuple(self.defined_node_ids))
        if self.wait_request is not None and not isinstance(self.wait_request, WaitRequest):
            raise WorkflowContractError("wait_request must be WaitRequest")
        if set(self.node_results) != {result.node_id for result in self.node_results.values()}:
            raise WorkflowContractError("node_results keys must match node_id")
        if self.defined_node_ids and not set(self.node_results) <= set(self.defined_node_ids):
            raise WorkflowContractError("node result is outside workflow definition")
        if self.output is not None:
            object.__setattr__(self, "output", _freeze(self.output, "output"))
        if self.run.status is WorkflowRunStatus.COMPLETED and self.error_code is not None:
            raise WorkflowContractError("completed result cannot have an error")
        if self.run.status is WorkflowRunStatus.FAILED and not (self.error_code or self.run.error_code):
            raise WorkflowContractError("failed result requires an error")
        if self.run.status is WorkflowRunStatus.COMPLETED and self.run.completed_at is None:
            raise WorkflowContractError("completed run requires completed_at")
        if self.run.status is WorkflowRunStatus.CANCELLED and self.run.waiting_nodes:
            raise WorkflowContractError("cancelled run cannot have waiting nodes")
        if self.run.status is WorkflowRunStatus.ROLLED_BACK and self.rollback_valid is not True:
            raise WorkflowContractError("rolled back result requires valid rollback")

    def to_dict(self) -> dict[str, Any]:
        return {"run": self.run.to_dict(), "node_results": {key: value.to_dict() for key, value in self.node_results.items()}, "output": _thaw(self.output) if self.output is not None else None, "error_code": self.error_code, "events": [event.to_dict() for event in self.events], "rollback_valid": self.rollback_valid, "wait_request": self.wait_request.to_dict() if self.wait_request else None, "attempts": dict(self.attempts), "defined_node_ids": list(self.defined_node_ids)}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> WorkflowResult:
        known = set(cls.__dataclass_fields__)
        if not isinstance(data, Mapping) or set(data) - known:
            raise WorkflowSerializationError("unknown WorkflowResult fields")
        values = dict(data)
        values["run"] = WorkflowRun.from_dict(values["run"])
        values["node_results"] = {key: WorkflowNodeResult.from_dict(value) for key, value in values.get("node_results", {}).items()}
        values["events"] = tuple(WorkflowEvent.from_dict(event) for event in values.get("events", ()))
        if values.get("wait_request") is not None:
            values["wait_request"] = WaitRequest.from_dict(values["wait_request"])
        return cls(**values)


@dataclass(frozen=True, slots=True)
class WorkflowEvent:
    event_id: str
    event_type: str
    workflow_id: str
    run_id: str
    occurred_at: datetime
    data: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _dt(self.occurred_at, "occurred_at")
        object.__setattr__(self, "data", _freeze(self.data, "data"))

    def to_dict(self) -> dict[str, Any]:
        return {"event_id": self.event_id, "event_type": self.event_type, "workflow_id": self.workflow_id, "run_id": self.run_id, "occurred_at": self.occurred_at.isoformat(), "data": _thaw(self.data)}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> WorkflowEvent:
        known = {"event_id", "event_type", "workflow_id", "run_id", "occurred_at", "data"}
        if not isinstance(data, Mapping) or set(data) - known:
            raise WorkflowSerializationError("unknown WorkflowEvent fields")
        values = dict(data)
        values["occurred_at"] = datetime.fromisoformat(values["occurred_at"])
        return cls(**values)


@dataclass(frozen=True, slots=True)
class WorkflowCheckpoint:
    checkpoint_id: str
    run_id: str
    completed_nodes: tuple[str, ...] = ()
    created_at: datetime | None = None

    def __post_init__(self) -> None:
        if self.created_at is not None:
            _dt(self.created_at, "created_at")
        object.__setattr__(self, "completed_nodes", tuple(self.completed_nodes))


@dataclass(frozen=True, slots=True)
class WaitRequest:
    kind: str
    reason: str
    node_id: str
    details: Mapping[str, Any] = field(default_factory=dict)
    approval_request: ApprovalRequest | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "details", _freeze(self.details, "details"))
        if self.approval_request is not None and not isinstance(self.approval_request, ApprovalRequest):
            raise WorkflowContractError("approval_request must be ApprovalRequest")

    def to_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "reason": self.reason, "node_id": self.node_id, "details": _thaw(self.details), "approval_request": self.approval_request.to_dict() if self.approval_request else None}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> WaitRequest:
        known = {"kind", "reason", "node_id", "details", "approval_request"}
        if not isinstance(data, Mapping) or set(data) - known:
            raise WorkflowSerializationError("unknown WaitRequest fields")
        values = dict(data)
        if values.get("approval_request") is not None:
            values["approval_request"] = ApprovalRequest.from_dict(values["approval_request"])
        return cls(**values)


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    maximum_attempts: int = 1
    retryable_errors: tuple[str, ...] = ()
    backoff_seconds: float = 0.0

    def __post_init__(self) -> None:
        if isinstance(self.maximum_attempts, bool) or self.maximum_attempts < 1:
            raise WorkflowContractError("maximum_attempts must be positive")
        if not math.isfinite(self.backoff_seconds) or self.backoff_seconds < 0:
            raise WorkflowContractError("backoff_seconds must be finite and non-negative")
        object.__setattr__(self, "retryable_errors", tuple(self.retryable_errors))


@dataclass(frozen=True, slots=True)
class ApprovalDecision:
    actor_id: str
    approved: bool
    decided_at: datetime | None = None

    def __post_init__(self) -> None:
        if not self.actor_id or not isinstance(self.approved, bool):
            raise WorkflowContractError("approval decision is invalid")
        if self.decided_at is not None:
            _dt(self.decided_at, "decided_at")


@dataclass(frozen=True, slots=True)
class ApprovalRequest:
    approval_id: str
    workflow_id: str
    workflow_version: str
    run_id: str
    node_id: str
    inputs: Mapping[str, Any]
    status: ApprovalStatus = ApprovalStatus.PENDING
    decision: ApprovalDecision | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "inputs", _freeze(self.inputs, "inputs"))
        object.__setattr__(self, "status", _enum(self.status, ApprovalStatus, "status"))
        if self.status is ApprovalStatus.PENDING and self.decision is not None:
            raise WorkflowContractError("pending approval cannot have a decision")

    @property
    def fingerprint(self) -> tuple[str, str, str, str, Any]:
        return (self.workflow_id, self.workflow_version, self.run_id, self.node_id, self.inputs)

    def decide(self, decision: ApprovalDecision) -> ApprovalRequest:
        if self.status is not ApprovalStatus.PENDING:
            raise WorkflowStateError("approval is already resolved")
        return ApprovalRequest(self.approval_id, self.workflow_id, self.workflow_version, self.run_id, self.node_id, self.inputs, ApprovalStatus.APPROVED if decision.approved else ApprovalStatus.DENIED, decision)

    def expire(self) -> ApprovalRequest:
        if self.status is not ApprovalStatus.PENDING:
            raise WorkflowStateError("approval is already resolved")
        return ApprovalRequest(self.approval_id, self.workflow_id, self.workflow_version, self.run_id, self.node_id, self.inputs, ApprovalStatus.EXPIRED)

    def assert_matches(self, *, run_id: str, inputs: Mapping[str, Any], workflow_id: str | None = None, workflow_version: str | None = None, node_id: str | None = None) -> None:
        if (run_id, _freeze(inputs, "inputs")) != (self.run_id, self.inputs) or (workflow_id is not None and workflow_id != self.workflow_id) or (workflow_version is not None and workflow_version != self.workflow_version) or (node_id is not None and node_id != self.node_id):
            raise WorkflowStateError("approval fingerprint does not match execution target")

    def to_dict(self) -> dict[str, Any]:
        return {"approval_id": self.approval_id, "workflow_id": self.workflow_id, "workflow_version": self.workflow_version, "run_id": self.run_id, "node_id": self.node_id, "inputs": _thaw(self.inputs), "status": self.status.value, "decision": {"actor_id": self.decision.actor_id, "approved": self.decision.approved, "decided_at": self.decision.decided_at.isoformat() if self.decision and self.decision.decided_at else None} if self.decision else None}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> ApprovalRequest:
        known = {"approval_id", "workflow_id", "workflow_version", "run_id", "node_id", "inputs", "status", "decision"}
        if not isinstance(data, Mapping) or set(data) - known:
            raise WorkflowSerializationError("unknown ApprovalRequest fields")
        values = dict(data)
        if values.get("decision") is not None:
            decision = dict(values["decision"])
            if decision.get("decided_at") is not None:
                decision["decided_at"] = datetime.fromisoformat(decision["decided_at"])
            values["decision"] = ApprovalDecision(**decision)
        return cls(**values)
