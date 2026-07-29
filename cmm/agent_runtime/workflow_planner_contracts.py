"""Phase 9.7 – Workflow Planner Adapter Contracts.

Typed contracts for requesting, constructing, validating, and versioning autonomous workflow plans.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from cmm.agent_runtime.contracts import AgentRun
from cmm.agent_runtime.enums import (
    AgentPlanningDecision,
    AgentPlanningStatus,
    WorkflowPlanChangeReason,
    WorkflowPlanNodeKind,
    WorkflowPlanRisk,
    WorkflowPlanStatus,
    WorkflowPlanValidationStatus,
)
from cmm.agent_runtime.errors import InvalidAgentPlanningContractError
from cmm.agent_runtime.goal_contracts import Goal
from cmm.agent_runtime.model_requirements_contracts import (
    model_requirements_from_dict,
    model_requirements_to_dict,
)
from cmm.agent_runtime.observation_contracts import ObservationSnapshot
from kernel.llm.model_selection import ModelRequirements


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def generate_planning_request_id() -> str:
    return f"agent-plan-req-{uuid.uuid4().hex[:12]}"


def generate_planning_context_id() -> str:
    return f"agent-plan-ctx-{uuid.uuid4().hex[:12]}"


def generate_workflow_plan_id() -> str:
    return f"workflow-plan-{uuid.uuid4().hex[:12]}"


def generate_workflow_id() -> str:
    return f"workflow-{uuid.uuid4().hex[:12]}"


def generate_workflow_task_id() -> str:
    return f"wf-task-{uuid.uuid4().hex[:12]}"


def generate_workflow_dependency_id() -> str:
    return f"wf-dep-{uuid.uuid4().hex[:12]}"


def generate_workflow_operation_id() -> str:
    return f"wf-op-{uuid.uuid4().hex[:12]}"


def generate_workflow_validation_node_id() -> str:
    return f"wf-val-{uuid.uuid4().hex[:12]}"


def generate_workflow_approval_node_id() -> str:
    return f"wf-appr-{uuid.uuid4().hex[:12]}"


def generate_workflow_checkpoint_id() -> str:
    return f"wf-chk-{uuid.uuid4().hex[:12]}"


@dataclass(frozen=True)
class AgentPlanningRequest:
    """Input request sent to the Workflow Planner Adapter."""

    id: str
    goal_id: str
    agent_run_id: str
    objective: str
    success_criteria: list[dict[str, Any]] = field(default_factory=list)
    constraints: list[dict[str, Any]] = field(default_factory=list)
    requirements: list[str] = field(default_factory=list)
    relevant_knowledge_ids: list[str] = field(default_factory=list)
    resource_ids: list[str] = field(default_factory=list)
    observation_snapshot_id: str | None = None
    reasoning_result_id: str | None = None
    cognitive_result_id: str | None = None
    information_acquisition_result_ids: list[str] = field(default_factory=list)
    allowed_operations: list[str] = field(default_factory=list)
    prohibited_operations: list[str] = field(default_factory=list)
    required_validations: list[str] = field(default_factory=list)
    required_approvals: list[str] = field(default_factory=list)
    validation_policy: str = "default"
    recovery_policy: str = "default"
    rollback_policy: str = "default"
    budget: dict[str, Any] = field(default_factory=dict)
    timeout_seconds: float | None = None
    permissions: list[str] = field(default_factory=list)
    autonomy_level: int = 1
    actor_id: str = "agent-runtime"
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=_utc_now_iso)

    def __post_init__(self) -> None:
        if not self.id or not isinstance(self.id, str):
            raise InvalidAgentPlanningContractError(
                "AgentPlanningRequest 'id' must be non-empty."
            )
        if not self.goal_id or not isinstance(self.goal_id, str):
            raise InvalidAgentPlanningContractError(
                "AgentPlanningRequest 'goal_id' must be non-empty."
            )
        if not self.agent_run_id or not isinstance(self.agent_run_id, str):
            raise InvalidAgentPlanningContractError(
                "AgentPlanningRequest 'agent_run_id' must be non-empty."
            )
        if self.timeout_seconds is not None and self.timeout_seconds <= 0:
            raise InvalidAgentPlanningContractError(
                "AgentPlanningRequest 'timeout_seconds' must be positive."
            )
        if self.autonomy_level < 0:
            raise InvalidAgentPlanningContractError(
                "AgentPlanningRequest 'autonomy_level' cannot be negative."
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "goal_id": self.goal_id,
            "agent_run_id": self.agent_run_id,
            "objective": self.objective,
            "success_criteria": list(self.success_criteria),
            "constraints": list(self.constraints),
            "requirements": list(self.requirements),
            "relevant_knowledge_ids": list(self.relevant_knowledge_ids),
            "resource_ids": list(self.resource_ids),
            "observation_snapshot_id": self.observation_snapshot_id,
            "reasoning_result_id": self.reasoning_result_id,
            "cognitive_result_id": self.cognitive_result_id,
            "information_acquisition_result_ids": list(
                self.information_acquisition_result_ids
            ),
            "allowed_operations": list(self.allowed_operations),
            "prohibited_operations": list(self.prohibited_operations),
            "required_validations": list(self.required_validations),
            "required_approvals": list(self.required_approvals),
            "validation_policy": self.validation_policy,
            "recovery_policy": self.recovery_policy,
            "rollback_policy": self.rollback_policy,
            "budget": dict(self.budget),
            "timeout_seconds": self.timeout_seconds,
            "permissions": list(self.permissions),
            "autonomy_level": self.autonomy_level,
            "actor_id": self.actor_id,
            "metadata": dict(self.metadata),
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentPlanningRequest:
        return cls(
            id=data["id"],
            goal_id=data["goal_id"],
            agent_run_id=data["agent_run_id"],
            objective=data.get("objective", ""),
            success_criteria=list(data.get("success_criteria", [])),
            constraints=list(data.get("constraints", [])),
            requirements=list(data.get("requirements", [])),
            relevant_knowledge_ids=list(data.get("relevant_knowledge_ids", [])),
            resource_ids=list(data.get("resource_ids", [])),
            observation_snapshot_id=data.get("observation_snapshot_id"),
            reasoning_result_id=data.get("reasoning_result_id"),
            cognitive_result_id=data.get("cognitive_result_id"),
            information_acquisition_result_ids=list(
                data.get("information_acquisition_result_ids", [])
            ),
            allowed_operations=list(data.get("allowed_operations", [])),
            prohibited_operations=list(data.get("prohibited_operations", [])),
            required_validations=list(data.get("required_validations", [])),
            required_approvals=list(data.get("required_approvals", [])),
            validation_policy=data.get("validation_policy", "default"),
            recovery_policy=data.get("recovery_policy", "default"),
            rollback_policy=data.get("rollback_policy", "default"),
            budget=dict(data.get("budget", {})),
            timeout_seconds=data.get("timeout_seconds"),
            permissions=list(data.get("permissions", [])),
            autonomy_level=data.get("autonomy_level", 1),
            actor_id=data.get("actor_id", "agent-runtime"),
            metadata=dict(data.get("metadata", {})),
            created_at=data.get("created_at") or _utc_now_iso(),
        )


@dataclass(frozen=True)
class AgentPlanningContext:
    """Immutable snapshot preserving exact context delivered to the Planner."""

    id: str
    request_id: str
    goal: Goal | None = None
    agent_run: AgentRun | None = None
    objective: str = ""
    success_criteria: list[dict[str, Any]] = field(default_factory=list)
    constraints: list[dict[str, Any]] = field(default_factory=list)
    requirements: list[str] = field(default_factory=list)
    observation_snapshot: ObservationSnapshot | None = None
    relevant_facts: list[str] = field(default_factory=list)
    cognitive_recommendations: list[str] = field(default_factory=list)
    accepted_gaps: list[str] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)
    resources: list[str] = field(default_factory=list)
    knowledge_ids: list[str] = field(default_factory=list)
    allowed_operations: list[str] = field(default_factory=list)
    prohibited_operations: list[str] = field(default_factory=list)
    permissions: list[str] = field(default_factory=list)
    nominal_policies: dict[str, Any] = field(default_factory=dict)
    budget_estimate: dict[str, Any] = field(default_factory=dict)
    timeout_seconds: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=_utc_now_iso)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "request_id": self.request_id,
            "goal": self.goal.to_dict()
            if self.goal and hasattr(self.goal, "to_dict")
            else None,
            "agent_run": self.agent_run.to_dict()
            if self.agent_run and hasattr(self.agent_run, "to_dict")
            else None,
            "objective": self.objective,
            "success_criteria": list(self.success_criteria),
            "constraints": list(self.constraints),
            "requirements": list(self.requirements),
            "observation_snapshot": (
                self.observation_snapshot.to_dict()
                if self.observation_snapshot
                and hasattr(self.observation_snapshot, "to_dict")
                else None
            ),
            "relevant_facts": list(self.relevant_facts),
            "cognitive_recommendations": list(self.cognitive_recommendations),
            "accepted_gaps": list(self.accepted_gaps),
            "assumptions": list(self.assumptions),
            "resources": list(self.resources),
            "knowledge_ids": list(self.knowledge_ids),
            "allowed_operations": list(self.allowed_operations),
            "prohibited_operations": list(self.prohibited_operations),
            "permissions": list(self.permissions),
            "nominal_policies": dict(self.nominal_policies),
            "budget_estimate": dict(self.budget_estimate),
            "timeout_seconds": self.timeout_seconds,
            "metadata": dict(self.metadata),
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentPlanningContext:
        goal_val = Goal.from_dict(data["goal"]) if data.get("goal") else None
        agent_run_val = (
            AgentRun.from_dict(data["agent_run"]) if data.get("agent_run") else None
        )
        obs_val = (
            ObservationSnapshot.from_dict(data["observation_snapshot"])
            if data.get("observation_snapshot")
            else None
        )
        return cls(
            id=data["id"],
            request_id=data["request_id"],
            goal=goal_val,
            agent_run=agent_run_val,
            objective=data.get("objective", ""),
            success_criteria=list(data.get("success_criteria", [])),
            constraints=list(data.get("constraints", [])),
            requirements=list(data.get("requirements", [])),
            observation_snapshot=obs_val,
            relevant_facts=list(data.get("relevant_facts", [])),
            cognitive_recommendations=list(data.get("cognitive_recommendations", [])),
            accepted_gaps=list(data.get("accepted_gaps", [])),
            assumptions=list(data.get("assumptions", [])),
            resources=list(data.get("resources", [])),
            knowledge_ids=list(data.get("knowledge_ids", [])),
            allowed_operations=list(data.get("allowed_operations", [])),
            prohibited_operations=list(data.get("prohibited_operations", [])),
            permissions=list(data.get("permissions", [])),
            nominal_policies=dict(data.get("nominal_policies", {})),
            budget_estimate=dict(data.get("budget_estimate", {})),
            timeout_seconds=data.get("timeout_seconds"),
            metadata=dict(data.get("metadata", {})),
            created_at=data.get("created_at") or _utc_now_iso(),
        )


@dataclass(frozen=True)
class AgentWorkflowTask:
    """Individual executable or logical task node in an AgentWorkflowPlan."""

    id: str
    workflow_id: str
    name: str
    description: str
    kind: WorkflowPlanNodeKind = WorkflowPlanNodeKind.TASK
    status: str = "pending"
    dependency_ids: list[str] = field(default_factory=list)
    operation_ids: list[str] = field(default_factory=list)
    validation_node_ids: list[str] = field(default_factory=list)
    approval_node_ids: list[str] = field(default_factory=list)
    checkpoint_ids: list[str] = field(default_factory=list)
    inputs: dict[str, Any] = field(default_factory=dict)
    expected_outputs: dict[str, Any] = field(default_factory=dict)
    success_criteria: list[str] = field(default_factory=list)
    timeout_seconds: float | None = None
    optional: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.id:
            raise InvalidAgentPlanningContractError(
                "AgentWorkflowTask 'id' must be non-empty."
            )
        if not self.workflow_id:
            raise InvalidAgentPlanningContractError(
                "AgentWorkflowTask 'workflow_id' must be non-empty."
            )
        if self.timeout_seconds is not None and self.timeout_seconds <= 0:
            raise InvalidAgentPlanningContractError(
                "AgentWorkflowTask 'timeout_seconds' must be positive."
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "workflow_id": self.workflow_id,
            "name": self.name,
            "description": self.description,
            "kind": self.kind.value
            if isinstance(self.kind, WorkflowPlanNodeKind)
            else str(self.kind),
            "status": self.status,
            "dependency_ids": list(self.dependency_ids),
            "operation_ids": list(self.operation_ids),
            "validation_node_ids": list(self.validation_node_ids),
            "approval_node_ids": list(self.approval_node_ids),
            "checkpoint_ids": list(self.checkpoint_ids),
            "inputs": dict(self.inputs),
            "expected_outputs": dict(self.expected_outputs),
            "success_criteria": list(self.success_criteria),
            "timeout_seconds": self.timeout_seconds,
            "optional": self.optional,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentWorkflowTask:
        kind_raw = data.get("kind", WorkflowPlanNodeKind.TASK)
        kind_val = (
            WorkflowPlanNodeKind(kind_raw) if isinstance(kind_raw, str) else kind_raw
        )
        return cls(
            id=data["id"],
            workflow_id=data["workflow_id"],
            name=data.get("name", ""),
            description=data.get("description", ""),
            kind=kind_val,
            status=data.get("status", "pending"),
            dependency_ids=list(data.get("dependency_ids", [])),
            operation_ids=list(data.get("operation_ids", [])),
            validation_node_ids=list(data.get("validation_node_ids", [])),
            approval_node_ids=list(data.get("approval_node_ids", [])),
            checkpoint_ids=list(data.get("checkpoint_ids", [])),
            inputs=dict(data.get("inputs", {})),
            expected_outputs=dict(data.get("expected_outputs", {})),
            success_criteria=list(data.get("success_criteria", [])),
            timeout_seconds=data.get("timeout_seconds"),
            optional=bool(data.get("optional", False)),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass(frozen=True)
class AgentWorkflowDependency:
    """Dependency relationship edge between workflow tasks in the DAG."""

    id: str
    source_task_id: str
    target_task_id: str
    dependency_type: str = "requires_completion"
    blocking: bool = True
    condition: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.id:
            raise InvalidAgentPlanningContractError(
                "AgentWorkflowDependency 'id' must be non-empty."
            )
        if not self.source_task_id:
            raise InvalidAgentPlanningContractError(
                "AgentWorkflowDependency 'source_task_id' must be non-empty."
            )
        if not self.target_task_id:
            raise InvalidAgentPlanningContractError(
                "AgentWorkflowDependency 'target_task_id' must be non-empty."
            )
        if self.source_task_id == self.target_task_id:
            raise InvalidAgentPlanningContractError("Self-dependency is not allowed.")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "source_task_id": self.source_task_id,
            "target_task_id": self.target_task_id,
            "dependency_type": self.dependency_type,
            "blocking": self.blocking,
            "condition": self.condition,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentWorkflowDependency:
        return cls(
            id=data["id"],
            source_task_id=data["source_task_id"],
            target_task_id=data["target_task_id"],
            dependency_type=data.get("dependency_type", "requires_completion"),
            blocking=bool(data.get("blocking", True)),
            condition=data.get("condition"),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass(frozen=True)
class AgentWorkflowOperation:
    """Typed operation specification attached to a workflow task."""

    id: str
    task_id: str
    operation_name: str
    parameters: dict[str, Any] = field(default_factory=dict)
    expected_effects: list[str] = field(default_factory=list)
    reversible: bool = False
    rollback_operation: str | None = None
    required_permissions: list[str] = field(default_factory=list)
    required_validations: list[str] = field(default_factory=list)
    requires_approval: bool = False
    risk: WorkflowPlanRisk = WorkflowPlanRisk.NONE
    idempotency_key: str | None = None
    timeout_seconds: float | None = None
    model_requirements: ModelRequirements | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.id:
            raise InvalidAgentPlanningContractError(
                "AgentWorkflowOperation 'id' must be non-empty."
            )
        if not self.task_id:
            raise InvalidAgentPlanningContractError(
                "AgentWorkflowOperation 'task_id' must be non-empty."
            )
        if not self.operation_name:
            raise InvalidAgentPlanningContractError(
                "AgentWorkflowOperation 'operation_name' must be non-empty."
            )
        if self.timeout_seconds is not None and self.timeout_seconds <= 0:
            raise InvalidAgentPlanningContractError(
                "AgentWorkflowOperation 'timeout_seconds' must be positive."
            )
        if (
            self.model_requirements is not None
            and not isinstance(self.model_requirements, ModelRequirements)
        ):
            raise InvalidAgentPlanningContractError(
                "AgentWorkflowOperation 'model_requirements' must be "
                "a ModelRequirements instance or None."
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "task_id": self.task_id,
            "operation_name": self.operation_name,
            "parameters": dict(self.parameters),
            "expected_effects": list(self.expected_effects),
            "reversible": self.reversible,
            "rollback_operation": self.rollback_operation,
            "required_permissions": list(self.required_permissions),
            "required_validations": list(self.required_validations),
            "requires_approval": self.requires_approval,
            "risk": self.risk.value
            if isinstance(self.risk, WorkflowPlanRisk)
            else str(self.risk),
            "idempotency_key": self.idempotency_key,
            "timeout_seconds": self.timeout_seconds,
            "model_requirements": (
                model_requirements_to_dict(self.model_requirements)
                if self.model_requirements is not None
                else None
            ),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentWorkflowOperation:
        risk_raw = data.get("risk", WorkflowPlanRisk.NONE)
        risk_val = WorkflowPlanRisk(risk_raw) if isinstance(risk_raw, str) else risk_raw
        return cls(
            id=data["id"],
            task_id=data["task_id"],
            operation_name=data["operation_name"],
            parameters=dict(data.get("parameters", {})),
            expected_effects=list(data.get("expected_effects", [])),
            reversible=bool(data.get("reversible", False)),
            rollback_operation=data.get("rollback_operation"),
            required_permissions=list(data.get("required_permissions", [])),
            required_validations=list(data.get("required_validations", [])),
            requires_approval=bool(data.get("requires_approval", False)),
            risk=risk_val,
            idempotency_key=data.get("idempotency_key"),
            timeout_seconds=data.get("timeout_seconds"),
            model_requirements=(
                model_requirements_from_dict(data["model_requirements"])
                if data.get("model_requirements") is not None
                else None
            ),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass(frozen=True)
class AgentWorkflowValidationNode:
    """Explicit validation checkpoint embedded in a workflow plan."""

    id: str
    workflow_id: str
    policy: str
    timing: str = "post"
    required: bool = True
    blocking: bool = True
    scope: str = "task"
    related_id: str | None = None
    selected_steps: list[str] = field(default_factory=list)
    expected_result: str = "passed"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "workflow_id": self.workflow_id,
            "policy": self.policy,
            "timing": self.timing,
            "required": self.required,
            "blocking": self.blocking,
            "scope": self.scope,
            "related_id": self.related_id,
            "selected_steps": list(self.selected_steps),
            "expected_result": self.expected_result,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentWorkflowValidationNode:
        return cls(
            id=data["id"],
            workflow_id=data["workflow_id"],
            policy=data.get("policy", "default"),
            timing=data.get("timing", "post"),
            required=bool(data.get("required", True)),
            blocking=bool(data.get("blocking", True)),
            scope=data.get("scope", "task"),
            related_id=data.get("related_id"),
            selected_steps=list(data.get("selected_steps", [])),
            expected_result=data.get("expected_result", "passed"),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass(frozen=True)
class AgentWorkflowApprovalNode:
    """Human or policy approval node specification embedded in a plan."""

    id: str
    workflow_id: str
    reason: str
    risk: WorkflowPlanRisk = WorkflowPlanRisk.MEDIUM
    related_id: str | None = None
    expected_effects: list[str] = field(default_factory=list)
    possible_side_effects: list[str] = field(default_factory=list)
    rollback_available: bool = False
    required_approvers: list[str] = field(default_factory=list)
    pending: bool = True
    conditions: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "workflow_id": self.workflow_id,
            "reason": self.reason,
            "risk": self.risk.value
            if isinstance(self.risk, WorkflowPlanRisk)
            else str(self.risk),
            "related_id": self.related_id,
            "expected_effects": list(self.expected_effects),
            "possible_side_effects": list(self.possible_side_effects),
            "rollback_available": self.rollback_available,
            "required_approvers": list(self.required_approvers),
            "pending": self.pending,
            "conditions": list(self.conditions),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentWorkflowApprovalNode:
        risk_raw = data.get("risk", WorkflowPlanRisk.MEDIUM)
        risk_val = WorkflowPlanRisk(risk_raw) if isinstance(risk_raw, str) else risk_raw
        return cls(
            id=data["id"],
            workflow_id=data["workflow_id"],
            reason=data.get("reason", ""),
            risk=risk_val,
            related_id=data.get("related_id"),
            expected_effects=list(data.get("expected_effects", [])),
            possible_side_effects=list(data.get("possible_side_effects", [])),
            rollback_available=bool(data.get("rollback_available", False)),
            required_approvers=list(data.get("required_approvers", [])),
            pending=bool(data.get("pending", True)),
            conditions=list(data.get("conditions", [])),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass(frozen=True)
class AgentWorkflowCheckpoint:
    """State checkpoint specification embedded in a plan."""

    id: str
    workflow_id: str
    name: str
    position: int
    affected_resources: list[str] = field(default_factory=list)
    expected_versions: dict[str, str] = field(default_factory=dict)
    reversible_operations: list[str] = field(default_factory=list)
    reason: str = ""
    required: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "workflow_id": self.workflow_id,
            "name": self.name,
            "position": self.position,
            "affected_resources": list(self.affected_resources),
            "expected_versions": dict(self.expected_versions),
            "reversible_operations": list(self.reversible_operations),
            "reason": self.reason,
            "required": self.required,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentWorkflowCheckpoint:
        return cls(
            id=data["id"],
            workflow_id=data["workflow_id"],
            name=data.get("name", ""),
            position=int(data.get("position", 0)),
            affected_resources=list(data.get("affected_resources", [])),
            expected_versions=dict(data.get("expected_versions", {})),
            reversible_operations=list(data.get("reversible_operations", [])),
            reason=data.get("reason", ""),
            required=bool(data.get("required", True)),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass(frozen=True)
class AgentWorkflowRollbackStrategy:
    """Rollback strategy specification declared by a plan."""

    id: str
    available: bool = True
    kind: str = "step_by_step"
    trigger_conditions: list[str] = field(default_factory=list)
    scope: str = "workflow"
    operation_mappings: dict[str, str] = field(default_factory=dict)
    checkpoint_ids: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    expected_effects: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "available": self.available,
            "kind": self.kind,
            "trigger_conditions": list(self.trigger_conditions),
            "scope": self.scope,
            "operation_mappings": dict(self.operation_mappings),
            "checkpoint_ids": list(self.checkpoint_ids),
            "limitations": list(self.limitations),
            "expected_effects": list(self.expected_effects),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentWorkflowRollbackStrategy:
        return cls(
            id=data["id"],
            available=bool(data.get("available", True)),
            kind=data.get("kind", "step_by_step"),
            trigger_conditions=list(data.get("trigger_conditions", [])),
            scope=data.get("scope", "workflow"),
            operation_mappings=dict(data.get("operation_mappings", {})),
            checkpoint_ids=list(data.get("checkpoint_ids", [])),
            limitations=list(data.get("limitations", [])),
            expected_effects=list(data.get("expected_effects", [])),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass(frozen=True)
class AgentWorkflowRecoveryStrategy:
    """Recovery strategy specification declared by a plan."""

    id: str
    actions: list[str] = field(default_factory=list)
    maximum_attempts: int = 3
    retryable_errors: list[str] = field(default_factory=list)
    fallback_operations: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "actions": list(self.actions),
            "maximum_attempts": self.maximum_attempts,
            "retryable_errors": list(self.retryable_errors),
            "fallback_operations": list(self.fallback_operations),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentWorkflowRecoveryStrategy:
        return cls(
            id=data["id"],
            actions=list(data.get("actions", [])),
            maximum_attempts=int(data.get("maximum_attempts", 3)),
            retryable_errors=list(data.get("retryable_errors", [])),
            fallback_operations=list(data.get("fallback_operations", [])),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass(frozen=True)
class AgentWorkflowBudgetEstimate:
    """Estimated resource budget for executing a plan."""

    estimated_tokens: int = 0
    estimated_cost: float = 0.0
    estimated_duration_seconds: float = 0.0
    estimated_operations: int = 0
    limits: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.estimated_tokens < 0:
            raise InvalidAgentPlanningContractError(
                "estimated_tokens cannot be negative."
            )
        if self.estimated_cost < 0:
            raise InvalidAgentPlanningContractError(
                "estimated_cost cannot be negative."
            )
        if self.estimated_duration_seconds < 0:
            raise InvalidAgentPlanningContractError(
                "estimated_duration_seconds cannot be negative."
            )
        if self.estimated_operations < 0:
            raise InvalidAgentPlanningContractError(
                "estimated_operations cannot be negative."
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "estimated_tokens": self.estimated_tokens,
            "estimated_cost": self.estimated_cost,
            "estimated_duration_seconds": self.estimated_duration_seconds,
            "estimated_operations": self.estimated_operations,
            "limits": dict(self.limits),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentWorkflowBudgetEstimate:
        return cls(
            estimated_tokens=int(data.get("estimated_tokens", 0)),
            estimated_cost=float(data.get("estimated_cost", 0.0)),
            estimated_duration_seconds=float(
                data.get("estimated_duration_seconds", 0.0)
            ),
            estimated_operations=int(data.get("estimated_operations", 0)),
            limits=dict(data.get("limits", {})),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass(frozen=True)
class AgentWorkflowRisk:
    """Identified operational or architectural risk in a plan."""

    id: str
    name: str
    level: WorkflowPlanRisk = WorkflowPlanRisk.LOW
    description: str = ""
    mitigation: str = ""
    impact: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "level": self.level.value
            if isinstance(self.level, WorkflowPlanRisk)
            else str(self.level),
            "description": self.description,
            "mitigation": self.mitigation,
            "impact": self.impact,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentWorkflowRisk:
        level_raw = data.get("level", WorkflowPlanRisk.LOW)
        level_val = (
            WorkflowPlanRisk(level_raw) if isinstance(level_raw, str) else level_raw
        )
        return cls(
            id=data["id"],
            name=data.get("name", ""),
            level=level_val,
            description=data.get("description", ""),
            mitigation=data.get("mitigation", ""),
            impact=data.get("impact", ""),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass(frozen=True)
class AgentWorkflowAssumption:
    """Explicit planning assumption underlying a plan."""

    id: str
    statement: str
    validated: bool = False
    impact_if_invalid: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "statement": self.statement,
            "validated": self.validated,
            "impact_if_invalid": self.impact_if_invalid,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentWorkflowAssumption:
        return cls(
            id=data["id"],
            statement=data.get("statement", ""),
            validated=bool(data.get("validated", False)),
            impact_if_invalid=data.get("impact_if_invalid", ""),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass(frozen=True)
class AgentPlanningWarning:
    """Warning item produced during planning or structural validation."""

    code: str
    message: str
    node_id: str | None = None
    severity: str = "warning"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "node_id": self.node_id,
            "severity": self.severity,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentPlanningWarning:
        return cls(
            code=data["code"],
            message=data.get("message", ""),
            node_id=data.get("node_id"),
            severity=data.get("severity", "warning"),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass(frozen=True)
class AgentPlanningError:
    """Error item produced during plan structural validation."""

    code: str
    message: str
    node_id: str | None = None
    severity: str = "error"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "node_id": self.node_id,
            "severity": self.severity,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentPlanningError:
        return cls(
            code=data["code"],
            message=data.get("message", ""),
            node_id=data.get("node_id"),
            severity=data.get("severity", "error"),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass(frozen=True)
class AgentWorkflowPlanValidation:
    """Validation report resulting from structural validation of an AgentWorkflowPlan."""

    status: WorkflowPlanValidationStatus = WorkflowPlanValidationStatus.PENDING
    is_valid: bool = False
    blocking_errors: list[str] = field(default_factory=list)
    warnings: list[AgentPlanningWarning] = field(default_factory=list)
    findings: list[dict[str, Any]] = field(default_factory=list)
    validated_at: str = field(default_factory=_utc_now_iso)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value
            if isinstance(self.status, WorkflowPlanValidationStatus)
            else str(self.status),
            "is_valid": self.is_valid,
            "blocking_errors": list(self.blocking_errors),
            "warnings": [warning.to_dict() for warning in self.warnings],
            "findings": [dict(f) for f in self.findings],
            "validated_at": self.validated_at,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentWorkflowPlanValidation:
        status_raw = data.get("status", WorkflowPlanValidationStatus.PENDING)
        status_val = (
            WorkflowPlanValidationStatus(status_raw)
            if isinstance(status_raw, str)
            else status_raw
        )
        warnings_raw = data.get("warnings", [])
        warnings_list = [
            AgentPlanningWarning.from_dict(w) if isinstance(w, dict) else w
            for w in warnings_raw
        ]
        return cls(
            status=status_val,
            is_valid=bool(data.get("is_valid", False)),
            blocking_errors=list(data.get("blocking_errors", [])),
            warnings=warnings_list,
            findings=[dict(f) for f in data.get("findings", [])],
            validated_at=data.get("validated_at") or _utc_now_iso(),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass(frozen=True)
class AgentWorkflowPlan:
    """Auditable, structured workflow plan contract produced by the Workflow Planner Adapter."""

    id: str
    goal_id: str
    agent_run_id: str
    workflow_id: str
    planner_plan_id: str | None = None
    version: int = 1
    previous_version_id: str | None = None
    status: WorkflowPlanStatus = WorkflowPlanStatus.DRAFT
    objective: str = ""
    scope: list[str] = field(default_factory=list)
    tasks: list[AgentWorkflowTask] = field(default_factory=list)
    dependencies: list[AgentWorkflowDependency] = field(default_factory=list)
    operations: list[AgentWorkflowOperation] = field(default_factory=list)
    validation_nodes: list[AgentWorkflowValidationNode] = field(default_factory=list)
    approval_nodes: list[AgentWorkflowApprovalNode] = field(default_factory=list)
    checkpoints: list[AgentWorkflowCheckpoint] = field(default_factory=list)
    rollback_strategy: AgentWorkflowRollbackStrategy | None = None
    recovery_strategy: AgentWorkflowRecoveryStrategy | None = None
    completion_criteria: list[str] = field(default_factory=list)
    pause_conditions: list[str] = field(default_factory=list)
    cancellation_conditions: list[str] = field(default_factory=list)
    assumptions: list[AgentWorkflowAssumption] = field(default_factory=list)
    risks: list[AgentWorkflowRisk] = field(default_factory=list)
    expected_effects: list[str] = field(default_factory=list)
    estimated_budget: AgentWorkflowBudgetEstimate | None = None
    timeout_seconds: float | None = None
    model_requirements: ModelRequirements | None = None
    confidence: float = 1.0
    validation: AgentWorkflowPlanValidation | None = None
    created_at: str = field(default_factory=_utc_now_iso)
    updated_at: str = field(default_factory=_utc_now_iso)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.id:
            raise InvalidAgentPlanningContractError(
                "AgentWorkflowPlan 'id' must be non-empty."
            )
        if not self.goal_id:
            raise InvalidAgentPlanningContractError(
                "AgentWorkflowPlan 'goal_id' must be non-empty."
            )
        if not self.agent_run_id:
            raise InvalidAgentPlanningContractError(
                "AgentWorkflowPlan 'agent_run_id' must be non-empty."
            )
        if not self.workflow_id:
            raise InvalidAgentPlanningContractError(
                "AgentWorkflowPlan 'workflow_id' must be non-empty."
            )
        if self.version <= 0:
            raise InvalidAgentPlanningContractError(
                "AgentWorkflowPlan 'version' must be a positive integer."
            )
        if not (0.0 <= self.confidence <= 1.0):
            raise InvalidAgentPlanningContractError(
                "AgentWorkflowPlan 'confidence' must be between 0.0 and 1.0."
            )
        if self.timeout_seconds is not None and self.timeout_seconds <= 0:
            raise InvalidAgentPlanningContractError(
                "AgentWorkflowPlan 'timeout_seconds' must be positive."
            )
        if (
            self.model_requirements is not None
            and not isinstance(self.model_requirements, ModelRequirements)
        ):
            raise InvalidAgentPlanningContractError(
                "AgentWorkflowPlan 'model_requirements' must be "
                "a ModelRequirements instance or None."
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "goal_id": self.goal_id,
            "agent_run_id": self.agent_run_id,
            "workflow_id": self.workflow_id,
            "planner_plan_id": self.planner_plan_id,
            "version": self.version,
            "previous_version_id": self.previous_version_id,
            "status": self.status.value
            if isinstance(self.status, WorkflowPlanStatus)
            else str(self.status),
            "objective": self.objective,
            "scope": list(self.scope),
            "tasks": [t.to_dict() for t in self.tasks],
            "dependencies": [d.to_dict() for d in self.dependencies],
            "operations": [o.to_dict() for o in self.operations],
            "validation_nodes": [v.to_dict() for v in self.validation_nodes],
            "approval_nodes": [a.to_dict() for a in self.approval_nodes],
            "checkpoints": [c.to_dict() for c in self.checkpoints],
            "rollback_strategy": self.rollback_strategy.to_dict()
            if self.rollback_strategy
            else None,
            "recovery_strategy": self.recovery_strategy.to_dict()
            if self.recovery_strategy
            else None,
            "completion_criteria": list(self.completion_criteria),
            "pause_conditions": list(self.pause_conditions),
            "cancellation_conditions": list(self.cancellation_conditions),
            "assumptions": [a.to_dict() for a in self.assumptions],
            "risks": [r.to_dict() for r in self.risks],
            "expected_effects": list(self.expected_effects),
            "estimated_budget": self.estimated_budget.to_dict()
            if self.estimated_budget
            else None,
            "timeout_seconds": self.timeout_seconds,
            "model_requirements": (
                model_requirements_to_dict(self.model_requirements)
                if self.model_requirements is not None
                else None
            ),
            "confidence": self.confidence,
            "validation": self.validation.to_dict() if self.validation else None,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentWorkflowPlan:
        status_raw = data.get("status", WorkflowPlanStatus.DRAFT)
        status_val = (
            WorkflowPlanStatus(status_raw)
            if isinstance(status_raw, str)
            else status_raw
        )

        rollback_val = (
            AgentWorkflowRollbackStrategy.from_dict(data["rollback_strategy"])
            if data.get("rollback_strategy")
            else None
        )
        recovery_val = (
            AgentWorkflowRecoveryStrategy.from_dict(data["recovery_strategy"])
            if data.get("recovery_strategy")
            else None
        )
        budget_val = (
            AgentWorkflowBudgetEstimate.from_dict(data["estimated_budget"])
            if data.get("estimated_budget")
            else None
        )
        validation_val = (
            AgentWorkflowPlanValidation.from_dict(data["validation"])
            if data.get("validation")
            else None
        )

        return cls(
            id=data["id"],
            goal_id=data["goal_id"],
            agent_run_id=data["agent_run_id"],
            workflow_id=data["workflow_id"],
            planner_plan_id=data.get("planner_plan_id"),
            version=int(data.get("version", 1)),
            previous_version_id=data.get("previous_version_id"),
            status=status_val,
            objective=data.get("objective", ""),
            scope=list(data.get("scope", [])),
            tasks=[AgentWorkflowTask.from_dict(t) for t in data.get("tasks", [])],
            dependencies=[
                AgentWorkflowDependency.from_dict(d)
                for d in data.get("dependencies", [])
            ],
            operations=[
                AgentWorkflowOperation.from_dict(o) for o in data.get("operations", [])
            ],
            validation_nodes=[
                AgentWorkflowValidationNode.from_dict(v)
                for v in data.get("validation_nodes", [])
            ],
            approval_nodes=[
                AgentWorkflowApprovalNode.from_dict(a)
                for a in data.get("approval_nodes", [])
            ],
            checkpoints=[
                AgentWorkflowCheckpoint.from_dict(c)
                for c in data.get("checkpoints", [])
            ],
            rollback_strategy=rollback_val,
            recovery_strategy=recovery_val,
            completion_criteria=list(data.get("completion_criteria", [])),
            pause_conditions=list(data.get("pause_conditions", [])),
            cancellation_conditions=list(data.get("cancellation_conditions", [])),
            assumptions=[
                AgentWorkflowAssumption.from_dict(a)
                for a in data.get("assumptions", [])
            ],
            risks=[AgentWorkflowRisk.from_dict(r) for r in data.get("risks", [])],
            expected_effects=list(data.get("expected_effects", [])),
            estimated_budget=budget_val,
            timeout_seconds=data.get("timeout_seconds"),
            model_requirements=(
                model_requirements_from_dict(data["model_requirements"])
                if data.get("model_requirements") is not None
                else None
            ),
            confidence=float(data.get("confidence", 1.0)),
            validation=validation_val,
            created_at=data.get("created_at") or _utc_now_iso(),
            updated_at=data.get("updated_at") or _utc_now_iso(),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass(frozen=True)
class AgentWorkflowPlanVersion:
    """Version metadata tracking plan mutations and replanning events."""

    workflow_id: str
    plan_id: str
    version: int
    change_reason: WorkflowPlanChangeReason
    evidence: dict[str, Any] = field(default_factory=dict)
    superseded_plan_id: str | None = None
    created_at: str = field(default_factory=_utc_now_iso)

    def to_dict(self) -> dict[str, Any]:
        return {
            "workflow_id": self.workflow_id,
            "plan_id": self.plan_id,
            "version": self.version,
            "change_reason": (
                self.change_reason.value
                if isinstance(self.change_reason, WorkflowPlanChangeReason)
                else str(self.change_reason)
            ),
            "evidence": dict(self.evidence),
            "superseded_plan_id": self.superseded_plan_id,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentWorkflowPlanVersion:
        reason_raw = data.get("change_reason", WorkflowPlanChangeReason.MANUAL_REQUEST)
        reason_val = (
            WorkflowPlanChangeReason(reason_raw)
            if isinstance(reason_raw, str)
            else reason_raw
        )
        return cls(
            workflow_id=data["workflow_id"],
            plan_id=data["plan_id"],
            version=int(data.get("version", 1)),
            change_reason=reason_val,
            evidence=dict(data.get("evidence", {})),
            superseded_plan_id=data.get("superseded_plan_id"),
            created_at=data.get("created_at") or _utc_now_iso(),
        )


@dataclass(frozen=True)
class AgentReplanningRequest:
    """Request contract to trigger replanning and create a new plan version."""

    id: str
    plan_id: str
    reason: WorkflowPlanChangeReason
    reason_details: str = ""
    new_information: dict[str, Any] = field(default_factory=dict)
    failed_operation_id: str | None = None
    failed_validation_id: str | None = None
    planning_request: AgentPlanningRequest | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=_utc_now_iso)

    def __post_init__(self) -> None:
        if not self.id:
            raise InvalidAgentPlanningContractError(
                "AgentReplanningRequest 'id' must be non-empty."
            )
        if not self.plan_id:
            raise InvalidAgentPlanningContractError(
                "AgentReplanningRequest 'plan_id' must be non-empty."
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "plan_id": self.plan_id,
            "reason": self.reason.value
            if isinstance(self.reason, WorkflowPlanChangeReason)
            else str(self.reason),
            "reason_details": self.reason_details,
            "new_information": dict(self.new_information),
            "failed_operation_id": self.failed_operation_id,
            "failed_validation_id": self.failed_validation_id,
            "planning_request": self.planning_request.to_dict()
            if self.planning_request
            else None,
            "metadata": dict(self.metadata),
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentReplanningRequest:
        reason_raw = data.get("reason", WorkflowPlanChangeReason.MANUAL_REQUEST)
        reason_val = (
            WorkflowPlanChangeReason(reason_raw)
            if isinstance(reason_raw, str)
            else reason_raw
        )
        plan_req = (
            AgentPlanningRequest.from_dict(data["planning_request"])
            if data.get("planning_request")
            else None
        )
        return cls(
            id=data["id"],
            plan_id=data["plan_id"],
            reason=reason_val,
            reason_details=data.get("reason_details", ""),
            new_information=dict(data.get("new_information", {})),
            failed_operation_id=data.get("failed_operation_id"),
            failed_validation_id=data.get("failed_validation_id"),
            planning_request=plan_req,
            metadata=dict(data.get("metadata", {})),
            created_at=data.get("created_at") or _utc_now_iso(),
        )


@dataclass(frozen=True)
class AgentReplanningResult:
    """Outcome result of a replanning execution."""

    id: str
    request_id: str
    status: AgentPlanningStatus
    decision: AgentPlanningDecision
    previous_plan_id: str
    new_plan: AgentWorkflowPlan | None = None
    version: int = 1
    change_reason: WorkflowPlanChangeReason = WorkflowPlanChangeReason.MANUAL_REQUEST
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=_utc_now_iso)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "request_id": self.request_id,
            "status": self.status.value
            if isinstance(self.status, AgentPlanningStatus)
            else str(self.status),
            "decision": (
                self.decision.value
                if isinstance(self.decision, AgentPlanningDecision)
                else str(self.decision)
            ),
            "previous_plan_id": self.previous_plan_id,
            "new_plan": self.new_plan.to_dict() if self.new_plan else None,
            "version": self.version,
            "change_reason": (
                self.change_reason.value
                if isinstance(self.change_reason, WorkflowPlanChangeReason)
                else str(self.change_reason)
            ),
            "metadata": dict(self.metadata),
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentReplanningResult:
        status_raw = data.get("status", AgentPlanningStatus.COMPLETED)
        status_val = (
            AgentPlanningStatus(status_raw)
            if isinstance(status_raw, str)
            else status_raw
        )
        dec_raw = data.get("decision", AgentPlanningDecision.REPLAN)
        dec_val = (
            AgentPlanningDecision(dec_raw) if isinstance(dec_raw, str) else dec_raw
        )
        reason_raw = data.get("change_reason", WorkflowPlanChangeReason.MANUAL_REQUEST)
        reason_val = (
            WorkflowPlanChangeReason(reason_raw)
            if isinstance(reason_raw, str)
            else reason_raw
        )

        return cls(
            id=data["id"],
            request_id=data["request_id"],
            status=status_val,
            decision=dec_val,
            previous_plan_id=data["previous_plan_id"],
            new_plan=AgentWorkflowPlan.from_dict(data["new_plan"])
            if data.get("new_plan")
            else None,
            version=int(data.get("version", 1)),
            change_reason=reason_val,
            metadata=dict(data.get("metadata", {})),
            created_at=data.get("created_at") or _utc_now_iso(),
        )
