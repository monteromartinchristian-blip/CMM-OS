"""Phase 10.2 – Serialization and round-trip tests for domain pack contracts."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from cmm.domains.contracts import (
    DomainConflict,
    DomainDefinition,
    DomainDependency,
)
from cmm.domains.enums import (
    DomainKind,
    DomainPackKind,
    DomainPackStatus,
)
from cmm.domains.errors import (
    DomainContractValidationError,
    DomainSerializationError,
)
from cmm.domains.identifiers import DomainId, DomainManifestId
from cmm.domains.manifest import (
    DomainCompatibility,
    DomainComponentReference,
    DomainManifest,
    DomainPermissionReference,
)
from cmm.domains.pack import DomainPack, ParsedDomainPack

# ── Helpers ────────────────────────────────────────────────────────────────────


def _make_minimal_manifest(
    slug: str = "university", version: str = "1.0.0"
) -> DomainManifest:
    return DomainManifest(
        id=DomainManifestId(slug=slug, version=version),
        domain_id=DomainId(slug=slug),
        schema_version="1",
        package_version=version,
        pack_kind=DomainPackKind.INTERNAL,
    )


def _make_minimal_definition(
    slug: str = "university", version: str = "1.0.0"
) -> DomainDefinition:
    return DomainDefinition(
        id=f"domain:{slug}",
        name=slug,
        display_name=slug.title(),
        version=version,
        kind=DomainKind.PERSONAL,
        description=f"{slug} description",
        manifest_id=f"manifest:{slug}:{version}",
    )


# ── DomainComponentReference serialization ─────────────────────────────────────


class TestComponentSerialization:
    """Serialization round-trip tests for DomainComponentReference."""

    def test_round_trip_minimal(self) -> None:
        original = DomainComponentReference(id="res", path="resources/res")
        restored = DomainComponentReference.from_dict(original.to_dict())
        assert restored.id == original.id
        assert restored.path == original.path
        assert restored.enabled == original.enabled

    def test_round_trip_full(self) -> None:
        original = DomainComponentReference(
            id="comp",
            path="rules/comp.py",
            entrypoint="main.py",
            version="2.0",
            checksum="sha256:abc123",
            enabled=False,
            metadata={"key": "value", "nested": {"a": 1}},
        )
        restored = DomainComponentReference.from_dict(original.to_dict())
        assert restored.id == original.id
        assert restored.entrypoint == original.entrypoint
        assert restored.version == original.version
        assert restored.checksum == original.checksum
        assert restored.enabled == original.enabled
        assert dict(restored.metadata) == dict(original.metadata)

    def test_reject_unknown_fields(self) -> None:
        with pytest.raises(DomainSerializationError, match="unknown fields"):
            DomainComponentReference.from_dict({"id": "x", "path": "y", "unknown": 1})

    def test_reject_missing_required(self) -> None:
        with pytest.raises(DomainSerializationError, match="missing"):
            DomainComponentReference.from_dict({"id": "x"})

    def test_reject_non_mapping(self) -> None:
        with pytest.raises(DomainSerializationError, match="mapping"):
            DomainComponentReference.from_dict([1, 2, 3])  # type: ignore[arg-type]


# ── DomainPermissionReference serialization ────────────────────────────────────


class TestPermissionSerialization:
    """Serialization round-trip tests for DomainPermissionReference."""

    def test_round_trip_minimal(self) -> None:
        original = DomainPermissionReference(policy="permissions/x.yaml")
        restored = DomainPermissionReference.from_dict(original.to_dict())
        assert restored.policy == original.policy

    def test_round_trip_full(self) -> None:
        original = DomainPermissionReference(
            policy="permissions/test.yaml",
            required_permissions=("p1", "p2"),
            optional_permissions=("p3",),
            metadata={"note": "test"},
        )
        restored = DomainPermissionReference.from_dict(original.to_dict())
        assert restored.required_permissions == original.required_permissions
        assert restored.optional_permissions == original.optional_permissions
        assert dict(restored.metadata) == dict(original.metadata)

    def test_reject_unknown_fields(self) -> None:
        with pytest.raises(DomainSerializationError, match="unknown fields"):
            DomainPermissionReference.from_dict({"policy": "x.yaml", "extra": "bad"})

    def test_reject_missing_policy(self) -> None:
        with pytest.raises(DomainSerializationError, match="missing"):
            DomainPermissionReference.from_dict({})


# ── DomainCompatibility serialization ──────────────────────────────────────────


class TestCompatibilitySerialization:
    """Serialization round-trip tests for DomainCompatibility."""

    def test_round_trip_empty(self) -> None:
        original = DomainCompatibility()
        restored = DomainCompatibility.from_dict(original.to_dict())
        assert restored.minimum_cmm_version is None

    def test_round_trip_full(self) -> None:
        original = DomainCompatibility(
            minimum_cmm_version="1.0",
            maximum_cmm_version="2.0",
            supported_python_versions=("3.10", "3.11"),
            supported_platforms=("linux", "darwin"),
            required_features=("feat1",),
            incompatible_features=("feat2",),
            metadata={"notes": "test"},
        )
        restored = DomainCompatibility.from_dict(original.to_dict())
        assert restored.minimum_cmm_version == original.minimum_cmm_version
        assert restored.maximum_cmm_version == original.maximum_cmm_version
        assert restored.supported_python_versions == original.supported_python_versions
        assert restored.supported_platforms == original.supported_platforms
        assert restored.required_features == original.required_features
        assert restored.incompatible_features == original.incompatible_features
        assert dict(restored.metadata) == dict(original.metadata)

    def test_reject_unknown_fields(self) -> None:
        with pytest.raises(DomainSerializationError, match="unknown fields"):
            DomainCompatibility.from_dict({"extra": True})


# ── DomainManifest serialization ───────────────────────────────────────────────


class TestManifestSerialization:
    """Serialization round-trip tests for DomainManifest."""

    def test_round_trip_minimal(self) -> None:
        original = _make_minimal_manifest()
        restored = DomainManifest.from_dict(original.to_dict())
        assert str(restored.id) == str(original.id)
        assert str(restored.domain_id) == str(original.domain_id)
        assert restored.pack_kind == original.pack_kind

    def test_round_trip_full(self) -> None:
        original = DomainManifest(
            id=DomainManifestId(slug="test", version="2.0"),
            domain_id=DomainId(slug="test"),
            schema_version="1",
            package_version="2.0",
            pack_kind=DomainPackKind.EXTERNAL,
            entrypoint="main.py",
            resources=(
                DomainComponentReference(
                    id="r1",
                    path="resources/r1",
                    version="1.0",
                    metadata={"tag": "important"},
                ),
                DomainComponentReference(id="r2", path="resources/r2"),
            ),
            profiles=(DomainComponentReference(id="default", path="profiles/default"),),
            rules=(DomainComponentReference(id="rule1", path="rules/rule1"),),
            operations=(DomainComponentReference(id="op1", path="operations/op1"),),
            permissions=DomainPermissionReference(
                policy="permissions/t.yaml",
                required_permissions=("read",),
            ),
            dependencies=(DomainDependency(domain_id="domain:base", required=True),),
            conflicts=(
                DomainConflict(
                    domain_id="domain:old",
                    reason="incompatible",
                    severity="error",
                ),
            ),
            compatibility=DomainCompatibility(minimum_cmm_version="1.0"),
            checksum="abc123",
            signature="sig456",
            metadata={"key": "val"},
        )
        restored = DomainManifest.from_dict(original.to_dict())
        assert str(restored.id) == str(original.id)
        assert restored.entrypoint == original.entrypoint
        assert len(restored.resources) == len(original.resources)
        assert restored.resources[0].id == original.resources[0].id
        assert restored.resources[0].metadata["tag"] == "important"  # type: ignore[index]
        assert restored.checksum == original.checksum
        assert restored.signature == original.signature
        assert restored.permissions is not None
        assert restored.permissions.policy == original.permissions.policy  # type: ignore[union-attr]
        assert restored.compatibility is not None
        assert len(restored.dependencies) == 1
        assert len(restored.conflicts) == 1

    def test_reject_unknown_fields(self) -> None:
        with pytest.raises(DomainSerializationError, match="unknown fields"):
            DomainManifest.from_dict(
                {
                    "id": "manifest:x:1.0",
                    "domain_id": "domain:x",
                    "schema_version": "1",
                    "package_version": "1.0",
                    "pack_kind": "internal",
                    "extra": "bad",
                }
            )

    def test_reject_missing_fields(self) -> None:
        with pytest.raises(DomainSerializationError, match="missing"):
            DomainManifest.from_dict({"id": "manifest:x:1.0"})

    def test_declarative_to_contractual_round_trip(self) -> None:
        """Verify declarative → contractual round-trip produces same manifest."""
        declarative = {
            "id": "domain:university",
            "name": "university",
            "display_name": "Universidad",
            "version": "1.0.0",
            "kind": "personal",
            "description": "University academic management",
            "minimum_cmm_version": "1.0.0",
            "resources": ["subject", "record"],
            "rules": ["AcademicDeadlineRule"],
            "operations": ["university.plan_semester"],
            "workflows": ["university.semester_planning"],
            "permissions": {"policy": "permissions/university.yaml"},
            "profiles": {"default": "UniversityProfile"},
            "dependencies": ["domain:general"],
        }
        manifest_from_decl = DomainManifest.from_declarative_dict(declarative)
        # Serialize to contractual dict
        contractual_dict = manifest_from_decl.to_dict()
        # Re-parse via from_dict (contractual)
        manifest_from_contract = DomainManifest.from_dict(contractual_dict)
        # Both manifests should be equivalent
        assert str(manifest_from_decl.id) == str(manifest_from_contract.id)
        assert manifest_from_decl.pack_kind == manifest_from_contract.pack_kind
        assert len(manifest_from_decl.resources) == len(
            manifest_from_contract.resources
        )


# ── ParsedDomainPack serialization ─────────────────────────────────────────────


class TestParsedDomainPackSerialization:
    """Serialization round-trip tests for ParsedDomainPack."""

    def test_round_trip(self) -> None:
        m = _make_minimal_manifest()
        d = _make_minimal_definition()
        original = ParsedDomainPack(definition=d, manifest=m)
        restored = ParsedDomainPack.from_dict(original.to_dict())
        assert restored.definition.id == original.definition.id
        assert restored.manifest.id == original.manifest.id

    def test_round_trip_with_components(self) -> None:
        m = DomainManifest(
            id=DomainManifestId(slug="test", version="1.0"),
            domain_id=DomainId(slug="test"),
            schema_version="1",
            package_version="1.0",
            pack_kind=DomainPackKind.INTERNAL,
            resources=(DomainComponentReference(id="r1", path="resources/r1"),),
            rules=(DomainComponentReference(id="rule1", path="rules/rule1"),),
        )
        d = DomainDefinition(
            id="domain:test",
            name="test",
            display_name="Test",
            version="1.0",
            kind=DomainKind.PERSONAL,
            description="test",
            manifest_id="manifest:test:1.0",
            resources=("r1",),
            rules=("rule1",),
        )
        original = ParsedDomainPack(definition=d, manifest=m)
        restored = ParsedDomainPack.from_dict(original.to_dict())
        assert restored.definition.resources == original.definition.resources

    def test_reject_unknown_fields(self) -> None:
        data = {
            "definition": _make_minimal_definition().to_dict(),
            "manifest": _make_minimal_manifest().to_dict(),
            "extra": True,
        }
        with pytest.raises(DomainSerializationError, match="unknown fields"):
            ParsedDomainPack.from_dict(data)

    def test_reject_missing_definition(self) -> None:
        with pytest.raises(DomainSerializationError, match="missing"):
            ParsedDomainPack.from_dict({"manifest": _make_minimal_manifest().to_dict()})

    def test_reject_missing_manifest(self) -> None:
        with pytest.raises(DomainSerializationError, match="missing"):
            ParsedDomainPack.from_dict(
                {"definition": _make_minimal_definition().to_dict()}
            )


# ── DomainPack serialization ───────────────────────────────────────────────────


class TestDomainPackSerialization:
    """Serialization round-trip tests for DomainPack."""

    def test_round_trip_minimal(self) -> None:
        m = _make_minimal_manifest()
        d = _make_minimal_definition()
        original = DomainPack(definition=d, manifest=m, root_path="/opt/d")
        restored = DomainPack.from_dict(original.to_dict())
        assert restored.root_path == original.root_path
        assert restored.status == original.status

    def test_round_trip_full(self) -> None:
        m = _make_minimal_manifest()
        d = _make_minimal_definition()
        installed = datetime(2025, 1, 1, tzinfo=timezone.utc)
        updated = datetime(2025, 6, 1, tzinfo=timezone.utc)
        original = DomainPack(
            definition=d,
            manifest=m,
            root_path="/opt/domain",
            status=DomainPackStatus.INSTALLED,
            source="https://example.com/pack.tar.gz",
            installed_at=installed,
            updated_at=updated,
            metadata={"note": "test"},
        )
        restored = DomainPack.from_dict(original.to_dict())
        assert restored.root_path == original.root_path
        assert restored.status == original.status
        assert restored.source == original.source
        # Datetime comparison
        assert restored.installed_at == installed
        assert restored.updated_at == updated

    def test_reject_unknown_fields(self) -> None:
        data = {
            "definition": _make_minimal_definition().to_dict(),
            "manifest": _make_minimal_manifest().to_dict(),
            "root_path": "/opt",
            "extra": "bad",
        }
        with pytest.raises(DomainSerializationError, match="unknown fields"):
            DomainPack.from_dict(data)

    def test_reject_missing_required(self) -> None:
        with pytest.raises(DomainSerializationError, match="missing"):
            DomainPack.from_dict({})

    def test_enum_as_string_in_to_dict(self) -> None:
        m = _make_minimal_manifest()
        d = _make_minimal_definition()
        pack = DomainPack(definition=d, manifest=m, root_path="/opt")
        d_result = pack.to_dict()
        assert d_result["status"] == "declared"
        assert isinstance(d_result["status"], str)


# ── Nesting context for errors ─────────────────────────────────────────────────


class TestNestedErrorContext:
    """Verify error context is preserved for nested deserialization errors."""

    def test_invalid_component_in_manifest_from_dict(self) -> None:
        data = {
            "id": "manifest:test:1.0",
            "domain_id": "domain:test",
            "schema_version": "1",
            "package_version": "1.0",
            "pack_kind": "internal",
            "resources": [
                {"id": "r", "path": "/absolute/path"},
            ],
        }
        # from_dict passes raw mappings through — validation happens in __post_init__
        # which wraps component errors as DomainContractValidationError
        with pytest.raises(
            (DomainContractValidationError, DomainSerializationError)
        ) as exc_info:
            DomainManifest.from_dict(data)
        error = exc_info.value
        assert error.field is not None
        assert "resources" in error.field

    def test_invalid_component_in_manifest_declarative(self) -> None:
        data = {
            "id": "domain:test",
            "version": "1.0",
            "resources": [{"id": "r", "path": "../../bad"}],
        }
        # Declarative builds components immediately, so path validation fails
        with pytest.raises(DomainContractValidationError):
            DomainManifest.from_declarative_dict(data)
