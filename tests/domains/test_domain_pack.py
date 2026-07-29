"""Phase 10.2 – Tests for DomainPack and ParsedDomainPack."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import datetime, timezone

import pytest

from cmm.domains.contracts import (
    DomainDefinition,
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
    DomainManifest,
)
from cmm.domains.pack import DomainPack, ParsedDomainPack


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


# ── DomainPack tests ───────────────────────────────────────────────────────────


class TestDomainPack:
    """Tests for DomainPack."""

    def test_valid_minimal_pack(self) -> None:
        m = _make_minimal_manifest()
        d = _make_minimal_definition()
        pack = DomainPack(definition=d, manifest=m, root_path="/opt/domains/university")
        assert pack.definition.id.slug == "university"
        assert pack.manifest.id.slug == "university"
        assert pack.root_path == "/opt/domains/university"
        assert pack.status == DomainPackStatus.DECLARED
        assert pack.source is None

    def test_def_mapping_coerced(self) -> None:
        m = _make_minimal_manifest()
        d_dict = _make_minimal_definition().to_dict()
        pack = DomainPack(definition=d_dict, manifest=m, root_path="/opt/domain")
        assert isinstance(pack.definition, DomainDefinition)

    def test_manifest_mapping_coerced(self) -> None:
        d = _make_minimal_definition()
        m_dict = _make_minimal_manifest().to_dict()
        pack = DomainPack(definition=d, manifest=m_dict, root_path="/opt/domain")
        assert isinstance(pack.manifest, DomainManifest)

    def test_non_str_definition_rejected(self) -> None:
        m = _make_minimal_manifest()
        with pytest.raises(
            DomainContractValidationError, match="DomainDefinition or mapping"
        ):
            DomainPack(definition=123, manifest=m, root_path="/opt/domain")  # type: ignore[arg-type]

    def test_non_str_manifest_rejected(self) -> None:
        d = _make_minimal_definition()
        with pytest.raises(
            DomainContractValidationError, match="DomainManifest or mapping"
        ):
            DomainPack(definition=d, manifest=123, root_path="/opt/domain")  # type: ignore[arg-type]

    def test_root_path_required(self) -> None:
        m = _make_minimal_manifest()
        d = _make_minimal_definition()
        with pytest.raises(DomainContractValidationError, match="non-empty"):
            DomainPack(definition=d, manifest=m, root_path="")

    def test_root_path_stripped(self) -> None:
        m = _make_minimal_manifest()
        d = _make_minimal_definition()
        pack = DomainPack(definition=d, manifest=m, root_path="  /opt/domain  ")
        assert pack.root_path == "/opt/domain"

    def test_root_path_backslash_normalized(self) -> None:
        m = _make_minimal_manifest()
        d = _make_minimal_definition()
        pack = DomainPack(definition=d, manifest=m, root_path="C:\\opt\\domain")
        assert pack.root_path == "C:/opt/domain"

    def test_source_empty_becomes_none(self) -> None:
        m = _make_minimal_manifest()
        d = _make_minimal_definition()
        pack = DomainPack(definition=d, manifest=m, root_path="/opt", source="")
        assert pack.source is None

    def test_source_preserved(self) -> None:
        m = _make_minimal_manifest()
        d = _make_minimal_definition()
        pack = DomainPack(
            definition=d,
            manifest=m,
            root_path="/opt",
            source="https://example.com/pack.tar.gz",
        )
        assert pack.source == "https://example.com/pack.tar.gz"

    def test_status_string_coerced(self) -> None:
        m = _make_minimal_manifest()
        d = _make_minimal_definition()
        pack = DomainPack(definition=d, manifest=m, root_path="/opt", status="valid")
        assert pack.status == DomainPackStatus.VALID

    def test_status_invalid_rejected(self) -> None:
        m = _make_minimal_manifest()
        d = _make_minimal_definition()
        with pytest.raises(
            DomainContractValidationError, match="Invalid DomainPackStatus"
        ):
            DomainPack(
                definition=d,
                manifest=m,
                root_path="/opt",
                status="nonexistent",
            )

    def test_def_manifest_slug_mismatch_rejected(self) -> None:
        m = _make_minimal_manifest(slug="university")
        d = _make_minimal_definition(slug="college")
        with pytest.raises(DomainContractValidationError, match="does not match"):
            DomainPack(definition=d, manifest=m, root_path="/opt")

    def test_def_manifest_version_mismatch_rejected(self) -> None:
        m = _make_minimal_manifest(version="1.0.0")
        d = _make_minimal_definition(version="2.0.0")
        with pytest.raises(DomainContractValidationError, match="does not match"):
            DomainPack(definition=d, manifest=m, root_path="/opt")

    def test_timestamps_valid(self) -> None:
        m = _make_minimal_manifest()
        d = _make_minimal_definition()
        installed = datetime(2025, 1, 1, tzinfo=timezone.utc)
        updated = datetime(2025, 6, 1, tzinfo=timezone.utc)
        pack = DomainPack(
            definition=d,
            manifest=m,
            root_path="/opt",
            installed_at=installed,
            updated_at=updated,
        )
        assert pack.installed_at == installed
        assert pack.updated_at == updated

    def test_updated_before_installed_rejected(self) -> None:
        m = _make_minimal_manifest()
        d = _make_minimal_definition()
        installed = datetime(2025, 6, 1, tzinfo=timezone.utc)
        updated = datetime(2025, 1, 1, tzinfo=timezone.utc)
        with pytest.raises(
            DomainContractValidationError, match="prior to installed_at"
        ):
            DomainPack(
                definition=d,
                manifest=m,
                root_path="/opt",
                installed_at=installed,
                updated_at=updated,
            )

    def test_timestamps_timezone_naive_rejected(self) -> None:
        m = _make_minimal_manifest()
        d = _make_minimal_definition()
        with pytest.raises(DomainContractValidationError, match="timezone-aware"):
            DomainPack(
                definition=d,
                manifest=m,
                root_path="/opt",
                installed_at=datetime(2025, 1, 1),  # noqa: DTZ001
            )

    def test_timestamps_from_string(self) -> None:
        m = _make_minimal_manifest()
        d = _make_minimal_definition()
        pack = DomainPack(
            definition=d,
            manifest=m,
            root_path="/opt",
            installed_at="2025-01-01T00:00:00Z",
            updated_at="2025-06-01T00:00:00+00:00",
        )
        assert pack.installed_at is not None
        assert pack.updated_at is not None
        assert pack.installed_at.tzinfo is not None

    def test_to_dict(self) -> None:
        m = _make_minimal_manifest()
        d = _make_minimal_definition()
        pack = DomainPack(definition=d, manifest=m, root_path="/opt")
        result = pack.to_dict()
        assert result["root_path"] == "/opt"
        assert result["status"] == "declared"
        assert "definition" in result
        assert "manifest" in result

    def test_from_dict(self) -> None:
        data = {
            "definition": _make_minimal_definition().to_dict(),
            "manifest": _make_minimal_manifest().to_dict(),
            "root_path": "/opt/test",
            "status": "enabled",
            "source": "https://example.com/pack.tar.gz",
        }
        pack = DomainPack.from_dict(data)
        assert pack.root_path == "/opt/test"
        assert pack.status == DomainPackStatus.ENABLED
        assert pack.source == "https://example.com/pack.tar.gz"

    def test_from_dict_missing_fields(self) -> None:
        with pytest.raises(DomainSerializationError, match="missing"):
            DomainPack.from_dict({})

    def test_from_dict_unknown_fields(self) -> None:
        data = {
            "definition": _make_minimal_definition().to_dict(),
            "manifest": _make_minimal_manifest().to_dict(),
            "root_path": "/opt",
            "extra_field": "should_fail",
        }
        with pytest.raises(DomainSerializationError, match="unknown fields"):
            DomainPack.from_dict(data)

    def test_round_trip(self) -> None:
        m = _make_minimal_manifest()
        d = _make_minimal_definition()
        original = DomainPack(
            definition=d,
            manifest=m,
            root_path="/opt/domain",
            status=DomainPackStatus.INSTALLED,
            source="https://example.com/pack.tar.gz",
            installed_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
            updated_at=datetime(2025, 6, 1, tzinfo=timezone.utc),
            metadata={"note": "test"},
        )
        restored = DomainPack.from_dict(original.to_dict())
        assert restored.root_path == original.root_path
        assert restored.status == original.status
        assert restored.source == original.source
        assert restored.installed_at == original.installed_at
        assert restored.updated_at == original.updated_at

    def test_deep_frozen_metadata(self) -> None:
        m = _make_minimal_manifest()
        d = _make_minimal_definition()
        pack = DomainPack(
            definition=d,
            manifest=m,
            root_path="/opt",
            metadata={"key": "val"},
        )
        with pytest.raises(TypeError):
            pack.metadata["new"] = "bad"  # type: ignore[index]

    def test_pack_is_frozen(self) -> None:
        m = _make_minimal_manifest()
        d = _make_minimal_definition()
        pack = DomainPack(definition=d, manifest=m, root_path="/opt")
        with pytest.raises(FrozenInstanceError):
            pack.root_path = "/opt2"  # type: ignore[misc]

    def test_all_status_values(self) -> None:
        m = _make_minimal_manifest()
        d = _make_minimal_definition()
        for status in DomainPackStatus:
            pack = DomainPack(definition=d, manifest=m, root_path="/opt", status=status)
            assert pack.status == status


# ── ParsedDomainPack tests ─────────────────────────────────────────────────────


class TestParsedDomainPack:
    """Tests for ParsedDomainPack."""

    def test_valid_from_instances(self) -> None:
        m = _make_minimal_manifest()
        d = _make_minimal_definition()
        parsed = ParsedDomainPack(definition=d, manifest=m)
        assert parsed.definition.id.slug == "university"
        assert parsed.manifest.id.slug == "university"

    def test_coherence_slug_mismatch_rejected(self) -> None:
        m = _make_minimal_manifest(slug="university")
        d = _make_minimal_definition(slug="college")
        with pytest.raises(DomainContractValidationError, match="does not match"):
            ParsedDomainPack(definition=d, manifest=m)

    def test_coherence_version_mismatch_rejected(self) -> None:
        m = _make_minimal_manifest(version="1.0.0")
        d = _make_minimal_definition(version="2.0.0")
        with pytest.raises(DomainContractValidationError, match="does not match"):
            ParsedDomainPack(definition=d, manifest=m)

    def test_coherence_manifest_id_slug_mismatch(self) -> None:
        # DomainDefinition itself validates manifest_id slug matches domain id,
        # so this will fail before ParsedDomainPack coherence checks run
        with pytest.raises(DomainContractValidationError, match="must match"):
            DomainDefinition(
                id="domain:university",
                name="university",
                display_name="University",
                version="1.0",
                kind=DomainKind.PERSONAL,
                description="test",
                manifest_id="manifest:other:1.0",
            )

    def test_coherence_definition_is_mapping(self) -> None:
        m = _make_minimal_manifest()
        d_dict = _make_minimal_definition().to_dict()
        parsed = ParsedDomainPack(definition=d_dict, manifest=m)
        assert isinstance(parsed.definition, DomainDefinition)

    def test_from_declarative_dict_minimal(self) -> None:
        data = {
            "id": "domain:university",
            "name": "university",
            "display_name": "Universidad",
            "version": "1.0.0",
            "kind": "personal",
            "description": "University academic management",
        }
        parsed = ParsedDomainPack.from_declarative_dict(data)
        assert parsed.definition.id.slug == "university"
        assert parsed.manifest.id.slug == "university"

    def test_from_declarative_dict_full(self) -> None:
        data = {
            "id": "domain:university",
            "name": "university",
            "display_name": "Universidad",
            "version": "1.0.0",
            "kind": "personal",
            "description": "University academic management",
            "minimum_cmm_version": "1.0.0",
            "resources": ["university_subject", "academic_record"],
            "rules": ["AcademicDeadlineRule"],
            "operations": ["university.plan_semester"],
            "workflows": ["university.semester_planning"],
            "permissions": {
                "policy": "permissions/university.yaml",
                "required_permissions": ["read_data"],
            },
            "dependencies": ["domain:general"],
        }
        parsed = ParsedDomainPack.from_declarative_dict(data)
        assert len(parsed.definition.resources) == 2
        assert len(parsed.manifest.resources) == 2
        # Permissions from declarative map should propagate
        assert parsed.manifest.permissions is not None
        assert parsed.manifest.permissions.policy == "permissions/university.yaml"

    def test_from_declarative_dict_experimental(self) -> None:
        data = {
            "id": "domain:test",
            "version": "1.0",
            "experimental": True,
            "author": "test",
            "license": "MIT",
        }
        parsed = ParsedDomainPack.from_declarative_dict(data)
        assert parsed.manifest.pack_kind == DomainPackKind.EXPERIMENTAL

    def test_to_dict(self) -> None:
        m = _make_minimal_manifest()
        d = _make_minimal_definition()
        parsed = ParsedDomainPack(definition=d, manifest=m)
        result = parsed.to_dict()
        assert "definition" in result
        assert "manifest" in result

    def test_from_dict(self) -> None:
        data = {
            "definition": _make_minimal_definition().to_dict(),
            "manifest": _make_minimal_manifest().to_dict(),
        }
        parsed = ParsedDomainPack.from_dict(data)
        assert parsed.definition.id.slug == "university"
        assert parsed.manifest.id.slug == "university"

    def test_from_dict_missing_fields(self) -> None:
        with pytest.raises(DomainSerializationError, match="missing"):
            ParsedDomainPack.from_dict({"definition": {}})

        with pytest.raises(DomainSerializationError, match="missing"):
            ParsedDomainPack.from_dict({"manifest": {}})

    def test_from_dict_unknown_fields(self) -> None:
        data = {
            "definition": _make_minimal_definition().to_dict(),
            "manifest": _make_minimal_manifest().to_dict(),
            "extra": True,
        }
        with pytest.raises(DomainSerializationError, match="unknown fields"):
            ParsedDomainPack.from_dict(data)
