"""Phase 10.35 — Domain SDK Builders."""

from __future__ import annotations

from typing import Any

from cmm.domains.contracts import DomainDefinition, DomainId, DomainKind
from cmm.domains.enums import DomainPackKind
from cmm.domains.manifest import DomainManifest


class ManifestBuilder:
    """Builder for constructing canonical DomainManifest instances."""

    def __init__(
        self,
        *,
        slug: str,
        version: str = "0.1.0",
        name: str | None = None,
    ) -> None:
        self._slug = slug
        self._version = version
        self._name = name or slug
        self._schema_version: str = "1"
        self._description: str | None = None
        self._entrypoint: str | None = None
        self._pack_kind: DomainPackKind = DomainPackKind.EXTERNAL
        self._metadata: dict[str, Any] = {}
        self._resources: list[Any] = []
        self._profiles: list[Any] = []
        self._rules: list[Any] = []
        self._operations: list[Any] = []
        self._workflows: list[Any] = []
        self._validators: list[Any] = []
        self._fixtures: list[Any] = []
        self._tests: list[Any] = []
        self._dependencies: list[Any] = []
        self._conflicts: list[Any] = []

    def with_name(self, name: str) -> ManifestBuilder:
        self._name = name
        return self

    def with_schema_version(self, schema_version: str) -> ManifestBuilder:
        self._schema_version = schema_version
        return self

    def with_description(self, description: str) -> ManifestBuilder:
        self._description = description
        return self

    def with_entrypoint(self, entrypoint: str | None) -> ManifestBuilder:
        self._entrypoint = entrypoint
        return self

    def with_pack_kind(self, pack_kind: str | DomainPackKind) -> ManifestBuilder:
        if isinstance(pack_kind, str):
            self._pack_kind = DomainPackKind(pack_kind)
        else:
            self._pack_kind = pack_kind
        return self

    def with_metadata(self, **metadata: Any) -> ManifestBuilder:
        self._metadata.update(metadata)
        return self

    def build(self) -> DomainManifest:
        data: dict[str, Any] = {
            "id": self._slug,
            "version": self._version,
            "schema_version": self._schema_version,
            "name": self._name,
            "pack_kind": self._pack_kind.value,
        }
        if self._description is not None:
            data["description"] = self._description
        if self._entrypoint is not None:
            data["entrypoint"] = self._entrypoint
        if self._metadata:
            data["metadata"] = self._metadata
        if self._resources:
            data["resources"] = self._resources
        if self._profiles:
            data["profiles"] = self._profiles
        if self._rules:
            data["rules"] = self._rules
        if self._operations:
            data["operations"] = self._operations
        if self._workflows:
            data["workflows"] = self._workflows
        if self._validators:
            data["validators"] = self._validators
        if self._fixtures:
            data["fixtures"] = self._fixtures
        if self._tests:
            data["tests"] = self._tests
        if self._dependencies:
            data["dependencies"] = self._dependencies
        if self._conflicts:
            data["conflicts"] = self._conflicts

        return DomainManifest.from_declarative_dict(data)

    def to_dict(self) -> dict[str, Any]:
        return self.build().to_dict()


class DomainBuilder:
    """Builder for constructing canonical DomainDefinition instances."""

    def __init__(self, manifest: DomainManifest) -> None:
        self._manifest = manifest
        self._display_name: str | None = None
        self._description: str | None = None
        self._kind: DomainKind = DomainKind.PERSONAL

    def with_display_name(self, display_name: str) -> DomainBuilder:
        self._display_name = display_name
        return self

    def with_description(self, description: str) -> DomainBuilder:
        self._description = description
        return self

    def with_kind(self, kind: str | DomainKind) -> DomainBuilder:
        if isinstance(kind, str):
            self._kind = DomainKind(kind)
        else:
            self._kind = kind
        return self

    def build(self) -> DomainDefinition:
        slug = self._manifest.domain_id.slug
        display_name = self._display_name or slug
        description = self._description or f"{slug} domain pack"

        resources = tuple(c.id for c in self._manifest.resources)
        rules = tuple(c.id for c in self._manifest.rules)
        operations = tuple(c.id for c in self._manifest.operations)
        workflows = tuple(c.id for c in self._manifest.workflows)
        validators = tuple(c.id for c in self._manifest.validators)

        permissions_list: list[str] = []
        if self._manifest.permissions:
            permissions_list.extend(self._manifest.permissions.required_permissions)
            permissions_list.extend(self._manifest.permissions.optional_permissions)

        return DomainDefinition(
            id=DomainId.from_str(f"domain:{slug}"),
            name=slug,
            display_name=display_name,
            version=self._manifest.package_version,
            kind=self._kind,
            description=description,
            manifest_id=self._manifest.id,
            resources=resources,
            rules=rules,
            operations=operations,
            workflows=workflows,
            permissions=tuple(permissions_list),
            validators=validators,
            dependencies=self._manifest.dependencies,
            conflicts=self._manifest.conflicts,
        )
