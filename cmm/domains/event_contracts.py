"""Phase 10.33 — Domain Event Contracts.

Immutable, JSON-serializable, type-safe contracts for Domain Intelligence Events.
All dataclasses are ``frozen=True``, use ``slots=True``, and never expose mutable state.
"""

from __future__ import annotations

import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from types import MappingProxyType
from typing import Any

from cmm.domains.contracts import (
    _deep_freeze,
    _deep_unfreeze,
    _ensure_tz_aware,
    _validate_non_empty_str,
)
from cmm.domains.errors import (
    DomainContractValidationError,
    DomainError,
    DomainEventContractError,
    DomainEventSerializationError,
)
from cmm.domains.identifiers import DomainId

# ── JSON-safe type alias ──────────────────────────────────────────────────────

JSONValue = (
    str | int | float | bool | None | Mapping[str, "JSONValue"] | list["JSONValue"]
)

# ── Privacy & Secret detection vocabulary ─────────────────────────────────────

_PRIVATE_MARKERS = frozenset(
    {
        "prompt",
        "systemprompt",
        "developerprompt",
        "privateprompt",
        "rawprompt",
        "usermessage",
        "objectivetext",
        "rawcontent",
        "secret",
        "secrets",
        "token",
        "tokens",
        "credential",
        "credentials",
        "password",
        "passwords",
        "apikey",
        "api_key",
        "privatekey",
        "private_key",
        "accesskey",
        "access_key",
        "secretkey",
        "secret_key",
        "authtoken",
        "auth_token",
        "authorization",
        "authorizationheader",
        "cookie",
        "setcookie",
        "set_cookie",
        "chainofthought",
        "reasoning",
        "rawreasoning",
        "reasoningtext",
        "reasoningcontent",
        "hiddenreasoning",
        "toolarguments",
        "toolresponse",
        "providerrequest",
        "providerresponse",
        "pii",
        "sessiontoken",
        "session_token",
        "sessionid",
        "session_id",
        "csrftoken",
        "csrf_token",
        "accesstoken",
        "access_token",
        "refreshtoken",
        "refresh_token",
    }
)

_SINGLE_WORD_PRIVATE_MARKERS = frozenset(
    {
        "systemprompt",
        "developerprompt",
        "privateprompt",
        "rawprompt",
        "usermessage",
        "objectivetext",
        "rawcontent",
        "chainofthought",
        "hiddenreasoning",
        "reasoningcontent",
        "rawreasoning",
        "rawresource",
        "toolarguments",
        "toolresponse",
        "providerrequest",
        "providerresponse",
        "pii",
        "password",
        "passwords",
        "secret",
        "secrets",
        "token",
        "tokens",
        "credential",
        "credentials",
        "apikey",
        "privatekey",
        "secretkey",
        "accesskey",
        "authtoken",
        "sessiontoken",
        "sessionid",
        "csrftoken",
        "cookie",
        "cookies",
        "authorization",
        "prompt",
    }
)

_SAFE_REFERENCE_KEYS = frozenset(
    {
        "reasoningtraceid",
        "knowledgepackageid",
        "providerauditid",
        "crossdomaintraceid",
        "contextid",
        "resultid",
        "compositionid",
        "conflictid",
        "executionid",
        "workflowid",
        "operationid",
        "approvalid",
        "proposalid",
        "updateid",
    }
)

_PRIVATE_TOKEN_SEQUENCES = (
    ("system", "prompt"),
    ("developer", "prompt"),
    ("private", "prompt"),
    ("raw", "prompt"),
    ("user", "message"),
    ("objective", "text"),
    ("raw", "content"),
    ("api", "key"),
    ("access", "key"),
    ("secret", "key"),
    ("private", "key"),
    ("auth", "token"),
    ("authorization", "header"),
    ("chain", "of", "thought"),
    ("reasoning", "text"),
    ("reasoning", "content"),
    ("hidden", "reasoning"),
    ("raw", "reasoning"),
    ("raw", "resource"),
    ("tool", "arguments"),
    ("tool", "response"),
    ("provider", "request"),
    ("provider", "response"),
    ("session", "token"),
    ("session", "id"),
    ("access", "token"),
    ("refresh", "token"),
    ("csrf", "token"),
)

_SECRET_VALUE_PATTERNS = (
    re.compile(r"authorization\s*[:=]", re.IGNORECASE),
    re.compile(r"\bbearer\s+[a-zA-Z0-9_\-\.]{8,}", re.IGNORECASE),
    re.compile(r"\bbearer\s*[:=]\s*\S+", re.IGNORECASE),
    re.compile(r"\b(?:sk|pk|api[_-]?key)[-_][a-zA-Z0-9_\-]{8,}\b", re.IGNORECASE),
    re.compile(r"\bkey-[a-zA-Z0-9_\-]{8,}\b", re.IGNORECASE),
    re.compile(
        r"\b(?:password|secret|credential|cookie|set[_-]?cookie|session[_-]?token|sessionid|session[_-]?id|access[_-]?token|refresh[_-]?token|auth[_-]?token|csrf[_-]?token|csrftoken)\s*[:=]\s*\S+",
        re.IGNORECASE,
    ),
)


def _normalized(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())


def _word_tokens(value: str) -> tuple[str, ...]:
    separated = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1 \2", value)
    separated = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", separated)
    return tuple(item for item in re.split(r"[^A-Za-z0-9]+", separated.lower()) if item)


def _contains_private_marker(value: str) -> bool:
    cleaned = re.sub(r"\[REDACTED_[A-Z0-9_]+\]", " ", value, flags=re.IGNORECASE)
    norm = _normalized(cleaned)
    if not norm or norm in _SAFE_REFERENCE_KEYS:
        return False
    if norm in _PRIVATE_MARKERS:
        return True
    tokens = _word_tokens(cleaned)
    if any(item in _SINGLE_WORD_PRIVATE_MARKERS for item in tokens):
        return True
    return any(
        tokens[index : index + len(sequence)] == sequence
        for sequence in _PRIVATE_TOKEN_SEQUENCES
        for index in range(len(tokens) - len(sequence) + 1)
    )


def _contains_secret_value(value: str) -> bool:
    cleaned = re.sub(r"\[REDACTED_[A-Z0-9_]+\]", " ", value, flags=re.IGNORECASE)
    for pattern in _SECRET_VALUE_PATTERNS:
        if pattern.search(cleaned):
            return True
    return False


def _validate_event_string_privacy(value: str, field_name: str) -> str:
    """Validate that an event string field contains no secrets or forbidden private markers."""
    if _contains_secret_value(value):
        raise DomainContractValidationError(
            f"Secret-like value detected in {field_name}",
            field=field_name,
            details={"category": "secret_value"},
        )
    if _contains_private_marker(value):
        raise DomainContractValidationError(
            f"Forbidden privacy/credential marker detected in {field_name}",
            field=field_name,
            details={"category": "private_marker"},
        )
    return value


def _validate_event_domain_id_privacy(
    domain_id: DomainId | None, field_name: str = "domain_id"
) -> DomainId | None:
    """Validate that a DomainId does not contain secrets or forbidden private markers."""
    if domain_id is None:
        return None
    if not isinstance(domain_id, DomainId):
        raise DomainContractValidationError(
            f"{field_name} must be DomainId or None, got {type(domain_id).__name__}",
            field=field_name,
        )
    _validate_event_string_privacy(domain_id.slug, field_name)
    _validate_event_string_privacy(str(domain_id), field_name)
    return domain_id


def _validate_optional_str_identifier(val: Any, field_name: str) -> str | None:
    """Validate optional string identifier: None or strict string (coerces whitespace/empty to None)."""
    if val is None:
        return None
    if not isinstance(val, str) or isinstance(val, bool):
        raise DomainContractValidationError(
            f"{field_name} must be a string or None, got {type(val).__name__}",
            field=field_name,
        )
    stripped = val.strip()
    if not stripped:
        return None
    _validate_event_string_privacy(stripped, field_name)
    return stripped


def _validate_optional_str_from_dict(val: Any, field_name: str) -> str | None:
    """Validate optional string identifier from dictionary deserialization."""
    if val is None:
        return None
    if not isinstance(val, str) or isinstance(val, bool):
        raise DomainEventSerializationError(
            f"{field_name} must be a string or None, got {type(val).__name__}",
            field=field_name,
        )
    stripped = val.strip()
    if not stripped:
        return None
    try:
        _validate_event_string_privacy(stripped, field_name)
    except DomainContractValidationError as exc:
        raise DomainEventSerializationError(
            exc.message, field=field_name, details=dict(exc.details)
        ) from None
    return stripped


def _reject_unknown_event_fields(
    data: Mapping[str, Any], known: frozenset[str], cls_name: str
) -> None:
    """Raise DomainEventSerializationError if data contains unknown fields."""
    unknown = set(data.keys()) - known
    if unknown:
        for k in unknown:
            if isinstance(k, str):
                try:
                    _validate_event_string_privacy(k, "field_name")
                except DomainContractValidationError as exc:
                    raise DomainEventSerializationError(
                        exc.message, field="data", details=dict(exc.details)
                    ) from None
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
                f"{field_name}: float must be finite, got non-finite {type(value).__name__}",
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
        f"{field_name}: value must be JSON-safe, got {type(value).__name__}",
        field=field_name,
    )


def _reject_credential_keys_event(data: Any, field_name: str) -> None:
    """Recursively scan for credential-like keys, forbidden private markers, and secret values."""
    if data is None:
        return
    if isinstance(data, str):
        _validate_event_string_privacy(data, field_name)
    elif isinstance(data, Mapping):
        for key, value in data.items():
            _validate_event_string_privacy(key, field_name)
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
    if isinstance(seq, (set, frozenset)):
        raise DomainEventContractError(
            f"{field_name} must be an ordered sequence (tuple or list), not a set/frozenset",
            field=field_name,
        )
    if not isinstance(seq, (tuple, list, Sequence)):
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
                domain_id = (
                    DomainId.from_str(item)
                    if item.startswith("domain:")
                    else DomainId(slug=item)
                )
            except (DomainError, ValueError, TypeError, KeyError):
                raise DomainEventContractError(
                    f"Invalid DomainId in {field_name}[{i}]",
                    field=field_name,
                    details={"index": i},
                ) from None
        else:
            raise DomainEventContractError(
                f"{field_name}[{i}] must be DomainId or str, got {type(item).__name__}",
                field=field_name,
                details={"index": i},
            )
        _validate_event_domain_id_privacy(domain_id, f"{field_name}[{i}]")
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
    if isinstance(seq, (set, frozenset)):
        raise DomainEventContractError(
            f"{field_name} must be an ordered sequence (tuple or list), not a set/frozenset",
            field=field_name,
        )
    if not isinstance(seq, (tuple, list, Sequence)):
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
                details={"index": i},
            )
        clean = item.strip()
        _validate_event_string_privacy(clean, f"{field_name}[{i}]")
        if clean in seen:
            raise DomainEventContractError(
                f"Duplicate item in {field_name}",
                field=field_name,
                details={"index": i},
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
        except (ValueError, TypeError):
            raise DomainEventSerializationError(
                f"Field '{field_name}' must contain a valid ISO-8601 datetime",
                field=field_name,
            ) from None
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
        kind_val = _validate_non_empty_str(self.kind, "kind")
        _validate_event_string_privacy(kind_val, "kind")
        object.__setattr__(self, "kind", kind_val)

        ref_id_val = _validate_non_empty_str(self.reference_id, "reference_id")
        _validate_event_string_privacy(ref_id_val, "reference_id")
        object.__setattr__(self, "reference_id", ref_id_val)

        if self.domain_id is not None:
            if isinstance(self.domain_id, str):
                try:
                    dom_id = (
                        DomainId.from_str(self.domain_id)
                        if self.domain_id.startswith("domain:")
                        else DomainId(slug=self.domain_id)
                    )
                except (DomainError, ValueError, TypeError, KeyError):
                    raise DomainEventContractError(
                        "Invalid domain_id in DomainEventReference",
                        field="domain_id",
                    ) from None
                object.__setattr__(self, "domain_id", dom_id)
            elif not isinstance(self.domain_id, DomainId):
                raise DomainEventContractError(
                    f"domain_id must be DomainId or None, got {type(self.domain_id).__name__}",
                    field="domain_id",
                )
            _validate_event_domain_id_privacy(self.domain_id, "domain_id")

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
        raw_kind = data["kind"]
        if not isinstance(raw_kind, str) or not raw_kind.strip():
            raise DomainEventSerializationError(
                f"kind must be a non-empty string, got {type(raw_kind).__name__}",
                field="kind",
            )
        try:
            _validate_event_string_privacy(raw_kind.strip(), "kind")
        except DomainContractValidationError as exc:
            raise DomainEventSerializationError(
                exc.message, field="kind", details=dict(exc.details)
            ) from None

        raw_ref_id = data["reference_id"]
        if not isinstance(raw_ref_id, str) or not raw_ref_id.strip():
            raise DomainEventSerializationError(
                f"reference_id must be a non-empty string, got {type(raw_ref_id).__name__}",
                field="reference_id",
            )
        try:
            _validate_event_string_privacy(raw_ref_id.strip(), "reference_id")
        except DomainContractValidationError as exc:
            raise DomainEventSerializationError(
                exc.message, field="reference_id", details=dict(exc.details)
            ) from None

        raw_domain_id = data.get("domain_id")
        domain_id: DomainId | None = None
        if raw_domain_id is not None:
            if isinstance(raw_domain_id, Mapping):
                try:
                    domain_id = DomainId.from_dict(dict(raw_domain_id))
                except (DomainError, ValueError, TypeError, KeyError):
                    raise DomainEventSerializationError(
                        "Invalid domain_id in DomainEventReference",
                        field="domain_id",
                    ) from None
            elif isinstance(raw_domain_id, str):
                try:
                    domain_id = (
                        DomainId.from_str(raw_domain_id)
                        if raw_domain_id.startswith("domain:")
                        else DomainId(slug=raw_domain_id)
                    )
                except (DomainError, ValueError, TypeError, KeyError):
                    raise DomainEventSerializationError(
                        "Invalid domain_id in DomainEventReference",
                        field="domain_id",
                    ) from None
            elif isinstance(raw_domain_id, DomainId):
                domain_id = raw_domain_id
            else:
                raise DomainEventSerializationError(
                    f"Invalid domain_id in DomainEventReference, got {type(raw_domain_id).__name__}",
                    field="domain_id",
                )
            try:
                _validate_event_domain_id_privacy(domain_id, "domain_id")
            except DomainContractValidationError as exc:
                raise DomainEventSerializationError(
                    exc.message, field="domain_id", details=dict(exc.details)
                ) from None
        return cls(
            kind=raw_kind,
            reference_id=raw_ref_id,
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
        event_id_val = _validate_non_empty_str(self.event_id, "event_id")
        _validate_event_string_privacy(event_id_val, "event_id")
        object.__setattr__(self, "event_id", event_id_val)

        event_type_val = _validate_non_empty_str(self.event_type, "event_type")
        _validate_event_string_privacy(event_type_val, "event_type")
        object.__setattr__(self, "event_type", event_type_val)

        schema_ver_val = _validate_non_empty_str(self.schema_version, "schema_version")
        _validate_event_string_privacy(schema_ver_val, "schema_version")
        object.__setattr__(self, "schema_version", schema_ver_val)
        actor_val = _validate_non_empty_str(self.actor, "actor")
        _validate_event_string_privacy(actor_val, "actor")
        object.__setattr__(self, "actor", actor_val)

        sens_val = _validate_non_empty_str(self.sensitivity, "sensitivity")
        _validate_event_string_privacy(sens_val, "sensitivity")
        object.__setattr__(self, "sensitivity", sens_val)

        # DomainId validation / coercion
        if isinstance(self.domain_id, str):
            try:
                dom_id = (
                    DomainId.from_str(self.domain_id)
                    if self.domain_id.startswith("domain:")
                    else DomainId(slug=self.domain_id)
                )
            except (DomainError, ValueError, TypeError, KeyError):
                raise DomainEventContractError(
                    "Invalid domain_id in DomainEvent",
                    field="domain_id",
                ) from None
            object.__setattr__(self, "domain_id", dom_id)
        elif not isinstance(self.domain_id, DomainId):
            raise DomainEventContractError(
                f"domain_id must be DomainId, got {type(self.domain_id).__name__}",
                field="domain_id",
            )
        _validate_event_domain_id_privacy(self.domain_id, "domain_id")

        # Related domain IDs
        object.__setattr__(
            self,
            "related_domain_ids",
            _freeze_domain_ids_event(self.related_domain_ids, "related_domain_ids"),
        )

        # Session / correlation / causation IDs
        object.__setattr__(
            self,
            "session_id",
            _validate_optional_str_identifier(self.session_id, "session_id"),
        )
        object.__setattr__(
            self,
            "correlation_id",
            _validate_optional_str_identifier(self.correlation_id, "correlation_id"),
        )
        object.__setattr__(
            self,
            "causation_id",
            _validate_optional_str_identifier(self.causation_id, "causation_id"),
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
        elif isinstance(self.provenance, (set, frozenset)):
            raise DomainEventContractError(
                "provenance must be an ordered sequence (tuple or list), not a set/frozenset",
                field="provenance",
            )
        elif isinstance(self.provenance, (tuple, list, Sequence)):
            prov_list: list[DomainEventReference] = []
            for i, ref in enumerate(self.provenance):
                if isinstance(ref, DomainEventReference):
                    prov_list.append(ref)
                elif isinstance(ref, Mapping):
                    try:
                        prov_list.append(DomainEventReference.from_dict(dict(ref)))
                    except (
                        DomainEventSerializationError,
                        DomainContractValidationError,
                    ) as exc:
                        raise DomainEventContractError(
                            exc.message,
                            field="provenance",
                            details={"index": i, **dict(getattr(exc, "details", {}))},
                        ) from None
                else:
                    raise DomainEventContractError(
                        f"provenance[{i}] must be DomainEventReference, got {type(ref).__name__}",
                        field="provenance",
                        details={"index": i},
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

        # Strict string validations for required fields
        raw_id = data["event_id"]
        if not isinstance(raw_id, str) or not raw_id.strip():
            raise DomainEventSerializationError(
                f"event_id must be a non-empty string, got {type(raw_id).__name__}",
                field="event_id",
            )
        try:
            _validate_event_string_privacy(raw_id.strip(), "event_id")
        except DomainContractValidationError as exc:
            raise DomainEventSerializationError(
                exc.message, field="event_id", details=dict(exc.details)
            ) from None

        raw_type = data["event_type"]
        if not isinstance(raw_type, str) or not raw_type.strip():
            raise DomainEventSerializationError(
                f"event_type must be a non-empty string, got {type(raw_type).__name__}",
                field="event_type",
            )
        try:
            _validate_event_string_privacy(raw_type.strip(), "event_type")
        except DomainContractValidationError as exc:
            raise DomainEventSerializationError(
                exc.message, field="event_type", details=dict(exc.details)
            ) from None

        raw_ver = data["schema_version"]
        if not isinstance(raw_ver, str) or not raw_ver.strip():
            raise DomainEventSerializationError(
                f"schema_version must be a non-empty string, got {type(raw_ver).__name__}",
                field="schema_version",
            )
        try:
            _validate_event_string_privacy(raw_ver.strip(), "schema_version")
        except DomainContractValidationError as exc:
            raise DomainEventSerializationError(
                exc.message, field="schema_version", details=dict(exc.details)
            ) from None

        raw_actor = data["actor"]
        if not isinstance(raw_actor, str) or not raw_actor.strip():
            raise DomainEventSerializationError(
                f"actor must be a non-empty string, got {type(raw_actor).__name__}",
                field="actor",
            )
        try:
            _validate_event_string_privacy(raw_actor.strip(), "actor")
        except DomainContractValidationError as exc:
            raise DomainEventSerializationError(
                exc.message, field="actor", details=dict(exc.details)
            ) from None

        raw_sens = data["sensitivity"]
        if not isinstance(raw_sens, str) or not raw_sens.strip():
            raise DomainEventSerializationError(
                f"sensitivity must be a non-empty string, got {type(raw_sens).__name__}",
                field="sensitivity",
            )
        try:
            _validate_event_string_privacy(raw_sens.strip(), "sensitivity")
        except DomainContractValidationError as exc:
            raise DomainEventSerializationError(
                exc.message, field="sensitivity", details=dict(exc.details)
            ) from None

        # DomainId
        raw_dom = data["domain_id"]
        if isinstance(raw_dom, Mapping):
            try:
                domain_id = DomainId.from_dict(dict(raw_dom))
            except (DomainError, ValueError, TypeError, KeyError):
                raise DomainEventSerializationError(
                    "Invalid domain_id in DomainEvent", field="domain_id"
                ) from None
        elif isinstance(raw_dom, str):
            try:
                domain_id = (
                    DomainId.from_str(raw_dom)
                    if raw_dom.startswith("domain:")
                    else DomainId(slug=raw_dom)
                )
            except (DomainError, ValueError, TypeError, KeyError):
                raise DomainEventSerializationError(
                    "Invalid domain_id in DomainEvent", field="domain_id"
                ) from None
        elif isinstance(raw_dom, DomainId):
            domain_id = raw_dom
        else:
            raise DomainEventSerializationError(
                f"Invalid domain_id in DomainEvent, got {type(raw_dom).__name__}",
                field="domain_id",
            )
        try:
            _validate_event_domain_id_privacy(domain_id, "domain_id")
        except DomainContractValidationError as exc:
            raise DomainEventSerializationError(
                exc.message, field="domain_id", details=dict(exc.details)
            ) from None

        # Related DomainIds
        raw_rel = data.get("related_domain_ids", ())
        if isinstance(raw_rel, (str, bytes, set, frozenset)) or not isinstance(
            raw_rel, (list, tuple, Sequence)
        ):
            raise DomainEventSerializationError(
                "related_domain_ids must be a sequence", field="related_domain_ids"
            )
        rel_list: list[DomainId] = []
        for i, rd in enumerate(raw_rel):
            if isinstance(rd, Mapping):
                try:
                    rel_dom = DomainId.from_dict(dict(rd))
                except (DomainError, ValueError, TypeError, KeyError):
                    raise DomainEventSerializationError(
                        f"Invalid related_domain_ids[{i}]",
                        field="related_domain_ids",
                        details={"index": i},
                    ) from None
            elif isinstance(rd, str):
                try:
                    rel_dom = (
                        DomainId.from_str(rd)
                        if rd.startswith("domain:")
                        else DomainId(slug=rd)
                    )
                except (DomainError, ValueError, TypeError, KeyError):
                    raise DomainEventSerializationError(
                        f"Invalid related_domain_ids[{i}]",
                        field="related_domain_ids",
                        details={"index": i},
                    ) from None
            elif isinstance(rd, DomainId):
                rel_dom = rd
            else:
                raise DomainEventSerializationError(
                    f"Invalid related_domain_ids[{i}], got {type(rd).__name__}",
                    field="related_domain_ids",
                    details={"index": i},
                )
            try:
                _validate_event_domain_id_privacy(rel_dom, f"related_domain_ids[{i}]")
            except DomainContractValidationError as exc:
                raise DomainEventSerializationError(
                    exc.message,
                    field="related_domain_ids",
                    details={"index": i, **dict(exc.details)},
                ) from None
            rel_list.append(rel_dom)

        # Provenance
        raw_prov = data.get("provenance", ())
        if isinstance(raw_prov, (str, bytes, set, frozenset)) or not isinstance(
            raw_prov, (list, tuple, Sequence)
        ):
            raise DomainEventSerializationError(
                "provenance must be a sequence", field="provenance"
            )
        prov_list: list[DomainEventReference] = []
        for i, p in enumerate(raw_prov):
            if isinstance(p, DomainEventReference):
                prov_list.append(p)
            elif isinstance(p, Mapping):
                try:
                    prov_list.append(DomainEventReference.from_dict(dict(p)))
                except (
                    DomainEventSerializationError,
                    DomainContractValidationError,
                ) as exc:
                    raise DomainEventSerializationError(
                        exc.message,
                        field="provenance",
                        details={"index": i, **dict(getattr(exc, "details", {}))},
                    ) from None
            else:
                raise DomainEventSerializationError(
                    f"Invalid provenance item[{i}], got {type(p).__name__}",
                    field="provenance",
                    details={"index": i},
                )

        # Permissions
        raw_perm = data.get("permissions", ())
        if isinstance(raw_perm, (str, bytes, set, frozenset)) or not isinstance(
            raw_perm, (list, tuple, Sequence)
        ):
            raise DomainEventSerializationError(
                "permissions must be a sequence of strings, not a scalar",
                field="permissions",
            )
        for i, p in enumerate(raw_perm):
            if not isinstance(p, str) or not p.strip():
                raise DomainEventSerializationError(
                    f"permissions[{i}] must be a non-empty string, got {type(p).__name__}",
                    field="permissions",
                    details={"index": i},
                )
            try:
                _validate_event_string_privacy(p.strip(), f"permissions[{i}]")
            except DomainContractValidationError as exc:
                raise DomainEventSerializationError(
                    exc.message,
                    field="permissions",
                    details={"index": i, **dict(exc.details)},
                ) from None

        # Optional identifiers (session_id, correlation_id, causation_id)
        session_id = _validate_optional_str_from_dict(
            data.get("session_id"), "session_id"
        )
        correlation_id = _validate_optional_str_from_dict(
            data.get("correlation_id"), "correlation_id"
        )
        causation_id = _validate_optional_str_from_dict(
            data.get("causation_id"), "causation_id"
        )

        # Payload & Metadata type checks
        raw_payload = data.get("payload", {})
        if raw_payload is not None and not isinstance(raw_payload, Mapping):
            raise DomainEventSerializationError(
                f"payload must be a mapping, got {type(raw_payload).__name__}",
                field="payload",
            )

        raw_meta = data.get("metadata", {})
        if raw_meta is not None and not isinstance(raw_meta, Mapping):
            raise DomainEventSerializationError(
                f"metadata must be a mapping, got {type(raw_meta).__name__}",
                field="metadata",
            )

        # DateTime
        occurred_at = _parse_datetime_event(data["occurred_at"], "occurred_at")

        return cls(
            event_id=raw_id,
            event_type=raw_type,
            schema_version=raw_ver,
            domain_id=domain_id,
            related_domain_ids=tuple(rel_list),
            actor=raw_actor,
            session_id=session_id,
            occurred_at=occurred_at,
            provenance=tuple(prov_list),
            sensitivity=raw_sens,
            permissions=tuple(raw_perm),
            correlation_id=correlation_id,
            causation_id=causation_id,
            payload=raw_payload,
            metadata=raw_meta,
        )
