"""Phase 9.9 – Autonomy Level Contracts.

Defines the immutable, serializable, strictly validated contracts that
constitute the formal Autonomy Level subsystem of the Autonomous Agent
Runtime:

* :class:`AutonomyProfile` — canonical, level-bound capability matrix.
* :class:`AutonomyEvaluationRequest` — structured request to evaluate a
  capability against a level and an operation profile.
* :class:`AutonomyEvaluationResult` — explicit, fail-safe evaluation
  outcome with reason codes, warnings, and metadata.
* :class:`AutonomyTransitionRequest`,
  :class:`AutonomyTransitionResult`,
  :class:`AutonomyTransitionRecord` — explicit contracts for
  governance and audit of level transitions during a run.

All contracts are:

* ``@dataclass(frozen=True, slots=True)``
* strictly validated in ``__post_init__``;
* serializable via ``serialize()`` / ``to_dict()``;
* reconstructible from mapping via ``from_mapping()`` / ``from_dict()``;
* immutable.
"""

from __future__ import annotations

import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from types import MappingProxyType
from typing import Any

from .enums import (
    AgentAutonomyLevel,
    AutonomyCapability,
    AutonomyDecision,
    AutonomyTransitionReason,
)
from .errors import (
    AutonomyCapabilityError,
    AutonomyLevelError,
    InvalidAutonomyContractError,
)

# ── Helpers ──────────────────────────────────────────────────────────────────


def _now_utc() -> datetime:
    """Return a timezone-aware UTC ``datetime``."""
    return datetime.now(timezone.utc)


def _ensure_aware_dt(val: Any, field_name: str) -> datetime:
    """Ensure ``val`` is a timezone-aware ``datetime``."""
    if not isinstance(val, datetime):
        raise InvalidAutonomyContractError(
            f"{field_name} must be a datetime instance, got {type(val).__name__}"
        )
    if val.tzinfo is None:
        raise InvalidAutonomyContractError(f"{field_name} must be timezone-aware")
    return val


def _parse_dt(val: Any, field_name: str) -> datetime:
    """Parse ISO string or datetime into a timezone-aware datetime."""
    if isinstance(val, datetime):
        return _ensure_aware_dt(val, field_name)
    if isinstance(val, str):
        try:
            parsed = datetime.fromisoformat(val)
        except ValueError as exc:
            raise InvalidAutonomyContractError(
                f"Invalid isoformat datetime string for {field_name}: {val!r}"
            ) from exc
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    raise InvalidAutonomyContractError(
        f"{field_name} must be an ISO string or datetime instance"
    )


def _validate_non_empty_str(val: Any, field_name: str) -> str:
    """Validate that ``val`` is a non-empty string."""
    if not isinstance(val, str) or not val.strip():
        raise InvalidAutonomyContractError(f"{field_name} must be a non-empty string")
    return val.strip()


def _freeze_metadata(meta: Any) -> MappingProxyType[str, Any]:
    """Validate and freeze metadata into a ``MappingProxyType``."""
    if meta is None:
        return MappingProxyType({})
    if not isinstance(meta, Mapping):
        raise InvalidAutonomyContractError("metadata must be a Mapping")
    result: dict[str, Any] = {}
    for k, v in meta.items():
        if not isinstance(k, str):
            raise InvalidAutonomyContractError("metadata keys must be strings")
        result[k] = v
    return MappingProxyType(result)


def _freeze_capability_tuple(
    items: Any, field_name: str
) -> tuple[AutonomyCapability, ...]:
    """Validate and freeze a sequence of ``AutonomyCapability`` values."""
    if items is None:
        return ()
    if isinstance(items, (str, bytes)):
        raise InvalidAutonomyContractError(
            f"{field_name} must be a sequence of AutonomyCapability"
        )
    if not isinstance(items, (tuple, list, set)) and not isinstance(items, Sequence):
        raise InvalidAutonomyContractError(
            f"{field_name} must be a sequence of AutonomyCapability"
        )
    result: list[AutonomyCapability] = []
    for item in items:
        if isinstance(item, AutonomyCapability):
            result.append(item)
        elif isinstance(item, str):
            try:
                result.append(AutonomyCapability(item))
            except ValueError as exc:
                raise AutonomyCapabilityError(
                    f"Unknown AutonomyCapability string: {item!r}"
                ) from exc
        else:
            raise InvalidAutonomyContractError(
                f"{field_name} entries must be AutonomyCapability, got "
                f"{type(item).__name__}"
            )
    return tuple(result)


def _freeze_str_tuple(
    seq: Any, field_name: str, allow_empty: bool = True
) -> tuple[str, ...]:
    """Validate and convert a sequence to a tuple of non-empty strings."""
    if seq is None:
        if allow_empty:
            return ()
        raise InvalidAutonomyContractError(f"{field_name} cannot be None")
    if isinstance(seq, (str, bytes)):
        raise InvalidAutonomyContractError(
            f"{field_name} must be a sequence of strings, not a single string"
        )
    if not isinstance(seq, (tuple, list, set)) and not isinstance(seq, Sequence):
        raise InvalidAutonomyContractError(
            f"{field_name} must be a sequence of strings"
        )
    result: list[str] = []
    for item in seq:
        if not isinstance(item, str) or not item.strip():
            raise InvalidAutonomyContractError(
                f"All items in {field_name} must be non-empty strings"
            )
        result.append(item.strip())
    return tuple(result)


def coerce_autonomy_level(value: Any) -> AgentAutonomyLevel:
    """Coerce ``value`` to ``AgentAutonomyLevel`` preserving integer compat.

    Accepted:

    * ``AgentAutonomyLevel`` instances (returned as-is);
    * integers in ``[0, 4]`` (returned as the matching enum member).

    Rejected:

    * ``bool`` (since ``bool`` is a subclass of ``int`` in Python);
    * integers outside ``[0, 4]``;
    * arbitrary strings (e.g. ``"high"``);
    * non-integer types.
    """
    if isinstance(value, bool):
        raise AutonomyLevelError(
            f"autonomy_level must be an integer in [0, 4], got bool: {value!r}"
        )
    if isinstance(value, AgentAutonomyLevel):
        return value
    if isinstance(value, int):
        try:
            return AgentAutonomyLevel(value)
        except ValueError as exc:
            raise AutonomyLevelError(
                f"autonomy_level must be in [0, 4], got {value!r}"
            ) from exc
    raise AutonomyLevelError(
        f"autonomy_level must be an integer in [0, 4] or "
        f"AgentAutonomyLevel, got {type(value).__name__}: {value!r}"
    )


# ── Identifier generators ───────────────────────────────────────────────────


def generate_autonomy_profile_id(level: AgentAutonomyLevel | int) -> str:
    """Return a deterministic identifier for an autonomy profile."""
    lvl = coerce_autonomy_level(level)
    return f"autonomy-profile-{lvl.value}"


def generate_autonomy_request_id() -> str:
    """Return a unique identifier for an ``AutonomyEvaluationRequest``."""
    return f"autonomy-req-{uuid.uuid4().hex}"


def generate_autonomy_result_id() -> str:
    """Return a unique identifier for an ``AutonomyEvaluationResult``."""
    return f"autonomy-res-{uuid.uuid4().hex}"


def generate_autonomy_transition_id() -> str:
    """Return a unique identifier for an ``AutonomyTransitionRecord``."""
    return f"autonomy-trn-{uuid.uuid4().hex}"


# ── AutonomyProfile ─────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class AutonomyProfile:
    """Canonical, level-bound capability matrix.

    Profiles are static, deterministic, and derived solely from an
    :class:`AgentAutonomyLevel`. They describe what a level can do,
    what it must request approval for, and what is structurally
    prohibited at that level.

    Invariants:

    * ``allowed``, ``requires_approval`` and ``prohibited`` sets are
      disjoint;
    * a capability that requires approval is implicitly not prohibited;
    * ``allow_execution`` is False for levels 0 and 1.
    """

    level: AgentAutonomyLevel
    name: str
    description: str
    allowed: tuple[AutonomyCapability, ...]
    requires_approval: tuple[AutonomyCapability, ...]
    prohibited: tuple[AutonomyCapability, ...]
    allow_execution: bool
    requires_rollback_for_mutation: bool
    requires_supervision: bool
    profile_id: str = ""
    metadata: MappingProxyType[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )

    def __post_init__(self) -> None:
        lvl = coerce_autonomy_level(self.level)
        object.__setattr__(self, "level", lvl)

        _validate_non_empty_str(self.name, "name")
        _validate_non_empty_str(self.description, "description")

        allowed = _freeze_capability_tuple(self.allowed, "allowed")
        requires = _freeze_capability_tuple(self.requires_approval, "requires_approval")
        prohibited = _freeze_capability_tuple(self.prohibited, "prohibited")

        # Disjointness checks
        overlap_allowed_prohibited = set(allowed) & set(prohibited)
        if overlap_allowed_prohibited:
            raise InvalidAutonomyContractError(
                "AutonomyProfile cannot allow and prohibit the same capability: "
                f"{sorted(c.value for c in overlap_allowed_prohibited)}"
            )
        overlap_allowed_requires = set(allowed) & set(requires)
        if overlap_allowed_requires:
            raise InvalidAutonomyContractError(
                "AutonomyProfile cannot both allow a capability and require "
                "approval for it: "
                f"{sorted(c.value for c in overlap_allowed_requires)}"
            )
        overlap_requires_prohibited = set(requires) & set(prohibited)
        if overlap_requires_prohibited:
            raise InvalidAutonomyContractError(
                "AutonomyProfile cannot both prohibit a capability and require "
                "approval for it: "
                f"{sorted(c.value for c in overlap_requires_prohibited)}"
            )

        if not isinstance(self.allow_execution, bool):
            raise InvalidAutonomyContractError("allow_execution must be a boolean")
        if not isinstance(self.requires_rollback_for_mutation, bool):
            raise InvalidAutonomyContractError(
                "requires_rollback_for_mutation must be a boolean"
            )
        if not isinstance(self.requires_supervision, bool):
            raise InvalidAutonomyContractError("requires_supervision must be a boolean")

        # Structural invariants for levels 0 and 1
        if lvl.value <= 1 and self.allow_execution:
            raise InvalidAutonomyContractError(
                f"Autonomy level {lvl.value} must not allow execution"
            )
        # Reversible-execution level must require rollback for mutations
        if (
            lvl.value == 2
            and not self.requires_rollback_for_mutation
            and any(
                c in allowed
                for c in (
                    AutonomyCapability.EXECUTE_REVERSIBLE,
                    AutonomyCapability.EXECUTE_WORKFLOW,
                )
            )
        ):
            raise InvalidAutonomyContractError(
                "Autonomy level 2 (reversible execution) must require "
                "rollback for mutations"
            )

        object.__setattr__(self, "allowed", allowed)
        object.__setattr__(self, "requires_approval", requires)
        object.__setattr__(self, "prohibited", prohibited)
        if not self.profile_id:
            object.__setattr__(self, "profile_id", generate_autonomy_profile_id(lvl))
        else:
            object.__setattr__(self, "profile_id", self.profile_id.strip())
        object.__setattr__(self, "metadata", _freeze_metadata(self.metadata))

    def allows(self, capability: AutonomyCapability | str) -> bool:
        """Return True if ``capability`` is permitted by the profile."""
        cap = _as_capability(capability)
        return cap in self.allowed

    def prohibits(self, capability: AutonomyCapability | str) -> bool:
        """Return True if ``capability`` is prohibited by the profile."""
        cap = _as_capability(capability)
        return cap in self.prohibited

    def requires_approval_for(self, capability: AutonomyCapability | str) -> bool:
        """Return True if ``capability`` requires explicit approval."""
        cap = _as_capability(capability)
        return cap in self.requires_approval

    def serialize(self) -> dict[str, Any]:
        """Serialize the profile to a JSON-compatible dictionary."""
        return {
            "profile_id": self.profile_id,
            "level": int(self.level),
            "name": self.name,
            "description": self.description,
            "allowed": [c.value for c in self.allowed],
            "requires_approval": [c.value for c in self.requires_approval],
            "prohibited": [c.value for c in self.prohibited],
            "allow_execution": self.allow_execution,
            "requires_rollback_for_mutation": self.requires_rollback_for_mutation,
            "requires_supervision": self.requires_supervision,
            "metadata": dict(self.metadata),
        }

    def to_dict(self) -> dict[str, Any]:
        """Alias for :meth:`serialize`."""
        return self.serialize()

    @classmethod
    def from_mapping(cls, mapping: Mapping[str, Any]) -> AutonomyProfile:
        """Reconstruct an ``AutonomyProfile`` from a mapping."""
        if not isinstance(mapping, Mapping):
            raise InvalidAutonomyContractError("mapping must be a Mapping")
        required = {"level", "name", "description"}
        missing = required - set(mapping.keys())
        if missing:
            raise InvalidAutonomyContractError(
                f"Missing required fields in mapping: {sorted(missing)}"
            )
        return cls(
            level=coerce_autonomy_level(mapping["level"]),
            name=str(mapping["name"]),
            description=str(mapping["description"]),
            allowed=tuple(mapping.get("allowed", ())),
            requires_approval=tuple(mapping.get("requires_approval", ())),
            prohibited=tuple(mapping.get("prohibited", ())),
            allow_execution=bool(mapping.get("allow_execution", False)),
            requires_rollback_for_mutation=bool(
                mapping.get("requires_rollback_for_mutation", False)
            ),
            requires_supervision=bool(mapping.get("requires_supervision", False)),
            profile_id=str(mapping.get("profile_id", "")),
            metadata=_freeze_metadata(mapping.get("metadata") or {}),
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AutonomyProfile:
        """Alias for :meth:`from_mapping`."""
        return cls.from_mapping(data)


def _as_capability(value: Any) -> AutonomyCapability:
    """Coerce ``value`` to :class:`AutonomyCapability` or raise."""
    if isinstance(value, AutonomyCapability):
        return value
    if isinstance(value, str):
        try:
            return AutonomyCapability(value)
        except ValueError as exc:
            raise AutonomyCapabilityError(
                f"Unknown AutonomyCapability string: {value!r}"
            ) from exc
    raise AutonomyCapabilityError(
        f"Capability must be AutonomyCapability or str, got {type(value).__name__}"
    )


# ── AutonomyEvaluationRequest ──────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class AutonomyEvaluationRequest:
    """Structured request to evaluate a capability against a level.

    The request carries the structural characteristics of the
    operation being attempted so the evaluator can produce a
    deterministic, fail-safe decision.
    """

    id: str
    agent_run_id: str
    autonomy_level: AgentAutonomyLevel | int
    capability: AutonomyCapability | str
    operation_name: str | None = None
    is_mutation: bool = False
    is_reversible: bool = True
    is_destructive: bool = False
    is_external: bool = False
    is_sensitive: bool = False
    requires_spend: bool = False
    changes_permissions: bool = False
    changes_policy: bool = False
    policy_decision: str | None = None
    approval_present: bool = False
    validation_passed: bool = False
    rollback_available: bool = False
    created_at: datetime = field(default_factory=_now_utc)
    metadata: MappingProxyType[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )

    def __post_init__(self) -> None:
        _validate_non_empty_str(self.id, "id")
        _validate_non_empty_str(self.agent_run_id, "agent_run_id")
        object.__setattr__(
            self, "autonomy_level", coerce_autonomy_level(self.autonomy_level)
        )
        object.__setattr__(self, "capability", _as_capability(self.capability))

        for f_name in (
            "is_mutation",
            "is_reversible",
            "is_destructive",
            "is_external",
            "is_sensitive",
            "requires_spend",
            "changes_permissions",
            "changes_policy",
            "approval_present",
            "validation_passed",
            "rollback_available",
        ):
            if not isinstance(getattr(self, f_name), bool):
                raise InvalidAutonomyContractError(f"{f_name} must be a boolean")

        if self.operation_name is not None:
            object.__setattr__(
                self,
                "operation_name",
                _validate_non_empty_str(self.operation_name, "operation_name"),
            )

        if self.policy_decision is not None:
            object.__setattr__(
                self, "policy_decision", str(self.policy_decision).strip()
            )
            if not object.__getattribute__(self, "policy_decision"):
                object.__setattr__(self, "policy_decision", None)

        object.__setattr__(
            self, "created_at", _ensure_aware_dt(self.created_at, "created_at")
        )
        object.__setattr__(self, "metadata", _freeze_metadata(self.metadata))

    def serialize(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "agent_run_id": self.agent_run_id,
            "autonomy_level": int(self.autonomy_level),
            "capability": self.capability.value
            if isinstance(self.capability, AutonomyCapability)
            else self.capability,
            "operation_name": self.operation_name,
            "is_mutation": self.is_mutation,
            "is_reversible": self.is_reversible,
            "is_destructive": self.is_destructive,
            "is_external": self.is_external,
            "is_sensitive": self.is_sensitive,
            "requires_spend": self.requires_spend,
            "changes_permissions": self.changes_permissions,
            "changes_policy": self.changes_policy,
            "policy_decision": self.policy_decision,
            "approval_present": self.approval_present,
            "validation_passed": self.validation_passed,
            "rollback_available": self.rollback_available,
            "created_at": self.created_at.isoformat(),
            "metadata": dict(self.metadata),
        }

    def to_dict(self) -> dict[str, Any]:
        return self.serialize()

    @classmethod
    def from_mapping(cls, mapping: Mapping[str, Any]) -> AutonomyEvaluationRequest:
        if not isinstance(mapping, Mapping):
            raise InvalidAutonomyContractError("mapping must be a Mapping")
        required = {
            "id",
            "agent_run_id",
            "autonomy_level",
            "capability",
        }
        missing = required - set(mapping.keys())
        if missing:
            raise InvalidAutonomyContractError(
                f"Missing required fields in mapping: {sorted(missing)}"
            )
        created_at_raw = mapping.get("created_at")
        created_at = (
            _parse_dt(created_at_raw, "created_at")
            if created_at_raw is not None
            else _now_utc()
        )
        return cls(
            id=str(mapping["id"]),
            agent_run_id=str(mapping["agent_run_id"]),
            autonomy_level=mapping["autonomy_level"],
            capability=mapping["capability"],
            operation_name=mapping.get("operation_name"),
            is_mutation=bool(mapping.get("is_mutation", False)),
            is_reversible=bool(mapping.get("is_reversible", True)),
            is_destructive=bool(mapping.get("is_destructive", False)),
            is_external=bool(mapping.get("is_external", False)),
            is_sensitive=bool(mapping.get("is_sensitive", False)),
            requires_spend=bool(mapping.get("requires_spend", False)),
            changes_permissions=bool(mapping.get("changes_permissions", False)),
            changes_policy=bool(mapping.get("changes_policy", False)),
            policy_decision=mapping.get("policy_decision"),
            approval_present=bool(mapping.get("approval_present", False)),
            validation_passed=bool(mapping.get("validation_passed", False)),
            rollback_available=bool(mapping.get("rollback_available", False)),
            created_at=created_at,
            metadata=_freeze_metadata(mapping.get("metadata") or {}),
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AutonomyEvaluationRequest:
        return cls.from_mapping(data)


# ── AutonomyEvaluationResult ────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class AutonomyEvaluationResult:
    """Outcome of an :class:`AutonomyEvaluationRequest`.

    Decisions follow these rules:

    * ``allowed`` is True **iff** the decision is ``ALLOW``.
    * ``requires_approval`` is True when an additional approval is needed.
    * ``requires_validation`` is True when validation is needed before
      execution.
    * ``requires_rollback`` is True when a rollback path is required.
    * ``denied`` is True when the operation cannot be authorized at the
      current level regardless of policy or approvals.
    * ``reason_codes`` carry machine-readable evidence; ``warnings`` carry
      non-fatal advisory notes.
    """

    id: str
    request_id: str
    level: AgentAutonomyLevel
    decision: AutonomyDecision
    allowed: bool
    requires_approval: bool
    requires_validation: bool
    requires_rollback: bool
    denied: bool
    reason_codes: tuple[str, ...]
    warnings: tuple[str, ...]
    evaluated_at: datetime
    metadata: MappingProxyType[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )

    def __post_init__(self) -> None:
        _validate_non_empty_str(self.id, "id")
        _validate_non_empty_str(self.request_id, "request_id")
        object.__setattr__(self, "level", coerce_autonomy_level(self.level))

        if not isinstance(self.decision, AutonomyDecision):
            try:
                object.__setattr__(self, "decision", AutonomyDecision(self.decision))
            except ValueError as exc:
                raise InvalidAutonomyContractError(
                    f"Invalid AutonomyDecision: {self.decision!r}"
                ) from exc

        for f_name in (
            "allowed",
            "requires_approval",
            "requires_validation",
            "requires_rollback",
            "denied",
        ):
            if not isinstance(getattr(self, f_name), bool):
                raise InvalidAutonomyContractError(f"{f_name} must be a boolean")

        if self.allowed and self.denied:
            raise InvalidAutonomyContractError(
                "AutonomyEvaluationResult cannot be both allowed and denied"
            )

        object.__setattr__(
            self, "reason_codes", _freeze_str_tuple(self.reason_codes, "reason_codes")
        )
        object.__setattr__(
            self, "warnings", _freeze_str_tuple(self.warnings, "warnings")
        )
        object.__setattr__(
            self, "evaluated_at", _ensure_aware_dt(self.evaluated_at, "evaluated_at")
        )
        object.__setattr__(self, "metadata", _freeze_metadata(self.metadata))

    @property
    def decision_value(self) -> str:
        """Return the string value of the underlying :class:`AutonomyDecision`."""
        return self.decision.value

    def serialize(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "request_id": self.request_id,
            "level": int(self.level),
            "decision": self.decision.value,
            "allowed": self.allowed,
            "requires_approval": self.requires_approval,
            "requires_validation": self.requires_validation,
            "requires_rollback": self.requires_rollback,
            "denied": self.denied,
            "reason_codes": list(self.reason_codes),
            "warnings": list(self.warnings),
            "evaluated_at": self.evaluated_at.isoformat(),
            "metadata": dict(self.metadata),
        }

    def to_dict(self) -> dict[str, Any]:
        return self.serialize()

    @classmethod
    def from_mapping(cls, mapping: Mapping[str, Any]) -> AutonomyEvaluationResult:
        if not isinstance(mapping, Mapping):
            raise InvalidAutonomyContractError("mapping must be a Mapping")
        required = {
            "id",
            "request_id",
            "level",
            "decision",
            "allowed",
            "requires_approval",
            "requires_validation",
            "requires_rollback",
            "denied",
            "reason_codes",
        }
        missing = required - set(mapping.keys())
        if missing:
            raise InvalidAutonomyContractError(
                f"Missing required fields in mapping: {sorted(missing)}"
            )
        evaluated_at_raw = mapping.get("evaluated_at")
        evaluated_at = (
            _parse_dt(evaluated_at_raw, "evaluated_at")
            if evaluated_at_raw is not None
            else _now_utc()
        )
        return cls(
            id=str(mapping["id"]),
            request_id=str(mapping["request_id"]),
            level=mapping["level"],
            decision=mapping["decision"],
            allowed=bool(mapping["allowed"]),
            requires_approval=bool(mapping["requires_approval"]),
            requires_validation=bool(mapping["requires_validation"]),
            requires_rollback=bool(mapping["requires_rollback"]),
            denied=bool(mapping["denied"]),
            reason_codes=tuple(mapping.get("reason_codes", ())),
            warnings=tuple(mapping.get("warnings", ())),
            evaluated_at=evaluated_at,
            metadata=_freeze_metadata(mapping.get("metadata") or {}),
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AutonomyEvaluationResult:
        return cls.from_mapping(data)


# ── Autonomy Transition contracts ───────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class AutonomyTransitionRequest:
    """Request to change the autonomy level of an :class:`AgentRun`."""

    id: str
    agent_run_id: str
    current_level: AgentAutonomyLevel | int
    target_level: AgentAutonomyLevel | int
    agent_definition_max_level: AgentAutonomyLevel | int
    authorized: bool = False
    actor_id: str | None = None
    reason: AutonomyTransitionReason | str = AutonomyTransitionReason.MANUAL_REDUCTION
    message: str = ""
    created_at: datetime = field(default_factory=_now_utc)
    metadata: MappingProxyType[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )

    def __post_init__(self) -> None:
        _validate_non_empty_str(self.id, "id")
        _validate_non_empty_str(self.agent_run_id, "agent_run_id")
        object.__setattr__(
            self, "current_level", coerce_autonomy_level(self.current_level)
        )
        object.__setattr__(
            self, "target_level", coerce_autonomy_level(self.target_level)
        )
        object.__setattr__(
            self,
            "agent_definition_max_level",
            coerce_autonomy_level(self.agent_definition_max_level),
        )
        if not isinstance(self.authorized, bool):
            raise InvalidAutonomyContractError("authorized must be a boolean")
        if self.actor_id is not None:
            object.__setattr__(
                self, "actor_id", _validate_non_empty_str(self.actor_id, "actor_id")
            )
        if not isinstance(self.reason, AutonomyTransitionReason):
            try:
                object.__setattr__(
                    self, "reason", AutonomyTransitionReason(self.reason)
                )
            except ValueError as exc:
                raise InvalidAutonomyContractError(
                    f"Invalid AutonomyTransitionReason: {self.reason!r}"
                ) from exc
        object.__setattr__(self, "message", str(self.message or "").strip())
        object.__setattr__(
            self, "created_at", _ensure_aware_dt(self.created_at, "created_at")
        )
        object.__setattr__(self, "metadata", _freeze_metadata(self.metadata))

    @property
    def is_escalation(self) -> bool:
        """Return True if the transition is an escalation (target > current)."""
        return int(self.target_level) > int(self.current_level)

    @property
    def is_reduction(self) -> bool:
        """Return True if the transition is a reduction (target < current)."""
        return int(self.target_level) < int(self.current_level)

    @property
    def is_no_op(self) -> bool:
        """Return True if the transition keeps the level unchanged."""
        return int(self.target_level) == int(self.current_level)

    def serialize(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "agent_run_id": self.agent_run_id,
            "current_level": int(self.current_level),
            "target_level": int(self.target_level),
            "agent_definition_max_level": int(self.agent_definition_max_level),
            "authorized": self.authorized,
            "actor_id": self.actor_id,
            "reason": self.reason.value
            if isinstance(self.reason, AutonomyTransitionReason)
            else self.reason,
            "message": self.message,
            "created_at": self.created_at.isoformat(),
            "metadata": dict(self.metadata),
        }

    def to_dict(self) -> dict[str, Any]:
        return self.serialize()

    @classmethod
    def from_mapping(cls, mapping: Mapping[str, Any]) -> AutonomyTransitionRequest:
        if not isinstance(mapping, Mapping):
            raise InvalidAutonomyContractError("mapping must be a Mapping")
        required = {
            "id",
            "agent_run_id",
            "current_level",
            "target_level",
            "agent_definition_max_level",
        }
        missing = required - set(mapping.keys())
        if missing:
            raise InvalidAutonomyContractError(
                f"Missing required fields in mapping: {sorted(missing)}"
            )
        created_at_raw = mapping.get("created_at")
        created_at = (
            _parse_dt(created_at_raw, "created_at")
            if created_at_raw is not None
            else _now_utc()
        )
        return cls(
            id=str(mapping["id"]),
            agent_run_id=str(mapping["agent_run_id"]),
            current_level=mapping["current_level"],
            target_level=mapping["target_level"],
            agent_definition_max_level=mapping["agent_definition_max_level"],
            authorized=bool(mapping.get("authorized", False)),
            actor_id=mapping.get("actor_id"),
            reason=mapping.get(
                "reason", AutonomyTransitionReason.MANUAL_REDUCTION.value
            ),
            message=str(mapping.get("message", "")),
            created_at=created_at,
            metadata=_freeze_metadata(mapping.get("metadata") or {}),
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AutonomyTransitionRequest:
        return cls.from_mapping(data)


@dataclass(frozen=True, slots=True)
class AutonomyTransitionResult:
    """Outcome of an autonomy level transition request.

    Successful results carry the new level to apply to the run. Failed
    results carry a reason code and the level remains unchanged.
    """

    id: str
    request_id: str
    agent_run_id: str
    success: bool
    previous_level: AgentAutonomyLevel
    new_level: AgentAutonomyLevel
    authorized: bool
    reason_codes: tuple[str, ...]
    message: str
    decided_at: datetime
    metadata: MappingProxyType[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )

    def __post_init__(self) -> None:
        _validate_non_empty_str(self.id, "id")
        _validate_non_empty_str(self.request_id, "request_id")
        _validate_non_empty_str(self.agent_run_id, "agent_run_id")
        if not isinstance(self.success, bool):
            raise InvalidAutonomyContractError("success must be a boolean")
        if not isinstance(self.authorized, bool):
            raise InvalidAutonomyContractError("authorized must be a boolean")
        object.__setattr__(
            self, "previous_level", coerce_autonomy_level(self.previous_level)
        )
        object.__setattr__(self, "new_level", coerce_autonomy_level(self.new_level))
        object.__setattr__(
            self, "reason_codes", _freeze_str_tuple(self.reason_codes, "reason_codes")
        )
        object.__setattr__(self, "message", str(self.message or "").strip())
        object.__setattr__(
            self, "decided_at", _ensure_aware_dt(self.decided_at, "decided_at")
        )
        object.__setattr__(self, "metadata", _freeze_metadata(self.metadata))

    def serialize(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "request_id": self.request_id,
            "agent_run_id": self.agent_run_id,
            "success": self.success,
            "previous_level": int(self.previous_level),
            "new_level": int(self.new_level),
            "authorized": self.authorized,
            "reason_codes": list(self.reason_codes),
            "message": self.message,
            "decided_at": self.decided_at.isoformat(),
            "metadata": dict(self.metadata),
        }

    def to_dict(self) -> dict[str, Any]:
        return self.serialize()

    @classmethod
    def from_mapping(cls, mapping: Mapping[str, Any]) -> AutonomyTransitionResult:
        if not isinstance(mapping, Mapping):
            raise InvalidAutonomyContractError("mapping must be a Mapping")
        required = {
            "id",
            "request_id",
            "agent_run_id",
            "success",
            "previous_level",
            "new_level",
            "authorized",
        }
        missing = required - set(mapping.keys())
        if missing:
            raise InvalidAutonomyContractError(
                f"Missing required fields in mapping: {sorted(missing)}"
            )
        decided_at_raw = mapping.get("decided_at")
        decided_at = (
            _parse_dt(decided_at_raw, "decided_at")
            if decided_at_raw is not None
            else _now_utc()
        )
        return cls(
            id=str(mapping["id"]),
            request_id=str(mapping["request_id"]),
            agent_run_id=str(mapping["agent_run_id"]),
            success=bool(mapping["success"]),
            previous_level=mapping["previous_level"],
            new_level=mapping["new_level"],
            authorized=bool(mapping["authorized"]),
            reason_codes=tuple(mapping.get("reason_codes", ())),
            message=str(mapping.get("message", "")),
            decided_at=decided_at,
            metadata=_freeze_metadata(mapping.get("metadata") or {}),
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AutonomyTransitionResult:
        return cls.from_mapping(data)


@dataclass(frozen=True, slots=True)
class AutonomyTransitionRecord:
    """Immutable audit record of a transition applied to an ``AgentRun``.

    ``AutonomyManager`` produces one of these for every successful or
    rejected transition. Records are append-only and can be persisted
    alongside ``AgentResult`` for full traceability.
    """

    id: str
    agent_run_id: str
    previous_level: AgentAutonomyLevel
    new_level: AgentAutonomyLevel
    authorized: bool
    actor_id: str | None
    reason: AutonomyTransitionReason
    message: str
    occurred_at: datetime
    metadata: MappingProxyType[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )

    def __post_init__(self) -> None:
        _validate_non_empty_str(self.id, "id")
        _validate_non_empty_str(self.agent_run_id, "agent_run_id")
        if not isinstance(self.authorized, bool):
            raise InvalidAutonomyContractError("authorized must be a boolean")
        object.__setattr__(
            self, "previous_level", coerce_autonomy_level(self.previous_level)
        )
        object.__setattr__(self, "new_level", coerce_autonomy_level(self.new_level))
        if self.actor_id is not None:
            object.__setattr__(
                self, "actor_id", _validate_non_empty_str(self.actor_id, "actor_id")
            )
        if not isinstance(self.reason, AutonomyTransitionReason):
            try:
                object.__setattr__(
                    self, "reason", AutonomyTransitionReason(self.reason)
                )
            except ValueError as exc:
                raise InvalidAutonomyContractError(
                    f"Invalid AutonomyTransitionReason: {self.reason!r}"
                ) from exc
        object.__setattr__(self, "message", str(self.message or "").strip())
        object.__setattr__(
            self, "occurred_at", _ensure_aware_dt(self.occurred_at, "occurred_at")
        )
        object.__setattr__(self, "metadata", _freeze_metadata(self.metadata))

    @property
    def is_no_op(self) -> bool:
        """Return True when the record describes a level that did not change."""
        return int(self.previous_level) == int(self.new_level)

    def serialize(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "agent_run_id": self.agent_run_id,
            "previous_level": int(self.previous_level),
            "new_level": int(self.new_level),
            "authorized": self.authorized,
            "actor_id": self.actor_id,
            "reason": self.reason.value
            if isinstance(self.reason, AutonomyTransitionReason)
            else self.reason,
            "message": self.message,
            "occurred_at": self.occurred_at.isoformat(),
            "metadata": dict(self.metadata),
        }

    def to_dict(self) -> dict[str, Any]:
        return self.serialize()

    @classmethod
    def from_mapping(cls, mapping: Mapping[str, Any]) -> AutonomyTransitionRecord:
        if not isinstance(mapping, Mapping):
            raise InvalidAutonomyContractError("mapping must be a Mapping")
        required = {
            "id",
            "agent_run_id",
            "previous_level",
            "new_level",
            "authorized",
            "reason",
        }
        missing = required - set(mapping.keys())
        if missing:
            raise InvalidAutonomyContractError(
                f"Missing required fields in mapping: {sorted(missing)}"
            )
        occurred_at_raw = mapping.get("occurred_at")
        occurred_at = (
            _parse_dt(occurred_at_raw, "occurred_at")
            if occurred_at_raw is not None
            else _now_utc()
        )
        return cls(
            id=str(mapping["id"]),
            agent_run_id=str(mapping["agent_run_id"]),
            previous_level=mapping["previous_level"],
            new_level=mapping["new_level"],
            authorized=bool(mapping["authorized"]),
            actor_id=mapping.get("actor_id"),
            reason=mapping["reason"],
            message=str(mapping.get("message", "")),
            occurred_at=occurred_at,
            metadata=_freeze_metadata(mapping.get("metadata") or {}),
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AutonomyTransitionRecord:
        return cls.from_mapping(data)


__all__ = [
    "AutonomyCapability",
    "AutonomyDecision",
    "AutonomyEvaluationRequest",
    "AutonomyEvaluationResult",
    "AutonomyProfile",
    "AutonomyTransitionReason",
    "AutonomyTransitionRecord",
    "AutonomyTransitionRequest",
    "AutonomyTransitionResult",
    "coerce_autonomy_level",
    "generate_autonomy_profile_id",
    "generate_autonomy_request_id",
    "generate_autonomy_result_id",
    "generate_autonomy_transition_id",
]
