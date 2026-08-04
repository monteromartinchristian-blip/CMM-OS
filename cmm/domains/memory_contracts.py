"""Phase 10.18 — Domain Memory Integration Contracts.

Immutable, deterministic reference-only models, enums, privacy guards, canonical serialization,
and validation results for domain memory integration.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from types import MappingProxyType
from typing import Any, TypeVar

from cmm.domains.errors import (
    DomainMemoryContractError,
    DomainMemoryPrivacyError,
    DomainMemorySerializationError,
    DomainSerializationError,
)
from cmm.domains.identifiers import DomainId

T = TypeVar("T")

_ID_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_.:-]{0,191}$")
_MAX_METADATA_DEPTH = 4
_MAX_METADATA_ITEMS = 32
_MAX_METADATA_SEQUENCE_ITEMS = 64
_MAX_METADATA_STRING_LENGTH = 128
_DIGEST_PREFIX_LENGTH = 12

_CANONICAL_INVALIDATION_REASONS = frozenset(
    {
        "EXPIRED",
        "SUPERSEDED",
        "OUTDATED",
        "CORRUPTED",
        "USER_REQUEST",
        "CONTRADICTED",
        "PRIVACY_REDACTION",
        "WRONG_DOMAIN",
        "POLICY_EXCLUSION",
        "REF_INVALIDATED",
        "ADMINISTRATIVE",
        "INTERNAL_REASON",
        "expired",
        "superseded",
        "outdated",
        "corrupted",
        "user_request",
        "contradicted",
        "privacy_redaction",
        "wrong_domain",
        "policy_exclusion",
        "ref_invalidated",
        "administrative",
        "internal_reason",
    }
)


def _validate_invalidation_reason(val: Any) -> str:
    if not isinstance(val, str) or isinstance(val, bool):
        raise DomainMemoryContractError(
            "invalidation_reason must be a string", field="invalidation_reason"
        )
    if _contains_private_marker(val):
        raise DomainMemoryPrivacyError(
            "invalidation_reason cannot contain private markers or PII",
            field="invalidation_reason",
        )
    if val in _CANONICAL_INVALIDATION_REASONS or _ID_PREFIX_PATTERN.match(val):
        return val
    raise DomainMemoryContractError(
        "invalidation_reason must be a closed vocabulary code or canonical prefixed reference",
        field="invalidation_reason",
    )


def _validate_superseded_by(val: Any) -> str:
    if not isinstance(val, str) or isinstance(val, bool):
        raise DomainMemoryContractError(
            "superseded_by must be a string", field="superseded_by"
        )
    if _contains_private_marker(val):
        raise DomainMemoryPrivacyError(
            "superseded_by cannot contain private markers or PII",
            field="superseded_by",
        )
    if not _ID_PREFIX_PATTERN.match(val):
        raise DomainMemoryContractError(
            "superseded_by must be a canonical prefixed reference (e.g. ref:...)",
            field="superseded_by",
        )
    return val


_MISSING = object()


def _validate_collection_from_dict(
    data: dict[str, Any],
    field_name: str,
    elem_parser: Callable[[Any], T] | None = None,
) -> tuple[T, ...]:
    if field_name not in data:
        return ()
    val = data[field_name]
    if type(val) is not list:
        raise DomainMemorySerializationError(
            f"{field_name} must be a list", field=field_name
        )
    if elem_parser is not None:
        return tuple(elem_parser(item) for item in val)
    return tuple(val)


def _validate_collection_constructor(
    val: Any,
    field_name: str,
    elem_parser: Callable[[Any], T] | None = None,
) -> tuple[T, ...]:
    if val is _MISSING:
        return ()
    if type(val) is not tuple:
        raise DomainMemoryContractError(
            f"{field_name} must be a tuple", field=field_name
        )
    if elem_parser is not None:
        return tuple(elem_parser(item) for item in val)
    return val


def _parse_json_dict_item(
    item: Any,
    field_name: str,
    parser_func: Callable[[dict[str, Any]], T],
) -> T:
    if type(item) is not dict:
        raise DomainMemorySerializationError(
            f"{field_name} element must be a JSON object (dict)", field=field_name
        )
    return parser_func(item)
_MAX_METADATA_ITEMS = 32
_MAX_METADATA_SEQUENCE_ITEMS = 64
_MAX_METADATA_STRING_LENGTH = 128
_DIGEST_PREFIX_LENGTH = 12

_SAFE_METADATA_KEYS = frozenset(
    {
        "category",
        "scope",
        "version",
        "tags",
        "domain",
        "status",
        "reasoningtraceid",
        "knowledgepackageid",
        "providerauditid",
        "crossdomaintraceid",
    }
)

_PRIVATE_MARKERS = frozenset(
    {
        "prompt",
        "systemprompt",
        "developerprompt",
        "usermessage",
        "message",
        "content",
        "rawcontent",
        "claimtext",
        "claim",
        "payload",
        "payloads",
        "rawpayload",
        "resourcecontent",
        "secret",
        "secrets",
        "token",
        "tokens",
        "credential",
        "credentials",
        "password",
        "passwords",
        "apikey",
        "chainofthought",
        "reasoning",
        "rawreasoning",
        "reasoningtext",
        "toolarguments",
        "toolresponse",
        "providerrequest",
        "providerresponse",
        "pii",
    }
)

_PRIVATE_KEY_TOKENS = frozenset(
    {
        "prompt",
        "message",
        "content",
        "claim",
        "payload",
        "secret",
        "token",
        "credential",
        "password",
        "apikey",
        "reasoning",
        "pii",
        "tool",
        "provider",
    }
)

_PRIVATE_TOKEN_SEQUENCES = (
    ("prompt",),
    ("user", "message"),
    ("content",),
    ("claim", "text"),
    ("claim",),
    ("payload",),
    ("secret",),
    ("token",),
    ("credential",),
    ("password",),
    ("api", "key"),
    ("chain", "of", "thought"),
    ("reasoning", "text"),
    ("raw", "reasoning"),
    ("raw", "resource"),
    ("resource", "content"),
    ("tool", "arguments"),
    ("tool", "response"),
    ("provider", "request"),
    ("provider", "response"),
)

# Metadata vocabulary - closed sets per key
_STRUCTURAL_CATEGORY_VALUES = frozenset(
    {"vital_stats", "laboratory", "medication", "diagnosis", "lifestyle", "goal"}
)
_STRUCTURAL_STATUS_VALUES = frozenset({"draft", "active", "archived", "superseded"})
_STRUCTURAL_PRIORITY_VALUES = frozenset({"low", "medium", "high", "critical"})
_STRUCTURAL_TAG_VALUES = frozenset({"temporal", "epistemic", "provenance", "actionable"})
_STRUCTURAL_SOURCE_TYPE_VALUES = frozenset({"manual", "automated", "imported", "derived"})
_STRUCTURAL_DOMAIN_TAG_VALUES = frozenset({"health", "fitness", "education", "finance", "career"})

# Allowed metadata keys and their value validators
_ALLOWED_METADATA_KEYS = frozenset(
    {"category", "status", "tag", "priority", "source_type", "domain_tag"}
)
_METADATA_VOCABULARIES: dict[str, frozenset[str]] = {
    "category": _STRUCTURAL_CATEGORY_VALUES,
    "status": _STRUCTURAL_STATUS_VALUES,
    "tag": _STRUCTURAL_TAG_VALUES,
    "priority": _STRUCTURAL_PRIORITY_VALUES,
    "source_type": _STRUCTURAL_SOURCE_TYPE_VALUES,
    "domain_tag": _STRUCTURAL_DOMAIN_TAG_VALUES,
}

_ID_PREFIX_PATTERN = re.compile(r"^[a-z][a-z0-9_]*:[A-Za-z0-9_.:-]+$")


def _normalized(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())


def _word_tokens(value: str) -> tuple[str, ...]:
    separated = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1 \2", value)
    separated = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", separated)
    return tuple(item for item in re.split(r"[^A-Za-z0-9]+", separated.lower()) if item)


def _contains_private_marker(value: str) -> bool:
    norm = _normalized(value)
    if norm in _SAFE_METADATA_KEYS:
        return False
    norm_stem = norm.rstrip("s")
    if norm in _PRIVATE_MARKERS or norm_stem in _PRIVATE_MARKERS:
        return True
    tokens = _word_tokens(value)
    if any(
        t in _PRIVATE_KEY_TOKENS or t.rstrip("s") in _PRIVATE_KEY_TOKENS for t in tokens
    ):
        return True
    return any(
        tokens[idx : idx + len(seq)] == seq
        for seq in _PRIVATE_TOKEN_SEQUENCES
        for idx in range(len(tokens) - len(seq) + 1)
    )


def _validate_id(val: Any, field_name: str) -> str:
    if not isinstance(val, str) or isinstance(val, bool):
        raise DomainMemoryContractError(
            f"{field_name} must be a string", field=field_name
        )
    if not _ID_RE.fullmatch(val):
        raise DomainMemoryContractError(
            f"{field_name} violates canonical ID syntax", field=field_name
        )
    return val


def _parse_domain_id(val: Any) -> DomainId:
    if isinstance(val, DomainId):
        return val
    if isinstance(val, str) and not isinstance(val, bool):
        if val.startswith("domain:"):
            try:
                return DomainId.from_str(val)
            except Exception as exc:
                raise DomainMemoryContractError(
                    "Invalid domain string"
                ) from exc
        try:
            return DomainId(slug=val)
        except Exception as exc:
            raise DomainMemoryContractError("Invalid domain slug") from exc
    raise DomainMemoryContractError("domain_id must be a DomainId or str")


def _is_plain_id_string(val: str) -> bool:
    """True for canonical *_id strings like ref:1, item:100, ev:abc."""
    return bool(_ID_PREFIX_PATTERN.match(val))


def _validate_metadata_value(key: str, val: str) -> None:
    """Validate a metadata value against the closed vocabulary scheme."""
    vocab = _METADATA_VOCABULARIES.get(key)
    if vocab is not None:
        if val not in vocab:
            raise DomainMemoryPrivacyError(
                "Metadata value not in closed vocabulary"
            )
        return

    # Fallback: must be a canonical ID string (prefix:rest)
    if not _is_plain_id_string(val):
        raise DomainMemoryPrivacyError(
            "Metadata value must be a canonical ID or closed vocabulary token"
        )


def _validate_and_freeze_metadata(
    meta: Any, depth: int = 1
) -> MappingProxyType[str, Any]:
    if depth > _MAX_METADATA_DEPTH:
        raise DomainMemoryPrivacyError("Metadata exceeds maximum allowed depth")

    if not isinstance(meta, (dict, MappingProxyType, Mapping)):
        raise DomainMemoryContractError("Metadata must be a dictionary or mapping")

    if len(meta) > _MAX_METADATA_ITEMS:
        raise DomainMemoryPrivacyError("Metadata exceeds maximum allowed items")

    frozen: dict[str, Any] = {}
    for key, val in meta.items():
        if not isinstance(key, str) or isinstance(key, bool):
            raise DomainMemoryContractError("Metadata keys must be strings")

        if key not in _ALLOWED_METADATA_KEYS:
            raise DomainMemoryPrivacyError(
                "Unrecognized structural metadata key"
            )

        if _contains_private_marker(key):
            raise DomainMemoryPrivacyError(
                "Metadata key contains forbidden private marker"
            )

        frozen[key] = _validate_and_freeze_value(val, depth=depth + 1, meta_key=key)

    return MappingProxyType(frozen)


def _validate_and_freeze_value(val: Any, depth: int, meta_key: str | None = None) -> Any:
    if depth > _MAX_METADATA_DEPTH:
        raise DomainMemoryPrivacyError("Metadata exceeds maximum allowed depth")

    if val is None or isinstance(val, bool):
        raise DomainMemoryContractError(
            "Metadata values cannot be None or boolean"
        )

    if isinstance(val, int):
        if val < 0 or val > 1_000_000:
            raise DomainMemoryPrivacyError("Metadata integer out of range")
        return val

    if isinstance(val, float):
        if not math.isfinite(val):
            raise DomainMemoryContractError("Metadata float values must be finite")
        return val

    if isinstance(val, str):
        if len(val) > _MAX_METADATA_STRING_LENGTH:
            raise DomainMemoryPrivacyError("Metadata string value exceeds length limit")
        if _contains_private_marker(val):
            raise DomainMemoryPrivacyError(
                "Metadata string value contains forbidden private marker"
            )
        # Validate against closed vocabulary for this key
        if meta_key is not None:
            _validate_metadata_value(meta_key, val)
        return val

    if isinstance(val, (dict, MappingProxyType, Mapping)):
        return _validate_and_freeze_metadata(val, depth=depth)

    if isinstance(val, (list, tuple)):
        if len(val) > _MAX_METADATA_SEQUENCE_ITEMS:
            raise DomainMemoryPrivacyError("Metadata sequence exceeds maximum length")
        return tuple(
            _validate_and_freeze_value(elem, depth=depth + 1, meta_key=meta_key)
            for elem in val
        )

    raise DomainMemoryContractError(
        f"Unsupported metadata value type: {type(val).__name__}"
    )


def _thaw_json_value(obj: Any) -> Any:
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, DomainId):
        return str(obj)
    if isinstance(obj, MappingProxyType):
        return {k: _thaw_json_value(v) for k, v in sorted(obj.items())}
    if isinstance(obj, dict):
        return {k: _thaw_json_value(v) for k, v in sorted(obj.items())}
    if isinstance(obj, (tuple, list, set, frozenset)):
        return [_thaw_json_value(v) for v in obj]
    if hasattr(obj, "to_dict"):
        return _thaw_json_value(obj.to_dict())
    return obj


def _canonical_json(data: Any) -> str:
    return json.dumps(
        _thaw_json_value(data), sort_keys=True, separators=(",", ":"), allow_nan=False
    )


def _sha256_digest(data: Any) -> str:
    return hashlib.sha256(_canonical_json(data).encode("utf-8")).hexdigest()


def _digest_prefix(data: Any) -> str:
    return _sha256_digest(data)[:_DIGEST_PREFIX_LENGTH]


class DomainMemoryCapability(str, Enum):
    """Closed enum of canonical domain memory capabilities."""

    READ = "READ"
    PROPOSE = "PROPOSE"
    APPROVE = "APPROVE"
    APPLY = "APPLY"
    INVALIDATE = "INVALIDATE"
    DELETE = "DELETE"

    @property
    def is_write_capability(self) -> bool:
        return self in (
            DomainMemoryCapability.PROPOSE,
            DomainMemoryCapability.APPROVE,
            DomainMemoryCapability.APPLY,
            DomainMemoryCapability.INVALIDATE,
            DomainMemoryCapability.DELETE,
        )


class DomainMemorySensitivityLevel(str, Enum):
    """Closed enum of canonical sensitivity levels."""

    NORMAL = "NORMAL"
    RESTRICTED = "RESTRICTED"
    SECRET = "SECRET"
    HIGH = "HIGH"


class DomainMemoryProposalKind(str, Enum):
    """Closed enum of proposal kinds."""

    MEMORY_UPDATE = "memory_update"
    AGENT_KNOWLEDGE_UPDATE = "agent_knowledge_update"


class DomainMemoryReferenceKind(str, Enum):
    """Closed enum for canonical reference kinds."""

    KNOWLEDGE_ITEM = "knowledge_item"
    KNOWLEDGE_RELATION = "knowledge_relation"
    EVIDENCE = "evidence"
    RESOURCE = "resource"
    CONTRADICTION = "contradiction"
    VERSION = "version"
    RESOLUTION_MEMORY_ENTRY = "resolution_memory_entry"
    KNOWLEDGE_PACKAGE = "knowledge_package"


class DomainMemoryTemporalKind(str, Enum):
    """Closed enum mirroring cmm.cognitive.TemporalScopeKind for reference-only snapshots."""

    UNKNOWN = "unknown"
    TIMELESS = "timeless"
    POINT_IN_TIME = "point_in_time"
    INTERVAL = "interval"
    SAFETY = "safety"


class DomainMemorySelectionDecisionCode(str, Enum):
    """Closed enum for memory selection decision outcomes."""

    SELECTED = "selected"
    EXCLUDED_DOMAIN_INAPPLICABLE = "excluded_domain_inapplicable"
    EXCLUDED_PERMISSION_DENIED = "excluded_permission_denied"
    EXCLUDED_PERMISSION_MISSING = "excluded_permission_missing"
    EXCLUDED_PERMISSION_UNSCOPED = "excluded_permission_unscoped"
    EXCLUDED_SENSITIVITY_RESTRICTED = "excluded_sensitivity_restricted"
    EXCLUDED_TEMPORAL_INVALID = "excluded_temporal_invalid"
    EXCLUDED_TEMPORAL_UNKNOWN = "excluded_temporal_unknown"
    EXCLUDED_TEMPORAL_EXPIRED = "excluded_temporal_expired"
    EXCLUDED_SUPERSEDED = "excluded_superseded"
    EXCLUDED_DUPLICATE = "excluded_duplicate"
    EXCLUDED_UNSUPPORTED_KIND = "excluded_unsupported_kind"
    EXCLUDED_PROVENANCE_MISSING = "excluded_provenance_missing"
    EXCLUDED_EVIDENCE_MISSING = "excluded_evidence_missing"
    EXCLUDED_CONFIRMATION_REQUIRED = "excluded_confirmation_required"
    EXCLUDED_ORDERING_UNKNOWN = "excluded_ordering_unknown"
    EXCLUDED_PRESERVED_CONFLICT = "excluded_preserved_conflict"
    EXCLUDED_MISSING_REFERENCE = "excluded_missing_reference"
    EXCLUDED_REFERENCE_MISMATCH = "excluded_reference_mismatch"
    EXCLUDED_INVALIDATED = "excluded_invalidated"


class DomainMemoryValidationCode(str, Enum):
    """Closed enum for integration validation codes."""

    VALID = "valid"
    INVALID_REFERENCE_INTEGRITY = "invalid_reference_integrity"
    INVALID_PRIVACY_BREACH = "invalid_privacy_breach"
    INVALID_PERMISSION_DENIED = "invalid_permission_denied"
    INVALID_PERMISSION_UNSCOPED = "invalid_permission_unscoped"
    INVALID_APPROVAL_REQUIRED = "invalid_approval_required"
    INVALID_APPROVAL_COVERAGE_MISMATCH = "invalid_approval_coverage_mismatch"
    INVALID_PROVENANCE_MISSING = "invalid_provenance_missing"
    INVALID_EVIDENCE_MISSING = "invalid_evidence_missing"
    INVALID_TEMPORAL_INVARIANT = "invalid_temporal_invariant"
    INVALID_VERSION_INVARIANT = "invalid_version_invariant"
    INVALID_PROPOSAL_COVERAGE = "invalid_proposal_coverage"
    INVALID_PROPOSAL_KIND_MISMATCH = "invalid_proposal_kind_mismatch"
    INVALID_DUPLICATE_PROPOSAL_CLASSIFICATION = "invalid_duplicate_proposal_classification"
    INVALID_TRACE_VIEW_MISMATCH = "invalid_trace_view_mismatch"
    INVALID_DIGEST_TAMPERED = "invalid_digest_tampered"
    INVALID_MISSING_REFERENCE = "invalid_missing_reference"
    INVALID_REFERENCE_MISMATCH = "invalid_reference_mismatch"
    INVALID_STRUCTURE = "invalid_structure"


@dataclass(frozen=True)
class DomainMemoryTemporalSnapshot:
    """Frozen reference-only snapshot of a cmm.cognitive.TemporalScope.

    Mirrors the canonical temporal contract from cmm.cognitive.knowledge.TemporalScope
    without duplicating the temporal engine. All values are stored as ISO-8601 strings
    or primitive reference types; no datetime objects are created here.
    """

    kind: DomainMemoryTemporalKind = DomainMemoryTemporalKind.UNKNOWN
    observed_at: str | None = None
    valid_from: str | None = None
    valid_to: str | None = None
    expires_at: str | None = None
    last_verified_at: str | None = None
    invalidated: bool = False
    invalidation_reason: str | None = None
    superseded_by: str | None = None

    def __post_init__(self) -> None:
        if isinstance(self.kind, str) and not isinstance(self.kind, DomainMemoryTemporalKind):
            try:
                object.__setattr__(
                    self, "kind", DomainMemoryTemporalKind(self.kind)
                )
            except ValueError:
                raise DomainMemoryContractError(
                    "Invalid temporal kind"
                )
        elif not isinstance(self.kind, DomainMemoryTemporalKind):
            raise DomainMemoryContractError(
                "kind must be a DomainMemoryTemporalKind"
            )

        # Validate ISO-8601 strings
        for field_name in (
            "observed_at",
            "valid_from",
            "valid_to",
            "expires_at",
            "last_verified_at",
        ):
            val = getattr(self, field_name)
            if val is not None:
                _validate_iso_datetime(val, field_name)

        if not isinstance(self.invalidated, bool):
            raise DomainMemoryContractError("invalidated must be a boolean")

        if self.invalidation_reason is not None:
            _validate_invalidation_reason(self.invalidation_reason)

        if self.invalidated and (
            self.invalidation_reason is None or not self.invalidation_reason.strip()
        ):
            raise DomainMemoryContractError(
                "invalidated=True requires invalidation_reason"
            )

        if self.superseded_by is not None:
            _validate_superseded_by(self.superseded_by)

        if (
            self.valid_from is not None
            and self.valid_to is not None
        ):
            from_dt = datetime.fromisoformat(self.valid_from.replace("Z", "+00:00"))
            to_dt = datetime.fromisoformat(self.valid_to.replace("Z", "+00:00"))
            if to_dt < from_dt:
                raise DomainMemoryContractError(
                    "valid_to cannot be before valid_from"
                )

    @property
    def is_current(self) -> bool:
        """Reference-only current status: not invalidated and has valid interval."""
        if self.invalidated:
            return False
        if self.kind == DomainMemoryTemporalKind.INTERVAL:
            return self.valid_from is not None and self.valid_to is not None
        return self.kind == DomainMemoryTemporalKind.TIMELESS

    @property
    def id(self) -> str:
        return self.digest

    @property
    def digest(self) -> str:
        return _sha256_digest(self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        return _thaw_json_value(
            {
                "kind": self.kind.value,
                "observed_at": self.observed_at,
                "valid_from": self.valid_from,
                "valid_to": self.valid_to,
                "expires_at": self.expires_at,
                "last_verified_at": self.last_verified_at,
                "invalidated": self.invalidated,
                "invalidation_reason": self.invalidation_reason,
                "superseded_by": self.superseded_by,
            }
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DomainMemoryTemporalSnapshot:
        if not isinstance(data, dict):
            raise DomainMemorySerializationError(
                "invalid DomainMemoryTemporalSnapshot payload", field="data"
            )
        known = {
            "kind",
            "observed_at",
            "valid_from",
            "valid_to",
            "expires_at",
            "last_verified_at",
            "invalidated",
            "invalidation_reason",
            "superseded_by",
        }
        if set(data.keys()) - known:
            raise DomainMemorySerializationError(
                "invalid DomainMemoryTemporalSnapshot payload", field="data"
            )
        try:
            return cls(
                kind=data.get("kind", DomainMemoryTemporalKind.UNKNOWN.value),
                observed_at=data.get("observed_at"),
                valid_from=data.get("valid_from"),
                valid_to=data.get("valid_to"),
                expires_at=data.get("expires_at"),
                last_verified_at=data.get("last_verified_at"),
                invalidated=data.get("invalidated", False),
                invalidation_reason=data.get("invalidation_reason"),
                superseded_by=data.get("superseded_by"),
            )
        except (
            KeyError,
            TypeError,
            ValueError,
            DomainMemoryContractError,
            DomainMemoryPrivacyError,
            DomainSerializationError,
        ) as exc:
            raise DomainMemorySerializationError(
                "invalid DomainMemoryTemporalSnapshot payload", field="data"
            ) from exc


def _validate_iso_datetime(val: str, field_name: str) -> None:
    """Validate that a string is a canonical ISO-8601 datetime."""
    if not isinstance(val, str) or isinstance(val, bool):
        raise DomainMemoryContractError(
            f"{field_name} must be an ISO-8601 string"
        )
    try:
        dt = datetime.fromisoformat(val.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            raise DomainMemoryContractError(
                f"{field_name} must be timezone-aware"
            )
    except (ValueError, TypeError):
        raise DomainMemoryContractError(
            f"{field_name} must be a valid ISO-8601 string"
        )


@dataclass(frozen=True)
class DomainMemoryPermissionDecisionSnapshot:
    """Frozen reference-only snapshot of a domain permission decision."""

    decision_id: str
    allowed: bool
    capabilities: tuple[DomainMemoryCapability, ...] = ()
    source_domain_id: DomainId | None = None
    target_domain_id: DomainId | None = None
    sensitivity_levels: tuple[DomainMemorySensitivityLevel, ...] = ()

    def __post_init__(self) -> None:
        _validate_id(self.decision_id, "decision_id")
        if not isinstance(self.allowed, bool):
            raise DomainMemoryContractError("allowed must be a boolean")

        caps: list[DomainMemoryCapability] = []
        raw_caps = _validate_collection_constructor(
            self.capabilities, "capabilities"
        )
        caps: list[DomainMemoryCapability] = []
        for c in raw_caps:
            if isinstance(c, DomainMemoryCapability):
                caps.append(c)
            elif isinstance(c, str) and not isinstance(c, bool):
                try:
                    caps.append(DomainMemoryCapability(c))
                except ValueError:
                    raise DomainMemoryContractError("Invalid capability")
            else:
                raise DomainMemoryContractError("Invalid capability element")
        sorted_caps = tuple(sorted(set(caps), key=lambda x: x.value))
        object.__setattr__(self, "capabilities", sorted_caps)

        if self.source_domain_id is not None:
            if isinstance(self.source_domain_id, str) and not self.source_domain_id.strip():
                raise DomainMemoryContractError("source_domain_id cannot be empty")
            object.__setattr__(
                self, "source_domain_id", _parse_domain_id(self.source_domain_id)
            )
        if self.target_domain_id is not None:
            if isinstance(self.target_domain_id, str) and not self.target_domain_id.strip():
                raise DomainMemoryContractError("target_domain_id cannot be empty")
            object.__setattr__(
                self, "target_domain_id", _parse_domain_id(self.target_domain_id)
            )

        raw_sens = _validate_collection_constructor(
            self.sensitivity_levels, "sensitivity_levels"
        )
        sens: list[DomainMemorySensitivityLevel] = []
        for s in raw_sens:
            if isinstance(s, DomainMemorySensitivityLevel):
                sens.append(s)
            elif isinstance(s, str) and not isinstance(s, bool):
                try:
                    sens.append(DomainMemorySensitivityLevel(s))
                except ValueError:
                    raise DomainMemoryContractError("Invalid sensitivity level")
            else:
                raise DomainMemoryContractError("Invalid sensitivity level element")
        sorted_sens = tuple(sorted(set(sens), key=lambda x: x.value))
        object.__setattr__(self, "sensitivity_levels", sorted_sens)

    @property
    def id(self) -> str:
        return self.decision_id

    @property
    def digest(self) -> str:
        return _sha256_digest(self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        return _thaw_json_value(
            {
                "decision_id": self.decision_id,
                "allowed": self.allowed,
                "capabilities": [c.value for c in self.capabilities],
                "source_domain_id": (
                    str(self.source_domain_id) if self.source_domain_id else None
                ),
                "target_domain_id": (
                    str(self.target_domain_id) if self.target_domain_id else None
                ),
                "sensitivity_levels": [s.value for s in self.sensitivity_levels],
            }
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DomainMemoryPermissionDecisionSnapshot:
        if not isinstance(data, dict):
            raise DomainMemorySerializationError(
                "invalid DomainMemoryPermissionDecisionSnapshot payload", field="data"
            )
        known = {
            "decision_id",
            "allowed",
            "capabilities",
            "source_domain_id",
            "target_domain_id",
            "sensitivity_levels",
        }
        if set(data.keys()) - known:
            raise DomainMemorySerializationError(
                "invalid DomainMemoryPermissionDecisionSnapshot payload", field="data"
            )
        try:
            caps_raw = _validate_collection_from_dict(data, "capabilities")
            sens_raw = _validate_collection_from_dict(data, "sensitivity_levels")

            src_dom = data.get("source_domain_id")
            tgt_dom = data.get("target_domain_id")

            return cls(
                decision_id=data["decision_id"],
                allowed=data["allowed"],
                capabilities=tuple(caps_raw),
                source_domain_id=(
                    _parse_domain_id(src_dom)
                    if src_dom is not None
                    else None
                ),
                target_domain_id=(
                    _parse_domain_id(tgt_dom)
                    if tgt_dom is not None
                    else None
                ),
                sensitivity_levels=tuple(sens_raw),
            )
        except (
            KeyError,
            TypeError,
            ValueError,
            DomainMemoryContractError,
            DomainMemoryPrivacyError,
            DomainSerializationError,
        ) as exc:
            raise DomainMemorySerializationError(
                "invalid DomainMemoryPermissionDecisionSnapshot payload", field="data"
            ) from exc


@dataclass(frozen=True)
class DomainMemoryProposalSnapshot:
    """Frozen reference-only snapshot of a memory or agent knowledge proposal.

    Defecto 1 fix: requires at least one explicit write capability.
    READ is never allowed in required_capabilities.
    """

    proposal_id: str
    proposal_kind: DomainMemoryProposalKind
    affected_reference_ids: tuple[str, ...] = ()
    required_capabilities: tuple[DomainMemoryCapability, ...] = ()
    requires_confirmation: bool = False

    def __post_init__(self) -> None:
        _validate_id(self.proposal_id, "proposal_id")

        if isinstance(self.proposal_kind, DomainMemoryProposalKind):
            pass
        elif isinstance(self.proposal_kind, str) and not isinstance(
            self.proposal_kind, bool
        ):
            try:
                object.__setattr__(
                    self,
                    "proposal_kind",
                    DomainMemoryProposalKind(self.proposal_kind),
                )
            except ValueError:
                raise DomainMemoryContractError(
                    "Invalid proposal_kind"
                )
        else:
            raise DomainMemoryContractError(
                "proposal_kind must be a DomainMemoryProposalKind enum or string"
            )

        raw_aff = _validate_collection_constructor(
            self.affected_reference_ids, "affected_reference_ids"
        )
        aff = tuple(
            sorted(
                {
                    _validate_id(i, "affected_reference_ids element")
                    for i in raw_aff
                }
            )
        )
        object.__setattr__(self, "affected_reference_ids", aff)

        raw_caps = _validate_collection_constructor(
            self.required_capabilities, "required_capabilities"
        )
        caps: list[DomainMemoryCapability] = []
        for c in raw_caps:
            if isinstance(c, DomainMemoryCapability):
                caps.append(c)
            elif isinstance(c, str) and not isinstance(c, bool):
                try:
                    caps.append(DomainMemoryCapability(c))
                except ValueError:
                    raise DomainMemoryContractError(
                        "Invalid required capability"
                    )
            else:
                raise DomainMemoryContractError(
                    "Invalid required capability element"
                )

        # Defecto 1: at least one capability required, READ never allowed
        if not caps:
            raise DomainMemoryContractError(
                "At least one required capability must be specified"
            )
        for cap in caps:
            if not cap.is_write_capability:
                raise DomainMemoryContractError(
                    "READ cannot be a required capability for proposals"
                )

        sorted_caps = tuple(sorted(set(caps), key=lambda x: x.value))
        object.__setattr__(self, "required_capabilities", sorted_caps)

        if not isinstance(self.requires_confirmation, bool):
            raise DomainMemoryContractError("requires_confirmation must be a boolean")

    @property
    def id(self) -> str:
        return self.proposal_id

    @property
    def digest(self) -> str:
        return _sha256_digest(self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        return _thaw_json_value(
            {
                "proposal_id": self.proposal_id,
                "proposal_kind": self.proposal_kind.value,
                "affected_reference_ids": list(self.affected_reference_ids),
                "required_capabilities": [c.value for c in self.required_capabilities],
                "requires_confirmation": self.requires_confirmation,
            }
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DomainMemoryProposalSnapshot:
        if not isinstance(data, dict):
            raise DomainMemorySerializationError(
                "invalid DomainMemoryProposalSnapshot payload", field="data"
            )
        known = {
            "proposal_id",
            "proposal_kind",
            "affected_reference_ids",
            "required_capabilities",
            "requires_confirmation",
        }
        if set(data.keys()) - known:
            raise DomainMemorySerializationError(
                "invalid DomainMemoryProposalSnapshot payload", field="data"
            )
        try:
            aff_raw = _validate_collection_from_dict(data, "affected_reference_ids")
            caps_raw = _validate_collection_from_dict(data, "required_capabilities")
            return cls(
                proposal_id=data["proposal_id"],
                proposal_kind=data["proposal_kind"],
                affected_reference_ids=tuple(aff_raw),
                required_capabilities=tuple(caps_raw),
                requires_confirmation=data.get("requires_confirmation", False),
            )
        except (
            KeyError,
            TypeError,
            ValueError,
            DomainMemoryContractError,
            DomainMemoryPrivacyError,
            DomainSerializationError,
        ) as exc:
            raise DomainMemorySerializationError(
                "invalid DomainMemoryProposalSnapshot payload", field="data"
            ) from exc


@dataclass(frozen=True)
class DomainMemoryApprovalRequestSnapshot:
    """Frozen reference-only snapshot of an approval request."""

    request_id: str
    proposal_id: str

    def __post_init__(self) -> None:
        _validate_id(self.request_id, "request_id")
        _validate_id(self.proposal_id, "proposal_id")

    @property
    def id(self) -> str:
        return self.request_id

    @property
    def digest(self) -> str:
        return _sha256_digest(self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        return _thaw_json_value(
            {
                "request_id": self.request_id,
                "proposal_id": self.proposal_id,
            }
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DomainMemoryApprovalRequestSnapshot:
        if not isinstance(data, dict):
            raise DomainMemorySerializationError(
                "invalid DomainMemoryApprovalRequestSnapshot payload", field="data"
            )
        known = {"request_id", "proposal_id"}
        if set(data.keys()) - known:
            raise DomainMemorySerializationError(
                "invalid DomainMemoryApprovalRequestSnapshot payload", field="data"
            )
        try:
            return cls(
                request_id=data["request_id"],
                proposal_id=data["proposal_id"],
            )
        except (
            KeyError,
            TypeError,
            ValueError,
            DomainMemoryContractError,
            DomainMemoryPrivacyError,
            DomainSerializationError,
        ) as exc:
            raise DomainMemorySerializationError(
                "invalid DomainMemoryApprovalRequestSnapshot payload", field="data"
            ) from exc


@dataclass(frozen=True)
class DomainMemoryApprovalDecisionSnapshot:
    """Frozen reference-only snapshot of an approval decision."""

    decision_id: str
    request_id: str
    approved: bool

    def __post_init__(self) -> None:
        _validate_id(self.decision_id, "decision_id")
        _validate_id(self.request_id, "request_id")
        if not isinstance(self.approved, bool):
            raise DomainMemoryContractError("approved must be a boolean")

    @property
    def id(self) -> str:
        return self.decision_id

    @property
    def digest(self) -> str:
        return _sha256_digest(self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        return _thaw_json_value(
            {
                "decision_id": self.decision_id,
                "request_id": self.request_id,
                "approved": self.approved,
            }
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DomainMemoryApprovalDecisionSnapshot:
        if not isinstance(data, dict):
            raise DomainMemorySerializationError(
                "invalid DomainMemoryApprovalDecisionSnapshot payload", field="data"
            )
        known = {"decision_id", "request_id", "approved"}
        if set(data.keys()) - known:
            raise DomainMemorySerializationError(
                "invalid DomainMemoryApprovalDecisionSnapshot payload", field="data"
            )
        try:
            return cls(
                decision_id=data["decision_id"],
                request_id=data["request_id"],
                approved=data["approved"],
            )
        except (
            KeyError,
            TypeError,
            ValueError,
            DomainMemoryContractError,
            DomainMemoryPrivacyError,
            DomainSerializationError,
        ) as exc:
            raise DomainMemorySerializationError(
                "invalid DomainMemoryApprovalDecisionSnapshot payload", field="data"
            ) from exc


@dataclass(frozen=True)
class DomainMemoryTraceSnapshot:
    """Frozen reference-only snapshot of a reasoning trace."""

    trace_id: str
    primary_domain: DomainId

    def __post_init__(self) -> None:
        _validate_id(self.trace_id, "trace_id")
        object.__setattr__(
            self, "primary_domain", _parse_domain_id(self.primary_domain)
        )

    @property
    def id(self) -> str:
        return self.trace_id

    @property
    def digest(self) -> str:
        return _sha256_digest(self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        return _thaw_json_value(
            {
                "trace_id": self.trace_id,
                "primary_domain": str(self.primary_domain),
            }
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DomainMemoryTraceSnapshot:
        if not isinstance(data, dict):
            raise DomainMemorySerializationError(
                "invalid DomainMemoryTraceSnapshot payload", field="data"
            )
        known = {"trace_id", "primary_domain"}
        if set(data.keys()) - known:
            raise DomainMemorySerializationError(
                "invalid DomainMemoryTraceSnapshot payload", field="data"
            )
        try:
            return cls(
                trace_id=data["trace_id"],
                primary_domain=_parse_domain_id(data["primary_domain"]),
            )
        except (
            KeyError,
            TypeError,
            ValueError,
            DomainMemoryContractError,
            DomainMemoryPrivacyError,
            DomainSerializationError,
        ) as exc:
            raise DomainMemorySerializationError(
                "invalid DomainMemoryTraceSnapshot payload", field="data"
            ) from exc


@dataclass(frozen=True)
class DomainMemoryViewSnapshot:
    """Frozen reference-only snapshot of a domain memory view.

    Defecto 2 fix: view_id includes a canonical digest prefix, and view_digest
    is validated in __post_init__.
    """

    view_id: str
    request_id: str
    primary_domain: DomainId
    trace_id: str | None = None
    view_digest: str = ""

    def __post_init__(self) -> None:
        _validate_id(self.view_id, "view_id")
        _validate_id(self.request_id, "request_id")

        if (
            not isinstance(self.view_digest, str)
            or len(self.view_digest) != 64
            or any(
                character not in "0123456789abcdef"
                for character in self.view_digest
            )
        ):
            raise DomainMemoryContractError(
                "view_digest must be a full SHA-256 hex digest",
                field="view_digest",
            )

        expected_prefix = f"view:{self.request_id}:"
        if not self.view_id.startswith(expected_prefix):
            raise DomainMemoryContractError(
                "view_id must follow canonical format view:<request_id>:<digest>",
                field="view_id",
            )

        suffix = self.view_id[len(expected_prefix):]
        if suffix != self.view_digest[:_DIGEST_PREFIX_LENGTH]:
            raise DomainMemoryContractError(
                "view_id suffix must match view_digest prefix",
                field="view_id",
            )

        object.__setattr__(
            self, "primary_domain", _parse_domain_id(self.primary_domain)
        )
        if self.trace_id is not None:
            _validate_id(self.trace_id, "trace_id")

    @property
    def id(self) -> str:
        return self.view_id

    @property
    def digest(self) -> str:
        return _sha256_digest(self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        return _thaw_json_value(
            {
                "view_id": self.view_id,
                "request_id": self.request_id,
                "primary_domain": str(self.primary_domain),
                "trace_id": self.trace_id,
                "view_digest": self.view_digest,
            }
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DomainMemoryViewSnapshot:
        if not isinstance(data, dict):
            raise DomainMemorySerializationError(
                "invalid DomainMemoryViewSnapshot payload", field="data"
            )
        known = {"view_id", "request_id", "primary_domain", "trace_id", "view_digest"}
        if set(data.keys()) - known:
            raise DomainMemorySerializationError(
                "invalid DomainMemoryViewSnapshot payload", field="data"
            )
        try:
            return cls(
                view_id=data["view_id"],
                request_id=data["request_id"],
                primary_domain=_parse_domain_id(data["primary_domain"]),
                trace_id=data.get("trace_id"),
                view_digest=data.get("view_digest", ""),
            )
        except (
            KeyError,
            TypeError,
            ValueError,
            DomainMemoryContractError,
            DomainMemoryPrivacyError,
            DomainSerializationError,
        ) as exc:
            raise DomainMemorySerializationError(
                "invalid DomainMemoryViewSnapshot payload", field="data"
            ) from exc


@dataclass(frozen=True)
class DomainMemoryReference:
    """Immutable, payload-free reference descriptor for a memory item."""

    reference_id: str
    kind: DomainMemoryReferenceKind
    canonical_id: str
    domain_id: DomainId
    applicable_domains: tuple[DomainId, ...] = ()
    sensitivity_level: str | DomainMemorySensitivityLevel | None = None
    version: int | None = None
    superseded_by_id: str | None = None
    evidence_ids: tuple[str, ...] = ()
    resource_ids: tuple[str, ...] = ()
    has_unresolved_conflict: bool = False
    has_unknown_ordering: bool = False
    temporal: DomainMemoryTemporalSnapshot | None = None
    metadata: MappingProxyType[str, Any] = field(
        default_factory=lambda: _validate_and_freeze_metadata({})
    )

    def __post_init__(self) -> None:
        _validate_id(self.reference_id, "reference_id")
        _validate_id(self.canonical_id, "canonical_id")

        if not isinstance(self.kind, DomainMemoryReferenceKind):
            if isinstance(self.kind, str):
                try:
                    object.__setattr__(
                        self, "kind", DomainMemoryReferenceKind(self.kind)
                    )
                except ValueError:
                    raise DomainMemoryContractError("Invalid kind")
            else:
                raise DomainMemoryContractError(
                    "kind must be a DomainMemoryReferenceKind enum"
                )

        object.__setattr__(self, "domain_id", _parse_domain_id(self.domain_id))

        raw_app = _validate_collection_constructor(
            self.applicable_domains, "applicable_domains"
        )
        app_doms: list[DomainId] = []
        for d in raw_app:
            app_doms.append(_parse_domain_id(d))
        unique_app = sorted(set(app_doms), key=lambda x: str(x))
        object.__setattr__(self, "applicable_domains", tuple(unique_app))

        if self.sensitivity_level is not None:
            if isinstance(self.sensitivity_level, DomainMemorySensitivityLevel):
                object.__setattr__(
                    self, "sensitivity_level", self.sensitivity_level.value
                )
            elif isinstance(self.sensitivity_level, str) and not isinstance(
                self.sensitivity_level, bool
            ):
                try:
                    sens_enum = DomainMemorySensitivityLevel(
                        self.sensitivity_level
                    )
                    object.__setattr__(self, "sensitivity_level", sens_enum.value)
                except ValueError:
                    raise DomainMemoryContractError(
                        "Invalid sensitivity_level"
                    )
            else:
                raise DomainMemoryContractError(
                    "sensitivity_level must be a string or DomainMemorySensitivityLevel enum"
                )

        if self.version is not None and (
            not isinstance(self.version, int)
            or isinstance(self.version, bool)
            or self.version < 1
        ):
            raise DomainMemoryContractError("version must be a positive integer")

        if self.superseded_by_id is not None:
            _validate_id(self.superseded_by_id, "superseded_by_id")

        raw_ev = _validate_collection_constructor(
            self.evidence_ids, "evidence_ids"
        )
        ev_ids = tuple(
            sorted(
                {_validate_id(ev, "evidence_ids element") for ev in raw_ev}
            )
        )
        object.__setattr__(self, "evidence_ids", ev_ids)

        raw_res = _validate_collection_constructor(
            self.resource_ids, "resource_ids"
        )
        res_ids = tuple(
            sorted(
                {_validate_id(res, "resource_ids element") for res in raw_res}
            )
        )
        object.__setattr__(self, "resource_ids", res_ids)

        if not isinstance(self.has_unresolved_conflict, bool):
            raise DomainMemoryContractError("has_unresolved_conflict must be a boolean")
        if not isinstance(self.has_unknown_ordering, bool):
            raise DomainMemoryContractError("has_unknown_ordering must be a boolean")

        if self.temporal is not None:
            if isinstance(self.temporal, dict):
                object.__setattr__(
                    self, "temporal", DomainMemoryTemporalSnapshot.from_dict(self.temporal)
                )
            elif not isinstance(self.temporal, DomainMemoryTemporalSnapshot):
                raise DomainMemoryContractError(
                    "temporal must be a DomainMemoryTemporalSnapshot"
                )

        object.__setattr__(
            self, "metadata", _validate_and_freeze_metadata(dict(self.metadata))
        )

    @property
    def id(self) -> str:
        return self.reference_id

    @property
    def digest(self) -> str:
        return _sha256_digest(self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        return _thaw_json_value(
            {
                "reference_id": self.reference_id,
                "kind": self.kind.value,
                "canonical_id": self.canonical_id,
                "domain_id": str(self.domain_id),
                "applicable_domains": [str(d) for d in self.applicable_domains],
                "sensitivity_level": self.sensitivity_level,
                "version": self.version,
                "superseded_by_id": self.superseded_by_id,
                "evidence_ids": list(self.evidence_ids),
                "resource_ids": list(self.resource_ids),
                "has_unresolved_conflict": self.has_unresolved_conflict,
                "has_unknown_ordering": self.has_unknown_ordering,
                "temporal": self.temporal.to_dict() if self.temporal else None,
                "metadata": dict(self.metadata),
            }
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DomainMemoryReference:
        if not isinstance(data, dict):
            raise DomainMemorySerializationError(
                "invalid DomainMemoryReference payload", field="data"
            )

        known_fields = {
            "reference_id",
            "kind",
            "canonical_id",
            "domain_id",
            "applicable_domains",
            "sensitivity_level",
            "version",
            "superseded_by_id",
            "evidence_ids",
            "resource_ids",
            "has_unresolved_conflict",
            "has_unknown_ordering",
            "temporal",
            "metadata",
        }
        unknown = set(data.keys()) - known_fields
        if unknown:
            raise DomainMemorySerializationError(
                "invalid DomainMemoryReference payload", field="data"
            )

        try:
            temporal_data = data.get("temporal")
            temporal = None
            if "temporal" in data and temporal_data is not None:
                if type(temporal_data) is not dict:
                    raise DomainMemorySerializationError(
                        "invalid DomainMemoryReference payload", field="temporal"
                    )
                temporal = DomainMemoryTemporalSnapshot.from_dict(temporal_data)

            raw_app = _validate_collection_from_dict(data, "applicable_domains")
            raw_ev = _validate_collection_from_dict(data, "evidence_ids")
            raw_res = _validate_collection_from_dict(data, "resource_ids")

            return cls(
                reference_id=data["reference_id"],
                kind=DomainMemoryReferenceKind(data["kind"]),
                canonical_id=data["canonical_id"],
                domain_id=_parse_domain_id(data["domain_id"]),
                applicable_domains=tuple(
                    _parse_domain_id(d) for d in raw_app
                ),
                sensitivity_level=data.get("sensitivity_level"),
                version=data.get("version"),
                superseded_by_id=data.get("superseded_by_id"),
                evidence_ids=tuple(raw_ev),
                resource_ids=tuple(raw_res),
                has_unresolved_conflict=data.get("has_unresolved_conflict", False),
                has_unknown_ordering=data.get("has_unknown_ordering", False),
                temporal=temporal,
                metadata=_validate_and_freeze_metadata(data.get("metadata", {})),
            )
        except (
            KeyError,
            TypeError,
            ValueError,
            DomainMemoryContractError,
            DomainMemoryPrivacyError,
            DomainSerializationError,
        ) as exc:
            raise DomainMemorySerializationError(
                "invalid DomainMemoryReference payload", field="data"
            ) from exc


@dataclass(frozen=True)
class DomainMemoryViewRequest:
    """Immutable request for building a reference-only domain memory view.

    Defecto 3 fix: canonical_id must map to exactly one reference identity.
    Defecto 5 fix: temporal_reference field added.
    """

    request_id: str
    primary_domain: DomainId
    supporting_domains: tuple[DomainId, ...] = ()
    trace_id: str | None = None
    resolution_reference_id: str | None = None
    requested_kinds: tuple[DomainMemoryReferenceKind, ...] = ()
    candidates: tuple[DomainMemoryReference, ...] = ()
    permission_decision_ids: tuple[str, ...] = ()
    temporal_reference: str | None = None

    def __post_init__(self) -> None:
        _validate_id(self.request_id, "request_id")

        primary = _parse_domain_id(self.primary_domain)
        object.__setattr__(self, "primary_domain", primary)

        raw_supp = _validate_collection_constructor(
            self.supporting_domains, "supporting_domains"
        )
        supp: list[DomainId] = []
        for d in raw_supp:
            parsed = _parse_domain_id(d)
            if parsed == primary:
                raise DomainMemoryContractError(
                    "primary_domain cannot appear in supporting_domains",
                    field="supporting_domains",
                )
            supp.append(parsed)
        unique_supp = sorted(set(supp), key=lambda x: str(x))
        object.__setattr__(self, "supporting_domains", tuple(unique_supp))

        if self.trace_id is not None:
            _validate_id(self.trace_id, "trace_id")
        if self.resolution_reference_id is not None:
            _validate_id(self.resolution_reference_id, "resolution_reference_id")

        if self.temporal_reference is not None:
            _validate_iso_datetime(self.temporal_reference, "temporal_reference")

        raw_kinds = _validate_collection_constructor(
            self.requested_kinds, "requested_kinds"
        )
        kinds: list[DomainMemoryReferenceKind] = []
        for k in raw_kinds:
            if isinstance(k, str):
                kinds.append(DomainMemoryReferenceKind(k))
            elif isinstance(k, DomainMemoryReferenceKind):
                kinds.append(k)
            else:
                raise DomainMemoryContractError(
                    "requested_kinds element must be DomainMemoryReferenceKind"
                )
        unique_kinds = sorted(set(kinds), key=lambda x: x.value)
        object.__setattr__(self, "requested_kinds", tuple(unique_kinds))

        raw_cands = _validate_collection_constructor(
            self.candidates, "candidates"
        )
        cand_refs: list[DomainMemoryReference] = []
        seen_ref_ids: set[str] = set()
        seen_canonical_map: dict[str, DomainMemoryReference] = {}

        for c in raw_cands:
            if not isinstance(c, DomainMemoryReference):
                raise DomainMemoryContractError(
                    "candidates element must be DomainMemoryReference"
                )
            if c.reference_id in seen_ref_ids:
                raise DomainMemoryContractError(
                    "Duplicate candidate reference_id",
                    field="candidates",
                )
            seen_ref_ids.add(c.reference_id)

            # Defecto 3: strictly reject multiple reference_ids for same canonical_id
            if c.canonical_id in seen_canonical_map:
                raise DomainMemoryContractError(
                    f"Duplicate canonical_id in candidates: {c.canonical_id}",
                    field="candidates",
                )
            else:
                seen_canonical_map[c.canonical_id] = c
            cand_refs.append(c)

        sorted_cands = tuple(sorted(cand_refs, key=lambda c: c.reference_id))
        object.__setattr__(self, "candidates", sorted_cands)

        raw_perms = _validate_collection_constructor(
            self.permission_decision_ids, "permission_decision_ids"
        )
        p_ids = tuple(
            sorted(
                {
                    _validate_id(pid, "permission_decision_ids element")
                    for pid in raw_perms
                }
            )
        )
        object.__setattr__(self, "permission_decision_ids", p_ids)

    @property
    def id(self) -> str:
        return self.request_id

    @property
    def digest(self) -> str:
        return _sha256_digest(self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        return _thaw_json_value(
            {
                "request_id": self.request_id,
                "primary_domain": str(self.primary_domain),
                "supporting_domains": [str(d) for d in self.supporting_domains],
                "trace_id": self.trace_id,
                "resolution_reference_id": self.resolution_reference_id,
                "requested_kinds": [k.value for k in self.requested_kinds],
                "candidates": [c.to_dict() for c in self.candidates],
                "permission_decision_ids": list(self.permission_decision_ids),
                "temporal_reference": self.temporal_reference,
            }
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DomainMemoryViewRequest:
        if not isinstance(data, dict):
            raise DomainMemorySerializationError(
                "invalid DomainMemoryViewRequest payload", field="data"
            )

        known = {
            "request_id",
            "primary_domain",
            "supporting_domains",
            "trace_id",
            "resolution_reference_id",
            "requested_kinds",
            "candidates",
            "permission_decision_ids",
            "temporal_reference",
        }
        unknown = set(data.keys()) - known
        if unknown:
            raise DomainMemorySerializationError(
                "invalid DomainMemoryViewRequest payload", field="data"
            )

        try:
            supp_raw = _validate_collection_from_dict(data, "supporting_domains")
            kinds_raw = _validate_collection_from_dict(data, "requested_kinds")
            cands_raw = _validate_collection_from_dict(
                data,
                "candidates",
                elem_parser=lambda c: _parse_json_dict_item(
                    c, "candidates", DomainMemoryReference.from_dict
                ),
            )
            perms_raw = _validate_collection_from_dict(
                data, "permission_decision_ids"
            )

            return cls(
                request_id=data["request_id"],
                primary_domain=_parse_domain_id(data["primary_domain"]),
                supporting_domains=tuple(
                    _parse_domain_id(d) for d in supp_raw
                ),
                trace_id=data.get("trace_id"),
                resolution_reference_id=data.get("resolution_reference_id"),
                requested_kinds=tuple(
                    DomainMemoryReferenceKind(k) for k in kinds_raw
                ),
                candidates=cands_raw,
                permission_decision_ids=tuple(perms_raw),
                temporal_reference=data.get("temporal_reference"),
            )
        except (
            KeyError,
            TypeError,
            ValueError,
            DomainMemoryContractError,
            DomainMemoryPrivacyError,
            DomainSerializationError,
        ) as exc:
            raise DomainMemorySerializationError(
                "invalid DomainMemoryViewRequest payload", field="data"
            ) from exc


@dataclass(frozen=True)
class DomainMemorySelectionDecision:
    """Selection decision for a candidate reference in a memory view."""

    reference_id: str
    code: DomainMemorySelectionDecisionCode
    related_reference_ids: tuple[str, ...] = ()
    permission_decision_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _validate_id(self.reference_id, "reference_id")
        if not isinstance(self.code, DomainMemorySelectionDecisionCode):
            if isinstance(self.code, str):
                object.__setattr__(
                    self, "code", DomainMemorySelectionDecisionCode(self.code)
                )
            else:
                raise DomainMemoryContractError(
                    "code must be a DomainMemorySelectionDecisionCode"
                )

        raw_rel = _validate_collection_constructor(
            self.related_reference_ids, "related_reference_ids"
        )
        rel_ids = tuple(
            sorted(
                {
                    _validate_id(r, "related_reference_ids element")
                    for r in raw_rel
                }
            )
        )
        object.__setattr__(self, "related_reference_ids", rel_ids)

        raw_perms = _validate_collection_constructor(
            self.permission_decision_ids, "permission_decision_ids"
        )
        p_ids = tuple(
            sorted(
                {
                    _validate_id(p, "permission_decision_ids element")
                    for p in raw_perms
                }
            )
        )
        object.__setattr__(self, "permission_decision_ids", p_ids)

    def to_dict(self) -> dict[str, Any]:
        return _thaw_json_value(
            {
                "reference_id": self.reference_id,
                "code": self.code.value,
                "related_reference_ids": list(self.related_reference_ids),
                "permission_decision_ids": list(self.permission_decision_ids),
            }
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DomainMemorySelectionDecision:
        if not isinstance(data, dict):
            raise DomainMemorySerializationError(
                "invalid DomainMemorySelectionDecision payload", field="data"
            )
        known = {
            "reference_id",
            "code",
            "related_reference_ids",
            "permission_decision_ids",
        }
        if set(data.keys()) - known:
            raise DomainMemorySerializationError(
                "invalid DomainMemorySelectionDecision payload", field="data"
            )
        try:
            rel_raw = _validate_collection_from_dict(data, "related_reference_ids")
            perms_raw = _validate_collection_from_dict(
                data, "permission_decision_ids"
            )
            return cls(
                reference_id=data["reference_id"],
                code=DomainMemorySelectionDecisionCode(data["code"]),
                related_reference_ids=tuple(rel_raw),
                permission_decision_ids=tuple(perms_raw),
            )
        except (
            KeyError,
            TypeError,
            ValueError,
            DomainMemoryContractError,
            DomainMemoryPrivacyError,
            DomainSerializationError,
        ) as exc:
            raise DomainMemorySerializationError(
                "invalid DomainMemorySelectionDecision payload", field="data"
            ) from exc


@dataclass(frozen=True)
class DomainMemoryView:
    """Immutable, reference-only memory view result.

    Defecto 2 fix: view_id follows content-bound format.
    Defecto 4 fix: view_id bound to complete request content via request_digest.
    """

    view_id: str
    request_id: str
    primary_domain: DomainId
    request_digest: str
    trace_id: str | None = None
    temporal_reference: str | None = None
    selection_decisions: tuple[DomainMemorySelectionDecision, ...] = ()
    selected_references: tuple[DomainMemoryReference, ...] = ()

    def __post_init__(self) -> None:
        _validate_id(self.view_id, "view_id")
        _validate_id(self.request_id, "request_id")

        if (
            not isinstance(self.request_digest, str)
            or len(self.request_digest) != 64
            or any(c not in "0123456789abcdef" for c in self.request_digest)
        ):
            raise DomainMemoryContractError(
                "request_digest must be a full SHA-256 hex digest",
                field="request_digest",
            )

        # Content-bound view_id: view:<request_id>:<digest_prefix>
        expected_prefix = f"view:{self.request_id}:"
        if not self.view_id.startswith(expected_prefix):
            raise DomainMemoryContractError(
                "view_id must follow canonical format view:<request_id>:<digest>",
                field="view_id",
            )

        object.__setattr__(
            self, "primary_domain", _parse_domain_id(self.primary_domain)
        )

        if self.trace_id is not None:
            _validate_id(self.trace_id, "trace_id")
        if self.temporal_reference is not None:
            _validate_iso_datetime(
                self.temporal_reference,
                "temporal_reference",
            )

        selection_decisions = _validate_collection_constructor(
            self.selection_decisions, "selection_decisions"
        )
        selected_references = _validate_collection_constructor(
            self.selected_references, "selected_references"
        )

        dec_map: dict[str, DomainMemorySelectionDecision] = {}
        for d in selection_decisions:
            if not isinstance(d, DomainMemorySelectionDecision):
                raise DomainMemoryContractError(
                    "selection_decisions element must be DomainMemorySelectionDecision"
                )
            if d.reference_id in dec_map:
                raise DomainMemoryContractError(
                    f"Duplicate decision for reference_id: {d.reference_id}"
                )
            dec_map[d.reference_id] = d
        sorted_decs = tuple(sorted(dec_map.values(), key=lambda d: d.reference_id))
        object.__setattr__(self, "selection_decisions", sorted_decs)

        ref_map: dict[str, DomainMemoryReference] = {}
        for r in selected_references:
            if not isinstance(r, DomainMemoryReference):
                raise DomainMemoryContractError(
                    "selected_references element must be DomainMemoryReference"
                )
            if r.reference_id in ref_map:
                raise DomainMemoryContractError(
                    f"Duplicate selected reference_id: {r.reference_id}"
                )
            ref_map[r.reference_id] = r
        sorted_refs = tuple(sorted(ref_map.values(), key=lambda r: r.reference_id))
        object.__setattr__(self, "selected_references", sorted_refs)

        # Invariant checks between selection_decisions and selected_references
        selected_ids_from_refs = set(ref_map.keys())
        selected_ids_from_decs = {
            d.reference_id
            for d in sorted_decs
            if d.code == DomainMemorySelectionDecisionCode.SELECTED
        }
        if selected_ids_from_refs != selected_ids_from_decs:
            raise DomainMemoryContractError(
                "selected_references must exactly match candidate decisions with SELECTED code"
            )

        suffix = self.view_id[len(expected_prefix):]
        if suffix != self.content_digest[:_DIGEST_PREFIX_LENGTH]:
            raise DomainMemoryContractError(
                "view_id suffix must match content_digest prefix",
                field="view_id",
            )

    @property
    def excluded_decisions(self) -> tuple[DomainMemorySelectionDecision, ...]:
        return tuple(
            d
            for d in self.selection_decisions
            if d.code != DomainMemorySelectionDecisionCode.SELECTED
        )

    @property
    def id(self) -> str:
        return self.view_id

    @property
    def digest(self) -> str:
        return _sha256_digest(self.to_dict())

    @property
    def content_digest(self) -> str:
        """Digest of view content excluding the view_id itself."""
        payload: dict[str, Any] = {
            "request_id": self.request_id,
            "primary_domain": str(self.primary_domain),
            "request_digest": self.request_digest,
            "selection_decisions": [
                d.to_dict() for d in self.selection_decisions
            ],
            "selected_references": [
                r.to_dict() for r in self.selected_references
            ],
        }
        if self.trace_id is not None:
            payload["trace_id"] = self.trace_id
        if self.temporal_reference is not None:
            payload["temporal_reference"] = self.temporal_reference
        return _sha256_digest(payload)

    def to_dict(self) -> dict[str, Any]:
        res = {
            "view_id": self.view_id,
            "request_id": self.request_id,
            "primary_domain": str(self.primary_domain),
            "request_digest": self.request_digest,
            "selection_decisions": [d.to_dict() for d in self.selection_decisions],
            "selected_references": [r.to_dict() for r in self.selected_references],
        }
        if self.trace_id is not None:
            res["trace_id"] = self.trace_id
        if self.temporal_reference is not None:
            res["temporal_reference"] = self.temporal_reference
        return _thaw_json_value(res)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DomainMemoryView:
        if not isinstance(data, dict):
            raise DomainMemorySerializationError(
                "invalid DomainMemoryView payload", field="data"
            )
        known = {
            "view_id",
            "request_id",
            "primary_domain",
            "request_digest",
            "trace_id",
            "temporal_reference",
            "selection_decisions",
            "selected_references",
        }
        if set(data.keys()) - known:
            raise DomainMemorySerializationError(
                "invalid DomainMemoryView payload", field="data"
            )
        req_digest = data.get("request_digest")
        if req_digest is None or not isinstance(req_digest, str) or len(req_digest) != 64 or any(c not in "0123456789abcdef" for c in req_digest):
            raise DomainMemorySerializationError(
                "invalid DomainMemoryView payload", field="request_digest"
            )

        try:
            raw_decisions = _validate_collection_from_dict(
                data,
                "selection_decisions",
                elem_parser=lambda d: _parse_json_dict_item(
                    d, "selection_decisions", DomainMemorySelectionDecision.from_dict
                ),
            )
            raw_selected = _validate_collection_from_dict(
                data,
                "selected_references",
                elem_parser=lambda r: _parse_json_dict_item(
                    r, "selected_references", DomainMemoryReference.from_dict
                ),
            )
            return cls(
                view_id=data["view_id"],
                request_id=data["request_id"],
                primary_domain=_parse_domain_id(data["primary_domain"]),
                request_digest=req_digest,
                trace_id=data.get("trace_id"),
                temporal_reference=data.get("temporal_reference"),
                selection_decisions=raw_decisions,
                selected_references=raw_selected,
            )
        except (
            KeyError,
            TypeError,
            ValueError,
            DomainMemoryContractError,
            DomainMemoryPrivacyError,
            DomainSerializationError,
        ) as exc:
            raise DomainMemorySerializationError(
                "invalid DomainMemoryView payload", field="data"
            ) from exc


@dataclass(frozen=True)
class DomainMemoryProposalBinding:
    """Reference-only binding between a domain execution and existing update proposals.

    Defecto 2 fix: binding_id includes a canonical digest prefix bound to view_id.
    """

    binding_id: str
    domain_id: DomainId
    trace_id: str
    view_id: str
    view_digest: str = ""
    memory_proposal_ids: tuple[str, ...] = ()
    agent_knowledge_proposal_ids: tuple[str, ...] = ()
    affected_reference_ids: tuple[str, ...] = ()
    permission_decision_ids: tuple[str, ...] = ()
    approval_request_ids: tuple[str, ...] = ()
    approval_decision_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _validate_id(self.binding_id, "binding_id")
        _validate_id(self.trace_id, "trace_id")
        _validate_id(self.view_id, "view_id")

        if (
            not isinstance(self.view_digest, str)
            or len(self.view_digest) != 64
            or any(
                character not in "0123456789abcdef"
                for character in self.view_digest
            )
        ):
            raise DomainMemoryContractError(
                "view_digest must be a full SHA-256 hex digest",
                field="view_digest",
            )

        view_suffix = self.view_id.rsplit(":", 1)[-1]
        if view_suffix != self.view_digest[:_DIGEST_PREFIX_LENGTH]:
            raise DomainMemoryContractError(
                "view_id suffix must match view_digest prefix",
                field="view_digest",
            )

        dom_id = _parse_domain_id(self.domain_id)
        object.__setattr__(self, "domain_id", dom_id)

        # Content-bound binding_id format:
        # binding:<domain_id>:<trace_id>:<view_id>:<digest_prefix>
        expected_prefix = f"binding:{dom_id}:{self.trace_id}:{self.view_id}:"
        if not self.binding_id.startswith(expected_prefix):
            raise DomainMemoryContractError(
                "binding_id must follow canonical format "
                "binding:<domain_id>:<trace_id>:<view_id>:<digest>",
                field="binding_id",
            )

        raw_mp = _validate_collection_constructor(
            self.memory_proposal_ids, "memory_proposal_ids"
        )
        raw_akp = _validate_collection_constructor(
            self.agent_knowledge_proposal_ids, "agent_knowledge_proposal_ids"
        )

        if not raw_mp and not raw_akp:
            raise DomainMemoryContractError(
                "At least one memory or agent knowledge proposal ID must be bound"
            )

        mp_ids = tuple(
            sorted(
                {
                    _validate_id(i, "memory_proposal_ids")
                    for i in raw_mp
                }
            )
        )
        object.__setattr__(self, "memory_proposal_ids", mp_ids)

        akp_ids = tuple(
            sorted(
                {
                    _validate_id(i, "agent_knowledge_proposal_ids")
                    for i in raw_akp
                }
            )
        )
        object.__setattr__(self, "agent_knowledge_proposal_ids", akp_ids)

        if not set(mp_ids).isdisjoint(set(akp_ids)):
            raise DomainMemoryContractError(
                "memory_proposal_ids and agent_knowledge_proposal_ids must be disjoint"
            )

        raw_aff = _validate_collection_constructor(
            self.affected_reference_ids, "affected_reference_ids"
        )
        aff_ids = tuple(
            sorted(
                {
                    _validate_id(i, "affected_reference_ids")
                    for i in raw_aff
                }
            )
        )
        object.__setattr__(self, "affected_reference_ids", aff_ids)

        raw_perms = _validate_collection_constructor(
            self.permission_decision_ids, "permission_decision_ids"
        )
        perm_ids = tuple(
            sorted(
                {
                    _validate_id(i, "permission_decision_ids")
                    for i in raw_perms
                }
            )
        )
        object.__setattr__(self, "permission_decision_ids", perm_ids)

        raw_reqs = _validate_collection_constructor(
            self.approval_request_ids, "approval_request_ids"
        )
        app_reqs = tuple(
            sorted(
                {
                    _validate_id(i, "approval_request_ids")
                    for i in raw_reqs
                }
            )
        )
        object.__setattr__(self, "approval_request_ids", app_reqs)

        raw_decs = _validate_collection_constructor(
            self.approval_decision_ids, "approval_decision_ids"
        )
        app_decs = tuple(
            sorted(
                {
                    _validate_id(i, "approval_decision_ids")
                    for i in raw_decs
                }
            )
        )
        object.__setattr__(self, "approval_decision_ids", app_decs)

        suffix = self.binding_id[len(expected_prefix):]
        if suffix != self.content_digest[:_DIGEST_PREFIX_LENGTH]:
            raise DomainMemoryContractError(
                "binding_id suffix must match content_digest prefix",
                field="binding_id",
            )

    @property
    def id(self) -> str:
        return self.binding_id

    @property
    def digest(self) -> str:
        return _sha256_digest(self.to_dict())

    @property
    def content_digest(self) -> str:
        """Digest of binding content excluding the binding_id itself."""
        return _sha256_digest(
            {
                "domain_id": str(self.domain_id),
                "trace_id": self.trace_id,
                "view_id": self.view_id,
                "view_digest": self.view_digest,
                "memory_proposal_ids": list(self.memory_proposal_ids),
                "agent_knowledge_proposal_ids": list(
                    self.agent_knowledge_proposal_ids
                ),
                "affected_reference_ids": list(self.affected_reference_ids),
                "permission_decision_ids": list(self.permission_decision_ids),
                "approval_request_ids": list(self.approval_request_ids),
                "approval_decision_ids": list(self.approval_decision_ids),
            }
        )

    def to_dict(self) -> dict[str, Any]:
        return _thaw_json_value(
            {
                "binding_id": self.binding_id,
                "domain_id": str(self.domain_id),
                "trace_id": self.trace_id,
                "view_id": self.view_id,
                "view_digest": self.view_digest,
                "memory_proposal_ids": list(self.memory_proposal_ids),
                "agent_knowledge_proposal_ids": list(
                    self.agent_knowledge_proposal_ids
                ),
                "affected_reference_ids": list(self.affected_reference_ids),
                "permission_decision_ids": list(self.permission_decision_ids),
                "approval_request_ids": list(self.approval_request_ids),
                "approval_decision_ids": list(self.approval_decision_ids),
            }
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DomainMemoryProposalBinding:
        if not isinstance(data, dict):
            raise DomainMemorySerializationError(
                "invalid DomainMemoryProposalBinding payload", field="data"
            )
        known = {
            "binding_id",
            "domain_id",
            "trace_id",
            "view_id",
            "view_digest",
            "memory_proposal_ids",
            "agent_knowledge_proposal_ids",
            "affected_reference_ids",
            "permission_decision_ids",
            "approval_request_ids",
            "approval_decision_ids",
        }
        if set(data.keys()) - known:
            raise DomainMemorySerializationError(
                "invalid DomainMemoryProposalBinding payload", field="data"
            )
        try:
            raw_mp = _validate_collection_from_dict(data, "memory_proposal_ids")
            raw_akp = _validate_collection_from_dict(
                data, "agent_knowledge_proposal_ids"
            )
            raw_aff = _validate_collection_from_dict(data, "affected_reference_ids")
            raw_perms = _validate_collection_from_dict(
                data, "permission_decision_ids"
            )
            raw_reqs = _validate_collection_from_dict(data, "approval_request_ids")
            raw_decs = _validate_collection_from_dict(data, "approval_decision_ids")

            return cls(
                binding_id=data["binding_id"],
                domain_id=_parse_domain_id(data["domain_id"]),
                trace_id=data["trace_id"],
                view_id=data["view_id"],
                view_digest=data.get("view_digest", ""),
                memory_proposal_ids=tuple(raw_mp),
                agent_knowledge_proposal_ids=tuple(raw_akp),
                affected_reference_ids=tuple(raw_aff),
                permission_decision_ids=tuple(raw_perms),
                approval_request_ids=tuple(raw_reqs),
                approval_decision_ids=tuple(raw_decs),
            )
        except (
            KeyError,
            TypeError,
            ValueError,
            DomainMemoryContractError,
            DomainMemoryPrivacyError,
            DomainSerializationError,
        ) as exc:
            raise DomainMemorySerializationError(
                "invalid DomainMemoryProposalBinding payload", field="data"
            ) from exc


def _parse_inventory_item(item: Any, cls_type: type) -> Any:
    if isinstance(item, cls_type):
        return item
    if isinstance(item, (dict, MappingProxyType, Mapping)):
        return cls_type.from_dict(dict(item))
    raise DomainMemoryContractError(
        f"Inventory item must be an instance or dictionary for {cls_type.__name__}"
    )


@dataclass(frozen=True)
class DomainMemoryReferenceInventory:
    """Authoritative reference inventory supplied by caller for validator execution.

    Defecto 3 fix: rejects multiple reference_ids for same canonical_id.
    Defecto 6 fix: removes legacy alias fields.
    """

    references: tuple[DomainMemoryReference, ...] = ()
    proposals: tuple[DomainMemoryProposalSnapshot, ...] = ()
    permission_decisions: tuple[DomainMemoryPermissionDecisionSnapshot, ...] = ()
    approval_requests: tuple[DomainMemoryApprovalRequestSnapshot, ...] = ()
    approval_decisions: tuple[DomainMemoryApprovalDecisionSnapshot, ...] = ()
    traces: tuple[DomainMemoryTraceSnapshot, ...] = ()
    views: tuple[DomainMemoryViewSnapshot, ...] = ()

    def __post_init__(self) -> None:
        raw_refs = _validate_collection_constructor(
            self.references, "references"
        )
        raw_props = _validate_collection_constructor(
            self.proposals, "proposals"
        )
        raw_perms = _validate_collection_constructor(
            self.permission_decisions, "permission_decisions"
        )
        raw_app_reqs = _validate_collection_constructor(
            self.approval_requests, "approval_requests"
        )
        raw_app_decs = _validate_collection_constructor(
            self.approval_decisions, "approval_decisions"
        )
        raw_traces = _validate_collection_constructor(
            self.traces, "traces"
        )
        raw_views = _validate_collection_constructor(
            self.views, "views"
        )

        ref_map: dict[str, DomainMemoryReference] = {}
        canonical_map: dict[str, DomainMemoryReference] = {}
        for r in raw_refs:
            if not isinstance(r, DomainMemoryReference):
                raise DomainMemoryContractError(
                    "references element must be a DomainMemoryReference"
                )
            if r.reference_id in ref_map:
                existing = ref_map[r.reference_id]
                if existing != r or existing.digest != r.digest:
                    raise DomainMemoryContractError(
                        f"Conflicting duplicate reference_id: {r.reference_id}"
                    )
                raise DomainMemoryContractError(
                    f"Duplicate reference_id in inventory: {r.reference_id}"
                )

            # Defecto 3: strict canonical identity uniqueness
            if r.canonical_id in canonical_map:
                raise DomainMemoryContractError(
                    f"Duplicate canonical_id in inventory: {r.canonical_id}"
                )

            ref_map[r.reference_id] = r
            canonical_map[r.canonical_id] = r
        sorted_refs = tuple(sorted(ref_map.values(), key=lambda r: r.reference_id))
        object.__setattr__(self, "references", sorted_refs)

        prop_map: dict[str, DomainMemoryProposalSnapshot] = {}
        for p in raw_props:
            parsed_p = _parse_inventory_item(p, DomainMemoryProposalSnapshot)
            if parsed_p.proposal_id in prop_map:
                raise DomainMemoryContractError(
                    f"Duplicate proposal_id in inventory: {parsed_p.proposal_id}"
                )
            prop_map[parsed_p.proposal_id] = parsed_p
        sorted_props = tuple(sorted(prop_map.values(), key=lambda p: p.proposal_id))
        object.__setattr__(self, "proposals", sorted_props)

        perm_map: dict[str, DomainMemoryPermissionDecisionSnapshot] = {}
        for pd in raw_perms:
            parsed_pd = _parse_inventory_item(
                pd, DomainMemoryPermissionDecisionSnapshot
            )
            if parsed_pd.decision_id in perm_map:
                raise DomainMemoryContractError(
                    f"Duplicate permission decision_id in inventory: {parsed_pd.decision_id}"
                )
            perm_map[parsed_pd.decision_id] = parsed_pd
        sorted_perms = tuple(sorted(perm_map.values(), key=lambda p: p.decision_id))
        object.__setattr__(self, "permission_decisions", sorted_perms)

        app_req_map: dict[str, DomainMemoryApprovalRequestSnapshot] = {}
        for ar in raw_app_reqs:
            parsed_ar = _parse_inventory_item(
                ar, DomainMemoryApprovalRequestSnapshot
            )
            if parsed_ar.request_id in app_req_map:
                raise DomainMemoryContractError(
                    f"Duplicate approval request_id in inventory: {parsed_ar.request_id}"
                )
            app_req_map[parsed_ar.request_id] = parsed_ar
        sorted_app_reqs = tuple(
            sorted(app_req_map.values(), key=lambda a: a.request_id)
        )
        object.__setattr__(self, "approval_requests", sorted_app_reqs)

        app_dec_map: dict[str, DomainMemoryApprovalDecisionSnapshot] = {}
        for ad in raw_app_decs:
            parsed_ad = _parse_inventory_item(
                ad, DomainMemoryApprovalDecisionSnapshot
            )
            if parsed_ad.decision_id in app_dec_map:
                raise DomainMemoryContractError(
                    f"Duplicate approval decision_id in inventory: {parsed_ad.decision_id}"
                )
            app_dec_map[parsed_ad.decision_id] = parsed_ad
        sorted_app_decs = tuple(
            sorted(app_dec_map.values(), key=lambda a: a.decision_id)
        )
        object.__setattr__(self, "approval_decisions", sorted_app_decs)

        tr_map: dict[str, DomainMemoryTraceSnapshot] = {}
        for tr in raw_traces:
            parsed_tr = _parse_inventory_item(tr, DomainMemoryTraceSnapshot)
            if parsed_tr.trace_id in tr_map:
                raise DomainMemoryContractError(
                    f"Duplicate trace_id in inventory: {parsed_tr.trace_id}"
                )
            tr_map[parsed_tr.trace_id] = parsed_tr
        sorted_trs = tuple(sorted(tr_map.values(), key=lambda t: t.trace_id))
        object.__setattr__(self, "traces", sorted_trs)

        vw_map: dict[str, DomainMemoryViewSnapshot] = {}
        for vw in raw_views:
            parsed_vw = _parse_inventory_item(vw, DomainMemoryViewSnapshot)
            if parsed_vw.view_id in vw_map:
                existing = vw_map[parsed_vw.view_id]
                if parsed_vw.view_digest != existing.view_digest:
                    raise DomainMemoryContractError(
                        f"Conflicting view_digest for view_id: {parsed_vw.view_id}"
                    )
                raise DomainMemoryContractError(
                    f"Duplicate view_id in inventory: {parsed_vw.view_id}"
                )
            vw_map[parsed_vw.view_id] = parsed_vw
        sorted_vws = tuple(sorted(vw_map.values(), key=lambda v: v.view_id))
        object.__setattr__(self, "views", sorted_vws)

    @property
    def id(self) -> str:
        return _sha256_digest(self.to_dict())

    @property
    def digest(self) -> str:
        return _sha256_digest(self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        return _thaw_json_value(
            {
                "references": [r.to_dict() for r in self.references],
                "proposals": [p.to_dict() for p in self.proposals],
                "permission_decisions": [
                    pd.to_dict() for pd in self.permission_decisions
                ],
                "approval_requests": [ar.to_dict() for ar in self.approval_requests],
                "approval_decisions": [ad.to_dict() for ad in self.approval_decisions],
                "traces": [tr.to_dict() for tr in self.traces],
                "views": [vw.to_dict() for vw in self.views],
            }
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DomainMemoryReferenceInventory:
        if not isinstance(data, dict):
            raise DomainMemorySerializationError(
                "invalid DomainMemoryReferenceInventory payload", field="data"
            )
        known = {
            "references",
            "proposals",
            "permission_decisions",
            "approval_requests",
            "approval_decisions",
            "traces",
            "views",
        }
        unknown = set(data.keys()) - known
        if unknown:
            # Defecto 6: reject legacy alias fields explicitly
            raise DomainMemorySerializationError(
                "invalid DomainMemoryReferenceInventory payload", field="data"
            )
        try:
            refs = _validate_collection_from_dict(
                data,
                "references",
                elem_parser=lambda r: _parse_json_dict_item(
                    r, "references", DomainMemoryReference.from_dict
                ),
            )
            props = _validate_collection_from_dict(
                data,
                "proposals",
                elem_parser=lambda p: _parse_json_dict_item(
                    p, "proposals", DomainMemoryProposalSnapshot.from_dict
                ),
            )
            perms = _validate_collection_from_dict(
                data,
                "permission_decisions",
                elem_parser=lambda pd: _parse_json_dict_item(
                    pd, "permission_decisions", DomainMemoryPermissionDecisionSnapshot.from_dict
                ),
            )
            app_reqs = _validate_collection_from_dict(
                data,
                "approval_requests",
                elem_parser=lambda ar: _parse_json_dict_item(
                    ar, "approval_requests", DomainMemoryApprovalRequestSnapshot.from_dict
                ),
            )
            app_decs = _validate_collection_from_dict(
                data,
                "approval_decisions",
                elem_parser=lambda ad: _parse_json_dict_item(
                    ad, "approval_decisions", DomainMemoryApprovalDecisionSnapshot.from_dict
                ),
            )
            traces = _validate_collection_from_dict(
                data,
                "traces",
                elem_parser=lambda tr: _parse_json_dict_item(
                    tr, "traces", DomainMemoryTraceSnapshot.from_dict
                ),
            )
            views = _validate_collection_from_dict(
                data,
                "views",
                elem_parser=lambda vw: _parse_json_dict_item(
                    vw, "views", DomainMemoryViewSnapshot.from_dict
                ),
            )

            return cls(
                references=refs,
                proposals=props,
                permission_decisions=perms,
                approval_requests=app_reqs,
                approval_decisions=app_decs,
                traces=traces,
                views=views,
            )
        except (
            KeyError,
            TypeError,
            ValueError,
            DomainMemoryContractError,
            DomainMemoryPrivacyError,
            DomainSerializationError,
        ) as exc:
            raise DomainMemorySerializationError(
                "invalid DomainMemoryReferenceInventory payload", field="data"
            ) from exc


@dataclass(frozen=True)
class DomainMemoryValidationResult:
    """Validation outcome for a domain memory view or proposal binding."""

    is_valid: bool
    code: DomainMemoryValidationCode
    codes: tuple[DomainMemoryValidationCode, ...] = ()
    affected_reference_ids: tuple[str, ...] = ()
    affected_object_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.is_valid, bool):
            raise DomainMemoryContractError("is_valid must be a boolean")
        if not isinstance(self.code, DomainMemoryValidationCode):
            if isinstance(self.code, str):
                object.__setattr__(self, "code", DomainMemoryValidationCode(self.code))
            else:
                raise DomainMemoryContractError(
                    "code must be DomainMemoryValidationCode"
                )

        raw_codes = _validate_collection_constructor(
            self.codes, "codes"
        )
        parsed_codes: list[DomainMemoryValidationCode] = []
        for c in raw_codes:
            if isinstance(c, str):
                parsed_codes.append(DomainMemoryValidationCode(c))
            elif isinstance(c, DomainMemoryValidationCode):
                parsed_codes.append(c)
            else:
                raise DomainMemoryContractError(
                    "codes element must be DomainMemoryValidationCode"
                )
        if self.code not in parsed_codes:
            parsed_codes.append(self.code)
        object.__setattr__(
            self, "codes", tuple(sorted(set(parsed_codes), key=lambda x: x.value))
        )

        raw_aff_ref = _validate_collection_constructor(
            self.affected_reference_ids, "affected_reference_ids"
        )
        aff_ref = tuple(
            sorted(
                {
                    _validate_id(r, "affected_reference_ids element")
                    for r in raw_aff_ref
                }
            )
        )
        object.__setattr__(self, "affected_reference_ids", aff_ref)

        raw_aff_obj = _validate_collection_constructor(
            self.affected_object_ids, "affected_object_ids"
        )
        aff_obj = tuple(
            sorted(
                {
                    _validate_id(o, "affected_object_ids element")
                    for o in raw_aff_obj
                }
            )
        )
        object.__setattr__(self, "affected_object_ids", aff_obj)

        if self.is_valid:
            if self.code != DomainMemoryValidationCode.VALID:
                raise DomainMemoryContractError("is_valid=True requires code=VALID")
            if self.codes != (DomainMemoryValidationCode.VALID,):
                raise DomainMemoryContractError(
                    "is_valid=True requires codes=(VALID,)"
                )
        else:
            if self.code == DomainMemoryValidationCode.VALID:
                raise DomainMemoryContractError(
                    "is_valid=False requires non-VALID code"
                )

    @property
    def diagnostics(self) -> tuple[str, ...]:
        """Sanitized reference-only summary codes."""
        return tuple(f"{c.value}" for c in self.codes)

    def to_dict(self) -> dict[str, Any]:
        return _thaw_json_value(
            {
                "is_valid": self.is_valid,
                "code": self.code.value,
                "codes": [c.value for c in self.codes],
                "affected_reference_ids": list(self.affected_reference_ids),
                "affected_object_ids": list(self.affected_object_ids),
            }
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DomainMemoryValidationResult:
        if not isinstance(data, dict):
            raise DomainMemorySerializationError(
                "invalid DomainMemoryValidationResult payload", field="data"
            )
        known = {
            "is_valid",
            "code",
            "codes",
            "affected_reference_ids",
            "affected_object_ids",
        }
        # Defecto 6: reject diagnostics field - it's not a valid input field
        if set(data.keys()) - known:
            raise DomainMemorySerializationError(
                "invalid DomainMemoryValidationResult payload", field="data"
            )
        try:
            raw_codes = _validate_collection_from_dict(data, "codes")
            raw_aff_ref = _validate_collection_from_dict(
                data, "affected_reference_ids"
            )
            raw_aff_obj = _validate_collection_from_dict(
                data, "affected_object_ids"
            )

            return cls(
                is_valid=data["is_valid"],
                code=DomainMemoryValidationCode(data["code"]),
                codes=tuple(
                    DomainMemoryValidationCode(c) for c in raw_codes
                ),
                affected_reference_ids=tuple(raw_aff_ref),
                affected_object_ids=tuple(raw_aff_obj),
            )
        except (
            KeyError,
            TypeError,
            ValueError,
            DomainMemoryContractError,
            DomainMemoryPrivacyError,
            DomainSerializationError,
        ) as exc:
            raise DomainMemorySerializationError(
                "invalid DomainMemoryValidationResult payload", field="data"
            ) from exc