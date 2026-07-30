"""Phase 10.3 – Registry Contracts.

Immutable, JSON-serializable, type-safe contracts for the Domain Registry subsystem.

All dataclasses are ``frozen=True`` and never expose mutable internal state.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from functools import cmp_to_key
from types import MappingProxyType
from typing import Any

from cmm.domains.contracts import (
    DomainDefinition,
    _deep_freeze,
    _deep_unfreeze,
    _ensure_tz_aware,
    _freeze_str_tuple,
    _reject_unknown_fields,
    _validate_non_empty_str,
    _validate_strict_bool,
)
from cmm.domains.enums import DomainKind, DomainStatus
from cmm.domains.errors import (
    DomainContractValidationError,
    DomainSerializationError,
)

# ── Single source of truth: which statuses have enabled=True ───────────────────

_ENABLED_STATUSES: frozenset[DomainStatus] = frozenset(
    {
        DomainStatus.ACTIVE,
        DomainStatus.DEGRADED,
    }
)


# ── Semantic version utilities ─────────────────────────────────────────────────

_SEMVER_RE_STRICT = (
    r"^(0|[1-9]\d*)\."  # major
    r"(0|[1-9]\d*)\."  # minor
    r"(0|[1-9]\d*)"  # patch
    r"(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"  # pre-release
    r"(?:\+([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?$"  # build metadata
)

import re as _re

_SEMVER_PATTERN = _re.compile(_SEMVER_RE_STRICT)


def _compare_pre_release_identifiers(a: str | int, b: str | int) -> int:
    a_is_int = isinstance(a, int)
    b_is_int = isinstance(b, int)
    if a_is_int and b_is_int:
        if a < b:
            return -1
        if a > b:
            return 1
        return 0
    if a_is_int and not b_is_int:
        return -1
    if not a_is_int and b_is_int:
        return 1
    a_str, b_str = str(a), str(b)
    if a_str < b_str:
        return -1
    if a_str > b_str:
        return 1
    return 0


def _compare_pre_release(a: tuple[str | int, ...], b: tuple[str | int, ...]) -> int:
    max_len = max(len(a), len(b))
    for i in range(max_len):
        if i >= len(a):
            return -1
        if i >= len(b):
            return 1
        cmp_result = _compare_pre_release_identifiers(a[i], b[i])
        if cmp_result != 0:
            return cmp_result
    return 0


class _SemanticVersion:
    __slots__ = ("_string", "build", "major", "minor", "patch", "pre_release")

    def __init__(self, version: str) -> None:
        m = _SEMVER_PATTERN.match(version)
        if not m:
            raise DomainContractValidationError(
                f"Invalid semantic version: {version!r}",
                field="version",
                details={"value": version},
            )
        self._string = version
        self.major = int(m.group(1))
        self.minor = int(m.group(2))
        self.patch = int(m.group(3))
        pre_raw = m.group(4)
        self.pre_release: tuple[str | int, ...] = _parse_pre_release(pre_raw)
        self.build = m.group(5)

    def __str__(self) -> str:
        return self._string

    def __repr__(self) -> str:
        return f"_SemanticVersion({self._string!r})"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, _SemanticVersion):
            return NotImplemented
        return (self.major, self.minor, self.patch, self.pre_release) == (
            other.major,
            other.minor,
            other.patch,
            other.pre_release,
        )

    def __hash__(self) -> int:
        return hash((self.major, self.minor, self.patch, self.pre_release))

    def __lt__(self, other: _SemanticVersion) -> bool:
        if (self.major, self.minor, self.patch) != (
            other.major,
            other.minor,
            other.patch,
        ):
            return (self.major, self.minor, self.patch) < (
                other.major,
                other.minor,
                other.patch,
            )
        if not self.pre_release and other.pre_release:
            return False
        if self.pre_release and not other.pre_release:
            return True
        if self.pre_release and other.pre_release:
            return _compare_pre_release(self.pre_release, other.pre_release) < 0
        return False

    def __le__(self, other: _SemanticVersion) -> bool:
        return self == other or self < other

    def __gt__(self, other: _SemanticVersion) -> bool:
        return other < self

    def __ge__(self, other: _SemanticVersion) -> bool:
        return other <= self


def _parse_pre_release(raw: str | None) -> tuple[str | int, ...]:
    if not raw:
        return ()
    parts: list[str | int] = []
    for ident in raw.split("."):
        parts.append(int(ident) if ident.isdigit() else ident)
    return tuple(parts)


def parse_semver(version: str) -> _SemanticVersion:
    return _SemanticVersion(version)


def compare_versions_desc(a: str, b: str) -> int:
    """Compare two valid SemVer strings for descending precedence order.

    Raises ``DomainContractValidationError`` if either string is not a
    valid SemVer — callers that must tolerate malformed data should use
    ``_compare_versions_desc_safe`` instead.
    """
    sv_a, sv_b = _SemanticVersion(a), _SemanticVersion(b)
    if sv_a > sv_b:
        return -1
    if sv_a < sv_b:
        return 1
    return 0


def _compare_versions_desc_safe(left: str, right: str) -> int:
    """Descending SemVer comparator that never raises.

    Falls back to reverse-lexicographic comparison when either version
    string fails to parse as SemVer, so callers can sort mixed-validity
    data deterministically without a ``TypeError`` or crash.
    """
    try:
        return compare_versions_desc(left, right)
    except DomainContractValidationError:
        if left == right:
            return 0
        return -1 if left > right else 1


def _canonical_slug(slug: str) -> str:
    if slug.startswith("domain:"):
        return slug[len("domain:") :]
    return slug


def _compare_records(left: DomainRegistryRecord, right: DomainRegistryRecord) -> int:
    """Deterministic comparator: slug asc, then SemVer desc, then timestamps.

    Used with ``functools.cmp_to_key`` everywhere records need a total,
    stable order (store listings, registry listings, snapshots).
    """
    left_slug = _canonical_slug(left.definition.id.slug)
    right_slug = _canonical_slug(right.definition.id.slug)
    if left_slug != right_slug:
        return -1 if left_slug < right_slug else 1

    version_cmp = _compare_versions_desc_safe(
        left.definition.version, right.definition.version
    )
    if version_cmp:
        return version_cmp

    if left.registered_at != right.registered_at:
        return -1 if left.registered_at < right.registered_at else 1
    if left.updated_at != right.updated_at:
        return -1 if left.updated_at < right.updated_at else 1
    return 0


# ── JSON-safe helpers ──────────────────────────────────────────────────────────

_JSON_SCALAR_TYPES = (str, int, float, type(None))
_JSON_CONTAINER_TYPES = (dict, list, tuple, MappingProxyType)


def _is_json_safe(value: Any) -> bool:
    if isinstance(value, bool):
        return True
    if isinstance(value, _JSON_SCALAR_TYPES):
        return True
    if isinstance(value, _JSON_CONTAINER_TYPES):
        items = (
            value.items()
            if isinstance(value, (dict, MappingProxyType))
            else enumerate(value)
        )
        for _k, v in items:
            if not _is_json_safe(v):
                return False
        return True
    return False


def _validate_json_safe_metadata(
    meta: Any, field_name: str
) -> MappingProxyType[str, Any]:
    if meta is None:
        return MappingProxyType({})
    if not isinstance(meta, Mapping):
        raise DomainContractValidationError(
            f"{field_name} must be a mapping", field=field_name
        )
    for k, v in meta.items():
        if not isinstance(k, str):
            raise DomainContractValidationError(
                f"{field_name} keys must be strings", field=field_name
            )
        if not _is_json_safe(v):
            raise DomainContractValidationError(
                f"{field_name} values must be JSON-safe (str, int, float, None, list, dict); "
                f"got {type(v).__name__} for key {k!r}",
                field=field_name,
                details={"key": k, "type": type(v).__name__},
            )
    return _deep_freeze(meta)


_SENSITIVE_EXACT_WORDS: frozenset[str] = frozenset(
    {
        "secret",
        "secrets",
        "password",
        "passwords",
        "token",
        "tokens",
        "credential",
        "credentials",
        "apikey",
        "api_key",
        "privatekey",
        "private_key",
        "auth_token",
        "authtoken",
        "access_key",
        "accesskey",
        "secret_key",
        "secretkey",
    }
)


def _reject_sensitive_keys(meta: Mapping[str, Any], field_name: str) -> None:
    for k in meta:
        lower = k.lower().replace("-", "_").replace(" ", "_")
        if lower in _SENSITIVE_EXACT_WORDS:
            raise DomainContractValidationError(
                f"{field_name} contains sensitive key: {k!r}",
                field=field_name,
                details={"key": k},
            )
        for part in lower.split("_"):
            if part in {"secret", "password", "token", "credential"}:
                raise DomainContractValidationError(
                    f"{field_name} contains potentially sensitive key: {k!r}",
                    field=field_name,
                    details={"key": k},
                )


# ── Strict from_dict helpers ───────────────────────────────────────────────────


def _require_non_empty_str(value: Any, field_name: str, cls_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise DomainSerializationError(
            f"{cls_name}.from_dict: {field_name} must be a non-empty string, got {type(value).__name__}: {value!r}",
            field=field_name,
        )
    return value.strip()


def _require_strict_bool(value: Any, field_name: str, cls_name: str) -> bool:
    if not isinstance(value, bool):
        raise DomainSerializationError(
            f"{cls_name}.from_dict: {field_name} must be a boolean (True or False), got {type(value).__name__}: {value!r}",
            field=field_name,
        )
    return value


def _require_str_tuple(raw: Any, field_name: str, cls_name: str) -> tuple[str, ...]:
    if raw is None:
        return ()
    if isinstance(raw, str):
        raise DomainSerializationError(
            f"{cls_name}.from_dict: {field_name} must be a list of strings, not a string",
            field=field_name,
        )
    if not isinstance(raw, (list, tuple)):
        raise DomainSerializationError(
            f"{cls_name}.from_dict: {field_name} must be a list of strings, got {type(raw).__name__}",
            field=field_name,
        )
    result: list[str] = []
    for i, item in enumerate(raw):
        if not isinstance(item, str) or not item.strip():
            raise DomainSerializationError(
                f"{cls_name}.from_dict: {field_name}[{i}] must be a non-empty string, got {type(item).__name__}: {item!r}",
                field=f"{field_name}[{i}]",
            )
        result.append(item.strip())
    return tuple(result)


def _parse_tz_aware_datetime(raw: Any, field_name: str, cls_name: str) -> datetime:
    if isinstance(raw, datetime):
        if raw.tzinfo is None:
            raise DomainSerializationError(
                f"{cls_name}.from_dict: {field_name} must be timezone-aware, got naive datetime",
                field=field_name,
            )
        return raw
    if isinstance(raw, str):
        try:
            parsed = datetime.fromisoformat(raw)
        except ValueError as exc:
            raise DomainSerializationError(
                f"{cls_name}.from_dict: invalid isoformat for {field_name}: {raw!r}",
                field=field_name,
            ) from exc
        if parsed.tzinfo is None:
            raise DomainSerializationError(
                f"{cls_name}.from_dict: {field_name} must be timezone-aware, got naive datetime string: {raw!r}",
                field=field_name,
            )
        return parsed
    raise DomainSerializationError(
        f"{cls_name}.from_dict: {field_name} must be a datetime or ISO string, got {type(raw).__name__}",
        field=field_name,
    )


def _require_status(value: Any, field_name: str, cls_name: str) -> DomainStatus:
    if isinstance(value, DomainStatus):
        return value
    if isinstance(value, str):
        try:
            return DomainStatus(value)
        except ValueError as exc:
            raise DomainSerializationError(
                f"{cls_name}.from_dict: invalid {field_name}: {value!r}",
                field=field_name,
            ) from exc
    raise DomainSerializationError(
        f"{cls_name}.from_dict: {field_name} must be a DomainStatus or string, got {type(value).__name__}",
        field=field_name,
    )


# ── DomainRegistryStoreSnapshot ────────────────────────────────────────────────

_SNAPSHOT_STATE_KNOWN = frozenset({"records"})


@dataclass(frozen=True, slots=True)
class DomainRegistryStoreSnapshot:
    """Opaque snapshot of store state for atomic rollback operations."""

    records: tuple[DomainRegistryRecord, ...]

    def __post_init__(self) -> None:
        if isinstance(self.records, (list, tuple)):
            object.__setattr__(self, "records", tuple(self.records))
        else:
            raise DomainContractValidationError(
                "records must be a list or tuple", field="records"
            )

    def to_dict(self) -> dict[str, Any]:
        return {"records": [r.to_dict() for r in self.records]}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DomainRegistryStoreSnapshot:
        if not isinstance(data, Mapping):
            raise DomainSerializationError(
                "DomainRegistryStoreSnapshot.from_dict requires a mapping", field="data"
            )
        _reject_unknown_fields(
            data, _SNAPSHOT_STATE_KNOWN, "DomainRegistryStoreSnapshot"
        )
        if "records" not in data:
            raise DomainSerializationError(
                "DomainRegistryStoreSnapshot.from_dict missing required field 'records'",
                field="records",
            )
        records_raw = data["records"]
        if not isinstance(records_raw, (list, tuple)):
            raise DomainSerializationError("records must be a list", field="records")
        records: list[DomainRegistryRecord] = []
        for i, item in enumerate(records_raw):
            if not isinstance(item, Mapping):
                raise DomainSerializationError(
                    f"Each item in records must be a mapping, got {type(item).__name__} at index {i}",
                    field=f"records[{i}]",
                )
            try:
                records.append(DomainRegistryRecord.from_dict(dict(item)))
            except DomainSerializationError:
                raise
            except Exception as exc:
                raise DomainSerializationError(
                    f"Failed to parse record at index {i}",
                    field=f"records[{i}]",
                    details={"error": type(exc).__name__},
                ) from exc
        return cls(records=tuple(records))


# ── DomainRegistryRecord ───────────────────────────────────────────────────────

_RECORD_KNOWN = frozenset({"definition", "status", "registered_at", "updated_at"})


@dataclass(frozen=True, slots=True)
class DomainRegistryRecord:
    """Immutable registry entry. The single authoritative source of lifecycle state.

    ``definition.enabled`` is always normalized from ``status``:
    ACTIVE, DEGRADED → True; all others → False.
    """

    definition: DomainDefinition
    status: DomainStatus
    registered_at: datetime
    updated_at: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.definition, DomainDefinition):
            raise DomainContractValidationError(
                f"definition must be a DomainDefinition, got {type(self.definition).__name__}",
                field="definition",
            )
        if not isinstance(self.status, DomainStatus):
            raise DomainContractValidationError(
                f"status must be a DomainStatus, got {type(self.status).__name__}",
                field="status",
            )

        # Normalize enabled from status (authoritative)
        expected_enabled = self.status in _ENABLED_STATUSES
        if self.definition.enabled != expected_enabled:
            import dataclasses

            object.__setattr__(
                self,
                "definition",
                dataclasses.replace(self.definition, enabled=expected_enabled),
            )

        object.__setattr__(
            self, "registered_at", _ensure_tz_aware(self.registered_at, "registered_at")
        )
        object.__setattr__(
            self, "updated_at", _ensure_tz_aware(self.updated_at, "updated_at")
        )
        if self.registered_at.tzinfo != timezone.utc:
            object.__setattr__(
                self, "registered_at", self.registered_at.astimezone(timezone.utc)
            )
        if self.updated_at.tzinfo != timezone.utc:
            object.__setattr__(
                self, "updated_at", self.updated_at.astimezone(timezone.utc)
            )
        if self.updated_at < self.registered_at:
            raise DomainContractValidationError(
                "updated_at cannot be before registered_at", field="updated_at"
            )

    @property
    def domain_id(self) -> str:
        return self.definition.id.slug

    @property
    def version(self) -> str:
        return self.definition.version

    def to_dict(self) -> dict[str, Any]:
        return {
            "definition": self.definition.to_dict(),
            "status": self.status.value,
            "registered_at": self.registered_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DomainRegistryRecord:
        if not isinstance(data, Mapping):
            raise DomainSerializationError(
                "DomainRegistryRecord.from_dict requires a mapping", field="data"
            )
        _reject_unknown_fields(data, _RECORD_KNOWN, "DomainRegistryRecord")
        required = {"definition", "status", "registered_at", "updated_at"}
        missing = required - set(data.keys())
        if missing:
            raise DomainSerializationError(
                f"DomainRegistryRecord.from_dict missing required fields: {sorted(missing)}",
                field="data",
            )
        definition_data = data["definition"]
        if not isinstance(definition_data, Mapping):
            raise DomainSerializationError(
                "definition must be a mapping", field="definition"
            )
        definition = DomainDefinition.from_dict(dict(definition_data))
        status = _require_status(data["status"], "status", "DomainRegistryRecord")
        registered_at = _parse_tz_aware_datetime(
            data["registered_at"], "registered_at", "DomainRegistryRecord"
        )
        updated_at = _parse_tz_aware_datetime(
            data["updated_at"], "updated_at", "DomainRegistryRecord"
        )
        return cls(
            definition=definition,
            status=status,
            registered_at=registered_at,
            updated_at=updated_at,
        )


# ── DomainQuery ────────────────────────────────────────────────────────────────

_QUERY_KNOWN = frozenset(
    {
        "kinds",
        "statuses",
        "capabilities",
        "enabled",
        "tags",
        "minimum_version",
        "include_experimental",
        "metadata",
    }
)


@dataclass(frozen=True, slots=True)
class DomainQuery:
    kinds: tuple[DomainKind, ...] = ()
    statuses: tuple[DomainStatus, ...] = ()
    capabilities: tuple[str, ...] = ()
    enabled: bool | None = None
    tags: tuple[str, ...] = ()
    minimum_version: str | None = None
    include_experimental: bool = False
    metadata: MappingProxyType[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )

    def __post_init__(self) -> None:
        object.__setattr__(self, "kinds", _freeze_kinds(self.kinds, "kinds"))
        object.__setattr__(
            self, "statuses", _freeze_statuses(self.statuses, "statuses")
        )
        object.__setattr__(
            self,
            "capabilities",
            _freeze_query_str_tuple(
                self.capabilities, "capabilities", require_unique=True
            ),
        )
        object.__setattr__(
            self,
            "tags",
            _freeze_query_str_tuple(self.tags, "tags", require_unique=True),
        )
        if self.enabled is not None and not isinstance(self.enabled, bool):
            raise DomainContractValidationError(
                f"enabled must be a bool or None, got {type(self.enabled).__name__}: {self.enabled!r}",
                field="enabled",
            )
        object.__setattr__(self, "enabled", self.enabled)
        if self.minimum_version is not None:
            if (
                not isinstance(self.minimum_version, str)
                or not self.minimum_version.strip()
            ):
                raise DomainContractValidationError(
                    "minimum_version must be a non-empty string",
                    field="minimum_version",
                )
            parse_semver(self.minimum_version)
        object.__setattr__(self, "minimum_version", self.minimum_version)
        object.__setattr__(
            self,
            "include_experimental",
            _validate_strict_bool(self.include_experimental, "include_experimental"),
        )
        meta = _validate_json_safe_metadata(self.metadata, "metadata")
        _reject_sensitive_keys(meta, "metadata")
        object.__setattr__(self, "metadata", meta)

    def to_dict(self) -> dict[str, Any]:
        return {
            "kinds": sorted([k.value for k in self.kinds]),
            "statuses": sorted([s.value for s in self.statuses]),
            "capabilities": list(self.capabilities),
            "enabled": self.enabled,
            "tags": list(self.tags),
            "minimum_version": self.minimum_version,
            "include_experimental": self.include_experimental,
            "metadata": _deep_unfreeze(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DomainQuery:
        if not isinstance(data, Mapping):
            raise DomainSerializationError(
                "DomainQuery.from_dict requires a mapping", field="data"
            )
        _reject_unknown_fields(data, _QUERY_KNOWN, "DomainQuery")
        kinds_raw = data.get("kinds", ())
        if isinstance(kinds_raw, str):
            raise DomainSerializationError(
                "kinds must be a list of strings, not a string", field="kinds"
            )
        kinds = tuple(kinds_raw) if kinds_raw else ()
        statuses_raw = data.get("statuses", ())
        if isinstance(statuses_raw, str):
            raise DomainSerializationError(
                "statuses must be a list of strings, not a string", field="statuses"
            )
        statuses = tuple(statuses_raw) if statuses_raw else ()
        enabled_raw = data.get("enabled")
        if enabled_raw is not None and not isinstance(enabled_raw, bool):
            raise DomainSerializationError(
                f"enabled must be a boolean or None, got {type(enabled_raw).__name__}",
                field="enabled",
            )
        ie_raw = data.get("include_experimental")
        if ie_raw is not None and not isinstance(ie_raw, bool):
            raise DomainSerializationError(
                f"include_experimental must be a boolean, got {type(ie_raw).__name__}",
                field="include_experimental",
            )
        return cls(
            kinds=kinds,
            statuses=statuses,
            capabilities=tuple(data.get("capabilities", ())),
            enabled=enabled_raw,
            tags=tuple(data.get("tags", ())),
            minimum_version=data.get("minimum_version"),
            include_experimental=ie_raw if ie_raw is not None else False,
            metadata=data.get("metadata"),
        )


def _freeze_kinds(raw: Any, field_name: str) -> tuple[DomainKind, ...]:
    if raw is None:
        return ()
    if isinstance(raw, (str, bytes)):
        raise DomainContractValidationError(
            f"{field_name} must be a sequence of DomainKind, not a string",
            field=field_name,
        )
    if not isinstance(raw, (tuple, list, Sequence)):
        raise DomainContractValidationError(
            f"{field_name} must be a sequence", field=field_name
        )
    result, seen = [], set()
    for i, item in enumerate(raw):
        if isinstance(item, DomainKind):
            kind = item
        elif isinstance(item, str):
            try:
                kind = DomainKind(item)
            except ValueError as exc:
                raise DomainContractValidationError(
                    f"Invalid DomainKind at {field_name}[{i}]: {item!r}",
                    field=field_name,
                    details={"index": i, "value": item},
                ) from exc
        else:
            raise DomainContractValidationError(
                f"Each item in {field_name} must be a DomainKind or string, got {type(item).__name__} at index {i}",
                field=field_name,
                details={"index": i},
            )
        if kind.value not in seen:
            seen.add(kind.value)
            result.append(kind)
    return tuple(result)


def _freeze_statuses(raw: Any, field_name: str) -> tuple[DomainStatus, ...]:
    if raw is None:
        return ()
    if isinstance(raw, (str, bytes)):
        raise DomainContractValidationError(
            f"{field_name} must be a sequence of DomainStatus, not a string",
            field=field_name,
        )
    if not isinstance(raw, (tuple, list, Sequence)):
        raise DomainContractValidationError(
            f"{field_name} must be a sequence", field=field_name
        )
    result, seen = [], set()
    for i, item in enumerate(raw):
        if isinstance(item, DomainStatus):
            status = item
        elif isinstance(item, str):
            try:
                status = DomainStatus(item)
            except ValueError as exc:
                raise DomainContractValidationError(
                    f"Invalid DomainStatus at {field_name}[{i}]: {item!r}",
                    field=field_name,
                    details={"index": i, "value": item},
                ) from exc
        else:
            raise DomainContractValidationError(
                f"Each item in {field_name} must be a DomainStatus or string, got {type(item).__name__} at index {i}",
                field=field_name,
                details={"index": i},
            )
        if status.value not in seen:
            seen.add(status.value)
            result.append(status)
    return tuple(result)


def _freeze_query_str_tuple(
    seq: Any, field_name: str, *, allow_empty: bool = True, require_unique: bool = False
) -> tuple[str, ...]:
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
    result = []
    for i, item in enumerate(seq):
        if not isinstance(item, str) or not item.strip():
            raise DomainContractValidationError(
                f"All items in {field_name} must be non-empty strings",
                field=field_name,
                details={"index": i, "value": item},
            )
        result.append(item.strip())
    if require_unique and len(set(result)) != len(result):
        raise DomainContractValidationError(
            f"Duplicate items in {field_name}", field=field_name
        )
    return tuple(result)


# ── DomainValidationResult ─────────────────────────────────────────────────────

_VALIDATION_KNOWN = frozenset(
    {
        "domain_id",
        "version",
        "valid",
        "errors",
        "warnings",
        "missing_dependencies",
        "conflicts",
        "checked_at",
        "metadata",
    }
)


@dataclass(frozen=True, slots=True)
class DomainValidationResult:
    domain_id: str
    version: str
    valid: bool
    errors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    missing_dependencies: tuple[str, ...] = ()
    conflicts: tuple[str, ...] = ()
    checked_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: MappingProxyType[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "domain_id", _validate_non_empty_str(self.domain_id, "domain_id")
        )
        object.__setattr__(
            self, "version", _validate_non_empty_str(self.version, "version")
        )
        object.__setattr__(self, "valid", _validate_strict_bool(self.valid, "valid"))
        for attr in ("errors", "warnings", "missing_dependencies", "conflicts"):
            object.__setattr__(
                self,
                attr,
                _freeze_str_tuple(getattr(self, attr), attr, require_unique=True),
            )
        object.__setattr__(
            self, "checked_at", _ensure_tz_aware(self.checked_at, "checked_at")
        )
        if self.checked_at.tzinfo != timezone.utc:
            object.__setattr__(
                self, "checked_at", self.checked_at.astimezone(timezone.utc)
            )
        if self.valid:
            if self.errors:
                raise DomainContractValidationError(
                    "valid=True but errors are present",
                    field="errors",
                    details={"errors": list(self.errors)},
                )
            if self.missing_dependencies:
                raise DomainContractValidationError(
                    "valid=True but missing_dependencies are present",
                    field="missing_dependencies",
                    details={"missing": list(self.missing_dependencies)},
                )
            if self.conflicts:
                raise DomainContractValidationError(
                    "valid=True but conflicts are present",
                    field="conflicts",
                    details={"conflicts": list(self.conflicts)},
                )
        meta = _validate_json_safe_metadata(self.metadata, "metadata")
        _reject_sensitive_keys(meta, "metadata")
        object.__setattr__(self, "metadata", meta)

    def to_dict(self) -> dict[str, Any]:
        return {
            "domain_id": self.domain_id,
            "version": self.version,
            "valid": self.valid,
            "errors": list(self.errors),
            "warnings": list(self.warnings),
            "missing_dependencies": list(self.missing_dependencies),
            "conflicts": list(self.conflicts),
            "checked_at": self.checked_at.isoformat(),
            "metadata": _deep_unfreeze(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DomainValidationResult:
        if not isinstance(data, Mapping):
            raise DomainSerializationError(
                "DomainValidationResult.from_dict requires a mapping", field="data"
            )
        _reject_unknown_fields(data, _VALIDATION_KNOWN, "DomainValidationResult")
        required = {"domain_id", "version", "valid", "checked_at"}
        missing = required - set(data.keys())
        if missing:
            raise DomainSerializationError(
                f"DomainValidationResult.from_dict missing required fields: {sorted(missing)}",
                field="data",
            )
        domain_id = _require_non_empty_str(
            data["domain_id"], "domain_id", "DomainValidationResult"
        )
        version = _require_non_empty_str(
            data["version"], "version", "DomainValidationResult"
        )
        try:
            parse_semver(version)
        except DomainContractValidationError as exc:
            raise DomainSerializationError(
                f"DomainValidationResult.from_dict: version must be a valid semver: {version!r}",
                field="version",
                details={"version": version},
            ) from exc
        valid = _require_strict_bool(data["valid"], "valid", "DomainValidationResult")
        checked_at = _parse_tz_aware_datetime(
            data["checked_at"], "checked_at", "DomainValidationResult"
        )
        return cls(
            domain_id=domain_id,
            version=version,
            valid=valid,
            errors=_require_str_tuple(
                data.get("errors"), "errors", "DomainValidationResult"
            ),
            warnings=_require_str_tuple(
                data.get("warnings"), "warnings", "DomainValidationResult"
            ),
            missing_dependencies=_require_str_tuple(
                data.get("missing_dependencies"),
                "missing_dependencies",
                "DomainValidationResult",
            ),
            conflicts=_require_str_tuple(
                data.get("conflicts"), "conflicts", "DomainValidationResult"
            ),
            checked_at=checked_at,
            metadata=data.get("metadata"),
        )


# ── DomainRegistrySnapshot ─────────────────────────────────────────────────────

_SNAPSHOT_KNOWN = frozenset({"captured_at", "records", "snapshot_version"})


@dataclass(frozen=True, slots=True)
class DomainRegistrySnapshot:
    captured_at: datetime
    records: tuple[DomainRegistryRecord, ...]
    snapshot_version: str = "10.3.0"

    @property
    def definitions(self) -> tuple[DomainDefinition, ...]:
        return tuple(r.definition for r in self.records)

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "captured_at", _ensure_tz_aware(self.captured_at, "captured_at")
        )
        if self.captured_at.tzinfo != timezone.utc:
            object.__setattr__(
                self, "captured_at", self.captured_at.astimezone(timezone.utc)
            )
        object.__setattr__(
            self,
            "snapshot_version",
            _validate_non_empty_str(self.snapshot_version, "snapshot_version"),
        )
        if isinstance(self.records, (list, tuple)):
            sorted_records = tuple(
                sorted(self.records, key=cmp_to_key(_compare_records))
            )
            object.__setattr__(self, "records", sorted_records)
        else:
            raise DomainContractValidationError(
                "records must be a list or tuple", field="records"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "captured_at": self.captured_at.isoformat(),
            "records": [r.to_dict() for r in self.records],
            "snapshot_version": self.snapshot_version,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DomainRegistrySnapshot:
        if not isinstance(data, Mapping):
            raise DomainSerializationError(
                "DomainRegistrySnapshot.from_dict requires a mapping", field="data"
            )
        _reject_unknown_fields(data, _SNAPSHOT_KNOWN, "DomainRegistrySnapshot")
        required = {"captured_at", "records"}
        missing = required - set(data.keys())
        if missing:
            raise DomainSerializationError(
                f"DomainRegistrySnapshot.from_dict missing required fields: {sorted(missing)}",
                field="data",
            )
        captured_at = _parse_tz_aware_datetime(
            data["captured_at"], "captured_at", "DomainRegistrySnapshot"
        )
        records_raw = data["records"]
        if not isinstance(records_raw, (list, tuple)):
            raise DomainSerializationError("records must be a list", field="records")
        records: list[DomainRegistryRecord] = []
        for i, item in enumerate(records_raw):
            if not isinstance(item, Mapping):
                raise DomainSerializationError(
                    f"Each item in records must be a mapping, got {type(item).__name__} at index {i}",
                    field=f"records[{i}]",
                )
            try:
                records.append(DomainRegistryRecord.from_dict(dict(item)))
            except DomainSerializationError:
                raise
            except Exception as exc:
                raise DomainSerializationError(
                    f"Failed to parse record at index {i}",
                    field=f"records[{i}]",
                    details={"error": type(exc).__name__},
                ) from exc
        return cls(
            captured_at=captured_at,
            records=tuple(records),
            snapshot_version=data.get("snapshot_version", "10.3.0"),
        )


_SORT_PRIORITY_ENABLED_STATUS: dict[str, int] = {
    DomainStatus.ACTIVE.value: 0,
    DomainStatus.REGISTERED.value: 1,
    DomainStatus.DISABLED.value: 2,
    DomainStatus.DEGRADED.value: 3,
    DomainStatus.DISCOVERED.value: 4,
    DomainStatus.INCOMPATIBLE.value: 5,
    DomainStatus.INVALID.value: 6,
    DomainStatus.FAILED.value: 7,
    DomainStatus.UNLOADED.value: 8,
    DomainStatus.LOADING.value: 9,
}


def get_status_sort_priority(status: DomainStatus) -> int:
    return _SORT_PRIORITY_ENABLED_STATUS.get(status.value, 100)


__all__ = [
    "_ENABLED_STATUSES",
    "DomainQuery",
    "DomainRegistryRecord",
    "DomainRegistrySnapshot",
    "DomainRegistryStoreSnapshot",
    "DomainValidationResult",
    "_canonical_slug",
    "_compare_records",
    "_compare_versions_desc_safe",
    "compare_versions_desc",
    "get_status_sort_priority",
    "parse_semver",
]
