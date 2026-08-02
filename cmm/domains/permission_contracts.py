"""Immutable domain-specific permission contracts for Phase 10.15."""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from cmm.agent_runtime.agent_security_enums import SensitivityLevel
from cmm.agent_runtime.domain_permission_contracts import (
    PermissionApprovalRequirement,
    PermissionCapability,
    PermissionOutcome,
    _freeze,
    _thaw,
)
from cmm.agent_runtime.permission_restriction_contracts import (
    ExportPolicy,
    ExportRequest,
    ExternalProviderEgressPolicy,
    ExternalProviderEgressRequest,
    ExternalSourceRequirement,
    ExternalSourceUse,
    PostVerificationRequirement,
)
from cmm.domains.errors import (
    DomainPermissionContractError,
    DomainPermissionSerializationError,
)
from cmm.domains.registry_contracts import parse_semver


def _error(message: str, field_name: str | None = None) -> DomainPermissionContractError:
    return DomainPermissionContractError(message, field=field_name)


def _text(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise _error(f"{name} must be a non-empty string", name)
    return value.strip()


def _strings(value: Any, name: str) -> tuple[str, ...]:
    if value is None or isinstance(value, (str, bytes)):
        raise _error(f"{name} must be a sequence of strings", name)
    result = tuple(_text(item, name) for item in value)
    if len(result) != len(set(result)):
        raise _error(f"{name} must not contain duplicates", name)
    return result


def _optional_strings(value: Any, name: str) -> tuple[str, ...] | None:
    return None if value is None else _strings(value, name)


def _bool(value: Any, name: str) -> bool:
    if not isinstance(value, bool):
        raise _error(f"{name} must be a boolean", name)
    return value


def _json(value: Any, name: str) -> Any:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise _error(f"{name} must contain finite numbers", name)
        return value
    if isinstance(value, Mapping):
        return {str(k): _json(item, f"{name}.{k}") for k, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_json(item, name) for item in value]
    raise _error(f"{name} must be JSON-safe", name)


def _enum(value: Any, enum_type: type[Enum], name: str) -> Any:
    if isinstance(value, enum_type):
        return value
    try:
        return enum_type(value)
    except (TypeError, ValueError) as exc:
        raise _error(f"invalid {name}", name) from exc


def _aware(value: Any, name: str) -> datetime:
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value)
        except ValueError as exc:
            raise _error(f"{name} must be an ISO datetime", name) from exc
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise _error(f"{name} must be timezone-aware", name)
    return value


class CrossDomainDuration(str, Enum):
    SINGLE_USE = "single_use"
    REQUEST = "request"
    WORKFLOW_RUN = "workflow_run"
    SESSION = "session"


@dataclass(frozen=True, slots=True)
class DomainAutonomyLimits:
    maximum_autonomy_level: int | None = None
    maximum_operations: int | None = None
    maximum_workflows: int | None = None
    maximum_iterations: int | None = None
    maximum_questions: int | None = None
    maximum_external_calls: int | None = None
    maximum_duration_seconds: float | None = None
    maximum_cost: float | None = None
    allow_reversible_changes: bool = False
    allow_irreversible_changes: bool = False
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in ("maximum_autonomy_level", "maximum_operations", "maximum_workflows", "maximum_iterations", "maximum_questions", "maximum_external_calls"):
            value = getattr(self, name)
            if value is not None and (isinstance(value, bool) or not isinstance(value, int) or value < 0):
                raise _error(f"{name} must be a non-negative integer or None", name)
        for name in ("maximum_duration_seconds", "maximum_cost"):
            value = getattr(self, name)
            if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0):
                raise _error(f"{name} must be finite and non-negative", name)
        object.__setattr__(self, "allow_reversible_changes", _bool(self.allow_reversible_changes, "allow_reversible_changes"))
        object.__setattr__(self, "allow_irreversible_changes", _bool(self.allow_irreversible_changes, "allow_irreversible_changes"))
        object.__setattr__(self, "metadata", _freeze(_json(self.metadata, "metadata")))

    def to_dict(self) -> dict[str, Any]:
        return {name: _thaw(getattr(self, name)) for name in self.__dataclass_fields__}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> DomainAutonomyLimits:
        known = set(cls.__dataclass_fields__)
        unknown = set(data) - known
        if unknown:
            raise DomainPermissionSerializationError(f"unknown fields: {sorted(unknown)}")
        return cls(**dict(data))


_POLICY_FIELDS = {
    "policy_id", "domain_id", "version", "allowed_resources", "prohibited_resources",
    "allowed_resource_kinds", "prohibited_resource_kinds",
    "allowed_sensitivity_levels", "prohibited_sensitivity_levels", "allowed_operations", "prohibited_operations",
    "allowed_workflows", "prohibited_workflows", "allow_cross_domain_access", "allowed_target_domains",
    "prohibited_target_domains", "allow_sensitive_inference", "allow_memory_read", "allow_memory_write",
    "allow_external_search", "allow_external_models", "allow_external_communication", "allow_file_modification",
    "allow_task_creation", "allow_schedule_modification", "allow_goal_update", "allow_export",
    "allowed_capabilities", "prohibited_capabilities", "approval_capabilities",
    "allow_inbound_cross_domain_access", "allowed_source_domains", "prohibited_source_domains",
    "expires_at", "approval_requirements", "autonomy_limits", "enabled", "metadata",
    "source_requirement", "egress_policy", "export_policy", "post_verification",
}


@dataclass(frozen=True, slots=True)
class DomainPermissionPolicy:
    policy_id: str
    domain_id: str
    version: str
    allowed_resource_kinds: tuple[str, ...] | None = None
    prohibited_resource_kinds: tuple[str, ...] = ()
    allowed_sensitivity_levels: tuple[SensitivityLevel, ...] | None = None
    prohibited_sensitivity_levels: tuple[SensitivityLevel, ...] = ()
    allowed_operations: tuple[str, ...] | None = None
    prohibited_operations: tuple[str, ...] = ()
    allowed_workflows: tuple[str, ...] | None = None
    prohibited_workflows: tuple[str, ...] = ()
    allow_cross_domain_access: bool = False
    allowed_target_domains: tuple[str, ...] | None = None
    prohibited_target_domains: tuple[str, ...] = ()
    allow_sensitive_inference: bool = False
    allow_memory_read: bool = False
    allow_memory_write: bool = False
    allow_external_search: bool = False
    allow_external_models: bool = False
    allow_external_communication: bool = False
    allow_file_modification: bool = False
    allow_task_creation: bool = False
    allow_schedule_modification: bool = False
    allow_goal_update: bool = False
    allow_export: bool = False
    allowed_capabilities: tuple[PermissionCapability, ...] = ()
    prohibited_capabilities: tuple[PermissionCapability, ...] = ()
    approval_capabilities: tuple[PermissionCapability, ...] = ()
    allow_inbound_cross_domain_access: bool = False
    allowed_source_domains: tuple[str, ...] | None = None
    prohibited_source_domains: tuple[str, ...] = ()
    expires_at: datetime | None = None
    approval_requirements: tuple[str, ...] = ()
    autonomy_limits: DomainAutonomyLimits = field(default_factory=DomainAutonomyLimits)
    enabled: bool = True
    metadata: Mapping[str, Any] = field(default_factory=dict)
    allowed_resources: tuple[str, ...] | None = None
    prohibited_resources: tuple[str, ...] = ()
    source_requirement: ExternalSourceRequirement | None = None
    egress_policy: ExternalProviderEgressPolicy | None = None
    export_policy: ExportPolicy | None = None
    post_verification: PostVerificationRequirement | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "policy_id", _text(self.policy_id, "policy_id"))
        object.__setattr__(self, "domain_id", _text(self.domain_id, "domain_id"))
        if not self.domain_id.startswith("domain:"):
            raise _error("domain_id must use domain: prefix", "domain_id")
        object.__setattr__(self, "version", _text(self.version, "version"))
        try:
            parse_semver(self.version)
        except Exception as exc:
            raise _error("version must be valid SemVer", "version") from exc
        for name in ("allowed_resources", "allowed_resource_kinds", "allowed_operations", "allowed_workflows", "allowed_target_domains", "allowed_source_domains"):
            object.__setattr__(self, name, _optional_strings(getattr(self, name), name))
        for name in ("prohibited_resources", "prohibited_resource_kinds", "prohibited_operations", "prohibited_workflows", "prohibited_target_domains", "prohibited_source_domains", "approval_requirements"):
            object.__setattr__(self, name, _strings(getattr(self, name), name))
        for name in ("allowed_sensitivity_levels", "prohibited_sensitivity_levels"):
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(self, name, tuple(_enum(item, SensitivityLevel, name) for item in value))
        for name in ("allowed_capabilities", "prohibited_capabilities", "approval_capabilities"):
            value = tuple(_enum(item, PermissionCapability, name) for item in getattr(self, name))
            if len(set(value)) != len(value):
                raise _error(f"{name} must not contain duplicates", name)
            object.__setattr__(self, name, value)
        for name in _POLICY_FIELDS - {"policy_id", "domain_id", "version", "allowed_resources", "prohibited_resources", "allowed_resource_kinds", "prohibited_resource_kinds", "allowed_sensitivity_levels", "prohibited_sensitivity_levels", "allowed_operations", "prohibited_operations", "allowed_workflows", "prohibited_workflows", "allowed_target_domains", "prohibited_target_domains", "allowed_source_domains", "prohibited_source_domains", "allowed_capabilities", "prohibited_capabilities", "approval_capabilities", "approval_requirements", "autonomy_limits", "metadata", "enabled", "expires_at", "source_requirement", "egress_policy", "export_policy", "post_verification"}:
            object.__setattr__(self, name, _bool(getattr(self, name), name))
        if self.expires_at is not None:
            object.__setattr__(self, "expires_at", _aware(self.expires_at, "expires_at"))
        if not isinstance(self.autonomy_limits, DomainAutonomyLimits):
            raise _error("autonomy_limits must be DomainAutonomyLimits", "autonomy_limits")
        for name, contract_type in (
            ("source_requirement", ExternalSourceRequirement),
            ("egress_policy", ExternalProviderEgressPolicy),
            ("export_policy", ExportPolicy),
            ("post_verification", PostVerificationRequirement),
        ):
            value = getattr(self, name)
            if value is not None and not isinstance(value, contract_type):
                raise _error(f"{name} must be {contract_type.__name__}", name)
        object.__setattr__(self, "enabled", _bool(self.enabled, "enabled"))
        object.__setattr__(self, "metadata", _freeze(_json(self.metadata, "metadata")))

    def to_dict(self) -> dict[str, Any]:
        result = {name: _thaw(getattr(self, name)) for name in _POLICY_FIELDS}
        result["allowed_sensitivity_levels"] = None if self.allowed_sensitivity_levels is None else [v.value for v in self.allowed_sensitivity_levels]
        result["prohibited_sensitivity_levels"] = [v.value for v in self.prohibited_sensitivity_levels]
        for name in ("allowed_capabilities", "prohibited_capabilities", "approval_capabilities"):
            result[name] = [item.value for item in getattr(self, name)]
        result["autonomy_limits"] = self.autonomy_limits.to_dict()
        for name in ("source_requirement", "egress_policy", "export_policy", "post_verification"):
            value = getattr(self, name)
            result[name] = None if value is None else value.to_dict()
        if self.expires_at is not None:
            result["expires_at"] = self.expires_at.isoformat()
        return {key: result[key] for key in sorted(result)}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> DomainPermissionPolicy:
        unknown = set(data) - _POLICY_FIELDS
        if unknown:
            raise DomainPermissionSerializationError(f"unknown fields: {sorted(unknown)}")
        values = dict(data)
        values["autonomy_limits"] = DomainAutonomyLimits.from_dict(values.get("autonomy_limits", {}))
        for name, contract_type in (
            ("source_requirement", ExternalSourceRequirement),
            ("egress_policy", ExternalProviderEgressPolicy),
            ("export_policy", ExportPolicy),
            ("post_verification", PostVerificationRequirement),
        ):
            value = values.get(name)
            if value is not None:
                values[name] = contract_type.from_dict(value)
        return cls(**values)


@dataclass(frozen=True, slots=True)
class DomainPermissionRequest:
    request_id: str
    action: PermissionCapability
    domain_id: str
    actor_id: str
    session_id: str
    resource_id: str | None = None
    resource_kind: str | None = None
    sensitivity_level: SensitivityLevel | None = None
    operation_id: str | None = None
    operation_version: str | None = None
    workflow_id: str | None = None
    workflow_version: str | None = None
    source_domain: str | None = None
    target_domain: str | None = None
    autonomy_level: int | None = None
    context: Mapping[str, Any] = field(default_factory=dict)
    metadata: Mapping[str, Any] = field(default_factory=dict)
    external_domain_trusted: bool = False
    purpose: str | None = None
    source_use: ExternalSourceUse | None = None
    egress_request: ExternalProviderEgressRequest | None = None
    export_request: ExportRequest | None = None

    def __post_init__(self) -> None:
        for name in ("request_id", "domain_id", "actor_id", "session_id"):
            object.__setattr__(self, name, _text(getattr(self, name), name))
        if not self.domain_id.startswith("domain:"):
            raise _error("domain_id must use domain: prefix", "domain_id")
        object.__setattr__(self, "action", _enum(self.action, PermissionCapability, "action"))
        for name in ("resource_id", "resource_kind", "operation_id", "operation_version", "workflow_id", "workflow_version", "source_domain", "target_domain"):
            value = getattr(self, name)
            object.__setattr__(self, name, None if value is None else _text(value, name))
        if self.sensitivity_level is not None:
            object.__setattr__(self, "sensitivity_level", _enum(self.sensitivity_level, SensitivityLevel, "sensitivity_level"))
        if self.autonomy_level is not None and (isinstance(self.autonomy_level, bool) or not isinstance(self.autonomy_level, int) or self.autonomy_level < 0):
            raise _error("autonomy_level must be a non-negative integer", "autonomy_level")
        object.__setattr__(
            self,
            "purpose",
            None if self.purpose is None else _text(self.purpose, "purpose"),
        )
        object.__setattr__(self, "external_domain_trusted", _bool(self.external_domain_trusted, "external_domain_trusted"))
        for name, contract_type in (
            ("source_use", ExternalSourceUse),
            ("egress_request", ExternalProviderEgressRequest),
            ("export_request", ExportRequest),
        ):
            value = getattr(self, name)
            if value is not None and not isinstance(value, contract_type):
                raise _error(f"{name} must be {contract_type.__name__}", name)
        if self.action is PermissionCapability.OPERATION_EXECUTE and self.operation_id is None:
            raise _error("operation.execute requires operation_id", "operation_id")
        if self.action is PermissionCapability.WORKFLOW_EXECUTE and self.workflow_id is None:
            raise _error("workflow.execute requires workflow_id", "workflow_id")
        if self.action is PermissionCapability.DOMAIN_CROSS_ACCESS and (self.source_domain is None or self.target_domain is None or self.source_domain == self.target_domain):
            raise _error("domain.cross_access requires distinct source and target domains", "source_domain")
        if self.action is PermissionCapability.RESOURCE_READ and self.resource_id is None and self.resource_kind is None:
            raise _error("resource.read requires resource_id or resource_kind", "resource_id")
        object.__setattr__(self, "context", _freeze(_json(self.context, "context")))
        object.__setattr__(self, "metadata", _freeze(_json(self.metadata, "metadata")))

    def to_dict(self) -> dict[str, Any]:
        result = {name: _thaw(getattr(self, name)) for name in self.__dataclass_fields__}
        result["action"] = self.action.value
        if self.sensitivity_level is not None:
            result["sensitivity_level"] = self.sensitivity_level.value
        for name in ("source_use", "egress_request", "export_request"):
            value = getattr(self, name)
            result[name] = None if value is None else value.to_dict()
        return result

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> DomainPermissionRequest:
        known = set(cls.__dataclass_fields__)
        unknown = set(data) - known
        if unknown:
            raise DomainPermissionSerializationError(f"unknown fields: {sorted(unknown)}")
        values = dict(data)
        for name, contract_type in (
            ("source_use", ExternalSourceUse),
            ("egress_request", ExternalProviderEgressRequest),
            ("export_request", ExportRequest),
        ):
            value = values.get(name)
            if value is not None:
                values[name] = contract_type.from_dict(value)
        return cls(**values)


@dataclass(frozen=True, slots=True)
class CrossDomainPermissionRequest:
    request_id: str
    source_domain: str
    target_domain: str
    resource_ids: tuple[str, ...] = ()
    requested_operations: tuple[str, ...] = ()
    requested_workflows: tuple[str, ...] = ()
    reason: str = ""
    duration: CrossDomainDuration = CrossDomainDuration.REQUEST
    requires_approval: bool = True
    sensitivity_level: SensitivityLevel | None = None
    actor_id: str = ""
    session_id: str = ""
    expires_at: datetime | None = None
    provenance: Mapping[str, Any] = field(default_factory=dict)
    constraints: Mapping[str, Any] = field(default_factory=dict)
    metadata: Mapping[str, Any] = field(default_factory=dict)
    capability: PermissionCapability = PermissionCapability.DOMAIN_CROSS_ACCESS
    resource_kinds: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name in ("request_id", "source_domain", "target_domain", "reason", "actor_id", "session_id"):
            object.__setattr__(self, name, _text(getattr(self, name), name))
        if not self.source_domain.startswith("domain:") or not self.target_domain.startswith("domain:") or self.source_domain == self.target_domain:
            raise _error("source and target domains must be distinct canonical IDs", "target_domain")
        object.__setattr__(self, "capability", _enum(self.capability, PermissionCapability, "capability"))
        for name in ("resource_ids", "resource_kinds", "requested_operations", "requested_workflows"):
            object.__setattr__(self, name, _strings(getattr(self, name), name))
        if self.capability is PermissionCapability.RESOURCE_READ and not (self.resource_ids or self.resource_kinds):
            raise _error("resource.read requires resource_ids or resource_kinds", "resource_ids")
        if self.capability is PermissionCapability.OPERATION_EXECUTE and not self.requested_operations:
            raise _error("operation.execute requires requested_operations", "requested_operations")
        if self.capability is PermissionCapability.WORKFLOW_EXECUTE and not self.requested_workflows:
            raise _error("workflow.execute requires requested_workflows", "requested_workflows")
        object.__setattr__(self, "duration", _enum(self.duration, CrossDomainDuration, "duration"))
        object.__setattr__(self, "requires_approval", _bool(self.requires_approval, "requires_approval"))
        if self.sensitivity_level is not None:
            object.__setattr__(self, "sensitivity_level", _enum(self.sensitivity_level, SensitivityLevel, "sensitivity_level"))
        if self.expires_at is not None:
            object.__setattr__(self, "expires_at", _aware(self.expires_at, "expires_at"))
        if not isinstance(self.constraints, Mapping):
            raise _error("constraints must be a mapping", "constraints")
        normalized_constraints = dict(self.constraints)
        set_constraints = {
            "allowed_resources", "prohibited_resources",
            "allowed_resource_kinds", "prohibited_resource_kinds",
            "allowed_operations", "prohibited_operations",
            "allowed_workflows", "prohibited_workflows",
            "allowed_target_domains", "prohibited_target_domains",
            "allowed_sensitivity_levels", "prohibited_sensitivity_levels", "scopes",
        }
        for name in set_constraints & set(normalized_constraints):
            normalized_constraints[name] = _strings(normalized_constraints[name], name)
        for name in {"allowed_sensitivity_levels", "prohibited_sensitivity_levels"} & set(normalized_constraints):
            normalized_constraints[name] = tuple(
                _enum(item, SensitivityLevel, name).value
                for item in normalized_constraints[name]
            )
        if "scopes" in normalized_constraints:
            normalized_constraints["scopes"] = tuple(
                _enum(item, CrossDomainDuration, "scopes").value
                for item in normalized_constraints["scopes"]
            )
        for name in ("maximum_operations", "maximum_workflows"):
            if name in normalized_constraints:
                value = normalized_constraints[name]
                if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                    raise _error(f"{name} must be a non-negative integer", name)
        if "expires_at" in normalized_constraints:
            normalized_constraints["expires_at"] = _aware(
                normalized_constraints["expires_at"], "expires_at"
            ).isoformat()
        object.__setattr__(self, "constraints", _freeze(_json(normalized_constraints, "constraints")))
        for name in ("provenance", "metadata"):
            object.__setattr__(self, name, _freeze(_json(getattr(self, name), name)))

    def to_dict(self) -> dict[str, Any]:
        result = {name: _thaw(getattr(self, name)) for name in self.__dataclass_fields__}
        result["capability"] = self.capability.value
        result["duration"] = self.duration.value
        if self.sensitivity_level is not None:
            result["sensitivity_level"] = self.sensitivity_level.value
        if self.expires_at is not None:
            result["expires_at"] = self.expires_at.isoformat()
        return result

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> CrossDomainPermissionRequest:
        known = set(cls.__dataclass_fields__)
        unknown = set(data) - known
        if unknown:
            raise DomainPermissionSerializationError(f"unknown fields: {sorted(unknown)}")
        return cls(**dict(data))


@dataclass(frozen=True, slots=True)
class CrossDomainPermissionDecision:
    request_id: str
    decision: PermissionOutcome
    granted_resources: tuple[str, ...] = ()
    granted_operations: tuple[str, ...] = ()
    granted_workflows: tuple[str, ...] = ()
    constraints: Mapping[str, Any] = field(default_factory=dict)
    approval_requirements: tuple[PermissionApprovalRequirement, ...] = ()
    reasons: tuple[str, ...] = ()
    trace_entries: tuple[Mapping[str, Any], ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "request_id", _text(self.request_id, "request_id"))
        object.__setattr__(self, "decision", _enum(self.decision, PermissionOutcome, "decision"))
        for name in ("granted_resources", "granted_operations", "granted_workflows", "reasons"):
            object.__setattr__(self, name, _strings(getattr(self, name), name))
        requirements = tuple(self.approval_requirements)
        if not all(isinstance(item, PermissionApprovalRequirement) for item in requirements):
            raise _error("approval_requirements must contain PermissionApprovalRequirement values", "approval_requirements")
        if len({item.requirement_id for item in requirements}) != len(requirements):
            raise _error("approval_requirements must not contain duplicate IDs", "approval_requirements")
        object.__setattr__(self, "approval_requirements", requirements)
        if self.decision is PermissionOutcome.APPROVAL_REQUIRED and not self.approval_requirements:
            raise _error("approval_required requires approval_requirements", "approval_requirements")
        object.__setattr__(self, "constraints", _freeze(_json(self.constraints, "constraints")))
        object.__setattr__(self, "trace_entries", tuple(_freeze(_json(item, "trace_entries")) for item in self.trace_entries))
        object.__setattr__(self, "metadata", _freeze(_json(self.metadata, "metadata")))

    def to_dict(self) -> dict[str, Any]:
        result = {name: _thaw(getattr(self, name)) for name in self.__dataclass_fields__}
        result["decision"] = self.decision.value
        result["approval_requirements"] = [item.to_dict() for item in self.approval_requirements]
        return result


@dataclass(frozen=True, slots=True)
class DomainPermissionConflict:
    action: PermissionCapability
    allowing_sources: tuple[str, ...] = ()
    denying_sources: tuple[str, ...] = ()
    approval_sources: tuple[str, ...] = ()
    resolution: PermissionOutcome = PermissionOutcome.DENY
    reason_code: str = "conflict"
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "action", _enum(self.action, PermissionCapability, "action"))
        for name in ("allowing_sources", "denying_sources", "approval_sources"):
            object.__setattr__(self, name, _strings(getattr(self, name), name))
        object.__setattr__(self, "resolution", _enum(self.resolution, PermissionOutcome, "resolution"))
        if self.resolution not in (PermissionOutcome.DENY, PermissionOutcome.APPROVAL_REQUIRED):
            raise _error("conflict resolution must be deny or approval_required", "resolution")
        object.__setattr__(self, "reason_code", _text(self.reason_code, "reason_code"))
        object.__setattr__(self, "metadata", _freeze(_json(self.metadata, "metadata")))

    def to_dict(self) -> dict[str, Any]:
        result = {name: _thaw(getattr(self, name)) for name in self.__dataclass_fields__}
        result["action"] = self.action.value
        result["resolution"] = self.resolution.value
        return result


__all__ = [
    "CrossDomainDuration", "CrossDomainPermissionDecision", "CrossDomainPermissionRequest",
    "DomainAutonomyLimits", "DomainPermissionConflict", "DomainPermissionPolicy", "DomainPermissionRequest",
    "PermissionCapability", "PermissionOutcome", "SensitivityLevel",
]
