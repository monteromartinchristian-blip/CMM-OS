"""Phase 10.8 – Domain Composition Contracts.

Immutable, JSON-serializable, type-safe contracts for the Domain Composition subsystem.
All dataclasses are ``frozen=True``, use ``slots=True``, and never expose mutable
internal state.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from types import MappingProxyType
from typing import Any

from cmm.domains.contracts import (
    _deep_freeze,
    _deep_unfreeze,
    _ensure_tz_aware,
    _normalize_empty_to_none,
    _reject_unknown_fields,
    _validate_non_empty_str,
    _validate_strict_bool,
)
from cmm.domains.enums import DomainCompositionStatus, DomainConflictPolicy
from cmm.domains.errors import (
    DomainCompositionContractError,
    DomainCompositionSerializationError,
)
from cmm.domains.identifiers import DomainId

# ── Helpers ────────────────────────────────────────────────────────────────────


def _validate_positive_int(val: Any, field_name: str) -> int:
    """Validate a positive integer, rejecting bool."""
    if isinstance(val, bool):
        raise DomainCompositionContractError(
            f"{field_name} must be an integer, not a boolean", field=field_name
        )
    if not isinstance(val, int):
        raise DomainCompositionContractError(
            f"{field_name} must be an integer, got {type(val).__name__}: {val!r}",
            field=field_name,
        )
    return val


def _validate_finite_float(val: Any, field_name: str) -> float:
    """Validate a finite float, rejecting bool, NaN, Inf."""
    if isinstance(val, bool):
        raise DomainCompositionContractError(
            f"{field_name} must be a number, not a boolean", field=field_name
        )
    if isinstance(val, int):
        val = float(val)
    elif isinstance(val, float):
        pass
    else:
        raise DomainCompositionContractError(
            f"{field_name} must be an int or float, got {type(val).__name__}: {val!r}",
            field=field_name,
        )
    if not math.isfinite(val):
        raise DomainCompositionContractError(
            f"{field_name} must be a finite number, got {val!r}", field=field_name
        )
    return val


def _validate_confidence_opt(val: Any, field_name: str) -> float | None:
    """Validate optional confidence: None or finite float in [0, 1]."""
    if val is None:
        return None
    f = _validate_finite_float(val, field_name)
    if not (0.0 <= f <= 1.0):
        raise DomainCompositionContractError(
            f"{field_name} must be between 0.0 and 1.0, got {f!r}", field=field_name
        )
    return f


def _validate_positive_int_opt(val: Any, field_name: str) -> int | None:
    """Validate optional positive integer."""
    if val is None:
        return None
    return _validate_positive_int(val, field_name)


def _coerce_domain_id(val: Any, field_name: str) -> DomainId:
    """Coerce a string or DomainId to a DomainId."""
    if isinstance(val, DomainId):
        return val
    if isinstance(val, str):
        try:
            return DomainId.from_str(val)
        except (ValueError, TypeError) as exc:
            raise DomainCompositionContractError(
                f"Invalid DomainId in {field_name}: {exc}",
                field=field_name,
            ) from exc
    raise DomainCompositionContractError(
        f"{field_name} must be a DomainId or canonical string, got {type(val).__name__}",
        field=field_name,
    )


def _freeze_domain_ids(
    seq: Any, field_name: str, *, require_unique: bool = True
) -> tuple[DomainId, ...]:
    """Validate and convert sequence to tuple of unique DomainId."""
    if seq is None:
        return ()
    if isinstance(seq, (str, bytes)):
        raise DomainCompositionContractError(
            f"{field_name} must be a sequence of DomainId, not a string",
            field=field_name,
        )
    if not isinstance(seq, (tuple, list, set, frozenset)):
        raise DomainCompositionContractError(
            f"{field_name} must be a tuple, list, or sequence",
            field=field_name,
        )
    result: list[DomainId] = []
    seen: set[str] = set()
    for i, item in enumerate(seq):
        domain_id = _coerce_domain_id(item, f"{field_name}[{i}]")
        slug = domain_id.slug
        if require_unique and slug in seen:
            raise DomainCompositionContractError(
                f"Duplicate domain in {field_name}: {slug}",
                field=field_name,
                details={"duplicate": slug, "index": i},
            )
        if require_unique:
            seen.add(slug)
        result.append(domain_id)
    return tuple(result)


def _freeze_str_tuple(
    seq: Any,
    field_name: str,
    *,
    allow_empty: bool = True,
    require_unique: bool = False,
) -> tuple[str, ...]:
    """Validate and convert sequence to tuple of clean non-empty strings."""
    if seq is None:
        if allow_empty:
            return ()
        raise DomainCompositionContractError(
            f"{field_name} cannot be None", field=field_name
        )
    if isinstance(seq, (str, bytes)):
        raise DomainCompositionContractError(
            f"{field_name} must be a sequence of strings, not a string",
            field=field_name,
        )
    if not isinstance(seq, (tuple, list, set, frozenset)):
        raise DomainCompositionContractError(
            f"{field_name} must be a tuple, list, or sequence of strings",
            field=field_name,
        )
    result = []
    for i, item in enumerate(seq):
        if not isinstance(item, str) or not item.strip():
            raise DomainCompositionContractError(
                f"All items in {field_name} must be non-empty strings",
                field=field_name,
                details={"index": i, "value": item},
            )
        result.append(item.strip())
    if require_unique and len(set(result)) != len(result):
        raise DomainCompositionContractError(
            f"Duplicate items in {field_name}", field=field_name
        )
    return tuple(result)


# ═══════════════════════════════════════════════════════════════════════════════
# DomainCompositionPolicy
# ═══════════════════════════════════════════════════════════════════════════════

_POLICY_KNOWN = frozenset(
    {
        "conflict_policy",
        "blocking_severities",
        "partial_severities",
        "denied_permission_prefixes",
        "required_permission_prefixes",
        "granted_permission_prefixes",
        "metadata",
    }
)


@dataclass(frozen=True, slots=True)
class DomainCompositionPolicy:
    """Immutable configuration for domain composition.

    All prefix tuples must be disjoint and contain unique, non-empty strings.
    """

    conflict_policy: DomainConflictPolicy = DomainConflictPolicy.MOST_RESTRICTIVE
    blocking_severities: tuple[str, ...] = ("critical", "high", "blocking")
    partial_severities: tuple[str, ...] = ("medium", "warning")
    denied_permission_prefixes: tuple[str, ...] = ("deny:", "prohibit:")
    required_permission_prefixes: tuple[str, ...] = ("require:",)
    granted_permission_prefixes: tuple[str, ...] = ("allow:", "grant:")
    metadata: MappingProxyType[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )

    def __post_init__(self) -> None:
        # Conflict policy
        if isinstance(self.conflict_policy, str):
            try:
                object.__setattr__(
                    self,
                    "conflict_policy",
                    DomainConflictPolicy(self.conflict_policy),
                )
            except ValueError as exc:
                raise DomainCompositionContractError(
                    f"Invalid DomainConflictPolicy: {self.conflict_policy!r}",
                    field="conflict_policy",
                ) from exc
        elif not isinstance(self.conflict_policy, DomainConflictPolicy):
            raise DomainCompositionContractError(
                "conflict_policy must be a DomainConflictPolicy",
                field="conflict_policy",
            )

        # Freeze severity and prefix tuples
        object.__setattr__(
            self,
            "blocking_severities",
            _freeze_str_tuple(
                self.blocking_severities,
                "blocking_severities",
                require_unique=True,
            ),
        )
        object.__setattr__(
            self,
            "partial_severities",
            _freeze_str_tuple(
                self.partial_severities,
                "partial_severities",
                require_unique=True,
            ),
        )

        # Severities must be disjoint
        blocking_set = set(self.blocking_severities)
        partial_set = set(self.partial_severities)
        overlap = blocking_set & partial_set
        if overlap:
            raise DomainCompositionContractError(
                f"Severities must be disjoint between blocking and partial: {sorted(overlap)}",
                field="blocking_severities",
            )

        # Permission prefix groups
        prefix_groups: list[tuple[str, tuple[str, ...]]] = [
            ("denied_permission_prefixes", self.denied_permission_prefixes),
            ("required_permission_prefixes", self.required_permission_prefixes),
            ("granted_permission_prefixes", self.granted_permission_prefixes),
        ]
        all_prefixes: set[str] = set()
        for gname, gval in prefix_groups:
            frozen = _freeze_str_tuple(
                gval, gname, require_unique=True, allow_empty=False
            )
            object.__setattr__(self, gname, frozen)
            gset = set(frozen)
            overlap_with = all_prefixes & gset
            if overlap_with:
                raise DomainCompositionContractError(
                    f"Permission prefixes must be disjoint across groups: {sorted(overlap_with)}",
                    field=gname,
                )
            all_prefixes |= gset

        # Metadata
        object.__setattr__(self, "metadata", _deep_freeze(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "conflict_policy": self.conflict_policy.value,
            "blocking_severities": list(self.blocking_severities),
            "partial_severities": list(self.partial_severities),
            "denied_permission_prefixes": list(self.denied_permission_prefixes),
            "required_permission_prefixes": list(self.required_permission_prefixes),
            "granted_permission_prefixes": list(self.granted_permission_prefixes),
            "metadata": _deep_unfreeze(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DomainCompositionPolicy:
        """Deserialize from dictionary."""
        if not isinstance(data, Mapping):
            raise DomainCompositionSerializationError(
                "DomainCompositionPolicy.from_dict requires a mapping", field="data"
            )
        _reject_unknown_fields(data, _POLICY_KNOWN, "DomainCompositionPolicy")
        try:
            return cls(
                conflict_policy=DomainConflictPolicy(
                    data.get("conflict_policy", "most_restrictive")
                ),
                blocking_severities=tuple(data.get("blocking_severities", ())),
                partial_severities=tuple(data.get("partial_severities", ())),
                denied_permission_prefixes=tuple(
                    data.get("denied_permission_prefixes", ())
                ),
                required_permission_prefixes=tuple(
                    data.get("required_permission_prefixes", ())
                ),
                granted_permission_prefixes=tuple(
                    data.get("granted_permission_prefixes", ())
                ),
                metadata=_deep_freeze(data.get("metadata")),
            )
        except DomainCompositionContractError as exc:
            raise DomainCompositionSerializationError(
                str(exc), field=exc.field
            ) from exc


# ═══════════════════════════════════════════════════════════════════════════════
# DomainCompositionItem
# ═══════════════════════════════════════════════════════════════════════════════

_ITEM_KNOWN = frozenset(
    {
        "category",
        "identifier",
        "contributing_domains",
        "primary_contributor",
        "precedence",
        "metadata",
    }
)


@dataclass(frozen=True, slots=True)
class DomainCompositionItem:
    """A single composed item with full provenance."""

    category: str
    identifier: str
    contributing_domains: tuple[DomainId, ...]
    primary_contributor: DomainId
    precedence: int
    metadata: MappingProxyType[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "category", _validate_non_empty_str(self.category, "category")
        )
        object.__setattr__(
            self, "identifier", _validate_non_empty_str(self.identifier, "identifier")
        )
        object.__setattr__(
            self,
            "contributing_domains",
            _freeze_domain_ids(
                self.contributing_domains,
                "contributing_domains",
                require_unique=True,
            ),
        )
        if len(self.contributing_domains) == 0:
            raise DomainCompositionContractError(
                "contributing_domains must not be empty",
                field="contributing_domains",
            )
        object.__setattr__(
            self,
            "primary_contributor",
            _coerce_domain_id(self.primary_contributor, "primary_contributor"),
        )
        if self.primary_contributor.slug not in {
            d.slug for d in self.contributing_domains
        }:
            raise DomainCompositionContractError(
                f"primary_contributor {self.primary_contributor.slug} must be in contributing_domains",
                field="primary_contributor",
            )
        object.__setattr__(
            self,
            "precedence",
            _validate_positive_int(self.precedence, "precedence"),
        )
        object.__setattr__(self, "metadata", _deep_freeze(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "category": self.category,
            "identifier": self.identifier,
            "contributing_domains": [str(d) for d in self.contributing_domains],
            "primary_contributor": str(self.primary_contributor),
            "precedence": self.precedence,
            "metadata": _deep_unfreeze(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DomainCompositionItem:
        """Deserialize from dictionary."""
        if not isinstance(data, Mapping):
            raise DomainCompositionSerializationError(
                "DomainCompositionItem.from_dict requires a mapping", field="data"
            )
        _reject_unknown_fields(data, _ITEM_KNOWN, "DomainCompositionItem")
        required = {
            "category",
            "identifier",
            "contributing_domains",
            "primary_contributor",
            "precedence",
        }
        missing = required - set(data.keys())
        if missing:
            raise DomainCompositionSerializationError(
                f"DomainCompositionItem.from_dict missing required fields: {sorted(missing)}",
                field="data",
            )
        try:
            return cls(
                category=str(data["category"]),
                identifier=str(data["identifier"]),
                contributing_domains=tuple(data["contributing_domains"]),
                primary_contributor=str(data["primary_contributor"]),
                precedence=data["precedence"],
                metadata=_deep_freeze(data.get("metadata")),
            )
        except DomainCompositionContractError as exc:
            raise DomainCompositionSerializationError(
                str(exc), field=exc.field
            ) from exc


# ═══════════════════════════════════════════════════════════════════════════════
# DomainCompositionDecision
# ═══════════════════════════════════════════════════════════════════════════════

_DECISION_KNOWN = frozenset(
    {
        "code",
        "category",
        "identifier",
        "action",
        "domains",
        "reason",
        "blocking",
        "metadata",
    }
)


@dataclass(frozen=True, slots=True)
class DomainCompositionDecision:
    """A single decision made during domain composition."""

    code: str
    category: str
    identifier: str | None
    action: str
    domains: tuple[DomainId, ...] = ()
    reason: str | None = None
    blocking: bool = False
    metadata: MappingProxyType[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )

    def __post_init__(self) -> None:
        object.__setattr__(self, "code", _validate_non_empty_str(self.code, "code"))
        object.__setattr__(
            self, "category", _validate_non_empty_str(self.category, "category")
        )
        # identifier can be None or a non-empty string
        if self.identifier is not None and (
            not isinstance(self.identifier, str) or not self.identifier.strip()
        ):
            raise DomainCompositionContractError(
                "identifier must be a non-empty string or None",
                field="identifier",
            )
        object.__setattr__(
            self, "action", _validate_non_empty_str(self.action, "action")
        )
        object.__setattr__(
            self,
            "domains",
            _freeze_domain_ids(self.domains, "domains", require_unique=True),
        )
        object.__setattr__(self, "reason", _normalize_empty_to_none(self.reason))
        object.__setattr__(
            self, "blocking", _validate_strict_bool(self.blocking, "blocking")
        )
        object.__setattr__(self, "metadata", _deep_freeze(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "code": self.code,
            "category": self.category,
            "identifier": self.identifier,
            "action": self.action,
            "domains": [str(d) for d in self.domains],
            "reason": self.reason,
            "blocking": self.blocking,
            "metadata": _deep_unfreeze(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DomainCompositionDecision:
        """Deserialize from dictionary."""
        if not isinstance(data, Mapping):
            raise DomainCompositionSerializationError(
                "DomainCompositionDecision.from_dict requires a mapping", field="data"
            )
        _reject_unknown_fields(data, _DECISION_KNOWN, "DomainCompositionDecision")
        required = {"code", "category", "action"}
        missing = required - set(data.keys())
        if missing:
            raise DomainCompositionSerializationError(
                f"DomainCompositionDecision.from_dict missing required fields: {sorted(missing)}",
                field="data",
            )
        blocking_raw = data.get("blocking", False)
        try:
            blocking = _validate_strict_bool(blocking_raw, "blocking")
        except (TypeError, ValueError) as exc:
            raise DomainCompositionSerializationError(
                str(exc), field="blocking"
            ) from exc
        return cls(
            code=str(data["code"]),
            category=str(data["category"]),
            identifier=data.get("identifier"),
            action=str(data["action"]),
            domains=tuple(data.get("domains", ())),
            reason=data.get("reason"),
            blocking=blocking,
            metadata=_deep_freeze(data.get("metadata")),
        )


# ═══════════════════════════════════════════════════════════════════════════════
# DomainCompositionConflict
# ═══════════════════════════════════════════════════════════════════════════════

_CONFLICT_KNOWN = frozenset(
    {
        "code",
        "category",
        "domains",
        "severity",
        "message",
        "blocking",
        "resolved",
        "resolution",
        "metadata",
    }
)


@dataclass(frozen=True, slots=True)
class DomainCompositionConflict:
    """A conflict detected during domain composition."""

    code: str
    category: str
    domains: tuple[DomainId, ...]
    severity: str
    message: str
    blocking: bool
    resolved: bool = False
    resolution: str | None = None
    metadata: MappingProxyType[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )

    def __post_init__(self) -> None:
        object.__setattr__(self, "code", _validate_non_empty_str(self.code, "code"))
        object.__setattr__(
            self, "category", _validate_non_empty_str(self.category, "category")
        )
        object.__setattr__(
            self,
            "domains",
            _freeze_domain_ids(self.domains, "domains", require_unique=True),
        )
        if len(self.domains) == 0:
            raise DomainCompositionContractError(
                "domains must not be empty", field="domains"
            )
        object.__setattr__(
            self, "severity", _validate_non_empty_str(self.severity, "severity")
        )
        object.__setattr__(
            self, "message", _validate_non_empty_str(self.message, "message")
        )
        object.__setattr__(
            self, "blocking", _validate_strict_bool(self.blocking, "blocking")
        )
        object.__setattr__(
            self, "resolved", _validate_strict_bool(self.resolved, "resolved")
        )
        object.__setattr__(
            self, "resolution", _normalize_empty_to_none(self.resolution)
        )
        # If not resolved, resolution must be None
        if not self.resolved and self.resolution is not None:
            raise DomainCompositionContractError(
                "Unresolved conflict must not have a resolution",
                field="resolution",
            )
        object.__setattr__(self, "metadata", _deep_freeze(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "code": self.code,
            "category": self.category,
            "domains": [str(d) for d in self.domains],
            "severity": self.severity,
            "message": self.message,
            "blocking": self.blocking,
            "resolved": self.resolved,
            "resolution": self.resolution,
            "metadata": _deep_unfreeze(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DomainCompositionConflict:
        """Deserialize from dictionary."""
        if not isinstance(data, Mapping):
            raise DomainCompositionSerializationError(
                "DomainCompositionConflict.from_dict requires a mapping", field="data"
            )
        _reject_unknown_fields(data, _CONFLICT_KNOWN, "DomainCompositionConflict")
        required = {"code", "category", "domains", "severity", "message", "blocking"}
        missing = required - set(data.keys())
        if missing:
            raise DomainCompositionSerializationError(
                f"DomainCompositionConflict.from_dict missing required fields: {sorted(missing)}",
                field="data",
            )
        blocking_raw = data["blocking"]
        try:
            blocking = _validate_strict_bool(blocking_raw, "blocking")
        except (TypeError, ValueError) as exc:
            raise DomainCompositionSerializationError(
                str(exc), field="blocking"
            ) from exc
        resolved_raw = data.get("resolved", False)
        try:
            resolved = _validate_strict_bool(resolved_raw, "resolved")
        except (TypeError, ValueError) as exc:
            raise DomainCompositionSerializationError(
                str(exc), field="resolved"
            ) from exc
        return cls(
            code=str(data["code"]),
            category=str(data["category"]),
            domains=tuple(data["domains"]),
            severity=str(data["severity"]),
            message=str(data["message"]),
            blocking=blocking,
            resolved=resolved,
            resolution=data.get("resolution"),
            metadata=_deep_freeze(data.get("metadata")),
        )


# ═══════════════════════════════════════════════════════════════════════════════
# EffectiveReasoningProfile
# ═══════════════════════════════════════════════════════════════════════════════

_PROFILE_KNOWN = frozenset(
    {
        "base_profile",
        "contributing_profiles",
        "contributing_domains",
        "added_rules",
        "required_rules",
        "prohibited_actions",
        "minimum_confidence",
        "maximum_inference_depth",
        "maximum_questions_per_turn",
        "metadata",
    }
)


@dataclass(frozen=True, slots=True)
class EffectiveReasoningProfile:
    """The effective reasoning profile composed from primary and supporting domains."""

    base_profile: str | None
    contributing_profiles: tuple[str, ...] = ()
    contributing_domains: tuple[DomainId, ...] = ()
    added_rules: tuple[str, ...] = ()
    required_rules: tuple[str, ...] = ()
    prohibited_actions: tuple[str, ...] = ()
    minimum_confidence: float | None = None
    maximum_inference_depth: int | None = None
    maximum_questions_per_turn: int | None = None
    metadata: MappingProxyType[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "base_profile", _normalize_empty_to_none(self.base_profile)
        )
        object.__setattr__(
            self,
            "contributing_profiles",
            _freeze_str_tuple(
                self.contributing_profiles, "contributing_profiles", require_unique=True
            ),
        )
        object.__setattr__(
            self,
            "contributing_domains",
            _freeze_domain_ids(
                self.contributing_domains, "contributing_domains", require_unique=True
            ),
        )
        object.__setattr__(
            self,
            "added_rules",
            _freeze_str_tuple(self.added_rules, "added_rules", require_unique=True),
        )
        object.__setattr__(
            self,
            "required_rules",
            _freeze_str_tuple(
                self.required_rules, "required_rules", require_unique=True
            ),
        )
        object.__setattr__(
            self,
            "prohibited_actions",
            _freeze_str_tuple(
                self.prohibited_actions, "prohibited_actions", require_unique=True
            ),
        )
        object.__setattr__(
            self,
            "minimum_confidence",
            _validate_confidence_opt(self.minimum_confidence, "minimum_confidence"),
        )
        object.__setattr__(
            self,
            "maximum_inference_depth",
            _validate_positive_int_opt(
                self.maximum_inference_depth, "maximum_inference_depth"
            ),
        )
        object.__setattr__(
            self,
            "maximum_questions_per_turn",
            _validate_positive_int_opt(
                self.maximum_questions_per_turn, "maximum_questions_per_turn"
            ),
        )
        object.__setattr__(self, "metadata", _deep_freeze(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "base_profile": self.base_profile,
            "contributing_profiles": list(self.contributing_profiles),
            "contributing_domains": [str(d) for d in self.contributing_domains],
            "added_rules": list(self.added_rules),
            "required_rules": list(self.required_rules),
            "prohibited_actions": list(self.prohibited_actions),
            "minimum_confidence": self.minimum_confidence,
            "maximum_inference_depth": self.maximum_inference_depth,
            "maximum_questions_per_turn": self.maximum_questions_per_turn,
            "metadata": _deep_unfreeze(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EffectiveReasoningProfile:
        """Deserialize from dictionary."""
        if not isinstance(data, Mapping):
            raise DomainCompositionSerializationError(
                "EffectiveReasoningProfile.from_dict requires a mapping", field="data"
            )
        _reject_unknown_fields(data, _PROFILE_KNOWN, "EffectiveReasoningProfile")
        if "base_profile" not in data:
            raise DomainCompositionSerializationError(
                "EffectiveReasoningProfile.from_dict missing required field 'base_profile'",
                field="base_profile",
            )
        try:
            return cls(
                base_profile=data.get("base_profile"),
                contributing_profiles=tuple(data.get("contributing_profiles", ())),
                contributing_domains=tuple(data.get("contributing_domains", ())),
                added_rules=tuple(data.get("added_rules", ())),
                required_rules=tuple(data.get("required_rules", ())),
                prohibited_actions=tuple(data.get("prohibited_actions", ())),
                minimum_confidence=data.get("minimum_confidence"),
                maximum_inference_depth=data.get("maximum_inference_depth"),
                maximum_questions_per_turn=data.get("maximum_questions_per_turn"),
                metadata=_deep_freeze(data.get("metadata")),
            )
        except DomainCompositionContractError as exc:
            raise DomainCompositionSerializationError(
                str(exc), field=exc.field
            ) from exc


# ═══════════════════════════════════════════════════════════════════════════════
# PermissionComposition
# ═══════════════════════════════════════════════════════════════════════════════

_PERM_KNOWN = frozenset(
    {
        "required_permissions",
        "granted_permissions",
        "denied_permissions",
        "unresolved_permissions",
        "provenance",
        "metadata",
    }
)


@dataclass(frozen=True, slots=True)
class PermissionComposition:
    """The effective permission set after composition."""

    required_permissions: tuple[str, ...] = ()
    granted_permissions: tuple[str, ...] = ()
    denied_permissions: tuple[str, ...] = ()
    unresolved_permissions: tuple[str, ...] = ()
    provenance: MappingProxyType[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )
    metadata: MappingProxyType[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "required_permissions",
            _freeze_str_tuple(
                self.required_permissions, "required_permissions", require_unique=True
            ),
        )
        object.__setattr__(
            self,
            "granted_permissions",
            _freeze_str_tuple(
                self.granted_permissions, "granted_permissions", require_unique=True
            ),
        )
        object.__setattr__(
            self,
            "denied_permissions",
            _freeze_str_tuple(
                self.denied_permissions, "denied_permissions", require_unique=True
            ),
        )
        object.__setattr__(
            self,
            "unresolved_permissions",
            _freeze_str_tuple(
                self.unresolved_permissions,
                "unresolved_permissions",
                require_unique=True,
            ),
        )
        object.__setattr__(self, "provenance", _deep_freeze(self.provenance))
        object.__setattr__(self, "metadata", _deep_freeze(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "required_permissions": list(self.required_permissions),
            "granted_permissions": list(self.granted_permissions),
            "denied_permissions": list(self.denied_permissions),
            "unresolved_permissions": list(self.unresolved_permissions),
            "provenance": _deep_unfreeze(self.provenance),
            "metadata": _deep_unfreeze(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PermissionComposition:
        """Deserialize from dictionary."""
        if not isinstance(data, Mapping):
            raise DomainCompositionSerializationError(
                "PermissionComposition.from_dict requires a mapping", field="data"
            )
        _reject_unknown_fields(data, _PERM_KNOWN, "PermissionComposition")
        return cls(
            required_permissions=tuple(data.get("required_permissions", ())),
            granted_permissions=tuple(data.get("granted_permissions", ())),
            denied_permissions=tuple(data.get("denied_permissions", ())),
            unresolved_permissions=tuple(data.get("unresolved_permissions", ())),
            provenance=_deep_freeze(data.get("provenance")),
            metadata=_deep_freeze(data.get("metadata")),
        )


# ═══════════════════════════════════════════════════════════════════════════════
# PresentationComposition
# ═══════════════════════════════════════════════════════════════════════════════

_PRES_KNOWN = frozenset(
    {
        "values",
        "provenance",
        "conflicts",
        "metadata",
    }
)


@dataclass(frozen=True, slots=True)
class PresentationComposition:
    """The effective presentation after composition."""

    values: MappingProxyType[str, Any]
    provenance: MappingProxyType[str, Any]
    conflicts: tuple[DomainCompositionConflict, ...] = ()
    metadata: MappingProxyType[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )

    def __post_init__(self) -> None:
        if not isinstance(self.values, Mapping):
            raise DomainCompositionContractError(
                "values must be a mapping", field="values"
            )
        object.__setattr__(self, "values", _deep_freeze(self.values))
        if not isinstance(self.provenance, Mapping):
            raise DomainCompositionContractError(
                "provenance must be a mapping", field="provenance"
            )
        object.__setattr__(self, "provenance", _deep_freeze(self.provenance))
        if not isinstance(self.conflicts, tuple):
            raise DomainCompositionContractError(
                "conflicts must be a tuple", field="conflicts"
            )
        for i, c in enumerate(self.conflicts):
            if not isinstance(c, DomainCompositionConflict):
                raise DomainCompositionContractError(
                    f"conflicts[{i}] must be a DomainCompositionConflict, got {type(c).__name__}",
                    field=f"conflicts[{i}]",
                )
        object.__setattr__(self, "metadata", _deep_freeze(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "values": _deep_unfreeze(self.values),
            "provenance": _deep_unfreeze(self.provenance),
            "conflicts": [c.to_dict() for c in self.conflicts],
            "metadata": _deep_unfreeze(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PresentationComposition:
        """Deserialize from dictionary."""
        if not isinstance(data, Mapping):
            raise DomainCompositionSerializationError(
                "PresentationComposition.from_dict requires a mapping", field="data"
            )
        _reject_unknown_fields(data, _PRES_KNOWN, "PresentationComposition")
        required = {"values", "provenance"}
        missing = required - set(data.keys())
        if missing:
            raise DomainCompositionSerializationError(
                f"PresentationComposition.from_dict missing required fields: {sorted(missing)}",
                field="data",
            )

        conflicts_raw = data.get("conflicts", ())
        if not isinstance(conflicts_raw, (list, tuple)):
            raise DomainCompositionSerializationError(
                "conflicts must be a list", field="conflicts"
            )
        conflicts_list = []
        for i, c in enumerate(conflicts_raw):
            if isinstance(c, DomainCompositionConflict):
                conflicts_list.append(c)
            elif isinstance(c, Mapping):
                conflicts_list.append(DomainCompositionConflict.from_dict(dict(c)))
            else:
                raise DomainCompositionSerializationError(
                    f"conflicts[{i}] must be a mapping, got {type(c).__name__}",
                    field=f"conflicts[{i}]",
                )

        return cls(
            values=_deep_freeze(data.get("values")),
            provenance=_deep_freeze(data.get("provenance")),
            conflicts=tuple(conflicts_list),
            metadata=_deep_freeze(data.get("metadata")),
        )


# ═══════════════════════════════════════════════════════════════════════════════
# DomainComposition
# ═══════════════════════════════════════════════════════════════════════════════

_COMPOSITION_KNOWN = frozenset(
    {
        "id",
        "resolution_id",
        "status",
        "primary_domain",
        "supporting_domains",
        "effective_profile",
        "rules",
        "resources",
        "operations",
        "workflows",
        "validators",
        "capabilities",
        "permissions",
        "presentation",
        "decisions",
        "conflicts",
        "policy",
        "composed_at",
        "metadata",
    }
)


@dataclass(frozen=True, slots=True)
class DomainComposition:
    """The complete result of domain composition."""

    id: str
    resolution_id: str
    status: DomainCompositionStatus
    primary_domain: DomainId
    supporting_domains: tuple[DomainId, ...] = ()

    effective_profile: EffectiveReasoningProfile | None = None

    rules: tuple[DomainCompositionItem, ...] = ()
    resources: tuple[DomainCompositionItem, ...] = ()
    operations: tuple[DomainCompositionItem, ...] = ()
    workflows: tuple[DomainCompositionItem, ...] = ()
    validators: tuple[DomainCompositionItem, ...] = ()
    capabilities: tuple[DomainCompositionItem, ...] = ()

    permissions: PermissionComposition | None = None
    presentation: PresentationComposition | None = None

    decisions: tuple[DomainCompositionDecision, ...] = ()
    conflicts: tuple[DomainCompositionConflict, ...] = ()

    policy: DomainCompositionPolicy = field(default_factory=DomainCompositionPolicy)
    composed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: MappingProxyType[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", _validate_non_empty_str(self.id, "id"))
        object.__setattr__(
            self,
            "resolution_id",
            _validate_non_empty_str(self.resolution_id, "resolution_id"),
        )

        if isinstance(self.status, str):
            try:
                object.__setattr__(self, "status", DomainCompositionStatus(self.status))
            except ValueError as exc:
                raise DomainCompositionContractError(
                    f"Invalid DomainCompositionStatus: {self.status!r}",
                    field="status",
                ) from exc
        elif not isinstance(self.status, DomainCompositionStatus):
            raise DomainCompositionContractError(
                "status must be a DomainCompositionStatus",
                field="status",
            )

        object.__setattr__(
            self,
            "primary_domain",
            _coerce_domain_id(self.primary_domain, "primary_domain"),
        )

        object.__setattr__(
            self,
            "supporting_domains",
            _freeze_domain_ids(
                self.supporting_domains, "supporting_domains", require_unique=True
            ),
        )

        # Primary must not be in supporting
        primary_slug = self.primary_domain.slug
        for sd in self.supporting_domains:
            if sd.slug == primary_slug:
                raise DomainCompositionContractError(
                    f"Primary domain {primary_slug} must not appear in supporting_domains",
                    field="supporting_domains",
                )

        # Validate effective_profile
        if self.effective_profile is not None and not isinstance(
            self.effective_profile, EffectiveReasoningProfile
        ):
            raise DomainCompositionContractError(
                "effective_profile must be an EffectiveReasoningProfile",
                field="effective_profile",
            )

        # Validate item tuples
        for attr_name in (
            "rules",
            "resources",
            "operations",
            "workflows",
            "validators",
            "capabilities",
        ):
            seq = getattr(self, attr_name)
            if not isinstance(seq, tuple):
                raise DomainCompositionContractError(
                    f"{attr_name} must be a tuple", field=attr_name
                )
            for i, item in enumerate(seq):
                if not isinstance(item, DomainCompositionItem):
                    raise DomainCompositionContractError(
                        f"{attr_name}[{i}] must be a DomainCompositionItem, got {type(item).__name__}",
                        field=f"{attr_name}[{i}]",
                    )

        # Validate permissions
        if self.permissions is not None and not isinstance(
            self.permissions, PermissionComposition
        ):
            raise DomainCompositionContractError(
                "permissions must be a PermissionComposition",
                field="permissions",
            )

        # Validate presentation
        if self.presentation is not None and not isinstance(
            self.presentation, PresentationComposition
        ):
            raise DomainCompositionContractError(
                "presentation must be a PresentationComposition",
                field="presentation",
            )

        # Validate decisions
        if not isinstance(self.decisions, tuple):
            raise DomainCompositionContractError(
                "decisions must be a tuple", field="decisions"
            )
        for i, d in enumerate(self.decisions):
            if not isinstance(d, DomainCompositionDecision):
                raise DomainCompositionContractError(
                    f"decisions[{i}] must be a DomainCompositionDecision, got {type(d).__name__}",
                    field=f"decisions[{i}]",
                )

        # Validate conflicts
        if not isinstance(self.conflicts, tuple):
            raise DomainCompositionContractError(
                "conflicts must be a tuple", field="conflicts"
            )
        for i, c in enumerate(self.conflicts):
            if not isinstance(c, DomainCompositionConflict):
                raise DomainCompositionContractError(
                    f"conflicts[{i}] must be a DomainCompositionConflict, got {type(c).__name__}",
                    field=f"conflicts[{i}]",
                )

        # Validate policy
        if not isinstance(self.policy, DomainCompositionPolicy):
            if isinstance(self.policy, Mapping):
                try:
                    object.__setattr__(
                        self,
                        "policy",
                        DomainCompositionPolicy.from_dict(dict(self.policy)),
                    )
                except (
                    DomainCompositionContractError,
                    DomainCompositionSerializationError,
                ) as exc:
                    raise DomainCompositionContractError(
                        f"Invalid policy: {exc}",
                        field="policy",
                    ) from exc
            else:
                raise DomainCompositionContractError(
                    "policy must be a DomainCompositionPolicy",
                    field="policy",
                )

        # Validate composed_at
        object.__setattr__(
            self,
            "composed_at",
            _ensure_tz_aware(self.composed_at, "composed_at"),
        )

        # Validate status invariants
        unresolved_blocking = any(c.blocking and not c.resolved for c in self.conflicts)
        if unresolved_blocking and self.status == DomainCompositionStatus.COMPOSED:
            raise DomainCompositionContractError(
                "COMPOSED status requires no unresolved blocking conflicts",
                field="status",
            )
        if not unresolved_blocking and self.status == DomainCompositionStatus.BLOCKED:
            raise DomainCompositionContractError(
                "BLOCKED status requires at least one unresolved blocking conflict",
                field="status",
            )

        object.__setattr__(self, "metadata", _deep_freeze(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "id": self.id,
            "resolution_id": self.resolution_id,
            "status": self.status.value,
            "primary_domain": str(self.primary_domain),
            "supporting_domains": [str(d) for d in self.supporting_domains],
            "effective_profile": self.effective_profile.to_dict()
            if self.effective_profile
            else None,
            "rules": [r.to_dict() for r in self.rules],
            "resources": [r.to_dict() for r in self.resources],
            "operations": [o.to_dict() for o in self.operations],
            "workflows": [w.to_dict() for w in self.workflows],
            "validators": [v.to_dict() for v in self.validators],
            "capabilities": [c.to_dict() for c in self.capabilities],
            "permissions": self.permissions.to_dict() if self.permissions else None,
            "presentation": self.presentation.to_dict() if self.presentation else None,
            "decisions": [d.to_dict() for d in self.decisions],
            "conflicts": [c.to_dict() for c in self.conflicts],
            "policy": self.policy.to_dict(),
            "composed_at": self.composed_at.isoformat(),
            "metadata": _deep_unfreeze(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DomainComposition:
        """Deserialize from dictionary."""
        if not isinstance(data, Mapping):
            raise DomainCompositionSerializationError(
                "DomainComposition.from_dict requires a mapping", field="data"
            )
        _reject_unknown_fields(data, _COMPOSITION_KNOWN, "DomainComposition")
        required = {
            "id",
            "resolution_id",
            "status",
            "primary_domain",
            "composed_at",
        }
        missing = required - set(data.keys())
        if missing:
            raise DomainCompositionSerializationError(
                f"DomainComposition.from_dict missing required fields: {sorted(missing)}",
                field="data",
            )

        def _parse_items(
            raw: Any, field_label: str
        ) -> tuple[DomainCompositionItem, ...]:
            if raw is None:
                return ()
            if not isinstance(raw, (list, tuple)):
                raise DomainCompositionSerializationError(
                    f"{field_label} must be a list", field=field_label
                )
            result = []
            for i, item in enumerate(raw):
                if isinstance(item, DomainCompositionItem):
                    result.append(item)
                elif isinstance(item, Mapping):
                    result.append(DomainCompositionItem.from_dict(dict(item)))
                else:
                    raise DomainCompositionSerializationError(
                        f"{field_label}[{i}] must be a mapping, got {type(item).__name__}",
                        field=f"{field_label}[{i}]",
                    )
            return tuple(result)

        def _parse_conflicts(raw: Any) -> tuple[DomainCompositionConflict, ...]:
            if raw is None:
                return ()
            if not isinstance(raw, (list, tuple)):
                raise DomainCompositionSerializationError(
                    "conflicts must be a list", field="conflicts"
                )
            result = []
            for i, c in enumerate(raw):
                if isinstance(c, DomainCompositionConflict):
                    result.append(c)
                elif isinstance(c, Mapping):
                    result.append(DomainCompositionConflict.from_dict(dict(c)))
                else:
                    raise DomainCompositionSerializationError(
                        f"conflicts[{i}] must be a mapping, got {type(c).__name__}",
                        field=f"conflicts[{i}]",
                    )
            return tuple(result)

        def _parse_decisions(raw: Any) -> tuple[DomainCompositionDecision, ...]:
            if raw is None:
                return ()
            if not isinstance(raw, (list, tuple)):
                raise DomainCompositionSerializationError(
                    "decisions must be a list", field="decisions"
                )
            result = []
            for i, d in enumerate(raw):
                if isinstance(d, DomainCompositionDecision):
                    result.append(d)
                elif isinstance(d, Mapping):
                    result.append(DomainCompositionDecision.from_dict(dict(d)))
                else:
                    raise DomainCompositionSerializationError(
                        f"decisions[{i}] must be a mapping, got {type(d).__name__}",
                        field=f"decisions[{i}]",
                    )
            return tuple(result)

        def _parse_policy(raw: Any) -> DomainCompositionPolicy:
            if isinstance(raw, DomainCompositionPolicy):
                return raw
            if isinstance(raw, Mapping):
                return DomainCompositionPolicy.from_dict(dict(raw))
            return DomainCompositionPolicy()

        def _parse_profile(raw: Any) -> EffectiveReasoningProfile | None:
            if raw is None:
                return None
            if isinstance(raw, EffectiveReasoningProfile):
                return raw
            if isinstance(raw, Mapping):
                return EffectiveReasoningProfile.from_dict(dict(raw))
            raise DomainCompositionSerializationError(
                f"effective_profile must be a mapping or None, got {type(raw).__name__}",
                field="effective_profile",
            )

        def _parse_permissions(raw: Any) -> PermissionComposition | None:
            if raw is None:
                return None
            if isinstance(raw, PermissionComposition):
                return raw
            if isinstance(raw, Mapping):
                return PermissionComposition.from_dict(dict(raw))
            raise DomainCompositionSerializationError(
                f"permissions must be a mapping or None, got {type(raw).__name__}",
                field="permissions",
            )

        def _parse_presentation(raw: Any) -> PresentationComposition | None:
            if raw is None:
                return None
            if isinstance(raw, PresentationComposition):
                return raw
            if isinstance(raw, Mapping):
                return PresentationComposition.from_dict(dict(raw))
            raise DomainCompositionSerializationError(
                f"presentation must be a mapping or None, got {type(raw).__name__}",
                field="presentation",
            )

        composed_at_raw = data.get("composed_at")
        if isinstance(composed_at_raw, datetime):
            composed_at = composed_at_raw
        elif isinstance(composed_at_raw, str):
            composed_at = datetime.fromisoformat(composed_at_raw)
            if composed_at.tzinfo is None:
                composed_at = composed_at.replace(tzinfo=timezone.utc)
        else:
            raise DomainCompositionSerializationError(
                "composed_at must be an ISO string or datetime",
                field="composed_at",
            )

        return cls(
            id=str(data["id"]),
            resolution_id=str(data["resolution_id"]),
            status=DomainCompositionStatus(data["status"]),
            primary_domain=str(data["primary_domain"]),
            supporting_domains=tuple(data.get("supporting_domains", ())),
            effective_profile=_parse_profile(data.get("effective_profile")),
            rules=_parse_items(data.get("rules"), "rules"),
            resources=_parse_items(data.get("resources"), "resources"),
            operations=_parse_items(data.get("operations"), "operations"),
            workflows=_parse_items(data.get("workflows"), "workflows"),
            validators=_parse_items(data.get("validators"), "validators"),
            capabilities=_parse_items(data.get("capabilities"), "capabilities"),
            permissions=_parse_permissions(data.get("permissions")),
            presentation=_parse_presentation(data.get("presentation")),
            decisions=_parse_decisions(data.get("decisions")),
            conflicts=_parse_conflicts(data.get("conflicts")),
            policy=_parse_policy(data.get("policy")),
            composed_at=composed_at,
            metadata=_deep_freeze(data.get("metadata")),
        )


__all__ = [
    "DomainComposition",
    "DomainCompositionConflict",
    "DomainCompositionDecision",
    "DomainCompositionItem",
    "DomainCompositionPolicy",
    "EffectiveReasoningProfile",
    "PermissionComposition",
    "PresentationComposition",
]
