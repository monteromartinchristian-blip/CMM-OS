"""Phase 10.33 — Domain Event Contracts.

Immutable, JSON-serializable, type-safe contracts for Domain Intelligence Events.
All dataclasses are ``frozen=True``, use ``slots=True``, and never expose mutable state.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from types import MappingProxyType
from typing import Any

from cmm.domains.contracts import (
    _deep_freeze,
    _deep_unfreeze,
    _ensure_tz_aware,
    _normalize_empty_to_none,
    _validate_non_empty_str,
)
from cmm.domains.errors import (
    DomainContractValidationError,
    DomainEventContractError,
    DomainEventSerializationError,
)
from cmm.domains.identifiers import DomainId

# ── JSON-safe type alias ──────────────────────────────────────────────────────

JSONValue = (
    str | int | float | bool | None | Mapping[str, "JSONValue"] | list["JSONValue"]
)

# ── Credential / Secret key substrings for rejection ─────────────────────────

_CREDENTIAL_KEY_SUBSTRINGS = frozenset(
    {
        "password",
        "secret",
        "token",
        "apikey",
        "api_key",
        "privatekey",
        "private_key",
        "credential",
        "authtoken",
        "auth_token",
        "accesskey",
        "access_key",
        "secretkey",
        "secret_key",
        "authorization",
        "cookie",
    }
)


def _reject_unknown_event_fields(
    data: Mapping[str, Any], known: frozenset[str], cls_name: str
) -> None:
    """Raise DomainEventSerializationError if data contains unknown fields."""
    unknown = set(data.keys()) - known
    if unknown:
        raise DomainEventSerializationError(
            f"{cls_name}.from_dict got unknown fields: {sorted(unknown)}",
            field="data",
            details={"unknown_fields": sorted(unknown)},
        )


def _validate_json_safe_event(value: Any, field_name: str) -> Any:
    """Validate that a value is JSON-safe (recursively)."""
    if value is None:
        return None
    if isinstance(value, (str, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise DomainEventContractError(
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
                raise DomainEventContractError(
                    f"{field_name}: all keys must be strings",
                    field=field_name,
                )
            result[k] = _validate_json_safe_event(v, f"{field_name}.{k}")
        return result
    if isinstance(value, (list, tuple)):
        return [
            _validate_json_safe_event(v, f"{field_name}[{i}]")
            for i, v in enumerate(value)
        ]
    raise DomainEventContractError(
        f"{field_name}: value must be JSON-safe, got {type(value).__name__}: {value!r}",
        field=field_name,
    )


def _reject_credential_keys_event(data: Any, field_name: str) -> None:
    """Recursively scan for credential-like keys in JSON-safe structures."""
    if data is None:
        return
    if isinstance(data, Mapping):
        for key, value in data.items():
            key_lower = key.lower()
            norm_key = key_lower.replace("_", "").replace("-", "")
            if any(
                ck in key_lower or ck in norm_key for ck in _CREDENTIAL_KEY_SUBSTRINGS
            ):
                raise DomainContractValidationError(
                    f"Credential-like key detected in {field_name}: '{key}'",
                    field=field_name,
                    details={"credential_key": key},
                )
            _reject_credential_keys_event(value, f"{field_name}.{key}")
    elif isinstance(data, (list, tuple)):
        for i, item in enumerate(data):
            _reject_credential_keys_event(item, f"{field_name}[{i}]")


def _validate_event_dict_payload(
    raw: Any, field_name: str
) -> MappingProxyType[str, Any]:
    """Validate dictionary payload/metadata is JSON-safe, credential-free, and deep-freeze it."""
    if raw is None:
        return MappingProxyType({})
    if isinstance(raw, MappingProxyType):
        _reject_credential_keys_event(raw, field_name)
        return raw
    if not isinstance(raw, Mapping):
        raise DomainEventContractError(
            f"{field_name} must be a mapping, got {type(raw).__name__}",
            field=field_name,
        )
    validated = _validate_json_safe_event(raw, field_name)
    _reject_credential_keys_event(validated, field_name)
    return _deep_freeze(validated)


def _freeze_domain_ids_event(
    seq: Any, field_name: str, *, require_unique: bool = True
) -> tuple[DomainId, ...]:
    """Validate and convert sequence to tuple of unique DomainId."""
    if seq is None:
        return ()
    if isinstance(seq, (str, bytes)):
        raise DomainEventContractError(
            f"{field_name} must be a sequence of DomainId, not a string",
            field=field_name,
        )
    if not isinstance(seq, (tuple, list, set, Sequence)):
        raise DomainEventContractError(
            f"{field_name} must be a tuple, list, or sequence",
            field=field_name,
        )
    result: list[DomainId] = []
    seen: set[str] = set()
    for i, item in enumerate(seq):
        if isinstance(item, DomainId):
            domain_id = item
        elif isinstance(item, str):
            try:
                domain_id = DomainId.from_str(item)
            except Exception as exc:
                raise DomainEventContractError(
                    f"Invalid DomainId in {field_name}[{i}]: {exc}",
                    field=field_name,
                ) from exc
        else:
            raise DomainEventContractError(
                f"{field_name}[{i}] must be DomainId or str, got {type(item).__name__}",
                field=field_name,
            )
        slug = domain_id.slug
        if require_unique and slug in seen:
            raise DomainEventContractError(
                f"Duplicate domain in {field_name}: {slug}",
                field=field_name,
                details={"duplicate": slug, "index": i},
            )
        if require_unique:
            seen.add(slug)
        result.append(domain_id)
    return tuple(result)


def _freeze_str_tuple_unique_event(seq: Any, field_name: str) -> tuple[str, ...]:
    """Validate sequence of unique non-empty strings."""
    if seq is None:
        return ()
    if isinstance(seq, (str, bytes)):
        raise DomainEventContractError(
            f"{field_name} must be a sequence of strings, not a string",
            field=field_name,
        )
    if not isinstance(seq, (tuple, list, set, Sequence)):
        raise DomainEventContractError(
            f"{field_name} must be a tuple, list, or sequence of strings",
            field=field_name,
        )
    result: list[str] = []
    seen: set[str] = set()
    for i, item in enumerate(seq):
        if not isinstance(item, str) or not item.strip():
            raise DomainEventContractError(
                f"All items in {field_name} must be non-empty strings",
                field=field_name,
                details={"index": i, "value": item},
            )
        clean = item.strip()
        if clean in seen:
            raise DomainEventContractError(
                f"Duplicate item in {field_name}: {clean!r}",
                field=field_name,
                details={"duplicate": clean},
            )
        seen.add(clean)
        result.append(clean)
    return tuple(result)


def _parse_datetime_event(val: Any, field_name: str) -> datetime:
    """Parse string or datetime to timezone-aware datetime, rejecting naive."""
    if val is None:
        raise DomainEventSerializationError(
            f"{field_name} cannot be None", field=field_name
        )
    if isinstance(val, datetime):
        if val.tzinfo is None:
            raise DomainEventContractError(
                f"{field_name} must be timezone-aware", field=field_name
            )
        return val
    if isinstance(val, str):
        try:
            parsed = datetime.fromisoformat(val)
        except ValueError as exc:
            raise DomainEventSerializationError(
                f"Invalid isoformat datetime string for {field_name}: {val!r}",
                field=field_name,
            ) from exc
        if parsed.tzinfo is None:
            raise DomainEventSerializationError(
                f"{field_name} must be timezone-aware", field=field_name
            )
        return parsed
    raise DomainEventSerializationError(
        f"{field_name} must be an ISO string or datetime instance, got {type(val).__name__}",
        field=field_name,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# DomainEventReference
# ═══════════════════════════════════════════════════════════════════════════════

_EVENT_REF_KNOWN = frozenset({"kind", "reference_id", "domain_id"})


@dataclass(frozen=True, slots=True)
class DomainEventReference:
    """Reference pointer to an upstream authoritative object."""

    kind: str
    reference_id: str
    domain_id: DomainId | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "kind", _validate_non_empty_str(self.kind, "kind"))
        object.__setattr__(
            self,
            "reference_id",
            _validate_non_empty_str(self.reference_id, "reference_id"),
        )
        if self.domain_id is not None:
            if isinstance(self.domain_id, str):
                object.__setattr__(self, "domain_id", DomainId.from_str(self.domain_id))
            elif not isinstance(self.domain_id, DomainId):
                raise DomainEventContractError(
                    f"domain_id must be DomainId or None, got {type(self.domain_id).__name__}",
                    field="domain_id",
                )

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        d: dict[str, Any] = {
            "kind": self.kind,
            "reference_id": self.reference_id,
        }
        if self.domain_id is not None:
            d["domain_id"] = self.domain_id.to_dict()
        else:
            d["domain_id"] = None
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DomainEventReference:
        """Deserialize from dictionary."""
        if not isinstance(data, Mapping):
            raise DomainEventSerializationError(
                "DomainEventReference.from_dict requires a mapping", field="data"
            )
        _reject_unknown_event_fields(data, _EVENT_REF_KNOWN, "DomainEventReference")
        required = {"kind", "reference_id"}
        missing = required - set(data.keys())
        if missing:
            raise DomainEventSerializationError(
                f"DomainEventReference.from_dict missing required fields: {sorted(missing)}",
                field="data",
            )
        raw_domain_id = data.get("domain_id")
        domain_id: DomainId | None = None
        if raw_domain_id is not None:
            if isinstance(raw_domain_id, Mapping):
                domain_id = DomainId.from_dict(dict(raw_domain_id))
            elif isinstance(raw_domain_id, str):
                domain_id = DomainId.from_str(raw_domain_id)
            elif isinstance(raw_domain_id, DomainId):
                domain_id = raw_domain_id
            else:
                raise DomainEventSerializationError(
                    f"Invalid domain_id in DomainEventReference: {raw_domain_id!r}",
                    field="domain_id",
                )
        return cls(
            kind=str(data["kind"]),
            reference_id=str(data["reference_id"]),
            domain_id=domain_id,
        )


# ═══════════════════════════════════════════════════════════════════════════════
# DomainEvent
# ═══════════════════════════════════════════════════════════════════════════════

_DOMAIN_EVENT_KNOWN = frozenset(
    {
        "event_id",
        "event_type",
        "schema_version",
        "domain_id",
        "related_domain_ids",
        "actor",
        "session_id",
        "occurred_at",
        "provenance",
        "sensitivity",
        "permissions",
        "correlation_id",
        "causation_id",
        "payload",
        "metadata",
    }
)


@dataclass(frozen=True, slots=True)
class DomainEvent:
    """Immutable, serializable Domain Intelligence Event."""

    event_id: str
    event_type: str
    schema_version: str
    domain_id: DomainId
    actor: str
    occurred_at: datetime
    sensitivity: str
    related_domain_ids: tuple[DomainId, ...] = ()
    session_id: str | None = None
    provenance: tuple[DomainEventReference, ...] = ()
    permissions: tuple[str, ...] = ()
    correlation_id: str | None = None
    causation_id: str | None = None
    payload: MappingProxyType[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )
    metadata: MappingProxyType[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "event_id", _validate_non_empty_str(self.event_id, "event_id")
        )
        object.__setattr__(
            self, "event_type", _validate_non_empty_str(self.event_type, "event_type")
        )
        object.__setattr__(
            self,
            "schema_version",
            _validate_non_empty_str(self.schema_version, "schema_version"),
        )
        object.__setattr__(self, "actor", _validate_non_empty_str(self.actor, "actor"))
        object.__setattr__(
            self,
            "sensitivity",
            _validate_non_empty_str(self.sensitivity, "sensitivity"),
        )

        # DomainId validation / coercion
        if isinstance(self.domain_id, str):
            object.__setattr__(self, "domain_id", DomainId.from_str(self.domain_id))
        elif not isinstance(self.domain_id, DomainId):
            raise DomainEventContractError(
                f"domain_id must be DomainId, got {type(self.domain_id).__name__}",
                field="domain_id",
            )

        # Related domain IDs
        object.__setattr__(
            self,
            "related_domain_ids",
            _freeze_domain_ids_event(self.related_domain_ids, "related_domain_ids"),
        )

        # Session / correlation / causation IDs
        object.__setattr__(
            self, "session_id", _normalize_empty_to_none(self.session_id)
        )
        object.__setattr__(
            self, "correlation_id", _normalize_empty_to_none(self.correlation_id)
        )
        object.__setattr__(
            self, "causation_id", _normalize_empty_to_none(self.causation_id)
        )

        # occurred_at timezone awareness
        object.__setattr__(
            self, "occurred_at", _ensure_tz_aware(self.occurred_at, "occurred_at")
        )

        # Permissions
        object.__setattr__(
            self,
            "permissions",
            _freeze_str_tuple_unique_event(self.permissions, "permissions"),
        )

        # Provenance
        if self.provenance is None:
            object.__setattr__(self, "provenance", ())
        elif isinstance(self.provenance, (tuple, list, Sequence)):
            prov_list: list[DomainEventReference] = []
            for i, ref in enumerate(self.provenance):
                if isinstance(ref, DomainEventReference):
                    prov_list.append(ref)
                elif isinstance(ref, Mapping):
                    prov_list.append(DomainEventReference.from_dict(dict(ref)))
                else:
                    raise DomainEventContractError(
                        f"provenance[{i}] must be DomainEventReference, got {type(ref).__name__}",
                        field="provenance",
                    )
            object.__setattr__(self, "provenance", tuple(prov_list))
        else:
            raise DomainEventContractError(
                "provenance must be a sequence of DomainEventReference",
                field="provenance",
            )

        # Payload & Metadata validation (JSON-safe, recursive secret rejection, frozen)
        object.__setattr__(
            self, "payload", _validate_event_dict_payload(self.payload, "payload")
        )
        object.__setattr__(
            self, "metadata", _validate_event_dict_payload(self.metadata, "metadata")
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "schema_version": self.schema_version,
            "domain_id": self.domain_id.to_dict(),
            "related_domain_ids": [d.to_dict() for d in self.related_domain_ids],
            "actor": self.actor,
            "session_id": self.session_id,
            "occurred_at": self.occurred_at.isoformat(),
            "provenance": [p.to_dict() for p in self.provenance],
            "sensitivity": self.sensitivity,
            "permissions": list(self.permissions),
            "correlation_id": self.correlation_id,
            "causation_id": self.causation_id,
            "payload": _deep_unfreeze(self.payload),
            "metadata": _deep_unfreeze(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DomainEvent:
        """Deserialize from dictionary."""
        if not isinstance(data, Mapping):
            raise DomainEventSerializationError(
                "DomainEvent.from_dict requires a mapping", field="data"
            )
        _reject_unknown_event_fields(data, _DOMAIN_EVENT_KNOWN, "DomainEvent")
        required = {
            "event_id",
            "event_type",
            "schema_version",
            "domain_id",
            "actor",
            "occurred_at",
            "sensitivity",
        }
        missing = required - set(data.keys())
        if missing:
            raise DomainEventSerializationError(
                f"DomainEvent.from_dict missing required fields: {sorted(missing)}",
                field="data",
            )

        # DomainId
        raw_dom = data["domain_id"]
        if isinstance(raw_dom, Mapping):
            domain_id = DomainId.from_dict(dict(raw_dom))
        elif isinstance(raw_dom, str):
            domain_id = DomainId.from_str(raw_dom)
        elif isinstance(raw_dom, DomainId):
            domain_id = raw_dom
        else:
            raise DomainEventSerializationError(
                f"Invalid domain_id in DomainEvent: {raw_dom!r}", field="domain_id"
            )

        # Related DomainIds
        raw_rel = data.get("related_domain_ids", ())
        if not isinstance(raw_rel, (list, tuple, Sequence)):
            raise DomainEventSerializationError(
                "related_domain_ids must be a sequence", field="related_domain_ids"
            )
        rel_list: list[DomainId] = []
        for i, rd in enumerate(raw_rel):
            if isinstance(rd, Mapping):
                rel_list.append(DomainId.from_dict(dict(rd)))
            elif isinstance(rd, str):
                rel_list.append(DomainId.from_str(rd))
            elif isinstance(rd, DomainId):
                rel_list.append(rd)
            else:
                raise DomainEventSerializationError(
                    f"Invalid related_domain_ids[{i}]: {rd!r}",
                    field="related_domain_ids",
                )

        # Provenance
        raw_prov = data.get("provenance", ())
        if not isinstance(raw_prov, (list, tuple, Sequence)):
            raise DomainEventSerializationError(
                "provenance must be a sequence", field="provenance"
            )
        prov_list: list[DomainEventReference] = []
        for p in raw_prov:
            if isinstance(p, DomainEventReference):
                prov_list.append(p)
            elif isinstance(p, Mapping):
                prov_list.append(DomainEventReference.from_dict(dict(p)))
            else:
                raise DomainEventSerializationError(
                    f"Invalid provenance item: {p!r}", field="provenance"
                )

        # DateTime
        occurred_at = _parse_datetime_event(data["occurred_at"], "occurred_at")

        return cls(
            event_id=str(data["event_id"]),
            event_type=str(data["event_type"]),
            schema_version=str(data["schema_version"]),
            domain_id=domain_id,
            related_domain_ids=tuple(rel_list),
            actor=str(data["actor"]),
            session_id=data.get("session_id"),
            occurred_at=occurred_at,
            provenance=tuple(prov_list),
            sensitivity=str(data["sensitivity"]),
            permissions=tuple(data.get("permissions", ())),
            correlation_id=data.get("correlation_id"),
            causation_id=data.get("causation_id"),
            payload=data.get("payload", {}),
            metadata=data.get("metadata", {}),
        )
