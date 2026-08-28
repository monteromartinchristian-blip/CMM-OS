"""Phase 10.32 — Domain Conflict Resolution contracts.

Immutable, deterministic and JSON-serializable contracts used by the
Domain Conflict Resolution layer.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Any

from cmm.domains.contracts import _deep_freeze
from cmm.domains.errors import (
    DomainConflictResolutionContractError,
    DomainConflictResolutionSerializationError,
)
from cmm.domains.identifiers import DomainId

# ── Enums ─────────────────────────────────────────────────────────────────────


class DomainConflictSourceKind(str, Enum):
    DECLARED_DOMAIN_CONFLICT = "declared_domain_conflict"
    COMPOSITION_CONFLICT = "composition_conflict"
    PERMISSION_CONFLICT = "permission_conflict"
    PROFILE_CONFLICT = "profile_conflict"
    RULE_SELECTION_CONFLICT = "rule_selection_conflict"
    PRESENTATION_CONFLICT = "presentation_conflict"
    CROSS_DOMAIN_CONTRADICTION = "cross_domain_contradiction"
    KNOWLEDGE_CONTRADICTION = "knowledge_contradiction"
    SELECTION_CONFLICT = "selection_conflict"
    DOMAIN_SPECIFIC_CONFLICT = "domain_specific_conflict"


class DomainConflictKind(str, Enum):
    SAFETY = "safety"
    PERMISSION = "permission"
    MANDATORY_RULE = "mandatory_rule"
    DOMAIN_RISK = "domain_risk"
    DOMAIN_PRECEDENCE = "domain_precedence"
    EVIDENCE = "evidence"
    RELIABILITY = "reliability"
    TEMPORAL = "temporal"
    PREFERENCE = "preference"
    RECOMMENDATION = "recommendation"
    PRESENTATION = "presentation"
    COMPOSITION = "composition"
    KNOWLEDGE = "knowledge"
    SELECTION = "selection"
    OTHER = "other"


class DomainConflictSeverity(str, Enum):
    ADVISORY = "advisory"
    MATERIAL = "material"
    BLOCKING = "blocking"


class DomainConflictStatus(str, Enum):
    OPEN = "open"
    RESOLVED = "resolved"
    UNRESOLVED = "unresolved"
    BLOCKED = "blocked"
    AWAITING_USER = "awaiting_user"
    AWAITING_HUMAN_REVIEW = "awaiting_human_review"
    POSTPONED = "postponed"


class DomainConflictStrategy(str, Enum):
    MOST_RESTRICTIVE = "most_restrictive"
    HIGH_RISK_DOMAIN_PRECEDENCE = "high_risk_domain_precedence"
    PRIMARY_DOMAIN_PRECEDENCE = "primary_domain_precedence"
    EVIDENCE_WEIGHTED = "evidence_weighted"
    SEPARATE_RESULTS = "separate_results"
    ASK_USER = "ask_user"
    HUMAN_REVIEW = "human_review"
    POSTPONE_ACTION = "postpone_action"
    MAINTAIN_CONFLICT = "maintain_conflict"


class DomainConflictAuthority(str, Enum):
    GLOBAL_SAFETY = "global_safety"
    PERMISSION = "permission"
    MANDATORY_RULE = "mandatory_rule"
    HIGH_RISK_DOMAIN = "high_risk_domain"
    PRIMARY_DOMAIN = "primary_domain"
    EVIDENCE = "evidence"
    RELIABILITY = "reliability"
    TEMPORAL = "temporal"
    USER = "user"
    HUMAN_REVIEW = "human_review"
    UNCLASSIFIED = "unclassified"


class DomainConflictReasonCode(str, Enum):
    SAFETY_PRECEDENCE = "DOMAIN_CONFLICT_SAFETY_PRECEDENCE"
    PERMISSION_PRECEDENCE = "DOMAIN_CONFLICT_PERMISSION_PRECEDENCE"
    MANDATORY_RULE_PRECEDENCE = "DOMAIN_CONFLICT_MANDATORY_RULE_PRECEDENCE"
    HIGH_RISK_PRECEDENCE = "DOMAIN_CONFLICT_HIGH_RISK_PRECEDENCE"
    PRIMARY_PRECEDENCE = "DOMAIN_CONFLICT_PRIMARY_PRECEDENCE"
    EVIDENCE_PRECEDENCE = "DOMAIN_CONFLICT_EVIDENCE_PRECEDENCE"
    RELIABILITY_PRECEDENCE = "DOMAIN_CONFLICT_RELIABILITY_PRECEDENCE"
    TEMPORAL_PRECEDENCE = "DOMAIN_CONFLICT_TEMPORAL_PRECEDENCE"
    USER_INPUT_REQUIRED = "DOMAIN_CONFLICT_USER_INPUT_REQUIRED"
    HUMAN_REVIEW_REQUIRED = "DOMAIN_CONFLICT_HUMAN_REVIEW_REQUIRED"
    ACTION_POSTPONED = "DOMAIN_CONFLICT_ACTION_POSTPONED"
    SEPARATE_RESULTS = "DOMAIN_CONFLICT_SEPARATE_RESULTS"
    PRESERVED = "DOMAIN_CONFLICT_PRESERVED"
    BLOCKING_UNRESOLVED = "DOMAIN_CONFLICT_BLOCKING_UNRESOLVED"
    INSUFFICIENT_BASIS = "DOMAIN_CONFLICT_INSUFFICIENT_BASIS"
    STRATEGY_NOT_APPLICABLE = "DOMAIN_CONFLICT_STRATEGY_NOT_APPLICABLE"


# ── Internal Helpers ──────────────────────────────────────────────────────────

_CREDENTIAL_KEY_SUBSTRINGS = frozenset(
    {
        "password",
        "secret",
        "token",
        "api_key",
        "private_key",
        "credential",
        "auth_token",
        "access_key",
        "secret_key",
    }
)


def _validate_strict_bool(value: Any, field_name: str) -> bool:
    if type(value) is not bool:
        raise DomainConflictResolutionContractError(
            f"{field_name} must be a strict boolean, got {type(value).__name__}: {value!r}",
            field=field_name,
        )
    return value


def _validate_non_empty_str(value: Any, field_name: str) -> str:
    if not isinstance(value, str):
        raise DomainConflictResolutionContractError(
            f"{field_name} must be a string, got {type(value).__name__}: {value!r}",
            field=field_name,
        )
    val = value.strip()
    if not val:
        raise DomainConflictResolutionContractError(
            f"{field_name} must not be empty or whitespace",
            field=field_name,
        )
    return val


def _coerce_enum(
    val: Any,
    enum_cls: type[Enum],
    field_name: str,
    *,
    allow_none: bool = False,
) -> Any:
    if val is None:
        if allow_none:
            return None
        raise DomainConflictResolutionContractError(
            f"{field_name} must not be None",
            field=field_name,
        )
    if isinstance(val, enum_cls):
        return val
    if isinstance(val, str):
        try:
            return enum_cls(val)
        except ValueError:
            valid = sorted(e.value for e in enum_cls)
            raise DomainConflictResolutionContractError(
                f"Invalid {enum_cls.__name__} for {field_name}: {val!r}. Must be one of {valid}",
                field=field_name,
            ) from None
    raise DomainConflictResolutionContractError(
        f"{field_name} must be a {enum_cls.__name__} or string, got {type(val).__name__}: {val!r}",
        field=field_name,
    )


def _coerce_optional_domain_id(
    value: DomainId | str | None,
    field_name: str,
) -> DomainId | None:
    if value is None:
        return None
    if isinstance(value, DomainId):
        return value
    if isinstance(value, str):
        val = value.strip()
        if not val:
            raise DomainConflictResolutionContractError(
                f"{field_name} must not be empty or whitespace",
                field=field_name,
            )
        try:
            return DomainId.from_str(val)
        except Exception as exc:
            raise DomainConflictResolutionContractError(
                f"Invalid DomainId for {field_name}: {value!r}",
                field=field_name,
            ) from exc
    raise DomainConflictResolutionContractError(
        f"{field_name} must be a DomainId, str, or None, got {type(value).__name__}: {value!r}",
        field=field_name,
    )


def _coerce_unique_str_tuple(
    value: tuple[str, ...] | list[str] | Any,
    field_name: str,
) -> tuple[str, ...]:
    if not isinstance(value, (tuple, list)):
        raise DomainConflictResolutionContractError(
            f"{field_name} must be a tuple or list",
            field=field_name,
        )
    result: list[str] = []
    seen: set[str] = set()
    for i, item in enumerate(value):
        validated = _validate_non_empty_str(item, f"{field_name}[{i}]")
        if validated in seen:
            raise DomainConflictResolutionContractError(
                f"Duplicate entry in {field_name}: '{validated}'",
                field=field_name,
            )
        seen.add(validated)
        result.append(validated)
    return tuple(result)


def _validate_json_safe(value: Any, field_name: str) -> Any:
    if value is None:
        return None
    if isinstance(value, (str, int, float)):
        if isinstance(value, float) and not math.isfinite(value):
            raise DomainConflictResolutionContractError(
                f"{field_name}: float must be finite, got {value!r}",
                field=field_name,
            )
        return value
    if isinstance(value, bool):
        return value
    if isinstance(value, Mapping):
        result: dict[str, Any] = {}
        for k, v in value.items():
            if not isinstance(k, str):
                raise DomainConflictResolutionContractError(
                    f"{field_name}: all keys must be strings",
                    field=field_name,
                )
            result[k] = _validate_json_safe(v, f"{field_name}.{k}")
        return result
    if isinstance(value, (list, tuple)):
        return [
            _validate_json_safe(v, f"{field_name}[{i}]") for i, v in enumerate(value)
        ]
    raise DomainConflictResolutionContractError(
        f"{field_name}: value must be JSON-safe, got {type(value).__name__}: {value!r}",
        field=field_name,
    )


def _reject_credential_keys_deep(metadata: Any, field_name: str) -> None:
    if metadata is None:
        return
    if isinstance(metadata, (Mapping, MappingProxyType)):
        for key, value in metadata.items():
            key_lower = key.lower()
            if any(ck in key_lower for ck in _CREDENTIAL_KEY_SUBSTRINGS):
                raise DomainConflictResolutionContractError(
                    f"Credential-like key detected in {field_name}: '{key}'",
                    field=field_name,
                    details={"credential_key": key},
                )
            _reject_credential_keys_deep(value, f"{field_name}.{key}")
    elif isinstance(metadata, (list, tuple)):
        for i, item in enumerate(metadata):
            _reject_credential_keys_deep(item, f"{field_name}[{i}]")


def _validate_json_safe_metadata(
    raw: Any, field_name: str
) -> MappingProxyType[str, Any]:
    if raw is None:
        return MappingProxyType({})
    if isinstance(raw, MappingProxyType):
        _reject_credential_keys_deep(raw, field_name)
        return raw
    validated = _validate_json_safe(raw, field_name)
    frozen = _deep_freeze(validated)
    _reject_credential_keys_deep(frozen, field_name)
    return frozen


def _deep_unfreeze_value(value: Any) -> Any:
    if isinstance(value, (MappingProxyType, Mapping)):
        return {k: _deep_unfreeze_value(v) for k, v in value.items()}
    if isinstance(value, tuple):
        return [_deep_unfreeze_value(v) for v in value]
    if isinstance(value, frozenset):
        return sorted([_deep_unfreeze_value(v) for v in value], key=str)
    return value


def _strict_mapping(
    data: Any,
    expected: frozenset[str],
    name: str,
) -> Mapping[str, Any]:
    if not isinstance(data, Mapping):
        raise DomainConflictResolutionSerializationError(
            f"{name}.from_dict requires a mapping",
            field="data",
        )
    unknown = set(data) - expected
    if unknown:
        raise DomainConflictResolutionSerializationError(
            f"{name}.from_dict received unknown fields: {sorted(unknown)}",
            field="data",
        )
    return data


# ── DomainConflictReference ───────────────────────────────────────────────────

_REFERENCE_KNOWN = frozenset(
    {
        "source_kind",
        "source_id",
        "domain_id",
        "blocking",
        "severity",
        "authority_kind",
        "evidence_refs",
        "metadata",
    }
)


@dataclass(frozen=True, slots=True)
class DomainConflictReference:
    source_kind: DomainConflictSourceKind
    source_id: str
    domain_id: DomainId | None = None
    blocking: bool = False
    severity: DomainConflictSeverity | None = None
    authority_kind: DomainConflictAuthority | None = None
    evidence_refs: tuple[str, ...] = ()
    metadata: MappingProxyType[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "source_kind",
            _coerce_enum(self.source_kind, DomainConflictSourceKind, "source_kind"),
        )
        object.__setattr__(
            self,
            "source_id",
            _validate_non_empty_str(self.source_id, "source_id"),
        )
        object.__setattr__(
            self,
            "domain_id",
            _coerce_optional_domain_id(self.domain_id, "domain_id"),
        )
        object.__setattr__(
            self,
            "blocking",
            _validate_strict_bool(self.blocking, "blocking"),
        )
        object.__setattr__(
            self,
            "severity",
            _coerce_enum(
                self.severity,
                DomainConflictSeverity,
                "severity",
                allow_none=True,
            ),
        )
        object.__setattr__(
            self,
            "authority_kind",
            _coerce_enum(
                self.authority_kind,
                DomainConflictAuthority,
                "authority_kind",
                allow_none=True,
            ),
        )
        object.__setattr__(
            self,
            "evidence_refs",
            _coerce_unique_str_tuple(self.evidence_refs, "evidence_refs"),
        )
        object.__setattr__(
            self,
            "metadata",
            _validate_json_safe_metadata(self.metadata, "metadata"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_kind": self.source_kind.value,
            "source_id": self.source_id,
            "domain_id": str(self.domain_id) if self.domain_id else None,
            "blocking": self.blocking,
            "severity": self.severity.value if self.severity else None,
            "authority_kind": self.authority_kind.value
            if self.authority_kind
            else None,
            "evidence_refs": list(self.evidence_refs),
            "metadata": _deep_unfreeze_value(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> DomainConflictReference:
        mapping = _strict_mapping(data, _REFERENCE_KNOWN, "DomainConflictReference")
        try:
            return cls(
                source_kind=mapping["source_kind"],
                source_id=mapping["source_id"],
                domain_id=mapping.get("domain_id"),
                blocking=mapping.get("blocking", False),
                severity=mapping.get("severity"),
                authority_kind=mapping.get("authority_kind"),
                evidence_refs=tuple(mapping.get("evidence_refs", ())),
                metadata=mapping.get("metadata", {}),
            )
        except DomainConflictResolutionContractError as exc:
            raise DomainConflictResolutionSerializationError(
                exc.message,
                field=exc.field,
            ) from exc
