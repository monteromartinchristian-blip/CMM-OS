"""Phase 10.7 – Domain Resolver Contracts.

Immutable, JSON-serializable, type-safe contracts consumed and produced by
the Domain Resolution subsystem.  All dataclasses are ``frozen=True`` and
never expose mutable internal state.

No live registry access, no LLM calls, no network, no filesystem.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from types import MappingProxyType
from typing import Any

from cmm.domains.contracts import (
    _deep_freeze,
    _ensure_tz_aware,
    _normalize_empty_to_none,
    _reject_unknown_fields,
    _validate_non_empty_str,
    _validate_strict_bool,
)
from cmm.domains.enums import DomainResolutionStatus
from cmm.domains.errors import (
    DomainContractValidationError,
    DomainResolutionSerializationError,
)
from cmm.domains.identifiers import DomainId

# ── JSON-safe type alias (mirrors resolution_contracts) ────────────────────────

JSONValue = (
    str | int | float | bool | None | Mapping[str, "JSONValue"] | list["JSONValue"]
)


# ── Helper: validate JSON-safe metadata (freeze + reject credentials) ───────────


def _validate_json_safe(value: Any, field_name: str) -> Any:
    """Validate that a value is JSON-safe (recursively)."""
    if value is None:
        return None
    if isinstance(value, (str, int, float)):
        if isinstance(value, float) and not math.isfinite(value):
            raise DomainContractValidationError(
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
                raise DomainContractValidationError(
                    f"{field_name}: all keys must be strings",
                    field=field_name,
                )
            result[k] = _validate_json_safe(v, f"{field_name}.{k}")
        return result
    if isinstance(value, (list, tuple)):
        return [
            _validate_json_safe(v, f"{field_name}[{i}]") for i, v in enumerate(value)
        ]
    raise DomainContractValidationError(
        f"{field_name}: value must be JSON-safe, got {type(value).__name__}: {value!r}",
        field=field_name,
    )


def _validate_json_safe_metadata(
    raw: Any, field_name: str
) -> MappingProxyType[str, Any]:
    """Validate metadata is JSON-safe and deep-freeze it."""
    if raw is None:
        return MappingProxyType({})
    if isinstance(raw, MappingProxyType):
        return raw
    validated = _validate_json_safe(raw, field_name)
    return _deep_freeze(validated)


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


def _reject_credential_keys_deep(metadata: Any, field_name: str) -> None:
    """Recursively scan for credential-like keys in a JSON-safe structure."""
    if metadata is None:
        return
    if isinstance(metadata, Mapping):
        for key, value in metadata.items():
            key_lower = key.lower()
            if any(ck in key_lower for ck in _CREDENTIAL_KEY_SUBSTRINGS):
                raise DomainContractValidationError(
                    f"Credential-like key detected in {field_name}: '{key}'",
                    field=field_name,
                    details={"credential_key": key},
                )
            _reject_credential_keys_deep(value, f"{field_name}.{key}")
    elif isinstance(metadata, (list, tuple)):
        for i, item in enumerate(metadata):
            _reject_credential_keys_deep(item, f"{field_name}[{i}]")


# ── Numeric validation helpers ─────────────────────────────────────────────────


def _validate_finite_float(val: Any, field_name: str) -> float:
    """Validate a finite float, rejecting bool, NaN, Inf."""
    if isinstance(val, bool):
        raise DomainContractValidationError(
            f"{field_name} must be a number, not a boolean", field=field_name
        )
    if isinstance(val, int):
        val = float(val)
    elif isinstance(val, float):
        pass
    else:
        raise DomainContractValidationError(
            f"{field_name} must be an int or float, got {type(val).__name__}: {val!r}",
            field=field_name,
        )
    if not math.isfinite(val):
        raise DomainContractValidationError(
            f"{field_name} must be a finite number, got {val!r}", field=field_name
        )
    return val


def _validate_confidence(val: Any, field_name: str) -> float:
    """Validate confidence: finite float in [0, 1], reject bool."""
    f = _validate_finite_float(val, field_name)
    if not (0.0 <= f <= 1.0):
        raise DomainContractValidationError(
            f"{field_name} must be between 0.0 and 1.0, got {f!r}", field=field_name
        )
    return f


def _validate_confidence_opt(val: Any, field_name: str) -> float | None:
    """Validate optional confidence: None or finite float in [0, 1]."""
    if val is None:
        return None
    return _validate_confidence(val, field_name)


def _validate_non_negative_float(val: Any, field_name: str) -> float:
    """Validate a non-negative float, rejecting bool."""
    f = _validate_finite_float(val, field_name)
    if f < 0.0:
        raise DomainContractValidationError(
            f"{field_name} must be non-negative, got {f!r}", field=field_name
        )
    return f


def _validate_contribution(val: Any, field_name: str) -> float:
    """Validate contribution: finite float, not bool, not NaN/Inf.

    Contributions can be positive, zero, or negative.
    """
    if isinstance(val, bool):
        raise DomainContractValidationError(
            f"{field_name} must be a number, not a boolean", field=field_name
        )
    if isinstance(val, int):
        val = float(val)
    elif isinstance(val, float):
        pass
    else:
        raise DomainContractValidationError(
            f"{field_name} must be an int or float, got {type(val).__name__}: {val!r}",
            field=field_name,
        )
    if not math.isfinite(val):
        raise DomainContractValidationError(
            f"{field_name} must be a finite number, got {val!r}", field=field_name
        )
    return val


# ── DomainId coercion helpers ──────────────────────────────────────────────────


def _coerce_domain_id(val: Any, field_name: str) -> DomainId:
    """Coerce a string or DomainId to a DomainId."""
    if isinstance(val, DomainId):
        return val
    if isinstance(val, str):
        try:
            return DomainId.from_str(val)
        except (ValueError, TypeError, DomainContractValidationError) as exc:
            raise DomainContractValidationError(
                f"Invalid DomainId in {field_name}: {exc}",
                field=field_name,
            ) from exc
    raise DomainContractValidationError(
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
        raise DomainContractValidationError(
            f"{field_name} must be a sequence of DomainId, not a string",
            field=field_name,
        )
    if not isinstance(seq, (tuple, list, set, Sequence)):
        raise DomainContractValidationError(
            f"{field_name} must be a tuple, list, or sequence",
            field=field_name,
        )
    result: list[DomainId] = []
    seen: set[str] = set()
    for i, item in enumerate(seq):
        domain_id = _coerce_domain_id(item, f"{field_name}[{i}]")
        slug = domain_id.slug
        if require_unique and slug in seen:
            raise DomainContractValidationError(
                f"Duplicate domain in {field_name}: {slug}",
                field=field_name,
                details={"duplicate": slug, "index": i},
            )
        if require_unique:
            seen.add(slug)
        result.append(domain_id)
    return tuple(result)


def _freeze_domain_ids_from_dict(
    data_raw: Any, field_name: str, *, require_unique: bool = True
) -> tuple[DomainId, ...]:
    """Like _freeze_domain_ids but raises DomainResolutionSerializationError."""
    try:
        return _freeze_domain_ids(data_raw, field_name, require_unique=require_unique)
    except DomainContractValidationError as exc:
        raise DomainResolutionSerializationError(
            exc.message, field=exc.field, details=dict(exc.details)
        ) from exc


def _parse_datetime_opt(val: Any, field_name: str) -> datetime | None:
    """Parse string or datetime to timezone-aware datetime or None."""
    if val is None:
        return None
    if isinstance(val, datetime):
        return _ensure_tz_aware(val, field_name)
    if isinstance(val, str):
        try:
            parsed = datetime.fromisoformat(val)
        except ValueError as exc:
            raise DomainResolutionSerializationError(
                f"Invalid isoformat datetime string for {field_name}: {val!r}",
                field=field_name,
            ) from exc
        if parsed.tzinfo is None:
            raise DomainResolutionSerializationError(
                f"{field_name} must be timezone-aware",
                field=field_name,
            )
        return parsed
    raise DomainResolutionSerializationError(
        f"{field_name} must be an ISO string or datetime instance, got {type(val).__name__}",
        field=field_name,
    )


# ── Deep unfreeze for serialization ────────────────────────────────────────────


def _deep_unfreeze_value(value: Any) -> Any:
    """Unfreeze a single value for serialization."""
    if isinstance(value, MappingProxyType):
        return {k: _deep_unfreeze_value(v) for k, v in value.items()}
    if isinstance(value, tuple):
        return [_deep_unfreeze_value(v) for v in value]
    if isinstance(value, frozenset):
        return sorted([_deep_unfreeze_value(v) for v in value], key=str)
    return value


# ═══════════════════════════════════════════════════════════════════════════════
# Phase 10.7 Contracts
# ═══════════════════════════════════════════════════════════════════════════════


# ── DomainScoringPolicy ──────────────────────────────────────────────────────


_SCORING_POLICY_KNOWN = frozenset(
    {
        "explicit_weight",
        "resource_weight",
        "operation_weight",
        "workflow_weight",
        "intent_weight",
        "entity_weight",
        "objective_weight",
        "knowledge_weight",
        "session_weight",
        "goal_weight",
        "event_weight",
        "profile_weight",
        "history_weight",
        "user_preference_weight",
        "system_policy_weight",
        "active_bonus",
        "degraded_penalty",
        "ambiguity_margin",
        "supporting_margin",
        "minimum_resolution_score",
        "default_minimum_confidence",
        "high_impact_minimum_confidence",
        "max_supporting_domains",
        "confidence_scale",
    }
)


@dataclass(frozen=True, slots=True)
class DomainScoringPolicy:
    """Immutable configuration for the domain candidate scorer.

    All weights and thresholds are finite, non-negative numbers.
    Confidence values must be in [0, 1].
    """

    explicit_weight: float = 100.0
    resource_weight: float = 40.0
    operation_weight: float = 35.0
    workflow_weight: float = 30.0
    intent_weight: float = 25.0
    entity_weight: float = 20.0
    objective_weight: float = 20.0
    knowledge_weight: float = 15.0
    session_weight: float = 15.0
    goal_weight: float = 15.0
    event_weight: float = 15.0
    profile_weight: float = 10.0
    history_weight: float = 8.0
    user_preference_weight: float = 5.0
    system_policy_weight: float = 5.0
    active_bonus: float = 5.0
    degraded_penalty: float = 5.0
    ambiguity_margin: float = 5.0
    supporting_margin: float = 15.0
    minimum_resolution_score: float = 10.0
    default_minimum_confidence: float = 0.55
    high_impact_minimum_confidence: float = 0.80
    max_supporting_domains: int = 3
    confidence_scale: float = 100.0

    def __post_init__(self) -> None:
        # Validate all weights (non-negative floats)
        weight_fields = [
            "explicit_weight",
            "resource_weight",
            "operation_weight",
            "workflow_weight",
            "intent_weight",
            "entity_weight",
            "objective_weight",
            "knowledge_weight",
            "session_weight",
            "goal_weight",
            "event_weight",
            "profile_weight",
            "history_weight",
            "user_preference_weight",
            "system_policy_weight",
        ]
        for fname in weight_fields:
            object.__setattr__(
                self, fname, _validate_non_negative_float(getattr(self, fname), fname)
            )

        # Bonuses / penalties
        for fname in ("active_bonus", "degraded_penalty"):
            object.__setattr__(
                self, fname, _validate_non_negative_float(getattr(self, fname), fname)
            )

        # Margins
        for fname in ("ambiguity_margin", "supporting_margin"):
            object.__setattr__(
                self, fname, _validate_non_negative_float(getattr(self, fname), fname)
            )

        object.__setattr__(
            self,
            "minimum_resolution_score",
            _validate_non_negative_float(
                self.minimum_resolution_score, "minimum_resolution_score"
            ),
        )

        # Confidence thresholds
        for fname in (
            "default_minimum_confidence",
            "high_impact_minimum_confidence",
        ):
            object.__setattr__(
                self,
                fname,
                _validate_confidence(getattr(self, fname), fname),
            )

        # Confidence scale: finite positive
        object.__setattr__(
            self,
            "confidence_scale",
            _validate_non_negative_float(self.confidence_scale, "confidence_scale"),
        )
        if self.confidence_scale == 0.0:
            raise DomainContractValidationError(
                "confidence_scale must be positive", field="confidence_scale"
            )

        # max_supporting_domains: positive integer
        if not isinstance(self.max_supporting_domains, int) or isinstance(
            self.max_supporting_domains, bool
        ):
            raise DomainContractValidationError(
                "max_supporting_domains must be an integer",
                field="max_supporting_domains",
            )
        if self.max_supporting_domains < 0:
            raise DomainContractValidationError(
                "max_supporting_domains must be non-negative",
                field="max_supporting_domains",
            )

        # Cross-field: high_impact_minimum_confidence >= default
        if self.high_impact_minimum_confidence < self.default_minimum_confidence:
            raise DomainContractValidationError(
                "high_impact_minimum_confidence must be >= default_minimum_confidence",
                field="high_impact_minimum_confidence",
                details={
                    "high": self.high_impact_minimum_confidence,
                    "default": self.default_minimum_confidence,
                },
            )

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "explicit_weight": self.explicit_weight,
            "resource_weight": self.resource_weight,
            "operation_weight": self.operation_weight,
            "workflow_weight": self.workflow_weight,
            "intent_weight": self.intent_weight,
            "entity_weight": self.entity_weight,
            "objective_weight": self.objective_weight,
            "knowledge_weight": self.knowledge_weight,
            "session_weight": self.session_weight,
            "goal_weight": self.goal_weight,
            "event_weight": self.event_weight,
            "profile_weight": self.profile_weight,
            "history_weight": self.history_weight,
            "user_preference_weight": self.user_preference_weight,
            "system_policy_weight": self.system_policy_weight,
            "active_bonus": self.active_bonus,
            "degraded_penalty": self.degraded_penalty,
            "ambiguity_margin": self.ambiguity_margin,
            "supporting_margin": self.supporting_margin,
            "minimum_resolution_score": self.minimum_resolution_score,
            "default_minimum_confidence": self.default_minimum_confidence,
            "high_impact_minimum_confidence": self.high_impact_minimum_confidence,
            "max_supporting_domains": self.max_supporting_domains,
            "confidence_scale": self.confidence_scale,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DomainScoringPolicy:
        """Deserialize from dictionary."""
        if not isinstance(data, Mapping):
            raise DomainResolutionSerializationError(
                "DomainScoringPolicy.from_dict requires a mapping", field="data"
            )
        _reject_unknown_fields(data, _SCORING_POLICY_KNOWN, "DomainScoringPolicy")
        return cls(**{k: data[k] for k in _SCORING_POLICY_KNOWN if k in data})


# ── DomainResolutionReason ───────────────────────────────────────────────────


_REASON_KNOWN = frozenset(
    {
        "code",
        "message",
        "domain_id",
        "signal_kind",
        "contribution",
        "blocking",
        "metadata",
    }
)


@dataclass(frozen=True, slots=True)
class DomainResolutionReason:
    """Immutable, structured reason explaining a resolution decision.

    Invariants:
    * ``code`` is stable, namespaced, and non-empty.
    * ``message`` is safe (no secrets, no arbitrary exception strings).
    * ``contribution`` is a finite float (can be positive, zero, or negative),
      never a bool.
    * ``blocking`` is a strict bool.
    * ``metadata`` is JSON-safe and frozen.
    """

    code: str
    message: str
    domain_id: DomainId | None = None
    signal_kind: str | None = None
    contribution: float | None = None
    blocking: bool = False
    metadata: MappingProxyType[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )

    def __post_init__(self) -> None:
        object.__setattr__(self, "code", _validate_non_empty_str(self.code, "code"))
        object.__setattr__(
            self, "message", _validate_non_empty_str(self.message, "message")
        )
        if self.domain_id is not None:
            object.__setattr__(
                self, "domain_id", _coerce_domain_id(self.domain_id, "domain_id")
            )
        object.__setattr__(
            self, "signal_kind", _normalize_empty_to_none(self.signal_kind)
        )
        if self.contribution is not None:
            object.__setattr__(
                self,
                "contribution",
                _validate_contribution(self.contribution, "contribution"),
            )
        object.__setattr__(
            self, "blocking", _validate_strict_bool(self.blocking, "blocking")
        )
        object.__setattr__(
            self, "metadata", _validate_json_safe_metadata(self.metadata, "metadata")
        )
        _reject_credential_keys_deep(self.metadata, "metadata")

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "code": self.code,
            "message": self.message,
            "domain_id": str(self.domain_id) if self.domain_id else None,
            "signal_kind": self.signal_kind,
            "contribution": self.contribution,
            "blocking": self.blocking,
            "metadata": _deep_unfreeze_value(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DomainResolutionReason:
        """Deserialize from dictionary."""
        if not isinstance(data, Mapping):
            raise DomainResolutionSerializationError(
                "DomainResolutionReason.from_dict requires a mapping", field="data"
            )
        _reject_unknown_fields(data, _REASON_KNOWN, "DomainResolutionReason")
        required = {"code", "message"}
        missing = required - set(data.keys())
        if missing:
            raise DomainResolutionSerializationError(
                f"DomainResolutionReason.from_dict missing required fields: {sorted(missing)}",
                field="data",
            )
        domain_id_raw = data.get("domain_id")
        domain_id: DomainId | None = None
        if domain_id_raw is not None:
            if isinstance(domain_id_raw, DomainId):
                domain_id = domain_id_raw
            elif isinstance(domain_id_raw, str):
                domain_id = _coerce_domain_id(domain_id_raw, "domain_id")
            else:
                raise DomainResolutionSerializationError(
                    f"domain_id must be string or DomainId, got {type(domain_id_raw).__name__}",
                    field="domain_id",
                )
        return cls(
            code=str(data["code"]),
            message=str(data["message"]),
            domain_id=domain_id,
            signal_kind=data.get("signal_kind"),
            contribution=data.get("contribution"),
            blocking=bool(data.get("blocking", False)),
            metadata=data.get("metadata"),
        )


# ── DomainCandidateScore ─────────────────────────────────────────────────────


_CANDIDATE_SCORE_KNOWN = frozenset(
    {
        "domain_id",
        "score",
        "confidence",
        "eligible",
        "rejected",
        "rejection_codes",
        "reasons",
        "matched_signal_kinds",
        "metadata",
    }
)


def _freeze_reasons_tuple(
    seq: Any, field_name: str
) -> tuple[DomainResolutionReason, ...]:
    """Validate and freeze a sequence of DomainResolutionReason."""
    if seq is None:
        return ()
    if isinstance(seq, (str, bytes)):
        raise DomainContractValidationError(
            f"{field_name} must be a sequence, not a string", field=field_name
        )
    if not isinstance(seq, (tuple, list, Sequence)):
        raise DomainContractValidationError(
            f"{field_name} must be a list or tuple", field=field_name
        )
    result: list[DomainResolutionReason] = []
    for i, item in enumerate(seq):
        item_path = f"{field_name}[{i}]"
        if isinstance(item, DomainResolutionReason):
            result.append(item)
        elif isinstance(item, Mapping):
            try:
                result.append(DomainResolutionReason.from_dict(dict(item)))
            except (
                DomainContractValidationError,
                DomainResolutionSerializationError,
                ValueError,
                TypeError,
            ) as exc:
                raise DomainContractValidationError(
                    f"Invalid reason at {item_path}: {exc}",
                    field=item_path,
                ) from exc
        else:
            raise DomainContractValidationError(
                f"Each item in {field_name} must be a DomainResolutionReason or mapping, "
                f"got {type(item).__name__}",
                field=item_path,
            )
    # Deduplicate by code+domain_id+signal_kind
    seen: set[tuple[str, str, str]] = set()
    deduped: list[DomainResolutionReason] = []
    for r in result:
        key = (r.code, str(r.domain_id) if r.domain_id else "", r.signal_kind or "")
        if key not in seen:
            seen.add(key)
            deduped.append(r)
    return tuple(deduped)


@dataclass(frozen=True, slots=True)
class DomainCandidateScore:
    """Immutable score for a single domain candidate.

    Invariants:
    * ``score`` is a finite float.
    * ``confidence`` is in [0, 1].
    * ``eligible`` and ``rejected`` cannot both be True.
    * ``rejected`` requires at least one ``rejection_code``.
    * ``eligible == False`` does NOT imply ``rejected == True``.
    * ``reasons`` are ordered deterministically.
    * ``matched_signal_kinds`` are unique strings.
    """

    domain_id: DomainId
    score: float
    confidence: float
    eligible: bool
    rejected: bool
    rejection_codes: tuple[str, ...] = ()
    reasons: tuple[DomainResolutionReason, ...] = ()
    matched_signal_kinds: tuple[str, ...] = ()
    metadata: MappingProxyType[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "domain_id", _coerce_domain_id(self.domain_id, "domain_id")
        )
        object.__setattr__(self, "score", _validate_finite_float(self.score, "score"))
        object.__setattr__(
            self, "confidence", _validate_confidence(self.confidence, "confidence")
        )
        object.__setattr__(
            self, "eligible", _validate_strict_bool(self.eligible, "eligible")
        )
        object.__setattr__(
            self, "rejected", _validate_strict_bool(self.rejected, "rejected")
        )
        # Eligible and rejected cannot both be True
        if self.eligible and self.rejected:
            raise DomainContractValidationError(
                "eligible and rejected cannot both be True",
                field="eligible",
                details={"domain": str(self.domain_id)},
            )
        # Rejected requires at least one rejection code
        if self.rejected and len(self.rejection_codes) == 0:
            raise DomainContractValidationError(
                "Rejected candidate must have at least one rejection code",
                field="rejection_codes",
                details={"domain": str(self.domain_id)},
            )
        # rejection_codes: unique, non-empty strings
        object.__setattr__(
            self,
            "rejection_codes",
            _freeze_unique_str_tuple(self.rejection_codes, "rejection_codes"),
        )
        # Reasons
        object.__setattr__(
            self, "reasons", _freeze_reasons_tuple(self.reasons, "reasons")
        )
        # matched_signal_kinds: unique, non-empty strings
        object.__setattr__(
            self,
            "matched_signal_kinds",
            _freeze_unique_str_tuple(self.matched_signal_kinds, "matched_signal_kinds"),
        )
        object.__setattr__(
            self, "metadata", _validate_json_safe_metadata(self.metadata, "metadata")
        )
        _reject_credential_keys_deep(self.metadata, "metadata")

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "domain_id": str(self.domain_id),
            "score": self.score,
            "confidence": self.confidence,
            "eligible": self.eligible,
            "rejected": self.rejected,
            "rejection_codes": list(self.rejection_codes),
            "reasons": [r.to_dict() for r in self.reasons],
            "matched_signal_kinds": list(self.matched_signal_kinds),
            "metadata": _deep_unfreeze_value(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DomainCandidateScore:
        """Deserialize from dictionary."""
        if not isinstance(data, Mapping):
            raise DomainResolutionSerializationError(
                "DomainCandidateScore.from_dict requires a mapping", field="data"
            )
        _reject_unknown_fields(data, _CANDIDATE_SCORE_KNOWN, "DomainCandidateScore")
        required = {"domain_id", "score", "confidence", "eligible", "rejected"}
        missing = required - set(data.keys())
        if missing:
            raise DomainResolutionSerializationError(
                f"DomainCandidateScore.from_dict missing required fields: {sorted(missing)}",
                field="data",
            )
        domain_id_raw = data["domain_id"]
        if isinstance(domain_id_raw, DomainId):
            domain_id = domain_id_raw
        elif isinstance(domain_id_raw, str):
            domain_id = _coerce_domain_id(domain_id_raw, "domain_id")
        else:
            raise DomainResolutionSerializationError(
                f"domain_id must be string or DomainId, got {type(domain_id_raw).__name__}",
                field="domain_id",
            )
        reasons_raw = data.get("reasons", ())
        if isinstance(reasons_raw, (list, tuple)):
            reasons_list = []
            for i, r in enumerate(reasons_raw):
                if isinstance(r, DomainResolutionReason):
                    reasons_list.append(r)
                elif isinstance(r, Mapping):
                    reasons_list.append(DomainResolutionReason.from_dict(dict(r)))
                else:
                    raise DomainResolutionSerializationError(
                        f"reasons[{i}] must be a mapping, got {type(r).__name__}",
                        field=f"reasons[{i}]",
                    )
            reasons = tuple(reasons_list)
        else:
            reasons = ()
        return cls(
            domain_id=domain_id,
            score=data["score"],
            confidence=data["confidence"],
            eligible=bool(data["eligible"]),
            rejected=bool(data["rejected"]),
            rejection_codes=tuple(data.get("rejection_codes", ())),
            reasons=reasons,
            matched_signal_kinds=tuple(data.get("matched_signal_kinds", ())),
            metadata=data.get("metadata"),
        )


def _freeze_unique_str_tuple(seq: Any, field_name: str) -> tuple[str, ...]:
    """Validate and freeze a sequence of unique, non-empty strings."""
    if seq is None:
        return ()
    if isinstance(seq, (str, bytes)):
        raise DomainContractValidationError(
            f"{field_name} must be a sequence of strings, not a string",
            field=field_name,
        )
    if not isinstance(seq, (tuple, list, set, Sequence)):
        raise DomainContractValidationError(
            f"{field_name} must be a list or tuple of strings",
            field=field_name,
        )
    result: list[str] = []
    seen: set[str] = set()
    for i, item in enumerate(seq):
        if not isinstance(item, str) or not item.strip():
            raise DomainContractValidationError(
                f"All items in {field_name} must be non-empty strings",
                field=field_name,
                details={"index": i, "value": item},
            )
        clean = item.strip()
        if clean in seen:
            raise DomainContractValidationError(
                f"Duplicate item in {field_name}: {clean!r}",
                field=field_name,
                details={"duplicate": clean},
            )
        seen.add(clean)
        result.append(clean)
    return tuple(result)


# ── DomainResolutionResult ───────────────────────────────────────────────────


_RESULT_KNOWN = frozenset(
    {
        "id",
        "context_id",
        "status",
        "primary_domain",
        "supporting_domains",
        "rejected_domains",
        "ambiguous_domains",
        "confidence",
        "reasons",
        "candidate_scores",
        "requires_clarification",
        "recommended_question",
        "fallback_used",
        "resolved_at",
        "metadata",
    }
)


@dataclass(frozen=True, slots=True)
class DomainResolutionResult:
    """Immutable result of a domain resolution operation.

    Status-specific invariants are validated in ``__post_init__``.
    """

    id: str
    context_id: str
    status: DomainResolutionStatus

    primary_domain: DomainId | None = None
    supporting_domains: tuple[DomainId, ...] = ()
    rejected_domains: tuple[DomainId, ...] = ()
    ambiguous_domains: tuple[DomainId, ...] = ()

    confidence: float = 0.0
    reasons: tuple[DomainResolutionReason, ...] = ()
    candidate_scores: tuple[DomainCandidateScore, ...] = ()

    requires_clarification: bool = False
    recommended_question: str | None = None

    fallback_used: bool = False
    resolved_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: MappingProxyType[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", _validate_non_empty_str(self.id, "id"))
        object.__setattr__(
            self, "context_id", _validate_non_empty_str(self.context_id, "context_id")
        )
        if not isinstance(self.status, DomainResolutionStatus):
            raise DomainContractValidationError(
                f"status must be a DomainResolutionStatus, got {type(self.status).__name__}",
                field="status",
            )
        object.__setattr__(
            self, "resolved_at", _ensure_tz_aware(self.resolved_at, "resolved_at")
        )

        # Primary domain
        if self.primary_domain is not None:
            object.__setattr__(
                self,
                "primary_domain",
                _coerce_domain_id(self.primary_domain, "primary_domain"),
            )

        # Domain tuples
        object.__setattr__(
            self,
            "supporting_domains",
            _freeze_domain_ids(self.supporting_domains, "supporting_domains"),
        )
        object.__setattr__(
            self,
            "rejected_domains",
            _freeze_domain_ids(self.rejected_domains, "rejected_domains"),
        )
        object.__setattr__(
            self,
            "ambiguous_domains",
            _freeze_domain_ids(self.ambiguous_domains, "ambiguous_domains"),
        )

        # Confidence
        object.__setattr__(
            self, "confidence", _validate_confidence(self.confidence, "confidence")
        )

        # Reasons
        if not isinstance(self.reasons, tuple):
            raise DomainContractValidationError(
                "reasons must be a tuple", field="reasons"
            )
        deduped_reasons = _deduplicate_reasons(self.reasons)
        object.__setattr__(self, "reasons", deduped_reasons)

        # Candidate scores
        if not isinstance(self.candidate_scores, tuple):
            raise DomainContractValidationError(
                "candidate_scores must be a tuple", field="candidate_scores"
            )
        object.__setattr__(
            self,
            "candidate_scores",
            _validate_candidate_scores_list(self.candidate_scores, "candidate_scores"),
        )

        # Bools
        object.__setattr__(
            self,
            "requires_clarification",
            _validate_strict_bool(
                self.requires_clarification, "requires_clarification"
            ),
        )
        object.__setattr__(
            self,
            "fallback_used",
            _validate_strict_bool(self.fallback_used, "fallback_used"),
        )

        # Recommended question
        object.__setattr__(
            self,
            "recommended_question",
            _normalize_empty_to_none(self.recommended_question),
        )

        # Metadata
        object.__setattr__(
            self, "metadata", _validate_json_safe_metadata(self.metadata, "metadata")
        )
        _reject_credential_keys_deep(self.metadata, "metadata")

        # ── Status-specific invariants ────────────────────────────────────
        self._validate_status_invariants()

    def _validate_status_invariants(self) -> None:
        """Validate invariants based on the resolution status."""
        status = self.status

        if status == DomainResolutionStatus.RESOLVED:
            if self.primary_domain is None:
                raise DomainContractValidationError(
                    "RESOLVED status requires a primary_domain",
                    field="primary_domain",
                )
            primary_slug = self.primary_domain.slug
            rejected_slugs = {d.slug for d in self.rejected_domains}
            ambiguous_slugs = {d.slug for d in self.ambiguous_domains}
            if primary_slug in rejected_slugs:
                raise DomainContractValidationError(
                    "Primary domain cannot be in rejected_domains",
                    field="primary_domain",
                    details={"domain": primary_slug},
                )
            if primary_slug in ambiguous_slugs:
                raise DomainContractValidationError(
                    "Primary domain cannot be in ambiguous_domains",
                    field="primary_domain",
                    details={"domain": primary_slug},
                )
            if self.requires_clarification:
                raise DomainContractValidationError(
                    "RESOLVED status cannot have requires_clarification=True",
                    field="requires_clarification",
                )
            if self.recommended_question is not None:
                raise DomainContractValidationError(
                    "RESOLVED status cannot have a recommended_question",
                    field="recommended_question",
                )

        elif status == DomainResolutionStatus.AMBIGUOUS:
            if len(self.ambiguous_domains) < 2:
                raise DomainContractValidationError(
                    "AMBIGUOUS status requires at least 2 ambiguous_domains",
                    field="ambiguous_domains",
                    details={"count": len(self.ambiguous_domains)},
                )
            if not self.requires_clarification:
                raise DomainContractValidationError(
                    "AMBIGUOUS status requires requires_clarification=True",
                    field="requires_clarification",
                )
            if self.recommended_question is None:
                raise DomainContractValidationError(
                    "AMBIGUOUS status requires a recommended_question",
                    field="recommended_question",
                )

        elif status == DomainResolutionStatus.INSUFFICIENT_INFORMATION:
            if (
                self.primary_domain is not None
                and not self.fallback_used
                and not self.requires_clarification
            ):
                raise DomainContractValidationError(
                    "INSUFFICIENT_INFORMATION with a non-fallback primary "
                    "requires requires_clarification=True",
                    field="requires_clarification",
                )

        elif status == DomainResolutionStatus.UNSUPPORTED:
            if self.primary_domain is not None:
                raise DomainContractValidationError(
                    "UNSUPPORTED status cannot have a primary_domain",
                    field="primary_domain",
                )
            if self.confidence != 0.0:
                raise DomainContractValidationError(
                    "UNSUPPORTED status must have confidence 0.0",
                    field="confidence",
                )
            # At least one candidate must exist
            # (unvalidated here; the resolver is responsible)

        elif status == DomainResolutionStatus.BLOCKED:
            if self.primary_domain is not None:
                raise DomainContractValidationError(
                    "BLOCKED status cannot have a primary_domain",
                    field="primary_domain",
                )
            if len(self.rejected_domains) == 0:
                raise DomainContractValidationError(
                    "BLOCKED status requires at least one rejected domain",
                    field="rejected_domains",
                )
            blocking_reasons = [r for r in self.reasons if r.blocking]
            if len(blocking_reasons) == 0:
                raise DomainContractValidationError(
                    "BLOCKED status requires at least one blocking reason",
                    field="reasons",
                )

        elif status == DomainResolutionStatus.FAILED:
            # No additional invariants beyond structural validity
            pass

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "id": self.id,
            "context_id": self.context_id,
            "status": self.status.value,
            "primary_domain": str(self.primary_domain) if self.primary_domain else None,
            "supporting_domains": [str(d) for d in self.supporting_domains],
            "rejected_domains": [str(d) for d in self.rejected_domains],
            "ambiguous_domains": [str(d) for d in self.ambiguous_domains],
            "confidence": self.confidence,
            "reasons": [r.to_dict() for r in self.reasons],
            "candidate_scores": [s.to_dict() for s in self.candidate_scores],
            "requires_clarification": self.requires_clarification,
            "recommended_question": self.recommended_question,
            "fallback_used": self.fallback_used,
            "resolved_at": self.resolved_at.isoformat(),
            "metadata": _deep_unfreeze_value(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DomainResolutionResult:
        """Deserialize from dictionary."""
        if not isinstance(data, Mapping):
            raise DomainResolutionSerializationError(
                "DomainResolutionResult.from_dict requires a mapping", field="data"
            )
        _reject_unknown_fields(data, _RESULT_KNOWN, "DomainResolutionResult")
        required = {"id", "context_id", "status", "resolved_at"}
        missing = required - set(data.keys())
        if missing:
            raise DomainResolutionSerializationError(
                f"DomainResolutionResult.from_dict missing required fields: {sorted(missing)}",
                field="data",
            )

        # Parse status
        status_raw = data["status"]
        if isinstance(status_raw, DomainResolutionStatus):
            status = status_raw
        elif isinstance(status_raw, str):
            try:
                status = DomainResolutionStatus(status_raw)
            except ValueError as exc:
                raise DomainResolutionSerializationError(
                    f"Invalid DomainResolutionStatus: {status_raw!r}",
                    field="status",
                ) from exc
        else:
            raise DomainResolutionSerializationError(
                f"status must be a string or DomainResolutionStatus, got {type(status_raw).__name__}",
                field="status",
            )

        # Parse primary_domain
        primary_raw = data.get("primary_domain")
        primary_domain: DomainId | None = None
        if primary_raw is not None:
            if isinstance(primary_raw, DomainId):
                primary_domain = primary_raw
            elif isinstance(primary_raw, str):
                primary_domain = _coerce_domain_id(primary_raw, "primary_domain")
            else:
                raise DomainResolutionSerializationError(
                    f"primary_domain must be string or DomainId, got {type(primary_raw).__name__}",
                    field="primary_domain",
                )

        # Parse reasons
        reasons_raw = data.get("reasons", ())
        reasons = _parse_reasons_from_dict(reasons_raw, "reasons")

        # Parse candidate_scores
        scores_raw = data.get("candidate_scores", ())
        candidate_scores = _parse_candidate_scores_from_dict(
            scores_raw, "candidate_scores"
        )

        # Parse resolved_at
        resolved_at = _parse_datetime_opt(data["resolved_at"], "resolved_at")
        if resolved_at is None:
            raise DomainResolutionSerializationError(
                "resolved_at is required", field="resolved_at"
            )

        return cls(
            id=str(data["id"]),
            context_id=str(data["context_id"]),
            status=status,
            primary_domain=primary_domain,
            supporting_domains=_freeze_domain_ids_from_dict(
                data.get("supporting_domains", ()), "supporting_domains"
            ),
            rejected_domains=_freeze_domain_ids_from_dict(
                data.get("rejected_domains", ()), "rejected_domains"
            ),
            ambiguous_domains=_freeze_domain_ids_from_dict(
                data.get("ambiguous_domains", ()), "ambiguous_domains"
            ),
            confidence=data.get("confidence", 0.0),
            reasons=reasons,
            candidate_scores=candidate_scores,
            requires_clarification=bool(data.get("requires_clarification", False)),
            recommended_question=data.get("recommended_question"),
            fallback_used=bool(data.get("fallback_used", False)),
            resolved_at=resolved_at,
            metadata=data.get("metadata"),
        )


# ── Helper: deduplicate reasons ─────────────────────────────────────────────


def _deduplicate_reasons(
    reasons: tuple[DomainResolutionReason, ...],
) -> tuple[DomainResolutionReason, ...]:
    """Deduplicate reasons deterministically by (code, domain_id, signal_kind)."""
    seen: set[tuple[str, str, str]] = set()
    result: list[DomainResolutionReason] = []
    for r in reasons:
        key = (r.code, str(r.domain_id) if r.domain_id else "", r.signal_kind or "")
        if key not in seen:
            seen.add(key)
            result.append(r)
    return tuple(result)


def _validate_candidate_scores_list(
    seq: tuple[DomainCandidateScore, ...], field_name: str
) -> tuple[DomainCandidateScore, ...]:
    """Validate a tuple of DomainCandidateScore — no duplicate domain_ids."""
    if not isinstance(seq, tuple):
        raise DomainContractValidationError(
            f"{field_name} must be a tuple", field=field_name
        )
    seen: set[str] = set()
    for i, item in enumerate(seq):
        if not isinstance(item, DomainCandidateScore):
            raise DomainContractValidationError(
                f"Each item in {field_name} must be a DomainCandidateScore, "
                f"got {type(item).__name__} at index {i}",
                field=f"{field_name}[{i}]",
            )
        slug = item.domain_id.slug
        if slug in seen:
            raise DomainContractValidationError(
                f"Duplicate domain_id in {field_name}: {slug}",
                field=field_name,
                details={"duplicate": slug, "index": i},
            )
        seen.add(slug)
    return seq


def _parse_reasons_from_dict(
    raw: Any, field_name: str
) -> tuple[DomainResolutionReason, ...]:
    """Parse a list of reasons from dict representation."""
    if raw is None:
        return ()
    if not isinstance(raw, (list, tuple)):
        raise DomainResolutionSerializationError(
            f"{field_name} must be a list", field=field_name
        )
    result: list[DomainResolutionReason] = []
    for i, item in enumerate(raw):
        if isinstance(item, DomainResolutionReason):
            result.append(item)
        elif isinstance(item, Mapping):
            try:
                result.append(DomainResolutionReason.from_dict(dict(item)))
            except (
                DomainContractValidationError,
                DomainResolutionSerializationError,
                ValueError,
                TypeError,
            ) as exc:
                raise DomainResolutionSerializationError(
                    f"Invalid reason at {field_name}[{i}]",
                    field=f"{field_name}[{i}]",
                ) from exc
        else:
            raise DomainResolutionSerializationError(
                f"Each item in {field_name} must be a mapping, got {type(item).__name__}",
                field=f"{field_name}[{i}]",
            )
    return tuple(result)


def _parse_candidate_scores_from_dict(
    raw: Any, field_name: str
) -> tuple[DomainCandidateScore, ...]:
    """Parse a list of candidate scores from dict representation."""
    if raw is None:
        return ()
    if not isinstance(raw, (list, tuple)):
        raise DomainResolutionSerializationError(
            f"{field_name} must be a list", field=field_name
        )
    result: list[DomainCandidateScore] = []
    for i, item in enumerate(raw):
        if isinstance(item, DomainCandidateScore):
            result.append(item)
        elif isinstance(item, Mapping):
            try:
                result.append(DomainCandidateScore.from_dict(dict(item)))
            except (
                DomainContractValidationError,
                DomainResolutionSerializationError,
                ValueError,
                TypeError,
            ) as exc:
                raise DomainResolutionSerializationError(
                    f"Invalid candidate_score at {field_name}[{i}]",
                    field=f"{field_name}[{i}]",
                ) from exc
        else:
            raise DomainResolutionSerializationError(
                f"Each item in {field_name} must be a mapping, got {type(item).__name__}",
                field=f"{field_name}[{i}]",
            )
    return tuple(result)


# ── Public API ─────────────────────────────────────────────────────────────────

__all__ = [
    "DomainCandidateScore",
    "DomainResolutionReason",
    "DomainResolutionResult",
    "DomainScoringPolicy",
]
