"""Strict contracts for Phase 10.13 domain operations."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from types import MappingProxyType
from typing import Any

from cmm.agent_runtime.enums import OperationEffectType, PolicyRiskLevel
from cmm.agent_runtime.operation_execution_contracts import OperationDescriptor
from cmm.domains.enums import DomainOperationStatus, DomainOperationType
from cmm.domains.errors import (
    DomainContractValidationError,
    DomainOperationContractError,
    DomainOperationSerializationError,
)
from cmm.domains.registry_contracts import parse_semver


def _non_empty(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise DomainOperationContractError(
            f"{field_name} must be a non-empty string", field=field_name
        )
    return value.strip()


def _optional_text(value: Any, field_name: str) -> str | None:
    return None if value is None else _non_empty(value, field_name)


def _strict_bool(value: Any, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise DomainOperationContractError(
            f"{field_name} must be a boolean", field=field_name
        )
    return value


def _string_tuple(value: Any, field_name: str) -> tuple[str, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, (tuple, list)):
        raise DomainOperationContractError(
            f"{field_name} must be a sequence of strings", field=field_name
        )
    result = tuple(_non_empty(item, field_name) for item in value)
    if len(result) != len(set(result)):
        raise DomainOperationContractError(
            f"{field_name} must not contain duplicates", field=field_name
        )
    return result


def _validate_json(value: Any, path: str) -> Any:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise DomainOperationContractError(
                f"{path} must be JSON-safe and finite", field=path
            )
        return value
    if isinstance(value, Mapping):
        normalized: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise DomainOperationContractError(
                    f"{path} must have string keys", field=path
                )
            normalized[key] = _validate_json(item, f"{path}.{key}")
        return normalized
    if isinstance(value, (tuple, list)):
        return [
            _validate_json(item, f"{path}[{index}]") for index, item in enumerate(value)
        ]
    raise DomainOperationContractError(
        f"{path} must be JSON-safe",
        field=path,
        details={"type": type(value).__name__},
    )


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, (tuple, list)):
        return tuple(_freeze(item) for item in value)
    return value


def _thaw(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _thaw(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw(item) for item in value]
    return value


def _json_mapping(value: Any, field_name: str) -> MappingProxyType[str, Any]:
    if not isinstance(value, Mapping):
        raise DomainOperationContractError(
            f"{field_name} must be a mapping", field=field_name
        )
    return _freeze(_validate_json(value, field_name))


def _enum(value: Any, enum_type: type[Any], field_name: str) -> Any:
    if isinstance(value, enum_type):
        return value
    if isinstance(value, str):
        try:
            return enum_type(value)
        except ValueError as exc:
            raise DomainOperationContractError(
                f"Invalid {field_name}: {value}", field=field_name
            ) from exc
    raise DomainOperationContractError(
        f"{field_name} must be a {enum_type.__name__}", field=field_name
    )


def _aware(value: Any, field_name: str) -> datetime:
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value)
        except ValueError as exc:
            raise DomainOperationContractError(
                f"{field_name} must be an ISO datetime", field=field_name
            ) from exc
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise DomainOperationContractError(
            f"{field_name} must be timezone-aware", field=field_name
        )
    return value


def _reject_unknown(data: Mapping[str, Any], known: frozenset[str], name: str) -> None:
    unknown = sorted(set(data) - known)
    if unknown:
        raise DomainOperationSerializationError(
            f"{name}.from_dict got unknown fields: {unknown}",
            details={"unknown_fields": unknown},
        )


_TRANSITIONS: Mapping[DomainOperationStatus, frozenset[DomainOperationStatus]] = (
    MappingProxyType(
        {
            DomainOperationStatus.REGISTERED: frozenset(
                {
                    DomainOperationStatus.AVAILABLE,
                    DomainOperationStatus.UNAVAILABLE,
                    DomainOperationStatus.BLOCKED,
                    DomainOperationStatus.WAITING_FOR_APPROVAL,
                }
            ),
            DomainOperationStatus.UNAVAILABLE: frozenset(
                {DomainOperationStatus.AVAILABLE, DomainOperationStatus.BLOCKED}
            ),
            DomainOperationStatus.BLOCKED: frozenset(
                {
                    DomainOperationStatus.AVAILABLE,
                    DomainOperationStatus.WAITING_FOR_APPROVAL,
                }
            ),
            DomainOperationStatus.WAITING_FOR_APPROVAL: frozenset(
                {
                    DomainOperationStatus.AVAILABLE,
                    DomainOperationStatus.BLOCKED,
                    DomainOperationStatus.CANCELLED,
                }
            ),
            DomainOperationStatus.AVAILABLE: frozenset(
                {DomainOperationStatus.RUNNING, DomainOperationStatus.CANCELLED}
            ),
            DomainOperationStatus.RUNNING: frozenset(
                {
                    DomainOperationStatus.COMPLETED,
                    DomainOperationStatus.FAILED,
                    DomainOperationStatus.CANCELLED,
                }
            ),
            DomainOperationStatus.FAILED: frozenset(
                {DomainOperationStatus.ROLLED_BACK}
            ),
            DomainOperationStatus.COMPLETED: frozenset(),
            DomainOperationStatus.ROLLED_BACK: frozenset(),
            DomainOperationStatus.CANCELLED: frozenset(),
        }
    )
)


def validate_domain_operation_transition(
    source: DomainOperationStatus | str, target: DomainOperationStatus | str
) -> DomainOperationStatus:
    source_value = _enum(source, DomainOperationStatus, "source status")
    target_value = _enum(target, DomainOperationStatus, "target status")
    if target_value not in _TRANSITIONS[source_value]:
        raise DomainOperationContractError(
            f"Invalid domain operation transition: {source_value.value} -> {target_value.value}",
            details={"source": source_value.value, "target": target_value.value},
        )
    return target_value


_DEFINITION_FIELDS = frozenset(
    {
        "operation_id",
        "domain_id",
        "version",
        "name",
        "description",
        "operation_type",
        "input_schema",
        "output_schema",
        "required_resources",
        "required_permissions",
        "risk_level",
        "reversible",
        "requires_approval",
        "validation_policy_id",
        "rollback_policy_id",
        "enabled",
        "metadata",
    }
)


@dataclass(frozen=True, slots=True)
class DomainOperationDefinition:
    operation_id: str
    domain_id: str
    version: str
    name: str
    description: str
    operation_type: DomainOperationType
    input_schema: Mapping[str, Any] = field(default_factory=dict)
    output_schema: Mapping[str, Any] = field(default_factory=dict)
    required_resources: tuple[str, ...] = ()
    required_permissions: tuple[str, ...] = ()
    risk_level: PolicyRiskLevel = PolicyRiskLevel.NONE
    reversible: bool = False
    requires_approval: bool = False
    validation_policy_id: str | None = None
    rollback_policy_id: str | None = None
    enabled: bool = True
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        operation_id = _non_empty(self.operation_id, "operation_id")
        domain_id = _non_empty(self.domain_id, "domain_id")
        if not domain_id.startswith("domain:"):
            raise DomainOperationContractError(
                "domain_id must be canonical", field="domain_id"
            )
        slug = domain_id.removeprefix("domain:")
        if operation_id.split(".", 1)[0] != slug:
            raise DomainOperationContractError(
                "operation_id domain prefix must match domain_id", field="operation_id"
            )
        version = _non_empty(self.version, "version")
        try:
            parse_semver(version)
        except DomainContractValidationError as exc:
            raise DomainOperationContractError(
                f"Invalid semantic version: {version}", field="version"
            ) from exc
        operation_type = _enum(
            self.operation_type, DomainOperationType, "operation_type"
        )
        risk = _enum(self.risk_level, PolicyRiskLevel, "risk_level")
        reversible = _strict_bool(self.reversible, "reversible")
        approval = _strict_bool(self.requires_approval, "requires_approval")
        enabled = _strict_bool(self.enabled, "enabled")
        rollback_policy = _optional_text(self.rollback_policy_id, "rollback_policy_id")
        if not reversible and rollback_policy is not None:
            raise DomainOperationContractError(
                "A non-reversible operation cannot declare rollback support",
                field="rollback_policy_id",
            )
        if operation_type is DomainOperationType.DESTRUCTIVE and not approval:
            raise DomainOperationContractError(
                "A destructive operation requires explicit approval",
                field="requires_approval",
            )
        object.__setattr__(self, "operation_id", operation_id)
        object.__setattr__(self, "domain_id", domain_id)
        object.__setattr__(self, "version", version)
        object.__setattr__(self, "name", _non_empty(self.name, "name"))
        object.__setattr__(
            self, "description", _non_empty(self.description, "description")
        )
        object.__setattr__(self, "operation_type", operation_type)
        object.__setattr__(
            self, "input_schema", _json_mapping(self.input_schema, "input_schema")
        )
        object.__setattr__(
            self, "output_schema", _json_mapping(self.output_schema, "output_schema")
        )
        object.__setattr__(
            self,
            "required_resources",
            _string_tuple(self.required_resources, "required_resources"),
        )
        object.__setattr__(
            self,
            "required_permissions",
            _string_tuple(self.required_permissions, "required_permissions"),
        )
        object.__setattr__(self, "risk_level", risk)
        object.__setattr__(self, "reversible", reversible)
        object.__setattr__(self, "requires_approval", approval)
        object.__setattr__(
            self,
            "validation_policy_id",
            _optional_text(self.validation_policy_id, "validation_policy_id"),
        )
        object.__setattr__(self, "rollback_policy_id", rollback_policy)
        object.__setattr__(self, "enabled", enabled)
        object.__setattr__(self, "metadata", _json_mapping(self.metadata, "metadata"))

    def to_dict(self) -> dict[str, Any]:
        return {
            "operation_id": self.operation_id,
            "domain_id": self.domain_id,
            "version": self.version,
            "name": self.name,
            "description": self.description,
            "operation_type": self.operation_type.value,
            "input_schema": _thaw(self.input_schema),
            "output_schema": _thaw(self.output_schema),
            "required_resources": list(self.required_resources),
            "required_permissions": list(self.required_permissions),
            "risk_level": self.risk_level.value,
            "reversible": self.reversible,
            "requires_approval": self.requires_approval,
            "validation_policy_id": self.validation_policy_id,
            "rollback_policy_id": self.rollback_policy_id,
            "enabled": self.enabled,
            "metadata": _thaw(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> DomainOperationDefinition:
        if not isinstance(data, Mapping):
            raise DomainOperationSerializationError(
                "DomainOperationDefinition.from_dict requires a mapping"
            )
        _reject_unknown(data, _DEFINITION_FIELDS, "DomainOperationDefinition")
        try:
            return cls(**dict(data))
        except KeyError as exc:
            raise DomainOperationSerializationError(
                "DomainOperationDefinition is missing required fields"
            ) from exc

    def to_operation_descriptor(self) -> OperationDescriptor:
        effect = {
            DomainOperationType.READ: OperationEffectType.READ,
            DomainOperationType.MEMORY: OperationEffectType.MEMORY_WRITE,
            DomainOperationType.EXTERNAL: OperationEffectType.EXTERNAL_CALL,
            DomainOperationType.DESTRUCTIVE: OperationEffectType.DELETE,
        }.get(self.operation_type, OperationEffectType.EXECUTE)
        return OperationDescriptor(
            name=self.operation_id,
            description=self.description,
            version=self.version,
            input_schema=self.input_schema,
            output_schema=self.output_schema,
            effects=(effect,),
            reversible=self.reversible,
            rollback_operation_name=self.rollback_policy_id,
            risks=(self.risk_level.value,),
            required_permissions=self.required_permissions,
            sensitivity="sensitive"
            if self.operation_type is DomainOperationType.SENSITIVE
            else "internal",
            validations=(self.validation_policy_id,)
            if self.validation_policy_id
            else (),
            enabled=self.enabled,
            metadata={
                "domain_id": self.domain_id,
                "operation_type": self.operation_type.value,
                **_thaw(self.metadata),
            },
        )


_REQUEST_FIELDS = frozenset(
    {
        "request_id",
        "operation_id",
        "operation_version",
        "inputs",
        "agent_run_id",
        "workflow_id",
        "task_id",
        "session_id",
        "primary_domain_id",
        "supporting_domain_ids",
        "granted_permissions",
        "denied_permissions",
        "available_resources",
        "capabilities",
        "approval_request_id",
        "idempotency_key",
        "created_at",
        "metadata",
    }
)


@dataclass(frozen=True, slots=True)
class DomainOperationRequest:
    request_id: str
    operation_id: str
    operation_version: str
    inputs: Mapping[str, Any]
    agent_run_id: str
    task_id: str
    primary_domain_id: str
    idempotency_key: str
    workflow_id: str = "domain-operation"
    session_id: str | None = None
    supporting_domain_ids: tuple[str, ...] = ()
    granted_permissions: tuple[str, ...] = ()
    denied_permissions: tuple[str, ...] = ()
    available_resources: tuple[str, ...] = ()
    capabilities: tuple[str, ...] = ()
    approval_request_id: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for attr in (
            "request_id",
            "operation_id",
            "operation_version",
            "agent_run_id",
            "workflow_id",
            "task_id",
            "primary_domain_id",
            "idempotency_key",
        ):
            object.__setattr__(self, attr, _non_empty(getattr(self, attr), attr))
        try:
            parse_semver(self.operation_version)
        except DomainContractValidationError as exc:
            raise DomainOperationContractError(
                "operation_version must be semantic version", field="operation_version"
            ) from exc
        object.__setattr__(self, "inputs", _json_mapping(self.inputs, "inputs"))
        object.__setattr__(
            self, "session_id", _optional_text(self.session_id, "session_id")
        )
        object.__setattr__(
            self,
            "supporting_domain_ids",
            _string_tuple(self.supporting_domain_ids, "supporting_domain_ids"),
        )
        object.__setattr__(
            self,
            "granted_permissions",
            _string_tuple(self.granted_permissions, "granted_permissions"),
        )
        object.__setattr__(
            self,
            "denied_permissions",
            _string_tuple(self.denied_permissions, "denied_permissions"),
        )
        object.__setattr__(
            self,
            "available_resources",
            _string_tuple(self.available_resources, "available_resources"),
        )
        object.__setattr__(
            self, "capabilities", _string_tuple(self.capabilities, "capabilities")
        )
        object.__setattr__(
            self,
            "approval_request_id",
            _optional_text(self.approval_request_id, "approval_request_id"),
        )
        object.__setattr__(self, "created_at", _aware(self.created_at, "created_at"))
        object.__setattr__(self, "metadata", _json_mapping(self.metadata, "metadata"))

    def calculate_fingerprint(self) -> str:
        payload = {
            "operation_id": self.operation_id,
            "operation_version": self.operation_version,
            "inputs": _thaw(self.inputs),
            "agent_run_id": self.agent_run_id,
            "primary_domain_id": self.primary_domain_id,
            "supporting_domain_ids": sorted(self.supporting_domain_ids),
        }
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "operation_id": self.operation_id,
            "operation_version": self.operation_version,
            "inputs": _thaw(self.inputs),
            "agent_run_id": self.agent_run_id,
            "workflow_id": self.workflow_id,
            "task_id": self.task_id,
            "session_id": self.session_id,
            "primary_domain_id": self.primary_domain_id,
            "supporting_domain_ids": list(self.supporting_domain_ids),
            "granted_permissions": list(self.granted_permissions),
            "denied_permissions": list(self.denied_permissions),
            "available_resources": list(self.available_resources),
            "capabilities": list(self.capabilities),
            "approval_request_id": self.approval_request_id,
            "idempotency_key": self.idempotency_key,
            "created_at": self.created_at.isoformat(),
            "metadata": _thaw(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> DomainOperationRequest:
        if not isinstance(data, Mapping):
            raise DomainOperationSerializationError(
                "DomainOperationRequest.from_dict requires a mapping"
            )
        _reject_unknown(data, _REQUEST_FIELDS, "DomainOperationRequest")
        return cls(**dict(data))


_CONTEXT_FIELDS = frozenset(
    {
        "operation_id",
        "operation_version",
        "primary_domain_id",
        "supporting_domain_ids",
        "required_permissions",
        "granted_permissions",
        "denied_permissions",
        "available_resources",
        "profile_id",
        "composition_id",
        "composed_operation_ids",
        "selected_rule_ids",
        "session_id",
        "provenance",
        "metadata",
    }
)


@dataclass(frozen=True, slots=True)
class DomainOperationContext:
    operation_id: str
    operation_version: str
    primary_domain_id: str
    supporting_domain_ids: tuple[str, ...] = ()
    required_permissions: tuple[str, ...] = ()
    granted_permissions: tuple[str, ...] = ()
    denied_permissions: tuple[str, ...] = ()
    available_resources: tuple[str, ...] = ()
    profile_id: str | None = None
    composition_id: str | None = None
    composed_operation_ids: tuple[str, ...] = ()
    selected_rule_ids: tuple[str, ...] = ()
    session_id: str | None = None
    provenance: Mapping[str, Any] = field(default_factory=dict)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for attr in ("operation_id", "operation_version", "primary_domain_id"):
            object.__setattr__(self, attr, _non_empty(getattr(self, attr), attr))
        try:
            parse_semver(self.operation_version)
        except DomainContractValidationError as exc:
            raise DomainOperationContractError(
                "operation_version must be semantic version", field="operation_version"
            ) from exc
        for attr in (
            "supporting_domain_ids",
            "required_permissions",
            "granted_permissions",
            "denied_permissions",
            "available_resources",
            "composed_operation_ids",
            "selected_rule_ids",
        ):
            object.__setattr__(self, attr, _string_tuple(getattr(self, attr), attr))
        object.__setattr__(
            self, "profile_id", _optional_text(self.profile_id, "profile_id")
        )
        object.__setattr__(
            self,
            "composition_id",
            _optional_text(self.composition_id, "composition_id"),
        )
        object.__setattr__(
            self, "session_id", _optional_text(self.session_id, "session_id")
        )
        object.__setattr__(
            self, "provenance", _json_mapping(self.provenance, "provenance")
        )
        object.__setattr__(self, "metadata", _json_mapping(self.metadata, "metadata"))

    @classmethod
    def from_effective(
        cls,
        request: DomainOperationRequest,
        *,
        resolved_profile: Any | None = None,
        composition: Any | None = None,
        selected_rule_ids: tuple[str, ...] = (),
    ) -> DomainOperationContext:
        primary = request.primary_domain_id
        supporting = request.supporting_domain_ids
        granted = list(request.granted_permissions)
        denied = list(request.denied_permissions)
        required: list[str] = []
        profile_id: str | None = None
        composition_id: str | None = None
        composed_operations: tuple[str, ...] = ()
        provenance: dict[str, Any] = {}

        if resolved_profile is not None:
            profile_primary = str(resolved_profile.primary_domain)
            profile_supporting = tuple(
                str(item) for item in resolved_profile.supporting_domains
            )
            if profile_primary != primary or profile_supporting != supporting:
                raise DomainOperationContractError(
                    "resolved profile domain context does not match request"
                )
            profile_id = resolved_profile.id
            for permission in resolved_profile.permissions or ():
                if permission not in granted:
                    granted.append(permission)
            provenance["profile_trace_id"] = resolved_profile.trace_id

        if composition is not None:
            composition_primary = str(composition.primary_domain)
            composition_supporting = tuple(
                str(item) for item in composition.supporting_domains
            )
            if composition_primary != primary or composition_supporting != supporting:
                raise DomainOperationContractError(
                    "composition domain context does not match request"
                )
            composition_id = composition.id
            composed_operations = tuple(
                item.identifier for item in composition.operations
            )
            provenance["operations"] = {
                item.identifier: item.to_dict() for item in composition.operations
            }
            if composition.permissions is not None:
                required.extend(composition.permissions.required_permissions)
                for permission in composition.permissions.granted_permissions:
                    if permission not in granted:
                        granted.append(permission)
                for permission in composition.permissions.denied_permissions:
                    if permission not in denied:
                        denied.append(permission)
                provenance.update(_thaw(composition.permissions.provenance))

        return cls(
            operation_id=request.operation_id,
            operation_version=request.operation_version,
            primary_domain_id=primary,
            supporting_domain_ids=supporting,
            required_permissions=tuple(required),
            granted_permissions=tuple(granted),
            denied_permissions=tuple(denied),
            available_resources=request.available_resources,
            profile_id=profile_id,
            composition_id=composition_id,
            composed_operation_ids=composed_operations,
            selected_rule_ids=selected_rule_ids,
            session_id=request.session_id,
            provenance=provenance,
            metadata={"request_id": request.request_id},
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "operation_id": self.operation_id,
            "operation_version": self.operation_version,
            "primary_domain_id": self.primary_domain_id,
            "supporting_domain_ids": list(self.supporting_domain_ids),
            "required_permissions": list(self.required_permissions),
            "granted_permissions": list(self.granted_permissions),
            "denied_permissions": list(self.denied_permissions),
            "available_resources": list(self.available_resources),
            "profile_id": self.profile_id,
            "composition_id": self.composition_id,
            "composed_operation_ids": list(self.composed_operation_ids),
            "selected_rule_ids": list(self.selected_rule_ids),
            "session_id": self.session_id,
            "provenance": _thaw(self.provenance),
            "metadata": _thaw(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> DomainOperationContext:
        if not isinstance(data, Mapping):
            raise DomainOperationSerializationError(
                "DomainOperationContext.from_dict requires a mapping"
            )
        _reject_unknown(data, _CONTEXT_FIELDS, "DomainOperationContext")
        return cls(**dict(data))


@dataclass(frozen=True, slots=True)
class DomainOperationTraceEntry:
    code: str
    status: DomainOperationStatus
    occurred_at: datetime
    reason_code: str
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "code", _non_empty(self.code, "code"))
        object.__setattr__(
            self, "status", _enum(self.status, DomainOperationStatus, "status")
        )
        object.__setattr__(self, "occurred_at", _aware(self.occurred_at, "occurred_at"))
        object.__setattr__(
            self, "reason_code", _non_empty(self.reason_code, "reason_code")
        )
        object.__setattr__(self, "metadata", _json_mapping(self.metadata, "metadata"))

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "status": self.status.value,
            "occurred_at": self.occurred_at.isoformat(),
            "reason_code": self.reason_code,
            "metadata": _thaw(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> DomainOperationTraceEntry:
        _reject_unknown(
            data,
            frozenset({"code", "status", "occurred_at", "reason_code", "metadata"}),
            "DomainOperationTraceEntry",
        )
        return cls(**dict(data))


@dataclass(frozen=True, slots=True)
class DomainOperationRollbackResult:
    attempted: bool
    succeeded: bool
    policy_id: str | None
    error: Mapping[str, Any] | None

    def __post_init__(self) -> None:
        object.__setattr__(self, "attempted", _strict_bool(self.attempted, "attempted"))
        object.__setattr__(self, "succeeded", _strict_bool(self.succeeded, "succeeded"))
        if self.succeeded and not self.attempted:
            raise DomainOperationContractError(
                "rollback cannot succeed when not attempted"
            )
        if self.attempted and not self.succeeded and self.error is None:
            raise DomainOperationContractError(
                "a failed rollback requires a structured error", field="error"
            )
        if self.succeeded and self.error is not None:
            raise DomainOperationContractError(
                "a successful rollback cannot contain an error", field="error"
            )
        object.__setattr__(
            self, "policy_id", _optional_text(self.policy_id, "policy_id")
        )
        if self.error is not None:
            object.__setattr__(self, "error", _json_mapping(self.error, "error"))

    def to_dict(self) -> dict[str, Any]:
        return {
            "attempted": self.attempted,
            "succeeded": self.succeeded,
            "policy_id": self.policy_id,
            "error": _thaw(self.error) if self.error is not None else None,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> DomainOperationRollbackResult:
        _reject_unknown(
            data,
            frozenset({"attempted", "succeeded", "policy_id", "error"}),
            "DomainOperationRollbackResult",
        )
        return cls(**dict(data))


_RESULT_FIELDS = frozenset(
    {
        "result_id",
        "request_id",
        "operation_id",
        "operation_version",
        "domain_id",
        "status",
        "output",
        "findings",
        "produced_knowledge",
        "memory_proposals",
        "validation_results",
        "transaction_id",
        "approval_request_id",
        "rollback_result",
        "started_at",
        "completed_at",
        "events",
        "trace_entries",
        "error",
        "metadata",
    }
)


@dataclass(frozen=True, slots=True)
class DomainOperationResult:
    result_id: str
    request_id: str
    operation_id: str
    operation_version: str
    domain_id: str
    status: DomainOperationStatus
    output: Mapping[str, Any] = field(default_factory=dict)
    findings: tuple[Mapping[str, Any], ...] = ()
    produced_knowledge: tuple[Mapping[str, Any], ...] = ()
    memory_proposals: tuple[Mapping[str, Any], ...] = ()
    validation_results: tuple[Mapping[str, Any], ...] = ()
    transaction_id: str | None = None
    approval_request_id: str | None = None
    rollback_result: DomainOperationRollbackResult | None = None
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    events: tuple[Mapping[str, Any], ...] = ()
    trace_entries: tuple[DomainOperationTraceEntry, ...] = ()
    error: Mapping[str, Any] | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for attr in (
            "result_id",
            "request_id",
            "operation_id",
            "operation_version",
            "domain_id",
        ):
            object.__setattr__(self, attr, _non_empty(getattr(self, attr), attr))
        try:
            parse_semver(self.operation_version)
        except DomainContractValidationError as exc:
            raise DomainOperationContractError(
                "operation_version must be semantic version", field="operation_version"
            ) from exc
        object.__setattr__(
            self, "status", _enum(self.status, DomainOperationStatus, "status")
        )
        object.__setattr__(self, "output", _json_mapping(self.output, "output"))
        for attr in (
            "findings",
            "produced_knowledge",
            "memory_proposals",
            "validation_results",
            "events",
        ):
            value = getattr(self, attr)
            if not isinstance(value, (tuple, list)):
                raise DomainOperationContractError(
                    f"{attr} must be a sequence", field=attr
                )
            object.__setattr__(
                self,
                attr,
                tuple(
                    _json_mapping(item, f"{attr}[{index}]")
                    for index, item in enumerate(value)
                ),
            )
        object.__setattr__(
            self,
            "transaction_id",
            _optional_text(self.transaction_id, "transaction_id"),
        )
        object.__setattr__(
            self,
            "approval_request_id",
            _optional_text(self.approval_request_id, "approval_request_id"),
        )
        if self.rollback_result is not None and not isinstance(
            self.rollback_result, DomainOperationRollbackResult
        ):
            raise DomainOperationContractError(
                "rollback_result has invalid type", field="rollback_result"
            )
        started = _aware(self.started_at, "started_at")
        completed = _aware(self.completed_at, "completed_at")
        if completed < started:
            raise DomainOperationContractError(
                "completed_at cannot be before started_at", field="completed_at"
            )
        object.__setattr__(self, "started_at", started)
        object.__setattr__(self, "completed_at", completed)
        if not isinstance(self.trace_entries, (tuple, list)) or any(
            not isinstance(item, DomainOperationTraceEntry)
            for item in self.trace_entries
        ):
            raise DomainOperationContractError(
                "trace_entries has invalid type", field="trace_entries"
            )
        object.__setattr__(self, "trace_entries", tuple(self.trace_entries))
        if self.error is not None:
            object.__setattr__(self, "error", _json_mapping(self.error, "error"))
        object.__setattr__(self, "metadata", _json_mapping(self.metadata, "metadata"))

        non_executed = frozenset(
            {
                DomainOperationStatus.REGISTERED,
                DomainOperationStatus.AVAILABLE,
                DomainOperationStatus.UNAVAILABLE,
                DomainOperationStatus.BLOCKED,
                DomainOperationStatus.WAITING_FOR_APPROVAL,
            }
        )
        if self.status is DomainOperationStatus.COMPLETED and (
            self.error is not None or self.rollback_result is not None
        ):
            raise DomainOperationContractError(
                "completed results cannot contain error or rollback_result"
            )
        if self.status is DomainOperationStatus.FAILED:
            if self.error is None or not self.error.get("code"):
                raise DomainOperationContractError(
                    "failed results require a structured error", field="error"
                )
            if self.rollback_result is not None and self.rollback_result.succeeded:
                raise DomainOperationContractError(
                    "a failed result cannot contain a successful rollback"
                )
        if self.status is DomainOperationStatus.ROLLED_BACK and (
            self.rollback_result is None
            or not self.rollback_result.attempted
            or not self.rollback_result.succeeded
        ):
            raise DomainOperationContractError(
                "rolled_back results require a successful attempted rollback",
                field="rollback_result",
            )
        if (
            self.rollback_result is not None
            and self.rollback_result.attempted
            and not self.rollback_result.succeeded
            and self.status is not DomainOperationStatus.FAILED
        ):
            raise DomainOperationContractError(
                "a failed rollback is only compatible with failed results"
            )
        if self.status is DomainOperationStatus.WAITING_FOR_APPROVAL and not (
            self.approval_request_id
            or any(
                key in self.metadata
                for key in ("approval", "approval_evidence", "availability")
            )
        ):
            raise DomainOperationContractError(
                "waiting_for_approval requires approval evidence",
                field="approval_request_id",
            )
        if self.status in non_executed:
            if self.transaction_id is not None or self.rollback_result is not None:
                raise DomainOperationContractError(
                    "non-executed results cannot contain transaction or rollback state"
                )
            if (
                self.output
                or self.findings
                or self.produced_knowledge
                or self.memory_proposals
                or self.validation_results
            ):
                raise DomainOperationContractError(
                    "non-executed results cannot contain execution payloads"
                )

    def to_dict(self) -> dict[str, Any]:
        return {
            "result_id": self.result_id,
            "request_id": self.request_id,
            "operation_id": self.operation_id,
            "operation_version": self.operation_version,
            "domain_id": self.domain_id,
            "status": self.status.value,
            "output": _thaw(self.output),
            "findings": [_thaw(item) for item in self.findings],
            "produced_knowledge": [_thaw(item) for item in self.produced_knowledge],
            "memory_proposals": [_thaw(item) for item in self.memory_proposals],
            "validation_results": [_thaw(item) for item in self.validation_results],
            "transaction_id": self.transaction_id,
            "approval_request_id": self.approval_request_id,
            "rollback_result": self.rollback_result.to_dict()
            if self.rollback_result
            else None,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat(),
            "events": [_thaw(item) for item in self.events],
            "trace_entries": [item.to_dict() for item in self.trace_entries],
            "error": _thaw(self.error) if self.error is not None else None,
            "metadata": _thaw(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> DomainOperationResult:
        if not isinstance(data, Mapping):
            raise DomainOperationSerializationError(
                "DomainOperationResult.from_dict requires a mapping"
            )
        _reject_unknown(data, _RESULT_FIELDS, "DomainOperationResult")
        values = dict(data)
        values["trace_entries"] = tuple(
            DomainOperationTraceEntry.from_dict(item)
            for item in values.get("trace_entries", ())
        )
        if values.get("rollback_result") is not None:
            values["rollback_result"] = DomainOperationRollbackResult.from_dict(
                values["rollback_result"]
            )
        return cls(**values)


__all__ = [
    "DomainOperationContext",
    "DomainOperationDefinition",
    "DomainOperationRequest",
    "DomainOperationResult",
    "DomainOperationRollbackResult",
    "DomainOperationTraceEntry",
    "validate_domain_operation_transition",
]
