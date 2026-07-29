"""Phase 9.25 – Agent Security, Permissions, and Isolation Contracts.

Immutable, JSON-serializable, type-safe contracts for the authorization boundary.
All dataclasses are ``frozen=True`` and never expose mutable internal state.
"""

from __future__ import annotations

import re
import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from types import MappingProxyType
from typing import Any

from cmm.agent_runtime.agent_security_enums import (
    ExternalActionCategory,
    KillSwitchState,
    PermissionEffect,
    PromptInjectionResult,
    SensitivityLevel,
)
from cmm.agent_runtime.agent_security_errors import InvalidSecurityContractError
from cmm.agent_runtime.contracts import (
    _freeze_metadata,
    _freeze_str_tuple,
)

# ── Helpers ──────────────────────────────────────────────────────────────────


_SECURITY_ID_PATTERN = re.compile(r"^[a-zA-Z][a-zA-Z0-9_.\-]{0,127}$")
_PERMISSION_CONTEXT_ID_PATTERN = re.compile(r"^perm-ctx-[a-zA-Z0-9_.\-]{1,63}$")
_AUDIT_ENTRY_ID_PATTERN = re.compile(r"^audit-[a-zA-Z0-9_.\-]{1,63}$")
_KILL_SWITCH_REPORT_ID_PATTERN = re.compile(r"^ks-report-[a-zA-Z0-9_.\-]{1,63}$")

_FORBIDDEN_METADATA_KEYS: frozenset[str] = frozenset(
    {
        "chain_of_thought",
        "private_prompt",
        "internal_reasoning",
        "api_key",
        "apikey",
        "password",
        "passwd",
        "private_key",
        "secret",
        "bearer",
        "token",
        "credential",
        "credentials",
    }
)


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _ensure_tz_aware(dt: Any, field_name: str) -> datetime:
    if not isinstance(dt, datetime):
        raise InvalidSecurityContractError(
            f"{field_name} must be a datetime instance", {"field": field_name}
        )
    if dt.tzinfo is None:
        raise InvalidSecurityContractError(
            f"{field_name} must be timezone-aware", {"field": field_name}
        )
    return dt


def _validate_non_empty_str(val: Any, field_name: str) -> str:
    if not isinstance(val, str) or not val.strip():
        raise InvalidSecurityContractError(
            f"{field_name} must be a non-empty string", {"field": field_name}
        )
    return val.strip()


def _validate_identifier(val: Any, field_name: str) -> str:
    s = _validate_non_empty_str(val, field_name)
    if not _SECURITY_ID_PATTERN.match(s):
        raise InvalidSecurityContractError(
            f"{field_name} has invalid format",
            {"field": field_name, "value": s},
        )
    return s


def _validate_permission_context_id(val: Any, field_name: str) -> str:
    s = _validate_non_empty_str(val, field_name)
    if not _PERMISSION_CONTEXT_ID_PATTERN.match(s):
        raise InvalidSecurityContractError(
            f"{field_name} has invalid format",
            {"field": field_name, "value": s},
        )
    return s


def _validate_audit_entry_id(val: Any, field_name: str) -> str:
    s = _validate_non_empty_str(val, field_name)
    if not _AUDIT_ENTRY_ID_PATTERN.match(s):
        raise InvalidSecurityContractError(
            f"{field_name} has invalid format",
            {"field": field_name, "value": s},
        )
    return s


def _validate_kill_switch_report_id(val: Any, field_name: str) -> str:
    s = _validate_non_empty_str(val, field_name)
    if not _KILL_SWITCH_REPORT_ID_PATTERN.match(s):
        raise InvalidSecurityContractError(
            f"{field_name} has invalid format",
            {"field": field_name, "value": s},
        )
    return s


def _validate_sensitivity_level(val: Any, field_name: str) -> SensitivityLevel:
    if isinstance(val, SensitivityLevel):
        return val
    if isinstance(val, str):
        try:
            return SensitivityLevel(val.strip().lower())
        except ValueError as exc:
            raise InvalidSecurityContractError(
                f"{field_name} must be a valid SensitivityLevel",
                {"field": field_name, "value": val},
            ) from exc
    raise InvalidSecurityContractError(
        f"{field_name} must be a SensitivityLevel or valid string",
        {"field": field_name},
    )


def _validate_permission_effect(val: Any, field_name: str) -> PermissionEffect:
    if isinstance(val, PermissionEffect):
        return val
    if isinstance(val, str):
        try:
            return PermissionEffect(val.strip().lower())
        except ValueError as exc:
            raise InvalidSecurityContractError(
                f"{field_name} must be a valid PermissionEffect",
                {"field": field_name, "value": val},
            ) from exc
    raise InvalidSecurityContractError(
        f"{field_name} must be a PermissionEffect or valid string",
        {"field": field_name},
    )


def _validate_prompt_injection_result(
    val: Any, field_name: str
) -> PromptInjectionResult:
    if isinstance(val, PromptInjectionResult):
        return val
    if isinstance(val, str):
        try:
            return PromptInjectionResult(val.strip().lower())
        except ValueError as exc:
            raise InvalidSecurityContractError(
                f"{field_name} must be a valid PromptInjectionResult",
                {"field": field_name, "value": val},
            ) from exc
    raise InvalidSecurityContractError(
        f"{field_name} must be a PromptInjectionResult or valid string",
        {"field": field_name},
    )


def _validate_kill_switch_state(val: Any, field_name: str) -> KillSwitchState:
    if isinstance(val, KillSwitchState):
        return val
    if isinstance(val, str):
        try:
            return KillSwitchState(val.strip().lower())
        except ValueError as exc:
            raise InvalidSecurityContractError(
                f"{field_name} must be a valid KillSwitchState",
                {"field": field_name, "value": val},
            ) from exc
    raise InvalidSecurityContractError(
        f"{field_name} must be a KillSwitchState or valid string",
        {"field": field_name},
    )


def _validate_external_action_category(
    val: Any, field_name: str
) -> ExternalActionCategory:
    if isinstance(val, ExternalActionCategory):
        return val
    if isinstance(val, str):
        try:
            return ExternalActionCategory(val.strip().lower())
        except ValueError as exc:
            raise InvalidSecurityContractError(
                f"{field_name} must be a valid ExternalActionCategory",
                {"field": field_name, "value": val},
            ) from exc
    raise InvalidSecurityContractError(
        f"{field_name} must be an ExternalActionCategory or valid string",
        {"field": field_name},
    )


def _validate_metadata_no_secrets(meta: Mapping[str, Any]) -> None:
    for key in meta:
        if key.lower() in _FORBIDDEN_METADATA_KEYS:
            raise InvalidSecurityContractError(
                f"Metadata contains forbidden key: {key!r}",
                {"field": "metadata", "forbidden_key": key},
            )


# ── AgentPermissionContext ────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class AgentPermissionContext:
    """
    Immutable permission context for an agent run.

    Captures the complete authorization boundary including identity, scopes,
    constraints, and lifecycle.
    """

    id: str
    agent_id: str
    agent_run_id: str
    goal_id: str
    actor_id: str
    owner_actor_id: str
    allowed_domains: tuple[str, ...]
    allowed_resources: tuple[str, ...]
    allowed_operations: tuple[str, ...]
    allowed_sensitivity_levels: tuple[SensitivityLevel, ...]
    maximum_autonomy_level: int
    allow_external_access: bool = False
    allow_external_models: bool = False
    allow_memory_write: bool = False
    allow_goal_creation: bool = False
    allow_delegation: bool = False
    allow_publication: bool = False
    allow_communications: bool = False
    allow_destructive_actions: bool = False
    allow_permission_elevation: bool = False
    expires_at: datetime | None = None
    created_at: datetime = field(default_factory=_now_utc)
    metadata: MappingProxyType[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )

    def __post_init__(self) -> None:
        # Validate identifiers
        object.__setattr__(self, "id", _validate_permission_context_id(self.id, "id"))
        object.__setattr__(
            self, "agent_id", _validate_identifier(self.agent_id, "agent_id")
        )
        object.__setattr__(
            self,
            "agent_run_id",
            _validate_identifier(self.agent_run_id, "agent_run_id"),
        )
        object.__setattr__(
            self, "goal_id", _validate_identifier(self.goal_id, "goal_id")
        )
        object.__setattr__(
            self, "actor_id", _validate_identifier(self.actor_id, "actor_id")
        )
        object.__setattr__(
            self,
            "owner_actor_id",
            _validate_identifier(self.owner_actor_id, "owner_actor_id"),
        )

        # Validate collections
        object.__setattr__(
            self,
            "allowed_domains",
            _freeze_str_tuple(self.allowed_domains, "allowed_domains"),
        )
        object.__setattr__(
            self,
            "allowed_resources",
            _freeze_str_tuple(self.allowed_resources, "allowed_resources"),
        )
        object.__setattr__(
            self,
            "allowed_operations",
            _freeze_str_tuple(self.allowed_operations, "allowed_operations"),
        )

        # Validate sensitivity levels
        levels = []
        for lvl in self.allowed_sensitivity_levels:
            if isinstance(lvl, str):
                try:
                    lvl = SensitivityLevel(lvl.strip().lower())
                except ValueError as exc:
                    raise InvalidSecurityContractError(
                        f"allowed_sensitivity_levels contains invalid value: {lvl!r}",
                        {"field": "allowed_sensitivity_levels", "value": str(lvl)},
                    ) from exc
            if not isinstance(lvl, SensitivityLevel):
                raise InvalidSecurityContractError(
                    "allowed_sensitivity_levels must contain SensitivityLevel values",
                    {"field": "allowed_sensitivity_levels"},
                )
            levels.append(lvl)
        object.__setattr__(self, "allowed_sensitivity_levels", tuple(levels))

        # Validate autonomy level
        if not isinstance(self.maximum_autonomy_level, int) or isinstance(
            self.maximum_autonomy_level, bool
        ):
            raise InvalidSecurityContractError(
                "maximum_autonomy_level must be a non-negative integer",
                {"field": "maximum_autonomy_level"},
            )
        if self.maximum_autonomy_level < 0:
            raise InvalidSecurityContractError(
                "maximum_autonomy_level cannot be negative",
                {"field": "maximum_autonomy_level"},
            )

        # Validate timestamps
        object.__setattr__(
            self, "created_at", _ensure_tz_aware(self.created_at, "created_at")
        )
        if self.expires_at is not None:
            # Note: expires_at may legitimately be in the past relative to
            # created_at when constructing a representation of a context that
            # was created earlier and has since expired (is_expired detects
            # this). No ordering invariant is enforced here.
            object.__setattr__(
                self, "expires_at", _ensure_tz_aware(self.expires_at, "expires_at")
            )

        # Validate metadata (no secrets)
        object.__setattr__(self, "metadata", _freeze_metadata(dict(self.metadata)))
        _validate_metadata_no_secrets(self.metadata)

    @property
    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return datetime.now(timezone.utc) >= self.expires_at

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "agent_id": self.agent_id,
            "agent_run_id": self.agent_run_id,
            "goal_id": self.goal_id,
            "actor_id": self.actor_id,
            "owner_actor_id": self.owner_actor_id,
            "allowed_domains": list(self.allowed_domains),
            "allowed_resources": list(self.allowed_resources),
            "allowed_operations": list(self.allowed_operations),
            "allowed_sensitivity_levels": [
                lvl.value for lvl in self.allowed_sensitivity_levels
            ],
            "maximum_autonomy_level": self.maximum_autonomy_level,
            "allow_external_access": self.allow_external_access,
            "allow_external_models": self.allow_external_models,
            "allow_memory_write": self.allow_memory_write,
            "allow_goal_creation": self.allow_goal_creation,
            "allow_delegation": self.allow_delegation,
            "allow_publication": self.allow_publication,
            "allow_communications": self.allow_communications,
            "allow_destructive_actions": self.allow_destructive_actions,
            "allow_permission_elevation": self.allow_permission_elevation,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "created_at": self.created_at.isoformat(),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_mapping(cls, mapping: Mapping[str, Any]) -> AgentPermissionContext:
        if not isinstance(mapping, Mapping):
            raise InvalidSecurityContractError("mapping must be a Mapping instance")

        required_keys = {
            "id",
            "agent_id",
            "agent_run_id",
            "goal_id",
            "actor_id",
            "owner_actor_id",
            "allowed_domains",
            "allowed_resources",
            "allowed_operations",
            "allowed_sensitivity_levels",
            "maximum_autonomy_level",
        }
        missing = required_keys - set(mapping.keys())
        if missing:
            raise InvalidSecurityContractError(
                f"Missing required fields: {sorted(missing)}"
            )

        def parse_dt(val: Any, name: str) -> datetime | None:
            if val is None:
                return None
            if isinstance(val, datetime):
                return _ensure_tz_aware(val, name)
            if isinstance(val, str):
                parsed = datetime.fromisoformat(val)
                return _ensure_tz_aware(parsed, name)
            raise InvalidSecurityContractError(f"{name} must be datetime or ISO string")

        def parse_required_dt(val: Any, name: str) -> datetime:
            parsed = parse_dt(val, name)
            if parsed is None:
                raise InvalidSecurityContractError(f"{name} is required")
            return parsed

        levels_raw = mapping["allowed_sensitivity_levels"]
        levels = [SensitivityLevel(l) if isinstance(l, str) else l for l in levels_raw]

        return cls(
            id=str(mapping["id"]),
            agent_id=str(mapping["agent_id"]),
            agent_run_id=str(mapping["agent_run_id"]),
            goal_id=str(mapping["goal_id"]),
            actor_id=str(mapping["actor_id"]),
            owner_actor_id=str(mapping["owner_actor_id"]),
            allowed_domains=tuple(mapping["allowed_domains"]),
            allowed_resources=tuple(mapping["allowed_resources"]),
            allowed_operations=tuple(mapping["allowed_operations"]),
            allowed_sensitivity_levels=tuple(levels),
            maximum_autonomy_level=int(mapping["maximum_autonomy_level"]),
            allow_external_access=bool(mapping.get("allow_external_access", False)),
            allow_external_models=bool(mapping.get("allow_external_models", False)),
            allow_memory_write=bool(mapping.get("allow_memory_write", False)),
            allow_goal_creation=bool(mapping.get("allow_goal_creation", False)),
            allow_delegation=bool(mapping.get("allow_delegation", False)),
            allow_publication=bool(mapping.get("allow_publication", False)),
            allow_communications=bool(mapping.get("allow_communications", False)),
            allow_destructive_actions=bool(
                mapping.get("allow_destructive_actions", False)
            ),
            allow_permission_elevation=bool(
                mapping.get("allow_permission_elevation", False)
            ),
            expires_at=parse_dt(mapping.get("expires_at"), "expires_at"),
            created_at=parse_required_dt(mapping["created_at"], "created_at"),
            metadata=MappingProxyType(dict(mapping.get("metadata", {}))),
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentPermissionContext:
        return cls.from_mapping(data)


# ── PermissionCheckRequest ────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class PermissionCheckRequest:
    """
    Request to evaluate a permission check against the authorization boundary.
    """

    agent_id: str | None = None
    agent_run_id: str | None = None
    goal_id: str | None = None
    actor_id: str | None = None
    operation: str | None = None
    domain: str | None = None
    resources: tuple[str, ...] = ()
    sensitivity: SensitivityLevel | None = None
    required_autonomy_level: int | None = None
    external_access: bool = False
    external_model: bool = False
    memory_write: bool = False
    goal_creation: bool = False
    delegation: bool = False
    publication: bool = False
    communications: bool = False
    destructive_action: bool = False
    requested_elevation: bool = False
    required_budget: tuple[str, ...] = ()
    required_locks: tuple[str, ...] = ()
    required_checkpoints: tuple[str, ...] = ()
    metadata: MappingProxyType[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )

    def __post_init__(self) -> None:
        if self.agent_id is not None:
            object.__setattr__(
                self, "agent_id", _validate_identifier(self.agent_id, "agent_id")
            )
        if self.agent_run_id is not None:
            object.__setattr__(
                self,
                "agent_run_id",
                _validate_identifier(self.agent_run_id, "agent_run_id"),
            )
        if self.goal_id is not None:
            object.__setattr__(
                self, "goal_id", _validate_identifier(self.goal_id, "goal_id")
            )
        if self.actor_id is not None:
            object.__setattr__(
                self, "actor_id", _validate_identifier(self.actor_id, "actor_id")
            )
        if self.operation is not None:
            object.__setattr__(
                self, "operation", _validate_non_empty_str(self.operation, "operation")
            )
        if self.domain is not None:
            object.__setattr__(
                self, "domain", _validate_non_empty_str(self.domain, "domain")
            )
        if self.sensitivity is not None:
            object.__setattr__(
                self,
                "sensitivity",
                _validate_sensitivity_level(self.sensitivity, "sensitivity"),
            )
        if self.required_autonomy_level is not None:
            if not isinstance(self.required_autonomy_level, int) or isinstance(
                self.required_autonomy_level, bool
            ):
                raise InvalidSecurityContractError(
                    "required_autonomy_level must be a non-negative integer",
                    {"field": "required_autonomy_level"},
                )
            if self.required_autonomy_level < 0:
                raise InvalidSecurityContractError(
                    "required_autonomy_level cannot be negative",
                    {"field": "required_autonomy_level"},
                )

        object.__setattr__(
            self, "resources", _freeze_str_tuple(self.resources, "resources")
        )
        object.__setattr__(
            self,
            "required_budget",
            _freeze_str_tuple(self.required_budget, "required_budget"),
        )
        object.__setattr__(
            self,
            "required_locks",
            _freeze_str_tuple(self.required_locks, "required_locks"),
        )
        object.__setattr__(
            self,
            "required_checkpoints",
            _freeze_str_tuple(self.required_checkpoints, "required_checkpoints"),
        )
        object.__setattr__(self, "metadata", _freeze_metadata(dict(self.metadata)))
        _validate_metadata_no_secrets(self.metadata)

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "agent_run_id": self.agent_run_id,
            "goal_id": self.goal_id,
            "actor_id": self.actor_id,
            "operation": self.operation,
            "domain": self.domain,
            "resources": list(self.resources),
            "sensitivity": self.sensitivity.value if self.sensitivity else None,
            "required_autonomy_level": self.required_autonomy_level,
            "external_access": self.external_access,
            "external_model": self.external_model,
            "memory_write": self.memory_write,
            "goal_creation": self.goal_creation,
            "delegation": self.delegation,
            "publication": self.publication,
            "communications": self.communications,
            "destructive_action": self.destructive_action,
            "requested_elevation": self.requested_elevation,
            "required_budget": list(self.required_budget),
            "required_locks": list(self.required_locks),
            "required_checkpoints": list(self.required_checkpoints),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_mapping(cls, mapping: Mapping[str, Any]) -> PermissionCheckRequest:
        if not isinstance(mapping, Mapping):
            raise InvalidSecurityContractError("mapping must be a Mapping instance")

        sens = mapping.get("sensitivity")
        if isinstance(sens, str):
            sens = SensitivityLevel(sens.strip().lower())

        return cls(
            agent_id=mapping.get("agent_id"),
            agent_run_id=mapping.get("agent_run_id"),
            goal_id=mapping.get("goal_id"),
            actor_id=mapping.get("actor_id"),
            operation=mapping.get("operation"),
            domain=mapping.get("domain"),
            resources=tuple(mapping.get("resources", ())),
            sensitivity=sens,
            required_autonomy_level=mapping.get("required_autonomy_level"),
            external_access=bool(mapping.get("external_access", False)),
            external_model=bool(mapping.get("external_model", False)),
            memory_write=bool(mapping.get("memory_write", False)),
            goal_creation=bool(mapping.get("goal_creation", False)),
            delegation=bool(mapping.get("delegation", False)),
            publication=bool(mapping.get("publication", False)),
            communications=bool(mapping.get("communications", False)),
            destructive_action=bool(mapping.get("destructive_action", False)),
            requested_elevation=bool(mapping.get("requested_elevation", False)),
            required_budget=tuple(mapping.get("required_budget", ())),
            required_locks=tuple(mapping.get("required_locks", ())),
            required_checkpoints=tuple(mapping.get("required_checkpoints", ())),
            metadata=MappingProxyType(dict(mapping.get("metadata", {}))),
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PermissionCheckRequest:
        return cls.from_mapping(data)


# ── PermissionDecision ────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class PermissionDecision:
    """
    Structured authorization decision returned by the security service.
    """

    effect: PermissionEffect
    reason_codes: tuple[str, ...]
    denied_dimensions: tuple[str, ...]
    required_approvals: tuple[str, ...]
    obligations: tuple[str, ...]
    effective_constraints: MappingProxyType[str, Any]
    evaluated_context_id: str
    timestamp: datetime
    correlation_id: str | None = None
    causation_id: str | None = None
    metadata: MappingProxyType[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "effect",
            _validate_permission_effect(self.effect, "effect"),
        )
        object.__setattr__(
            self,
            "reason_codes",
            _freeze_str_tuple(self.reason_codes, "reason_codes"),
        )
        object.__setattr__(
            self,
            "denied_dimensions",
            _freeze_str_tuple(self.denied_dimensions, "denied_dimensions"),
        )
        object.__setattr__(
            self,
            "required_approvals",
            _freeze_str_tuple(self.required_approvals, "required_approvals"),
        )
        object.__setattr__(
            self, "obligations", _freeze_str_tuple(self.obligations, "obligations")
        )
        object.__setattr__(
            self,
            "effective_constraints",
            _freeze_metadata(dict(self.effective_constraints)),
        )
        object.__setattr__(
            self,
            "evaluated_context_id",
            _validate_identifier(self.evaluated_context_id, "evaluated_context_id"),
        )
        object.__setattr__(
            self,
            "timestamp",
            _ensure_tz_aware(self.timestamp, "timestamp"),
        )
        if self.correlation_id is not None:
            object.__setattr__(
                self,
                "correlation_id",
                _validate_identifier(self.correlation_id, "correlation_id"),
            )
        if self.causation_id is not None:
            object.__setattr__(
                self,
                "causation_id",
                _validate_identifier(self.causation_id, "causation_id"),
            )
        object.__setattr__(self, "metadata", _freeze_metadata(dict(self.metadata)))
        _validate_metadata_no_secrets(self.metadata)

    @property
    def is_allowed(self) -> bool:
        return self.effect in {
            PermissionEffect.ALLOW,
            PermissionEffect.ALLOW_WITH_CONSTRAINTS,
        }

    @property
    def is_denied(self) -> bool:
        return not self.is_allowed

    def to_dict(self) -> dict[str, Any]:
        return {
            "effect": self.effect.value,
            "reason_codes": list(self.reason_codes),
            "denied_dimensions": list(self.denied_dimensions),
            "required_approvals": list(self.required_approvals),
            "obligations": list(self.obligations),
            "effective_constraints": dict(self.effective_constraints),
            "evaluated_context_id": self.evaluated_context_id,
            "timestamp": self.timestamp.isoformat(),
            "correlation_id": self.correlation_id,
            "causation_id": self.causation_id,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_mapping(cls, mapping: Mapping[str, Any]) -> PermissionDecision:
        if not isinstance(mapping, Mapping):
            raise InvalidSecurityContractError("mapping must be a Mapping instance")

        required_keys = {
            "effect",
            "reason_codes",
            "denied_dimensions",
            "required_approvals",
            "obligations",
            "effective_constraints",
            "evaluated_context_id",
            "timestamp",
        }
        missing = required_keys - set(mapping.keys())
        if missing:
            raise InvalidSecurityContractError(
                f"Missing required fields: {sorted(missing)}"
            )

        def parse_dt(val: Any, name: str) -> datetime:
            if isinstance(val, datetime):
                return _ensure_tz_aware(val, name)
            if isinstance(val, str):
                parsed = datetime.fromisoformat(val)
                return _ensure_tz_aware(parsed, name)
            raise InvalidSecurityContractError(f"{name} must be datetime or ISO string")

        return cls(
            effect=mapping["effect"],
            reason_codes=tuple(mapping["reason_codes"]),
            denied_dimensions=tuple(mapping["denied_dimensions"]),
            required_approvals=tuple(mapping["required_approvals"]),
            obligations=tuple(mapping["obligations"]),
            effective_constraints=MappingProxyType(
                dict(mapping["effective_constraints"])
            ),
            evaluated_context_id=str(mapping["evaluated_context_id"]),
            timestamp=parse_dt(mapping["timestamp"], "timestamp"),
            correlation_id=mapping.get("correlation_id"),
            causation_id=mapping.get("causation_id"),
            metadata=MappingProxyType(dict(mapping.get("metadata", {}))),
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PermissionDecision:
        return cls.from_mapping(data)


# ── SecurityAuditEntry ────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class SecurityAuditEntry:
    """
    Immutable audit record of a permission evaluation.

    Never stores secrets or full sensitive content.
    """

    id: str
    permission_context_id: str
    actor_id: str
    agent_id: str
    agent_run_id: str
    goal_id: str | None
    action: str
    resources: tuple[str, ...]
    decision: PermissionEffect
    reason_codes: tuple[str, ...]
    sensitivity: SensitivityLevel | None
    requested_elevation: bool
    prompt_injection_finding: PromptInjectionResult
    kill_switch_state: KillSwitchState
    timestamp: datetime
    trace_id: str | None = None
    correlation_id: str | None = None
    metadata: MappingProxyType[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", _validate_audit_entry_id(self.id, "id"))
        object.__setattr__(
            self,
            "permission_context_id",
            _validate_identifier(self.permission_context_id, "permission_context_id"),
        )
        object.__setattr__(
            self, "actor_id", _validate_identifier(self.actor_id, "actor_id")
        )
        object.__setattr__(
            self, "agent_id", _validate_identifier(self.agent_id, "agent_id")
        )
        object.__setattr__(
            self,
            "agent_run_id",
            _validate_identifier(self.agent_run_id, "agent_run_id"),
        )
        if self.goal_id is not None:
            object.__setattr__(
                self,
                "goal_id",
                _validate_identifier(self.goal_id, "goal_id"),
            )
        object.__setattr__(
            self, "action", _validate_non_empty_str(self.action, "action")
        )
        object.__setattr__(
            self, "resources", _freeze_str_tuple(self.resources, "resources")
        )
        object.__setattr__(
            self,
            "decision",
            _validate_permission_effect(self.decision, "decision"),
        )
        object.__setattr__(
            self,
            "reason_codes",
            _freeze_str_tuple(self.reason_codes, "reason_codes"),
        )
        if self.sensitivity is not None:
            object.__setattr__(
                self,
                "sensitivity",
                _validate_sensitivity_level(self.sensitivity, "sensitivity"),
            )
        if self.trace_id is not None:
            object.__setattr__(
                self,
                "trace_id",
                _validate_identifier(self.trace_id, "trace_id"),
            )
        if self.correlation_id is not None:
            object.__setattr__(
                self,
                "correlation_id",
                _validate_identifier(self.correlation_id, "correlation_id"),
            )
        object.__setattr__(
            self,
            "prompt_injection_finding",
            _validate_prompt_injection_result(
                self.prompt_injection_finding, "prompt_injection_finding"
            ),
        )
        object.__setattr__(
            self,
            "kill_switch_state",
            _validate_kill_switch_state(self.kill_switch_state, "kill_switch_state"),
        )
        object.__setattr__(
            self, "timestamp", _ensure_tz_aware(self.timestamp, "timestamp")
        )
        object.__setattr__(self, "metadata", _freeze_metadata(dict(self.metadata)))
        _validate_metadata_no_secrets(self.metadata)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "permission_context_id": self.permission_context_id,
            "actor_id": self.actor_id,
            "agent_id": self.agent_id,
            "agent_run_id": self.agent_run_id,
            "goal_id": self.goal_id,
            "action": self.action,
            "resources": list(self.resources),
            "decision": self.decision.value,
            "reason_codes": list(self.reason_codes),
            "sensitivity": self.sensitivity.value if self.sensitivity else None,
            "requested_elevation": self.requested_elevation,
            "prompt_injection_finding": self.prompt_injection_finding.value,
            "kill_switch_state": self.kill_switch_state.value,
            "timestamp": self.timestamp.isoformat(),
            "trace_id": self.trace_id,
            "correlation_id": self.correlation_id,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_mapping(cls, mapping: Mapping[str, Any]) -> SecurityAuditEntry:
        if not isinstance(mapping, Mapping):
            raise InvalidSecurityContractError("mapping must be a Mapping instance")

        required_keys = {
            "id",
            "permission_context_id",
            "actor_id",
            "agent_id",
            "agent_run_id",
            "action",
            "resources",
            "decision",
            "reason_codes",
            "requested_elevation",
            "prompt_injection_finding",
            "kill_switch_state",
            "timestamp",
        }
        missing = required_keys - set(mapping.keys())
        if missing:
            raise InvalidSecurityContractError(
                f"Missing required fields: {sorted(missing)}"
            )

        def parse_dt(val: Any, name: str) -> datetime:
            if isinstance(val, datetime):
                return _ensure_tz_aware(val, name)
            if isinstance(val, str):
                parsed = datetime.fromisoformat(val)
                return _ensure_tz_aware(parsed, name)
            raise InvalidSecurityContractError(f"{name} must be datetime or ISO string")

        sens = mapping.get("sensitivity")
        if isinstance(sens, str):
            sens = SensitivityLevel(sens.strip().lower())

        return cls(
            id=str(mapping["id"]),
            permission_context_id=str(mapping["permission_context_id"]),
            actor_id=str(mapping["actor_id"]),
            agent_id=str(mapping["agent_id"]),
            agent_run_id=str(mapping["agent_run_id"]),
            goal_id=mapping.get("goal_id"),
            action=str(mapping["action"]),
            resources=tuple(mapping["resources"]),
            decision=mapping["decision"],
            reason_codes=tuple(mapping["reason_codes"]),
            sensitivity=sens,
            requested_elevation=bool(mapping["requested_elevation"]),
            prompt_injection_finding=mapping["prompt_injection_finding"],
            kill_switch_state=mapping["kill_switch_state"],
            timestamp=parse_dt(mapping["timestamp"], "timestamp"),
            trace_id=mapping.get("trace_id"),
            correlation_id=mapping.get("correlation_id"),
            metadata=MappingProxyType(dict(mapping.get("metadata", {}))),
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SecurityAuditEntry:
        return cls.from_mapping(data)


# ── KillSwitchState / KillSwitchReport ────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class KillSwitchReport:
    """
    Comprehensive report of a kill switch activation and its effects.
    """

    id: str
    state: KillSwitchState
    affected_runs: tuple[str, ...]
    blocked_operations: tuple[str, ...]
    released_locks: tuple[str, ...]
    canceled_reservations: tuple[str, ...]
    in_progress_operations_marked: tuple[str, ...]
    recovery_requested: bool
    errors: tuple[str, ...]
    activated_at: datetime
    activated_by: str
    reason: str
    released_at: datetime | None = None
    released_by: str | None = None
    failed_at: datetime | None = None
    metadata: MappingProxyType[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", _validate_kill_switch_report_id(self.id, "id"))
        object.__setattr__(
            self,
            "state",
            _validate_kill_switch_state(self.state, "state"),
        )
        object.__setattr__(
            self,
            "affected_runs",
            _freeze_str_tuple(self.affected_runs, "affected_runs"),
        )
        object.__setattr__(
            self,
            "blocked_operations",
            _freeze_str_tuple(self.blocked_operations, "blocked_operations"),
        )
        object.__setattr__(
            self,
            "released_locks",
            _freeze_str_tuple(self.released_locks, "released_locks"),
        )
        object.__setattr__(
            self,
            "canceled_reservations",
            _freeze_str_tuple(self.canceled_reservations, "canceled_reservations"),
        )
        object.__setattr__(
            self,
            "in_progress_operations_marked",
            _freeze_str_tuple(
                self.in_progress_operations_marked, "in_progress_operations_marked"
            ),
        )
        object.__setattr__(
            self,
            "errors",
            _freeze_str_tuple(self.errors, "errors"),
        )
        object.__setattr__(
            self, "activated_at", _ensure_tz_aware(self.activated_at, "activated_at")
        )
        object.__setattr__(
            self,
            "activated_by",
            _validate_identifier(self.activated_by, "activated_by"),
        )
        object.__setattr__(
            self, "reason", _validate_non_empty_str(self.reason, "reason")
        )
        if self.released_at is not None:
            object.__setattr__(
                self,
                "released_at",
                _ensure_tz_aware(self.released_at, "released_at"),
            )
            if self.released_by is None:
                raise InvalidSecurityContractError(
                    "released_by is required when released_at is set",
                    {"field": "released_by"},
                )
            object.__setattr__(
                self,
                "released_by",
                _validate_identifier(self.released_by, "released_by"),
            )
        if self.failed_at is not None:
            object.__setattr__(
                self,
                "failed_at",
                _ensure_tz_aware(self.failed_at, "failed_at"),
            )
        object.__setattr__(self, "metadata", _freeze_metadata(dict(self.metadata)))
        _validate_metadata_no_secrets(self.metadata)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "state": self.state.value,
            "affected_runs": list(self.affected_runs),
            "blocked_operations": list(self.blocked_operations),
            "released_locks": list(self.released_locks),
            "canceled_reservations": list(self.canceled_reservations),
            "in_progress_operations_marked": list(self.in_progress_operations_marked),
            "recovery_requested": self.recovery_requested,
            "errors": list(self.errors),
            "activated_at": self.activated_at.isoformat(),
            "activated_by": self.activated_by,
            "reason": self.reason,
            "released_at": self.released_at.isoformat() if self.released_at else None,
            "released_by": self.released_by,
            "failed_at": self.failed_at.isoformat() if self.failed_at else None,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_mapping(cls, mapping: Mapping[str, Any]) -> KillSwitchReport:
        if not isinstance(mapping, Mapping):
            raise InvalidSecurityContractError("mapping must be a Mapping instance")

        required_keys = {
            "id",
            "state",
            "affected_runs",
            "blocked_operations",
            "released_locks",
            "canceled_reservations",
            "in_progress_operations_marked",
            "recovery_requested",
            "errors",
            "activated_at",
            "activated_by",
            "reason",
        }
        missing = required_keys - set(mapping.keys())
        if missing:
            raise InvalidSecurityContractError(
                f"Missing required fields: {sorted(missing)}"
            )

        def parse_dt(val: Any, name: str) -> datetime | None:
            if val is None:
                return None
            if isinstance(val, datetime):
                return _ensure_tz_aware(val, name)
            if isinstance(val, str):
                parsed = datetime.fromisoformat(val)
                return _ensure_tz_aware(parsed, name)
            raise InvalidSecurityContractError(f"{name} must be datetime or ISO string")

        def parse_required_dt(val: Any, name: str) -> datetime:
            parsed = parse_dt(val, name)
            if parsed is None:
                raise InvalidSecurityContractError(f"{name} is required")
            return parsed

        return cls(
            id=str(mapping["id"]),
            state=mapping["state"],
            affected_runs=tuple(mapping["affected_runs"]),
            blocked_operations=tuple(mapping["blocked_operations"]),
            released_locks=tuple(mapping["released_locks"]),
            canceled_reservations=tuple(mapping["canceled_reservations"]),
            in_progress_operations_marked=tuple(
                mapping["in_progress_operations_marked"]
            ),
            recovery_requested=bool(mapping["recovery_requested"]),
            errors=tuple(mapping["errors"]),
            activated_at=parse_required_dt(mapping["activated_at"], "activated_at"),
            activated_by=str(mapping["activated_by"]),
            reason=str(mapping["reason"]),
            released_at=parse_dt(mapping.get("released_at"), "released_at"),
            released_by=mapping.get("released_by"),
            failed_at=parse_dt(mapping.get("failed_at"), "failed_at"),
            metadata=MappingProxyType(dict(mapping.get("metadata", {}))),
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> KillSwitchReport:
        return cls.from_mapping(data)


# ── UntrustedContentFinding / PromptInjectionAssessment ───────────────────────


@dataclass(frozen=True, slots=True)
class UntrustedContentFinding:
    """
    Structured finding from prompt injection analysis.
    """

    result: PromptInjectionResult
    categories: tuple[str, ...]
    matched_patterns: tuple[str, ...]
    confidence: float
    metadata: MappingProxyType[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "result",
            _validate_prompt_injection_result(self.result, "result"),
        )
        object.__setattr__(
            self,
            "categories",
            _freeze_str_tuple(self.categories, "categories"),
        )
        object.__setattr__(
            self,
            "matched_patterns",
            _freeze_str_tuple(self.matched_patterns, "matched_patterns"),
        )
        if not isinstance(self.confidence, (int, float)):
            raise InvalidSecurityContractError(
                "confidence must be a number",
                {"field": "confidence"},
            )
        if not 0.0 <= self.confidence <= 1.0:
            raise InvalidSecurityContractError(
                "confidence must be between 0.0 and 1.0",
                {"field": "confidence", "value": self.confidence},
            )
        object.__setattr__(self, "confidence", float(self.confidence))
        object.__setattr__(self, "metadata", _freeze_metadata(dict(self.metadata)))
        _validate_metadata_no_secrets(self.metadata)

    def to_dict(self) -> dict[str, Any]:
        return {
            "result": self.result.value,
            "categories": list(self.categories),
            "matched_patterns": list(self.matched_patterns),
            "confidence": self.confidence,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_mapping(cls, mapping: Mapping[str, Any]) -> UntrustedContentFinding:
        if not isinstance(mapping, Mapping):
            raise InvalidSecurityContractError("mapping must be a Mapping instance")

        required_keys = {
            "result",
            "categories",
            "matched_patterns",
            "confidence",
        }
        missing = required_keys - set(mapping.keys())
        if missing:
            raise InvalidSecurityContractError(
                f"Missing required fields: {sorted(missing)}"
            )

        return cls(
            result=mapping["result"],
            categories=tuple(mapping["categories"]),
            matched_patterns=tuple(mapping["matched_patterns"]),
            confidence=float(mapping["confidence"]),
            metadata=MappingProxyType(dict(mapping.get("metadata", {}))),
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> UntrustedContentFinding:
        return cls.from_mapping(data)


@dataclass(frozen=True, slots=True)
class PromptInjectionAssessment:
    """
    Assessment of potentially untrusted content for prompt injection.
    """

    content_id: str
    finding: UntrustedContentFinding
    assessed_at: datetime
    assessor: str
    metadata: MappingProxyType[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "content_id",
            _validate_identifier(self.content_id, "content_id"),
        )
        object.__setattr__(
            self,
            "assessed_at",
            _ensure_tz_aware(self.assessed_at, "assessed_at"),
        )
        object.__setattr__(
            self, "assessor", _validate_identifier(self.assessor, "assessor")
        )
        object.__setattr__(self, "metadata", _freeze_metadata(dict(self.metadata)))
        _validate_metadata_no_secrets(self.metadata)

    def to_dict(self) -> dict[str, Any]:
        return {
            "content_id": self.content_id,
            "finding": self.finding.to_dict(),
            "assessed_at": self.assessed_at.isoformat(),
            "assessor": self.assessor,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_mapping(cls, mapping: Mapping[str, Any]) -> PromptInjectionAssessment:
        if not isinstance(mapping, Mapping):
            raise InvalidSecurityContractError("mapping must be a Mapping instance")

        required_keys = {
            "content_id",
            "finding",
            "assessed_at",
            "assessor",
        }
        missing = required_keys - set(mapping.keys())
        if missing:
            raise InvalidSecurityContractError(
                f"Missing required fields: {sorted(missing)}"
            )

        def parse_dt(val: Any, name: str) -> datetime:
            if isinstance(val, datetime):
                return _ensure_tz_aware(val, name)
            if isinstance(val, str):
                parsed = datetime.fromisoformat(val)
                return _ensure_tz_aware(parsed, name)
            raise InvalidSecurityContractError(f"{name} must be datetime or ISO string")

        finding_raw = mapping["finding"]
        if isinstance(finding_raw, Mapping):
            finding = UntrustedContentFinding.from_mapping(finding_raw)
        elif isinstance(finding_raw, UntrustedContentFinding):
            finding = finding_raw
        else:
            raise InvalidSecurityContractError(
                "finding must be an UntrustedContentFinding or Mapping"
            )

        return cls(
            content_id=str(mapping["content_id"]),
            finding=finding,
            assessed_at=parse_dt(mapping["assessed_at"], "assessed_at"),
            assessor=str(mapping["assessor"]),
            metadata=MappingProxyType(dict(mapping.get("metadata", {}))),
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PromptInjectionAssessment:
        return cls.from_mapping(data)


# ── Factory helpers ───────────────────────────────────────────────────────────


def generate_permission_context_id() -> str:
    return f"perm-ctx-{uuid.uuid4().hex[:16]}"


def generate_audit_entry_id() -> str:
    return f"audit-{uuid.uuid4().hex[:16]}"


def generate_kill_switch_report_id() -> str:
    return f"ks-report-{uuid.uuid4().hex[:16]}"


# ── Public API ────────────────────────────────────────────────────────────────

__all__ = [
    "AgentPermissionContext",
    "KillSwitchReport",
    "PermissionCheckRequest",
    "PermissionDecision",
    "PromptInjectionAssessment",
    "SecurityAuditEntry",
    "UntrustedContentFinding",
    "generate_audit_entry_id",
    "generate_kill_switch_report_id",
    "generate_permission_context_id",
]
