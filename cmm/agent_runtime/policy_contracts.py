"""Phase 9.8 – Policy Engine Contracts.

Defines data contracts, condition models, rule structures, policy definitions,
evaluation requests, context models, and evaluation results for policy-based authorization.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from dataclasses import field as dataclass_field
from datetime import datetime, timezone
from typing import Any

from .enums import (
    PolicyCombiningAlgorithm,
    PolicyConditionOperator,
    PolicyDecision,
    PolicyEffect,
    PolicyEvaluationStatus,
    PolicyFailureMode,
    PolicyObligationKind,
    PolicyResourceKind,
    PolicyRiskLevel,
    PolicyScope,
    PolicySeverity,
    PolicySubjectKind,
)
from .errors import InvalidPolicyContractError, PolicyVersionError


def _now_iso() -> str:
    """Return current timestamp in ISO 8601 UTC format."""
    return datetime.now(timezone.utc).isoformat()


def _as_tuple_str(items: Any) -> tuple[str, ...]:
    """Convert an iterable or single item into a tuple of non-empty stripped strings."""
    if items is None:
        return ()
    if isinstance(items, str):
        val = items.strip()
        return (val,) if val else ()
    if isinstance(items, (tuple, list, set)):
        result: list[str] = []
        for item in items:
            val = str(item).strip()
            if val:
                result.append(val)
        return tuple(result)
    val = str(items).strip()
    return (val,) if val else ()


def _as_tuple_enum(items: Any, enum_cls: type) -> tuple[Any, ...]:
    """Convert an iterable or single item into a tuple of enum members."""
    if items is None:
        return ()
    if isinstance(items, enum_cls):
        return (items,)
    if isinstance(items, str):
        try:
            return (enum_cls(items),)
        except ValueError:
            return ()
    if isinstance(items, (tuple, list, set)):
        res: list[Any] = []
        for item in items:
            if isinstance(item, enum_cls):
                res.append(item)
            elif isinstance(item, str):
                try:
                    res.append(enum_cls(item))
                except ValueError:
                    pass
        return tuple(res)
    return ()


# Safe attribute path validator regex: identifiers separated by dots
_FIELD_PATH_REGEX = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*(\.[a-zA-Z_][a-zA-Z0-9_]*)*$")


@dataclass(frozen=True, slots=True)
class PolicySubject:
    """Subject/Actor under policy evaluation."""

    id: str
    kind: PolicySubjectKind = PolicySubjectKind.AGENT
    roles: tuple[str, ...] = ()
    permissions: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = dataclass_field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.id or not self.id.strip():
            raise InvalidPolicyContractError("PolicySubject.id must not be empty.")
        object.__setattr__(self, "id", self.id.strip())
        if not isinstance(self.kind, PolicySubjectKind):
            object.__setattr__(self, "kind", PolicySubjectKind(self.kind))
        object.__setattr__(self, "roles", _as_tuple_str(self.roles))
        object.__setattr__(self, "permissions", _as_tuple_str(self.permissions))
        object.__setattr__(self, "metadata", dict(self.metadata or {}))

    def serialize(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind.value,
            "roles": list(self.roles),
            "permissions": list(self.permissions),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> PolicySubject:
        return cls(
            id=str(data["id"]),
            kind=PolicySubjectKind(data.get("kind", PolicySubjectKind.AGENT.value)),
            roles=_as_tuple_str(data.get("roles")),
            permissions=_as_tuple_str(data.get("permissions")),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass(frozen=True, slots=True)
class PolicyResource:
    """Target resource in a policy check."""

    id: str
    kind: PolicyResourceKind = PolicyResourceKind.OPERATION
    sensitivity: str = "internal"
    path: str | None = None
    owner_id: str | None = None
    metadata: Mapping[str, Any] = dataclass_field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.id or not self.id.strip():
            raise InvalidPolicyContractError("PolicyResource.id must not be empty.")
        object.__setattr__(self, "id", self.id.strip())
        if not isinstance(self.kind, PolicyResourceKind):
            object.__setattr__(self, "kind", PolicyResourceKind(self.kind))
        object.__setattr__(
            self, "sensitivity", str(self.sensitivity or "internal").strip().lower()
        )
        if self.path is not None:
            object.__setattr__(self, "path", str(self.path).strip())
        if self.owner_id is not None:
            object.__setattr__(self, "owner_id", str(self.owner_id).strip())
        object.__setattr__(self, "metadata", dict(self.metadata or {}))

    def serialize(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind.value,
            "sensitivity": self.sensitivity,
            "path": self.path,
            "owner_id": self.owner_id,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> PolicyResource:
        return cls(
            id=str(data["id"]),
            kind=PolicyResourceKind(
                data.get("kind", PolicyResourceKind.OPERATION.value)
            ),
            sensitivity=str(data.get("sensitivity", "internal")),
            path=data.get("path"),
            owner_id=data.get("owner_id"),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass(frozen=True, slots=True)
class PolicyAction:
    """Action or operation being attempted."""

    name: str
    operation_name: str | None = None
    parameters: Mapping[str, Any] = dataclass_field(default_factory=dict)
    is_mutation: bool = False
    is_reversible: bool = True
    metadata: Mapping[str, Any] = dataclass_field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.name or not self.name.strip():
            raise InvalidPolicyContractError("PolicyAction.name must not be empty.")
        object.__setattr__(self, "name", self.name.strip())
        if self.operation_name is not None:
            object.__setattr__(self, "operation_name", str(self.operation_name).strip())
        object.__setattr__(self, "parameters", dict(self.parameters or {}))
        object.__setattr__(self, "metadata", dict(self.metadata or {}))

    def serialize(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "operation_name": self.operation_name,
            "parameters": dict(self.parameters),
            "is_mutation": self.is_mutation,
            "is_reversible": self.is_reversible,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> PolicyAction:
        return cls(
            name=str(data["name"]),
            operation_name=data.get("operation_name"),
            parameters=dict(data.get("parameters", {})),
            is_mutation=bool(data.get("is_mutation", False)),
            is_reversible=bool(data.get("is_reversible", True)),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass(frozen=True, slots=True)
class PolicyEnvironment:
    """Environmental context during policy check."""

    name: str = "development"
    is_production: bool = False
    ip_address: str | None = None
    timestamp: str = dataclass_field(default_factory=_now_iso)
    metadata: Mapping[str, Any] = dataclass_field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.name or not self.name.strip():
            raise InvalidPolicyContractError(
                "PolicyEnvironment.name must not be empty."
            )
        object.__setattr__(self, "name", self.name.strip().lower())
        if self.ip_address is not None:
            object.__setattr__(self, "ip_address", str(self.ip_address).strip())
        object.__setattr__(self, "timestamp", str(self.timestamp or _now_iso()))
        object.__setattr__(self, "metadata", dict(self.metadata or {}))

    def serialize(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "is_production": self.is_production,
            "ip_address": self.ip_address,
            "timestamp": self.timestamp,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> PolicyEnvironment:
        return cls(
            name=str(data.get("name", "development")),
            is_production=bool(data.get("is_production", False)),
            ip_address=data.get("ip_address"),
            timestamp=str(data.get("timestamp") or _now_iso()),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass(frozen=True, slots=True)
class PolicyCondition:
    """Structured condition evaluated against request/context attributes without eval or code execution."""

    field: str
    operator: PolicyConditionOperator
    value: Any
    case_sensitive: bool = True
    negate: bool = False
    metadata: Mapping[str, Any] = dataclass_field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.field or not self.field.strip():
            raise InvalidPolicyContractError("PolicyCondition.field must not be empty.")
        f_clean = self.field.strip()
        # Security invariant: Reject private attributes, method calls, or dynamic code attempts
        if (
            any(part.startswith("_") for part in f_clean.split("."))
            or "(" in f_clean
            or ")" in f_clean
            or " " in f_clean
        ):
            raise InvalidPolicyContractError(
                f"PolicyCondition.field contains invalid path or private attribute access: {f_clean}"
            )
        if not _FIELD_PATH_REGEX.match(f_clean):
            raise InvalidPolicyContractError(
                f"PolicyCondition.field path format invalid: {f_clean}"
            )
        object.__setattr__(self, "field", f_clean)
        if not isinstance(self.operator, PolicyConditionOperator):
            object.__setattr__(self, "operator", PolicyConditionOperator(self.operator))
        object.__setattr__(self, "metadata", dict(self.metadata or {}))

    def serialize(self) -> dict[str, Any]:
        return {
            "field": self.field,
            "operator": self.operator.value,
            "value": self.value,
            "case_sensitive": self.case_sensitive,
            "negate": self.negate,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> PolicyCondition:
        return cls(
            field=str(data["field"]),
            operator=PolicyConditionOperator(data["operator"]),
            value=data.get("value"),
            case_sensitive=bool(data.get("case_sensitive", True)),
            negate=bool(data.get("negate", False)),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass(frozen=True, slots=True)
class PolicyTarget:
    """Target matching specifications for a policy."""

    scopes: tuple[PolicyScope, ...] = (PolicyScope.GLOBAL,)
    subject_kinds: tuple[PolicySubjectKind, ...] = ()
    resource_kinds: tuple[PolicyResourceKind, ...] = ()
    action_names: tuple[str, ...] = ()
    conditions: tuple[PolicyCondition, ...] = ()
    metadata: Mapping[str, Any] = dataclass_field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "scopes", _as_tuple_enum(self.scopes, PolicyScope))
        object.__setattr__(
            self, "subject_kinds", _as_tuple_enum(self.subject_kinds, PolicySubjectKind)
        )
        object.__setattr__(
            self,
            "resource_kinds",
            _as_tuple_enum(self.resource_kinds, PolicyResourceKind),
        )
        object.__setattr__(self, "action_names", _as_tuple_str(self.action_names))
        conds: list[PolicyCondition] = []
        for cond in self.conditions:
            if isinstance(cond, PolicyCondition):
                conds.append(cond)
            elif isinstance(cond, Mapping):
                conds.append(PolicyCondition.from_mapping(cond))
        object.__setattr__(self, "conditions", tuple(conds))
        object.__setattr__(self, "metadata", dict(self.metadata or {}))

    def serialize(self) -> dict[str, Any]:
        return {
            "scopes": [s.value for s in self.scopes],
            "subject_kinds": [sk.value for sk in self.subject_kinds],
            "resource_kinds": [rk.value for rk in self.resource_kinds],
            "action_names": list(self.action_names),
            "conditions": [c.serialize() for c in self.conditions],
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> PolicyTarget:
        return cls(
            scopes=_as_tuple_enum(data.get("scopes"), PolicyScope),
            subject_kinds=_as_tuple_enum(data.get("subject_kinds"), PolicySubjectKind),
            resource_kinds=_as_tuple_enum(
                data.get("resource_kinds"), PolicyResourceKind
            ),
            action_names=_as_tuple_str(data.get("action_names")),
            conditions=tuple(
                PolicyCondition.from_mapping(c) if isinstance(c, Mapping) else c
                for c in data.get("conditions", ())
            ),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass(frozen=True, slots=True)
class PolicyObligation:
    """Required obligation attached to a policy decision."""

    kind: PolicyObligationKind
    required: bool = True
    blocking: bool = True
    parameters: Mapping[str, Any] = dataclass_field(default_factory=dict)
    reason: str | None = None
    source_policy_id: str | None = None
    source_rule_id: str | None = None
    metadata: Mapping[str, Any] = dataclass_field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.kind, PolicyObligationKind):
            object.__setattr__(self, "kind", PolicyObligationKind(self.kind))
        object.__setattr__(self, "parameters", dict(self.parameters or {}))
        if self.reason is not None:
            object.__setattr__(self, "reason", str(self.reason).strip())
        if self.source_policy_id is not None:
            object.__setattr__(
                self, "source_policy_id", str(self.source_policy_id).strip()
            )
        if self.source_rule_id is not None:
            object.__setattr__(self, "source_rule_id", str(self.source_rule_id).strip())
        object.__setattr__(self, "metadata", dict(self.metadata or {}))

    def serialize(self) -> dict[str, Any]:
        return {
            "kind": self.kind.value,
            "required": self.required,
            "blocking": self.blocking,
            "parameters": dict(self.parameters),
            "reason": self.reason,
            "source_policy_id": self.source_policy_id,
            "source_rule_id": self.source_rule_id,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> PolicyObligation:
        return cls(
            kind=PolicyObligationKind(data["kind"]),
            required=bool(data.get("required", True)),
            blocking=bool(data.get("blocking", True)),
            parameters=dict(data.get("parameters", {})),
            reason=data.get("reason"),
            source_policy_id=data.get("source_policy_id"),
            source_rule_id=data.get("source_rule_id"),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass(frozen=True, slots=True)
class PolicyRestriction:
    """Restriction constraining an approved or conditional policy action."""

    kind: str
    description: str
    parameters: Mapping[str, Any] = dataclass_field(default_factory=dict)
    source_policy_id: str | None = None
    source_rule_id: str | None = None
    metadata: Mapping[str, Any] = dataclass_field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.kind or not self.kind.strip():
            raise InvalidPolicyContractError(
                "PolicyRestriction.kind must not be empty."
            )
        if not self.description or not self.description.strip():
            raise InvalidPolicyContractError(
                "PolicyRestriction.description must not be empty."
            )
        object.__setattr__(self, "kind", self.kind.strip().lower())
        object.__setattr__(self, "description", self.description.strip())
        object.__setattr__(self, "parameters", dict(self.parameters or {}))
        if self.source_policy_id is not None:
            object.__setattr__(
                self, "source_policy_id", str(self.source_policy_id).strip()
            )
        if self.source_rule_id is not None:
            object.__setattr__(self, "source_rule_id", str(self.source_rule_id).strip())
        object.__setattr__(self, "metadata", dict(self.metadata or {}))

    def serialize(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "description": self.description,
            "parameters": dict(self.parameters),
            "source_policy_id": self.source_policy_id,
            "source_rule_id": self.source_rule_id,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> PolicyRestriction:
        return cls(
            kind=str(data["kind"]),
            description=str(data["description"]),
            parameters=dict(data.get("parameters", {})),
            source_policy_id=data.get("source_policy_id"),
            source_rule_id=data.get("source_rule_id"),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass(frozen=True, slots=True)
class PolicyAdvice:
    """Non-binding advisory recommendation resulting from policy evaluation."""

    code: str
    message: str
    source_policy_id: str | None = None
    source_rule_id: str | None = None
    metadata: Mapping[str, Any] = dataclass_field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.code or not self.code.strip():
            raise InvalidPolicyContractError("PolicyAdvice.code must not be empty.")
        if not self.message or not self.message.strip():
            raise InvalidPolicyContractError("PolicyAdvice.message must not be empty.")
        object.__setattr__(self, "code", self.code.strip())
        object.__setattr__(self, "message", self.message.strip())
        if self.source_policy_id is not None:
            object.__setattr__(
                self, "source_policy_id", str(self.source_policy_id).strip()
            )
        if self.source_rule_id is not None:
            object.__setattr__(self, "source_rule_id", str(self.source_rule_id).strip())
        object.__setattr__(self, "metadata", dict(self.metadata or {}))

    def serialize(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "source_policy_id": self.source_policy_id,
            "source_rule_id": self.source_rule_id,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> PolicyAdvice:
        return cls(
            code=str(data["code"]),
            message=str(data["message"]),
            source_policy_id=data.get("source_policy_id"),
            source_rule_id=data.get("source_rule_id"),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass(frozen=True, slots=True)
class PolicyViolation:
    """Policy violation detail recorded when a check fails or denies access."""

    code: str
    message: str
    severity: PolicySeverity = PolicySeverity.ERROR
    policy_id: str | None = None
    rule_id: str | None = None
    metadata: Mapping[str, Any] = dataclass_field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.code or not self.code.strip():
            raise InvalidPolicyContractError("PolicyViolation.code must not be empty.")
        if not self.message or not self.message.strip():
            raise InvalidPolicyContractError(
                "PolicyViolation.message must not be empty."
            )
        object.__setattr__(self, "code", self.code.strip())
        object.__setattr__(self, "message", self.message.strip())
        if not isinstance(self.severity, PolicySeverity):
            object.__setattr__(self, "severity", PolicySeverity(self.severity))
        if self.policy_id is not None:
            object.__setattr__(self, "policy_id", str(self.policy_id).strip())
        if self.rule_id is not None:
            object.__setattr__(self, "rule_id", str(self.rule_id).strip())
        object.__setattr__(self, "metadata", dict(self.metadata or {}))

    def serialize(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "severity": self.severity.value,
            "policy_id": self.policy_id,
            "rule_id": self.rule_id,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> PolicyViolation:
        return cls(
            code=str(data["code"]),
            message=str(data["message"]),
            severity=PolicySeverity(data.get("severity", PolicySeverity.ERROR.value)),
            policy_id=data.get("policy_id"),
            rule_id=data.get("rule_id"),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass(frozen=True, slots=True)
class PolicyWarning:
    """Warning emitted during policy evaluation."""

    code: str
    message: str
    policy_id: str | None = None
    rule_id: str | None = None
    metadata: Mapping[str, Any] = dataclass_field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.code or not self.code.strip():
            raise InvalidPolicyContractError("PolicyWarning.code must not be empty.")
        if not self.message or not self.message.strip():
            raise InvalidPolicyContractError("PolicyWarning.message must not be empty.")
        object.__setattr__(self, "code", self.code.strip())
        object.__setattr__(self, "message", self.message.strip())
        if self.policy_id is not None:
            object.__setattr__(self, "policy_id", str(self.policy_id).strip())
        if self.rule_id is not None:
            object.__setattr__(self, "rule_id", str(self.rule_id).strip())
        object.__setattr__(self, "metadata", dict(self.metadata or {}))

    def serialize(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "policy_id": self.policy_id,
            "rule_id": self.rule_id,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> PolicyWarning:
        return cls(
            code=str(data["code"]),
            message=str(data["message"]),
            policy_id=data.get("policy_id"),
            rule_id=data.get("rule_id"),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass(frozen=True, slots=True)
class PolicyError:
    """Error encountered while attempting policy evaluation."""

    code: str
    message: str
    details: Mapping[str, Any] = dataclass_field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.code or not self.code.strip():
            raise InvalidPolicyContractError("PolicyError.code must not be empty.")
        if not self.message or not self.message.strip():
            raise InvalidPolicyContractError("PolicyError.message must not be empty.")
        object.__setattr__(self, "code", self.code.strip())
        object.__setattr__(self, "message", self.message.strip())
        object.__setattr__(self, "details", dict(self.details or {}))

    def serialize(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "details": dict(self.details),
        }

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> PolicyError:
        return cls(
            code=str(data["code"]),
            message=str(data["message"]),
            details=dict(data.get("details", {})),
        )


@dataclass(frozen=True, slots=True)
class PolicyRule:
    """Individual rule within a policy."""

    id: str
    policy_id: str
    description: str
    conditions: tuple[PolicyCondition, ...] = ()
    effect: PolicyEffect = PolicyEffect.PERMIT
    decision: PolicyDecision = PolicyDecision.ALLOW
    priority: int = 0
    reason_code: str = "rule_matched"
    obligations: tuple[PolicyObligation, ...] = ()
    restrictions: tuple[PolicyRestriction, ...] = ()
    enabled: bool = True
    metadata: Mapping[str, Any] = dataclass_field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.id or not self.id.strip():
            raise InvalidPolicyContractError("PolicyRule.id must not be empty.")
        if not self.policy_id or not self.policy_id.strip():
            raise InvalidPolicyContractError("PolicyRule.policy_id must not be empty.")
        if self.priority < 0:
            raise InvalidPolicyContractError(
                f"PolicyRule.priority must not be negative, got {self.priority}"
            )
        object.__setattr__(self, "id", self.id.strip())
        object.__setattr__(self, "policy_id", self.policy_id.strip())
        object.__setattr__(self, "description", str(self.description or "").strip())

        conds: list[PolicyCondition] = []
        for c in self.conditions:
            if isinstance(c, PolicyCondition):
                conds.append(c)
            elif isinstance(c, Mapping):
                conds.append(PolicyCondition.from_mapping(c))
        object.__setattr__(self, "conditions", tuple(conds))

        if not isinstance(self.effect, PolicyEffect):
            object.__setattr__(self, "effect", PolicyEffect(self.effect))
        if not isinstance(self.decision, PolicyDecision):
            object.__setattr__(self, "decision", PolicyDecision(self.decision))

        object.__setattr__(
            self, "reason_code", str(self.reason_code or "rule_matched").strip()
        )

        obs: list[PolicyObligation] = []
        for o in self.obligations:
            if isinstance(o, PolicyObligation):
                obs.append(o)
            elif isinstance(o, Mapping):
                obs.append(PolicyObligation.from_mapping(o))
        object.__setattr__(self, "obligations", tuple(obs))

        rests: list[PolicyRestriction] = []
        for r in self.restrictions:
            if isinstance(r, PolicyRestriction):
                rests.append(r)
            elif isinstance(r, Mapping):
                rests.append(PolicyRestriction.from_mapping(r))
        object.__setattr__(self, "restrictions", tuple(rests))

        object.__setattr__(self, "metadata", dict(self.metadata or {}))

    def serialize(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "policy_id": self.policy_id,
            "description": self.description,
            "conditions": [c.serialize() for c in self.conditions],
            "effect": self.effect.value,
            "decision": self.decision.value,
            "priority": self.priority,
            "reason_code": self.reason_code,
            "obligations": [o.serialize() for o in self.obligations],
            "restrictions": [r.serialize() for r in self.restrictions],
            "enabled": self.enabled,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> PolicyRule:
        return cls(
            id=str(data["id"]),
            policy_id=str(data["policy_id"]),
            description=str(data.get("description", "")),
            conditions=tuple(
                PolicyCondition.from_mapping(c) if isinstance(c, Mapping) else c
                for c in data.get("conditions", ())
            ),
            effect=PolicyEffect(data.get("effect", PolicyEffect.PERMIT.value)),
            decision=PolicyDecision(data.get("decision", PolicyDecision.ALLOW.value)),
            priority=int(data.get("priority", 0)),
            reason_code=str(data.get("reason_code", "rule_matched")),
            obligations=tuple(
                PolicyObligation.from_mapping(o) if isinstance(o, Mapping) else o
                for o in data.get("obligations", ())
            ),
            restrictions=tuple(
                PolicyRestriction.from_mapping(r) if isinstance(r, Mapping) else r
                for r in data.get("restrictions", ())
            ),
            enabled=bool(data.get("enabled", True)),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass(frozen=True, slots=True)
class Policy:
    """Immutable policy contract."""

    id: str
    name: str
    description: str
    version: int = 1
    enabled: bool = True
    priority: int = 0
    scope: PolicyScope = PolicyScope.GLOBAL
    effect: PolicyEffect = PolicyEffect.PERMIT
    target: PolicyTarget | None = None
    rules: tuple[PolicyRule, ...] = ()
    obligations: tuple[PolicyObligation, ...] = ()
    restrictions: tuple[PolicyRestriction, ...] = ()
    failure_mode: PolicyFailureMode = PolicyFailureMode.DENY
    valid_from: str | None = None
    valid_until: str | None = None
    actor_id: str | None = None
    created_at: str = dataclass_field(default_factory=_now_iso)
    updated_at: str = dataclass_field(default_factory=_now_iso)
    metadata: Mapping[str, Any] = dataclass_field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.id or not self.id.strip():
            raise InvalidPolicyContractError("Policy.id must not be empty.")
        if not self.name or not self.name.strip():
            raise InvalidPolicyContractError("Policy.name must not be empty.")
        if self.version < 1:
            raise PolicyVersionError(
                f"Policy.version must be positive, got {self.version}"
            )
        if self.priority < 0:
            raise InvalidPolicyContractError(
                f"Policy.priority must not be negative, got {self.priority}"
            )

        # Ensure valid_from <= valid_until if both provided
        if self.valid_from and self.valid_until and self.valid_from > self.valid_until:
            raise InvalidPolicyContractError(
                f"Policy valid_from ({self.valid_from}) cannot be after valid_until ({self.valid_until})"
            )

        object.__setattr__(self, "id", self.id.strip())
        object.__setattr__(self, "name", self.name.strip())
        object.__setattr__(self, "description", str(self.description or "").strip())
        if not isinstance(self.scope, PolicyScope):
            object.__setattr__(self, "scope", PolicyScope(self.scope))
        if not isinstance(self.effect, PolicyEffect):
            object.__setattr__(self, "effect", PolicyEffect(self.effect))
        if not isinstance(self.failure_mode, PolicyFailureMode):
            object.__setattr__(
                self, "failure_mode", PolicyFailureMode(self.failure_mode)
            )

        if self.target is not None and isinstance(self.target, Mapping):
            object.__setattr__(self, "target", PolicyTarget.from_mapping(self.target))

        # Check unique rule IDs within policy
        parsed_rules: list[PolicyRule] = []
        rule_ids: set[str] = set()
        for r in self.rules:
            rule_obj = PolicyRule.from_mapping(r) if isinstance(r, Mapping) else r
            if rule_obj.id in rule_ids:
                raise InvalidPolicyContractError(
                    f"Duplicate rule ID '{rule_obj.id}' inside policy '{self.id}'"
                )
            rule_ids.add(rule_obj.id)
            parsed_rules.append(rule_obj)
        object.__setattr__(self, "rules", tuple(parsed_rules))

        obs: list[PolicyObligation] = []
        for o in self.obligations:
            obs.append(
                PolicyObligation.from_mapping(o) if isinstance(o, Mapping) else o
            )
        object.__setattr__(self, "obligations", tuple(obs))

        rests: list[PolicyRestriction] = []
        for restriction in self.restrictions:
            restriction_obj = (
                PolicyRestriction.from_mapping(restriction)
                if isinstance(restriction, Mapping)
                else restriction
            )
            rests.append(restriction_obj)
        object.__setattr__(self, "restrictions", tuple(rests))

        if self.actor_id is not None:
            object.__setattr__(self, "actor_id", str(self.actor_id).strip())

        object.__setattr__(self, "created_at", str(self.created_at or _now_iso()))
        object.__setattr__(self, "updated_at", str(self.updated_at or _now_iso()))
        object.__setattr__(self, "metadata", dict(self.metadata or {}))

    def serialize(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "enabled": self.enabled,
            "priority": self.priority,
            "scope": self.scope.value,
            "effect": self.effect.value,
            "target": self.target.serialize() if self.target else None,
            "rules": [r.serialize() for r in self.rules],
            "obligations": [o.serialize() for o in self.obligations],
            "restrictions": [r.serialize() for r in self.restrictions],
            "failure_mode": self.failure_mode.value,
            "valid_from": self.valid_from,
            "valid_until": self.valid_until,
            "actor_id": self.actor_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> Policy:
        t_raw = data.get("target")
        t_obj = (
            PolicyTarget.from_mapping(t_raw) if isinstance(t_raw, Mapping) else t_raw
        )
        return cls(
            id=str(data["id"]),
            name=str(data["name"]),
            description=str(data.get("description", "")),
            version=int(data.get("version", 1)),
            enabled=bool(data.get("enabled", True)),
            priority=int(data.get("priority", 0)),
            scope=PolicyScope(data.get("scope", PolicyScope.GLOBAL.value)),
            effect=PolicyEffect(data.get("effect", PolicyEffect.PERMIT.value)),
            target=t_obj,
            rules=tuple(
                PolicyRule.from_mapping(r) if isinstance(r, Mapping) else r
                for r in data.get("rules", ())
            ),
            obligations=tuple(
                PolicyObligation.from_mapping(o) if isinstance(o, Mapping) else o
                for o in data.get("obligations", ())
            ),
            restrictions=tuple(
                PolicyRestriction.from_mapping(r) if isinstance(r, Mapping) else r
                for r in data.get("restrictions", ())
            ),
            failure_mode=PolicyFailureMode(
                data.get("failure_mode", PolicyFailureMode.DENY.value)
            ),
            valid_from=data.get("valid_from"),
            valid_until=data.get("valid_until"),
            actor_id=data.get("actor_id"),
            created_at=str(data.get("created_at") or _now_iso()),
            updated_at=str(data.get("updated_at") or _now_iso()),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass(frozen=True, slots=True)
class PolicySet:
    """Group of ordered, prioritized policies evaluated using a combining algorithm."""

    id: str
    name: str
    description: str
    version: int = 1
    enabled: bool = True
    priority: int = 0
    scope: PolicyScope = PolicyScope.GLOBAL
    combining_algorithm: PolicyCombiningAlgorithm = (
        PolicyCombiningAlgorithm.DENY_OVERRIDES
    )
    policy_ids: tuple[str, ...] = ()
    policies: tuple[Policy, ...] = ()
    created_at: str = dataclass_field(default_factory=_now_iso)
    updated_at: str = dataclass_field(default_factory=_now_iso)
    metadata: Mapping[str, Any] = dataclass_field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.id or not self.id.strip():
            raise InvalidPolicyContractError("PolicySet.id must not be empty.")
        if not self.name or not self.name.strip():
            raise InvalidPolicyContractError("PolicySet.name must not be empty.")
        if self.version < 1:
            raise PolicyVersionError(
                f"PolicySet.version must be positive, got {self.version}"
            )
        if self.priority < 0:
            raise InvalidPolicyContractError(
                f"PolicySet.priority must not be negative, got {self.priority}"
            )

        object.__setattr__(self, "id", self.id.strip())
        object.__setattr__(self, "name", self.name.strip())
        object.__setattr__(self, "description", str(self.description or "").strip())
        if not isinstance(self.scope, PolicyScope):
            object.__setattr__(self, "scope", PolicyScope(self.scope))
        if not isinstance(self.combining_algorithm, PolicyCombiningAlgorithm):
            object.__setattr__(
                self,
                "combining_algorithm",
                PolicyCombiningAlgorithm(self.combining_algorithm),
            )

        object.__setattr__(self, "policy_ids", _as_tuple_str(self.policy_ids))

        parsed_policies: list[Policy] = []
        for p in self.policies:
            parsed_policies.append(
                Policy.from_mapping(p) if isinstance(p, Mapping) else p
            )
        object.__setattr__(self, "policies", tuple(parsed_policies))

        object.__setattr__(self, "created_at", str(self.created_at or _now_iso()))
        object.__setattr__(self, "updated_at", str(self.updated_at or _now_iso()))
        object.__setattr__(self, "metadata", dict(self.metadata or {}))

    def serialize(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "enabled": self.enabled,
            "priority": self.priority,
            "scope": self.scope.value,
            "combining_algorithm": self.combining_algorithm.value,
            "policy_ids": list(self.policy_ids),
            "policies": [p.serialize() for p in self.policies],
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> PolicySet:
        return cls(
            id=str(data["id"]),
            name=str(data["name"]),
            description=str(data.get("description", "")),
            version=int(data.get("version", 1)),
            enabled=bool(data.get("enabled", True)),
            priority=int(data.get("priority", 0)),
            scope=PolicyScope(data.get("scope", PolicyScope.GLOBAL.value)),
            combining_algorithm=PolicyCombiningAlgorithm(
                data.get(
                    "combining_algorithm", PolicyCombiningAlgorithm.DENY_OVERRIDES.value
                )
            ),
            policy_ids=_as_tuple_str(data.get("policy_ids")),
            policies=tuple(
                Policy.from_mapping(p) if isinstance(p, Mapping) else p
                for p in data.get("policies", ())
            ),
            created_at=str(data.get("created_at") or _now_iso()),
            updated_at=str(data.get("updated_at") or _now_iso()),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass(frozen=True, slots=True)
class PolicyVersion:
    """Version metadata for a policy or policy set."""

    policy_id: str
    version: int
    created_at: str = dataclass_field(default_factory=_now_iso)
    author_id: str | None = None
    change_summary: str = ""
    metadata: Mapping[str, Any] = dataclass_field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.policy_id or not self.policy_id.strip():
            raise InvalidPolicyContractError(
                "PolicyVersion.policy_id must not be empty."
            )
        if self.version < 1:
            raise PolicyVersionError(
                f"PolicyVersion.version must be positive, got {self.version}"
            )
        object.__setattr__(self, "policy_id", self.policy_id.strip())
        if self.author_id is not None:
            object.__setattr__(self, "author_id", str(self.author_id).strip())
        object.__setattr__(
            self, "change_summary", str(self.change_summary or "").strip()
        )
        object.__setattr__(self, "metadata", dict(self.metadata or {}))


@dataclass(frozen=True, slots=True)
class PolicyTraceReference:
    """Audit reference pointing to a stored policy evaluation trace."""

    id: str
    request_id: str
    evaluated_at: str = dataclass_field(default_factory=_now_iso)
    summary: str = ""
    metadata: Mapping[str, Any] = dataclass_field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.id or not self.id.strip():
            raise InvalidPolicyContractError(
                "PolicyTraceReference.id must not be empty."
            )
        if not self.request_id or not self.request_id.strip():
            raise InvalidPolicyContractError(
                "PolicyTraceReference.request_id must not be empty."
            )
        object.__setattr__(self, "id", self.id.strip())
        object.__setattr__(self, "request_id", self.request_id.strip())
        object.__setattr__(self, "metadata", dict(self.metadata or {}))


@dataclass(frozen=True, slots=True)
class PolicyEvaluationRequest:
    """Request data container submitted to the Policy Engine for evaluation."""

    id: str
    subject: PolicySubject
    resource: PolicyResource
    action: PolicyAction
    environment: PolicyEnvironment
    policy_set_ids: tuple[str, ...] = ()
    permissions: tuple[str, ...] = ()
    sensitivity: str = "internal"
    risk: PolicyRiskLevel = PolicyRiskLevel.LOW
    goal_id: str | None = None
    agent_run_id: str | None = None
    workflow_plan_id: str | None = None
    task_id: str | None = None
    operation_id: str | None = None
    actor_id: str | None = None
    created_at: str = dataclass_field(default_factory=_now_iso)
    metadata: Mapping[str, Any] = dataclass_field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.id or not self.id.strip():
            raise InvalidPolicyContractError(
                "PolicyEvaluationRequest.id must not be empty."
            )
        object.__setattr__(self, "id", self.id.strip())

        if isinstance(self.subject, Mapping):
            object.__setattr__(
                self, "subject", PolicySubject.from_mapping(self.subject)
            )
        if isinstance(self.resource, Mapping):
            object.__setattr__(
                self, "resource", PolicyResource.from_mapping(self.resource)
            )
        if isinstance(self.action, Mapping):
            object.__setattr__(self, "action", PolicyAction.from_mapping(self.action))
        if isinstance(self.environment, Mapping):
            object.__setattr__(
                self, "environment", PolicyEnvironment.from_mapping(self.environment)
            )

        object.__setattr__(self, "policy_set_ids", _as_tuple_str(self.policy_set_ids))
        object.__setattr__(self, "permissions", _as_tuple_str(self.permissions))
        object.__setattr__(
            self, "sensitivity", str(self.sensitivity or "internal").strip().lower()
        )
        if not isinstance(self.risk, PolicyRiskLevel):
            object.__setattr__(self, "risk", PolicyRiskLevel(self.risk))

        if self.goal_id is not None:
            object.__setattr__(self, "goal_id", str(self.goal_id).strip())
        if self.agent_run_id is not None:
            object.__setattr__(self, "agent_run_id", str(self.agent_run_id).strip())
        if self.workflow_plan_id is not None:
            object.__setattr__(
                self, "workflow_plan_id", str(self.workflow_plan_id).strip()
            )
        if self.task_id is not None:
            object.__setattr__(self, "task_id", str(self.task_id).strip())
        if self.operation_id is not None:
            object.__setattr__(self, "operation_id", str(self.operation_id).strip())
        if self.actor_id is not None:
            object.__setattr__(self, "actor_id", str(self.actor_id).strip())

        object.__setattr__(self, "created_at", str(self.created_at or _now_iso()))
        object.__setattr__(self, "metadata", dict(self.metadata or {}))

    def serialize(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "subject": self.subject.serialize(),
            "resource": self.resource.serialize(),
            "action": self.action.serialize(),
            "environment": self.environment.serialize(),
            "policy_set_ids": list(self.policy_set_ids),
            "permissions": list(self.permissions),
            "sensitivity": self.sensitivity,
            "risk": self.risk.value,
            "goal_id": self.goal_id,
            "agent_run_id": self.agent_run_id,
            "workflow_plan_id": self.workflow_plan_id,
            "task_id": self.task_id,
            "operation_id": self.operation_id,
            "actor_id": self.actor_id,
            "created_at": self.created_at,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> PolicyEvaluationRequest:
        return cls(
            id=str(data["id"]),
            subject=PolicySubject.from_mapping(data["subject"])
            if isinstance(data["subject"], Mapping)
            else data["subject"],
            resource=PolicyResource.from_mapping(data["resource"])
            if isinstance(data["resource"], Mapping)
            else data["resource"],
            action=PolicyAction.from_mapping(data["action"])
            if isinstance(data["action"], Mapping)
            else data["action"],
            environment=PolicyEnvironment.from_mapping(data.get("environment", {}))
            if isinstance(data.get("environment"), Mapping)
            else data["environment"],
            policy_set_ids=_as_tuple_str(data.get("policy_set_ids")),
            permissions=_as_tuple_str(data.get("permissions")),
            sensitivity=str(data.get("sensitivity", "internal")),
            risk=PolicyRiskLevel(data.get("risk", PolicyRiskLevel.LOW.value)),
            goal_id=data.get("goal_id"),
            agent_run_id=data.get("agent_run_id"),
            workflow_plan_id=data.get("workflow_plan_id"),
            task_id=data.get("task_id"),
            operation_id=data.get("operation_id"),
            actor_id=data.get("actor_id"),
            created_at=str(data.get("created_at") or _now_iso()),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass(frozen=True, slots=True)
class PolicyEvaluationContext:
    """Execution context assembled for evaluating policies."""

    actor: PolicySubject | None
    agent_id: str | None
    goal: Any | None
    agent_run: Any | None
    subject: PolicySubject
    resource: PolicyResource
    action: PolicyAction
    environment: PolicyEnvironment
    permissions: tuple[str, ...] = ()
    sensitivity: str = "internal"
    risk: PolicyRiskLevel = PolicyRiskLevel.LOW
    evaluated_policies: tuple[Policy, ...] = ()
    policy_sets: tuple[PolicySet, ...] = ()
    workflow_ref: Any | None = None
    task_ref: Any | None = None
    operation_ref: Any | None = None
    temporal_reference: str = dataclass_field(default_factory=_now_iso)
    metadata: Mapping[str, Any] = dataclass_field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "permissions", _as_tuple_str(self.permissions))
        object.__setattr__(
            self, "sensitivity", str(self.sensitivity or "internal").strip().lower()
        )
        if not isinstance(self.risk, PolicyRiskLevel):
            object.__setattr__(self, "risk", PolicyRiskLevel(self.risk))
        object.__setattr__(
            self, "temporal_reference", str(self.temporal_reference or _now_iso())
        )
        object.__setattr__(self, "metadata", dict(self.metadata or {}))


@dataclass(frozen=True, slots=True)
class PolicyRuleEvaluation:
    """Individual rule evaluation output."""

    rule_id: str
    policy_id: str
    matched: bool
    effect: PolicyEffect
    decision: PolicyDecision
    reason_code: str
    condition_results: tuple[dict[str, Any], ...] = ()
    obligations: tuple[PolicyObligation, ...] = ()
    restrictions: tuple[PolicyRestriction, ...] = ()
    evaluated_at: str = dataclass_field(default_factory=_now_iso)

    def serialize(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "policy_id": self.policy_id,
            "matched": self.matched,
            "effect": self.effect.value,
            "decision": self.decision.value,
            "reason_code": self.reason_code,
            "condition_results": [dict(c) for c in self.condition_results],
            "obligations": [o.serialize() for o in self.obligations],
            "restrictions": [r.serialize() for r in self.restrictions],
            "evaluated_at": self.evaluated_at,
        }


@dataclass(frozen=True, slots=True)
class PolicyEvaluationResult:
    """Comprehensive evaluation result produced by the Policy Engine."""

    id: str
    request_id: str
    status: PolicyEvaluationStatus
    decision: PolicyDecision
    allowed: bool
    denied: bool
    requires_approval: bool
    requires_validation: bool
    requires_information: bool
    paused: bool
    applicable_policy_ids: tuple[str, ...] = ()
    matched_rule_ids: tuple[str, ...] = ()
    rule_evaluations: tuple[PolicyRuleEvaluation, ...] = ()
    obligations: tuple[PolicyObligation, ...] = ()
    restrictions: tuple[PolicyRestriction, ...] = ()
    advice: tuple[PolicyAdvice, ...] = ()
    violations: tuple[PolicyViolation, ...] = ()
    warnings: tuple[PolicyWarning, ...] = ()
    errors: tuple[PolicyError, ...] = ()
    reason_codes: tuple[str, ...] = ()
    confidence: float = 1.0
    evaluated_at: str = dataclass_field(default_factory=_now_iso)
    policy_trace_id: str = dataclass_field(
        default_factory=lambda: f"trace-{_now_iso()}"
    )
    metadata: Mapping[str, Any] = dataclass_field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.id or not self.id.strip():
            raise InvalidPolicyContractError(
                "PolicyEvaluationResult.id must not be empty."
            )
        if not self.request_id or not self.request_id.strip():
            raise InvalidPolicyContractError(
                "PolicyEvaluationResult.request_id must not be empty."
            )
        if not (0.0 <= self.confidence <= 1.0):
            raise InvalidPolicyContractError(
                f"PolicyEvaluationResult.confidence must be between 0.0 and 1.0, got {self.confidence}"
            )

        object.__setattr__(self, "id", self.id.strip())
        object.__setattr__(self, "request_id", self.request_id.strip())
        if not isinstance(self.status, PolicyEvaluationStatus):
            object.__setattr__(self, "status", PolicyEvaluationStatus(self.status))
        if not isinstance(self.decision, PolicyDecision):
            object.__setattr__(self, "decision", PolicyDecision(self.decision))

        object.__setattr__(
            self, "applicable_policy_ids", _as_tuple_str(self.applicable_policy_ids)
        )
        object.__setattr__(
            self, "matched_rule_ids", _as_tuple_str(self.matched_rule_ids)
        )
        object.__setattr__(self, "reason_codes", _as_tuple_str(self.reason_codes))

        object.__setattr__(self, "evaluated_at", str(self.evaluated_at or _now_iso()))
        object.__setattr__(
            self, "policy_trace_id", str(self.policy_trace_id or f"trace-{self.id}")
        )
        object.__setattr__(self, "metadata", dict(self.metadata or {}))

    def serialize(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "request_id": self.request_id,
            "status": self.status.value,
            "decision": self.decision.value,
            "allowed": self.allowed,
            "denied": self.denied,
            "requires_approval": self.requires_approval,
            "requires_validation": self.requires_validation,
            "requires_information": self.requires_information,
            "paused": self.paused,
            "applicable_policy_ids": list(self.applicable_policy_ids),
            "matched_rule_ids": list(self.matched_rule_ids),
            "rule_evaluations": [re.serialize() for re in self.rule_evaluations],
            "obligations": [o.serialize() for o in self.obligations],
            "restrictions": [r.serialize() for r in self.restrictions],
            "advice": [a.serialize() for a in self.advice],
            "violations": [v.serialize() for v in self.violations],
            "warnings": [w.serialize() for w in self.warnings],
            "errors": [e.serialize() for e in self.errors],
            "reason_codes": list(self.reason_codes),
            "confidence": self.confidence,
            "evaluated_at": self.evaluated_at,
            "policy_trace_id": self.policy_trace_id,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> PolicyEvaluationResult:
        rule_evals = tuple(
            PolicyRuleEvaluation(
                rule_id=str(re_data["rule_id"]),
                policy_id=str(re_data["policy_id"]),
                matched=bool(re_data["matched"]),
                effect=PolicyEffect(re_data["effect"]),
                decision=PolicyDecision(re_data["decision"]),
                reason_code=str(re_data["reason_code"]),
                condition_results=tuple(re_data.get("condition_results", ())),
                obligations=tuple(
                    PolicyObligation.from_mapping(o)
                    for o in re_data.get("obligations", ())
                ),
                restrictions=tuple(
                    PolicyRestriction.from_mapping(r)
                    for r in re_data.get("restrictions", ())
                ),
                evaluated_at=str(re_data.get("evaluated_at") or _now_iso()),
            )
            for re_data in data.get("rule_evaluations", ())
        )

        return cls(
            id=str(data["id"]),
            request_id=str(data["request_id"]),
            status=PolicyEvaluationStatus(
                data.get("status", PolicyEvaluationStatus.COMPLETED.value)
            ),
            decision=PolicyDecision(data.get("decision", PolicyDecision.ALLOW.value)),
            allowed=bool(data.get("allowed", False)),
            denied=bool(data.get("denied", False)),
            requires_approval=bool(data.get("requires_approval", False)),
            requires_validation=bool(data.get("requires_validation", False)),
            requires_information=bool(data.get("requires_information", False)),
            paused=bool(data.get("paused", False)),
            applicable_policy_ids=_as_tuple_str(data.get("applicable_policy_ids")),
            matched_rule_ids=_as_tuple_str(data.get("matched_rule_ids")),
            rule_evaluations=rule_evals,
            obligations=tuple(
                PolicyObligation.from_mapping(o) if isinstance(o, Mapping) else o
                for o in data.get("obligations", ())
            ),
            restrictions=tuple(
                PolicyRestriction.from_mapping(r) if isinstance(r, Mapping) else r
                for r in data.get("restrictions", ())
            ),
            advice=tuple(
                PolicyAdvice.from_mapping(a) if isinstance(a, Mapping) else a
                for a in data.get("advice", ())
            ),
            violations=tuple(
                PolicyViolation.from_mapping(v) if isinstance(v, Mapping) else v
                for v in data.get("violations", ())
            ),
            warnings=tuple(
                PolicyWarning.from_mapping(w) if isinstance(w, Mapping) else w
                for w in data.get("warnings", ())
            ),
            errors=tuple(
                PolicyError.from_mapping(e) if isinstance(e, Mapping) else e
                for e in data.get("errors", ())
            ),
            reason_codes=_as_tuple_str(data.get("reason_codes")),
            confidence=float(data.get("confidence", 1.0)),
            evaluated_at=str(
                data.get("created_at") or data.get("evaluated_at") or _now_iso()
            ),
            policy_trace_id=str(data.get("policy_trace_id") or f"trace-{data['id']}"),
            metadata=dict(data.get("metadata", {})),
        )
