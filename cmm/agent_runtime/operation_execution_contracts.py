"""Phase 9.13 – Operation Selection and Execution Contracts.

Defines immutable contracts for requests, descriptors, capabilities, gates, and results.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from types import MappingProxyType
from typing import Any

from cmm.agent_runtime.enums import (
    AgentOperationExecutionStatus,
    OperationEffectType,
    OperationEnvironment,
)
from cmm.agent_runtime.errors import InvalidAgentOperationContractError
from kernel.llm.model_selection import ModelRequirements


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_timezone(iso_string: str) -> None:
    dt = datetime.fromisoformat(iso_string)
    if dt.tzinfo is None:
        raise InvalidAgentOperationContractError(
            f"Timestamp '{iso_string}' must be timezone-aware."
        )


def _freeze_mapping(data: Mapping[str, Any]) -> MappingProxyType:
    normalized: dict[str, Any] = {}
    for k, v in data.items():
        if isinstance(v, dict):
            normalized[k] = _freeze_mapping(v)
        elif isinstance(v, list):
            normalized[k] = tuple(
                _freeze_mapping(x) if isinstance(x, dict) else x for x in v
            )
        else:
            normalized[k] = v
    return MappingProxyType(normalized)


@dataclass(frozen=True)
class AgentOperationRequest:
    """Immutable request to execute a registered operation."""

    id: str
    agent_run_id: str
    workflow_id: str
    task_id: str
    operation_name: str
    idempotency_key: str
    operation_version: str = "1"
    parameters: Mapping[str, Any] = field(default_factory=dict)
    expected_effects: tuple[str, ...] = ()
    constraints: tuple[str, ...] = ()
    permissions: tuple[str, ...] = ()
    environment: str = "local"
    resource_versions: Mapping[str, str] = field(default_factory=dict)
    approval_request_id: str | None = None
    budget_reservation_id: str | None = None
    checkpoint_id: str | None = None
    created_at: str = field(default_factory=_now_iso)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.id or not isinstance(self.id, str) or not self.id.strip():
            raise InvalidAgentOperationContractError("Request id cannot be empty.")
        if (
            not self.agent_run_id
            or not isinstance(self.agent_run_id, str)
            or not self.agent_run_id.strip()
        ):
            raise InvalidAgentOperationContractError("agent_run_id cannot be empty.")
        if (
            not self.workflow_id
            or not isinstance(self.workflow_id, str)
            or not self.workflow_id.strip()
        ):
            raise InvalidAgentOperationContractError("workflow_id cannot be empty.")
        if (
            not self.task_id
            or not isinstance(self.task_id, str)
            or not self.task_id.strip()
        ):
            raise InvalidAgentOperationContractError("task_id cannot be empty.")
        if (
            not self.operation_name
            or not isinstance(self.operation_name, str)
            or not self.operation_name.strip()
        ):
            raise InvalidAgentOperationContractError("operation_name cannot be empty.")
        if (
            not self.operation_version
            or not isinstance(self.operation_version, str)
            or not self.operation_version.strip()
        ):
            raise InvalidAgentOperationContractError(
                "operation_version cannot be empty."
            )
        if (
            not self.environment
            or not isinstance(self.environment, str)
            or not self.environment.strip()
        ):
            raise InvalidAgentOperationContractError("environment cannot be empty.")
        if (
            not self.idempotency_key
            or not isinstance(self.idempotency_key, str)
            or not self.idempotency_key.strip()
        ):
            raise InvalidAgentOperationContractError("idempotency_key cannot be empty.")

        _ensure_timezone(self.created_at)

        # Ensure parameters are serializable
        try:
            json.dumps(self.parameters)
        except (TypeError, ValueError) as err:
            raise InvalidAgentOperationContractError(
                f"parameters must be JSON serializable: {err}"
            ) from err

        object.__setattr__(self, "parameters", _freeze_mapping(dict(self.parameters)))
        object.__setattr__(self, "expected_effects", tuple(self.expected_effects))
        object.__setattr__(self, "constraints", tuple(self.constraints))
        object.__setattr__(self, "permissions", tuple(self.permissions))
        object.__setattr__(
            self,
            "resource_versions",
            MappingProxyType(
                {str(k): str(v) for k, v in dict(self.resource_versions).items()}
            ),
        )
        object.__setattr__(self, "metadata", _freeze_mapping(dict(self.metadata)))

    def calculate_fingerprint(self) -> str:
        """Calculate a deterministic sha256 fingerprint for this operation request."""
        payload = {
            "operation_name": self.operation_name,
            "operation_version": self.operation_version,
            "parameters": self.parameters,
            "environment": self.environment,
            "resource_versions": dict(sorted(self.resource_versions.items())),
            "constraints": sorted(self.constraints),
            "permissions": sorted(self.permissions),
            "expected_effects": sorted(self.expected_effects),
        }
        encoded = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        """Return canonical serializable dictionary representation."""
        return {
            "id": self.id,
            "agent_run_id": self.agent_run_id,
            "workflow_id": self.workflow_id,
            "task_id": self.task_id,
            "operation_name": self.operation_name,
            "operation_version": self.operation_version,
            "parameters": dict(self.parameters),
            "expected_effects": list(self.expected_effects),
            "constraints": list(self.constraints),
            "permissions": list(self.permissions),
            "environment": self.environment,
            "resource_versions": dict(self.resource_versions),
            "idempotency_key": self.idempotency_key,
            "approval_request_id": self.approval_request_id,
            "budget_reservation_id": self.budget_reservation_id,
            "checkpoint_id": self.checkpoint_id,
            "created_at": self.created_at,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentOperationRequest:
        """Construct from canonical dictionary representation."""
        return cls(
            id=data["id"],
            agent_run_id=data["agent_run_id"],
            workflow_id=data["workflow_id"],
            task_id=data["task_id"],
            operation_name=data["operation_name"],
            operation_version=data.get("operation_version", "1"),
            parameters=data.get("parameters", {}),
            expected_effects=tuple(data.get("expected_effects", ())),
            constraints=tuple(data.get("constraints", ())),
            permissions=tuple(data.get("permissions", ())),
            environment=data.get("environment", "local"),
            resource_versions=data.get("resource_versions", {}),
            idempotency_key=data["idempotency_key"],
            approval_request_id=data.get("approval_request_id"),
            budget_reservation_id=data.get("budget_reservation_id"),
            checkpoint_id=data.get("checkpoint_id"),
            created_at=data.get("created_at", _now_iso()),
            metadata=data.get("metadata", {}),
        )


@dataclass(frozen=True)
class OperationDescriptor:
    """Descriptor declaring capabilities, schema, risks, and properties of an operation."""

    name: str
    description: str
    version: str = "1"
    input_schema: Mapping[str, Any] = field(default_factory=dict)
    output_schema: Mapping[str, Any] = field(default_factory=dict)
    effects: tuple[OperationEffectType | str, ...] = ()
    reversible: bool = True
    rollback_operation_name: str | None = None
    risks: tuple[str, ...] = ()
    required_permissions: tuple[str, ...] = ()
    sensitivity: str = "internal"
    validations: tuple[str, ...] = ()
    timeout_seconds: int = 30
    estimated_cost: float | None = None
    idempotent: bool = True
    compatible_environments: tuple[OperationEnvironment | str, ...] = (
        OperationEnvironment.LOCAL,
    )
    enabled: bool = True
    model_requirements: ModelRequirements | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.name or not isinstance(self.name, str) or not self.name.strip():
            raise InvalidAgentOperationContractError("Operation name cannot be empty.")
        if (
            not self.version
            or not isinstance(self.version, str)
            or not self.version.strip()
        ):
            raise InvalidAgentOperationContractError(
                "Operation version cannot be empty."
            )
        if self.timeout_seconds <= 0:
            raise InvalidAgentOperationContractError(
                "timeout_seconds must be positive."
            )
        if (
            self.model_requirements is not None
            and not isinstance(self.model_requirements, ModelRequirements)
        ):
            raise InvalidAgentOperationContractError(
                "model_requirements must be a ModelRequirements instance or None."
            )

        eff_tuples = []
        for eff in self.effects:
            eff_val = eff.value if isinstance(eff, OperationEffectType) else str(eff)
            eff_tuples.append(eff_val)

        env_tuples = []
        for env in self.compatible_environments:
            env_val = env.value if isinstance(env, OperationEnvironment) else str(env)
            env_tuples.append(env_val)

        object.__setattr__(
            self, "input_schema", _freeze_mapping(dict(self.input_schema))
        )
        object.__setattr__(
            self, "output_schema", _freeze_mapping(dict(self.output_schema))
        )
        object.__setattr__(self, "effects", tuple(eff_tuples))
        object.__setattr__(self, "risks", tuple(self.risks))
        object.__setattr__(
            self, "required_permissions", tuple(self.required_permissions)
        )
        object.__setattr__(self, "validations", tuple(self.validations))
        object.__setattr__(self, "compatible_environments", tuple(env_tuples))
        object.__setattr__(self, "metadata", _freeze_mapping(dict(self.metadata)))


@dataclass(frozen=True)
class OperationCapability:
    """Configured capability allowance and boundary restrictions for an operation."""

    operation_name: str
    operation_version: str = "1"
    allowed: bool = True
    constraints: tuple[str, ...] = ()
    requires_approval: bool = False
    maximum_uses: int | None = 5
    allowed_environments: tuple[OperationEnvironment | str, ...] = (
        OperationEnvironment.LOCAL,
    )
    allowed_parameter_paths: tuple[str, ...] = ()
    denied_parameter_paths: tuple[str, ...] = ()
    expires_at: str | None = None
    reason_codes: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if (
            not self.operation_name
            or not isinstance(self.operation_name, str)
            or not self.operation_name.strip()
        ):
            raise InvalidAgentOperationContractError(
                "Capability operation_name cannot be empty."
            )
        if (
            not self.operation_version
            or not isinstance(self.operation_version, str)
            or not self.operation_version.strip()
        ):
            raise InvalidAgentOperationContractError(
                "Capability operation_version cannot be empty."
            )

        if self.expires_at is not None:
            _ensure_timezone(self.expires_at)

        env_tuples = []
        for env in self.allowed_environments:
            env_val = env.value if isinstance(env, OperationEnvironment) else str(env)
            env_tuples.append(env_val)

        object.__setattr__(self, "constraints", tuple(self.constraints))
        object.__setattr__(self, "allowed_environments", tuple(env_tuples))
        object.__setattr__(
            self, "allowed_parameter_paths", tuple(self.allowed_parameter_paths)
        )
        object.__setattr__(
            self, "denied_parameter_paths", tuple(self.denied_parameter_paths)
        )
        object.__setattr__(self, "reason_codes", tuple(self.reason_codes))
        object.__setattr__(self, "metadata", _freeze_mapping(dict(self.metadata)))


@dataclass(frozen=True)
class OperationExecutionGateResult:
    """Structured conjuntive evaluation outcome across all 12 security gates."""

    request_id: str
    allowed: bool = True
    denied: bool = False
    blocked: bool = False
    requires_approval: bool = False
    requires_validation: bool = False
    requires_budget: bool = False
    registered: bool = True
    parameters_valid: bool = True
    capability_satisfied: bool = True
    permissions_satisfied: bool = True
    autonomy_satisfied: bool = True
    policy_satisfied: bool = True
    approval_satisfied: bool = True
    budget_satisfied: bool = True
    dependencies_satisfied: bool = True
    environment_satisfied: bool = True
    checkpoint_satisfied: bool = True
    rollback_satisfied: bool = True
    locks_satisfied: bool = True
    resource_versions_satisfied: bool = True
    reason_codes: tuple[str, ...] = ()
    evaluated_at: str = field(default_factory=_now_iso)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if (
            not self.request_id
            or not isinstance(self.request_id, str)
            or not self.request_id.strip()
        ):
            raise InvalidAgentOperationContractError("request_id cannot be empty.")
        _ensure_timezone(self.evaluated_at)
        object.__setattr__(self, "reason_codes", tuple(self.reason_codes))
        object.__setattr__(self, "metadata", _freeze_mapping(dict(self.metadata)))


@dataclass(frozen=True)
class AgentOperationExecutionResult:
    """Structured result returned by Operation Execution Adapter to the Runtime Loop."""

    id: str
    request_id: str
    agent_run_id: str
    workflow_id: str
    task_id: str
    operation_name: str
    idempotency_key: str
    operation_version: str = "1"
    status: AgentOperationExecutionStatus | str = (
        AgentOperationExecutionStatus.COMPLETED
    )
    success: bool = True
    execution_result_id: str | None = None
    effects: tuple[str, ...] = ()
    side_effects: tuple[str, ...] = ()
    artifacts: tuple[str, ...] = ()
    validation_result_ids: tuple[str, ...] = ()
    budget_consumption_id: str | None = None
    checkpoint_id: str | None = None
    transaction_boundary_id: str | None = None
    rollback_available: bool = True
    rollback_reference: str | None = None
    resource_versions_before: Mapping[str, str] = field(default_factory=dict)
    resource_versions_after: Mapping[str, str] = field(default_factory=dict)
    reason_codes: tuple[str, ...] = ()
    started_at: str = field(default_factory=_now_iso)
    completed_at: str = field(default_factory=_now_iso)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.id or not isinstance(self.id, str) or not self.id.strip():
            raise InvalidAgentOperationContractError("Result id cannot be empty.")
        if (
            not self.request_id
            or not isinstance(self.request_id, str)
            or not self.request_id.strip()
        ):
            raise InvalidAgentOperationContractError("request_id cannot be empty.")
        if (
            not self.agent_run_id
            or not isinstance(self.agent_run_id, str)
            or not self.agent_run_id.strip()
        ):
            raise InvalidAgentOperationContractError("agent_run_id cannot be empty.")
        if (
            not self.operation_name
            or not isinstance(self.operation_name, str)
            or not self.operation_name.strip()
        ):
            raise InvalidAgentOperationContractError("operation_name cannot be empty.")
        if (
            not self.idempotency_key
            or not isinstance(self.idempotency_key, str)
            or not self.idempotency_key.strip()
        ):
            raise InvalidAgentOperationContractError("idempotency_key cannot be empty.")

        _ensure_timezone(self.started_at)
        _ensure_timezone(self.completed_at)

        st_val = (
            self.status.value
            if isinstance(self.status, AgentOperationExecutionStatus)
            else str(self.status)
        )
        object.__setattr__(self, "status", st_val)
        object.__setattr__(self, "effects", tuple(self.effects))
        object.__setattr__(self, "side_effects", tuple(self.side_effects))
        object.__setattr__(self, "artifacts", tuple(self.artifacts))
        object.__setattr__(
            self, "validation_result_ids", tuple(self.validation_result_ids)
        )
        object.__setattr__(
            self,
            "resource_versions_before",
            MappingProxyType(
                {str(k): str(v) for k, v in dict(self.resource_versions_before).items()}
            ),
        )
        object.__setattr__(
            self,
            "resource_versions_after",
            MappingProxyType(
                {str(k): str(v) for k, v in dict(self.resource_versions_after).items()}
            ),
        )
        object.__setattr__(self, "reason_codes", tuple(self.reason_codes))
        object.__setattr__(self, "metadata", _freeze_mapping(dict(self.metadata)))

    def to_dict(self) -> dict[str, Any]:
        """Return canonical dictionary representation."""
        return {
            "id": self.id,
            "request_id": self.request_id,
            "agent_run_id": self.agent_run_id,
            "workflow_id": self.workflow_id,
            "task_id": self.task_id,
            "operation_name": self.operation_name,
            "operation_version": self.operation_version,
            "idempotency_key": self.idempotency_key,
            "status": self.status,
            "success": self.success,
            "execution_result_id": self.execution_result_id,
            "effects": list(self.effects),
            "side_effects": list(self.side_effects),
            "artifacts": list(self.artifacts),
            "validation_result_ids": list(self.validation_result_ids),
            "budget_consumption_id": self.budget_consumption_id,
            "rollback_available": self.rollback_available,
            "rollback_reference": self.rollback_reference,
            "resource_versions_before": dict(self.resource_versions_before),
            "resource_versions_after": dict(self.resource_versions_after),
            "reason_codes": list(self.reason_codes),
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "metadata": dict(self.metadata),
        }
