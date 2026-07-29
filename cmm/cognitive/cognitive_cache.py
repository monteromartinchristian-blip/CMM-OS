"""Phase 8.24 – Cognitive Cache.

Stores structured, traceable cognitive artifacts — materialized knowledge,
verified summaries, structured reasoning results, document analyses, detected
contradictions, resolved questions, cognitive plans, validated conclusions,
Knowledge Packages, and other reusable intermediate results — so previously
verified cognitive work can be reused without being treated as permanently
valid or independent from the context that produced it.

This module caches cognitive artifacts, never provider prompts, tokens, or
raw model payloads. Provider prompt caching, token-prefix reuse, and
cache-hit billing belong to Phase 11.42. Structural validation-pipeline
integration belongs to Phase 8.26.

Phase 8.25 adds an optional `PrivacyMetadata` (see `cmm.cognitive.privacy`)
to `CognitiveCacheEntry` alongside the pre-existing `sensitivity`/
`permissions` fields, which are kept for compatibility. `sensitivity`/
`permissions` still gate reuse in `CognitiveCache._permission_denied`;
`privacy` additionally governs whether an entry may be stored at all
(`allow_cache`) and whether it may be reused in a remote processing context
(`LOCAL_ONLY` policy).
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from threading import RLock
from types import MappingProxyType
from typing import Any, Protocol, runtime_checkable

from cmm.cognitive.enums import ResourcePermissionOperation, SensitivityLevel
from cmm.cognitive.errors import (
    CognitiveCacheConflictError,
    CognitiveCacheNotFoundError,
    InvalidCognitiveCacheEntryError,
    InvalidPrivacyMetadataError,
)
from cmm.cognitive.knowledge_packages import KnowledgePackage
from cmm.cognitive.privacy import (
    PrivacyMetadata,
    PrivacyPolicy,
    ProcessingLocation,
    privacy_from_knowledge_package,
    resolve_effective_privacy_metadata,
)
from cmm.cognitive.resources import ResourcePermission

COGNITIVE_CACHE_SCHEMA_VERSION = 1

Clock = Callable[[], datetime]

# Explicit, deliberate sensitivity hierarchy for this module. Declared here
# rather than derived from ``enumerate(SensitivityLevel)`` so a future
# reordering or extension of the enum in ``enums.py`` (which does not itself
# promise to be a formal hierarchy) cannot silently change cache authorization
# semantics.
_SENSITIVITY_HIERARCHY: tuple[SensitivityLevel, ...] = (
    SensitivityLevel.PUBLIC,
    SensitivityLevel.INTERNAL,
    SensitivityLevel.PERSONAL,
    SensitivityLevel.SENSITIVE,
    SensitivityLevel.HIGHLY_SENSITIVE,
    SensitivityLevel.RESTRICTED,
)
_SENSITIVITY_RANK: Mapping[SensitivityLevel, int] = {
    level: index for index, level in enumerate(_SENSITIVITY_HIERARCHY)
}
# Highest sensitivity reusable without any explicit clearance.
_SAFE_WITHOUT_CLEARANCE_RANK = _SENSITIVITY_RANK[SensitivityLevel.PUBLIC]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _require_aware(value: datetime | None, name: str) -> None:
    if value is not None and (
        not isinstance(value, datetime) or value.tzinfo is None
    ):
        raise InvalidCognitiveCacheEntryError(f"{name} must be timezone-aware")


def _jsonable(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    if hasattr(value, "to_dict") and callable(value.to_dict):
        return _jsonable(value.to_dict())
    if isinstance(value, Mapping):
        return {str(key): _jsonable(value[key]) for key in sorted(value, key=str)}
    if isinstance(value, (tuple, list)):
        return [_jsonable(item) for item in value]
    if isinstance(value, (set, frozenset)):
        return [_jsonable(item) for item in sorted(value, key=str)]
    return value


def _freeze(value: Any) -> Any:
    """Recursively freeze nested containers so no mutable object is aliased."""
    if isinstance(value, Mapping):
        return MappingProxyType({str(key): _freeze(value[key]) for key in value})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    if isinstance(value, (set, frozenset)):
        return frozenset(_freeze(item) for item in value)
    return value


def _ensure_json_serializable(value: Any, name: str) -> None:
    try:
        json.dumps(_jsonable(value))
    except (TypeError, ValueError) as exc:
        raise InvalidCognitiveCacheEntryError(
            f"{name} must be JSON-serializable"
        ) from exc


def _unique_ids(values: Sequence[Any], name: str) -> tuple[str, ...]:
    result = tuple(str(item) for item in values)
    if len(result) != len(set(result)):
        raise InvalidCognitiveCacheEntryError(f"{name} must not contain duplicate ids")
    return result


class CognitiveCacheEntryStatus(str, Enum):
    """Reusability status of a cached cognitive artifact."""

    VALID = "valid"
    STALE = "stale"
    INVALID = "invalid"
    EXPIRED = "expired"


class CognitiveCacheLookupStatus(str, Enum):
    """Outcome of a cache lookup, distinguishing every non-reusable case."""

    MISS = "miss"
    HIT_REUSABLE = "hit_reusable"
    HIT_STALE = "hit_stale"
    HIT_EXPIRED = "hit_expired"
    HIT_INVALID = "hit_invalid"
    CONTEXT_MISMATCH = "context_mismatch"
    PERMISSION_DENIED = "permission_denied"
    REVALIDATION_REQUIRED = "revalidation_required"


def build_cognitive_cache_context_signature(
    *,
    objective: str | None = None,
    profile_version: str | None = None,
    domain_version: str | None = None,
    session_scope: str | None = None,
    permissions: Sequence[str] = (),
    sensitivity: SensitivityLevel | str | None = None,
    temporal_scope: Mapping[str, Any] | None = None,
    schema_versions: Mapping[str, int] | None = None,
    dependency_ids: Sequence[str] = (),
    cognitive_params: Mapping[str, Any] | None = None,
) -> str:
    """Build a deterministic, provider-independent cognitive context signature.

    Only semantically relevant context is hashed (objective, versions, scope,
    permissions, sensitivity, temporal scope, dependency ids, cognitive
    parameters). No random UUIDs or ephemeral timestamps are included, so two
    semantically equivalent contexts always produce the same signature.
    """
    sensitivity_value = (
        sensitivity.value if isinstance(sensitivity, SensitivityLevel) else sensitivity
    )
    payload = {
        "objective": " ".join((objective or "").casefold().split()),
        "profile_version": profile_version,
        "domain_version": domain_version,
        "session_scope": session_scope,
        "permissions": sorted(str(item) for item in permissions),
        "sensitivity": sensitivity_value,
        "temporal_scope": _jsonable(dict(temporal_scope or {})),
        "schema_versions": _jsonable(dict(schema_versions or {})),
        "dependency_ids": sorted(str(item) for item in dependency_ids),
        "cognitive_params": _jsonable(dict(cognitive_params or {})),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return f"sha256:{hashlib.sha256(encoded.encode('utf-8')).hexdigest()}"


def cognitive_cache_entry_id(key: str, context_signature: str) -> str:
    """Deterministic cache entry id derived from the logical key and context."""
    if not isinstance(key, str) or not key.strip():
        raise InvalidCognitiveCacheEntryError("key must be a non-empty string")
    if not isinstance(context_signature, str) or not context_signature.strip():
        raise InvalidCognitiveCacheEntryError(
            "context_signature must be a non-empty string"
        )
    encoded = json.dumps(
        {"key": key, "context_signature": context_signature}, sort_keys=True
    )
    digest = hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:24]
    return f"cognitive-cache:{digest}"


def _coerce_permissions(value: Any) -> tuple[ResourcePermission, ...]:
    result: list[ResourcePermission] = []
    for item in value or ():
        if isinstance(item, ResourcePermission):
            result.append(item)
        elif isinstance(item, Mapping):
            result.append(
                ResourcePermission(
                    allowed_actor_ids=tuple(
                        str(v) for v in item.get("allowed_actor_ids", ())
                    ),
                    allowed_domains=tuple(
                        str(v) for v in item.get("allowed_domains", ())
                    ),
                    allowed_operations=tuple(
                        ResourcePermissionOperation(v)
                        for v in item.get(
                            "allowed_operations",
                            (ResourcePermissionOperation.READ.value,),
                        )
                    ),
                    expires_at=(
                        datetime.fromisoformat(item["expires_at"])
                        if item.get("expires_at")
                        else None
                    ),
                    metadata=dict(item.get("metadata", {})),
                )
            )
        else:
            raise InvalidCognitiveCacheEntryError(
                "permissions must contain ResourcePermission values"
            )
    return tuple(result)


@dataclass(frozen=True, slots=True)
class CognitiveCacheEntry:
    """Immutable, traceable record of one reusable cognitive artifact."""

    id: str
    key: str
    kind: str
    value: Mapping[str, Any]
    context_signature: str
    profile_version: str | None = None
    domain_version: str | None = None
    source_ids: tuple[str, ...] = ()
    dependency_ids: tuple[str, ...] = ()
    process_metadata: Mapping[str, Any] = field(default_factory=dict)
    confidence: float = 1.0
    created_at: datetime = field(default_factory=_utc_now)
    last_validated_at: datetime = field(default_factory=_utc_now)
    updated_at: datetime | None = None
    invalidated_at: datetime | None = None
    valid_until: datetime | None = None
    invalidation_keys: tuple[str, ...] = ()
    sensitivity: SensitivityLevel = SensitivityLevel.INTERNAL
    permissions: tuple[ResourcePermission, ...] = ()
    privacy: PrivacyMetadata | None = None
    provenance: tuple[str, ...] = ()
    status: CognitiveCacheEntryStatus = CognitiveCacheEntryStatus.VALID
    metadata: Mapping[str, Any] = field(default_factory=dict)
    schema_version: int = COGNITIVE_CACHE_SCHEMA_VERSION
    audit_log: tuple[Mapping[str, Any], ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or not self.id.strip():
            raise InvalidCognitiveCacheEntryError("id must not be empty")
        if not isinstance(self.key, str) or not self.key.strip():
            raise InvalidCognitiveCacheEntryError("key must not be empty")
        if not isinstance(self.kind, str) or not self.kind.strip():
            raise InvalidCognitiveCacheEntryError("kind must not be empty")
        if (
            not isinstance(self.context_signature, str)
            or not self.context_signature.strip()
        ):
            raise InvalidCognitiveCacheEntryError("context_signature must not be empty")
        if self.schema_version != COGNITIVE_CACHE_SCHEMA_VERSION:
            raise InvalidCognitiveCacheEntryError(
                f"Unsupported CognitiveCacheEntry schema_version: {self.schema_version}"
            )

        status = self.status
        if isinstance(status, str):
            try:
                status = CognitiveCacheEntryStatus(status)
            except ValueError as exc:
                raise InvalidCognitiveCacheEntryError(
                    f"Invalid status: {status}"
                ) from exc
        elif not isinstance(status, CognitiveCacheEntryStatus):
            raise InvalidCognitiveCacheEntryError(f"Invalid status: {status}")
        object.__setattr__(self, "status", status)

        sensitivity = self.sensitivity
        if isinstance(sensitivity, str):
            try:
                sensitivity = SensitivityLevel(sensitivity)
            except ValueError as exc:
                raise InvalidCognitiveCacheEntryError(
                    f"Invalid sensitivity: {sensitivity}"
                ) from exc
        elif not isinstance(sensitivity, SensitivityLevel):
            raise InvalidCognitiveCacheEntryError(f"Invalid sensitivity: {sensitivity}")
        object.__setattr__(self, "sensitivity", sensitivity)

        privacy = self.privacy
        if privacy is not None:
            try:
                if isinstance(privacy, Mapping):
                    privacy = PrivacyMetadata.from_mapping(privacy)
                elif not isinstance(privacy, PrivacyMetadata):
                    raise InvalidCognitiveCacheEntryError(
                        f"Invalid privacy: {privacy!r}"
                    )
            except InvalidPrivacyMetadataError as exc:
                raise InvalidCognitiveCacheEntryError(f"Invalid privacy: {exc}") from exc
            object.__setattr__(self, "privacy", privacy)

        for name in (
            "created_at",
            "last_validated_at",
            "updated_at",
            "invalidated_at",
            "valid_until",
        ):
            _require_aware(getattr(self, name), name)
        if not isinstance(self.created_at, datetime):
            raise InvalidCognitiveCacheEntryError("created_at must be a datetime")
        if not isinstance(self.last_validated_at, datetime):
            raise InvalidCognitiveCacheEntryError("last_validated_at must be a datetime")
        if self.last_validated_at < self.created_at:
            raise InvalidCognitiveCacheEntryError(
                "last_validated_at must not precede created_at"
            )
        if self.valid_until is not None and self.valid_until < self.created_at:
            raise InvalidCognitiveCacheEntryError(
                "valid_until must not precede created_at"
            )
        if self.updated_at is None:
            object.__setattr__(self, "updated_at", self.created_at)
        elif self.updated_at < self.created_at:
            raise InvalidCognitiveCacheEntryError(
                "updated_at must not precede created_at"
            )
        if self.invalidated_at is not None and self.invalidated_at < self.created_at:
            raise InvalidCognitiveCacheEntryError(
                "invalidated_at must not precede created_at"
            )

        object.__setattr__(
            self, "source_ids", _unique_ids(self.source_ids, "source_ids")
        )
        object.__setattr__(
            self, "dependency_ids", _unique_ids(self.dependency_ids, "dependency_ids")
        )
        object.__setattr__(
            self,
            "invalidation_keys",
            _unique_ids(self.invalidation_keys, "invalidation_keys"),
        )
        object.__setattr__(
            self, "provenance", tuple(str(item) for item in self.provenance or ())
        )

        if (
            isinstance(self.confidence, bool)
            or not isinstance(self.confidence, (int, float))
            or not (0.0 <= float(self.confidence) <= 1.0)
        ):
            raise InvalidCognitiveCacheEntryError(
                f"confidence must be between 0.0 and 1.0, got {self.confidence}"
            )
        object.__setattr__(self, "confidence", float(self.confidence))

        permissions = _coerce_permissions(self.permissions)
        object.__setattr__(self, "permissions", permissions)

        _ensure_json_serializable(self.value, "value")
        _ensure_json_serializable(self.process_metadata, "process_metadata")
        _ensure_json_serializable(self.metadata, "metadata")
        for record in self.audit_log or ():
            if not isinstance(record, Mapping):
                raise InvalidCognitiveCacheEntryError(
                    "audit_log entries must be mappings"
                )
        object.__setattr__(self, "value", _freeze(self.value))
        object.__setattr__(self, "process_metadata", _freeze(self.process_metadata))
        object.__setattr__(self, "metadata", _freeze(self.metadata))
        object.__setattr__(
            self, "audit_log", tuple(_freeze(record) for record in self.audit_log or ())
        )

    def _transition(
        self,
        status: CognitiveCacheEntryStatus,
        reason: str | None,
        *,
        at: datetime,
        touch_last_validated: bool,
    ) -> CognitiveCacheEntry:
        _require_aware(at, "at")
        if at < self.created_at:
            raise InvalidCognitiveCacheEntryError(
                "transition timestamp must not precede created_at"
            )
        record = {
            "event": "revalidated" if touch_last_validated else "invalidated",
            "from": self.status.value,
            "to": status.value,
            "reason": reason,
            "at": at.isoformat(),
        }
        changes: dict[str, Any] = {
            "status": status,
            "updated_at": at,
            "audit_log": self.audit_log + (record,),
        }
        if touch_last_validated:
            changes["last_validated_at"] = at
        else:
            changes["invalidated_at"] = at
        return dataclasses.replace(self, **changes)

    def _with_invalidation(
        self, status: CognitiveCacheEntryStatus, reason: str | None, *, at: datetime
    ) -> CognitiveCacheEntry:
        """Mark a status change that is NOT a revalidation: `last_validated_at` is untouched."""
        return self._transition(status, reason, at=at, touch_last_validated=False)

    def _with_revalidation(
        self, status: CognitiveCacheEntryStatus, reason: str | None, *, at: datetime
    ) -> CognitiveCacheEntry:
        """Mark a genuine revalidation: `last_validated_at` advances to `at`."""
        return self._transition(status, reason, at=at, touch_last_validated=True)

    def serialize(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "id": self.id,
            "key": self.key,
            "kind": self.kind,
            "value": _jsonable(dict(self.value)),
            "source_ids": list(self.source_ids),
            "dependency_ids": list(self.dependency_ids),
            "context_signature": self.context_signature,
            "profile_version": self.profile_version,
            "domain_version": self.domain_version,
            "process_metadata": _jsonable(dict(self.process_metadata)),
            "confidence": self.confidence,
            "created_at": self.created_at.isoformat(),
            "last_validated_at": self.last_validated_at.isoformat(),
            "updated_at": (
                self.updated_at.isoformat() if self.updated_at is not None else None
            ),
            "invalidated_at": (
                self.invalidated_at.isoformat() if self.invalidated_at is not None else None
            ),
            "valid_until": (
                self.valid_until.isoformat() if self.valid_until is not None else None
            ),
            "invalidation_keys": list(self.invalidation_keys),
            "sensitivity": self.sensitivity.value,
            "permissions": [permission.to_dict() for permission in self.permissions],
            "privacy": self.privacy.to_dict() if self.privacy is not None else None,
            "provenance": list(self.provenance),
            "status": self.status.value,
            "metadata": _jsonable(dict(self.metadata)),
            "audit_log": [_jsonable(dict(record)) for record in self.audit_log],
        }

    def to_dict(self) -> dict[str, Any]:
        return self.serialize()

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> CognitiveCacheEntry:
        if not isinstance(payload, Mapping):
            raise InvalidCognitiveCacheEntryError("payload must be a mapping")

        def parse_dt(value: Any, *, default: datetime | None = None) -> datetime | None:
            if value is None:
                return default
            if isinstance(value, datetime):
                return value
            if isinstance(value, str):
                try:
                    return datetime.fromisoformat(value)
                except ValueError as exc:
                    raise InvalidCognitiveCacheEntryError(
                        "invalid ISO timestamp"
                    ) from exc
            raise InvalidCognitiveCacheEntryError("datetime value is invalid")

        created_at = parse_dt(payload.get("created_at"), default=_utc_now()) or _utc_now()
        return cls(
            id=payload.get("id", ""),
            key=payload.get("key", ""),
            kind=payload.get("kind", ""),
            value=dict(payload.get("value") or {}),
            context_signature=payload.get("context_signature", ""),
            profile_version=payload.get("profile_version"),
            domain_version=payload.get("domain_version"),
            source_ids=tuple(payload.get("source_ids") or ()),
            dependency_ids=tuple(payload.get("dependency_ids") or ()),
            process_metadata=dict(payload.get("process_metadata") or {}),
            confidence=payload.get("confidence", 1.0),
            created_at=created_at,
            last_validated_at=parse_dt(
                payload.get("last_validated_at"), default=created_at
            )
            or created_at,
            updated_at=parse_dt(payload.get("updated_at")),
            invalidated_at=parse_dt(payload.get("invalidated_at")),
            valid_until=parse_dt(payload.get("valid_until")),
            invalidation_keys=tuple(payload.get("invalidation_keys") or ()),
            sensitivity=payload.get("sensitivity", SensitivityLevel.INTERNAL.value),
            permissions=tuple(payload.get("permissions") or ()),
            privacy=(
                PrivacyMetadata.from_mapping(payload["privacy"])
                if payload.get("privacy") is not None
                else None
            ),
            provenance=tuple(payload.get("provenance") or ()),
            status=payload.get("status", CognitiveCacheEntryStatus.VALID.value),
            metadata=dict(payload.get("metadata") or {}),
            schema_version=payload.get("schema_version", COGNITIVE_CACHE_SCHEMA_VERSION),
            audit_log=tuple(payload.get("audit_log") or ()),
        )

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> CognitiveCacheEntry:
        return cls.from_mapping(data)


@dataclass(frozen=True, slots=True)
class CognitiveCacheContext:
    """The reader's context, used to decide whether a cached entry may be reused."""

    context_signature: str
    profile_version: str | None = None
    domain_version: str | None = None
    schema_version: int = COGNITIVE_CACHE_SCHEMA_VERSION
    actor_id: str | None = None
    domain: str | None = None
    sensitivity_clearance: SensitivityLevel | None = None
    processing_location: ProcessingLocation = ProcessingLocation.LOCAL
    invalidated_dependency_ids: frozenset[str] = field(default_factory=frozenset)
    at: datetime = field(default_factory=_utc_now)

    def __post_init__(self) -> None:
        if (
            not isinstance(self.context_signature, str)
            or not self.context_signature.strip()
        ):
            raise InvalidCognitiveCacheEntryError("context_signature must not be empty")
        _require_aware(self.at, "at")
        if not isinstance(self.at, datetime):
            raise InvalidCognitiveCacheEntryError("at must be a datetime")

        location = self.processing_location
        if isinstance(location, str):
            try:
                location = ProcessingLocation(location)
            except ValueError as exc:
                raise InvalidCognitiveCacheEntryError(
                    f"Invalid processing_location: {location}"
                ) from exc
        elif not isinstance(location, ProcessingLocation):
            raise InvalidCognitiveCacheEntryError(
                f"Invalid processing_location: {location}"
            )
        object.__setattr__(self, "processing_location", location)

        clearance = self.sensitivity_clearance
        if isinstance(clearance, str):
            try:
                clearance = SensitivityLevel(clearance)
            except ValueError as exc:
                raise InvalidCognitiveCacheEntryError(
                    f"Invalid sensitivity_clearance: {clearance}"
                ) from exc
        elif clearance is not None and not isinstance(clearance, SensitivityLevel):
            raise InvalidCognitiveCacheEntryError(
                f"Invalid sensitivity_clearance: {clearance}"
            )
        object.__setattr__(self, "sensitivity_clearance", clearance)
        object.__setattr__(
            self,
            "invalidated_dependency_ids",
            frozenset(str(item) for item in self.invalidated_dependency_ids or ()),
        )


@dataclass(frozen=True, slots=True)
class CognitiveCacheLookupResult:
    """Structured, unambiguous outcome of a cache lookup."""

    status: CognitiveCacheLookupStatus
    hit: bool
    reusable: bool
    reason: str
    entry: CognitiveCacheEntry | None = None
    requires_revalidation: bool = False


@dataclass(frozen=True, slots=True)
class CognitiveCacheValidationResult:
    """Outcome of revalidating a single cache entry against a context."""

    status: CognitiveCacheEntryStatus
    reason: str


@runtime_checkable
class CognitiveCacheValidator(Protocol):
    """Extension point for revalidating a cache entry without invoking a model."""

    def __call__(
        self,
        entry: CognitiveCacheEntry,
        context: CognitiveCacheContext,
    ) -> CognitiveCacheValidationResult: ...


def _schema_unsupported(entry: CognitiveCacheEntry) -> bool:
    return entry.schema_version != COGNITIVE_CACHE_SCHEMA_VERSION


def _is_expired(entry: CognitiveCacheEntry, at: datetime) -> bool:
    return (entry.valid_until is not None and entry.valid_until <= at) or (
        entry.status is CognitiveCacheEntryStatus.EXPIRED
    )


def default_cognitive_cache_validator(
    entry: CognitiveCacheEntry, context: CognitiveCacheContext
) -> CognitiveCacheValidationResult:
    """Structural revalidation: dates, versions, context signature, dependencies.

    Never invokes a model. Callers needing Phase 7 Validation Pipeline
    integration should supply their own validator (Phase 8.26 concern).
    """
    now = context.at
    if _schema_unsupported(entry):
        return CognitiveCacheValidationResult(
            CognitiveCacheEntryStatus.INVALID, "unsupported schema_version"
        )
    if _is_expired(entry, now):
        return CognitiveCacheValidationResult(
            CognitiveCacheEntryStatus.EXPIRED, "valid_until has passed"
        )
    if entry.context_signature != context.context_signature:
        return CognitiveCacheValidationResult(
            CognitiveCacheEntryStatus.STALE, "context_signature mismatch"
        )
    if (
        context.profile_version is not None
        and entry.profile_version != context.profile_version
    ):
        return CognitiveCacheValidationResult(
            CognitiveCacheEntryStatus.STALE, "profile_version mismatch"
        )
    if (
        context.domain_version is not None
        and entry.domain_version != context.domain_version
    ):
        return CognitiveCacheValidationResult(
            CognitiveCacheEntryStatus.STALE, "domain_version mismatch"
        )
    if context.invalidated_dependency_ids and (
        set(entry.dependency_ids) & context.invalidated_dependency_ids
    ):
        return CognitiveCacheValidationResult(
            CognitiveCacheEntryStatus.STALE, "dependency invalidated"
        )
    return CognitiveCacheValidationResult(CognitiveCacheEntryStatus.VALID, "valid")


@runtime_checkable
class CognitiveCacheStoreProtocol(Protocol):
    """Protocol for Cognitive Cache store implementations.

    Distinct from ``KnowledgeStoreProtocol``: the Knowledge Store holds
    canonical knowledge; this store holds derived, reusable cognitive results.
    """

    def get(self, entry_id: str) -> CognitiveCacheEntry: ...

    def get_by_key(
        self, key: str, context_signature: str | None = None
    ) -> CognitiveCacheEntry | None: ...

    def put(self, entry: CognitiveCacheEntry) -> CognitiveCacheEntry: ...

    def delete(self, entry_id: str) -> None: ...

    def invalidate(
        self,
        entry_id: str,
        reason: str | None = None,
        *,
        status: CognitiveCacheEntryStatus = CognitiveCacheEntryStatus.INVALID,
    ) -> CognitiveCacheEntry: ...

    def find_by_source_id(self, source_id: str) -> tuple[CognitiveCacheEntry, ...]: ...

    def find_by_dependency_id(
        self, dependency_id: str
    ) -> tuple[CognitiveCacheEntry, ...]: ...

    def find_by_invalidation_key(self, key: str) -> tuple[CognitiveCacheEntry, ...]: ...

    def find_by_predicate(
        self, predicate: Callable[[CognitiveCacheEntry], bool]
    ) -> tuple[CognitiveCacheEntry, ...]: ...

    def clear(self) -> None: ...


_IDENTITY_FIELDS = (
    "key",
    "kind",
    "context_signature",
    "schema_version",
    "source_ids",
    "dependency_ids",
    "invalidation_keys",
    "profile_version",
    "domain_version",
)


class InMemoryCognitiveCacheStore:
    """Thread-safe, deterministic in-memory Cognitive Cache store.

    Accepts an injectable ``clock`` (a zero-argument callable returning a
    timezone-aware ``datetime``) so invalidation is deterministic and
    testable without depending on wall-clock time. Defaults to the real UTC
    clock.
    """

    def __init__(self, *, clock: Clock | None = None) -> None:
        self._entries: dict[str, CognitiveCacheEntry] = {}
        self._key_index: dict[str, list[str]] = {}
        self._source_index: dict[str, set[str]] = {}
        self._dependency_index: dict[str, set[str]] = {}
        self._invalidation_index: dict[str, set[str]] = {}
        self._lock = RLock()
        self._clock: Clock = clock or _utc_now

    @staticmethod
    def _same_identity(
        existing: CognitiveCacheEntry, incoming: CognitiveCacheEntry
    ) -> bool:
        for name in _IDENTITY_FIELDS:
            if getattr(existing, name) != getattr(incoming, name):
                return False
        return existing.value == incoming.value

    def _index(self, entry: CognitiveCacheEntry) -> None:
        self._key_index.setdefault(entry.key, [])
        if entry.id not in self._key_index[entry.key]:
            self._key_index[entry.key].append(entry.id)
        for source_id in entry.source_ids:
            self._source_index.setdefault(source_id, set()).add(entry.id)
        for dependency_id in entry.dependency_ids:
            self._dependency_index.setdefault(dependency_id, set()).add(entry.id)
        for invalidation_key in entry.invalidation_keys:
            self._invalidation_index.setdefault(invalidation_key, set()).add(entry.id)

    def put(self, entry: CognitiveCacheEntry) -> CognitiveCacheEntry:
        if not isinstance(entry, CognitiveCacheEntry):
            raise InvalidCognitiveCacheEntryError(
                f"Expected CognitiveCacheEntry, got {type(entry).__name__}"
            )
        with self._lock:
            existing = self._entries.get(entry.id)
            if existing is not None and existing.serialize() == entry.serialize():
                return existing
            if existing is not None and not self._same_identity(existing, entry):
                raise CognitiveCacheConflictError(
                    f"CognitiveCacheEntry '{entry.id}' already exists with incompatible data"
                )
            self._entries[entry.id] = entry
            self._index(entry)
            return entry

    def get(self, entry_id: str) -> CognitiveCacheEntry:
        if not isinstance(entry_id, str) or not entry_id.strip():
            raise InvalidCognitiveCacheEntryError("entry_id must be a non-empty string")
        with self._lock:
            entry = self._entries.get(entry_id.strip())
            if entry is None:
                raise CognitiveCacheNotFoundError(
                    f"CognitiveCacheEntry not found: '{entry_id.strip()}'"
                )
            return entry

    def get_by_key(
        self, key: str, context_signature: str | None = None
    ) -> CognitiveCacheEntry | None:
        with self._lock:
            ids = self._key_index.get(key, [])
            if not ids:
                return None
            if context_signature is None:
                return self._entries[ids[-1]]
            for entry_id in reversed(ids):
                entry = self._entries[entry_id]
                if entry.context_signature == context_signature:
                    return entry
            return None

    def delete(self, entry_id: str) -> None:
        if not isinstance(entry_id, str) or not entry_id.strip():
            raise InvalidCognitiveCacheEntryError("entry_id must be a non-empty string")
        with self._lock:
            key = entry_id.strip()
            entry = self._entries.get(key)
            if entry is None:
                raise CognitiveCacheNotFoundError(
                    f"CognitiveCacheEntry not found for deletion: '{key}'"
                )
            del self._entries[key]
            ids = self._key_index.get(entry.key)
            if ids and key in ids:
                ids.remove(key)
            for source_id in entry.source_ids:
                self._source_index.get(source_id, set()).discard(key)
            for dependency_id in entry.dependency_ids:
                self._dependency_index.get(dependency_id, set()).discard(key)
            for invalidation_key in entry.invalidation_keys:
                self._invalidation_index.get(invalidation_key, set()).discard(key)

    def invalidate(
        self,
        entry_id: str,
        reason: str | None = None,
        *,
        status: CognitiveCacheEntryStatus = CognitiveCacheEntryStatus.INVALID,
    ) -> CognitiveCacheEntry:
        with self._lock:
            entry = self.get(entry_id)
            updated = entry._with_invalidation(status, reason, at=self._clock())
            self._entries[updated.id] = updated
            return updated

    def _find(self, index: Mapping[str, set[str]], key: str) -> tuple[CognitiveCacheEntry, ...]:
        with self._lock:
            ids = index.get(key, set())
            matches = [self._entries[entry_id] for entry_id in ids if entry_id in self._entries]
        matches.sort(key=lambda e: (e.created_at, e.id))
        return tuple(matches)

    def find_by_source_id(self, source_id: str) -> tuple[CognitiveCacheEntry, ...]:
        return self._find(self._source_index, source_id)

    def find_by_dependency_id(self, dependency_id: str) -> tuple[CognitiveCacheEntry, ...]:
        return self._find(self._dependency_index, dependency_id)

    def find_by_invalidation_key(self, key: str) -> tuple[CognitiveCacheEntry, ...]:
        return self._find(self._invalidation_index, key)

    def find_by_predicate(
        self, predicate: Callable[[CognitiveCacheEntry], bool]
    ) -> tuple[CognitiveCacheEntry, ...]:
        with self._lock:
            matches = [entry for entry in self._entries.values() if predicate(entry)]
        matches.sort(key=lambda e: (e.created_at, e.id))
        return tuple(matches)

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()
            self._key_index.clear()
            self._source_index.clear()
            self._dependency_index.clear()
            self._invalidation_index.clear()


class CognitiveCache:
    """Coordinates reuse, invalidation, and revalidation of cognitive artifacts.

    Never converts a cached result into an established fact, never returns a
    stale/expired/invalid entry as reusable, and never bypasses permissions or
    sensitivity clearance.
    """

    def __init__(
        self,
        store: CognitiveCacheStoreProtocol,
        *,
        validator: CognitiveCacheValidator | None = None,
        clock: Clock | None = None,
    ) -> None:
        if not isinstance(store, CognitiveCacheStoreProtocol):
            raise InvalidCognitiveCacheEntryError(
                "store must implement CognitiveCacheStoreProtocol"
            )
        self._store = store
        self._validator = validator or default_cognitive_cache_validator
        self._clock: Clock = clock or _utc_now

    def put(self, entry: CognitiveCacheEntry) -> CognitiveCacheEntry:
        if not isinstance(entry, CognitiveCacheEntry):
            raise InvalidCognitiveCacheEntryError(
                f"Expected CognitiveCacheEntry, got {type(entry).__name__}"
            )
        if entry.privacy is not None and not entry.privacy.allow_cache:
            raise InvalidCognitiveCacheEntryError(
                "cannot cache an entry whose privacy metadata forbids caching "
                "(allow_cache=False)"
            )
        now = self._clock()
        if (
            entry.status is CognitiveCacheEntryStatus.VALID
            and entry.valid_until is not None
            and entry.valid_until <= now
        ):
            entry = entry._with_invalidation(
                CognitiveCacheEntryStatus.EXPIRED,
                "valid_until had already passed at put time",
                at=now,
            )
        return self._store.put(entry)

    def _permission_denied(
        self, entry: CognitiveCacheEntry, context: CognitiveCacheContext
    ) -> bool:
        entry_rank = _SENSITIVITY_RANK[entry.sensitivity]
        if context.sensitivity_clearance is None:
            # Safe by default: absence of clearance only authorizes entries at
            # or below the public tier. Personal, sensitive, highly sensitive,
            # and restricted content always require explicit clearance.
            if entry_rank > _SAFE_WITHOUT_CLEARANCE_RANK:
                return True
        elif entry_rank > _SENSITIVITY_RANK[context.sensitivity_clearance]:
            return True
        if entry.permissions:
            allowed = any(
                permission.allows(
                    ResourcePermissionOperation.READ,
                    actor_id=context.actor_id,
                    domain=context.domain,
                    at=context.at,
                )
                for permission in entry.permissions
            )
            if not allowed:
                return True
        return False

    def get(self, key: str, context: CognitiveCacheContext) -> CognitiveCacheLookupResult:
        if not isinstance(context, CognitiveCacheContext):
            raise InvalidCognitiveCacheEntryError(
                "context must be a CognitiveCacheContext"
            )

        exact = self._store.get_by_key(key, context.context_signature)
        entry = exact
        context_mismatch = False
        if entry is None:
            candidate = self._store.get_by_key(key)
            if candidate is None:
                return CognitiveCacheLookupResult(
                    status=CognitiveCacheLookupStatus.MISS,
                    hit=False,
                    reusable=False,
                    reason="no cache entry for key",
                    entry=None,
                    requires_revalidation=False,
                )
            entry = candidate
            context_mismatch = True

        if context_mismatch:
            return CognitiveCacheLookupResult(
                status=CognitiveCacheLookupStatus.CONTEXT_MISMATCH,
                hit=True,
                reusable=False,
                reason="context_signature does not match the cached entry",
                entry=entry,
                requires_revalidation=True,
            )

        if _schema_unsupported(entry):
            return CognitiveCacheLookupResult(
                status=CognitiveCacheLookupStatus.HIT_INVALID,
                hit=True,
                reusable=False,
                reason="unsupported schema_version",
                entry=entry,
            )

        if entry.status is CognitiveCacheEntryStatus.INVALID:
            return CognitiveCacheLookupResult(
                status=CognitiveCacheLookupStatus.HIT_INVALID,
                hit=True,
                reusable=False,
                reason="entry is marked invalid",
                entry=entry,
            )

        if _is_expired(entry, context.at):
            return CognitiveCacheLookupResult(
                status=CognitiveCacheLookupStatus.HIT_EXPIRED,
                hit=True,
                reusable=False,
                reason="entry has expired",
                entry=entry,
            )

        if self._permission_denied(entry, context):
            return CognitiveCacheLookupResult(
                status=CognitiveCacheLookupStatus.PERMISSION_DENIED,
                hit=True,
                reusable=False,
                reason="insufficient permissions or sensitivity clearance",
                entry=entry,
            )

        if (
            entry.privacy is not None
            and entry.privacy.policy is PrivacyPolicy.LOCAL_ONLY
            and context.processing_location is ProcessingLocation.REMOTE
        ):
            return CognitiveCacheLookupResult(
                status=CognitiveCacheLookupStatus.PERMISSION_DENIED,
                hit=True,
                reusable=False,
                reason="entry privacy policy is LOCAL_ONLY; unavailable in a remote "
                "processing context",
                entry=entry,
            )

        if (
            context.profile_version is not None
            and entry.profile_version != context.profile_version
        ):
            return CognitiveCacheLookupResult(
                status=CognitiveCacheLookupStatus.REVALIDATION_REQUIRED,
                hit=True,
                reusable=False,
                reason="profile_version mismatch",
                entry=entry,
                requires_revalidation=True,
            )
        if (
            context.domain_version is not None
            and entry.domain_version != context.domain_version
        ):
            return CognitiveCacheLookupResult(
                status=CognitiveCacheLookupStatus.REVALIDATION_REQUIRED,
                hit=True,
                reusable=False,
                reason="domain_version mismatch",
                entry=entry,
                requires_revalidation=True,
            )
        if context.invalidated_dependency_ids and (
            set(entry.dependency_ids) & context.invalidated_dependency_ids
        ):
            return CognitiveCacheLookupResult(
                status=CognitiveCacheLookupStatus.REVALIDATION_REQUIRED,
                hit=True,
                reusable=False,
                reason="a dependency has been invalidated",
                entry=entry,
                requires_revalidation=True,
            )

        if entry.status is CognitiveCacheEntryStatus.STALE:
            return CognitiveCacheLookupResult(
                status=CognitiveCacheLookupStatus.HIT_STALE,
                hit=True,
                reusable=False,
                reason="entry is marked stale",
                entry=entry,
                requires_revalidation=True,
            )

        return CognitiveCacheLookupResult(
            status=CognitiveCacheLookupStatus.HIT_REUSABLE,
            hit=True,
            reusable=True,
            reason="valid",
            entry=entry,
            requires_revalidation=False,
        )

    def reuse(self, key: str, context: CognitiveCacheContext) -> CognitiveCacheLookupResult:
        """Alias of :meth:`get` for call sites emphasising reuse intent."""
        return self.get(key, context)

    def invalidate(
        self, entry_id: str, reason: str | None = None
    ) -> CognitiveCacheEntry:
        return self._store.invalidate(entry_id, reason)

    def revalidate(
        self, entry_id: str, context: CognitiveCacheContext
    ) -> CognitiveCacheEntry:
        """Structurally revalidate one entry. Never invokes a model."""
        entry = self._store.get(entry_id)
        result = self._validator(entry, context)
        updated = entry._with_revalidation(result.status, result.reason, at=context.at)
        return self._store.put(updated)

    def _invalidate_all(
        self, matches: Sequence[CognitiveCacheEntry], reason: str
    ) -> tuple[CognitiveCacheEntry, ...]:
        return tuple(
            self._store.invalidate(entry.id, reason)
            for entry in matches
            if entry.status is not CognitiveCacheEntryStatus.INVALID
        )

    def _invalidate_matching(
        self,
        predicate: Callable[[CognitiveCacheEntry], bool],
        reason: str,
        *,
        status: CognitiveCacheEntryStatus = CognitiveCacheEntryStatus.INVALID,
    ) -> tuple[CognitiveCacheEntry, ...]:
        matches = self._store.find_by_predicate(predicate)
        return tuple(
            self._store.invalidate(entry.id, reason, status=status)
            for entry in matches
            if entry.status is not status
        )

    def invalidate_by_source_id(
        self, source_id: str, reason: str | None = None
    ) -> tuple[CognitiveCacheEntry, ...]:
        return self._invalidate_all(
            self._store.find_by_source_id(source_id),
            reason or f"source '{source_id}' invalidated",
        )

    def invalidate_by_dependency_id(
        self, dependency_id: str, reason: str | None = None
    ) -> tuple[CognitiveCacheEntry, ...]:
        return self._invalidate_all(
            self._store.find_by_dependency_id(dependency_id),
            reason or f"dependency '{dependency_id}' invalidated",
        )

    def invalidate_by_key(
        self, invalidation_key: str, reason: str | None = None
    ) -> tuple[CognitiveCacheEntry, ...]:
        return self._invalidate_all(
            self._store.find_by_invalidation_key(invalidation_key),
            reason or f"invalidation key '{invalidation_key}' triggered",
        )

    def invalidate_by_profile_version(
        self, profile_version: str, reason: str | None = None
    ) -> tuple[CognitiveCacheEntry, ...]:
        return self._invalidate_matching(
            lambda entry: entry.profile_version == profile_version,
            reason or f"profile_version '{profile_version}' invalidated",
        )

    def invalidate_by_domain_version(
        self, domain_version: str, reason: str | None = None
    ) -> tuple[CognitiveCacheEntry, ...]:
        return self._invalidate_matching(
            lambda entry: entry.domain_version == domain_version,
            reason or f"domain_version '{domain_version}' invalidated",
        )

    def invalidate_by_schema_version(
        self, schema_version: int, reason: str | None = None
    ) -> tuple[CognitiveCacheEntry, ...]:
        return self._invalidate_matching(
            lambda entry: entry.schema_version == schema_version,
            reason or f"schema_version {schema_version} invalidated",
        )

    def invalidate_expired(
        self, *, at: datetime | None = None, reason: str | None = None
    ) -> tuple[CognitiveCacheEntry, ...]:
        reference = at or self._clock()
        return self._invalidate_matching(
            lambda entry: entry.valid_until is not None and entry.valid_until <= reference,
            reason or "entry expired",
            status=CognitiveCacheEntryStatus.EXPIRED,
        )

    # NOTE: a per-actor `invalidate_by_revoked_permission` wrapper was
    # deliberately NOT added here. Invalidating on a single revoked actor
    # would either (a) invalidate the whole entry for every other actor still
    # legitimately entitled to it — broader than the contractual change that
    # occurred — or (b) require rewriting `permissions` in place, which is a
    # privacy-policy update belonging to Phase 8.25. Until 8.25 defines how
    # permission updates propagate, callers needing this should invalidate by
    # the `source_id`/`dependency_id`/`invalidation_key` whose policy actually
    # changed, using the wrappers above.


def _most_restrictive_sensitivity(
    package: KnowledgePackage, explicit: SensitivityLevel | None
) -> SensitivityLevel:
    """Resolve the entry's sensitivity as the most restrictive of the package's
    resources and any explicit override, never a silent downgrade.

    Phase 8.23 does not yet expose a single formal sensitivity for a whole
    KnowledgePackage (only per-Resource `sensitivity`), so this is a
    deliberately conservative, documented stand-in until Phase 8.25 defines
    complete package-level privacy metadata: with no resources and no
    explicit argument, it falls back to the most restrictive level
    (`RESTRICTED`) rather than guessing a permissive default.
    """
    candidates = [resource.sensitivity for resource in package.resources]
    if explicit is not None:
        candidates.append(explicit)
    if not candidates:
        return SensitivityLevel.RESTRICTED
    return max(candidates, key=lambda level: _SENSITIVITY_RANK[level])


def cache_entry_from_knowledge_package(
    package: KnowledgePackage,
    *,
    key: str,
    context_signature: str,
    profile_version: str | None = None,
    domain_version: str | None = None,
    dependency_ids: Sequence[str] = (),
    invalidation_keys: Sequence[str] = (),
    permissions: Sequence[ResourcePermission] = (),
    sensitivity: SensitivityLevel | None = None,
    privacy: PrivacyMetadata | None = None,
    confidence: float = 1.0,
    process_metadata: Mapping[str, Any] | None = None,
    entry_id: str | None = None,
) -> CognitiveCacheEntry:
    """Wrap a canonical, already-serialized KnowledgePackage as a cache entry.

    `profile_version`/`domain_version` are the caller's reasoning-profile and
    domain-policy *versions* — distinct from `package.profile`/`package.domain`,
    which are identifiers/names preserved only inside the serialized `value`.
    They are never inferred from the package.

    `privacy` never downgrades the package's own derived privacy (see
    `cmm.cognitive.privacy.privacy_from_knowledge_package`): both are
    combined with `resolve_effective_privacy_metadata`, which always keeps
    the more restrictive result.

    Does not duplicate the KnowledgePackage contract, does not convert it to a
    prompt, and does not implement Markdown/YAML export.
    """
    if not isinstance(package, KnowledgePackage):
        raise InvalidCognitiveCacheEntryError(
            f"Expected KnowledgePackage, got {type(package).__name__}"
        )
    resolved_id = entry_id or cognitive_cache_entry_id(key, context_signature)
    derived_privacy = privacy_from_knowledge_package(package)
    resolved_privacy = (
        derived_privacy
        if privacy is None
        else resolve_effective_privacy_metadata(derived_privacy, privacy).effective
    )
    return CognitiveCacheEntry(
        id=resolved_id,
        key=key,
        kind="knowledge_package",
        value=package.serialize(),
        context_signature=context_signature,
        profile_version=profile_version,
        domain_version=domain_version,
        source_ids=package.provenance,
        dependency_ids=tuple(dependency_ids),
        process_metadata=dict(process_metadata or {}),
        confidence=confidence,
        created_at=package.created_at,
        last_validated_at=package.created_at,
        valid_until=package.valid_until,
        invalidation_keys=tuple(invalidation_keys),
        sensitivity=_most_restrictive_sensitivity(package, sensitivity),
        permissions=tuple(permissions),
        privacy=resolved_privacy,
        provenance=package.provenance,
        schema_version=COGNITIVE_CACHE_SCHEMA_VERSION,
    )


def privacy_from_cache_entry(entry: CognitiveCacheEntry) -> PrivacyMetadata:
    """Return a CognitiveCacheEntry's effective privacy metadata.

    Falls back to a conservative default `PrivacyMetadata()` for entries
    created before Phase 8.25 (or otherwise without explicit `privacy`).
    """
    if not isinstance(entry, CognitiveCacheEntry):
        raise InvalidCognitiveCacheEntryError(
            f"Expected CognitiveCacheEntry, got {type(entry).__name__}"
        )
    return entry.privacy if entry.privacy is not None else PrivacyMetadata()
