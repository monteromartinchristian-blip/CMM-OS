"""Phase 10.2 – Tests for DomainManifest and related contracts."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from cmm.domains.contracts import DomainConflict, DomainDependency
from cmm.domains.enums import DomainPackKind
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

# ── DomainComponentReference tests ─────────────────────────────────────────────


class TestDomainComponentReference:
    """Tests for DomainComponentReference."""

    def test_valid_minimal_component(self) -> None:
        comp = DomainComponentReference(id="my_resource", path="resources/my_resource")
        assert comp.id == "my_resource"
        assert comp.path == "resources/my_resource"
        assert comp.entrypoint is None
        assert comp.version is None
        assert comp.checksum is None
        assert comp.enabled is True

    def test_valid_full_component(self) -> None:
        comp = DomainComponentReference(
            id="my_rule",
            path="rules/my_rule.py",
            entrypoint="main.py",
            version="1.0.0",
            checksum="abc123",
            enabled=False,
            metadata={"tags": ["security"]},
        )
        assert comp.id == "my_rule"
        assert comp.enabled is False
        assert comp.version == "1.0.0"

    def test_empty_id_rejected(self) -> None:
        with pytest.raises(DomainContractValidationError, match="non-empty"):
            DomainComponentReference(id="", path="foo")

    def test_whitespace_id_rejected(self) -> None:
        with pytest.raises(DomainContractValidationError, match="non-empty"):
            DomainComponentReference(id="   ", path="foo")

    def test_empty_path_rejected(self) -> None:
        with pytest.raises(DomainContractValidationError, match="non-empty path"):
            DomainComponentReference(id="x", path="")

    def test_absolute_path_rejected(self) -> None:
        with pytest.raises(DomainContractValidationError, match="absolute"):
            DomainComponentReference(id="x", path="/etc/passwd")

    def test_path_traversal_rejected(self) -> None:
        with pytest.raises(DomainContractValidationError, match="path traversal"):
            DomainComponentReference(id="x", path="resources/../etc/passwd")

    def test_path_traversal_double_dot_only_rejected(self) -> None:
        with pytest.raises(DomainContractValidationError, match="path traversal"):
            DomainComponentReference(id="x", path="..")

    def test_empty_segment_rejected(self) -> None:
        with pytest.raises(DomainContractValidationError, match="empty path segments"):
            DomainComponentReference(id="x", path="foo//bar")

    def test_windows_style_path_normalized(self) -> None:
        comp = DomainComponentReference(id="x", path="resources\\my_res")
        assert comp.path == "resources/my_res"

    def test_windows_drive_letter_rejected(self) -> None:
        with pytest.raises(DomainContractValidationError, match="drive letter"):
            DomainComponentReference(id="x", path="C:\\foo\\bar")

    def test_entrypoint_absolute_rejected(self) -> None:
        with pytest.raises(DomainContractValidationError, match="absolute"):
            DomainComponentReference(id="x", path="foo", entrypoint="/main.py")

    def test_entrypoint_empty_becomes_none(self) -> None:
        comp = DomainComponentReference(id="x", path="foo", entrypoint="")
        assert comp.entrypoint is None

    def test_entrypoint_traversal_rejected(self) -> None:
        with pytest.raises(DomainContractValidationError, match="path traversal"):
            DomainComponentReference(id="x", path="foo", entrypoint="../main.py")

    def test_version_empty_becomes_none(self) -> None:
        comp = DomainComponentReference(id="x", path="foo", version="")
        assert comp.version is None

    def test_checksum_empty_becomes_none(self) -> None:
        comp = DomainComponentReference(id="x", path="foo", checksum="")
        assert comp.checksum is None

    def test_non_bool_enabled_rejected(self) -> None:
        with pytest.raises(DomainContractValidationError, match="boolean"):
            DomainComponentReference(id="x", path="foo", enabled=1)  # type: ignore[arg-type]

    def test_enabled_with_truthy_int_rejected(self) -> None:
        with pytest.raises(DomainContractValidationError, match="boolean"):
            DomainComponentReference(id="x", path="foo", enabled=1)  # type: ignore[arg-type]

    def test_metadata_with_credential_key_rejected(self) -> None:
        with pytest.raises(DomainContractValidationError, match="Credential-like key"):
            DomainComponentReference(
                id="x", path="foo", metadata={"password": "secret123"}
            )

    def test_metadata_with_token_rejected(self) -> None:
        with pytest.raises(DomainContractValidationError, match="Credential-like key"):
            DomainComponentReference(id="x", path="foo", metadata={"api_token": "abc"})

    def test_metadata_deep_frozen(self) -> None:
        comp = DomainComponentReference(
            id="x", path="foo", metadata={"nested": {"key": "val"}}
        )
        with pytest.raises(TypeError):
            comp.metadata["new"] = "bad"  # type: ignore[index]

    def test_to_dict(self) -> None:
        comp = DomainComponentReference(
            id="my_res", path="resources/my_res", version="1.0"
        )
        d = comp.to_dict()
        assert d == {
            "id": "my_res",
            "path": "resources/my_res",
            "entrypoint": None,
            "version": "1.0",
            "checksum": None,
            "enabled": True,
            "metadata": {},
        }

    def test_from_dict_valid(self) -> None:
        comp = DomainComponentReference.from_dict(
            {"id": "res", "path": "resources/res"}
        )
        assert comp.id == "res"

    def test_from_dict_missing_id(self) -> None:
        with pytest.raises(DomainSerializationError, match="missing"):
            DomainComponentReference.from_dict({"path": "x"})

    def test_from_dict_missing_path(self) -> None:
        with pytest.raises(DomainSerializationError, match="missing"):
            DomainComponentReference.from_dict({"id": "x"})

    def test_from_dict_unknown_fields(self) -> None:
        with pytest.raises(DomainSerializationError, match="unknown fields"):
            DomainComponentReference.from_dict({"id": "x", "path": "y", "foo": "bar"})

    def test_from_dict_non_mapping(self) -> None:
        with pytest.raises(DomainSerializationError, match="mapping"):
            DomainComponentReference.from_dict("bad")  # type: ignore[arg-type]

    def test_from_dict_non_bool_enabled(self) -> None:
        with pytest.raises(DomainSerializationError, match="boolean"):
            DomainComponentReference.from_dict({"id": "x", "path": "y", "enabled": 1})

    def test_round_trip(self) -> None:
        original = DomainComponentReference(
            id="comp",
            path="rules/comp.py",
            entrypoint="main.py",
            version="2.0",
            checksum="sha256:abc",
            enabled=False,
            metadata={"key": "value"},
        )
        restored = DomainComponentReference.from_dict(original.to_dict())
        assert restored.id == original.id
        assert restored.path == original.path
        assert restored.entrypoint == original.entrypoint
        assert restored.version == original.version
        assert restored.checksum == original.checksum
        assert restored.enabled == original.enabled


# ── DomainPermissionReference tests ────────────────────────────────────────────


class TestDomainPermissionReference:
    """Tests for DomainPermissionReference."""

    def test_valid_minimal(self) -> None:
        perm = DomainPermissionReference(policy="permissions/domain.yaml")
        assert perm.policy == "permissions/domain.yaml"
        assert perm.required_permissions == ()
        assert perm.optional_permissions == ()

    def test_valid_full(self) -> None:
        perm = DomainPermissionReference(
            policy="permissions/domain.yaml",
            required_permissions=("read_db", "write_log"),
            optional_permissions=("send_email",),
            metadata={"description": "test"},
        )
        assert perm.required_permissions == ("read_db", "write_log")
        assert perm.optional_permissions == ("send_email",)

    def test_policy_absolute_rejected(self) -> None:
        with pytest.raises(DomainContractValidationError, match="absolute"):
            DomainPermissionReference(policy="/etc/policy.yaml")

    def test_policy_traversal_rejected(self) -> None:
        with pytest.raises(DomainContractValidationError, match="path traversal"):
            DomainPermissionReference(policy="../etc/policy.yaml")

    def test_empty_perm_rejected(self) -> None:
        with pytest.raises(DomainContractValidationError, match="non-empty"):
            DomainPermissionReference(policy="x.yaml", required_permissions=("",))

    def test_duplicate_perm_rejected(self) -> None:
        with pytest.raises(DomainContractValidationError, match="Duplicate"):
            DomainPermissionReference(
                policy="x.yaml",
                required_permissions=("a", "a"),
            )

    def test_overlap_required_and_optional_rejected(self) -> None:
        with pytest.raises(DomainContractValidationError, match="cannot be both"):
            DomainPermissionReference(
                policy="x.yaml",
                required_permissions=("a",),
                optional_permissions=("a",),
            )

    def test_credential_in_metadata_rejected(self) -> None:
        with pytest.raises(DomainContractValidationError, match="Credential-like key"):
            DomainPermissionReference(policy="x.yaml", metadata={"secret": "abc"})

    def test_to_dict(self) -> None:
        perm = DomainPermissionReference(
            policy="p.yaml", required_permissions=("a", "b")
        )
        d = perm.to_dict()
        assert d["policy"] == "p.yaml"
        assert d["required_permissions"] == ["a", "b"]
        assert d["optional_permissions"] == []

    def test_from_dict(self) -> None:
        perm = DomainPermissionReference.from_dict(
            {
                "policy": "p.yaml",
                "required_permissions": ["x"],
                "optional_permissions": ["y"],
            }
        )
        assert perm.policy == "p.yaml"
        assert perm.required_permissions == ("x",)
        assert perm.optional_permissions == ("y",)

    def test_from_dict_missing_policy(self) -> None:
        with pytest.raises(DomainSerializationError, match="missing"):
            DomainPermissionReference.from_dict({})

    def test_round_trip(self) -> None:
        original = DomainPermissionReference(
            policy="permissions/test.yaml",
            required_permissions=("p1", "p2"),
            optional_permissions=("p3",),
            metadata={"note": "test"},
        )
        restored = DomainPermissionReference.from_dict(original.to_dict())
        assert restored.policy == original.policy
        assert restored.required_permissions == original.required_permissions
        assert restored.optional_permissions == original.optional_permissions
        assert dict(restored.metadata) == dict(original.metadata)


# ── DomainCompatibility tests ──────────────────────────────────────────────────


class TestDomainCompatibility:
    """Tests for DomainCompatibility."""

    def test_empty_compatibility(self) -> None:
        compat = DomainCompatibility()
        assert compat.minimum_cmm_version is None
        assert compat.maximum_cmm_version is None

    def test_empty_versions_become_none(self) -> None:
        compat = DomainCompatibility(minimum_cmm_version="", maximum_cmm_version="")
        assert compat.minimum_cmm_version is None
        assert compat.maximum_cmm_version is None

    def test_collections_no_empty_items(self) -> None:
        with pytest.raises(DomainContractValidationError, match="non-empty"):
            DomainCompatibility(supported_python_versions=("3.10", "", "3.11"))

    def test_collections_no_duplicates(self) -> None:
        with pytest.raises(DomainContractValidationError, match="Duplicate"):
            DomainCompatibility(supported_python_versions=("3.10", "3.10"))

    def test_feature_overlap_rejected(self) -> None:
        with pytest.raises(
            DomainContractValidationError, match="both required and incompatible"
        ):
            DomainCompatibility(
                required_features=("feat_a",),
                incompatible_features=("feat_a",),
            )

    def test_credential_in_metadata_rejected(self) -> None:
        with pytest.raises(DomainContractValidationError, match="Credential-like key"):
            DomainCompatibility(metadata={"api_key": "abc"})

    def test_deep_frozen_metadata(self) -> None:
        compat = DomainCompatibility(metadata={"key": "val"})
        with pytest.raises(TypeError):
            compat.metadata["x"] = "y"  # type: ignore[index]

    def test_to_dict(self) -> None:
        compat = DomainCompatibility(
            minimum_cmm_version="1.0",
            supported_python_versions=("3.10", "3.11"),
            required_features=("f1",),
        )
        d = compat.to_dict()
        assert d["minimum_cmm_version"] == "1.0"
        assert d["supported_python_versions"] == ["3.10", "3.11"]
        assert d["required_features"] == ["f1"]

    def test_from_dict(self) -> None:
        compat = DomainCompatibility.from_dict(
            {
                "minimum_cmm_version": "2.0",
                "supported_python_versions": ["3.10"],
            }
        )
        assert compat.minimum_cmm_version == "2.0"

    def test_from_dict_unknown_fields(self) -> None:
        with pytest.raises(DomainSerializationError, match="unknown fields"):
            DomainCompatibility.from_dict({"foo": "bar"})

    def test_round_trip(self) -> None:
        original = DomainCompatibility(
            minimum_cmm_version="1.0",
            maximum_cmm_version="2.0",
            supported_python_versions=("3.10", "3.11"),
            supported_platforms=("linux",),
            required_features=("feat1",),
            incompatible_features=("feat2",),
            metadata={"notes": "test"},
        )
        restored = DomainCompatibility.from_dict(original.to_dict())
        assert restored.minimum_cmm_version == original.minimum_cmm_version
        assert restored.supported_python_versions == original.supported_python_versions
        assert restored.required_features == original.required_features


# ── DomainManifest tests (full contractual format) ─────────────────────────────


class TestDomainManifestFull:
    """Tests for DomainManifest in full contractual format."""

    @pytest.fixture
    def minimal_data(self) -> dict:
        return {
            "id": "manifest:university:1.0.0",
            "domain_id": "domain:university",
            "schema_version": "1",
            "package_version": "1.0.0",
            "pack_kind": "internal",
        }

    def test_valid_minimal_manifest(self, minimal_data: dict) -> None:
        m = DomainManifest(**minimal_data)
        assert m.id.slug == "university"
        assert m.id.version == "1.0.0"
        assert m.pack_kind == DomainPackKind.INTERNAL

    def test_schema_version_required(self, minimal_data: dict) -> None:
        with pytest.raises(DomainContractValidationError, match="non-empty"):
            DomainManifest(**{**minimal_data, "schema_version": ""})

    def test_package_version_required(self, minimal_data: dict) -> None:
        with pytest.raises(DomainContractValidationError, match="non-empty"):
            DomainManifest(**{**minimal_data, "package_version": ""})

    def test_id_slug_mismatch_rejected(self) -> None:
        with pytest.raises(DomainContractValidationError, match="slug.*must match"):
            DomainManifest(
                id=DomainManifestId(slug="other", version="1.0"),
                domain_id=DomainId(slug="university"),
                schema_version="1",
                package_version="1.0",
                pack_kind=DomainPackKind.INTERNAL,
            )

    def test_id_version_mismatch_rejected(self) -> None:
        with pytest.raises(DomainContractValidationError, match="version.*must match"):
            DomainManifest(
                id=DomainManifestId(slug="university", version="2.0"),
                domain_id=DomainId(slug="university"),
                schema_version="1",
                package_version="1.0",
                pack_kind=DomainPackKind.INTERNAL,
            )

    def test_entrypoint_empty_becomes_none(self, minimal_data: dict) -> None:
        m = DomainManifest(**{**minimal_data, "entrypoint": ""})
        assert m.entrypoint is None

    def test_entrypoint_absolute_rejected(self, minimal_data: dict) -> None:
        with pytest.raises(DomainContractValidationError, match="absolute"):
            DomainManifest(**{**minimal_data, "entrypoint": "/main.py"})

    def test_entrypoint_traversal_rejected(self, minimal_data: dict) -> None:
        with pytest.raises(DomainContractValidationError, match="path traversal"):
            DomainManifest(**{**minimal_data, "entrypoint": "../main.py"})

    def test_component_id_uniqueness(self, minimal_data: dict) -> None:
        comp = DomainComponentReference(id="same", path="resources/a")
        with pytest.raises(
            DomainContractValidationError, match="Duplicate component id"
        ):
            DomainManifest(
                **minimal_data,
                resources=(comp,),
                rules=(DomainComponentReference(id="same", path="rules/b"),),
            )

    def test_component_path_uniqueness(self, minimal_data: dict) -> None:
        comp1 = DomainComponentReference(id="a", path="resources/same")
        comp2 = DomainComponentReference(id="b", path="resources/same")
        with pytest.raises(
            DomainContractValidationError, match="Duplicate component path"
        ):
            DomainManifest(**minimal_data, resources=(comp1,), rules=(comp2,))

    def test_dependencies_unique(self, minimal_data: dict) -> None:
        dep = DomainDependency(domain_id="domain:other")
        with pytest.raises(DomainContractValidationError, match="Duplicate dependency"):
            DomainManifest(**minimal_data, dependencies=(dep, dep))

    def test_conflicts_unique(self, minimal_data: dict) -> None:
        conf = DomainConflict(
            domain_id="domain:other", reason="conflict", severity="error"
        )
        with pytest.raises(DomainContractValidationError, match="Duplicate conflict"):
            DomainManifest(**minimal_data, conflicts=(conf, conf))

    def test_self_dependency_rejected(self, minimal_data: dict) -> None:
        with pytest.raises(
            DomainContractValidationError, match="cannot depend on itself"
        ):
            DomainManifest(
                **minimal_data,
                dependencies=(DomainDependency(domain_id="domain:university"),),
            )

    def test_self_conflict_rejected(self, minimal_data: dict) -> None:
        with pytest.raises(
            DomainContractValidationError, match="cannot conflict with itself"
        ):
            DomainManifest(
                **minimal_data,
                conflicts=(
                    DomainConflict(
                        domain_id="domain:university",
                        reason="test",
                        severity="error",
                    ),
                ),
            )

    def test_dependency_and_conflict_same_domain_rejected(
        self, minimal_data: dict
    ) -> None:
        with pytest.raises(
            DomainContractValidationError,
            match="both dependency and conflict",
        ):
            DomainManifest(
                **minimal_data,
                dependencies=(DomainDependency(domain_id="domain:other"),),
                conflicts=(
                    DomainConflict(
                        domain_id="domain:other",
                        reason="test",
                        severity="error",
                    ),
                ),
            )

    def test_dependency_must_be_required(self, minimal_data: dict) -> None:
        with pytest.raises(
            DomainContractValidationError, match="must have required=True"
        ):
            DomainManifest(
                **minimal_data,
                dependencies=(
                    DomainDependency(domain_id="domain:other", required=False),
                ),
            )

    def test_checksum_empty_becomes_none(self, minimal_data: dict) -> None:
        m = DomainManifest(**{**minimal_data, "checksum": ""})
        assert m.checksum is None

    def test_signature_empty_becomes_none(self, minimal_data: dict) -> None:
        m = DomainManifest(**{**minimal_data, "signature": "  "})
        assert m.signature is None

    def test_checksum_too_long_rejected(self, minimal_data: dict) -> None:
        with pytest.raises(DomainContractValidationError, match="too long"):
            DomainManifest(**{**minimal_data, "checksum": "x" * 2000})

    def test_credential_in_manifest_metadata_rejected(self, minimal_data: dict) -> None:
        with pytest.raises(DomainContractValidationError, match="Credential-like key"):
            DomainManifest(**{**minimal_data, "metadata": {"token": "abc"}})

    def test_credential_in_component_metadata_rejected(
        self, minimal_data: dict
    ) -> None:
        # Credential keys are rejected at component creation time
        with pytest.raises(DomainContractValidationError, match="Credential-like key"):
            DomainComponentReference(
                id="r", path="resources/r", metadata={"secret": "x"}
            )

    def test_credential_in_manifest_via_raw_component(self, minimal_data: dict) -> None:
        # Credential keys in raw component mapping are caught during manifest freeze
        with pytest.raises(DomainContractValidationError, match="Credential-like key"):
            DomainManifest(
                **{
                    **minimal_data,
                    "resources": (
                        {"id": "r", "path": "resources/r", "metadata": {"secret": "x"}},
                    ),
                }
            )

    def test_nested_credential_detected(self, minimal_data: dict) -> None:
        with pytest.raises(DomainContractValidationError, match="Credential-like key"):
            DomainManifest(
                **{
                    **minimal_data,
                    "metadata": {"config": {"nested": {"password": "x"}}},
                }
            )

    def test_invalid_pack_kind(self, minimal_data: dict) -> None:
        with pytest.raises(
            DomainContractValidationError, match="Invalid DomainPackKind"
        ):
            DomainManifest(**{**minimal_data, "pack_kind": "invalid_kind"})

    def test_external_pack_kind(self, minimal_data: dict) -> None:
        m = DomainManifest(**{**minimal_data, "pack_kind": "external"})
        assert m.pack_kind == DomainPackKind.EXTERNAL

    def test_experimental_pack_kind(self, minimal_data: dict) -> None:
        m = DomainManifest(**{**minimal_data, "pack_kind": "experimental"})
        assert m.pack_kind == DomainPackKind.EXPERIMENTAL

    def test_permissions_as_mapping(self, minimal_data: dict) -> None:
        m = DomainManifest(
            **{
                **minimal_data,
                "permissions": {"policy": "permissions/u.yaml"},
            }
        )
        assert m.permissions is not None
        assert m.permissions.policy == "permissions/u.yaml"

    def test_permissions_already_instance(self, minimal_data: dict) -> None:
        perm = DomainPermissionReference(policy="perms/x.yaml")
        m = DomainManifest(**{**minimal_data, "permissions": perm})
        assert m.permissions is perm

    def test_compatibility_as_mapping(self, minimal_data: dict) -> None:
        m = DomainManifest(
            **{
                **minimal_data,
                "compatibility": {"minimum_cmm_version": "1.0"},
            }
        )
        assert m.compatibility is not None
        assert m.compatibility.minimum_cmm_version == "1.0"

    def test_to_dict(self, minimal_data: dict) -> None:
        m = DomainManifest(
            **{
                **minimal_data,
                "resources": (DomainComponentReference(id="r", path="resources/r"),),
            }
        )
        d = m.to_dict()
        assert d["id"] == "manifest:university:1.0.0"
        assert d["domain_id"] == "domain:university"
        assert d["pack_kind"] == "internal"
        assert len(d["resources"]) == 1

    def test_from_dict(self, minimal_data: dict) -> None:
        m = DomainManifest.from_dict(minimal_data)
        assert m.id.slug == "university"
        assert m.pack_kind == DomainPackKind.INTERNAL

    def test_from_dict_unknown_fields(self) -> None:
        with pytest.raises(DomainSerializationError, match="unknown fields"):
            DomainManifest.from_dict(
                {
                    "id": "x",
                    "extra": True,
                    "domain_id": "domain:x",
                    "schema_version": "1",
                    "package_version": "1.0",
                    "pack_kind": "internal",
                }
            )  # type: ignore[arg-type]

    def test_from_dict_missing_fields(self) -> None:
        with pytest.raises(DomainSerializationError, match="missing"):
            DomainManifest.from_dict({})

    def test_full_manifest_round_trip(self) -> None:
        original = DomainManifest(
            id=DomainManifestId(slug="test", version="1.0"),
            domain_id=DomainId(slug="test"),
            schema_version="1",
            package_version="1.0",
            pack_kind=DomainPackKind.INTERNAL,
            entrypoint="main.py",
            resources=(DomainComponentReference(id="r1", path="resources/r1"),),
            rules=(DomainComponentReference(id="rule1", path="rules/rule1"),),
            permissions=DomainPermissionReference(policy="perms/t.yaml"),
            compatibility=DomainCompatibility(minimum_cmm_version="1.0"),
            checksum="abc123",
            signature="sig456",
            metadata={"key": "val"},
        )
        restored = DomainManifest.from_dict(original.to_dict())
        assert restored.id == original.id
        assert restored.domain_id == original.domain_id
        assert restored.checksum == original.checksum
        assert restored.signature == original.signature
        assert restored.permissions is not None
        assert restored.compatibility is not None


# ── DomainManifest declarative format tests ────────────────────────────────────


class TestDomainManifestDeclarative:
    """Tests for DomainManifest.from_declarative_dict()."""

    def test_minimal_declarative(self) -> None:
        data = {
            "id": "domain:university",
            "name": "university",
            "display_name": "Universidad",
            "version": "1.0.0",
            "kind": "personal",
            "description": "University academic management",
        }
        m = DomainManifest.from_declarative_dict(data)
        assert m.id.slug == "university"
        assert m.package_version == "1.0.0"
        assert m.pack_kind == DomainPackKind.INTERNAL
        assert m.schema_version == "1"

    def test_declarative_with_resources_strings(self) -> None:
        data = {
            "id": "domain:university",
            "version": "1.0.0",
            "resources": ["subject", "record"],
        }
        m = DomainManifest.from_declarative_dict(data)
        assert len(m.resources) == 2
        assert m.resources[0].id == "subject"
        assert m.resources[0].path == "resources/subject"

    def test_declarative_with_profile_mapping(self) -> None:
        data = {
            "id": "domain:university",
            "version": "1.0.0",
            "profiles": {"default": "UniversityProfile"},
        }
        m = DomainManifest.from_declarative_dict(data)
        assert len(m.profiles) == 1
        assert m.profiles[0].id == "UniversityProfile"
        assert m.profiles[0].path == "profiles/UniversityProfile"

    def test_declarative_with_rules_strings(self) -> None:
        data = {
            "id": "domain:university",
            "version": "1.0.0",
            "rules": ["AcademicDeadlineRule"],
        }
        m = DomainManifest.from_declarative_dict(data)
        assert len(m.rules) == 1
        assert m.rules[0].path == "rules/AcademicDeadlineRule"

    def test_declarative_with_operations_strings(self) -> None:
        data = {
            "id": "domain:university",
            "version": "1.0.0",
            "operations": ["university.plan_semester"],
        }
        m = DomainManifest.from_declarative_dict(data)
        assert len(m.operations) == 1
        assert m.operations[0].path == "operations/university.plan_semester"

    def test_declarative_with_workflows_strings(self) -> None:
        data = {
            "id": "domain:university",
            "version": "1.0.0",
            "workflows": ["university.semester_planning"],
        }
        m = DomainManifest.from_declarative_dict(data)
        assert len(m.workflows) == 1

    def test_declarative_with_permissions(self) -> None:
        data = {
            "id": "domain:university",
            "version": "1.0.0",
            "permissions": {"policy": "permissions/university.yaml"},
        }
        m = DomainManifest.from_declarative_dict(data)
        assert m.permissions is not None
        assert m.permissions.policy == "permissions/university.yaml"

    def test_declarative_with_dependencies_strings(self) -> None:
        data = {
            "id": "domain:university",
            "version": "1.0.0",
            "dependencies": ["domain:general"],
        }
        m = DomainManifest.from_declarative_dict(data)
        assert len(m.dependencies) == 1
        assert m.dependencies[0].domain_id.slug == "general"
        assert m.dependencies[0].required is True

    def test_declarative_experimental_pack(self) -> None:
        data = {
            "id": "domain:university",
            "version": "1.0.0",
            "experimental": True,
        }
        m = DomainManifest.from_declarative_dict(data)
        assert m.pack_kind == DomainPackKind.EXPERIMENTAL

    def test_declarative_explicit_pack_kind(self) -> None:
        data = {
            "id": "domain:university",
            "version": "1.0.0",
            "pack_kind": "external",
        }
        m = DomainManifest.from_declarative_dict(data)
        assert m.pack_kind == DomainPackKind.EXTERNAL

    def test_declarative_missing_id(self) -> None:
        with pytest.raises(DomainSerializationError, match="id"):
            DomainManifest.from_declarative_dict({})

    def test_declarative_missing_version(self) -> None:
        with pytest.raises(DomainSerializationError, match="version"):
            DomainManifest.from_declarative_dict({"id": "domain:x"})

    def test_declarative_component_explicit_mapping(self) -> None:
        data = {
            "id": "domain:test",
            "version": "1.0",
            "resources": [
                {
                    "id": "res1",
                    "path": "custom/path.py",
                    "entrypoint": "main.py",
                    "version": "2.0",
                    "checksum": "abc",
                    "enabled": False,
                    "metadata": {"key": "val"},
                }
            ],
        }
        m = DomainManifest.from_declarative_dict(data)
        comp = m.resources[0]
        assert comp.id == "res1"
        assert comp.path == "custom/path.py"
        assert comp.entrypoint == "main.py"
        assert comp.version == "2.0"
        assert comp.checksum == "abc"
        assert comp.enabled is False

    def test_declarative_schema_version_default(self) -> None:
        data = {"id": "domain:test", "version": "1.0"}
        m = DomainManifest.from_declarative_dict(data)
        assert m.schema_version == "1"

    def test_declarative_schema_version_explicit(self) -> None:
        data = {
            "id": "domain:test",
            "version": "1.0",
            "schema_version": "2",
        }
        m = DomainManifest.from_declarative_dict(data)
        assert m.schema_version == "2"

    def test_declarative_domain_id_without_prefix(self) -> None:
        data = {"id": "university", "version": "1.0"}
        m = DomainManifest.from_declarative_dict(data)
        assert m.domain_id.slug == "university"

    def test_declarative_compatibility_top_level(self) -> None:
        data = {
            "id": "domain:test",
            "version": "1.0",
            "minimum_cmm_version": "1.0.0",
        }
        m = DomainManifest.from_declarative_dict(data)
        assert m.compatibility is not None
        assert m.compatibility.minimum_cmm_version == "1.0.0"

    def test_declarative_compatibility_full_mapping(self) -> None:
        data = {
            "id": "domain:test",
            "version": "1.0",
            "compatibility": {
                "minimum_cmm_version": "1.0",
                "supported_python_versions": ["3.10"],
            },
        }
        m = DomainManifest.from_declarative_dict(data)
        assert m.compatibility is not None
        assert m.compatibility.minimum_cmm_version == "1.0"


# ── Immutability tests ─────────────────────────────────────────────────────────


class TestImmutability:
    """Verify deep immutability of all new contracts."""

    def test_component_reference_is_frozen(self) -> None:
        comp = DomainComponentReference(id="x", path="y")
        with pytest.raises(FrozenInstanceError):
            comp.id = "z"  # type: ignore[misc]

    def test_component_metadata_frozen(self) -> None:
        comp = DomainComponentReference(id="x", path="y", metadata={"k": "v"})
        with pytest.raises(TypeError):
            comp.metadata["new"] = "bad"  # type: ignore[index]

    def test_permission_reference_is_frozen(self) -> None:
        perm = DomainPermissionReference(policy="x.yaml")
        with pytest.raises(FrozenInstanceError):
            perm.policy = "y.yaml"  # type: ignore[misc]

    def test_compatibility_is_frozen(self) -> None:
        compat = DomainCompatibility(minimum_cmm_version="1.0")
        with pytest.raises(FrozenInstanceError):
            compat.minimum_cmm_version = "2.0"  # type: ignore[misc]

    def test_manifest_is_frozen(self) -> None:
        m = DomainManifest(
            id=DomainManifestId(slug="test", version="1.0"),
            domain_id=DomainId(slug="test"),
            schema_version="1",
            package_version="1.0",
            pack_kind=DomainPackKind.INTERNAL,
        )
        with pytest.raises(FrozenInstanceError):
            m.schema_version = "2"  # type: ignore[misc]

    def test_component_tuple_immutable_via_casting(self) -> None:
        comps = (
            DomainComponentReference(id="a", path="resources/a"),
            DomainComponentReference(id="b", path="resources/b"),
        )
        # Tuples are immutable, reassignment should fail
        with pytest.raises(TypeError):
            comps[0] = DomainComponentReference(id="c", path="c")  # type: ignore[index]
