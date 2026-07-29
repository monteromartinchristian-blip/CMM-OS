"""Phase 10.1 – Domain Contracts.

Immutable, JSON-serializable, type-safe contracts for the Domain Intelligence subsystem.

All dataclasses are ``frozen=True`` and never expose mutable internal state.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from types import MappingProxyType
from typing import Any

from cmm.domains.enums import DomainKind
from cmm.domains.errors import (
    DomainContractValidationError,
    DomainError,
    DomainSerializationError,
)
from cmm.domains.identifiers import (
    DomainId,
    DomainManifestId,
    DomainResultId,
)

# ── Deep freeze / unfreeze helpers ────────────────────────────────────────────


def _deep_freeze(value: Any) -> Any:
    """Recursively freeze value: dict → MappingProxyType, list/tuple → tuple, set → frozenset."""
    if isinstance(value, dict):
        for k in value:
            if not isinstance(k, str):
                raise DomainContractValidationError(
                    "Metadata keys must be strings", field="metadata"
                )
        return MappingProxyType({k: _deep_freeze(v) for k, v in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_deep_freeze(v) for v in value)
    if isinstance(value, (set, frozenset)):
        return frozenset(_deep_freeze(v) for v in value)
    return value


def _deep_unfreeze(value: Any) -> Any:
    """Reverse _deep_freeze for serialization: MappingProxyType → dict, tuple → list, frozenset → sorted list."""
    if isinstance(value, MappingProxyType):
        return {k: _deep_unfreeze(v) for k, v in value.items()}
    if isinstance(value, tuple):
        return [_deep_unfreeze(v) for v in value]
    if isinstance(value, frozenset):
        return sorted([_deep_unfreeze(v) for v in value], key=str)
    return value


# ── Validation helpers ────────────────────────────────────────────────────────


def _validate_non_empty_str(val: Any, field_name: str) -> str:
    """Validate that value is a non-empty string."""
    if not isinstance(val, str) or not val.strip():
        raise DomainContractValidationError(
            f"{field_name} must be a non-empty string", field=field_name
        )
    return val.strip()


def _validate_strict_bool(val: Any, field_name: str) -> bool:
    """Validate that value is exactly a bool (not int 0/1, not string)."""
    if not isinstance(val, bool):
        raise DomainContractValidationError(
            f"{field_name} must be a boolean (True or False), got {type(val).__name__}: {val!r}",
            field=field_name,
        )
    return val


def _validate_strict_bool_opt(val: Any, field_name: str) -> bool | None:
    """Validate optional boolean: accept None or strict bool."""
    if val is None:
        return None
    return _validate_strict_bool(val, field_name)


def _validate_strict_confidence(val: Any, field_name: str) -> float:
    """Validate confidence: must be int (not bool) or finite float in [0.0, 1.0]."""
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


def _validate_strict_confidence_from_dict(val: Any, field_name: str) -> float:
    """Like _validate_strict_confidence but raises DomainSerializationError for from_dict context."""
    try:
        return _validate_strict_confidence(val, field_name)
    except DomainContractValidationError as exc:
        raise DomainSerializationError(
            exc.message, field=exc.field, details=dict(exc.details)
        ) from exc


def _ensure_tz_aware(dt: datetime, field_name: str) -> datetime:
    """Ensure datetime is timezone-aware."""
    if not isinstance(dt, datetime):
        raise DomainContractValidationError(
            f"{field_name} must be a datetime instance", field=field_name
        )
    if dt.tzinfo is None:
        raise DomainContractValidationError(
            f"{field_name} must be timezone-aware", field=field_name
        )
    return dt


def _parse_datetime_opt(val: Any, field_name: str) -> datetime | None:
    """Parse string or datetime to timezone-aware datetime or None."""
    if val is None:
        return None
    if isinstance(val, datetime):
        return _ensure_tz_aware(val, field_name)
    if isinstance(val, str):
        try:
            parsed = datetime.fromisoformat(val)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed
        except ValueError as exc:
            raise DomainContractValidationError(
                f"Invalid isoformat datetime string for {field_name}: {val!r}",
                field=field_name,
            ) from exc
    raise DomainContractValidationError(
        f"{field_name} must be an ISO string or datetime instance, got {type(val).__name__}",
        field=field_name,
    )


def _normalize_empty_to_none(val: str | None) -> str | None:
    """Convert empty string to None."""
    if val is not None and isinstance(val, str) and not val.strip():
        return None
    return val


def _reject_unknown_fields(
    data: Mapping[str, Any], known: frozenset[str], cls_name: str
) -> None:
    """Raise DomainSerializationError if data contains unknown fields."""
    unknown = set(data.keys()) - known
    if unknown:
        raise DomainSerializationError(
            f"{cls_name}.from_dict got unknown fields: {sorted(unknown)}",
            field="data",
            details={"unknown_fields": sorted(unknown)},
        )


def _wrap_nested_error(
    exc: Exception, parent_field: str, index: int | None = None
) -> DomainError:
    """Wrap a nested error preserving original code, message, field, and details with contextual path."""
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
            raise DomainContractValidationError(
                exc.message, field=full_path, details=original_details
            ) from exc
        if isinstance(exc, DomainSerializationError):
            raise DomainSerializationError(
                exc.message, field=full_path, details=original_details
            ) from exc
        raise DomainError(
            exc.message, field=full_path, details=original_details
        ) from exc
    # Non-DomainError: wrap generically
    raise DomainSerializationError(
        f"Invalid nested value in {parent_field}: {exc}",
        field=parent_field,
        details={"error": str(exc)},
    ) from exc


# ── String freeze helpers ─────────────────────────────────────────────────────


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


# ── DomainMetadata ────────────────────────────────────────────────────────────

_METADATA_KNOWN = frozenset(
    {
        "author",
        "license",
        "homepage",
        "repository",
        "created_at",
        "updated_at",
        "minimum_cmm_version",
        "maximum_cmm_version",
        "tags",
        "experimental",
        "deprecated",
        "metadata",
    }
)


@dataclass(frozen=True, slots=True)
class DomainMetadata:
    """Immutable metadata for a domain."""

    author: str
    license: str
    homepage: str | None = None
    repository: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    minimum_cmm_version: str | None = None
    maximum_cmm_version: str | None = None
    tags: tuple[str, ...] = ()
    experimental: bool = False
    deprecated: bool = False
    metadata: MappingProxyType[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "author", _validate_non_empty_str(self.author, "author")
        )
        object.__setattr__(
            self, "license", _validate_non_empty_str(self.license, "license")
        )
        object.__setattr__(self, "homepage", _normalize_empty_to_none(self.homepage))
        object.__setattr__(
            self, "repository", _normalize_empty_to_none(self.repository)
        )

        if self.created_at is not None:
            object.__setattr__(
                self, "created_at", _ensure_tz_aware(self.created_at, "created_at")
            )
        if self.updated_at is not None:
            object.__setattr__(
                self, "updated_at", _ensure_tz_aware(self.updated_at, "updated_at")
            )
            if self.created_at is not None and self.updated_at < self.created_at:
                raise DomainContractValidationError(
                    "updated_at cannot be prior to created_at", field="updated_at"
                )

        object.__setattr__(
            self,
            "minimum_cmm_version",
            _normalize_empty_to_none(self.minimum_cmm_version),
        )
        object.__setattr__(
            self,
            "maximum_cmm_version",
            _normalize_empty_to_none(self.maximum_cmm_version),
        )

        # Tags
        object.__setattr__(
            self, "tags", _freeze_str_tuple(self.tags, "tags", require_unique=True)
        )

        # Strict booleans
        object.__setattr__(
            self,
            "experimental",
            _validate_strict_bool(self.experimental, "experimental"),
        )
        object.__setattr__(
            self, "deprecated", _validate_strict_bool(self.deprecated, "deprecated")
        )

        # Deep-freeze metadata
        object.__setattr__(self, "metadata", _deep_freeze(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "author": self.author,
            "license": self.license,
            "homepage": self.homepage,
            "repository": self.repository,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "minimum_cmm_version": self.minimum_cmm_version,
            "maximum_cmm_version": self.maximum_cmm_version,
            "tags": list(self.tags),
            "experimental": self.experimental,
            "deprecated": self.deprecated,
            "metadata": _deep_unfreeze(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DomainMetadata:
        """Deserialize from dictionary."""
        if not isinstance(data, Mapping):
            raise DomainSerializationError(
                "DomainMetadata.from_dict requires a mapping", field="data"
            )
        _reject_unknown_fields(data, _METADATA_KNOWN, "DomainMetadata")
        required = {"author", "license"}
        missing = required - set(data.keys())
        if missing:
            raise DomainSerializationError(
                f"DomainMetadata.from_dict missing required fields: {sorted(missing)}",
                field="data",
            )

        # Strict bool validation for from_dict
        exp_raw = data.get("experimental")
        dep_raw = data.get("deprecated")
        try:
            experimental = (
                _validate_strict_bool(exp_raw, "experimental")
                if exp_raw is not None
                else False
            )
        except DomainContractValidationError as exc:
            raise DomainSerializationError(
                exc.message, field=exc.field, details=dict(exc.details)
            ) from exc
        try:
            deprecated = (
                _validate_strict_bool(dep_raw, "deprecated")
                if dep_raw is not None
                else False
            )
        except DomainContractValidationError as exc:
            raise DomainSerializationError(
                exc.message, field=exc.field, details=dict(exc.details)
            ) from exc

        return cls(
            author=str(data["author"]),
            license=str(data["license"]),
            homepage=data.get("homepage"),
            repository=data.get("repository"),
            created_at=_parse_datetime_opt(data.get("created_at"), "created_at"),
            updated_at=_parse_datetime_opt(data.get("updated_at"), "updated_at"),
            minimum_cmm_version=data.get("minimum_cmm_version"),
            maximum_cmm_version=data.get("maximum_cmm_version"),
            tags=tuple(data.get("tags", ())),
            experimental=experimental,
            deprecated=deprecated,
            metadata=_deep_freeze(data.get("metadata")),
        )


# ── DomainCapability ──────────────────────────────────────────────────────────

_CAPABILITY_KNOWN = frozenset(
    {
        "name",
        "kind",
        "provided_by",
        "version",
        "requirements",
        "permissions",
        "metadata",
    }
)


@dataclass(frozen=True, slots=True)
class DomainCapability:
    """A named capability provided by a domain."""

    name: str
    kind: str
    provided_by: DomainId
    version: str
    requirements: tuple[str, ...] = ()
    permissions: tuple[str, ...] = ()
    metadata: MappingProxyType[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", _validate_non_empty_str(self.name, "name"))
        object.__setattr__(self, "kind", _validate_non_empty_str(self.kind, "kind"))
        object.__setattr__(
            self, "version", _validate_non_empty_str(self.version, "version")
        )

        if isinstance(self.provided_by, str):
            object.__setattr__(self, "provided_by", DomainId.from_str(self.provided_by))
        elif not isinstance(self.provided_by, DomainId):
            raise DomainContractValidationError(
                "provided_by must be a DomainId instance or canonical string",
                field="provided_by",
            )

        object.__setattr__(
            self,
            "requirements",
            _freeze_str_tuple(self.requirements, "requirements", require_unique=True),
        )
        object.__setattr__(
            self,
            "permissions",
            _freeze_str_tuple(self.permissions, "permissions", require_unique=True),
        )
        object.__setattr__(self, "metadata", _deep_freeze(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "name": self.name,
            "kind": self.kind,
            "provided_by": str(self.provided_by),
            "version": self.version,
            "requirements": list(self.requirements),
            "permissions": list(self.permissions),
            "metadata": _deep_unfreeze(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DomainCapability:
        """Deserialize from dictionary."""
        if not isinstance(data, Mapping):
            raise DomainSerializationError(
                "DomainCapability.from_dict requires a mapping", field="data"
            )
        _reject_unknown_fields(data, _CAPABILITY_KNOWN, "DomainCapability")
        required = {"name", "kind", "provided_by", "version"}
        missing = required - set(data.keys())
        if missing:
            raise DomainSerializationError(
                f"DomainCapability.from_dict missing required fields: {sorted(missing)}",
                field="data",
            )
        return cls(
            name=str(data["name"]),
            kind=str(data["kind"]),
            provided_by=str(data["provided_by"]),
            version=str(data["version"]),
            requirements=tuple(data.get("requirements", ())),
            permissions=tuple(data.get("permissions", ())),
            metadata=_deep_freeze(data.get("metadata")),
        )


# ── DomainDependency ──────────────────────────────────────────────────────────

_DEPENDENCY_KNOWN = frozenset(
    {"domain_id", "version_constraint", "required", "reason", "metadata"}
)


@dataclass(frozen=True, slots=True)
class DomainDependency:
    """A dependency relationship from one domain to another."""

    domain_id: DomainId
    version_constraint: str | None = None
    required: bool = True
    reason: str | None = None
    metadata: MappingProxyType[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )

    def __post_init__(self) -> None:
        if isinstance(self.domain_id, str):
            object.__setattr__(self, "domain_id", DomainId.from_str(self.domain_id))
        elif not isinstance(self.domain_id, DomainId):
            raise DomainContractValidationError(
                "domain_id must be a DomainId instance or canonical string",
                field="domain_id",
            )

        object.__setattr__(
            self,
            "version_constraint",
            _normalize_empty_to_none(self.version_constraint),
        )
        object.__setattr__(self, "reason", _normalize_empty_to_none(self.reason))

        # Strict bool
        object.__setattr__(
            self, "required", _validate_strict_bool(self.required, "required")
        )

        object.__setattr__(self, "metadata", _deep_freeze(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "domain_id": str(self.domain_id),
            "version_constraint": self.version_constraint,
            "required": self.required,
            "reason": self.reason,
            "metadata": _deep_unfreeze(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DomainDependency:
        """Deserialize from dictionary."""
        if not isinstance(data, Mapping):
            raise DomainSerializationError(
                "DomainDependency.from_dict requires a mapping", field="data"
            )
        _reject_unknown_fields(data, _DEPENDENCY_KNOWN, "DomainDependency")
        if "domain_id" not in data:
            raise DomainSerializationError(
                "DomainDependency.from_dict missing required field 'domain_id'",
                field="domain_id",
            )

        # Strict bool from_dict
        req_raw = data.get("required")
        if req_raw is not None:
            try:
                required = _validate_strict_bool(req_raw, "required")
            except DomainContractValidationError as exc:
                raise DomainSerializationError(
                    exc.message, field=exc.field, details=dict(exc.details)
                ) from exc
        else:
            required = True

        return cls(
            domain_id=str(data["domain_id"]),
            version_constraint=data.get("version_constraint"),
            required=required,
            reason=data.get("reason"),
            metadata=_deep_freeze(data.get("metadata")),
        )


# ── DomainConflict ────────────────────────────────────────────────────────────

_CONFLICT_KNOWN = frozenset({"domain_id", "reason", "severity", "metadata"})


@dataclass(frozen=True, slots=True)
class DomainConflict:
    """A known incompatibility with another domain."""

    domain_id: DomainId
    reason: str
    severity: str
    metadata: MappingProxyType[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )

    def __post_init__(self) -> None:
        if isinstance(self.domain_id, str):
            object.__setattr__(self, "domain_id", DomainId.from_str(self.domain_id))
        elif not isinstance(self.domain_id, DomainId):
            raise DomainContractValidationError(
                "domain_id must be a DomainId instance or canonical string",
                field="domain_id",
            )
        object.__setattr__(
            self, "reason", _validate_non_empty_str(self.reason, "reason")
        )
        object.__setattr__(
            self, "severity", _validate_non_empty_str(self.severity, "severity")
        )
        object.__setattr__(self, "metadata", _deep_freeze(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "domain_id": str(self.domain_id),
            "reason": self.reason,
            "severity": self.severity,
            "metadata": _deep_unfreeze(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DomainConflict:
        """Deserialize from dictionary."""
        if not isinstance(data, Mapping):
            raise DomainSerializationError(
                "DomainConflict.from_dict requires a mapping", field="data"
            )
        _reject_unknown_fields(data, _CONFLICT_KNOWN, "DomainConflict")
        required = {"domain_id", "reason", "severity"}
        missing = required - set(data.keys())
        if missing:
            raise DomainSerializationError(
                f"DomainConflict.from_dict missing required fields: {sorted(missing)}",
                field="data",
            )
        return cls(
            domain_id=str(data["domain_id"]),
            reason=str(data["reason"]),
            severity=str(data["severity"]),
            metadata=_deep_freeze(data.get("metadata")),
        )


# ── DomainDefinition ─────────────────────────────────────────────────────────

_DEFINITION_KNOWN = frozenset(
    {
        "id",
        "name",
        "display_name",
        "version",
        "kind",
        "description",
        "manifest_id",
        "reasoning_profile",
        "resources",
        "rules",
        "operations",
        "workflows",
        "permissions",
        "validators",
        "presentation_policy",
        "dependencies",
        "optional_dependencies",
        "conflicts",
        "capabilities",
        "enabled",
        "metadata",
    }
)


@dataclass(frozen=True, slots=True)
class DomainDefinition:
    """Full immutable definition of a domain."""

    id: DomainId
    name: str
    display_name: str
    version: str
    kind: DomainKind
    description: str
    manifest_id: DomainManifestId
    reasoning_profile: str | None = None
    resources: tuple[str, ...] = ()
    rules: tuple[str, ...] = ()
    operations: tuple[str, ...] = ()
    workflows: tuple[str, ...] = ()
    permissions: tuple[str, ...] = ()
    validators: tuple[str, ...] = ()
    presentation_policy: MappingProxyType[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )
    dependencies: tuple[DomainDependency, ...] = ()
    optional_dependencies: tuple[DomainDependency, ...] = ()
    conflicts: tuple[DomainConflict, ...] = ()
    capabilities: tuple[DomainCapability, ...] = ()
    enabled: bool = True
    metadata: DomainMetadata | None = None

    def __post_init__(self) -> None:
        # ── Coerce string ids ────────────────────────────────────────────
        if isinstance(self.id, str):
            object.__setattr__(self, "id", DomainId.from_str(self.id))
        elif not isinstance(self.id, DomainId):
            raise DomainContractValidationError(
                "id must be a DomainId instance or canonical string", field="id"
            )

        if isinstance(self.manifest_id, str):
            if not self.manifest_id.startswith("manifest:"):
                raise DomainContractValidationError(
                    f"manifest_id must start with 'manifest:': {self.manifest_id!r}",
                    field="manifest_id",
                )
            rest = self.manifest_id[len("manifest:") :]
            parts = rest.split(":")
            if len(parts) < 2:
                raise DomainContractValidationError(
                    f"manifest_id must have format manifest:<slug>:<version>: {self.manifest_id!r}",
                    field="manifest_id",
                )
            slug_part = parts[0]
            version_part = ":".join(parts[1:])
            object.__setattr__(
                self,
                "manifest_id",
                DomainManifestId(slug=slug_part, version=version_part),
            )
        elif not isinstance(self.manifest_id, DomainManifestId):
            raise DomainContractValidationError(
                "manifest_id must be a DomainManifestId instance or canonical string",
                field="manifest_id",
            )

        # ── Textual fields ───────────────────────────────────────────────
        object.__setattr__(self, "name", _validate_non_empty_str(self.name, "name"))
        object.__setattr__(
            self,
            "display_name",
            _validate_non_empty_str(self.display_name, "display_name"),
        )
        object.__setattr__(
            self, "version", _validate_non_empty_str(self.version, "version")
        )
        object.__setattr__(
            self,
            "description",
            _validate_non_empty_str(self.description, "description"),
        )

        # ── Coerce kind ──────────────────────────────────────────────────
        if isinstance(self.kind, str):
            try:
                object.__setattr__(self, "kind", DomainKind(self.kind))
            except ValueError as exc:
                raise DomainContractValidationError(
                    f"Invalid DomainKind: {self.kind!r}", field="kind"
                ) from exc
        elif not isinstance(self.kind, DomainKind):
            raise DomainContractValidationError(
                f"kind must be a DomainKind, got {type(self.kind).__name__}",
                field="kind",
            )

        # ── Optional reasoning_profile ───────────────────────────────────
        object.__setattr__(
            self, "reasoning_profile", _normalize_empty_to_none(self.reasoning_profile)
        )

        # ── String collections ───────────────────────────────────────────
        for attr_name in (
            "resources",
            "rules",
            "operations",
            "workflows",
            "permissions",
            "validators",
        ):
            object.__setattr__(
                self,
                attr_name,
                _freeze_str_tuple(
                    getattr(self, attr_name), attr_name, require_unique=True
                ),
            )

        # ── Presentation policy ──────────────────────────────────────────
        object.__setattr__(
            self, "presentation_policy", _deep_freeze(self.presentation_policy)
        )

        # ── Dependencies ─────────────────────────────────────────────────
        deps = _coerce_dependency_tuple(self.dependencies, "dependencies")
        opt_deps = _coerce_dependency_tuple(
            self.optional_dependencies, "optional_dependencies"
        )
        object.__setattr__(self, "dependencies", deps)
        object.__setattr__(self, "optional_dependencies", opt_deps)

        # Check uniqueness across required and optional
        dep_ids = set()
        for dep in deps:
            dep_ids.add(dep.domain_id.slug)
        for dep in opt_deps:
            if dep.domain_id.slug in dep_ids:
                raise DomainContractValidationError(
                    f"Domain {dep.domain_id.slug} appears in both dependencies and optional_dependencies",
                    field="optional_dependencies",
                )

        # Required deps must have required=True
        for dep in deps:
            if not dep.required:
                raise DomainContractValidationError(
                    f"Required dependency {dep.domain_id.slug} must have required=True",
                    field="dependencies",
                )
        for dep in opt_deps:
            if dep.required:
                raise DomainContractValidationError(
                    f"Optional dependency {dep.domain_id.slug} must have required=False",
                    field="optional_dependencies",
                )

        # No self-dependency
        for dep in deps:
            if dep.domain_id.slug == self.id.slug:
                raise DomainContractValidationError(
                    f"Domain cannot depend on itself: {self.id.slug}",
                    field="dependencies",
                )
        for dep in opt_deps:
            if dep.domain_id.slug == self.id.slug:
                raise DomainContractValidationError(
                    f"Domain cannot depend on itself: {self.id.slug}",
                    field="optional_dependencies",
                )

        # ── Conflicts ────────────────────────────────────────────────────
        conflict_list = _coerce_conflict_tuple(self.conflicts, "conflicts")
        conflict_slugs = set()
        for c in conflict_list:
            if c.domain_id.slug == self.id.slug:
                raise DomainContractValidationError(
                    f"Domain cannot conflict with itself: {self.id.slug}",
                    field="conflicts",
                )
            if c.domain_id.slug in conflict_slugs:
                raise DomainContractValidationError(
                    f"Duplicate conflict for domain {c.domain_id.slug}",
                    field="conflicts",
                )
            conflict_slugs.add(c.domain_id.slug)
        object.__setattr__(self, "conflicts", conflict_list)

        # ── Capabilities ─────────────────────────────────────────────────
        caps = _coerce_capability_tuple(self.capabilities, "capabilities")
        for cap in caps:
            if cap.provided_by.slug != self.id.slug:
                raise DomainContractValidationError(
                    f"Capability '{cap.name}' provided_by {cap.provided_by.slug} must match domain id {self.id.slug}",
                    field="capabilities",
                )
        object.__setattr__(self, "capabilities", caps)

        # ── Coherence checks ─────────────────────────────────────────────
        if self.name != self.id.slug:
            raise DomainContractValidationError(
                f"name '{self.name}' must match domain id slug '{self.id.slug}'",
                field="name",
            )

        if self.manifest_id.slug != self.id.slug:
            raise DomainContractValidationError(
                f"manifest_id slug '{self.manifest_id.slug}' must match domain id slug '{self.id.slug}'",
                field="manifest_id",
            )

        if self.manifest_id.version != self.version:
            raise DomainContractValidationError(
                f"manifest_id version '{self.manifest_id.version}' must match domain version '{self.version}'",
                field="manifest_id",
            )

        # Strict bool
        object.__setattr__(
            self, "enabled", _validate_strict_bool(self.enabled, "enabled")
        )

        # Metadata: None or DomainMetadata (coerce from mapping)
        if self.metadata is not None and not isinstance(self.metadata, DomainMetadata):
            if isinstance(self.metadata, Mapping):
                try:
                    object.__setattr__(
                        self, "metadata", DomainMetadata.from_dict(dict(self.metadata))
                    )
                except DomainError as exc:
                    _wrap_nested_error(exc, "metadata")
            else:
                raise DomainContractValidationError(
                    f"metadata must be DomainMetadata or mapping, got {type(self.metadata).__name__}",
                    field="metadata",
                )

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "id": str(self.id),
            "name": self.name,
            "display_name": self.display_name,
            "version": self.version,
            "kind": self.kind.value,
            "description": self.description,
            "manifest_id": str(self.manifest_id),
            "reasoning_profile": self.reasoning_profile,
            "resources": list(self.resources),
            "rules": list(self.rules),
            "operations": list(self.operations),
            "workflows": list(self.workflows),
            "permissions": list(self.permissions),
            "validators": list(self.validators),
            "presentation_policy": _deep_unfreeze(self.presentation_policy),
            "dependencies": [d.to_dict() for d in self.dependencies],
            "optional_dependencies": [d.to_dict() for d in self.optional_dependencies],
            "conflicts": [c.to_dict() for c in self.conflicts],
            "capabilities": [c.to_dict() for c in self.capabilities],
            "enabled": self.enabled,
            "metadata": self.metadata.to_dict() if self.metadata else None,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DomainDefinition:
        """Deserialize from dictionary."""
        if not isinstance(data, Mapping):
            raise DomainSerializationError(
                "DomainDefinition.from_dict requires a mapping", field="data"
            )
        _reject_unknown_fields(data, _DEFINITION_KNOWN, "DomainDefinition")
        required = {
            "id",
            "name",
            "display_name",
            "version",
            "kind",
            "description",
            "manifest_id",
        }
        missing = required - set(data.keys())
        if missing:
            raise DomainSerializationError(
                f"DomainDefinition.from_dict missing required fields: {sorted(missing)}",
                field="data",
            )

        def _parse_deps(raw: Any, field_label: str) -> tuple[DomainDependency, ...]:
            if raw is None:
                return ()
            if not isinstance(raw, (list, tuple)):
                raise DomainSerializationError(
                    f"{field_label} must be a list", field=field_label
                )
            result = []
            for i, item in enumerate(raw):
                if not isinstance(item, Mapping):
                    raise DomainSerializationError(
                        f"Each item in {field_label} must be a mapping, got {type(item).__name__} at index {i}",
                        field=f"{field_label}[{i}]",
                    )
                try:
                    result.append(DomainDependency.from_dict(dict(item)))
                except DomainError as exc:
                    _wrap_nested_error(exc, field_label, i)
            return tuple(result)

        def _parse_conflicts(raw: Any, field_label: str) -> tuple[DomainConflict, ...]:
            if raw is None:
                return ()
            if not isinstance(raw, (list, tuple)):
                raise DomainSerializationError(
                    f"{field_label} must be a list", field=field_label
                )
            result = []
            for i, item in enumerate(raw):
                if not isinstance(item, Mapping):
                    raise DomainSerializationError(
                        f"Each item in {field_label} must be a mapping, got {type(item).__name__} at index {i}",
                        field=f"{field_label}[{i}]",
                    )
                try:
                    result.append(DomainConflict.from_dict(dict(item)))
                except DomainError as exc:
                    _wrap_nested_error(exc, field_label, i)
            return tuple(result)

        def _parse_caps(raw: Any, field_label: str) -> tuple[DomainCapability, ...]:
            if raw is None:
                return ()
            if not isinstance(raw, (list, tuple)):
                raise DomainSerializationError(
                    f"{field_label} must be a list", field=field_label
                )
            result = []
            for i, item in enumerate(raw):
                if not isinstance(item, Mapping):
                    raise DomainSerializationError(
                        f"Each item in {field_label} must be a mapping, got {type(item).__name__} at index {i}",
                        field=f"{field_label}[{i}]",
                    )
                try:
                    result.append(DomainCapability.from_dict(dict(item)))
                except DomainError as exc:
                    _wrap_nested_error(exc, field_label, i)
            return tuple(result)

        # Validate metadata field: absent/None → None, mapping → parse, other → error
        meta_raw = data.get("metadata")
        metadata: DomainMetadata | None = None
        if meta_raw is not None:
            if not isinstance(meta_raw, Mapping):
                raise DomainSerializationError(
                    f"metadata must be a mapping or None, got {type(meta_raw).__name__}",
                    field="metadata",
                )
            try:
                metadata = DomainMetadata.from_dict(dict(meta_raw))
            except DomainError as exc:
                _wrap_nested_error(exc, "metadata")

        # Strict bool for enabled
        enabled_raw = data.get("enabled")
        if enabled_raw is not None:
            try:
                enabled = _validate_strict_bool(enabled_raw, "enabled")
            except DomainContractValidationError as exc:
                raise DomainSerializationError(
                    exc.message, field=exc.field, details=dict(exc.details)
                ) from exc
        else:
            enabled = True

        return cls(
            id=str(data["id"]),
            name=str(data["name"]),
            display_name=str(data["display_name"]),
            version=str(data["version"]),
            kind=str(data["kind"]),
            description=str(data["description"]),
            manifest_id=str(data["manifest_id"]),
            reasoning_profile=data.get("reasoning_profile"),
            resources=tuple(data.get("resources", ())),
            rules=tuple(data.get("rules", ())),
            operations=tuple(data.get("operations", ())),
            workflows=tuple(data.get("workflows", ())),
            permissions=tuple(data.get("permissions", ())),
            validators=tuple(data.get("validators", ())),
            presentation_policy=_deep_freeze(data.get("presentation_policy")),
            dependencies=_parse_deps(data.get("dependencies"), "dependencies"),
            optional_dependencies=_parse_deps(
                data.get("optional_dependencies"), "optional_dependencies"
            ),
            conflicts=_parse_conflicts(data.get("conflicts"), "conflicts"),
            capabilities=_parse_caps(data.get("capabilities"), "capabilities"),
            enabled=enabled,
            metadata=metadata,
        )


# ── DomainResult ──────────────────────────────────────────────────────────────

_RESULT_KNOWN = frozenset(
    {
        "id",
        "status",
        "objective",
        "primary_domain",
        "supporting_domains",
        "reasoning_result_id",
        "workflow_result_id",
        "operation_result_ids",
        "findings",
        "recommendations",
        "approval_ids",
        "confidence",
        "trace_id",
        "session_id",
        "created_at",
        "metadata",
    }
)


@dataclass(frozen=True, slots=True)
class DomainResult:
    """Result produced by domain intelligence operations."""

    id: DomainResultId
    status: str
    objective: str
    primary_domain: DomainId
    supporting_domains: tuple[DomainId, ...] = ()
    reasoning_result_id: str | None = None
    workflow_result_id: str | None = None
    operation_result_ids: tuple[str, ...] = ()
    findings: tuple[MappingProxyType[str, Any], ...] = ()
    recommendations: tuple[MappingProxyType[str, Any], ...] = ()
    approval_ids: tuple[str, ...] = ()
    confidence: float = 0.0
    trace_id: str | None = None
    session_id: str | None = None
    created_at: datetime | None = None
    metadata: MappingProxyType[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )

    def __post_init__(self) -> None:
        if isinstance(self.id, str):
            try:
                object.__setattr__(self, "id", DomainResultId(opaque_id=self.id))
            except DomainContractValidationError:
                if self.id.startswith("domain-result:"):
                    opq = self.id[len("domain-result:") :]
                    object.__setattr__(self, "id", DomainResultId(opaque_id=opq))
                else:
                    object.__setattr__(self, "id", DomainResultId(opaque_id=self.id))
        elif not isinstance(self.id, DomainResultId):
            raise DomainContractValidationError(
                "id must be a DomainResultId instance or canonical string", field="id"
            )

        object.__setattr__(
            self, "status", _validate_non_empty_str(self.status, "status")
        )
        object.__setattr__(
            self, "objective", _validate_non_empty_str(self.objective, "objective")
        )

        if isinstance(self.primary_domain, str):
            object.__setattr__(
                self, "primary_domain", DomainId.from_str(self.primary_domain)
            )
        elif not isinstance(self.primary_domain, DomainId):
            raise DomainContractValidationError(
                "primary_domain must be a DomainId instance or canonical string",
                field="primary_domain",
            )

        # Supporting domains
        sup: list[DomainId] = []
        seen = {self.primary_domain.slug}
        for item in self.supporting_domains:
            if isinstance(item, str):
                item = DomainId.from_str(item)
            elif not isinstance(item, DomainId):
                raise DomainContractValidationError(
                    "supporting_domains items must be DomainId instances or strings",
                    field="supporting_domains",
                )
            if item.slug in seen:
                raise DomainContractValidationError(
                    f"Duplicate or primary domain in supporting_domains: {item.slug}",
                    field="supporting_domains",
                )
            seen.add(item.slug)
            sup.append(item)
        object.__setattr__(self, "supporting_domains", tuple(sup))

        # Confidence (strict, via helper)
        object.__setattr__(
            self,
            "confidence",
            _validate_strict_confidence(self.confidence, "confidence"),
        )

        # Optional string IDs
        object.__setattr__(
            self,
            "reasoning_result_id",
            _normalize_empty_to_none(self.reasoning_result_id),
        )
        object.__setattr__(
            self,
            "workflow_result_id",
            _normalize_empty_to_none(self.workflow_result_id),
        )
        object.__setattr__(self, "trace_id", _normalize_empty_to_none(self.trace_id))
        object.__setattr__(
            self, "session_id", _normalize_empty_to_none(self.session_id)
        )

        # Collections of string IDs
        object.__setattr__(
            self,
            "operation_result_ids",
            _freeze_str_tuple(
                self.operation_result_ids, "operation_result_ids", require_unique=True
            ),
        )
        object.__setattr__(
            self,
            "approval_ids",
            _freeze_str_tuple(self.approval_ids, "approval_ids", require_unique=True),
        )

        # Findings and recommendations (deep-frozen)
        object.__setattr__(
            self, "findings", tuple(_deep_freeze(f) for f in self.findings)
        )
        object.__setattr__(
            self,
            "recommendations",
            tuple(_deep_freeze(r) for r in self.recommendations),
        )

        # Timestamp
        if self.created_at is not None:
            object.__setattr__(
                self, "created_at", _ensure_tz_aware(self.created_at, "created_at")
            )

        object.__setattr__(self, "metadata", _deep_freeze(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "id": str(self.id),
            "status": self.status,
            "objective": self.objective,
            "primary_domain": str(self.primary_domain),
            "supporting_domains": [str(d) for d in self.supporting_domains],
            "reasoning_result_id": self.reasoning_result_id,
            "workflow_result_id": self.workflow_result_id,
            "operation_result_ids": list(self.operation_result_ids),
            "findings": [_deep_unfreeze(f) for f in self.findings],
            "recommendations": [_deep_unfreeze(r) for r in self.recommendations],
            "approval_ids": list(self.approval_ids),
            "confidence": self.confidence,
            "trace_id": self.trace_id,
            "session_id": self.session_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "metadata": _deep_unfreeze(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DomainResult:
        """Deserialize from dictionary."""
        if not isinstance(data, Mapping):
            raise DomainSerializationError(
                "DomainResult.from_dict requires a mapping", field="data"
            )
        _reject_unknown_fields(data, _RESULT_KNOWN, "DomainResult")
        required = {"id", "status", "objective", "primary_domain"}
        missing = required - set(data.keys())
        if missing:
            raise DomainSerializationError(
                f"DomainResult.from_dict missing required fields: {sorted(missing)}",
                field="data",
            )

        def _parse_domain_ids(raw: Any, field_label: str) -> tuple[DomainId, ...]:
            if raw is None:
                return ()
            if not isinstance(raw, (list, tuple)):
                raise DomainSerializationError(
                    f"{field_label} must be a list", field=field_label
                )
            result = []
            for i, item in enumerate(raw):
                if not isinstance(item, str):
                    raise DomainSerializationError(
                        f"Each item in {field_label} must be a string, got {type(item).__name__} at index {i}",
                        field=f"{field_label}[{i}]",
                    )
                try:
                    result.append(DomainId.from_str(str(item)))
                except DomainError as exc:
                    _wrap_nested_error(exc, field_label, i)
            return tuple(result)

        def _parse_mapping_list(
            raw: Any, field_label: str
        ) -> tuple[MappingProxyType[str, Any], ...]:
            if raw is None:
                return ()
            if not isinstance(raw, (list, tuple)):
                raise DomainSerializationError(
                    f"{field_label} must be a list", field=field_label
                )
            result = []
            for i, item in enumerate(raw):
                if not isinstance(item, Mapping):
                    raise DomainSerializationError(
                        f"Each item in {field_label} must be a mapping, got {type(item).__name__} at index {i}",
                        field=f"{field_label}[{i}]",
                    )
                result.append(_deep_freeze(item))
            return tuple(result)

        return cls(
            id=str(data["id"]),
            status=str(data["status"]),
            objective=str(data["objective"]),
            primary_domain=str(data["primary_domain"]),
            supporting_domains=_parse_domain_ids(
                data.get("supporting_domains"), "supporting_domains"
            ),
            reasoning_result_id=data.get("reasoning_result_id"),
            workflow_result_id=data.get("workflow_result_id"),
            operation_result_ids=tuple(data.get("operation_result_ids", ())),
            findings=_parse_mapping_list(data.get("findings"), "findings"),
            recommendations=_parse_mapping_list(
                data.get("recommendations"), "recommendations"
            ),
            approval_ids=tuple(data.get("approval_ids", ())),
            confidence=_validate_strict_confidence_from_dict(
                data.get("confidence", 0.0), "confidence"
            ),
            trace_id=data.get("trace_id"),
            session_id=data.get("session_id"),
            created_at=_parse_datetime_opt(data.get("created_at"), "created_at"),
            metadata=_deep_freeze(data.get("metadata")),
        )


# ── Internal coercion helpers ─────────────────────────────────────────────────


def _coerce_dependency_tuple(seq: Any, field_name: str) -> tuple[DomainDependency, ...]:
    """Coerce a sequence into a tuple of DomainDependency instances."""
    if seq is None:
        return ()
    if isinstance(seq, (str, bytes)):
        raise DomainContractValidationError(
            f"{field_name} must be a sequence of DomainDependency, not a string",
            field=field_name,
        )
    if not isinstance(seq, (tuple, list, set, Sequence)):
        raise DomainContractValidationError(
            f"{field_name} must be a sequence",
            field=field_name,
        )
    result = []
    for i, item in enumerate(seq):
        if isinstance(item, DomainDependency):
            result.append(item)
        elif isinstance(item, Mapping):
            try:
                result.append(DomainDependency.from_dict(dict(item)))
            except DomainError as exc:
                _wrap_nested_error(exc, field_name, i)
        else:
            raise DomainContractValidationError(
                f"Each item in {field_name} must be a DomainDependency or mapping, got {type(item).__name__}",
                field=field_name,
                details={"index": i},
            )
    return tuple(result)


def _coerce_conflict_tuple(seq: Any, field_name: str) -> tuple[DomainConflict, ...]:
    """Coerce a sequence into a tuple of DomainConflict instances."""
    if seq is None:
        return ()
    if isinstance(seq, (str, bytes)):
        raise DomainContractValidationError(
            f"{field_name} must be a sequence of DomainConflict, not a string",
            field=field_name,
        )
    if not isinstance(seq, (tuple, list, set, Sequence)):
        raise DomainContractValidationError(
            f"{field_name} must be a sequence",
            field=field_name,
        )
    result = []
    for i, item in enumerate(seq):
        if isinstance(item, DomainConflict):
            result.append(item)
        elif isinstance(item, Mapping):
            try:
                result.append(DomainConflict.from_dict(dict(item)))
            except DomainError as exc:
                _wrap_nested_error(exc, field_name, i)
        else:
            raise DomainContractValidationError(
                f"Each item in {field_name} must be a DomainConflict or mapping, got {type(item).__name__}",
                field=field_name,
                details={"index": i},
            )
    return tuple(result)


def _coerce_capability_tuple(seq: Any, field_name: str) -> tuple[DomainCapability, ...]:
    """Coerce a sequence into a tuple of DomainCapability instances."""
    if seq is None:
        return ()
    if isinstance(seq, (str, bytes)):
        raise DomainContractValidationError(
            f"{field_name} must be a sequence of DomainCapability, not a string",
            field=field_name,
        )
    if not isinstance(seq, (tuple, list, set, Sequence)):
        raise DomainContractValidationError(
            f"{field_name} must be a sequence",
            field=field_name,
        )
    result = []
    for i, item in enumerate(seq):
        if isinstance(item, DomainCapability):
            result.append(item)
        elif isinstance(item, Mapping):
            try:
                result.append(DomainCapability.from_dict(dict(item)))
            except DomainError as exc:
                _wrap_nested_error(exc, field_name, i)
        else:
            raise DomainContractValidationError(
                f"Each item in {field_name} must be a DomainCapability or mapping, got {type(item).__name__}",
                field=field_name,
                details={"index": i},
            )
    return tuple(result)


__all__ = [
    "DomainCapability",
    "DomainConflict",
    "DomainDefinition",
    "DomainDependency",
    "DomainMetadata",
    "DomainResult",
]
