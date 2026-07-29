"""Phase 10.2 – Domain Pack.

Combines a DomainDefinition with a DomainManifest into a DomainPack — the
installable, verifiable unit of domain distribution.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from types import MappingProxyType
from typing import Any

from cmm.domains.contracts import (
    DomainConflict,
    DomainDefinition,
    DomainDependency,
    DomainMetadata,
    _deep_freeze,
    _deep_unfreeze,
    _normalize_empty_to_none,
    _reject_unknown_fields,
)
from cmm.domains.enums import (
    DomainPackKind,
    DomainPackStatus,
)
from cmm.domains.errors import (
    DomainContractValidationError,
    DomainSerializationError,
)
from cmm.domains.manifest import (
    DomainManifest,
    _normalize_root_path_lexical,
)

# ── Coherence validation shared between ParsedDomainPack and DomainPack ────────


def _validate_pack_coherence(
    definition: DomainDefinition,
    manifest: DomainManifest,
    context: str = "pack",
) -> None:
    """Validate bidirectional coherence between definition and manifest.

    Checks exact match per category:
    - resources, rules, operations, workflows, validators: exact sets
    - permissions: definition permissions must be subset of manifest policy's required_permissions
    - dependencies: definition dependencies must match manifest dependencies exactly
    - conflicts: must match exactly
    - experimental: bidirectional enforcement
    """
    d = definition
    m = manifest

    # Same domain ID
    if d.id.slug != m.domain_id.slug:
        raise DomainContractValidationError(
            f"Definition domain id '{d.id.slug}' does not match manifest "
            f"domain id '{m.domain_id.slug}'",
            field="definition.id",
        )

    # Same version
    if d.version != m.package_version:
        raise DomainContractValidationError(
            f"Definition version '{d.version}' does not match manifest "
            f"package_version '{m.package_version}'",
            field="definition.version",
        )

    # Same manifest identity
    if d.manifest_id.slug != m.id.slug or d.manifest_id.version != m.id.version:
        raise DomainContractValidationError(
            f"Definition manifest_id '{d.manifest_id}' does not match "
            f"manifest id '{m.id}'",
            field="definition.manifest_id",
        )

    # ── Category-level exact match for shared categories ────────────────
    _check_category_exact(d.resources, m.resources, "resources")
    _check_category_exact(d.rules, m.rules, "rules")
    _check_category_exact(d.operations, m.operations, "operations")
    _check_category_exact(d.workflows, m.workflows, "workflows")
    _check_category_exact(d.validators, m.validators, "validators")

    # ── Permissions ─────────────────────────────────────────────────────
    if d.permissions and m.permissions:
        manifest_perms = set(m.permissions.required_permissions) | set(
            m.permissions.optional_permissions
        )
        def_perms = set(d.permissions)
        if not def_perms.issubset(manifest_perms):
            extra = def_perms - manifest_perms
            raise DomainContractValidationError(
                f"Definition permissions not in manifest: {sorted(extra)}",
                field="definition.permissions",
            )

    # ── Dependencies exact match ────────────────────────────────────────
    def_dep_set = {(dep.domain_id.slug, dep.required) for dep in d.dependencies}
    manifest_dep_set = {(dep.domain_id.slug, dep.required) for dep in m.dependencies}
    if def_dep_set != manifest_dep_set:
        extra_def = {s for s, _ in def_dep_set} - {s for s, _ in manifest_dep_set}
        extra_man = {s for s, _ in manifest_dep_set} - {s for s, _ in def_dep_set}
        details: dict[str, Any] = {}
        if extra_def:
            details["extra_in_definition"] = sorted(extra_def)
        if extra_man:
            details["extra_in_manifest"] = sorted(extra_man)
        raise DomainContractValidationError(
            "Definition dependencies and manifest dependencies must match exactly",
            field="definition.dependencies",
            details=details,
        )

    # ── Conflicts exact match ───────────────────────────────────────────
    def_conf_set = {c.domain_id.slug for c in d.conflicts}
    manifest_conf_set = {c.domain_id.slug for c in m.conflicts}
    if def_conf_set != manifest_conf_set:
        extra_def = def_conf_set - manifest_conf_set
        extra_man = manifest_conf_set - def_conf_set
        details = {}
        if extra_def:
            details["extra_in_definition"] = sorted(extra_def)
        if extra_man:
            details["extra_in_manifest"] = sorted(extra_man)
        raise DomainContractValidationError(
            "Definition conflicts and manifest conflicts must match exactly",
            field="definition.conflicts",
            details=details,
        )

    # ── Experimental bidirectional ──────────────────────────────────────
    meta = d.metadata
    def_experimental = meta is not None and meta.experimental
    manifest_experimental = m.pack_kind == DomainPackKind.EXPERIMENTAL

    if def_experimental and not manifest_experimental:
        raise DomainContractValidationError(
            "Definition is marked experimental (metadata.experimental=True) "
            f"but manifest has pack_kind={m.pack_kind.value}",
            field="manifest.pack_kind",
        )
    if manifest_experimental:
        if meta is None:
            raise DomainContractValidationError(
                "Manifest pack_kind=EXPERIMENTAL requires "
                "DomainDefinition.metadata with experimental=True",
                field="manifest.pack_kind",
            )
        if not meta.experimental:
            raise DomainContractValidationError(
                "Manifest pack_kind=EXPERIMENTAL requires "
                "DomainDefinition.metadata.experimental=True",
                field="manifest.pack_kind",
            )


def _check_category_exact(
    def_ids: tuple[str, ...],
    manifest_comps: tuple[Any, ...],
    category: str,
) -> None:
    """Check that definition IDs and manifest component IDs match exactly."""
    def_set = set(def_ids)
    manifest_set = {comp.id for comp in manifest_comps}
    if def_set != manifest_set:
        extra_def = def_set - manifest_set
        extra_man = manifest_set - def_set
        details: dict[str, Any] = {}
        if extra_def:
            details["extra_in_definition"] = sorted(extra_def)
        if extra_man:
            details["extra_in_manifest"] = sorted(extra_man)
        raise DomainContractValidationError(
            f"Definition {category} and manifest {category} must match exactly",
            field=f"definition.{category}",
            details=details,
        )


# ── Strict type validators for from_dict ──────────────────────────────────────


def _validate_dict_str(val: Any, field_name: str) -> str:
    """Validate a value from from_dict is a real string."""
    if not isinstance(val, str):
        raise DomainSerializationError(
            f"'{field_name}' must be a string, got {type(val).__name__}: {val!r}",
            field=field_name,
        )
    return val


def _validate_dict_opt_str(val: Any, field_name: str) -> str | None:
    """Validate optional string."""
    if val is None:
        return None
    if not isinstance(val, str):
        raise DomainSerializationError(
            f"'{field_name}' must be a string or None, got {type(val).__name__}",
            field=field_name,
        )
    return val


def _validate_dict_mapping(val: Any, field_name: str) -> Mapping[str, Any]:
    """Validate a value is a mapping."""
    if not isinstance(val, Mapping):
        raise DomainSerializationError(
            f"'{field_name}' must be a mapping, got {type(val).__name__}",
            field=field_name,
        )
    return val


def _validate_dict_mapping_or_dc(val: Any, field_name: str, dc_type: type) -> Any:
    """Validate a value is a mapping or an instance of the given dataclass."""
    if not isinstance(val, (Mapping, dc_type)):
        raise DomainSerializationError(
            f"'{field_name}' must be a mapping or {dc_type.__name__}, "
            f"got {type(val).__name__}",
            field=field_name,
        )
    return val


def _parse_pack_datetime(val: Any, field_name: str) -> datetime | None:
    """Parse an optional ISO 8601 string or timezone-aware datetime. Rejects naive."""
    if val is None:
        return None
    if isinstance(val, datetime):
        if val.tzinfo is None:
            raise DomainSerializationError(
                f"'{field_name}' must be timezone-aware, got naive datetime",
                field=field_name,
            )
        return val
    if isinstance(val, str):
        try:
            parsed = datetime.fromisoformat(val)
        except ValueError as exc:
            raise DomainSerializationError(
                f"Invalid isoformat datetime string for '{field_name}': {val!r}",
                field=field_name,
            ) from exc
        if parsed.tzinfo is None:
            raise DomainSerializationError(
                f"'{field_name}' must be timezone-aware (ISO string without "
                f"timezone offset is not accepted)",
                field=field_name,
            )
        return parsed
    raise DomainSerializationError(
        f"'{field_name}' must be an ISO string or datetime instance, "
        f"got {type(val).__name__}",
        field=field_name,
    )


# ── ParsedDomainPack ───────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class ParsedDomainPack:
    """Result of parsing a declarative domain pack definition."""

    definition: DomainDefinition
    manifest: DomainManifest

    def __post_init__(self) -> None:
        if isinstance(self.definition, Mapping):
            object.__setattr__(
                self,
                "definition",
                DomainDefinition.from_dict(dict(self.definition)),
            )
        elif not isinstance(self.definition, DomainDefinition):
            raise DomainContractValidationError(
                "definition must be a DomainDefinition or mapping",
                field="definition",
            )

        if isinstance(self.manifest, Mapping):
            object.__setattr__(
                self,
                "manifest",
                DomainManifest.from_dict(dict(self.manifest)),
            )
        elif not isinstance(self.manifest, DomainManifest):
            raise DomainContractValidationError(
                "manifest must be a DomainManifest or mapping",
                field="manifest",
            )

        _validate_pack_coherence(self.definition, self.manifest, "ParsedDomainPack")

    def to_dict(self) -> dict[str, Any]:
        return {
            "definition": self.definition.to_dict(),
            "manifest": self.manifest.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ParsedDomainPack:
        """Deserialize from dictionary with strict type validation."""
        if not isinstance(data, Mapping):
            raise DomainSerializationError(
                "ParsedDomainPack.from_dict requires a mapping", field="data"
            )
        _reject_unknown_fields(
            data,
            frozenset({"definition", "manifest"}),
            "ParsedDomainPack",
        )
        if "definition" not in data:
            raise DomainSerializationError(
                "ParsedDomainPack.from_dict missing required field 'definition'",
                field="definition",
            )
        if "manifest" not in data:
            raise DomainSerializationError(
                "ParsedDomainPack.from_dict missing required field 'manifest'",
                field="manifest",
            )

        _validate_dict_mapping_or_dc(data["definition"], "definition", DomainDefinition)
        _validate_dict_mapping_or_dc(data["manifest"], "manifest", DomainManifest)

        return cls(
            definition=data["definition"],
            manifest=data["manifest"],
        )

    @classmethod
    def from_declarative_dict(cls, data: dict[str, Any]) -> ParsedDomainPack:
        """Build ParsedDomainPack from a declarative dictionary."""
        if not isinstance(data, Mapping):
            raise DomainSerializationError(
                "ParsedDomainPack.from_declarative_dict requires a mapping",
                field="data",
            )

        manifest = DomainManifest.from_declarative_dict(data)

        # Build DomainDefinition from declarative data
        name = data.get("name", manifest.domain_id.slug)
        display_name = data.get("display_name", data.get("title", name))
        description = data.get("description", f"{name} domain pack")
        domain_id_raw = data.get("id", f"domain:{manifest.domain_id.slug}")
        if not domain_id_raw.startswith("domain:"):
            domain_id_raw = f"domain:{domain_id_raw}"

        kind_raw = data.get("kind", "personal")

        # Helper to extract string IDs from declarative component entries
        def _extract_ids(raw: Any) -> tuple[str, ...]:
            if raw is None:
                return ()
            if isinstance(raw, str):
                return (raw.strip(),)
            if isinstance(raw, (list, tuple)):
                result = []
                for item in raw:
                    if isinstance(item, str):
                        result.append(item.strip())
                    elif isinstance(item, Mapping):
                        item_dict = dict(item)
                        cid = item_dict.get("id", item_dict.get("name", ""))
                        if cid:
                            result.append(str(cid).strip())
                return tuple(result)
            if isinstance(raw, Mapping):
                item_dict = dict(raw)
                cid = item_dict.get("id", item_dict.get("name", ""))
                if cid:
                    return (str(cid).strip(),)
                # Profile-like mapping: first string value
                for v in item_dict.values():
                    if isinstance(v, str) and v.strip():
                        return (v.strip(),)
                return ()
            return ()

        resources = _extract_ids(data.get("resources"))
        rules = _extract_ids(data.get("rules"))
        operations = _extract_ids(data.get("operations"))
        workflows = _extract_ids(data.get("workflows"))
        validators = _extract_ids(data.get("validators"))

        # Build definition permissions from manifest permissions (not policy path)
        permissions_list: list[str] = []
        if manifest.permissions:
            permissions_list.extend(manifest.permissions.required_permissions)
            permissions_list.extend(manifest.permissions.optional_permissions)

        # Build DomainMetadata from declarative fields — no defaults invented
        metadata: DomainMetadata | None = None
        has_meta_fields = any(
            data.get(k) is not None
            for k in (
                "author",
                "license",
                "homepage",
                "repository",
                "tags",
                "experimental",
            )
        )
        if has_meta_fields:
            author = data.get("author")
            lic = data.get("license")
            if not author or not lic:
                raise DomainSerializationError(
                    "Declarative metadata requires both 'author' and 'license' "
                    "when any metadata fields are present",
                    field="metadata",
                )
            meta_dict: dict[str, Any] = {"author": author, "license": lic}
            for key in (
                "homepage",
                "repository",
                "minimum_cmm_version",
                "maximum_cmm_version",
            ):
                if data.get(key) is not None:
                    meta_dict[key] = data[key]
            if "tags" in data:
                meta_dict["tags"] = data["tags"]
            if "experimental" in data:
                exp_val = data["experimental"]
                if not isinstance(exp_val, bool):
                    raise DomainSerializationError(
                        f"Declarative 'experimental' must be a boolean, "
                        f"got {type(exp_val).__name__}",
                        field="experimental",
                    )
                meta_dict["experimental"] = exp_val
            metadata = DomainMetadata.from_dict(meta_dict)

        # Build dependencies for definition (including optional)
        def parse_decl_dep(dep: Any, required_default: bool) -> DomainDependency:
            if isinstance(dep, str):
                dep_id = dep if dep.startswith("domain:") else f"domain:{dep}"
                return DomainDependency(domain_id=dep_id, required=required_default)
            if isinstance(dep, Mapping):
                dep_dict = dict(dep)
                if (
                    "id" in dep_dict
                    and "domain_id" in dep_dict
                    and dep_dict["id"] != dep_dict["domain_id"]
                ):
                    raise DomainSerializationError(
                        "Dependency has conflicting 'id' and 'domain_id'",
                        field="dependencies",
                    )
                if "id" in dep_dict and "domain_id" not in dep_dict:
                    dep_dict["domain_id"] = dep_dict.pop("id")
                dep_id = dep_dict.get("domain_id")
                if dep_id is None:
                    raise DomainSerializationError(
                        "Dependency missing required 'domain_id'",
                        field="dependencies",
                    )
                if not str(dep_id).startswith("domain:"):
                    dep_id = f"domain:{dep_id}"
                dep_dict["domain_id"] = dep_id
                dep_dict.setdefault("required", required_default)
                return DomainDependency.from_dict(dep_dict)
            raise DomainSerializationError(
                f"Invalid dependency format: {type(dep).__name__}",
                field="dependencies",
            )

        def_deps = tuple(
            parse_decl_dep(dep, True) for dep in data.get("dependencies", ())
        )
        opt_deps = tuple(
            parse_decl_dep(dep, False) for dep in data.get("optional_dependencies", ())
        )

        # Build definition conflicts
        def parse_decl_conf(c: Any) -> DomainConflict:
            if isinstance(c, str):
                return DomainConflict(
                    domain_id=c if c.startswith("domain:") else f"domain:{c}",
                    reason="conflict",
                    severity="error",
                )
            if isinstance(c, Mapping):
                c_dict = dict(c)
                if (
                    "id" in c_dict
                    and "domain_id" in c_dict
                    and c_dict["id"] != c_dict["domain_id"]
                ):
                    raise DomainSerializationError(
                        "Conflict has conflicting 'id' and 'domain_id'",
                        field="conflicts",
                    )
                if "id" in c_dict and "domain_id" not in c_dict:
                    c_dict["domain_id"] = c_dict.pop("id")
                return DomainConflict.from_dict(c_dict)
            raise DomainSerializationError(
                f"Invalid conflict format: {type(c).__name__}",
                field="conflicts",
            )

        def_confs = tuple(parse_decl_conf(c) for c in data.get("conflicts", ()))

        definition = DomainDefinition(
            id=domain_id_raw,
            name=name,
            display_name=display_name,
            version=manifest.package_version,
            kind=kind_raw,
            description=description,
            manifest_id=str(manifest.id),
            reasoning_profile=data.get("reasoning_profile"),
            resources=resources,
            rules=rules,
            operations=operations,
            workflows=workflows,
            permissions=tuple(permissions_list),
            validators=validators,
            presentation_policy=_deep_freeze(data.get("presentation_policy", {})),
            dependencies=def_deps,
            optional_dependencies=opt_deps,
            conflicts=def_confs,
            capabilities=tuple(data.get("capabilities", ())),
            enabled=True,
            metadata=metadata,
        )

        return cls(definition=definition, manifest=manifest)


# ── DomainPack ─────────────────────────────────────────────────────────────────

_PACK_KNOWN = frozenset(
    {
        "definition",
        "manifest",
        "root_path",
        "status",
        "source",
        "installed_at",
        "updated_at",
        "metadata",
    }
)


@dataclass(frozen=True, slots=True)
class DomainPack:
    """Immutable representation of an installable domain pack."""

    definition: DomainDefinition
    manifest: DomainManifest
    root_path: str
    status: DomainPackStatus = DomainPackStatus.DECLARED
    source: str | None = None
    installed_at: datetime | None = None
    updated_at: datetime | None = None
    metadata: MappingProxyType[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )

    def __post_init__(self) -> None:
        # ── Coerce definition ────────────────────────────────────────────
        if isinstance(self.definition, Mapping):
            object.__setattr__(
                self,
                "definition",
                DomainDefinition.from_dict(dict(self.definition)),
            )
        elif not isinstance(self.definition, DomainDefinition):
            raise DomainContractValidationError(
                "definition must be a DomainDefinition or mapping",
                field="definition",
            )

        # ── Coerce manifest ──────────────────────────────────────────────
        if isinstance(self.manifest, Mapping):
            object.__setattr__(
                self,
                "manifest",
                DomainManifest.from_dict(dict(self.manifest)),
            )
        elif not isinstance(self.manifest, DomainManifest):
            raise DomainContractValidationError(
                "manifest must be a DomainManifest or mapping",
                field="manifest",
            )

        # ── Coherence ────────────────────────────────────────────────────
        _validate_pack_coherence(self.definition, self.manifest, "DomainPack")

        # ── Root path ────────────────────────────────────────────────────
        if not isinstance(self.root_path, str):
            raise DomainContractValidationError(
                f"root_path must be a string, got {type(self.root_path).__name__}",
                field="root_path",
            )
        if not self.root_path.strip():
            raise DomainContractValidationError(
                "root_path must be a non-empty string", field="root_path"
            )
        object.__setattr__(
            self,
            "root_path",
            _normalize_root_path_lexical(self.root_path.strip()),
        )

        # ── Status ───────────────────────────────────────────────────────
        if isinstance(self.status, str):
            try:
                object.__setattr__(self, "status", DomainPackStatus(self.status))
            except ValueError as exc:
                raise DomainContractValidationError(
                    f"Invalid DomainPackStatus: {self.status!r}",
                    field="status",
                ) from exc
        elif not isinstance(self.status, DomainPackStatus):
            raise DomainContractValidationError(
                "status must be a DomainPackStatus", field="status"
            )

        # ── Source ───────────────────────────────────────────────────────
        object.__setattr__(self, "source", _normalize_empty_to_none(self.source))

        # ── Timestamps ───────────────────────────────────────────────────
        installed = self._parse_pack_dt(self.installed_at, "installed_at")
        object.__setattr__(self, "installed_at", installed)

        updated = self._parse_pack_dt(self.updated_at, "updated_at")
        object.__setattr__(self, "updated_at", updated)

        if installed is not None and updated is not None and updated < installed:
            raise DomainContractValidationError(
                "updated_at cannot be prior to installed_at",
                field="updated_at",
            )

        # ── Metadata ─────────────────────────────────────────────────────
        object.__setattr__(self, "metadata", _deep_freeze(self.metadata))

    @staticmethod
    def _parse_pack_dt(val: Any, field_name: str) -> datetime | None:
        """Parse optional datetime: timezone-aware required, naive rejected."""
        if val is None:
            return None
        if isinstance(val, datetime):
            if val.tzinfo is None:
                raise DomainContractValidationError(
                    f"{field_name} must be timezone-aware", field=field_name
                )
            return val
        if isinstance(val, str):
            try:
                parsed = datetime.fromisoformat(val)
            except ValueError as exc:
                raise DomainContractValidationError(
                    f"Invalid isoformat datetime string for {field_name}: {val!r}",
                    field=field_name,
                ) from exc
            if parsed.tzinfo is None:
                raise DomainContractValidationError(
                    f"{field_name} must be timezone-aware (ISO string without "
                    f"timezone offset is not accepted)",
                    field=field_name,
                )
            return parsed
        raise DomainContractValidationError(
            f"{field_name} must be an ISO string or datetime instance, "
            f"got {type(val).__name__}",
            field=field_name,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "definition": self.definition.to_dict(),
            "manifest": self.manifest.to_dict(),
            "root_path": self.root_path,
            "status": self.status.value,
            "source": self.source,
            "installed_at": self.installed_at.isoformat()
            if self.installed_at
            else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "metadata": _deep_unfreeze(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DomainPack:
        """Deserialize from dictionary with strict type validation."""
        if not isinstance(data, Mapping):
            raise DomainSerializationError(
                "DomainPack.from_dict requires a mapping", field="data"
            )
        _reject_unknown_fields(data, _PACK_KNOWN, "DomainPack")
        required = {"definition", "manifest", "root_path"}
        missing = required - set(data.keys())
        if missing:
            raise DomainSerializationError(
                f"DomainPack.from_dict missing required fields: {sorted(missing)}",
                field="data",
            )

        # Validate types before passing to constructor
        _validate_dict_mapping_or_dc(data["definition"], "definition", DomainDefinition)
        _validate_dict_mapping_or_dc(data["manifest"], "manifest", DomainManifest)

        root_path = data["root_path"]
        if not isinstance(root_path, str):
            raise DomainSerializationError(
                f"'root_path' must be a string, got {type(root_path).__name__}",
                field="root_path",
            )
        if not root_path.strip():
            raise DomainSerializationError(
                "'root_path' must be a non-empty string",
                field="root_path",
            )

        status_raw = data.get("status")
        if status_raw is not None and not isinstance(
            status_raw, (str, DomainPackStatus)
        ):
            raise DomainSerializationError(
                f"'status' must be a string or DomainPackStatus, "
                f"got {type(status_raw).__name__}",
                field="status",
            )

        source_raw = data.get("source")
        if source_raw is not None and not isinstance(source_raw, str):
            raise DomainSerializationError(
                f"'source' must be a string or None, got {type(source_raw).__name__}",
                field="source",
            )

        meta_raw = data.get("metadata")
        if meta_raw is not None and not isinstance(meta_raw, Mapping):
            raise DomainSerializationError(
                f"'metadata' must be a mapping or None, got {type(meta_raw).__name__}",
                field="metadata",
            )

        installed_raw = data.get("installed_at")
        updated_raw = data.get("updated_at")

        # Parse timestamps with full error context
        installed_at = None
        if installed_raw is not None:
            try:
                installed_at = _parse_pack_datetime(installed_raw, "installed_at")
            except DomainSerializationError:
                raise
            except Exception as exc:
                raise DomainSerializationError(
                    f"Invalid 'installed_at': {exc}",
                    field="installed_at",
                ) from exc

        updated_at = None
        if updated_raw is not None:
            try:
                updated_at = _parse_pack_datetime(updated_raw, "updated_at")
            except DomainSerializationError:
                raise
            except Exception as exc:
                raise DomainSerializationError(
                    f"Invalid 'updated_at': {exc}",
                    field="updated_at",
                ) from exc

        return cls(
            definition=data["definition"],
            manifest=data["manifest"],
            root_path=_normalize_root_path_lexical(root_path.strip()),
            status=status_raw if status_raw is not None else "declared",
            source=source_raw,
            installed_at=installed_at,
            updated_at=updated_at,
            metadata=_deep_freeze(meta_raw) if meta_raw is not None else None,
        )


__all__ = [
    "DomainPack",
    "ParsedDomainPack",
]
