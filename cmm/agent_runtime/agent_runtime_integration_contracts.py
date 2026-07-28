"""Immutable contracts for the Agent Runtime integration composition root.

The contracts in this module compose canonical Agent Runtime contracts.  They
do not replace the canonical run, operation, workflow, or security models.
"""

from __future__ import annotations

import math
import re
from collections.abc import Iterable, Mapping
from copy import copy
from dataclasses import dataclass, field, fields, is_dataclass
from datetime import datetime, timezone
from enum import Enum
from types import MappingProxyType
from typing import Any

from cmm.agent_runtime.agent_runtime_integration_enums import (
    RESULT_SNAPSHOT_STATES,
    TERMINAL_INTEGRATION_STATES,
    IntegrationCompensationStatus,
    IntegrationExecutionState,
    IntegrationFailureMode,
)
from cmm.agent_runtime.agent_security_contracts import AgentPermissionContext
from cmm.agent_runtime.agent_security_enums import SensitivityLevel
from cmm.agent_runtime.operation_execution_contracts import (
    AgentOperationExecutionResult,
    AgentOperationRequest,
)
from cmm.agent_runtime.workflow_planner_contracts import AgentWorkflowPlan

_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:\-]{0,127}$")
_SECRET_KEYS = frozenset(
    {
        "password",
        "passwords",
        "passwd",
        "secret",
        "secrets",
        "token",
        "tokens",
        "api_key",
        "api_keys",
        "apikey",
        "authorization",
        "cookie",
        "credential",
        "credentials",
        "private_key",
        "access_key",
        "refresh_token",
        "bearer",
    }
)
_SECRET_KEY_PREFIXES = (
    "secret_",
    "password_",
    "passwd_",
    "api_key_",
    "apikey_",
    "private_key_",
    "access_key_",
    "refresh_token_",
    "authorization_",
    "bearer_",
)
_SECRET_KEY_SUFFIXES = (
    "_secret",
    "_password",
    "_passwd",
    "_token",
    "_api_key",
    "_apikey",
    "_credential",
    "_credentials",
    "_private_key",
    "_access_key",
)
_JSON_PRIMITIVES = (str, int, bool, float, type(None))
_CREDENTIAL_SECRET_SUFFIXES = frozenset(
    {"data", "id", "key", "secret", "token", "value"}
)


class _FrozenList(list[Any]):
    """List-compatible immutable snapshot preserving canonical equality."""

    @staticmethod
    def _reject_mutation(*args: Any, **kwargs: Any) -> None:
        raise TypeError("canonical snapshot collections are immutable")

    __setitem__ = _reject_mutation
    __delitem__ = _reject_mutation
    __iadd__ = _reject_mutation
    __imul__ = _reject_mutation
    append = _reject_mutation
    clear = _reject_mutation
    extend = _reject_mutation
    insert = _reject_mutation
    pop = _reject_mutation
    remove = _reject_mutation
    reverse = _reject_mutation
    sort = _reject_mutation


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _identifier(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not _ID_RE.fullmatch(value):
        raise ValueError(f"{field_name} must be a valid non-empty identifier")
    return value


def _optional_identifier(value: Any, field_name: str) -> str | None:
    if value is None:
        return None
    return _identifier(value, field_name)


def _identifier_tuple(value: Iterable[str], field_name: str) -> tuple[str, ...]:
    if isinstance(value, str):
        raise TypeError(f"{field_name} must be an iterable of identifiers")
    result = tuple(_identifier(item, field_name) for item in value)
    if len(result) != len(set(result)):
        raise ValueError(f"{field_name} must not contain duplicate identifiers")
    return result


def _string_tuple(value: Iterable[str], field_name: str) -> tuple[str, ...]:
    if isinstance(value, str):
        raise TypeError(f"{field_name} must be an iterable of strings")
    result: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise ValueError(f"{field_name} must contain non-empty strings")
        result.append(item.strip())
    return tuple(result)


def _utc_datetime(value: datetime | str, field_name: str) -> datetime:
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError(f"{field_name} must be an ISO datetime") from exc
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise ValueError(f"{field_name} must be a timezone-aware datetime")
    return value.astimezone(timezone.utc)


def _optional_utc_datetime(
    value: datetime | str | None, field_name: str
) -> datetime | None:
    if value is None:
        return None
    return _utc_datetime(value, field_name)


def _is_secret_key(key: str) -> bool:
    camel_separated = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", key)
    normalized = re.sub(r"[^A-Za-z0-9]+", "_", camel_separated).strip("_").casefold()
    exact_or_affixed = (
        normalized in _SECRET_KEYS
        or normalized.startswith(_SECRET_KEY_PREFIXES)
        or normalized.endswith(_SECRET_KEY_SUFFIXES)
    )
    if exact_or_affixed:
        return True
    parts = normalized.split("_")
    return (
        len(parts) > 1
        and parts[0] in {"credential", "credentials"}
        and parts[-1] in _CREDENTIAL_SECRET_SUFFIXES
    )


def _freeze_json(value: Any, field_name: str, *, reject_secrets: bool = False) -> Any:
    if isinstance(value, Enum):
        value = value.value
    if isinstance(value, Mapping):
        frozen: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise TypeError(f"{field_name} keys must be strings")
            if reject_secrets and _is_secret_key(key):
                raise ValueError(f"{field_name} contains secret-like key {key!r}")
            frozen[key] = _freeze_json(item, field_name, reject_secrets=reject_secrets)
        return MappingProxyType(frozen)
    if isinstance(value, (list, tuple)):
        return tuple(
            _freeze_json(item, field_name, reject_secrets=reject_secrets)
            for item in value
        )
    if isinstance(value, (set, frozenset)):
        return tuple(
            _freeze_json(item, field_name, reject_secrets=reject_secrets)
            for item in sorted(value, key=repr)
        )
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError(f"{field_name} must not contain non-finite numbers")
    if isinstance(value, _JSON_PRIMITIVES):
        return value
    raise ValueError(
        f"{field_name} must contain only JSON-safe values, got {type(value).__name__}"
    )


def _freeze_mapping(
    value: Mapping[str, Any] | None,
    field_name: str,
    *,
    reject_secrets: bool = False,
) -> MappingProxyType[str, Any]:
    if value is None:
        value = {}
    if not isinstance(value, Mapping):
        raise TypeError(f"{field_name} must be a mapping")
    return _freeze_json(value, field_name, reject_secrets=reject_secrets)


def _freeze_mapping_tuple(
    value: Iterable[Mapping[str, Any]], field_name: str
) -> tuple[MappingProxyType[str, Any], ...]:
    if isinstance(value, (str, bytes, Mapping)):
        raise TypeError(f"{field_name} must be an iterable of mappings")
    return tuple(_freeze_mapping(item, field_name) for item in value)


def _thaw_json(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _thaw_json(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_thaw_json(item) for item in value]
    if isinstance(value, Enum):
        return value.value
    return value


def _validate_canonical_json(
    value: Any, field_name: str, *, in_metadata: bool = False
) -> None:
    """Validate canonical serialized data without over-scanning parameters."""

    if isinstance(value, Enum):
        value = value.value
    if isinstance(value, Mapping):
        for key, item in value.items():
            if not isinstance(key, str):
                raise TypeError(f"{field_name} keys must be strings")
            if in_metadata and _is_secret_key(key):
                raise ValueError(f"{field_name} contains secret-like key {key!r}")
            _validate_canonical_json(
                item,
                field_name,
                in_metadata=in_metadata or key.casefold() == "metadata",
            )
        return
    if isinstance(value, (list, tuple, set, frozenset)):
        for item in value:
            _validate_canonical_json(item, field_name, in_metadata=in_metadata)
        return
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError(f"{field_name} must not contain non-finite numbers")
    if isinstance(value, _JSON_PRIMITIVES):
        return
    raise ValueError(
        f"{field_name} must contain only JSON-safe values, got {type(value).__name__}"
    )


def _immutable_canonical_value(
    value: Any, field_name: str, *, in_metadata: bool = False
) -> Any:
    """Copy and recursively freeze one value retained by a canonical contract."""

    if is_dataclass(value) and not isinstance(value, type):
        snapshot = copy(value)
        for definition in fields(value):
            object.__setattr__(
                snapshot,
                definition.name,
                _immutable_canonical_value(
                    getattr(value, definition.name),
                    f"{field_name}.{definition.name}",
                    in_metadata=in_metadata or definition.name.casefold() == "metadata",
                ),
            )
        return snapshot
    if isinstance(value, Mapping):
        result: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise TypeError(f"{field_name} keys must be strings")
            if in_metadata and _is_secret_key(key):
                raise ValueError(f"{field_name} contains secret-like key {key!r}")
            result[key] = _immutable_canonical_value(
                item,
                f"{field_name}.{key}",
                in_metadata=in_metadata or key.casefold() == "metadata",
            )
        return MappingProxyType(result)
    if isinstance(value, list):
        return _FrozenList(
            _immutable_canonical_value(item, field_name, in_metadata=in_metadata)
            for item in value
        )
    if isinstance(value, tuple):
        return tuple(
            _immutable_canonical_value(item, field_name, in_metadata=in_metadata)
            for item in value
        )
    if isinstance(value, (set, frozenset)):
        return frozenset(
            _immutable_canonical_value(item, field_name, in_metadata=in_metadata)
            for item in sorted(value, key=repr)
        )
    if isinstance(value, (Enum, datetime)):
        return value
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError(f"{field_name} must not contain non-finite numbers")
    if isinstance(value, _JSON_PRIMITIVES):
        return value
    raise ValueError(
        f"{field_name} must contain only JSON-safe values, got {type(value).__name__}"
    )


def _snapshot_canonical_contract(value: Any, field_name: str) -> Any:
    """Validate serialized canonical content and retain an immutable copy."""

    serialized = value.to_dict()
    _validate_canonical_json(serialized, field_name)
    return _immutable_canonical_value(value, field_name)


def _enum(value: Any, enum_type: type[Enum], field_name: str) -> Any:
    try:
        return value if isinstance(value, enum_type) else enum_type(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} has an invalid value") from exc


def _positive_int(value: Any, field_name: str, *, allow_zero: bool = False) -> int:
    minimum = 0 if allow_zero else 1
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        comparison = "non-negative" if allow_zero else "positive"
        raise ValueError(f"{field_name} must be a {comparison} integer")
    return value


def _optional_positive_number(value: Any, field_name: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{field_name} must be a positive number")
    normalized = float(value)
    if not math.isfinite(normalized) or normalized <= 0:
        raise ValueError(f"{field_name} must be a positive number")
    return normalized


def _operation_result_to_dict(
    value: AgentOperationExecutionResult,
) -> dict[str, Any]:
    data = value.to_dict()
    data["checkpoint_id"] = value.checkpoint_id
    data["transaction_boundary_id"] = value.transaction_boundary_id
    return _thaw_json(data)


def _operation_result_from_dict(
    data: Mapping[str, Any],
) -> AgentOperationExecutionResult:
    return AgentOperationExecutionResult(
        id=data["id"],
        request_id=data["request_id"],
        agent_run_id=data["agent_run_id"],
        workflow_id=data["workflow_id"],
        task_id=data["task_id"],
        operation_name=data["operation_name"],
        idempotency_key=data["idempotency_key"],
        operation_version=data.get("operation_version", "1"),
        status=data.get("status", "completed"),
        success=data.get("success", True),
        execution_result_id=data.get("execution_result_id"),
        effects=tuple(data.get("effects", ())),
        side_effects=tuple(data.get("side_effects", ())),
        artifacts=tuple(data.get("artifacts", ())),
        validation_result_ids=tuple(data.get("validation_result_ids", ())),
        budget_consumption_id=data.get("budget_consumption_id"),
        checkpoint_id=data.get("checkpoint_id"),
        transaction_boundary_id=data.get("transaction_boundary_id"),
        rollback_available=data.get("rollback_available", True),
        rollback_reference=data.get("rollback_reference"),
        resource_versions_before=data.get("resource_versions_before", {}),
        resource_versions_after=data.get("resource_versions_after", {}),
        reason_codes=tuple(data.get("reason_codes", ())),
        started_at=data["started_at"],
        completed_at=data["completed_at"],
        metadata=data.get("metadata", {}),
    )


@dataclass(frozen=True, slots=True)
class IntegrationExecutionPolicy:
    """Limits and failure semantics for one integrated execution."""

    max_operations: int = 100
    max_retries: int = 3
    failure_mode: IntegrationFailureMode = IntegrationFailureMode.MANDATORY_FAIL_CLOSED
    allow_delegation: bool = True
    allow_recovery: bool = True
    allow_memory_updates: bool = True
    require_terminal_validation: bool = True
    compensate_on_failure: bool = True
    fail_on_best_effort_error: bool = False
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "max_operations", _positive_int(self.max_operations, "max_operations")
        )
        object.__setattr__(
            self,
            "max_retries",
            _positive_int(self.max_retries, "max_retries", allow_zero=True),
        )
        object.__setattr__(
            self,
            "failure_mode",
            _enum(self.failure_mode, IntegrationFailureMode, "failure_mode"),
        )
        for field_name in (
            "allow_delegation",
            "allow_recovery",
            "allow_memory_updates",
            "require_terminal_validation",
            "compensate_on_failure",
            "fail_on_best_effort_error",
        ):
            if not isinstance(getattr(self, field_name), bool):
                raise TypeError(f"{field_name} must be a bool")
        object.__setattr__(
            self,
            "metadata",
            _freeze_mapping(self.metadata, "metadata", reject_secrets=True),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "max_operations": self.max_operations,
            "max_retries": self.max_retries,
            "failure_mode": self.failure_mode.value,
            "allow_delegation": self.allow_delegation,
            "allow_recovery": self.allow_recovery,
            "allow_memory_updates": self.allow_memory_updates,
            "require_terminal_validation": self.require_terminal_validation,
            "compensate_on_failure": self.compensate_on_failure,
            "fail_on_best_effort_error": self.fail_on_best_effort_error,
            "metadata": _thaw_json(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> IntegrationExecutionPolicy:
        return cls(
            max_operations=data.get("max_operations", 100),
            max_retries=data.get("max_retries", 3),
            failure_mode=data.get(
                "failure_mode", IntegrationFailureMode.MANDATORY_FAIL_CLOSED
            ),
            allow_delegation=data.get("allow_delegation", True),
            allow_recovery=data.get("allow_recovery", True),
            allow_memory_updates=data.get("allow_memory_updates", True),
            require_terminal_validation=data.get("require_terminal_validation", True),
            compensate_on_failure=data.get("compensate_on_failure", True),
            fail_on_best_effort_error=data.get("fail_on_best_effort_error", False),
            metadata=data.get("metadata", {}),
        )


@dataclass(frozen=True, slots=True)
class IntegratedAgentExecutionRequest:
    """Complete immutable input to the integration composition root."""

    execution_id: str
    request_id: str
    goal_id: str
    actor_id: str
    owner_actor_id: str
    requested_agent_id: str | None = None
    requested_agent_version: str | None = None
    required_capabilities: tuple[str, ...] = ()
    required_agent_profile: Mapping[str, Any] = field(default_factory=dict)
    operations: tuple[AgentOperationRequest, ...] = ()
    workflow: AgentWorkflowPlan | None = None
    cognitive_context: Mapping[str, Any] = field(default_factory=dict)
    permission_context: AgentPermissionContext | None = None
    resources: Mapping[str, Any] = field(default_factory=dict)
    sensitivity: SensitivityLevel = SensitivityLevel.INTERNAL
    max_autonomy_level: int = 0
    budget_id: str | None = None
    budget_allocations: Mapping[str, Any] = field(default_factory=dict)
    available_approval_ids: tuple[str, ...] = ()
    deadline: datetime | None = None
    timeout_seconds: float | None = None
    delegation_policy: Mapping[str, Any] = field(default_factory=dict)
    recovery_policy: Mapping[str, Any] = field(default_factory=dict)
    observability: Mapping[str, Any] = field(default_factory=dict)
    trace_id: str | None = None
    correlation_id: str | None = None
    causation_id: str | None = None
    policy: IntegrationExecutionPolicy = field(
        default_factory=IntegrationExecutionPolicy
    )
    created_at: datetime = field(default_factory=_now_utc)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in (
            "execution_id",
            "request_id",
            "goal_id",
            "actor_id",
            "owner_actor_id",
        ):
            object.__setattr__(
                self, field_name, _identifier(getattr(self, field_name), field_name)
            )
        for field_name in (
            "requested_agent_id",
            "budget_id",
            "trace_id",
            "correlation_id",
            "causation_id",
        ):
            object.__setattr__(
                self,
                field_name,
                _optional_identifier(getattr(self, field_name), field_name),
            )
        if self.requested_agent_version is not None and (
            not isinstance(self.requested_agent_version, str)
            or not self.requested_agent_version.strip()
        ):
            raise ValueError("requested_agent_version must be a non-empty string")
        object.__setattr__(
            self,
            "required_capabilities",
            _string_tuple(self.required_capabilities, "required_capabilities"),
        )
        operations = tuple(self.operations)
        if any(not isinstance(item, AgentOperationRequest) for item in operations):
            raise ValueError("operations must contain AgentOperationRequest values")
        if self.workflow is not None and not isinstance(
            self.workflow, AgentWorkflowPlan
        ):
            raise ValueError("workflow must be an AgentWorkflowPlan")
        if operations and self.workflow is not None:
            raise ValueError("provide operations or workflow, not both")
        # Neither operations nor a workflow is permitted: it signals that a
        # configured planning_service must produce the workflow before
        # execution (see AgentRuntimeIntegrationService planner wiring).
        if self.permission_context is not None and not isinstance(
            self.permission_context, AgentPermissionContext
        ):
            raise ValueError("permission_context must be an AgentPermissionContext")
        object.__setattr__(
            self,
            "operations",
            tuple(
                _snapshot_canonical_contract(item, "operations") for item in operations
            ),
        )
        if self.workflow is not None:
            object.__setattr__(
                self,
                "workflow",
                _snapshot_canonical_contract(self.workflow, "workflow"),
            )
        if self.permission_context is not None:
            object.__setattr__(
                self,
                "permission_context",
                _snapshot_canonical_contract(
                    self.permission_context, "permission_context"
                ),
            )
        for field_name in (
            "required_agent_profile",
            "cognitive_context",
            "resources",
            "budget_allocations",
            "delegation_policy",
            "recovery_policy",
            "observability",
        ):
            object.__setattr__(
                self,
                field_name,
                _freeze_mapping(getattr(self, field_name), field_name),
            )
        object.__setattr__(
            self,
            "sensitivity",
            _enum(self.sensitivity, SensitivityLevel, "sensitivity"),
        )
        if (
            isinstance(self.max_autonomy_level, bool)
            or not isinstance(self.max_autonomy_level, int)
            or not 0 <= self.max_autonomy_level <= 4
        ):
            raise ValueError("max_autonomy_level must be an integer from 0 through 4")
        object.__setattr__(
            self,
            "available_approval_ids",
            _identifier_tuple(self.available_approval_ids, "available_approval_ids"),
        )
        object.__setattr__(
            self, "deadline", _optional_utc_datetime(self.deadline, "deadline")
        )
        object.__setattr__(
            self,
            "timeout_seconds",
            _optional_positive_number(self.timeout_seconds, "timeout_seconds"),
        )
        if not isinstance(self.policy, IntegrationExecutionPolicy):
            raise TypeError("policy must be an IntegrationExecutionPolicy")
        object.__setattr__(
            self, "created_at", _utc_datetime(self.created_at, "created_at")
        )
        object.__setattr__(
            self,
            "metadata",
            _freeze_mapping(self.metadata, "metadata", reject_secrets=True),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "execution_id": self.execution_id,
            "request_id": self.request_id,
            "goal_id": self.goal_id,
            "actor_id": self.actor_id,
            "owner_actor_id": self.owner_actor_id,
            "requested_agent_id": self.requested_agent_id,
            "requested_agent_version": self.requested_agent_version,
            "required_capabilities": list(self.required_capabilities),
            "required_agent_profile": _thaw_json(self.required_agent_profile),
            "operations": [_thaw_json(item.to_dict()) for item in self.operations],
            "workflow": _thaw_json(self.workflow.to_dict()) if self.workflow else None,
            "cognitive_context": _thaw_json(self.cognitive_context),
            "permission_context": _thaw_json(self.permission_context.to_dict())
            if self.permission_context
            else None,
            "resources": _thaw_json(self.resources),
            "sensitivity": self.sensitivity.value,
            "max_autonomy_level": self.max_autonomy_level,
            "budget_id": self.budget_id,
            "budget_allocations": _thaw_json(self.budget_allocations),
            "available_approval_ids": list(self.available_approval_ids),
            "deadline": self.deadline.isoformat() if self.deadline else None,
            "timeout_seconds": self.timeout_seconds,
            "delegation_policy": _thaw_json(self.delegation_policy),
            "recovery_policy": _thaw_json(self.recovery_policy),
            "observability": _thaw_json(self.observability),
            "trace_id": self.trace_id,
            "correlation_id": self.correlation_id,
            "causation_id": self.causation_id,
            "policy": self.policy.to_dict(),
            "created_at": self.created_at.isoformat(),
            "metadata": _thaw_json(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> IntegratedAgentExecutionRequest:
        permission_data = data.get("permission_context")
        workflow_data = data.get("workflow")
        return cls(
            execution_id=data["execution_id"],
            request_id=data["request_id"],
            goal_id=data["goal_id"],
            actor_id=data["actor_id"],
            owner_actor_id=data["owner_actor_id"],
            requested_agent_id=data.get("requested_agent_id"),
            requested_agent_version=data.get("requested_agent_version"),
            required_capabilities=tuple(data.get("required_capabilities", ())),
            required_agent_profile=data.get("required_agent_profile", {}),
            operations=tuple(
                AgentOperationRequest.from_dict(dict(item))
                for item in data.get("operations", ())
            ),
            workflow=AgentWorkflowPlan.from_dict(dict(workflow_data))
            if workflow_data
            else None,
            cognitive_context=data.get("cognitive_context", {}),
            permission_context=AgentPermissionContext.from_mapping(permission_data)
            if permission_data
            else None,
            resources=data.get("resources", {}),
            sensitivity=data.get("sensitivity", SensitivityLevel.INTERNAL),
            max_autonomy_level=data.get("max_autonomy_level", 0),
            budget_id=data.get("budget_id"),
            budget_allocations=data.get("budget_allocations", {}),
            available_approval_ids=tuple(data.get("available_approval_ids", ())),
            deadline=data.get("deadline"),
            timeout_seconds=data.get("timeout_seconds"),
            delegation_policy=data.get("delegation_policy", {}),
            recovery_policy=data.get("recovery_policy", {}),
            observability=data.get("observability", {}),
            trace_id=data.get("trace_id"),
            correlation_id=data.get("correlation_id"),
            causation_id=data.get("causation_id"),
            policy=IntegrationExecutionPolicy.from_dict(data.get("policy", {})),
            created_at=data.get("created_at", _now_utc()),
            metadata=data.get("metadata", {}),
        )


@dataclass(frozen=True, slots=True)
class IntegrationCompensation:
    """One durable, idempotent compensation journal entry."""

    compensation_id: str
    execution_id: str
    action: str
    target_id: str | None = None
    idempotency_key: str | None = None
    failure_mode: IntegrationFailureMode = (
        IntegrationFailureMode.MANDATORY_WITH_COMPENSATION
    )
    status: IntegrationCompensationStatus = IntegrationCompensationStatus.PENDING
    payload: Mapping[str, Any] = field(default_factory=dict)
    attempt_count: int = 0
    error: str | None = None
    created_at: datetime = field(default_factory=_now_utc)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in ("compensation_id", "execution_id"):
            object.__setattr__(
                self, field_name, _identifier(getattr(self, field_name), field_name)
            )
        for field_name in ("target_id", "idempotency_key"):
            object.__setattr__(
                self,
                field_name,
                _optional_identifier(getattr(self, field_name), field_name),
            )
        if not isinstance(self.action, str) or not self.action.strip():
            raise ValueError("action must be a non-empty string")
        object.__setattr__(self, "action", self.action.strip())
        object.__setattr__(
            self,
            "failure_mode",
            _enum(self.failure_mode, IntegrationFailureMode, "failure_mode"),
        )
        object.__setattr__(
            self,
            "status",
            _enum(self.status, IntegrationCompensationStatus, "status"),
        )
        object.__setattr__(self, "payload", _freeze_mapping(self.payload, "payload"))
        object.__setattr__(
            self,
            "attempt_count",
            _positive_int(self.attempt_count, "attempt_count", allow_zero=True),
        )
        if self.error is not None and not isinstance(self.error, str):
            raise ValueError("error must be a string or None")
        object.__setattr__(
            self, "created_at", _utc_datetime(self.created_at, "created_at")
        )
        for field_name in ("started_at", "completed_at"):
            object.__setattr__(
                self,
                field_name,
                _optional_utc_datetime(getattr(self, field_name), field_name),
            )
        object.__setattr__(
            self,
            "metadata",
            _freeze_mapping(self.metadata, "metadata", reject_secrets=True),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "compensation_id": self.compensation_id,
            "execution_id": self.execution_id,
            "action": self.action,
            "target_id": self.target_id,
            "idempotency_key": self.idempotency_key,
            "failure_mode": self.failure_mode.value,
            "status": self.status.value,
            "payload": _thaw_json(self.payload),
            "attempt_count": self.attempt_count,
            "error": self.error,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat()
            if self.completed_at
            else None,
            "metadata": _thaw_json(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> IntegrationCompensation:
        return cls(
            compensation_id=data["compensation_id"],
            execution_id=data["execution_id"],
            action=data["action"],
            target_id=data.get("target_id"),
            idempotency_key=data.get("idempotency_key"),
            failure_mode=data.get(
                "failure_mode", IntegrationFailureMode.MANDATORY_WITH_COMPENSATION
            ),
            status=data.get("status", IntegrationCompensationStatus.PENDING),
            payload=data.get("payload", {}),
            attempt_count=data.get("attempt_count", 0),
            error=data.get("error"),
            created_at=data.get("created_at", _now_utc()),
            started_at=data.get("started_at"),
            completed_at=data.get("completed_at"),
            metadata=data.get("metadata", {}),
        )


@dataclass(frozen=True, slots=True)
class IntegratedAgentExecutionResult:
    """Immutable terminal or paused snapshot of an integrated execution."""

    execution_id: str
    request_id: str
    goal_id: str
    final_state: IntegrationExecutionState
    agent_id: str | None = None
    agent_version: str | None = None
    agent_run_id: str | None = None
    operation_request_ids: tuple[str, ...] = ()
    operation_results: tuple[AgentOperationExecutionResult, ...] = ()
    result: Mapping[str, Any] = field(default_factory=dict)
    validation_results: tuple[Mapping[str, Any], ...] = ()
    memory_updates: tuple[Mapping[str, Any], ...] = ()
    delegations: tuple[Mapping[str, Any], ...] = ()
    approval_ids: tuple[str, ...] = ()
    budget_id: str | None = None
    budget_allocations: Mapping[str, Any] = field(default_factory=dict)
    budget_consumption_ids: tuple[str, ...] = ()
    checkpoint_ids: tuple[str, ...] = ()
    retry_count: int = 0
    recovery_attempts: tuple[Mapping[str, Any], ...] = ()
    event_ids: tuple[str, ...] = ()
    trace_id: str | None = None
    metrics: Mapping[str, Any] = field(default_factory=dict)
    audit_ids: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()
    created_at: datetime = field(default_factory=_now_utc)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in ("execution_id", "request_id", "goal_id"):
            object.__setattr__(
                self, field_name, _identifier(getattr(self, field_name), field_name)
            )
        for field_name in ("agent_id", "agent_run_id", "budget_id", "trace_id"):
            object.__setattr__(
                self,
                field_name,
                _optional_identifier(getattr(self, field_name), field_name),
            )
        if self.agent_version is not None and (
            not isinstance(self.agent_version, str) or not self.agent_version.strip()
        ):
            raise ValueError("agent_version must be a non-empty string")
        object.__setattr__(
            self,
            "final_state",
            _enum(self.final_state, IntegrationExecutionState, "final_state"),
        )
        if self.final_state not in RESULT_SNAPSHOT_STATES:
            raise ValueError(
                "final_state must be a terminal or paused result snapshot state"
            )
        for field_name in (
            "operation_request_ids",
            "approval_ids",
            "budget_consumption_ids",
            "checkpoint_ids",
            "event_ids",
            "audit_ids",
        ):
            object.__setattr__(
                self,
                field_name,
                _identifier_tuple(getattr(self, field_name), field_name),
            )
        operation_results = tuple(self.operation_results)
        if any(
            not isinstance(item, AgentOperationExecutionResult)
            for item in operation_results
        ):
            raise ValueError(
                "operation_results must contain AgentOperationExecutionResult values"
            )
        for item in operation_results:
            if self.agent_run_id is not None and item.agent_run_id != self.agent_run_id:
                raise ValueError(
                    "operation_results agent_run_id must match result agent_run_id"
                )
            if (
                self.operation_request_ids
                and item.request_id not in self.operation_request_ids
            ):
                raise ValueError(
                    "operation_results request_id must match operation_request_ids"
                )
        object.__setattr__(
            self,
            "operation_results",
            tuple(
                _snapshot_canonical_contract(item, "operation_results")
                for item in operation_results
            ),
        )
        object.__setattr__(self, "result", _freeze_mapping(self.result, "result"))
        for field_name in (
            "validation_results",
            "memory_updates",
            "delegations",
            "recovery_attempts",
        ):
            object.__setattr__(
                self,
                field_name,
                _freeze_mapping_tuple(getattr(self, field_name), field_name),
            )
        for field_name in ("budget_allocations", "metrics"):
            object.__setattr__(
                self,
                field_name,
                _freeze_mapping(getattr(self, field_name), field_name),
            )
        object.__setattr__(
            self,
            "retry_count",
            _positive_int(self.retry_count, "retry_count", allow_zero=True),
        )
        for field_name in ("warnings", "errors"):
            object.__setattr__(
                self,
                field_name,
                _string_tuple(getattr(self, field_name), field_name),
            )
        object.__setattr__(
            self, "created_at", _utc_datetime(self.created_at, "created_at")
        )
        for field_name in ("started_at", "completed_at"):
            object.__setattr__(
                self,
                field_name,
                _optional_utc_datetime(getattr(self, field_name), field_name),
            )
        object.__setattr__(
            self,
            "metadata",
            _freeze_mapping(self.metadata, "metadata", reject_secrets=True),
        )

    @property
    def is_terminal(self) -> bool:
        return self.final_state in TERMINAL_INTEGRATION_STATES

    @property
    def run_id(self) -> str | None:
        """Compatibility alias for the canonical agent run identifier."""

        return self.agent_run_id

    def to_dict(self) -> dict[str, Any]:
        return {
            "execution_id": self.execution_id,
            "request_id": self.request_id,
            "goal_id": self.goal_id,
            "agent_id": self.agent_id,
            "agent_version": self.agent_version,
            "agent_run_id": self.agent_run_id,
            "final_state": self.final_state.value,
            "operation_request_ids": list(self.operation_request_ids),
            "operation_results": [
                _operation_result_to_dict(item) for item in self.operation_results
            ],
            "result": _thaw_json(self.result),
            "validation_results": _thaw_json(self.validation_results),
            "memory_updates": _thaw_json(self.memory_updates),
            "delegations": _thaw_json(self.delegations),
            "approval_ids": list(self.approval_ids),
            "budget_id": self.budget_id,
            "budget_allocations": _thaw_json(self.budget_allocations),
            "budget_consumption_ids": list(self.budget_consumption_ids),
            "checkpoint_ids": list(self.checkpoint_ids),
            "retry_count": self.retry_count,
            "recovery_attempts": _thaw_json(self.recovery_attempts),
            "event_ids": list(self.event_ids),
            "trace_id": self.trace_id,
            "metrics": _thaw_json(self.metrics),
            "audit_ids": list(self.audit_ids),
            "warnings": list(self.warnings),
            "errors": list(self.errors),
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat()
            if self.completed_at
            else None,
            "metadata": _thaw_json(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> IntegratedAgentExecutionResult:
        return cls(
            execution_id=data["execution_id"],
            request_id=data["request_id"],
            goal_id=data["goal_id"],
            agent_id=data.get("agent_id"),
            agent_version=data.get("agent_version"),
            agent_run_id=data.get("agent_run_id"),
            final_state=data["final_state"],
            operation_request_ids=tuple(data.get("operation_request_ids", ())),
            operation_results=tuple(
                _operation_result_from_dict(item)
                for item in data.get("operation_results", ())
            ),
            result=data.get("result", {}),
            validation_results=tuple(data.get("validation_results", ())),
            memory_updates=tuple(data.get("memory_updates", ())),
            delegations=tuple(data.get("delegations", ())),
            approval_ids=tuple(data.get("approval_ids", ())),
            budget_id=data.get("budget_id"),
            budget_allocations=data.get("budget_allocations", {}),
            budget_consumption_ids=tuple(data.get("budget_consumption_ids", ())),
            checkpoint_ids=tuple(data.get("checkpoint_ids", ())),
            retry_count=data.get("retry_count", 0),
            recovery_attempts=tuple(data.get("recovery_attempts", ())),
            event_ids=tuple(data.get("event_ids", ())),
            trace_id=data.get("trace_id"),
            metrics=data.get("metrics", {}),
            audit_ids=tuple(data.get("audit_ids", ())),
            warnings=tuple(data.get("warnings", ())),
            errors=tuple(data.get("errors", ())),
            created_at=data.get("created_at", _now_utc()),
            started_at=data.get("started_at"),
            completed_at=data.get("completed_at"),
            metadata=data.get("metadata", {}),
        )


@dataclass(frozen=True, slots=True)
class IntegrationExecutionRecord:
    """Durable integration state stored between orchestration steps."""

    execution_id: str
    request_id: str
    goal_id: str
    state: IntegrationExecutionState = IntegrationExecutionState.CREATED
    version: int = 1
    request: IntegratedAgentExecutionRequest | None = None
    agent_id: str | None = None
    agent_version: str | None = None
    agent_run_id: str | None = None
    workflow_id: str | None = None
    pending_approval_ids: tuple[str, ...] = ()
    approval_ids: tuple[str, ...] = ()
    budget_id: str | None = None
    budget_reservation_ids: tuple[str, ...] = ()
    operation_result_ids: tuple[str, ...] = ()
    checkpoint_ids: tuple[str, ...] = ()
    delegation_ids: tuple[str, ...] = ()
    event_ids: tuple[str, ...] = ()
    compensations: tuple[IntegrationCompensation, ...] = ()
    result: IntegratedAgentExecutionResult | None = None
    last_error: str | None = None
    created_at: datetime = field(default_factory=_now_utc)
    updated_at: datetime = field(default_factory=_now_utc)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in ("execution_id", "request_id", "goal_id"):
            object.__setattr__(
                self, field_name, _identifier(getattr(self, field_name), field_name)
            )
        object.__setattr__(
            self, "state", _enum(self.state, IntegrationExecutionState, "state")
        )
        object.__setattr__(self, "version", _positive_int(self.version, "version"))
        if self.request is not None:
            if not isinstance(self.request, IntegratedAgentExecutionRequest):
                raise ValueError("request must be an IntegratedAgentExecutionRequest")
            if (
                self.request.execution_id != self.execution_id
                or self.request.request_id != self.request_id
                or self.request.goal_id != self.goal_id
            ):
                raise ValueError("request identifiers must match record identifiers")
        for field_name in (
            "agent_id",
            "agent_run_id",
            "workflow_id",
            "budget_id",
        ):
            object.__setattr__(
                self,
                field_name,
                _optional_identifier(getattr(self, field_name), field_name),
            )
        if self.agent_version is not None and (
            not isinstance(self.agent_version, str) or not self.agent_version.strip()
        ):
            raise ValueError("agent_version must be a non-empty string")
        for field_name in (
            "pending_approval_ids",
            "approval_ids",
            "budget_reservation_ids",
            "operation_result_ids",
            "checkpoint_ids",
            "delegation_ids",
            "event_ids",
        ):
            object.__setattr__(
                self,
                field_name,
                _identifier_tuple(getattr(self, field_name), field_name),
            )
        compensations = tuple(self.compensations)
        if any(not isinstance(item, IntegrationCompensation) for item in compensations):
            raise ValueError(
                "compensations must contain IntegrationCompensation values"
            )
        if any(item.execution_id != self.execution_id for item in compensations):
            raise ValueError("compensation execution_id must match record execution_id")
        object.__setattr__(self, "compensations", compensations)
        if self.result is not None:
            if not isinstance(self.result, IntegratedAgentExecutionResult):
                raise ValueError("result must be an IntegratedAgentExecutionResult")
            if (
                self.result.execution_id != self.execution_id
                or self.result.request_id != self.request_id
                or self.result.goal_id != self.goal_id
                or self.result.agent_run_id != self.agent_run_id
                or self.result.final_state != self.state
            ):
                raise ValueError("result identifiers and state must match record")
        if self.last_error is not None and not isinstance(self.last_error, str):
            raise ValueError("last_error must be a string or None")
        for field_name in ("created_at", "updated_at"):
            object.__setattr__(
                self,
                field_name,
                _utc_datetime(getattr(self, field_name), field_name),
            )
        for field_name in ("started_at", "completed_at"):
            object.__setattr__(
                self,
                field_name,
                _optional_utc_datetime(getattr(self, field_name), field_name),
            )
        object.__setattr__(
            self,
            "metadata",
            _freeze_mapping(self.metadata, "metadata", reject_secrets=True),
        )

    @property
    def is_terminal(self) -> bool:
        return self.state in TERMINAL_INTEGRATION_STATES

    @property
    def run_id(self) -> str | None:
        return self.agent_run_id

    def to_dict(self) -> dict[str, Any]:
        return {
            "execution_id": self.execution_id,
            "request_id": self.request_id,
            "goal_id": self.goal_id,
            "state": self.state.value,
            "version": self.version,
            "request": self.request.to_dict() if self.request else None,
            "agent_id": self.agent_id,
            "agent_version": self.agent_version,
            "agent_run_id": self.agent_run_id,
            "workflow_id": self.workflow_id,
            "pending_approval_ids": list(self.pending_approval_ids),
            "approval_ids": list(self.approval_ids),
            "budget_id": self.budget_id,
            "budget_reservation_ids": list(self.budget_reservation_ids),
            "operation_result_ids": list(self.operation_result_ids),
            "checkpoint_ids": list(self.checkpoint_ids),
            "delegation_ids": list(self.delegation_ids),
            "event_ids": list(self.event_ids),
            "compensations": [item.to_dict() for item in self.compensations],
            "result": self.result.to_dict() if self.result else None,
            "last_error": self.last_error,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat()
            if self.completed_at
            else None,
            "metadata": _thaw_json(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> IntegrationExecutionRecord:
        return cls(
            execution_id=data["execution_id"],
            request_id=data["request_id"],
            goal_id=data["goal_id"],
            state=data.get("state", IntegrationExecutionState.CREATED),
            version=data.get("version", 1),
            request=IntegratedAgentExecutionRequest.from_dict(data["request"])
            if data.get("request")
            else None,
            agent_id=data.get("agent_id"),
            agent_version=data.get("agent_version"),
            agent_run_id=data.get("agent_run_id"),
            workflow_id=data.get("workflow_id"),
            pending_approval_ids=tuple(data.get("pending_approval_ids", ())),
            approval_ids=tuple(data.get("approval_ids", ())),
            budget_id=data.get("budget_id"),
            budget_reservation_ids=tuple(data.get("budget_reservation_ids", ())),
            operation_result_ids=tuple(data.get("operation_result_ids", ())),
            checkpoint_ids=tuple(data.get("checkpoint_ids", ())),
            delegation_ids=tuple(data.get("delegation_ids", ())),
            event_ids=tuple(data.get("event_ids", ())),
            compensations=tuple(
                IntegrationCompensation.from_dict(item)
                for item in data.get("compensations", ())
            ),
            result=IntegratedAgentExecutionResult.from_dict(data["result"])
            if data.get("result")
            else None,
            last_error=data.get("last_error"),
            created_at=data.get("created_at", _now_utc()),
            updated_at=data.get("updated_at", _now_utc()),
            started_at=data.get("started_at"),
            completed_at=data.get("completed_at"),
            metadata=data.get("metadata", {}),
        )


@dataclass(frozen=True, slots=True)
class IntegrationExecutionStatus:
    """Compact immutable status snapshot for API and monitoring callers."""

    execution_id: str
    request_id: str
    goal_id: str
    state: IntegrationExecutionState = IntegrationExecutionState.CREATED
    version: int = 1
    agent_id: str | None = None
    agent_run_id: str | None = None
    pending_approval_ids: tuple[str, ...] = ()
    progress: Mapping[str, Any] = field(default_factory=dict)
    message: str | None = None
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()
    created_at: datetime = field(default_factory=_now_utc)
    updated_at: datetime = field(default_factory=_now_utc)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in ("execution_id", "request_id", "goal_id"):
            object.__setattr__(
                self, field_name, _identifier(getattr(self, field_name), field_name)
            )
        object.__setattr__(
            self, "state", _enum(self.state, IntegrationExecutionState, "state")
        )
        object.__setattr__(self, "version", _positive_int(self.version, "version"))
        for field_name in ("agent_id", "agent_run_id"):
            object.__setattr__(
                self,
                field_name,
                _optional_identifier(getattr(self, field_name), field_name),
            )
        object.__setattr__(
            self,
            "pending_approval_ids",
            _identifier_tuple(self.pending_approval_ids, "pending_approval_ids"),
        )
        object.__setattr__(self, "progress", _freeze_mapping(self.progress, "progress"))
        if self.message is not None and not isinstance(self.message, str):
            raise ValueError("message must be a string or None")
        for field_name in ("warnings", "errors"):
            object.__setattr__(
                self,
                field_name,
                _string_tuple(getattr(self, field_name), field_name),
            )
        for field_name in ("created_at", "updated_at"):
            object.__setattr__(
                self,
                field_name,
                _utc_datetime(getattr(self, field_name), field_name),
            )
        object.__setattr__(
            self,
            "metadata",
            _freeze_mapping(self.metadata, "metadata", reject_secrets=True),
        )

    @property
    def is_terminal(self) -> bool:
        return self.state in TERMINAL_INTEGRATION_STATES

    @property
    def run_id(self) -> str | None:
        return self.agent_run_id

    def to_dict(self) -> dict[str, Any]:
        return {
            "execution_id": self.execution_id,
            "request_id": self.request_id,
            "goal_id": self.goal_id,
            "state": self.state.value,
            "version": self.version,
            "agent_id": self.agent_id,
            "agent_run_id": self.agent_run_id,
            "pending_approval_ids": list(self.pending_approval_ids),
            "progress": _thaw_json(self.progress),
            "message": self.message,
            "warnings": list(self.warnings),
            "errors": list(self.errors),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "metadata": _thaw_json(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> IntegrationExecutionStatus:
        return cls(
            execution_id=data["execution_id"],
            request_id=data["request_id"],
            goal_id=data["goal_id"],
            state=data.get("state", IntegrationExecutionState.CREATED),
            version=data.get("version", 1),
            agent_id=data.get("agent_id"),
            agent_run_id=data.get("agent_run_id"),
            pending_approval_ids=tuple(data.get("pending_approval_ids", ())),
            progress=data.get("progress", {}),
            message=data.get("message"),
            warnings=tuple(data.get("warnings", ())),
            errors=tuple(data.get("errors", ())),
            created_at=data.get("created_at", _now_utc()),
            updated_at=data.get("updated_at", _now_utc()),
            metadata=data.get("metadata", {}),
        )


__all__ = [
    "IntegratedAgentExecutionRequest",
    "IntegratedAgentExecutionResult",
    "IntegrationCompensation",
    "IntegrationExecutionPolicy",
    "IntegrationExecutionRecord",
    "IntegrationExecutionStatus",
]
