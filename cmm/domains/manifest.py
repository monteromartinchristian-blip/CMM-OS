"""Phase 10.2 – Domain Manifest.

Declarative, immutable, and validatable representation of a Domain Pack.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any

from cmm.domains.contracts import (
    DomainConflict,
    DomainDependency,
    _deep_freeze,
    _deep_unfreeze,
    _normalize_empty_to_none,
    _reject_unknown_fields,
    _validate_non_empty_str,
    _validate_strict_bool,
    _wrap_nested_error,
)
from cmm.domains.enums import DomainPackKind
from cmm.domains.errors import (
    DomainContractValidationError,
    DomainSerializationError,
)
from cmm.domains.identifiers import (
    DomainId,
    DomainManifestId,
)

# ── Path validation helpers ────────────────────────────────────────────────────

_INVALID_PATH_CHARS_RE = re.compile(r"[^\x20-\x7E]")
_CREDENTIAL_KEYS = frozenset(
    {
        "password",
        "secret",
        "token",
        "api_key",
        "private_key",
        "credential",
    }
)


def _validate_safe_relative_path(value: str, field_name: str) -> str:
    """Validate a safe relative path: no absolute, no traversal, POSIX-normalized."""
    if not isinstance(value, str):
        raise DomainContractValidationError(
            f"{field_name} must be a string, got {type(value).__name__}",
            field=field_name,
        )
    stripped = value.strip()
    if not stripped:
        raise DomainContractValidationError(
            f"{field_name} must be a non-empty path", field=field_name
        )

    if stripped.startswith("/"):
        raise DomainContractValidationError(
            f"{field_name} must be a relative path, got absolute: {stripped!r}",
            field=field_name,
        )
    if re.match(r"^[A-Za-z]:[\\/]", stripped):
        raise DomainContractValidationError(
            f"{field_name} must be a relative path (no drive letter): {stripped!r}",
            field=field_name,
        )

    normalized = stripped.replace("\\", "/")

    if ".." in normalized.split("/"):
        raise DomainContractValidationError(
            f"{field_name} must not contain path traversal '..': {normalized!r}",
            field=field_name,
        )

    segments = normalized.split("/")
    for i, seg in enumerate(segments):
        if not seg:
            raise DomainContractValidationError(
                f"{field_name} must not contain empty path segments: {normalized!r}",
                field=field_name,
                details={"empty_segment_index": i},
            )

    if _INVALID_PATH_CHARS_RE.search(normalized):
        raise DomainContractValidationError(
            f"{field_name} contains invalid characters: {normalized!r}",
            field=field_name,
        )

    return normalized


def _normalize_optional_safe_path(value: str | None, field_name: str) -> str | None:
    """Normalize an optional safe relative path: empty string → None, else validate."""
    if value is None:
        return None
    if not isinstance(value, str):
        raise DomainContractValidationError(
            f"{field_name} must be a string or None, got {type(value).__name__}",
            field=field_name,
        )
    if not value.strip():
        return None
    return _validate_safe_relative_path(value, field_name)


def _scan_credential_keys(
    mapping: Mapping[str, Any], base_path: str
) -> list[DomainContractValidationError]:
    """Scan a mapping (and nested mappings) for credential-like keys."""
    errors: list[DomainContractValidationError] = []
    for key, val in mapping.items():
        if not isinstance(key, str):
            continue
        key_lower = key.lower()
        full_path = f"{base_path}.{key}" if base_path else key
        if key_lower in _CREDENTIAL_KEYS or any(
            ck in key_lower for ck in _CREDENTIAL_KEYS
        ):
            errors.append(
                DomainContractValidationError(
                    f"Credential-like key detected in metadata: '{full_path}'",
                    field=full_path,
                    details={"credential_key": key},
                )
            )
        if isinstance(val, Mapping):
            errors.extend(_scan_credential_keys(dict(val), full_path))
    return errors


def _validate_metadata_no_credentials(
    metadata: Mapping[str, Any], root_path: str
) -> None:
    """Raise if any credential-like keys are found in metadata (recursively)."""
    if metadata is None:
        return
    errors = _scan_credential_keys(dict(metadata), root_path)
    if errors:
        raise errors[0]


def _freeze_component_tuple(
    seq: Any, field_name: str
) -> tuple[DomainComponentReference, ...]:
    """Coerce a sequence into a tuple of DomainComponentReference instances."""
    if seq is None:
        return ()
    if isinstance(seq, (str, bytes)):
        raise DomainContractValidationError(
            f"{field_name} must be a sequence of components, not a string",
            field=field_name,
        )
    if not isinstance(seq, (tuple, list)):
        raise DomainContractValidationError(
            f"{field_name} must be a list or tuple, got {type(seq).__name__}",
            field=field_name,
        )
    result: list[DomainComponentReference] = []
    for i, item in enumerate(seq):
        if isinstance(item, DomainComponentReference):
            result.append(item)
        elif isinstance(item, Mapping):
            try:
                result.append(DomainComponentReference.from_dict(dict(item)))
            except DomainContractValidationError as exc:
                _wrap_nested_error(exc, field_name, i)
            except DomainSerializationError as exc:
                _wrap_nested_error(exc, field_name, i)
        else:
            raise DomainContractValidationError(
                f"Each item in {field_name} must be a DomainComponentReference or "
                f"mapping, got {type(item).__name__}",
                field=field_name,
                details={"index": i},
            )
    return tuple(result)


# ── DomainComponentReference ───────────────────────────────────────────────────

_COMPONENT_KNOWN = frozenset(
    {
        "id",
        "path",
        "entrypoint",
        "version",
        "checksum",
        "enabled",
        "metadata",
    }
)


@dataclass(frozen=True, slots=True)
class DomainComponentReference:
    """Immutable declaration of a component contained in a domain pack."""

    id: str
    path: str
    entrypoint: str | None = None
    version: str | None = None
    checksum: str | None = None
    enabled: bool = True
    metadata: MappingProxyType[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", _validate_non_empty_str(self.id, "id"))
        object.__setattr__(
            self, "path", _validate_safe_relative_path(self.path, "path")
        )
        object.__setattr__(
            self,
            "entrypoint",
            _normalize_optional_safe_path(self.entrypoint, "entrypoint"),
        )
        object.__setattr__(self, "version", _normalize_empty_to_none(self.version))
        object.__setattr__(self, "checksum", _normalize_empty_to_none(self.checksum))
        object.__setattr__(
            self, "enabled", _validate_strict_bool(self.enabled, "enabled")
        )
        object.__setattr__(self, "metadata", _deep_freeze(self.metadata))
        _validate_metadata_no_credentials(
            self.metadata, f"component[{self.id}].metadata"
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "path": self.path,
            "entrypoint": self.entrypoint,
            "version": self.version,
            "checksum": self.checksum,
            "enabled": self.enabled,
            "metadata": _deep_unfreeze(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DomainComponentReference:
        if not isinstance(data, Mapping):
            raise DomainSerializationError(
                "DomainComponentReference.from_dict requires a mapping",
                field="data",
            )
        _reject_unknown_fields(data, _COMPONENT_KNOWN, "DomainComponentReference")
        required = {"id", "path"}
        missing = required - set(data.keys())
        if missing:
            raise DomainSerializationError(
                f"DomainComponentReference.from_dict missing required "
                f"fields: {sorted(missing)}",
                field="data",
            )

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
            id=data["id"],
            path=data["path"],
            entrypoint=data.get("entrypoint"),
            version=data.get("version"),
            checksum=data.get("checksum"),
            enabled=enabled,
            metadata=_deep_freeze(data.get("metadata")),
        )


# ── DomainPermissionReference ──────────────────────────────────────────────────

_PERMISSION_KNOWN = frozenset(
    {
        "policy",
        "required_permissions",
        "optional_permissions",
        "metadata",
    }
)


@dataclass(frozen=True, slots=True)
class DomainPermissionReference:
    """Immutable permission declaration for a domain pack."""

    policy: str
    required_permissions: tuple[str, ...] = ()
    optional_permissions: tuple[str, ...] = ()
    metadata: MappingProxyType[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "policy", _validate_safe_relative_path(self.policy, "policy")
        )

        req: tuple[str, ...] = ()
        if self.required_permissions:
            req = self._validate_perm_list(
                self.required_permissions, "required_permissions"
            )
        object.__setattr__(self, "required_permissions", req)

        opt: tuple[str, ...] = ()
        if self.optional_permissions:
            opt = self._validate_perm_list(
                self.optional_permissions, "optional_permissions"
            )
        object.__setattr__(self, "optional_permissions", opt)

        overlap = set(req) & set(opt)
        if overlap:
            raise DomainContractValidationError(
                f"Permissions cannot be both required and optional: {sorted(overlap)}",
                field="permissions",
                details={"overlapping": sorted(overlap)},
            )

        object.__setattr__(self, "metadata", _deep_freeze(self.metadata))
        _validate_metadata_no_credentials(self.metadata, "permissions.metadata")

    @staticmethod
    def _validate_perm_list(seq: Any, field_name: str) -> tuple[str, ...]:
        if seq is None:
            return ()
        if isinstance(seq, (str, bytes)):
            raise DomainContractValidationError(
                f"{field_name} must be a sequence of strings, not a string",
                field=field_name,
            )
        if not isinstance(seq, (tuple, list)):
            raise DomainContractValidationError(
                f"{field_name} must be a list or tuple, got {type(seq).__name__}",
                field=field_name,
            )
        result: list[str] = []
        for i, item in enumerate(seq):
            if not isinstance(item, str) or not item.strip():
                raise DomainContractValidationError(
                    f"All items in {field_name} must be non-empty strings",
                    field=field_name,
                    details={"index": i, "value": item},
                )
            result.append(item.strip())
        if len(set(result)) != len(result):
            raise DomainContractValidationError(
                f"Duplicate permissions in {field_name}", field=field_name
            )
        return tuple(result)

    def to_dict(self) -> dict[str, Any]:
        return {
            "policy": self.policy,
            "required_permissions": list(self.required_permissions),
            "optional_permissions": list(self.optional_permissions),
            "metadata": _deep_unfreeze(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DomainPermissionReference:
        if not isinstance(data, Mapping):
            raise DomainSerializationError(
                "DomainPermissionReference.from_dict requires a mapping",
                field="data",
            )
        _reject_unknown_fields(data, _PERMISSION_KNOWN, "DomainPermissionReference")
        if "policy" not in data:
            raise DomainSerializationError(
                "DomainPermissionReference.from_dict missing required field 'policy'",
                field="policy",
            )
        return cls(
            policy=data["policy"],
            required_permissions=tuple(data.get("required_permissions", ())),
            optional_permissions=tuple(data.get("optional_permissions", ())),
            metadata=_deep_freeze(data.get("metadata")),
        )


# ── DomainCompatibility ────────────────────────────────────────────────────────

_COMPAT_KNOWN = frozenset(
    {
        "minimum_cmm_version",
        "maximum_cmm_version",
        "supported_python_versions",
        "supported_platforms",
        "required_features",
        "incompatible_features",
        "metadata",
    }
)


@dataclass(frozen=True, slots=True)
class DomainCompatibility:
    """Immutable compatibility declaration for a domain pack."""

    minimum_cmm_version: str | None = None
    maximum_cmm_version: str | None = None
    supported_python_versions: tuple[str, ...] = ()
    supported_platforms: tuple[str, ...] = ()
    required_features: tuple[str, ...] = ()
    incompatible_features: tuple[str, ...] = ()
    metadata: MappingProxyType[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )

    def __post_init__(self) -> None:
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

        for attr_name in (
            "supported_python_versions",
            "supported_platforms",
            "required_features",
            "incompatible_features",
        ):
            object.__setattr__(
                self,
                attr_name,
                self._validate_string_tuple(getattr(self, attr_name), attr_name),
            )

        overlap = set(self.required_features) & set(self.incompatible_features)
        if overlap:
            raise DomainContractValidationError(
                f"Features cannot be both required and incompatible: {sorted(overlap)}",
                field="features",
                details={"overlapping": sorted(overlap)},
            )

        object.__setattr__(self, "metadata", _deep_freeze(self.metadata))
        _validate_metadata_no_credentials(self.metadata, "compatibility.metadata")

    @staticmethod
    def _validate_string_tuple(seq: Any, field_name: str) -> tuple[str, ...]:
        if seq is None:
            return ()
        if isinstance(seq, (str, bytes)):
            raise DomainContractValidationError(
                f"{field_name} must be a sequence of strings, not a string",
                field=field_name,
            )
        if not isinstance(seq, (tuple, list)):
            raise DomainContractValidationError(
                f"{field_name} must be a list or tuple, got {type(seq).__name__}",
                field=field_name,
            )
        result: list[str] = []
        for i, item in enumerate(seq):
            if not isinstance(item, str) or not item.strip():
                raise DomainContractValidationError(
                    f"All items in {field_name} must be non-empty strings",
                    field=field_name,
                    details={"index": i, "value": item},
                )
            result.append(item.strip())
        if len(set(result)) != len(result):
            raise DomainContractValidationError(
                f"Duplicate items in {field_name}", field=field_name
            )
        return tuple(result)

    def to_dict(self) -> dict[str, Any]:
        return {
            "minimum_cmm_version": self.minimum_cmm_version,
            "maximum_cmm_version": self.maximum_cmm_version,
            "supported_python_versions": list(self.supported_python_versions),
            "supported_platforms": list(self.supported_platforms),
            "required_features": list(self.required_features),
            "incompatible_features": list(self.incompatible_features),
            "metadata": _deep_unfreeze(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DomainCompatibility:
        if not isinstance(data, Mapping):
            raise DomainSerializationError(
                "DomainCompatibility.from_dict requires a mapping", field="data"
            )
        _reject_unknown_fields(data, _COMPAT_KNOWN, "DomainCompatibility")
        return cls(
            minimum_cmm_version=data.get("minimum_cmm_version"),
            maximum_cmm_version=data.get("maximum_cmm_version"),
            supported_python_versions=tuple(data.get("supported_python_versions", ())),
            supported_platforms=tuple(data.get("supported_platforms", ())),
            required_features=tuple(data.get("required_features", ())),
            incompatible_features=tuple(data.get("incompatible_features", ())),
            metadata=_deep_freeze(data.get("metadata")),
        )


# ── DomainManifest ─────────────────────────────────────────────────────────────

_MANIFEST_KNOWN = frozenset(
    {
        "id",
        "domain_id",
        "schema_version",
        "package_version",
        "pack_kind",
        "entrypoint",
        "resources",
        "profiles",
        "rules",
        "operations",
        "workflows",
        "permissions",
        "prompts",
        "presentation",
        "validators",
        "migrations",
        "fixtures",
        "tests",
        "dependencies",
        "conflicts",
        "compatibility",
        "checksum",
        "signature",
        "metadata",
    }
)

_CATEGORY_PATH_PREFIX: dict[str, str] = {
    "resources": "resources/",
    "profiles": "profiles/",
    "rules": "rules/",
    "operations": "operations/",
    "workflows": "workflows/",
    "prompts": "prompts/",
    "presentation": "presentation/",
    "validators": "validators/",
    "migrations": "migrations/",
    "fixtures": "fixtures/",
    "tests": "tests/",
}

_COMPONENT_CATEGORIES = tuple(_CATEGORY_PATH_PREFIX.keys())

# ── Declarative allowed top-level fields ──────────────────────────────────────

_DECLARATIVE_KNOWN = frozenset(
    {
        "id",
        "name",
        "display_name",
        "title",
        "version",
        "kind",
        "description",
        "schema_version",
        "pack_kind",
        "experimental",
        "minimum_cmm_version",
        "maximum_cmm_version",
        "supported_python_versions",
        "entrypoint",
        "resources",
        "profile",
        "profiles",
        "rules",
        "operations",
        "workflows",
        "permissions",
        "prompts",
        "presentation",
        "validators",
        "migrations",
        "fixtures",
        "tests",
        "dependencies",
        "optional_dependencies",
        "conflicts",
        "compatibility",
        "checksum",
        "signature",
        "metadata",
        "reasoning_profile",
        "presentation_policy",
        "capabilities",
        "homepage",
        "repository",
        "tags",
        "author",
        "license",
    }
)

# Declarative component mapping known fields
_DECLARATIVE_COMPONENT_KNOWN = frozenset(
    {"id", "name", "path", "entrypoint", "version", "checksum", "enabled", "metadata"}
)


def _validate_declarative_str(val: Any, field_name: str) -> str:
    """Validate a declarative field is a real string (no coercions)."""
    if not isinstance(val, str):
        raise DomainSerializationError(
            f"Declarative field '{field_name}' must be a string, "
            f"got {type(val).__name__}: {val!r}",
            field=field_name,
        )
    return val


def _validate_declarative_bool(val: Any, field_name: str) -> bool:
    """Validate a declarative field is a strict boolean."""
    if not isinstance(val, bool):
        raise DomainSerializationError(
            f"Declarative field '{field_name}' must be a boolean (True/False), "
            f"got {type(val).__name__}: {val!r}",
            field=field_name,
        )
    return val


def _validate_declarative_opt_str(val: Any, field_name: str) -> str | None:
    """Validate a declarative field is a string or None."""
    if val is None:
        return None
    if not isinstance(val, str):
        raise DomainSerializationError(
            f"Declarative field '{field_name}' must be a string or None, "
            f"got {type(val).__name__}: {val!r}",
            field=field_name,
        )
    return val


def _validate_declarative_root_path(value: Any, field_name: str) -> str:
    """Validate and normalize a root path (may be absolute or relative)."""
    if not isinstance(value, str):
        raise DomainSerializationError(
            f"Declarative field '{field_name}' must be a string, "
            f"got {type(value).__name__}: {value!r}",
            field=field_name,
        )
    stripped = value.strip()
    if not stripped:
        raise DomainSerializationError(
            f"Declarative field '{field_name}' must be a non-empty string",
            field=field_name,
        )
    return _normalize_root_path_lexical(stripped)


def _normalize_root_path_lexical(path: str) -> str:
    """Lexically normalize a root path without filesystem access.

    - Backslashes → forward slashes
    - Remove repeated slashes
    - Remove single-dot segments
    - Resolve '..' segments lexically (never above root)
    """
    # Normalize separators
    normalized = path.replace("\\", "/")

    # Preserve leading slash for absolute paths
    is_absolute = normalized.startswith("/")

    segments = normalized.split("/")
    resolved: list[str] = []
    for seg in segments:
        if not seg or seg == ".":
            continue
        if seg == "..":
            if resolved and resolved[-1] != "..":
                resolved.pop()
            elif not is_absolute:
                resolved.append("..")
            # For absolute paths, '..' above root is silently ignored
        else:
            resolved.append(seg)

    result = "/".join(resolved)
    if is_absolute:
        result = "/" + result
    if not result:
        result = "." if not is_absolute else "/"
    return result


@dataclass(frozen=True, slots=True)
class DomainManifest:
    """Immutable manifest declaring the contents of a Domain Pack."""

    id: DomainManifestId
    domain_id: DomainId
    schema_version: str
    package_version: str
    pack_kind: DomainPackKind
    entrypoint: str | None = None
    resources: tuple[DomainComponentReference, ...] = ()
    profiles: tuple[DomainComponentReference, ...] = ()
    rules: tuple[DomainComponentReference, ...] = ()
    operations: tuple[DomainComponentReference, ...] = ()
    workflows: tuple[DomainComponentReference, ...] = ()
    permissions: DomainPermissionReference | None = None
    prompts: tuple[DomainComponentReference, ...] = ()
    presentation: tuple[DomainComponentReference, ...] = ()
    validators: tuple[DomainComponentReference, ...] = ()
    migrations: tuple[DomainComponentReference, ...] = ()
    fixtures: tuple[DomainComponentReference, ...] = ()
    tests: tuple[DomainComponentReference, ...] = ()
    dependencies: tuple[DomainDependency, ...] = ()
    conflicts: tuple[DomainConflict, ...] = ()
    compatibility: DomainCompatibility | None = None
    checksum: str | None = None
    signature: str | None = None
    metadata: MappingProxyType[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )

    def __post_init__(self) -> None:
        # ── Coerce ids ──────────────────────────────────────────────────
        if isinstance(self.id, str):
            object.__setattr__(
                self,
                "id",
                DomainManifestId.from_dict(self._parse_manifest_id_string(self.id)),
            )
        elif not isinstance(self.id, DomainManifestId):
            raise DomainContractValidationError(
                "id must be a DomainManifestId", field="id"
            )

        if isinstance(self.domain_id, str):
            object.__setattr__(self, "domain_id", DomainId.from_str(self.domain_id))
        elif not isinstance(self.domain_id, DomainId):
            raise DomainContractValidationError(
                "domain_id must be a DomainId", field="domain_id"
            )

        # ── Schema & package version ─────────────────────────────────────
        object.__setattr__(
            self,
            "schema_version",
            _validate_non_empty_str(self.schema_version, "schema_version"),
        )
        object.__setattr__(
            self,
            "package_version",
            _validate_non_empty_str(self.package_version, "package_version"),
        )

        # ── Pack kind ────────────────────────────────────────────────────
        if isinstance(self.pack_kind, str):
            try:
                object.__setattr__(self, "pack_kind", DomainPackKind(self.pack_kind))
            except ValueError as exc:
                raise DomainContractValidationError(
                    f"Invalid DomainPackKind: {self.pack_kind!r}",
                    field="pack_kind",
                ) from exc
        elif not isinstance(self.pack_kind, DomainPackKind):
            raise DomainContractValidationError(
                f"pack_kind must be a DomainPackKind, got "
                f"{type(self.pack_kind).__name__}",
                field="pack_kind",
            )

        # ── Coherence ────────────────────────────────────────────────────
        if self.id.slug != self.domain_id.slug:
            raise DomainContractValidationError(
                f"Manifest id slug '{self.id.slug}' must match domain_id "
                f"slug '{self.domain_id.slug}'",
                field="id",
            )
        if self.id.version != self.package_version:
            raise DomainContractValidationError(
                f"Manifest id version '{self.id.version}' must match "
                f"package_version '{self.package_version}'",
                field="id",
            )

        # ── Entrypoint ───────────────────────────────────────────────────
        object.__setattr__(
            self,
            "entrypoint",
            _normalize_optional_safe_path(self.entrypoint, "entrypoint"),
        )

        # ── Component collections ────────────────────────────────────────
        for category in _COMPONENT_CATEGORIES:
            raw = getattr(self, category)
            frozen = _freeze_component_tuple(raw, category)
            object.__setattr__(self, category, frozen)

        # ── Permissions ─────────────────────────────────────────────────
        if self.permissions is not None and isinstance(self.permissions, Mapping):
            try:
                object.__setattr__(
                    self,
                    "permissions",
                    DomainPermissionReference.from_dict(dict(self.permissions)),
                )
            except (DomainContractValidationError, DomainSerializationError) as exc:
                _wrap_nested_error(exc, "permissions")
        elif self.permissions is not None and not isinstance(
            self.permissions, DomainPermissionReference
        ):
            raise DomainContractValidationError(
                "permissions must be a DomainPermissionReference or mapping",
                field="permissions",
            )

        # ── Global uniqueness: component IDs ────────────────────────────
        all_components: dict[str, DomainComponentReference] = {}
        for category in _COMPONENT_CATEGORIES:
            for comp in getattr(self, category):
                if comp.id in all_components:
                    raise DomainContractValidationError(
                        f"Duplicate component id '{comp.id}' in manifest "
                        f"(first seen in {self._find_component_category(all_components[comp.id])})",
                        field=category,
                        details={"duplicate_id": comp.id},
                    )
                all_components[comp.id] = comp

        # ── Global uniqueness: component paths ──────────────────────────
        all_paths: dict[str, DomainComponentReference] = {}
        for category in _COMPONENT_CATEGORIES:
            for comp in getattr(self, category):
                if comp.path in all_paths:
                    raise DomainContractValidationError(
                        f"Duplicate component path '{comp.path}' in manifest "
                        f"(first seen in {self._find_component_category(all_paths[comp.path])})",
                        field=category,
                        details={"duplicate_path": comp.path},
                    )
                all_paths[comp.path] = comp

        # ── Dependencies ─────────────────────────────────────────────────
        deps = self._coerce_dependency_tuple(self.dependencies, "dependencies")
        object.__setattr__(self, "dependencies", deps)

        dep_slugs = set()
        for dep in deps:
            if dep.domain_id.slug in dep_slugs:
                raise DomainContractValidationError(
                    f"Duplicate dependency on {dep.domain_id.slug}",
                    field="dependencies",
                )
            dep_slugs.add(dep.domain_id.slug)
            if dep.domain_id.slug == self.domain_id.slug:
                raise DomainContractValidationError(
                    f"Manifest cannot depend on itself: {self.domain_id.slug}",
                    field="dependencies",
                )
            if not dep.required:
                raise DomainContractValidationError(
                    f"Manifest dependency on {dep.domain_id.slug} must have "
                    f"required=True",
                    field="dependencies",
                )

        # ── Conflicts ────────────────────────────────────────────────────
        confs = self._coerce_conflict_tuple(self.conflicts, "conflicts")
        object.__setattr__(self, "conflicts", confs)

        conf_slugs = set()
        for c in confs:
            if c.domain_id.slug in conf_slugs:
                raise DomainContractValidationError(
                    f"Duplicate conflict with {c.domain_id.slug}",
                    field="conflicts",
                )
            conf_slugs.add(c.domain_id.slug)
            if c.domain_id.slug == self.domain_id.slug:
                raise DomainContractValidationError(
                    f"Manifest cannot conflict with itself: {self.domain_id.slug}",
                    field="conflicts",
                )
            if c.domain_id.slug in dep_slugs:
                raise DomainContractValidationError(
                    f"Domain {c.domain_id.slug} appears as both dependency "
                    f"and conflict",
                    field="conflicts",
                )

        # ── Compatibility ────────────────────────────────────────────────
        if self.compatibility is not None and isinstance(self.compatibility, Mapping):
            try:
                object.__setattr__(
                    self,
                    "compatibility",
                    DomainCompatibility.from_dict(dict(self.compatibility)),
                )
            except (DomainContractValidationError, DomainSerializationError) as exc:
                _wrap_nested_error(exc, "compatibility")
        elif self.compatibility is not None and not isinstance(
            self.compatibility, DomainCompatibility
        ):
            raise DomainContractValidationError(
                "compatibility must be a DomainCompatibility or mapping",
                field="compatibility",
            )

        # ── Checksum & signature ─────────────────────────────────────────
        object.__setattr__(
            self, "checksum", _normalize_checksum_sig(self.checksum, "checksum")
        )
        object.__setattr__(
            self, "signature", _normalize_checksum_sig(self.signature, "signature")
        )

        # ── Metadata ─────────────────────────────────────────────────────
        object.__setattr__(self, "metadata", _deep_freeze(self.metadata))
        _validate_metadata_no_credentials(self.metadata, "manifest.metadata")

    def _find_component_category(self, comp: DomainComponentReference) -> str:
        for category in _COMPONENT_CATEGORIES:
            if comp in getattr(self, category):
                return category
        return "unknown"

    @staticmethod
    def _parse_manifest_id_string(value: str) -> dict[str, str]:
        if not value.startswith("manifest:"):
            raise DomainContractValidationError(
                f"Manifest id must start with 'manifest:': {value!r}",
                field="id",
            )
        rest = value[len("manifest:") :]
        parts = rest.split(":", 1)
        if len(parts) < 2:
            raise DomainContractValidationError(
                f"Manifest id must be manifest:<slug>:<version>: {value!r}",
                field="id",
            )
        return {"slug": parts[0], "version": parts[1]}

    @staticmethod
    def _coerce_dependency_tuple(
        seq: Any, field_name: str
    ) -> tuple[DomainDependency, ...]:
        if seq is None:
            return ()
        if isinstance(seq, (str, bytes)):
            raise DomainContractValidationError(
                f"{field_name} must be a sequence, not a string",
                field=field_name,
            )
        if not isinstance(seq, (tuple, list)):
            raise DomainContractValidationError(
                f"{field_name} must be a list or tuple, got {type(seq).__name__}",
                field=field_name,
            )
        result: list[DomainDependency] = []
        for i, item in enumerate(seq):
            if isinstance(item, DomainDependency):
                result.append(item)
            elif isinstance(item, Mapping):
                try:
                    result.append(DomainDependency.from_dict(dict(item)))
                except (DomainContractValidationError, DomainSerializationError) as exc:
                    _wrap_nested_error(exc, field_name, i)
            else:
                raise DomainContractValidationError(
                    f"Each item in {field_name} must be a DomainDependency "
                    f"or mapping, got {type(item).__name__}",
                    field=field_name,
                    details={"index": i},
                )
        return tuple(result)

    @staticmethod
    def _coerce_conflict_tuple(seq: Any, field_name: str) -> tuple[DomainConflict, ...]:
        if seq is None:
            return ()
        if isinstance(seq, (str, bytes)):
            raise DomainContractValidationError(
                f"{field_name} must be a sequence, not a string",
                field=field_name,
            )
        if not isinstance(seq, (tuple, list)):
            raise DomainContractValidationError(
                f"{field_name} must be a list or tuple, got {type(seq).__name__}",
                field=field_name,
            )
        result: list[DomainConflict] = []
        for i, item in enumerate(seq):
            if isinstance(item, DomainConflict):
                result.append(item)
            elif isinstance(item, Mapping):
                try:
                    result.append(DomainConflict.from_dict(dict(item)))
                except (DomainContractValidationError, DomainSerializationError) as exc:
                    _wrap_nested_error(exc, field_name, i)
            else:
                raise DomainContractValidationError(
                    f"Each item in {field_name} must be a DomainConflict "
                    f"or mapping, got {type(item).__name__}",
                    field=field_name,
                    details={"index": i},
                )
        return tuple(result)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": str(self.id),
            "domain_id": str(self.domain_id),
            "schema_version": self.schema_version,
            "package_version": self.package_version,
            "pack_kind": self.pack_kind.value,
            "entrypoint": self.entrypoint,
            "resources": [c.to_dict() for c in self.resources],
            "profiles": [c.to_dict() for c in self.profiles],
            "rules": [c.to_dict() for c in self.rules],
            "operations": [c.to_dict() for c in self.operations],
            "workflows": [c.to_dict() for c in self.workflows],
            "permissions": self.permissions.to_dict() if self.permissions else None,
            "prompts": [c.to_dict() for c in self.prompts],
            "presentation": [c.to_dict() for c in self.presentation],
            "validators": [c.to_dict() for c in self.validators],
            "migrations": [c.to_dict() for c in self.migrations],
            "fixtures": [c.to_dict() for c in self.fixtures],
            "tests": [c.to_dict() for c in self.tests],
            "dependencies": [d.to_dict() for d in self.dependencies],
            "conflicts": [c.to_dict() for c in self.conflicts],
            "compatibility": self.compatibility.to_dict()
            if self.compatibility
            else None,
            "checksum": self.checksum,
            "signature": self.signature,
            "metadata": _deep_unfreeze(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DomainManifest:
        """Deserialize from the full contractual format."""
        if not isinstance(data, Mapping):
            raise DomainSerializationError(
                "DomainManifest.from_dict requires a mapping", field="data"
            )
        _reject_unknown_fields(data, _MANIFEST_KNOWN, "DomainManifest")
        required = {
            "id",
            "domain_id",
            "schema_version",
            "package_version",
            "pack_kind",
        }
        missing = required - set(data.keys())
        if missing:
            raise DomainSerializationError(
                f"DomainManifest.from_dict missing required fields: {sorted(missing)}",
                field="data",
            )
        return cls(
            id=data["id"],
            domain_id=data["domain_id"],
            schema_version=data["schema_version"],
            package_version=data["package_version"],
            pack_kind=data["pack_kind"],
            entrypoint=data.get("entrypoint"),
            resources=tuple(data.get("resources", ())),
            profiles=tuple(data.get("profiles", ())),
            rules=tuple(data.get("rules", ())),
            operations=tuple(data.get("operations", ())),
            workflows=tuple(data.get("workflows", ())),
            permissions=data.get("permissions"),
            prompts=tuple(data.get("prompts", ())),
            presentation=tuple(data.get("presentation", ())),
            validators=tuple(data.get("validators", ())),
            migrations=tuple(data.get("migrations", ())),
            fixtures=tuple(data.get("fixtures", ())),
            tests=tuple(data.get("tests", ())),
            dependencies=tuple(data.get("dependencies", ())),
            conflicts=tuple(data.get("conflicts", ())),
            compatibility=data.get("compatibility"),
            checksum=data.get("checksum"),
            signature=data.get("signature"),
            metadata=_deep_freeze(data.get("metadata")),
        )

    @classmethod
    def from_declarative_dict(cls, data: dict[str, Any]) -> DomainManifest:
        """Build a DomainManifest from a simplified declarative format.

        Rejects unknown fields and validates strict types.
        """
        if not isinstance(data, Mapping):
            raise DomainSerializationError(
                "DomainManifest.from_declarative_dict requires a mapping",
                field="data",
            )
        _reject_unknown_fields(data, _DECLARATIVE_KNOWN, "DomainManifest.declarative")

        # ── Required fields ──────────────────────────────────────────────
        manifest_id_raw = data.get("id")
        if manifest_id_raw is None:
            raise DomainSerializationError(
                "Missing required field 'id' in declarative dict",
                field="id",
            )
        _validate_declarative_str(manifest_id_raw, "id")
        manifest_id_raw = manifest_id_raw  # noqa: PLW0127 # type: ignore[assignment]

        domain_id_raw = manifest_id_raw
        if not domain_id_raw.startswith("domain:"):
            domain_id_raw = f"domain:{domain_id_raw}"

        version = data.get("version")
        if version is None:
            raise DomainSerializationError(
                "Missing required field 'version' in declarative dict",
                field="version",
            )
        _validate_declarative_str(version, "version")
        version = version  # noqa: PLW0127 # type: ignore[assignment]

        schema_version = data.get("schema_version", "1")
        if schema_version is not None:
            _validate_declarative_str(schema_version, "schema_version")
        schema_version = schema_version if schema_version is not None else "1"  # type: ignore[assignment]

        # ── Experimental ─────────────────────────────────────────────────
        experimental_raw = data.get("experimental")
        experimental = False
        if experimental_raw is not None:
            experimental = _validate_declarative_bool(experimental_raw, "experimental")

        # ── Pack kind ────────────────────────────────────────────────────
        pack_kind_raw = data.get("pack_kind")
        if pack_kind_raw is not None and not isinstance(
            pack_kind_raw, (str, DomainPackKind)
        ):
            raise DomainSerializationError(
                f"Declarative field 'pack_kind' must be a string or DomainPackKind, "
                f"got {type(pack_kind_raw).__name__}",
                field="pack_kind",
            )
        if pack_kind_raw is not None:
            pack_kind = (
                DomainPackKind(pack_kind_raw)
                if isinstance(pack_kind_raw, str)
                else pack_kind_raw
            )
        elif experimental:
            pack_kind = DomainPackKind.EXPERIMENTAL
        else:
            pack_kind = DomainPackKind.INTERNAL

        # ── DomainId ─────────────────────────────────────────────────────
        name = data.get("name")
        if name is not None:
            _validate_declarative_str(name, "name")
        if not name:
            name = domain_id_raw.replace("domain:", "")
        domain_id = DomainId.from_str(domain_id_raw)
        manifest_id = DomainManifestId(slug=domain_id.slug, version=version)

        # ── Entrypoint ───────────────────────────────────────────────────
        entrypoint = data.get("entrypoint")
        if entrypoint is not None:
            entrypoint = _validate_declarative_opt_str(entrypoint, "entrypoint")

        # ── Components ───────────────────────────────────────────────────
        def _build_components(
            raw: Any, category: str
        ) -> tuple[DomainComponentReference, ...]:
            if raw is None:
                return ()
            if isinstance(raw, str):
                prefix = _CATEGORY_PATH_PREFIX.get(category, "")
                return (
                    DomainComponentReference(
                        id=raw.strip(),
                        path=f"{prefix}{raw.strip()}",
                    ),
                )
            if isinstance(raw, (list, tuple)):
                result: list[DomainComponentReference] = []
                for i, item in enumerate(raw):
                    if isinstance(item, str):
                        prefix = _CATEGORY_PATH_PREFIX.get(category, "")
                        result.append(
                            DomainComponentReference(
                                id=item.strip(),
                                path=f"{prefix}{item.strip()}",
                            )
                        )
                    elif isinstance(item, Mapping):
                        result.append(_build_declarative_component(item, category, i))
                    else:
                        raise DomainSerializationError(
                            f"Component in {category}[{i}] must be a string or "
                            f"mapping, got {type(item).__name__}",
                            field=f"{category}[{i}]",
                        )
                return tuple(result)
            if isinstance(raw, Mapping):
                return (_build_declarative_component(raw, category),)
            raise DomainSerializationError(
                f"Declarative {category} must be a string, list, or mapping, "
                f"got {type(raw).__name__}",
                field=category,
            )

        def _build_declarative_component(
            item: Mapping[str, Any], category: str, index: int | None = None
        ) -> DomainComponentReference:
            comp_id = item.get("id", "")
            comp_name = item.get("name", "")

            if comp_id and comp_name and comp_id != comp_name:
                raise DomainSerializationError(
                    f"Component in {category} has conflicting id='{comp_id}' "
                    f"and name='{comp_name}'",
                    field=f"{category}[{index}].id"
                    if index is not None
                    else f"{category}.id",
                )

            final_id = comp_id or comp_name
            extracted_key: str | None = None
            if not final_id:
                # Only for profiles: allow {"default": "Name"} as special case
                if category in ("profiles", "profile"):
                    for k, v in item.items():
                        if (
                            isinstance(v, str)
                            and v.strip()
                            and k not in _DECLARATIVE_COMPONENT_KNOWN
                        ):
                            final_id = v.strip()
                            extracted_key = k
                            break
                if not final_id:
                    field_prefix = (
                        f"{category}[{index}]" if index is not None else category
                    )
                    raise DomainSerializationError(
                        f"Component in {field_prefix} must have 'id' or 'name'",
                        field=field_prefix,
                    )

            # Build allowed keys for unknown field check (exclude extracted key)
            allowed_keys = set(_DECLARATIVE_COMPONENT_KNOWN)
            if extracted_key:
                allowed_keys.add(extracted_key)

            _reject_unknown_fields(
                item, frozenset(allowed_keys), f"DomainManifest.declarative.{category}"
            )

            prefix = _CATEGORY_PATH_PREFIX.get(category, "")
            path_raw = item.get("path")
            if path_raw is not None and not isinstance(path_raw, str):
                field_prefix = (
                    f"{category}[{index}].path"
                    if index is not None
                    else f"{category}.path"
                )
                raise DomainSerializationError(
                    f"Component path must be a string, got {type(path_raw).__name__}",
                    field=field_prefix,
                )
            path = path_raw if isinstance(path_raw, str) else f"{prefix}{final_id}"

            entrypoint_raw = item.get("entrypoint")
            if entrypoint_raw is not None and not isinstance(entrypoint_raw, str):
                field_prefix = (
                    f"{category}[{index}].entrypoint"
                    if index is not None
                    else f"{category}.entrypoint"
                )
                raise DomainSerializationError(
                    f"Component entrypoint must be a string, got {type(entrypoint_raw).__name__}",
                    field=field_prefix,
                )

            version_raw = item.get("version")
            if version_raw is not None and not isinstance(version_raw, str):
                field_prefix = (
                    f"{category}[{index}].version"
                    if index is not None
                    else f"{category}.version"
                )
                raise DomainSerializationError(
                    f"Component version must be a string, got {type(version_raw).__name__}",
                    field=field_prefix,
                )

            checksum_raw = item.get("checksum")
            if checksum_raw is not None and not isinstance(checksum_raw, str):
                field_prefix = (
                    f"{category}[{index}].checksum"
                    if index is not None
                    else f"{category}.checksum"
                )
                raise DomainSerializationError(
                    f"Component checksum must be a string, got {type(checksum_raw).__name__}",
                    field=field_prefix,
                )

            enabled_raw = item.get("enabled")
            if enabled_raw is not None:
                field_prefix = (
                    f"{category}[{index}].enabled"
                    if index is not None
                    else f"{category}.enabled"
                )
                if not isinstance(enabled_raw, bool):
                    raise DomainSerializationError(
                        f"Component enabled must be a boolean, got {type(enabled_raw).__name__}",
                        field=field_prefix,
                    )

            metadata_raw = item.get("metadata")
            if metadata_raw is not None and not isinstance(metadata_raw, Mapping):
                field_prefix = (
                    f"{category}[{index}].metadata"
                    if index is not None
                    else f"{category}.metadata"
                )
                raise DomainSerializationError(
                    f"Component metadata must be a mapping, got {type(metadata_raw).__name__}",
                    field=field_prefix,
                )

            kwargs: dict[str, Any] = {"id": final_id, "path": path}
            if entrypoint_raw is not None:
                kwargs["entrypoint"] = entrypoint_raw
            if version_raw is not None:
                kwargs["version"] = version_raw
            if checksum_raw is not None:
                kwargs["checksum"] = checksum_raw
            if enabled_raw is not None:
                kwargs["enabled"] = enabled_raw
            if metadata_raw is not None:
                kwargs["metadata"] = _deep_freeze(metadata_raw)
            return DomainComponentReference(**kwargs)

        # ── Profiles: handle "profile" alias ─────────────────────────────
        has_profile = "profile" in data
        has_profiles = "profiles" in data
        if has_profile and has_profiles:
            raise DomainSerializationError(
                "Cannot specify both 'profile' and 'profiles' keys — use only one",
                field="profiles",
            )
        profiles_raw = data.get("profiles", data.get("profile"))

        # ── Permissions ──────────────────────────────────────────────────
        permissions_raw = data.get("permissions")
        permissions: DomainPermissionReference | None = None
        if permissions_raw is None:
            permissions = None
        elif isinstance(permissions_raw, str):
            permissions = DomainPermissionReference(policy=permissions_raw)
        elif isinstance(permissions_raw, Mapping):
            permissions = DomainPermissionReference.from_dict(dict(permissions_raw))
        else:
            raise DomainSerializationError(
                f"Declarative 'permissions' must be a string, mapping, or None, "
                f"got {type(permissions_raw).__name__}",
                field="permissions",
            )

        # ── Dependencies ─────────────────────────────────────────────────
        dependencies_raw = data.get("dependencies")
        dependencies: list[DomainDependency] = []
        if dependencies_raw is not None:
            if not isinstance(dependencies_raw, (list, tuple)):
                raise DomainSerializationError(
                    f"Declarative 'dependencies' must be a list, "
                    f"got {type(dependencies_raw).__name__}",
                    field="dependencies",
                )
            for i, dep in enumerate(dependencies_raw):
                if isinstance(dep, str):
                    dep_id = dep if dep.startswith("domain:") else f"domain:{dep}"
                    dependencies.append(
                        DomainDependency(domain_id=dep_id, required=True)
                    )
                elif isinstance(dep, Mapping):
                    dep_dict = dict(dep)
                    # Handle alias "id" for "domain_id"
                    if (
                        "id" in dep_dict
                        and "domain_id" in dep_dict
                        and dep_dict["id"] != dep_dict["domain_id"]
                    ):
                        raise DomainSerializationError(
                            f"Dependency at index {i} has conflicting "
                            f"id='{dep_dict['id']}' and domain_id='{dep_dict['domain_id']}'",
                            field=f"dependencies[{i}]",
                        )
                    if "id" in dep_dict and "domain_id" not in dep_dict:
                        dep_dict["domain_id"] = dep_dict.pop("id")
                    dep_id = dep_dict.get("domain_id")
                    if dep_id is None:
                        raise DomainSerializationError(
                            f"Dependency at index {i} missing required 'domain_id'",
                            field=f"dependencies[{i}]",
                        )
                    if not str(dep_id).startswith("domain:"):
                        dep_id = f"domain:{dep_id}"
                    dep_dict["domain_id"] = dep_id
                    # For manifest dependencies, enforce required=True
                    dep_required = dep_dict.get("required", True)
                    if not isinstance(dep_required, bool):
                        raise DomainSerializationError(
                            f"Dependency at index {i} 'required' must be boolean, "
                            f"got {type(dep_required).__name__}",
                            field=f"dependencies[{i}].required",
                        )
                    if not dep_required:
                        raise DomainSerializationError(
                            f"Manifest dependency at index {i} must have required=True, "
                            f"got required=False",
                            field=f"dependencies[{i}].required",
                        )
                    dependencies.append(
                        DomainDependency.from_dict(
                            {**dep_dict, "domain_id": dep_id, "required": True}
                        )
                    )
                else:
                    raise DomainSerializationError(
                        f"Dependency at index {i} must be a string or mapping, "
                        f"got {type(dep).__name__}",
                        field=f"dependencies[{i}]",
                    )

        # ── Conflicts ────────────────────────────────────────────────────
        conflicts_raw = data.get("conflicts")
        conflicts_list: list[DomainConflict] = []
        if conflicts_raw is not None:
            if not isinstance(conflicts_raw, (list, tuple)):
                raise DomainSerializationError(
                    f"Declarative 'conflicts' must be a list, "
                    f"got {type(conflicts_raw).__name__}",
                    field="conflicts",
                )
            for i, c in enumerate(conflicts_raw):
                if isinstance(c, str):
                    conflicts_list.append(
                        DomainConflict(
                            domain_id=c if c.startswith("domain:") else f"domain:{c}",
                            reason="conflict",
                            severity="error",
                        )
                    )
                elif isinstance(c, Mapping):
                    c_dict = dict(c)
                    # Handle alias "id" for "domain_id"
                    if (
                        "id" in c_dict
                        and "domain_id" in c_dict
                        and c_dict["id"] != c_dict["domain_id"]
                    ):
                        raise DomainSerializationError(
                            f"Conflict at index {i} has conflicting "
                            f"id='{c_dict['id']}' and domain_id='{c_dict['domain_id']}'",
                            field=f"conflicts[{i}]",
                        )
                    if "id" in c_dict and "domain_id" not in c_dict:
                        c_dict["domain_id"] = c_dict.pop("id")
                    conflicts_list.append(DomainConflict.from_dict(c_dict))
                else:
                    raise DomainSerializationError(
                        f"Conflict at index {i} must be a string or mapping, "
                        f"got {type(c).__name__}",
                        field=f"conflicts[{i}]",
                    )

        # ── Compatibility ────────────────────────────────────────────────
        compatibility_raw = data.get("compatibility")
        has_top_level_compat = (
            data.get("minimum_cmm_version") is not None
            or data.get("maximum_cmm_version") is not None
            or data.get("supported_python_versions") is not None
        )

        compatibility: DomainCompatibility | None = None
        if compatibility_raw is not None:
            if has_top_level_compat:
                raise DomainSerializationError(
                    "Cannot specify both 'compatibility' mapping and top-level "
                    "compatibility fields (minimum_cmm_version, maximum_cmm_version, "
                    "supported_python_versions)",
                    field="compatibility",
                )
            if not isinstance(compatibility_raw, Mapping):
                raise DomainSerializationError(
                    f"Declarative 'compatibility' must be a mapping, "
                    f"got {type(compatibility_raw).__name__}",
                    field="compatibility",
                )
            compatibility = DomainCompatibility.from_dict(dict(compatibility_raw))
        elif has_top_level_compat:
            compat_data: dict[str, Any] = {}
            mv = data.get("minimum_cmm_version")
            if mv is not None:
                _validate_declarative_opt_str(mv, "minimum_cmm_version")
                compat_data["minimum_cmm_version"] = mv
            xv = data.get("maximum_cmm_version")
            if xv is not None:
                _validate_declarative_opt_str(xv, "maximum_cmm_version")
                compat_data["maximum_cmm_version"] = xv
            spv = data.get("supported_python_versions")
            if spv is not None:
                compat_data["supported_python_versions"] = spv
            compatibility = DomainCompatibility.from_dict(compat_data)

        # ── Metadata ─────────────────────────────────────────────────────
        metadata_raw = data.get("metadata")
        if metadata_raw is not None and not isinstance(metadata_raw, Mapping):
            raise DomainSerializationError(
                f"Declarative 'metadata' must be a mapping, "
                f"got {type(metadata_raw).__name__}",
                field="metadata",
            )

        return cls(
            id=manifest_id,
            domain_id=domain_id,
            schema_version=schema_version,
            package_version=version,
            pack_kind=pack_kind,
            entrypoint=entrypoint,
            resources=_build_components(data.get("resources"), "resources"),
            profiles=_build_components(profiles_raw, "profiles"),
            rules=_build_components(data.get("rules"), "rules"),
            operations=_build_components(data.get("operations"), "operations"),
            workflows=_build_components(data.get("workflows"), "workflows"),
            permissions=permissions,
            prompts=_build_components(data.get("prompts"), "prompts"),
            presentation=_build_components(data.get("presentation"), "presentation"),
            validators=_build_components(data.get("validators"), "validators"),
            migrations=_build_components(data.get("migrations"), "migrations"),
            fixtures=_build_components(data.get("fixtures"), "fixtures"),
            tests=_build_components(data.get("tests"), "tests"),
            dependencies=tuple(dependencies),
            conflicts=tuple(conflicts_list),
            compatibility=compatibility,
            checksum=data.get("checksum"),
            signature=data.get("signature"),
            metadata=_deep_freeze(metadata_raw),
        )


def _normalize_checksum_sig(value: str | None, field_name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise DomainContractValidationError(
            f"{field_name} must be a string, got {type(value).__name__}",
            field=field_name,
        )
    normalized = value.strip()
    if not normalized:
        return None
    max_len = 1024
    if len(normalized) > max_len:
        raise DomainContractValidationError(
            f"{field_name} is too long ({len(normalized)} > {max_len})",
            field=field_name,
        )
    return normalized


__all__ = [
    "DomainCompatibility",
    "DomainComponentReference",
    "DomainManifest",
    "DomainPermissionReference",
]
