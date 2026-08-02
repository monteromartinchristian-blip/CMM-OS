"""Common, domain-agnostic permission contracts for Phase 10.15."""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from types import MappingProxyType
from typing import Any

from .agent_security_enums import SensitivityLevel
from .permission_restriction_contracts import (
    ExportRequest,
    ExternalProviderEgressRequest,
    ExternalSourceUse,
    PostVerificationRequirement,
)


class PermissionCapability(str, Enum):
    RESOURCE_READ = "resource.read"
    KNOWLEDGE_READ = "knowledge.read"
    ENTITY_READ = "entity.read"
    RELATIONSHIP_READ = "relationship.read"
    MEMORY_READ = "memory.read"
    MEMORY_WRITE = "memory.write"
    SENSITIVE_INFERENCE = "inference.sensitive"
    SEARCH_EXTERNAL = "search.external"
    MODEL_EXTERNAL = "model.external"
    OPERATION_EXECUTE = "operation.execute"
    WORKFLOW_EXECUTE = "workflow.execute"
    COMMUNICATION_EXTERNAL = "communication.external"
    PUBLICATION = "publication"
    FILE_MODIFY = "file.modify"
    TASK_CREATE = "task.create"
    SCHEDULE_MODIFY = "schedule.modify"
    GOAL_UPDATE = "goal.update"
    EXPORT = "export"
    DOMAIN_CROSS_ACCESS = "domain.cross_access"
    KNOWLEDGE_DELETE = "knowledge.delete"
    PERMISSION_MODIFY = "permission.modify"
    FINANCIAL_SPEND = "financial.spend"
    MEDICAL_DECISION = "medical.decision"
    MEDICAL_ACTION = "medical.action"
    LEGAL_DECISION = "legal.decision"
    LEGAL_ACTION = "legal.action"
    FINANCIAL_DECISION = "financial.decision"
    FINANCIAL_ACTION = "financial.action"
    SENSITIVE_INFERENCE_PERSIST = "sensitive_inference.persist"
    EXTERNAL_DOMAIN_ACTIVATE = "external_domain.activate"
    IRREVERSIBLE_CHANGE = "irreversible.change"


MANDATORY_APPROVAL_CAPABILITIES = frozenset(
    {
        PermissionCapability.COMMUNICATION_EXTERNAL,
        PermissionCapability.PUBLICATION,
        PermissionCapability.SCHEDULE_MODIFY,
        PermissionCapability.FILE_MODIFY,
        PermissionCapability.IRREVERSIBLE_CHANGE,
        PermissionCapability.KNOWLEDGE_DELETE,
        PermissionCapability.MEDICAL_DECISION,
        PermissionCapability.MEDICAL_ACTION,
        PermissionCapability.LEGAL_DECISION,
        PermissionCapability.LEGAL_ACTION,
        PermissionCapability.FINANCIAL_DECISION,
        PermissionCapability.FINANCIAL_ACTION,
        PermissionCapability.FINANCIAL_SPEND,
        PermissionCapability.PERMISSION_MODIFY,
        PermissionCapability.SENSITIVE_INFERENCE_PERSIST,
    }
)


class PermissionLayer(str, Enum):
    GLOBAL = "global"
    USER = "user"
    SESSION = "session"
    DOMAIN = "domain"
    OPERATION = "operation"
    WORKFLOW = "workflow"
    AUTONOMY = "autonomy"


class PermissionOutcome(str, Enum):
    ALLOW = "allow"
    DENY = "deny"
    ABSTAIN = "abstain"
    APPROVAL_REQUIRED = "approval_required"


@dataclass(frozen=True, slots=True)
class PermissionApprovalRequirement:
    """A context-bound approval obligation, independent from approval storage."""

    requirement_id: str
    action: PermissionCapability
    actor_id: str
    session_id: str
    domain_id: str
    resource_id: str | None = None
    resource_kind: str | None = None
    operation_id: str | None = None
    operation_version: str | None = None
    workflow_id: str | None = None
    workflow_version: str | None = None
    node_id: str | None = None
    source_domain: str | None = None
    target_domain: str | None = None
    fingerprint: str = ""
    expires_at: str | None = None
    scope: str = "request"
    one_time: bool = True
    reusable: bool = False
    reason_code: str = "approval_required"
    risk: str = "medium"
    purpose: str | None = None
    sensitivity: SensitivityLevel | None = None
    constraints: MappingProxyType[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )

    def __post_init__(self) -> None:
        for name in ("requirement_id", "actor_id", "session_id", "domain_id", "fingerprint", "scope", "reason_code", "risk"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be a non-empty string")
            object.__setattr__(self, name, value.strip())
        object.__setattr__(self, "action", _enum(self.action, PermissionCapability, "action"))
        for name in ("resource_id", "resource_kind", "operation_id", "operation_version", "workflow_id", "workflow_version", "node_id", "source_domain", "target_domain", "purpose"):
            value = getattr(self, name)
            if value is not None and (not isinstance(value, str) or not value.strip()):
                raise ValueError(f"{name} must be a non-empty string or None")
            object.__setattr__(self, name, None if value is None else value.strip())
        if self.sensitivity is not None:
            object.__setattr__(
                self,
                "sensitivity",
                _enum(self.sensitivity, SensitivityLevel, "sensitivity"),
            )
        if not isinstance(self.one_time, bool) or not isinstance(self.reusable, bool) or self.one_time == self.reusable:
            raise ValueError("exactly one of one_time and reusable must be true")
        if not isinstance(self.constraints, Mapping):
            raise TypeError("constraints must be a mapping")
        object.__setattr__(self, "constraints", _validate_constraints(self.constraints))
        if self.expires_at is not None:
            try:
                parsed = datetime.fromisoformat(self.expires_at)
            except (TypeError, ValueError) as exc:
                raise ValueError("expires_at must be an ISO timestamp") from exc
            if parsed.tzinfo is None:
                raise ValueError("expires_at must be timezone-aware")
            object.__setattr__(self, "expires_at", parsed.isoformat())

    def to_dict(self) -> dict[str, Any]:
        result = {name: getattr(self, name) for name in self.__dataclass_fields__}
        result["action"] = self.action.value
        result["sensitivity"] = (
            self.sensitivity.value if self.sensitivity is not None else None
        )
        result["constraints"] = _thaw(self.constraints)
        return result

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> PermissionApprovalRequirement:
        unknown = set(data) - set(cls.__dataclass_fields__)
        if unknown:
            raise ValueError(f"unknown fields: {sorted(unknown)}")
        return cls(**dict(data))


@dataclass(frozen=True, slots=True)
class PermissionApprovalGrant:
    """Legacy read-only approval hint.

    ``satisfies`` remains available for compatibility and inspection, but this
    object is never executable authorization evidence.  Only the canonical
    approval service may validate and consume an approval for execution.
    """

    requirement: PermissionApprovalRequirement
    approved_at: str
    expires_at: str | None = None
    consumed: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.requirement, PermissionApprovalRequirement):
            raise TypeError("requirement must be PermissionApprovalRequirement")
        for name in ("approved_at", "expires_at"):
            value = getattr(self, name)
            if value is None:
                continue
            try:
                parsed = datetime.fromisoformat(value)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"{name} must be an ISO timestamp") from exc
            if parsed.tzinfo is None:
                raise ValueError(f"{name} must be timezone-aware")
            object.__setattr__(self, name, parsed.isoformat())
        if not isinstance(self.consumed, bool):
            raise TypeError("consumed must be a boolean")

    def satisfies(self, requirement: PermissionApprovalRequirement, *, now: datetime) -> bool:
        if now.tzinfo is None:
            raise ValueError("now must be timezone-aware")
        if self.consumed and self.requirement.one_time:
            return False
        if self.expires_at is not None and now >= datetime.fromisoformat(self.expires_at):
            return False
        if requirement.expires_at is not None and now >= datetime.fromisoformat(requirement.expires_at):
            return False
        return self.requirement == requirement


_LAYER_PRECEDENCE = {
    PermissionLayer.GLOBAL: 0,
    PermissionLayer.USER: 1,
    PermissionLayer.SESSION: 2,
    PermissionLayer.DOMAIN: 3,
    PermissionLayer.OPERATION: 4,
    PermissionLayer.WORKFLOW: 5,
    PermissionLayer.AUTONOMY: 6,
}
_PERMISSIVE_BOOLEAN_CONSTRAINTS = frozenset(
    {
        "allow_external_access",
        "allow_memory_write",
        "allow_sensitive_inference",
        "allow_reversible_changes",
        "allow_irreversible_changes",
        "allow_export",
    }
)
_SET_INTERSECTION_CONSTRAINTS = frozenset(
    {
        "allowed_resources",
        "allowed_resource_kinds",
        "allowed_operations",
        "allowed_workflows",
        "allowed_target_domains",
        "allowed_sensitivity_levels",
        "scopes",
    }
)
_SET_UNION_CONSTRAINTS = frozenset(
    {
        "prohibited_resources",
        "prohibited_resource_kinds",
        "prohibited_operations",
        "prohibited_workflows",
        "prohibited_target_domains",
        "prohibited_sensitivity_levels",
    }
)


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({str(k): _freeze(v) for k, v in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(v) for v in value)
    if isinstance(value, (set, frozenset)):
        return frozenset(_freeze(v) for v in value)
    return value


def _thaw(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {k: _thaw(v) for k, v in value.items()}
    if isinstance(value, tuple):
        return [_thaw(v) for v in value]
    if isinstance(value, frozenset):
        return sorted((_thaw(v) for v in value), key=str)
    return value


def _json_safe(value: Any, path: str = "value") -> None:
    if value is None or isinstance(value, (str, bool, int)):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"{path} must be finite")
        return
    if isinstance(value, Mapping):
        for key, item in value.items():
            if not isinstance(key, str):
                raise TypeError(f"{path} keys must be strings")
            _json_safe(item, f"{path}.{key}")
        return
    if isinstance(value, (tuple, list, frozenset)):
        for item in value:
            _json_safe(item, path)
        return
    raise ValueError(f"{path} must be JSON-safe")


def _unique_strings(value: Any, field_name: str) -> tuple[str, ...]:
    if isinstance(value, (str, bytes)) or value is None:
        raise ValueError(f"{field_name} must be a sequence")
    result = tuple(value)
    if any(not isinstance(item, str) or not item.strip() for item in result):
        raise ValueError(f"{field_name} must contain non-empty strings")
    if len(set(result)) != len(result):
        raise ValueError(f"{field_name} must not contain duplicates")
    return result


def _enum(value: Any, enum_type: type[Enum], field_name: str) -> Any:
    if isinstance(value, enum_type):
        return value
    if isinstance(value, str):
        try:
            return enum_type(value)
        except ValueError as exc:
            raise ValueError(f"invalid {field_name}") from exc
    raise ValueError(f"{field_name} must be an enum value")


def _constraint_values(value: Any, field_name: str) -> tuple[str, ...]:
    if isinstance(value, (str, bytes)) or value is None:
        raise ValueError(f"{field_name} must be a sequence of strings")
    values = tuple(value)
    if any(not isinstance(item, str) or not item.strip() for item in values):
        raise ValueError(f"{field_name} must contain non-empty strings")
    return tuple(sorted(set(values)))


def _validate_constraints(raw: Mapping[str, Any]) -> MappingProxyType[str, Any]:
    normalized: dict[str, Any] = {}
    for key, value in raw.items():
        if not isinstance(key, str):
            raise TypeError("constraint keys must be strings")
        if key in _PERMISSIVE_BOOLEAN_CONSTRAINTS or key.startswith("prohibit_"):
            if not isinstance(value, bool):
                raise ValueError(f"{key} must be a boolean")
        elif key.startswith(("maximum_", "minimum_")):
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
                raise ValueError(f"{key} must be a finite non-negative number")
        elif key in _SET_INTERSECTION_CONSTRAINTS or key in _SET_UNION_CONSTRAINTS:
            value = _constraint_values(value, key)
        elif key == "expires_at":
            if isinstance(value, datetime):
                if value.tzinfo is None:
                    raise ValueError("expires_at must be timezone-aware")
                value = value.isoformat()
            if not isinstance(value, str):
                raise ValueError("expires_at must be an ISO timestamp")
            try:
                parsed = datetime.fromisoformat(value)
            except ValueError as exc:
                raise ValueError("expires_at must be an ISO timestamp") from exc
            if parsed.tzinfo is None:
                raise ValueError("expires_at must be timezone-aware")
            value = parsed.isoformat()
        elif key == "post_verification":
            if isinstance(value, PostVerificationRequirement):
                value = value.to_dict()
            if not isinstance(value, Mapping):
                raise ValueError("post_verification must be a mapping")
            value = PostVerificationRequirement.from_dict(value).to_dict()
        elif key in {"bound_source_use", "bound_egress", "bound_export"}:
            if not isinstance(value, Mapping):
                raise ValueError(f"{key} must be a mapping")
            contract_type = {
                "bound_source_use": ExternalSourceUse,
                "bound_egress": ExternalProviderEgressRequest,
                "bound_export": ExportRequest,
            }[key]
            value = contract_type.from_dict(value).to_dict()
        else:
            raise ValueError(f"unknown constraint: {key}")
        normalized[key] = value
    return _freeze(normalized)


@dataclass(frozen=True, slots=True)
class PermissionLayerEvaluation:
    source: PermissionLayer
    effect: PermissionOutcome
    source_id: str | None = None
    policy_id: str | None = None
    policy_version: str | None = None
    domain_role: str | None = None
    matched_rules: tuple[str, ...] = ()
    reasons: tuple[str, ...] = ()
    approval_requirements: tuple[PermissionApprovalRequirement, ...] = ()
    constraints: Mapping[str, Any] = field(default_factory=dict)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "source", _enum(self.source, PermissionLayer, "source"))
        object.__setattr__(self, "effect", _enum(self.effect, PermissionOutcome, "effect"))
        source_id = self.source.value if self.source_id is None else self.source_id
        if not isinstance(source_id, str) or not source_id.strip():
            raise ValueError("source_id must be a non-empty string")
        object.__setattr__(self, "source_id", source_id.strip())
        for name in ("policy_id", "policy_version", "domain_role"):
            value = getattr(self, name)
            if value is not None and (not isinstance(value, str) or not value.strip()):
                raise ValueError(f"{name} must be a non-empty string or None")
            object.__setattr__(self, name, None if value is None else value.strip())
        for name in ("matched_rules", "reasons"):
            object.__setattr__(self, name, _unique_strings(getattr(self, name), name))
        requirements = tuple(self.approval_requirements)
        if not all(isinstance(item, PermissionApprovalRequirement) for item in requirements):
            raise ValueError("approval_requirements must contain PermissionApprovalRequirement values")
        if len({item.requirement_id for item in requirements}) != len(requirements):
            raise ValueError("approval_requirements must have unique requirement IDs")
        object.__setattr__(self, "approval_requirements", requirements)
        if self.effect is PermissionOutcome.APPROVAL_REQUIRED and not self.approval_requirements:
            raise ValueError("approval_required requires approval_requirements")
        if not isinstance(self.constraints, Mapping) or not isinstance(self.metadata, Mapping):
            raise TypeError("constraints and metadata must be mappings")
        _json_safe(self.constraints, "constraints")
        _json_safe(self.metadata, "metadata")
        object.__setattr__(self, "constraints", _validate_constraints(self.constraints))
        object.__setattr__(self, "metadata", _freeze(dict(self.metadata)))

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source.value,
            "effect": self.effect.value,
            "source_id": self.source_id,
            "policy_id": self.policy_id,
            "policy_version": self.policy_version,
            "domain_role": self.domain_role,
            "matched_rules": list(self.matched_rules),
            "reasons": list(self.reasons),
            "approval_requirements": [item.to_dict() for item in self.approval_requirements],
            "constraints": _thaw(self.constraints),
            "metadata": _thaw(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> PermissionLayerEvaluation:
        known = {"source", "effect", "source_id", "policy_id", "policy_version", "domain_role", "matched_rules", "reasons", "approval_requirements", "constraints", "metadata"}
        unknown = set(data) - known
        if unknown:
            raise ValueError(f"unknown fields: {sorted(unknown)}")
        values = dict(data)
        values["approval_requirements"] = tuple(PermissionApprovalRequirement.from_dict(item) for item in values.get("approval_requirements", ()))
        return cls(**values)


@dataclass(frozen=True, slots=True)
class EffectivePermissionResult:
    request_id: str
    action: PermissionCapability
    decision: PermissionOutcome
    layer_evaluations: tuple[PermissionLayerEvaluation, ...]
    effective_constraints: Mapping[str, Any] = field(default_factory=dict)
    approval_requirements: tuple[PermissionApprovalRequirement, ...] = ()
    denied_by: tuple[str, ...] = ()
    allowed_by: tuple[str, ...] = ()
    unresolved_by: tuple[str, ...] = ()
    reasons: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.request_id.strip():
            raise ValueError("request_id is required")
        object.__setattr__(self, "action", _enum(self.action, PermissionCapability, "action"))
        object.__setattr__(self, "decision", _enum(self.decision, PermissionOutcome, "decision"))
        object.__setattr__(self, "layer_evaluations", tuple(self.layer_evaluations))
        object.__setattr__(self, "effective_constraints", _validate_constraints(self.effective_constraints))
        requirements = tuple(self.approval_requirements)
        if not all(isinstance(item, PermissionApprovalRequirement) for item in requirements):
            raise ValueError("approval_requirements must contain PermissionApprovalRequirement values")
        if len({item.requirement_id for item in requirements}) != len(requirements):
            raise ValueError("approval_requirements must have unique requirement IDs")
        object.__setattr__(self, "approval_requirements", requirements)
        object.__setattr__(self, "reasons", tuple(dict.fromkeys(self.reasons)))
        for name in ("denied_by", "allowed_by", "unresolved_by"):
            object.__setattr__(self, name, _unique_strings(getattr(self, name), name))
        identities = {item.source_id for item in self.layer_evaluations}
        if len(identities) != len(self.layer_evaluations):
            raise ValueError("layer evaluations must have unique source_id values")
        expected_denied = tuple(item.source_id for item in self.layer_evaluations if item.effect is PermissionOutcome.DENY)
        expected_allowed = tuple(item.source_id for item in self.layer_evaluations if item.effect is PermissionOutcome.ALLOW)
        expected_unresolved = tuple(item.source_id for item in self.layer_evaluations if item.effect is PermissionOutcome.ABSTAIN)
        if self.denied_by != expected_denied or self.allowed_by != expected_allowed or self.unresolved_by != expected_unresolved:
            raise ValueError("layer provenance does not match evaluations")
        if self.decision is PermissionOutcome.DENY and not self.denied_by and not self.unresolved_by:
            raise ValueError("deny requires a denying or unresolved layer")
        if self.decision is PermissionOutcome.ALLOW and (self.denied_by or self.unresolved_by or self.approval_requirements):
            raise ValueError("allow cannot have deny, abstain, or approval requirements")
        if self.decision is PermissionOutcome.APPROVAL_REQUIRED and not self.approval_requirements:
            raise ValueError("approval_required requires requirements")

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "action": self.action.value,
            "decision": self.decision.value,
            "layer_evaluations": [item.to_dict() for item in self.layer_evaluations],
            "effective_constraints": _thaw(self.effective_constraints),
            "approval_requirements": [item.to_dict() for item in self.approval_requirements],
            "denied_by": list(self.denied_by),
            "allowed_by": list(self.allowed_by),
            "unresolved_by": list(self.unresolved_by),
            "reasons": list(self.reasons),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> EffectivePermissionResult:
        known = {"request_id", "action", "decision", "layer_evaluations", "effective_constraints", "approval_requirements", "denied_by", "allowed_by", "unresolved_by", "reasons"}
        unknown = set(data) - known
        if unknown:
            raise ValueError(f"unknown fields: {sorted(unknown)}")
        values = dict(data)
        values["layer_evaluations"] = tuple(PermissionLayerEvaluation.from_dict(item) for item in values.get("layer_evaluations", ()))
        values["approval_requirements"] = tuple(PermissionApprovalRequirement.from_dict(item) for item in values.get("approval_requirements", ()))
        return cls(**values)


def _intersect_constraints(evaluations: tuple[PermissionLayerEvaluation, ...]) -> dict[str, Any]:
    values: dict[str, Any] = {}
    for evaluation in evaluations:
        for key, value in evaluation.constraints.items():
            if key.startswith("maximum_"):
                values[key] = min(values[key], value) if key in values else value
            elif key.startswith("minimum_"):
                values[key] = max(values[key], value) if key in values else value
            elif key in _PERMISSIVE_BOOLEAN_CONSTRAINTS:
                values[key] = bool(values[key]) and value if key in values else value
            elif key.startswith("prohibit_"):
                values[key] = bool(values[key]) or value if key in values else value
            elif key in _SET_INTERSECTION_CONSTRAINTS:
                values[key] = tuple(sorted(set(values[key]) & set(value))) if key in values else value
            elif key in _SET_UNION_CONSTRAINTS:
                values[key] = tuple(sorted(set(values[key]) | set(value))) if key in values else value
            elif key == "expires_at":
                values[key] = (
                    min(
                        (values[key], value),
                        key=lambda candidate: datetime.fromisoformat(candidate),
                    )
                    if key in values
                    else value
                )
            elif key == "post_verification":
                incoming = PostVerificationRequirement.from_dict(value)
                if key not in values:
                    values[key] = incoming.to_dict()
                    continue
                current = PostVerificationRequirement.from_dict(values[key])
                manual_verifiers = {
                    item for item in (current.manual_verifier, incoming.manual_verifier) if item
                }
                if len(manual_verifiers) > 1:
                    raise ValueError("conflicting post_verification manual verifiers")
                merged = PostVerificationRequirement(
                    kinds=tuple(dict.fromkeys((*current.kinds, *incoming.kinds))),
                    resource_ids=tuple(dict.fromkeys((*current.resource_ids, *incoming.resource_ids))),
                    comparison_fields=tuple(dict.fromkeys((*current.comparison_fields, *incoming.comparison_fields))),
                    evidence_kinds=tuple(dict.fromkeys((*current.evidence_kinds, *incoming.evidence_kinds))),
                    manual_verifier=next(iter(manual_verifiers), None),
                )
                values[key] = merged.to_dict()
            elif key in {"bound_source_use", "bound_egress", "bound_export"}:
                if key in values and values[key] != value:
                    raise ValueError(f"conflicting exact restriction binding: {key}")
                values[key] = value
            else:
                raise ValueError(f"unknown constraint: {key}")
    return values


def intersect_permission_layers(
    evaluations: tuple[PermissionLayerEvaluation, ...] | list[PermissionLayerEvaluation],
    *,
    request_id: str,
    action: str,
) -> EffectivePermissionResult:
    supplied = tuple(evaluations)
    identities: dict[str, PermissionLayerEvaluation] = {}
    for item in supplied:
        existing = identities.get(item.source_id)
        if existing is not None and existing != item:
            raise ValueError("duplicate source_id has conflicting evaluation")
        identities[item.source_id] = item
    layers = tuple(sorted(identities.values(), key=lambda item: (_LAYER_PRECEDENCE[item.source], item.source_id, item.policy_id or "", item.policy_version or "")))
    denied = tuple(item.source_id for item in layers if item.effect is PermissionOutcome.DENY)
    approvals = tuple({item.requirement_id: item for evaluation in layers for item in evaluation.approval_requirements}.values())
    allowed = tuple(item.source_id for item in layers if item.effect is PermissionOutcome.ALLOW)
    unresolved = tuple(item.source_id for item in layers if item.effect is PermissionOutcome.ABSTAIN)
    reasons = tuple(dict.fromkeys(reason for item in layers for reason in item.reasons))
    if denied:
        decision = PermissionOutcome.DENY
    elif unresolved:
        decision = PermissionOutcome.DENY
        reasons = tuple(dict.fromkeys((*reasons, "no_sufficient_allow")))
    elif approvals:
        decision = PermissionOutcome.APPROVAL_REQUIRED
    else:
        decision = PermissionOutcome.ALLOW if allowed else PermissionOutcome.DENY
        if decision is PermissionOutcome.DENY:
            reasons = tuple(dict.fromkeys((*reasons, "no_sufficient_allow")))
    return EffectivePermissionResult(
        request_id=request_id,
        action=action,
        decision=decision,
        layer_evaluations=layers,
        effective_constraints=_intersect_constraints(layers),
        approval_requirements=approvals,
        denied_by=denied,
        allowed_by=allowed,
        unresolved_by=unresolved,
        reasons=reasons,
    )


__all__ = [
    "MANDATORY_APPROVAL_CAPABILITIES",
    "EffectivePermissionResult",
    "PermissionApprovalGrant",
    "PermissionApprovalRequirement",
    "PermissionCapability",
    "PermissionLayer",
    "PermissionLayerEvaluation",
    "PermissionOutcome",
    "SensitivityLevel",
    "intersect_permission_layers",
]
