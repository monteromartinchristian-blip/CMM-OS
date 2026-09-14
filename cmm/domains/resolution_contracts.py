"""Phase 10.6 – Domain Resolution Contracts.

Immutable, JSON-serializable, type-safe contracts for the Domain
Resolution Context subsystem.  All dataclasses are ``frozen=True`` and
never expose mutable internal state.

No resolver logic, no live registry access, no LLM calls.
"""

from __future__ import annotations

import math
import re as _re
from collections.abc import Mapping, Sequence
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
from cmm.domains.contracts import (
    _wrap_nested_error as _global_wrap_nested_error,
)
from cmm.domains.errors import (
    DomainContractValidationError,
    DomainError,
    DomainResolutionContextInvalid,
    DomainResolutionContractError,
    DomainResolutionPolicyError,
    DomainResolutionSerializationError,
    DomainSerializationError,
)
from cmm.domains.identifiers import DomainId

# ── JSON-safe type alias (shared) ─────────────────────────────────────────────

JSONValue = (
    str | int | float | bool | None | Mapping[str, "JSONValue"] | list["JSONValue"]
)


# ── JSON-safe validation helpers ──────────────────────────────────────────────


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


# ── Resolution-specific error wrapping helper ─────────────────────────────────


def _wrap_resolution_nested_error(
    exc: Exception, parent_field: str, index: int | None = None
) -> None:
    """Wrap a nested error preserving original code, message, field, and details.

    Translates generic ``DomainContractValidationError`` and
    ``DomainSerializationError`` into their resolution-specific
    equivalents so the public boundary never exposes base-domain errors.
    """
    if isinstance(exc, DomainError):
        inner_field = exc.field or ""
        full_path = (
            f"{parent_field}[{index}].{inner_field}"
            if index is not None and inner_field
            else f"{parent_field}[{index}]"
            if index is not None
            else f"{parent_field}.{inner_field}"
            if inner_field
            else parent_field
        )
        original_details = dict(exc.details) if exc.details else {}
        original_details["_original_code"] = exc.code
        if isinstance(exc, DomainContractValidationError):
            raise DomainResolutionContractError(
                exc.message, field=full_path, details=original_details
            ) from exc
        if isinstance(exc, DomainSerializationError):
            raise DomainResolutionSerializationError(
                exc.message, field=full_path, details=original_details
            ) from exc
        # Already resolution errors — re-raise with enriched path
        if isinstance(exc, DomainResolutionContractError):
            raise DomainResolutionContractError(
                exc.message, field=full_path, details=original_details
            ) from exc
        if isinstance(exc, DomainResolutionSerializationError):
            raise DomainResolutionSerializationError(
                exc.message, field=full_path, details=original_details
            ) from exc
        raise DomainResolutionContractError(
            exc.message, field=full_path, details=original_details
        ) from exc
    # Non-DomainError: wrap generically as resolution contract error
    raise DomainResolutionContractError(
        f"Invalid nested value in {parent_field}: {exc}",
        field=parent_field,
        details={"error": str(exc)},
    ) from exc


# ── Confidence helpers ────────────────────────────────────────────────────────


def _validate_confidence_opt(val: Any, field_name: str) -> float | None:
    """Validate optional confidence: None or finite float in [0, 1]."""
    if val is None:
        return None
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
    if not (0.0 <= val <= 1.0):
        raise DomainContractValidationError(
            f"{field_name} must be between 0.0 and 1.0, got {val!r}", field=field_name
        )
    return val


def _validate_weight_opt(val: Any, field_name: str) -> float | None:
    """Validate optional weight: None or finite non-negative float."""
    if val is None:
        return None
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
    if val < 0.0:
        raise DomainContractValidationError(
            f"{field_name} must be non-negative, got {val!r}", field=field_name
        )
    return val


# ── Domain ID tuple helpers ───────────────────────────────────────────────────


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


def _coerce_domain_id(val: Any, field_name: str) -> DomainId:
    """Coerce a string or DomainId to a DomainId."""
    if isinstance(val, DomainId):
        return val
    if isinstance(val, str):
        try:
            return DomainId.from_str(val)
        except DomainContractValidationError as exc:
            raise DomainContractValidationError(
                f"Invalid DomainId in {field_name}: {exc.message}",
                field=field_name,
            ) from exc
    raise DomainContractValidationError(
        f"{field_name} must be a DomainId or canonical string, got {type(val).__name__}",
        field=field_name,
    )


# ── String tuple helpers ──────────────────────────────────────────────────────


def _freeze_str_tuple_unique(
    seq: Any, field_name: str, *, allow_empty: bool = True
) -> tuple[str, ...]:
    """Validate and convert sequence to tuple of unique, non-empty strings."""
    if seq is None:
        if allow_empty:
            return ()
        raise DomainContractValidationError(
            f"{field_name} cannot be None", field=field_name
        )
    if isinstance(seq, (str, bytes)):
        raise DomainContractValidationError(
            f"{field_name} must be a sequence of strings, not a string",
            field=field_name,
        )
    if not isinstance(seq, (tuple, list, set, Sequence)):
        raise DomainContractValidationError(
            f"{field_name} must be a tuple, list, or sequence of strings",
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


# ── BCP-47 language tag validation ────────────────────────────────────────────

_BCP47_SIMPLE_RE = _re.compile(r"^(?P<primary>[a-z]{2,3})(?:-(?P<region>[A-Z]{2}))?$")


def _validate_language_tag(val: Any, field_name: str) -> str:
    """Validate a simplified BCP-47 language tag."""
    if val is None:
        return "und"
    if not isinstance(val, str) or not val.strip():
        return "und"
    tag = val.strip()
    m = _BCP47_SIMPLE_RE.match(tag)
    if not m:
        raise DomainContractValidationError(
            f"{field_name}: invalid BCP-47 language tag: {tag!r}",
            field=field_name,
            details={"value": tag},
        )
    return tag


def _validate_language_tag_optional(val: Any, field_name: str) -> str:
    """Validate BCP-47 language tag, defaulting to 'und'."""
    if val is None:
        return "und"
    if not isinstance(val, str):
        raise DomainContractValidationError(
            f"{field_name} must be a string, got {type(val).__name__}", field=field_name
        )
    return _validate_language_tag(val, field_name)


# ── Text length validation ────────────────────────────────────────────────────

_MAX_INPUT_STR_CHARS = 200_000


def _validate_text_opt(val: Any, field_name: str) -> str | None:
    """Validate optional text field: non-empty string → cleaned, empty/None → None."""
    if val is None:
        return None
    if not isinstance(val, str):
        raise DomainContractValidationError(
            f"{field_name} must be a string, got {type(val).__name__}", field=field_name
        )
    cleaned = val.strip()
    if not cleaned:
        return None
    if len(cleaned) > _MAX_INPUT_STR_CHARS:
        raise DomainContractValidationError(
            f"{field_name} exceeds maximum length of {_MAX_INPUT_STR_CHARS} characters",
            field=field_name,
            details={"length": len(cleaned), "max": _MAX_INPUT_STR_CHARS},
        )
    return cleaned


# ── Resolution-specific datetime parse (rejects naive) ────────────────────────


def _parse_datetime_opt_resolution(val: Any, field_name: str) -> datetime | None:
    """Parse string or datetime to timezone-aware datetime or None.

    Unlike the generic ``_parse_datetime_opt``, this helper **rejects** naive
    datetimes from ISO strings instead of silently assuming UTC.
    """
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


# ═══════════════════════════════════════════════════════════════════════════════
# Phase 10.6 Contracts
# ═══════════════════════════════════════════════════════════════════════════════

# ── DomainResolutionSignal ────────────────────────────────────────────────────

_SIGNAL_KNOWN = frozenset(
    {
        "kind",
        "source",
        "value",
        "domain_ids",
        "confidence",
        "weight",
        "observed_at",
        "provenance",
        "metadata",
    }
)


@dataclass(frozen=True, slots=True)
class DomainResolutionSignal:
    """Generic contract to preserve resolution evidence without deciding yet.

    Each signal carries a ``kind`` (e.g. ``"entity"``, ``"intent"``),
    a ``source``, and a JSON-safe ``value`` together with optional
    confidence / weight and domain hints.
    """

    kind: str
    source: str
    value: JSONValue
    domain_ids: tuple[DomainId, ...] = ()
    confidence: float | None = None
    weight: float | None = None
    observed_at: datetime | None = None
    provenance: MappingProxyType[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )
    metadata: MappingProxyType[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )

    def __post_init__(self) -> None:
        object.__setattr__(self, "kind", _validate_non_empty_str(self.kind, "kind"))
        object.__setattr__(
            self, "source", _validate_non_empty_str(self.source, "source")
        )
        object.__setattr__(
            self, "domain_ids", _freeze_domain_ids(self.domain_ids, "domain_ids")
        )
        object.__setattr__(
            self,
            "confidence",
            _validate_confidence_opt(self.confidence, "confidence"),
        )
        object.__setattr__(self, "weight", _validate_weight_opt(self.weight, "weight"))
        if self.observed_at is not None:
            object.__setattr__(
                self, "observed_at", _ensure_tz_aware(self.observed_at, "observed_at")
            )
        # Provenance: must be present when confidence is set (auto-analysis)
        if self.confidence is not None and (
            self.provenance is None
            or (isinstance(self.provenance, Mapping) and len(self.provenance) == 0)
        ):
            raise DomainContractValidationError(
                "provenance is required when confidence is set (auto-analysis signal)",
                field="provenance",
            )
        object.__setattr__(
            self,
            "provenance",
            _validate_json_safe_metadata(self.provenance, "provenance"),
        )
        _reject_credential_keys_deep(self.provenance, "provenance")
        object.__setattr__(
            self, "metadata", _validate_json_safe_metadata(self.metadata, "metadata")
        )
        _reject_credential_keys_deep(self.metadata, "metadata")
        # Validate JSON-safe value
        _validate_json_safe(
            _deep_unfreeze(self.value)
            if isinstance(self.value, MappingProxyType)
            else self.value,
            "value",
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "kind": self.kind,
            "source": self.source,
            "value": _deep_unfreeze_value(self.value),
            "domain_ids": [str(d) for d in self.domain_ids],
            "confidence": self.confidence,
            "weight": self.weight,
            "observed_at": self.observed_at.isoformat() if self.observed_at else None,
            "provenance": _deep_unfreeze(self.provenance),
            "metadata": _deep_unfreeze(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DomainResolutionSignal:
        """Deserialize from dictionary."""
        if not isinstance(data, Mapping):
            raise DomainResolutionSerializationError(
                "DomainResolutionSignal.from_dict requires a mapping", field="data"
            )
        _reject_unknown_fields(data, _SIGNAL_KNOWN, "DomainResolutionSignal")
        required = {"kind", "source", "value"}
        missing = required - set(data.keys())
        if missing:
            raise DomainResolutionSerializationError(
                f"DomainResolutionSignal.from_dict missing required fields: {sorted(missing)}",
                field="data",
            )
        return cls(
            kind=str(data["kind"]),
            source=str(data["source"]),
            value=data["value"],
            domain_ids=_freeze_domain_ids_from_dict(
                data.get("domain_ids", ()), "domain_ids"
            ),
            confidence=data.get("confidence"),
            weight=data.get("weight"),
            observed_at=_parse_datetime_opt_resolution(
                data.get("observed_at"), "observed_at"
            ),
            provenance=data.get("provenance"),
            metadata=data.get("metadata"),
        )


def _deep_unfreeze_value(value: Any) -> Any:
    """Unfreeze a single value for serialization."""
    if isinstance(value, MappingProxyType):
        return {k: _deep_unfreeze_value(v) for k, v in value.items()}
    if isinstance(value, tuple):
        return [_deep_unfreeze_value(v) for v in value]
    if isinstance(value, frozenset):
        return sorted([_deep_unfreeze_value(v) for v in value], key=str)
    return value


# ── DomainResolutionResource ──────────────────────────────────────────────────

_RESOURCE_KNOWN = frozenset(
    {
        "id",
        "resource_type",
        "source",
        "domain_ids",
        "sensitivity",
        "temporal_reference",
        "metadata",
    }
)


@dataclass(frozen=True, slots=True)
class DomainResolutionResource:
    """Lightweight reference to a resource relevant to domain resolution."""

    id: str
    resource_type: str
    source: str
    domain_ids: tuple[DomainId, ...] = ()
    sensitivity: str | None = None
    temporal_reference: datetime | None = None
    metadata: MappingProxyType[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", _validate_non_empty_str(self.id, "id"))
        object.__setattr__(
            self,
            "resource_type",
            _validate_non_empty_str(self.resource_type, "resource_type"),
        )
        object.__setattr__(
            self, "source", _validate_non_empty_str(self.source, "source")
        )
        object.__setattr__(
            self, "domain_ids", _freeze_domain_ids(self.domain_ids, "domain_ids")
        )
        object.__setattr__(
            self, "sensitivity", _normalize_empty_to_none(self.sensitivity)
        )
        if self.temporal_reference is not None:
            object.__setattr__(
                self,
                "temporal_reference",
                _ensure_tz_aware(self.temporal_reference, "temporal_reference"),
            )
        object.__setattr__(
            self, "metadata", _validate_json_safe_metadata(self.metadata, "metadata")
        )
        _reject_credential_keys_deep(self.metadata, "metadata")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "resource_type": self.resource_type,
            "source": self.source,
            "domain_ids": [str(d) for d in self.domain_ids],
            "sensitivity": self.sensitivity,
            "temporal_reference": (
                self.temporal_reference.isoformat() if self.temporal_reference else None
            ),
            "metadata": _deep_unfreeze(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DomainResolutionResource:
        if not isinstance(data, Mapping):
            raise DomainResolutionSerializationError(
                "DomainResolutionResource.from_dict requires a mapping", field="data"
            )
        _reject_unknown_fields(data, _RESOURCE_KNOWN, "DomainResolutionResource")
        required = {"id", "resource_type", "source"}
        missing = required - set(data.keys())
        if missing:
            raise DomainResolutionSerializationError(
                f"DomainResolutionResource.from_dict missing required fields: {sorted(missing)}",
                field="data",
            )
        return cls(
            id=str(data["id"]),
            resource_type=str(data["resource_type"]),
            source=str(data["source"]),
            domain_ids=_freeze_domain_ids_from_dict(
                data.get("domain_ids", ()), "domain_ids"
            ),
            sensitivity=data.get("sensitivity"),
            temporal_reference=_parse_datetime_opt_resolution(
                data.get("temporal_reference"), "temporal_reference"
            ),
            metadata=data.get("metadata"),
        )


# ── DomainResolutionEntity ──────────────────────────────────────────────────

_ENTITY_KNOWN = frozenset(
    {
        "id",
        "entity_type",
        "source",
        "labels",
        "domain_ids",
        "confidence",
        "metadata",
    }
)


@dataclass(frozen=True, slots=True)
class DomainResolutionEntity:
    """Lightweight reference to an entity detected during resolution."""

    id: str
    entity_type: str
    source: str
    labels: tuple[str, ...] = ()
    domain_ids: tuple[DomainId, ...] = ()
    confidence: float | None = None
    metadata: MappingProxyType[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", _validate_non_empty_str(self.id, "id"))
        object.__setattr__(
            self,
            "entity_type",
            _validate_non_empty_str(self.entity_type, "entity_type"),
        )
        object.__setattr__(
            self, "source", _validate_non_empty_str(self.source, "source")
        )
        object.__setattr__(
            self, "labels", _freeze_str_tuple_unique(self.labels, "labels")
        )
        object.__setattr__(
            self, "domain_ids", _freeze_domain_ids(self.domain_ids, "domain_ids")
        )
        object.__setattr__(
            self,
            "confidence",
            _validate_confidence_opt(self.confidence, "confidence"),
        )
        object.__setattr__(
            self, "metadata", _validate_json_safe_metadata(self.metadata, "metadata")
        )
        _reject_credential_keys_deep(self.metadata, "metadata")
        # provenance requirement: if confidence is set, metadata should contain source provenance
        if self.confidence is not None and (
            not self.metadata.get("source") and not self.metadata.get("provenance")
        ):
            raise DomainContractValidationError(
                "metadata.source or metadata.provenance is required when confidence is set (auto-detected entity)",
                field="metadata",
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "entity_type": self.entity_type,
            "source": self.source,
            "labels": list(self.labels),
            "domain_ids": [str(d) for d in self.domain_ids],
            "confidence": self.confidence,
            "metadata": _deep_unfreeze(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DomainResolutionEntity:
        if not isinstance(data, Mapping):
            raise DomainResolutionSerializationError(
                "DomainResolutionEntity.from_dict requires a mapping", field="data"
            )
        _reject_unknown_fields(data, _ENTITY_KNOWN, "DomainResolutionEntity")
        required = {"id", "entity_type", "source"}
        missing = required - set(data.keys())
        if missing:
            raise DomainResolutionSerializationError(
                f"DomainResolutionEntity.from_dict missing required fields: {sorted(missing)}",
                field="data",
            )
        return cls(
            id=str(data["id"]),
            entity_type=str(data["entity_type"]),
            source=str(data["source"]),
            labels=tuple(data.get("labels", ())),
            domain_ids=_freeze_domain_ids_from_dict(
                data.get("domain_ids", ()), "domain_ids"
            ),
            confidence=data.get("confidence"),
            metadata=data.get("metadata"),
        )


# ── DomainResolutionKnowledgeItem ───────────────────────────────────────────

_KNOWLEDGE_KNOWN = frozenset(
    {
        "id",
        "knowledge_type",
        "source",
        "domain_ids",
        "relevance",
        "valid_at",
        "provenance",
        "metadata",
    }
)


@dataclass(frozen=True, slots=True)
class DomainResolutionKnowledgeItem:
    """Lightweight reference to a knowledge item relevant to domain resolution."""

    id: str
    knowledge_type: str
    source: str
    domain_ids: tuple[DomainId, ...] = ()
    relevance: float | None = None
    valid_at: datetime | None = None
    provenance: MappingProxyType[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )
    metadata: MappingProxyType[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", _validate_non_empty_str(self.id, "id"))
        object.__setattr__(
            self,
            "knowledge_type",
            _validate_non_empty_str(self.knowledge_type, "knowledge_type"),
        )
        object.__setattr__(
            self, "source", _validate_non_empty_str(self.source, "source")
        )
        object.__setattr__(
            self, "domain_ids", _freeze_domain_ids(self.domain_ids, "domain_ids")
        )
        object.__setattr__(
            self, "relevance", _validate_confidence_opt(self.relevance, "relevance")
        )
        if self.valid_at is not None:
            object.__setattr__(
                self, "valid_at", _ensure_tz_aware(self.valid_at, "valid_at")
            )
        object.__setattr__(
            self,
            "provenance",
            _validate_json_safe_metadata(self.provenance, "provenance"),
        )
        _reject_credential_keys_deep(self.provenance, "provenance")
        object.__setattr__(
            self, "metadata", _validate_json_safe_metadata(self.metadata, "metadata")
        )
        _reject_credential_keys_deep(self.metadata, "metadata")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "knowledge_type": self.knowledge_type,
            "source": self.source,
            "domain_ids": [str(d) for d in self.domain_ids],
            "relevance": self.relevance,
            "valid_at": self.valid_at.isoformat() if self.valid_at else None,
            "provenance": _deep_unfreeze(self.provenance),
            "metadata": _deep_unfreeze(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DomainResolutionKnowledgeItem:
        if not isinstance(data, Mapping):
            raise DomainResolutionSerializationError(
                "DomainResolutionKnowledgeItem.from_dict requires a mapping",
                field="data",
            )
        _reject_unknown_fields(data, _KNOWLEDGE_KNOWN, "DomainResolutionKnowledgeItem")
        required = {"id", "knowledge_type", "source"}
        missing = required - set(data.keys())
        if missing:
            raise DomainResolutionSerializationError(
                f"DomainResolutionKnowledgeItem.from_dict missing required fields: {sorted(missing)}",
                field="data",
            )
        return cls(
            id=str(data["id"]),
            knowledge_type=str(data["knowledge_type"]),
            source=str(data["source"]),
            domain_ids=_freeze_domain_ids_from_dict(
                data.get("domain_ids", ()), "domain_ids"
            ),
            relevance=data.get("relevance"),
            valid_at=_parse_datetime_opt_resolution(data.get("valid_at"), "valid_at"),
            provenance=data.get("provenance"),
            metadata=data.get("metadata"),
        )


# ── DomainResolutionHistoryItem ──────────────────────────────────────────────

_HISTORY_KNOWN = frozenset(
    {
        "id",
        "item_type",
        "timestamp",
        "domain_ids",
        "summary",
        "metadata",
    }
)


@dataclass(frozen=True, slots=True)
class DomainResolutionHistoryItem:
    """Lightweight reference to a historical interaction relevant to resolution."""

    id: str
    item_type: str
    timestamp: datetime
    domain_ids: tuple[DomainId, ...] = ()
    summary: str | None = None
    metadata: MappingProxyType[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", _validate_non_empty_str(self.id, "id"))
        object.__setattr__(
            self, "item_type", _validate_non_empty_str(self.item_type, "item_type")
        )
        object.__setattr__(
            self, "timestamp", _ensure_tz_aware(self.timestamp, "timestamp")
        )
        object.__setattr__(
            self, "domain_ids", _freeze_domain_ids(self.domain_ids, "domain_ids")
        )
        object.__setattr__(self, "summary", _normalize_empty_to_none(self.summary))
        object.__setattr__(
            self, "metadata", _validate_json_safe_metadata(self.metadata, "metadata")
        )
        _reject_credential_keys_deep(self.metadata, "metadata")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "item_type": self.item_type,
            "timestamp": self.timestamp.isoformat(),
            "domain_ids": [str(d) for d in self.domain_ids],
            "summary": self.summary,
            "metadata": _deep_unfreeze(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DomainResolutionHistoryItem:
        if not isinstance(data, Mapping):
            raise DomainResolutionSerializationError(
                "DomainResolutionHistoryItem.from_dict requires a mapping",
                field="data",
            )
        _reject_unknown_fields(data, _HISTORY_KNOWN, "DomainResolutionHistoryItem")
        required = {"id", "item_type", "timestamp"}
        missing = required - set(data.keys())
        if missing:
            raise DomainResolutionSerializationError(
                f"DomainResolutionHistoryItem.from_dict missing required fields: {sorted(missing)}",
                field="data",
            )
        timestamp_raw = data["timestamp"]
        if isinstance(timestamp_raw, datetime):
            timestamp = timestamp_raw
        elif isinstance(timestamp_raw, str):
            try:
                timestamp = datetime.fromisoformat(timestamp_raw)
            except ValueError as exc:
                raise DomainResolutionSerializationError(
                    f"Invalid isoformat datetime string for timestamp: {timestamp_raw!r}",
                    field="timestamp",
                ) from exc
            if timestamp.tzinfo is None:
                raise DomainResolutionSerializationError(
                    "timestamp must be timezone-aware",
                    field="timestamp",
                )
        else:
            raise DomainResolutionSerializationError(
                f"timestamp must be ISO string or datetime, got {type(timestamp_raw).__name__}",
                field="timestamp",
            )
        return cls(
            id=str(data["id"]),
            item_type=str(data["item_type"]),
            timestamp=timestamp,
            domain_ids=_freeze_domain_ids_from_dict(
                data.get("domain_ids", ()), "domain_ids"
            ),
            summary=data.get("summary"),
            metadata=data.get("metadata"),
        )


# ── DomainResolutionEvent ────────────────────────────────────────────────────

_EVENT_KNOWN = frozenset(
    {
        "id",
        "event_type",
        "source",
        "timestamp",
        "actor",
        "domain_ids",
        "payload",
        "metadata",
    }
)


@dataclass(frozen=True, slots=True)
class DomainResolutionEvent:
    """Lightweight reference to a kernel event relevant to domain resolution."""

    id: str
    event_type: str
    source: str
    timestamp: datetime
    actor: str | None = None
    domain_ids: tuple[DomainId, ...] = ()
    payload: MappingProxyType[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )
    metadata: MappingProxyType[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", _validate_non_empty_str(self.id, "id"))
        object.__setattr__(
            self, "event_type", _validate_non_empty_str(self.event_type, "event_type")
        )
        object.__setattr__(
            self, "source", _validate_non_empty_str(self.source, "source")
        )
        object.__setattr__(
            self, "timestamp", _ensure_tz_aware(self.timestamp, "timestamp")
        )
        object.__setattr__(self, "actor", _normalize_empty_to_none(self.actor))
        object.__setattr__(
            self, "domain_ids", _freeze_domain_ids(self.domain_ids, "domain_ids")
        )
        object.__setattr__(
            self, "payload", _validate_json_safe_metadata(self.payload, "payload")
        )
        _reject_credential_keys_deep(self.payload, "payload")
        object.__setattr__(
            self, "metadata", _validate_json_safe_metadata(self.metadata, "metadata")
        )
        _reject_credential_keys_deep(self.metadata, "metadata")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "event_type": self.event_type,
            "source": self.source,
            "timestamp": self.timestamp.isoformat(),
            "actor": self.actor,
            "domain_ids": [str(d) for d in self.domain_ids],
            "payload": _deep_unfreeze(self.payload),
            "metadata": _deep_unfreeze(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DomainResolutionEvent:
        if not isinstance(data, Mapping):
            raise DomainResolutionSerializationError(
                "DomainResolutionEvent.from_dict requires a mapping", field="data"
            )
        _reject_unknown_fields(data, _EVENT_KNOWN, "DomainResolutionEvent")
        required = {"id", "event_type", "source", "timestamp"}
        missing = required - set(data.keys())
        if missing:
            raise DomainResolutionSerializationError(
                f"DomainResolutionEvent.from_dict missing required fields: {sorted(missing)}",
                field="data",
            )
        timestamp_raw = data["timestamp"]
        if isinstance(timestamp_raw, datetime):
            timestamp = timestamp_raw
        elif isinstance(timestamp_raw, str):
            try:
                timestamp = datetime.fromisoformat(timestamp_raw)
            except ValueError as exc:
                raise DomainResolutionSerializationError(
                    f"Invalid isoformat datetime string for timestamp: {timestamp_raw!r}",
                    field="timestamp",
                ) from exc
            if timestamp.tzinfo is None:
                raise DomainResolutionSerializationError(
                    "timestamp must be timezone-aware",
                    field="timestamp",
                )
        else:
            raise DomainResolutionSerializationError(
                f"timestamp must be ISO string or datetime, got {type(timestamp_raw).__name__}",
                field="timestamp",
            )
        return cls(
            id=str(data["id"]),
            event_type=str(data["event_type"]),
            source=str(data["source"]),
            timestamp=timestamp,
            actor=data.get("actor"),
            domain_ids=_freeze_domain_ids_from_dict(
                data.get("domain_ids", ()), "domain_ids"
            ),
            payload=data.get("payload"),
            metadata=data.get("metadata"),
        )


# ── DomainResolutionPolicy ───────────────────────────────────────────────────

_POLICY_KNOWN = frozenset(
    {
        "allowed_domains",
        "denied_domains",
        "required_domains",
        "allow_disabled",
        "allow_degraded",
        "allow_external",
        "allow_experimental",
        "require_authorization",
        "high_impact_domains",
        "minimum_confidence",
        "metadata",
    }
)


@dataclass(frozen=True, slots=True)
class DomainResolutionPolicy:
    """Restrictions that Phase 10.7 must respect during resolution."""

    allowed_domains: tuple[DomainId, ...] = ()
    denied_domains: tuple[DomainId, ...] = ()
    required_domains: tuple[DomainId, ...] = ()
    allow_disabled: bool = False
    allow_degraded: bool = True
    allow_external: bool = False
    allow_experimental: bool = False
    require_authorization: bool = True
    high_impact_domains: tuple[DomainId, ...] = ()
    minimum_confidence: float | None = None
    metadata: MappingProxyType[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "allowed_domains",
            _freeze_domain_ids(self.allowed_domains, "allowed_domains"),
        )
        object.__setattr__(
            self,
            "denied_domains",
            _freeze_domain_ids(self.denied_domains, "denied_domains"),
        )
        object.__setattr__(
            self,
            "required_domains",
            _freeze_domain_ids(self.required_domains, "required_domains"),
        )
        object.__setattr__(
            self,
            "high_impact_domains",
            _freeze_domain_ids(self.high_impact_domains, "high_impact_domains"),
        )

        # Strict booleans
        for bool_field in (
            "allow_disabled",
            "allow_degraded",
            "allow_external",
            "allow_experimental",
            "require_authorization",
        ):
            object.__setattr__(
                self,
                bool_field,
                _validate_strict_bool(getattr(self, bool_field), bool_field),
            )

        # Minimum confidence
        object.__setattr__(
            self,
            "minimum_confidence",
            _validate_confidence_opt(self.minimum_confidence, "minimum_confidence"),
        )

        # Metadata
        object.__setattr__(
            self, "metadata", _validate_json_safe_metadata(self.metadata, "metadata")
        )
        _reject_credential_keys_deep(self.metadata, "metadata")

        # ── Invariants ──────────────────────────────────────────────────
        # allowed ∩ denied must be empty
        allowed_slugs = {d.slug for d in self.allowed_domains}
        denied_slugs = {d.slug for d in self.denied_domains}
        overlap = allowed_slugs & denied_slugs
        if overlap:
            raise DomainResolutionPolicyError(
                f"allowed_domains and denied_domains overlap: {sorted(overlap)}",
                field="denied_domains",
                details={"overlap": sorted(overlap)},
            )

        # required cannot be in denied
        required_slugs = {d.slug for d in self.required_domains}
        denied_required = required_slugs & denied_slugs
        if denied_required:
            raise DomainResolutionPolicyError(
                f"required_domains contains denied domains: {sorted(denied_required)}",
                field="required_domains",
                details={"denied_required": sorted(denied_required)},
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed_domains": [str(d) for d in self.allowed_domains],
            "denied_domains": [str(d) for d in self.denied_domains],
            "required_domains": [str(d) for d in self.required_domains],
            "allow_disabled": self.allow_disabled,
            "allow_degraded": self.allow_degraded,
            "allow_external": self.allow_external,
            "allow_experimental": self.allow_experimental,
            "require_authorization": self.require_authorization,
            "high_impact_domains": [str(d) for d in self.high_impact_domains],
            "minimum_confidence": self.minimum_confidence,
            "metadata": _deep_unfreeze(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DomainResolutionPolicy:
        if not isinstance(data, Mapping):
            raise DomainResolutionSerializationError(
                "DomainResolutionPolicy.from_dict requires a mapping", field="data"
            )
        _reject_unknown_fields(data, _POLICY_KNOWN, "DomainResolutionPolicy")
        # Strict bool deserialization
        bool_fields = {
            "allow_disabled": False,
            "allow_degraded": True,
            "allow_external": False,
            "allow_experimental": False,
            "require_authorization": True,
        }
        kwargs: dict[str, Any] = {}
        for bf_name, bf_default in bool_fields.items():
            raw = data.get(bf_name, bf_default)
            if not isinstance(raw, bool):
                raise DomainResolutionSerializationError(
                    f"{bf_name} must be a boolean, got {type(raw).__name__}: {raw!r}",
                    field=bf_name,
                )
            kwargs[bf_name] = raw
        return cls(
            allowed_domains=_freeze_domain_ids_from_dict(
                data.get("allowed_domains", ()), "allowed_domains"
            ),
            denied_domains=_freeze_domain_ids_from_dict(
                data.get("denied_domains", ()), "denied_domains"
            ),
            required_domains=_freeze_domain_ids_from_dict(
                data.get("required_domains", ()), "required_domains"
            ),
            high_impact_domains=_freeze_domain_ids_from_dict(
                data.get("high_impact_domains", ()), "high_impact_domains"
            ),
            minimum_confidence=data.get("minimum_confidence"),
            metadata=data.get("metadata"),
            **kwargs,
        )


# ── DomainResolutionContext ──────────────────────────────────────────────────

_CONTEXT_KNOWN = frozenset(
    {
        "id",
        "objective",
        "user_input",
        "event",
        "goal_id",
        "session_id",
        "workflow_id",
        "explicit_domains",
        "available_domains",
        "authorized_domains",
        "active_domains",
        "resources",
        "entities",
        "knowledge_items",
        "recent_history",
        "kernel_events",
        "signals",
        "current_profile",
        "current_workflow",
        "intent",
        "requested_operations",
        "actor",
        "permissions",
        "temporal_reference",
        "language",
        "user_preferences",
        "system_policy",
        "metadata",
        "created_at",
    }
)


@dataclass(frozen=True, slots=True)
class DomainResolutionContext:
    """Snapshot of all resolution-relevant information for Phase 10.7.

    Immutable, deterministic, JSON-serializable, with no live store access.
    """

    id: str
    objective: str | None = None
    user_input: str | None = None
    event: DomainResolutionEvent | None = None

    goal_id: str | None = None
    session_id: str | None = None
    workflow_id: str | None = None

    explicit_domains: tuple[DomainId, ...] = ()
    available_domains: tuple[DomainId, ...] = ()
    authorized_domains: tuple[DomainId, ...] = ()
    active_domains: tuple[DomainId, ...] = ()

    resources: tuple[DomainResolutionResource, ...] = ()
    entities: tuple[DomainResolutionEntity, ...] = ()
    knowledge_items: tuple[DomainResolutionKnowledgeItem, ...] = ()
    recent_history: tuple[DomainResolutionHistoryItem, ...] = ()
    kernel_events: tuple[DomainResolutionEvent, ...] = ()
    signals: tuple[DomainResolutionSignal, ...] = ()

    current_profile: str | None = None
    current_workflow: str | None = None
    intent: str | None = None
    requested_operations: tuple[str, ...] = ()

    actor: str = "system"
    permissions: tuple[str, ...] = ()
    temporal_reference: datetime | None = None
    language: str = "und"

    user_preferences: MappingProxyType[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )
    system_policy: DomainResolutionPolicy | None = None
    metadata: MappingProxyType[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )

    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", _validate_non_empty_str(self.id, "id"))
        object.__setattr__(
            self, "created_at", _ensure_tz_aware(self.created_at, "created_at")
        )

        # Text fields: clean, normalize empty to None
        object.__setattr__(
            self, "objective", _validate_text_opt(self.objective, "objective")
        )
        object.__setattr__(
            self, "user_input", _validate_text_opt(self.user_input, "user_input")
        )
        object.__setattr__(self, "goal_id", _normalize_empty_to_none(self.goal_id))
        object.__setattr__(
            self, "session_id", _normalize_empty_to_none(self.session_id)
        )
        object.__setattr__(
            self, "workflow_id", _normalize_empty_to_none(self.workflow_id)
        )
        object.__setattr__(
            self, "current_profile", _normalize_empty_to_none(self.current_profile)
        )
        object.__setattr__(
            self, "current_workflow", _normalize_empty_to_none(self.current_workflow)
        )
        object.__setattr__(self, "intent", _normalize_empty_to_none(self.intent))

        # Domain ID lists
        object.__setattr__(
            self,
            "explicit_domains",
            _freeze_domain_ids(self.explicit_domains, "explicit_domains"),
        )
        object.__setattr__(
            self,
            "available_domains",
            _freeze_domain_ids(self.available_domains, "available_domains"),
        )
        object.__setattr__(
            self,
            "authorized_domains",
            _freeze_domain_ids(self.authorized_domains, "authorized_domains"),
        )
        object.__setattr__(
            self,
            "active_domains",
            _freeze_domain_ids(self.active_domains, "active_domains"),
        )

        # Nested collections — element-level coercion & validation
        object.__setattr__(
            self,
            "resources",
            _freeze_resource_tuple(self.resources, "resources"),
        )
        object.__setattr__(
            self,
            "entities",
            _freeze_entity_tuple(self.entities, "entities"),
        )
        object.__setattr__(
            self,
            "knowledge_items",
            _freeze_knowledge_tuple(self.knowledge_items, "knowledge_items"),
        )
        object.__setattr__(
            self,
            "recent_history",
            _freeze_history_tuple(self.recent_history, "recent_history"),
        )
        object.__setattr__(
            self,
            "kernel_events",
            _freeze_event_tuple(self.kernel_events, "kernel_events"),
        )
        object.__setattr__(
            self,
            "signals",
            _freeze_signal_tuple(self.signals, "signals"),
        )

        # Requested operations / permissions
        object.__setattr__(
            self,
            "requested_operations",
            _freeze_str_tuple_unique(self.requested_operations, "requested_operations"),
        )
        object.__setattr__(
            self,
            "permissions",
            _freeze_str_tuple_unique(self.permissions, "permissions"),
        )

        # Actor
        object.__setattr__(self, "actor", _validate_non_empty_str(self.actor, "actor"))

        # Temporal reference
        if self.temporal_reference is not None:
            object.__setattr__(
                self,
                "temporal_reference",
                _ensure_tz_aware(self.temporal_reference, "temporal_reference"),
            )

        # Language
        object.__setattr__(
            self, "language", _validate_language_tag_optional(self.language, "language")
        )

        # User preferences
        object.__setattr__(
            self,
            "user_preferences",
            _validate_json_safe_metadata(self.user_preferences, "user_preferences"),
        )
        _reject_credential_keys_deep(self.user_preferences, "user_preferences")

        # System policy
        if self.system_policy is not None and not isinstance(
            self.system_policy, DomainResolutionPolicy
        ):
            if isinstance(self.system_policy, Mapping):
                try:
                    object.__setattr__(
                        self,
                        "system_policy",
                        DomainResolutionPolicy.from_dict(dict(self.system_policy)),
                    )
                except DomainError as exc:
                    _global_wrap_nested_error(exc, "system_policy")
            else:
                raise DomainResolutionContractError(
                    f"system_policy must be DomainResolutionPolicy or mapping, got {type(self.system_policy).__name__}",
                    field="system_policy",
                )

        # Metadata
        object.__setattr__(
            self, "metadata", _validate_json_safe_metadata(self.metadata, "metadata")
        )
        _reject_credential_keys_deep(self.metadata, "metadata")

        # ── Context invariants ──────────────────────────────────────────

        # At least one resolution source must exist
        has_source = any(
            (
                self.user_input is not None,
                self.objective is not None,
                self.event is not None,
                len(self.explicit_domains) > 0,
                len(self.resources) > 0,
                len(self.entities) > 0,
                len(self.knowledge_items) > 0,
                len(self.requested_operations) > 0,
                len(self.signals) > 0,
            )
        )
        if not has_source:
            raise DomainResolutionContextInvalid(
                "DomainResolutionContext must have at least one resolution source: "
                "user_input, event, objective, explicit_domains, resources, entities, "
                "knowledge_items, requested_operations, or signals",
                field="context",
            )

        # Domain subset invariants
        avail_slugs = {d.slug for d in self.available_domains}

        # explicit ⊆ available (when available not empty)
        if avail_slugs:
            explicit_slugs = {d.slug for d in self.explicit_domains}
            if not explicit_slugs <= avail_slugs:
                stray = sorted(explicit_slugs - avail_slugs)
                raise DomainResolutionContextInvalid(
                    f"explicit_domains contains domains not in available_domains: {stray}",
                    field="explicit_domains",
                    details={"stray": stray},
                )

        # active ⊆ available
        active_slugs = {d.slug for d in self.active_domains}
        if not active_slugs <= avail_slugs:
            stray = sorted(active_slugs - avail_slugs)
            raise DomainResolutionContextInvalid(
                f"active_domains contains domains not in available_domains: {stray}",
                field="active_domains",
                details={"stray": stray},
            )

        # authorized ⊆ available (when authorized declared)
        authorized_slugs = {d.slug for d in self.authorized_domains}
        if authorized_slugs and not authorized_slugs <= avail_slugs:
            stray = sorted(authorized_slugs - avail_slugs)
            raise DomainResolutionContextInvalid(
                f"authorized_domains contains domains not in available_domains: {stray}",
                field="authorized_domains",
                details={"stray": stray},
            )

        # explicit ⊆ authorized (when authorized declared)
        if authorized_slugs:
            explicit_slugs = {d.slug for d in self.explicit_domains}
            if not explicit_slugs <= authorized_slugs:
                stray = sorted(explicit_slugs - authorized_slugs)
                raise DomainResolutionContextInvalid(
                    f"explicit_domains contains domains not in authorized_domains: {stray}",
                    field="explicit_domains",
                    details={"stray": stray},
                )

        # Policy invariants (when policy present)
        if self.system_policy is not None:
            policy = self.system_policy
            # Denied domain cannot appear as authorized
            denied_slugs = {d.slug for d in policy.denied_domains}
            if authorized_slugs:
                denied_auth = authorized_slugs & denied_slugs
                if denied_auth:
                    raise DomainResolutionContextInvalid(
                        f"authorized_domains contains policy-denied domains: {sorted(denied_auth)}",
                        field="authorized_domains",
                        details={"denied": sorted(denied_auth)},
                    )
            # Required domain must be present in available
            required_slugs = {d.slug for d in policy.required_domains}
            if required_slugs:
                missing_required = required_slugs - avail_slugs
                if missing_required:
                    raise DomainResolutionContextInvalid(
                        f"required_domains from policy are missing from available_domains: {sorted(missing_required)}",
                        field="system_policy",
                        details={"missing": sorted(missing_required)},
                    )

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "id": self.id,
            "objective": self.objective,
            "user_input": self.user_input,
            "event": self.event.to_dict() if self.event else None,
            "goal_id": self.goal_id,
            "session_id": self.session_id,
            "workflow_id": self.workflow_id,
            "explicit_domains": [str(d) for d in self.explicit_domains],
            "available_domains": [str(d) for d in self.available_domains],
            "authorized_domains": [str(d) for d in self.authorized_domains],
            "active_domains": [str(d) for d in self.active_domains],
            "resources": [r.to_dict() for r in self.resources],
            "entities": [e.to_dict() for e in self.entities],
            "knowledge_items": [k.to_dict() for k in self.knowledge_items],
            "recent_history": [h.to_dict() for h in self.recent_history],
            "kernel_events": [ev.to_dict() for ev in self.kernel_events],
            "signals": [s.to_dict() for s in self.signals],
            "current_profile": self.current_profile,
            "current_workflow": self.current_workflow,
            "intent": self.intent,
            "requested_operations": list(self.requested_operations),
            "actor": self.actor,
            "permissions": list(self.permissions),
            "temporal_reference": (
                self.temporal_reference.isoformat() if self.temporal_reference else None
            ),
            "language": self.language,
            "user_preferences": _deep_unfreeze(self.user_preferences),
            "system_policy": self.system_policy.to_dict()
            if self.system_policy
            else None,
            "metadata": _deep_unfreeze(self.metadata),
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DomainResolutionContext:
        """Deserialize from dictionary."""
        if not isinstance(data, Mapping):
            raise DomainResolutionSerializationError(
                "DomainResolutionContext.from_dict requires a mapping", field="data"
            )
        _reject_unknown_fields(data, _CONTEXT_KNOWN, "DomainResolutionContext")
        required = {"id", "created_at"}
        missing = required - set(data.keys())
        if missing:
            raise DomainResolutionSerializationError(
                f"DomainResolutionContext.from_dict missing required fields: {sorted(missing)}",
                field="data",
            )

        created_at_raw = data["created_at"]
        if isinstance(created_at_raw, datetime):
            created_at = created_at_raw
        elif isinstance(created_at_raw, str):
            try:
                created_at = datetime.fromisoformat(created_at_raw)
            except ValueError as exc:
                raise DomainResolutionSerializationError(
                    f"Invalid isoformat datetime string for created_at: {created_at_raw!r}",
                    field="created_at",
                ) from exc
            if created_at.tzinfo is None:
                raise DomainResolutionSerializationError(
                    "created_at must be timezone-aware",
                    field="created_at",
                )
        else:
            raise DomainResolutionSerializationError(
                f"created_at must be ISO string or datetime, got {type(created_at_raw).__name__}",
                field="created_at",
            )

        # Parse event if present
        event_raw = data.get("event")
        event: DomainResolutionEvent | None = None
        if event_raw is not None:
            if isinstance(event_raw, DomainResolutionEvent):
                event = event_raw
            elif isinstance(event_raw, Mapping):
                try:
                    event = DomainResolutionEvent.from_dict(dict(event_raw))
                except DomainError as exc:
                    _global_wrap_nested_error(exc, "event")
            else:
                raise DomainResolutionSerializationError(
                    f"event must be a mapping or DomainResolutionEvent, got {type(event_raw).__name__}",
                    field="event",
                )

        # Parse policy if present
        policy_raw = data.get("system_policy")
        system_policy: DomainResolutionPolicy | None = None
        if policy_raw is not None:
            if isinstance(policy_raw, DomainResolutionPolicy):
                system_policy = policy_raw
            elif isinstance(policy_raw, Mapping):
                try:
                    system_policy = DomainResolutionPolicy.from_dict(dict(policy_raw))
                except DomainError as exc:
                    _global_wrap_nested_error(exc, "system_policy")
            else:
                raise DomainResolutionSerializationError(
                    f"system_policy must be a mapping or DomainResolutionPolicy, got {type(policy_raw).__name__}",
                    field="system_policy",
                )

        # Parse user preferences
        user_prefs_raw = data.get("user_preferences", {})
        if isinstance(user_prefs_raw, MappingProxyType):
            user_preferences = user_prefs_raw
        elif isinstance(user_prefs_raw, Mapping):
            user_preferences = _deep_freeze(user_prefs_raw)
        else:
            raise DomainResolutionSerializationError(
                f"user_preferences must be a mapping, got {type(user_prefs_raw).__name__}",
                field="user_preferences",
            )

        return cls(
            id=str(data["id"]),
            objective=data.get("objective"),
            user_input=data.get("user_input"),
            event=event,
            goal_id=data.get("goal_id"),
            session_id=data.get("session_id"),
            workflow_id=data.get("workflow_id"),
            explicit_domains=_freeze_domain_ids_from_dict(
                data.get("explicit_domains", ()), "explicit_domains"
            ),
            available_domains=_freeze_domain_ids_from_dict(
                data.get("available_domains", ()), "available_domains"
            ),
            authorized_domains=_freeze_domain_ids_from_dict(
                data.get("authorized_domains", ()), "authorized_domains"
            ),
            active_domains=_freeze_domain_ids_from_dict(
                data.get("active_domains", ()), "active_domains"
            ),
            resources=_parse_resource_list(data.get("resources"), "resources"),
            entities=_parse_entity_list(data.get("entities"), "entities"),
            knowledge_items=_parse_knowledge_list(
                data.get("knowledge_items"), "knowledge_items"
            ),
            recent_history=_parse_history_list(
                data.get("recent_history"), "recent_history"
            ),
            kernel_events=_parse_event_list(data.get("kernel_events"), "kernel_events"),
            signals=_parse_signal_list(data.get("signals"), "signals"),
            current_profile=data.get("current_profile"),
            current_workflow=data.get("current_workflow"),
            intent=data.get("intent"),
            requested_operations=tuple(data.get("requested_operations", ())),
            actor=str(data.get("actor", "system")),
            permissions=tuple(data.get("permissions", ())),
            temporal_reference=_parse_datetime_opt_resolution(
                data.get("temporal_reference"), "temporal_reference"
            ),
            language=str(data.get("language", "und")),
            user_preferences=user_preferences,
            system_policy=system_policy,
            metadata=data.get("metadata"),
            created_at=created_at,
        )


# ── Tuple coercion helpers for nested lists (element-level validation) ──────────


def _freeze_resource_tuple(
    seq: Any, field_name: str
) -> tuple[DomainResolutionResource, ...]:
    """Validate and freeze a sequence of DomainResolutionResource.

    Accepts:
    * tuple/list of DomainResolutionResource instances
    * tuple/list of Mappings → coerced via ``from_dict()``
    * None → ()

    Rejects: int, str, object, callback, or any other non-convertible type.
    """
    return _freeze_nested_sequence(
        seq, field_name, DomainResolutionResource, "DomainResolutionResource"
    )


def _freeze_entity_tuple(
    seq: Any, field_name: str
) -> tuple[DomainResolutionEntity, ...]:
    """Validate and freeze a sequence of DomainResolutionEntity."""
    return _freeze_nested_sequence(
        seq, field_name, DomainResolutionEntity, "DomainResolutionEntity"
    )


def _freeze_knowledge_tuple(
    seq: Any, field_name: str
) -> tuple[DomainResolutionKnowledgeItem, ...]:
    """Validate and freeze a sequence of DomainResolutionKnowledgeItem."""
    return _freeze_nested_sequence(
        seq,
        field_name,
        DomainResolutionKnowledgeItem,
        "DomainResolutionKnowledgeItem",
    )


def _freeze_history_tuple(
    seq: Any, field_name: str
) -> tuple[DomainResolutionHistoryItem, ...]:
    """Validate and freeze a sequence of DomainResolutionHistoryItem."""
    return _freeze_nested_sequence(
        seq, field_name, DomainResolutionHistoryItem, "DomainResolutionHistoryItem"
    )


def _freeze_event_tuple(seq: Any, field_name: str) -> tuple[DomainResolutionEvent, ...]:
    """Validate and freeze a sequence of DomainResolutionEvent."""
    return _freeze_nested_sequence(
        seq, field_name, DomainResolutionEvent, "DomainResolutionEvent"
    )


def _freeze_signal_tuple(
    seq: Any, field_name: str
) -> tuple[DomainResolutionSignal, ...]:
    """Validate and freeze a sequence of DomainResolutionSignal."""
    return _freeze_nested_sequence(
        seq, field_name, DomainResolutionSignal, "DomainResolutionSignal"
    )


def _freeze_nested_sequence(
    seq: Any,
    field_name: str,
    expected_type: type,
    type_name: str,
) -> tuple:
    """Element-level coercion and validation for nested contract sequences.

    Accepts instances of ``expected_type`` or ``Mapping`` (coerced via
    ``from_dict()``).  Rejects int, str, bool, object, callback, etc.
    Errors preserve field paths like ``resources[i].sensitivity``.
    """
    if seq is None:
        return ()
    if isinstance(seq, (str, bytes)):
        raise DomainResolutionContractError(
            f"{field_name} must be a sequence of {type_name}, not a string",
            field=field_name,
        )
    if not isinstance(seq, (tuple, list, Sequence)):
        raise DomainResolutionContractError(
            f"{field_name} must be a list or tuple of {type_name}",
            field=field_name,
        )
    result: list = []
    for i, item in enumerate(seq):
        item_path = f"{field_name}[{i}]"
        if isinstance(item, expected_type):
            result.append(item)
        elif isinstance(item, Mapping):
            try:
                result.append(expected_type.from_dict(dict(item)))
            except DomainError as exc:
                _wrap_resolution_nested_error(exc, field_name, i)
        elif item is None:
            raise DomainResolutionContractError(
                f"Each item in {field_name} must be a {type_name} or mapping, not None",
                field=item_path,
            )
        else:
            raise DomainResolutionContractError(
                f"Each item in {field_name} must be a {type_name} or mapping, "
                f"got {type(item).__name__}",
                field=item_path,
            )
    return tuple(result)


# ── from_dict list parsers ────────────────────────────────────────────────────


def _parse_resource_list(
    raw: Any, field_name: str
) -> tuple[DomainResolutionResource, ...]:
    if raw is None:
        return ()
    if not isinstance(raw, (list, tuple)):
        raise DomainResolutionSerializationError(
            f"{field_name} must be a list", field=field_name
        )
    result: list[DomainResolutionResource] = []
    for i, item in enumerate(raw):
        if isinstance(item, DomainResolutionResource):
            result.append(item)
        elif isinstance(item, Mapping):
            try:
                result.append(DomainResolutionResource.from_dict(dict(item)))
            except DomainError as exc:
                _wrap_resolution_nested_error(exc, field_name, i)
        else:
            raise DomainResolutionSerializationError(
                f"Each item in {field_name} must be a mapping, got {type(item).__name__} at index {i}",
                field=f"{field_name}[{i}]",
            )
    return tuple(result)


def _parse_entity_list(raw: Any, field_name: str) -> tuple[DomainResolutionEntity, ...]:
    if raw is None:
        return ()
    if not isinstance(raw, (list, tuple)):
        raise DomainResolutionSerializationError(
            f"{field_name} must be a list", field=field_name
        )
    result: list[DomainResolutionEntity] = []
    for i, item in enumerate(raw):
        if isinstance(item, DomainResolutionEntity):
            result.append(item)
        elif isinstance(item, Mapping):
            try:
                result.append(DomainResolutionEntity.from_dict(dict(item)))
            except DomainError as exc:
                _wrap_resolution_nested_error(exc, field_name, i)
        else:
            raise DomainResolutionSerializationError(
                f"Each item in {field_name} must be a mapping, got {type(item).__name__} at index {i}",
                field=f"{field_name}[{i}]",
            )
    return tuple(result)


def _parse_knowledge_list(
    raw: Any, field_name: str
) -> tuple[DomainResolutionKnowledgeItem, ...]:
    if raw is None:
        return ()
    if not isinstance(raw, (list, tuple)):
        raise DomainResolutionSerializationError(
            f"{field_name} must be a list", field=field_name
        )
    result: list[DomainResolutionKnowledgeItem] = []
    for i, item in enumerate(raw):
        if isinstance(item, DomainResolutionKnowledgeItem):
            result.append(item)
        elif isinstance(item, Mapping):
            try:
                result.append(DomainResolutionKnowledgeItem.from_dict(dict(item)))
            except DomainError as exc:
                _wrap_resolution_nested_error(exc, field_name, i)
        else:
            raise DomainResolutionSerializationError(
                f"Each item in {field_name} must be a mapping, got {type(item).__name__} at index {i}",
                field=f"{field_name}[{i}]",
            )
    return tuple(result)


def _parse_history_list(
    raw: Any, field_name: str
) -> tuple[DomainResolutionHistoryItem, ...]:
    if raw is None:
        return ()
    if not isinstance(raw, (list, tuple)):
        raise DomainResolutionSerializationError(
            f"{field_name} must be a list", field=field_name
        )
    result: list[DomainResolutionHistoryItem] = []
    for i, item in enumerate(raw):
        if isinstance(item, DomainResolutionHistoryItem):
            result.append(item)
        elif isinstance(item, Mapping):
            try:
                result.append(DomainResolutionHistoryItem.from_dict(dict(item)))
            except DomainError as exc:
                _wrap_resolution_nested_error(exc, field_name, i)
        else:
            raise DomainResolutionSerializationError(
                f"Each item in {field_name} must be a mapping, got {type(item).__name__} at index {i}",
                field=f"{field_name}[{i}]",
            )
    return tuple(result)


def _parse_event_list(raw: Any, field_name: str) -> tuple[DomainResolutionEvent, ...]:
    if raw is None:
        return ()
    if not isinstance(raw, (list, tuple)):
        raise DomainResolutionSerializationError(
            f"{field_name} must be a list", field=field_name
        )
    result: list[DomainResolutionEvent] = []
    for i, item in enumerate(raw):
        if isinstance(item, DomainResolutionEvent):
            result.append(item)
        elif isinstance(item, Mapping):
            try:
                result.append(DomainResolutionEvent.from_dict(dict(item)))
            except DomainError as exc:
                _wrap_resolution_nested_error(exc, field_name, i)
        else:
            raise DomainResolutionSerializationError(
                f"Each item in {field_name} must be a mapping, got {type(item).__name__} at index {i}",
                field=f"{field_name}[{i}]",
            )
    return tuple(result)


def _parse_signal_list(raw: Any, field_name: str) -> tuple[DomainResolutionSignal, ...]:
    if raw is None:
        return ()
    if not isinstance(raw, (list, tuple)):
        raise DomainResolutionSerializationError(
            f"{field_name} must be a list", field=field_name
        )
    result: list[DomainResolutionSignal] = []
    for i, item in enumerate(raw):
        if isinstance(item, DomainResolutionSignal):
            result.append(item)
        elif isinstance(item, Mapping):
            try:
                result.append(DomainResolutionSignal.from_dict(dict(item)))
            except DomainError as exc:
                _wrap_resolution_nested_error(exc, field_name, i)
        else:
            raise DomainResolutionSerializationError(
                f"Each item in {field_name} must be a mapping, got {type(item).__name__} at index {i}",
                field=f"{field_name}[{i}]",
            )
    return tuple(result)


# ── Public API ─────────────────────────────────────────────────────────────────

__all__ = [
    "DomainResolutionContext",
    "DomainResolutionEntity",
    "DomainResolutionEvent",
    "DomainResolutionHistoryItem",
    "DomainResolutionKnowledgeItem",
    "DomainResolutionPolicy",
    "DomainResolutionResource",
    "DomainResolutionSignal",
]
