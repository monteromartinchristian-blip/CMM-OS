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
    if not isinstance(raw, (Mapping, MappingProxyType)):
        raise DomainConflictResolutionContractError(
            f"{field_name} must be a mapping, got {type(raw).__name__}: {raw!r}",
            field=field_name,
        )
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
                evidence_refs=mapping.get("evidence_refs", ()),
                metadata=mapping.get("metadata", {}),
            )
        except KeyError as exc:
            field_name = str(exc.args[0])
            raise DomainConflictResolutionSerializationError(
                f"DomainConflictReference.from_dict missing required field: {field_name}",
                field=field_name,
            ) from exc
        except DomainConflictResolutionContractError as exc:
            raise DomainConflictResolutionSerializationError(
                exc.message,
                field=exc.field,
            ) from exc


# ── Case, Resolution, and Policy Helpers ──────────────────────────────────────


def _coerce_domain_id_tuple(
    value: tuple[DomainId | str, ...] | list[DomainId | str] | Any,
    field_name: str,
) -> tuple[DomainId, ...]:
    if not isinstance(value, (tuple, list)):
        raise DomainConflictResolutionContractError(
            f"{field_name} must be a tuple or list",
            field=field_name,
        )
    result: list[DomainId] = []
    seen: set[str] = set()
    for i, item in enumerate(value):
        did = _coerce_optional_domain_id(item, f"{field_name}[{i}]")
        if did is None:
            raise DomainConflictResolutionContractError(
                f"{field_name}[{i}] must not be None",
                field=field_name,
            )
        slug = str(did)
        if slug not in seen:
            seen.add(slug)
            result.append(did)
    return tuple(result)


def _coerce_references_tuple(
    value: tuple[DomainConflictReference, ...] | list[DomainConflictReference] | Any,
    field_name: str,
) -> tuple[DomainConflictReference, ...]:
    if not isinstance(value, (tuple, list)):
        raise DomainConflictResolutionContractError(
            f"{field_name} must be a tuple or list",
            field=field_name,
        )
    if len(value) == 0:
        raise DomainConflictResolutionContractError(
            f"{field_name} must not be empty",
            field=field_name,
        )
    result: list[DomainConflictReference] = []
    seen_ids: set[str] = set()
    for i, item in enumerate(value):
        if not isinstance(item, DomainConflictReference):
            raise DomainConflictResolutionContractError(
                f"{field_name}[{i}] must be a DomainConflictReference",
                field=field_name,
            )
        if item.source_id in seen_ids:
            raise DomainConflictResolutionContractError(
                f"Duplicate reference source_id in {field_name}: '{item.source_id}'",
                field=field_name,
            )
        seen_ids.add(item.source_id)
        result.append(item)
    return tuple(result)


def _coerce_strategy_tuple(
    value: (
        tuple[DomainConflictStrategy | str, ...]
        | list[DomainConflictStrategy | str]
        | Any
    ),
    field_name: str,
) -> tuple[DomainConflictStrategy, ...]:
    if not isinstance(value, (tuple, list)):
        raise DomainConflictResolutionContractError(
            f"{field_name} must be a tuple or list",
            field=field_name,
        )
    result: list[DomainConflictStrategy] = []
    seen: set[DomainConflictStrategy] = set()
    for i, item in enumerate(value):
        st = _coerce_enum(item, DomainConflictStrategy, f"{field_name}[{i}]")
        if st not in seen:
            seen.add(st)
            result.append(st)
    return tuple(result)


def _coerce_reason_codes_tuple(
    value: (
        tuple[DomainConflictReasonCode | str, ...]
        | list[DomainConflictReasonCode | str]
        | Any
    ),
    field_name: str,
) -> tuple[DomainConflictReasonCode, ...]:
    if not isinstance(value, (tuple, list)):
        raise DomainConflictResolutionContractError(
            f"{field_name} must be a tuple or list",
            field=field_name,
        )
    result: list[DomainConflictReasonCode] = []
    seen: set[DomainConflictReasonCode] = set()
    for i, item in enumerate(value):
        rc = _coerce_enum(item, DomainConflictReasonCode, f"{field_name}[{i}]")
        if rc not in seen:
            seen.add(rc)
            result.append(rc)
    return tuple(result)


# ── DomainConflictCase ─────────────────────────────────────────────────────────

_CASE_KNOWN = frozenset(
    {
        "id",
        "domains",
        "kind",
        "severity",
        "status",
        "references",
        "affected_item_refs",
        "candidate_strategies",
        "requires_human_review",
        "blocking",
        "metadata",
    }
)


@dataclass(frozen=True, slots=True)
class DomainConflictCase:
    id: str
    domains: tuple[DomainId, ...]
    kind: DomainConflictKind
    severity: DomainConflictSeverity
    status: DomainConflictStatus
    references: tuple[DomainConflictReference, ...]
    affected_item_refs: tuple[str, ...] = ()
    candidate_strategies: tuple[DomainConflictStrategy, ...] = ()
    requires_human_review: bool = False
    blocking: bool = False
    metadata: MappingProxyType[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", _validate_non_empty_str(self.id, "id"))
        object.__setattr__(
            self,
            "domains",
            _coerce_domain_id_tuple(self.domains, "domains"),
        )
        object.__setattr__(
            self,
            "kind",
            _coerce_enum(self.kind, DomainConflictKind, "kind"),
        )
        object.__setattr__(
            self,
            "severity",
            _coerce_enum(self.severity, DomainConflictSeverity, "severity"),
        )
        object.__setattr__(
            self,
            "status",
            _coerce_enum(self.status, DomainConflictStatus, "status"),
        )
        object.__setattr__(
            self,
            "references",
            _coerce_references_tuple(self.references, "references"),
        )
        object.__setattr__(
            self,
            "affected_item_refs",
            _coerce_unique_str_tuple(self.affected_item_refs, "affected_item_refs"),
        )
        object.__setattr__(
            self,
            "candidate_strategies",
            _coerce_strategy_tuple(self.candidate_strategies, "candidate_strategies"),
        )
        object.__setattr__(
            self,
            "requires_human_review",
            _validate_strict_bool(self.requires_human_review, "requires_human_review"),
        )
        object.__setattr__(
            self,
            "blocking",
            _validate_strict_bool(self.blocking, "blocking"),
        )
        object.__setattr__(
            self,
            "metadata",
            _validate_json_safe_metadata(self.metadata, "metadata"),
        )

        if self.blocking and self.severity is not DomainConflictSeverity.BLOCKING:
            raise DomainConflictResolutionContractError(
                "blocking=True requires severity=BLOCKING",
                field="blocking",
            )
        if not self.blocking and self.severity is DomainConflictSeverity.BLOCKING:
            raise DomainConflictResolutionContractError(
                "severity=BLOCKING requires blocking=True",
                field="severity",
            )

        if not self.blocking and any(r.blocking for r in self.references):
            raise DomainConflictResolutionContractError(
                "blocking references require case blocking=True",
                field="blocking",
            )

        if self.status is DomainConflictStatus.RESOLVED and (
            self.blocking or any(r.blocking for r in self.references)
        ):
            raise DomainConflictResolutionContractError(
                "RESOLVED case cannot have blocking=True or contain blocking references",
                field="status",
            )

        if self.status is DomainConflictStatus.BLOCKED and not self.blocking:
            raise DomainConflictResolutionContractError(
                "BLOCKED status requires blocking=True",
                field="status",
            )

        if (
            self.status is DomainConflictStatus.AWAITING_HUMAN_REVIEW
            and not self.requires_human_review
        ):
            raise DomainConflictResolutionContractError(
                "AWAITING_HUMAN_REVIEW status requires requires_human_review=True",
                field="requires_human_review",
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "domains": [str(d) for d in self.domains],
            "kind": self.kind.value,
            "severity": self.severity.value,
            "status": self.status.value,
            "references": [r.to_dict() for r in self.references],
            "affected_item_refs": list(self.affected_item_refs),
            "candidate_strategies": [s.value for s in self.candidate_strategies],
            "requires_human_review": self.requires_human_review,
            "blocking": self.blocking,
            "metadata": _deep_unfreeze_value(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> DomainConflictCase:
        mapping = _strict_mapping(data, _CASE_KNOWN, "DomainConflictCase")
        try:
            if "references" not in mapping:
                raise KeyError("references")
            raw_refs = mapping["references"]
            if not isinstance(raw_refs, (tuple, list)):
                raise DomainConflictResolutionContractError(
                    "references must be a tuple or list",
                    field="references",
                )
            references = tuple(
                DomainConflictReference.from_dict(r) if isinstance(r, Mapping) else r
                for r in raw_refs
            )
            return cls(
                id=mapping["id"],
                domains=mapping.get("domains", ()),
                kind=mapping["kind"],
                severity=mapping["severity"],
                status=mapping["status"],
                references=references,
                affected_item_refs=mapping.get("affected_item_refs", ()),
                candidate_strategies=mapping.get("candidate_strategies", ()),
                requires_human_review=mapping.get("requires_human_review", False),
                blocking=mapping.get("blocking", False),
                metadata=mapping.get("metadata", {}),
            )
        except KeyError as exc:
            field_name = str(exc.args[0])
            raise DomainConflictResolutionSerializationError(
                f"DomainConflictCase.from_dict missing required field: {field_name}",
                field=field_name,
            ) from exc
        except DomainConflictResolutionContractError as exc:
            raise DomainConflictResolutionSerializationError(
                exc.message,
                field=exc.field,
            ) from exc


# ── DomainConflictResolution ───────────────────────────────────────────────────

_RESOLUTION_KNOWN = frozenset(
    {
        "conflict_id",
        "status",
        "strategy",
        "winning_reference_ids",
        "preserved_reference_ids",
        "rejected_reference_ids",
        "reason_codes",
        "requires_user_input",
        "requires_human_review",
        "action_postponed",
        "conflict_preserved",
        "can_proceed",
        "metadata",
    }
)


@dataclass(frozen=True, slots=True)
class DomainConflictResolution:
    conflict_id: str
    status: DomainConflictStatus
    strategy: DomainConflictStrategy
    winning_reference_ids: tuple[str, ...] = ()
    preserved_reference_ids: tuple[str, ...] = ()
    rejected_reference_ids: tuple[str, ...] = ()
    reason_codes: tuple[DomainConflictReasonCode, ...] = ()
    requires_user_input: bool = False
    requires_human_review: bool = False
    action_postponed: bool = False
    conflict_preserved: bool = False
    can_proceed: bool = False
    metadata: MappingProxyType[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "conflict_id",
            _validate_non_empty_str(self.conflict_id, "conflict_id"),
        )
        object.__setattr__(
            self,
            "status",
            _coerce_enum(self.status, DomainConflictStatus, "status"),
        )
        object.__setattr__(
            self,
            "strategy",
            _coerce_enum(self.strategy, DomainConflictStrategy, "strategy"),
        )
        object.__setattr__(
            self,
            "winning_reference_ids",
            _coerce_unique_str_tuple(
                self.winning_reference_ids, "winning_reference_ids"
            ),
        )
        object.__setattr__(
            self,
            "preserved_reference_ids",
            _coerce_unique_str_tuple(
                self.preserved_reference_ids, "preserved_reference_ids"
            ),
        )
        object.__setattr__(
            self,
            "rejected_reference_ids",
            _coerce_unique_str_tuple(
                self.rejected_reference_ids, "rejected_reference_ids"
            ),
        )
        object.__setattr__(
            self,
            "reason_codes",
            _coerce_reason_codes_tuple(self.reason_codes, "reason_codes"),
        )
        object.__setattr__(
            self,
            "requires_user_input",
            _validate_strict_bool(self.requires_user_input, "requires_user_input"),
        )
        object.__setattr__(
            self,
            "requires_human_review",
            _validate_strict_bool(self.requires_human_review, "requires_human_review"),
        )
        object.__setattr__(
            self,
            "action_postponed",
            _validate_strict_bool(self.action_postponed, "action_postponed"),
        )
        object.__setattr__(
            self,
            "conflict_preserved",
            _validate_strict_bool(self.conflict_preserved, "conflict_preserved"),
        )
        object.__setattr__(
            self,
            "can_proceed",
            _validate_strict_bool(self.can_proceed, "can_proceed"),
        )
        object.__setattr__(
            self,
            "metadata",
            _validate_json_safe_metadata(self.metadata, "metadata"),
        )

        if set(self.winning_reference_ids) & set(self.rejected_reference_ids):
            raise DomainConflictResolutionContractError(
                "winning_reference_ids and rejected_reference_ids must be disjoint",
                field="winning_reference_ids",
            )

        if self.requires_user_input != (
            self.status is DomainConflictStatus.AWAITING_USER
        ):
            raise DomainConflictResolutionContractError(
                "requires_user_input=True <=> status=AWAITING_USER",
                field="requires_user_input",
            )

        if self.requires_human_review != (
            self.status is DomainConflictStatus.AWAITING_HUMAN_REVIEW
        ):
            raise DomainConflictResolutionContractError(
                "requires_human_review=True <=> status=AWAITING_HUMAN_REVIEW",
                field="requires_human_review",
            )

        if self.action_postponed != (self.status is DomainConflictStatus.POSTPONED):
            raise DomainConflictResolutionContractError(
                "action_postponed=True <=> status=POSTPONED",
                field="action_postponed",
            )

        if self.status is DomainConflictStatus.BLOCKED and self.can_proceed:
            raise DomainConflictResolutionContractError(
                "BLOCKED status requires can_proceed=False",
                field="can_proceed",
            )

        if self.rejected_reference_ids and not self.reason_codes:
            raise DomainConflictResolutionContractError(
                "rejected_reference_ids require at least one auditable reason_code",
                field="reason_codes",
            )

        if self.strategy is DomainConflictStrategy.MAINTAIN_CONFLICT:
            if not self.conflict_preserved:
                raise DomainConflictResolutionContractError(
                    "MAINTAIN_CONFLICT strategy requires conflict_preserved=True",
                    field="conflict_preserved",
                )
            if self.status not in {
                DomainConflictStatus.UNRESOLVED,
                DomainConflictStatus.BLOCKED,
            }:
                raise DomainConflictResolutionContractError(
                    "MAINTAIN_CONFLICT cannot claim semantic resolution",
                    field="status",
                )
            if self.can_proceed:
                raise DomainConflictResolutionContractError(
                    "MAINTAIN_CONFLICT requires can_proceed=False",
                    field="can_proceed",
                )

        if self.strategy is DomainConflictStrategy.SEPARATE_RESULTS:
            if self.status is not DomainConflictStatus.UNRESOLVED:
                raise DomainConflictResolutionContractError(
                    "SEPARATE_RESULTS preserves semantic disagreement and requires status=UNRESOLVED",
                    field="status",
                )
            if not self.conflict_preserved:
                raise DomainConflictResolutionContractError(
                    "SEPARATE_RESULTS requires conflict_preserved=True",
                    field="conflict_preserved",
                )

        if (
            self.strategy is DomainConflictStrategy.POSTPONE_ACTION
            and not self.conflict_preserved
        ):
            raise DomainConflictResolutionContractError(
                "POSTPONE_ACTION strategy requires conflict_preserved=True",
                field="conflict_preserved",
            )

        if (
            self.strategy is DomainConflictStrategy.ASK_USER
            and not self.requires_user_input
        ):
            raise DomainConflictResolutionContractError(
                "ASK_USER strategy requires requires_user_input=True",
                field="requires_user_input",
            )

        if (
            self.strategy is DomainConflictStrategy.HUMAN_REVIEW
            and not self.requires_human_review
        ):
            raise DomainConflictResolutionContractError(
                "HUMAN_REVIEW strategy requires requires_human_review=True",
                field="requires_human_review",
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "conflict_id": self.conflict_id,
            "status": self.status.value,
            "strategy": self.strategy.value,
            "winning_reference_ids": list(self.winning_reference_ids),
            "preserved_reference_ids": list(self.preserved_reference_ids),
            "rejected_reference_ids": list(self.rejected_reference_ids),
            "reason_codes": [rc.value for rc in self.reason_codes],
            "requires_user_input": self.requires_user_input,
            "requires_human_review": self.requires_human_review,
            "action_postponed": self.action_postponed,
            "conflict_preserved": self.conflict_preserved,
            "can_proceed": self.can_proceed,
            "metadata": _deep_unfreeze_value(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> DomainConflictResolution:
        mapping = _strict_mapping(data, _RESOLUTION_KNOWN, "DomainConflictResolution")
        try:
            return cls(
                conflict_id=mapping["conflict_id"],
                status=mapping["status"],
                strategy=mapping["strategy"],
                winning_reference_ids=mapping.get("winning_reference_ids", ()),
                preserved_reference_ids=mapping.get("preserved_reference_ids", ()),
                rejected_reference_ids=mapping.get("rejected_reference_ids", ()),
                reason_codes=mapping.get("reason_codes", ()),
                requires_user_input=mapping.get("requires_user_input", False),
                requires_human_review=mapping.get("requires_human_review", False),
                action_postponed=mapping.get("action_postponed", False),
                conflict_preserved=mapping.get("conflict_preserved", False),
                can_proceed=mapping.get("can_proceed", False),
                metadata=mapping.get("metadata", {}),
            )
        except KeyError as exc:
            field_name = str(exc.args[0])
            raise DomainConflictResolutionSerializationError(
                f"DomainConflictResolution.from_dict missing required field: {field_name}",
                field=field_name,
            ) from exc
        except DomainConflictResolutionContractError as exc:
            raise DomainConflictResolutionSerializationError(
                exc.message,
                field=exc.field,
            ) from exc


# ── DomainConflictResolutionPolicy ─────────────────────────────────────────────

_POLICY_KNOWN = frozenset(
    {
        "default_strategy",
        "blocking_strategy",
        "permission_strategy",
        "mandatory_rule_strategy",
        "high_risk_strategy",
        "primary_strategy",
        "evidence_strategy",
        "allow_separate_results",
        "allow_user_confirmation",
        "allow_human_review",
        "allow_postpone",
        "preserve_unresolved_conflicts",
        "metadata",
    }
)

_PERMISSION_ALLOWED = frozenset(
    {
        DomainConflictStrategy.MOST_RESTRICTIVE,
        DomainConflictStrategy.HUMAN_REVIEW,
        DomainConflictStrategy.MAINTAIN_CONFLICT,
        DomainConflictStrategy.POSTPONE_ACTION,
    }
)

_MANDATORY_ALLOWED = frozenset(
    {
        DomainConflictStrategy.MOST_RESTRICTIVE,
        DomainConflictStrategy.HUMAN_REVIEW,
        DomainConflictStrategy.MAINTAIN_CONFLICT,
        DomainConflictStrategy.POSTPONE_ACTION,
    }
)

_HIGH_RISK_ALLOWED = frozenset(
    {
        DomainConflictStrategy.HIGH_RISK_DOMAIN_PRECEDENCE,
        DomainConflictStrategy.MOST_RESTRICTIVE,
        DomainConflictStrategy.HUMAN_REVIEW,
        DomainConflictStrategy.MAINTAIN_CONFLICT,
        DomainConflictStrategy.POSTPONE_ACTION,
    }
)


@dataclass(frozen=True, slots=True)
class DomainConflictResolutionPolicy:
    default_strategy: DomainConflictStrategy = DomainConflictStrategy.MAINTAIN_CONFLICT
    blocking_strategy: DomainConflictStrategy = DomainConflictStrategy.MAINTAIN_CONFLICT
    permission_strategy: DomainConflictStrategy = (
        DomainConflictStrategy.MOST_RESTRICTIVE
    )
    mandatory_rule_strategy: DomainConflictStrategy = (
        DomainConflictStrategy.MOST_RESTRICTIVE
    )
    high_risk_strategy: DomainConflictStrategy = (
        DomainConflictStrategy.HIGH_RISK_DOMAIN_PRECEDENCE
    )
    primary_strategy: DomainConflictStrategy = (
        DomainConflictStrategy.PRIMARY_DOMAIN_PRECEDENCE
    )
    evidence_strategy: DomainConflictStrategy = DomainConflictStrategy.EVIDENCE_WEIGHTED
    allow_separate_results: bool = True
    allow_user_confirmation: bool = True
    allow_human_review: bool = True
    allow_postpone: bool = True
    preserve_unresolved_conflicts: bool = True
    metadata: MappingProxyType[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "default_strategy",
            _coerce_enum(
                self.default_strategy,
                DomainConflictStrategy,
                "default_strategy",
            ),
        )
        object.__setattr__(
            self,
            "blocking_strategy",
            _coerce_enum(
                self.blocking_strategy,
                DomainConflictStrategy,
                "blocking_strategy",
            ),
        )
        object.__setattr__(
            self,
            "permission_strategy",
            _coerce_enum(
                self.permission_strategy,
                DomainConflictStrategy,
                "permission_strategy",
            ),
        )
        object.__setattr__(
            self,
            "mandatory_rule_strategy",
            _coerce_enum(
                self.mandatory_rule_strategy,
                DomainConflictStrategy,
                "mandatory_rule_strategy",
            ),
        )
        object.__setattr__(
            self,
            "high_risk_strategy",
            _coerce_enum(
                self.high_risk_strategy,
                DomainConflictStrategy,
                "high_risk_strategy",
            ),
        )
        object.__setattr__(
            self,
            "primary_strategy",
            _coerce_enum(
                self.primary_strategy,
                DomainConflictStrategy,
                "primary_strategy",
            ),
        )
        object.__setattr__(
            self,
            "evidence_strategy",
            _coerce_enum(
                self.evidence_strategy,
                DomainConflictStrategy,
                "evidence_strategy",
            ),
        )
        object.__setattr__(
            self,
            "allow_separate_results",
            _validate_strict_bool(
                self.allow_separate_results, "allow_separate_results"
            ),
        )
        object.__setattr__(
            self,
            "allow_user_confirmation",
            _validate_strict_bool(
                self.allow_user_confirmation, "allow_user_confirmation"
            ),
        )
        object.__setattr__(
            self,
            "allow_human_review",
            _validate_strict_bool(self.allow_human_review, "allow_human_review"),
        )
        object.__setattr__(
            self,
            "allow_postpone",
            _validate_strict_bool(self.allow_postpone, "allow_postpone"),
        )
        object.__setattr__(
            self,
            "preserve_unresolved_conflicts",
            _validate_strict_bool(
                self.preserve_unresolved_conflicts,
                "preserve_unresolved_conflicts",
            ),
        )
        object.__setattr__(
            self,
            "metadata",
            _validate_json_safe_metadata(self.metadata, "metadata"),
        )

        if self.permission_strategy not in _PERMISSION_ALLOWED:
            raise DomainConflictResolutionContractError(
                f"permission_strategy must be one of {sorted(s.value for s in _PERMISSION_ALLOWED)}, got {self.permission_strategy.value!r}",
                field="permission_strategy",
            )

        if self.mandatory_rule_strategy not in _MANDATORY_ALLOWED:
            raise DomainConflictResolutionContractError(
                f"mandatory_rule_strategy must be one of {sorted(s.value for s in _MANDATORY_ALLOWED)}, got {self.mandatory_rule_strategy.value!r}",
                field="mandatory_rule_strategy",
            )

        if self.high_risk_strategy not in _HIGH_RISK_ALLOWED:
            raise DomainConflictResolutionContractError(
                f"high_risk_strategy must be one of {sorted(s.value for s in _HIGH_RISK_ALLOWED)}, got {self.high_risk_strategy.value!r}",
                field="high_risk_strategy",
            )

        configured_strategies = {
            self.default_strategy,
            self.blocking_strategy,
            self.permission_strategy,
            self.mandatory_rule_strategy,
            self.high_risk_strategy,
            self.primary_strategy,
            self.evidence_strategy,
        }

        if (
            DomainConflictStrategy.HUMAN_REVIEW in configured_strategies
            and not self.allow_human_review
        ):
            raise DomainConflictResolutionContractError(
                "HUMAN_REVIEW configured but allow_human_review is False",
                field="allow_human_review",
            )

        if (
            DomainConflictStrategy.ASK_USER in configured_strategies
            and not self.allow_user_confirmation
        ):
            raise DomainConflictResolutionContractError(
                "ASK_USER configured but allow_user_confirmation is False",
                field="allow_user_confirmation",
            )

        if (
            DomainConflictStrategy.POSTPONE_ACTION in configured_strategies
            and not self.allow_postpone
        ):
            raise DomainConflictResolutionContractError(
                "POSTPONE_ACTION configured but allow_postpone is False",
                field="allow_postpone",
            )

        if (
            DomainConflictStrategy.SEPARATE_RESULTS in configured_strategies
            and not self.allow_separate_results
        ):
            raise DomainConflictResolutionContractError(
                "SEPARATE_RESULTS configured but allow_separate_results is False",
                field="allow_separate_results",
            )

        if not self.preserve_unresolved_conflicts:
            raise DomainConflictResolutionContractError(
                "preserve_unresolved_conflicts must be True",
                field="preserve_unresolved_conflicts",
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "default_strategy": self.default_strategy.value,
            "blocking_strategy": self.blocking_strategy.value,
            "permission_strategy": self.permission_strategy.value,
            "mandatory_rule_strategy": self.mandatory_rule_strategy.value,
            "high_risk_strategy": self.high_risk_strategy.value,
            "primary_strategy": self.primary_strategy.value,
            "evidence_strategy": self.evidence_strategy.value,
            "allow_separate_results": self.allow_separate_results,
            "allow_user_confirmation": self.allow_user_confirmation,
            "allow_human_review": self.allow_human_review,
            "allow_postpone": self.allow_postpone,
            "preserve_unresolved_conflicts": self.preserve_unresolved_conflicts,
            "metadata": _deep_unfreeze_value(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> DomainConflictResolutionPolicy:
        mapping = _strict_mapping(data, _POLICY_KNOWN, "DomainConflictResolutionPolicy")
        try:
            return cls(
                default_strategy=mapping.get(
                    "default_strategy",
                    DomainConflictStrategy.MAINTAIN_CONFLICT,
                ),
                blocking_strategy=mapping.get(
                    "blocking_strategy",
                    DomainConflictStrategy.MAINTAIN_CONFLICT,
                ),
                permission_strategy=mapping.get(
                    "permission_strategy",
                    DomainConflictStrategy.MOST_RESTRICTIVE,
                ),
                mandatory_rule_strategy=mapping.get(
                    "mandatory_rule_strategy",
                    DomainConflictStrategy.MOST_RESTRICTIVE,
                ),
                high_risk_strategy=mapping.get(
                    "high_risk_strategy",
                    DomainConflictStrategy.HIGH_RISK_DOMAIN_PRECEDENCE,
                ),
                primary_strategy=mapping.get(
                    "primary_strategy",
                    DomainConflictStrategy.PRIMARY_DOMAIN_PRECEDENCE,
                ),
                evidence_strategy=mapping.get(
                    "evidence_strategy",
                    DomainConflictStrategy.EVIDENCE_WEIGHTED,
                ),
                allow_separate_results=mapping.get("allow_separate_results", True),
                allow_user_confirmation=mapping.get("allow_user_confirmation", True),
                allow_human_review=mapping.get("allow_human_review", True),
                allow_postpone=mapping.get("allow_postpone", True),
                preserve_unresolved_conflicts=mapping.get(
                    "preserve_unresolved_conflicts", True
                ),
                metadata=mapping.get("metadata", {}),
            )
        except DomainConflictResolutionContractError as exc:
            raise DomainConflictResolutionSerializationError(
                exc.message,
                field=exc.field,
            ) from exc
